"""Catalog + courses + enrollments + lessons."""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user_id
from core import compute_freshness, db, now_iso
from core_cache import cached
from models import Course, CourseSummary, Enrollment, LessonCompleteRequest
from seed_data import CATEGORIES, CERTIFICATION_PATHS, INDUSTRIES

router = APIRouter(prefix="/api", tags=["catalog"])


@cached(ttl_seconds=180, key_prefix="catalog_courses")
async def _cached_course_docs(query_key: str, query: dict) -> list[dict]:
    """Cached fetch of course docs matching a filter.

    `query_key` is passed as a deterministic string to the decorator so
    dict-value queries key correctly (dicts aren't hashable for cache keys
    but the caller pre-serializes to a stable string).
    """
    return await db.courses.find(query, {"_id": 0}).to_list(200)


@router.get("/catalog/industries")
async def get_industries():
    return {"industries": INDUSTRIES}


@router.get("/catalog/categories")
async def get_categories():
    return {"categories": CATEGORIES}


@router.get("/catalog/certification-paths")
async def get_certification_paths():
    return {"paths": CERTIFICATION_PATHS}


@router.get("/courses", response_model=List[CourseSummary])
async def list_courses(
    category: Optional[str] = None,
    industry: Optional[str] = None,
    difficulty: Optional[str] = None,
    q: Optional[str] = None,
):
    query = {}
    if category:
        query["category"] = category
    if industry:
        query["industries"] = industry
    if difficulty:
        query["difficulty"] = difficulty
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"subtitle": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]
    # Stable string key so the cache decorator can hash it
    import json as _json
    query_key = _json.dumps(query, sort_keys=True, default=str)
    docs = await _cached_course_docs(query_key, query)
    out = []
    for d in docs:
        score, days = compute_freshness(d)
        out.append(CourseSummary(
            id=d["id"], slug=d["slug"], title=d["title"], subtitle=d["subtitle"],
            category=d["category"], industries=d.get("industries", []),
            difficulty=d["difficulty"], duration_hours=d["duration_hours"],
            thumbnail_url=d["thumbnail_url"], intro_video_url=d.get("intro_video_url"),
            instructor=d["instructor"],
            enrolled_count=d.get("enrolled_count", 0), rating=d.get("rating", 4.7),
            module_count=len(d.get("modules", [])),
            has_full_content=d.get("has_full_content", False),
            last_reviewed_at=d.get("last_reviewed_at"),
            freshness_score=score, days_since_review=days,
        ))
    return out


@router.get("/courses/{slug}", response_model=Course)
async def get_course(slug: str):
    doc = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Course not found")
    score, days = compute_freshness(doc)
    doc["freshness_score"] = score
    doc["days_since_review"] = days
    return Course(**doc)


def _build_preview_script(course: dict) -> str:
    """Compose a ~30-second (~75-word) audio pitch from course meta."""
    title = course.get("title", "this program")
    subtitle = course.get("subtitle") or ""
    difficulty = course.get("difficulty", "")
    duration = course.get("duration_hours", "")
    category = course.get("category", "")
    modules = course.get("modules", []) or []
    first_module = modules[0].get("title") if modules and isinstance(modules[0], dict) else ""

    parts = [f"Welcome to {title}."]
    if subtitle:
        parts.append(subtitle.rstrip(".") + ".")
    if first_module:
        parts.append(f"We open with {first_module},")
    parts.append(f"then walk you through {len(modules) or 15} focused modules")
    if duration:
        parts.append(f"across roughly {duration} hours of executive-grade material.")
    else:
        parts.append("of executive-grade material.")
    if difficulty:
        parts.append(f"Pitched at the {difficulty.lower()} level")
        if category:
            parts.append(f"for {category.lower()} practitioners.")
        else:
            parts.append("for enterprise practitioners.")
    parts.append("Ready when you are — enroll below to begin.")
    script = " ".join(parts)
    # Keep it comfortably inside the TTS 2000-char cap
    return script[:1200]


@router.get("/courses/{slug}/preview-audio")
async def course_preview_audio(slug: str):
    """Return a cached ~30-second TTS pitch for the course.

    First request generates via OpenAI TTS + Emergent LLM key, caches the MP3
    base64 in `course_previews`. Subsequent requests hit the cache (< 5ms).
    Freshness: cache is invalidated whenever the course's `last_reviewed_at`
    changes so refreshed courses get a fresh pitch.
    """
    import base64
    import os

    course = await db.courses.find_one(
        {"slug": slug},
        {"_id": 0, "id": 1, "slug": 1, "title": 1, "subtitle": 1, "difficulty": 1,
         "duration_hours": 1, "category": 1, "modules.title": 1, "last_reviewed_at": 1},
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    cache_key = f"{course['id']}::{course.get('last_reviewed_at', '')}"
    cached_row = await db.course_previews.find_one({"cache_key": cache_key}, {"_id": 0})
    if cached_row and cached_row.get("audio_b64"):
        return {
            "audio_b64": cached_row["audio_b64"],
            "mime": cached_row.get("mime", "audio/mpeg"),
            "script": cached_row.get("script", ""),
            "cached": True,
        }

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    script = _build_preview_script(course)
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        tts = OpenAITextToSpeech(api_key=key)
        audio_bytes = await tts.generate_speech(
            text=script, model="tts-1", voice="shimmer", speed=1.05, response_format="mp3",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS generation failed: {e}") from e

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    await db.course_previews.update_one(
        {"cache_key": cache_key},
        {"$set": {
            "cache_key": cache_key,
            "course_id": course["id"],
            "slug": slug,
            "script": script,
            "audio_b64": audio_b64,
            "mime": "audio/mpeg",
            "voice": "shimmer",
            "generated_at": now_iso(),
        }},
        upsert=True,
    )
    return {"audio_b64": audio_b64, "mime": "audio/mpeg", "script": script, "cached": False}


@router.post("/courses/{slug}/enroll")
async def enroll(slug: str, user_id: str = Depends(get_current_user_id)):
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    existing = await db.enrollments.find_one({"user_id": user_id, "course_id": course["id"]})
    if existing:
        return {"enrollment_id": existing["id"], "already_enrolled": True}
    enrollment = Enrollment(user_id=user_id, course_id=course["id"])
    await db.enrollments.insert_one(enrollment.model_dump())
    await db.courses.update_one({"id": course["id"]}, {"$inc": {"enrolled_count": 1}})
    # Founding-member first-course perk (idempotent, no-op for non-founders)
    try:
        from founding_member import claim_first_course
        await claim_first_course(user_id, course["id"])
    except Exception:
        pass

    # Live activity feed
    try:
        import asyncio as _asyncio
        from core import log_activity
        u = await db.users.find_one({"id": user_id}, {"_id": 0, "full_name": 1})
        _asyncio.create_task(log_activity(
            kind="enrollment",
            message=f'{(u or {}).get("full_name", "A learner")} enrolled in "{course["title"]}"',
            actor_id=user_id, actor_name=(u or {}).get("full_name"),
            target={"course_slug": slug},
        ))
    except Exception:
        pass

    return {"enrollment_id": enrollment.id, "already_enrolled": False}


@router.get("/enrollments")
async def my_enrollments(user_id: str = Depends(get_current_user_id)):
    enrollments = await db.enrollments.find({"user_id": user_id}, {"_id": 0}).to_list(200)
    course_ids = [e["course_id"] for e in enrollments]
    courses = await db.courses.find({"id": {"$in": course_ids}}, {"_id": 0, "modules": 0, "quiz": 0}).to_list(200)
    course_map = {c["id"]: c for c in courses}
    result = []
    for e in enrollments:
        c = course_map.get(e["course_id"])
        if not c:
            continue
        result.append({
            "enrollment": e,
            "course": {
                "id": c["id"], "slug": c["slug"], "title": c["title"],
                "subtitle": c["subtitle"], "thumbnail_url": c["thumbnail_url"],
                "category": c["category"], "difficulty": c["difficulty"],
                "duration_hours": c["duration_hours"],
            },
        })
    return result


@router.post("/lessons/complete")
async def complete_lesson(payload: LessonCompleteRequest, user_id: str = Depends(get_current_user_id)):
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    enrollment = await db.enrollments.find_one({"user_id": user_id, "course_id": payload.course_id})
    if not enrollment:
        raise HTTPException(status_code=400, detail="Not enrolled")

    completed_lessons = set(enrollment.get("completed_lessons", []))
    completed_lessons.add(payload.lesson_id)
    total_lessons = sum(len(m.get("lessons", [])) for m in course.get("modules", []))
    progress_pct = (len(completed_lessons) / total_lessons * 100) if total_lessons else 0.0

    completed_modules = set(enrollment.get("completed_modules", []))
    for m in course.get("modules", []):
        lesson_ids = {l["id"] for l in m.get("lessons", [])}
        if lesson_ids and lesson_ids.issubset(completed_lessons):
            completed_modules.add(m["id"])

    await db.enrollments.update_one(
        {"user_id": user_id, "course_id": payload.course_id},
        {"$set": {
            "completed_lessons": list(completed_lessons),
            "completed_modules": list(completed_modules),
            "progress_pct": round(progress_pct, 1),
            "last_accessed": now_iso(),
        }},
    )
    await db.users.update_one({"id": user_id}, {"$inc": {"xp": 20}})
    return {"progress_pct": round(progress_pct, 1), "completed_lessons": len(completed_lessons), "total_lessons": total_lessons}
