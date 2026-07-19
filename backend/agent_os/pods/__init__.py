"""Pod A — Prospecting.

Sprint 1 end-to-end wiring: given an input query, Pod A calls the Apollo
stub to fetch candidate prospects, then queues one approval per
prospect for the HubSpot ``create_contact`` action. It never writes
to HubSpot until the human approves each one.

Handler contract:
    async def run(ctx: _PodContext, input_payload: dict) -> dict

    input_payload keys:
        titles: list[str]   — job titles to search for
        countries: list[str] — ISO-2 country filter
        limit: int          — cap the search result

    return dict:
        prospects_found: int
        approvals_created: int   # new approvals queued this run
        contacts_created: int    # non-zero only if approvals were already-approved
        skipped_pending: int     # already queued, still pending
"""
from __future__ import annotations

from typing import Any

from ..approvals import ApprovalRequired
from ..orchestrator import register_pod_handler


async def run(ctx, input_payload: dict[str, Any]) -> dict[str, Any]:
    titles = input_payload.get("titles") or ["Head of AI", "VP AI"]
    countries = input_payload.get("countries") or ["AE", "SA"]
    limit = int(input_payload.get("limit") or 10)

    # Step 1 — Apollo prospect search (read-only, no approval gate)
    apollo_out = await ctx.mcp("apollo", "search_prospects",
                               {"titles": titles, "countries": countries, "limit": limit})
    prospects = apollo_out.get("prospects", [])

    counts = {
        "prospects_found": len(prospects),
        "approvals_created": 0,
        "contacts_created": 0,
        "skipped_pending": 0,
    }

    # Step 2 — for each prospect, gate on approval before touching HubSpot.
    # Design choice (logged as deviation): we queue ALL missing approvals
    # in one pass, then defer the run if any were new — better UX for the
    # human approver (batch-decide the whole prospect list at once) than
    # halting on first-missing which would require N re-dispatches.
    # Idempotency key = email.
    any_new_this_run = False
    for p in prospects:
        email = p.get("email", "")
        if not email:
            continue
        try:
            approval = await ctx.require_approval(
                action="hubspot.create_contact",
                payload=p,
                summary=f"Create HubSpot contact for {p.get('name', email)} ({p.get('company', '?')})",
                idempotency_key=email,
            )
        except ApprovalRequired:
            counts["approvals_created"] += 1
            any_new_this_run = True
            continue

        # Approved — safe to write to HubSpot via the stub connector.
        result = await ctx.mcp("hubspot", "create_contact", approval.payload)
        if result.get("created"):
            counts["contacts_created"] += 1

    if any_new_this_run:
        # Defer the run — the orchestrator marks it waiting_approval.
        # Attach counts so the approver UI can show "X new approvals queued".
        raise ApprovalRequired(
            f"{counts['approvals_created']} approvals queued; awaiting human decision"
        )

    return counts


register_pod_handler("pod_a_prospecting", run)
