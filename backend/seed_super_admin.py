"""Idempotent super-admin seed.

Creates a single super-admin user on first startup if one does not exist.
Credentials come from env vars (with safe defaults for dev/preview).

DEPLOY NOTE: In production set SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD
via secure secrets. The default password below is intentionally generated
fresh each server boot when the env var is unset — the fingerprint is
logged so an operator can copy it from server logs the first time.
"""
import os
import secrets
import string

from auth import hash_password
from core import db, logger, now_iso

DEFAULT_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.tech")


def _generate_default_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(20))


async def seed_super_admin() -> None:
    existing = await db.users.find_one({"role": "super_admin"}, {"_id": 0, "email": 1})
    if existing:
        logger.info(f"Super-admin already exists ({existing['email']}) — skipping seed.")
        return

    password = os.environ.get("SUPER_ADMIN_PASSWORD") or _generate_default_password()
    user_doc = {
        "id": "super-admin-root",
        "email": DEFAULT_EMAIL.lower(),
        "password_hash": hash_password(password),
        "full_name": "ITHR Super Admin",
        "role": "super_admin",
        "organization": None,
        "title": "Root",
        "avatar_url": None,
        "xp": 0,
        "streak_days": 0,
        "created_at": now_iso(),
        "must_reset_password": True,
    }
    try:
        await db.users.insert_one(user_doc)
    except Exception:
        # Race with a parallel worker — safe to swallow.
        logger.exception("Super-admin insert raced; assuming another worker created it.")
        return

    # Only show the password when we generated it ourselves (env var was unset).
    if not os.environ.get("SUPER_ADMIN_PASSWORD"):
        logger.warning(
            "==================================================\n"
            f"  Super-admin created: {DEFAULT_EMAIL}\n"
            f"  Temp password (rotate immediately): {password}\n"
            "  Set SUPER_ADMIN_PASSWORD in backend/.env to fix a value.\n"
            "=================================================="
        )
    else:
        logger.info(f"Super-admin created ({DEFAULT_EMAIL}) using SUPER_ADMIN_PASSWORD env var.")
