"""Audit log for super-admin actions.

Every mutating admin action writes one row to `admin_audit_log`:
    {
      id, actor_id, actor_email, actor_role,
      action,             # "user.suspend", "user.role_change", "user.delete", "user.impersonate", ...
      target_type,        # "user" | "org" | "course" | "system"
      target_id,          # id of the affected resource
      target_label,       # human-readable (e.g. victim's email)
      meta,               # arbitrary dict — previous/new values, reason, etc.
      ip, user_agent,
      created_at,
    }

Rows are append-only. No API to delete audit rows exists on purpose.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import Request

from core import db, logger, now_iso


async def log_admin_action(
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    target_label: str = "",
    meta: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> None:
    """Persist one audit row. Best-effort — never raises."""
    try:
        actor = await db.users.find_one({"id": actor_id}, {"_id": 0, "email": 1, "role": 1})
        ip = ""
        ua = ""
        if request is not None:
            # X-Forwarded-For handling for ingress
            xff = request.headers.get("x-forwarded-for", "")
            ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "")
            ua = request.headers.get("user-agent", "")[:300]
        row = {
            "id": str(uuid.uuid4()),
            "actor_id": actor_id,
            "actor_email": (actor or {}).get("email", ""),
            "actor_role": (actor or {}).get("role", ""),
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "target_label": target_label or "",
            "meta": meta or {},
            "ip": ip,
            "user_agent": ua,
            "created_at": now_iso(),
        }
        await db.admin_audit_log.insert_one(row)
    except Exception:
        logger.exception("audit log write failed (non-fatal)")
