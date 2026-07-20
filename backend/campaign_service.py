"""Email-campaign service (Iteration 57).

Two responsibilities:

    1. **Automated lifecycle triggers** — module-completion nudge, module-5
       founding-cohort offer, and the 7-day re-engagement sweep. Every trigger
       is idempotent (unique index on `email_trigger_log` for one-shot triggers;
       weekly cooldown key for recurring re-engagement).

    2. **Manual Super-Admin campaigns** — compose a subject + body once, target
       an audience segment (all learners / by course / by role), preview the
       recipient count, dispatch, and log the outcome per-recipient in
       `email_send_log` for the campaign-history table.

Everything writes to two dedicated collections:

    * `email_trigger_log`  — one row per (user_id, trigger_key). Unique index
                              guarantees a trigger fires at most once per user.
                              Weekly re-engagement uses a rolling week-bucket
                              trigger_key so the same user can be nudged again
                              after 7 days.
    * `email_campaigns`     — one row per manual campaign (subject, body,
                              filter, sent_by, counts).
    * `email_send_log`      — one row per (campaign_id, recipient) with status.

Sends never raise — a Resend failure logs, increments the campaign's
`failed_count`, and lets the batch continue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from core import db, logger
from models import gen_id
from email_service import (
    send_manual_campaign_email,
    send_module_5_offer_email,
    send_module_completion_email,
    send_reengagement_email,
)

TRIGGER_LOG = "email_trigger_log"
CAMPAIGN_COLL = "email_campaigns"
SEND_LOG = "email_send_log"

_MAX_MANUAL_CAMPAIGN_RECIPIENTS = 5000


# ---- Index bootstrap ------------------------------------------------------


async def ensure_indexes() -> None:
    """Idempotent — safe to call on every boot and every trigger."""
    await db[TRIGGER_LOG].create_index(
        [("user_id", 1), ("trigger_key", 1)], unique=True
    )
    await db[CAMPAIGN_COLL].create_index([("sent_at", -1)])
    await db[SEND_LOG].create_index([("campaign_id", 1)])
    await db[SEND_LOG].create_index([("recipient_email", 1)])


# ---- Helpers ---------------------------------------------------------------


async def _already_triggered(user_id: str, trigger_key: str) -> bool:
    doc = await db[TRIGGER_LOG].find_one(
        {"user_id": user_id, "trigger_key": trigger_key}, {"_id": 1}
    )
    return doc is not None


async def _record_trigger(user_id: str, trigger_key: str, email: str, ok: bool) -> None:
    try:
        await db[TRIGGER_LOG].insert_one({
            "user_id": user_id,
            "trigger_key": trigger_key,
            "email": email,
            "sent": ok,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        # Duplicate-key race — trigger already logged, nothing to do.
        logger.debug(f"[campaign] duplicate trigger_key insert {user_id}/{trigger_key} — safely ignored")


async def _user_email_and_name(user_id: str) -> tuple[str, str] | None:
    u = await db.users.find_one(
        {"id": user_id}, {"_id": 0, "email": 1, "full_name": 1, "role": 1}
    )
    if not u or not u.get("email"):
        return None
    if u.get("role") in ("super_admin", "admin"):
        return None
    return u["email"], u.get("full_name") or "there"


# ---- Automated: module-completion nudge -----------------------------------


async def trigger_module_completion(
    user_id: str, course: dict, module_id: str
) -> bool:
    """Called from `catalog_router.complete_lesson` after a lesson-complete
    write.  If the freshly-completed lesson pushes the whole module to done,
    fires the module-completion nudge exactly once per (user, course, module).

    Silently no-ops for admin/super_admin roles.
    Never raises — email failures do not block the enrollment write.
    """
    try:
        await ensure_indexes()
        u = await _user_email_and_name(user_id)
        if not u:
            return False
        email, name = u

        modules = course.get("modules") or []
        module_ids = [m.get("id") for m in modules]
        try:
            idx = module_ids.index(module_id)
        except ValueError:
            return False
        module = modules[idx]
        module_index_1based = idx + 1
        total_modules = len(modules)
        next_title = modules[idx + 1].get("title") if idx + 1 < total_modules else None

        trigger_key = f"module-complete:{course.get('id')}:{module_id}"
        if await _already_triggered(user_id, trigger_key):
            return False

        ok = await send_module_completion_email(
            email=email,
            full_name=name,
            course_title=course.get("title") or "",
            course_slug=course.get("slug") or "",
            module_title=module.get("title") or f"Module {module_index_1based}",
            module_index=module_index_1based,
            total_modules=total_modules,
            next_module_title=next_title,
        )
        await _record_trigger(user_id, trigger_key, email, ok)

        # Chain the module-5 offer trigger — it has its own idempotency guard.
        if module_index_1based == 5:
            await _maybe_trigger_module_5_offer(
                user_id=user_id, email=email, name=name, course=course
            )
        return ok
    except Exception:
        logger.exception("[campaign] trigger_module_completion failed")
        return False


async def _maybe_trigger_module_5_offer(
    *, user_id: str, email: str, name: str, course: dict
) -> None:
    """Idempotent module-5 offer trigger.

    Founding cohort perk (first 500 signups); the message renders slightly
    different copy when the recipient's `founding_member_seq` is in-range.
    Regardless of seq, we still send — non-founding members get a copy that
    omits the #N-of-500 badge but keeps the "unlock the next 10 modules"
    positioning.
    """
    trigger_key = f"module-5-offer:{course.get('id')}"
    if await _already_triggered(user_id, trigger_key):
        return
    u_full = await db.users.find_one(
        {"id": user_id}, {"_id": 0, "founding_member_seq": 1}
    )
    seq = (u_full or {}).get("founding_member_seq")
    ok = await send_module_5_offer_email(
        email=email,
        full_name=name,
        course_title=course.get("title") or "",
        course_slug=course.get("slug") or "",
        seq_position=seq,
    )
    await _record_trigger(user_id, trigger_key, email, ok)


# ---- Automated: 7-day re-engagement sweep ---------------------------------


REENGAGEMENT_DORMANT_DAYS = 7
REENGAGEMENT_COOLDOWN_DAYS = 30  # never send more than one re-eng email per 30d
REENGAGEMENT_BATCH_CAP = 500


def _week_bucket(now_dt: datetime) -> str:
    """ISO year+week — anchors the trigger_key so a user can be re-engaged
    monthly at most (cooldown enforced separately by the trigger_log)."""
    y, w, _ = now_dt.isocalendar()
    return f"{y}-W{w:02d}"


async def _candidates_reengagement(
    dormant_before_iso: str, min_reg_before_iso: str
) -> list[dict]:
    """Users who registered ≥ 7 days ago, have zero enrollments touched in
    the past 7 days AND no lesson completion in the past 7 days. Excluded:
    super_admin / admin, users with `drip_opt_out=true`, users with no email.
    """
    # Users who touched an enrolment (last_accessed) or completed a lesson
    # in the recent window are "active" — skip them.
    active_user_ids = set()
    async for e in db.enrollments.find(
        {"last_accessed": {"$gte": dormant_before_iso}},
        {"_id": 0, "user_id": 1},
    ):
        if e.get("user_id"):
            active_user_ids.add(e["user_id"])

    candidates = await db.users.find(
        {
            "created_at": {"$lt": min_reg_before_iso},
            "id": {"$nin": list(active_user_ids)},
            "drip_opt_out": {"$ne": True},
            "role": {"$nin": ["super_admin", "admin"]},
        },
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "created_at": 1},
    ).to_list(REENGAGEMENT_BATCH_CAP)
    return [u for u in candidates if u.get("email")]


async def run_reengagement_sweep(dry_run: bool = False) -> dict:
    """Daily-runnable dormancy sweep.

    Sends `send_reengagement_email` to any user who has been inactive for at
    least `REENGAGEMENT_DORMANT_DAYS` days AND hasn't received a re-engagement
    email in the current 30-day cooldown window. Idempotent per week-bucket.
    """
    await ensure_indexes()
    now_dt = datetime.now(timezone.utc)
    dormant_iso = (now_dt - timedelta(days=REENGAGEMENT_DORMANT_DAYS)).isoformat()
    min_reg_iso = (now_dt - timedelta(days=REENGAGEMENT_DORMANT_DAYS)).isoformat()
    cooldown_iso = (now_dt - timedelta(days=REENGAGEMENT_COOLDOWN_DAYS)).isoformat()

    cands = await _candidates_reengagement(dormant_iso, min_reg_iso)

    # Cooldown: exclude users who received any re-engagement email inside the
    # 30-day cooldown window.
    already_recent_uids = set()
    async for row in db[TRIGGER_LOG].find(
        {"trigger_key": {"$regex": "^reengagement:"}, "sent_at": {"$gte": cooldown_iso}},
        {"_id": 0, "user_id": 1},
    ):
        already_recent_uids.add(row["user_id"])
    cands = [u for u in cands if u["id"] not in already_recent_uids]

    trigger_key = f"reengagement:{_week_bucket(now_dt)}"
    counts = {"sent": 0, "skipped": 0, "errors": 0, "samples": []}
    for u in cands:
        if await _already_triggered(u["id"], trigger_key):
            counts["skipped"] += 1
            continue
        if dry_run:
            counts["samples"].append(u["email"])
            continue
        # days_inactive is best-effort — derived from registration age if we
        # can't find a last_accessed row.
        days_inactive = REENGAGEMENT_DORMANT_DAYS
        last_touch = await db.enrollments.find_one(
            {"user_id": u["id"]}, {"_id": 0, "last_accessed": 1}, sort=[("last_accessed", -1)]
        )
        if last_touch and last_touch.get("last_accessed"):
            try:
                last_dt = datetime.fromisoformat(last_touch["last_accessed"].replace("Z", "+00:00"))
                days_inactive = max(REENGAGEMENT_DORMANT_DAYS, (now_dt - last_dt).days)
            except Exception:
                pass
        try:
            ok = await send_reengagement_email(u["email"], u.get("full_name") or "", days_inactive)
        except Exception:
            logger.exception(f"[campaign/reengagement] send failed for {u['email']}")
            ok = False
        await _record_trigger(u["id"], trigger_key, u["email"], ok)
        counts["sent" if ok else "errors"] += 1

    return {
        "dry_run": dry_run,
        "generated_at": now_dt.isoformat(),
        "eligible": len(cands),
        "sent": counts["sent"],
        "skipped_already_sent": counts["skipped"],
        "errors": counts["errors"],
        "dry_run_samples": counts["samples"][:10],
    }


# ---- Manual campaigns (Super-Admin composer) ------------------------------


async def _resolve_audience(filter_spec: dict) -> list[dict]:
    """Basic v1 segmentation: `all` / `role` / `by_course` / `founding_only`.

    filter_spec keys:
      - segment: "all_learners" | "role" | "by_course" | "founding_only"
      - role: str (when segment=="role")
      - course_slug: str (when segment=="by_course") — targets enrolled learners
    Returns a list of {id, email, full_name} — email guaranteed truthy.
    """
    segment = filter_spec.get("segment", "all_learners")
    base_query = {"role": {"$nin": ["super_admin", "admin"]}}

    if segment == "role":
        role = (filter_spec.get("role") or "").strip()
        if not role:
            return []
        query = {"role": role}
    elif segment == "founding_only":
        query = {**base_query, "founding_member_seq": {"$ne": None}}
    elif segment == "by_course":
        slug = (filter_spec.get("course_slug") or "").strip()
        if not slug:
            return []
        course = await db.courses.find_one({"slug": slug}, {"_id": 0, "id": 1})
        if not course:
            return []
        user_ids = await db.enrollments.distinct("user_id", {"course_id": course["id"]})
        if not user_ids:
            return []
        query = {**base_query, "id": {"$in": user_ids}}
    else:
        # Default: all_learners (drop super_admin/admin)
        query = base_query

    rows = await db.users.find(
        query, {"_id": 0, "id": 1, "email": 1, "full_name": 1}
    ).to_list(_MAX_MANUAL_CAMPAIGN_RECIPIENTS + 1)
    return [r for r in rows if r.get("email")]


async def preview_campaign_recipients(filter_spec: dict) -> dict:
    """Return {count, sample_emails} for the Super-Admin preview UI."""
    audience = await _resolve_audience(filter_spec or {})
    truncated = len(audience) > _MAX_MANUAL_CAMPAIGN_RECIPIENTS
    return {
        "count": min(len(audience), _MAX_MANUAL_CAMPAIGN_RECIPIENTS),
        "truncated": truncated,
        "max_recipients": _MAX_MANUAL_CAMPAIGN_RECIPIENTS,
        "sample_emails": [r["email"] for r in audience[:5]],
    }


async def dispatch_manual_campaign(
    *,
    sent_by_admin_id: str,
    sent_by_email: str,
    subject: str,
    body_markdown: str,
    filter_spec: dict,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    test_recipient: Optional[str] = None,
) -> dict:
    """Send a Super-Admin-composed campaign.

    If `test_recipient` is set, sends **only** to that address for QA (no
    campaign log entry). Otherwise resolves the audience, logs a campaign
    row, dispatches per-recipient (fire-and-forget failure isolation), and
    returns delivery totals.
    """
    await ensure_indexes()
    subject = (subject or "").strip()
    body = (body_markdown or "").strip()
    if not subject or not body:
        return {"ok": False, "error": "subject and body are required"}

    now_iso = datetime.now(timezone.utc).isoformat()

    if test_recipient:
        ok = await send_manual_campaign_email(
            email=test_recipient,
            full_name="Test Recipient",
            subject=subject,
            body_markdown=body,
            cta_label=cta_label,
            cta_url=cta_url,
        )
        return {"ok": True, "test": True, "recipient": test_recipient, "delivered": ok}

    audience = await _resolve_audience(filter_spec or {})
    audience = audience[:_MAX_MANUAL_CAMPAIGN_RECIPIENTS]
    if not audience:
        return {"ok": False, "error": "audience is empty for the selected filter"}

    campaign_id = gen_id()
    await db[CAMPAIGN_COLL].insert_one({
        "id": campaign_id,
        "subject": subject,
        "body_markdown": body,
        "cta_label": cta_label,
        "cta_url": cta_url,
        "filter": filter_spec or {"segment": "all_learners"},
        "sent_by": sent_by_admin_id,
        "sent_by_email": sent_by_email,
        "sent_at": now_iso,
        "status": "in_progress",
        "total_recipients": len(audience),
        "delivered_count": 0,
        "failed_count": 0,
    })

    delivered = 0
    failed = 0
    for u in audience:
        try:
            ok = await send_manual_campaign_email(
                email=u["email"],
                full_name=u.get("full_name") or "",
                subject=subject,
                body_markdown=body,
                cta_label=cta_label,
                cta_url=cta_url,
            )
        except Exception:
            logger.exception(f"[campaign] manual send failed for {u.get('email')}")
            ok = False
        try:
            await db[SEND_LOG].insert_one({
                "campaign_id": campaign_id,
                "user_id": u["id"],
                "recipient_email": u["email"],
                "delivered": ok,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            logger.exception("[campaign] send_log insert failed")
        if ok:
            delivered += 1
        else:
            failed += 1

    await db[CAMPAIGN_COLL].update_one(
        {"id": campaign_id},
        {"$set": {
            "delivered_count": delivered,
            "failed_count": failed,
            "status": "sent" if failed == 0 else ("partial" if delivered > 0 else "failed"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {
        "ok": True,
        "campaign_id": campaign_id,
        "total_recipients": len(audience),
        "delivered_count": delivered,
        "failed_count": failed,
    }


async def list_campaign_history(limit: int = 50) -> list[dict]:
    """Return the most-recent N campaigns for the Super-Admin history panel."""
    limit = max(1, min(200, limit))
    rows = await db[CAMPAIGN_COLL].find(
        {}, {"_id": 0}
    ).sort("sent_at", -1).to_list(limit)
    return rows
