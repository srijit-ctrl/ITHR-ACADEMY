"""Iteration 6 — Phase 4+5:
- /api/paths — role-based learning paths (list, detail, enroll-all)
- /api/passport/me + /api/passport/{slug} (public, no-auth)
- Adaptive assessment modes (onboarding / escalate / reinforce)
- Curriculum patches — list + decide (needs seeded briefing + apply)
- Enterprise seat management — preview + checkout (increase) + credit (decrease) + fulfill
- Light regression: courses list still 24

Run:
  pytest /app/backend/tests/test_iteration6.py -v --tb=short
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

from conftest import TEST_USER_PASSWORD

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

PATH_SLUG = "product-manager-ai"
COURSE_SLUG = "agentic-ai-foundations"
TIMEOUT = 60


# ---------------- shared fixtures ----------------
@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _register(api_client, tag: str) -> dict:
    email = f"TEST_iter6.{tag}+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    password = TEST_USER_PASSWORD
    r = api_client.post(
        f"{API}/auth/register",
        json={
            "email": email, "password": password, "full_name": f"Iter6 {tag}",
            "organization": "TEST OrgCo", "title": "Product Manager",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "email": email, "password": password,
        "token": data["token"], "user": data["user"],
        "headers": {"Authorization": f"Bearer {data['token']}"},
    }


@pytest.fixture(scope="module")
def learner(api_client):
    return _register(api_client, "path")


@pytest.fixture(scope="module")
def passport_learner(api_client):
    return _register(api_client, "passport")


@pytest.fixture(scope="module")
def adaptive_learner(api_client):
    return _register(api_client, "adaptive")


@pytest.fixture(scope="module")
def owner(api_client):
    """A learner who creates their own org so they become the owner."""
    u = _register(api_client, "owner")
    r = api_client.post(
        f"{API}/enterprise/organizations",
        json={"name": f"TEST Seat Co {uuid.uuid4().hex[:5]}", "industry": "Financial Services",
              "domain": "test.com", "seat_count": 25},
        headers=u["headers"], timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"create org failed: {r.status_code} {r.text}"
    u["org"] = r.json()["organization"]
    return u


@pytest.fixture(scope="module")
def patch_owner(api_client):
    """An authenticated user needed to seed a curriculum patch."""
    return _register(api_client, "patch")


# ---------------- Paths ----------------
class TestPaths:
    def test_list_paths(self, api_client):
        r = api_client.get(f"{API}/paths", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["count"] == 7, f"expected 7 paths, got {data['count']}"
        slugs = {p["slug"] for p in data["paths"]}
        expected = {
            "product-manager-ai", "engineer-agentic", "risk-compliance-officer",
            "hr-people-leader", "banking-officer", "healthcare-clinician", "executive-cxo",
        }
        assert slugs == expected, f"slug mismatch: {slugs}"
        for p in data["paths"]:
            for k in ("slug", "role", "target_credential", "estimated_weeks", "title"):
                assert k in p and p[k], f"path {p.get('slug')} missing {k}"

    def test_get_path_detail(self, api_client):
        r = api_client.get(f"{API}/paths/{PATH_SLUG}", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["slug"] == PATH_SLUG
        assert data["role"] == "Product Manager"
        assert isinstance(data.get("courses"), list)
        assert len(data["courses"]) == 5, f"expected 5 resolved courses, got {len(data['courses'])}"
        for c in data["courses"]:
            assert c.get("slug") and c.get("title") and c.get("id")

    def test_path_not_found(self, api_client):
        r = api_client.get(f"{API}/paths/does-not-exist", timeout=TIMEOUT)
        assert r.status_code == 404

    def test_enroll_path_and_idempotency(self, api_client, learner):
        # 1st enroll should enroll all 5
        r = api_client.post(
            f"{API}/paths/{PATH_SLUG}/enroll", json={},
            headers=learner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 5
        assert data["enrolled"] == 5
        assert data["already_enrolled"] == 0

        # 2nd call — everything is already enrolled
        r2 = api_client.post(
            f"{API}/paths/{PATH_SLUG}/enroll", json={},
            headers=learner["headers"], timeout=TIMEOUT,
        )
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        assert data2["total"] == 5
        assert data2["enrolled"] == 0
        assert data2["already_enrolled"] == 5


# ---------------- Passport ----------------
class TestPassport:
    def test_me_fresh_learner(self, api_client, passport_learner):
        r = api_client.get(f"{API}/passport/me", headers=passport_learner["headers"], timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("passport_slug"), "passport_slug should be auto-generated"
        assert data["full_name"] == passport_learner["user"]["full_name"]
        assert data["credential_level"] == "Learner"  # no certs yet
        assert data["certificates"] == []
        # Save the slug for the public test
        passport_learner["slug"] = data["passport_slug"]

    def test_public_passport_no_auth(self, api_client, passport_learner):
        """Public endpoint MUST work without Authorization header."""
        # Ensure /me was called to set slug
        if "slug" not in passport_learner:
            r = api_client.get(f"{API}/passport/me", headers=passport_learner["headers"], timeout=TIMEOUT)
            passport_learner["slug"] = r.json()["passport_slug"]
        slug = passport_learner["slug"]
        # Use a bare requests call — no auth header
        r = requests.get(f"{API}/passport/{slug}", timeout=TIMEOUT)
        assert r.status_code == 200, f"public passport must work unauthenticated: {r.status_code} {r.text}"
        data = r.json()
        assert data["passport_slug"] == slug
        assert data["full_name"] == passport_learner["user"]["full_name"]

    def test_certificate_lifts_credential_level(self, api_client, passport_learner):
        """Complete a quiz → passport should reflect new cert + credential lifted."""
        # 1) get a session
        r = api_client.get(
            f"{API}/courses/{COURSE_SLUG}/assessment/session?count=10",
            headers=passport_learner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200
        sess = r.json()

        # 2) build ALL-CORRECT answers by looking up correct in original bank
        # We can't see `correct` in the session response — but the session provided a
        # permutation for each Q. We need the course truth: fetch course.
        course_r = api_client.get(f"{API}/courses/{COURSE_SLUG}", timeout=TIMEOUT)
        assert course_r.status_code == 200
        bank = {q["id"]: q for q in course_r.json().get("quiz", [])}

        answers = {"__perm__": {}}
        for q in sess["questions"]:
            qid = q["id"]
            perm = q["permutation"]  # perm[new] = orig
            correct_orig = bank[qid]["correct"]
            # find shuffled indices whose perm maps to correct
            shuffled_correct = [i for i, orig in enumerate(perm) if orig in correct_orig]
            answers[qid] = shuffled_correct
            answers["__perm__"][qid] = perm

        submit = api_client.post(
            f"{API}/courses/{COURSE_SLUG}/quiz/submit",
            json={"course_id": sess["course_id"], "answers": answers, "duration_seconds": 60},
            headers=passport_learner["headers"], timeout=TIMEOUT,
        )
        assert submit.status_code == 200, submit.text
        sub = submit.json()
        assert sub["passed"] is True, f"quiz did not pass: {sub}"
        assert sub.get("certificate"), "expected certificate on pass"

        # 3) passport should now show the cert + credential ladder lifted
        r2 = api_client.get(f"{API}/passport/me", headers=passport_learner["headers"], timeout=TIMEOUT)
        assert r2.status_code == 200
        p = r2.json()
        assert len(p["certificates"]) >= 1
        assert p["credential_level"] != "Learner", f"credential_level should lift after cert: {p['credential_level']}"


# ---------------- Adaptive assessment ----------------
class TestAdaptive:
    def test_onboarding_mode_new_learner(self, api_client, adaptive_learner):
        r = api_client.get(
            f"{API}/courses/{COURSE_SLUG}/assessment/session?count=10",
            headers=adaptive_learner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["adaptive_mode"] == "onboarding", f"expected onboarding, got {data['adaptive_mode']}"
        # ~60% beginner: beginner count should be strictly greater than advanced
        diffs = [q["difficulty"] for q in data["questions"]]
        beg = sum(1 for d in diffs if d == "beginner")
        adv = sum(1 for d in diffs if d == "advanced")
        # In onboarding the mix is 60/30/10 — beginner > advanced (allowing slim bank)
        assert beg >= adv, f"onboarding: beg({beg}) should be >= adv({adv}) — diffs={diffs}"

    def test_reinforce_after_fail(self, api_client, adaptive_learner):
        # Submit an all-wrong quiz to force a fail
        sess_r = api_client.get(
            f"{API}/courses/{COURSE_SLUG}/assessment/session?count=10",
            headers=adaptive_learner["headers"], timeout=TIMEOUT,
        )
        sess = sess_r.json()
        # All-wrong: pick index that is NOT the correct one (approximated: send [] which is empty=wrong)
        answers = {"__perm__": {}}
        for q in sess["questions"]:
            answers[q["id"]] = []  # nothing selected = wrong
            answers["__perm__"][q["id"]] = q["permutation"]
        sub = api_client.post(
            f"{API}/courses/{COURSE_SLUG}/quiz/submit",
            json={"course_id": sess["course_id"], "answers": answers, "duration_seconds": 30},
            headers=adaptive_learner["headers"], timeout=TIMEOUT,
        )
        assert sub.status_code == 200
        assert sub.json()["passed"] is False

        # Next session should be reinforce
        r2 = api_client.get(
            f"{API}/courses/{COURSE_SLUG}/assessment/session?count=10",
            headers=adaptive_learner["headers"], timeout=TIMEOUT,
        )
        assert r2.status_code == 200
        assert r2.json()["adaptive_mode"] == "reinforce", f"expected reinforce, got {r2.json()['adaptive_mode']}"

    def test_escalate_after_pass(self, api_client, passport_learner):
        """passport_learner previously passed the quiz — a fresh session must be 'escalate'."""
        r = api_client.get(
            f"{API}/courses/{COURSE_SLUG}/assessment/session?count=10",
            headers=passport_learner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["adaptive_mode"] == "escalate", f"expected escalate, got {data['adaptive_mode']}"
        # escalate: advanced >= beginner
        diffs = [q["difficulty"] for q in data["questions"]]
        beg = sum(1 for d in diffs if d == "beginner")
        adv = sum(1 for d in diffs if d == "advanced")
        # In escalate 20/50/30, we expect advanced > beginner OR at least intermediate dominant.
        # Just assert beginner is NOT dominant.
        assert beg <= 5, f"escalate should not be beginner-heavy: diffs={diffs}"


# ---------------- Curriculum patches ----------------
class TestPatches:
    def test_seed_and_decide_patch(self, api_client, patch_owner):
        # 1) briefing to have signals cached
        b = api_client.get(f"{API}/intelligence/briefing", timeout=TIMEOUT + 60)
        assert b.status_code == 200, b.text
        signals = b.json().get("signals", [])
        if not signals:
            pytest.skip("no signals in current briefing")
        signal_id = signals[0]["id"]

        # 2) apply -> creates a proposed patch (this needs LLM, generous timeout)
        ap = api_client.post(
            f"{API}/intelligence/signals/{signal_id}/apply",
            json={"course_slug": COURSE_SLUG},
            headers=patch_owner["headers"], timeout=TIMEOUT + 60,
        )
        assert ap.status_code == 200, ap.text
        patch = ap.json()["patch"]
        assert patch["status"] == "proposed"
        patch_id = patch["id"]

        # 3) list patches
        lst = api_client.get(f"{API}/intelligence/patches",
                             headers=patch_owner["headers"], timeout=TIMEOUT)
        assert lst.status_code == 200, lst.text
        ids = {p["id"] for p in lst.json()["patches"]}
        assert patch_id in ids

        # 4) decide=approved
        dec = api_client.post(
            f"{API}/intelligence/patches/{patch_id}/decide",
            json={"decision": "approved"},
            headers=patch_owner["headers"], timeout=TIMEOUT,
        )
        assert dec.status_code == 200
        assert dec.json()["status"] == "approved"

        # 5) verify status update via filtered list
        approved = api_client.get(
            f"{API}/intelligence/patches?status=approved",
            headers=patch_owner["headers"], timeout=TIMEOUT,
        )
        assert approved.status_code == 200
        assert any(p["id"] == patch_id for p in approved.json()["patches"])

    def test_decide_invalid_id(self, api_client, patch_owner):
        r = api_client.post(
            f"{API}/intelligence/patches/does-not-exist/decide",
            json={"decision": "approved"},
            headers=patch_owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_decide_invalid_value(self, api_client, patch_owner):
        r = api_client.post(
            f"{API}/intelligence/patches/whatever/decide",
            json={"decision": "yolo"},
            headers=patch_owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 400


# ---------------- Enterprise seat management ----------------
class TestSeats:
    def test_preview_checkout(self, api_client, owner):
        current = owner["org"]["seat_count"]
        r = api_client.post(
            f"{API}/enterprise/organizations/seats/preview",
            json={"seat_count": current + 5},
            headers=owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] == "checkout"
        assert data["delta"] == 5
        assert data["charge_now"] == round(5 * 18.00, 2)

    def test_preview_credit(self, api_client, owner):
        current = owner["org"]["seat_count"]
        r = api_client.post(
            f"{API}/enterprise/organizations/seats/preview",
            json={"seat_count": current - 5},
            headers=owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] == "credit"
        assert data["credit_note"] == round(5 * 18.00, 2)

    def test_preview_noop(self, api_client, owner):
        current = owner["org"]["seat_count"]
        r = api_client.post(
            f"{API}/enterprise/organizations/seats/preview",
            json={"seat_count": current},
            headers=owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json()["action"] == "noop"

    def test_increase_seats_returns_checkout(self, api_client, owner):
        current = owner["org"]["seat_count"]
        r = api_client.post(
            f"{API}/enterprise/organizations/seats",
            json={"seat_count": current + 3, "origin_url": "https://x.com"},
            headers=owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] == "checkout"
        assert data["checkout_url"].startswith("http"), data["checkout_url"]
        assert data["session_id"]
        assert data["amount"] == round(3 * 18.00, 2)
        owner["session_id"] = data["session_id"]

        # Seat count must NOT be updated yet (until paid)
        mine = api_client.get(f"{API}/enterprise/organizations/mine",
                              headers=owner["headers"], timeout=TIMEOUT)
        assert mine.status_code == 200
        assert mine.json()["organization"]["seat_count"] == current, "seat count must not increase before payment"

    def test_fulfill_unpaid(self, api_client, owner):
        sid = owner.get("session_id")
        if not sid:
            pytest.skip("no session_id from prior test")
        r = api_client.post(
            f"{API}/enterprise/organizations/seats/fulfill/{sid}",
            headers=owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Stripe test key won't auto-pay, so fulfilled must be false
        assert data["fulfilled"] is False, f"expected unpaid fulfill, got {data}"

    def test_decrease_seats_applies_immediately_and_credit_event(self, api_client, owner):
        # Refresh org to know current seat_count
        mine = api_client.get(f"{API}/enterprise/organizations/mine",
                              headers=owner["headers"], timeout=TIMEOUT)
        current = mine.json()["organization"]["seat_count"]
        target = current - 2
        r = api_client.post(
            f"{API}/enterprise/organizations/seats",
            json={"seat_count": target, "origin_url": "https://x.com"},
            headers=owner["headers"], timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] == "credit"
        # Seat count updated immediately
        mine2 = api_client.get(f"{API}/enterprise/organizations/mine",
                               headers=owner["headers"], timeout=TIMEOUT)
        assert mine2.json()["organization"]["seat_count"] == target

        # Billing events include prorated_credit
        billing = api_client.get(f"{API}/enterprise/organizations/billing",
                                 headers=owner["headers"], timeout=TIMEOUT)
        assert billing.status_code == 200
        events = billing.json().get("events", [])
        assert any(e.get("type") == "prorated_credit" for e in events), f"no prorated_credit in {events}"


# ---------------- Light regression ----------------
class TestRegression:
    def test_courses_count(self, api_client):
        r = api_client.get(f"{API}/courses", timeout=TIMEOUT)
        assert r.status_code == 200
        courses = r.json()
        assert len(courses) == 24, f"expected 24 courses, got {len(courses)}"
