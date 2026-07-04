"""Role-based learning paths.

Curated, role-first tracks so learners don't have to navigate a 24-course catalog
to figure out what matters for them. Each path is a *sequence* of course slugs
with an intent, a target credential, and an expected duration.

Endpoints:
- GET /api/paths                        list role-based tracks
- GET /api/paths/{slug}                 single track w/ resolved course cards
- POST /api/paths/{slug}/enroll         enroll the user in every course in the path
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user_id
from core import db, now_iso

router = APIRouter(prefix="/api", tags=["paths"])


def _gen_id() -> str:
    return uuid.uuid4().hex


ROLE_PATHS = [
    {
        "slug": "product-manager-ai",
        "role": "Product Manager",
        "title": "AI-Native Product Manager",
        "subtitle": "From backlog to bar-raising: ship durable AI features that scale.",
        "target_credential": "Agentic AI Practitioner + AI PM",
        "estimated_weeks": 10,
        "audience": "PMs, PgMs, and TPMs shipping AI-powered products.",
        "outcomes": [
            "Author eval-driven PRDs for AI features",
            "Run structured discovery on data & failure modes",
            "Own AI feature rollout with guardrails, telemetry, and cost governance",
        ],
        "course_slugs": [
            "agentic-ai-foundations",
            "prompt-engineering-mastery",
            "ai-product-management",
            "rag-enterprise",
            "ai-governance-compliance",
        ],
    },
    {
        "slug": "engineer-agentic",
        "role": "Software / AI Engineer",
        "title": "Agentic Engineer",
        "subtitle": "Build production agents: RAG, multi-agent, MCP/A2A, security, and MLOps.",
        "target_credential": "Agentic AI Professional",
        "estimated_weeks": 14,
        "audience": "Senior engineers pivoting into agent-native systems.",
        "outcomes": [
            "Design multi-agent systems with reliability + cost budgets",
            "Ship RAG that survives real corpora",
            "Instrument LLM apps with evals, traces, and rollbacks",
        ],
        "course_slugs": [
            "prompt-engineering-mastery",
            "rag-enterprise",
            "multi-agent-systems",
            "mcp-a2a-protocols",
            "vector-databases",
            "ai-security-red-team",
            "ai-devops-mlops",
        ],
    },
    {
        "slug": "risk-compliance-officer",
        "role": "Risk / Compliance Officer",
        "title": "AI Governance & Compliance",
        "subtitle": "Own AI risk end-to-end: EU AI Act, NIST AI RMF, ISO 42001, sector rules.",
        "target_credential": "AI Governance Specialist",
        "estimated_weeks": 8,
        "audience": "Legal, risk, compliance, audit, and ethics-committee members.",
        "outcomes": [
            "Map obligations across EU AI Act, NIST AI RMF, ISO 42001",
            "Stand up model risk management aligned to SR 11-7 / regulator expectations",
            "Operationalize responsible-AI charters into review workflows",
        ],
        "course_slugs": [
            "agentic-ai-foundations",
            "ai-governance-compliance",
            "responsible-ai",
            "ai-security-red-team",
        ],
    },
    {
        "slug": "hr-people-leader",
        "role": "HR / People Leader",
        "title": "AI-Ready People Leader",
        "subtitle": "Reskill your workforce and change the operating rhythm — not just the tools.",
        "target_credential": "AI Change Champion",
        "estimated_weeks": 6,
        "audience": "CHROs, L&D leads, workforce planners, DEI leaders.",
        "outcomes": [
            "Design role-based reskilling programs with real behaviour change",
            "Set fair-use policy for AI in HR (hiring, evaluation, promotions)",
            "Report on transformation health metrics to the board",
        ],
        "course_slugs": [
            "agentic-ai-foundations",
            "ai-change-management",
            "generative-ai-executives",
            "responsible-ai",
        ],
    },
    {
        "slug": "banking-officer",
        "role": "Banking / Financial Services",
        "title": "AI for Banking & Financial Services",
        "subtitle": "Deploy safely across SR 11-7, ECOA, PCI, and OCC guidance.",
        "target_credential": "Agentic AI Specialist — Banking",
        "estimated_weeks": 9,
        "audience": "Retail bankers, credit officers, AML/compliance, product owners.",
        "outcomes": [
            "Understand model risk management for LLM-powered banking agents",
            "Ship fair-lending-ready credit decisioning workflows",
            "Instrument AML/KYC automation with human-in-the-loop",
        ],
        "course_slugs": [
            "agentic-ai-foundations",
            "agentic-ai-banking",
            "ai-governance-compliance",
            "rag-enterprise",
        ],
    },
    {
        "slug": "healthcare-clinician",
        "role": "Healthcare / Life Sciences",
        "title": "AI in Regulated Healthcare",
        "subtitle": "PHI-safe agentic workflows for clinical, ops, and research teams.",
        "target_credential": "Agentic AI Specialist — Healthcare",
        "estimated_weeks": 9,
        "audience": "Health-system CIOs, clinician informaticists, MedTech PMs.",
        "outcomes": [
            "Deploy HIPAA-safe agent pipelines for clinical and admin work",
            "Navigate FDA SaMD & Predetermined Change Control Plans",
            "Instrument clinician-in-the-loop with explainability",
        ],
        "course_slugs": [
            "agentic-ai-foundations",
            "agentic-ai-healthcare",
            "ai-governance-compliance",
            "responsible-ai",
        ],
    },
    {
        "slug": "executive-cxo",
        "role": "Executive / C-suite",
        "title": "AI-Ready Executive",
        "subtitle": "Set strategy, govern risk, and lead the transformation — without becoming an engineer.",
        "target_credential": "Chief AI Officer Track",
        "estimated_weeks": 6,
        "audience": "CEO, COO, CIO, CFO, board members, business-unit heads.",
        "outcomes": [
            "Set an AI portfolio strategy with measurable outcomes",
            "Build governance without slowing product velocity",
            "Report AI value + risk to the board with credibility",
        ],
        "course_slugs": [
            "generative-ai-executives",
            "ai-governance-compliance",
            "ai-change-management",
            "chief-ai-officer-track",
        ],
    },
]


@router.get("/paths")
async def list_paths():
    return {
        "count": len(ROLE_PATHS),
        "paths": [
            {
                "slug": p["slug"],
                "role": p["role"],
                "title": p["title"],
                "subtitle": p["subtitle"],
                "target_credential": p["target_credential"],
                "estimated_weeks": p["estimated_weeks"],
                "course_count": len(p["course_slugs"]),
            }
            for p in ROLE_PATHS
        ],
    }


def _thin_course(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "slug": c.get("slug"),
        "title": c.get("title"),
        "subtitle": c.get("subtitle"),
        "category": c.get("category"),
        "difficulty": c.get("difficulty"),
        "duration_hours": c.get("duration_hours"),
        "thumbnail_url": c.get("thumbnail_url"),
        "has_full_content": c.get("has_full_content", False),
    }


@router.get("/paths/{slug}")
async def get_path(slug: str):
    path = next((p for p in ROLE_PATHS if p["slug"] == slug), None)
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
    courses = await db.courses.find({"slug": {"$in": path["course_slugs"]}}, {"_id": 0}).to_list(200)
    course_map = {c["slug"]: c for c in courses}
    ordered = [_thin_course(course_map[s]) for s in path["course_slugs"] if s in course_map]
    return {**path, "courses": ordered}


@router.post("/paths/{slug}/enroll")
async def enroll_path(slug: str, user_id: str = Depends(get_current_user_id)):
    path = next((p for p in ROLE_PATHS if p["slug"] == slug), None)
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
    courses = await db.courses.find(
        {"slug": {"$in": path["course_slugs"]}}, {"_id": 0, "id": 1, "slug": 1}
    ).to_list(200)
    enrolled = 0
    skipped = 0
    for c in courses:
        existing = await db.enrollments.find_one({"user_id": user_id, "course_id": c["id"]})
        if existing:
            skipped += 1
            continue
        doc = {
            "id": _gen_id(),
            "user_id": user_id,
            "course_id": c["id"],
            "enrolled_at": now_iso(),
            "progress_pct": 0.0,
            "completed_lessons": [],
            "completed": False,
        }
        await db.enrollments.insert_one(doc)
        enrolled += 1
    await db.users.update_one({"id": user_id}, {"$set": {"active_path": slug}})
    return {"path_slug": slug, "enrolled": enrolled, "already_enrolled": skipped, "total": len(courses)}
