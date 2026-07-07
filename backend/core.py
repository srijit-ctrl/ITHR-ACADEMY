"""Shared core: DB client, logger, and cross-cutting helpers."""
from __future__ import annotations

import json
import logging
import os
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ----- DB -----
mongo_url = os.environ["MONGO_URL"]
db_name = os.environ["DB_NAME"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[db_name]

# ----- Logger -----
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eaia")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_cert_id() -> str:
    # Cryptographically-random suffix (secrets, not random) — cert IDs are
    # publicly verifiable and must be unpredictable.
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"EAIA-2026-{suffix}"


def gen_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


async def log_activity(
    kind: str,
    message: str,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    target: Optional[dict] = None,
) -> None:
    """Record a super-admin-facing activity event.

    Fire-and-forget usage: `await log_activity(...)` OR wrap in
    `asyncio.create_task(...)`. Failures are swallowed — activity logging
    must NEVER block the user-facing action that triggered it.

    kind: one of "signup", "enrollment", "certificate", "org_created",
          "seat_change", "verify", "digest", "other"
    """
    try:
        await db.activity_events.insert_one({
            "id": secrets.token_hex(8),
            "kind": kind,
            "message": message,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "target": target or {},
            "created_at": now_iso(),
        })
    except Exception:
        logger.exception(f"[activity] Failed to log {kind}: {message}")


def user_to_public(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "email": doc["email"],
        "full_name": doc["full_name"],
        "role": doc["role"],
        "organization": doc.get("organization"),
        "title": doc.get("title"),
        "created_at": doc["created_at"],
        "avatar_url": doc.get("avatar_url"),
        "xp": doc.get("xp", 0),
        "streak_days": doc.get("streak_days", 0),
        # Founding-member perk — only surfaced when the user actually earned it.
        "founding_member_seq": doc.get("founding_member_seq"),
        "signup_discount_code": doc.get("signup_discount_code"),
        "founding_course_id": doc.get("founding_course_id"),
        "founding_cert_used": doc.get("founding_cert_used", False),
        # Referral payment bypass (first 500 redemptions are marked Paid).
        "payment_status": doc.get("payment_status"),
        "paid_via_referral": doc.get("paid_via_referral", False),
        "referral_seq": doc.get("referral_seq"),
    }


def compute_freshness(doc: dict) -> tuple[int, int]:
    """Return (freshness_score, days_since_review) for a course doc."""
    reviewed = doc.get("last_reviewed_at")
    if not reviewed:
        return 60, 999
    try:
        rev_dt = datetime.fromisoformat(reviewed)
        if rev_dt.tzinfo is None:
            rev_dt = rev_dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - rev_dt).days
        score = max(55, min(100, 100 - int(days * 0.45)))
        return score, days
    except Exception:
        return 70, 999


def extract_json(raw: str):
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip().strip("`").strip()
    return json.loads(cleaned)


def get_stripe(request: Request):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)
