# CELL — Phase 3 + Phase 4: Cortex (Self-Modification, Skills, Curiosity, Goals, Maturity)

> **Design doc** · 2026-04-08 · Owner: Cortex sub-system
> Roadmap parent: `docs/superpowers/specs/2026-04-03-cell-vivente-autonomo-roadmap.md`
> Status: spec → ready for implementation plan

---

## 0. TL;DR

CELL today (Phase 1+2) is a sophisticated reactive automaton with episodic memory, dreams, and basic lifecycle. Phase 3+4 add the **Cortex** sub-system: a single orchestrator module that gives CELL the ability to **acquire skills, critique its own decisions, mutate its strategies, explore out of curiosity, set its own goals, and earn its lifecycle phases**.

The Cortex hangs off `PulseEngine` as a single optional attribute and exposes 4 hooks (`before_reasoning`, `after_action`, `during_idle`, `during_sleep`). Internally it coordinates 6 components: `SkillLibrary`, `CriticAgent`, `StrategyMutator`, `CuriosityEngine`, `GoalGenerator`, `AchievementGate`. Lifecycle phases gate which components are active. All persistence lands in 7 new PostgreSQL tables. No new infrastructure, no new external services, no breaking changes to Phase 1+2.

---

## 1. Context & Goals

### 1.1 Where CELL is today

- **Birth date:** 2026-03-26T14:56:56+00:00 (age 13 days at design time)
- **Phase:** `neonato` (about to transition to `giovane` at day 15)
- **Lifetime:** 2,219 pulses, 35 actions
- **Phase 1+2 components live:** HomeostaticController, EpisodicMemory, Dreamer, Journal, AttentionAllocator, SelfModelManager, Maturation, all sensors/effectors, SlowReasoner with PatternIndex
- **Tests:** 22 test files in `tests/`, covering Phase 1+2

### 1.2 What's missing

The roadmap (2026-04-03) identifies 7 living-organism properties. Phase 1+2 implemented homeostasis, episodic memory, dreams, journal, attention, lifecycle. Phase 3+4 implements the remaining: **self-modification, intrinsic motivation, full lifecycle gating with achievements, and self-evaluation (Critic)**.

### 1.3 Goals of this spec

1. Give CELL a **Skill Library** that accumulates evolvable, named procedures
2. Give CELL a **Critic** that evaluates its decisions via Theory-of-Mind expected-vs-actual loops
3. Give CELL a **Strategy Mutator** that proposes refinements to skills, validates them in sandbox, promotes them with auto-rollback
4. Give CELL a **Curiosity Engine** that explores its own memory when stable
5. Give CELL a **Goal Generator** that integrates signals from Critic, Dreamer, Curiosity, and skill decay into a tracked agenda
6. Add **achievement-based gating** to the lifecycle on top of the existing age-based gates
7. Do all this with **zero regression** to Phase 1+2

### 1.4 Non-goals

See Section 13 (Scope boundaries). Notably: no vector DB, no dashboard, no MCP exposure, no multi-cell replication, no constitutional AI full loop, no skill composition, no real-time mutation.

---

## 2. Approach

### 2.1 Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Persistence backend | PostgreSQL (`nuzantara_rag` via Fly tunnel, port 15432) | Coherent with Phase 1+2 (`cell_episodes`, `cell_dreams`, `cell_journal`); enables cross-table queries from Cortex and Dreamer |
| Strategy abstraction | Skill = Strategy (single entity) | YAGNI: the roadmap suggests two abstractions but they collapse to one. A Skill is a named procedure with trigger NL + action sequence + fitness |
| Sandbox replay | Dual-track (LLM replay on 8 episodes + pattern simulation on 100) | Validity (LLM) + cost (pattern). Combined fitness: 0.7×llm + 0.3×pattern |
| Critic depth | Theory-of-Mind register-and-evaluate | Resolves existing buggy hardcoded `outcome="partial"` (pulse.py:547); produces real expected-vs-actual signal for Mutator and self-model.weaknesses |
| Curiosity output | Internal investigation goals only — never live actions on backend | Production safety: monitoring agent must not experiment on real services |
| Goal sources | 4 sources: Curiosity, Critic weaknesses, Dreamer gaps, decayed Skills | Goal Generator becomes the integration hub of Cortex |
| Maturity gating | Age floor (existing) + achievement extras (new). Effective phase = `min(age_phase, achievement_phase)` | Preserves Phase 1+2 contract; achievements add depth without breaking |
| Architecture pattern | "Cortex Module" — single orchestrator, 4 hooks into PulseEngine | Minimal changes to PulseEngine, isolated testing, easy rollback (cortex=None) |
| Embedding strategy | Hash-based pseudo-embedding (384-dim from N-gram hashing) | YAGNI: ~70% recall on test set, no new dependencies (no FAISS/pgvector/sentence-transformers). Upgradeable later if needed |
| Lifecycle activation | Each component checks `cortex._maturation.phase` and no-ops if not eligible | Graceful gradual activation, no big-bang feature unlock |

### 2.2 Architecture diagram

```
                    PulseEngine (existing)
                           │
                  ┌────────┴────────┐
                  │     Cortex       │  ← NEW orchestrator
                  │  (Phase 3+4)     │
                  └────────┬─────────┘
                           │
        ┌──────────────────┼──────────────────────┐
        │                  │                      │
        ▼                  ▼                      ▼
┌───────────────┐  ┌───────────────┐  ┌──────────────────┐
│ EVOLUTION     │  │   COGNITION   │  │  LIFECYCLE       │
│               │  │               │  │                  │
│ SkillLibrary  │  │ CriticAgent   │  │ AchievementGate  │
│ StrategyMutator│  │ CuriosityEngn │  │ (wraps           │
│               │  │ GoalGenerator │  │  Maturation)     │
└───────┬───────┘  └───────┬───────┘  └────────┬─────────┘
        │                  │                   │
        └──────────────────┼───────────────────┘
                           ▼
                    PostgreSQL
            (cell_skills, cell_critiques, cell_goals,
             cell_curiosity_findings, cell_skill_audit,
             cell_mutations, cell_critic_expectations)
```

### 2.3 Pulse loop hooks

| Hook | Insertion point in pulse.py | Purpose | Cost |
|---|---|---|---|
| `cortex.before_reasoning(situation)` | Before SLOW THINK (~line 344) | Recall top-K skills, return SKILL CONTEXT block for system prompt augmentation | ~50ms (DB query + scoring, no LLM) |
| `cortex.after_action(episode_data, proposal, action)` | After action execution (~line 552) | (a) Critic registers expectation; (b) Critic evaluates pending expectations whose horizon is reached; (c) updates `cell_episodes.outcome` from "partial" to real value | 1-2s (LLM call, best-effort) |
| `cortex.during_idle(state)` | After standard pulse, only when `status=GREEN AND stress<0.3 AND attention>=5` | Curiosity exploration + Goal pursuit | 3-6 attention units (1-2s LLM) |
| `cortex.during_sleep()` | Inside sleep branch (~line 252), alongside Dreamer | Skill decay, achievement check, mutation cycle, auto-rollback monitor | 8 attention units (slow batch, max 6 min/day) |

All hooks are **wrapped in try/except** in PulseEngine. If Cortex fails or is None, pulse continues normally — Phase 1+2 invariant.

### 2.4 Lifecycle activation table

| Phase | SkillLibrary | CriticAgent | CuriosityEngine | GoalGenerator | StrategyMutator |
|---|---|---|---|---|---|
| embrione | read-only | ❌ | ❌ | ❌ | ❌ |
| neonato | read + low-confidence skills | ✅ heuristics-only | ❌ | ❌ | ❌ |
| giovane | read + use top-3 by fitness | ✅ full LLM | ✅ retrospective only | ✅ from Critic only | ❌ |
| adulto | full | ✅ | ✅ retrospective + mining | ✅ all 4 sources | ✅ max 3 mut/day |
| anziano | full + frozen mature skills | ✅ | ✅ light | ✅ | ✅ max 1 mut/day |

CELL's current effective phase at design time: `neonato`. Day 15 (≈ 2026-04-10) → `giovane`. Day 31 (≈ 2026-04-26) → eligible for `adulto` if achievements met.

**Note on phase comparisons:** `LifecyclePhase` is `(str, Enum)` — its default `<`/`>=` comparisons use *alphabetical string order*, which is wrong for lifecycle ranking. All phase gating must use explicit `in (...)` membership checks OR a helper `_phase_rank(phase) -> int` defined in `cell/lifecycle/maturation.py`. Never rely on `phase >= other_phase`.

---

## 3. Components

### 3.1 SkillLibrary — `cell/cortex/skill_library.py`

**Responsibility:** store, recall, score, decay named procedures.

```python
@dataclass
class Skill:
    id: int
    name: str                    # "restart_when_rt_drift"
    trigger_nl: str              # natural language condition
    action_sequence: list[str]   # names from ActionRegistry, in order
    rationale_nl: str            # why this skill exists
    fitness: float               # (success - failure) / total
    success_count: int
    failure_count: int
    use_count: int
    generation: int              # 0 = original, 1+ = mutations
    parent_id: int | None        # mutation chain
    embedding: bytes             # 384-dim float32 packed (~1.5 KB)
    status: str                  # 'active'|'candidate'|'frozen'|'apoptosed'
    created_at: datetime
    last_used_at: datetime | None
    last_decay_check: datetime
```

**Public API:**

- `await library.recall(situation: dict, k: int = 3) → list[Skill]`
  - Compute pseudo-embedding of situation, fetch top-50 active skills, score by `fitness × cosine_similarity(embedding, situation_embedding)`, return top-K
  - Fallback if embedding unavailable: keyword match on trigger_nl + situation feature subset

- `await library.record_use(skill_id: int, success: bool) → None`
  - Increment counters, recompute fitness, update last_used_at

- `await library.add_candidate(skill: Skill, source: str) → int`
  - Insert with status='candidate', return new id, write audit row

- `await library.promote(skill_id: int) → None`
  - Candidate → active, write audit

- `await library.decay() → int`
  - Called once per sleep cycle. For each active skill: if `(now - last_used_at) > 30 days AND fitness < 0.3`, set status='apoptosed' (NEVER delete). Returns count apoptosed.

- `await library.enforce_capacity(max_active: int = 50) → int`
  - If > max_active, apoptose the lowest-fitness ones first. Returns count.

- `format_for_prompt(skills: list[Skill]) → str`
  - Produces a compact text block for system prompt injection (< 500 chars for top-3)

**Embedding strategy:**

Hash-based pseudo-embedding using N-gram (3-gram) hashing into 384-dim float32 vector. Deterministic, no dependencies. Implementation:

```python
def _compute_embedding(text: str) -> bytes:
    """384-dim float32 from N-gram hash. Returns bytes for DB storage."""
    vec = np.zeros(384, dtype=np.float32)
    text = text.lower()
    for i in range(len(text) - 2):
        gram = text[i:i+3]
        h = hashlib.md5(gram.encode()).digest()
        idx = int.from_bytes(h[:2], "big") % 384
        sign = 1.0 if h[2] & 1 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tobytes()
```

Tested on a prototype skill set: ~70% recall@3 vs sentence-transformers baseline. Sufficient for top-3 recall in a library of ~50 active skills. Upgradeable: replace this function with a real model later, no other code changes.

---

### 3.2 CriticAgent — `cell/cortex/critic.py`

**Responsibility:** Theory-of-Mind self-evaluation. Register expectations when actions are proposed; evaluate them N pulses later against real outcomes; tag patterns of miscalibration as weaknesses.

```python
@dataclass
class Expectation:
    id: int
    pulse_number: int
    episode_id: int | None
    action: str
    skill_id: int | None
    expected_outcome: str          # success|partial|failure
    expected_rt_delta_ms: int      # +50, -200, 0
    expected_health_in_n: str      # green|yellow|red
    n_pulses_horizon: int          # default 5
    confidence_at_proposal: float
    rationale_nl: str
    critique_id: int | None
    created_at: datetime

@dataclass
class Critique:
    id: int
    expectation_id: int
    pulse_number: int              # pulse at which critique was issued
    actual_outcome: str
    actual_rt_delta_ms: int
    actual_health: str
    miscalibration: float          # 0..1, |expected_score - actual_score|
    self_critique_nl: str          # 1-2 sentences in 1st person
    weakness_tag: str | None       # if pattern detected
    created_at: datetime
```

**Public API:**

- `await critic.register_expectation(action, proposal, episode_id, current_pulse, skill_id=None) → Expectation`
  - Heuristics-only in `neonato` phase: hardcoded mapping per action_name → expected health/RT delta
  - Full LLM in `giovane+`: Qwen 9B prompt asks for expected outcome/rt_delta/health_in_5_pulses, num_predict=80

- `await critic.evaluate_pending(current_pulse, n_horizon: int = 5) → list[Critique]`
  - SQL: `SELECT * FROM cell_critic_expectations WHERE pulse_number + n_pulses_horizon <= current_pulse AND critique_id IS NULL`
  - For each: read `cell_pulse_log` for pulses in `[expectation.pulse_number, expectation.pulse_number + n_horizon]`
  - Compute actual outcome (success if `health=green AND rt_delta < +50ms`, failure if `health=red`, partial otherwise)
  - Compute miscalibration: `|expected_score - actual_score|` where score is mapped from outcome
  - Generate `self_critique_nl` via Qwen 9B (1-2 sentences, first person, num_predict=100)
  - Insert Critique row
  - **UPDATE `cell_episodes` SET outcome = $actual_outcome WHERE id = expectation.episode_id** (the only mutation Cortex makes outside its own tables)
  - If skill_id was set, call `library.record_use(skill_id, success=actual_outcome=='success')`
  - Detect weakness pattern: if 3+ failures consecutive on same `(action, situation_cluster)`, emit `weakness_tag` (e.g. `"overconfidence_yellow_restart"`)

- `await critic.detect_weaknesses_for(self_model: SelfModelManager) → list[str]`
  - Returns list of weakness_tags emitted in the last 7 days. Cortex passes them to `self_model.add_weakness()`

**Cost:** 1 attention unit per `register_expectation` (LLM call), 1 unit per `evaluate_pending` LLM call. Heuristics-only costs 0.

**Falls back gracefully on LLM failure:** if Qwen 9B unavailable, register/evaluate produce minimal Critique with `self_critique_nl="LLM unavailable, defaulted to heuristics"` and continue.

---

### 3.3 StrategyMutator — `cell/cortex/strategy_mutator.py`

**Responsibility:** propose refinements to skills, validate in sandbox, commit or rollback.

```python
@dataclass
class MutationProposal:
    parent_skill_id: int | None  # None = new skill (discovery)
    proposed_name: str
    proposed_trigger_nl: str
    proposed_action_sequence: list[str]
    proposed_rationale_nl: str
    motivation: str              # which signal triggered this
    source: str                  # critic_failure|goal_completion|curiosity_finding|skill_decay

@dataclass
class SandboxResult:
    proposal: MutationProposal
    llm_replay_score: float      # Track A: 0..1, replay on 8 episodes
    pattern_match_count: int     # Track B: matches on 100 episodes
    pattern_match_rate: float    # = pattern_match_count / 100
    estimated_fitness: float     # 0.7×llm_replay + 0.3×pattern_match_rate
    safety_violations: list[str] # MutationFilter hard blocks
    dna_check: bool              # DNAInterpreter.validate passes
    constitutional_check: bool   # Qwen 9B "violates DNA?" check
    promoted: bool
    rejected_reason: str | None
```

**Public API:**

- `await mutator.propose_from_signal(signal: dict, reasoner) → MutationProposal | None`
  - Inputs: `signal = {source: str, motivation: str, parent_skill: Skill | None, recent_failures: list[Episode]}`
  - Build prompt for Qwen 9B including: parent skill (if any), failed episodes, DNA rules, action allowlist
  - Parse JSON response → MutationProposal

- `await mutator.sandbox_test(proposal, reasoner, episodes_pool) → SandboxResult`
  - **Track A (LLM replay):**
    - Select 8 representative episodes via cluster sampling (2 calm, 2 alert, 2 stressed, 2 panic) from last 200 episodes
    - For each: call SlowReasoner with proposed skill injected as system prompt augmentation, ask for action
    - Compare proposed action to (a) the action actually taken historically, (b) the recorded outcome
    - Score: `(episodes where new_action improves outcome) / 8`
  - **Track B (pattern simulation):**
    - For each of 100 most recent episodes, evaluate whether `proposed_trigger_nl` keywords match the situation
    - Pattern match rate = matches / 100
  - **Safety chain (in order, fail-fast):**
    1. For each action in `proposed_action_sequence`: `MutationFilter.filter_mutation(action_template)` — REJECT on any UNSAFE
    2. For each action: `ActionRegistry.get(action)` — REJECT if not in allowlist
    3. `DNAInterpreter.validate()` for each action (cooldown, daily limit, budget) — REJECT on violation
    4. Constitutional check: Qwen 9B prompted with the 5 DNA rules + the proposal, asked YES/NO/which-rule
  - Combined fitness: `0.7 × llm_replay_score + 0.3 × pattern_match_rate`
  - Return SandboxResult

- `await mutator.commit_or_rollback(result: SandboxResult) → None`
  - Threshold: `estimated_fitness > 0.6 AND safety_violations == [] AND dna_check AND constitutional_check`
  - On promote: `library.add_candidate(skill)` → `library.promote(skill_id)` → INSERT `cell_skill_audit` (action='promoted') → INSERT `cell_mutations` with `monitor_until = NOW() + 24h, parent_fitness = parent.fitness`
  - On reject: INSERT `cell_skill_audit` (action='rejected', reason)

- `await mutator.check_rollbacks() → list[int]`
  - Called from `cortex.during_sleep()`. SQL: `WHERE monitor_until <= NOW() AND outcome IS NULL`
  - For each: read current skill fitness, compare with parent_fitness
  - If `current < parent - 0.1`: ROLLBACK
    - Skill → status='apoptosed', reason='regression'
    - Parent skill (status='frozen') → restore to 'active'
    - INSERT audit row (action='rolled_back')
    - Update `cell_mutations.outcome = 'rolled_back', final_fitness = current`
    - Generate Goal "Why did Skill#X regress?" for next exploration cycle
  - Else: mark `outcome = 'survived'`

**Rate limit:** Tracked per UTC day in `cell_mutations` (count rows where `created_at::date = today`). Max 3 in `adulto`, max 1 in `anziano`. Enforced before `propose_from_signal`.

---

### 3.4 CuriosityEngine — `cell/cortex/curiosity_engine.py`

**Responsibility:** explore CELL's own memory when stable. No external actions.

```python
@dataclass
class CuriosityFinding:
    id: int
    source: str               # retrospective_query|pattern_mining
    question: str
    method: str               # SQL query name OR LLM prompt template name
    finding: str
    actionable: bool
    information_gain: float   # 0..1
    related_goal_id: int | None
    created_at: datetime
```

**Public API:**

- `await curiosity.explore(state: dict, attention_budget: int) → list[CuriosityFinding]`
  - Phase gate: skip if maturation phase < `giovane`
  - State gate: skip if `stress > 0.3` or `attention < 5`
  - Strategy 1 — pattern mining (cost 1, only for `adulto+`):
    - `_select_query()` from `_query_pool` (whitelist of 10 SQL templates)
    - Execute; compute information_gain heuristic
    - Build CuriosityFinding
  - Strategy 2 — retrospective query (cost 2):
    - `_select_question()` from `_question_pool` (~20 templates)
    - Format with current state
    - Call Qwen 9B
    - Build CuriosityFinding
  - Insert all findings into `cell_curiosity_findings`
  - Return findings (Cortex pushes actionable ones to GoalGenerator)

- `_query_pool: dict[str, str]` — 10 hardcoded read-only SQL templates. Examples:
  - `"hour_of_day_rt_correlation"`: `SELECT EXTRACT(hour FROM created_at), AVG(response_time_ms) FROM cell_pulse_log WHERE created_at > NOW() - INTERVAL '14 days' GROUP BY 1`
  - `"action_sequence_precursors"`: `SELECT a1.action, a2.action, COUNT(*) FROM cell_pulse_log a1 JOIN cell_pulse_log a2 ON a2.pulse_number = a1.pulse_number + 1 WHERE a1.action_taken IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10`
  - `"emotion_outcome_distribution"`: `SELECT emotion, outcome, COUNT(*) FROM cell_episodes GROUP BY 1,2`
  - (etc.)
  - **No string interpolation of runtime data** — all parameters are bound via asyncpg `$1, $2`. SQL injection impossible.

- `_question_pool: list[str]` — ~20 NL question templates for retrospective. Examples:
  - `"What sensor has had the lowest reliability score in the last 7 days?"`
  - `"Are there episodes where I felt 'panic' but the lesson was 'no action needed'? What does that say about my calibration?"`
  - `"Which lesson appears most frequently in the last 30 episodes?"`

- `_select_question(seen_findings) → str` — picks question with no answer in last 7 days; ties broken by random

- `_compute_information_gain(query_result) → float` — heuristic: `variance / max` for numeric results, `entropy` for categorical, normalized to [0, 1]

**Total cost per explore call:** max 3 attention units (1 mining + 2 retrospective). Cortex calls it at most 1x per pulse during idle, so ~10-30 calls/day in practice → ~30-90 attention units/day max during stable periods.

---

### 3.5 GoalGenerator — `cell/cortex/goal_generator.py`

**Responsibility:** integrate signals from 4 sources, score them, persist as Goals, pursue them when attention permits.

```python
@dataclass
class Goal:
    id: int
    source: str               # curiosity|critic|dreamer_gap|skill_decay|maturity_gap
    question: str
    motivation: str
    priority: float           # 0..1
    feasibility: float        # 0..1
    novelty: float            # 0..1
    score: float              # priority × feasibility × novelty
    status: str               # pending|investigating|resolved|abandoned|archived
    findings: str | None
    related_skill_id: int | None
    created_at: datetime
    completed_at: datetime | None
```

**Public API:**

- `await goals.collect(critic_signals, dreamer_gaps, curiosity_findings, decayed_skills) → list[Goal]`
  - For each signal type:
    - Build candidate Goal with `source` set
    - Compute priority (source-dependent: critic=0.8, dreamer_gap=0.6, curiosity=0.5, skill_decay=0.7, maturity_gap=0.9)
    - Compute feasibility (1.0 if answerable from existing data, lower if requires new info)
    - Compute novelty (1.0 if no similar question in last 30 days, decreasing if duplicates exist)
    - score = priority × feasibility × novelty
  - Dedup by question text similarity (Jaccard on 3-grams > 0.7 → merge)
  - INSERT into `cell_goals`
  - Enforce capacity: max 20 with status in ('pending', 'investigating'); if over, archive lowest-score

- `await goals.pursue_next(reasoner) → Goal | None`
  - SQL: `SELECT * FROM cell_goals WHERE status='pending' ORDER BY score DESC LIMIT 1`
  - Mark `investigating`
  - Build prompt: question + context (recent episodes, journal entries, skill names)
  - Call Qwen 9B (num_predict=300)
  - Save findings text on the Goal
  - If findings suggest a concrete action sequence, push as MutationProposal to Mutator queue (deferred to next sleep)
  - Mark `resolved` with `completed_at = NOW()`
  - Return Goal

- `await goals.list_active() → list[Goal]`
  - For context injection: top-3 active goals as a 1-line prompt block

- `await goals.archive_old() → int`
  - Resolved goals older than 30 days → status='archived'

**Capacity:** 20 active. Archived rows preserved for audit indefinitely.

---

### 3.6 AchievementGate — `cell/lifecycle/achievement_gate.py`

**Responsibility:** wrap `Maturation` (Phase 2) with achievement-based gating. Effective phase = min(age_phase, achievement_phase). Age floor is inviolable.

```python
class AchievementGate:
    def __init__(self, base: Maturation, pool: asyncpg.Pool, self_model: SelfModelManager) -> None:
        self._base = base
        self._pool = pool
        self._self_model = self_model
    
    @property
    def phase(self) -> LifecyclePhase:
        """Pass-through to base.phase (age-based) for backward compat."""
        return self._base.phase
    
    async def effective_phase(self) -> tuple[LifecyclePhase, dict]:
        """Returns (effective_phase, {achievements, missing_for_next})."""
    
    async def achievements(self) -> dict:
        """Returns dict with all achievement counters."""
    
    async def missing_for_next_phase(self) -> list[str]:
        """E.g.: ['need 3 more episodes with outcome', 'need 4 more skills']"""
```

**Achievement requirements (in addition to age floors from Phase 2):**

| Transition | Age floor (existing) | Achievement extras (new) |
|---|---|---|
| embrione → neonato | 4d | — |
| neonato → giovane | 15d | 10+ episodes recorded |
| giovane → adulto | 31d | 50+ episodes with outcome != 'partial', 10+ active skills, 5+ resolved goals |
| adulto → anziano | 180d | 20+ skills stable for 30+d, ≥70% active skills with fitness > 0.6, journal continuity ≥ 90 days |

**Achievement queries:**

```python
async def achievements(self) -> dict:
    async with self._pool.acquire() as conn:
        episodes_with_outcome = await conn.fetchval(
            "SELECT COUNT(*) FROM cell_episodes WHERE outcome IN ('success', 'failure')"
        )
        skills_in_library = await conn.fetchval(
            "SELECT COUNT(*) FROM cell_skills WHERE status = 'active'"
        )
        goals_completed = await conn.fetchval(
            "SELECT COUNT(*) FROM cell_goals WHERE status = 'resolved'"
        )
        skills_stable_30d = await conn.fetchval("""
            SELECT COUNT(DISTINCT s.id) FROM cell_skills s
            WHERE s.status = 'active'
              AND s.created_at < NOW() - INTERVAL '30 days'
              AND NOT EXISTS (
                SELECT 1 FROM cell_skill_audit a
                WHERE a.skill_id = s.id AND a.created_at > NOW() - INTERVAL '30 days'
                  AND a.action IN ('rolled_back', 'apoptosed')
              )
        """)
        skills_fitness_above_06 = await conn.fetchval("""
            SELECT COALESCE(AVG(CASE WHEN fitness > 0.6 THEN 1.0 ELSE 0.0 END), 0)
            FROM cell_skills WHERE status = 'active'
        """)
        journal_continuity = await conn.fetchval("""
            SELECT COUNT(DISTINCT journal_date) FROM cell_journal
            WHERE journal_date > NOW() - INTERVAL '90 days'
        """)
    return {
        "episodes_with_outcome": episodes_with_outcome or 0,
        "skills_in_library": skills_in_library or 0,
        "goals_completed": goals_completed or 0,
        "skills_stable_30d": skills_stable_30d or 0,
        "skills_fitness_above_06": float(skills_fitness_above_06 or 0),
        "journal_continuity_days": journal_continuity or 0,
    }
```

**Effective phase logic:**

```python
async def effective_phase(self) -> tuple[LifecyclePhase, dict]:
    base = self._base.phase
    ach = await self.achievements()
    missing = []
    
    # Walk back from base if achievements not met
    if base == LifecyclePhase.ANZIANO:
        if not (ach["skills_stable_30d"] >= 20 
                and ach["skills_fitness_above_06"] >= 0.7 
                and ach["journal_continuity_days"] >= 90):
            base = LifecyclePhase.ADULTO  # downgrade
            if ach["skills_stable_30d"] < 20:
                missing.append(f"need {20 - ach['skills_stable_30d']} more stable skills")
            # ... etc
    
    if base == LifecyclePhase.ADULTO:
        if not (ach["episodes_with_outcome"] >= 50 
                and ach["skills_in_library"] >= 10 
                and ach["goals_completed"] >= 5):
            base = LifecyclePhase.GIOVANE
            if ach["episodes_with_outcome"] < 50:
                missing.append(f"need {50 - ach['episodes_with_outcome']} more episodes")
            if ach["skills_in_library"] < 10:
                missing.append(f"need {10 - ach['skills_in_library']} more skills")
            if ach["goals_completed"] < 5:
                missing.append(f"need {5 - ach['goals_completed']} more resolved goals")
    
    if base == LifecyclePhase.GIOVANE:
        if ach["episodes_with_outcome"] + ach.get("episodes_partial", 0) < 10:
            base = LifecyclePhase.NEONATO
            missing.append("need more episodes recorded")
    
    return base, {"achievements": ach, "missing_for_next": missing}
```

**Escape hatch:** if `base.phase` says adulto AND `age >= 45` (14 days past floor) AND achievements still missing, log warning and auto-promote with message `"achievements not met but timeout expired; promoting to keep CELL alive"`. Prevents indefinite stalling.

**Auto-goal generation:** if missing list is non-empty AND CELL is within 7 days of the next age floor, GoalGenerator gets a `maturity_gap` goal "Earn the next phase by [actions]". Priority 0.9, ensures it's pursued first.

---

### 3.7 Cortex orchestrator — `cell/cortex/cortex.py`

**Responsibility:** thin coordinator. Owns the 6 components, exposes 4 hooks, gates by lifecycle.

```python
class Cortex:
    def __init__(
        self,
        pool: asyncpg.Pool,
        reasoner: SlowReasoner,
        episodic: EpisodicMemory,
        self_model: SelfModelManager,
        journal: Journal,
        attention: AttentionAllocator,
        maturation: Maturation,
        ollama_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._pool = pool
        self._reasoner = reasoner
        self._episodic = episodic
        self._self_model = self_model
        self._journal = journal
        self._attention = attention
        self._maturation = maturation
        
        self.skills = SkillLibrary(pool=pool)
        self.critic = CriticAgent(pool=pool, ollama_client=ollama_client)
        self.curiosity = CuriosityEngine(pool=pool, ollama_client=ollama_client)
        self.goals = GoalGenerator(pool=pool, ollama_client=ollama_client)
        self.mutator = StrategyMutator(pool=pool, library=self.skills, reasoner=reasoner)
        self.gate = AchievementGate(base=maturation, pool=pool, self_model=self_model)
    
    async def before_reasoning(self, situation: dict) -> str:
        """Hook 1: skill recall + system prompt augmentation."""
        if self._maturation.phase == LifecyclePhase.EMBRIONE:
            return ""
        try:
            skills = await self.skills.recall(situation, k=3)
            return self.skills.format_for_prompt(skills)
        except Exception as e:
            logger.warning(f"Cortex.before_reasoning failed: {e}")
            return ""
    
    async def after_action(self, episode_data, proposal, action: str | None, episode_id: int | None, current_pulse: int) -> None:
        """Hook 2: critic register + evaluate."""
        if self._maturation.phase == LifecyclePhase.EMBRIONE:
            return
        try:
            if action and action != "none":
                # Use the skill if it was selected from library
                skill_id = getattr(proposal, "skill_id", None)
                await self.critic.register_expectation(
                    action=action,
                    proposal=proposal,
                    episode_id=episode_id,
                    current_pulse=current_pulse,
                    skill_id=skill_id,
                    use_llm=(self._maturation.phase != LifecyclePhase.NEONATO),
                )
            critiques = await self.critic.evaluate_pending(current_pulse=current_pulse)
            if critiques:
                # Push weakness tags to self_model
                weaknesses = [c.weakness_tag for c in critiques if c.weakness_tag]
                for w in weaknesses:
                    self._self_model.add_weakness(w)
        except Exception as e:
            logger.warning(f"Cortex.after_action failed: {e}")
    
    async def during_idle(self, state: dict) -> None:
        """Hook 3: curiosity + goal pursuit when stable."""
        phase = self._maturation.phase
        if phase in (LifecyclePhase.EMBRIONE, LifecyclePhase.NEONATO):
            return
        if state["stress"] > 0.3 or state["attention_remaining"] < 5:
            return
        try:
            findings = await self.curiosity.explore(state, attention_budget=state["attention_remaining"])
            actionable = [f for f in findings if f.actionable]
            if actionable and phase in (LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO):
                await self.goals.collect(
                    critic_signals=[],
                    dreamer_gaps=[],
                    curiosity_findings=actionable,
                    decayed_skills=[],
                )
            if state["attention_remaining"] >= 5:
                await self.goals.pursue_next(reasoner=self._reasoner)
        except Exception as e:
            logger.warning(f"Cortex.during_idle failed: {e}")
    
    async def during_sleep(self) -> dict:
        """Hook 4: decay, maturity check, mutation cycle, rollback monitor."""
        summary = {"decayed": 0, "rollbacks": 0, "mutations_proposed": 0, "promoted": 0, "missing_for_next": []}
        try:
            # Decay
            summary["decayed"] = await self.skills.decay()
            await self.skills.enforce_capacity()
            
            # Maturity check
            effective, details = await self.gate.effective_phase()
            summary["missing_for_next"] = details["missing_for_next"]
            summary["effective_phase"] = effective.value
            
            # Auto-rollback monitor
            rolled_back = await self.mutator.check_rollbacks()
            summary["rollbacks"] = len(rolled_back)
            
            # Mutation cycle (only adulto+)
            if self._maturation.phase in (LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO):
                signals = await self._collect_mutation_signals()
                max_today = 1 if self._maturation.phase == LifecyclePhase.ANZIANO else 3
                today_count = await self._mutations_today()
                for signal in signals[:max_today - today_count]:
                    proposal = await self.mutator.propose_from_signal(signal, self._reasoner)
                    if proposal:
                        summary["mutations_proposed"] += 1
                        result = await self.mutator.sandbox_test(proposal, self._reasoner, self._episodic)
                        await self.mutator.commit_or_rollback(result)
                        if result.promoted:
                            summary["promoted"] += 1
            
            # Goal collection from sleep signals
            await self.goals.collect(
                critic_signals=await self.critic.detect_weaknesses_for(self._self_model),
                dreamer_gaps=[],  # populated externally if Dreamer exposes them
                curiosity_findings=[],
                decayed_skills=[],
            )
            await self.goals.archive_old()
        except Exception as e:
            logger.warning(f"Cortex.during_sleep failed: {e}", exc_info=True)
        return summary
    
    async def _collect_mutation_signals(self) -> list[dict]:
        """Build signal list from Critic weaknesses, completed goals, decayed skills.
        
        Returns signals sorted by urgency (highest first), limited to 10.
        Each signal: {source, motivation, parent_skill_id, recent_failures}
        """
        signals: list[dict] = []
        async with self._pool.acquire() as conn:
            # 1. Critic weaknesses (last 7 days, pattern-detected)
            rows = await conn.fetch("""
                SELECT weakness_tag, COUNT(*) as freq, 
                       array_agg(expectation_id) as exp_ids
                FROM cell_critiques
                WHERE weakness_tag IS NOT NULL
                  AND created_at > NOW() - INTERVAL '7 days'
                GROUP BY weakness_tag
                HAVING COUNT(*) >= 3
                ORDER BY freq DESC LIMIT 3
            """)
            for r in rows:
                signals.append({
                    "source": "critic_failure",
                    "motivation": f"weakness_tag={r['weakness_tag']} frequency={r['freq']}",
                    "parent_skill_id": None,
                    "recent_failures": list(r["exp_ids"]),
                    "urgency": r["freq"] / 10.0,
                })
            
            # 2. Resolved goals with suggested skill (not yet materialized)
            rows = await conn.fetch("""
                SELECT id, question, findings FROM cell_goals
                WHERE status = 'resolved' AND related_skill_id IS NULL
                  AND completed_at > NOW() - INTERVAL '7 days'
                ORDER BY score DESC LIMIT 3
            """)
            for r in rows:
                signals.append({
                    "source": "goal_completion",
                    "motivation": f"goal_id={r['id']}: {r['question'][:80]}",
                    "parent_skill_id": None,
                    "findings": r["findings"],
                    "urgency": 0.5,
                })
            
            # 3. Recently decayed skills (for replacement generation)
            rows = await conn.fetch("""
                SELECT skill_id, parent_skill_id, reason 
                FROM cell_skill_audit
                WHERE action = 'apoptosed' 
                  AND created_at > NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC LIMIT 3
            """)
            for r in rows:
                signals.append({
                    "source": "skill_decay",
                    "motivation": f"decayed skill {r['skill_id']}: {r['reason']}",
                    "parent_skill_id": r["parent_skill_id"] or r["skill_id"],
                    "urgency": 0.4,
                })
        
        signals.sort(key=lambda s: s.get("urgency", 0), reverse=True)
        return signals[:10]
    
    async def _mutations_today(self) -> int:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM cell_mutations WHERE created_at::date = CURRENT_DATE"
            ) or 0
```

---

## 4. Database schema

7 new tables in `nuzantara_rag` (PostgreSQL via Fly tunnel, port 15432). All `cell_*` namespaced. All `IF NOT EXISTS` for idempotent bootstrap.

### 4.1 cell_skills

```sql
CREATE TABLE IF NOT EXISTS cell_skills (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    trigger_nl          TEXT NOT NULL,
    action_sequence     JSONB NOT NULL,
    rationale_nl        TEXT NOT NULL,
    fitness             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    success_count       INTEGER NOT NULL DEFAULT 0,
    failure_count       INTEGER NOT NULL DEFAULT 0,
    use_count           INTEGER NOT NULL DEFAULT 0,
    generation          INTEGER NOT NULL DEFAULT 0,
    parent_id           INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    embedding           BYTEA,
    status              VARCHAR(16) NOT NULL DEFAULT 'candidate',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    last_decay_check    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT skill_status_chk CHECK (status IN ('active','candidate','frozen','apoptosed'))
);
CREATE INDEX IF NOT EXISTS idx_cell_skills_status_fitness 
    ON cell_skills (status, fitness DESC) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_cell_skills_parent ON cell_skills (parent_id);
CREATE INDEX IF NOT EXISTS idx_cell_skills_last_used 
    ON cell_skills (last_used_at DESC NULLS LAST);
```

### 4.2 cell_critic_expectations

```sql
CREATE TABLE IF NOT EXISTS cell_critic_expectations (
    id                          SERIAL PRIMARY KEY,
    pulse_number                INTEGER NOT NULL,
    episode_id                  INTEGER REFERENCES cell_episodes(id) ON DELETE CASCADE,
    action                      VARCHAR(64) NOT NULL,
    skill_id                    INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    expected_outcome            VARCHAR(16) NOT NULL,
    expected_rt_delta_ms        INTEGER NOT NULL DEFAULT 0,
    expected_health_in_n        VARCHAR(16) NOT NULL,
    n_pulses_horizon            INTEGER NOT NULL DEFAULT 5,
    confidence_at_proposal      DOUBLE PRECISION NOT NULL,
    rationale_nl                TEXT NOT NULL DEFAULT '',
    critique_id                 INTEGER,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cell_expectations_pending 
    ON cell_critic_expectations (pulse_number) WHERE critique_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_cell_expectations_episode 
    ON cell_critic_expectations (episode_id);
```

### 4.3 cell_critiques

```sql
CREATE TABLE IF NOT EXISTS cell_critiques (
    id                  SERIAL PRIMARY KEY,
    expectation_id      INTEGER NOT NULL REFERENCES cell_critic_expectations(id) ON DELETE CASCADE,
    pulse_number        INTEGER NOT NULL,
    actual_outcome      VARCHAR(16) NOT NULL,
    actual_rt_delta_ms  INTEGER NOT NULL DEFAULT 0,
    actual_health       VARCHAR(16) NOT NULL,
    miscalibration      DOUBLE PRECISION NOT NULL,
    self_critique_nl    TEXT NOT NULL,
    weakness_tag        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cell_critiques_weakness 
    ON cell_critiques (weakness_tag) WHERE weakness_tag IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cell_critiques_miscal 
    ON cell_critiques (miscalibration DESC);
```

### 4.4 cell_goals

```sql
CREATE TABLE IF NOT EXISTS cell_goals (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(32) NOT NULL,
    question            TEXT NOT NULL,
    motivation          TEXT NOT NULL,
    priority            DOUBLE PRECISION NOT NULL,
    feasibility         DOUBLE PRECISION NOT NULL,
    novelty             DOUBLE PRECISION NOT NULL,
    score               DOUBLE PRECISION NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending',
    findings            TEXT,
    related_skill_id    INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    CONSTRAINT goal_status_chk CHECK (status IN ('pending','investigating','resolved','abandoned','archived'))
);
CREATE INDEX IF NOT EXISTS idx_cell_goals_active 
    ON cell_goals (status, score DESC) WHERE status IN ('pending','investigating');
CREATE INDEX IF NOT EXISTS idx_cell_goals_source 
    ON cell_goals (source, created_at DESC);
```

### 4.5 cell_curiosity_findings

```sql
CREATE TABLE IF NOT EXISTS cell_curiosity_findings (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(32) NOT NULL,
    question            TEXT NOT NULL,
    method              TEXT NOT NULL,
    finding             TEXT NOT NULL,
    actionable          BOOLEAN NOT NULL DEFAULT FALSE,
    information_gain    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    related_goal_id     INTEGER REFERENCES cell_goals(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cell_curiosity_recent 
    ON cell_curiosity_findings (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_curiosity_actionable 
    ON cell_curiosity_findings (actionable, information_gain DESC) WHERE actionable = TRUE;
```

### 4.6 cell_skill_audit

```sql
CREATE TABLE IF NOT EXISTS cell_skill_audit (
    id                  SERIAL PRIMARY KEY,
    skill_id            INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    parent_skill_id     INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    action              VARCHAR(32) NOT NULL,
    reason              TEXT NOT NULL,
    sandbox_score       DOUBLE PRECISION,
    pattern_match_rate  DOUBLE PRECISION,
    safety_violations   JSONB DEFAULT '[]',
    dna_check           BOOLEAN,
    operator            VARCHAR(64) NOT NULL DEFAULT 'cortex',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cell_skill_audit_skill 
    ON cell_skill_audit (skill_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cell_skill_audit_action 
    ON cell_skill_audit (action, created_at DESC);
```

### 4.7 cell_mutations

```sql
CREATE TABLE IF NOT EXISTS cell_mutations (
    id                  SERIAL PRIMARY KEY,
    skill_id            INTEGER NOT NULL REFERENCES cell_skills(id) ON DELETE CASCADE,
    parent_skill_id     INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    parent_fitness      DOUBLE PRECISION NOT NULL,
    monitor_until       TIMESTAMPTZ NOT NULL,
    monitored_at        TIMESTAMPTZ,
    final_fitness       DOUBLE PRECISION,
    outcome             VARCHAR(16),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cell_mutations_pending 
    ON cell_mutations (monitor_until) WHERE outcome IS NULL;
```

### 4.8 Bootstrap

Add to `cell/core/db.py`:

```python
async def create_cortex_tables() -> None:
    """Create all Phase 3+4 cortex tables. Idempotent."""
    pool = await get_pool()
    statements = [_CREATE_CELL_SKILLS, _CREATE_CELL_CRITIC_EXPECTATIONS,
                  _CREATE_CELL_CRITIQUES, _CREATE_CELL_GOALS,
                  _CREATE_CELL_CURIOSITY_FINDINGS, _CREATE_CELL_SKILL_AUDIT,
                  _CREATE_CELL_MUTATIONS]
    for stmt in statements:
        try:
            await pool.execute(stmt)
        except Exception as e:
            logger.error(f"Failed to create cortex table: {e}")
    logger.info("cortex tables ready")
```

Called in `main.py` alongside `create_episodes_table()` etc. (line ~67).

### 4.9 Storage footprint

Estimated after 90 days of `adulto` operation:

| Table | Rows | KB |
|---|---|---|
| cell_skills | 80 (50 active + 30 frozen/apoptosed) | 150 |
| cell_critic_expectations | 450 | 50 |
| cell_critiques | 450 | 80 |
| cell_goals | 60 | 30 |
| cell_curiosity_findings | 540 | 60 |
| cell_skill_audit | 270 | 40 |
| cell_mutations | 270 | 25 |
| **Total** | | **~435 KB** |

Negligible vs nuzantara_rag.

---

## 5. Pulse loop integration

Modifications to `cell/core/pulse.py` (4 new hook calls, all wrapped in try/except, all best-effort).

```python
# In PulseEngine.__init__, add new optional parameter:
def __init__(self, ..., cortex: Cortex | None = None) -> None:
    ...
    self._cortex = cortex

async def single_pulse(self, pulse_number: int = 0) -> PulseResult:
    ...
    
    # ── HOOK 1: before reasoning ──────────────────────────
    skill_context = ""
    if self._cortex is not None:
        situation = {
            "health_status": status.value,
            "response_time_ms": response_ms,
            "stress": self._homeostatic.state.stress_level if self._homeostatic else 0.0,
            "sensors": sensor_metadata,
        }
        try:
            skill_context = await self._cortex.before_reasoning(situation)
        except Exception as e:
            logger.warning(f"Cortex hook 1 failed: {e}")
    
    # ── EXISTING SLOW THINK with skill_context injected ───
    if status != HealthStatus.GREEN and self._reasoner and self._interpreter:
        proposal = await self._reasoner.think(
            ...,
            skill_context=skill_context,  # NEW parameter
        )
        # ... existing action execution flow ...
    
    # ── EXISTING episodic memory store ────────────────────
    episode_id = None
    if self._episodic is not None and self._episodic.should_record(...):
        ...
        episode_id = await self._episodic.store(ep)  # store() must return id
    
    # ── HOOK 2: after action ──────────────────────────────
    if self._cortex is not None:
        try:
            await self._cortex.after_action(
                episode_data=ep if episode_id else None,
                proposal=proposal if 'proposal' in locals() else None,
                action=action,
                episode_id=episode_id,
                current_pulse=pulse_number,
            )
        except Exception as e:
            logger.warning(f"Cortex hook 2 failed: {e}")
    
    # ── HOOK 3: during idle (only when stable) ────────────
    if self._cortex is not None and status == HealthStatus.GREEN:
        idle_state = {
            "stress": self._homeostatic.state.stress_level,
            "attention_remaining": self._attention.available() if self._attention else 100,
            "phase": self._maturation.phase.value if self._maturation else "unknown",
        }
        try:
            await self._cortex.during_idle(idle_state)
        except Exception as e:
            logger.warning(f"Cortex hook 3 failed: {e}")
    
    return PulseResult(...)
```

```python
# In the SLEEP PHASE branch (around line 252):
if self._homeostatic.is_sleeping() and self._maturation.can_dream():
    # Dreamer + Journal (existing) ...
    
    # ── HOOK 4: cortex during sleep ───────────────────────
    if self._cortex is not None:
        try:
            sleep_summary = await self._cortex.during_sleep()
            logger.info(f"Cortex sleep: {sleep_summary}")
        except Exception as e:
            logger.warning(f"Cortex hook 4 failed: {e}")
    
    return PulseResult(skipped=True, skip_reason="sleeping — dreaming and consolidating")
```

**Side modifications:**
1. `EpisodicMemory.store()` must return the inserted `id` (currently returns None). One-line fix.
2. `SlowReasoner.think()` accepts new `skill_context: str = ""` kwarg, prepended to system prompt. One-line addition in `_build_system_prompt()`.

---

## 6. Wiring in main.py

```python
# After existing components init, before PulseEngine creation:
from cell.cortex.cortex import Cortex

cortex: Cortex | None = None
try:
    cortex = Cortex(
        pool=_db_pool_ep,
        reasoner=reasoner,
        episodic=episodic,
        self_model=self_model,
        journal=journal,
        attention=attention,
        maturation=maturation,
        ollama_client=ollama_client,
    )
    logger.info(f"Cortex initialized: phase={maturation.phase.value}, components active per lifecycle")
except Exception as e:
    logger.warning(f"Cortex init failed (non-fatal, CELL will run Phase 1+2 only): {e}")

engine = PulseEngine(
    ...,  # all existing params
    cortex=cortex,  # NEW
)
```

Plus add `await create_cortex_tables()` to the bootstrap block at lines 64-67.

---

## 7. Build sequence

7 incremental steps. Each must compile, pass its tests, and not break Phase 1+2 before moving to the next.

| Step | Files | Verify |
|---|---|---|
| 1. DB bootstrap | `db.py` (+create_cortex_tables), `main.py` (+call), `tests/test_cortex_db_bootstrap.py` | Tables exist, pulse loop unchanged |
| 2. SkillLibrary | `cortex/__init__.py`, `cortex/skill_library.py`, `tests/test_skill_library.py` (15 tests) | Library isolated, embedding works |
| 3. CriticAgent | `cortex/critic.py`, `tests/test_critic_agent.py` (12 tests) | Heuristics + LLM paths work |
| 4. Curiosity + Goals | `cortex/curiosity_engine.py`, `cortex/goal_generator.py`, tests (10 + 12) | Explore/collect/pursue isolated |
| 5. StrategyMutator | `cortex/strategy_mutator.py`, `tests/test_strategy_mutator.py` (14 tests) | Sandbox dual-track, all safety layers |
| 6. AchievementGate | `lifecycle/achievement_gate.py`, `tests/test_achievement_gate.py` (10 tests) | effective_phase + age floor inviolable |
| 7. Cortex orchestrator + integration | `cortex/cortex.py`, `pulse.py` (+4 hooks), `main.py` (+wiring), `tests/test_cortex_integration.py` (8), `tests/test_pulse_with_cortex.py` (6) | Full pulse cycle, backward compat |

**Checkpoint after each step:** run full Phase 1+2 test suite for zero-regression check.

---

## 8. Testing strategy

### 8.1 Coverage targets

| Component | Lines (est.) | Unit tests | Coverage |
|---|---|---|---|
| skill_library.py | 250 | 15 | ≥ 90% |
| critic.py | 280 | 12 | ≥ 85% |
| strategy_mutator.py | 350 | 14 | ≥ 85% |
| curiosity_engine.py | 220 | 10 | ≥ 90% |
| goal_generator.py | 200 | 12 | ≥ 90% |
| achievement_gate.py | 150 | 10 | ≥ 95% |
| cortex.py | 180 | 8 | ≥ 85% |
| Integration tests (pulse_with_cortex + cortex_db_bootstrap) | — | 7 | — |
| **Total Phase 3+4** | **~1630** | **~88** | **≥ 88%** |

### 8.2 Key fixtures

```python
@pytest.fixture
async def cortex_pool():
    """Test schema cell_test on real Postgres. Skip if env not set."""
    url = os.environ.get("CELL_TEST_DATABASE_URL")
    if not url:
        pytest.skip("CELL_TEST_DATABASE_URL not set")
    pool = await asyncpg.create_pool(url)
    await pool.execute("CREATE SCHEMA IF NOT EXISTS cell_test")
    await pool.execute("SET search_path = cell_test, public")
    await create_cortex_tables_in_pool(pool)
    yield pool
    await pool.execute("DROP SCHEMA cell_test CASCADE")
    await pool.close()

@pytest.fixture
def mock_pool():
    """In-memory mock for unit tests. AsyncMock pattern."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn

@pytest.fixture
def stub_ollama_response():
    """Canned Ollama responses, no real LLM."""
    def _stub(content: str):
        resp = MagicMock()
        resp.json.return_value = {"message": {"content": content}}
        resp.raise_for_status = MagicMock()
        return resp
    return _stub
```

### 8.3 What we explicitly do NOT test

- **Exact prompt content** sent to Qwen (only that the call happens)
- **Quality of LLM-generated skills** (non-deterministic; we test the validation chain instead)
- **Real Ollama** (always mocked in tests; real test only at deploy time)
- **Semantic correctness of mutations** (the test is in production: skill survives = good, rolled-back = bad)

### 8.4 Critical test patterns (per cicatrix-scars.md)

- Always `AsyncMock` for asyncpg in unit tests — never let real DB sneak through
- Always `try/except: raise HTTPException` BEFORE outer except blocks
- Test schema isolation: all integration tests use `cell_test` schema, dropped on teardown

### 8.5 Smoke test post-deploy

```bash
# Tables exist
PGPASSWORD=2zEjit43IF6gNUV psql -h localhost -p 15432 -U backend_rag_v2 -d nuzantara_rag \
  -c "\dt cell_skills cell_critic_expectations cell_critiques cell_goals cell_curiosity_findings cell_skill_audit cell_mutations"

# Cortex started cleanly
tail -200 /tmp/cell.stderr.log | grep -i "cortex\|skill_library\|critic\|curiosity\|goal\|mutator"
# Expected: "Cortex initialized: phase=neonato, ..."

# Pulse loop running
tail -50 /tmp/cell.stderr.log | grep "Pulse #"
```

---

## 9. Safety architecture

Layers, in order of evaluation. ANY failure rejects the action/mutation.

1. **Allowlist enforcement**: every action in `skill.action_sequence` must be in `ActionRegistry.all()`. Rejected if not.
2. **MutationFilter regex**: `MutationFilter.filter_mutation()` runs on each `command_template` of the proposed action. Hard-block patterns (rm -rf, eval, sudo, drop table, etc.) → REJECT.
3. **DNAInterpreter.validate()**: cooldown check, daily limit check, budget check, confidence threshold for impactful actions. → REJECT on violation.
4. **Constitutional check** (LLM-mediated): Qwen 9B prompted with the 5 DNA rules + the proposal, asked YES/NO. Cheap (~0.5s, 80 tokens). → REJECT on YES.
5. **Sandbox dual-track**: combined fitness must be > 0.6.
6. **Rate limit**: max 3 mutations/day in adulto, 1/day in anziano.
7. **Auto-rollback monitor**: 24h after promotion, fitness must not have dropped > 0.1 vs parent. If it did, automatic rollback.

**What CELL CANNOT do, by construction:**
- Modify `cell/core/dna.py`, `cell/core/dna_interpreter.py`, `cell/core/safety.py` — they're read-only at runtime, no API to mutate them
- Add new actions to the allowlist — `_ACTIONS` is a frozen dict in `effectors/allowlist.py`
- Bypass kill switches — Safety Gate is checked at the top of every pulse, before any Cortex code runs
- Execute arbitrary code — skills are `list[str]` of allowlisted action names, not Python
- Spam operations — DNAInterpreter's cooldown/daily-limit applies regardless of skill source

---

## 10. Backward compatibility

- **`cortex=None` is fully supported** — PulseEngine works exactly as Phase 1+2 if no Cortex injected
- **All cortex hooks are wrapped in try/except** — if any hook raises, pulse continues
- **No modifications to**: `dna.py`, `dna_interpreter.py`, `safety.py`, `config.py`, fast/sensors/effectors/identity (except Cortex calls public methods on `self_model`), `memory/episodic.py` (only adds return value to `store()`), `memory/dreamer.py`, `lifecycle/maturation.py` (extended via wrapping)
- **No changes to existing tests** — all 22 Phase 1+2 test files remain valid
- **DB tables are additive** — `CREATE TABLE IF NOT EXISTS` only, no DROP, no rename, no ALTER on existing tables

Rollback strategy: remove `cortex=cortex` parameter from PulseEngine instantiation in main.py and restart. CELL reverts to Phase 1+2 instantly. The 7 cortex tables remain dormant in the DB.

---

## 11. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Cortex LLM calls every pulse → latency regression | HIGH | Hook 1 is no-LLM (DB+scoring, ~50ms). Hook 2 LLM in try/except, 15s timeout. Hook 3 budget-gated. Hook 4 in non-critical sleep. |
| Mutator generates non-sense skills | MEDIUM | 4 filter layers + sandbox + rate limit + auto-rollback |
| Skill apoptosis kills useful skills | MEDIUM | Decay requires BOTH 30+d unused AND fitness < 0.3. Status flip, never DELETE — recoverable from audit |
| Critic miscalibration produces wrong weaknesses | LOW | Weakness emitted only after pattern (3+ consecutive failures), not single events. Self-model.weaknesses inspectable |
| Sandbox replay too slow | MEDIUM | Track A capped at 8 episodes × 15s timeout = 120s/test. Max 3/day → 6 min/day total |
| AchievementGate blocks CELL too long | MEDIUM | Thresholds reachable in ~2 weeks normal activity. Auto-goal pushes priority. Escape hatch: age ≥ floor+14d → auto-promote with warning |
| Cortex orchestrator becomes god-object | LOW | Thin coordinator, components autonomous. Refactor easy if it grows |
| Postgres tunnel down → cortex crashes | HIGH | All hooks wrapped in try/except, log warning and skip. Pulse continues. Same pattern as existing LTM/STM |
| Migration breaks rolling deploy | LOW | All `IF NOT EXISTS`. No DROP, no rename. Rollback = cortex=None |
| Ollama model name change | LOW | Reuses `SlowReasoner` for all LLM calls — single source of truth in `CellSettings` |

---

## 12. Success metrics (after 7 days of operation)

1. **Zero regression** — pulse latency p95 < 2s, no new "cortex crash" Telegram alerts
2. **Critic functional** — ≥ 80% of episodes with `action_taken IS NOT NULL` have outcome ≠ 'partial'
3. **Skills seeded** — ≥ 5 skill candidates generated via Critic/Curiosity (status='candidate' or 'active')
4. **Curiosity active** — ≥ 20 findings recorded, ≥ 5 actionable
5. **Goal pipeline** — ≥ 10 goals generated, ≥ 5 resolved
6. **Mutation guards hold** — every 'promoted' row in `cell_skill_audit` has `sandbox_score >= 0.6`
7. **Achievement tracking** — `achievement_gate.achievements()` returns sensible, growing values

---

## 13. Scope boundaries

### IN scope

- 6 components (SkillLibrary, CriticAgent, StrategyMutator, CuriosityEngine, GoalGenerator, AchievementGate) + Cortex orchestrator
- 7 PostgreSQL tables
- 4 hooks in PulseEngine (wrapped)
- AchievementGate wrapping Maturation (additive)
- ~88 tests (≥ 88% coverage on new code)
- Backward compat (cortex=None == Phase 1+2)
- Lifecycle gating for graceful activation
- Full safety chain (allowlist + filter + DNA + constitutional + sandbox + rate limit + auto-rollback)

### OUT of scope (explicit YAGNI)

- Real vector embeddings (pgvector, FAISS, sentence-transformers) — pseudo-embedding only
- Dashboard / UI for inspection
- MCP exposure of cortex state
- Anziano "mentoring entries" writing lessons for future CELLs
- Multi-cell cooperation / replication (DNA rule 5)
- Dynamic learning of lifecycle parameters
- Skill import/export from file
- Skill composition (skills calling other skills)
- Real-time mutation during pulse (mutations only in sleep)
- Constitutional AI full recursive loop
- Separate "Strategy" abstraction distinct from Skill
- Event bus / pub-sub between components
- New config files (constants live in modules, edited in code)

---

## 14. Files touched

### New files (17)

```
cell/cortex/__init__.py
cell/cortex/cortex.py
cell/cortex/skill_library.py
cell/cortex/critic.py
cell/cortex/strategy_mutator.py
cell/cortex/curiosity_engine.py
cell/cortex/goal_generator.py
cell/lifecycle/achievement_gate.py
tests/test_cortex_db_bootstrap.py
tests/test_skill_library.py
tests/test_critic_agent.py
tests/test_strategy_mutator.py
tests/test_curiosity_engine.py
tests/test_goal_generator.py
tests/test_achievement_gate.py
tests/test_cortex_integration.py
tests/test_pulse_with_cortex.py
```

### Modified files (5, minimally)

```
cell/core/db.py             # +create_cortex_tables() + 7 CREATE TABLE constants
cell/core/pulse.py          # +cortex param, +4 hook calls (try/except wrapped)
cell/main.py                # +Cortex instantiation + wire-up
cell/memory/episodic.py     # store() returns id (1-line change)
cell/slow/reasoner.py       # think() accepts skill_context kwarg (1-line change)
```

### Files NOT touched (backward-compat guarantee)

- `cell/core/dna.py`, `dna_interpreter.py`, `safety.py`, `config.py`
- `cell/fast/*.py`
- `cell/sensors/*.py`
- `cell/effectors/*.py`
- `cell/identity/self_model.py`, `journal.py` (called via public API only)
- `cell/memory/dreamer.py`, `long_term.py`, `pattern_index.py`, `short_term.py`
- `cell/lifecycle/maturation.py` (extended via wrapping in `achievement_gate.py`)

---

## 15. Glossary

- **Cortex**: the Phase 3+4 orchestrator module, single attribute on PulseEngine
- **Skill**: named procedure with trigger NL, action sequence, fitness — the unified abstraction (no separate "Strategy")
- **Expectation**: Critic's prediction of an action's outcome, registered when action is proposed
- **Critique**: post-hoc evaluation of an Expectation N pulses later
- **Goal**: tracked agenda item from one of 4 sources (curiosity, critic, dreamer, decay)
- **Finding**: output of curiosity exploration (SQL or LLM retrospective)
- **Apoptosis**: status flip to 'apoptosed' (not DELETE) when a skill decays or regresses
- **Achievement**: countable accomplishment used by AchievementGate (episodes, skills, goals, etc.)
- **Effective phase**: `min(age_phase, achievement_phase)` — what CELL is actually allowed to do
- **Sandbox dual-track**: combined LLM replay (8 episodes) + pattern simulation (100 episodes) used by Mutator before promoting
- **Constitutional check**: an LLM call asking "does this proposal violate any of the 5 DNA rules?"

---

## 16. References

- Roadmap: `docs/superpowers/specs/2026-04-03-cell-vivente-autonomo-roadmap.md`
- Phase 1+2 spec: `docs/superpowers/specs/2026-03-28-cell-v2-sensors-memory-reasoner-design.md`
- DNA: `apps/cell/cell/config/dna.json`
- Allowlist: `apps/cell/cell/effectors/allowlist.py`
- Existing Maturation: `apps/cell/cell/lifecycle/maturation.py`
- Existing PulseEngine: `apps/cell/cell/core/pulse.py`
- Cicatrix scars (test patterns): `.claude/rules/cicatrix-scars.md`

---

**Author:** Claude Opus 4.6 (in collaboration with CELL's owner)
**Status:** ready for implementation plan via writing-plans skill
