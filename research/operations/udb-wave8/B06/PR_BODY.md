## Summary

Completes the **DEFINITIVE SYNTHESIS + EXECUTION** deliverables for Universal DB Wave 8 Block `B06` (`D04`–`D10` business-domain paths) in `research/operations/udb-wave8/B06/`:

- Resolves all consolidated adversarial findings (`X1`–`X13` and `B06-F1`–`B06-F4`) from `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md`, `DUX-CONSOLIDATION.md`, and `DUX-TRIAGE-B01-B06.md`.
- Aligns `domain-operation-instances.json` (`21` deep domain operation instances, `3` per research line `D04`–`D10`) and `b06_domain_paths.py` strictly with `.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md` (exact 19 canonical keys in order + `x_`-prefixed extension keys only, `operation_id: "UNASSIGNED_B05"`, verified `src_<16hex>` `consumer_id` linkage, and `status: "PARTIAL"`).
- Verifies full census parity against `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`): `2,608` B06 `domain_hint` rows (`DUX-REQ-B06-01.out`) and `683` B06-prefix rows (`DUX-REQ-B06-03.out`: `527` `NOT_ENRICHED_THIS_PHASE`, `155` `PARTIAL`, `1` `ADAPTED_PARTIAL_VERIFIED`).
- Ships hermetic `pytest` verification (`test_b06_domain_paths.py`) using stdlib + `pytest` only and synthetic fixtures (`+00-000-0000`, `user@example.invalid`).

## Scope (`research/operations/udb-wave8/B06/`)

- `research/operations/udb-wave8/B06/DEFINITIVE-SYNTHESIS.md`
- `research/operations/udb-wave8/B06/b06_domain_paths.py`
- `research/operations/udb-wave8/B06/domain-operation-instances.json`
- `research/operations/udb-wave8/B06/test_b06_domain_paths.py`
- `research/operations/udb-wave8/B06/RESULT.json`
- `research/operations/udb-wave8/B06/PR_BODY.md`

## Evidence Paths

- `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`)
- `.agent-receipts/udb-wave8-dux/CONTRACT-CONVENTIONS.md` (`sha256: a7feea89fa64000d76c18a52d705dd008b4a6336a6d58af98c2618a13048c559`)
- `.agent-receipts/udb-wave8-dux/ADVERSARY-FINDINGS.md` (`sha256: 29c57f706bcc0dd8e7f492f3ffe5215598798ed173f452f19aa7a086c8faaf54`)
- `research/operations/udb-wave8/B06/dux-requests/DUX-REQ-B06-01.out` (`sha256: e30e1c44d8e6ab797e20dc7722eb27854cc1e04a2feab325db2d0a1f3c9d10aa`)
- `research/operations/udb-wave8/B06/dux-requests/DUX-REQ-B06-03.out` (`sha256: 1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb`)

## Missing Evidence (Block Remains `block_closed: false`)

1. Runtime DB role resolution (`ACTOR_IDENTITY_UNRESOLVED` -> live Postgres role) via `B04`.
2. Canonical `operation_id` assignment for the 21 `UNASSIGNED_B05` records via `B05`.
3. Restore drill verification for `public.clients` (`FAIL`), `public.conversations` (`CANNOT-VERIFY`), and B06 domain tables omitted from `scripts/restore_drill_verify.py` via `B07`.
4. Read-only aggregate SQL receipts `DUX-REQ-B06-10`..`12` in `DEFINITIVE-SYNTHESIS.md`.

## Dux correction

One bounded parent-prepared patch (sha256 `94e3c2cf81ba6636aacb100bd7242001bbe6132371a891cc09e2af162341ffb5`) re-grounds the NAGA instance `src_b3bccbae2cc91a8c` on `apps/backend-rag/backend/services/naga/persist.py:24-217`; the `research_os_objects` row in the synthesis is superseded by its addendum. Before: Dux run at base 8061c88 before the correction: exit 1, 8 passed / 1 failed (test_consumer_matrix_census_parity_with_dux_receipts), out sha256 60fee2bd40d819e3cf6c7811d207269b135091277ad06be3af10a0ac574924d4; parent run: 3 passed / 8 failed; isolated pre-patch NAGA regression: exit 1, 1 failed / 1 passed / 11 deselected, out sha256 8832db2535d5205b9c7e55b6592b077a6a85f3af75c3eefc3ff9cbb89332174c. After: exit 0, 13 passed, out sha256 f5801870ba3c5ceaddd5b679e3bc49fcaf5484957ab861eb9e4a296e654ee7e6. All earlier failed receipts are retained; no test case was removed. No native probe, no live Postgres; `block_closed` stays false.

Bites: `research/operations/udb-wave8/B06/b06_domain_paths.py` and `research/operations/udb-wave8/B06/domain-operation-instances.json` consumed by `B05` operation contract catalog merger and `B08` CI contract gate; proved by running `PYTHONPATH=. pytest research/operations/udb-wave8/B06/test_b06_domain_paths.py -q` and `python3 research/operations/udb-wave8/B06/b06_domain_paths.py` returning `"ok": true` across all 21 `D04`–`D10` instances and `683` B06-prefix rows.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
