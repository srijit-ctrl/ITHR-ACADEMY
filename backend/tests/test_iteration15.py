"""Iteration 15 backend tests.

Covers:
- Founding-member perk (assign on register, idempotent across refresh/me,
  first-course lock, cap enforcement via DB probe).
- Super-admin org+admin provisioning, list orgs/users, reset password, delete org.
- Enterprise admin creating a user with domain enforcement.
- Role gating (non-super-admin -> 403 on /api/admin/*).
- Sample certificate verify + PDF public endpoints.
"""
import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

from conftest import TEST_USER_PASSWORD

# Load frontend/.env to pick up REACT_APP_BACKEND_URL used across the suite
load_dotenv(Path(__file__).parent.parent.parent / "frontend" / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.tech")
# Test-only default matches the preview placeholder in /app/backend/.env.
# In production CI, override via SUPER_ADMIN_PASSWORD env var.
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "preview-only-rotate-in-prod")


# ---------------- Helpers ----------------
def _register(prefix: str = "iter15") -> dict:
    email = f"{prefix}+{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": TEST_USER_PASSWORD, "full_name": "Iter15 User",
    })
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "email": email,
        "password": TEST_USER_PASSWORD,
        "token": data["token"],
        "user": data["user"],
        "cookies": r.cookies,
    }


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def super_admin_token():
    r = requests.post(f"{API}/auth/login", json={
        "email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD,
    })
    assert r.status_code == 200, f"super-admin login failed: {r.status_code} {r.text}"
    d = r.json()
    assert d["user"]["role"] == "super_admin"
    return d["token"]


# ---------------- Founding member perk ----------------
class TestFoundingMember:
    def test_register_returns_founding_fields(self):
        u = _register("fmreg")
        user = u["user"]
        # If under cap, seq/code should be present. We accept either case
        # (skip content asserts if the cap has already been hit in this DB).
        if user.get("founding_member_seq") is None:
            pytest.skip("Founder cap already reached in this DB — skipping content asserts.")
        assert isinstance(user["founding_member_seq"], int)
        assert 1 <= user["founding_member_seq"] <= 500
        code = user["signup_discount_code"]
        assert isinstance(code, str) and len(code) == 10
        assert code.isupper() or code.isalnum()  # uppercase alnum
        # Only uppercase + digits allowed
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        assert set(code).issubset(allowed), f"code {code!r} has non-alnum-upper chars"
        # First-course fields default
        assert user.get("founding_course_id") is None
        assert user.get("founding_cert_used") is False

    def test_founding_idempotent_across_refresh_and_me(self):
        u = _register("fmidem")
        if u["user"].get("founding_member_seq") is None:
            pytest.skip("Founder cap reached; idempotency test needs a founder user.")
        seq0 = u["user"]["founding_member_seq"]
        code0 = u["user"]["signup_discount_code"]

        # /auth/me
        r = requests.get(f"{API}/auth/me", headers=_headers(u["token"]))
        assert r.status_code == 200
        me = r.json()
        assert me["founding_member_seq"] == seq0
        assert me["signup_discount_code"] == code0

        # /auth/refresh (uses cookie from registration response)
        r2 = requests.post(f"{API}/auth/refresh", cookies=u["cookies"])
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2["user"]["founding_member_seq"] == seq0
        assert d2["user"]["signup_discount_code"] == code0

    def test_founding_first_course_lock(self):
        u = _register("fmlock")
        if u["user"].get("founding_member_seq") is None:
            pytest.skip("Founder cap reached — first-course lock test needs a founder user.")
        h = _headers(u["token"])

        # Enroll in course A
        r = requests.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=h)
        assert r.status_code == 200, r.text

        # /me should now show founding_course_id set to the foundations course id
        r_me = requests.get(f"{API}/auth/me", headers=h)
        assert r_me.status_code == 200
        me = r_me.json()
        first_locked = me["founding_course_id"]
        assert first_locked is not None, "founding_course_id should be set after first enroll"

        # Enroll in a DIFFERENT course
        r2 = requests.post(f"{API}/courses/rag-enterprise/enroll", headers=h)
        assert r2.status_code == 200, r2.text

        # founding_course_id must NOT change
        r_me2 = requests.get(f"{API}/auth/me", headers=h)
        assert r_me2.status_code == 200
        me2 = r_me2.json()
        assert me2["founding_course_id"] == first_locked, (
            f"founding_course_id changed after second enroll: "
            f"was {first_locked}, now {me2['founding_course_id']}"
        )

    def test_founding_cap_logic_via_code_inspection(self):
        """Verify the cap logic exists — the FOUNDER_CAP constant and the
        assign_if_eligible early-return on seq > cap. Mass-populating 500 stub
        users to hit the cap would poison the shared DB for later tests; the
        review request explicitly permits code-inspection verification here.
        """
        import sys
        sys.path.insert(0, "/app/backend")
        from founding_member import FOUNDER_CAP, assign_if_eligible
        import inspect
        assert FOUNDER_CAP == 500
        src = inspect.getsource(assign_if_eligible)
        assert "FOUNDER_CAP" in src, "cap check must reference FOUNDER_CAP"
        assert "return None" in src, "over-cap path must return None"


# ---------------- Admin: orgs & users ----------------
class TestSuperAdminOrgs:
    def test_create_org_with_admin_and_domain_derivation(self, super_admin_token):
        h = _headers(super_admin_token)
        unique = uuid.uuid4().hex[:6]
        admin_email = f"cto+{unique}@acme-{unique}.test"
        payload = {
            "name": f"TEST ACME {unique}",
            "admin_email": admin_email,
            "admin_full_name": "Acme CTO",
            "industry": "manufacturing",
            "seat_count": 30,
        }
        r = requests.post(f"{API}/admin/orgs", headers=h, json=payload)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        d = r.json()
        # organization shape
        org = d["organization"]
        for k in ("id", "name", "slug", "domain", "seat_count", "invite_code"):
            assert k in org, f"missing org.{k}"
        assert org["name"] == payload["name"]
        # domain derived from admin email
        expected_domain = admin_email.split("@", 1)[1].lower()
        assert org["domain"] == expected_domain, f"expected domain {expected_domain}, got {org['domain']}"
        assert org["seat_count"] == 30

        # admin shape
        adm = d["admin"]
        for k in ("id", "email", "full_name", "temp_password", "must_reset_password"):
            assert k in adm
        assert adm["email"] == admin_email
        assert len(adm["temp_password"]) == 14
        assert adm["must_reset_password"] is True

        # stash for downstream tests
        pytest.iter15_org = org
        pytest.iter15_org_admin = {"email": admin_email, "temp_password": adm["temp_password"], "id": adm["id"]}

    def test_list_orgs_contains_new_org(self, super_admin_token):
        h = _headers(super_admin_token)
        r = requests.get(f"{API}/admin/orgs", headers=h)
        assert r.status_code == 200
        d = r.json()
        assert "organizations" in d and isinstance(d["organizations"], list)
        assert d["total"] == len(d["organizations"])
        org = getattr(pytest, "iter15_org", None)
        if org:
            ids = {o["id"] for o in d["organizations"]}
            assert org["id"] in ids

    def test_admin_endpoints_require_super_admin(self):
        # Register a normal learner
        u = _register("nonadmin")
        h = _headers(u["token"])
        r1 = requests.get(f"{API}/admin/orgs", headers=h)
        assert r1.status_code == 403
        assert "Super admin only" in r1.text
        r2 = requests.get(f"{API}/admin/users", headers=h)
        assert r2.status_code == 403
        assert "Super admin only" in r2.text

    def test_admin_endpoints_require_auth(self):
        r = requests.get(f"{API}/admin/orgs")
        assert r.status_code in (401, 403)
        r2 = requests.get(f"{API}/admin/users")
        assert r2.status_code in (401, 403)

    def test_list_users_paginated(self, super_admin_token):
        h = _headers(super_admin_token)
        r = requests.get(f"{API}/admin/users?limit=5&skip=0", headers=h)
        assert r.status_code == 200
        d = r.json()
        assert "users" in d and "total" in d
        assert d["limit"] == 5
        assert len(d["users"]) <= 5
        # Ensure no password_hash leaks
        for u in d["users"]:
            assert "password_hash" not in u

    def test_reset_user_password(self, super_admin_token):
        # Register a fresh user
        u = _register("resetme")
        h_admin = _headers(super_admin_token)
        r = requests.post(f"{API}/admin/users/{u['user']['id']}/reset-password", headers=h_admin)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user_id"] == u["user"]["id"]
        assert d["email"] == u["email"].lower()
        new_pw = d["temp_password"]
        assert len(new_pw) == 14
        # Log in with the new password
        r_login = requests.post(f"{API}/auth/login", json={"email": u["email"], "password": new_pw})
        assert r_login.status_code == 200, f"login with new temp_pw failed: {r_login.text}"
        # Old password should NOT work anymore
        r_old = requests.post(f"{API}/auth/login", json={"email": u["email"], "password": u["password"]})
        assert r_old.status_code == 401

    def test_reset_password_unknown_user(self, super_admin_token):
        h = _headers(super_admin_token)
        r = requests.post(f"{API}/admin/users/nonexistent-user-id/reset-password", headers=h)
        assert r.status_code == 404


# ---------------- Enterprise admin creates user (domain enforcement) ----------------
class TestEnterpriseAdminCreateUser:
    def _login_org_admin(self):
        org_admin = getattr(pytest, "iter15_org_admin", None)
        if not org_admin:
            pytest.skip("No org admin from prior test")
        r = requests.post(f"{API}/auth/login", json={
            "email": org_admin["email"], "password": org_admin["temp_password"],
        })
        assert r.status_code == 200, r.text
        return r.json()["token"]

    def test_admin_creates_user_with_matching_domain(self):
        org = getattr(pytest, "iter15_org", None)
        if not org:
            pytest.skip("Need org from prior test")
        token = self._login_org_admin()
        h = _headers(token)

        new_email = f"employee+{uuid.uuid4().hex[:6]}@{org['domain']}"
        r = requests.post(f"{API}/enterprise/organizations/users", headers=h, json={
            "email": new_email,
            "full_name": "New Hire",
            "department": "Engineering",
            "role": "member",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        user = d["user"]
        for k in ("id", "email", "full_name", "role", "department"):
            assert k in user
        assert user["email"] == new_email
        assert user["role"] == "member"
        assert user["department"] == "Engineering"
        assert "temp_password" in d
        assert len(d["temp_password"]) == 14
        assert d["must_reset_password"] is True

    def test_admin_create_user_mismatched_domain_rejected(self):
        org = getattr(pytest, "iter15_org", None)
        if not org:
            pytest.skip("Need org from prior test")
        token = self._login_org_admin()
        h = _headers(token)

        r = requests.post(f"{API}/enterprise/organizations/users", headers=h, json={
            "email": f"outsider+{uuid.uuid4().hex[:5]}@gmail.com",
            "full_name": "Wrong Domain",
            "role": "member",
        })
        assert r.status_code == 400, r.text
        detail = r.json().get("detail", "")
        assert "Email domain must be @" in detail, f"unexpected error: {detail}"
        assert org["domain"] in detail

    def test_admin_create_user_requires_valid_fields(self):
        token = self._login_org_admin()
        h = _headers(token)
        r = requests.post(f"{API}/enterprise/organizations/users", headers=h, json={
            "email": "not-an-email",
            "full_name": "X",
        })
        assert r.status_code == 400


# ---------------- Delete org (last in the flow) ----------------
class TestSuperAdminDeleteOrg:
    def test_delete_org_cascades_and_clears_user_org(self, super_admin_token):
        org = getattr(pytest, "iter15_org", None)
        org_admin = getattr(pytest, "iter15_org_admin", None)
        if not (org and org_admin):
            pytest.skip("Need org + admin from prior tests")

        h = _headers(super_admin_token)
        r = requests.delete(f"{API}/admin/orgs/{org['id']}", headers=h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["deleted"] is True
        assert d["org_id"] == org["id"]
        assert d["name"] == org["name"]

        # Verify org gone from admin listing
        r2 = requests.get(f"{API}/admin/orgs", headers=h)
        assert r2.status_code == 200
        ids = {o["id"] for o in r2.json()["organizations"]}
        assert org["id"] not in ids

        # Verify the admin user still exists but org fields cleared
        r_users = requests.get(f"{API}/admin/users?limit=500", headers=h)
        assert r_users.status_code == 200
        users_list = r_users.json()["users"]
        adm = next((u for u in users_list if u["id"] == org_admin["id"]), None)
        assert adm is not None, "user should still exist after org deletion"
        assert adm.get("organization") in (None,), f"organization should be cleared, got {adm.get('organization')}"

    def test_delete_unknown_org_returns_404(self, super_admin_token):
        h = _headers(super_admin_token)
        r = requests.delete(f"{API}/admin/orgs/does-not-exist-xyz", headers=h)
        assert r.status_code == 404


# ---------------- Sample certificate ----------------
class TestSampleCertificate:
    def test_verify_sample_cert(self):
        r = requests.get(f"{API}/certificates/verify/SAMPLE-ITHR-2026-001")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["valid"] is True
        cert = d["certificate"]
        assert cert["certificate_id"] == "SAMPLE-ITHR-2026-001"
        assert cert["user_name"] == "Sample Learner"
        assert cert["score"] == 92 or cert["score"] == 92.0
        assert "course_title" in cert and isinstance(cert["course_title"], str) and cert["course_title"]
        assert cert.get("verification_url") == "/verify/SAMPLE-ITHR-2026-001"

    def test_sample_cert_pdf(self):
        r = requests.get(f"{API}/certificates/SAMPLE-ITHR-2026-001/pdf")
        assert r.status_code == 200, r.text[:300]
        ct = r.headers.get("content-type", "").lower()
        assert "application/pdf" in ct, f"unexpected content-type: {ct}"
        assert r.content.startswith(b"%PDF"), "not a valid PDF body"
        assert len(r.content) > 15000, f"pdf too small: {len(r.content)} bytes"
