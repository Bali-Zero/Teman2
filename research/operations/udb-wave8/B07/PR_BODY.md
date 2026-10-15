# [UDB Wave 8 · B07] Maintenance and Migration Lineage (`D02`, `D11`, `D13`)

## Summary

Delivers the Definitive Synthesis, canonical contract adapter, read-only boolean/hash ledger probe, and deterministic pytest invariant suite for **Block B07 — Maintenance and Migration Lineage** (`D02` Schema & Migration Lineage, `D11` Backup, Restore & Disaster Recovery, `D13` Maintenance, Vacuum, Partitioning & Retention) under campaign `universal-db-wave8-20261015`.

All cross-block adversarial findings (`X1..X13`) and B07-specific findings (`B07-F1..B07-F5`) from `DUX-CONSOLIDATION.md` are dispositioned and enforced:
- **`B07-F1` (`DR-B07-05.pro.out` reconciliation)**: Refuted and dropped Stage-1 inference `IN-03` and counterexample `CE-09`. Recorded as a verified fact from `.agent-receipts/udb-wave8-inputs/dux-requests/DR-B07-05.pro.out` that `com.nuzantara.outbox-prune` and `com.balizero.visa-retention-worker` are `NOT_LOADED` on **both** Mini and Pro, while `com.nuzantara.postgres-backup` is loaded on Pro (`0\tcom.nuzantara.postgres-backup`).
- **`B07-F2` (Negative test for checksum drift)**: Implemented `reconcile_migration_checksums()` in `b07_lineage_adapter.py` and `test_negative_checksum_drift_file_vs_ledger()` in `test_b07_lineage_invariants.py`, verifying that an edited SQL migration file whose `schema_versions.checksum` or `schema_migrations.checksum` still matches the pre-edit SHA-256 is deterministically flagged (`CHECKSUM_DRIFT_FILE_VS_LEDGER`, `FORWARD_VS_FULL_HASH_MISMATCH`, `MANUAL_APPLY_SENTINEL_BYPASS`, `DUAL_LEDGER_SPLIT_BRAIN`) and never marked `EVIDENCED`.
- **`B07-F3` (Read-only boolean/hash probe)**: Implemented `b07_ledger_boolean_probe.py` using `conn.transaction(readonly=True)` and projecting only integer migration numbers, booleans (`in_schema_versions`, `in_schema_migrations`, `ledgers_checksum_equal`, `matches_disk_full_sha256`, `matches_disk_forward_sha256`, `is_manual_apply_sentinel`, `has_provenance_populated`), and integer partition counts (zero actor strings, zero PII).
- **`B07-F4` & `X10` (Canonical `consumer_id` join)**: Replaced all ad-hoc consumer labels with verified `consumer_id` values from `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`src_e98bb23501189d64`, `src_c8f206461cd9bf69`, `src_058ad32e4ad2e6a8`, `src_697f237385fbe9eb`, `src_33d3066a868d2df3`, `src_fcca1b3652b56e72`, `src_5726ef98e1124f67`, `src_05d88b7c837c1309`, `runtime_5f57957a06e5f29c`, `src_6e1c7398dbc460bf`, `runtime_6689ea94b8c976b0`, `src_def7a4c288a552af`), guarded by `load_valid_consumer_ids()`.
- **`B07-F5` & `X1..X3` (Contract envelope & status truth)**: Enforced `CONTRACT-CONVENTIONS.md` (`store_id = "pg:fly:nuzantara-postgres/public"`, `operation_id = "UNASSIGNED_B05"`, `source_version = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"`, 19 canonical keys + `x_` extensions, status `"PARTIAL"` with `block_closed = false`).

## Scope

Strictly restricted to `research/operations/udb-wave8/B07/**`:
- `research/operations/udb-wave8/B07/ANALYSIS.md`
- `research/operations/udb-wave8/B07/PROPOSAL.md`
- `research/operations/udb-wave8/B07/DEFINITIVE-SYNTHESIS.md`
- `research/operations/udb-wave8/B07/b07_lineage_adapter.py`
- `research/operations/udb-wave8/B07/b07_ledger_boolean_probe.py`
- `research/operations/udb-wave8/B07/test_b07_lineage_invariants.py`
- `research/operations/udb-wave8/B07/RESULT.json`
- `research/operations/udb-wave8/B07/PR_BODY.md`

## Evidence Paths

- `.agent-receipts/udb-wave8-inputs/dux-requests/DR-B07-01.out` — 199 SQL `migrations_v2` files and 138 Python migrations (receipt keys), `alembic.ini` (`script_location = backend/db/migrations`, `versions_dir_absent`).
- `.agent-receipts/udb-wave8-inputs/dux-requests/DR-B07-05.pro.out` — Mini & Pro `launchctl` verification showing `com.nuzantara.outbox-prune` and `com.balizero.visa-retention-worker` are `NOT_LOADED` on both hosts, and `com.nuzantara.postgres-backup` is loaded on Pro.
- `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` — Canonical `consumer_id` registry (6,029 rows) joined by `b07_lineage_adapter.py`.
- `research/operations/udb-wave8/B07/test_b07_lineage_invariants.py` — Pytest suite verifying envelope contract, negative checksum drift (`B07-F2`), consumer-matrix membership (`B07-F4`), and `CE-01..CE-08`.

## Explicit Missing Evidence (`block_closed: false`)

1. **`UN-01` (`DUX-REQ-B07-10`)**: Live Fly PostgreSQL execution of `research/operations/udb-wave8/B07/b07_ledger_boolean_probe.py` against `nuzantara-postgres` to verify live `schema_versions` vs `schema_migrations` vs disk SHA-256 parity across all 199 SQL `migrations_v2` files.
2. **`UN-02` (`DUX-REQ-B07-11`)**: Live Fly `nuzantara-rag` runtime `ENABLE_OLYMPUS` flag and read-only numeric counts from `olympus_heartbeats`, `olympus_action_audit`, and `pg_stat_user_tables`.
3. **`UN-03` (`DUX-REQ-B07-10`)**: Live Fly PostgreSQL partition existence and child count (`pg_inherits`) for `audit_events`, `security_events`, and `olympus_metrics`.
4. **`UN-04` (`DUX-REQ-B07-12`)**: Latest restore drill receipt from `scripts/pg-restore-drill.sh` (`src_def7a4c288a552af`) and tail of `~/.nuzantara_backups/postgres/backup.log` on Pro.

Bites: `research/operations/udb-wave8/B07/test_b07_lineage_invariants.py` (and `B16` canonical ledger assembler consuming `b07_lineage_adapter.emit_b07_canonical_records()`) — running `pytest research/operations/udb-wave8/B07/test_b07_lineage_invariants.py -q` observes deterministic pass across all contract-envelope, consumer-matrix join, DR-B07-01/05 receipt, and negative checksum-drift (`CHECKSUM_DRIFT_FILE_VS_LEDGER`) invariants.
