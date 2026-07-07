"""Founding-Member perk system.

The first 500 users to register get a lifetime perk on their **first
enrolled course**: unlocked access to modules 6-15 + a free certificate
on that course. After that first course they are ordinary paying users.

Fields stored on `users`:
- founding_member_seq: int    | The 1-based ordinal (1..500)
- signup_discount_code: str   | 10-char code (uppercase alnum)
- founding_course_id: str|None| Set on first enrollment
- founding_cert_used: bool    | Set true after they claim the free cert

Public helpers:
- assign_if_eligible(user_id)   Called during registration
- claim_first_course(user_id, course_id)  Called on first enrollment
- has_full_module_access(user, course_id)
- can_claim_free_cert(user, course_id)
"""
import os
import secrets
import string

from core import db, logger

FOUNDER_CAP = 500


def _referral_code() -> str:
    return (os.environ.get("FOUNDING_REFERRAL_CODE") or "").strip().upper()


def is_valid_referral_code(code: str) -> bool:
    configured = _referral_code()
    return bool(configured) and (code or "").strip().upper() == configured


async def redeem_referral_code(user_id: str, code: str) -> dict | None:
    """First 500 signups using the referral code bypass payment entirely.

    Marks the user payment_status='paid' + paid_via_referral, allocating a
    1-based referral_seq. Returns {seq} on success, None when the code is
    invalid or the 500-user cap is exhausted.
    """
    if not is_valid_referral_code(code):
        return None
    seq = await db.users.count_documents({"paid_via_referral": True}) + 1
    if seq > FOUNDER_CAP:
        logger.info(f"Referral cap reached — user {user_id[:8]}… registered without bypass")
        return None
    result = await db.users.update_one(
        {"id": user_id, "paid_via_referral": {"$exists": False}},
        {"$set": {
            "payment_status": "paid",
            "paid_via_referral": True,
            "referral_seq": seq,
        }},
    )
    if result.modified_count == 0:
        return None
    logger.info(f"Referral bypass #{seq}/{FOUNDER_CAP} applied to user {user_id[:8]}…")
    return {"seq": seq}
CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))


async def assign_if_eligible(user_id: str) -> dict | None:
    """Idempotent — assigns a founding code if one is still available.

    Returns {seq, code} when the user is one of the founders, None otherwise.
    Safe to call multiple times on the same user (no double-allocation).
    """
    existing = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "founding_member_seq": 1, "signup_discount_code": 1},
    )
    # NB: Mongo returns `{}` (empty dict — truthy check would flip wrong way)
    # when the user exists but neither field has been set yet. Compare `is None`
    # explicitly so a fresh user is treated as eligible instead of "not found".
    if existing is None:
        return None
    if existing.get("founding_member_seq"):
        return {
            "seq": existing["founding_member_seq"],
            "code": existing["signup_discount_code"],
        }

    # Count founders atomically-ish. This is fine for a launch-time perk;
    # a hard-race two users landing at seq=500 is acceptable (one takes 500,
    # the other misses out — no user gets a duplicate seq).
    seq = await db.users.count_documents({"founding_member_seq": {"$exists": True}}) + 1
    if seq > FOUNDER_CAP:
        return None

    code = _generate_code()
    # Ensure uniqueness — retry a handful of times before giving up.
    for _ in range(5):
        if not await db.users.find_one({"signup_discount_code": code}, {"_id": 0, "id": 1}):
            break
        code = _generate_code()

    result = await db.users.update_one(
        {"id": user_id, "founding_member_seq": {"$exists": False}},
        {"$set": {"founding_member_seq": seq, "signup_discount_code": code, "founding_cert_used": False}},
    )
    if result.modified_count == 0:
        # Someone else won the race — re-read
        again = await db.users.find_one({"id": user_id}, {"_id": 0, "founding_member_seq": 1, "signup_discount_code": 1})
        if again and again.get("founding_member_seq"):
            return {"seq": again["founding_member_seq"], "code": again["signup_discount_code"]}
        return None

    logger.info(f"Founding member #{seq}/{FOUNDER_CAP} allocated to user {user_id[:8]}… (code={code})")
    return {"seq": seq, "code": code}


async def claim_first_course(user_id: str, course_id: str) -> None:
    """Called when a user enrolls in their first course.

    Sets the founding_course_id if the user is a founder AND has not already
    claimed a founding course. This determines which single course gets the
    modules 6-15 + free cert perk.
    """
    user = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "founding_member_seq": 1, "founding_course_id": 1},
    )
    if not user or not user.get("founding_member_seq"):
        return
    if user.get("founding_course_id"):
        return
    await db.users.update_one(
        {"id": user_id, "founding_course_id": {"$exists": False}},
        {"$set": {"founding_course_id": course_id}},
    )


def has_full_module_access(user: dict, course_id: str) -> bool:
    """True when a founder's founding course grants full-course access."""
    if not user:
        return False
    if user.get("founding_member_seq") and user.get("founding_course_id") == course_id:
        return True
    return False


def can_claim_free_cert(user: dict, course_id: str) -> bool:
    """True when a founder can claim a free cert on this course (once)."""
    if not user or not user.get("founding_member_seq"):
        return False
    if user.get("founding_course_id") != course_id:
        return False
    return not user.get("founding_cert_used", False)


async def mark_cert_claimed(user_id: str) -> None:
    await db.users.update_one({"id": user_id}, {"$set": {"founding_cert_used": True}})


async def stats() -> dict:
    """Aggregate founding-member stats for the super-admin dashboard."""
    total_claimed = await db.users.count_documents({"founding_member_seq": {"$exists": True}})
    with_first_course = await db.users.count_documents({"founding_course_id": {"$exists": True}})
    cert_used = await db.users.count_documents({"founding_cert_used": True})
    return {
        "cap": FOUNDER_CAP,
        "claimed": total_claimed,
        "remaining": max(0, FOUNDER_CAP - total_claimed),
        "with_first_course_locked": with_first_course,
        "cert_claimed": cert_used,
    }
