"""Iter-26: Credential Impressions widget backend tests.

Covers:
  - GET /api/certificates/verify/<real-cert-id> inserts a verify_impressions row,
    idempotent on same-IP-same-day, unique impression_key = sha256(cert|day|ip)
  - SAMPLE-ITHR-2026-001 verify is explicitly excluded from impressions
  - GET /api/certificates/impressions (authenticated) returns aggregated + per-cert
  - Auth required for /certificates/impressions (no token → 401/403)
  - Mongo indexes: impression_key (unique), user_id, (certificate_id, day)
"""
import hashlib
import os
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

LEARNER_EMAIL = os.environ.get("EAIA_IMPRESSIONS_TEST_EMAIL", "impressions-test@example.com")
LEARNER_PASSWORD = os.environ.get("EAIA_IMPRESSIONS_TEST_PASSWORD", "TestPass123!")
REAL_CERT_ID = "IMPR-TEST-2026-XYZ"
SAMPLE_CERT_ID = "SAMPLE-ITHR-2026-001"


@pytest.fixture(scope="module")
def mongo_db():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": LEARNER_EMAIL, "password": LEARNER_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Seeded learner login failed: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


# ---------- Mongo Indexes ----------
class TestIndexes:
    def test_verify_impressions_indexes(self, mongo_db):
        info = mongo_db.verify_impressions.index_information()
        assert "impression_key_1" in info, f"missing impression_key index: {list(info)}"
        assert info["impression_key_1"].get("unique") is True, "impression_key not unique"
        assert "user_id_1" in info, f"missing user_id index: {list(info)}"
        # compound (certificate_id, day)
        compound = [k for k, v in info.items() if v["key"] == [("certificate_id", 1), ("day", 1)]]
        assert compound, f"missing compound (certificate_id, day) index: {list(info)}"


# ---------- Sample cert suppression ----------
class TestSampleCertSuppression:
    def test_sample_verify_does_not_create_impression(self, mongo_db):
        before = mongo_db.verify_impressions.count_documents({"certificate_id": SAMPLE_CERT_ID})
        # 3 hits to sample
        for _ in range(3):
            r = requests.get(f"{BASE_URL}/api/certificates/verify/{SAMPLE_CERT_ID}", timeout=10)
            assert r.status_code == 200, r.text
            assert r.json().get("valid") is True
        after = mongo_db.verify_impressions.count_documents({"certificate_id": SAMPLE_CERT_ID})
        assert after == before == 0, f"SAMPLE should never create impressions (before={before}, after={after})"


# ---------- Verify + dedup ----------
class TestVerifyImpressionDedup:
    def test_verify_real_cert_creates_and_dedups(self, mongo_db):
        """Dedup verification.

        NOTE: `request.client.host` in FastAPI reflects the immediate TCP peer,
        which behind the k8s ingress is the ingress pod's IP — and the ingress
        runs multiple replicas. So repeated requests from the same origin can
        surface 2–3 distinct source IPs to the backend. That's a real product
        concern (documented in the test report) but per-IP-per-day dedup itself
        still works: the count plateaus after a small burst. We verify the
        plateau rather than a strict "1 row per burst".
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mongo_db.verify_impressions.delete_many({
            "certificate_id": REAL_CERT_ID, "day": today,
        })

        # First burst of 10 hits — count should end up ≤ small (ingress pool size)
        for _ in range(10):
            r = requests.get(f"{BASE_URL}/api/certificates/verify/{REAL_CERT_ID}", timeout=10)
            assert r.status_code == 200 and r.json()["valid"] is True
        after_burst_1 = mongo_db.verify_impressions.count_documents({
            "certificate_id": REAL_CERT_ID, "day": today,
        })
        assert 1 <= after_burst_1 <= 5, (
            f"expected dedup to plateau at ≤5 rows for 10 same-origin hits, got {after_burst_1}"
        )

        # Second burst of 10 — count MUST NOT grow (already deduped)
        for _ in range(10):
            r = requests.get(f"{BASE_URL}/api/certificates/verify/{REAL_CERT_ID}", timeout=10)
            assert r.status_code == 200
        after_burst_2 = mongo_db.verify_impressions.count_documents({
            "certificate_id": REAL_CERT_ID, "day": today,
        })
        assert after_burst_2 == after_burst_1, (
            f"dedup broken across bursts: {after_burst_1} → {after_burst_2}"
        )

    def test_different_ip_or_day_creates_new_row(self, mongo_db):
        """Simulate different verifier via direct impression_key seeding (as noted
        in the review request — FastAPI's request.client.host cannot be spoofed
        via X-Forwarded-For in this environment)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        user_id = mongo_db.certificates.find_one({"certificate_id": REAL_CERT_ID})["user_id"]
        before = mongo_db.verify_impressions.count_documents({"certificate_id": REAL_CERT_ID})

        fake_ip = "203.0.113.42"
        impression_key = hashlib.sha256(f"{REAL_CERT_ID}|{today}|{fake_ip}".encode()).hexdigest()
        # Cleanup if it exists from a previous run
        mongo_db.verify_impressions.delete_one({"impression_key": impression_key})

        mongo_db.verify_impressions.insert_one({
            "impression_key": impression_key,
            "certificate_id": REAL_CERT_ID,
            "user_id": user_id,
            "day": today,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "ip_hash_short": hashlib.sha256(fake_ip.encode()).hexdigest()[:12],
        })
        after = mongo_db.verify_impressions.count_documents({"certificate_id": REAL_CERT_ID})
        assert after == before + 1

        # Attempting the same insert again should raise duplicate-key
        from pymongo.errors import DuplicateKeyError
        with pytest.raises(DuplicateKeyError):
            mongo_db.verify_impressions.insert_one({
                "impression_key": impression_key,
                "certificate_id": REAL_CERT_ID,
                "user_id": user_id,
                "day": today,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "ip_hash_short": "dup",
            })


# ---------- /certificates/impressions endpoint ----------
class TestImpressionsEndpoint:
    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/certificates/impressions", timeout=10)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text[:200]}"

    def test_returns_shape_and_matches_db(self, auth_token, mongo_db):
        # Ensure the learner has ≥3 impressions across ≥2 distinct days by seeding
        # deterministic rows (some past, one for today). This is a controlled
        # setup independent of the flaky ingress-IP dedup behavior.
        user_id = mongo_db.certificates.find_one({"certificate_id": REAL_CERT_ID})["user_id"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for day, ip in [(today, "10.0.0.1"), ("2026-07-01", "10.0.0.2"), ("2026-07-02", "10.0.0.3")]:
            key = hashlib.sha256(f"{REAL_CERT_ID}|{day}|{ip}".encode()).hexdigest()
            mongo_db.verify_impressions.update_one(
                {"impression_key": key},
                {"$setOnInsert": {
                    "impression_key": key,
                    "certificate_id": REAL_CERT_ID,
                    "user_id": user_id,
                    "day": day,
                    "verified_at": f"{day}T12:00:00+00:00",
                    "ip_hash_short": hashlib.sha256(ip.encode()).hexdigest()[:12],
                }},
                upsert=True,
            )

        r = requests.get(
            f"{BASE_URL}/api/certificates/impressions",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(["total_all_time", "total_last_30d", "total_this_month", "by_certificate"]).issubset(data.keys())
        assert isinstance(data["total_all_time"], int)
        assert isinstance(data["total_last_30d"], int)
        assert isinstance(data["total_this_month"], int)
        assert isinstance(data["by_certificate"], list)

        db_total = mongo_db.verify_impressions.count_documents({"user_id": user_id})
        assert data["total_all_time"] == db_total, f"api {data['total_all_time']} != db {db_total}"
        assert data["total_all_time"] >= 3

        # monthly ≤ 30d ≤ all_time
        assert data["total_this_month"] <= data["total_last_30d"] <= data["total_all_time"]

    def test_by_certificate_sorted_desc(self, auth_token):
        r = requests.get(
            f"{BASE_URL}/api/certificates/impressions",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10,
        )
        assert r.status_code == 200
        bc = r.json()["by_certificate"]
        assert bc, "by_certificate should not be empty for seeded learner"
        counts = [c["impressions"] for c in bc]
        assert counts == sorted(counts, reverse=True), f"not sorted desc: {counts}"
        # Verify each entry shape + IMPR-TEST-2026-XYZ present with course_title
        first = bc[0]
        for k in ("certificate_id", "course_title", "impressions"):
            assert k in first
        target = next((c for c in bc if c["certificate_id"] == REAL_CERT_ID), None)
        assert target is not None, f"expected {REAL_CERT_ID} in by_certificate: {bc}"
        assert target["impressions"] >= 3
        assert target["course_title"], "course_title should not be empty"

    def test_impressions_bad_token_rejected(self):
        r = requests.get(
            f"{BASE_URL}/api/certificates/impressions",
            headers={"Authorization": "Bearer not-a-real-token"},
            timeout=10,
        )
        assert r.status_code in (401, 403)


# ---------- Email throttle sanity (behavior-only) ----------
class TestEmailThrottleGuard:
    def test_duplicate_verify_does_not_re_alert(self, mongo_db):
        """Because dedup insert fails on the unique index for same-IP-same-day,
        is_new_impression = False → the email branch is skipped. We can't observe
        the send directly (fire-and-forget), so we verify the DB side: no row-count
        change and no last_verify_alert_at bump between duplicate hits."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Ensure at least one prior row exists so the next hit is a duplicate
        mongo_db.verify_impressions.delete_many({
            "certificate_id": REAL_CERT_ID, "day": today,
        })
        requests.get(f"{BASE_URL}/api/certificates/verify/{REAL_CERT_ID}", timeout=10)

        cert_before = mongo_db.certificates.find_one({"certificate_id": REAL_CERT_ID}, {"_id": 0, "last_verify_alert_at": 1})
        rows_before = mongo_db.verify_impressions.count_documents({"certificate_id": REAL_CERT_ID, "day": today})
        # Duplicate hit
        requests.get(f"{BASE_URL}/api/certificates/verify/{REAL_CERT_ID}", timeout=10)
        cert_after = mongo_db.certificates.find_one({"certificate_id": REAL_CERT_ID}, {"_id": 0, "last_verify_alert_at": 1})
        rows_after = mongo_db.verify_impressions.count_documents({"certificate_id": REAL_CERT_ID, "day": today})

        assert rows_after == rows_before, "duplicate should not create new impression"
        assert cert_after.get("last_verify_alert_at") == cert_before.get("last_verify_alert_at"), \
            "duplicate should not bump last_verify_alert_at (email suppressed)"
