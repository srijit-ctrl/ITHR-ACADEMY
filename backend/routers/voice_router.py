"""Voice IO endpoints — Whisper (STT) + OpenAI TTS via Emergent LLM Key.

Powers the voice-interactive "Ask Aletheia" experience across:
  - Certificate page tutor (CertificateTutor.jsx)
  - In-lesson tutor (InlineTutor.jsx)
  - Landing-page demo tutor (DemoChat.jsx)

Both endpoints are intentionally open — STT/TTS are per-request stateless and
the credentials never touch the browser. Rate-limit / gate by session cookie
later once we see abuse patterns.
"""
from __future__ import annotations

import base64
import io
import os

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel

from core import logger

router = APIRouter(prefix="/api/voice", tags=["voice"])


# ---------------- STT (Whisper) ----------------
@router.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = Form("en"),
):
    """Transcribe a short audio blob using whisper-1.

    Frontend sends a webm/mp3/wav blob from MediaRecorder. Whisper accepts up to
    25 MB; browser recordings ~15s stay well under 500 KB.
    """
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (25 MB max)")

    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText

        stt = OpenAISpeechToText(api_key=key)
        buf = io.BytesIO(data)
        # Whisper needs a filename hint for MIME sniffing
        buf.name = file.filename or "audio.webm"
        response = await stt.transcribe(
            file=buf,
            model="whisper-1",
            response_format="json",
            language=language or "en",
            temperature=0.0,
        )
        text = (getattr(response, "text", "") or "").strip()
        return {"text": text}
    except Exception as e:
        logger.exception("STT failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from e


# ---------------- TTS (OpenAI) ----------------
class TTSRequest(BaseModel):
    text: str
    voice: str = "shimmer"  # warm/female; other picks: coral, nova
    speed: float = 1.0


@router.post("/tts")
async def text_to_speech(payload: TTSRequest):
    """Generate an MP3 for the given text (max 4096 chars per Whisper API)."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")
    # Guard against runaway TTS spend + ingress timeout at long generations.
    # Cap at 2000 chars — OpenAI TTS at 4000 chars regularly bumps against a
    # 60s Cloudflare upstream limit. Long content should be chunked client-side.
    if len(text) > 2000:
        text = text[:1997] + "…"

    voice = payload.voice if payload.voice in {
        "alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer",
    } else "shimmer"
    speed = max(0.5, min(2.0, float(payload.speed or 1.0)))

    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech

        tts = OpenAITextToSpeech(api_key=key)
        audio_bytes = await tts.generate_speech(
            text=text,
            model="tts-1",
            voice=voice,
            speed=speed,
            response_format="mp3",
        )
        # Return base64 in JSON so it plays cleanly from a data URI on the client
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        return {"audio_b64": b64, "mime": "audio/mpeg", "voice": voice}
    except Exception as e:
        logger.exception("TTS failed")
        raise HTTPException(status_code=500, detail=f"Speech generation failed: {e}") from e
