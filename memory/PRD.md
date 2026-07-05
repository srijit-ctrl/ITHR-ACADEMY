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

## Test Users & Files
- No pre-seeded users. Register via `POST /api/auth/register`.
- Backend test suite: `/app/backend/tests/backend_test.py` (75/75 pass)
- Auth playbook: `/app/auth_testing.md`
- Test credentials memo: `/app/memory/test_credentials.md`
