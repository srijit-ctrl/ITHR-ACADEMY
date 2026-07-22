# Ops / Environment Notes (read before touching the PPTX viewer or deploying)

## In-portal PPTX → PDF viewer depends on LibreOffice at runtime
- Endpoint: `GET /api/courses/{slug}/resources/{filename}/preview.pdf` (`backend/routers/resource_viewer_router.py`).
- It converts PPTX/DOCX → PDF via headless LibreOffice (`soffice`), then caches the PDF in
  `/app/backend/static/course_resources/.pdf_cache/`.
- **`soffice` is installed at OS level and does NOT persist across forks / container rebuilds / production deploys.**
  Only files under `/app` persist.
- The cached PDFs live under `/app` so they DO persist. That is why the existing
  `prompt-engineering-mastery-deck.pptx` still previews even without LibreOffice installed —
  the endpoint streams the cached PDF (cache invalidation is mtime-based: it only reconverts when
  the source PPTX is newer than the cache).

### Rules
1. Do NOT re-save / re-copy / touch the source PPTX in a container where LibreOffice is absent —
   it bumps the source mtime, invalidates the cache, and the endpoint will 502.
2. Before adding a NEW PPTX resource, either:
   - install LibreOffice first: `apt-get update && apt-get install -y libreoffice`, hit the
     preview endpoint once to warm the cache, OR
   - pre-generate the PDF and drop it in `.pdf_cache/<stem>.pdf` with an mtime newer than the source.
3. For production robustness, bake `libreoffice` into the base image (deploy build step).

## Frontend pdf.js worker
- `ResourcePdfViewer.jsx` pins the pdf.js worker to jsdelivr CDN
  (`https://cdn.jsdelivr.net/npm/pdfjs-dist@<version>/build/pdf.worker.min.mjs`).
- Corporate proxies may block jsdelivr → viewer shows "Couldn't render this document".
- Hardening option (not yet done): self-host the worker under `frontend/public/` and point
  `pdfjs.GlobalWorkerOptions.workerSrc` at it.

## Course content
- All 28 courses have exactly 15 modules (verified Jun 2026). Generation script:
  `backend/scripts/generate_course_content_append.py` (idempotent; `--slug X` for one course, `--all` for batch).

## ⚠️ CRITICAL: generated course content must be BAKED INTO CODE, not left in the DB
- LLM-generated course content written directly to MongoDB does NOT deploy to production.
  Production is a SEPARATE database that is seeded fresh from code on every deploy.
- The 17 non-`full_builders` courses' content is baked into `backend/data/generated_courses.json`
  (committed) and re-seeded on every startup via `backend/seed_generated_courses.py`
  (wired into `server.py::seed_database()`). This is what makes them appear complete in production.
- **If you ever regenerate or add course content via a script that writes to the DB, you MUST
  re-export it into `data/generated_courses.json`** (see the export one-liner in git history /
  iteration 72) so the change survives a production redeploy. Otherwise production will revert
  to stubs on the next deploy.
- Category filter list is derived live from `courses` in `GET /api/catalog/categories` — do not
  re-hardcode it; empty categories must never be shown.
