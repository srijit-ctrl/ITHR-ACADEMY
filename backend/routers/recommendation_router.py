"""AI-powered course recommendation engine.

Blends:
- Rule-based signals (industry match, difficulty ladder, category overlap, credential path)
- Claude-drafted rationale for the top pick (cached per user for 24h)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage
from fastapi import APIRouter, Depends

from auth import get_current_user_id
from core import compute_freshness, db, logger, now_iso

router = APIRouter(prefix="/api", tags=["recommendations"])


# Difficulty ladder — the higher the index, the more advanced.
DIFFICULTY_ORDER = [
    "Fundamental", "Beginner", "Intermediate", "Advanced",
    "Expert", "Architect", "Enterprise Leader", "CXO",
]


def _difficulty_rank(d: str) -> int:
    try:
        return DIFFICULTY_ORDER.index(d)
    except ValueError:
        return 2  # default to Intermediate


def _learner_posture(completed_courses: list[dict]) -> tuple[set, set, int]:
    """Aggregate industry, category, and max-difficulty-rank across completed courses."""
    industries: set = set()
    categories: set = set()
    max_rank = -1
    for c in completed_courses:
        industries.update(c.get("industries", []))
        categories.add(c.get("category"))
        max_rank = max(max_rank, _difficulty_rank(c.get("difficulty", "Beginner")))
    return industries, categories, max_rank


def _difficulty_score(c_rank: int, learner_max_rank: int) -> float:
    """Reward next-step difficulty progression; penalize regression / huge jump."""
    if learner_max_rank == -1:
        return max(0, 12 - abs(c_rank - 1) * 5)
    delta = c_rank - learner_max_rank
    if delta == 1:
        return 18
    if delta == 0:
        return 10
    if delta == 2:
        return 6
    if delta < 0:
        return 2
    return 0  # jump >= 3


def _score_one_course(
    course: dict,
    learner_industries: set,
    learner_categories: set,
    learner_max_rank: int,
) -> tuple[float, dict]:
    """Return (score, signals) tuple for a single course against learner posture."""
    overlap_ind = len(set(course.get("industries", [])) & learner_industries)
    overlap_cat = 1 if course.get("category") in learner_categories else 0
    c_rank = _difficulty_rank(course.get("difficulty", "Beginner"))
    freshness, _ = compute_freshness(course)

    score = 0.0
    score += overlap_ind * 8 + overlap_cat * 12
    score += _difficulty_score(c_rank, learner_max_rank)
    score += min(10, (course.get("enrolled_count", 0) / 3000))
    score += (course.get("rating", 4.5) - 4.0) * 4
    score += (freshness - 60) * 0.1
    if course.get("has_full_content"):
        score += 6

    signals = {
        "industry_overlap": overlap_ind,
        "category_overlap": overlap_cat,
        "difficulty_delta": c_rank - learner_max_rank if learner_max_rank >= 0 else None,
        "has_full_content": course.get("has_full_content", False),
        "freshness": freshness,
    }
    return score, signals


async def _score_courses(user_id: str) -> list[dict]:
    enrollments = await db.enrollments.find({"user_id": user_id}, {"_id": 0}).to_list(200)
    certs = await db.certificates.find({"user_id": user_id}, {"_id": 0}).to_list(200)
    enrolled_course_ids = {e["course_id"] for e in enrollments}
    cert_course_ids = {c["course_id"] for c in certs}

    completed_courses = await db.courses.find(
        {"id": {"$in": list(cert_course_ids)}}, {"_id": 0}
    ).to_list(200) if cert_course_ids else []

    learner_industries, learner_categories, learner_max_rank = _learner_posture(completed_courses)

    all_courses = await db.courses.find({}, {"_id": 0}).to_list(200)
    scored: list[dict] = []
    for c in all_courses:
        if c["id"] in enrolled_course_ids or c["id"] in cert_course_ids:
            continue
        score, signals = _score_one_course(c, learner_industries, learner_categories, learner_max_rank)
        scored.append({"course": c, "score": round(score, 2), "signals": signals})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _thin(course: dict) -> dict:
    """Return only fields the client needs (drop modules/quiz)."""
    return {
        "id": course.get("id"),
        "slug": course.get("slug"),
        "title": course.get("title"),
        "subtitle": course.get("subtitle"),
        "category": course.get("category"),
        "industries": course.get("industries", []),
        "difficulty": course.get("difficulty"),
        "duration_hours": course.get("duration_hours"),
        "thumbnail_url": course.get("thumbnail_url"),
        "instructor": course.get("instructor"),
        "enrolled_count": course.get("enrolled_count", 0),
        "rating": course.get("rating", 4.7),
        "has_full_content": course.get("has_full_content", False),
    }


@router.get("/recommendations")
async def get_recommendations(user_id: str = Depends(get_current_user_id)):
    scored = await _score_courses(user_id)
    top = scored[:6]
    return {
        "generated_at": now_iso(),
        "count": len(top),
        "recommendations": [
            {"course": _thin(x["course"]), "score": x["score"], "signals": x["signals"]}
            for x in top
        ],
    }


async def _rationale_from_llm(learner_context: str, course: dict) -> str:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        return ""
    # SHA-256 (truncated) — cache key hash, not a security digest.
    sig = hashlib.sha256(f"{learner_context}::{course['slug']}".encode()).hexdigest()[:12]
    chat = LlmChat(
        api_key=key,
        session_id=f"rec-rationale-{sig}",
        system_message=(
            "You are Solon, the ITHR AI Career Mentor. Return a 2-sentence, "
            "specific rationale (max 55 words) for WHY this ITHR course is the next-best "
            "step for this learner. No preamble. No 'as a mentor'. No bullet points."
        ),
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    prompt = (
        f"Learner context:\n{learner_context}\n\n"
        f"Course: {course['title']} — {course.get('subtitle','')}\n"
        f"Category: {course.get('category')} | Difficulty: {course.get('difficulty')}\n"
        f"Industries: {', '.join(course.get('industries', [])) or 'general'}\n\n"
        f"Write the rationale."
    )
    chunks = []
    try:
        async for event in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(event, TextDelta):
                chunks.append(event.content)
            elif isinstance(event, StreamDone):
                break
    except Exception:
        logger.exception("rationale llm failed")
        return ""
    return "".join(chunks).strip()


@router.get("/recommendations/next-best")
async def next_best(user_id: str = Depends(get_current_user_id)):
    """Return the single top recommendation + AI-written rationale (24h cache)."""
    scored = await _score_courses(user_id)
    if not scored:
        return {"recommendation": None}
    top = scored[0]
    course = top["course"]

    # Build learner context for LLM
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    certs = await db.certificates.find(
        {"user_id": user_id}, {"_id": 0, "course_title": 1}
    ).to_list(50)
    completed_titles = [c["course_title"] for c in certs]
    learner_context = (
        f"Name: {user.get('full_name','learner')}\n"
        f"Title: {user.get('title','')}\n"
        f"Organization: {user.get('organization','')}\n"
        f"Certifications earned: {', '.join(completed_titles) if completed_titles else 'none yet'}"
    )

    # Cache rationale by (user, course) for 24h — SHA-256 used as cache key, not a security digest.
    cache_key = hashlib.sha256(f"{user_id}::{course['slug']}".encode()).hexdigest()
    cached = await db.rec_rationales.find_one({"key": cache_key}, {"_id": 0})
    if cached:
        try:
            created = datetime.fromisoformat(cached["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - created).total_seconds() < 86400:
                rationale = cached["rationale"]
            else:
                rationale = None
        except Exception:
            rationale = None
    else:
        rationale = None

    if not rationale:
        rationale = await _rationale_from_llm(learner_context, course)
        if rationale:
            await db.rec_rationales.update_one(
                {"key": cache_key},
                {"$set": {"key": cache_key, "rationale": rationale, "created_at": now_iso()}},
                upsert=True,
            )

    return {
        "recommendation": {
            "course": _thin(course),
            "score": top["score"],
            "signals": top["signals"],
            "rationale": rationale or "This is your best next step based on your interests and prior work.",
        }
    }
