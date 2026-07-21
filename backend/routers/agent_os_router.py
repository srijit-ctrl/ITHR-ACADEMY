"""Super-admin-only surface for the Agent OS.

Sprint 1 exposes the minimum viable ops surface:
  * ``GET  /api/admin/agent-os/pods`` — the pod inventory (read).
  * ``POST /api/admin/agent-os/pods/{id}/dispatch`` — kick off a run.
  * ``GET  /api/admin/agent-os/runs`` — recent runs across all pods.
  * ``GET  /api/admin/agent-os/approvals`` — pending queue.
  * ``POST /api/admin/agent-os/approvals/{id}/decide`` — approve/reject.
  * ``POST /api/admin/agent-os/kill-switch`` — global kill switch.

Sprint 2 layers the Agent Control Center UI on these + adds a PUBLIC
HubSpot webhook receiver at ``POST /api/agent-os/webhooks/hubspot`` in
`public_router` below (HMAC-verified, no super-admin gate — HubSpot
authenticates itself via the x-hubspot-signature-v3 header).
"""
from __future__ import annotations

import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import get_current_super_admin
from core import db, logger, now_iso

from agent_os import approvals, orchestrator
from agent_os.models import ApprovalDecision, PodId

router = APIRouter(prefix="/api/admin/agent-os", tags=["agent-os"])

# Separate PUBLIC router for the HubSpot inbound webhook — HubSpot cannot
# supply a super-admin JWT, so the endpoint stands or falls on the
# HMAC-SHA256 signature check.
public_router = APIRouter(prefix="/api/agent-os", tags=["agent-os-public"])


class DispatchPayload(BaseModel):
    input: dict[str, Any] = {}


class DecidePayload(BaseModel):
    decision: Literal["approved", "rejected"]
    note: Optional[str] = None


class KillSwitchPayload(BaseModel):
    engaged: bool


@router.get("/pods")
async def list_pods(_sa: str = Depends(get_current_super_admin)):
    pods = await db.agent_pods.find({}, {"_id": 0}).sort("id", 1).to_list(50)
    return {"pods": pods, "registered_handlers": orchestrator.registered_pod_ids()}


@router.post("/pods/{pod_id}/toggle")
async def toggle_pod(
    pod_id: PodId,
    enabled: bool,
    sa_id: str = Depends(get_current_super_admin),
):
    """Super-admin-only. Pods NEVER call this."""
    result = await db.agent_pods.update_one(
        {"id": pod_id},
        {"$set": {"enabled": enabled, "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "unknown pod")
    from agent_os.audit import emit
    await emit("pod.toggle", actor=sa_id, subject=pod_id, details={"enabled": enabled})
    return {"ok": True, "id": pod_id, "enabled": enabled}


@router.post("/pods/{pod_id}/dispatch")
async def dispatch_pod(
    pod_id: PodId,
    payload: DispatchPayload,
    sa_id: str = Depends(get_current_super_admin),
):
    """Fire a pod run under the super admin's identity."""
    if pod_id not in orchestrator.registered_pod_ids():
        raise HTTPException(400, f"pod {pod_id} handler not registered")
    run = await orchestrator.dispatch(pod_id, triggered_by=sa_id, input_payload=payload.input)
    return run.model_dump()


@router.get("/runs")
async def list_runs(
    limit: int = 50,
    pod_id: Optional[PodId] = None,
    _sa: str = Depends(get_current_super_admin),
):
    q: dict[str, Any] = {}
    if pod_id:
        q["pod_id"] = pod_id
    rows = await db.agent_runs.find(q, {"_id": 0}).sort("created_at", -1).to_list(max(1, min(200, limit)))
    return {"runs": rows}


@router.get("/approvals")
async def list_approvals(
    decision: ApprovalDecision = "pending",
    limit: int = 100,
    _sa: str = Depends(get_current_super_admin),
):
    rows = await db.agent_approval_queue.find(
        {"decision": decision}, {"_id": 0},
    ).sort("created_at", -1).to_list(max(1, min(500, limit)))
    return {"approvals": rows}


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    payload: DecidePayload,
    sa_id: str = Depends(get_current_super_admin),
):
    try:
        row = await approvals.decide(
            approval_id=approval_id, decision=payload.decision,
            decided_by=sa_id, note=payload.note,
        )
    except approvals.ApprovalRejected as e:
        raise HTTPException(404, str(e))
    return row.model_dump()


@router.get("/audit")
async def list_audit(
    limit: int = 100,
    actor: Optional[str] = None,
    event: Optional[str] = None,
    _sa: str = Depends(get_current_super_admin),
):
    q: dict[str, Any] = {}
    if actor: q["actor"] = actor
    if event: q["event"] = event
    rows = await db.agent_audit_log.find(q, {"_id": 0}).sort("at", -1).to_list(max(1, min(500, limit)))
    return {"events": rows}


@router.post("/kill-switch")
async def toggle_kill_switch(
    payload: KillSwitchPayload,
    sa_id: str = Depends(get_current_super_admin),
):
    """Global stop — no pod can dispatch while engaged."""
    await db.platform_flags.update_one(
        {"key": "agent_os_kill_switch"},
        {"$set": {"key": "agent_os_kill_switch", "value": payload.engaged,
                  "updated_at": now_iso(), "updated_by": sa_id}},
        upsert=True,
    )
    from agent_os.audit import emit
    await emit("pod.kill_switch", actor=sa_id, subject="global",
               details={"engaged": payload.engaged})
    return {"engaged": payload.engaged}


# ---- Sprint 2 additions --------------------------------------------------


@router.get("/connectors/status")
async def connectors_status(_sa: str = Depends(get_current_super_admin)):
    """Report which real MCP connectors are configured vs stubbed. Powers
    the "HubSpot: live" / "HubSpot: stubbed" badge in the Agent Control
    Center UI."""
    from agent_os.hubspot_connector import hubspot_configured
    from agent_os.hubspot_webhooks import webhook_configured
    return {
        "hubspot": {
            "outbound_configured": hubspot_configured(),
            "webhook_configured": webhook_configured(),
        },
        "apollo": {"outbound_configured": False},  # Sprint 3
    }


@router.get("/webhooks/hubspot/events")
async def list_hubspot_webhook_events(
    limit: int = 100,
    _sa: str = Depends(get_current_super_admin),
):
    """Recent inbound HubSpot events (last N) for the admin console —
    lets operators see what fired the pods."""
    limit = max(1, min(500, limit))
    from agent_os.hubspot_webhooks import WEBHOOK_EVENTS_COLL
    rows = await db[WEBHOOK_EVENTS_COLL].find(
        {}, {"_id": 0, "raw": 0},  # trim raw payload — API stays lean
    ).sort("_id", -1).to_list(limit)
    return {"events": rows, "count": len(rows)}


# ---- PUBLIC: HubSpot inbound webhook -------------------------------------


@public_router.post("/webhooks/hubspot")
async def hubspot_webhook(request: Request):
    """Receive `contact.creation`, `deal.propertyChange`, and other
    HubSpot subscription events. HMAC-SHA256 v3 verified; dedupe by
    (portalId, subscriptionId, eventId); dispatches a pod run per event.

    Returns JSON `{ok: true, processed: N, duplicates: N}`.
    Non-2xx only on signature failure or malformed JSON — HubSpot retries
    aggressively on failures, so we accept-and-log even for unknown event
    types.
    """
    from agent_os.audit import emit
    from agent_os.hubspot_webhooks import (
        ensure_indexes,
        mark_processed,
        rebuild_public_uri,
        record_event,
        verify_signature,
        webhook_configured,
    )

    body = await request.body()
    sig = request.headers.get("x-hubspot-signature-v3")
    ts = request.headers.get("x-hubspot-request-timestamp")

    if not webhook_configured():
        # Deliberately explicit — surfaces the "add secret" step to
        # operators looking at Cloudflare / access logs.
        await emit("hubspot.webhook.rejected", actor="hubspot",
                   subject="signature", details={"reason": "secret_not_configured"})
        return JSONResponse({"ok": False, "error": "webhook secret not configured"}, status_code=503)
    if not sig or not ts:
        return JSONResponse({"ok": False, "error": "missing signature headers"}, status_code=400)
    if not verify_signature(request.method, rebuild_public_uri(request), body, ts, sig):
        await emit("hubspot.webhook.rejected", actor="hubspot",
                   subject="signature", details={"reason": "signature_mismatch"})
        return JSONResponse({"ok": False, "error": "bad signature"}, status_code=401)

    try:
        events_in = json.loads(body or b"[]")
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

    if isinstance(events_in, dict):
        # HubSpot sometimes wraps in a single-object envelope during Test calls
        events_in = [events_in]

    await ensure_indexes()
    processed = 0
    duplicates = 0
    for evt in events_in:
        first_time = await record_event(evt)
        if not first_time:
            duplicates += 1
            continue
        try:
            await _dispatch_hubspot_event(evt)
            await mark_processed(f"{evt.get('portalId')}:{evt.get('subscriptionId')}:{evt.get('eventId')}", "ok")
            processed += 1
        except Exception:
            logger.exception("[hubspot-webhook] event dispatch failed")
            await mark_processed(f"{evt.get('portalId')}:{evt.get('subscriptionId')}:{evt.get('eventId')}", "error")

    return {"ok": True, "processed": processed, "duplicates": duplicates}


async def _dispatch_hubspot_event(evt: dict) -> None:
    """Route a single verified HubSpot event to the correct pod handler.

    Wired minimally today — one clear mapping per subscription type.
    Future events land in `agent_audit_log` only until a mapping exists.
    """
    from agent_os.audit import emit
    sub_type = evt.get("subscriptionType") or ""
    await emit("hubspot.webhook.received", actor="hubspot",
               subject=sub_type, details={
                   "portalId": evt.get("portalId"),
                   "eventId": evt.get("eventId"),
                   "objectId": evt.get("objectId"),
                   "propertyName": evt.get("propertyName"),
               })
    # Route table — extend as pods add HubSpot triggers.
    if sub_type == "contact.creation":
        pod = "followup"  # new contact → followup pod queues an intro sequence
    elif sub_type == "deal.propertyChange" and evt.get("propertyName") == "dealstage":
        pod = "proposal"  # deal stage moved → proposal pod re-checks docs
    else:
        return  # audit-only; no pod dispatch yet
    if pod not in orchestrator.registered_pod_ids():
        return
    try:
        await orchestrator.dispatch(
            pod, triggered_by="hubspot-webhook",
            input_payload={"source": "hubspot", "event": evt},
        )
    except Exception:
        logger.exception(f"[hubspot-webhook] pod dispatch failed for {pod}")
