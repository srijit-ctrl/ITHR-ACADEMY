"""LLM-powered course-content generation (Aletheia faculty writer).

Fills the 17 stub courses (no modules) with a full 4-module curriculum and
enriches the thin builder courses (45 short lessons) with real learning
material. Resumable: already-generated courses/modules are skipped.

Run:  python generate_course_content.py            # everything
      python generate_course_content.py stubs      # only stub courses
      python generate_course_content.py thin       # only thin enrichment
"""
import asyncio
import json
import os
import sys
import uuid

import json_repair
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

from core import db, logger, now_iso  # noqa: E402
from models import Lesson, Module, QuizQuestion  # noqa: E402

CONCURRENCY = 5
_sem = asyncio.Semaphore(CONCURRENCY)

SYSTEM = (
    "You are a senior curriculum designer at ITHR Academy, an enterprise AI training "
    "platform for consulting, banking, healthcare and government professionals. "
    "You write rigorous, practical, business-grounded learning material. "
    "You ALWAYS answer with pure JSON — no prose, no markdown fences."
)


def _clean_code_sample(value):
    """LLM sometimes returns code_sample as {language, code} — coerce to str."""
    if isinstance(value, dict):
        return value.get("code") or None
    return value if isinstance(value, str) and value.strip() else None


async def _ask(prompt: str, retries: int = 4) -> dict:
    async with _sem:
        for attempt in range(retries + 1):
            try:
                chat = LlmChat(
                    api_key=os.environ["EMERGENT_LLM_KEY"],
                    session_id=f"contentgen-{uuid.uuid4()}",
                    system_message=SYSTEM,
                ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=8192)
                raw = await chat.send_message(UserMessage(text=prompt))
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                cleaned = cleaned.strip()
                try:
                    data = json.loads(cleaned, strict=False)
                except json.JSONDecodeError:
                    data = json_repair.loads(cleaned)  # tolerates truncation/bad escapes
                # Reject salvaged-but-gutted lessons so truncated calls retry.
                for l in data.get("lessons", []):
                    if len(l.get("content", "")) < 900:
                        raise ValueError(f"lesson content too short after parse ({len(l.get('content', ''))} chars)")
                return data
            except Exception as e:
                logger.warning(f"contentgen call failed (attempt {attempt + 1}): {e}")
                if attempt == retries:
                    raise
                await asyncio.sleep(3)


# ---------------- Stub courses: full curriculum ----------------

OUTLINE_PROMPT = """Design a 4-module curriculum for this course.

Course: {title}
Subtitle: {subtitle}
Category: {category} | Difficulty: {difficulty} | Duration: {duration_hours}h

Return JSON exactly:
{{"modules":[{{"number":1,"title":"…","summary":"1-sentence module summary","level":1,"duration_min":45,
   "lessons":[{{"title":"…","duration_min":12}},{{"title":"…","duration_min":12}},{{"title":"…","duration_min":12}}]}}, … 4 modules total]}}
Rules: module 1 has level 1, modules 2-3 level 2, module 4 level 3. 3 lessons per module.
Lesson titles must be specific and practical (no generic "Introduction to X" repetition)."""

MODULE_PROMPT = """Write the full lesson content for one module of the course "{course_title}" ({subtitle}).

Module {number}: {module_title} — {summary}
Lessons: {lesson_titles}

Return JSON exactly:
{{"lessons":[{{"title":"<same title>","content":"<350-450 words of markdown>","key_takeaways":["…","…","…"],"code_sample":null}}]}}
Content rules:
- Markdown with 2-3 "### " subheadings, **bold** key terms, `inline code` where apt.
- Concrete enterprise examples (name real frameworks, regulations, tools).
- Separate paragraphs with blank lines.
- code_sample: a short code/config snippet string ONLY where genuinely useful, else null.
- 3-5 key_takeaways, each a crisp sentence."""

QUIZ_PROMPT = """Write a 12-question certification quiz for the course "{title}" ({subtitle}).

Return JSON exactly:
{{"questions":[{{"question":"…","type":"mcq","options":["…","…","…","…"],"correct":[0],"explanation":"…","difficulty":"intermediate"}}]}}
Mix difficulties (4 beginner, 5 intermediate, 3 advanced). Exactly one correct index per question."""


async def build_stub_course(course: dict) -> None:
    slug = course["slug"]
    outline = await _ask(OUTLINE_PROMPT.format(**{
        "title": course["title"], "subtitle": course["subtitle"],
        "category": course["category"], "difficulty": course["difficulty"],
        "duration_hours": course.get("duration_hours", 20),
    }))

    async def gen_module(m):
        data = await _ask(MODULE_PROMPT.format(
            course_title=course["title"], subtitle=course["subtitle"],
            number=m["number"], module_title=m["title"], summary=m.get("summary", ""),
            lesson_titles=json.dumps([l["title"] for l in m.get("lessons", [])]),
        ))
        lessons = []
        for src, gen in zip(m.get("lessons", []), data["lessons"]):
            lessons.append(Lesson(
                title=gen.get("title") or src["title"],
                content=gen["content"],
                duration_min=src.get("duration_min", 12),
                code_sample=_clean_code_sample(gen.get("code_sample")),
                key_takeaways=[t for t in gen.get("key_takeaways", []) if isinstance(t, str)],
            ))
        return Module(
            number=m["number"], title=m["title"], summary=m.get("summary", ""),
            level=m.get("level", 2), duration_min=m.get("duration_min", 45),
            lessons=lessons,
        )

    modules = await asyncio.gather(*[gen_module(m) for m in outline["modules"]])
    update = {
        "modules": [m.model_dump() for m in modules],
        "has_full_content": True,
        "description": course.get("description") or course["subtitle"],
        "last_reviewed_at": now_iso(),
    }
    if not course.get("quiz"):
        quiz = await _ask(QUIZ_PROMPT.format(title=course["title"], subtitle=course["subtitle"]))
        update["quiz"] = [QuizQuestion(**q).model_dump() for q in quiz["questions"]]
    await db.courses.update_one({"slug": slug}, {"$set": update})
    logger.info(f"[contentgen] STUB DONE {slug}: {sum(len(m.lessons) for m in modules)} lessons")


# ---------------- Thin builder courses: enrichment ----------------

ENRICH_PROMPT = """Expand the lessons of this module of the course "{course_title}" into deep, competitive-grade learning material.

Module: {module_title}
Existing lessons (title + current brief text to expand while preserving intent):
{lessons_json}

Return JSON exactly:
{{"lessons":[{{"title":"<same title>","content":"<400-550 words of markdown>","key_takeaways":["…","…","…","…"],"code_sample":null}}]}}
Content rules: markdown with 3+ "### " subheadings, **bold** terms, blank-line paragraphs.
Each lesson MUST include: (1) a named framework, standard, regulation or tool treated in depth;
(2) a concrete enterprise case example with realistic numbers/metrics; (3) a "common pitfalls"
or "what practitioners get wrong" angle. Write at the depth of a paid executive-education
program — denser and more actionable than typical online courses. code_sample only where
genuinely useful (else null). Keep the SAME lesson order and titles. 4-5 key_takeaways."""

MIN_RICH_CHARS = 1500


async def enrich_course(course: dict) -> None:
    slug = course["slug"]

    async def enrich_module(mi, mod):
        lessons = mod.get("lessons", [])
        todo = [(li, l) for li, l in enumerate(lessons) if len(l.get("content", "")) < MIN_RICH_CHARS]
        if not todo:
            return 0
        count = 0
        # Chunk to 2 lessons per call so responses never truncate mid-JSON.
        for start in range(0, len(todo), 2):
            chunk = todo[start:start + 2]
            data = await _ask(ENRICH_PROMPT.format(
                course_title=course["title"], module_title=mod["title"],
                lessons_json=json.dumps([
                    {"title": l["title"], "brief": l.get("content", "")[:400]} for _, l in chunk
                ]),
            ))
            for (li, old), gen in zip(chunk, data["lessons"]):
                fields = {
                    "content": gen["content"],
                    "key_takeaways": [t for t in gen.get("key_takeaways", old.get("key_takeaways", [])) if isinstance(t, str)],
                    "code_sample": _clean_code_sample(gen.get("code_sample")) or _clean_code_sample(old.get("code_sample")),
                }
                await db.courses.update_one(
                    {"slug": slug},
                    {"$set": {f"modules.{mi}.lessons.{li}.{k}": v for k, v in fields.items()}},
                )
                # Persist so course re-seeding on restart can re-apply the content.
                await db.lesson_content_overrides.update_one(
                    {"lesson_id": old["id"]},
                    {"$set": {"lesson_id": old["id"], **fields, "updated_at": now_iso()}},
                    upsert=True,
                )
                count += 1
        return count

    results = await asyncio.gather(
        *[enrich_module(mi, m) for mi, m in enumerate(course.get("modules", []))],
        return_exceptions=True,
    )
    ok = [r for r in results if isinstance(r, int)]
    errs = [r for r in results if not isinstance(r, int)]
    logger.info(f"[contentgen] ENRICH DONE {slug}: {sum(ok)} lessons expanded, {len(errs)} module errors")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("all", "stubs"):
        stubs = await db.courses.find(
            {"$or": [{"modules": {"$size": 0}}, {"modules": None}]}, {"_id": 0}
        ).to_list(50)
        logger.info(f"[contentgen] {len(stubs)} stub courses to build")
        for c in stubs:
            try:
                await build_stub_course(c)
            except Exception:
                logger.exception(f"[contentgen] stub failed: {c['slug']} — continuing")

    if mode in ("all", "thin"):
        thin = []
        async for c in db.courses.find({"has_full_content": True}, {"_id": 0}):
            lessons = [l for m in c.get("modules", []) for l in m.get("lessons", [])]
            if lessons and any(len(l.get("content", "")) < MIN_RICH_CHARS for l in lessons):
                thin.append(c)
        logger.info(f"[contentgen] {len(thin)} thin courses to enrich")
        for c in thin:
            try:
                await enrich_course(c)
            except Exception:
                logger.exception(f"[contentgen] enrich failed: {c['slug']} — continuing")

    logger.info("[contentgen] ALL DONE")


if __name__ == "__main__":
    asyncio.run(main())

