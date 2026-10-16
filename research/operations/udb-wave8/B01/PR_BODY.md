---
adversarial_review: codex
reviewed_source_sha256: "e2a01275e71c64dcaaa422e5d602165e82a26d0c30cbff2a9d73a2dec151c3b1"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# fix(restore-drill): B01 measurable conversations check, strict clients guard, hermetic recovery evidence

Block **B01** (real-backup recovery) of campaign `universal-db-wave8-20261015`. Status `PARTIAL`, `block_closed: false`. Authoritative evidence: [`research/operations/udb-wave8/B01/RESULT.json`](research/operations/udb-wave8/B01/RESULT.json).

## What ships

- `scripts/ci/restore_drill_verify.py` — the `conversations` invariant becomes measurable without DDL (`pg_input_is_valid` on PostgreSQL 17, jsonb and text `messages`); the `clients` predicate stays strict and unchanged (`client_type` in individual/company, `lead_metadata` an object when present), and `lead_metadata` joins the required columns so a missing column reads CANNOT-VERIFY, never PASS.
- `scripts/tests/test_restore_drill_verify.py` — 27 tests.
- `research/operations/udb-wave8/B01/` — recovery adapter and contract records, 14 adapter tests, committed `fixtures/` (byte-identical copies of the sanitized prior-run receipt, campaign state and lead delta, plus a consumer-matrix projection labelled as a projection, see `fixtures/PROVENANCE.json`), synthesis documents with a 2026-10-16 addendum, and the restore admission proposal (historical, superseded by the addendum).
- `.secrets.baseline` entries for exact digest findings in these files only.

## Findings

- Last real-backup run (2026-10-15, 5 relations): aggregate CANNOT-VERIFY — `conversations` unmeasured, `clients` FAIL (violation), the other three PASS. No rows, counts or raw errors were exported.
- The synthetic throwaway PostgreSQL 17.11 suite (private socket, no TCP listener) passes all guilt and innocence cases.

## Explicit missing evidence (`block_closed: false`)

1. The owner-authorized single isolated restore with the installed candidate (consent 2026-10-16). Merging this PR is the install route; the run happens after the merge and the reviewed pin check, so its result cannot be carried by this diff.
2. `clients` must measure PASS on that run without any client-row change or predicate change; otherwise a data-owner proposal follows.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](research/operations/udb-wave8/B01/R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `REVIEWED_PARTIAL_WITH_BLOCKERS`; this file's reviewed bytes had SHA256 `e2a01275e71c64dcaaa422e5d602165e82a26d0c30cbff2a9d73a2dec151c3b1`. Its findings (historical run date and relation counts, fabricated consent fields and 12/12 acceptance, Option 2A dependency cycle, stale execution evidence) are applied by the addendum and this body. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. This revision was not re-reviewed.

Bites: `scripts/tests/test_restore_drill_verify.py` and `research/operations/udb-wave8/B01/test_b01_recovery_adapter.py`, shipped in this PR, exercise the verifier and the adapter from committed files only (41 passed, 0 skipped in a clean copy); the live consumer is the Mini restore drill (`scripts/restore_drill/run_drill.sh` → `scripts/ci/restore_drill_verify.py`), whose single authorized post-merge run is the observation that decides closure.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
