"""In-portal document viewer.

Serves PPTX course resources as PDFs so learners can read them inline
without downloading. Conversion is done once via headless LibreOffice
(`soffice --headless --convert-to pdf`) and the PDF is cached alongside
the source file. Subsequent hits stream the cached PDF instantly.

Fallback: if the PDF conversion is unavailable (missing LibreOffice, corrupted
source), the client can degrade to the Microsoft Office Online viewer
(`https://view.officeapps.live.com/op/embed.aspx?src=<public-url>`) — but
that requires the file to be publicly reachable, which is a privacy trade-off
we default AWAY from. The endpoint returns 502 in that case so the client
knows to swap in the fallback.

Access rule mirrors the download endpoint in catalog_router:
    - public resource → any authenticated user
    - non-public → learner must be enrolled
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth import get_current_user_id
from core import db, logger

router = APIRouter(prefix="/api", tags=["resource-viewer"])

COURSE_RESOURCES_DIR = Path(__file__).resolve().parent.parent / "static" / "course_resources"
PDF_CACHE_DIR = COURSE_RESOURCES_DIR / ".pdf_cache"
PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Formats we can convert with LibreOffice.
_CONVERTIBLE_EXTS = {".pptx", ".ppt", ".pptm", ".key", ".doc", ".docx", ".odp", ".odt"}


def _pdf_cache_path(source_filename: str) -> Path:
    """Deterministic PDF cache filename for a given source resource."""
    stem = Path(source_filename).stem
    return PDF_CACHE_DIR / f"{stem}.pdf"


async def _convert_to_pdf(source: Path, target: Path) -> None:
    """Convert `source` (PPTX/DOCX/etc) → `target` (PDF) via headless LibreOffice.

    Runs in a subprocess to avoid blocking the event loop. Raises RuntimeError
    on non-zero exit. LibreOffice writes to `target.parent` with the same stem
    as the source; we rename to the exact target path on success.
    """
    if not source.exists():
        raise FileNotFoundError(f"Source resource missing: {source}")

    proc = await asyncio.create_subprocess_exec(
        "soffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(target.parent),
        str(source),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError as e:
        proc.kill()
        raise RuntimeError("LibreOffice conversion timed out after 120s") from e

    if proc.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed (exit={proc.returncode}): {stderr.decode(errors='ignore')}"
        )

    # LibreOffice writes to <outdir>/<stem>.pdf which is what we want,
    # but stem may differ from the exact filename we want to cache under.
    lo_output = target.parent / f"{source.stem}.pdf"
    if lo_output != target and lo_output.exists():
        lo_output.rename(target)

    if not target.exists():
        raise RuntimeError(f"LibreOffice ran but produced no PDF at {target}")


@router.get("/courses/{slug}/resources/{filename}/preview.pdf")
async def preview_resource_as_pdf(
    slug: str, filename: str, user_id: str = Depends(get_current_user_id),
):
    """Return the resource as an inline PDF for browser rendering.

    Contract:
      * 401 anonymous, 403 non-enrolled (non-public resource), 404 course/resource missing.
      * 415 for source formats we cannot convert.
      * 502 if conversion fails at runtime — the client can then fall back
        to the Office Online iframe using the public URL.
      * 200 with `Content-Type: application/pdf` + `Content-Disposition: inline`.
    """
    course = await db.courses.find_one({"slug": slug}, {"_id": 0, "id": 1, "resources": 1})
    if not course:
        raise HTTPException(404, "Course not found")

    resource = next(
        (r for r in (course.get("resources") or []) if r.get("filename") == filename),
        None,
    )
    if not resource:
        raise HTTPException(404, "Resource not found")

    if not resource.get("public", False):
        enrolled = await db.enrollments.find_one({"user_id": user_id, "course_id": course["id"]})
        if not enrolled:
            raise HTTPException(403, "Enroll in this course to unlock its resources")

    # Path-traversal guard.
    safe_source = (COURSE_RESOURCES_DIR / filename).resolve()
    if not str(safe_source).startswith(str(COURSE_RESOURCES_DIR.resolve()) + "/"):
        raise HTTPException(400, "Invalid filename")
    if not safe_source.exists():
        raise HTTPException(404, "Source file missing on server")

    ext = safe_source.suffix.lower()
    # PDFs pass through directly.
    if ext == ".pdf":
        return FileResponse(
            path=str(safe_source),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{safe_source.name}"',
                "Cache-Control": "private, max-age=3600",
            },
        )

    if ext not in _CONVERTIBLE_EXTS:
        raise HTTPException(415, f"Format {ext} is not previewable in-portal")

    pdf_path = _pdf_cache_path(filename)

    # Regenerate only when source is newer than the cached PDF (or PDF missing).
    needs_convert = (
        not pdf_path.exists()
        or safe_source.stat().st_mtime > pdf_path.stat().st_mtime
    )
    if needs_convert:
        try:
            await _convert_to_pdf(safe_source, pdf_path)
        except Exception as e:
            logger.exception(f"[resource-viewer] PDF conversion failed for {filename}")
            raise HTTPException(502, "Preview unavailable — please download the file instead.") from e

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{Path(filename).stem}.pdf"',
            "Cache-Control": "private, max-age=3600",
        },
    )
