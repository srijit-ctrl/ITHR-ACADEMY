"""Login-event tracking + best-effort IP geolocation.

Adds three side-effects to every successful login (fire-and-forget so slow
network calls never block the auth flow):

1. Update the user's `last_login_at`, `login_count`, `last_ip` fields.
2. Insert a doc into `user_login_logs` with (user_id, ip, user_agent,
   accept_language, country, city, created_at).
3. Cache the IP→country mapping in `ip_geo_cache` for 24h so repeat logins
   from the same IP don't hammer the free geo API.

Geo lookup: uses ip-api.com free tier (45 req/min, no key). If the API is
down or the IP is private/local, we log with country="Unknown". Every branch
returns fast — no request path should ever be blocked by geo lookup.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
from datetime import datetime, timezone

import httpx

from core import db, now_iso

logger = logging.getLogger("eaia")

GEO_CACHE_TTL_HOURS = 24
GEO_API_URL = "http://ip-api.com/json/{ip}?fields=status,country,countryCode,city"
GEO_TIMEOUT_SEC = 2.5


def _extract_client_ip(headers: dict, fallback: str | None = None) -> str:
    """Prefer X-Forwarded-For (respecting first hop) then X-Real-IP then fallback."""
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if xff:
        # First IP in the chain is the client
        return xff.split(",")[0].strip()
    xri = headers.get("x-real-ip") or headers.get("X-Real-IP")
    if xri:
        return xri.strip()
    return fallback or "unknown"


def _is_private_ip(ip: str) -> bool:
    """Return True for RFC1918/loopback/link-local — never worth geo-looking-up."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved
    except (ValueError, TypeError):
        return True


async def _fetch_geo(ip: str) -> dict:
    """Return {country, country_code, city} or all-Unknown on any failure."""
    unknown = {"country": "Unknown", "country_code": "??", "city": "Unknown"}
    if not ip or ip == "unknown" or _is_private_ip(ip):
        return unknown

    # Cache lookup — successful entries live 24h
    cached = await db.ip_geo_cache.find_one({"ip": ip}, {"_id": 0, "country": 1, "country_code": 1, "city": 1, "expires_at": 1})
    if cached and cached.get("expires_at", "") > now_iso():
        return {"country": cached.get("country", "Unknown"),
                "country_code": cached.get("country_code", "??"),
                "city": cached.get("city", "Unknown")}

    try:
        async with httpx.AsyncClient(timeout=GEO_TIMEOUT_SEC) as client:
            r = await client.get(GEO_API_URL.format(ip=ip))
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    geo = {
                        "country": data.get("country") or "Unknown",
                        "country_code": data.get("countryCode") or "??",
                        "city": data.get("city") or "Unknown",
                    }
                    # Cache for 24h
                    from datetime import timedelta
                    expires_at = (datetime.now(timezone.utc) + timedelta(hours=GEO_CACHE_TTL_HOURS)).isoformat()
                    await db.ip_geo_cache.update_one(
                        {"ip": ip},
                        {"$set": {**geo, "ip": ip, "expires_at": expires_at, "cached_at": now_iso()}},
                        upsert=True,
                    )
                    return geo
    except Exception as e:
        logger.debug(f"[geo] lookup failed for {ip}: {e}")
    return unknown


async def track_login(user_id: str, headers: dict, client_host: str | None) -> None:
    """Fire-and-forget login tracking. Callers should schedule via asyncio.create_task
    so slow geo lookups never block the login response."""
    try:
        ip = _extract_client_ip(headers, fallback=client_host)
        user_agent = headers.get("user-agent") or headers.get("User-Agent") or ""
        accept_language = headers.get("accept-language") or headers.get("Accept-Language") or ""
        # Primary language tag: `en-US,en;q=0.9` → `en`
        primary_lang = accept_language.split(",")[0].split(";")[0].split("-")[0].strip().lower() or "unknown"

        geo = await _fetch_geo(ip)

        ts = now_iso()

        # (1) Update user doc counters
        await db.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "last_login_at": ts,
                    "last_ip": ip,
                    "last_country": geo["country"],
                    "last_country_code": geo["country_code"],
                    "last_city": geo["city"],
                    "last_language": primary_lang,
                },
                "$inc": {"login_count": 1},
            },
        )

        # (2) Detailed login log row
        await db.user_login_logs.insert_one({
            "user_id": user_id,
            "ip": ip,
            "user_agent": user_agent[:500],
            "accept_language": accept_language[:200],
            "primary_language": primary_lang,
            "country": geo["country"],
            "country_code": geo["country_code"],
            "city": geo["city"],
            "created_at": ts,
        })
    except Exception as e:
        # Never let a tracking failure break login — this is background hygiene
        logger.debug(f"[login-track] failed for user_id={user_id}: {e}")


def schedule_login_tracking(user_id: str, request) -> None:
    """Convenience: schedule track_login without blocking. Call from route handlers."""
    try:
        headers = {k.lower(): v for k, v in request.headers.items()}
        client_host = request.client.host if request.client else None
        asyncio.create_task(track_login(user_id, headers, client_host))
    except Exception as e:
        logger.debug(f"[login-track] schedule failed: {e}")
