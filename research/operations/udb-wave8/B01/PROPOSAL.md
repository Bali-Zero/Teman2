---
adversarial_review: codex
reviewed_source_sha256: "7c1bfb03d900c686ddb9c9f820ebdc23fa0eb868155fbd9a495f64b47c0e7fc9"
review_disposition: HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED
---

# B01 Proposal — Real-Backup Recovery (`mini.restore_drill`)

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
- **Block ID:** `B01` — Real-backup recovery
- **Mission Colour & Gear:** `BLUE` · `GEAR3`
- **Host & Seat:** `[Mini]` · `gemini-4-argon` (`high`) — `EXTERNAL PREPARER, NO_DUX` (Appointed BLUE Dux: `claude-opus-5-5` `xhigh` on `pro`)
- **Worktree:** `~/nuzantara/.worktrees/db-udb-b01-recovery`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage:** `ANALYSIS` (Proposal for `EXECUTION` gate approval)

---

## 1. Candidate Development and Evidence Boundary

The candidate makes the `conversations` check DDL-free on PostgreSQL 17 and tests
text and JSONB inputs, non-array guilt cases and preserved NULL behavior. It adds
`lead_metadata` to the required-column guard while preserving both strict
`clients` predicates. It changes neither client rows nor the stock drill's
invariant policy.

The unit suite, adapter checks and disposable synthetic PostgreSQL evidence test
the implementation. They cannot establish installed bytes, restored schema,
real-backup health or permission to run. See `RESULT.json` for actual command
receipts and their scope; the prior real-backup receipt covers five relations and
has aggregate `CANNOT-VERIFY`, with `clients: FAIL`.

Check-level observation belongs to the separately admitted operator's private-report
boundary. This proposal does not authorize new counters in the stock run log,
raw report export, a production aggregate query, or a change to `run_drill.sh`.

## 2. Current Owner Consent and One-Run Admission

Owner continuation of 2026-10-16 grants boolean-only diagnostics, independently
gated installation with reviewed pins, and exactly one isolated restore of an
existing backup. No fresh consent request is needed for that scope. The frozen
prior-run receipt contains no consent fields and does not identify a backup file
or establish an exhausted authorization flag.

The BLUE Dux must complete this sequence:

1. Integrate the documentary and operator-safety corrections within the existing
   B01 correction budget. Reconcile old/new source hashes; regenerate the complete
   candidate and run-package manifests.
2. Obtain the fresh independent exact-head BLUE gate and admission for the exact
   operational package. Neither the earlier blocked gate nor a source-only review
   signs changed bytes.
3. Release the single original B01 PR through required checks, then install and
   verify only the admitted wrapper/payload/verifier/role-scanner/Dockerfile pins.
4. Check resources, any lock and the canonical container immediately before use.
   Unknown Docker state, a present lock/container or a pin mismatch refuses the
   launch. A durable exclusive reservation allows only one invocation; a second
   invocation must make no SSH or launch request.
5. Run the existing-backup job through the durable detached operator within the
   original deadline, including its watchdog and owned-resource cleanup. Export
   only safe statuses/check names and source digests.

No new backup, second restore, client-row repair, production client query, raw
log export or weaker invariant is authorized. A scheduled run is not a substitute
for the specifically admitted one-shot proof.

## 3. Acceptance and Dependency Boundary

Require a fresh real-backup receipt with all five strict relation invariants
passing, actual installed pins and observed owned-resource cleanup before marking
B01 closed. A synthetic all-pass case or merged PR does not satisfy that test.
If `clients` still fails, record it as failure and stop this run path without a
repeat or data repair.

The historical Option 2A idea of S2 remediation before B01 closure is not adopted:
the original S1 gate requires B01 closed before S2 starts. Any stage amendment
requires an actual owner decision; none is assumed here.

## 4. Disposition of Historical DUX Requests

`DUX-REQUEST-1` (production aggregate attribution) remains not admitted. Its
integer-count query and live-schema assertions are not part of this execution plan.
The authorized alternative is the admitted restore's boolean-only check
classification, without client rows, counts or raw query errors.

`DUX-REQUEST-2` was a historical request about entering execution, not a native
permission or an exemption from the current exact-head gate. Old proposed changes
to client semantics and new stock-log counters remain rejected.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED` for this file's bytes with SHA256 `7c1bfb03d900c686ddb9c9f820ebdc23fa0eb868155fbd9a495f64b47c0e7fc9` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. The reconciled body is prepared after those reviewed bytes and still requires the fresh independent exact-head BLUE gate.
