"""Iteration 7 backend tests — Try-a-lesson demo, Digest, Notifications, Cert PDF, Patch-webhook side-effect.

Feature coverage:
- POST/GET /api/demo/*  (rate-limit + SSE streaming + validation)
- GET  /api/certificates/{id}/pdf (WeasyPrint, application/pdf, filename header)
- POST /api/enterprise/organizations/digest/preview + /send + GET /log
- POST/GET /api/enterprise/organizations/notifications
- POST /api/intelligence/patches/{id}/decide with webhook side-effect (does not break approval)
"""
from __future__ import annotations

import json
import os
import time
import uuid

import pytest
import requests

def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if url:
        return url.rstrip("/")
    # Fallback: read from /app/frontend/.env
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url()


# ---------- Fixtures ----------
def _register(email_prefix: str, org: str = "TEST Org"):
    email = f"TEST_iter7_{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": "TestPass123!",
        "full_name": f"Iter7 {email_prefix}",
        "organization": org,
        "title": "Analyst",
    }, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    return data["token"], data["user"]


@pytest.fixture(scope="module")
def learner():
    tok, user = _register("learner")
    return {"token": tok, "user": user, "headers": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def owner_with_org():
    tok, user = _register("owner")
    headers = {"Authorization": f"Bearer {tok}"}
    r = requests.post(f"{BASE_URL}/api/enterprise/organizations",
                      json={"name": f"TEST Iter7 Co {uuid.uuid4().hex[:6]}", "seat_count": 25, "industry": "Technology"},
                      headers=headers, timeout=30)
    assert r.status_code == 200, f"org create failed: {r.status_code} {r.text[:200]}"
    org = r.json()["organization"]
    return {"token": tok, "user": user, "headers": headers, "org": org}


# ==================== DEMO ====================
class TestDemoLesson:
    def test_lesson_public_shape(self):
        # no Authorization header
        r = requests.get(f"{BASE_URL}/api/demo/lesson", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "What is an AI Agent?"
        assert isinstance(data["sections"], list) and len(data["sections"]) == 3
        assert isinstance(data["suggested_questions"], list) and len(data["suggested_questions"]) == 3

    def test_ask_short_message_422(self):
        r = requests.post(f"{BASE_URL}/api/demo/ask", json={"message": "a"}, timeout=15)
        assert r.status_code == 422

    def test_ask_long_message_422(self):
        r = requests.post(f"{BASE_URL}/api/demo/ask", json={"message": "x" * 501}, timeout=15)
        assert r.status_code == 422

    def test_ask_sse_stream(self):
        """Fresh IP -> should stream remaining_in_window then deltas then done=true."""
        # Use a unique X-Forwarded-For so we get a fresh window
        fake_ip = f"10.9.7.{int(time.time()) % 250 + 1}"
        headers = {"X-Forwarded-For": fake_ip, "Content-Type": "application/json"}
        with requests.post(
            f"{BASE_URL}/api/demo/ask",
            json={"message": "How is an agent different from a chatbot?"},
            headers=headers,
            stream=True,
            timeout=60,
        ) as r:
            assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
            assert "text/event-stream" in r.headers.get("Content-Type", "")
            events = []
            got_done = False
            got_delta = False
            got_remaining = False
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if raw.startswith("data: "):
                    payload = json.loads(raw[6:])
                    events.append(payload)
                    if "remaining_in_window" in payload:
                        got_remaining = True
                        assert isinstance(payload["remaining_in_window"], int)
                    if "delta" in payload:
                        got_delta = True
                    if payload.get("done"):
                        got_done = True
                        break
                    if payload.get("error"):
                        break
            assert got_remaining, f"missing remaining_in_window; events={events[:3]}"
            assert got_delta, f"missing delta events; events={events[:5]}"
            assert got_done, f"missing done=true; events={events[-3:]}"

    def test_rate_limit_6th_request(self):
        """Fresh IP, fire 5 successful + 1 rate-limited (429)."""
        fake_ip = f"10.9.8.{int(time.time()) % 240 + 2}"
        headers = {"X-Forwarded-For": fake_ip, "Content-Type": "application/json"}
        # We don't need to consume the full stream — we can close after headers arrive.
        successes = 0
        for i in range(5):
            r = requests.post(
                f"{BASE_URL}/api/demo/ask",
                json={"message": f"question {i}"},
                headers=headers,
                stream=True,
                timeout=30,
            )
            if r.status_code == 200:
                successes += 1
            r.close()
        assert successes == 5, f"expected 5 successes, got {successes}"

        # 6th should be 429
        r = requests.post(
            f"{BASE_URL}/api/demo/ask",
            json={"message": "one more"},
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text[:200]}"


# ==================== CERT PDF ====================
class TestCertificatePDF:
    def test_pdf_after_quiz_pass(self, learner):
        """Issue a certificate via quiz submit, then request PDF."""
        # Pull course + assessment session for agentic-ai-foundations
        slug = "agentic-ai-foundations"
        r = requests.get(
            f"{BASE_URL}/api/courses/{slug}/assessment/session?count=5",
            headers=learner["headers"],
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        session = r.json()

        # Build all-correct answers using permutation trick
        # For each question: submit an empty selection (0 correct) OR use __perm__ trick
        # The assessment_router expects: answers[qid] = [selected_original_indices_after_perm_translation]
        # Since options were shuffled, we need to pass __perm__ mapping so submitter is translated.
        # But we don't know the correct answers here. So instead, hit the course DB via a passing_score=0 shortcut?
        # Simplest: submit an empty answers set -> score=0, no cert. Not what we want.
        # Alternate approach: use QuizSubmitRequest with all_correct pattern via peeking course.quiz
        # We DON'T have direct DB access — but the /courses/{slug} endpoint returns quiz? Let's check.
        r2 = requests.get(f"{BASE_URL}/api/courses/{slug}", timeout=15)
        assert r2.status_code == 200
        course = r2.json()
        quiz = course.get("quiz", [])
        assert quiz, "course must expose quiz for cert flow"

        # Submit all correct answers (using course-canonical indices, no perm)
        answers = {q["id"]: q["correct"] for q in quiz}
        r3 = requests.post(
            f"{BASE_URL}/api/courses/{slug}/quiz/submit",
            json={"course_id": course["id"], "answers": answers, "duration_seconds": 60},
            headers=learner["headers"],
            timeout=30,
        )
        assert r3.status_code == 200, r3.text[:200]
        result = r3.json()
        assert result["passed"] is True, f"expected pass, got {result}"
        cert = result["certificate"]
        assert cert, "expected a certificate to be issued"
        cert_id = cert["certificate_id"]

        # Now fetch PDF
        r4 = requests.get(f"{BASE_URL}/api/certificates/{cert_id}/pdf", timeout=60)
        assert r4.status_code == 200, f"pdf fetch failed: {r4.status_code} {r4.text[:200]}"
        assert r4.headers.get("Content-Type", "").startswith("application/pdf"), \
            f"expected application/pdf, got {r4.headers.get('Content-Type')}"
        cd = r4.headers.get("Content-Disposition", "")
        assert "attachment" in cd and cert_id in cd, f"missing filename in {cd}"
        # Verify it looks like a PDF
        assert r4.content[:4] == b"%PDF", f"body does not start with %PDF: {r4.content[:20]}"


# ==================== DIGEST ====================
class TestDigest:
    def test_preview_html(self, owner_with_org):
        r = requests.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/preview",
            headers=owner_with_org["headers"],
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "html" in data and "meta" in data and "org_id" in data
        html = data["html"]
        assert isinstance(html, str) and len(html) > 100
        assert "ITHR" in html
        assert "Weekly" in html

    def test_send_graceful_degradation(self, owner_with_org):
        r = requests.post(
            f"{BASE_URL}/api/enterprise/organizations/digest/send",
            headers=owner_with_org["headers"],
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "log" in data
        log = data["log"]
        assert isinstance(log.get("delivery"), list)
        assert len(log["delivery"]) >= 1
        # RESEND_API_KEY empty → delivered=false with reason=no_api_key
        for d in log["delivery"]:
            assert d["delivered"] is False
            assert d["reason"] == "no_api_key"

    def test_log_endpoint(self, owner_with_org):
        r = requests.get(
            f"{BASE_URL}/api/enterprise/organizations/digest/log",
            headers=owner_with_org["headers"],
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)
        assert len(data["logs"]) >= 1, "expected at least the send() from prior test"


# ==================== NOTIFICATIONS ====================
class TestNotifications:
    def test_set_and_get_webhooks(self, owner_with_org):
        slack_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        teams_url = "https://example.webhook.office.com/webhook/xxx"
        r = requests.post(
            f"{BASE_URL}/api/enterprise/organizations/notifications",
            headers=owner_with_org["headers"],
            json={"slack_webhook_url": slack_url, "teams_webhook_url": teams_url},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:200]
        updated = r.json()["updated"]
        assert updated["slack_webhook_url"] == slack_url
        assert updated["teams_webhook_url"] == teams_url

        r2 = requests.get(
            f"{BASE_URL}/api/enterprise/organizations/notifications",
            headers=owner_with_org["headers"],
            timeout=15,
        )
        assert r2.status_code == 200
        got = r2.json()
        assert got["slack_webhook_url"] == slack_url
        assert got["teams_webhook_url"] == teams_url

    def test_invalid_slack_url_400(self, owner_with_org):
        r = requests.post(
            f"{BASE_URL}/api/enterprise/organizations/notifications",
            headers=owner_with_org["headers"],
            json={"slack_webhook_url": "not-a-url"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_invalid_teams_url_400(self, owner_with_org):
        r = requests.post(
            f"{BASE_URL}/api/enterprise/organizations/notifications",
            headers=owner_with_org["headers"],
            json={"teams_webhook_url": "http://insecure.example.com/webhook"},
            timeout=15,
        )
        assert r.status_code == 400


# ==================== PATCH DECIDE + WEBHOOK SIDE-EFFECT ====================
class TestPatchDecideWithWebhook:
    def test_patch_decide_does_not_break_with_fake_webhooks(self, owner_with_org):
        """
        With fake Slack/Teams webhooks configured, approving a patch should still return 200.
        The notification failures should be swallowed (best-effort).
        """
        # Get a patch — first list existing ones (iter6 may have created some)
        r = requests.get(
            f"{BASE_URL}/api/intelligence/patches",
            headers=owner_with_org["headers"],
            timeout=15,
        )
        assert r.status_code == 200
        patches = r.json().get("patches", [])
        # Find a proposed one, or seed a new one via signals/apply
        proposed = next((p for p in patches if p.get("status") == "proposed"), None)
        if not proposed:
            # Seed briefing + apply signal — slow LLM path (~90s)
            b = requests.get(f"{BASE_URL}/api/intelligence/briefing", timeout=180)
            assert b.status_code == 200, b.text[:200]
            signals = b.json().get("signals", [])
            assert signals, "no signals in briefing"
            r2 = requests.post(
                f"{BASE_URL}/api/intelligence/signals/{signals[0]['id']}/apply",
                json={"course_slug": "agentic-ai-foundations"},
                headers=owner_with_org["headers"],
                timeout=180,
            )
            assert r2.status_code == 200, r2.text[:200]
            proposed = r2.json()["patch"]

        # Decide approved — should return 200 even if webhooks fail
        r3 = requests.post(
            f"{BASE_URL}/api/intelligence/patches/{proposed['id']}/decide",
            json={"decision": "approved"},
            headers=owner_with_org["headers"],
            timeout=30,
        )
        assert r3.status_code == 200, f"patch decide failed: {r3.status_code} {r3.text[:200]}"
        data = r3.json()
        assert data["status"] == "approved"
