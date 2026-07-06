"""Transactional-email service — a thin, shared Resend wrapper reused
across auth signup, certificate issuance, and enterprise invites.

All templates share a common wrapper (ITHR header + navy CTA button + footer)
so branding stays consistent across the app's lifecycle emails. Every send
happens in a background thread (asyncio.to_thread) and NEVER raises — a
failed email must not block a successful signup or cert issuance.
"""
from __future__ import annotations

import asyncio
import os
import re

import resend

from core import logger

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "no-reply@ithr.tech")
FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def _safe(s: str) -> str:
    return re.sub(r"[<>]", "", s or "")


def _wrap(kicker: str, heading: str, body_html: str, cta_label: str, cta_url: str, footer_note: str = "") -> str:
    """Common ITHR-branded email shell — Teal button + Navy header."""
    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#F6F8FB;font-family:Calibre,Manrope,Tahoma,Arial,sans-serif;color:#16335E;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F8FB;padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:6px;box-shadow:0 8px 32px -12px rgba(22,51,94,0.15);overflow:hidden;">
        <tr>
          <td style="background:#16335E;padding:28px 32px;color:#ffffff;">
            <div style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#00A78B;font-family:monospace;">{kicker}</div>
            <div style="font-size:24px;font-weight:600;margin-top:6px;">{heading}</div>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            {body_html}
            <table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0;">
              <tr>
                <td style="border-radius:999px;background:#00A78B;">
                  <a href="{cta_url}" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;">{cta_label}</a>
                </td>
              </tr>
            </table>
            <p style="font-size:13px;line-height:1.6;color:#6b7280;margin:8px 0 0 0;">Or paste this link in your browser:<br><a href="{cta_url}" style="color:#00A78B;word-break:break-all;">{cta_url}</a></p>
            {f'<p style="font-size:13px;color:#6b7280;margin:16px 0 0 0;line-height:1.6;">{footer_note}</p>' if footer_note else ''}
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px;background:#F6F8FB;border-top:1px solid #E5E7EB;font-size:12px;color:#6b7280;">
            ITHR Technologies Consulting LLC · Made in the UAE
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


async def _fire(to_email: str, subject: str, html: str, text_fallback: str, tag: str) -> bool:
    """Actually send. Always safe — logs on failure, returns False."""
    if not RESEND_API_KEY:
        logger.warning(f"[email/{tag}] RESEND_API_KEY not set — email skipped for {to_email}")
        return False
    params = {
        "from": f"ITHR Academy <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text_fallback,
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        rid = result.get("id") if isinstance(result, dict) else result
        logger.info(f"[email/{tag}] Sent to {to_email} (resend id: {rid})")
        return True
    except Exception:
        logger.exception(f"[email/{tag}] Resend send failed for {to_email}")
        return False


# ---- Welcome on signup ----------------------------------------------------


async def send_welcome_email(email: str, full_name: str) -> bool:
    dash_url = f"{FRONTEND_URL}/dashboard"
    catalog_url = f"{FRONTEND_URL}/courses"
    name = _safe(full_name or "there")
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Welcome, {name} —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  You now have access to <b style="color:#16335E;">Enterprise Agentic AI Academy</b> — the training platform built to move your career and your team from AI-curious to AI-productive.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0;">
  Here's a fast way in: enroll in <a href="{catalog_url}" style="color:#00A78B;">Agentic AI Foundations</a> (our most-taken course) and Aletheia, your AI tutor, will walk you through each lesson.
</p>
"""
    html = _wrap(
        kicker="ITHR Academy · You're in",
        heading=f"Welcome to the Academy, {name}.",
        body_html=body,
        cta_label="Open my dashboard",
        cta_url=dash_url,
        footer_note="Reply to this email or reach out via the contact page — a human on the ITHR team reads every response.",
    )
    text = (
        f"Welcome, {name}!\n\n"
        f"You now have access to Enterprise Agentic AI Academy.\n"
        f"Open your dashboard: {dash_url}\n"
        f"Browse the catalog: {catalog_url}\n\n"
        "— ITHR Academy"
    )
    return await _fire(email, "Welcome to ITHR Academy", html, text, tag="welcome")


# ---- Certificate earned ---------------------------------------------------


async def send_certificate_email(
    email: str, full_name: str, course_title: str, certificate_id: str, score: int
) -> bool:
    cert_url = f"{FRONTEND_URL}/certificate/{certificate_id}"
    passport_url = f"{FRONTEND_URL}/passport"
    name = _safe(full_name or "there")
    course = _safe(course_title)
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Congratulations, {name} —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  You've officially earned your certificate in <b style="color:#16335E;">{course}</b> with a score of <b style="color:#00A78B;">{score}%</b>. Your credential is <b>publicly verifiable</b> at <a href="{cert_url}" style="color:#00A78B;">{cert_url}</a> — share it on LinkedIn, drop it in your résumé, or email the link to your leadership team.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0;">
  You can also add it to your public <a href="{passport_url}" style="color:#00A78B;">AI Skills Passport</a> — a single link that shows everything you've earned across ITHR Academy.
</p>
"""
    html = _wrap(
        kicker="Credential Earned · ITHR Academy",
        heading=f"You're certified in {course}.",
        body_html=body,
        cta_label="View & download my certificate",
        cta_url=cert_url,
        footer_note="Your certificate PDF, QR code, and LinkedIn share button are all on the page.",
    )
    text = (
        f"Congratulations {name}!\n\n"
        f'You earned your certificate in "{course}" with a score of {score}%.\n\n'
        f"View + download: {cert_url}\n"
        f"AI Skills Passport: {passport_url}\n\n"
        "— ITHR Academy"
    )
    return await _fire(email, f"Certified in {course_title}", html, text, tag="cert")


# ---- Enterprise invite ----------------------------------------------------


async def send_org_invite_email(
    email: str, org_name: str, invite_code: str, admin_name: str
) -> bool:
    join_url = f"{FRONTEND_URL}/enterprise/join?code={invite_code}"
    admin = _safe(admin_name or "your team admin")
    org = _safe(org_name or "your organization")
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hi there —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  <b style="color:#16335E;">{admin}</b> has invited you to join <b style="color:#16335E;">{org}</b> on the ITHR Enterprise Agentic AI Academy.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Your invite code: <b style="font-family:monospace;background:#F6F8FB;padding:4px 10px;border-radius:4px;color:#00A78B;letter-spacing:1px;">{invite_code}</b>
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0;">
  You'll get full access to the course catalog, AI tutor, and any team-specific learning paths — all under {org}'s enterprise seat.
</p>
"""
    html = _wrap(
        kicker="Team Invite · ITHR Academy",
        heading=f"You're invited to {org}.",
        body_html=body,
        cta_label="Accept invite & join",
        cta_url=join_url,
        footer_note="If you didn't expect this invite, you can safely ignore this email — no account was created for you.",
    )
    text = (
        f"You're invited to join {org} on ITHR Academy.\n\n"
        f"Invite code: {invite_code}\n"
        f"Accept: {join_url}\n\n"
        "— ITHR Academy"
    )
    return await _fire(email, f"You're invited to {org_name} on ITHR Academy", html, text, tag="invite")
