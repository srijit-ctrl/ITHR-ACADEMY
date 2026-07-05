# Compliance Statement

*DRAFT — describes design-alignment posture, not attested controls.
Attestation status is tracked publicly on /trust. Placeholders in **{{ }}**.*

**Effective date:** {{ EFFECTIVE_DATE }}
**Governing entity:** ITHR Technologies FZ-LLC (Dubai, UAE)

## 1. Framework Alignment
The Academy is **designed to align** with the following external
control frameworks. Design alignment is not the same as certification;
where we hold no external attestation, we say so explicitly.

| Framework | Current status | Roadmap target |
|-----------|---------------|----------------|
| **GDPR** (EU 2016/679) | Technical safeguards implemented (encryption, access control, deletion workflows). DPA available on request. | Formal DPO appointed on enterprise sale volume threshold |
| **UAE PDPL** (Federal Decree-Law 45/2021) | Data-processing register maintained. Consent flows in place. | Onshore data residency option for UAE enterprises |
| **SOC 2 Type II** | Controls designed to align with Trust Services Criteria (Security, Availability, Confidentiality) | Type II attestation targeted for **{{ SOC2_TARGET }}** |
| **ISO/IEC 27001:2022** | ISMS scoping in progress | Certification targeted for **{{ ISO_TARGET }}** |
| **ISO/IEC 42001:2023** (AI Management System) | Design references incorporated into internal AI-quality process | Alignment review targeted for **{{ ISO_42001_TARGET }}** |
| **NIST AI RMF 1.0** | Applied to curriculum authoring and AI-tutor operating envelope | Continuous — public change-log on /trust |
| **EU AI Act** (Regulation 2024/1689) | Provider-side obligations tracked; risk-tier classification maintained per feature | Continuous — public change-log on /trust |
| **FERPA** (US 20 U.S.C. § 1232g) | Learner-record handling aligned with FERPA-style disclosure limits | Consideration on US education-sector sale |
| **PCI-DSS** | Card data never touches ITHR infrastructure — all payments handled by Stripe | Reliance on Stripe's PCI-DSS Level 1 attestation |

## 2. Learner Data Rights
Every individual learner has the following rights under UAE PDPL,
GDPR, and equivalent frameworks:

- **Access** — request a copy of the personal data we hold about you.
- **Correction** — update your profile at any time via the dashboard,
  or request correction via **{{ PRIVACY_EMAIL }}**.
- **Deletion** — request account deletion. We will remove your account
  and enrolments; certificates remain publicly verifiable unless you
  also request certificate revocation.
- **Portability** — request an export of your enrolments, quiz
  attempts, and certificates in machine-readable JSON.
- **Objection** — object to any specific processing purpose (e.g.
  marketing) with immediate effect.
- **Withdraw consent** — where processing relies on consent.

**Response SLA:** 30 days from receipt (extendable to 60 days for
complex requests, with notice).

## 3. Data Retention
| Data class | Default retention |
|-----------|-------------------|
| Account profile | While account is active + 12 months after deletion request |
| Enrolments & quiz attempts | 24 months (needed to defend certificate integrity claims) |
| AI Tutor / Mentor conversation logs | 90 days |
| Certificates | Indefinite (public verification requirement) |
| Payment records | 7 years (UAE tax law) |
| Application logs | 30 days |
| Backup snapshots | 14 days |

## 4. Sub-Processors
Production sub-processors are published on **/trust** and cover:
compute + storage (cloud infra), CDN, transactional email, payments,
LLM inference. Any change or addition is announced with **30 days
advance notice** for enterprise customers.

## 5. Cross-Border Transfers
Where a sub-processor operates outside the UAE / EEA, transfers rely
on Standard Contractual Clauses (GDPR Chapter V) or equivalent PDPL
adequacy mechanisms.

## 6. AI-Specific Compliance
- The Academy's AI features (Tutor, Mentor, Recommendation Engine,
  Curriculum Patch Drafts) operate as **content-suggestion systems**
  with a human-in-the-loop review model for any patch that reaches
  production. This is consistent with the EU AI Act's "limited-risk"
  posture for supportive AI systems.
- Automated decision-making that produces a *legal or similarly
  significant effect* on the learner is **not** used. Certificates are
  awarded based on deterministic scoring, not AI evaluation.
- Model outputs are watermarked at the platform layer with the
  string "*AI-generated response*" in every response envelope.

## 7. Enterprise Compliance Bundle
For B2B evaluations, we provide a one-click **procurement pack**
(`/api/trust/procurement-pack`) containing:
- Data Processing Addendum (draft, unsigned)
- Sub-processor list
- Compliance framework mapping
- Cyber-security summary (this doc)
- Latest pen-test attestation letter (when available)
- Insurance certificate

## 8. Contact
- Privacy / DSAR: **{{ PRIVACY_EMAIL }}**
- Enterprise compliance questionnaire: **{{ ENTERPRISE_EMAIL }}**
- Legal: **{{ LEGAL_EMAIL }}**
