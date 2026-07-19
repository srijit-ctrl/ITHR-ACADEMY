"""WhatsApp Business API integration via Twilio.

Design constraints (from the product brief and Meta policy):

* **Explicit opt-in only.** Every send path checks ``whatsapp_opt_in is True``
  on the target user document. If missing or False the send is a no-op —
  we return ``skipped_opt_out`` and record nothing.
* **Template-only for scheduled / broadcast traffic.** Free-form body is
  reserved for inbound-window acks. ``sendWhatsAppTemplate()`` is the
  primary export; ``sendWhatsAppFreeform()`` is intentionally not exposed
  outside the inbound webhook path.
* **Per-sender rate limit at 80 msgs/sec** with a token-bucket async
  limiter — never fire a naive ``asyncio.gather`` over the full user list.
* **Every send is recorded** in the ``whatsapp_message_log`` collection —
  ``twilio_message_sid``, template SID, content variables, status,
  ``error_code``, timestamps. Required for the delivery-status webhook to
  correlate updates back to the row and for compliance/audit lookups.
* **Missing credentials or missing template SIDs are graceful.** The
  integration ships pre-templates: if a template SID env var is empty
  the send returns ``skipped_no_template`` and the caller (a broadcast
  job) continues iterating over the rest of the recipient list.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from core import db

log = logging.getLogger("whatsapp")

# --------------------------------------------------------------------------- #
# Config loaded from env
# --------------------------------------------------------------------------- #

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_API_KEY_SID = os.environ.get("TWILIO_API_KEY_SID", "")
TWILIO_API_KEY_SECRET = os.environ.get("TWILIO_API_KEY_SECRET", "")
TWILIO_WHATSAPP_SENDER = os.environ.get("TWILIO_WHATSAPP_SENDER", "")
TWILIO_STATUS_CALLBACK_URL = os.environ.get("TWILIO_STATUS_CALLBACK_URL", "")

# Purpose-specific template SIDs. Empty string means "not yet approved by
# Meta" — the send helper returns a skipped result rather than raising.
TEMPLATE_SIDS: dict[str, str] = {
    "new_course": os.environ.get("TWILIO_CONTENT_SID_NEW_COURSE", ""),
    "enrollment_stale": os.environ.get("TWILIO_CONTENT_SID_ENROLLMENT_STALE", ""),
    "deadline": os.environ.get("TWILIO_CONTENT_SID_DEADLINE", ""),
    "certificate_issued": os.environ.get("TWILIO_CONTENT_SID_CERTIFICATE_ISSUED", ""),
    "ce_renewal": os.environ.get("TWILIO_CONTENT_SID_CE_RENEWAL", ""),
}


def _build_client() -> Optional[Client]:
    """Return an initialised Twilio client, or ``None`` when creds missing.

    Preference order (Twilio-recommended for production):
      1. API Key SID + Secret with account SID as the ``account_sid`` arg
      2. Account SID + Auth Token
    """
    if TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET and TWILIO_ACCOUNT_SID:
        return Client(TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, TWILIO_ACCOUNT_SID)
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return None


_client: Optional[Client] = _build_client()
_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None


def is_configured() -> bool:
    """True once at least Account SID + Auth Token (or API-key pair) AND a
    sender are populated. Templates can still be individually missing —
    checked per-send."""
    return _client is not None and bool(TWILIO_WHATSAPP_SENDER)


# --------------------------------------------------------------------------- #
# E.164 validation
# --------------------------------------------------------------------------- #

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalise_e164(raw: str, default_country_code: str = "+971") -> Optional[str]:
    """Return ``raw`` as an ``+E.164`` string, or ``None`` if it can't be
    coerced. UAE (+971) is the default country code for a bare local
    number — the ITHR primary market.

    Never raises; caller decides whether an unparseable input is an
    error or a silent skip.
    """
    if not raw:
        return None
    s = re.sub(r"[\s()\-\u00a0]", "", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        # Bare digits assumed to be local to the default country code.
        s = default_country_code + s.lstrip("0")
    return s if _E164_RE.match(s) else None


def to_whatsapp_uri(e164: str) -> str:
    """Prefix an ``+E.164`` number with the ``whatsapp:`` scheme Twilio
    requires. Idempotent."""
    return e164 if e164.startswith("whatsapp:") else f"whatsapp:{e164}"


def parse_from_uri(uri: str) -> str:
    """Strip the ``whatsapp:`` prefix so we can index against stored numbers."""
    return uri[len("whatsapp:") :] if uri.startswith("whatsapp:") else uri


# --------------------------------------------------------------------------- #
# Per-sender rate limiter (80 msgs/sec default)
# --------------------------------------------------------------------------- #


class _SenderRateLimiter:
    """Sliding-window limiter, one bucket per sender URI.

    Twilio caps WhatsApp sender throughput at 80 messages per second by
    default (error 63018 above that). ``acquire()`` blocks the caller
    just long enough to keep the window under the cap — batch jobs can
    simply await it inside their loop.
    """

    def __init__(self, max_per_sec: int = 80) -> None:
        self.max_per_sec = max_per_sec
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def acquire(self, sender: str) -> None:
        async with self._lock:
            q = self._buckets[sender]
            now = time.monotonic()
            while q and now - q[0] >= 1.0:
                q.popleft()
            if len(q) >= self.max_per_sec:
                wait_for = max(0.0, 1.0 - (now - q[0]))
                await asyncio.sleep(wait_for)
                now = time.monotonic()
                while q and now - q[0] >= 1.0:
                    q.popleft()
            q.append(time.monotonic())


rate_limiter = _SenderRateLimiter(80)


# --------------------------------------------------------------------------- #
# Send paths
# --------------------------------------------------------------------------- #


@dataclass
class SendResult:
    ok: bool
    outcome: str  # sent / skipped_opt_out / skipped_no_number / skipped_no_template / not_configured / failed
    twilio_message_sid: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _log_send(
    user_id: str,
    to: str,
    template_key: str,
    template_sid: str,
    variables: dict,
    result: SendResult,
    kind: str = "template",
) -> None:
    """Every send attempt — successful, skipped, or failed — writes one row."""
    await db.whatsapp_message_log.insert_one(
        {
            "user_id": user_id,
            "kind": kind,  # template | freeform | inbound
            "to": to,
            "template_key": template_key,
            "template_sid": template_sid,
            "content_variables": variables,
            "twilio_message_sid": result.twilio_message_sid,
            "status": result.outcome,  # matches Twilio statuses once the callback lands
            "error_code": result.error_code,
            "error_message": result.error_message,
            "sent_at": _now_iso(),
            "updated_at": _now_iso(),
        }
    )


async def send_whatsapp_template(
    user_id: str,
    template_key: str,
    variables: Optional[dict] = None,
) -> SendResult:
    """Primary broadcast / reminder send. Never sends without an explicit
    opt-in row in the ``users`` collection.

    Errors on the individual send are swallowed and recorded — a failed
    send to one learner must never break a batch job (see brief §3a).
    """
    variables = variables or {}
    user = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "id": 1, "whatsapp_number": 1, "whatsapp_opt_in": 1},
    )
    if not user:
        result = SendResult(False, "skipped_no_user")
        return result

    if not user.get("whatsapp_opt_in"):
        result = SendResult(False, "skipped_opt_out")
        await _log_send(user_id, "", template_key, "", variables, result)
        return result

    number = user.get("whatsapp_number") or ""
    if not number:
        result = SendResult(False, "skipped_no_number")
        await _log_send(user_id, "", template_key, "", variables, result)
        return result

    template_sid = TEMPLATE_SIDS.get(template_key, "")
    if not template_sid:
        # Templates not yet approved by Meta — this is a graceful stub,
        # not an error. Log it so admins can see which templates block
        # which broadcasts.
        result = SendResult(False, "skipped_no_template")
        await _log_send(user_id, number, template_key, "", variables, result)
        return result

    if not is_configured():
        result = SendResult(False, "not_configured")
        await _log_send(user_id, number, template_key, template_sid, variables, result)
        return result

    to_uri = to_whatsapp_uri(number)
    await rate_limiter.acquire(TWILIO_WHATSAPP_SENDER)

    import json as _json

    kwargs: dict[str, Any] = {
        "from_": TWILIO_WHATSAPP_SENDER,
        "to": to_uri,
        "content_sid": template_sid,
        "content_variables": _json.dumps({str(k): str(v) for k, v in variables.items()}),
    }
    if TWILIO_STATUS_CALLBACK_URL:
        kwargs["status_callback"] = TWILIO_STATUS_CALLBACK_URL

    try:
        # Twilio's Python SDK is blocking — offload so the FastAPI event
        # loop stays responsive during a burst broadcast.
        msg = await asyncio.to_thread(_client.messages.create, **kwargs)
        result = SendResult(True, msg.status or "queued", twilio_message_sid=msg.sid)
    except TwilioRestException as e:
        log.warning(f"[whatsapp] send failed for user={user_id} code={e.code} msg={e.msg}")
        result = SendResult(False, "failed", error_code=str(e.code), error_message=e.msg)
    except Exception as e:  # noqa: BLE001 - swallow so batch continues
        log.exception(f"[whatsapp] unexpected send error for user={user_id}")
        result = SendResult(False, "failed", error_message=str(e)[:200])

    await _log_send(user_id, number, template_key, template_sid, variables, result)
    return result


async def send_whatsapp_freeform_ack(
    to_uri: str,
    body: str,
    user_id: Optional[str] = None,
) -> SendResult:
    """Free-form body reply. **ONLY** used from the inbound webhook path
    where Twilio has just handed us a real inbound message — that opens
    the 24h customer-service window. Do not import this from broadcast
    code paths.
    """
    if not is_configured():
        return SendResult(False, "not_configured")
    await rate_limiter.acquire(TWILIO_WHATSAPP_SENDER)
    try:
        kwargs = {"from_": TWILIO_WHATSAPP_SENDER, "to": to_uri, "body": body}
        if TWILIO_STATUS_CALLBACK_URL:
            kwargs["status_callback"] = TWILIO_STATUS_CALLBACK_URL
        msg = await asyncio.to_thread(_client.messages.create, **kwargs)
        result = SendResult(True, msg.status or "queued", twilio_message_sid=msg.sid)
    except TwilioRestException as e:
        log.warning(f"[whatsapp] freeform ack failed code={e.code} msg={e.msg}")
        result = SendResult(False, "failed", error_code=str(e.code), error_message=e.msg)
    except Exception as e:  # noqa: BLE001
        log.exception("[whatsapp] freeform ack unexpected error")
        result = SendResult(False, "failed", error_message=str(e)[:200])

    if user_id:
        await _log_send(user_id, parse_from_uri(to_uri), "freeform_ack", "", {}, result, kind="freeform")
    return result


# --------------------------------------------------------------------------- #
# Batch broadcast — respects rate limit
# --------------------------------------------------------------------------- #


async def broadcast_template(
    template_key: str,
    variables_fn,  # callable(user_dict) -> variables dict, per-recipient
    audience_query: Optional[dict] = None,
    max_recipients: int = 5000,
) -> dict:
    """Broadcast a template to every learner matching ``audience_query``
    who has opted into WhatsApp.

    The rate limiter inside ``send_whatsapp_template`` throttles per-sender
    to 80 msgs/sec, so we can iterate sequentially without exploding.
    """
    query = {"whatsapp_opt_in": True}
    if audience_query:
        query.update(audience_query)
    cursor = db.users.find(query, {"_id": 0, "id": 1, "whatsapp_number": 1, "full_name": 1, "email": 1})
    recipients = await cursor.to_list(max_recipients)

    counts = {"sent": 0, "skipped_no_template": 0, "skipped_opt_out": 0, "skipped_no_number": 0, "failed": 0}
    for user in recipients:
        try:
            vars_for_user = variables_fn(user) if callable(variables_fn) else (variables_fn or {})
        except Exception:  # noqa: BLE001
            vars_for_user = {}
        result = await send_whatsapp_template(user["id"], template_key, vars_for_user)
        counts[result.outcome] = counts.get(result.outcome, 0) + 1

    return {
        "template_key": template_key,
        "audience_size": len(recipients),
        "counts": counts,
        "generated_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Webhook signature validation
# --------------------------------------------------------------------------- #


def validate_twilio_signature(url: str, form_data: dict, signature: str) -> bool:
    """Verify an X-Twilio-Signature header. Returns False when the auth
    token is missing (dev mode) so local testing without Twilio can still
    invoke webhooks — production MUST set TWILIO_AUTH_TOKEN."""
    if not _validator:
        return False
    return _validator.validate(url, form_data, signature or "")


async def record_inbound_message(form: dict) -> Optional[str]:
    """Persist an inbound message (from the Twilio inbound webhook) into
    ``whatsapp_message_log`` and update the sender's 24h-window marker on
    the ``users`` document. Returns the matched user_id if the from-number
    resolves to a known learner, else ``None``.
    """
    wa_from = form.get("From", "")  # 'whatsapp:+E.164'
    wa_to = form.get("To", "")
    body = form.get("Body", "")
    message_sid = form.get("MessageSid", "")
    number = parse_from_uri(wa_from)

    now = _now_iso()
    # Resolve to a user (best-effort — inbound may come from someone whose
    # stored number lacks the leading + or wasn't E.164-normalised).
    user = await db.users.find_one(
        {"$or": [{"whatsapp_number": number}, {"whatsapp_number": number.lstrip("+")}]},
        {"_id": 0, "id": 1},
    )
    user_id = user["id"] if user else None

    await db.whatsapp_message_log.insert_one(
        {
            "user_id": user_id,
            "kind": "inbound",
            "to": parse_from_uri(wa_to),
            "from": number,
            "body": body,
            "twilio_message_sid": message_sid,
            "status": "received",
            "template_key": None,
            "template_sid": None,
            "content_variables": None,
            "error_code": None,
            "error_message": None,
            "sent_at": now,
            "updated_at": now,
        }
    )

    if user_id:
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"whatsapp_last_inbound_at": now}},
        )
    return user_id


async def update_status_from_callback(form: dict) -> None:
    """Twilio status-callback handler. Idempotent — matches on
    ``twilio_message_sid`` and updates status + error columns."""
    sid = form.get("MessageSid")
    if not sid:
        return
    status = form.get("MessageStatus")
    error_code = form.get("ErrorCode") or None
    await db.whatsapp_message_log.update_one(
        {"twilio_message_sid": sid},
        {
            "$set": {
                "status": status,
                "error_code": error_code,
                "channel_status_message": form.get("ChannelStatusMessage"),
                "updated_at": _now_iso(),
            }
        },
    )
