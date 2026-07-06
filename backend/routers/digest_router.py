"""Enterprise digest — weekly (or on-demand) HTML email with critical signals.

Endpoints:
  POST /api/enterprise/organizations/digest/preview   → HTML preview (no send)
  POST /api/enterprise/organizations/digest/send      → send to org owner+admins
  POST /api/enterprise/organizations/notifications    → store slack/teams webhook URLs
  GET  /api/enterprise/organizations/digest/log       → past sends

Anyone in the org can PREVIEW; only owner/admin can SEND or edit webhooks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user_id
from core import db, now_iso
from notifications import send_email
from routers.enterprise_router import _resolve_org_for_user
from routers.intelligence_router import INTELLIGENCE_CACHE_KEY

router = APIRouter(prefix="/api/enterprise", tags=["enterprise-digest"])


IMPACT_COLOR = {
    "Critical": "#c93648",
    "High": "#00a897",
    "Medium": "#5b7ba8",
    "Low": "#7d8ba0",
}


async def _load_digest_data() -> tuple[list[dict], list[dict]]:
    """Fetch critical intelligence signals + pending curriculum patches for the digest."""
    cached = await db.intelligence_cache.find_one({"key": INTELLIGENCE_CACHE_KEY}, {"_id": 0})
    signals = (cached.get("payload") or {}).get("signals", []) if cached else []
    critical_signals = [s for s in signals if s.get("impact") in ("Critical", "High")][:6]
    patches = await db.curriculum_patches.find(
        {"status": "proposed"}, {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    return critical_signals, patches


def _kpi_row_html(summary: dict) -> str:
    return f"""
    <table role="presentation" width="100%" style="border-collapse:collapse;margin:0 0 32px;">
      <tr>
        {_kpi_cell("Readiness", f"{summary.get('readiness_index','—')}", "/ 100")}
        {_kpi_cell("Certifications", str(summary.get("total_certificates", 0)), "earned")}
        {_kpi_cell("Avg progress", f"{summary.get('avg_progress','—')}%", "across seats")}
        {_kpi_cell("Seats", f"{summary.get('seats_used',0)}/{summary.get('seat_count',0)}", "used")}
      </tr>
    </table>
    """


def _signal_card_html(s: dict) -> str:
    color = IMPACT_COLOR.get(s.get("impact", "Medium"), "#5b7ba8")
    return f"""
    <table role="presentation" width="100%" style="border-collapse:collapse;margin:0 0 14px;border:1px solid #d7dde6;">
      <tr>
        <td style="padding:16px 20px;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:{color};margin-bottom:4px;">
            {s.get('impact','Medium').upper()} · {s.get('category','')}
          </div>
          <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:20px;line-height:1.25;color:#0d1321;margin:0 0 6px;">
            {_esc(s.get('title',''))}
          </div>
          <div style="font-family:Arial,sans-serif;font-size:13px;color:#4a5768;margin-bottom:8px;">
            {_esc(s.get('summary',''))[:220]}
          </div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#00a897;">
            → {_esc(s.get('recommended_action',''))[:120]}
          </div>
        </td>
      </tr>
    </table>
    """


def _patches_section_html(patches: list[dict]) -> str:
    if not patches:
        return ""
    rows = "".join(
        f"""
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid #eef1f5;font-family:Arial,sans-serif;font-size:13px;">
            <div style="color:#0d1321;font-weight:600;">{_esc(p.get('proposed_title',''))}</div>
            <div style="color:#7d8ba0;font-size:11px;font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:1.5px;margin-top:2px;">
              {_esc(p.get('course_slug',''))} · Module {p.get('module_number','?')}
            </div>
          </td>
        </tr>
        """ for p in patches[:5]
    )
    return f"""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#00a897;margin:32px 0 12px;">Pending curriculum patches</div>
    <table role="presentation" width="100%" style="border-collapse:collapse;border:1px solid #d7dde6;">{rows}</table>
    """


def _digest_shell_html(org: dict, kpi_html: str, body_html: str, briefing_url: str) -> str:
    """Wrap the KPI + body content in the ITHR-branded email envelope."""
    return f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ITHR Weekly Intelligence Digest</title></head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:Arial,sans-serif;color:#0d1321;">
  <table role="presentation" width="100%" style="border-collapse:collapse;background:#f5f7fa;padding:40px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="640" style="border-collapse:collapse;background:#ffffff;border:1px solid #d7dde6;">
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" style="border-collapse:collapse;background:#0d1321;color:#ffffff;">
                <tr>
                  <td style="padding:24px 32px;">
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#d4a836;margin-bottom:6px;">EST. 2026 · ITHR TECHNOLOGIES</div>
                    <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:26px;line-height:1;color:#ffffff;">
                      ITHR <span style="color:#00a897;">Academy</span>
                    </div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.7);margin-top:6px;">Weekly Intelligence Digest</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:36px 32px 8px;">
              <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:32px;line-height:1.15;color:#0d1321;margin-bottom:8px;">
                {_esc(org.get('name','Your organization'))}: this week in agentic AI.
              </div>
              <div style="font-family:Arial,sans-serif;font-size:14px;color:#4a5768;">
                A curated brief of critical signals + pending curriculum updates for your team.
              </div>
            </td>
          </tr>

          <tr><td style="padding:24px 32px 0;">{kpi_html}</td></tr>
          <tr><td style="padding:0 32px 24px;">{body_html}</td></tr>

          <tr>
            <td style="padding:0 32px 40px;">
              <a href="{briefing_url}" style="display:inline-block;background:#00a897;color:#ffffff;padding:12px 24px;font-family:Arial,sans-serif;font-size:14px;font-weight:600;text-decoration:none;">Open full briefing →</a>
            </td>
          </tr>

          <tr>
            <td style="padding:20px 32px;background:#f5f7fa;border-top:1px solid #d7dde6;">
              <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:2px;text-transform:uppercase;color:#7d8ba0;text-align:center;">
                © 2026 ITHR Technologies Consulting LLC · A Certification Authority
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body></html>
"""


async def _build_digest_html(org: dict, summary: dict) -> tuple[str, dict]:
    """Assemble the HTML digest + return (html, meta).

    Orchestrates: (1) data load, (2) KPI + signals + patches section render,
    (3) shell wrap. Broken into helpers so each section is independently
    testable and swappable.
    """
    import os
    critical_signals, patches = await _load_digest_data()

    kpi_html = _kpi_row_html(summary)
    signals_html = "".join(_signal_card_html(s) for s in critical_signals)
    if not signals_html:
        signals_html = '<div style="font-family:Arial,sans-serif;font-size:13px;color:#7d8ba0;">No critical signals in this window.</div>'
    patches_html = _patches_section_html(patches)

    body_html = f"""
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#00a897;margin-bottom:16px;">Critical intelligence · Top {len(critical_signals)}</div>
      {signals_html}
      {patches_html}
    """

    # Briefing URL from env — no hardcoded preview host so prod links land on learn.ithr.tech
    base_url = os.environ.get("PUBLIC_APP_URL", "").rstrip("/") or "https://learn.ithr.tech"
    briefing_url = f"{base_url}/intelligence"

    html = _digest_shell_html(org, kpi_html, body_html, briefing_url)
    meta = {
        "critical_signal_count": len(critical_signals),
        "pending_patch_count": len(patches),
        "generated_at": now_iso(),
    }
    return html, meta


def _kpi_cell(label: str, value: str, unit: str) -> str:
    return f"""
    <td style="padding:16px 12px;border:1px solid #d7dde6;background:#f5f7fa;width:25%;text-align:left;">
      <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:28px;line-height:1;color:#0d1321;">
        {value} <span style="font-family:Arial,sans-serif;font-size:11px;color:#7d8ba0;font-weight:normal;">{unit}</span>
      </div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:2px;text-transform:uppercase;color:#7d8ba0;margin-top:6px;">{label}</div>
    </td>
    """


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _summary_for_org(org: dict) -> dict:
    """Fast KPI aggregation for the digest header."""
    members = await db.org_members.find({"org_id": org["id"]}, {"_id": 0, "user_id": 1}).to_list(1000)
    user_ids = [m["user_id"] for m in members]
    enrollments = await db.enrollments.find({"user_id": {"$in": user_ids}}, {"_id": 0}).to_list(5000)
    certs = await db.certificates.find({"user_id": {"$in": user_ids}}, {"_id": 0, "user_id": 1}).to_list(5000)
    total_progress = sum(e.get("progress_pct", 0.0) for e in enrollments)
    per_user_progress = {uid: 0.0 for uid in user_ids}
    counts = {uid: 0 for uid in user_ids}
    for e in enrollments:
        per_user_progress[e["user_id"]] = per_user_progress.get(e["user_id"], 0) + e.get("progress_pct", 0.0)
        counts[e["user_id"]] = counts.get(e["user_id"], 0) + 1
    avg_per_user = [(per_user_progress[u] / counts[u]) if counts[u] else 0 for u in user_ids]
    avg_progress = round(sum(avg_per_user) / len(avg_per_user), 1) if avg_per_user else 0.0
    cert_users = {c["user_id"] for c in certs}
    cert_coverage = round(len(cert_users) / len(user_ids) * 100, 1) if user_ids else 0.0
    readiness = round(avg_progress * 0.5 + cert_coverage * 0.5, 1)
    return {
        "seat_count": org.get("seat_count", 0),
        "seats_used": len(members),
        "total_certificates": len(certs),
        "avg_progress": avg_progress,
        "cert_coverage_pct": cert_coverage,
        "readiness_index": readiness,
    }


@router.post("/organizations/digest/preview")
async def preview_digest(user_id: str = Depends(get_current_user_id)):
    org, _ = await _resolve_org_for_user(user_id)
    summary = await _summary_for_org(org)
    html, meta = await _build_digest_html(org, summary)
    return {"html": html, "meta": meta, "org_id": org["id"]}


@router.post("/organizations/digest/send")
async def send_digest(payload: dict = None, user_id: str = Depends(get_current_user_id)):
    org, member = await _resolve_org_for_user(user_id, require_admin=True)
    payload = payload or {}
    summary = await _summary_for_org(org)
    html, meta = await _build_digest_html(org, summary)

    # Recipients: all admins + owner (dedupe)
    recipients_set = set()
    if payload.get("to"):
        recipients_set.add(payload["to"].lower().strip())
    else:
        admins = await db.org_members.find(
            {"org_id": org["id"], "role": {"$in": ["owner", "admin"]}},
            {"_id": 0, "email": 1},
        ).to_list(50)
        for a in admins:
            recipients_set.add(a["email"].lower().strip())
    recipients = sorted(recipients_set)

    delivery = []
    for email in recipients:
        result = await send_email(
            to_email=email,
            subject=f"[ITHR Academy] Weekly digest for {org['name']}",
            html=html,
        )
        delivery.append({"email": email, **result})

    log_doc = {
        "id": uuid.uuid4().hex,
        "org_id": org["id"],
        "sent_by": user_id,
        "recipients": recipients,
        "delivery": delivery,
        "meta": meta,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.org_digest_logs.insert_one(log_doc)
    log_doc.pop("_id", None)
    return {"log": log_doc}


@router.get("/organizations/digest/log")
async def digest_log(user_id: str = Depends(get_current_user_id)):
    org, _ = await _resolve_org_for_user(user_id)
    logs = await db.org_digest_logs.find(
        {"org_id": org["id"]}, {"_id": 0}
    ).sort("sent_at", -1).to_list(50)
    return {"logs": logs}


# ---------- Notification channel settings ----------
@router.get("/organizations/notifications")
async def get_notifications(user_id: str = Depends(get_current_user_id)):
    org, _ = await _resolve_org_for_user(user_id, require_admin=True)
    return {
        "slack_webhook_url": org.get("slack_webhook_url"),
        "teams_webhook_url": org.get("teams_webhook_url"),
        "notify_on_patch_approval": org.get("notify_on_patch_approval", True),
    }


@router.post("/organizations/notifications")
async def set_notifications(payload: dict, user_id: str = Depends(get_current_user_id)):
    org, _ = await _resolve_org_for_user(user_id, require_admin=True)
    update = {}
    if "slack_webhook_url" in payload:
        val = (payload["slack_webhook_url"] or "").strip()
        if val and not val.startswith(("https://hooks.slack.com/", "https://")):
            raise HTTPException(status_code=400, detail="Slack webhook URL must be a Slack incoming-webhook HTTPS URL")
        update["slack_webhook_url"] = val or None
    if "teams_webhook_url" in payload:
        val = (payload["teams_webhook_url"] or "").strip()
        if val and not val.startswith("https://"):
            raise HTTPException(status_code=400, detail="Teams webhook URL must start with https://")
        update["teams_webhook_url"] = val or None
    if "notify_on_patch_approval" in payload:
        update["notify_on_patch_approval"] = bool(payload["notify_on_patch_approval"])
    if not update:
        raise HTTPException(status_code=400, detail="No settings provided")
    await db.organizations.update_one({"id": org["id"]}, {"$set": update})
    return {"updated": update}
