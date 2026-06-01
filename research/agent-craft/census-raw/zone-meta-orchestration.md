# Zone: META-ORCHESTRATION + SELF-IMPROVEMENT

> macro_group: **meta-orchestration**
> Census date: 2026-06-02 · Method: read of REAL CODE + empirical `launchctl print` / logs / sqlite / git. NOT docs, NOT memory.
> Scope: agents that manage agents (orchestration) + agents that improve agents (self-improvement) + the worktree broker (L1).

The most strategic layer of the organism. Verdict up front: **the orchestration layer exists and works on-demand; the self-improvement layer is built end-to-end but is functionally DEAD — every self-improvement loop is either crashing, empty-fed, or producing only thin-signal noise. Nuzantara is not, in practice, improving itself.**

---

## Entity table

| Entity | Kind | Status | Empirical proof |
|---|---|---|---|
| `scripts/federation_orchestrator.py` | orchestrator | **OPERATIVO (on-demand) — but NO checkpointer, NOT scheduled, idle ~3-4wk** | LangGraph `StateGraph` compiled at line 509 `graph.compile()` with **zero checkpointer arg**. Not wired to any LaunchAgent/cron (grep empty). Last federation-attributable dispatch activity in `ai-dispatch-output/`: 2026-05-08. Runs only when a human/agent invokes `python scripts/federation_orchestrator.py "task"`. |
| `scripts/agent_start.py` (Agent Worktree Broker L1) | broker | **OPERATIVO (library) — but enforcement is opt-in; TTL not auto-reaped** | Clean CLI, kill-switch `AGENT_BROKER_ENABLED`, WIP-safe cleanup. BUT `--cleanup` is manual (no cron). Live evidence of failure mode: 25+ stale `.worktrees/*` on disk right now (each carries `agent-library/.evoskill`), exactly the W62 scar. |
| `com.balizero.agent-library-evolver.weekly` (EvoSkill / Voyager skill-library evolver) | self-improvement | **ROTTO** | `launchctl print`: `runs=1 last exit code=2`. out.log: 3 consecutive failed runs — 2026-05-19 (incomplete), **2026-05-24 `FATAL: evoskill run failed`**, **2026-05-31 `FATAL: DEEPSEEK_API_KEY not set after sourcing ~/.nuzantara-secrets.env`**. Has NEVER completed a successful evolution. EvoSkill program frontier frozen at `program/base` generation=0 (single commit `7902ac05d` 2026-05-24, never advanced). |
| `com.balizero.wr2.reflexion.weekly` (WR2 Reflexion synth) | self-improvement | **OPERATIVO ma A VUOTO (empty-fed loop)** | `launchctl print`: `last exit code=0`. BUT runs on empty data: log shows last 3 weeks `No data in last 7 days; skipping synthesis`. `carousel_runs` table = **0 rows**. `reflective_lessons` = only 2 rows, both `2026-W19 / regulatory / low` (thin-signal self-acknowledged noise). Loop is alive but has nothing to learn from. |
| `com.balizero.wr3.reflexion.weekly` (WR3 Reflexion synth) | self-improvement | **ROTTO (won't launch)** | `launchctl print`: `last exit reason = OS_REASON_CODESIGNING`. The interpreter `apps/war-room/.venv/bin/python3` fails macOS codesigning → process never starts. Logs at `~/Library/Logs/wr3-reflexion-weekly.*` do **not exist** (never produced output). Agent spec `~/.claude/agents/wr3-reflexion-synth.md` is well-designed but the cron that should drive it is dead on launch. |
| `~/.claude/agents/wr3-reflexion-synth.md` (+ implied `wr2` reflexion agent) | self-improvement (agent definition) | **INCERTO / DEFINED-NOT-DRIVING** | Agent markdown defines model=sonnet, scheduled tier, ≤10 lessons, `_proposed/` skill drafts, `_quarantine/` demotion. But the LIVE reflexion crons call standalone Python scripts (`_reflexion-synthesis.py`), NOT the subagent. The `.md` agent is documentation of intent; the executing artifact is the Python script. No code path invokes the subagent. |

---

## Detail per entity

### 1. federation_orchestrator.py — orchestrator
- **What it is**: LangGraph DAG `CLASSIFY → CHECKPOINT → DISPATCH(parallel search/explore/sandbox) → ASSEMBLE → REVIEW(redteam) → OUTPUT`. Classifier = local Ollama `qwen3.5:9b` (`think:false`), keyword pre-filter from `federation_capability_table`. Dispatch shells out to `scripts/ai-dispatch.sh` (Gemini/Codex/Claude). Output = markdown context file in `ai-dispatch-output/`.
- **Checkpointer**: **ABSENT.** Line 509 is bare `graph.compile()`. The `human_checkpoint_node` does a blocking `input()` (or Telegram auto-proceed) — it is a *prompt* checkpoint, NOT a LangGraph durability checkpoint. If the process dies mid-run, state is lost (no resume).
- **Observability**: full Langfuse/LangSmith span scaffolding (lines 62-181) — degrades to no-op when no API key.
- **Run cadence**: NOT a daemon, NOT cron. Invoked manually. `ai-dispatch-output/` newest artifact is 2026-05-08; `audit.jsonl` last line 2026-05-08 (and those entries are direct `ai-dispatch.sh` calls, `cmd:reasoning/oracolo` — NOT the `source:federation_orchestrator` audit entries the orchestrator nodes write, which means the orchestrator graph itself has produced no recent audit rows).
- **Verdict**: OPERATIVO as a library/CLI, but de-facto unused recently and **stateless** (no checkpointer = no crash-resume, no human-in-the-loop interrupt/resume).

### 2. agent_start.py — worktree broker (L1)
- **What it is**: enforces the invariant `working_tree(w₁) ∩ working_tree(w₂) = ∅` (4/4 LLM panel convergence, documented in code header). Create/list/cleanup/release subcommands, per-worktree `.agent-task.json` metadata + `.env.worktree` (BRANCH_EXPECTED W59 guard), env-safe symlinks (.venv/.env/node_modules).
- **Gap (live)**: TTL=60min default but `--cleanup` is opt-in (no LaunchAgent runs it). Result observed THIS census: ~25+ residual `.worktrees/*` directories (`docs-stash-*`, `ops-*`, `audit-*`, `agents-m5-clean`, …) — precisely the W62 scar (TTL violated 34×). WIP-safe cleanup also means dirty worktrees never auto-reap even if cron existed.
- **Verdict**: OPERATIVO as code, but the broker has no autonomous reaper → structural-debt accumulation.

### 3. agent-library-evolver (EvoSkill = Voyager-style skill library) — self-improvement
- **What it is**: the closest thing to a Voyager skill-library growth loop. Weekly Sunday 03:00 WITA. Wrapper `scripts/agent-library-evolver-run.sh` (23.7KB): source secrets → gather+redact context (Symbiosis Law 2 fail-closed redaction) → PG advisory lock single-flight → `uv run evoskill run` (DeepSeek V4 Pro harness, `mode=skill_only`, iterations=10, frontier_size=3) → budget verify ≤$1.00 → `gh pr create` for proposals (graduation NEVER autonomous).
- **Empirical status — ROTTO, never succeeded**:
  - 2026-05-19: run started, reached `invoking uv run evoskill run`, log truncates (incomplete).
  - 2026-05-24: `FATAL: evoskill run failed` (also `WARN: psql connection to DATABASE_URL failed rc=2` → single-flight degraded).
  - 2026-05-31: `FATAL: DEEPSEEK_API_KEY not set after sourcing ~/.nuzantara-secrets.env` — fails before even reaching evoskill.
  - `launchctl`: `runs=1 last exit code=2`.
- **EvoSkill frontier state**: `program/base` branch = generation=0, single commit `7902ac05d` (2026-05-24 03:00:46), `parent: null`. The Voyager frontier has **never advanced past the seed program.** Seed dataset = 5 synthetic scar→pattern rows (`seed-patterns.csv`); `.evoskill/data/` contains only that CSV — no iteration outputs.
- **Path-drift hazard (W50/W51/W52 family, ACTIVE)**: git-tracked plist (`infra/launchd/`) points `ProgramArguments` + `REPO_ROOT` at `~/Desktop/nuzantara/`; the **LIVE installed** plist (`~/Library/LaunchAgents/`) points at `~/Desktop/nuzantara-deploy/`. Wrapper content is byte-identical between the two paths today, but this is the exact split-brain that caused the 2026-05-25 32h `program/base` checkout drift on the shared deploy worktree.
- **Verdict**: a complete, sophisticated self-improvement engine that has produced **zero successful evolutions**. The skill library does not grow.

### 4. WR2 reflexion synth — self-improvement (Reflexion, Shinn et al. 2023)
- **What it is**: `~/.claude/skills/bali-zero-brand/_reflexion-synthesis.py`. Weekly Sun 02:30 WITA. Reads last-7d `carousel_runs` (designer-override diffs = gold signal) + `slide_states` critic failures + human-review-queue rejections from `wr2-episodic.db`; W3.1 outcome-aware engagement bucketing (top20/bottom20 by IG likes); delegates synthesis to `claude -p --model claude-opus-4-7` (OAuth, defense-in-depth strips `ANTHROPIC_API_KEY`); writes ≤10 lessons to `reflective_lessons` + appends to voice on/off-tone files + `_proposed-amendments/`.
- **Empirical status — ALIVE BUT STARVED**:
  - `launchctl`: `last exit code=0` (clean).
  - But `carousel_runs` = **0 rows** → the loop's primary input is empty.
  - `reflective_lessons` = 2 rows total, both `2026-W19 / regulatory / low` — and the synthesis notes in-log explicitly say *"Signal this week is extremely thin: zero completed runs… everything else would be self-justification noise."* The model correctly refuses to hallucinate lessons.
  - Last 3 weeks: `No data in last 7 days; skipping synthesis`.
  - `_proposed-amendments/` has ~6 files but they are mostly `*-ig-insights-insufficient-data.md` (the loop reporting it has no data).
- **Verdict**: the Reflexion loop is correctly implemented and disciplined (anti-self-justification works), but the production pipeline upstream (WR2 carousels actually running + being scored + IG metrics) is not feeding it, so it learns nothing.

### 5. WR3 reflexion synth — self-improvement
- **What it is**: WR3 (video/episode) mirror of WR2 reflexion. Cron Sun 02:30 WITA → `apps/war-room/.venv/bin/python3 ~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py`. Agent spec `wr3-reflexion-synth.md` is the richest definition (per-agent failure taxonomy, skill graduation ≥3 success episodes, demotion ≥2 critic FAIL).
- **Empirical status — ROTTO at launch**: `launchctl print` → `last exit reason = OS_REASON_CODESIGNING`. The venv python3 binary fails macOS codesign verification → the process never executes. The declared log files (`~/Library/Logs/wr3-reflexion-weekly.log/.err`) **do not exist** → never produced a single line of output.
- **Verdict**: ROTTO. The most elaborate self-improvement agent in the system has never run once.

---

## GAP analysis — what is missing / broken in Nuzantara's self-improvement

### GAP-1 (HARD): federation_orchestrator has NO LangGraph checkpointer
The orchestrator compiles with bare `graph.compile()` (line 509). The backend already SHIPS a production-grade `AsyncPostgresSaver` (`apps/backend-rag/backend/services/workflow/checkpointer.py`, psycopg3, autocommit, dict_row) AND `kg_langgraph_orchestrator.py` uses checkpointing. The federation orchestrator simply doesn't wire it. Consequences:
- No crash-resume: a long parallel dispatch (Gemini explore on 1M ctx can take minutes) that dies loses all state.
- No true human-in-the-loop interrupt/resume: `human_checkpoint_node` blocks on `input()` instead of using LangGraph `interrupt()` + checkpointed resume. This is the exact gap flagged in memory `p2_19_langgraph_federation_orchestrator_2026_05_20.md` (Gap E1) — still open as of this census.
**Fix shape**: pass `checkpointer=AsyncPostgresSaver(...)` to `compile()`, convert the blocking input to `interrupt()`. Reuse the existing checkpointer module.

### GAP-2 (HARD): the Voyager skill-library loop (EvoSkill) has never succeeded → skill library does not grow
Three independent failure modes in three consecutive weeks:
1. `DEEPSEEK_API_KEY` missing/unsourced (2026-05-31) — secrets-file provisioning broken on the live (deploy) path.
2. `evoskill run failed` (2026-05-24) — upstream EvoSkill engine error, root cause not captured (telemetry `evolver.log` empty/unreadable).
3. PG advisory-lock connection failing (`DATABASE_URL` → Fly private DNS unreachable from local cron) → single-flight degraded.
The EvoSkill frontier is frozen at generation=0. There is no closed loop: even if it ran, graduation is gated behind manual `gh pr create` + Antonello review (by design), so the library cannot grow autonomously — and it isn't growing manually either (`agent-library/03-lessons.md` last touched 2026-05-17, PR #700). **The self-improvement promise is structurally present but operationally null.**

### GAP-3 (HARD): WR3 reflexion is dead on launch (codesigning)
`OS_REASON_CODESIGNING` on `apps/war-room/.venv/bin/python3`. Likely a venv built/copied across machines (Air→Pro) or quarantine xattr on the interpreter. The richest self-improvement agent definition in the repo has produced zero output ever. **Fix shape**: rebuild the war-room venv on Pro (or re-sign / strip `com.apple.quarantine`), verify with a manual `launchctl kickstart`.

### GAP-4 (STRUCTURAL): the Reflexion loops run but the upstream production pipeline doesn't feed them
WR2 reflexion exits 0 but `carousel_runs`=0 and only 2 thin `reflective_lessons`. This is the deepest gap: **the learning loop is not the bottleneck — the doing loop is.** Reflexion can only synthesize lessons from runs that (a) executed, (b) got critic-scored, (c) got IG engagement metrics, (d) got designer-override diffs. None of that data is landing in `wr2-episodic.db`. So the loop is a correctly-built engine idling in neutral. Even WR2's own logged self-assessment says the only honest output is "defer until ≥3-5 actual runs accumulate."

### GAP-5 (STRUCTURAL): no autonomous reaper closes the broker loop → W62 recurs live
`agent_start.py --cleanup` is opt-in. ~25+ stale worktrees on disk right now. No `com.nuzantara.agent-worktree-cleanup` LaunchAgent exists (the cicatrix W62 ANTIBODY #1 was *proposed, not shipped*). Each stale worktree also carries a full `agent-library/.evoskill` copy, widening sibling-race surface. The broker prevents collisions at create-time but never tidies up.

### GAP-6 (STRUCTURAL): deploy-path split-brain on the evolver plist (W50/W51/W52 family)
Git-tracked evolver plist → `~/Desktop/nuzantara/`; live installed plist → `~/Desktop/nuzantara-deploy/`. Identical wrapper bytes today, but `nuzantara-deploy` is the shared worktree that the 2026-05-25 cicatrix showed can silently drift onto `program/base` for 32h. The evolver writes its own checkpoint to `program/base` on that same shared tree — the loop is architecturally primed to re-trigger that exact desync. Memory S4 audit (2026-05-31) flags `nuzantara-deploy` as currently a symlink in a wrong-branch worktree.

### GAP-7 (DESIGN): the `.md` self-improvement agents are not the executing artifacts
`wr3-reflexion-synth.md` (and the WR2 equivalent) describe sonnet-driven subagents with rich failure taxonomies, but the live crons invoke standalone Python (`_reflexion-synthesis.py`) that calls `claude -p` directly. The subagent definitions are intent-documentation that nothing dispatches. Whatever evolves in the `.md` (model routing, skill graduation rules) does not change runtime behavior — a silent doc/code divergence in the most strategic layer.

### Synthesis
Nuzantara has **two working orchestration primitives** (federation_orchestrator as on-demand router; agent_start as collision-prevention broker) and **four self-improvement loops, none of which currently improve anything**: EvoSkill crashes (GAP-2), WR3 reflexion won't launch (GAP-3), WR2 reflexion idles on empty data (GAP-4), and the broker never reaps (GAP-5). The architecture for self-improvement is unusually complete and thoughtful (Voyager frontier, Reflexion with anti-self-justification discipline, outcome-aware bucketing) — but the **closed loop is open at every joint**: missing secrets, dead interpreter, starved input pipeline, no reaper, no checkpointer, and a deploy-path split-brain waiting to re-fire. The single highest-leverage fix is GAP-4/GAP-2 sequencing: there is no point hardening the learning loops until the *production* loops (WR2/WR3 carousel+episode runs, EvoSkill secrets+DB reachability) actually feed them.
