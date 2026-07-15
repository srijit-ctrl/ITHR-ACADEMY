"""Tier-3 security primitives: password policy, MFA (TOTP), feature flags, MFA challenge tokens."""
import re
import time
from datetime import datetime, timedelta, timezone

import jwt

from auth import JWT_SECRET, JWT_ALGORITHM
from core import db

DEFAULT_PASSWORD_POLICY = {
    "min_length": 8,
    "require_upper": True,
    "require_lower": True,
    "require_digit": True,
    "require_symbol": False,
    "block_common": True,
    "expiry_days": 0,
}

DEFAULT_MFA_ENFORCEMENT = "off"  # off | super_admins | admins | all

DEFAULT_FLAGS = {
    "registrations": True,
    "referrals": True,
    "ai_tutor": True,
    "chat_quiz": True,
    "voice_io": True,
    "checkout": True,
    "intelligence_desk": True,
}

COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "admin123", "letmein1", "welcome1", "iloveyou",
    "sunshine1", "princess1", "football1", "monkey123", "dragon123", "master123",
    "abc12345", "passw0rd", "p@ssword", "password!", "changeme1",
}


async def get_security_settings() -> dict:
    doc = await db.platform_settings.find_one({"id": "security"}, {"_id": 0}) or {}
    policy = {**DEFAULT_PASSWORD_POLICY, **(doc.get("password_policy") or {})}
    return {
        "mfa_enforcement": doc.get("mfa_enforcement", DEFAULT_MFA_ENFORCEMENT),
        "password_policy": policy,
    }


async def update_security_settings(patch: dict) -> dict:
    current = await get_security_settings()
    if "mfa_enforcement" in patch and patch["mfa_enforcement"] in ("off", "super_admins", "admins", "all"):
        current["mfa_enforcement"] = patch["mfa_enforcement"]
    if isinstance(patch.get("password_policy"), dict):
        allowed = set(DEFAULT_PASSWORD_POLICY)
        current["password_policy"].update({k: v for k, v in patch["password_policy"].items() if k in allowed})
    await db.platform_settings.update_one(
        {"id": "security"}, {"$set": {"id": "security", **current}}, upsert=True
    )
    return current


def validate_password(password: str, policy: dict) -> list:
    errors = []
    if len(password) < policy["min_length"]:
        errors.append(f"Password must be at least {policy['min_length']} characters")
    if policy["require_upper"] and not re.search(r"[A-Z]", password):
        errors.append("Must contain an uppercase letter")
    if policy["require_lower"] and not re.search(r"[a-z]", password):
        errors.append("Must contain a lowercase letter")
    if policy["require_digit"] and not re.search(r"\d", password):
        errors.append("Must contain a digit")
    if policy["require_symbol"] and not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Must contain a symbol")
    if policy["block_common"] and password.lower() in COMMON_PASSWORDS:
        errors.append("This password is too common — choose something unique")
    return errors


def mfa_enforcement_covers(enforcement: str, role: str) -> bool:
    if enforcement == "all":
        return True
    if enforcement == "admins":
        return role in ("admin", "super_admin", "corporate_admin")
    if enforcement == "super_admins":
        return role == "super_admin"
    return False


# ---- MFA challenge tokens (password verified, TOTP pending) ----------------


def create_mfa_challenge_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "mfa_challenge",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_mfa_challenge_token(token: str) -> str:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "mfa_challenge":
        raise ValueError("Not an MFA challenge token")
    return payload["sub"]


# ---- Feature flags (15s cache) ----------------------------------------------

_flags_cache = {"value": None, "at": 0.0}


async def get_flags() -> dict:
    now = time.monotonic()
    if _flags_cache["value"] is not None and now - _flags_cache["at"] < 15:
        return _flags_cache["value"]
    doc = await db.platform_settings.find_one({"id": "flags"}, {"_id": 0, "id": 0}) or {}
    flags = {**DEFAULT_FLAGS, **{k: bool(v) for k, v in doc.items() if k in DEFAULT_FLAGS}}
    _flags_cache.update(value=flags, at=now)
    return flags


async def update_flags(patch: dict) -> dict:
    updates = {k: bool(v) for k, v in patch.items() if k in DEFAULT_FLAGS}
    if updates:
        await db.platform_settings.update_one({"id": "flags"}, {"$set": {"id": "flags", **updates}}, upsert=True)
    _flags_cache.update(value=None, at=0.0)
    return await get_flags()


async def flag_enabled(name: str) -> bool:
    return (await get_flags()).get(name, True)


def require_flag(name: str):
    from fastapi import HTTPException

    async def dep():
        if not await flag_enabled(name):
            raise HTTPException(status_code=403, detail="This feature is currently disabled by the platform administrator")
    return dep
