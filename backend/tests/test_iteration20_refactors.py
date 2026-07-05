"""Iter-20 non-regression tests — verifies pure-refactor changes don't alter observable behaviour.

Scope:
- admin_router: create_org_with_admin (now 3 helpers)
- enterprise_router: admin_create_user (validate helper), update_seats (3 helpers)
- recommendation_router: _score_courses now delegates to _learner_posture + _difficulty_score + _score_one_course helpers
- GET /api/recommendations + /api/recommendations/next-best still return the documented shape

Uses `.example.com` domains to sidestep the pre-existing `email_validator` `.test`-TLD rejection.
"""
import os
import secrets
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.tech")
SUPER_ADMIN_PW = os.environ.get("SUPER_ADMIN_PASSWORD", "preview-only-rotate-in-prod")


def _rand():
    return secrets.token_hex(4)


def _register(session, prefix="iter20"):
    email = f"{prefix}+{_rand()}@example.com"
    pw = "TestPass123!"
    r = session.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": pw, "full_name": "Iter20 Tester",
        "organization": "IterCorp", "title": "Analyst",
    })
    assert r.status_code == 200, r.text
    return email, pw, r.json()["token"], r.json()["user"]


def _super_admin_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PW,
    })
    if r.status_code != 200:
        pytest.skip(f"super-admin login failed: {r.status_code}")
    body = r.json()
    assert body["user"]["role"] == "super_admin"
    return body["token"]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s
    s.close()


# ---- Refactor 1: create_org_with_admin (3 helpers) --------------------------
class TestCreateOrgWithAdmin:
    def test_full_org_and_admin_provisioning(self, session):
        sa_token = _super_admin_token(session)
        suffix = _rand()
        domain = f"iter20-{suffix}.example.com"
        admin_email = f"cto+{suffix}@{domain}"
        payload = {
            "name": f"Iter20 Org {suffix}",
            "admin_email": admin_email,
            "admin_full_name": "Iter20 Admin",
            "industry": "Technology",
            "seat_count": 25,
        }
        r = session.post(f"{BASE_URL}/api/admin/orgs", json=payload,
                         headers={"Authorization": f"Bearer {sa_token}"})
        assert r.status_code == 200, r.text
        body = r.json()

        # organization block
        assert "organization" in body
        org = body["organization"]
        assert org["name"] == payload["name"]
        assert org["domain"] == domain  # derived from admin_email
        assert org["seat_count"] == 25
        assert org["seats_used"] == 1
        assert org["invite_code"] and isinstance(org["invite_code"], str)
        assert "id" in org and "slug" in org
        assert "_id" not in org

        # admin block with 14-char temp password
        admin = body["admin"]
        assert admin["email"] == admin_email.lower()
        assert admin["full_name"] == "Iter20 Admin"
        assert admin["must_reset_password"] is True
        assert isinstance(admin["temp_password"], str)
        assert len(admin["temp_password"]) == 14

        # persist for downstream tests in this module
        pytest.iter20_org_id = org["id"]
        pytest.iter20_org_domain = domain
        pytest.iter20_org_slug = org["slug"]
        pytest.iter20_admin_email = admin_email.lower()
        pytest.iter20_admin_pw = admin["temp_password"]

    def test_missing_name_returns_400(self, session):
        sa_token = _super_admin_token(session)
        r = session.post(f"{BASE_URL}/api/admin/orgs", json={
            "admin_email": f"x+{_rand()}@example.com",
            "admin_full_name": "X",
        }, headers={"Authorization": f"Bearer {sa_token}"})
        assert r.status_code == 400
        assert "name" in r.json()["detail"].lower()

    def test_invalid_admin_email_returns_400(self, session):
        sa_token = _super_admin_token(session)
        r = session.post(f"{BASE_URL}/api/admin/orgs", json={
            "name": "Bad Org",
            "admin_email": "not-an-email",
            "admin_full_name": "X",
        }, headers={"Authorization": f"Bearer {sa_token}"})
        assert r.status_code == 400
        assert "admin_email" in r.json()["detail"].lower()


# ---- Refactor 2: admin_create_user (validate helper) ------------------------
class TestEnterpriseAdminCreateUser:
    @staticmethod
    def _admin_token(session):
        # Depends on the org+admin created above; must reset password first? No —
        # first login is allowed even with must_reset_password=True (the flag
        # only informs the frontend to route to reset UI). Verify login works.
        email = getattr(pytest, "iter20_admin_email", None)
        pw = getattr(pytest, "iter20_admin_pw", None)
        if not email or not pw:
            pytest.skip("org+admin not provisioned by prior test")
        r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    def test_matching_domain_creates_user(self, session):
        token = self._admin_token(session)
        domain = pytest.iter20_org_domain
        new_email = f"emp+{_rand()}@{domain}"
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/users", json={
            "email": new_email, "full_name": "Emp One", "department": "Eng", "role": "member",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["email"] == new_email.lower()
        assert body["user"]["role"] == "member"
        assert len(body["temp_password"]) == 14
        assert body["must_reset_password"] is True

    def test_mismatched_domain_rejected(self, session):
        token = self._admin_token(session)
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/users", json={
            "email": f"foreign+{_rand()}@other.example.com",
            "full_name": "Foreign", "department": "Eng", "role": "member",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "Email domain must be @" in detail
        assert pytest.iter20_org_domain in detail

    def test_missing_full_name_rejected(self, session):
        token = self._admin_token(session)
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/users", json={
            "email": f"x+{_rand()}@{pytest.iter20_org_domain}",
            "full_name": "", "role": "member",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "full_name" in r.json()["detail"].lower()


# ---- Refactor 3: update_seats (validate + decrease + increase helpers) ------
class TestSeatChangeRefactor:
    def _admin_token(self, session):
        email = getattr(pytest, "iter20_admin_email", None)
        pw = getattr(pytest, "iter20_admin_pw", None)
        if not email or not pw:
            pytest.skip("org+admin not provisioned")
        r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200
        return r.json()["token"]

    def test_noop_returns_no_change_message(self, session):
        token = self._admin_token(session)
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/seats", json={
            "seat_count": 25,  # matches provisioned value
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] == "noop"
        assert body["message"] == "No change."

    def test_below_min_seat_rejected(self, session):
        token = self._admin_token(session)
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/seats", json={
            "seat_count": 5,  # under 10 minimum
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "10 seats" in r.json()["detail"]

    def test_over_max_rejected(self, session):
        token = self._admin_token(session)
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/seats", json={
            "seat_count": 5001,
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "5000" in r.json()["detail"]

    def test_decrease_returns_credit_note(self, session):
        token = self._admin_token(session)
        # We provisioned with 25 seats and 1 seat used. Decrease to 20.
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/seats", json={
            "seat_count": 20,
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] == "credit"
        assert "credit_note" in body
        cn = body["credit_note"]
        assert cn["seats_removed"] == 5
        assert cn["type"] == "prorated_credit"
        assert cn["amount"] == round(5 * 18.00, 2)
        assert body["organization"]["seat_count"] == 20

    def test_increase_returns_checkout_or_502_accepted(self, session):
        token = self._admin_token(session)
        # Attempt increase; Stripe key may be missing in preview → 502 is acceptable.
        r = session.post(f"{BASE_URL}/api/enterprise/organizations/seats", json={
            "seat_count": 30, "origin_url": BASE_URL,
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (200, 502), r.text
        if r.status_code == 200:
            body = r.json()
            assert body["action"] == "checkout"
            assert "checkout_url" in body
            assert body["seats_delta"] > 0


# ---- Refactor 4: recommendations _score_courses split -----------------------
class TestRecommendationsShape:
    def test_recommendations_returns_expected_shape(self, session):
        _, _, token, _ = _register(session, prefix="iter20.rec")
        r = session.get(f"{BASE_URL}/api/recommendations",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "generated_at" in body
        assert "count" in body
        assert "recommendations" in body
        assert isinstance(body["recommendations"], list)
        assert body["count"] == len(body["recommendations"])
        if body["recommendations"]:
            first = body["recommendations"][0]
            assert "course" in first
            assert "score" in first
            assert "signals" in first
            # signals shape from _score_one_course helper
            sig = first["signals"]
            for k in ("industry_overlap", "category_overlap", "has_full_content", "freshness"):
                assert k in sig
            # course is thinned
            course = first["course"]
            for k in ("id", "slug", "title", "category", "difficulty"):
                assert k in course
            assert "modules" not in course  # thin — no modules
            assert "quiz" not in course

    def test_next_best_returns_recommendation_with_rationale(self, session):
        _, _, token, _ = _register(session, prefix="iter20.nb")
        r = session.get(f"{BASE_URL}/api/recommendations/next-best",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "recommendation" in body
        rec = body["recommendation"]
        if rec is None:
            pytest.skip("no courses seeded — recommendation empty")
        assert "course" in rec
        assert "score" in rec
        assert "signals" in rec
        assert "rationale" in rec
        assert isinstance(rec["rationale"], str)
        assert len(rec["rationale"]) > 0  # falls back to canned line if LLM unavailable

    def test_recommendations_requires_auth(self, session):
        r = session.get(f"{BASE_URL}/api/recommendations")
        assert r.status_code in (401, 403)
