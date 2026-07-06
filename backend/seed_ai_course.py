"""AI-powered course-content generator.

Fills in the 15-module curriculum for any stub course in the catalog using
Claude Sonnet 4.5 (via the Emergent LLM key). Idempotent: only writes if
the course exists AND its `has_full_content` flag is False.

Usage:
    # Generate content for a single course
    python -m seed_ai_course --slug generative-ai-executives

    # Batch (all courses currently flagged has_full_content=False)
    python -m seed_ai_course --all

    # Dry-run — print the generated JSON to stdout but do NOT write
    python -m seed_ai_course --slug fine-tuning-llms --dry-run

    # Force regenerate even if already has_full_content
    python -m seed_ai_course --slug ai-observability --force

Design notes:
- Each call to Claude asks for a FULL 15-module structure with 4-5 lessons
  per module, each lesson containing markdown content + key takeaways.
- Prompt is deliberately constrained to force valid JSON (no markdown
  fences, no prose outside the JSON body).
- Retries: 3 attempts with exponential backoff on parse failures.
- Writes are transactional-ish per course: modules array is replaced
  wholesale, `has_full_content` set to True, `content_generated_at` timestamp
  recorded.
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

# Emergent LLM
from emergentintegrations.llm.chat import LlmChat, UserMessage
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_ai_course")

# ---- Config ---------------------------------------------------------------
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

if not (MONGO_URL and DB_NAME):
    raise SystemExit("MONGO_URL and DB_NAME must be set in the environment.")
if not EMERGENT_LLM_KEY:
    raise SystemExit("EMERGENT_LLM_KEY must be set to call Claude Sonnet 4.5.")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ---- Prompt ---------------------------------------------------------------
CURRICULUM_SYSTEM_PROMPT = """You are a Senior AI Curriculum Architect for the Enterprise Agentic AI Academy \
(ITHR Technologies Consulting). Given a course topic, audience, and difficulty, generate a rigorous, \
enterprise-grade 15-module curriculum with real lesson-level content.

Voice: precise, scholarly, warm. Cite specific frameworks, models, and vendors by name \
(Claude Sonnet 4.5, GPT-5, Gemini 3, LangGraph, CrewAI, AutoGen, MCP, LlamaIndex, vLLM, Bedrock, etc). \
Prefer 2-4 concise paragraphs of markdown per lesson with **bold** for key terms, inline `code`, and \
brief real-world examples. Never mention that you are an LLM.

Respond STRICTLY in JSON matching this schema (no markdown fences, no prose outside the JSON body):

{
  "modules": [
    {
      "number": 1..15 (must be sequential),
      "title": "Module title (5-8 words)",
      "summary": "One-sentence module summary (12-18 words)",
      "level": 1 for modules 1-5, 2 for 6-10, 3 for 11-15,
      "duration_min": 40-60,
      "lessons": [
        {
          "title": "Lesson title (4-8 words)",
          "content": "2-4 paragraphs of enterprise-grade markdown lesson content. Include real vendor/framework references. Use **bold** for key terms and `code` inline where relevant.",
          "duration_min": 8-15,
          "key_takeaways": ["3 concise action-oriented bullet-point takeaways"]
        }
        // exactly 4 or 5 lessons per module
      ]
    }
    // exactly 15 modules
  ]
}
"""


def _build_chat(session_id: str) -> LlmChat:
    return LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=CURRICULUM_SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")


async def _generate_curriculum(course: dict, max_retries: int = 3) -> dict:
    """Call Claude with the course metadata; return the parsed JSON. Retries on parse errors."""
    prompt = f"""Generate the full curriculum for this course.

Course title: {course['title']}
Subtitle: {course.get('subtitle', '')}
Category: {course.get('category', '')}
Difficulty: {course.get('difficulty', 'Intermediate')}
Target duration: {course.get('duration_hours', 20)} hours
Industries: {', '.join(course.get('industries', []) or ['general enterprise'])}
Existing learning objectives: {course.get('learning_objectives', [])}

Generate exactly 15 modules with 4-5 lessons each. Ensure lesson `content` is proper markdown, \
substantive (not stub text), and enterprise-relevant. Return valid JSON only.
"""

    last_err = None
    for attempt in range(1, max_retries + 1):
        session_id = f"course-gen-{course['slug']}-{attempt}-{uuid.uuid4().hex[:6]}"
        chat = _build_chat(session_id)
        log.info(f"[{course['slug']}] Generation attempt {attempt}/{max_retries}...")
        try:
            reply = await chat.send_message(UserMessage(text=prompt))
            # Strip any accidental fences
            text = reply.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip().rsplit("```", 1)[0].strip()
            parsed = json.loads(text)
            _validate_curriculum(parsed)
            log.info(f"[{course['slug']}] Generation succeeded ({len(parsed['modules'])} modules).")
            return parsed
        except Exception as e:
            last_err = e
            log.warning(f"[{course['slug']}] Attempt {attempt} failed: {e}. Retrying...")
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"All {max_retries} generation attempts failed. Last error: {last_err}")


def _validate_curriculum(payload: dict) -> None:
    if "modules" not in payload:
        raise ValueError("Response missing 'modules'")
    mods = payload["modules"]
    if len(mods) != 15:
        raise ValueError(f"Expected 15 modules, got {len(mods)}")
    for i, m in enumerate(mods):
        if m.get("number") != i + 1:
            raise ValueError(f"Module {i}: expected number={i+1}, got {m.get('number')}")
        if not (4 <= len(m.get("lessons", [])) <= 5):
            raise ValueError(f"Module {i+1}: expected 4-5 lessons, got {len(m.get('lessons', []))}")
        for L in m["lessons"]:
            if len(L.get("content", "")) < 150:
                raise ValueError(f"Module {i+1} '{L.get('title')}': lesson content too short ({len(L.get('content',''))} chars)")


def _stamp_ids(modules: list) -> list:
    """Attach uuid IDs to each module + lesson so they behave like the manually-authored ones."""
    for m in modules:
        m["id"] = uuid.uuid4().hex
        for L in m.get("lessons", []):
            L["id"] = uuid.uuid4().hex
            L.setdefault("duration_min", 10)
            L.setdefault("key_takeaways", [])
            L.setdefault("code_sample", None)
        m.setdefault("duration_min", sum(L.get("duration_min", 10) for L in m["lessons"]))
    return modules


async def _persist(course_slug: str, generated: dict) -> None:
    modules = _stamp_ids(generated["modules"])
    total_duration = sum(m.get("duration_min", 45) for m in modules)
    duration_hours = max(15, round(total_duration / 60))
    await db.courses.update_one(
        {"slug": course_slug},
        {"$set": {
            "modules": modules,
            "has_full_content": True,
            "content_generated_at": datetime.now(timezone.utc).isoformat(),
            "duration_hours": duration_hours,
        }},
    )
    log.info(f"[{course_slug}] Persisted {len(modules)} modules ({duration_hours}h total).")


async def generate_for_slug(slug: str, dry_run: bool = False, force: bool = False) -> bool:
    course = await db.courses.find_one({"slug": slug})
    if not course:
        log.error(f"[{slug}] Course not found.")
        return False
    if course.get("has_full_content") and not force:
        log.info(f"[{slug}] Already has full content — skipping (pass --force to overwrite).")
        return False
    payload = await _generate_curriculum(course)
    if dry_run:
        print(json.dumps(payload, indent=2))
        return True
    await _persist(slug, payload)
    return True


async def generate_all(dry_run: bool = False, force: bool = False) -> None:
    query = {} if force else {"has_full_content": {"$ne": True}}
    cursor = db.courses.find(query, {"slug": 1, "title": 1, "_id": 0})
    slugs = [c["slug"] async for c in cursor]
    log.info(f"Batch generation for {len(slugs)} courses: {slugs}")
    for slug in slugs:
        try:
            await generate_for_slug(slug, dry_run=dry_run, force=force)
        except Exception as e:
            log.exception(f"[{slug}] Fatal error during generation: {e}")


def main():
    parser = argparse.ArgumentParser(description="AI-generate full curriculum for stub courses.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Course slug to generate content for.")
    group.add_argument("--all", action="store_true", help="Generate content for ALL stub courses.")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout without writing.")
    parser.add_argument("--force", action="store_true", help="Regenerate even if content already exists.")
    args = parser.parse_args()

    if args.all:
        asyncio.run(generate_all(dry_run=args.dry_run, force=args.force))
    else:
        ok = asyncio.run(generate_for_slug(args.slug, dry_run=args.dry_run, force=args.force))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
