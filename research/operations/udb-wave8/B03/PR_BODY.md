---
adversarial_review: codex
---

## Summary

Make the B03 census adapter reproducible from shipped, pinned historical fixtures while preserving all original assertions and frozen identities. The existing Mini worktree received the supplied hermetic patch only after exact baseline-hash verification and a successful apply check.

The census remains 6,030 leads: the frozen C09 population of 6,029 plus `runtime_mini_46522da0ef79d3aa7422ca41`. Its dispositions are 1,803 excluded, 43 duplicate and 4,184 unresolved. The actual active-consumer denominator is **UNKNOWN** and `block_closed` is **false**.

## Validation

- Current-source pytest in the original worktree: **24 passed, 0 skipped**.
- Complete isolated candidate with no ignored input receipts: **24 passed, 0 skipped**.
- Fixture CLI regeneration: CSV, JSONL and summary match existing candidate artifacts byte for byte.
- Deterministic fixture derivation check: all nine fixture payloads and projected adapter pins match.
- The supplied patch removes no original assertion lines; the resulting suite has 24 test methods and 101 self-assert calls.
- A first isolated verification harness omitted the three generated reference outputs: 23 passed and 1 failed. Copying the complete candidate corrected the harness; no source changes were needed. Both outcomes are preserved.

Exact commands, source/fixture/output SHA-256 values, timestamps and the retained harness failure are in `research/operations/udb-wave8/B03/INTEGRATION-VERIFICATION.json`. Historical pre-correction pin failures remain in the original `dux-requests` receipts.

## Evidence limits

Fixtures replay dated evidence; they are not new native observations. The frozen C09 SHA-256 is `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`. Deployed execution, B04/B05 store/operation bindings, real backup/restore evidence and host-wide legacy retirement remain unresolved. Cross-host native request 13 was not admitted and remains deferred. The coordinator owns fresh independent acceptance and final committed-head binding; no candidate commit is claimed here.

Scope is `research/operations/udb-wave8/B03/**` only. No shared file, credential, native runtime or secret baseline was changed.

Bites: the B03 contract suite and census adapter CLI consume the shipped fixtures; the observed effects are 24 passing tests with zero skips both with original receipts and without them, plus byte-identical regeneration of the 6,030-lead CSV, JSONL and summary. Evidence: `research/operations/udb-wave8/B03/INTEGRATION-VERIFICATION.json`.

## Adversarial review

Fresh independent Codex review by `/root/b03_available_final_gate` inspected pre-attribution lines 1-24, as pinned in `R1-DOCUMENT-REVIEW.json`. This is a scoped document review, not a complete document endorsement, implementation approval, native observation or final exact-head gate. Historical command/runtime statements are retained as recorded instructions and receipts, not newly observed events. Operational acceptance and the active denominator remain unproved.
