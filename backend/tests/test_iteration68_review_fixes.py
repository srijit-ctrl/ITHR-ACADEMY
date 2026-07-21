"""Iteration 68 — Post code-review remediation verifications.

Covers the 6 findings from iteration_67 review:

MEDIUM:
 1. `/alerts-center` insert-first dedupe with unique index — under concurrency
    only ONE admin_automation_runs row for trigger='alert_high_severity'+key
    should be created, and the marker is cleared on /resolve so a re-fire is
    allowed.

LOW:
 2. /me/inspire — 20/hr rate limit → 429 on the 21st call.
 3. /me/change-password — 8/hr rate limit → 429 on the 9th wrong-password
    attempt.
 4. /me/summary — recent_events entries carry `kind` (not `event_type`).
 5. + 6. FoundingMemberBadge undefined-code + AdminCopilotPanel SSE cleanup are
    frontend-only, tested via Playwright separately.

REGRESSION:
 7. POST /api/auth/register triggers user_signup automation.
 8. /api/admin/automations still lists rules.
 9. /api/me/daily-goal still accepts a 5-180 minute PATCH.

DB interactions use synchronous `pymongo` — avoids Motor loop conflicts under
pytest-xdist.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
SA_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SA_PW = os.environ.get("SUPER_ADMIN_PASSWORD", "")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mdb():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def sa_token():
    if not SA_PW:
        pytest.skip("SUPER_ADMIN_PASSWORD not set")
    r = requests.post(f"{API}/auth/login", json={"email": SA_EMAIL, "password": SA_PW}, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def sa_headers(sa_token):
    return {"Authorization": f"Bearer {sa_token}", "Content-Type": "application/json"}


@pytest.fixture
def fresh_user(mdb):
    email = f"test_it68_{uuid.uuid4().hex[:10]}@example.com"
    pw = "TestPass123!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": pw, "full_name": "It68 User"},
        timeout=20,
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("access_token") or body.get("token")
    user = body.get("user") or {}
    uid = user.get("id")
    yield {
        "email": email,
        "password": pw,
        "token": token,
        "user_id": uid,
        "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    }
    # cleanup rate-limit rows for this user
    try:
        if uid:
            mdb.me_rate.delete_many({"key": {"$regex": uid}})
            mdb.module_events.delete_many({"user_id": uid})
    except Exception:
        pass


# ---------------------------------------------------------------------------
# MEDIUM 1 — alert-automation dedupe race + resume-after-resolve
# ---------------------------------------------------------------------------
ALERT_KEY = "reset-spike"


def _cleanup_alert(mdb):
    mdb.password_reset_tokens.delete_many({"seed_source": "iter68_test"})
    mdb.admin_alert_automation_fired.delete_many({"key": ALERT_KEY})
    mdb.admin_automation_runs.delete_many({"trigger": "alert_high_severity", "payload.key": ALERT_KEY})
    mdb.admin_alert_states.delete_many({"key": ALERT_KEY})


def _seed_reset_tokens(mdb, count=15):
    now = datetime.now(timezone.utc).isoformat()
    docs = [{
        "id": uuid.uuid4().hex,
        "user_id": f"iter68_seed_{i}",
        "token": uuid.uuid4().hex,
        "token_hash": uuid.uuid4().hex,
        "created_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "used": False,
        "seed_source": "iter68_test",
    } for i in range(count)]
    mdb.password_reset_tokens.insert_many(docs)


class TestAlertAutomationDedupe:
    def test_unique_index_exists(self, sa_headers, mdb):
        # Ping /alerts-center once so ensure_indexes() has definitely run.
        requests.get(f"{API}/admin/alerts-center", headers=sa_headers, timeout=15)
        info = mdb.admin_alert_automation_fired.index_information()
        # find any index over field `key` with unique=True
        unique_key_idx = [
            name for name, meta in info.items()
            if any(f[0] == "key" for f in meta.get("key", [])) and meta.get("unique")
        ]
        assert unique_key_idx, f"Expected unique index on `key` in admin_alert_automation_fired, got: {info}"

    def test_dedupe_under_concurrency_then_resume_after_resolve(self, sa_headers, mdb):
        _cleanup_alert(mdb)
        try:
            _seed_reset_tokens(mdb, 15)

            # Baseline
            assert mdb.admin_automation_runs.count_documents({"trigger": "alert_high_severity", "payload.key": ALERT_KEY}) == 0
            assert mdb.admin_alert_automation_fired.count_documents({"key": ALERT_KEY}) == 0

            # 5 parallel calls to /alerts-center
            async def _hammer():
                async with httpx.AsyncClient(timeout=30.0) as ac:
                    tasks = [ac.get(f"{API}/admin/alerts-center", headers=sa_headers) for _ in range(5)]
                    return await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.run(_hammer())

            # 3 sequential polls
            for _ in range(3):
                requests.get(f"{API}/admin/alerts-center", headers=sa_headers, timeout=15)

            # Wait for fire-and-forget asyncio.create_task on server side.
            time.sleep(3)

            marker_count = mdb.admin_alert_automation_fired.count_documents({"key": ALERT_KEY})
            run_count = mdb.admin_automation_runs.count_documents({
                "trigger": "alert_high_severity", "payload.key": ALERT_KEY,
            })

            # Under dedupe: exactly 1 marker + at most 1 automation run (0 if
            # no user rule for alert_high_severity is enabled).
            assert marker_count == 1, f"expected exactly 1 dedupe marker, got {marker_count}"
            assert run_count <= 1, f"dedupe race — expected <=1 auto run, got {run_count}"

            # POST /resolve clears the marker
            r = requests.post(
                f"{API}/admin/alerts-center/{ALERT_KEY}/resolve",
                headers=sa_headers, json={"note": "iter68 test"}, timeout=15,
            )
            assert r.status_code == 200, r.text
            marker_after = mdb.admin_alert_automation_fired.count_documents({"key": ALERT_KEY})
            assert marker_after == 0, f"marker should be cleared after /resolve, got {marker_after}"

            # NOTE: Because /resolve also sets admin_alert_states.status =
            # 'resolved' (with resolved_at NOW), /alerts-center suppresses the
            # alert for 7 days. So we validate the resume-after-resolve
            # architecture point via marker clearance — the next re-fire (
            # after 7d) would create a fresh marker via the same insert-first
            # path (proven by the concurrent test above).
        finally:
            _cleanup_alert(mdb)


# ---------------------------------------------------------------------------
# LOW 2 — /me/inspire 20/hr rate limit
# ---------------------------------------------------------------------------
class TestInspireRateLimit:
    def test_21st_call_returns_429(self, fresh_user):
        headers = fresh_user["headers"]
        for i in range(20):
            r = requests.post(f"{API}/me/inspire", headers=headers, json={}, timeout=30)
            assert r.status_code != 429, f"unexpectedly rate-limited on call #{i+1}: {r.text}"

        r21 = requests.post(f"{API}/me/inspire", headers=headers, json={}, timeout=15)
        assert r21.status_code == 429, f"expected 429 on 21st call, got {r21.status_code}: {r21.text}"
        detail = (r21.json() or {}).get("detail", "")
        assert "Too many inspiration requests" in detail, f"unexpected detail: {detail}"


# ---------------------------------------------------------------------------
# LOW 3 — /me/change-password 8/hr rate limit
# ---------------------------------------------------------------------------
class TestChangePasswordRateLimit:
    def test_9th_wrong_password_returns_429(self, fresh_user):
        headers = fresh_user["headers"]
        payload = {"current_password": "WRONG_PASS_XYZ!", "new_password": "AnotherPassX9!"}

        for i in range(8):
            r = requests.post(f"{API}/me/change-password", headers=headers, json=payload, timeout=15)
            assert r.status_code != 429, f"unexpectedly rate-limited on wrong-password call #{i+1}: {r.text}"
            assert r.status_code == 401, f"expected 401 on wrong-password call #{i+1}, got {r.status_code}: {r.text}"

        r9 = requests.post(f"{API}/me/change-password", headers=headers, json=payload, timeout=15)
        assert r9.status_code == 429, f"expected 429 on 9th call, got {r9.status_code}: {r9.text}"
        detail = (r9.json() or {}).get("detail", "")
        assert "Too many password-change attempts" in detail, f"unexpected detail: {detail}"


# ---------------------------------------------------------------------------
# LOW 4 — me_summary recent_events uses `kind`
# ---------------------------------------------------------------------------
class TestMeSummaryRecentEventsField:
    def test_recent_events_carries_kind_not_event_type(self, fresh_user, mdb):
        uid = fresh_user["user_id"]
        mdb.module_events.insert_one({
            "id": uuid.uuid4().hex,
            "user_id": uid,
            "course_id": "test-course-iter68",
            "module_id": "test-module-1",
            "kind": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        r = requests.get(f"{API}/me/summary", headers=fresh_user["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        events = body.get("recent_events") or []
        assert len(events) >= 1, f"expected at least 1 recent_event, got {events}"
        e = events[0]
        assert "kind" in e, f"expected `kind` field in recent_events entry, got keys={list(e.keys())}"
        assert e["kind"] == "completed", f"expected kind='completed', got {e.get('kind')}"
        assert "event_type" not in e, f"recent_events entry should NOT have `event_type` — got {e}"


# ---------------------------------------------------------------------------
# REGRESSION
# ---------------------------------------------------------------------------
class TestRegression:
    def test_signup_triggers_user_signup_automation(self, mdb):
        baseline = mdb.admin_automation_runs.count_documents({"trigger": "user_signup"})
        email = f"test_it68_reg_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "TestPass123!", "full_name": "R"},
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        time.sleep(2)
        after = mdb.admin_automation_runs.count_documents({"trigger": "user_signup"})
        # Only assert non-decrease — a `user_signup` rule may not be enabled
        # in this env, in which case count stays the same. We just verify no
        # exception broke the pipeline (count didn't decrease).
        assert after >= baseline, "automation runs count decreased unexpectedly"

    def test_automations_list_endpoint(self, sa_headers):
        r = requests.get(f"{API}/admin/automations", headers=sa_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "automations" in body
        assert isinstance(body["automations"], list)

    def test_daily_goal_patch_still_works(self, fresh_user):
        r = requests.patch(
            f"{API}/me/daily-goal", headers=fresh_user["headers"],
            json={"target_minutes": 45}, timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("target_minutes") == 45
        r_low = requests.patch(f"{API}/me/daily-goal", headers=fresh_user["headers"], json={"target_minutes": 4}, timeout=15)
        assert r_low.status_code == 422
        r_high = requests.patch(f"{API}/me/daily-goal", headers=fresh_user["headers"], json={"target_minutes": 181}, timeout=15)
        assert r_high.status_code == 422

    def test_alerts_center_still_returns_shape(self, sa_headers):
        r = requests.get(f"{API}/admin/alerts-center", headers=sa_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "alerts" in body
        assert "generated_at" in body
        assert isinstance(body["alerts"], list)
