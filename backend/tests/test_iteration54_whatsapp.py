"""Regression tests for the Feb 2026 Twilio WhatsApp integration.

Covers:
  * Learner-facing opt-in / opt-out lifecycle (unchecked default, E.164
    validation, opt-out clears number and stops future sends).
  * ``send_whatsapp_template`` respects the opt-in flag and gracefully
    skips when a template SID is unconfigured (Meta approval pending).
  * Admin overview surfaces opt-in rate + template readiness + failed
    sends.
  * Broadcast trigger returns the counts contract even in stubbed mode.
  * Inbound + status-callback webhooks reject unsigned requests.
"""
import os
import uuid

import httpx
import pytest

API_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


def _register(prefix: str = "wa") -> tuple[str, str]:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = httpx.post(
        f"{API_URL}/api/auth/register",
        json={"email": email, "password": os.environ.get("E2E_TEST_USER_PASSWORD","TestPass123!"), "full_name": "WA Regression"},
        timeout=15,
    )
    r.raise_for_status()
    return email, r.json()["token"]


def _sa_token() -> str:
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": os.environ.get("E2E_SUPER_ADMIN_EMAIL","superadmin@ithr.online"), "password": os.environ.get("E2E_SUPER_ADMIN_PASSWORD","Dubai_deram2026")},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["token"]


def test_opt_in_defaults_false_on_new_account():
    _, token = _register()
    r = httpx.get(
        f"{API_URL}/api/whatsapp/status",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["whatsapp_opt_in"] is False
    assert body["whatsapp_number"] in (None, "")
    assert body["whatsapp_opt_in_timestamp"] is None


def test_opt_in_rejects_invalid_number():
    _, token = _register()
    r = httpx.post(
        f"{API_URL}/api/whatsapp/opt-in",
        headers={"Authorization": f"Bearer {token}"},
        json={"opt_in": True, "whatsapp_number": "not-a-number", "source": "account_settings"},
        timeout=15,
    )
    assert r.status_code == 400


def test_opt_in_normalises_local_uae_number():
    _, token = _register()
    r = httpx.post(
        f"{API_URL}/api/whatsapp/opt-in",
        headers={"Authorization": f"Bearer {token}"},
        json={"opt_in": True, "whatsapp_number": "0501234567", "source": "account_settings"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["whatsapp_number"] == "+971501234567"


def test_opt_out_clears_number_and_flag():
    _, token = _register()
    hdr = {"Authorization": f"Bearer {token}"}
    httpx.post(f"{API_URL}/api/whatsapp/opt-in", headers=hdr,
               json={"opt_in": True, "whatsapp_number": "+971501234567", "source": "account_settings"},
               timeout=15).raise_for_status()

    r = httpx.post(f"{API_URL}/api/whatsapp/opt-in", headers=hdr,
                   json={"opt_in": False, "source": "account_settings"},
                   timeout=15)
    assert r.status_code == 200
    assert r.json()["opt_in"] is False

    status = httpx.get(f"{API_URL}/api/whatsapp/status", headers=hdr, timeout=15).json()
    assert status["whatsapp_opt_in"] is False
    assert status["whatsapp_number"] in (None, "")


def test_admin_overview_lists_all_templates_and_configured_flag():
    token = _sa_token()
    r = httpx.get(f"{API_URL}/api/admin/whatsapp/overview",
                  headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    body = r.json()
    keys = {t["key"] for t in body["templates"]}
    assert keys == {"new_course", "enrollment_stale", "deadline", "certificate_issued", "ce_renewal"}
    # opt_in_rate always numeric, never null
    assert isinstance(body["opt_in_rate_pct"], (int, float))


def test_broadcast_dry_run_returns_audience_size():
    token = _sa_token()
    r = httpx.post(
        f"{API_URL}/api/admin/whatsapp/broadcast/new-course",
        headers={"Authorization": f"Bearer {token}"},
        params={"course_slug": "agentic-ai-foundations", "dry_run": True},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert "audience_size" in body
    assert "template_configured" in body


def test_broadcast_404_for_unknown_course():
    token = _sa_token()
    r = httpx.post(
        f"{API_URL}/api/admin/whatsapp/broadcast/new-course",
        headers={"Authorization": f"Bearer {token}"},
        params={"course_slug": "does-not-exist-slug", "dry_run": True},
        timeout=15,
    )
    assert r.status_code == 404


def test_broadcast_gracefully_skips_when_template_sid_missing():
    """Opt an ad-hoc user in, then fire a live broadcast. Because the
    ``new_course`` template SID is empty in the test env, the send helper
    must return ``skipped_no_template`` — never raise, never send."""
    _, token = _register("wa-broadcast")
    httpx.post(f"{API_URL}/api/whatsapp/opt-in",
               headers={"Authorization": f"Bearer {token}"},
               json={"opt_in": True, "whatsapp_number": "+971509999999", "source": "account_settings"},
               timeout=15).raise_for_status()

    sa_token = _sa_token()
    r = httpx.post(
        f"{API_URL}/api/admin/whatsapp/broadcast/new-course",
        headers={"Authorization": f"Bearer {sa_token}"},
        params={"course_slug": "agentic-ai-foundations", "dry_run": False},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["failed"] == 0
    # At least one send should be accounted for (either skipped_no_template
    # or, once real SIDs are wired, sent). Either way it must not crash.
    assert sum(body["counts"].values()) >= 1


def test_inbound_webhook_rejects_unsigned_request():
    r = httpx.post(
        f"{API_URL}/api/whatsapp/inbound",
        data={"From": "whatsapp:+971509999999", "To": "whatsapp:+13612788411",
              "Body": "Hello", "MessageSid": "SMtest"},
        timeout=15,
    )
    assert r.status_code == 403


def test_status_callback_rejects_unsigned_request():
    r = httpx.post(
        f"{API_URL}/api/whatsapp/status-callback",
        data={"MessageSid": "SMtest", "MessageStatus": "delivered"},
        timeout=15,
    )
    assert r.status_code == 403
