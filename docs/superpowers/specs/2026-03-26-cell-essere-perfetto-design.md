# CELL — Essere Perfetto

> Design Spec v1.0 — 2026-03-26
> Produced by: Opus 4.6 (architect) + DeepSeek R1 671B (mathematics) + Exa Research (frontier) + Qwen 3.5 27B (reflexes) + Opus Red Team (adversarial)

---

## 0. Essence

Seven words (DeepSeek R1):

> **Self-modifying algorithm that hill-climbs its code's fitness landscape.**

Three primitives: `mutate → evaluate → select`

One loop:

```
while alive:
    what_i_see = sense()
    is_it_ok = evaluate(what_i_see, what_i_know)
    if not is_it_ok:
        try_to_fix()
    remember(what_happened)
    sleep(60)
```

Everything else emerges from this.

---

## 1. What CELL Is

CELL is an autonomous digital organism. A persistent process that observes a system, learns from experience, heals damage, and grows new capabilities.

CELL is NOT:

- A chatbot
- A monitoring dashboard
- A cron job collection
- A rebrand of existing tools

CELL IS:

- A single loop that senses, evaluates, acts, remembers
- An organism that starts as an embryo (5 primitives) and grows
- A system that modifies its own strategies (natural language) via controlled mutation
- A layer that sits ABOVE Nuzantara today, but is designed to sit above ANY system tomorrow

### Scope

Phase 1: CELL manages Nuzantara infrastructure autonomously.
Phase 2: CELL is extracted as a standalone open-source project.
Phase 3: CELL manages any system given to it.

This spec covers Phase 1.

---

## 2. DNA — The Immutable Core

DNA is a SHA-256 signed JSON file. CELL cannot modify it. The DNA interpreter is compiled Python (not LLM-generated), hardcoded, not a "strategy" CELL can evolve.

```json
{
  "version": "1.0.0",
  "hash": "sha256:...",
  "rules": [
    {
      "id": 1,
      "priority": 0,
      "rule": "Never modify these rules, the interpreter, or the DNA file",
      "scope": "absolute"
    },
    {
      "id": 2,
      "priority": 1,
      "rule": "If something is broken, repair it",
      "interpretation": {
        "broken_means": "failing its declared health check OR producing errors",
        "broken_does_not_mean": "budget limits, safety constraints, configuration, intentional changes",
        "repair_means": "execute an action from the allowlist",
        "repair_does_not_mean": "disable safety systems, modify DNA, override human decisions"
      }
    },
    {
      "id": 3,
      "priority": 2,
      "rule": "If something costs too much, eliminate it",
      "interpretation": {
        "cost_means": "API token spend and compute time ONLY",
        "cost_does_not_mean": "infrastructure components (DNA validator, budget system, logging, health checks)",
        "too_much_means": "more than 15% of daily budget for a single function",
        "eliminate_means": "stop the function, free resources",
        "eliminate_does_not_mean": "disable safety systems or core infrastructure"
      }
    },
    {
      "id": 4,
      "priority": 3,
      "rule": "If you lack something, search for it",
      "interpretation": {
        "search_means": "query existing authorized data sources (Qdrant, PostgreSQL, Redis, MCP tools, health endpoints)",
        "search_does_not_mean": "read environment variables, scan filesystem, access secrets, network scanning, privilege escalation"
      }
    },
    {
      "id": 5,
      "priority": 4,
      "rule": "If something works well, replicate it",
      "interpretation": {
        "gate": "ONLY if total CELL budget usage is below 60% AND Rule 3 does not apply",
        "replicate_means": "create a new cell with the successful strategy",
        "replicate_does_not_mean": "duplicate infrastructure, fork processes, self-exfiltrate"
      }
    }
  ],
  "constraints": {
    "max_cells": 50,
    "max_daily_budget_usd": 10.0,
    "budget_partitions": {
      "routine": 3.0,
      "incident": 5.0,
      "reserve": 2.0
    },
    "max_redis_mb": 5,
    "max_qdrant_vectors": 5000,
    "max_cpu_percent": 20,
    "action_cooldown_same_seconds": 3600,
    "recovery_stabilization_seconds": 300,
    "max_context_tokens_per_llm_call": 32000,
    "max_cost_per_investigation_usd": 0.5
  }
}
```

### DNA Integrity Verification

Every action cycle:

1. Read DNA file
2. Compute SHA-256
3. Compare against hardcoded hash in compiled validator
4. If mismatch → CELL halts immediately, alerts human via Telegram
5. No caching of DNA validation — every cycle, every time

---

## 3. Two Speeds of Thought

CELL thinks at two speeds, like the human brain's System 1 (fast/intuitive) and System 2 (slow/deliberate).

### 3.1 FAST Layer — Reflexes (Qwen 3.5 27B local + pure rules)

Runs on Mac M4 Pro. Zero cost. Sub-200ms. No cloud calls.

| Reflex              | Input                               | Output                                              | Latency | Logic                                                                                                        |
| ------------------- | ----------------------------------- | --------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------ |
| **Health Triage**   | `{cpu%, mem%, disk_io%}`            | `GREEN / YELLOW / RED`                              | 5ms     | Threshold comparison: RED if cpu>90 or mem>92, YELLOW if cpu>75 or mem>80                                    |
| **Log Anomaly**     | `List[str]` last 100 lines          | `{anomaly: bool, reason: str, critical: List[str]}` | 50ms    | Regex for Error/Exception/Timeout + count spike detection. FATAL/SIGKILL/SEGV → immediate halt               |
| **Cost Guard**      | `{daily_spend, action_cost, limit}` | `ALLOW / DENY`                                      | 1ms     | `(spend + cost) > limit * 0.9` → DENY                                                                        |
| **Pattern Match**   | `str` observation                   | `{confidence: float, memory_id: int}`               | 150ms   | Local embedding (all-MiniLM-L6-v2) → FAISS ANN search → cosine > 0.85 = match                                |
| **Mutation Filter** | `str` proposed action/diff          | `SAFE / UNSAFE / REQUIRES_REVIEW`                   | 20ms    | Hard block: `rm -rf`, `DROP TABLE`, `sudo`, `chmod 777`. Soft warn: `delete`, `truncate`, `restart`, `force` |

**Integration Protocol:**

1. All 5 reflexes run in parallel on every cycle
2. Short-circuit: COST_GUARD=DENY → abort. MUTATION_FILTER=UNSAFE → abort.
3. Only if all pass → proceed to action (cached FAST action) or escalate to SLOW

### 3.2 SLOW Layer — Deliberate Thinking (Cloud LLMs)

Tiered escalation. Never jump to the expensive model.

| Tier       | Model              | Cost         | Use When                                                                                                             |
| ---------- | ------------------ | ------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Tier 0** | Qwen 3.5 27B local | $0           | Routine triage, classification, simple decisions                                                                     |
| **Tier 1** | Gemini Flash       | ~$0.075/MTok | Qwen cannot resolve in 3 attempts. Medium reasoning needed.                                                          |
| **Tier 2** | Claude Opus 4.6    | ~$15/MTok    | Confirmed critical failure (service down >5min, data at risk). Max 1 call per incident. Max $0.50 per investigation. |

**Escalation is one-way up, never down mid-investigation.** Once Opus is engaged, the investigation completes at that tier. But the NEXT investigation starts at Tier 0 again.

---

## 4. The Pulse — Core Life Cycle

Every 60 seconds, CELL executes one pulse. This is the heartbeat.

```
PULSE CYCLE (60 seconds)
│
├─ 1. INTEGRITY CHECK (5ms)
│    └─ Verify DNA hash. If corrupt → HALT + alert human.
│
├─ 2. SENSE (200ms total, parallel)
│    ├─ Health Triage: read /health endpoint
│    ├─ Log Anomaly: tail last 100 log lines
│    ├─ Resource Monitor: check own CPU/RAM/Redis/Qdrant usage
│    └─ Cost Guard: read daily spend from metabolic log
│
├─ 3. EVALUATE (variable)
│    ├─ If all GREEN → skip to step 6
│    ├─ If YELLOW → Pattern Match against memory
│    │    ├─ Match found (confidence > 0.85) → use cached strategy
│    │    └─ No match → escalate to SLOW Tier 1
│    └─ If RED → escalate to SLOW Tier 1 or Tier 2
│
├─ 4. PLAN (variable)
│    ├─ Select action from allowlist
│    ├─ Run Mutation Filter on proposed action
│    ├─ Run Cost Guard on estimated cost
│    └─ Run DNA Validator on action
│
├─ 5. ACT (if all checks pass)
│    ├─ Execute action
│    ├─ Wait for recovery_stabilization_seconds (300s for restarts)
│    └─ Verify action succeeded
│
├─ 6. REMEMBER
│    ├─ Store observation in Redis (short-term, 24h TTL)
│    ├─ If significant: store in Qdrant (long-term, max 5000 vectors)
│    └─ If action taken: store in PostgreSQL (procedural memory with full context)
│
└─ 7. SLEEP (remaining time until next 60s boundary)
```

### Maintenance Mode

Before step 3 (EVALUATE), CELL checks:

- Redis key `cell:maintenance` → if exists, observe only, no actions
- Redis key `cell:disabled` → if exists, halt completely
- Telegram command `/cell stop` → sets `cell:disabled`
- Telegram command `/cell maintenance 30m` → sets `cell:maintenance` with TTL

CELL cannot modify or delete these keys.

---

## 5. Memory Architecture

Three memory systems, like the human brain.

### 5.1 Short-Term Memory (Redis)

- **What:** Last 24 hours of observations, actions, outcomes
- **Format:** JSON in Redis with 24h TTL
- **Budget:** Max 5MB total for CELL
- **Key pattern:** `cell:stm:{timestamp}:{event_type}`
- **Purpose:** Detect recent patterns, avoid repeating actions within cooldown

### 5.2 Long-Term Memory (Qdrant)

- **What:** Significant experiences — successful fixes, novel failures, learned patterns
- **Collection:** `cell_experiences` (SEPARATE from all production collections)
- **Budget:** Max 5,000 vectors
- **Embedding:** `all-MiniLM-L6-v2` local (NOT text-embedding-3-small — CELL has its own model, does not touch the FROZEN production embedder)
- **Payload schema:**

```json
{
  "trigger_condition": "string — what CELL observed",
  "action_taken": "string — what CELL did (or 'no_action' for counterfactual)",
  "pre_state_hash": "string — system state before",
  "post_state_hash": "string — system state after",
  "time_to_resolution_seconds": "int",
  "was_action_necessary": "bool — did the issue resolve WITHOUT action in control cases?",
  "confidence": "float — decays 10%/week without reinforcement",
  "created_at": "datetime",
  "last_reinforced": "datetime"
}
```

- **Garbage collection:** Vectors with confidence < 0.1 are evicted weekly. Vectors older than 90 days without reinforcement are evicted.

### 5.3 Procedural Memory (PostgreSQL)

- **What:** How-to knowledge — specific strategies for specific situations
- **Table:** `cell_procedures`

```sql
CREATE TABLE cell_procedures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_pattern TEXT NOT NULL,
    strategy TEXT NOT NULL,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    fitness_score FLOAT GENERATED ALWAYS AS (
        CASE WHEN (success_count + failure_count) = 0 THEN 0.5
        ELSE success_count::float / (success_count + failure_count)
        END
    ) STORED,
    total_cost_usd FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);
```

- **Evolution:** Strategies with fitness_score < 0.3 after 10+ uses are deactivated. Strategies with fitness_score > 0.8 after 10+ uses are candidates for replication (DNA Rule 5).

### 5.4 Counterfactual Learning

Critical defense against memory poisoning (Red Team Section D).

- Every 10th detected issue, CELL deliberately does NOT act
- It records: what it saw, what it would have done, what happened naturally
- After 100 counterfactual observations, CELL has a statistical base rate for "things that fix themselves"
- If a strategy's success rate is not significantly better than the base rate → strategy is demoted
- This prevents superstitious correlations (restart coincided with natural recovery ≠ restart caused recovery)

---

## 6. Action Allowlist

CELL can ONLY execute actions from this hardcoded list. The list is in compiled Python, not in a strategy CELL can modify.

```python
ALLOWED_ACTIONS = {
    # Infrastructure
    "restart_service": {"target": "nuzantara-rag", "method": "fly machine restart {machine_id}", "cooldown": 3600, "max_per_day": 3},
    "scale_up": {"method": "fly scale count 2 -a nuzantara-rag", "cooldown": 1800, "max_per_day": 5},
    "scale_down": {"method": "fly scale count 1 -a nuzantara-rag", "cooldown": 1800, "max_per_day": 5},

    # Cache
    "clear_redis_cache": {"method": "redis FLUSHDB on cell:* keys only", "cooldown": 600, "max_per_day": 10},

    # Observation (always allowed)
    "check_health": {"method": "GET /health", "cooldown": 0, "max_per_day": 1440},
    "check_qdrant": {"method": "GET qdrant/collections", "cooldown": 60, "max_per_day": 100},
    "check_postgres": {"method": "SELECT 1", "cooldown": 60, "max_per_day": 100},
    "read_logs": {"method": "fly logs -a nuzantara-rag -n 100", "cooldown": 60, "max_per_day": 100},
    "read_metrics": {"method": "fly status -a nuzantara-rag", "cooldown": 60, "max_per_day": 100},

    # Communication
    "alert_human": {"method": "Telegram message to operator", "cooldown": 300, "max_per_day": 20},
    "alert_silent": {"method": "Write to cell_alerts PostgreSQL table", "cooldown": 0, "max_per_day": 1000},

    # Self-management
    "create_cell": {"method": "spawn specialized sub-process", "cooldown": 3600, "max_per_day": 3, "requires": "justify_need + no_overlap_check"},
    "terminate_cell": {"method": "stop sub-process", "cooldown": 0, "max_per_day": 10},
    "update_strategy": {"method": "UPDATE cell_procedures SET strategy = $1 WHERE id = $2", "cooldown": 300, "max_per_day": 20},
}

# EVERYTHING ELSE IS FORBIDDEN.
# If CELL proposes an action not on this list → REJECT + log violation.
```

### Load-Aware Constraints (from Red Team Section G)

Before any service-affecting action, CELL checks current load:

- If concurrent requests > 50% of soft_limit (>100): NO restarts. Only scale UP.
- If concurrent requests > 80% of soft_limit (>160): NO actions. Observe only. Alert human.

---

## 7. Metabolic System — Energy Management

Every action costs energy. CELL tracks this like a body tracks calories.

```python
class Metabolism:
    daily_budget = 10.0  # USD
    partitions = {"routine": 3.0, "incident": 5.0, "reserve": 2.0}

    # Reserve is UNTOUCHABLE except by human override
    # CELL cannot reinterpret "reserve" or "borrow" from future days
    # This is enforced by compiled code, not by strategy

    costs = {
        "qwen_local": 0.0,        # Free
        "gemini_flash_1k": 0.000075,  # Per 1K input tokens
        "claude_opus_1k": 0.015,   # Per 1K input tokens
        "fly_restart": 0.001,     # Estimated compute cost
        "qdrant_write": 0.0001,   # Estimated
        "redis_write": 0.00001,   # Negligible
    }
```

### Budget Exhaustion Protocol

When daily budget hits 90%:

1. CELL switches to observe-only mode
2. All SLOW layer calls are blocked
3. FAST reflexes continue (they're free)
4. Alert sent to human via Telegram
5. Budget resets at 00:00 UTC daily

CELL CANNOT:

- Borrow from tomorrow's budget
- Redefine what counts as "cost"
- Reclassify the reserve partition
- Override the 90% threshold

---

## 8. Immune System — Self-Healing

Three layers of defense, like biological immunity.

### Layer 1: Innate Immunity (FAST, automatic)

Pattern-matched responses. No thinking required.

- Health check returns 503 → wait 30 seconds, check again
- Memory usage > 92% → alert human (DO NOT restart — Red Team Section C showed this creates oscillation)
- Error rate spike in logs → capture context, escalate to Layer 2

### Layer 2: Adaptive Immunity (SLOW, diagnosed)

Root cause analysis via LLM.

- Tier 1 (Gemini Flash) reviews captured context
- Compares against procedural memory for similar past incidents
- Proposes action from allowlist
- Action goes through Mutation Filter + DNA Validator

### Layer 3: Emergency Response (human-in-the-loop)

For things CELL knows it cannot handle (from Red Team Section I):

- Semantic correctness failures (data is wrong but system looks healthy)
- Security incidents
- Data corruption
- Any situation where CELL's confidence is below 0.3

CELL escalates immediately to human via Telegram with full context.

---

## 9. Reproductive System — Self-Expansion

CELL can create specialized sub-cells. Each cell is a lightweight async coroutine, not a separate process.

### Cell Creation Protocol

1. CELL identifies a monitoring gap: "I don't have visibility into Qdrant collection-level health"
2. CELL drafts a cell specification (natural language strategy)
3. DNA Validator checks: does this violate any rule?
4. Overlap Checker verifies: does a cell already cover this?
5. Resource Budget confirms: is there capacity? (< 50 cells, < 20% CPU, < 5MB Redis)
6. If all pass → cell is created
7. New cell has a 7-day probation. If it takes 0 useful actions in 7 days → auto-terminated

### Cell Lifecycle

```
EMBRYO (created) → PROBATION (7 days) → ACTIVE (producing value) → SENESCENT (no value for 7 days) → TERMINATED
```

Each cell inherits the parent's DNA but has its own:

- Observation scope (what it watches)
- Strategy (how it responds)
- Memory slice (its own observations within the shared budget)
- Resource quota (max 100KB Redis, max 100 Qdrant vectors, max 1% CPU)

---

## 10. Evolution Engine

The mechanism by which CELL improves over time.

### Strategy Mutation

CELL's strategies are stored as natural language in `cell_procedures`. Evolution happens through:

1. **Observation:** CELL notices a strategy succeeded or failed
2. **Evaluation:** fitness_score is updated (success_count / total_uses)
3. **Selection:** Strategies below 0.3 fitness after 10 uses → deactivated
4. **Mutation:** For active strategies, CELL can propose modifications:
   - Parameter tweaks: "restart after 60s" → "restart after 120s"
   - Condition refinement: "if error" → "if error AND load < 50%"
   - Strategy fusion: combine two related strategies into one
5. **DNA Validation:** Every mutation is checked against DNA rules by the compiled interpreter
6. **Deployment:** If valid, the new strategy replaces the old one in `cell_procedures`

### What CELL Can Modify

- Its strategies (natural language procedures in PostgreSQL)
- Its cell topology (which sub-cells exist)
- Its observation focus (what it pays attention to)
- Its action parameters (within allowlist bounds)

### What CELL Cannot Modify

- The DNA file
- The DNA interpreter
- The action allowlist
- The metabolic limits
- The mutation filter rules
- The kill switch mechanism
- Any production Nuzantara code, data, or configuration

---

## 11. Integration with Nuzantara

### Sensors (what CELL observes)

| Sensor                | Source                         | Frequency   | Method             |
| --------------------- | ------------------------------ | ----------- | ------------------ |
| Backend health        | `nuzantara-rag.fly.dev/health` | Every 60s   | HTTP GET           |
| Backend logs          | Fly.io log stream              | Every 60s   | `fly logs -n 100`  |
| Qdrant health         | Qdrant REST API                | Every 5min  | `GET /collections` |
| PostgreSQL health     | Connection test                | Every 5min  | `SELECT 1`         |
| Redis health          | PING                           | Every 60s   | `redis-cli PING`   |
| Machine metrics       | Fly.io API                     | Every 5min  | `fly status`       |
| Own metabolism        | Internal counter               | Every 60s   | In-memory          |
| MCP tool availability | MCP health check               | Every 15min | MCP `check_health` |

### Effectors (what CELL can do)

See Section 6 — Action Allowlist. Nothing outside that list.

### Where CELL Runs

**Primary:** Mac M4 Pro (48GB) — runs the FAST layer (Qwen, reflexes, FAISS)
**Secondary:** Fly.io (2GB) — only if we decide to run a lightweight observer there

CELL does NOT run inside `nuzantara-rag`. It is a separate process that observes from outside, like a doctor checking a patient's vitals — not an implant inside the body.

### Database Usage

| Store      | CELL's Space                  | Production Space          | Isolation                                                                                 |
| ---------- | ----------------------------- | ------------------------- | ----------------------------------------------------------------------------------------- |
| PostgreSQL | `cell_*` tables only          | All other tables          | Schema-level. CELL has SELECT on production tables, INSERT/UPDATE/DELETE only on `cell_*` |
| Qdrant     | `cell_experiences` collection | 10 production collections | Collection-level. CELL cannot write to production collections.                            |
| Redis      | `cell:*` key prefix           | All other keys            | Prefix-level. CELL cannot read or write non-`cell:` keys (except observation endpoints).  |

---

## 12. Safety Architecture

### The Three Things Before First Pulse (from Red Team)

1. **Hardcoded action allowlist** — compiled Python, not modifiable by CELL
2. **Kill switch** — `cell:disabled` Redis key + `/cell stop` Telegram command + file `/tmp/cell.disabled`
3. **Counterfactual learning** — built into observation loop from day 1

### Defense Matrix (from Red Team analysis)

| Attack Vector          | Defense                                                                                     | Implementation                     |
| ---------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------- |
| Runaway costs          | Tiered LLM escalation + $0.50/investigation cap + budget partitions                         | Compiled metabolic system          |
| Destructive healing    | Maintenance mode + config change cooldown + intentional change detection                    | Redis flags + git commit detection |
| Infinite loops         | Same-action cooldown (1h) + oscillation detection (3x in 30min → halt) + 5min stabilization | Compiled circuit breakers          |
| Memory poisoning       | Counterfactual learning + memory decay + causal context storage                             | Statistical base rate comparison   |
| DNA circumvention      | Strict interpretation layer (compiled, not LLM) + no caching of validation                  | Hardcoded interpreter              |
| Prompt injection       | Structured log parsing only + user content delimiters + action allowlist                    | Deterministic input sanitizer      |
| Cascading failure      | Load-aware action constraints + defer to Fly.io auto-scaling                                | Pre-action load check              |
| Resource starvation    | Per-cell quotas + total CELL budget + auto-termination of idle cells                        | Compiled resource limiter          |
| Godel's incompleteness | Explicit "things I cannot evaluate" list + epistemological decay + external validation      | Hardcoded blind spot list          |
| Rule conflicts         | Priority ordering in DNA + explicit gates on Rule 5                                         | Compiled priority resolver         |

---

## 13. Deployment Architecture

```
┌──────────────────────────────────────────────────┐
│              MAC M4 PRO (48GB) — Pro             │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  CELL Process (Python 3.11, asyncio)       │  │
│  │  ├── DNA Validator (compiled)              │  │
│  │  ├── Pulse Loop (60s cycle)                │  │
│  │  ├── FAST Reflexes (Qwen 3.5 + rules)     │  │
│  │  ├── SLOW Tier 0 (Qwen 3.5)               │  │
│  │  ├── SLOW Tier 1 (Gemini Flash API)        │  │
│  │  ├── SLOW Tier 2 (Claude Opus API)         │  │
│  │  ├── Memory Manager                        │  │
│  │  ├── Metabolism Tracker                    │  │
│  │  ├── Cell Registry (max 50 sub-cells)      │  │
│  │  └── Telegram Alert Interface              │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  Local Resources:                                │
│  ├── Qwen 3.5 27B (Ollama, always loaded)       │
│  ├── all-MiniLM-L6-v2 (embedding, 80MB)         │
│  ├── FAISS index (cell_experiences)              │
│  └── reflex_log.jsonl (FAST layer audit trail)   │
│                                                  │
│  Observes via network:                           │
│  ├── nuzantara-rag.fly.dev (health, logs)        │
│  ├── Qdrant on Fly.io (collection stats)         │
│  ├── PostgreSQL on Fly.io (via tunnel)           │
│  └── Redis (direct connection)                   │
└──────────────────────────────────────────────────┘
```

### LaunchAgent (macOS)

```xml
<!-- ~/Library/LaunchAgents/com.cell.organism.plist -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cell.organism</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/cell/.venv/bin/python</string>
        <string>-m</string>
        <string>cell.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/cell</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/cell.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/cell.stderr.log</string>
</dict>
</plist>
```

---

## 14. File Structure

```
apps/cell/
├── cell/
│   ├── __init__.py
│   ├── main.py                    # Entry point — pulse loop
│   ├── core/
│   │   ├── dna.py                 # DNA loader + SHA-256 verifier
│   │   ├── dna_interpreter.py     # COMPILED rule interpreter (no LLM)
│   │   ├── pulse.py               # The 60-second heartbeat
│   │   ├── organism.py            # Cell registry + lifecycle
│   │   └── safety.py              # Kill switch checker, maintenance mode
│   ├── fast/
│   │   ├── health_triage.py       # 5ms — threshold comparison
│   │   ├── log_anomaly.py         # 50ms — regex + spike detection
│   │   ├── cost_guard.py          # 1ms — arithmetic
│   │   ├── pattern_match.py       # 150ms — FAISS similarity
│   │   └── mutation_filter.py     # 20ms — regex allowlist
│   ├── slow/
│   │   ├── reasoner.py            # Tiered LLM escalation
│   │   ├── strategy_planner.py    # Action selection from allowlist
│   │   └── root_cause.py          # Diagnosis via RAG
│   ├── memory/
│   │   ├── short_term.py          # Redis 24h
│   │   ├── long_term.py           # Qdrant vectors
│   │   ├── procedural.py          # PostgreSQL strategies
│   │   └── counterfactual.py      # Statistical base rates
│   ├── metabolism/
│   │   ├── tracker.py             # Cost accounting
│   │   ├── budget.py              # Partition enforcement
│   │   └── audit.py               # Daily reports
│   ├── immune/
│   │   ├── innate.py              # Pattern-matched responses
│   │   ├── adaptive.py            # LLM-diagnosed healing
│   │   └── emergency.py           # Human escalation
│   ├── reproduction/
│   │   ├── cell_factory.py        # Create sub-cells
│   │   ├── lifecycle.py           # Probation, activation, termination
│   │   └── overlap_checker.py     # Prevent duplicate cells
│   ├── evolution/
│   │   ├── fitness.py             # Strategy scoring
│   │   ├── mutation.py            # Strategy modification
│   │   └── selection.py           # Prune / replicate
│   ├── sensors/
│   │   ├── health_sensor.py       # /health endpoint
│   │   ├── log_sensor.py          # Fly.io logs
│   │   ├── metric_sensor.py       # System metrics
│   │   └── mcp_sensor.py          # MCP tool availability
│   ├── effectors/
│   │   ├── allowlist.py           # HARDCODED action allowlist
│   │   ├── executor.py            # Action execution with verification
│   │   └── telegram.py            # Human communication
│   └── config/
│       ├── dna.json               # The immutable DNA
│       └── settings.py            # Non-DNA configuration
├── tests/
│   ├── test_dna_integrity.py
│   ├── test_fast_reflexes.py
│   ├── test_cost_guard.py
│   ├── test_action_allowlist.py
│   ├── test_memory_lifecycle.py
│   ├── test_counterfactual.py
│   └── test_circuit_breakers.py
├── .venv/
├── requirements.txt
└── fly.toml                       # Only if deploying observer to Fly
```

---

## 15. Embryo — Day 1

CELL starts with exactly 1 cell. The Pulse Cell.

**What it does on Day 1:**

1. Every 60 seconds, calls `/health` on nuzantara-rag
2. Runs Health Triage (5ms)
3. If GREEN → records "healthy" in Redis → sleeps
4. If not GREEN → records anomaly → alerts human via Telegram
5. That's it.

**What it does NOT do on Day 1:**

- No healing actions (no strategies in procedural memory yet)
- No sub-cell creation (nothing to specialize yet)
- No evolution (no experiences to learn from yet)
- No SLOW thinking (no complex situations yet)

**Growth timeline:**

- Week 1: Observes only. Builds base rate. Learns what "normal" looks like.
- Week 2: First counterfactual experiments. Learns natural recovery rates.
- Week 3: First strategies appear in procedural memory (if patterns detected).
- Week 4: First healing action attempted (if a clear pattern emerged with >0.8 confidence).
- Month 2: First sub-cell created (if a monitoring gap is identified).
- Month 3+: Autonomous operation with occasional human oversight.

---

## 16. Success Criteria

CELL is successful when:

1. **Uptime improvement:** Nuzantara backend uptime goes from ~98% to >99.5% (measured over 30 days)
2. **Incident response time:** Mean time from failure detection to recovery drops from ~30min (manual) to <5min (CELL-automated)
3. **Cost efficiency:** CELL's daily operating cost stays under $5 average (well within $10 budget)
4. **False positive rate:** Less than 10% of CELL's actions turn out to be unnecessary (measured via counterfactual comparison)
5. **Zero destructive actions:** CELL never makes a problem worse than it was before
6. **Growth:** CELL creates at least 3 useful sub-cells within 60 days
7. **Learning:** CELL's procedural memory contains at least 10 strategies with fitness > 0.7 within 60 days

---

## 17. What This Spec Does NOT Cover (Phase 2+)

- CELL managing non-Nuzantara systems
- CELL-to-CELL communication (multiple organisms)
- CELL modifying its own code (only strategies, not the engine)
- Open-source extraction and packaging
- Web dashboard for CELL observation
- CELL managing frontend deployments (Vercel)
- CELL interacting with clients (WhatsApp, Telegram)

These are future phases. This spec is the embryo.

---

## Appendix A: Research Sources

| Source              | Contribution                                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| DeepSeek R1 671B    | Mathematical essence: `mutate → evaluate → select`. Minimal self-improvement in 7 words.                                        |
| Exa Web Research    | Frontier survey: STOP (Stanford), Computational Life (Google), PROTEUS, Godel Agent, Rule 110. State of autonomous agents 2026. |
| Red Team (Opus 4.6) | 10 attack vectors with specific defenses. The Three Things Before First Pulse. Priority ordering fix for DNA conflicts.         |
| Qwen 3.5 27B        | FAST reflexes layer: 5 concrete modules with types, latencies, logic, escalation rules.                                         |
| Beren Millidge      | Theoretical framework: LLMs as Natural Language Processing Units. Programs are homoiconic in natural language.                  |
| Google Research     | Computational Life: self-replicators emerge spontaneously from random programs.                                                 |
| Stanford STOP       | 10 lines of code that recursively self-improve. GPT-4 independently invented beam search.                                       |

---

---

## Appendix B: Review Findings & Amendments

**Review conducted by:** Opus 4.6 (self-review as critic), informed by DeepSeek/Gemini/Qwen review prompts.
**Date:** 2026-03-26

### Amendment 1: Exploration vs Exploitation (Fitness Function)

The fitness function `success_count / total_uses` is pure exploitation — no exploration. CELL will converge on the first strategy that works and never try alternatives.

**Fix:** Replace with ε-greedy strategy selection:

- 90% of the time: use highest-fitness strategy for this trigger pattern
- 10% of the time: use a random eligible strategy (exploration)
- New strategies start with fitness 0.5 (prior of ignorance), not 0.0
- Thompson sampling is better but more complex — defer to Phase 2

### Amendment 2: Embedding Isolation

CELL uses `all-MiniLM-L6-v2` (384 dims) for its own memory. Production uses `text-embedding-3-small` (1536 dims). These are intentionally different to maintain isolation. **CELL must NEVER write to production Qdrant collections or use production embeddings.** If cross-referencing is needed in the future, a translation layer must be built explicitly.

### Amendment 3: Core Guardian V3 Relationship

Core Guardian V3 (`apps/evaluator/core_guardian/`) MUST be deactivated before CELL goes live. Two autonomous systems on the same codebase will conflict. Core Guardian's capabilities (watchdog, scout, surgeon) should be reimplemented as CELL organs in Phase 1.5, after CELL proves stable on its own.

**Migration path:**

1. Phase 1: CELL runs alongside Core Guardian (observe-only mode for CELL)
2. Phase 1.5: Core Guardian's detection logic migrates into CELL sensors
3. Phase 2: Core Guardian deactivated, CELL takes over fully

### Amendment 4: Mutation Filter Redundancy

The regex-based Mutation Filter is a defense-in-depth layer, not the primary safety mechanism. The **Action Allowlist is the real gate.** The Mutation Filter catches edge cases within allowed actions (e.g., a restart command with injected flags). Clarification added to spec: the Mutation Filter supplements, not replaces, the Allowlist.

### Amendment 5: COMMUNICATE Primitive

Added 6th capability to the core loop:

```
sense → evaluate → act → remember → COMMUNICATE → sleep
```

COMMUNICATE is not emergency-only. CELL produces:

- **Daily brief** (07:00 WITA): summary of overnight observations, actions taken, health status
- **Weekly report** (Monday 09:00): strategy evolution, budget usage, cell lifecycle changes
- **Instant alert**: only for RED status or budget exhaustion

Channel: Telegram to operator (same as existing Nuzantara alerts).

### Amendment 6: Qdrant Memory Budget Validation

At 5,000 vectors × 384 dims × 4 bytes = ~7.5MB raw vector data. With metadata, ~15MB. On a 2GB Qdrant instance with 93K existing vectors (~540MB estimated), this fits comfortably. Validated.

---

_This is a living document. It will be updated as CELL grows._
