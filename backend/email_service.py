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
PREFERRED_SENDER_EMAIL = os.environ.get("PREFERRED_SENDER_EMAIL", "")
PREFERRED_SENDER_DOMAIN_ID = os.environ.get("PREFERRED_SENDER_DOMAIN_ID", "")
_sender_cache = {"value": None, "checked_at": 0.0}
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


async def _preferred_domain_verified() -> bool:
    try:
        d = await asyncio.to_thread(resend.Domains.get, PREFERRED_SENDER_DOMAIN_ID)
        records = (d or {}).get("records") or []
        sending_records = [r for r in records if r.get("record") in ("DKIM", "SPF")]
        return bool(sending_records) and all(r.get("status") == "verified" for r in sending_records)
    except Exception:
        logger.warning("Preferred-sender domain check failed — using fallback sender")
        return False


async def _resolve_sender() -> str:
    """Prefers PREFERRED_SENDER_EMAIL once its Resend domain verifies; re-checks hourly."""
    import time
    if not (PREFERRED_SENDER_EMAIL and PREFERRED_SENDER_DOMAIN_ID):
        return SENDER_EMAIL
    now = time.monotonic()
    if _sender_cache["value"] and now - _sender_cache["checked_at"] < 3600:
        return _sender_cache["value"]
    sender = PREFERRED_SENDER_EMAIL if await _preferred_domain_verified() else SENDER_EMAIL
    _sender_cache.update(value=sender, checked_at=now)
    return sender


async def _fire(to_email: str, subject: str, html: str, text_fallback: str, tag: str) -> bool:
    """Actually send. Always safe — logs on failure, returns False."""
    if not RESEND_API_KEY:
        logger.warning(f"[email/{tag}] RESEND_API_KEY not set — email skipped for {to_email}")
        return False
    sender = await _resolve_sender()
    params = {
        "from": f"ITHR Academy <{sender}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text_fallback,
    }
    try:
        for attempt in range(4):
            try:
                result = await asyncio.to_thread(resend.Emails.send, params)
                break
            except resend.exceptions.RateLimitError:
                if attempt == 3:
                    raise
                await asyncio.sleep(1.2 * (attempt + 1))
        rid = result.get("id") if isinstance(result, dict) else result
        logger.info(f"[email/{tag}] Sent to {to_email} (resend id: {rid})")
        return True
    except Exception:
        logger.exception(f"[email/{tag}] Resend send failed for {to_email}")
        return False


# ---- Shared premium-voice building blocks ----------------------------------


def _first(full_name: str) -> str:
    return _safe(full_name or "there").split(" ")[0]


def _section(title: str) -> str:
    return f'<p style="font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#16335E;margin:0 0 8px 0;">{title}</p>'


def _signoff() -> str:
    return (
        '<p style="font-size:14px;line-height:1.5;margin:20px 0 0 0;border-top:1px solid #E5E9F0;padding-top:16px;">'
        '<b style="color:#16335E;">ITHR Academy</b><br/>'
        '<span style="color:#6b7280;font-style:italic;">Enterprise Agentic AI Academy</span><br/>'
        '<span style="color:#6b7280;">Made in the UAE</span></p>'
    )


_TEXT_SIGNOFF = "\n\nITHR Academy — Enterprise Agentic AI Academy — Made in the UAE"


# ---- Welcome on signup ----------------------------------------------------


async def send_welcome_email(email: str, full_name: str) -> bool:
    dash_url = f"{FRONTEND_URL}/dashboard"
    catalog_url = f"{FRONTEND_URL}/courses"
    first = _first(full_name)
    html = _wrap(
        kicker="ITHR Academy · Enterprise Agentic AI Academy",
        heading=f"Welcome to the Academy, {first}.",
        body_html=_welcome_body(first, catalog_url),
        cta_label="Access My Learning Portal",
        cta_url=dash_url,
        footer_note="You are receiving this email because an account was created for you at ITHR Academy.",
    )
    text = _welcome_text(first, dash_url, catalog_url)
    return await _fire(email, "Welcome to ITHR Academy — Your Learning Journey Begins", html, text, tag="welcome")


def _welcome_body(first: str, catalog_url: str) -> str:
    return f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Welcome to <b style="color:#16335E;">ITHR Academy</b>. Your learning journey begins today.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  You now have exclusive access to the ITHR Academy — a next-generation learning platform designed to help
  professionals and organizations build practical AI capabilities that deliver measurable business outcomes.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 20px 0;">
  Whether you're taking your first steps into Artificial Intelligence or advancing toward enterprise AI
  leadership, you're in the right place.
</p>
<p style="font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#16335E;margin:0 0 8px 0;">Start your learning journey</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  We recommend beginning with <a href="{catalog_url}" style="color:#00A78B;font-weight:600;">Agentic AI Foundations</a>,
  where you'll gain a strong understanding of AI agents, automation, enterprise use cases, and modern AI workflows.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 20px 0;">
  Throughout your learning experience, <b style="color:#16335E;">Aletheia</b>, your AI Learning Mentor, will guide
  you through each module, answer your questions, and help you apply concepts in real-world scenarios.
</p>
<p style="font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#16335E;margin:0 0 8px 0;">Need assistance?</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 20px 0;">
  Our support team is here to help. Simply reply to this email or contact us through the support portal,
  and one of our Academy specialists will respond promptly.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 4px 0;">
  We look forward to being part of your AI transformation journey.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:0 0 20px 0;">Welcome aboard.</p>
<p style="font-size:14px;line-height:1.5;margin:0;border-top:1px solid #E5E9F0;padding-top:16px;">
  <b style="color:#16335E;">ITHR Academy</b><br/>
  <span style="color:#6b7280;font-style:italic;">Enterprise Agentic AI Academy</span><br/>
  <span style="color:#6b7280;">Made in the UAE</span>
</p>
"""


def _welcome_text(first: str, dash_url: str, catalog_url: str) -> str:
    return (
        f"Hello {first},\n\n"
        "Welcome to ITHR Academy. Your learning journey begins today.\n\n"
        "You now have exclusive access to the ITHR Academy — a next-generation learning platform "
        "designed to help professionals and organizations build practical AI capabilities that deliver "
        "measurable business outcomes.\n\n"
        "START YOUR LEARNING JOURNEY\n"
        "We recommend beginning with Agentic AI Foundations. Aletheia, your AI Learning Mentor, "
        "will guide you through each module.\n\n"
        f"Access your learning portal: {dash_url}\n"
        f"Browse the catalog: {catalog_url}\n\n"
        "NEED ASSISTANCE?\n"
        "Simply reply to this email and one of our Academy specialists will respond promptly.\n\n"
        "Welcome aboard.\n\n"
        "ITHR Academy — Enterprise Agentic AI Academy — Made in the UAE"
    )


async def send_founding_welcome_email(email: str, full_name: str, seq: int) -> bool:
    """Welcome email for referral-code signups (first 500 = payment bypassed)."""
    dash_url = f"{FRONTEND_URL}/dashboard"
    login_url = f"{FRONTEND_URL}/login"
    name = _safe(full_name or "there")
    first = _first(full_name)
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  It is our privilege to welcome you as <b style="color:#16335E;">Founding Member #{seq} of 500</b> at ITHR Academy.
  Your referral code has been accepted and your account is marked <b style="color:#0f766e;">Paid</b> — no payment is required.
</p>
{_section("Your access details")}
<ul style="font-size:14px;line-height:1.8;color:#4b5563;margin:0 0 20px 0;padding-left:18px;">
  <li>Account email: <b>{_safe(email)}</b></li>
  <li>Status: Founding Member · Paid (referral)</li>
  <li>Sign in any time: <a href="{login_url}" style="color:#00A78B;">{login_url}</a></li>
</ul>
{_section("What this unlocks")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 4px 0;">
  Every course, video lesson, and certification examination on the platform is now available to you.
  <b style="color:#16335E;">Aletheia</b>, your AI Learning Mentor, will accompany you inside every lesson.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">Welcome aboard.</p>
{_signoff()}
"""
    html = _wrap(
        kicker=f"ITHR Academy · Founding Member #{seq}",
        heading=f"Welcome, {first} — your access is confirmed.",
        body_html=body,
        cta_label="Access My Learning Portal",
        cta_url=dash_url,
        footer_note="Please retain this email — it confirms your Founding Member status.",
    )
    text = (
        f"Hello {first},\n\n"
        f"Welcome — you are Founding Member #{seq} of 500 at ITHR Academy.\n"
        f"Your account ({email}) is marked Paid. No payment required.\n"
        f"Sign in: {login_url}\nLearning portal: {dash_url}\n\nWelcome aboard."
        + _TEXT_SIGNOFF
    )
    return await _fire(email, f"Founding Member #{seq} — your ITHR Academy access", html, text, tag="founding-welcome")


# ---- Certificate earned ---------------------------------------------------


async def send_certificate_email(
    email: str, full_name: str, course_title: str, certificate_id: str, score: int
) -> bool:
    cert_url = f"{FRONTEND_URL}/certificate/{certificate_id}"
    passport_url = f"{FRONTEND_URL}/passport"
    name = _safe(full_name or "there")
    first = _first(full_name)
    course = _safe(course_title)
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Congratulations. You have officially earned your certification in <b style="color:#16335E;">{course}</b>
  with a score of <b style="color:#00A78B;">{score}%</b> — a formal recognition of your professional AI capability.
</p>
{_section("Share your achievement")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Your credential is <b>publicly verifiable</b> at
  <a href="{cert_url}" style="color:#00A78B;">{cert_url}</a> — share it on LinkedIn, add it to your résumé,
  or forward the link to your leadership team.
</p>
{_section("Your AI Skills Passport")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0;">
  This credential has also been added to your public
  <a href="{passport_url}" style="color:#00A78B;">AI Skills Passport</a> — a single, verifiable record of
  everything you have earned across ITHR Academy.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">We are proud to certify your progress.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="Credential Earned · ITHR Academy",
        heading=f"You are certified in {course}.",
        body_html=body,
        cta_label="View & Download My Certificate",
        cta_url=cert_url,
        footer_note="Your certificate PDF, verification QR code, and LinkedIn share option are available on the certificate page.",
    )
    text = (
        f"Hello {first},\n\n"
        f'Congratulations — you have earned your certification in "{course}" with a score of {score}%.\n\n'
        f"View and download: {cert_url}\n"
        f"AI Skills Passport: {passport_url}"
        + _TEXT_SIGNOFF
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
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello,</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  <b style="color:#16335E;">{admin}</b> has invited you to join <b style="color:#16335E;">{org}</b>
  on the ITHR Academy — Enterprise Agentic AI Academy.
</p>
{_section("Your invitation code")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 16px 0;">
  <b style="font-family:monospace;background:#F6F8FB;padding:4px 10px;border-radius:4px;color:#00A78B;letter-spacing:1px;">{invite_code}</b>
</p>
{_section("What your enterprise seat includes")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0;">
  Full access to the complete course catalog, Aletheia — your AI Learning Mentor, and any team-specific
  learning paths curated by {org} — all under your organization's enterprise seat.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">We look forward to welcoming you.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="Enterprise Invitation · ITHR Academy",
        heading=f"You are invited to join {org}.",
        body_html=body,
        cta_label="Accept Invitation & Join",
        cta_url=join_url,
        footer_note="If you did not expect this invitation, you may safely disregard this email — no account has been created for you.",
    )
    text = (
        f"Hello,\n\n"
        f"{admin} has invited you to join {org} on ITHR Academy.\n\n"
        f"Invitation code: {invite_code}\n"
        f"Accept: {join_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, f"You're invited to {org_name} on ITHR Academy", html, text, tag="invite")


# ---- Payment confirmation -------------------------------------------------


async def send_payment_confirmation_email(
    email: str, full_name: str, item_description: str, amount: float,
    currency: str = "usd", invoice_id: str | None = None, receipt_url: str | None = None,
) -> bool:
    dash_url = f"{FRONTEND_URL}/dashboard"
    name = _safe(full_name or "there")
    first = _first(full_name)
    item = _safe(item_description)
    amt_str = f"${amount:,.2f} {currency.upper()}"
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 16px 0;">
  Thank you for your purchase. Your payment has been received and your access is now active.
</p>
{_section("Payment summary")}
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
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:16px 0 0 0;">
  Should you have any billing questions, simply reply to this email and one of our Academy specialists
  will respond promptly.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">Thank you for investing in your AI capability.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="Payment Confirmed · ITHR Academy",
        heading=f"Your payment is confirmed, {first}.",
        body_html=body,
        cta_label="Access My Learning Portal",
        cta_url=dash_url,
        footer_note="This payment was processed securely via Stripe.",
    )
    text = (
        f"Hello {first},\n\n"
        f"Thank you for your purchase — payment confirmed for {item}.\n"
        f"Amount: {amt_str}\n"
        + (f"Invoice: {invoice_id}\n" if invoice_id else "")
        + (f"Receipt: {receipt_url}\n" if receipt_url else "")
        + f"\nAccess your learning portal: {dash_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, "Payment confirmed — ITHR Academy", html, text, tag="payment")


# ---- Validity expiration --------------------------------------------------


async def send_validity_expiration_email(
    email: str, full_name: str, credential_or_plan: str, expires_on: str, renewal_url: str | None = None,
) -> bool:
    name = _safe(full_name or "there")
    first = _first(full_name)
    item = _safe(credential_or_plan)
    cta_url = renewal_url or f"{FRONTEND_URL}/pricing"
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  This is a courtesy notice that your <b style="color:#16335E;">{item}</b> is scheduled to expire on
  <b style="color:#00A78B;">{_safe(expires_on)}</b>.
</p>
{_section("Why renew now")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Renewing keeps your credentials publicly verifiable, your team's seats active, and your learning
  progress uninterrupted — with no re-onboarding required.
</p>
<p style="font-size:13px;line-height:1.6;color:#6b7280;margin:16px 0 0 0;">
  Not planning to renew? No action is needed — you will receive one final reminder 24 hours before the
  expiration date, after which access winds down gracefully.
</p>
{_signoff()}
"""
    html = _wrap(
        kicker="Renewal Notice · ITHR Academy",
        heading=f"Your {item} expires soon.",
        body_html=body,
        cta_label="Renew My Access",
        cta_url=cta_url,
        footer_note="",
    )
    text = (
        f"Hello {first},\n\n"
        f"Your {item} expires on {expires_on}. Renew: {cta_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, f"Renewal reminder: {credential_or_plan}", html, text, tag="expiration")


# ---- Complaint / Support response ----------------------------------------


async def send_complaint_response_email(
    email: str, full_name: str, ticket_ref: str, response_text: str, agent_name: str = "The ITHR Support Team",
) -> bool:
    name = _safe(full_name or "there")
    first = _first(full_name)
    # Escape the response body but keep line breaks
    safe_response = _safe(response_text).replace("\n", "<br>")
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 16px 0;">
  Thank you for contacting ITHR Academy. Please find below our response to your inquiry
  (reference <span style="font-family:monospace;color:#00A78B;">{_safe(ticket_ref)}</span>):
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#F6F8FB;border-left:4px solid #00A78B;border-radius:0 6px 6px 0;margin:0 0 16px 0;">
  <tr><td style="padding:16px 20px;font-size:14px;line-height:1.65;color:#16335E;">{safe_response}</td></tr>
</table>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:0;">
  If this fully resolves your inquiry, no further action is required. Should you need anything more,
  simply reply to this email — it will route directly back to your assigned specialist, and we will
  continue working with you until the matter is fully resolved.
</p>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:14px 0 0 0;">
  With regards,<br/><b style="color:#16335E;">{_safe(agent_name)}</b>
</p>
{_signoff()}
"""
    html = _wrap(
        kicker=f"Support Response · Ref {_safe(ticket_ref)}",
        heading="A response to your inquiry.",
        body_html=body,
        cta_label="Reply / Open My Ticket",
        cta_url=f"{FRONTEND_URL}/support?ref={ticket_ref}",
        footer_note="You may reply directly to this email — all replies are logged against your ticket automatically.",
    )
    text = (
        f"Hello {first},\n\nRe: {ticket_ref}\n\n{response_text}\n\nWith regards,\n{agent_name}"
        + _TEXT_SIGNOFF
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
    first = _first(full_name)
    course = _safe(course_title)
    verify_url = f"{FRONTEND_URL}/verify/{certificate_id}"
    passport_url = f"{FRONTEND_URL}/passport"
    html = _wrap(
        kicker="Credential Verified · ITHR Academy",
        heading="Your credential was just verified.",
        body_html=_verify_alert_body(first, course, certificate_id, verified_at, verifier_ip_hash, passport_url),
        cta_label="View My Skills Passport",
        cta_url=passport_url,
        footer_note=(
            "This is a positive signal — verifiers only reach this page when they wish to confirm your qualifications. "
            f"You can view the public record at {verify_url}."
        ),
    )
    text = (
        f"Hello {first},\n\n"
        f"Your {course} credential ({certificate_id}) was verified at {verified_at} UTC.\n\n"
        f"Public record: {verify_url}\nAI Skills Passport: {passport_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, f'Your "{course_title}" credential was just verified', html, text, tag="verify-alert")


def _verify_alert_body(first: str, course: str, certificate_id: str, verified_at: str, verifier_ip_hash: str, passport_url: str) -> str:
    return f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Your <b style="color:#16335E;">{course}</b> credential was just verified on the public verification page.
  This typically indicates a recruiter, hiring manager, or business partner is confirming your
  qualifications — a strong signal of professional interest.
</p>
{_section("Verification details")}
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#F6F8FB;border-radius:6px;margin:12px 0;">
  <tr><td style="padding:12px 16px;font-size:12px;color:#6b7280;">
    <div><b style="color:#16335E;">Credential:</b> {course}</div>
    <div><b style="color:#16335E;">ID:</b> <span style="font-family:monospace;">{_safe(certificate_id)}</span></div>
    <div><b style="color:#16335E;">Verified at:</b> {_safe(verified_at)} UTC</div>
    <div><b style="color:#16335E;">Verifier (hashed):</b> <span style="font-family:monospace;font-size:10px;">{_safe(verifier_ip_hash)[:12]}…</span></div>
  </td></tr>
</table>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:14px 0 0 0;">
  This is an excellent moment to ensure your <a href="{passport_url}" style="color:#00A78B;">AI Skills Passport</a>
  reflects your latest credentials — it is what verifiers see when they scan your QR code.
</p>
{_signoff()}
"""


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
    passport_url = f"{FRONTEND_URL}/passport"
    dash_url = f"{FRONTEND_URL}/dashboard"
    html = _wrap(
        kicker="Weekly Credential Report · ITHR Academy",
        heading=f"{week_impressions} verification{'s' if week_impressions != 1 else ''} this week.",
        body_html=_digest_body(_first(full_name), week_impressions, _digest_rows_html(top_credentials), passport_url),
        cta_label="View My Skills Passport",
        cta_url=passport_url,
        footer_note=f"To pause these weekly summaries, adjust your notification settings at {dash_url}/settings.",
    )
    text = (
        f"Hello {_first(full_name)},\n\n"
        f"Your credentials were verified {week_impressions} time(s) this past week.\n\n"
        + "\n".join(f'  {c.get("course_title","?")} — {c.get("impressions",0)}×' for c in (top_credentials[:5] or []))
        + f"\n\nAI Skills Passport: {passport_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, f"You had {week_impressions} credential verification(s) this week", html, text, tag="digest-impressions")


def _digest_rows_html(top_credentials: list[dict]) -> str:
    return "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #E5E7EB;font-size:14px;color:#16335E;">{_safe(c.get("course_title",""))}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #E5E7EB;font-size:14px;text-align:right;font-family:monospace;color:#00A78B;">{int(c.get("impressions", 0))}×</td></tr>'
        for c in (top_credentials[:5] or [])
    ) or '<tr><td colspan="2" style="padding:12px 0;font-size:13px;color:#6b7280;">—</td></tr>'


def _digest_body(first: str, week_impressions: int, rows_html: str, passport_url: str) -> str:
    return f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Your credentials were verified <b style="color:#00A78B;">{week_impressions} time{'s' if week_impressions != 1 else ''}</b>
  this week. Verifications typically come from recruiters, hiring managers, and business partners confirming
  your qualifications — a strong signal of professional interest in your profile.
</p>
{_section("Most-verified this week")}
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#F6F8FB;border-radius:6px;margin:8px 0;">
  <tr>
    <td style="padding:6px 16px;font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#6b7280;">Credential</td>
    <td style="padding:6px 16px;font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#6b7280;text-align:right;">Verifies</td>
  </tr>
  <tr><td colspan="2" style="padding:0 16px 12px 16px;"><table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;">{rows_html}</table></td></tr>
</table>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:14px 0 0 0;">
  This is an excellent moment to ensure your <a href="{passport_url}" style="color:#00A78B;">AI Skills Passport</a>
  and public profile reflect your latest credentials.
</p>
{_signoff()}
"""


# ---- Referral system emails ------------------------------------------------


async def send_first_course_bypass_email(email: str, full_name: str, code: str, course_title: str, seq: int) -> bool:
    """First 500 first-enrollments: unique bypass code = that course + cert free."""
    dash_url = f"{FRONTEND_URL}/dashboard"
    name = _safe(full_name or "there")
    first = _first(full_name)
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Congratulations. You are enrollment <b style="color:#16335E;">#{seq} of the first 500</b> at ITHR Academy —
  and as part of our founding cohort, your course <b style="color:#16335E;">{_safe(course_title)}</b>,
  including its full certification, is complimentary.
</p>
{_section("Your bypass code — already applied")}
<p style="font-family:monospace;font-size:22px;letter-spacing:3px;color:#00A78B;background:#F0FDF9;border:1px dashed #00A78B;padding:14px 18px;text-align:center;margin:0 0 16px 0;">{_safe(code)}</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0;">
  No action is required — the code has been applied to your account automatically. Continue your course,
  complete the certification examination, and your credential will be issued at no charge.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">Enjoy the journey.</p>
{_signoff()}
"""
    html = _wrap(
        kicker=f"ITHR Academy · First 500 — #{seq}",
        heading="Your first course is complimentary.",
        body_html=body,
        cta_label="Continue My Learning",
        cta_url=dash_url,
        footer_note="This one-time bypass applies to your first enrolled course and its certificate.",
    )
    text = (
        f"Hello {first},\n\n"
        f"Congratulations — you are enrollment #{seq} of the first 500 at ITHR Academy.\n"
        f"Your course \"{course_title}\", including certification, is complimentary.\n"
        f"Bypass code (already applied): {code}\n\n"
        f"Continue learning: {dash_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, f"You're #{seq} of 500 — your first course is free", html, text, tag="bypass")


async def send_referral_reward_email(email: str, full_name: str, referred_name: str, reward_num: int) -> bool:
    """Referrer earned a free course of choice (max 5)."""
    dash_url = f"{FRONTEND_URL}/dashboard"
    name = _safe(full_name or "there")
    first = _first(full_name)
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Excellent news — <b style="color:#16335E;">{_safe(referred_name)}</b> joined ITHR Academy using your
  referral code and has enrolled in their first course.
</p>
{_section("Your reward")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0;">
  This earns you <b style="color:#00A78B;">complimentary course #{reward_num} of 5</b> — any course of your
  choice, including its certification. Redeem it from the Referrals panel on your dashboard.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">Thank you for growing the Academy community.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="Referral Reward · ITHR Academy",
        heading=f"Complimentary course #{reward_num} of 5 unlocked.",
        body_html=body,
        cta_label="Redeem My Complimentary Course",
        cta_url=dash_url,
        footer_note="Share your code with up to 5 professionals — each successful enrollment unlocks another complimentary course.",
    )
    text = (
        f"Hello {first},\n\n"
        f"{referred_name} joined ITHR Academy with your referral code and enrolled in their first course.\n"
        f"You've earned complimentary course #{reward_num} of 5 — redeem from your dashboard's Referrals panel.\n\n"
        f"Learning portal: {dash_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, f"Referral reward unlocked — free course #{reward_num} of 5", html, text, tag="referral-reward")


# ---- Onboarding drip: Day-2 first-course nudge --------------------------


async def send_first_course_nudge_email(email: str, full_name: str) -> bool:
    """Sent on Day 2 to registered learners who haven't enrolled in any course yet.

    Nudge the learner into their first enrollment (which triggers the first-course
    bypass code + starts real learning). Warm, low-pressure tone.
    """
    catalog_url = f"{FRONTEND_URL}/courses"
    dash_url = f"{FRONTEND_URL}/dashboard"
    first = _first(full_name)
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  A couple of days ago you claimed your seat at <b style="color:#16335E;">ITHR Academy</b> — welcome
  once more. Your account is ready; the next step is choosing where to start.
</p>
{_section("Two ways to begin")}
<ul style="font-size:14px;line-height:1.8;color:#4b5563;margin:0 0 20px 0;padding-left:18px;">
  <li><b style="color:#16335E;">Agentic AI Foundations</b> — the vocabulary and mental models every leader needs, in 15 modules.</li>
  <li><b style="color:#16335E;">An industry track</b> — Banking, Healthcare, Manufacturing, Retail, Government or HR / Talent Ops — tailored to the room you actually work in.</li>
</ul>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Whichever you pick, <b style="color:#16335E;">Aletheia</b>, your AI tutor, is embedded inside every
  lesson to answer questions in your context and quiz you when you want to stress-test the material.
</p>
{_section("Founding Member perk still active")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  While the first 500 seats are open, your first full course + credential is free once you enroll —
  no card required. It is limited to a single course per learner, so choose the one that matters most.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">Pick a course and I'll see you inside.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="ITHR Academy · Choose your first course",
        heading=f"Ready when you are, {first}.",
        body_html=body,
        cta_label="Browse the Catalog",
        cta_url=catalog_url,
        footer_note=f"If you'd rather go straight to your dashboard, sign in here: {dash_url}",
    )
    text = (
        f"Hello {first},\n\n"
        "A couple of days ago you claimed your seat at ITHR Academy. Your account is ready — "
        "the next step is picking a first course.\n\n"
        "TWO WAYS TO BEGIN\n"
        "• Agentic AI Foundations — the vocabulary + mental models every leader needs (15 modules).\n"
        "• An industry track — Banking, Healthcare, Manufacturing, Retail, Government, or HR.\n\n"
        "FOUNDING MEMBER PERK\n"
        "Your first full course + credential is free while the first-500 seats remain open.\n\n"
        f"Browse the catalog: {catalog_url}\n"
        f"Dashboard: {dash_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, "Your ITHR Academy seat is waiting — pick a course to begin", html, text, tag="drip-first-course-nudge")


# ---- Onboarding drip: Day-5 referral invite ------------------------------


async def send_referral_invite_email(email: str, full_name: str, referral_code: str, share_url: str) -> bool:
    """Sent on Day 5 to learners who have started at least one course but haven't
    yet shared their personal referral code. Positions the ask as "reward the
    people you'd want in the room with you"."""
    first = _first(full_name)
    dash_url = f"{FRONTEND_URL}/dashboard"
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  You're in — and now you have five invitations you can hand out.
</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 20px 0;">
  Your <b style="color:#16335E;">personal referral code</b> gives up to five other professionals their
  first full course free. Each one who enrolls unlocks another complimentary course of your choice —
  up to five, on us.
</p>
{_section("Your code")}
<div style="background:#F6F8FB;border:1px dashed #16335E;border-radius:6px;padding:14px 18px;margin:0 0 18px 0;text-align:center;">
  <div style="font-family:monospace;font-size:22px;letter-spacing:0.2em;color:#16335E;font-weight:600;">{_safe(referral_code)}</div>
</div>
<p style="font-size:14px;line-height:1.6;color:#4b5563;margin:0 0 20px 0;">
  Or share this direct link: <a href="{share_url}" style="color:#00A78B;font-weight:600;word-break:break-all;">{share_url}</a>
</p>
{_section("Who should you invite?")}
<ul style="font-size:14px;line-height:1.8;color:#4b5563;margin:0 0 20px 0;padding-left:18px;">
  <li>The two colleagues you already trust with hard problems.</li>
  <li>Anyone reporting into you who has been asking "where do I start with AI?"</li>
  <li>A peer at another company you swap notes with — they'll thank you.</li>
</ul>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">Reward the people you'd want in the room with you.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="ITHR Academy · Five invitations to give",
        heading=f"{first}, five people can join — free — on you.",
        body_html=body,
        cta_label="Manage My Referrals",
        cta_url=dash_url,
        footer_note="You can copy your code, share it on LinkedIn, or send it via WhatsApp from your dashboard's Refer & Earn panel.",
    )
    text = (
        f"Hello {first},\n\n"
        "You're in — and now you have five invitations you can hand out.\n\n"
        f"Your personal referral code: {referral_code}\n"
        f"Direct link: {share_url}\n\n"
        "Each of the first five people who enrolls with your code gets their first course free — "
        "and unlocks another complimentary course of your choice for you.\n\n"
        f"Manage referrals: {dash_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(email, "5 invitations to give — your ITHR Academy referral code", html, text, tag="drip-referral-invite")


# ---- Automated campaigns (Iteration 57) ---------------------------------
#
# Three new lifecycle triggers driven by Resend + logged via `email_trigger_log`.
#   1. Module-completion nudge  — fires after any full module completes on any course.
#   2. Module-5 offer           — fires exactly once when the 5th module of a course
#                                  completes.  Positions the "unlock 10 more modules
#                                  free — first 500 users" perk.
#   3. 7-day re-engagement       — sweep-driven; identifies learners inactive ≥ 7 days
#                                  (no enrolments touched, no lesson completions).


async def send_module_completion_email(
    email: str,
    full_name: str,
    course_title: str,
    course_slug: str,
    module_title: str,
    module_index: int,
    total_modules: int,
    next_module_title: str | None,
) -> bool:
    """Fired when a learner finishes every lesson in a module.

    Keeps the momentum going — congratulates on progress, previews the next
    module, and links straight to the course dashboard.
    """
    first = _first(full_name)
    course_url = f"{FRONTEND_URL}/courses/{course_slug}"
    dash_url = f"{FRONTEND_URL}/dashboard"
    completion_pct = round((module_index / total_modules) * 100) if total_modules else 0
    next_block = ""
    if next_module_title:
        next_block = f"""
{_section("Up next")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Your next module is <b style="color:#16335E;">{_safe(next_module_title)}</b>. Aletheia will pick up
  right where you left off — click Continue below and we'll drop you into the first lesson.
</p>
"""
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Nicely done — you just finished <b style="color:#16335E;">{_safe(module_title)}</b>
  in <b style="color:#16335E;">{_safe(course_title)}</b>. That's <b style="color:#00A78B;">{module_index} of {total_modules}</b>
  modules complete (~{completion_pct}% of the course).
</p>
<div style="background:#F6F8FB;border-radius:6px;padding:14px 18px;margin:0 0 16px 0;">
  <div style="height:8px;background:#E5E9F0;border-radius:999px;overflow:hidden;">
    <div style="height:100%;width:{completion_pct}%;background:linear-gradient(90deg,#00A78B,#2E7FC1);"></div>
  </div>
  <div style="font-size:12px;letter-spacing:0.1em;text-transform:uppercase;color:#6b7280;margin-top:8px;text-align:right;">
    {completion_pct}% complete
  </div>
</div>
{next_block}
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">Keep the streak alive.</p>
{_signoff()}
"""
    html = _wrap(
        kicker=f"Module {module_index} of {total_modules} · Complete",
        heading=f"Module complete — {module_index}/{total_modules}",
        body_html=body,
        cta_label="Continue Course",
        cta_url=course_url,
        footer_note=f"Not ready right now? Your progress is saved. Come back any time via your dashboard: {dash_url}",
    )
    text = (
        f"Hello {first},\n\n"
        f"You just finished \"{module_title}\" in \"{course_title}\". "
        f"That's {module_index} of {total_modules} modules ({completion_pct}%).\n\n"
        + (f"Up next: {next_module_title}\n\n" if next_module_title else "")
        + f"Continue: {course_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(
        email,
        f"Module {module_index} complete — {module_index}/{total_modules} in {course_title}",
        html, text, tag="module-complete",
    )


async def send_module_5_offer_email(
    email: str,
    full_name: str,
    course_title: str,
    course_slug: str,
    seq_position: int | None = None,
) -> bool:
    """Sent once, on completion of the 5th module of any course.

    Positions the founding-cohort perk: "Unlock the next 10 modules free —
    only for the first 500 users." If `seq_position` is provided we surface
    it so the recipient sees they are still inside the cohort.
    """
    first = _first(full_name)
    course_url = f"{FRONTEND_URL}/courses/{course_slug}"
    dash_url = f"{FRONTEND_URL}/dashboard"
    seq_line = ""
    if seq_position and seq_position <= 500:
        seq_line = (
            f'<p style="font-size:13px;line-height:1.5;color:#6b7280;margin:0 0 12px 0;">'
            f'You are Founding Member <b style="color:#16335E;">#{seq_position} of 500</b> — '
            'the offer below is reserved for the founding cohort.</p>'
        )
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  Five modules down — that's the halfway line on <b style="color:#16335E;">{_safe(course_title)}</b>.
  The pattern-matching should be starting to click. This is the point at which most learners
  drop off. We want you to stay.
</p>
{seq_line}
{_section("Founding offer · Unlock the next 10 modules free")}
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  For the <b style="color:#00A78B;">first 500 Founding Members</b>, the remaining 10 modules of this
  course — plus its full certification — are complimentary. No card required. No promotional code
  to enter. It is applied to your account the moment you click Continue.
</p>
<ul style="font-size:14px;line-height:1.8;color:#4b5563;margin:0 0 20px 0;padding-left:18px;">
  <li>Complete the remaining 10 modules at your pace.</li>
  <li>Sit the certification exam whenever you feel ready.</li>
  <li>Earn a publicly verifiable digital credential (LinkedIn-ready).</li>
</ul>
<p style="font-size:13px;line-height:1.6;color:#6b7280;margin:0 0 12px 0;">
  This offer is limited to the founding cohort and applies to a single course per learner —
  claim it while your seat is active.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">You are 5 modules from a credential.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="Founding cohort perk · Unlock 10 modules free",
        heading="You're halfway. Let's finish.",
        body_html=body,
        cta_label="Unlock the Next 10 Modules",
        cta_url=course_url,
        footer_note=f"Manage your enrolments from your dashboard: {dash_url}",
    )
    text = (
        f"Hello {first},\n\n"
        f"You just finished 5 modules of \"{course_title}\" — halfway there.\n\n"
        "FOUNDING OFFER — UNLOCK THE NEXT 10 MODULES FREE\n"
        "For the first 500 Founding Members, the remaining 10 modules of this course, plus its full "
        "certification, are complimentary. No card required.\n\n"
        + (f"You are Founding Member #{seq_position} of 500.\n\n" if seq_position and seq_position <= 500 else "")
        + f"Continue: {course_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(
        email,
        f"Halfway there — unlock the next 10 modules of {course_title} free",
        html, text, tag="module-5-offer",
    )


async def send_reengagement_email(email: str, full_name: str, days_inactive: int) -> bool:
    """Sent on the 7-day dormancy sweep to learners who have not touched a lesson.

    Warm, low-pressure re-entry. Highlights AI tutor + industry tracks
    without shaming the absence.
    """
    first = _first(full_name)
    dash_url = f"{FRONTEND_URL}/dashboard"
    catalog_url = f"{FRONTEND_URL}/courses"
    body = f"""\
<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  It's been a little while — {days_inactive} days since you last dropped into the Academy.
  Life gets busy; that's OK. The good news: nothing you started is lost — every lesson, every
  completed module, every rating is exactly where you left it.
</p>
{_section("Three ways to restart in under 5 minutes")}
<ul style="font-size:14px;line-height:1.8;color:#4b5563;margin:0 0 20px 0;padding-left:18px;">
  <li><b style="color:#16335E;">Ask Aletheia to recap</b> — one message on the dashboard tutor, and she'll summarise where you left off.</li>
  <li><b style="color:#16335E;">Pick the shortest lesson</b> — most next-lessons in-flight are &lt; 10 minutes.</li>
  <li><b style="color:#16335E;">Try a different track</b> — Banking, Healthcare, Manufacturing, Retail, Government, or HR — pattern-switch the momentum back on.</li>
</ul>
<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 12px 0;">
  If nothing above resonates, hit reply and tell us what's blocking — we read every response.
</p>
<p style="font-size:15px;line-height:1.6;color:#16335E;font-weight:600;margin:16px 0 0 0;">See you inside.</p>
{_signoff()}
"""
    html = _wrap(
        kicker="ITHR Academy · Come back and finish",
        heading=f"Your seat is still yours, {first}.",
        body_html=body,
        cta_label="Resume My Learning",
        cta_url=dash_url,
        footer_note=f"Browse the full catalog: {catalog_url}",
    )
    text = (
        f"Hello {first},\n\n"
        f"It's been {days_inactive} days since you last dropped in. Nothing you started is lost.\n\n"
        "THREE WAYS TO RESTART IN UNDER 5 MINUTES\n"
        "• Ask Aletheia (AI tutor) to recap where you left off.\n"
        "• Pick the shortest lesson — most next-up lessons are < 10 minutes.\n"
        "• Try a different track — Banking, Healthcare, Manufacturing, Retail, Government, or HR.\n\n"
        f"Resume: {dash_url}\n"
        f"Catalog: {catalog_url}"
        + _TEXT_SIGNOFF
    )
    return await _fire(
        email,
        f"Your Academy seat is still yours, {first} — 3 ways to restart",
        html, text, tag="reengagement-7d",
    )


# ---- Manual campaign shell (custom body from Super Admin composer) -------


async def send_manual_campaign_email(
    email: str,
    full_name: str,
    subject: str,
    body_markdown: str,
    cta_label: str | None,
    cta_url: str | None,
) -> bool:
    """Deliver a Super-Admin-composed campaign to a single recipient.

    `body_markdown` accepts plain paragraphs separated by blank lines — we wrap
    each paragraph in <p> tags so admins can compose in a simple textarea
    without knowing HTML. Optional CTA button is rendered only when both
    `cta_label` and `cta_url` are supplied.
    """
    first = _first(full_name)
    paragraphs = [p.strip() for p in (body_markdown or "").split("\n\n") if p.strip()]
    body_html = "".join(
        f'<p style="font-size:15px;line-height:1.6;color:#4b5563;margin:0 0 14px 0;">{_safe(p).replace(chr(10), "<br/>")}</p>'
        for p in paragraphs
    )
    body_html = f'<p style="font-size:16px;line-height:1.55;margin:0 0 14px 0;">Hello {first},</p>' + body_html + _signoff()

    if cta_label and cta_url:
        html = _wrap(
            kicker="ITHR Academy",
            heading=_safe(subject),
            body_html=body_html,
            cta_label=_safe(cta_label),
            cta_url=cta_url,
            footer_note="You are receiving this email because you have an account at ITHR Academy.",
        )
    else:
        # Reuse _wrap but hide the CTA row by pointing it at the dashboard.
        html = _wrap(
            kicker="ITHR Academy",
            heading=_safe(subject),
            body_html=body_html,
            cta_label="Open My Dashboard",
            cta_url=f"{FRONTEND_URL}/dashboard",
            footer_note="You are receiving this email because you have an account at ITHR Academy.",
        )
    text_paragraphs = "\n\n".join(paragraphs)
    text = f"Hello {first},\n\n{text_paragraphs}" + _TEXT_SIGNOFF
    return await _fire(email, subject, html, text, tag="manual-campaign")
