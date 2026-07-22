"""Iteration 74 — launch-readiness bug list backend tests.

Covers:
 - CRITICAL #1: /api/intelligence/briefing must not hang; returns within
   ~30s with a briefing payload OR 504/error (never open-ended stream).
 - CRITICAL #3: /api/mentor/chat grounds course titles in the live catalog.
 - CRITICAL #4/#5: /legal/* markdown files exist, have no unfilled tokens,
   proper branding (ITHR Technologies Consulting LLC, ithr.online),
   Privacy Policy exists and retains the "DRAFT" line.
 - HIGH #6: /api/courses search filters (prompt / RAG).
 - HIGH #8: /robots.txt and /sitemap.xml served as real files, not React shell.
 - BRANDING: no user-facing 'ithr.tech' / 'FZ-LLC' / 'learn.ithr.tech' in
   legal markdowns; enterprise contact is enterprise@ithr.online.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

import httpx
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_PASSWORD = "TestPass123!"

FRONTEND_PUBLIC = Path("/app/frontend/public")
LEGAL_DIR = FRONTEND_PUBLIC / "legal"

# ---------------------------------------------------------------- helpers ----


def _register_learner():
    email = f"qa74-{uuid.uuid4().hex[:10]}@example.com"
    r = httpx.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "full_name": "QA74"},
        timeout=20,
    )
    r.raise_for_status()
    return email, r.json()["token"]


# ============================================================ CRITICAL #1 ====


class TestIntelligenceBriefingNoHang:
    def test_briefing_completes_within_30s(self):
        """GET /api/intelligence/briefing must respond within 30s.

        It is anonymous (no auth guard) — either 200 with payload,
        or 504/502 on timeout — but NEVER hang.
        """
        start = time.time()
        try:
            r = httpx.get(f"{BASE_URL}/api/intelligence/briefing", timeout=30)
        except httpx.ReadTimeout:
            pytest.fail(
                f"Intelligence briefing hung >30s (client timeout). "
                f"Backend must enforce its 18s server timeout."
            )
        elapsed = time.time() - start
        assert elapsed < 30, f"briefing endpoint took {elapsed:.1f}s (>=30s)"
        assert r.status_code in (200, 502, 504), (
            f"unexpected status {r.status_code}: {r.text[:200]}"
        )
        if r.status_code == 200:
            payload = r.json()
            # Cache hit or fresh must expose some briefing shape
            assert (
                "signals" in payload
                or "from_cache" in payload
                or "generated_at" in payload
            ), f"200 briefing missing expected keys: {list(payload)[:8]}"


# ============================================================ CRITICAL #3 ====


class TestMentorGroundedInCatalog:
    def test_mentor_titles_match_catalog(self):
        """Ask Solon for course titles, verify each verbatim in /api/courses."""
        _, token = _register_learner()
        # Snapshot the real catalog
        cat = httpx.get(f"{BASE_URL}/api/courses", timeout=20)
        cat.raise_for_status()
        catalog_titles = {c["title"] for c in cat.json() if c.get("title")}
        assert len(catalog_titles) >= 20, "unexpectedly small catalog"

        # SSE stream — collect deltas over the reply
        prompt = (
            "List EXACTLY 4 ITHR Academy course titles you'd recommend for "
            "someone moving into agentic AI. Return each title on its own line "
            "with NO commentary, NO numbering, NO quotes — just the raw title "
            "text, copied verbatim from the catalog."
        )
        session_id = str(uuid.uuid4())
        collected: list[str] = []
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.stream(
                "POST",
                f"{BASE_URL}/api/mentor/chat",
                json={"message": prompt, "session_id": session_id},
                headers=headers,
                timeout=45,
            ) as resp:
                assert resp.status_code == 200, (
                    f"mentor stream returned {resp.status_code}"
                )
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        obj = json.loads(line[6:])
                    except Exception:
                        continue
                    if "delta" in obj:
                        collected.append(obj["delta"])
                    if obj.get("done"):
                        break
        except httpx.ReadTimeout:
            pytest.fail("mentor stream hung >45s")

        full = "".join(collected).strip()
        assert full, "mentor produced empty reply"
        print(f"\n[MENTOR REPLY]\n{full}\n[/MENTOR]")

        # Extract candidate course titles: lines with letters, strip markdown
        candidates: list[str] = []
        for raw in full.splitlines():
            s = raw.strip()
            if not s:
                continue
            # Strip bullets/numbers/markdown emphasis
            s = re.sub(r"^[-*•\d.\)\s]+", "", s)
            s = s.strip("*_`\"' ")
            # Drop trailing dashes/comma/period
            s = re.sub(r"[.,;:—–\-]+$", "", s).strip()
            if len(s) < 6 or len(s) > 120:
                continue
            candidates.append(s)

        # Find titles the model returned that look like course-title lines
        # (heuristic: any candidate that ~matches a catalog title exactly counts)
        hits: list[str] = []
        misses: list[str] = []
        for c in candidates:
            if c in catalog_titles:
                hits.append(c)
            else:
                # Only report as miss if the line looks like a title claim,
                # not a full sentence. Heuristic: <=8 words AND capitalised.
                words = c.split()
                if (
                    2 <= len(words) <= 12
                    and words[0][:1].isupper()
                    and not c.endswith(".")
                ):
                    misses.append(c)

        print(f"[HITS: {hits}]  [MISSES: {misses}]")
        # At least some grounding — model returned >=2 exact catalog titles
        assert len(hits) >= 2, (
            f"Mentor returned <2 exact catalog titles. Hits={hits}, "
            f"Misses(candidate title-shaped lines)={misses}, full={full[:600]}"
        )
        # And no fabricated titles that look like course claims
        assert not misses, (
            f"Mentor cited titles NOT in the catalog (hallucination risk): "
            f"{misses}"
        )


# ==================================================== CRITICAL #4/#5 =========


class TestLegalDocs:
    """Legal markdown source files (rendered by /legal/* pages)."""

    LEGAL_KEYS = ["terms", "disclaimer", "compliance", "privacy"]

    def _load(self, key: str) -> str:
        return (LEGAL_DIR / f"{key}.md").read_text(encoding="utf-8")

    def test_privacy_exists(self):
        p = LEGAL_DIR / "privacy.md"
        assert p.exists(), "privacy.md missing"
        raw = p.read_text(encoding="utf-8")
        assert "# Privacy Policy" in raw, "no Privacy Policy heading"
        assert "GDPR" in raw and "PDPL" in raw, "no GDPR/PDPL sections"

    def test_no_unfilled_template_tokens(self):
        """No `{{ FOO }}` tokens with keys the renderer doesn't know."""
        known = {
            "EFFECTIVE_DATE",
            "CONTACT_EMAIL",
            "LEGAL_EMAIL",
            "BILLING_EMAIL",
            "PRIVACY_EMAIL",
            "SECURITY_EMAIL",
            "ENTERPRISE_EMAIL",
            "SOC2_TARGET",
            "ISO_TARGET",
            "ISO_42001_TARGET",
        }
        pat = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")
        for k in self.LEGAL_KEYS:
            raw = self._load(k)
            for m in pat.finditer(raw):
                assert m.group(1) in known, (
                    f"{k}.md contains unknown/unfilled token: {m.group(0)}"
                )

    def test_correct_entity_and_domain(self):
        for k in self.LEGAL_KEYS:
            raw = self._load(k)
            assert "ITHR Technologies Consulting LLC" in raw, (
                f"{k}.md missing correct legal entity"
            )
            assert "FZ-LLC" not in raw, f"{k}.md still contains 'FZ-LLC'"
            assert "ithr.tech" not in raw, f"{k}.md still contains 'ithr.tech'"
            assert "learn.ithr.tech" not in raw, (
                f"{k}.md still contains 'learn.ithr.tech'"
            )
            # Domain must appear in the rendered content — either literally
            # or via an _EMAIL placeholder (all _EMAIL tokens resolve to
            # <name>@ithr.online in the LegalDoc renderer's PLACEHOLDERS map).
            has_domain = "ithr.online" in raw or re.search(r"\{\{\s*[A-Z0-9_]*EMAIL[A-Z0-9_]*\s*\}\}", raw)
            assert has_domain, f"{k}.md must reference 'ithr.online' (directly or via _EMAIL token)"

    def test_draft_line_preserved(self):
        for k in self.LEGAL_KEYS:
            raw = self._load(k)
            assert "DRAFT" in raw.upper(), f"{k}.md must retain a DRAFT notice"


# ================================================================ HIGH #6 ====


class TestCatalogSearchFilters:
    def test_search_prompt(self):
        r = httpx.get(
            f"{BASE_URL}/api/courses",
            params={"q": "prompt"},
            timeout=15,
        )
        assert r.status_code == 200
        titles = [c["title"] for c in r.json()]
        assert any("Prompt Engineering Mastery" in t for t in titles), (
            f"'prompt' search must surface Prompt Engineering Mastery; got {titles}"
        )
        # Non-matching search MUST narrow (sanity check that ?q= actually filters)
        r2 = httpx.get(
            f"{BASE_URL}/api/courses",
            params={"q": "zzzzznotarealtopic"},
            timeout=15,
        )
        assert r2.status_code == 200
        assert len(r2.json()) == 0, "unmatched search should return 0 results"

    def test_search_rag(self):
        r = httpx.get(
            f"{BASE_URL}/api/courses",
            params={"q": "RAG"},
            timeout=15,
        )
        assert r.status_code == 200
        titles = [c["title"] for c in r.json()]
        slugs = [c.get("slug") for c in r.json()]
        assert any(
            "Retrieval-Augmented" in t or slug == "rag-enterprise"
            for t, slug in zip(titles, slugs)
        ), f"'RAG' search must surface rag-enterprise; got {list(zip(titles, slugs))}"
        assert r.status_code == 200
        titles = [c["title"] for c in r.json()]
        slugs = [c.get("slug") for c in r.json()]
        assert any(
            "Retrieval-Augmented" in t or slug == "rag-enterprise"
            for t, slug in zip(titles, slugs)
        ), f"'RAG' search must surface rag-enterprise; got {list(zip(titles, slugs))}"


# ================================================================ HIGH #8 ====


class TestStaticSeoFiles:
    def test_robots_txt(self):
        r = httpx.get(f"{BASE_URL}/robots.txt", timeout=10, follow_redirects=True)
        assert r.status_code == 200
        body = r.text
        assert not body.lstrip().lower().startswith("<!doctype"), (
            "robots.txt returned React HTML shell — must be plain text"
        )
        assert "User-agent" in body, "robots.txt missing User-agent"
        assert "Sitemap:" in body, "robots.txt missing Sitemap line"

    def test_sitemap_xml(self):
        r = httpx.get(f"{BASE_URL}/sitemap.xml", timeout=10, follow_redirects=True)
        assert r.status_code == 200
        body = r.text
        assert not body.lstrip().lower().startswith("<!doctype"), (
            "sitemap.xml returned React HTML shell — must be XML"
        )
        assert body.lstrip().startswith("<?xml"), "sitemap.xml missing <?xml prolog"
        assert "<urlset" in body, "sitemap.xml missing <urlset>"
        assert "/courses/" in body, "sitemap.xml should list course URLs"


# ================================================================ BRANDING ====


class TestBrandingRegression:
    def test_no_stale_brand_in_legal_docs(self):
        for key in ["terms", "disclaimer", "compliance", "privacy", "security"]:
            p = LEGAL_DIR / f"{key}.md"
            if not p.exists():
                continue
            raw = p.read_text(encoding="utf-8")
            for bad in ("ithr.tech", "learn.ithr.tech", "FZ-LLC"):
                assert bad not in raw, f"{key}.md still contains stale token '{bad}'"

    def test_enterprise_email_is_ithr_online(self):
        raw = (LEGAL_DIR / "compliance.md").read_text(encoding="utf-8")
        # The token is filled at render time; source uses {{ ENTERPRISE_EMAIL }}
        assert "ENTERPRISE_EMAIL" in raw or "enterprise@ithr.online" in raw
