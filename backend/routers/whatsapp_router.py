"""WhatsApp routes.

Public + learner-authenticated:
  * ``POST /api/whatsapp/opt-in`` — learner-facing opt-in / opt-out toggle.
  * ``GET  /api/whatsapp/status``  — learner reads their own current opt-in state.

Twilio-only (signed):
  * ``POST /api/whatsapp/inbound`` — Twilio hits this when a learner replies.
                                     Records the message + sends the free-form
                                     ack within the newly-opened 24h window.
  * ``POST /api/whatsapp/status-callback`` — Twilio delivery status updates.

Super-admin:
  * ``GET  /api/admin/whatsapp/overview`` — opt-in rate + recent send status.
  * ``POST /api/admin/whatsapp/broadcast/new-course`` — trigger a broadcast
                                                       (idempotent by course).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from auth import get_current_user_id, get_current_super_admin
from core import db, now_iso
from models import WhatsAppOptInPayload
from whatsapp_service import (
    TEMPLATE_SIDS,
    broadcast_template,
    is_configured,
    normalise_e164,
    record_inbound_message,
    send_whatsapp_freeform_ack,
    to_whatsapp_uri,
    update_status_from_callback,
    validate_twilio_signature,
)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
admin_router = APIRouter(prefix="/api/admin/whatsapp", tags=["whatsapp-admin"])


# --------------------------------------------------------------------------- #
# Learner-facing opt-in / status
# --------------------------------------------------------------------------- #


@router.get("/status")
async def whatsapp_status(user_id: str = Depends(get_current_user_id)):
    user = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "whatsapp_number": 1, "whatsapp_opt_in": 1,
         "whatsapp_opt_in_source": 1, "whatsapp_opt_in_timestamp": 1},
    ) or {}
    return {
        "whatsapp_number": user.get("whatsapp_number"),
        "whatsapp_opt_in": bool(user.get("whatsapp_opt_in")),
        "whatsapp_opt_in_source": user.get("whatsapp_opt_in_source"),
        "whatsapp_opt_in_timestamp": user.get("whatsapp_opt_in_timestamp"),
        "integration_configured": is_configured(),
    }


@router.post("/opt-in")
async def whatsapp_opt_in(
    payload: WhatsAppOptInPayload,
    user_id: str = Depends(get_current_user_id),
):
    """Explicit opt-in / opt-out. Never runs unless the learner posts the
    request themselves — no server-side backfill, no default-true."""
    if payload.opt_in:
        # Opt-in requires a valid E.164 number.
        e164 = normalise_e164(payload.whatsapp_number or "")
        if not e164:
            raise HTTPException(
                status_code=400,
                detail="A valid mobile number in international format is required (example: +9715XXXXXXXX).",
            )
        await db.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "whatsapp_number": e164,
                    "whatsapp_opt_in": True,
                    "whatsapp_opt_in_source": payload.source,
                    "whatsapp_opt_in_timestamp": now_iso(),
                }
            },
        )
        return {"ok": True, "opt_in": True, "whatsapp_number": e164}

    # Opt-out — stop future sends immediately. Number is cleared so a
    # later re-opt-in is a deliberate new capture, not a resurrection.
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "whatsapp_opt_in": False,
                "whatsapp_opt_in_source": payload.source,
                "whatsapp_opt_in_timestamp": now_iso(),
            },
            "$unset": {"whatsapp_number": ""},
        },
    )
    return {"ok": True, "opt_in": False}


# --------------------------------------------------------------------------- #
# Twilio webhooks
# --------------------------------------------------------------------------- #


async def _read_form_and_verify(request: Request) -> dict:
    """Parse Twilio's x-www-form-urlencoded body and verify the signature.
    Twilio hits our public URL, so signature validation must use whatever
    URL Twilio actually called — we prefer PUBLIC_APP_URL when set to
    avoid mismatches behind the k8s ingress."""
    form = await request.form()
    form_dict = {k: str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature", "")
    import os
    base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
    url = f"{base}{request.url.path}" if base else str(request.url)
    if not validate_twilio_signature(url, form_dict, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    return form_dict


@router.post("/inbound")
async def whatsapp_inbound(request: Request):
    """Twilio webhook — a learner sent a WhatsApp message to our sender."""
    form = await _read_form_and_verify(request)
    user_id = await record_inbound_message(form)

    # Immediate ack — inside the freshly-opened 24h customer-service window.
    wa_from = form.get("From", "")
    if wa_from and wa_from.startswith("whatsapp:"):
        await send_whatsapp_freeform_ack(
            wa_from,
            body=(
                "Thanks — we've received your message. A member of the ITHR Academy "
                "team will follow up shortly. Reply STOP at any time to stop receiving "
                "WhatsApp updates."
            ),
            user_id=user_id,
        )
    return Response(status_code=200)


@router.post("/status-callback")
async def whatsapp_status_callback(request: Request):
    """Twilio delivery-status webhook. Updates the matching message-log row."""
    form = await _read_form_and_verify(request)
    await update_status_from_callback(form)
    return Response(status_code=200)


# --------------------------------------------------------------------------- #
# Super-admin visibility & broadcast trigger
# --------------------------------------------------------------------------- #


@admin_router.get("/overview")
async def whatsapp_overview(_sa: str = Depends(get_current_super_admin)):
    """Opt-in rate + recent-send breakdown + failed-send list for the ops team."""
    total_users = await db.users.count_documents({})
    opted_in = await db.users.count_documents({"whatsapp_opt_in": True})
    opt_in_rate = round((opted_in / total_users) * 100, 1) if total_users else 0.0

    # Recent sends (last 200) grouped by status
    recent = await db.whatsapp_message_log.find(
        {"kind": {"$in": ["template", "freeform"]}},
        {"_id": 0, "user_id": 1, "template_key": 1, "status": 1, "error_code": 1,
         "error_message": 1, "sent_at": 1, "twilio_message_sid": 1, "to": 1},
    ).sort("sent_at", -1).to_list(200)

    status_breakdown: dict[str, int] = {}
    for row in recent:
        s = row.get("status") or "unknown"
        status_breakdown[s] = status_breakdown.get(s, 0) + 1

    # Failed sends surfaced separately with error codes for ops triage.
    failed = [
        {
            "user_id": r.get("user_id"),
            "to": r.get("to"),
            "template_key": r.get("template_key"),
            "error_code": r.get("error_code"),
            "error_message": r.get("error_message"),
            "sent_at": r.get("sent_at"),
        }
        for r in recent
        if r.get("status") in ("failed", "undelivered")
    ][:50]

    # Per-template-slot readiness so the ops team can see which SIDs are
    # still pending Meta approval at a glance.
    templates_status = [
        {"key": k, "configured": bool(sid)} for k, sid in TEMPLATE_SIDS.items()
    ]

    return {
        "integration_configured": is_configured(),
        "total_users": total_users,
        "opted_in": opted_in,
        "opt_in_rate_pct": opt_in_rate,
        "templates": templates_status,
        "recent_sends_status_breakdown": status_breakdown,
        "recent_sends": recent[:50],
        "failed_sends": failed,
        "generated_at": now_iso(),
    }


@admin_router.post("/broadcast/new-course")
async def broadcast_new_course(
    course_slug: str,
    dry_run: bool = False,
    _sa: str = Depends(get_current_super_admin),
):
    """Broadcast the ``new_course`` template to every opted-in learner.

    Rate-limited to 80 msgs/sec per Twilio sender by the service layer.
    Idempotent by `course_slug + template_key` via the message log —
    a repeat call for the same course won't re-send to anyone the log
    shows was already sent."""
    course = await db.courses.find_one({"slug": course_slug}, {"_id": 0, "id": 1, "title": 1})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if dry_run:
        audience = await db.users.count_documents({"whatsapp_opt_in": True})
        return {"dry_run": True, "audience_size": audience, "template_key": "new_course",
                "template_configured": bool(TEMPLATE_SIDS.get("new_course"))}

    # Idempotency guard — collect user_ids already sent this course
    already = await db.whatsapp_message_log.distinct(
        "user_id",
        {"template_key": "new_course",
         "content_variables.course_slug": course_slug,
         "status": {"$nin": ["failed", "skipped_no_template", "not_configured"]}},
    )
    query = {"whatsapp_opt_in": True}
    if already:
        query["id"] = {"$nin": [uid for uid in already if uid]}

    def _vars_for(user):
        return {"1": (user.get("full_name") or "there").split(" ")[0],
                "2": course["title"],
                "course_slug": course_slug}

    return await broadcast_template(
        template_key="new_course",
        variables_fn=_vars_for,
        audience_query=query,
    )
