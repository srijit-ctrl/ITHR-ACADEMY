"""Trust & procurement — public endpoints for buyer due-diligence.

Endpoints:
  GET /api/trust/procurement-pack  → ZIP with 4 PDFs + a README the buyer can hand to their vendor-review team

Everything in the pack reflects the same realistic Live / In progress / Planned labelling
that appears on the public /trust page. Nothing is claimed that is not actually shipped.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from weasyprint import HTML

router = APIRouter(prefix="/api/trust", tags=["trust"])


# ---------- HTML fragments (styled minimally so WeasyPrint renders cleanly) ----------

_PDF_BASE_CSS = """
@page { size: A4; margin: 20mm 18mm; @bottom-right { content: counter(page) " / " counter(pages); color: #6b7280; font-size: 9pt; } }
* { font-family: "Helvetica Neue", Arial, sans-serif; }
h1 { font-size: 22pt; color: #1f2430; margin: 0 0 4pt 0; letter-spacing: -0.02em; }
h2 { font-size: 14pt; color: #1f2430; margin: 20pt 0 6pt; border-top: 1pt solid #d4dbe6; padding-top: 10pt; }
h3 { font-size: 11pt; color: #2e5aac; margin: 12pt 0 4pt; }
p, li, td, th { font-size: 10pt; line-height: 1.55; color: #2b303b; }
ul { margin: 4pt 0 8pt 14pt; padding: 0; }
li { margin-bottom: 3pt; }
.kicker { font-size: 8pt; letter-spacing: 0.25em; text-transform: uppercase; color: #b58a2b; font-weight: 600; margin-bottom: 4pt; }
.meta { font-size: 8pt; color: #6b7280; margin-top: 4pt; }
.pill { display: inline-block; padding: 1pt 6pt; border-radius: 8pt; font-size: 7.5pt; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.pill-live { background: #d1fadf; color: #14804a; }
.pill-progress { background: #fde9c4; color: #a05e07; }
.pill-planned { background: #eef1f5; color: #4b5563; }
.uae-line { font-size: 8pt; letter-spacing: 0.2em; text-transform: uppercase; color: #b58a2b; }
table { width: 100%; border-collapse: collapse; margin-top: 6pt; }
th, td { text-align: left; padding: 5pt 6pt; border-bottom: 0.5pt solid #d4dbe6; vertical-align: top; }
th { background: #f5f8fd; font-size: 8.5pt; letter-spacing: 0.1em; text-transform: uppercase; color: #4b5563; font-weight: 600; }
.footer { position: fixed; bottom: 8mm; left: 18mm; right: 18mm; font-size: 8pt; color: #6b7280; border-top: 0.5pt solid #d4dbe6; padding-top: 4pt; display: flex; justify-content: space-between; }
.cover { text-align: center; padding: 60pt 20pt 20pt; }
.cover .brand { font-size: 12pt; letter-spacing: 0.25em; text-transform: uppercase; color: #b58a2b; }
.cover h1 { font-size: 32pt; margin: 16pt 0 8pt; letter-spacing: -0.03em; }
.cover .sub { font-size: 12pt; color: #4b5563; max-width: 380pt; margin: 0 auto; }
.small { font-size: 9pt; color: #4b5563; }
"""


def _pill(status: str) -> str:
    labels = {"live": ("Live", "pill-live"), "progress": ("In progress", "pill-progress"), "planned": ("Planned", "pill-planned")}
    label, cls = labels.get(status, ("Planned", "pill-planned"))
    return f'<span class="pill {cls}">{label}</span>'


def _render_pdf(inner_html: str, page_footer_text: str) -> bytes:
    """Render a minimal-styled A4 PDF."""
    generated = datetime.now(timezone.utc).strftime("%B %d, %Y")
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><style>{_PDF_BASE_CSS}</style></head>
    <body>
      {inner_html}
      <div class="footer">
        <span>{page_footer_text}</span>
        <span>ITHR Technologies Consulting LLC · Generated {generated}</span>
      </div>
    </body>
    </html>
    """
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    return buf.getvalue()


def _security_factsheet_pdf() -> bytes:
    live_items = [
        ("HTTPS / TLS", "All traffic served over TLS 1.2+; HSTS in production."),
        ("Password hashing", "bcrypt with 12 rounds; plaintext never persisted."),
        ("Session tokens", "Short-lived signed JWTs verified on every request."),
        ("Role-based access control", "Owner / admin / member enforced server-side, not client-side only."),
        ("Public credential verification", "Every credential has a /verify/{id} endpoint + scannable QR."),
        ("Server-rendered PDF certificates", "PDFs generated on our servers; screenshots cannot be silently altered."),
        ("Abuse rate-limiting", "Anonymous try-a-lesson endpoint capped per IP."),
    ]
    progress_items = [
        ("UAE data residency", "MVP runs in shared cloud today; UAE me-central-1 migration is the next milestone."),
        ("SOC 2 Type I readiness", "Controls written up and evidence collection under way. Not yet attested."),
        ("UAE PDPL registration + DPO", "Preparing formal registration with the UAE Data Office."),
    ]
    planned_items = [
        ("MFA + SSO (Azure AD / Okta / Google Workspace)", "Enterprise SSO with MFA enforcement and SCIM auto-deprovisioning."),
        ("Envelope encryption at rest (KMS)", "For production DB, object storage, and backups after cutover."),
        ("ISO/IEC 27001 certification", "Referenced internally; no certificate held today."),
        ("Independent penetration test (CREST)", "Scheduled ahead of enterprise general availability."),
    ]

    def _rows(items):
        return "".join(f"<tr><td style='width:38%'><b>{name}</b></td><td>{detail}</td></tr>" for name, detail in items)

    inner = f"""
    <div class="cover">
      <div class="brand">ITHR Academy · Security Fact-Sheet</div>
      <h1>What protects your data today.</h1>
      <p class="sub">A one-page honest snapshot of the controls that are Live, In progress, and Planned. Nothing here is aspirational.</p>
      <p class="uae-line" style="margin-top:14pt">🇦🇪 Made in the UAE · for the world</p>
    </div>

    <h2>{_pill("live")} &nbsp; Live today</h2>
    <table><tbody>{_rows(live_items)}</tbody></table>

    <h2>{_pill("progress")} &nbsp; In progress</h2>
    <table><tbody>{_rows(progress_items)}</tbody></table>

    <h2>{_pill("planned")} &nbsp; Planned</h2>
    <table><tbody>{_rows(planned_items)}</tbody></table>

    <h2>What we do NOT claim</h2>
    <ul>
      <li>We are <b>not yet SOC 2 attested.</b> If any deck says otherwise, it is incorrect.</li>
      <li>We do <b>not yet hold ISO/IEC 27001</b> or ISO/IEC 17024 accreditation.</li>
      <li>Customer data does <b>not yet reside inside UAE borders in production.</b> The MVP runs in a shared cloud region.</li>
      <li>Payments today are configured against a <b>Stripe test key.</b> A live-key cutover precedes real revenue.</li>
    </ul>

    <h2>Contacts</h2>
    <p class="small">
      Security disclosures — <b>security@ithr.ae</b><br/>
      Data-subject requests — <b>privacy@ithr.ae</b><br/>
      Enterprise procurement / DPA — <b>enterprise@ithr.ae</b>
    </p>
    """
    return _render_pdf(inner, "Security Fact-Sheet · v1.0")


def _subprocessors_pdf() -> bytes:
    rows = [
        ("MongoDB", "Primary database (learners, courses, credentials)", "Cloud region — see notes", "Live"),
        ("Anthropic", "AI Tutor (Aletheia) + AI Mentor (Solon) + curriculum drafting", "Vendor default", "Live"),
        ("Stripe", "Payment processing (subscriptions, one-time, per-seat)", "Vendor default; test key today", "Live"),
        ("Google (Emergent-managed OAuth)", "Sign in with Google", "Google infrastructure", "Live"),
        ("Resend", "Transactional + weekly digest emails", "Vendor default", "Planned (key not yet provisioned)"),
        ("AWS (me-central-1)", "Production compute, storage, KMS, WAF", "UAE (Dubai / Etihad DC)", "Planned"),
    ]
    body = "".join(
        f"<tr><td><b>{n}</b></td><td>{p}</td><td>{r}</td><td class='small'>{s}</td></tr>"
        for n, p, r, s in rows
    )
    inner = f"""
    <div class="kicker">Sub-processors</div>
    <h1>Who we rely on to run the Academy.</h1>
    <p class="meta">This list is authoritative. If a sub-processor changes, the /trust page is updated the same day.</p>

    <table>
      <thead><tr><th>Sub-processor</th><th>Purpose</th><th>Region / notes</th><th>Status</th></tr></thead>
      <tbody>{body}</tbody>
    </table>

    <h2>Commitments</h2>
    <ul>
      <li>We do <b>not sell learner data.</b></li>
      <li>We do <b>not use enterprise customer data to train third-party AI models.</b></li>
      <li>Every sub-processor has (or will have, before onboarding real customers) a signed data-processing agreement.</li>
      <li>Customer notice will be given for any material change to this list.</li>
    </ul>

    <h2>Contact</h2>
    <p class="small">To request a machine-readable feed of this list, email <b>enterprise@ithr.ae</b>.</p>
    """
    return _render_pdf(inner, "Sub-processor Register · v1.0")


def _dpa_template_pdf() -> bytes:
    inner = """
    <div class="kicker">Data Processing Addendum (Template)</div>
    <h1>DPA between Customer and ITHR Technologies Consulting LLC.</h1>
    <p class="meta">This document is a working template. Executed DPAs are exchanged during procurement and superseded by signed originals on customer letterhead.</p>

    <h2>1. Parties</h2>
    <p>This Data Processing Addendum ("Addendum") supplements the Master Services Agreement between the Customer ("Controller") and <b>ITHR Technologies Consulting LLC</b>, a company registered in the United Arab Emirates ("Processor"), collectively the "Parties".</p>

    <h2>2. Scope and Roles</h2>
    <p>The Processor processes Personal Data on behalf of the Controller solely for the purpose of providing the ITHR Enterprise Agentic AI Academy service ("Service"). Nothing in this Addendum grants the Processor rights to Personal Data beyond what is strictly necessary to deliver the Service.</p>

    <h2>3. Categories of Personal Data</h2>
    <ul>
      <li>Identity data — name, email, professional title, organisation.</li>
      <li>Learning data — enrolment, progress, assessment results, issued credentials.</li>
      <li>Usage data — sign-in timestamps, IP address, device / browser meta.</li>
      <li>Communications — messages sent to AI Tutor / AI Mentor (retained for continuity; not used to train third-party models).</li>
    </ul>

    <h2>4. Sub-processors</h2>
    <p>A current list of sub-processors is published at <b>https://[production-domain]/trust</b> and included in this pack as <i>SUB_PROCESSORS.pdf</i>. Reasonable advance notice will be given for material changes.</p>

    <h2>5. Security Measures</h2>
    <p>The Processor implements the technical and organisational measures described in the accompanying <i>SECURITY_FACTSHEET.pdf</i>. Additional measures apply once the Processor completes UAE data-residency migration and SOC 2 attestation.</p>

    <h2>6. International Transfers</h2>
    <p>Personal Data is currently processed in the Processor's operating cloud region. The Processor is executing a migration to <b>AWS me-central-1 (UAE)</b> to keep data of UAE data subjects within UAE borders. Where transfers outside the UAE occur, the Parties rely on Standard Contractual Clauses or an equivalent lawful mechanism.</p>

    <h2>7. Data-subject Rights</h2>
    <p>The Processor shall assist the Controller in responding to data-subject requests (access, rectification, erasure, portability, restriction, objection) within thirty (30) calendar days of receipt.</p>

    <h2>8. Breach Notification</h2>
    <p>The Processor shall notify the Controller of a confirmed Personal Data breach without undue delay and no later than seventy-two (72) hours after becoming aware of it, providing all information reasonably required for the Controller to comply with its own notification obligations under applicable law (including the UAE PDPL and, where applicable, the GDPR).</p>

    <h2>9. Audit</h2>
    <p>The Controller may, no more than once per year and on reasonable prior notice, request an audit of the Processor's compliance with this Addendum. In lieu of an on-site audit, the Processor may satisfy this obligation by providing then-current third-party attestations (e.g., SOC 2 Type II) once available.</p>

    <h2>10. Return / Deletion</h2>
    <p>Upon termination of the Service, the Processor shall return or delete Personal Data within ninety (90) days, save where retention is required by applicable law.</p>

    <h2>11. Term and Order of Precedence</h2>
    <p>This Addendum takes effect on the date the Master Services Agreement takes effect and remains in force for as long as the Processor processes Personal Data on behalf of the Controller. In the event of conflict between this Addendum and the Master Services Agreement, this Addendum controls with respect to Personal Data protection matters.</p>

    <h2>12. Governing Law</h2>
    <p>This Addendum shall be governed by the laws of the United Arab Emirates unless the Parties expressly agree otherwise in the executed Master Services Agreement.</p>

    <h2>Signatures</h2>
    <table>
      <tbody>
        <tr><td style="width:50%; padding-top:24pt"><b>For the Controller</b><br/><br/>Name: ______________________<br/>Title: ______________________<br/>Date: ______________________</td>
        <td style="width:50%; padding-top:24pt"><b>For ITHR Technologies Consulting LLC</b><br/><br/>Name: ______________________<br/>Title: ______________________<br/>Date: ______________________</td></tr>
      </tbody>
    </table>
    """
    return _render_pdf(inner, "DPA Template · v1.0 (working draft)")


def _compliance_dossier_pdf() -> bytes:
    inner = """
    <div class="cover">
      <div class="brand">ITHR Academy · Compliance Dossier</div>
      <h1>Trust · Security · Compliance</h1>
      <p class="sub">A candid dossier of what is Live, In progress, and Planned. Written to help your vendor-review team say yes with eyes open.</p>
      <p class="uae-line" style="margin-top:14pt">🇦🇪 Made in the UAE · for the world</p>
    </div>

    <h2>1. Issuer identity</h2>
    <p>The Academy is operated end-to-end by <b>ITHR Technologies Consulting LLC</b>, a UAE-registered consulting firm. Every credential is issued in ITHR's own name; we do not resell certification under another party's mark.</p>

    <h2>2. Live security controls</h2>
    <ul>
      <li>HTTPS / TLS in transit; HSTS on production.</li>
      <li>bcrypt password hashing (12 rounds); plaintext never persisted.</li>
      <li>Short-lived signed JWTs, verified on every /api/* request.</li>
      <li>Role-based access control enforced server-side on all enterprise endpoints.</li>
      <li>Public credential verification at /verify/{id} + scannable QR.</li>
      <li>Server-rendered PDF certificates (WeasyPrint) with embedded QR.</li>
      <li>Rate-limiting on the anonymous try-a-lesson endpoint.</li>
    </ul>

    <h2>3. In progress</h2>
    <ul>
      <li>UAE data residency (AWS me-central-1) — migration is the next infrastructure milestone.</li>
      <li>SOC 2 Type I readiness — controls documented, evidence collection ongoing. Not yet attested.</li>
      <li>UAE PDPL registration + designated DPO — preparing filing with the UAE Data Office.</li>
    </ul>

    <h2>4. Planned</h2>
    <ul>
      <li>MFA + SSO (Azure AD / Okta / Google Workspace) with SCIM provisioning.</li>
      <li>Envelope encryption at rest (KMS) for production DB, storage, backups.</li>
      <li>ISO/IEC 27001 initial certification.</li>
      <li>ISO/IEC 17024 personnel-certification-body accreditation.</li>
      <li>Independent CREST penetration test.</li>
      <li>Cryptographic signatures + W3C Verifiable Credentials.</li>
    </ul>

    <h2>5. Certificate authenticity model</h2>
    <p>Every issued credential has (a) an opaque server-issued ID, (b) a public /verify/{id} endpoint, (c) an embedded QR that resolves to that endpoint, and (d) a server-rendered PDF. Screenshots and altered PDFs cannot pass verification.</p>
    <p>Issuer legitimacy rests on a real legal entity, a documented pass rubric, a public registry, and — as they arrive — external accreditations (ISO/IEC 17024).</p>

    <h2>6. Courseware authenticity</h2>
    <p>Courses are authored and reviewed internally today, with an Academic Advisory Board planned as an external quality gate. AI-drafted curriculum patches enter a human-review queue and are never published to learners without approval.</p>

    <h2>7. Data-subject rights</h2>
    <p>Access, correction, portability, and deletion requests are handled within 30 calendar days. Contact <b>privacy@ithr.ae</b>.</p>

    <h2>8. Incident response</h2>
    <p>Confirmed personal-data breaches are notified within 72 hours to the customer and, where applicable, to the UAE Data Office and other supervisory authorities.</p>

    <h2>9. Sub-processors</h2>
    <p>See the accompanying <i>SUB_PROCESSORS.pdf</i>. The public list at /trust is authoritative and is updated the same day of any change.</p>

    <h2>10. What we do not claim</h2>
    <ul>
      <li>Not yet SOC 2 attested. Not yet ISO/IEC 27001 certified. Not yet ISO/IEC 17024 accredited.</li>
      <li>Production data is not yet inside UAE borders.</li>
      <li>Payments are configured against a Stripe test key today.</li>
    </ul>

    <h2>Contacts</h2>
    <p class="small">
      Security — <b>security@ithr.ae</b><br/>
      Privacy / DSAR — <b>privacy@ithr.ae</b><br/>
      Enterprise procurement — <b>enterprise@ithr.ae</b>
    </p>
    """
    return _render_pdf(inner, "Compliance Dossier · v1.0")


def _readme_text() -> str:
    generated = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return f"""ITHR Academy — Enterprise Procurement Pack
Generated on {generated}

Contents
--------
1. SECURITY_FACTSHEET.pdf   — one-page snapshot of Live / In progress / Planned controls
2. SUB_PROCESSORS.pdf       — authoritative list of third parties we rely on
3. DPA_TEMPLATE.pdf         — Data Processing Addendum working template
4. COMPLIANCE_DOSSIER.pdf   — full trust dossier (issuer identity, controls, roadmap)

How to use
----------
- Hand this pack to your vendor-review or procurement team.
- Any executed contract supersedes the DPA template on your letterhead.
- The public source of truth is https://[production-domain]/trust — always the freshest version.

Contacts
--------
Security disclosures ................ security@ithr.ae
Data-subject requests ............... privacy@ithr.ae
Enterprise procurement / DPA ........ enterprise@ithr.ae

Made in the UAE — for the world.
ITHR Technologies Consulting LLC
"""


@router.get("/procurement-pack")
async def procurement_pack():
    """Return a ZIP with the 4 procurement PDFs + a README.

    Public endpoint — buyers should be able to grab this without an account.
    """
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _readme_text())
        zf.writestr("SECURITY_FACTSHEET.pdf", _security_factsheet_pdf())
        zf.writestr("SUB_PROCESSORS.pdf", _subprocessors_pdf())
        zf.writestr("DPA_TEMPLATE.pdf", _dpa_template_pdf())
        zf.writestr("COMPLIANCE_DOSSIER.pdf", _compliance_dossier_pdf())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="ITHR-Academy-Procurement-Pack-{stamp}.zip"'},
    )
