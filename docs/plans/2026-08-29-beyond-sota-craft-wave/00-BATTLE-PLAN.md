---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
type: battle-plan
status: READY — squads launch on Zero's GO
---

# Beyond-SOTA craft wave — battle plan

Mandate (Zero, 2026-08-29): execute the 39 first-PRs of the 13 engineering-craft lanes (panel
2026-08-28, PR #5177) plus L00 (R9 defuse, deadline 2026-09-02), in parallel sessions. **Opus 5
sessions are the orchestrators** — the session that authored these specs is NOT in the squad.
Every model of the arsenal is positioned where it genuinely serves (workhorse-first ruling
2026-08-15; Fable 5 out of the workflow, ruling 2026-08-20 — no lane may route to it).

## 1. Force structure

| Role                                 | Model                                                                                                            | Where                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Conductor** (1)                    | Opus 5, xhigh                                                                                                    | Interactive tmux session on Pro, on the Pro default interactive profile (slot-1 account) with a LIGHT footprint — no builds, no subagents; if that account is weekly-capped it borrows the idlest squad seat and says so on this board. Owns the board, merge choreography (it merges the auto-merge-OFF classes on gates-green evidence), seat ledger, escalations to Zero. Never implements. |
| **Squad orchestrator** (1 per squad) | Opus 5, xhigh                                                                                                    | One session per squad, own worktree via `scripts/agent_start.py`. Runs the modus loop per PR: GROUND → BUILD (delegated) → VERIFY → SHIP → PROVE-LIVE. Holds the final on-disk gate (empirical, never delegated).                                                                                                                                                                              |
| **Implementer**                      | Sonnet 5 (subagent, `model:"sonnet"`)                                                                            | Well-specified BUILD units inside each squad — the default builder.                                                                                                                                                                                                                                                                                                                            |
| **Grunt**                            | Haiku 4.5 (subagent)                                                                                             | Fixtures (fixture-gen), ledger rows (ledger-writer), docs cross-refs (docs-sync), mechanical edits.                                                                                                                                                                                                                                                                                            |
| **Red-team + sandbox**               | Codex GPT-5.6 (`codex exec --sandbox read-only\|workspace-write -c model_reasoning_effort=xhigh`, `< /dev/null`) | Security-adjacent diffs (L00 workflow, L07 dead-man, L13 broker), migration upgrade+downgrade sandbox (L12-PR2), second opinion on any workflow diff.                                                                                                                                                                                                                                          |
| **Refuter (default)**                | Kimi K3 (`kimi -p ... -m kimi-code/k3`)                                                                          | Blind review of every PR diff before arming, EXCEPT workflow/security-class diffs (those go to Codex sol per §4 and the lane specs). Generator≠grader, family-exclusion: never refutes a diff Kimi built. Flat quota — use freely.                                                                                                                                                             |
| **Width / consistency**              | Gemini 3.1 Pro (`agy -p`, effort high)                                                                           | Cross-file consistency sweeps (consumer-map before PROVE-LIVE, all-specs coherence check), long-context ingestion. Not a builder here.                                                                                                                                                                                                                                                         |
| **Extra diversity refuters**         | Qwen3.8 Max, DeepSeek V4 Pro, GLM 5.2 (TP1 API)                                                                  | Optional second refuters when family-exclusion needs a third family; math-shaped checks (L08 burn-rate, L05 KPI). TP1 weekly quota was DEAD on 2026-08-29 morning (reset ~14:52 UTC) — probe before relying (`scripts/arsenal_probe.py`).                                                                                                                                                      |
| **Local / PII**                      | Ollama (qwen3.5:9b)                                                                                              | Not load-bearing in this wave (no PII surface); available for log triage at zero cost.                                                                                                                                                                                                                                                                                                         |
| **Ground truth**                     | NotebookLM                                                                                                       | NOT convoked — no regulatory facts in this wave. Deliberate.                                                                                                                                                                                                                                                                                                                                   |
| **Fable 5**                          | —                                                                                                                | NOT in the field. Zero-manual-only (ruling 2026-08-20).                                                                                                                                                                                                                                                                                                                                        |

## 2. Squads, lanes, conflict serialization

Cross-lane file conflicts are the #1 killer (39% of open PRs DIRTY; `evidence/brief.yml`+`pack.yml`
and `scripts/evidence_pack_lint.py` are live hotspots). Squads are conflict-disjoint BY
CONSTRUCTION; inside a squad, PRs are SEQUENTIAL unless the spec says otherwise.

| Squad                      | Lanes (order binding)                                                 | Machine                     | Seat                                                                                                    | Wave                |
| -------------------------- | --------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------- |
| **W — workflows track**    | L00 → L06 → L05 → L04-PR3 → L12-PR3                                   | Pro                         | slot 2                                                                                                  | 1 (L00 immediately) |
| **E — evidence lint**      | L01 (PR-1→2→3) → L03-PR3                                              | Pro                         | slot 3                                                                                                  | 1                   |
| **P — prod probes**        | L07 (PR-1→2→3) + L11-PR1, then L11-PR2/3                              | Mini                        | slot 4                                                                                                  | 1                   |
| **F — fleet & security**   | L09 (PR-1→2→3) → L13-PR1/PR-2 (L13-PR3 waits for Squad C's L10-PR1)   | Mini                        | slot 5                                                                                                  | 1                   |
| **D — data**               | L12-PR1 → L12-PR2 (PR-3 handed to Squad W)                            | Pro                         | slot 1 — launches at the 30/8 09:00 weekly reset (no earlier: slots 2-5 are taken and slot 6 is barred) | 1 (from 30/8 09:00) |
| **C — context & learning** | L02 (PR-1→2→3) → L10 (PR-1→2→3) → release L13-PR3 to Squad F          | Pro (slot freed by D or E)  | first free                                                                                              | 2                   |
| **A — architecture**       | L03-PR1/PR2 (PR-3 stays with Squad E) → L04-PR1/PR2 → L08-PR1/PR2/PR3 | Mini (slot freed by P or F) | first free                                                                                              | 2                   |

Hard constraints honored by this layout:

- **≤3 concurrent squads per machine** (Pro spawns >3 parallel lanes → ENXIO, measured).
- **One OAuth seat per squad, ≤2 concurrent headless lanes per seat**; slot 6 (Team) is LAST
  RESORT by Zero's ruling 2026-08-23 — a squad whose seat dies suspends and asks the conductor,
  it does not self-serve slot 6.
- **Every `.github/workflows/` edit — from ANY lane — is executed by Squad W.** A lane whose PR
  needs workflow wiring (L07-PR1's blocking flip, L08-PR1's immune-enforcement hook, L11-PR2/PR3
  CI jobs, L12-PR3's restore-drill) builds everything else in its own squad and hands the workflow
  diff to W as a separate serialized mini-PR. Auto-merge OFF; the CONDUCTOR merges on gates-green
  evidence posted in the squad ledger; lease-check respected.
- **Shared-file handoffs are explicit**: `pending_arms_report.py` (L10-PR1 → then L13-PR3),
  scar corpus (L02 → then L10-PR3), evidence lint (L01 → then L03-PR3),
  `.github/workflows/immune-enforcement.yml` (Squad W only, serialized),
  `scripts/proprioception.py` + its SessionStart wiring (order: L13-PR2 → L02-PR1 → L10-PR2 →
  L05-PR2; each later PR rebases on the merged predecessor).
- **Squad order in this table supersedes any per-PR "wave" tag inside a lane spec** — those tags
  are the panel INDEX's advisory grouping, not a schedule.
- M5 stays out of the wave (Zero's interactive workstation).

## 3. Launch mechanics (conductor or Zero, per squad)

**Step 0 (blocking)**: this spec pack must be ON MAIN before any squad launches — the squad
worktrees are cut from main and the mandate points at these files. Conductor verifies in each
fresh worktree: `ls docs/plans/2026-08-29-beyond-sota-craft-wave/` shows all 16 files.

Seat map (names only — values live in `~/.nuzantara-secrets.env`, never echoed):
W→`$CLAUDE_CODE_OAUTH_TOKEN_2` · E→`_3` · P→`_4` · F→`_5` · D→`_1` (post-reset) · C/A→the slot
their predecessor squad frees. Slot `_6` (Team) is never self-served.

```bash
# 1. worktree (from the machine's main checkout, repo root)
#    craft-* lanes are not in agent_start.py's KNOWN_LANES allowlist — the flag is required
python3 scripts/agent_start.py --lane craft-<squad> --task-id <squad-slug> --allow-unknown-lane
cd .worktrees/craft-<squad>-<squad-slug>

# 2. seat check BEFORE dispatch (never discover quota by dying)
#    Pro (Keychain lives here):   python3 scripts/claude_seat_quota.py --json
#    Mini (reads Pro's report):   python3 scripts/claude_seat_quota.py --from-report
#    Check the EXIT CODE and the per-seat %, skip any seat at/over limit

# 3. orchestrator launch (headless, incremental, resumable)
export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_<N>"   # from ~/.nuzantara-secrets.env
CLAUDE_CONFIG_DIR="$(mktemp -d)" claude -p "$(cat <<'MANDATE'
You are the Opus 5 orchestrator for squad <X> of the beyond-SOTA craft wave.
Specs (binding, read them first): docs/plans/2026-08-29-beyond-sota-craft-wave/<your lane files>.
Rules of engagement: section 4 of 00-BATTLE-PLAN.md in the same directory — they bind you.
FIRST ACT, always (fresh start or restart): read ./SQUAD-LEDGER.md if it exists and the open
PRs on your branch prefix (gh pr list --state open --json number,headRefName) — resume at the
first unmerged item, never re-open an existing PR. Then work the lanes IN ORDER. Write incremental progress to ./SQUAD-LEDGER.md after
every step (never pause waiting for input — if blocked, write the blocker to the ledger and move
to the next unblocked item; suspend per the three-reds rule). Between PRs, check for a ./STOP
file: if present, finish the ledger entry and exit cleanly.
MANDATE
)" --model claude-opus-5 --effort xhigh \
  --allowedTools "Bash,Read,Write,Edit,Grep,Glob,Agent,Skill" \
  >> ./SQUAD-RUN.log 2>&1 &
```

tmux variant for observability: `tmux new -s craft-<squad>` and run the same command in the pane.
Kill switch per squad: `touch .worktrees/craft-<squad>-*/STOP`. Fleet-wide: conductor message via
`fleet_mail.sh` + STOP files.

**Conductor cadence** (every 20-30 min): read each `SQUAD-LEDGER.md`; open PRs via
`gh pr list --state open --json number,headRefName` filtered on the `agent/<host>/craft-` prefix
(`gh pr list --head` without a value errors out); `python3 scripts/claude_seat_quota.py --json`
(Pro) / `--from-report` (Mini); arm/merge per §5; quota-dead squad → reassign seat or suspend;
surface NEEDS-RULING lines to Zero in one batch, never one-by-one.

**Crash detection & restart**: a squad whose ledger has not moved for 45 min AND whose open PRs
show no new commits/checks is presumed crashed. Restart = relaunch the SAME command in the SAME
worktree (never a second `agent_start.py` with the same task-id — the broker's WIP guard refuses);
the mandate already orders a restarted orchestrator to FIRST read `SQUAD-LEDGER.md` and the open
PRs (`gh pr list --state open --json number,headRefName`, filtered on its own branch prefix) and
resume at the first unmerged item — never re-open a PR that already exists.

## 4. Rules of engagement (binding for every orchestrator)

1. Worktree only (`agent_start.py`), claim commit first, `git -C` on every git call.
2. One PR = one concern, target ≤400 net lines. Branch namespace `agent/<host>/craft-<squad>/...`.
3. **Generator≠grader, family exclusion**: every diff gets a blind non-Anthropic refutation
   (Kimi K3 default; Codex sol for security/workflow class; a diff built by Codex is refuted by
   Kimi and vice versa). Dispositions recorded in the PR body (accepted/rejected/survives).
4. **Final on-disk gate = the orchestrator itself (Opus 5 xhigh), empirical**: re-run the tests,
   re-grep the tree, run the guilt+innocence fixtures from the spec THIS turn. Never from memory,
   never delegated to the implementer.
5. Arm `gh pr merge --auto` BARE at open — EXCEPT the auto-merge-OFF classes (workflow diffs,
   migrations): for those the squad posts gates-green evidence in its ledger and the CONDUCTOR
   merges. Verify arming via GraphQL (`autoMergeRequest` + `mergeQueueEntry.state`) — the CLI
   prints nothing trustworthy.
6. Never push while a push is in flight; judge pushes by captured return code.
7. Evidence pack per branch at the path from `scripts/ci/evidence_paths.py --ref <branch>`;
   lint locally with the origin/main lint BEFORE pushing (Fact-3 recipe in the L00 spec memory);
   `dissent.status` ∈ {CONFIRMED, PLAUSIBLE, RETRACTED}.
8. Rule 8 (so numbered here on purpose): three reds for the SAME cause → SUSPEND (PENDING-ARMS
   line, branch alive), move on. Fix-of-a-fix stops at depth 1 — the second correction means the
   surface is under-specified: write the missing spec detail into the lane file via PR, do not
   open a third fix.
9. Needs-ruling items: NEVER decided by a squad. Write `<ruled value — Zero>` placeholders,
   ship notice/advisory/dry-run mode, add the item to SQUAD-LEDGER under `NEEDS-RULING`.
10. PROVE-LIVE by consumer, not by artifact: a lint proves armed by turning RED on its guilt
    fixture IN CI; a probe by its heartbeat CONTENT; a plist by `launchctl print` + fresh log
    line. Anything not provable this turn → PENDING-ARMS row (ledger-writer agent).
11. ALIGN-FLEET where a HOME-fork twin exists (repomap script, claude-cascade.sh, claude hooks):
    diff BEFORE overwriting (a fix may be stranded live-side), then repo→live, then
    `scripts/lint_home_fork.py` green. Hook-dir live copies on other machines: `operator[control-plane]`
    rows, not silent ssh writes.
12. Seats: your assigned slot only; quota regex `hit your (session |usage |weekly )?limit` → write
    ledger, exit 98-style, let the conductor reassign. Slot 6 Team NEVER self-served.
13. No client PII anywhere; no secret values in any output, config, or fixture (planted tokens in
    tests are FAKE strings, never real ones).
14. No Fable dispatch, no `/model claude-fable-5`, under any circumstances.

## 5. Merge choreography (conductor)

- Queue discipline: arm at most ONE PR per hotspot class at a time (evidence pack files, workflow
  files, `pending_arms_report.py`, scar corpus). Disjoint-file PRs may arm freely in parallel.
- A required check red does NOT get a blind `gh run rerun`: diagnose cause first (W111 — stale
  merge ref → `gh pr update-branch` / `mq requeue`).
- A PR whose recomputed floor is 3 ALSO needs the required `harness/fable-gate` commit status on
  its head SHA: the gate seat (Opus 5 xhigh — the script's name is historical, it never invokes
  Fable) decides the verdict, then publishes it:
  `python3 scripts/harness_fable_gate.py --verdict <PASS|...> --sha <head-sha>`. If the status
  lands after the PR's checks finished, rerun the ORIGINAL `pull_request` run to refresh the
  rollup (the external-status-on-unchanged-SHA case — a `workflow_dispatch` run never enters it).
- After L00 merges: `gh pr update-branch 5177`, rerun its harness-floor check (environment
  changed — a legitimate new round, not a Rule-8 violation), then normal queue.
- Dependabot/foreign DIRTY PRs from the standing backlog are OUT of this wave's scope.

## 6. Timeline (estimate, not a vow)

- **Day 0 (GO)**: Squad W lands L00 (hours — one workflow block). Squads E/P/F launch; Squad D
  launches at the 30/8 09:00 slot-1 reset.
- **Day 1-2**: Wave 1 lanes complete (26 PRs incl. Squad W's 9-item track). Wave 2 squads (C, A)
  start as slots free.
- **Day 3-4**: Wave 2 completes (14 PRs; 40 total = 39 + L00). Conductor closes: PENDING-ARMS
  reconciliation, fleet align, NEEDS-RULING batch to Zero, CAPTURE (memories + AMENDMENTS).
- Throughput guard: the queue's measured median open→merge is 61 min and Backend Tests ~2.5×/PR —
  if the queue chokes, the conductor slows ARMING, never quality.

## 7. What Zero decides (before or during the wave)

GO for the wave itself · the §Needs-ruling batches each spec carries (context budget number,
effort-per-gear default, appetite semantics, Sentry credential mint, dead-man real fire,
tailnet ACL apply, superscar retirement semantics…) · slot-6 use if MAX seats die en masse ·
anything a squad marks NEEDS-RULING in its ledger.
