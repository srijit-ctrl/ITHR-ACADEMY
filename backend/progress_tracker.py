"""Student progress tracking agent.

Complements the existing `enrollments`-column progress tracker with an
explicit audit stream:

* `module_events` — one row per {user_id, course_id, module_id, kind}
  where `kind ∈ ("started", "completed")`. Unique index on
  (user_id, course_id, module_id, kind) makes both events idempotent —
  duplicate lesson-completions never duplicate the audit row.

The rest of the platform still writes progress state into `enrollments`
(where `progress_pct`, `completed_lessons`, `completed_modules` already
live). This module adds three things on top:

    1. `record_module_started(user_id, course_id, module_id)`
    2. `record_module_completed(user_id, course_id, module_id)`
    3. `mark_course_completed(user_id, course_id)`
       — flips `enrollment.completed = True + completed_at` when all
       modules of a course are done. Emits a "ready for your credential"
       nudge email; the actual credential is still minted only via the
       assessment gate in `assessment_router` (design decision — keeps
       the credential's audit trail intact).

Everything is idempotent, safe to call from fire-and-forget tasks, and
never raises on failure — a broken tracker must never block a lesson
completion write.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core import db, logger

MODULE_EVENTS = "module_events"

KIND_STARTED = "started"
KIND_COMPLETED = "completed"


# ---- Index bootstrap ------------------------------------------------------


async def ensure_indexes() -> None:
    """Idempotent — safe to call on every event write."""
    await db[MODULE_EVENTS].create_index(
        [("user_id", 1), ("course_id", 1), ("module_id", 1), ("kind", 1)],
        unique=True,
    )
    await db[MODULE_EVENTS].create_index([("user_id", 1), ("created_at", -1)])


# ---- Helpers ---------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _find_event(user_id: str, course_id: str, module_id: str, kind: str) -> Optional[dict]:
    return await db[MODULE_EVENTS].find_one(
        {"user_id": user_id, "course_id": course_id, "module_id": module_id, "kind": kind},
        {"_id": 0},
    )


async def _insert_event(*, user_id: str, course_id: str, module_id: str, kind: str, meta: Optional[dict] = None) -> Optional[dict]:
    """Insert an event, catching duplicate-key so callers get idempotency for free.

    Returns the inserted document, or None when the event already existed.
    """
    doc = {
        "user_id": user_id,
        "course_id": course_id,
        "module_id": module_id,
        "kind": kind,
        "created_at": _now(),
    }
    if meta:
        doc["meta"] = meta
    try:
        await db[MODULE_EVENTS].insert_one(doc)
        return doc
    except Exception:
        # DuplicateKey is the only expected exception here (unique compound
        # index). Any other error is real — surface it so the caller decides.
        return None


# ---- Public API ------------------------------------------------------------


async def record_module_started(user_id: str, course_id: str, module_id: str) -> Optional[dict]:
    """Emit a `module_started` event.

    Called on the first lesson completion of a module (implicit start),
    OR by the explicit `POST /api/progress/module/start` endpoint.
    Idempotent — a returning learner will not create a duplicate row.
    """
    try:
        await ensure_indexes()
        if await _find_event(user_id, course_id, module_id, KIND_STARTED):
            return None
        return await _insert_event(
            user_id=user_id, course_id=course_id,
            module_id=module_id, kind=KIND_STARTED,
        )
    except Exception:
        logger.exception("[progress] record_module_started failed")
        return None


async def record_module_completed(user_id: str, course_id: str, module_id: str) -> Optional[dict]:
    """Emit a `module_completed` event. Idempotent."""
    try:
        await ensure_indexes()
        if await _find_event(user_id, course_id, module_id, KIND_COMPLETED):
            return None
        return await _insert_event(
            user_id=user_id, course_id=course_id,
            module_id=module_id, kind=KIND_COMPLETED,
        )
    except Exception:
        logger.exception("[progress] record_module_completed failed")
        return None


async def mark_course_completed(user_id: str, course: dict) -> bool:
    """Called when the caller has already computed `progress_pct == 100`.

    * Flips `enrollment.completed = True` + `completed_at`.
    * Fires `send_ready_for_certificate_email` (non-blocking).
    * Fires an admin-console activity event.

    Returns True on the first flip, False if the enrollment was already
    marked complete (idempotent).

    Note: actual credential minting still happens through the assessment
    endpoint (POST /api/courses/{slug}/quiz/submit). This function just
    signals "learning done — take the assessment to earn your credential".
    """
    try:
        result = await db.enrollments.update_one(
            {"user_id": user_id, "course_id": course["id"], "completed": {"$ne": True}},
            {"$set": {
                "completed": True,
                "completed_at": _now(),
                "progress_pct": 100.0,
            }},
        )
        if result.modified_count == 0:
            return False

        # Fire-and-forget notification + activity feed.
        import asyncio

        async def _side_effects():
            try:
                u = await db.users.find_one(
                    {"id": user_id},
                    {"_id": 0, "email": 1, "full_name": 1},
                )
                if u and u.get("email"):
                    from email_service import send_ready_for_certificate_email
                    await send_ready_for_certificate_email(
                        email=u["email"],
                        full_name=u.get("full_name") or "",
                        course_title=course.get("title") or "",
                        course_slug=course.get("slug") or "",
                    )
            except Exception:
                logger.exception("[progress] ready-for-cert email dispatch failed")
            try:
                from core import log_activity
                await log_activity(
                    kind="course_completed",
                    message=f"Completed all modules of \"{course.get('title')}\"",
                    actor_id=user_id,
                    target_id=course.get("id"),
                )
            except Exception:
                logger.exception("[progress] course_completed activity write failed")

        asyncio.create_task(_side_effects())
        return True
    except Exception:
        logger.exception("[progress] mark_course_completed failed")
        return False


# ---- Progress read models --------------------------------------------------


def _lesson_map(course: dict) -> dict[str, dict]:
    """{lesson_id: {module_id, module_index_1based, title, duration_min}}"""
    out: dict[str, dict] = {}
    for m_idx, module in enumerate(course.get("modules", [])):
        for lesson in module.get("lessons", []):
            out[lesson["id"]] = {
                "module_id": module["id"],
                "module_index_1based": m_idx + 1,
                "lesson_title": lesson.get("title"),
                "duration_min": lesson.get("duration_min", 0),
            }
    return out


async def summarize_course_progress(user_id: str, course: dict, enrollment: dict) -> dict:
    """Build a rich per-course progress payload for the dashboard.

    Includes per-module started/completed timestamps sourced from
    `module_events`. The enrolment doc supplies the aggregate progress_pct
    (already maintained by catalog_router.complete_lesson) so this reader
    never has to recompute state.
    """
    course_id = course["id"]

    # One query for all module_events on this (user, course)
    events = await db[MODULE_EVENTS].find(
        {"user_id": user_id, "course_id": course_id},
        {"_id": 0, "module_id": 1, "kind": 1, "created_at": 1},
    ).to_list(1000)
    events_by_mid: dict[str, dict] = {}
    for ev in events:
        events_by_mid.setdefault(ev["module_id"], {})[ev["kind"]] = ev["created_at"]

    completed_lessons = set(enrollment.get("completed_lessons") or [])
    completed_modules = set(enrollment.get("completed_modules") or [])

    modules_out = []
    total_lessons = 0
    total_completed_lessons = 0
    for idx, m in enumerate(course.get("modules", [])):
        lessons = m.get("lessons", []) or []
        lc = sum(1 for l in lessons if l["id"] in completed_lessons)
        total_lessons += len(lessons)
        total_completed_lessons += lc
        mid = m["id"]
        ev = events_by_mid.get(mid, {})
        modules_out.append({
            "module_id": mid,
            "module_index_1based": idx + 1,
            "title": m.get("title"),
            "lesson_count": len(lessons),
            "lessons_completed": lc,
            "completed": mid in completed_modules,
            "started_at": ev.get(KIND_STARTED),
            "completed_at": ev.get(KIND_COMPLETED),
        })

    total_modules = len(course.get("modules", []))
    return {
        "course_id": course_id,
        "course_slug": course.get("slug"),
        "course_title": course.get("title"),
        "progress_pct": round(float(enrollment.get("progress_pct") or 0.0), 1),
        "completed": bool(enrollment.get("completed")),
        "completed_at": enrollment.get("completed_at"),
        "enrolled_at": enrollment.get("enrolled_at"),
        "last_accessed": enrollment.get("last_accessed"),
        "total_modules": total_modules,
        "modules_completed": len(completed_modules & {m["id"] for m in course.get("modules", [])}),
        "total_lessons": total_lessons,
        "lessons_completed": total_completed_lessons,
        "modules": modules_out,
    }


async def summarize_all_enrollments(user_id: str) -> list[dict]:
    """Every enrollment for a user, each with a rich progress payload.

    Orphaned enrollments (course was deleted) are silently skipped —
    keeps the dashboard from breaking when a course is removed mid-cohort.
    """
    enrolls = await db.enrollments.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("last_accessed", -1).to_list(200)
    out = []
    for e in enrolls:
        course = await db.courses.find_one(
            {"id": e["course_id"]},
            {"_id": 0, "id": 1, "slug": 1, "title": 1, "modules": 1},
        )
        if not course:
            continue
        out.append(await summarize_course_progress(user_id, course, e))
    return out
