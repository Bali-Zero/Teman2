---
date: 2026-10-08
domain: visa
client_case: none — gold corpus drift diagnosis (synthetic personas only)
sources:
  - apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py (offline replay, highest signed pack)
  - apps/backend-rag/backend/tests/services/visa_engine/test_evaluator_gold.py (PERSONAS, PRODUCTION_REPLAY_EXPECTATIONS)
  - apps/backend-rag/backend/tests/scripts/visa_engine/test_gold_replay_driver.py (regression floor)
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-025.{source,signed}.json
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-0{06,23,24}.signed.json
  - git history of the corpus and packs (befb71ba00, 587f468fe7, 97f56f2b56, 529efc1a11)
adversarial_review: codex
---

# Gold corpus drift — personas 1, 9 and 10

## Measurement

The offline gold replay against seq-25 (`rulepack-prod-025.signed.json`, version
2026.10.7) printed `matches=17/20 unexplained_divergences=3` before this change. The
three divergent personas are 1, 9 and 10. After this change it prints
`matches=18/20 unexplained_divergences=2`, with 9 and 10 left divergent.

The live replay was not run from this lane. The orchestrator measured live equal to
offline on all twenty personas, so the engine is self-consistent and the gap is
between the corpus and the pack.

I also replayed 1, 9 and 10 against every signed production pack on disk, each at
its own signing date plus two hours. That is the only way to read old packs: at the
current date they all answer stale-source review.

## Persona 1 — Indonesian citizen, cured (decision A)

| | Expected (before) | Actual on seq-25 |
|---|---|---|
| State | `NO_SUPPORTED_PATH` | `NO_SUPPORTED_PATH` |
| No-path codes | `APPLICANT_IS_INDONESIAN_CITIZEN` | `BVK_NATIONALITY_ONLY`, `APPLICANT_IS_INDONESIAN_CITIZEN`, `VOA_DUAL_NATIONALITY_NOT_ASSESSED`, `AGE_BELOW_55` |

Since seq-23 the state and the citizen exclusion are right. Only the code list is
incomplete. The persona has two nationalities and the shared baseline is under 55, so
other products' own hard filters fire on the same facts. The raw evaluator yields five
proofs, one per rule below. The public policy adapter merges the two age proofs into one
`AGE_BELOW_55`, which is why the expectation lists four codes:

- `hf.citizen` emits `APPLICANT_IS_INDONESIAN_CITIZEN`.
- `hf.a1.not-bvk-nationality` emits `BVK_NATIONALITY_ONLY`.
- `hf.b1.voa-dual-nationality` emits `VOA_DUAL_NATIONALITY_NOT_ASSESSED`.
- `hf.e33e.age-below-55` and `hf.e33f.age-below-55` both emit `AGE_BELOW_55`, deduplicated.

History, each claim re-derived from the pack sources and `git log -S`:

- `hf.citizen`, `hf.a1.not-bvk-nationality` and `hf.e33e.age-below-55` exist in every pack since seq-1, the first signed production pack (3c412c96b0).
- `hf.e33f.age-below-55` exists since seq-6 (529efc1a11). Seq-5 has no signed file on disk.
- `hf.b1.voa-dual-nationality` is new in seq-23 (candidate e04b4aa137, signed 587f468fe7). The same pack retired the review hold `CITIZENSHIP_LIST_DIVERGENCE`, which seq-22 still carries. That flipped persona 1 from `HUMAN_REVIEW_REQUIRED` to `NO_SUPPORTED_PATH` with five codes, including `SPONSOR_REQUIRED` from `hf.e33f.sponsor-required`.
- Seq-24 (97f56f2b56) retired `hf.e33f.sponsor-required`, leaving the four codes that seq-25 (2a1e00e0d3) still emits.
- Seq-1 answers `DECISIVE_SOURCE_FRESHNESS_UNKNOWN` at its signing date, so the review reason for persona 1 before seq-23 is only stated for the seq-4 to seq-22 packs on disk, replayed at their own signing dates.

Personas 2, 3 and 4 were re-derived in the seq-23 and seq-24 commits. Persona 1 was not.

Decision A: the gold was stale and the engine is right. The expectation now lists the
four codes in engine order, with a dated comment. The legal citation and rationale are
unchanged.

## Personas 9 and 10 — not cured (decision B)

| Persona | Expected | Actual on seq-25 |
|---|---|---|
| 9, channel `ONSHORE_CONVERSION` | `NO_SUPPORTED_PATH`, `DIRECT_ONSHORE_CONVERSION_UNSUPPORTED` | `SUPPORTED_CANDIDATES`, `D12` |
| 10, channel `STATUS_BRIDGING` | `HUMAN_REVIEW_REQUIRED`, `STATUS_BRIDGING_REVIEW` | `SUPPORTED_CANDIDATES`, `D12` |

### Cause

Both expected outcomes were copied from the synthetic five-product fixture in
`_gold_fixtures.py`, which has rules keyed on `process.application_channel`. No
production pack has ever had such a rule, and neither expected reason code exists in
any pack. Counted in all 24 source files on disk, the fact name and both codes occur
zero times.

The fact is accepted on the public request, then ignored. Persona 9, persona 10 and
a variant with channel `OFFSHORE` all return the identical `D12` decision. The
expectation entered with the PR-5 corpus (befb71ba00, 2026-09-09) and has not changed.

`D12` is the only candidate because:

- `el.d12-multi-entry-support` supports the `INVESTMENT` purpose with a stay up to 360 days.
- `hf.d12-onshore-conversion-excluded` fires only on `process.wants_onshore_conversion = true`, and the persona leaves it at the baseline `false`.
- `E28A` is out through `hf.e28a.paid-capital-below-min`. The persona sets investment capital but leaves paid-up capital at the baseline of zero.
- Product `D12` has been a candidate for these facts since seq-6 (529efc1a11, 2026-08-12). Seq-1 to seq-4 answered review.

### Why this is not a gold update

A previous decision, recorded in the floor test docstring (befb71ba00, re-derived
2026-09-10), deliberately kept these two out of the expectation table. The legal
reading was that a direct C1-to-E28A onshore conversion is unsupported and that a
status-bridging route needs an adviser. Rewriting them to `D12` would pin the engine's
silence about the channel as if it were the legal answer, and would contradict the
persona labels. The cure belongs in the pack or in the request contract, not here.

### Open questions for the pack owner

1. **Channel is inert.** Either a rule must consume `process.application_channel`, or the contract must stop accepting it, or the personas must be re-encoded with the fact production does read, `process.wants_onshore_conversion`.
2. **Re-encoding does not give the labelled answer.** With `wants_onshore_conversion = true` and paid-up capital at 2.5 billion IDR, seq-25 returns `E28A` alone as a supported candidate. With only `wants_onshore_conversion = true` it asks for `sponsor.type`. No rule excludes `E28A` for a person in Indonesia on a visit status who wants an onshore conversion. Whether that is the intended law is a legal call.
3. **Bridging from C1 is already prohibited.** `hf.bridging.from-visit-itk` excludes the `BRIDGING` product when the current status is `C1`, among others. So for persona 10 the pack's own reading is prohibition, which matches neither the old gold (adviser review) nor the engine's current `D12`.

The ledger note from 2026-08-23 already names the root mechanism for investor
personas: the hit policy `COVER_ALL_DECLARED_PURPOSES` lets one broad support rule
carry a product without checking its defining constraint.

## What changed in the repo

- Persona 1 expectation updated in `test_evaluator_gold.py`.
- The floor test now requires at least 18 matches, at most 2 unexplained divergences, and exactly personas 9 and 10 as the unexplained set.
- A new test proves the new persona 1 expectation against seq-25 offline and that the old single-code expectation no longer matches.

## Verification

Commands run from `apps/backend-rag`:

```bash
PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.gold_replay_driver --offline --out <report.json>
PYTHONPATH=. .venv/bin/pytest backend/tests/scripts/visa_engine backend/tests/services/visa_engine/test_evaluator_gold.py -q -p no:cacheprovider -o addopts=""
```

## Adversarial review

Codex GPT-5.6, read-only sandbox, 2026-10-08: 4 findings.

- **[BLOCK]** The sandbox could not execute pytest or driver writes. This is the environment, not the patch. Re-run by the author: 40 passed, 18/20.
- **[LOW]** Persona 1 confirmed. The five raw proofs are merged to four by the public adapter. The note now says so.
- **[MEDIUM]** The rule-history claims were inexact. Corrected in this head.
- **[MEDIUM]** The floor did not pin how personas 9 and 10 diverge. Pinned in this head.

Surviving: none.
