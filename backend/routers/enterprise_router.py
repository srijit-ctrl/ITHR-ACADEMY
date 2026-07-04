"""Enterprise Portal: organization management, team invites, team dashboards."""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

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
        "id": __import__("uuid").uuid4().hex,
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
        "id": __import__("uuid").uuid4().hex,
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
        "id": __import__("uuid").uuid4().hex,
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


# -------------------- Team Analytics Dashboard --------------------
@router.get("/organizations/dashboard")
async def team_dashboard(user_id: str = Depends(get_current_user_id)):
    org, member = await _resolve_org_for_user(user_id)

    members = await db.org_members.find({"org_id": org["id"]}, {"_id": 0}).to_list(500)
    member_user_ids = [m["user_id"] for m in members]

    # Aggregate stats per user
    enrollments = await db.enrollments.find({"user_id": {"$in": member_user_ids}}, {"_id": 0}).to_list(5000)
    certificates = await db.certificates.find({"user_id": {"$in": member_user_ids}}, {"_id": 0}).to_list(5000)

    per_user = {uid: {"enrollments": 0, "completed": 0, "certificates": 0, "avg_progress": 0.0, "progress_sum": 0.0} for uid in member_user_ids}
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
    for uid, p in per_user.items():
        p["avg_progress"] = round(p["progress_sum"] / p["enrollments"], 1) if p["enrollments"] else 0.0
        p.pop("progress_sum")

    # Department breakdown
    dept_stats = {}
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

    # Top courses by enrollment across the org
    course_counts = {}
    for e in enrollments:
        course_counts[e["course_id"]] = course_counts.get(e["course_id"], 0) + 1
    top_course_ids = sorted(course_counts, key=lambda k: -course_counts[k])[:5]
    top_courses_docs = await db.courses.find({"id": {"$in": top_course_ids}}, {"_id": 0, "id": 1, "title": 1, "slug": 1, "thumbnail_url": 1, "category": 1}).to_list(20)
    top_courses = []
    for c in top_courses_docs:
        top_courses.append({**c, "enrolled_count": course_counts.get(c["id"], 0)})
    top_courses.sort(key=lambda c: -c["enrolled_count"])

    # Overall readiness score (weighted: 50% avg progress + 50% cert coverage)
    total_progress = sum(p["avg_progress"] for p in per_user.values())
    avg_progress = round(total_progress / len(per_user), 1) if per_user else 0.0
    cert_coverage = round(sum(1 for p in per_user.values() if p["certificates"] > 0) / len(per_user) * 100, 1) if per_user else 0.0
    readiness_index = round((avg_progress * 0.5) + (cert_coverage * 0.5), 1)

    return {
        "organization": org,
        "membership": member,
        "summary": {
            "seat_count": org.get("seat_count", 25),
            "seats_used": len(members),
            "seats_remaining": max(0, org.get("seat_count", 25) - len(members)),
            "total_enrollments": len(enrollments),
            "total_completed": sum(p["completed"] for p in per_user.values()),
            "total_certificates": sum(p["certificates"] for p in per_user.values()),
            "avg_progress": avg_progress,
            "cert_coverage_pct": cert_coverage,
            "readiness_index": readiness_index,
        },
        "members": enriched_members,
        "departments": departments,
        "top_courses": top_courses,
    }


# -------------------- Seat management --------------------
@router.post("/organizations/seats")
async def update_seats(payload: dict, user_id: str = Depends(get_current_user_id)):
    """Adjust seat count (owner only). In production this would trigger a Stripe subscription update."""
    org, member = await _resolve_org_for_user(user_id, require_admin=True)
    if member["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only the owner may adjust seats")

    new_count = int(payload.get("seat_count", 0))
    if new_count < org.get("seats_used", 0):
        raise HTTPException(status_code=400, detail=f"Cannot reduce below current usage ({org.get('seats_used', 0)} seats used)")
    if new_count > 5000:
        raise HTTPException(status_code=400, detail="Contact ITHR sales for >5000 seats")
    if new_count < 10:
        raise HTTPException(status_code=400, detail="Team plans require minimum 10 seats")

    await db.organizations.update_one({"id": org["id"]}, {"$set": {"seat_count": new_count}})
    org["seat_count"] = new_count
    return {"organization": org, "message": f"Seat count updated to {new_count}"}


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
