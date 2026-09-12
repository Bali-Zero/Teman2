---
date: 2026-09-12
domain: visa
client_case: none
sources:
  - research/secondhome/probe-superseded-threshold.py (the v1 guard this spec replaces)
  - evidence/2026-09/agent-air-m5-mouth-shweb-w3-editorial-20260911-cc099459/build-receipts/guard-mutation-run.txt
  - POST refuter round 3 (codex-sol, 2026-09-12, BLOCK, findings 1-7)
---

# probe-guard-spec-v2 — the E33 claim guard, specified rather than patched

Written for PR-1b. The author of this spec does not implement it: generator is never grader, and
this session has now been the generator of two guard designs that an adversarial seat defeated.

## Why a spec instead of a fourth round

Three adversarial rounds landed on ONE surface: the guard. Round 1 said it measured tokens and not
claims. Round 2 defeated the marker-based acquittal from both sides at once — it acquitted
`E33 requires IDR 2 billion and no longer requires a sponsor` and convicted
`For E33, IDR 2 billion, the old threshold, is no longer required`. Round 3 defeated the
replacement in seven ways. The repo's own rule: a fix-of-a-fix stops at depth 1, and if the
correction is itself wrong the surface is under-specified, so you write the spec.

The v1 guard SHIPS with PR-1, labelled as a measurement instrument. Nothing below is a defect in
the article content: the five sources are cured and independently checked.

## R1 — The entity is amount + currency, on BOTH sides

v1 reads only what precedes the amount, so `E33 applicants may own 2 billion USD.` and
`two billion dollars` are convicted. A currency token on EITHER side owns the figure; a non-rupiah
owner acquits it; no owner at all leaves it convicted. Acceptance: both strings acquitted, and
`2 billion rupiah`, `2 miliardi di IDR`, `due miliardi` still convicted.

## R2 — Two written forms of the amount are still invisible

`E33 requires Rp. 2.000.000.000.` (a dot after `Rp`) and `IDR 2.0 billion` both pass v1. The
abbreviation may carry a trailing dot, and a decimal that equals two (`2.0`, `2,0`, `2.00`) is two
billion. `2.5 billion` must stay acquitted. Acceptance: four strings, two convicted, two acquitted.

## R3 — An allowance is a PARAGRAPH-scoped statement, not a line hash

v1 keys the allowlist on `sha256(normalised line)`. The refuter allowlisted
`E33 no longer requires IDR 2 billion.` and then wrote `It is false that` on the line above: the
paragraph asserts the obligation again, the hash is unchanged, `--claims` exits 0 and `stale` is
empty. An allowance must be keyed on the paragraph that carries the occurrence — the block of
non-empty lines around it, normalised the same way — so that any edit to the surrounding sentences
rotates the key and sends the allowance back for review. Acceptance: the refuter's exact
counter-example turns red, and a whitespace-only edit elsewhere in the file does not.

## R4 — Anchor the row that carries the conditions

The `Financial requirement` row of the comparison table is unanchored: removing
`in the applicant's own name` and turning `completed strata unit` into `qualifying property` leaves
`--claims` at zero. Both conditions live there; they must be anchored to THAT row in all five
locales, exactly as Duration, Renewal and the four metadata fields already are. Acceptance: that
mutation red in each locale.

## R5 — Pin the wording removed at every round, not only at the base

The 30 literal pins compare against the BASE commit `70b43c5459`. Wording removed in the
INTERMEDIATE rounds is unguarded, so restoring the frozen head's `**Cosa vale come prova:**` or
`**Yang diterima sebagai bukti:**` passes green — and with it returns the contradiction between a
list of accepted proofs and a statement that the accepted document is unknown. The pin set must be
built from the union of every wording this mandate removed, at any round, with the round recorded
next to each entry. Acceptance: both headings red.

## R6 — Pin what the last round removed

The 180-day absence threshold was removed from five locales and never pinned; putting
`(180+ consecutive days outside Indonesia)` back leaves `--claims` at zero. Any figure this mandate
deletes for want of a source is pinned in the same commit that deletes it. Acceptance: red.

## R7 — One comparator, one proof, for BOTH exports

`idArticles.sort` could be deleted with the suite green because the ID fixture had a single
publishable article. Fixed in PR-1 (two ID translations whose dates run against filesystem order);
the spec records the rule: every sorted output gets a fixture where the correct order disagrees
with the filesystem order, and the mutation is proved red.

## What "done" means for PR-1b

A mutation run in the shape of `build-receipts/guard-mutation-run.txt`, extended with the seven
counter-examples above, every one red, and the honest paragraph in the probe docstring rewritten to
match what the code then actually does. Until then the docstring keeps saying what it says now.

## Adversarial review

This spec is the OUTPUT of adversarial review, not a document awaiting one. Every requirement
above is a counter-example that `codex-sol` executed against the working tree on 2026-09-12
(round 3, BLOCK, findings 1-7), with the command and the result recorded in the session
scratchpad and summarised in the PR body. R7 was additionally re-proved red in this repo after
the fixture landed. The one judgement that is mine and not the refuter's is the choice of
paragraph scope in R3; a reviewer who thinks the section or the whole file is the right unit
should say so before it is implemented, because widening the scope makes allowances rotate more
often and narrowing it reopens the evasion.

Not reviewed by a second seat: this spec itself. It ships as a document, implements nothing, and
the seat that implements it is expected to attack it first.
