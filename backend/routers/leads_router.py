"""Enterprise lead capture — powered by /hr-suite modal + /enterprise inline form.

Public write endpoint:
    POST /api/leads/enterprise
        body: { name, email, company, role?, seats?, bundle, message?, source_url? }
        - Persists to `enterprise_leads`.
        - Fires Slack webhook alert (fire-and-forget).
        - Fires Resend auto-reply confirmation (fire-and-forget).
        - Rate-limited: 50 requests/hour per IP AND 3 requests/hour per email.

Super-admin read endpoints:
    GET  /api/admin/leads/enterprise?limit=100&status=new
    POST /api/admin/leads/enterprise/{id}/status  (mark contacted/qualified/closed)

The Slack + email side effects are decoupled — either can fail without
blocking the DB write, so the sales team never loses a lead record.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from auth import get_current_super_admin
from core import db, logger
from models import gen_id

router = APIRouter(prefix="/api", tags=["leads"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin-leads"])

LEADS_COLL = "enterprise_leads"
RATE_COLL = "lead_intake_rate"

_ALLOWED_BUNDLES = {
    "talent-ops-bundle",
    "hr-starter",
    "hr-growth",
    "hr-enterprise",
    "hr-consult",
    "generic",
}

_MAX_MESSAGE_LEN = 2000

# Rate-limit windows
_IP_HOURLY_CAP = 50    # Corporate-NAT-friendly — many legitimate leads from one office
_EMAIL_HOURLY_CAP = 3  # Same email hammering the form → clear abuse signal


# ---- Models ---------------------------------------------------------------


class EnterpriseLeadPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    company: str = Field(min_length=1, max_length=200)
    role: Optional[str] = Field(default=None, max_length=200)
    seats: Optional[int] = Field(default=None, ge=1, le=100000)
    bundle: str = Field(default="generic", max_length=64)
    message: Optional[str] = Field(default=None, max_length=_MAX_MESSAGE_LEN)
    source_url: Optional[str] = Field(default=None, max_length=500)


class LeadStatusUpdate(BaseModel):
    status: str = Field(pattern="^(new|contacted|qualified|closed_won|closed_lost)$")
    note: Optional[str] = Field(default=None, max_length=1000)


# ---- Rate limiter ---------------------------------------------------------


async def _hash_ip(ip: str) -> str:
    """Store an IP as a salted hash — never surface a raw IP in the DB."""
    salt = "ithr-lead-rate-v1"
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


async def _rate_limit_check(ip_hash: str, email: str) -> bool:
    """Enforce per-IP and per-email hourly caps.

    Returns True when the request is inside the allowance. Non-blocking:
    failure to record a rate row falls back to allowing the request (a
    broken counter must not block a legitimate lead).
    """
    now = datetime.now(timezone.utc)
    window_start_iso = (now - timedelta(hours=1)).isoformat()
    try:
        ip_count = await db[RATE_COLL].count_documents({"ip_hash": ip_hash, "ts": {"$gte": window_start_iso}})
        if ip_count >= _IP_HOURLY_CAP:
            return False
        email_count = await db[RATE_COLL].count_documents({"email": email.lower(), "ts": {"$gte": window_start_iso}})
        if email_count >= _EMAIL_HOURLY_CAP:
            return False
        await db[RATE_COLL].insert_one({
            "ip_hash": ip_hash,
            "email": email.lower(),
            "ts": now.isoformat(),
        })
        return True
    except Exception:
        logger.exception("[leads] rate-limit check failed — allowing request")
        return True


# ---- Public endpoint ------------------------------------------------------


@router.post("/leads/enterprise")
async def submit_enterprise_lead(payload: EnterpriseLeadPayload, request: Request):
    """Capture an enterprise lead, ping Slack, auto-reply the sender.

    Deliberately returns 200 for every well-formed submission (rate-limit
    silently absorbs abusive traffic — no side-channel leak on whether a
    given email was recently used, matching the enumeration-safe pattern
    used by /auth/forgot-password).
    """
    # Normalise + validate the bundle key
    bundle = (payload.bundle or "generic").strip().lower()
    if bundle not in _ALLOWED_BUNDLES:
        bundle = "generic"

    # IP → hash → rate limit
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = (forwarded.split(",")[0] if forwarded else (request.client.host if request.client else "")).strip() or "unknown"
    ip_hash = await _hash_ip(ip)
    allowed = await _rate_limit_check(ip_hash, payload.email)
    if not allowed:
        logger.info(f"[leads] rate-limit throttled ip_hash={ip_hash[:8]}… email={payload.email}")
        return {"ok": True, "lead_id": None, "throttled": True}  # silent throttle — no enumeration signal

    lead_id = gen_id()
    now_iso = datetime.now(timezone.utc).isoformat()
    lead_doc = {
        "id": lead_id,
        "name": payload.name.strip(),
        "email": payload.email.lower(),
        "company": payload.company.strip(),
        "role": (payload.role or "").strip() or None,
        "seats": payload.seats,
        "bundle": bundle,
        "message": (payload.message or "").strip() or None,
        "source_url": payload.source_url,
        "ip_hash": ip_hash,
        "user_agent": (request.headers.get("user-agent") or "")[:400],
        "status": "new",
        "created_at": now_iso,
        "slack_delivered": False,
        "confirmation_email_sent": False,
    }
    try:
        await db[LEADS_COLL].insert_one(lead_doc)
    except Exception:
        logger.exception("[leads] DB insert failed")
        raise HTTPException(status_code=500, detail="Failed to record inquiry")

    # ---- Fire-and-forget Slack + email side effects ---------------------
    async def _side_effects():
        try:
            from slack_service import send_slack_lead_alert
            ok = await send_slack_lead_alert(lead_doc)
            if ok:
                await db[LEADS_COLL].update_one({"id": lead_id}, {"$set": {"slack_delivered": True}})
        except Exception:
            logger.exception("[leads] slack dispatch raised")
        try:
            from email_service import send_enterprise_lead_confirmation_email
            ok = await send_enterprise_lead_confirmation_email(
                email=lead_doc["email"],
                full_name=lead_doc["name"],
                bundle=bundle,
                company=lead_doc["company"],
            )
            if ok:
                await db[LEADS_COLL].update_one({"id": lead_id}, {"$set": {"confirmation_email_sent": True}})
        except Exception:
            logger.exception("[leads] confirmation-email dispatch raised")
        try:
            from core import log_activity
            await log_activity(
                kind="enterprise_lead",
                message=f"New lead · {lead_doc['company']} · {bundle}",
                actor_id=None,
                actor_name=lead_doc["name"],
                target_id=lead_id,
            )
        except Exception:
            logger.exception("[leads] activity log dispatch failed")

    asyncio.create_task(_side_effects())

    return {"ok": True, "lead_id": lead_id}


# ---- Super-admin endpoints ------------------------------------------------


@admin_router.get("/leads/enterprise")
async def list_enterprise_leads(
    limit: int = 100,
    status: Optional[str] = None,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Most-recent enterprise leads first. Optional status filter."""
    limit = max(1, min(500, limit))
    query: dict = {}
    if status:
        query["status"] = status
    rows = await db[LEADS_COLL].find(query, {"_id": 0, "ip_hash": 0, "user_agent": 0}).sort("created_at", -1).to_list(limit)

    # Optional: expose Slack config state so the panel can show a "not configured" banner.
    from slack_service import slack_configured
    return {
        "leads": rows,
        "count": len(rows),
        "slack_configured": slack_configured(),
    }


@admin_router.post("/leads/enterprise/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    payload: LeadStatusUpdate,
    super_admin_id: str = Depends(get_current_super_admin),
):
    """Move a lead through the CRM funnel (new → contacted → qualified → won/lost)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {"status": payload.status, "status_updated_at": now_iso, "status_updated_by": super_admin_id}
    if payload.note:
        update["last_note"] = payload.note
    result = await db[LEADS_COLL].update_one({"id": lead_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True, "lead_id": lead_id, "status": payload.status}
