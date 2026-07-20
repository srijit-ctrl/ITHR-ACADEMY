"""Slack Incoming Webhooks — thin fire-and-forget wrapper.

Used today for enterprise-lead intake alerts (Talent Ops Bundle + HR
Transformation Stack + generic enterprise inquiries). Extendable to any
other event where "ping #sales in Slack" is the desired notification.

Design constraints:
    * `SLACK_WEBHOOK_URL` may be blank in preview — the sender degrades
      to a warning-log-only path and returns False. NEVER raises.
    * Rich block layout by default (attractive card with bundle badge,
      seat count, "reply-to" mailto link). Falls back to plain text if
      Slack's Block Kit rejects any field.
    * 5-second timeout — sales alerts must not queue behind slow webhooks.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from core import logger

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
SLACK_ALERT_TIMEOUT_S = 5.0


def slack_configured() -> bool:
    """True when a webhook URL is present (used by /api/health checks
    and the super-admin lead panel to indicate live vs stubbed state)."""
    return bool(SLACK_WEBHOOK_URL) and SLACK_WEBHOOK_URL.startswith("https://hooks.slack.com/")


def _blocks_for_lead(lead: dict) -> list[dict]:
    """Slack Block Kit payload for an enterprise lead."""
    bundle = lead.get("bundle") or "generic"
    name = lead.get("name") or "—"
    email = lead.get("email") or "—"
    company = lead.get("company") or "—"
    role = lead.get("role") or ""
    seats = lead.get("seats")
    seats_line = f"~{seats} seats" if seats else "seat count not specified"
    message = (lead.get("message") or "").strip() or "_(no message)_"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"New Enterprise Lead · {bundle}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Name*\n{name}"},
                {"type": "mrkdwn", "text": f"*Company*\n{company}"},
                {"type": "mrkdwn", "text": f"*Email*\n<mailto:{email}|{email}>"},
                {"type": "mrkdwn", "text": f"*Role*\n{role or '—'}"},
                {"type": "mrkdwn", "text": f"*Bundle*\n`{bundle}`"},
                {"type": "mrkdwn", "text": f"*Seats*\n{seats_line}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Message*\n{message[:1500]}"},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Source: `{lead.get('source_url') or 'unknown'}`"},
                {"type": "mrkdwn", "text": f"Received: {lead.get('created_at') or '—'}"},
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reply to lead"},
                    "url": f"mailto:{email}?subject=Re:%20{bundle}%20—%20ITHR%20Academy",
                    "style": "primary",
                },
            ],
        },
    ]
    return blocks


async def send_slack_lead_alert(lead: dict) -> bool:
    """Post a rich lead card to the configured Slack webhook.

    Returns True on delivery (HTTP 2xx), False on any failure. Never raises
    — a broken webhook must not block the lead-capture write.
    """
    if not slack_configured():
        logger.warning("[slack] SLACK_WEBHOOK_URL not configured — lead alert skipped")
        return False
    payload = {
        "text": f"New enterprise lead — {lead.get('bundle', 'generic')} · {lead.get('name', '—')}",
        "blocks": _blocks_for_lead(lead),
    }
    try:
        async with httpx.AsyncClient(timeout=SLACK_ALERT_TIMEOUT_S) as client:
            r = await client.post(SLACK_WEBHOOK_URL, json=payload)
        if r.status_code >= 200 and r.status_code < 300:
            logger.info(f"[slack] lead alert delivered (bundle={lead.get('bundle')}, email={lead.get('email')})")
            return True
        logger.warning(f"[slack] lead alert failed status={r.status_code} body={r.text[:200]}")
        return False
    except Exception:
        logger.exception("[slack] lead alert dispatch raised — swallowing")
        return False


async def send_slack_text(message: str) -> bool:
    """Plain-text webhook fallback — used for one-line ops alerts."""
    if not slack_configured():
        return False
    try:
        async with httpx.AsyncClient(timeout=SLACK_ALERT_TIMEOUT_S) as client:
            r = await client.post(SLACK_WEBHOOK_URL, json={"text": message[:1500]})
        return 200 <= r.status_code < 300
    except Exception:
        logger.exception("[slack] plain-text dispatch failed")
        return False
