"""Backend contract tests for the Daily Learning Goal endpoints (iteration 66).

Covers:
- GET /api/me/daily-goal default shape for a fresh user
- PATCH /api/me/daily-goal persists new target
- Validation: target_minutes < 5 (422) and > 180 (422)
- Minutes-per-day computation from module_events (started=2, completed=8)
- Streak logic across 3 consecutive days
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

# Direct DB access to seed module_events (mimics prod events)
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def registered_user():
    email = f"test_dg_{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPass123!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": "Daily Goal User"},
        timeout=20,
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("access_token") or body.get("token")
    user = body.get("user") or {}
    yield {"email": email, "password": password, "token": token, "user_id": user.get("id")}


# ----- module-level helper to insert module_events directly ------------------
async def _insert_events(user_id: str, events: list[dict]):
    """events: list of {kind, created_at (iso str)}."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    docs = []
    for e in events:
        docs.append({
            "id": uuid.uuid4().hex,
            "user_id": user_id,
            "course_id": e.get("course_id", "test-course"),
            "module_id": e.get("module_id", "test-module"),
            "kind": e["kind"],
            "created_at": e["created_at"],
        })
    if docs:
        await db.module_events.insert_many(docs)
    client.close()


async def _cleanup_events(user_id: str):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.module_events.delete_many({"user_id": user_id})
    client.close()


# ----- Tests -----------------------------------------------------------------
class TestDailyGoalDefaults:
    """Fresh-user default shape."""

    def test_get_daily_goal_default_shape(self, registered_user):
        r = requests.get(f"{API}/me/daily-goal", headers=_h(registered_user["token"]), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()

        # Top-level keys
        for key in ("target_minutes", "today", "streak_days", "week", "preset_targets"):
            assert key in data, f"missing key: {key}"

        # Default target
        assert data["target_minutes"] == 15, f"expected default 15, got {data['target_minutes']}"

        # today shape
        today = data["today"]
        for key in ("date", "minutes", "remaining_minutes", "pct", "hit_goal"):
            assert key in today
        assert today["minutes"] == 0
        assert today["remaining_minutes"] == 15
        assert today["pct"] == 0
        assert today["hit_goal"] is False

        # week: exactly 7 items
        assert isinstance(data["week"], list)
        assert len(data["week"]) == 7
        for d in data["week"]:
            for key in ("date", "day_of_week", "minutes", "hit_goal"):
                assert key in d

        # preset targets
        assert data["preset_targets"] == [5, 15, 30, 60]

        # streak_days is int
        assert isinstance(data["streak_days"], int)
        assert data["streak_days"] == 0


class TestDailyGoalPatch:
    """Update target_minutes."""

    def test_patch_persists(self, registered_user):
        h = _h(registered_user["token"])
        # PATCH to 30
        r = requests.patch(f"{API}/me/daily-goal", headers=h, json={"target_minutes": 30}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["target_minutes"] == 30

        # Follow-up GET returns the persisted 30
        r2 = requests.get(f"{API}/me/daily-goal", headers=h, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["target_minutes"] == 30

    def test_patch_min_validation(self, registered_user):
        h = _h(registered_user["token"])
        r = requests.patch(f"{API}/me/daily-goal", headers=h, json={"target_minutes": 0}, timeout=15)
        assert r.status_code == 422, f"expected 422 for target<5, got {r.status_code}: {r.text}"

    def test_patch_max_validation(self, registered_user):
        h = _h(registered_user["token"])
        r = requests.patch(f"{API}/me/daily-goal", headers=h, json={"target_minutes": 200}, timeout=15)
        assert r.status_code == 422, f"expected 422 for target>180, got {r.status_code}: {r.text}"


class TestMinutesComputation:
    """Insert module_events and verify per-day minutes."""

    def test_minutes_today(self, registered_user):
        user_id = registered_user["user_id"]
        assert user_id, "need user_id to insert events"

        # First reset target back to 15 to make it predictable
        h = _h(registered_user["token"])
        requests.patch(f"{API}/me/daily-goal", headers=h, json={"target_minutes": 15}, timeout=15)

        # Clean any prior events
        asyncio.run(_cleanup_events(user_id))

        # Insert 1 started (2 min) + 1 completed (8 min) events dated today
        now = datetime.now(timezone.utc)
        events = [
            {"kind": "started", "created_at": now.isoformat()},
            {"kind": "completed", "created_at": now.isoformat()},
        ]
        asyncio.run(_insert_events(user_id, events))

        r = requests.get(f"{API}/me/daily-goal", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["today"]["minutes"] == 10, f"expected 10 (2+8), got {data['today']['minutes']}"
        assert data["today"]["remaining_minutes"] == 5
        # pct = round(10/15 * 100) = 67
        assert data["today"]["pct"] == 67, f"expected 67, got {data['today']['pct']}"
        assert data["today"]["hit_goal"] is False

        # Cleanup
        asyncio.run(_cleanup_events(user_id))


class TestStreakLogic:
    """Insert consecutive days of events exceeding target — streak should count them."""

    def test_three_day_streak(self, registered_user):
        user_id = registered_user["user_id"]
        h = _h(registered_user["token"])

        # Set target to 15 for the test
        requests.patch(f"{API}/me/daily-goal", headers=h, json={"target_minutes": 15}, timeout=15)
        asyncio.run(_cleanup_events(user_id))

        # Insert 2 'completed' events per day for today, yesterday, day-before
        # 2 completed = 16 min > 15 target
        now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        # Unique index on (user_id, course_id, module_id, kind) — vary module_id.
        events = []
        for delta in (0, 1, 2):
            day = now - timedelta(days=delta)
            events.append({"kind": "completed", "module_id": f"mod-a-{delta}", "created_at": day.isoformat()})
            events.append({"kind": "completed", "module_id": f"mod-b-{delta}", "created_at": day.isoformat()})
        asyncio.run(_insert_events(user_id, events))

        r = requests.get(f"{API}/me/daily-goal", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Allow tail = today or yesterday. With today AND yesterday hit, streak=3.
        assert data["streak_days"] == 3, f"expected streak 3, got {data['streak_days']}. week={data['week']}"

        # Cleanup
        asyncio.run(_cleanup_events(user_id))


class TestUnauthenticated:
    """Guard: unauth requests are rejected."""

    def test_get_requires_auth(self):
        r = requests.get(f"{API}/me/daily-goal", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_patch_requires_auth(self):
        r = requests.patch(f"{API}/me/daily-goal", json={"target_minutes": 15}, timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"
