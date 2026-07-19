"""Super-admin-only surface for the Agent OS.

Sprint 1 exposes the minimum viable ops surface:
  * ``GET  /api/admin/agent-os/pods`` — the pod inventory (read).
  * ``POST /api/admin/agent-os/pods/{id}/dispatch`` — kick off a run.
  * ``GET  /api/admin/agent-os/runs`` — recent runs across all pods.
  * ``GET  /api/admin/agent-os/approvals`` — pending queue.
  * ``POST /api/admin/agent-os/approvals/{id}/decide`` — approve/reject.
  * ``POST /api/admin/agent-os/kill-switch`` — global kill switch.

Sprint 2 layers the Agent Control Center UI on these + adds richer
filtering, batch decide, and the HubSpot webhook.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_super_admin
from core import db, now_iso

from agent_os import approvals, orchestrator
from agent_os.models import ApprovalDecision, PodId

router = APIRouter(prefix="/api/admin/agent-os", tags=["agent-os"])


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
