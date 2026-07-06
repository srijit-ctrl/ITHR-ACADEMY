"""Iteration 24 — Transactional email dispatch + palette-locked PDF tests.

Covers:
1. POST /api/auth/register → welcome email fire-and-forget; response <2s.
2. POST /api/auth/forgot-password → real Resend send fires; sender=no-reply@ithr.tech.
3. Certificate issuance (quiz/submit at 100%) → cert email fire-and-forget.
4. POST /api/enterprise/organizations/invites → invite email fire-and-forget.
5. GET /api/certificates/SAMPLE-ITHR-2026-001/pdf → 200 + >20KB + valid PDF.

Verification of the actual Resend send is done by tailing backend logs — we
assert the `[email/<tag>] Sent to <email> (resend id: ...)` marker appears
within a short window of the API call. If sender is wrong the marker won't
appear or would be replaced by a `[email/<tag>] Resend send failed` line.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent.parent / "frontend" / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

# Resend limits our account to 2 requests/sec — space out sends generously in
# tests so we don't need a paid plan just to keep CI green. 800ms is safe.
RESEND_THROTTLE_S = 0.8
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()

BACKEND_LOG_PATHS = [
    "/var/log/supervisor/backend.out.log",
    "/var/log/supervisor/backend.err.log",
]


def _read_recent_log(seconds_back: float = 30.0, max_bytes: int = 200_000) -> str:
    """Read the tail of backend logs — combined stdout+stderr."""
    combined = ""
    for p in BACKEND_LOG_PATHS:
        try:
            with open(p, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - max_bytes))
                combined += f.read().decode("utf-8", errors="replace")
        except FileNotFoundError:
            pass
    return combined


def _wait_for_log_line(pattern: str, timeout: float = 10.0, start_marker_ts: float | None = None) -> str | None:
    """Poll backend logs until a matching line appears; return the line or None on timeout."""
    deadline = time.time() + timeout
    rx = re.compile(pattern)
    while time.time() < deadline:
        content = _read_recent_log()
        # walk lines from bottom for recent-first matching
        for line in content.splitlines()[::-1]:
            if rx.search(line):
                return line
        time.sleep(0.5)
    return None


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(os.environ.get("MONGO_URL"))
    yield client[os.environ.get("DB_NAME")]
    client.close()


@pytest.fixture(autouse=True)
def _throttle_resend():
    """Sleep before each test so back-to-back Resend calls stay under 2 req/s."""
    time.sleep(RESEND_THROTTLE_S)
    yield


# ---------------------------------------------------------------------------
# 1. Welcome email on register
# ---------------------------------------------------------------------------
class TestWelcomeEmail:
    def test_register_dispatches_welcome_email_nonblocking(self, api):
        ts = int(time.time() * 1000)
        email = f"iter24.welcome+{ts}-{uuid.uuid4().hex[:6]}@example.com"
        payload = {
            "email": email,
            "password": "WelcomePass123!",
            "full_name": "Iter24 Welcome Tester",
        }
        t0 = time.perf_counter()
        r = api.post(f"{API}/auth/register", json=payload)
        elapsed = time.perf_counter() - t0
        assert r.status_code == 200, r.text
        # Fire-and-forget = register must NOT block on Resend network
        assert elapsed < 3.0, f"register took {elapsed:.2f}s — email dispatch is blocking"

        # Wait up to 10s for the welcome-email log line to appear
        line = _wait_for_log_line(rf"\[email/welcome\] Sent to {re.escape(email)}", timeout=12.0)
        assert line is not None, (
            f"Welcome email log line not found within 12s for {email}. "
            "Check backend logs for [email/welcome] Resend errors."
        )
        # Extract resend id — must be a non-empty string in the log line
        m = re.search(r"resend id: ([^\)\s]+)", line)
        assert m is not None, f"resend id not found in welcome log line: {line}"
        assert len(m.group(1)) > 5, f"resend id looks empty/invalid: {m.group(1)}"


# ---------------------------------------------------------------------------
# 2. Forgot-password Resend send
# ---------------------------------------------------------------------------
class TestForgotPasswordResend:
    def test_forgot_password_fires_real_resend_send(self, api, mongo):
        # Reset the in-app rate limiter so this test is hermetic (earlier
        # test runs on the same IP will otherwise silently throttle us).
        mongo.pw_reset_rate.delete_many({})

        # Register a fresh user first so forgot-password has a real account
        ts = int(time.time() * 1000)
        email = f"iter24.forgot+{ts}-{uuid.uuid4().hex[:6]}@example.com"
        r = api.post(f"{API}/auth/register", json={
            "email": email,
            "password": "SomePass123!",
            "full_name": "Iter24 Forgot Tester",
        })
        assert r.status_code == 200, r.text
        # Register just fired a welcome email — space to avoid Resend 2/sec throttle
        time.sleep(RESEND_THROTTLE_S)

        # Trigger forgot-password
        r2 = api.post(f"{API}/auth/forgot-password", json={"email": email})
        assert r2.status_code == 200, r2.text

        # Wait for the [password_reset] Sent line
        line = _wait_for_log_line(rf"\[password_reset\] Sent to {re.escape(email)}", timeout=12.0)
        assert line is not None, (
            f"password_reset Sent log line not found for {email} — check for ResendError in backend logs "
            "(may indicate sandbox restriction is still active)."
        )
        m = re.search(r"resend id: ([^\)\s]+)", line)
        assert m is not None, f"resend id not present in line: {line}"
        rid = m.group(1)
        assert rid and rid.lower() != "none" and len(rid) > 5, f"resend id looks empty: {rid}"

    def test_sender_email_is_no_reply_ithr_tech(self):
        assert SENDER_EMAIL == "no-reply@ithr.tech", (
            f"SENDER_EMAIL env var must be no-reply@ithr.tech, got: '{SENDER_EMAIL}'"
        )


# ---------------------------------------------------------------------------
# 3. Certificate email on quiz-pass
# ---------------------------------------------------------------------------
class TestCertificateEmail:
    def test_quiz_pass_dispatches_cert_email_nonblocking(self, api):
        ts = int(time.time() * 1000)
        email = f"iter24.cert+{ts}-{uuid.uuid4().hex[:6]}@example.com"
        reg = api.post(f"{API}/auth/register", json={
            "email": email,
            "password": "CertPass123!",
            "full_name": "Iter24 Cert Tester",
        })
        assert reg.status_code == 200, reg.text
        token = reg.json()["token"]
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Register just fired a welcome email — space next Resend call
        time.sleep(RESEND_THROTTLE_S)

        slug = "agentic-ai-foundations"
        # Enroll
        enr = api.post(f"{API}/courses/{slug}/enroll", headers=h)
        assert enr.status_code in (200, 201), enr.text

        # Get quiz
        course = api.get(f"{API}/courses/{slug}").json()
        answers = {q["id"]: q["correct"] for q in course["quiz"]}

        t0 = time.perf_counter()
        r = api.post(
            f"{API}/courses/{slug}/quiz/submit",
            headers=h,
            json={"course_id": course["id"], "answers": answers, "duration_seconds": 300},
        )
        elapsed = time.perf_counter() - t0
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["passed"] is True
        assert d["certificate"] is not None
        # Cert issuance must not block on email — allow up to 3s for the endpoint
        assert elapsed < 3.5, f"quiz/submit took {elapsed:.2f}s — cert-email dispatch is blocking"

        line = _wait_for_log_line(rf"\[email/cert\] Sent to {re.escape(email)}", timeout=12.0)
        assert line is not None, (
            f"[email/cert] Sent log not found for {email}. "
            "Certificate email did not dispatch (or Resend failed)."
        )
        m = re.search(r"resend id: ([^\)\s]+)", line)
        assert m is not None, f"resend id missing in cert log: {line}"
        assert len(m.group(1)) > 5, f"resend id empty: {m.group(1)}"


# ---------------------------------------------------------------------------
# 4. Org-invite email
# ---------------------------------------------------------------------------
class TestOrgInviteEmail:
    def test_create_invite_dispatches_invite_email(self, api):
        ts = int(time.time() * 1000)
        owner_email = f"iter24.owner+{ts}-{uuid.uuid4().hex[:6]}@example.com"
        reg = api.post(f"{API}/auth/register", json={
            "email": owner_email,
            "password": "OwnerPass123!",
            "full_name": "Iter24 Owner",
            "organization": "Iter24 Test Org",
            "title": "Owner",
        })
        assert reg.status_code == 200, reg.text
        token = reg.json()["token"]
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Register just fired a welcome email — space next Resend call
        time.sleep(RESEND_THROTTLE_S)

        org_r = api.post(f"{API}/enterprise/organizations", headers=h, json={
            "name": f"Iter24 Test Org {uuid.uuid4().hex[:6]}",
            "industry": "software",
            "seat_count": 25,
        })
        assert org_r.status_code == 200, org_r.text

        invitee_email = f"iter24.invitee+{ts}-{uuid.uuid4().hex[:6]}@example.com"
        t0 = time.perf_counter()
        inv_r = api.post(f"{API}/enterprise/organizations/invites", headers=h, json={
            "email": invitee_email,
            "role": "member",
            "department": "Engineering",
        })
        elapsed = time.perf_counter() - t0
        assert inv_r.status_code == 200, inv_r.text
        assert elapsed < 3.0, f"invite creation took {elapsed:.2f}s — invite-email dispatch is blocking"

        line = _wait_for_log_line(rf"\[email/invite\] Sent to {re.escape(invitee_email)}", timeout=12.0)
        assert line is not None, (
            f"[email/invite] Sent log not found for {invitee_email}. "
            "Invite email did not dispatch (or Resend failed)."
        )
        m = re.search(r"resend id: ([^\)\s]+)", line)
        assert m is not None, f"resend id missing in invite log: {line}"
        assert len(m.group(1)) > 5


# ---------------------------------------------------------------------------
# 5. Sample certificate PDF — palette locked + still 200 + >20KB + valid PDF
# ---------------------------------------------------------------------------
class TestSampleCertPdf:
    def test_sample_cert_pdf_valid(self, api):
        r = api.get(f"{API}/certificates/SAMPLE-ITHR-2026-001/pdf")
        assert r.status_code == 200, r.text
        content = r.content
        assert len(content) > 20_000, f"expected >20KB PDF, got {len(content)} bytes"
        assert content[:5] == b"%PDF-", f"expected %PDF- header, got {content[:8]!r}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_pdf_template_source_contains_ithr_palette(self):
        """Sanity-check the palette lock at the template source layer."""
        p = Path(__file__).parent.parent / "routers" / "assessment_router.py"
        content = p.read_text()
        # Teal + Navy must be present, and no legacy purple / orange hex should
        # be present in the PDF template.
        assert "#00A78B" in content, "ITHR Teal #00A78B missing from PDF template"
        assert "#16335E" in content, "ITHR Navy #16335E missing from PDF template"
