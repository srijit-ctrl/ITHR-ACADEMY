"""JWT auth utilities.

Split-token model:
- Access token: short-lived (JWT_ACCESS_EXPIRY_MINUTES, default 15 min), sent in the
  Authorization: Bearer header, kept only in browser memory (never localStorage).
- Refresh token: longer-lived (JWT_REFRESH_EXPIRY_DAYS, default 7 days), signed with
  a separate secret, delivered only via an httpOnly + Secure + SameSite cookie, and
  used exclusively by POST /api/auth/refresh to mint a fresh access token.

The legacy create_token / JWT_EXPIRY_HOURS variables are kept as aliases so the
existing tests keep passing during migration, but new code should use
create_access_token / create_refresh_token.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "168"))

JWT_ACCESS_EXPIRY_MINUTES = int(os.environ.get("JWT_ACCESS_EXPIRY_MINUTES", "15"))
JWT_REFRESH_EXPIRY_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRY_DAYS", "7"))
JWT_REFRESH_SECRET = os.environ.get("JWT_REFRESH_SECRET", JWT_SECRET + "-refresh")

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str = "learner") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode an access token."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def decode_refresh_token(token: str) -> dict:
    payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token")
    return payload


# ---- Legacy alias (kept so existing code / tests continue to work) --------
def create_token(user_id: str, email: str, role: str = "learner") -> str:
    """Legacy alias — returns a short-lived access token."""
    return create_access_token(user_id, email, role)


async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        return payload["sub"]
    except Exception:
        return None
