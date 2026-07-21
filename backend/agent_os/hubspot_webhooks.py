"""HubSpot inbound webhooks — HMAC-SHA256 v3 signature verification.

Signature construction (per HubSpot request-validation docs):
    hash_input = f"{METHOD}{URI}{RAW_BODY}{TIMESTAMP}"
    expected    = base64(hmac_sha256(secret, hash_input))
    compare against x-hubspot-signature-v3

URI must be the exact PUBLIC url HubSpot called (not the internal pod URL).
We honour `HUBSPOT_WEBHOOK_PUBLIC_URL` when set, else reconstruct from the
FastAPI request (works when the reverse proxy passes X-Forwarded-* correctly).

Dedupe key = `{portalId}:{subscriptionId}:{eventId}` — HubSpot does NOT
guarantee `eventId` alone is unique across the portal. Persisted to
`hubspot_webhook_events` with a unique index so retries are safe.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

from core import db, logger

WEBHOOK_EVENTS_COLL = "hubspot_webhook_events"


def _secret() -> str:
    return (os.environ.get("HUBSPOT_WEBHOOK_SECRET") or "").strip()


def webhook_configured() -> bool:
    return bool(_secret())


def _public_url_override() -> Optional[str]:
    """Operator can pin the exact public URL HubSpot sees in the .env if
    the reverse-proxy chain rewrites headers. Used verbatim in signature
    verification when set."""
    val = (os.environ.get("HUBSPOT_WEBHOOK_PUBLIC_URL") or "").strip()
    return val or None


def compute_signature(method: str, uri: str, body: bytes, timestamp: str, secret: str) -> str:
    """Return the base64-encoded HMAC-SHA256 signature HubSpot expects.

    `body` MUST be the raw request bytes exactly as HubSpot sent them —
    do NOT re-serialise the parsed JSON. Callers get the raw body via
    `await request.body()` in the FastAPI handler.
    """
    raw = f"{method}{uri}{body.decode('utf-8', errors='replace')}{timestamp}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_signature(method: str, uri: str, body: bytes, timestamp: str, signature: str) -> bool:
    """Constant-time comparison. Returns False (never raises) on any
    missing/bad input so the caller can respond with a clean 401."""
    secret = _secret()
    if not secret:
        # No secret configured → deny by default. The caller sees 401
        # and knows to configure HUBSPOT_WEBHOOK_SECRET.
        return False
    if not signature or not timestamp:
        return False
    expected = compute_signature(method, uri, body, timestamp, secret)
    try:
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def rebuild_public_uri(request) -> str:
    """Assemble the exact URL HubSpot signed. Precedence:
        1. `HUBSPOT_WEBHOOK_PUBLIC_URL` override (operator-set, wins).
        2. Reconstructed from `X-Forwarded-Proto` + `X-Forwarded-Host` + path.
        3. Fallback to the request's own URL.
    """
    override = _public_url_override()
    if override:
        return override
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    path = request.url.path
    query = request.url.query
    url = f"{proto}://{host}{path}"
    if query:
        url += f"?{query}"
    return url


async def ensure_indexes() -> None:
    await db[WEBHOOK_EVENTS_COLL].create_index("dedupe_key", unique=True)
    await db[WEBHOOK_EVENTS_COLL].create_index([("processed_at", -1)])


async def record_event(evt: dict) -> tuple[bool, str]:
    """Insert-or-skip pattern — returns (first_time, dedupe_key).

    first_time = True on first-ever insert, False on duplicate.
    dedupe_key = the exact string used (caller should reuse it for
                 `mark_processed` to avoid re-computing).

    Dedupe key composition:
        {portalId}:{subscriptionId}:{eventId} when all three fields exist.
        Falls back to a SHA-256 hash of the sorted-JSON event body when
        any field is missing — protects against malformed HubSpot retries
        that would otherwise all collide on "unknown:unknown:unknown" and
        be silently dropped as duplicates.
    """
    import hashlib
    import json as _json
    portal_id = evt.get("portalId")
    sub_id = evt.get("subscriptionId")
    event_id = evt.get("eventId")
    if portal_id is not None and sub_id is not None and event_id is not None:
        dedupe_key = f"{portal_id}:{sub_id}:{event_id}"
    else:
        # Malformed/incomplete event — hash the body so each unique payload
        # still gets its own row.
        payload = _json.dumps(evt, sort_keys=True, default=str).encode("utf-8")
        dedupe_key = "sha256:" + hashlib.sha256(payload).hexdigest()[:32]
    try:
        await db[WEBHOOK_EVENTS_COLL].insert_one({
            "dedupe_key": dedupe_key,
            "portal_id": portal_id or "unknown",
            "subscription_id": sub_id or "unknown",
            "event_id": event_id or "unknown",
            "subscription_type": evt.get("subscriptionType"),
            "object_id": evt.get("objectId"),
            "property_name": evt.get("propertyName"),
            "property_value": evt.get("propertyValue"),
            "raw": evt,
            "processed_at": None,
        })
        return True, dedupe_key
    except Exception:
        # Duplicate-key on the compound dedupe — already processed
        logger.debug(f"[hubspot-webhook] duplicate event skipped: {dedupe_key}")
        return False, dedupe_key


async def mark_processed(dedupe_key: str, outcome: str) -> None:
    from datetime import datetime, timezone
    await db[WEBHOOK_EVENTS_COLL].update_one(
        {"dedupe_key": dedupe_key},
        {"$set": {"processed_at": datetime.now(timezone.utc).isoformat(), "outcome": outcome}},
    )
