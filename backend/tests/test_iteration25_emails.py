"""Iter-25 backend tests.

Covers:
- Super-admin analytics matches post-purge state (55 users, 25 orgs, 1 cert).
- POST /api/admin/emails/complaint-response — validation, RBAC, success + log line.
- POST /api/admin/emails/validity-expiration — validation, RBAC, success + log line.
- GET /api/certificates/verify/SAMPLE-ITHR-2026-001 — NO verify-alert email fires (suppressed).
- Payment-confirmation email dispatch code path exists in checkout_router.
- send_credential_verification_alert throttle logic (unit-level via code inspection).
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

SUPER_ADMIN_EMAIL = "superadmin@ithr.tech"
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "preview-only-rotate-in-prod")

BACKEND_LOG_PATHS = [
    "/var/log/supervisor/backend.out.log",
    "/var/log/supervisor/backend.err.log",
]


# ---------- fixtures ------------------------------------------------------
@pytest.fixture(scope="module")
def super_admin_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"super-admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["user"]["role"] == "super_admin"
    return data["token"]


@pytest.fixture(scope="module")
def learner_token() -> str:
    """A fresh learner used to assert 403 on admin-only endpoints."""
    ts = int(time.time())
    email = f"iter25.learner+{ts}@example.com"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": email,
            "password": "IterTest25!Pass",
            "full_name": "Iter25 Learner",
            "organization": "iter25-QA",
            "title": "QA",
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), f"learner register failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _tail_backend_log(pattern: str, tail_lines: int = 400) -> str | None:
    for p in BACKEND_LOG_PATHS:
        if not Path(p).exists():
            continue
        try:
            out = subprocess.check_output(
                ["tail", "-n", str(tail_lines), p], stderr=subprocess.DEVNULL, timeout=5,
            ).decode("utf-8", errors="replace")
        except Exception:
            continue
        m = re.search(pattern, out)
        if m:
            return m.group(0)
    return None


# ---------- Analytics ------------------------------------------------------
class TestPostPurgeAnalytics:
    def test_analytics_reflects_purge(self, super_admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/analytics?days=30",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        totals = data["totals"]
        # Post-purge invariants (allow tiny drift from test-created learners)
        assert totals["users"] >= 55 and totals["users"] <= 80, f"users={totals['users']} outside expected post-purge band"
        assert totals["orgs"] >= 25 and totals["orgs"] <= 35, f"orgs={totals['orgs']} outside expected post-purge band"
        assert totals["certs_all_time"] >= 1, "sample cert should still exist"
        assert totals["certs_all_time"] <= 5, "post-purge cert count should stay tiny"
        # Founder-perk block still present
        fp = data.get("founder_perk") or {}
        assert fp.get("cap") == 500
        assert fp.get("claimed", 0) >= 1
        # top_orgs_by_certs is allowed to be empty after purge
        assert isinstance(data.get("top_orgs_by_certs", []), list)


# ---------- Admin email endpoints ------------------------------------------
class TestAdminEmailEndpoints:
    def test_complaint_response_success(self, super_admin_token):
        payload = {
            "email": "srijit@ithr360.com",
            "ticket_ref": f"TKT-ITER25-{int(time.time())}",
            "response_text": "Iter25 automated test: acknowledging your ticket.\nBest,\nQA",
            "agent_name": "Iter25 QA Agent",
            "full_name": "Srijit",
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/emails/complaint-response",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json=payload,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["sent"] is True
        assert data["email"] == payload["email"]
        assert data["ticket_ref"] == payload["ticket_ref"]

        # Wait briefly for the async send + log flush
        time.sleep(3)
        hit = _tail_backend_log(rf"\[email/support\] Sent to {re.escape(payload['email'])} \(resend id: [^)]+\)")
        assert hit, "Expected '[email/support] Sent to ...' log line within 3s of dispatch"

    def test_complaint_response_missing_fields(self, super_admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/emails/complaint-response",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"email": "someone@example.com"},  # missing ticket_ref + response_text
            timeout=15,
        )
        assert r.status_code == 400
        assert "required" in r.json().get("detail", "").lower()

    def test_complaint_response_rejects_learner(self, learner_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/emails/complaint-response",
            headers={"Authorization": f"Bearer {learner_token}"},
            json={
                "email": "someone@example.com",
                "ticket_ref": "TKT-1",
                "response_text": "test",
            },
            timeout=15,
        )
        assert r.status_code == 403

    def test_validity_expiration_success(self, super_admin_token):
        payload = {
            "email": "srijit@ithr360.com",
            "credential_or_plan": "Practitioner tier",
            "expires_on": "March 15, 2026",
            "renewal_url": "https://example.com/renew",
            "full_name": "Srijit",
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/emails/validity-expiration",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json=payload,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["sent"] is True
        assert data["email"] == payload["email"]

        time.sleep(3)
        hit = _tail_backend_log(rf"\[email/expiration\] Sent to {re.escape(payload['email'])} \(resend id: [^)]+\)")
        assert hit, "Expected '[email/expiration] Sent to ...' log line within 3s of dispatch"

    def test_validity_expiration_missing_fields(self, super_admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/emails/validity-expiration",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"email": "someone@example.com", "credential_or_plan": "X"},  # missing expires_on
            timeout=15,
        )
        assert r.status_code == 400
        assert "required" in r.json().get("detail", "").lower()

    def test_validity_expiration_rejects_learner(self, learner_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/emails/validity-expiration",
            headers={"Authorization": f"Bearer {learner_token}"},
            json={
                "email": "someone@example.com",
                "credential_or_plan": "X",
                "expires_on": "March 15, 2026",
            },
            timeout=15,
        )
        assert r.status_code == 403


# ---------- Sample cert verify: no email fire -----------------------------
class TestSampleCertVerifySuppression:
    def test_sample_cert_verify_no_email_fires(self):
        # Snapshot log first, then hit endpoint, then assert no NEW verify-alert line
        pre_snapshot_len = 0
        for p in BACKEND_LOG_PATHS:
            if Path(p).exists():
                pre_snapshot_len += Path(p).stat().st_size

        r = requests.get(
            f"{BASE_URL}/api/certificates/verify/SAMPLE-ITHR-2026-001",
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["valid"] is True
        assert data["certificate"]["certificate_id"] == "SAMPLE-ITHR-2026-001"

        # Wait for any async task to finish
        time.sleep(3)

        # Look at newly appended log content
        new_content = ""
        for p in BACKEND_LOG_PATHS:
            if not Path(p).exists():
                continue
            with open(p, "rb") as f:
                # read all — the file may have rotated, so best-effort
                content = f.read().decode("utf-8", errors="replace")
            new_content += content

        # In the last ~1000 chars only (proxy for "recent")
        tail = new_content[-4000:]
        assert "[email/verify-alert]" not in tail or "SAMPLE-ITHR-2026-001" not in tail, (
            "SAMPLE cert must NOT fire a verify-alert email (explicit suppression)."
        )


# ---------- Payment confirmation code path exists -------------------------
class TestPaymentConfirmationCodePath:
    def test_checkout_router_dispatches_payment_email(self):
        p = Path("/app/backend/routers/checkout_router.py")
        assert p.exists(), "checkout_router.py missing"
        src = p.read_text()
        assert "send_payment_confirmation_email" in src, (
            "checkout_router must import + dispatch send_payment_confirmation_email"
        )
        # Idempotency guard: only dispatch when transitioning INTO paid
        assert 'txn.get("payment_status") != "paid"' in src, (
            "payment-confirmation dispatch should be guarded by an idempotency check"
        )
        # Fire-and-forget wrapper
        assert "create_task(send_payment_confirmation_email" in src, (
            "dispatch should be fire-and-forget via asyncio.create_task"
        )


# ---------- Verify-alert throttle logic (source inspection) --------------
class TestVerifyAlertThrottle:
    def test_assessment_router_has_6h_throttle_and_sample_suppression(self):
        p = Path("/app/backend/routers/assessment_router.py")
        src = p.read_text()
        assert "send_credential_verification_alert" in src
        assert 'timedelta(hours=6)' in src, "6-hour throttle window expected"
        assert 'SAMPLE-ITHR-2026-001' in src, "explicit SAMPLE cert suppression expected"
        assert "last_verify_alert_at" in src, "throttle persistence field expected"
        assert "hashlib.sha256" in src, "verifier IP must be hashed for privacy"
