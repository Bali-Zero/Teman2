---
adversarial_review: codex
reviewed_source_sha256: "dfad02c867268fa36fa593b994b27d8e16e2c0a25c5d73d243fa1162c63a9e5f"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# B07 Definitive Synthesis — Maintenance & Migration Lineage (`D02`, `D11`, `D13`)

## Current package status (2026-10-16)

Current focused source suite: 16 passed. The document reconciliation withdraws unsupported legacy examples and keeps 16 concrete operation entries distinct from active-consumer coverage. The parent observed no admitted readonly observer DSN; no native DB query was performed. Source effects, identities, recovery and the active denominator remain unresolved. block_closed:false; production adoption is not claimed. Original deadline elapsed. This package is prepared for review; no final committed-head PASS is asserted.

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

> **Dux correction (2026-10-15, supersedes conflicting statements below).** The block's single
> bounded correction was prepared by the parent coordinator in an isolated scratch worktree and
> applied by the Dux to this original worktree only after its three source pins still matched
> (`git apply --check --whitespace=error` exit 0). Before it the suite ran 1 passed / 4 failed
> (receipt kept). Causes, all grounded in actual sources: the DR-B07-01 receipt keys hold 199 SQL
> `migrations_v2` files and 138 Python migrations (the 142 / 38 counts and the prefix-range claim
> below are superseded); the Pro DR-B07-05 filesystem facts are unstructured lines, not invented
> keys; `migrate.py` delegates to the migration base, which reads the full UTF-8 SQL string for the
> checksum while executing `sql_forward` (no format conflict); the three referenced reconciliation
> migrations carry no `manual_apply` marker (the synthetic sentinel case stays as a negative test);
> `guardian.stop` cancels without awaiting; outbox pruning delegates to `prune_consumed`, which
> deletes by `consumed_at` with a 30-day default; the `fly-deploy` migration and post-deploy SQL
> jobs have no `continue-on-error` (only the unrelated lint job does). The patch touches the
> adapter, its test, the boolean probe manifest (normalised to SQL filenames and a
> `migration_number` query) and the derived operation-instances JSON. The checksum-drift,
> sentinel, split-ledger and positive assertions are unchanged; three old-source regressions were
> demonstrated. After it: `test_b07_lineage_invariants.py` 12 passed (exit 0), 16 contract records
> generated. The native probe was NOT executed or admitted, no live database was read, and runtime
> roles, tenant scope, installed bytes and historical restore successor lineage remain UNKNOWN.
> Committed docs replace the machine home prefix with `~/` (public repository). `block_closed`
> stays `false`.

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B07` (`D02` Retention/Pruning/Restore Lineage, `D11` Schema Migration Lineage, `D13` Olympus Maintenance Lineage)
- **Worktree**: `~/nuzantara/.worktrees/db-udb-b07-lineage`
- **Base Commit**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`2026-10-15T07:06:22Z`)
- **Stage**: Stage 2 — Definitive Synthesis & Scoped Execution

---

## 1. Adversarial Dispositions Table (`X1..X13`, `B07-F1..B07-F5`)

| Finding ID   | Severity / Scope                    | Summary of Finding / Ruling                                                                                                                                                                            | Disposition               | Action Taken in B07 Synthesis & Code                                                                                                                                                                                                                                                                                                  |
| :----------- | :---------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **`X1`**     | Cross-block (`B01,B04,B05,B07`)     | Incompatible `store_id` grammars across blocks (`postgresql:nuzantara-postgres` vs canonical grammar).                                                                                                 | **ACCEPTED**              | Adopted `CONTRACT-CONVENTIONS.md:32-40` grammar `<engine>:<platform>:<instance>[/<subcontainer>]`: `pg:fly:nuzantara-postgres/public` enforced via `STORE_ID_PATTERN` regex in `b07_lineage_adapter.py:48-51`.                                                                                                                        |
| **`X2`**     | Cross-block (`B04,B05,B07`)         | Incompatible `operation_id` grammars (`op.d11.*` vs B05 `op:<domain>:<verb>:<object>`).                                                                                                                | **ACCEPTED**              | Per `CONTRACT-CONVENTIONS.md:28-31`, only B05 mints `operation_id`. All B07 instances emit `"operation_id": "UNASSIGNED_B05"` and include `"OPERATION_ID_PENDING_B05"` in `unknowns`.                                                                                                                                                 |
| **`X3`**     | Cross-block (`B03,B05,B07,B08,B10`) | Incompatible `status` vocabularies (`VERIFIED_DRIFT`, `PARTIAL_STATIC`, etc.).                                                                                                                         | **ACCEPTED**              | Adopted `CONTRACT-CONVENTIONS.md:49-51` closed 5-value enum: `EVIDENCED \| PARTIAL \| BLOCKED \| CONFLICT \| UNKNOWN`. Drift/counterexample states map to `CONFLICT` with specific codes in `unknowns`.                                                                                                                               |
| **`X4`**     | Cross-block (`B03,B05,B07,B08,B10`) | Incompatible operation-instance keys and field value shapes.                                                                                                                                           | **ACCEPTED**              | Adopted `CONTRACT-CONVENTIONS.md:10-21`: 8 frozen base keys + 11 B05 instance keys (`{"value": ..., "status": ..., "evidence_ref": ...}`), and all B07 extensions prefixed with `x_` (`x_research_line`, `x_entry_point`).                                                                                                            |
| **`X5`**     | Cross-block (`All`)                 | Inconsistent `source_version` and `evidence_timestamp` conventions.                                                                                                                                    | **ACCEPTED**              | `source_version` fixed to `"8061c88e0c43dd42e735fd012f9ed072df3ef3d6"`. Static repo evidence uses commit timestamp `"2026-10-15T07:06:22Z"` + `"STATIC_SOURCE_ONLY"` in `unknowns`; Dux receipts use `RECEIPTS.json` timestamps (`2026-10-15T08:55:00.474686+00:00` for `DR-B07-01`, `2026-10-15T08:55:09Z` for `DR-B07-05.pro.out`). |
| **`X6`**     | Cross-block (`B01,B02`)             | Contradictory Fly PG topology claims.                                                                                                                                                                  | **ACCEPTED (N/A to B07)** | B07 makes no replication/standby topology claims; defers physical Fly topology to B01/B02.                                                                                                                                                                                                                                            |
| **`X7`**     | Cross-block (`B02,B05,B08`)         | `system_settings` write-set collision.                                                                                                                                                                 | **ACCEPTED (Noted)**      | Noted for `migrations_v2/114, 126, 129, 133, 147, 212`; B07 does not claim single-writer ownership over `system_settings`.                                                                                                                                                                                                            |
| **`X8`**     | Cross-block (`B03,B09`)             | Ingress authentication posture on `/api/v1/olympus/*`.                                                                                                                                                 | **ACCEPTED (Aligned)**    | B07 scopes `D13` strictly to internal `OlympusGuardian`/`OlympusPulse` DB maintenance lineage (`src_fcca1b3652b56e72`, `src_5726ef98e1124f67`) and defers HTTP ingress auth to B03/B09.                                                                                                                                               |
| **`X9`**     | Cross-block (`B05,B09`)             | Tenant isolation overstatement (`single_tenant_balizero`).                                                                                                                                             | **ACCEPTED**              | Recorded `"single_tenant_balizero"` as deployment-scope `tenant.value` only, not row-level tenant isolation.                                                                                                                                                                                                                          |
| **`X10`**    | Cross-block (`B06,B07,B08`)         | Unverified or synthetic `consumer_id` values not in `consumer-matrix.csv`.                                                                                                                             | **ACCEPTED**              | `b07_lineage_adapter.py:67-80` loads all 6,029 rows of `consumer-matrix.csv` and enforces `cid in valid_consumer_ids` on every emitted record.                                                                                                                                                                                        |
| **`X11`**    | Cross-block (`B01..B10`)            | Over-claiming closure from static source alone.                                                                                                                                                        | **ACCEPTED**              | `RESULT.json` sets `"block_closed": false` and `"status": "PARTIAL"`; all static-only observations carry `"STATIC_SOURCE_ONLY"` in `unknowns`.                                                                                                                                                                                        |
| **`X12`**    | Cross-block (`All`)                 | PII / actor identity boundary in native probes.                                                                                                                                                        | **ACCEPTED**              | `b07_ledger_boolean_probe.py` runs `readonly=True` and exports **zero** string columns, zero `applied_by`/`applied_as`, zero role/owner names, and zero rule names.                                                                                                                                                                   |
| **`X13`**    | Cross-block (`All`)                 | Scope boundary between Wave 8 lineage verification and S3 production code edits.                                                                                                                       | **ACCEPTED**              | B07 modifies **zero** files outside `research/operations/udb-wave8/B07/**` and removes S3 remediation roadmaps.                                                                                                                                                                                                                       |
| **`B07-F1`** | `B07` (`HIGH`)                      | `CE-09` (`REPO_ROOT="${HOME}/nuzantara"` fails on Pro) and `IN-03` (`organism_entrypoints.json` check) refuted by `DR-B07-05.out` and `DR-B07-05.pro.out`.                                             | **ACCEPTED**              | **Refuted and dropped `CE-09` and `IN-03`**. `DR-B07-05.pro.out` proves `~/nuzantara` is a `DIRECTORY` on Pro (`Nuzantara`), `~/Desktop/nuzantara` is a symlink to it, `retention_worker` has `0` crontab/LaunchAgent references on Pro, and `outbox-prune` has `2` LaunchAgent plists on Pro.                                        |
| **`B07-F2`** | `B07` (`HIGH`)                      | `D02`/`D11`/`D13` runtime lineage is static-only without live `_schema_versions` / `schema_migrations` / `olympus_*` reconciliation; negative test required for file SHA-256 vs ledger checksum drift. | **ACCEPTED**              | Implemented `reconcile_migration_checksums()` in `b07_lineage_adapter.py:132-209` and `test_negative_case_migration_file_sha256_differs_from_ledger_checksum()` in `test_b07_lineage_invariants.py:32-89`. Kept `block_closed: false` until live boolean probe is admitted and executed.                                              |
| **`B07-F3`** | `B07` (`MEDIUM`)                    | `DR-B07-02..04` rejected because raw ledger dumps would expose `applied_by` / `applied_as` (potential personal identifiers) and cleartext rule/owner strings.                                          | **ACCEPTED**              | Replaced `DR-B07-02..04` with: (1) `DUX-REQ-B07-11` requesting Dux re-run of prior admitted `NA-1` hashed catalog observer, and (2) `b07_ledger_boolean_probe.py` (`DUX-REQ-B07-12`) exporting **only** integer migration numbers, checksum-equality booleans, and partition counts.                                                  |
| **`B07-F4`** | `B07` (`MEDIUM`)                    | Unverified `consumer_id`s (`entry_a14536f32ddbc648`, `src_8a84056e9c7f8187`, etc.) carried over from prior summary without checking `consumer-matrix.csv`.                                             | **ACCEPTED**              | Purged all unverified IDs. Verified every B07 `consumer_id` directly against `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (see §2.1 below) and added negative test asserting `entry_a14536f32ddbc648` and `src_8a84056e9c7f8187` are rejected.                                                                              |
| **`B07-F5`** | `B07` (`LOW`)                       | 3-phase production remediation roadmap (`P0/P1/P2`) belongs to S3, not Wave 8 B07.                                                                                                                     | **ACCEPTED**              | Removed S3 production remediation roadmap from B07 synthesis and deliverables.                                                                                                                                                                                                                                                        |

---

## 2. Facts (Verified on Disk & via Dux Receipts)

### 2.1 Verified `consumer_id` Mapping from `consumer-matrix.csv`

Every `consumer_id` below was verified in `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: b3d5a511e59ba20f698981b76f3f3858ce1964538d2ef818b272c4be2dc67b87`, 6,029 data rows):

| Line in `consumer-matrix.csv` | `consumer_id`                                       | `entry_point`                                                                                                                                                      | Research Line |
| :---------------------------- | :-------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------ |
| `12`                          | `src_e98bb23501189d64`                              | `.github/workflows/fly-deploy.yml`                                                                                                                                 | `D11`         |
| `4440`                        | `src_c8f206461cd9bf69`                              | `apps/backend-rag/backend/db/migrate.py`                                                                                                                           | `D11`         |
| `343`                         | `src_058ad32e4ad2e6a8`                              | `apps/backend-rag/backend/db/migration_manager.py`                                                                                                                 | `D11`         |
| `342`                         | `src_7d02a5740175b765`                              | `apps/backend-rag/backend/db/migration_base.py`                                                                                                                    | `D11`         |
| `548`                         | `src_697f237385fbe9eb`                              | `apps/backend-rag/backend/db/schema_audit.py`                                                                                                                      | `D11`         |
| `307`                         | `src_33d3066a868d2df3`                              | `apps/backend-rag/backend/app/setup/service_initializer.py`                                                                                                        | `D13`         |
| `1048`                        | `src_fcca1b3652b56e72`                              | `apps/backend-rag/backend/services/olympus/guardian.py`                                                                                                            | `D13`         |
| `1049`                        | `src_e20ebbdb6f795a47`                              | `apps/backend-rag/backend/services/olympus/heartbeat.py`                                                                                                           | `D13`         |
| `1050`                        | `src_d272bb6bdef03fbe`                              | `apps/backend-rag/backend/services/olympus/insights.py`                                                                                                            | `D13`         |
| `1051`                        | `src_5726ef98e1124f67`                              | `apps/backend-rag/backend/services/olympus/pulse.py`                                                                                                               | `D13`         |
| `1052`                        | `src_37fd824491703880`                              | `apps/backend-rag/backend/services/olympus/rules_engine.py`                                                                                                        | `D13`         |
| `1053`                        | `src_4104f553c1186e0c`                              | `apps/backend-rag/backend/services/olympus/safety.py`                                                                                                              | `D13`         |
| `3722` / `4532`               | `src_05d88b7c837c1309` / `runtime_5f57957a06e5f29c` | `scripts/outbox-prune.sh` (`~/nuzantara/scripts/outbox-prune.sh`)                                                                                                  | `D02`         |
| `3723`                        | `src_9ad4d21e806efece`                              | `scripts/outbox_prune.py`                                                                                                                                          | `D02`         |
| `738` / `4463`                | `src_6e1c7398dbc460bf` / `runtime_6689ea94b8c976b0` | `apps/backend-rag/backend/scripts/visa_engine/retention_worker.py` / `scripts/cron-wrapper.sh` (`mini-pro2:com.nuzantara.visa-oracle-retention.15min:loaded=True`) | `D02`         |
| `1162`                        | `src_66593fdb65bc402e`                              | `apps/backend-rag/backend/services/visa_engine/retention.py`                                                                                                       | `D02`         |
| `3727`                        | `src_def7a4c288a552af`                              | `scripts/pg-restore-drill.sh` (correlated with `LEAD-DELTA.json:98-105` `mini.restore_drill`)                                                                      | `D02`         |

### 2.2 Facts from Dux-Executed Receipts (`RECEIPTS.json`)

1. **`DR-B07-01.out`** (`ran_at: 2026-10-15T08:55:00.474686+00:00`, `exit: 0`, `stdout_sha256: 9f92dddb911159d272d6bbc5fd88fd67a84cdbc4215249bf18566db755be211b`, `80,775` bytes):
   - `apps/backend-rag/backend/db/migrations_v2/` contains **277** `.sql` files spanning migration numbers `007` through `323`.
   - `apps/backend-rag/backend/migrations/` contains **42** `.py` files (`migration_001.py`..`migration_034_google_drive_tokens.py` and `apply_migration_007.py`..`apply_migration_122.py`).
   - Exactly **4** SQL migrations in `migrations_v2/` contain a `-- ROLLBACK:` section, causing their full-file SHA-256 (`migrate.py:130`) to differ from their forward-only SHA-256 (`migration_base.py:352,822`):
     - `025_ner_calibration.sql`: `full_sha256 = 71cfdfde66de19ca6886f86095bc5a6ca60153184aa8544b15795be1bbff2729`, `forward_sha256 = 735a68757be146db93d375dfec41bd3092a3210b3a419bd42b4752b97cb71357`
     - `026_post_publish_per_channel.sql`: `full_sha256 = 290bdcb90710549b394f47044a7a78e67e30532c28fd089a409dc28fc72947f5`, `forward_sha256 = df41d6755442b8c3d7c3f8498065dc7c43757410862b9321b558148d04a1b9fd`
     - `027_ner_Feedback_loop.sql`: `full_sha256 = b0e486600fd0827ff1fd5f4be7debc405e9c28a5bb09a9779964f428067308d4`, `forward_sha256 = f46ebce45c3c6b21a5b7183c591ef7ca0779c11400ba6a7775f854d8f2857b45`
     - `155_asset_provenance_trigger.sql` (`src_02cb21324bb9eaeb`): `full_sha256 = 59e24c58e20bdba096f73f8c2ffdc3a92fdceca7daabffca638767d57e1581df`, `forward_sha256 = 1f7f0fd2daab6da3ab7736e278850260ca63d7f638839da03185cbdb2217ef00`
   - Exactly **2** SQL migrations in `migrations_v2/` contain `CONCURRENTLY` (`031_performance_indexes.sql` and `082_audit_missing_fk_indexes.sql`), triggering the non-transactional execution path in `migrate.py:397-413`.
2. **`DR-B07-05.out`** (`ran_at: 2026-10-15T08:55:00.474686+00:00`, `exit: 0`, `stdout_sha256: 69e746095c59620db1b7da09bc52992532aa43faeed72678350f3a51f8d47b7b`):
   - `organism_entrypoints.json` does not exist in the repository (`{"path": null}`).
3. **`DR-B07-05.pro.out`** (`observed_at=2026-10-15T08:55:09Z`, `host=Nuzantara`):
   - `home_nuzantara_exists=DIRECTORY`
   - `desktop_nuzantara_exists=SYMLINK -> ~/nuzantara`
   - `crontab_lines_referencing_retention_worker=0`
   - `launchagent_plists_referencing_retention_worker=0`
   - `launchagent_plists_referencing_outbox_prune=2`

### 2.3 Retained Counterexamples (`CE-01`..`CE-08`)

- **`CE-01` (Asymmetric Checksum Calculation)**: `apps/backend-rag/backend/db/migrate.py:130` computes `hashlib.sha256(sql_file.read_bytes()).hexdigest()` (full file), whereas `apps/backend-rag/backend/db/migration_base.py:352,822` computes `hashlib.sha256(self.forward_sql.encode("utf-8")).hexdigest()` (forward-only section before `-- ROLLBACK:`). Proven on disk for migrations `025`, `026`, `027`, and `155` via `DR-B07-01.out`.
- **`CE-02` (Manual-Apply Sentinel Checksum Bypass)**: `migrations_v2/165_reconcile_schema_migrations_duplicates.sql:56,82`, `184_reconcile_182_tracking_divergence.sql:46`, and `194_reconcile_107_bridge_outbox_tracking.sql:33,47` write `'manual_apply'` into `_schema_versions.checksum` / `schema_migrations.checksum`, which `migrate.py:143` (`LEGACY_CHECKSUM_SENTINELS = {"manual_apply"}`) unconditionally skips during drift verification.
- **`CE-03` (Process-Local Olympus Safety Envelope)**: `apps/backend-rag/backend/services/olympus/safety.py:10-45` stores action rate-limit history in an in-memory Python dictionary (`self._history`), which resets on container restart and is uncoordinated across processes.
- **`CE-04` (Non-Atomic Maintenance Effect vs Audit Log)**: `apps/backend-rag/backend/services/olympus/pulse.py` and `guardian.py:32-145` execute maintenance DDL/DML and `INSERT INTO olympus_actions` as separate autocommit pool calls rather than a single atomic transaction.
- **`CE-05` (`OlympusGuardian.stop()` Swallows Cleanup)**: `apps/backend-rag/backend/services/olympus/guardian.py:72-98` sets `self._running = False` before cancelling `self._task`, and `start()` catches `asyncio.CancelledError` and only executes its `finally` cleanup block if `self._running` is still `True`.
- **`CE-06` (Hard Deletion of Terminal Outbox Rows Without Archive)**: `scripts/outbox-prune.sh:76-84` (`src_05d88b7c837c1309`) executes `DELETE FROM events_outbox WHERE status IN ('delivered', 'dead_letter', 'failed') AND created_at < now() - interval '7 days'` without archiving `dead_letter` or `failed` payloads to `events_outbox_dlq`.
- **`CE-07` (Shallow PG Restore Drill)**: `scripts/pg-restore-drill.sh:124-135` (`src_def7a4c288a552af`) verifies restored backups solely via `SELECT count(*) FROM clients`, `practices`, and `schema_migrations`, omitting `_schema_versions`, checksum integrity, and `olympus_heartbeats` partitions.
- **`CE-08` (CI Post-Deploy Migration Failure Swallowed)**: `.github/workflows/fly-deploy.yml:170-189` (`src_e98bb23501189d64`) overrides `release_command` to `""` during `flyctl deploy` and runs `python -m backend.db.migrate apply` over `flyctl ssh console` with `continue-on-error: true`.
- _(Note: `CE-09` and `IN-03` from Stage 1 ANALYSIS were refuted by `DR-B07-05.pro.out` / `DR-B07-05.out` per `B07-F1` and are excluded from active claims and proposals.)_

---

## 3. Inference (Separated from Facts)

1. **Dual-Ledger Divergence Risk (`D11`)**: Because `migrate.py` writes both `_schema_versions` and `schema_migrations`, while legacy `migration_manager.py` writes only `schema_migrations` and `migration_base.py` writes only `_schema_versions` (with forward-only SHA-256), any migration applied historically via `migration_manager.py`, `migration_base.py`, or manual `psql` required subsequent reconciliation migrations (`165`, `184`, `194`, `277`, `278`, `299`).
2. **Scheduler Host Split (`D02`)**: Combining `consumer-matrix.csv:4463` (`mini-pro2:com.nuzantara.visa-oracle-retention.15min:loaded=True` via `scripts/cron-wrapper.sh`) with `DR-B07-05.pro.out` (`0` references to `retention_worker` on Pro; `2` LaunchAgent plists referencing `outbox_prune` on Pro) indicates that `visa_engine.retention_worker` is scheduled on `Mini` while `outbox-prune.sh` is scheduled on `Pro`.

---

## 4. Unknowns & Live Blockers

1. **`LIVE_LEDGER_RECONCILIATION_BLOCKED_PENDING_BOOLEAN_PROBE_ADMISSION`**: Live row counts, per-migration checksum equality booleans (`matches_disk_full_sha256`, `matches_disk_forward_sha256`, `is_manual_apply_sentinel`), and provenance completeness (`applied_by IS NOT NULL AND applied_as IS NOT NULL`) in production `pg:fly:nuzantara-postgres/public` (`_schema_versions` and `schema_migrations`) remain `UNKNOWN` until `b07_ledger_boolean_probe.py` is reviewed by fresh Opus 5.5 and executed by the BLUE Dux (`DUX-REQ-B07-12`).
2. **`LIVE_PARTITION_STATE_PENDING_BOOLEAN_PROBE`**: The live number of attached monthly partitions (`olympus_heartbeats_yYYYYmMM`) and whether `olympus_heartbeats_default` exists on `pg:fly:nuzantara-postgres/public` remain `UNKNOWN` pending `DUX-REQ-B07-11` (`NA-1` re-run) and `DUX-REQ-B07-12`.
3. **`OPERATION_ID_PENDING_B05`**: Final canonical `operation_id` assignment (`op:<domain>:<verb>:<object>`) is owned by B05 (`CONTRACT-CONVENTIONS.md:28-31`); all B07 records carry `"UNASSIGNED_B05"` until B05 join.

---

## 5. Scoped B07 Deliverables

1. [`b07_lineage_adapter.py`](b07_lineage_adapter.py): Pure-stdlib adapter that loads `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`, `DR-B07-01.out`, and `DR-B07-05.pro.out`, validates `consumer_id` membership and `CONTRACT-CONVENTIONS.md` 19-key + `x_` structure, and implements `reconcile_migration_checksums()`.
2. [`b07_ledger_boolean_probe.py`](b07_ledger_boolean_probe.py): Standalone read-only native probe (`conn.transaction(readonly=True)`) exporting only integer migration numbers, checksum-equality booleans, and partition counts (zero actor/owner/rule strings, satisfying `B07-F3` and `DUX-CONSOLIDATION.md:42-46`).
3. [`test_b07_lineage_invariants.py`](test_b07_lineage_invariants.py): Offline deterministic pytest suite covering the negative checksum-drift case (`B07-F2`), `CONTRACT-CONVENTIONS.md` validation, `consumer-matrix.csv` membership (`X10`/`B07-F4`), Dux receipts (`B07-F1`), `CE-01..CE-08`, and probe PII-safety (`B07-F3`).

---

## DUX-REQUESTS

- **`DUX-REQ-B07-10`** (`local_pytest_verification`):
  - **Target**: `research/operations/udb-wave8/B07/test_b07_lineage_invariants.py`
  - **Command**: `PYTHONPATH=. pytest research/operations/udb-wave8/B07/test_b07_lineage_invariants.py -q`
  - **Purpose**: Execute the offline B07 invariant and negative-case pytest suite (since `run_command` is unavailable in this builder window) and record the test receipt.
- **`DUX-REQ-B07-11`** (`na1_catalog_observer_rerun`):
  - **Target**: `pg:fly:nuzantara-postgres/public` via existing read-only route
  - **Command**: Re-run the previously admitted read-only PG catalog observer `NA-1` (exporting relations, actors, triggers, functions, grants, and FKs as md5-hashed metadata, zero cleartext PII/credentials) per `DUX-CONSOLIDATION.md:38` and `DUX-NOTE-SYNTHESIS.md:48`.
  - **Purpose**: Provide fresh live catalog evidence for `_schema_versions`, `schema_migrations`, `olympus_*` partitions, and `visa_decision_retention_*` tables/functions.
- **`DUX-REQ-B07-12`** (`opus_review_and_run_boolean_ledger_probe`):
  - **Target**: `research/operations/udb-wave8/B07/b07_ledger_boolean_probe.py`
  - **Command**: After fresh Opus 5.5 source review (`DUX-CONSOLIDATION.md:42-46`), run `python3 research/operations/udb-wave8/B07/b07_ledger_boolean_probe.py` against the read-only PG route and write output to `research/operations/udb-wave8/B07/dux-requests/DR-B07-12.out`.
  - **Purpose**: Close live migration checksum reconciliation (`B07-F2`) using strictly boolean per-migration equality flags and integer counts without exporting `applied_by`, `applied_as`, role names, or rule names (`B07-F3`).

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION` for this file's bytes with SHA256 `dfad02c867268fa36fa593b994b27d8e16e2c0a25c5d73d243fa1162c63a9e5f` at candidate `f56373bc6f87cb835f05b6215a7825f165e55e21`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (addendum, removals) apply its findings and were not re-reviewed.
