"""Iteration 47: AI Tutor persona, structured meta footer, quiz multi-turn,
and DB session meta-stripping."""
import json
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://enterprise-agent-dev.preview.emergentagent.com").rstrip("/")
LEARNER_EMAIL = "refe_1784091849@test.com"
LEARNER_PASSWORD = "Passw0rd!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": LEARNER_EMAIL, "password": LEARNER_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Learner login failed: {r.status_code} {r.text}")
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- Persona endpoint tests ---
class TestTutorProfile:
    """GET /api/ai/tutor-profile returns correct persona per course category."""

    def test_no_slug_returns_aletheia(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/ai/tutor-profile", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["name"] == "Aletheia"

    def test_governance_returns_themis(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/ai/tutor-profile",
            headers=auth_headers,
            params={"course_slug": "ai-governance-compliance"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Themis"

    def test_prompt_returns_calliope(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/ai/tutor-profile",
            headers=auth_headers,
            params={"course_slug": "prompt-engineering-mastery"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Calliope"

    def test_cao_returns_athena(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/ai/tutor-profile",
            headers=auth_headers,
            params={"course_slug": "chief-ai-officer-track"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Athena"

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/ai/tutor-profile", timeout=10)
        assert r.status_code in (401, 403)


def _consume_sse(response, timeout=60):
    """Consume the SSE stream, returning list of parsed events."""
    events = []
    start = time.time()
    buf = ""
    for line in response.iter_lines(decode_unicode=True):
        if time.time() - start > timeout:
            break
        if line is None:
            continue
        if not line:
            continue
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except Exception:
                pass
            if events and events[-1].get("done"):
                break
    return events


# --- SSE stream + META footer tests ---
class TestTutorStream:
    """POST /api/ai/tutor streams answer + @@META@@ JSON footer."""

    def test_stream_produces_meta_footer(self, auth_headers):
        session_id = str(uuid.uuid4())
        body = {
            "message": "In one paragraph, what is an AI agent?",
            "session_id": session_id,
            "course_context": None,
            "mode": None,
        }
        r = requests.post(
            f"{BASE_URL}/api/ai/tutor",
            headers=auth_headers,
            json=body,
            stream=True,
            timeout=90,
        )
        assert r.status_code == 200
        events = _consume_sse(r, timeout=90)
        deltas = "".join(e.get("delta", "") for e in events if "delta" in e)
        done_evt = next((e for e in events if e.get("done")), None)
        assert done_evt is not None, "did not receive done event"
        assert "@@META@@" in deltas, f"no META marker in stream. Sample:\n{deltas[-400:]}"
        # Parse the JSON footer
        footer = deltas.split("@@META@@", 1)[1].strip()
        # Take just the first line / JSON object
        meta = json.loads(footer.splitlines()[0] if "\n" in footer else footer)
        assert "understanding" in meta
        assert "mode" in meta
        assert isinstance(meta.get("suggested_actions"), list)
        assert len(meta["suggested_actions"]) >= 1
        for a in meta["suggested_actions"]:
            assert "label" in a and "action" in a
        assert "knowledge_check" in meta

        # Return session id for the next test
        return session_id, done_evt.get("session_id")

    def test_stored_session_strips_meta(self, auth_headers):
        session_id = str(uuid.uuid4())
        body = {
            "message": "One-sentence definition of RAG please.",
            "session_id": session_id,
        }
        r = requests.post(
            f"{BASE_URL}/api/ai/tutor",
            headers=auth_headers,
            json=body,
            stream=True,
            timeout=90,
        )
        assert r.status_code == 200
        events = _consume_sse(r, timeout=90)
        done_evt = next((e for e in events if e.get("done")), None)
        assert done_evt, "no done event"
        stored_id = done_evt["session_id"]

        # Fetch DB session
        s = requests.get(
            f"{BASE_URL}/api/ai/sessions/{stored_id}",
            headers=auth_headers,
            timeout=15,
        )
        assert s.status_code == 200
        session = s.json()
        assistant_msgs = [m for m in session.get("messages", []) if m.get("role") == "assistant"]
        assert assistant_msgs, "no assistant message stored"
        for m in assistant_msgs:
            assert "@@META@@" not in m["content"], f"raw META in stored content: {m['content'][-200:]}"


# --- Quiz mode multi-turn continuity ---
class TestQuizMode:
    """Quiz mode: 5-question quiz, continues on same session_id with scoring."""

    def test_quiz_start_and_answer(self, auth_headers):
        session_id = str(uuid.uuid4())
        # Start quiz
        r1 = requests.post(
            f"{BASE_URL}/api/ai/tutor",
            headers=auth_headers,
            json={
                "message": "Quiz me — start a 5-question quiz on prompt engineering.",
                "session_id": session_id,
                "course_context": "prompt-engineering-mastery",
                "mode": "quiz",
            },
            stream=True,
            timeout=120,
        )
        assert r1.status_code == 200
        events1 = _consume_sse(r1, timeout=120)
        deltas1 = "".join(e.get("delta", "") for e in events1 if "delta" in e)
        done1 = next((e for e in events1 if e.get("done")), None)
        assert done1, "quiz start: no done"
        assert "@@META@@" in deltas1, "quiz start: missing META"
        footer1 = deltas1.split("@@META@@", 1)[1].strip().splitlines()[0]
        meta1 = json.loads(footer1)
        actions1 = meta1.get("suggested_actions", [])
        # Should be MCQ-like options (2-4 chips)
        assert len(actions1) >= 2, f"quiz should offer options, got {actions1}"

        stored_id = done1["session_id"]
        # Pick an answer (first option) and continue on same session
        answer_msg = actions1[0]["action"]
        r2 = requests.post(
            f"{BASE_URL}/api/ai/tutor",
            headers=auth_headers,
            json={
                "message": answer_msg,
                "session_id": stored_id,
                "course_context": "prompt-engineering-mastery",
                "mode": "quiz",
            },
            stream=True,
            timeout=120,
        )
        assert r2.status_code == 200
        events2 = _consume_sse(r2, timeout=120)
        deltas2 = "".join(e.get("delta", "") for e in events2 if "delta" in e)
        done2 = next((e for e in events2 if e.get("done")), None)
        assert done2, "quiz turn 2: no done"
        assert done2["session_id"] == stored_id, "session id must persist across turns"
        # Should reference a running score
        lower = deltas2.lower()
        score_indicators = ["score", "correct", "incorrect", "partially", "1/5", "2/5", "next question"]
        matched = [k for k in score_indicators if k in lower]
        assert matched, f"expected grading/score signal in turn 2. Sample: {deltas2[-300:]}"

        # Verify persisted session has multi-turn history and no META
        s = requests.get(
            f"{BASE_URL}/api/ai/sessions/{stored_id}",
            headers=auth_headers,
            timeout=15,
        )
        assert s.status_code == 200
        msgs = s.json().get("messages", [])
        # At least 4 messages (u,a,u,a)
        assert len(msgs) >= 4, f"expected >=4 messages, got {len(msgs)}"
        for m in msgs:
            if m["role"] == "assistant":
                assert "@@META@@" not in m["content"]
