---
adversarial_review: codex
reviewed_source_sha256: "ffa69c4e6f4b1b70ad47470345aa91dc8a1a5ddeabcdd89f2377b88e5e601e31"
review_disposition: HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED
---

# B01 Restore Admission & Owner Decision Proposal (`RESTORE-ADMISSION-PROPOSAL.md`)

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

> **STATUS: REVIEWABLE PROPOSAL ONLY — NOT AN APPROVAL OR ASSUMED CONSENT.**
> No live organ installation, no client-row mutation, and no real-backup restore run is authorized by this document. Execution requires explicit sign-off by **Zero (Owner)** on the three decisions below.

- **Campaign ID:** `universal-db-wave8-20261015`
- **Block ID:** `B01` — Real-backup recovery
- **Target Organ / Consumer ID:** `runtime_mini_46522da0ef79d3aa7422ca41` (`com.nuzantara.restore-drill` on `Mini`, `LEAD-DELTA.json:7-9`)
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Prior Run Baseline:** `REAL-RUN-RECEIPT.json` (`sha256: 9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d`), started `2026-10-15T03:00:43.925327+00:00`, completed `2026-10-15T03:02:11+00:00` (`elapsed_seconds: 87.658`), under single-use authorization `APPROVED_ONE_EXISTING_JOB` (`STATE.json:40`), which is **exhausted** (`BATTLE.md:4,13`, `ASTRA-ADVICE.md:7`).

---

## 1. Why Three Owner Decisions Are Required (`ADVERSARY-FINDINGS.md:129`, `DUX-CONSOLIDATION.md:51-57`)

In the prior authorized run (`REAL-RUN-RECEIPT.json:37-73`, `STATE.json:91-127`), the 5 declared invariants scored:

1. `conversations`: `status = "CANNOT-VERIFY"`, `reason_classes = {"UNMEASURED_CHECK": 1}`
2. `clients`: `status = "FAIL"`, `reason_classes = {"VIOLATION": 1}`
3. `visa_decisions`: `status = "PASS"`, `reason_classes = {}`
4. `events_outbox`: `status = "PASS"`, `reason_classes = {}`
5. `visa_decision_retention_policies`: `status = "PASS"`, `reason_classes = {}`

- **Aggregate:** `CANNOT-VERIFY` (`rows_counts_and_raw_errors_exported: false`, `raw_report_sha256: 1d368c2d16d32a0834bb7d120d75005423227b77239107b1dc1873f8140b5744`).

Closing `B01` requires every one of the 5 invariants to be **measured and satisfied (`PASS`)** on a fresh admitted real-backup run (`BATTLE.md:4,13`). Three distinct authority boundaries block closure today:

### Decision 1 — Consent to Install the Reviewed Candidate on Mini (`B01-F5`)

- **Fact:** Merging the B01 PR into `origin/main` does **not** update the live restore organ on `Mini`. The wrapper (`~/scripts/mini-restore-drill.sh`) resolves `$HOME/nuzantara/scripts/restore_drill/run_drill.sh`, which invokes `$REPO_ROOT/scripts/ci/restore_drill_verify.py` at its currently installed revision (`3fe0dfc4...`, `REPORT.md:31-32`, `STATE.json:24-30`, `ADVERSARY-FINDINGS.md:98-100`).
- **Fact:** The admitted one-run operator (`NA-7`) verifies all 6 installed source pins on Mini before triggering `com.nuzantara.restore-drill` (`REAL-RUN-RECEIPT.json:9`).
- **Decision Requested from Zero:**
  - Authorize updating `$HOME/nuzantara/scripts/ci/restore_drill_verify.py` (and `scripts/tests/test_restore_drill_verify.py`) on `Mini` to the merged, Opus-5.5-gated commit SHA, and updating the expected `verifier` SHA-256 pin in the `NA-7` operator wrapper before triggering the next run.

### Decision 2 — Data-Owner Ruling on the `clients` Violation (`B01-F3`)

- **Fact:** Per Dux ruling (`DUX-CONSOLIDATION.md:52-53`), the `clients` invariant in `scripts/ci/restore_drill_verify.py:221-229` (`client_type NOT IN ('individual','company')` and `lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) <> 'object'`) **stands unchanged**. Relaxing the predicate to force green is rejected (`REPORT.md:59`, `ADVERSARY-FINDINGS.md:89-93`), and B01 is forbidden from repairing client rows (`BATTLE.md:4,13`).
- **Fact:** Because `REAL-RUN-RECEIPT.json:48-53` recorded `clients: FAIL` (`VIOLATION: 1`), the restored production backup contains at least one row violating `client_type_unknown` or `lead_metadata_not_object`. Without a data remediation or schema ruling, re-running against the same backup data after fixing `conversations` will change the aggregate verdict from `CANNOT-VERIFY` to `FAIL` (`clients: FAIL`), not `PASS`.
- **Decision Requested from Zero (Data Owner):** Choose one of:
  - **Option 2A (Authorize Non-PII Subcheck Attribution + Production Data Backfill in S2+ before Closure Run):**
    1. Authorize a boolean-only subcheck attribution (`client_type_unknown_nonzero: bool`, `lead_metadata_not_object_nonzero: bool` — exporting **no** row values and **no** integer counters) on the restored backup or read-only production catalog.
    2. Authorize a separate, audited production data migration (outside B01, which may not repair client rows) to remediate the offending `clients` row(s) (for example, extending `243_jsonb_string_scalar_organism_wide_backfill.sql:402-420` to `clients.lead_metadata` if double-encoded string scalars are present, or normalizing legacy `client_type` values), wait for a fresh Tigris dump (`nuzantara-fly-YYYYMMDD-HHMM.sql.gz`), and then run Decision 3.
  - **Option 2B (Run Candidate Now to Prove `conversations` Measurement, Honest `FAIL` on `clients`):**
    1. Authorize Decision 1 + Decision 3 immediately against the current backup to prove `conversations` transitions from `CANNOT-VERIFY` (`UNMEASURED_CHECK: 1`) to `PASS` and all 5 relations are measured, while keeping `B01` open (`block_closed: false`) with an honest `FAIL` on `clients` until Option 2A is completed.

### Decision 3 — Consent for Exactly One Out-of-Cadence Real-Backup Run on Mini (`B01-F6`)

- **Why "Observing the Next Scheduled Run" Cannot Close B01 in This Campaign (`B01-F6`):**
  1. The prior sidecar error timestamp in `STATE.json:32-38` is `2026-10-12T15:07:50+00:00` (Monday `23:07` UTC+8), so the effective launchd schedule on Mini is not established to fire within the 24-hour campaign window (`BATTLE.md:23`).
  2. Without Decision 1 (candidate installation on Mini), any scheduled launchd execution runs the old base bytes (`3fe0dfc4...`) and reproduces `conversations: CANNOT-VERIFY`.
- **Decision Requested from Zero:**
  - Grant single-use consent (`APPROVED_ONE_CANDIDATE_JOB_B01`) for **exactly one** out-of-cadence execution of `com.nuzantara.restore-drill` on `Mini` via the source-reviewed `NA-7` operator after Preconditions P1–P4 below are satisfied.

---

## 2. Preconditions (Must All Be Green Before Launch)

| ID     | Precondition                                                                                                                                                                                                                                                                       | Verification Artifact / Gate                                         |
| :----- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------- |
| **P1** | Candidate `scripts/ci/restore_drill_verify.py` and `scripts/tests/test_restore_drill_verify.py` pass unit tests (`pytest -q scripts/tests/test_restore_drill_verify.py` and `pytest -q research/operations/udb-wave8/B01/test_b01_recovery_adapter.py`).                           | Dux receipt for `DUX-REQ-B01-10` and `DUX-REQ-B01-11` (`exit == 0`). |
| **P2** | Throwaway synthetic PostgreSQL 17 suite passes all 4 adversary guilt cases + dual-type (`JSONB` + `TEXT`) innocence cases over a private Unix socket (`listen_addresses=''`).                                                                                                      | Dux receipt for `DUX-REQ-B01-12` (`all_passed == true`).             |
| **P3** | Fresh independent `claude-opus-5-5` (`xhigh`) on-disk gate signs `LGTM` on the B01 candidate and PR merges to `main`.                                                                                                                                                              | Signed gate receipt + merged commit SHA on `main`.                   |
| **P4** | **Owner Decisions 1, 2, and 3** are explicitly signed by Zero; Mini checkout `$HOME/nuzantara` is updated to the merged commit SHA; `NA-3` confirms all 6 installed source pins match and no `/tmp/nuzantara-restore-drill.*` workdir or `nuzantara-pg-drill` container is active. | `NA-3` pre-run metadata receipt (`source_pin_matches == 6`).         |

---

## 3. Exact Launch and Observation Commands (Admitted Operator Route Only)

1. **Pre-Run Metadata & Pin Verification (`NA-3`):**
   - Execute the admitted `NA-3` Mini restore-organ metadata probe on `Mini` (checking `~/Library/LaunchAgents/com.nuzantara.restore-drill.plist`, `~/scripts/mini-restore-drill.sh`, `$HOME/nuzantara/scripts/restore_drill/run_drill.sh`, `$HOME/nuzantara/scripts/restore_drill/role_scanner.py`, `$HOME/nuzantara/scripts/restore_drill/Dockerfile`, and `$HOME/nuzantara/scripts/ci/restore_drill_verify.py` against the updated pin set, plus `~/.organism/last_seen/mini.restore_drill.json` timestamp).
2. **Single Out-of-Cadence Job Trigger & Bounded Observation (`NA-7`):**
   - Invoke the source-reviewed `NA-7` one-run operator on `Mini`, which:
     1. Re-verifies all 6 source pins before launch (`source_pin_matches == 6`).
     2. Triggers `launchctl kickstart gui/$(id -u)/com.nuzantara.restore-drill` **exactly once**.
     3. Polls `~/.organism/last_seen/mini.restore_drill.json` and container state at 30s intervals up to the bounded timeout without opening any private `/tmp/nuzantara-restore-drill.*` file descriptors (`private_report_fd_observed: false`).
     4. Classifies theverifier summary into relation `status` (`PASS` / `FAIL` / `CANNOT-VERIFY`) and `reason_classes` tallies (`VIOLATION`, `UNMEASURED_CHECK`, `MISSING_COLUMN`, `BELOW_FLOOR`, `MISSING_RELATION`, `QUERY_ERROR`) plus `raw_report_sha256`.
3. **Post-Run Log Classification (`NA-4`):**
   - Execute the admitted `NA-4` Mini restore-log classifier to confirm container cleanup (`lingering_containers == 0`) and sidecar status without exporting raw log lines.

---

## 4. Strict Output Boundary (Privacy & Security Guarantee)

Per Builder Contract 4, SYMBIOSIS Law 2 (UU PDP), and `REPORT.md:124-125`:

- **Never exported from Mini:**
  - Zero client rows or column values from `clients`, `conversations`, `visa_decisions`, `events_outbox`, or `visa_decision_retention_policies`.
  - Zero raw SQL error strings or `restore.log` lines (`scripts/restore_drill/run_drill.sh:3,240`).
  - Zero application row counts or check violation integer counters (`rows_counts_and_raw_errors_exported: false`, `REAL-RUN-RECEIPT.json:72`).
  - Zero credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `DRILL_PASSWORD`).
- **Permitted in the Receipt (`REAL-RUN-RECEIPT.json` shape):**
  - Execution timestamps (`started_at`, `timestamp`), `elapsed_seconds`, `source_pin_matches` (`int`), `private_report_fd_observed` (`false`).
  - `verifier_summary.aggregate` (`PASS` | `FAIL` | `CANNOT-VERIFY`).
  - Per-relation `{"relation": <name>, "status": <status>, "reason_classes": {<class>: <count_of_reasons>}}` for the 5 invariants.
  - `raw_report_sha256`, `stderr_sha256`, `operator_sha256`, `metadata_dependency_sha256`, `bundle_sha256`.

---

## 5. Success Criteria, Abort / Rollback, and Decision Authority

- **Success Criteria for `B01` Closure (`block_closed: true`):**
  1. `source_pin_matches == 6` on the reviewed candidate revision.
  2. All **5** declared invariants (`conversations`, `clients`, `visa_decisions`, `events_outbox`, `visa_decision_retention_policies`) are **measured** (`UNMEASURED_CHECK` absent on every relation) and report `status == "PASS"` (`reason_classes == {}`).
  3. `verifier_summary.aggregate == "PASS"`, `sidecar.status == "ok"`, and `rows_counts_and_raw_errors_exported == false`.
- **Abort & Rollback Procedure:**
  - **Automatic In-Run Abort:** `scripts/restore_drill/run_drill.sh:54-75, 278-303` enforces a 30-minute watchdog (`TIMEOUT_SECONDS=1800`) and an `EXIT`/`INT`/`TERM` trap that terminates the worker process group, removes any container labeled `com.nuzantara.restore-drill.run=nuzantara-restore-drill.*`, and deletes `/tmp/nuzantara-restore-drill.*` (`mode 0700`).
  - **Manual Abort:** If operator observation exceeds 300s or detects an anomaly, terminate the job via `launchctl kill SIGTERM gui/$(id -u)/com.nuzantara.restore-drill` and verify `docker ps -aq --filter "name=nuzantara-pg-drill"` is empty and `/tmp/nuzantara-restore-drill.*` is removed.
  - **Code Rollback on Mini:** If the candidate verifier exhibits any regression on Mini, reset `$HOME/nuzantara` back to `3fe0dfc4...` and re-verify the original 6 pins with `NA-3`.
- **Who Decides:**
  - **Zero (System & Data Owner):** Sole authority for Decisions 1, 2, and 3.
  - **Fresh Independent `claude-opus-5-5` (`xhigh`) Gate:** Sole authority for on-disk candidate verification prior to merge/install.
  - **Appointed Temporary BLUE Dux (`claude-opus-5-5` `xhigh` on `pro`):** Coordinates gate dispatch, PR release, and admitted `NA-3`/`NA-4`/`NA-7` execution once Zero grants consent.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED` for this file's bytes with SHA256 `ffa69c4e6f4b1b70ad47470345aa91dc8a1a5ddeabcdd89f2377b88e5e601e31` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (addendum) apply its findings and were not re-reviewed.
