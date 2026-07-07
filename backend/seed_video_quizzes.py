"""Seed sample lesson videos + interactive checkpoints (idempotent).

Attaches a video to the first lesson of the first two catalog courses and
creates 2 checkpoints each. Run: python seed_video_quizzes.py
"""
import asyncio
import uuid

from core import db, now_iso

SAMPLE_VIDEOS = [
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4",
]

QUESTIONS = [
    [
        {
            "timestamp_sec": 8,
            "question": "According to this lesson, what is the FIRST step before deploying an AI agent in production?",
            "options": [
                "Define the agent's scope, guardrails and success metrics",
                "Give the agent unrestricted tool access",
                "Skip evaluation and ship quickly",
                "Train a brand-new foundation model",
            ],
            "correct_index": 0,
        },
        {
            "timestamp_sec": 20,
            "question": "Which practice keeps an agentic workflow auditable?",
            "options": [
                "Deleting logs after every run",
                "Structured logging of every tool call and decision",
                "Hiding prompts from reviewers",
                "Disabling human review",
            ],
            "correct_index": 1,
        },
    ],
    [
        {
            "timestamp_sec": 8,
            "question": "What distinguishes an AI agent from a simple chatbot?",
            "options": [
                "It only answers questions",
                "It can plan, use tools and act toward a goal autonomously",
                "It never makes mistakes",
                "It requires no language model",
            ],
            "correct_index": 1,
        },
        {
            "timestamp_sec": 18,
            "question": "Why are checkpoint quizzes embedded in training videos?",
            "options": [
                "To make videos longer",
                "To verify comprehension before the learner continues",
                "To collect marketing data",
                "To replace the final certification exam",
            ],
            "correct_index": 1,
        },
    ],
]


async def main():
    courses = await db.courses.find({}, {"_id": 0, "id": 1, "slug": 1, "title": 1, "modules": 1}).sort("slug", 1).to_list(2)
    if not courses:
        print("No courses found — seed the catalog first.")
        return

    for idx, course in enumerate(courses):
        modules = course.get("modules") or []
        if not modules or not modules[0].get("lessons"):
            print(f"Skipping {course['slug']} — no lessons")
            continue
        lesson = modules[0]["lessons"][0]
        video_url = SAMPLE_VIDEOS[idx % len(SAMPLE_VIDEOS)]

        await db.courses.update_one(
            {"id": course["id"]},
            {"$set": {"modules.0.lessons.0.video_url": video_url}},
        )
        await db.lesson_videos.update_one(
            {"lesson_id": lesson["id"]},
            {"$set": {"lesson_id": lesson["id"], "video_url": video_url, "updated_at": now_iso()}},
            upsert=True,
        )

        await db.video_checkpoints.delete_many({"lesson_id": lesson["id"]})
        docs = []
        for q in QUESTIONS[idx % len(QUESTIONS)]:
            docs.append({
                "id": str(uuid.uuid4()),
                "course_id": course["id"],
                "lesson_id": lesson["id"],
                "created_at": now_iso(),
                **q,
            })
        await db.video_checkpoints.insert_many(docs)
        print(f"Seeded {course['slug']} / lesson '{lesson['title']}' -> video + {len(docs)} checkpoints")


if __name__ == "__main__":
    asyncio.run(main())
