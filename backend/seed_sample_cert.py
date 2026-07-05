"""Idempotent sample-certificate seed.

Ensures a demonstration certificate exists so the /certifications page's
"See a sample" CTA can link to a stable, publicly-verifiable cert without
requiring a real learner journey.

The sample cert:
- Uses a fixed certificate_id: "SAMPLE-ITHR-2026-001"
- Holder: "Sample Learner"
- Course: "Agentic AI Foundations"
- Score: 92
"""
from core import db, logger, now_iso

SAMPLE_CERT_ID = "SAMPLE-ITHR-2026-001"


async def seed_sample_certificate() -> None:
    existing = await db.certificates.find_one({"certificate_id": SAMPLE_CERT_ID}, {"_id": 0, "certificate_id": 1})
    if existing:
        return
    # Look up the Foundations course id so the cert references a real course.
    course = await db.courses.find_one(
        {"slug": "agentic-ai-foundations"},
        {"_id": 0, "id": 1, "title": 1},
    )
    if not course:
        logger.warning("Sample cert: 'agentic-ai-foundations' course not found — skipping.")
        return
    cert = {
        "id": "sample-cert-record",
        "certificate_id": SAMPLE_CERT_ID,
        "user_id": "sample-learner-user",
        "user_name": "Sample Learner",
        "course_id": course["id"],
        "course_title": course.get("title", "Agentic AI Foundations"),
        "score": 92,
        "issued_at": now_iso(),
        "verification_url": f"/verify/{SAMPLE_CERT_ID}",
    }
    try:
        await db.certificates.insert_one(cert)
        logger.info(f"Sample certificate seeded: {SAMPLE_CERT_ID}")
    except Exception:
        logger.exception("Sample cert seed failed (non-fatal)")
