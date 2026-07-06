"""Super-Admin console routes.

These endpoints are gated by `get_current_super_admin` — only users whose
`role == "super_admin"` at the DB level can call them. The super-admin
sign-in itself uses the regular /api/auth/login endpoint (email + password);
we deliberately do NOT surface a separate super-admin login URL on the
public landing page.

Endpoints:
- POST   /api/admin/orgs           Create an org + its first admin (owner) user.
- GET    /api/admin/orgs           List every org with member/seat stats.
- GET    /api/admin/users          List every user (paginated).
- POST   /api/admin/users/{id}/reset-password
                                    Force-reset a user's password. Returns
                                    the new temp password (one-time display).
- DELETE /api/admin/orgs/{id}      Delete an org and cascade its members.
"""
import csv
import io
import re
import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import get_current_super_admin, hash_password
from core import db, gen_invite_code, now_iso
from models_ext import Organization

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- helpers ---------------------------------------------------------
_TEMP_PW_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*"


def _generate_temp_password(length: int = 14) -> str:
    """Cryptographically-strong temp password shown once at creation time."""
    return "".join(secrets.choice(_TEMP_PW_ALPHABET) for _ in range(length))


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "organization"


def _extract_domain(email: str) -> str:
    return email.strip().lower().split("@", 1)[1] if "@" in email else ""


def _validate_create_org_payload(payload: dict) -> tuple[str, str, str, str | None, int]:
    """Validate and normalize the create-org payload. Raises HTTPException on invalid."""
    name = (payload.get("name") or "").strip()
    admin_email = (payload.get("admin_email") or "").lower().strip()
    admin_full_name = (payload.get("admin_full_name") or "").strip()
    industry = payload.get("industry")
    seat_count = int(payload.get("seat_count") or 25)

    if not name:
        raise HTTPException(status_code=400, detail="name required")
    if not admin_email or "@" not in admin_email:
        raise HTTPException(status_code=400, detail="valid admin_email required")
    if not admin_full_name:
        raise HTTPException(status_code=400, detail="admin_full_name required")
    return name, admin_email, admin_full_name, industry, seat_count


async def _unique_org_slug(name: str) -> str:
    base = _slugify(name)
    slug = base
    counter = 1
    while await db.organizations.find_one({"slug": slug}):
        counter += 1
        slug = f"{base}-{counter}"
    return slug


async def _insert_admin_user(admin_email: str, admin_full_name: str, org_name: str, temp_pw: str) -> str:
    admin_user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": admin_user_id,
        "email": admin_email,
        "password_hash": hash_password(temp_pw),
        "full_name": admin_full_name,
        "role": "learner",
        "organization": org_name,
        "title": "Enterprise Admin",
        "avatar_url": None,
        "xp": 0,
        "streak_days": 0,
        "created_at": now_iso(),
        "must_reset_password": True,
    })
    return admin_user_id


# ---------- Org + first-admin provisioning ---------------------------------
@router.post("/orgs")
async def create_org_with_admin(
    payload: dict,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Provision a new enterprise org and its first admin user in one call.

    Body: { name, admin_email, admin_full_name, industry?, seat_count? }
    Response: { organization, admin: { id, email, full_name, temp_password } }
    """
    name, admin_email, admin_full_name, industry, seat_count = _validate_create_org_payload(payload)

    if await db.users.find_one({"email": admin_email}):
        raise HTTPException(status_code=400, detail="Admin email already registered")

    slug = await _unique_org_slug(name)
    domain = _extract_domain(admin_email)
    temp_pw = _generate_temp_password()
    admin_user_id = await _insert_admin_user(admin_email, admin_full_name, name, temp_pw)

    org_obj = Organization(
        name=name,
        slug=slug,
        industry=industry,
        domain=domain,
        seat_count=max(10, min(5000, seat_count)),
        seats_used=1,
        owner_user_id=admin_user_id,
        invite_code=gen_invite_code(),
    )
    org_doc = org_obj.model_dump()
    await db.organizations.insert_one(org_doc)
    org_doc.pop("_id", None)

    await db.org_members.insert_one({
        "id": uuid.uuid4().hex,
        "org_id": org_doc["id"],
        "user_id": admin_user_id,
        "email": admin_email,
        "full_name": admin_full_name,
        "role": "owner",
        "department": "Leadership",
        "joined_at": now_iso(),
    })
    await db.users.update_one(
        {"id": admin_user_id},
        {"$set": {"org_id": org_doc["id"]}},
    )

    # Live activity feed
    try:
        import asyncio as _asyncio
        from core import log_activity
        _asyncio.create_task(log_activity(
            kind="org_created",
            message=f'New enterprise org "{name}" provisioned ({seat_count} seats)',
            actor_id=admin_user_id, actor_name=admin_full_name,
            target={"org_slug": slug, "seat_count": org_obj.seat_count},
        ))
    except Exception:
        pass

    return {
        "organization": org_doc,
        "admin": {
            "id": admin_user_id,
            "email": admin_email,
            "full_name": admin_full_name,
            "temp_password": temp_pw,
            "must_reset_password": True,
        },
    }


@router.get("/orgs")
async def list_all_orgs(_super_admin_id: str = Depends(get_current_super_admin)):
    # Single aggregation: fetch orgs + live member counts in one round-trip.
    pipeline = [
        {"$sort": {"created_at": -1}},
        {"$limit": 500},
        {"$lookup": {
            "from": "org_members",
            "localField": "id",
            "foreignField": "org_id",
            "as": "_members",
        }},
        {"$addFields": {"seats_used": {"$size": "$_members"}}},
        {"$project": {"_id": 0, "_members": 0}},
    ]
    orgs = await db.organizations.aggregate(pipeline).to_list(500)
    return {"organizations": orgs, "total": len(orgs)}


@router.delete("/orgs/{org_id}")
async def delete_org(org_id: str, _super_admin_id: str = Depends(get_current_super_admin)):
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "name": 1})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # Cascade: remove memberships (users are kept — they may exist independently)
    await db.org_members.delete_many({"org_id": org_id})
    await db.users.update_many({"org_id": org_id}, {"$unset": {"org_id": ""}, "$set": {"organization": None}})
    await db.organizations.delete_one({"id": org_id})
    return {"deleted": True, "org_id": org_id, "name": org["name"]}


# ---------- User admin -----------------------------------------------------
@router.get("/users")
async def list_all_users(
    _super_admin_id: str = Depends(get_current_super_admin),
    limit: int = 100,
    skip: int = 0,
):
    limit = max(1, min(500, limit))
    users = await db.users.find(
        {},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.users.count_documents({})
    return {"users": users, "total": total, "limit": limit, "skip": skip}


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, _super_admin_id: str = Depends(get_current_super_admin)):
    """Force-reset a user's password. Returns the new temp password (shown once)."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    temp_pw = _generate_temp_password()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hash_password(temp_pw), "must_reset_password": True}},
    )
    return {"user_id": user_id, "email": user["email"], "temp_password": temp_pw}


# ---- Analytics -----------------------------------------------------------
@router.get("/analytics")
async def platform_analytics_endpoint(
    days: int = 30,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    from analytics import platform_analytics
    days = max(7, min(90, days))
    return await platform_analytics(days=days)


# ---- Manual email dispatch (super-admin driven) --------------------------
@router.post("/emails/complaint-response")
async def admin_send_complaint_response(
    payload: dict,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Send a support-ticket response email to a specified user.

    Body: {email, ticket_ref, response_text, agent_name?, full_name?}
    """
    from email_service import send_complaint_response_email
    to_email = (payload.get("email") or "").strip().lower()
    ticket_ref = (payload.get("ticket_ref") or "").strip()
    response_text = (payload.get("response_text") or "").strip()
    if not (to_email and ticket_ref and response_text):
        raise HTTPException(status_code=400, detail="email, ticket_ref, and response_text are required")
    full_name = payload.get("full_name")
    if not full_name:
        u = await db.users.find_one({"email": to_email}, {"_id": 0, "full_name": 1})
        full_name = (u or {}).get("full_name")
    sent = await send_complaint_response_email(
        email=to_email, full_name=full_name or "there",
        ticket_ref=ticket_ref, response_text=response_text,
        agent_name=payload.get("agent_name") or "The ITHR Support Team",
    )
    return {"sent": sent, "email": to_email, "ticket_ref": ticket_ref}


@router.post("/emails/validity-expiration")
async def admin_send_validity_expiration(
    payload: dict,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Send a renewal-reminder email to a specified user.

    Body: {email, credential_or_plan, expires_on, renewal_url?, full_name?}
    """
    from email_service import send_validity_expiration_email
    to_email = (payload.get("email") or "").strip().lower()
    credential = (payload.get("credential_or_plan") or "").strip()
    expires_on = (payload.get("expires_on") or "").strip()
    if not (to_email and credential and expires_on):
        raise HTTPException(status_code=400, detail="email, credential_or_plan, and expires_on are required")
    full_name = payload.get("full_name")
    if not full_name:
        u = await db.users.find_one({"email": to_email}, {"_id": 0, "full_name": 1})
        full_name = (u or {}).get("full_name")
    sent = await send_validity_expiration_email(
        email=to_email, full_name=full_name or "there",
        credential_or_plan=credential, expires_on=expires_on,
        renewal_url=payload.get("renewal_url"),
    )
    return {"sent": sent, "email": to_email}


# ---- Live activity feed --------------------------------------------------
@router.get("/activity/recent")
async def recent_activity(
    limit: int = 25,
    since: str | None = None,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Return recent platform activity events for the super-admin feed.

    Params:
      - limit: max events to return (default 25, clamped to [1, 100])
      - since: ISO timestamp — return events created strictly AFTER this
        moment. Used by the frontend for polling delta fetches.
    """
    limit = max(1, min(100, limit))
    query = {}
    if since:
        query["created_at"] = {"$gt": since}
    events = await db.activity_events.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    # Reverse so callers can render oldest-first if they choose
    return {"events": events, "count": len(events)}


# ---- CSV export (P2, iter-31) --------------------------------------------
EXPORT_CSV_MAX_ROWS = 10000


@router.get("/activity/export.csv")
async def export_activity_csv(
    since: str | None = Query(None, description="ISO timestamp — include events strictly after this moment"),
    until: str | None = Query(None, description="ISO timestamp — include events strictly before this moment"),
    kind: str | None = Query(None, description="Filter by event kind (signup, enrollment, certificate, org_created, seat_change, ...)"),
    limit: int = Query(EXPORT_CSV_MAX_ROWS, ge=1, le=EXPORT_CSV_MAX_ROWS, description=f"Max rows (capped at {EXPORT_CSV_MAX_ROWS})"),
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Stream a CSV of platform activity events for offline audit / compliance.

    Newest events first. Columns:
      created_at, kind, actor_id, actor_name, message, target_json

    `target_json` is a JSON-encoded string of the event's `target` payload
    (course_slug, org_slug, certificate_id, etc.) so downstream tools can
    parse it without a schema per row.
    """
    import json as _json

    query: dict = {}
    ts_filter: dict = {}
    if since:
        ts_filter["$gt"] = since
    if until:
        ts_filter["$lt"] = until
    if ts_filter:
        query["created_at"] = ts_filter
    if kind:
        query["kind"] = kind

    cursor = db.activity_events.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)

    async def _iter_rows():
        # Header row
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["created_at", "kind", "actor_id", "actor_name", "message", "target_json"])
        yield buf.getvalue()

        async for ev in cursor:
            buf = io.StringIO()
            writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
            target = ev.get("target") or {}
            writer.writerow([
                ev.get("created_at", ""),
                ev.get("kind", ""),
                ev.get("actor_id", ""),
                ev.get("actor_name", ""),
                ev.get("message", ""),
                _json.dumps(target, separators=(",", ":")) if target else "",
            ])
            yield buf.getvalue()

    filename = f"ithr-activity-{now_iso()[:10]}.csv"
    return StreamingResponse(
        _iter_rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---- Cache management (super-admin ops) -----------------------------------
@router.get("/cache/stats")
async def cache_stats(_super_admin_id: str = Depends(get_current_super_admin)):
    """Return light diagnostics of the in-process TTL cache."""
    from core_cache import stats
    return stats()


@router.post("/cache/purge")
async def cache_purge(
    prefix: str | None = None,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Drop cache entries. Nuclear (no prefix) or scoped to a key_prefix.

    Known prefixes:
      - platform_analytics — /api/admin/analytics
      - org_analytics — /api/enterprise/organizations/analytics
      - catalog_courses — /api/courses list
    """
    from core_cache import bust
    dropped = bust(prefix=prefix)
    return {"dropped": dropped, "prefix": prefix}


# ---- Weekly digest runners -----------------------------------------------
@router.post("/digests/impressions/run")
async def run_impressions_digest_endpoint(
    dry_run: bool = False,
    window_days: int = 7,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Manually run the credential-impressions weekly digest.

    Idempotent within a 6-day window per user, so safe to re-run.
    Set ?dry_run=true to see the pool without sending.
    """
    from digest_jobs import run_impressions_digest
    window_days = max(1, min(30, window_days))
    return await run_impressions_digest(dry_run=dry_run, window_days=window_days)


# ---- AI course-content generation status ---------------------------------
@router.get("/courses/content-status")
async def courses_content_status(_super_admin_id: str = Depends(get_current_super_admin)):
    """Return per-course content status so admins can see which courses
    have full curricula vs stubs. Used to drive the AI pipeline decisions."""
    courses = await db.courses.find(
        {},
        {"_id": 0, "slug": 1, "title": 1, "has_full_content": 1, "content_generated_at": 1, "duration_hours": 1},
    ).sort("slug", 1).to_list(200)
    with_content = [c for c in courses if c.get("has_full_content")]
    stubs = [c for c in courses if not c.get("has_full_content")]
    return {
        "total": len(courses),
        "with_content": len(with_content),
        "stubs": len(stubs),
        "stub_slugs": [c["slug"] for c in stubs],
        "recently_generated": sorted(
            [c for c in courses if c.get("content_generated_at")],
            key=lambda c: c["content_generated_at"], reverse=True,
        )[:5],
    }
