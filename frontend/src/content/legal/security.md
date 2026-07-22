# Cyber Security Statement

*DRAFT — reflects current-state controls. Attestation status is
tracked publicly on /trust.*

**Effective date:** {{ EFFECTIVE_DATE }}

## 1. Scope
This statement describes the technical and organisational security
controls in place for the Enterprise Agentic AI Academy platform,
covering learner and enterprise data on **ithr.online**.

## 2. Identity & Access
- **Authentication:** JWT-based access tokens (15-minute lifetime,
  kept in browser memory only — never `localStorage`), paired with a
  7-day `httpOnly + Secure + SameSite=Lax` refresh cookie scoped to
  `/api/auth`. Optional Google OAuth is delegated through an audited
  identity provider.
- **Password storage:** bcrypt with per-user salt.
- **Role model:** three tiers — `learner`, `enterprise admin`
  (org-scoped), `super admin` (platform-scoped). Every privileged
  endpoint enforces a role guard AND re-validates the caller's role
  against the database on each request.
- **Session revocation:** logout clears the refresh cookie server-side.

## 3. Transport & Data at Rest
- **TLS 1.2+** enforced on all API and CDN endpoints. HSTS with
  `max-age=31536000; includeSubDomains` is emitted on every response.
- **Data at rest:** MongoDB storage is provisioned with encryption
  enabled at the cloud provider layer.
- **Backups:** Nightly logical dumps retained for 14 rolling days.
- **Secrets:** never committed to source; loaded from environment
  variables at runtime. `.env` files are not checked in.

## 4. Application Security
- **CSP (Content Security Policy):** strict `default-src 'self'`,
  `frame-ancestors 'none'`, `object-src 'none'`.
- **XSS defence:** all lesson HTML and rich-text content is passed
  through DOMPurify before rendering.
- **Baseline headers:** `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: geolocation=(), microphone=(), camera=()`.
- **Cryptographic hashing** uses SHA-256 (or bcrypt for passwords).
  No use of MD5 or SHA-1 anywhere in the codebase.
- **Automated dependency scanning** runs on every commit; critical
  vulnerabilities block merge.

## 5. AI-Provider Data Handling
- Learner input to the AI Tutor and Mentor is passed to third-party
  LLM providers (OpenAI, Anthropic, Google) over TLS 1.2+ under
  their zero-training data-processing terms.
- The Academy does **not** send personally identifiable information
  in prompts unless the learner explicitly types it.
- Conversation logs are retained in ITHR's database for 90 days for
  quality-review purposes, then deleted.

## 6. Vulnerability Management
- **Responsible disclosure:** please email **{{ SECURITY_EMAIL }}**
  with a description and reproduction steps. We commit to
  acknowledging within 3 business days and to providing a remediation
  ETA within 10 business days.
- We do **not** currently operate a bug bounty programme.
- Do not attempt intrusive testing without prior written consent.

## 7. Incident Response
If a security incident materially affects learner or enterprise data,
we will notify affected users within **72 hours** of confirmation,
with:
- What happened, when, and how it was discovered.
- What data was affected.
- What actions we've taken and what actions you should take.
- A point of contact for further questions.

## 8. Attestations
- **SOC 2:** *Not yet attested.* Controls are designed to align with
  the SOC 2 Trust Services Criteria. Roadmap: Type II attestation
  targeted for **{{ SOC2_TARGET }}**.
- **ISO/IEC 27001:** *Not yet certified.* Roadmap: certification
  targeted for **{{ ISO_TARGET }}**.
- **GDPR / UAE PDPL:** technical safeguards implemented; DPA and
  sub-processor list available on request from **{{ PRIVACY_EMAIL }}**.

Current status is always published — with dates — on **/trust**.

## 9. Sub-Processors
The Academy uses a short list of production sub-processors (compute,
storage, CDN, email, payments, LLM inference). The current list is
maintained on **/trust** and refreshed on any change with a 30-day
notice window for enterprise customers.

## 10. Contact
- Security disclosures: **{{ SECURITY_EMAIL }}**
- Privacy / DSAR: **{{ PRIVACY_EMAIL }}**
- Enterprise DPA / audit questionnaire: **{{ ENTERPRISE_EMAIL }}**
