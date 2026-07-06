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
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from auth import get_current_user_id
from core import db, gen_cert_id, now_iso
from models import Certificate, QuizAttempt, QuizSubmitRequest

router = APIRouter(prefix="/api", tags=["assessment"])


DEFAULT_QUESTIONS_PER_ATTEMPT = 15


ADAPTIVE_MIXES = {
    "onboarding": {"beginner": 0.60, "intermediate": 0.30, "advanced": 0.10},
    "escalate":   {"beginner": 0.20, "intermediate": 0.50, "advanced": 0.30},
    "reinforce":  {"beginner": 0.55, "intermediate": 0.35, "advanced": 0.10},
}


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


async def _resolve_adaptive_mode(user_id: str, course_id: str) -> str:
    history = await db.quiz_attempts.find(
        {"user_id": user_id, "course_id": course_id},
        {"_id": 0, "passed": 1},
    ).sort("attempted_at", -1).to_list(5)
    if not history:
        return "onboarding"
    return "escalate" if history[0].get("passed") else "reinforce"


def _bucket_bank(bank: list[dict], rng: random.Random) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {"beginner": [], "intermediate": [], "advanced": []}
    for q in bank:
        d = (q.get("difficulty") or "intermediate").lower()
        if d not in buckets:
            d = "intermediate"
        buckets[d].append(q)
    for k in buckets:
        rng.shuffle(buckets[k])
    return buckets


def _draw_adaptive(bank: list[dict], count: int, mode: str, rng: random.Random) -> list[dict]:
    mix = ADAPTIVE_MIXES[mode]
    buckets = _bucket_bank(bank, rng)
    picked: list[dict] = []
    for level, weight in mix.items():
        target = round(count * weight)
        picked.extend(buckets[level][:target])
        buckets[level] = buckets[level][target:]
    leftover = buckets["intermediate"] + buckets["beginner"] + buckets["advanced"]
    rng.shuffle(leftover)
    while len(picked) < count and leftover:
        picked.append(leftover.pop())
    rng.shuffle(picked)
    return picked


def _draw_random(bank: list[dict], count: int, rng: random.Random) -> list[dict]:
    pool = list(bank)
    rng.shuffle(pool)
    return pool[: min(count, len(pool))]


def _client_view(shuffled: list[dict]) -> list[dict]:
    return [
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


@router.get("/courses/{slug}/assessment/session")
async def start_assessment_session(
    slug: str,
    count: int = Query(DEFAULT_QUESTIONS_PER_ATTEMPT, ge=5, le=40),
    seed: Optional[int] = None,
    adaptive: bool = Query(True, description="If true, weight question selection by learner's prior attempts"),
    user_id: str = Depends(get_current_user_id),
):
    """Return a randomized paper for this attempt.

    Adaptive mode ratios (beginner / intermediate / advanced):
    - onboarding: 60 / 30 / 10 (learner has no prior attempts)
    - escalate:   20 / 50 / 30 (learner passed most recent attempt)
    - reinforce:  55 / 35 / 10 (learner failed most recent attempt)
    """
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    bank = course.get("quiz", [])
    if not bank:
        raise HTTPException(status_code=400, detail="No assessment available for this course")

    rng = random.Random(seed) if seed is not None else random.SystemRandom()  # nosec B311 — non-security question shuffling. Seeded case only for reproducible test papers.

    if adaptive:
        mode = await _resolve_adaptive_mode(user_id, course["id"])
        picked = _draw_adaptive(bank, count, mode, rng)
    else:
        mode = "random"
        picked = _draw_random(bank, count, rng)

    shuffled = [_shuffle_options(q, rng) for q in picked]
    client_view = _client_view(shuffled)

    return {
        "course_id": course["id"],
        "slug": slug,
        "passing_score": course.get("passing_score", 65),
        "duration_minutes": 30,
        "total": len(client_view),
        "bank_size": len(bank),
        "adaptive_mode": mode,
        "questions": client_view,
    }


def _grade_answers(
    questions: list[dict],
    answers: dict,
    perms: Optional[dict],
) -> tuple[int, int]:
    """Grade an answers dict; returns (correct_count, total_graded)."""
    by_id = {q["id"]: q for q in questions}
    graded = len([q for q in questions if q["id"] in answers])
    total = graded if graded else len(questions)
    correct = 0
    for qid, submitted in answers.items():
        q = by_id.get(qid)
        if not q:
            continue
        submitted_indices = list(submitted or [])
        if perms and qid in perms:
            perm = perms[qid]
            submitted_indices = [perm[i] for i in submitted_indices if 0 <= i < len(perm)]
        if sorted(submitted_indices) == sorted(q["correct"]):
            correct += 1
    return correct, total


async def _issue_certificate_if_new(
    user_id: str, course: dict, score: float,
) -> Optional[dict]:
    """Create a Certificate on first pass; return the cert dict (new or existing)."""
    existing = await db.certificates.find_one({"user_id": user_id, "course_id": course["id"]})
    if existing:
        existing.pop("_id", None)
        return existing
    user = await db.users.find_one({"id": user_id})
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
    # Fire the cert-earned email — fire-and-forget so the API path stays fast.
    try:
        import asyncio as _asyncio
        from email_service import send_certificate_email
        _asyncio.create_task(send_certificate_email(
            email=user["email"], full_name=user["full_name"],
            course_title=course["title"], certificate_id=cert_obj.certificate_id,
            score=int(round(score, 0)),
        ))
    except Exception:
        # never block cert issuance on email
        pass

    # Live activity feed
    try:
        import asyncio as _asyncio
        from core import log_activity
        _asyncio.create_task(log_activity(
            kind="certificate",
            message=f'{user["full_name"]} earned "{course["title"]}" ({round(score, 0):.0f}%)',
            actor_id=user_id, actor_name=user["full_name"],
            target={"certificate_id": cert_obj.certificate_id, "course_slug": course.get("slug")},
        ))
    except Exception:
        pass
    # If this is the founder's free-cert course, flag it as claimed so future
    # certs on other courses are billable as usual.
    try:
        from founding_member import can_claim_free_cert, mark_cert_claimed
        if can_claim_free_cert(user, course["id"]):
            await mark_cert_claimed(user_id)
    except Exception:
        pass
    return cert_obj.model_dump()


@router.post("/courses/{slug}/quiz/submit")
async def submit_quiz(
    slug: str,
    payload: QuizSubmitRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Grade an attempt.

    `payload.answers` shape: { question_id: [selected_indices] }
    Clients using the /session endpoint pass `answers['__perm__']` = {qid: [orig_indices]}
    so we can translate shuffled indices back to course-canonical positions.
    """
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    questions = course.get("quiz", [])
    if not questions:
        raise HTTPException(status_code=400, detail="No assessment available for this course")

    perms = payload.answers.pop("__perm__", None) if isinstance(payload.answers, dict) else None
    correct, total = _grade_answers(questions, payload.answers, perms)

    score = (correct / total * 100) if total else 0
    passing = course.get("passing_score", 65)
    passed = score >= passing

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

    cert = await _issue_certificate_if_new(user_id, course, score) if passed else None

    return {
        "score": round(score, 1),
        "passed": passed,
        "correct": correct,
        "total": total,
        "passing_score": passing,
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
async def verify_certificate(certificate_id: str, request: Request):
    cert = await db.certificates.find_one(
        {"certificate_id": certificate_id}, {"_id": 0}
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # ---- Impression tracking + holder alert -----------------------------
    # A single verifier IP on a given day counts as one impression, no matter
    # how many times they refresh. The email alert is throttled separately
    # (once per 6h). The sample cert is fully excluded from both.
    try:
        import asyncio as _asyncio
        import hashlib
        from datetime import datetime, timedelta, timezone
        from email_service import send_credential_verification_alert

        if certificate_id != "SAMPLE-ITHR-2026-001":
            now_dt = datetime.now(timezone.utc)
            client_ip = (request.client.host if request.client else "unknown") or "unknown"
            day = now_dt.strftime("%Y-%m-%d")
            impression_key = hashlib.sha256(f"{certificate_id}|{day}|{client_ip}".encode()).hexdigest()

            # Idempotent insert — unique on impression_key so refreshes/rescans
            # by the same verifier on the same day only count once.
            try:
                await db.verify_impressions.insert_one({
                    "impression_key": impression_key,
                    "certificate_id": certificate_id,
                    "user_id": cert["user_id"],
                    "day": day,
                    "verified_at": now_dt.isoformat(),
                    "ip_hash_short": hashlib.sha256(client_ip.encode()).hexdigest()[:12],
                })
                is_new_impression = True
            except Exception:
                # Duplicate key on the unique index — this verifier already
                # counted today. Not an error.
                is_new_impression = False

            # Send holder-alert only on new impression + past 6h cooldown
            cutoff = (now_dt - timedelta(hours=6)).isoformat()
            last_alert = cert.get("last_verify_alert_at", "")
            if is_new_impression and last_alert < cutoff:
                holder = await db.users.find_one({"id": cert["user_id"]}, {"_id": 0, "email": 1, "full_name": 1})
                if holder:
                    await db.certificates.update_one(
                        {"certificate_id": certificate_id},
                        {"$set": {"last_verify_alert_at": now_dt.isoformat()}},
                    )
                    _asyncio.create_task(send_credential_verification_alert(
                        email=holder["email"], full_name=holder.get("full_name") or "",
                        certificate_id=certificate_id, course_title=cert.get("course_title", ""),
                        verifier_ip_hash=impression_key,
                        verified_at=now_dt.isoformat()[:19].replace("T", " "),
                    ))
    except Exception:
        # Never fail a public verify because of tracking / email hiccups.
        pass

    return {"valid": True, "certificate": cert}


@router.get("/certificates/impressions")
async def credential_impressions(user_id: str = Depends(get_current_user_id)):
    """Return credential-verification impression counts for the caller.

    Response shape:
        {
          "total_all_time": int,
          "total_last_30d": int,
          "total_this_month": int,
          "by_certificate": [
            {"certificate_id": str, "course_title": str, "impressions": int}
          ]
        }
    """
    from datetime import datetime, timedelta, timezone

    now_dt = datetime.now(timezone.utc)
    since_30d = (now_dt - timedelta(days=30)).isoformat()
    month_start = now_dt.replace(day=1).strftime("%Y-%m-%d")

    total_all_time = await db.verify_impressions.count_documents({"user_id": user_id})
    total_last_30d = await db.verify_impressions.count_documents({
        "user_id": user_id, "verified_at": {"$gte": since_30d},
    })
    total_this_month = await db.verify_impressions.count_documents({
        "user_id": user_id, "day": {"$gte": month_start},
    })

    # Per-cert breakdown (only user's own certs)
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$certificate_id", "impressions": {"$sum": 1}}},
        {"$sort": {"impressions": -1}},
    ]
    per_cert_raw = await db.verify_impressions.aggregate(pipeline).to_list(50)
    cert_ids = [r["_id"] for r in per_cert_raw]
    cert_docs = await db.certificates.find(
        {"certificate_id": {"$in": cert_ids}},
        {"_id": 0, "certificate_id": 1, "course_title": 1},
    ).to_list(50) if cert_ids else []
    title_by_id = {c["certificate_id"]: c.get("course_title", "") for c in cert_docs}

    by_certificate = [
        {
            "certificate_id": r["_id"],
            "course_title": title_by_id.get(r["_id"], "(unknown)"),
            "impressions": r["impressions"],
        }
        for r in per_cert_raw
    ]

    return {
        "total_all_time": total_all_time,
        "total_last_30d": total_last_30d,
        "total_this_month": total_this_month,
        "by_certificate": by_certificate,
    }


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


@router.get("/certificates/{certificate_id}/pdf")
async def certificate_pdf(certificate_id: str):
    """Server-rendered, print-ready PDF of a certificate.

    Uses WeasyPrint to render an A4-landscape HTML template with the ITHR seal,
    gold accents, and embedded QR (base64 SVG). Public — anyone with the ID
    can download since the credential is already publicly verifiable.
    """
    cert = await db.certificates.find_one(
        {"certificate_id": certificate_id}, {"_id": 0}
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    import base64
    import os

    from weasyprint import HTML

    # Generate QR SVG inline
    base_url = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
    verify_url = f"{base_url}/verify/{certificate_id}" if base_url else f"/verify/{certificate_id}"
    qr_buf = io.BytesIO()
    segno.make(verify_url, error="H").save(qr_buf, kind="svg", scale=6, dark="#16335E", light="#ffffff", border=1, xmldecl=False)
    qr_b64 = base64.b64encode(qr_buf.getvalue()).decode("ascii")

    issued_raw = cert.get("issued_at", "")
    try:
        issued = datetime.fromisoformat(issued_raw.replace("Z", "+00:00")).strftime("%B %d, %Y")
    except Exception:
        issued = issued_raw[:10]

    html = _CERT_PDF_TEMPLATE.format(
        holder=_html_escape(cert["user_name"]),
        course=_html_escape(cert["course_title"]),
        score=cert.get("score", 0),
        cert_id=_html_escape(cert["certificate_id"]),
        issued=issued,
        qr_b64=qr_b64,
        verify_url=_html_escape(verify_url),
    )

    pdf_buf = io.BytesIO()
    HTML(string=html).write_pdf(pdf_buf)
    return Response(
        content=pdf_buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ITHR-{certificate_id}.pdf"'},
    )


def _html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_CERT_PDF_TEMPLATE = r"""
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  /* ITHR Brand palette lock (Iter 24) — Teal #00A78B + Navy #16335E + Gold #C5A253 */
  @page {{ size: A4 landscape; margin: 0; }}
  body {{ margin: 0; font-family: 'Calibri', 'Tahoma', 'Helvetica', Arial, sans-serif; color: #16335E; }}
  .sheet {{
    width: 297mm; height: 210mm; padding: 18mm 22mm;
    box-sizing: border-box; position: relative;
    background: #ffffff;
    background-image:
      linear-gradient(0deg, transparent 24%, rgba(0,167,139,0.025) 25%, rgba(0,167,139,0.025) 26%, transparent 27%, transparent 74%, rgba(0,167,139,0.025) 75%, rgba(0,167,139,0.025) 76%, transparent 77%);
    background-size: 100% 60px;
  }}
  /* Ornamental gold borders — kept for ceremonial contrast */
  .sheet::before, .sheet::after {{
    content: ''; position: absolute; left: 10mm; right: 10mm; height: 3mm;
    background: linear-gradient(90deg, transparent, #C5A253 20%, #C5A253 80%, transparent);
  }}
  .sheet::before {{ top: 8mm; }}
  .sheet::after  {{ bottom: 8mm; }}

  /* Inner double rule — navy outer, gold inner */
  .inner-rule {{
    position: absolute; inset: 14mm 18mm; border: 0.6mm solid #C5A253;
    box-shadow: inset 0 0 0 1mm #ffffff, inset 0 0 0 1.4mm #16335E;
    pointer-events: none;
  }}

  .header {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 8mm; position: relative;
  }}
  .brand-lockup {{ display: flex; align-items: center; gap: 6mm; }}
  .seal {{
    width: 28mm; height: 28mm; border-radius: 50%;
    background: radial-gradient(circle at 30% 25%, #21467a 0%, #16335E 100%);
    box-shadow: 0 0 0 1mm #C5A253, 0 0 0 1.6mm #ffffff, 0 0 0 1.9mm #C5A253;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    color: #ffffff; text-align: center;
  }}
  .seal-est   {{ font-size: 6pt; letter-spacing: 2pt; color: #C5A253; text-transform: uppercase; }}
  .seal-mark  {{ font-family: 'Georgia', serif; font-size: 14pt; letter-spacing: 1pt; margin: 1mm 0; }}
  .seal-tag   {{ font-size: 5pt; letter-spacing: 1.5pt; color: rgba(255,255,255,0.85); text-transform: uppercase; }}
  .seal-line  {{ width: 8mm; height: 0.3mm; background: #C5A253; margin: 1mm 0; }}

  .brand-name    {{ font-family: 'Georgia', serif; font-size: 22pt; letter-spacing: -0.5pt; margin: 0; color: #16335E; }}
  .brand-name .accent {{ color: #00A78B; }}
  .brand-tag     {{ font-size: 8pt; letter-spacing: 3pt; color: #4a5768; text-transform: uppercase; margin-top: 1.5mm; }}

  .award-block  {{ text-align: right; }}
  .award-title  {{ font-size: 8pt; letter-spacing: 3pt; color: #C5A253; text-transform: uppercase; }}
  .award-num    {{ font-family: 'Georgia', serif; font-size: 18pt; color: #16335E; }}

  .body {{ text-align: center; margin-top: 6mm; position: relative; }}
  .presents  {{ font-size: 9pt; letter-spacing: 3pt; color: #4a5768; text-transform: uppercase; }}
  .holder    {{ font-family: 'Georgia', serif; font-size: 48pt; letter-spacing: -1pt; margin: 4mm 0; color: #16335E; }}
  .completed {{ font-size: 9pt; letter-spacing: 3pt; color: #4a5768; text-transform: uppercase; margin-top: 2mm; }}
  .course    {{ font-family: 'Georgia', serif; font-style: italic; font-size: 22pt; margin: 4mm 0 3mm; color: #00A78B; }}
  .score     {{ font-size: 11pt; color: #4a5768; }}
  .score b   {{ color: #16335E; }}

  .divider-gold {{
    width: 40mm; height: 0.4mm;
    background: linear-gradient(90deg, transparent, #C5A253, transparent);
    margin: 6mm auto;
  }}

  .footer {{
    display: flex; justify-content: space-between; align-items: flex-end;
    margin-top: 6mm; position: relative;
  }}
  .fact {{ font-size: 8pt; }}
  .fact-label {{ letter-spacing: 2pt; color: #7d8ba0; text-transform: uppercase; font-size: 6.5pt; margin-bottom: 1mm; }}
  .fact-value {{ font-family: 'Courier', monospace; color: #16335E; }}

  .qr-frame {{
    padding: 2mm; border: 0.5mm solid #C5A253; background: #ffffff;
  }}
  .qr-frame img {{ width: 24mm; height: 24mm; display: block; }}

  .signature-line {{ border-top: 0.3mm solid #16335E; padding-top: 1.5mm; width: 55mm; text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #16335E; }}
  .signature-role {{ font-size: 7pt; letter-spacing: 2pt; color: #7d8ba0; text-transform: uppercase; margin-top: 1mm; }}
</style></head>
<body>
  <div class="sheet">
    <div class="inner-rule"></div>

    <div class="header">
      <div class="brand-lockup">
        <div class="seal">
          <div class="seal-est">Est. 2026</div>
          <div class="seal-mark">ITHR</div>
          <div class="seal-line"></div>
          <div class="seal-tag">Academy</div>
        </div>
        <div>
          <div class="brand-name">ITHR <span class="accent">Academy</span></div>
          <div class="brand-tag">Enterprise Agentic AI · Independent Issuer</div>
        </div>
      </div>
      <div class="award-block">
        <div class="award-title">Certificate</div>
        <div class="award-num">of Achievement</div>
      </div>
    </div>

    <div class="body">
      <div class="presents">This is to certify that</div>
      <div class="holder">{holder}</div>
      <div class="completed">has successfully completed the program</div>
      <div class="course">{course}</div>
      <div class="score">with a score of <b>{score}%</b></div>
      <div class="divider-gold"></div>
    </div>

    <div class="footer">
      <div>
        <div class="signature-line">Reyes Al-Fahad</div>
        <div class="signature-role">Chief Learning Officer · ITHR</div>
      </div>

      <div style="text-align:center;">
        <div class="fact">
          <div class="fact-label">Credential ID</div>
          <div class="fact-value">{cert_id}</div>
        </div>
        <div class="fact" style="margin-top:3mm;">
          <div class="fact-label">Issued</div>
          <div class="fact-value">{issued}</div>
        </div>
        <div style="font-size:7pt;color:#7d8ba0;margin-top:3mm;">Verify at {verify_url}</div>
      </div>

      <div class="qr-frame">
        <img src="data:image/svg+xml;base64,{qr_b64}" alt="QR" />
      </div>
    </div>
  </div>
</body></html>
"""
