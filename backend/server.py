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
    assessment_router, auth_router, catalog_router, checkout_router,
    dashboard_router, enterprise_router, intelligence_router, tutor_router,
)
from seed_data import CATALOG_COURSES, build_full_course


app = FastAPI(title="Enterprise Agentic AI Academy API", version="1.1.0")


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
    ]
    full_slugs = set()

    for builder in full_builders:
        full = builder()
        doc = full.model_dump()
        doc["has_full_content"] = True
        seed_hash = int(hashlib.md5(full.slug.encode()).hexdigest()[:8], 16)
        days_ago = seed_hash % 45
        reviewed_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        doc["last_reviewed_at"] = reviewed_at.isoformat()
        await db.courses.update_one({"slug": full.slug}, {"$set": doc}, upsert=True)
        full_slugs.add(full.slug)

    logger.info(f"Upserted {len(full_slugs)} full courses.")

    for meta in CATALOG_COURSES:
        if meta["slug"] in full_slugs:
            continue
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
    total = await db.courses.count_documents({})
    logger.info(f"Seed complete. Total courses: {total}.")


# -------------------- Router mounting --------------------
for r in (
    dashboard_router.router,  # health/root first
    auth_router.router,
    catalog_router.router,
    assessment_router.router,
    tutor_router.router,
    intelligence_router.router,
    checkout_router.router,
    enterprise_router.router,
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


@app.on_event("startup")
async def on_startup():
    await seed_database()


@app.on_event("shutdown")
async def on_shutdown():
    mongo_client.close()
