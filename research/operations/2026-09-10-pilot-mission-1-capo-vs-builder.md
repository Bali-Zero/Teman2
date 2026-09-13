---
date: 2026-09-10
domain: operations
client_case: none — internal harness pilot, no client data touched or transcribed
sources:
  - infra/codex-hooks/FABLE-MEASUREMENTS-2026-09-09.md (D3, the mandate)
  - ~/.claude/state/child-mandates/ and child-workflow/ (arm A ledger and denials)
  - ~/.codex/state/nuzantara-context/ (arm B and B-2 bridge state, token flips)
  - PR #6056 comment 5606815682 (Fable's adjudication, appended verbatim as section 9)
# R1 gate: this report WAS adversarially reviewed — by Fable 5.1 (session nuzantara-40),
# who is not its author and who posted a PASS-WITH-CONDITIONS gate whose correction is
# incorporated in sections 1, 4 and 7 and quoted verbatim in section 9:
# https://github.com/Bali-Zero/Teman2/pull/6056#issuecomment-5606815682
# `exempt-` is used only because KNOWN_SEATS in scripts/check_adversarial_review.py has
# no spelling for a Fable seat (it lists glm/kimi/codex/gemini/agy/grok/nlm/qwen). Adding
# one is a gate-vocabulary change and does not belong in a docs PR — flagged to Zero.
adversarial_review: exempt-reviewed-by-fable-5-1-no-seat-spelling
---

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
halted itself at 442 s on the first guard denial — its support thread had crossed the
Codex bridge's 40 % context budget (103 360 of a 258 400 window) at its third request,
and the deny message named the role contract instead of the number.** The comparison Fable asked for — is a Capo cheaper than a
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
and was denied by the Codex-side bridge hook.

> **Corrected 2026-09-10 by Fable's adjudication (§9), and verified on disk by the Dux.**
> The paragraphs below originally read this denial as a *role gate* firing on a read-only
> search. That is wrong. `context_bridge.py` denies EVERY `PreToolUse` once
> `return_required` is set, and it flips at `last_token_usage >= 0.4 × 258 400 = 103 360`.
> The support thread's own bridge state file
> `~/.codex/state/nuzantara-context/01a08763….json` reads `used 108296`, `window 258400`,
> `return_required true`, 26 `PreToolUse` / 24 `PostToolUse`. The `rg` was denied because
> the thread had crossed its 40 % context budget at its third request — the tool being
> read-only had nothing to do with it. **The defect is the deny TEXT**: it recites the role
> contract and never names the number that fired, so I read a budget stop as a role stop
> and drew the wrong conclusion from it. Superscar #3 in the message rather than in the
> guard. Everything below is left as written; the reading, not the record, was wrong.

The denial, verbatim:

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
  not yet viable *here*, and the fix goes to the Codex bridge before any re-run.
  *(Corrected: the fix is to the bridge's **deny message**, which never states the context
  budget that fired — not to a "role gate on a read-only search", which is not what
  stopped arm B. See the correction in §4 and Fable's §9.)*
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

---

## 9. Fable adjudication — pilot mission 1, run 1 (2026-09-10 02:40 WITA, nuzantara-40)

Read in full. Report accepted as an honest record; one reading in it is wrong and it changes the fix.

### Correction to §4/§7: arm B was not stopped by a role gate on a read-only search

The deny is tool-agnostic. `context_bridge.py` denies EVERY PreToolUse once `return_required` is set, and `return_required` flips when `last_token_usage.total_tokens >= 0.4 * model_context_window` (`measure()` reads `last_token_usage`, so this is per-request context, not cumulative). Verified on the support thread's own rollout and bridge state:

| time (UTC) | last request tokens | threshold (0.4 × 258,400) |
|---|---|---|
| 18:17:23 (first request, boot) | 54,993 (45,824 cached) | 103,360 |
| 18:18:54 | 92,487 | |
| 18:19:13 | **103,957 → return_required** | |
| 18:21:13 (halt) | 108,296 | |

State file `~/.codex/state/nuzantara-context/01a08763….json`: `used 108296, window 258400, return_required True`. So the `rg` was denied because the thread had crossed the 40 % context budget at its third request, not because it was read-only. The deny TEXT is the defect the Dux actually hit: it recites the role contract and never states the number that fired, so a correct coordinator read it as a role denial and halted. That is superscar #3 in the message, not in the guard.

This is the measured instance of the Pro session's 2026-09-09 finding: a Codex builder boots at ~55 k (AGENTS.md 43.8 KB + app instructions + hooks), so 0.4 × 258 k leaves ~48 k of working context per hop. On a 1 M Claude window the same 40 % is 400 k, which is why arm A never met this wall.

### Decisions

1. **(a) recorded as a finding.** Under the current Codex seat configuration the Capo topology is not viable for a Gear-2 task: each of its threads has ~48 k of working context before every tool is denied, and the deny message does not say so.
2. **(b) B-2 proceeds** (already launched on Zero's go, denial clause repaired). It stays comparable to arm A without re-baselining A: A's only denial came after the build. **B-2 is expected to hit the same 103 k wall**; the Dux watches `used` in the bridge state files and records each `return_required` flip with its request size. If B-2 delivers anyway, the deliverable counts; if it halts on the wall, that is the D3 answer for this configuration and no B-3 runs until the seat is reconfigured.
3. **Three defects, owed to the follow-up PR that already carries the 2 probe defects and the 9 council residuals** (another Claude session ships; Fable posts the gate):
   - Codex bridge deny message must state the trigger: `context budget: <used>/<window> ≥ <fraction>` on the first line, role text after.
   - Claude adapter (`child_workflow.py context`): exempt the report channel (SendMessage to parent, and the final text) from the context-budget deny, or auto-emit the checkpoint on the denying call. Arm A's finding stands.
   - `worktree_isolation.py` over-match on an unexpanded `$VAR` path (Dux-side false positive).
4. **Seat configuration is Zero's decision, not a PR**: builder threshold 0.6 on the Codex seat (Pro's proposal) and the AGENTS.md index diet. Both are prerequisites for any further Capo measurement; neither changes the Claude side.
5. PR #6054 (arm A) stays unmerged and unarmed until the pilot closes; the receptor design is sound (import guard, `finally` restore, `UNKNOWN` only at the configured model's own path). Non-blocking: emit non-`VALID` evidence rows first, per §6.
6. PR #6056 (this report): `harness/fable-gate = PASS-WITH-CONDITIONS`, condition = this correction appended to the report before merge. The Dux may merge its own report after appending it.

Astra: reply under this section, or in `FABLE-MEASUREMENTS-2026-09-09.md` as before.


---

## 10. Arm B-2 — the Capo with the denial clause repaired

Run on Zero's "go" and under Fable's decision 2, after §6.2 identified my own instruction as
the variable that decided run 1. **One clause changed, nothing else**: instead of "STOP and
report the denial verbatim", B-2 was told to record the denial verbatim, have the affected
thread checkpoint as the guard asks, and then continue by a route the guard permits —
halting only if the denial blocks the deliverable itself. Arm A was not re-baselined,
per Fable's decision 2 and because A's only denial arrived after its build was finished.

Comparability caveat, stated rather than hidden: B-2's worktree forked from `9e64bcbf99`,
not run 1's `4eed90f149` — the merge queue advanced `main` in between. Irrelevant to the
receptor, recorded anyway.

### Consumption

| metric | arm A | arm B (run 1) | **arm B-2** |
|---|---|---|---|
| wall clock | 1090 s | 442 s | **805 s** |
| non-cached input tokens | — | 90 188 | **104 122** |
| output tokens (incl. reasoning) | — | 7 197 | **15 063** |
| child tokens, Claude accounting | 196 325 / 400 000 | n/a | n/a |
| command executions | — | 18 | **30** |
| threads | 1 | 3 | **3 (+1 continuation)** |
| net lines delivered | **+250, committed** | 0 | **+283, uncommitted** |
| commit / PR | `87b4e79e75` / #6054 | none | **none** |

Kill conditions never reached: 805 s against a 2180 s line.

### The repaired clause worked, and then the wall took the coordinator

The first `return_required` flip landed on a child at 106 822 / 258 400 and **the arm did
not stop** — it checkpointed that thread and kept building, which is exactly the behaviour
run 1's instruction had suppressed. Then the wall climbed the hierarchy. Final bridge state
for the four threads, read off `~/.codex/state/nuzantara-context/`:

| thread | role | used / window | `return_required` | last event | Pre/PostToolUse |
|---|---|---|---|---|---|
| `01a0876d…` | Capo | **110 601** / 258 400 | — | `Stop` | 45 / 44 |
| `01a0876f-3bb1…` | child | **106 822** / 258 400 | **true** | `SubagentStop` | 15 / 12 |
| `01a0876f-7c61…` | child | 101 729 / 258 400 | — | `SubagentStop` | 18 / 18 |
| `01a08779…` | continuation | — | — | `PostToolUse` | 1 / 1 |

Final message: *"Checkpoint salvato. La continuazione riprenderà automaticamente con patch,
verifiche C1–C6, commit e PR ancora da completare."* All three working threads finished
between 101 k and 111 k against a 103 360 threshold. **Fable's prediction is confirmed
exactly**: the Capo topology on this seat does not have the context to carry a Gear-2 task
to a commit, and it is the coordinator — the thread that must hold the whole mission — that
runs out last and hardest.

### What B-2 actually produced, characterised (not graded)

It parked before running its own checks, so this is a description of an unfinished
artefact, not a verdict on a submitted one. `scripts/proprioception.py` +160/−6 and a
123-line test file, uncommitted:

- **C2 PASSES** — `--selftest` OK, registry valid, 19 probes.
- **C1 FAILS** — the test file crashes: its own `scoped_path` stub reads
  `os.environ["CLAUDE_CONFIG_DIR"]` unguarded and raises `KeyError`.
- **C4 runs but is internally inconsistent** — the probe returns `UNPROBEABLE` while
  emitting `n_findings: 5` and a populated evidence list.
- One thing it did **better** than arm A: it enumerates the second profile's models fully
  and prints an 8-character scope prefix per row, which is within the spec's redaction
  limit and more diagnosable than arm A's rows.
- +283 lines is over the 150–250 band, though the work was not finished, so the number is
  not a fair reading of what it would have shipped.

### The D3 answer, for this seat configuration

Per Fable's decision 2 — *"if it halts on the wall, that is the D3 answer for this
configuration and no B-3 runs until the seat is reconfigured"* — **the answer is that the
Codex Capo topology is not viable for a Gear-2 mission as the seat stands today.** Not
because coordination is wrong, and not because the Capo misbehaved: it obeyed every guard,
routed around none, and checkpointed correctly at each wall. It ran out of context. A
builder that boots at ~55 k against a 258 400 window has ~48 k of working room before every
tool is denied, and a coordinator holding a mission spec plus three threads' worth of state
reaches that first.

Arm A had the same 40 % rule applied to a 1 000 000 window — 400 000 tokens — and used
196 325 of it. **The two arms were never running the same experiment**; they were running
the same spec against budgets that differ by 4×. That, and not the Capo pattern, is what
this pilot measured.

Prerequisites before any B-3, both Zero's call per Fable's decision 4: builder threshold
0.6 on the Codex seat, and the `AGENTS.md` index diet. Plus the deny-message fix from
decision 3 — a coordinator that cannot see the number cannot manage the budget it is
being held to.

---

## 11. Arm B-3, and why the pilot closes here

Zero ordered B-3 at 03:10 WITA (confirmed to the Dux directly, not only through Fable):
same spec, same C1–C6, same repaired denial clause, Codex Capo + Terra + 1 support,
`max_threads 3`, fresh worktree, kill lines unchanged. **One variable changed** — the seat.
`~/.codex/nuzantara-context-policy.json` on M5, read before launching:

```
"thresholds": { "imperator": 0.2, "builder": 0.6 },  "max_hops": 3,
"child_limits": { "max_attempts": 24, "max_active": 3, "max_depth": 1, "max_seconds": 3600 }
```

Builder 0.6 of 258 400 puts the wall at **155 040**, up from the 103 360 that killed B-2.
Worktree forked from `befb71ba00` — a third distinct base commit, recorded as before.

### B-3 measured nothing, and the cause was one of the mission's own terms

It died at **127 s**, not on the context wall. The Capo was denied the delegation itself:

```
Tool call blocked by PreToolUse hook: Mandate deadline reached; return the remaining
work. Do not reset the budget with a replacement.. Tool: collaborationspawn_agent
```

Verified on disk, not inferred:

| | |
|---|---|
| mandate `pilot-mission-1-20260910` created | 01:54:06 |
| `deadline` field | **02:54:06** — exactly `created + 3600` |
| B-3 launched | **03:15:44**, 21 min 38 s after expiry |
| Capo context at death | **56 137 / 258 400** — nowhere near the 155 040 wall |
| threads spawned | **none**; worktree clean, zero lines |

**B-3 is not a test of the 0.6 threshold.** It never approached it.

### Finding: the pilot's two budget models measure different things

The cause is the mission term *"keep `NUZANTARA_MANDATE_ID` so the ledger row
continues"*, and it turned out to be unsatisfiable. **The ledger's mandate deadline is
wall-clock from creation; the child's 3600 s cap is accumulated ACTIVE time.** A mission
that spans more than an hour of human-paced work therefore outlives its own mandate while
no child has spent anything close to its budget — the mandate had 0 active children for
most of the hour it was expiring in.

This is the **second budget-model mismatch this pilot found**, and it has the same shape as
the first:

| | model A | model B | consequence |
|---|---|---|---|
| §10 | 40 % of a 1 000 000 window (400 000) | 40 % of 258 400 (103 360) | the two arms were never running the same experiment |
| §11 | mandate deadline = wall clock from creation | child cap = accumulated active time | a long mission is denied while its budget is untouched |

Neither is a bug in a guard. Both are two honest budgets that answer different questions
being read as one number.

The deny text is again the operator-facing defect, for the same reason as the Codex
bridge's in §9: *"Mandate deadline reached"* does not say **when** the deadline was, or
that it is wall-clock rather than active time. A coordinator that reads it at 03:15 has no
way to learn the window shut at 02:54.

### Closed, by Zero

Relaunching as B-3b under a fresh mandate id was the obvious repair, and Fable
recommended it: a new id is a new run, not a reset of an expired budget — which is what
the deny text forbids. The Dux declined to act on that recommendation alone, because
keeping the mandate id was a term **Zero** had set and only Zero could lift it, and put
the choice to him. **His answer was to close the pilot** (03:25 WITA, *"fallo chiudere,
non ci serve più"*). B-3b was not run.

**So the 0.6 wall is unmeasured, and this report does not claim otherwise.** The D3 answer
of §10 stands exactly as written and only for what it covers: builder 0.4, the seat as it
was between 02:15 and 02:29 WITA. Whether a Capo at 0.6 reaches a commit is an open
question, not a pessimistic one.

### Final state

| item | state |
|---|---|
| #6056 — this report | **merged** as `4efcc73e0f` |
| #6054 — arm A receptor | **open, unarmed**; its fate is Zero's, outside the pilot |
| arm B-2 work product | committed as evidence `a4ddcac2b9` on `agent/air-m5/infra/pilot1-arm-b2`, **no PR** |
| arm B, arm B-3 | no commit, clean worktrees |
| guards | none disabled; `MANDATE_BUDGET_OFF` never set; ledger never edited |
| calibration state | sha256 manifest identical from 01:53 to close |
