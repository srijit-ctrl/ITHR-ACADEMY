"""Intelligence briefing + course refresh + NEW push-to-curriculum action."""
import asyncio
import uuid
from datetime import datetime, timezone

# Hard ceiling for the (LLM-backed) briefing generation so the endpoint can
# never hang indefinitely — the frontend gets a fast, actionable error instead.
# Set generously enough that a normal regeneration completes, but bounded.
BRIEFING_TIMEOUT_SECONDS = 40

from fastapi import APIRouter, Depends, HTTPException

from ai_service import _build_chat, generate_course_refresh, generate_intelligence_briefing
from auth import get_current_user_id
from core import db, extract_json, logger, now_iso

router = APIRouter(prefix="/api", tags=["intelligence"])

INTELLIGENCE_CACHE_KEY = "current_briefing"
INTELLIGENCE_CACHE_HOURS = 6

# Guards against multiple concurrent background regenerations.
_regen_inflight = False


def _stale_cache_response(cached: dict) -> dict:
    """Return the last-good cached briefing, flagged stale, with its REAL age."""
    try:
        cached_at = datetime.fromisoformat(cached["cached_at"])
        age_hours = round((datetime.now(timezone.utc) - cached_at).total_seconds() / 3600, 1)
    except Exception:
        age_hours = None
    return {**cached["payload"], "cache_age_hours": age_hours, "from_cache": True, "stale": True}


async def _generate_and_cache() -> dict:
    """Generate a fresh briefing and persist it to the cache. Returns payload."""
    course_docs = await db.courses.find({}, {"_id": 0, "slug": 1}).to_list(200)
    slugs = [c["slug"] for c in course_docs]
    raw = await generate_intelligence_briefing(slugs)
    parsed = extract_json(raw)
    payload = {**parsed, "generated_at": parsed.get("generated_at") or now_iso()}
    await db.intelligence_cache.update_one(
        {"key": INTELLIGENCE_CACHE_KEY},
        {"$set": {"key": INTELLIGENCE_CACHE_KEY, "payload": payload, "cached_at": now_iso()}},
        upsert=True,
    )
    return payload


async def _regenerate_in_background():
    """Fire-and-forget stale-while-revalidate refresh (only one at a time)."""
    global _regen_inflight
    if _regen_inflight:
        return
    _regen_inflight = True
    try:
        await asyncio.wait_for(_generate_and_cache(), timeout=120)
        logger.info("Intelligence briefing regenerated in background.")
    except Exception:
        logger.exception("Background briefing regeneration failed (non-fatal)")
    finally:
        _regen_inflight = False


@router.get("/intelligence/briefing")
async def intelligence_briefing(force: bool = False):
    cached = await db.intelligence_cache.find_one({"key": INTELLIGENCE_CACHE_KEY}, {"_id": 0})

    if cached and not force:
        cached_at = datetime.fromisoformat(cached["cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < INTELLIGENCE_CACHE_HOURS:
            return {**cached["payload"], "cache_age_hours": round(age_hours, 1), "from_cache": True}
        # Stale-while-revalidate: return the cached briefing INSTANTLY and kick
        # off a background refresh so the next visitor gets fresh content. This
        # is why the page never hangs on the (slow) LLM generation.
        asyncio.create_task(_regenerate_in_background())
        return {**cached["payload"], "cache_age_hours": round(age_hours, 1), "from_cache": True, "stale": True}

    # No cache yet, OR the user explicitly forced a refresh — generate
    # synchronously but bounded, so we can never hang indefinitely.
    try:
        payload = await asyncio.wait_for(_generate_and_cache(), timeout=BRIEFING_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Intelligence generation timed out after %ss", BRIEFING_TIMEOUT_SECONDS)
        if cached:
            asyncio.create_task(_regenerate_in_background())
            return _stale_cache_response(cached)
        raise HTTPException(
            status_code=504,
            detail="The live briefing is taking longer than usual to generate. Please retry in a moment.",
        )
    except Exception as e:
        logger.exception("Intelligence generation failed")
        if cached:
            return _stale_cache_response(cached)
        raise HTTPException(status_code=502, detail=f"Intelligence generation failed: {e}")

    return {**payload, "cache_age_hours": 0, "from_cache": False}


@router.get("/intelligence/course/{slug}/refresh")
async def course_refresh(slug: str, user_id: str = Depends(get_current_user_id)):
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    cache_key = f"course_refresh_{slug}"
    cached = await db.intelligence_cache.find_one({"key": cache_key}, {"_id": 0})
    if cached:
        cached_at = datetime.fromisoformat(cached["cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < 12:
            return {**cached["payload"], "cache_age_hours": round(age_hours, 1), "from_cache": True}

    try:
        raw = await generate_course_refresh(course)
        parsed = extract_json(raw)
    except Exception as e:
        logger.exception("Course refresh generation failed")
        raise HTTPException(status_code=502, detail=f"Course refresh failed: {e}")

    await db.intelligence_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "payload": parsed, "cached_at": now_iso()}},
        upsert=True,
    )
    return {**parsed, "cache_age_hours": 0, "from_cache": False}


# ==================== NEW: Push signal into curriculum ====================
PATCH_SYSTEM_PROMPT = """You are the ITHR Curriculum Author agent. Given a single industry signal and a target course, propose a concrete curriculum patch.

Return STRICTLY JSON matching:
{
  "target_module_number": integer 1-15 (which module this update belongs to),
  "patch_type": one of ["module_update","lesson_add","note"],
  "proposed_title": string (title of the new lesson or module update — <10 words),
  "proposed_content": string (150-350 words of publish-ready lesson content, markdown allowed with **bold** and bullet lists),
  "rationale": string (1-2 sentences explaining WHY this patch is needed given the signal)
}

No fences, no prose outside JSON.
"""


async def _generate_patch(signal: dict, course: dict) -> dict:
    from emergentintegrations.llm.chat import UserMessage, TextDelta, StreamDone
    session_id = f"patch-{course['slug']}-{signal.get('id', 'x')}"
    chat = _build_chat(session_id=session_id, system_message=PATCH_SYSTEM_PROMPT)
    prompt = (
        f"Target course: {course['title']}\n"
        f"Course subtitle: {course.get('subtitle', '')}\n"
        f"Signal: {signal.get('title')}\n"
        f"Signal summary: {signal.get('summary')}\n"
        f"Signal impact: {signal.get('impact')}\n"
        f"Recommended action from Intelligence Desk: {signal.get('recommended_action')}\n\n"
        "Author a curriculum patch."
    )
    chunks = []
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            chunks.append(event.content)
        elif isinstance(event, StreamDone):
            break
    return extract_json("".join(chunks))


@router.post("/intelligence/signals/{signal_id}/apply")
async def apply_signal(signal_id: str, payload: dict, user_id: str = Depends(get_current_user_id)):
    """Push a signal into a course as an AI-drafted curriculum patch, ready for review."""
    course_slug = payload.get("course_slug")
    if not course_slug:
        raise HTTPException(status_code=400, detail="course_slug required")

    # Load latest briefing to find signal
    cached = await db.intelligence_cache.find_one({"key": INTELLIGENCE_CACHE_KEY}, {"_id": 0})
    if not cached:
        raise HTTPException(status_code=404, detail="No active briefing available")
    signals = cached["payload"].get("signals", [])
    signal = next((s for s in signals if s.get("id") == signal_id), None)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found in current briefing")

    course = await db.courses.find_one({"slug": course_slug}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        patch_json = await _generate_patch(signal, course)
    except Exception as e:
        logger.exception("Patch generation failed")
        raise HTTPException(status_code=502, detail=f"Patch generation failed: {e}")

    module_number = patch_json.get("target_module_number") or 1
    modules = course.get("modules", [])
    module_title = None
    if modules and 1 <= module_number <= len(modules):
        module_title = modules[module_number - 1].get("title")

    patch_doc = {
        "id": uuid.uuid4().hex,
        "course_slug": course_slug,
        "signal_id": signal_id,
        "signal_title": signal.get("title", ""),
        "module_number": module_number,
        "module_title": module_title,
        "patch_type": patch_json.get("patch_type", "module_update"),
        "proposed_title": patch_json.get("proposed_title", ""),
        "proposed_content": patch_json.get("proposed_content", ""),
        "rationale": patch_json.get("rationale", ""),
        "status": "proposed",
        "created_by": user_id,
        "created_at": now_iso(),
    }
    await db.curriculum_patches.insert_one(patch_doc)
    patch_doc.pop("_id", None)

    # Mark course as "recently reviewed" since a real update was proposed
    await db.courses.update_one(
        {"slug": course_slug},
        {"$set": {"last_reviewed_at": now_iso()}},
    )

    return {"patch": patch_doc, "status": "proposed"}


@router.get("/intelligence/patches")
async def list_patches(course_slug: str = None, status: str = None, user_id: str = Depends(get_current_user_id)):
    q = {}
    if course_slug:
        q["course_slug"] = course_slug
    if status:
        q["status"] = status
    patches = await db.curriculum_patches.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"patches": patches, "count": len(patches)}


@router.post("/intelligence/patches/{patch_id}/decide")
async def decide_patch(patch_id: str, payload: dict, user_id: str = Depends(get_current_user_id)):
    """Approve or reject a patch."""
    decision = payload.get("decision")
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    patch = await db.curriculum_patches.find_one({"id": patch_id}, {"_id": 0})
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    await db.curriculum_patches.update_one(
        {"id": patch_id},
        {"$set": {"status": decision, "reviewed_at": now_iso(), "reviewed_by": user_id}},
    )

    # Fire notifications to org channels (best-effort, non-blocking failure)
    if decision == "approved":
        try:
            from notifications import notify_channels
            # Notify every org that has webhooks + notify_on_patch_approval enabled
            orgs_cursor = db.organizations.find(
                {"$or": [{"slack_webhook_url": {"$ne": None}},
                         {"teams_webhook_url": {"$ne": None}}],
                 "notify_on_patch_approval": {"$ne": False}},
                {"_id": 0, "slack_webhook_url": 1, "teams_webhook_url": 1, "name": 1, "id": 1},
            )
            reviewer = await db.users.find_one({"id": user_id}, {"_id": 0, "full_name": 1})
            reviewer_name = (reviewer or {}).get("full_name", "an editor")
            title = f"Curriculum patch approved · {patch.get('course_slug')}"
            text = (
                f"*{patch.get('proposed_title','(untitled)')}*\n"
                f"Signal: {patch.get('signal_title','')}\n"
                f"Module: {patch.get('module_number')} · Reviewer: {reviewer_name}"
            )
            facts = [
                {"name": "Course", "value": patch.get("course_slug", "")},
                {"name": "Module", "value": str(patch.get("module_number", "-"))},
                {"name": "Reviewer", "value": reviewer_name},
                {"name": "Type", "value": patch.get("patch_type", "module_update")},
            ]
            async for org in orgs_cursor:
                await notify_channels(
                    slack_url=org.get("slack_webhook_url"),
                    teams_url=org.get("teams_webhook_url"),
                    title=title, text=text, facts=facts,
                )
        except Exception:
            logger.exception("Patch approval notifications failed (non-fatal)")

    return {"status": decision, "patch_id": patch_id}
