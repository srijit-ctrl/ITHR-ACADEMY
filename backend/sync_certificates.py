"""Re-align issued certificates with live user/course records.

Certificate PDFs are rendered on demand, so every previously-issued
certificate automatically picks up the latest template (artwork, QR-only
verification, disclaimer). This script fixes records whose stored
user_name/course_title drifted from the live user/course docs so the
pre-render integrity check never blocks a legitimate download.

Usage (preview or prod pod):
    python sync_certificates.py            # dry run
    python sync_certificates.py --confirm  # write fixes
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from core import db, logger  # noqa: E402


async def main(confirm: bool):
    fixed, orphans, ok = 0, 0, 0
    async for cert in db.certificates.find({}, {"_id": 0}):
        cid = cert["certificate_id"]
        if cid == "SAMPLE-ITHR-2026-001":
            continue
        user = await db.users.find_one({"id": cert.get("user_id")}, {"_id": 0, "full_name": 1})
        course = await db.courses.find_one({"id": cert.get("course_id")}, {"_id": 0, "title": 1})
        if not user or not course:
            orphans += 1
            logger.warning(f"[certsync] ORPHAN {cid}: user={'ok' if user else 'MISSING'} course={'ok' if course else 'MISSING'}")
            continue
        updates = {}
        if (user["full_name"] or "").strip() != (cert.get("user_name") or "").strip():
            updates["user_name"] = user["full_name"]
        if (course["title"] or "").strip() != (cert.get("course_title") or "").strip():
            updates["course_title"] = course["title"]
        if updates:
            fixed += 1
            logger.info(f"[certsync] {'FIX' if confirm else 'WOULD FIX'} {cid}: {list(updates)}")
            if confirm:
                await db.certificates.update_one({"certificate_id": cid}, {"$set": updates})
        else:
            ok += 1
    logger.info(f"[certsync] done — ok={ok} fixed={fixed} orphans={orphans} (orphans belong to deleted users/courses; purge removes them)")


if __name__ == "__main__":
    asyncio.run(main(confirm="--confirm" in sys.argv))
