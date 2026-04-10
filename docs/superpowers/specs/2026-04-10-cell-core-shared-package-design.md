# CELL Core — Shared Organism Package Design

**Date:** 2026-04-10
**Status:** Draft
**Author:** Zero + Claude Opus 4.6
**Consulted:** Gemini CLI, Claude CLI, DeepSeek API

## 1. Problem

CELL (`apps/cell/`) and Mata Garuda (`apps/mata-garuda/`) are building the same biological patterns independently:

| Concept | CELL (exists) | MG Sprint 5 (planned) |
|---------|---------------|----------------------|
| Memory | Episodic (PostgreSQL, ACT-R) | Knowledge KB (SQLite, FTS5) |
| Consolidation | Dreamer (nightly, Ollama) | Reflection (post-run, subprocess LLM) |
| Learning | LTM weekly rules | Skills as KB rows |
| Lifecycle | Maturation (5 phases) | Lamarckian fitness |
| Identity | SelfModel (JSON) | GENOME.md mutations |
| Safety | DNA + Safety Gates | Path firewall |

Without intervention, Sprint 5 creates a parallel system. Unification "later" won't happen (ref: `feedback_no_pragmatic_divergence.md`).

## 2. Vision

CELL is the stem cell. Every Nuzantara agent is a differentiated cell that inherits the same nucleus (pulse, memory, lifecycle, safety) and specializes its own sensors and effectors.

`packages/cell-core/` provides the nucleus. `apps/cell/` and `apps/mata-garuda/` import it.

## 3. Architecture Decision: Protocol + Composition

**Decision:** PulseLoop is a **concrete orchestrator** that takes **Protocol implementations** via constructor injection. NOT an ABC to subclass.

**Rationale** (validated by Claude CLI, Gemini CLI, DeepSeek):

1. **ABC creates version coupling.** Adding a lifecycle phase requires base class change → both consumers update simultaneously. With 224+105 tests, this is a coordination tax.
2. **Lifecycle ordering is the Runner's job.** `PulseLoop.pulse()` is the template method that guarantees sense→think→act→reflect→dream→mature. Protocols provide the implementations. The Runner enforces the contract.
3. **Substitutability is explicit.** SQLite vs PostgreSQL is `EpisodicStore` protocol, not a subclass hierarchy.
4. **Testability.** Mock individual protocols without subclassing. Simple fakes, not complex inheritance trees.
5. **Homeostasis belongs in core** (Gemini: "without it you have a cron job"). It's the governor that makes this biological, not just a scheduler.

## 4. Package Structure

```
packages/cell-core/
├── __init__.py           # Public API exports
├── types.py              # Shared dataclasses
├── protocols.py          # All Protocol definitions (Sensor, Thinker, Actor, STM, LTM, Episodic)
├── pulse.py              # PulseLoop — concrete lifecycle runner
├── memory_sqlite.py      # SQLite backend (default, zero deps)
├── memory_pg.py          # PostgreSQL backend (optional, requires asyncpg)
├── lifecycle.py          # Maturation phases + confidence gates
├── safety.py             # Gate framework + DNA loader/interpreter
├── reasoner.py           # Tier escalation framework
├── homeostasis.py        # Homeostatic controller + trend detector
├── identity.py           # SelfModel base (JSON file persistence)
└── pyproject.toml        # Package metadata
```

**9 source files.** No nested packages. Flat = readable. All protocols in one file.

### Dependencies

- **Required:** None beyond stdlib (`sqlite3`, `json`, `dataclasses`, `typing`, `asyncio`, `pathlib`, `math`, `time`, `logging`, `enum`)
- **Optional:** `asyncpg` (only if importing `memory_pg`), `redis`/`aioredis` (only if using Redis STM)
- **Respects:** SYMBIOSIS Law #1 (CLI-only for LLM — reasoner framework takes subprocess commands, not API clients)

## 5. Module Specifications

### 5.1 types.py — Shared Vocabulary

All dataclasses that every cell uses internally. No logic, only structures.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

class Phase(str, Enum):
    EMBRIONE = "embrione"   # day 0-3: observe only
    NEONATO = "neonato"     # day 4-14: act with high confidence
    GIOVANE = "giovane"     # day 15-30: autonomous + dreams
    ADULTO = "adulto"       # day 31-179: full autonomy
    ANZIANO = "anziano"     # day 180+: stability priority

@dataclass
class CellConfig:
    """Configuration for one organ/agent."""
    name: str                           # "cell", "mata-garuda", "evaluator"
    dna_path: str                       # path to organ-specific dna.json
    pulse_interval_seconds: int = 60
    birth_date: datetime | None = None  # for lifecycle calculation
    memory_backend: str = "sqlite"      # "sqlite" | "postgres"
    db_path: str = "cell.db"            # SQLite path (if sqlite backend)
    sleep_hours: tuple[int, int] = (2, 6)  # UTC hours for circadian sleep

@dataclass
class SensorReading:
    sensor_name: str
    status: Literal["green", "yellow", "red"]
    value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Proposal:
    action: str          # action name from allowlist, or "none"
    reason: str
    confidence: float    # 0.0 - 1.0
    tier_used: int       # -1=pattern, 0=fast, 1=deep
    cost_usd: float = 0.0

@dataclass
class Episode:
    situation: dict[str, Any]
    emotion: str         # calm, alert, stressed, panic
    action_taken: str
    outcome: str         # success, partial, failure
    lesson: str
    id: int = 0
    timestamp: float = 0.0
    recall_count: int = 0
    activation: float = 0.0

@dataclass
class LearnedRule:
    rule_text: str
    support_count: int
    created_at: str = ""

@dataclass
class HomeostaticState:
    stress_level: float = 0.0
    energy_level: float = 1.0
    arousal: float = 0.5
    comfort_zone: tuple[float, float] = (50.0, 200.0)
    setpoint_rt_ms: float = 100.0
    circadian_phase: str = "awake"  # "awake" | "drowsy" | "asleep"

@dataclass
class PulseResult:
    timestamp: datetime
    pulse_number: int
    halted: bool = False
    halt_reason: str = ""
    skipped: bool = False
    skip_reason: str = ""
    health_status: str | None = None
    action_taken: str | None = None
    action_reason: str | None = None
    thought_tier: int | None = None
    error: str | None = None

@dataclass
class SafetyCheckResult:
    can_proceed: bool
    reason: str = ""
    detail: str = ""

@dataclass
class DNARule:
    text: str
    priority: int

@dataclass
class DNAConfig:
    rules: list[DNARule]
    constraints: dict[str, Any]
```

### 5.2 protocols.py — The Contracts

Runtime-checkable Protocol classes. Each organ provides its own implementations.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Sensor(Protocol):
    """Perceives one aspect of the environment."""
    name: str
    async def read(self, **context: Any) -> SensorReading: ...

@runtime_checkable
class Thinker(Protocol):
    """Reasons about sensor readings and proposes actions."""
    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal: ...

@runtime_checkable
class Actor(Protocol):
    """Executes a proposed action."""
    async def act(self, proposal: Proposal) -> str: ...
    def can_execute(self, action_name: str) -> bool: ...

@runtime_checkable
class STMStore(Protocol):
    """Short-term memory — volatile, TTL-based."""
    async def store(self, event_type: str, data: dict) -> None: ...
    async def recent(self, event_type: str, limit: int) -> list[dict]: ...

@runtime_checkable
class LTMStore(Protocol):
    """Long-term memory — persistent learned rules."""
    async def store_rule(self, rule: LearnedRule) -> None: ...
    async def load_rules(self, limit: int) -> list[LearnedRule]: ...
    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]: ...

@runtime_checkable
class EpisodicStore(Protocol):
    """Episodic memory — significant moments with ACT-R activation."""
    async def store(self, episode: Episode) -> int: ...
    async def recall(self, situation: dict, limit: int) -> list[Episode]: ...
    async def recall_recent(self, hours: int, limit: int) -> list[Episode]: ...
    async def forget_weak(self, keep: int) -> int: ...
```

**3 sub-protocols for memory** (DeepSeek recommendation). Each composable independently. A light agent can use SQLite for all three. A heavy agent can mix PostgreSQL episodic + Redis STM.

### 5.3 pulse.py — The Lifecycle Runner

Concrete class. Guarantees phase ordering. Takes protocols via constructor.

```python
class PulseLoop:
    """The heartbeat. Orchestrates: sense→think→act→reflect→dream→mature.
    
    This is a CONCRETE class, not an ABC. Variation is via protocol
    implementations passed to the constructor.
    """
    
    def __init__(
        self,
        config: CellConfig,
        sensors: list[Sensor],
        thinker: Thinker,
        actor: Actor,
        stm: STMStore,
        ltm: LTMStore,
        episodic: EpisodicStore,
        lifecycle: Maturation,
        safety: SafetyGate,
        homeostasis: HomeostaticController | None = None,
        identity: SelfModel | None = None,
        on_pulse: Callable[[PulseResult], Awaitable[None]] | None = None,
    ):
        self.config = config
        self.sensors = sensors
        self.thinker = thinker
        self.actor = actor
        self.stm = stm
        self.ltm = ltm
        self.episodic = episodic
        self.lifecycle = lifecycle
        self.safety = safety
        self.homeostasis = homeostasis or HomeostaticController(config.sleep_hours)
        self.identity = identity
        self.on_pulse = on_pulse
        self.pulse_count = 0
        self._recent_pulses: list[dict] = []
    
    async def run(self):
        """Infinite loop. Call this and the cell lives."""
        while True:
            result = await self.single_pulse()
            if self.on_pulse:
                await self.on_pulse(result)
            interval = self.homeostasis.next_interval()
            await asyncio.sleep(interval)
    
    async def single_pulse(self) -> PulseResult:
        """One complete lifecycle tick."""
        self.pulse_count += 1
        now = datetime.now(timezone.utc)
        
        # 0. SAFETY CHECK
        safety_result = await self.safety.check()
        if not safety_result.can_proceed:
            return PulseResult(
                timestamp=now, pulse_number=self.pulse_count,
                halted=True, halt_reason=safety_result.reason,
            )
        
        # 1. SENSE — collect all sensor readings
        readings = []
        for sensor in self.sensors:
            try:
                reading = await sensor.read()
                readings.append(reading)
            except Exception as e:
                readings.append(SensorReading(
                    sensor_name=sensor.name, status="red",
                    metadata={"error": str(e)},
                ))
        
        # 2. EVALUATE — fast homeostatic update
        worst_status = max(
            (r.status for r in readings),
            key=lambda s: {"green": 0, "yellow": 1, "red": 2}[s],
            default="green",
        )
        state = self.homeostasis.update(readings, worst_status, now.hour)
        trend = self.homeostasis.detect_trend(self._recent_pulses)
        
        # Store in STM
        for reading in readings:
            await self.stm.store(reading.sensor_name, {
                "status": reading.status,
                "value": reading.value,
                "stress": state.stress_level,
                "energy": state.energy_level,
            })
        
        self._recent_pulses.append({
            "pulse": self.pulse_count, "status": worst_status,
            "stress": state.stress_level, "timestamp": now.isoformat(),
        })
        if len(self._recent_pulses) > 50:
            self._recent_pulses = self._recent_pulses[-50:]
        
        # 3. THINK — if needed
        proposal = Proposal(action="none", reason="stable", confidence=0.0, tier_used=-1)
        should_think = (
            worst_status != "green"
            or trend.get("is_anomalous", False)
        )
        if should_think and self.lifecycle.can_act():
            ltm_rules = await self.ltm.load_rules(limit=10)
            recent_episodes = await self.episodic.recall_recent(hours=24, limit=5)
            memory_context = {
                "ltm_rules": [r.rule_text for r in ltm_rules],
                "recent_episodes": [
                    {"action": e.action_taken, "outcome": e.outcome, "lesson": e.lesson}
                    for e in recent_episodes
                ],
            }
            proposal = await self.thinker.think(readings, state, memory_context)
        
        # 4. ACT — if approved
        action_taken = None
        if proposal.action != "none":
            threshold = self.lifecycle.action_confidence_threshold()
            if (proposal.confidence >= threshold
                    and self.actor.can_execute(proposal.action)):
                action_taken = await self.actor.act(proposal)
        
        # 5. REFLECT — store episode if significant
        if action_taken or worst_status != "green":
            emotion = self._derive_emotion(state)
            episode = Episode(
                situation={
                    "readings": [{
                        "sensor": r.sensor_name, "status": r.status,
                    } for r in readings],
                    "stress": state.stress_level,
                    "energy": state.energy_level,
                },
                emotion=emotion,
                action_taken=proposal.action,
                outcome=action_taken or "no_action",
                lesson="",  # filled by dreamer during consolidation
            )
            await self.episodic.store(episode)
        
        # 6. DREAM — during sleep window
        if self.homeostasis.is_sleeping() and self.lifecycle.can_dream():
            recent = await self.episodic.recall_recent(hours=24, limit=50)
            if recent:
                new_rules = await self.ltm.condense(recent)
                for rule in new_rules:
                    await self.ltm.store_rule(rule)
                await self.episodic.forget_weak(keep=500)
        
        # 7. MATURE — lifecycle tick
        self.lifecycle.tick(self.pulse_count)
        
        # Update identity if present
        if self.identity:
            self.identity.record_pulse()
            if action_taken:
                self.identity.record_action(proposal.action)
        
        return PulseResult(
            timestamp=now,
            pulse_number=self.pulse_count,
            health_status=worst_status,
            action_taken=action_taken,
            action_reason=proposal.reason if action_taken else None,
            thought_tier=proposal.tier_used if should_think else None,
        )
    
    def _derive_emotion(self, state: HomeostaticState) -> str:
        if state.stress_level > 0.8:
            return "panic"
        if state.stress_level > 0.5:
            return "stressed"
        if state.stress_level > 0.2:
            return "alert"
        return "calm"
```

### 5.4 memory_sqlite.py — Default Backend (Zero Dependencies)

SQLite implementation of all 3 memory protocols. This is what Mata Garuda Sprint 5 uses out of the box.

```python
class SqliteSTM(STMStore):
    """Short-term memory in SQLite with TTL cleanup."""
    # Table: stm (id, event_type, data_json, created_at)
    # Cleanup: DELETE WHERE created_at < now - ttl_seconds on every store()

class SqliteLTM(LTMStore):
    """Long-term rules in SQLite with FTS5 search."""
    # Table: ltm (id, rule_text, support_count, created_at)
    # FTS5: ltm_fts (rule_text) for fast text search
    # condense(): groups similar episodes, extracts rule via pattern matching

class SqliteEpisodic(EpisodicStore):
    """Episodic memory in SQLite with ACT-R activation scoring."""
    # Table: episodes (id, situation_json, emotion, action_taken, outcome, lesson,
    #                   timestamp, recall_count, activation)
    # recall(): computes activation = base + recency + frequency, sorts descending
    # forget_weak(): DELETE lowest activation beyond keep limit

class SqliteMemoryStack:
    """Convenience: creates all 3 stores from one SQLite DB path."""
    def __init__(self, db_path: str = "cell.db"):
        self.stm = SqliteSTM(db_path)
        self.ltm = SqliteLTM(db_path)
        self.episodic = SqliteEpisodic(db_path)
```

### 5.5 memory_pg.py — PostgreSQL Backend (Optional)

For CELL's production deployment. Requires `asyncpg`.

```python
class PgSTM(STMStore):
    """Redis-backed STM (preserves current CELL behavior)."""
    # Delegates to Redis with cell:stm:* key pattern

class PgLTM(LTMStore):
    """PostgreSQL-backed LTM (preserves cell_ltm table)."""
    # Uses existing cell_ltm schema

class PgEpisodic(EpisodicStore):
    """PostgreSQL-backed episodic with ACT-R (preserves cell_episodes)."""
    # Uses existing schema, async via asyncpg pool

class PgMemoryStack:
    """Convenience: PostgreSQL + Redis combo for production CELL."""
    def __init__(self, pg_pool, redis):
        self.stm = PgSTM(redis)  # STM stays in Redis (TTL native)
        self.ltm = PgLTM(pg_pool)
        self.episodic = PgEpisodic(pg_pool)
```

### 5.6 lifecycle.py — Maturation

Direct extraction from `cell/lifecycle/maturation.py`. Unchanged logic.

```python
class Maturation:
    """Lifecycle phase based on age in days."""
    def __init__(self, birth_date: datetime):
        self.birth_date = birth_date
        self.total_pulses = 0
    
    @property
    def age_days(self) -> int: ...
    
    @property
    def phase(self) -> Phase: ...
    
    def can_act(self) -> bool: ...
    def can_dream(self) -> bool: ...
    def can_reason_deep(self) -> bool: ...
    def action_confidence_threshold(self) -> float: ...
    def tick(self, pulse_count: int) -> None: ...
```

Phase thresholds (unchanged):
- Embrione: 0-3 days, threshold 1.1 (blocks all)
- Neonato: 4-14 days, threshold 0.8
- Giovane: 15-30 days, threshold 0.5
- Adulto: 31-179 days, threshold 0.0
- Anziano: 180+ days, threshold 0.0

### 5.7 safety.py — Gate Framework + DNA

```python
class SafetyGate:
    """Kill switch + maintenance mode. Organ-agnostic."""
    def __init__(self, disable_file: str = "/tmp/cell.disabled",
                 redis: Any = None):
        # File kill switch always works (even without Redis)
        # Redis kill switches: cell:{name}:disabled, cell:{name}:maintenance
    
    async def check(self) -> SafetyCheckResult: ...

class DNALoader:
    """Loads organ-specific DNA rules from JSON file."""
    def load(self, path: str) -> DNAConfig: ...
    def verify_hash(self, expected: str) -> bool: ...

class DNAInterpreter:
    """Validates proposed actions against DNA rules + constraints."""
    def __init__(self, dna: DNAConfig): ...
    def validate(self, proposal: Proposal, budget_spent: float) -> SafetyCheckResult: ...
```

### 5.8 homeostasis.py — The Governor

Direct extraction from `cell/fast/homeostatic_controller.py` + `trend_detector.py`. The biological heart.

```python
class HomeostaticController:
    """Maintains internal equilibrium. <1ms per update."""
    
    def __init__(self, sleep_hours: tuple[int, int] = (2, 6)): ...
    
    def update(
        self,
        readings: list[SensorReading],
        worst_status: str,
        hour_utc: int,
    ) -> HomeostaticState: ...
    
    def detect_trend(self, recent_pulses: list[dict]) -> dict:
        """Returns {is_anomalous, pattern: monotonic_drift|flapping|sustained_degraded}"""
        ...
    
    def is_sleeping(self) -> bool: ...
    
    def next_interval(self) -> float:
        """Adaptive pulse interval based on stress/energy/arousal."""
        ...
```

Homeostasis is generic: any agent has stress (error rate), energy (budget), arousal (activity level), and circadian rhythm (maintenance windows). Not infra-specific.

### 5.9 reasoner.py — Tier Escalation Framework

```python
class TierConfig:
    """Configuration for one reasoning tier."""
    tier: int           # -1, 0, 1, ...
    name: str           # "pattern_match", "qwen_fast", "gemma_deep"
    command: list[str]  # subprocess command (SYMBIOSIS Law #1: CLI-only)
    max_cost_usd: float
    timeout_seconds: float

class ReasonerFramework:
    """Tier-based escalation. Tries cheapest tier first."""
    
    def __init__(self, tiers: list[TierConfig], allowlist: list[str]):
        # Tiers sorted by cost ascending
        ...
    
    async def reason(
        self,
        situation: str,
        context: dict[str, Any],
    ) -> Proposal:
        """Escalates through tiers until one produces a confident proposal."""
        ...
```

The framework provides the escalation loop. Each organ configures which LLMs and commands to use. CELL uses Ollama (qwen3.5, gemma4). MG uses `claude --print` and `gemini -p`.

### 5.10 identity.py — SelfModel

```python
class SelfModel:
    """Persistent identity across restarts. JSON file."""
    
    def __init__(self, path: str = "data/self_model.json"):
        self.path = Path(path)
        self.data: dict = self._load()
    
    def record_pulse(self) -> None: ...
    def record_action(self, action_name: str) -> None: ...
    def update_sensor_reliability(self, sensor: str, success: bool) -> None: ...
    def save(self) -> None: ...  # atomic POSIX write
    
    @property
    def age_days(self) -> int: ...
    
    @property
    def total_pulses(self) -> int: ...
```

## 6. How Consumers Use cell-core

### 6.1 CELL (Infrastructure Monitor)

```python
from cell_core import PulseLoop, CellConfig, Maturation, SafetyGate
from cell_core import HomeostaticController, SelfModel
from cell_core.memory_pg import PgMemoryStack
from cell_core.protocols import Sensor, Thinker, Actor

# CELL's existing sensors become Protocol implementations
class HealthSensor:
    name = "health"
    async def read(self, **ctx) -> SensorReading:
        # existing HTTP health check logic
        ...

class OllamaReasoner:
    async def think(self, readings, state, memory_context) -> Proposal:
        # existing SlowReasoner logic (Ollama tiers)
        ...

class FlyActor:
    async def act(self, proposal) -> str:
        # existing FlyEffector + LocalEffector logic
        ...
    def can_execute(self, action_name) -> bool:
        return action_name in self.allowlist

# Wire it up
config = CellConfig(
    name="cell",
    dna_path="apps/cell/cell/config/dna.json",
    birth_date=datetime(2026, 3, 26, 14, 56, 56, tzinfo=timezone.utc),
    memory_backend="postgres",
)
mem = PgMemoryStack(pg_pool, redis)
cell = PulseLoop(
    config=config,
    sensors=[HealthSensor(), DatabaseSensor(), QdrantSensor(), ...],
    thinker=OllamaReasoner(),
    actor=FlyActor(allowlist),
    stm=mem.stm, ltm=mem.ltm, episodic=mem.episodic,
    lifecycle=Maturation(config.birth_date),
    safety=SafetyGate(redis=redis),
    identity=SelfModel("data/self_model.json"),
)
await cell.run()
```

### 6.2 Mata Garuda (Intelligence Agent)

```python
from cell_core import PulseLoop, CellConfig, Maturation, SafetyGate
from cell_core.memory_sqlite import SqliteMemoryStack

class RegulationSensor:
    name = "regulations"
    async def read(self, **ctx) -> SensorReading:
        # scrape peraturan.go.id, check for new regulations
        ...

class GapSensor:
    name = "knowledge_gaps"
    async def read(self, **ctx) -> SensorReading:
        # read nexus:gaps Redis stream
        ...

class CLIReasoner:
    async def think(self, readings, state, memory_context) -> Proposal:
        # subprocess: claude --print "Given these readings..."
        ...

class RedisPublisher:
    async def act(self, proposal) -> str:
        # publish to garuda:raw Redis stream
        ...
    def can_execute(self, action_name) -> bool:
        return action_name in {"publish", "scrape", "alert_human"}

config = CellConfig(
    name="mata-garuda",
    dna_path="apps/mata-garuda/dna.json",
    birth_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
    pulse_interval_seconds=3600,  # hourly, not every 60s
    sleep_hours=(2, 6),
)
mem = SqliteMemoryStack("mata_garuda_cell.db")
mg = PulseLoop(
    config=config,
    sensors=[RegulationSensor(), GapSensor()],
    thinker=CLIReasoner(),
    actor=RedisPublisher(),
    stm=mem.stm, ltm=mem.ltm, episodic=mem.episodic,
    lifecycle=Maturation(config.birth_date),
    safety=SafetyGate(),  # no Redis needed, file kill switch only
)
await mg.run()
```

## 7. Migration Strategy

### Phase 1: Extract cell-core (this sprint)

1. Create `packages/cell-core/` with all modules
2. Write tests for cell-core (extract from CELL's 224 tests + new protocol tests)
3. Verify: `pytest packages/cell-core/tests/ -q` passes

### Phase 2: MG Sprint 5 uses cell-core

1. MG Sprint 5 imports cell-core instead of building reflection.py + knowledge.py from scratch
2. Sprint 5 tasks become: implement `RegulationSensor`, `GapSensor`, `CLIReasoner`, `RedisPublisher`, configure `CellConfig` + `dna.json`
3. Sprint 5 `lamarckian.py` becomes a hook on `PulseLoop.on_pulse` callback

### Phase 3: CELL migrates to cell-core (next sprint)

1. Replace `cell/core/pulse.py` PulseEngine with cell-core PulseLoop
2. Wrap existing sensors as Protocol implementations
3. Swap memory classes to cell-core's PgMemoryStack
4. Run CELL's 224 tests against new wiring

### Phase 4: Future organs adopt cell-core

- Evaluator, bali-intel-scraper, any new agent → import cell-core, implement protocols, wire PulseLoop.

## 8. What cell-core Does NOT Include

Extracted to organ-specific code:

- **Specific sensors** (HealthSensor, DatabaseSensor, etc.) → stay in `apps/cell/`
- **Specific effectors** (FlyEffector, TelegramAlerter, etc.) → stay in `apps/cell/`
- **Specific LLM config** (Ollama models, prompt templates) → organ's reasoner implementation
- **Cortex** (critic, curiosity, goals, mutations) → stays in `apps/cell/` for now. Phase 3-4 of CELL vivente. Will migrate to cell-core when at least 2 organs use cortex features.
- **Frontend components** (CellDashboard, VitalSigns, etc.) → stay in `apps/mouth/`
- **Dreamer** — the dreaming *strategy* stays in cell-core (LTM.condense during sleep). The Dreamer *class* with LLM prompts stays organ-specific.
- **Journal** — stays organ-specific. Different organs journal differently.

## 9. Impact on SYMBIOSIS.md

Update required:

```markdown
### L0 Cellular — cell-core (NEW)
Every organ is a differentiated cell. `packages/cell-core/` provides:
- PulseLoop (lifecycle runner)
- Memory stack (STM/LTM/Episodic)
- Lifecycle (maturation phases)
- Safety (DNA + gates)
- Homeostasis (governor)
- Identity (self-model)

Organs implement: Sensor, Thinker, Actor protocols.
Communication between organs: L1 (Redis Streams) unchanged.
```

The 8 pillars map directly to cell-core:
1. Riflessione → `EpisodicStore.store()` (REFLECT phase)
2. Accumulazione → `LTMStore.store_rule()` (DREAM phase)
3. Condivisione → Redis Streams (unchanged, organ-specific Actor)
4. Confronto → Future: Council as a specialized Thinker
5. Sogno → `LTMStore.condense()` during sleep window
6. Curiosita' → Future: organ-specific Sensor that reads nexus:gaps
7. Misura → `SelfModel` metrics + `HomeostaticState`
8. Simbiosi → Maturation phases (embrione → anziano)

## 10. Async/Sync Boundary (Critical)

**The trap** (flagged by all 3 LLMs): CELL is fully async. MG's Sprint 5 uses subprocess LLM calls which are blocking.

**Solution:** All protocols are `async def`. The sync consumer wraps blocking calls:

```python
class CLIReasoner:
    async def think(self, readings, state, memory_context) -> Proposal:
        # asyncio.create_subprocess_exec, not subprocess.run
        proc = await asyncio.create_subprocess_exec(
            "claude", "--print", prompt,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return parse_proposal(stdout.decode())
```

SQLite is inherently sync. `SqliteMemoryStack` uses `asyncio.to_thread()` for I/O:

```python
class SqliteEpisodic:
    async def store(self, episode: Episode) -> int:
        return await asyncio.to_thread(self._store_sync, episode)
    
    def _store_sync(self, episode: Episode) -> int:
        # actual sqlite3 operations
        ...
```

This keeps the event loop clean while allowing stdlib-only operation.

## 11. Testing Strategy

```
packages/cell-core/tests/
├── test_types.py              # Dataclass creation, validation
├── test_pulse.py              # PulseLoop lifecycle ordering, error handling
├── test_memory_sqlite.py      # All 3 SQLite stores: CRUD, TTL, ACT-R, FTS5
├── test_memory_protocols.py   # Protocol compliance checks
├── test_lifecycle.py          # Phase transitions, confidence gates
├── test_safety.py             # Kill switch, DNA validation
├── test_homeostasis.py        # Stress/energy/arousal, circadian, trend detection
├── test_reasoner.py           # Tier escalation, timeout handling
├── test_identity.py           # SelfModel persistence, atomic write
└── conftest.py                # Fixtures: fake sensors, thinkers, actors
```

Target: 100% coverage on core logic. Fakes for protocols in `conftest.py`:

```python
class FakeSensor:
    name = "fake"
    async def read(self, **ctx):
        return SensorReading(sensor_name="fake", status="green")

class FakeThinker:
    async def think(self, readings, state, memory_context):
        return Proposal(action="none", reason="fake", confidence=1.0, tier_used=-1)

class FakeActor:
    async def act(self, proposal):
        return "fake_outcome"
    def can_execute(self, action_name):
        return True
```

## 12. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Over-abstraction for 2 consumers | Flat structure, 10 files, no nested packages |
| Protocol version drift | `runtime_checkable`, type errors at import time |
| SQLite concurrency (multiple organs same DB) | Each organ gets its own DB file |
| Async/sync mixing blocks event loop | `asyncio.to_thread()` for all SQLite ops |
| CELL's 224 tests break during migration | Phase 3 is separate sprint, not blocking |
| Memory backend proliferation | Only 2 backends (sqlite, pg). Add more only when needed |

## 13. Success Criteria

1. `packages/cell-core/` exists with all 10 modules
2. `pytest packages/cell-core/tests/` passes with >95% coverage
3. Mata Garuda Sprint 5 imports cell-core and implements 4 protocols (2 sensors, 1 thinker, 1 actor)
4. CELL original continues working unchanged (Phase 3 migration is separate)
5. SYMBIOSIS.md updated with L0 Cellular layer
6. Zero new external dependencies
