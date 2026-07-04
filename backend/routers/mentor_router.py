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
- Direct, strategic, and empathetic — a senior mentor who has hired for and led AI teams at Fortune 500 companies.
- Frames advice in terms of *role → capability → credential → project*.
- Concise: 4-8 sentence answers with concrete next actions.
- Speaks in business plus technical language; skips jargon-for-jargon's sake.
- Never claims to be Claude or any specific model. You are Solon.

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

When a learner shares their role, industry, or years of experience, IMMEDIATELY:
- Diagnose their skill posture (strengths, gaps).
- Recommend the next 1-2 courses AND next credential.
- Suggest a 90-day plan with a concrete artifact/project.
- Flag any regulatory context (EU AI Act, NIST AI RMF, ISO 42001, HIPAA, SR 11-7) relevant to their industry.

When they ask "what should I study next?" default to the credential ladder anchor and a specific ITHR course slug.
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


def _build_chat(session_id: str, extra_context: Optional[str] = None) -> LlmChat:
    system = MENTOR_SYSTEM_PROMPT
    if extra_context:
        system += f"\n\nLearner profile snapshot:\n{extra_context}\n\nUse this context to personalize every response."
    return LlmChat(
        api_key=_emergent_key(),
        session_id=session_id,
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")


@router.post("/mentor/chat")
async def mentor_chat(payload: MentorRequest, user_id: str = Depends(get_current_user_id)):
    session_id = payload.session_id or str(uuid.uuid4())
    session = await db.mentor_sessions.find_one(
        {"id": session_id, "user_id": user_id}, {"_id": 0}
    )
    history = session.get("messages", []) if session else []

    # Attach persistent learner context if the user has a profile stored.
    ctx_lines = []
    if payload.context:
        for k, v in payload.context.items():
            if v:
                ctx_lines.append(f"- {k}: {v}")
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "title": 1, "organization": 1})
    if user_doc:
        if user_doc.get("title"):
            ctx_lines.append(f"- title: {user_doc['title']}")
        if user_doc.get("organization"):
            ctx_lines.append(f"- organization: {user_doc['organization']}")
    context_block = "\n".join(ctx_lines) if ctx_lines else None

    chat = _build_chat(session_id, context_block)

    async def event_generator():
        collected = []
        # Feed prior turns as a preamble so the model has continuity even
        # when emergentintegrations session-cache expires.
        preamble = None
        if history:
            recap = "\n".join(f"{m['role'].upper()}: {m['content'][:400]}" for m in history[-6:])
            preamble = f"Prior conversation summary (do not repeat):\n{recap}\n\nNew learner turn:\n{payload.message}"
        try:
            msg = UserMessage(text=preamble or payload.message)
            async for event in chat.stream_message(msg):
                if isinstance(event, TextDelta):
                    collected.append(event.content)
                    yield f"data: {json.dumps({'delta': event.content})}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            logger.exception("Mentor error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        full = "".join(collected)
        user_msg = {"role": "user", "content": payload.message, "timestamp": now_iso()}
        ai_msg = {"role": "assistant", "content": full, "timestamp": now_iso()}
        if session:
            await db.mentor_sessions.update_one(
                {"id": session_id},
                {"$push": {"messages": {"$each": [user_msg, ai_msg]}},
                 "$set": {"updated_at": now_iso()}},
            )
        else:
            await db.mentor_sessions.insert_one({
                "id": session_id,
                "user_id": user_id,
                "title": payload.message[:60],
                "messages": [user_msg, ai_msg],
                "created_at": now_iso(),
                "updated_at": now_iso(),
            })
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
