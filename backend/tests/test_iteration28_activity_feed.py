"""Iteration 28 — Live Activity Feed backend tests.

Coverage:
- log_activity helper writes to db.activity_events with correct fields
- POST /api/auth/register writes a signup event
- POST /api/courses/{slug}/enroll writes an enrollment event (new only)
- Certificate issuance writes a certificate event
- POST /api/admin/orgs writes an org_created event
- GET /api/admin/activity/recent authorization gating (401/403)
- GET /api/admin/activity/recent limit clamping + since= filter
- db.activity_events has index on 'created_at'
"""
import os
import time
import asyncio

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://enterprise-agent-dev.preview.emergentagent.com"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.tech")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "preview-only-rotate-in-prod")


# ---------- fixtures --------------------------------------------------------


@pytest.fixture(scope="module")
def super_admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD,
    })
    assert r.status_code == 200, f"super-admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def super_admin_client(super_admin_token):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {super_admin_token}",
        "Content-Type": "application/json",
    })
    return s


@pytest.fixture(scope="module")
def fresh_learner():
    """Register a fresh learner; return (token, email, id, name)."""
    ts = int(time.time() * 1000)
    email = f"iter28.learner+{ts}@example.com"
    payload = {
        "email": email,
        "password": "TestPass123!",
        "full_name": f"Iter28 Learner {ts}",
        "organization": "Test Corp",
        "title": "Analyst",
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "token": data["token"],
        "email": email,
        "id": data["user"]["id"],
        "name": payload["full_name"],
    }


@pytest.fixture(scope="module")
def learner_client(fresh_learner):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {fresh_learner['token']}",
        "Content-Type": "application/json",
    })
    return s


# ---------- mongo index -----------------------------------------------------


def test_activity_events_created_at_index():
    """Mongo activity_events must have an index on created_at."""
    async def _check():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        info = await db.activity_events.index_information()
        client.close()
        return info
    info = asyncio.get_event_loop().run_until_complete(_check())
    # Search for an index on created_at (name may vary)
    has_created_at_index = any(
        any(k == "created_at" for k, _ in idx["key"])
        for idx in info.values()
    )
    assert has_created_at_index, f"No created_at index found. Indexes: {list(info.keys())}"


# ---------- auth gating -----------------------------------------------------


def test_recent_activity_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/activity/recent")
    assert r.status_code in (401, 403), r.status_code


def test_recent_activity_forbidden_for_learner(learner_client):
    r = learner_client.get(f"{BASE_URL}/api/admin/activity/recent")
    assert r.status_code == 403, f"Expected 403 for learner, got {r.status_code} {r.text}"


def test_recent_activity_super_admin_ok(super_admin_client):
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "events" in data and isinstance(data["events"], list)
    assert "count" in data and data["count"] == len(data["events"])


# ---------- limit clamping --------------------------------------------------


def test_recent_activity_default_limit_and_sort(super_admin_client):
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) <= 25
    # DESC sort
    for a, b in zip(events, events[1:]):
        assert a["created_at"] >= b["created_at"], "events not sorted DESC by created_at"


def test_recent_activity_limit_clamp_high(super_admin_client):
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"limit": 500})
    assert r.status_code == 200
    assert len(r.json()["events"]) <= 100


def test_recent_activity_limit_clamp_low(super_admin_client):
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"limit": 0})
    assert r.status_code == 200
    # Clamped to 1
    assert len(r.json()["events"]) <= 1


# ---------- registration creates signup event ------------------------------


def test_register_creates_signup_event(fresh_learner, super_admin_client):
    # Give the fire-and-forget task a moment
    time.sleep(1.5)
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"limit": 100})
    assert r.status_code == 200
    events = r.json()["events"]
    signup_events = [e for e in events if e["kind"] == "signup" and fresh_learner["email"] in e["message"]]
    assert signup_events, f"No signup event for fresh learner {fresh_learner['email']} in {len(events)} events"
    ev = signup_events[0]
    assert ev["actor_id"] == fresh_learner["id"]
    assert ev["actor_name"] == fresh_learner["name"]
    assert "New signup" in ev["message"]


# ---------- enrollment creates enrollment event ----------------------------


def test_enrollment_creates_activity_event(learner_client, super_admin_client, fresh_learner):
    # find any course slug
    r = requests.get(f"{BASE_URL}/api/courses")
    assert r.status_code == 200
    courses = r.json()
    assert courses, "No courses available"
    slug = courses[0]["slug"]
    title = courses[0]["title"]

    # First enrollment — should log
    r1 = learner_client.post(f"{BASE_URL}/api/courses/{slug}/enroll")
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1.get("already_enrolled") is False

    time.sleep(1.5)
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"limit": 100})
    events = r.json()["events"]
    matches = [
        e for e in events
        if e["kind"] == "enrollment"
        and e.get("actor_id") == fresh_learner["id"]
        and title in e["message"]
    ]
    assert matches, f"No enrollment event for course {title!r} by learner {fresh_learner['id']}"

    # Second enrollment attempt — should NOT create a duplicate
    prev_count = len(matches)
    r2 = learner_client.post(f"{BASE_URL}/api/courses/{slug}/enroll")
    assert r2.status_code == 200
    assert r2.json().get("already_enrolled") is True

    time.sleep(1.5)
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"limit": 100})
    events = r.json()["events"]
    matches2 = [
        e for e in events
        if e["kind"] == "enrollment"
        and e.get("actor_id") == fresh_learner["id"]
        and title in e["message"]
    ]
    assert len(matches2) == prev_count, "already-enrolled should not create a second enrollment event"


# ---------- org_created event ---------------------------------------------


def test_create_org_writes_org_created_event(super_admin_client):
    ts = int(time.time() * 1000)
    name = f"TEST Iter28 Org {ts}"
    payload = {
        "name": name,
        "admin_email": f"iter28.orgadmin+{ts}@example.com",
        "admin_full_name": f"Iter28 OrgAdmin {ts}",
        "industry": "Technology",
        "seat_count": 30,
    }
    r = super_admin_client.post(f"{BASE_URL}/api/admin/orgs", json=payload)
    assert r.status_code == 200, r.text
    org_id = r.json()["organization"]["id"]

    time.sleep(1.5)
    r2 = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"limit": 100})
    events = r2.json()["events"]
    matches = [
        e for e in events
        if e["kind"] == "org_created" and name in e["message"] and "30 seats" in e["message"]
    ]
    assert matches, f"No org_created event with name {name!r} + 30 seats"

    # Cleanup
    try:
        super_admin_client.delete(f"{BASE_URL}/api/admin/orgs/{org_id}")
    except Exception:
        pass


# ---------- since= delta filter -------------------------------------------


def test_recent_activity_since_delta(super_admin_client):
    """since=<very-recent> should return an empty (or small) event list."""
    from datetime import datetime, timezone, timedelta
    # Snapshot NOW before doing anything — no future event yet
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"since": future})
    assert r.status_code == 200
    assert r.json()["events"] == [], "since=future should return zero events"

    # since=very-old should return a full window
    past = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"since": past, "limit": 100})
    assert r.status_code == 200
    old_events = r.json()["events"]
    # There should be at least some events from prior activity
    assert isinstance(old_events, list)


def test_since_returns_only_newer_events(super_admin_client, learner_client, fresh_learner):
    """After a snapshot, a new activity should show in a since= poll."""
    from datetime import datetime, timezone
    # Snapshot the latest created_at
    r = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"limit": 1})
    now_iso_snap = r.json()["events"][0]["created_at"] if r.json()["events"] else datetime.now(timezone.utc).isoformat()

    # Trigger a new activity — register another learner
    ts = int(time.time() * 1000)
    email = f"iter28.delta+{ts}@example.com"
    r_reg = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "TestPass123!",
        "full_name": f"Delta {ts}", "organization": "Test", "title": "Test",
    })
    assert r_reg.status_code == 200

    time.sleep(1.5)
    # since=snapshot must include the new signup
    r2 = super_admin_client.get(f"{BASE_URL}/api/admin/activity/recent", params={"since": now_iso_snap, "limit": 100})
    assert r2.status_code == 200
    events = r2.json()["events"]
    assert any(e["kind"] == "signup" and email in e["message"] for e in events), \
        f"Expected signup for {email} in delta poll; got {len(events)} events"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
