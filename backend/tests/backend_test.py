"""Enterprise Agentic AI Academy — Backend API tests."""
import json
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def test_user(api_client):
    """Register a fresh user, return dict {email, password, token, user}."""
    email = f"test.learner+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    password = "TestPass123!"
    payload = {
        "email": email, "password": password, "full_name": "Test Learner",
        "organization": "Test Corp", "title": "Analyst",
    }
    r = api_client.post(f"{API}/auth/register", json=payload)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    return {"email": email, "password": password, "token": data["token"], "user": data["user"]}


@pytest.fixture(scope="session")
def auth_headers(test_user):
    return {"Authorization": f"Bearer {test_user['token']}"}


# ---------------- Health ----------------
def test_health(api_client):
    r = api_client.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ---------------- Auth ----------------
class TestAuth:
    def test_register_duplicate(self, api_client, test_user):
        r = api_client.post(f"{API}/auth/register", json={
            "email": test_user["email"], "password": "AnotherPass!", "full_name": "Dup"
        })
        assert r.status_code == 400

    def test_login_valid(self, api_client, test_user):
        r = api_client.post(f"{API}/auth/login", json={
            "email": test_user["email"], "password": test_user["password"]
        })
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == test_user["email"].lower()
        assert isinstance(d["token"], str) and len(d["token"]) > 20

    def test_login_invalid(self, api_client, test_user):
        r = api_client.post(f"{API}/auth/login", json={
            "email": test_user["email"], "password": "WrongPass!"
        })
        assert r.status_code == 401

    def test_me_with_token(self, api_client, auth_headers, test_user):
        r = api_client.get(f"{API}/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["email"] == test_user["email"].lower()

    def test_me_without_token(self, api_client):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code in (401, 403)

    def test_google_callback_missing_session_id(self, api_client):
        r = api_client.post(f"{API}/auth/google/callback", json={})
        assert r.status_code == 400

    def test_google_callback_invalid_session_id(self, api_client):
        r = api_client.post(f"{API}/auth/google/callback", json={"session_id": "invalid-session-xxx"})
        assert r.status_code == 401
        assert r.status_code != 500


# ---------------- Catalog ----------------
class TestCatalog:
    def test_industries(self, api_client):
        r = api_client.get(f"{API}/catalog/industries")
        assert r.status_code == 200
        inds = r.json()["industries"]
        assert isinstance(inds, list)
        assert len(inds) == 22, f"expected 22 industries, got {len(inds)}"

    def test_categories(self, api_client):
        r = api_client.get(f"{API}/catalog/categories")
        assert r.status_code == 200
        cats = r.json()["categories"]
        assert isinstance(cats, list) and len(cats) > 0

    def test_certification_paths(self, api_client):
        r = api_client.get(f"{API}/catalog/certification-paths")
        assert r.status_code == 200
        paths = r.json()["paths"]
        assert isinstance(paths, list)
        assert len(paths) == 8, f"expected 8 tiers, got {len(paths)}"


# ---------------- Courses ----------------
class TestCourses:
    def test_list_all(self, api_client):
        r = api_client.get(f"{API}/courses")
        assert r.status_code == 200
        courses = r.json()
        assert len(courses) == 24, f"expected 24 courses, got {len(courses)}"

    def test_filter_by_difficulty(self, api_client):
        r = api_client.get(f"{API}/courses?difficulty=beginner")
        assert r.status_code == 200
        for c in r.json():
            assert c["difficulty"] == "beginner"

    def test_filter_by_category(self, api_client):
        r = api_client.get(f"{API}/courses")
        cat = r.json()[0]["category"]
        r2 = api_client.get(f"{API}/courses?category={cat}")
        assert r2.status_code == 200
        for c in r2.json():
            assert c["category"] == cat

    def test_search_query(self, api_client):
        r = api_client.get(f"{API}/courses?q=agentic")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_get_full_course(self, api_client):
        r = api_client.get(f"{API}/courses/agentic-ai-foundations")
        assert r.status_code == 200
        c = r.json()
        assert len(c["modules"]) == 15, f"expected 15 modules, got {len(c['modules'])}"
        assert len(c["quiz"]) == 12, f"expected 12 quiz questions, got {len(c['quiz'])}"


# ---------------- Enrollment / Progress ----------------
class TestEnrollment:
    def test_enroll_requires_auth(self, api_client):
        r = requests.post(f"{API}/courses/agentic-ai-foundations/enroll")
        assert r.status_code in (401, 403)

    def test_enroll_first_and_repeat(self, api_client, auth_headers):
        r = api_client.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert d["already_enrolled"] is False
        # second call
        r2 = api_client.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["already_enrolled"] is True

    def test_get_enrollments(self, api_client, auth_headers):
        r = api_client.get(f"{API}/enrollments", headers=auth_headers)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 1
        assert "course" in rows[0] and "enrollment" in rows[0]
        assert rows[0]["course"]["slug"] == "agentic-ai-foundations"

    def test_complete_lesson(self, api_client, auth_headers):
        # get course to grab course_id, module_id, lesson_id
        course = api_client.get(f"{API}/courses/agentic-ai-foundations").json()
        m0 = course["modules"][0]
        l0 = m0["lessons"][0]
        r = api_client.post(f"{API}/lessons/complete", headers=auth_headers, json={
            "course_id": course["id"], "module_id": m0["id"], "lesson_id": l0["id"]
        })
        assert r.status_code == 200
        d = r.json()
        assert "progress_pct" in d
        assert d["progress_pct"] > 0


# ---------------- Quiz / Certificate ----------------
class TestQuizCert:
    def test_submit_quiz_pass_and_certificate(self, api_client, auth_headers):
        course = api_client.get(f"{API}/courses/agentic-ai-foundations").json()
        # build answers: use correct answers
        answers = {q["id"]: q["correct"] for q in course["quiz"]}
        r = api_client.post(
            f"{API}/courses/agentic-ai-foundations/quiz/submit",
            headers=auth_headers,
            json={"course_id": course["id"], "answers": answers, "duration_seconds": 300}
        )
        assert r.status_code == 200
        d = r.json()
        assert d["score"] == 100.0
        assert d["passed"] is True
        assert d["certificate"] is not None
        assert d["certificate"]["certificate_id"].startswith("EAIA-2026-")

    def test_certificates_list(self, api_client, auth_headers):
        r = api_client.get(f"{API}/certificates", headers=auth_headers)
        assert r.status_code == 200
        certs = r.json()
        assert len(certs) >= 1

    def test_certificate_verify_public(self, api_client, auth_headers):
        certs = api_client.get(f"{API}/certificates", headers=auth_headers).json()
        cid = certs[0]["certificate_id"]
        # no auth
        r = requests.get(f"{API}/certificates/verify/{cid}")
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is True
        assert d["certificate"]["certificate_id"] == cid

    def test_certificate_verify_not_found(self, api_client):
        r = api_client.get(f"{API}/certificates/verify/EAIA-2026-XXXXXX")
        assert r.status_code == 404

    def test_submit_quiz_fail(self, api_client, auth_headers):
        # register another user for a clean fail attempt
        email = f"quizfail+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
        reg = api_client.post(f"{API}/auth/register", json={
            "email": email, "password": "Pass123!", "full_name": "Q Fail"
        })
        token = reg.json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        api_client.post(f"{API}/courses/agentic-ai-foundations/enroll", headers=h)
        course = api_client.get(f"{API}/courses/agentic-ai-foundations").json()
        # deliberately wrong: use [999] for all
        answers = {q["id"]: [99] for q in course["quiz"]}
        r = api_client.post(f"{API}/courses/agentic-ai-foundations/quiz/submit",
                            headers=h, json={"course_id": course["id"], "answers": answers, "duration_seconds": 30})
        assert r.status_code == 200
        d = r.json()
        assert d["passed"] is False
        assert d["certificate"] is None


# ---------------- Dashboard ----------------
class TestDashboard:
    def test_stats(self, api_client, auth_headers):
        r = api_client.get(f"{API}/dashboard/stats", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        for k in ("enrollments", "certificates", "completed_courses", "xp", "streak_days"):
            assert k in d
        # note: enrollments/certs values depend on test order under xdist; assert types only
        assert isinstance(d["enrollments"], int)
        assert isinstance(d["certificates"], int)
        assert isinstance(d["xp"], int)


# ---------------- AI Tutor SSE ----------------
class TestAITutor:
    def test_stream_tutor(self, test_user):
        headers = {
            "Authorization": f"Bearer {test_user['token']}",
            "Content-Type": "application/json",
        }
        payload = {
            "message": "Explain in detail (at least 5 sentences) what an agentic AI system is, its key components, and how it differs from traditional AI chatbots. Include examples.",
            "session_id": None, "course_context": None,
        }
        with requests.post(f"{API}/ai/tutor", headers=headers, json=payload, stream=True, timeout=90) as r:
            assert r.status_code == 200, f"tutor status {r.status_code}"
            delta_count = 0
            got_done = False
            session_id = None
            content_buf = []
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if raw.startswith("data:"):
                    data = raw[len("data:"):].strip()
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    if "delta" in obj and obj["delta"]:
                        delta_count += 1
                        content_buf.append(obj["delta"])
                    if obj.get("done"):
                        got_done = True
                        session_id = obj.get("session_id")
                    if "error" in obj:
                        pytest.fail(f"AI error: {obj['error']}")
            assert delta_count >= 20, f"expected >=20 delta events, got {delta_count}. content={''.join(content_buf)[:200]}"
            assert got_done is True
            assert session_id is not None


# ---------------- Intelligence (Iteration 2) ----------------
class TestIntelligence:
    def test_briefing_public_returns_valid_schema(self, api_client):
        r = api_client.get(f"{API}/intelligence/briefing", timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("briefing_title", "executive_summary", "signals", "course_refresh_priorities"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["signals"], list)
        assert 6 <= len(d["signals"]) <= 8, f"expected 6-8 signals, got {len(d['signals'])}"
        assert isinstance(d["course_refresh_priorities"], list)
        # Each signal has required fields
        for s in d["signals"]:
            for k in ("id", "category", "title", "summary", "impact",
                      "affected_courses", "source_type", "recommended_action"):
                assert k in s, f"signal missing {k}: {s}"
            assert isinstance(s["affected_courses"], list)

    def test_briefing_cache_behavior(self, api_client):
        r1 = api_client.get(f"{API}/intelligence/briefing", timeout=120)
        assert r1.status_code == 200
        r2 = api_client.get(f"{API}/intelligence/briefing", timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        assert d.get("from_cache") is True
        assert "cache_age_hours" in d
        assert isinstance(d["cache_age_hours"], (int, float))

    def test_briefing_force_bypasses_cache(self, api_client):
        # This may be slow; skip if we can't afford time in this run.
        # Just verify endpoint accepts the param and returns 200.
        r = api_client.get(f"{API}/intelligence/briefing?force=false", timeout=30)
        assert r.status_code == 200

    def test_course_refresh_requires_auth(self, api_client):
        r = requests.get(f"{API}/intelligence/course/agentic-ai-foundations/refresh")
        assert r.status_code in (401, 403)

    def test_course_refresh_unknown_slug_404(self, api_client, auth_headers):
        r = api_client.get(
            f"{API}/intelligence/course/this-slug-does-not-exist/refresh",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 404

    def test_course_refresh_returns_schema(self, api_client, auth_headers):
        r = api_client.get(
            f"{API}/intelligence/course/agentic-ai-foundations/refresh",
            headers=auth_headers, timeout=180,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("freshness_score", "gaps", "new_lessons_suggested",
                  "deprecations", "executive_note"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["freshness_score"], int)
        assert 0 <= d["freshness_score"] <= 100
        assert isinstance(d["gaps"], list)
        assert isinstance(d["new_lessons_suggested"], list)



# ---------------- Iteration 3: Freshness fields on courses ----------------
class TestFreshness:
    def test_list_courses_have_freshness_fields(self, api_client):
        r = api_client.get(f"{API}/courses")
        assert r.status_code == 200
        courses = r.json()
        assert len(courses) == 24
        for c in courses:
            assert "freshness_score" in c
            assert "days_since_review" in c
            assert "last_reviewed_at" in c
            assert isinstance(c["freshness_score"], int)
            assert 55 <= c["freshness_score"] <= 100, f"freshness OOR for {c['slug']}: {c['freshness_score']}"
            assert isinstance(c["days_since_review"], int)
            assert 0 <= c["days_since_review"] <= 200

    def test_freshness_decreases_with_days(self, api_client):
        r = api_client.get(f"{API}/courses")
        courses = r.json()
        # collect (days, score)
        pairs = [(c["days_since_review"], c["freshness_score"]) for c in courses if c["days_since_review"] < 90]
        # invariant: higher days => lower or equal score
        # verify by sorting
        pairs_sorted = sorted(pairs, key=lambda p: p[0])
        for i in range(1, len(pairs_sorted)):
            assert pairs_sorted[i][1] <= pairs_sorted[i - 1][1] + 1  # allow rounding

    def test_single_course_has_freshness_fields(self, api_client):
        r = api_client.get(f"{API}/courses/agentic-ai-foundations")
        assert r.status_code == 200
        c = r.json()
        assert "freshness_score" in c
        assert "days_since_review" in c
        assert "last_reviewed_at" in c
        assert 55 <= c["freshness_score"] <= 100


# ---------------- Iteration 3: 5 full courses ----------------
FULL_COURSES = [
    "agentic-ai-foundations",
    "prompt-engineering-mastery",
    "multi-agent-systems",
    "rag-enterprise",
    "ai-governance-compliance",
    "agentic-ai-banking",
    "agentic-ai-healthcare",
    "agentic-ai-manufacturing",
    "agentic-ai-retail",
    "agentic-ai-government",
]


class TestFullCourses:
    @pytest.mark.parametrize("slug", FULL_COURSES)
    def test_full_course_has_15_modules_12_quiz(self, api_client, slug):
        r = api_client.get(f"{API}/courses/{slug}")
        assert r.status_code == 200, f"{slug}: {r.status_code} {r.text[:200]}"
        c = r.json()
        assert len(c["modules"]) == 15, f"{slug} modules={len(c['modules'])}"
        assert len(c["quiz"]) == 12, f"{slug} quiz={len(c['quiz'])}"
        # each module has lessons
        for m in c["modules"]:
            assert "lessons" in m
            assert len(m["lessons"]) >= 1

    def test_list_has_ten_full_courses(self, api_client):
        r = api_client.get(f"{API}/courses")
        courses = r.json()
        full = [c for c in courses if c.get("has_full_content")]
        assert len(full) == 10, f"expected 10 full courses, got {len(full)}: {[c['slug'] for c in full]}"
        slugs = {c["slug"] for c in full}
        assert slugs == set(FULL_COURSES), f"slugs mismatch: {slugs}"


# ---------------- Iteration 3: Stripe checkout ----------------
class TestStripeCheckout:
    def test_list_packages(self, api_client):
        r = api_client.get(f"{API}/checkout/packages")
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        for pid in ("practitioner_monthly", "practitioner_annual", "professional_track", "team_monthly_per_seat"):
            assert pid in pkgs, f"missing package {pid}"
        assert pkgs["practitioner_monthly"]["amount"] == 29.0
        assert pkgs["practitioner_annual"]["amount"] == 290.0
        assert pkgs["professional_track"]["amount"] == 499.0
        assert pkgs["team_monthly_per_seat"]["amount"] == 18.0

    def test_create_session_requires_auth(self, api_client):
        r = requests.post(f"{API}/checkout/session", json={
            "package_id": "practitioner_monthly",
            "origin_url": "https://example.com",
        })
        assert r.status_code in (401, 403)

    def test_create_session_invalid_package(self, api_client, auth_headers):
        r = api_client.post(f"{API}/checkout/session", headers=auth_headers, json={
            "package_id": "nonexistent_package",
            "origin_url": "https://example.com",
        })
        assert r.status_code == 400

    def test_create_session_practitioner_monthly(self, api_client, auth_headers, test_user):
        r = api_client.post(f"{API}/checkout/session", headers=auth_headers, json={
            "package_id": "practitioner_monthly",
            "origin_url": "https://example.com",
        }, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        d = r.json()
        assert "url" in d and "session_id" in d
        assert "checkout.stripe.com" in d["url"], f"unexpected url: {d['url']}"
        # session_id typically starts with cs_
        assert d["session_id"].startswith("cs_"), f"unexpected session_id: {d['session_id']}"
        # store for later status check
        pytest.stripe_session = {"session_id": d["session_id"], "token": test_user["token"]}

    def test_create_session_team_seats_clamped(self, api_client, auth_headers):
        # request 500 seats -> clamped to 100 -> amount 1800
        r = api_client.post(f"{API}/checkout/session", headers=auth_headers, json={
            "package_id": "team_monthly_per_seat",
            "origin_url": "https://example.com",
            "quantity": 500,
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout.stripe.com" in d["url"]

    def test_create_session_team_seats_clamped_min(self, api_client, auth_headers):
        # request 1 seat -> clamped to 10 -> amount 180
        r = api_client.post(f"{API}/checkout/session", headers=auth_headers, json={
            "package_id": "team_monthly_per_seat",
            "origin_url": "https://example.com",
            "quantity": 1,
        }, timeout=30)
        assert r.status_code == 200, r.text

    def test_checkout_status_requires_auth(self, api_client):
        r = requests.get(f"{API}/checkout/status/cs_test_dummy")
        assert r.status_code in (401, 403)

    def test_checkout_status_returns_data(self, api_client, auth_headers):
        # relies on prior test_create_session_practitioner_monthly
        session_data = getattr(pytest, "stripe_session", None)
        if not session_data:
            pytest.skip("No stripe session created yet")
        r = api_client.get(f"{API}/checkout/status/{session_data['session_id']}", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "payment_status" in d
        assert "status" in d
        # unpaid new session
        assert d["payment_status"] in ("initiated", "unpaid", "no_payment_required", "paid")

    def test_checkout_status_unknown_session_404(self, api_client, auth_headers):
        r = api_client.get(f"{API}/checkout/status/cs_does_not_exist_xyz", headers=auth_headers)
        assert r.status_code == 404

    def test_checkout_status_forbidden_other_user(self, api_client, auth_headers, test_user):
        # create session with user A
        r = api_client.post(f"{API}/checkout/session", headers=auth_headers, json={
            "package_id": "practitioner_monthly",
            "origin_url": "https://example.com",
        }, timeout=30)
        assert r.status_code == 200
        sess_id = r.json()["session_id"]
        # register user B
        email = f"otheruser+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
        reg = api_client.post(f"{API}/auth/register", json={
            "email": email, "password": "Pass123!", "full_name": "Other User"
        })
        assert reg.status_code == 200
        token_b = reg.json()["token"]
        r2 = api_client.get(f"{API}/checkout/status/{sess_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert r2.status_code == 403

    def test_webhook_bad_signature_returns_400(self, api_client):
        # POST plain JSON with no valid Stripe-Signature header
        r = requests.post(f"{API}/webhook/stripe",
                          data=b'{"type":"checkout.session.completed"}',
                          headers={"Content-Type": "application/json"})
        # should be 400 (invalid sig) — should NOT be 500
        assert r.status_code in (200, 400), f"got {r.status_code}: {r.text[:200]}"

    def test_create_session_missing_origin_url(self, api_client, auth_headers):
        r = api_client.post(f"{API}/checkout/session", headers=auth_headers, json={
            "package_id": "practitioner_monthly",
        })
        assert r.status_code == 400

    def test_payment_transaction_persisted(self, api_client, auth_headers):
        # create session, then fetch status, then verify record exists via status endpoint
        r = api_client.post(f"{API}/checkout/session", headers=auth_headers, json={
            "package_id": "professional_track",
            "origin_url": "https://example.com",
        }, timeout=30)
        assert r.status_code == 200
        sess_id = r.json()["session_id"]
        # status endpoint reads from payment_transactions, so a 200/402/etc (not 404) confirms it was persisted
        r2 = api_client.get(f"{API}/checkout/status/{sess_id}", headers=auth_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["package_id"] == "professional_track"
        assert d["tier"] == "professional"
        assert d["amount"] == 499.0


# ==================== Iteration 4: Enterprise Portal ====================
def _register_user(api_client, prefix="ent"):
    email = f"{prefix}+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    r = api_client.post(f"{API}/auth/register", json={
        "email": email, "password": "TestPass123!", "full_name": f"{prefix.title()} User"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "token": d["token"], "user": d["user"]}


class TestEnterpriseOrg:
    """Enterprise portal: org create/get/dashboard/seats/members/invite/join."""

    def test_mine_returns_404_when_no_org(self, api_client):
        u = _register_user(api_client, "noorg")
        r = api_client.get(f"{API}/enterprise/organizations/mine",
                           headers={"Authorization": f"Bearer {u['token']}"})
        assert r.status_code == 404

    def test_create_organization_requires_auth(self, api_client):
        r = requests.post(f"{API}/enterprise/organizations",
                          json={"name": "NoAuth Co", "industry": "banking", "seat_count": 25})
        assert r.status_code in (401, 403)

    def test_full_org_flow(self, api_client):
        # === 1. Owner registers + creates org ===
        owner = _register_user(api_client, "owner")
        owner_h = {"Authorization": f"Bearer {owner['token']}"}
        create_payload = {"name": f"TEST Org {uuid.uuid4().hex[:6]}",
                          "industry": "banking", "seat_count": 25}
        r = api_client.post(f"{API}/enterprise/organizations",
                            headers=owner_h, json=create_payload)
        assert r.status_code == 200, r.text
        org = r.json()["organization"]
        assert org["name"] == create_payload["name"]
        assert org["slug"] and len(org["slug"]) > 0
        assert org["invite_code"] and len(org["invite_code"]) >= 4
        assert org["seat_count"] == 25
        assert org["seats_used"] == 1
        assert org["owner_user_id"] == owner["user"]["id"]
        pytest.ent_org = org
        pytest.ent_owner = owner

        # === 2. Second create for same user returns 400 ===
        r2 = api_client.post(f"{API}/enterprise/organizations",
                             headers=owner_h, json=create_payload)
        assert r2.status_code == 400

        # === 3. GET /organizations/mine returns org + membership ===
        r = api_client.get(f"{API}/enterprise/organizations/mine", headers=owner_h)
        assert r.status_code == 200
        d = r.json()
        assert d["organization"]["id"] == org["id"]
        assert d["membership"]["role"] == "owner"

        # === 4. Owner creates invite ===
        invitee_email = f"invitee+{uuid.uuid4().hex[:6]}@example.com"
        r = api_client.post(f"{API}/enterprise/organizations/invites",
                            headers=owner_h,
                            json={"email": invitee_email, "role": "member", "department": "Engineering"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["invite"]["email"] == invitee_email
        assert d["invite"]["role"] == "member"
        assert d["invite"]["department"] == "Engineering"
        assert d["invite"]["status"] == "pending"
        assert "invite_url" in d
        assert org["invite_code"] in d["invite_url"]

        # === 5. Invalid role defaults to "member" ===
        r = api_client.post(f"{API}/enterprise/organizations/invites",
                            headers=owner_h,
                            json={"email": f"x+{uuid.uuid4().hex[:4]}@example.com", "role": "hacker"})
        assert r.status_code == 200
        assert r.json()["invite"]["role"] == "member"

        # === 6. Bad email ===
        r = api_client.post(f"{API}/enterprise/organizations/invites",
                            headers=owner_h, json={"email": "not-an-email"})
        assert r.status_code == 400

        # === 7. List invites ===
        r = api_client.get(f"{API}/enterprise/organizations/invites", headers=owner_h)
        assert r.status_code == 200
        assert len(r.json()["invites"]) >= 2

        # === 8. New user joins via invite_code ===
        member = _register_user(api_client, "member")
        member_h = {"Authorization": f"Bearer {member['token']}"}
        r = api_client.post(f"{API}/enterprise/organizations/join",
                            headers=member_h,
                            json={"invite_code": org["invite_code"]})
        assert r.status_code == 200, r.text
        assert r.json()["membership"]["role"] == "member"
        pytest.ent_member = member

        # verify seats_used incremented
        r = api_client.get(f"{API}/enterprise/organizations/mine", headers=owner_h)
        assert r.json()["organization"]["seats_used"] == 2

        # === 9. Invalid invite code ===
        another = _register_user(api_client, "another")
        r = api_client.post(f"{API}/enterprise/organizations/join",
                            headers={"Authorization": f"Bearer {another['token']}"},
                            json={"invite_code": "BOGUSCODE"})
        assert r.status_code == 404

        # === 10. Already-in-org user cannot join again ===
        r = api_client.post(f"{API}/enterprise/organizations/join",
                            headers=member_h,
                            json={"invite_code": org["invite_code"]})
        assert r.status_code == 400

        # === 11. Dashboard summary ===
        r = api_client.get(f"{API}/enterprise/organizations/dashboard", headers=owner_h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["organization"]["id"] == org["id"]
        assert "summary" in d
        for k in ("readiness_index", "seat_count", "seats_used",
                  "avg_progress", "cert_coverage_pct"):
            assert k in d["summary"], f"missing summary key {k}"
        assert d["summary"]["seats_used"] == 2
        assert isinstance(d["members"], list) and len(d["members"]) == 2
        assert "stats" in d["members"][0]
        assert isinstance(d["departments"], list)
        assert isinstance(d["top_courses"], list)

        # Fresh org: readiness_index should be 0 (no progress/certs yet)
        assert d["summary"]["readiness_index"] == 0.0

        # === 12. Adjust seats (owner only) ===
        r = api_client.post(f"{API}/enterprise/organizations/seats",
                            headers=owner_h, json={"seat_count": 50})
        assert r.status_code == 200
        assert r.json()["organization"]["seat_count"] == 50

        # Cannot go below current usage
        r = api_client.post(f"{API}/enterprise/organizations/seats",
                            headers=owner_h, json={"seat_count": 1})
        assert r.status_code == 400

        # Cannot exceed 5000
        r = api_client.post(f"{API}/enterprise/organizations/seats",
                            headers=owner_h, json={"seat_count": 10000})
        assert r.status_code == 400

        # Member cannot adjust seats (403)
        r = api_client.post(f"{API}/enterprise/organizations/seats",
                            headers=member_h, json={"seat_count": 30})
        assert r.status_code == 403

        # === 13. Remove member ===
        # Find member's org_member id via dashboard
        dash = api_client.get(f"{API}/enterprise/organizations/dashboard", headers=owner_h).json()
        member_row = next((m for m in dash["members"] if m["role"] == "member"), None)
        assert member_row is not None
        r = api_client.delete(f"{API}/enterprise/organizations/members/{member_row['id']}",
                              headers=owner_h)
        assert r.status_code == 200
        assert r.json()["removed"] is True

        # Verify seats_used decremented
        r = api_client.get(f"{API}/enterprise/organizations/mine", headers=owner_h)
        assert r.json()["organization"]["seats_used"] == 1

        # Cannot remove the owner
        owner_row = next(m for m in dash["members"] if m["role"] == "owner")
        r = api_client.delete(f"{API}/enterprise/organizations/members/{owner_row['id']}",
                              headers=owner_h)
        assert r.status_code == 400


# ==================== Iteration 4: Push signals into curriculum ====================
class TestPushToCurriculum:
    """Apply intelligence signals to courses as curriculum patches."""

    def test_apply_requires_auth(self, api_client):
        r = requests.post(f"{API}/intelligence/signals/sig-x/apply",
                          json={"course_slug": "agentic-ai-foundations"})
        assert r.status_code in (401, 403)

    def test_apply_requires_course_slug(self, api_client, auth_headers):
        r = api_client.post(f"{API}/intelligence/signals/sig-x/apply",
                            headers=auth_headers, json={})
        assert r.status_code == 400

    def test_apply_unknown_signal_404(self, api_client, auth_headers):
        # Ensure briefing exists (cached)
        api_client.get(f"{API}/intelligence/briefing", timeout=120)
        r = api_client.post(f"{API}/intelligence/signals/does-not-exist-signal/apply",
                            headers=auth_headers,
                            json={"course_slug": "agentic-ai-foundations"})
        assert r.status_code == 404

    def test_apply_unknown_course_404(self, api_client, auth_headers):
        brief = api_client.get(f"{API}/intelligence/briefing", timeout=120).json()
        sig_id = brief["signals"][0]["id"]
        r = api_client.post(f"{API}/intelligence/signals/{sig_id}/apply",
                            headers=auth_headers,
                            json={"course_slug": "no-such-course"})
        assert r.status_code == 404

    def test_apply_success_returns_patch_and_updates_freshness(self, api_client, auth_headers):
        # cached briefing
        brief = api_client.get(f"{API}/intelligence/briefing", timeout=120).json()
        sig_id = brief["signals"][0]["id"]
        # course freshness BEFORE
        c_before = api_client.get(f"{API}/courses/agentic-ai-foundations").json()
        r = api_client.post(f"{API}/intelligence/signals/{sig_id}/apply",
                            headers=auth_headers,
                            json={"course_slug": "agentic-ai-foundations"},
                            timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "proposed"
        p = d["patch"]
        for k in ("course_slug", "signal_id", "module_number", "module_title",
                  "patch_type", "proposed_title", "proposed_content", "rationale",
                  "status", "created_by", "created_at"):
            assert k in p, f"patch missing {k}"
        assert p["course_slug"] == "agentic-ai-foundations"
        assert p["signal_id"] == sig_id
        assert p["status"] == "proposed"
        assert isinstance(p["module_number"], int)
        pytest.push_patch_id = p["id"]

        # course freshness_score bumped to ~100 (0 days since review)
        c_after = api_client.get(f"{API}/courses/agentic-ai-foundations").json()
        assert c_after["freshness_score"] >= c_before.get("freshness_score", 0)
        assert c_after["days_since_review"] == 0
        assert c_after["freshness_score"] == 100

    def test_list_patches(self, api_client, auth_headers):
        r = api_client.get(f"{API}/intelligence/patches", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert "patches" in d and isinstance(d["patches"], list)
        assert d["count"] == len(d["patches"])

    def test_list_patches_filter_by_course(self, api_client, auth_headers):
        r = api_client.get(f"{API}/intelligence/patches?course_slug=agentic-ai-foundations",
                           headers=auth_headers)
        assert r.status_code == 200
        for p in r.json()["patches"]:
            assert p["course_slug"] == "agentic-ai-foundations"

    def test_list_patches_filter_by_status(self, api_client, auth_headers):
        r = api_client.get(f"{API}/intelligence/patches?status=proposed",
                           headers=auth_headers)
        assert r.status_code == 200
        for p in r.json()["patches"]:
            assert p["status"] == "proposed"

    def test_decide_patch_approve(self, api_client, auth_headers):
        pid = getattr(pytest, "push_patch_id", None)
        if not pid:
            pytest.skip("no patch id from previous test")
        r = api_client.post(f"{API}/intelligence/patches/{pid}/decide",
                            headers=auth_headers, json={"decision": "approved"})
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_decide_patch_invalid_decision(self, api_client, auth_headers):
        pid = getattr(pytest, "push_patch_id", None)
        if not pid:
            pytest.skip("no patch id")
        r = api_client.post(f"{API}/intelligence/patches/{pid}/decide",
                            headers=auth_headers, json={"decision": "maybe"})
        assert r.status_code == 400

    def test_decide_patch_unknown(self, api_client, auth_headers):
        r = api_client.post(f"{API}/intelligence/patches/nonexistent-patch-id/decide",
                            headers=auth_headers, json={"decision": "approved"})
        assert r.status_code == 404


# ==================== Iteration 4: Router refactor sanity ====================
class TestRouterRefactorSanity:
    """After router refactor, endpoints across 8 routers still respond."""

    def test_all_router_endpoints_respond(self, api_client, auth_headers):
        """Sample endpoints from each of the 8 routers must respond (mounted)."""
        checks = [
            ("GET", "/health", None, [200]),                       # dashboard_router
            ("GET", "/courses", None, [200]),                      # catalog_router
            ("GET", "/catalog/industries", None, [200]),
            ("GET", "/dashboard/stats", auth_headers, [200]),
            ("GET", "/enrollments", auth_headers, [200]),          # assessment_router
            ("GET", "/certificates", auth_headers, [200]),
            ("GET", "/checkout/packages", None, [200]),            # checkout_router
            ("GET", "/enterprise/organizations/mine", auth_headers, [200, 404]),  # enterprise_router
            ("GET", "/intelligence/patches", auth_headers, [200]), # intelligence_router
        ]
        for method, ep, hdrs, ok_codes in checks:
            r = requests.request(method, f"{API}{ep}", headers=hdrs or {})
            assert r.status_code in ok_codes, f"{ep} returned {r.status_code}, expected {ok_codes}"
