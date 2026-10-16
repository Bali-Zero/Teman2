---
adversarial_review: codex
reviewed_source_sha256: "625fac618adf89018c64493f5bd5e61fc8ab57e863de28125b10969d8a50f699"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# B01 Definitive Synthesis — Real-Backup Recovery (`DEFINITIVE-SYNTHESIS.md`)

> **Dux addendum (2026-10-16, supersedes every conflicting statement below).** Authoritative status and evidence:
> `RESULT.json`. The only real-backup run of record is the 2026-10-15 run (started 03:00:43Z, terminal 03:02:11Z, 5 relations):
> aggregate CANNOT-VERIFY, `conversations` CANNOT-VERIFY (UNMEASURED_CHECK), `clients` FAIL (VIOLATION), `visa_decisions`,
> `events_outbox` and `visa_decision_retention_policies` PASS (raw-report sha256 `1d368c2d16d32a0834bb7d120d75005423227b77239107b1dc1873f8140b5744`;
> no rows, counts or raw errors exported). Any other run date, a 10/12 or 12/12 relation count, and any quoted consent field
> not in that receipt are withdrawn as unsupported. The five invariants and the strict `clients` predicate are unchanged;
> widening `clients` semantics is rejected. Option 2A (production backfill in S2+ before B01 closure) is a dependency cycle
> with S1 and is not adopted. Owner consent of 2026-10-16 ("continua") admits only boolean-only diagnostics, installation of
> the independently gated candidate with reviewed pins, and EXACTLY ONE isolated restore of an existing backup; it grants no
> client-row remediation, invariant change, repeat run or new backup. `block_closed` stays `false` until all five invariants
> are measured PASS on that run.

- **Campaign ID:** `universal-db-wave8-20261015`
- **Block ID:** `B01` — Real-backup recovery (`D14` Recovery, retention and security)
- **Mission Colour & Gear:** `BLUE` · `GEAR3`
- **Host & Seat:** `[Mini]` (`Mini-Pro2`) · `EXTERNAL PREPARER, NO_DUX` (Appointed BLUE Dux: `claude-opus-5-5` `xhigh` on `pro`)
- **Model / Effort / Session Honesty (`BATTLE.md:22`, `DUX-TRIAGE-B01-B06.md:22`):**
  - `requested_model`: `gemini-4-argon-high` | `requested_effort`: `high`
  - `effective_model`: `UNOBSERVED` | `effective_effort`: `UNOBSERVED`
  - `conversation_id`: `64a3af46-22ae-444a-b824-980df8bccf28`
- **Worktree:** `~/nuzantara/.worktrees/db-udb-b01-recovery`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`2026-10-15T07:06:22Z`)
- **Block Closure Status:** `block_closed: false` (blocked on three owner decisions documented in `RESTORE-ADMISSION-PROPOSAL.md`)

---

## 0. Pinned Inputs & Dux Consolidation Artifacts (Verified SHA-256)

| Pinned Artifact            | Path                                                                                           | SHA-256                                                            |
| :------------------------- | :--------------------------------------------------------------------------------------------- | :----------------------------------------------------------------- |
| `ADVERSARY-FINDINGS.md`    | `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md`                                          | `29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54` |
| `CONTRACT-CONVENTIONS.md`  | `.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md`                                        | `a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559` |
| `DUX-CONSOLIDATION.md`     | `.agent-receipts/udb-wave8-dux/DUX-CONSOLIDATION.md`                                           | `c39218718f496b643b550abf98ca40bd2755e74d3954caed953005eb5b906e14` |
| `DUX-TRIAGE-B01-B06.md`    | `.agent-receipts/udb-wave8-dux/DUX-TRIAGE-B01-B06.md`                                          | `806837176838f33b3cf7fc284316efe6d2d1a214b363d90aa3adbbf7acbfcc7c` |
| `REPORT.md`                | `.agent-receipts/udb-wave8-inputs/REPORT.md`                                                   | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` |
| `STATE.json`               | `.agent-receipts/udb-wave8-inputs/STATE.json`                                                  | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` |
| `FINAL-BLUE-GATE.json`     | `.agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json`                                        | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` |
| `REAL-RUN-RECEIPT.json`    | `.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json`                                       | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` |
| `research-lines.csv`       | `.agent-receipts/udb-wave8-inputs/research-lines.csv`                                          | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` |
| `consumer-matrix.csv`      | `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`                                         | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` |
| `ASTRA-ADVICE.md`          | `.agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md`                                             | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` |
| `LEAD-DELTA.json`          | `.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json`          | `91e6bac9c91181a2b3aa3f6cd1dc6585671c18ce90cb887444229a1a17a084e7` |
| `SYNTHETIC-PG-RESULT.json` | `.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/SYNTHETIC-PG-RESULT.json` | `38f9500820971b08cb6bbe2ada8251294f436905db96f49d59de547ce60aaa81` |

---

## 1. Consolidated Adversarial Findings Disposition Table

Every cross-block finding naming `B01` and every `B01-*` finding from `ADVERSARY-FINDINGS.md` and `DUX-CONSOLIDATION.md` is disposed below:

| Finding ID                 | Severity | Summary of Adversarial Finding                                                                                                                                                                          | Disposition      | Concrete Fix / Evidence in B01 Synthesis                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| :------------------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :--------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **X1**                     | BLOCKER  | `store_id` in B01 (`pg.nuzantara_backups_...`) used an incompatible grammar.                                                                                                                            | **ACCEPT & FIX** | Replaced with `unknown:unknown:unknown` and `"STORE_ID_PROPOSED:pg:mini:nuzantara-pg-drill/public"` in `unknowns` per `CONTRACT-CONVENTIONS.md:32-40`.                                                                                                                                                                                                                                                                                                                                                 |
| **X2**                     | MAJOR    | B01 minted `OP-B01-RESTORE-VERIFY`; only B05 owns `operation_id`.                                                                                                                                       | **ACCEPT & FIX** | Replaced with sentinel `"UNASSIGNED_B05"` and added `"OPERATION_ID_PENDING_B05"` to `unknowns` per `CONTRACT-CONVENTIONS.md:28-31`.                                                                                                                                                                                                                                                                                                                                                                    |
| **X3**                     | MAJOR    | B01 used `status = "FAIL"` instead of the common enumeration.                                                                                                                                           | **ACCEPT & FIX** | Replaced with `"BLOCKED"` from `EVIDENCED \| PARTIAL \| BLOCKED \| CONFLICT \| UNKNOWN` (`CONTRACT-CONVENTIONS.md:49-51`); verifier verdict moved to `x_verifier_aggregate`.                                                                                                                                                                                                                                                                                                                           |
| **X4**                     | BLOCKER  | Operation instances must have the exact 19 keys (`8 frozen + 11 instance`) with `{"value", "status", "evidence_ref"}` objects, plus `x_`-prefixed extras.                                               | **ACCEPT & FIX** | Enforced in `b01_recovery_adapter.py:validate_contract_instance_record` and tested in `test_b01_recovery_adapter.py`.                                                                                                                                                                                                                                                                                                                                                                                  |
| **X5**                     | MAJOR    | B01 used a fabricated `2026-04-19T14:45:07Z` `evidence_timestamp`.                                                                                                                                      | **ACCEPT & FIX** | Set `evidence_timestamp` to `"2026-10-15T03:02:11+00:00"` (verbatim terminal sidecar timestamp in `REAL-RUN-RECEIPT.json:32` and `STATE.json:86`).                                                                                                                                                                                                                                                                                                                                                     |
| **X6**                     | MAJOR    | Contradictory root causes stated as fact (`messages` JSONB vs JSON; "exactly one of two clients subchecks" deduced from `VIOLATION: 1`).                                                                | **ACCEPT & FIX** | Section 2 strictly separates **Facts (`F`)**, **Inferences (`I`)**, and **Unknowns (`U`)**. Per `REPORT.md:125-126`, the reason classes in `REAL-RUN-RECEIPT.json` identify neither the failing `clients` subcheck nor the underlying `conversations` error on the backup; both remain **Unknown (`U`)** on the backup.                                                                                                                                                                                |
| **X8 / X9**                | MAJOR    | Sibling ownership misassignments and dependency cycles.                                                                                                                                                 | **ACCEPT & FIX** | Followed `DUX-CONSOLIDATION.md:15-22` freeze order; B01 consumes only frozen inputs and pinned prior files, and sets `block_closed: false` with explicit `unknowns`.                                                                                                                                                                                                                                                                                                                                   |
| **X10**                    | MAJOR    | Fabricated or mis-cited IDs and receipt quotes in B01 (`DUX-TRIAGE-B01-B06.md` §2.1).                                                                                                                   | **ACCEPT & FIX** | The companion analysis and proposal bodies are reconciled in this prepared correction; the fresh whole-head gate is pending. `b01_recovery_adapter.py` membership-tests every `consumer_id` against the 6,030-lead union (`consumer-matrix.csv` + `LEAD-DELTA.json`).                                                                                                                                                                                                                                  |
| **X11**                    | MAJOR    | Prior native admissions do not stretch to new exercises; `B01:DUX-REQUEST-1` is not admitted.                                                                                                           | **ACCEPT & FIX** | Dropped `DUX-REQUEST-1` (marked `DEFERRED_NATIVE_PROBE` in `dux-requests/RECEIPTS.json:2-7` and ruled not admitted in `DUX-CONSOLIDATION.md:39`).                                                                                                                                                                                                                                                                                                                                                      |
| **X13**                    | MINOR    | Builders cannot run commands; test results must be Dux receipts; model/effort echo is `UNOBSERVED`.                                                                                                     | **ACCEPT & FIX** | Recorded `effective_model: UNOBSERVED`, `effective_effort: UNOBSERVED`, and set `RESULT.json` test results to `"PENDING_DUX_EXECUTION"`.                                                                                                                                                                                                                                                                                                                                                               |
| **B01-F1**                 | BLOCKER  | `ANALYSIS.md` and `PROPOSAL.md` cited a fabricated `2026-04-19T14:43Z` run, backup filename, 10/12 relations, exit 1, and `consent_scope`/`consent_exhausted` quotes.                                   | **ACCEPT & FIX** | The prepared correction replaces the unsupported provenance and consent assertions in the companion bodies with the receipt facts in Section 2.1; fresh whole-head verification remains pending. `REAL-RUN-RECEIPT.json` (`sha256: 9851ae05...`) started `2026-10-15T03:00:43.925327+00:00`, elapsed `87.658s`, covers 5 relations (`conversations` `CANNOT-VERIFY`, `clients` `FAIL`, `visa_decisions`/`events_outbox`/`visa_decision_retention_policies` `PASS`), and has aggregate `CANNOT-VERIFY`. |
| **B01-F2**                 | MAJOR    | `ANALYSIS.md:63` claimed any relation `FAIL` makes aggregate `FAIL`; in fact `CANNOT-VERIFY` takes precedence over `FAIL` (`STATE.json:92`, `REPORT.md:57-63`).                                         | **ACCEPT & FIX** | Corrected in Section 2.1 and pinned with dedicated regression tests (`test_fail_plus_unmeasured_check_gives_cannot_verify_aggregate` in `scripts/tests/test_restore_drill_verify.py` and `guilt_4` in `b01_recovery_adapter.py`).                                                                                                                                                                                                                                                                      |
| **B01-F3**                 | BLOCKER  | Change 3 would relax `_CLIENTS_VIOLATIONS_SQL` to force `clients` green (`REPORT.md:59` bars forcing green).                                                                                            | **ACCEPT & FIX** | Rejected Change 3 per `DUX-CONSOLIDATION.md:52-53`. `_CLIENTS_VIOLATIONS_SQL` in `scripts/ci/restore_drill_verify.py:222-229` is kept unchanged (`client_type NOT IN ('individual','company')` and `lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) <> 'object'`). Only the Wave 7 `required_columns` schema guard (`"lead_metadata"`) is added. Data-owner decision is proposed in `RESTORE-ADMISSION-PROPOSAL.md`.                                                                         |
| **B01-F4**                 | MAJOR    | Change 1 (`WHEN messages IS NULL THEN true`) silently tightened `NULL` handling compared to the non-`STRICT` `pg_temp.try_jsonb_array(text)` helper.                                                    | **ACCEPT & FIX** | Updated `_CONVERSATIONS_VIOLATIONS_SQL` (`scripts/ci/restore_drill_verify.py:204-215`) to filter `WHERE messages IS NOT NULL AND CASE WHEN pg_input_is_valid(messages::text, 'jsonb') THEN jsonb_typeof((messages::text)::jsonb) <> 'array' ELSE true END`, preserving exact `NULL` semantics (`NULL` rows are not counted on either `JSONB` or `TEXT`, verified by `guilt_2` in `b01_recovery_adapter.py`).                                                                                           |
| **B01-F5**                 | BLOCKER  | Merging to `main` does not update Mini's installed verifier (`3fe0dfc4...` in `$HOME/nuzantara`), and `NA-7` checks installed pins before running.                                                      | **ACCEPT & FIX** | Explicitly stated in Section 2.1 and `PR_BODY.md`, and formalized as **Owner Decision 1** in `RESTORE-ADMISSION-PROPOSAL.md`.                                                                                                                                                                                                                                                                                                                                                                          |
| **B01-F6**                 | MAJOR    | "Next scheduled run" cannot close B01 in this campaign (cadence unproved; prior sidecar `2026-10-12T15:07:50+00:00` was Monday `23:07` UTC+8; outside 24h window; would run base bytes).                | **ACCEPT & FIX** | Removed the claim that waiting for a scheduled run can close B01; documented in `RESTORE-ADMISSION-PROPOSAL.md` §1 (Decision 3).                                                                                                                                                                                                                                                                                                                                                                       |
| **B01-F7**                 | MAJOR    | `DUX-REQUEST-1` is a new live PROD exercise exporting integer counters over client tables and measures today's PROD, not the backup.                                                                    | **ACCEPT & FIX** | Withdrawn. `dux-requests/RECEIPTS.json:2-7` records `DEFERRED_NATIVE_PROBE`; `DUX-CONSOLIDATION.md:39` rules it not admitted.                                                                                                                                                                                                                                                                                                                                                                          |
| **B01-F8**                 | MAJOR    | "12/12 PASS" gate came from the fabricated relation count in F1; the verifier covers 5 relations (`STATE.json:93-123`).                                                                                 | **ACCEPT & FIX** | The prepared admission plan requires **5 relations** (`conversations`, `clients`, `visa_decisions`, `events_outbox`, `visa_decision_retention_policies`).                                                                                                                                                                                                                                                                                                                                              |
| **B01-F9**                 | MINOR    | Frozen-field row used non-CSV `consumer_id`, minted `operation_id`, fabricated timestamp, and `status=FAIL`; Change 4 logged counters to `run.log`.                                                     | **ACCEPT & FIX** | Rebuilt frozen-field row using `runtime_mini_46522da0ef79d3aa7422ca41` (`LEAD-DELTA.json:7`), `UNASSIGNED_B05`, `2026-10-15T03:02:11+00:00`, and `status=BLOCKED`. Dropped Change 4 (`scripts/restore_drill/run_drill.sh` is left untouched so no new counters are written to `run.log`).                                                                                                                                                                                                              |
| **Missing Negative Cases** | MAJOR    | Four guilt cases needed on synthetic PG17: (1) JSONB non-array counted; (2) NULL behaviour unchanged; (3) string-scalar `lead_metadata` still FAILs; (4) FAIL + unmeasured check gives `CANNOT-VERIFY`. | **ACCEPT & FIX** | Implemented in `b01_recovery_adapter.py:run_synthetic_pg17_suite`, `test_b01_recovery_adapter.py`, and `scripts/tests/test_restore_drill_verify.py`, and requested in `DUX-REQ-B01-10..12`.                                                                                                                                                                                                                                                                                                            |

---

## 2. Verified Facts (`F`), Inferences (`I`), and Unknowns (`U`)

### 2.1 Verified Facts (`F`)

1. **Authorized One-Run Real-Backup Receipt (`REAL-RUN-RECEIPT.json:1-83`, `STATE.json:39-41, 80-130`, `REPORT.md:117-127`):**
   - **F:** Owner authorization in `STATE.json:40` was `"real_backup_owner_authorization": "APPROVED_ONE_EXISTING_JOB"`, and `"real_backup_run_triggered": true` (`STATE.json:39`). That single-run consent is exhausted (`BATTLE.md:4,13`, `ASTRA-ADVICE.md:7`).
   - **F:** `REAL-RUN-RECEIPT.json` (`sha256: 9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d`) records:
     - `REQUEST_ACCEPTED` at `"started_at": "2026-10-15T03:00:43.925327+00:00"` with `"source_pin_matches": 6` (`lines 5-10`).
     - Three `OBSERVING` events with `"private_report_fd_observed": false` (`lines 12-25`).
     - `TERMINAL` event after `"elapsed_seconds": 87.337` (outer `"elapsed_seconds": 87.658`, `lines 3, 27-29`), with `sidecar` `"status": "error"` at `"timestamp": "2026-10-15T03:02:11+00:00"` (`lines 30-36`).
     - `verifier_summary.aggregate`: `"CANNOT-VERIFY"` (`line 38`).
     - **5 relations** in `verifier_summary.invariants` (`lines 39-69`):
       - `conversations`: `status: "CANNOT-VERIFY"`, `reason_classes: {"UNMEASURED_CHECK": 1}`
       - `clients`: `status: "FAIL"`, `reason_classes: {"VIOLATION": 1}`
       - `visa_decisions`: `status: "PASS"`, `reason_classes: {}`
       - `events_outbox`: `status: "PASS"`, `reason_classes: {}`
       - `visa_decision_retention_policies`: `status: "PASS"`, `reason_classes: {}`
     - `"raw_report_sha256": "1d368c2d16d32a0834bb7d120d75005423227b77239107b1dc1873f8140b5744"`, `"rows_counts_and_raw_errors_exported": false`, `"raw_logs_or_records_exported": false` (`lines 71-75`).
   - **F:** Prior sidecar before the authorized run recorded `"status": "error"` at `"timestamp": "2026-10-12T15:07:50+00:00"` (`STATE.json:32-38`, `REPORT.md:33-34`).
2. **Aggregate Precedence in `restore_drill_verify.py` (`scripts/ci/restore_drill_verify.py:438-445`, `REPORT.md:57-63`):**
   - **F:** `evaluate()` checks `if "CANNOT-VERIFY" in statuses: aggregate = "CANNOT-VERIFY" elif "FAIL" in statuses: aggregate = "FAIL" else: aggregate = "PASS"`. Therefore, when `clients` is `FAIL` and `conversations` is `CANNOT-VERIFY`, the aggregate verdict is `CANNOT-VERIFY` (exit code `3`), not `FAIL` (exit code `1`).
3. **Mini Organ Installation Boundary (`REPORT.md:31-32, 118-120`, `ADVERSARY-FINDINGS.md:98-100`):**
   - **F:** Mini's installed verifier, payload (`scripts/restore_drill/run_drill.sh`), role scanner (`scripts/restore_drill/role_scanner.py`), wrapper (`~/scripts/mini-restore-drill.sh`), and plist (`~/Library/LaunchAgents/com.nuzantara.restore-drill.plist`) execute the files on Mini's local disk (`$HOME/nuzantara`), which are pinned at base `3fe0dfc4...`. Merging a PR to GitHub `main` does **not** install anything on Mini, and the `NA-7` operator verifies those 6 installed pins before running.
4. **Repository Schema & Verifier Facts (`scripts/ci/restore_drill_verify.py`, `migrations_v2`):**
   - **F:** On base commit `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`, `clients.required_columns` (`scripts/ci/restore_drill_verify.py:113-120`) omitted `"lead_metadata"`, whereas `_CLIENTS_VIOLATIONS_SQL` (`lines 225-227`) queries `lead_metadata`. The Wave 7 candidate patch adding `"lead_metadata"` to `clients.required_columns` was reviewed and signed `LGTM` in `FINAL-BLUE-GATE.json:108,116`, with the explicit finding that because `clients` scored `FAIL` (`VIOLATION: 1`) on the real run, `lead_metadata` existed in the restored backup (`FINAL-BLUE-GATE.json:117`, `REPORT.md:66-67`).
   - **F:** On base commit `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`, `_CONVERSATIONS_VIOLATIONS_SQL` implemented `CREATE OR REPLACE FUNCTION pg_temp.try_jsonb_array(text) RETURNS boolean` and called `pg_temp.try_jsonb_array(messages)`. On production, `conversations` was skipped during the read-only query-shape check because `_CONVERSATIONS_VIOLATIONS_SQL` creates a temporary function (`STATE.json:49`, `REPORT.md:40-41`).
   - **F:** In PostgreSQL 17, `pg_temp.try_jsonb_array(text)` is only defined for `text` (and `varchar` via implicit cast). For a `jsonb` or `json` column, the cast to `text` is assignment-only (`castcontext = 'a'`), so `pg_temp.try_jsonb_array(messages)` fails function resolution (`SQLSTATE 42883`). Conversely, `pg_input_is_valid(messages::text, 'jsonb')` uses an explicit `::text` cast and built-in PostgreSQL 16+ validation, succeeding on `jsonb`, `json`, `text`, and `varchar` without DDL.

### 2.2 Inferences (`I`)

1. **I:** In `restore_drill_verify.py:391-428`, `clients` only reaches `status == "FAIL"` when `missing_cols` is empty (`lead_metadata` present in `information_schema.columns` once `lead_metadata` is in `required_columns`), `row_count` is measured, and all declared `checks` (`client_type_unknown`, `lead_metadata_not_object`) are present in `measurement["violations"]` with integer values (`>= 0`).
2. **I:** Because `apps/backend-rag/backend/db/migrations_v2/243_jsonb_string_scalar_organism_wide_backfill.sql:381` and `apps/backend-rag/backend/app/routers/conversations.py:258,531` target `public.conversations.messages` as `jsonb` in production while `143_legacy_conversations.sql:18` declares `messages TEXT`, a restored production backup whose `conversations.messages` column is `jsonb` (or `json`) will fail the base `_CONVERSATIONS_VIOLATIONS_SQL` (`try_jsonb_array(text)`) with `SQLSTATE 42883` and cause `fetch_live` (`restore_drill_verify.py:345-353`) to leave `measurement["violations"]` unset, producing `conversations: CANNOT-VERIFY` (`UNMEASURED_CHECK: 1`).

### 2.3 Unknowns (`U`)

1. **U (`CONVERSATIONS_UNMEASURED_CHECK_CAUSE_UNOBSERVED_ON_BACKUP`):** Because `REAL-RUN-RECEIPT.json:72,75` did not export raw errors or logs (`rows_counts_and_raw_errors_exported: false`), the exact PostgreSQL error emitted when `_CONVERSATIONS_VIOLATIONS_SQL` ran against the restored backup on `2026-10-15T03:00:43Z` was not directly observed (`REPORT.md:125-126`).
2. **U (`CLIENTS_VIOLATION_SUBCHECK_UNOBSERVED_ON_BACKUP`):** Which `clients` invariant check (`client_type_unknown` vs `lead_metadata_not_object`, or `row_count` floor) produced `reason_classes: {"VIOLATION": 1}` in `REAL-RUN-RECEIPT.json:48-53` is unobserved (`REPORT.md:125-126`).
3. **U (`EFFECTIVE_MINI_LAUNCHD_SCHEDULE_AND_ENV_OVERRIDES`):** The effective launchd calendar schedule and any runtime `RESTORE_DRILL_*` environment overrides in Mini's user launchd domain are unobserved (`LEAD-DELTA.json:26`).

---

## 3. Final Design & Executed Within-Scope Changes

All edits are strictly inside B01's owned perimeter (`scripts/ci/restore_drill_verify.py`, `scripts/tests/test_restore_drill_verify.py`, and `research/operations/udb-wave8/B01/**`):

1. **`scripts/ci/restore_drill_verify.py`:**
   - Added `"lead_metadata"` to `clients.required_columns` (`lines 111-124`) so a restore missing `lead_metadata` is caught by the required-column guard rather than failing `_CLIENTS_VIOLATIONS_SQL`.
   - Kept `_CLIENTS_VIOLATIONS_SQL` (`lines 217-225`) **strict and unchanged** (`client_type NOT IN ('individual','company')` and `lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) <> 'object'`), per `B01-F3` and `DUX-CONSOLIDATION.md:52-53`.
   - Replaced `_CONVERSATIONS_VIOLATIONS_SQL` (`lines 204-215`) with a DDL-free, dual-type (`JSONB` / `JSON` / `TEXT`) query that preserves `NULL` semantics (`B01-F4`):
     ```sql
     SELECT jsonb_build_object(
       'messages_not_json_array',
       (SELECT count(*) FROM conversations
          WHERE messages IS NOT NULL
            AND CASE
              WHEN pg_input_is_valid(messages::text, 'jsonb')
                THEN jsonb_typeof((messages::text)::jsonb) <> 'array'
              ELSE true
            END)
     );
     ```
2. **`scripts/tests/test_restore_drill_verify.py`:**
   - Added `test_clients_missing_lead_metadata_skips_violations_query_and_names_missing_column`
   - Added `test_fail_plus_unmeasured_check_gives_cannot_verify_aggregate` (`B01-F2`, Guilt Case 4)
   - Added `test_conversations_and_clients_sql_invariants` (`B01-F3`, `B01-F4`)
3. **`research/operations/udb-wave8/B01/b01_recovery_adapter.py` & `test_b01_recovery_adapter.py`:**
   - Stdlib-only adapter verifying pinned input SHA-256 digests, membership-testing `consumer_id` against the 6,030-lead universe (`consumer-matrix.csv` + `LEAD-DELTA.json`), emitting `b01-recovery-instances.json` in strict `CONTRACT-CONVENTIONS.md` 19-key + `x_` format, and implementing `run_synthetic_pg17_suite()` for the 4 adversary guilt cases + innocence proofs over a private Unix-socket throwaway PG17 cluster.
4. **`research/operations/udb-wave8/B01/RESTORE-ADMISSION-PROPOSAL.md`:**
   - Historical proposal only. The later owner continuation already admits independently gated installation and exactly one existing-backup restore; it admits no client-row repair or stage amendment. Current execution follows the reconciled `PROPOSAL.md` and the fresh exact-head/package gates.

---

## 4. Sibling Contract Record & Historical Restore References (`CONTRACT-CONVENTIONS.md`)

### 4.1 Primary B01 Recovery Record (`runtime_mini_46522da0ef79d3aa7422ca41`)

Frozen-source snapshot emitted by `b01_recovery_adapter.py` into `research/operations/udb-wave8/B01/b01-recovery-instances.json`. Its permission-related unknown strings describe the frozen input state; they do not revoke the later conditional owner consent in the current proposal. The installed bytes and new run remain unproved:

- `consumer_id`: `"runtime_mini_46522da0ef79d3aa7422ca41"` (verbatim 6030th lead in `LEAD-DELTA.json:7`)
- `operation_id`: `"UNASSIGNED_B05"`
- `store_id`: `"unknown:unknown:unknown"` (`STORE_ID_PROPOSED:pg:mini:nuzantara-pg-drill/public` in `unknowns`)
- `source_version`: `"8061c88e0c43dd42e735fd012f9ed072df3ef3d6"`
- `evidence_timestamp`: `"2026-10-15T03:02:11+00:00"` (`REAL-RUN-RECEIPT.json:32`)
- `evidence_sha256`: `"9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d"` (`REAL-RUN-RECEIPT.json`)
- `status`: `"BLOCKED"`
- `unknowns`: `["OPERATION_ID_PENDING_B05", "STORE_ID_PROPOSED:pg:mini:nuzantara-pg-drill/public", "CONVERSATIONS_UNMEASURED_CHECK_CAUSE_UNOBSERVED_ON_BACKUP", "CLIENTS_VIOLATION_SUBCHECK_UNOBSERVED_ON_BACKUP", "MINI_CANDIDATE_INSTALLATION_NOT_ADMITTED", "OWNER_CONSENT_EXHAUSTED_FOR_NEW_REAL_BACKUP_RUN", "DATA_OWNER_RULING_REQUIRED_ON_CLIENTS_VIOLATION"]`

### 4.2 Five Historical Restore Source References (`LEAD-DELTA.json:48-54`, Reconciled by `B03`)

Per `REPORT.md:94-97` and `LEAD-DELTA.json:48-54`, the 5 historical restore source references retained in `consumer-matrix.csv` are:

1. `src_307bea3dfb94ec31` (`.github/workflows/restore-drill.yml`, `consumer-matrix.csv:25`)
2. `src_d073f505ff1671ad`
3. `src_def7a4c288a552af`
4. `src_cdf3ae5e4ecf861c`
5. `src_2f350566b97aee80`
   `b01_recovery_adapter.py` resolves all 5 verbatim from `consumer-matrix.csv` into `b01-recovery-summary.json`.

---

## DUX-REQUESTS

Per `DUX-NOTE-SYNTHESIS.md:24-27`, the BLUE Dux is requested to run the following commands from the worktree root (`~/nuzantara/.worktrees/db-udb-b01-recovery`) to produce the B01 execution receipts:

### `DUX-REQ-B01-10` — Run Verifier Unit Test Suite (`scripts/tests/test_restore_drill_verify.py`)

```bash
pytest -q scripts/tests/test_restore_drill_verify.py
```

### `DUX-REQ-B01-11` — Run B01 Recovery Adapter & Contract Conventions Test Suite

```bash
pytest -q research/operations/udb-wave8/B01/test_b01_recovery_adapter.py
```

### `DUX-REQ-B01-12` — Generate B01 Contract Artifacts & Run Throwaway PG17 Guilt/Innocence Suite

```bash
python3 research/operations/udb-wave8/B01/b01_recovery_adapter.py \
  --out-dir research/operations/udb-wave8/B01 \
  --synthetic-pg-out research/operations/udb-wave8/B01/dux-requests/SYNTHETIC-PG17-B01.json
```

- **What this produces:**
  1. `research/operations/udb-wave8/B01/b01-recovery-instances.json` (19-key + `x_` contract instance for B05's validator).
  2. `research/operations/udb-wave8/B01/b01-recovery-summary.json` (verified receipt summary, 5 historical restore references, and candidate SHA-256 pins).
  3. `research/operations/udb-wave8/B01/dux-requests/SYNTHETIC-PG17-B01.json` (throwaway PG17 socket proof covering all 4 adversary guilt cases + dual-type `JSONB`/`TEXT` innocence cases; per `DUX-CONSOLIDATION.md:47-48`, throwaway PG17 on a private socket with no production data is a test, not a native exercise).

### `DUX-REQ-B01-13` — Record SHA-256 Digests of All B01 Deliverables

```bash
shasum -a 256 \
  scripts/ci/restore_drill_verify.py \
  scripts/tests/test_restore_drill_verify.py \
  research/operations/udb-wave8/B01/b01_recovery_adapter.py \
  research/operations/udb-wave8/B01/test_b01_recovery_adapter.py \
  research/operations/udb-wave8/B01/DEFINITIVE-SYNTHESIS.md \
  research/operations/udb-wave8/B01/RESTORE-ADMISSION-PROPOSAL.md \
  research/operations/udb-wave8/B01/RESULT.json \
  research/operations/udb-wave8/B01/PR_BODY.md
```

### `DUX-REQ-B01-14` — Optional Same-Admitted Re-Run of `NA-3` and `NA-4` (Metadata Only)

- If the Dux desires a fresh timestamped confirmation that Mini's installed restore organ (`~/scripts/mini-restore-drill.sh`, `~/Library/LaunchAgents/com.nuzantara.restore-drill.plist`, `$HOME/nuzantara/scripts/restore_drill/*`, and `~/.organism/last_seen/mini.restore_drill.json`) remains unchanged at its 6 base pins since `2026-10-15T03:02:11+00:00`, request the same-admitted `NA-3` (Mini restore-organ metadata probe) and `NA-4` (Mini restore-log classifier) into a new receipt subfolder per `DUX-NOTE-SYNTHESIS.md:52` and `DUX-CONSOLIDATION.md:35-38`.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION` for this file's bytes with SHA256 `625fac618adf89018c64493f5bd5e61fc8ab57e863de28125b10969d8a50f699` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (addendum) apply its findings and were not re-reviewed.
