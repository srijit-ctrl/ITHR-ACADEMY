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


# ---- Payment confirmation -------------------------------------------------


async def send_payment_confirmation_email(
    email: str, full_name: str, item_description: str, amount: float,
    currency: str = "usd", invoice_id: str | None = None, receipt_url: str | None = None,
) -> bool:
    dash_url = f"{FRONTEND_URL}/dashboard"
    name = _safe(full_name or "there")
    item = _safe(item_description)
    amt_str = f"${amount:,.2f} {currency.upper()}"
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hi {name} —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 16px 0;">
  Thank you for your payment. Your enrollment / seat purchase is confirmed and access is live.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#F6F8FB;border-radius:6px;margin:0 0 8px 0;">
  <tr><td style="padding:16px 20px;">
    <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#6b7280;margin-bottom:4px;">Item</div>
    <div style="font-size:15px;color:#16335E;font-weight:600;">{item}</div>
    <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#6b7280;margin:14px 0 4px;">Amount</div>
    <div style="font-size:22px;color:#00A78B;font-weight:600;">{amt_str}</div>
    {f'<div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#6b7280;margin:14px 0 4px;">Invoice ID</div><div style="font-family:monospace;font-size:13px;color:#16335E;">{_safe(invoice_id)}</div>' if invoice_id else ''}
  </td></tr>
</table>
{f'<p style="font-size:13px;margin:16px 0 0 0;"><a href="{receipt_url}" style="color:#00A78B;">View full receipt →</a></p>' if receipt_url else ''}
"""
    html = _wrap(
        kicker="Payment Confirmed · ITHR Academy",
        heading=f"You're all set, {name}.",
        body_html=body,
        cta_label="Continue to my dashboard",
        cta_url=dash_url,
        footer_note="This payment was processed securely via Stripe. Reach out to billing@ithr.tech for any billing questions.",
    )
    text = (
        f"Hi {name},\n\n"
        f"Payment confirmed for {item}.\n"
        f"Amount: {amt_str}\n"
        + (f"Invoice: {invoice_id}\n" if invoice_id else "")
        + (f"Receipt: {receipt_url}\n" if receipt_url else "")
        + f"\nContinue: {dash_url}\n\n— ITHR Academy"
    )
    return await _fire(email, "Payment confirmed — ITHR Academy", html, text, tag="payment")


# ---- Validity expiration --------------------------------------------------


async def send_validity_expiration_email(
    email: str, full_name: str, credential_or_plan: str, expires_on: str, renewal_url: str | None = None,
) -> bool:
    name = _safe(full_name or "there")
    item = _safe(credential_or_plan)
    cta_url = renewal_url or f"{FRONTEND_URL}/pricing"
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hi {name} —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  A quick heads-up: your <b style="color:#16335E;">{item}</b> is scheduled to expire on <b style="color:#00A78B;">{_safe(expires_on)}</b>.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Renewing now keeps your credentials verifiable, your team's seats active, and your dashboard streak intact — with no re-onboarding required.
</p>
<p style="font-size:13px;line-height:1.6;color:#6b7280;margin:16px 0 0 0;">
  Not planning to renew? No action needed — you'll receive one final reminder 24 hours before the expiration date, then access winds down gracefully.
</p>
"""
    html = _wrap(
        kicker="Renewal Reminder · ITHR Academy",
        heading=f"Your {item} expires soon.",
        body_html=body,
        cta_label="Renew now",
        cta_url=cta_url,
        footer_note="",
    )
    text = (
        f"Hi {name},\n\n"
        f"Your {item} expires on {expires_on}. Renew: {cta_url}\n\n— ITHR Academy"
    )
    return await _fire(email, f"Renewal reminder: {credential_or_plan}", html, text, tag="expiration")


# ---- Complaint / Support response ----------------------------------------


async def send_complaint_response_email(
    email: str, full_name: str, ticket_ref: str, response_text: str, agent_name: str = "The ITHR Support Team",
) -> bool:
    name = _safe(full_name or "there")
    # Escape the response body but keep line breaks
    safe_response = _safe(response_text).replace("\n", "<br>")
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hi {name} —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 16px 0;">
  Thank you for reaching out. Here is our response to your inquiry (reference <span style="font-family:monospace;color:#00A78B;">{_safe(ticket_ref)}</span>):
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#F6F8FB;border-left:4px solid #00A78B;border-radius:0 6px 6px 0;margin:0 0 16px 0;">
  <tr><td style="padding:16px 20px;font-size:14px;line-height:1.65;color:#16335E;">{safe_response}</td></tr>
</table>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:0;">
  If this fully answers your question, feel free to close the thread. If not, simply reply to this email and it will route back to me directly — we&apos;ll keep working until it&apos;s resolved.
</p>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:14px 0 0 0;">
  — {_safe(agent_name)}
</p>
"""
    html = _wrap(
        kicker=f"Support Response · Ref {_safe(ticket_ref)}",
        heading="A response to your inquiry.",
        body_html=body,
        cta_label="Reply / open ticket",
        cta_url=f"{FRONTEND_URL}/support?ref={ticket_ref}",
        footer_note="You can reply directly to this email — all replies are logged against your ticket automatically.",
    )
    text = (
        f"Hi {name},\n\nRe: {ticket_ref}\n\n{response_text}\n\n— {agent_name}\nITHR Support"
    )
    return await _fire(email, f"Re: your ITHR support ticket [{ticket_ref}]", html, text, tag="support")


# ---- Credential verification alert (holder is notified) ------------------


async def send_credential_verification_alert(
    email: str, full_name: str, certificate_id: str, course_title: str,
    verifier_ip_hash: str, verified_at: str,
) -> bool:
    """Fire when someone visits the public verify page for a cert.

    Sends a heads-up to the CREDENTIAL HOLDER so they know their cert
    is being checked (e.g., during a hiring interview). Positioning:
    "signal of interest" — this is a feature, not a security alert.
    """
    name = _safe(full_name or "there")
    course = _safe(course_title)
    verify_url = f"{FRONTEND_URL}/verify/{certificate_id}"
    passport_url = f"{FRONTEND_URL}/passport"
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hi {name} —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Someone just verified your <b style="color:#16335E;">{course}</b> credential on the public verification page. That usually means a recruiter, hiring manager, or partner is checking your qualifications right now.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#F6F8FB;border-radius:6px;margin:12px 0;">
  <tr><td style="padding:12px 16px;font-size:12px;color:#6b7280;">
    <div><b style="color:#16335E;">Credential:</b> {course}</div>
    <div><b style="color:#16335E;">ID:</b> <span style="font-family:monospace;">{_safe(certificate_id)}</span></div>
    <div><b style="color:#16335E;">Verified at:</b> {_safe(verified_at)} UTC</div>
    <div><b style="color:#16335E;">Verifier (hashed):</b> <span style="font-family:monospace;font-size:10px;">{_safe(verifier_ip_hash)[:12]}…</span></div>
  </td></tr>
</table>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:14px 0 0 0;">
  A great time to make sure your <a href="{passport_url}" style="color:#00A78B;">AI Skills Passport</a> is up to date — that&apos;s what verifiers see when they scan the QR code.
</p>
"""
    html = _wrap(
        kicker="Credential Verified · ITHR Academy",
        heading="Someone just verified your credential.",
        body_html=body,
        cta_label="View my passport",
        cta_url=passport_url,
        footer_note=(
            "This is a positive signal — verifiers only reach this page when they want to confirm your qualifications. "
            "If you did NOT expect this and don't recognize any pending job/partnership contexts, "
            f"you can still view the public record at {verify_url}."
        ),
    )
    text = (
        f"Hi {name},\n\n"
        f"Someone verified your {course} credential ({certificate_id}) at {verified_at} UTC.\n\n"
        f"View public record: {verify_url}\nAI Skills Passport: {passport_url}\n\n— ITHR Academy"
    )
    return await _fire(email, f'Your "{course_title}" credential was just verified', html, text, tag="verify-alert")


# ---- Weekly credential-impressions digest --------------------------------


async def send_impressions_digest_email(
    email: str, full_name: str, week_impressions: int, top_credentials: list[dict],
) -> bool:
    """Weekly summary of credential verifications for a learner.

    Only send when week_impressions >= 1 — no zero-value emails.
    top_credentials: list of {course_title, impressions} sorted desc.
    """
    if week_impressions < 1:
        return False
    name = _safe(full_name or "there")
    passport_url = f"{FRONTEND_URL}/passport"
    dash_url = f"{FRONTEND_URL}/dashboard"

    rows_html = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #E5E7EB;font-size:14px;color:#16335E;">{_safe(c.get("course_title",""))}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #E5E7EB;font-size:14px;text-align:right;font-family:monospace;color:#00A78B;">{int(c.get("impressions", 0))}×</td></tr>'
        for c in (top_credentials[:5] or [])
    ) or '<tr><td colspan="2" style="padding:12px 0;font-size:13px;color:#6b7280;">—</td></tr>'

    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hi {name} —</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Your credentials were verified <b style="color:#00A78B;">{week_impressions} time{'s' if week_impressions != 1 else ''}</b> this week — typically that means recruiters, hiring managers, or partners are checking your qualifications. Great signal of professional interest.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#F6F8FB;border-radius:6px;margin:8px 0;">
  <tr>
    <td style="padding:6px 16px;font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#6b7280;">Most-verified this week</td>
    <td style="padding:6px 16px;font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#6b7280;text-align:right;">Verifies</td>
  </tr>
  <tr><td colspan="2" style="padding:0 16px 12px 16px;"><table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;">{rows_html}</table></td></tr>
</table>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:14px 0 0 0;">
  Perfect time to double-check that your <a href="{passport_url}" style="color:#00A78B;">AI Skills Passport</a> and public profile reflect your latest credentials.
</p>
"""
    html = _wrap(
        kicker="Weekly Credential Report · ITHR Academy",
        heading=f"{week_impressions} verification{'s' if week_impressions != 1 else ''} this week.",
        body_html=body,
        cta_label="View my passport",
        cta_url=passport_url,
        footer_note=f"To pause these weekly summaries, adjust your notification settings at {dash_url}/settings.",
    )
    text = (
        f"Hi {name},\n\n"
        f"Your credentials were verified {week_impressions} time(s) this past week.\n\n"
        + "\n".join(f'  {c.get("course_title","?")} — {c.get("impressions",0)}×' for c in (top_credentials[:5] or []))
        + f"\n\nPassport: {passport_url}\n\n— ITHR Academy"
    )
    return await _fire(email, f"You had {week_impressions} credential verification(s) this week", html, text, tag="digest-impressions")
