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

## Test Users & Files
- No pre-seeded users. Register via `POST /api/auth/register`.
- Backend test suite: `/app/backend/tests/backend_test.py` (75/75 pass)
- Auth playbook: `/app/auth_testing.md`
- Test credentials memo: `/app/memory/test_credentials.md`
