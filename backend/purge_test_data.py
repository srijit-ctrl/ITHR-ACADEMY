"""Purge accumulated test/dummy data from the DB.

Safely removes:
  - All users with @example.com emails (or any --pattern match)
  - Their org_members, enrollments, certificates, quiz_attempts, mentor_sessions
  - Any org where ALL remaining members are also being purged (org becomes an
    empty shell — safe to drop)
  - Payment transactions tied to purged users
  - Password-reset tokens tied to purged users
  - Org invites for @example.com recipient emails

Preserves:
  - The super-admin user (superadmin@ithr.tech)
  - Any user matching --keep-email
  - The sample certificate (SAMPLE-ITHR-2026-001)
  - All course + assessment data

Usage:
    # Dry-run — SHOW what would be deleted, do NOT delete
    python -m purge_test_data --dry-run

    # Actually delete (default pattern = @example.com)
    python -m purge_test_data --confirm

    # Custom pattern
    python -m purge_test_data --pattern "@testing.local" --confirm

    # Preserve specific emails
    python -m purge_test_data --keep-email real.person@ithr.tech --confirm
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("purge_test_data")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
if not (MONGO_URL and DB_NAME):
    raise SystemExit("MONGO_URL + DB_NAME must be set.")

PROTECTED_EMAILS = {"superadmin@ithr.tech", "superadmin@ithr.online", "srijit@ithr360.com"}
PROTECTED_CERT_IDS = {"SAMPLE-ITHR-2026-001"}


async def purge(pattern: str, keep_emails: set, dry_run: bool = True):
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]

    protected = PROTECTED_EMAILS | keep_emails
    query = {"email": {"$regex": pattern, "$options": "i"}, "email": {"$nin": list(protected)}}
    # Two $regex + $nin need to be nested via $and
    query = {"$and": [
        {"email": {"$regex": pattern, "$options": "i"}},
        {"email": {"$nin": list(protected)}},
    ]}

    victim_user_ids = []
    victim_emails = []
    async for u in db.users.find(query, {"_id": 0, "id": 1, "email": 1}):
        victim_user_ids.append(u["id"])
        victim_emails.append(u["email"])

    log.info(f"Users matching pattern '{pattern}' (excluding {len(protected)} protected): {len(victim_user_ids)}")
    if not victim_user_ids:
        log.info("Nothing to purge. Exiting.")
        return

    # Related-doc counts
    counts = {
        "enrollments":            await db.enrollments.count_documents({"user_id": {"$in": victim_user_ids}}),
        "certificates":           await db.certificates.count_documents({"user_id": {"$in": victim_user_ids}, "certificate_id": {"$nin": list(PROTECTED_CERT_IDS)}}),
        "org_members":            await db.org_members.count_documents({"user_id": {"$in": victim_user_ids}}),
        "org_invites":            await db.org_invites.count_documents({"email": {"$regex": pattern, "$options": "i"}}),
        "quiz_attempts":          await db.quiz_attempts.count_documents({"user_id": {"$in": victim_user_ids}}),
        "assessment_attempts":    await db.assessment_attempts.count_documents({"user_id": {"$in": victim_user_ids}}),
        "mentor_sessions":        await db.mentor_sessions.count_documents({"user_id": {"$in": victim_user_ids}}),
        "payment_transactions":   await db.payment_transactions.count_documents({"user_id": {"$in": victim_user_ids}}),
        "password_reset_tokens":  await db.password_reset_tokens.count_documents({"user_id": {"$in": victim_user_ids}}),
    }
    log.info(f"Cascade delete targets: {counts}")

    # Orgs where 100% of remaining members are victims → drop
    orphaned_orgs = []
    async for org in db.organizations.find({}, {"_id": 0, "id": 1, "name": 1, "slug": 1}):
        remaining = await db.org_members.count_documents({
            "org_id": org["id"],
            "user_id": {"$nin": victim_user_ids},
        })
        if remaining == 0:
            orphaned_orgs.append(org["id"])
    log.info(f"Orgs to drop (all members are victims): {len(orphaned_orgs)}")

    if dry_run:
        log.info("=== DRY RUN — no writes performed. Re-run with --confirm to actually delete. ===")
        return

    # Actually delete
    r_users = await db.users.delete_many({"id": {"$in": victim_user_ids}})
    r_enroll = await db.enrollments.delete_many({"user_id": {"$in": victim_user_ids}})
    r_certs = await db.certificates.delete_many({"user_id": {"$in": victim_user_ids}, "certificate_id": {"$nin": list(PROTECTED_CERT_IDS)}})
    r_members = await db.org_members.delete_many({"user_id": {"$in": victim_user_ids}})
    r_invites = await db.org_invites.delete_many({"email": {"$regex": pattern, "$options": "i"}})
    r_quiz = await db.quiz_attempts.delete_many({"user_id": {"$in": victim_user_ids}})
    r_assmt = await db.assessment_attempts.delete_many({"user_id": {"$in": victim_user_ids}})
    r_mentor = await db.mentor_sessions.delete_many({"user_id": {"$in": victim_user_ids}})
    r_pay = await db.payment_transactions.delete_many({"user_id": {"$in": victim_user_ids}})
    r_pwt = await db.password_reset_tokens.delete_many({"user_id": {"$in": victim_user_ids}})
    r_orgs = await db.organizations.delete_many({"id": {"$in": orphaned_orgs}})
    # Also drop rate-limit buckets since victim emails might be in them
    await db.pw_reset_rate.delete_many({})

    log.info(
        "Deleted: "
        f"users={r_users.deleted_count}, "
        f"enrollments={r_enroll.deleted_count}, "
        f"certificates={r_certs.deleted_count}, "
        f"org_members={r_members.deleted_count}, "
        f"org_invites={r_invites.deleted_count}, "
        f"quiz_attempts={r_quiz.deleted_count}, "
        f"assessment_attempts={r_assmt.deleted_count}, "
        f"mentor_sessions={r_mentor.deleted_count}, "
        f"payment_transactions={r_pay.deleted_count}, "
        f"password_reset_tokens={r_pwt.deleted_count}, "
        f"orgs={r_orgs.deleted_count}"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pattern", default="@example.com", help="Regex to match victim emails (default: @example.com).")
    p.add_argument("--keep-email", action="append", default=[], help="Additional emails to preserve (repeat flag).")
    p.add_argument("--dry-run", action="store_true", help="Show what would be deleted (default).")
    p.add_argument("--confirm", action="store_true", help="Actually delete.")
    args = p.parse_args()
    dry = args.dry_run or not args.confirm
    asyncio.run(purge(args.pattern, set(args.keep_email), dry_run=dry))


if __name__ == "__main__":
    main()
