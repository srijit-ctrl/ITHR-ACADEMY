"""Executive Command Centre: consolidated KPIs, alert centre, Org/User 360 drill-downs."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_super_admin
from core import db, now_iso, logger

router = APIRouter(prefix="/api/admin", tags=["command-center"])


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _pct(cur: float, prev: float):
    if prev == 0:
        return None if cur == 0 else 100.0
    return round((cur - prev) / prev * 100, 1)


async def _period_counts(start: str, end: str) -> dict:
    """All KPI counts for one time window (ISO string comparisons work on ISO dates)."""
    in_window = lambda field: {field: {"$gte": start, "$lt": end}}  # noqa: E731
    new_users = await db.users.count_documents(in_window("created_at"))
    active_users = len(await db.user_login_logs.distinct("user_id", in_window("created_at")))
    new_enrollments = await db.enrollments.count_documents(in_window("enrolled_at"))
    completions = await db.enrollments.count_documents({"completed": True, **in_window("completed_at")})
    attempts = await db.quiz_attempts.count_documents(in_window("attempted_at"))
    passes = await db.quiz_attempts.count_documents({"passed": True, **in_window("attempted_at")})
    certs = await db.certificates.count_documents(in_window("issued_at"))
    verifications = await db.verify_impressions.count_documents(in_window("verified_at"))
    ai_sessions = await db.chat_sessions.count_documents(in_window("created_at"))
    ai_users = len(await db.chat_sessions.distinct("user_id", in_window("updated_at")))
    referral_signups = await db.referral_signups.count_documents(in_window("created_at"))
    rev_agg = await db.payment_transactions.aggregate([
        {"$match": {"payment_status": "paid", **in_window("created_at")}},
        {"$group": {"_id": None, "total": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}}}},
    ]).to_list(1)
    revenue = round((rev_agg[0]["total"] if rev_agg else 0) or 0, 2)
    return {
        "new_users": new_users, "active_users": active_users,
        "new_enrollments": new_enrollments, "completions": completions,
        "assessment_attempts": attempts, "assessment_passes": passes,
        "certificates_issued": certs, "credential_verifications": verifications,
        "ai_sessions": ai_sessions, "ai_active_users": ai_users,
        "referral_signups": referral_signups, "revenue": revenue,
    }


@router.get("/command-center")
async def command_center(days: int = 30, _sa: str = Depends(get_current_super_admin)):
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    cur_start, prev_start = _iso(now - timedelta(days=days)), _iso(now - timedelta(days=days * 2))
    now_s = _iso(now)

    cur = await _period_counts(cur_start, now_s)
    prev = await _period_counts(prev_start, cur_start)

    # All-time / point-in-time stats
    total_users = await db.users.count_documents({})
    suspended_users = await db.users.count_documents({"is_suspended": True})
    mfa_users = await db.users.count_documents({"mfa_enabled": True})
    total_orgs = await db.organizations.count_documents({})
    seats = await db.organizations.aggregate([
        {"$group": {"_id": None,
                    "purchased": {"$sum": {"$ifNull": ["$seat_count", 0]}},
                    "used": {"$sum": {"$ifNull": ["$seats_used", 0]}}}},
    ]).to_list(1)
    seat_row = seats[0] if seats else {"purchased": 0, "used": 0}
    total_enrollments = await db.enrollments.count_documents({})
    total_completions = await db.enrollments.count_documents({"completed": True})
    total_certs = await db.certificates.count_documents({})
    dau = len(await db.user_login_logs.distinct("user_id", {"created_at": {"$gte": _iso(now - timedelta(days=1))}}))
    mau = len(await db.user_login_logs.distinct("user_id", {"created_at": {"$gte": _iso(now - timedelta(days=30))}}))

    kpis = []

    def add(key, label, value, prev_value=None, fmt="int", drill=None, definition=""):
        item = {"key": key, "label": label, "value": value, "format": fmt, "drill": drill, "definition": definition}
        if prev_value is not None:
            item["prev_value"] = prev_value
            item["delta_pct"] = _pct(value, prev_value)
        kpis.append(item)

    add("total_users", "Total registered users", total_users, drill="users", definition="All accounts ever created")
    add("new_users", "New registrations", cur["new_users"], prev["new_users"], drill="users", definition=f"Accounts created in last {days}d vs prior {days}d")
    add("dau", "Daily active users", dau, drill="traffic", definition="Distinct users with a login in the last 24h")
    add("mau", "Monthly active users", mau, drill="traffic", definition="Distinct users with a login in the last 30d")
    add("active_users", "Active users (period)", cur["active_users"], prev["active_users"], drill="traffic", definition="Distinct users logging in during the period")
    add("total_orgs", "Enterprise organizations", total_orgs, drill="orgs", definition="Provisioned tenant organizations")
    add("seats_purchased", "Seats purchased", seat_row["purchased"], drill="orgs", definition="Sum of seat_count across orgs")
    add("seats_used", "Seats activated", seat_row["used"], drill="orgs", definition="Sum of seats_used across orgs")
    add("new_enrollments", "New enrollments", cur["new_enrollments"], prev["new_enrollments"], drill="analytics", definition="Course enrollments created in the period")
    add("completions", "Course completions", cur["completions"], prev["completions"], drill="analytics", definition="Enrollments marked complete in the period")
    add("completion_rate", "Overall completion rate",
        round(total_completions / total_enrollments * 100, 1) if total_enrollments else 0.0,
        fmt="pct", drill="analytics", definition="All-time completed / total enrollments")
    add("assessment_attempts", "Assessment attempts", cur["assessment_attempts"], prev["assessment_attempts"], drill="analytics", definition="Quiz/assessment attempts in the period")
    add("pass_rate", "Assessment pass rate",
        round(cur["assessment_passes"] / cur["assessment_attempts"] * 100, 1) if cur["assessment_attempts"] else 0.0,
        fmt="pct", drill="analytics", definition="Passed / attempted in the period")
    add("certificates_issued", "Credentials issued", cur["certificates_issued"], prev["certificates_issued"], drill="analytics", definition="Certificates issued in the period")
    add("total_certs", "Credentials (all-time)", total_certs, drill="analytics", definition="All certificates ever issued")
    add("verifications", "Credential verifications", cur["credential_verifications"], prev["credential_verifications"], drill="analytics", definition="Public verify-page impressions in the period")
    add("ai_sessions", "AI tutor conversations", cur["ai_sessions"], prev["ai_sessions"], drill="sessions", definition="New Aletheia chat sessions in the period")
    add("ai_active_users", "AI tutor active users", cur["ai_active_users"], prev["ai_active_users"], drill="sessions", definition="Distinct users with tutor activity in the period")
    add("revenue", "Revenue (period)", cur["revenue"], prev["revenue"], fmt="usd", drill="analytics", definition="Sum of paid Stripe transactions in the period")
    add("referral_signups", "Referral signups", cur["referral_signups"], prev["referral_signups"], drill="users", definition="Signups via personal referral codes in the period")
    add("suspended_users", "Suspended accounts", suspended_users, drill="users", definition="Accounts currently suspended")
    add("mfa_users", "MFA-enabled accounts", mfa_users, drill="security", definition="Accounts with TOTP MFA active")

    return {"days": days, "generated_at": now_iso(), "kpis": kpis}


# ---- Alert & Action Centre ----------------------------------------------------


async def _compute_alerts() -> list:
    """Live signal scan. Each alert has a stable key so ack/resolve state persists."""
    now = datetime.now(timezone.utc)
    alerts = []

    def add(key, severity, title, detail, drill=None):
        alerts.append({"key": key, "severity": severity, "title": title, "detail": detail, "drill": drill})

    week_ago = _iso(now - timedelta(days=7))
    prev_week = _iso(now - timedelta(days=14))
    cur_logins = await db.user_login_logs.count_documents({"created_at": {"$gte": week_ago}})
    prev_logins = await db.user_login_logs.count_documents({"created_at": {"$gte": prev_week, "$lt": week_ago}})
    if prev_logins >= 10 and cur_logins < prev_logins * 0.5:
        add("active-users-decline", "high", "Sharp decline in active users",
            f"Logins this week ({cur_logins}) are down {round((1 - cur_logins / prev_logins) * 100)}% vs last week ({prev_logins}).", "traffic")

    async for org in db.organizations.find({}, {"_id": 0, "id": 1, "name": 1, "seat_count": 1, "seats_used": 1}):
        seat_count, used = org.get("seat_count") or 0, org.get("seats_used") or 0
        if seat_count >= 10 and used / seat_count < 0.3:
            add(f"unused-seats-{org['id']}", "medium", f"Low seat utilization: {org['name']}",
                f"Only {used}/{seat_count} purchased seats activated ({round(used / seat_count * 100)}%).", "orgs")

    stale = _iso(now - timedelta(days=30))
    dormant = await db.enrollments.count_documents({"completed": {"$ne": True}, "last_accessed": {"$lt": stale}})
    if dormant > 0:
        add("dormant-learners", "medium", "Learners falling behind",
            f"{dormant} active enrollment(s) with no activity in 30+ days.", "users")

    month_ago = _iso(now - timedelta(days=30))
    attempts = await db.quiz_attempts.count_documents({"attempted_at": {"$gte": month_ago}})
    passes = await db.quiz_attempts.count_documents({"passed": True, "attempted_at": {"$gte": month_ago}})
    if attempts >= 20 and passes / attempts < 0.4:
        add("low-pass-rate", "high", "Unusual assessment failure rate",
            f"30-day pass rate is {round(passes / attempts * 100)}% across {attempts} attempts.", "analytics")

    failed_pay = await db.payment_transactions.count_documents({"payment_status": {"$in": ["failed", "unpaid"]}, "created_at": {"$gte": month_ago}})
    if failed_pay > 0:
        add("failed-payments", "high", "Failed payments detected",
            f"{failed_pay} failed/unpaid transaction(s) in the last 30 days.", "analytics")

    resets = await db.password_reset_tokens.count_documents({"created_at": {"$gte": _iso(now - timedelta(days=1))}})
    if resets >= 10:
        add("reset-spike", "high", "Password-reset spike", f"{resets} reset requests in 24h — possible credential-stuffing attempt.", "security")

    bypass_used = await db.course_entitlements.count_documents({"source": "first-course-bypass"})
    if bypass_used >= 450:
        add("bypass-cap", "medium", "First-500 bypass cap nearly exhausted", f"{bypass_used}/500 bypass codes issued.", "analytics")

    return alerts


@router.get("/alerts-center")
async def alerts_center(_sa: str = Depends(get_current_super_admin)):
    live = await _compute_alerts()
    states = {s["key"]: s async for s in db.admin_alert_states.find({}, {"_id": 0})}
    out = []
    for a in live:
        st = states.get(a["key"], {})
        if st.get("status") == "resolved" and st.get("resolved_at", "") > _iso(datetime.now(timezone.utc) - timedelta(days=7)):
            continue  # resolved within the last week — suppress
        out.append({**a, "status": st.get("status", "open"), "acked_by": st.get("acked_by"), "note": st.get("note")})
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda x: order.get(x["severity"], 3))

    # Automation-builder trigger: alert_high_severity.
    # Insert-first dedupe: rely on a unique index on `key` so two overlapping
    # polls can't both dispatch. Duplicate-key means someone else already
    # fired for this open-cycle and we skip. The marker is cleared in
    # /resolve so a future re-open fires again.
    try:
        from pymongo.errors import DuplicateKeyError
        from routers.admin_automations_router import run_automations_for_trigger
        import asyncio as _asyncio
        for a in out:
            if a.get("severity") != "high" or a.get("status") == "resolved":
                continue
            try:
                await db.admin_alert_automation_fired.insert_one({
                    "key": a["key"], "fired_at": now_iso(),
                    "severity": a["severity"], "title": a.get("title"),
                })
            except DuplicateKeyError:
                continue  # another worker already dispatched — skip
            _asyncio.create_task(run_automations_for_trigger("alert_high_severity", {
                "key": a["key"], "title": a.get("title"), "detail": a.get("detail"),
                "category": a.get("category"), "severity": a.get("severity"),
            }))
    except Exception:
        logger.exception("[alerts-center] automation dispatch failed")

    return {"alerts": out, "generated_at": now_iso()}


@router.post("/alerts-center/{key}/ack")
async def ack_alert(key: str, sa: str = Depends(get_current_super_admin)):
    await db.admin_alert_states.update_one(
        {"key": key}, {"$set": {"key": key, "status": "acknowledged", "acked_by": sa, "acked_at": now_iso()}}, upsert=True)
    return {"ok": True}


@router.post("/alerts-center/{key}/resolve")
async def resolve_alert(key: str, payload: dict = None, sa: str = Depends(get_current_super_admin)):
    await db.admin_alert_states.update_one(
        {"key": key},
        {"$set": {"key": key, "status": "resolved", "acked_by": sa, "resolved_at": now_iso(),
                  "note": (payload or {}).get("note", "")}}, upsert=True)
    # Clear the automation dedupe marker so a future re-open fires again.
    await db.admin_alert_automation_fired.delete_one({"key": key})
    return {"ok": True}


# ---- Organization 360 -----------------------------------------------------------


@router.get("/org360/{org_id}")
async def org_360(org_id: str, _sa: str = Depends(get_current_super_admin)):
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    members = await db.org_members.find({"org_id": org_id}, {"_id": 0}).to_list(500)
    user_ids = [m["user_id"] for m in members]
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "email": 1, "full_name": 1, "role": 1, "created_at": 1, "last_login_at": 1})}
    enroll = await db.enrollments.aggregate([
        {"$match": {"user_id": {"$in": user_ids}}},
        {"$group": {"_id": None, "total": {"$sum": 1}, "completed": {"$sum": {"$cond": ["$completed", 1, 0]}},
                    "avg_progress": {"$avg": {"$ifNull": ["$progress_pct", 0]}}}},
    ]).to_list(1)
    e = enroll[0] if enroll else {"total": 0, "completed": 0, "avg_progress": 0}
    certs = await db.certificates.count_documents({"user_id": {"$in": user_ids}})
    ai = await db.chat_sessions.count_documents({"user_id": {"$in": user_ids}})
    return {
        "organization": org,
        "members": [{**m, "user": users.get(m["user_id"], {})} for m in members[:100]],
        "member_count": len(members),
        "stats": {
            "enrollments": e["total"], "completions": e["completed"],
            "avg_progress": round(e.get("avg_progress") or 0, 1),
            "certificates": certs, "ai_sessions": ai,
        },
    }


# ---- User / Learner 360 ---------------------------------------------------------


@router.get("/user360/{user_id}")
async def user_360(user_id: str, _sa: str = Depends(get_current_super_admin)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "mfa_secret": 0, "mfa_backup_codes": 0})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    enrollments = await db.enrollments.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    course_ids = [e["course_id"] for e in enrollments]
    courses = {c["id"]: c["title"] async for c in db.courses.find({"id": {"$in": course_ids}}, {"_id": 0, "id": 1, "title": 1})}
    for e in enrollments:
        e["course_title"] = courses.get(e["course_id"], "—")
    certs = await db.certificates.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    attempts = await db.quiz_attempts.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(25)
    ai_count = await db.chat_sessions.count_documents({"user_id": user_id})
    logins = await db.user_login_logs.find({"user_id": user_id}, {"_id": 0, "ip": 0}).sort("created_at", -1).to_list(10)
    referrals = await db.referral_signups.count_documents({"referrer_id": user_id})
    audit = await db.admin_audit_log.find(
        {"$or": [{"target_id": user_id}, {"actor_id": user_id}]}, {"_id": 0}
    ).sort("created_at", -1).to_list(15)
    return {
        "user": u,
        "enrollments": enrollments,
        "certificates": certs,
        "assessment_attempts": attempts,
        "ai_sessions": ai_count,
        "recent_logins": logins,
        "referrals_made": referrals,
        "audit_trail": audit,
    }


# ---- Phase 2: Learning funnel ----------------------------------------------------


@router.get("/learning-funnel")
async def learning_funnel(_sa: str = Depends(get_current_super_admin)):
    """Global + per-course funnel: Enrolled → Started → Engaged → Assessed → Passed → Completed → Credentialed."""
    enrolled = await db.enrollments.count_documents({})
    started = await db.enrollments.count_documents({"progress_pct": {"$gt": 0}})
    engaged = await db.enrollments.count_documents({"progress_pct": {"$gte": 25}})
    assessed_users = await db.quiz_attempts.distinct("user_id")
    assessed = await db.enrollments.count_documents({"user_id": {"$in": assessed_users}}) if assessed_users else 0
    passed_pairs = await db.quiz_attempts.aggregate([
        {"$match": {"passed": True}},
        {"$group": {"_id": {"u": "$user_id", "c": "$course_id"}}},
    ]).to_list(10000)
    passed = len(passed_pairs)
    completed = await db.enrollments.count_documents({"completed": True})
    credentialed = await db.certificates.count_documents({})
    stages = [
        {"stage": "Enrolled", "count": enrolled}, {"stage": "Started", "count": started},
        {"stage": "Engaged (≥25%)", "count": engaged}, {"stage": "Assessed", "count": assessed},
        {"stage": "Passed", "count": passed}, {"stage": "Completed", "count": completed},
        {"stage": "Credentialed", "count": credentialed},
    ]
    # Per-course drop-off table
    per_course = await db.enrollments.aggregate([
        {"$group": {"_id": "$course_id", "enrolled": {"$sum": 1},
                    "started": {"$sum": {"$cond": [{"$gt": [{"$ifNull": ["$progress_pct", 0]}, 0]}, 1, 0]}},
                    "completed": {"$sum": {"$cond": ["$completed", 1, 0]}},
                    "avg_progress": {"$avg": {"$ifNull": ["$progress_pct", 0]}}}},
        {"$sort": {"enrolled": -1}}, {"$limit": 40},
    ]).to_list(40)
    course_ids = [c["_id"] for c in per_course]
    titles = {c["id"]: c["title"] async for c in db.courses.find({"id": {"$in": course_ids}}, {"_id": 0, "id": 1, "title": 1})}
    certs_by_course = {c["_id"]: c["n"] for c in await db.certificates.aggregate(
        [{"$group": {"_id": "$course_id", "n": {"$sum": 1}}}]).to_list(200)}
    courses = [{
        "course_id": c["_id"], "title": titles.get(c["_id"], c["_id"]),
        "enrolled": c["enrolled"], "started": c["started"], "completed": c["completed"],
        "credentialed": certs_by_course.get(c["_id"], 0),
        "avg_progress": round(c.get("avg_progress") or 0, 1),
        "dropoff_pct": round((1 - (c["completed"] / c["enrolled"])) * 100, 1) if c["enrolled"] else 0,
    } for c in per_course]
    return {"stages": stages, "courses": courses, "generated_at": now_iso()}


# ---- Phase 2: Assessment quality analytics ----------------------------------------


@router.get("/assessment-analytics")
async def assessment_analytics(_sa: str = Depends(get_current_super_admin)):
    attempts = await db.quiz_attempts.find({}, {"_id": 0, "answers": 0}).sort("attempted_at", -1).to_list(5000)
    total = len(attempts)
    if total == 0:
        return {"total": 0, "summary": None, "per_course": [], "recent": [], "generated_at": now_iso()}
    passes = [a for a in attempts if a.get("passed")]
    scores = sorted(a.get("score", 0) for a in attempts)
    median = scores[len(scores) // 2]
    # first-attempt pass rate + avg attempts to pass, per (user, course)
    by_pair = {}
    for a in reversed(attempts):  # chronological
        by_pair.setdefault((a["user_id"], a["course_id"]), []).append(a)
    first_pass = sum(1 for arr in by_pair.values() if arr[0].get("passed"))
    attempts_to_pass = [next((i + 1 for i, a in enumerate(arr) if a.get("passed")), None) for arr in by_pair.values()]
    attempts_to_pass = [n for n in attempts_to_pass if n]
    per_course_map = {}
    for a in attempts:
        m = per_course_map.setdefault(a["course_id"], {"attempts": 0, "passes": 0, "score_sum": 0.0, "dur_sum": 0})
        m["attempts"] += 1
        m["passes"] += 1 if a.get("passed") else 0
        m["score_sum"] += a.get("score", 0)
        m["dur_sum"] += a.get("duration_seconds", 0)
    titles = {c["id"]: c["title"] async for c in db.courses.find(
        {"id": {"$in": list(per_course_map)}}, {"_id": 0, "id": 1, "title": 1})}
    per_course = sorted([{
        "course_id": cid, "title": titles.get(cid, cid), "attempts": m["attempts"],
        "pass_rate": round(m["passes"] / m["attempts"] * 100, 1),
        "avg_score": round(m["score_sum"] / m["attempts"], 1),
        "avg_duration_min": round(m["dur_sum"] / m["attempts"] / 60, 1),
    } for cid, m in per_course_map.items()], key=lambda x: -x["attempts"])
    users = {u["id"]: u["full_name"] async for u in db.users.find(
        {"id": {"$in": list({a["user_id"] for a in attempts[:25]})}}, {"_id": 0, "id": 1, "full_name": 1})}
    recent = [{**a, "user_name": users.get(a["user_id"], "—"), "course_title": titles.get(a["course_id"], a["course_id"])}
              for a in attempts[:25]]
    return {
        "total": total,
        "summary": {
            "attempts": total, "passes": len(passes),
            "pass_rate": round(len(passes) / total * 100, 1),
            "avg_score": round(sum(scores) / total, 1), "median_score": round(median, 1),
            "highest": round(scores[-1], 1), "lowest": round(scores[0], 1),
            "first_attempt_pass_rate": round(first_pass / len(by_pair) * 100, 1),
            "avg_attempts_to_pass": round(sum(attempts_to_pass) / len(attempts_to_pass), 2) if attempts_to_pass else None,
        },
        "per_course": per_course, "recent": recent, "generated_at": now_iso(),
    }


# ---- Phase 2: Credential management -------------------------------------------------


@router.get("/credentials")
async def list_credentials(q: str = "", _sa: str = Depends(get_current_super_admin)):
    match = {}
    if q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        match = {"$or": [{"user_name": rx}, {"course_title": rx}, {"certificate_id": rx}]}
    certs = await db.certificates.find(match, {"_id": 0}).sort("issued_at", -1).to_list(200)
    ver_counts = {v["_id"]: v["n"] for v in await db.verify_impressions.aggregate(
        [{"$group": {"_id": "$certificate_id", "n": {"$sum": 1}}}]).to_list(2000)}
    for c in certs:
        c["verifications"] = ver_counts.get(c.get("certificate_id"), 0)
    total = await db.certificates.count_documents({})
    revoked = await db.certificates.count_documents({"revoked": True})
    return {"credentials": certs, "total": total, "revoked": revoked, "generated_at": now_iso()}


@router.post("/credentials/{certificate_id}/revoke")
async def revoke_credential(certificate_id: str, payload: dict, request: Request, sa: str = Depends(get_current_super_admin)):
    reason = (payload or {}).get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A revocation reason is required")
    cert = await db.certificates.find_one({"certificate_id": certificate_id}, {"_id": 0, "course_title": 1})
    if not cert:
        raise HTTPException(status_code=404, detail="Credential not found")
    await db.certificates.update_one(
        {"certificate_id": certificate_id},
        {"$set": {"revoked": True, "revoked_reason": reason, "revoked_at": now_iso(), "revoked_by": sa}})
    from admin_audit import log_admin_action
    await log_admin_action(sa, "credential.revoke", "certificate", certificate_id, cert["course_title"], {"reason": reason}, request)
    return {"ok": True}


@router.post("/credentials/{certificate_id}/restore")
async def restore_credential(certificate_id: str, request: Request, sa: str = Depends(get_current_super_admin)):
    r = await db.certificates.update_one(
        {"certificate_id": certificate_id},
        {"$set": {"revoked": False}, "$unset": {"revoked_reason": "", "revoked_at": "", "revoked_by": ""}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Credential not found")
    from admin_audit import log_admin_action
    await log_admin_action(sa, "credential.restore", "certificate", certificate_id, certificate_id, None, request)
    return {"ok": True}


# ---- Phase 2: AI operations ---------------------------------------------------------


@router.get("/ai-ops")
async def ai_ops(days: int = 30, _sa: str = Depends(get_current_super_admin)):
    days = max(1, min(days, 180))
    now = datetime.now(timezone.utc)
    since = _iso(now - timedelta(days=days))
    sessions = await db.chat_sessions.find(
        {"updated_at": {"$gte": since}}, {"_id": 0, "id": 1, "user_id": 1, "title": 1, "created_at": 1, "messages": 1}
    ).to_list(3000)
    total_sessions = len(sessions)
    total_msgs = sum(len(s.get("messages") or []) for s in sessions)
    total_chars = sum(len(m.get("content", "")) for s in sessions for m in (s.get("messages") or []))
    est_tokens = total_chars // 4  # rough heuristic, clearly labeled an estimate in UI
    est_cost = round(est_tokens / 1_000_000 * 6.0, 2)  # blended $/1M-token estimate
    active_users = len({s["user_id"] for s in sessions})
    daily = {}
    for s in sessions:
        d = (s.get("created_at") or "")[:10]
        if d:
            daily[d] = daily.get(d, 0) + 1
    daily_series = sorted(({"date": k, "sessions": v} for k, v in daily.items()), key=lambda x: x["date"])[-30:]
    topics = {}
    for s in sessions:
        t = (s.get("title") or "Untitled")[:60]
        topics[t] = topics.get(t, 0) + 1
    top_topics = sorted(({"topic": k, "sessions": v} for k, v in topics.items()), key=lambda x: -x["sessions"])[:10]
    all_time = await db.chat_sessions.count_documents({})

    # Learner-provided quality ratings (thumbs up / down) — real signal, not heuristics.
    period_ratings = await db.tutor_ratings.find(
        {"updated_at": {"$gte": since}},
        {"_id": 0, "rating": 1, "reason": 1, "updated_at": 1, "session_id": 1, "turn_index": 1},
    ).to_list(5000)
    up_count = sum(1 for r in period_ratings if r.get("rating") == "up")
    down_count = sum(1 for r in period_ratings if r.get("rating") == "down")
    total_ratings = up_count + down_count
    satisfaction_pct = round((up_count / total_ratings) * 100, 1) if total_ratings else None
    coverage_pct = round((total_ratings / total_msgs) * 100, 1) if total_msgs else 0
    recent_negative = sorted(
        [r for r in period_ratings if r.get("rating") == "down" and (r.get("reason") or "").strip()],
        key=lambda r: r.get("updated_at", ""), reverse=True,
    )[:8]
    return {
        "days": days,
        "summary": {
            "sessions": total_sessions, "all_time_sessions": all_time,
            "active_users": active_users,
            "messages": total_msgs,
            "avg_msgs_per_session": round(total_msgs / total_sessions, 1) if total_sessions else 0,
            "est_tokens": est_tokens, "est_cost_usd": est_cost,
            "ratings_up": up_count, "ratings_down": down_count,
            "ratings_total": total_ratings,
            "satisfaction_pct": satisfaction_pct,
            "rating_coverage_pct": coverage_pct,
        },
        "daily": daily_series, "top_topics": top_topics,
        "recent_negative_reasons": [
            {"reason": r.get("reason", ""), "at": r.get("updated_at", "")} for r in recent_negative
        ],
        "generated_at": now_iso(),
    }
