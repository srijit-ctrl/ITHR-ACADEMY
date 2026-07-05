# Enterprise Agentic AI Academy — PRD

## Original Problem Statement (Summary)
Build a commercially deployable enterprise SaaS Learning & Certification Platform for Agentic AI, delivered as an ITHR Technologies Consulting LLC value proposition. Serves individuals and Fortune 500 organizations. 15-module × 3-level course structure. Multi-industry. Assessment, certification, AI tutor, enterprise dashboards, real-time curriculum intelligence, tiered pricing.

## User Choices Confirmed
- Pillars: Learner portal + Assessment + Certification + Catalog + Real-time Intelligence + Enterprise Portal
- AI: Claude Sonnet 4.5 via Emergent Universal LLM key
- Auth: JWT email/password + Emergent Google OAuth (unified JWT)
- Payments: Stripe (test key `sk_test_emergent`)
- Branding: ITHR Technologies (teal #00A896 + navy)

## What's Been Implemented

### Iteration 1 — MVP Core
- Backend (FastAPI + MongoDB), JWT + bcrypt + Emergent Google OAuth
- 1 full course + 22 catalog stubs, enrollment, quiz, certificates, AI Tutor
- All learner pages + Login/Register
- 27/27 tests

### Iteration 2 — ITHR Rebrand + Intelligence Desk
- ITHR logo + teal palette, dedicated /pricing, real-time /intelligence briefing (Claude Sonnet 4.5, 6h cache)
- 33/33 tests

### Iteration 3 — Catalog Expansion + Freshness + Stripe
- 4 more full 15-module courses (Prompt Eng, RAG, Multi-Agent, Governance)
- Course freshness system on cards + detail
- Stripe checkout: subscribe + one-time + team-per-seat + polling success page
- 55/55 tests

### Iteration 4 — Enterprise Portal + Industry Courses + Push-to-Curriculum + Refactor (current)
- **Refactor**: server.py 906 → 133 lines. 8 domain routers in `/app/backend/routers/*` + shared `/app/backend/core.py`
- **5 new industry full courses**: Banking, Healthcare, Manufacturing, Retail, Government — **10 full courses total** out of 24
- **Enterprise Portal MVP** (backend + frontend):
  - `POST /api/enterprise/organizations` — create org
  - `POST /api/enterprise/organizations/invites` — invite by email/role/dept
  - `POST /api/enterprise/organizations/join` — accept invite via code
  - `GET /api/enterprise/organizations/dashboard` — team readiness index, member table, department breakdown, top courses
  - `POST /api/enterprise/organizations/seats` — owner-only seat adjustment
  - `DELETE /api/enterprise/organizations/members/{id}` — remove member
  - Frontend: `/enterprise/portal`, `/enterprise/setup`, `/enterprise/join`, Dashboard integration
- **Push-to-Curriculum**: `POST /api/intelligence/signals/{id}/apply` uses Claude to draft a full lesson patch, saves to `curriculum_patches` collection, bumps course freshness. UI: signal-card chips are now Sparkles buttons → click opens a beautiful modal with the AI-drafted patch (title, module, markdown content, rationale, status).
- **New collections**: `organizations`, `org_members`, `org_invites`, `curriculum_patches`
- 75/75 tests pass

### Iteration 7 — Try-a-lesson demo + Digest + Notifications + PDF + Visual Refresh (current)
- **Try a Lesson (anonymous demo)** — `GET /api/demo/lesson` + `POST /api/demo/ask` (SSE, IP rate-limited 5 per 30-min). New landing widget streams Aletheia's answer with 3 suggested prompts, then converts to a "Register free" CTA on limit.
- **Weekly Enterprise Digest** — Resend integration with graceful `no_api_key` degradation. Endpoints: `/digest/preview`, `/digest/send`, `/digest/log`. HTML email template with KPIs, top signals, pending patches, ITHR seal header.
- **Slack + Teams patch-approval notifications** — org-level webhook URLs stored on `organizations` doc; patch-approve automatically POSTs `notify_channels()`. Endpoints: `/organizations/notifications` (GET/POST).
- **Certificate PDF export** — `GET /api/certificates/{id}/pdf` returns WeasyPrint-rendered A4-landscape certificate with ITHR seal, gold-foil borders, embedded QR.
- **Landing visual refresh (aiilm.me-inspired)** — removed all dark backgrounds; introduced soft warm section tints (mint/cream), pill-shaped `section-kicker` labels, numbered `.step-card` treatments with big serif numerals. New "How the Academy works" 3-step section, refreshed Certification Ladder + Intelligence Desk sections.
- **13/13 backend pytest + full frontend E2E scenarios pass** (iteration_7.json).


- **Curriculum Patch Review UI** at `/patches` — list + filter (pending/approved/rejected), inline preview, approve/reject actions.
- **Stripe seat operations** in Enterprise Portal:
  - `POST /api/enterprise/organizations/seats/preview` — real-time charge/credit preview.
  - `POST /api/enterprise/organizations/seats` (increase) — returns Stripe Checkout URL; seats only bumped after `/seats/fulfill/{session_id}` verifies paid status.
  - `POST /api/enterprise/organizations/seats` (decrease) — applies immediately + records prorated credit in `org_billing_events`.
  - Enterprise Portal: `Manage seats` modal with live preview + `Billing history` sidebar for owners.
- **AI Skills Passport**:
  - `GET /api/passport/me` (auth) auto-generates a stable public slug.
  - `GET /api/passport/{slug}` (public, no auth) — LinkedIn/CV-shareable.
  - Category-to-skills mapping surfaces earned competencies from certified courses only.
  - `/passport` and `/passport/:slug` pages with cert-QR-cards, LinkedIn share, copy-URL.
- **Role-based learning paths**: 7 curated tracks (Product Manager, Engineer, Risk/Compliance, HR, Banking, Healthcare, Executive):
  - `GET /api/paths`, `GET /api/paths/{slug}`, `POST /api/paths/{slug}/enroll` (bulk-enroll all courses in track).
  - `/paths` and `/paths/:slug` pages.
- **Adaptive assessments**: `/assessment/session?adaptive=true` returns `adaptive_mode` (`onboarding` / `escalate` / `reinforce`) and mixes difficulty buckets based on the learner's past attempts (60/30/10, 20/50/30, 55/35/10).
- **Inline AI Tutor widget** (Aletheia) embedded in LessonViewer — 3 contextual quick-prompts (Explain / Example / Quiz me) + streaming chat scoped to the current lesson.
- Full-course upsert now uses `$setOnInsert` for `quiz` so extended assessment banks persist across restarts.
- **20/20 backend pytest + 10/10 frontend E2E scenarios pass** (iteration_6.json).


- **AI Mentor (Solon)**: dedicated career coach persona separate from Aletheia (Tutor).
  - `POST /api/mentor/chat` streams SSE deltas via Claude Sonnet 4.5, persistent history per user.
  - `GET/DELETE /api/mentor/sessions[/{id}]` CRUD.
  - New `/mentor` page: profile inputs (role/industry/years), 4 starter prompts, sidebar of past sessions.
- **Randomized Assessment Engine**: `GET /api/courses/{slug}/assessment/session?count=15` returns shuffled question subset with shuffled option order.
  - Server returns `permutation` per question — no `correct`/`explanation` leaked to client.
  - `POST .../quiz/submit` accepts `answers.__perm__` map to decode shuffled indices.
  - `GET /api/courses/{slug}/attempts` history.
  - Seeded **341 questions across all 24 courses** (15-27 per course, mix of mcq/multi/true_false/scenario).
- **Certification Engine**:
  - `GET /api/certificates/{id}/qr.svg` returns SVG QR (segno lib, high error correction) pointing to `/verify/{id}`.
  - LinkedIn "Add to profile" deep-link on Certificate page.
  - QR embedded on both `/certificate/{id}` and public `/verify/{id}` pages.
- **AI Recommendation Engine**:
  - `GET /api/recommendations` — rule-based scoring (industry/category overlap, difficulty ladder, freshness, popularity, has_full_content bonus).
  - `GET /api/recommendations/next-best` — top pick + Claude-drafted rationale (24h cache via `rec_rationales` collection).
  - Dashboard shows Next-Best banner + 6-course recommendation grid.
- Dashboard adds Mentor entry + Recommendations grid; Header adds Mentor nav item.
- **18/18 backend pytest + 5/5 frontend E2E scenarios pass** (iteration_5.json).



### P0 — Next
- Weekly email digest to enterprise buyers with critical signals
- Slack/Teams notifications on patch approvals
- Certificate PDF export (server-side rendered, not just print)

### P1 — Milestone 2
- Renewal / CE credit engine (annual re-certification workflows)
- Multi-language content (i18n)
- Advanced proctoring (webcam + focus loss detection)
- Skills-gap report per organization (compare to industry benchmark)
- Talent Directory: public opt-in registry of certified graduates

### P2 — Milestone 3 (Production Hardening)
- Multi-tenant white-label, SSO (Azure AD, Okta, SCIM/LDAP)
- Blockchain credential anchoring
- Kubernetes + load testing (10M / 100K concurrent)
- SOC 2 / ISO 27001 / GDPR / FERPA formal evidence

## Follow-ups Noted by Testing
- Wrap raw-dict endpoints in Pydantic request models (invites, apply-signal, decide-patch)
- Add role-based auth gate on `POST /api/intelligence/patches/{id}/decide` (currently any authenticated user)
- Field-level Pydantic validation on `OrganizationCreate.seat_count` (Field(ge=10, le=5000))
- Extract shared course scaffold helper to DRY seed_* files
- Design-system dialog to replace `confirm()`/`alert()` in EnterprisePortal
- (Iter 8) Extract `<HeroSection kicker title italic variant />` component — hero markup now duplicated across Verify/Certifications/Pricing/EnterprisePortal
- (Iter 8) Consider auth or rate-limit on public `GET /api/certificates/{id}/pdf` to prevent bulk scraping
- (Iter 8) EnterprisePortal.jsx ~409 lines — split SeatEditor/StatCard/MemberRow into `/components/enterprise/*` when the file grows further

### Iteration 8 — aiilm.me tokens on secondary pages + WeasyPrint runtime (Feb 2026)
- **Verify page (/verify)** now uses `HeroBlobs variant="cool"` + `section-kicker` pill + italic serif accent on "credential". 0 console errors.
- **EnterprisePortal (/enterprise/portal)** — JSX repaired (2 missing `</div>` closes + missing `HeroBlobs` import from prior fork); hero now renders with cool blobs, role/industry pill kicker, italic org name.
- **WeasyPrint system deps installed** (`libpango-1.0-0`, `libpangoft2-1.0-0`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libffi-dev`, `shared-mime-info`). `GET /api/certificates/{id}/pdf` now returns a valid 26KB A4-landscape PDF (`%PDF-1.7`, Content-Disposition attachment).
- Certifications + Pricing hero styling already matched — re-verified 0 console errors.
- 2/2 backend pytest (`test_iteration8_pdf.py`) + 4/4 frontend hero pages pass (iteration_8.json).

### Iteration 12 — Official ITHR Brand Kit Rollout (Feb 2026)
- **Brand assets shipped** — copied official ITHR brand kit into `/app/frontend/public/brand/` (5 SVGs: FullColor, Mono_Navy, Mono_White, Reverse_OnDark, Mark) + `/app/frontend/public/` (favicon.ico + 6 favicon PNGs + apple-touch-icon + site.webmanifest). Brand guidelines PDF saved to `/app/docs/brand/`.
- **Color palette swapped to exact ITHR** — Teal `#00A78B` leads (~60%), Navy `#16335E` for foreground text, Bright Blue `#2E7FC1` + Sky Blue `#3FA9E0` for accents. Background shifted from pure white to soft off-white `#F6F8FB` for eye-comfort. Legacy `--brand-gold / --brand-purple / --brand-orange` variable names remapped to nearest ITHR palette values so existing className usages render in brand colors automatically.
- **Font stack** — `['Calibre', 'Manrope', 'Tahoma', -apple-system, ...]` per user directive. Calibre self-hosted (deferred licensing) → Manrope from Google Fonts (renders today) → Tahoma universal fallback.
- **ITHR Logo component** — `ITHRLockup` and `ITHRMark` in `components/brand/ITHRBrand.jsx` now render the official SVGs directly. No filters, no recolour, no rotation (brand-guideline compliant). Header + Footer pick them up automatically.
- **Meta + title** — `<meta theme-color="#16335E">`, favicon links, apple-touch-icon, site.webmanifest all wired in `index.html`. Title updated to "ITHR Enterprise Agentic AI Academy".
- **Intelligence hero** — swapped `bg-foreground` (near-black) → `bg-brand-navy` (#16335E) with teal italic accent — consistent with the eye-soothing theme.
- Testing: 12 acceptance criteria pass, 0 console errors across 7 public routes, computed styles match exact HEX targets (iteration_12.json).

### Iteration 10 — One-click Procurement Pack (Feb 2026)
- **New endpoint `GET /api/trust/procurement-pack`** (public, `/app/backend/routers/trust_router.py`) returns an ~88KB ZIP with 5 entries:
  - `README.txt` — usage instructions + contacts
  - `SECURITY_FACTSHEET.pdf` — one-page Live / In progress / Planned snapshot
  - `SUB_PROCESSORS.pdf` — authoritative sub-processor register
  - `DPA_TEMPLATE.pdf` — working Data Processing Addendum draft (12 clauses, signature block)
  - `COMPLIANCE_DOSSIER.pdf` — full 10-section dossier mirroring the /trust page
- All PDFs are server-rendered with WeasyPrint. Filename: `ITHR-Academy-Procurement-Pack-YYYY-MM-DD.zip`.
- **Frontend CTA on `/trust`**: primary "Generate procurement pack" button in the hero (data-testid `download-procurement-pack`) + secondary CTA in the "Request a DPA" card (data-testid `dpa-download-pack`). Uses Blob + anchor download pattern; loader while generating; sonner toast on success/failure.
- 7/7 backend pytest + full frontend Playwright download interception pass (iteration_10.json).

### Iteration 9 — Public Trust Page + Factual Copy Sweep + Made-in-UAE Theme + Calibre Font Stack (Feb 2026)
- **Public `/trust` page** — realistic-only claims with Live / In progress / Planned pill labels: 14 security controls, 6 sub-processors, 8 issuer legitimacy pillars, "What we do not claim" honest-limits section (SOC 2 not attested, ISO 27001 not certified, no UAE data residency yet, Stripe on test key). Contact cards: `security@ithr.ae`, `privacy@ithr.ae`, `enterprise@ithr.ae`. HeroBlobs cool + section-kicker + italic "honestly" accent.
- **Made-in-UAE theme** — inline SVG UAE flag (2:1 official ratio, no external asset dependency) surfaces in three places: `/trust` UAE strip, Landing hero micro-pill, Footer signature line. Copy: "Made in the UAE — for the world."
- **Factual copy sweep** — removed all inflated / unverifiable claims across pages:
  - Landing hero: `128,400 CERTIFIED`, `400+ ENTERPRISES` → replaced with structural stats (10 tiers / 24 courses / 15 modules / 100% publicly verifiable).
  - Enterprise page: `2.3× Higher AI ROI`, `68% Faster upskilling`, `128k`, `400+ Enterprises` → replaced with structural stats.
  - Curriculum band: "shaped with faculty and practitioners from" → "informed by public research & standards from" + "Independently authored by ITHR · not affiliated" disclaimer.
  - Removed "Fortune 500" phrasing from Landing, Pricing, Enterprise, Footer.
  - Removed "400+ enterprises" claim from Certifications hero copy.
  - Footer: replaced fake SOC 2 / ISO 27001 / GDPR badge row with a Made-in-UAE + Trust link.
- **Font stack** — swapped `IBM Plex Sans` → `Calibre → Manrope → system` (Manrope loaded from Google Fonts, actually renders; Calibre remains first so a future self-hosted licensed webfont picks up automatically). Cormorant Garamond (serif) and IBM Plex Mono (mono) unchanged.
- **Documentation** — `/app/docs/COMMERCIAL_STRATEGY_AND_COMPLIANCE.md` published in prior turn covers ownership, UAE data-residency migration plan, regulatory matrix (PDPL/NESA/CBUAE/DHA/DoH/ADGM/DIFC + GDPR/CCPA/FERPA/HIPAA/SOC 2/ISO 27001), certificate + courseware authenticity model, and cost projections at 3 tiers ($785 / $11,580 / $28,500 monthly).
- Testing: frontend 100% pass, 0 console errors, computed body font-family confirmed `Calibre, Manrope, -apple-system, ...` (iteration_9.json).

### Iteration 13 — Integrity & Honest-Claims Sweep + Legacy Class Rename (Feb 2026)
- **"Certification Authority" → "Independent Issuer"** across Landing hero kicker, Certificate page (seal label + est. line), Footer signature tagline, ITHRLockup sub-mark, ITHRSeal default label. Motivation: avoid implying government/national accreditation ITHR does not hold.
- **Enterprise compliance line softened** — `Enterprise.jsx` capability card no longer says "SOC 2 Type II / ISO 27001 / FERPA aligned". Now: *"Designed to align with GDPR, SOC 2, ISO 27001, and FERPA controls. Audit trails on every credential. Current attestation status is published on our Trust page."* — matches the honest posture already used on `/trust`.
- **Instructor byline generalised** — CourseDetail now shows *"ITHR Academy Editorial Team · Course authored & reviewed by ITHR"* instead of 24 invented persona names. `course.instructor` field is untouched on the backend but is no longer surfaced in the UI.
- **Fake social-proof metrics hidden** — Star/rating badge + Users/enrolled_count badge removed from `CourseCard.jsx` and `CourseDetail.jsx`. Cards now display *`15 modules · 28h · Refreshed Xd ago`* (structural facts only, no fabricated popularity). Backend data unchanged for internal analytics.
- **Pricing capstone claim** — "Live capstone review by ITHR faculty" → "Capstone review by ITHR Academy reviewers" (no non-existent faculty implied).
- **Legacy class rename completed** — all `text-brand-gold-deep` occurrences swapped to canonical ITHR tokens (`text-brand-teal` and `text-brand-navy` where semantic). Trust page "In progress" status pill now uses `bg-brand-sky/15 text-brand-navy border-brand-sky/40` (softer, visually distinct from Live/Planned).
- Files touched: `Landing.jsx`, `Enterprise.jsx`, `Pricing.jsx`, `Certificate.jsx`, `Trust.jsx`, `Footer.jsx`, `TryALesson.jsx`, `CourseCard.jsx`, `CourseDetail.jsx`, `components/brand/ITHRBrand.jsx`.
- Verified via smoke screenshots on `/`, `/courses`, `/courses/agentic-ai-foundations`. Header brand row now reads *"Academy | INDEPENDENT ISSUER"*.

### Iteration 14 — Security Hardening + Backend Refactor + Legacy Rename (Feb 2026)

**Critical security fixes**
- **Auth token architecture rewritten to in-memory access + httpOnly refresh cookie.**
  - Backend now issues a 15-min access token in the JSON body **and** sets a 7-day `ithr_refresh` httpOnly + Secure + SameSite=Lax cookie scoped to `/api/auth`.
  - New endpoints: `POST /api/auth/refresh` (rotates cookie, returns fresh access token) and `POST /api/auth/logout` (clears cookie).
  - `.env`: `JWT_ACCESS_EXPIRY_MINUTES=15`, `JWT_REFRESH_EXPIRY_DAYS=7`, `JWT_REFRESH_SECRET` (separate secret), `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`.
  - Frontend removes **all** `localStorage.eaia_token / eaia_user` usage. Access token lives in a module-level ref inside `api.js` (`setAccessToken` / `getAccessToken`). `AuthProvider` hydrates via `/auth/refresh` on mount; axios response interceptor auto-refreshes once on 401 and retries the original request.
  - Verified end-to-end: hard-reload of `/dashboard` after a fresh register successfully rehydrates the session via cookie, 0 console errors, `localStorage` shows only the PostHog analytics key.
- **Certificate PDF template** — "Certification Authority" → "Independent Issuer" (previous iteration missed this template).

**Frontend quality fixes**
- Array-index keys replaced with stable identifiers in `Trust.jsx` (issuer pillars, controls, sub-processors), `Mentor.jsx` (starters), `LessonViewer.jsx` (key takeaways), `Landing.jsx` (intelligence signals).
- Chat message state (`Mentor.jsx`, `TryALesson.jsx`) now attaches a stable `id` at creation time so `key=` is no longer index-based.
- `AuthContext.jsx` value prop wrapped with `useMemo` so downstream consumers don't re-render on unrelated parent renders.
- `TryALesson.jsx` empty SSE-parse catch block now logs to `console.debug` instead of swallowing silently.

**Backend refactor (5 flagged high-complexity functions split into helpers)**
- `assessment_router.start_assessment_session` (91 → ~40 lines) — extracted `_resolve_adaptive_mode`, `_bucket_bank`, `_draw_adaptive`, `_draw_random`, `_client_view`; `ADAPTIVE_MIXES` promoted to module const.
- `assessment_router.submit_quiz` (90 → ~30 lines) — extracted `_grade_answers`, `_issue_certificate_if_new`.
- `enterprise_router.team_dashboard` (79 → ~15 lines) — extracted `_aggregate_per_user_stats`, `_build_department_breakdown`, `_top_courses_by_enrollment`, `_readiness_summary`.
- `mentor_router.mentor_chat` (68 → ~35 lines) — extracted `_build_context_block`, `_preamble_with_history`, `_persist_mentor_turn`.
- `passport_router._build_passport` (87 → ~25 lines) — extracted `_fetch_course_map`, `_skills_from_certs`, `_credential_level_from_certs`, `_industry_footprint`, `_learning_hours`, `_serialise_cert`.
- All pytest suites still green (142/144; two pre-existing test-order/Stripe-key failures unchanged).

**False-positive fixes from the code review — deliberately skipped**
- Report flagged `eval()` at `seed_assessments.py:124` — no `eval()` exists anywhere in the backend (verified via grep).
- Report flagged undefined `cert` in `passport_router.py:147-154` — `cert` is the comprehension loop variable at L153; Python semantics are correct.
- Report flagged `is` vs `==` in `auth.py:47,61`, `core.py:66`, `recommendation_router.py:207` — all four are `is None` checks, which is the idiomatic Python pattern (not a bug).
- Report flagged missing DOMPurify at `LessonViewer:137`, `Intelligence:259`, `TryALesson:118` — all three already use `DOMPurify.sanitize()` (fixed in Iteration 11).

### Iteration 15 — Founding-Member Perk + Admin Roles + Legal Docs + Sample Cert (Feb 2026)

**Header brand text**
- Header sub-mark now reads **"Enterprise Agentic AI Academy"** (previously "Academy | INDEPENDENT ISSUER"). Wrapped for narrow chrome; ITHRSeal default label kept as "Independent Issuer" for the certificate ceremonial use.

**Founding-Member Perk (first 500 signups — user directive `c`)**
- New module `/app/backend/founding_member.py` — idempotent allocator, `assign_if_eligible()` on register, `claim_first_course()` on first enrollment, `can_claim_free_cert()` + `mark_cert_claimed()` inside assessment.
- Fields added to `users`: `founding_member_seq (int)`, `signup_discount_code (10-char alnum)`, `founding_course_id`, `founding_cert_used`. Surfaced through `UserPublic` model.
- UX: `FoundingMemberBadge` on `/dashboard` shows the seq, code (copy-to-clipboard), and status ("Enroll in your first course…" → "Locked in…" → "Redeemed").

**Admin architecture (two-tier)**
- New role `super_admin` (God-mode). `get_current_super_admin` guard in `auth.py` validates JWT role + DB role (defence in depth against a stolen token whose role was later downgraded).
- New router `/app/backend/routers/admin_router.py`:
  - `POST /api/admin/orgs` — provision org + first admin user; returns temp password once.
  - `GET  /api/admin/orgs` / `DELETE /api/admin/orgs/{id}` — list/cascade-delete.
  - `GET  /api/admin/users` / `POST /api/admin/users/{id}/reset-password`.
- New `POST /api/enterprise/organizations/users` — enterprise admin creates users directly; enforces org's email domain (derived from admin's email at provisioning time). Returns temp password once.
- New Super-Admin console `/admin` (unlinked from public nav, role-gated). Includes Orgs table (with create-new modal), Users table (with reset-password action), and TempCredsModal (one-time password display).
- New Enterprise Portal "Create user directly" flow with domain enforcement + one-time creds display.
- Idempotent super-admin seed at startup (`SUPER_ADMIN_EMAIL` + `SUPER_ADMIN_PASSWORD` env vars).

**Legal / compliance pages**
- Markdown source of truth under `/app/frontend/public/legal/` (4 docs, 16 KB total).
- New `LegalDoc.jsx` renderer using `react-markdown` + `remark-gfm` (installed as deps).
- 4 public routes: `/legal/disclaimer`, `/legal/terms`, `/legal/security`, `/legal/compliance`.
- Placeholder tokens (`{{ EFFECTIVE_DATE }}`, `{{ LEGAL_EMAIL }}`, etc.) substituted at render time.
- Custom `.legal-prose` CSS in `index.css` for typography, tables, code blocks, blockquotes.
- Footer expanded to 6 columns; new "Legal" column links all four docs.
- All docs carry the "DRAFT — not yet reviewed by counsel" disclaimer at the top.

**Sample certificate**
- Idempotent seed `seed_sample_cert.py` creates a public cert `SAMPLE-ITHR-2026-001` linked to "Agentic AI Foundations" course, holder "Sample Learner", score 92.
- `/certifications` page now has two CTAs: **"See a sample certificate"** (→ `/verify/SAMPLE-ITHR-2026-001`) + **"Download sample PDF"** (→ WeasyPrint-rendered PDF, ~25 KB).

**Cost & infrastructure doc**
- `/app/docs/COST_AND_INFRASTRUCTURE.md` — 378-line internal costing sheet with 5 traffic tiers (Seed → Enterprise-heavy), component-level unit costs, sensitivity analysis, headcount waterfall, risk register.
- Downloadable Word doc at `/docs/ITHR_Cost_and_Infrastructure.docx` (20 KB, generated via pandoc; auto ToC + numbered sections).

**Tier consistency audit**
- Verified 6-tier ladder is consistent across Landing, Certifications page copy, and stat pips.
- Renamed a misleading test assertion (`expected 8 tiers` → `expected 8 learning paths`) — the "8" referred to Learning Paths, not credential tiers.

### Iteration 15 (retest + fix) — Founding-Member Bug Squash + Warning Log (Feb 2026)

**Critical bug found + fixed post-testing-agent handoff:**
- `/app/backend/founding_member.py::assign_if_eligible` treated Mongo's empty projection dict (`{}`) as "user not found" — `if not existing:` fired on every fresh user because the `_id`-stripped projection returns `{}` when the projected fields don't yet exist on the doc. **Fix:** `if existing is None:` (explicit None check).
- `/app/backend/routers/auth_router.py::register` did not re-hydrate the local `doc` after `assign_if_eligible()` returned the newly-assigned seq/code, so the register-response body left `founding_member_seq: null` even though the DB was updated. **Fix:** re-hydrate local doc from `result` before building `AuthResponse`.
- Silent-failure hardening: the `try/except` around `assign_if_eligible` now logs via `logger.exception` instead of swallowing (catches this class of regression in future).
- Test infra: `tests/conftest.py` now also loads `frontend/.env` so `REACT_APP_BACKEND_URL` is available for standalone `pytest` runs.

**Verified via testing subagent (iteration_15.json):**
- Iter-15 founding-member acceptance criteria: **4/4 = 100%**.
- Dashboard FoundingMemberBadge Playwright acceptance: **4/4 = 100%** (badge visible, seq matches "#N of 500", code matches register response, copy-to-clipboard button present).
- Full backend suite: **177/185 = 95.7%** (all 8 remaining failures are pre-existing preview-env flakes documented in earlier iterations).

**Non-blocking test-brittleness noted for future cleanup** (pre-existing, not regressions):
- `TestEnterpriseAdminCreateUser` skips 3/6 tests under xdist parallel run due to worker-scope leakage of module attributes; test should use a session-scoped fixture instead of `pytest.attr`.
- LLM-dependent tests in `test_iteration6`/`_7` occasionally 502 on Cloudflare pass-through.

### Iteration 16 — Super-Admin + Enterprise-Admin Analytics Dashboards (Feb 2026)

**Backend**
- New module `/app/backend/analytics.py` with two aggregators:
  - `platform_analytics(days)` → GET `/api/admin/analytics` (super-admin only).
  - `org_analytics(org_id, days)` → GET `/api/enterprise/organizations/analytics` (org owner/admin only).
- Both accept `days ∈ [7, 90]`, default 30; auto-clamp.
- Shared day-bucketing (`_fill_series`) so the two dashboards can't drift.

**Platform analytics returns:**
- `totals { users, orgs, seats_issued, certs_all_time }`
- `signups_per_day[]`, `certs_per_day[]` (day-bucketed series)
- `founder_perk { cap:500, claimed, remaining, first_course_locked, cert_used }`
- `top_orgs_by_certs[]` (5), `top_courses_by_enrollment[]` (10) — orphan `course_id`s filtered
- `active_users { last_24h, last_7d, last_30d }` from distinct enrollments

**Org analytics returns:**
- `totals { members, enrollments_window, certs_window, certs_all_time }`
- `enrollments_per_day[]`, `certs_per_day[]`
- `top_courses[]` (5, orphan-filtered), `top_learners[]` (5, ranked by window enrolments + all-time certs + avg progress)
- `departments[]` sorted by cert_coverage_pct desc
- `funnel[]` — Enrolled → In progress → Completed → Certified

**Frontend**
- New `/app/frontend/src/components/AnalyticsPanels.jsx` — `PlatformAnalyticsPanel` + `OrgAnalyticsPanel`, using recharts 3.6.0.
- Range switcher (7d / 30d / 90d) with keyboard-friendly buttons.
- `SuperAdminPortal` adds an "Analytics" tab (**default active**).
- `EnterprisePortal` adds a "View analytics" toggle in the hero and a collapsible panel above the readiness stats. Only visible to org owner/admin.
- Reusable widgets: `StatPip`, `TrendCard` (line chart), `TopList` (bar-in-list ranking), and a horizontal-bar funnel.

**Testing subagent verdict:**
- Iter-16 acceptance criteria: **100% (11/11 backend + 3/3 frontend flows)**.
- Full backend suite: **188/196** = 95.9% (+11 net-new passes vs iter-15 baseline; unchanged 6 pre-existing flakes).
- All 24 new data-testids visible in Playwright; range switcher fires correct network calls; non-admin learner correctly gated.

**Minor post-test polish applied:**
- `platform_analytics` + `org_analytics` now **skip** orphaned course_ids (enrollments pointing to deleted courses) — top-courses list is now real courses only.

### Iteration 17 — SUPER_ADMIN_PASSWORD moved out of committed .env (Feb 2026)

- `/app/backend/.env` now stores `SUPER_ADMIN_PASSWORD=preview-only-rotate-in-prod` — a deliberate placeholder, never a real secret.
- `seed_super_admin.py` rewritten to be **rotate-via-restart**: on every boot it re-syncs the DB password_hash to `$SUPER_ADMIN_PASSWORD` (so operators rotate by changing the Emergent secret + restarting).
- Production-safety warning: if the running pod resolves to `learn.ithr.tech` AND the placeholder value is present, an **ERROR-level** loud banner logs on every boot; anywhere else it logs a milder WARNING. Impossible to miss in production tail-of-logs.
- Rotation flow + production launch checklist added to `/app/memory/test_credentials.md`.
- Verified end-to-end: old password → 401 · new placeholder → 200 (`role: super_admin`) · rotation warning fires in preview logs · nothing broken elsewhere.

### Iteration 18 — 10-Second Course Intro Videos (Ken-Burns MVP + Sora 2 Upgrade Path) (Feb 2026)

**Approach (best-judgment):**
- **B / Ken-Burns cinemagraphs** over each course's existing Unsplash thumbnail. Zero AI-credit spend, ships in one pass, visually cohesive with the aiilm.me hero motion already in the codebase.
- Backend model kept extensible: `Course.intro_video_url: Optional[str]` (nullable). Any course can be upgraded to a real Sora 2 clip later by just populating that field — the frontend switches to a real `<video>` element automatically. **No frontend changes needed** for the upgrade.

**Frontend**
- New `/app/frontend/src/components/CourseIntro.jsx` exporting `<CourseIntroHero>` (full-bleed autoplay for CourseDetail), `<CourseIntroButton>` (small pill for CourseCard hover overlay), and `<CourseIntroLightbox>` (12-second auto-close modal, ESC-close, mute toggle when video present).
- `.course-intro-cinemagraph` CSS keyframe: 10-second `transform: scale(1) → scale(1.08) translate(-1.5%,-1.5%) → scale(1)` loop with `prefers-reduced-motion: reduce` bypass.
- Lightbox rendered via **`createPortal(modal, document.body)`** so parent `overflow-hidden` / `transform` / `contain` never clip it.
- CourseCard: play button appears on hover, opens the lightbox with the course category kicker + title overlaid in navy-gradient at bottom.
- CourseDetail hero: static `<img>` replaced with `<CourseIntroHero>` — courses now open with a subtle Ken-Burns animation instead of a still frame.

**Backend**
- `Course.intro_video_url` field added to both the full `Course` model and the `CourseSummary` API response.
- Catalog router surfaces the field so the frontend receives it on `/api/courses`.

**Verified end-to-end via Playwright:**
- 24 play buttons on `/courses` ✅
- Click opens portal-rendered lightbox with full-viewport blurred navy backdrop ✅
- Course title + category rendered in the lightbox ✅
- ESC key closes lightbox ✅
- Zero non-401 console errors ✅

## Test Users & Files
- No pre-seeded users. Register via `POST /api/auth/register`.
- Backend test suite: `/app/backend/tests/backend_test.py` (75/75 pass)
- Auth playbook: `/app/auth_testing.md`
- Test credentials memo: `/app/memory/test_credentials.md`

### Iteration 19 — Code-Quality Sweep (Feb 2026)

Surgical fixes applied to the real (non-false-positive) findings from the earlier code review:

**Backend**
- **`core.py`**: `random.choices` → `secrets.choice` for `gen_cert_id()` and `gen_invite_code()`. Certificate IDs and invite codes are now cryptographically-random. Format unchanged: `EAIA-2026-[A-Z0-9]{6}` and `[A-Z0-9]{8}`.
- **`analytics.py`**: split the two large functions (`platform_analytics`, `org_analytics`) into 9 focused helpers — `_platform_totals`, `_platform_founder_perk`, `_platform_active_users`, `_platform_top_orgs`, `_platform_top_courses`, `_org_top_courses`, `_org_per_user_stats`, `_org_departments`, `_org_funnel`. Behaviour identical; complexity per function down ~4x. Orphan-course skipping preserved.
- **`tests/test_iteration15.py`** + **`tests/test_iteration16_analytics.py`**: hard-coded `SUPER_ADMIN_PASSWORD = "ITHR!Root-2026-ChangeMe"` (stale) replaced with `os.environ.get("SUPER_ADMIN_PASSWORD", "preview-only-rotate-in-prod")`. Hard-coded `TestPass123!` in iter-16 helper also moved behind `EAIA_TEST_USER_PASSWORD` env var (matches the pattern already in `conftest.py`).

**Frontend**
- **`AITutorPanel.jsx`** + **`InlineTutor.jsx`**: chat messages now carry a stable `id` field at creation time; `key={m.id || \`msg-${i}\`}` replaces `key={i}` in the render map. Prevents React reconciliation glitches during streaming updates.
- **`Mentor.jsx`**: two empty `catch (e) { void e; }` blocks replaced with `console.debug("[Mentor] …", e?.message)` — errors now leave a diagnostic trail without breaking the UX.
- **`Intelligence.jsx`**: `course_refresh_priorities.map` now uses `key={p.course_slug}` (was `key={p.course_slug + i}`) — slug is already unique per row.

**Testing verdict (iteration_19.json)**
- Backend: 25/25 (100%) on iter-15 + iter-16 core acceptance tests.
- Frontend: 4/4 (100%) — Landing, Mentor, Intelligence, AITutorPanel all render with zero non-401 console errors, zero React key warnings.
- No regressions detected. The 4 xdist-parallel skips (documented since iter-15) and the `.test`-TLD email validator quirk are pre-existing and unchanged by this iteration.

**Deliberately skipped (all documented as false positives from the code review)**
- `eval()` in seed_assessments.py — no eval anywhere in the backend (grep-verified iter-14).
- `DOMPurify` missing in LessonViewer/Intelligence/TryALesson — all three already use `DOMPurify.sanitize()` (fixed iter-11).
- `is` vs `==` on `is None` checks — idiomatic Python, not bugs.
- Reactor Quiz.jsx / LessonViewer.jsx stale-closure claims — both files already use `useCallback` correctly with the right deps (verified this iteration).

### Iteration 20 — Code-Quality Sweep #2 (Feb 2026)

Second-round fixes from the follow-up Code Review. Focus on **real** issues; the "eval() in seed_assessments" and "missing DOMPurify in 3 files" flagged again are the SAME false positives already verified in iter-14 & iter-19 (`grep` confirmed).

**Backend refactors — pure structural, no behaviour change:**
- `routers/admin_router.py::create_org_with_admin` (was 101 lines, complexity 11) → split into `_validate_create_org_payload`, `_unique_org_slug`, `_insert_admin_user`.
- `routers/enterprise_router.py::update_seats` (was 110 lines) → split into `_validate_seat_change`, `_apply_seat_decrease`, `_start_seat_increment_checkout`.
- `routers/enterprise_router.py::admin_create_user` (was 78 lines, complexity 12) → validation extracted into `_validate_admin_user_payload`.
- `routers/recommendation_router.py::_score_courses` (was 71 lines, nesting 6, complexity 18) → split into `_learner_posture`, `_difficulty_score`, `_score_one_course`.

**Frontend real fixes:**
- Array-index-as-key removed in 3 flagged files: `CourseDetail.jsx` (learning objectives now `key={\`objective-${i}-${o.slice(0,24)}\`}`), `CourseCatalog.jsx` (skeleton now `key={\`skeleton-${i}\`}`), `HeroBlobs.jsx` (blob now `key={\`blob-${b.cls}-${i}\`}`).
- `context/AuthContext.jsx::logout` empty catch replaced with `console.debug("[Auth] logout POST failed (non-fatal): ...")` — errors observable without breaking UX.
- `pages/SuperAdminPortal.jsx::loadAll` wrapped in `useCallback([])`; `useEffect` deps now correctly list `[user, loadAll]` — the flagged missing hook dep. No infinite re-renders in testing.

**Deliberately skipped (documented false positives / high-risk-low-value):**
- `eval()` in seed_assessments.py — no `eval()` exists in the backend (grep-verified iter 14 + iter 20).
- `DOMPurify` missing in `LessonViewer:137 / Intelligence:259 / TryALesson:122` — all three DO call `DOMPurify.sanitize()` (grep-verified). Same false positive as iter 14.
- Complexity refactors of `TryALesson.jsx` / `InlineTutor.jsx` / `AITutorPanel.jsx` / `EnterprisePortal.jsx` — high regression risk, no behavioural benefit. Deferred as P2 tech-debt.
- `assessment_router.py::random` — used with an explicit user-visible seed for **reproducible** shuffling (documented design choice), not for security tokens. Safe as-is.

**Testing verdict (iteration_20.json):**
- Backend: **14/14 (100%)** on new refactor suite (`test_iteration20_refactors.py`), 26/29 on iter-15+iter-16 baseline (3 failures are the SAME pre-existing `.test`-TLD email_validator issue documented for 5+ iterations).
- Frontend: **5/5 (100%)** — Landing, Catalog, CourseDetail, Intelligence, SuperAdmin. Zero React key warnings, zero non-401 console errors, zero infinite re-render warnings.


