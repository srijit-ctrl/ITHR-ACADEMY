"""PulseDesk router — powers the embeddable conversational widget.

Public endpoints (called by the widget on any host site):
    GET  /api/pulsedesk/widget.js            Static widget script (adapted for SSE/HTTP)
    GET  /api/pulsedesk/config/{widget_key}  Public tenant config (name, colour, greeting)
    POST /api/pulsedesk/visitor/join         Idempotent visitor bootstrap; returns history + greeting
    POST /api/pulsedesk/visitor/message      Visitor -> AI. Returns AI reply in the response.
    POST /api/pulsedesk/visitor/callback     Visitor requests a phone callback

Super-admin endpoints (used by the admin console):
    GET  /api/admin/pulsedesk/conversations  All conversations, newest first
    GET  /api/admin/pulsedesk/conversations/{id}/messages
    GET  /api/admin/pulsedesk/callbacks

The widget is deliberately non-realtime for the MVP — a POST -> AI reply
round-trip keeps infra simple and reliable through the existing K8s ingress
(no WebSocket upgrades to worry about). Human agent takeover can be layered
in later via SSE without touching the current happy path.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from auth import get_current_super_admin
from core import logger
from pulsedesk_service import (
    DEFAULT_TENANT_KEY,
    append_message,
    generate_ai_reply,
    get_or_create_conversation,
    get_tenant_public,
    list_all_conversations,
    list_callback_requests,
    list_messages,
    record_callback_request,
)

router = APIRouter(prefix="/api/pulsedesk", tags=["pulsedesk"])
admin_router = APIRouter(prefix="/api/admin/pulsedesk", tags=["admin-pulsedesk"])

# ---- Static widget serve --------------------------------------------------

_WIDGET_JS_PATH = Path(__file__).resolve().parent.parent / "pulsedesk_widget" / "widget.js"


@router.get("/widget.js")
async def serve_widget_js():
    """Serve the client-side widget as a static file.

    The widget is placed under `/app/backend/pulsedesk_widget/widget.js` so
    it's part of the same repo. Cache is deliberately short (5 min) so
    updates propagate to embedded sites quickly during rollouts.
    """
    if not _WIDGET_JS_PATH.exists():
        raise HTTPException(status_code=404, detail="widget.js not built into backend image")
    return FileResponse(
        _WIDGET_JS_PATH,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


# ---- Payloads --------------------------------------------------------------


class VisitorJoinPayload(BaseModel):
    widget_key: str
    visitor_id: str = Field(min_length=4, max_length=64)
    visitor_meta: Optional[dict] = None
    page_context: Optional[str] = Field(default=None, max_length=3000)


class VisitorMessagePayload(BaseModel):
    widget_key: str
    visitor_id: str = Field(min_length=4, max_length=64)
    text: str = Field(min_length=1, max_length=2000)
    page_context: Optional[str] = Field(default=None, max_length=3000)


class CallbackPayload(BaseModel):
    widget_key: str
    visitor_id: str = Field(min_length=4, max_length=64)
    phone_number: str = Field(min_length=4, max_length=40)


# ---- Public: tenant config -------------------------------------------------


@router.get("/config/{widget_key}")
async def config_endpoint(widget_key: str):
    tenant = await get_tenant_public(widget_key)
    if not tenant:
        raise HTTPException(status_code=404, detail="unknown widget key")
    return {
        "name": tenant.get("name") or "Chat",
        "primaryColor": tenant.get("primary_color") or "#0A1B2A",
        "greeting": tenant.get("ai_greeting"),
    }


# ---- Public: visitor bootstrap ---------------------------------------------


@router.post("/visitor/join")
async def visitor_join(payload: VisitorJoinPayload):
    tenant = await get_tenant_public(payload.widget_key)
    if not tenant:
        raise HTTPException(status_code=404, detail="unknown widget key")
    conv = await get_or_create_conversation(
        widget_key=payload.widget_key,
        visitor_id=payload.visitor_id,
        visitor_meta=payload.visitor_meta or {},
    )
    messages = await list_messages(conv["id"], limit=100)
    return {
        "conversation_id": conv["id"],
        "messages": messages,
        "greeting": tenant.get("ai_greeting") if not messages else None,
    }


# ---- Public: visitor sends message → AI reply ------------------------------


@router.post("/visitor/message")
async def visitor_message(payload: VisitorMessagePayload, request: Request):
    tenant = await get_tenant_public(payload.widget_key)
    if not tenant:
        raise HTTPException(status_code=404, detail="unknown widget key")
    # Fetch existing meta so we can merge (don't clobber richer data captured on /visitor/join)
    referer = request.headers.get("referer", "")
    from core import db as _db
    existing = await _db.pulsedesk_conversations.find_one(
        {"widget_key": payload.widget_key, "visitor_id": payload.visitor_id},
        {"_id": 0, "visitor_meta": 1},
    )
    merged_meta = {**(existing.get("visitor_meta") if existing else {} or {})}
    if referer and "url" not in merged_meta:
        merged_meta["url"] = referer

    conv = await get_or_create_conversation(
        widget_key=payload.widget_key,
        visitor_id=payload.visitor_id,
        visitor_meta=merged_meta,
    )

    # 1) Persist the visitor message
    visitor_msg = await append_message(
        conversation_id=conv["id"],
        sender_type="visitor",
        text=payload.text.strip(),
        page_context=payload.page_context,
    )

    # 2) If this conversation is under human control, skip AI and return
    #    only the visitor echo — the human will reply through the admin UI.
    if conv.get("status") == "agent":
        return {"visitor_message": visitor_msg, "ai_message": None, "status": "agent"}

    # 3) Generate AI reply (never raises — falls back to rule-based responder)
    try:
        ai_text = await generate_ai_reply(conv, payload.text, page_context=payload.page_context)
    except Exception:
        logger.exception("[pulsedesk] AI reply generation failed")
        ai_text = "I'm having trouble reaching my brain right now — tap 'Request a callback' below and someone from the team will follow up."
    ai_msg = await append_message(
        conversation_id=conv["id"],
        sender_type="ai",
        text=ai_text,
    )
    return {"visitor_message": visitor_msg, "ai_message": ai_msg, "status": "ai"}


# ---- Public: callback request ---------------------------------------------


@router.post("/visitor/callback")
async def visitor_callback(payload: CallbackPayload, request: Request):
    tenant = await get_tenant_public(payload.widget_key)
    if not tenant:
        raise HTTPException(status_code=404, detail="unknown widget key")
    conv = await get_or_create_conversation(
        widget_key=payload.widget_key,
        visitor_id=payload.visitor_id,
        visitor_meta={"url": request.headers.get("referer", "")},
    )
    doc = await record_callback_request(
        widget_key=payload.widget_key,
        visitor_id=payload.visitor_id,
        phone_number=payload.phone_number,
        conversation_id=conv["id"],
    )
    # Also record as a "system" message inside the conversation so the
    # visitor's history shows they've asked for a callback.
    await append_message(
        conversation_id=conv["id"],
        sender_type="system",
        text=f"Callback requested — someone will call {doc['phone_number']} shortly.",
    )
    return {"ok": True, "callback_id": doc["id"]}


# ---- Super-admin: conversation inbox --------------------------------------


@admin_router.get("/conversations")
async def admin_list_conversations(
    limit: int = 200,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    convs = await list_all_conversations(limit=limit)
    return {"conversations": convs, "count": len(convs)}


@admin_router.get("/conversations/{conversation_id}/messages")
async def admin_conversation_messages(
    conversation_id: str,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    return {"messages": await list_messages(conversation_id, limit=500)}


@admin_router.get("/callbacks")
async def admin_list_callbacks(
    limit: int = 100,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    return {"callbacks": await list_callback_requests(limit=limit)}


@admin_router.get("/default-widget-key")
async def default_widget_key(_super_admin_id: str = Depends(get_current_super_admin)):
    """Debug helper — returns the bootstrapped ITHR tenant widget key so an
    operator can verify what the embed script is pointing at."""
    return {"widget_key": DEFAULT_TENANT_KEY}
