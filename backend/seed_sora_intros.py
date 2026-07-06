"""Sora 2 course-intro video generation pipeline.

Given a course slug, generate a ~8-second cinematic intro video with
Sora 2, save it to `/app/frontend/public/course-intros/<slug>.mp4`,
and set `course.intro_video_url` on the course doc so the frontend
switches from Ken-Burns cinemagraphs to the real motion video.

Usage:
    # Generate for a single course
    python -m seed_sora_intros --slug agentic-ai-foundations

    # Generate for all courses missing intro_video_url
    python -m seed_sora_intros --all

    # Force regenerate
    python -m seed_sora_intros --slug X --force
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_sora_intros")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

if not (MONGO_URL and DB_NAME and EMERGENT_LLM_KEY):
    raise SystemExit("MONGO_URL, DB_NAME, EMERGENT_LLM_KEY must be set.")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

OUTPUT_DIR = "/app/frontend/public/course-intros"
PUBLIC_URL_PREFIX = "/course-intros"  # served from frontend public/
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _prompt_for(course: dict) -> str:
    """Craft a Sora 2 prompt tuned for an enterprise AI-training course intro."""
    title = course.get("title", "AI Training")
    category = course.get("category", "AI")
    industries = ", ".join((course.get("industries") or [])[:3]) or "enterprise"
    return (
        f"A cinematic 8-second course intro for an enterprise AI training academy. "
        f"Theme: {title} — {category}. Aesthetic: sleek, modern, professional, "
        f"teal ({'#00A78B'}) and deep navy ({'#16335E'}) color palette with subtle gold accents. "
        f"Show close-up macro shots of glowing circuit patterns, layered translucent data visualizations, "
        f"floating holographic UI elements representing {industries} workflows, and abstract flowing "
        f"neural network graphs. Slow, deliberate camera moves — dolly-in and gentle rotation. "
        f"Cinematic lighting with soft rim lights. NO on-screen text, NO people, NO logos. "
        f"Photorealistic corporate feel, like a Fortune-500 keynote opener."
    )


def _generate_video(prompt: str, output_path: str, model: str = "sora-2") -> str | None:
    """Blocking Sora 2 call — run in a thread executor from async code."""
    video_gen = OpenAIVideoGeneration(api_key=EMERGENT_LLM_KEY)
    video_bytes = video_gen.text_to_video(
        prompt=prompt,
        model=model,
        size="1280x720",
        duration=8,
        max_wait_time=900,
    )
    if not video_bytes:
        return None
    video_gen.save_video(video_bytes, output_path)
    return output_path


async def generate_for_slug(slug: str, force: bool = False, model: str = "sora-2") -> bool:
    course = await db.courses.find_one({"slug": slug}, {"_id": 0})
    if not course:
        log.error(f"[{slug}] Course not found.")
        return False
    output_path = os.path.join(OUTPUT_DIR, f"{slug}.mp4")
    if os.path.exists(output_path) and course.get("intro_video_url") and not force:
        log.info(f"[{slug}] Intro video already present — skipping (pass --force to overwrite).")
        return False

    prompt = _prompt_for(course)
    log.info(f"[{slug}] Generating Sora 2 video (model={model})...")
    log.debug(f"[{slug}] Prompt: {prompt[:180]}...")
    try:
        result = await asyncio.to_thread(_generate_video, prompt, output_path, model)
    except Exception as e:
        log.exception(f"[{slug}] Sora 2 generation raised: {e}")
        return False
    if not result:
        log.error(f"[{slug}] Sora 2 returned no bytes.")
        return False

    public_url = f"{PUBLIC_URL_PREFIX}/{slug}.mp4"
    await db.courses.update_one(
        {"slug": slug},
        {"$set": {
            "intro_video_url": public_url,
            "intro_video_generated_at": datetime.now(timezone.utc).isoformat(),
            "intro_video_model": model,
        }},
    )
    file_size_kb = os.path.getsize(output_path) // 1024
    log.info(f"[{slug}] ✅ Saved {file_size_kb} KB → {public_url}")
    return True


async def generate_all(force: bool = False, model: str = "sora-2") -> None:
    query = {} if force else {"intro_video_url": {"$in": [None, ""]}}
    cursor = db.courses.find(query, {"slug": 1, "title": 1, "_id": 0})
    slugs = [c["slug"] async for c in cursor]
    log.info(f"Sora 2 batch for {len(slugs)} courses: {slugs}")
    for idx, slug in enumerate(slugs, start=1):
        log.info(f"=== ({idx}/{len(slugs)}) {slug} ===")
        await generate_for_slug(slug, force=force, model=model)


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", help="Course slug to generate intro video for.")
    g.add_argument("--all", action="store_true", help="Generate videos for ALL courses missing one.")
    p.add_argument("--force", action="store_true", help="Regenerate even if intro_video_url is set.")
    p.add_argument("--model", default="sora-2", choices=["sora-2", "sora-2-pro"])
    args = p.parse_args()
    if args.all:
        asyncio.run(generate_all(force=args.force, model=args.model))
    else:
        ok = asyncio.run(generate_for_slug(args.slug, force=args.force, model=args.model))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
