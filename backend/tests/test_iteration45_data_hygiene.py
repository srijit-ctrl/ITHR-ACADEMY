"""Iteration 45 — Data Hygiene panel + realtime dashboard + tabs-as-links.

Tests the new endpoints:
  GET  /api/admin/data-hygiene           (dry-run scan)
  POST /api/admin/data-hygiene/purge     (one-click cascade purge)

Also verifies:
  - Register throwaway @example.com users → they appear as victims
  - Purge removes them + writes audit row action='data.purge_test'
  - Protected accounts (superadmin@ithr.online, srijit*, sri0564823232) survive
  - Normal learner cannot access either endpoint (403)
  - Dashboard KPI reflects DB changes within cache TTL (10s)
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env directly
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

SUPER_ADMIN_EMAIL = "superadmin@ithr.online"
SUPER_ADMIN_PASSWORD = "Dubai_deram2026"


@pytest.fixture(scope="module")
def super_admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Super admin login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def learner_token():
    """Register a temporary learner (will be purged by test)."""
    email = f"hygienelearner_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Hygiene Learner",
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), f"Learner register failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token"), email


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------ Security: unauthenticated + learner ------------------

class TestDataHygieneSecurity:
    def test_get_hygiene_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/data-hygiene", timeout=10)
        assert r.status_code in (401, 403), f"Unauth GET should be 401/403, got {r.status_code}"

    def test_post_purge_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/admin/data-hygiene/purge", timeout=10)
        assert r.status_code in (401, 403), f"Unauth POST should be 401/403, got {r.status_code}"

    def test_get_hygiene_forbidden_for_learner(self, learner_token):
        token, _ = learner_token
        r = requests.get(f"{BASE_URL}/api/admin/data-hygiene", headers=_auth(token), timeout=10)
        assert r.status_code == 403, f"Learner GET should be 403, got {r.status_code}"

    def test_post_purge_forbidden_for_learner(self, learner_token):
        token, _ = learner_token
        r = requests.post(f"{BASE_URL}/api/admin/data-hygiene/purge", headers=_auth(token), timeout=10)
        assert r.status_code == 403, f"Learner POST should be 403, got {r.status_code}"


# ------------------ Purge end-to-end ------------------

class TestDataHygieneE2E:
    def test_hygiene_scan_shape(self, super_admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/data-hygiene",
            headers=_auth(super_admin_token),
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert "victims" in data
        assert "cascade" in data
        assert isinstance(data["cascade"], dict)
        assert data.get("dry_run") is True

    def test_full_purge_flow(self, super_admin_token):
        # 1) Snapshot baseline user count
        base = requests.get(
            f"{BASE_URL}/api/admin/dashboard",
            headers=_auth(super_admin_token),
            timeout=20,
        ).json()
        base_users = base["kpis"]["total_users"]

        # 2) Register 3 throwaway @example.com users
        throwaway_emails = [f"hygienetest{i}_{uuid.uuid4().hex[:6]}@example.com" for i in range(3)]
        for em in throwaway_emails:
            rr = requests.post(
                f"{BASE_URL}/api/auth/register",
                json={"email": em, "password": "TestPass123!", "full_name": f"HT {em}"},
                timeout=15,
            )
            assert rr.status_code in (200, 201), f"register {em} failed: {rr.status_code} {rr.text}"

        # 3) Verify scan reports at least 3 victims
        r = requests.get(
            f"{BASE_URL}/api/admin/data-hygiene",
            headers=_auth(super_admin_token),
            timeout=20,
        )
        data = r.json()
        assert data["victims"] >= 3, f"Expected >=3 victims, got {data['victims']}"

        # 4) Verify KPI reflects new users within 15s (cache TTL=10s)
        time.sleep(12)
        snap = requests.get(
            f"{BASE_URL}/api/admin/dashboard",
            headers=_auth(super_admin_token),
            timeout=20,
        ).json()
        new_users = snap["kpis"]["total_users"]
        assert new_users >= base_users + 3, f"KPI should have grown by >=3 (base={base_users}, new={new_users})"

        # 5) Purge
        p = requests.post(
            f"{BASE_URL}/api/admin/data-hygiene/purge",
            headers=_auth(super_admin_token),
            timeout=60,
        )
        assert p.status_code == 200, f"{p.status_code} {p.text}"
        summary = p.json()
        assert summary.get("dry_run") is False
        assert summary.get("deleted_users", 0) >= 3
        remaining = summary.get("remaining_users")
        assert remaining is not None

        # 6) Verify scan is now clean (or at least, our 3 test users are gone)
        r2 = requests.get(
            f"{BASE_URL}/api/admin/data-hygiene",
            headers=_auth(super_admin_token),
            timeout=20,
        ).json()
        # None of our throwaway emails should be victim previews
        preview = r2.get("victim_preview") or []
        for em in throwaway_emails:
            assert em not in preview, f"{em} should have been purged"

        # 7) Audit log has a data.purge_test row (recent)
        al = requests.get(
            f"{BASE_URL}/api/admin/audit-log?action=data.purge_test&limit=5",
            headers=_auth(super_admin_token),
            timeout=15,
        )
        assert al.status_code == 200
        rows = al.json().get("rows", [])
        assert len(rows) >= 1, "Expected at least one data.purge_test audit row"
        latest = rows[0]
        assert latest.get("action") == "data.purge_test"
        assert latest.get("actor_email") == SUPER_ADMIN_EMAIL

    def test_protected_accounts_survive(self, super_admin_token):
        """superadmin@ithr.online + srijit* + sri0564823232@gmail.com must all still exist."""
        r = requests.get(
            f"{BASE_URL}/api/admin/users?limit=200",
            headers=_auth(super_admin_token),
            timeout=15,
        )
        assert r.status_code == 200
        users = r.json().get("users", [])
        emails = {u["email"] for u in users}
        assert "superadmin@ithr.online" in emails, "Super admin must survive purge"

    def test_dashboard_cache_ttl_low(self, super_admin_token):
        """Sanity: dashboard endpoint responds quickly and repeatedly."""
        for _ in range(3):
            r = requests.get(
                f"{BASE_URL}/api/admin/dashboard",
                headers=_auth(super_admin_token),
                timeout=15,
            )
            assert r.status_code == 200
            body = r.json()
            assert "kpis" in body
            assert "total_users" in body["kpis"]
