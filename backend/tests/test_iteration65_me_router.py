"""Backend contract tests for /api/me/* self-service portal endpoints.

Covers:
- Registration + GET /api/me + can_change_password flag
- GET /api/me/summary shape (user + kpis + next_up + recent_events)
- PATCH /api/me/profile field update
- Avatar validation (valid data URI, invalid MIME, oversized payload)
- POST /api/me/change-password happy path + same-password rejection + old-password no longer works
- POST /api/me/inspire returns non-empty quote ≤260 chars
"""
from __future__ import annotations

import base64
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"


# ----- helpers ---------------------------------------------------------------
def _unique_email():
    return f"test_me_{uuid.uuid4().hex[:10]}@example.com"


def _tiny_jpeg_data_uri():
    """Small valid data-URI. Backend only checks the MIME prefix + size."""
    b = b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"
    return "data:image/jpeg;base64," + base64.b64encode(b).decode()


@pytest.fixture(scope="module")
def registered_user():
    """Register a fresh user; yield (email, password, token, user_id)."""
    email = _unique_email()
    password = "TestPass123!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": "Test Me User"},
        timeout=20,
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token, f"no token in register response: {body}"
    user = body.get("user") or {}
    yield {
        "email": email,
        "password": password,
        "token": token,
        "user_id": user.get("id"),
    }


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ----- Tests -----------------------------------------------------------------
class TestMeContract:
    def test_get_me(self, registered_user):
        r = requests.get(f"{API}/me", headers=_h(registered_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "user" in data
        u = data["user"]
        assert u.get("email") == registered_user["email"]
        assert u.get("full_name") == "Test Me User"
        assert u.get("can_change_password") is True
        # sensitive fields must not leak
        assert "password_hash" not in u
        assert "_id" not in u

    def test_get_me_summary(self, registered_user):
        r = requests.get(f"{API}/me/summary", headers=_h(registered_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "user" in data
        assert "kpis" in data
        kpis = data["kpis"]
        for k in (
            "enrollments_total",
            "enrollments_completed",
            "enrollments_in_progress",
            "certificates",
            "avg_progress_pct",
        ):
            assert k in kpis, f"missing kpi key {k}"
        assert isinstance(kpis["enrollments_total"], int)
        assert "next_up" in data
        assert "recent_events" in data
        assert isinstance(data["recent_events"], list)

    def test_patch_profile_updates_fields(self, registered_user):
        payload = {
            "title": "Senior AI Eng",
            "bio": "Test bio",
            "location": "Dubai",
        }
        r = requests.patch(f"{API}/me/profile", json=payload, headers=_h(registered_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "updated_fields" in body
        for k in payload.keys():
            assert k in body["updated_fields"]
        # verify persistence via GET /me
        r2 = requests.get(f"{API}/me", headers=_h(registered_user["token"]), timeout=15)
        u = r2.json()["user"]
        assert u["title"] == "Senior AI Eng"
        assert u["bio"] == "Test bio"
        assert u["location"] == "Dubai"


class TestAvatarValidation:
    def test_valid_jpeg_data_uri_accepted(self, registered_user):
        uri = _tiny_jpeg_data_uri()
        r = requests.patch(
            f"{API}/me/profile",
            json={"avatar_url": uri},
            headers=_h(registered_user["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert "avatar_url" in r.json()["updated_fields"]

    def test_invalid_mime_rejected(self, registered_user):
        r = requests.patch(
            f"{API}/me/profile",
            json={"avatar_url": "data:text/plain;base64,SGVsbG8gd29ybGQ="},
            headers=_h(registered_user["token"]),
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"

    def test_oversized_avatar_rejected(self, registered_user):
        # Create a >500 KB base64 payload -> raw size > 400_000 bytes -> 413
        # 700_000 raw bytes ≈ 933_336 base64 chars
        raw = b"\xff" * 700_000
        b64 = base64.b64encode(raw).decode()
        uri = "data:image/jpeg;base64," + b64
        r = requests.patch(
            f"{API}/me/profile",
            json={"avatar_url": uri},
            headers=_h(registered_user["token"]),
            timeout=20,
        )
        # Pydantic model caps avatar_url to 800_000 chars; if exceeded returns 422.
        # For our ~933k, expect either 413 or 422. Both indicate rejection.
        assert r.status_code in (413, 422), f"expected 413/422 got {r.status_code}: {r.text}"


class TestChangePassword:
    def test_change_password_flow(self, registered_user):
        # We'll change password to a NEW one, verify login with new works,
        # verify old fails, verify same-password rejection.
        new_pw = "NewPass456!"
        r = requests.post(
            f"{API}/me/change-password",
            json={"current_password": registered_user["password"], "new_password": new_pw},
            headers=_h(registered_user["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text

        # login with new works
        r_login = requests.post(
            f"{API}/auth/login",
            json={"email": registered_user["email"], "password": new_pw},
            timeout=15,
        )
        assert r_login.status_code == 200, r_login.text
        new_token = r_login.json().get("access_token") or r_login.json().get("token")
        assert new_token

        # login with old fails
        r_old = requests.post(
            f"{API}/auth/login",
            json={"email": registered_user["email"], "password": registered_user["password"]},
            timeout=15,
        )
        assert r_old.status_code in (400, 401), f"old pw should fail but got {r_old.status_code}"

        # Same-password rejection
        r_same = requests.post(
            f"{API}/me/change-password",
            json={"current_password": new_pw, "new_password": new_pw},
            headers=_h(new_token),
            timeout=15,
        )
        assert r_same.status_code == 400, r_same.text

        # Update fixture password + token for subsequent inspire test
        registered_user["password"] = new_pw
        registered_user["token"] = new_token


class TestInspire:
    def test_inspire_returns_quote(self, registered_user):
        # Claude call may take 4-15s
        r = requests.post(
            f"{API}/me/inspire",
            json={},
            headers=_h(registered_user["token"]),
            timeout=45,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "quote" in body
        assert isinstance(body["quote"], str)
        assert len(body["quote"]) > 0, "quote should not be empty"
        assert len(body["quote"]) <= 260, f"quote too long: {len(body['quote'])}"
        assert "personalised" in body
        assert isinstance(body["personalised"], bool)


class TestAuth:
    def test_me_unauth(self):
        r = requests.get(f"{API}/me", timeout=10)
        assert r.status_code in (401, 403)
