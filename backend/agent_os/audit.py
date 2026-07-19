"""Append-only audit log emitter.

Pods never call this directly — they touch the DB via ``AgentDb`` which
emits audit events on their behalf. Direct writes are still allowed
from the orchestrator + approvals modules (both trusted paths), so the
`emit()` function is exposed here.
"""
from __future__ import annotations

from typing import Any, Optional

from core import db
from .models import AuditEvent, AuditEventType

COLLECTION = "agent_audit_log"


async def emit(
    event: AuditEventType,
    actor: str,
    *,
    subject: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Write one immutable audit row. Never raises — audit failures must
    never break the caller. Callers should still `await` this so bursts
    keep their ordering."""
    try:
        doc = AuditEvent(event=event, actor=actor, subject=subject, details=details or {}).model_dump()
        await db[COLLECTION].insert_one(doc)
    except Exception:  # noqa: BLE001 — audit must never crash the caller
        import logging
        logging.getLogger("agent_os.audit").exception("audit emit failed for %s", event)


async def ensure_indexes() -> None:
    """Called from orchestrator startup. Idempotent."""
    await db[COLLECTION].create_index([("at", -1)])
    await db[COLLECTION].create_index([("actor", 1), ("at", -1)])
    await db[COLLECTION].create_index([("event", 1), ("at", -1)])
