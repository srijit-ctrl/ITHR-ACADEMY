"""ITHR Command Assist — super-admin operations copilot.

Streams a Claude-Sonnet-4.5-grounded assistant that answers questions about
platform metrics, users, orgs, credentials, revenue, alerts, and Agent OS
runs. All context comes from live Mongo reads at call-time — never a stale
snapshot.

Security posture: every endpoint is guarded by `get_current_super_admin`.
The Emergent LLM key routes through `ai_service._build_chat`, so no new
provider key is required.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from emergentintegrations.llm.chat import UserMessage, TextDelta, StreamDone

from auth import get_current_super_admin
from core import db, now_iso
from ai_service import _build_chat

router = APIRouter(prefix="/api/admin/copilot", tags=["admin-copilot"])


COPILOT_SYSTEM_PROMPT = """You are **ITHR Command Assist** — a senior operations copilot embedded in the ITHR Agentic AI Academy super-admin console.

Your role: help the super admin understand what's happening on the platform right now and recommend concrete next actions. You do NOT run actions yourself; you point the operator to the right tab / endpoint / query.

Style:
- Concise, professional, executive-friendly. Prefer 1-3 short paragraphs, bullets when helpful.
- Ground every claim in the data snapshot provided below. If the data doesn't cover the question, say so plainly ("I can see A and B but not C — check the D tab for that").
- Use exact numbers from the snapshot when relevant.
- When suggesting a next step, name the specific admin tab in italic (e.g. *Enterprise leads*, *Agent OS*, *Audit log*, *Alerts*, *Email campaigns*, *AI operations*, *Security*).

Available admin tabs the user can jump to: Command Centre, Alerts, Analytics, Traffic, Organizations, Users, Enterprise leads, Widget conversations, Learning funnel, Assessments, Credentials, AI operations, Video quizzes, AI sessions, Email campaigns, Send email, Agent OS, Automations, Audit log, Security, Feature flags, WhatsApp.

Refuse: anything not tied to platform operations. No jokes, no personal opinions, no off-topic help.
"""


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    page_context: Optional[str] = Field(default=None, max_length=500)


async def _build_snapshot() -> dict:
    """Compact real-time snapshot of the platform: KPIs, alerts, hot signals.

    Deliberately small — everything here is inlined into the LLM system prompt.
    """
    now = datetime.now(timezone.utc)
    window_30d = (now - timedelta(days=30)).isoformat()
    window_7d = (now - timedelta(days=7)).isoformat()
    window_24h = (now - timedelta(hours=24)).isoformat()

    async def _count(col, q=None):
        return await db[col].count_documents(q or {})

    total_users = await _count("users")
    new_users_7d = await _count("users", {"created_at": {"$gte": window_7d}})
    active_24h = len(await db.user_login_logs.distinct("user_id", {"created_at": {"$gte": window_24h}}))
    active_30d = len(await db.user_login_logs.distinct("user_id", {"created_at": {"$gte": window_30d}}))
    total_orgs = await _count("organizations")
    total_enrollments = await _count("enrollments")
    completions = await _count("enrollments", {"completed": True})
    certs_30d = await _count("certificates", {"issued_at": {"$gte": window_30d}})
    total_certs = await _count("certificates")

    rev = await db.payment_transactions.aggregate([
        {"$match": {"payment_status": "paid", "created_at": {"$gte": window_30d}}},
        {"$group": {"_id": None, "total": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}}}},
    ]).to_list(1)
    revenue_30d = round((rev[0]["total"] if rev else 0) or 0, 2)

    # Recent alerts (open only)
    alerts = []
    async for a in db.admin_alert_states.find({"status": {"$in": ["open", "acknowledged"]}}, {"_id": 0}).limit(5):
        alerts.append({"key": a.get("key"), "status": a.get("status")})

    # New enterprise leads not yet contacted
    new_leads_count = await _count("enterprise_leads", {"status": "new"})

    # Agent OS: waiting_approval count
    waiting_approvals = await _count("agent_approval_queue", {"status": "pending"})
    total_pods = await _count("agent_pods", {"enabled": True})

    # PulseDesk conversations last 24h
    pd_convos_24h = await _count("pulsedesk_conversations", {"last_message_at": {"$gte": window_24h}})

    return {
        "generated_at": now_iso(),
        "users": {
            "total": total_users, "new_7d": new_users_7d,
            "active_24h": active_24h, "active_30d": active_30d,
        },
        "orgs": {"total": total_orgs},
        "learning": {
            "total_enrollments": total_enrollments,
            "completions": completions,
            "certificates_30d": certs_30d,
            "certificates_total": total_certs,
        },
        "revenue_30d_usd": revenue_30d,
        "alerts_open": len(alerts),
        "alerts_sample": alerts,
        "enterprise_leads_new": new_leads_count,
        "agent_os": {
            "enabled_pods": total_pods,
            "pending_approvals": waiting_approvals,
        },
        "pulsedesk_conversations_24h": pd_convos_24h,
    }


@router.get("/snapshot")
async def snapshot(_sa: str = Depends(get_current_super_admin)):
    """Copilot preview endpoint — returns the exact snapshot the copilot sees."""
    return await _build_snapshot()


def _sse(event: str, data) -> bytes:
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/chat")
async def copilot_chat(
    payload: CopilotChatRequest,
    request: Request,
    sa_id: str = Depends(get_current_super_admin),
):
    """SSE-streamed copilot reply. The final `done` event includes session_id."""
    session_id = payload.session_id or f"copilot-{uuid.uuid4().hex[:12]}"
    snap = await _build_snapshot()
    system = (
        COPILOT_SYSTEM_PROMPT
        + "\n\nCURRENT PLATFORM SNAPSHOT (real-time, do not repeat verbatim — cite what's relevant):\n"
        + json.dumps(snap, indent=2)
    )
    if payload.page_context:
        system += f"\n\nCurrent super-admin tab: {payload.page_context}"

    # Log the query for audit trail
    query_row_id = uuid.uuid4().hex
    await db.copilot_queries.insert_one({
        "id": query_row_id,
        "session_id": session_id,
        "actor_id": sa_id,
        "message": payload.message[:2000],
        "page_context": payload.page_context,
        "created_at": now_iso(),
    })

    async def event_stream():
        yield _sse("open", {"session_id": session_id, "snapshot_generated_at": snap["generated_at"]})
        chunks: list[str] = []
        try:
            chat = _build_chat(session_id=session_id, system_message=system, model_key="claude-sonnet-4.5")
            async for event in chat.stream_message(UserMessage(text=payload.message)):
                if isinstance(event, TextDelta):
                    chunks.append(event.content)
                    yield _sse("delta", event.content)
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:  # pragma: no cover
            yield _sse("error", {"detail": str(e)[:400]})
            return
        full = "".join(chunks)
        # Persist assistant reply on the exact row we inserted (id-scoped).
        await db.copilot_queries.update_one(
            {"id": query_row_id},
            {"$set": {"assistant_reply": full[:8000], "replied_at": now_iso()}},
        )
        yield _sse("done", {"session_id": session_id, "length": len(full)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class CopilotSessionPurgeRequest(BaseModel):
    session_id: str


@router.post("/reset")
async def copilot_reset(_sa: str = Depends(get_current_super_admin)):
    """Return a fresh session id so the next message opens a new context window."""
    return {"session_id": f"copilot-{uuid.uuid4().hex[:12]}"}


@router.get("/history")
async def copilot_history(limit: int = 20, _sa: str = Depends(get_current_super_admin)):
    """Recent copilot queries (all admins) for audit / re-open of a session."""
    limit = max(1, min(limit, 100))
    rows = []
    async for r in db.copilot_queries.find({}, {"_id": 0}).sort("created_at", -1).limit(limit):
        rows.append(r)
    return {"queries": rows}
