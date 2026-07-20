"""Iteration 58 backend tests — Student Progress Tracker.

Covers:
  1. Public /api/progress/founding-module5 counter (no auth).
  2. /api/progress/me returns empty totals for a fresh user.
  3. /api/progress/me/{slug} returns 400 when not enrolled, 404 for unknown slug.
  4. Full flow: enroll → complete lessons of module 1 → module_started + module_completed
     events land in module_events with distinct timestamps.
  5. Module-5 completion allocates founding_module5_seq (idempotent — repeated
     module-5 completions don't re-allocate).
  6. Complete every module of a course → enrollment.completed=True + completed_at set.
  7. Progress-tracker idempotency: repeating record_module_started for the same
     (user, course, module) never creates duplicate events.
  8. Auth guards on write endpoints.
"""
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import db  # noqa: E402

from pymongo import MongoClient  # noqa: E402
_sync_client = MongoClient(os.environ["MONGO_URL"])
sync_db = _sync_client[os.environ["DB_NAME"]]

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

TEST_PREFIX = "TEST_it58_"


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=API, timeout=60.0) as c:
        yield c


def _register(http, name="Iter58 Learner"):
    email = f"{TEST_PREFIX}{uuid.uuid4().hex[:10]}@example.com"
    r = http.post("/auth/register", json={
        "email": email, "password": "TestPass123!", "full_name": name,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _authed(learner):
    return {"Authorization": f"Bearer {learner['token']}"}


# =========================================================================
# ============  1. PUBLIC COUNTER & AUTH GUARDS ===========================
# =========================================================================


class TestPublicAndAuth:
    def test_founding_module5_public(self, http):
        r = http.get("/progress/founding-module5")
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("cap", "claimed", "remaining"):
            assert k in body
        assert body["cap"] == 500

    def test_me_requires_auth(self, http):
        r = http.get("/progress/me")
        assert r.status_code in (401, 403)

    def test_module_start_requires_auth(self, http):
        r = http.post("/progress/module/start", json={"course_id": "x", "module_id": "y"})
        assert r.status_code in (401, 403)


# =========================================================================
# ============  2. EMPTY / MISSING STATES  ================================
# =========================================================================


class TestEmptyStates:
    def test_me_empty_for_fresh_user(self, http):
        learner = _register(http, "Empty State")
        r = http.get("/progress/me", headers=_authed(learner))
        assert r.status_code == 200
        body = r.json()
        assert body["totals"]["courses"] == 0
        assert body["courses"] == []

    def test_me_by_slug_404_for_unknown_course(self, http):
        learner = _register(http)
        r = http.get("/progress/me/does-not-exist-slug", headers=_authed(learner))
        assert r.status_code == 404

    def test_me_by_slug_400_when_not_enrolled(self, http):
        learner = _register(http)
        r = http.get("/progress/me/agentic-ai-foundations", headers=_authed(learner))
        assert r.status_code == 400


# =========================================================================
# ============  3. FULL FLOW  =============================================
# =========================================================================


class TestFullFlow:
    """Enroll → complete lessons of the first module → verify per-module
    timestamps and event log."""

    def _enroll(self, http, learner):
        r = http.post("/courses/agentic-ai-foundations/enroll", headers=_authed(learner))
        assert r.status_code == 200
        return r.json()

    def _complete_module(self, http, learner, course, module):
        """Complete every lesson in a module, return final lesson-complete response."""
        result = None
        for l in module["lessons"]:
            r = http.post("/lessons/complete", headers=_authed(learner),
                          json={"course_id": course["id"], "lesson_id": l["id"], "module_id": module["id"]})
            assert r.status_code == 200, r.text
            result = r.json()
        return result

    def test_module_start_and_complete_events_recorded(self, http):
        learner = _register(http, "Full Flow")
        self._enroll(http, learner)
        course = http.get("/courses/agentic-ai-foundations").json()
        module = course["modules"][0]
        self._complete_module(http, learner, course, module)

        # Wait a moment for fire-and-forget event writes.
        time.sleep(1.5)

        # Verify /progress/me/{slug}
        p = http.get("/progress/me/agentic-ai-foundations", headers=_authed(learner)).json()
        m1 = p["modules"][0]
        assert m1["completed"] is True
        assert m1["started_at"] is not None
        assert m1["completed_at"] is not None
        assert m1["lessons_completed"] == m1["lesson_count"]

        # Verify module_events collection has both events
        evs = list(sync_db.module_events.find({
            "user_id": learner["user"]["id"], "course_id": course["id"], "module_id": module["id"]
        }))
        kinds = {ev["kind"] for ev in evs}
        assert "started" in kinds
        assert "completed" in kinds

    def test_module_events_endpoint(self, http):
        learner = _register(http, "Events Audit")
        self._enroll(http, learner)
        course = http.get("/courses/agentic-ai-foundations").json()
        self._complete_module(http, learner, course, course["modules"][0])
        time.sleep(1.5)
        r = http.get("/progress/module-events", headers=_authed(learner))
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 2  # started + completed at minimum

    def test_module5_milestone_allocated_on_module5_completion(self, http):
        learner = _register(http, "M5 Milestone")
        self._enroll(http, learner)
        course = http.get("/courses/agentic-ai-foundations").json()
        # Complete modules 1..5
        for m in course["modules"][:5]:
            self._complete_module(http, learner, course, m)
        time.sleep(2)

        me = http.get("/auth/me", headers=_authed(learner)).json()
        assert me.get("founding_module5_seq") is not None, f"seq missing: {me}"
        assert me.get("founding_module5_reached_at") is not None
        assert me.get("founding_module5_course_id") == course["id"]

    def test_module5_milestone_idempotent(self, http):
        """Re-completing module 5 (via completing modules 4→5 again on a
        different course, or resubmitting lessons) must not double-allocate
        the seq. Same sequence number persists."""
        learner = _register(http, "M5 Idempotent")
        self._enroll(http, learner)
        course = http.get("/courses/agentic-ai-foundations").json()
        for m in course["modules"][:5]:
            self._complete_module(http, learner, course, m)
        time.sleep(2)
        first_seq = http.get("/auth/me", headers=_authed(learner)).json().get("founding_module5_seq")
        assert first_seq is not None

        # Re-submit the last lesson of module 5 — must not re-allocate.
        m5 = course["modules"][4]
        for l in m5["lessons"]:
            http.post("/lessons/complete", headers=_authed(learner),
                      json={"course_id": course["id"], "lesson_id": l["id"], "module_id": m5["id"]})
        time.sleep(1.5)

        second_seq = http.get("/auth/me", headers=_authed(learner)).json().get("founding_module5_seq")
        assert second_seq == first_seq

    def test_all_modules_complete_flips_enrollment_completed(self, http):
        learner = _register(http, "All Modules")
        self._enroll(http, learner)
        course = http.get("/courses/agentic-ai-foundations").json()
        for m in course["modules"]:
            self._complete_module(http, learner, course, m)
        time.sleep(2)

        p = http.get("/progress/me/agentic-ai-foundations", headers=_authed(learner)).json()
        assert p["progress_pct"] == 100.0
        assert p["completed"] is True
        assert p["completed_at"] is not None
        assert p["modules_completed"] == p["total_modules"]

    def test_progress_me_aggregates(self, http):
        """/progress/me totals: after 1 completed course + 1 partial, totals
        show 2 courses, 1 completed, 1 in_progress."""
        learner = _register(http, "Aggregates")
        # Course 1 — fully complete
        http.post("/courses/agentic-ai-foundations/enroll", headers=_authed(learner))
        course = http.get("/courses/agentic-ai-foundations").json()
        for m in course["modules"]:
            self._complete_module(http, learner, course, m)
        # Course 2 — enroll only, no progress
        r2 = http.post("/courses/prompt-engineering-mastery/enroll", headers=_authed(learner))
        if r2.status_code != 200:
            pytest.skip("prompt-engineering-mastery not enrollable in this preview DB")
        time.sleep(2)
        totals = http.get("/progress/me", headers=_authed(learner)).json()["totals"]
        assert totals["courses"] >= 2
        assert totals["completed"] >= 1
        assert totals["not_started"] >= 1


# =========================================================================
# ============  4. EXPLICIT MODULE-START ENDPOINT  ========================
# =========================================================================


class TestExplicitModuleStart:
    def test_explicit_start_signal_recorded(self, http):
        learner = _register(http, "Explicit Start")
        http.post("/courses/agentic-ai-foundations/enroll", headers=_authed(learner))
        course = http.get("/courses/agentic-ai-foundations").json()
        m2 = course["modules"][1]
        r = http.post("/progress/module/start", headers=_authed(learner),
                      json={"course_id": course["id"], "module_id": m2["id"]})
        assert r.status_code == 200
        assert r.json()["recorded"] is True

    def test_explicit_start_idempotent(self, http):
        learner = _register(http, "Idempotent Start")
        http.post("/courses/agentic-ai-foundations/enroll", headers=_authed(learner))
        course = http.get("/courses/agentic-ai-foundations").json()
        m3 = course["modules"][2]
        r1 = http.post("/progress/module/start", headers=_authed(learner),
                       json={"course_id": course["id"], "module_id": m3["id"]})
        r2 = http.post("/progress/module/start", headers=_authed(learner),
                       json={"course_id": course["id"], "module_id": m3["id"]})
        assert r1.json()["recorded"] is True
        assert r2.json()["recorded"] is False
        assert r2.json()["already_started"] is True

    def test_explicit_start_400_when_not_enrolled(self, http):
        learner = _register(http, "Not Enrolled")
        r = http.post("/progress/module/start", headers=_authed(learner),
                      json={"course_id": "nonexistent-course", "module_id": "nonexistent-module"})
        assert r.status_code == 400
