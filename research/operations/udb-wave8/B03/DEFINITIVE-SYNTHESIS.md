---
adversarial_review: codex
---

# B03 Definitive Synthesis — Active-Consumer Denominator

- **Campaign ID:** `universal-db-wave8-20261015`
- **Block ID:** `B03` (`Active-consumer denominator`)
- **Mission Colour & Seat Role:** `BLUE` — `EXTERNAL PREPARER, NO_DUX` (Host: `Mini`)
- **Branch / Worktree:** `agent/mini-pro2/db/udb-b03-census` — `/Users/nuzantara/nuzantara/.worktrees/db-udb-b03-census`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage:** `DEFINITIVE SYNTHESIS + EXECUTION (Single Permitted Correction Applied)`

---

## 1. Dux-Observed On-Disk SHA-256 Digests & Receipts (Facts)

All frozen inputs, Dux synthesis conventions, prior wave artifacts, and `DUX-REQUESTS` receipts are pinned to the Dux-observed on-disk `shasum -a 256` values (`DUX-NOTE-CORRECTION.md:16-35`):

| Artifact Path | On-Disk SHA-256 | Role / Observed Status |
|---|---|---|
| `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json` | `e8a35c2404520884f58c7d2801e647c743b86cf69707591f1a1c828bab97722e` | Frozen Wave 8 input manifest (`files` + `scope` keys) |
| `.agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md` | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` | Scoped Astra 6/xhigh guidance |
| `.agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json` | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` | Prior BLUE gate (`NO-GO`) |
| `.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | Mini restore drill execution receipt (`rc=3`) |
| `.agent-receipts/udb-wave8-inputs/REPORT.md` | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` | Prior completion report |
| `.agent-receipts/udb-wave8-inputs/STATE.json` | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` | Prior completion state (`total_leads: 6030`) |
| `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | `6,029` consumer rows (`6,030` lines w/ header) |
| `.agent-receipts/udb-wave8-inputs/research-lines.csv` | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` | Block dependency matrix |
| `.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json` | `91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7` | 6,030th lead (`runtime_mini_46522da0ef79d3aa7422ca41`) + 5 historical restore refs |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/source-index-enhanced.json` | `9f90a66733d63b9183ad21beeca6b84b78db0b243e41aeb9a1d7bc5ab89363cd` | Pinned supplementary prior (`10,299` nodes) |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-pro.json` | `4f7bf4e90c1aad7f47ca04cd80ca8fe304cf2affae56bbc68fca080185986703` | Pinned supplementary prior (`observed_at: 2026-10-12T05:16:40.748258+00:00`) |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-mini.json` | `99bff7025a5cfecd5b4413c8f9b19e921f884b6f80890a9e3fffc7342c2306e2` | Pinned supplementary prior (`observed_at: 2026-10-12T05:16:41.077585+00:00`) |
| `.agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/jobs-M5.json` | `b53d5b487c7da69e732e4bd31a57a422f655871b11b738f9ef136f3f596c7198` | Pinned supplementary prior (`observed_at: 2026-10-12T05:16:41.337970+00:00`) |
| `.agent-receipts/udb-wave8-inputs-dux/prior/advance-20261014-0535/GITHUB-WORKFLOW-METADATA.json` | `115e40a4d82a89b11301ef17b7820ecf4ee94e0f51f4e8a3e94ad91fbb729a29` | Pinned supplementary prior (`observed_at: 2026-10-13T22:12:52.915013+00:00`) |
| `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md` | `29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54` | Consolidated adversarial findings (`X1`–`X13`, `B03-F1`–`B03-F6`) |
| `.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md` | `a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559` | Frozen sibling contract field & value conventions |
| `.agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md` | `c39218718f496b643b550abf98ca40bd2755e74d3954caed953005eb5b906e14` | Dux synthesis rulings & sibling alignment |
| `research/operations/udb-wave8/B03/dux-requests/DUX-REQ-B03-01.out` | `5f75a3842b88278d37a44c46c033f7f9363ee8892a7c72144c5d77f124802b1c` | `OK_DUX_CORRECTED` (`exit 0`): 6,029-row prefix/type/status/blocker breakdown |
| `research/operations/udb-wave8/B03/dux-requests/DUX-REQ-B03-02.out` | `68dfa39474c7e7f69f835e3c7c6f4d9408073187c296921b75673e49b19ddc35` | `OK` (`exit 0`): `index_*` vs `src_*` overlap = `0/678` |
| `research/operations/udb-wave8/B03/dux-requests/DUX-REQ-B03-03.out` | `393e5450977dc09335cf1a3a000a53cc1822e64ca8617ac834818afa06d03786` | `OK` (`exit 0`): Restore-drill & manual/break-glass row inventory |
| `research/operations/udb-wave8/B03/dux-requests/DUX-REQ-B03-04.out` | `e6e2d89b8da3c825606f5917040d9b355bf085ade24b51dd60c9ee3e0cc1cdc0` | `OK` (`exit 0`): Non-dot glob receipt (`**` skipped `.agent-receipts/`) |
| `research/operations/udb-wave8/B03/dux-requests/DUX-REQ-B03-10.out` | `ee9cd107a8651119b0b0bd5e14059572eae7a60f5ecbc2a16b629f34f1d2a981` | Pre-correction diagnostic `FAILED` (`exit 1`, `PinVerificationError` on old manifest pin); historical failure retained; current-source verification is recorded in INTEGRATION-VERIFICATION.json |
| `research/operations/udb-wave8/B03/dux-requests/DUX-REQ-B03-11.out` | `ccc00a341818bc8ac421a10ecd70021d237c35ed48646200bd1685771c5207a6` | Pre-correction diagnostic `FAILED` (`exit 1`, `PinVerificationError` on old manifest pin); historical failure retained; current-source verification is recorded in INTEGRATION-VERIFICATION.json |
| `research/operations/udb-wave8/B03/dux-requests/DUX-REQ-B03-12.out` | `dbc54d786d78254cd799e6b35cdc51cbc1ec83eea26277c51062567a32ee32c2` | `OK` (`exit 0`): `matched_index_nodes: 10292 of 10299` (`source_id == sha256(path)[:24]` of `git ls-files`) |

Note on `DUX-REQ-B03-13` (cross-host LaunchAgents/crontab hashing): **DEFERRED / NOT ADMITTED** (`DUX-NOTE-CORRECTION.md:13-14`). Removed from `## DUX-REQUESTS`; nothing is claimed from it.

---

## 2. Complete Adversarial Dispositions Table

Every cross-block finding naming `B03` (`X1`, `X2`, `X3`, `X5`, `X9`, `X10`, `X11`, `X13`) and every block-specific finding (`B03-F1` through `B03-F6`) from `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md` has been addressed:

| Finding ID | Severity | Adversary Challenge Summary | Disposition | Concrete Resolution & Verification |
|---|---|---|---|---|
| **X1** | BLOCKER | `store_id` syntax incompatible across blocks (`B03` proposed `store_pg_fly_prod` vs `B04` `<engine>:<platform>:<instance>[/<subcontainer>]`). | **ACCEPT** | Adopted `CONTRACT-CONVENTIONS.md:32-40` and `DUX-NOTE-CORRECTION.md:43-44`. Because B04 owns store cataloguing and has not catalogued `pg:mini:local` (or the 5 `engine_*` host engines), `b03_census_adapter.py` writes `"unknown:unknown:unknown"` for `store_id` and records `STORE_ID_PROPOSED:<value>` plus `STORE_BINDING_PENDING_B04` (or `NON_CONSUMER_ENTITY_EXCLUDED`) in `unknowns`. |
| **X2** | BLOCKER | `operation_id` minted independently by 5 blocks; B03 proposed `op_restore_drill_verify` / `UNRESOLVED_OP`. | **ACCEPT** | Adopted `CONTRACT-CONVENTIONS.md:28-31`. Only B05 mints `op:<domain>:<verb>:<object>`. `b03_census_adapter.py` emits `"UNASSIGNED_B05"` on all rows and appends `"OPERATION_ID_PENDING_B05"` to `unknowns`. |
| **X3** | BLOCKER | `status` overloaded with 4 incompatible vocabularies; B03 placed `active \| retired \| duplicate \| excluded \| unresolved` inside `status`. | **ACCEPT** | Adopted `CONTRACT-CONVENTIONS.md:49-51`. `status` is restricted to `EVIDENCED \| PARTIAL \| BLOCKED \| CONFLICT \| UNKNOWN`. Lifecycle disposition is carried exclusively in `x_disposition` (`active \| retired \| duplicate \| excluded \| unresolved`). |
| **X5** | MAJOR | `source_version` and `evidence_timestamp` lack canonical rule; adapter execution time and `STATE.json` `03:28:00Z` must never be used as evidence timestamps. | **ACCEPT** | Adopted `CONTRACT-CONVENTIONS.md:41-46` and `DUX-NOTE-CORRECTION.md:41-42`. `b03_census_adapter.py` never calls `datetime.now()` and never uses `03:28:00Z`. Repository-static rows (`src_*`, `index_*`, `runtime_<16hex>`, `mcp_*`, `NOTEBOOK-CONTAINER-REFERENCE-NLM-*`) use base commit timestamp `"2026-10-15T07:06:22Z"` and record `"STATIC_SOURCE_ONLY"` in `unknowns`. Prior host/CI/execution rows use the backing artifact's own timestamp (`2026-10-12T05:16:40.748258+00:00` for `jobs-pro.json`, `2026-10-12T05:16:41.077585+00:00` for `jobs-mini.json`, `2026-10-12T05:16:41.337970+00:00` for `jobs-M5.json`, `2026-10-13T22:12:52.915013+00:00` for `GITHUB-WORKFLOW-METADATA.json`, and `2026-10-15T03:00:43Z` for `REAL-RUN-RECEIPT.json`). |
| **X9** | MAJOR | `B01` and `B03` both claim authority over denominator gates without referencing each other's rule IDs. | **ACCEPT** | Per `DUX-CONSOLIDATION.md:67`, B03 owns per-lead census disposition (`x_disposition`) and summary accounting in `b03-census-summary.json` for B01's gate rules to consume; B03 does not mint parallel gate rules. |
| **X10** | MAJOR | Restore-drill organ (`runtime_mini_46522da0ef79d3aa7422ca41`) classified differently across B03, B05, B06, B07, B09. | **ACCEPT** | Per `DUX-CONSOLIDATION.md:68` and `DUX-NOTE-CORRECTION.md:43-44`, `runtime_mini_46522da0ef79d3aa7422ca41` is one consumer lead with `store_id = "unknown:unknown:unknown"`, `"STORE_ID_PROPOSED:pg:mini:local"` and `"STORE_BINDING_PENDING_B04"` in `unknowns`, `status = "PARTIAL"`, `x_disposition = "unresolved"`, and `x_restore_ref_role = "live_mini_restore_organ_partial_contract"`. |
| **X11** | MAJOR | 67 `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` rows and 5 `engine_*` rows must be excluded consistently across blocks. | **ACCEPT** | Per `CONTRACT-CONVENTIONS.md:26` and `DUX-CONSOLIDATION.md:69`, all 67 `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` rows, all 5 `engine_*` rows, and all 1,731 `RETAINED_TEST_SOURCE` rows (`1,803` total) are assigned `x_disposition = "excluded"`. |
| **X13** | MINOR | Sibling output formats differ (JSONL, CSV, YAML, SQLite) without declared canonical serialization. | **ACCEPT** | Per `CONTRACT-CONVENTIONS.md:8-13`, `b03_census_adapter.py` writes both canonical JSONL (`b03-consumer-census.jsonl`, with `unknowns` as a JSON array) and CSV (`b03-consumer-census.csv`, with `unknowns` `;`-joined) with the 8 frozen fields first and `x_`-prefixed B03 fields after. |
| **B03-F1** | MAJOR | `DUX-REQ-B03-02` falsified both proposed duplicate-join mechanisms (`0/678` `index_*` match `src_*`; `0` `CI-REGISTRATION-UNMATCHED-GH-*` matched `src_*`). | **ACCEPT** | `src_*` (`4,441` rows with lexical datastore hits) and `index_*` (`678` rows with entry markers and zero lexical datastore hits) are disjoint partitions of `source-index-enhanced.json`. `DUX-REQ-B03-12.out` proved `source_id == sha256(path)[:24]` across `10,292 / 10,299` nodes in `source-index-enhanced.json`. For `CI-REGISTRATION-UNMATCHED-GH-*` (`114` rows, lines `5850–5963`), `entry_point` (`source-path-sha256:<64hex>`) has `<64hex>[:24]` matching `index_<24hex>`, which is recorded in `x_candidate_join_id` while keeping `x_disposition = "unresolved"` per `PATH_MATCH_DOES_NOT_PROVE_SAME_DATABASE_CONSUMER`. Only the 43 `runtime-{pro,mini}-plist-<16hex>` rows (lines `4700–4742`)—whose `canonical_id` (`job_{pro,mini}_<24hex>`) is checked directly against `supp_meta["pro_job_ids"]` / `supp_meta["mini_job_ids"]` loaded from `jobs-pro.json` and `jobs-mini.json` (with the `or bool(canonical_id)` tautology removed per `DUX-NOTE-CORRECTION.md:40`)—are marked `x_disposition = "duplicate"`. |
| **B03-F2** | MAJOR | `DUX-REQ-B03-04` glob missed `.agent-receipts/udb-wave8-inputs-dux/prior/` because Python `glob("**")` skips dot-directories. | **ACCEPT** | All 6 prior artifacts under `.agent-receipts/udb-wave8-inputs-dux/prior/` are now pinned in `PINNED_PRIOR_INPUTS` and checked fail-closed by `verify_pinned_inputs()`. |
| **B03-F3** | MAJOR | Factual line-number and prefix-count errors in `ANALYSIS.md`. | **ACCEPT** | Corrected all line numbers, consumer IDs, and prefix counts in §3 and §4 below using `DUX-REQ-B03-01.out` and `DUX-REQ-B03-03.out`. |
| **B03-F4** | BLOCKER | `PROPOSAL.md` invented a 6th sub-state `blocked_evidence` that could silently shrink the unresolved denominator. | **ACCEPT** | Dropped `blocked_evidence` completely. `x_disposition` is strictly `active \| retired \| duplicate \| excluded \| unresolved`. All 3,647 `BLOCKED_DISCOVERY`, 284 `BLOCKED_RUNTIME_CONTRACT`, 8 `BLOCKED_MCP_REACHABILITY`, 317 `PARTIAL_DISCOVERY`, and 38 `UNMATCHED_CURRENT_SOURCE_PATH` non-duplicate rows remain `x_disposition = "unresolved"`. |
| **B03-F5** | MAJOR | Failed to inspect `LEAD-DELTA.json` directly and missed the 5 `historical_source_references_retained` IDs. | **ACCEPT** | Read `.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json:48-55` and reconciled all 5 IDs (`src_307bea3dfb94ec31`, `src_d073f505ff1671ad`, `src_def7a4c288a552af`, `src_cdf3ae5e4ecf861c`, `src_2f350566b97aee80`) in `b03_census_adapter.py` (`HISTORICAL_RESTORE_REFS`) and §4 below. |
| **B03-F6** | MINOR | `source_version` / `evidence_timestamp` undefined; manual/break-glass enumeration missed `scripts/pg-restore-drill.sh`, `scripts/pg.sh`, and runbook manual paths. | **ACCEPT** | Fixed `source_version` and `evidence_timestamp` per `CONTRACT-CONVENTIONS.md` (`X5`), and expanded `MANUAL_BREAK_GLASS_PATTERNS` in `b03_census_adapter.py` and §5 below. |

---

## 3. Verified Facts: 6,030-Lead Population & Prefix Accounting (`DUX-REQ-B03-01.out`)

From `DUX-REQ-B03-01.out:25-316`, `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`6,029` data rows, lines `2–6030`), and `.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json` (`1` delta row), the `6,030` leads partition as follows under `b03_census_adapter.py` (confirmed by the current-source integration receipts in `INTEGRATION-VERIFICATION.json`):

| Lead Family / Prefix | CSV Lines | Total Leads | `excluded` | `duplicate` | `retired` | `active` | `unresolved` | `evidence_timestamp` | Backing Artifact (`x_evidence_ref`) |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `src_<16-20hex>` | `2–4440`, `4698–4699` | `4,441` | `1,731` | `0` | `0` | `0` | `2,710` | `2026-10-15T07:06:22Z` | `.../census-20261012-0454/source-index-enhanced.json` |
| `runtime_<16hex>` | `4441–4688`, `4697` | `249` | `0` | `0` | `0` | `0` | `249` | `2026-10-15T07:06:22Z` | `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` |
| `mcp_<16hex>` | `4689–4696` | `8` | `0` | `0` | `0` | `0` | `8` | `2026-10-15T07:06:22Z` | `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` |
| `runtime-pro-plist-<16hex>` | `4700–4737` | `38` | `0` | `38` | `0` | `0` | `0` | `2026-10-12T05:16:40.748258+00:00` | `.../census-20261012-0454/jobs-pro.json` |
| `runtime-mini-plist-<16hex>` | `4738–4742` | `5` | `0` | `5` | `0` | `0` | `0` | `2026-10-12T05:16:41.077585+00:00` | `.../census-20261012-0454/jobs-mini.json` |
| `runtime-pro-backup-fabecdf99dd5201c` | `4743` | `1` | `0` | `0` | `0` | `0` | `1` | `2026-10-12T05:16:40.748258+00:00` | `.../census-20261012-0454/jobs-pro.json` |
| `index_<24hex>` | `4744–5421` | `678` | `0` | `0` | `0` | `0` | `678` | `2026-10-15T07:06:22Z` | `.../census-20261012-0454/source-index-enhanced.json` |
| `job_pro_<24hex>` | `5422–5639` | `218` | `0` | `0` | `0` | `0` | `218` | `2026-10-12T05:16:40.748258+00:00` | `.../census-20261012-0454/jobs-pro.json` |
| `cron_pro_<24hex>` | `5640–5727` | `88` | `0` | `0` | `0` | `0` | `88` | `2026-10-12T05:16:40.748258+00:00` | `.../census-20261012-0454/jobs-pro.json` |
| `job_mini_<24hex>` | `5728–5764` | `37` | `0` | `0` | `0` | `0` | `37` | `2026-10-12T05:16:41.077585+00:00` | `.../census-20261012-0454/jobs-mini.json` |
| `cron_mini_<24hex>` | `5765–5771` | `7` | `0` | `0` | `0` | `0` | `7` | `2026-10-12T05:16:41.077585+00:00` | `.../census-20261012-0454/jobs-mini.json` |
| `job_M5_<24hex>` | `5772–5786` | `15` | `0` | `0` | `0` | `0` | `15` | `2026-10-12T05:16:41.337970+00:00` | `.../census-20261012-0454/jobs-M5.json` |
| `engine_*` | `5787–5791` | `5` | `5` | `0` | `0` | `0` | `0` | Host `jobs-{pro,mini,M5}.json` `observed_at` | `jobs-pro.json` / `jobs-mini.json` / `jobs-M5.json` |
| `SOURCE-PATH-UNMATCHED-PRO-*` + `SOURCE-TRACE-*` | `5792–5849` | `58` | `0` | `0` | `0` | `0` | `58` | `2026-10-12T05:16:40.748258+00:00` | `.../census-20261012-0454/jobs-pro.json` |
| `CI-REGISTRATION-UNMATCHED-GH-*` | `5850–5963` | `114` | `0` | `0` | `0` | `0` | `114` | `2026-10-13T22:12:52.915013+00:00` | `.../advance-20261014-0535/GITHUB-WORKFLOW-METADATA.json` |
| `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` | `5964–6030` | `67` | `67` | `0` | `0` | `0` | `0` | `2026-10-15T07:06:22Z` | `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` |
| `runtime_mini_46522da0ef79d3aa7422ca41` (`LEAD-DELTA.json`) | `N/A (delta)` | `1` | `0` | `0` | `0` | `0` | `1` | `2026-10-15T03:00:43Z` | `.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json` |
| **Total (`6,030` Leads)** | **All** | **`6,030`** | **`1,803`** | **`43`** | **`0`** | **`0`** | **`4,184`** | — | **Design Conservation: `1803 + 43 + 0 + 0 + 4184 = 6030`** |

---

## 4. Reconciliation of the 5 Historical Restore References (`LEAD-DELTA.json:48-55`)

In `.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json:48-55`, the live Mini restore organ `runtime_mini_46522da0ef79d3aa7422ca41` (`label_hash: 46522da0ef79d3aa7422ca4129b701d5e19a863a02d71543567183c4ca09777d`) is linked to five historical repository source leads (`historical_source_references_retained`), with `"legacy_copies_elsewhere_proved_retired": false`:

| `consumer_id` | CSV Line | `entry_point` | CSV `status` | B03 `status` | B03 `x_disposition` | `x_restore_ref_role` | Disposition Rationale |
|---|---:|---|---|---|---|---|---|
| `src_307bea3dfb94ec31` | `25` | `.github/workflows/restore-drill.yml` | `BLOCKED_DISCOVERY` | `BLOCKED` | `unresolved` | `historical_restore_ref:git_deleted_workflow_legacy_unproved` | Deleted from git in `e1b328af52` and absent from `GITHUB-WORKFLOW-METADATA.json`, **but** `LEAD-DELTA.json:55` states `legacy_copies_elsewhere_proved_retired: false`. Per `evaluate_retirement_claim()`, cannot be marked `retired` until legacy copies across hosts are proved retired. |
| `src_d073f505ff1671ad` | `3280` | `scripts/ci/restore_drill_verify.py` | `BLOCKED_DISCOVERY` | `BLOCKED` | `unresolved` | `historical_restore_ref:restore_drill_verifier_script` | Tracked in git; invoked by Mini restore organ `runtime_mini_46522da0ef79d3aa7422ca41`. Target/store contract and standalone invocation remain `unresolved`. |
| `src_def7a4c288a552af` | `3727` | `scripts/pg-restore-drill.sh` | `BLOCKED_DISCOVERY` | `BLOCKED` | `unresolved` | `historical_restore_ref:pg_restore_drill_shell_script` | Tracked in git (`shell_script`, `datastore=postgres`); invoked by Mini restore organ and usable as manual operator script. |
| `src_cdf3ae5e4ecf861c` | `4046` | `scripts/tests/test_restore_drill_verify.py` | `RETAINED_TEST_SOURCE` | `PARTIAL` | `excluded` | `historical_restore_ref:verifier_unit_test_excluded` | Unit test suite (`test_coverage=test`); excluded from active production denominator. |
| `src_2f350566b97aee80` | `4047` | `scripts/tests/test_restore_drill_workflow_wiring.py` | `RETAINED_TEST_SOURCE` | `PARTIAL` | `excluded` | `historical_restore_ref:workflow_wiring_unit_test_excluded` | Unit test suite (`test_coverage=test`); excluded from active production denominator. |
| `runtime_mini_46522da0ef79d3aa7422ca41` | `LEAD-DELTA` | `sha256:e49f6ef5...` + `scripts/pg-restore-drill.sh` + `scripts/ci/restore_drill_verify.py` | `PARTIAL_DISCOVERY` | `PARTIAL` | `unresolved` | `live_mini_restore_organ_partial_contract` | Executed on Mini (`REAL-RUN-RECEIPT.json`, `2026-10-15T03:00:43Z`, `rc=3`, `overall="CANNOT-VERIFY"`). Uses `store_id="unknown:unknown:unknown"` with `"STORE_ID_PROPOSED:pg:mini:local"` and `"STORE_BINDING_PENDING_B04"` in `unknowns` because B04 has not catalogued `pg:mini:local`; `REAL_BACKUP_RESTORE_NOT_PROVED` and `EFFECTIVE_JOB_TARGET_AND_ROLE_OVERRIDES_UNOBSERVED` block promotion to `active`. |

---

## 5. Manual & Break-Glass Consumer Surface Enumeration (`B03-F6` & `DUX-REQ-B03-12.out`)

Per `ASTRA-ADVICE.md`, `DUX-REQ-B03-03.out`, and `DUX-REQ-B03-12.out`, manual/break-glass scripts and CLI entrypoints have zero cron/launchd schedule by design:

1. **Core Database Migration & Restore Operator Surfaces (`DUX-REQ-B03-03.out`)**:
   - `src_c8f206461cd9bf69` (CSV line `4440`, `apps/backend-rag/backend/db/migrate.py`, `BLOCKED_DISCOVERY`) — `x_manual_break_glass_class = "manual_migration_cli"`.
   - `src_058ad32e4ad2e6a8` (CSV line `343`, `apps/backend-rag/backend/db/migration_manager.py`, `BLOCKED_DISCOVERY`) — `x_manual_break_glass_class = "manual_migration_manager"`.
   - `src_def7a4c288a552af` (CSV line `3727`, `scripts/pg-restore-drill.sh`, `BLOCKED_DISCOVERY`) — `x_manual_break_glass_class = "manual_restore_drill_shell"`.
   - `src_d073f505ff1671ad` (CSV line `3280`, `scripts/ci/restore_drill_verify.py`, `BLOCKED_DISCOVERY`) — `x_manual_break_glass_class = "manual_or_cron_restore_verifier"`.
   - The previously asserted `src_07703aa402d20fc0` mapping for `apps/bali-intel-scraper/backend/db/migrations/env.py` is withdrawn: that ID is absent from the emitted census. No emitted consumer mapping or manual-surface classification is established here.
   - `src_2879480f813f3a7d` (CSV line `1584`, `apps/mouth/scripts/Migrate.sh`, `BLOCKED_DISCOVERY`) — `x_manual_break_glass_class = "manual_migration_shell"`.
2. **Additional Operator & Migration Scripts Confirmed in `source-index-enhanced.json` via `DUX-REQ-B03-12.out`**:
   - `DUX-REQ-B03-12.out` proved `10,292 / 10,299` `source-index-enhanced.json` `source_id` values equal `sha256(path)[:24]` of `git ls-files`, including `565f0d7a0ce55c64dd06f943` (`scripts/fly-pg-backup.sh`), `582504540432ac2b3c759feb` (`scripts/mini-migration/migrate-job.sh`), `7d0da4637b3306d0416b4f13` (`apps/backend-rag/scripts/release_migrate.sh`), `0da4162c9c64c774e2613f7a` (`infra/launchagents/wrappers/fly-pg-proxy-wrapper.sh`), `19634d31464404f32d4c98ea` (`infra/launchagents/install_fly_pg_tunnel.sh`), and `47a78a46e51d8aeb919f20b7` (`infra/scripts/pg-organism-bridge-watchdog.sh`).

---

## 6. Bounded Inferences & Explicit Unknowns

The earlier source-disposition category totals describe frozen source categories, not the unresolved output denominator; exclusions and duplicate handling intervene. The authoritative emitted unresolved count is `4184`, and the active denominator remains `UNKNOWN`.

### Bounded Inferences
1. **`CI-REGISTRATION-UNMATCHED-GH-*` ↔ `index_*` Path-Hash Alignment**: Of the `114` frozen `CI-REGISTRATION-UNMATCHED-GH-*` rows (historical lines `5850–5963`), the emitted census records `98` nonempty candidate index joins and `16` empty joins. All `114` remain unresolved; the prior all-114 index-match claim is withdrawn. Under `consumer-matrix.csv` blocker `PATH_MATCH_DOES_NOT_PROVE_SAME_DATABASE_CONSUMER`, this is recorded in `x_candidate_join_id` as a candidate link rather than collapsed into `x_disposition = "duplicate"`.
2. **`runtime-{pro,mini}-plist-*` ↔ `job_{pro,mini}_*` Pre-Image Identity**: All `43` `runtime-{pro,mini}-plist-<16hex>` rows (`38` Pro + `5` Mini, lines `4700–4742`) name a canonical `job_{pro,mini}_<24hex>` in `identity_relationships` whose `label_hash[:24]` is checked directly against `jobs-pro.json` and `jobs-mini.json` (`supp_meta["pro_job_ids"]` / `supp_meta["mini_job_ids"]`).

### Explicit Unknowns (`active_consumer_denominator = "UNKNOWN"`)
1. **Independent Acceptance and Committed-Head Binding Pending**: Current-source tests and fixture CLI now pass as recorded in `INTEGRATION-VERIFICATION.json`. Historical pre-correction `DUX-REQ-B03-10` and `DUX-REQ-B03-11` failures remain preserved in their original receipts. The coordinator must independently accept the frozen candidate and bind its final committed head.
2. **Unresolved Consumer Leads**: Lack deployed-execution evidence (`PRODUCTION_EXECUTION_NOT_OBSERVED`), concrete store instance binding (`STORE_BINDING_PENDING_B04`), and operation contract assignment (`OPERATION_ID_PENDING_B05`).
3. **Unproved Host Retirement of Legacy Restore Workflow Copies**: `LEAD-DELTA.json:55` records `legacy_copies_elsewhere_proved_retired: false` for `.github/workflows/restore-drill.yml` (`src_307bea3dfb94ec31`).

---

## DUX-REQUESTS

Historical requested commands are retained below for traceability. Their execution placeholders are superseded by the scoped current-source receipts in `INTEGRATION-VERIFICATION.json`; they are not additional execution orders:

- **`DUX-REQ-B03-10` (Run Unit & Negative Test Suite)**:
  - **Command**: `python3 -I -B -m unittest discover -s research/operations/udb-wave8/B03 -p "test_*.py" -v`
  - **Expected Observation**: All 8 test methods in `test_b03_census_adapter.py` pass (`OK`) against the corrected on-disk SHA-256 pins.
- **`DUX-REQ-B03-11` (Emit Deterministic 6,030-Row Census Artifacts)**:
  - **Command**: `python3 -I -B research/operations/udb-wave8/B03/b03_census_adapter.py --output-dir research/operations/udb-wave8/B03/artifacts`
  - **Expected Observation**: Writes `b03-consumer-census.csv` (`6,031` lines w/ header), `b03-consumer-census.jsonl` (`6,030` lines), and `b03-census-summary.json`, and prints summary JSON with emitted artifact SHA-256 digests to stdout.
- **`DUX-REQ-B03-12` (Repository Path Pre-Image Join Against `index_*`)**:
  - **Command**: `python3 -I -B -c 'import hashlib, json, subprocess; files = subprocess.check_output(["git", "ls-files"], text=True).splitlines(); idx = json.load(open(".agent-receipts/udb-wave8-inputs-dux/prior/census-20261012-0454/source-index-enhanced.json")); idx_set = {n["source_id"] for n in idx["nodes"]}; m = {hashlib.sha256(f.encode()).hexdigest()[:24]: f for f in files}; matched = sorted((sid, m[sid]) for sid in idx_set if sid in m); print("matched_index_nodes:", len(matched), "of", len(idx_set)); print("pg_sh_match:", [x for x in matched if "pg" in x[1] or "restore" in x[1] or "migrate" in x[1]][:30])'`
  - **Observed Pre-Correction Status**: Already passed (`exit 0`, `matched_index_nodes: 10292 of 10299`, stdout sha256 `dbc54d786d78254cd799e6b35cdc51cbc1ec83eea26277c51062567a32ee32c2`). Retained per `DUX-NOTE-CORRECTION.md:49`.


## Current-source integration receipt — 2026-10-16

The supplied hermetic patch passed exact preimage/hash verification and was applied to the original B03 worktree. Current-source pytest passed 24 tests with zero skips. The complete isolated candidate, without ignored inputs, also passed 24 tests with zero skips. Fixture CLI replay reproduced all three candidate census artifacts byte for byte; deterministic fixture derivation passed. Source and fixture hashes, commands, timestamps, the first incomplete-harness failure and its corrected rerun are in `INTEGRATION-VERIFICATION.json`. No source correction followed patch intake.

These are offline historical-fixture replays, not fresh native observations. The frozen C09 remains 6029 rows at SHA-256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`; the union remains 6030 after adding `runtime_mini_46522da0ef79d3aa7422ca41`. The actual active denominator remains `UNKNOWN`; 4184 leads remain unresolved. Native/store/operation/retirement unknowns above remain binding, `block_closed` remains false, and `head_sha` is null until the coordinator binds the committed candidate externally. The campaign deadline and correction budget are unchanged.

## Adversarial review

Fresh independent Codex review by `/root/b03_available_final_gate` inspected pre-attribution lines 1-11, 47-140, 156-160, as pinned in `R1-DOCUMENT-REVIEW.json`. This is a scoped document review, not a complete document endorsement, implementation approval, native observation or final exact-head gate. Surviving objections DOC3, DOC4, DOC5 are retained in that receipt; the parent reconciled the current synthesis facts and labels the rejected historical schema/join/retirement hypotheses as superseded. Historical command/runtime statements are retained as recorded instructions and receipts, not newly observed events. Operational acceptance and the active denominator remain unproved.
