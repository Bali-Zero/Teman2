---
adversarial_review: codex
reviewed_source_sha256: "6de9d4b53d88661038a6dfcf9210f4b23d6600389b9bc8603a68e78be70ece87"
review_disposition: HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED
---

# B07 Proposal — Maintenance and Migration Lineage Adapter, Invariant Suite & Remediation Plan

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
   - Machine-readable verification of `CE-01` through `CE-08` with exact file path, line range, file SHA-256, violated invariant, and runtime blast radius.

### 2.2 Deliverable 2: `research/operations/udb-wave8/B07/test_b07_lineage_invariants.py`

A self-contained `pytest` suite (requiring zero network or live DB access) that tests the adapter and AST/source invariants for `CE-01`..`CE-08`:

- `test_ce01_dual_ledger_asymmetry`: verifies that `MigrationManager.get_applied_migrations` queries `_schema_versions` while `BaseMigration._is_applied` and `_check_dependencies` query `schema_migrations`, and that `migration_manager.py:617-627` inserts `001_baseline_v2.sql` only into `_schema_versions`.
- `test_ce02_lock_busy_exits_zero`: verifies with a mocked `lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", 73491) -> False` that `apply_all_pending()` returns `{"applied": [], "skipped": [], "failed": []}` and `migrate.cmd_apply()` returns `True` (`exit 0`).
- `test_ce03_standalone_py_migrations_untracked_and_autocommit`: verifies `_lock_guard.py:17-40` lacks `conn.transaction()` and `migration_119_partners.py` / `apply_migration_122.py` never reference `_schema_versions` or `schema_migrations`.
- `test_ce04_migrate_cli_stdout_noop`: verifies `migrate.py` `cmd_apply` contains `for _num in result["applied"]: pass` and emits zero `"   - Migration "` lines required by `.github/workflows/fly-deploy.yml:373`.
- `test_ce05_schema_audit_uses_migration_dsn`: verifies `schema_audit.py:761` delegates `database_url=None` to `MigrationManager`, which calls `resolve_migration_dsn()`.
- `test_ce06_checksum_audit_sentinel_bypass_and_rollback_hash`: verifies `schema_audit.py:475-496` `continue`s before hashing on-disk SQL files for the 17 non-SHA256 sentinels, and `BaseMigration._log_migration` hashes unsplit `sql` rather than `sql_forward`.
- `test_ce07_olympus_dual_process_and_null_alert_service`: verifies `service_initializer.py` instantiates `OlympusGuardian` in both `initialize_services` and `initialize_services_light(..., alert_service=None)` with no cross-process lock in `guardian.py`.
- `test_ce08_olympus_pulse_missing_semaphore_and_guc_reset`: verifies `guardian.py:_pulse_loop` omits `get_bg_pool_semaphore()` and `safety.py:action_timeouts` omits a `finally` GUC reset.

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

Withdrawn after independent review. No query body or execution request is retained. Schema, authorization and privacy assumptions were not admitted; any native reconciliation needs a separately validated read-only specification.

### `DR-B07-03` — Live `pg_proc` (`SECURITY DEFINER`), `pg_trigger`, and `pg_event_trigger` Catalog Inventory (`D02`)

Withdrawn after independent review. No query body or execution request is retained. Schema, authorization and privacy assumptions were not admitted; any native reconciliation needs a separately validated read-only specification.

### `DR-B07-04` — Live Olympus Partition & Action Outcome Aggregate (`D02`)

Withdrawn after independent review. No query body or execution request is retained. Schema, authorization and privacy assumptions were not admitted; any native reconciliation needs a separately validated read-only specification.

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
- **Why It Matters**: Tests the scheduler/path hypotheses with host observations. The original wrong-Pro-path and absent-retention-scheduler claims were refuted; neither is an active finding.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED` for this file's bytes with SHA256 `6de9d4b53d88661038a6dfcf9210f4b23d6600389b9bc8603a68e78be70ece87` at candidate `f56373bc6f87cb835f05b6215a7825f165e55e21`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (addendum, removals) apply its findings and were not re-reviewed.
