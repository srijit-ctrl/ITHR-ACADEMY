"""Quiz + Certificate routes."""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user_id
from core import db, gen_cert_id, now_iso
from models import Certificate, QuizAttempt, QuizSubmitRequest

router = APIRouter(prefix="/api", tags=["assessment"])


@router.post("/courses/{slug}/quiz/submit")
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
            cert_obj = Certificate(
                certificate_id=gen_cert_id(),
                user_id=user_id, user_name=user["full_name"],
                course_id=course["id"], course_title=course["title"],
                score=round(score, 1), verification_url="",
            )
            cert_obj.verification_url = f"/verify/{cert_obj.certificate_id}"
            await db.certificates.insert_one(cert_obj.model_dump())
            await db.enrollments.update_one(
                {"user_id": user_id, "course_id": course["id"]},
                {"$set": {"completed": True, "completed_at": now_iso(), "progress_pct": 100.0}},
            )
            await db.users.update_one({"id": user_id}, {"$inc": {"xp": 500}})
            cert = cert_obj.model_dump()
        else:
            cert = existing_cert
            cert.pop("_id", None)

    return {
        "score": round(score, 1), "passed": passed,
        "correct": correct, "total": total,
        "passing_score": course.get("passing_score", 65),
        "attempt_id": attempt.id, "certificate": cert,
    }


@router.get("/certificates")
async def my_certificates(user_id: str = Depends(get_current_user_id)):
    certs = await db.certificates.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    return certs


@router.get("/certificates/verify/{certificate_id}")
async def verify_certificate(certificate_id: str):
    cert = await db.certificates.find_one({"certificate_id": certificate_id}, {"_id": 0})
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return {"valid": True, "certificate": cert}
