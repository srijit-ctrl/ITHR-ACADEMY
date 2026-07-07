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


@router.post("/auth/register", response_model=AuthResponse)
async def register(payload: UserRegister, response: Response):
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

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
    # Founding-member perk allocation (first 500 signups get a lifetime perk on
    # their first enrolled course — free modules 6-15 + free certificate).
    try:
        from founding_member import assign_if_eligible
        result = await assign_if_eligible(user_id)
        if result:
            # Re-hydrate local doc so the response reflects the newly-assigned
            # founding_member_seq + signup_discount_code fields.
            doc["founding_member_seq"] = result["seq"]
            doc["signup_discount_code"] = result["code"]
            doc["founding_cert_used"] = False
    except Exception:
        # Non-fatal — user is still registered. Log loudly so future silent
        # regressions of the "seq/code stay null" class don't slip through.
        logger.exception("Founding-member allocation raised during registration")

    # Send the welcome email as a fire-and-forget task so a slow / failing
    # Resend call never blocks the register response.
    try:
        import asyncio as _asyncio
        from email_service import send_welcome_email
        _asyncio.create_task(send_welcome_email(doc["email"], doc.get("full_name") or ""))
    except Exception:
        logger.exception("Welcome-email dispatch failed (non-fatal)")

    # Log to the super-admin live activity feed (fire-and-forget).
    try:
        from core import log_activity
        import asyncio as _asyncio
        _asyncio.create_task(log_activity(
            kind="signup",
            message=f"New signup: {doc['full_name']} ({doc['email']})",
            actor_id=user_id, actor_name=doc.get("full_name"),
        ))
    except Exception:
        logger.exception("Activity-log dispatch failed (non-fatal)")

    access = create_access_token(user_id, doc["email"], doc["role"])
    _set_refresh_cookie(response, user_id)
    return AuthResponse(token=access, user=UserPublic(**user_to_public(doc)))


@router.post("/auth/login", response_model=AuthResponse)
async def login(payload: UserLogin, request: Request, response: Response):
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if doc.get("is_suspended"):
        raise HTTPException(status_code=403, detail="This account has been suspended. Contact your administrator.")
    access = create_access_token(doc["id"], doc["email"], doc["role"])
    _set_refresh_cookie(response, doc["id"])
    # Fire-and-forget login tracking (updates last_login_at, login_count,
    # IP + geo + language). Never blocks the auth response.
    from login_tracking import schedule_login_tracking
    schedule_login_tracking(doc["id"], request)
    return AuthResponse(token=access, user=UserPublic(**user_to_public(doc)))


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
    access = create_access_token(doc["id"], doc["email"], doc["role"])
    _set_refresh_cookie(response, doc["id"])
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


@router.post("/auth/google/callback", response_model=AuthResponse)
async def google_callback(payload: dict, request: Request, response: Response):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )
            r.raise_for_status()
            profile = r.json()
        except Exception:
            logger.exception("Emergent OAuth exchange failed")
            # Deliberately generic — do not leak upstream provider details in the
            # HTTP body. Full context is captured server-side via logger.exception.
            raise HTTPException(status_code=401, detail="OAuth verification failed")

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
        user_doc = await db.users.find_one({"email": email})
    else:
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

    access = create_access_token(user_doc["id"], user_doc["email"], user_doc["role"])
    _set_refresh_cookie(response, user_doc["id"])
    # Fire-and-forget login tracking so Google sign-ins also appear in
    # /api/admin/dashboard KPIs (active_7d/active_30d, geo card, language pie).
    from login_tracking import schedule_login_tracking
    schedule_login_tracking(user_doc["id"], request)
    return AuthResponse(token=access, user=UserPublic(**user_to_public(user_doc)))
