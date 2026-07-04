"""Iteration 8 — Verify existing certificate EAIA-2026-FK78B1 PDF endpoint after WeasyPrint deps install."""
import os
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
CERT_ID = "EAIA-2026-FK78B1"


def test_existing_cert_verify_public():
    r = requests.get(f"{API}/certificates/verify/{CERT_ID}", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["valid"] is True
    assert d["certificate"]["certificate_id"] == CERT_ID


def test_existing_cert_pdf_export():
    r = requests.get(f"{API}/certificates/{CERT_ID}/pdf", timeout=60)
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
    ct = r.headers.get("Content-Type", "")
    assert "application/pdf" in ct, f"unexpected content-type: {ct}"
    body = r.content
    assert len(body) > 10_000, f"PDF too small: {len(body)} bytes"
    assert body.startswith(b"%PDF-"), f"missing PDF magic bytes: {body[:8]!r}"
    cd = r.headers.get("Content-Disposition", "")
    assert CERT_ID in cd, f"cert id not in Content-Disposition: {cd}"
