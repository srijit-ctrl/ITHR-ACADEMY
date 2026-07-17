"""Iteration 43 — Super-admin email re-sync + clash-guard tests.

Scenarios:
1) Baseline: login with canonical email superadmin@ithr.online works (200 + super_admin token).
2) Email re-sync on boot: set super_admin email in Mongo to legacy 'superadmin@ithr.tech',
   restart backend, wait, verify email is re-synced back to 'superadmin@ithr.online'
   and canonical login still works.
3) Clash guard: set super_admin email back to 'superadmin@ithr.tech' in Mongo, register
   a throwaway learner with 'superadmin@ithr.online', restart backend, verify:
     - super_admin email REMAINS 'superadmin@ithr.tech' (rename skipped)
     - "Cannot rename super-admin" is logged
     - login with superadmin@ithr.tech + $SUPER_ADMIN_PASSWORD still works (password re-sync intact)
4) Cleanup: delete throwaway learner, restart backend, verify super_admin email is
   back to 'superadmin@ithr.online' and canonical login works.

Uses:
 - REACT_APP_BACKEND_URL from /app/frontend/.env for HTTP
 - MONGO_URL + DB_NAME from /app/backend/.env for direct Mongo mutations (motor)
"""
import asyncio
import os
import subprocess
import time
from pathlib import Path

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

# ---- Config loading ---------------------------------------------------------
def _load_env(path: str) -> dict:
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


_frontend_env = _load_env("/app/frontend/.env")
_backend_env = _load_env("/app/backend/.env")

BASE_URL = (_frontend_env.get("REACT_APP_BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
MONGO_URL = _backend_env.get("MONGO_URL") or os.environ.get("MONGO_URL")
DB_NAME = _backend_env.get("DB_NAME") or os.environ.get("DB_NAME")

CANONICAL_EMAIL = "superadmin@ithr.online"
LEGACY_EMAIL = "superadmin@ithr.tech"
SUPER_PWD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

BACKEND_LOG = "/var/log/supervisor/backend.err.log"
BACKEND_OUT = "/var/log/supervisor/backend.out.log"


# ---- Helpers ----------------------------------------------------------------
async def _get_super_admin_email() -> str:
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        doc = await db.users.find_one({"role": "super_admin"}, {"_id": 0, "email": 1})
        return (doc or {}).get("email", "")
    finally:
        client.close()


async def _set_super_admin_email(new_email: str) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        await db.users.update_one({"role": "super_admin"}, {"$set": {"email": new_email}})
    finally:
        client.close()


async def _delete_user_by_email(email: str) -> int:
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        res = await db.users.delete_one({"email": email, "role": {"$ne": "super_admin"}})
        return res.deleted_count
    finally:
        client.close()


def _restart_backend_and_wait(settle_seconds: int = 10) -> None:
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True, capture_output=True)
    # poll /api/health until healthy or timeout
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=5)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    time.sleep(settle_seconds)  # allow seed_super_admin() coroutine to run


def _tail_backend_logs(bytes_per_file: int = 300000) -> str:
    """Read a large tail of both backend logs so we can grep for seed markers
    even when HTTP access log noise dominates the very end."""
    text = ""
    for path in (BACKEND_LOG, BACKEND_OUT):
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - bytes_per_file))
                    text += f.read().decode(errors="ignore")
            except Exception:
                pass
    return text


def _log_mtime_now() -> float:
    """Return current time; used as a lower bound for freshly-appended markers."""
    return time.time()


def _log_contains_since(marker: str, since_ts: float, timeout: int = 15) -> bool:
    """Poll backend.err.log for `marker` appearing at or after `since_ts`.
    Returns True as soon as the marker is found on a log line whose leading
    ISO timestamp is >= since_ts."""
    import re
    deadline = time.time() + timeout
    ts_re = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    while time.time() < deadline:
        try:
            with open(BACKEND_LOG, "rb") as f:
                # Read last 500KB to be safe against noisy access logs
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 500000))
                data = f.read().decode(errors="ignore")
            for line in data.splitlines():
                if marker not in line:
                    continue
                m = ts_re.match(line)
                if not m:
                    continue
                # Convert log ts (UTC-naive) to epoch — logs use local time same as time.time()
                # We just require it to be after since_ts (with 5s tolerance for skew)
                import datetime as _dt
                try:
                    lt = _dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
                except Exception:
                    continue
                if lt >= since_ts - 5:
                    return True
        except FileNotFoundError:
            pass
        time.sleep(1)
    return False


def _login(email: str, password: str) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )


# ---- Tests ------------------------------------------------------------------
def test_00_baseline_canonical_login_works():
    r = _login(CANONICAL_EMAIL, SUPER_PWD)
    assert r.status_code == 200, r.text
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token and len(token) > 20
    user = data.get("user") or {}
    assert user.get("role") == "super_admin"
    assert user.get("email") == CANONICAL_EMAIL


def test_01_email_resync_on_boot():
    """Mutate super-admin email to legacy, restart, expect rename back to canonical."""
    # Precondition: current email should be canonical
    current = asyncio.run(_get_super_admin_email())
    assert current == CANONICAL_EMAIL, f"expected {CANONICAL_EMAIL}, got {current}"

    # Set to legacy
    asyncio.run(_set_super_admin_email(LEGACY_EMAIL))
    assert asyncio.run(_get_super_admin_email()) == LEGACY_EMAIL

    # Restart backend and wait for seed_super_admin to run
    marker_since = _log_mtime_now()
    _restart_backend_and_wait(settle_seconds=8)

    # Verify email is back to canonical
    after = asyncio.run(_get_super_admin_email())
    assert after == CANONICAL_EMAIL, f"email not re-synced, got {after}"

    # Verify log contains the re-sync marker for THIS restart
    assert _log_contains_since("Super-admin email re-synced", marker_since), (
        "expected 'Super-admin email re-synced' in backend logs after this restart"
    )

    # Login with canonical works
    r = _login(CANONICAL_EMAIL, SUPER_PWD)
    assert r.status_code == 200, r.text


def test_02_clash_guard_prevents_rename():
    """If canonical email is taken by another user, rename must be skipped."""
    # Force legacy email on super-admin
    asyncio.run(_set_super_admin_email(LEGACY_EMAIL))
    assert asyncio.run(_get_super_admin_email()) == LEGACY_EMAIL

    # Register a throwaway learner with the canonical email
    # (endpoint from /app/backend/routers/auth_router.py — register creates learner)
    reg_payload = {
        "email": CANONICAL_EMAIL,
        "password": "TestPass123!",
        "full_name": "TEST Clash Learner",
        "organization": "TEST Corp",
        "title": "Analyst",
    }
    reg = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload, timeout=30)
    assert reg.status_code in (200, 201), f"registration failed: {reg.status_code} {reg.text}"

    try:
        # Restart backend to trigger seed_super_admin with the clash present
        marker_since = _log_mtime_now()
        _restart_backend_and_wait(settle_seconds=8)

        # Super-admin email must remain LEGACY (rename skipped)
        after = asyncio.run(_get_super_admin_email())
        assert after == LEGACY_EMAIL, f"expected rename to be skipped, but email is {after}"

        # Backend logs contain the clash error line for THIS restart
        assert _log_contains_since("Cannot rename super-admin", marker_since), (
            "expected 'Cannot rename super-admin' in backend logs after this restart"
        )

        # Password re-sync should still work — login with legacy email + env password
        r = _login(LEGACY_EMAIL, SUPER_PWD)
        assert r.status_code == 200, f"legacy-email login failed: {r.status_code} {r.text}"
        data = r.json()
        assert (data.get("user") or {}).get("role") == "super_admin"
    finally:
        # Cleanup — delete throwaway learner (guard ensures we don't touch super_admin)
        deleted = asyncio.run(_delete_user_by_email(CANONICAL_EMAIL))
        assert deleted == 1, f"cleanup: expected to delete 1 learner, deleted={deleted}"


def test_03_final_state_clean():
    """After cleanup, restart backend and expect canonical email + login."""
    _restart_backend_and_wait(settle_seconds=8)

    final = asyncio.run(_get_super_admin_email())
    assert final == CANONICAL_EMAIL, f"final email should be canonical, got {final}"

    r = _login(CANONICAL_EMAIL, SUPER_PWD)
    assert r.status_code == 200, r.text
    data = r.json()
    assert (data.get("user") or {}).get("role") == "super_admin"
    assert (data.get("user") or {}).get("email") == CANONICAL_EMAIL
