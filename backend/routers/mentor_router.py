"""AI Mentor — career/AI-advisor persona.

Separate from Aletheia (the in-lesson Tutor).
Mentor focuses on career pathing, skill gaps, certification roadmaps, and
interview-style guidance. Uses persistent chat history per user.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user_id
from core import db, logger, now_iso

router = APIRouter(prefix="/api", tags=["mentor"])


MENTOR_SYSTEM_PROMPT = """You are Solon, the AI Career Mentor for ITHR Technologies' Enterprise Agentic AI Academy — a top-tier certification body preparing professionals for roles in the AI-native economy.

Your voice:
- Warm, approachable, and encouraging — a friendly guide, not a technical expert lecturing.
- Speak in plain, everyday language. Assume NOTHING about the learner's technical background.
- Avoid jargon and acronyms. If a technical term is truly needed, immediately explain it in one simple sentence (e.g. "RAG — basically teaching an AI to look things up before it answers").
- Keep it gentle and simple: short, easy-to-read answers (3-6 sentences), one clear suggestion at a time rather than overwhelming lists.
- Lead with guidance and reassurance ("here's a good next step for you"), not diagnosis or gatekeeping.
- Be curious and patient — if you're unsure of their level, ask a friendly question instead of assuming.
- Never claims to be Claude or any specific model. You are Solon.

Adapt to the person: whether they're a complete beginner or a seasoned executive, keep the interaction light, human, and guidance-oriented. Meet them where they are and make AI feel accessible, never intimidating.

You have deep familiarity with ITHR Technologies' credential ladder:
1. Agentic AI Foundation (entry)
2. Agentic AI Practitioner
3. Agentic AI Professional (capstone)
4. Agentic AI Specialist (domain: banking, healthcare, manufacturing, retail, government)
5. Agentic AI Expert
6. Agentic AI Architect
7. Enterprise AI Leader
8. Chief AI Officer Track

You also know ITHR's course catalog covers: prompt engineering, RAG, multi-agent systems, AI governance & compliance, AI security & red-teaming, industry tracks, MLOps for AI, MCP & A2A protocols, and vector databases.

When a learner shares their role, industry, or experience, gently:
- Reflect back what you heard in simple terms and reassure them there's a clear path.
- Suggest the next 1-2 courses and the next credential — framed as a friendly recommendation, not a verdict.
- Offer a light, doable 90-day plan with one small hands-on project they'd enjoy.
- Only mention rules/regulations (like the EU AI Act or HIPAA) if it's genuinely helpful, and explain in plain words why it matters to them.

When they ask "what should I study next?", point them to one specific ITHR course by its exact title and the credential it leads toward — kept simple and encouraging.
"""


class MentorRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[dict] = None  # {"role": ..., "industry": ..., "years": ...}


def _emergent_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="LLM key not configured")
    return key


def _build_chat(session_id: str, extra_context: Optional[str] = None, catalog_block: Optional[str] = None) -> LlmChat:
    system = MENTOR_SYSTEM_PROMPT
    if catalog_block:
        system += catalog_block
    if extra_context:
        system += f"\n\nLearner profile snapshot:\n{extra_context}\n\nUse this context to personalize every response."
    return LlmChat(
        api_key=_emergent_key(),
        session_id=session_id,
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")


async def _build_catalog_block() -> Optional[str]:
    """Inject the REAL, live course catalog so Solon never invents course titles.

    The model is instructed to reference courses ONLY by their exact title from
    this list. This grounds every recommendation in what actually exists.
    """
    courses = await db.courses.find(
        {}, {"_id": 0, "title": 1, "slug": 1, "category": 1}
    ).sort("title", 1).to_list(200)
    lines = [
        f'- "{c["title"]}" (slug: {c["slug"]}, category: {c.get("category", "")})'
        for c in courses if c.get("title")
    ]
    if not lines:
        return None
    catalog = "\n".join(lines)
    return (
        "\n\n=== ITHR LIVE COURSE CATALOG (authoritative — the ONLY courses that exist) ===\n"
        "You MUST reference courses using their EXACT title from this list, copied verbatim. "
        "NEVER invent, rename, paraphrase, translate, or guess a course title. If a learner's "
        "need has no exact match, say so plainly and recommend the closest real course(s) from "
        "this list. Do not cite any course title that is not in this list.\n"
        f"{catalog}\n"
        "=== END CATALOG ===\n"
    )


async def _build_context_block(payload_context: Optional[dict], user_id: str) -> Optional[str]:
    """Assemble a compact context block from request + stored user profile."""
    ctx_lines: list[str] = []
    if payload_context:
        for k, v in payload_context.items():
            if v:
                ctx_lines.append(f"- {k}: {v}")
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "title": 1, "organization": 1})
    if user_doc:
        if user_doc.get("title"):
            ctx_lines.append(f"- title: {user_doc['title']}")
        if user_doc.get("organization"):
            ctx_lines.append(f"- organization: {user_doc['organization']}")
    return "\n".join(ctx_lines) if ctx_lines else None


def _preamble_with_history(history: list[dict], new_message: str) -> str:
    """Feed prior turns as a preamble so the model has continuity even when
    the emergentintegrations session cache expires."""
    if not history:
        return new_message
    recap = "\n".join(f"{m['role'].upper()}: {m['content'][:400]}" for m in history[-6:])
    return f"Prior conversation summary (do not repeat):\n{recap}\n\nNew learner turn:\n{new_message}"


async def _persist_mentor_turn(
    session_id: str, user_id: str, existing_session: Optional[dict],
    user_message: str, assistant_message: str,
) -> None:
    user_msg = {"role": "user", "content": user_message, "timestamp": now_iso()}
    ai_msg = {"role": "assistant", "content": assistant_message, "timestamp": now_iso()}
    # Single idempotent upsert keyed by session id. Prevents the double-write
    # that produced duplicate threads in the "Past Conversations" sidebar when
    # a brand-new session was saved concurrently.
    await db.mentor_sessions.update_one(
        {"id": session_id},
        {
            "$push": {"messages": {"$each": [user_msg, ai_msg]}},
            "$set": {"updated_at": now_iso()},
            "$setOnInsert": {
                "id": session_id,
                "user_id": user_id,
                "title": user_message[:60],
                "created_at": now_iso(),
            },
        },
        upsert=True,
    )


@router.post("/mentor/chat")
async def mentor_chat(payload: MentorRequest, user_id: str = Depends(get_current_user_id)):
    session_id = payload.session_id or str(uuid.uuid4())
    session = await db.mentor_sessions.find_one(
        {"id": session_id, "user_id": user_id}, {"_id": 0}
    )
    history = session.get("messages", []) if session else []
    context_block = await _build_context_block(payload.context, user_id)
    catalog_block = await _build_catalog_block()
    chat = _build_chat(session_id, context_block, catalog_block)
    prompt = _preamble_with_history(history, payload.message)

    async def event_generator():
        collected: list[str] = []
        try:
            async for event in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(event, TextDelta):
                    collected.append(event.content)
                    yield f"data: {json.dumps({'delta': event.content})}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            logger.exception("Mentor error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        await _persist_mentor_turn(session_id, user_id, session, payload.message, "".join(collected))
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/mentor/sessions")
async def list_mentor_sessions(user_id: str = Depends(get_current_user_id)):
    sessions = await db.mentor_sessions.find(
        {"user_id": user_id}, {"_id": 0, "messages": 0}
    ).sort("updated_at", -1).to_list(50)
    return sessions


@router.get("/mentor/sessions/{session_id}")
async def get_mentor_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    session = await db.mentor_sessions.find_one(
        {"id": session_id, "user_id": user_id}, {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/mentor/sessions/{session_id}")
async def delete_mentor_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    res = await db.mentor_sessions.delete_one({"id": session_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}
