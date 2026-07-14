"""Super-admin KPI dashboard aggregation endpoints.

Everything is aggregation-based (no in-Python bucketing) and cached via the
existing @cached decorator so the dashboard is cheap under repeated reloads.

Endpoints:
  GET /api/admin/dashboard                — full snapshot (all cards + charts)
  GET /api/admin/dashboard/timeseries     — on-demand series (metric + range)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_super_admin
from core import db
from core_cache import cached

logger = logging.getLogger("eaia")
router = APIRouter(prefix="/api/admin/dashboard", tags=["admin-dashboard"])


# Unicode regional indicator flag from ISO-3166 alpha-2 code
def _flag(code: str) -> str:
    if not code or len(code) != 2 or not code.isalpha():
        return "🌐"
    return "".join(chr(0x1F1E6 + (ord(c.upper()) - ord("A"))) for c in code)


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _date_labels(days: int) -> list[str]:
    now = datetime.now(timezone.utc)
    return [(now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]


async def _day_series(collection, date_field: str, start_iso: str, labels: list[str]) -> list[dict]:
    pipeline = [
        {"$match": {date_field: {"$gte": start_iso}}},
        {"$project": {"day": {"$substr": [f"${date_field}", 0, 10]}}},
        {"$group": {"_id": "$day", "count": {"$sum": 1}}},
    ]
    rows = await collection.aggregate(pipeline).to_list(len(labels) + 10)
    counts = {r["_id"]: r["count"] for r in rows}
    return [{"date": d, "count": counts.get(d, 0)} for d in labels]


@cached(ttl_seconds=45, key_prefix="admin_dashboard_kpis")
async def _compute_kpis() -> dict:
    now = datetime.now(timezone.utc)
    d7 = (now - timedelta(days=7)).isoformat()
    d30 = (now - timedelta(days=30)).isoformat()

    total_users = await db.users.count_documents({})
    active_7d = await db.users.count_documents({"last_login_at": {"$gte": d7}})
    active_30d = await db.users.count_documents({"last_login_at": {"$gte": d30}})
    enrollments_total = await db.enrollments.count_documents({})

    attempts_total = await db.assessment_attempts.count_documents({"status": "completed"})
    certs_total = await db.certificates.count_documents({})
    pass_rate = round(100 * certs_total / attempts_total, 1) if attempts_total > 0 else 0.0

    # Revenue — sum of paid payment_transactions (real Stripe-confirmed orders)
    rev_pipeline = [
        {"$match": {"payment_status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    rev_rows = await db.payment_transactions.aggregate(rev_pipeline).to_list(1)
    revenue_total = float(rev_rows[0]["total"]) if rev_rows else 0.0

    llm_key_health = "green" if os.environ.get("EMERGENT_LLM_KEY") else "red"

    return {
        "total_users": total_users,
        "active_7d": active_7d,
        "active_30d": active_30d,
        "enrollments_total": enrollments_total,
        "exam_pass_rate": pass_rate,
        "revenue_total": revenue_total,
        "llm_key_health": llm_key_health,
    }


@cached(ttl_seconds=120, key_prefix="admin_dashboard_top_courses")
async def _top_courses(limit: int = 8) -> list[dict]:
    pipeline = [
        {"$group": {"_id": "$course_id", "enrollments": {"$sum": 1}}},
        {"$sort": {"enrollments": -1}},
        {"$limit": limit},
    ]
    rows = await db.enrollments.aggregate(pipeline).to_list(limit)
    ids = [r["_id"] for r in rows]
    courses = await db.courses.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "slug": 1, "title": 1}).to_list(len(ids))
    by_id = {c["id"]: c for c in courses}
    return [
        {"slug": by_id.get(r["_id"], {}).get("slug", r["_id"]),
         "title": by_id.get(r["_id"], {}).get("title", r["_id"]),
         "enrollments": r["enrollments"]}
        for r in rows
    ]


@cached(ttl_seconds=180, key_prefix="admin_dashboard_band")
async def _band_distribution() -> list[dict]:
    """Distribution of enrollments by course difficulty (band)."""
    pipeline = [
        {"$lookup": {"from": "courses", "localField": "course_id", "foreignField": "id", "as": "course"}},
        {"$unwind": {"path": "$course", "preserveNullAndEmptyArrays": True}},
        {"$group": {"_id": {"$ifNull": ["$course.difficulty", "Unknown"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    rows = await db.enrollments.aggregate(pipeline).to_list(10)
    return [{"band": r["_id"], "count": r["count"]} for r in rows]


@cached(ttl_seconds=180, key_prefix="admin_dashboard_language")
async def _language_distribution() -> list[dict]:
    """Distribution of logins by primary Accept-Language tag over the last 30 days."""
    d30 = _iso_days_ago(30)
    pipeline = [
        {"$match": {"created_at": {"$gte": d30}}},
        {"$group": {"_id": {"$ifNull": ["$primary_language", "unknown"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    rows = await db.user_login_logs.aggregate(pipeline).to_list(10)
    label_by_code = {"en": "English", "es": "Spanish", "fr": "French", "de": "German",
                     "hi": "Hindi", "pt": "Portuguese", "ja": "Japanese", "zh": "Chinese",
                     "it": "Italian", "ru": "Russian", "ar": "Arabic", "ko": "Korean"}
    return [{"code": r["_id"], "language": label_by_code.get(r["_id"], (r["_id"] or "").upper()), "count": r["count"]} for r in rows]


@cached(ttl_seconds=180, key_prefix="admin_dashboard_geo")
async def _geo_summary(days: int = 30) -> dict:
    dfrom = _iso_days_ago(days)
    logins_30d = await db.user_login_logs.count_documents({"created_at": {"$gte": dfrom}})
    countries = await db.user_login_logs.aggregate([
        {"$match": {"created_at": {"$gte": dfrom}, "country": {"$ne": "Unknown"}}},
        {"$group": {"_id": "$country"}},
    ]).to_list(500)
    cities = await db.user_login_logs.aggregate([
        {"$match": {"created_at": {"$gte": dfrom}, "city": {"$ne": "Unknown"}}},
        {"$group": {"_id": {"country": "$country", "city": "$city"}}},
    ]).to_list(2000)

    top_rows = await db.user_login_logs.aggregate([
        {"$match": {"created_at": {"$gte": dfrom}, "country": {"$ne": "Unknown"}}},
        {"$group": {"_id": "$country", "count": {"$sum": 1}, "code": {"$first": "$country_code"}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]).to_list(5)

    top_countries = [
        {"country": r["_id"], "code": r.get("code", "??"), "count": r["count"], "flag": _flag(r.get("code", "??"))}
        for r in top_rows
    ]
    return {
        "countries": len(countries),
        "cities": len(cities),
        "logins_30d": logins_30d,
        "top_countries": top_countries,
    }


@cached(ttl_seconds=120, key_prefix="admin_dashboard_signups_enrollments")
async def _signups_enrollments_series(days: int = 30) -> list[dict]:
    labels = _date_labels(days)
    start_iso = _iso_days_ago(days)
    signups = await _day_series(db.users, "created_at", start_iso, labels)
    enrollments = await _day_series(db.enrollments, "enrolled_at", start_iso, labels)
    e_by_date = {r["date"]: r["count"] for r in enrollments}
    return [{"date": s["date"], "signups": s["count"], "enrollments": e_by_date.get(s["date"], 0)} for s in signups]


@router.get("")
async def dashboard_snapshot(_super_admin_id: str = Depends(get_current_super_admin)):
    """Full super-admin dashboard payload (all cards + charts + geo card)."""
    return {
        "kpis": await _compute_kpis(),
        "signups_enrollments_30d": await _signups_enrollments_series(30),
        "top_courses": await _top_courses(8),
        "band_distribution": await _band_distribution(),
        "language_distribution": await _language_distribution(),
        "geo": await _geo_summary(30),
    }


@router.get("/timeseries")
async def dashboard_timeseries(
    metric: str = Query(..., pattern="^(signups|enrollments|exam_attempts|orders)$"),
    days: int = Query(30, ge=1, le=365),
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Return {labels, values} for the requested metric over the last N days."""
    labels = _date_labels(days)
    start_iso = _iso_days_ago(days)
    collection_map = {
        "signups": (db.users, "created_at"),
        "enrollments": (db.enrollments, "enrolled_at"),
        "exam_attempts": (db.assessment_attempts, "created_at"),
        "orders": (db.payment_transactions, "created_at"),
    }
    if metric not in collection_map:
        raise HTTPException(status_code=400, detail="Unsupported metric")
    collection, date_field = collection_map[metric]
    series = await _day_series(collection, date_field, start_iso, labels)
    return {"metric": metric, "days": days, "series": series}
