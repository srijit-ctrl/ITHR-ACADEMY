# Production Data Purge Runbook

## What this does

Removes testing-agent noise + any account matching known test patterns from
your production MongoDB, cascade-deleting their enrollments, certificates,
org memberships, quiz attempts, payment transactions, and login logs.

Protected accounts (always kept):
- `superadmin@ithr.online`, `superadmin@ithr.tech`
- `srijit@ithr360.com`
- `sri0564823232@gmail.com`
- Anything passed via `--keep-email`

## When to run

- **First-time cleanup after launch** — clear out iteration-test noise so
  the KPI dashboard reflects real traffic only. (You're doing this now.)
- **Ad-hoc** — after a testing-agent run against prod (rare).
- **Never** on a scheduled cron. Purge is a manual, deliberate operation.

## Prerequisites

- SSH / exec access to the production pod (Emergent → Home tab → Pod shell).
- Confirm the pod's `MONGO_URL` + `DB_NAME` point at production, not preview.

## Step 1 — Dry run (always do this first)

Inside the prod pod shell:

```bash
cd /app/backend
python3 -m purge_test_data --dry-run
```

Expected output:
```
INFO DB: <prod-db-name> @ <prod-cluster-host>
INFO Users: total=<N>  protected=<M>  victims=<V>
INFO First victims: [...]
INFO Cascade delete targets: {...}
INFO Orgs to drop (all members are victims): <O>
INFO === DRY RUN — no writes. Re-run with --confirm to actually delete. ===
```

**Sanity checks before continuing:**
- `victims` count is a reasonable number (not 0, not thousands).
- `First victims` list contains only obviously-test emails (`@example.com`,
  `.test`, `iter*`, `orgtest*`, `cto+*@acme-*.test`, etc.).
- If you see any legitimate learner email in the sample → **STOP** and add
  them to `--keep-email` on the next run.

## Step 2 — Commit

```bash
python3 -m purge_test_data --confirm
```

If you also want to remove the seeded sample certificate (`SAMPLE-ITHR-2026-001`)
so `/verify` requires a real credential ID going forward:

```bash
python3 -m purge_test_data --confirm --drop-sample-cert
```

**Then** set the pod env var so it doesn't re-seed on next restart:

```bash
# Emergent → App settings → Environment variables → Add:
SEED_SAMPLE_CERT=false
```

## Step 3 — Verify

```bash
python3 -c "
import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
async def main():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    print('users:', await c.users.count_documents({}))
    print('certs:', await c.certificates.count_documents({}))
    print('enrollments:', await c.enrollments.count_documents({}))
    print('orgs:', await c.organizations.count_documents({}))
    async for u in c.users.find({}, {'_id':0,'email':1,'role':1}).sort('created_at', 1):
        print(' -', u['email'], '  role=', u.get('role','learner'))
asyncio.run(main())
"
```

Then hit the super-admin KPI dashboard at `https://ithr.online/admin` — the
user count and Recharts should now show only real analytics.

## Adding extra patterns

If the built-in regexes miss a variant, extend with `--extra-patterns`:

```bash
python3 -m purge_test_data --extra-patterns "@my-new-test-domain\\.co,@stress-test" --confirm
```

## Recovering from a mistake

If you accidentally purge a real account:

1. `db.users.find({email: '<victim>'})` will return nothing.
2. If Emergent's managed DB has point-in-time backups, restore the `users`
   collection to a snapshot from just before the purge.
3. If no backup: the user must re-register. Their enrollments, certs, and
   payment history are irrecoverable (cascade-deleted).

**This is why Step 1 (dry run + sanity check) is mandatory.**

## Preventing re-accumulation

The testing agent v3 spawns accounts under `@example.com`, `iter*.example.com`,
etc. If you run testing-agent-v3 against production (not recommended!), those
accounts land in prod. Two mitigations:

1. Point testing-agent at preview only (default).
2. Schedule a monthly `python3 -m purge_test_data --confirm` as a cron job
   in your prod pod if you *do* need to test against prod.
