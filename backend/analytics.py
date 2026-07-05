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
        return iso_str[:10]
    except Exception:
        return None


def _fill_series(labels: list[str], docs: list[dict], date_field: str) -> list[dict]:
    """Bucket docs into a day-by-day count series."""
    buckets: dict[str, int] = {d: 0 for d in labels}
    for d in docs:
        day = _iso_day(d.get(date_field, ""))
        if day and day in buckets:
            buckets[day] += 1
    return [{"date": d, "count": buckets[d]} for d in labels]


# ---- platform helpers ------------------------------------------------------


async def _platform_top_orgs(start_iso: str) -> list[dict]:
    """Top 5 organizations by certificates issued in the window."""
    pipeline = [
        {"$match": {"issued_at": {"$gte": start_iso}}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "id", "as": "u"}},
        {"$unwind": {"path": "$u", "preserveNullAndEmptyArrays": True}},
        {"$match": {"u.org_id": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$u.org_id", "certs": {"$sum": 1}}},
        {"$sort": {"certs": -1}},
        {"$limit": 5},
    ]
    raw = await db.certificates.aggregate(pipeline).to_list(10)
    if not raw:
        return []
    ids = [t["_id"] for t in raw]
    org_docs = await db.organizations.find(
        {"id": {"$in": ids}},
        {"_id": 0, "id": 1, "name": 1, "slug": 1},
    ).to_list(20)
    lookup = {o["id"]: o for o in org_docs}
    return [
        {**lookup.get(t["_id"], {"id": t["_id"], "name": "(unknown)", "slug": t["_id"]}),
         "certs": t["certs"]}
        for t in raw
    ]


async def _platform_top_courses(start_iso: str) -> list[dict]:
    """Top 10 courses by enrollment in the window. Orphaned course_ids skipped."""
    pipeline = [
        {"$match": {"enrolled_at": {"$gte": start_iso}}},
        {"$group": {"_id": "$course_id", "enrollments": {"$sum": 1}}},
        {"$sort": {"enrollments": -1}},
        {"$limit": 10},
    ]
    raw = await db.enrollments.aggregate(pipeline).to_list(20)
    if not raw:
        return []
    ids = [t["_id"] for t in raw]
    course_docs = await db.courses.find(
        {"id": {"$in": ids}},
        {"_id": 0, "id": 1, "title": 1, "slug": 1, "category": 1},
    ).to_list(20)
    lookup = {c["id"]: c for c in course_docs}
    return [
        {**lookup[t["_id"]], "enrollments": t["enrollments"]}
        for t in raw
        if t["_id"] in lookup
    ]


async def _platform_active_users() -> dict:
    now = datetime.now(timezone.utc)
    windows = {"last_24h": 1, "last_7d": 7, "last_30d": 30}
    out: dict[str, int] = {}
    for label, days in windows.items():
        since = (now - timedelta(days=days)).isoformat()
        out[label] = len(await db.enrollments.distinct("user_id", {"enrolled_at": {"$gte": since}}))
    return out


async def _platform_founder_perk() -> dict:
    claimed = await db.users.count_documents({"founding_member_seq": {"$exists": True}})
    return {
        "cap": 500,
        "claimed": claimed,
        "remaining": max(0, 500 - claimed),
        "first_course_locked": await db.users.count_documents({"founding_course_id": {"$exists": True}}),
        "cert_used": await db.users.count_documents({"founding_cert_used": True}),
    }


async def _platform_totals() -> dict:
    total_seats = await db.organizations.aggregate(
        [{"$group": {"_id": None, "s": {"$sum": "$seat_count"}}}]
    ).to_list(1)
    return {
        "users": await db.users.count_documents({}),
        "orgs": await db.organizations.count_documents({}),
        "seats_issued": total_seats[0]["s"] if total_seats else 0,
        "certs_all_time": await db.certificates.count_documents({}),
    }


# ---- platform-wide (super admin) ------------------------------------------


async def platform_analytics(days: int = 30) -> dict:
    """Return aggregated metrics for the super-admin console."""
    start, labels = _daterange(days)
    start_iso = start.isoformat()

    signups_docs = await db.users.find(
        {"created_at": {"$gte": start_iso}},
        {"_id": 0, "created_at": 1},
    ).to_list(50000)
    certs_docs = await db.certificates.find(
        {"issued_at": {"$gte": start_iso}},
        {"_id": 0, "issued_at": 1},
    ).to_list(50000)

    return {
        "window_days": days,
        "totals": await _platform_totals(),
        "signups_per_day": _fill_series(labels, signups_docs, "created_at"),
        "certs_per_day": _fill_series(labels, certs_docs, "issued_at"),
        "founder_perk": await _platform_founder_perk(),
        "top_orgs_by_certs": await _platform_top_orgs(start_iso),
        "top_courses_by_enrollment": await _platform_top_courses(start_iso),
        "active_users": await _platform_active_users(),
    }


# ---- org helpers -----------------------------------------------------------


def _org_top_courses(enrollments: list[dict], course_lookup: dict) -> list[dict]:
    counts: dict[str, int] = {}
    for e in enrollments:
        counts[e["course_id"]] = counts.get(e["course_id"], 0) + 1
    top_ids = sorted(counts, key=lambda k: -counts[k])[:5]
    return [
        {**course_lookup[cid], "enrollments": counts[cid]}
        for cid in top_ids
        if cid in course_lookup
    ]


def _org_per_user_stats(
    members: list[dict],
    enrollments_window: list[dict],
    all_enrollments: list[dict],
    all_certs: list[dict],
) -> dict[str, dict]:
    """Build per-user stats keyed by user_id."""
    per_user: dict[str, dict] = {}
    for m in members:
        per_user[m["user_id"]] = {
            "user_id": m["user_id"], "full_name": m["full_name"], "email": m["email"],
            "department": m.get("department"), "enrollments_window": 0, "certs_all_time": 0,
            "avg_progress": 0.0, "_progress_sum": 0.0, "_all_enroll_count": 0,
        }
    for e in enrollments_window:
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
    for p in per_user.values():
        p["avg_progress"] = (
            round(p["_progress_sum"] / p["_all_enroll_count"], 1)
            if p["_all_enroll_count"] else 0.0
        )
        p.pop("_progress_sum")
        p.pop("_all_enroll_count")
    return per_user


def _org_departments(members: list[dict], per_user: dict[str, dict]) -> list[dict]:
    stats: dict[str, dict] = {}
    for m in members:
        dept = m.get("department") or "Unassigned"
        d = stats.setdefault(dept, {"name": dept, "members": 0, "certs": 0, "progress_sum": 0.0})
        d["members"] += 1
        u = per_user.get(m["user_id"], {})
        d["certs"] += u.get("certs_all_time", 0)
        d["progress_sum"] += u.get("avg_progress", 0.0)
    out = []
    for d in stats.values():
        n = d["members"] or 1
        out.append({
            "name": d["name"], "members": d["members"], "certs": d["certs"],
            "avg_progress": round(d["progress_sum"] / n, 1),
            "cert_coverage_pct": round(d["certs"] / n * 100, 1),
        })
    out.sort(key=lambda d: -d["cert_coverage_pct"])
    return out


def _org_funnel(all_enrollments: list[dict], all_certs: list[dict]) -> list[dict]:
    enrolled_ids = {e["user_id"] for e in all_enrollments}
    in_progress_ids = {e["user_id"] for e in all_enrollments if 0 < (e.get("progress_pct") or 0) < 100}
    completed_ids = {e["user_id"] for e in all_enrollments if e.get("completed")}
    certified_ids = {c["user_id"] for c in all_certs}
    return [
        {"stage": "Enrolled",    "count": len(enrolled_ids)},
        {"stage": "In progress", "count": len(in_progress_ids)},
        {"stage": "Completed",   "count": len(completed_ids)},
        {"stage": "Certified",   "count": len(certified_ids)},
    ]


# ---- org-scoped (enterprise admin) ----------------------------------------


async def org_analytics(org_id: str, days: int = 30) -> dict:
    """Return aggregated metrics for a single org's admin dashboard."""
    start, labels = _daterange(days)
    start_iso = start.isoformat()

    members = await db.org_members.find(
        {"org_id": org_id},
        {"_id": 0, "user_id": 1, "full_name": 1, "email": 1, "department": 1},
    ).to_list(2000)
    member_user_ids = [m["user_id"] for m in members]

    enrollments = await db.enrollments.find(
        {"user_id": {"$in": member_user_ids}, "enrolled_at": {"$gte": start_iso}},
        {"_id": 0, "user_id": 1, "course_id": 1, "enrolled_at": 1, "completed": 1, "completed_at": 1, "progress_pct": 1},
    ).to_list(20000)
    all_enrollments = await db.enrollments.find(
        {"user_id": {"$in": member_user_ids}},
        {"_id": 0, "user_id": 1, "course_id": 1, "completed": 1, "progress_pct": 1},
    ).to_list(20000)
    certs = await db.certificates.find(
        {"user_id": {"$in": member_user_ids}, "issued_at": {"$gte": start_iso}},
        {"_id": 0, "user_id": 1, "course_id": 1, "issued_at": 1},
    ).to_list(20000)
    all_certs = await db.certificates.find(
        {"user_id": {"$in": member_user_ids}},
        {"_id": 0, "user_id": 1, "course_id": 1},
    ).to_list(20000)

    # Course lookup for orphan-skipping in top-courses
    top_course_ids = list({e["course_id"] for e in enrollments})
    course_docs = await db.courses.find(
        {"id": {"$in": top_course_ids}},
        {"_id": 0, "id": 1, "title": 1, "slug": 1, "category": 1, "thumbnail_url": 1},
    ).to_list(50) if top_course_ids else []
    course_lookup = {c["id"]: c for c in course_docs}

    per_user = _org_per_user_stats(members, enrollments, all_enrollments, all_certs)
    top_learners = sorted(
        per_user.values(),
        key=lambda x: (-x["enrollments_window"], -x["certs_all_time"]),
    )[:5]

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
        "top_courses": _org_top_courses(enrollments, course_lookup),
        "top_learners": top_learners,
        "departments": _org_departments(members, per_user),
        "funnel": _org_funnel(all_enrollments, all_certs),
    }
