---
date: 2026-08-18
domain: visa
client_case: none
sources:
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json (el.e33e.deposit-income-basis, el.e33g.income-60k-manual — real defects motivating this increment)
  - apps/backend-rag/backend/scripts/visa_engine/compile_claims.py (E5 increment-1 compiler, PR #4283)
adversarial_review: kimi-k3
---

# E5 doctrine-factory — increment 2: two more hard compile-time lints

Increment 1 (PR #4283) shipped the claim-backed rule compiler
(`compile_claims.py`) with two hard lints: VERIFIED-only (claim state) and
R-OVERSTAY-PLANNING (condition structure). This increment adds two more,
each motivated by a **real, currently-active defect** in
`rulepack-prod-007.source.json` — not a hypothetical.

## Lint 3 — UNSATISFIABLE-CONDITION

`el.e33e.deposit-income-basis`'s `when` is logically unsatisfiable. Its
outer `all` re-asserts the same four leaves (`bank_deposit_usd`,
`bank_deposit_at_state_bank`, `bank_deposit_in_own_name`,
`passive_monthly_income_usd`) that an inner branch demands the XOR of:
one branch requires `D ∧ I` (deposit-conditions AND income all true), the
other requires `(D ∧ ¬I) ∨ (¬D ∧ I)` (exactly one true). `D ∧ I ∧ (XOR)`
is a contradiction — the rule can never fire, silently, forever.

Verified by brute force over the boolean abstraction (every distinct leaf
— by canonical-JSON identity — is an independent atom): 6 distinct
leaves, 64 assignments, zero satisfy `when`.

Implementation: `_compile_boolean_shape` walks `when` once, collecting
every distinct leaf into a dict keyed by canonical JSON (so two
occurrences of the *same* leaf collapse onto the *same* atom — this
sharing is exactly what makes the E33E contradiction visible) and
producing a compact `_Shape` tuple tree. `lint_unsatisfiable_condition`
then brute-forces all `2**N` assignments against that shape. Sound for
UNSAT-*by-structure* (independent atoms is the most permissive possible
reading — if even that has no satisfying assignment, no stricter
arithmetic-aware semantics can have one either); deliberately blind to
*arithmetic* contradictions (`x>5 AND x<3` as two unrelated atoms) — that
is a different, harder tool this lint does not attempt.

**Declared limit**: a `when` with more than 20 distinct leaves is not
brute-forced (2**20 assignments is already over a million per rule) — the
compiler emits an explicit `"satisfiability not checked (N leaves > 20)"`
report note instead of silently skipping. Verified by a dedicated test
(`test_guilt_more_than_twenty_leaves_is_skipped_with_declared_note`) that
asserts the note text is present, and by an end-to-end test through
`compile_manifest` that a 21-leaf rule still compiles clean *with* the
note visible in `report.render()`.

## Lint 4 — VACUOUS-RULE

`el.e33g.income-60k-manual` claims (by name) to gate on income, but its
`when` is the same remote-work block literally duplicated twice — it
references zero income facts, and the literal `60000` appears nowhere in
the pack.

Two mechanical checks (deliberately never inferring intent from the rule
name or claim_ids — that is form, not entity):

- **4a — duplicate-subtree**: an `all`/`any` node with two
  structurally-identical (canonical-JSON-equal) children is a compile
  error. The duplication itself is the smell; E33G's `all[A, A]` is
  exactly this shape.
- **4b — `must_reference_facts`** (optional manifest field): an author
  declares `must_reference_facts: [fact paths]` on a rule entry, and the
  compiler proves every listed fact actually appears in the `when`-derived
  `required_facts` — a mechanical proof, not an inference.

## Adversarial review

kimi-k3 (`kimi -m kimi-code/k3`) reviewed the full diff. First attempt
(8-minute timebox) got stuck in meta-planning about how to orchestrate
the review and produced no disposition before being killed — noted, then
retried once with a tighter "answer directly from the diff, no tools"
prompt, which succeeded within its 5-minute timebox.

| # | Finding | Disposition | Action |
|---|---|---|---|
| 1 | `condition.get("args", [])` doesn't apply its default when the manifest has `"args": null` (or any non-list) — iterating raises `TypeError` before schema validation ever runs, crashing the whole compile instead of producing a finding | ACCEPT | Added `_safe_args()` helper (treats non-list `args` as `[]`); used in `_compile_boolean_shape` and `_find_duplicate_subtrees`. Added guilt tests with `None`/string/int/dict `args` proving no crash. |
| 2 | `{"op": "any", "args": []}` is Kleene-FALSE (genuinely unsatisfiable) but the original `if not leaves: return [], None` early-return passed it silently — a 0-leaf `when` was never actually evaluated | ACCEPT | Removed the early-return special case; the general brute-force loop already handles 0 leaves correctly (`2**0 == 1` assignment, evaluated for real). Added guilt tests for bare empty-`any` and empty-`any` nested under a real leaf. |
| 3 | `_canonical_key` (via `json.dumps`) was re-run on every leaf for every one of up to `2**20` assignments — ~20M redundant serializations at the exact boundary the lint is documented to still check | ACCEPT | Merged leaf-collection and shape-compilation into one pass (`_compile_boolean_shape` → `_Shape` tuple tree with leaf keys pre-resolved); evaluation (`_evaluate_boolean_shape`) now touches plain tuples/strings, zero `json.dumps` per assignment. Measured: the 20-leaf boundary test dropped from ~3.0s to ~1.3s locally. |
| 4 | `entry.get("must_reference_facts") or []` treated any falsy-but-present value (`""`, `0`, `False`) as if the field were absent, silently bypassing the "must be a list" rejection | ACCEPT (minor) | Rewrote to distinguish `None`/missing-key (→ not declared) from any other non-list value (→ rejected). Added guilt tests for `""`/`0`/`False` and an innocence test confirming explicit `null` still means "not declared". |
| 5 | `test_innocence_simple_contradiction_by_shared_leaf_is_caught` asserts the lint *fires* — by the file's own guilt/innocence naming convention that's a guilt test; only the name was wrong | ACCEPT (cosmetic) | Renamed to `test_guilt_simple_contradiction_by_shared_leaf_is_caught`. |
| 6 | The `>20` guard's off-by-one | DECLINE | 20-checked / 21-skipped matches the docstring and both boundary tests exactly; no logic error. |
| 7 | Soundness of the independent-atoms abstraction | DECLINE | Correct relaxation argument, verified by hand: if the most permissive reading is UNSAT, no stricter arithmetic-aware semantics can be SAT. Documented arithmetic blindness is a disclosed completeness gap, not a soundness bug. |
| 8 | The E33E fixture's UNSAT claim itself | DECLINE | Verified by hand (kimi and independently, here): 6 distinct leaves, `D ∧ I ∧ ((D∧¬I)∨(¬D∧I))`, genuinely UNSAT; fixture also does not false-positive Lint 4a. |
| 9 | Possible `KeyError` on leaf lookup during evaluation | DECLINE | Collection and evaluation now share one traversal (`_compile_boolean_shape`), so this class of desync is structurally impossible — every leaf key evaluated was necessarily collected. |
| 10 | Duplicate-subtree walk edge cases (`not`/`any` interaction, `first_index == 0`) | DECLINE | `is not None` (not truthiness) handles index 0 correctly; `not` recurses into `arg`; nested/deep duplicates are caught as the tests claim. |
| 11 | Skip-note semantics (`report.ok` ignoring notes) | DECLINE | Intentional and tested — "declared limit, not silent skip" is the literal task-brief requirement. |
| 12 | Test infrastructure (`_PACK_PATH`/`_REPO_ROOT` path arithmetic, boundary tests proving what they claim) | DECLINE | Verified: `parents[3]` from the test file resolves to `apps/backend-rag`; the 20-leaf test's `skip_note is None` assertion is only possible if the brute force actually ran. |

Out-of-scope, explicitly declined by design (not raised by kimi, stated up
front in the module docstring): arithmetic-contradiction solving
(`x>5 AND x<3` as the same variable) — a different, much harder tool.

## Verification

```
PYTHONPATH=. pytest backend/tests/scripts/test_visa_engine_compile_claims.py -v
```

61 passed (up from 26 pre-review, 53 after the initial guilt/innocence
pass, +8 from the kimi-k3 findings above). Golden slice (26 rules across
D1/D2/D12/E31B/E31D) unaffected — new lints report clean on every rule in
`research/visa/doctrine-factory/e5/slice-rule-manifest.json`. `ruff
format --check` / `ruff check` clean.
