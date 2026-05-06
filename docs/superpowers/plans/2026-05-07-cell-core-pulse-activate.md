# Plan — W2-D Cell-Core PulseLoop Activation (FASE 3 Symbiosis Turn-On)

**Date:** 2026-05-07
**Branch:** `feat/cell-core-pulse-activate-2026-05-07`
**Doctrine ref:** PR #479 §FASE 3 (cell-core PulseLoop currently ~10% active, target 100%)
**Sub-session:** W2-D parallel wave (file scope: `apps/cell/`, `packages/cell-core/`)

## Existing State (~10% active assessment)

The state machine SENSE→THINK→ACT→REFLECT→DREAM→MATURE is already implemented
in `packages/cell-core/cell_core/pulse.py` (321 lines). 14 unit tests pass.
What is NOT yet wired:

1. **MATURE phase does NOT call `genome.promote_skills()`** — skill graduation
   (tier2 ≥ 30 uses + 0.70 confidence; tier1 ≥ 100 uses + 0.85 confidence)
   defined in `cell_core/genome.py` but never invoked from PulseLoop.
2. **REFLECT phase does NOT record reflection into Genome** — episodes go to
   episodic store only, no `record_skill(type='insight')` after success.
3. **No event-stream sensor** for `events_outbox` PG durable bus — required
   per task spec for SENSE step.
4. **No daemon entrypoint** for cell-core PulseLoop standalone (the existing
   `apps/cell/cell/main.py` runs the older `PulseEngine`, not `PulseLoop`).
5. **No graceful Ollama-down rule-based classifier fallback** in the THINK
   path of the canonical PulseLoop.

## Schema Divergence Note

Task spec describes separate SQLite tables `skills`, `reflections`, `insights`
with graduation rule. Repo reality (canonical):

* Single `genome` table at `~/.cell/genome.db` with `type` discriminator
  (`skill | pattern | scar | insight | trajectory`) — `cell_core/genome.py`.
* Graduation via `tier` column (`NULL → tier2 → tier1`) using thresholds
  `TIER2_MIN_USES=30 / TIER2_MIN_CONFIDENCE=0.70` and
  `TIER1_MIN_USES=100 / TIER1_MIN_CONFIDENCE=0.85`.

**Decision:** implement against existing schema (Option A per task brief).
Map task-spec semantics to repo:

| Task spec       | Repo reality                                        |
| --------------- | --------------------------------------------------- |
| skills          | `genome` rows where `type='skill'`                  |
| reflections     | `genome` rows where `type='trajectory'` (episodes)  |
| insights        | `genome` rows where `type='insight'`                |
| graduated skill | `genome.tier='tier1'` (top tier)                    |

The "reflection ≥3 → insight; insight ≥2 + score ≥0.7 → graduated" rule maps
cleanly to existing `promote_skills` thresholds; the Genome already enforces
monotonic promotion. We add a thin `mature_skills()` that invokes
`promote_skills()` on a cadence and persists telemetry into the cell journal.

## SMOKE Findings

* **Genome SQLite** — `~/.cell/genome.db` does **NOT** exist on Pro yet.
  Genome class auto-creates on first instantiation. We will create on demand
  inside the daemon entrypoint (test will use temp file).
* **Ollama** — `ollama serve` is **DOWN** at smoke time (`ollama list` →
  "could not connect"). Per spec Law 4, PulseLoop must degrade. Existing
  `cell_core.pulse` has graceful behavior: thinker is injected via Protocol;
  if no real thinker is configured, FakeThinker / rule-based stays in path.
* **Redis** — UP (`redis-cli ping → PONG`).
* **events_outbox** — table is created by SQL migration 144 (verified live
  on prod), schema in `apps/backend-rag/backend/services/events/outbox.py`
  with columns `(id BIGSERIAL, channel, payload JSONB, created_at,
  consumed_at, consumer_id)`.
* **Import** — `from cell_core.pulse import PulseLoop` works under py3.11.
* **Existing tests** — 14/14 pass on `tests/test_pulse.py` (cell-core).

## Codex Review Adjustments (2026-05-07)

Codex sandbox review flagged 4 P1s (no P0). All addressed below:

1. **`record_skill` kwarg is `entry_type`, not `type`.** Plan now uses
   `entry_type='skill'` for graduation candidates.
2. **`promote_skills()` only promotes `type='skill'` rows.** REFLECT MUST
   record actual skill rows (with `entry_type='skill'`) and `use_skill()`
   to bump `uses`. Trajectories are recorded separately for audit; only
   skill rows reach graduation.
3. **`memory_sqlite._get_conn()` lacks `busy_timeout`.** We add it inside
   the daemon entrypoint immediately after instantiation via a small
   helper that invokes `PRAGMA busy_timeout=5000` on the connection,
   matching Genome's setting. Tests verify the pragma is set.
4. **Pulse phases must catch `sqlite3.OperationalError` and degrade.**
   Each phase wraps the SQLite touch in `try/except OperationalError →
   log + record yellow status`, never aborts the pulse. DREAM is bounded
   (max 50 episodes) and on lock error returns yellow rather than crashing.
5. **Daemon must lazy-connect Redis/PG/Ollama and swallow startup errors.**
   The entrypoint connects on first use, every helper has a NoOp fallback
   when the dependency is unreachable at boot.

## Implementation Plan (TDD per state)

### State 1 — SENSE (event-bus sensor)

* `cell_core/sensors/outbox_sensor.py` — new sensor reading from PG
  `events_outbox` (last N unconsumed rows for one or more channels). Uses
  asyncpg if available; degrades gracefully when `db_pool=None`.
* Tests: empty bus → green, populated → yellow with metadata, DB unreachable
  → red but no crash (Law 4 isolation).

### State 2 — THINK (rule-based classifier with optional Ollama)

* `cell_core/thinkers/rule_based.py` — concrete Thinker that classifies a
  reading into a proposed action using a simple rule table (severity →
  action). Implements the `Thinker` Protocol.
* `cell_core/thinkers/ollama_aware.py` — wraps RuleBasedThinker; tries Ollama
  first with a 2s timeout, falls back to rules on timeout/error/down.
  Documents Ollama-not-real-time-critical constraint.
* Tests: rule-based output deterministic; Ollama unreachable → rule fallback
  fires; Ollama timeout → rule fallback fires.

### State 3 — ACT (already implemented)

PulseLoop.act() already gates on `lifecycle.action_confidence_threshold()`
and `actor.can_execute()`. Only addition: a guard test ensuring an Actor
that raises does not crash the loop.

### State 4 — REFLECT (Genome write)

* Extend PulseLoop with optional `genome` parameter (already in constructor)
  and a new `_reflect_to_genome()` helper that calls
  `genome.record_skill(type='trajectory', ...)` on every reflection-worthy
  pulse. Thin layer; no behavior change when `genome=None`.
* Tests: reflection-worthy pulse writes a trajectory row; non-worthy pulse
  does not; genome=None → no crash, no write.

### State 5 — DREAM (already implemented; add genome metric)

PulseLoop.DREAM already condenses episodic → LTM rules. Add an optional
`_dream_metric_to_genome()` that records the day's dream summary as a row
of `type='insight'` in Genome (precondition=dream_date, procedure=summary,
confidence=0.5 default). Tests cover write + skip-when-no-genome.

### State 6 — MATURE (skill graduation)

Add `_mature_skills()` step that runs at most once per pulse-window
(every 60 pulses by default to match the existing LTM-cache cadence). It
calls `genome.promote_skills()` and emits the result as a metric. Tests:
runs only on cadence, no-op on idle DB, returns count.

## Daemon Entrypoint

* `apps/cell/scripts/run_pulse_loop.py` — new CLI that wires:
  - SQLite Genome at `~/.cell/genome.db`
  - SqliteSTM/SqliteEpisodic/SqliteLTM at the same DB
  - OutboxSensor (DSN from env), HealthSensor (existing)
  - OllamaAwareRuleBasedThinker (env: OLLAMA_URL, OLLAMA_MODEL=qwen3.5:9b)
  - SafetyGate stub (Redis kill-switch, degrade-open)
  - PulseLoop with `metrics=None` for v0.
  - 3-cycle smoke harness: `--smoke 3` runs three cycles and prints Genome
    counts to stdout.

## LaunchAgent (post-merge step, NOT bootstrapped from PR)

`apps/cell/com.cell.organism.pulse.daemon.plist` (mode 0444 per cicatrix
P0-3): KeepAlive=true, RunAtLoad=true, ProgramArguments pointing at the
new CLI. Bootstrap step left for the operator after PR merge.

## Test Coverage Target

* ≥85% on the new modules. Unit tests per state transition (sense→think,
  think→act, act→reflect, reflect→dream, dream→mature). Integration test
  full cycle in-memory using temp-file SQLite. Live smoke test on Pro
  using `--smoke 3`.

## Constraints Honored

* **No `ANTHROPIC_API_KEY`, no `pip install anthropic`, no Anthropic SDK
  imports.** Ollama for local LLM; rule-based fallback when Ollama down.
* **Genome SQLite WAL** — already enabled by `cell_core.genome.Genome`
  (`PRAGMA journal_mode=WAL` + `busy_timeout=5000`).
* **Symbiosis Law 4** — outbox sensor degrades gracefully (PG down →
  yellow, never crash).
* **WIP commit cadence** — every state gets its own commit + push.
* **Branch hijack antibody** — verify branch before each Edit/Write.
* **Atomic git add+commit+push <30s** between writes.

## Out-of-Scope (Wave 3)

* HGT Pro↔Mini (`cell_core/hgt/`)
* Cell observatory dashboard
* Telegram CMD interface
* Replacing the older `PulseEngine` in `apps/cell/cell/main.py` (separate PR)
