"""Iteration 73 — In-portal PDF viewer + course-completion (28 courses × 15 modules).

Covers:
  * GET /api/courses returns 28 courses, each with exactly 15 modules.
  * The regenerated course 'agentic-ai-learning-development' has 15 modules
    (1..15) with non-empty lessons, published status, has_full_content True,
    5 learning_objectives, 7 skills_gained.
  * PDF preview endpoint contract for prompt-engineering-mastery deck:
      - 401 anonymous
      - 403 authed but not enrolled
      - 200 application/pdf + %PDF magic when enrolled
      - 404 for unknown slug
      - 404 for unknown filename on real course
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

TARGET_SLUG = "prompt-engineering-mastery"
TARGET_FILENAME = "prompt-engineering-mastery-deck.pptx"
REGEN_SLUG = "agentic-ai-learning-development"


# --- fixtures --------------------------------------------------------------

@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _register(session, tag):
    email = f"qa_iter73_{tag}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "email": email,
        "password": "TestPass123!",
        "full_name": f"QA Iter73 {tag}",
    }
    r = session.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token, f"no token in register response: {r.json()}"
    return email, token


@pytest.fixture(scope="module")
def enrolled_token(http):
    """Register + enroll in prompt-engineering-mastery."""
    _, token = _register(http, "enr")
    r = http.post(
        f"{API}/courses/{TARGET_SLUG}/enroll",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"enroll failed: {r.status_code} {r.text}"
    return token


@pytest.fixture(scope="module")
def non_enrolled_token(http):
    _, token = _register(http, "noenr")
    return token


# --- Content completeness --------------------------------------------------

class TestCourseCatalogCompleteness:
    def test_28_courses_each_with_15_modules(self, http):
        r = http.get(f"{API}/courses", timeout=30)
        assert r.status_code == 200
        courses = r.json()
        if isinstance(courses, dict):
            courses = courses.get("courses") or courses.get("items") or []
        assert isinstance(courses, list), f"unexpected shape: {type(courses)}"
        assert len(courses) == 28, f"expected 28 courses, got {len(courses)}"

        # List endpoint returns module_count (not full modules array)
        bad = []
        for c in courses:
            mc = c.get("module_count")
            if mc != 15:
                bad.append((c.get("slug"), mc))
        assert not bad, f"courses without 15 modules (module_count): {bad}"

        # has_full_content must be True on ALL 28 published courses
        no_full = [c.get("slug") for c in courses if not c.get("has_full_content")]
        assert not no_full, f"courses with has_full_content falsy: {no_full}"

    def test_regenerated_course_details(self, http):
        r = http.get(f"{API}/courses/{REGEN_SLUG}", timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c.get("slug") == REGEN_SLUG
        assert c.get("status") == "published", f"status={c.get('status')}"

        mods = c.get("modules") or []
        assert len(mods) == 15, f"expected 15 modules, got {len(mods)}"

        # numbered 1..15 via 'number' field
        numbers = [m.get("number") for m in mods]
        assert numbers == list(range(1, 16)), f"module numbering not 1..15: {numbers}"

        # each module has non-empty lessons
        empty = [m.get("title") for m in mods if not (m.get("lessons") or [])]
        assert not empty, f"modules with empty lessons: {empty}"

        # 5 learning_objectives, 7 skills_gained
        assert len(c.get("learning_objectives") or []) == 5, (
            f"learning_objectives count={len(c.get('learning_objectives') or [])}"
        )
        assert len(c.get("skills_gained") or []) == 7, (
            f"skills_gained count={len(c.get('skills_gained') or [])}"
        )

    def test_regenerated_course_has_full_content_flag(self, http):
        """has_full_content is only exposed on the list endpoint."""
        r = http.get(f"{API}/courses", timeout=30)
        assert r.status_code == 200
        courses = r.json()
        target = next((c for c in courses if c.get("slug") == REGEN_SLUG), None)
        assert target is not None, f"{REGEN_SLUG} missing from /api/courses"
        assert target.get("has_full_content") is True, (
            f"has_full_content={target.get('has_full_content')}"
        )
        assert target.get("module_count") == 15


# --- PDF viewer contract ---------------------------------------------------

class TestPdfViewerContract:
    def _preview_url(self, slug=TARGET_SLUG, filename=TARGET_FILENAME):
        return f"{API}/courses/{slug}/resources/{filename}/preview.pdf"

    def test_anonymous_returns_401(self, http):
        r = http.get(self._preview_url(), timeout=30)
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text[:200]}"

    def test_non_enrolled_returns_403(self, http, non_enrolled_token):
        r = http.get(
            self._preview_url(),
            headers={"Authorization": f"Bearer {non_enrolled_token}"},
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_enrolled_returns_pdf(self, http, enrolled_token):
        r = http.get(
            self._preview_url(),
            headers={"Authorization": f"Bearer {enrolled_token}"},
            timeout=60,
        )
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text[:200]}"
        ctype = r.headers.get("Content-Type", "")
        assert ctype.startswith("application/pdf"), f"unexpected Content-Type: {ctype}"
        body = r.content
        assert body[:4] == b"%PDF", f"body doesn't start with %PDF magic: {body[:16]!r}"
        assert len(body) > 100_000, f"PDF suspiciously small: {len(body)} bytes"

    def test_unknown_slug_returns_404(self, http, enrolled_token):
        r = http.get(
            f"{API}/courses/definitely-not-a-course-xyz/resources/{TARGET_FILENAME}/preview.pdf",
            headers={"Authorization": f"Bearer {enrolled_token}"},
            timeout=30,
        )
        assert r.status_code == 404, f"expected 404 got {r.status_code}"

    def test_unknown_filename_on_real_course_returns_404(self, http, enrolled_token):
        r = http.get(
            f"{API}/courses/{TARGET_SLUG}/resources/no-such-file.pptx/preview.pdf",
            headers={"Authorization": f"Bearer {enrolled_token}"},
            timeout=30,
        )
        assert r.status_code == 404, f"expected 404 got {r.status_code}"
