"""Auth routes: register, login, me, google callback, refresh, logout.

Token flow (in-memory access + httpOnly refresh cookie):
- On register/login/google-callback the API returns a short-lived access token in the
  JSON body AND sets an httpOnly Secure SameSite refresh cookie.
- On /auth/refresh the API reads the cookie and returns a new access token.
- On /auth/logout the API clears the refresh cookie.

Access tokens are NEVER persisted client-side (browser memory only).
"""
import os
import uuid

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from auth import (
    JWT_REFRESH_EXPIRY_DAYS,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user_id,
    hash_password,
    verify_password,
)
from core import db, logger, now_iso, user_to_public
from models import AuthResponse, UserLogin, UserPublic, UserRegister

router = APIRouter(prefix="/api", tags=["auth"])

REFRESH_COOKIE_NAME = "ithr_refresh"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")


def _set_refresh_cookie(response: Response, user_id: str) -> None:
    refresh = create_refresh_token(user_id)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=JWT_REFRESH_EXPIRY_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    # Emit an explicit Set-Cookie with all the original flags so defence-in-depth
    # is preserved on strict user agents (some UAs only match on name+path+domain
    # when deleting, but re-emitting HttpOnly/Secure/SameSite avoids any ambiguity).
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value="",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=0,
        path="/api/auth",
    )


async def _validate_registration(payload: UserRegister) -> dict | None:
    """Gate checks before account creation. Returns the personal referrer (or None)."""
    import security_service as sec
    if not await sec.flag_enabled("registrations"):
        raise HTTPException(status_code=403, detail="New registrations are temporarily disabled")
    if await db.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already registered")
    policy = (await sec.get_security_settings())["password_policy"]
    policy_errors = sec.validate_password(payload.password, policy)
    if policy_errors:
        raise HTTPException(status_code=400, detail="; ".join(policy_errors))
    # Validate any provided referral code BEFORE creating the account so a
    # typo'd code fails loudly instead of silently registering a free account.
    if payload.referral_code:
        from founding_member import is_valid_referral_code
        if not is_valid_referral_code(payload.referral_code):
            import referral_system
            personal_referrer = await referral_system.find_referrer_by_code(payload.referral_code)
            if not personal_referrer:
                raise HTTPException(status_code=400, detail="Invalid referral code")
            return personal_referrer
    return None


async def _apply_signup_perks(doc: dict, payload: UserRegister, personal_referrer: dict | None) -> dict | None:
    """Founding-member allocation + referral redemption. Returns founding referral result (or None)."""
    user_id = doc["id"]
    # Founding-member perk allocation (first 500 signups get a lifetime perk on
    # their first enrolled course — free modules 6-15 + free certificate).
    try:
        from founding_member import assign_if_eligible
        result = await assign_if_eligible(user_id)
        if result:
            doc["founding_member_seq"] = result["seq"]
            doc["signup_discount_code"] = result["code"]
            doc["founding_cert_used"] = False
    except Exception:
        logger.exception("Founding-member allocation raised during registration")

    referral_applied = None
    if payload.referral_code and not personal_referrer:
        # FOUNDING500-style payment bypass (first 500 redemptions -> marked Paid).
        try:
            from founding_member import redeem_referral_code
            referral_applied = await redeem_referral_code(user_id, payload.referral_code)
            if referral_applied:
                doc["payment_status"] = "paid"
                doc["paid_via_referral"] = True
                doc["referral_seq"] = referral_applied["seq"]
        except Exception:
            logger.exception("Referral redemption raised during registration")
    elif personal_referrer:
        # Personal referral (ITHR-XXXXXX): record signup + grant first-course-free
        try:
            import referral_system
            ok = await referral_system.handle_referral_signup(
                personal_referrer, user_id, doc["email"], payload.referral_code
            )
            if ok:
                await db.users.update_one({"id": user_id}, {"$set": {
                    "referred_by": personal_referrer["id"],
                    "referred_via_code": payload.referral_code.strip().upper(),
                }})
        except Exception:
            logger.exception("Personal-referral signup raised during registration")
    return referral_applied


def _dispatch_signup_side_effects(doc: dict, referral_applied: dict | None) -> None:
    """Fire-and-forget welcome email + super-admin activity feed — never blocks the response."""
    import asyncio as _asyncio
    try:
        if referral_applied:
            from email_service import send_founding_welcome_email
            _asyncio.create_task(send_founding_welcome_email(
                doc["email"], doc.get("full_name") or "", referral_applied["seq"]
            ))
        else:
            from email_service import send_welcome_email
            _asyncio.create_task(send_welcome_email(doc["email"], doc.get("full_name") or ""))
    except Exception:
        logger.exception("Welcome-email dispatch failed (non-fatal)")
    try:
        from core import log_activity
        _asyncio.create_task(log_activity(
            kind="signup",
            message=f"New signup: {doc['full_name']} ({doc['email']})",
            actor_id=doc["id"], actor_name=doc.get("full_name"),
        ))
    except Exception:
        logger.exception("Activity-log dispatch failed (non-fatal)")


def _issue_session(response: Response, doc: dict, request: Request | None = None) -> str:
    """Common session-issue path: mint access token, set refresh cookie, and
    (when a Request object is available) schedule non-blocking login tracking.

    Returns the access token so callers can shape the JSON body as needed.
    Used by /auth/login, /auth/mfa-verify, /auth/refresh, /auth/google/callback.
    """
    access = create_access_token(doc["id"], doc["email"], doc["role"])
    _set_refresh_cookie(response, doc["id"])
    if request is not None:
        from login_tracking import schedule_login_tracking
        schedule_login_tracking(doc["id"], request)
    return access


async def _check_mfa_required(doc: dict) -> dict | None:
    """If the account has MFA enabled, return the challenge-token envelope
    (caller returns it immediately). Otherwise return None so caller continues
    to normal session issue.
    """
    if not doc.get("mfa_enabled"):
        return None
    import security_service as sec
    return {"mfa_required": True, "challenge_token": sec.create_mfa_challenge_token(doc["id"])}


def _verify_totp_or_backup(doc: dict, code: str) -> bool:
    """Verify a TOTP challenge OR fall back to a single-use backup code.

    Backup codes are stored as SHA-256 hashes and marked `used=true` when
    consumed. Returns True on any successful match. Never raises.
    """
    import hashlib
    import pyotp
    if pyotp.TOTP(doc["mfa_secret"]).verify(code, valid_window=1):
        return True
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    backups = doc.get("mfa_backup_codes") or []
    for b in backups:
        if not b.get("used") and b.get("hash") == code_hash:
            return True
    return False


async def _consume_backup_code(user_id: str, code_hash: str) -> None:
    """Mark a single backup code as used (positional-array update)."""
    await db.users.update_one(
        {"id": user_id, "mfa_backup_codes.hash": code_hash},
        {"$set": {"mfa_backup_codes.$.used": True}},
    )


@router.post("/auth/register", response_model=AuthResponse)
async def register(payload: UserRegister, response: Response):
    personal_referrer = await _validate_registration(payload)

    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name,
        "role": payload.role or "learner",
        "organization": payload.organization,
        "title": payload.title,
        "avatar_url": None,
        "xp": 0,
        "streak_days": 0,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)

    referral_applied = await _apply_signup_perks(doc, payload, personal_referrer)
    _dispatch_signup_side_effects(doc, referral_applied)

    access = _issue_session(response, doc)
    return AuthResponse(token=access, user=UserPublic(**user_to_public(doc)))


@router.post("/auth/login", response_model=None)
async def login(payload: UserLogin, request: Request, response: Response):
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if doc.get("is_suspended"):
        raise HTTPException(status_code=403, detail="This account has been suspended. Contact your administrator.")
    mfa_envelope = await _check_mfa_required(doc)
    if mfa_envelope:
        # Password OK, TOTP pending: issue a 5-min challenge token instead of real tokens.
        return mfa_envelope
    access = _issue_session(response, doc, request)
    import security_service as sec
    result = {"token": access, "user": user_to_public(doc)}
    settings = await sec.get_security_settings()
    if sec.mfa_enforcement_covers(settings["mfa_enforcement"], doc.get("role", "learner")):
        result["mfa_setup_required"] = True
    return result


class MfaVerifyPayload(BaseModel):
    challenge_token: str
    code: str


@router.post("/auth/mfa-verify", response_model=None)
async def mfa_verify_login(payload: MfaVerifyPayload, request: Request, response: Response):
    import hashlib
    import security_service as sec
    try:
        user_id = sec.decode_mfa_challenge_token(payload.challenge_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA challenge — sign in again")
    doc = await db.users.find_one({"id": user_id})
    if not doc or not doc.get("mfa_enabled") or not doc.get("mfa_secret"):
        raise HTTPException(status_code=400, detail="MFA is not configured for this account")
    code = payload.code.strip().upper()
    if not _verify_totp_or_backup(doc, code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    # If a backup code was used, mark it consumed (single-use).
    import pyotp
    if not pyotp.TOTP(doc["mfa_secret"]).verify(code, valid_window=1):
        await _consume_backup_code(user_id, hashlib.sha256(code.encode()).hexdigest())
    access = _issue_session(response, doc, request)
    return {"token": access, "user": user_to_public(doc)}


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh(response: Response, ithr_refresh: str = Cookie(default=None)):
    """Exchange a valid refresh cookie for a fresh access token.

    Also rotates the refresh cookie (sliding expiry) so long-lived sessions
    don't require a hard re-login every 7 days.
    """
    if not ithr_refresh:
        raise HTTPException(status_code=401, detail="No refresh cookie")
    try:
        payload = decode_refresh_token(ithr_refresh)
    except Exception:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user_id = payload["sub"]
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="User no longer exists")
    if doc.get("is_suspended"):
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=403, detail="Account suspended")
    access = _issue_session(response, doc)
    return AuthResponse(token=access, user=UserPublic(**user_to_public(doc)))


@router.post("/auth/logout")
async def logout(response: Response):
    _clear_refresh_cookie(response)
    return {"ok": True}


@router.get("/auth/me", response_model=UserPublic)
async def me(user_id: str = Depends(get_current_user_id)):
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return UserPublic(**user_to_public(doc))


async def _exchange_google_session(session_id: str) -> dict:
    """Exchange an Emergent OAuth session_id for the user's Google profile.

    Raises HTTPException(401) if the exchange fails — the upstream provider
    error is intentionally NOT surfaced in the response body (side-channel
    hardening). Full context is captured server-side via `logger.exception`.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            logger.exception("Emergent OAuth exchange failed")
            raise HTTPException(status_code=401, detail="OAuth verification failed")


async def _upsert_google_user(profile: dict) -> dict:
    """Find-or-create a user document from a validated Google profile.

    Preserves any pre-existing `full_name` on the DB record (users may have
    edited it after registering); only fills a name from Google when the DB
    record has none.
    """
    email = (profile.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="No email returned by provider")

    existing = await db.users.find_one({"email": email})
    if existing:
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "avatar_url": profile.get("picture"),
                "full_name": existing.get("full_name") or profile.get("name") or email,
            }},
        )
        return await db.users.find_one({"email": email})

    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id, "email": email, "password_hash": "",
        "full_name": profile.get("name") or email.split("@")[0],
        "role": "learner", "organization": None, "title": None,
        "avatar_url": profile.get("picture"),
        "xp": 0, "streak_days": 0,
        "created_at": now_iso(),
        "auth_provider": "google",
    }
    await db.users.insert_one(user_doc)
    return user_doc


@router.post("/auth/google/callback", response_model=AuthResponse)
async def google_callback(payload: dict, request: Request, response: Response):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    profile = await _exchange_google_session(session_id)
    user_doc = await _upsert_google_user(profile)
    access = _issue_session(response, user_doc, request)
    return AuthResponse(token=access, user=UserPublic(**user_to_public(user_doc)))
