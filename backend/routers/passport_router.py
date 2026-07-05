"""Public AI Skills Passport.

Portable, verifiable profile of a learner's ITHR credentials + AI competencies.
Accessible without authentication so it can be shared on LinkedIn, résumés, etc.

Endpoints:
- GET /api/passport/me                  (auth) my own passport slug + summary
- GET /api/passport/{slug}              (public) render passport by slug
"""
from __future__ import annotations

import re

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user_id
from core import db, now_iso

router = APIRouter(prefix="/api", tags=["passport"])


def _gen_id() -> str:
    return uuid.uuid4().hex


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:40] or "learner"


async def _ensure_passport_slug(user: dict) -> str:
    if user.get("passport_slug"):
        return user["passport_slug"]
    base = _slugify(user["full_name"])
    slug = base
    n = 1
    while await db.users.find_one({"passport_slug": slug}):
        n += 1
        slug = f"{base}-{n}"
    await db.users.update_one({"id": user["id"]}, {"$set": {"passport_slug": slug}})
    return slug


CATEGORY_TO_SKILLS = {
    "Foundations": ["Agent architectures", "Perceive-Reason-Act loops", "Memory hierarchies"],
    "Prompt Engineering": ["Structured prompting", "Chain-of-Thought", "Prompt evals"],
    "Retrieval-Augmented Generation": ["Hybrid retrieval", "Vector search", "Grounded generation"],
    "Multi-Agent Systems": ["Multi-agent orchestration", "A2A / MCP", "Supervisor patterns"],
    "Governance & Compliance": ["EU AI Act", "NIST AI RMF", "ISO 42001", "Model risk mgmt"],
    "Industry — Banking": ["SR 11-7 alignment", "Fair lending AI", "AML augmentation"],
    "Industry — Healthcare": ["HIPAA-safe pipelines", "FDA SaMD", "Clinical decision support"],
    "Industry — Manufacturing": ["OT/IT boundary", "Digital twins", "Functional safety"],
    "Industry — Retail": ["Personalization at scale", "Dynamic pricing", "Assortment optimization"],
    "Industry — Government": ["FedRAMP AI", "Section 508", "Fair public services"],
    "Industry — Hospitality": ["Guest personalization", "Distribution parity", "Revenue management"],
    "Strategy & Leadership": ["AI portfolio strategy", "Board-level AI reporting", "Change leadership"],
    "Executive Track": ["AI portfolio strategy", "Board-level AI reporting", "Change leadership"],
    "Product Management": ["Eval-driven PRDs", "Golden datasets", "Trust & guardrail design"],
    "AI Architecture": ["LLM gateway", "Reference architecture", "Multi-tenant AI"],
    "Vector Databases": ["ANN indexing", "Semantic routing", "Hybrid search"],
    "Fine-Tuning": ["LoRA/QLoRA", "DPO", "SFT tradeoffs"],
    "Security": ["Prompt injection defense", "Dual-LLM pattern", "AI red-teaming"],
    "MLOps for AI": ["Eval regressions", "Model registry", "Semantic caching"],
    "MCP & A2A": ["MCP tool exposure", "A2A skill discovery", "Agent interop"],
    "Observability": ["TTFT & tokens/sec SLIs", "LLM tracing", "LLM-as-judge"],
    "Change Management": ["Kotter for AI", "CoE design", "AI adoption metrics"],
    "Responsible AI": ["Fairness metrics", "Explainability", "Right-to-be-forgotten"],
    "Executive / C-suite": ["AI portfolio strategy", "Board-level AI reporting", "Change leadership"],
}


async def _fetch_course_map(course_ids: list[str]) -> dict[str, dict]:
    if not course_ids:
        return {}
    docs = await db.courses.find(
        {"id": {"$in": course_ids}},
        {"_id": 0, "id": 1, "slug": 1, "title": 1, "category": 1, "industries": 1, "difficulty": 1, "duration_hours": 1},
    ).to_list(200)
    return {c["id"]: c for c in docs}


def _skills_from_certs(certs: list[dict], course_map: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Return (sorted_skills, sorted_completed_categories) derived from cert list."""
    skills: set[str] = set()
    categories: set[str] = set()
    for cert in certs:
        c = course_map.get(cert["course_id"])
        if not c:
            continue
        cat = c.get("category") or ""
        categories.add(cat)
        skills.update(CATEGORY_TO_SKILLS.get(cat, []))
    return sorted(skills), sorted(categories)


def _credential_level_from_certs(certs: list[dict], course_map: dict[str, dict]) -> str:
    ladder = ["Beginner", "Intermediate", "Advanced", "Expert", "Architect", "Enterprise Leader", "CXO"]
    max_idx = -1
    for cert in certs:
        c = course_map.get(cert["course_id"])
        if not c:
            continue
        try:
            idx = ladder.index(c.get("difficulty", "Beginner"))
            if idx > max_idx:
                max_idx = idx
        except ValueError:
            continue
    return ladder[max_idx] if max_idx >= 0 else "Learner"


def _industry_footprint(certs: list[dict], course_map: dict[str, dict]) -> list[str]:
    inds: set[str] = set()
    for cert in certs:
        c = course_map.get(cert["course_id"])
        if c:
            inds.update(c.get("industries", []))
    return sorted(inds)


def _learning_hours(certs: list[dict], course_map: dict[str, dict]) -> int:
    total = 0
    for cert in certs:
        c = course_map.get(cert["course_id"])
        if c:
            total += c.get("duration_hours", 0) or 0
    return total


def _serialise_cert(cert: dict) -> Optional[dict]:
    if not cert or not cert.get("certificate_id") or not cert.get("course_title"):
        return None
    return {
        "certificate_id": cert["certificate_id"],
        "course_title": cert["course_title"],
        "score": cert.get("score"),
        "issued_at": cert.get("issued_at"),
        "verification_url": cert.get("verification_url"),
    }


async def _build_passport(user: dict) -> dict:
    user_id = user["id"]
    certs = await db.certificates.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("issued_at", -1).to_list(200)
    enrollments = await db.enrollments.find(
        {"user_id": user_id}, {"_id": 0}
    ).to_list(500)

    all_course_ids = list({e["course_id"] for e in enrollments} | {c["course_id"] for c in certs})
    course_map = await _fetch_course_map(all_course_ids)

    skills, categories = _skills_from_certs(certs, course_map)
    credential_level = _credential_level_from_certs(certs, course_map)
    industries = _industry_footprint(certs, course_map)
    hours = _learning_hours(certs, course_map)

    return {
        "passport_slug": user.get("passport_slug"),
        "full_name": user.get("full_name"),
        "title": user.get("title"),
        "organization": user.get("organization"),
        "credential_level": credential_level,
        "xp": user.get("xp", 0),
        "certificates": [c for c in (_serialise_cert(cert) for cert in certs) if c],
        "skills": skills,
        "categories": categories,
        "industries": industries,
        "learning_hours": hours,
        "generated_at": now_iso(),
    }


@router.get("/passport/me")
async def my_passport(user_id: str = Depends(get_current_user_id)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    slug = await _ensure_passport_slug(user)
    user["passport_slug"] = slug
    passport = await _build_passport(user)
    return passport


@router.get("/passport/{slug}")
async def public_passport(slug: str):
    """Public — no auth required, so passports can be linked from LinkedIn/CV."""
    user = await db.users.find_one({"passport_slug": slug}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Passport not found")
    return await _build_passport(user)
