"""PulseDesk — embeddable conversational widget service.

Data model:
    pulsedesk_tenants        one per client site (multi-tenant support)
    pulsedesk_conversations  one per visitor (identified by visitor_id in localStorage)
    pulsedesk_messages       one per exchange

Business rules:
    * Each site embed carries a `widget_key` — no cross-tenant data leak.
    * Visitors are anonymous, keyed only by localStorage `pulsedesk_visitor_id`.
    * AI replies use the ITHR Emergent LLM key via emergentintegrations. A
      light rule-based fallback covers the case where the LLM call fails.
    * Zero PII — we never persist visitor IP/email unless they voluntarily
      submit a callback request.

Bootstrap: `ensure_ithr_tenant()` guarantees the "ithr-academy-live" tenant
exists at server startup, so the widget can begin working immediately with
no manual /register step.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from ai_service import _build_chat  # reuse the existing Emergent LLM plumbing
from core import db, logger
from emergentintegrations.llm.chat import StreamDone, TextDelta, UserMessage
from models import gen_id

TENANTS = "pulsedesk_tenants"
CONVERSATIONS = "pulsedesk_conversations"
MESSAGES = "pulsedesk_messages"
CALLBACKS = "pulsedesk_callback_requests"

DEFAULT_TENANT_KEY = "ithr-academy-live"

_HISTORY_LIMIT = 12  # last 12 messages carried into the AI system prompt
_AI_REPLY_MAX_CHARS = 1400


# ---- Index bootstrap ------------------------------------------------------


async def ensure_indexes() -> None:
    await db[TENANTS].create_index("widget_key", unique=True)
    await db[TENANTS].create_index("agent_token", unique=True, sparse=True)
    await db[CONVERSATIONS].create_index([("widget_key", 1), ("visitor_id", 1)], unique=True)
    await db[CONVERSATIONS].create_index([("last_message_at", -1)])
    await db[MESSAGES].create_index([("conversation_id", 1), ("created_at", 1)])
    await db[CALLBACKS].create_index([("created_at", -1)])


async def ensure_ithr_tenant() -> dict:
    """Idempotent — creates the default ITHR tenant on first boot.

    Returns the tenant dict. Called from `startup_event` in server.py so the
    widget key is ready by the time the first browser request arrives.
    """
    await ensure_indexes()
    existing = await db[TENANTS].find_one({"widget_key": DEFAULT_TENANT_KEY}, {"_id": 0})
    if existing:
        return existing

    tenant = {
        "widget_key": DEFAULT_TENANT_KEY,
        "name": "ITHR Academy",
        "primary_color": "#16335E",
        "agent_token": secrets.token_urlsafe(32),
        "ai_greeting": (
            "Hi — I'm Aletheia, the ITHR Academy assistant. Ask me about any "
            "course, module, or credential — or how the platform works. If you'd "
            "like a human to jump in, request a callback below."
        ),
        "created_at": _now(),
    }
    try:
        await db[TENANTS].insert_one(tenant)
        logger.info(f"[pulsedesk] Provisioned default tenant (widget_key={DEFAULT_TENANT_KEY})")
    except Exception:
        # Duplicate-key race — the other coroutine won; return the winner.
        return await db[TENANTS].find_one({"widget_key": DEFAULT_TENANT_KEY}, {"_id": 0})
    return tenant


# ---- Helpers ---------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_tenant_public(widget_key: str) -> Optional[dict]:
    """Public tenant config — safe to return to any visitor."""
    doc = await db[TENANTS].find_one(
        {"widget_key": widget_key},
        {"_id": 0, "name": 1, "primary_color": 1, "widget_key": 1, "ai_greeting": 1},
    )
    return doc


async def get_or_create_conversation(
    widget_key: str, visitor_id: str, visitor_meta: dict | None = None
) -> dict:
    """Idempotent — one conversation per (widget, visitor)."""
    conv = await db[CONVERSATIONS].find_one(
        {"widget_key": widget_key, "visitor_id": visitor_id}, {"_id": 0}
    )
    if conv:
        return conv
    conv = {
        "id": gen_id(),
        "widget_key": widget_key,
        "visitor_id": visitor_id,
        "visitor_meta": visitor_meta or {},
        "status": "ai",
        "created_at": _now(),
        "last_message_at": _now(),
        "message_count": 0,
    }
    try:
        await db[CONVERSATIONS].insert_one(conv)
    except Exception:
        # Race — the other coroutine won; return the winner
        return await db[CONVERSATIONS].find_one(
            {"widget_key": widget_key, "visitor_id": visitor_id}, {"_id": 0}
        )
    return conv


async def append_message(
    conversation_id: str,
    sender_type: str,
    text: str,
    *,
    page_context: Optional[str] = None,
    meta: Optional[dict] = None,
) -> dict:
    """Persist a message and bump the conversation's last_message_at."""
    now = _now()
    doc = {
        "id": gen_id(),
        "conversation_id": conversation_id,
        "sender_type": sender_type,  # visitor | ai | agent | system
        "text": text,
        "created_at": now,
    }
    if page_context:
        doc["page_context"] = page_context[:3000]
    if meta:
        doc["meta"] = meta
    await db[MESSAGES].insert_one(doc)
    await db[CONVERSATIONS].update_one(
        {"id": conversation_id},
        {"$set": {"last_message_at": now}, "$inc": {"message_count": 1}},
    )
    return {k: v for k, v in doc.items() if k != "_id"}


async def list_messages(conversation_id: str, limit: int = 200) -> list[dict]:
    limit = max(1, min(500, limit))
    return await db[MESSAGES].find(
        {"conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(limit)


# ---- AI reply --------------------------------------------------------------


PULSEDESK_SYSTEM_PROMPT = """You are Aletheia — a warm, concise, high-signal
conversational assistant embedded in the ITHR Academy site.

Your job:
- Answer questions about the courses, credentials, HR-transformation stack,
  enterprise pricing, and how the platform works.
- Ground answers in the page-context passed with each message when available.
- Recommend the most relevant next step (browse the catalog, sit an
  assessment, book a demo) when the visitor's intent is clear.
- If the visitor asks something you can't verify from context, say so and
  offer to route them to a human via the "Request a callback" option.

Style:
- 1–3 short paragraphs, no walls of text.
- Plain English. No markdown headers, no bullet lists longer than 4 items.
- Never invent pricing, module names, or certifications. If unsure, say
  "let me get a human to confirm".

Refusals:
- Politely decline off-brand or off-topic requests (personal advice, other
  companies' products, unrelated technical support).
"""


def _build_conversation_prompt(
    system: str, history: list[dict], page_context: Optional[str]
) -> str:
    """Compose a system prompt with rolling conversation memory."""
    parts = [system]
    if page_context:
        parts.append(f"\n\nPAGE CONTEXT (what the visitor is currently viewing):\n{page_context[:2500]}")
    if history:
        rows = []
        for m in history[-_HISTORY_LIMIT:]:
            speaker = {"visitor": "Visitor", "ai": "You", "agent": "Team"}.get(m["sender_type"], "Note")
            rows.append(f"{speaker}: {m['text'][:600]}")
        parts.append("\n\nRECENT CONVERSATION (most recent last):\n" + "\n".join(rows))
    return "\n".join(parts)


def _fallback_reply(user_text: str) -> str:
    """Zero-config rule-based reply used when the LLM call fails.

    Kept deliberately small — surfaces the callback CTA fast so the visitor
    is never left in a dead conversation.
    """
    t = (user_text or "").lower().strip()
    if any(k in t for k in ("price", "cost", "how much", "pricing")):
        return (
            "Pricing for enterprise programs is tailored to seat count and cohort length. "
            "The public catalog and consumer credential pricing are on /pricing. "
            "Want me to have someone reach out with a quote?"
        )
    if any(k in t for k in ("demo", "trial", "try", "test drive")):
        return (
            "Yes — you can browse the full catalog and try any published course preview. "
            "For a full enterprise walkthrough, tap 'Request a callback' below and someone from "
            "the team will reach out."
        )
    if any(k in t for k in ("cert", "credential", "badge", "linkedin")):
        return (
            "Every completed course maps to a publicly verifiable digital credential — "
            "LinkedIn-shareable, with a QR code that resolves to a live ITHR verification page. "
            "Which course are you thinking about?"
        )
    if any(k in t for k in ("hi", "hello", "hey", "sup")):
        return "Hi — I'm Aletheia. What brings you to ITHR Academy today?"
    return (
        "Great question. I'm still learning — could you rephrase, or tap "
        "'Request a callback' if you'd like a human to weigh in?"
    )


async def generate_ai_reply(
    conversation: dict, user_text: str, page_context: Optional[str] = None
) -> str:
    """Generate an AI reply for a visitor message.

    Never raises — falls back to a rule-based responder if the LLM call
    fails so the conversation is never dead.
    """
    try:
        history = await list_messages(conversation["id"], limit=100)
        system = _build_conversation_prompt(PULSEDESK_SYSTEM_PROMPT, history, page_context)
        chat = _build_chat(
            session_id=f"pd:{conversation['id'][:16]}",
            system_message=system,
        )
        chunks: list[str] = []
        async for event in chat.stream_message(UserMessage(text=user_text)):
            if isinstance(event, TextDelta):
                chunks.append(event.content)
            elif isinstance(event, StreamDone):
                break
        reply = "".join(chunks).strip()
        if not reply:
            reply = _fallback_reply(user_text)
        return reply[:_AI_REPLY_MAX_CHARS]
    except Exception:
        logger.exception("[pulsedesk] LLM reply failed — using fallback responder")
        return _fallback_reply(user_text)


# ---- Callback capture -----------------------------------------------------


async def record_callback_request(
    widget_key: str,
    visitor_id: str,
    phone_number: str,
    conversation_id: Optional[str] = None,
) -> dict:
    doc = {
        "id": gen_id(),
        "widget_key": widget_key,
        "visitor_id": visitor_id,
        "conversation_id": conversation_id,
        "phone_number": phone_number.strip()[:40],
        "created_at": _now(),
        "status": "new",
    }
    await db[CALLBACKS].insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---- Admin read views -----------------------------------------------------


async def list_conversations_for_widget(widget_key: str, limit: int = 100) -> list[dict]:
    limit = max(1, min(500, limit))
    return await db[CONVERSATIONS].find(
        {"widget_key": widget_key}, {"_id": 0}
    ).sort("last_message_at", -1).to_list(limit)


async def list_all_conversations(limit: int = 200) -> list[dict]:
    limit = max(1, min(500, limit))
    return await db[CONVERSATIONS].find({}, {"_id": 0}).sort("last_message_at", -1).to_list(limit)


async def list_callback_requests(limit: int = 100) -> list[dict]:
    limit = max(1, min(500, limit))
    return await db[CALLBACKS].find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
