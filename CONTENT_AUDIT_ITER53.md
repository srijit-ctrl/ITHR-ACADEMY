# Iteration 53 · Content Audit Report

**Generated:** Feb 2026
**Scope:** All 28 courses in the ITHR Academy catalog + supporting marketing pages.

---

## 1. Broken routes (P0)

Both slugs reported as 404 by the auditor return **HTTP 200** from the API in preview.

| Slug | API status | Likely user-visible issue |
|------|------------|---------------------------|
| `chief-ai-officer-track` | 200 | Rendered a stub curriculum with a working Enroll button — read by the auditor as "broken" |
| `ai-change-management` | 200 | Same pattern as above |

**Fix applied:** every course now returns a `status` field (`published` or `coming_soon`). Both slugs above are `coming_soon`; the frontend now renders a "Coming soon" badge, a "Notify me when live" CTA, hides the "Verified digital credential" claim, hides "Certification Track" branding, and replaces the hardcoded objectives/module count with real data. If your prod DB is state-consistent with preview, these routes will now be honest and no longer misidentified as broken.

**No other routes 404.** All 28 slugs resolve.

---

## 2. Stub-vs-published census (P0)

Derived at read-time by `derive_status()` in `routers/catalog_router.py`. A course is `published` only if it has non-empty `learning_objectives` AND ≥10 modules AND does not carry the "Full curriculum in preparation" marker.

**11 published** (real 15-module curriculum):
`agentic-ai-foundations`, `prompt-engineering-mastery`, `multi-agent-systems`, `rag-enterprise`, `ai-governance-compliance`, `agentic-ai-banking`, `agentic-ai-healthcare`, `agentic-ai-manufacturing`, `agentic-ai-retail`, `agentic-ai-government`, `agentic-ai-talent-acquisition`.

**17 coming_soon** — all shipped as 4-module stubs with empty objectives/skills/business_value and the "Full curriculum in preparation" description:

`generative-ai-executives`, `llm-architecture-deep-dive`, `ai-security-red-team`, `agentic-ai-hospitality`, `ai-product-management`, `ai-architecture-enterprise`, `vector-databases`, `fine-tuning-llms`, `ai-devops-mlops`, `ai-change-management`, `responsible-ai`, `chief-ai-officer-track`, `mcp-a2a-protocols`, `ai-observability`, `agentic-ai-performance-management`, `agentic-ai-succession-planning`, `agentic-ai-learning-development`.

**Path taken (per your P0 direction):** Option A applied uniformly to all 17. No course can now show "Enroll" + "Verified credential" + placeholder objectives simultaneously.

---

## 3. Template bugs (P0)

**Fixed:** `CourseDetail.jsx` no longer hardcodes:
- `"15 modules across 3 tiers"` → now computed from `course.modules` (counts real modules and real tier presence).
- `"Hands-on labs & capstone project"` → only shown when there are actual lessons.
- `"Verified digital credential upon passing"` → hidden on `coming_soon` courses.
- `"Personal AI tutor throughout"` → hidden on `coming_soon` courses.
- Placeholder-objectives fallback text (`"Deep understanding of the course subject..."`) → removed. If a course has no objectives we now show a plain "Detailed learning objectives will be published when this course launches" message with waitlist CTA.
- `CourseCard.jsx` similarly no longer defaults to `|| 15` modules; it displays the true count and paints a "Coming soon" chip in place of the freshness score for `coming_soon` cards.

Also fixed: the `POST /api/courses/{slug}/enroll` endpoint returns **409 Conflict** for any `coming_soon` course, so the CTA cannot be bypassed by direct-fetch. A new `POST /api/courses/{slug}/waitlist` endpoint replaces it for stubs (idempotent, records interest in `course_waitlist`).

---

## 4. Marketing headline (P1)

**Fixed** in three places (`Certifications.jsx`, `Landing.jsx` hero, `Landing.jsx` ladder section):

- Was: "Six tiers. / One global standard." — factually wrong; `/api/catalog/certification-paths` returns eight tiers.
- Now: "Eight tiers. / One global standard." — matches the API.

If the content owner wanted the tier count reduced, that's a separate data change (edit `CERTIFICATION_PATHS` in `seed_data.py`); not touching that without direction.

---

## 5. Citations (P1)

**"Landmark Case Studies" (module 1, lesson 3 of Agentic AI Foundations)** — now cites all three landmark claims with primary sources:

- Klarna → [Klarna press release, 27 Feb 2024](https://www.klarna.com/international/press/klarna-ai-assistant-handles-two-thirds-of-customer-service-chats-in-its-first-month/)
- Anthropic Claude → [Claude 3.5 Sonnet launch page](https://www.anthropic.com/news/claude-3-5-sonnet)
- Salesforce Agentforce → [Agentforce 2.0 press release, 17 Dec 2024](https://www.salesforce.com/news/press-releases/2024/12/17/agentforce-2-announcement/)

Added a "**Source:**" line under each claim and an editorial caveat that all figures are vendor-reported, not independently audited. Updated in both `backend/seed_data.py` (seed source of truth) AND `backend/assets/generated_courses/content_overrides.json` (runtime override — this was the file actually served).

### Uncited numeric-company claims flagged for SME review (39 more)

The audit script (see below) found 39 additional places where a named vendor (`Klarna`, `Anthropic`, `Salesforce`, `Goldman Sachs`, `UnitedHealth`, `OpenAI`, `Microsoft`, `Google`, `Amazon`, `Meta`, `McKinsey`, `Gartner`, `Forrester`, `IDC`, `PwC`, `Deloitte`, `Accenture`, `Bain`) is quoted alongside a specific number without a link. Not fixing these blindly — many require the SME to confirm whether the underlying claim is: (a) a public press-release figure that needs a URL added, (b) a synthetic teaching example that should be relabeled "hypothetical", or (c) genuinely apocryphal and should be removed.

**Top hotspots by course:**

- `agentic-ai-foundations` — 10 instances across lessons 3:3 (Constitutional AI), 4:0 (API keys), 5:1 (embedding pricing), 7:0 (Goldman Sachs trading desk case), 7:1 (embedding options), 11:1 (Microsoft Azure AI Content Safety). Also two mentions in the module wrap (0:4) that reference the now-cited landmark cases — these can inherit the citations by cross-reference.
- `multi-agent-systems` — 2 instances (3:2 OpenAI cost figure, 13:1 Salesforce clinical-trial case).
- `rag-enterprise` — 2 instances (1:1 embedding pricing, 8:0 Anthropic 200k context).
- Others (`ai-governance-compliance`, `prompt-engineering-mastery`, `agentic-ai-banking`, etc.) — remaining ~25 spread across the industry / vertical courses. Full JSONL dump available on request.

Recommendation: give this list to the SME author with a directive to either (a) add a citation, (b) replace with a "hypothetical example" framing, or (c) delete. I can wire in the citations once the source URLs are provided — no code work needed, just the JSON patch.

---

## 6. Assessment mechanism (P2 — verification only)

**Confirmed: a real graded exam exists.** No new exam system needed.

- Frontend route: `/quiz/:slug` → `frontend/src/pages/Quiz.jsx`.
- Backend endpoints:
  - `POST /api/courses/{slug}/assessment/session` — starts a proctored session (see `routers/assessment_router.py` L112).
  - `POST /api/courses/{slug}/quiz/submit` — grades submission and issues certificate on pass (L242).
- Entry point in the UI: `CourseDetail.jsx` renders "Attempt certification exam" button only when the caller is **enrolled** AND the course has `quiz.length > 0`. The auditor didn't see it because they were either not enrolled or looking at a stub course (stubs have no quiz).
- The lesson-level "Reflection Questions" they saw are correct — those are ungraded self-check prompts inside lessons. The graded certification exam is a separate course-level surface, gated behind enrollment.

**Confirmed defect there is none.** The audit's assumption was based on incomplete exploration.

---

## Additional defects found beyond your list

1. **`AI Ops` panel referred to `has_full_content` as the publication gate** on the catalog card. That flag is set by the seed but not consistently maintained; using `status` derived at read-time is now the single source of truth. `has_full_content` still works but the UI now defers to `status`.
2. **Cache TTL:** the `/api/courses` list is cached 180s (`@cached(ttl_seconds=180, key_prefix="catalog_courses")`). Editorial updates to a course's objectives may take up to 3 minutes to reflect in the catalog. Non-blocking; documented for the content team.
3. **Freshness badge** was showing on stub cards. Now hidden for `coming_soon` — a freshness score on an empty curriculum is misleading.
