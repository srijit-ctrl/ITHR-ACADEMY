"""Onboarding email drip.

Three-stage journey for a newly-registered learner:

    Day 0  · Welcome                — sent inline from /auth/register (already live).
    Day 2+ · First-course nudge     — for learners who registered ≥ 2 days ago and
                                       still have zero enrollments.
    Day 5+ · Referral invite        — for learners who have enrolled at least once
                                       and have not yet used their personal
                                       referral code (0 successful signups).

Design constraints:
    - Idempotent: exactly one email per (user, stage) — enforced via
      `drip_send_log` unique index.
    - Safe to re-run daily by a cron or the Super Admin. Never sends the
      same stage twice to the same learner.
    - `dry_run=True` returns the counts + samples without dispatching Resend.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from core import db
from email_service import send_first_course_nudge_email, send_referral_invite_email
from referral_system import ensure_personal_code

log = logging.getLogger("onboarding_drip")

STAGE_FIRST_COURSE_NUDGE = "first-course-nudge"
STAGE_REFERRAL_INVITE = "referral-invite"

DAY_2_MIN_AGE_HOURS = 48
DAY_5_MIN_AGE_HOURS = 120

DRIP_COLLECTION = "drip_send_log"


async def _ensure_indexes() -> None:
    """One-time idempotency guarantee. Called on every run so a missing
    collection self-heals — cheap, MongoDB no-ops if the index already exists."""
    await db[DRIP_COLLECTION].create_index([("user_id", 1), ("stage", 1)], unique=True)


async def _already_sent(user_id: str, stage: str) -> bool:
    return await db[DRIP_COLLECTION].find_one({"user_id": user_id, "stage": stage}, {"_id": 1}) is not None


async def _record_send(user_id: str, stage: str, email: str, ok: bool) -> None:
    await db[DRIP_COLLECTION].insert_one({
        "user_id": user_id,
        "stage": stage,
        "email": email,
        "sent": ok,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })


async def _candidates_first_course_nudge(older_than_iso: str) -> list[dict]:
    """Users who registered ≥ 48h ago with zero enrollments and haven't been
    nudged yet. Bounded to 500 per run so a runaway job can't blast the whole DB."""
    already = await db[DRIP_COLLECTION].distinct("user_id", {"stage": STAGE_FIRST_COURSE_NUDGE})
    users = await db.users.find(
        {
            "created_at": {"$lt": older_than_iso},
            "id": {"$nin": already},
            "drip_opt_out": {"$ne": True},
            "role": {"$nin": ["super_admin", "admin"]},
        },
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "created_at": 1},
    ).to_list(500)
    out = []
    for u in users:
        if not u.get("email"):
            continue
        has_enroll = await db.enrollments.find_one({"user_id": u["id"]}, {"_id": 1})
        if has_enroll:
            continue
        out.append(u)
    return out


async def _candidates_referral_invite(older_than_iso: str) -> list[dict]:
    """Users who registered ≥ 120h ago, have ≥ 1 enrollment, have not yet
    received a referral-invite drip, and have made zero successful referrals."""
    already = await db[DRIP_COLLECTION].distinct("user_id", {"stage": STAGE_REFERRAL_INVITE})
    users = await db.users.find(
        {
            "created_at": {"$lt": older_than_iso},
            "id": {"$nin": already},
            "drip_opt_out": {"$ne": True},
            "role": {"$nin": ["super_admin", "admin"]},
        },
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "personal_referral_code": 1},
    ).to_list(500)
    out = []
    for u in users:
        if not u.get("email"):
            continue
        has_enroll = await db.enrollments.find_one({"user_id": u["id"]}, {"_id": 1})
        if not has_enroll:
            continue
        # Zero successful (any) referral signups
        has_signup = await db.referral_signups.find_one({"referrer_id": u["id"]}, {"_id": 1})
        if has_signup:
            continue
        out.append(u)
    return out


async def run_onboarding_drip(
    dry_run: bool = False,
    share_base: Optional[str] = None,
) -> dict:
    """Drive both drip stages in one pass. Returns per-stage counts.

    Callable manually from the Super Admin (`POST /api/admin/drips/onboarding/run`)
    or from any daily cron. Fully idempotent — a user who already received a
    stage is silently skipped.
    """
    await _ensure_indexes()
    now_dt = datetime.now(timezone.utc)
    day2_cut = (now_dt - timedelta(hours=DAY_2_MIN_AGE_HOURS)).isoformat()
    day5_cut = (now_dt - timedelta(hours=DAY_5_MIN_AGE_HOURS)).isoformat()

    # ---- Stage: First-course nudge -----------------------------------
    nudge_cands = await _candidates_first_course_nudge(day2_cut)
    nudge_sent = 0
    nudge_skipped = 0
    nudge_errors = 0
    nudge_samples: list[str] = []
    for u in nudge_cands:
        if await _already_sent(u["id"], STAGE_FIRST_COURSE_NUDGE):
            nudge_skipped += 1
            continue
        if dry_run:
            nudge_samples.append(u["email"])
            continue
        try:
            ok = await send_first_course_nudge_email(u["email"], u.get("full_name") or "")
        except Exception:
            log.exception(f"[drip/nudge] send failed for {u['email']}")
            ok = False
        await _record_send(u["id"], STAGE_FIRST_COURSE_NUDGE, u["email"], ok)
        if ok:
            nudge_sent += 1
        else:
            nudge_errors += 1

    # ---- Stage: Referral invite --------------------------------------
    invite_cands = await _candidates_referral_invite(day5_cut)
    invite_sent = 0
    invite_skipped = 0
    invite_errors = 0
    invite_samples: list[str] = []
    base = (share_base or "").rstrip("/")
    for u in invite_cands:
        if await _already_sent(u["id"], STAGE_REFERRAL_INVITE):
            invite_skipped += 1
            continue
        code = u.get("personal_referral_code") or await ensure_personal_code(u["id"])
        share_url = f"{base}/register?ref={code}" if base else code
        if dry_run:
            invite_samples.append(u["email"])
            continue
        try:
            ok = await send_referral_invite_email(u["email"], u.get("full_name") or "", code, share_url)
        except Exception:
            log.exception(f"[drip/invite] send failed for {u['email']}")
            ok = False
        await _record_send(u["id"], STAGE_REFERRAL_INVITE, u["email"], ok)
        if ok:
            invite_sent += 1
        else:
            invite_errors += 1

    return {
        "dry_run": dry_run,
        "generated_at": now_dt.isoformat(),
        "first_course_nudge": {
            "eligible": len(nudge_cands),
            "sent": nudge_sent,
            "skipped_already_sent": nudge_skipped,
            "errors": nudge_errors,
            "dry_run_samples": nudge_samples[:10],
        },
        "referral_invite": {
            "eligible": len(invite_cands),
            "sent": invite_sent,
            "skipped_already_sent": invite_skipped,
            "errors": invite_errors,
            "dry_run_samples": invite_samples[:10],
        },
    }
