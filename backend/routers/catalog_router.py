"""Catalog + courses + enrollments + lessons."""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user_id
from core import compute_freshness, db, now_iso
from models import Course, CourseSummary, Enrollment, LessonCompleteRequest
from seed_data import CATEGORIES, CERTIFICATION_PATHS, INDUSTRIES

router = APIRouter(prefix="/api", tags=["catalog"])


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
    docs = await db.courses.find(query, {"_id": 0}).to_list(200)
    out = []
    for d in docs:
        score, days = compute_freshness(d)
        out.append(CourseSummary(
            id=d["id"], slug=d["slug"], title=d["title"], subtitle=d["subtitle"],
            category=d["category"], industries=d.get("industries", []),
            difficulty=d["difficulty"], duration_hours=d["duration_hours"],
            thumbnail_url=d["thumbnail_url"], instructor=d["instructor"],
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
