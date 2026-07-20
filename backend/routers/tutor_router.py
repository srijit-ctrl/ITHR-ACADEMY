"""AI Tutor + course generator routes."""
import json
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai_service import CHAT_MODELS, DEFAULT_TUTOR_MODEL, generate_course_outline, get_tutor_persona, resolve_model, stream_tutor_response, TUTOR_META_MARKER
from auth import get_current_user_id
from core import db, logger, now_iso
from models import ChatMessage, ChatRequest, ChatSession

router = APIRouter(prefix="/api", tags=["ai"])


class TutorRating(BaseModel):
    session_id: str
    turn_index: int = Field(ge=0, description="0-based index of the assistant message within its session")
    rating: Literal["up", "down"]
    reason: Optional[str] = Field(default=None, max_length=500)


@router.post("/ai/tutor")
async def ai_tutor(payload: ChatRequest, user_id: str = Depends(get_current_user_id)):
    from security_service import flag_enabled
    if not await flag_enabled("ai_tutor"):
        raise HTTPException(status_code=403, detail="The AI tutor is currently disabled")
    if payload.mode == "quiz" and not await flag_enabled("chat_quiz"):
        raise HTTPException(status_code=403, detail="In-chat quizzes are currently disabled")
    session_id = payload.session_id or str(uuid.uuid4())
    session = await db.chat_sessions.find_one({"id": session_id, "user_id": user_id}, {"_id": 0})
    history = session["messages"] if session else []

    course = None
    if payload.course_context:
        course = await db.courses.find_one(
            {"slug": payload.course_context},
            {"_id": 0, "title": 1, "subtitle": 1, "category": 1, "difficulty": 1, "description": 1},
        )

    async def event_generator():
        collected = []
        try:
            async for chunk in stream_tutor_response(
                session_id=session_id, user_message=payload.message,
                course=course, history=history, mode=payload.mode,
                model_key=payload.model_key,
            ):
                collected.append(chunk)
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
        except Exception as e:
            logger.exception("AI tutor error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        full_response = "".join(collected)
        visible = full_response.split(TUTOR_META_MARKER, 1)[0].strip() if TUTOR_META_MARKER in full_response else full_response
        new_user_msg = ChatMessage(role="user", content=payload.message).model_dump()
        new_ai_msg = ChatMessage(role="assistant", content=visible).model_dump()

        if session:
            await db.chat_sessions.update_one(
                {"id": session_id},
                {"$push": {"messages": {"$each": [new_user_msg, new_ai_msg]}},
                 "$set": {"updated_at": now_iso()}},
            )
        else:
            new_session = ChatSession(
                id=session_id, user_id=user_id, title=payload.message[:60],
                messages=[ChatMessage(**new_user_msg), ChatMessage(**new_ai_msg)],
            )
            await db.chat_sessions.insert_one(new_session.model_dump())

        resolved_key, _, _ = resolve_model(payload.model_key)
        yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'model': resolved_key})}\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/ai/tutor-profile")
async def tutor_profile(course_slug: str = None, user_id: str = Depends(get_current_user_id)):
    category = None
    if course_slug:
        c = await db.courses.find_one({"slug": course_slug}, {"_id": 0, "category": 1})
        category = (c or {}).get("category")
    name, style = get_tutor_persona(category)
    return {"name": name, "style": style, "category": category}


@router.get("/ai/models")
async def list_chat_models():
    """Return the model options the tutor UI can offer. Kept a public
    read so an unauthenticated visitor previewing the tutor sees the
    same menu — the model_key is just a label, no secret leaks."""
    return {
        "default": DEFAULT_TUTOR_MODEL,
        "models": [
            {
                "key": key,
                "provider": provider,
                "model_id": model_id,
                "label": _label_for(key),
            }
            for key, (provider, model_id) in CHAT_MODELS.items()
        ],
    }


_MODEL_LABELS = {
    "claude-sonnet-4.5": "Claude Sonnet 4.5 · Balanced",
    "claude-sonnet-4.6": "Claude Sonnet 4.6 · Balanced+",
    "gemini-3.5-flash": "Gemini 3.5 Flash · Fastest",
    "gemini-3.1-pro": "Gemini 3.1 Pro · Highest quality",
    "gemini-3-flash": "Gemini 3 Flash · Cheapest",
}


def _label_for(key: str) -> str:
    return _MODEL_LABELS.get(key, key)


@router.get("/ai/sessions")
async def list_chat_sessions(user_id: str = Depends(get_current_user_id)):
    sessions = await db.chat_sessions.find({"user_id": user_id}, {"_id": 0, "messages": 0}).sort("updated_at", -1).to_list(50)
    return sessions


@router.get("/ai/sessions/{session_id}")
async def get_chat_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    session = await db.chat_sessions.find_one({"id": session_id, "user_id": user_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/ai/generate-course")
async def ai_generate_course_endpoint(payload: dict, user_id: str = Depends(get_current_user_id)):
    topic = payload.get("topic", "").strip()
    audience = payload.get("audience", "enterprise professionals")
    if not topic:
        raise HTTPException(status_code=400, detail="Topic required")

    raw = await generate_course_outline(topic, audience)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned.strip())
        return {"outline": parsed, "raw": raw}
    except Exception:
        return {"outline": None, "raw": raw, "error": "Could not parse structured JSON — showing raw response."}



@router.post("/ai/tutor/rate")
async def rate_tutor_message(payload: TutorRating, user_id: str = Depends(get_current_user_id)):
    """Record a thumbs-up / thumbs-down rating for one assistant message in a session.

    One rating per (user, session, turn). Re-submitting overwrites the previous value —
    letting the learner change their mind without polluting analytics.
    """
    session = await db.chat_sessions.find_one(
        {"id": payload.session_id, "user_id": user_id},
        {"_id": 0, "messages": 1},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    assistant_msgs = [m for m in (session.get("messages") or []) if m.get("role") == "assistant"]
    if payload.turn_index >= len(assistant_msgs):
        raise HTTPException(status_code=400, detail="turn_index out of range")

    key = f"{user_id}|{payload.session_id}|{payload.turn_index}"
    await db.tutor_ratings.update_one(
        {"key": key},
        {"$set": {
            "key": key,
            "user_id": user_id,
            "session_id": payload.session_id,
            "turn_index": payload.turn_index,
            "rating": payload.rating,
            "reason": payload.reason,
            "updated_at": now_iso(),
        }, "$setOnInsert": {"created_at": now_iso()}},
        upsert=True,
    )
    return {"ok": True, "rating": payload.rating}


@router.get("/ai/tutor/ratings/{session_id}")
async def my_session_ratings(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Ratings the current learner has already submitted for this session — used
    by the tutor UI to render the correct thumb-up/down state on reload."""
    docs = await db.tutor_ratings.find(
        {"user_id": user_id, "session_id": session_id},
        {"_id": 0, "turn_index": 1, "rating": 1},
    ).to_list(500)
    return {"ratings": {str(d["turn_index"]): d["rating"] for d in docs}}
