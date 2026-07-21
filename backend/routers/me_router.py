"""Learner self-service portal endpoints (/api/me/*).

Every route is scoped to the caller — a learner can only view and mutate
their own profile. No admin permissions required, no cross-user reads.

Route inventory:
- GET  /api/me                    → hydrated profile snapshot for the portal
- GET  /api/me/summary            → dashboard KPI roll-up (streak, XP, next lesson)
- PATCH /api/me/profile           → update full_name, title, department, location,
                                    timezone, bio, avatar_url (base64 or URL)
- POST /api/me/change-password    → old + new password (rejects Google-auth users)
- POST /api/me/inspire            → Claude-generated personalised motivational quote
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from emergentintegrations.llm.chat import UserMessage, TextDelta, StreamDone

from auth import get_current_user_id, hash_password, verify_password
from core import db, logger, now_iso
from ai_service import _build_chat

router = APIRouter(prefix="/api/me", tags=["self-service"])


# ---------------------------------------------------------------------------
# Simple per-user hourly rate limiter shared across a couple of endpoints.
# Backing collection `me_rate` — one row per bucket key, resets on window roll.
# ---------------------------------------------------------------------------
async def _rate_ok(bucket_key: str, limit_per_hour: int) -> bool:
    """Return True if the request is under the limit, False if throttled."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)
    doc = await db.me_rate.find_one({"key": bucket_key})
    if not doc:
        await db.me_rate.insert_one({
            "key": bucket_key, "count": 1, "window_start": now.isoformat(),
        })
        return True
    try:
        ws = datetime.fromisoformat(doc["window_start"])
        if ws.tzinfo is None:
            ws = ws.replace(tzinfo=timezone.utc)
    except Exception:
        ws = window_start
    if ws < window_start:
        await db.me_rate.update_one(
            {"key": bucket_key},
            {"$set": {"count": 1, "window_start": now.isoformat()}},
        )
        return True
    if doc.get("count", 0) >= limit_per_hour:
        return False
    await db.me_rate.update_one({"key": bucket_key}, {"$inc": {"count": 1}})
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_MAX_AVATAR_BYTES = 400_000  # 400 KB — client should compress before upload
_AVATAR_MIME_RE = re.compile(r"^data:image/(png|jpe?g|webp|gif);base64,", re.I)


def _validate_avatar(avatar_url: Optional[str]) -> None:
    """Reject monster payloads / non-image data URIs. Public URLs pass through."""
    if not avatar_url:
        return
    if avatar_url.startswith("data:"):
        if not _AVATAR_MIME_RE.match(avatar_url):
            raise HTTPException(400, "Avatar must be a PNG/JPEG/WebP/GIF data URI or an https URL")
        # Rough size check — base64 expands ~1.33× so decode-length check is accurate.
        try:
            _, b64 = avatar_url.split(",", 1)
            raw_len = (len(b64) * 3) // 4
            if raw_len > _MAX_AVATAR_BYTES:
                raise HTTPException(413, f"Avatar too large — max {_MAX_AVATAR_BYTES // 1024} KB after compression")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "Malformed avatar data URI")
    elif not avatar_url.startswith("https://"):
        raise HTTPException(400, "avatar_url must be https:// or a data URI")


def _public_user(doc: dict) -> dict:
    """Trim sensitive fields before returning."""
    doc = {**doc}
    for k in ("password_hash", "mfa_secret", "mfa_backup_codes", "_id"):
        doc.pop(k, None)
    return doc


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    title: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = Field(default=None, max_length=80)
    location: Optional[str] = Field(default=None, max_length=80)
    timezone: Optional[str] = Field(default=None, max_length=64)
    bio: Optional[str] = Field(default=None, max_length=500)
    avatar_url: Optional[str] = Field(default=None, max_length=800_000)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


class InspireRequest(BaseModel):
    mood: Optional[str] = Field(default=None, max_length=40)


class DailyGoalUpdate(BaseModel):
    target_minutes: int = Field(..., ge=5, le=180)


# Minutes credited per module_event kind — coarse but honest proxy for
# time-on-task without instrumenting <video> timeupdate. Tune via the two
# constants below; both are safe to bump if you later want a more generous
# habit engine.
MINUTES_PER_MODULE_STARTED = 2
MINUTES_PER_MODULE_COMPLETED = 8
DEFAULT_DAILY_GOAL_MINUTES = 15


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("")
async def me_profile(user_id: str = Depends(get_current_user_id)):
    """Full profile snapshot for the self-service portal."""
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(404, "User not found")
    user = _public_user(doc)
    user["can_change_password"] = user.get("auth_provider") != "google" and bool(doc.get("password_hash"))
    return {"user": user}


@router.get("/summary")
async def me_summary(user_id: str = Depends(get_current_user_id)):
    """Compact KPI roll-up for the profile hero — streak, XP, courses, next-lesson."""
    doc = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}

    enrollments_total = await db.enrollments.count_documents({"user_id": user_id})
    enrollments_completed = await db.enrollments.count_documents({"user_id": user_id, "completed": True})
    enrollments_in_progress = enrollments_total - enrollments_completed
    certificates = await db.certificates.count_documents({"user_id": user_id})

    # Aggregate progress percentage across enrollments
    avg_progress = 0.0
    if enrollments_total > 0:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": None, "avg": {"$avg": {"$ifNull": ["$progress_pct", 0]}}}},
        ]
        agg = await db.enrollments.aggregate(pipeline).to_list(1)
        if agg:
            avg_progress = round(float(agg[0].get("avg") or 0), 1)

    # Next-best lesson: most recently-accessed incomplete enrollment
    next_up = None
    async for row in db.enrollments.find(
        {"user_id": user_id, "completed": {"$ne": True}},
        {"_id": 0, "course_id": 1, "progress_pct": 1, "last_accessed": 1},
    ).sort("last_accessed", -1).limit(1):
        course = await db.courses.find_one(
            {"id": row["course_id"]},
            {"_id": 0, "slug": 1, "title": 1, "thumbnail_url": 1},
        )
        if course:
            next_up = {
                "slug": course.get("slug"),
                "title": course.get("title"),
                "thumbnail_url": course.get("thumbnail_url"),
                "progress_pct": round(float(row.get("progress_pct") or 0), 1),
            }
        break

    # Last 5 activity events for the "recent activity" strip
    recent_events = []
    async for e in db.module_events.find(
        {"user_id": user_id}, {"_id": 0, "kind": 1, "course_id": 1, "module_id": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5):
        recent_events.append(e)

    return {
        "user": {
            "id": doc.get("id"),
            "email": doc.get("email"),
            "full_name": doc.get("full_name"),
            "avatar_url": doc.get("avatar_url"),
            "xp": int(doc.get("xp") or 0),
            "streak_days": int(doc.get("streak_days") or 0),
            "founding_member_seq": doc.get("founding_member_seq"),
            "created_at": doc.get("created_at"),
        },
        "kpis": {
            "enrollments_total": enrollments_total,
            "enrollments_completed": enrollments_completed,
            "enrollments_in_progress": enrollments_in_progress,
            "certificates": certificates,
            "avg_progress_pct": avg_progress,
        },
        "next_up": next_up,
        "recent_events": recent_events,
    }


@router.patch("/profile")
async def update_profile(payload: ProfileUpdate, user_id: str = Depends(get_current_user_id)):
    """Partial-update the caller's profile fields. Empty strings are ignored."""
    _validate_avatar(payload.avatar_url)

    updates = {}
    for field in ("full_name", "title", "department", "location", "timezone", "bio", "avatar_url"):
        val = getattr(payload, field)
        if val is None:
            continue
        # Empty string → clear the field (mongo will replace with "")
        updates[field] = val.strip() if isinstance(val, str) else val
    if not updates:
        raise HTTPException(400, "No fields to update")

    updates["updated_at"] = now_iso()
    await db.users.update_one({"id": user_id}, {"$set": updates})
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(404, "User not found")
    return {"user": _public_user(doc), "updated_fields": list(updates.keys())}


@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, user_id: str = Depends(get_current_user_id)):
    """Change the caller's password. Rejects Google-auth users."""
    if not await _rate_ok(f"change-pw:{user_id}", limit_per_hour=8):
        raise HTTPException(429, "Too many password-change attempts — please wait an hour")
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(404, "User not found")

    if doc.get("auth_provider") == "google" and not doc.get("password_hash"):
        raise HTTPException(400, "This account signs in with Google — passwords are managed by Google")

    if not doc.get("password_hash"):
        raise HTTPException(400, "This account has no password set — use the reset-password flow")

    if not verify_password(payload.current_password, doc["password_hash"]):
        raise HTTPException(401, "Current password is incorrect")

    if payload.new_password == payload.current_password:
        raise HTTPException(400, "New password must differ from current password")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": hash_password(payload.new_password),
            "must_reset_password": False,
            "password_changed_at": now_iso(),
        }},
    )
    logger.info(f"[me] Password changed for user {user_id}")
    return {"ok": True, "message": "Password updated"}


# ---------------------------------------------------------------------------
# Motivational quote — AI-generated personalised burst.
# ---------------------------------------------------------------------------
INSPIRE_SYSTEM_PROMPT = """You are an inspiration engine embedded in the ITHR Enterprise Agentic AI Academy learner portal.

Produce exactly ONE motivational quote for the learner named below, tuned to their learning context. Style guardrails:
- 1 to 2 short sentences. Maximum 220 characters total.
- Warm, energetic, human — not corporate.
- Reference the domain: agentic AI, machine intelligence, mastery, career growth, curiosity, engineering craft.
- No emojis. No hashtags. No quotation marks around the sentence.
- Never mention the learner's raw email address.
- If the learner just enrolled: celebrate the beginning.
- If they're mid-course: nudge momentum.
- If they hold a credential: celebrate the milestone and dare them to teach it.

Output the sentence only — no preamble, no attribution, no line breaks."""


@router.post("/inspire")
async def inspire(payload: InspireRequest, user_id: str = Depends(get_current_user_id)):
    """AI-generated personalised motivational quote via Claude Sonnet 4.5."""
    if not await _rate_ok(f"inspire:{user_id}", limit_per_hour=20):
        raise HTTPException(429, "Too many inspiration requests — please wait a few minutes")
    doc = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}
    first_name = (doc.get("full_name") or "there").split(" ")[0]
    xp = int(doc.get("xp") or 0)
    streak = int(doc.get("streak_days") or 0)

    # Current course (most-recently-accessed enrollment)
    current_course = None
    async for row in db.enrollments.find(
        {"user_id": user_id, "completed": {"$ne": True}}, {"_id": 0, "course_id": 1, "progress_pct": 1},
    ).sort("last_accessed", -1).limit(1):
        course = await db.courses.find_one({"id": row["course_id"]}, {"_id": 0, "title": 1, "slug": 1})
        if course:
            current_course = {**course, "progress_pct": row.get("progress_pct", 0)}
        break

    certs_total = await db.certificates.count_documents({"user_id": user_id})

    context = (
        f"Learner name: {first_name}\n"
        f"XP total: {xp}\n"
        f"Streak days: {streak}\n"
        f"Credentials earned: {certs_total}\n"
        f"Currently studying: {current_course.get('title') if current_course else 'no active course yet'}\n"
    )
    if current_course:
        context += f"Course progress: {current_course.get('progress_pct', 0)}%\n"
    if payload.mood:
        context += f"Learner mood signal: {payload.mood}\n"
    context += "\nWrite one motivational sentence for them now."

    try:
        chat = _build_chat(
            session_id=f"inspire-{user_id}-{uuid.uuid4().hex[:6]}",
            system_message=INSPIRE_SYSTEM_PROMPT,
            model_key="claude-sonnet-4.5",
        )
        chunks: list[str] = []
        async for event in chat.stream_message(UserMessage(text=context)):
            if isinstance(event, TextDelta):
                chunks.append(event.content)
            elif isinstance(event, StreamDone):
                break
        quote = "".join(chunks).strip().strip('"').strip("'")
        if not quote:
            raise ValueError("empty LLM output")
        # Trim if the model overshoots
        if len(quote) > 260:
            quote = quote[:257].rstrip() + "…"
        return {"quote": quote, "personalised": True}
    except Exception as e:  # pragma: no cover — network / LLM failures
        logger.warning(f"[me/inspire] LLM call failed for {user_id}: {e}")
        # Curated fallback so the UI never renders blank
        fallback_pool = [
            "The models change every quarter — your craft compounds every day.",
            f"Ship one lesson today, {first_name}. That's how mastery accretes.",
            "The best agent architects treat every prompt as a design decision.",
            "You're not learning tools — you're learning to think in systems that think.",
            "Curiosity, then rigor, then output. In that order. Every day.",
        ]
        return {"quote": fallback_pool[hash(user_id) % len(fallback_pool)], "personalised": False}


# ---------------------------------------------------------------------------
# Daily learning goal — habit engine
# ---------------------------------------------------------------------------
def _date_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


async def _minutes_by_day(user_id: str, days: int = 8) -> dict[str, int]:
    """Aggregate module_events into estimated minutes-learned per UTC day.

    Returns a dict keyed by `YYYY-MM-DD` covering the last `days` (inclusive
    of today). Missing days default to 0 in the caller.
    """
    from_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    # Include today + previous (days-1) → total `days` buckets
    from datetime import timedelta as _td
    window_start = from_dt - _td(days=days - 1)

    per_day: dict[str, int] = {}
    async for evt in db.module_events.find(
        {"user_id": user_id, "created_at": {"$gte": window_start.isoformat()}},
        {"_id": 0, "kind": 1, "created_at": 1},
    ):
        try:
            evt_dt = datetime.fromisoformat(evt["created_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        key = _date_str(evt_dt)
        credit = MINUTES_PER_MODULE_COMPLETED if evt.get("kind") == "completed" else MINUTES_PER_MODULE_STARTED
        per_day[key] = per_day.get(key, 0) + credit
    return per_day


def _streak_days(per_day: dict[str, int], target: int, today: datetime) -> int:
    """Count consecutive days (ending today OR yesterday) where minutes ≥ target.

    Yesterday is allowed as the tail so learners don't lose their streak the
    moment they haven't opened the app today yet.
    """
    from datetime import timedelta as _td
    streak = 0
    today_utc = today.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    # Allow either today or yesterday to be the streak tail.
    today_hit = per_day.get(_date_str(today_utc), 0) >= target
    cursor = today_utc if today_hit else (today_utc - _td(days=1))
    while True:
        if per_day.get(_date_str(cursor), 0) >= target:
            streak += 1
            cursor -= _td(days=1)
        else:
            break
    return streak


@router.get("/daily-goal")
async def get_daily_goal(user_id: str = Depends(get_current_user_id)):
    """Today's minutes + 7-day heatmap + current streak."""
    doc = await db.users.find_one({"id": user_id}, {"_id": 0, "daily_goal_minutes": 1}) or {}
    target = int(doc.get("daily_goal_minutes") or DEFAULT_DAILY_GOAL_MINUTES)

    now = datetime.now(timezone.utc)
    per_day = await _minutes_by_day(user_id, days=8)

    from datetime import timedelta as _td
    week: list[dict] = []
    for i in range(7, 0, -1):
        d = now - _td(days=i - 1)
        key = _date_str(d)
        minutes = per_day.get(key, 0)
        week.append({
            "date": key,
            "day_of_week": d.strftime("%a"),
            "minutes": minutes,
            "hit_goal": minutes >= target,
        })

    today = week[-1]
    remaining = max(0, target - today["minutes"])
    pct = min(100, round((today["minutes"] / max(target, 1)) * 100))
    streak = _streak_days(per_day, target, now)

    return {
        "target_minutes": target,
        "today": {
            "date": today["date"],
            "minutes": today["minutes"],
            "remaining_minutes": remaining,
            "pct": pct,
            "hit_goal": today["hit_goal"],
        },
        "streak_days": streak,
        "week": week,
        "preset_targets": [5, 15, 30, 60],
    }


@router.patch("/daily-goal")
async def update_daily_goal(payload: DailyGoalUpdate, user_id: str = Depends(get_current_user_id)):
    """Update the caller's daily target (5-180 minutes)."""
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"daily_goal_minutes": payload.target_minutes, "daily_goal_updated_at": now_iso()}},
    )
    return await get_daily_goal(user_id=user_id)  # type: ignore[arg-type]
