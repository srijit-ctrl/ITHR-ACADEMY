"""
Load test — ITHR Academy public read-heavy endpoints + demo SSE.

Run against the preview environment first:

  cd /app/backend/tests/load
  pip install locust
  locust -f locustfile.py --host https://voice-tutor-labs.preview.emergentagent.com --headless -u 25 -r 5 -t 2m

Flags:
  -u : concurrent virtual users
  -r : ramp-up rate (users per second)
  -t : run duration
  --headless : no web UI, print stats to stdout

Target thresholds (informal SLOs):
  /api/courses                p95 < 800ms   (list, cached)
  /api/podcast/latest         p95 < 400ms   (single doc, no audio)
  /api/podcast/rss.xml        p95 < 500ms   (aggregation over episodes)
  /api/intelligence/briefing  p95 < 900ms   (cached briefing)
  POST /api/demo/ask (SSE)    p95 < 3.5s to first byte  (LLM-dependent, low weight)

The demo/ask task is deliberately weighted low (weight=1 vs the reads' weight=5-10)
because each call burns Emergent LLM credits.
"""
from __future__ import annotations

import json
import random

from locust import HttpUser, between, task

DEMO_PROMPTS = [
    "What is an AI agent, in one paragraph?",
    "Give me two examples of agentic AI in banking.",
    "How is Aletheia different from a chatbot?",
    "Explain the risk of prompt injection.",
]


class PublicReader(HttpUser):
    """Simulates an anonymous visitor browsing the public surface."""

    # 1-4 seconds between requests keeps traffic realistic (human dwell)
    wait_time = between(1, 4)

    def on_start(self):
        # Warm up: hit landing so the SPA + CDN are ready
        self.client.get("/", name="00-landing (bootstrap)")

    @task(10)
    def course_catalog(self):
        with self.client.get("/api/courses", name="GET /api/courses", catch_response=True) as r:
            if r.status_code == 200:
                try:
                    data = r.json()
                    if not isinstance(data, list) or len(data) < 5:
                        r.failure(f"unexpected shape (len={len(data) if isinstance(data, list) else 'not-list'})")
                except Exception as e:
                    r.failure(f"bad json: {e}")
            else:
                r.failure(f"status={r.status_code}")

    @task(6)
    def intelligence_briefing(self):
        with self.client.get("/api/intelligence/briefing", name="GET /api/intelligence/briefing", catch_response=True) as r:
            if r.status_code == 200:
                try:
                    d = r.json()
                    if not d.get("signals"):
                        r.failure("no signals")
                except Exception as e:
                    r.failure(f"bad json: {e}")
            else:
                r.failure(f"status={r.status_code}")

    @task(5)
    def podcast_latest(self):
        with self.client.get("/api/podcast/latest", name="GET /api/podcast/latest", catch_response=True) as r:
            # 404 is acceptable in a fresh env with no episodes generated
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"status={r.status_code}")

    @task(3)
    def podcast_rss(self):
        with self.client.get("/api/podcast/rss.xml", name="GET /api/podcast/rss.xml", catch_response=True) as r:
            if r.status_code == 200 and r.text.startswith("<?xml"):
                r.success()
            else:
                r.failure(f"status={r.status_code} body_start={r.text[:40]!r}")

    # ---- AI-critical (low weight — burns LLM credits) ----
    @task(1)
    def demo_ask_streaming(self):
        """POST /api/demo/ask returns SSE. We stream and measure time-to-final-byte."""
        prompt = random.choice(DEMO_PROMPTS)
        payload = {"message": prompt}
        headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
        with self.client.post(
            "/api/demo/ask",
            data=json.dumps(payload),
            headers=headers,
            name="POST /api/demo/ask (SSE)",
            catch_response=True,
            stream=True,
            timeout=30,
        ) as r:
            if r.status_code != 200:
                r.failure(f"status={r.status_code}")
                return
            bytes_read = 0
            try:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        bytes_read += len(chunk)
                        # Stop reading after ~4KB — enough to prove the SSE stream works,
                        # keeps LLM cost per test bounded.
                        if bytes_read > 4096:
                            break
                if bytes_read == 0:
                    r.failure("empty SSE body")
                else:
                    r.success()
            except Exception as e:
                r.failure(f"stream error: {e}")
