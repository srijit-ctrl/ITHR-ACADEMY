"""Auth routes: register, login, me, google callback."""
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

from auth import create_token, get_current_user_id, hash_password, verify_password
from core import db, logger, now_iso, user_to_public
from models import AuthResponse, UserLogin, UserPublic, UserRegister

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse)
async def register(payload: UserRegister):
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
    token = create_token(user_id, doc["email"], doc["role"])
    return AuthResponse(token=token, user=UserPublic(**user_to_public(doc)))


@router.post("/auth/login", response_model=AuthResponse)
async def login(payload: UserLogin):
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(doc["id"], doc["email"], doc["role"])
    return AuthResponse(token=token, user=UserPublic(**user_to_public(doc)))


@router.get("/auth/me", response_model=UserPublic)
async def me(user_id: str = Depends(get_current_user_id)):
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return UserPublic(**user_to_public(doc))


@router.post("/auth/google/callback", response_model=AuthResponse)
async def google_callback(payload: dict):
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
        except Exception as e:
            logger.exception("Emergent OAuth exchange failed")
            raise HTTPException(status_code=401, detail=f"OAuth verification failed: {e}")

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

    token = create_token(user_doc["id"], user_doc["email"], user_doc["role"])
    return AuthResponse(token=token, user=UserPublic(**user_to_public(user_doc)))
