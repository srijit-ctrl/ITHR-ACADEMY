# ITHR Enterprise Agentic AI Academy
## Commercial Strategy, Ownership, Compliance & Cost Dossier

**Document version:** 1.0
**Prepared:** February 2026
**Prepared for:** Executive stakeholders, procurement, and enterprise buyers
**Status:** Confidential — internal + trusted partners

---

## 1. Executive summary

The **ITHR Enterprise Agentic AI Academy** (the "Portal") is a full-stack SaaS learning, assessment, and certification platform for agentic-AI competence, operated by **ITHR Technologies Consulting LLC**. This document describes:

1. What we ship today and what we still need to reach **commercial viability**.
2. Legal ownership of the portal, IP, data, and issued credentials.
3. Where the database resides today, and the concrete path to a **UAE-resident data plane** (PDPL / NDMO / TDRA compliant).
4. Data-security posture (in-transit, at-rest, access control, audit).
5. Authenticity model for **credentials** — why an ITHR-issued certificate is trustworthy.
6. Authenticity model for **courseware** — how curriculum accuracy is maintained.
7. **Cost projections** for base, growth, and traffic-spike scenarios.

---

## 2. What is commercially live today

| Layer | Status |
|---|---|
| Learner portal (24 courses, 10 fully authored 15-module tracks) | ✅ live |
| Randomised assessment engine (341 questions, shuffled options, adaptive) | ✅ live |
| Certification engine (QR verification, public /verify, server-rendered PDF) | ✅ live |
| AI Tutor (Aletheia) + AI Career Mentor (Solon) + Recommendation engine | ✅ live |
| Enterprise Portal (org, invites, seat mgmt, team analytics, patch review) | ✅ live |
| Stripe payments (subscribe, one-time, per-seat with prorated credit) | ✅ live (test key) |
| Real-time Intelligence Desk (Claude-driven signal ingest, push-to-curriculum) | ✅ live |
| AI Skills Passport (public, LinkedIn/CV-shareable) | ✅ live |
| Weekly digest email + Slack/Teams webhooks | ✅ code live, email key not yet configured |
| Try-a-lesson anonymous demo | ✅ live |

---

## 3. Roadmap to commercial viability

### Phase 1 — Production hardening (0–60 days)
| Item | Why it matters |
|---|---|
| Provision **production Stripe live key** and swap `sk_test_emergent` | Cannot collect real revenue on test key |
| Provision **Resend / SES production key** for digest + invites | Currently degrades gracefully — buyers expect email notifications |
| Enable **live domain + TLS** on `academy.ithr.ae` (or client sub-domain) | Preview URL is not brandable for enterprise sales |
| **DPA + Master Services Agreement** templates (English + Arabic) | Every enterprise procurement requires these |
| **SOC 2 Type I** readiness audit (see §6) | Blocker for Fortune 500 procurement in ≈70% of RFPs |
| **PDPL registration** with UAE Data Office if serving UAE data subjects | Legal requirement — see §5 |
| **Load test** to 10k concurrent + 100k daily active | Sales-defensible SLA claim |
| **Backup + restore drill** (MongoDB PITR + object storage snapshot) | Required for SOC 2 CC7.5 |
| **Idle-session logout, MFA, SSO** (Azure AD / Okta / SCIM) | Enterprise-mandated for privileged access |
| **Cookie banner + granular consent** (GDPR + UAE PDPL Art. 6) | Legal requirement |

### Phase 2 — Revenue expansion (60–180 days)
| Item | Revenue lever |
|---|---|
| **Talent Directory** (opt-in registry of certified graduates + recruiter search) | Upsell to hiring teams — $500/seat/mo per recruiter |
| **Renewal / CE credit engine** (annual re-certification workflows) | Recurring revenue — 20 CE credits every 2 years @ $199 renewal fee |
| **Custom enterprise curriculum** (bespoke tracks per organisation) | High-margin services — $50k–$250k per engagement |
| **Multi-language content (Arabic first, then FR/ES/DE/ZH)** | Unlocks EMEA + LATAM + APAC procurement |
| **Advanced proctoring** (webcam + focus loss + tab-switch detection) | Required for regulated industries (banking, healthcare) |
| **Skills-gap benchmark reports** (compare org vs. industry percentile) | Board-level report — anchors C-suite renewals |
| **Blockchain credential anchoring** (Polygon / Ethereum + IPFS) | Marketing differentiator; validates "tamper-proof" claim |
| **White-label + SSO** for large accounts | 5–8× ARPU multiplier |
| **API-based verification for ATS integrations** (Workday, SuccessFactors) | Sticky embed inside HRIS workflows |

### Phase 3 — Institutional partnerships (180–365 days)
| Item | Strategic value |
|---|---|
| **Accreditation partnerships** — UAE MoE, ADEK, KHDA endorsement | Elevates issuer credibility (see §7) |
| **University co-branding** — American University in Dubai, KU, MBZUAI | Academic legitimacy for the certificate ladder |
| **Government workforce programs** — NAFIS, Emiratisation Council | Public-sector procurement pipeline |
| **ANSI/IEEE/ISO/IEC 17024** personnel certification body accreditation | International recognition; competitor moat |
| **Content peer-review board** (5–8 external agentic-AI academics) | Formal courseware authenticity governance (see §8) |

### Commercial-viability checklist (must all be YES to sell to a Fortune 500)
- [ ] Live Stripe + tax invoicing (VAT / GST / US sales tax)
- [ ] Signed DPA + MSA templates
- [ ] Data-residency guarantees in writing (UAE / EU / US as needed)
- [ ] SOC 2 Type I report or equivalent (ISO 27001 pending)
- [ ] Public trust & security portal (`trust.ithr.ae` mirroring Vanta / Drata style)
- [ ] Named CISO or vCISO on record
- [ ] Documented incident-response plan + 24×7 on-call rota
- [ ] Contractual uptime SLA (99.9%) with credits

---

## 4. Ownership

### 4.1 Legal owner of the portal, IP and issued credentials
| Asset | Owner |
|---|---|
| Software (source code, database schema, UI, brand marks) | **ITHR Technologies Consulting LLC** |
| Trademark "ITHR Academy" + logo + certificate seal | ITHR Technologies Consulting LLC (registration recommended in UAE, EU, US, IN) |
| Copyright on courseware, question bank, videos, worksheets | ITHR Technologies Consulting LLC |
| Certificates issued to learners | ITHR is the **issuing authority**; the learner holds a **non-transferable licence to display** the credential |
| Aggregated / anonymised analytics | ITHR |
| Learner-generated content (chat prompts to Aletheia / Solon) | Learner retains authorship; ITHR holds a licence to process for service delivery |
| Enterprise-specific dashboards + benchmarks | Joint — ITHR technology, customer data (per DPA) |

### 4.2 Corporate structure (recommended)
- **Head entity:** ITHR Technologies Consulting LLC (existing)
- **Recommended sub-entity for UAE data hosting:** *ITHR Academy FZ-LLC* incorporated in **Dubai Internet City (TECOM)** or **DIFC Innovation Hub** — grants free-zone tax treatment, 100% foreign ownership, and a UAE tax residency certificate suitable for MENA procurement.
- **IP holding:** register a separate IP holdco in a friendly jurisdiction (e.g., DIFC) to license courseware IP to operating entities.

---

## 5. Where the database resides today — and how to move to the UAE

### 5.1 Current state (development / MVP)
- **Primary database:** MongoDB, hosted in the current Emergent-managed Kubernetes cluster.
- **Connection:** `MONGO_URL` from `/app/backend/.env`.
- **Region:** Emergent's default region (US-East for the shared preview environment).
- **This is not production-grade.** Preview environments are ephemeral, shared, and are not certified for regulated workloads.

### 5.2 Target state — UAE-resident production
| Layer | Recommended provider (UAE region) |
|---|---|
| Compute + Kubernetes | **AWS `me-central-1` (Bahrain / UAE)** — actual UAE region is `me-central-1` (Middle East / UAE, Etihad Data Centre) *or* **Microsoft Azure UAE North (Dubai)** *or* **Oracle Cloud UAE Central (Abu Dhabi)** |
| Managed MongoDB | **MongoDB Atlas** on AWS `me-central-1` (UAE region), Replica Set with 3 nodes across two AZs |
| Object storage (PDFs, media) | **AWS S3 me-central-1** with SSE-KMS + Object Lock (compliance mode) |
| CDN | CloudFront with UAE edge locations, TLS 1.3, HSTS preload |
| Email | **AWS SES me-central-1** (or Resend EU + DPA — SES UAE is preferred) |
| Payments | Stripe (data flows via EU/UAE processing; UAE Central Bank licensed acquirer for AED settlement — **Network International** or **Amazon Payment Services** for local card acceptance |
| Backup | Cross-AZ within `me-central-1`; encrypted; **no data crosses UAE borders** |
| DR (Disaster Recovery) | Warm-standby in Azure UAE North for provider-diversity; still inside UAE borders |
| Secrets | AWS Secrets Manager (KMS-encrypted) — never in `.env` in prod |

### 5.3 Migration plan (weeks)
1. **W1** — Provision AWS `me-central-1` account with Control Tower + Landing Zone; open UAE-only routing policies.
2. **W2** — Stand up EKS + MongoDB Atlas UAE cluster; configure VPC + PrivateLink to Atlas.
3. **W3** — Data-migration dry run via `mongodump | mongorestore` inside a Direct Connect tunnel; verify checksums; **no data leaves UAE region**.
4. **W4** — Cutover window (2-hour maintenance): freeze writes, replicate delta, DNS flip, confirm.
5. **W5** — Compliance evidence pack (§6) refreshed; DPA + Schedule of Sub-processors updated for signing customers.

### 5.4 Regulatory parameters that apply

#### UAE — federal + free-zone
| Regulation | Applies to | Key obligation |
|---|---|---|
| **UAE PDPL (Federal Decree-Law 45 of 2021)** | All personal data of UAE residents | Lawful basis, consent, DSAR (data-subject access request) within 30 days, cross-border transfer restrictions, breach notification to UAE Data Office |
| **UAE Cybercrime Law (Federal Decree-Law 34 of 2021)** | All systems touching UAE users | Prohibits unauthorised access; requires reasonable security |
| **TDRA IoT / Cloud Computing Regulatory Framework** | Cloud services in UAE | Registration for classified data; **data residency for regulated verticals** (banking, health, government) |
| **NESA / SIA (National Electronic Security Authority)** IA Standards v2 | Critical-sector customers (energy, finance, gov) | 188 mandatory controls; annual audit |
| **CBUAE Consumer Protection & Cyber Risk Regulations** | Any bank customer using the platform | Bank-grade encryption, log retention 6 y+, red-team every 12 mo |
| **DHA / DoH e-Health Data Regulation** | Healthcare customers | PHI must remain in UAE; audit logs 25 y |
| **ADGM / DIFC Data Protection Regulations** | Customers domiciled in ADGM or DIFC | GDPR-equivalent (adequacy already recognised by EU) |

#### International (still relevant to enterprise buyers even if data is in UAE)
- **GDPR** (EU learners): Article 45 adequacy — DIFC has EU adequacy; ADGM & mainland UAE do **not** yet; use SCCs (Standard Contractual Clauses) as a bridge.
- **CCPA / CPRA** (California learners): Opt-out of sale, deletion, portability.
- **FERPA** (US higher-education partners): educational records confidentiality.
- **HIPAA** (US healthcare enterprise customers): BAA required if the platform ingests PHI.
- **SOC 2 Type II** (procurement standard for US Fortune 500).
- **ISO 27001:2022 + ISO 27701** (privacy management extension).
- **ISO/IEC 27017 + 27018** (cloud + cloud PII controls).

---

## 6. Data-security posture

### 6.1 What is in place today (MVP)
- HTTPS everywhere via Kubernetes ingress; TLS 1.2+
- JWT tokens signed with per-environment secret; bcrypt password hashing (12 rounds); expiration + refresh
- MongoDB `MONGO_URL` bound to internal cluster network (not internet-exposed)
- Server-side authorization on every `/api/*` route (`Depends(get_current_user)`)
- Role-based access checks on Enterprise endpoints (owner / admin / member)
- Audit trail on assessment submissions + certificate issuance
- Rate-limiting on anonymous demo endpoint (5 req / 30 min per IP)
- Public credential verification (`/verify/{id}`) uses opaque IDs (`EAIA-2026-XXXXXX`), not learner-guessable

### 6.2 What must be added for production (§3 Phase 1)
| Control area | Requirement |
|---|---|
| **Encryption at rest** | KMS (AWS KMS or Azure Key Vault) — envelope encryption for MongoDB Atlas, S3 buckets, backups |
| **Encryption in transit** | TLS 1.3 only; internal service mesh (Istio / Linkerd) with mTLS |
| **Key rotation** | 90-day automatic rotation for KMS keys; 30-day for JWT signing secret |
| **Identity** | SSO via Azure AD / Okta / Google Workspace; enforce MFA for admins; SCIM auto-deprovisioning |
| **Access management** | Break-glass IAM roles; time-bound; session-recorded (Teleport or AWS Session Manager) |
| **Logging** | Centralised (CloudWatch + S3 + Athena) with immutable retention 400 days (SOC 2) and 6 y for financial |
| **Vulnerability management** | Snyk / Dependabot on every PR; monthly OWASP ZAP; annual pen-test by CREST-accredited firm |
| **WAF** | CloudFront + AWS WAF (OWASP Top 10, bot control); rate limiting per IP + per token |
| **DDoS** | AWS Shield Advanced (custom threshold + response team) |
| **Secrets management** | Secrets Manager; no secrets in `.env` in production containers |
| **Data classification** | Public / Internal / Confidential / Restricted (PII, PHI, financial); labelled at collection |
| **Data-subject rights** | DSAR portal with 30-day SLA; automated export/delete jobs |
| **Backups** | Point-in-time recovery ≤5 min RPO; cross-AZ; quarterly restore drill |
| **Business continuity** | Documented DR (RTO 4 h, RPO 5 min); annual tabletop exercise |
| **Third-party risk** | Sub-processor register (Stripe, MongoDB, AWS, Resend, Anthropic, Google) with signed DPAs |
| **Incident response** | 24×7 on-call; 72-h notification to UAE Data Office + 72-h GDPR notification; playbook + comms templates |
| **Employee security** | Background checks; annual security awareness training; NDA + IP assignment |
| **Physical security** | Delegated to cloud provider (AWS SOC 2 + ISO 27001 attestations on file) |

### 6.3 Compliance evidence pack (deliverable to every enterprise buyer)
1. Latest SOC 2 Type II report (bridge letter between audit periods)
2. ISO 27001:2022 certificate + Statement of Applicability
3. Penetration-test executive summary (annual, redacted)
4. Sub-processor list + DPA templates
5. Data-flow diagram (customer data → services → storage → backups)
6. Incident-response playbook (executive summary)
7. Business-continuity plan
8. Insurance certificates — Cyber liability (min USD 5M), Professional indemnity, E&O
9. Trust page: `trust.ithr.ae`

---

## 7. Certificate authenticity — why an ITHR credential is trustworthy

### 7.1 Technical authenticity
Every issued credential has **four independently verifiable layers**:

1. **Opaque credential ID** (`EAIA-2026-XXXXXX`) — server-issued, 6-char high-entropy suffix, unguessable, uniqueness-enforced in MongoDB.
2. **Public verification endpoint** `GET /api/certificates/verify/{id}` — returns issuer, holder, course, score, issued-at. Anyone with the ID (or scanning the QR) can validate.
3. **QR code** rendered server-side (`segno`, error-correction level H) embedded in both the on-screen certificate and the server-rendered PDF. QR resolves to `/verify/{id}` — verifiable without a login.
4. **Server-rendered PDF** produced by WeasyPrint on our servers, not the learner's browser. This means we hold the source of truth; screenshots or altered PDFs will fail QR verification.

### 7.2 Anti-fraud roadmap (§3 Phase 2/3)
- **Cryptographic signature** on the credential JSON (Ed25519); public key published at `academy.ithr.ae/.well-known/credential-key.pem`.
- **W3C Verifiable Credentials** JSON-LD format for interoperability with digital wallets (Apple / Google Wallet, EU Digital Identity Wallet).
- **Blockchain anchoring** of a hash of every issued credential (Polygon or Ethereum L2); anyone can independently verify inclusion.
- **Proctoring artefacts** (webcam + browser lock) stored alongside the credential for regulated tracks — chain-of-custody defensible.
- **LinkedIn "Add to profile" deep-link** already live on `/certificate/:id` — leverages LinkedIn's issuer allow-list once ITHR is enrolled with the LinkedIn Learning issuer program.

### 7.3 Why is ITHR entitled to issue this credential?
A credential is trustworthy because of **who stands behind it**, not merely because the software works. ITHR's issuer legitimacy rests on the following pillars — some in place, some to be executed as part of §3.

| Pillar | Status |
|---|---|
| **Legal entity** — ITHR Technologies Consulting LLC is a duly incorporated UAE consulting firm with a valid trade licence, VAT registration, and Emiratisation compliance. | ✅ existing |
| **Subject-matter authority** — ITHR employs / engages practitioners with hands-on enterprise agentic-AI deployment experience. Curriculum is authored by named subject-matter experts whose bios are published on the Academy site. | ⚠ to be published |
| **Peer review** — every full course is reviewed by an independent Academic Advisory Board of external agentic-AI academics + industry CTOs before publication. | ⚠ to be formalised in Phase 3 |
| **Assessment integrity** — question bank is authored per Bloom's taxonomy; items are psychometrically calibrated (item-response theory) as data accrues; adaptive engine controls for gaming. | ✅ engine live; IRT calibration planned |
| **Renewal cadence** — every credential requires 20 CE credits every 24 months to remain "Active"; expired credentials are visibly marked on `/verify/{id}`. | ⚠ engine planned (§3 Phase 2) |
| **Registry of issued credentials** — public, searchable, tamper-evident. | ✅ live |
| **Accreditation** (endorsement, not the same as authority) — target accreditations that strengthen recognition: UAE Ministry of Education equivalency, KHDA course approval, ANSI/IEEE/ISO 17024 personnel-certification-body accreditation. | ⚠ Phase 3 |
| **Insurance & indemnity** — ITHR carries Professional Indemnity insurance covering issuer liability. | ⚠ Phase 1 |
| **Transparent issuer policy** — publicly-published rubric describing pass criteria, appeals process, revocation policy, and code of ethics. | ⚠ to be published |

> **Plain-language answer:** ITHR is entitled to issue this credential because (i) it is a legally established firm that has publicly declared itself the issuer, (ii) it applies a documented, peer-reviewable rubric to every award, (iii) it maintains a public registry that anyone can inspect, and (iv) it stands behind each award with professional indemnity and a code of ethics. Certification legitimacy is a **social contract** — the technical stack keeps it honest; the accreditations (Phase 3) make it internationally portable.

---

## 8. Courseware authenticity

Buyers and regulators must be able to trust that the *content* of a course is accurate, current, and free of bias or hallucination.

### 8.1 Authorship + review workflow
1. **Named authors** — every module lists a primary author (with LinkedIn / ORCID).
2. **Peer review** — Academic Advisory Board (5–8 external experts) reviews every full course before publication and re-reviews at 12-month intervals.
3. **Freshness score** — every course has a `freshness_score` and `last_reviewed_at`; content older than 6 months is auto-flagged for review.
4. **Change log** — every published module has a Git-backed change log; changes >5% material trigger re-review + version bump on the credential.

### 8.2 AI-content governance
- **No unreviewed AI-generated content ships to learners.** Claude Sonnet is used to *draft* curriculum patches (see Push-to-Curriculum), but every patch enters a **human review queue** (`/patches`) and cannot be published without an approver's sign-off.
- Aletheia (Tutor) and Solon (Mentor) responses are marked as AI outputs, are not stored as courseware, and cite the module they contextualise.
- **Model provenance:** every AI feature declares which model + version generated the text (audit trail).
- **Real-time Intelligence Desk** ingests curated public sources; each surfaced signal cites its source URL + retrieval timestamp.

### 8.3 Learner-appeal + correction
- Every lesson has a "Report an issue" affordance (planned Phase 1 finish).
- Reported issues auto-open a review ticket, tracked in the same patch pipeline; correction turnaround target: 5 business days.
- Corrections flow into the change-log and, where material, trigger CE-credit notices to already-certified holders.

---

## 9. Cost projections

All figures in USD, monthly, at the **retail** cloud rate (before typical 15–30% enterprise / startup credits). Excludes salaries, marketing, and content authoring; those are separate P&L lines.

### 9.1 Baseline — dev / early production (≤ 1,000 MAU)
| Line item | Provider | Est. monthly |
|---|---|---|
| Compute (2 × m5.large EKS nodes, autoscale) | AWS `me-central-1` | $250 |
| MongoDB Atlas M10 (3-node replica set) | MongoDB | $180 |
| Object storage (10 GB) + CloudFront (100 GB egress) | AWS S3 + CDN | $30 |
| Managed Redis (cache) | AWS ElastiCache t4g.small | $35 |
| Email (Resend Pro or SES) | 50k emails/mo | $30 |
| Domain, DNS, TLS, Route 53 | AWS | $10 |
| Anthropic Claude Sonnet 4.5 tokens | ~2M input + 500k output | $30 |
| Stripe fees (variable — see below) | Stripe | pass-through |
| Logging + monitoring (Datadog Pro or Grafana Cloud) | Datadog | $200 |
| Backup + snapshots | AWS | $20 |
| **Subtotal — baseline** | | **≈ $785 / mo** |

### 9.2 Growth — mid-market (≈ 10,000 MAU, 5 enterprise clients)
| Line item | Est. monthly |
|---|---|
| Compute (5 × m5.xlarge, 2 AZ) | $1,200 |
| MongoDB Atlas M30 (3-node) | $780 |
| Object storage (250 GB) + CDN (2 TB egress) | $250 |
| Redis (m5.large, HA) | $220 |
| Email (500k / mo) | $150 |
| Anthropic Claude tokens (~20M in + 5M out) | $300 |
| Sora 2 / image generation (optional, if enabled) | $200 |
| WAF + Shield Advanced | $3,000 |
| Datadog / Grafana Enterprise | $600 |
| Backups (cross-AZ + snapshots) | $180 |
| Pen-test (annual, amortised) | $1,000 |
| SOC 2 audit (annual, amortised) | $2,500 |
| Insurance (cyber + E&O + PI) | $1,200 |
| **Subtotal — growth** | **≈ $11,580 / mo** |

### 9.3 Scale + traffic-spike protection (100,000 MAU, viral / launch-day surge)
| Line item | Est. monthly |
|---|---|
| Compute — Karpenter autoscale 10→40 nodes | $6,000 |
| MongoDB Atlas M60 sharded (or Serverless with burst) | $3,800 |
| Object storage (2 TB) + CDN (20 TB egress) | $2,300 |
| Redis cluster | $900 |
| Email (5M / mo) | $1,500 |
| Anthropic Claude tokens (~200M in + 50M out) | $3,000 |
| Signed-URL preview + video hosting (Mux or Cloudflare Stream) | $2,000 |
| WAF + Shield Advanced + rate-limit tiers | $3,500 |
| Observability + SIEM | $2,500 |
| DR site (Azure UAE North warm-standby, 50%) | $3,000 |
| **Subtotal — scale** | **≈ $28,500 / mo** |

### 9.4 Traffic-spike (viral 24 h — 1M unique visitors)
Autoscaling handles most of this; the delta above scale-tier is short-lived. Worst-case additive burn:
- Edge egress: +$4,000
- Anthropic Claude burst tokens: +$2,500
- Emergency human on-call (SRE surge): +$3,000
- Total incremental for the spike day: **≈ $9,500** one-off.

### 9.5 Non-cloud costs (not monthly, but planning-critical)
| One-off item | Approx. USD |
|---|---|
| SOC 2 Type I audit | $18,000 |
| SOC 2 Type II audit (annual) | $30,000 |
| ISO 27001 initial + surveillance | $45,000 initial + $18,000/yr |
| Penetration test (CREST) | $22,000 |
| Legal — DPA / MSA / IP assignment templates | $12,000 |
| Trademark registration (UAE + EU + US + IN) | $15,000 |
| Accreditation with ANSI/IEEE 17024 body | $40,000 |
| UAE PDPL registration + DPO engagement (yr 1) | $18,000 |

### 9.6 Break-even framing (illustrative — assumes only enterprise revenue)
- Growth-tier COGS ≈ $12k / mo → **1 enterprise client at $15k / mo covers COGS**.
- Scale-tier COGS ≈ $28k / mo → **2 enterprise clients at $15k / mo covers COGS with a 10% margin buffer**.
- Individual learner P&L: at $29 / mo consumer plan and Anthropic + infra marginal cost ≈ $2.50 per active learner / mo, gross margin ≈ 91% — extremely healthy once fixed costs are absorbed.

### 9.7 Cost controls we've already engineered
- **Response caching** on `/api/intelligence` (6 h TTL) — kills Claude re-billing on repeat opens.
- **Rec-rationale cache** (24 h) — same principle for recommendation copy.
- **Rate-limit** on anonymous demo endpoint (5/30 min/IP) — kills token-farming attacks.
- **Static-at-edge** for course catalog + course detail (already ETag-friendly).

---

## 10. Immediate next actions (priority order)

1. Provision production Stripe live key + tax invoicing.
2. Register **ITHR Academy FZ-LLC** in DIFC/TECOM for UAE tax + data-residency posture.
3. Stand up AWS `me-central-1` production environment + MongoDB Atlas UAE region.
4. Book **SOC 2 Type I** readiness assessment (Vanta / Drata + a Big-4 partner).
5. File **UAE PDPL registration** with the UAE Data Office; designate a Data Protection Officer.
6. Publish `trust.ithr.ae` with sub-processor list, DPA template, and security-controls page.
7. Recruit **Academic Advisory Board** (5 external experts) — publish bios + governance charter.
8. Publish **Issuer Policy** on the Academy site (pass rubric, appeals, revocation, code of ethics).
9. Enrol ITHR with the **LinkedIn Learning issuer programme** so "Add to profile" auto-validates.
10. Kick off **ISO/IEC 17024 personnel-certification-body accreditation** — the strongest global signal for issuer legitimacy.

---

*Document maintained by ITHR Academy engineering. Update on any change to sub-processors, data residency, or accreditation status.*
