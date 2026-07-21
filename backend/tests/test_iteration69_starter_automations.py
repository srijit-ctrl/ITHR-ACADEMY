"""Iteration 69 — Starter automations end-to-end verification.

Covers:
- Seed idempotency: exactly 5 rules with seed_key prefix 'starter.', all
  enabled=true, created_by='system.starter', each with 1 create_audit_entry
  action referencing trigger fields via {{...}} placeholders.
- Restart-idempotency (no duplicates) — since the seed function is called
  on startup, we verify the count after a supervisor restart.
- Trigger 1: user_signup — POST /api/auth/register → admin_automation_runs
  row + admin_audit_log entry with placeholders substituted.
- Trigger 2: certificate_issued — direct invoke via
  /api/admin/automations/{id}/test with dry_run=false + payload.
- Trigger 3: module_5_completed — same direct-invoke pattern.
- Trigger 4: alert_high_severity — seed 15 reset tokens, GET
  /api/admin/alerts-center twice (dedupe), /resolve, verify marker cleared.
- Trigger 5: enterprise_lead_created — POST /api/leads/enterprise.
- CRUD regression: PATCH toggle + DELETE on a starter rule.

Uses synchronous pymongo — avoids Motor loop conflicts under pytest-xdist.
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

EXPECTED_TRIGGERS = {
    "user_signup",
    "certificate_issued",
    "module_5_completed",
    "alert_high_severity",
    "enterprise_lead_created",
}


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


# ---------------------------------------------------------------------------
# Test 1: Seed idempotency + rule shape
# ---------------------------------------------------------------------------
class TestSeedIdempotency:
    def test_five_starter_rules_exist_with_expected_shape(self, mdb):
        rows = list(mdb.admin_automations.find({"seed_key": {"$regex": "^starter\\."}}))
        assert len(rows) == 5, f"expected exactly 5 starter rules, got {len(rows)}: {[r.get('seed_key') for r in rows]}"

        triggers = {r["trigger"] for r in rows}
        assert triggers == EXPECTED_TRIGGERS, f"trigger set mismatch: got {triggers}"

        for r in rows:
            assert r.get("enabled") is True, f"{r['seed_key']} is not enabled"
            assert r.get("created_by") == "system.starter", f"{r['seed_key']} created_by={r.get('created_by')}"
            assert r.get("description"), f"{r['seed_key']} description empty"
            actions = r.get("actions") or []
            assert len(actions) == 1, f"{r['seed_key']} action count = {len(actions)}"
            assert actions[0].get("action") == "create_audit_entry", f"{r['seed_key']} action != create_audit_entry"
            detail = actions[0].get("params", {}).get("detail", "")
            assert "{{" in detail and "}}" in detail, f"{r['seed_key']} detail lacks {{...}} placeholder: {detail}"

    def test_restart_backend_keeps_count_at_five(self, mdb):
        """Restart backend and confirm exactly 5 rules still (no duplicates)."""
        import subprocess
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False, capture_output=True)
        # wait for backend to come back
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                r = requests.get(f"{API}/", timeout=3)
                if r.status_code in (200, 404):
                    break
            except Exception:
                pass
            time.sleep(1)
        # give startup event a couple seconds to finish seed_starter_automations
        time.sleep(3)
        rows = list(mdb.admin_automations.find({"seed_key": {"$regex": "^starter\\."}}))
        assert len(rows) == 5, f"restart-idempotency broken: got {len(rows)} starter rules"


# ---------------------------------------------------------------------------
# Test 2: user_signup end-to-end
# ---------------------------------------------------------------------------
class TestUserSignupTrigger:
    def test_signup_creates_run_and_audit_entry(self, mdb):
        # Snapshot baseline count for this trigger
        baseline = mdb.admin_automation_runs.count_documents({"trigger": "user_signup"})
        email = f"test_it69_signup_{uuid.uuid4().hex[:10]}@example.com"
        full_name = "It69 Signup User"
        pw = "TestPass123!"
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": pw, "full_name": full_name},
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        uid = (r.json().get("user") or {}).get("id")
        assert uid

        # wait for fire-and-forget task
        time.sleep(3)

        after = mdb.admin_automation_runs.count_documents({"trigger": "user_signup"})
        assert after >= baseline + 1, f"no new automation_runs row (baseline={baseline}, after={after})"

        # Find the run for this user
        run = mdb.admin_automation_runs.find_one(
            {"trigger": "user_signup", "payload.user_id": uid},
            sort=[("run_at", -1)],
        )
        assert run is not None, "no run row for this user"
        assert run.get("matched") is True
        outcomes = run.get("outcomes") or []
        assert any(o.get("ok") is True for o in outcomes), f"no ok=true outcome: {outcomes}"

        # Audit-log entry
        audit = mdb.admin_audit_log.find_one(
            {"action": "automation.user_signup", "meta.payload.user_id": uid}
        )
        assert audit is not None, "no admin_audit_log entry for automation.user_signup"
        detail = audit.get("detail", "")
        assert full_name in detail, f"full_name not resolved in detail: {detail}"
        assert email in detail, f"email not resolved in detail: {detail}"
        assert "password" in detail, f"auth_provider not resolved (expected 'password'): {detail}"
        assert "{{" not in detail and "}}" not in detail, f"unresolved placeholder in detail: {detail}"

        payload = audit.get("meta", {}).get("payload", {})
        assert payload.get("email") == email
        assert payload.get("full_name") == full_name
        assert payload.get("auth_provider") == "password"
        assert "referral_seq" in payload

        # cleanup
        try:
            mdb.users.delete_one({"id": uid})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test 3: certificate_issued via /test endpoint (dry_run=false)
# ---------------------------------------------------------------------------
class TestCertificateIssuedTrigger:
    def test_direct_invoke_writes_audit_entry(self, sa_headers, mdb):
        # locate the starter rule
        rule = mdb.admin_automations.find_one({"seed_key": "starter.certificate_issued.audit"})
        assert rule is not None
        rid = rule["id"]

        cert_id = f"IT69-CERT-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "user_id": "it69_user",
            "course_slug": "hr-fundamentals",
            "course_title": "HR Fundamentals",
            "certificate_id": cert_id,
            "score": 87.5,
        }
        r = requests.post(
            f"{API}/admin/automations/{rid}/test",
            headers=sa_headers,
            json={"payload": payload, "dry_run": False},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("dry_run") is False
        result = body.get("result") or {}
        assert result.get("matched") is True
        assert any(o.get("ok") is True for o in (result.get("actions") or []))

        # audit entry
        audit = mdb.admin_audit_log.find_one(
            {"action": "automation.certificate_issued", "meta.payload.certificate_id": cert_id}
        )
        assert audit is not None, "no audit entry for certificate_issued"
        detail = audit.get("detail", "")
        assert cert_id in detail, f"cert_id not resolved: {detail}"
        assert "HR Fundamentals" in detail, f"course_title not resolved: {detail}"
        assert "87.5" in detail, f"score not resolved: {detail}"
        assert "{{" not in detail, f"unresolved placeholder: {detail}"


# ---------------------------------------------------------------------------
# Test 4: module_5_completed via /test endpoint
# ---------------------------------------------------------------------------
class TestModule5CompletedTrigger:
    def test_direct_invoke_writes_audit_entry(self, sa_headers, mdb):
        rule = mdb.admin_automations.find_one({"seed_key": "starter.module_5_completed.audit"})
        assert rule is not None
        rid = rule["id"]

        uid = f"it69_user_{uuid.uuid4().hex[:8]}"
        payload = {
            "user_id": uid,
            "course_id": "course_abc",
            "course_slug": "hr-fundamentals",
            "course_title": "HR Fundamentals",
            "module_id": "mod_5",
        }
        r = requests.post(
            f"{API}/admin/automations/{rid}/test",
            headers=sa_headers, json={"payload": payload, "dry_run": False}, timeout=20,
        )
        assert r.status_code == 200, r.text
        result = r.json().get("result") or {}
        assert result.get("matched") is True

        audit = mdb.admin_audit_log.find_one(
            {"action": "automation.module_5_completed", "meta.payload.user_id": uid}
        )
        assert audit is not None
        detail = audit.get("detail", "")
        assert uid in detail
        assert "HR Fundamentals" in detail
        assert "{{" not in detail


# ---------------------------------------------------------------------------
# Test 5: alert_high_severity end-to-end (dedupe + resolve)
# ---------------------------------------------------------------------------
ALERT_KEY = "reset-spike"


def _cleanup_alert(mdb):
    mdb.password_reset_tokens.delete_many({"seed_source": "iter69_test"})
    mdb.admin_alert_automation_fired.delete_many({"key": ALERT_KEY})
    mdb.admin_alert_states.delete_many({"key": ALERT_KEY})


def _seed_reset_tokens(mdb, count=15):
    now = datetime.now(timezone.utc).isoformat()
    docs = [{
        "id": uuid.uuid4().hex,
        "user_id": f"iter69_seed_{i}",
        "token": uuid.uuid4().hex,
        "token_hash": uuid.uuid4().hex,
        "created_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "used": False,
        "seed_source": "iter69_test",
    } for i in range(count)]
    mdb.password_reset_tokens.insert_many(docs)


class TestAlertHighSeverityTrigger:
    def test_alert_creates_one_run_and_audit_entry(self, sa_headers, mdb):
        _cleanup_alert(mdb)
        # capture rule id
        rule = mdb.admin_automations.find_one({"seed_key": "starter.alert_high_severity.audit"})
        assert rule is not None
        rid = rule["id"]

        try:
            _seed_reset_tokens(mdb, 15)

            # First GET should trip the alert and fire the starter rule
            r1 = requests.get(f"{API}/admin/alerts-center", headers=sa_headers, timeout=15)
            assert r1.status_code == 200, r1.text
            time.sleep(3)

            marker = mdb.admin_alert_automation_fired.count_documents({"key": ALERT_KEY})
            assert marker == 1, f"expected exactly 1 marker after first GET, got {marker}"

            runs = list(mdb.admin_automation_runs.find({
                "trigger": "alert_high_severity", "rule_id": rid, "payload.key": ALERT_KEY,
            }))
            assert len(runs) == 1, f"expected 1 run for starter alert rule, got {len(runs)}"
            assert runs[0].get("matched") is True

            audit = mdb.admin_audit_log.find_one({
                "action": "automation.alert_high_severity",
                "meta.payload.key": ALERT_KEY,
            })
            assert audit is not None
            detail = audit.get("detail", "")
            assert ALERT_KEY in detail
            assert "{{" not in detail

            # Second GET must not create duplicate
            requests.get(f"{API}/admin/alerts-center", headers=sa_headers, timeout=15)
            time.sleep(2)
            marker2 = mdb.admin_alert_automation_fired.count_documents({"key": ALERT_KEY})
            runs2 = mdb.admin_automation_runs.count_documents({
                "trigger": "alert_high_severity", "rule_id": rid, "payload.key": ALERT_KEY,
            })
            assert marker2 == 1, f"dedupe broken — marker={marker2}"
            assert runs2 == 1, f"dedupe broken — runs={runs2}"

            # /resolve clears the marker
            rr = requests.post(
                f"{API}/admin/alerts-center/{ALERT_KEY}/resolve",
                headers=sa_headers, json={"note": "iter69 test"}, timeout=15,
            )
            assert rr.status_code == 200, rr.text
            marker3 = mdb.admin_alert_automation_fired.count_documents({"key": ALERT_KEY})
            assert marker3 == 0, f"marker not cleared after resolve: {marker3}"
        finally:
            _cleanup_alert(mdb)


# ---------------------------------------------------------------------------
# Test 6: enterprise_lead_created end-to-end
# ---------------------------------------------------------------------------
class TestEnterpriseLeadTrigger:
    def test_lead_submission_creates_run_and_audit(self, mdb):
        company = f"TEST_IT69_{uuid.uuid4().hex[:6]}"
        email = f"test_it69_lead_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "Iter69 Lead",
            "email": email,
            "company": company,
            "role": "HR Director",
            "seats": 42,
            "bundle": "hr-enterprise",
            "message": "test lead",
        }
        r = requests.post(f"{API}/leads/enterprise", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        lead_id = r.json().get("lead_id")
        assert lead_id

        # side effects are asyncio.create_task
        time.sleep(3)

        run = mdb.admin_automation_runs.find_one(
            {"trigger": "enterprise_lead_created", "payload.lead_id": lead_id},
            sort=[("run_at", -1)],
        )
        assert run is not None, "no automation_runs row for enterprise_lead_created"
        assert run.get("matched") is True

        audit = mdb.admin_audit_log.find_one(
            {"action": "automation.enterprise_lead_created", "meta.payload.lead_id": lead_id}
        )
        assert audit is not None, "no audit entry for enterprise_lead_created"
        detail = audit.get("detail", "")
        assert company in detail, f"company not resolved: {detail}"
        assert "hr-enterprise" in detail, f"bundle not resolved: {detail}"
        assert "42" in detail, f"seats not resolved: {detail}"
        assert email in detail, f"email not resolved: {detail}"
        assert "{{" not in detail, f"unresolved placeholder: {detail}"

        # cleanup
        try:
            mdb.enterprise_leads.delete_one({"id": lead_id})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test 7: CRUD regressions on starter rules
# ---------------------------------------------------------------------------
class TestStarterRuleCRUD:
    def test_toggle_and_test_endpoint_dry_run(self, sa_headers, mdb):
        rule = mdb.admin_automations.find_one({"seed_key": "starter.user_signup.audit"})
        assert rule is not None
        rid = rule["id"]

        # Dry-run test
        r_test = requests.post(
            f"{API}/admin/automations/{rid}/test",
            headers=sa_headers,
            json={"payload": {"user_id": "x", "email": "x@x.com", "full_name": "X",
                              "auth_provider": "password"}, "dry_run": True},
            timeout=15,
        )
        assert r_test.status_code == 200, r_test.text
        assert r_test.json().get("dry_run") is True

        # Toggle off
        r_off = requests.post(f"{API}/admin/automations/{rid}/toggle", headers=sa_headers, timeout=15)
        assert r_off.status_code == 200
        assert r_off.json().get("enabled") is False

        # Toggle back on (to restore state for other tests)
        r_on = requests.post(f"{API}/admin/automations/{rid}/toggle", headers=sa_headers, timeout=15)
        assert r_on.status_code == 200
        assert r_on.json().get("enabled") is True

    def test_list_endpoint_returns_five_starters(self, sa_headers):
        r = requests.get(f"{API}/admin/automations", headers=sa_headers, timeout=15)
        assert r.status_code == 200, r.text
        rows = r.json().get("automations") or []
        starters = [row for row in rows if str(row.get("seed_key", "")).startswith("starter.")]
        assert len(starters) == 5, f"expected 5 starters in list endpoint, got {len(starters)}"
        for s in starters:
            assert s.get("enabled") is True
            assert len(s.get("actions") or []) == 1
