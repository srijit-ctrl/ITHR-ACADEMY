"""Executive Command Centre: consolidated KPIs, alert centre, Org/User 360 drill-downs."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_super_admin
from core import db, now_iso

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
    attempts = await db.quiz_attempts.count_documents(in_window("created_at"))
    passes = await db.quiz_attempts.count_documents({"passed": True, **in_window("created_at")})
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
    add("active_users", "Active users (period)", cur["active_users"], prev["active_users"], drill="traffic", definition=f"Distinct users logging in during the period")
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
    attempts = await db.quiz_attempts.count_documents({"created_at": {"$gte": month_ago}})
    passes = await db.quiz_attempts.count_documents({"passed": True, "created_at": {"$gte": month_ago}})
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
