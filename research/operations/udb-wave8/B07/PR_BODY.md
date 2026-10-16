---
adversarial_review: codex
reviewed_source_sha256: "100a4f4d1557720ce4887d5110a5fe44f38c271f3e6d8867b35e2a5c32d09e9d"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# research(udb-wave8): B07 maintenance and migration lineage — offline adapter, read-only probe with pinned observer, fixture-backed invariants

## Current package status (2026-10-16)

Current focused source suite: 16 passed. The document reconciliation withdraws unsupported legacy examples and keeps 16 concrete operation entries distinct from active-consumer coverage. The parent observed no admitted readonly observer DSN; no native DB query was performed. Source effects, identities, recovery and the active denominator remain unresolved. block_closed:false; production adoption is not claimed. Original deadline elapsed. This package is prepared for review; no final committed-head PASS is asserted.

Block **B07** (`D02`, `D11`, `D13`) of campaign `universal-db-wave8-20261015`. Status `PARTIAL`, `block_closed: false`. Authoritative evidence: [`RESULT.json`](RESULT.json).

## What ships

- `b07_lineage_adapter.py` — `load_consumer_matrix_index`, `validate_operation_instance`, `reconcile_migration_checksums`, `load_dr01_manifest`, `parse_dr05_pro_kv`, `build_b07_operation_instances`. The checksum reconciler returns `CHECKSUM_DRIFT_FILE_VS_LEDGER`, `FORWARD_VS_FULL_HASH_MISMATCH`, `MANUAL_APPLY_SENTINEL_BYPASS` or `DUAL_LEDGER_SPLIT_BRAIN` for the negative cases. Only the positive control is `EVIDENCED`.
- `b07_ledger_boolean_probe.py` — a read-only probe that has **not been executed** against any database. Before it loads the manifest, reads the environment, imports `asyncpg` or connects, it refuses any expected observer hash that is not the pinned `md5('nuzantara_readonly')`. It then requires a dedicated `B07_OBSERVER_DSN` distinct from `DATABASE_URL`, opens a read-only transaction and proves `current_user = session_user` with no privileged role attribute. Only after that does it read `_schema_versions`, `schema_migrations` and the `olympus_heartbeats` partition counts, and it emits integers, booleans and counts only.
- `test_b07_lineage_invariants.py` — 16 offline tests over committed fixtures and base-commit sources. They cover:
  - `test_negative_case_migration_file_sha256_differs_from_ledger_checksum` (four negative cases plus the positive control);
  - matrix membership for the 16 operation instances;
  - `test_dux_receipts_dr01_and_dr05_pro_invariants`;
  - `test_static_counterexample_invariants_ce01_to_ce08`;
  - the G6 observer-pin tests `test_probe_pins_the_canonical_readonly_observer_only` and `test_probe_rejects_caller_supplied_non_admitted_principal_before_connection`.
- `fixtures/` — frozen metadata, not new native observations ([`PROVENANCE.json`](fixtures/PROVENANCE.json)):
  - `dr01.json`: DR-B07-01 at `2026-10-15T08:55:00Z`, 199 SQL rows and 138 Python rows;
  - `dr05-pro.txt`: a counts-only DR-B07-05 Pro projection at `2026-10-15T08:55:09Z`, symlink target redacted;
  - `consumer-ids.csv`: the 6029 `consumer_id` values projected from the campaign consumer matrix (sha256 `c09e1432…`).
- Synthesis documents with reconciled active claims and explicitly withdrawn historical findings. `PROPOSAL.md` drops the refuted `CE-09`/`IN-03` claims and marks deferred DR-B07-02..04 NOT ADMITTED.
- Historical source-package baseline admission recorded 606 digest findings. The current curated package is covered by a separate exact per-entry admission and independent verification; no credential values are admitted.

## Contract values (embedded; the source is an external campaign control file)

`CONTRACT-CONVENTIONS.md` is an untracked campaign control copy (sha256 `a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559`) and is not in this repository. B07 uses:

| Field            | Value                                                        |
| ---------------- | ------------------------------------------------------------ |
| `store_id`       | `pg:fly:nuzantara-postgres/public`                           |
| `operation_id`   | `UNASSIGNED_B05` (only B05 mints operation ids)              |
| `source_version` | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`                   |
| status enum      | `EVIDENCED`, `PARTIAL`, `BLOCKED`, `CONFLICT`, `UNKNOWN`     |
| keys             | 8 frozen base keys + 11 instance keys; extensions under `x_` |

## Findings

- **F1 (DR-B07-05):** the Pro projection shows 0 crontab lines and 0 LaunchAgent plists referencing the retention worker, and 2 LaunchAgent plists referencing outbox-prune. These are presence counts; no launchd load or run state is claimed.
- **Static only (base `8061c88e0c`):**
  - the migration runner checksums the full UTF-8 SQL text;
  - reconcile migrations 165/184/194 carry no `manual_apply` sentinel;
  - `guardian.stop` cancels without awaiting;
  - outbox pruning deletes consumed rows only;
  - the run-migrations job has no `continue-on-error`;
  - `scripts/pg-restore-drill.sh` is absent, and its historical restore instance stays `BLOCKED`, with successor lineage `UNPROVEN`.
- **G6:** a caller-supplied observer hash is no longer accepted. The admitted identity is a source-pinned module constant, and both a non-admitted well-formed hash and the application-role hash are refused with zero connections. This is **not** native admission: no credential exists for this probe.

## Explicit missing evidence (`block_closed: false`)

1. **UN-01:** a live read-only probe run against the Fly ledgers. This needs a `B07_OBSERVER_DSN` for `nuzantara_readonly`, which is an owner credential decision.
2. **UN-02:** the live `ENABLE_OLYMPUS` value and the Olympus/pg_stat figures.
3. **UN-03:** partitions of `audit_events`, `security_events` and `olympus_metrics` are not covered by the probe.
4. **UN-04:** no restore drill receipt and no Pro backup log were read.
5. **Disclosed discrepancy:** the adapter constants `DR05_EVIDENCE_TIMESTAMP` and `DR05_STDOUT_SHA256` do not match the DR-B07-05 receipt (see `RESULT.json`).

## Historical receipt parser and TCC guard

The adapter must recognize the frozen DR05 symlink observation verbatim. Its historical path is parser input, never a filesystem access. The TCC guard therefore receives one exact-file exception under its existing historical-record policy. The guard passes with this declaration and fails on this parser alone when the entry is removed; all 16 lineage tests still pass. The adapter and frozen DR05 fixture remain byte-identical. This correction does not provide operational closure or an independent final signature.

## Adversarial review

The Codex document review was scoped, and the parent receipt is committed as [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json), observed `2026-10-15T16:54:26Z`. Its disposition is `REVIEWED_PARTIAL_WITH_BLOCKERS` for the documents at candidate `f56373bc6f87cb835f05b6215a7825f165e55e21`; this file's reviewed bytes have SHA256 `100a4f4d1557720ce4887d5110a5fe44f38c271f3e6d8867b35e2a5c32d09e9d`.

Its three findings are applied here:

- the B16 consumer and the invented function names are gone;
- the absent drill path stays historical;
- native observations stay missing.

**Limits of the review:**

- It covered bounded excerpts only, so it is not a full-document or code review, not implementation approval, and not the final BLUE gate.
- The requested seat was Astra 6/xhigh, and its effective runtime identity was not observed.
- This revision was not re-reviewed.

Bites: `research/operations/udb-wave8/B07/test_b07_lineage_invariants.py`, shipped in this PR, consumes the adapter, the probe guard and `fixtures/`. At the committed head it runs 16 passed, exit 0, and the run is recorded in the evidence pack. This includes the G6 pin refusing a non-admitted observer before any connection.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
