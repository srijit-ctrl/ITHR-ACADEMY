"""Iteration 5 — Phase 4 AI layer:
- Randomized assessment session + submit + attempts
- Certificate SVG QR endpoint
- Mentor (Solon) SSE chat + sessions CRUD
- Recommendation engine + next-best (Claude rationale, 24h cache)
- Light regression on legacy endpoints
"""
from __future__ import annotations

import json
import os
import time
import uuid

import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load frontend .env (has REACT_APP_BACKEND_URL) — same convention as backend_test.py
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


# ---------------- shared fixtures ----------------
@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def learner(api_client):
    email = f"test.iter5+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    password = "TestPass123!"
    r = api_client.post(f"{API}/auth/register", json={
        "email": email, "password": password, "full_name": "Iter5 Learner",
        "organization": "TEST BankCo", "title": "Product Manager",
    })
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "email": email, "password": password,
        "token": data["token"], "user": data["user"],
        "headers": {"Authorization": f"Bearer {data['token']}"},
    }


# ---------------- Assessment: randomized session ----------------
SLUG = "agentic-ai-foundations"


class TestAssessmentSession:
    def test_session_returns_questions_shape(self, api_client, learner):
        r = api_client.get(
            f"{API}/courses/{SLUG}/assessment/session?count=10",
            headers=learner["headers"],
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["slug"] == SLUG
        assert d["total"] == 10
        assert d["bank_size"] >= 15, f"bank_size={d['bank_size']}"
        assert "passing_score" in d and isinstance(d["passing_score"], int)
        assert len(d["questions"]) == 10
        for q in d["questions"]:
            assert "id" in q and "question" in q and "options" in q
            assert "permutation" in q and isinstance(q["permutation"], list)
            assert len(q["permutation"]) == len(q["options"])
            # correct MUST NOT leak
            assert "correct" not in q
            assert "explanation" not in q

    def test_session_randomization(self, api_client, learner):
        r1 = api_client.get(
            f"{API}/courses/{SLUG}/assessment/session?count=10",
            headers=learner["headers"],
        ).json()
        r2 = api_client.get(
            f"{API}/courses/{SLUG}/assessment/session?count=10",
            headers=learner["headers"],
        ).json()
        ids1 = [q["id"] for q in r1["questions"]]
        ids2 = [q["id"] for q in r2["questions"]]
        # Not deterministically identical: at least one of order or subset differs
        assert ids1 != ids2, "consecutive sessions should be randomized"


# ---------------- Assessment: submit with __perm__ + cert ----------------
class TestAssessmentSubmitAndCert:
    """Uses the raw course quiz `correct` values + session permutations to submit a passing paper."""

    def test_submit_pass_and_no_duplicate_cert(self, api_client, learner):
        # 1. Enroll (idempotent — new learner)
        api_client.post(f"{API}/courses/{SLUG}/enroll", headers=learner["headers"])

        # 2. Get session
        sess = api_client.get(
            f"{API}/courses/{SLUG}/assessment/session?count=10",
            headers=learner["headers"],
        ).json()

        # 3. Get raw course quiz to look up correct answers
        course = api_client.get(f"{API}/courses/{SLUG}").json()
        raw_by_id = {q["id"]: q for q in course["quiz"]}

        # 4. Build answers: for each session question, look up original correct,
        # then translate via inverse of `permutation` (perm maps new_idx -> orig_idx).
        answers = {}
        perms = {}
        for q in sess["questions"]:
            qid = q["id"]
            perm = q["permutation"]  # perm[new] = orig
            perms[qid] = perm
            raw_q = raw_by_id.get(qid)
            if not raw_q:
                # question may only exist in augmented bank (seed_assessments)
                # In that case skip; the server will treat it as wrong but banks
                # from seed_assessments ALSO update the course document, so this
                # should typically be present.
                answers[qid] = []
                continue
            orig_correct = raw_q["correct"]
            # translate orig -> new for submission
            inv = {orig: new for new, orig in enumerate(perm)}
            new_correct = sorted(inv[c] for c in orig_correct if c in inv)
            answers[qid] = new_correct

        answers["__perm__"] = perms

        payload = {
            "course_id": sess["course_id"],
            "answers": answers,
            "duration_seconds": 240,
        }
        r = api_client.post(
            f"{API}/courses/{SLUG}/quiz/submit",
            headers=learner["headers"],
            json=payload,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["passed"] is True, f"expected pass, got score={d['score']}"
        assert d["certificate"] is not None
        cert_id = d["certificate"]["certificate_id"]
        assert cert_id.startswith("EAIA-")
        # stash for the next test
        pytest.iter5_cert_id = cert_id
        pytest.iter5_course_id = sess["course_id"]

        # Re-submit — must NOT issue duplicate
        r2 = api_client.post(
            f"{API}/courses/{SLUG}/quiz/submit",
            headers=learner["headers"],
            json=payload,
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["passed"] is True
        # same cert returned
        assert d2["certificate"]["certificate_id"] == cert_id

    def test_certificates_list_contains_cert(self, api_client, learner):
        r = api_client.get(f"{API}/certificates", headers=learner["headers"])
        assert r.status_code == 200
        ids = [c["certificate_id"] for c in r.json()]
        assert getattr(pytest, "iter5_cert_id", None) in ids

    def test_attempts_hides_answers(self, api_client, learner):
        r = api_client.get(f"{API}/courses/{SLUG}/attempts", headers=learner["headers"])
        assert r.status_code == 200
        attempts = r.json()
        assert len(attempts) >= 1
        for a in attempts:
            assert "answers" not in a
            assert a["course_id"] == getattr(pytest, "iter5_course_id")

    def test_certificate_qr_svg(self, api_client):
        cert_id = getattr(pytest, "iter5_cert_id", None)
        assert cert_id, "cert not issued in prior test"
        r = api_client.get(f"{API}/certificates/{cert_id}/qr.svg")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/svg+xml")
        body = r.text
        assert "<svg" in body

    def test_certificate_qr_not_found(self, api_client):
        r = api_client.get(f"{API}/certificates/EAIA-DOES-NOT-EXIST/qr.svg")
        assert r.status_code == 404


# ---------------- Mentor (Solon) ----------------
def _consume_sse(resp):
    """Yield decoded json payloads from `data: ...` lines."""
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            piece = line[len("data:"):].strip()
            try:
                yield json.loads(piece)
            except json.JSONDecodeError:
                continue


class TestMentor:
    def test_chat_sse_creates_session(self, api_client, learner):
        r = requests.post(
            f"{API}/mentor/chat",
            headers={**learner["headers"], "Accept": "text/event-stream"},
            json={"message": "I am a PM in banking with 5 years. What next?"},
            stream=True, timeout=90,
        )
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        deltas = []
        session_id = None
        for evt in _consume_sse(r):
            if "delta" in evt:
                deltas.append(evt["delta"])
            if evt.get("done"):
                session_id = evt.get("session_id")
                break
        assert session_id, "did not receive done+session_id"
        assert len(deltas) > 0, "no streaming deltas received"
        full_text = "".join(deltas)
        assert len(full_text) > 30
        pytest.iter5_session_id = session_id

    def test_list_sessions_contains(self, api_client, learner):
        r = api_client.get(f"{API}/mentor/sessions", headers=learner["headers"])
        assert r.status_code == 200
        sessions = r.json()
        sid = getattr(pytest, "iter5_session_id", None)
        assert sid
        assert any(s["id"] == sid for s in sessions)

    def test_get_session_messages(self, api_client, learner):
        sid = getattr(pytest, "iter5_session_id", None)
        r = api_client.get(f"{API}/mentor/sessions/{sid}", headers=learner["headers"])
        assert r.status_code == 200
        s = r.json()
        assert s["id"] == sid
        assert len(s["messages"]) >= 2
        roles = [m["role"] for m in s["messages"]]
        assert "user" in roles and "assistant" in roles

    def test_chat_continuity_with_session_id(self, api_client, learner):
        sid = getattr(pytest, "iter5_session_id", None)
        r = requests.post(
            f"{API}/mentor/chat",
            headers={**learner["headers"], "Accept": "text/event-stream"},
            json={
                "message": "Given that context, which ITHR course should I take first?",
                "session_id": sid,
            },
            stream=True, timeout=90,
        )
        assert r.status_code == 200
        parts = []
        done = False
        for evt in _consume_sse(r):
            if "delta" in evt:
                parts.append(evt["delta"])
            if evt.get("done"):
                done = True
                assert evt.get("session_id") == sid
                break
        assert done
        full = "".join(parts).lower()
        # context ref hint (banking OR PM OR agentic ladder mention)
        ref_ok = any(k in full for k in ["bank", "pm", "product", "manager", "agentic", "foundation", "practitioner"])
        assert ref_ok, f"assistant did not reference prior context: {full[:200]}"

    def test_delete_session_and_404(self, api_client, learner):
        sid = getattr(pytest, "iter5_session_id", None)
        r = api_client.delete(f"{API}/mentor/sessions/{sid}", headers=learner["headers"])
        assert r.status_code == 200
        assert r.json() == {"deleted": True}
        r2 = api_client.get(f"{API}/mentor/sessions/{sid}", headers=learner["headers"])
        assert r2.status_code == 404

    def test_mentor_requires_auth(self, api_client):
        r = requests.get(f"{API}/mentor/sessions")
        assert r.status_code in (401, 403)


# ---------------- Recommendations ----------------
class TestRecommendations:
    def test_recommendations_list(self, api_client, learner):
        r = api_client.get(f"{API}/recommendations", headers=learner["headers"])
        assert r.status_code == 200
        d = r.json()
        assert "recommendations" in d
        recs = d["recommendations"]
        assert 0 < len(recs) <= 6, f"expected 1..6 recs, got {len(recs)}"
        for x in recs:
            assert "course" in x
            assert "score" in x and isinstance(x["score"], (int, float))
            assert "signals" in x
            # thin course shape
            assert "id" in x["course"] and "slug" in x["course"]
            assert "modules" not in x["course"]

    def test_next_best_and_cache(self, api_client, learner):
        t0 = time.time()
        r = api_client.get(f"{API}/recommendations/next-best", headers=learner["headers"])
        assert r.status_code == 200, r.text
        first_dur = time.time() - t0
        d = r.json()
        assert "recommendation" in d
        rec = d["recommendation"]
        assert rec is not None
        assert "course" in rec and "rationale" in rec
        assert isinstance(rec["rationale"], str) and len(rec["rationale"]) > 0
        first_rationale = rec["rationale"]

        # Second call — should be cached (faster) and return same rationale
        t1 = time.time()
        r2 = api_client.get(f"{API}/recommendations/next-best", headers=learner["headers"])
        second_dur = time.time() - t1
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["recommendation"]["rationale"] == first_rationale
        # Cache should be materially faster than LLM call (very lenient)
        print(f"next-best timings: first={first_dur:.2f}s second={second_dur:.2f}s")
        # We won't hard-fail on timing but assert second call is under 10s
        assert second_dur < 10, f"second call not cached (took {second_dur:.2f}s)"


# ---------------- Regression: existing endpoints ----------------
class TestRegression:
    def test_courses_count(self, api_client):
        r = api_client.get(f"{API}/courses")
        assert r.status_code == 200
        assert len(r.json()) == 24

    def test_intelligence_signals(self, api_client):
        r = api_client.get(f"{API}/intelligence/briefing")
        assert r.status_code == 200
        d = r.json()
        signals = d if isinstance(d, list) else d.get("signals", d.get("items", []))
        assert isinstance(signals, list) and len(signals) > 0

    def test_enterprise_dashboard_requires_auth(self, api_client):
        r = requests.get(f"{API}/enterprise/organizations/dashboard")
        assert r.status_code in (401, 403)
