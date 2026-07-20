"""Super-Admin email-campaign endpoints (Iteration 57).

All endpoints are super-admin-only. See `campaign_service.py` for the
business logic and DB schema.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from auth import get_current_super_admin
from campaign_service import (
    dispatch_manual_campaign,
    list_campaign_history,
    preview_campaign_recipients,
    run_reengagement_sweep,
)
from core import db

router = APIRouter(prefix="/api/admin/campaigns", tags=["admin-campaigns"])


class CampaignFilter(BaseModel):
    segment: str = Field(default="all_learners")  # all_learners | role | by_course | founding_only
    role: Optional[str] = None
    course_slug: Optional[str] = None


class CampaignPreviewRequest(BaseModel):
    filter: CampaignFilter = CampaignFilter()


class CampaignSendRequest(BaseModel):
    subject: str
    body_markdown: str
    filter: CampaignFilter = CampaignFilter()
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None


class CampaignTestSendRequest(BaseModel):
    subject: str
    body_markdown: str
    test_recipient: str
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None


@router.post("/preview")
async def campaign_preview(
    payload: CampaignPreviewRequest,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Return recipient count + first 5 emails for the composer preview panel."""
    return await preview_campaign_recipients(payload.filter.model_dump())


@router.post("/send")
async def campaign_send(
    payload: CampaignSendRequest,
    super_admin_id: str = Depends(get_current_super_admin),
):
    admin_doc = await db.users.find_one({"id": super_admin_id}, {"_id": 0, "email": 1}) or {}
    result = await dispatch_manual_campaign(
        sent_by_admin_id=super_admin_id,
        sent_by_email=admin_doc.get("email") or "",
        subject=payload.subject,
        body_markdown=payload.body_markdown,
        filter_spec=payload.filter.model_dump(),
        cta_label=payload.cta_label,
        cta_url=payload.cta_url,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Campaign send failed"))
    return result


@router.post("/test-send")
async def campaign_test_send(
    payload: CampaignTestSendRequest,
    super_admin_id: str = Depends(get_current_super_admin),
):
    """Send the composed body to a single QA address without logging a campaign."""
    admin_doc = await db.users.find_one({"id": super_admin_id}, {"_id": 0, "email": 1}) or {}
    result = await dispatch_manual_campaign(
        sent_by_admin_id=super_admin_id,
        sent_by_email=admin_doc.get("email") or "",
        subject=payload.subject,
        body_markdown=payload.body_markdown,
        filter_spec={},
        cta_label=payload.cta_label,
        cta_url=payload.cta_url,
        test_recipient=payload.test_recipient,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Test send failed"))
    return result


@router.get("/history")
async def campaign_history(
    limit: int = 50,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Most-recent campaigns first (newest at index 0)."""
    return {"campaigns": await list_campaign_history(limit=limit)}


@router.post("/reengagement/run")
async def reengagement_run(
    dry_run: bool = False,
    _super_admin_id: str = Depends(get_current_super_admin),
):
    """Kick the 7-day re-engagement sweep. `dry_run=true` returns eligible
    counts + up to 10 sample emails without dispatching anything."""
    return await run_reengagement_sweep(dry_run=dry_run)
