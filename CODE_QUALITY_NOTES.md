# Code Quality Scanner — False Positive Registry

Automated code-quality scanners repeatedly flag the same items on this codebase.
**Every item below has been manually verified as a false positive**. Future
agents and reviewers should consult this list before "fixing" any of them.

Last verified: Feb 2026 (iter-29 + iter-30 review cycles)

---

## Confirmed False Positives — DO NOT CHANGE

### 1. `dangerouslySetInnerHTML` XSS warnings
- `frontend/src/pages/LessonViewer.jsx:137`
- `frontend/src/pages/Intelligence.jsx:259`
- `frontend/src/components/demo/DemoLessonBody.jsx:21`

**Why safe:** All three sites already wrap content in `DOMPurify.sanitize(...)`
before rendering. Scanners flag the pattern `dangerouslySetInnerHTML` without
inspecting the sanitization wrapper. Grep for `DOMPurify.sanitize` in each
file to confirm.

### 2. `eval()` in `backend/seed_assessments.py`
- **Report says:** line 124 contains `eval()` code injection risk.
- **Reality:** The file contains **no `eval()` calls at all**. Line 124 is a
  plain dict literal in a static seed-data list. Run
  `grep -n "eval(" /app/backend/seed_assessments.py` — it returns nothing.
- Likely triggered by a substring match against the word "evaluate" somewhere
  in the file's course content strings.

### 3. `seed_super_admin.py:29` "hardcoded secret"
- **Line 29:** `PLACEHOLDER_PASSWORD = "preview-only-rotate-in-prod"`
- **Why safe:** This is a **sentinel constant** used to detect misconfiguration
  in production. Read the module docstring — it explicitly warns operators
  when this placeholder appears as the active password in a production env.
  It is not the actual password; it is a detector string.
- The **actual** password comes from `os.environ.get("SUPER_ADMIN_PASSWORD")`.

### 4. React hook dependency warnings (49 alleged instances)
- Reports flag `Quiz.jsx:21`, `LessonViewer.jsx:16`, `SuperAdminPortal.jsx:28`,
  `Intelligence.jsx:34`, `MemberList.jsx:10`, `AuthContext.jsx`, and others.
- **Reality:** `eslint-plugin-react-hooks` (the authoritative React hook
  linter) reports **zero issues** across all flagged files. Every loader
  function is already wrapped in `useCallback` with correct dependencies.
- Run `mcp_lint_javascript` on any of the files to confirm.

### 5. `random` module in `routers/assessment_router.py`
- Lines 39, 62, 74, 90 — used for shuffling quiz question order and answer
  option positions.
- **Why safe:** This is **not** a security-sensitive operation. Question
  shuffle order does not need cryptographic unpredictability — a learner
  guessing the sequence gains nothing (the correct answers are re-mapped
  per-attempt).
- Line 132 already uses `random.SystemRandom()` (crypto-grade) for the
  top-level RNG choice, so seeded shuffles remain reproducible while
  unseeded shuffles use OS entropy.

### 6. `is True/False/None` vs `== True/False/None` in test files
- **Reports say** 101 instances across `tests/test_iteration*.py`.
- **Reality:** `is None` / `is True` / `is False` is the **correct** Python
  idiom per PEP 8 (identity check for singletons). Replacing these with `==`
  would be a regression — `== True` would accidentally match `1`, `== False`
  would match `0`, `== None` would defer to `__eq__` overrides. Keep as-is.

### 7. Console statements (`console.debug`, `console.error`)
- All present console statements fall into two safe categories:
  - `console.error(...)` for surfacing genuine load/save failures (Quiz.jsx,
    LessonViewer.jsx).
  - `console.debug(...)` inside catch blocks for silent-recovery diagnostics
    (Mentor.jsx, AuthContext.jsx, ActivityFeedPanel.jsx, sseStream.js).
- No stray `console.log` calls exist anywhere in the frontend.

### 8. Nested ternary expressions
- Cosmetic preference, not a bug. The current usage in Quiz.jsx (line 124),
  LessonViewer.jsx (line 179), and SeatEditorModal.jsx render conditional
  UI text/classes; extracting to helpers here would add indirection without
  clarifying intent.

---

## P3 Maintainability Backlog (Optional)

These are **not bugs** but genuine complexity items on the backlog. They can
be tackled in a dedicated refactor session; they do not impact correctness or
production readiness:

- `routers/digest_router.py:_build_digest_html` (137 lines)
- `routers/enterprise_router.py:fulfill_seat_increment` (114 lines)
- `purge_test_data.py:purge` (80 lines)
- `routers/admin_router.py:create_org_with_admin` (70 lines)
- `components/enterprise/MemberList.jsx` (161 lines)
- `components/AnalyticsPanels.jsx:OrgAnalyticsPanel` (88 lines)
- `components/admin/ActivityFeedPanel.jsx` (84 lines)
- `components/demo/DemoChat.jsx` (77 lines)

---

## Applied Real Fixes (from previous scans)

For historical context, the following **were** real issues from earlier
scan reports and have already been fixed:

- `tests/test_iteration28_activity_feed.py` — hardcoded super-admin creds
  moved to `os.environ.get(...)` with placeholder fallback.
- `routers/assessment_router.py` — unseeded RNG upgraded to `SystemRandom()`.
- `routers/admin_router.py:list_all_orgs` — N+1 query replaced with `$lookup`
  aggregation.
- `server.py` — added `/health` endpoint for K8s liveness probes.

---

## Scanner Suppressions Applied (iter-31, Option A)

To finally silence the recurring scanner reports, inline suppression comments
have been added at each confirmed-false-positive site:

- `backend/seed_super_admin.py:29` — `# nosec B105` on `PLACEHOLDER_PASSWORD`.
- `backend/routers/assessment_router.py:132` — `# nosec B311` on the
  `random.Random(seed)` fallback (non-security question shuffling).
- `frontend/src/pages/LessonViewer.jsx:136` — `// eslint-disable-next-line
  react/no-danger` above the DOMPurify-sanitized `dangerouslySetInnerHTML`.
- `frontend/src/pages/Intelligence.jsx:259` — same suppression above the
  DOMPurify-sanitized `dangerouslySetInnerHTML`.
- `frontend/src/components/demo/DemoLessonBody.jsx:22` — same suppression
  above the DOMPurify-sanitized `dangerouslySetInnerHTML`.

**Items that cannot be suppressed in code** (scanner has no way to silence):

- `seed_assessments.py:124` — the scanner "eval() RCE" flag is triggered by
  substring-matching the word **"evaluate"** in question content
  (line 138 contains `"RAGAS evaluates"`). Nothing to suppress in code;
  scanner needs to be reconfigured or ignored.
- 49 "missing React hook deps" — `eslint-plugin-react-hooks` reports zero
  issues, so no `// eslint-disable-next-line react-hooks/exhaustive-deps`
  comments are warranted. Scanner is producing phantom findings.
- `is True/False/None` in test assertions — the linters actually configured
  (ruff, pylint) do not flag these because they are correct per PEP 8.
- 13 "undefined variables" — reported with no file/line references. Cannot
  action a hallucination without a specific location.

- `components/admin/ActivityFeedPanel.jsx` — silent catch now emits
  `console.debug` for devtools observability while preserving polling
  recovery behavior.


---

## Feb 2026 update — Iter 38 review-cycle additions

### 8. Hardcoded credentials in `backend/tests/test_iteration36_*.py` / `test_iteration38_*.py`
- **Report says:** hardcoded secret at line 19/31/44 leaks credentials.
- **Reality:** These are the documented **test fixtures** for the super-admin
  account (`superadmin@ithr.online` / `Dubai_deram2026`) that already appears
  in `/app/memory/test_credentials.md`. Every test-agent run reads the same
  credentials from that memory file. There is no separate production secret
  to leak — prod uses `SUPER_ADMIN_PASSWORD` from Emergent Secrets, not this
  string. Test files are excluded from the production build; the pattern is
  standard for pytest fixtures.
- **What we did do:** the real fix (already shipped iter-30) is that the
  seed script gates on `os.environ["SUPER_ADMIN_PASSWORD"]` and only falls
  back to a sentinel in dev.

### 9. `admin_control_router.get_alerts()` complexity 13 / 96 lines
- **Report says:** cyclomatic complexity too high.
- **Reality:** the function is a **linear, single-purpose read** — a series of
  independent alert-source counts appended to one list. There are no nested
  branches, no shared mutable state, no callable arguments. Extracting each
  alert-source into its own helper would add indirection (7+ mini-functions
  that call each other in a hard-coded sequence) with no testability win.
- **What we did fix:** if a real bug surfaces, the fix is in whichever
  alert-source branch fired, not in a broken abstraction.

### 10. `purge_test_data.py:107 purge()` — 106 lines
- **Report says:** too long / 28 locals.
- **Reality:** the function is one atomic DB transaction with cascade deletes.
  Breaking it into per-collection helpers means threading `db`, victim ids,
  and drop-flag flags through 12+ signatures for no runtime benefit — and it
  would fragment the safety invariant that all writes happen after the
  dry-run report is printed. Leaving as-is.

### 11. Empty `catch { /* noop */ }` blocks in `AuthContext.jsx`
- **Iter 38 fix (2026-02-06):** all four call sites now log via
  `console.debug("[Auth] ...", e?.message)`. The behaviour is still "swallow
  and continue" because `sessionStorage` is genuinely optional (Safari ITP,
  privacy mode) — but the linter no longer flags empty catch bodies.

### 12. `TrafficPanel.jsx:123` — array index as key
- **Iter 38 fix (2026-02-06):** switched to a stable composite key
  (`row.path || row.city || row.country || row.hour || row.day`) so
  reordering the country/city/page tables no longer forces DOM churn.

### 13. `random.choice()` in `assessment_router.py`
- **Report says:** insecure PRNG for security-sensitive operations.
- **Reality:** `random.choice()` here selects **quiz-question shuffle order**
  and **presentation-only** demo assertions. Zero cryptographic use. All
  actual security tokens (JWTs, refresh cookies, password-reset tokens) go
  through `secrets.token_urlsafe(...)` — grep `secrets\.` in the repo to
  confirm. `random` is the correct standard-library choice for pedagogical
  content ordering.

---

## July 2026 review cycle — additional verified items

### 7. `cert_render.py` MD5 "weak cryptography"
- **FIXED (cosmetically):** now `hashlib.md5(..., usedforsecurity=False)` + nosec.
- md5 here is a stable A/B bucketing hash for certificate design selection — not
  a security operation. It is deliberately NOT changed to sha256: doing so would
  flip the design of every previously issued certificate.

### 8. Test files "hardcoded secrets" (tests/test_iteration*.py)
- These are local test-account credentials (also documented in
  /app/memory/test_credentials.md) used against the preview database. Standard
  practice; not production secrets. DO NOT churn.

### 9. `tests/load/locustfile.py` weak random
- Load-test traffic randomization. Zero security relevance.

### 10. "14 undefined variables"
- Verified with pyflakes across backend + routers: exactly ONE real instance
  existed (`generate_course_content.py:253` corrupted duplicate `gger.info`
  block from a bad historical edit) — FIXED July 2026. No others exist.

### 11. Oversized-function refactors
- `referral_system.handle_first_enrollment` split into `_issue_first_course_bypass`
  + `_convert_referral` (July 2026, behavior preserved, retested).
- `purge_test_data.purge`, `get_alerts`, `create_org_with_admin`,
  `_issue_certificate_if_new`, `verify_certificate`, `_org_analytics_uncached`
  are deliberately left as-is: linear, well-commented, fully tested operational
  code where a split adds indirection without reducing risk. Revisit only if a
  bug actually lands in one of them.

### 12. `auth_router.register()` complexity (July 2026 report)
- **FIXED July 2026:** split into `_validate_registration`, `_apply_signup_perks`,
  `_dispatch_signup_side_effects` + a 25-line handler. All paths regression
  tested (duplicate email, policy rejection, invalid code, normal, founding
  code, personal referral).

### 13. Type-hint coverage on seed/test scripts
- `export_generated_content.py`, `seed_video_quizzes.py`, test files: one-shot
  operational scripts. Type annotations add no safety here; deliberately skipped.
  Core business modules (security_service, referral_system, email_service,
  ai_service) are typed.
