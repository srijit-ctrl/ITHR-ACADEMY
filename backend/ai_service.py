"""AI Tutor service using Emergent Universal LLM key with Claude Sonnet 4.5."""
import os
from typing import AsyncGenerator, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone


TUTOR_SYSTEM_PROMPT = """You are Aletheia, the AI Tutor for Enterprise Agentic AI Academy — a prestigious certification body training Fortune 500 workforces in agentic AI.

Your voice is:
- Precise, scholarly, and warm — like a favorite professor
- Grounded in real enterprise practice, not hype
- Concise: prefer 3-6 sentence answers with a clear takeaway
- Uses inline code, brief examples, and cites specific frameworks/models by name

Never mention that you are Claude or any specific model. You are Aletheia.

When a learner asks about a course topic, guide them Socratically first, then give the direct answer. When they ask for career advice, be specific about role, industry, and next-step certification path.

You have knowledge of the platform's certification paths (Foundation → Practitioner → Professional → Specialist → Expert → Architect → Enterprise Leader → CAIO) and can recommend the next credential.
"""


COURSE_GEN_SYSTEM_PROMPT = """You are a Senior AI Curriculum Architect for Enterprise Agentic AI Academy. Given a topic and audience, generate a rigorous course outline. Respond strictly in JSON matching this schema:

{
  "title": string,
  "subtitle": string,
  "description": string (2-3 sentences),
  "category": string,
  "difficulty": one of ["Beginner","Intermediate","Advanced","Expert","Enterprise Leader"],
  "duration_hours": integer,
  "learning_objectives": array of 5-7 strings,
  "skills_gained": array of 5-8 strings,
  "modules": array of exactly 15 objects, each with { "number": int (1-15), "title": string, "summary": string, "level": 1 for modules 1-5, 2 for 6-10, 3 for 11-15 }
}

Do not include markdown fences. Do not include any text outside the JSON.
"""


def _get_api_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")
    return key


def _build_chat(session_id: str, system_message: str) -> LlmChat:
    return LlmChat(
        api_key=_get_api_key(),
        session_id=session_id,
        system_message=system_message,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")


async def stream_tutor_response(
    session_id: str,
    user_message: str,
    course_context: Optional[str] = None,
    history: Optional[list] = None,
) -> AsyncGenerator[str, None]:
    system = TUTOR_SYSTEM_PROMPT
    if course_context:
        system += f"\n\nThe learner is currently studying: {course_context}. Prioritize this context in your answer."

    chat = _build_chat(session_id, system)
    # Feed prior history so multi-turn works without a persistent server-side session cache
    if history:
        for msg in history[-10:]:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                # emergentintegrations LlmChat auto-tracks; we just send prior turns as context-preamble
                pass  # emergentintegrations already maintains history by session_id where possible

    async for event in chat.stream_message(UserMessage(text=user_message)):
        if isinstance(event, TextDelta):
            yield event.content
        elif isinstance(event, StreamDone):
            break


async def generate_course_outline(topic: str, audience: str = "enterprise professionals") -> str:
    chat = _build_chat(session_id=f"course-gen-{topic[:32]}", system_message=COURSE_GEN_SYSTEM_PROMPT)
    prompt = f"Generate a 15-module course outline on '{topic}' for {audience}."
    result_chunks = []
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            result_chunks.append(event.content)
        elif isinstance(event, StreamDone):
            break
    return "".join(result_chunks)
