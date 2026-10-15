# B03 Analysis — Active-Consumer Denominator & 6,030-Lead Reconciliation

## 0. Mandate & Execution Metadata

| Field | Value |
| :--- | :--- |
| **Campaign** | `universal-db-wave8-20261015` |
| **Block** | `B03` — Active-consumer denominator |
| **Mission Colour / Gear** | `BLUE` / `GEAR3` |
| **Dux Role** | `EXTERNAL PREPARER, NO_DUX` |
| **Host** | `Mini` |
| **Worktree** | `/Users/nuzantara/nuzantara/.worktrees/db-udb-b03-census` (`~/nuzantara/.worktrees/db-udb-b03-census`) |
| **Base Commit** | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` |
| **Pinned Current-Main Baseline** | `d0c67ee668f97c754e8bcec662d0df7dbf30a126` (`STATE.json:10`) |
| **Model / Requested Effort** | `Gemini 4 Argon` / `High` |
| **Server Effort Echo** | `UNOBSERVED` |
| **Conversation ID** | `21deb6db-2bcf-4f65-ae16-47e1040160bd` |
| **Sibling Dependencies** | `B04`, `B07` (and operation-instance handoff to `B05`) |
| **Input Baseline Scope** | `FROZEN_DATED_TECHNICAL_BASELINE_NOT_NEW_LIVE_PROOF` (`INPUT-MANIFEST.json:3`) |

### Pinned Input Manifest Digests (`.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:4-12`)
- `REPORT.md`: `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a`
- `STATE.json`: `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4`
- `FINAL-BLUE-GATE.json`: `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856`
- `REAL-RUN-RECEIPT.json`: `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d`
- `ASTRA-ADVICE.md`: `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8`
- `research-lines.csv`: `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10`
- `consumer-matrix.csv`: `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`

---

## 1. Facts (With Exact `file:line` Citations and Input Hashes)

### 1.1 Composition of the 6,030 Heterogeneous Leads Universe
1. **Top-Level Lead Accounting (`STATE.json:16-22`, `REPORT.md:48-60`)**:
   - `baseline_leads_preserved`: **6,029** data rows in `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv:2-6030` (line 1 is the 36-column header; total file lines = 6,031 with trailing newline; SHA-256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`).
   - `additional_runtime_observations`: **1** runtime organ observation (`mini.restore_drill`, the loaded Mini launchd restore organ introduced in commit `e1b328af52`, absent from earlier registration-label identities and tracked via `LEAD-DELTA.json`, `REPORT.md:42-45,58`, `STATE.json:19`).
   - `union_lead_rows`: **6,030** (`STATE.json:20`).
   - `active_consumer_denominator`: **`"UNKNOWN"`** (`STATE.json:21`).

2. **Observed Contiguous Blocks in `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`**:
   - **Header (`consumer-matrix.csv:1`)**: 36 columns: `consumer_id,domain,entry_point,evidence,runtime_registration,operations,store,schemas_tables_keys,owner,authority,identity_relationships,transaction_boundary,authorization,locality_sensitivity,retention,concurrency_idempotency,latency_availability,test_coverage,disposition,blocker,domain_hint,domain_classification,store_signal_hint,persistence_client_hints,activation_status,production_execution_evidence,contract_coverage_status,phase_source_path_evidence,phase_factory_candidate_count,phase_source_scope_status,phase_registered_ingress_evidence,phase_registered_source_route_candidates,phase_registered_source_scope,phase_ci_registration_evidence,phase_ci_reported_states,phase_ci_actor_identity`.
   - **`src_<16hex>` block (`consumer-matrix.csv:2-4440`, 4,439 rows)**: Repository lexical/source/config/test leads from `census-20261012-0454/source-index-enhanced.json`.
     - Lines `3-34` contain `.github/workflows/*.yml` rows. Most carry `GITHUB-WORKFLOW-METADATA.json; workflow sha256 <64hex>` in column 34 (`phase_ci_registration_evidence`) and `active` or `disabled_manually` in column 35 (`phase_ci_reported_states`), e.g., `src_e98bb23501189d64` (`.github/workflows/fly-deploy.yml`, `disabled_manually`, line 12).
     - Line `33` (`src_307bea3dfb94ec31`, `.github/workflows/restore-drill.yml`) has empty `phase_ci_registration_evidence` and `disposition=BLOCKED_DISCOVERY`.
     - Test files (e.g., `src_68731f9ccbfebfc8` at line 35, `src_bb703a3ef68e55dd` at line 36, `src_c621d38591c1fa96` at line 1500) carry `test_coverage=test`, `disposition=RETAINED_TEST_SOURCE`, and `blocker="Not counted as an active production consumer; coverage not inferred from filename"`.
     - Line `1476` (`src_c8f206461cd9bf69`, `apps/backend-rag/backend/db/migrate.py`) carries `test_coverage=cli_verified_isolated_46_of_129`, `disposition=ADAPTED_ISOLATED_VERIFIED`, and `blocker="Isolated CLI status/apply/plan verified on 46/129 files; 83 files fail out-of-order or historical assumptions; production ledger authority still requires Wave 1"`.
   - **`runtime_<16hex>` and `index_<24hex>` block (`consumer-matrix.csv:4441-5421`, 981 combined rows)**:
     - Starts at line `4441` (`runtime_43ef1245b8f39264`, `Air-M5:/Users/balizero/nuzantara/scripts/openclaw-health-guard.sh`, `classification=OUTSIDE_TRACKED_CODE_INDEX`, `disposition=BLOCKED_RUNTIME_CONTRACT`). Includes host paths on `Air-M5`, `Nuzantara`, and `mini-pro2` (`consumer-matrix.csv:4441-4600`).
     - Transitions to `index_<24hex>` static entry markers (`domain=source-entry-candidate`, `entry_point=source#<8hex>`, `disposition=BLOCKED_DISCOVERY`, `activation_status=STATIC_ENTRY_MARKER_ONLY`) running through line `5421` (`index_ab5a68ba9ce1de0179de2126`). Each `index_<24hex>` row embeds `source_id=<24hex>` in column 4 (`evidence`).
   - **Host Launchd & Cron Registration blocks (`consumer-matrix.csv:5422-5786`, 365 rows)**:
     - `job_pro_<24hex>` (`consumer-matrix.csv:5422-5639`, **218 rows**): Pro launchd registration candidates (`RUNNING_AT_SNAPSHOT`, `LOADED_NOT_RUNNING_AT_SNAPSHOT`, `LOADED_CONFIGURATION_METADATA_OBSERVED`, `NOT_LOADED_AT_SNAPSHOT`).
     - `cron_pro_<24hex>` (`consumer-matrix.csv:5640-5727`, **88 rows**): Pro cron schedule entries (`SCHEDULE_OBSERVED`, enriched with `shellgraph-20261013-1018` CST command/branch templates).
     - `job_mini_<24hex>` (`consumer-matrix.csv:5728-5764`, **37 rows**): Mini launchd registration candidates (`LOADED_NOT_RUNNING_AT_SNAPSHOT`, `SYSTEM_RUNTIME_UNOBSERVED`).
     - `cron_mini_<24hex>` (`consumer-matrix.csv:5765-5771`, **7 rows**): Mini cron schedule entries (`SCHEDULE_OBSERVED`).
     - `job_M5_<24hex>` (`consumer-matrix.csv:5772-5786`, **15 rows**): Air-M5 launchd registration candidates (`LOADED_NOT_RUNNING_AT_SNAPSHOT`, `NOT_LOADED_AT_SNAPSHOT`, `SYSTEM_RUNTIME_UNOBSERVED`).
   - **Infrastructure Engine block (`consumer-matrix.csv:5787-5791`, 5 rows)**:
     - `engine_pro_db290460f45d18f587ee2d73` (Pro PostgreSQL, line 5787), `engine_pro_50d92a3e7149a43398b9a3c1` (Pro Redis, line 5788), `engine_mini_ee20d4b0d807071ea399a99e` (Mini PostgreSQL, line 5789), `engine_mini_87c7a25641f2121e838d067c` (Mini Redis, line 5790), `engine_M5_ee20d4b0d807071ea399a99e` (Air-M5 PostgreSQL, line 5791).
   - **Unmatched Source-Path & Trace blocks (`consumer-matrix.csv:5792-5849`, 58 rows)**:
     - `SOURCE-PATH-UNMATCHED-PRO-<12hex>` (`consumer-matrix.csv:5792-5832`, **41 rows**) and `SOURCE-TRACE-UNMATCHED-PRO-<12hex>` (`consumer-matrix.csv:5833-5849`, **17 rows**), carrying `activation_status=PATH_NOVELTY_NOT_ACTOR_NOVELTY` and `blocker="PATH_MATCH_DOES_NOT_PROVE_SAME_DATABASE_CONSUMER"`.
   - **Unmatched GitHub CI Registration block (`consumer-matrix.csv:5850-5963`, 114 rows)**:
     - `CI-REGISTRATION-UNMATCHED-GH-<12hex>` (`consumer-matrix.csv:5850-5963`, **114 rows**): Records from `GITHUB-WORKFLOW-METADATA.json` with `source-path-sha256=<64hex>` and `reported_states=active` or `disabled_manually`.
   - **NotebookLM Container Reference block (`consumer-matrix.csv:5964-6030`, 67 rows)**:
     - `NOTEBOOK-CONTAINER-REFERENCE-NLM-<12hex>` (`consumer-matrix.csv:5964-6030`, **67 rows**): Records from `NOTEBOOKLM-REGISTRY-EXTRACT.json` with `store="NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY"`.

### 1.2 Facts on Historical Restore References & Manual/Break-Glass Consumers
1. **Historical Restore References (`REPORT.md:38-46,56-60`, `STATE.json:19,71-85`)**:
   - `.github/workflows/restore-drill.yml` (`src_307bea3dfb94ec31`, `consumer-matrix.csv:33`) is absent from pinned current-main `d0c67ee668f97c754e8bcec662d0df7dbf30a126`, having been replaced by the Mini launchd organ `mini.restore_drill` in commit `e1b328af52` (`REPORT.md:40-44`).
   - `scripts/ci/restore_drill_verify.py` (`src_4aa41913f64f2f8c`, `consumer-matrix.csv:4357`) remains present in the worktree (`scripts/ci/restore_drill_verify.py:1-120`), and its docstring at `scripts/ci/restore_drill_verify.py:3` still states: `Called by .github/workflows/restore-drill.yml after pg_restore finishes.`
   - `REPORT.md:59-60` records that five historical restore source references remain separate pending proper runtime reconciliation, and notes: *"Removing a repository workflow does not prove every deployed or manual legacy copy retired."*
2. **Manual / Break-Glass Consumer Leads (`consumer-matrix.csv:1476,4351-4440,4441-4600`)**:
   - `src_c8f206461cd9bf69` (`apps/backend-rag/backend/db/migrate.py`, line 1476): CLI migration tool verified in isolated execution (`46/129` files).
   - `src_4aa41913f64f2f8c` (`scripts/ci/restore_drill_verify.py`, line 4357): CLI post-restore verification script (`argparse` CLI at `scripts/ci/restore_drill_verify.py:92-119`).
   - Scripts under `scripts/` and `apps/*/scripts/` tagged with `PYTHON_SOURCE_WITH_ENTRY_MARKERS` in column 28 (`phase_source_path_evidence`), e.g., lines `4351-4440` (`scripts/wr2_*.py`, `scripts/wr3_*.py`).

---

## 2. Counterexamples & Structural Defects in the Frozen Baseline

### Counterexample 1 — Entity-Type Conflation in the 6,030-Lead Universe
- **Fact Base**: `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` (`consumer-matrix.csv:5964-6030`, 67 rows) explicitly carry `store="NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY"`. `engine_*` (`consumer-matrix.csv:5787-5791`, 5 rows) represent the PostgreSQL and Redis server processes (`D01_PHYSICAL_SCOPE`). `RETAINED_TEST_SOURCE` rows (e.g., `consumer-matrix.csv:35,36,1500`) explicitly carry `blocker="Not counted as an active production consumer; coverage not inferred from filename"`.
- **Counterexample**: Treating all 6,030 rows as candidate active database consumers violates type safety by mixing **stores/engines**, **external NotebookLM containers**, and **test files** into the consumer denominator.

### Counterexample 2 — Unjoined Multi-Phase Representation Duplicates
- **Fact Base**:
  1. `consumer-matrix.csv:3-34` (`src_*` for `.github/workflows/*.yml`) already record `GITHUB-WORKFLOW-METADATA.json; workflow sha256 <64hex>` in column 34, while `consumer-matrix.csv:5850-5963` (`CI-REGISTRATION-UNMATCHED-GH-*`, 114 rows) append workflow metadata records keyed by `source-path-sha256=<64hex>`.
  2. `index_<24hex>` rows (`consumer-matrix.csv:4800-5421`) record `source_id=<24hex>` from `source-index-enhanced.json`, whose 16-hex prefix corresponds to `src_<16hex>` rows from the same index.
  3. `SOURCE-PATH-UNMATCHED-PRO-*` and `SOURCE-TRACE-UNMATCHED-PRO-*` (`consumer-matrix.csv:5792-5849`, 58 rows) explicitly state `activation_status=PATH_NOVELTY_NOT_ACTOR_NOVELTY`.
- **Counterexample**: A single underlying code unit is represented multiple times across disjoint ID namespaces (`src_*`, `index_*`, `CI-REGISTRATION-UNMATCHED-GH-*`, `SOURCE-PATH-UNMATCHED-PRO-*`), inflating the lead count unless cross-namespace identity joins mark secondary rows `duplicate`.

### Counterexample 3 — Cross-Host Launchd Fan-Out and Unverified Retirement
- **Fact Base**: Identical 24-hex registration digests appear across `pro`, `mini`, and `M5`:
  - `677151fe12f23c23c5e04e5f` at `consumer-matrix.csv:5422` (`job_pro_`), `:5728` (`job_mini_`), and `:5772` (`job_M5_`).
  - `b10755ffacfc6dae401dcfe1` at `consumer-matrix.csv:5424` (`job_pro_`), `:5729` (`job_mini_`), and `:5774` (`job_M5_`).
  - `e227cf45488093dcd8cdbed0` at `consumer-matrix.csv:5426` (`job_pro_`), `:5730` (`job_mini_`), and `:5775` (`job_M5_`).
- **Counterexample**: Neither plist presence on a thin-client (`job_M5_*`, `LOADED_NOT_RUNNING_AT_SNAPSHOT`) nor git file deletion alone (`.github/workflows/restore-drill.yml` at `consumer-matrix.csv:33`) suffices to prove a consumer `active` or `retired` without host-level runtime reconciliation.

### Counterexample 4 — Static Shell/CST Grammar vs. Runtime Branch Selection
- **Fact Base**: All 88 `cron_pro_*` rows (`consumer-matrix.csv:5640-5727`) enriched with `shellgraph-20261013-1018` CST templates carry `blocker="STATIC_SHELL_CST_DOES_NOT_PROVE_RUNTIME_BRANCH_SELECTION; NO_LIVE_EXECUTION_OR_DATABASE_TARGET_PROOF"`.
- **Counterexample**: Static shell syntax trees cannot establish which branch executes in production or which `store_id` is targeted at runtime.

---

## 3. Inference & §Meta-pattern (Separated from Facts)

### §Meta-pattern — "Additive Observation Union Without Canonical Entity Resolution"
We infer from the structure of `consumer-matrix.csv` and `STATE.json` that prior census waves operated as an **append-only observation union**: whenever a new extraction pass ran (`source-index-enhanced.json`, `REGISTERED-INGRESS-SOURCE.json`, `SOURCE-BOUNDARY-PRO.json`, `GITHUB-WORKFLOW-METADATA.json`, `NOTEBOOKLM-REGISTRY-EXTRACT.json`, `shellgraph`, and host launchd/cron snapshots), any row not immediately joined was appended under a new prefix (`index_*`, `SOURCE-PATH-UNMATCHED-PRO-*`, `CI-REGISTRATION-UNMATCHED-GH-*`, `NOTEBOOK-CONTAINER-REFERENCE-NLM-*`).

Consequently:
1. **Observations were conflated with actors**: Static entry markers (`index_*`), path hashes (`SOURCE-PATH-UNMATCHED-PRO-*`), and CI state records (`CI-REGISTRATION-UNMATCHED-GH-*`) became separate rows alongside `src_*` source files.
2. **Truncated hash barriers prevented trivial joins**: Host launchd/cron registrations (`job_*`, `cron_*`) and unmatched path records replaced cleartext labels/paths with 12-hex or 24-hex SHA-256 prefixes in the CSV, decoupling them from `src_*` paths unless pre-image maps or path-hash recomputations are applied.
3. **Disposition overloaded entity class and verification status**: `disposition` mixed non-consumer category labels (`RETAINED_TEST_SOURCE`) with evidence-gate states (`BLOCKED_DISCOVERY`, `BLOCKED_RUNTIME_CONTRACT`).

---

## 4. Missing Evidence & Explicit Unknowns

1. **Exact Full-File Sub-Counts & Hash Join Tables in `consumer-matrix.csv`**:
   - Because shell/python execution is unavailable during ANALYSIS (`DUX-NOTE-ANALYSIS.md:11-14`), exact row counts for internal sub-slices (e.g., exact split between `runtime_*` and `index_*` within lines `4441-5421`, exact count of `RETAINED_TEST_SOURCE` across lines `2-4440`, and all 5 historical restore rows across the full CSV) require the read-only aggregations listed in `PROPOSAL.md` `## DUX-REQUESTS`.
2. **Pre-Image / Label Lookup Map for Hashed Host Registrations (`job_*`, `cron_*`, `SOURCE-PATH-UNMATCHED-PRO-*`)**:
   - The frozen input directory `.agent-receipts/udb-wave8-inputs/` contains only the 7 pinned files (`INPUT-MANIFEST.json:4-12`); the upstream pre-image artifacts (`census-20261012-0454/launchd-cron-normalize.json`, `SOURCE-BOUNDARY-PRO.json`, `LEAD-DELTA.json`) referenced in `consumer-matrix.csv` and `REPORT.md` are not in `.agent-receipts/udb-wave8-inputs/`.
3. **Live Runtime & Store Target Binding (`B04` and `B07` Dependencies)**:
   - Promotion of `BLOCKED_DISCOVERY` and `BLOCKED_RUNTIME_CONTRACT` leads to `status="active"` with a concrete `store_id` and `operation_id` requires runtime execution and store-target bindings from sibling blocks `B04` and `B07` (and operation-instance contracts from `B05`).
4. **Runtime Invocation Binding of `scripts/ci/restore_drill_verify.py` to `mini.restore_drill`**:
   - Whether the loaded Mini launchd organ `mini.restore_drill` invokes `scripts/ci/restore_drill_verify.py` (`src_4aa41913f64f2f8c`) or a separate verification path is unobserved in the 7 frozen files.
