"""Weekly Executive Briefing podcast — auto-generated 5-min MP3 from the
latest intelligence briefing + a featured course.

Pipeline:
  1. Pull cached intelligence briefing (top 3 signals + executive summary)
  2. Pick a featured course (freshest full-curriculum one)
  3. Compose a ~5-minute (~4500-char) narration script
  4. Chunk script into ≤2000-char pieces and call OpenAI TTS for each
     (using the Emergent LLM Key). MP3 frames concatenate byte-wise cleanly
     so we just join the raw bytes.
  5. Persist as a `podcast_episodes` document (audio base64 + metadata).
  6. Expose:
       - POST /api/admin/podcast/generate            (super-admin)
       - GET  /api/podcast/latest                    (public)
       - GET  /api/podcast/episodes                  (public list)
       - GET  /api/podcast/episodes/{id}/audio.mp3   (public MP3 stream)
       - GET  /api/podcast/rss.xml                   (public RSS 2.0)
       - POST /api/admin/podcast/{id}/email          (super-admin — fan-out email)

Design notes:
  - Episodes are content-hashed by their generated_at week so duplicate
    weekly generates upsert onto the same doc.
  - Audio is stored as base64 in Mongo. Fine at ~2-3 MB per weekly episode.
    Move to S3/GridFS if the archive grows beyond ~100 episodes.
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from auth import get_current_super_admin
from core import db, logger, now_iso

router = APIRouter(prefix="/api", tags=["podcast"])


# ---------------- Script builder ----------------
def _build_script(briefing: dict, featured: dict | None) -> str:
    """Compose a 4-5 minute narration script from the briefing payload."""
    dateline = datetime.now(timezone.utc).strftime("%A, %B %d")
    parts: list[str] = []

    parts.append(
        "Welcome to the ITHR Enterprise Agentic AI Weekly Executive Briefing. "
        f"This is your five-minute update for {dateline}."
    )

    exec_summary = (briefing.get("executive_summary") or "").strip()
    if exec_summary:
        parts.append(f"Here's the big picture. {exec_summary}")

    signals = briefing.get("signals") or []
    top_signals = signals[:3]
    if top_signals:
        parts.append("Now, the three signals executives should be tracking this week.")
        for i, sig in enumerate(top_signals, start=1):
            title = (sig.get("title") or "").strip().rstrip(".")
            summary = (sig.get("summary") or sig.get("description") or "").strip()
            impact = (sig.get("impact") or "").strip()
            action = (sig.get("recommended_action") or "").strip()
            block = [f"Signal number {i}. {title}."]
            if summary:
                block.append(summary)
            if impact:
                block.append(f"Why it matters. {impact}")
            if action:
                block.append(f"Recommended action. {action}")
            parts.append(" ".join(block))

    if featured:
        ft = (featured.get("title") or "").strip()
        subtitle = (featured.get("subtitle") or "").strip().rstrip(".")
        duration = featured.get("duration_hours")
        parts.append(
            f"This week's featured program on the Academy is {ft}. "
            + (f"{subtitle}. " if subtitle else "")
            + (f"A {duration}-hour executive track" if duration else "An executive track")
            + " authored and continuously refreshed by the ITHR editorial team. "
            "You can find the full curriculum, and a thirty-second audio preview, at ithr.online."
        )

    parts.append(
        "That's your briefing. Compound the advantage — subscribe to next Monday's edition, "
        "and if you're leading a team, invite them into an ITHR enterprise workspace. "
        "This has been Aletheia. See you next week."
    )
    return "\n\n".join(parts).strip()


# ---------------- TTS with chunking ----------------
async def _tts_chunks(text: str) -> bytes:
    """Split text on sentence boundaries into ≤1800-char chunks, call TTS
    for each, and concatenate the MP3 bytes. Voice: shimmer (warm exec).
    """
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    # Sentence-aware chunking so speech doesn't cut mid-word
    sentences = []
    buf = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if buf:
                sentences.append(" ".join(buf))
                buf = []
            continue
        for sent in line.replace("!", ".").replace("?", ".").split(". "):
            sent = sent.strip()
            if sent:
                sentences.append(sent + ("." if not sent.endswith(".") else ""))
    if buf:
        sentences.append(" ".join(buf))

    chunks: list[str] = []
    current = ""
    for s in sentences:
        candidate = (current + " " + s).strip() if current else s
        if len(candidate) > 1800:
            if current:
                chunks.append(current)
            current = s
        else:
            current = candidate
    if current:
        chunks.append(current)

    from emergentintegrations.llm.openai import OpenAITextToSpeech
    tts = OpenAITextToSpeech(api_key=key)

    audio_parts: list[bytes] = []
    for i, ch in enumerate(chunks):
        try:
            piece = await tts.generate_speech(
                text=ch, model="tts-1", voice="shimmer", speed=1.0, response_format="mp3",
            )
            audio_parts.append(piece)
            logger.info(f"Podcast TTS chunk {i+1}/{len(chunks)} — {len(ch)} chars → {len(piece)} bytes")
        except Exception as e:
            logger.exception("Podcast TTS chunk failed")
            raise HTTPException(status_code=502, detail=f"TTS chunk {i+1} failed: {e}") from e

    return b"".join(audio_parts)


# ---------------- Featured course picker ----------------
async def _pick_featured_course() -> dict | None:
    """Pick a fresh, full-curriculum course as the weekly feature."""
    course = await db.courses.find_one(
        {"has_full_content": True},
        {"_id": 0, "id": 1, "slug": 1, "title": 1, "subtitle": 1, "duration_hours": 1, "last_reviewed_at": 1},
        sort=[("last_reviewed_at", -1)],
    )
    return course


# ---------------- Endpoints ----------------
@router.post("/admin/podcast/generate")
async def generate_episode(_admin_id: str = Depends(get_current_super_admin)):
    """Assemble a new weekly episode. Upserts on the ISO-week key so
    accidental double-runs within the same week overwrite rather than
    duplicate."""
    # 1) Get briefing (this is cached, will not thrash the LLM)
    briefing_doc = await db.intelligence_cache.find_one({"key": "current_briefing"}, {"_id": 0})
    if not briefing_doc:
        raise HTTPException(status_code=409, detail="No intelligence briefing available yet — hit /api/intelligence/briefing first.")
    briefing = briefing_doc.get("payload") or {}

    # 2) Feature a course
    featured = await _pick_featured_course()

    # 3) Compose script
    script = _build_script(briefing, featured)

    # 4) TTS
    audio_bytes = await _tts_chunks(script)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    # 5) Persist
    now = datetime.now(timezone.utc)
    iso_week = now.isocalendar()
    week_key = f"{iso_week.year}-W{iso_week.week:02d}"
    episode_id = f"ep-{week_key}"

    signals = (briefing.get("signals") or [])[:3]
    doc = {
        "id": episode_id,
        "week_key": week_key,
        "title": briefing.get("briefing_title") or f"ITHR Weekly Executive Briefing · {week_key}",
        "summary": briefing.get("executive_summary") or "",
        "script": script,
        "audio_b64": audio_b64,
        "audio_bytes": len(audio_bytes),
        "duration_seconds_est": round(len(script.split()) / 2.6),  # ~156 wpm
        "signals": [{"title": s.get("title"), "id": s.get("id")} for s in signals],
        "featured_course": (
            {"slug": featured.get("slug"), "title": featured.get("title")} if featured else None
        ),
        "generated_at": now_iso(),
        "published_at": now_iso(),
    }
    await db.podcast_episodes.update_one({"id": episode_id}, {"$set": doc}, upsert=True)

    # Return a lean payload (no audio_b64)
    return {**{k: v for k, v in doc.items() if k not in ("audio_b64", "script")}, "created": True}


def _episode_public(ep: dict, request_origin: str) -> dict:
    base = request_origin.rstrip("/")
    return {
        "id": ep["id"],
        "week_key": ep["week_key"],
        "title": ep["title"],
        "summary": ep.get("summary", ""),
        "duration_seconds_est": ep.get("duration_seconds_est", 300),
        "audio_bytes": ep.get("audio_bytes", 0),
        "signals": ep.get("signals", []),
        "featured_course": ep.get("featured_course"),
        "published_at": ep.get("published_at"),
        "audio_url": f"{base}/api/podcast/episodes/{ep['id']}/audio.mp3",
    }


def _public_base() -> str:
    """Best-effort public base URL for links inside the RSS feed and JSON."""
    return (os.environ.get("PUBLIC_APP_URL") or os.environ.get("FRONTEND_URL") or "").rstrip("/")


@router.get("/podcast/latest")
async def get_latest():
    ep = await db.podcast_episodes.find_one({}, {"_id": 0, "audio_b64": 0, "script": 0}, sort=[("published_at", -1)])
    if not ep:
        raise HTTPException(status_code=404, detail="No episodes published yet.")
    return _episode_public(ep, _public_base())


@router.get("/podcast/episodes")
async def list_episodes():
    eps = await db.podcast_episodes.find({}, {"_id": 0, "audio_b64": 0, "script": 0}).sort("published_at", -1).to_list(24)
    base = _public_base()
    return {"episodes": [_episode_public(e, base) for e in eps]}


@router.get("/podcast/episodes/{episode_id}/audio.mp3")
async def stream_audio(episode_id: str):
    ep = await db.podcast_episodes.find_one({"id": episode_id}, {"_id": 0, "audio_b64": 1, "title": 1})
    if not ep or not ep.get("audio_b64"):
        raise HTTPException(status_code=404, detail="Episode not found")
    audio = base64.b64decode(ep["audio_b64"])
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'inline; filename="ithr-briefing-{episode_id}.mp3"',
            "Cache-Control": "public, max-age=3600",
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/podcast/rss.xml")
async def rss_feed():
    """RSS 2.0 feed for Apple Podcasts / Spotify / Overcast subscription."""
    base = _public_base() or "https://learn.ithr.online"
    eps = await db.podcast_episodes.find({}, {"_id": 0, "audio_b64": 0, "script": 0}).sort("published_at", -1).to_list(50)

    items = []
    for e in eps:
        pub = e.get("published_at") or now_iso()
        try:
            pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            pub_dt = datetime.now(timezone.utc)
        rfc822 = format_datetime(pub_dt)
        audio_url = f"{base}/api/podcast/episodes/{e['id']}/audio.mp3"
        items.append(f"""    <item>
      <title>{xml_escape(e.get('title',''))}</title>
      <description>{xml_escape(e.get('summary',''))}</description>
      <pubDate>{rfc822}</pubDate>
      <guid isPermaLink="false">{xml_escape(e['id'])}</guid>
      <enclosure url="{xml_escape(audio_url)}" length="{e.get('audio_bytes',0)}" type="audio/mpeg" />
      <itunes:duration>{e.get('duration_seconds_est',300)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

    now_rfc = format_datetime(datetime.now(timezone.utc))
    channel = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>ITHR Weekly Executive Briefing</title>
    <link>{xml_escape(base)}/podcast</link>
    <language>en-us</language>
    <copyright>© ITHR Technologies Consulting LLC</copyright>
    <description>A five-minute weekly briefing on Enterprise Agentic AI — the top three signals for executives and one featured program from the ITHR Academy.</description>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <itunes:author>ITHR Academy</itunes:author>
    <itunes:summary>A five-minute weekly briefing on Enterprise Agentic AI, narrated by Aletheia.</itunes:summary>
    <itunes:owner>
      <itunes:name>ITHR Academy</itunes:name>
      <itunes:email>no-reply@ithr.online</itunes:email>
    </itunes:owner>
    <itunes:category text="Business" />
    <itunes:explicit>false</itunes:explicit>
{chr(10).join(items)}
  </channel>
</rss>
"""
    return Response(content=channel, media_type="application/rss+xml")


@router.post("/admin/podcast/{episode_id}/email")
async def email_episode(episode_id: str, _admin_id: str = Depends(get_current_super_admin)):
    """Fan-out email announcing this episode to all learners with
    `digest_impressions_enabled=True` (reusing the existing opt-in flag).
    """
    ep = await db.podcast_episodes.find_one({"id": episode_id}, {"_id": 0, "audio_b64": 0, "script": 0})
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")

    base = _public_base() or "https://learn.ithr.online"
    audio_url = f"{base}/api/podcast/episodes/{episode_id}/audio.mp3"
    page_url = f"{base}/podcast"

    from email_service import _fire, _wrap  # existing helpers

    signals_html = "".join(
        f"<li style='margin:6px 0'>{(s.get('title') or '')}</li>" for s in (ep.get("signals") or [])
    )
    featured = ep.get("featured_course") or {}
    featured_html = ""
    if featured.get("slug"):
        featured_html = (
            f"<p style='margin:12px 0 4px'><b>Featured program:</b> "
            f"<a href='{base}/courses/{featured['slug']}' style='color:#00A78B'>{featured.get('title','')}</a></p>"
        )

    body = f"""
      <p>This week's ITHR Executive Briefing is live — five minutes covering the three signals every enterprise leader should track, and one featured Academy program.</p>
      <p style='margin:16px 0 4px'><b>In this episode:</b></p>
      <ul style='padding-left:20px;margin:4px 0 12px'>{signals_html}</ul>
      {featured_html}
      <p style='margin:12px 0 20px;color:#6b7280;font-size:13px'>Duration: ~{max(1, round(ep.get('duration_seconds_est', 300)/60))} min</p>
    """
    html = _wrap(
        kicker="ITHR Weekly Briefing",
        heading=ep.get("title", "This week's Executive Briefing"),
        body_html=body,
        cta_label="▶ Listen now",
        cta_url=audio_url,
        footer_note=f"Subscribe via RSS: {base}/api/podcast/rss.xml · Web player: {page_url}",
    )

    # Recipients — opt-in flag; if none flagged, send to super-admin(s) as a safe default.
    recipients = await db.users.find(
        {"$or": [{"digest_impressions_enabled": True}, {"role": "super_admin"}]},
        {"_id": 0, "email": 1, "full_name": 1},
    ).to_list(500)
    if not recipients:
        raise HTTPException(status_code=409, detail="No opt-in recipients found.")

    sent = 0
    failed = 0
    for u in recipients:
        try:
            ok = await _fire(
                to_email=u["email"],
                subject=ep.get("title", "This week's ITHR Executive Briefing"),
                html=html,
                text_fallback=f"This week's ITHR Executive Briefing: {audio_url}",
                tag=f"podcast-{episode_id}",
            )
            sent += 1 if ok else 0
            failed += 0 if ok else 1
        except Exception:
            logger.exception(f"Podcast email failed for {u.get('email')}")
            failed += 1

    # Log the send
    await db.podcast_episodes.update_one(
        {"id": episode_id},
        {"$set": {
            "last_emailed_at": now_iso(),
            "email_recipients_count": len(recipients),
            "email_send_id": str(uuid.uuid4()),
        }},
    )
    return {"sent": sent, "failed": failed, "recipients_count": len(recipients)}
