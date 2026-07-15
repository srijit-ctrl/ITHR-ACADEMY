"""Referral & rewards endpoints."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user_id
from core import db
from models import Enrollment
import referral_system

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


@router.get("/me")
async def my_referrals(user_id: str = Depends(get_current_user_id)):
    share_base = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
    return await referral_system.get_summary(user_id, share_base)


class RedeemPayload(BaseModel):
    course_slug: str


@router.post("/redeem")
async def redeem(payload: RedeemPayload, user_id: str = Depends(get_current_user_id)):
    course = await db.courses.find_one({"slug": payload.course_slug}, {"_id": 0, "id": 1, "title": 1})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    existing = await db.enrollments.find_one({"user_id": user_id, "course_id": course["id"]})
    if existing:
        raise HTTPException(status_code=400, detail="You are already enrolled in this course — pick another one")
    result = await referral_system.redeem_reward(user_id, course)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    enrollment = Enrollment(user_id=user_id, course_id=course["id"])
    await db.enrollments.insert_one(enrollment.model_dump())
    await db.courses.update_one({"id": course["id"]}, {"$inc": {"enrolled_count": 1}})
    return {"ok": True, "enrolled_course": course["title"]}
