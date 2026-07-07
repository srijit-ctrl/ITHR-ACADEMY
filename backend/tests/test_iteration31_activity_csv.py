"""Iter-31 — Super-admin Activity Feed CSV export.

Endpoint under test:
    GET /api/admin/activity/export.csv

Covers:
- Auth gating (401 anon, 403 non-super-admin)
- Response headers (Content-Type text/csv, Content-Disposition attachment)
- CSV shape: header row present, data rows follow schema
- Filters: kind=<value>, since=<iso>, limit clamp
- target_json column is well-formed JSON when present, empty string otherwise
"""
import csv
import io
import json
import os
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://voice-tutor-labs.preview.emergentagent.com"
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@ithr.tech")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "preview-only-rotate-in-prod")

EXPORT_URL = f"{BASE_URL}/api/admin/activity/export.csv"


@pytest.fixture(scope="module")
def super_admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD,
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def learner_token():
    ts = int(time.time() * 1000)
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": f"iter31.csv+{ts}@example.com",
        "password": "TestPass123!",
        "full_name": f"Iter31 CSV {ts}",
        "organization": "Test", "title": "Analyst",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---- auth gating -------------------------------------------------------


def test_export_requires_auth():
    r = requests.get(EXPORT_URL)
    assert r.status_code in (401, 403), r.status_code


def test_export_forbidden_for_learner(learner_token):
    r = requests.get(EXPORT_URL, headers={"Authorization": f"Bearer {learner_token}"})
    assert r.status_code == 403, r.text


# ---- response headers --------------------------------------------------


def test_export_content_type_and_disposition(super_admin_token):
    r = requests.get(EXPORT_URL, headers={"Authorization": f"Bearer {super_admin_token}"})
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert ".csv" in cd.lower()


# ---- csv shape ---------------------------------------------------------


def test_export_csv_header_row_and_columns(super_admin_token):
    r = requests.get(f"{EXPORT_URL}?limit=5", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert r.status_code == 200
    reader = csv.reader(io.StringIO(r.text))
    rows = list(reader)
    assert rows, "CSV should have at least a header row"
    assert rows[0] == ["created_at", "kind", "actor_id", "actor_name", "message", "target_json"]
    # Data rows (if any) should also have 6 columns
    for row in rows[1:]:
        assert len(row) == 6, f"expected 6 cols, got {len(row)}: {row}"


def test_export_target_json_is_valid(super_admin_token):
    """target_json cell is either empty string or parseable JSON."""
    r = requests.get(f"{EXPORT_URL}?limit=100", headers={"Authorization": f"Bearer {super_admin_token}"})
    reader = csv.reader(io.StringIO(r.text))
    next(reader)  # skip header
    for row in reader:
        target_col = row[5]
        if target_col:
            parsed = json.loads(target_col)
            assert isinstance(parsed, dict), f"target_json should decode to a dict, got {type(parsed)}"


# ---- filters -----------------------------------------------------------


def test_export_kind_filter(super_admin_token):
    """kind=signup should only return signup rows."""
    r = requests.get(f"{EXPORT_URL}?kind=signup&limit=200", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert r.status_code == 200
    reader = csv.reader(io.StringIO(r.text))
    next(reader)  # skip header
    kinds = {row[1] for row in reader}
    if kinds:  # only check if there were any events
        assert kinds == {"signup"}, f"kind=signup filter leaked other kinds: {kinds}"


def test_export_since_future_returns_only_header(super_admin_token):
    r = requests.get(f"{EXPORT_URL}?since=2099-01-01T00:00:00Z", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert r.status_code == 200
    lines = [ln for ln in r.text.split("\n") if ln.strip()]
    assert len(lines) == 1, f"future-since should return only the header row, got {len(lines)} lines"


def test_export_limit_clamp_high(super_admin_token):
    """Limit above the cap (10000) should be rejected (422 fastapi validation)."""
    r = requests.get(f"{EXPORT_URL}?limit=999999", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert r.status_code == 422, f"expected 422 clamp rejection, got {r.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
