"""Interactive video checkpoint quizzes.

Learner flow:
- GET  /api/lessons/{lesson_id}/video-quiz          -> video_url + checkpoints (no answers)
- POST /api/video-quiz/{checkpoint_id}/answer       -> server-side grading, 3-attempt cap.
  On the 3rd wrong answer the lesson's checkpoint state AND lesson progress are
  reset and the frontend restarts the video from the beginning.

Admin (super_admin) flow:
- GET    /api/admin/video-checkpoints?lesson_id=
- POST   /api/admin/video-checkpoints
- PUT    /api/admin/video-checkpoints/{checkpoint_id}
- DELETE /api/admin/video-checkpoints/{checkpoint_id}
- PUT    /api/admin/lessons/{lesson_id}/video       -> set/clear the lesson video URL
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_super_admin, get_current_user_id
from core import db, now_iso

router = APIRouter(prefix="/api", tags=["video-quiz"])

MAX_ATTEMPTS = 3


def _find_lesson(course: dict, lesson_id: str) -> Optional[dict]:
    for m in course.get("modules", []):
        for l in m.get("lessons", []):
            if l.get("id") == lesson_id:
                return l
    return None


async def _course_by_lesson(lesson_id: str) -> dict:
    course = await db.courses.find_one(
        {"modules.lessons.id": lesson_id}, {"_id": 0, "id": 1, "title": 1, "modules": 1}
    )
    if not course:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return course


# -------------------- Learner endpoints --------------------


@router.get("/lessons/{lesson_id}/video-quiz")
async def get_video_quiz(lesson_id: str, user_id: str = Depends(get_current_user_id)):
    course = await _course_by_lesson(lesson_id)
    lesson = _find_lesson(course, lesson_id)

    checkpoints = await db.video_checkpoints.find(
        {"lesson_id": lesson_id}, {"_id": 0, "correct_index": 0}
    ).sort("timestamp_sec", 1).to_list(50)

    states = await db.checkpoint_attempts.find(
        {"user_id": user_id, "lesson_id": lesson_id}, {"_id": 0}
    ).to_list(100)
    by_cp = {s["checkpoint_id"]: s for s in states}
    for cp in checkpoints:
        s = by_cp.get(cp["id"], {})
        cp["passed"] = s.get("status") == "passed"
        cp["attempts_used"] = s.get("attempts", 0)

    return {"video_url": lesson.get("video_url"), "checkpoints": checkpoints}


class AnswerPayload(BaseModel):
    selected_index: int = Field(ge=0, le=9)


async def _reset_lesson_progress(user_id: str, course_id: str, lesson_id: str) -> None:
    """Full lesson-progress reset after 3 failed checkpoint attempts."""
    course = await db.courses.find_one({"id": course_id}, {"_id": 0, "id": 1, "modules": 1})
    if not course:
        # checkpoint may carry a stale course_id from a re-seed — resolve by lesson membership
        course = await db.courses.find_one({"modules.lessons.id": lesson_id}, {"_id": 0, "id": 1, "modules": 1})
    if not course:
        return
    enrollment = await db.enrollments.find_one({"user_id": user_id, "course_id": course["id"]})
    if not enrollment:
        return
    completed = set(enrollment.get("completed_lessons", []))
    completed.discard(lesson_id)
    total = sum(len(m.get("lessons", [])) for m in course.get("modules", []))
    progress = (len(completed) / total * 100) if total else 0.0
    completed_modules = set(enrollment.get("completed_modules", []))
    for m in course.get("modules", []):
        lesson_ids = {l["id"] for l in m.get("lessons", [])}
        if lesson_id in lesson_ids:
            completed_modules.discard(m["id"])
    await db.enrollments.update_one(
        {"user_id": user_id, "course_id": course["id"]},
        {"$set": {
            "completed_lessons": list(completed),
            "completed_modules": list(completed_modules),
            "progress_pct": round(progress, 1),
            "last_accessed": now_iso(),
        }},
    )


@router.post("/video-quiz/{checkpoint_id}/answer")
async def answer_checkpoint(
    checkpoint_id: str, payload: AnswerPayload, user_id: str = Depends(get_current_user_id)
):
    cp = await db.video_checkpoints.find_one({"id": checkpoint_id}, {"_id": 0})
    if not cp:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    state = await db.checkpoint_attempts.find_one(
        {"user_id": user_id, "checkpoint_id": checkpoint_id}, {"_id": 0}
    )
    if state and state.get("status") == "passed":
        return {"correct": True, "already_passed": True, "attempts_used": state.get("attempts", 1), "attempts_left": 0, "reset": False}

    attempts = (state.get("attempts", 0) if state else 0) + 1
    correct = payload.selected_index == cp["correct_index"]

    if correct:
        await db.checkpoint_attempts.update_one(
            {"user_id": user_id, "checkpoint_id": checkpoint_id},
            {"$set": {
                "user_id": user_id, "checkpoint_id": checkpoint_id,
                "lesson_id": cp["lesson_id"], "course_id": cp["course_id"],
                "attempts": attempts, "status": "passed", "updated_at": now_iso(),
            }},
            upsert=True,
        )
        return {"correct": True, "attempts_used": attempts, "attempts_left": MAX_ATTEMPTS - attempts, "reset": False}

    if attempts >= MAX_ATTEMPTS:
        # 3 strikes: wipe checkpoint state for the whole lesson + reset progress.
        await db.checkpoint_attempts.delete_many({"user_id": user_id, "lesson_id": cp["lesson_id"]})
        await _reset_lesson_progress(user_id, cp["course_id"], cp["lesson_id"])
        return {"correct": False, "attempts_used": attempts, "attempts_left": 0, "reset": True}

    await db.checkpoint_attempts.update_one(
        {"user_id": user_id, "checkpoint_id": checkpoint_id},
        {"$set": {
            "user_id": user_id, "checkpoint_id": checkpoint_id,
            "lesson_id": cp["lesson_id"], "course_id": cp["course_id"],
            "attempts": attempts, "status": "in_progress", "updated_at": now_iso(),
        }},
        upsert=True,
    )
    return {"correct": False, "attempts_used": attempts, "attempts_left": MAX_ATTEMPTS - attempts, "reset": False}


# -------------------- Admin endpoints --------------------


class CheckpointCreate(BaseModel):
    course_id: str
    lesson_id: str
    timestamp_sec: float = Field(ge=0)
    question: str = Field(min_length=3)
    options: List[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0)


class CheckpointUpdate(BaseModel):
    timestamp_sec: Optional[float] = Field(default=None, ge=0)
    question: Optional[str] = None
    options: Optional[List[str]] = None
    correct_index: Optional[int] = Field(default=None, ge=0)


@router.get("/admin/video-checkpoints")
async def admin_list_checkpoints(lesson_id: str, _admin: str = Depends(get_current_super_admin)):
    rows = await db.video_checkpoints.find({"lesson_id": lesson_id}, {"_id": 0}).sort("timestamp_sec", 1).to_list(100)
    return {"rows": rows}


@router.post("/admin/video-checkpoints")
async def admin_create_checkpoint(payload: CheckpointCreate, _admin: str = Depends(get_current_super_admin)):
    if payload.correct_index >= len(payload.options):
        raise HTTPException(status_code=400, detail="correct_index out of range")
    course = await db.courses.find_one({"id": payload.course_id}, {"_id": 0, "modules": 1})
    if not course or not _find_lesson(course, payload.lesson_id):
        raise HTTPException(status_code=404, detail="Course/lesson not found")
    doc = {
        "id": str(uuid.uuid4()),
        "course_id": payload.course_id,
        "lesson_id": payload.lesson_id,
        "timestamp_sec": payload.timestamp_sec,
        "question": payload.question,
        "options": payload.options,
        "correct_index": payload.correct_index,
        "created_at": now_iso(),
    }
    await db.video_checkpoints.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/admin/video-checkpoints/{checkpoint_id}")
async def admin_update_checkpoint(checkpoint_id: str, payload: CheckpointUpdate, _admin: str = Depends(get_current_super_admin)):
    cp = await db.video_checkpoints.find_one({"id": checkpoint_id}, {"_id": 0})
    if not cp:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    options = updates.get("options", cp["options"])
    correct = updates.get("correct_index", cp["correct_index"])
    if correct >= len(options):
        raise HTTPException(status_code=400, detail="correct_index out of range")
    if updates:
        await db.video_checkpoints.update_one({"id": checkpoint_id}, {"$set": updates})
    return {**cp, **updates}


@router.delete("/admin/video-checkpoints/{checkpoint_id}")
async def admin_delete_checkpoint(checkpoint_id: str, _admin: str = Depends(get_current_super_admin)):
    res = await db.video_checkpoints.delete_one({"id": checkpoint_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    await db.checkpoint_attempts.delete_many({"checkpoint_id": checkpoint_id})
    return {"ok": True}


class LessonVideoPayload(BaseModel):
    video_url: Optional[str] = None


@router.put("/admin/lessons/{lesson_id}/video")
async def admin_set_lesson_video(lesson_id: str, payload: LessonVideoPayload, _admin: str = Depends(get_current_super_admin)):
    course = await _course_by_lesson(lesson_id)
    for mi, m in enumerate(course.get("modules", [])):
        for li, l in enumerate(m.get("lessons", [])):
            if l.get("id") == lesson_id:
                await db.courses.update_one(
                    {"id": course["id"]},
                    {"$set": {f"modules.{mi}.lessons.{li}.video_url": payload.video_url}},
                )
                if payload.video_url:
                    await db.lesson_videos.update_one(
                        {"lesson_id": lesson_id},
                        {"$set": {"lesson_id": lesson_id, "video_url": payload.video_url, "updated_at": now_iso()}},
                        upsert=True,
                    )
                else:
                    await db.lesson_videos.delete_one({"lesson_id": lesson_id})
                return {"ok": True, "lesson_id": lesson_id, "video_url": payload.video_url}
    raise HTTPException(status_code=404, detail="Lesson not found")
