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
import re
import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException

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


# ---------- Org + first-admin provisioning ---------------------------------
@router.post("/orgs")
async def create_org_with_admin(
    payload: dict,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Provision a new enterprise org and its first admin user in one call.

    Body: { name, admin_email, admin_full_name, industry?, seat_count? }
    Response: { organization, admin: { id, email, full_name, temp_password } }

    The temp_password is returned exactly once — the super-admin is
    expected to hand it to the enterprise admin over a secure channel.
    """
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

    if await db.users.find_one({"email": admin_email}):
        raise HTTPException(status_code=400, detail="Admin email already registered")

    # slug uniqueness
    base_slug = _slugify(name)
    slug = base_slug
    counter = 1
    while await db.organizations.find_one({"slug": slug}):
        counter += 1
        slug = f"{base_slug}-{counter}"

    # Domain is derived from the admin's email — enforced for all future users
    domain = _extract_domain(admin_email)

    # 1) Create the admin user
    temp_pw = _generate_temp_password()
    admin_user_id = str(uuid.uuid4())
    admin_doc = {
        "id": admin_user_id,
        "email": admin_email,
        "password_hash": hash_password(temp_pw),
        "full_name": admin_full_name,
        "role": "learner",  # user-level role stays learner; org membership grants admin powers
        "organization": name,
        "title": "Enterprise Admin",
        "avatar_url": None,
        "xp": 0,
        "streak_days": 0,
        "created_at": now_iso(),
        "must_reset_password": True,
    }
    await db.users.insert_one(admin_doc)

    # 2) Create the org
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

    # 3) Attach admin as owner member
    member_doc = {
        "id": uuid.uuid4().hex,
        "org_id": org_doc["id"],
        "user_id": admin_user_id,
        "email": admin_email,
        "full_name": admin_full_name,
        "role": "owner",
        "department": "Leadership",
        "joined_at": now_iso(),
    }
    await db.org_members.insert_one(member_doc)

    # 4) Attach user → org
    await db.users.update_one(
        {"id": admin_user_id},
        {"$set": {"org_id": org_doc["id"]}},
    )

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
    orgs = await db.organizations.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Attach live member count in a single aggregation
    for org in orgs:
        member_count = await db.org_members.count_documents({"org_id": org["id"]})
        org["seats_used"] = member_count
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
