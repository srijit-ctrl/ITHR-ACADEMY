"""Analytics aggregation helpers shared by super-admin and enterprise-admin
dashboards.

Kept out of the routers so both `admin_router` (platform-wide) and
`enterprise_router` (org-scoped) can share the same day-bucketing +
completion-funnel logic without drifting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import db

# ---- date helpers ----------------------------------------------------------


def _daterange(days: int) -> tuple[datetime, list[str]]:
    """Return (start_iso_dt, list of YYYY-MM-DD strings inclusive)."""
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days - 1)
    labels = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    return start, labels


def _iso_day(iso_str: str) -> str | None:
    """Extract YYYY-MM-DD from an ISO string; returns None on failure."""
    if not iso_str:
        return None
    try:
        return iso_str[:10]  # YYYY-MM-DD
    except Exception:
        return None


def _empty_series(labels: list[str]) -> list[dict]:
    return [{"date": d, "count": 0} for d in labels]


def _fill_series(labels: list[str], docs: list[dict], date_field: str) -> list[dict]:
    """Bucket docs into a day-by-day count series."""
    buckets: dict[str, int] = {d: 0 for d in labels}
    for d in docs:
        day = _iso_day(d.get(date_field, ""))
        if day and day in buckets:
            buckets[day] += 1
    return [{"date": d, "count": buckets[d]} for d in labels]


# ---- platform-wide (super admin) ------------------------------------------


async def platform_analytics(days: int = 30) -> dict:
    """Return aggregated metrics for the super-admin console."""
    start, labels = _daterange(days)
    start_iso = start.isoformat()

    # Signups per day
    signups_docs = await db.users.find(
        {"created_at": {"$gte": start_iso}},
        {"_id": 0, "created_at": 1},
    ).to_list(50000)

    # Certificates per day
    certs_docs = await db.certificates.find(
        {"issued_at": {"$gte": start_iso}},
        {"_id": 0, "issued_at": 1},
    ).to_list(50000)

    # Founder code claim rate (all-time — 500 is a small cap)
    founders_claimed = await db.users.count_documents({"founding_member_seq": {"$exists": True}})
    founders_with_first_course = await db.users.count_documents({"founding_course_id": {"$exists": True}})
    founders_cert_used = await db.users.count_documents({"founding_cert_used": True})

    # Top 5 orgs by cert issuance (last {days})
    org_pipeline = [
        {"$match": {"issued_at": {"$gte": start_iso}}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "id", "as": "u"}},
        {"$unwind": {"path": "$u", "preserveNullAndEmptyArrays": True}},
        {"$match": {"u.org_id": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$u.org_id", "certs": {"$sum": 1}}},
        {"$sort": {"certs": -1}},
        {"$limit": 5},
    ]
    top_orgs_raw = await db.certificates.aggregate(org_pipeline).to_list(10)
    top_org_ids = [t["_id"] for t in top_orgs_raw]
    org_docs = await db.organizations.find(
        {"id": {"$in": top_org_ids}},
        {"_id": 0, "id": 1, "name": 1, "slug": 1},
    ).to_list(20) if top_org_ids else []
    org_lookup = {o["id"]: o for o in org_docs}
    top_orgs = [
        {**org_lookup.get(t["_id"], {"id": t["_id"], "name": "(unknown)", "slug": t["_id"]}),
         "certs": t["certs"]}
        for t in top_orgs_raw
    ]

    # Top 10 courses by enrollment (last {days})
    top_course_pipeline = [
        {"$match": {"enrolled_at": {"$gte": start_iso}}},
        {"$group": {"_id": "$course_id", "enrollments": {"$sum": 1}}},
        {"$sort": {"enrollments": -1}},
        {"$limit": 10},
    ]
    top_courses_raw = await db.enrollments.aggregate(top_course_pipeline).to_list(20)
    top_course_ids = [t["_id"] for t in top_courses_raw]
    course_docs = await db.courses.find(
        {"id": {"$in": top_course_ids}},
        {"_id": 0, "id": 1, "title": 1, "slug": 1, "category": 1},
    ).to_list(20) if top_course_ids else []
    course_lookup = {c["id"]: c for c in course_docs}
    top_courses = [
        {**course_lookup.get(t["_id"], {"id": t["_id"], "title": "(unknown)", "slug": ""}),
         "enrollments": t["enrollments"]}
        for t in top_courses_raw
    ]

    # Active user counts (any activity in last 24h / 7d / 30d)
    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(days=1)).isoformat()
    since_7d = (now - timedelta(days=7)).isoformat()
    since_30d = (now - timedelta(days=30)).isoformat()

    active_24h = len(await db.enrollments.distinct("user_id", {"enrolled_at": {"$gte": since_24h}}))
    active_7d = len(await db.enrollments.distinct("user_id", {"enrolled_at": {"$gte": since_7d}}))
    active_30d = len(await db.enrollments.distinct("user_id", {"enrolled_at": {"$gte": since_30d}}))

    # Totals
    total_users = await db.users.count_documents({})
    total_orgs = await db.organizations.count_documents({})
    total_seats = await db.organizations.aggregate([
        {"$group": {"_id": None, "s": {"$sum": "$seat_count"}}}
    ]).to_list(1)
    total_seats_val = total_seats[0]["s"] if total_seats else 0
    total_certs_all_time = await db.certificates.count_documents({})

    return {
        "window_days": days,
        "totals": {
            "users": total_users,
            "orgs": total_orgs,
            "seats_issued": total_seats_val,
            "certs_all_time": total_certs_all_time,
        },
        "signups_per_day": _fill_series(labels, signups_docs, "created_at"),
        "certs_per_day": _fill_series(labels, certs_docs, "issued_at"),
        "founder_perk": {
            "cap": 500,
            "claimed": founders_claimed,
            "remaining": max(0, 500 - founders_claimed),
            "first_course_locked": founders_with_first_course,
            "cert_used": founders_cert_used,
        },
        "top_orgs_by_certs": top_orgs,
        "top_courses_by_enrollment": top_courses,
        "active_users": {
            "last_24h": active_24h,
            "last_7d": active_7d,
            "last_30d": active_30d,
        },
    }


# ---- org-scoped (enterprise admin) ----------------------------------------


async def org_analytics(org_id: str, days: int = 30) -> dict:
    """Return aggregated metrics for a single org's admin dashboard."""
    start, labels = _daterange(days)
    start_iso = start.isoformat()

    # Members of this org
    members = await db.org_members.find(
        {"org_id": org_id},
        {"_id": 0, "user_id": 1, "full_name": 1, "email": 1, "department": 1},
    ).to_list(2000)
    member_user_ids = [m["user_id"] for m in members]

    # Enrollments in window
    enrollments = await db.enrollments.find(
        {"user_id": {"$in": member_user_ids}, "enrolled_at": {"$gte": start_iso}},
        {"_id": 0, "user_id": 1, "course_id": 1, "enrolled_at": 1, "completed": 1, "completed_at": 1, "progress_pct": 1},
    ).to_list(20000)

    # All enrollments (for funnel)
    all_enrollments = await db.enrollments.find(
        {"user_id": {"$in": member_user_ids}},
        {"_id": 0, "user_id": 1, "course_id": 1, "completed": 1, "progress_pct": 1},
    ).to_list(20000)

    # Certificates in window
    certs = await db.certificates.find(
        {"user_id": {"$in": member_user_ids}, "issued_at": {"$gte": start_iso}},
        {"_id": 0, "user_id": 1, "course_id": 1, "issued_at": 1},
    ).to_list(20000)
    all_certs = await db.certificates.find(
        {"user_id": {"$in": member_user_ids}},
        {"_id": 0, "user_id": 1, "course_id": 1},
    ).to_list(20000)

    # Top 5 courses by enrollment in-window
    course_counts: dict[str, int] = {}
    for e in enrollments:
        course_counts[e["course_id"]] = course_counts.get(e["course_id"], 0) + 1
    top_course_ids = sorted(course_counts, key=lambda k: -course_counts[k])[:5]
    course_docs = await db.courses.find(
        {"id": {"$in": top_course_ids}},
        {"_id": 0, "id": 1, "title": 1, "slug": 1, "category": 1, "thumbnail_url": 1},
    ).to_list(20) if top_course_ids else []
    course_lookup = {c["id"]: c for c in course_docs}
    top_courses = [
        {**course_lookup.get(cid, {"id": cid, "title": "(unknown)", "slug": ""}),
         "enrollments": course_counts[cid]}
        for cid in top_course_ids
    ]

    # Top 5 most active learners (by enrollments in-window then all-time certs)
    per_user: dict[str, dict] = {}
    for m in members:
        per_user[m["user_id"]] = {
            "user_id": m["user_id"], "full_name": m["full_name"], "email": m["email"],
            "department": m.get("department"), "enrollments_window": 0, "certs_all_time": 0,
            "avg_progress": 0.0, "_progress_sum": 0.0, "_all_enroll_count": 0,
        }
    for e in enrollments:
        p = per_user.get(e["user_id"])
        if p:
            p["enrollments_window"] += 1
    for e in all_enrollments:
        p = per_user.get(e["user_id"])
        if p:
            p["_progress_sum"] += e.get("progress_pct", 0.0)
            p["_all_enroll_count"] += 1
    for c in all_certs:
        p = per_user.get(c["user_id"])
        if p:
            p["certs_all_time"] += 1
    for _uid, p in per_user.items():
        p["avg_progress"] = round(p["_progress_sum"] / p["_all_enroll_count"], 1) if p["_all_enroll_count"] else 0.0
        p.pop("_progress_sum")
        p.pop("_all_enroll_count")
    top_learners = sorted(
        per_user.values(),
        key=lambda x: (-x["enrollments_window"], -x["certs_all_time"]),
    )[:5]

    # Department leaderboard
    dept_stats: dict[str, dict] = {}
    for m in members:
        dept = m.get("department") or "Unassigned"
        d = dept_stats.setdefault(dept, {"name": dept, "members": 0, "certs": 0, "progress_sum": 0.0})
        d["members"] += 1
        stats = per_user.get(m["user_id"], {})
        d["certs"] += stats.get("certs_all_time", 0)
        d["progress_sum"] += stats.get("avg_progress", 0.0)
    departments = []
    for d in dept_stats.values():
        avg = round(d["progress_sum"] / d["members"], 1) if d["members"] else 0.0
        departments.append({
            "name": d["name"], "members": d["members"],
            "certs": d["certs"], "avg_progress": avg,
            "cert_coverage_pct": round(d["certs"] / d["members"] * 100, 1) if d["members"] else 0.0,
        })
    departments.sort(key=lambda d: -d["cert_coverage_pct"])

    # Completion funnel (all-time within the org)
    enrolled_ids = {e["user_id"] for e in all_enrollments}
    in_progress_ids = {e["user_id"] for e in all_enrollments if 0 < (e.get("progress_pct") or 0) < 100}
    completed_ids = {e["user_id"] for e in all_enrollments if e.get("completed")}
    certified_ids = {c["user_id"] for c in all_certs}
    funnel = [
        {"stage": "Enrolled",     "count": len(enrolled_ids)},
        {"stage": "In progress",  "count": len(in_progress_ids)},
        {"stage": "Completed",    "count": len(completed_ids)},
        {"stage": "Certified",    "count": len(certified_ids)},
    ]

    return {
        "window_days": days,
        "totals": {
            "members": len(members),
            "enrollments_window": len(enrollments),
            "certs_window": len(certs),
            "certs_all_time": len(all_certs),
        },
        "enrollments_per_day": _fill_series(labels, enrollments, "enrolled_at"),
        "certs_per_day": _fill_series(labels, certs, "issued_at"),
        "top_courses": top_courses,
        "top_learners": top_learners,
        "departments": departments,
        "funnel": funnel,
    }
