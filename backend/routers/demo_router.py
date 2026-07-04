"""Public anonymous demo endpoint — 'Try a lesson' on the landing page.

Streams Aletheia (Claude Sonnet 4.5) with a curated demo lesson prompt so
first-time visitors can experience the tutor without signing up.

Rate-limited by IP: 5 requests per 30-minute window to prevent abuse.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from collections import defaultdict

from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import logger

router = APIRouter(prefix="/api/demo", tags=["demo"])


DEMO_SYSTEM_PROMPT = """You are Aletheia — a scholarly, Socratic AI tutor for the ITHR Enterprise Agentic AI Academy.

You are helping a first-time visitor experience a mini-lesson on "What is an AI Agent?".

Rules:
- Keep answers concise (4-8 sentences).
- Use one crisp real-world analogy per answer.
- Never claim to be Claude or any specific model.
- If asked something completely off-topic (weather, sports), gently redirect to agentic AI.
- End every answer with ONE thought-provoking question to keep the learner engaged.
- No emoji. No bullet lists unless the learner explicitly asks for them.

Current lesson context:
- Definition: An agent is software that perceives, reasons, acts, and reflects to accomplish goals.
- Core loop: perceive → reason → act → reflect.
- Difference vs chatbots: agents take *actions* via tools, not just words.
- Enterprise examples: autonomous incident response, supply-chain rebalancing, compliance drafting.
"""


# ---- In-memory IP rate limiter (per-process; good enough for the demo) ----
_WINDOW_SEC = 30 * 60
_LIMIT = 5
_hits: dict[str, list[float]] = defaultdict(list)


def _check_rate(ip: str) -> tuple[bool, int]:
    now = time.time()
    _hits[ip] = [t for t in _hits[ip] if now - t < _WINDOW_SEC]
    if len(_hits[ip]) >= _LIMIT:
        return False, 0
    _hits[ip].append(now)
    return True, _LIMIT - len(_hits[ip])


class DemoAsk(BaseModel):
    message: str = Field(..., min_length=2, max_length=500)


@router.get("/lesson")
async def demo_lesson():
    """Return the fixed demo lesson content the frontend renders."""
    return {
        "id": "demo-what-is-an-agent",
        "title": "What is an AI Agent?",
        "duration_min": 4,
        "sections": [
            {
                "heading": "The one-line definition",
                "body": "An **AI agent** is software that perceives its environment, reasons about it, takes actions using tools, and reflects on the outcome to improve.",
            },
            {
                "heading": "The core loop",
                "body": "Every agent, from a customer-support assistant to an autonomous supply-chain planner, runs a variant of the same loop: **perceive → reason → act → reflect**. The action step is what separates agents from chatbots — an agent writes to a database, triggers a workflow, or calls an API.",
            },
            {
                "heading": "A concrete example",
                "body": "Imagine an AIOps agent watching your production logs. When it sees a spike in 500 errors, it *perceives* the anomaly, *reasons* about likely causes using history + docs, *acts* by rolling back the last deployment, then *reflects* by writing a post-mortem draft for the on-call engineer.",
            },
        ],
        "suggested_questions": [
            "How is an agent different from a normal chatbot?",
            "What are the biggest risks of deploying agents in banking?",
            "Can you give me one interview-style question about agents?",
        ],
    }


@router.post("/ask")
async def demo_ask(payload: DemoAsk, request: Request):
    """Stream Aletheia's answer to a demo question. Public + rate-limited."""
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "anon").split(",")[0].strip()
    allowed, remaining = _check_rate(ip)
    if not allowed:
        raise HTTPException(status_code=429, detail="Demo limit reached. Register for unlimited access to Aletheia.")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"demo-{uuid.uuid4().hex[:12]}",
        system_message=DEMO_SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    async def event_gen():
        yield f"data: {json.dumps({'remaining_in_window': remaining})}\n\n"
        try:
            async for event in chat.stream_message(UserMessage(text=payload.message)):
                if isinstance(event, TextDelta):
                    yield f"data: {json.dumps({'delta': event.content})}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            logger.exception("Demo stream failed")
            yield f"data: {json.dumps({'error': str(e)[:120]})}\n\n"
            return
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
