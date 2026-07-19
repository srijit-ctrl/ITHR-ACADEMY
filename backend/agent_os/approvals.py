"""Approval queue engine — the hard boundary between pods and side-effects.

Sprint 1 scope:
  * Submit approval requests.
  * Query pending approvals (super-admin read).
  * Decide (approve / reject) — super-admin only, single-writer.
  * ``require_approval()`` context that a pod must open before any
    irreversible connector call — raises :class:`ApprovalRequired` if
    the caller lacks an approved row keyed to this run + action +
    idempotency key.

Sprint 2 will layer expiry, batch decisions, and the Agent Control
Center UI on top of this same schema. The Sprint 2 UI is a read/write
consumer only — it must not extend the schema without a flagged
deviation.
"""
from __future__ import annotations

from typing import Any, Optional

from core import db

from .audit import emit
from .models import ApprovalAction, ApprovalDecision, ApprovalRequest, PodId

COLLECTION = "agent_approval_queue"


class ApprovalRequired(Exception):
    """Raised when a pod attempts an irreversible action without an
    approved row for it. Never caught inside pod code — the orchestrator
    catches it, marks the run ``waiting_approval``, and returns."""


class ApprovalRejected(Exception):
    """A decision exists for this action but the human rejected it."""


async def submit(
    *,
    run_id: str,
    pod_id: PodId,
    action: ApprovalAction,
    payload: dict[str, Any],
    summary: str,
    idempotency_key: Optional[str] = None,
) -> ApprovalRequest:
    """Enqueue an irreversible action for human review. Idempotent — a
    repeat submission with the same key returns the existing row."""
    if idempotency_key:
        existing = await db[COLLECTION].find_one(
            {"pod_id": pod_id, "action": action, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            return ApprovalRequest(**existing)

    req = ApprovalRequest(
        run_id=run_id, pod_id=pod_id, action=action, payload=payload,
        summary=summary, idempotency_key=idempotency_key,
    )
    await db[COLLECTION].insert_one(req.model_dump())
    await emit("approval.requested", actor=pod_id, subject=req.id,
               details={"action": action, "run_id": run_id, "summary": summary})
    return req


async def find_decision(
    *,
    pod_id: PodId,
    action: ApprovalAction,
    idempotency_key: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Optional[ApprovalRequest]:
    """Look up whether a decision exists for this pod attempt.

    When an ``idempotency_key`` is supplied it wins — decisions carry
    across runs (a re-dispatched run finds the previously-approved row).
    When only ``run_id`` is supplied we match strictly on that pair;
    this is the fallback for one-shot actions that don't have a natural
    idempotency key."""
    q: dict[str, Any] = {"pod_id": pod_id, "action": action}
    if idempotency_key:
        q["idempotency_key"] = idempotency_key
    elif run_id:
        q["run_id"] = run_id
    else:
        return None
    doc = await db[COLLECTION].find_one(q, {"_id": 0})
    return ApprovalRequest(**doc) if doc else None


async def require_approval(
    *,
    run_id: str,
    pod_id: PodId,
    action: ApprovalAction,
    payload: dict[str, Any],
    summary: str,
    idempotency_key: Optional[str] = None,
) -> ApprovalRequest:
    """The pod-facing gate. Two outcomes only:
       * Returns the approved request → pod proceeds with the connector call.
       * Raises ``ApprovalRequired`` (still pending) or ``ApprovalRejected``.

    Never lets a pod through on a missing / pending / rejected decision.
    """
    existing = await find_decision(pod_id=pod_id, action=action,
                                   idempotency_key=idempotency_key, run_id=run_id)
    if existing is None:
        # First time we've seen this action for the run — enqueue it and
        # halt the pod. The orchestrator will pick this up and mark the
        # run as ``waiting_approval``.
        await submit(
            run_id=run_id, pod_id=pod_id, action=action, payload=payload,
            summary=summary, idempotency_key=idempotency_key,
        )
        raise ApprovalRequired(f"awaiting human approval for {action}")

    if existing.decision == "approved":
        return existing
    if existing.decision == "rejected":
        raise ApprovalRejected(f"rejected by {existing.decided_by} — {existing.decision_note or 'no note'}")
    # pending / expired both halt the pod
    raise ApprovalRequired(f"decision {existing.decision} for {action}")


async def decide(
    *,
    approval_id: str,
    decision: ApprovalDecision,
    decided_by: str,
    note: Optional[str] = None,
) -> ApprovalRequest:
    """Super-admin single-writer. Callers upstream must have already
    verified the decider is a super admin — this function does not
    re-check RBAC. Returns the updated row."""
    from datetime import datetime, timezone
    doc = await db[COLLECTION].find_one_and_update(
        {"id": approval_id, "decision": "pending"},
        {"$set": {
            "decision": decision,
            "decided_by": decided_by,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "decision_note": note,
        }},
        return_document=True,
        projection={"_id": 0},
    )
    if not doc:
        raise ApprovalRejected("no pending approval with that id")
    await emit(
        "approval.approved" if decision == "approved" else "approval.rejected",
        actor=decided_by, subject=approval_id, details={"note": note},
    )
    return ApprovalRequest(**doc)


async def ensure_indexes() -> None:
    await db[COLLECTION].create_index([("decision", 1), ("created_at", -1)])
    await db[COLLECTION].create_index([("run_id", 1), ("action", 1)])
    await db[COLLECTION].create_index(
        [("pod_id", 1), ("action", 1), ("idempotency_key", 1)],
        unique=True, sparse=True,
    )
