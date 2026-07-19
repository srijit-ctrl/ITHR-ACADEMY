"""Pydantic models for the Agent OS collections.

Everything a pod, the orchestrator, or the Super Admin dashboard touches
gets a model here — no raw-dict writes anywhere. Timestamps are ISO 8601
UTC strings for cross-service compatibility.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Pod registry
# --------------------------------------------------------------------------- #


PodId = Literal[
    "pod_a_prospecting", "pod_b_outreach", "pod_c_followup", "pod_d_proposal",
    "pod_e_content", "pod_f_slack_ops", "pod_g_reporting",
]

MCPConnector = Literal[
    "apollo", "hubspot", "gmail", "docusign", "canva", "slack",
]


class AgentPod(BaseModel):
    """One row per operational pod. `enabled` and `kill_switch` are the
    two human-controlled levers — writes to these fields go through a
    super-admin-only endpoint, never a pod runtime write path."""
    id: PodId
    display_name: str
    purpose: str
    enabled: bool = True
    kill_switch: bool = False
    mcp_scopes: list[MCPConnector] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Run lifecycle
# --------------------------------------------------------------------------- #


RunStatus = Literal["queued", "running", "waiting_approval", "completed", "failed", "cancelled"]


class AgentRun(BaseModel):
    """One pod invocation. Every side-effecting call the pod attempts
    against an MCP connector produces an ``approval_queue`` row that
    references this run's id."""
    id: str = Field(default_factory=_uid)
    pod_id: PodId
    triggered_by: str  # user_id of the initiating human, or "cron:daily"
    input: dict[str, Any] = Field(default_factory=dict)
    status: RunStatus = "queued"
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = Field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Approval queue
# --------------------------------------------------------------------------- #


ApprovalAction = Literal[
    "hubspot.create_contact", "hubspot.update_deal", "gmail.send",
    "docusign.send_envelope", "canva.publish", "slack.post_message",
]

ApprovalDecision = Literal["pending", "approved", "rejected", "expired"]


class ApprovalRequest(BaseModel):
    """A pod cannot execute any irreversible ``action`` without a row in
    this collection with ``decision='approved'``. The runtime helper
    :func:`agent_os.approvals.require_approval` enforces this — pods
    have no import path to bypass it (see db_guard)."""
    id: str = Field(default_factory=_uid)
    run_id: str
    pod_id: PodId
    action: ApprovalAction
    payload: dict[str, Any]  # what would be sent — displayed to the approver
    summary: str  # one-line, learner-safe description
    decision: ApprovalDecision = "pending"
    decided_by: Optional[str] = None  # user_id of the super admin
    decided_at: Optional[str] = None
    decision_note: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    # Idempotency guard — a pod that submits twice must dedupe by this key.
    idempotency_key: Optional[str] = None


# --------------------------------------------------------------------------- #
# Append-only audit log
# --------------------------------------------------------------------------- #


AuditEventType = Literal[
    "pod.run.started", "pod.run.completed", "pod.run.failed",
    "pod.toggle", "pod.kill_switch",
    "approval.requested", "approval.approved", "approval.rejected", "approval.expired",
    "mcp.call.attempted", "mcp.call.executed", "mcp.call.blocked",
    "guard.write.blocked",
]


class AuditEvent(BaseModel):
    """Append-only. Never updated in place. `actor` is the human user_id
    or the pod_id, never both."""
    id: str = Field(default_factory=_uid)
    at: str = Field(default_factory=_now)
    event: AuditEventType
    actor: str  # user_id | pod_id | "orchestrator" | "system"
    subject: Optional[str] = None  # run_id | approval_id | pod_id | connector
    details: dict[str, Any] = Field(default_factory=dict)
