---
adversarial_review: codex
---

# B08 current synthesis and historical dispositions

## Historical ledger replay after B01 integration (2026-10-16)

The ledger describes base8061c88e and remains byte-identical historical evidence. Main now carries the separately verified B01 restore correction. Replay accepts only the original verifier or that one exact later revision, and the later revision additionally requires the committed, hash-verified original source snapshot. An unknown revision or missing/tampered snapshot fails closed. This compatibility does not update historical B01/B02 observations, establish current operational acceptance or repeat a native run. The original102 tests and their assertions are preserved; 6 additional compatibility checks now pass with all102 existing tests (108 total). Runtime lint passes; two unchanged legacy E731 test findings remain, with no new lint findings. The prior independent signature does not cover this source delta; a new final review is pending.

## Current boundary correction (2026-10-16)

Current source SHA256: `7a09dbe7dc2f576312c2824cfb44fb64fa996e1f5bc19118b2fc5f4f56f154ae`. Current verified suite: 102 passed in both original and clean copies, independently reproduced. Output-boundary defects were corrected and reviewed; valid artifacts remain byte-identical. All older pass counts below describe historical stages. Status remains PARTIAL with block_closed:false and all native unknowns retained.


## Current execution addendum (2026-10-16)

The candidate remains PARTIAL, with block_closed: false. The already prepared hermetic patch was applied once after exact baseline/source hash verification and git apply --check. The current source suite with admitted frozen receipts passed 37 tests with zero failures and skips. A clean copied root without .agent-receipts or dux-requests also passed 37 tests with zero failures and skips. Both CLI runs exited 0 and reproduced the historical pinned ledger byte for byte.

Current source-bound observations are in integration-20261016/CURRENT-SOURCE-TESTS.json, CURRENT-CLEAN-CHECKOUT.json, CURRENT-REGENERATION.json and CURRENT-LEDGER-CHECK.json. PATCH-INTAKE.json binds original preimages and patch provenance. All 88 original assertions, 23 pytest.raises checks, source finding IDs and six counterexamples are preserved. The stale on-disk ledger was refreshed to the pinned 77,786-byte result; its previous digest remains in the regeneration receipt.

The historical isolated 16-pass receipt and prepared worker runs retain their own scope. The original clean checkout reported 14 passed and 2 skipped; its missing-source variant reported 3 passed, 1 failed, 2 skipped and 10 errors. These are historical observations, not current candidate failures or skips. PREPARED-VERIFICATION-SUMMARY.json preserves their provenance.

The ledger contains 9 operation instances and 8 dimensions. The frozen inventory has 6029 rows plus one nested delta giving 6030 union leads; the active denominator remains UNKNOWN. B01 recovery, B02 Redis admission/observations, B03 denominator closure, B04 physical/model bindings and B05 canonical operation assignment are not inferred or newly measured. There were no native probes.

The parent must independently accept the frozen candidate, issue its official verification receipt, bind the committed head externally and obtain fresh independent review. The authenticated owner availability exception of 2026-10-16 removes the Claude seat dependency while preserving substantive acceptance. head_sha remains PENDING_DUX_COMMIT.

The historical body below is superseded wherever it conflicts with this addendum, source-bound receipts or binding campaign conventions. Historical commands, hypotheses, numbers, seat availability requirements and proposed changes are not implementation approval. Production changes await the ordered later stages; none of the four successors has started.

## Historical synthesis, superseded by the addendum

# B08 Definitive Synthesis — Cross-Store Operational Guarantees (`D12`, `D14`, `D15`, `D16`, `D17`)

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B08` — Cross-store operational guarantees (`dependencies`, `references`, `versions`, `time_semantics`, `retention_erasure_security`, `recovery_order`, `workload_cost`, `analytics_observability`)
- **Mission Colour / Gear**: `BLUE` · `GEAR 3`
- **Dux**: `claude-opus-5-5` (`xhigh`) on `Pro` (sole ship authority)
- **Block Lead Seat**: `Gemini 4 Argon (High)` — `EXTERNAL PREPARER, NO_DUX`
- **Host / Worktree**: `[Mini]` · `/Users/nuzantara/nuzantara/.worktrees/db-udb-b08-crossstore`
- **Base Commit**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (committer timestamp `2026-10-15T07:06:22Z`)
- **Block Closure State**: `PARTIAL` (`block_closed: false`)

---

## 1. Complete Adversarial & Dux Findings Dispositions (`X1..X13`, `B08-F1..B08-F5`)

Every cross-block finding (`X1..X13`) and every `B08`-specific finding (`B08-F1..B08-F5`) from `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md`, `CONTRACT-CONVENTIONS.md`, and `DUX-CONSOLIDATION.md` is accepted and enforced in code (`b08_crossstore_adapter.py`) and tests (`test_b08_crossstore_adapter.py`):

| Finding ID | Severity | Summary of Issue | Disposition | Exact Correction Applied in B08 Synthesis & Code |
| :--- | :--- | :--- | :--- | :--- |
| **`X1`** | `BLOCKER` | Incompatible `store_id` grammar (`pg:fly_prod:nuzantara_rag` vs canonical `<engine>:<platform>:<instance>[/<subcontainer>]`). | **ACCEPT** | Enforced `STORE_ID_RE` (`CONTRACT-CONVENTIONS.md:32-40`) in `b08_crossstore_adapter.py:48-77`. All B08 records use canonical IDs: `pg:fly:nuzantara-postgres/public`, `pg:mini:restore-drill/nuzantara_restore_drill`, `qdrant:pro:local/sha8-af100a6d`, `qdrant:gcloud:nuzantara-qdrant/unknown`, `redis:pro:6379/db0`, `redis:mini:6379/db0`, `sqlite:pro:mata-garuda/provenance`, `file:pro:organism/events`, `file:fly:data/llm_cost_log`, `object:gdrive:balizero_root/clients`, `external:gcloud:notebooklm/container`. Tested in `test_rejects_invalid_store_id_grammar`. |
| **`X2`** | `MAJOR` | `B08` minted `operation_id` values (`op:cross_store:...`), colliding with `B05` sole minting authority. | **ACCEPT** | Every B08 operation instance sets `"operation_id": "UNASSIGNED_B05"` and includes `"OPERATION_ID_PENDING_B05"` in `unknowns` (`CONTRACT-CONVENTIONS.md:27-30`). Enforced in `b08_crossstore_adapter.py:106-114` and tested in `test_rejects_minted_operation_id_from_b08`. |
| **`X3`** | `MAJOR` | Custom status values (`DEGRADED_LOSSY`, `BROKEN_MASKED_ZERO`, etc.) broke the 5-value enum. | **ACCEPT** | Top-level and field-level `status` are strictly constrained to `EVIDENCED \| PARTIAL \| BLOCKED \| CONFLICT \| UNKNOWN` (`CONTRACT-CONVENTIONS.md:49-51`). B08-specific metadata lives exclusively in `x_`-prefixed fields (`x_guarantee_dimension`, `x_record_kind`, `x_counterexample_id`, `x_target_store_ids`, `x_evidence_ref`). Tested in `test_rejects_custom_status_outside_enum`. |
| **`X4`** | `BLOCKER` | Competing 12-field schema in `B08` vs `B05`'s 19-key operation instance validator (`8` frozen + `11` instance object fields). | **ACCEPT** | Dropped the standalone 12-field schema. Every B08 operation instance carries the exact 19 keys (`8` frozen + `11` instance keys formatted as `{"value": ..., "status": ..., "evidence_ref": ...}`) plus `x_`-prefixed extension keys (`CONTRACT-CONVENTIONS.md:8-25`, `DUX-CONSOLIDATION.md:20-21`). Tested in `test_all_emitted_operation_instances_satisfy_19_key_contract` and `test_rejects_unprefixed_extra_keys_and_flat_instance_fields`. |
| **`X5`** | `MAJOR` | Inconsistent `source_version` and `evidence_timestamp` rules across blocks. | **ACCEPT** | Static repository evidence uses `source_version = "8061c88e0c43dd42e735fd012f9ed072df3ef3d6"`, `evidence_timestamp = "2026-10-15T07:06:22Z"`, and `"STATIC_SOURCE_ONLY"` in `unknowns` (`CONTRACT-CONVENTIONS.md:41-46`). `STATE.json` evidence uses `"2026-10-15T03:28:29.868658+00:00"`, and `REAL-RUN-RECEIPT.json` uses `"2026-10-15T03:02:11+00:00"`. Tested in `test_rejects_static_source_without_unknown_marker`. |
| **`X6`** | `MAJOR` | Over-claiming which `clients` subcheck failed (`VIOLATION: 1`) or the exact SQL error behind `conversations` `UNMEASURED_CHECK: 1`. | **ACCEPT** | Strictly separated in §2.1/§2.3 and `evaluate_ce01_restore_verdict_and_epistemology` (`b08_crossstore_adapter.py:217-253`): Fact = `_VIOLATIONS_SQL["clients"]` executed (`MISSING_COLUMN: 0`), proving `lead_metadata` existed on `clients` in that backup (`FINAL-BLUE-GATE.json:117`), and returned `1` reason of class `VIOLATION`; Unknown = whether one or both `clients` subchecks (`client_type_unknown`, `lead_metadata_not_object`) were non-zero (`REPORT.md:124-127`) and the exact SQL error on `conversations`. Tested in `test_ce01_restore_precedence_and_subcheck_epistemology`. |
| **`X7`** | `BLOCKER` | `B08` `P-AUTH-01` proposed reading `REDIS_PASSWORD` to authenticate `redis-cli` and writing into `.agent-receipts/udb-wave8-inputs/`. | **ACCEPT** | **Completely deleted `P-AUTH-01`**. B08 never reads or uses `REDIS_PASSWORD`, `REDIS_URL`, `QDRANT_API_KEY`, or admin/app secrets, and never writes outside `research/operations/udb-wave8/B08/`. Redis observer admission is deferred 100% to `B02`'s keyless `nuzantara_observer` consent proposal (`DUX-CONSOLIDATION.md:54`). |
| **`X8`** | `MAJOR` | Misattributed sibling block numbers (`B01..B07`) and unpinned transitive closure dependencies. | **ACCEPT** | Corrected the sibling ownership map in §4 to match actual `BATTLE.md` scopes (`B01` recovery, `B02` Redis observer, `B03` denominator, `B04` physical stores, `B05` operation contracts, `B06` business domains `D04..D10`, `B07` maintenance/migrations `D02/D11/D13`). Added `validate_sibling_gate_constraints` (`b08_crossstore_adapter.py:168-214`) to block `EVIDENCED` or `block_closed=True` while `B01`, `B02`, `B03`, or `B04` are unclosed. |
| **`X9`** | `MAJOR` | Unfreeze / circular dependency risk across blocks during synthesis. | **ACCEPT** | Consumed only pinned `.agent-receipts/udb-wave8-inputs/`, `.agent-receipts/udb-wave8-dux/`, `.agent-receipts/udb-wave8-siblings/`, and `research/operations/udb-wave8/B08/dux-requests/`. Unclosed sibling dependencies are recorded as explicit `unknowns` tokens (`DUX-CONSOLIDATION.md:22`). |
| **`X10`** | `MAJOR` | Misquoted `consumer-matrix.csv` column names (`source_file`, `line_number`, `symbol`, `store_family`), `STATE.json` line numbers, and restore row numbers. | **ACCEPT** | Re-derived all citations from real files and `DUX-REQ-B08-01..02.out`: `consumer-matrix.csv` has `36` exact columns and `6029` data rows (lines `2..6030`); the `6030`th lead (`mini.restore_drill`) is in `LEAD-DELTA.json`; real restore rows are CSV lines `25`, `3280`, `3727`, `4046`, `4047`. |
| **`X11`** | `MAJOR` | Ad-hoc native exercise definitions outside Dux receipt schema. | **ACCEPT** | Requested only deterministic Python/pytest commands via `## DUX-REQUESTS` (`DUX-REQ-B08-10..12`), logged by Dux in `research/operations/udb-wave8/B08/dux-requests/RECEIPTS.json`. |
| **`X12`** | `MINOR` | Write-boundary discipline across `research/operations/udb-wave8/B0N/`, `scripts/ci/`, and `.agent-receipts/`. | **ACCEPT** | All B08 deliverables reside strictly inside `research/operations/udb-wave8/B08/`. CLI enforces path containment (`b08_crossstore_adapter.py:846-851`), tested in `test_cli_refuses_output_outside_b08_directory`. |
| **`X13`** | `MINOR` | `RESULT.json` `head_sha` and `tests` provenance before Dux commit/execution. | **ACCEPT** | `RESULT.json` sets `"head_sha": "PENDING_DUX_COMMIT"` and `"result": "PENDING_DUX_EXECUTION"` on all requested test/generator commands (`DUX-CONSOLIDATION.md:27`). |
| **`B08-F1`** | `BLOCKER` | `P-AUTH-01` used `REDIS_PASSWORD` and proposed writing `.agent-receipts/udb-wave8-inputs/REDIS-OBSERVATION-RECEIPT.json`. | **ACCEPT** | Deleted `P-AUTH-01` and all writes outside `research/operations/udb-wave8/B08/`. Enforced output path guard in `b08_crossstore_adapter.py:846-851`. |
| **`B08-F2`** | `MAJOR` | `P-AUTH-02 Step 1` assumed `verify.json` persists on Mini after `run_drill.sh` (which deletes `$WORK_DIR` on exit via `trap cleanup EXIT` at `run_drill.sh:66-76`) and `DUX-REQ-B08-04` was rejected (`NOT_ADMITTED_BOUNDARY`). | **ACCEPT** | Deleted `P-AUTH-02 Step 1`. B08 respects the Mini raw-reason boundary (`RECEIPTS.json:68-73`) and defers restore drill re-execution and sanitized subcheck counter admission to `B01`'s `RESTORE-ADMISSION-PROPOSAL.md` (`DUX-CONSOLIDATION.md:55-56`). |
| **`B08-F3`** | `MAJOR` | Wrong sibling block mapping in `B08/PROPOSAL.md §3.2`. | **ACCEPT** | Replaced with the verified Wave 8 sibling map (`B01` recovery, `B02` Redis, `B03` denominator, `B04` physical stores, `B05` operation contracts, `B06` business domains `D04..D10`, `B07` maintenance/migrations `D02/D11/D13`) in §4 below. |
| **`B08-F4`** | `MAJOR` | Fabricated CSV column names (`source_file`, `line_number`, `symbol`, `store_family`), wrong restore row numbers (`2948, 2962, 5762, 5919`), and wrong `STATE.json` line citations. | **ACCEPT** | Corrected in §2.1 below and in `b08_crossstore_adapter.py` using `DUX-REQ-B08-01.out` and `DUX-REQ-B08-02.out`. |
| **`B08-F5`** | `MINOR` | Proposed `scripts/ci/verify_crossstore_guarantees.py` and `tests/ci/test_verify_crossstore_guarantees.py` outside B08 write scope. | **ACCEPT** | Relocated implementation and pytest suite to `research/operations/udb-wave8/B08/b08_crossstore_adapter.py` and `research/operations/udb-wave8/B08/test_b08_crossstore_adapter.py` (`DUX-NOTE-SYNTHESIS.md:20-23`). |

---

## 2. Epistemological Ledger: Facts, Inferences, and Unknowns

### 2.1 Verified Facts (Pinned Inputs & Repository Evidence Only)

1. **Wave 8 Baseline Census & Denominator State** (`.agent-receipts/udb-wave8-inputs/STATE.json:8-12`, sha256 `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4`):
   - `baseline_leads_preserved`: `6029` (`STATE.json:8`)
   - `additional_runtime_observations`: `1` (`STATE.json:9`)
   - `union_lead_rows`: `6030` (`STATE.json:10`)
   - `active_consumer_denominator`: `"UNKNOWN"` (`STATE.json:11`)
   - `complete_operation_contracts`: `0` (`STATE.json:12`)
   - The `6029` static/runtime leads reside in `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`1` header line + `6029` data rows at lines `2..6030`, sha256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`), while the `6030`th lead (`mini.restore_drill`) is recorded in `LEAD-DELTA.json` (`REPORT.md:94-97`).

2. **Exact `consumer-matrix.csv` Schema & Multi-Store Distribution** (`research/operations/udb-wave8/B08/dux-requests/DUX-REQ-B08-01.out`, ran at `2026-10-15T09:57:12.805733+00:00`, stdout sha256 `74d784664ffca2b9b268738641880b9adc0d56e128319e80b61cad9048cbfaf2`):
   - `consumer-matrix.csv` contains **36 columns**: `consumer_id, domain, entry_point, evidence, runtime_registration, operations, store, schemas_tables_keys, owner, authority, identity_relationships, transaction_boundary, authorization, locality_sensitivity, retention, concurrency_idempotency, latency_availability, test_coverage, disposition, blocker, domain_hint, domain_classification, store_signal_hint, persistence_client_hints, activation_status, production_execution_evidence, contract_coverage_status, phase_source_path_evidence, phase_factory_candidate_count, phase_source_scope_status, phase_registered_ingress_evidence, phase_registered_source_route_candidates, phase_registered_source_scope, phase_ci_registration_evidence, phase_ci_reported_states, phase_ci_actor_identity`.
   - Out of `6,029` CSV rows, **`1,803` rows** match multi-store (`;` in `store`) or cross-boundary (`event_delivery`, `qdrant`, `redis`, `file_state`, `object_storage`) store classifications.
   - Breakdown by `consumer_id` prefix family across those `1,803` rows: `src`: `1,572`, `runtime`: `158`, `NOTEBOOK-CONTAINER-REFERENCE-NLM`: `67`, `engine_pro`: `2`, `engine_mini`: `2`, `runtime-pro-plist`: `1`, `engine_M5`: `1`.
   - Top multi-store/boundary `store` combinations: `http_indirect;postgresql` (`446`), `file_state;sqlite` (`115`), `UNKNOWN;not proof of statelessness` (`112`), `file_state;postgresql` (`77`), `file_state;http_indirect` (`76`), `NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY` (`67`), `file_state;http_indirect;postgresql` (`58`), `postgresql;qdrant` (`43`), `postgresql;redis` (`41`), `http_indirect;qdrant` (`40`), `file_state;qdrant` (`39`), `event_delivery;postgresql` (`38`), `graph;postgresql` (`37`), `event_delivery` (`36`), `postgresql;sql_dialect_unknown` (`34`), `file_state;redis` (`31`), `graph;http_indirect;postgresql` (`30`), `object_storage` (`28`), `event_delivery;redis` (`23`), `redis;sqlite` (`22`), `postgresql;qdrant;redis` (`21`).

3. **Verified Restore-Drill Consumer Rows & Real-Backup Observation** (`DUX-REQ-B08-02.out`, stdout sha256 `e3ce0173f333b159ee1d706f35b061f8d81c9cd52fc9b93807b98ff54cc5cc69`; `STATE.json:41,80-130`; `REAL-RUN-RECEIPT.json:1-43`, sha256 `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d`):
   - The 5 restore-drill rows in `consumer-matrix.csv` are:
     - `src_307bea3dfb94ec31` (`data_row: 24`, `csv_line: 25`, `.github/workflows/restore-drill.yml`, `store: "object_storage;postgresql"`, `schemas_tables_keys: "clients"`)
     - `src_d073f505ff1671ad` (`data_row: 3279`, `csv_line: 3280`, `scripts/ci/restore_drill_verify.py`, `store: "event_delivery;postgresql"`, `schemas_tables_keys: "clients;conversations;events_outbox;visa_decision_retention_policies;visa_decisions"`)
     - `src_def7a4c288a552af` (`data_row: 3726`, `csv_line: 3727`, `scripts/pg-restore-drill.sh`, `store: "object_storage;postgresql"`, `schemas_tables_keys: "clients;practices"`)
     - `src_cdf3ae5e4ecf861c` (`data_row: 4045`, `csv_line: 4046`, `scripts/tests/test_restore_drill_verify.py`, `disposition: "RETAINED_TEST_SOURCE"`)
     - `src_2f350566b97aee80` (`data_row: 4046`, `csv_line: 4047`, `scripts/tests/test_restore_drill_workflow_wiring.py`, `disposition: "RETAINED_TEST_SOURCE"`)
   - In `REAL-RUN-RECEIPT.json:19-42` (`timestamp_utc: "2026-10-15T03:02:11+00:00"`, `backup_file: "nuzantara_20261015_030000.sql.gz"`, `overall_status: "CANNOT-VERIFY"`):
     - `table_statuses`: `clients: "FAIL"`, `conversations: "CANNOT-VERIFY"`, `events_outbox: "PASS"`, `visa_decision_retention_policies: "PASS"`, `visa_decisions: "PASS"`.
     - `reason_counts`: `{"MISSING_COLUMN": 0, "MISSING_TABLE": 0, "NULL_IDENTITY": 0, "ORPHAN_FK": 0, "PARSE_ANOMALY": 0, "ROW_COUNT_BELOW_FLOOR": 0, "UNMEASURED_CHECK": 1, "VIOLATION": 1}`.
   - Per `FINAL-BLUE-GATE.json:117` and `scripts/ci/restore_drill_verify.py:85-100,200-220`, `_VIOLATIONS_SQL["clients"]` only executes after required column presence (`id`, `lead_metadata`) succeeds (`MISSING_COLUMN: 0`). Therefore, `lead_metadata` existed on `clients` in that restored backup, and `_VIOLATIONS_SQL["clients"]` returned at least one violation (`VIOLATION: 1`).
   - Per `scripts/restore_drill/run_drill.sh:66-76`, `trap cleanup EXIT` executes `rm -rf "$WORK_DIR"`, deleting `$WORK_DIR/verify.json` on container teardown.

4. **Six Code-Verified Cross-Store Counterexamples (`CE-01`..`CE-06`)** (with SHA256 hashes from `DUX-REQ-B08-03.out`, stdout sha256 `dfe2256fd1c51cbbfb1276faa6dd27342209760b5ecbaf2b80e0112551c5df68`):
   - **`CE-01` (Restore Verdict Precedence & Single-Store Scope)**: `scripts/ci/restore_drill_verify.py:43-50,451-457` (sha256 `3fe0dfc48e5f4e3e2000b0813b59d60a8500503f68c89596e4b09a0b91dad856`) verifies only 5 PostgreSQL tables (`clients`, `conversations`, `visa_decisions`, `visa_decision_retention_policies`, `events_outbox`) and computes overall status with `CANNOT-VERIFY > FAIL > PASS` precedence (`restore_drill_verify.py:451-457`), causing `conversations: CANNOT-VERIFY` to mask `clients: FAIL` in the top-level scalar `overall_status`.
   - **`CE-02` (Polymorphic Cross-Store References Without FK or Single Authority)**: `apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:26-30,44-73` (`src_54ed3c033ab03a89`, sha256 `62e437d7de7c60300330d01ea4d2ff7957fc4b309016d229a3bd8051635eb01e`) defines `asset_provenance` with `asset_kind TEXT NOT NULL` (`12` domain kinds where `8/12` lack PG target tables, including Qdrant `intel_finding`/`kg_entity` and external `crm_enrichment_lookup`) and unconstrained `asset_id TEXT NOT NULL` with zero database-level foreign keys, while `sqlite:pro:mata-garuda/provenance` (`provenance.db`) remains active in parallel.
   - **`CE-03` (Lossy PG -> JSONL -> Redis Organism Fan-Out & Wall-Clock Correlation IDs)**: `scripts/pg-to-organism-bridge.py:138-222` (`src_a725ee3bebe31d76`, sha256 `96226534ea52ff70418dbdc040680efa70f546dfbf8bbdd51b030d0ae3420333`) truncates serialized payloads exceeding `2000` bytes (`_truncate_payload` at lines `138-153`), falls back to a non-deterministic wall-clock timestamp `f"pg-{channel}-{datetime.now(timezone.utc).timestamp()}"` when `_outbox_id` and `correlation_id` are absent (`lines 172-176`), and treats `redis-cli XADD organism:events` failures (`NOAUTH`, `WRONGPASS`, `ERR`, nonzero exit) as non-fatal warnings (`lines 215-222`) after appending to `~/.organism/events/pg-bridge.jsonl`.
   - **`CE-04` (Zero-I/O Qdrant Health Check False Positive)**: `apps/backend-rag/backend/services/monitoring/unified_health_service.py:129-156` (sha256 `d74572f5e8dfa7aec4cbe63d6854541a2037248f889d54bd14838933fc38a65b`) instantiates `QdrantClient(qdrant_url=settings.qdrant_url, collection_name="visa_oracle")` (which sets attributes in `__init__` without network I/O per `apps/backend-rag/backend/core/qdrant_db.py:55-90`, sha256 `5b67c71400cbb38154f32c7f85ddf6b1fa8ec24e5d54c4c05de84fa4ceac400e`) and immediately returns `status="ok"` and registers `ServiceStatus.HEALTHY` if `client.qdrant_url and client.collection_name` are truthy, performing zero network or collection existence checks.
   - **`CE-05` (Missing Table `42P01` Masked as `$0.00` Spend)**: `apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:82-89` (`src_af8a65192e15e595`, sha256 `910eba9f6b8002d6cc915c6abf1f6d6e42360b362e3d085d2928c0d49e587d05`) catches PostgreSQL error code `"42P01"` (`undefined_table` on `war_room_costs` / `war_room_drafts`) and returns HTTP `200` with `{ days, limit, rows: [], grand_total_usd: 0 }`.
   - **`CE-06` (Outbox 60-Minute Unconsumed Orphan Stratum & Unimplemented 90-Day JSONL Cost Pruning)**:
     - `apps/backend-rag/backend/services/events/outbox.py:283,332-335` (`src_e23395130cffca55`, sha256 `fdf8f48cadf3fdd72b9393dc27ac385b9be489772c6931f7a9e453fb0f413269`) restricts `replay_unconsumed` to `WHERE consumed_at IS NULL AND created_at > NOW() - INTERVAL '60 minutes'`, while `prune_consumed` (`outbox.py:422-448`, invoked daily by `scripts/outbox-prune.sh:72-88`, `src_05d88b7c837c1309`, sha256 `316314201094a5660418b493596be6a7d7451463bbcf0284b4e17d77e47a49dd`) deletes only `WHERE consumed_at IS NOT NULL AND consumed_at < NOW() - INTERVAL '30 days'`. Any row remaining `consumed_at IS NULL` after 60 minutes is never replayed by `replay_unconsumed` and never pruned by `outbox-prune.sh`.
     - `apps/backend-rag/backend/services/observability/llm_cost_recorder.py:58-60,109-112` (`src_787bbadb9e6dca52`, sha256 `14bab578510a94609a94c0bdfb2c952a04efe2654c26b3485c23234a721f21cd`) defines `DEFAULT_RETENTION_DAYS = 90` and assigns `self.retention_days = retention_days` in `__init__`, but `self.retention_days` is never read anywhere in the module; rotated `/data/llm_cost_log.YYYY-MM-DD.jsonl` files are never pruned, and parallel writes to PG `llm_cost_events` and JSONL (`lines 255-285`) have no backfill or reconciliation on single-sink failure.

### 2.2 Bounded Inferences (Labeled & Separated from Facts)

- **[INFERENCE-1]**: Because `pg-to-organism-bridge.py` (`src_a725ee3bebe31d76`) listens via ephemeral `LISTEN/NOTIFY` and does not call `outbox.replay_unconsumed` inside `_run_listener` (`pg-to-organism-bridge.py:238-260`), any notification emitted while the bridge is reconnecting or while local Redis returns `NOAUTH`/`ERR` produces permanent divergence between PG `events_outbox`, `~/.organism/events/pg-bridge.jsonl`, and Redis `organism:events`.
- **[INFERENCE-2]**: Because `check_qdrant` in `unified_health_service.py:129-156` checks only Python attribute truthiness on a newly constructed `QdrantClient` instance, health telemetry cannot detect Qdrant Cloud outages, collection deletions, or embedding dimension mismatches (`1536` dims).

### 2.3 Explicit Unknowns & Unclosed Sibling Blockers

- **`CLIENTS_FAILING_SUBCHECK_UNDISAMBIGUATED` & `CONVERSATIONS_UNMEASURED_SQL_CAUSE_UNKNOWN`** (`Finding X6`, `B08-F2`): Sanitized `REAL-RUN-RECEIPT.json` records `VIOLATION: 1` on `clients` and `UNMEASURED_CHECK: 1` on `conversations`. Which of the two `clients` subchecks (`client_type_unknown` vs `lead_metadata_not_object`) was non-zero, whether both were non-zero, and what SQL error triggered `UNMEASURED_CHECK: 1` on `conversations` are **UNKNOWN** from pinned artifacts and stay on Mini until `B01`'s `RESTORE-ADMISSION-PROPOSAL.md` is approved and executed.
- **`B01_RECOVERY_EVIDENCE_MISSING`**: `real_backup_restore_success_proved` is `false` (`STATE.json:41`).
- **`B02_REDIS_OBSERVER_EVIDENCE_MISSING`**: `redis.pro` and `redis.mini` are both `"AUTHORIZATION_REQUIRED"` (`STATE.json:44-47`), awaiting `B02`'s keyless `nuzantara_observer` admission.
- **`B03_DENOMINATOR_UNCLOSED`**: `active_consumer_denominator` is `"UNKNOWN"` (`STATE.json:11`).
- **`B04_QDRANT_PROD_METADATA_MISSING`**: `qdrant_model_binding_proved` is `false` (`STATE.json:43`), and live production Qdrant collection/vector/payload metadata is unverified in Wave 8 baseline inputs.
- **`OPERATION_ID_PENDING_B05`**: Canonical `operation_id` assignment (`op:<domain>:<verb>:<object>`) is owned by `B05`.

---

## 3. Current Observed Facts vs. Desired Target Guarantees Across All 8 Dimensions

Per `DUX-NOTE-SYNTHESIS.md:19`, current repository/runtime facts (`x_record_kind: "CURRENT_FACT"`) and desired operational guarantees (`x_record_kind: "DESIRED_GUARANTEE"`) are strictly separated across all 8 dimensions:

| Dimension (`x_guarantee_dimension`) | Research Lines | Current Observed Fact (`CURRENT_FACT`) | Current Status | Desired Target Guarantee (`DESIRED_GUARANTEE`) | Blocking Siblings |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. `dependencies`** | `D12` | `1,803` of `6,029` CSV rows span multi-store or cross-boundary surfaces (`DUX-REQ-B08-01.out`). `outbox.py` (`src_e23395130cffca55`) writes PG `events_outbox` + `pg_notify` atomically (`lines 210-228`), but downstream consumers (`pg-to-organism-bridge.py`, webhook/Redis relays) execute outside the PG transaction without end-to-end delivery acks. | `PARTIAL` | Every cross-store fan-out edge (`PG -> Redis`, `PG -> Qdrant`, `PG -> JSONL`) declares an explicit transaction boundary, downstream idempotency key (`_outbox_id`), and dead-letter/orphan sweep covering all unconsumed ages. | `B02`, `B03`, `B05` |
| **2. `references`** | `D14` | `154_asset_provenance.sql` (`src_54ed3c033ab03a89`, `lines 26-73`) uses single-table polymorphic `asset_kind` + unconstrained `asset_id TEXT` across 12 kinds where `8/12` lack PG target tables; `sqlite:pro:mata-garuda/provenance` (`provenance.db`) coexists as split authority; `67` `NOTEBOOK-CONTAINER-REFERENCE-NLM` rows reference external NotebookLM containers. | `CONFLICT` | Every cross-store pointer (`asset_provenance`, Qdrant `point_id`/`source_id`, GDrive file IDs) has a single declared store of authority and automated dangling-pointer verification. | `B04`, `B06`, `B07` |
| **3. `versions`** | `D14` | `299_schema_versions_provenance.sql` (`src_da55e7bec3535c6e`) and `165_reconcile_schema_migrations_duplicates.sql` reconcile PG migration tracking, but `STATE.json:42-43` shows local Pro Qdrant has only `2` collections (`af100a6d`) and `qdrant_model_binding_proved: false`. Restore drill failed against backup `nuzantara_20261015_030000.sql.gz`. | `BLOCKED` | PG `_schema_versions` / `schema_migrations` match backup dump invariants, and Qdrant collections prove `text-embedding-3-small` (`1536`-dim) version binding across environments. | `B01`, `B04`, `B07` |
| **4. `time_semantics`** | `D15` | `pg-to-organism-bridge.py` (`src_a725ee3bebe31d76`, `lines 138-222`) truncates payloads `>2000` bytes, mints wall-clock `correlation_id` (`pg-{channel}-{ts}`) when `_outbox_id` is absent (`line 175`), and logs `redis-cli XADD` errors as non-fatal (`lines 215-222`). | `CONFLICT` | Cross-store event propagation preserves producer `event_id`/`_outbox_id` and UTC emission timestamp without wall-clock correlation fallback or silent payload truncation. | `B02`, `B05` |
| **5. `retention_erasure_security`** | `D16` | `outbox-prune.sh` (`src_05d88b7c837c1309`) calls `prune_consumed(older_than_days=30)` (`WHERE consumed_at IS NOT NULL`), while `replay_unconsumed` (`outbox.py:334`) ignores `consumed_at IS NULL` rows older than `60` minutes, creating an unpruned orphan gap. `264_visa_decision_retention_policy.sql` defines PG retention metadata without proved Qdrant/GDrive erasure cascade. | `CONFLICT` | Retention and UU PDP erasure policies cascade deterministically across PG, Qdrant vectors, Redis streams/keys, and local JSONL logs with zero unpruned orphan stratum. | `B01`, `B02`, `B04`, `B06` |
| **6. `recovery_order`** | `D16`, `D17` | `restore_drill_verify.py` (`src_d073f505ff1671ad`, `lines 43-50,451-457`) verifies 5 PG tables only; `REAL-RUN-RECEIPT.json` recorded `clients: FAIL` (`VIOLATION: 1`), `conversations: CANNOT-VERIFY` (`UNMEASURED_CHECK: 1`), and overall `CANNOT-VERIFY` (masking `FAIL`). Qdrant, Redis, SQLite, and GDrive have no coordinated recovery drill. | `BLOCKED` | Restore drill proves `PASS` across all required PG tables with disaggregated per-subcheck counters (`B01`), never masks `FAIL` behind `CANNOT-VERIFY`, and enforces recovery order: `1. PG base + _schema_versions -> 2. SQLite/GDrive provenance -> 3. Qdrant parity -> 4. Redis watermark -> 5. Outbox replay`. | `B01`, `B02`, `B04` |
| **7. `workload_cost`** | `D16` | `llm_cost_recorder.py` (`src_787bbadb9e6dca52`, `lines 58-60,109-112,239-298`) writes in parallel to Prometheus, PG `llm_cost_events`, and `/data/llm_cost_log.YYYY-MM-DD.jsonl` without reconciliation on single-sink failure, and never references `self.retention_days` (`90` days) to prune old JSONL files. | `CONFLICT` | Cost ledger sinks (`llm_cost_events` and `/data/llm_cost_log.*.jsonl`) reconcile row counts via request correlation IDs and enforce the declared 90-day local JSONL retention window. | `B04`, `B07` |
| **8. `analytics_observability`** | `D17` | `unified_health_service.py:129-156` (`check_qdrant`) returns `status="ok"` on attribute truthiness with zero network I/O (`CE-04`). `war-room/metrics/costs/route.ts:84-89` (`src_af8a65192e15e595`) catches SQL `42P01` (`undefined_table`) and returns HTTP `200` with `grand_total_usd: 0` (`CE-05`). | `CONFLICT` | Health and cost endpoints perform real read/ping probes and surface `DEGRADED`/`ERROR` instead of masking missing tables (`42P01`) as `$0.00` or unprobed clients as `ok`. | `B02`, `B04` |

---

## 4. Sibling Block Ownership & Transitive Closure Wiring (`B01..B07`)

Per `ADVERSARY-FINDINGS.md` (`X8`, `B08-F3`) and `DUX-CONSOLIDATION.md:20-22`, `B08` maps its upstream and downstream interfaces to the exact Wave 8 sibling blocks:

| Sibling Block | Canonical Wave 8 Scope | Relationship to `B08` Cross-Store Operational Guarantees | Current Closure Dependency |
| :--- | :--- | :--- | :--- |
| **`B01`** | Real-backup recovery (`mini.restore_drill`) | Supplies the sanitized per-subcheck diagnostic admission (`RESTORE-ADMISSION-PROPOSAL.md`) and real-backup restore proof on `Mini` (`pg:mini:restore-drill/nuzantara_restore_drill`). | `BLOCKED` (`real_backup_restore_success_proved: false` in `STATE.json:41`) |
| **`B02`** | Redis observer admission (`Pro` & `Mini`) | Supplies the keyless `nuzantara_observer` ACL admission for `redis:pro:6379/db0` and `redis:mini:6379/db0`. `B08` deleted `P-AUTH-01` and relies exclusively on `B02`. | `BLOCKED` (`redis.pro/mini: AUTHORIZATION_REQUIRED` in `STATE.json:44-47`) |
| **`B03`** | Active-consumer denominator (`D00`, `6,030` union leads) | Reconciles `6,029` `consumer-matrix.csv` leads + `1` `LEAD-DELTA.json` lead (`mini.restore_drill`) and resolves `active_consumer_denominator`. | `BLOCKED` (`active_consumer_denominator: "UNKNOWN"` in `STATE.json:11`) |
| **`B04`** | Physical stores & connections (`D01`) | Authoritative owner of `store_id` inventory across PG, Qdrant (`qdrant_model_binding_proved`), Redis, SQLite, and GDrive. | `BLOCKED` (`qdrant_model_binding_proved: false` in `STATE.json:43`) |
| **`B05`** | Effective operation contracts (`D03`) | Sole minting authority for `operation_id` (`op:<domain>:<verb>:<object>`) and owner of the 19-key operation instance validator. `B08` emits 19-key + `x_`-prefixed instances with `operation_id: "UNASSIGNED_B05"` for `B05` validation. | `PARTIAL` (`complete_operation_contracts: 0` in `STATE.json:12`) |
| **`B06`** | Business-domain paths (`D04`–`D10`) | Supplies domain-level data paths (CRM `clients`, `conversations`, `visa_decisions`, Mata Garuda / War Room provenance, KBLI/RAG) whose cross-store edges `B08` evaluates. | `PARTIAL` (static/schema evidence available; runtime closure gated on `B01`/`B03`/`B04`) |
| **`B07`** | Maintenance & migration lineage (`D02`, `D11`, `D13`) | Supplies migration ledger reconciliation (`schema_migrations` vs `_schema_versions`), cron/launchd maintenance inventory (`outbox-prune.sh`, `pg-to-organism-bridge.py`), and `provenance.db` -> PG cutover lineage. | `PARTIAL` (static lineage evidenced; live parity gated on `B01`/`B04`) |

---

## 5. Definitive Design of B08 Deliverables

All B08 code, tests, and generated artifacts live strictly inside `research/operations/udb-wave8/B08/`:

1. **`research/operations/udb-wave8/B08/b08_crossstore_adapter.py`**:
   - Pure Python 3.11+ standard-library module (`argparse`, `csv`, `hashlib`, `json`, `pathlib`, `re`, `typing`).
   - Enforces `CONTRACT-CONVENTIONS.md` via:
     - `validate_store_id(store_id, unknowns)`: regex enforcement of `<engine>:<platform>:<instance>[/<subcontainer>]` and `STORE_ID_PROPOSED:<value>` when `unknown:unknown:unknown` is used (`X1`).
     - `validate_operation_instance(record, known_consumer_ids)`: enforces the 19 required keys (`8` frozen + `11` instance dicts `{value, status, evidence_ref}`), rejects non-`x_` extra keys (`X4`), enforces `operation_id == "UNASSIGNED_B05"` + `"OPERATION_ID_PENDING_B05"` (`X2`), enforces the 5-value `status` enum (`X3`), enforces `STATIC_SOURCE_ONLY` on base-commit static evidence (`X5`), verifies `consumer_id` membership in `consumer-matrix.csv` + `mini.restore_drill` (`X10`), and prohibits `DESIRED_GUARANTEE` records from claiming `status == "EVIDENCED"`.
     - `validate_sibling_gate_constraints(records, state_json, block_closed)`: fail-closed guard that raises `ContractViolationError` if `block_closed=True` or if any `recovery_order`, `redis:*`, or `qdrant:*` record claims `status == "EVIDENCED"` while `STATE.json` shows `real_backup_restore_success_proved=False`, `redis.pro/mini="AUTHORIZATION_REQUIRED"`, or `qdrant_model_binding_proved=False` (`X8`, `B08-F3`).
   - Evaluates `CE-01`..`CE-06` directly against pinned repository files and `REAL-RUN-RECEIPT.json` (`evaluate_ce01_restore_verdict_and_epistemology` through `evaluate_ce06_outbox_and_cost_retention`).
   - CLI entry point writes `research/operations/udb-wave8/B08/b08_crossstore_ledger.json` and refuses any output path outside `research/operations/udb-wave8/B08/` (`B08-F1`, `B08-F5`).

2. **`research/operations/udb-wave8/B08/test_b08_crossstore_adapter.py`**:
   - Self-contained `pytest` suite (`12` test functions covering positive generation and negative/guilt tests for `X1`, `X2`, `X3`, `X4`, `X5`, `X6`, `X8`/`B08-F3`, `X10`/`B08-F4`, `B08-F1`/`B08-F5`, and `CE-01`..`CE-06`).

3. **`research/operations/udb-wave8/B08/b08_crossstore_ledger.json`**:
   - Deterministic JSON artifact containing `census_summary`, `missing_sibling_evidence`, `dimensions` (all 8 dimensions split into `current_facts` and `desired_guarantees`), `operation_instances` (9 validated 19-key + `x_` records), and `counterexamples` (`CE-01`..`CE-06`).

---

## DUX-REQUESTS

Per `DUX-NOTE-SYNTHESIS.md:29-33` and `DUX-CONSOLIDATION.md:27`, B08 requests the BLUE Dux on `Pro` to execute the following read-only/bounded verification commands and log their outputs in `research/operations/udb-wave8/B08/dux-requests/RECEIPTS.json`:

- **`DUX-REQ-B08-10`** (Generate deterministic B08 cross-store ledger from pinned inputs):
  ```bash
  python3 research/operations/udb-wave8/B08/b08_crossstore_adapter.py --repo-root . --out research/operations/udb-wave8/B08/b08_crossstore_ledger.json
  ```
- **`DUX-REQ-B08-11`** (Run B08 pytest suite covering positive + negative/guilt checks across all 8 dimensions):
  ```bash
  pytest -q research/operations/udb-wave8/B08/test_b08_crossstore_adapter.py
  ```
- **`DUX-REQ-B08-12`** (Validate B08's emitted `operation_instances` in `b08_crossstore_ledger.json` against `B05`'s 19-key contract validator and record candidate `RESULT.json` SHA256 hashes for `B01`, `B02`, `B03`, and `B04`):
  ```bash
  python3 -c 'import hashlib, json, pathlib; p = pathlib.Path("research/operations/udb-wave8/B08/b08_crossstore_ledger.json"); data = json.loads(p.read_text()); print("ledger_sha256:", hashlib.sha256(p.read_bytes()).hexdigest(), "instances:", len(data["operation_instances"]), "dimensions:", len(data["dimensions"]), "block_closed:", data["block_closed"])'
  ```

## Adversarial review

A real scoped Codex document review examined source SHA-256 5447eb37abc05517a5f2233257a57c2c1c7be1fde4639f67402629a234d51c1b. R1-DOCUMENT-REVIEW.json records scope, findings and limitations: REVIEWED_PARTIAL_WITH_BLOCKERS, no full-document or implementation approval. Historical wrong counts/paths/authority proposals do not become executable through attribution. The addendum reconciles actual receipts; this is not an independent code grade. Requested supporting seat: Astra 6 / xhigh; effective runtime identity UNOBSERVED. A fresh independent Opus 5.5 / xhigh exact-head BLUE gate remains required.
