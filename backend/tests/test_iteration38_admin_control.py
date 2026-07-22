"""Iteration 38 backend tests: Tier-1 super-admin control endpoints.

Covers: suspend/reactivate, delete (cascade), role change, impersonation,
audit log listing + CSV export, and the login/refresh suspension guard.
"""
import os
import time
import uuid
import base64
import json

import jwt
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://enterprise-agent-dev.preview.emergentagent.com").rstrip("/")

SUPER_ADMIN_EMAIL = "superadmin@ithr.online"
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def super_admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD,
    })
    assert r.status_code == 200, f"super admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def super_admin_id(super_admin_token):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture
def learner_account():
    """Register a fresh learner via public register endpoint. Returns dict with id/email/password/token."""
    email = f"test_i38_{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPass123!"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Iter38 Test Learner",
        "organization": "TestOrg",
        "title": "Analyst",
    })
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    body = r.json()
    return {
        "id": body["user"]["id"],
        "email": email,
        "password": password,
        "token": body["token"],
    }


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- SUSPEND / REACTIVATE ----------
class TestSuspendReactivate:
    def test_suspend_and_idempotency(self, super_admin_token, learner_account):
        # first suspend
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/suspend",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["is_suspended"] is True
        assert body["user_id"] == learner_account["id"]

        # idempotent — repeating stays 200
        r2 = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/suspend",
            headers=_auth(super_admin_token),
        )
        assert r2.status_code == 200
        assert r2.json()["is_suspended"] is True

        # verify via /api/admin/users listing (GET after mutate)
        r3 = requests.get(
            f"{BASE_URL}/api/admin/users?q={learner_account['email']}",
            headers=_auth(super_admin_token),
        )
        assert r3.status_code == 200
        users = r3.json()["users"]
        assert len(users) >= 1
        u = next(x for x in users if x["id"] == learner_account["id"])
        assert u.get("is_suspended") is True

    def test_suspended_user_cannot_login(self, super_admin_token, learner_account):
        # suspend first
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/suspend",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200
        # try login
        r2 = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": learner_account["email"],
            "password": learner_account["password"],
        })
        assert r2.status_code == 403
        detail = r2.json().get("detail", "").lower()
        assert "suspend" in detail, f"expected 'suspend' in detail; got {detail!r}"

    def test_reactivate(self, super_admin_token, learner_account):
        # suspend then reactivate
        requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/suspend",
            headers=_auth(super_admin_token),
        )
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/reactivate",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200
        assert r.json()["is_suspended"] is False

        # verify login now works
        r2 = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": learner_account["email"],
            "password": learner_account["password"],
        })
        assert r2.status_code == 200

    def test_suspend_self_400(self, super_admin_token, super_admin_id):
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{super_admin_id}/suspend",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert "own" in detail or "yourself" in detail or "self" in detail


# ---------- ROLE CHANGE ----------
class TestRoleChange:
    def test_role_change_success(self, super_admin_token, learner_account):
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/role",
            headers=_auth(super_admin_token),
            json={"role": "instructor"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "instructor"
        assert body["previous"] == "learner"

        # GET verify
        r2 = requests.get(
            f"{BASE_URL}/api/admin/users?q={learner_account['email']}",
            headers=_auth(super_admin_token),
        )
        u = next(x for x in r2.json()["users"] if x["id"] == learner_account["id"])
        assert u["role"] == "instructor"

    def test_role_invalid_400(self, super_admin_token, learner_account):
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/role",
            headers=_auth(super_admin_token),
            json={"role": "godmode"},
        )
        assert r.status_code == 400
        assert "invalid role" in r.json().get("detail", "").lower()

    def test_role_change_self_400(self, super_admin_token, super_admin_id):
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{super_admin_id}/role",
            headers=_auth(super_admin_token),
            json={"role": "admin"},
        )
        assert r.status_code == 400


# ---------- DELETE ----------
class TestDeleteUser:
    def test_delete_learner_and_cascade_counts(self, super_admin_token, learner_account):
        r = requests.delete(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["deleted"] == 1
        assert "cascade" in body
        # cascade dict has expected keys
        expected_keys = {
            "enrollments", "certificates", "org_members", "quiz_attempts",
            "assessment_attempts", "mentor_sessions", "payment_transactions",
            "password_reset_tokens", "user_login_logs", "tutor_sessions",
        }
        assert expected_keys.issubset(body["cascade"].keys())

        # GET verify — user gone
        r2 = requests.get(
            f"{BASE_URL}/api/admin/users?q={learner_account['email']}",
            headers=_auth(super_admin_token),
        )
        users = r2.json()["users"]
        assert not any(u["id"] == learner_account["id"] for u in users)

    def test_delete_self_400(self, super_admin_token, super_admin_id):
        r = requests.delete(
            f"{BASE_URL}/api/admin/users/{super_admin_id}",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 400


# ---------- IMPERSONATION ----------
class TestImpersonation:
    def test_impersonate_non_super_admin(self, super_admin_token, super_admin_id, learner_account):
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/impersonate",
            headers=_auth(super_admin_token),
            json={"reason": "iter38 test"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["expires_in"] == 900
        assert "token" in body
        assert body["user"]["id"] == learner_account["id"]
        assert body["user"]["email"] == learner_account["email"]

        # decode token — must have imp_of=<admin_id>
        # We decode WITHOUT verification since we don't have JWT_SECRET in the test.
        decoded = jwt.decode(body["token"], options={"verify_signature": False})
        assert decoded["imp_of"] == super_admin_id
        assert decoded["sub"] == learner_account["id"]
        assert decoded["role"] == learner_account.get("role", "learner") or decoded["role"] in {"learner"}

        # Verify the impersonation token actually authenticates as the target
        r2 = requests.get(f"{BASE_URL}/api/auth/me", headers=_auth(body["token"]))
        assert r2.status_code == 200
        assert r2.json()["id"] == learner_account["id"]

    def test_impersonate_super_admin_403(self, super_admin_token, super_admin_id):
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{super_admin_id}/impersonate",
            headers=_auth(super_admin_token),
            json={"reason": "should fail — self"},
        )
        # Self-check is 400 (checked earlier), but spec says impersonating another super_admin returns 403.
        # There's only one super_admin in the DB, so we cannot easily test the 403 branch without creating another.
        # Instead, promote the learner momentarily and try.
        assert r.status_code == 400  # self

    def test_impersonate_another_super_admin_403(self, super_admin_token, learner_account):
        # Promote learner to super_admin, try impersonate, expect 403, then demote/delete
        r_promote = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/role",
            headers=_auth(super_admin_token),
            json={"role": "super_admin"},
        )
        assert r_promote.status_code == 200

        try:
            r = requests.post(
                f"{BASE_URL}/api/admin/users/{learner_account['id']}/impersonate",
                headers=_auth(super_admin_token),
                json={"reason": "should be blocked"},
            )
            assert r.status_code == 403
            assert "super" in r.json()["detail"].lower()
        finally:
            # cleanup — demote first (guard: last super admin), then delete
            requests.post(
                f"{BASE_URL}/api/admin/users/{learner_account['id']}/role",
                headers=_auth(super_admin_token),
                json={"role": "learner"},
            )
            requests.delete(
                f"{BASE_URL}/api/admin/users/{learner_account['id']}",
                headers=_auth(super_admin_token),
            )

    def test_impersonate_suspended_user_400(self, super_admin_token, learner_account):
        # suspend
        requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/suspend",
            headers=_auth(super_admin_token),
        )
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/impersonate",
            headers=_auth(super_admin_token),
            json={"reason": "should be blocked"},
        )
        assert r.status_code == 400
        assert "suspend" in r.json()["detail"].lower()


# ---------- AUDIT LOG ----------
class TestAuditLog:
    def test_audit_log_lists_recent_actions(self, super_admin_token, super_admin_id, learner_account):
        # Trigger a well-defined action so we can look for it
        requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/suspend",
            headers=_auth(super_admin_token),
        )
        # small delay to let the fire-and-forget log write
        time.sleep(0.5)

        r = requests.get(
            f"{BASE_URL}/api/admin/audit-log?limit=200",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "rows" in data and "total" in data
        assert isinstance(data["rows"], list)
        assert data["total"] >= 1

        # find our specific suspend action
        match = next(
            (r for r in data["rows"] if r.get("action") == "user.suspend" and r.get("target_id") == learner_account["id"]),
            None,
        )
        assert match is not None, "no user.suspend audit row for this test learner"
        assert match["actor_email"] == SUPER_ADMIN_EMAIL
        assert match["actor_id"] == super_admin_id
        assert match["target_label"] == learner_account["email"]

    def test_audit_log_action_filter(self, super_admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/audit-log?action=user.suspend&limit=50",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200
        rows = r.json()["rows"]
        assert all(row["action"] == "user.suspend" for row in rows)

    def test_audit_log_csv_export(self, super_admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/audit-log/export.csv",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        text = r.text
        first_line = text.split("\n", 1)[0].strip()
        # header row check
        assert "created_at" in first_line
        assert "actor_email" in first_line
        assert "action" in first_line
        assert "target_label" in first_line


# ---------- AUTH & FILTER GUARDS ----------
class TestGuardsAndFilters:
    def test_learner_jwt_cannot_hit_admin_endpoints(self, learner_account):
        # Try a couple of admin endpoints with a learner token — all must 403.
        endpoints = [
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/audit-log"),
            ("POST", f"/api/admin/users/{learner_account['id']}/suspend"),
        ]
        for method, path in endpoints:
            r = requests.request(
                method, f"{BASE_URL}{path}",
                headers=_auth(learner_account["token"]),
                json={},
            )
            assert r.status_code == 403, f"{method} {path} returned {r.status_code}: {r.text}"

    def test_users_filters(self, super_admin_token, learner_account):
        # partial email match
        partial = learner_account["email"].split("@")[0][:12]
        r = requests.get(
            f"{BASE_URL}/api/admin/users?q={partial}",
            headers=_auth(super_admin_token),
        )
        assert r.status_code == 200
        matches = [u for u in r.json()["users"] if u["id"] == learner_account["id"]]
        assert len(matches) == 1

        # role filter
        r2 = requests.get(
            f"{BASE_URL}/api/admin/users?role=learner&limit=200",
            headers=_auth(super_admin_token),
        )
        assert r2.status_code == 200
        assert all(u["role"] == "learner" for u in r2.json()["users"])

        # suspended=true filter
        requests.post(
            f"{BASE_URL}/api/admin/users/{learner_account['id']}/suspend",
            headers=_auth(super_admin_token),
        )
        r3 = requests.get(
            f"{BASE_URL}/api/admin/users?suspended=true&limit=200",
            headers=_auth(super_admin_token),
        )
        assert r3.status_code == 200
        suspended_users = r3.json()["users"]
        assert all(u.get("is_suspended") is True for u in suspended_users)
        assert any(u["id"] == learner_account["id"] for u in suspended_users)

        # suspended=false filter — our learner should NOT be in this list
        r4 = requests.get(
            f"{BASE_URL}/api/admin/users?suspended=false&limit=500",
            headers=_auth(super_admin_token),
        )
        assert r4.status_code == 200
        assert not any(u["id"] == learner_account["id"] for u in r4.json()["users"])


# ---------- CLEANUP (module-level teardown) ----------
def test_zzz_cleanup_stray_test_learners(super_admin_token):
    """Best-effort cleanup — delete any TEST_i38 learners left over from this run."""
    r = requests.get(
        f"{BASE_URL}/api/admin/users?q=test_i38&limit=500",
        headers=_auth(super_admin_token),
    )
    assert r.status_code == 200
    for u in r.json().get("users", []):
        if u.get("role") == "super_admin":
            continue
        requests.delete(
            f"{BASE_URL}/api/admin/users/{u['id']}",
            headers=_auth(super_admin_token),
        )
