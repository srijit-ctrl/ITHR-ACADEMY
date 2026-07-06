"""Weekly digest jobs — currently: credential-impressions digest for learners.

Designed to be safe to re-run (idempotency window per user), so the
super-admin can trigger it manually via `POST /api/admin/digests/impressions/run`
or a future cron / scheduled job can hit the same endpoint.

Every eligible learner is sent at most ONE digest per rolling 6-day window
(guards against accidental double-runs on the same day and also permits a
few days of drift on a weekly cadence).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from core import db
from email_service import send_impressions_digest_email

log = logging.getLogger("digest_jobs")

DIGEST_KIND_IMPRESSIONS = "impressions"
IDEMPOTENCY_WINDOW_DAYS = 6


async def _learners_with_recent_impressions(since_iso: str) -> list[dict]:
    """Group verify_impressions in the window by user_id; return user docs enriched with counts."""
    pipeline = [
        {"$match": {"verified_at": {"$gte": since_iso}}},
        {"$group": {
            "_id": "$user_id",
            "week_impressions": {"$sum": 1},
        }},
    ]
    groups = await db.verify_impressions.aggregate(pipeline).to_list(1000)
    if not groups:
        return []
    user_ids = [g["_id"] for g in groups]
    user_docs = await db.users.find(
        {"id": {"$in": user_ids}},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "digest_impressions_enabled": 1},
    ).to_list(1000)
    users_by_id = {u["id"]: u for u in user_docs}
    return [
        {"user": users_by_id[g["_id"]], "week_impressions": g["week_impressions"]}
        for g in groups
        if g["_id"] in users_by_id and users_by_id[g["_id"]].get("digest_impressions_enabled") is not False
    ]


async def _top_credentials_for_user(user_id: str, since_iso: str, limit: int = 5) -> list[dict]:
    pipeline = [
        {"$match": {"user_id": user_id, "verified_at": {"$gte": since_iso}}},
        {"$group": {"_id": "$certificate_id", "impressions": {"$sum": 1}}},
        {"$sort": {"impressions": -1}},
        {"$limit": limit},
    ]
    raw = await db.verify_impressions.aggregate(pipeline).to_list(limit)
    if not raw:
        return []
    cert_ids = [r["_id"] for r in raw]
    cert_docs = await db.certificates.find(
        {"certificate_id": {"$in": cert_ids}},
        {"_id": 0, "certificate_id": 1, "course_title": 1},
    ).to_list(limit)
    title_by_id = {c["certificate_id"]: c.get("course_title", "") for c in cert_docs}
    return [
        {"certificate_id": r["_id"], "course_title": title_by_id.get(r["_id"], "(unknown)"), "impressions": r["impressions"]}
        for r in raw
    ]


async def _already_sent_recently(user_id: str, cutoff_iso: str) -> bool:
    doc = await db.digest_send_log.find_one({
        "user_id": user_id, "kind": DIGEST_KIND_IMPRESSIONS, "sent_at": {"$gte": cutoff_iso},
    })
    return doc is not None


async def _record_send(user_id: str, week_impressions: int, sent: bool) -> None:
    await db.digest_send_log.insert_one({
        "user_id": user_id,
        "kind": DIGEST_KIND_IMPRESSIONS,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "week_impressions": week_impressions,
        "sent": sent,
    })


async def run_impressions_digest(dry_run: bool = False, window_days: int = 7) -> dict:
    """Send a credential-impressions digest to every learner with ≥1 impression
    in the last `window_days`. Skips users who received the same digest within
    the last IDEMPOTENCY_WINDOW_DAYS."""
    now_dt = datetime.now(timezone.utc)
    since_iso = (now_dt - timedelta(days=window_days)).isoformat()
    idempotency_cutoff = (now_dt - timedelta(days=IDEMPOTENCY_WINDOW_DAYS)).isoformat()

    eligible = await _learners_with_recent_impressions(since_iso)
    log.info(f"[digest/impressions] {len(eligible)} eligible learners in last {window_days}d")

    sent_count = 0
    skipped_recent = 0
    skipped_disabled = 0  # already filtered in _learners_with_recent_impressions but counted for clarity
    errors = 0

    for row in eligible:
        u = row["user"]
        wk = row["week_impressions"]
        if await _already_sent_recently(u["id"], idempotency_cutoff):
            skipped_recent += 1
            continue
        top = await _top_credentials_for_user(u["id"], since_iso)
        if dry_run:
            log.info(f"  DRY {u['email']} wk={wk} top={[c['course_title'] for c in top]}")
            continue
        ok = await send_impressions_digest_email(
            email=u["email"], full_name=u.get("full_name") or "",
            week_impressions=wk, top_credentials=top,
        )
        await _record_send(u["id"], wk, ok)
        if ok:
            sent_count += 1
        else:
            errors += 1

    return {
        "kind": DIGEST_KIND_IMPRESSIONS,
        "window_days": window_days,
        "eligible": len(eligible),
        "sent": sent_count,
        "skipped_recent": skipped_recent,
        "skipped_disabled": skipped_disabled,
        "errors": errors,
        "dry_run": dry_run,
    }
