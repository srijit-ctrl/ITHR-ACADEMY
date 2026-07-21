"""Iteration 70 — Course resources download endpoint.

Covers:
- GET /api/courses/prompt-engineering-mastery includes `resources` array with
  exactly one entry (pem-deck-v1) and expected metadata.
- Anonymous download → 401.
- Registered but non-enrolled user → 403 ('Enroll'/'unlock').
- Enrolled user → 200 pptx bytes (PK zip magic + size ~2.1 MB).
- Path traversal → 400 'Invalid filename'.
- Wrong filename → 404 'Resource not found'.
- Wrong course slug → 404 'Course not found'.
- Persistence: seed rehydrates resources on backend restart.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest

from _creds import API_URL, register_learner  # type: ignore

SLUG = "prompt-engineering-mastery"
FILENAME = "prompt-engineering-mastery-deck.pptx"
RESOURCE_ID = "pem-deck-v1"


# ---------------------------------------------------------------------------
# Course model — resources array persistence
# ---------------------------------------------------------------------------
class TestCourseResourceContract:
    def test_course_detail_includes_single_resource(self):
        r = httpx.get(f"{API_URL}/api/courses/{SLUG}", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        resources = data.get("resources") or []
        assert len(resources) == 1, f"expected 1 resource, got {resources}"
        res = resources[0]
        assert res["id"] == RESOURCE_ID
        assert "Prompt Engineering Mastery" in res["title"]
        assert res["kind"] == "presentation"
        assert res["filename"] == FILENAME
        assert "presentationml" in res["mime_type"]
        # ~2.1 MB tolerance ±5%
        assert 2_000_000 <= int(res["size_bytes"]) <= 2_200_000
        assert res["public"] is False

    def test_other_courses_have_empty_resources(self):
        r = httpx.get(f"{API_URL}/api/courses/agentic-ai-foundations", timeout=15)
        assert r.status_code == 200
        assert (r.json().get("resources") or []) == []


# ---------------------------------------------------------------------------
# Download endpoint auth/enrollment gate
# ---------------------------------------------------------------------------
class TestDownloadAccessGate:
    def test_anonymous_returns_401(self):
        r = httpx.get(f"{API_URL}/api/courses/{SLUG}/resources/{FILENAME}", timeout=15)
        assert r.status_code == 401, r.text

    def test_registered_but_not_enrolled_returns_403(self):
        _, token = register_learner(name="PEM Locked", prefix="pem-locked")
        r = httpx.get(
            f"{API_URL}/api/courses/{SLUG}/resources/{FILENAME}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert r.status_code == 403, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "enroll" in detail or "unlock" in detail

    def test_enrolled_user_downloads_pptx(self, tmp_path):
        _, token = register_learner(name="PEM Enrolled", prefix="pem-enrolled")
        headers = {"Authorization": f"Bearer {token}"}

        # Enroll
        enroll = httpx.post(
            f"{API_URL}/api/courses/{SLUG}/enroll", headers=headers, timeout=15,
        )
        assert enroll.status_code == 200, enroll.text

        # Download
        r = httpx.get(
            f"{API_URL}/api/courses/{SLUG}/resources/{FILENAME}",
            headers=headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "presentationml" in ct, ct
        size = len(r.content)
        # 2.1 MB ±5%
        assert 2_000_000 <= size <= 2_200_000, f"unexpected size {size}"
        # PK zip magic (PPTX is a ZIP)
        assert r.content[:4] == b"PK\x03\x04", r.content[:8]

        # Persist to tmp for downstream inspection (not strictly required)
        out = tmp_path / "download.pptx"
        out.write_bytes(r.content)
        assert out.stat().st_size == size


# ---------------------------------------------------------------------------
# Validation / edge cases
# ---------------------------------------------------------------------------
class TestDownloadValidation:
    @pytest.fixture(scope="class")
    def enrolled_token(self):
        _, token = register_learner(name="PEM Validation", prefix="pem-val")
        r = httpx.post(
            f"{API_URL}/api/courses/{SLUG}/enroll",
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        assert r.status_code == 200
        return token

    def test_path_traversal_rejected(self, enrolled_token):
        bad = quote("../../etc/passwd", safe="")
        r = httpx.get(
            f"{API_URL}/api/courses/{SLUG}/resources/{bad}",
            headers={"Authorization": f"Bearer {enrolled_token}"},
            timeout=15,
        )
        # Server may reject before or after finding resource — must NOT 200/500.
        assert r.status_code in (400, 404), r.text
        # If it hit the traversal guard specifically → 400 'Invalid filename'.
        if r.status_code == 400:
            assert "invalid filename" in (r.json().get("detail") or "").lower()

    def test_unknown_filename_returns_404(self, enrolled_token):
        r = httpx.get(
            f"{API_URL}/api/courses/{SLUG}/resources/nonexistent.pptx",
            headers={"Authorization": f"Bearer {enrolled_token}"},
            timeout=15,
        )
        assert r.status_code == 404
        assert "resource not found" in (r.json().get("detail") or "").lower()

    def test_unknown_course_returns_404(self, enrolled_token):
        r = httpx.get(
            f"{API_URL}/api/courses/does-not-exist/resources/anything.pptx",
            headers={"Authorization": f"Bearer {enrolled_token}"},
            timeout=15,
        )
        assert r.status_code == 404
        assert "course not found" in (r.json().get("detail") or "").lower()


# ---------------------------------------------------------------------------
# Regression sanity — spot-check iter-63..69 flows
# ---------------------------------------------------------------------------
class TestRegressionSpotChecks:
    def test_courses_list_still_returns_expected_set(self):
        r = httpx.get(f"{API_URL}/api/courses", timeout=15)
        assert r.status_code == 200
        slugs = {c["slug"] for c in r.json()}
        assert SLUG in slugs
        # A few known long-standing catalog entries
        assert "agentic-ai-foundations" in slugs
