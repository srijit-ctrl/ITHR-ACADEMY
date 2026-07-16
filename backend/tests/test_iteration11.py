"""Iteration 11 regression tests — security headers + MD5→SHA-256 + __import__ removal.

Verifies no functional regressions from code-review remediation.
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://ithr-agentic-hub.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

# ------------------------------ Security headers ------------------------------

REQUIRED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": None,          # presence-only
    "strict-transport-security": None,   # presence-only
    "content-security-policy": None,     # presence-only, we spot-check tokens
}


@pytest.mark.parametrize("path", ["/api/courses", "/api/intelligence/briefing"])
def test_security_headers_on_api(path):
    r = requests.get(f"{BASE_URL}{path}", timeout=15)
    assert r.status_code == 200, r.text[:200]
    for hdr, expected in REQUIRED_HEADERS.items():
        assert hdr in r.headers, f"missing header {hdr}"
        if expected:
            assert r.headers[hdr] == expected, (
                f"{hdr}={r.headers[hdr]!r} expected {expected!r}"
            )
    csp = r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


# ------------------------------ MD5 → SHA-256 no regression ------------------------------

def test_courses_seeded_with_freshness():
    r = requests.get(f"{API}/courses", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 24, f"expected 24 seeded courses, got {len(data)}"
    sample = data[0]
    for k in ("freshness_score", "last_reviewed_at", "days_since_review"):
        assert k in sample, f"missing freshness field {k}"


def test_assessment_questions_bank_size():
    """Assessment router uses SHA-256 for stable question IDs now.
    Bank must still return >=15 questions per course."""
    slug = "agentic-ai-foundations"
    r = requests.get(f"{API}/courses/{slug}", timeout=15)
    assert r.status_code == 200
    course = r.json()
    # Full assessment bank lives inside the course doc as quiz
    assert len(course.get("quiz", [])) >= 15, f"quiz={len(course.get('quiz', []))}"


# ------------------------------ Auth helper ------------------------------

def _register(session, tag="i11"):
    email = f"test.learner+{tag}-{int(time.time()*1000)}@example.com"
    r = session.post(f"{API}/auth/register", json={
        "email": email,
        "password": "TestPass123!Strong",
        "full_name": "Iter11 Tester",
        "organization": "Test Corp",
        "title": "Analyst",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------ Recommendation cache (SHA-256 cache key) ------------------------------

def test_recommendation_next_best_cache():
    s = requests.Session()
    auth = _register(s, "reccache")
    headers = {"Authorization": f"Bearer {auth['token']}"}

    r1 = s.get(f"{API}/recommendations/next-best", headers=headers, timeout=30)
    assert r1.status_code == 200
    d1 = r1.json()
    # Response wraps rec under "recommendation"
    rec1 = d1.get("recommendation", d1)
    assert "rationale" in rec1, d1

    r2 = s.get(f"{API}/recommendations/next-best", headers=headers, timeout=30)
    assert r2.status_code == 200
    d2 = r2.json()
    rec2 = d2.get("recommendation", d2)
    assert "rationale" in rec2
    # Same user + same next course → same rationale (cache hit produces identical text)
    slug1 = rec1.get("course", {}).get("slug")
    slug2 = rec2.get("course", {}).get("slug")
    if slug1 and slug1 == slug2:
        assert rec1["rationale"] == rec2["rationale"], "cache should return identical rationale"


# ------------------------------ Enterprise router — uuid top-of-file works ------------------------------

def test_enterprise_create_org_returns_hex_id():
    s = requests.Session()
    auth = _register(s, "entorg")
    headers = {"Authorization": f"Bearer {auth['token']}"}
    r = s.post(
        f"{API}/enterprise/organizations",
        headers=headers,
        json={"name": "Iter11 Test Org", "seat_count": 10},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    org = r.json()["organization"]
    assert "id" in org
    # Must be a valid UUID (either hex-32 or dashed-36 form)
    import uuid as _uuid
    _uuid.UUID(org["id"])  # raises ValueError if not valid


def test_enterprise_create_invite_returns_hex_id():
    """Ensures uuid.uuid4().hex still works in the invite path (which was previously via __import__)."""
    s = requests.Session()
    auth = _register(s, "entinv")
    headers = {"Authorization": f"Bearer {auth['token']}"}
    r = s.post(
        f"{API}/enterprise/organizations",
        headers=headers,
        json={"name": "Iter11 Invite Org", "seat_count": 10},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    r2 = s.post(
        f"{API}/enterprise/organizations/invites",
        headers=headers,
        json={"email": "invitee@example.com"},
        timeout=15,
    )
    assert r2.status_code == 200, r2.text
    inv_resp = r2.json()
    invite = inv_resp.get("invite", inv_resp)
    assert "id" in invite
    # invite ids are uuid.uuid4().hex (32 chars) — validates __import__ removal worked
    assert len(invite["id"]) == 32, f"invite id={invite['id']!r}"


# ------------------------------ Passport router — defensive filter still returns 200 ------------------------------

def test_passport_me_returns_200():
    s = requests.Session()
    auth = _register(s, "passport")
    headers = {"Authorization": f"Bearer {auth['token']}"}
    r = s.get(f"{API}/passport/me", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()
    # Passport schema is flat: passport_slug, full_name, certificates, ...
    for k in ("passport_slug", "full_name", "certificates"):
        assert k in p, f"missing {k}: {list(p.keys())}"
    assert isinstance(p["certificates"], list)


def test_passport_public_by_slug():
    """After creating a passport /me, the returned slug should resolve publicly."""
    s = requests.Session()
    auth = _register(s, "passpub")
    headers = {"Authorization": f"Bearer {auth['token']}"}
    me = s.get(f"{API}/passport/me", headers=headers, timeout=15).json()
    slug = me["passport_slug"]
    r = requests.get(f"{API}/passport/{slug}", timeout=15)  # public, no auth
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("passport_slug") == slug
    assert "certificates" in body
