"""Iteration 51 backend tests — covers the three additive features shipped this session:

  A) GET /api/trust/founding-seats     — public live seat counter for /register
  C) POST /api/ai/tutor/rate + GET /api/ai/tutor/ratings/{sid} — learner thumbs on tutor turns
  D) GET /api/certificates/{id}/share-image.png + /api/share/certificate/{id} — LinkedIn share

Also verifies the /api/admin/ai-ops payload now contains the ratings fields.
Tests clean up their own @example.com users (data-hygiene sweep at the end).
"""
import json
import os
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")
SAMPLE_CERT_ID = "SAMPLE-ITHR-2026-001"

# ---------------------- Fixtures ----------------------


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=API, timeout=90.0) as c:
        yield c


@pytest.fixture(scope="module")
def super_admin_token(http):
    if not SUPER_ADMIN_PASSWORD:
        pytest.skip("SUPER_ADMIN_PASSWORD not set")
    r = http.post("/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
    assert r.status_code == 200, f"super-admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def learner(http):
    """Register a fresh throw-away learner. Cleaned up in teardown at the end of the module."""
    email = f"TEST_it51_{uuid.uuid4().hex[:8]}@example.com"
    password = os.environ.get("E2E_TEST_USER_PASSWORD", "TestPass123!")
    r = http.post("/auth/register", json={
        "full_name": "Iter51 Learner",
        "email": email,
        "password": password,
    })
    assert r.status_code == 200, f"register failed: {r.text}"
    token = r.json()["token"]
    yield {"email": email, "password": password, "token": token, "user_id": r.json()["user"]["id"]}


# ---------------------- (A) Founding seats counter ----------------------


class TestFoundingSeats:
    def test_founding_seats_public(self, http):
        r = http.get("/trust/founding-seats")
        assert r.status_code == 200
        data = r.json()
        # Contract used by /register frontend
        assert set(["claimed", "total", "remaining"]).issubset(data.keys())
        assert isinstance(data["claimed"], int) and data["claimed"] >= 0
        assert data["total"] == 500
        assert data["remaining"] == data["total"] - data["claimed"]
        assert data["remaining"] >= 0


# ---------------------- (C) AI Tutor ratings ----------------------


def _stream_tutor_and_get_session(http, token: str) -> tuple[str, int]:
    """Fire one short tutor message via SSE stream and return the resulting session_id
    + number of assistant messages in the session."""
    headers = {"Authorization": f"Bearer {token}"}
    body = {"message": "One word: yes.", "session_id": None, "mode": "chat"}
    session_id = None
    with httpx.stream("POST", f"{API}/ai/tutor", json=body, headers=headers, timeout=120.0) as s:
        assert s.status_code == 200, f"tutor stream failed: {s.status_code}"
        for line in s.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            try:
                payload = json.loads(line[5:].strip())
            except Exception:
                continue
            if payload.get("done") and payload.get("session_id"):
                session_id = payload["session_id"]
                break
    assert session_id, "tutor stream did not surface a session_id"
    return session_id


class TestTutorRatings:
    def test_full_rating_flow(self, http, learner):
        token = learner["token"]
        headers = {"Authorization": f"Bearer {token}"}

        session_id = _stream_tutor_and_get_session(http, token)

        # Thumbs-up on turn 0
        r = http.post("/ai/tutor/rate", headers=headers, json={
            "session_id": session_id, "turn_index": 0, "rating": "up",
        })
        assert r.status_code == 200, r.text
        assert r.json()["rating"] == "up"

        # GET ratings
        r = http.get(f"/ai/tutor/ratings/{session_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["ratings"] == {"0": "up"}

        # Overwrite to down with a reason — value flips, no dup row
        r = http.post("/ai/tutor/rate", headers=headers, json={
            "session_id": session_id, "turn_index": 0, "rating": "down", "reason": "Too short",
        })
        assert r.status_code == 200
        r = http.get(f"/ai/tutor/ratings/{session_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["ratings"] == {"0": "down"}

        # turn_index out of range -> 400
        r = http.post("/ai/tutor/rate", headers=headers, json={
            "session_id": session_id, "turn_index": 99, "rating": "up",
        })
        assert r.status_code == 400

        # Ownership: session not owned by caller -> 404 (use a random uuid)
        r = http.post("/ai/tutor/rate", headers=headers, json={
            "session_id": str(uuid.uuid4()), "turn_index": 0, "rating": "up",
        })
        assert r.status_code == 404

    def test_rate_requires_auth(self, http):
        r = http.post("/ai/tutor/rate", json={
            "session_id": str(uuid.uuid4()), "turn_index": 0, "rating": "up",
        })
        assert r.status_code in (401, 403)


# ---------------------- Super Admin AI Ops payload ----------------------


class TestAiOpsPayload:
    def test_ai_ops_contains_ratings_fields(self, http, super_admin_token):
        r = http.get("/admin/ai-ops?days=30", headers={"Authorization": f"Bearer {super_admin_token}"})
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data.get("summary") or {}
        # New rating keys must exist
        for key in ["ratings_up", "ratings_down", "ratings_total", "satisfaction_pct", "rating_coverage_pct"]:
            assert key in summary, f"missing {key} in ai-ops.summary — got {list(summary.keys())}"
        assert isinstance(summary["ratings_up"], int)
        assert isinstance(summary["ratings_down"], int)
        assert summary["ratings_total"] == summary["ratings_up"] + summary["ratings_down"]
        # satisfaction_pct is None if no ratings else numeric 0-100
        sp = summary["satisfaction_pct"]
        assert sp is None or (0 <= sp <= 100)
        # recent_negative_reasons is a list
        assert isinstance(data.get("recent_negative_reasons"), list)


# ---------------------- (D) LinkedIn share endpoints ----------------------


class TestShareEndpoints:
    def test_share_image_png(self, http):
        r = http.get(f"/certificates/{SAMPLE_CERT_ID}/share-image.png")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("image/png")
        # PNG magic bytes
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(r.content) > 5000, f"share PNG unexpectedly small: {len(r.content)} bytes"

    def test_share_image_404_for_unknown(self, http):
        r = http.get("/certificates/UNKNOWN-CERT-XYZ/share-image.png")
        assert r.status_code == 404

    def test_share_landing_html(self, http):
        r = http.get(f"/share/certificate/{SAMPLE_CERT_ID}")
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "text/html" in ct
        html = r.text
        # Open Graph
        assert 'property="og:image"' in html
        assert 'property="og:title"' in html
        assert 'property="og:description"' in html
        assert f"/api/certificates/{SAMPLE_CERT_ID}/share-image.png" in html
        # Twitter
        assert 'name="twitter:card"' in html
        assert 'summary_large_image' in html
        # Meta-refresh to /verify/{id}
        assert 'http-equiv="refresh"' in html
        assert f"/verify/{SAMPLE_CERT_ID}" in html

    def test_share_landing_404_for_unknown(self, http):
        r = http.get("/share/certificate/UNKNOWN-CERT-XYZ")
        assert r.status_code == 404


# ---------------------- Teardown / hygiene ----------------------


def teardown_module(_module):
    """Clean up the throw-away @example.com user we created."""
    if not SUPER_ADMIN_PASSWORD:
        return
    try:
        with httpx.Client(base_url=API, timeout=30.0) as c:
            r = c.post("/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
            if r.status_code != 200:
                return
            tok = r.json()["token"]
            head = {"Authorization": f"Bearer {tok}"}
            # sweep any TEST_it51 users (backend + UI created)
            u = c.get("/admin/users?q=TEST_it51", headers=head)
            if u.status_code == 200:
                for user in (u.json().get("users") or []):
                    c.delete(f"/admin/users/{user['id']}", headers=head)
    except Exception:
        pass
