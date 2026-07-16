---
date: 2026-07-17
domain: operations
client_case: none (execution architecture for the GARUDA-FILIERA program, pilot batch A1)
adversarial_review: exempt-preregistration-frozen-plan
sources:
  - "companion: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (§3 D0-D6, §4 batching, §5 sampling, §8 solo-operatore)"
  - "companion: research/operations/2026-07-16-kbli-filiera-methodology.md (P1-P9, L0-L6, G13-G17)"
  - "mandate: Zero GO 2026-07-16 — 'go... e ricorda di implementarlo per tutti i workflow'"
  - ".claude/skills/kbli-navigator/SKILL.md (established truths, artifacts & access, operating rules)"
---

# PILOT A1 — Pre-registration (GARUDA-FILIERA, batch plan signed BEFORE extraction)

> Authored: Fable session f5892d39, 2026-07-17 (Zero GO 2026-07-16: "go... e ricorda di
> implementarlo per tutti i workflow"). Companion: research/operations/2026-07-16-kbli-garuda-
> filiera-workflow.md (D0-D6). This plan is FROZEN once the pilot starts: changes require a
> new version line, never silent edits (pre-registration discipline, §3 "scientific").

## Code list (15 — fixed, seed 20260716 for the sampled subsets)

| Class | Codes | Why |
|---|---|---|
| Index cases (known truth) | 68112, 51103, 51203 | pipeline MUST reproduce the already-proven collisions (68112 MICE/residential; 5110x/5120x space-vs-aviation). Failure to reproduce = pipeline bug, not new fact. |
| High-concern sweep suspects | 20111, 43216, 43223, 49213 | scope_uraian carries verbatim OLD-PP28 titles/sub-classifications (sweep 2026-07-16, post-manual-review) |
| Batch A random sample | 47771, 50115, 60312, 64110, 64310 | `_l2_source=null ∧ per_skala≠[]` (the 119 highest-risk set), random.seed(20260716) |
| Innocence controls | 65121, 85202, 85579 | OSS-native, no pp28_sources: dossiers MUST come out boring (no changes proposed). A "finding" here = over-extraction bug. |

## Acceptance criteria (falsifiable, fixed now)

1. **D0 completeness invariant**: every dossier cites ≥1 vault item per applicable layer
   (BPS Vol.2 crosswalk row; OSS snapshot files or absence record; PP28 render refs where
   pp28_sources exist). Missing layer without a recorded ABSENT = dossier INVALID.
2. **Index-case reproduction**: 68112 dossier concludes code-number collision with the same
   verdict as the shipped fix (per_skala stays detached); 51103/51203 conclude
   aviation-licensing-does-not-inherit. Any other conclusion → STOP-THE-LINE (pipeline bug).
3. **Innocence controls**: zero proposed changes on 65121/85202/85579. Any proposed change →
   over-extraction; batch FAILS.
4. **Crosswalk discipline**: every 2020↔2025 join cites a Lampiran 5 (2020→2025) or
   Lampiran 10 (2025→2020) row from BPS Vol.2 (vault sha 29f17b3b…) with page locator;
   1-to-many rows get uraian-semantics rationale + refuter verdict (generator≠grader).
   Title-similarity-only mapping = automatic quarantine.
5. **Digit discipline**: any load-bearing digit read from a PP28 render carries
   (render sha256, page, row); pdftotext digits are never evidence (681t2 lesson).
6. **Verdict taxonomy**: every non-deterministic fact ends `certified | quarantined(reason,owner)
   | abstained(reason)`. No fourth state.
7. **D6 final gate (Fable, non-delegable)**: 100% of quarantines + ≥5 random dossiers re-read
   against raw vault evidence (never seat summaries) before sign-off.
8. **Measurement (for Zero's Fable-usage question)**: per-dossier: seat invocations, tokens/seat
   (where reported), wall time, quarantine rate. Batch report includes the Fable-vs-heavy-plane
   token split.

## Failure rules
Per workflow doc §6: seat probe-dead → declared degraded council; compiler exception →
quarantine + continue (fail-visible); Fable window dead → suspend at batch boundary.

## Vault snapshot pinned for this pilot
- BPS Vol.2 2026: sha256 29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949 (444pp, both directions)
- PP28: 21/21 BPK ids (fetch-log 2026-07-17, 345MB, per-file sha in pp28/fetch-log.jsonl)
- OSS: full re-snapshot 2026-07-17 (fetch-log + absences.jsonl)
- Canonical: data/source_documents/KBLI_2025_FINAL_CLEAN.json @ main (post-#2559)

## Adversarial review

Exempt (`exempt-preregistration-frozen-plan`): this document IS the pre-registered contract
itself, not a finding or a synthesis to be graded by a second seat before it can be trusted —
generator≠grader for a pre-registration means the plan is frozen BEFORE the extraction that
would let anyone game it, and it is subsequently graded EMPIRICALLY, not by review of its prose:
the D6 final gate (§Acceptance criteria #7, workflow doc §3 D6) re-reads dossiers against raw
vault evidence and either reproduces the acceptance criteria above or the batch fails outright.
Nothing here is asserted as a fact about the world (that's what the pilot run produces, and
those per-dossier outputs get their own generator≠grader treatment inside the D1/D5 protocol);
this file only commits, in writing, to a plan before seeing results — the R1 gate's purpose
(no self-graded homework) does not apply to a commitment device.
