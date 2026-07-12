---
date: 2026-07-11
domain: compliance
client_case: null
adversarial_review: gpt-5.5
sources:
  - infra/claude-hooks/worktree_isolation.py
  - infra/claude-hooks/guard_fuzz_harness.py
  - infra/claude-hooks/test_segment_scoped_dispatch.py
  - .claude/rules/cicatrix-superscar.md (#3)
  - .claude/rules/cicatrix-scars.md (W83/W84/W85/W91/W92 entries)
  - infra/guard-conformance/registry.json + check_guard_conformance.py
  - PR #2266 (this lane's deliverable, gate bounce + revise)
---

# Lane S3 (IMMUNE) — guard fuzz harness + W92 fix + Pro ff-only allowlist

## Mandate

Kill superscar family #3 (guard-over-match) at the root **on
`worktree_isolation.py` specifically** — its most recidivist guard:
`infra/claude-hooks/worktree_isolation.py` had produced FOUR documented
over-matches in sequence before this run (W83, W84, W85, W91), each fixed
only after a live false-block already bit someone in production use. This
does NOT close the family across every guard in the codebase —
`host_boundary.py` is a known sibling with the same write-target-extraction
shape and is explicitly NOT audited by this lane (see the fenced finding
below). Also implement PENDING-ARMS "Pro main self-align strutturalmente
chiuso" (iteration 5): a runtime-state allowlist so Pro's 3
perennially-dirty tracked files stop shutting the ff-only-pull exception.

## §Meta-pattern — why does THIS guard keep biting?

Four structural reasons converge on `worktree_isolation.py` specifically,
and understanding them is the actual deliverable (the fuzz harness is the
tool; this is the diagnosis the tool exists to act on):

1. **Two independent decision channels sharing one docstring, not one
   implementation.** The file blocks BOTH mutating git verbs (`main()`'s
   git-verb path) AND shell file-writes (`_write_hits_main`). Every fix so
   far (W83, W84, W85, W91) landed in the git-verb channel. W92 proved the
   file-write channel is a SEPARATE decision surface that inherited none of
   those fixes — `_is_remote_dispatch` was wired into the git-verb path at
   W83 and simply never reached the write-target scanner. A guard with two
   channels needs its blind-spot audit run TWICE, once per channel, or a
   fix to one silently leaves the twin unpatched.

2. **Negative-gating (fail-open on uncertainty) is the intended default, but
   the family's actual failures run in BOTH directions, not just one.**
   The file's own docstring states the philosophy explicitly: "defense
   conservative — a global L1 hook on 3 machines must NOT false-positive"
   (i.e. must not falsely BLOCK). In practice the six over-matches split:
   W83, W84, W85, and W91 (git-verb channel) and this run's own W92
   (write-target channel) are each a shape that got wrongly classified
   as a MATCH and produced a false BLOCK — the opposite of "ambiguous
   therefore allow." The "6th over-match" found at this same PR's gate
   (§Gate bounce below) is the true false-allow instance: the
   whole-command `_is_remote_dispatch` exemption let a genuine local
   write/git-pull through when only an earlier segment was remote. So the
   family is not one causal pattern (ambiguous→allow) — it's a guard whose
   classifier fails in both directions depending on which check is
   under-scoped, and the fail-open default only explains the false-allow
   half. That tail is exactly what a hand-written regression suite cannot bound
   — it only ever covers the shape someone already got burned by.

3. **Shell syntax is combinatorial; hand-picked examples are not.** Quotes,
   comments, newlines, heredocs, pipes, `&&`/`;`/`|` segment boundaries,
   ssh/scp/rsync wrapping, and git-verbs-appearing-as-text all compose with
   each other. Five scars in six weeks is not five independent bugs; it is
   one under-sampled space. `guard_fuzz_harness.py` (382 generated cases
   across BOTH channels) is the structural answer: instead of adding case
   #6 to a list of examples, generate the CROSS PRODUCT of verb × wrapper ×
   channel and let mismatches surface proactively.

4. **Every "fix" is itself a guard with an inverted sign.** W91 already
   named this for the ff-only exception ("an eccezione a segno invertito,
   vuole guilt+innocence propri"); this run extends it: the runtime-state
   ALLOWLIST added here is ALSO an exception, and needed its own
   guilt+innocence proof (see below) — and during that very test-writing I
   found a real bug (Python default-parameter late-binding froze the
   allowlist path at function-definition time). The lesson generalizes past
   ff-only: any code that says "except when X" is a second guard hiding
   inside the first one's docstring, and the org's C2 conformance rule
   ("nessuna guardia mergiata senza guilt+innocence") should read as
   applying to every `if`/`except` branch inside a guard function, not just
   the guard's own top-level verdict.

   **§Gate bounce, 2026-07-11 ~22:10 WITA — this exact prediction came true
   on THIS SAME PR before merge.** The gate-reviewer found a REAL under-match
   in this lane's own W92 fix: `_is_remote_dispatch` — the exemption W92
   reused — was itself a WHOLE-COMMAND check, not scoped to any particular
   segment of a compound command. `ssh mini hostname && cp /tmp/x scripts/f.py`
   and `ssh pro hostname; tee scripts/g.py < /tmp/y` both got wrongly exempted
   (the remote segment is the PRELUDE `hostname`; the actual write lives in a
   LATER, LOCAL segment). Attribution: the git-verb channel had carried the
   SAME hole on `main` since W83 — `ssh pro hostname && git pull origin main`
   passed TODAY before this fix, unrelated to this PR's own changes; W92's fix
   simply replicated an existing disease into a second channel by reusing the
   function verbatim, exactly as designed, exactly as the meta-pattern above
   predicts EVERY exception will eventually need its own guilt+innocence.
   This is the **6th over-match** of the family on this guard.

   **Fix**: segment-scoped exemption. `_segments()` splits the noise-stripped
   command on `&& || ; |`; `_is_position_remote_dispatched(cmd_scan, pos)`
   answers "is the segment CONTAINING this character offset itself
   remote-dispatched" rather than "is ANY segment of the whole command
   remote-dispatched." Applied to BOTH channels: the git-verb channel checks
   `all(_is_position_remote_dispatched(...) for m in blocked_matches)` (every
   matched verb must sit in its own remote segment); the write-target channel
   made `_extract_write_targets` return `(path, offset)` pairs so each target
   is segment-scoped individually.

   **A SEVENTH near-miss, found while fixing the sixth, in the SAME turn**:
   the fuzz harness's `run_corpus()` had RE-IMPLEMENTED the git-verb decision
   inline (its own stale hand-copy, using the pre-fix whole-command check) —
   so after applying the segment-scoping fix to the real guard, the harness
   reported 24 "mismatches" that were harness-drift, not guard bugs. This is
   the EXACT failure mode the harness's own docstring says it exists to
   prevent ("BEFORE the sixth over-match ships"), now manifesting as the
   tool's own reimplementation drifting from the fix in real time. Structural
   cure (not a patch): extracted the git-verb decision into a pure,
   unit-testable `_git_verb_verdict(cmd, cwd) -> GitVerbVerdict` function in
   `worktree_isolation.py`, called by BOTH `main()` and
   `guard_fuzz_harness.py::run_corpus()` — a single source of truth so the
   two paths can never diverge again. A SECOND test file
   (`test_segment_scoped_dispatch.py`) initially wrote its OWN
   `_simulate_git_channel` reimplementation too (written before
   `_git_verb_verdict` existed, in the same response) — caught and fixed
   before commit by replacing it with a one-line call to the real function.
   Three independent copies of the same 12-line decision tree existed
   simultaneously for a few minutes of this session (main(), the harness, the
   new test) before converging on one. **The meta-pattern needs a fifth
   entry**: a fix that reuses logic via COPY (not a shared callable) silently
   commits to keeping N copies in sync forever; the harness's own genesis
   docstring already names the disease ("a hand-written regression suite only
   covers shapes someone already got burned by") without naming that a fuzz
   HARNESS can get the same disease if its classifier is a copy, not a call.

## §Solo-operatore — live-hook propagation one-liner

This PR ships the REPO CANON (`infra/claude-hooks/`). The live PreToolUse
hook that Claude Code actually invokes on each machine lives at
`~/.claude/hooks/` — a separate, operator-owned control-plane copy (per
CLAUDE.md §2: "`~/.claude/hooks/` control-plane one-liners" is a true
operator-only category, `host_boundary` stays hard by design, and this
file's own installer explicitly does NOT auto-propagate). Per precedent
(#2022/#2026, the same pattern used for W91), propagation is a manual,
reviewable step — never auto-applied by an agent:

```bash
# On EACH machine (M5 / Pro / Mini), after this PR merges to main:
cd ~/Desktop/nuzantara && git pull --ff-only origin main   # picks up the repo canon
bash infra/claude-hooks/install_worktree_hooks.sh          # installs + self-verifies via test_hook_innocence.py, rolls back if red
```

`install_worktree_hooks.sh` (pre-existing, unmodified by this lane) already
backs up any file it overwrites and refuses to leave a broken hook live —
it runs the innocence vaccine after copying and rolls back on red. This
lane changed `worktree_isolation.py` (W92 fix) and added 2 new files next
to it (`guard_fuzz_harness.py`, `runtime_state_allowlist.json`) that the
installer's existing `HOOKS=(...)` array does NOT copy (it only lists
`worktree_isolation.py worktree_file_write_check.py`) — the fuzz harness
and the allowlist config are CI/dev-time artifacts, not live-hook payload,
so no installer change was needed for them. Only `worktree_isolation.py`
itself needs the re-copy above.

## Deliverables (this PR, #2266)

1. **`infra/claude-hooks/guard_fuzz_harness.py`** — reusable property/fuzz
   corpus runner (`Case` NamedTuple + `run_corpus()`), guard-agnostic BY
   DESIGN (the `Case`/corpus-generator shape is meant for reuse by a future
   guard's own corpus function) but NOT YET guard-agnostic in its current
   caller: `run_corpus()` calls `mod._git_verb_verdict()` and
   `mod._write_hits_main()` directly (`guard_fuzz_harness.py:358` area) —
   both are `worktree_isolation.py`-specific symbols, so a second guard
   (e.g. `host_boundary.py`) needs either a parametrized classifier
   argument or its own runner copy before this harness actually runs
   against it. Generates 445 cases (382 original + 63 true-compound
   remote-prelude cases added at the gate bounce): 8 mutating git verbs ×
   5 wrapper classes (noop, remote-dispatch, text-only,
   deceptive-local-under-match, true-compound-remote-prelude) + 6
   read-only verbs × 4 wrapper classes + 7 ff-only-pull segment variants,
   on the git-verb channel; 7 write-verbs × 7 destination/quoting/compound
   shapes + 2 scp/rsync colon-dest cases + heredoc/commit-message noise +
   sinks, on the write-target channel. `python3
   infra/claude-hooks/guard_fuzz_harness.py --list` prints corpus size
   without executing; bare invocation classifies every case and reports
   unexplained mismatches, exit 1 on any. `run_corpus()`'s git-verb branch
   now calls the real `mod._git_verb_verdict()` (see §Gate bounce) instead
   of a hand-copy of the decision.

2. **W92 fix** (`infra/claude-hooks/worktree_isolation.py::_write_hits_main`):
   started as a one-line reuse of the existing whole-command
   `_is_remote_dispatch` check (same function W83 already proved correct
   for the git-verb channel), applied upstream of `_extract_write_targets`
   — but that whole-command check is exactly what the gate bounce (§Gate
   bounce below) proved defective (6th over-match: it exempts a compound
   command the instant ANY segment is remote-dispatched, even when the
   actual write lives in a later local segment). The version that
   shipped in this PR therefore calls the segment-scoped
   `_is_position_remote_dispatched()` instead
   (`worktree_isolation.py:535`), not the whole-command
   `_is_remote_dispatch`. Pinned by `test_w92_remote_write_dispatch.py`
   (13 innocence + 8 guilt — 2 cases corrected at the gate bounce, see
   §Gate bounce).

3. **Runtime-state allowlist** (`infra/claude-hooks/runtime_state_allowlist.json`
   + `worktree_isolation.py::_main_tree_tracked_clean`): declares 3 Pro-only
   tracked files as expected runtime residue for the ff-only-pull exception,
   machine-scoped (mirrors `scripts/lint_home_fork.py`'s `machine_label()`
   convention: `air-m5`→`m5`, `*mini*`→`mini`, `nuzantara`→`pro`). Pinned by
   `test_runtime_state_allowlist.py` (2 innocence + 5 guilt + 1 integration
   + 1 baseline). During test-writing, found and fixed a real bug: the
   allowlist-path parameter used a Python default value, which binds ONCE
   at function-definition time — any runtime reassignment of
   `RUNTIME_STATE_ALLOWLIST_PATH` was silently ignored. Fixed to resolve
   the module-global at call time instead.

4. **Segment-scoped remote-dispatch fix** (6th over-match — see §Gate
   bounce for the full trauma text): `_segments()` +
   `_is_position_remote_dispatched()` in `worktree_isolation.py`, applied to
   both channels; `_git_verb_verdict()` extracted as the single pure
   decision function both `main()` and the fuzz harness call. Pinned by
   `test_segment_scoped_dispatch.py` (4+4 innocence + 4+5 guilt across both
   channels).

5. **Registry + CI wiring**: `infra/guard-conformance/registry.json`
   updated (0 violations from `check_guard_conformance.py`); 4 explicit
   execution steps in `.github/workflows/guard-conformance.yml` (not just
   ancestor-dir path-filter substring match — this workflow's own comments
   call that pattern out as W81 "esiste != armato" theater, citing the
   exact same trap for the pre-existing W83/W84 suites before this workflow
   became their direct executor).

## Verification (empirical, this run — post gate-bounce revise)

All 15 test files under `infra/claude-hooks/` pass individually
(`test_arm_keep_hook`, `test_block_regex`, `test_ffonly_pull_exception`,
`test_hook_innocence`, `test_host_boundary`, `test_phase`,
`test_premise_gate`, `test_runtime_state_allowlist` [new],
`test_segment_scoped_dispatch` [new, gate bounce], `test_tilde_target_resolver`,
`test_w79_shell_write`, `test_w83_remote_dispatch`,
`test_w84_strip_noise_cross_line`, `test_w85_stash_readonly`,
`test_w92_remote_write_dispatch` [new, 2 cases corrected at gate bounce]).
`guard_fuzz_harness.py` reports 445/445 with 0 unexplained mismatches.
`check_guard_conformance.py` reports 0 violations (2 real phantom-link
violations were caught and fixed mid-revise — see §Gate bounce). Pre-commit
(lease-check, anti-reward-hacking lint, secrets scan, prettier, typecheck,
Python lint, off-limits-file check) and pre-push hooks both green on the
original commit; the revise commit repeats the same battery before push.

**Process note (transparency, not spin)**: mid-revise, a verification
command run without an explicit `cd`/absolute path picked up the AMBIENT
shell cwd, which had silently drifted to the read-only main checkout
between separate Bash tool calls (this harness resets cwd per-call — a fact
I had not been respecting). This produced a false alarm that looked like
"my earlier commit vanished" (grep on the main checkout's untouched copy of
`worktree_isolation.py`/`registry.json` found none of my new symbols). No
data was lost and the main checkout was never written to — `git status
--porcelain` there stayed clean throughout except for one pre-existing
sibling-owned file. Root cause was purely diagnostic: I re-verified with
explicit absolute paths and confirmed the worktree branch/commit were
intact. Filed as a live instance of superscar #6 (anti-hallucination
blindness) against MYSELF mid-task, not a new scar — the antidote already
prescribed ("mai costruire su un file/path citato... senza aver fatto
find/ls/cat per validarlo fisicamente in questo turno") is exactly what
caught it once applied.

## Live finding, deliberately NOT touched (fenced — flag for a future lane)

`infra/claude-hooks/host_boundary.py` clones the W79 write-target
extraction VERBATIM (its own docstring says so: "Reuses the W79 Bash-write-
target extraction (verbatim) from worktree_isolation.py") but has ZERO
`_is_remote_dispatch` awareness in its clone — grep confirms no reference
to that symbol anywhere in the file. The exact W92 shape (an
ssh/scp/rsync-dispatched write with a relative destination landing under a
protected path like `~/.claude/` or `~/.ssh/`) is a plausible LATENT twin
bug there. This was NOT fixed in this PR: the mandate fences other guards
untouched unless they get their own tests, and `host_boundary.py` is
explicitly control-plane / "stays hard by design" per CLAUDE.md §2 — it
guards the phase-switch itself and is deliberately harder to modify than
an ordinary hook. Recommended next step: a follow-up lane applies the SAME
harness (already guard-agnostic by design) with a `host_boundary`-specific
corpus generator reusing the `Case`/`run_corpus` primitives.

**Updated by the gate-bounce finding**: if/when that follow-up lane ports
the W92 fix into `host_boundary.py`, it must port the SEGMENT-SCOPED version
(`_is_position_remote_dispatched`), not the whole-command
`_is_remote_dispatch` this report originally pointed at — porting the
pre-bounce fix would import the 6th over-match into a third file on day
one. Whoever picks this up should read §Gate bounce above first.

## PENDING-ARMS ledger deltas

- **NOT YET CLOSE — conditional**: "Pro main self-align strutturalmente
  chiuso" (opened 2026-07-06) — closes only when BOTH (1) PR #2266 merges
  AND (2) the live hook copy on Pro is aligned (`install_worktree_hooks.sh`
  re-run per §Solo-operatore above, so `_main_tree_tracked_clean()` with
  the new allowlist is actually the code Pro's PreToolUse hook executes).
  Iteration 5 (runtime-state allowlist) ships CODE in this PR, but the
  ledger's own success criterion — "pull ff-only autonomo ATTRAVERSA su
  Pro con i 3 runtime file dirty E resta BLOCCATO con un file tracked
  non-runtime dirty" — is proven here only by synthetic unit tests
  (`test_runtime_state_allowlist.py`), not by a live pull on Pro with the
  new hook installed. Owner: `agent[repo-side]` until both conditions are
  met; this matches what PENDING-ARMS.md already records for this line.
- **OPEN** (new, this run): "host_boundary.py W92-twin audit" — the
  write-target extraction clone in `host_boundary.py` has no
  `_is_remote_dispatch` awareness; same shape as W92, unverified whether
  live-exploitable (protected paths are narrower than the main-checkout
  surface W92 hit, but the mechanism is identical). Owner:
  `agent[future-lane]`. Not urgent (control-plane paths are a much smaller
  practical target than "any relative path under the repo"), but should
  not be forgotten — tracked here and in this report rather than the ledger
  file directly (serialization rule: this lane never edits PENDING-ARMS.md
  in place, only proposes the delta in this report). **Updated**: if ported,
  must port the segment-scoped fix, not the pre-bounce whole-command one.
- **CLOSE** (this run, gate bounce): "S3-immune GATED: BOUNCED (REVISE)"
  (orchestrator ledger line, 2026-07-11 ~22:10 WITA) — segment-scoped
  exemption shipped on both channels, corpus expanded with 63 true-compound
  cases, report updated with the trauma text, all in this same PR (#2266,
  still unarmed for re-gate). Scar filing for the 6th over-match deferred to
  orchestrator serial reconciliation per instruction (W-number collision
  live the night this was found) — trauma/antibody/gotcha text for that
  filing is the §Gate bounce section above, ready to paste verbatim into
  cicatrix-scars.md + a MEMBRI line in cicatrix-superscar.md #3 once a free
  W-number is assigned.

## Files touched (absolute paths)

- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/infra/claude-hooks/worktree_isolation.py` (modified — W92 fix + allowlist wiring + segment-scoped 6th-over-match fix + `_git_verb_verdict` extraction)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/infra/claude-hooks/guard_fuzz_harness.py` (new, then revised at gate bounce — true-compound corpus + calls real `_git_verb_verdict` instead of a stale reimplementation)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/infra/claude-hooks/runtime_state_allowlist.json` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/infra/claude-hooks/test_w92_remote_write_dispatch.py` (new, then corrected at gate bounce — 2 cases moved from innocence to guilt, `ssh mini echo x | tee` genuinely writes locally)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/infra/claude-hooks/test_runtime_state_allowlist.py` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/infra/claude-hooks/test_segment_scoped_dispatch.py` (new, gate bounce — 6th over-match guilt+innocence, both channels)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/infra/guard-conformance/registry.json` (modified, twice — initial + gate-bounce symbols)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/.github/workflows/guard-conformance.yml` (modified, twice — initial 3 steps + gate-bounce 4th step)
- `/Users/balizero/Desktop/nuzantara/.worktrees/infra-guard-fuzz/research/operations/2026-07-11-guard-fuzz-immune.md` (this report; committed to the PR branch per gate instruction)
- PR: https://github.com/Balizero1987/Teman2/pull/2266 (branch `agent/air-m5/infra/guard-fuzz`, commit `182114e7db` + gate-bounce revise commit)

## Adversarial review

- Seat: gpt-5.5 (Codex CLI, fresh context, read-only) — 2026-07-12
- Verdict as returned: REFUTED (5 findings)
- (a) "Kills superscar #3 at the root" / "guard-agnostic runner" → CONFIRMED: `host_boundary.py` clones the write-target extraction verbatim with zero `_is_remote_dispatch`/`_is_position_remote_dispatched` awareness (grep confirms), and `run_corpus()` calls `mod._git_verb_verdict()` / `mod._write_hits_main()` directly — hard-wired to `worktree_isolation.py`, not a parametrized classifier. Mandate and deliverable §1 reworded to scope the claim and name the harness's actual current coupling.
- (b) "Every prior fix landed only in the git-verb channel; every failure was ambiguous→allow" → CONFIRMED false as a single pattern: W83/W84/W85/W91 and this run's own W92 are false-BLOCKS (over-matches on a shape wrongly classified as a match), confirmed by the file's own docstring language ("phantom write-target... false BLOCK") and the W84/W85 scar text. Only the 6th over-match (whole-command `_is_remote_dispatch` exemption) is the true false-allow instance. Meta-pattern point 2 reworded to state both directions instead of one causal claim.
- (c) "W92 fix is one-line reuse of proven-correct `_is_remote_dispatch`" → CONFIRMED stale: `worktree_isolation.py:535` shows the shipped `_write_hits_main` calling `_is_position_remote_dispatched` (segment-scoped), not the whole-command `_is_remote_dispatch` this sentence names — the sentence described the pre-gate-bounce draft. Deliverable §2 corrected to describe the final segment-scoped design.
- (d) "13 innocence + 7 guilt" → CONFIRMED arithmetic error: counted directly in `test_w92_remote_write_dispatch.py` — 13 items in `innocent`, 8 items in `guilty`. Corrected to 13/8 in deliverable §2.
- (e) "CLOSE: Pro main self-align strutturalmente chiuso" → CONFIRMED unsupported: the report's own §Solo-operatore section says the live hook on Pro is "not yet live-armed" until `install_worktree_hooks.sh` re-runs, and PENDING-ARMS.md's own success criterion (a live ff-only pull on Pro with the 3 runtime files dirty) is proven here only by synthetic unit tests. Ledger delta reworded to "NOT YET CLOSE — conditional" (merge + live re-arm both required), matching PENDING-ARMS.md.
