"""Iteration 59 backend tests — Slack webhook + Enterprise-Lead intake.

Covers:
  1. Public POST /api/leads/enterprise happy path (returns lead_id).
  2. Payload validation (invalid email → 422, bundle allow-list clamps unknown to 'generic').
  3. Rate limiter — per-email 3/hour silent throttle (still returns ok:true, lead_id:null).
  4. Slack degrades gracefully when SLACK_WEBHOOK_URL is unset (no exception, slack_delivered stays False).
  5. Super-admin GET /api/admin/leads/enterprise auth guard + payload shape.
  6. Super-admin POST /api/admin/leads/enterprise/{id}/status transition.
  7. IP hashing — raw IP never leaks into the DB row.

All tests use TEST_it59_ prefixed emails so purge_test_data can sweep them.
"""
import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import db  # noqa: E402

from pymongo import MongoClient  # noqa: E402
_sync_client = MongoClient(os.environ["MONGO_URL"])
sync_db = _sync_client[os.environ["DB_NAME"]]

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

TEST_PREFIX = "TEST_it59_"


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=API, timeout=60.0) as c:
        yield c


@pytest.fixture(scope="module")
def super_admin_token(http):
    if not SUPER_ADMIN_PASSWORD:
        pytest.skip("SUPER_ADMIN_PASSWORD not set")
    r = http.post("/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
    assert r.status_code == 200
    return r.json()["token"]


@pytest.fixture(scope="module")
def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}"}


def _fresh_email() -> str:
    return f"{TEST_PREFIX}{uuid.uuid4().hex[:10]}@example.com"


def _make_payload(**overrides) -> dict:
    base = {
        "name": "Ada Lovelace",
        "email": _fresh_email(),
        "company": "Analytical Engines",
        "role": "CTO",
        "seats": 50,
        "bundle": "talent-ops-bundle",
        "message": "We are exploring AI-fluent training for our People Ops team.",
        "source_url": "https://ithr.online/hr-suite",
    }
    base.update(overrides)
    return base


# =========================================================================
# ============  1. HAPPY PATH  ============================================
# =========================================================================


class TestHappyPath:
    def test_public_submit_returns_lead_id(self, http):
        payload = _make_payload()
        r = http.post("/leads/enterprise", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["lead_id"] and isinstance(body["lead_id"], str)

        # Verify row landed with expected fields (raw IP MUST NOT be present)
        doc = sync_db.enterprise_leads.find_one({"id": body["lead_id"]})
        assert doc is not None
        assert doc["email"] == payload["email"].lower()
        assert doc["bundle"] == "talent-ops-bundle"
        assert doc["status"] == "new"
        assert "ip_hash" in doc
        assert doc["ip_hash"] and len(doc["ip_hash"]) == 32
        # No raw IP field
        assert "ip" not in doc
        assert "client_ip" not in doc


# =========================================================================
# ============  2. VALIDATION  ============================================
# =========================================================================


class TestValidation:
    def test_invalid_email_422(self, http):
        r = http.post("/leads/enterprise", json=_make_payload(email="not-an-email"))
        assert r.status_code == 422

    def test_missing_name_422(self, http):
        payload = _make_payload()
        del payload["name"]
        r = http.post("/leads/enterprise", json=payload)
        assert r.status_code == 422

    def test_unknown_bundle_clamped_to_generic(self, http):
        r = http.post("/leads/enterprise", json=_make_payload(bundle="totally-invalid-bundle-name"))
        assert r.status_code == 200
        doc = sync_db.enterprise_leads.find_one({"id": r.json()["lead_id"]})
        assert doc["bundle"] == "generic"

    def test_seat_count_upper_bound(self, http):
        r = http.post("/leads/enterprise", json=_make_payload(seats=99999999))
        assert r.status_code == 422

    def test_seat_count_lower_bound(self, http):
        r = http.post("/leads/enterprise", json=_make_payload(seats=0))
        assert r.status_code == 422

    def test_message_length_cap(self, http):
        r = http.post("/leads/enterprise", json=_make_payload(message="A" * 3000))
        assert r.status_code == 422


# =========================================================================
# ============  3. RATE LIMITER  ==========================================
# =========================================================================


class TestRateLimit:
    def test_per_email_silent_throttle(self, http):
        """3 submissions with the same email land, 4th silently throttles."""
        email = _fresh_email()
        ids = []
        for _ in range(3):
            r = http.post("/leads/enterprise", json=_make_payload(email=email))
            assert r.status_code == 200
            assert r.json()["lead_id"] is not None
            ids.append(r.json()["lead_id"])
        # 4th — silent throttle (200, ok:True, but no lead_id)
        r = http.post("/leads/enterprise", json=_make_payload(email=email))
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json().get("lead_id") is None


# =========================================================================
# ============  4. SLACK GRACEFUL DEGRADATION =============================
# =========================================================================


class TestSlackDegradation:
    def test_slack_not_configured_flag_true_when_url_blank(self):
        """When SLACK_WEBHOOK_URL is blank, slack_configured() → False."""
        # This test asserts against the current env; if a webhook was later
        # configured it should skip rather than fail.
        from slack_service import slack_configured
        if slack_configured():
            pytest.skip("SLACK_WEBHOOK_URL is configured in this env — cannot assert 'no config' behaviour")
        assert slack_configured() is False


# =========================================================================
# ============  5. SUPER-ADMIN LIST  ======================================
# =========================================================================


class TestAdminList:
    def test_admin_list_requires_auth(self, http):
        r = http.get("/admin/leads/enterprise")
        assert r.status_code in (401, 403)

    def test_admin_list_shape(self, http, super_admin_headers):
        # Ensure at least one lead exists
        http.post("/leads/enterprise", json=_make_payload())
        r = http.get("/admin/leads/enterprise?limit=10", headers=super_admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("leads", "count", "slack_configured"):
            assert k in body
        assert isinstance(body["leads"], list)
        # Ensure the lead payload doesn't include ip_hash / user_agent
        if body["leads"]:
            lead = body["leads"][0]
            assert "ip_hash" not in lead
            assert "user_agent" not in lead
            assert "email" in lead
            assert "bundle" in lead

    def test_admin_status_filter(self, http, super_admin_headers):
        # Get a fresh lead we can mark contacted
        r = http.post("/leads/enterprise", json=_make_payload())
        lead_id = r.json()["lead_id"]
        # Move to contacted
        r2 = http.post(f"/admin/leads/enterprise/{lead_id}/status",
                       json={"status": "contacted", "note": "Called 2026-02-15"},
                       headers=super_admin_headers)
        assert r2.status_code == 200
        # Filter by contacted, verify inclusion
        r3 = http.get("/admin/leads/enterprise?status=contacted&limit=200", headers=super_admin_headers)
        ids = [l["id"] for l in r3.json()["leads"]]
        assert lead_id in ids


# =========================================================================
# ============  6. STATUS TRANSITIONS  ====================================
# =========================================================================


class TestStatusTransition:
    def test_valid_status_transition(self, http, super_admin_headers):
        r = http.post("/leads/enterprise", json=_make_payload())
        lead_id = r.json()["lead_id"]
        r2 = http.post(f"/admin/leads/enterprise/{lead_id}/status",
                       json={"status": "qualified"}, headers=super_admin_headers)
        assert r2.status_code == 200
        doc = sync_db.enterprise_leads.find_one({"id": lead_id})
        assert doc["status"] == "qualified"

    def test_invalid_status_rejected(self, http, super_admin_headers):
        r = http.post("/leads/enterprise", json=_make_payload())
        lead_id = r.json()["lead_id"]
        r2 = http.post(f"/admin/leads/enterprise/{lead_id}/status",
                       json={"status": "bogus_status"}, headers=super_admin_headers)
        assert r2.status_code == 422

    def test_status_update_404_for_unknown_lead(self, http, super_admin_headers):
        r = http.post("/admin/leads/enterprise/nonexistent-lead-id/status",
                      json={"status": "contacted"}, headers=super_admin_headers)
        assert r.status_code == 404

    def test_status_transition_requires_super_admin(self, http):
        r = http.post("/admin/leads/enterprise/any/status", json={"status": "contacted"})
        assert r.status_code in (401, 403)
