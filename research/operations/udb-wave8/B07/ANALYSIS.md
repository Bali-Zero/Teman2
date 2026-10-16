---
adversarial_review: codex
reviewed_source_sha256: "cdade916a3803c830e2db5a8f065f6e277187e847f93bf2e14f9b9458744831f"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# B07 Analysis — Maintenance and Migration Lineage (`D02`, `D11`, `D13`)

> **Dux addendum (2026-10-16, supersedes every conflicting statement below, including the 2026-10-15 correction).**
> Authoritative status and evidence: `RESULT.json`. `test_b07_lineage_invariants.py` runs 16 passed (exit 0) offline over the
> committed `fixtures/` (`dr01.json`, the counts-only `dr05-pro.txt` projection, `consumer-ids.csv`, `PROVENANCE.json`).
> Withdrawn as UNVERIFIED (no receipt or test supports them): alembic lineage; launchctl NOT_LOADED or loaded states; a
> `read_bytes` checksum path; a `manual-apply` stamp written by `schema_audit`; an `enable_olympus` default at `config.py:423`;
> hard-coded guardian table counts or partition-warning behaviour; a `migrate apply` release command (the source runs
> `apply-all`); `CE-09` and the S3 remediation roadmap. The 30-day prune default is not test-asserted. `CONTRACT-CONVENTIONS.md`
> and `.agent-receipts/...` paths are external, untracked campaign control files (conventions sha256
> `a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559`); line citations into them are not verifiable in this
> repository. The values B07 uses are embedded in `PR_BODY.md`. The consumer-id source is the campaign consumer matrix
> (sha256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`, 6029 rows), committed as the `consumer-ids.csv`
> projection. Statements below that something was "removed", "purged" or "dropped" are true only as far as the committed
> tree shows. The probe observer is pinned to `md5('nuzantara_readonly')` and is NOT native-admitted; no database was
> read. `block_closed` stays `false`.

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B07` — Maintenance and migration lineage
- **Host / Worktree**: `Mini` / `~/nuzantara/.worktrees/db-udb-b07-lineage`
- **Base Commit**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Role**: Gemini block lead (`EXTERNAL PREPARER, NO_DUX`)
- **Stage**: `ANALYSIS` (read-only code inspection; zero shell execution; `Facts`, `Inference`, and `Unknowns` strictly separated)

---

## 0. Frozen Input Provenance (`INPUT-MANIFEST.json`)

All baseline claims reference the frozen wave-8 input bundle at `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json` (`classification: FROZEN_DATED_TECHNICAL_BASELINE_NOT_NEW_LIVE_PROOF`, `manifest_sha256: 29972870e9021802eb46936a4e935bc4996e409d38a027ecbf21c445c44abeb7`):

| Input Artifact          | SHA-256                                                            | Role in B07                                                                                                                               |
| :---------------------- | :----------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| `REPORT.md`             | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` | Frozen baseline narrative (`2026-10-12`)                                                                                                  |
| `STATE.json`            | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` | Prior state (`6,030` rows in `consumer-matrix.csv`)                                                                                       |
| `FINAL-BLUE-GATE.json`  | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` | Prior release verdict (`NO-GO`)                                                                                                           |
| `REAL-RUN-RECEIPT.json` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | Prior live-probe receipt (`198` tables, `25` non-system schemas)                                                                          |
| `research-lines.csv`    | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` | Scopes `D02`, `D11`, `D13` (`PARTIAL`, `confidence_pct=55`)                                                                               |
| `consumer-matrix.csv`   | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | `6,030` consumer rows across sources, SQL migrations, workflows, and entrypoints                                                          |
| `ASTRA-ADVICE.md`       | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` | Mandates `B07` for migration runners, dual ledgers (`_schema_versions`, `schema_migrations`), Olympus (`D02`), and scheduled jobs (`D11`) |

---

## 1. Facts (Pinned to `file:line` and Frozen Input Hashes)

### 1.1 Migration Runners & Dual-Ledger Lineage (`D13`)

1. **Four Distinct Migration Surfaces Exist in the Monorepo**:
   - **Surface A — Numbered SQL Runner (`migrations_v2/*.sql`)**:
     - `MigrationManager` (`apps/backend-rag/backend/db/migration_manager.py:113-691`) discovers `*.sql` files in `apps/backend-rag/backend/db/migrations_v2/` matching `^(\d+)_(.+)\.sql$` (`migration_manager.py:438-476`).
     - In `consumer-matrix.csv:345-543`, `migrations_v2/` contains numbered SQL files spanning `092_attendance_late_incidents.sql` (`src_c3690f7139c4b00b`) through `323_visa_oracle_team_testing.sql` (`src_0b56630879dc5899`).
     - Each file is wrapped in `BaseMigration` (`apps/backend-rag/backend/db/migration_base.py:732-1165`) and invoked via CLI `apps/backend-rag/backend/db/migrate.py:118-181`.
   - **Surface B — Standalone Python Migration Scripts (`backend/migrations/apply_migration_*.py` + `migration_*.py`)**:
     - `consumer-matrix.csv:569-650` indexes 20 `apply_migration_*.py` scripts (`apply_migration_007.py` through `apply_migration_122.py`) and 62 `migration_*.py` modules (`migration_010_legal_ingestion.py` through `migration_126_Populate_kb_leaf_nodes.py`).
     - Representative standalone scripts `apps/backend-rag/backend/migrations/apply_migration_119.py:38-67` and `apps/backend-rag/backend/migrations/apply_migration_122.py:34-55` read `os.environ.get("DATABASE_URL")` directly, open a raw `asyncpg.connect(database_url)`, and invoke `await upgrade(conn)` (`apps/backend-rag/backend/migrations/migration_119_partners.py:47-205`) or `await apply(conn)` inside `run_with_lock_timeout(conn, upgrade)` (`apps/backend-rag/backend/migrations/_lock_guard.py:17-40`).
   - **Surface C — Legacy Service Runner (`backend/services/misc/migration_runner.py`)**:
     - `MigrationRunner` (`apps/backend-rag/backend/services/misc/migration_runner.py:30-250`, `src_f21ec0e344792217` in `consumer-matrix.csv:1503`) scans `apps/backend-rag/backend/migrations/migration_*.py` for subclasses of `BaseMigration` (`migration_runner.py:76-135`), reads applied numbers via `MigrationManager.get_applied_migrations()` (`migration_runner.py:148`), and calls `await instance.apply()` (`migration_runner.py:165`).
     - Procedural Python migrations (`migration_100c_olympus_tables.py:21`, `migration_104_olympus_v3_columns.py:18`, `migration_119_partners.py:47`) define `async def up(pool)` or `async def upgrade(conn)` rather than subclassing `BaseMigration`, so `MigrationRunner.discover_migrations()` skips them (`migration_runner.py:106-114`).
   - **Surface D — Scraper Alembic & Raw SQL (`apps/bali-intel-scraper/`)**:
     - `apps/bali-intel-scraper/backend/db/migrations/env.py:1-57` (`src_73e6a1d000604ec3` in `consumer-matrix.csv:2248`) configures Alembic with `config.set_main_option("sqlalchemy.url", settings.database.url)` and `target_metadata = None`.
     - Two raw SQL migration scripts exist outside Alembic versions: `apps/bali-intel-scraper/backend/db/migrations/add_indexes.sql` (`src_defcf0739a50a4a2`, `consumer-matrix.csv:2247`) and `apps/bali-intel-scraper/migrations/001_add_performance_indexes.sql` (`src_88815835c248a721`, `consumer-matrix.csv:2295`).

2. **Execution Identity & Role Assumption (`migration_base.py:22-221`)**:
   - `resolve_migration_dsn()` (`apps/backend-rag/backend/db/migration_base.py:62-72`) returns `(settings.migration_database_url.strip(), True)` when `MIGRATION_DATABASE_URL` is set, else `(settings.database_url, False)`.
   - Constants in `migration_base.py:22-26`: `RUNTIME_ROLE = "backend_rag_v2"`, `LEDGER_ROLE = "visa_ledger_owner"`, `MIGRATION_DSN_ENV = "MIGRATION_DATABASE_URL"`.
   - When `dedicated=True`, `assume_runtime_role(conn)` (`migration_base.py:99-221`) queries `session_user`, `current_user`, `rolsuper`, and `pg_has_role(session_user, $1, 'MEMBER')` (`migration_base.py:114-121`). It raises `MigrationError` if `session_user == "backend_rag_v2"` (`130-137`), if `is_superuser` is true without `ALLOW_SUPERUSER_MIGRATIONS=true` (`139-151`), or if `session_user` lacks `MEMBER` on `backend_rag_v2` or `visa_ledger_owner` (`159-189`). It then executes `SET ROLE "backend_rag_v2"` (`191`) and verifies `current_user == "backend_rag_v2"` (`193-204`).
   - When `dedicated=False` (`MIGRATION_DATABASE_URL` unset), `assume_runtime_role` is skipped (`migration_manager.py:173-174`, `migration_base.py:1073-1074`).

3. **Dual-Ledger Schema & Read/Write Asymmetry (`_schema_versions` vs `schema_migrations`)**:
   - **`_schema_versions` DDL** (`migration_manager.py:202-238`, extended by `apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:62-88`):
     - Columns: `id SERIAL PRIMARY KEY`, `version_name VARCHAR(255) NOT NULL UNIQUE`, `migration_number INTEGER NOT NULL UNIQUE`, `applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()`, `description TEXT`, `checksum VARCHAR(64)`, `execution_time_ms INTEGER`, `applied_by VARCHAR(100) DEFAULT CURRENT_USER`, `status VARCHAR(20) DEFAULT 'applied'`, plus provenance columns added in migration `299`: `applied_as TEXT`, `applied_via TEXT CHECK (applied_via IS NULL OR applied_via IN ('release_command', 'manual', 'ci'))`, `runner_version TEXT`.
   - **`schema_migrations` DDL** (`migration_base.py:846-885`):
     - Columns: `id SERIAL PRIMARY KEY`, `migration_name VARCHAR(255) NOT NULL UNIQUE`, `migration_number INTEGER`, `applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()`, `description TEXT`, `checksum VARCHAR(64)`, `execution_time_ms INTEGER`, `status VARCHAR(50) DEFAULT 'applied'`. It does **not** have a `UNIQUE` constraint on `migration_number` in `CREATE TABLE IF NOT EXISTS` (`850-859`), and does **not** have `applied_by`, `applied_as`, `applied_via`, or `runner_version`.
   - **Read Path Split**:
     - `MigrationManager.get_applied_migrations()` (`migration_manager.py:283-321`) and `MigrationManager.is_applied()` (`migration_manager.py:323-338`) read **exclusively** from `_schema_versions` where `status = 'applied'`.
     - `MigrationManager._apply_all_pending_locked()` (`migration_manager.py:565-577`) determines `pending` solely by checking `migration_number not in applied_numbers` (from `_schema_versions`).
     - Inside `BaseMigration.apply()` (`migration_base.py:1093`), `self._is_applied(conn)` (`migration_base.py:888-895`) reads **exclusively** from `schema_migrations` by `WHERE migration_name = $1 AND status = 'applied'`.
     - `BaseMigration._check_dependencies(conn)` (`migration_base.py:897-920`) reads **exclusively** from `schema_migrations` by `WHERE migration_number = $1 AND status = 'applied'`.
   - **Write Path (`BaseMigration._log_migration`, `migration_base.py:922-1047`)**:
     - Upserts into `schema_migrations` on `CONFLICT (migration_name)` (`995-1009`).
     - Checks if `_schema_versions` exists (`1012-1019`) and whether provenance columns exist (`956-985`); if so, upserts into `_schema_versions` on `CONFLICT (migration_number)` (`1021-1047`).
     - Resolves provenance via `_resolve_provenance(conn)` (`migration_base.py:930-953`): `applied_as = current_user`, `applied_via = os.environ.get("MIGRATION_APPLIED_VIA") or ("release_command" if os.environ.get("FLY_APP_NAME") else "ci" if os.environ.get("CI") else "manual")`, and `runner_version = os.environ.get("MIGRATION_RUNNER_VERSION") or os.environ.get("FLY_IMAGE_REF") or git rev-parse HEAD or "unknown"`.

4. **Transaction, Concurrency, and Rollback Mechanics (`D13`)**:
   - **Advisory Lock**: `MigrationManager.ADVISORY_LOCK_ID = 73491` (`migration_manager.py:120`). `apply_all_pending()` acquires a connection from `self.pool` and executes `SELECT pg_try_advisory_lock($1)` (`migration_manager.py:529-536`).
   - **Per-Migration Connection & Transaction**: `BaseMigration.apply()` (`migration_base.py:1071-1135`) opens a separate `conn = await asyncpg.connect(dsn)`, calls `await assume_runtime_role(conn)` if `dedicated`, and wraps `await conn.execute(sql_forward)` + `await self._log_migration(...)` inside `async with conn.transaction():` (`migration_base.py:1109-1130`), EXCEPT when `self._contains_concurrent_index(sql_forward)` is true (`CREATE INDEX CONCURRENTLY` or `DROP INDEX CONCURRENTLY`, `migration_base.py:725-729`), which runs outside a transaction (`1131-1135`).
   - **Rollback**: `split_migration_sql(sql)` (`migration_base.py:710-722`) splits on `^--\s*===\s*ROLLBACK\s*===\s*$`. `BaseMigration.rollback()` (`migration_base.py:1137-1164`) extracts the rollback section, executes it in `async with conn.transaction():`, and deletes tracking rows from `schema_migrations` (by `migration_name`) and `_schema_versions` (by `migration_number`).

5. **CI/CD vs External Mirror Migration Execution (`D13`)**:
   - In `.github/workflows/fly-deploy.yml:349-400`, the `post-deploy-migrations` step connects via WireGuard to `nuzantara-postgres.internal:5432` and runs `python -m backend.db.migrate apply` (lines 360–365).
   - In `.github/workflows/fly-deploy.yml:489-522`, a separate step runs `python -m backend.migrations.apply_migration_119`, `apply_migration_120`, and `apply_migration_121`.
   - In `consumer-matrix.csv:11` (`src_be1576c6db3d7bc5`), `.github/workflows/fly-deploy.yml` in `BaliZero0/Nuzantara` is recorded with state `disabled_manually`. Per `apps/backend-rag/CLAUDE.md:457-464` and `consumer-matrix.csv:5948` (`entry_d59b842b6a149dd9`, `mini.zero_sync`, `~/scripts/zero-sync.sh`), production deploys mirror `main` to `FastLabsNet/zero` on self-hosted runner `mini-zero-1`.

---

### 1.2 Olympus DB Guardian, Pulse Maintenance & DB-Internal Triggers/Functions (`D02`)

1. **Olympus Schema & Tables (`migration_100c_olympus_tables.py`, `migration_104_olympus_v3_columns.py`, `211_olympus_residual_runtime_grants.sql`, `233_olympus_safety_envelope_rules.sql`)**:
   - `apps/backend-rag/backend/migrations/migration_100c_olympus_tables.py:21-184` creates:
     - `olympus_heartbeats` (`PARTITION BY RANGE (recorded_at)` with monthly partitions `olympus_heartbeats_2026_03`..`2026_06` and `olympus_heartbeats_default`).
     - `olympus_actions` (`rhythm VARCHAR(20) NOT NULL CHECK (rhythm IN ('heartbeat', 'pulse', 'metacognition', 'council'))`, `outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('success', 'failure', 'skipped', 'proposed'))`).
     - `olympus_rules` (`category VARCHAR(30) NOT NULL CHECK (category IN ('threshold', 'schedule', 'policy', 'skill'))`, `source VARCHAR(20) NOT NULL DEFAULT 'static' CHECK (source IN ('static', 'learned', 'adapted', 'override'))`).
     - `olympus_insights` and `olympus_skills`.
   - `apps/backend-rag/backend/migrations/migration_104_olympus_v3_columns.py:18-55` adds `bloat_top3 JSONB`, `locks_waiting INT`, `long_queries INT`, `wal_size_mb FLOAT` to `olympus_heartbeats` and `verify_query TEXT`, `verified BOOLEAN` to `olympus_actions`.
   - `apps/backend-rag/backend/db/migrations_v2/211_olympus_residual_runtime_grants.sql:35-199` grants `SELECT` on `public.query_clusters` and `public.x_monitored_tweets` and `USAGE, SELECT, UPDATE` on `query_clusters_id_seq` and `x_monitored_tweets_id_seq` to `backend_rag_v2` so `OlympusPulse.repair_sequences()` does not fail with `InsufficientPrivilegeError`.
   - `apps/backend-rag/backend/db/migrations_v2/233_olympus_safety_envelope_rules.sql:25-56` seeds 4 static rules in `olympus_rules`: `max_actions_per_pulse` (`50`), `max_pulse_duration_seconds` (`600`), `action_statement_timeout_s` (`300`), `action_lock_timeout_s` (`5`).

2. **Olympus Runtime Initialization & Loops (`service_initializer.py`, `guardian.py`)**:
   - `OlympusGuardian` (`apps/backend-rag/backend/services/olympus/guardian.py:24-324`) is instantiated in **two** startup paths:
     1. Full init (`rag` process group): `apps/backend-rag/backend/app/setup/service_initializer.py:1937-1963` creates `OlympusGuardian(db_pool=db_pool, alert_service=alert_service)`, calls `await olympus.initialize()` and `await olympus.start()`, unless `DISABLE_BACKGROUND_WORKERS == "1"`.
     2. Light init (`api` process group): `apps/backend-rag/backend/app/setup/service_initializer.py:2184-2196` creates `OlympusGuardian(db_pool=db_pool, alert_service=None)`, calls `await olympus.initialize()` and `await olympus.start()`, unless `DISABLE_BACKGROUND_WORKERS == "1"`.
   - `guardian.start()` (`guardian.py:238-257`) spawns two `asyncio.Task`s: `olympus_heartbeat` (`_heartbeat_loop`, interval `heartbeat_interval_seconds`, default `300s`) and `olympus_pulse` (`_pulse_loop`, initial `await asyncio.sleep(60)`, then interval `pulse_interval_hours * 3600`, default `6h`).
   - `_heartbeat_loop()` (`guardian.py:207-218`) wraps `await self.run_heartbeat()` in `async with get_bg_pool_semaphore():` and guards pool health via `CircuitBreaker(failure_threshold=3, timeout=900.0, name="olympus-pool")` (`guardian.py:42-46`).
   - `HeartbeatCollector.collect_and_Assess()` (`apps/backend-rag/backend/services/olympus/heartbeat.py:38-155`) queries `pg_stat_activity`, `pg_settings`, `pg_database_size(current_database())`, `pg_stat_database`, `pg_stat_user_tables`, and `pg_locks` in one connection, then acquires a second connection (`heartbeat.py:124`) to `INSERT INTO olympus_heartbeats`. If `pool_utilization >= 0.95` and `idle_in_tx > 0`, `emergency_kill_idle_tx()` (`heartbeat.py:157-199`) executes `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction'` and logs to `olympus_actions`.
   - `OlympusPulse.run_full_pulse()` (`apps/backend-rag/backend/services/olympus/pulse.py:618-667`) executes 9 maintenance operations in order under `PulseBudget(max_actions=50, max_runtime_s=600)` (`apps/backend-rag/backend/services/olympus/safety.py:54-83`):
     1. `vacuum_bloated_tables` (`pulse.py:72-128`): `VACUUM ANALYZE <table>` on tables in `_SAFE_VACUUM_TABLES` (`pulse.py:26-51`) under `action_timeouts(self.pool, st, lk)`.
     2. `cleanup_audit_trail` (`pulse.py:130-199`): `DROP TABLE IF EXISTS <partition>` if `api_audit_trail` is partitioned (`relkind = 'p'`), else `DELETE FROM api_audit_trail WHERE created_at < NOW() - INTERVAL '<days> days'`.
     3. `repair_sequences` (`pulse.py:251-332`): scans `pg_class`/`pg_depend` for `public` sequences, queries `SELECT COALESCE(MAX(col), 0) FROM public.<table>`, and calls `SELECT setval($1, $2)` when `max_val > seq_val`.
     4. `rebuild_invalid_indexes` (`pulse.py:334-380`): runs `REINDEX INDEX CONCURRENTLY <idx>` on `pg_index.indisvalid = false` in `public` under `action_timeouts`.
     5. `refresh_materialized_views` (`pulse.py:382-433`): queries `SELECT matviewname FROM pg_matviews` and runs `REFRESH MATERIALIZED VIEW CONCURRENTLY <view>` (falling back to non-concurrent `REFRESH MATERIALIZED VIEW <view>`).
     6. `cleanup_expired_sessions` (`pulse.py:435-459`): `DELETE FROM persistent_sessions WHERE updated_at < NOW() - INTERVAL '30 days'`.
     7. `ensure_next_partition` (`pulse.py:461-510`): executes `CREATE TABLE IF NOT EXISTS olympus_heartbeats_YYYY_MM PARTITION OF olympus_heartbeats FOR VALUES FROM (...) TO (...)` for `NOW() + INTERVAL '1 month'`.
     8. `cleanup_olympus_self` (`pulse.py:512-616`): detaches (`ALTER TABLE olympus_heartbeats DETACH PARTITION`) and drops (`DROP TABLE IF EXISTS`) monthly partitions older than `olympus_hb_retention_months` (`6`), deletes `olympus_actions` older than `90 days`, and deletes `olympus_insights` (`superseded_by IS NOT NULL` or `status = 'acknowledged'` older than `90 days`).
     9. `autovacuum_advisor` (`pulse.py:201-249`): emits `outcome="proposed"` actions for tables with `n_dead_tup > 10000`.
   - After `pulse.run_full_pulse()`, `guardian.run_pulse()` (`guardian.py:76-112`) calls `InsightsCollector.collect_query_insights()` and `collect_bloat_insights()` (`apps/backend-rag/backend/services/olympus/insights.py:42-218`), persists all `PulseAction` rows to `olympus_actions`, updates `olympus_rules` (`record_applied` / `lower_confidence` in `apps/backend-rag/backend/services/olympus/rules_engine.py:67-95`), and calls `_maybe_send_weekly_digest()` (`guardian.py:114-156`, which upserts `rule_name = 'insight_digest_last_iso_week'` into `olympus_rules`).

3. **DB-Internal Triggers & SECURITY DEFINER Maintenance Functions (`D02`)**:
   - **Provenance Immutability Trigger** (`apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql:29-56`): `public._schema_versions_299_guard_fn()` (`LANGUAGE plpgsql`, trigger `trg_schema_versions_299_guard` `BEFORE UPDATE ON public._schema_versions FOR EACH ROW`) blocks modifying `applied_as`, `applied_via`, or `runner_version` once non-NULL, while allowing `NULL -> value` backfill.
   - **Visa & Garuda Retention `SECURITY DEFINER` Purge Functions** (`apps/backend-rag/backend/scripts/visa_engine/retention_worker.py:56-69, 266-288`):
     - `public.visa_decision_retention_evidence()`
     - `public.visa_idempotency_retention_evidence()`
     - `public.purge_visa_decisions(integer,text)`
     - `public.purge_visa_evaluate_idempotency(integer,text)`
     - `public.purge_garuda_voa_checks(integer,text)`
     - `public.purge_garuda_voa_check_results(integer,text)`
     - Invoked by `retention_worker.py` under a dedicated non-superuser, non-`backend_rag_v2` executor role via `VISA_ENGINE_RETENTION_DATABASE_URL` (`retention_worker.py:45-47, 242-288`).
   - **Append-Only Ledger / Audit Guard Triggers (`migrations_v2/`)**:
     - `146_audit_protection_triggers.sql` (`src_c40147f6e9081fd9`), `187_visa_oracle_audit_spine.sql` (`src_e11cfda87216b8bb`), `190_visa_audit_remediation.sql` (`src_fd55b2651f33a8a5`), `193_visa_audit_definer_hardening.sql` (`src_3f079176158f36a7`), `287_garuda_orders_foundation.sql` (`src_028c16b2fd60b96e`), and `308_visa_Check_store.sql` (`src_89f5c0d52b633c68`) define DB-level append-only/retention triggers and `SECURITY DEFINER` routines.

---

### 1.3 Scheduled Jobs, LaunchAgents, Cron, Event Loops & Manual Maintenance Writers (`D11`)

1. **Registered Host Schedulers (`consumer-matrix.csv:5944-6031` / `organism_entrypoints.json`)**:
   - `consumer-matrix.csv` rows `5944–6031` enumerate 88 registered host entrypoints (`entry_*`) across `mini.*`, `pro.*`, `air.*`, and `fly.*`.
   - Direct DB maintenance & sync entrypoints include:
     - `pro.outbox_prune_daily` (`entry_a14536f32ddbc648`, `consumer-matrix.csv:6012`): runs `~/nuzantara/scripts/outbox-prune.sh` daily at `03:15` via `~/Library/LaunchAgents/com.nuzantara.outbox-prune.daily.plist` (`scripts/outbox-prune.sh:8-9`). Connects via `DATABASE_URL` (rewriting `.flycast`/`.internal` hostnames to `127.0.0.1:15432` when local `pg-proxy` is reachable, `scripts/outbox-prune.sh:46-55`) and invokes `backend.services.events.outbox.prune_consumed(conn, older_than_days=30)` (`scripts/outbox-prune.sh:77-83`).
     - `pro.backup_pg_fly` (`entry_308dc4f0cf99c62f`, `consumer-matrix.csv:5973`): runs `~/scripts/fly-pg-backup.sh` (`launchd`).
     - `pro.postgres_Tunnel` (`entry_be0c0ce5e1e4dbdb`, `consumer-matrix.csv:6019`): runs `/opt/homebrew/bin/flyctl proxy 15432:5432 -a nuzantara-postgres`.
     - `mini.zero_sync` (`entry_d59b842b6a149dd9`, `consumer-matrix.csv:5948`): runs `~/scripts/zero-sync.sh` (`cron`), syncing `main` to `FastLabsNet/zero` to trigger self-hosted deploy/migration execution.
     - `fly.rag_backend` (`entry_1a3f28e732a1fb77`, `consumer-matrix.csv:5944`): Fly app `nuzantara-rag` hosting the in-process loops below.

2. **In-Process Background Loops in `nuzantara-rag` (`service_initializer.py:1800-2261`)**:
   - Full init (`rag` process group, `service_initializer.py:1800-1964`):
     - `HealthMonitor` (`check_interval=60s`, lines `1810-1820`).
     - `wa_subscription_guardian` (`start_whatsapp_subscription_guardian_task`, Redis leader lock, 6h re-arm + silence receptor, lines `1834-1848`).
     - `BackendSelfHealingAgent` (`GCAction` only, `check_interval=300s`, lines `1873-1885`).
     - `kg_incremental_builder` (`start_kg_incremental_task(db_pool)`, daily, writes verdict to `system_settings.kg_incremental_last`, lines `1898-1908`).
     - `newsletter_daily_task` (`start_newsletter_daily_task(db_pool)`, replaces dead `com.balizero.wr2.newsletter` LaunchAgent, lines `1922-1930`).
     - `OlympusGuardian` (`heartbeat` every 300s + `pulse` every 6h, lines `1948-1953`).
   - Light init (`api` process group, `service_initializer.py:2167-2261`):
     - `AttendanceMonitor` (`start_schedulers()`, lines `2172-2174`) + `TeamTimesheetService` (`start_auto_logout_monitor()`, lines `2175-2177`).
     - `OlympusGuardian` (`heartbeat` every 300s + `pulse` every 6h, with `alert_service=None`, lines `2188-2192`).
     - `delivery_manager.start_retry_loop(send_adapters)` (Channel DLQ retry loop on `failed_messages`, lines `2241-2250`).

3. **Unscheduled / Manual Maintenance & Audit Scripts (`D11`)**:
   - `apps/backend-rag/backend/scripts/visa_engine/retention_worker.py` (`src_596b45ec9f303d3c`, `consumer-matrix.csv:1109`): `BLOCKED_DISCOVERY` (`runtime_candidate_unverified`). Requires an external scheduler (`retention_worker.py:5-6`), but has no entry in `organism_entrypoints.json` (`consumer-matrix.csv:5944-6031`).
   - `apps/backend-rag/backend/db/schema_audit.py` (`src_a3c3563c2026a9bf`, `consumer-matrix.csv:342`): invoked during CI/deploy pre-flight and post-deploy checks (`.github/workflows/fly-deploy.yml:403-411`) or manually via CLI (`python -m backend.db.schema_audit`).

---

## 2. Counterexamples & Structural Defects (Proven from Source)

Each counterexample below disproves an explicit or implicit invariant in the codebase or census notes, pinned to exact `file:line`:

### Counterexample CE-01 — Dual-Ledger Split-Brain Between `_schema_versions` and `schema_migrations` (`D13`)

- **Claimed Invariant**: `_schema_versions` and `schema_migrations` track applied migrations in lockstep (`migration_base.py:986-1047`).
- **Disproof (`file:line`)**:
  1. `MigrationManager.get_applied_migrations()` (`apps/backend-rag/backend/db/migration_manager.py:298-304`) and `_apply_all_pending_locked()` (`migration_manager.py:565-577`) read **only** `_schema_versions`.
  2. `BaseMigration._is_applied()` (`apps/backend-rag/backend/db/migration_base.py:888-895`) reads **only** `schema_migrations` (matching `migration_name`), and `BaseMigration._check_dependencies()` (`migration_base.py:897-920`) reads **only** `schema_migrations` (matching `migration_number`).
  3. **Direction 1 (`_schema_versions` only -> permanent skip in `schema_migrations`)**: When a migration row exists in `_schema_versions` but not in `schema_migrations` (e.g., baseline `001` fake-applied at `migration_manager.py:617-627`, which inserts ONLY into `_schema_versions` with `version_name = '001_baseline_v2.sql'`, or a manual insert into `_schema_versions`), `apply_all_pending()` sees `migration_number in applied_numbers` (`migration_manager.py:570`) and **never invokes `BaseMigration.apply()`**, leaving `schema_migrations` permanently missing that row and breaking `BaseMigration._check_dependencies()` (`migration_base.py:905-919`) and `schema_audit.py`'s `tracking_divergence_legacy_only` check (`apps/backend-rag/backend/db/schema_audit.py:636-647`).
  4. **Direction 2 (`schema_migrations` only -> silent no-op backfill)**: When a row exists in `schema_migrations` (with matching `migration_name`) but not in `_schema_versions`, `apply_all_pending()` queues it, and `BaseMigration.apply()` (`migration_base.py:1093-1106`) sees `await self._is_applied(conn) == True`, **skips executing `sql_forward`**, and calls `await self._log_migration(conn, sql, 0)` inside an autocommit connection (outside `conn.transaction()`) to backfill `_schema_versions`.
  5. **Historical Proof in Repo**: Migrations `165_reconcile_schema_migrations_duplicates.sql:1-191`, `184_reconcile_182_tracking_divergence.sql:1-49`, and `194_reconcile_107_bridge_outbox_tracking.sql:1-49` had to be authored specifically to repair production divergence caused by this split-brain architecture.

### Counterexample CE-02 — Lock-Contention on Advisory Lock `73491` Exits `0` (`D13`)

- **Claimed Invariant**: `consumer-matrix.csv:343` (`apps/backend-rag/backend/db/migration_manager.py`) states `"Lock-busy refusal is nonzero"`.
- **Disproof (`file:line`)**:
  - In `apps/backend-rag/backend/db/migration_manager.py:534-541`, when `await lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", self.ADVISORY_LOCK_ID)` returns `False`, `apply_all_pending()` logs `"Another migration process is running, skipping"` and returns `{"applied": [], "skipped": [], "failed": []}`.
  - In `apps/backend-rag/backend/db/migrate.py:77`, `cmd_apply()` evaluates `return len(result["failed"]) == 0`, which is `True` (`0 == 0`).
  - In `apps/backend-rag/backend/db/migrate.py:169-170`, `main()` executes `sys.exit(0 if success else 1)`. Therefore, advisory lock contention exits with code **`0`**, silently reporting success to CI/callers when zero migrations were checked or applied.

### Counterexample CE-03 — Standalone Python Migrations (`apply_migration_*.py`) Bypass Role Guard, Advisory Lock, Atomic Transactions, and Both Ledgers (`D13`)

- **Claimed Invariant**: All schema migrations record provenance in `_schema_versions` / `schema_migrations` and execute as `backend_rag_v2` via `resolve_migration_dsn()` (`migration_base.py:62-221`).
- **Disproof (`file:line`)**:
  - `apps/backend-rag/backend/migrations/apply_migration_119.py:38-44` and `apps/backend-rag/backend/migrations/apply_migration_122.py:34-40` read `os.environ.get("DATABASE_URL")` directly (ignoring `MIGRATION_DATABASE_URL` and `assume_runtime_role()`), do not acquire `pg_try_advisory_lock(73491)`, and invoke `migration_119_partners.py:47-205` / `migration_122_practice_types_visa_d1_5yr.py`, which execute DDL/DML and **never insert into `_schema_versions` or `schema_migrations`**.
  - Furthermore, `apps/backend-rag/backend/migrations/_lock_guard.py:17-40` runs `await conn.execute(f"SET lock_timeout = '{timeout}'")` at session scope (not `SET LOCAL`) **without opening `async with conn.transaction():`**. In `migration_119_partners.py:51-198`, 10+ separate `await conn.execute(...)` calls run in autocommit mode; if statement #8 fails, statements #1–#7 remain permanently committed with zero ledger record.
  - Additionally, `.github/workflows/fly-deploy.yml:489-522` hardcodes `apply_migration_119`, `apply_migration_120`, and `apply_migration_121`, omitting `apply_migration_122.py` (`consumer-matrix.csv:588`) and `migration_125`/`migration_126` (`consumer-matrix.csv:646-647`).

### Counterexample CE-04 — `migrate.py` Empty `pass` Loops Break Post-Deploy Migration Counting (`D13`)

- **Claimed Invariant**: `.github/workflows/fly-deploy.yml:373` parses `APPLIED=$(grep -cF "   - Migration " migration_output.txt || true)` from `python -m backend.db.migrate apply` stdout to detect applied migrations and send Telegram notifications (`fly-deploy.yml:377-394`).
- **Disproof (`file:line`)**:
  - In `apps/backend-rag/backend/db/migrate.py:67-75`, the output loops in `cmd_apply()` are literal no-ops:
    ```python
    if result["applied"]:
        for _num in result["applied"]:
            pass
    ```
  - Likewise, `cmd_status()` (`migrate.py:31-35`), `cmd_list()` (`migrate.py:44-47`), and `cmd_info()` (`migrate.py:85-88`) have had all `print()` statements replaced with `pass`. Consequently, `"   - Migration "` is **never** emitted to stdout, `APPLIED` in `fly-deploy.yml:373` is always `0`, and `migrate.py status` / `migrate.py list` produce zero output.

### Counterexample CE-05 — `schema_audit.py` Violates the `MIGRATION_DATABASE_URL` Isolation Invariant (`D13`)

- **Claimed Invariant**: `apps/backend-rag/backend/db/migration_base.py:68-69` states: _"`schema_audit` and the runtime keep reading `settings.database_url` directly and never see the migrator DSN."_
- **Disproof (`file:line`)**:
  - `apps/backend-rag/backend/db/schema_audit.py:761` instantiates `manager = MigrationManager(database_url=database_url)` where `database_url` defaults to `None` (`schema_audit.py:739, 795`).
  - `MigrationManager.__init__` (`apps/backend-rag/backend/db/migration_manager.py:126-129`) sets `resolved_dsn, dedicated = (database_url, False) if database_url else resolve_migration_dsn()`.
  - Therefore, whenever `MIGRATION_DATABASE_URL` is set in the environment, `schema_audit.py` connects using `MIGRATION_DATABASE_URL` (`dedicated=True`) and calls `assume_runtime_role()` (`migration_manager.py:173-174`), directly contradicting `migration_base.py:68-69`.

### Counterexample CE-06 — Checksum Audit Skips File Hashing on 17 Sentinel Rows and Hashes Rollback Comments (`D13`)

- **Claimed Invariant**: `schema_audit.py` detects any post-apply tampering of applied SQL files in `migrations_v2/`.
- **Disproof (`file:line`)**:
  1. In `apps/backend-rag/backend/db/schema_audit.py:475-496`, when `recorded_checksum` in `_schema_versions` is not a 64-hex-char SHA-256 (which is true for 17 production migrations documented at `schema_audit.py:254-263`: `'manual_apply'`, `'manual-fix'`, `'manual'`, `''`, and MD5 `'031c4d196dcc3860b6ee0598d0db7853'` on `182`), `_check_migration_checksums()` executes `continue` **before** reading or hashing `sql_files[mig_num]`. Any modification to those 17 `.sql` files on disk is invisible to `schema_audit.py`.
  2. For 8 additional migrations (`127`, `157`, `158`, `186`, `192`, `200`, `207`, `217`), `LEGACY_CHECKSUM_BASELINE` (`schema_audit.py:315-347, 504-514`) downgrades SHA-256 mismatches to `warning` unless `SCHEMA_AUDIT_CHECKSUM_ENFORCE=true`, and compares only against `recorded_checksum` in the DB rather than pinning the expected on-disk SHA-256 in code — meaning further edits to those 8 files still only produce the same baseline warning.
  3. In `apps/backend-rag/backend/db/migration_base.py:1056, 1112, 1129`, `BaseMigration.apply()` executes `sql_forward` (stripped of `-- === ROLLBACK ===`), but passes the full `sql` string to `_log_migration(conn, sql, ...)` (`929`), so editing or adding a `-- === ROLLBACK ===` section retroactively invalidates the recorded forward migration checksum.
  4. `_check_migration_checksums()` (`schema_audit.py:428-526`) checks only `_schema_versions` and never verifies `schema_migrations.checksum`.

### Counterexample CE-07 — Dual-Process Uncoordinated `OlympusGuardian` Execution & Silent Alert Drop on `api` (`D02`)

- **Claimed Invariant**: `OlympusGuardian` runs as a single coordinated DB maintenance guardian with alerting and weekly digests enabled (`guardian.py:16-22`).
- **Disproof (`file:line`)**:
  1. `OlympusGuardian` is started in **both** `initialize_services` (`rag` process group, `apps/backend-rag/backend/app/setup/service_initializer.py:1948-1951`) and `initialize_services_light` (`api` process group, `service_initializer.py:2188-2191`).
  2. Unlike `wa_subscription_guardian` (`service_initializer.py:1831-1832`) and `kg_incremental_builder` (`1895`), `OlympusGuardian` (`apps/backend-rag/backend/services/olympus/guardian.py:55-257`) acquires **no Redis lock and no PostgreSQL advisory lock** before running `run_heartbeat()` or `run_pulse()`. Whenever `api` and `rag` are both running, both processes execute heartbeats (every 5m) and pulses (every 6h) concurrently against the same PostgreSQL instance, racing on `VACUUM ANALYZE`, `REINDEX INDEX CONCURRENTLY`, `REFRESH MATERIALIZED VIEW`, partition DDL, and `olympus_rules` confidence updates.
  3. On the always-on `api` process (`service_initializer.py:2188`), `OlympusGuardian(db_pool=db_pool, alert_service=None)` is initialized with `alert_service=None`. In `guardian.py:114-115` (`_maybe_send_weekly_digest`) and `guardian.py:163-164` (`_fire_alerts`), `if not self.alert_service: return` immediately exits. Thus, the always-on `api` guardian **never** sends critical DB alerts or weekly digests!

### Counterexample CE-08 — Olympus `_pulse_loop` Bypasses `get_bg_pool_semaphore()` & `action_timeouts` Leaks Session GUCs (`D02`)

- **Claimed Invariant**: Background DB loops bound pool concurrency via `get_bg_pool_semaphore()` and scope statement/lock timeouts safely to single maintenance actions (`guardian.py:213`, `safety.py:28-51`).
- **Disproof (`file:line`)**:
  1. While `_heartbeat_loop()` acquires `async with get_bg_pool_semaphore():` (`guardian.py:213`), `_pulse_loop()` (`guardian.py:219-227`) calls `await self.run_pulse()` **without** acquiring `get_bg_pool_semaphore()`.
  2. `action_timeouts(pool, statement_timeout_s, lock_timeout_s)` (`apps/backend-rag/backend/services/olympus/safety.py:28-51`) executes session-level `SET statement_timeout = '{st}s'` and `SET lock_timeout = '{lk}s'` without a `try/finally` reset (`SET statement_timeout = '30s'; SET lock_timeout = DEFAULT`), and `cleanup_audit_trail` (`pulse.py:155-184`) and `refresh_materialized_views` (`pulse.py:394-415`) do not use `action_timeouts` at all.
  3. In `pulse.py:461-510`, `ensure_next_partition()` only creates the partition for `NOW() + INTERVAL '1 month'` (never the current month). If the current month's partition was missed, heartbeats insert into `olympus_heartbeats_default`; any subsequent attempt to attach a partition whose timestamp range overlaps rows already in `olympus_heartbeats_default` fails in PostgreSQL (`check constraint of default partition would be violated by some row`).

### Counterexample CE-09 — `scripts/outbox-prune.sh` Hardcodes Wrong Repo Path for Host `pro` (`D11`)

- **Claimed Invariant**: `pro.outbox_prune_daily` (`consumer-matrix.csv:6012`, `scripts/outbox-prune.sh`) prunes `events_outbox` daily at `03:15` on host `Pro`.
- **Disproof (`file:line`)**:
  - Per `AGENTS.md` §0, the repository path on `Pro` (`user: nuzantara`, `hostname: Nuzantara`) is `~/Desktop/nuzantara`, whereas `~/nuzantara` is the path on `Mini` and `Air-M5`.
  - `scripts/outbox-prune.sh:25, 58-64` hardcodes `REPO_ROOT="${HOME}/nuzantara"` and `VENV="${REPO_ROOT}/apps/backend-rag/.venv/bin/python"`. If `~/nuzantara` does not exist on `Pro`, `[ ! -x "$VENV" ]` at line `61` logs `ERROR: backend-rag .venv not found` and exits `2` **without calling `organism_heartbeat "pro.outbox_prune_daily" "fail"`** (unlike line `40`).

---

## 3. Inferences (Derived Directly from Facts)

1. **Inference IN-01 (Ledger Lineage Cannot Be Reconstructed from Either Table Alone)**:
   - Because `MigrationManager` reads `_schema_versions` while `BaseMigration` reads `schema_migrations`, and standalone `apply_migration_*.py` scripts write to neither, the effective migration state of `nuzantara-postgres` is a 4-way join across:
     1. `public._schema_versions` (SQL runner primary read ledger + provenance from `299`),
     2. `public.schema_migrations` (`BaseMigration` idempotency & dependency ledger),
     3. `pg_catalog` (`pg_class`, `pg_attribute`, `pg_proc`, `pg_trigger`, `pg_Constraint`, `pg_indexes`) for unrecorded Python migrations (`apply_migration_007..122`, `migration_100c`, `migration_104`, `migration_119`, `migration_122`) and scraper SQL, and
     4. `public.alembic_version` (if created by `apps/bali-intel-scraper/backend/db/migrations/env.py`).
2. **Inference IN-02 (Unmonitored Drift Window on 25 Applied SQL Migrations)**:
   - Combining the 17 non-SHA256 sentinel rows skipped before file hashing (`schema_audit.py:254-263, 475-496`) and the 8 `LEGACY_CHECKSUM_BASELINE` rows demoted to warning (`schema_audit.py:315-347`), 25 applied migrations in `migrations_v2/` lack strict on-disk SHA-256 enforcement during default `schema_audit.py` runs.
3. **Inference IN-03 (Visa/Garuda Retention Execution Gap)**:
   - Because `apps/backend-rag/backend/scripts/visa_engine/retention_worker.py` (`src_596b45ec9f303d3c`) is designed to be invoked only by an external scheduler (`retention_worker.py:5-6`) using `VISA_ENGINE_RETENTION_DATABASE_URL`, and no entrypoint in `organism_entrypoints.json` (`consumer-matrix.csv:5944-6031`) invokes `retention_worker.py`, `purge_visa_decisions`, `purge_visa_evaluate_idempotency`, `purge_garuda_voa_checks`, and `purge_garuda_voa_check_results` are either unscheduled or triggered outside the registered organism manifest.

---

## 4. Unknowns & Sibling Contract Mapping (`BATTLE.md` §3)

### 4.1 Explicit Unknowns Requiring Read-Only Live Catalog / Host Verification (`DUX-REQUESTS`)

- **`UNK-B07-01` (Live Dual-Ledger Delta)**: Exact row counts, symmetric difference (`_schema_versions FULL OUTER JOIN schema_migrations`), and `NULL` vs non-`NULL` provenance counts (`applied_as`, `applied_via`, `runner_version`) in live `nuzantara-postgres`.
- **`UNK-B07-02` (On-Disk SHA-256 vs Live Checksums for the 25 Baseline/Sentinel Migrations)**: Exact SHA-256 of all `migrations_v2/*.sql` files on disk (both full-file and forward-only SQL) compared against live `_schema_versions.checksum` and `schema_migrations.checksum`.
- **`UNK-B07-03` (Live `pg_proc` / `pg_trigger` / `pg_event_trigger` Inventory)**: Complete live catalog list of `SECURITY DEFINER` functions, user triggers (`tgname`, `tgrelid`, `tgenabled`), and event triggers in `nuzantara-postgres` to confirm whether any out-of-band triggers exist without repo DDL.
- **`UNK-B07-04` (Live Olympus Partition & Action State)**: Current child partitions of `public.olympus_heartbeats` (specifically whether `2026_07`..`2026_11` exist or if rows fell into `olympus_heartbeats_default`), plus aggregate `olympus_actions` counts by `(rhythm, action_type, outcome)`.
- **`UNK-B07-05` (Live Scheduler & Retention Worker Registration)**: Whether any crontab/LaunchAgent on `Pro`, `Mini`, or Fly runs `backend.scripts.visa_engine.retention_worker` with `VISA_ENGINE_RETENTION_DATABASE_URL`, and whether `~/nuzantara` on `Pro` is a symlink to `~/Desktop/nuzantara` for `scripts/outbox-prune.sh`.

### 4.2 Mapping to Frozen Sibling Contract (`BATTLE.md` §3)

Per `BATTLE.md` §3, B07 binds its consumers and operations to the common contract fields (`consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns`) and the B05 operation instance fields (`principal,role,tenant,authorization,transaction,effects,retries,idempotency,failure,retention,recovery`):

| Consumer ID (`consumer-matrix.csv`)                                                                                                    | Operation ID                       | Store ID                                                                                                                                                                                                             | Principal / Role (`B03`/`B05`)                                                                                                                                                 | Transaction & Locks (`B05`)                                                                                                                                                                                                        | Idempotency, Retries & Recovery (`B05`)                                                                                                                                                                                   | Status    | Unknowns                   |
| :------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------- | :------------------------- |
| `src_8a84056e9c7f8187` (`migrate.py`) + `src_1e0257e8a9c6bd69` (`migration_manager.py`) + `src_2d40b844767621b7` (`migration_base.py`) | `op_d13_sql_migration_apply`       | `postgresql:nuzantara-postgres` (`_schema_versions`, `schema_migrations`, target DDL)                                                                                                                                | `MIGRATION_DATABASE_URL` session user (`MEMBER` of `backend_rag_v2`, `visa_ledger_owner`) -> `SET ROLE "backend_rag_v2"` (or `DATABASE_URL` when unset)                        | Session `pg_try_advisory_lock(73491)` on pool conn; separate `asyncpg.connect(dsn)` per file with `conn.transaction()` (autocommit if `CONCURRENTLY`)                                                                              | Dual-ledger check (`_schema_versions` by number, `schema_migrations` by name); pool init retry `3x` (no retry on per-file `connect`); rollback via `-- === ROLLBACK ===`; **Defects**: `CE-01`, `CE-02`, `CE-04`, `CE-06` | `PARTIAL` | `UNK-B07-01`, `UNK-B07-02` |
| `src_a3c3563c2026a9bf` (`schema_audit.py`)                                                                                             | `op_d13_schema_audit`              | `postgresql:nuzantara-postgres` (`_schema_versions`, `schema_migrations`, `information_schema`, `pg_catalog`)                                                                                                        | Intended: `DATABASE_URL` runtime role; **Actual (`CE-05`)**: uses `resolve_migration_dsn()` (`MIGRATION_DATABASE_URL` -> `SET ROLE "backend_rag_v2"`) when `database_url=None` | Read-only queries across pool (`min=1, max=5`)                                                                                                                                                                                     | Stateless audit; skips hashing 17 sentinel rows (`CE-06`), demotes 8 baseline rows to warning                                                                                                                             | `PARTIAL` | `UNK-B07-01`, `UNK-B07-02` |
| `src_081e527c88a78466` (`apply_migration_119.py`) .. `src_72d067168854784d` (`apply_migration_122.py`) + `_lock_guard.py`              | `op_d13_py_standalone_migration`   | `postgresql:nuzantara-postgres` (`partners`, `practice_types`, etc.)                                                                                                                                                 | Raw `DATABASE_URL` (bypasses `MIGRATION_DATABASE_URL` and `assume_runtime_role`)                                                                                               | Session `SET lock_timeout = '5s'`; **no transaction wrapper** (`CE-03`); **no advisory lock**                                                                                                                                      | Relies on `IF NOT EXISTS` / `ON CONFLICT` in DDL/DML; writes **zero** ledger rows (`CE-03`)                                                                                                                               | `PARTIAL` | `UNK-B07-01`               |
| `src_f21ec0e344792217` (`services/misc/migration_runner.py`)                                                                           | `op_d13_legacy_service_runner`     | `postgresql:nuzantara-postgres` (`_schema_versions`, `schema_migrations`)                                                                                                                                            | Delegates to `MigrationManager` / `BaseMigration`                                                                                                                              | Delegates to `BaseMigration.apply()`                                                                                                                                                                                               | Discovers only `BaseMigration` subclasses in `backend/migrations/`; skips procedural Python migrations (`100c`, `104`, `119`, `122`)                                                                                      | `PARTIAL` | `UNK-B07-01`               |
| `src_73e6a1d000604ec3` (`apps/bali-intel-scraper/backend/db/migrations/env.py`)                                                        | `op_d13_scraper_alembic`           | `postgresql` (`settings.database.url`, `alembic_version`)                                                                                                                                                            | `settings.database.url` principal                                                                                                                                              | `context.begin_transaction()`                                                                                                                                                                                                      | Alembic revision tracking (`target_metadata = None`)                                                                                                                                                                      | `PARTIAL` | `UNK-B07-01`               |
| `src_6a79176158068491` (`olympus/guardian.py`) + `src_1d4525a19836a350` (`heartbeat.py`)                                               | `op_d02_olympus_heartbeat`         | `postgresql:nuzantara-postgres` (`olympus_heartbeats`, `olympus_actions`, `pg_stat_*`, `pg_locks`)                                                                                                                   | `DATABASE_URL` (`backend_rag_v2`) in **both** `rag` and `api` process groups (`CE-07`)                                                                                         | Autocommit reads + `INSERT INTO olympus_heartbeats` + `pg_terminate_backend` on emergency (`pool >= 95%`); guarded by `get_bg_pool_semaphore()` and `CircuitBreaker(3, 900s)`                                                      | Append-only time-series every `300s`; retained `6 months` via monthly partition drop (`cleanup_olympus_self`); `alert_service=None` on `api` (`CE-07`)                                                                    | `PARTIAL` | `UNK-B07-04`               |
| `src_6a79176158068491` (`olympus/guardian.py`) + `src_c608253411521a09` (`pulse.py`) + `src_a59907c954328889` (`insights.py`)          | `op_d02_olympus_pulse`             | `postgresql:nuzantara-postgres` (`olympus_actions`, `olympus_rules`, `olympus_insights`, `olympus_heartbeats_*`, `api_audit_trail`, `persistent_sessions`, `_SAFE_VACUUM_TABLES`, `pg_matviews`, sequences, indexes) | `DATABASE_URL` (`backend_rag_v2`) in **both** `rag` and `api` process groups (`CE-07`)                                                                                         | Autocommit DDL/maintenance (`VACUUM ANALYZE`, `REINDEX CONCURRENTLY`, `REFRESH MATERIALIZED VIEW`, `DROP TABLE`, `DELETE`, `setval`); `PulseBudget(50, 600s)`; missing `get_bg_pool_semaphore()` and GUC `finally` reset (`CE-08`) | Runs every `6h`; lowers rule confidence on `failure` (`rules_engine.py:78-95`); **no cross-process lock** (`CE-07`)                                                                                                       | `PARTIAL` | `UNK-B07-04`               |
| `src_596b45ec9f303d3c` (`scripts/visa_engine/retention_worker.py`)                                                                     | `op_d02_d11_visa_garuda_retention` | `postgresql:nuzantara-postgres` (`visa_decision_retention_policies`, `visa_decisions`, `visa_evaluate_idempotency`, `garuda_voa_checks`, `garuda_voa_check_results`)                                                 | Dedicated non-superuser, non-`backend_rag_v2` role via `VISA_ENGINE_RETENTION_DATABASE_URL` (`_assert_operator_boundary`)                                                      | Calls bounded `SECURITY DEFINER` purge functions (`limit=1000`, `max_batches=20`)                                                                                                                                                  | Batch-loop until `deleted < limit`; verifies live policy against `load_approved_privacy_policy()`; unscheduled in `organism_entrypoints.json` (`IN-03`)                                                                   | `PARTIAL` | `UNK-B07-03`, `UNK-B07-05` |
| `entry_a14536f32ddbc648` (`pro.outbox_prune_daily` / `scripts/outbox-prune.sh`)                                                        | `op_d11_outbox_prune_daily`        | `postgresql:nuzantara-postgres` (`events_outbox`)                                                                                                                                                                    | `DATABASE_URL` from `~/.nuzantara-secrets.env` on `Pro` (rewritten to `127.0.0.1:15432` if `pg-proxy` up)                                                                      | Single connection `command_timeout=300` calling `prune_consumed(conn, older_than_days=30)`                                                                                                                                         | Daily LaunchAgent at `03:15`; hardcodes `REPO_ROOT="${HOME}/nuzantara"` (`CE-09`)                                                                                                                                         | `PARTIAL` | `UNK-B07-05`               |

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION` for this file's bytes with SHA256 `cdade916a3803c830e2db5a8f065f6e277187e847f93bf2e14f9b9458744831f` at candidate `f56373bc6f87cb835f05b6215a7825f165e55e21`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (addendum, removals) apply its findings and were not re-reviewed.
