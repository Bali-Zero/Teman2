# CELL Migration to cell-core — Design Spec

**Date:** 2026-04-10
**Status:** Draft
**Author:** Zero + Claude Opus 4.6

## 1. Problem

CELL (`apps/cell/`) is the progenitor organism — mature, production, 224 tests, 2057 lines of core. cell-core (`packages/cell-core/`) was extracted from CELL's patterns but CELL doesn't use it yet. Two codebases with the same logic diverge.

## 2. Strategy: Incremental Refactor, Not Rewrite

CELL's PulseEngine has 611 lines and 30+ constructor params. Rewriting it is high risk. Instead:

**Phase A (this sprint):** Replace CELL's internal modules with cell-core imports where direct 1:1 mapping exists. PulseEngine stays as orchestrator but delegates to cell-core types and utilities.

**Phase B (future):** Cortex, Dreamer, Journal, PatternIndex, Metabolism move to cell-core when 2+ organs need them.

## 3. Phase A — What Changes

### 3.1 Direct Replacements (cell-core already has these)

| CELL Module | cell-core Replacement | Change |
|---|---|---|
| `lifecycle/maturation.py` (92 lines) | `cell_core.lifecycle.Maturation` | Delete CELL's, import cell-core's |
| `fast/homeostatic_controller.py` (192 lines) | `cell_core.homeostasis.HomeostaticController` | Delete CELL's, import cell-core's |
| `fast/trend_detector.py` (92 lines) | `cell_core.homeostasis.TrendDetector` | Delete CELL's, import cell-core's |
| `identity/self_model.py` (163 lines) | `cell_core.identity.SelfModel, SelfModelManager` | Delete CELL's, import cell-core's |
| `core/safety.py` (64 lines) | `cell_core.safety.SafetyGate` | Delete CELL's, import cell-core's |
| `core/dna.py` (47 lines) | `cell_core.safety.DNALoader` | Delete CELL's, import cell-core's |

**Total removed:** ~650 lines replaced by cell-core imports.

### 3.2 Type Alignment

CELL's types (in various files) → cell-core's `types.py`:

| CELL Type | Location | cell-core Type |
|---|---|---|
| `HealthStatus` | `fast/health_triage.py` | Stays (CELL-specific enum with triage logic) |
| `PulseResult` | `core/pulse.py` | `cell_core.types.PulseResult` |
| `HomeostaticState` | `fast/homeostatic_controller.py` | `cell_core.types.HomeostaticState` |
| `Episode` | `memory/episodic.py` | `cell_core.types.Episode` |
| `TrendResult` | `fast/trend_detector.py` | `cell_core.homeostasis.TrendResult` |
| `SafetyCheckResult` | `core/safety.py` | `cell_core.types.SafetyCheckResult` |

### 3.3 What Stays in CELL (Phase A)

- `core/pulse.py` PulseEngine — stays as orchestrator, imports cell-core types
- `core/dna_interpreter.py` — stays (CELL-specific validation logic with allowlist + cooldowns)
- `core/config.py` — stays (Nuzantara URLs, tokens)
- `core/db.py` — stays (PostgreSQL schema)
- `sensors/*` — all 8 sensors stay (Nuzantara-specific)
- `effectors/*` — all 4 effectors stay (Nuzantara-specific)
- `slow/reasoner.py` — stays (Ollama-specific, CELL's own tier config)
- `memory/episodic.py` — stays (PostgreSQL-backed, different from cell-core's SQLite)
- `memory/short_term.py` — stays (Redis-backed)
- `memory/long_term.py` — stays (PostgreSQL-backed)
- `memory/pattern_index.py` — stays (FAISS, no cell-core equivalent)
- `memory/dreamer.py` — stays (Ollama LLM prompts)
- `identity/journal.py` — stays (Ollama LLM prompts)
- `cortex/*` — all 5 components stay
- `metabolism/*` — stays (attention + budget tracking)

### 3.4 Migration Steps

1. Install cell-core in CELL's venv
2. Replace imports: `from cell.lifecycle.maturation import ...` → `from cell_core.lifecycle import ...`
3. Replace imports: `from cell.fast.homeostatic_controller import ...` → `from cell_core.homeostasis import ...`
4. Replace imports: `from cell.fast.trend_detector import ...` → `from cell_core.homeostasis import ...`
5. Replace imports: `from cell.identity.self_model import ...` → `from cell_core.identity import ...`
6. Replace imports: `from cell.core.safety import ...` → `from cell_core.safety import ...`
7. Replace imports: `from cell.core.dna import ...` → `from cell_core.safety import ...`
8. Update PulseEngine to use cell-core PulseResult
9. Delete the replaced CELL modules
10. Update all test imports
11. Run 224 tests — all must pass

## 4. Compatibility Concerns

### 4.1 HomeostaticController API Difference

CELL's version: `update(response_time_ms: int, health_status: str, hour_utc: int)`
cell-core's version: same signature.

CELL uses `recommended_pulse_interval()`, cell-core uses the same name. Compatible.

### 4.2 Maturation Constructor Difference

CELL's: `Maturation(age_days: int)` — takes age directly.
cell-core's: `Maturation(birth_date: datetime)` — computes age.

**Fix:** In `main.py`, change `Maturation(age_days=self_model.model.age_days)` to `Maturation(birth_date=datetime.fromisoformat(self_model.model.birth_date))`.

### 4.3 SelfModelManager API

CELL's `record_action()` takes no args.
cell-core's `record_action(action_name: str)` takes the action name.

**Fix:** Update call sites in PulseEngine to pass action name.

### 4.4 SafetyGate Constructor

CELL's: `SafetyGate(redis=client, disable_file="/tmp/cell.disabled")`
cell-core's: `SafetyGate(disable_file="/tmp/cell.disabled", redis=client, cell_name="cell")`

**Fix:** Add `cell_name="cell"` kwarg. Redis key pattern changes from `cell:disabled` to `cell:cell:disabled` — need to verify.

Actually, cell-core uses `cell:{cell_name}:disabled`. For CELL, cell_name="cell" → `cell:cell:disabled`. But CELL currently checks `cell:disabled`. Two options:
- A) Change cell-core to use `cell:disabled` when cell_name="cell" (breaks cell-core contract)
- B) Update Redis keys (need to update any scripts/monitoring that sets `cell:disabled`)
- C) Keep CELL's SafetyGate but import cell-core types

**Decision: C for now.** CELL keeps its own SafetyGate (64 lines, Redis-specific) but imports `SafetyCheckResult` from cell-core. This is pragmatic — the kill switch key format is a deployment detail, not an architecture decision.

## 5. Phase A File Changes

| Action | File | Lines Removed |
|---|---|---|
| DELETE | `cell/lifecycle/maturation.py` | 92 |
| DELETE | `cell/fast/homeostatic_controller.py` | 192 |
| DELETE | `cell/fast/trend_detector.py` | 92 |
| DELETE | `cell/identity/self_model.py` | 163 |
| DELETE | `cell/core/dna.py` | 47 |
| KEEP | `cell/core/safety.py` | 0 (import SafetyCheckResult from cell-core) |
| MODIFY | `cell/core/pulse.py` | Update imports |
| MODIFY | `cell/main.py` | Update imports + Maturation constructor |
| MODIFY | `cell/slow/reasoner.py` | Update Episode import |
| MODIFY | `cell/memory/episodic.py` | Import Episode from cell-core |
| MODIFY | `cell/cortex/cortex.py` | Update imports |
| MODIFY | All test files referencing replaced modules | Update imports |

**Net reduction:** ~586 lines of CELL code replaced by cell-core imports.

## 6. Testing Strategy

1. Run 224 tests before any changes (baseline)
2. After each module replacement, run tests
3. After all replacements, run full suite
4. Verify no import errors with: `python -c "from cell.core.pulse import PulseEngine"`

## 7. Success Criteria

1. 224 tests pass (zero regressions)
2. `cell/lifecycle/maturation.py`, `cell/fast/homeostatic_controller.py`, `cell/fast/trend_detector.py`, `cell/identity/self_model.py`, `cell/core/dna.py` deleted
3. CELL imports `Maturation`, `HomeostaticController`, `TrendDetector`, `SelfModel`, `SelfModelManager`, `DNALoader`, `HomeostaticState`, `TrendResult`, `PulseResult`, `Episode`, `SafetyCheckResult` from cell-core
4. CELL's production behavior unchanged (same pulse cycle, same outputs)
