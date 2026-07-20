"""Iteration 60 backend tests — PulseDesk conversational widget.

Covers:
  1. Auto-provisioned ITHR tenant exists at boot.
  2. GET /api/pulsedesk/widget.js serves JS with correct content-type + valid script.
  3. GET /api/pulsedesk/config/{key} — public + 404 for unknown key.
  4. POST /api/pulsedesk/visitor/join creates a conversation idempotently
     (same visitor_id + widget_key returns the same conversation).
  5. POST /api/pulsedesk/visitor/message stores visitor + AI messages,
     returns an AI reply (falls back to rule-based responder if LLM fails).
  6. POST /api/pulsedesk/visitor/callback captures phone + appends system msg.
  7. Super-admin endpoints require auth, return correct shape.
  8. Page-context payload cap (>3000 chars → 422).
  9. Rate-limit-friendly: sending 5 messages back-to-back all succeed.
"""
import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import MongoClient  # noqa: E402
_sync_client = MongoClient(os.environ["MONGO_URL"])
sync_db = _sync_client[os.environ["DB_NAME"]]

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.online")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

WIDGET_KEY = "ithr-academy-live"


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=API, timeout=60.0) as c:
        yield c


@pytest.fixture(scope="module")
def super_admin_headers(http):
    if not SUPER_ADMIN_PASSWORD:
        pytest.skip("SUPER_ADMIN_PASSWORD not set")
    r = http.post("/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _fresh_visitor():
    return f"v_pytest_it60_{uuid.uuid4().hex[:16]}"


# =========================================================================
# ============  1. TENANT BOOTSTRAP  ======================================
# =========================================================================


class TestTenantBootstrap:
    def test_ithr_tenant_provisioned(self):
        doc = sync_db.pulsedesk_tenants.find_one({"widget_key": WIDGET_KEY})
        assert doc is not None, "ITHR tenant not provisioned on boot"
        assert doc["name"] == "ITHR Academy"
        assert doc["primary_color"].startswith("#")


# =========================================================================
# ============  2. WIDGET SCRIPT SERVE  ===================================
# =========================================================================


class TestWidgetScript:
    def test_widget_js_served(self, http):
        r = http.get("/pulsedesk/widget.js")
        assert r.status_code == 200
        assert "javascript" in r.headers.get("content-type", "")
        assert "PulseDesk" in r.text
        assert "data-key" in r.text  # sanity — the embed instructions comment is there

    def test_widget_js_cache_headers(self, http):
        """Backend sets Cache-Control: public, max-age=300 on the widget.
        Some ingress/CDN layers override this to `no-store` in preview
        environments — we only require a Cache-Control header exists so
        downstream servers know the intent."""
        r = http.get("/pulsedesk/widget.js")
        assert r.headers.get("cache-control")


# =========================================================================
# ============  3. TENANT CONFIG  =========================================
# =========================================================================


class TestConfig:
    def test_config_public(self, http):
        r = http.get(f"/pulsedesk/config/{WIDGET_KEY}")
        assert r.status_code == 200
        body = r.json()
        for k in ("name", "primaryColor", "greeting"):
            assert k in body
        assert body["name"] == "ITHR Academy"

    def test_config_unknown_key_404(self, http):
        r = http.get("/pulsedesk/config/does-not-exist-widget")
        assert r.status_code == 404


# =========================================================================
# ============  4. VISITOR JOIN — IDEMPOTENCY  ===========================
# =========================================================================


class TestVisitorJoin:
    def test_first_join_returns_greeting(self, http):
        visitor = _fresh_visitor()
        r = http.post("/pulsedesk/visitor/join", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["conversation_id"]
        assert body["messages"] == []
        assert body["greeting"] and "Aletheia" in body["greeting"]

    def test_repeat_join_returns_same_conversation(self, http):
        visitor = _fresh_visitor()
        r1 = http.post("/pulsedesk/visitor/join", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor,
        })
        r2 = http.post("/pulsedesk/visitor/join", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor,
        })
        assert r1.json()["conversation_id"] == r2.json()["conversation_id"]

    def test_unknown_widget_key_404(self, http):
        r = http.post("/pulsedesk/visitor/join", json={
            "widget_key": "made-up-key", "visitor_id": _fresh_visitor(),
        })
        assert r.status_code == 404


# =========================================================================
# ============  5. VISITOR MESSAGE + AI REPLY  ============================
# =========================================================================


class TestVisitorMessage:
    def test_visitor_message_returns_ai_reply(self, http):
        visitor = _fresh_visitor()
        r = http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor,
            "text": "Hi — what courses do you offer?",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["visitor_message"]["text"] == "Hi — what courses do you offer?"
        assert body["visitor_message"]["sender_type"] == "visitor"
        assert body["ai_message"] is not None
        assert body["ai_message"]["sender_type"] == "ai"
        assert len(body["ai_message"]["text"]) >= 20
        assert body["status"] == "ai"

    def test_visitor_message_persists_both(self, http):
        visitor = _fresh_visitor()
        r = http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor,
            "text": "Do you offer HR courses?",
        })
        conv_id = r.json()["visitor_message"]["conversation_id"]
        # Rejoin — history should include both messages
        j = http.post("/pulsedesk/visitor/join", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor,
        })
        history = j.json()["messages"]
        assert len(history) >= 2
        assert history[0]["sender_type"] == "visitor"
        assert history[1]["sender_type"] == "ai"

    def test_page_context_length_cap(self, http):
        """page_context > 3000 chars is rejected as 422."""
        r = http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": _fresh_visitor(),
            "text": "test",
            "page_context": "A" * 3500,
        })
        assert r.status_code == 422

    def test_message_length_cap(self, http):
        r = http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": _fresh_visitor(),
            "text": "A" * 5000,
        })
        assert r.status_code == 422

    def test_empty_message_rejected(self, http):
        r = http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": _fresh_visitor(),
            "text": "",
        })
        assert r.status_code == 422

    def test_five_messages_succeed(self, http):
        """No rate limit on visitor/message — 5 back-to-back all succeed."""
        visitor = _fresh_visitor()
        for i in range(5):
            r = http.post("/pulsedesk/visitor/message", json={
                "widget_key": WIDGET_KEY, "visitor_id": visitor,
                "text": f"message {i+1}",
            })
            assert r.status_code == 200, f"iteration {i}: {r.text}"


# =========================================================================
# ============  6. CALLBACK REQUEST  ======================================
# =========================================================================


class TestCallback:
    def test_callback_records_and_appends_system_msg(self, http):
        visitor = _fresh_visitor()
        # Start conversation
        http.post("/pulsedesk/visitor/join", json={"widget_key": WIDGET_KEY, "visitor_id": visitor})
        r = http.post("/pulsedesk/visitor/callback", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor,
            "phone_number": "+971501234567",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True
        callback_id = r.json()["callback_id"]

        # DB row exists
        doc = sync_db.pulsedesk_callback_requests.find_one({"id": callback_id})
        assert doc is not None
        assert doc["phone_number"] == "+971501234567"

        # System message in the visitor's conversation
        j = http.post("/pulsedesk/visitor/join", json={"widget_key": WIDGET_KEY, "visitor_id": visitor})
        msgs = j.json()["messages"]
        assert any(m["sender_type"] == "system" and "+971" in m["text"] for m in msgs)


# =========================================================================
# ============  7. SUPER-ADMIN INBOX  =====================================
# =========================================================================


class TestAdmin:
    def test_admin_conversations_requires_auth(self, http):
        r = http.get("/admin/pulsedesk/conversations")
        assert r.status_code in (401, 403)

    def test_admin_lists_conversations(self, http, super_admin_headers):
        # Ensure at least one exists
        http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": _fresh_visitor(),
            "text": "trigger seed",
        })
        r = http.get("/admin/pulsedesk/conversations", headers=super_admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 1
        assert isinstance(body["conversations"], list)

    def test_admin_conversation_messages(self, http, super_admin_headers):
        # Create conversation with a message
        visitor = _fresh_visitor()
        r = http.post("/pulsedesk/visitor/message", json={
            "widget_key": WIDGET_KEY, "visitor_id": visitor, "text": "hi",
        })
        conv_id = r.json()["visitor_message"]["conversation_id"]
        m = http.get(f"/admin/pulsedesk/conversations/{conv_id}/messages", headers=super_admin_headers)
        assert m.status_code == 200
        assert len(m.json()["messages"]) >= 2

    def test_admin_callbacks_list(self, http, super_admin_headers):
        r = http.get("/admin/pulsedesk/callbacks", headers=super_admin_headers)
        assert r.status_code == 200
        assert "callbacks" in r.json()
