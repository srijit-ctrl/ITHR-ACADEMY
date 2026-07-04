"""Email + webhook notification services.

- Resend for transactional email (weekly enterprise digests)
- Slack/Teams incoming webhooks for patch-approval notifications

Everything gracefully degrades: if RESEND_API_KEY is missing we log-and-store the
digest instead of failing hard, so the platform is testable without credentials.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("eaia.notifications")


async def send_email(
    *,
    to_email: str,
    subject: str,
    html: str,
    from_override: Optional[str] = None,
) -> dict:
    """Send a single HTML email via Resend.

    Returns {"delivered": bool, "id": str|None, "reason": str|None}.
    Never raises — callers can ignore return value if email is a bonus channel.
    """
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = from_override or os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

    if not api_key:
        logger.info(f"[email:MOCK] to={to_email} subject={subject!r} (no RESEND_API_KEY set)")
        return {"delivered": False, "id": None, "reason": "no_api_key"}

    try:
        import resend
        resend.api_key = api_key
        params = {
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        # Resend SDK is sync — run in a thread to keep the event loop free
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"delivered": True, "id": (result or {}).get("id"), "reason": None}
    except Exception as e:
        logger.exception(f"Resend send failed for {to_email}")
        return {"delivered": False, "id": None, "reason": str(e)[:200]}


async def send_slack_webhook(url: str, text: str, blocks: Optional[list] = None) -> bool:
    """POST a message to a Slack incoming webhook. Returns True on success."""
    if not url:
        return False
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(url, json=payload)
            return 200 <= r.status_code < 300
    except Exception:
        logger.exception("Slack webhook failed")
        return False


async def send_teams_webhook(url: str, title: str, text: str, facts: Optional[list] = None) -> bool:
    """POST a message-card to a Microsoft Teams incoming webhook."""
    if not url:
        return False
    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": "0d1321",
        "title": title,
        "text": text,
    }
    if facts:
        payload["sections"] = [{"facts": [{"name": f["name"], "value": f["value"]} for f in facts]}]
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(url, json=payload)
            return 200 <= r.status_code < 300
    except Exception:
        logger.exception("Teams webhook failed")
        return False


async def notify_channels(*, slack_url: Optional[str], teams_url: Optional[str],
                          title: str, text: str, facts: Optional[list] = None,
                          slack_blocks: Optional[list] = None) -> dict:
    """Fire-and-forget notifier for both Slack and Teams. Returns delivery status per channel."""
    results = {}
    tasks = []
    if slack_url:
        tasks.append(("slack", send_slack_webhook(slack_url, f"*{title}*\n{text}", slack_blocks)))
    if teams_url:
        tasks.append(("teams", send_teams_webhook(teams_url, title, text, facts)))
    if not tasks:
        return {}
    outcomes = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
    for (name, _), ok in zip(tasks, outcomes):
        results[name] = ok if isinstance(ok, bool) else False
    return results
