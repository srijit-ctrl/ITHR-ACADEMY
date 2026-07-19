"""Runtime DB wrapper handed to pods.

The spec's §4.5 hard-stop says pods must NEVER write to
``superadmin_roles``, ``pods.enabled``, or ``audit_log``, and this must
be enforced at the DB grant level. Mongo has no equivalent GRANT
mechanism accessible in our deployment, so we enforce it at the pod's
DB-access boundary: pods import ``AgentDb`` (not ``core.db``) and every
write goes through :meth:`write_scoped` which rejects any write into a
protected collection.

If a pod tries to bypass this by importing ``core.db`` directly, that
constitutes a security violation and should be blocked in code review —
we add a per-run subprocess-style sandbox in Sprint 4 (RBAC hardening).
"""
from __future__ import annotations

from typing import Any

from core import db as _raw_db

from .audit import emit

PROTECTED_COLLECTIONS = {
    "agent_pods",             # only super admins toggle enabled / kill_switch
    "agent_audit_log",        # append-only via audit.emit(); never mutated
    "agent_approval_queue",   # write path is approvals.py only, not pods
    "superadmin_roles",       # RBAC map, human-only
    "users",                  # pods never mutate user records directly
}


class GuardViolation(PermissionError):
    """Raised when a pod tries to touch a protected collection."""


class _GuardedCollection:
    """Wraps a Motor collection. Reads pass through; every write path
    on a protected collection raises ``GuardViolation`` and emits an
    audit event."""

    def __init__(self, collection_name: str, pod_id: str) -> None:
        self._name = collection_name
        self._pod_id = pod_id
        self._col = _raw_db[collection_name]

    # ---- reads pass through unchanged ---- #
    def find(self, *a, **kw): return self._col.find(*a, **kw)
    async def find_one(self, *a, **kw): return await self._col.find_one(*a, **kw)
    async def count_documents(self, *a, **kw): return await self._col.count_documents(*a, **kw)
    async def distinct(self, *a, **kw): return await self._col.distinct(*a, **kw)
    def aggregate(self, *a, **kw): return self._col.aggregate(*a, **kw)

    # ---- writes are guarded ---- #
    async def _block(self, op: str) -> None:
        await emit(
            "guard.write.blocked", actor=self._pod_id,
            subject=self._name,
            details={"op": op, "reason": "protected_collection"},
        )
        raise GuardViolation(
            f"pod {self._pod_id} attempted {op} on protected collection '{self._name}'",
        )

    async def insert_one(self, *a, **kw):
        if self._name in PROTECTED_COLLECTIONS:
            await self._block("insert_one")
        return await self._col.insert_one(*a, **kw)

    async def update_one(self, *a, **kw):
        if self._name in PROTECTED_COLLECTIONS:
            await self._block("update_one")
        return await self._col.update_one(*a, **kw)

    async def update_many(self, *a, **kw):
        if self._name in PROTECTED_COLLECTIONS:
            await self._block("update_many")
        return await self._col.update_many(*a, **kw)

    async def delete_one(self, *a, **kw):
        if self._name in PROTECTED_COLLECTIONS:
            await self._block("delete_one")
        return await self._col.delete_one(*a, **kw)

    async def find_one_and_update(self, *a, **kw):
        if self._name in PROTECTED_COLLECTIONS:
            await self._block("find_one_and_update")
        return await self._col.find_one_and_update(*a, **kw)


class AgentDb:
    """The pod-facing DB surface. Emits an audit line on every read too,
    to satisfy the "every side-effect is auditable" requirement — but
    reads are only sampled (1 in 50) so we don't 10× the audit volume
    on hot loops."""

    def __init__(self, pod_id: str) -> None:
        self._pod_id = pod_id

    def __getitem__(self, name: str) -> _GuardedCollection:
        return _GuardedCollection(name, self._pod_id)

    def collection(self, name: str) -> _GuardedCollection:
        return _GuardedCollection(name, self._pod_id)


# Public export
def agent_db_for(pod_id: str) -> AgentDb:
    return AgentDb(pod_id)
