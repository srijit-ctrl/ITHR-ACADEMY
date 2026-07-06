"""Iteration 21 — Password reset (forgot-password + reset-password) tests.

Covers:
- POST /api/auth/forgot-password happy path (existing user), unknown email
  (no enumeration leak), malformed email (422), rate limiting (silent throttle).
- POST /api/auth/reset-password happy path, expired token, consumed token,
  invalid token, short password (422).
- password_reset_tokens collection indexes (unique token_hash, TTL, user_id).

Uses SYNC pymongo (not motor) to avoid event-loop-closed issues with pytest-xdist
loadscope + module-scoped fixtures. The E2E happy path seeds a raw token directly
into MongoDB using the exact SHA-256 hashing pattern the router uses, so we
don't depend on Resend sandbox delivery to exercise the reset endpoint.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

# Load env before anything else
load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent.parent / "frontend" / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def test_user(api):
    """Register a fresh user for the whole module."""
    ts = int(time.time() * 1000)  # ms to reduce collision on rapid reruns
    email = f"iter21.reset+{ts}@example.com"
    password = "OldPass123!"
    r = api.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Iter21 Reset Tester",
        "organization": "Test Corp",
        "title": "Analyst",
    })
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "email": email,
        "password": password,
        "user_id": data["user"]["id"],
    }


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _reset_rate_limits(mongo):
    """Wipe pw_reset_rate so tests are hermetic."""
    mongo.pw_reset_rate.delete_many({})


# ---------------------------------------------------------------------------
# forgot-password endpoint
# ---------------------------------------------------------------------------
class TestForgotPassword:
    def test_forgot_existing_user_returns_200_and_inserts_token(self, api, mongo, test_user):
        _reset_rate_limits(mongo)
        # Wipe any pre-existing token rows for this email to snapshot cleanly
        mongo.password_reset_tokens.delete_many({"email": test_user["email"]})
        before = mongo.password_reset_tokens.count_documents({"email": test_user["email"]})

        r = api.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": test_user["email"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "If an account exists" in body.get("message", "")

        after = mongo.password_reset_tokens.count_documents({"email": test_user["email"]})
        assert after == before + 1, f"expected 1 new token row (before={before} after={after})"

        doc = mongo.password_reset_tokens.find_one(
            {"email": test_user["email"], "consumed": False},
            sort=[("created_at", -1)],
        )
        assert doc is not None
        assert "token_hash" in doc and len(doc["token_hash"]) == 64  # sha256 hex
        assert "expires_at" in doc
        assert doc.get("consumed") is False
        assert doc.get("user_id") == test_user["user_id"]

    def test_forgot_unknown_email_returns_200_no_row(self, api, mongo):
        _reset_rate_limits(mongo)
        unknown = f"iter21.unknown+{int(time.time() * 1000)}@example.com"
        before = mongo.password_reset_tokens.count_documents({"email": unknown})

        r = api.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": unknown})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "If an account exists" in body.get("message", "")

        after = mongo.password_reset_tokens.count_documents({"email": unknown})
        assert after == before, "no row should be created for unknown email"

    def test_forgot_malformed_email_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "not-an-email"})
        assert r.status_code == 422, r.text

    def test_forgot_rate_limit_silent_throttle(self, api, mongo, test_user):
        """8 calls in a row: further calls still 200 but no new token rows beyond email limit=3."""
        _reset_rate_limits(mongo)
        email = test_user["email"]
        mongo.password_reset_tokens.delete_many({"email": email})
        before = mongo.password_reset_tokens.count_documents({"email": email})

        codes = []
        for _ in range(8):
            r = api.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email})
            codes.append(r.status_code)
        assert all(c == 200 for c in codes), f"all responses should be 200 (got {codes})"

        after = mongo.password_reset_tokens.count_documents({"email": email})
        new_rows = after - before
        # email limit = 3/hour; IP limit = 5/hour. So at most 3 new rows.
        assert new_rows <= 3, f"expected ≤3 new rows under rate limit, got {new_rows}"
        assert new_rows >= 1, "at least the first call should have inserted a row"


# ---------------------------------------------------------------------------
# reset-password endpoint
# ---------------------------------------------------------------------------
class TestResetPassword:
    def test_reset_happy_path(self, api, mongo, test_user):
        """Seed a fresh token, POST reset, verify user password changed."""
        _reset_rate_limits(mongo)
        mongo.password_reset_tokens.delete_many({"user_id": test_user["user_id"]})

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mongo.password_reset_tokens.insert_one({
            "user_id": test_user["user_id"],
            "email": test_user["email"],
            "token_hash": token_hash,
            "expires_at": expires_at,
            "consumed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ip": "test",
        })

        new_password = "NewPass123!"
        r = api.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": raw_token,
            "new_password": new_password,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True

        # (a) Old password no longer works
        r_old = api.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_user["email"], "password": test_user["password"],
        })
        assert r_old.status_code == 401, f"old password should be rejected, got {r_old.status_code}"

        # (b) New password works
        r_new = api.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_user["email"], "password": new_password,
        })
        assert r_new.status_code == 200, f"new password should log in, got {r_new.status_code} {r_new.text}"
        assert "token" in r_new.json()

        # (c) Token row is now consumed=true + consumed_at set
        doc = mongo.password_reset_tokens.find_one({"token_hash": token_hash})
        assert doc is not None
        assert doc.get("consumed") is True
        assert doc.get("consumed_at")

        test_user["password"] = new_password

    def test_reset_with_expired_token(self, api, mongo, test_user):
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)  # already expired
        mongo.password_reset_tokens.insert_one({
            "user_id": test_user["user_id"],
            "email": test_user["email"],
            "token_hash": token_hash,
            "expires_at": expires_at,
            "consumed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ip": "test",
        })
        r = api.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": raw_token,
            "new_password": "AnotherPass1!",
        })
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "expired" in detail, f"expected 'expired' in detail, got '{detail}'"
        mongo.password_reset_tokens.delete_one({"token_hash": token_hash})

    def test_reset_with_consumed_token_reuse(self, api, mongo, test_user):
        """Seed a token, consume it, then try again → 400."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mongo.password_reset_tokens.insert_one({
            "user_id": test_user["user_id"],
            "email": test_user["email"],
            "token_hash": token_hash,
            "expires_at": expires_at,
            "consumed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ip": "test",
        })
        # First use — success
        r1 = api.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": raw_token,
            "new_password": "ReusePass123!",
        })
        assert r1.status_code == 200, r1.text
        test_user["password"] = "ReusePass123!"

        # Second use — should fail
        r2 = api.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": raw_token,
            "new_password": "AnotherPass456!",
        })
        assert r2.status_code == 400, r2.text
        detail = (r2.json().get("detail") or "").lower()
        assert "invalid" in detail or "already been used" in detail, f"got detail={detail}"

    def test_reset_with_invalid_token(self, api):
        r = api.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": "totally-bogus-non-existent-token-123456789012345",
            "new_password": "NewPass123!",
        })
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "invalid" in detail or "expired" in detail

    def test_reset_with_short_password_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": "a" * 32,  # meets min_length=20 on token
            "new_password": "abc",  # too short
        })
        assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Indexes on password_reset_tokens collection
# ---------------------------------------------------------------------------
class TestPasswordResetIndexes:
    def test_indexes_exist(self, mongo):
        info = mongo.password_reset_tokens.index_information()
        token_hash_idx = None
        expires_ttl_idx = None
        user_id_idx = None
        for name, meta in info.items():
            keys = meta.get("key", [])
            if any(k[0] == "token_hash" for k in keys):
                token_hash_idx = meta
            if any(k[0] == "expires_at" for k in keys):
                expires_ttl_idx = meta
            if any(k[0] == "user_id" for k in keys):
                user_id_idx = meta

        assert token_hash_idx is not None, "token_hash index missing"
        assert token_hash_idx.get("unique") is True, "token_hash index should be unique"

        assert expires_ttl_idx is not None, "expires_at TTL index missing"
        assert expires_ttl_idx.get("expireAfterSeconds") == 0, (
            f"expires_at TTL should be expireAfterSeconds=0, got {expires_ttl_idx.get('expireAfterSeconds')}"
        )

        assert user_id_idx is not None, "user_id index missing"
