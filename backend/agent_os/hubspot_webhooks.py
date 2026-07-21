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


async def record_event(evt: dict) -> bool:
    """Insert-or-skip pattern — returns True when this is the first time
    we've seen this event (caller should process), False on duplicate."""
    portal_id = evt.get("portalId") or "unknown"
    sub_id = evt.get("subscriptionId") or "unknown"
    event_id = evt.get("eventId") or "unknown"
    dedupe_key = f"{portal_id}:{sub_id}:{event_id}"
    try:
        await db[WEBHOOK_EVENTS_COLL].insert_one({
            "dedupe_key": dedupe_key,
            "portal_id": portal_id,
            "subscription_id": sub_id,
            "event_id": event_id,
            "subscription_type": evt.get("subscriptionType"),
            "object_id": evt.get("objectId"),
            "property_name": evt.get("propertyName"),
            "property_value": evt.get("propertyValue"),
            "raw": evt,
            "processed_at": None,
        })
        return True
    except Exception:
        # Duplicate-key on the compound dedupe — already processed
        logger.debug(f"[hubspot-webhook] duplicate event skipped: {dedupe_key}")
        return False


async def mark_processed(dedupe_key: str, outcome: str) -> None:
    from datetime import datetime, timezone
    await db[WEBHOOK_EVENTS_COLL].update_one(
        {"dedupe_key": dedupe_key},
        {"$set": {"processed_at": datetime.now(timezone.utc).isoformat(), "outcome": outcome}},
    )
