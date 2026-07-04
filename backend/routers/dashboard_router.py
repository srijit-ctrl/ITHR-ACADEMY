"""Dashboard stats."""
from fastapi import APIRouter, Depends

from auth import get_current_user_id
from core import db

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/stats")
async def dashboard_stats(user_id: str = Depends(get_current_user_id)):
    enrollment_count = await db.enrollments.count_documents({"user_id": user_id})
    cert_count = await db.certificates.count_documents({"user_id": user_id})
    completed = await db.enrollments.count_documents({"user_id": user_id, "completed": True})
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    return {
        "enrollments": enrollment_count,
        "certificates": cert_count,
        "completed_courses": completed,
        "xp": user.get("xp", 0),
        "streak_days": user.get("streak_days", 0),
        "subscription_tier": user.get("subscription_tier"),
        "subscription_expires_at": user.get("subscription_expires_at"),
    }


@router.get("/health")
async def health():
    from core import now_iso
    return {"status": "healthy", "timestamp": now_iso()}


@router.get("/")
async def root():
    return {"service": "Enterprise Agentic AI Academy", "status": "ok", "version": "1.0.0"}
