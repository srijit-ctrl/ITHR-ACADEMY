"""Export LLM-generated course content from the DB into committed JSON assets
so PRODUCTION (separate DB) hydrates the same material at startup.

Outputs:
  assets/generated_courses/{slug}.json      — full modules+quiz for generated stub courses
  assets/generated_courses/content_overrides.json — positional lesson enrichment
      { slug: { "mi:li": {content, key_takeaways, code_sample} } } for builder courses

Run: python export_generated_content.py
"""
import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from core import db  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "generated_courses")

# Builder courses re-seed their modules from code at every boot; everything
# else with content was generated directly into the DB.
BUILDER_SLUGS_QUERY = {"has_full_content": True}


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Which slugs come from code builders? They are re-upserted each boot —
    # detect via seed: builder courses have 40+ lessons; generated stubs have ~12.
    overrides = {}
    stub_count = 0
    async for c in db.courses.find({}, {"_id": 0}):
        modules = c.get("modules") or []
        lessons = [l for m in modules for l in m.get("lessons", [])]
        if not lessons:
            continue
        if len(lessons) <= 20:
            # Generated stub course → export full modules + quiz
            payload = {
                "slug": c["slug"],
                "modules": modules,
                "quiz": c.get("quiz") or [],
            }
            with open(os.path.join(OUT_DIR, f"{c['slug']}.json"), "w") as f:
                json.dump(payload, f, ensure_ascii=False)
            stub_count += 1
        else:
            # Builder course → export positional enrichment overrides
            per = {}
            for mi, m in enumerate(modules):
                for li, l in enumerate(m.get("lessons", [])):
                    if len(l.get("content", "")) >= 1200:
                        per[f"{mi}:{li}"] = {
                            "content": l["content"],
                            "key_takeaways": l.get("key_takeaways", []),
                            "code_sample": l.get("code_sample"),
                        }
            if per:
                overrides[c["slug"]] = per

    with open(os.path.join(OUT_DIR, "content_overrides.json"), "w") as f:
        json.dump(overrides, f, ensure_ascii=False)

    total_ov = sum(len(v) for v in overrides.values())
    print(f"Exported {stub_count} full course files + positional overrides for "
          f"{len(overrides)} builder courses ({total_ov} lessons).")


if __name__ == "__main__":
    asyncio.run(main())
