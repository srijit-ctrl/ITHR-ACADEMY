"""Tests for /api/trust/procurement-pack endpoint (iter 10)."""
import io
import os
import re
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://enterprise-ai-learn-2.preview.emergentagent.com").rstrip("/")
ENDPOINT = f"{BASE_URL}/api/trust/procurement-pack"

EXPECTED_ENTRIES = {
    "README.txt",
    "SECURITY_FACTSHEET.pdf",
    "SUB_PROCESSORS.pdf",
    "DPA_TEMPLATE.pdf",
    "COMPLIANCE_DOSSIER.pdf",
}


@pytest.fixture(scope="module")
def pack_response():
    r = requests.get(ENDPOINT, timeout=60)
    return r


class TestProcurementPack:
    def test_status_200(self, pack_response):
        assert pack_response.status_code == 200, f"Body: {pack_response.text[:300]}"

    def test_content_type_zip(self, pack_response):
        assert "application/zip" in pack_response.headers.get("Content-Type", "").lower()

    def test_content_disposition(self, pack_response):
        cd = pack_response.headers.get("Content-Disposition", "")
        assert "ITHR-Academy-Procurement-Pack" in cd, f"Got: {cd}"
        assert re.search(r"ITHR-Academy-Procurement-Pack-\d{8}\.zip", cd), f"filename pattern: {cd}"

    def test_body_size_over_50kb(self, pack_response):
        size = len(pack_response.content)
        assert size > 50_000, f"Body too small: {size} bytes"

    def test_zip_has_exactly_5_entries(self, pack_response):
        zf = zipfile.ZipFile(io.BytesIO(pack_response.content))
        names = set(zf.namelist())
        assert names == EXPECTED_ENTRIES, f"Got: {names}"

    def test_pdfs_have_magic_bytes_and_over_5kb(self, pack_response):
        zf = zipfile.ZipFile(io.BytesIO(pack_response.content))
        for name in EXPECTED_ENTRIES:
            if not name.endswith(".pdf"):
                continue
            data = zf.read(name)
            assert data[:4] == b"%PDF", f"{name} missing magic bytes: {data[:8]}"
            assert len(data) > 5_000, f"{name} too small: {len(data)}"

    def test_readme_has_content(self, pack_response):
        zf = zipfile.ZipFile(io.BytesIO(pack_response.content))
        readme = zf.read("README.txt").decode()
        assert "ITHR Academy" in readme
        assert "Procurement Pack" in readme
