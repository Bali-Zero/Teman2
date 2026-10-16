---
adversarial_review: codex
reviewed_source_sha256: "d0a1438f4b7118e64096547f6aeabea174ba9c6bc93ecc3d490513a06a387916"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# B01 Analysis — Real-Backup Recovery (`mini.restore_drill`)

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
- **Stage:** `ANALYSIS` (read-only analysis; no code mutations, no native probes, no real-backup execution)

---

## 0. Scoped Frozen Inputs Verification

All scoped inputs enumerated in `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:1-47` and the block notes were read directly from disk:

| Input Artifact          | Path                                                          | Verified SHA-256 / Ref                                             | Role in B01                                                                     |
| :---------------------- | :------------------------------------------------------------ | :----------------------------------------------------------------- | :------------------------------------------------------------------------------ |
| `DUX-NOTE-ANALYSIS.md`  | `research/operations/udb-wave8/B01/DUX-NOTE-ANALYSIS.md:1-31` | Base `8061c88e`                                                    | Stage mandate, boundaries, `DUX-REQUESTS` protocol                              |
| `BATTLE.md`             | `research/operations/udb-wave8/B01/BATTLE.md:1-31`            | Base `8061c88e`                                                    | Campaign/block contract, sibling schema, stop rules                             |
| `REPORT.md`             | `.agent-receipts/udb-wave8-inputs/REPORT.md:1-146`            | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` | Wave 7 executive report & Section 5 recovery state                              |
| `STATE.json`            | `.agent-receipts/udb-wave8-inputs/STATE.json:1-134`           | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` | Wave 7 organ inventory, synthetic PG vs real run state                          |
| `FINAL-BLUE-GATE.json`  | `.agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json:1-128` | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` | Wave 7 gate verdict (`HOLD`) & candidate patch assessment                       |
| `REAL-RUN-RECEIPT.json` | `.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:1-84` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | Authorized one-run real-backup receipt (`FAIL`)                                 |
| `research-lines.csv`    | `.agent-receipts/udb-wave8-inputs/research-lines.csv:1-20`    | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` | `D14` Recovery, retention and security rubric                                   |
| `ASTRA-ADVICE.md`       | `.agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md:1-12`       | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` | Strategic priorities (`B01` #4: `clients` FAIL + `conversations` CANNOT-VERIFY) |
| `consumer-matrix.csv`   | `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv:1-120`  | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | Cross-consumer operation matrix for `clients` and `conversations`               |

---

## 1. Verified Facts and Limits

### 1.1 Recovery consumer and source boundary

The registered organ is `mini.restore_drill`, driven by launchd label
`com.nuzantara.restore-drill` on Mini. Its source chain is
`infra/launchagents/wrappers/mini-restore-drill.sh` →
`scripts/restore_drill/run_drill.sh` → `scripts/ci/restore_drill_verify.py`.
A repository source reference does not prove which bytes are installed. The
independently reviewed run package must pin and compare the installed wrapper,
payload, verifier, role scanner and Dockerfile before the authorized run.
The stock payload's cleanup behavior makes existing-lock and existing-container
refusal mandatory; preflight uncertainty is a refusal, not permission to clean up
another run.

### 1.2 What the prior real-backup receipt proves

The pinned `REAL-RUN-RECEIPT.json` has SHA-256
`9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d`.
Its request event started at `2026-10-15T03:00:43.925327+00:00`; the
terminal sidecar timestamp is `2026-10-15T03:02:11+00:00`.
It reports exactly five relation outcomes:

| Relation                           | Status          | Sanitized reason class |
| ---------------------------------- | --------------- | ---------------------- |
| `conversations`                    | `CANNOT-VERIFY` | `UNMEASURED_CHECK`     |
| `clients`                          | `FAIL`          | `VIOLATION`            |
| `visa_decisions`                   | `PASS`          | None                   |
| `events_outbox`                    | `PASS`          | None                   |
| `visa_decision_retention_policies` | `PASS`          | None                   |

The verifier aggregate is `CANNOT-VERIFY`. The wrapper process exit and the
verifier verdict are separate observations. The receipt supplies no owner-consent
fields, backup filename or compressed-backup size. It identifies neither the
violated `clients` subcheck nor the unmeasured `conversations` check's cause.
No additional relation outcome or installed-schema observation is inferred.

### 1.3 Source-backed hypotheses and strict invariants

A historical `pg_temp.try_jsonb_array(text)` query has DDL and type-resolution
failure modes. Repository migrations and writers motivate testing both text and
JSONB shapes; they do not establish the type in the restored backup.
The candidate uses a DDL-free PostgreSQL 17 query and tests innocent and guilty
JSONB/TEXT cases, including non-arrays and preserved SQL-NULL behavior.
A synthetic pass does not establish real-backup recovery.

The `clients` predicates remain strict:
`client_type NOT IN ('individual','company')` and
`lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) <> 'object'`.
Adding `lead_metadata` to required columns detects a missing column; it does not
repair a data violation. A faithful restore can preserve a pre-existing violation,
so a failed invariant alone proves neither corruption nor acceptable data.
No client-row repair or semantic weakening is admitted.

## 2. Consumer and Operation Identity

Use the canonical lead `runtime_mini_46522da0ef79d3aa7422ca41` from
`LEAD-DELTA.json`. The human-readable organ name is not a substitute consumer ID.
The adapter's frozen-source record has `operation_id: UNASSIGNED_B05`,
`store_id: unknown:unknown:unknown`, `status: BLOCKED`,
`source_version: 8061c88e0c43dd42e735fd012f9ed072df3ef3d6`, and the
receipt hash/timestamp above. Proposed store bindings remain in `unknowns`;
B04 and B05 must resolve them. A proposed operation name, role or store identifier
is not a verified deployment fact. The frozen receipt's historical permission
unknowns do not override the later owner consent described below.

## 3. Current Admission and Missing Evidence

The 2026-10-16 owner continuation admits boolean-only diagnostics, installation of
the independently gated candidate with reviewed pins, and exactly one isolated
restore of an existing backup. It does not admit a new backup, production client
queries, client-row repair, invariant weakening or a repeated restore. The prior
receipt is not an authorization record for this run.

Before that run, the Dux must reconcile the corrected commit and operational
package, obtain the fresh independent BLUE gate, release through required checks,
install only the admitted pins, and prove resource and lock/container preconditions.
The one-run reservation must be exclusive and durable. A repeat invocation,
pin mismatch, any lock, any existing canonical drill container, or unknown Docker
state must refuse execution. Cleanup may affect only resources owned by that run.

Still missing: actual installed-pin verification, the authorized fresh real-backup
receipt, named boolean-only diagnostic outcomes, and observed cleanup. B01 closes
only when all five strict invariants pass that admitted run. A failure remains a
failure. Deferring client remediation to S2 before B01 closure would cycle against
the unchanged S1 prerequisite and is not adopted.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION` for this file's bytes with SHA256 `d0a1438f4b7118e64096547f6aeabea174ba9c6bc93ecc3d490513a06a387916` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. The reconciled body is prepared after those reviewed bytes and still requires the fresh independent exact-head BLUE gate.
