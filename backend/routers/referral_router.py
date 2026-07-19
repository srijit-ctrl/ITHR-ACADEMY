"""Referral & rewards endpoints."""
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user_id, get_current_user_optional
from core import db
from models import Enrollment
from security_service import require_flag
import referral_system

router = APIRouter(prefix="/api/referrals", tags=["referrals"], dependencies=[Depends(require_flag("referrals"))])


def _mask_name(full_name: str) -> str:
    """Anonymise a public leaderboard entry to first name + last-name initial."""
    parts = (full_name or "").strip().split()
    if not parts:
        return "Anonymous"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


async def _aggregate_leaderboard(limit: int) -> list[dict]:
    """Return the top-N referrers by CONVERTED signups (real enrollments),
    with total signups as a secondary sort. Referrers with zero signups
    are excluded."""
    pipeline = [
        {"$group": {
            "_id": "$referrer_id",
            "signups": {"$sum": 1},
            "converted": {"$sum": {"$cond": [{"$eq": ["$converted", True]}, 1, 0]}},
        }},
        {"$sort": {"converted": -1, "signups": -1, "_id": 1}},
        {"$limit": max(1, min(limit, 100))},
    ]
    rows = await db.referral_signups.aggregate(pipeline).to_list(limit)
    user_ids = [r["_id"] for r in rows]
    users = await db.users.find(
        {"id": {"$in": user_ids}},
        {"_id": 0, "id": 1, "full_name": 1, "personal_referral_code": 1, "email": 1, "organization": 1},
    ).to_list(len(user_ids)) if user_ids else []
    by_id = {u["id"]: u for u in users}
    out = []
    for r in rows:
        u = by_id.get(r["_id"], {})
        out.append({
            "user_id": r["_id"],
            "full_name": u.get("full_name") or "",
            "email": u.get("email") or "",
            "organization": u.get("organization") or "",
            "referral_code": u.get("personal_referral_code") or "",
            "signups": r["signups"],
            "converted": r["converted"],
        })
    return out


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


@router.get("/leaderboard")
async def referral_leaderboard(
    limit: int = Query(10, ge=1, le=50),
    user_id: str | None = Depends(get_current_user_optional),
):
    """Public leaderboard of top referrers.

    Rows anonymise the referrer to `First L.` so real names never leak to
    unauthenticated visitors — the same masking is applied to the caller's
    row too, keeping the display consistent. A signed-in caller additionally
    receives their own `viewer_rank` and `viewer_stats` so the UI can render
    "You are #12 with 3 signups" underneath the table.

    Sort: converted DESC, signups DESC — a real enrollment counts more than
    a pending invite.
    """
    top = await _aggregate_leaderboard(limit)
    total_referrers = await db.referral_signups.distinct("referrer_id")
    total_signups = await db.referral_signups.count_documents({})
    total_converted = await db.referral_signups.count_documents({"converted": True})

    rows = [
        {
            "rank": i + 1,
            "name": _mask_name(row["full_name"]),
            "organization": (row["organization"] or "")[:60],
            "signups": row["signups"],
            "converted": row["converted"],
        }
        for i, row in enumerate(top)
    ]

    payload: dict = {
        "rows": rows,
        "totals": {
            "referrers": len(total_referrers),
            "signups": total_signups,
            "converted": total_converted,
        },
    }

    if user_id:
        me_signups = await db.referral_signups.count_documents({"referrer_id": user_id})
        me_converted = await db.referral_signups.count_documents({"referrer_id": user_id, "converted": True})
        rank: int | None = None
        if me_signups > 0:
            # Rank = 1 + (# of referrers who beat me on (converted, signups))
            better = await db.referral_signups.aggregate([
                {"$group": {
                    "_id": "$referrer_id",
                    "signups": {"$sum": 1},
                    "converted": {"$sum": {"$cond": [{"$eq": ["$converted", True]}, 1, 0]}},
                }},
                {"$match": {"$or": [
                    {"converted": {"$gt": me_converted}},
                    {"converted": me_converted, "signups": {"$gt": me_signups}},
                ]}},
                {"$count": "n"},
            ]).to_list(1)
            rank = (better[0]["n"] if better else 0) + 1
        me = await db.users.find_one({"id": user_id}, {"_id": 0, "full_name": 1})
        payload["viewer_rank"] = rank
        payload["viewer_stats"] = {
            "name": _mask_name((me or {}).get("full_name", "")),
            "signups": me_signups,
            "converted": me_converted,
        }

    return payload


# ---- Public helper reused by admin_router for the unmasked view ----------
async def build_full_leaderboard(limit: int) -> dict:
    """Same aggregation, but WITHOUT masking — used by the Super Admin panel.

    Kept here (not in admin_router) to keep the aggregation logic in one file
    so masked + unmasked views can never drift apart.
    """
    top = await _aggregate_leaderboard(limit)
    return {
        "rows": [{"rank": i + 1, **row} for i, row in enumerate(top)],
        "totals": {
            "referrers": len(await db.referral_signups.distinct("referrer_id")),
            "signups": await db.referral_signups.count_documents({}),
            "converted": await db.referral_signups.count_documents({"converted": True}),
        },
    }
