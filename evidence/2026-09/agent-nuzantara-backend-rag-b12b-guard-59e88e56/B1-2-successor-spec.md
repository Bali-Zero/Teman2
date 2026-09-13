---
title: "B1.2 successor spec — why #6266 became two PRs, and the double-import cure"
predecessor: "PR #6266, CLOSED. Gate verdict BLOCK 2026-09-12T02:10Z, harness/fable-gate=failure"
successors:
  - "PR-A agent/nuzantara/backend-rag/b12a-variants — the nine variants + fixtures registry + build spec"
  - "PR-B agent/nuzantara/backend-rag/b12b-guard — this one: the G1-G13 guard, the cure specs, the three reviewer records"
merge_order: "A then B — the guard's census reads the variants"
seat: "claude-opus-5 (Dux, session 402a5404, Pro)"
---

## The three gate causes and where each one went

| #   | Cause                                                                                                                                        | Disposition                                                                                                                                        |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **G13 leg A convicted an HONEST tree** under double import. CI `Backend Shard 3` run 34665686663: 1 failed / 2113 passed.                    | **Cured here.** A defect this guard introduced, not one it inherited.                                                                              |
| 2   | **gear 2 was below the deterministic floor 3**: counted churn 2050 ≥ `SIZE_GEAR3_THRESHOLD` 1828, `Harness floor recompute` run 34665686616. | **Cured by the split.** Each successor declares gear 2 and each computes floor 2, verified with `evidence_pack_lint --print-floor` before opening. |
| 3   | **`Detect Secrets` RED**: one unaudited `Hex High Entropy String` in the predecessor's `pack.yml`.                                           | **Cured here** by an inline `# pragma: allowlist secret` on every long-hex line this pack writes.                                                  |

Gear 3 was _not_ the way out of cause 2: it demands an evidence pack with non-empty receipts **and**
non-empty dissent _plus_ the canonical Gemini/Codex/Kimi council, and the kimi and agy seats were
TIMEOUT that day. Splitting is what makes the declared gear and the computed floor agree, which is
what the check actually measures.

Note on cause 2 that the predecessor's pack got wrong independently of the floor: it carried
`dissent: []` while ruling I14 required the pack to NAME the Codex dissent with the three round
ids. Both successors now carry a populated `dissent:` with `CONFIRMED`/`PLAUSIBLE` per entry. The
empty list was a real omission, not a formatting detail — an evidence pack whose dissent section is
empty is claiming nobody objected, and three reviewers had.

## Cause 1 in full, because it is the interesting one

**What broke.** `test_g13_collected_items_run_the_class_body_def` resolved its `expected` function
object through `importlib.import_module(_module_dotted_name(rel_path))`, i.e. under the name
`backend.tests.services.rag.test_evidence_scoring_abstain`. pytest had already imported the same
FILE under a different dotted name: `backend/tests/` has no `__init__.py` while `services/` and
`services/rag/` do, so under prepend import mode pytest names it
`services.rag.test_evidence_scoring_abstain`. Two names, two module objects, two distinct function
objects for the same source `def` — and leg A compared one against the other and failed on a
completely untouched checkout.

**Why every local run was green.** Per-file runs never put the guard and the protected files in ONE
session, so only one of the two dotted names was ever live. CI Shard 3 collects both. This is the
generic shape: _a guard that compares runtime identity is only as correct as the session shape you
proved it in_, and a per-file proof is not a proof for a guard that reads `request.session.items`.

**The cure, in two parts.**

1. **Leg A takes `expected` from the item's own class** — `item.cls.__dict__[item.name]` — so the
   comparison is self-consistent by construction: there is no second module object for it to
   disagree with. It still convicts the bypass it was written for, because a
   `pytest_collection_modifyitems` hook replaces `item._obj` and leaves `item.cls` untouched.
   _Which file the class came from_ is G11's and G12's question, not leg A's.
2. **G11 and G12 resolve modules by FILE IDENTITY, not by dotted name** (`_modules_for`): they scan
   `sys.modules` for every module whose `__file__` resolves to the parsed path, and check ALL of
   them. Returning a list rather than picking one is deliberate — when both names are loaded, every
   copy must satisfy G11 and G12, which is strictly stronger. The dotted import survives only as a
   fallback for the case where pytest has imported nothing, i.e. the guard running alone.

**Proved in the shape that caught it**, not in the shape that missed it: one invocation collecting
the guard together with the four tripwire files and the six B1 §4 innocence files. `G13 leg A` reports
`18 of 18 protected items collected in this session and verified`, so leg A is non-vacuous in that
run rather than passing because it had nothing to compare.

**The two pre-existing failures in that run are not this diff's.**
`TestDetectTeamQuery::test_dynamic_company_name_marker_matches` and
`..._uppercase_in_query` fail in the same multi-file session _with the guard removed entirely_,
measured both ways. They are order-dependent and predate this work; the brief records them as a
verified assumption rather than quietly excluding them from the run.

## One declared deviation from the split direction

The staff room's direction listed `B1-2-round-2-cure-spec.md` among this PR's contents. It is NOT
here, and that is a decision rather than an oversight. With it, this PR's counted churn was 1840
against `SIZE_GEAR3_THRESHOLD` 1828 — the very violation the split exists to cure — and the
alternatives were worse: trimming the guard's own explanation to fit a size gate trades
understanding for a number, and bumping to gear 3 reopens the council requirement that was
unavailable.

Nothing unique is lost. The round-2 cure is recorded in three other places that ship here: the
guard docstring's G11 entry, `pack.yml`'s round-2 dissent entry with its resolution, and
`codex-round-2-b1-2.md` — the reviewer's own verbatim words, which are the part that could not be
reconstructed. What the deleted file held was a restatement in the Dux's words of all three.

Also recorded, because the first assembly of this PR got it wrong: the floor was recomputed five
times while tightening (1910 → 1880 → 1844 → 1840 → 1822 counted lines), and only the last is
under the threshold, with six lines of margin. The direction's estimate of "~1780" was close but optimistic, and recounting before
opening — which the direction itself insisted on — is what caught it.

## Fix-of-a-fix depth

This is depth 1 on the G13 surface: round 3's cure (G13) was itself wrong, and this is its single
correction. Per the contract, if THIS correction turns out to be wrong the surface is
under-specified and the next step is a spec, not a third attempt. The three-reds counter for B1.2
stays at three **Codex** rounds — a gate red is not an adversarial round.

## What the successors do NOT change

The nine originals stay byte-identical, the registry still declares the DENSE path only, and the
standing limit from round 3 stands unchanged: G12/G13 raise the cost of a deliberate in-process
substitution, they do not make it impossible, and no in-process check can. Accidental weakening is
what G1-G13 pin; deliberate sabotage is the review and gate boundary.
