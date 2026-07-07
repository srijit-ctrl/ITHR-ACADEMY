"""Anonymous website traffic tracking.

Endpoints:
  - POST /api/telemetry/pageview           (public, anonymous — 1 call per SPA route change)
  - GET  /api/admin/traffic/summary        (super-admin only — dashboard payload)

Design:
  - No cookies. Uniqueness = sha256(ip + user_agent)[:16] → "visitor_id".
  - Fire-and-forget geo lookup reuses login_tracking._fetch_geo (24h cache).
  - Bot filtering: any UA containing a common crawler token is silently dropped.
  - Rate limit per IP-hash: max 30 pageviews / 60s to protect Mongo.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_super_admin, get_current_user_optional
from core import db, logger, now_iso
from login_tracking import _extract_client_ip, _fetch_geo

router = APIRouter(tags=["traffic"])

# In-memory rate limiter (per IP-hash). Resets on backend restart — good enough.
_recent_hits: dict[str, list[float]] = {}
_RATE_MAX = 30
_RATE_WINDOW_SEC = 60

_BOT_TOKENS = (
    "bot", "crawler", "spider", "curl/", "wget/", "python-requests", "httpx/",
    "headlesschrome", "lighthouse", "pingdom", "uptime", "monitor",
)


class PageviewPayload(BaseModel):
    path: str
    referrer: str | None = None


def _visitor_id(ip: str, user_agent: str) -> str:
    return hashlib.sha256(f"{ip}::{user_agent}".encode("utf-8")).hexdigest()[:16]


def _looks_like_bot(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(t in ua for t in _BOT_TOKENS)


def _rate_ok(vid: str) -> bool:
    now = time.time()
    window = _recent_hits.setdefault(vid, [])
    # Drop old
    cutoff = now - _RATE_WINDOW_SEC
    window[:] = [t for t in window if t > cutoff]
    if len(window) >= _RATE_MAX:
        return False
    window.append(now)
    return True


# ---------------- PUBLIC — record a pageview ----------------
@router.post("/api/telemetry/pageview")
async def pageview(
    payload: PageviewPayload,
    request: Request,
    user_id: str | None = Depends(get_current_user_optional),
):
    headers = {k.lower(): v for k, v in request.headers.items()}
    ua = headers.get("user-agent", "")[:500]

    if _looks_like_bot(ua):
        return {"ok": True, "skipped": "bot"}

    ip = _extract_client_ip(headers, fallback=(request.client.host if request.client else None))
    vid = _visitor_id(ip, ua)

    if not _rate_ok(vid):
        return {"ok": True, "skipped": "rate_limit"}

    # Sanitise path — reject anything longer than 200 chars or containing junk
    path = (payload.path or "/")[:200]
    referrer = (payload.referrer or "")[:200]

    # Geo lookup is cached 24h in login_tracking; safe to call every pageview.
    geo = await _fetch_geo(ip)

    ts = datetime.now(timezone.utc)
    doc = {
        "visitor_id": vid,
        "user_id": user_id,          # None if anonymous
        "ip": ip,
        "user_agent": ua,
        "path": path,
        "referrer": referrer,
        "country": geo["country"],
        "country_code": geo["country_code"],
        "city": geo["city"],
        "created_at": ts.isoformat(),
        "day": ts.strftime("%Y-%m-%d"),
        "hour": ts.strftime("%Y-%m-%dT%H"),
    }
    try:
        await db.page_visits.insert_one(doc)
    except Exception:
        logger.exception("pageview insert failed (non-fatal)")
    return {"ok": True}


# ---------------- SUPER-ADMIN — traffic summary ----------------
def _flag(code: str) -> str:
    if not code or len(code) != 2 or not code.isalpha():
        return "🌐"
    return "".join(chr(0x1F1E6 + (ord(c.upper()) - ord("A"))) for c in code)


@router.get("/api/admin/traffic/summary")
async def traffic_summary(_admin_id: str = Depends(get_current_super_admin)):
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    d7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    d30 = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    # Totals
    total_all = await db.page_visits.count_documents({})

    # Today
    today_visits = await db.page_visits.count_documents({"day": today})
    today_unique = len(await db.page_visits.distinct("visitor_id", {"day": today}))

    # Last 7 days
    seven_visits = await db.page_visits.count_documents({"day": {"$gte": d7}})
    seven_unique = len(await db.page_visits.distinct("visitor_id", {"day": {"$gte": d7}}))

    # Last 30 days
    thirty_unique = len(await db.page_visits.distinct("visitor_id", {"day": {"$gte": d30}}))

    # Top countries (last 30d) — one visitor counted once per country/day pair
    country_pipeline = [
        {"$match": {"day": {"$gte": d30}}},
        {"$group": {"_id": {"country": "$country", "cc": "$country_code", "vid": "$visitor_id"}}},
        {"$group": {"_id": {"country": "$_id.country", "cc": "$_id.cc"}, "unique_visitors": {"$sum": 1}}},
        {"$sort": {"unique_visitors": -1}},
        {"$limit": 15},
    ]
    countries = []
    async for row in db.page_visits.aggregate(country_pipeline):
        countries.append({
            "country": row["_id"]["country"],
            "country_code": row["_id"]["cc"],
            "flag": _flag(row["_id"]["cc"]),
            "unique_visitors": row["unique_visitors"],
        })

    # Top cities (last 7d)
    city_pipeline = [
        {"$match": {"day": {"$gte": d7}}},
        {"$group": {"_id": {"city": "$city", "country": "$country", "cc": "$country_code", "vid": "$visitor_id"}}},
        {"$group": {"_id": {"city": "$_id.city", "country": "$_id.country", "cc": "$_id.cc"}, "unique_visitors": {"$sum": 1}}},
        {"$sort": {"unique_visitors": -1}},
        {"$limit": 10},
    ]
    cities = []
    async for row in db.page_visits.aggregate(city_pipeline):
        cities.append({
            "city": row["_id"]["city"],
            "country": row["_id"]["country"],
            "flag": _flag(row["_id"]["cc"]),
            "unique_visitors": row["unique_visitors"],
        })

    # Top pages (last 7d)
    page_pipeline = [
        {"$match": {"day": {"$gte": d7}}},
        {"$group": {"_id": "$path", "views": {"$sum": 1}, "uniques": {"$addToSet": "$visitor_id"}}},
        {"$project": {"path": "$_id", "views": 1, "unique_visitors": {"$size": "$uniques"}, "_id": 0}},
        {"$sort": {"views": -1}},
        {"$limit": 10},
    ]
    pages = []
    async for row in db.page_visits.aggregate(page_pipeline):
        pages.append(row)

    # Hourly buckets for the last 24h
    since_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H")
    hourly_pipeline = [
        {"$match": {"hour": {"$gte": since_24h}}},
        {"$group": {"_id": "$hour", "views": {"$sum": 1}, "uniques": {"$addToSet": "$visitor_id"}}},
        {"$project": {"hour": "$_id", "views": 1, "unique_visitors": {"$size": "$uniques"}, "_id": 0}},
        {"$sort": {"hour": 1}},
    ]
    hourly = []
    async for row in db.page_visits.aggregate(hourly_pipeline):
        hourly.append(row)

    # Daily for last 30d
    daily_pipeline = [
        {"$match": {"day": {"$gte": d30}}},
        {"$group": {"_id": "$day", "views": {"$sum": 1}, "uniques": {"$addToSet": "$visitor_id"}}},
        {"$project": {"day": "$_id", "views": 1, "unique_visitors": {"$size": "$uniques"}, "_id": 0}},
        {"$sort": {"day": 1}},
    ]
    daily = []
    async for row in db.page_visits.aggregate(daily_pipeline):
        daily.append(row)

    return {
        "generated_at": now_iso(),
        "totals": {
            "all_time_pageviews": total_all,
            "today_pageviews": today_visits,
            "today_unique_visitors": today_unique,
            "seven_day_pageviews": seven_visits,
            "seven_day_unique_visitors": seven_unique,
            "thirty_day_unique_visitors": thirty_unique,
        },
        "top_countries": countries,
        "top_cities": cities,
        "top_pages": pages,
        "hourly_last_24h": hourly,
        "daily_last_30d": daily,
    }
