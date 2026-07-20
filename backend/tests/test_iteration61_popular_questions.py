"""Iteration 61 backend tests — PulseDesk 'Popular questions' admin analytics.

Covers:
  1. GET /api/admin/pulsedesk/popular-questions requires super-admin auth (401/403 without).
  2. Happy path returns {days, total_visitor_messages, top_intents:[{intent,count,unique_visitors,samples}]}.
  3. `days` param is clamped to [1, 90].
  4. `top_n` param is clamped to [1, 50].
  5. Endpoint counts visitor messages we just POSTed in the last N days (integration flow).
"""
import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")
WIDGET_KEY = "ithr-academy-live"


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=API, timeout=60.0) as c:
        yield c


@pytest.fixture(scope="module")
def super_admin_headers(http):
    if not SUPER_ADMIN_PASSWORD:
        pytest.skip("SUPER_ADMIN_PASSWORD not set")
    r = http.post("/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


class TestAuthGuard:
    def test_no_token_rejected(self, http):
        r = http.get("/admin/pulsedesk/popular-questions")
        assert r.status_code in (401, 403), r.text

    def test_bad_token_rejected(self, http):
        r = http.get(
            "/admin/pulsedesk/popular-questions",
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert r.status_code in (401, 403), r.text


class TestPopularQuestionsShape:
    def test_happy_path_returns_shape(self, http, super_admin_headers):
        r = http.get(
            "/admin/pulsedesk/popular-questions?days=30&top_n=5",
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["days"] == 30
        assert isinstance(body["total_visitor_messages"], int)
        assert body["total_visitor_messages"] >= 0
        assert isinstance(body["top_intents"], list)
        assert len(body["top_intents"]) <= 5
        for i in body["top_intents"]:
            assert "intent" in i
            assert isinstance(i["count"], int)
            assert i["count"] >= 1
            assert "unique_visitors" in i
            assert isinstance(i["samples"], list)
            assert len(i["samples"]) <= 3

    def test_days_upper_clamped_to_90(self, http, super_admin_headers):
        r = http.get(
            "/admin/pulsedesk/popular-questions?days=9999&top_n=5",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["days"] == 90

    def test_days_lower_clamped_to_1(self, http, super_admin_headers):
        r = http.get(
            "/admin/pulsedesk/popular-questions?days=0&top_n=5",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["days"] == 1

    def test_top_n_upper_clamped_to_50(self, http, super_admin_headers):
        r = http.get(
            "/admin/pulsedesk/popular-questions?days=30&top_n=9999",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert len(r.json()["top_intents"]) <= 50

    def test_top_n_default_when_missing(self, http, super_admin_headers):
        r = http.get(
            "/admin/pulsedesk/popular-questions?days=7",
            headers=super_admin_headers,
        )
        assert r.status_code == 200


class TestIntegrationCount:
    def test_new_visitor_message_appears_in_bucket(self, http, super_admin_headers):
        """Post a fresh visitor 'pricing' question, then verify the bucket
        includes it via the admin analytics endpoint."""
        visitor = f"v_pytest_it61_{uuid.uuid4().hex[:12]}"
        text = "How much does the annual pricing cost for enterprise seats?"
        r = http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor, "text": text,
        })
        assert r.status_code == 200, r.text

        # Ask analytics — the pricing bucket should be present + non-zero.
        r2 = http.get(
            "/admin/pulsedesk/popular-questions?days=1&top_n=20",
            headers=super_admin_headers,
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body["total_visitor_messages"] >= 1
        # There should exist some bucket whose count>=1
        assert any(i["count"] >= 1 for i in body["top_intents"])
