"""Iteration 42 — deployment-fix verification smoke tests.

Covers:
 - /api/health
 - superadmin login (JWT)
 - courses list (>=28)
 - agentic-ai-banking has modules with lesson content
 - sample certificate PDF
"""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://enterprise-agent-dev.preview.emergentagent.com").rstrip("/")
SUPER_EMAIL = "superadmin@ithr.online"
SUPER_PWD = os.environ.get("SUPER_ADMIN_PASSWORD", "")


def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "healthy"


def test_superadmin_login_returns_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_EMAIL, "password": SUPER_PWD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # token key may be access_token or token
    token = data.get("access_token") or data.get("token")
    assert token and isinstance(token, str) and len(token) > 20
    user = data.get("user") or {}
    assert user.get("role") == "super_admin" or user.get("email") == SUPER_EMAIL


def test_courses_list_has_28():
    r = requests.get(f"{BASE_URL}/api/courses", timeout=30)
    assert r.status_code == 200
    data = r.json()
    courses = data if isinstance(data, list) else data.get("courses") or data.get("items") or []
    assert isinstance(courses, list)
    assert len(courses) >= 28, f"expected >=28 courses, got {len(courses)}"


def test_agentic_ai_banking_course_has_rich_modules():
    r = requests.get(f"{BASE_URL}/api/courses/agentic-ai-banking", timeout=30)
    assert r.status_code == 200
    data = r.json()
    modules = data.get("modules") or []
    assert len(modules) > 0, "no modules on agentic-ai-banking"
    # Verify at least one module has lessons with content/body
    found_content = False
    for m in modules:
        lessons = m.get("lessons") or []
        for lesson in lessons:
            body = lesson.get("content") or lesson.get("body") or lesson.get("markdown") or ""
            if isinstance(body, str) and len(body) > 100:
                found_content = True
                break
        if found_content:
            break
    assert found_content, "no lesson has rich content (>100 chars)"


def test_sample_certificate_pdf():
    r = requests.get(f"{BASE_URL}/api/certificates/SAMPLE-ITHR-2026-001/pdf", timeout=60)
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "application/pdf" in ctype, f"unexpected content-type: {ctype}"
    # PDF signature %PDF
    assert r.content[:4] == b"%PDF", "response body is not a PDF"
    assert len(r.content) > 1000
