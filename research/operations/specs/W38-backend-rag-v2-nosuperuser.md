# W38 — Demote `backend_rag_v2` from SUPERUSER (defense-in-depth)

**Status**: DRAFT — PENDING ANTONELLO APPROVAL — **DO NOT EXECUTE**
**Severity**: P1 SECURITY
**Discovered by**: W36 audit closure 2026-05-23 ~04:30 WITA during T3.2 Postgres MCP install (cicatrix line ~770 of `cicatrix-scars.md`)
**Auditor**: W38 (Claude Opus 4.7), 2026-05-23 ~07:45 WITA
**Audit snapshot**: `research/operations/audits/2026-05-23-w38-backend-rag-v2-rolsuper-audit.json`
**Touch scope**: production Postgres role + 1 new Fly secret (`ADMIN_DATABASE_URL`)
**Reversibility**: trivial (single `ALTER ROLE backend_rag_v2 SUPERUSER` rollback)

---

## 1. Audit findings (read-only, 2026-05-23 07:30 WITA)

Connected as `backend_rag_v2` via DSN from Fly secret `DATABASE_URL` (psql executed inside Fly machine `7847d95ce257d8`, app `nuzantara-rag`).

### 1.1 `backend_rag_v2` role attributes

```
rolname          = backend_rag_v2
rolsuper         = t     ⚠️ FULL SUPERUSER
rolinherit       = t
rolcreaterole    = f
rolcreatedb      = f
rolcanlogin      = t
rolreplication   = f
rolbypassrls     = f
rolconnlimit     = -1    (unlimited)
rolvaliduntil    = null  (never expires)
```

**Conclusion**: `rolsuper=t` is STILL the live state (not stale memory). Plus `rolinherit=t` means the role auto-inherits any group it's added to.

### 1.2 Other superuser roles in DB

```
backend_rag_v2     SUPER LOGIN  ← app role (the target of this spec)
backend_ts_user    SUPER LOGIN  ← timescale? not used by app
flypgadmin         SUPER LOGIN  ← Fly platform
nuzantara_memory   SUPER LOGIN  ← legacy (cf. nuzantara_memory DB)
nuzantara_rag      SUPER LOGIN  ← legacy (cf. nuzantara_rag DB ownership)
postgres           SUPER CREATEROLE CREATEDB LOGIN REPL  ← Stolon/PG bootstrap
repmgr             SUPER LOGIN  ← replication manager
zantara_rag_user   SUPER LOGIN  ← legacy (owns pgcrypto + uuid-ossp)
nuzantara_readonly LOGIN        ← T3.2 readonly (the ONLY non-super non-platform role)
```

Eight superuser roles in total; `backend_rag_v2` is the only one used by the application code (verified via `pg_stat_activity` sample).

### 1.3 Live activity sample (`pg_stat_activity` filtered to `usename='backend_rag_v2'`)

All 30 sampled queries are **routine CRUD** — no DDL observed in any active session:

- `UPDATE whatsapp_team_sessions SET status='connected'…` (wa-mirror)
- `SELECT id, channel, payload FROM events_outbox WHERE channel = ANY($1)…` (outbox poller)
- `SELECT pg_advisory_unlock_all(); CLOSE ALL; UNLISTEN *; RESET ALL;` (connection-pool reset)
- `SELECT 1` (asyncpg liveness ping)

**Zero queries requiring superuser observed in 30-row sample.** Runtime DDL paths exist in code (see §1.5) but are infrequent and idempotent.

### 1.4 Schema / object footprint

| Schema        | Owner               | Tables | Sequences | Views |
| ------------- | ------------------- | -----: | --------: | ----: |
| `public`      | `pg_database_owner` |    239 |       151 |    21 |
| `mata_garuda` | `backend_rag_v2`    |      0 |         0 |     0 |

- 227 of the 239 public tables are owned by `backend_rag_v2` directly (so it has implicit ALL via OWNER role).
- The 12 non-owned tables already have explicit grants (244 entries × 7 privilege types) per migration 156 + T3.2.
- `mata_garuda` schema is owned by `backend_rag_v2` but currently empty (intel pipeline runs but stores in `public.*`).

### 1.5 DDL paths in application runtime code

| Path                                                | What                                                                                                                                              | When                                                                                     |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `apps/backend-rag/backend/db/migration_manager.py`  | `python -m backend.db.migrate apply-all` runner — `CREATE TABLE _schema_versions IF NOT EXISTS` + each SQL file                                   | Once per CD deploy via `flyctl ssh console` (see `.github/workflows/fly-deploy.yml:151`) |
| Migration `*.sql` files                             | `CREATE EXTENSION IF NOT EXISTS {pg_trgm,postgis,pgcrypto,pg_stat_statements}` (8 occurrences across migrations 055/081b/092/103/167/169/109/185) | Once per CD deploy (idempotent, no-ops if already installed)                             |
| `backend/app/routers/dashboard.py:897`              | `CREATE TABLE IF NOT EXISTS analytics_map_lookups`                                                                                                | Lazy at first dashboard request (cold-start path)                                        |
| `backend/app/services/crm/audit_logger.py:376`      | `CREATE TABLE IF NOT EXISTS crm_audit_log`                                                                                                        | Lazy at first CRM audit write                                                            |
| `backend/services/crm/client_core.py:594`           | `await conn.execute(CREATE_AUDIT_TABLE_SQL)`                                                                                                      | Lazy at first client_core call                                                           |
| `backend/services/olympus/pulse.py:149-150,449,477` | `ALTER TABLE api_audit_trail DETACH PARTITION`, `DROP TABLE {old_partition}`, `CREATE TABLE {new} PARTITION OF olympus_heartbeats`                | Olympus pulse cron (partition rotation)                                                  |

**All of these are idempotent or operate on owner-controlled tables** — they DO NOT actually require `rolsuper=t`. They require:

- `CREATE EXTENSION` → requires superuser OR membership in `pg_create_subscription` (PG ≥ 15) OR explicit grant on extension OR pre-installation
- `CREATE TABLE` / `ALTER TABLE` / `DROP TABLE` on owned tables → requires OWNER, which `backend_rag_v2` already has on 227/239 tables
- `CREATE TABLE … PARTITION OF` → requires OWNER on parent table → `olympus_heartbeats` is owned by `backend_rag_v2`

### 1.6 Extensions owned by `backend_rag_v2`

```
pg_trgm    1.6     (public)
postgis    3.5.2   (public)
```

Two other extensions (`pgcrypto`, `uuid-ossp`) are owned by legacy role `zantara_rag_user`; `plpgsql` is owned by `postgres`. If we ALTER ROLE NOSUPERUSER, ownership is preserved (extensions stay).

### 1.7 No CREATE ROLE / ALTER SYSTEM / pg_hba / COPY-PROGRAM in codebase

```
grep -rn "CREATE ROLE\|ALTER SYSTEM\|pg_hba\|COPY .* FROM PROGRAM" apps/backend-rag/ → 0 matches
```

No legitimate runtime use case for `rolsuper=t`.

---

## 2. Permission set the app actually needs

### 2.1 Object-level (already in place)

- **OWNER** on 227 of 239 public tables → keeps ALL on those (SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER + DDL on owned)
- **GRANT** on 12 non-owned public tables (244 entries × 7 privileges already present from migration 156 + cross-grants)
- **USAGE** on `public` and `mata_garuda` schemas (mata_garuda is owned)
- **USAGE** on 151 sequences (auto-inherited via OWNER on parent tables, plus explicit grants from `ALTER DEFAULT PRIVILEGES` in T3.2 era)

### 2.2 Role memberships (currently zero — need to add)

| Role                | What it enables                                      | Required by                                             |
| ------------------- | ---------------------------------------------------- | ------------------------------------------------------- |
| `pg_monitor`        | `pg_ls_waldir()`, `pg_stat_activity` full visibility | `health_monitor.py:280` (explicitly documented in code) |
| `pg_read_all_stats` | (subset of pg_monitor)                               | redundant if pg_monitor granted                         |
| `pg_signal_backend` | `pg_terminate_backend()` for self-cleanup            | possibly outbox cleanup — verify with grep              |

### 2.3 Extension creation — the only real ceiling

`CREATE EXTENSION` is the **single capability** that genuinely requires elevated privilege post-demotion:

- Postgres ≥ 13 introduced "trusted extensions" — these CAN be created by any role with CREATE on the target schema:
  - `pg_trgm` (trusted ✅)
  - `pgcrypto` (trusted ✅)
  - `pgstattuple` (trusted ✅)
- Not trusted (still require superuser):
  - `postgis` (NOT trusted)
  - `pg_stat_statements` (NOT trusted, also requires `shared_preload_libraries`)

**Implication**: 6 of the 8 existing `CREATE EXTENSION` calls in migrations will work post-demotion because the extension is ALREADY installed (`IF NOT EXISTS` no-op). NEW migrations that need a NEW non-trusted extension would fail.

### 2.4 The proposed fix: introduce `ADMIN_DATABASE_URL` for migrations

Migration runner is the ONLY code path that legitimately needs DDL elevation. Split DSN responsibilities:

```
DATABASE_URL       = postgres://backend_rag_v2:…@…    (NOSUPERUSER — app runtime)
ADMIN_DATABASE_URL = postgres://flypgadmin:…@…        (SUPERUSER — migrations only)
```

`backend/db/migration_manager.py` reads `ADMIN_DATABASE_URL` if set, falls back to `DATABASE_URL` for local dev. The deploy workflow already runs migrations in a separate step (`.github/workflows/fly-deploy.yml:134`), so this is a localized change.

---

## 3. Migration plan (3 stages)

### Stage A — Pre-flight (no production change, ~30 min)

1. **Audit `pg_signal_backend` usage**: `grep -rn "pg_terminate_backend\|pg_cancel_backend" apps/backend-rag/` — if any, decide GRANT pg_signal_backend OR refactor.
2. **Empirical CREATE TABLE test on staging clone** OR on a throwaway namespace in prod:
   - In prod (safe): create `nuzantara_readonly_test` role via `flypgadmin`, run the proposed grants, verify identical behavior to current `backend_rag_v2` for a SELECT-INSERT-UPDATE-CREATE TABLE workload
3. **Verify Olympus pulse partition rotation works without superuser** — `olympus_heartbeats` is owned by `backend_rag_v2`, ownership is preserved, so this should work post-demotion; but test once.
4. **Document the `ADMIN_DATABASE_URL` for `flypgadmin`** — extract from Fly Postgres via `repmgr` or `fly secrets list -a nuzantara-postgres` (if accessible).

**Gate**: all pre-flight smoke green AND Antonello signs off → proceed to Stage B.

### Stage B — Code + secret prep (no DB change, ~20 min)

1. **Patch `backend/db/migration_manager.py`**: read `ADMIN_DATABASE_URL` first, fall back to `DATABASE_URL`.
2. **Add `ADMIN_DATABASE_URL` Fly secret**: `fly secrets set ADMIN_DATABASE_URL='postgres://flypgadmin:<pwd>@nuzantara-postgres.flycast:5432/nuzantara_rag?sslmode=disable' -a nuzantara-rag --stage` (staged, applied next deploy).
3. **GRANT pg_monitor TO backend_rag_v2** (run as `repmgr` via `fly ssh console`). Idempotent.
4. **Optional: GRANT pg_signal_backend TO backend_rag_v2** if §3.A.1 found usage.
5. **Deploy via standard `fly deploy` rolling** — migration runner now uses admin DSN, app runtime still uses `backend_rag_v2` (still SUPER at this point — no functional change yet).

**Gate**: deploy green, `pg_stat_activity` shows migrations running as `flypgadmin`, all health checks pass → proceed to Stage C.

### Stage C — The actual demotion (~5 min execution + 24h observation)

**Recommended window**: Sunday 03:00-05:00 WITA (low traffic per `api_audit_trail` analysis). Avoid:

- 09:00-18:00 WITA (Bali Zero business hours — KITAS/visa clients active)
- Mon/Tue 10:00 WITA (regulatory-watcher.30min cron + Telegram alerts)
- Wed 08:00 + Sun 16:00 (wr-topic + judgement-day crons)

1. **Pre-execution**: `fly status -a nuzantara-rag` → all green; `mem save` checkpoint
2. **Execute** (single statement, via `fly ssh console -a nuzantara-rag` → `psql -h nuzantara-postgres.flycast -U repmgr -d nuzantara_rag`):

   ```sql
   ALTER ROLE backend_rag_v2 NOSUPERUSER;
   ```

3. **Immediate verification** (within 60s):
   - `SELECT rolname, rolsuper FROM pg_roles WHERE rolname='backend_rag_v2';` → expect `t` → `f`
   - Smoke: `curl https://nuzantara-rag.fly.dev/health` → 200
   - Smoke: `mcp__nuzantara-mcp__check_health` → 200
   - Smoke: `mcp__nuzantara-mcp__list_clients limit=1` → 1 client returned (proves SELECT works)

4. **24h observability window**:
   - Cell organism telegram alerts for any red-tier (post-W27 dedup 30min)
   - `~/scripts/audit-launchd-daily.sh` next-day delta tracks any new HOT failures
   - Manual spot-check Olympus pulse cron at next fire (CREATE TABLE PARTITION OF olympus_heartbeats works?)

**Gate**: zero HOT failures + 0 PEL accumulation surge + Olympus partition rotation green → Stage C complete.

---

## 4. Rollback plan

**Single statement** (executable in <5 seconds):

```sql
ALTER ROLE backend_rag_v2 SUPERUSER;
```

Run via `fly ssh console -a nuzantara-rag` as `repmgr`. No deploy needed. No data risk.

**Trigger criteria**:

- App health degrades within 5 min of Stage C execution
- Any non-recoverable `permission denied` in `/app/logs/app.log`
- Olympus pulse cron fails with `permission denied` on next fire
- Sentry capture of `psycopg.errors.InsufficientPrivilege` or asyncpg `PostgresPermissionError`

**Post-rollback investigation**: enumerate which capability triggered the failure, decide between (a) explicit GRANT for that capability OR (b) abandon the demotion until the affected code path is refactored.

---

## 5. Risk assessment per backend service

| Service                                                 | Risk                                                    | Mitigation                                                                                  |
| ------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **CRM + clients API**                                   | LOW — only CRUD on owned tables                         | OWNER preserves ALL → no change                                                             |
| **RAG query/ingest**                                    | LOW — SELECT on `parent_documents`, INSERT on `vectors` | All owned tables                                                                            |
| **wa-mirror (WhatsApp)**                                | LOW — CRUD on `whatsapp_*` tables                       | All owned tables                                                                            |
| **events_outbox**                                       | LOW — pub/sub via `pg_notify` + table CRUD              | `pg_notify` works without superuser                                                         |
| **Olympus pulse partition rotation**                    | MEDIUM — DROP TABLE + CREATE PARTITION + ALTER DETACH   | OWNER on `olympus_heartbeats` parent table → operations on partitions OK; verify in Stage A |
| **`/health` endpoint pg_monitor probe**                 | MEDIUM — `pg_ls_waldir()` needs `pg_monitor`            | Stage B GRANT pg_monitor explicit                                                           |
| **Migrations runner (`apply-all`)**                     | HIGH — CREATE EXTENSION on non-trusted extensions       | Stage B introduces `ADMIN_DATABASE_URL` w/ `flypgadmin`                                     |
| **mata_garuda intel pipeline**                          | LOW — schema owned by `backend_rag_v2`, currently empty | No change                                                                                   |
| **Cron jobs (regulatory-watcher, dlq-autopilot, etc.)** | LOW — same connection pool as app                       | Inherits NOSUPERUSER via shared `DATABASE_URL`                                              |

**Overall risk**: MEDIUM-LOW after Stages A+B mitigations.

---

## 6. Recommended execution timing

- **Stages A+B**: any weekday, Antonello available, expect ~50 min total wall
- **Stage C**: **Sunday 03:00 WITA** (best window):
  - Lowest CRM/wa-mirror traffic
  - No critical cron firing (judgement-day at 16:00 leaves 13h grace)
  - Easy rollback window if anything breaks
  - Antonello available for monitoring during execution

**NOT recommended**:

- Friday afternoon (weekend incident response harder)
- During or within 48h of any other prod DB schema change

---

## 7. Out of scope

- **Other 7 superuser roles** (`backend_ts_user`, `nuzantara_memory`, `nuzantara_rag`, `zantara_rag_user`): legacy / Fly platform. Separate spec if needed.
- **`flypgadmin` rotation**: Fly platform-managed; not our concern.
- **Per-table grant audit on the 12 non-owned public tables**: already done in migration 156 + T3.2 cascade.
- **RLS (Row-Level Security)**: orthogonal — apply per-table independently if needed.
- **Migration to non-Fly Postgres**: out of scope.

---

## 8. Open questions for Antonello

1. **Approve Stage A (pre-flight tests in prod with throwaway role)?** Yes / No
2. **Approve Stage B (`ADMIN_DATABASE_URL` secret + code patch + GRANT pg_monitor)?** Yes / No
3. **Approve Stage C (ALTER ROLE NOSUPERUSER) execution window?** Sunday 03:00 WITA / other
4. **Optional bonus**: Demote `nuzantara_memory` + `nuzantara_rag` + `zantara_rag_user` legacy roles too? (separate ticket — these aren't used by app but are attack surface if any rogue script connects with them)

---

## 9. References

- Audit snapshot: `research/operations/audits/2026-05-23-w38-backend-rag-v2-rolsuper-audit.json`
- Original discovery: `.claude/rules/cicatrix-scars.md` cicatrix 2026-05-23 RESOLVED T3.2 (~ line 770, "PHASE 1 — fly ssh read-only metadata investigation discovered 4 critical facts")
- T3.2 spec: `research/operations/specs/T3.2-postgres-qdrant-mcp.md` (901 lines, iter-5)
- Fly deploy workflow: `.github/workflows/fly-deploy.yml` (migration step lines 134-152)
- Migration runner: `apps/backend-rag/backend/db/migration_manager.py:98-108`
- pg_monitor requirement: `apps/backend-rag/backend/services/monitoring/health_monitor.py:280-291`
- Postgres trusted extensions list: https://www.postgresql.org/docs/current/contrib.html
