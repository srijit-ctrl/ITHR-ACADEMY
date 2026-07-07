"""Pydantic models for Enterprise Agentic AI Academy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_id() -> str:
    return str(uuid.uuid4())


# -------------------- User --------------------
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    role: Optional[Literal["learner", "instructor", "admin", "corporate_admin"]] = "learner"
    organization: Optional[str] = None
    title: Optional[str] = None
    referral_code: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    organization: Optional[str] = None
    title: Optional[str] = None
    created_at: str
    avatar_url: Optional[str] = None
    xp: int = 0
    streak_days: int = 0
    # Founding-member perk (only populated for the first 500 users)
    founding_member_seq: Optional[int] = None
    signup_discount_code: Optional[str] = None
    founding_course_id: Optional[str] = None
    founding_cert_used: bool = False
    # Referral payment bypass (first 500 redemptions are marked Paid)
    payment_status: Optional[str] = None
    paid_via_referral: bool = False
    referral_seq: Optional[int] = None


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


# -------------------- Course --------------------
class Lesson(BaseModel):
    id: str = Field(default_factory=gen_id)
    title: str
    content: str  # markdown text
    duration_min: int = 10
    code_sample: Optional[str] = None
    key_takeaways: List[str] = []
    video_url: Optional[str] = None


class Module(BaseModel):
    id: str = Field(default_factory=gen_id)
    number: int
    title: str
    summary: str
    level: Literal[1, 2, 3]  # 1=free, 2=premium, 3=advanced
    duration_min: int = 45
    lessons: List[Lesson] = []


class QuizQuestion(BaseModel):
    id: str = Field(default_factory=gen_id)
    question: str
    type: Literal["mcq", "multi", "true_false", "scenario"] = "mcq"
    options: List[str]
    correct: List[int]  # indices of correct answers
    explanation: str = ""
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"


class Course(BaseModel):
    id: str = Field(default_factory=gen_id)
    slug: str
    title: str
    subtitle: str
    description: str
    category: str
    industries: List[str] = []
    difficulty: Literal["Fundamental", "Beginner", "Intermediate", "Advanced", "Expert", "Architect", "Enterprise Leader"] = "Beginner"
    duration_hours: int = 20
    thumbnail_url: str = ""
    hero_url: Optional[str] = None
    intro_video_url: Optional[str] = None  # Optional Sora-2 (or other) intro clip; falls back to Ken-Burns on thumbnail_url.
    instructor: str = "AI Academy Faculty"
    prerequisites: List[str] = []
    learning_objectives: List[str] = []
    skills_gained: List[str] = []
    business_value: str = ""
    is_certification_track: bool = True
    modules: List[Module] = []
    quiz: List[QuizQuestion] = []
    passing_score: int = 65
    enrolled_count: int = 0
    rating: float = 4.8
    created_at: str = Field(default_factory=now_iso)
    last_reviewed_at: Optional[str] = None
    freshness_score: int = 100
    days_since_review: int = 0


class CourseSummary(BaseModel):
    id: str
    slug: str
    title: str
    subtitle: str
    category: str
    industries: List[str]
    difficulty: str
    duration_hours: int
    thumbnail_url: str
    intro_video_url: Optional[str] = None
    instructor: str
    enrolled_count: int
    rating: float
    module_count: int
    has_full_content: bool = False
    last_reviewed_at: Optional[str] = None
    freshness_score: int = 100
    days_since_review: int = 0


# -------------------- Enrollment / Progress --------------------
class Enrollment(BaseModel):
    id: str = Field(default_factory=gen_id)
    user_id: str
    course_id: str
    enrolled_at: str = Field(default_factory=now_iso)
    completed_lessons: List[str] = []  # lesson ids
    completed_modules: List[str] = []  # module ids
    progress_pct: float = 0.0
    completed: bool = False
    completed_at: Optional[str] = None
    last_accessed: str = Field(default_factory=now_iso)


class LessonCompleteRequest(BaseModel):
    course_id: str
    lesson_id: str
    module_id: str


# -------------------- Quiz Attempts --------------------
class QuizSubmitRequest(BaseModel):
    course_id: str
    answers: dict  # {question_id: [selected_indices]}
    duration_seconds: int = 0


class QuizAttempt(BaseModel):
    id: str = Field(default_factory=gen_id)
    user_id: str
    course_id: str
    score: float  # 0-100
    passed: bool
    total_questions: int
    correct_count: int
    duration_seconds: int
    answers: dict
    attempted_at: str = Field(default_factory=now_iso)


# -------------------- Certificate --------------------
class Certificate(BaseModel):
    id: str = Field(default_factory=gen_id)
    certificate_id: str  # human-readable e.g. EAIA-2026-ABC123
    user_id: str
    user_name: str
    course_id: str
    course_title: str
    score: float
    issued_at: str = Field(default_factory=now_iso)
    valid_until: Optional[str] = None
    verification_url: str = ""


# -------------------- AI Tutor --------------------
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: str = Field(default_factory=now_iso)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    course_context: Optional[str] = None  # course id for context


class ChatSession(BaseModel):
    id: str = Field(default_factory=gen_id)
    user_id: str
    title: str = "New Conversation"
    messages: List[ChatMessage] = []
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
