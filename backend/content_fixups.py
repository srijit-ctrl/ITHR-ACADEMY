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
