"""Shared test fixtures.

Reads test credentials from env so hardcoded literals never appear in
individual test files. `TestPass123!` and `Dubai_deram2026` remain the
defaults for local runs — production/CI can override via env.
"""
import os
import uuid

import httpx

API_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
TEST_USER_PASSWORD = os.environ.get("E2E_TEST_USER_PASSWORD", "TestPass123!")  # noqa: S105 — dev fixture
SUPER_ADMIN_EMAIL = os.environ.get("E2E_SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SUPER_ADMIN_PASSWORD = os.environ.get("E2E_SUPER_ADMIN_PASSWORD", "Dubai_deram2026")  # noqa: S105


def register_learner(name: str = "E2E Tester", prefix: str = "e2e") -> tuple[str, str]:
    """Register a fresh learner. Returns (email, token)."""
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = httpx.post(
        f"{API_URL}/api/auth/register",
        json={"email": email, "password": TEST_USER_PASSWORD, "full_name": name},
        timeout=15,
    )
    r.raise_for_status()
    return email, r.json()["token"]


def super_admin_token() -> str:
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["token"]
