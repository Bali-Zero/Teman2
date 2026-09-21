# Erratum — evidence pack `agent-air-m5-infra-cate-parity-prose-edcbbd89` (PR #7018)

Condition **C3** of the PASS-WITH-CONDITIONS verdict on PR #7018
([pull/7018#issuecomment-5755487126](https://github.com/Bali-Zero/Teman2/pull/7018#issuecomment-5755487126)),
ledger row `PWC-CONDITIONS for PR #7018` in `.claude/skills/modus/PENDING-ARMS.md`.
Written by the shipping session of #7018. The pack itself is left as it was signed:
this file says where it is wrong, and each correction carries the command that shows it.

A pack whose subject is sentences that outlive their code described its own diff with
sentences that did not survive its own last commit. Every error below has the same
cause: the pack was written against the FIRST draft, and the council's folds changed
the diff under it without the description following.

## 1. `diff.behaviour_change: "None"` — false

The shipped diff adds two executable lines to `DATA_FILES` in
`scripts/tests/test_cate_trigger_parity.py`:

```
+    ".github/workflows/catE-paid-anthropic-baseline.txt",
+    "scripts/tests/test_cate_paid_budget.sh",
```

and the test's behaviour changes with them — deleting either path from the filter now
reds `test_the_data_a_step_reads_starts_the_workflow` on both events, which was the
whole point of the fold. What is true is narrower: the WORKFLOW's executable lines do
not move (stripped of comment lines it hashes `b143df844052a672` before and after).

## 2. `diff.surface` and the receipt `8 insertions, 4 deletions across 2 files` — stale

Both describe the first draft. The squash that landed:

```
$ git show --numstat --format= a467a64173 | grep -v evidence/
6	2	.github/workflows/catE-sovereignty-lint.yml
18	4	scripts/tests/test_cate_trigger_parity.py
```

The test file carries the docstring header (`Four bindings`), the rewritten binding 4,
the `_executable_lines()` comment, a nine-line comment block and the two `DATA_FILES`
entries — not "one docstring line and one comment line".

## 3. Brief constraint 1, "every comment in it [the workflow] is byte-identical" — false

```
$ git show a467a64173 -- .github/workflows/catE-sovereignty-lint.yml | grep -cE '^[+-]\s+#'
8
```

The corrected filter sentence changed under BOTH events. The constraint conflated two
claims; only the first holds: the executable view is identical, the comments are not.

## 4. Dissent row, agy's `xargs` objection — right outcome, false reason, wrong label

The row says RETRACTED because "the two xargs comments on disk say xargs splits on
WHITESPACE … neither mentions exit codes". There are FOUR `xargs` comments on main
(r.350, r.392, r.408, r.412), and r.392-395 is precisely about slices:

> `--files-from, NOT xargs: the tree is ~10.5k paths and xargs would split it across
several processes, leaving the blind-scan guard able to see only one slice at a time.`

So the sentence the seat argued against exists. The seat's error was different: it read
a claim about a LOST EXIT CODE into a sentence about VISIBILITY — the blind-scan guard
counting files it could not see — and on the merits BSD `xargs` exits 1 when any slice
fails, so the exit-code concern does not apply either. The objection is still rejected;
the correct reading is **REFUTED**, by the conducting session against r.392-395.

Why the pack said RETRACTED: `evidence_pack_lint.py` accepts only
`CONFIRMED | PLAUSIBLE | RETRACTED`, and a push was refused until the row used one of
them. RETRACTED means the SEAT withdrew; here the AUTHOR refuted. The schema has no word
for the second, so an author-side refutation can only be filed under a label that
misstates who closed it — noted here, not fixed here.

## 5. The reserve seat was seated without trying the third titolare

`seat_fallback_reason` measures why `codex-gpt-5.6-sol` was unreachable. It says
nothing about `tp1-qwen3.8-max`, the third titolare in `COUNCIL_REVIEW_SEATS_TITOLARI` —
and the reason is that it was **not attempted**. The only evidence about it was the
session-start arsenal probe, eleven hours old, listing it `quota_dead`: a liveness
table, which is exactly what the pack's own `seat_fallback_reason` says it is not.
Zero's ruling is that the reserves do not play while the titolari are available; for
codex that was measured, for qwen it was assumed. The quorum still stands at one
titolare plus one reserve, but the substitution record is incomplete in the direction
that matters.
