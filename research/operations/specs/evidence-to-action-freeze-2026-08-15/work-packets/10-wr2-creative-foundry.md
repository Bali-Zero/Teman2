---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 10 — WR2 Creative Foundry

**Wave:** 2
**Depends on:** Packets 04, 06, and 18
**Feeds:** Packets 13 and 14
**Risk:** medium creative-quality risk; Instagram publication remains manual

## Session prompt

You own the conversion of WR2 from an industrial template pipeline into a faithful creative foundry invoked by the Conductor after topic and Creative Lock. Preserve its efficient rendering machinery; repair the contracts that flatten editorial intent and bypass independent quality judgment.

You are not alone in the codebase. Use a dedicated worktree, declare exact files, preserve concurrent changes, and never revert user assets or queue state. Do not publish to Instagram, alter live queue files by hand, or let the generating agent grade itself.

## Mission

Given a verified `ContentObject` with topic, angle, audience, promise, narrative arc, must-keep elements, and claim bindings, produce a distinct carousel whose per-slide visual and narrative intention survives planning, rendering, and critic review.

## Live baseline to refresh

- WR2 has a rich planner, image generator, HTML renderer, Canva paths, brand rules, metrics, and tests.
- The planning representation can carry hero intent, but a typed projection commonly preserves hero/image fields only for the cover; downstream selection relies on `is_hero_image`, collapsing a multi-slide visual plan to cover-only.
- The daemon renderer's current result can be `legibility_only_pass`; the full constitutional/visual critic in the interactive architect lane does not necessarily gate daemon drafts.
- The strongest recent carousel quality came from a sensitive operator–AI session, not autonomous template repetition.

Measure recent slide-level image uniqueness, hero coverage, critic coverage, human edit distance, rejection reasons, layout diversity, and production time.

## File ownership

Primary ownership:

- `scripts/wr2_carousel_ir.py`
- `scripts/wr2_planner_writer.py`
- `scripts/wr2_draft_generator.py`
- `scripts/wr2_image_generator.py`
- `scripts/wr2_html_renderer/**`
- `scripts/wr2_creative_ledger.py`
- WR2 claim/grounding adapters required for Packet 04/06 contracts
- focused `scripts/tests/test_wr2_*` and renderer tests
- WR2 foundry runbook/contract documentation

Inspect but do not redesign topic discovery, Intel Lake, NAGA, Instagram publishing, or the canonical queue writer. Do not edit production queue JSON manually.

## Inputs and frozen contracts

- `ContentObject` carrying exact `topic_lock_ref` and `creative_lock_ref`, plus separate unexpired `ApprovalReceipt` objects bound to each referenced object hash.
- Exact reviewed `Claim` and `Evidence` ID/hash references from NAGA.
- `MediaManifest` with per-asset provenance, hashes, rights, prompts, and checks.
- Immutable `WorkflowRun` coordination snapshot and independent canonical `VerificationReceipt` bound to the exact rendered artifacts.
- Instagram always requires a human publication action.

## Deliverables

1. A lossless typed carousel IR carrying for every slide: role, claim bindings, layout family, hero flag, visual purpose, original prompt, asset source, and fallback policy.
2. A migration/compatibility adapter for existing drafts with an explicit loss report.
3. Per-slide image generation/selection driven by the IR, never inferred from cover position.
4. Asset-uniqueness enforcement: no silent placeholder/anchor reuse; SHA-256 provenance in `MediaManifest`.
5. One independent critic gate on the exact rendered PNGs, covering factual fidelity, narrative promise, brand, typography, bilingual assist, visual-topic sensitivity, and slide-level verdicts.
6. A Creative Lock checkpoint: changes to topic/angle/promise after lock require a new immutable `CreativeLock` and a separate exact operator `ApprovalReceipt`; a lock never embeds its own approval.
7. Human-edit capture as structured deltas without automatically mutating prompts or templates.
8. A small layout/visual retrieval library selected by topic need and prior evaluated outcomes, not template frequency alone.

## Non-goals

- Do not let WR2 decide which topic matters.
- Do not eliminate the operator–AI creative session.
- Do not add mass autonomous publishing.
- Do not optimize primarily for token savings or carousel throughput.
- Do not reuse a successful visual metaphor silently for unrelated topics.
- Do not use an LLM's self-score as the final gate.

## Implementation sequence

1. Freeze 30 representative historical carousels with operator quality labels and edit histories where available.
2. Trace one multi-hero plan field-by-field through planner, IR, image selection, renderer, and manifest; write a failing regression test.
3. Make the IR lossless and add compatibility adapters.
4. Enforce per-slide asset provenance and uniqueness.
5. Connect the independent critic to the exact daemon-rendered output.
6. Add Creative Lock and critic receipts to the workflow state.
7. Shadow against current WR2 on 5–10 locked briefs; do not publish.
8. Let the operator blind-compare candidates and record structured edits.

## Golden set and adversarial cases

Use at least 30 prior carousels spanning tax, visa, property, company, Bali news, numbers, bilingual terminology, narrative/metaphorical topics, and document-heavy explainers.

Adversarial cases:

- three hero slides after the cover;
- same asset hash assigned to different hero intentions;
- heading promises N items but body delivers a paragraph or wrong count;
- legal claim unsupported or expired;
- bilingual term missing first-use assist;
- visually legible but thematically generic output;
- critic evaluating source HTML instead of final PNG;
- plan mutated after Creative Lock.

## Tests and exit criteria

- IR round-trip and legacy loss-report tests.
- Per-slide hero/image selection tests.
- asset hash uniqueness and explicit-reuse tests.
- claim coverage and stale-claim tests.
- final-PNG critic invocation and generator≠grader tests.
- deterministic typography/safe-area/OCR checks.
- blind operator comparison and edit-distance capture.

### Human-edit metric

For each paired locked brief, capture four normalized deltas separately: **structural** (slide order/count, narrative role, heading/promise fields), **textual** (field-level normalized changes to headings and body), **factual** (claim bindings, qualifiers, numbers, citations, and corrections), and **visual/asset** (layout family, hero intent, asset selection, crop, and fallback). The composite edit distance is the preregistered weighted sum of those four values; weights sum to 1 and may not be selected after results are visible.

Before any shadow result is inspected, Packet 10 must create and freeze the canonical `MetricProfile` that binds baseline/candidate pairing, field normalizers, weights, eligible/excluded cases, minimum paired sample, domain/risk subgroups, confidence interval, and operating window. Packet 10 appends results only through canonical `MetricResult` objects; Packet 14 independently validates and consumes those objects but does not preregister this packet's metric after seeing results. If the sample floor is not met, report `insufficient_evidence` and do not claim the 25% improvement or pass that efficiency gate. Factual and critical-claim regressions are hard guardrails and cannot be averaged away by smaller text edits.

Exit only when all declared hero slides receive intentional assets or explicit reviewed fallbacks, silent reuse is zero, every rendered slide has an independent verdict, critical claim errors are zero on the golden set, the preregistered paired sample is sufficient, composite median human edit distance improves at least 25% against baseline without any factual guardrail or topic-diversity regression, and Instagram remains a manual stop.

## Shadow, canary, and rollback

Render shadow candidates without touching the live publication queue. Canary a small number of operator-selected briefs through the new IR while preserving the legacy renderer path. Rollback selects the old pipeline via feature flag and retains manifests/comparison data.

## Reviewer handoff

Provide before/after IR examples, field-lineage trace, final PNGs, critic receipts, asset hashes, claim coverage, blind comparison results, edit deltas, and proof that no post was published.
