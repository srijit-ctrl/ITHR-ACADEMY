# ITHR Enterprise Agentic AI Academy — Cost & Infrastructure Sheet

**Internal use only — ITHR Technologies FZ-LLC**
**Author:** Platform Engineering
**Version:** v1.0 · February 2026
**Distribution:** ITHR founders, CFO, Head of Ops, Head of Sales

> All figures in USD unless stated. Numbers use retail list prices at
> Feb-2026 rates. AWS is used as the reference cloud; the same
> topology maps 1:1 to GCP / Azure with ±10% variance. Add **25% VAT
> (US billing)** or **5% VAT (UAE billing)** at invoice time —
> excluded from the tables below to keep the unit-economics clean.

---

## 1. Executive summary

| Traffic tier | Monthly active users | Monthly infra cost | Cost/MAU | Rev per MAU @ retail | Gross margin |
|---|---|---|---|---|---|
| **Seed** (launch, ≤500 founders) | 500 | **$412** | $0.82 | $0 (perk) | −100% (planned) |
| **Early** | 2,500 | **$1,155** | $0.46 | $18–$45 | 88–98% |
| **Growth** | 15,000 | **$5,780** | $0.39 | $22–$48 | 92–99% |
| **Scale** | 60,000 | **$21,400** | $0.36 | $22–$48 | 93–99% |
| **Enterprise-heavy** | 250,000 | **$78,500** | $0.31 | $22–$48 | 94–99% |

**Take-aways:**
- The dominant cost driver above 2,500 MAU is **LLM inference**
  (~55% of infra spend). Everything else is broadly fixed.
- Break-even on infra alone is **~30 paying learners** at $22/month.
- Break-even including headcount + G&A (see §7) is **~1,800 paying
  learners** at blended $32/month ARPU.
- The founding-member perk (first 500 with free modules 6-15 +
  free cert) has a total cost of **~$3,000** in AI + certificate
  infra (see §5.4). Treat it as customer-acquisition spend, not
  revenue.

---

## 2. Reference architecture

```
                     ┌─────────────────────────┐
                     │  Cloudflare CDN + WAF   │
                     │  learn.ithr.tech + api  │
                     └───────────┬─────────────┘
                                 │  TLS 1.2+
             ┌───────────────────┴────────────────────┐
             │                                        │
     ┌───────▼───────┐                        ┌───────▼───────┐
     │  React SPA    │                        │  FastAPI API  │
     │  (Nginx pod)  │                        │  (uvicorn/    │
     │  2 replicas   │                        │   gunicorn)   │
     └───────────────┘                        │  4 replicas   │
                                              └───┬─────┬─────┘
                                                  │     │
                                    ┌─────────────┘     └────────────┐
                                    │                                 │
                            ┌───────▼────────┐              ┌─────────▼──────────┐
                            │   MongoDB       │              │  Emergent LLM Key   │
                            │   Atlas M20     │              │  → OpenAI / Claude  │
                            │   (replica set) │              │  → Gemini           │
                            └────────────────┘              └─────────────────────┘
                                    │
                            ┌───────▼────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐
                            │  S3 for PDFs   │  │  Stripe  │  │  Resend  │  │  Sentry │
                            │  + procurement │  │ payments │  │  email   │  │   APM   │
                            │  packs         │  │          │  │          │  │         │
                            └────────────────┘  └──────────┘  └──────────┘  └────────┘
```

**Deployment target for production:** Emergent-managed Kubernetes.
Preview lives on the same substrate but with a single replica per
service and a shared MongoDB tier.

---

## 3. Component-level unit costs

### 3.1 Compute (backend + frontend)

Kubernetes pods on managed EKS / Emergent-managed.

| SKU | Spec | Purpose | Cost/month | Notes |
|---|---|---|---|---|
| Backend pod | 0.5 vCPU / 1 GB | FastAPI worker | $18 × N | Autoscale 2–20 |
| Frontend pod | 0.2 vCPU / 512 MB | Nginx-served CRA build | $9 × 2 | Fixed 2 replicas |
| Ingress controller | Shared | Traefik | $12 flat | — |
| WeasyPrint worker | 0.5 vCPU / 1 GB | Certificate PDF gen | $18 × 1 | Sync, low volume |
| K8s control plane | — | EKS / equivalent | $73 flat | — |

At **N=4 backend replicas**: ~**$208/month** for the compute layer.

### 3.2 Database

| SKU | Cost/month | Storage | RAM | Notes |
|---|---|---|---|---|
| MongoDB Atlas M10 (dev) | **$60** | 10 GB | 2 GB | For preview / staging only |
| MongoDB Atlas M20 (prod) | **$180** | 40 GB | 4 GB | Recommended launch tier |
| MongoDB Atlas M30 (growth) | **$390** | 80 GB | 8 GB | ~15k MAU |
| MongoDB Atlas M40 (scale) | **$780** | 160 GB | 16 GB | ~60k MAU |
| MongoDB Atlas M60 (enterprise) | **$2,400** | 320 GB | 32 GB | ~250k MAU |

Backups: included at each tier (Atlas continuous backup up to M20;
snapshot-only below).

### 3.3 Object storage

S3-compatible for:
- PDF certificates (average 220 KB each — cached in-app for 24h)
- Procurement packs (average 1.2 MB each)
- User avatars (average 40 KB)
- Course thumbnails (average 180 KB — served via CDN)

| Volume | Storage cost | GET/PUT | Total |
|---|---|---|---|
| < 200 GB | $4.60/month | $2 | **~$7/mo** |
| 200 GB – 2 TB | $46/month | $18 | **~$64/mo** |
| 2 – 20 TB | $460/month | $180 | **~$640/mo** |

Egress is served via Cloudflare (free bandwidth zone), so S3
egress fees are negligible.

### 3.4 CDN + DNS + WAF (Cloudflare)

| Plan | Cost/month | When to upgrade |
|---|---|---|
| **Pro** | **$20** | Launch → 5k MAU |
| **Business** | **$200** | 5k → 50k MAU (adds custom SSL, image resizing) |
| **Enterprise** | Custom (~$5k) | > 50k MAU + SLA requirements |

### 3.5 LLM inference (dominant variable cost)

Via the **Emergent LLM Key** — pass-through pricing on OpenAI /
Anthropic / Google at their public rates.

Per-interaction budgets:

| Feature | Input tokens (avg) | Output tokens (avg) | Est. $/interaction |
|---|---|---|---|
| AI Tutor turn (in-lesson chat) | 1,200 | 400 | **$0.014** (GPT-5.2) / $0.011 (Claude Haiku) |
| Mentor session (career chat, 10 turns) | 6,000 | 3,000 | **$0.06** (Claude Sonnet 4.6) |
| Curriculum patch draft (auto) | 4,500 | 1,800 | **$0.035** (Claude Sonnet 4.6) |
| Recommendation rationale | 800 | 200 | **$0.005** (GPT-5.2) |
| Course-slug generation | 300 | 200 | **$0.003** (Gemini 3 Flash) |

**Assumed usage per active learner per month:**

| Tier | Tutor turns | Mentor sessions | Rec rationales | LLM cost / MAU |
|---|---|---|---|---|
| Free / try-a-lesson | 3 | 0 | 0 | **$0.04** |
| Learner (paid) | 40 | 2 | 12 | **$0.75** |
| Enterprise seat | 25 | 3 | 8 | **$0.62** |

Plus platform-level flat costs:
- Curriculum patch pipeline: ~120 patches/month × $0.035 = **$4.20/mo**
- Intelligence feed summarisation: ~200 items/month × $0.008 = **$1.60/mo**

### 3.6 Third-party services

| Service | Purpose | Cost/month | Notes |
|---|---|---|---|
| **Stripe** | Payments | 2.9% + $0.30 per txn | No fixed fee |
| **Resend** | Transactional email | $0 up to 3k emails/mo, then $20 / 50k | Digest emails |
| **Sentry** | Error monitoring | $26 (Team) / $80 (Business) | Team plan for launch |
| **Grafana Cloud** | Metrics + logs | $0 (free tier ≤50 GB) / $299 (Pro) | Free tier OK ≤50k MAU |
| **Uptime Kuma** | Uptime monitoring | $0 (self-hosted) | Runs on the K8s cluster |
| **Cloudflare Turnstile** | Bot protection | $0 (free) | — |
| **PostHog** | Product analytics | $0 up to 1M events/mo | Already integrated |
| **DomainSSL / cert renewal** | — | $0 (Let's Encrypt) | — |

### 3.7 Fixed / one-time costs

Not part of monthly unit economics but reflected in cash-flow plan.

| Item | Amount | Notes |
|---|---|---|
| Domain (ithr.tech) | ~$60 / year | Cloudflare Registrar |
| SSL cert (Let's Encrypt) | $0 | via cert-manager on K8s |
| WeasyPrint dep licence | $0 | GPL/LGPL; used server-side only |
| Design fonts (Calibri / Tahoma) | $0 | System / MS installed |
| Legal (SOC2 audit) | $18k – $35k | One-time, deferred |
| Pen-test (annual) | $6k – $12k | Post-SOC2 kickoff |
| GDPR DPO retainer | $8k – $18k/year | If EU enterprise pipeline > $250k ARR |

---

## 4. Consolidated cost projections

### 4.1 Seed (launch — first 90 days)
Target: 500 founding members claiming the perk + up to 100 paid seats.

| Line | Cost/mo |
|---|---|
| Compute (2 backend replicas + 2 frontend + WeasyPrint) | 82 |
| MongoDB Atlas M10 (dev) + M20 (prod) | 60 + 180 |
| Object storage | 7 |
| Cloudflare Pro | 20 |
| LLM inference (500 founders + 50 paid × light usage) | 42 |
| Sentry Team + Grafana free | 26 + 0 |
| Resend free tier | 0 |
| **Total** | **$417** |
| **Cost / MAU (@ 500)** | **$0.83** |

### 4.2 Early (2,500 MAU)
Assume 15% paying, blended $30 ARPU. Revenue ≈ $11,250/mo.

| Line | Cost/mo |
|---|---|
| Compute (4 backend replicas) | 154 |
| MongoDB Atlas M20 | 180 |
| Object storage | 12 |
| Cloudflare Pro | 20 |
| LLM inference (2,500 × $0.55 blended) | 1,375 |
| Sentry Team + Grafana free | 26 |
| Resend Pro ($20) | 20 |
| Misc buffer (15%) | 268 |
| **Total** | **$2,055** |
| **Cost / MAU** | **$0.82** |
| **Gross margin** | **82%** |

### 4.3 Growth (15,000 MAU)
Assume 20% paying, blended $32 ARPU. Revenue ≈ $96,000/mo.

| Line | Cost/mo |
|---|---|
| Compute (10 backend replicas + autoscale headroom) | 350 |
| MongoDB Atlas M30 | 390 |
| Object storage | 64 |
| Cloudflare Business | 200 |
| LLM inference (15,000 × $0.55 blended) | 8,250 |
| Sentry Business + Grafana Pro | 80 + 299 |
| Resend Pro | 40 |
| Misc buffer (15%) | 1,459 |
| **Total** | **$11,132** |
| **Cost / MAU** | **$0.74** |
| **Gross margin** | **88%** |

### 4.4 Scale (60,000 MAU)
Assume 22% paying, blended $34 ARPU. Revenue ≈ $448,800/mo.

| Line | Cost/mo |
|---|---|
| Compute (20 backend replicas + WeasyPrint 3 replicas) | 850 |
| MongoDB Atlas M40 + read replicas | 1,560 |
| Object storage | 340 |
| Cloudflare Business | 200 |
| LLM inference (60,000 × $0.55 blended) | 33,000 |
| Sentry Business + Grafana Pro | 379 |
| Resend Pro | 200 |
| Misc buffer (15%) | 5,479 |
| **Total** | **$42,008** |
| **Cost / MAU** | **$0.70** |
| **Gross margin** | **91%** |

### 4.5 Enterprise-heavy (250,000 MAU)
Higher enterprise mix (60% enterprise seats, 40% self-serve).
Assume blended $28 ARPU. Revenue ≈ $1.4M/mo.

| Line | Cost/mo |
|---|---|
| Compute (K8s HPA to ~50 replicas peak) | 3,200 |
| MongoDB Atlas M60 + sharding | 4,800 |
| Object storage | 1,400 |
| Cloudflare Enterprise | 5,000 |
| LLM inference (250,000 × $0.60 blended enterprise) | 150,000 |
| Sentry Business + Grafana Pro + Datadog trial | 1,200 |
| Resend Business | 500 |
| Misc buffer + K8s ops | 25,000 |
| **Total** | **$191,100** |
| **Cost / MAU** | **$0.76** |
| **Gross margin** | **86%** |

---

## 5. Feature-level cost notes

### 5.1 Certificate PDF generation
- WeasyPrint renders each cert on-demand: ~250 ms CPU per PDF.
- Cache PDFs in S3 for 24h under `certificates/{cert_id}.pdf` (already implemented).
- At 60k MAU with 22% completing a course, ~13k PDFs/mo generated →
  ~55 minutes of CPU time → **$0.30/mo** in incremental compute.
- Storage grows ~2.8 GB/mo of new PDFs.

### 5.2 AI Tutor SSE streaming
- Persistent SSE connections are cheap on Uvicorn (no thread per
  connection). Each concurrent stream costs ~4 MB RSS.
- 400 concurrent tutor streams comfortably fit in 4 backend replicas.
- LLM cost dominates; infra cost is negligible.

### 5.3 Curriculum patch pipeline
- Batch job runs every 6 hours.
- Consumes ~120 signals/day × $0.035 each = **$126/mo** at scale.
- Human review remains a headcount cost (see §7).

### 5.4 Founding-Member perk (first 500 users)
- **Perk cost per founder:** free modules 6–15 access + 1 free cert.
  Marginal infra cost = tutor turns (~40) × $0.014 + PDF (~$0.001)
  = **$0.57 per founder**.
- **Total perk cost** across 500 founders = **~$285** in LLM +
  **~$3 in PDFs + storage**. Round to **$300** total, one-time.
- **Opportunity cost** vs $22/mo learner subscription = $22 × 500
  = **$11,000/mo of foregone revenue**. Justified only if it
  seeds ≥ 50 word-of-mouth conversions ($1,100/mo LTV).

### 5.5 Procurement pack ZIP generator
- Generated on-demand (< 5/day expected).
- Marginal cost negligible (< $1/mo).

---

## 6. Traffic-scaling scenarios

Cost sensitivity to two key variables:

### 6.1 If AI Tutor usage doubles per learner (heavy usage)
- LLM cost line rises ~90%, everything else unchanged.
- Growth-tier total moves from $11.1k → **$18.5k/mo**.
- Mitigations:
  - Cache common tutor answers (~30% deflection possible).
  - Downshift to Claude Haiku 4.5 for casual Q&A ($0.008 → $0.004).
  - Offer a "premium AI credits" add-on to heavy users.

### 6.2 If MongoDB storage grows faster than modelled
- Certificate collection is largest write-heavy set.
- At 60k MAU we project 40 GB of certs alone by year 3.
- Move certs older than 12 months to a compressed archive collection
  → 60% storage reduction, no user-visible impact.

### 6.3 If Cloudflare bandwidth cap is hit
- Cloudflare Business tier includes 100 GB/mo of image bandwidth.
- Course thumbnails average 180 KB; at 15k MAU × 40 page views/mo =
  ~110 GB/mo → we exceed on the Pro plan.
- **Trigger**: upgrade to Business at 10k MAU regardless of the
  cost-per-MAU trend.

---

## 7. Headcount & G&A (outside infra, for full break-even model)

| Role | Cost/year (Dubai / remote blend) | When to hire |
|---|---|---|
| Founder-CTO | $0 (equity) | Now |
| Founder-CEO | $0 (equity) | Now |
| Full-stack engineer #1 | $85,000 | 500 MAU |
| Content lead / curriculum ops | $70,000 | 1,500 MAU |
| Full-stack engineer #2 | $85,000 | 8,000 MAU |
| DevRel / community | $60,000 | 5,000 MAU |
| CS / support | $45,000 | 5,000 MAU |
| Head of Enterprise Sales | $110,000 + comm | 10k MAU or 5+ enterprise leads |
| SRE / platform | $110,000 | 30k MAU |

Blended G&A (accountant, legal retainer, office, insurance): **~$3,000/mo**
at launch → ~$12,000/mo at growth tier.

**Break-even @ growth tier** (15k MAU):
- Infra: $11.1k/mo
- Headcount (7 people): ~$36k/mo blended
- G&A: $12k/mo
- **Total OpEx**: **~$59k/mo**
- Revenue @ 20% paying × $32 ARPU × 15k MAU = **$96k/mo**
- **Contribution**: **+$37k/mo** → cash-flow positive

---

## 8. Risk register (cost-side)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM provider raises prices | Medium | High | Multi-provider (OpenAI + Claude + Gemini). Cache. Downgrade tier per feature. |
| MongoDB Atlas region outage | Low | High | Multi-region replica set at M40+; cold failover playbook |
| Cloudflare pricing change on Business tier | Low | Medium | Fastly / BunnyCDN as fallback (design tested) |
| Certificate PDF traffic spike (viral) | Low | Medium | Pre-generate + S3-cache on quiz-pass; already implemented |
| Refund liability spike | Low | Medium | Clear 14-day / 20%-consumption policy in ToS |
| Sub-processor DPA renegotiation | Medium | Low | Standard SCCs; 30-day change notice already committed to enterprise |
| Regulatory attestation delay (SOC2) | High | Low (already deferred) | Post loudly on /trust; keep "designed to align" wording |

---

## 9. Operating rhythm

**Monthly cost review** — first Tuesday of the month.
- Pull actual costs from AWS + Atlas + Stripe + Cloudflare consoles.
- Compare to this projection tier.
- Escalate if any line item > 15% over projection two months in a row.

**Quarterly capacity review** — Q-first Monday.
- Are we within the MAU tier this doc assumes?
- If we crossed a tier boundary, refresh the projection column.

**Annual re-baseline** — every February.
- Rebuild this document with actuals.
- Refresh LLM per-turn prices (they usually drop 20-40%/year).
- Reassess SOC2 / ISO cert timing.

---

## 10. Data sources

- MongoDB Atlas pricing — atlas.mongodb.com/pricing (retrieved Feb 2026)
- AWS EKS pricing — aws.amazon.com/eks/pricing
- Cloudflare plans — cloudflare.com/plans
- Stripe pricing — stripe.com/pricing (2.9% + $0.30 for cards; UAE
  merchants pay 3.2% for international cards)
- OpenAI, Anthropic, Google model pricing pages (retrieved Feb 2026)
- Resend pricing — resend.com/pricing
- Sentry pricing — sentry.io/pricing
- ITHR internal traffic model — see `/app/docs/GROWTH_MODEL.xlsx`
  (create separately)

---

**End of document.**

*Any changes to this doc must be reviewed by the CTO and versioned.
Distribute internally only.*
