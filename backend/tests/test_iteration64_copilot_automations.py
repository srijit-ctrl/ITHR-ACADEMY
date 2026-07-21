"""Iteration 64 — Super-admin Phase 3 (Copilot) + Phase 5 (Automations) backend tests.

Covers:
  - GET /api/admin/copilot/snapshot — returns real-time platform snapshot.
  - POST /api/admin/copilot/chat — SSE stream (open + delta + done events).
  - POST /api/admin/copilot/reset — issues new session id.
  - GET /api/admin/automations/meta — trigger + action catalog.
  - CRUD flow — GET list → POST create → toggle → test dry-run → runs list → DELETE.
  - Enterprise-lead trigger dispatch (regression on run_automations_for_trigger hook).
"""
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=API, timeout=60.0) as c:
        yield c


@pytest.fixture(scope="module")
def sa_headers(http):
    if not SUPER_ADMIN_PASSWORD:
        pytest.skip("SUPER_ADMIN_PASSWORD not set")
    r = http.post("/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token, f"No token in login response: {r.json()}"
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Phase 3 — Copilot backend
# ============================================================================
class TestCopilotSnapshot:
    def test_snapshot_unauth(self, http):
        r = http.get("/admin/copilot/snapshot")
        assert r.status_code in (401, 403)

    def test_snapshot_shape(self, http, sa_headers):
        r = http.get("/admin/copilot/snapshot", headers=sa_headers)
        assert r.status_code == 200
        j = r.json()
        # Required keys per contract
        for key in ("users", "orgs", "learning", "revenue_30d_usd", "alerts_open", "agent_os", "pulsedesk_conversations_24h"):
            assert key in j, f"Missing key {key} in snapshot: {list(j)}"
        assert isinstance(j["users"], dict)
        assert "total" in j["users"]
        assert isinstance(j["revenue_30d_usd"], (int, float))
        assert isinstance(j["alerts_open"], int)


class TestCopilotReset:
    def test_reset_returns_new_session(self, http, sa_headers):
        r = http.post("/admin/copilot/reset", headers=sa_headers)
        assert r.status_code == 200
        assert r.json().get("session_id", "").startswith("copilot-")


class TestCopilotChatSSE:
    """SSE stream — assert we see event: open, event: delta (>=1), event: done."""

    def test_chat_stream_events(self, sa_headers):
        # Use streaming client so we don't buffer forever.
        url = f"{API}/admin/copilot/chat"
        payload = {"message": "Reply with a very short one-sentence acknowledgment only.", "session_id": f"test-{uuid.uuid4().hex[:8]}"}
        with httpx.Client(timeout=45.0) as c:
            with c.stream("POST", url, json=payload, headers={**sa_headers, "Accept": "text/event-stream"}) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "").lower()
                events_seen = []
                delta_count = 0
                for line in resp.iter_lines():
                    if not line:
                        continue
                    if line.startswith("event:"):
                        ev = line.split(":", 1)[1].strip()
                        events_seen.append(ev)
                        if ev == "delta":
                            delta_count += 1
                    if "done" in events_seen:
                        break
        assert "open" in events_seen, f"No open event: {events_seen[:20]}"
        assert delta_count >= 1, f"No delta events: {events_seen[:20]}"
        assert "done" in events_seen, f"No done event: {events_seen[:30]}"


# ============================================================================
# Phase 5 — Automations backend
# ============================================================================
class TestAutomationsMeta:
    def test_meta_returns_registries(self, http, sa_headers):
        r = http.get("/admin/automations/meta", headers=sa_headers)
        assert r.status_code == 200
        j = r.json()
        assert "triggers" in j and "actions" in j and "condition_ops" in j
        assert "enterprise_lead_created" in j["triggers"]
        assert "send_slack_message" in j["actions"]
        assert "contains" in j["condition_ops"]


class TestAutomationCRUD:
    """Create → Toggle → Test dry-run → Runs → Delete round-trip."""

    def test_full_lifecycle(self, http, sa_headers):
        # 1) LIST — starts at some state; capture initial count
        r = http.get("/admin/automations", headers=sa_headers)
        assert r.status_code == 200
        initial = r.json()["automations"]
        initial_ids = {row["id"] for row in initial}

        # 2) CREATE
        payload = {
            "name": f"TEST_lifecycle_{uuid.uuid4().hex[:6]}",
            "description": "iteration_64 lifecycle test",
            "trigger": "enterprise_lead_created",
            "conditions": [{"field": "bundle", "op": "contains", "value": "talent"}],
            "actions": [{"action": "send_slack_message", "params": {"text": "New lead {{email}} · {{bundle}}"}}],
            "enabled": True,
        }
        r = http.post("/admin/automations", json=payload, headers=sa_headers)
        assert r.status_code == 200, r.text
        row = r.json()
        rule_id = row["id"]
        assert row["name"] == payload["name"]
        assert row["trigger"] == "enterprise_lead_created"
        assert row["enabled"] is True
        assert len(row["conditions"]) == 1
        assert len(row["actions"]) == 1

        # 3) GET-list — the new row should be present
        r = http.get("/admin/automations", headers=sa_headers)
        assert r.status_code == 200
        all_ids = {row["id"] for row in r.json()["automations"]}
        assert rule_id in all_ids
        assert rule_id not in initial_ids

        # 4) TOGGLE — flip enabled off
        r = http.post(f"/admin/automations/{rule_id}/toggle", headers=sa_headers)
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        # Toggle back on
        r = http.post(f"/admin/automations/{rule_id}/toggle", headers=sa_headers)
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        # 5) TEST dry-run — matching payload → should match + 1 action
        r = http.post(
            f"/admin/automations/{rule_id}/test",
            json={"payload": {"bundle": "talent-development", "email": "x@y.com"}, "dry_run": True},
            headers=sa_headers,
        )
        assert r.status_code == 200
        j = r.json()
        assert j["dry_run"] is True
        assert j["result"]["matched"] is True
        assert len(j["result"]["actions"]) == 1
        assert j["result"]["actions"][0]["action"] == "send_slack_message"

        # 5b) TEST dry-run — non-matching → matched False
        r = http.post(
            f"/admin/automations/{rule_id}/test",
            json={"payload": {"bundle": "leadership", "email": "z@y.com"}, "dry_run": True},
            headers=sa_headers,
        )
        assert r.status_code == 200
        assert r.json()["result"]["matched"] is False

        # 6) RUNS list — dry-runs may or may not be recorded, but endpoint returns 200
        r = http.get(f"/admin/automations/{rule_id}/runs", headers=sa_headers)
        assert r.status_code == 200
        assert "runs" in r.json()

        # 7) DELETE
        r = http.delete(f"/admin/automations/{rule_id}", headers=sa_headers)
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        # 8) Verify gone
        r = http.get("/admin/automations", headers=sa_headers)
        assert r.status_code == 200
        assert rule_id not in {row["id"] for row in r.json()["automations"]}

    def test_invalid_trigger_rejected(self, http, sa_headers):
        payload = {
            "name": "TEST_invalid",
            "trigger": "not_a_real_trigger",
            "actions": [{"action": "send_slack_message", "params": {"text": "x"}}],
        }
        r = http.post("/admin/automations", json=payload, headers=sa_headers)
        assert r.status_code == 400

    def test_invalid_action_rejected(self, http, sa_headers):
        payload = {
            "name": "TEST_invalid_action",
            "trigger": "enterprise_lead_created",
            "actions": [{"action": "unknown_action", "params": {}}],
        }
        r = http.post("/admin/automations", json=payload, headers=sa_headers)
        assert r.status_code == 400

    def test_delete_missing_returns_404(self, http, sa_headers):
        r = http.delete(f"/admin/automations/does-not-exist-{uuid.uuid4().hex[:6]}", headers=sa_headers)
        assert r.status_code == 404


class TestAutomationTriggerDispatchOnLead:
    """Regression: /api/leads/enterprise POST invokes run_automations_for_trigger."""

    def test_enterprise_lead_dispatch(self, http, sa_headers):
        # Create a rule that matches any enterprise lead
        payload = {
            "name": f"TEST_dispatch_{uuid.uuid4().hex[:6]}",
            "trigger": "enterprise_lead_created",
            "conditions": [],  # match all
            "actions": [{"action": "create_audit_entry", "params": {"action": "automation.test_lead", "detail": "auto-fired by iteration64 test"}}],
            "enabled": True,
        }
        r = http.post("/admin/automations", json=payload, headers=sa_headers)
        assert r.status_code == 200, r.text
        rule_id = r.json()["id"]

        try:
            # Submit an enterprise lead (this endpoint is public — no auth needed)
            lead_email = f"test-iter64-{uuid.uuid4().hex[:6]}@example.com"
            lead_resp = http.post("/leads/enterprise", json={
                "name": "Iter64 Tester",
                "email": lead_email,
                "company": "Iter64 Co",
                "bundle": "talent-development",
                "seats": 5,
            })
            # The endpoint may be 200 or 201
            assert lead_resp.status_code in (200, 201), f"Lead POST failed: {lead_resp.status_code} {lead_resp.text}"

            # Give the fire-and-forget task a moment to run
            time.sleep(2.0)

            # Check runs were logged
            r = http.get(f"/admin/automations/{rule_id}/runs", headers=sa_headers)
            assert r.status_code == 200
            runs = r.json().get("runs", [])
            # At least one non-dry-run should have executed
            live_runs = [x for x in runs if not x.get("dry_run")]
            assert len(live_runs) >= 1, f"Expected >=1 live run, got: {runs}"
        finally:
            http.delete(f"/admin/automations/{rule_id}", headers=sa_headers)
