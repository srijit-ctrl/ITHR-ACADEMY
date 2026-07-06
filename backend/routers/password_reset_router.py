"""Password reset flow — forgot-password + reset-password endpoints.

Flow:
1. POST /api/auth/forgot-password {email} — Always returns 200 (do not leak
   whether the email exists — prevents user enumeration). If the email
   matches an active learner/admin account, generate a single-use signed
   token, store its SHA-256 hash + expiry in the `password_reset_tokens`
   collection, and dispatch a branded Resend email with the reset link.

2. POST /api/auth/reset-password {token, new_password} — Validate the token
   is fresh, unconsumed, and matches an existing user. Update the user's
   password_hash, mark the token as consumed, and invalidate any other
   pending reset tokens for that user.

Rate limiting is enforced at two layers: per-IP (max 5/hour) and per-email
(max 3/hour) to prevent abuse. Enforcement uses a lightweight Mongo counter
so it survives worker restarts without needing Redis.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import resend
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from auth import hash_password
from core import db, logger, now_iso

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ---- Config ---------------------------------------------------------------
TOKEN_TTL_MINUTES = int(os.environ.get("PASSWORD_RESET_TOKEN_TTL_MINUTES", "60"))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

_RATE_IP_PER_HOUR = 5
_RATE_EMAIL_PER_HOUR = 3

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


# ---- Models ---------------------------------------------------------------
class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


# ---- Helpers --------------------------------------------------------------
def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def _check_rate_limit(bucket_key: str, limit: int) -> bool:
    """Return True if the request is under the rate limit; False if throttled."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)
    doc = await db.pw_reset_rate.find_one({"key": bucket_key})
    if not doc:
        await db.pw_reset_rate.insert_one({
            "key": bucket_key, "count": 1, "window_start": now.isoformat()
        })
        return True
    try:
        ws = datetime.fromisoformat(doc["window_start"])
        if ws.tzinfo is None:
            ws = ws.replace(tzinfo=timezone.utc)
    except Exception:
        ws = window_start
    if ws < window_start:
        # Reset window
        await db.pw_reset_rate.update_one(
            {"key": bucket_key},
            {"$set": {"count": 1, "window_start": now.isoformat()}},
        )
        return True
    if doc.get("count", 0) >= limit:
        return False
    await db.pw_reset_rate.update_one({"key": bucket_key}, {"$inc": {"count": 1}})
    return True


def _reset_email_html(full_name: str, reset_link: str) -> str:
    """Inline-CSS HTML for the reset email — email clients hate stylesheets."""
    safe_name = re.sub(r"[<>]", "", full_name or "there")
    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#F6F8FB;font-family:Calibre,Manrope,Tahoma,Arial,sans-serif;color:#16335E;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F8FB;padding:40px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:6px;box-shadow:0 8px 32px -12px rgba(22,51,94,0.15);overflow:hidden;">
          <tr>
            <td style="background:#16335E;padding:28px 32px;color:#ffffff;">
              <div style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#00A78B;font-family:monospace;">ITHR Academy · Password Reset</div>
              <div style="font-size:24px;font-weight:600;margin-top:6px;">Reset your password</div>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="font-size:16px;line-height:1.55;margin:0 0 16px 0;color:#16335E;">Hi {safe_name},</p>
              <p style="font-size:15px;line-height:1.6;margin:0 0 20px 0;color:#4b5563;">
                We received a request to reset the password for your ITHR Enterprise Agentic AI Academy account.
                Click the button below to set a new password. This link expires in <b>{TOKEN_TTL_MINUTES} minutes</b>
                and can only be used once.
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0;">
                <tr>
                  <td style="border-radius:999px;background:#00A78B;">
                    <a href="{reset_link}" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;font-family:Calibre,Manrope,Tahoma,Arial,sans-serif;">
                      Reset password
                    </a>
                  </td>
                </tr>
              </table>
              <p style="font-size:13px;line-height:1.6;margin:16px 0 0 0;color:#6b7280;">
                Or copy this link into your browser:<br>
                <a href="{reset_link}" style="color:#00A78B;word-break:break-all;">{reset_link}</a>
              </p>
              <p style="font-size:13px;line-height:1.6;margin:24px 0 0 0;color:#6b7280;">
                If you didn't request a password reset, you can safely ignore this email — your account remains secure.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px;background:#F6F8FB;border-top:1px solid #E5E7EB;font-size:12px;color:#6b7280;">
              ITHR Technologies Consulting LLC · Made in the UAE · <a href="{FRONTEND_URL}/legal/security" style="color:#00A78B;text-decoration:none;">Security policy</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _reset_email_text(full_name: str, reset_link: str) -> str:
    return (
        f"Hi {full_name or 'there'},\n\n"
        "We received a request to reset the password for your ITHR Academy account.\n\n"
        f"Reset your password (expires in {TOKEN_TTL_MINUTES} minutes):\n{reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email.\n\n"
        "— ITHR Enterprise Agentic AI Academy"
    )


async def _send_reset_email(to_email: str, full_name: str, reset_link: str) -> bool:
    """Fire the Resend send. Returns True on success. Logs on failure (never raises)."""
    if not RESEND_API_KEY:
        logger.warning(
            "[password_reset] RESEND_API_KEY not set — logging reset link instead of sending:\n"
            f"  to: {to_email}\n  link: {reset_link}"
        )
        return False
    params = {
        "from": f"ITHR Academy <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": "Reset your ITHR Academy password",
        "html": _reset_email_html(full_name, reset_link),
        "text": _reset_email_text(full_name, reset_link),
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"[password_reset] Sent to {to_email} (resend id: {result.get('id') if isinstance(result, dict) else result})")
        return True
    except Exception:
        logger.exception(f"[password_reset] Resend send failed for {to_email}")
        return False


# ---- Endpoints ------------------------------------------------------------
@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordIn, request: Request):
    """Kick off a password-reset. Always returns 200 to prevent enumeration."""
    email = payload.email.lower().strip()
    client_ip = (request.client.host if request.client else "unknown") or "unknown"

    # Rate limit BEFORE any DB lookup so a spammer can't probe emails.
    if not await _check_rate_limit(f"ip:{client_ip}", _RATE_IP_PER_HOUR):
        # Silent throttle — same 200 shape so nothing leaks.
        logger.warning(f"[password_reset] IP rate-limited: {client_ip}")
        return {"ok": True, "message": "If an account exists for that email, a reset link has been sent."}
    if not await _check_rate_limit(f"email:{email}", _RATE_EMAIL_PER_HOUR):
        logger.warning(f"[password_reset] Email rate-limited: {email}")
        return {"ok": True, "message": "If an account exists for that email, a reset link has been sent."}

    user = await db.users.find_one(
        {"email": email},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "auth_provider": 1},
    )
    # Silently succeed if user doesn't exist OR is a Google-OAuth-only user
    # (they have no password_hash to reset — direct them back to Google sign-in
    # via the same generic 200 message).
    if user and user.get("auth_provider") != "google":
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES)
        # Invalidate any prior unconsumed tokens for this user (single-active-link policy)
        await db.password_reset_tokens.update_many(
            {"user_id": user["id"], "consumed": False},
            {"$set": {"consumed": True, "invalidated_at": now_iso(), "invalidation_reason": "superseded"}},
        )
        await db.password_reset_tokens.insert_one({
            "user_id": user["id"],
            "email": user["email"],
            "token_hash": token_hash,
            "expires_at": expires_at,  # datetime; TTL index will auto-purge
            "consumed": False,
            "created_at": now_iso(),
            "ip": client_ip,
        })
        reset_link = f"{FRONTEND_URL}/reset-password?token={raw_token}"
        await _send_reset_email(user["email"], user.get("full_name") or "", reset_link)
    elif user and user.get("auth_provider") == "google":
        logger.info(f"[password_reset] Skipping reset for Google-auth user: {email}")

    return {"ok": True, "message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordIn):
    """Consume a reset token and set the new password."""
    token_hash = _hash_token(payload.token)
    now = datetime.now(timezone.utc)

    record = await db.password_reset_tokens.find_one(
        {"token_hash": token_hash, "consumed": False},
    )
    if not record:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has already been used.")

    expires_at = record.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except Exception:
            expires_at = None
    if not expires_at:
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")
    # Mongo returns naive UTC datetimes — normalize before comparison.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")

    user = await db.users.find_one({"id": record["user_id"]}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        raise HTTPException(status_code=400, detail="Account not found for this reset link.")

    # Update password_hash + mark token consumed atomically-ish
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(payload.new_password), "must_reset_password": False}},
    )
    await db.password_reset_tokens.update_one(
        {"_id": record["_id"]},
        {"$set": {"consumed": True, "consumed_at": now_iso()}},
    )
    # Invalidate any other still-open tokens for this user
    await db.password_reset_tokens.update_many(
        {"user_id": user["id"], "consumed": False},
        {"$set": {"consumed": True, "invalidated_at": now_iso(), "invalidation_reason": "reset_completed"}},
    )
    logger.info(f"[password_reset] Password reset completed for {user['email']}")
    return {"ok": True, "message": "Password has been reset. You can now sign in with your new password."}
