---
id: memory-budget-gate-hardening
title: Fix MultiEdit predicted-size math treating sequential edits as independent
seat: jules
branch: agent/mini-pro2/infra/memory-budget-gate
scope: .claude/hooks/memory_budget_gate.py, scripts/tests/test_memory_budget_gate.py
acceptance: /Users/nuzantara/nuzantara/.venv/bin/python3 scripts/tests/test_memory_budget_gate.py
status: dispatched
session: sessions/15864235742731785865
dispatched_at: 2026-08-26T18:27:24Z
---

## Where

`.claude/hooks/memory_budget_gate.py`, function `_predicted_size`
(commit `2ac962a52` on branch `agent/mini-pro2/infra/memory-budget-gate`,
open PR #4733 — dispatch against that branch, NOT `main`: the file does
not exist on `main` yet). The exact lines:

```
90:        edits = ti.get("edits") if tool == "MultiEdit" else [ti]
94:            text = path.read_text(encoding="utf-8")
...
108:            occurrences = text.count(old)
...
112:            delta += (_b(new) - _b(old)) * count
113:        return current + delta
```

## What

`text` is read ONCE (line 94) and every edit in a `MultiEdit` payload is
measured against that same, un-mutated snapshot (`text.count(old)` at line
108). The real `MultiEdit` tool applies its edits SEQUENTIALLY — edit N
operates on the result of edit 1..N-1, not on the pre-write file. So when
edit N's `old_string` is text that only exists because an EARLIER edit in
the same call produced it, `text.count(old)` on the original snapshot is
0, `count` becomes 0 (line 108-111), and that edit's real byte delta is
silently dropped from the predicted total.

Concrete failure scenario (this is the one to reproduce as a red test
first, per this repo's TDD discipline): a `MEMORY.md` sitting comfortably
under `HARD_LIMIT_BYTES`, hit with a two-edit `MultiEdit`:

1. `old_string="- some line\n"` (present in the file) ->
   `new_string="<<<MARKER>>>\n"` (small, near-zero net delta)
2. `old_string="<<<MARKER>>>\n"` (does NOT exist in the file BEFORE edit 1
   runs — it is edit 1's own output) -> `new_string=` several hundred
   bytes of new content

`_predicted_size` computes edit 2's `occurrences` against the pre-write
`text`, finds 0, and contributes **0 bytes** for what is actually a large
real write. The gate can therefore report `predicted <= HARD_LIMIT_BYTES`
and allow a `MultiEdit` that, once genuinely applied, pushes `MEMORY.md`
past the harness's ~24.4 KiB silent-truncation cliff — precisely the
failure mode PR #4733 exists to close.

Fix `_predicted_size` so edits inside one `MultiEdit` are simulated
sequentially: maintain a running text (or running byte-length + a
sequentially-updated copy) and apply each edit's replacement to the
result of the previous one before measuring the next `old_string` against
it, mirroring how the real `MultiEdit` tool behaves. Preserve every
existing property (fail-open on any edit whose `old_string` truly isn't
found even after prior edits' simulated effect returns `None` for the
whole prediction — same as today's "occurrences==0 for a non-sequential
edit" case at line 109-111, not a hard error).

## Why

Cicatrice #3 discipline (`.claude/rules/cicatrix-superscar.md`,
"guard-over-match / substring trapping" family, gemello UNDER-match): a
guard that measures the SHAPE of the edits (independent substring counts)
instead of their real, sequential EFFECT is exactly the under-match
pattern that family documents — it stays green on the exact input class
it exists to catch. This directly reopens the disease PR #4733's own
docstring names: "the entries that disappear are the ones at the bottom
... Nothing caught it, because the only existing signal is a POST-write
warning."

## Scope fence

Touch ONLY `_predicted_size`'s `MultiEdit`/`Edit` branch and its test
file. Do NOT touch: `_is_memory_index`, the `HARD_LIMIT_BYTES` default,
the fail-open exit-0 paths, the stderr message text, or any file outside
the two listed in `scope` above. Do not change the gate's Write-tool
branch (already correct — a single `content` string has no sequencing
question).

## Acceptance

Add a new guilt case to `scripts/tests/test_memory_budget_gate.py`
reproducing the two-edit sequential-dependency scenario above and
asserting the gate now BLOCKS (exit 2) a `MultiEdit` whose real applied
effect crosses `HARD_LIMIT_BYTES`, even though edit 2's `old_string` is
absent from the pre-write file. Keep every existing guilt/innocence case
passing (do not weaken G1-G5/I1+ to make the new case pass). Runnable
proof: `/Users/nuzantara/nuzantara/.venv/bin/python3
scripts/tests/test_memory_budget_gate.py` (this file's own `main()`
prints PASS/FAIL per case and exits non-zero on any FAIL — read the
printed count, not just the exit code).
