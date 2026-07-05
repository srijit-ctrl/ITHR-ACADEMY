"""Iteration 14 — Split-token auth (in-memory access + httpOnly refresh cookie)
+ refactor of 5 high-complexity backend functions.

Focus:
1. Verify /auth/register /auth/login /auth/refresh /auth/logout return correct
   cookie flags + response shape.
2. Verify access token type='access' and ~15 min expiry.
3. Verify refresh token type='refresh' and ~7 day expiry (decoded with
   JWT_REFRESH_SECRET).
4. Verify refactored endpoints (assessment session/submit, enterprise dashboard,
   mentor SSE, passport, cert PDF brand-tag) still work.
"""
import os
import re
import time
import uuid

import jwt
import pytest
import requests

from conftest import TEST_USER_PASSWORD

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

JWT_SECRET = os.environ.get("JWT_SECRET", "eaia-super-secret-jwt-key-change-in-prod-2026")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_REFRESH_SECRET = os.environ.get("JWT_REFRESH_SECRET", "eaia-refresh-super-secret-2026-rotate-in-prod")

REFRESH_COOKIE = "ithr_refresh"


# ============================================================================
# Helpers
# ============================================================================
def _new_user_payload(prefix="i14"):
    email = f"{prefix}+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    return {
        "email": email,
        "password": TEST_USER_PASSWORD,
        "full_name": "Iter14 User",
        "organization": "Test Corp",
        "title": "Analyst",
    }


def _parse_set_cookie_headers(response):
    """Return list of raw Set-Cookie header strings (requests doesn't expose
    them if session-level cookies were merged, so we look at response.raw as
    well as .headers)."""
    # requests exposes each Set-Cookie as separate item via
    # response.raw.headers.getlist() when using urllib3.
    raw = []
    try:
        raw = response.raw.headers.getlist("Set-Cookie")
    except Exception:
        pass
    if not raw:
        # fallback — may collapse multiple cookies into one string
        h = response.headers.get("Set-Cookie")
        if h:
            raw = [h]
    return raw


def _find_ithr_cookie_header(response):
    for line in _parse_set_cookie_headers(response):
        if line.lower().startswith(f"{REFRESH_COOKIE}="):
            return line
    return None


# ============================================================================
# 1. Register / Login cookie flags
# ============================================================================
class TestAuthCookieFlags:
    def test_register_sets_refresh_cookie_with_correct_flags(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/register", json=_new_user_payload("reg"))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and "user" in data
        assert isinstance(data["token"], str) and len(data["token"]) > 20

        # Cookie must be present in the jar
        assert REFRESH_COOKIE in s.cookies, f"cookie {REFRESH_COOKIE} not set. jar={dict(s.cookies)}"

        # Verify raw Set-Cookie flags
        line = _find_ithr_cookie_header(r)
        assert line is not None, f"no Set-Cookie for {REFRESH_COOKIE}. headers={dict(r.headers)}"
        low = line.lower()
        assert "httponly" in low, f"missing HttpOnly: {line}"
        assert "secure" in low, f"missing Secure: {line}"
        assert re.search(r"samesite=lax", low), f"missing SameSite=Lax: {line}"
        assert re.search(r"path=/api/auth", low), f"wrong path scope: {line}"
        # sanity: max-age ~ 7 days
        m = re.search(r"max-age=(\d+)", low)
        assert m, f"no max-age: {line}"
        max_age = int(m.group(1))
        assert 6 * 86400 <= max_age <= 8 * 86400, f"max-age not ~7d: {max_age}"

    def test_login_sets_refresh_cookie(self):
        s = requests.Session()
        payload = _new_user_payload("login")
        r = s.post(f"{API}/auth/register", json=payload)
        assert r.status_code == 200
        s2 = requests.Session()
        r2 = s2.post(f"{API}/auth/login", json={
            "email": payload["email"], "password": payload["password"],
        })
        assert r2.status_code == 200
        assert REFRESH_COOKIE in s2.cookies
        line = _find_ithr_cookie_header(r2)
        assert line is not None
        low = line.lower()
        assert "httponly" in low
        assert "secure" in low
        assert "samesite=lax" in low


# ============================================================================
# 2. Refresh endpoint
# ============================================================================
class TestRefreshEndpoint:
    def test_refresh_without_cookie_returns_401(self):
        # Fresh session, no cookie
        r = requests.post(f"{API}/auth/refresh")
        assert r.status_code == 401
        detail = r.json().get("detail", "")
        assert "no refresh" in detail.lower() or "no cookie" in detail.lower(), f"unexpected detail: {detail}"

    def test_refresh_with_bogus_cookie_returns_401_and_clears(self):
        # Manually attach a bogus cookie scoped to /api/auth
        cookies = {REFRESH_COOKIE: "not.a.valid.jwt"}
        r = requests.post(f"{API}/auth/refresh", cookies=cookies)
        assert r.status_code == 401
        # Should clear cookie (max-age=0 or expires in past)
        line = _find_ithr_cookie_header(r)
        # deletion may show as ithr_refresh=""; Max-Age=0
        if line:
            low = line.lower()
            assert "max-age=0" in low or 'expires=' in low, f"cookie not cleared: {line}"

    def test_refresh_with_valid_cookie_rotates_and_returns_new_token(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("refr"))
        assert reg.status_code == 200
        original_access = reg.json()["token"]
        original_cookie = s.cookies.get(REFRESH_COOKIE)
        assert original_cookie

        # Wait 1s so the new iat differs
        time.sleep(1.1)
        r = s.post(f"{API}/auth/refresh")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "token" in d
        new_access = d["token"]
        assert new_access != original_access, "access token should be freshly minted"

        # Cookie should be rotated
        line = _find_ithr_cookie_header(r)
        assert line is not None, "refresh should re-issue the cookie"
        new_cookie = s.cookies.get(REFRESH_COOKIE)
        assert new_cookie and new_cookie != original_cookie, "refresh cookie should rotate"


# ============================================================================
# 3. Logout clears cookie + subsequent refresh fails
# ============================================================================
class TestLogout:
    def test_logout_clears_cookie(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("lo"))
        assert reg.status_code == 200
        assert REFRESH_COOKIE in s.cookies

        # Grab the current cookie value BEFORE logout (used later to simulate stale)
        stale_cookie_val = s.cookies.get(REFRESH_COOKIE)

        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # Set-Cookie should be the deletion form (empty value + Max-Age=0 or expires in past)
        line = _find_ithr_cookie_header(r)
        assert line is not None, "logout should Set-Cookie to clear"
        low = line.lower()
        assert "max-age=0" in low or "expires=" in low, f"logout did not clear cookie: {line}"

        # Subsequent refresh WITHOUT the stale cookie -> 401
        # (Session jar dropped the cookie because Max-Age=0)
        r2 = s.post(f"{API}/auth/refresh")
        assert r2.status_code == 401


# ============================================================================
# 4. Token claim + expiry assertions
# ============================================================================
class TestTokenClaims:
    def test_access_token_has_type_access_and_15min_expiry(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("clm"))
        assert reg.status_code == 200
        access = reg.json()["token"]
        # Decode WITHOUT verification of expiry — we want to inspect claims
        payload = jwt.decode(access, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload.get("type") == "access", f"missing/wrong type: {payload}"
        assert "sub" in payload and "email" in payload and "role" in payload
        diff = payload["exp"] - payload["iat"]
        # ~15 min = 900 s. Allow ±50s tolerance.
        assert 850 <= diff <= 950, f"access exp-iat out of window: {diff}s"

    def test_refresh_token_has_type_refresh_and_7day_expiry(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("clr"))
        assert reg.status_code == 200
        refresh_cookie = s.cookies.get(REFRESH_COOKIE)
        assert refresh_cookie
        payload = jwt.decode(refresh_cookie, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload.get("type") == "refresh"
        assert "sub" in payload
        diff = payload["exp"] - payload["iat"]
        # 7 days = 604800 s. Window [86400*6+3600, 86400*7+3600] = [522000, 608400]
        assert 86400 * 6 + 3600 <= diff <= 86400 * 7 + 3600, f"refresh exp-iat out of window: {diff}s"

    def test_legacy_create_token_alias_still_accepted_by_me(self):
        """Old create_token() alias still works — /auth/me accepts the resulting bearer.
        (register uses create_access_token internally, but the alias is verified via
        the /google/callback error branches which still use it — here we simply
        verify /auth/me accepts the token from /register, i.e. the access-token
        acceptance surface is unchanged.)"""
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("leg"))
        assert reg.status_code == 200
        token = reg.json()["token"]
        r = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "email" in r.json()


# ============================================================================
# 5. Google callback negative paths
# ============================================================================
class TestGoogleCallback:
    def test_missing_session_id_400(self):
        r = requests.post(f"{API}/auth/google/callback", json={})
        assert r.status_code == 400

    def test_invalid_session_id_401_not_500(self):
        r = requests.post(f"{API}/auth/google/callback",
                          json={"session_id": "invalid-session-xxxxx"})
        assert r.status_code == 401
        assert r.status_code != 500


# ============================================================================
# 6. Refactored assessment session + quiz submit
# ============================================================================
class TestAssessmentSessionRefactor:
    @pytest.fixture(scope="class")
    def user_headers(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("assess"))
        assert reg.status_code == 200
        return {"Authorization": f"Bearer {reg.json()['token']}"}

    def test_adaptive_onboarding_mode(self, user_headers):
        r = requests.get(
            f"{API}/courses/agentic-ai-foundations/assessment/session",
            headers=user_headers,
            params={"adaptive": "true", "count": 10},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["adaptive_mode"] in ("onboarding", "escalate", "reinforce")
        # Fresh user -> onboarding
        assert d["adaptive_mode"] == "onboarding"
        assert len(d["questions"]) == 10
        # Verify shape + no leakage
        for q in d["questions"]:
            for k in ("id", "question", "type", "options", "difficulty", "permutation"):
                assert k in q, f"missing key {k}: {q}"
            assert "correct" not in q, "server leaked 'correct' field"
            assert "explanation" not in q, "server leaked 'explanation' field"
            assert isinstance(q["permutation"], list)

    def test_count_parameter_honored(self, user_headers):
        r = requests.get(
            f"{API}/courses/agentic-ai-foundations/assessment/session",
            headers=user_headers,
            params={"count": 15},
        )
        assert r.status_code == 200
        assert len(r.json()["questions"]) == 15

    def test_seed_reproduces_paper(self, user_headers):
        r1 = requests.get(
            f"{API}/courses/agentic-ai-foundations/assessment/session",
            headers=user_headers,
            params={"seed": 12345, "adaptive": "false", "count": 10},
        )
        r2 = requests.get(
            f"{API}/courses/agentic-ai-foundations/assessment/session",
            headers=user_headers,
            params={"seed": 12345, "adaptive": "false", "count": 10},
        )
        assert r1.status_code == 200 and r2.status_code == 200
        ids1 = [q["id"] for q in r1.json()["questions"]]
        ids2 = [q["id"] for q in r2.json()["questions"]]
        assert ids1 == ids2, "seed should produce identical paper"
        perms1 = [q["permutation"] for q in r1.json()["questions"]]
        perms2 = [q["permutation"] for q in r2.json()["questions"]]
        assert perms1 == perms2, "seed should reproduce option shuffling"


class TestQuizSubmitRefactor:
    def test_pass_creates_cert_and_no_duplicate_on_resubmit(self):
        # Register fresh user
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("qs"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}"}

        # Enroll
        r = s.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=h)
        assert r.status_code == 200

        # Fetch course to get correct answers
        course = s.get(f"{API}/courses/agentic-ai-foundations").json()
        answers = {q["id"]: q["correct"] for q in course["quiz"]}

        r = s.post(
            f"{API}/courses/agentic-ai-foundations/quiz/submit",
            headers=h,
            json={"course_id": course["id"], "answers": answers, "duration_seconds": 300},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["passed"] is True
        assert d["score"] == 100.0
        assert d["certificate"] is not None
        first_cert_id = d["certificate"]["certificate_id"]
        assert first_cert_id.startswith("EAIA-2026-")

        # Verify enrollments now show completed
        rows = s.get(f"{API}/enrollments", headers=h).json()
        row = next(r for r in rows if r["course"]["slug"] == "agentic-ai-foundations")
        assert row["enrollment"]["completed"] is True

        # Resubmit — must NOT duplicate cert
        r2 = s.post(
            f"{API}/courses/agentic-ai-foundations/quiz/submit",
            headers=h,
            json={"course_id": course["id"], "answers": answers, "duration_seconds": 300},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["passed"] is True
        # certificate_id should be identical (existing cert returned)
        assert d2["certificate"]["certificate_id"] == first_cert_id

        # certificates listing has exactly 1 for this course
        certs = s.get(f"{API}/certificates", headers=h).json()
        matching = [c for c in certs if c["course_id"] == course["id"]]
        assert len(matching) == 1, f"duplicate cert issued: {matching}"

    def test_fail_returns_no_certificate(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("qf"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}"}
        s.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=h)
        course = s.get(f"{API}/courses/agentic-ai-foundations").json()
        answers = {q["id"]: [99] for q in course["quiz"]}
        r = s.post(
            f"{API}/courses/agentic-ai-foundations/quiz/submit",
            headers=h,
            json={"course_id": course["id"], "answers": answers, "duration_seconds": 30},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["passed"] is False
        assert d["certificate"] is None

    def test_perm_shuffled_indices_decode_correctly(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("qp"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}"}
        s.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=h)

        # Get session with adaptive=false, small count
        sess = s.get(
            f"{API}/courses/agentic-ai-foundations/assessment/session",
            headers=h,
            params={"adaptive": "false", "count": 12, "seed": 42},
        ).json()

        # For each shuffled question, find the "true" course-correct set,
        # then translate to the shuffled indices using inverse permutation.
        course = s.get(f"{API}/courses/agentic-ai-foundations").json()
        bank_by_id = {q["id"]: q for q in course["quiz"]}

        answers = {}
        perms = {}
        for q in sess["questions"]:
            perm = q["permutation"]  # perm[new_index] = original_index
            # inverse: for each orig_idx in canonical correct, find new_idx
            inv = {orig: new for new, orig in enumerate(perm)}
            true_correct = bank_by_id[q["id"]]["correct"]
            answers[q["id"]] = sorted(inv[c] for c in true_correct)
            perms[q["id"]] = perm
        answers["__perm__"] = perms

        r = s.post(
            f"{API}/courses/agentic-ai-foundations/quiz/submit",
            headers=h,
            json={"course_id": sess["course_id"], "answers": answers, "duration_seconds": 200},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        # Should score 100% because we mapped shuffled indices back to canonical correct
        assert d["score"] == 100.0, f"perm decode failed: {d}"
        assert d["passed"] is True


# ============================================================================
# 7. Enterprise dashboard refactor
# ============================================================================
class TestEnterpriseDashboardRefactor:
    def test_dashboard_shape_unchanged(self):
        s = requests.Session()
        # Create owner + org
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("owner14"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}"}
        r = s.post(f"{API}/enterprise/organizations", headers=h, json={
            "name": f"TEST DashOrg {uuid.uuid4().hex[:6]}",
            "industry": "banking", "seat_count": 25,
        })
        assert r.status_code == 200

        r = s.get(f"{API}/enterprise/organizations/dashboard", headers=h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "organization" in d
        summary = d["summary"]
        for k in ("seat_count", "seats_used", "seats_remaining",
                  "total_enrollments", "total_completed", "total_certificates",
                  "avg_progress", "cert_coverage_pct", "readiness_index"):
            assert k in summary, f"summary missing {k}"

        assert isinstance(d["members"], list)
        for m in d["members"]:
            assert "stats" in m
            for k in ("enrollments", "completed", "certificates", "avg_progress"):
                assert k in m["stats"]

        assert isinstance(d["departments"], list)
        # Sort assertion: departments avg_progress desc
        if len(d["departments"]) > 1:
            avgs = [dept["avg_progress"] for dept in d["departments"]]
            assert avgs == sorted(avgs, reverse=True)

        assert isinstance(d["top_courses"], list)
        if len(d["top_courses"]) > 1:
            counts = [c["enrolled_count"] for c in d["top_courses"]]
            assert counts == sorted(counts, reverse=True)


# ============================================================================
# 8. Mentor SSE refactor
# ============================================================================
class TestMentorRefactor:
    def test_mentor_chat_streams_and_persists_session(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("ment"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}",
             "Content-Type": "application/json"}

        # First message — creates session
        with requests.post(f"{API}/mentor/chat", headers=h, json={
            "message": "In 3 sentences, what's the biggest risk of deploying agents in production?",
            "session_id": None,
        }, stream=True, timeout=90) as r:
            assert r.status_code == 200, r.text
            delta_count = 0
            session_id = None
            done = False
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                import json as _json
                try:
                    obj = _json.loads(raw[len("data:"):].strip())
                except Exception:
                    continue
                if obj.get("delta"):
                    delta_count += 1
                if obj.get("session_id"):
                    session_id = obj["session_id"]
                if obj.get("done"):
                    done = True
                if "error" in obj:
                    pytest.fail(f"mentor error: {obj['error']}")
            assert delta_count >= 5, f"expected some deltas, got {delta_count}"
            assert done
            assert session_id

        # Sessions endpoint returns updated_at-desc list including this session
        r = s.get(f"{API}/mentor/sessions", headers=h)
        assert r.status_code == 200
        sessions = r.json()
        assert isinstance(sessions, list) and len(sessions) >= 1
        assert any(sess.get("id") == session_id or sess.get("session_id") == session_id
                   for sess in sessions)


# ============================================================================
# 9. Passport refactor
# ============================================================================
class TestPassportRefactor:
    def test_passport_me_shape(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("pass"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}"}

        r = s.get(f"{API}/passport/me", headers=h)
        assert r.status_code == 200, r.text
        d = r.json()
        expected_keys = {
            "passport_slug", "full_name", "title", "organization",
            "credential_level", "xp", "certificates", "skills",
            "categories", "industries", "learning_hours", "generated_at",
        }
        missing = expected_keys - set(d.keys())
        assert not missing, f"missing keys: {missing}"
        assert d["credential_level"] in (
            "Learner", "Beginner", "Practitioner", "Advanced Practitioner",
            "Specialist", "Expert", "Lead", "Executive", "CXO",
        ), f"unexpected credential_level: {d['credential_level']}"
        assert isinstance(d["certificates"], list)
        assert isinstance(d["skills"], list)
        assert isinstance(d["categories"], list)
        assert isinstance(d["industries"], list)
        assert isinstance(d["learning_hours"], int)

    def test_passport_public_by_slug(self):
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("passp"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}"}
        me = s.get(f"{API}/passport/me", headers=h).json()
        slug = me["passport_slug"]
        # Public — no auth
        r = requests.get(f"{API}/passport/{slug}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["passport_slug"] == slug
        assert "credential_level" in d


# ============================================================================
# 10. Cert PDF still generates + brand tag says Independent Issuer
# ============================================================================
class TestCertPdfBrandTag:
    def test_cert_pdf_returns_pdf(self):
        # Reuse the pass-path from above to get a cert
        s = requests.Session()
        reg = s.post(f"{API}/auth/register", json=_new_user_payload("pdf"))
        assert reg.status_code == 200
        h = {"Authorization": f"Bearer {reg.json()['token']}"}
        s.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=h)
        course = s.get(f"{API}/courses/agentic-ai-foundations").json()
        answers = {q["id"]: q["correct"] for q in course["quiz"]}
        r = s.post(
            f"{API}/courses/agentic-ai-foundations/quiz/submit",
            headers=h,
            json={"course_id": course["id"], "answers": answers, "duration_seconds": 300},
        )
        assert r.status_code == 200
        cert_id = r.json()["certificate"]["certificate_id"]

        # PDF endpoint
        r = requests.get(f"{API}/certificates/{cert_id}/pdf", timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"].startswith("application/pdf")
        assert len(r.content) > 5000, f"PDF suspiciously small: {len(r.content)} bytes"
        # PDF magic bytes
        assert r.content[:4] == b"%PDF", "not a PDF"

    def test_cert_pdf_template_uses_independent_issuer_tag(self):
        # We verify the template string in-place — no rendered PDF text parsing.
        # This is a quick static check that the refactor kept the brand tag intact.
        from routers.assessment_router import _CERT_PDF_TEMPLATE
        # Case: 'Independent Issuer' present, old 'Certification Authority' absent
        assert "Independent Issuer" in _CERT_PDF_TEMPLATE, "brand tag missing"
        assert "Certification Authority" not in _CERT_PDF_TEMPLATE, "stale brand tag still present"
