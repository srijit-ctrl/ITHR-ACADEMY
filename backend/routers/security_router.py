"""Tier-3 security endpoints: MFA (TOTP) self-service, security settings,
platform API keys, vendor-key rotation tracking, feature flags."""
import base64
import hashlib
import io
import os
import secrets
import uuid

import pyotp
import qrcode
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from admin_audit import log_admin_action
from auth import get_current_super_admin, get_current_user_id
from core import db, logger, now_iso
import security_service as sec

router = APIRouter(prefix="/api", tags=["security"])

ISSUER = "ITHR Academy"
VENDOR_KEY_NAMES = ["RESEND_API_KEY", "STRIPE_API_KEY", "EMERGENT_LLM_KEY", "JWT_SECRET"]


# ---- Public ------------------------------------------------------------------


@router.get("/flags")
async def public_flags():
    return await sec.get_flags()


@router.get("/security/password-policy")
async def public_password_policy():
    return (await sec.get_security_settings())["password_policy"]


# ---- MFA self-service (any authenticated user) --------------------------------


class MfaCode(BaseModel):
    code: str


@router.get("/security/mfa/status")
async def mfa_status(user_id: str = Depends(get_current_user_id)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "mfa_enabled": 1, "role": 1})
    settings = await sec.get_security_settings()
    return {
        "enabled": bool((u or {}).get("mfa_enabled")),
        "enforced": sec.mfa_enforcement_covers(settings["mfa_enforcement"], (u or {}).get("role", "learner")),
    }


@router.post("/security/mfa/setup")
async def mfa_setup(user_id: str = Depends(get_current_user_id)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "mfa_enabled": 1})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.get("mfa_enabled"):
        raise HTTPException(status_code=400, detail="MFA is already enabled")
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=u["email"], issuer_name=ISSUER)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    await db.users.update_one({"id": user_id}, {"$set": {"mfa_pending_secret": secret}})
    return {
        "qr_image": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}",
        "secret": secret,
        "otpauth_uri": uri,
    }


@router.post("/security/mfa/verify")
async def mfa_verify_setup(payload: MfaCode, user_id: str = Depends(get_current_user_id)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "mfa_pending_secret": 1})
    pending = (u or {}).get("mfa_pending_secret")
    if not pending:
        raise HTTPException(status_code=400, detail="No MFA enrollment in progress")
    if not pyotp.TOTP(pending).verify(payload.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    backup_plain = ["-".join(secrets.token_hex(2).upper() for _ in range(2)) for _ in range(8)]
    backup_hashed = [{"hash": hashlib.sha256(c.encode()).hexdigest(), "used": False} for c in backup_plain]
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"mfa_enabled": True, "mfa_secret": pending, "mfa_backup_codes": backup_hashed},
         "$unset": {"mfa_pending_secret": ""}},
    )
    logger.info(f"MFA enabled for user {user_id[:8]}…")
    return {"ok": True, "backup_codes": backup_plain}


@router.post("/security/mfa/disable")
async def mfa_disable(payload: MfaCode, user_id: str = Depends(get_current_user_id)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "mfa_enabled": 1, "mfa_secret": 1})
    if not (u or {}).get("mfa_enabled"):
        raise HTTPException(status_code=400, detail="MFA is not enabled")
    if not pyotp.TOTP(u["mfa_secret"]).verify(payload.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code — enter a current code from your authenticator")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"mfa_enabled": False}, "$unset": {"mfa_secret": "", "mfa_backup_codes": ""}},
    )
    return {"ok": True}


# ---- Superadmin: security settings --------------------------------------------


@router.get("/admin/security/settings")
async def get_settings(_admin_id: str = Depends(get_current_super_admin)):
    return await sec.get_security_settings()


@router.put("/admin/security/settings")
async def put_settings(payload: dict, request: Request, admin_id: str = Depends(get_current_super_admin)):
    updated = await sec.update_security_settings(payload)
    await log_admin_action(admin_id, "security.settings.update", "settings", "security", "Security settings", payload, request)
    return updated


# ---- Superadmin: feature flags -------------------------------------------------


@router.get("/admin/flags")
async def get_admin_flags(_admin_id: str = Depends(get_current_super_admin)):
    return await sec.get_flags()


@router.put("/admin/flags")
async def put_flags(payload: dict, request: Request, admin_id: str = Depends(get_current_super_admin)):
    updated = await sec.update_flags(payload)
    await log_admin_action(admin_id, "flags.update", "settings", "flags", "Feature flags", payload, request)
    return updated


# ---- Superadmin: platform-issued API keys --------------------------------------


class ApiKeyCreate(BaseModel):
    name: str


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.get("/admin/api-keys")
async def list_api_keys(_admin_id: str = Depends(get_current_super_admin)):
    keys = await db.platform_api_keys.find(
        {}, {"_id": 0, "key_hash": 0}
    ).sort("created_at", -1).to_list(100)
    return {"keys": keys}


@router.post("/admin/api-keys")
async def create_api_key(payload: ApiKeyCreate, request: Request, admin_id: str = Depends(get_current_super_admin)):
    raw = f"ithr_live_{secrets.token_urlsafe(32)}"
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip() or "Unnamed key",
        "prefix": raw[:16],
        "key_hash": _hash_key(raw),
        "created_by": admin_id,
        "created_at": now_iso(),
        "last_used_at": None,
        "revoked": False,
        "rotated_from": None,
    }
    await db.platform_api_keys.insert_one({**doc})
    await log_admin_action(admin_id, "apikey.create", "api_key", doc["id"], doc["name"], None, request)
    doc.pop("key_hash")
    doc.pop("_id", None)
    return {"key": raw, "record": doc}


@router.post("/admin/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: str, request: Request, admin_id: str = Depends(get_current_super_admin)):
    old = await db.platform_api_keys.find_one({"id": key_id, "revoked": False}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Active key not found")
    await db.platform_api_keys.update_one({"id": key_id}, {"$set": {"revoked": True, "revoked_at": now_iso()}})
    raw = f"ithr_live_{secrets.token_urlsafe(32)}"
    doc = {
        "id": str(uuid.uuid4()),
        "name": old["name"],
        "prefix": raw[:16],
        "key_hash": _hash_key(raw),
        "created_by": admin_id,
        "created_at": now_iso(),
        "last_used_at": None,
        "revoked": False,
        "rotated_from": key_id,
    }
    await db.platform_api_keys.insert_one({**doc})
    await log_admin_action(admin_id, "apikey.rotate", "api_key", key_id, old["name"], {"new_key_id": doc["id"]}, request)
    doc.pop("key_hash")
    doc.pop("_id", None)
    return {"key": raw, "record": doc}


@router.delete("/admin/api-keys/{key_id}")
async def revoke_api_key(key_id: str, request: Request, admin_id: str = Depends(get_current_super_admin)):
    target = await db.platform_api_keys.find_one({"id": key_id}, {"_id": 0, "name": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Key not found")
    await db.platform_api_keys.update_one({"id": key_id}, {"$set": {"revoked": True, "revoked_at": now_iso()}})
    await log_admin_action(admin_id, "apikey.revoke", "api_key", key_id, target["name"], None, request)
    return {"ok": True}


@router.get("/partner/ping")
async def partner_ping(x_api_key: str = Header(default="")):
    """Validation endpoint for platform-issued partner API keys."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    rec = await db.platform_api_keys.find_one({"key_hash": _hash_key(x_api_key), "revoked": False}, {"_id": 0, "id": 1, "name": 1})
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    await db.platform_api_keys.update_one({"id": rec["id"]}, {"$set": {"last_used_at": now_iso()}})
    return {"ok": True, "key_name": rec["name"]}


# ---- Superadmin: vendor (3rd-party) key rotation tracking ----------------------


@router.get("/admin/vendor-keys")
async def vendor_keys(_admin_id: str = Depends(get_current_super_admin)):
    meta = {m["key_name"]: m async for m in db.vendor_key_meta.find({}, {"_id": 0})}
    out = []
    for name in VENDOR_KEY_NAMES:
        val = os.environ.get(name, "")
        m = meta.get(name, {})
        out.append({
            "key_name": name,
            "configured": bool(val),
            "masked": f"{val[:6]}…{val[-4:]}" if len(val) > 12 else ("•••" if val else ""),
            "last_rotated_at": m.get("last_rotated_at"),
            "reminder_days": m.get("reminder_days", 90),
        })
    return {"keys": out}


@router.post("/admin/vendor-keys/{key_name}/mark-rotated")
async def mark_vendor_rotated(key_name: str, request: Request, admin_id: str = Depends(get_current_super_admin)):
    if key_name not in VENDOR_KEY_NAMES:
        raise HTTPException(status_code=404, detail="Unknown vendor key")
    await db.vendor_key_meta.update_one(
        {"key_name": key_name},
        {"$set": {"key_name": key_name, "last_rotated_at": now_iso()}, "$setOnInsert": {"reminder_days": 90}},
        upsert=True,
    )
    await log_admin_action(admin_id, "vendorkey.mark_rotated", "vendor_key", key_name, key_name, None, request)
    return {"ok": True, "last_rotated_at": now_iso()}
