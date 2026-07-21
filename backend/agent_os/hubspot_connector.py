"""HubSpot connector — real CRM read/write for the Agent OS.

Replaces `HubspotStub` in `mcp_registry.py` when `HUBSPOT_ACCESS_TOKEN` is
present in the environment. Graceful degradation when the token is blank:
returns `{"skipped": True, "reason": "hubspot_not_configured"}` and never
raises — pods remain runnable in preview environments without live creds.

Operations exposed (called via `mcp_call(pod_id, "hubspot", op, payload)`):
    create_contact           payload: {email, firstname?, lastname?, properties?}
    update_contact           payload: {contact_id, properties}
    lookup_contact_by_email  payload: {email}
    update_deal_stage        payload: {deal_id, dealstage}

Every call is scope-checked upstream in `mcp_registry.mcp_call`.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from core import logger

from .mcp_registry import HubspotStub, StubConnector

HUBSPOT_BASE_URL = "https://api.hubapi.com"
HUBSPOT_TIMEOUT_S = 20.0

_TOKEN_ENV = "HUBSPOT_ACCESS_TOKEN"


def _token() -> str:
    """Read at call-time so a mid-run env change picks up on the next call
    without a backend restart (tests need this)."""
    return (os.environ.get(_TOKEN_ENV) or "").strip()


def hubspot_configured() -> bool:
    return bool(_token())


async def _request(method: str, path: str, *, params: dict | None = None, json_body: dict | None = None) -> dict:
    """Single HTTP entry point — attaches the Bearer token, times out, and
    surfaces the JSON body. Non-2xx responses raise; the mcp_call layer
    swallows and logs.
    """
    token = _token()
    if not token:
        return {"skipped": True, "reason": "hubspot_not_configured"}
    async with httpx.AsyncClient(base_url=HUBSPOT_BASE_URL, timeout=HUBSPOT_TIMEOUT_S) as client:
        r = await client.request(
            method, path,
            params=params, json=json_body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if r.status_code >= 400:
        # Include HubSpot's error body in the log for triage; caller decides
        # whether to convert the exception into an audit entry.
        logger.error(f"[hubspot] {method} {path} → {r.status_code}: {r.text[:400]}")
    r.raise_for_status()
    return r.json()


class HubspotConnector(StubConnector):
    """Real HubSpot connector wired into the MCP registry.

    Behaviour when `HUBSPOT_ACCESS_TOKEN` is blank: delegate to the
    original `HubspotStub` so pods stay runnable in preview environments
    without live creds. Sprint 1's regression tests continue to pass; a
    warning is logged on every stubbed call so operators know they're
    seeing simulated data, not real HubSpot writes.
    """

    connector = "hubspot"

    def __init__(self):
        # Delegate stub — used when the access token is missing.
        self._stub = HubspotStub()

    async def call(self, pod_id: str, op: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Route the op → the correct HubSpot v3 REST endpoint. When no
        token is configured, delegates to the in-memory stub AND logs a
        warning per-call so the un-configured state is visible in prod
        logs."""
        if not hubspot_configured():
            logger.warning(
                f"[hubspot] no HUBSPOT_ACCESS_TOKEN — delegating {op!r} to in-memory stub "
                f"(pod={pod_id}). Data is NOT written to HubSpot."
            )
            return await self._stub.call(pod_id, op, payload)

        if op == "create_contact":
            props = {k: v for k, v in {
                "email": payload.get("email"),
                "firstname": payload.get("firstname"),
                "lastname": payload.get("lastname"),
                **(payload.get("properties") or {}),
            }.items() if v is not None}
            return await _request("POST", "/crm/v3/objects/contacts", json_body={"properties": props})

        if op == "update_contact":
            contact_id = payload["contact_id"]
            return await _request(
                "PATCH",
                f"/crm/v3/objects/contacts/{contact_id}",
                json_body={"properties": payload.get("properties") or {}},
            )

        if op == "lookup_contact_by_email":
            email = payload["email"]
            return await _request(
                "GET",
                f"/crm/v3/objects/contacts/{email}",
                params={"idProperty": "email"},
            )

        if op == "update_deal_stage":
            deal_id = payload["deal_id"]
            return await _request(
                "PATCH",
                f"/crm/v3/objects/deals/{deal_id}",
                json_body={"properties": {"dealstage": payload["dealstage"]}},
            )

        raise NotImplementedError(f"hubspot op not supported: {op}")
