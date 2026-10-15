# B07 Proposal — Maintenance and Migration Lineage Adapter, Invariant Suite & Remediation Plan

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B07` — Maintenance and migration lineage (`D02`, `D11`, `D13`)
- **Host / Worktree**: `Mini` / `~/nuzantara/.worktrees/db-udb-b07-lineage`
- **Base Commit**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Role**: Gemini block lead (`EXTERNAL PREPARER, NO_DUX`)
- **Write Scope (`BATTLE.md` §2)**: `own lineage reports/adapters only; migration directories are read-only`

---

## 1. Design Objectives & Sibling Contract Binding

To close the `PARTIAL (55%)` gaps on `D02`, `D11`, and `D13` without mutating read-only migration directories or production runtime code, `B07` proposes a deterministic, zero-PII **Lineage Adapter & Verifier** (`b07_lineage_adapter.py`) paired with a **Negative & Invariant Test Suite** (`test_b07_lineage_invariants.py`) inside `research/operations/udb-wave8/B07/`.

Every emitted lineage record strictly conforms to the frozen sibling contract (`BATTLE.md` §3):
- **Common Envelope Fields**:
  `consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns`
- **B05 Operation Instance Fields**:
  `principal,role,tenant,authorization,transaction,effects,retries,idempotency,failure,retention,recovery`

---

## 2. Proposed B07 Deliverables (Within Owned Report/Adapter Directory)

### 2.1 Deliverable 1: `research/operations/udb-wave8/B07/b07_lineage_adapter.py`
A pure-Python, read-only static + receipt-joining adapter that inspects the worktree at `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` and optional Dux live-catalog receipts (`DR-B07-01`..`DR-B07-05`) to emit:
1. **`b07-operations-matrix.csv` / `.json`** (conforming 1:1 to `BATTLE.md` §3 common + B05 fields):
   - **`D13` Migration Runners & Ledgers**:
     - Enumerates all numbered SQL files in `apps/backend-rag/backend/db/migrations_v2/*.sql` (`092`..`323`), computing:
       - `full_file_sha256` (matching `BaseMigration._calculate_checksum` at `migration_base.py:842-844`),
       - `forward_sql_sha256` (hash of `sql_forward` after `split_migration_sql` at `migration_base.py:710-722`),
       - `rollback_sql_present` (`bool`) and `rollback_sql_sha256`,
       - `tx_mode` (`autocommit_concurrently` when `CREATE/DROP INDEX CONCURRENTLY` matches `migration_base.py:725-729`, else `explicit_tx`),
       - `declared_dependencies` (`-- Depends on:` parsed per `migration_base.py:798-808`),
       - `audit_posture` (`enforced_sha256`, `skipped_non_sha256_sentinel` for the 17 rows in `schema_audit.py:254-263`, or `demoted_legacy_baseline_warning` for the 8 rows in `schema_audit.py:315-347`).
     - Enumerates all Python migration modules (`apps/backend-rag/backend/migrations/apply_migration_*.py` and `migration_*.py`), classifying each by runner compatibility:
       - `base_migration_subclass` (discoverable by `services/misc/migration_runner.py:76-135`),
       - `procedural_untracked` (`up(pool)`, `upgrade(conn)`, `apply(conn)` — invisible to `MigrationManager` and `MigrationRunner`, writing zero rows to `_schema_versions` or `schema_migrations`),
       - `ci_deploy_wired` (`apply_migration_119`, `120`, `121` in `.github/workflows/fly-deploy.yml:489-522` vs omitted `122`, `125`, `126`).
     - Enumerates `apps/bali-intel-scraper/` Alembic (`env.py`) and raw SQL migrations (`add_indexes.sql`, `001_add_performance_indexes.sql`).
   - **`D02` Olympus & DB-Internal Maintenance**:
     - Maps `OlympusGuardian` startup in `service_initializer.py:1948-1953` (`rag` group, `alert_service` bound) and `service_initializer.py:2188-2192` (`api` group, `alert_service=None`), `HeartbeatCollector` (`heartbeat.py:38-199`), all 9 `OlympusPulse` maintenance operations (`pulse.py:72-667`), `InsightsCollector` (`insights.py:42-218`), `RulesEngine` (`rules_engine.py:19-95`), `action_timeouts` / `PulseBudget` (`safety.py:28-83`), and DB-internal triggers/functions (`_schema_versions_299_guard_fn`, `purge_visa_decisions`, `purge_visa_evaluate_idempotency`, `purge_garuda_voa_checks`, `purge_garuda_voa_check_results`, and append-only audit triggers).
   - **`D11` Scheduled & Manual Maintenance Writers**:
     - Maps all host-scheduled maintenance entrypoints (`pro.outbox_prune_daily` / `scripts/outbox-prune.sh`, `pro.backup_pg_fly`, `pro.postgres_Tunnel`, `mini.zero_sync`, `fly.rag_backend`), in-process background tasks (`service_initializer.py:1800-2261`), and manual/unscheduled workers (`retention_worker.py`, `schema_audit.py`).
2. **`b07-counterexample-report.json`**:
   - Machine-readable verification of `CE-01` through `CE-09` with exact file path, line range, file SHA-256, violated invariant, and runtime blast radius.

### 2.2 Deliverable 2: `research/operations/udb-wave8/B07/test_b07_lineage_invariants.py`
A self-contained `pytest` suite (requiring zero network or live DB access) that tests the adapter and AST/source invariants for `CE-01`..`CE-09`:
- `test_ce01_dual_ledger_asymmetry`: verifies that `MigrationManager.get_applied_migrations` queries `_schema_versions` while `BaseMigration._is_applied` and `_check_dependencies` query `schema_migrations`, and that `migration_manager.py:617-627` inserts `001_baseline_v2.sql` only into `_schema_versions`.
- `test_ce02_lock_busy_exits_zero`: verifies with a mocked `lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", 73491) -> False` that `apply_all_pending()` returns `{"applied": [], "skipped": [], "failed": []}` and `migrate.cmd_apply()` returns `True` (`exit 0`).
- `test_ce03_standalone_py_migrations_untracked_and_autocommit`: verifies `_lock_guard.py:17-40` lacks `conn.transaction()` and `migration_119_partners.py` / `apply_migration_122.py` never reference `_schema_versions` or `schema_migrations`.
- `test_ce04_migrate_cli_stdout_noop`: verifies `migrate.py` `cmd_apply` contains `for _num in result["applied"]: pass` and emits zero `"   - Migration "` lines required by `.github/workflows/fly-deploy.yml:373`.
- `test_ce05_schema_audit_uses_migration_dsn`: verifies `schema_audit.py:761` delegates `database_url=None` to `MigrationManager`, which calls `resolve_migration_dsn()`.
- `test_ce06_checksum_audit_sentinel_bypass_and_rollback_hash`: verifies `schema_audit.py:475-496` `continue`s before hashing on-disk SQL files for the 17 non-SHA256 sentinels, and `BaseMigration._log_migration` hashes unsplit `sql` rather than `sql_forward`.
- `test_ce07_olympus_dual_process_and_null_alert_service`: verifies `service_initializer.py` instantiates `OlympusGuardian` in both `initialize_services` and `initialize_services_light(..., alert_service=None)` with no cross-process lock in `guardian.py`.
- `test_ce08_olympus_pulse_missing_semaphore_and_guc_reset`: verifies `guardian.py:_pulse_loop` omits `get_bg_pool_semaphore()` and `safety.py:action_timeouts` omits a `finally` GUC reset.
- `test_ce09_outbox_prune_repo_root_mismatch`: verifies `scripts/outbox-prune.sh:58` hardcodes `REPO_ROOT="${HOME}/nuzantara"` while `organism_heartbeat` identifies the host as `pro.outbox_prune_daily`.

---

## 3. Downstream Code Remediation Roadmap (For Code-Owning Lanes After B07)

Because `B07` is strictly scoped to lineage reports/adapters (`migration directories are read-only`), the following surgical fixes are specified for the downstream runtime/migration implementation PRs:

1. **Unify Dual-Ledger Read/Write & Lock Contention Exit Code (`D13` — `migration_manager.py`, `migration_base.py`, `migrate.py`)**:
   - In `MigrationManager.apply_all_pending()` (`migration_manager.py:534-541`), return `"lock_busy": True` when `pg_try_advisory_lock(73491)` is `False`, and make `migrate.py:cmd_apply()` exit nonzero (`sys.exit(2)`) on `lock_busy`.
   - Restore structured logging/stdout in `migrate.py:cmd_status`, `cmd_list`, `cmd_apply`, and `cmd_info` so `fly-deploy.yml:373` accurately counts applied migrations.
   - Reconcile `_schema_versions` and `schema_migrations` in `MigrationManager.get_applied_migrations()` using a `FULL OUTER JOIN` on `migration_number` so a row missing from `schema_migrations` is backfilled before `_check_dependencies()` runs, and fix baseline `001` (`migration_manager.py:617-627`) to write both tables without the `.sql` suffix.
   - Reuse the advisory-locked connection or pass a retry-wrapped connection factory into `BaseMigration.apply()` (`migration_base.py:1071`).
2. **Enforce On-Disk SHA-256 Pinning & Runtime DSN Isolation in `schema_audit.py` (`D13`)**:
   - In `schema_audit.py:761`, pass `database_url=settings.database_url` explicitly so `schema_audit` never consumes `MIGRATION_DATABASE_URL` (`CE-05`).
   - Pin the current on-disk SHA-256 hashes of the 17 sentinel files (`schema_audit.py:254-263`) and 8 legacy baseline files (`schema_audit.py:315-347`) in a static dictionary inside `schema_audit.py` and hash the on-disk `.sql` files on every audit run so any future file edit fails `schema_audit` immediately (`CE-06`).
3. **Fence `OlympusGuardian` Across Process Groups & Harden `safety.py` (`D02`)**:
   - Guard `OlympusGuardian.run_pulse()` with a non-blocking PostgreSQL session advisory lock (e.g., `pg_try_advisory_lock(73492)`) or run `OlympusPulse` exclusively on one process group with `AlertService()` wired (`service_initializer.py:2188`, `CE-07`).
   - Wrap `_pulse_loop()` in `async with get_bg_pool_semaphore():` (`guardian.py:219-227`), add a `try/finally` block in `safety.py:action_timeouts` (`RESET statement_timeout; RESET lock_timeout`), wrap `cleanup_audit_trail` and `refresh_materialized_views` in `action_timeouts`, and ensure `ensure_next_partition()` (`pulse.py:461-510`) also checks the current month (`CE-08`).
4. **Fix `scripts/outbox-prune.sh` Repo Path & Schedule `retention_worker.py` (`D11`)**:
   - In `scripts/outbox-prune.sh:58`, resolve `REPO_ROOT` dynamically (`[ -d "${HOME}/Desktop/nuzantara" ] && REPO_ROOT="${HOME}/Desktop/nuzantara" || REPO_ROOT="${HOME}/nuzantara"`) and emit `organism_heartbeat "pro.outbox_prune_daily" "fail"` on missing `.venv` (`CE-09`).
   - Register a scheduled entrypoint for `backend.scripts.visa_engine.retention_worker --apply --scope VISA_DECISION --scope GARUDA_CHECK` in `organism_entrypoints.json` using `VISA_ENGINE_RETENTION_DATABASE_URL` (`IN-03`).

---

## DUX-REQUESTS

To resolve `UNK-B07-01` through `UNK-B07-05` with live proof (while preserving the strict PII boundary: aggregate counts, catalog names, and SHA-256 hashes only — zero client rows, zero PII, zero secret values), `B07` requests that Dux execute the following 5 read-only commands and drop their JSON outputs into `research/operations/udb-wave8/B07/receipts/`:

### `DR-B07-01` — On-Disk SQL & Python Migration SHA-256 Manifest
- **ID**: `DR-B07-01`
- **Command**:
  ```bash
  python3 -c '
  import hashlib, json, pathlib, re
  root = pathlib.Path("apps/backend-rag/backend")
  out = {"migrations_v2": [], "py_migrations": []}
  for p in sorted((root / "db/migrations_v2").glob("*.sql")):
      raw = p.read_text(encoding="utf-8")
      parts = re.split(r"^--\s*===\s*ROLLBACK\s*===\s*$", raw, maxsplit=1, flags=re.M)
      fwd = parts[0].strip()
      rb = parts[1].strip() if len(parts) > 1 else ""
      out["migrations_v2"].append({
          "file": p.name,
          "full_sha256": hashlib.sha256(raw.encode()).hexdigest(),
          "forward_sha256": hashlib.sha256(fwd.encode()).hexdigest(),
          "has_rollback": bool(rb),
          "has_concurrently": bool(re.search(r"(CREATE|DROP)\s+INDEX\s+CONCURRENTLY", fwd, re.I)),
      })
  for p in sorted((root / "migrations").glob("*.py")):
      raw = p.read_bytes()
      out["py_migrations"].append({"file": p.name, "sha256": hashlib.sha256(raw).hexdigest()})
  print(json.dumps(out, indent=2))
  '
  ```
- **Inputs**: `apps/backend-rag/backend/db/migrations_v2/*.sql`, `apps/backend-rag/backend/migrations/*.py`
- **Expected Output Shape**: JSON object `{"migrations_v2": [{"file", "full_sha256", "forward_sha256", "has_rollback", "has_concurrently"}, ...], "py_migrations": [{"file", "sha256"}, ...]}`.
- **Why It Matters**: Pins `evidence_sha256` for all `D13` migration files on disk and quantifies how many files differ between `full_sha256` and `forward_sha256` (`CE-06`).

### `DR-B07-02` — Live Dual-Ledger Reconciliation & Provenance Aggregate (`_schema_versions` vs `schema_migrations`)
- **ID**: `DR-B07-02`
- **Command** (run via read-only DB connection to `nuzantara-postgres`):
  ```sql
  SELECT json_build_object(
    'schema_versions_count', (SELECT count(*) FROM public._schema_versions),
    'schema_migrations_count', (SELECT count(*) FROM public.schema_migrations),
    'provenance_populated_count', (SELECT count(*) FROM public._schema_versions WHERE applied_as IS NOT NULL AND applied_via IS NOT NULL AND runner_version IS NOT NULL),
    'applied_via_breakdown', (SELECT json_object_agg(coalesce(applied_via, 'NULL'), cnt) FROM (SELECT applied_via, count(*) AS cnt FROM public._schema_versions GROUP BY applied_via) s),
    'in_versions_not_migrations', (SELECT coalesce(json_agg(v.migration_number ORDER BY v.migration_number), '[]'::json) FROM public._schema_versions v LEFT JOIN public.schema_migrations m ON v.migration_number = m.migration_number WHERE m.migration_number IS NULL),
    'in_migrations_not_versions', (SELECT coalesce(json_agg(m.migration_number ORDER BY m.migration_number), '[]'::json) FROM public.schema_migrations m LEFT JOIN public._schema_versions v ON m.migration_number = v.migration_number WHERE v.migration_number IS NULL),
    'checksum_mismatch_between_ledgers', (SELECT coalesce(json_agg(v.migration_number ORDER BY v.migration_number), '[]'::json) FROM public._schema_versions v JOIN public.schema_migrations m ON v.migration_number = m.migration_number WHERE coalesce(v.checksum, '') <> coalesce(m.checksum, '')),
    'ledger_rows', (SELECT json_agg(row_to_json(t) ORDER BY t.migration_number) FROM (SELECT v.migration_number, v.version_name, m.migration_name, v.checksum AS v_checksum, m.checksum AS m_checksum, v.status AS v_status, m.status AS m_status, v.applied_by, v.applied_as, v.applied_via, v.runner_version FROM public._schema_versions v FULL OUTER JOIN public.schema_migrations m ON v.migration_number = m.migration_number) t)
  );
  ```
- **Inputs**: `public._schema_versions`, `public.schema_migrations` in `nuzantara-postgres`.
- **Expected Output Shape**: Single JSON object containing aggregate counts, symmetric differences, and the non-PII ledger join.
- **Why It Matters**: Resolves `UNK-B07-01` and `UNK-B07-02` by proving the exact live state of both migration ledgers and joining live checksums against `DR-B07-01`.

### `DR-B07-03` — Live `pg_proc` (`SECURITY DEFINER`), `pg_trigger`, and `pg_event_trigger` Catalog Inventory (`D02`)
- **ID**: `DR-B07-03`
- **Command** (run via read-only DB connection to `nuzantara-postgres`):
  ```sql
  SELECT json_build_object(
    'security_definer_functions', (
      SELECT coalesce(json_agg(row_to_json(f) ORDER BY f.schema_name, f.proname), '[]'::json)
      FROM (
        SELECT n.nspname AS schema_name, p.proname, pg_get_function_identity_arguments(p.oid) AS args,
               r.rolname AS owner_role, p.prosecdef AS security_definer,
               encode(sha256(convert_to(pg_get_functiondef(p.oid), 'UTF8')), 'hex') AS def_sha256
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_roles r ON r.oid = p.proowner
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND (p.prosecdef = true OR p.proname LIKE '%purge%' OR p.proname LIKE '%audit%' OR p.proname LIKE '%guard%')
      ) f
    ),
    'user_triggers', (
      SELECT coalesce(json_agg(row_to_json(t) ORDER BY t.table_schema, t.table_name, t.tgname), '[]'::json)
      FROM (
        SELECT ns.nspname AS table_schema, c.relname AS table_name, tg.tgname, tg.tgenabled,
               p.proname AS function_name, encode(sha256(convert_to(pg_get_triggerdef(tg.oid), 'UTF8')), 'hex') AS triggerdef_sha256
        FROM pg_trigger tg
        JOIN pg_class c ON c.oid = tg.tgrelid
        JOIN pg_namespace ns ON ns.oid = c.relnamespace
        JOIN pg_proc p ON p.oid = tg.tgfoid
        WHERE NOT tg.tgisinternal AND ns.nspname NOT IN ('pg_catalog', 'information_schema')
      ) t
    ),
    'event_triggers', (
      SELECT coalesce(json_agg(row_to_json(e) ORDER BY e.evtname), '[]'::json)
      FROM (SELECT evtname, evtevent, evtenabled, evtfoid::regproc::text AS function_name FROM pg_event_trigger) e
    )
  );
  ```
- **Inputs**: `pg_proc`, `pg_trigger`, `pg_event_trigger`, `pg_class`, `pg_namespace`, `pg_roles`.
- **Expected Output Shape**: Single JSON object with function signatures, owner roles, trigger attachments, and SHA-256 hashes of definitions.
- **Why It Matters**: Resolves `UNK-B07-03` by binding installed DB-internal functions and triggers (`D02`) to repo migration DDL by SHA-256.

### `DR-B07-04` — Live Olympus Partition & Action Outcome Aggregate (`D02`)
- **ID**: `DR-B07-04`
- **Command** (run via read-only DB connection to `nuzantara-postgres`):
  ```sql
  SELECT json_build_object(
    'heartbeat_partitions', (
      SELECT coalesce(json_agg(row_to_json(p) ORDER BY p.partition_name), '[]'::json)
      FROM (
        SELECT c.relname AS partition_name, pg_get_expr(c.relpartbound, c.oid) AS bound_expr,
               c.reltuples::bigint AS approx_rows
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class parent ON parent.oid = i.inhparent
        WHERE parent.relname = 'olympus_heartbeats'
      ) p
    ),
    'actions_by_rhythm_outcome', (
      SELECT coalesce(json_agg(row_to_json(a) ORDER BY a.rhythm, a.action_type, a.outcome), '[]'::json)
      FROM (
        SELECT rhythm, action_type, outcome, count(*) AS cnt, max(executed_at) AS last_executed_at
        FROM public.olympus_actions
        GROUP BY rhythm, action_type, outcome
      ) a
    ),
    'rules_summary', (
      SELECT coalesce(json_agg(row_to_json(r) ORDER BY r.rule_name), '[]'::json)
      FROM (
        SELECT rule_name, category, source, confidence, times_applied, last_applied_at
        FROM public.olympus_rules
      ) r
    )
  );
  ```
- **Inputs**: `pg_inherits`, `pg_class`, `public.olympus_actions`, `public.olympus_rules`.
- **Expected Output Shape**: Single JSON object with partition bounds/row estimates (`olympus_heartbeats_*`), action outcome counts, and active Olympus rules.
- **Why It Matters**: Resolves `UNK-B07-04` by verifying whether `ensure_next_partition` (`CE-08`) left rows in `olympus_heartbeats_default` and whether dual-process pulses (`CE-07`) caused duplicate/failed actions.

### `DR-B07-05` — Host Scheduler & Retention Worker Registration Check (`D11`)
- **ID**: `DR-B07-05`
- **Command** (read-only check on `Mini` and `Pro` host schedulers):
  ```bash
  python3 -c '
  import json, pathlib
  p = pathlib.Path("scripts/ableton_heartbeats/organism_entrypoints.json")
  if not p.exists():
      matches = list(pathlib.Path(".").rglob("organism_entrypoints.json"))
      p = matches[0] if matches else None
  data = json.loads(p.read_text()) if p else {}
  print(json.dumps({"path": str(p), "entrypoint_count": len(data) if isinstance(data, (list, dict)) else 0}, indent=2))
  '
  ```
- **Inputs**: `organism_entrypoints.json` in repo + read-only verification on `Pro` of whether `~/nuzantara` exists or is a symlink to `~/Desktop/nuzantara` (`test -e ~/nuzantara && ls -ld ~/nuzantara`).
- **Expected Output Shape**: JSON summary of `organism_entrypoints.json` and boolean/target for `~/nuzantara` on `Pro` plus any scheduler entry referencing `retention_worker.py`.
- **Why It Matters**: Resolves `UNK-B07-05` (`CE-09` and `IN-03`) by confirming whether `pro.outbox_prune_daily` fails on `Pro` due to `REPO_ROOT="${HOME}/nuzantara"` and whether `retention_worker.py` has any active scheduler.
