"""Orchestration service — the single entry point for all pod invocations.

Responsibilities:
  * Register pods into the ``agent_pods`` collection on startup (idempotent).
  * Enforce global + per-pod kill switch before dispatch.
  * Emit run-lifecycle audit events (started / completed / failed).
  * Catch :class:`agent_os.approvals.ApprovalRequired` from the pod body
    and park the run in status ``waiting_approval``. When the human
    approves, the pod can be re-driven — the ``require_approval`` gate
    finds the approved row and lets it through.
  * Never let a pod's exception crash the parent request — every
    dispatch is fully wrapped.

Not in Sprint 1: retries, parallel batching, cron trigger integration —
all of those land in Sprints 3/4.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from core import db

from .approvals import ApprovalRejected, ApprovalRequired
from .approvals import ensure_indexes as _approvals_indexes
from .audit import emit, ensure_indexes as _audit_indexes
from .db_guard import GuardViolation, agent_db_for
from .mcp_registry import KillSwitchTripped, ScopeViolation, mcp_call
from .models import AgentPod, AgentRun, PodId

log = logging.getLogger("agent_os.orchestrator")

_POD_HANDLERS: dict[PodId, Callable[..., Awaitable[dict[str, Any]]]] = {}


def register_pod_handler(pod_id: PodId, handler: Callable[..., Awaitable[dict[str, Any]]]) -> None:
    _POD_HANDLERS[pod_id] = handler


def registered_pod_ids() -> list[PodId]:
    return list(_POD_HANDLERS.keys())


# --------------------------------------------------------------------------- #
# Seed / bootstrap
# --------------------------------------------------------------------------- #


# Pod A–G definitions. Editing this list is an "add a new pod" — per §6
# decision matrix that is escalated to the human, not autonomous. Kept
# in one place so a code reviewer can see the entire pod inventory.
POD_INVENTORY: list[AgentPod] = [
    AgentPod(id="pod_a_prospecting", display_name="Pod A · Prospecting",
             purpose="Find ICP-fit prospects via Apollo and draft HubSpot contact records.",
             mcp_scopes=["apollo", "hubspot"]),
    AgentPod(id="pod_b_outreach", display_name="Pod B · Cold outreach",
             purpose="Draft personalised first-touch emails against HubSpot contacts.",
             mcp_scopes=["hubspot", "gmail"]),
    AgentPod(id="pod_c_followup", display_name="Pod C · Meeting follow-up",
             purpose="Read Gmail + HubSpot activity, draft follow-up notes and next-steps.",
             mcp_scopes=["hubspot", "gmail"]),
    AgentPod(id="pod_d_proposal", display_name="Pod D · Proposal + envelope prep",
             purpose="Draft proposal decks in Canva and prepare DocuSign envelopes (never sends).",
             mcp_scopes=["hubspot", "canva", "docusign"]),
    AgentPod(id="pod_e_content", display_name="Pod E · Content + branding",
             purpose="Generate social + collateral assets in Canva for human review.",
             mcp_scopes=["canva"]),
    AgentPod(id="pod_f_slack_ops", display_name="Pod F · Slack ops",
             purpose="Draft internal Slack notifications for the CX/ops team.",
             mcp_scopes=["slack"]),
    AgentPod(id="pod_g_reporting", display_name="Pod G · Reporting",
             purpose="Weekly pipeline digest — reads HubSpot, posts to Slack (draft).",
             mcp_scopes=["hubspot", "slack"]),
]


async def bootstrap() -> None:
    """Called from server startup. Idempotent — safe to re-run."""
    await _audit_indexes()
    await _approvals_indexes()
    await db.agent_pods.create_index([("id", 1)], unique=True)
    await db.agent_runs.create_index([("pod_id", 1), ("created_at", -1)])
    for pod in POD_INVENTORY:
        existing = await db.agent_pods.find_one({"id": pod.id}, {"_id": 0})
        if not existing:
            await db.agent_pods.insert_one(pod.model_dump())
        else:
            # Refresh purpose + mcp_scopes only. NEVER overwrite human-set
            # `enabled` or `kill_switch` — those are operator state, not seed.
            await db.agent_pods.update_one(
                {"id": pod.id},
                {"$set": {
                    "display_name": pod.display_name,
                    "purpose": pod.purpose,
                    "mcp_scopes": pod.mcp_scopes,
                    "updated_at": pod.updated_at,
                }},
            )


# --------------------------------------------------------------------------- #
# Kill switch + dispatch
# --------------------------------------------------------------------------- #


async def _kill_switch_check(pod_id: PodId) -> None:
    """Global (in ``platform_flags``) trumps per-pod (in ``agent_pods``)."""
    global_flag = await db.platform_flags.find_one({"key": "agent_os_kill_switch"}, {"_id": 0, "value": 1})
    if global_flag and global_flag.get("value") is True:
        raise KillSwitchTripped("global agent-os kill switch engaged")
    pod = await db.agent_pods.find_one({"id": pod_id}, {"_id": 0, "enabled": 1, "kill_switch": 1})
    if not pod:
        raise KillSwitchTripped(f"pod {pod_id} not registered")
    if pod.get("kill_switch") is True:
        raise KillSwitchTripped(f"pod {pod_id} kill switch engaged")
    if pod.get("enabled") is False:
        raise KillSwitchTripped(f"pod {pod_id} disabled")


async def dispatch(pod_id: PodId, triggered_by: str, input_payload: Optional[dict[str, Any]] = None) -> AgentRun:
    """Kick off a pod run. Never raises — every failure mode lands as a
    status on the returned :class:`AgentRun` row so the API can respond
    cleanly."""
    run = AgentRun(pod_id=pod_id, triggered_by=triggered_by, input=input_payload or {})
    await db.agent_runs.insert_one(run.model_dump())
    await emit("pod.run.started", actor=triggered_by, subject=run.id, details={"pod_id": pod_id})

    try:
        await _kill_switch_check(pod_id)
    except KillSwitchTripped as e:
        run.status, run.error = "cancelled", str(e)
        await _finalise(run)
        return run

    handler = _POD_HANDLERS.get(pod_id)
    if not handler:
        run.status, run.error = "failed", f"no handler registered for {pod_id}"
        await _finalise(run)
        return run

    run.status = "running"
    run.started_at = _iso()
    await db.agent_runs.update_one({"id": run.id}, {"$set": {"status": "running", "started_at": run.started_at}})

    try:
        pod_ctx = _PodContext(run=run, pod_id=pod_id, db=agent_db_for(pod_id))
        out = await handler(pod_ctx, input_payload or {})
        run.output, run.status = out, "completed"
    except ApprovalRequired as e:
        run.status = "waiting_approval"
        run.error = str(e)
        log.info(f"pod {pod_id} waiting on approval: {e}")
    except ApprovalRejected as e:
        run.status, run.error = "failed", f"approval rejected: {e}"
    except (ScopeViolation, GuardViolation) as e:
        # Loud fail — either the pod tried a connector it shouldn't or
        # wrote into a protected collection. Both are audit-worthy.
        run.status, run.error = "failed", f"security violation: {e}"
        log.error(f"pod {pod_id} security violation", exc_info=True)
    except Exception as e:  # noqa: BLE001
        run.status, run.error = "failed", f"{type(e).__name__}: {e}"
        log.exception(f"pod {pod_id} run failed")

    await _finalise(run)
    return run


async def _finalise(run: AgentRun) -> None:
    run.completed_at = _iso()
    await db.agent_runs.update_one({"id": run.id}, {"$set": {
        "status": run.status, "output": run.output, "error": run.error, "completed_at": run.completed_at,
    }})
    event = "pod.run.completed" if run.status == "completed" else "pod.run.failed"
    await emit(event, actor=run.triggered_by or "orchestrator", subject=run.id,
               details={"pod_id": run.pod_id, "status": run.status, "error": run.error})


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Context passed to every pod handler
# --------------------------------------------------------------------------- #


class _PodContext:
    """The only object a pod handler sees. Provides:
       * ``ctx.run`` — the AgentRun row (read-only view)
       * ``ctx.db`` — the guarded :class:`AgentDb` wrapper
       * ``ctx.mcp(connector, op, payload)`` — scope-checked connector call
       * ``ctx.require_approval(action, payload, summary, idempotency_key)`` —
         the approval gate
    """

    def __init__(self, *, run: AgentRun, pod_id: PodId, db) -> None:  # noqa: A002
        self.run = run
        self.pod_id = pod_id
        self.db = db

    async def mcp(self, connector, op, payload):
        return await mcp_call(self.pod_id, connector, op, payload)

    async def require_approval(self, *, action, payload, summary, idempotency_key=None):
        from .approvals import require_approval
        return await require_approval(
            run_id=self.run.id, pod_id=self.pod_id, action=action,
            payload=payload, summary=summary, idempotency_key=idempotency_key,
        )
