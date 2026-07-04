# Enterprise Agentic AI Academy — PRD

## Original Problem Statement (Summary)
Build a commercially deployable enterprise SaaS Learning & Certification Platform for Agentic AI — positioned as "Enterprise AI Workforce Transformation Platform" competing with Coursera Business, Microsoft Learn, Salesforce Trailhead, and AWS Skill Builder. Serve individual learners AND Fortune 500 companies. Course structure: 15 modules across 3 levels (Free 1–5, Premium 6–10, Certification 11–15). Multiple industries. Assessment engine + certification engine + AI tutor + enterprise dashboards.

## User Choices Confirmed (Feb 2026)
- Pillars: Learner portal + Assessment engine + Certification engine + Course catalog with industry tracks
- AI: Claude Sonnet 4.5 via Emergent Universal LLM key
- Auth: JWT email/password **+** Emergent-managed Google OAuth (both flows)
- Payments: deferred (mark courses free/premium, no real Stripe yet)
- Seed content: 1 full 15-module course + 22 catalog-metadata courses

## Personas
- Individual Learner (professional, developer, student)
- Corporate Learner (HR, PM, analyst)
- Training Manager / L&D
- CXO / Enterprise Leader
- Instructor / Content Author (deferred)
- Corporate Admin (deferred to Milestone 2)
- Super Admin (deferred)

## Core Requirements (Static)
1. **Auth**: JWT email/password + Google OAuth (both issue same JWT format, unified user record).
2. **Course Catalog**: 20+ categories, 22 industries, 8-tier certification ladder, filter/search.
3. **Course Structure**: 15 modules × ~5 lessons, 3 levels (Free/Premium/Certification).
4. **Assessment Engine**: MCQ/multi-select/true-false/scenario. Randomized pool ready. 65% pass threshold.
5. **Certification Engine**: Unique EAIA-2026-XXXXXX ID, public verification portal, printable credential.
6. **AI Tutor "Aletheia"**: Streaming Claude Sonnet 4.5 via Emergent Universal Key, session-persistent chat.
7. **Progress Tracking**: XP, streaks, per-lesson completion, enrollment progress bars.
8. **Enterprise Marketing Pages**: Enterprise value prop, industry tracks, certification paths.

## What's Been Implemented (Feb 2026 — Milestone 1 Core)
- ✅ Backend (FastAPI + MongoDB + JWT + bcrypt)
- ✅ Backend auth: register / login / me + Emergent Google OAuth exchange (`/api/auth/google/callback`)
- ✅ Course catalog: 1 full course (Agentic AI Foundations — 15 modules, 75 lessons, 12-question quiz) + 22 catalog metadata courses
- ✅ Enrollment + lesson completion + progress tracking
- ✅ Quiz engine with scoring + certificate auto-issuance on pass
- ✅ Public certificate verification portal
- ✅ AI Tutor "Aletheia" (Claude Sonnet 4.5, SSE streaming, persistent chat sessions)
- ✅ Landing page (Ivy League design), Course Catalog with filters, Course Detail, Lesson Viewer, Dashboard, Quiz, Certificate view, Verify page, Industries page, Enterprise pricing page, Certifications ladder
- ✅ Frontend design: Cormorant Garamond + IBM Plex Sans + crimson accent, parchment/oxford palette
- ✅ Emergent Google OAuth flow + email/password (dual login on both /login and /register)
- ✅ Test coverage: 27/27 backend pytest tests passing

## Prioritized Backlog

### P0 (next iteration)
- **Payments/Subscriptions**: Stripe integration for premium tier + enterprise seats
- **Full curriculum authoring**: Extend the 22 catalog courses with real lesson content
- **AI course generator UI**: The backend endpoint exists (`/api/ai/generate-course`) but no admin UI

### P1 (Milestone 2)
- **Enterprise Portal** (Layer 2): org management, employee dashboard, department analytics
- **AI Skills Passport** (Layer 2): portable verifiable competency record
- **Manager dashboards** (Layer 2): team progress, skill gaps
- **AI Mentor + AI Career Advisor**: role-based coaching separate from lesson-tutor
- **AI Recommendation Engine**: next-best course based on progress + role
- **Renewal / CE credit engine**: keep credentials current

### P2 (Milestone 3 — production hardening)
- Multi-tenant white-label + SSO (Azure AD, Okta, SCIM/LDAP)
- Multi-language content
- Advanced proctoring (webcam + screen)
- Blockchain credential anchoring (currently stub)
- Kubernetes deployment, load testing (10M users / 100k concurrent target)
- SOC 2 / ISO 27001 / GDPR / FERPA formal evidence

## Next Tasks (immediate)
1. Wire real payments (Stripe) with tiered plans for Layer 1 sellability
2. Author lesson content for 5 more catalog courses (Industry-specific: Banking, Healthcare, Manufacturing, RAG, Multi-Agent)
3. Build Enterprise Portal MVP (org registration, invite employees, view team progress)
4. Add AI-course-generator admin UI (backend endpoint ready)

## Test Users
- No pre-seeded accounts. Register fresh via `/api/auth/register`.
- See `/app/memory/test_credentials.md` and `/app/auth_testing.md`.
