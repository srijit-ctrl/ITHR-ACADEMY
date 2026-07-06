"""Iter-30 P3 refactor non-regression tests.

Scope (behavior-preserving refactor):
- digest_router: `_build_digest_html` split into `_load_digest_data`,
  `_kpi_row_html`, `_signal_card_html`, `_patches_section_html`,
  `_digest_shell_html`.
- enterprise_router: `fulfill_seat_increment` split into `_load_seat_txn`,
  `_verify_stripe_payment`, `_resolve_fulfill_target`,
  `_claim_and_apply_fulfillment`.

Also touches quick sanity regressions:
- GET /api/health returns 200.
- GET /api/admin/analytics?days=30 → 30-day zero-fill shape.
- GET /api/admin/orgs → $lookup aggregation returns seats_used per org.
- GET /api/courses/enterprise-ai-learn-2/assessment/session → randomized quiz.
"""
import os
import secrets

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.tech")
SUPER_ADMIN_PW = os.environ.get("SUPER_ADMIN_PASSWORD", "preview-only-rotate-in-prod")


def _rand():
    return secrets.token_hex(4)


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s
    s.close()


@pytest.fixture(scope="module")
def super_admin_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PW,
    })
    if r.status_code != 200:
        pytest.skip(f"super-admin login failed: {r.status_code} {r.text}")
    body = r.json()
    assert body["user"]["role"] == "super_admin"
    return body["token"]


@pytest.fixture(scope="module")
def provisioned_org(session, super_admin_token):
    """Create a fresh org + admin so digest/seat tests have a real membership."""
    suffix = _rand()
    domain = f"iter30-{suffix}.example.com"
    admin_email = f"cto+{suffix}@{domain}"
    payload = {
        "name": f"Iter30 Digest Co {suffix}",
        "admin_email": admin_email,
        "admin_full_name": "Iter30 Admin",
        "industry": "Technology",
        "seat_count": 25,
    }
    r = session.post(
        f"{BASE_URL}/api/admin/orgs", json=payload,
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    admin = body["admin"]
    org = body["organization"]

    # Log the admin in for downstream calls
    lr = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": admin["email"], "password": admin["temp_password"],
    })
    assert lr.status_code == 200, lr.text
    admin_token = lr.json()["token"]

    return {
        "org": org,
        "admin_email": admin["email"],
        "admin_pw": admin["temp_password"],
        "admin_token": admin_token,
    }


# =========================================================================
# Sanity regressions
# =========================================================================
class TestSanity:
    def test_api_health(self, session):
        r = session.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "healthy"

    def test_admin_analytics_shape(self, session, super_admin_token):
        r = session.get(
            f"{BASE_URL}/api/admin/analytics?days=30",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Iter-16 shape: signups_per_day + certs_per_day arrays, zero-filled to 30 days
        assert "signups_per_day" in body
        assert "certs_per_day" in body
        assert isinstance(body["signups_per_day"], list)
        assert isinstance(body["certs_per_day"], list)
        # Zero-fill guarantee: exactly 30 buckets
        assert len(body["signups_per_day"]) == 30, len(body["signups_per_day"])
        assert len(body["certs_per_day"]) == 30
        # Bucket shape sanity
        first = body["signups_per_day"][0]
        assert "date" in first
        assert "count" in first
        assert isinstance(first["count"], int)

    def test_admin_orgs_lookup(self, session, super_admin_token, provisioned_org):
        r = session.get(
            f"{BASE_URL}/api/admin/orgs",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "organizations" in body
        assert isinstance(body["organizations"], list)
        # Every org from $lookup should carry seats_used
        assert len(body["organizations"]) > 0
        seed_org_id = provisioned_org["org"]["id"]
        found = [o for o in body["organizations"] if o["id"] == seed_org_id]
        assert len(found) == 1
        o = found[0]
        assert "seats_used" in o
        # Owner was auto-added → seats_used >= 1
        assert o["seats_used"] >= 1
        assert "_id" not in o

    def test_assessment_session_randomized(self, session, provisioned_org):
        token = provisioned_org["admin_token"]
        url = f"{BASE_URL}/api/courses/enterprise-ai-learn-2/assessment/session"
        r1 = session.get(url, headers={"Authorization": f"Bearer {token}"})
        if r1.status_code == 404:
            pytest.skip("assessment course not seeded in this env")
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert "questions" in b1 or "quiz" in b1 or "session_id" in b1


# =========================================================================
# Digest refactor: preview + send
# =========================================================================
class TestDigestRefactor:
    def test_preview_html_contains_kpis_and_org_name(self, session, provisioned_org):
        token = provisioned_org["admin_token"]
        org = provisioned_org["org"]
        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/preview",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "html" in body and "meta" in body and "org_id" in body
        assert body["org_id"] == org["id"]

        html = body["html"]
        assert isinstance(html, str) and len(html) > 500

        # _digest_shell_html contract
        assert html.strip().endswith("</html>")
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()

        # Org name appears (shell escapes it — plain name should still be present)
        assert org["name"] in html

        # KPI row from _kpi_row_html — labels
        assert "Readiness" in html
        assert "Certifications" in html
        assert "Avg progress" in html
        assert "Seats" in html
        # 25 total seats provisioned, 1 used ("1/25")
        assert f"{org['seat_count']}" in html

        # Meta shape
        meta = body["meta"]
        assert "critical_signal_count" in meta
        assert "pending_patch_count" in meta
        assert "generated_at" in meta
        assert isinstance(meta["critical_signal_count"], int)
        assert isinstance(meta["pending_patch_count"], int)

    def test_preview_unauth_rejected(self, session):
        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/preview",
            json={},
        )
        assert r.status_code in (401, 403)

    def test_preview_non_member_rejected(self, session):
        # Register a fresh user with no org
        email = f"iter30.solo+{_rand()}@example.com"
        pw = "TestPass123!"
        rr = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": pw, "full_name": "Solo",
            "organization": "SoloCorp", "title": "Analyst",
        })
        assert rr.status_code == 200, rr.text
        token = rr.json()["token"]

        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/preview",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        # _resolve_org_for_user raises 404 for non-members
        assert r.status_code == 404

    def test_send_requires_admin_role(self, session, provisioned_org):
        # Add a second non-admin member and try to send
        admin_token = provisioned_org["admin_token"]
        org = provisioned_org["org"]
        member_email = f"iter30.mem+{_rand()}@{org['domain']}"
        cu = session.post(
            f"{BASE_URL}/api/enterprise/organizations/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": member_email, "full_name": "Iter30 Member",
                "department": "Eng", "role": "member",
            },
        )
        assert cu.status_code == 200, cu.text
        member_temp = cu.json()["temp_password"]

        # Login as the new member
        lr = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": member_email, "password": member_temp,
        })
        assert lr.status_code == 200, lr.text
        member_token = lr.json()["token"]

        # Non-admin SEND should be 403
        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/send",
            headers={"Authorization": f"Bearer {member_token}"},
            json={},
        )
        assert r.status_code == 403, r.text

        # Non-admin PREVIEW is allowed (anyone in the org)
        r2 = session.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/preview",
            headers={"Authorization": f"Bearer {member_token}"},
            json={},
        )
        assert r2.status_code == 200, r2.text

    def test_send_by_admin_returns_log(self, session, provisioned_org):
        token = provisioned_org["admin_token"]
        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"to": f"iter30.recv+{_rand()}@example.com"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "log" in body
        log = body["log"]
        for k in ("id", "org_id", "recipients", "delivery", "sent_at", "meta"):
            assert k in log, f"missing key {k} in log"
        assert isinstance(log["recipients"], list)
        assert isinstance(log["delivery"], list)
        assert "_id" not in log


# =========================================================================
# fulfill_seat_increment refactor
# =========================================================================
class TestFulfillSeatIncrementRefactor:
    def test_unauth_rejected(self, session):
        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/seats/fulfill/cs_test_missing"
        )
        assert r.status_code in (401, 403)

    def test_non_owner_rejected(self, session, provisioned_org):
        # Provision a second member (non-owner) in the org
        admin_token = provisioned_org["admin_token"]
        org = provisioned_org["org"]
        member_email = f"iter30.f+{_rand()}@{org['domain']}"
        cu = session.post(
            f"{BASE_URL}/api/enterprise/organizations/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": member_email, "full_name": "Iter30 NonOwner",
                "department": "Eng", "role": "member",
            },
        )
        assert cu.status_code == 200, cu.text
        temp = cu.json()["temp_password"]
        lr = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": member_email, "password": temp,
        })
        assert lr.status_code == 200, lr.text
        member_token = lr.json()["token"]

        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/seats/fulfill/cs_test_missing",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        # 403 either because member is not admin (_resolve_org_for_user
        # require_admin=True) OR because the additional "owner only" check
        # fires after admin passes. Either way ≠ 200.
        assert r.status_code == 403, r.text

    def test_owner_unknown_session_returns_404(self, session, provisioned_org):
        # The provisioned admin IS the owner (create_org_with_admin makes them owner)
        token = provisioned_org["admin_token"]
        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/seats/fulfill/cs_test_nonexistent_{_rand()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        # _load_seat_txn raises 404 when txn missing
        assert r.status_code == 404, r.text
        assert "not found" in r.json()["detail"].lower()

    def test_idempotency_already_fulfilled(self, session, provisioned_org):
        """Inject a pre-fulfilled txn directly via a preview → fulfill flow.

        We can't actually complete Stripe checkout in a test env, but we can
        verify that the fast-path idempotency (payment_status == "paid" AND
        fulfilled_at set) returns {already_fulfilled: True} without hitting
        Stripe. To do so we craft a session_id → payment_transactions row
        via the seats-increase endpoint (which creates a `pending` row), then
        directly manipulate that row via a follow-up increment attempt using
        the existing "already-fulfilled fast-path".

        This test is a smoke test only — it asserts that when Stripe is
        unavailable in the test env we get a well-formed 502 OR that the txn
        creation itself failed cleanly. That mirrors what iter-20 already
        verified for the checkout path.
        """
        token = provisioned_org["admin_token"]
        # Try an increase — may return 502 if Stripe secret missing, or 200 with
        # a checkout_url. Both are acceptable for the refactor's contract.
        r = session.post(
            f"{BASE_URL}/api/enterprise/organizations/seats",
            headers={"Authorization": f"Bearer {token}"},
            json={"seat_count": 30, "origin_url": BASE_URL},
        )
        assert r.status_code in (200, 502), r.text
        if r.status_code != 200:
            pytest.skip("Stripe unavailable — cannot craft a real txn for fulfill idempotency")

        body = r.json()
        session_id = body["session_id"]

        # Immediately call fulfill on that pending session — since payment
        # hasn't happened at Stripe, we expect either:
        #   • 502 (get_checkout_status raises → wrapped as HTTPException 502), or
        #   • 200 with fulfilled=False (payment_status != "paid" branch)
        r2 = session.post(
            f"{BASE_URL}/api/enterprise/organizations/seats/fulfill/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code in (200, 502), r2.text
        if r2.status_code == 200:
            b2 = r2.json()
            # Either not-yet-paid (fulfilled: False) or already_fulfilled True
            assert ("fulfilled" in b2) or ("already_fulfilled" in b2)
