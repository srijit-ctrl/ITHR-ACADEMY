# Load tests — ITHR Academy

Locust-based load testing for the public read surface + the demo AI streaming
endpoint. Isolated from unit tests so it never runs in CI.

## What's covered

| Endpoint | Weight | Target p95 |
| :-- | --: | --: |
| `GET /api/courses` | 10 | < 800 ms |
| `GET /api/intelligence/briefing` | 6 | < 900 ms |
| `GET /api/podcast/latest` | 5 | < 400 ms |
| `GET /api/podcast/rss.xml` | 3 | < 500 ms |
| `POST /api/demo/ask` (SSE) | 1 | < 3.5 s to first byte |

The demo endpoint uses the Emergent LLM key — its weight is deliberately low
to bound cost per run.

## Running locally

```bash
pip install locust
cd /app/backend/tests/load
locust -f locustfile.py \
       --host https://enterprise-ai-learn-2.preview.emergentagent.com \
       --headless -u 25 -r 5 -t 2m
```

- `-u 25` → 25 concurrent virtual users
- `-r 5`  → ramp 5 users/sec until target reached
- `-t 2m` → run 2 minutes
- `--headless` → no web UI, prints stats to stdout at the end

Add `--csv=./out` to persist per-endpoint stats to CSV.

## Interpreting results

Locust prints a per-endpoint table at the end. Focus on:
- **`# fails`** — should be 0 (or very close). Any 5xx is a real bug.
- **`Med`, `95%ile`** — compare against the thresholds above.
- **`# reqs/s`** — throughput headroom. If p95 balloons at low RPS your
  bottleneck is likely a hot Mongo query or Python endpoint; profile with
  `py-spy` or add a `core_cache.py` entry.

## Running against production

```bash
locust -f locustfile.py --host https://ithr.online --headless -u 10 -r 2 -t 2m
```

Start conservative on prod — the demo endpoint hits the LLM and the platform
runs on a shared K8s node. Ramp gradually.

## Known caveats

- Locust counts a 302/307 redirect as its own request; the `/api/courses` path
  should not redirect but if you see one, check the ingress config.
- `POST /api/demo/ask` may return `429` (rate-limited by IP) after ~20 rapid
  requests from the same source — that's the platform's protection working,
  not a bug. Reduce concurrency or add sleep between iterations.
- `EMERGENT_LLM_KEY` credits are consumed by the demo task — keep runs short.
