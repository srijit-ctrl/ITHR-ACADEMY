"""Iter 49 — Super Admin Command Centre + Alerts + Org/User 360 endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://enterprise-agent-dev.preview.emergentagent.com").rstrip("/")

SUPER_EMAIL = "superadmin@ithr.online"
SUPER_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")
LEARNER_EMAIL = "refe_1784091849@test.com"
LEARNER_PASSWORD = "Passw0rd!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j.get("access_token") or j["token"]


@pytest.fixture(scope="module")
def sa_token():
    return _login(SUPER_EMAIL, SUPER_PASSWORD)


@pytest.fixture(scope="module")
def learner_token():
    return _login(LEARNER_EMAIL, LEARNER_PASSWORD)


@pytest.fixture(scope="module")
def sa_headers(sa_token):
    return {"Authorization": f"Bearer {sa_token}"}


@pytest.fixture(scope="module")
def learner_headers(learner_token):
    return {"Authorization": f"Bearer {learner_token}"}


# ---------- Command Center ----------

class TestCommandCenter:
    def test_command_center_default(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/command-center", headers=sa_headers, timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert data["days"] == 30
        assert "generated_at" in data
        assert isinstance(data["kpis"], list)
        assert len(data["kpis"]) == 22, f"Expected 22 KPIs, got {len(data['kpis'])}"
        for k in data["kpis"]:
            assert "key" in k
            assert "label" in k
            assert "value" in k
            assert "format" in k
            assert "definition" in k

    def test_command_center_7days(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/command-center?days=7", headers=sa_headers, timeout=60)
        assert r.status_code == 200
        assert r.json()["days"] == 7

    def test_command_center_90days(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/command-center?days=90", headers=sa_headers, timeout=60)
        assert r.status_code == 200
        assert r.json()["days"] == 90

    def test_command_center_has_expected_kpi_keys(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/command-center?days=30", headers=sa_headers, timeout=60)
        keys = {k["key"] for k in r.json()["kpis"]}
        expected = {"total_users", "new_users", "dau", "mau", "total_orgs", "seats_purchased",
                    "revenue", "referral_signups", "ai_sessions", "certificates_issued", "mfa_users"}
        assert expected.issubset(keys), f"Missing keys: {expected - keys}"

    def test_command_center_delta_pct_present_on_period_kpis(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/command-center?days=30", headers=sa_headers, timeout=60)
        kpis = {k["key"]: k for k in r.json()["kpis"]}
        # new_users has prev_value + delta_pct
        assert "prev_value" in kpis["new_users"]
        assert "delta_pct" in kpis["new_users"]

    def test_command_center_forbidden_for_learner(self, learner_headers):
        r = requests.get(f"{BASE_URL}/api/admin/command-center", headers=learner_headers, timeout=30)
        assert r.status_code == 403


# ---------- Alerts Center ----------

class TestAlertsCenter:
    def test_alerts_center_returns_alerts(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/alerts-center", headers=sa_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "alerts" in data
        assert "generated_at" in data
        # Should have at least one alert per problem statement (low seat utilization)
        assert len(data["alerts"]) >= 1
        for a in data["alerts"]:
            assert "key" in a
            assert "severity" in a
            assert "title" in a
            assert "detail" in a
            assert a["severity"] in ("high", "medium", "low")

    def test_alerts_sorted_by_severity(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/alerts-center", headers=sa_headers, timeout=30)
        alerts = r.json()["alerts"]
        order = {"high": 0, "medium": 1, "low": 2}
        sev_list = [order[a["severity"]] for a in alerts]
        assert sev_list == sorted(sev_list)

    def test_alert_ack_persists(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/alerts-center", headers=sa_headers, timeout=30)
        alerts = r.json()["alerts"]
        if not alerts:
            pytest.skip("no alerts available")
        key = alerts[0]["key"]
        # ack
        r_ack = requests.post(f"{BASE_URL}/api/admin/alerts-center/{key}/ack", headers=sa_headers, timeout=30)
        assert r_ack.status_code == 200
        assert r_ack.json()["ok"] is True
        # Verify via GET
        r2 = requests.get(f"{BASE_URL}/api/admin/alerts-center", headers=sa_headers, timeout=30)
        found = next((a for a in r2.json()["alerts"] if a["key"] == key), None)
        assert found is not None
        assert found["status"] == "acknowledged"


# ---------- Org 360 ----------

class TestOrg360:
    def test_org360_valid(self, sa_headers):
        # Get an org first
        r = requests.get(f"{BASE_URL}/api/admin/orgs", headers=sa_headers, timeout=30)
        orgs = r.json().get("organizations", [])
        if not orgs:
            pytest.skip("no organizations")
        org_id = orgs[0]["id"]
        r2 = requests.get(f"{BASE_URL}/api/admin/org360/{org_id}", headers=sa_headers, timeout=30)
        assert r2.status_code == 200
        data = r2.json()
        assert "organization" in data
        assert "members" in data
        assert "member_count" in data
        assert "stats" in data
        stats = data["stats"]
        for k in ["enrollments", "completions", "avg_progress", "certificates", "ai_sessions"]:
            assert k in stats

    def test_org360_not_found(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/org360/does-not-exist-xyz", headers=sa_headers, timeout=30)
        assert r.status_code == 404


# ---------- User 360 ----------

class TestUser360:
    def test_user360_valid(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/users?limit=5", headers=sa_headers, timeout=30)
        users = r.json().get("users", [])
        assert len(users) > 0
        uid = users[0]["id"]
        r2 = requests.get(f"{BASE_URL}/api/admin/user360/{uid}", headers=sa_headers, timeout=30)
        assert r2.status_code == 200
        data = r2.json()
        u = data["user"]
        assert "password_hash" not in u
        assert "mfa_secret" not in u
        assert "enrollments" in data
        assert "certificates" in data
        assert "assessment_attempts" in data
        assert "ai_sessions" in data
        assert "recent_logins" in data
        assert "referrals_made" in data
        assert "audit_trail" in data
        # recent_logins must NOT have ip field
        for l in data["recent_logins"]:
            assert "ip" not in l
        # enrollments have course_title
        for e in data["enrollments"]:
            assert "course_title" in e

    def test_user360_not_found(self, sa_headers):
        r = requests.get(f"{BASE_URL}/api/admin/user360/does-not-exist-xyz", headers=sa_headers, timeout=30)
        assert r.status_code == 404
