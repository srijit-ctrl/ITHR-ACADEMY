"""Public credential-share endpoints.

Two surfaces:
  1. GET /api/certificates/{certificate_id}/share-image.png
     Server-rendered 1200x630 branded card (LinkedIn / Twitter / OG spec)
     used both as the download-a-shareable-image asset and as the OG image
     that scrapers pick up when a learner shares the certificate.

  2. GET /api/share/certificate/{certificate_id}
     Public HTML landing with proper Open Graph + Twitter Card meta tags
     pointing at (1), then meta-refreshes the human visitor to the real
     /verify/{id} page on the SPA. This is what learners paste into
     LinkedIn feed / Twitter / WhatsApp so previews render richly.
"""
from __future__ import annotations

import io
import os
import textwrap
from html import escape as _escape

from fastapi import APIRouter, HTTPException, Response
from PIL import Image, ImageDraw, ImageFont

from core import db

router = APIRouter(prefix="/api", tags=["share"])

_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_FRONTEND_BRAND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "public", "brand")
_FONT_PATH = os.path.join(_ASSET_DIR, "fonts", "GreatVibes-Regular.ttf")

# Cache PIL image assets between requests.
_share_bg = None
_share_shield = None


def _load_shield() -> Image.Image | None:
    global _share_shield
    if _share_shield is not None:
        return _share_shield or None
    path = os.path.join(_FRONTEND_BRAND_DIR, "ITHR_Academy_Shield.png")
    try:
        _share_shield = Image.open(path).convert("RGBA")
    except Exception:
        _share_shield = False
        return None
    return _share_shield


def _font(size: int, *, script: bool = False):
    """Return a PIL font at the requested size. Falls back to the default
    bundled PIL bitmap font if the on-disk TTF is missing so the endpoint
    never 500s on a fresh checkout."""
    if script and os.path.exists(_FONT_PATH):
        try:
            return ImageFont.truetype(_FONT_PATH, size)
        except Exception:
            pass
    # Try common system fonts for the sans-serif copy (DejaVu ships with
    # Debian/Ubuntu images, which is what our container runs).
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    l, _, r, _ = draw.textbbox((0, 0), text, font=font)
    return r - l


def _wrap_to_width(draw, text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for w in words:
        trial = " ".join(current + [w])
        if _text_width(draw, trial, font) <= max_width:
            current.append(w)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
            if len(lines) == max_lines - 1:
                # Squeeze the remainder into the last line and truncate with an ellipsis.
                remainder = " ".join([w] + words[words.index(w) + 1:])
                while _text_width(draw, remainder + "…", font) > max_width and len(remainder) > 4:
                    remainder = remainder[:-1]
                lines.append(remainder + "…")
                return lines
    if current:
        lines.append(" ".join(current))
    return lines


def _render_share_image(cert: dict) -> bytes:
    """Compose the 1200x630 branded share card. Sized to LinkedIn / Twitter
    recommended OG image dimensions."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (16, 31, 58))  # ITHR navy
    draw = ImageDraw.Draw(img)

    # Diagonal gold accent bar (top and bottom)
    draw.polygon([(0, 0), (W, 0), (W, 10), (0, 40)], fill=(198, 161, 90))
    draw.polygon([(0, H - 40), (W, H - 10), (W, H), (0, H)], fill=(198, 161, 90))

    # Soft radial glow behind the shield (approximated with a translucent
    # ellipse overlay).
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.ellipse((-80, -160, 520, 440), fill=(198, 161, 90, 22))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Brand shield (top-left).
    shield = _load_shield()
    if shield:
        target = 130
        s = shield.copy()
        s.thumbnail((target, target))
        img.paste(s, (60, 55), s)

    # Brand wordmark next to the shield.
    brand_font = _font(22)
    kicker_font = _font(18)
    draw.text((210, 68), "ITHR ACADEMY", font=brand_font, fill=(228, 206, 154))
    draw.text((210, 100), "Enterprise Agentic AI Academy", font=kicker_font, fill=(200, 210, 230))

    # "Certified" kicker.
    small_font = _font(16)
    draw.text((60, 220), "CERTIFIED CREDENTIAL", font=small_font, fill=(198, 161, 90))
    draw.line([(60, 250), (280, 250)], fill=(198, 161, 90), width=2)

    # Recipient name (large).
    name = (cert.get("user_name") or "Recipient").strip()
    name_font_size = 62 if len(name) <= 24 else 52 if len(name) <= 34 else 42
    name_font = _font(name_font_size)
    draw.text((60, 270), name, font=name_font, fill=(255, 255, 255))

    # "has earned"
    draw.text((60, 270 + name_font_size + 18), "has earned the credential", font=small_font, fill=(180, 195, 220))

    # Course title (wrapped, up to 2 lines).
    course = (cert.get("course_title") or "").strip()
    course_font = _font(30)
    lines = _wrap_to_width(draw, course, course_font, W - 120, max_lines=2)
    y = 270 + name_font_size + 50
    for line in lines:
        draw.text((60, y), line, font=course_font, fill=(228, 206, 154))
        y += 40

    # Bottom footer: credential id + date.
    footer_font = _font(15)
    cid = cert.get("certificate_id") or "—"
    draw.text((60, H - 78), f"Credential ID · {cid}", font=footer_font, fill=(200, 210, 230))
    issued = (cert.get("issued_at") or "")[:10]
    draw.text((60, H - 55), f"Issued {issued} · verify at learn.ithr.online/verify/{cid}",
              font=footer_font, fill=(160, 180, 210))

    # Right-side verified seal.
    seal_x, seal_y, seal_r = W - 130, H - 130, 60
    draw.ellipse(
        (seal_x - seal_r, seal_y - seal_r, seal_x + seal_r, seal_y + seal_r),
        outline=(198, 161, 90), width=3,
    )
    seal_font = _font(13)
    draw.text((seal_x - 32, seal_y - 18), "VERIFIED", font=seal_font, fill=(228, 206, 154))
    draw.text((seal_x - 24, seal_y + 2), "CREDENTIAL", font=_font(11), fill=(200, 210, 230))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.get("/certificates/{certificate_id}/share-image.png")
async def certificate_share_image(certificate_id: str):
    """LinkedIn/Twitter/OG-ready 1200x630 branded PNG of the credential.

    Public (no auth) — learners paste share links straight into LinkedIn,
    which fetches this URL as the OG image.
    """
    cert = await db.certificates.find_one(
        {"certificate_id": certificate_id}, {"_id": 0},
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.get("revoked"):
        raise HTTPException(status_code=410, detail="Credential revoked")

    png = _render_share_image(cert)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600, s-maxage=3600",
            "Content-Disposition": f'inline; filename="ITHR-{certificate_id}-share.png"',
        },
    )


@router.get("/share/certificate/{certificate_id}")
async def certificate_share_landing(certificate_id: str):
    """Public share landing with rich OG / Twitter meta tags.

    Purpose: when a learner pastes this URL into LinkedIn / Twitter /
    WhatsApp, the preview card renders the branded share image + course
    title. Human visitors are auto-forwarded to the SPA's /verify page.
    """
    cert = await db.certificates.find_one(
        {"certificate_id": certificate_id}, {"_id": 0},
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    base = (os.environ.get("PUBLIC_APP_URL") or "").rstrip("/")
    verify_url = f"{base}/verify/{certificate_id}" if base else f"/verify/{certificate_id}"
    image_url = f"{base}/api/certificates/{certificate_id}/share-image.png" if base else f"/api/certificates/{certificate_id}/share-image.png"

    name = _escape((cert.get("user_name") or "").strip())
    course = _escape((cert.get("course_title") or "").strip())
    title = f"{name} · {course} · ITHR Academy Credential"
    desc = f"{name} has earned the {course} credential from the ITHR Enterprise Agentic AI Academy. Verify authenticity at {verify_url}."
    desc_esc = _escape(desc)

    html = textwrap.dedent(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>{_escape(title)}</title>
      <meta name="description" content="{desc_esc}" />

      <!-- Open Graph -->
      <meta property="og:type" content="article" />
      <meta property="og:site_name" content="ITHR Academy" />
      <meta property="og:title" content="{_escape(title)}" />
      <meta property="og:description" content="{desc_esc}" />
      <meta property="og:url" content="{_escape(verify_url)}" />
      <meta property="og:image" content="{_escape(image_url)}" />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />

      <!-- Twitter -->
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content="{_escape(title)}" />
      <meta name="twitter:description" content="{desc_esc}" />
      <meta name="twitter:image" content="{_escape(image_url)}" />

      <!-- Bounce human visitors to the SPA verify page. Scrapers still get the meta above. -->
      <meta http-equiv="refresh" content="0; url={_escape(verify_url)}" />
      <link rel="canonical" href="{_escape(verify_url)}" />
      <style>
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               background: #101F3A; color: #ffffff; display: flex; align-items: center;
               justify-content: center; min-height: 100vh; padding: 24px; text-align: center; }}
        a {{ color: #E4CE9A; }}
      </style>
    </head>
    <body>
      <div>
        <p>Redirecting to the credential verification page…</p>
        <p><a href="{_escape(verify_url)}">Continue to verify</a></p>
      </div>
    </body>
    </html>
    """).strip()

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )
