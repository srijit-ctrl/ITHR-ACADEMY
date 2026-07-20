"""Iteration 52 backend tests — covers:

  1. POST /api/admin/drips/onboarding/run — dry_run + real send idempotency,
     role exclusion (super_admin/admin), 401/403 protection, drip_send_log
     unique index on (user_id, stage).
  2. GET  /api/referrals/leaderboard      — public masked list, viewer_rank/stats
     for signed-in caller, empty-name masking, 0-signup viewer.
  3. GET  /api/admin/referrals/leaderboard — Super Admin unmasked; 401/403 for
     non-admins.

Tests are hermetic — each fresh learner is created dynamically and cleaned up
by an admin sweep at the end.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

# Make backend modules importable so we can poke the DB directly for the
# "backdate created_at + verify drip idempotency" scenarios.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import db  # noqa: E402
from routers.referral_router import _mask_name  # noqa: E402

# Sync pymongo client for cross-test DB pokes — motor's async client caches the
# event loop from first use, which breaks when multiple `asyncio.run()` calls
# happen inside pytest workers. pymongo has no such constraint.
from pymongo import MongoClient  # noqa: E402
_sync_client = MongoClient(os.environ["MONGO_URL"])
sync_db = _sync_client[os.environ["DB_NAME"]]

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

TEST_PREFIX = "TEST_it52_"


# ---------------------- Fixtures ----------------------


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=API, timeout=90.0) as c:
        yield c


@pytest.fixture(scope="module")
def super_admin_token(http):
    if not SUPER_ADMIN_PASSWORD:
        pytest.skip("SUPER_ADMIN_PASSWORD not set")
    r = http.post("/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
    assert r.status_code == 200, f"super-admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}"}


def _register(http: httpx.Client, full_name: str = "Iter52 Learner") -> dict:
    email = f"{TEST_PREFIX}{uuid.uuid4().hex[:10]}@example.com"
    password = os.environ.get("E2E_TEST_USER_PASSWORD", "TestPass123!")
    r = http.post("/auth/register", json={
        "full_name": full_name,
        "email": email,
        "password": password,
    })
    assert r.status_code == 200, f"register failed: {r.text}"
    body = r.json()
    return {
        "email": email,
        "password": password,
        "token": body["token"],
        "user_id": body["user"]["id"],
        "full_name": full_name,
    }


# =========================================================================
# ===================  1. ONBOARDING DRIP TESTS  ==========================
# =========================================================================


class TestOnboardingDripAuth:
    """Endpoint must be super-admin only."""

    def test_unauthenticated_rejected(self, http):
        r = http.post("/admin/drips/onboarding/run?dry_run=true")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_regular_learner_rejected(self, http):
        learner = _register(http)
        r = http.post(
            "/admin/drips/onboarding/run?dry_run=true",
            headers={"Authorization": f"Bearer {learner['token']}"},
        )
        assert r.status_code in (401, 403), f"expected 401/403 for learner, got {r.status_code}: {r.text}"


class TestOnboardingDripDryRun:
    """Dry-run shape + role exclusion for the general endpoint."""

    def test_dry_run_shape(self, http, super_admin_headers):
        r = http.post("/admin/drips/onboarding/run?dry_run=true", headers=super_admin_headers)
        assert r.status_code == 200, f"drip run failed: {r.text}"
        data = r.json()
        assert data.get("dry_run") is True
        assert "generated_at" in data and isinstance(data["generated_at"], str)
        for stage in ("first_course_nudge", "referral_invite"):
            assert stage in data, f"missing stage {stage}"
            s = data[stage]
            for k in ("eligible", "sent", "skipped_already_sent", "errors", "dry_run_samples"):
                assert k in s, f"stage {stage} missing key {k}"
            assert isinstance(s["dry_run_samples"], list)
            # dry-run must not actually send
            assert s["sent"] == 0

    def test_super_admin_excluded_from_candidates(self, http, super_admin_headers):
        """The seeded superadmin@ithr.online must never appear as a drip candidate."""
        r = http.post("/admin/drips/onboarding/run?dry_run=true", headers=super_admin_headers)
        assert r.status_code == 200
        data = r.json()
        nudge_samples = data["first_course_nudge"]["dry_run_samples"]
        invite_samples = data["referral_invite"]["dry_run_samples"]
        assert SUPER_ADMIN_EMAIL not in nudge_samples, "super_admin leaked into nudge samples"
        assert SUPER_ADMIN_EMAIL not in invite_samples, "super_admin leaked into invite samples"

    def test_drip_send_log_unique_index(self, http, super_admin_headers):
        """Calling the endpoint must auto-create the unique index on (user_id, stage)."""
        # Fire the endpoint so _ensure_indexes() runs.
        http.post("/admin/drips/onboarding/run?dry_run=true", headers=super_admin_headers)
        info = sync_db.drip_send_log.index_information()
        found = False
        for name, spec in info.items():
            keys = [k for k, _ in spec.get("key", [])]
            if set(keys) == {"user_id", "stage"} and spec.get("unique"):
                found = True
                break
        assert found, f"unique (user_id, stage) index missing on drip_send_log; got: {info}"


class TestOnboardingDripIdempotency:
    """Backdate a fresh learner, run non-dry, then run again — second run must
    skip via drip_send_log."""

    def _backdate(self, user_id: str, days: int):
        past = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        sync_db.users.update_one({"id": user_id}, {"$set": {"created_at": past}})

    def _cleanup_drip_log(self, user_id: str):
        sync_db.drip_send_log.delete_many({"user_id": user_id})

    def test_first_course_nudge_idempotent(self, http, super_admin_headers):
        # Fresh learner, backdate to 3 days ago → eligible for Day-2 nudge only
        learner = _register(http, full_name="Nudge Idempotent")
        self._backdate(learner["user_id"], days=3)
        self._cleanup_drip_log(learner["user_id"])

        # First non-dry-run — expect this learner to be counted (either sent or errored,
        # since RESEND may or may not deliver — both are acceptable per spec: helper
        # must not raise, drip must record the attempt).
        r1 = http.post("/admin/drips/onboarding/run?dry_run=false", headers=super_admin_headers)
        assert r1.status_code == 200, f"real run failed: {r1.text}"
        stage1 = r1.json()["first_course_nudge"]
        assert stage1["eligible"] >= 1, "backdated learner not eligible"

        # Verify a drip_send_log row now exists for that user/stage
        log_row = sync_db.drip_send_log.find_one(
            {"user_id": learner["user_id"], "stage": "first-course-nudge"},
            {"_id": 0},
        )
        assert log_row is not None, "drip_send_log row missing after real run"
        assert log_row["stage"] == "first-course-nudge"
        assert log_row["email"].lower() == learner["email"].lower()
        assert "sent" in log_row  # boolean, may be True or False depending on Resend key

        # Second real run — this user must NOT be in the candidate list at all
        # (excluded via `id: {$nin: already}`). So no new row appears.
        r2 = http.post("/admin/drips/onboarding/run?dry_run=false", headers=super_admin_headers)
        assert r2.status_code == 200
        n = sync_db.drip_send_log.count_documents(
            {"user_id": learner["user_id"], "stage": "first-course-nudge"},
        )
        assert n == 1, f"expected exactly 1 log row after 2 runs, got {n}"

        # Cleanup
        self._cleanup_drip_log(learner["user_id"])

    def test_drip_helpers_never_raise(self):
        """Both new email helpers must return False (not raise) on Resend failure.
        We exercise them directly with a bad recipient — the shared _fire() helper
        catches all exceptions and returns False."""
        from email_service import (
            send_first_course_nudge_email,
            send_referral_invite_email,
        )

        async def go():
            # Should not raise — either True or False based on Resend availability.
            r1 = await send_first_course_nudge_email("delivered@resend.dev", "Test User")
            r2 = await send_referral_invite_email(
                "delivered@resend.dev", "Test User", "TESTCODE", "https://example.com/register?ref=TESTCODE",
            )
            return r1, r2

        r1, r2 = asyncio.run(go())
        assert isinstance(r1, bool)
        assert isinstance(r2, bool)


# =========================================================================
# ===================  2. PUBLIC LEADERBOARD TESTS  =======================
# =========================================================================


class TestMaskNameHelper:
    """Direct unit-tests on the mask helper — cheap and prevents drift."""

    def test_two_words(self):
        assert _mask_name("Alice Ma") == "Alice M."

    def test_multi_word_uses_last(self):
        assert _mask_name("Alice van Berg") == "Alice B."

    def test_one_word(self):
        assert _mask_name("Prince") == "Prince"

    def test_empty(self):
        assert _mask_name("") == "Anonymous"

    def test_whitespace_only(self):
        assert _mask_name("   ") == "Anonymous"


class TestPublicLeaderboard:
    def test_public_no_auth(self, http):
        r = http.get("/referrals/leaderboard?limit=10")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data and "totals" in data
        for k in ("referrers", "signups", "converted"):
            assert k in data["totals"] and isinstance(data["totals"][k], int)
        # No viewer_* fields for unauthenticated caller
        assert "viewer_rank" not in data
        assert "viewer_stats" not in data
        # Row shape + rank sequencing
        prev_rank = 0
        for row in data["rows"]:
            assert set(row.keys()) >= {"rank", "name", "organization", "signups", "converted"}
            assert row["rank"] == prev_rank + 1
            prev_rank = row["rank"]
            # Name is masked — never contain '@' (that would leak email)
            assert "@" not in row["name"]

    def test_public_sort_order(self, http):
        """converted DESC, signups DESC — verify monotonic (converted, signups) tuple."""
        r = http.get("/referrals/leaderboard?limit=50")
        assert r.status_code == 200
        rows = r.json()["rows"]
        prev = (10**9, 10**9)
        for row in rows:
            cur = (row["converted"], row["signups"])
            assert cur <= prev, f"sort broken at rank {row['rank']}: {cur} > {prev}"
            prev = cur

    def test_limit_bounds(self, http):
        # limit=0 should 422 (ge=1)
        r = http.get("/referrals/leaderboard?limit=0")
        assert r.status_code == 422
        r = http.get("/referrals/leaderboard?limit=51")
        assert r.status_code == 422
        r = http.get("/referrals/leaderboard?limit=1")
        assert r.status_code == 200
        assert len(r.json()["rows"]) <= 1

    def test_viewer_zero_signups(self, http):
        """Signed-in learner with 0 signups should get viewer_rank=null and
        viewer_stats with 0/0."""
        learner = _register(http, full_name="Alice Ma")
        r = http.get(
            "/referrals/leaderboard?limit=10",
            headers={"Authorization": f"Bearer {learner['token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("viewer_rank") is None
        vs = data.get("viewer_stats")
        assert vs is not None
        assert vs["signups"] == 0
        assert vs["converted"] == 0
        assert vs["name"] == "Alice M.", f"masked name mismatch: {vs['name']}"


# =========================================================================
# =============  3. SUPER ADMIN UNMASKED LEADERBOARD  =====================
# =========================================================================


class TestAdminLeaderboard:
    def test_unauthenticated_rejected(self, http):
        r = http.get("/admin/referrals/leaderboard")
        assert r.status_code in (401, 403)

    def test_learner_rejected(self, http):
        learner = _register(http)
        r = http.get(
            "/admin/referrals/leaderboard",
            headers={"Authorization": f"Bearer {learner['token']}"},
        )
        assert r.status_code in (401, 403)

    def test_super_admin_unmasked(self, http, super_admin_headers):
        r = http.get("/admin/referrals/leaderboard?limit=25", headers=super_admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data and "totals" in data
        for row in data["rows"]:
            assert set(row.keys()) >= {
                "rank", "user_id", "full_name", "email",
                "organization", "referral_code", "signups", "converted",
            }
        # Verify rank sequencing
        for i, row in enumerate(data["rows"]):
            assert row["rank"] == i + 1

    def test_admin_limit_clamped(self, http, super_admin_headers):
        # limit is clamped server-side to [1, 100] — no 422, just clamped.
        r = http.get("/admin/referrals/leaderboard?limit=500", headers=super_admin_headers)
        assert r.status_code == 200


# =========================================================================
# ===================  Cleanup =============================================
# =========================================================================


class TestZZCleanup:
    """Runs last (name prefix Z sorts to end). Sweeps @example.com users
    created by this suite."""

    def test_cleanup_sweep(self, http, super_admin_headers):
        # Find all TEST_it52_ users and delete via admin API
        r = http.get(f"/admin/users?q={TEST_PREFIX}", headers=super_admin_headers)
        if r.status_code != 200:
            pytest.skip(f"admin/users search unavailable: {r.status_code}")
        users = r.json()
        # Normalize response — some admin endpoints return list, others {items:[]}
        if isinstance(users, dict):
            users = users.get("items", users.get("users", []))
        deleted = 0
        for u in users:
            uid = u.get("id") or u.get("_id") or u.get("user_id")
            if not uid:
                continue
            if not (u.get("email") or "").startswith(TEST_PREFIX):
                continue
            d = http.delete(f"/admin/users/{uid}", headers=super_admin_headers)
            if d.status_code in (200, 204):
                deleted += 1
        # Also clean up any drip_send_log leftovers
        sync_db.drip_send_log.delete_many({"email": {"$regex": f"^{TEST_PREFIX}"}})
        print(f"Cleanup deleted {deleted} test users")
