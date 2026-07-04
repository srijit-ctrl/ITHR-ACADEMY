"""Enterprise Agentic AI Academy — FastAPI server."""
from __future__ import annotations

import json
import logging
import os
import random
import string
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (  # noqa: E402
    AuthResponse, ChatRequest, Course, CourseSummary,
    Enrollment, LessonCompleteRequest, QuizAttempt, QuizSubmitRequest,
    UserLogin, UserPublic, UserRegister, Certificate, ChatSession, ChatMessage,
)
from auth import (  # noqa: E402
    create_token, get_current_user_id, hash_password, verify_password,
)
from seed_data import (  # noqa: E402
    build_full_course, CATALOG_COURSES, INDUSTRIES, CATEGORIES, CERTIFICATION_PATHS,
)
from ai_service import stream_tutor_response, generate_course_outline, generate_intelligence_briefing, generate_course_refresh  # noqa: E402
import httpx  # noqa: E402
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest  # noqa: E402
from fastapi import Request  # noqa: E402


# -------------------- DB --------------------
mongo_url = os.environ["MONGO_URL"]
db_name = os.environ["DB_NAME"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[db_name]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eaia")


# -------------------- App --------------------
app = FastAPI(title="Enterprise Agentic AI Academy API", version="1.0.0")
api = APIRouter(prefix="/api")


# ==================== SEEDING ====================
async def seed_database():
    """Seed catalog + full courses. Idempotent (upserts full courses to replace metadata stubs)."""
    from seed_more_courses import (
        build_prompt_engineering_course, build_rag_course,
        build_multi_agent_course, build_ai_governance_course,
    )

    course_count = await db.courses.count_documents({})
    full_builders = [
        build_full_course,
        build_prompt_engineering_course,
        build_rag_course,
        build_multi_agent_course,
        build_ai_governance_course,
    ]
    full_slugs = set()

    # Upsert each full course (replaces metadata stubs if they exist)
    for builder in full_builders:
        full = builder()
        doc = full.model_dump()
        doc["has_full_content"] = True
        # Assign a plausible last_reviewed_at within past 45 days (deterministic per slug for stability)
        import hashlib
        seed_hash = int(hashlib.md5(full.slug.encode()).hexdigest()[:8], 16)
        days_ago = seed_hash % 45  # 0-44 days
        reviewed_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        doc["last_reviewed_at"] = reviewed_at.isoformat()
        await db.courses.update_one({"slug": full.slug}, {"$set": doc}, upsert=True)
        full_slugs.add(full.slug)

    logger.info(f"Upserted {len(full_slugs)} full courses.")

    # Seed catalog metadata for slugs not already present as full
    if course_count == 0:
        logger.info("Seeding catalog metadata...")
        for meta in CATALOG_COURSES:
            if meta["slug"] in full_slugs:
                continue
            import hashlib
            seed_hash = int(hashlib.md5(meta["slug"].encode()).hexdigest()[:8], 16)
            days_ago = seed_hash % 90
            reviewed_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
            catalog_doc = {
                "id": str(uuid.uuid4()),
                "slug": meta["slug"],
                "title": meta["title"],
                "subtitle": meta["subtitle"],
                "description": f"{meta['subtitle']}. Full curriculum in preparation — enroll now to secure early access.",
                "category": meta["category"],
                "industries": meta.get("industries", []),
                "difficulty": meta["difficulty"],
                "duration_hours": meta["duration_hours"],
                "thumbnail_url": meta["thumbnail_url"],
                "hero_url": None,
                "instructor": meta["instructor"],
                "prerequisites": [],
                "learning_objectives": [],
                "skills_gained": [],
                "business_value": "",
                "is_certification_track": True,
                "modules": [],
                "quiz": [],
                "passing_score": 65,
                "enrolled_count": meta["enrolled_count"],
                "rating": meta["rating"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_reviewed_at": reviewed_at.isoformat(),
                "has_full_content": False,
            }
            await db.courses.update_one({"slug": meta["slug"]}, {"$setOnInsert": catalog_doc}, upsert=True)

    await db.courses.create_index("slug", unique=True)
    await db.users.create_index("email", unique=True)
    await db.enrollments.create_index([("user_id", 1), ("course_id", 1)], unique=True)
    await db.certificates.create_index("certificate_id", unique=True)
    total = await db.courses.count_documents({})
    logger.info(f"Seed complete. Total courses: {total}.")


# ==================== HEALTH ====================
@api.get("/")
async def root():
    return {"service": "Enterprise Agentic AI Academy", "status": "ok", "version": "1.0.0"}


@api.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ==================== AUTH ====================
def _user_to_public(doc: dict) -> UserPublic:
    return UserPublic(
        id=doc["id"], email=doc["email"], full_name=doc["full_name"], role=doc["role"],
        organization=doc.get("organization"), title=doc.get("title"),
        created_at=doc["created_at"], avatar_url=doc.get("avatar_url"),
        xp=doc.get("xp", 0), streak_days=doc.get("streak_days", 0),
    )


@api.post("/auth/register", response_model=AuthResponse)
async def register(payload: UserRegister):
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name,
        "role": payload.role or "learner",
        "organization": payload.organization,
        "title": payload.title,
        "avatar_url": None,
        "xp": 0,
        "streak_days": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_token(user_id, doc["email"], doc["role"])
    return AuthResponse(token=token, user=_user_to_public(doc))


@api.post("/auth/login", response_model=AuthResponse)
async def login(payload: UserLogin):
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(doc["id"], doc["email"], doc["role"])
    return AuthResponse(token=token, user=_user_to_public(doc))


@api.get("/auth/me", response_model=UserPublic)
async def me(user_id: str = Depends(get_current_user_id)):
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_public(doc)


@api.post("/auth/google/callback", response_model=AuthResponse)
async def google_callback(payload: dict):
    """Exchange Emergent OAuth session_id for our JWT token. Creates user if new."""
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )
            r.raise_for_status()
            profile = r.json()
        except Exception as e:
            logger.exception("Emergent OAuth exchange failed")
            raise HTTPException(status_code=401, detail=f"OAuth verification failed: {e}")

    email = (profile.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="No email returned by provider")

    existing = await db.users.find_one({"email": email})
    if existing:
        # Ensure avatar / name refreshed
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "avatar_url": profile.get("picture"),
                "full_name": existing.get("full_name") or profile.get("name") or email,
            }},
        )
        user_doc = await db.users.find_one({"email": email})
    else:
        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": email,
            "password_hash": "",  # google-only user
            "full_name": profile.get("name") or email.split("@")[0],
            "role": "learner",
            "organization": None,
            "title": None,
            "avatar_url": profile.get("picture"),
            "xp": 0,
            "streak_days": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "google",
        }
        await db.users.insert_one(user_doc)

    token = create_token(user_doc["id"], user_doc["email"], user_doc["role"])
    return AuthResponse(token=token, user=_user_to_public(user_doc))


# ==================== CATALOG ====================
@api.get("/catalog/industries")
async def get_industries():
    return {"industries": INDUSTRIES}


@api.get("/catalog/categories")
async def get_categories():
    return {"categories": CATEGORIES}


@api.get("/catalog/certification-paths")
async def get_certification_paths():
    return {"paths": CERTIFICATION_PATHS}


def _compute_freshness(doc: dict) -> tuple[int, int]:
    """Return (freshness_score, days_since_review) for a course doc."""
    reviewed = doc.get("last_reviewed_at")
    if not reviewed:
        return 60, 999
    try:
        rev_dt = datetime.fromisoformat(reviewed)
        if rev_dt.tzinfo is None:
            rev_dt = rev_dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - rev_dt).days
        # freshness formula: 100 at 0 days, decays to 60 at 90 days, floors at 55
        score = max(55, min(100, 100 - int(days * 0.45)))
        return score, days
    except Exception:
        return 70, 999


@api.get("/courses", response_model=List[CourseSummary])
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

    docs = await db.courses.find(query, {"_id": 0}).to_list(200)
    summaries = []
    for d in docs:
        score, days = _compute_freshness(d)
        summaries.append(CourseSummary(
            id=d["id"], slug=d["slug"], title=d["title"], subtitle=d["subtitle"],
            category=d["category"], industries=d.get("industries", []),
            difficulty=d["difficulty"], duration_hours=d["duration_hours"],
            thumbnail_url=d["thumbnail_url"], instructor=d["instructor"],
            enrolled_count=d.get("enrolled_count", 0), rating=d.get("rating", 4.7),
            module_count=len(d.get("modules", [])),
            has_full_content=d.get("has_full_content", False),
            last_reviewed_at=d.get("last_reviewed_at"),
            freshness_score=score,
            days_since_review=days,
        ))
    return summaries


@api.get("/courses/{slug}", response_model=Course)
async def get_course(slug: str):
    doc = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Course not found")
    score, days = _compute_freshness(doc)
    doc["freshness_score"] = score
    doc["days_since_review"] = days
    return Course(**doc)


# ==================== ENROLLMENT / PROGRESS ====================
@api.post("/courses/{slug}/enroll")
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
    return {"enrollment_id": enrollment.id, "already_enrolled": False}


@api.get("/enrollments")
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


@api.post("/lessons/complete")
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
            "last_accessed": datetime.now(timezone.utc).isoformat(),
        }},
    )
    await db.users.update_one({"id": user_id}, {"$inc": {"xp": 20}})
    return {"progress_pct": round(progress_pct, 1), "completed_lessons": len(completed_lessons), "total_lessons": total_lessons}


# ==================== QUIZ / CERTIFICATION ====================
def _gen_cert_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"EAIA-2026-{suffix}"


@api.post("/courses/{slug}/quiz/submit")
async def submit_quiz(slug: str, payload: QuizSubmitRequest, user_id: str = Depends(get_current_user_id)):
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    questions = course.get("quiz", [])
    if not questions:
        raise HTTPException(status_code=400, detail="No quiz available for this course")

    correct = 0
    for q in questions:
        submitted = payload.answers.get(q["id"], [])
        if sorted(submitted) == sorted(q["correct"]):
            correct += 1

    total = len(questions)
    score = (correct / total * 100) if total else 0
    passed = score >= course.get("passing_score", 65)

    attempt = QuizAttempt(
        user_id=user_id, course_id=course["id"], score=round(score, 1),
        passed=passed, total_questions=total, correct_count=correct,
        duration_seconds=payload.duration_seconds, answers=payload.answers,
    )
    await db.quiz_attempts.insert_one(attempt.model_dump())

    cert = None
    if passed:
        user = await db.users.find_one({"id": user_id})
        existing_cert = await db.certificates.find_one({"user_id": user_id, "course_id": course["id"]})
        if not existing_cert:
            backend_url = os.environ.get("REACT_APP_BACKEND_URL", "")
            cert_obj = Certificate(
                certificate_id=_gen_cert_id(),
                user_id=user_id,
                user_name=user["full_name"],
                course_id=course["id"],
                course_title=course["title"],
                score=round(score, 1),
                verification_url=f"/verify/{_gen_cert_id()}",
            )
            cert_obj.verification_url = f"/verify/{cert_obj.certificate_id}"
            await db.certificates.insert_one(cert_obj.model_dump())
            await db.enrollments.update_one(
                {"user_id": user_id, "course_id": course["id"]},
                {"$set": {"completed": True, "completed_at": datetime.now(timezone.utc).isoformat(), "progress_pct": 100.0}},
            )
            await db.users.update_one({"id": user_id}, {"$inc": {"xp": 500}})
            cert = cert_obj.model_dump()
        else:
            cert = existing_cert
            cert.pop("_id", None)

    return {
        "score": round(score, 1),
        "passed": passed,
        "correct": correct,
        "total": total,
        "passing_score": course.get("passing_score", 65),
        "attempt_id": attempt.id,
        "certificate": cert,
    }


@api.get("/certificates")
async def my_certificates(user_id: str = Depends(get_current_user_id)):
    certs = await db.certificates.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    return certs


@api.get("/certificates/verify/{certificate_id}")
async def verify_certificate(certificate_id: str):
    cert = await db.certificates.find_one({"certificate_id": certificate_id}, {"_id": 0})
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return {"valid": True, "certificate": cert}


# ==================== AI TUTOR ====================
@api.post("/ai/tutor")
async def ai_tutor(payload: ChatRequest, user_id: str = Depends(get_current_user_id)):
    session_id = payload.session_id or str(uuid.uuid4())

    # Load existing history if session exists
    session = await db.chat_sessions.find_one({"id": session_id, "user_id": user_id}, {"_id": 0})
    history = session["messages"] if session else []

    course_context = None
    if payload.course_context:
        c = await db.courses.find_one({"slug": payload.course_context}, {"_id": 0, "title": 1, "subtitle": 1})
        if c:
            course_context = f"{c['title']} — {c['subtitle']}"

    async def event_generator():
        collected = []
        try:
            async for chunk in stream_tutor_response(
                session_id=session_id,
                user_message=payload.message,
                course_context=course_context,
                history=history,
            ):
                collected.append(chunk)
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
        except Exception as e:
            logger.exception("AI tutor error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        full_response = "".join(collected)
        now = datetime.now(timezone.utc).isoformat()
        new_user_msg = ChatMessage(role="user", content=payload.message).model_dump()
        new_ai_msg = ChatMessage(role="assistant", content=full_response).model_dump()

        if session:
            await db.chat_sessions.update_one(
                {"id": session_id},
                {"$push": {"messages": {"$each": [new_user_msg, new_ai_msg]}},
                 "$set": {"updated_at": now}},
            )
        else:
            new_session = ChatSession(
                id=session_id,
                user_id=user_id,
                title=payload.message[:60],
                messages=[ChatMessage(**new_user_msg), ChatMessage(**new_ai_msg)],
            )
            await db.chat_sessions.insert_one(new_session.model_dump())

        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@api.get("/ai/sessions")
async def list_chat_sessions(user_id: str = Depends(get_current_user_id)):
    sessions = await db.chat_sessions.find({"user_id": user_id}, {"_id": 0, "messages": 0}).sort("updated_at", -1).to_list(50)
    return sessions


@api.get("/ai/sessions/{session_id}")
async def get_chat_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    session = await db.chat_sessions.find_one({"id": session_id, "user_id": user_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@api.post("/ai/generate-course")
async def ai_generate_course_endpoint(
    payload: dict,
    user_id: str = Depends(get_current_user_id),
):
    topic = payload.get("topic", "").strip()
    audience = payload.get("audience", "enterprise professionals")
    if not topic:
        raise HTTPException(status_code=400, detail="Topic required")

    raw = await generate_course_outline(topic, audience)
    # Best-effort JSON extraction
    try:
        # Strip potential markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned.strip())
        return {"outline": parsed, "raw": raw}
    except Exception:
        return {"outline": None, "raw": raw, "error": "Could not parse structured JSON — showing raw response."}


# ==================== DASHBOARD / STATS ====================
@api.get("/dashboard/stats")
async def dashboard_stats(user_id: str = Depends(get_current_user_id)):
    enrollment_count = await db.enrollments.count_documents({"user_id": user_id})
    cert_count = await db.certificates.count_documents({"user_id": user_id})
    completed = await db.enrollments.count_documents({"user_id": user_id, "completed": True})
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    return {
        "enrollments": enrollment_count,
        "certificates": cert_count,
        "completed_courses": completed,
        "xp": user.get("xp", 0),
        "streak_days": user.get("streak_days", 0),
    }


# ==================== REAL-TIME INTELLIGENCE ====================
INTELLIGENCE_CACHE_KEY = "current_briefing"
INTELLIGENCE_CACHE_HOURS = 6  # regenerate at most every 6 hours


def _extract_json(raw: str):
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip().strip("`").strip()
    return json.loads(cleaned)


@api.get("/intelligence/briefing")
async def intelligence_briefing(force: bool = False):
    """Public: latest agentic AI intelligence briefing. Cached for 6h."""
    cached = await db.intelligence_cache.find_one({"key": INTELLIGENCE_CACHE_KEY}, {"_id": 0})
    if cached and not force:
        cached_at = datetime.fromisoformat(cached["cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < INTELLIGENCE_CACHE_HOURS:
            return {**cached["payload"], "cache_age_hours": round(age_hours, 1), "from_cache": True}

    # Fetch catalog slugs to inform the model
    course_docs = await db.courses.find({}, {"_id": 0, "slug": 1}).to_list(200)
    slugs = [c["slug"] for c in course_docs]

    try:
        raw = await generate_intelligence_briefing(slugs)
        parsed = _extract_json(raw)
    except Exception as e:
        logger.exception("Intelligence generation failed")
        if cached:
            return {**cached["payload"], "cache_age_hours": 999, "from_cache": True, "stale": True}
        raise HTTPException(status_code=502, detail=f"Intelligence generation failed: {e}")

    now_iso_str = datetime.now(timezone.utc).isoformat()
    payload = {**parsed, "generated_at": parsed.get("generated_at") or now_iso_str}

    await db.intelligence_cache.update_one(
        {"key": INTELLIGENCE_CACHE_KEY},
        {"$set": {"key": INTELLIGENCE_CACHE_KEY, "payload": payload, "cached_at": now_iso_str}},
        upsert=True,
    )
    return {**payload, "cache_age_hours": 0, "from_cache": False}


@api.get("/intelligence/course/{slug}/refresh")
async def course_refresh(slug: str, user_id: str = Depends(get_current_user_id)):
    """Authenticated: AI-generated curriculum refresh recommendations for a specific course."""
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # cache per course for 12h
    cache_key = f"course_refresh_{slug}"
    cached = await db.intelligence_cache.find_one({"key": cache_key}, {"_id": 0})
    if cached:
        cached_at = datetime.fromisoformat(cached["cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < 12:
            return {**cached["payload"], "cache_age_hours": round(age_hours, 1), "from_cache": True}

    try:
        raw = await generate_course_refresh(course)
        parsed = _extract_json(raw)
    except Exception as e:
        logger.exception("Course refresh generation failed")
        raise HTTPException(status_code=502, detail=f"Course refresh failed: {e}")

    now_iso_str = datetime.now(timezone.utc).isoformat()
    await db.intelligence_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "payload": parsed, "cached_at": now_iso_str}},
        upsert=True,
    )
    return {**parsed, "cache_age_hours": 0, "from_cache": False}


# ==================== STRIPE PAYMENTS ====================
# Fixed pricing packages — amounts defined server-side ONLY to prevent frontend manipulation
PAYMENT_PACKAGES = {
    "practitioner_monthly": {"amount": 29.00, "currency": "usd", "label": "Practitioner — Monthly", "duration_days": 30, "tier": "practitioner"},
    "practitioner_annual": {"amount": 290.00, "currency": "usd", "label": "Practitioner — Annual", "duration_days": 365, "tier": "practitioner"},
    "professional_track": {"amount": 499.00, "currency": "usd", "label": "Professional Track (12 mo)", "duration_days": 365, "tier": "professional"},
    "team_monthly_per_seat": {"amount": 18.00, "currency": "usd", "label": "Team — Per seat / month", "duration_days": 30, "tier": "team"},
}


def _get_stripe(request: Request) -> StripeCheckout:
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


@api.get("/checkout/packages")
async def list_packages():
    """Public — list available packages (frontend uses this to render buttons)."""
    return {"packages": {k: {"label": v["label"], "amount": v["amount"], "currency": v["currency"], "tier": v["tier"]} for k, v in PAYMENT_PACKAGES.items()}}


@api.post("/checkout/session")
async def create_checkout(payload: dict, request: Request, user_id: str = Depends(get_current_user_id)):
    """Create a Stripe checkout session for a fixed package."""
    package_id = payload.get("package_id")
    origin_url = payload.get("origin_url", "").rstrip("/")
    quantity = int(payload.get("quantity") or 1)

    if package_id not in PAYMENT_PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package_id")
    if not origin_url:
        raise HTTPException(status_code=400, detail="origin_url required")

    pkg = PAYMENT_PACKAGES[package_id]
    if package_id == "team_monthly_per_seat":
        # variable seats — enforce 10-100 range
        quantity = max(10, min(100, quantity))
    else:
        quantity = 1

    amount = float(pkg["amount"]) * quantity  # total charge

    success_url = f"{origin_url}/pricing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/pricing"

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    metadata = {
        "user_id": user_id,
        "email": user["email"],
        "package_id": package_id,
        "quantity": str(quantity),
        "tier": pkg["tier"],
    }

    stripe = _get_stripe(request)
    session_req = CheckoutSessionRequest(
        amount=amount,
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    try:
        session = await stripe.create_checkout_session(session_req)
    except Exception as e:
        logger.exception("Stripe session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    # Record transaction as INITIATED
    txn = {
        "session_id": session.session_id,
        "user_id": user_id,
        "email": user["email"],
        "package_id": package_id,
        "tier": pkg["tier"],
        "quantity": quantity,
        "amount": amount,
        "currency": pkg["currency"],
        "payment_status": "initiated",
        "status": "pending",
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(txn)

    return {"url": session.url, "session_id": session.session_id}


@api.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, request: Request, user_id: str = Depends(get_current_user_id)):
    """Poll Stripe for the current status of a session. Updates the transaction record idempotently."""
    txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your transaction")

    # If already terminal, return cached
    if txn.get("payment_status") == "paid" and txn.get("status") == "complete":
        return {"payment_status": "paid", "status": "complete", "package_id": txn["package_id"], "tier": txn["tier"], "amount": txn["amount"], "currency": txn["currency"]}

    stripe = _get_stripe(request)
    try:
        status_resp = await stripe.get_checkout_status(session_id)
    except Exception as e:
        logger.exception("Stripe status fetch failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    updates = {
        "payment_status": status_resp.payment_status,
        "status": status_resp.status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Idempotently grant benefit on first paid transition
    if status_resp.payment_status == "paid" and txn.get("payment_status") != "paid":
        pkg = PAYMENT_PACKAGES.get(txn["package_id"])
        if pkg:
            expires_at = datetime.now(timezone.utc) + timedelta(days=pkg["duration_days"])
            await db.users.update_one(
                {"id": txn["user_id"]},
                {"$set": {
                    "subscription_tier": pkg["tier"],
                    "subscription_expires_at": expires_at.isoformat(),
                    "subscription_package": txn["package_id"],
                }},
            )
            updates["fulfilled_at"] = datetime.now(timezone.utc).isoformat()

    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": updates})

    return {
        "payment_status": status_resp.payment_status,
        "status": status_resp.status,
        "package_id": txn["package_id"],
        "tier": txn["tier"],
        "amount": txn["amount"],
        "currency": txn["currency"],
        "amount_total_cents": status_resp.amount_total,
    }


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks for redundant status updates."""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    stripe = _get_stripe(request)
    try:
        webhook_resp = await stripe.handle_webhook(body, signature)
    except Exception as e:
        logger.exception("Stripe webhook parse failed")
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    if not webhook_resp.session_id:
        return {"received": True}

    txn = await db.payment_transactions.find_one({"session_id": webhook_resp.session_id}, {"_id": 0})
    if not txn:
        return {"received": True, "known": False}

    updates = {
        "payment_status": webhook_resp.payment_status,
        "webhook_event_id": webhook_resp.event_id,
        "webhook_event_type": webhook_resp.event_type,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Idempotent fulfillment
    if webhook_resp.payment_status == "paid" and txn.get("payment_status") != "paid":
        pkg = PAYMENT_PACKAGES.get(txn["package_id"])
        if pkg:
            expires_at = datetime.now(timezone.utc) + timedelta(days=pkg["duration_days"])
            await db.users.update_one(
                {"id": txn["user_id"]},
                {"$set": {
                    "subscription_tier": pkg["tier"],
                    "subscription_expires_at": expires_at.isoformat(),
                    "subscription_package": txn["package_id"],
                }},
            )
            updates["fulfilled_at"] = datetime.now(timezone.utc).isoformat()

    await db.payment_transactions.update_one({"session_id": webhook_resp.session_id}, {"$set": updates})
    return {"received": True, "session_id": webhook_resp.session_id}


# -------------------- register + middleware --------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await seed_database()


@app.on_event("shutdown")
async def on_shutdown():
    mongo_client.close()
