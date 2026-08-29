---
date: 2026-08-30
domain: operations
lane: craft-w L12-PR3b (restore-drill wiring)
adversarial_review: codex-gpt-5.6-sol + kimi-code/k3 (round 2 — both DO-NOT-SHIP; this spec IS their findings)
status: SPEC — SUSPENDED under the depth-1 rule, not abandoned
---

# Two evasions in the restore-drill wiring harness, measured and left open

## Why this is a spec and not a third fix round

`docs/plans/2026-08-29-beyond-sota-craft-wave/00-BATTLE-PLAN.md` and the repo's PR contract carry the
same rule: *"A fix-of-a-fix chain stops at depth 1: if the correction is itself wrong, the surface is
under-specified — write the spec, do not open the third PR."*

PR #5261 shipped a corpus pinning `.github/workflows/restore-drill.yml`'s exit-code wiring. Round 1
of adversarial review found twelve defects; all were cured. Round 2 found that **two of those cures
are themselves evadable**. That is the stated trigger, so the cures are not being patched a third
time in the same PR. They are written down here, with reproductions, and a PENDING-ARMS row points at
this file.

One round-2 finding WAS fixed in #5261, because it is not a harness subtlety but a live-path
regression that would misdirect an operator during a real backup failure: the gunzip check ran before
the psql check, so a psql failure (which closes the pipe, giving gunzip SIGPIPE 141) reported
"Backup archive truncated or corrupt". See that PR's own commit message.

## Evasion 1 — the adjacency pins are CONTAINMENT, and a splice defeats them

Found and EXECUTED by the Kimi K3 seat, not inferred.

`test_restore_drill_workflow_wiring.py` asserts that the `PIPESTATUS` capture immediately follows the
restore pipeline, and that `VERIFY_RC=$?` immediately follows the verifier invocation. Both use
containment against the next logical line:

    '_PIPE_STATUSES=("${PIPESTATUS[@]}")' in logical[idx + 1]

`_logical_lines` joins backslash-continuations. So inserting

    echo debugging \

between the pipeline and the capture makes the joined logical line read

    echo debugging _PIPE_STATUSES=("${PIPESTATUS[@]}")

and **all five adjacency assertions still pass** — the seat reported
`{'prev==set +e': True, 'next has capture': True, 'idx+2': True, 'idx+3': True, 'idx+4 == set -e': True}`.

At runtime that line is an `echo`. The assignment never executes, `_PIPE_STATUSES` is unset, and
`set -u` aborts the step mid-drill. **Tests green, drill broken.** The same splice works on the
`VERIFY_RC=$?` containment check.

The cure for the original non-adjacency defect is evadable by the same class of trick it was built to
stop — which is the signal the depth rule is about.

**Proposed fix**: compare the stripped logical line for EQUALITY against the expected capture, not
containment; or assert the joined line's first token is the assignment target. Whichever is chosen,
the guilt fixture is the `echo debugging \` splice above, and it must go red.

## Evasion 2 — `_logical_lines` mis-joins a line ending in a literal `\\`

`ln.rstrip().endswith("\\")` is true for a line ending in a DOUBLE backslash. In bash, `foo\\` at end
of line is a literal backslash then end-of-command, not a continuation. The joiner strips one and
merges with the following line, shifting logical indices inside a bracket window.

Direction: false RED on a correct workflow. Narrow, and introduced by the joiner cure itself.

**Proposed fix**: count trailing backslashes; treat an ODD count as a continuation and an EVEN count
as a literal. Guilt fixture: a line ending `echo "C:\path\\"` followed by a line that must stay
separate.

## Declared, NOT proposed for fixing

Round 2 also raised, and these are deliberately left as stated limits rather than work items:

- The structural psql finder requires the same logical line to contain `gunzip -c` and `psql` and the
  next line to carry the capture. A rewrite to `gunzip -c "$d" > /tmp/x.sql; cat /tmp/x.sql | psql …`
  would attach the capture to `cat | psql`. Adversarial-only; no benign edit produces it, and the
  Kimi seat tried and could not construct one.
- The if/fi balance counter is blind to `&&`, `case`, subshells and functions. Already declared in the
  docstring that asserts it.
- The TG_RC/`exit` same-line rule is evadable by a line continuation. Already declared.
- A `pytest.ini`/`pyproject.toml` carrying `addopts = --collect-only` would make the wiring workflow
  collect without executing. Config files are not in its `paths:`. Raised by the Codex seat; the same
  seat and the Kimi seat both confirmed that a MISSING corpus file exits 4 and a zero-collection run
  exits 5, so the workflow cannot pass without the tests existing — only a deliberate repo-wide
  addopts change defeats it.

## What round 2 could NOT break — recorded so the next reader does not re-attack it

The Kimi seat tried and failed on: `_strip_trailing_comment` (`#` inside single quotes, inside double
quotes, `${#arr[@]}`, `$#`, a `#` in a URL fragment, escaped `\#`, nested quotes); the structural psql
finder against any benign edit; and every vacuity angle on the new wiring workflow — missing file
exits 4, zero collection exits 5, no soft-fail on the install step, `paths:` covers both corpora and
the workflow itself. Its verdict on that last one, verbatim: *"It cannot pass without actually running
the tests."*

## Acceptance for whoever picks this up

Both evasions closed, each with a guilt fixture reproducing the exact splice/`\\` case above, each
proven by MUTATION on the production helper (not by reading the corpus), restored via `cp` + `cmp -s`,
`PYTHONDONTWRITEBYTECODE=1` throughout. And the existing regression set must still kill: `|| true` on
the log tail, `PIPESTATUS[0]`, a dropped `exit "$VERIFY_RC"`, an executable-psql-only `ON_ERROR_STOP`
flip, a deleted `set +e` before the pipe, an emptied `exit 3` branch.
