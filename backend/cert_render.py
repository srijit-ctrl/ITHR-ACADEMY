"""Certificate rendering using the uploaded ITHR artwork templates.

Two designs (design_a = "ab sign", design_b = plain) alternate deterministically
per certificate id. Dynamic fields are overlaid onto the artwork placeholders,
plus an injected QR code + Code128 barcode verification strip.
"""
import base64
import hashlib
import io
import os
import re

import segno

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "assets", "cert_templates")

_PLACEHOLDER_NAME = "Recipient Full Name"
_PLACEHOLDER_COURSE = "Advanced Certificate in Artificial Intelligence &amp; Machine Learning"
_PLACEHOLDER_DATE = "07 July 2026"
_PLACEHOLDER_ID = "ITHR-AI-2026-000123"

_VERIFY_CSS = """
  /* ---- WeasyPrint print-layout overrides (single-page fit) ---- */
  .content{ display:block; height:100%; padding:12mm 30mm 0; }
  /* Official ITHR Academy shield logo, prominent at the top centre. */
  .crest{ width:30mm; height:auto; margin-bottom:2.5mm; }
  .rule-orn{ margin:4.5mm auto 4mm; }
  .recipient{ min-width:0; }
  .course-title{ margin-left:auto; margin-right:auto; }
  .description{ margin-left:auto; margin-right:auto; }
  .spacer{ display:none; }
  .meta-row{ position:absolute; left:30mm; right:30mm; width:auto; bottom:50mm; margin:0; }
  /* Signatures removed — the credential is system-issued and QR-verifiable. */
  .sig-col{ display:none !important; }
  .bottom-block{
    position:absolute; left:28mm; right:28mm; bottom:27mm;
    width:auto; margin:0;
    display:flex; align-items:flex-end; justify-content:center;
  }
  .seal{ width:22mm; height:22mm; }
  .verify-strip{
    position:absolute; z-index:6;
    bottom:14mm; left:0; right:0;
    display:flex; align-items:center; justify-content:center; gap:6mm;
  }
  .verify-cell{ text-align:center; }
  .qr-img{ width:11mm; height:11mm; display:block; margin:0 auto; }
  .verify-label{
    font-family:'Jost', sans-serif; font-size:5pt; letter-spacing:1.2px;
    color:#2C4A6B; text-transform:uppercase; margin-top:0.8mm;
  }
  .verify-disclaimer{
    max-width:118mm; text-align:left;
    font-family:'Jost', sans-serif; font-size:5.4pt; line-height:1.5;
    color:#5B6B7E; letter-spacing:0.3px;
  }
  .verify-disclaimer b{ color:#2C4A6B; }
"""

_VERIFY_HTML = """
  <div class="verify-strip">
    <div class="verify-cell">
      <img class="qr-img" src="data:image/svg+xml;base64,{qr_b64}" alt="Verification QR">
      <div class="verify-label">Scan to verify</div>
    </div>
    <div class="verify-disclaimer">
      <b>This is a system-generated document and does not require a manual signature.</b><br>
      The authenticity of this certificate can be validated at any time by scanning the QR code
      or visiting {verify_url} &middot; Certificate ID: {cert_id}.
    </div>
  </div>
"""


def _load_templates() -> dict:
    templates = {}
    for key, fname in (("a", "design_a.html"), ("b", "design_b.html")):
        path = os.path.join(_TEMPLATE_DIR, fname)
        with open(path, encoding="utf-8") as f:
            templates[key] = f.read()
    return templates


_TEMPLATES = _load_templates()


def _official_logo_b64() -> str:
    path = os.path.join(os.path.dirname(__file__), "assets", "brand", "ITHR_Academy_Shield.png")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


_LOGO_B64 = _official_logo_b64()
_CREST_RE = re.compile(r'(<img class="crest" src=")data:image/png;base64,[^"]*(")')


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _qr_b64(verify_url: str) -> str:
    buf = io.BytesIO()
    segno.make(verify_url, error="H").save(
        buf, kind="svg", scale=6, dark="#152A47", light="#FBF8F1", border=1, xmldecl=False
    )
    return base64.b64encode(buf.getvalue()).decode("ascii")


def pick_design(certificate_id: str) -> str:
    """Alternate between the two uploaded designs, deterministic per cert id."""
    digest = hashlib.md5(certificate_id.encode()).hexdigest()
    return "a" if int(digest, 16) % 2 == 0 else "b"


def render_certificate_html(cert: dict, verify_url: str, issued_display: str) -> str:
    html = _TEMPLATES[pick_design(cert["certificate_id"])]
    # Swap the template crest for the official ITHR Academy shield logo (top centre).
    html = _CREST_RE.sub(rf'\g<1>data:image/png;base64,{_LOGO_B64}\g<2>', html, count=1)
    html = html.replace(_PLACEHOLDER_NAME, _escape(cert["user_name"]))
    html = html.replace(_PLACEHOLDER_COURSE, _escape(cert["course_title"]))
    html = html.replace(_PLACEHOLDER_DATE, _escape(issued_display))
    html = html.replace(_PLACEHOLDER_ID, _escape(cert["certificate_id"]))
    html = html.replace("</style>", _VERIFY_CSS + "\n</style>", 1)
    verify_block = _VERIFY_HTML.format(
        qr_b64=_qr_b64(verify_url),
        cert_id=_escape(cert["certificate_id"]),
        verify_url=_escape(verify_url.replace("https://", "").replace("http://", "")),
    )
    return html.replace("</body>", verify_block + "\n</body>", 1)


async def verify_certificate_integrity(db, cert: dict) -> list[str]:
    """Cross-check the credential against live user + course records before
    rendering. Returns a list of failed checks (empty = verified)."""
    failures = []
    for field in ("certificate_id", "user_name", "course_title", "user_id", "course_id", "issued_at"):
        if not cert.get(field):
            failures.append(f"missing field: {field}")
    if failures:
        return failures

    user = await db.users.find_one({"id": cert["user_id"]}, {"_id": 0, "full_name": 1})
    if not user:
        failures.append("recipient account no longer exists")
    elif (user.get("full_name") or "").strip().lower() != cert["user_name"].strip().lower():
        failures.append("recipient name does not match the account on record")

    course = await db.courses.find_one({"id": cert["course_id"]}, {"_id": 0, "title": 1})
    if not course:
        failures.append("course no longer exists")
    elif (course.get("title") or "").strip().lower() != cert["course_title"].strip().lower():
        failures.append("course title does not match the catalog record")

    return failures
