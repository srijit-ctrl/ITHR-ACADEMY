# Enterprise Agentic AI Academy — PRD

## Original Problem Statement (Summary)
Build a commercially deployable enterprise SaaS Learning & Certification Platform for Agentic AI, positioned as an "Enterprise AI Workforce Transformation Platform" and delivered as an ITHR Technologies Consulting LLC value proposition. Serves individuals and Fortune 500 organizations. 15-module × 3-level course structure. 20+ industries. Assessment, certification, AI tutor, enterprise dashboards, real-time curriculum intelligence, tiered pricing.

## User Choices Confirmed
- Pillars: Learner portal + Assessment engine + Certification engine + Course catalog with industry tracks + Real-time intelligence
- AI: Claude Sonnet 4.5 via Emergent Universal LLM key
- Auth: JWT email/password + Emergent-managed Google OAuth
- Payments: **Stripe** (test key `sk_test_emergent`) — activated in iteration 3
- Branding: ITHR Technologies (teal #00A896 + navy)

## What's Been Implemented

### Iteration 1 — MVP Core (Feb 2026)
- FastAPI + MongoDB backend with JWT + bcrypt + Emergent Google OAuth
- 1 full course (15 modules, 75 lessons, 12-Q quiz) + 22 catalog metadata courses
- Enrollment, lesson completion, XP, streaks
- Quiz + certificate auto-issuance + public verification
- AI Tutor Aletheia (Claude Sonnet 4.5, SSE streaming, persistent sessions)
- All pages: Landing, Catalog, Course Detail, Lesson Viewer, Dashboard, Quiz, Certificate, Verify, Industries, Enterprise, Certifications, Login/Register
- 27/27 backend tests + full frontend e2e pass

### Iteration 2 — ITHR Rebrand + Intelligence Desk
- ITHR Technologies rebrand: logo in header + footer + hero, teal + navy palette, copyright ITHR Technologies Consulting LLC
- Dedicated `/pricing` page with 6 plans (3 individual + 3 enterprise)
- Real-time **Intelligence Desk**: public `/intelligence` briefing with 8 signals + 8 course refresh priorities (Claude Sonnet 4.5, 6h Mongo cache)
- Backend endpoints: `GET /api/intelligence/briefing` and `GET /api/intelligence/course/{slug}/refresh`
- 33/33 backend tests pass

### Iteration 3 — Full Catalog Expansion + Freshness + Stripe (current)
- **4 additional full 15-module courses authored**: `prompt-engineering-mastery`, `rag-enterprise`, `multi-agent-systems`, `ai-governance-compliance` (each ~45 real lessons + 12-Q quiz). Total full courses: **5**.
- **Course freshness system**: every course carries `last_reviewed_at`, `freshness_score` (55-100), `days_since_review`. Surfaced on:
  - CourseCard: teal freshness pill (top-right of thumbnail) + "REFRESHED Xd/mo ago" text
  - CourseDetail: freshness pill + refreshed-ago text in hero meta row
- **Stripe integration** (via `emergentintegrations.payments.stripe.checkout`):
  - Fixed server-side packages: `practitioner_monthly` $29, `practitioner_annual` $290, `professional_track` $499, `team_monthly_per_seat` $18/seat (10-100 seats)
  - `POST /api/checkout/session` — auth-gated, creates Stripe checkout + `payment_transactions` record (`initiated`)
  - `GET /api/checkout/status/{session_id}` — auth-gated, polls Stripe + idempotently grants subscription (`subscription_tier`, `subscription_expires_at`)
  - `POST /api/webhook/stripe` — public webhook, idempotent fulfillment
  - Frontend Pricing buttons wired to Stripe checkout; `/pricing/success` polling page grants tier on paid
- 55/55 backend tests pass

## Prioritized Backlog

### P0 — Next
- Enterprise Portal (org register + invite employees + team analytics dashboards)
- Author 5 more full courses (industry-specific: Banking, Healthcare, Manufacturing, Retail, Government)
- Wire "push signals into curriculum" action on `/intelligence` — one-click to spawn AI-drafted lesson patches
- Admin UI for AI course generator + subscription management
- Refactor server.py (~906 lines) into routers/*.py

### P1 — Milestone 2 (Layer 2 Enterprise Transformation)
- AI Skills Passport
- Role-based learning paths (HR, Finance, Sales, Procurement, Manufacturing)
- Manager dashboards
- AI Mentor + AI Career Advisor
- AI Recommendation Engine
- Renewal / CE credit engine
- Weekly email digest to enterprise buyers

### P2 — Milestone 3 (Production Hardening)
- Multi-tenant white-label, SSO (Azure AD, Okta, SCIM/LDAP)
- Multi-language content
- Advanced proctoring
- Blockchain credential anchoring
- Kubernetes + load testing (10M / 100K concurrent)
- SOC 2 / ISO 27001 / GDPR / FERPA formal evidence

## Next Tasks (Immediate)
1. Enterprise Portal MVP (org onboarding + team dashboards)
2. 5 more industry-specific full courses
3. Wire freshness display into Intelligence Desk course-refresh flow
4. Split server.py into routers for maintainability

## Test Users & Files
- No pre-seeded users. Register via `POST /api/auth/register`.
- Backend test suite: `/app/backend/tests/backend_test.py` (55/55 pass)
- Auth playbook: `/app/auth_testing.md`
- Test credentials memo: `/app/memory/test_credentials.md`
