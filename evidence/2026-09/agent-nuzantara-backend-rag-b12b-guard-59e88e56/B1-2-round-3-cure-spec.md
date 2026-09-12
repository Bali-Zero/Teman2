---
title: "B1.2 round-3 cure spec — G12 and G13, each MEASURED against the reviewer's own bypass"
authority: "imperator ruling I14, fleet envelope 20260912T013527Z-13d6 (B1-ack, 2026-09-12T01:36Z)"
cured_sha_base: 71b28dd39d
seat: "claude-opus-5 (Dux, session 402a5404, Pro) — no fourth Codex round, the reviewer does not re-read"
---

## Why this spec exists at all

Round 3 returned BLOCK on one cause for the third time, and the three-reds rule says the
surface is under-specified: write the spec instead of taking a fourth round. The previous
window proposed REJECTING both blockers as outside the guard's threat model — an argument,
not a measurement. The Rule-8 tiebreaker says the verdict "spec it" is only honest once the
cheap patch has been measured and shown not to work, so the patches were measured first.

Both blockers turned out to be REAL and cheaply curable, so both are cured here. The
imperator's ruling I14 keeps the threat-model reasoning standing as the _fallback_ and
accepts the measured cure as the amendment: G12/G13 ship, the dissent is named, no fourth
round.

## What was measured, before any code was written

| #   | Claim under test                                                                                                      | Method                                                                                                | Result                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| M1  | G11's eight assertions all pass on an `exec`-compiled clone with forged `co_filename`/`co_firstlineno`/`__qualname__` | G11's assertion chain replayed against a synthetic module in the scratchpad (no tracked file touched) | **ALL GREEN**, and the clone is what runs — R3-1 is real, not hypothetical     |
| M2  | a structural code-object digest catches the clone without turning the honest tree red                                 | digest of runtime code vs an independent compile, over the 18 real protected names                    | clone **caught**; honest names **0 mismatches** _after_ two corrections, below |
| M3  | a `pytest_collection_modifyitems` hook replacing `item._obj` keeps G11 green while the body never runs                | throwaway pytest project, conftest hook present vs absent                                             | G11 **green** with the hook, victim body **never ran** — R3-2 is real          |

Two corrections M2 forced, each one a guard that would have been red on an honest tree —
i.e. a trade, which rule 8 forbids, not a cure:

1. **`co_flags` diverged on 8 of 18 names** (bit `1 << 24`, `CO_FUTURE_ANNOTATIONS`): the four
   tripwire files carry `from __future__ import annotations` and an isolated compile does not
   inherit it. Cured by compiling the whole module, which carries its own future imports —
   so `co_flags` stays IN the digest rather than being dropped to make the comparison pass.
2. **pytest REWRITES assert statements at import time.** A plain `compile()` of the parsed
   `def` disagrees with the runtime code object on **all 18** names — measured as 9 red
   G12 cases on the real tree. Cured by reproducing `_pytest.assertion.rewrite.rewrite_asserts`
   before compiling. This is the correction that matters: the first draft of G12 was a guard
   that convicted the innocent, and only running it on the real tree said so.

## The cure

**G12 — the runtime code OBJECT is what the parsed `def` compiles to.** A structural digest
(opcodes, flat constants, `co_names`, `co_varnames`, signature, `co_flags`, and recursively
the digests of nested code objects) of `cls.__dict__[name].__code__`, compared against the
same digest taken from the guard's own pytest-style compile of the file. `co_filename` and
`co_firstlineno` are deliberately EXCLUDED from the digest — they are exactly what the bypass
forges, and G11 already pins them; a digest that included them would be satisfied by the same
forgery. Also pinned here: `module.__file__` resolves to the parsed path (a shadow copy on
`sys.path` cannot split the two halves) and `obj.__globals__ is module.__dict__`.

**G13 — pytest runs the class-body def, on two legs, neither a silent skip.**

- _leg A, dynamic:_ for every protected name present in `request.session.items`, the collected
  item's callable **is** the class-body def — identity, not metadata. Names absent from the
  session are printed by name; selecting only the guard file collects none of them, and that
  is stated rather than hidden.
- _leg B, static:_ a CENSUS of the collection hooks defined in the conftest chain that applies
  to the four tripwire files, compared against an expected literal set (empty today). Leg B
  binds in EVERY session regardless of what was collected — it is what holds when leg A has
  nothing to compare, which is the case the reviewer's fix would have missed.

**R3-3 (minor), applied:** the module docstring no longer calls itself "purely static / no app
init" — G11-G13 import the four test modules and execute their top-level code, and the
docstring says so. Module identity is checked rather than trusted.

## Proofs

Superseded by `pack.yml`'s receipts on the successor PR, which re-ran every leg on the
ruff-formatted file and in the multi-file session shape that this spec's own proofs missed — see
`B1-2-successor-spec.md` for why a per-file proof was not enough. Kept here only as the shape the
proofs take: innocence on the guard alone, innocence on the four tripwire files and the six B1 §4
files, guilt A (forged clone) red on G12 with G11 green, guilt B (collection hook) red on G13 leg
B alone and on legs B and A together, ruff clean.

No guilt proof touched a tracked file: the mutations were planted in a `git archive` copy under
the session scratchpad, and M1/M3 used synthetic modules.

## What is NOT claimed

G12/G13 raise the cost of a deliberate in-process substitution; they do not make it
impossible, and no in-process check can. The imperator's threat-model boundary stands as
stated in I14: accidental weakening is what G1-G13 pin, deliberate sabotage is the review and
gate boundary. The dissent is named in `pack.yml` with the three round ids.
