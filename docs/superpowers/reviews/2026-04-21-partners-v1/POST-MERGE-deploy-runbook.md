# Post-merge deploy runbook — Partners v1

**After PR #141 merges to main**, execute these steps in order. Nothing is automated — each is a manual check + action.

## 1. Apply migrations 119 + 120 to Fly Postgres

Migrations do NOT run automatically on Fly deploy for this project — `fly-deploy.yml` only runs the backend-rag deploy, not Alembic/migration-manager. Migrations must be applied explicitly.

### Option A: via migration runner in the deployed container

After `fly deploy` completes:

```bash
fly ssh console -a nuzantara-rag
cd /app/apps/backend-rag
python -m backend.db.migration_manager apply --target 120
# Or whatever the apply command is for this project — check the runner
```

### Option B: apply manually via psql

```bash
fly ssh console -a nuzantara-postgres
psql -U postgres -d nuzantara

# Verify migrations 118 is present and nothing higher
SELECT version, applied_at FROM schema_migrations ORDER BY version DESC LIMIT 10;

# Exit psql; inside backend container:
cd /app/apps/backend-rag
python -c "
import asyncio, asyncpg, os
from backend.migrations.migration_119_partners import apply as apply_119
from backend.migrations.migration_120_partner_email_outbox import apply as apply_120

async def go():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await apply_119(conn)
    await apply_120(conn)
    # Record in schema_migrations if that's the project convention
    await conn.close()

asyncio.run(go())
"
```

### Verify schema

```bash
fly ssh console -a nuzantara-postgres
psql -U postgres -d nuzantara -c "\d partners"
psql -U postgres -d nuzantara -c "\d partner_referrals"
psql -U postgres -d nuzantara -c "\d partner_commissions"
psql -U postgres -d nuzantara -c "\d partner_audit_log"
psql -U postgres -d nuzantara -c "\d partner_email_outbox"
```

Expected: 4 tables + outbox, all `practice_id` columns are `INTEGER` referencing `practices(id)`.

### Verify system_settings

```sql
SELECT key, value FROM system_settings WHERE key LIKE 'partner_%' ORDER BY key;
```

Expected rows:
- `partner_accrual_cooling_off_days = 30`
- `partner_clawback_auto_writeoff_idr = 0`
- `partner_withholding_no_npwp_surcharge = 20`
- `partner_withholding_rate_pph21 = 2.5`
- `partner_withholding_rate_pph23 = 2.0`

## 2. Smoke endpoints

With an admin JWT cookie:

```bash
# List partners (should return empty envelope)
curl -s https://nuzantara-rag.fly.dev/api/partners \
  -H "Cookie: nz_access_token=$JWT" | jq .

# Expected: {"partners": [], "total": 0, "page": 1, "page_size": 50}
```

With NO JWT:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nuzantara-rag.fly.dev/api/partners
# Expected: 401 (or 403) — NOT 200 with data
```

With a partner-role JWT (once one exists):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nuzantara-rag.fly.dev/api/partners \
  -H "Cookie: nz_access_token=$PARTNER_JWT"
# Expected: 403 (CATA-2 gate)
```

## 3. Trigger accrual end-to-end

**Prerequisite: Asya has confirmed withholding rates (see ASYA-withholding-rates-runbook.md).**

Create a real partner via the team portal:

1. `/portal/partners/new` → fill form, submit.
2. As admin: `/portal/partners/{id}` → click Activate.
3. Verify: `SELECT welcome_email_sent_at FROM partners WHERE id = '...';` — should populate AFTER the outbox is flushed (next step).
4. Flush outbox: `POST /api/partners/outbox/flush` with admin+finance JWT.
5. Verify partner received welcome email at their address.

Then, attach the partner to a real practice:

1. `/portal/process/new` → select referrer from ReferrerDropdown.
2. Save process. Verify `SELECT * FROM partner_referrals WHERE partner_id = '...';` returns the new row.
3. Complete the process and mark it paid (via the normal practice workflow, NOT the partners UI).
4. Watch Fly logs: `fly logs -a nuzantara-rag | grep -iE "partner|accrue|commission"`.
5. Expected: handler fires within seconds of practice.status flipping; new row in `partner_commissions` with `status='accrued'` and `eligible_for_approval_at = completed_at + 30 days`.

## 4. Start v1.1 tracking

All 11 Important issues from the council synthesis are queued for v1.1. Owner: TBD. Tracked in `docs/superpowers/reviews/2026-04-21-partners-v1/99-synthesis.md` §Important.

Top 3 to prioritize for v1.1 (per post-deploy observations):

- **IMP-6 Email TOCTOU + case-sensitivity** — Real risk if a team member is added with an email that collides with an existing partner. Fix = SERIALIZABLE txn wrapper.
- **IMP-10 Brevo retry + circuit breaker** — v1 outbox has backoff + DLQ but no circuit breaker. One Brevo outage with 50+ pending emails = backlog that takes hours to drain.
- **IMP-5 `update_partner` audit failure mode** — if json.dumps raises on Decimal/UUID, commit happens but audit silently skipped. Defensive JSON encoder fix.

## 5. Monitor for the first week

Fly logs to watch:

```bash
fly logs -a nuzantara-rag | grep -E "partner|accrue|commission|outbox" 
```

Alert triggers to consider (manual for now):

- Any accrual where `withholding_category='tbd'` at insert time → partner record incomplete.
- Any `partner_email_outbox` row in `failed_dlq` status → Brevo / config issue.
- Any `partner_commissions` row where `eligible_for_approval_at` was >60 days ago and still `status='accrued'` → approval workflow stalled.
