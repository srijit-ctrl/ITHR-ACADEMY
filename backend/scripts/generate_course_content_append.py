"""Append missing modules to incomplete courses using Claude / Gemini via Emergent LLM key.

The catalog seeds 17 courses with a 4-module stub. This script extends each stub
to the full 15-module ITHR structure by APPENDING new modules that pick up where
the stub left off.

**Strategy**: One module per LLM call. Batches of 2 concurrent calls to respect
provider rate limits while staying inside the 120s bash tool timeout per module.
Failures on any single module fall back to Gemini 3 Flash before giving up. If
BOTH providers fail on a module, we abort that course and leave the DB unchanged
(no partial writes).

Design rules:
  * NEVER delete or renumber the existing 4 modules — user preference is "append
    missing modules only". Existing content is authoritative.
  * New module numbering starts at (max_existing_number + 1) and goes to 15.
  * Level distribution for new modules: 1-5 = level 1, 6-10 = level 2,
    11-15 = level 3. Matches the pattern of manually-authored courses.
  * All writes are idempotent: courses whose module count is already >= 15 are
    skipped. Uses `has_full_content=True` as the completion marker.

Usage:
    # Fill all incomplete courses
    python -m scripts.generate_course_content_append --all

    # One at a time (safer)
    python -m scripts.generate_course_content_append --slug ai-devops-mlops

    # Dry-run — print the JSON but don't write to DB
    python -m scripts.generate_course_content_append --slug responsible-ai --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gen-course-append")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

if not (MONGO_URL and DB_NAME):
    raise SystemExit("MONGO_URL and DB_NAME must be set in the environment.")
if not EMERGENT_LLM_KEY:
    raise SystemExit("EMERGENT_LLM_KEY must be set for LLM generation.")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

TARGET_MODULE_COUNT = 15
CONCURRENT_MODULES = 2  # keep low to respect rate limits + stay inside bash timeout

# --- Provider cascade (user choice: Claude Sonnet 4.5 primary, Gemini 3 Flash fallback) --
PROVIDERS = [
    ("anthropic", "claude-sonnet-4-5-20250929"),
    ("gemini", "gemini-3-flash-preview"),
]

MODULE_SYSTEM_PROMPT = """You are a Senior AI Curriculum Architect for the Enterprise Agentic AI Academy \
(ITHR Technologies Consulting). Generate ONE course module of enterprise-grade \
lesson content for the requested topic.

Voice: precise, scholarly, warm. Cite specific frameworks, models, and vendors by name \
(Claude Sonnet 4.5, GPT-5.2, Gemini 3, LangGraph, CrewAI, AutoGen, MCP, LlamaIndex, vLLM, \
Bedrock, Databricks, Snowflake, Pinecone, Weaviate, Anthropic, OpenAI, Cohere, etc). \
Prefer 2-3 concise paragraphs of markdown per lesson with **bold** for key terms, \
inline `code` for specifics, and brief real-world examples. Never mention that you are an LLM.

Respond STRICTLY in JSON matching this schema (no markdown fences, no prose outside the JSON body):

{
  "number": <int, matching the requested module number>,
  "title": "Module title (5-8 words)",
  "summary": "One-sentence module summary (12-18 words)",
  "level": <1|2|3 matching the requested level>,
  "duration_min": 40-60,
  "lessons": [
    {
      "title": "Lesson title (4-8 words)",
      "content": "2-3 paragraphs of enterprise-grade markdown. Reference real vendors/frameworks. **Bold** for key terms and `code` inline. MINIMUM 350 characters.",
      "duration_min": 8-15,
      "key_takeaways": ["3 concise action-oriented takeaways"]
    }
    // exactly 4 lessons
  ]
}
"""

OBJECTIVES_SYSTEM_PROMPT = """You are a Senior AI Curriculum Architect for the Enterprise Agentic AI Academy. \
Generate the learning-outcomes for a course.

Respond STRICTLY in JSON (no markdown fences, no prose outside the body):

{
  "learning_objectives": [
    // exactly 5 concise outcome bullets, each 8-16 words
  ],
  "skills_gained": [
    // exactly 7 concrete 1-3-word skill tags
  ]
}
"""


def _build_chat(provider: str, model_id: str, session_id: str, system_prompt: str) -> LlmChat:
    return LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_prompt,
    ).with_model(provider, model_id)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rsplit("```", 1)[0].strip()
    brace = text.find("{")
    if brace > 0:
        text = text[brace:]
    return text


async def _llm_call(session_prefix: str, prompt: str, system_prompt: str, validator, max_retries: int = 2) -> dict:
    """Provider cascade with per-provider retries. Returns parsed+validated JSON."""
    last_err: Optional[Exception] = None
    for provider, model_id in PROVIDERS:
        for attempt in range(1, max_retries + 1):
            session_id = f"{session_prefix}-{provider}-{attempt}-{uuid.uuid4().hex[:6]}"
            chat = _build_chat(provider, model_id, session_id, system_prompt)
            try:
                reply = await chat.send_message(UserMessage(text=prompt))
                text = _strip_fences(reply)
                parsed = json.loads(text)
                validator(parsed)
                log.info(f"[{session_prefix}] OK via {provider}/{model_id} on attempt {attempt}")
                return parsed
            except Exception as e:
                last_err = e
                log.warning(f"[{session_prefix}] {provider} attempt {attempt} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        log.warning(f"[{session_prefix}] {provider} exhausted — cascading.")
    raise RuntimeError(f"All providers failed for {session_prefix}. Last error: {last_err}")


# ---- Validators ---------------------------------------------------------

def _validate_module(payload: dict) -> None:
    for k in ("number", "title", "summary", "level", "lessons"):
        if k not in payload:
            raise ValueError(f"Module missing key '{k}'")
    lessons = payload.get("lessons") or []
    if not (3 <= len(lessons) <= 5):
        raise ValueError(f"Expected 3-5 lessons, got {len(lessons)}")
    for L in lessons:
        if not L.get("title") or len(L.get("content", "")) < 200:
            raise ValueError(f"Lesson '{L.get('title')}' content too short ({len(L.get('content', ''))} chars)")


def _validate_objectives(payload: dict) -> None:
    objs = payload.get("learning_objectives") or []
    skills = payload.get("skills_gained") or []
    if len(objs) < 4:
        raise ValueError(f"Expected 4+ learning_objectives, got {len(objs)}")
    if len(skills) < 5:
        raise ValueError(f"Expected 5+ skills_gained, got {len(skills)}")


# ---- Module generation --------------------------------------------------

def _existing_summary(modules: list) -> str:
    if not modules:
        return "(none — this is a greenfield course)"
    lines = []
    for m in modules:
        lines.append(f"  Module {m.get('number', '?')} · Level {m.get('level', '?')} · {m.get('title', '')}")
    return "\n".join(lines)


def _level_for(number: int) -> int:
    return 1 if number <= 5 else 2 if number <= 10 else 3


def _next_module_topic_hint(course: dict, number: int, level: int) -> str:
    """Guide the LLM toward a topic that fits the level + doesn't repeat existing modules."""
    level_hints = {
        1: "foundations, key concepts, why this matters for enterprises",
        2: "implementation patterns, real tooling, integrations, evaluation, security",
        3: "advanced case studies, domain-specific applications, capstone-caliber material",
    }
    if number == TARGET_MODULE_COUNT:
        return "capstone project — apply everything to a fictional Fortune 500 scenario. 3-4 lessons: brief, architecture deliverable, executive presentation."
    return level_hints[level]


async def _gen_one_module(course: dict, module_number: int) -> dict:
    level = _level_for(module_number)
    topic_hint = _next_module_topic_hint(course, module_number, level)
    prompt = f"""Generate module #{module_number} of an ITHR course.

Course title: {course['title']}
Subtitle: {course.get('subtitle', '')}
Category: {course.get('category', '')}
Difficulty: {course.get('difficulty', 'Intermediate')}
Industries: {', '.join(course.get('industries', []) or ['general enterprise'])}

Existing modules already in this course (DO NOT repeat these topics):
{_existing_summary(course.get('modules') or [])}

For module #{module_number}:
  * number = {module_number}
  * level = {level}
  * Focus: {topic_hint}
  * Exactly 4 lessons (or 3 for the capstone if it makes more sense).
  * Each lesson `content` must be substantive markdown (min 350 chars).

Return valid JSON only. No prose outside the JSON body.
"""
    session_prefix = f"mod-{course['slug']}-m{module_number}"
    parsed = await _llm_call(session_prefix, prompt, MODULE_SYSTEM_PROMPT, _validate_module)
    # Force correct number/level even if the LLM drifts.
    parsed["number"] = module_number
    parsed["level"] = level
    return parsed


async def _gen_objectives(course: dict) -> dict:
    prompt = f"""Generate learning_objectives + skills_gained for this ITHR course.

Course title: {course['title']}
Subtitle: {course.get('subtitle', '')}
Category: {course.get('category', '')}
Difficulty: {course.get('difficulty', 'Intermediate')}
Description: {course.get('description', '')}

5 outcome bullets + 7 skill tags. Return valid JSON only.
"""
    session_prefix = f"obj-{course['slug']}"
    return await _llm_call(session_prefix, prompt, OBJECTIVES_SYSTEM_PROMPT, _validate_objectives)


def _stamp_ids(modules: list) -> list:
    """Attach uuid IDs + defaults to each new module + lesson."""
    for m in modules:
        m["id"] = uuid.uuid4().hex
        for L in m.get("lessons", []):
            L["id"] = uuid.uuid4().hex
            L.setdefault("duration_min", 10)
            L.setdefault("key_takeaways", [])
            L.setdefault("code_sample", None)
        m.setdefault("duration_min", sum(L.get("duration_min", 10) for L in m["lessons"]))
    return modules


async def _gather_modules_bounded(course: dict, numbers: list) -> list:
    """Generate the requested modules sequentially, feeding each newly-generated
    module title back into the next prompt so the LLM avoids topic overlap.

    Sequential within a course (topic-coherence over speed). Concurrency is
    exploited at the course-batch level in process_all().
    """
    results = []
    # Snapshot of the course we mutate as we generate — the "existing_modules"
    # summary that goes into each subsequent prompt grows with each iteration.
    running_course = dict(course)
    running_modules = list(course.get("modules") or [])

    for number in numbers:
        running_course["modules"] = running_modules
        log.info(f"[{course['slug']}] → generating module {number}")
        mod = await _gen_one_module(running_course, number)
        results.append(mod)
        # Add a lightweight stub to running_modules so the next call sees it.
        running_modules = running_modules + [{
            "number": mod["number"],
            "level": mod["level"],
            "title": mod["title"],
        }]
    return results


async def process_course(slug: str, dry_run: bool = False, force: bool = False) -> bool:
    course = await db.courses.find_one({"slug": slug})
    if not course:
        log.error(f"[{slug}] Course not found.")
        return False

    existing_modules = course.get("modules") or []
    existing_count = len(existing_modules)
    log.info(f"[{slug}] Existing: {existing_count} modules · has_full_content={course.get('has_full_content')}")

    if existing_count >= TARGET_MODULE_COUNT and not force:
        log.info(f"[{slug}] Already at {existing_count} modules — skipping.")
        return False

    needs_objectives = not (course.get("learning_objectives") or [])
    numbers_to_gen = list(range(existing_count + 1, TARGET_MODULE_COUNT + 1))

    # Kick off objectives + modules in parallel.
    tasks = [_gather_modules_bounded(course, numbers_to_gen)]
    if needs_objectives:
        tasks.append(_gen_objectives(course))

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    modules_result = outcomes[0]
    if isinstance(modules_result, Exception):
        raise modules_result

    objectives_result = None
    if needs_objectives:
        objectives_result = outcomes[1]
        if isinstance(objectives_result, Exception):
            log.warning(f"[{slug}] Objectives generation failed ({objectives_result}) — proceeding without them.")
            objectives_result = None

    new_modules = _stamp_ids(modules_result)
    combined_modules = existing_modules + new_modules

    total_duration_min = sum(m.get("duration_min", 45) for m in combined_modules)
    duration_hours = max(course.get("duration_hours", 15), round(total_duration_min / 60))

    if dry_run:
        preview = {
            "slug": slug,
            "existing_count": existing_count,
            "appending": len(new_modules),
            "final_count": len(combined_modules),
            "duration_hours": duration_hours,
            "new_module_titles": [m["title"] for m in new_modules],
        }
        if objectives_result:
            preview["learning_objectives"] = objectives_result.get("learning_objectives") or []
            preview["skills_gained"] = objectives_result.get("skills_gained") or []
        print(json.dumps(preview, indent=2))
        return True

    update_doc = {
        "modules": combined_modules,
        "duration_hours": duration_hours,
        "has_full_content": True,
        "content_generated_at": datetime.now(timezone.utc).isoformat(),
        "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        "status": "published",  # graduate from stub so learners can enrol
    }
    # Strip the "Full curriculum in preparation" stub marker from the description
    # so `derive_status()` correctly reports "published".
    stub_desc = course.get("description") or ""
    if "Full curriculum in preparation" in stub_desc:
        cleaned = stub_desc.split("Full curriculum in preparation")[0].rstrip(" .—-")
        # Fall back to the subtitle if the description was 100% stub boilerplate.
        update_doc["description"] = cleaned or (course.get("subtitle") or "").rstrip(" .")
    if objectives_result:
        if objectives_result.get("learning_objectives"):
            update_doc["learning_objectives"] = objectives_result["learning_objectives"]
        if objectives_result.get("skills_gained"):
            update_doc["skills_gained"] = objectives_result["skills_gained"]

    result = await db.courses.update_one({"slug": slug}, {"$set": update_doc})
    log.info(
        f"[{slug}] ✓ Appended {len(new_modules)} modules (total={len(combined_modules)}, "
        f"{duration_hours}h). Modified={result.modified_count}."
    )
    return True


async def process_all(dry_run: bool = False, force: bool = False, concurrency: int = 3) -> None:
    """Process every incomplete course. Runs `concurrency` courses at a time.

    Different courses have zero topic overlap, so course-level concurrency is
    safe; modules within a single course are still serialised for coherence.
    """
    all_courses = await db.courses.find({}, {"slug": 1, "title": 1, "modules": 1, "_id": 0}).to_list(500)
    incomplete = [c for c in all_courses if len(c.get("modules") or []) < TARGET_MODULE_COUNT]
    log.info(f"Batch: {len(incomplete)} incomplete courses out of {len(all_courses)} total. Concurrency={concurrency}.")

    sem = asyncio.Semaphore(concurrency)
    counters = {"ok": 0, "fail": 0}

    async def _one(idx: int, c: dict):
        async with sem:
            log.info(f"=== ({idx}/{len(incomplete)}) {c['slug']} — {c.get('title', '')} ===")
            try:
                done = await process_course(c["slug"], dry_run=dry_run, force=force)
                if done:
                    counters["ok"] += 1
            except Exception as e:
                log.exception(f"[{c['slug']}] Fatal error: {e}")
                counters["fail"] += 1

    await asyncio.gather(*[_one(i, c) for i, c in enumerate(incomplete, start=1)])
    log.info(
        f"=== Batch complete: {counters['ok']} succeeded, {counters['fail']} failed, "
        f"{len(incomplete) - counters['ok'] - counters['fail']} skipped. ==="
    )


def main():
    parser = argparse.ArgumentParser(description="Append missing modules to incomplete ITHR courses.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Course slug to complete.")
    group.add_argument("--all", action="store_true", help="Process every incomplete course.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB.")
    parser.add_argument("--force", action="store_true", help="Regenerate even when already at 15 modules.")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent courses when --all (default 3).")
    args = parser.parse_args()

    if args.all:
        asyncio.run(process_all(dry_run=args.dry_run, force=args.force, concurrency=args.concurrency))
    else:
        ok = asyncio.run(process_course(args.slug, dry_run=args.dry_run, force=args.force))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
