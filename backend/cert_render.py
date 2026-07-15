"""Certificate rendering onto the official ITHR Academy gold artwork template.

The uploaded artwork (shield crest, laurels, gold frame, seal-of-excellence
ribbon) is embedded as a full-bleed background; dynamic fields (recipient,
program, date, certificate ID, verification QR) are overlaid as crisp
vector text so the PDF stays print-sharp.
"""
import base64
import io
import os

import segno

_ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")


def _b64_file(*parts: str) -> str:
    with open(os.path.join(_ASSET_DIR, *parts), "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


_TEMPLATE = open(os.path.join(_ASSET_DIR, "cert_templates", "gold.html"), encoding="utf-8").read()
_BG_B64 = _b64_file("cert_templates", "gold_bg.jpg")
_FONT_GV_B64 = _b64_file("fonts", "GreatVibes-Regular.ttf")


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _qr_b64(verify_url: str) -> str:
    buf = io.BytesIO()
    segno.make(verify_url, error="H").save(
        buf, kind="svg", scale=6, dark="#1F2C47", light=None, border=0, xmldecl=False
    )
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _name_font_size(name: str) -> str:
    n = len(name)
    if n <= 22:
        return "34pt"
    if n <= 30:
        return "28pt"
    if n <= 40:
        return "23pt"
    return "19pt"


def _course_font_size(title: str) -> str:
    n = len(title)
    if n <= 48:
        return "16.5pt"
    if n <= 62:
        return "14pt"
    if n <= 80:
        return "12pt"
    return "10.5pt"


def render_certificate_html(cert: dict, verify_url: str, issued_display: str) -> str:
    name = (cert.get("user_name") or "").strip()
    course = (cert.get("course_title") or "").strip()
    display_url = verify_url.replace("https://", "").replace("http://", "")
    html = _TEMPLATE
    for token, value in (
        ("__BG__", _BG_B64),
        ("__FONT_GV__", _FONT_GV_B64),
        ("__NAME_FS__", _name_font_size(name)),
        ("__COURSE_FS__", _course_font_size(course)),
        ("__NAME__", _escape(name)),
        ("__COURSE__", _escape(course)),
        ("__DATE__", _escape(issued_display)),
        ("__CERT_ID__", _escape(cert["certificate_id"])),
        ("__QR__", _qr_b64(verify_url)),
        ("__VERIFY_URL__", _escape(display_url)),
    ):
        html = html.replace(token, value)
    return html


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
