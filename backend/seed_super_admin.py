"""Idempotent super-admin seed with password sync.

Behaviour on every backend boot:
1. If no super-admin exists → create one with either
   $SUPER_ADMIN_PASSWORD (if set) or a fresh random password (logged once).
2. If a super-admin already exists AND $SUPER_ADMIN_PASSWORD is set → sync
   the DB password_hash to the env-var value so operators can rotate the
   secret by rotating the Emergent secret + restarting the pod.
3. If a super-admin already exists AND $SUPER_ADMIN_PASSWORD is unset →
   leave it alone (safest — some other operator may have rotated via API).

Additionally: if the env-var value is the well-known preview placeholder
(`preview-only-rotate-in-prod`) but the runtime environment looks like
production (host resolves to `learn.ithr.tech` or `SUPER_ADMIN_PASSWORD`
is literally set to the placeholder value in prod), log a loud WARNING so
operators cannot miss the misconfiguration.

DEPLOY NOTE: in production, set `SUPER_ADMIN_PASSWORD` via the Emergent
secret manager. Do NOT commit a real value to `.env` in this repo.
"""
import os
import secrets
import string

from auth import hash_password, verify_password
from core import db, logger, now_iso

DEFAULT_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.tech")
PLACEHOLDER_PASSWORD = "preview-only-rotate-in-prod"  # nosec B105 — sentinel constant, not a live secret. See CODE_QUALITY_NOTES.md.


def _generate_default_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(20))


def _looks_like_production() -> bool:
    """Best-effort check — does this pod look like production?"""
    for var in ("PUBLIC_APP_URL", "REACT_APP_BACKEND_URL"):
        v = (os.environ.get(var) or "").lower()
        if "learn.ithr.tech" in v or "ithr.host" in v:
            return True
    return False


def _log_placeholder_warning() -> None:
    if _looks_like_production():
        logger.error(
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "  SUPER_ADMIN_PASSWORD is the preview placeholder in a production env.\n"
            "  ROTATE IMMEDIATELY via the Emergent secret manager, then restart.\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        )
    else:
        logger.warning(
            "Super-admin using preview placeholder password — fine for preview, "
            "must be rotated in production."
        )


async def seed_super_admin() -> None:
    env_password = os.environ.get("SUPER_ADMIN_PASSWORD")
    existing = await db.users.find_one(
        {"role": "super_admin"},
        {"_id": 0, "email": 1, "password_hash": 1},
    )

    if existing:
        # Sync password to env-var if it's set (enables rotate-via-restart)
        if env_password:
            if not verify_password(env_password, existing.get("password_hash", "")):
                await db.users.update_one(
                    {"role": "super_admin"},
                    {"$set": {"password_hash": hash_password(env_password)}},
                )
                logger.info(f"Super-admin ({existing['email']}) password re-synced from SUPER_ADMIN_PASSWORD env var.")
            if env_password == PLACEHOLDER_PASSWORD:
                _log_placeholder_warning()
        else:
            logger.info(f"Super-admin already exists ({existing['email']}) — SUPER_ADMIN_PASSWORD unset, leaving DB password unchanged.")
        return

    # No super-admin yet — create one
    password = env_password or _generate_default_password()
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
        logger.exception("Super-admin insert raced; assuming another worker created it.")
        return

    if not env_password:
        logger.warning(
            "==================================================\n"
            f"  Super-admin created: {DEFAULT_EMAIL}\n"
            f"  Temp password (rotate immediately): {password}\n"
            "  Set SUPER_ADMIN_PASSWORD in the secret manager to lock a value.\n"
            "=================================================="
        )
    elif env_password == PLACEHOLDER_PASSWORD:
        _log_placeholder_warning()
    else:
        logger.info(f"Super-admin created ({DEFAULT_EMAIL}) using SUPER_ADMIN_PASSWORD env var.")
