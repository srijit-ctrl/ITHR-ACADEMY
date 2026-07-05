"""Enterprise Portal: organization management, team invites, team dashboards."""
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_user_id
from core import db, gen_invite_code, logger, now_iso
from models_ext import InviteAcceptRequest, OrganizationCreate

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "organization"


async def _resolve_org_for_user(user_id: str, require_admin: bool = False):
    member = await db.org_members.find_one({"user_id": user_id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="You are not part of an organization")
    if require_admin and member["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin role required")
    org = await db.organizations.find_one({"id": member["org_id"]}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org, member


# -------------------- Organization CRUD --------------------
@router.post("/organizations")
async def create_organization(payload: OrganizationCreate, user_id: str = Depends(get_current_user_id)):
    existing_member = await db.org_members.find_one({"user_id": user_id})
    if existing_member:
        raise HTTPException(status_code=400, detail="You already belong to an organization")

    # unique slug
    base_slug = _slugify(payload.name)
    slug = base_slug
    counter = 1
    while await db.organizations.find_one({"slug": slug}):
        counter += 1
        slug = f"{base_slug}-{counter}"

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from models_ext import Organization
    org_obj = Organization(
        name=payload.name.strip(),
        slug=slug,
        industry=payload.industry,
        domain=payload.domain,
        seat_count=max(10, min(5000, payload.seat_count)),
        seats_used=1,
        owner_user_id=user_id,
        invite_code=gen_invite_code(),
    )
    org_doc = org_obj.model_dump()
    await db.organizations.insert_one(org_doc)
    org_doc.pop("_id", None)  # strip inserted _id if present

    # owner as first member
    member_doc = {
        "id": uuid.uuid4().hex,
        "org_id": org_doc["id"],
        "user_id": user_id,
        "email": user["email"],
        "full_name": user["full_name"],
        "role": "owner",
        "department": user.get("title"),
        "joined_at": now_iso(),
    }
    await db.org_members.insert_one(member_doc)
    member_doc.pop("_id", None)

    await db.users.update_one({"id": user_id}, {"$set": {"organization": payload.name.strip(), "org_id": org_doc["id"]}})
    return {"organization": org_doc}


@router.get("/organizations/mine")
async def my_organization(user_id: str = Depends(get_current_user_id)):
    org, member = await _resolve_org_for_user(user_id)
    return {"organization": org, "membership": member}


# -------------------- Invites --------------------
@router.post("/organizations/invites")
async def create_invite(payload: dict, user_id: str = Depends(get_current_user_id)):
    org, _member = await _resolve_org_for_user(user_id, require_admin=True)
    email = (payload.get("email") or "").lower().strip()
    role = payload.get("role", "member")
    department = payload.get("department")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="valid email required")

    if org.get("seats_used", 0) >= org.get("seat_count", 25):
        raise HTTPException(status_code=400, detail="No seats available. Purchase more seats first.")

    invite = {
        "id": uuid.uuid4().hex,
        "org_id": org["id"],
        "email": email,
        "role": role if role in ("admin", "member") else "member",
        "department": department,
        "invited_by": user_id,
        "status": "pending",
        "created_at": now_iso(),
        "invite_code": org["invite_code"],  # attached for convenience
    }
    await db.org_invites.insert_one(invite)
    invite.pop("_id", None)
    return {"invite": invite, "invite_url": f"/enterprise/join?code={org['invite_code']}&email={email}"}


@router.get("/organizations/invites")
async def list_invites(user_id: str = Depends(get_current_user_id)):
    org, _ = await _resolve_org_for_user(user_id, require_admin=True)
    invites = await db.org_invites.find({"org_id": org["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"invites": invites}


@router.post("/organizations/join")
async def accept_invite(payload: InviteAcceptRequest, user_id: str = Depends(get_current_user_id)):
    existing_member = await db.org_members.find_one({"user_id": user_id})
    if existing_member:
        raise HTTPException(status_code=400, detail="You already belong to an organization")

    org = await db.organizations.find_one({"invite_code": payload.invite_code}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Invalid invite code")

    if org.get("seats_used", 0) >= org.get("seat_count", 25):
        raise HTTPException(status_code=400, detail="Organization has no available seats")

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    invite = await db.org_invites.find_one({"org_id": org["id"], "email": user["email"], "status": "pending"}, {"_id": 0})
    role = invite["role"] if invite else "member"
    department = invite.get("department") if invite else None

    member_doc = {
        "id": uuid.uuid4().hex,
        "org_id": org["id"], "user_id": user_id,
        "email": user["email"], "full_name": user["full_name"],
        "role": role, "department": department,
        "joined_at": now_iso(),
    }
    await db.org_members.insert_one(member_doc)
    member_doc.pop("_id", None)
    await db.organizations.update_one({"id": org["id"]}, {"$inc": {"seats_used": 1}})
    if invite:
        await db.org_invites.update_one({"id": invite["id"]}, {"$set": {"status": "accepted", "accepted_at": now_iso(), "user_id": user_id}})
    await db.users.update_one({"id": user_id}, {"$set": {"organization": org["name"], "org_id": org["id"]}})
    return {"membership": member_doc, "organization": org}


def _aggregate_per_user_stats(
    member_user_ids: list[str],
    enrollments: list[dict],
    certificates: list[dict],
) -> dict[str, dict]:
    per_user = {
        uid: {"enrollments": 0, "completed": 0, "certificates": 0, "avg_progress": 0.0, "progress_sum": 0.0}
        for uid in member_user_ids
    }
    for e in enrollments:
        p = per_user.get(e["user_id"])
        if not p:
            continue
        p["enrollments"] += 1
        p["progress_sum"] += e.get("progress_pct", 0.0)
        if e.get("completed"):
            p["completed"] += 1
    for c in certificates:
        p = per_user.get(c["user_id"])
        if p:
            p["certificates"] += 1
    for _uid, p in per_user.items():
        p["avg_progress"] = round(p["progress_sum"] / p["enrollments"], 1) if p["enrollments"] else 0.0
        p.pop("progress_sum")
    return per_user


def _build_department_breakdown(members: list[dict], per_user: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Return (enriched_members_with_stats, sorted_department_stats)."""
    dept_stats: dict[str, dict] = {}
    enriched_members = []
    for m in members:
        stats = per_user.get(m["user_id"], {"enrollments": 0, "completed": 0, "certificates": 0, "avg_progress": 0.0})
        enriched_members.append({**m, "stats": stats})
        dept = m.get("department") or "Unassigned"
        d = dept_stats.setdefault(dept, {"members": 0, "certificates": 0, "avg_progress_sum": 0.0})
        d["members"] += 1
        d["certificates"] += stats["certificates"]
        d["avg_progress_sum"] += stats["avg_progress"]
    departments = [
        {"name": name, "members": v["members"], "certificates": v["certificates"],
         "avg_progress": round(v["avg_progress_sum"] / v["members"], 1) if v["members"] else 0.0}
        for name, v in dept_stats.items()
    ]
    departments.sort(key=lambda d: -d["avg_progress"])
    return enriched_members, departments


async def _top_courses_by_enrollment(enrollments: list[dict], limit: int = 5) -> list[dict]:
    course_counts: dict[str, int] = {}
    for e in enrollments:
        course_counts[e["course_id"]] = course_counts.get(e["course_id"], 0) + 1
    top_ids = sorted(course_counts, key=lambda k: -course_counts[k])[:limit]
    if not top_ids:
        return []
    docs = await db.courses.find(
        {"id": {"$in": top_ids}},
        {"_id": 0, "id": 1, "title": 1, "slug": 1, "thumbnail_url": 1, "category": 1},
    ).to_list(20)
    top = [{**c, "enrolled_count": course_counts.get(c["id"], 0)} for c in docs]
    top.sort(key=lambda c: -c["enrolled_count"])
    return top


def _readiness_summary(per_user: dict[str, dict], seat_count: int, members_len: int, enrollments_len: int) -> dict:
    total_progress = sum(p["avg_progress"] for p in per_user.values())
    avg_progress = round(total_progress / len(per_user), 1) if per_user else 0.0
    cert_coverage = round(sum(1 for p in per_user.values() if p["certificates"] > 0) / len(per_user) * 100, 1) if per_user else 0.0
    readiness_index = round((avg_progress * 0.5) + (cert_coverage * 0.5), 1)
    return {
        "seat_count": seat_count,
        "seats_used": members_len,
        "seats_remaining": max(0, seat_count - members_len),
        "total_enrollments": enrollments_len,
        "total_completed": sum(p["completed"] for p in per_user.values()),
        "total_certificates": sum(p["certificates"] for p in per_user.values()),
        "avg_progress": avg_progress,
        "cert_coverage_pct": cert_coverage,
        "readiness_index": readiness_index,
    }


# -------------------- Team Analytics Dashboard --------------------
@router.get("/organizations/dashboard")
async def team_dashboard(user_id: str = Depends(get_current_user_id)):
    org, member = await _resolve_org_for_user(user_id)
    members = await db.org_members.find({"org_id": org["id"]}, {"_id": 0}).to_list(500)
    member_user_ids = [m["user_id"] for m in members]

    enrollments = await db.enrollments.find({"user_id": {"$in": member_user_ids}}, {"_id": 0}).to_list(5000)
    certificates = await db.certificates.find({"user_id": {"$in": member_user_ids}}, {"_id": 0}).to_list(5000)

    per_user = _aggregate_per_user_stats(member_user_ids, enrollments, certificates)
    enriched_members, departments = _build_department_breakdown(members, per_user)
    top_courses = await _top_courses_by_enrollment(enrollments)
    summary = _readiness_summary(
        per_user,
        seat_count=org.get("seat_count", 25),
        members_len=len(members),
        enrollments_len=len(enrollments),
    )

    return {
        "organization": org,
        "membership": member,
        "summary": summary,
        "members": enriched_members,
        "departments": departments,
        "top_courses": top_courses,
    }


# -------------------- Seat management --------------------
SEAT_PRICE_PER_MONTH = 18.00


@router.post("/organizations/seats/preview")
async def preview_seats(payload: dict, user_id: str = Depends(get_current_user_id)):
    """Preview financial impact of a seat change before checkout."""
    org, member = await _resolve_org_for_user(user_id, require_admin=True)
    new_count = int(payload.get("seat_count", 0))
    current = org.get("seat_count", 25)
    delta = new_count - current
    result = {
        "current_seat_count": current,
        "new_seat_count": new_count,
        "delta": delta,
        "unit_price_monthly": SEAT_PRICE_PER_MONTH,
    }
    if delta > 0:
        result["charge_now"] = round(delta * SEAT_PRICE_PER_MONTH, 2)
        result["action"] = "checkout"
        result["message"] = f"Adding {delta} seats: ${result['charge_now']:.2f}/month starting now (prorated on renewal)."
    elif delta < 0:
        result["credit_note"] = round(abs(delta) * SEAT_PRICE_PER_MONTH, 2)
        result["action"] = "credit"
        result["message"] = f"Removing {abs(delta)} seats: a prorated credit of up to ${result['credit_note']:.2f} will apply on next renewal."
    else:
        result["action"] = "noop"
        result["message"] = "No change."
    return result


@router.post("/organizations/seats")
async def update_seats(payload: dict, request: Request, user_id: str = Depends(get_current_user_id)):
    """Adjust seat count (owner only).

    Owner-side flow:
      - INCREASE: returns a Stripe Checkout URL for the incremental cost.
        Seats are NOT bumped until webhook / status check flags the txn paid.
      - DECREASE: seat_count is set immediately, prorated credit line noted.
      - NOOP: returns unchanged.
    """
    org, member = await _resolve_org_for_user(user_id, require_admin=True)
    if member["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only the owner may adjust seats")

    new_count = int(payload.get("seat_count", 0))
    origin_url = (payload.get("origin_url") or "").rstrip("/")
    if new_count < org.get("seats_used", 0):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reduce below current usage ({org.get('seats_used', 0)} seats used)",
        )
    if new_count > 5000:
        raise HTTPException(status_code=400, detail="Contact ITHR sales for >5000 seats")
    if new_count < 10:
        raise HTTPException(status_code=400, detail="Team plans require minimum 10 seats")

    current = org.get("seat_count", 25)
    delta = new_count - current

    # DECREASE — apply immediately + record prorated credit line
    if delta < 0:
        credit_amount = round(abs(delta) * SEAT_PRICE_PER_MONTH, 2)
        await db.organizations.update_one({"id": org["id"]}, {"$set": {"seat_count": new_count}})
        credit_doc = {
            "id": uuid.uuid4().hex,
            "org_id": org["id"],
            "type": "prorated_credit",
            "seats_removed": abs(delta),
            "amount": credit_amount,
            "currency": "usd",
            "note": f"Prorated credit for removing {abs(delta)} seats.",
            "created_by": user_id,
            "created_at": now_iso(),
        }
        await db.org_billing_events.insert_one(credit_doc)
        credit_doc.pop("_id", None)
        org["seat_count"] = new_count
        return {
            "organization": org,
            "action": "credit",
            "message": f"Seat count reduced to {new_count}. Prorated credit of ${credit_amount:.2f} will apply on next renewal.",
            "credit_note": credit_doc,
        }

    if delta == 0:
        return {"organization": org, "action": "noop", "message": "No change."}

    # INCREASE — create a Stripe checkout for the incremental amount
    if not origin_url:
        raise HTTPException(status_code=400, detail="origin_url required for seat increases")

    from core import get_stripe
    from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest

    amount = round(delta * SEAT_PRICE_PER_MONTH, 2)
    success_url = f"{origin_url}/enterprise/portal?seats_added={delta}&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/enterprise/portal"
    metadata = {
        "user_id": user_id,
        "org_id": org["id"],
        "package_id": "team_seat_increment",
        "seats_delta": str(delta),
        "target_seat_count": str(new_count),
        "type": "seat_increment",
    }
    stripe = get_stripe(request)
    try:
        session = await stripe.create_checkout_session(
            CheckoutSessionRequest(
                amount=amount, currency="usd",
                success_url=success_url, cancel_url=cancel_url,
                metadata=metadata,
            )
        )
    except Exception as e:
        logger.exception("Stripe seat-increment session failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    # Track the pending seat purchase so status webhook can fulfill it
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "user_id": user_id,
        "org_id": org["id"],
        "type": "seat_increment",
        "package_id": "team_seat_increment",
        "seats_delta": delta,
        "target_seat_count": new_count,
        "amount": amount, "currency": "usd",
        "payment_status": "initiated", "status": "pending",
        "metadata": metadata,
        "created_at": now_iso(),
    })

    return {
        "organization": org,
        "action": "checkout",
        "checkout_url": session.url,
        "session_id": session.session_id,
        "amount": amount,
        "seats_delta": delta,
        "message": f"Complete checkout to add {delta} seats (${amount:.2f}/month).",
    }


@router.post("/organizations/seats/fulfill/{session_id}")
async def fulfill_seat_increment(session_id: str, request: Request, user_id: str = Depends(get_current_user_id)):
    """Called by the client on redirect back to portal — verifies checkout and bumps seat count."""
    org, member = await _resolve_org_for_user(user_id, require_admin=True)
    if member["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only the owner may fulfill seat purchases")

    txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not txn or txn.get("type") != "seat_increment":
        raise HTTPException(status_code=404, detail="Seat increment transaction not found")
    if txn.get("org_id") != org["id"]:
        raise HTTPException(status_code=403, detail="This transaction does not belong to your org")

    if txn.get("payment_status") == "paid" and txn.get("fulfilled_at"):
        return {"already_fulfilled": True, "seat_count": org.get("seat_count")}

    from core import get_stripe
    stripe = get_stripe(request)
    try:
        status_resp = await stripe.get_checkout_status(session_id)
    except Exception as e:
        logger.exception("Stripe seat-increment status failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    updates = {"payment_status": status_resp.payment_status, "status": status_resp.status, "updated_at": now_iso()}
    if status_resp.payment_status == "paid":
        new_count = int(txn["target_seat_count"])
        await db.organizations.update_one({"id": org["id"]}, {"$set": {"seat_count": new_count}})
        await db.org_billing_events.insert_one({
            "id": uuid.uuid4().hex,
            "org_id": org["id"],
            "type": "seat_increment_paid",
            "seats_added": int(txn["seats_delta"]),
            "amount": txn["amount"],
            "currency": txn["currency"],
            "session_id": session_id,
            "created_at": now_iso(),
        })
        updates["fulfilled_at"] = now_iso()
        org["seat_count"] = new_count

    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": updates})
    return {
        "fulfilled": status_resp.payment_status == "paid",
        "payment_status": status_resp.payment_status,
        "seat_count": org.get("seat_count"),
    }


@router.get("/organizations/billing")
async def list_billing_events(user_id: str = Depends(get_current_user_id)):
    org, _ = await _resolve_org_for_user(user_id, require_admin=True)
    events = await db.org_billing_events.find(
        {"org_id": org["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"events": events}


@router.delete("/organizations/members/{member_id}")
async def remove_member(member_id: str, user_id: str = Depends(get_current_user_id)):
    org, _member = await _resolve_org_for_user(user_id, require_admin=True)
    target = await db.org_members.find_one({"id": member_id, "org_id": org["id"]}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target["role"] == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    await db.org_members.delete_one({"id": member_id})
    await db.organizations.update_one({"id": org["id"]}, {"$inc": {"seats_used": -1}})
    await db.users.update_one({"id": target["user_id"]}, {"$set": {"organization": None, "org_id": None}})
    return {"removed": True, "member_id": member_id}
