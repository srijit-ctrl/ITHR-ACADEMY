"""Regression tests for the Feb 2026 content-audit fixes (iter 53).

Covers:
  * `status` field on GET /api/courses (list) and GET /api/courses/{slug} (detail).
  * `derive_status()` classification: 11 published + 17 coming_soon.
  * POST /api/courses/{coming_soon}/enroll → 409 with a helpful message.
  * POST /api/courses/{coming_soon}/waitlist → 200, idempotent.
  * Enrolling in a `published` course still works (no regression).
  * The "Landmark Case Studies" lesson now carries primary-source URLs.
"""
import os
import uuid

import pytest
import httpx

API_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not API_URL:
    # In-container fallback used by CI where the frontend .env isn't loaded.
    API_URL = "http://localhost:8001"


def _register(email: str) -> str:
    r = httpx.post(f"{API_URL}/api/auth/register", json={
        "email": email, "password": "TestPass123!", "full_name": "Iter53 Tester",
    }, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def learner_token() -> str:
    return _register(f"iter53-{uuid.uuid4().hex[:8]}@example.com")


def test_status_field_present_on_catalog_list():
    r = httpx.get(f"{API_URL}/api/courses", timeout=15)
    assert r.status_code == 200
    courses = r.json()
    assert isinstance(courses, list)
    assert len(courses) == 28
    for c in courses:
        assert "status" in c, f"{c['slug']} missing status field"
        assert c["status"] in ("published", "coming_soon")


def test_status_distribution_matches_data_quality():
    """A course is `published` iff it has real objectives AND ≥10 modules."""
    r = httpx.get(f"{API_URL}/api/courses", timeout=15)
    courses = r.json()
    published = [c for c in courses if c["status"] == "published"]
    coming = [c for c in courses if c["status"] == "coming_soon"]
    assert len(published) == 11, f"expected 11 published, got {len(published)}: {[c['slug'] for c in published]}"
    assert len(coming) == 17, f"expected 17 coming_soon, got {len(coming)}"
    # None of the coming-soon cards should be masquerading as full-content
    stub_slugs = {c["slug"] for c in coming}
    assert "chief-ai-officer-track" in stub_slugs
    assert "ai-change-management" in stub_slugs
    assert "generative-ai-executives" in stub_slugs


def test_status_field_on_detail_endpoint():
    r = httpx.get(f"{API_URL}/api/courses/chief-ai-officer-track", timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "coming_soon"

    r = httpx.get(f"{API_URL}/api/courses/agentic-ai-foundations", timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_enroll_refused_for_coming_soon(learner_token):
    r = httpx.post(
        f"{API_URL}/api/courses/chief-ai-officer-track/enroll",
        headers={"Authorization": f"Bearer {learner_token}"},
        timeout=15,
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "waitlist" in detail.lower()


def test_waitlist_endpoint_idempotent(learner_token):
    hdr = {"Authorization": f"Bearer {learner_token}"}
    r1 = httpx.post(f"{API_URL}/api/courses/ai-change-management/waitlist", headers=hdr, timeout=15)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["already_joined"] is False
    joined_at_first = body1["joined_at"]

    r2 = httpx.post(f"{API_URL}/api/courses/ai-change-management/waitlist", headers=hdr, timeout=15)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["already_joined"] is True
    assert body2["joined_at"] == joined_at_first  # Timestamp of the ORIGINAL insert


def test_waitlist_refused_for_published_course(learner_token):
    r = httpx.post(
        f"{API_URL}/api/courses/agentic-ai-foundations/waitlist",
        headers={"Authorization": f"Bearer {learner_token}"},
        timeout=15,
    )
    assert r.status_code == 400
    assert "already live" in r.json()["detail"]


def test_enroll_still_works_for_published_course():
    # Fresh learner to avoid contaminating the module-scoped fixture user.
    token = _register(f"iter53-enroll-{uuid.uuid4().hex[:8]}@example.com")
    r = httpx.post(
        f"{API_URL}/api/courses/agentic-ai-foundations/enroll",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json().get("enrollment_id")


def test_landmark_case_studies_lesson_has_citations():
    r = httpx.get(f"{API_URL}/api/courses/agentic-ai-foundations", timeout=15)
    assert r.status_code == 200
    course = r.json()
    landmark = None
    for module in course["modules"]:
        for lesson in module["lessons"]:
            if "Landmark" in lesson["title"]:
                landmark = lesson
                break
        if landmark:
            break
    assert landmark, "Landmark Case Studies lesson not found in agentic-ai-foundations"
    content = landmark["content"]
    assert "klarna.com/international/press" in content, "Klarna citation missing"
    assert "anthropic.com" in content, "Anthropic citation missing"
    assert "salesforce.com/news/press-releases" in content, "Salesforce citation missing"
    assert "vendor-reported" in content, "Editorial caveat missing"
