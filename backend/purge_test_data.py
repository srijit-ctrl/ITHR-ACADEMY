"""Purge accumulated test/dummy data from the DB.

Safely removes users whose emails match one or more of the built-in
"testing-agent noise" patterns, plus their cascading data (enrollments,
certificates, org memberships, quiz attempts, etc.). Organisations whose
100% of remaining members were victims are also dropped.

The built-in patterns catch every leftover from the last 30+ test-agent
iterations we've shipped:
    - @example.com                  (generic test signup)
    - .test$                        (RFC 2606 reserved TLD)
    - @ex.com                       (org-flow smoke tests)
    - @iter16orgs.example.com       (iter-16 org test corpus)
    - @ui16orgs.example.com         (iter-16 UI test corpus)
    - @acme.com and @acme-*         (Acme-Co seed users)
    - @foo.com / @bar.com / @baz    (unit-test generics)
    - +test-, +iter-, +debug-       (namespaced local-part suffixes)
    - test.learner+                 (main-agent regression accounts)

Preserves:
    - Both super-admin accounts (superadmin@ithr.online, @ithr.tech)
    - srijit@ithr360.com and any custom --keep-email
    - By default, SAMPLE-ITHR-2026-001 (opt-in --drop-sample-cert to remove)
    - All courses, assessments, intelligence signals, podcast episodes

Usage:
    # 1) DRY-RUN — safe, shows what would happen
    python -m purge_test_data --dry-run

    # 2) Actually delete
    python -m purge_test_data --confirm

    # 3) Also drop the seeded SAMPLE certificate
    python -m purge_test_data --confirm --drop-sample-cert

    # 4) Custom extra patterns (comma-separated regex)
    python -m purge_test_data --extra-patterns "@acme2.co,@stress-test\\." --confirm

    # 5) Custom protected emails (repeat flag)
    python -m purge_test_data --keep-email founder@ithr.online --confirm

PRODUCTION NOTE
---------------
This script writes to whichever MongoDB the process env points at (MONGO_URL +
DB_NAME). Run it inside the *production pod* (not from your laptop) so
network + IP allow-lists are honoured. Always start with --dry-run.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("purge_test_data")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
if not (MONGO_URL and DB_NAME):
    raise SystemExit("MONGO_URL + DB_NAME must be set.")

# Always-preserved accounts. Add any founding/employee emails here.
PROTECTED_EMAILS = {
    "superadmin@ithr.tech",
    "superadmin@ithr.online",
    "srijit@ithr360.com",
    "sri0564823232@gmail.com",  # user's personal test account — keep
}
PROTECTED_CERT_IDS = {"SAMPLE-ITHR-2026-001"}

# Built-in testing-agent noise patterns. Any user whose email matches ANY of
# these regexes is a purge candidate (unless in PROTECTED_EMAILS).
DEFAULT_PATTERNS: list[str] = [
    r"@example\.com$",
    r"\.test$",                          # any .test TLD
    r"@ex\.com$",
    r"@iter\d+[a-z-]*\.example\.com$",   # iter16orgs / iter20-<hex> / iter30ui-<hex> ...
    r"@ui\d+orgs\.example\.com$",
    r"@iter\d+-[a-f0-9]+\.example\.com$",
    r"@acme\.com$",
    r"@acme-[a-f0-9]+\.test$",
    r"@acmecorp[a-f0-9]+\.com$",         # iter22 / iter23 acmecorp variants
    r"@foo\.com$",
    r"@bar\.com$",
    r"@baz\.",
    r"\+iter\d*-",                       # local-part namespaces used in tests
    r"\+debug-",
    r"\+stress-",
    r"^test\.learner\+",
    r"^orgtest\.\d+",
    r"^orgdebug\.\d+",
    r"^iter\d+\.",                       # iter22.newuser+..., iter30.mem+...
    r"^cto\+[a-f0-9]+@",
    r"^admin\+[a-f0-9]+@iter\d+",
    r"^emp\+[a-z0-9]+@iter\d+",
]


def _build_regex(patterns: list[str]) -> str:
    """Combine patterns with alternation. Anchoring is baked into each pattern."""
    return "|".join(f"(?:{p})" for p in patterns)


async def purge(
    patterns: list[str],
    keep_emails: set[str],
    dry_run: bool,
    drop_sample_cert: bool,
):
    from core import db  # reuse the app's Motor pool (works for CLI + endpoint)

    combined = _build_regex(patterns)
    protected = PROTECTED_EMAILS | keep_emails
    query = {"$and": [
        {"email": {"$regex": combined, "$options": "i"}},
        {"email": {"$nin": list(protected)}},
    ]}

    victim_user_ids: list[str] = []
    victim_emails: list[str] = []
    async for u in db.users.find(query, {"_id": 0, "id": 1, "email": 1}):
        victim_user_ids.append(u["id"])
        victim_emails.append(u["email"])

    total_users = await db.users.count_documents({})
    log.info(f"DB: {DB_NAME} @ {MONGO_URL.split('@')[-1]}")
    log.info(f"Users: total={total_users}  protected={len(protected)}  victims={len(victim_user_ids)}")
    if victim_emails:
        preview = victim_emails[:5]
        log.info(f"First victims: {preview}{'  ...' if len(victim_emails) > 5 else ''}")

    protected_cert_set = set() if drop_sample_cert else PROTECTED_CERT_IDS

    # Cascade delete inventory
    counts = {
        "enrollments":            await db.enrollments.count_documents({"user_id": {"$in": victim_user_ids}}),
        "certificates":           await db.certificates.count_documents({"user_id": {"$in": victim_user_ids}, "certificate_id": {"$nin": list(protected_cert_set)}}),
        "org_members":            await db.org_members.count_documents({"user_id": {"$in": victim_user_ids}}),
        "org_invites":            await db.org_invites.count_documents({"email": {"$regex": combined, "$options": "i"}}),
        "quiz_attempts":          await db.quiz_attempts.count_documents({"user_id": {"$in": victim_user_ids}}),
        "assessment_attempts":    await db.assessment_attempts.count_documents({"user_id": {"$in": victim_user_ids}}),
        "mentor_sessions":        await db.mentor_sessions.count_documents({"user_id": {"$in": victim_user_ids}}),
        "payment_transactions":   await db.payment_transactions.count_documents({"user_id": {"$in": victim_user_ids}}),
        "password_reset_tokens":  await db.password_reset_tokens.count_documents({"user_id": {"$in": victim_user_ids}}),
        "user_login_logs":        await db.user_login_logs.count_documents({"user_id": {"$in": victim_user_ids}}),
        "tutor_sessions":         await db.tutor_sessions.count_documents({"user_id": {"$in": victim_user_ids}}),
        "checkpoint_attempts":    await db.checkpoint_attempts.count_documents({"user_id": {"$in": victim_user_ids}}),
        "verify_impressions":     await db.verify_impressions.count_documents({"user_id": {"$in": victim_user_ids}}),
        "activity_events":        await db.activity_events.count_documents({"actor_id": {"$in": victim_user_ids}}),
        "admin_audit_log":        await db.admin_audit_log.count_documents({"$or": [{"target_id": {"$in": victim_user_ids}}, {"actor_id": {"$in": victim_user_ids}}]}),
    }
    log.info(f"Cascade delete targets: {counts}")

    # Orgs where every remaining member is a victim → drop (empty shell)
    orphaned_orgs: list[str] = []
    async for org in db.organizations.find({}, {"_id": 0, "id": 1, "name": 1}):
        remaining = await db.org_members.count_documents({
            "org_id": org["id"],
            "user_id": {"$nin": victim_user_ids},
        })
        if remaining == 0:
            orphaned_orgs.append(org["id"])
    log.info(f"Orgs to drop (all members are victims): {len(orphaned_orgs)}")

    # Optional: sample certificate
    sample_dropped_target = 0
    if drop_sample_cert:
        sample_dropped_target = await db.certificates.count_documents({"certificate_id": {"$in": list(PROTECTED_CERT_IDS)}})
        log.info(f"SAMPLE cert dropping: {sample_dropped_target} doc(s)  ({', '.join(PROTECTED_CERT_IDS)})")

    if dry_run:
        log.info("=== DRY RUN — no writes. Re-run with --confirm to actually delete. ===")
        return {
            "dry_run": True,
            "total_users": total_users,
            "victims": len(victim_user_ids),
            "victim_preview": victim_emails[:5],
            "cascade": counts,
            "orphaned_orgs": len(orphaned_orgs),
        }

    # Actually delete
    deleted_users = 0
    if victim_user_ids:
        r_users = await db.users.delete_many({"id": {"$in": victim_user_ids}})
        deleted_users = r_users.deleted_count
        r_enroll = await db.enrollments.delete_many({"user_id": {"$in": victim_user_ids}})
        r_certs = await db.certificates.delete_many({"user_id": {"$in": victim_user_ids}, "certificate_id": {"$nin": list(protected_cert_set)}})
        r_members = await db.org_members.delete_many({"user_id": {"$in": victim_user_ids}})
        r_invites = await db.org_invites.delete_many({"email": {"$regex": combined, "$options": "i"}})
        r_quiz = await db.quiz_attempts.delete_many({"user_id": {"$in": victim_user_ids}})
        r_assmt = await db.assessment_attempts.delete_many({"user_id": {"$in": victim_user_ids}})
        r_mentor = await db.mentor_sessions.delete_many({"user_id": {"$in": victim_user_ids}})
        r_pay = await db.payment_transactions.delete_many({"user_id": {"$in": victim_user_ids}})
        r_pwt = await db.password_reset_tokens.delete_many({"user_id": {"$in": victim_user_ids}})
        r_logs = await db.user_login_logs.delete_many({"user_id": {"$in": victim_user_ids}})
        r_tutor = await db.tutor_sessions.delete_many({"user_id": {"$in": victim_user_ids}})
        r_cp = await db.checkpoint_attempts.delete_many({"user_id": {"$in": victim_user_ids}})
        r_vi = await db.verify_impressions.delete_many({"user_id": {"$in": victim_user_ids}})
        r_act = await db.activity_events.delete_many({"actor_id": {"$in": victim_user_ids}})
        r_audit = await db.admin_audit_log.delete_many({"$or": [{"target_id": {"$in": victim_user_ids}}, {"actor_id": {"$in": victim_user_ids}}]})
        r_orgs = await db.organizations.delete_many({"id": {"$in": orphaned_orgs}})
        # Reset rate-limit buckets (may hold victim IPs/emails)
        await db.pw_reset_rate.delete_many({})

        log.info(
            "Deleted:  "
            f"users={r_users.deleted_count}  enroll={r_enroll.deleted_count}  "
            f"certs={r_certs.deleted_count}  org_members={r_members.deleted_count}  "
            f"org_invites={r_invites.deleted_count}  quiz={r_quiz.deleted_count}  "
            f"assmt={r_assmt.deleted_count}  mentor={r_mentor.deleted_count}  "
            f"pay={r_pay.deleted_count}  pwt={r_pwt.deleted_count}  "
            f"login_logs={r_logs.deleted_count}  tutor={r_tutor.deleted_count}  "
            f"checkpoints={r_cp.deleted_count}  impressions={r_vi.deleted_count}  "
            f"activity={r_act.deleted_count}  audit={r_audit.deleted_count}  "
            f"orgs={r_orgs.deleted_count}"
        )
    else:
        log.info("No victim users — skipping user-cascade deletes.")

    if drop_sample_cert:
        r_sample = await db.certificates.delete_many({"certificate_id": {"$in": list(PROTECTED_CERT_IDS)}})
        log.info(f"SAMPLE certs dropped: {r_sample.deleted_count}. "
                 "Set SEED_SAMPLE_CERT=false in the pod env to prevent re-seeding on next backend restart.")

    # Post-pass: sweep dashboard rows orphaned by this (or any earlier) purge —
    # activity-feed events and user-targeted audit entries that reference users
    # who no longer exist.
    remaining_ids = [u["id"] async for u in db.users.find({}, {"_id": 0, "id": 1})]
    r_act_orphan = await db.activity_events.delete_many(
        {"actor_id": {"$nin": remaining_ids + [None]}}
    )
    r_audit_orphan = await db.admin_audit_log.delete_many(
        {"action": {"$regex": r"^user\."}, "target_id": {"$nin": remaining_ids}}
    )
    log.info(f"Orphan sweep: activity_events={r_act_orphan.deleted_count}  admin_audit_log(user.*)={r_audit_orphan.deleted_count}")

    # Post-run sanity: real learner accounts remaining
    remaining = await db.users.count_documents({})
    log.info(f"Post-purge user count: {remaining}")
    return {
        "dry_run": False,
        "victims": len(victim_user_ids),
        "deleted_users": deleted_users,
        "cascade": counts,
        "orphaned_orgs": len(orphaned_orgs),
        "orphan_sweep": {
            "activity_events": r_act_orphan.deleted_count,
            "admin_audit_log": r_audit_orphan.deleted_count,
        },
        "remaining_users": remaining,
    }


def main():
    p = argparse.ArgumentParser(description="Purge test/dummy data from the DB.")
    p.add_argument(
        "--extra-patterns",
        default="",
        help="Comma-separated extra regexes to add to the default set.",
    )
    p.add_argument("--keep-email", action="append", default=[], help="Preserve this email (repeatable).")
    p.add_argument("--drop-sample-cert", action="store_true", help="Also delete SAMPLE-ITHR-2026-001 certificate.")
    p.add_argument("--dry-run", action="store_true", help="Show what would be deleted (default when --confirm missing).")
    p.add_argument("--confirm", action="store_true", help="Actually delete.")
    args = p.parse_args()

    patterns = list(DEFAULT_PATTERNS)
    if args.extra_patterns.strip():
        patterns.extend([p.strip() for p in args.extra_patterns.split(",") if p.strip()])

    dry = args.dry_run or not args.confirm
    asyncio.run(
        purge(
            patterns=patterns,
            keep_emails=set(args.keep_email),
            dry_run=dry,
            drop_sample_cert=args.drop_sample_cert,
        )
    )


if __name__ == "__main__":
    main()
