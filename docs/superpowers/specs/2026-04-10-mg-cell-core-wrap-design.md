# Mata Garuda cell-core Wrap Design

**Date:** 2026-04-10
**Status:** Draft
**Author:** Zero + Claude Opus 4.6
**Consulted:** Gemini CLI, Claude CLI

## 1. Problem

Mata Garuda and cell-core implement the same biological patterns separately. MG is in production (188 tests, daily cron). cell-core is ready (110 tests). Neither uses the other.

## 2. Strategy: Wrap, Don't Replace

PulseLoop wraps MG's existing system. MG code stays intact, cell-core orchestrates from above. Zero MG tests break.

**Metaphor (Gemini):** cell-core is the **brainstem** (survival, rhythm, homeostasis). MG is the **cerebral cortex** (high-order intelligence, learning). The brainstem keeps the cortex alive and regulated; the cortex does the actual thinking.

## 3. Architecture

```
PulseLoop (cell-core)
  ├── Sensors: RegulationSensor, GapSensor, FitnessSensor
  ├── Thinker: PassthroughThinker (MG decides internally)  
  ├── Actor: MetaChainActor (wraps existing MetaChain loop)
  ├── Memory: KnowledgeBridgeLTM (wraps existing knowledge.py)
  ├── Safety: SafetyGate (file kill switch) + DNA (immutable rules)
  ├── Homeostasis: stress from fitness, energy from budget
  └── Lifecycle: Maturation (MG born 2026-04-01)
```

### 3.1 Mapping

| cell-core Protocol | MG Implementation | How |
|---|---|---|
| `Sensor` | regulation_watcher check, gap detector, fitness sensor | New thin wrappers that call existing MG code |
| `Thinker` | MG's internal logic (MetaChain + LLM) | Passthrough — MG already reasons, PulseLoop just checks if thinking is needed |
| `Actor` | MetaChain loop (run_agent_loop) | `ThreadedActorProxy` wraps sync MG call via `asyncio.to_thread()` |
| `STMStore` | Not needed initially | Use cell-core's SqliteSTM (new, separate from knowledge.db) |
| `LTMStore` | knowledge.py KnowledgeBase | Bridge adapter: wraps KB's store/search as store_rule/load_rules/condense |
| `EpisodicStore` | reflection.py outputs | Bridge adapter: reflections become episodes |
| `SafetyGate` | path_firewall.py | cell-core SafetyGate (file kill switch) + MG's firewall stays |
| `DNA` | Immutable rules (budget, safety) | New `apps/mata-garuda/dna.json` — constitutional rules MG can never break |
| `GENOME` | GENOME.md (mutable, Lamarckian) | Stays in MG domain. cell-core doesn't manage it. DNA != GENOME. |
| `Maturation` | fitness.py success rate | New: MG gets lifecycle phases. Birth: 2026-04-01 |
| `HomeostaticController` | fitness.py + run metrics | Fitness feeds stress. Token budget feeds energy. |

### 3.2 DNA vs GENOME (Critical Design Decision)

**DNA** (cell-core, immutable, SHA-256 verified):
- Constitutional rules: "Never modify DNA", "Never send OSINT data outside Pro", "Budget < $10/day"
- Cannot be mutated by any agent, ever
- Verified every pulse

**GENOME** (MG, mutable, Lamarckian):  
- Agent personality: scraping strategies, regex patterns, escalation thresholds
- Mutated by feedback loop, approved by Zero, auto-reverted if fitness drops
- Stays entirely in MG domain — cell-core never reads or manages it

DNA = constitution. GENOME = personality. (Claude CLI recommendation, unanimously endorsed.)

### 3.3 Async/Sync Bridge

MG is synchronous (subprocess LLM calls). cell-core is async.

**Solution:** `MetaChainActor.act()` uses `asyncio.to_thread()` to wrap the sync MetaChain loop:

```python
class MetaChainActor:
    async def act(self, proposal: Proposal) -> str:
        return await asyncio.to_thread(self._run_sync, proposal)
    
    def _run_sync(self, proposal: Proposal) -> str:
        # existing MetaChain loop logic — unchanged
        ...
```

MG's 188 tests continue to test the sync core directly. cell-core tests test the async wrapper. No test pollution.

### 3.4 Homeostasis Mapping (Gemini recommendation)

MG's fitness.py becomes a **Sensor input** to HomeostaticController:

| MG Signal | Homeostasis Variable | Effect |
|---|---|---|
| fitness success rate dropping | stress rises | PulseLoop triggers more frequent pulses |
| fitness success rate stable | stress decays | PulseLoop relaxes interval |
| tokens_used per run | energy drain | High cost runs drain energy budget |
| green run (no errors) | energy recovery | Healthy cycles replenish |
| circadian (02:00-06:00 UTC) | sleep phase | Dream phase: consolidation via reflection |

**Homeostasis regulates PulseLoop frequency:**
- Stressed (fitness dropping): pulse every 15min — more runs, faster learning
- Calm (fitness stable): pulse every 60min — routine monitoring
- Sleeping (02:00-06:00): pulse every 5h — consolidation only, no scraping

### 3.5 Dream Phase = Reflection + Consolidation

During sleep window, PulseLoop triggers:
1. `LTMStore.condense()` → calls knowledge.py to extract rules from recent reflections
2. `EpisodicStore.forget_weak()` → prune low-activation reflections
3. Lamarckian review: if pending mutations exist, evaluate fitness trend

This replaces manual reflection triggers with an automatic circadian cycle.

### 3.6 Maturation for MG

MG born 2026-04-01. As of 2026-04-10, age = 9 days = **neonato** phase.

| Phase | MG Behavior |
|---|---|
| Embrione (0-3d) | Observe only. Log but don't act. (Already past this.) |
| Neonato (4-14d) | Act with high confidence only (threshold 0.8). Current phase. |
| Giovane (15-30d) | Autonomous + dreaming. Gap detector can auto-dispatch. |
| Adulto (31-179d) | Full autonomy. Curiosity engine proposes own tasks. |
| Anziano (180d+) | Stability priority. Conservative mutations. |

This gives MG a natural growth curve instead of being "fully autonomous from day 1".

## 4. File Structure (New/Modified)

### New files in apps/mata-garuda/

| File | Purpose |
|---|---|
| `mata_garuda/cell/config.py` | CellConfig for MG + dna.json path |
| `mata_garuda/cell/sensors.py` | RegulationSensor, GapSensor, FitnessSensor |
| `mata_garuda/cell/thinker.py` | PassthroughThinker (delegates to MG) |
| `mata_garuda/cell/actor.py` | MetaChainActor (wraps MetaChain loop) |
| `mata_garuda/cell/memory_bridge.py` | KnowledgeBridgeLTM, ReflectionEpisodicStore |
| `mata_garuda/cell/runner.py` | Build and run the PulseLoop |
| `mata_garuda/dna.json` | Immutable constitutional rules |
| `tests/test_cell_sensors.py` | Sensor protocol tests |
| `tests/test_cell_actor.py` | Actor wrapper tests |
| `tests/test_cell_memory.py` | Memory bridge tests |
| `tests/test_cell_runner.py` | Integration: full pulse cycle |

### NOT modified

- `mata_garuda/runtime/loop.py` — MetaChain stays as-is
- `mata_garuda/runtime/knowledge.py` — KB stays as-is
- `mata_garuda/runtime/reflection.py` — stays as-is
- `mata_garuda/runtime/lamarckian.py` — stays as-is
- `mata_garuda/runtime/fitness.py` — stays as-is
- `mata_garuda/agents/*` — all agents stay as-is
- `mata_garuda/tools/*` — all tools stay as-is
- All 188 existing tests — untouched

## 5. Entry Point

New CLI command:

```bash
python -m mata_garuda.cell.runner
```

Or via existing CLI:

```bash
mg cell start   # starts PulseLoop (runs forever)
mg cell pulse   # single pulse (for testing)
mg cell status  # shows lifecycle phase, stress, energy
```

The existing `mg run <agent>` continues to work for direct agent execution. `mg cell` adds the organism layer on top.

## 6. Dependencies

- `cell-core` added to MG's dev dependencies (local path: `../../packages/cell-core`)
- Zero new external packages (cell-core is stdlib-only)

## 7. Migration Path

1. **Now:** Add cell/ wrapper layer. Both entry points work (mg run + mg cell).
2. **Week 2:** Cron switches from direct `mg run regulation_watcher` to `mg cell start`. PulseLoop manages scheduling.
3. **Week 4:** Remove direct cron, PulseLoop is the sole entry point. Homeostasis manages frequency.
4. **Future:** New agents (gap detector, JDIH harvester) born as Sensors, never as standalone scripts.

## 8. What cell-core Wrap Does NOT Change

- GENOME.md mutation flow (stays Lamarckian, human-approved)
- path_firewall.py (stays as-is, additional safety layer)
- OSINT blindado (data never leaves Pro)
- CLI-only LLM (subprocess, never SDK)
- Redis stream publishing (garuda:raw)
- 188 existing tests

## 9. Success Criteria

1. `pytest tests/` passes (188 existing + ~20 new cell tests)
2. `mg cell pulse` runs one full cycle: sense → think → act → reflect
3. HomeostaticController shows stress/energy from fitness data
4. Maturation correctly reports neonato phase
5. Dream phase triggers reflection consolidation during sleep window
6. DNA integrity verified every pulse
7. Existing `mg run regulation_watcher` still works unchanged
