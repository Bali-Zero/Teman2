# lint_workflow_script Test Fixtures

A miniature `infra/workflows/` tree used by `test_lint_workflow_script.py`. Each file is
crafted to trigger exactly one rule, or to prove exactly one documented exemption does
NOT wrongly trigger — see `scripts/lint_workflow_script.py`'s own docstring for the full
rule/exemption text.

- `repo/infra/workflows/no_model.js` — an `agent(` call whose options object has no
  `model:` key → RULE 1 violation.
- `repo/infra/workflows/gate_label.js` — an `agent(` call whose `label:` contains "gate"
  → RULE 2 violation.
- `repo/infra/workflows/uncapped_loop.js` — a `phase(` span with a `while (` loop and no
  numeric cap or ROUNDS-style constant anywhere in the span → RULE 3 violation.
- `repo/infra/workflows/clean.js` — passes all three rules (innocence).
- `repo/infra/workflows/exemptions.js` — regression guard for the two false positives
  found against the real repo on 2026-09-18: an `agent(promptText, opts)` provenance-
  wrapper call (bare identifier, not an object literal — RULE 1/2 must not fire, the real
  `model:`/`label:` lives at the wrapper's own call sites) and a `for (const x of Y)` loop
  (bounded by its own finite collection — RULE 3 must not fire).
