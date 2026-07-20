"""Student progress API.

Read-only endpoints (for the dashboard) plus one write endpoint for
explicit "I've started this module" signals from the frontend. All
state mutations that update `enrollments.progress_pct` still happen
through `POST /api/lessons/complete` — this router only writes
`module_events`.

Endpoints
=========
GET  /api/progress/me                            All enrollments, deep
GET  /api/progress/me/{course_slug}              One course, deep
POST /api/progress/module/start                  Explicit module-start signal
GET  /api/progress/module-events                 Audit log (paginated)
GET  /api/progress/founding-module5              Public milestone counter
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user_id
from core import db
from progress_tracker import (
    MODULE_EVENTS,
    record_module_started,
    summarize_all_enrollments,
    summarize_course_progress,
)

router = APIRouter(prefix="/api/progress", tags=["progress"])


class ModuleStartPayload(BaseModel):
    course_id: str
    module_id: str


@router.get("/me")
async def my_progress(user_id: str = Depends(get_current_user_id)):
    """Every enrollment for the current user, each with per-module progress.

    Ordered by `last_accessed` desc so the dashboard's most-recent-first
    layout works without additional sorting on the client.
    """
    courses = await summarize_all_enrollments(user_id)
    # Aggregate roll-ups useful for a "Learning journey" hero card.
    total_courses = len(courses)
    completed_courses = sum(1 for c in courses if c["completed"])
    in_progress = sum(1 for c in courses if not c["completed"] and c["progress_pct"] > 0)
    not_started = sum(1 for c in courses if c["progress_pct"] == 0)
    overall_pct = round(
        sum(c["progress_pct"] for c in courses) / total_courses, 1
    ) if total_courses else 0.0
    return {
        "totals": {
            "courses": total_courses,
            "completed": completed_courses,
            "in_progress": in_progress,
            "not_started": not_started,
            "overall_progress_pct": overall_pct,
        },
        "courses": courses,
    }


@router.get("/me/{course_slug}")
async def my_course_progress(course_slug: str, user_id: str = Depends(get_current_user_id)):
    """Deep progress for a single course.

    Returns 404 when the course doesn't exist, 400 when the user isn't
    enrolled. All timestamps and per-module status come from `module_events`
    plus `enrollments`.
    """
    course = await db.courses.find_one(
        {"slug": course_slug},
        {"_id": 0, "id": 1, "slug": 1, "title": 1, "modules": 1},
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    enrollment = await db.enrollments.find_one({"user_id": user_id, "course_id": course["id"]})
    if not enrollment:
        raise HTTPException(status_code=400, detail="Not enrolled in this course")
    return await summarize_course_progress(user_id, course, enrollment)


@router.post("/module/start")
async def module_start(payload: ModuleStartPayload, user_id: str = Depends(get_current_user_id)):
    """Explicit "I've opened this module" signal from the frontend.

    Idempotent — a second call for the same (user, course, module)
    returns `{"recorded": false, "already_started": true}` without
    error. Use this to time-stamp module engagement when the learner
    opens a module page BEFORE finishing any lessons (the implicit
    start from the first lesson-completion also writes the same event
    but happens later in the flow).
    """
    enrollment = await db.enrollments.find_one(
        {"user_id": user_id, "course_id": payload.course_id},
        {"_id": 1},
    )
    if not enrollment:
        raise HTTPException(status_code=400, detail="Not enrolled")
    result = await record_module_started(user_id, payload.course_id, payload.module_id)
    return {
        "recorded": result is not None,
        "already_started": result is None,
    }


@router.get("/module-events")
async def my_module_events(
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
):
    """Audit log of the caller's module_started / module_completed events.

    Newest first, capped at 200 rows per request.
    """
    limit = max(1, min(200, limit))
    events = await db[MODULE_EVENTS].find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(limit)
    return {"events": events, "count": len(events)}


@router.get("/founding-module5")
async def founding_module5_public():
    """Public read: how many of the 500 module-5 milestone slots have been
    claimed. Powers a "N of 500 spots claimed" ticker on the marketing
    site — no auth required.
    """
    from founding_member import module5_milestone_stats
    return await module5_milestone_stats()
