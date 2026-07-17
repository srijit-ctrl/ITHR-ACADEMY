"""Iteration 44 — Super-Admin dashboard cleanup verification.

Verifies:
  1. GET /api/admin/alerts returns only real signals (no id starts with 'stub-'
     and no license-expiry / storage-threshold stub entries).
  2. GET /api/admin/dashboard returns kpis.revenue_total and NOT mock_revenue_total.
  3. GET /api/courses returns 28 courses.
  4. Spot-checking 3 course details, every lesson content length >= 1200 chars.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SUPER_ADMIN_EMAIL = "superadmin@ithr.online"
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def superadmin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
    assert r.status_code == 200, f"Super-admin login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(superadmin_token):
    return {"Authorization": f"Bearer {superadmin_token}"}


# ---------- ALERTS ----------
def test_alerts_no_stub_entries(api, admin_headers):
    r = api.get(f"{BASE_URL}/api/admin/alerts", headers=admin_headers)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert "alerts" in body
    alerts = body["alerts"]
    # No alert may declare stubbed:true, and none of the removed IDs may reappear.
    forbidden_ids = {"license-expiry", "storage-threshold"}
    for a in alerts:
        assert not a.get("stubbed"), f"Found stubbed alert: {a}"
        assert a["id"] not in forbidden_ids, f"Removed stub alert reappeared: {a}"
        assert not a["id"].startswith("stub-"), f"Stub id present: {a}"


# ---------- DASHBOARD KPI ----------
def test_dashboard_revenue_rename(api, admin_headers):
    r = api.get(f"{BASE_URL}/api/admin/dashboard", headers=admin_headers)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert "kpis" in body, body
    k = body["kpis"]
    assert "revenue_total" in k, f"revenue_total missing: {k}"
    assert "mock_revenue_total" not in k, f"Legacy mock_revenue_total still present: {k}"
    assert isinstance(k["revenue_total"], (int, float))
    # Also validate other kpis exist
    for field in ("total_users", "active_7d", "active_30d", "enrollments_total", "exam_pass_rate", "llm_key_health"):
        assert field in k, f"missing kpi field {field}"


# ---------- COURSES ----------
def test_courses_count(api):
    r = api.get(f"{BASE_URL}/api/courses")
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    courses = body.get("courses") if isinstance(body, dict) else body
    assert isinstance(courses, list), f"Unexpected courses payload: {type(body)}"
    assert len(courses) == 28, f"Expected 28 courses, got {len(courses)}"


@pytest.mark.parametrize("slug", ["agentic-ai-healthcare", "agentic-ai-retail", "multi-agent-systems"])
def test_course_lesson_content_length(api, slug):
    r = api.get(f"{BASE_URL}/api/courses/{slug}")
    assert r.status_code == 200, f"{slug}: {r.status_code} {r.text}"
    course = r.json()
    modules = course.get("modules", [])
    assert modules, f"No modules for {slug}"
    lesson_count = 0
    short_lessons = []
    for m in modules:
        for lesson in m.get("lessons", []):
            lesson_count += 1
            content = lesson.get("content", "") or ""
            if len(content) < 1200:
                short_lessons.append({
                    "module": m.get("title"),
                    "lesson": lesson.get("title"),
                    "len": len(content),
                })
    assert lesson_count > 0, f"No lessons found in {slug}"
    assert not short_lessons, f"{slug}: {len(short_lessons)} lessons < 1200 chars: {short_lessons[:3]}"
