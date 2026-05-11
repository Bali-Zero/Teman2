# ADR — PulseLoop nomenclature canonical map

**Date:** 2026-05-07
**Status:** Accepted
**Scope:** `apps/cell/cell/core/pulse.py`, `apps/cell/cell/cortex/cortex.py`, `packages/cell-core/cell_core/genome.py`, `packages/cell-core/cell_core/observatory.py`
**Code-only doc PR — no behavioral change.**

## Context

`SYMBIOSIS.md:64` describes the PulseLoop in shorthand:

> **PulseLoop** — concrete lifecycle runner (sense→think→act→reflect→dream→mature)

That six-word slogan reads cleanly in prose but does **not** match the
state machine actually implemented in `apps/cell/cell/core/pulse.py`. It
also does not match the `phase` enum used by the observatory, the four
named Cortex hooks, or the five Genome record types. As a result,
session briefs, planning docs (PR #479 §FASE 3), and parts of `MEMORY.md`
have repeatedly framed the PulseLoop as a six-state linear pipeline — an
abstraction that was useful at design time but is now actively
misleading. A 2026-05-07 sub-session (W2-D) was launched on the premise
"PulseLoop ~10% active, bring to 100%" and immediately hit the
contradiction: the loop is closer to 90%+ active, the schema described
in the brief did not exist, and the named transitions did not match the
code. The session was halted before any code was written.

This ADR fixes the nomenclature so future briefs anchor on what the code
actually does. **No code change.** Only mappings and pointers.

## 1. Canonical state machine — `PulseEngine.single_pulse()`

Source of truth: `apps/cell/cell/core/pulse.py:165-824` (function
`PulseEngine.single_pulse`). The numbered phases below are the
literal `# 1.`-`# 9.` comments in the source and are the names that
should be used in any new doc, brief, dashboard, or alert message.

| # | Canonical name | Source line | Skipped when |
|---|---|---|---|
| 1 | `DNA INTEGRITY`              | `pulse.py:172` | never (halts pulse if hash mismatch) |
| 2 | `SAFETY GATES`               | `pulse.py:177` | safety gate `can_proceed=False` aborts pulse |
| 3 | `SENSE`                      | `pulse.py:188` | always runs |
| 4 | `EVALUATE (FAST)`            | `pulse.py:192` | always runs (sensor aggregation + classify) |
|   | └─ `STM write`               | `pulse.py:323` | when `stm` is None |
|   | └─ `Trend detection`         | `pulse.py:344` | when `trend_detector` is None |
|   | └─ **SLEEP PHASE branch**    | `pulse.py:362-465` | only when `homeostatic.is_sleeping() and maturation.can_dream()` |
|   | └─ `LTM context refresh`     | `pulse.py:467` | every 60 pulses (~1h) |
|   | └─ `Journal context fetch`   | `pulse.py:479` | when `journal` is None |
|   | └─ `STM context for reasoner`| `pulse.py:487` | when `stm` is None |
|   | └─ `Attention gating`        | `pulse.py:507` | when `attention` is None |
| 5 | `THINK (SLOW)`               | `pulse.py:318/528` | only when `status != GREEN` and reasoner+interpreter both present |
| 6 | `VALIDATE` (DNA interpreter) | `pulse.py:560` | only when THINK proposed `action != "none"` |
|   | └─ Lifecycle confidence gate | `pulse.py:570-584` | when `maturation` is None |
|   | └─ ACT (Fly/Logs/Local effectors + alerts) | `pulse.py:594-669` | per-action; only the matched branch runs |
| 7 | `PERSIST` to PostgreSQL      | `pulse.py:684` | best-effort; logged on failure |
| 8 | `SELF-MODEL` record          | `pulse.py:699` | when `self_model` is None |
| 9 | `EPISODIC MEMORY` record     | `pulse.py:711` | only when `episodic.should_record(...)` returns True |
| — | Cortex hooks 1-4             | see §3 below   | per-hook gating |
| — | Pulse Observatory emit       | `pulse.py:783-822` | when `CELL_OBSERVATORY_EMIT != 'true'` |

**Sleep branch is a full alternative path**, not a sixth step in series.
When the cell is sleeping AND mature enough to dream
(`Maturation.can_dream()`), steps 5-9 are replaced with: Dreamer +
Journal write + Cortex hook 4 + observatory emit with `phase="sleep"`.
The pulse then returns early — VALIDATE/ACT/PERSIST/SELF-MODEL/EPISODIC
do **not** run during sleep. This is the antithesis of a linear
sense→think→act sequence and is invisible in the SYMBIOSIS slogan.

`PulseResult` (returned by every pulse, `pulse.py:79`) carries:
`timestamp`, `halted`, `halt_reason`, `skipped`, `skip_reason`,
`health_status`, `action_taken`, `action_reason`, `thought_tier`,
`error`. None of those fields are named "reflect" or "mature".

## 2. Alias map (deprecated short forms → canonical phase)

The slogan from `SYMBIOSIS.md:64` and downstream repetitions is
allowed as **prose shorthand**, not as a state-machine specification.
When future briefs need to map slogan → reality:

| Slogan term | Canonical phase(s) in code | Notes |
|---|---|---|
| `sense`   | step 3 SENSE + step 4 EVALUATE (FAST) sensor aggregation | |
| `think`   | step 5 THINK (SLOW) — runs only on non-green health | tier-gated by `attention.can_afford(DEEP_REASONING)` |
| `act`     | step 6 VALIDATE → effector dispatch (Fly/Logs/Local/NLM/alert) | hardcoded action whitelist; lifecycle confidence gate per action |
| `reflect` | NO dedicated step — the closest equivalents are: step 7 PERSIST (cell_pulse / cell_alerts rows), step 9 EPISODIC, Cortex hook 2 `after_action` (critic.register_expectation + critic.evaluate_pending) | the brief that originated W2-D miss-spec used "reflect" as if it were a discrete state — it is not |
| `dream`   | sleep branch in step 4 — Dreamer + Journal + Cortex hook 4 `during_sleep` | conditional on `homeostatic.is_sleeping() and maturation.can_dream()` |
| `mature`  | NOT a per-pulse phase — `Maturation` is an out-of-band lifecycle tracker (`packages/cell-core/cell_core/lifecycle.py:35-58`) returning EMBRIONE/NEONATO/GIOVANE/ADULTO/ANZIANO based on age. `AchievementGate.effective_phase()` (sleep branch hook 4 only) further gates on 7 achievement metrics | nothing in the loop "matures" within a single pulse |

**Implication for briefs:** "FASE 3 cell-core organism PulseLoop full
sense→think→act→reflect→dream→mature" is six items where two are not
pulse phases and one ("reflect") has no dedicated implementation. New
work should be specified against the §1 numbered phases or the §3 Cortex
hooks, not against the slogan.

`MEMORY.md` uses the slogan only inside research-capture summaries
(`seed_initial_skills.py` skill `experience:record_trajectory`
description says "Persist sense→think→act→reflect episode") — that is a
**skill description**, not a state-machine spec, so it stays as is.

## 3. Cortex hook catalog

Source: `apps/cell/cell/cortex/cortex.py:82-186`. The Cortex is a
phase-gated orchestrator over six components (skills, critic, curiosity,
goals, mutator, gate). Each hook is best-effort: failures log a warning
but do **not** block the pulse.

| Hook | Method | Called from `pulse.py` | Lifecycle phases | Responsibility |
|---|---|---|---|---|
| 1 | `before_reasoning(situation: dict) -> str` | `pulse.py:516-526` (right before THINK) | NEONATO+ | recall top-3 skills via `SkillLibrary.recall(situation, k=3)` and format for system-prompt augmentation. Returns empty string for EMBRIONE or on failure. |
| 2 | `after_action(episode_data, proposal, action, episode_id, current_pulse) -> None` | `pulse.py:740-751` (after EPISODIC) | NEONATO+ | `critic.register_expectation` (NEONATO uses heuristic, GIOVANE+ uses LLM) + `critic.evaluate_pending` for prior expectations whose evaluation pulse has arrived; surfaced weaknesses go to `self_model.add_weakness`. |
| 3 | `during_idle(state: dict) -> None` | `pulse.py:753-763` (after hook 2, only when `status == GREEN`) | GIOVANE+ | bail out if `stress > 0.3` or `attention_remaining < 5`; else `curiosity.explore` + (`goals.collect` & `goals.pursue_next` for GOALS_PHASES) + (`curiosity.allow_mining` only ADULTO/ANZIANO). |
| 4 | `during_sleep() -> dict` | `pulse.py:402-407` (sleep branch only) | called regardless; internal logic phase-gated | the heaviest hook: `skills.decay`, `skills.enforce_capacity`, `gate.effective_phase`, `mutator.check_rollbacks`, mutation cycle (ADULTO+: 3 props/day, ANZIANO: 1/day), `critic.detect_weaknesses_for(self_model)`, `goals.collect(critic_signals)`, `goals.archive_old`. Returns summary dict (`decayed`, `rollbacks`, `mutations_proposed`, `promoted`, `missing_for_next`, `effective_phase`). |

**Phase activation tuples** (`cortex.py:23-27`) are tuples not
`>=` comparisons — `LifecyclePhase` is a string enum and Python compares
str values **alphabetically**, so `"giovane" >= "adulto"` is `True`
(wrong). Future work that touches phase gating MUST use tuple
membership or the explicit rank map in
`apps/cell/cell/lifecycle/achievement_gate.py:19-25`.

## 4. Genome record types — schema + real examples

Source: `packages/cell-core/cell_core/genome.py:48` —
single `genome` table, FTS5-backed, five record types.

```sql
type TEXT NOT NULL CHECK(type IN ('skill','pattern','scar','insight','trajectory'))
```

There is **no** `~/.cell/genome.db` and **no** separate
`(skills, reflections, insights)` tables. Everything is rows in the
single `genome` table, distinguished by the `type` column. Each cell
opens its own `Genome(db_path=...)` — `experience` and `skill` services
in `apps/backend-rag/backend/services/{experience,skill}/service.py`
both accept a configurable path; `apps/mata-garuda/.../sentinel_cell.py`
points at `data/knowledge.db`. There is no global path convention.

| Type | When recorded | Confidence default | Scope default | API |
|---|---|---|---|---|
| `skill` | a procedure the cell learned that worked. Recorded by hand-curated `seed_initial_skills.py` for bootstrap and by `Cortex` mutation cycle (hook 4) for runtime growth. | 0.5 (seed sets to 0.6-0.8) | `Project` | `Genome.record_skill(cell, skill_id, procedure, precondition, success_criterion, confidence, scope, inherited_from, entry_type='skill', domain)` |
| `pattern` | regularities observed (not yet validated as actionable skills). Recorded via `record_skill(..., entry_type="pattern")`. | 0.5 | `Project` | same as skill, with `entry_type="pattern"` |
| `scar` | failure to be avoided. **Always Personal scope**, **confidence 0.9** (strong avoidance). | 0.9 (forced) | `Personal` (forced) | `Genome.record_scar(cell, scar_id, procedure, precondition)` — wraps `record_skill` with type-and-scope override |
| `insight` | derivative of multiple reflections (Cortex sleep branch / hook 4 mutation cycle). Recorded via `record_skill(..., entry_type="insight")`. | 0.5 | `Project` | same as skill with `entry_type="insight"` |
| `trajectory` | a recorded episode of execution (sense→think→act→reflect outcome). Carries `outcome`, `tokens`, `duration_ms`, `tags` columns nullable on other types. | 0.5 | `Project` | `Genome.record_trajectory(cell, trajectory_id, outcome, procedure, tokens, duration_ms, tags, confidence)` |

### Promotion / decay (no separate "graduation" table)

The brief that originated W2-D specified a 3-table schema with rules
"reflection ≥3 → insight; insight ≥2 + score ≥0.7 → graduated skill".
This does not exist as named in the code. The actual lifecycle of a
genome row is:

- **promotion** — `Genome.promote_skills()` (`genome.py:573`) walks
  rows of `type IN ('skill','pattern')` (not scar/insight) and
  upgrades `tier` from NULL → tier1 / tier1 → tier2 based on `uses`
  and `confidence` thresholds. Tier thresholds are class constants.
- **decay** — `Genome.decay_unused_skills()` (`genome.py:486`) drops
  `confidence` over time for rows that have not been used.
- **silencing** — `Genome.silence_skill()` (`genome.py:453`) and
  `silence_stale_skills_v2()` (`genome.py:620`) set `valid_to`
  (epigenetic silencing per `SYMBIOSIS.md:78`). Rows are **never
  deleted**; `vacuum()` is the only path that removes silenced rows
  older than 90 days.
- **inheritance / HGT** — `Genome.inherit_genome(parent_cell, fork_date)`
  (`genome.py:727`) selects active rows for selective transfer at fork
  time. `apply_inherited_genome()` writes them on the receiving cell
  with `inherited_from` set. This is the *plumbing* for FASE 3 of PR
  #479 — out of scope for this ADR, named here so future work doesn't
  reinvent it.

### Real seed examples (from `apps/backend-rag/backend/scripts/seed_initial_skills.py`)

**type=skill** — `cell="experience"`, `skill_id="experience:normalize_outcome"`:
> precondition: "Raw outcome string from LAM episode or cell pulse reflection."
> procedure: "Map free-text outcome tokens to the strict success|failure|partial enum; return None for ambiguous tokens (completed, done, unknown) rather than guessing."
> success_criterion: "Only strict tokens cross into Experience Library; noise stays out."
> confidence: 0.7

**type=skill** — `cell="rag"`, `skill_id="rag:hybrid_search_rrf"`:
> precondition: "Qdrant + BM25 stores populated; CrossEncoder loaded."
> procedure: "Combine BM25 + dense vector retrieval via Reciprocal Rank Fusion, then re-rank top-20 with CrossEncoder. Never skip reranking on authoritative domains (KBLI, visa)."
> success_criterion: "Top-5 recall > 0.85 on RAGAS canary set."
> confidence: 0.8

**type=skill** — `cell="rag"`, `skill_id="rag:evidence_score_gate"`:
> procedure: "Gate final answer on evidence score: <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS with disclaimer, >0.60 NORMAL. Do NOT override to NORMAL just because the LLM produced prose — check trusted_tools_used."

**type=trajectory** — described as the canonical emit shape from
`experience:record_trajectory` skill:
> "Persist sense→think→act→reflect episode via POST /api/experience/record. Use outcome=failure for Personal-scope scars; success/partial go Project."

(No `scar` or `insight` rows are present in the seed file — those grow
in production from runtime reflection, the same way `experience` cell
populates trajectories from real pulses.)

## 5. Pulse Observatory phase enum

Source: `apps/cell/cell/core/pulse.py:437,797`. The observatory emits
two `phase` literals only:

- `phase="active"` — main path emit (line 797)
- `phase="sleep"` — sleep branch emit (line 437)

Neither is `sense`, `think`, `act`, `reflect`, `dream`, or `mature`.
Dashboards and downstream consumers that filter on `phase` should
expect this two-value enum, not the slogan.

## 6. Lifecycle phases (orthogonal to pulse phases — do not confuse)

Source: `packages/cell-core/cell_core/types.py:19-23`,
`packages/cell-core/cell_core/lifecycle.py:35-58`,
`apps/cell/cell/lifecycle/achievement_gate.py`.

| Phase | Italian name | Age floor (days) | What unlocks | Achievement gate |
|---|---|---|---|---|
| `embrione` | EMBRIONE | 0 | observe + log only | none |
| `neonato`  | NEONATO  | 4 | act with confidence ≥ 0.8 | none |
| `giovane`  | GIOVANE  | 15 | autonomous actions, dreams active, confidence ≥ 0.5 | `episodes_recorded ≥ 10` |
| `adulto`   | ADULTO   | 31 | full autonomy | `episodes_with_outcome ≥ 50`, `skills_in_library ≥ 10`, `goals_completed ≥ 5` |
| `anziano`  | ANZIANO  | 180 | stability priority, reduced mutation rate (1/day vs 3/day) | `skills_stable_30d ≥ 20`, `skills_fitness_above_06 ≥ 0.7`, `journal_continuity_days ≥ 90` |

**Lifecycle phases are NOT pulse phases.** They are an orthogonal
property of the cell as a whole, recomputed from
`Maturation.birth_date` and `AchievementGate.achievements()`. Cortex
hook gating uses these. The slogan word "mature" gestures at this
table; it is not a state the loop visits per pulse.

`AchievementGate` has an **escape hatch** (`_ESCAPE_HATCH_DAYS = 14`):
if age exceeds the floor by 14 days but achievements are unmet, the
phase auto-promotes with a warning log (prevents permanent stall).

## Decision

- **Anchor any new brief, plan, or ADR on §1 (canonical phase numbers
  + Cortex hooks + sleep branch alternative path)**, not on the
  SYMBIOSIS.md slogan.
- **`SYMBIOSIS.md:64` slogan stays as prose** — adding a forward-pointer
  to this ADR is a follow-up doc PR (out of scope to keep this PR
  doc-only and avoid touching widely-imported files).
- **No code change** — this is a doc-only ADR. The existing PulseLoop
  is correct; only the names used to talk about it diverged.
- **W2-D supersession** — the brief that originated W2-D
  ("portare PulseLoop da ~10% a 100%") is superseded by this ADR.
  Future work in `apps/cell/`, `cell-core`, or any cell-related
  organism feature must (a) cite the canonical phase numbers when
  changing the loop, (b) cite the Cortex hooks when changing the
  orchestrator, (c) cite the Genome record types when changing
  persistence.

## Consequences

### Positive

- Briefs grounded in actual code state. No more "X% active" claims
  without `wc -l` evidence.
- Future PRs touching the PulseLoop can cite phase numbers from §1;
  reviewers can check the diff against the canonical contract.
- The five Genome record types stop being conflated with a fictional
  `(skills, reflections, insights)` 3-table schema.
- The Cortex hooks 1-4 catalog removes the ambiguity between "reflect
  in pulse" (which doesn't exist) and the actual `after_action` /
  `during_idle` / `during_sleep` orchestration.

### Neutral

- Slogan in `SYMBIOSIS.md:64` is left in place. A small follow-up PR
  could add a `<!-- See ADR 2026-05-07 ... -->` footnote. Out of
  scope here.
- `MEMORY.md` references the slogan only inside skill descriptions
  (which are descriptive prose, not specs). Left as-is.

### Negative

- None. Doc-only.

## Supersedes

- The W2-D session brief (2026-05-07) which assumed
  `~/.cell/genome.db` schema `(skills, reflections, insights)` and
  "PulseLoop ~10% active". Both premises empirically wrong:
  `~/.cell/genome.db` does not exist; the active loop is 824 LOC + 40+
  tests, closer to 90%+ than 10%. Sub-session correctly halted at
  T+12min with 0 LOC written.
- Any prior reading of `docs/SYMBIOSIS_TURNON_PLAN.md` §FASE 3 that
  framed FASE 3 as "cell-core PulseLoop activation". §FASE 3 is
  **HGT expansion** (`cell:skills` Redis stream, 3→10 cells). Not
  PulseLoop activation. Not in scope of this ADR either.
- `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md`
  describes `apps/organism/` (Supervisor + Actuators + Event Bus),
  NOT `apps/cell/`. Cell and organism are distinct subsystems with
  distinct vocabularies. Briefs that conflate them will misframe the
  task.

## References

- Code: `apps/cell/cell/core/pulse.py`
- Code: `apps/cell/cell/cortex/cortex.py`
- Code: `apps/cell/cell/lifecycle/achievement_gate.py`
- Code: `packages/cell-core/cell_core/genome.py`
- Code: `packages/cell-core/cell_core/lifecycle.py`
- Code: `packages/cell-core/cell_core/types.py`
- Code: `packages/cell-core/cell_core/observatory.py`
- Doc: `SYMBIOSIS.md` §64,77,78
- Doc: `docs/SYMBIOSIS_TURNON_PLAN.md` (PR #479) §FASE 1-4
- Doc: `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` (organism, NOT cell)
- Seed data: `apps/backend-rag/backend/scripts/seed_initial_skills.py`
