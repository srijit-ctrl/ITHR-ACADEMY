"""Enterprise Agentic AI Academy — thin bootstrap. Route handlers live in routers/*."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core import db, logger, mongo_client, now_iso
from routers import (
    admin_dashboard_router, admin_router, assessment_router, auth_router, catalog_router, checkout_router,
    dashboard_router, demo_router, digest_router, enterprise_router, intelligence_router,
    mentor_router, passport_router, password_reset_router, paths_router,
    recommendation_router, trust_router, tutor_router, voice_router, podcast_router,
    admin_control_router, traffic_router, video_quiz_router, referral_router, security_router, command_center_router,
)
from seed_data import CATALOG_COURSES, build_full_course


app = FastAPI(title="Enterprise Agentic AI Academy API", version="1.1.0")


# -------------------- Kubernetes liveness/readiness probe --------------------
# Kubernetes hits `/health` (no /api prefix) directly on the container. This must
# stay lightweight — no DB calls — so probes never flap on transient Mongo latency.
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# -------------------- Seeding --------------------
async def seed_database():
    """Seed catalog + full courses. Idempotent (upserts full courses to replace metadata stubs)."""
    from seed_more_courses import (
        build_ai_governance_course, build_multi_agent_course,
        build_prompt_engineering_course, build_rag_course,
    )
    from seed_industry_courses import (
        build_banking_course, build_government_course, build_healthcare_course,
        build_manufacturing_course, build_retail_course,
    )
    from seed_hr_courses import build_talent_acquisition_course

    full_builders = [
        build_full_course,
        build_prompt_engineering_course,
        build_rag_course,
        build_multi_agent_course,
        build_ai_governance_course,
        build_banking_course,
        build_healthcare_course,
        build_manufacturing_course,
        build_retail_course,
        build_government_course,
        build_talent_acquisition_course,
    ]
    full_slugs = set()

    for builder in full_builders:
        full = builder()
        doc = full.model_dump()
        doc["has_full_content"] = True
        # SHA-256 truncated — used as a deterministic seed for the reviewed-date jitter.
        # Not a security digest. (Was MD5 previously — flagged as weak-crypto in scanners.)
        seed_hash = int(hashlib.sha256(full.slug.encode()).hexdigest()[:8], 16)
        days_ago = seed_hash % 45
        reviewed_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        doc["last_reviewed_at"] = reviewed_at.isoformat()
        # Preserve existing extended quiz bank on upsert: use $setOnInsert for quiz
        # so seed_assessments' extra questions survive restarts. BUT if the
        # course exists in DB as a stub (empty quiz + has_full_content=False)
        # and is now graduating to a full course, force-set the quiz too.
        quiz_default = doc.pop("quiz", [])
        existing = await db.courses.find_one(
            {"slug": full.slug},
            {"_id": 0, "has_full_content": 1, "quiz": 1, "modules": 1},
        )
        # Preserve module/lesson ids across restarts (by position) so
        # video_checkpoints / lesson_videos / enrollments never orphan.
        if existing and existing.get("modules"):
            old_modules = existing["modules"]
            for mi, mod in enumerate(doc.get("modules", [])):
                if mi >= len(old_modules):
                    break
                mod["id"] = old_modules[mi].get("id", mod["id"])
                old_lessons = old_modules[mi].get("lessons", [])
                for li, lesson in enumerate(mod.get("lessons", [])):
                    if li >= len(old_lessons):
                        break
                    lesson["id"] = old_lessons[li].get("id", lesson["id"])
        was_stub = existing is not None and (not existing.get("has_full_content") or not existing.get("quiz"))
        if was_stub:
            # Stub → full transition: overwrite quiz with the new bank.
            doc["quiz"] = quiz_default
            await db.courses.update_one(
                {"slug": full.slug}, {"$set": doc}, upsert=True,
            )
        else:
            await db.courses.update_one(
                {"slug": full.slug},
                {"$set": doc, "$setOnInsert": {"quiz": quiz_default}},
                upsert=True,
            )
        full_slugs.add(full.slug)

    logger.info(f"Upserted {len(full_slugs)} full courses.")

    for meta in CATALOG_COURSES:
        if meta["slug"] in full_slugs:
            continue
        seed_hash = int(hashlib.sha256(meta["slug"].encode()).hexdigest()[:8], 16)
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
            "prerequisites": [], "learning_objectives": [], "skills_gained": [], "business_value": "",
            "is_certification_track": True, "modules": [], "quiz": [], "passing_score": 65,
            "enrolled_count": meta["enrolled_count"], "rating": meta["rating"],
            "created_at": now_iso(),
            "last_reviewed_at": reviewed_at.isoformat(),
            "has_full_content": False,
        }
        await db.courses.update_one({"slug": meta["slug"]}, {"$setOnInsert": catalog_doc}, upsert=True)

    await db.courses.create_index("slug", unique=True)
    await db.users.create_index("email", unique=True)
    await db.enrollments.create_index([("user_id", 1), ("course_id", 1)], unique=True)
    await db.certificates.create_index("certificate_id", unique=True)
    await db.organizations.create_index("slug", unique=True)
    await db.organizations.create_index("invite_code", unique=True)
    await db.org_members.create_index([("org_id", 1), ("user_id", 1)], unique=True)
    await db.rec_rationales.create_index("key", unique=True)
    await db.users.create_index("passport_slug", unique=True, sparse=True)
    # Password-reset tokens: TTL auto-purge + fast lookup by hash
    await db.password_reset_tokens.create_index("token_hash", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("user_id")
    # Credential impressions: dedup verifiers via unique impression_key + fast
    # lookups by holder + by-cert breakdown.
    await db.verify_impressions.create_index("impression_key", unique=True)
    await db.verify_impressions.create_index("user_id")
    await db.verify_impressions.create_index([("certificate_id", 1), ("day", 1)])
    # Live-activity feed: TTL-purge events older than 7 days + sort-by-time index
    await db.activity_events.create_index("created_at")
    # NOTE: Mongo's expireAfterSeconds needs a Date field, not an ISO string.
    # created_at is stored as ISO string above, so we prune manually via a
    # daily cursor. Keeping the sort index for fast tail-of-feed reads.

    # Seed randomized assessment banks (idempotent)
    from seed_assessments import seed_all as seed_assessment_banks
    try:
        await seed_assessment_banks()
    except Exception:
        logger.exception("Assessment bank seed failed (non-fatal)")

    total = await db.courses.count_documents({})
    logger.info(f"Seed complete. Total courses: {total}.")

    # Hydrate LLM-generated course content from committed assets so the
    # production DB gets the same material as preview on first boot.
    import json as _json
    gen_dir = os.path.join(os.path.dirname(__file__), "assets", "generated_courses")
    if os.path.isdir(gen_dir):
        hydrated = 0
        for fname in sorted(os.listdir(gen_dir)):
            if not fname.endswith(".json") or fname == "content_overrides.json":
                continue
            slug = fname[:-5]
            doc = await db.courses.find_one({"slug": slug}, {"_id": 0, "modules": 1})
            if doc is not None and not doc.get("modules"):
                with open(os.path.join(gen_dir, fname), encoding="utf-8") as f:
                    data = _json.load(f)
                await db.courses.update_one(
                    {"slug": slug},
                    {"$set": {
                        "modules": data["modules"],
                        "quiz": data.get("quiz") or [],
                        "has_full_content": True,
                    }},
                )
                hydrated += 1
        enriched_courses = 0
        ov_path = os.path.join(gen_dir, "content_overrides.json")
        if os.path.exists(ov_path):
            with open(ov_path, encoding="utf-8") as f:
                file_overrides = _json.load(f)
            for slug, per in file_overrides.items():
                course = await db.courses.find_one({"slug": slug}, {"_id": 0, "id": 1, "modules": 1})
                if not course:
                    continue
                sets = {}
                for key, o in per.items():
                    mi, li = (int(x) for x in key.split(":"))
                    try:
                        lesson = course["modules"][mi]["lessons"][li]
                    except (IndexError, KeyError):
                        continue
                    if len(lesson.get("content", "")) < len(o["content"]):
                        prefix = f"modules.{mi}.lessons.{li}"
                        sets[f"{prefix}.content"] = o["content"]
                        sets[f"{prefix}.key_takeaways"] = o.get("key_takeaways", [])
                        if o.get("code_sample"):
                            sets[f"{prefix}.code_sample"] = o["code_sample"]
                if sets:
                    await db.courses.update_one({"id": course["id"]}, {"$set": sets})
                    enriched_courses += 1
        if hydrated or enriched_courses:
            logger.info(f"Asset hydration: {hydrated} generated courses filled, {enriched_courses} builder courses enriched.")

    # Re-apply persisted lesson video URLs + LLM-enriched lesson content
    # (course upserts above replace docs, which would otherwise wipe
    # admin-configured videos / generated content on restart).
    mappings = await db.lesson_videos.find({}, {"_id": 0}).to_list(500)
    overrides = {o["lesson_id"]: o async for o in db.lesson_content_overrides.find({}, {"_id": 0})}
    applied = 0
    for m in mappings:
        course = await db.courses.find_one({"modules.lessons.id": m["lesson_id"]}, {"_id": 0, "id": 1, "modules": 1})
        if not course:
            continue
        for mi, mod in enumerate(course.get("modules", [])):
            for li, l in enumerate(mod.get("lessons", [])):
                if l.get("id") == m["lesson_id"]:
                    await db.courses.update_one(
                        {"id": course["id"]},
                        {"$set": {f"modules.{mi}.lessons.{li}.video_url": m["video_url"]}},
                    )
                    applied += 1
    if applied:
        logger.info(f"Re-applied {applied} lesson video URLs.")

    if overrides:
        content_applied = 0
        async for course in db.courses.find({"has_full_content": True}, {"_id": 0, "id": 1, "modules": 1}):
            sets = {}
            for mi, mod in enumerate(course.get("modules", [])):
                for li, l in enumerate(mod.get("lessons", [])):
                    o = overrides.get(l.get("id"))
                    if o and len(l.get("content", "")) < len(o.get("content", "")):
                        prefix = f"modules.{mi}.lessons.{li}"
                        sets[f"{prefix}.content"] = o["content"]
                        sets[f"{prefix}.key_takeaways"] = o.get("key_takeaways", [])
                        if o.get("code_sample"):
                            sets[f"{prefix}.code_sample"] = o["code_sample"]
            if sets:
                await db.courses.update_one({"id": course["id"]}, {"$set": sets})
                content_applied += 1
        if content_applied:
            logger.info(f"Re-applied enriched lesson content on {content_applied} courses.")


# -------------------- Router mounting --------------------
for r in (
    dashboard_router.router,  # health/root first
    auth_router.router,
    password_reset_router.router,
    catalog_router.router,
    assessment_router.router,
    tutor_router.router,
    voice_router.router,
    podcast_router.router,
    admin_control_router.router,
    traffic_router.router,
    mentor_router.router,
    recommendation_router.router,
    paths_router.router,
    passport_router.router,
    intelligence_router.router,
    checkout_router.router,
    enterprise_router.router,
    admin_router.router,
    admin_dashboard_router.router,
    digest_router.router,
    demo_router.router,
    trust_router.router,
    video_quiz_router.router,
    referral_router.router,
    security_router.router,
    command_center_router.router,
):
    app.include_router(r)


# -------------------- Middleware --------------------
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline security headers on every response.

    CSP hardens the XSS blast radius (localStorage token exfiltration surface is
    dominated by XSS; sanitising dangerouslySetInnerHTML + CSP is the pragmatic
    root-cause fix. httpOnly-cookie migration is on the roadmap.)
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
    )
    # Content-Security-Policy is deliberately permissive for the SPA (React needs
    # inline styles from Tailwind + streaming fetches). We block <object> and
    # frame-ancestors and lock scripts to self.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https:; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'",
    )
    return response


@app.on_event("startup")
async def on_startup():
    """Kick off seeding in the background so /health becomes reachable
    immediately (K8s readiness probes have ~2-5s tolerance, but a fresh
    Atlas cluster + full seed can easily take 30-90s and would time out
    the deployment).

    Seeding is idempotent — it's safe for the pod to serve traffic while
    seeding runs. Any endpoint that reads courses will return whatever is
    in the DB at that moment (empty on first boot, populated within seconds).
    """
    import asyncio as _asyncio

    async def _background_seed():
        try:
            await seed_database()
        except Exception:
            logger.exception("Catalog seed failed (non-fatal, will retry on next boot)")
        try:
            from seed_super_admin import seed_super_admin
            await seed_super_admin()
        except Exception:
            logger.exception("Super-admin seed failed (non-fatal)")
        try:
            # Gate sample-cert seed behind env flag so prod (where user has
            # purged demo data) doesn't re-create it on every backend restart.
            # Preview keeps SEED_SAMPLE_CERT=true so /verify demo still works.
            if os.environ.get("SEED_SAMPLE_CERT", "true").lower() in {"1", "true", "yes"}:
                from seed_sample_cert import seed_sample_certificate
                await seed_sample_certificate()
        except Exception:
            logger.exception("Sample certificate seed failed (non-fatal)")
        logger.info("Background seeding complete.")

    _asyncio.create_task(_background_seed())
    logger.info("Backend started; seeding scheduled in background.")


@app.on_event("shutdown")
async def on_shutdown():
    mongo_client.close()
