"""Per-pod MCP connector scoping + stubbed connector implementations.

Hard stop §4.4 — a pod's connector list is exactly what its row in
``agent_pods.mcp_scopes`` says. Any attempt to invoke a connector outside
this list raises :class:`ScopeViolation` and audit-logs a
``mcp.call.blocked`` event.

Sprint 1 ships **stub** connectors only — every ``call`` returns a
fixture-driven synthetic result. No real HubSpot / Apollo traffic. Real
MCP clients land in Sprint 3+ once dev-scoped credentials are provided.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from core import db

from .audit import emit
from .models import MCPConnector, PodId


class ScopeViolation(PermissionError):
    """Pod attempted an MCP call outside its declared scope."""


class KillSwitchTripped(RuntimeError):
    """Global or per-pod kill switch is engaged."""


# --------------------------------------------------------------------------- #
# Stub connector base
# --------------------------------------------------------------------------- #


@dataclass
class ConnectorCall:
    connector: MCPConnector
    op: str
    payload: dict[str, Any]


class StubConnector:
    """Base for every Sprint 1 stub. Every ``call`` writes an
    ``mcp.call.executed`` audit event and returns the pre-seeded
    fixture for that (connector, op) pair — never a live HTTP call."""

    connector: MCPConnector = "apollo"

    async def call(self, pod_id: PodId, op: str, payload: dict[str, Any]) -> dict[str, Any]:
        await emit("mcp.call.executed", actor=pod_id, subject=self.connector,
                   details={"op": op, "payload_keys": sorted(payload.keys())})
        return self._fixture(op, payload)

    def _fixture(self, op: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"stub": True, "connector": self.connector, "op": op, "input": payload}


class ApolloStub(StubConnector):
    connector = "apollo"

    def _fixture(self, op, payload):
        # Very small deterministic fixture — good enough for Sprint 1
        # exit criteria: prove the pod can shape output the enrichment
        # step expects, without touching the real Apollo API.
        if op == "search_prospects":
            return {"prospects": [
                {"email": "amina.hassan@example-fintech.ae", "name": "Amina Hassan",
                 "title": "Head of AI", "company": "Example Fintech", "country": "AE"},
                {"email": "raj.iyer@example-manuf.in", "name": "Raj Iyer",
                 "title": "VP Manufacturing Digital", "company": "Example Manufacturing", "country": "IN"},
            ]}
        return {"stub_op": op}


class HubspotStub(StubConnector):
    connector = "hubspot"

    def _fixture(self, op, payload):
        if op == "create_contact":
            return {"contact_id": f"stub-hs-{hash(payload.get('email', '')) & 0xffff:04x}",
                    "created": True, "would_have_written": payload}
        return {"stub_op": op}


# Registry — instantiated once and reused. Real clients replace these
# entries in Sprint 3 without touching pod code.
_CONNECTORS: dict[MCPConnector, StubConnector] = {
    "apollo": ApolloStub(),
    "hubspot": HubspotStub(),
    # gmail / docusign / canva / slack land in later sprints; missing
    # entry raises NotImplementedError below on any call, which is a
    # deliberate loud-fail so we notice unimplemented pod paths.
}


async def check_scope(pod_id: PodId, connector: MCPConnector) -> None:
    """Reads the pod's declared MCP scope from the ``agent_pods``
    collection and hard-raises if the requested connector is missing."""
    pod = await db.agent_pods.find_one({"id": pod_id}, {"_id": 0, "mcp_scopes": 1})
    if not pod:
        raise ScopeViolation(f"unknown pod {pod_id}")
    if connector not in (pod.get("mcp_scopes") or []):
        await emit("mcp.call.blocked", actor=pod_id, subject=connector,
                   details={"reason": "connector_not_in_scope"})
        raise ScopeViolation(f"pod {pod_id} lacks scope for {connector}")


async def mcp_call(pod_id: PodId, connector: MCPConnector, op: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Single public entry point for pods → connectors. Scope-checks,
    audit-logs the attempt, dispatches to the stub, and returns."""
    await emit("mcp.call.attempted", actor=pod_id, subject=connector, details={"op": op})
    await check_scope(pod_id, connector)
    impl = _CONNECTORS.get(connector)
    if impl is None:
        raise NotImplementedError(f"connector {connector} not implemented in Sprint 1")
    return await impl.call(pod_id, op, payload)
