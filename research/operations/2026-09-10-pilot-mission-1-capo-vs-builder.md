# Pilot mission 1 — Capo Codex vs standalone builder

**Dux:** Claude Opus 5, session `8d5d64cf`, Air-M5, 2026-09-10 01:52–02:23 WITA.
**Mandate:** D3 of `infra/codex-hooks/FABLE-MEASUREMENTS-2026-09-09.md`, Dux confirmed by
Astra, cleared by Zero 2026-09-10.
**Budgets:** `NUZANTARA_MANDATE_ID=pilot-mission-1-20260910`, `budget_mode=enforced`
(8 concurrent, 3600 active seconds, 120 tool calls, 40% of window). Never disabled;
`MANDATE_BUDGET_OFF` never set.
**Adjudicators:** Fable and Astra. **Neither PR may be merged before Fable has read this.**

---

## 1. Verdict in one line

**Arm A (standalone Sonnet 5) produced the deliverable and exhausted its tool budget one
call before it could ship it. Arm B (Codex Capo + Terra + support) produced nothing: it
halted itself at 442 s on the first guard denial, which landed on a read-only search
issued by its support thread.** The comparison Fable asked for — is a Capo cheaper than a
lone builder on a Gear-2 task — is **not answered by this run**, because arm B never
reached the build. What the run does establish is narrower and, I think, more useful: the
two topologies have opposite failure geometries, and the pilot's own instruction text was
the deciding variable. §6 says what I got wrong and §7 asks Fable one question.

---

## 2. The specification both arms received

Frozen before either arm started, byte-identical for both, held at
`scratchpad/PILOT1-SPEC.md` (session-local; reproduced in substance here):

One read-only builtin probe `child_calibration` in `scripts/proprioception.py` plus its
registry entry plus one test file, reporting per `(host, profile, model)` one of
`VALID` / `MISSING` / `EXPIRED` / `VERSION-MISMATCH` / `UNKNOWN` against
`~/.claude/state/child-context-capacities/`, evaluating only currently configured models,
150–250 net lines, one PR, auto-merge not armed.

Two definitions I fixed as Dux, because leaving them open would have made the arms
incomparable:

- **"Currently configured model"** = the declared dispatch roster in the registry entry's
  `args["models"]` (`claude-haiku-4-5-20251001`, `claude-sonnet-5`, `claude-opus-5`) ∪ the
  profile's own `settings.json` `"model"` value, **taken verbatim**. A routing spelling
  such as `claude-fable-5-1[1m]` is reported under that exact string and never
  de-suffixed — this is Fable's blocker 3 restated as a build constraint. A calibration
  record for a model that is not currently configured is ignored entirely: neither a
  finding nor an evidence line.
- **Status precedence:** `UNKNOWN` wins whenever the *inputs* (CLI version, scope,
  capacities dir) are undeterminable; otherwise
  `VALID` > `VERSION-MISMATCH` > `EXPIRED` > `MISSING`.

Six required checks, C1–C6 (test, `--selftest`, ruff, live read-only run with a before/after
sha256 manifest of the capacities dir, diff shape and line count, write-verb grep over the
added code). **I ran all six myself on each arm — generator is never grader**; the arms'
self-reports were compared against my runs, never substituted for them.

---

## 3. Arm A — standalone Sonnet 5 builder (baseline)

Single child, explicitly forbidden to delegate. Worktree
`.worktrees/infra-pilot1-arm-a`, branch `agent/air-m5/infra/pilot1-arm-a`, forked from
`origin/main` at `4eed90f149`.

### Consumption

| metric | value | cap |
|---|---|---|
| wall clock | **1090 s** (18m10s) | — |
| child active time (`budget_elapsed`) | 1043 s | 3600 |
| tool calls (`pretool_count`) | **122** | **120 — exceeded** |
| child tokens (`used`, latest-request accounting) | 196 325 | 400 000 |
| window / measurement | 1 000 000 / `calibrated` | — |
| denials | **2** | — |
| retries | 0 | — |
| Dux (parent) tool calls attributable to arm A | 11 | — |

Ledger row `bc807ad2…`, `budget_mode: enforced`, `max_active: 8`, one reservation at
depth 1, closed `returned_unverified`. Final child-workflow row carries
`budget_reason: tool_calls`, `budget_attention: true`, `return_required: true`,
`claimed_incomplete: true`, `denials: 2`.

### Deliverable

Commit `87b4e79e75`, **+250 / −0 across exactly two files** — `scripts/proprioception.py`
(+115) and `scripts/tests/test_proprioception_child_calibration.py` (+135). Exactly at the
top of the 150–250 band.

### Checks, as run by the Dux

| check | result |
|---|---|
| C1 test file | **9/9 PASS**, exit 0 — all 8 required scenarios, expiry split into TTL-overrun and future-`observed_at` |
| C2 `proprioception.py --selftest` | **OK** — "registry valid (19 probes), parser guards hold, redaction holds" |
| C3 ruff | **0 new diagnostics.** See §6 — the check as I wrote it was defective |
| C4 live read-only run | **PASS.** Probe emits `DIVERGED`, `n_findings: 5`, `duration_ms: 396`; sha256 manifest of the capacities dir **byte-identical before and after** |
| C5 diff shape | **PASS** — two intended files only, +250/−0 |
| C6 write-verb grep over added code | **PASS** — no match |

Live output row:

```
{"id": "child_calibration", "class": "model<->calibration", "status": "DIVERGED",
 "severity": "P3", "n_findings": 5, "duration_ms": 396,
 "evidence": ["m5:~/.claude:claude-haiku-4-5-20251001: VALID",
              "m5:~/.claude:claude-sonnet-5: VALID",
              "m5:~/.claude:claude-opus-5: VALID",
              "m5:~/.claude:claude-fable-5-1[1m]: MISSING",
              "m5:~/.claude-acct2:claude-haiku-4-5-20251001: MISSING"]}
```

Design notes worth Fable's eye: the probe reuses `TTL`, `scope()` and `scoped_path()` from
`child_context.py` through a guarded `spec_from_file_location` import and degrades to
`UNPROBEABLE` — not a crash — when the module is absent; it sets `CLAUDE_CONFIG_DIR` per
profile and restores it in a `finally`; a malformed record **at the configured model's own
path** reads `UNKNOWN`, while an unrelated malformed file in the directory is skipped
rather than blamed on a model. Evidence lines carry host, profile dir name, model and
status only — no scope hash, no `session_id`, no token count.

### Shipping

The builder was denied `git push`. **I pushed and opened PR #6054 as Dux.** That is the
role D3 assigns me ("Capo contributes and never verifies; the Dux integrates"), and the
denial was a child *resource* cap, not a permission the session lacks. Recording it
plainly: arm A **built** the thing and **did not ship** it. Auto-merge is not armed.

---

## 4. Arm B — Codex Capo + Terra builder + 1 support

`codex exec`, codex-cli 0.153.4, `gpt-5.6-sol`, `model_reasoning_effort=high`, with the
pre-existing `[agents] max_threads = 3 / max_depth = 1` in `~/.codex/config.toml` — the
cap D3 specifies, already in force, not set by me. Worktree
`.worktrees/infra-pilot1-arm-b`, same base commit, same spec file, same C1–C6, same
"report denials verbatim, disable nothing" clause.

### Consumption

| metric | value |
|---|---|
| wall clock | **442 s** (7m22s) — 41% of arm A, far under the 2180 s kill line |
| command executions | 18 |
| `collab_tool_call` (Capo↔threads) | 6 (3 × `wait`, paired started/completed) |
| agent messages | 7 |
| input tokens | 1 513 164, of which **1 422 976 cached** |
| **non-cached input** | **90 188** |
| output tokens | 7 197 (3 394 reasoning) |
| net lines delivered | **0** |
| commit / PR | none |

Kill conditions were never reached: B stopped itself well inside both the 2× wall-clock
(2180 s) and any reading of the 1.5× budget line.

### What happened

The Capo read the spec, inspected the existing probe contracts, delegated the
implementation to Terra and a read-only review of the integration points to the support
thread. Terra had designed nine TDD cases and had not yet written the RED test. The
support thread then issued a broad read-only `rg` across `infra scripts docs research`
and was denied by the Codex-side bridge hook:

```
Command blocked by PreToolUse hook: Native child 01a08763-24aa-7281-be43-bea3b2f275fb:
task role builder; return checkpoint and remaining work to parent
01a08761-7e61-7751-b526-b24b68388a47. Never launch an autonomous continuation or modify a
parent handoff. Use assigned scope, checks and shared mandate budget. A result remains
unverified until the coordinator independently accepts it. Checkpoint helper:
/Users/balizero/nuzantara/.venv/bin/python
/Users/balizero/.codex/hooks/nuzantara-context/context_bridge.py checkpoint
01a08763-24aa-7281-be43-bea3b2f275fb with JSON {"objective":"...","next_action":"return to
parent","remaining":["..."],"risks":[]}.
Command: rg -n "child_calibration|calibration receptor|currently configured|
child-context-capacities|VERSION-MISMATCH|claude-acct2|model<->calibration"
infra scripts docs research --glob '*.md' --glob '*.py' --glob '*.json' | head -n 240
```

The support thread saved the requested checkpoint. The Capo then halted **all three
threads** and reported, per the arm's instruction to stop and report any denial verbatim.
No guard was disabled or worked around; the worktree is clean, nothing staged, nothing
stashed. Checks: C5 run (empty diff, 0 lines — requirement not met); C1–C4 and C6 never
run.

Also recorded: one non-fatal `error` item at startup — *"Skill descriptions were shortened
to fit the skills context budget."* The Codex seat is starting near its context ceiling
before the mission text is even read, consistent with what the Pro session measured on
2026-09-09 (52–59k of AGENTS.md + app instructions + hooks at hop zero).

---

## 5. Ledger `needs_attention` and every denial — the pilot's required record

### Ledger (`~/.claude/state/child-mandates/`)

- **`pilot-mission-1-20260910` → `needs_attention`, reason "Child observed without a
  dispatch reservation".** This is the `observe()` race Fable filed as non-blocking in the
  re-review of `09d79d32` ("`observe()` still binds an unreserved child to the first free
  `reserved` row; pre-existing race, no new evidence"). **This run is that evidence**, and
  it is the first occurrence recorded under `budget_mode=enforced` rather than
  `interactive_observation`. The mandate's single reservation nonetheless closed correctly
  as `returned_unverified` — the flag fired without a leak.
- Four other mandates carry the same reason and two carry "Interactive session counters
  exceed one mandate budget" — all pre-date this pilot; listed for context, not attributed
  to it.

### Child denials (`~/.claude/state/child-workflow/`)

- **Arm A, 2 denials**, both the same text, on `Bash` (`git push`), then on `ToolSearch`
  and `SendMessage`:

  > `PreToolUse:Bash hook error: [python3 /Users/balizero/.claude/hooks/child_workflow.py context]: Child context budget reached. Return a checkpoint and remaining work to the parent. Child workflow: use the assigned objective, write scope, expected result, constraints and checks. Do not inherit the coordinator's rank. …`

  **The finding here is not the cap, it is the channel.** The same gate that stopped the
  work also stopped `SendMessage` — the child was denied the very tool it needed to report
  the denial. It reached me through an idle notification instead. A budget that silences a
  child's report channel makes the coordinator's `attention` report the only consumer, and
  that report is exactly what R1 was written to keep clean. Recommend exempting
  `SendMessage` (and a bounded `ToolSearch` for it) from the context-budget gate, or
  emitting the checkpoint automatically on the denying call.

- **Arm B, 1 denial** (the Codex bridge role gate, quoted verbatim in §4) — on a
  **read-only** `rg`. Nothing was mutated, nothing attempted outside the worktree.

- **Four `stop_blocked` / `stop_reminded: true` rows**, two in arm A's window
  (`1788976494`, `1788976784`) and two in arm B's (`1788977979`, `1788978157`): children
  tried to stop and were sent back to work. Arm A's two preceded a genuinely incomplete
  state, so the reminder did its job; arm B's followed the halt.

### Dux-side denial

One, worth recording because it is a false positive: `worktree_isolation.py` blocked a
`shasum … > "$S/measure/…"` whose target was the session scratchpad, because the hook
resolved the shell variable `$S` as a literal path segment and read it as a write into the
main checkout. Harmless here (absolute paths worked), but a hook that string-matches an
unexpanded variable will deny correct commands — superscar #3, guard-over-match, in its
OVER form.

### Read-only proof for the whole pilot

The sha256 manifest of `~/.claude/state/child-context-capacities/` taken at 01:53 and at
02:23 is **identical**. Neither arm, and no check I ran, mutated calibration state.

---

## 6. What I got wrong, as Dux

Two defects in my own instrument. Both are mine, not the arms'.

1. **C3 was mis-specified.** I wrote "`ruff check <both files>` → clean". `proprioception.py`
   carries 3 pre-existing `E741` on `origin/main` at lines 412/441/445, in
   `probe_git_alignment` and `probe_produced_promoted` — probes the spec forbade touching.
   As written, C3 graded code neither arm was allowed to fix, and was unpassable by
   construction. I graded it, identically for both arms, as **"introduces zero new ruff
   diagnostics"**, verified by running ruff against the base blob (3 errors) and the arm's
   blob (same 3, same lines). Arm A independently reached and stated the same reading.
2. **The denial clause decided the outcome.** Both arms were told, in the same words, to
   "STOP and report the denial verbatim". In arm A the first denial arrived *after* the
   build was finished, so the clause cost nothing. In arm B it arrived at minute seven, on
   a support thread's read-only search, and the clause cost the entire arm. **A Capo has
   three surfaces on which to catch a denial and a lone builder has one**; an instruction
   that halts on the first denial therefore penalises the wider topology in direct
   proportion to its width. I did not see that when I froze the spec. Arm B obeyed the
   instruction it was given; it did not fail the task.

One non-defect worth flagging to Fable as a receptor-design observation, not a spec
violation: the runner caps `evidence` at 5 lines while `n_findings` carries the true count.
Arm A's probe emits `VALID` rows into that list, so on M5 three of the five printed lines
are healthy triples and only two of the five actual findings are visible. The probe is
correct; the operator's view is not. Suggest emitting non-`VALID` rows first, or a single
summary line plus findings.

---

## 7. What I am asking Fable and Astra to decide

The mandate's question — Capo vs lone builder on a Gear-2 task — has **no measured answer
from this run**, and I will not manufacture one from 442 seconds of coordination.

Given §6.2, there are two honest readings, and choosing between them changes the pilot's
terms, which is not mine to do:

- **(a) The run stands as recorded.** Arm B's halt is a real property of the topology under
  the fleet's current guards: three surfaces, three chances to be stopped, a coordinator
  that correctly refuses to route around a guard. Then the answer to D3 is that the Capo is
  not yet viable *here*, and the fix is to the Codex bridge's role gate (it denied a
  read-only search) before any re-run.
- **(b) Run B-2 with the denial clause repaired**, identically re-worded for both arms —
  "report every denial verbatim and immediately; halt the arm only if the denial blocks the
  deliverable itself" — and re-baseline A under the same wording. This measures the
  topology instead of my sentence, and costs one more Sonnet 5 run plus one more Codex run.

My recommendation is **(b), preceded by (a) being recorded as a finding in its own right**,
because the arm-B denial on a read-only `rg` is a bridge defect that will bite any Capo
mission, and because arm A's `SendMessage` denial is a reporting-channel defect that will
bite any child mission. Both are worth fixing whether or not the pilot re-runs.

---

## 8. Artefacts

| item | location |
|---|---|
| Arm A PR (**do not merge, not armed**) | #6054, branch `agent/air-m5/infra/pilot1-arm-a`, commit `87b4e79e75` |
| Arm B branch | `agent/air-m5/infra/pilot1-arm-b` — no commit, clean, still at `4eed90f149` |
| Frozen spec | session scratchpad `PILOT1-SPEC.md` |
| Capo prompt | session scratchpad `PILOT1-CAPO-PROMPT.md` |
| Arm B event stream, last message, stderr | session scratchpad `measure/armB.*` |
| Arm A denial, verbatim | session scratchpad `measure/armA.denial.txt` |
| Capacity manifests (before / A / final) | session scratchpad `measure/capacities.*.sha` |
| Ledger and child-workflow snapshots | session scratchpad `measure/child-{mandates,workflow}.before*` |

Session scratchpad paths are host-local and session-scoped; they are evidence for this
report, not a durable store. Say the word and I will copy the measurement set into the repo
alongside this file.
