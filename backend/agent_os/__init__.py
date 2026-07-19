"""Agent OS — Sprint 1 skeleton.

Scoped to Sprint 1 of the ITHR Phase 2 Agent OS execution prompt:
  * Mongo-side schema (collections in place of the spec's Postgres tables).
  * Orchestration service skeleton with kill-switch + audit-log hooks.
  * Pod A (Prospecting) wired end-to-end against a STUBBED MCP connector
    layer — no live HubSpot / Apollo traffic until the approval queue UI
    and real credentials land in Sprint 2.

Design premises (recorded here because the technical spec was not
available at Sprint 0):
  * Seven pods A–G plus an orchestrator, all human-approval-gated for
    any send / sign / bill / discount / provision action (§4.1 hard stop).
  * Per-pod MCP scoping enforced at the connector layer, not per-request
    (§4.4 hard stop) — a pod can never call a connector missing from its
    declared scope.
  * Pods never write to `agent_pods.enabled`, `agent_audit_log`, or
    `approval_queue.decision` at the DB layer. The `AgentDb` wrapper
    (see :mod:`agent_os.db_guard`) is the pod-facing surface; it hard-
    raises ``PermissionError`` for any write into a protected collection.
    This is the Mongo-side equivalent of the spec's §4.5 DB-grant rule.
"""

from . import audit, approvals, models, orchestrator  # noqa: F401
