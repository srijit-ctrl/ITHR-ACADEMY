"""Idempotent content fix-ups applied on startup.

Replaces known dead/stale external links inside course lesson content across the
whole catalogue. Runs on every boot (cheap, idempotent) so both preview and
production stay corrected regardless of where a given course's content came
from (code builder, baked JSON, or a one-off patch script).
"""
from __future__ import annotations

import json

from core import db, logger

# Map of dead URL -> working replacement URL.
DEAD_LINK_REPLACEMENTS = {
    "https://www.salesforce.com/news/press-releases/2024/12/17/agentforce-2-announcement/":
        "https://www.salesforce.com/agentforce/",
    "https://www.anthropic.com/news/claude-2-1":
        "https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips",
}


async def fix_dead_links() -> int:
    """Replace dead links in every course's modules. Returns #courses updated."""
    updated = 0
    async for course in db.courses.find({}, {"_id": 0, "slug": 1, "modules": 1, "description": 1}):
        modules = course.get("modules") or []
        desc = course.get("description") or ""
        blob = json.dumps(modules)
        new_blob = blob
        new_desc = desc
        for dead, good in DEAD_LINK_REPLACEMENTS.items():
            if dead in new_blob:
                new_blob = new_blob.replace(dead, good)
            if dead in new_desc:
                new_desc = new_desc.replace(dead, good)
        changes = {}
        if new_blob != blob:
            changes["modules"] = json.loads(new_blob)
        if new_desc != desc:
            changes["description"] = new_desc
        if changes:
            await db.courses.update_one({"slug": course["slug"]}, {"$set": changes})
            updated += 1
    if updated:
        logger.info(f"[content-fixups] Repaired dead links in {updated} course(s).")
    return updated


async def reconcile_enrollments() -> dict:
    """Make enrollment analytics TRUTHFUL and prevent inflated counts.

    Fixes the "a course shows 80 enrolments but only 36 users exist" class of
    bug by:
      1. De-duplicating enrollment docs (one per user+course, keep earliest).
      2. (Re)creating the unique (user_id, course_id) index — safe now that
         duplicates are gone, so it can't abort startup on production.
      3. Recomputing every course's `enrolled_count` to the REAL number of
         enrollment records (removes the seeded placeholder marketing numbers).
    Idempotent; runs on every boot.
    """
    # 1) De-duplicate — keep the earliest enrollment per (user, course).
    seen: set = set()
    dupe_ids: list = []
    async for e in db.enrollments.find(
        {}, {"_id": 1, "user_id": 1, "course_id": 1}
    ).sort("enrolled_at", 1):
        key = (e.get("user_id"), e.get("course_id"))
        if key in seen:
            dupe_ids.append(e["_id"])
        else:
            seen.add(key)
    removed = 0
    if dupe_ids:
        res = await db.enrollments.delete_many({"_id": {"$in": dupe_ids}})
        removed = res.deleted_count

    # 2) Unique index (now safe).
    try:
        await db.enrollments.create_index(
            [("user_id", 1), ("course_id", 1)], unique=True
        )
    except Exception:
        logger.exception("[reconcile] enrollment unique index creation failed")

    # 3) Sync each course's enrolled_count to the real enrollment total.
    counts: dict = {}
    async for row in db.enrollments.aggregate(
        [{"$group": {"_id": "$course_id", "n": {"$sum": 1}}}]
    ):
        counts[row["_id"]] = row["n"]
    synced = 0
    async for co in db.courses.find({}, {"_id": 0, "id": 1, "enrolled_count": 1}):
        real = counts.get(co["id"], 0)
        if co.get("enrolled_count") != real:
            await db.courses.update_one({"id": co["id"]}, {"$set": {"enrolled_count": real}})
            synced += 1
    logger.info(
        f"[reconcile] removed {removed} duplicate enrollment(s); "
        f"synced enrolled_count on {synced} course(s)."
    )
    return {"duplicates_removed": removed, "courses_synced": synced}
