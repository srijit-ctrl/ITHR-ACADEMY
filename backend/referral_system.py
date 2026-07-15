"""Unique referral & first-course-bypass system.

Mechanic 1 — First-course bypass (first 500 first-enrollments platform-wide):
    when a user enrolls in their FIRST course, they receive a unique bypass
    code by email entitling them to complete THAT course incl. certification
    free of charge.

Mechanic 2 — Personal referral codes:
    every user owns a unique shareable code (max 5 signups). A referred user
    who signs up with it gets their FIRST course free; when they enroll, the
    referrer earns one free course of choice (max 5 rewards).

Collections:
    referral_signups:    {id, referrer_id, referred_id, referred_email, code,
                          converted, converted_course_id, created_at, converted_at}
    course_entitlements: {id, user_id, source, code, seq, course_id,
                          course_title, redeemed, created_at}
        source ∈ first-course-bypass | referred-first-course | referral-reward
"""
import secrets
import string
import uuid

from core import db, logger, now_iso

BYPASS_CAP = 500
REFERRAL_MAX_USES = 5

_ALPHABET = string.ascii_uppercase + string.digits


def _code(prefix: str, n: int = 8) -> str:
    return f"{prefix}-" + "".join(secrets.choice(_ALPHABET) for _ in range(n))


async def ensure_personal_code(user_id: str) -> str:
    """Idempotent: returns the user's unique shareable referral code."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "personal_referral_code": 1})
    if user is None:
        return ""
    if user.get("personal_referral_code"):
        return user["personal_referral_code"]
    for _ in range(6):
        code = _code("ITHR", 6)
        if not await db.users.find_one({"personal_referral_code": code}, {"_id": 1}):
            break
    await db.users.update_one(
        {"id": user_id, "personal_referral_code": {"$exists": False}},
        {"$set": {"personal_referral_code": code}},
    )
    doc = await db.users.find_one({"id": user_id}, {"_id": 0, "personal_referral_code": 1})
    return doc.get("personal_referral_code", code)


async def find_referrer_by_code(code: str) -> dict | None:
    return await db.users.find_one(
        {"personal_referral_code": (code or "").strip().upper()},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1},
    )


async def referral_uses(referrer_id: str) -> int:
    return await db.referral_signups.count_documents({"referrer_id": referrer_id})


async def handle_referral_signup(referrer: dict, referred_id: str, referred_email: str, code: str) -> bool:
    """Records a referred signup + grants the referred user a first-course-free
    entitlement. Returns False when the referrer's 5-signup cap is exhausted."""
    if await referral_uses(referrer["id"]) >= REFERRAL_MAX_USES:
        return False
    await db.referral_signups.insert_one({
        "id": str(uuid.uuid4()),
        "referrer_id": referrer["id"],
        "referred_id": referred_id,
        "referred_email": referred_email,
        "code": code.strip().upper(),
        "converted": False,
        "converted_course_id": None,
        "created_at": now_iso(),
        "converted_at": None,
    })
    await db.course_entitlements.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": referred_id,
        "source": "referred-first-course",
        "code": code.strip().upper(),
        "course_id": None,  # locked to their first enrolled course
        "course_title": None,
        "redeemed": False,
        "created_at": now_iso(),
    })
    logger.info(f"Referral signup recorded: {referred_email} via {code} (referrer {referrer['id'][:8]}…)")
    return True


async def _issue_first_course_bypass(user: dict, course: dict) -> None:
    """Mechanic a: first 500 first-enrollments platform-wide get a bypass code + email."""
    already = await db.course_entitlements.find_one(
        {"user_id": user["id"], "source": "first-course-bypass"}, {"_id": 1}
    )
    if already:
        return
    seq = await db.course_entitlements.count_documents({"source": "first-course-bypass"}) + 1
    if seq > BYPASS_CAP:
        return
    code = _code("FREE", 8)
    await db.course_entitlements.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "source": "first-course-bypass",
        "code": code,
        "seq": seq,
        "course_id": course["id"],
        "course_title": course["title"],
        "redeemed": True,  # applies automatically to this course
        "created_at": now_iso(),
    })
    logger.info(f"First-course bypass #{seq}/{BYPASS_CAP} issued to {user['email']} ({code})")
    try:
        from email_service import send_first_course_bypass_email
        await send_first_course_bypass_email(user["email"], user.get("full_name") or "", code, course["title"], seq)
    except Exception:
        logger.exception("bypass email failed (non-fatal)")


async def _convert_referral(user: dict, course: dict) -> None:
    """Mechanic b: lock referred user's free course, mark converted, reward referrer + email."""
    signup = await db.referral_signups.find_one({"referred_id": user["id"], "converted": False})
    if not signup:
        return
    await db.referral_signups.update_one(
        {"id": signup["id"]},
        {"$set": {"converted": True, "converted_course_id": course["id"], "converted_at": now_iso()}},
    )
    # lock the referred user's free first course to this course
    await db.course_entitlements.update_one(
        {"user_id": user["id"], "source": "referred-first-course", "course_id": None},
        {"$set": {"course_id": course["id"], "course_title": course["title"], "redeemed": True}},
    )
    rewards = await db.course_entitlements.count_documents(
        {"user_id": signup["referrer_id"], "source": "referral-reward"}
    )
    if rewards >= REFERRAL_MAX_USES:
        return
    await db.course_entitlements.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": signup["referrer_id"],
        "source": "referral-reward",
        "code": None,
        "course_id": None,  # course of choice, redeemed later
        "course_title": None,
        "redeemed": False,
        "created_at": now_iso(),
    })
    referrer = await db.users.find_one({"id": signup["referrer_id"]}, {"_id": 0, "email": 1, "full_name": 1})
    logger.info(f"Referral converted: {user['email']} → reward #{rewards + 1} for referrer {signup['referrer_id'][:8]}…")
    if referrer:
        try:
            from email_service import send_referral_reward_email
            await send_referral_reward_email(
                referrer["email"], referrer.get("full_name") or "",
                user.get("full_name") or user["email"], rewards + 1,
            )
        except Exception:
            logger.exception("referral reward email failed (non-fatal)")


async def handle_first_enrollment(user_id: str, course: dict) -> None:
    """Fire-and-forget hook called after a NEW enrollment is created.

    a) First-course bypass: if this is the user's first enrollment and the
       global 500-cap isn't exhausted, issue a unique bypass code + email it.
    b) Referral conversion: lock the referred user's free-course entitlement
       to this course, mark converted, reward the referrer (max 5) + email.
    """
    enrollment_count = await db.enrollments.count_documents({"user_id": user_id})
    if enrollment_count != 1:
        return  # only their first course triggers either mechanic
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "email": 1, "full_name": 1})
    if not user:
        return
    await _issue_first_course_bypass(user, course)
    await _convert_referral(user, course)


async def get_summary(user_id: str, share_base: str) -> dict:
    code = await ensure_personal_code(user_id)
    signups = await db.referral_signups.find(
        {"referrer_id": user_id}, {"_id": 0, "referred_email": 1, "converted": 1, "created_at": 1}
    ).to_list(REFERRAL_MAX_USES)
    entitlements = await db.course_entitlements.find(
        {"user_id": user_id}, {"_id": 0}
    ).to_list(20)
    bypass = next((e for e in entitlements if e["source"] == "first-course-bypass"), None)
    referred_free = next((e for e in entitlements if e["source"] == "referred-first-course"), None)
    rewards = [e for e in entitlements if e["source"] == "referral-reward"]
    return {
        "code": code,
        "share_url": f"{share_base}/register?ref={code}" if share_base else code,
        "max_uses": REFERRAL_MAX_USES,
        "signups": signups,
        "converted_count": sum(1 for s in signups if s["converted"]),
        "rewards_available": sum(1 for e in rewards if not e["redeemed"]),
        "rewards_redeemed": [
            {"course_title": e.get("course_title"), "course_id": e.get("course_id")}
            for e in rewards if e["redeemed"]
        ],
        "bypass": bypass,
        "referred_free_course": referred_free,
    }


async def redeem_reward(user_id: str, course: dict) -> dict:
    """Spend one referral-reward credit on a course of choice (enrolls the user)."""
    ent = await db.course_entitlements.find_one(
        {"user_id": user_id, "source": "referral-reward", "redeemed": False}, {"_id": 0, "id": 1}
    )
    if not ent:
        return {"ok": False, "reason": "No reward credits available"}
    await db.course_entitlements.update_one(
        {"id": ent["id"]},
        {"$set": {"redeemed": True, "course_id": course["id"], "course_title": course["title"]}},
    )
    return {"ok": True, "entitlement_id": ent["id"]}
