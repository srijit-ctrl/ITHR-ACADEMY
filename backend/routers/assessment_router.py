"""Quiz + Certificate routes.

Enhancements:
- `/api/courses/{slug}/assessment/session` returns a randomized subset of the
  course's question bank (with shuffled option order), so no two attempts see
  the exact same paper. Server does NOT persist the session — the client sends
  question ids + option indices back to `/submit`.
- Attempt endpoint lists a learner's past attempts.
- Certificate QR endpoint returns an SVG QR pointing to /verify/{cert_id}.
"""
from __future__ import annotations

import io
import random
from datetime import datetime, timezone
from typing import Optional

import segno
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from auth import get_current_user_id
from core import db, gen_cert_id, now_iso
from models import Certificate, QuizAttempt, QuizSubmitRequest

router = APIRouter(prefix="/api", tags=["assessment"])


DEFAULT_QUESTIONS_PER_ATTEMPT = 15


def _shuffle_options(q: dict, rng: random.Random) -> dict:
    """Return a copy of q with options shuffled and correct indices remapped."""
    idx = list(range(len(q["options"])))
    rng.shuffle(idx)
    remap = {orig: new for new, orig in enumerate(idx)}
    return {
        **q,
        "options": [q["options"][i] for i in idx],
        "correct": sorted(remap[c] for c in q["correct"]),
        "_option_permutation": idx,  # so submit can decode against course truth
    }


@router.get("/courses/{slug}/assessment/session")
async def start_assessment_session(
    slug: str,
    count: int = Query(DEFAULT_QUESTIONS_PER_ATTEMPT, ge=5, le=40),
    seed: Optional[int] = None,
    user_id: str = Depends(get_current_user_id),
):
    """Return a randomized paper for this attempt.

    Client uses the returned question IDs + option indices as-is; when
    submitting we look up the original course quiz and decode the option
    permutation via the shipped map.
    """
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    bank = course.get("quiz", [])
    if not bank:
        raise HTTPException(status_code=400, detail="No assessment available for this course")

    rng = random.Random(seed or random.SystemRandom().randint(0, 2**32 - 1))
    pool = list(bank)
    rng.shuffle(pool)
    picked = pool[: min(count, len(pool))]
    shuffled = [_shuffle_options(q, rng) for q in picked]

    # Do NOT reveal `correct` or `explanation` to client; keep permutation for submit-side mapping.
    client_view = [
        {
            "id": q["id"],
            "question": q["question"],
            "type": q.get("type", "mcq"),
            "options": q["options"],
            "difficulty": q.get("difficulty", "intermediate"),
            "permutation": q["_option_permutation"],
        }
        for q in shuffled
    ]

    return {
        "course_id": course["id"],
        "slug": slug,
        "passing_score": course.get("passing_score", 65),
        "duration_minutes": 30,
        "total": len(client_view),
        "bank_size": len(bank),
        "questions": client_view,
    }


@router.post("/courses/{slug}/quiz/submit")
async def submit_quiz(
    slug: str,
    payload: QuizSubmitRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Grade an attempt.

    `payload.answers` shape: { question_id: [selected_indices] }
    If `payload` includes `permutations` in `answers` metadata? — instead,
    clients using the /session endpoint must pass a `permutations` map on the
    request as `{qid: [orig_indices]}` via `answers['__perm__']` — a compact
    convention. Otherwise we assume indices are already course-canonical.
    """
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    questions = course.get("quiz", [])
    if not questions:
        raise HTTPException(status_code=400, detail="No assessment available for this course")

    perms = payload.answers.pop("__perm__", None) if isinstance(payload.answers, dict) else None

    by_id = {q["id"]: q for q in questions}
    correct = 0
    graded = len([q for q in questions if q["id"] in payload.answers])
    total = graded if graded else len(questions)

    for qid, submitted in payload.answers.items():
        q = by_id.get(qid)
        if not q:
            continue
        submitted_indices = list(submitted or [])
        if perms and qid in perms:
            # translate shuffled indices back to original
            perm = perms[qid]
            submitted_indices = [perm[i] for i in submitted_indices if 0 <= i < len(perm)]
        if sorted(submitted_indices) == sorted(q["correct"]):
            correct += 1

    score = (correct / total * 100) if total else 0
    passed = score >= course.get("passing_score", 65)

    attempt = QuizAttempt(
        user_id=user_id,
        course_id=course["id"],
        score=round(score, 1),
        passed=passed,
        total_questions=total,
        correct_count=correct,
        duration_seconds=payload.duration_seconds,
        answers=payload.answers,
    )
    await db.quiz_attempts.insert_one(attempt.model_dump())

    cert = None
    if passed:
        user = await db.users.find_one({"id": user_id})
        existing_cert = await db.certificates.find_one(
            {"user_id": user_id, "course_id": course["id"]}
        )
        if not existing_cert:
            cert_obj = Certificate(
                certificate_id=gen_cert_id(),
                user_id=user_id,
                user_name=user["full_name"],
                course_id=course["id"],
                course_title=course["title"],
                score=round(score, 1),
                verification_url="",
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
        "score": round(score, 1),
        "passed": passed,
        "correct": correct,
        "total": total,
        "passing_score": course.get("passing_score", 65),
        "attempt_id": attempt.id,
        "certificate": cert,
    }


@router.get("/courses/{slug}/attempts")
async def my_attempts(slug: str, user_id: str = Depends(get_current_user_id)):
    course = await db.courses.find_one({"slug": slug}, {"_id": 0, "id": 1})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    attempts = await db.quiz_attempts.find(
        {"user_id": user_id, "course_id": course["id"]},
        {"_id": 0, "answers": 0},
    ).sort("attempted_at", -1).to_list(50)
    return attempts


@router.get("/certificates")
async def my_certificates(user_id: str = Depends(get_current_user_id)):
    certs = await db.certificates.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    return certs


@router.get("/certificates/verify/{certificate_id}")
async def verify_certificate(certificate_id: str):
    cert = await db.certificates.find_one(
        {"certificate_id": certificate_id}, {"_id": 0}
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return {"valid": True, "certificate": cert}


@router.get("/certificates/{certificate_id}/qr.svg")
async def certificate_qr(certificate_id: str):
    """Return a scannable SVG QR that opens the public verification page."""
    cert = await db.certificates.find_one(
        {"certificate_id": certificate_id}, {"_id": 0}
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    import os
    base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
    verify_url = f"{base}/verify/{certificate_id}" if base else f"/verify/{certificate_id}"

    qr = segno.make(verify_url, error="H")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=6, dark="#0d1321", light="#ffffff", border=2, xmldecl=False)
    return Response(content=buf.getvalue(), media_type="image/svg+xml")
