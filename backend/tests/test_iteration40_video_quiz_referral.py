"""Iteration 40: Video-quiz + referral registration + certificate PDF integrity."""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://enterprise-agent-dev.preview.emergentagent.com"
API = f"{BASE_URL}/api"

SUPER_EMAIL = "superadmin@ithr.online"
SUPER_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

SAMPLE_CERT_ID = "SAMPLE-ITHR-2026-001"


# ---------------------- fixtures ----------------------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def super_admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASSWORD})
    assert r.status_code == 200, f"super-admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}"}


def _register_learner(s, referral_code=None, email=None):
    email = email or f"test.learner+{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}@example.com"
    body = {
        "email": email,
        "password": "TestPass123!",
        "full_name": f"Test Learner {uuid.uuid4().hex[:4]}",
        "organization": "Test Corp",
        "title": "Analyst",
    }
    if referral_code is not None:
        body["referral_code"] = referral_code
    r = s.post(f"{API}/auth/register", json=body)
    return r, email


# ---------------------- REGISTRATION REFERRAL ----------------------
class TestReferralRegistration:
    def test_register_with_valid_code_upper(self, s):
        r, email = _register_learner(s, referral_code="FOUNDING500")
        assert r.status_code == 200, r.text
        data = r.json()
        user = data["user"]
        assert user["paid_via_referral"] is True
        assert user["payment_status"] == "paid"
        assert isinstance(user.get("referral_seq"), int) and user["referral_seq"] >= 1

    def test_register_with_valid_code_lower(self, s):
        r, email = _register_learner(s, referral_code="founding500")
        assert r.status_code == 200, r.text
        user = r.json()["user"]
        assert user["paid_via_referral"] is True
        assert user["payment_status"] == "paid"
        assert isinstance(user.get("referral_seq"), int)

    def test_register_with_invalid_code_400_no_user(self, s):
        email = f"invalid+{uuid.uuid4().hex[:6]}@example.com"
        r, _ = _register_learner(s, referral_code="NOPE-INVALID-CODE", email=email)
        assert r.status_code == 400, r.text
        assert "Invalid referral code" in r.text
        # Verify no user created — attempting to log in should fail 401
        login = s.post(f"{API}/auth/login", json={"email": email, "password": "TestPass123!"})
        assert login.status_code == 401

    def test_register_without_code_normal(self, s):
        r, _ = _register_learner(s, referral_code=None)
        assert r.status_code == 200, r.text
        user = r.json()["user"]
        assert user.get("paid_via_referral") is False
        assert user.get("referral_seq") is None


# ---------------------- VIDEO-QUIZ LEARNER ----------------------
@pytest.fixture(scope="module")
def learner_ctx(s):
    """Register a fresh learner and return {token, headers, user_id, email}."""
    r, email = _register_learner(s, referral_code="FOUNDING500")
    assert r.status_code == 200
    data = r.json()
    return {
        "token": data["token"],
        "headers": {"Authorization": f"Bearer {data['token']}"},
        "user_id": data["user"]["id"],
        "email": email,
        "full_name": data["user"]["full_name"],
    }


@pytest.fixture(scope="module")
def foundations_course(s):
    r = s.get(f"{API}/courses/agentic-ai-foundations")
    assert r.status_code == 200, r.text
    c = r.json()
    assert c.get("modules"), "no modules in foundations course"
    return c


@pytest.fixture(scope="module")
def foundations_lesson(foundations_course):
    m = foundations_course["modules"][0]
    assert m.get("lessons"), "no lessons in first module"
    return {
        "course_id": foundations_course["id"],
        "course_slug": foundations_course["slug"],
        "module_id": m["id"],
        "lesson_id": m["lessons"][0]["id"],
    }


class TestVideoQuizLearner:
    def test_get_video_quiz_returns_video_and_checkpoints_no_answers(
        self, s, learner_ctx, foundations_lesson
    ):
        r = s.get(
            f"{API}/lessons/{foundations_lesson['lesson_id']}/video-quiz",
            headers=learner_ctx["headers"],
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("video_url"), "expected a seeded video_url"
        cps = data.get("checkpoints", [])
        assert len(cps) >= 2, f"expected >=2 checkpoints, got {len(cps)}"
        for cp in cps:
            # Answers must NOT leak to the client
            assert "correct_index" not in cp, f"correct_index leaked: {cp}"
            assert "question" in cp and "options" in cp and "id" in cp

    def test_get_video_quiz_requires_auth(self, s, foundations_lesson):
        r = s.get(f"{API}/lessons/{foundations_lesson['lesson_id']}/video-quiz")
        assert r.status_code in (401, 403)


# ---------------------- 3-STRIKE RESET FLOW ----------------------
@pytest.fixture(scope="module")
def reset_learner(s):
    """Fresh learner used solely for the 3-strike reset flow."""
    r, email = _register_learner(s, referral_code="FOUNDING500")
    assert r.status_code == 200
    d = r.json()
    return {"token": d["token"], "headers": {"Authorization": f"Bearer {d['token']}"},
            "user_id": d["user"]["id"], "email": email}


class TestVideoQuizReset:
    def test_enroll_complete_lesson_then_fail_3x_resets(
        self, s, reset_learner, foundations_course, foundations_lesson, super_admin_headers
    ):
        headers = reset_learner["headers"]

        # 1. Enroll
        er = s.post(f"{API}/courses/{foundations_course['slug']}/enroll", headers=headers)
        assert er.status_code in (200, 201), er.text

        # 2. Mark first lesson complete
        cr = s.post(
            f"{API}/lessons/complete",
            json={
                "course_id": foundations_course["id"],
                "lesson_id": foundations_lesson["lesson_id"],
                "module_id": foundations_lesson["module_id"],
            },
            headers=headers,
        )
        assert cr.status_code == 200, cr.text

        # Verify lesson in completed_lessons
        me_enr = s.get(f"{API}/enrollments", headers=headers)
        assert me_enr.status_code == 200
        enr = next(e["enrollment"] for e in me_enr.json() if e["enrollment"]["course_id"] == foundations_course["id"])
        assert foundations_lesson["lesson_id"] in enr["completed_lessons"]
        pre_progress = enr["progress_pct"]

        # 3. Grab a checkpoint id via admin (to know the true correct_index would be nice
        # but we test by picking the FIRST checkpoint and answering with a definitely-wrong
        # index. We look up the true answer server-side via admin list to invert it.)
        adm = s.get(
            f"{API}/admin/video-checkpoints?lesson_id={foundations_lesson['lesson_id']}",
            headers=super_admin_headers,
        )
        assert adm.status_code == 200, adm.text
        rows = adm.json()["rows"]
        assert rows, "no checkpoints seeded"
        cp = rows[0]
        wrong_idx = 0 if cp["correct_index"] != 0 else 1
        cp_id = cp["id"]

        # 4. Answer wrong three times
        r1 = s.post(f"{API}/video-quiz/{cp_id}/answer",
                    json={"selected_index": wrong_idx}, headers=headers)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["correct"] is False and d1["attempts_left"] == 2 and d1["reset"] is False

        r2 = s.post(f"{API}/video-quiz/{cp_id}/answer",
                    json={"selected_index": wrong_idx}, headers=headers)
        d2 = r2.json()
        assert d2["correct"] is False and d2["attempts_left"] == 1 and d2["reset"] is False

        r3 = s.post(f"{API}/video-quiz/{cp_id}/answer",
                    json={"selected_index": wrong_idx}, headers=headers)
        d3 = r3.json()
        assert d3["correct"] is False and d3["reset"] is True and d3["attempts_left"] == 0

        # 5. Verify enrollment reset: lesson removed from completed_lessons
        me_enr2 = s.get(f"{API}/enrollments", headers=headers)
        enr2 = next(e["enrollment"] for e in me_enr2.json() if e["enrollment"]["course_id"] == foundations_course["id"])
        assert foundations_lesson["lesson_id"] not in enr2["completed_lessons"]
        # progress recalculated downward (or equal to 0)
        assert enr2["progress_pct"] <= pre_progress

    def test_correct_answer_returns_correct_true(
        self, s, learner_ctx, foundations_lesson, super_admin_headers
    ):
        adm = s.get(
            f"{API}/admin/video-checkpoints?lesson_id={foundations_lesson['lesson_id']}",
            headers=super_admin_headers,
        )
        rows = adm.json()["rows"]
        cp = rows[0]
        r = s.post(
            f"{API}/video-quiz/{cp['id']}/answer",
            json={"selected_index": cp["correct_index"]},
            headers=learner_ctx["headers"],
        )
        assert r.status_code == 200, r.text
        assert r.json()["correct"] is True


# ---------------------- ADMIN CRUD AUTHZ ----------------------
class TestAdminAuthz:
    def test_learner_cannot_list(self, s, learner_ctx, foundations_lesson):
        r = s.get(
            f"{API}/admin/video-checkpoints?lesson_id={foundations_lesson['lesson_id']}",
            headers=learner_ctx["headers"],
        )
        assert r.status_code in (401, 403), r.status_code

    def test_learner_cannot_post(self, s, learner_ctx, foundations_lesson, foundations_course):
        r = s.post(
            f"{API}/admin/video-checkpoints",
            headers=learner_ctx["headers"],
            json={
                "course_id": foundations_course["id"],
                "lesson_id": foundations_lesson["lesson_id"],
                "timestamp_sec": 5,
                "question": "hijack?",
                "options": ["a", "b"],
                "correct_index": 0,
            },
        )
        assert r.status_code in (401, 403)

    def test_unauth_cannot_set_video(self, s, foundations_lesson):
        r = s.put(
            f"{API}/admin/lessons/{foundations_lesson['lesson_id']}/video",
            json={"video_url": "https://example.com/x.mp4"},
        )
        assert r.status_code in (401, 403)


class TestAdminCRUD:
    def test_admin_crud_lifecycle(self, s, super_admin_headers, foundations_lesson, foundations_course):
        # CREATE
        payload = {
            "course_id": foundations_course["id"],
            "lesson_id": foundations_lesson["lesson_id"],
            "timestamp_sec": 42.0,
            "question": "TEST_ Admin CRUD question?",
            "options": ["opt1", "opt2", "opt3"],
            "correct_index": 1,
        }
        r = s.post(f"{API}/admin/video-checkpoints", json=payload, headers=super_admin_headers)
        assert r.status_code == 200, r.text
        cp = r.json()
        cp_id = cp["id"]
        assert cp["correct_index"] == 1
        assert cp["timestamp_sec"] == 42.0

        # LIST includes it
        r2 = s.get(
            f"{API}/admin/video-checkpoints?lesson_id={foundations_lesson['lesson_id']}",
            headers=super_admin_headers,
        )
        assert cp_id in [row["id"] for row in r2.json()["rows"]]

        # UPDATE
        r3 = s.put(
            f"{API}/admin/video-checkpoints/{cp_id}",
            json={"question": "TEST_ updated?", "correct_index": 2},
            headers=super_admin_headers,
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["question"] == "TEST_ updated?"
        assert r3.json()["correct_index"] == 2

        # DELETE
        r4 = s.delete(f"{API}/admin/video-checkpoints/{cp_id}", headers=super_admin_headers)
        assert r4.status_code == 200
        assert r4.json()["ok"] is True

        # Verify gone
        r5 = s.get(
            f"{API}/admin/video-checkpoints?lesson_id={foundations_lesson['lesson_id']}",
            headers=super_admin_headers,
        )
        assert cp_id not in [row["id"] for row in r5.json()["rows"]]

    def test_admin_create_correct_index_out_of_range_400(
        self, s, super_admin_headers, foundations_lesson, foundations_course
    ):
        r = s.post(
            f"{API}/admin/video-checkpoints",
            json={
                "course_id": foundations_course["id"],
                "lesson_id": foundations_lesson["lesson_id"],
                "timestamp_sec": 5,
                "question": "bad",
                "options": ["a", "b"],
                "correct_index": 5,
            },
            headers=super_admin_headers,
        )
        assert r.status_code == 400

    def test_admin_set_lesson_video(self, s, super_admin_headers, foundations_lesson):
        new_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        r = s.put(
            f"{API}/admin/lessons/{foundations_lesson['lesson_id']}/video",
            json={"video_url": new_url},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["video_url"] == new_url


# ---------------------- CERTIFICATE PDF ----------------------
class TestCertificatePdf:
    def test_sample_cert_pdf_200(self, s):
        r = s.get(f"{API}/certificates/{SAMPLE_CERT_ID}/pdf")
        assert r.status_code == 200, r.text[:400]
        assert "application/pdf" in r.headers.get("content-type", "")
        # Sanity: PDF magic bytes
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 5000

    def test_nonexistent_cert_404(self, s):
        r = s.get(f"{API}/certificates/DOES-NOT-EXIST-000/pdf")
        assert r.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
