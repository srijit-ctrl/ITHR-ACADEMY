"""Super-admin control endpoints — Tier 1.

Adds user lifecycle + impersonation + audit log on top of the existing
admin_router.py. Kept in a separate file so the deep-links from the frontend
are easy to grep and the audit-log write points are grouped.

Guardrails:
- Cannot mutate yourself (suspend/delete/demote/impersonate self).
- Cannot suspend/delete/demote the LAST remaining super_admin.
- Cannot impersonate another super_admin (defence against admin-vs-admin abuse).
- Impersonation JWT is short-lived (15 min) and carries `imp_of=<actor_id>`
  so the frontend can render a persistent "Return to admin" banner.
- All mutations write to admin_audit_log (best-effort, never blocks).
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from admin_audit import log_admin_action
from auth import JWT_ACCESS_EXPIRY_MINUTES, get_current_super_admin, create_access_token
from core import db, now_iso

router = APIRouter(prefix="/api/admin", tags=["admin-control"])

VALID_ROLES = {"learner", "instructor", "admin", "super_admin"}


# --------- helpers ---------
async def _load_user_or_404(user_id: str) -> dict:
    doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


async def _guard_not_self(actor_id: str, target_id: str) -> None:
    if actor_id == target_id:
        raise HTTPException(status_code=400, detail="You cannot perform this action on your own account.")


async def _guard_not_last_super_admin(target: dict) -> None:
    if target.get("role") != "super_admin":
        return
    remaining = await db.users.count_documents({"role": "super_admin", "id": {"$ne": target["id"]}})
    if remaining < 1:
        raise HTTPException(status_code=400, detail="Cannot demote/suspend/delete the last remaining super admin.")


# --------- SUSPEND / REACTIVATE ---------
@router.post("/users/{user_id}/suspend")
async def suspend_user(user_id: str, request: Request, admin_id: str = Depends(get_current_super_admin)):
    await _guard_not_self(admin_id, user_id)
    target = await _load_user_or_404(user_id)
    await _guard_not_last_super_admin(target)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_suspended": True, "suspended_at": now_iso(), "suspended_by": admin_id}},
    )
    await log_admin_action(admin_id, "user.suspend", "user", user_id, target.get("email", ""), None, request)
    return {"ok": True, "user_id": user_id, "is_suspended": True}


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(user_id: str, request: Request, admin_id: str = Depends(get_current_super_admin)):
    target = await _load_user_or_404(user_id)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_suspended": False}, "$unset": {"suspended_at": "", "suspended_by": ""}},
    )
    await log_admin_action(admin_id, "user.reactivate", "user", user_id, target.get("email", ""), None, request)
    return {"ok": True, "user_id": user_id, "is_suspended": False}


# --------- DELETE ---------
@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request, admin_id: str = Depends(get_current_super_admin)):
    """Cascade delete of a single user — mirrors purge_test_data.py cascade
    scope. Enrollments, certs, quiz/assessment attempts, org memberships,
    tokens, login logs, tutor sessions all go with them.
    """
    await _guard_not_self(admin_id, user_id)
    target = await _load_user_or_404(user_id)
    await _guard_not_last_super_admin(target)

    # cascade
    r_enroll = await db.enrollments.delete_many({"user_id": user_id})
    r_certs = await db.certificates.delete_many({"user_id": user_id, "certificate_id": {"$ne": "SAMPLE-ITHR-2026-001"}})
    r_members = await db.org_members.delete_many({"user_id": user_id})
    r_quiz = await db.quiz_attempts.delete_many({"user_id": user_id})
    r_assmt = await db.assessment_attempts.delete_many({"user_id": user_id})
    r_mentor = await db.mentor_sessions.delete_many({"user_id": user_id})
    r_pay = await db.payment_transactions.delete_many({"user_id": user_id})
    r_pwt = await db.password_reset_tokens.delete_many({"user_id": user_id})
    r_logs = await db.user_login_logs.delete_many({"user_id": user_id})
    r_tutor = await db.tutor_sessions.delete_many({"user_id": user_id})
    r_user = await db.users.delete_one({"id": user_id})

    meta = {
        "cascade": {
            "enrollments": r_enroll.deleted_count,
            "certificates": r_certs.deleted_count,
            "org_members": r_members.deleted_count,
            "quiz_attempts": r_quiz.deleted_count,
            "assessment_attempts": r_assmt.deleted_count,
            "mentor_sessions": r_mentor.deleted_count,
            "payment_transactions": r_pay.deleted_count,
            "password_reset_tokens": r_pwt.deleted_count,
            "user_login_logs": r_logs.deleted_count,
            "tutor_sessions": r_tutor.deleted_count,
        },
    }
    await log_admin_action(admin_id, "user.delete", "user", user_id, target.get("email", ""), meta, request)
    return {"ok": True, "deleted": r_user.deleted_count, **meta}


# --------- ROLE CHANGE ---------
class RoleChange(BaseModel):
    role: str
    reason: str | None = None


@router.post("/users/{user_id}/role")
async def change_role(user_id: str, payload: RoleChange, request: Request, admin_id: str = Depends(get_current_super_admin)):
    await _guard_not_self(admin_id, user_id)
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {sorted(VALID_ROLES)}")
    target = await _load_user_or_404(user_id)
    if target.get("role") == payload.role:
        return {"ok": True, "user_id": user_id, "role": payload.role, "noop": True}
    # If demoting a super_admin, ensure at least one remains
    if target.get("role") == "super_admin" and payload.role != "super_admin":
        await _guard_not_last_super_admin(target)
    prev_role = target.get("role", "learner")
    await db.users.update_one({"id": user_id}, {"$set": {"role": payload.role, "role_changed_at": now_iso()}})
    await log_admin_action(
        admin_id, "user.role_change", "user", user_id, target.get("email", ""),
        {"from": prev_role, "to": payload.role, "reason": payload.reason or ""},
        request,
    )
    return {"ok": True, "user_id": user_id, "role": payload.role, "previous": prev_role}


# --------- IMPERSONATION ---------
class ImpersonationReason(BaseModel):
    reason: str | None = None


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(user_id: str, payload: ImpersonationReason, request: Request, admin_id: str = Depends(get_current_super_admin)):
    """Mint a short-lived JWT for `user_id` tagged as impersonation.

    Returns { token, expires_in, user, admin_return_hint }. Frontend stores
    the caller's original token in sessionStorage, swaps to the impersonation
    token, and shows a banner. Impersonation tokens carry `imp_of=<admin_id>`.
    """
    await _guard_not_self(admin_id, user_id)
    target = await _load_user_or_404(user_id)
    if target.get("role") == "super_admin":
        raise HTTPException(status_code=403, detail="Cannot impersonate another super admin.")
    if target.get("is_suspended"):
        raise HTTPException(status_code=400, detail="Cannot impersonate a suspended user. Reactivate them first.")

    # Reuse the standard access token creator, then re-encode with imp_of claim.
    # Cleanest: manually build the payload.
    import jwt
    from datetime import datetime, timezone, timedelta
    from auth import JWT_SECRET, JWT_ALGORITHM
    payload_jwt = {
        "sub": user_id,
        "email": target["email"],
        "role": target.get("role", "learner"),
        "type": "access",
        "imp_of": admin_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_EXPIRY_MINUTES),
    }
    token = jwt.encode(payload_jwt, JWT_SECRET, algorithm=JWT_ALGORITHM)

    await log_admin_action(
        admin_id, "user.impersonate", "user", user_id, target.get("email", ""),
        {"reason": payload.reason or "", "ttl_minutes": JWT_ACCESS_EXPIRY_MINUTES},
        request,
    )
    return {
        "token": token,
        "expires_in": JWT_ACCESS_EXPIRY_MINUTES * 60,
        "user": {"id": target["id"], "email": target["email"], "full_name": target.get("full_name", ""), "role": target.get("role", "learner")},
    }


# --------- AUDIT LOG ---------
@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    action: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    _admin_id: str = Depends(get_current_super_admin),
):
    query: dict[str, Any] = {}
    if action:
        query["action"] = action
    if actor_id:
        query["actor_id"] = actor_id
    if target_id:
        query["target_id"] = target_id
    total = await db.admin_audit_log.count_documents(query)
    rows = await db.admin_audit_log.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "rows": rows, "limit": limit, "skip": skip}


@router.get("/audit-log/export.csv")
async def export_audit_log_csv(
    action: str | None = None,
    _admin_id: str = Depends(get_current_super_admin),
):
    import csv
    import io as _io
    query: dict[str, Any] = {}
    if action:
        query["action"] = action
    rows = await db.admin_audit_log.find(query, {"_id": 0}).sort("created_at", -1).limit(10000).to_list(10000)
    buf = _io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at", "actor_email", "actor_role", "action", "target_type", "target_id", "target_label", "ip", "meta"])
    for r in rows:
        writer.writerow([
            r.get("created_at", ""), r.get("actor_email", ""), r.get("actor_role", ""),
            r.get("action", ""), r.get("target_type", ""), r.get("target_id", ""),
            r.get("target_label", ""), r.get("ip", ""), str(r.get("meta", "")),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="ithr-audit-log-{now_iso()[:10]}.csv"'},
    )
