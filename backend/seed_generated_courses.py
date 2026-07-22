"""Seed the LLM-generated full course content baked into the repo.

Why this exists
---------------
17 catalogue courses were fleshed out to the full 15-module ITHR structure by
an LLM batch job. That content was written straight into MongoDB — which means
it lived ONLY in the database and never travelled to production on redeploy
(production gets a fresh DB seeded from code, so those 17 courses stayed as
4-module "coming soon" stubs).

To make the content reproducible across every environment, the generated
courses were exported to `data/generated_courses.json` (committed to the repo).
This module upserts that content on startup — graduating each stub into a fully
published course. Idempotent + safe to run on every boot.

Guarantees:
  * Never touches the course-level `id` (so enrollments/certificates never orphan).
  * Never touches `slug`, `title`, `category`, `industries`, `thumbnail_url`,
    `instructor`, `enrolled_count`, `rating` — those come from the stub seed.
  * Sets the heavy content fields (modules, objectives, skills, description,
    duration, quiz) + flips `has_full_content=True` and `status="published"`.
  * Module/lesson ids come from the committed JSON, so they are identical in
    preview and production.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import db, logger

_DATA_FILE = Path(__file__).resolve().parent / "data" / "generated_courses.json"


def _load_records() -> list[dict]:
    if not _DATA_FILE.exists():
        logger.warning(f"[seed-generated] {_DATA_FILE} not found — skipping.")
        return []
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


async def seed_generated_courses() -> int:
    """Upsert baked full-course content into any matching course rows.

    Returns the number of courses that were actually modified this run.
    """
    records = _load_records()
    if not records:
        return 0

    modified = 0
    for rec in records:
        slug = rec.get("slug")
        modules = rec.get("modules") or []
        if not slug or len(modules) < 15:
            continue

        existing = await db.courses.find_one({"slug": slug}, {"_id": 0, "id": 1})
        if not existing:
            # Stub seed runs before this; if the row somehow doesn't exist we
            # skip rather than create a half-formed course.
            continue

        content = {
            "modules": modules,
            "learning_objectives": rec.get("learning_objectives") or [],
            "skills_gained": rec.get("skills_gained") or [],
            "business_value": rec.get("business_value") or "",
            "prerequisites": rec.get("prerequisites") or [],
            "description": rec.get("description") or "",
            "duration_hours": rec.get("duration_hours"),
            "quiz": rec.get("quiz") or [],
            "passing_score": rec.get("passing_score", 65),
            "has_full_content": True,
            "status": "published",
        }
        result = await db.courses.update_one({"slug": slug}, {"$set": content})
        if result.modified_count:
            modified += 1

    if modified:
        logger.info(f"[seed-generated] Published {modified} baked full course(s).")
    else:
        logger.info("[seed-generated] All baked courses already up to date.")
    return modified
