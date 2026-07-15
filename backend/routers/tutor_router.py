"""AI Tutor + course generator routes."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ai_service import generate_course_outline, get_tutor_persona, stream_tutor_response, TUTOR_META_MARKER
from auth import get_current_user_id
from core import db, logger, now_iso
from models import ChatMessage, ChatRequest, ChatSession

router = APIRouter(prefix="/api", tags=["ai"])


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

        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

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
