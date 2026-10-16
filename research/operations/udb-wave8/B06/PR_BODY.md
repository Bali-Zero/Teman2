---
adversarial_review: codex
reviewed_source_sha256: "03b6f11a4cc00c3e8eb537e04100a4abb55e3eaed9b54ba14bb272e704883e6d"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# research(udb-wave8): B06 business-domain paths — full source inventory, actual B05 submissions, explicit coverage gaps

## Current package status (2026-10-16)

Current source tests: 27 passed (18 preserved legacy tests plus 9 inventory tests). All 6029 C09 IDs and 4231 public source paths are retained; 1566 rows have static anchors and 4463 have no trace. The 21001 additional syntax signals pass actual B05 schema validation but do not establish operation semantics or business membership. Independent source execution is recorded; document and final commit gates remain incomplete. block_closed:false; production adoption is not claimed. Original deadline elapsed. This package is prepared for review; no final committed-head PASS is asserted.

Block **B06** (`D04`–`D10`) of campaign `universal-db-wave8-20261015`. Status `PARTIAL`, `block_closed: false`. Authoritative evidence: [`RESULT.json`](RESULT.json).

## What ships

- `b06_domain_paths.py` — builds the 21 D04–D10 operation instances in the frozen conventions shape with `x_` extensions, verifies pinned receipts, keeps source-taxonomy counters separate from business-inventory labels, and adds an explicit opt-in `--metadata-fixture` CLI that reports the processed and source byte identities separately.
- `domain-operation-instances.json` — the 21 records, semantically identical to the pre-repair artifact.
- `test_b06_domain_paths.py` — 18 offline tests over committed files only, no skips (e.g. `test_pinned_csv_source_and_prefix_census_parity`, `test_tampered_receipt_counter_fails_census_compare`, `test_missing_projection_fails_instead_of_skip`, `test_clean_checkout_fixture_cli_labels_both_byte_identities`).
- `fixtures/` — `consumer-matrix-metadata.csv` (6029-row, 11-field metadata projection; processed sha256 `dfe7c0b1…` deliberately distinct from source `c09e1432…`; no raw census copy), `manifest.json`, and the producer receipts with their commands:
  - `fixtures/receipts/DUX-REQ-B06-01.out` sha256 `1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb`
  - `fixtures/receipts/DUX-REQ-B06-03.out` sha256 `e30e1c44d8e6ab797e20dc7722eb27854cc1e04a2feab325db2d0a1f3c9d10aa`
- Synthesis documents with a 2026-10-16 addendum; `.secrets.baseline` entries for exact digest findings only.

## Findings

- **Prefix scope (DUX-REQ-B06-03):** 683 rows = 504 `NOT_ENRICHED_THIS_PHASE` + 179 `MATCHED_SOURCE_PATH_ONLY; ACTOR_IDENTITY_UNRESOLVED`, asserted equal to the census recomputed from the committed fixture.
- **Withdrawn:** the earlier 527/155/1 split, a 2,608-row subset of seven business labels in `domain_hint` (none of the seven labels occurs in the producer counters), and a "parent run 3 passed / 8 failed" claim without receipt. Earlier text also swapped the two receipt hashes; the values above are the pinned ones the tests enforce.
- **NAGA:** the operation is grounded in `services/naga` source (`test_naga_instance_is_grounded_in_actual_save_session_source`).

## Explicit missing evidence (`block_closed: false`)

1. Runtime role resolution for the 683 prefix rows (B04).
2. Canonical `operation_id` for the 21 `UNASSIGNED_B05` instances (B05).
3. Restore-drill measurement for `clients`/`conversations` and B06 tables (B01/B07).
4. Live aggregates DUX-REQ-B06-10/11/12: not admitted, not run.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `REVIEWED_PARTIAL_WITH_BLOCKERS`; this file's reviewed bytes had SHA256 `03b6f11a4cc00c3e8eb537e04100a4abb55e3eaed9b54ba14bb272e704883e6d`. Its findings (NAGA source, 2,608 vs 683 premise, adopt actual receipts) are applied here. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. This revision was not re-reviewed.


Preparation: original Gemini block work; current source integration and documentation reconciliation by Codex under the owner exception.

## 2026-10-16 bounded inventory completion

`b06_inventory.py` captures and consumes `fixtures/source-inventory.json.gz` with pinned provenance. Original C09 bytes are processed locally; only the minimal projection is published. All 6029 canonical IDs are retained: 4231 public-code paths, 1566 rows with static call anchors, 4463 rows without an operation trace, and 21001 syntax call signals.

Seven families are overlapping public-path candidate sets, not business-domain denominators. Generic calls, loops, exception handlers and consumer-level store bindings do not establish persistence, retries, failure behavior or effective targets. Those semantics remain UNKNOWN. The original 21 detailed examples remain separate historical evidence and do not establish full coverage.

Actual committed B05 validation is recorded in B05-VALIDATION.json. Principal, role, recovery and operation IDs remain unresolved. The parent reported at 2026-10-16T07:39Z that a secure owner-only credential file exists but zero canonical nuzantara_readonly DSN candidates are present and both observer DSN variables are unset. This is an access blocker, not a B06 native query.

`block_closed:false` remains binding. Required follow-up: establish business-family membership, inspect untraced and dynamic paths, prove effective call targets/effects/failure/retry behavior, obtain admitted observer access and satisfy dependent recovery evidence. No operational closure is claimed.

Bites: B06 inventory consumer loads the pinned projection, reconciles 6029 IDs, reports seven candidate sets and retains untraced/semantic gaps; actual B05 validation and clean reproduction receipts prove the prepared behavior.
