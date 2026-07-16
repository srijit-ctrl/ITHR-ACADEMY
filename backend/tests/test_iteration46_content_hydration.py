"""Iteration 46 — Course content hydration + hero contrast fix + paths regression.

Verifies:
- All 7 target courses have >=12 lessons with content >=1200 chars + 15+ Q quiz.
- Both key learning paths ('AI-Ready Executive' + 'Agentic Engineer') resolve to
  courses that ALL have has_full_content=True.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ithr-agentic-hub.preview.emergentagent.com").rstrip("/")


CONTENT_TARGET_SLUGS = [
    "generative-ai-executives",
    "llm-architecture-deep-dive",
    "ai-security-red-team",
    "agentic-ai-hospitality",
    "ai-product-management",
    "ai-change-management",
    "vector-databases",
]


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- Content richness ----------------
@pytest.mark.parametrize("slug", CONTENT_TARGET_SLUGS)
def test_course_has_rich_content(api, slug):
    r = api.get(f"{BASE_URL}/api/courses/{slug}")
    assert r.status_code == 200, f"{slug} failed to fetch: {r.status_code}"
    d = r.json()
    modules = d.get("modules", [])
    lessons = [l for m in modules for l in m.get("lessons", [])]
    assert len(lessons) >= 12, f"{slug}: expected >=12 lessons, got {len(lessons)}"
    short = [(l.get("title", ""), len(l.get("content", "") or "")) for l in lessons]
    too_short = [t for t in short if t[1] < 1200]
    assert not too_short, f"{slug}: lessons under 1200 chars: {too_short[:3]}"
    quiz = d.get("quiz", [])
    assert len(quiz) >= 15, f"{slug}: expected >=15 quiz questions, got {len(quiz)}"


# ---------------- Learning paths ----------------
def test_paths_list_has_key_paths(api):
    r = api.get(f"{BASE_URL}/api/paths")
    assert r.status_code == 200
    data = r.json()
    slugs = {p["slug"] for p in data["paths"]}
    assert "executive-cxo" in slugs, "AI-Ready Executive path missing"
    assert "engineer-agentic" in slugs, "Agentic Engineer path missing"


@pytest.mark.parametrize("path_slug,expected_title", [
    ("executive-cxo", "AI-Ready Executive"),
    ("engineer-agentic", "Agentic Engineer"),
])
def test_path_courses_all_have_content(api, path_slug, expected_title):
    r = api.get(f"{BASE_URL}/api/paths/{path_slug}")
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == expected_title
    courses = d.get("courses", [])
    assert len(courses) == len(d["course_slugs"]), f"{path_slug}: some slugs did not resolve"
    empty = [c["slug"] for c in courses if not c.get("has_full_content")]
    assert not empty, f"{path_slug}: courses without content: {empty}"


# ---------------- List endpoint sanity ----------------
def test_courses_list_all_have_full_content(api):
    r = api.get(f"{BASE_URL}/api/courses")
    assert r.status_code == 200
    courses = r.json()
    assert len(courses) >= 20
    empty = [c["slug"] for c in courses if not c.get("has_full_content")]
    assert not empty, f"Courses with has_full_content=False: {empty}"
