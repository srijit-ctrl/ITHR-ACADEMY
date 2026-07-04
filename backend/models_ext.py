"""Additional Pydantic models for Enterprise Portal + Curriculum patches."""
from __future__ import annotations

import uuid
from typing import List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field

from models import now_iso, gen_id


# -------------------- Organizations --------------------
class OrganizationCreate(BaseModel):
    name: str
    industry: Optional[str] = None
    seat_count: int = 25
    domain: Optional[str] = None  # email domain like "acme.com"


class Organization(BaseModel):
    id: str = Field(default_factory=gen_id)
    name: str
    slug: str
    industry: Optional[str] = None
    domain: Optional[str] = None
    seat_count: int = 25
    seats_used: int = 0
    owner_user_id: str
    subscription_tier: str = "team"
    created_at: str = Field(default_factory=now_iso)
    invite_code: str


class OrgMember(BaseModel):
    id: str = Field(default_factory=gen_id)
    org_id: str
    user_id: str
    email: str
    full_name: str
    role: Literal["owner", "admin", "member"] = "member"
    department: Optional[str] = None
    joined_at: str = Field(default_factory=now_iso)


class OrgInvite(BaseModel):
    id: str = Field(default_factory=gen_id)
    org_id: str
    email: EmailStr
    role: Literal["admin", "member"] = "member"
    department: Optional[str] = None
    invited_by: str
    status: Literal["pending", "accepted", "expired"] = "pending"
    created_at: str = Field(default_factory=now_iso)


class InviteAcceptRequest(BaseModel):
    invite_code: str


# -------------------- Curriculum Patches --------------------
class CurriculumPatch(BaseModel):
    id: str = Field(default_factory=gen_id)
    course_slug: str
    signal_id: str
    signal_title: str
    module_number: Optional[int] = None
    module_title: Optional[str] = None
    patch_type: Literal["module_add", "module_update", "lesson_add", "note"] = "module_update"
    proposed_content: str  # markdown content
    rationale: str
    status: Literal["proposed", "approved", "applied", "rejected"] = "proposed"
    created_by: str  # user_id
    created_at: str = Field(default_factory=now_iso)
    reviewed_at: Optional[str] = None
