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


async def _process_stage(
    *,
    stage: str,
    candidates: list[dict],
    dry_run: bool,
    send_fn,
) -> dict:
    """Generic per-stage driver. Applies idempotency guard, dispatches
    the per-candidate ``send_fn(user_dict) -> awaitable[bool]``, and
    returns the standard counts contract used by ``run_onboarding_drip``.

    Failures in one send never abort the batch — every candidate is
    tried independently and errors are counted, matching the design
    invariant "one bad email must not block the whole cohort".
    """
    counts = {"sent": 0, "skipped": 0, "errors": 0, "samples": []}
    for u in candidates:
        if await _already_sent(u["id"], stage):
            counts["skipped"] += 1
            continue
        if dry_run:
            counts["samples"].append(u["email"])
            continue
        try:
            ok = await send_fn(u)
        except Exception:
            log.exception(f"[drip/{stage}] send failed for {u['email']}")
            ok = False
        await _record_send(u["id"], stage, u["email"], ok)
        counts["sent" if ok else "errors"] += 1
    return counts


def _stage_result(cands: list[dict], counts: dict) -> dict:
    """Shape one stage's output for the API response envelope."""
    return {
        "eligible": len(cands),
        "sent": counts["sent"],
        "skipped_already_sent": counts["skipped"],
        "errors": counts["errors"],
        "dry_run_samples": counts["samples"][:10],
    }


async def run_onboarding_drip(
    dry_run: bool = False,
    share_base: Optional[str] = None,
) -> dict:
    """Drive both drip stages in one pass. Returns per-stage counts.

    Callable manually from the Super Admin (`POST /api/admin/drips/onboarding/run`)
    or from any daily cron. Fully idempotent — a user who already received
    a stage is silently skipped. Refactored (Feb 2026) to compose per-stage
    helpers rather than duplicate the send-with-catch loop inline.
    """
    await _ensure_indexes()
    now_dt = datetime.now(timezone.utc)
    day2_cut = (now_dt - timedelta(hours=DAY_2_MIN_AGE_HOURS)).isoformat()
    day5_cut = (now_dt - timedelta(hours=DAY_5_MIN_AGE_HOURS)).isoformat()
    base = (share_base or "").rstrip("/")

    # Stage 1 — first-course nudge
    nudge_cands = await _candidates_first_course_nudge(day2_cut)

    async def _send_nudge(u):
        return await send_first_course_nudge_email(u["email"], u.get("full_name") or "")

    nudge_counts = await _process_stage(
        stage=STAGE_FIRST_COURSE_NUDGE, candidates=nudge_cands,
        dry_run=dry_run, send_fn=_send_nudge,
    )

    # Stage 2 — referral invite (needs per-user code + share URL)
    invite_cands = await _candidates_referral_invite(day5_cut)

    async def _send_invite(u):
        code = u.get("personal_referral_code") or await ensure_personal_code(u["id"])
        share_url = f"{base}/register?ref={code}" if base else code
        return await send_referral_invite_email(
            u["email"], u.get("full_name") or "", code, share_url,
        )

    invite_counts = await _process_stage(
        stage=STAGE_REFERRAL_INVITE, candidates=invite_cands,
        dry_run=dry_run, send_fn=_send_invite,
    )

    return {
        "dry_run": dry_run,
        "generated_at": now_dt.isoformat(),
        "first_course_nudge": _stage_result(nudge_cands, nudge_counts),
        "referral_invite": _stage_result(invite_cands, invite_counts),
    }
