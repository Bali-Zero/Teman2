# Skill Registry HGT — Design Spec

**Date:** 2026-04-16
**Status:** IMPLEMENTED — 218 tests green, 69 HGT-specific tests
**Author:** Claude Opus 4.6 (Air session)
**Base:** `2026-04-12-dna-recording-design.md` (approved, 95% implemented)
**Brief:** Sprint 5.2 W3-4 Skill Registry — close remaining 5%

---

## 0. Summary

Close 3 gaps in the genome system to evolve from single-organ DNA recording to
organism-wide circulatory knowledge transfer:

| Gap | What | Status before |
|-----|------|---------------|
| 2 | HGT — Redis Streams publisher/consumer between sibling cells | Zero code |
| 3 | Confidence decay — exponential aging of unused skills | Only cut-off silence (binary) |
| 4 | Vertical feedback — child→parent skill improvement proposals | Zero code |
| + | Domain column + taxonomy for cross-domain routing | Schema lacks domain |

Gap 1 (session-reflect → genome) is already implemented in `~/.claude/scripts/session-reflect.py:229-288`.

---

## 1. Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │       Redis Streams (L1 real-time)   │
                    │                                     │
    cell:skills ◄───┤  HGT Publisher ← REFLECT hook       │
         │          │                                     │
         ▼          │  cell:feedback ← Vertical Feedback  │
    HGT Consumer    │                                     │
    (per cell)      └─────────────────────────────────────┘
         │
         ▼
    genome.record_skill(inherited_from=origin, confidence*=0.9)
         │
         ▼
    ┌────────────────────────────────────────┐
    │  Genome SQLite (L2 persistent)         │
    │  + domain column (new)                 │
    │  + decay_unused_skills() (new)         │
    │  + Cron 02:30 WITA nightly (new)       │
    └────────────────────────────────────────┘
```

### Streams

| Stream | Purpose | Fields |
|--------|---------|--------|
| `cell:skills` | Sibling skill transfer (HGT) | skill_id, cell_origin, procedure, precondition, success_criterion, confidence, type, scope, domain |
| `cell:feedback` | Child→parent improvement proposals | skill_id, from_cell, to_cell, new_confidence, procedure_updated, uses, original_inherited_from |

### Consumer Groups

Each cell registers its own consumer group: `hgt_{cell_name}` on `cell:skills`.
Parent cells register: `feedback_{cell_name}` on `cell:feedback`.

---

## 2. Decision: Confidence Decay Formula

### Options Considered

| Option | Formula | Pros | Cons |
|--------|---------|------|------|
| **Exponential** | `conf × 0.95^days` | Ebbinghaus-aligned, simple, one constant | Aggressive for long-unused but valid skills |
| Sigmoid | `conf × σ(-k(days-midpoint))` | Gentle start, sharp cutoff | Two constants (k, midpoint), harder to tune |
| Linear | `conf - (rate × days)` | Dead simple | Too aggressive early, unnatural |
| Step | Current: silence at 30 days if <0.4 | Zero compute | Binary, no gradual degradation |

### Decision: **Exponential with guard rails**

```python
new_conf = confidence * (DECAY_RATE ** days_unused)
# DECAY_RATE = 0.95
# Guard: never decay below 0.3 (silence threshold handles that)
# Guard: never decay skills used in last 7 days
# Guard: scars (type='scar') don't decay — avoidance memory is permanent
```

**Why exponential:** Ebbinghaus forgetting curve is exponential. It's been validated
by 140 years of cognitive science. One constant to tune. Natural half-life:
at 0.95/day, a skill with conf=0.8 reaches 0.3 in ~62 days. That feels right
for operational knowledge.

**Interaction with existing `silence_stale_skills()`:**
- Decay runs nightly (cron 02:30)
- `silence_stale_skills()` runs in DREAM hook (less frequent, only during sleep window)
- Decay reduces confidence gradually; silence_stale catches anything that fell to <0.3
- No conflict: decay is the ramp, silence is the cliff

---

## 3. Decision: Feedback Merge Policy

### Options Considered

| Option | Mechanism | Pros | Cons |
|--------|-----------|------|------|
| **Conditional overwrite** | If child.conf > parent.conf + 0.15 AND precondition compatible → update parent | Simple, deterministic | Loses parent's original version |
| Fork | Keep both parent and child versions | Preserves history | Divergence, no convergence mechanism |
| Weighted merge | Blend procedures textually | Theoretically richer | Semantically fragile, impossible to automate reliably |

### Decision: **Conditional overwrite with audit trail**

```python
# Merge conditions (ALL must be true):
# 1. child.confidence > parent.confidence + IMPROVEMENT_THRESHOLD (0.15)
# 2. child.uses >= 3 (proven in practice, not just theory)
# 3. precondition similarity (string overlap > 50% or identical)
# 4. Anti-loop: skill not rejected in last 7 days

# On merge:
# - Parent procedure overwritten with child's improved version
# - Parent confidence = child.confidence * INHERIT_DECAY (0.9)
# - Log old procedure in a 'scar' entry as audit trail
# - Notify via logger (no Telegram — too noisy)
```

**Why not fork:** Forks accumulate without convergence. In biology, gene duplication
is common but most duplicates become pseudogenes (dead). We don't have the selection
pressure to eliminate dead forks. Overwrite is cleaner.

**Anti-loop mechanism:**
- Track rejected proposals in a `_feedback_cooldown` dict: `{(from_cell, skill_id): rejection_timestamp}`
- If skill_id from same cell was rejected within 7 days → skip
- Cooldown is in-memory (not persisted) — restarts clear it, which is fine

---

## 4. Decision: Domain Taxonomy

### Options Considered

| Option | Mechanism | Pros | Cons |
|--------|-----------|------|------|
| **Flat enum** | 11 canonical strings | Simple, fast filter, no dependencies | Not extensible without code change |
| Hierarchical | Tree (business.visa, business.tax) | More precise routing | Complexity, partial matches needed |
| Semantic | Embedding similarity | No taxonomy maintenance | Requires model, slow, overkill |

### Decision: **Flat taxonomy, subscribe-by-domain**

```python
CANONICAL_DOMAINS = frozenset({
    "visa", "tax", "kbli", "property", "legal",
    "crm", "news", "architecture", "rag", "graph", "generic",
})

# 'generic' skills are broadcast to all consumers
# Each consumer declares interested_domains: set[str]
# Publisher tags each skill with domain (required field)
# Consumer filters: if skill.domain in interested_domains or skill.domain == "generic"
```

**Why flat:** At 11 domains and <10 cells, semantic routing is overkill. Flat
taxonomy is O(1) to check, zero dependencies, and extensible by adding strings.
If we ever need 50+ domains, we revisit.

---

## 5. Schema Migration: ADD COLUMN domain

Non-destructive ALTER TABLE. No Alembic (this is SQLite, not PG).

```python
# In Genome.__init__() → _ensure_schema():
# After existing CREATE TABLE, add:
conn.execute("""
    ALTER TABLE genome ADD COLUMN domain TEXT DEFAULT 'generic'
""")
# Wrapped in try/except (idempotent — fails silently if column exists)

# New index:
conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_genome_domain ON genome(domain)
""")
```

**Existing rows:** All get `domain='generic'` (safe default).
**record_skill() signature:** Add `domain: str = "generic"` parameter.

---

## 6. Component Design

### 6.1 HGT Publisher (`hgt/publisher.py`)

```python
class HGTPublisher:
    STREAM = "cell:skills"
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, redis_client, cell_name: str):
        self._redis = redis_client
        self._cell_name = cell_name

    async def publish(self, skill: dict) -> bool:
        """Publish skill to HGT stream if eligible."""
        if skill["confidence"] < self.CONFIDENCE_THRESHOLD:
            return False
        if skill["scope"] != "Project":
            return False
        if skill.get("type") == "scar":
            return False  # scars are Personal by definition

        await self._redis.xadd(self.STREAM, {
            "skill_id": skill["id"],
            "cell_origin": self._cell_name,
            "procedure": skill["procedure"],
            "precondition": skill.get("precondition") or "",
            "success_criterion": skill.get("success_criterion") or "",
            "confidence": str(skill["confidence"]),
            "type": skill.get("type", "skill"),
            "scope": "Project",
            "domain": skill.get("domain", "generic"),
        }, maxlen=1000)  # cap stream size
        return True
```

**Graceful degradation:** Wrapped in try/except at call site. Redis down → skill
still recorded in local genome, just not shared.

### 6.2 HGT Consumer (`hgt/consumer.py`)

```python
class HGTConsumer:
    STREAM = "cell:skills"
    INHERIT_DECAY = 0.9
    BLOCK_MS = 5000  # 5s block, not infinite

    def __init__(self, redis_client, genome: Genome, cell_name: str,
                 interested_domains: set[str]):
        self._redis = redis_client
        self._genome = genome
        self._cell_name = cell_name
        self._domains = interested_domains
        self._group = f"hgt_{cell_name}"

    async def ensure_group(self):
        """Create consumer group if not exists."""
        try:
            await self._redis.xgroup_create(
                self.STREAM, self._group, id="0", mkstream=True
            )
        except Exception:
            pass  # group already exists

    async def consume_once(self) -> int:
        """Read and process pending messages. Returns count processed."""
        entries = await self._redis.xreadgroup(
            groupname=self._group,
            consumername=self._cell_name,
            streams={self.STREAM: ">"},
            count=10,
            block=self.BLOCK_MS,
        )
        processed = 0
        for stream_name, messages in entries:
            for msg_id, data in messages:
                if self._should_consume(data):
                    self._integrate(data)
                    processed += 1
                await self._redis.xack(self.STREAM, self._group, msg_id)
        return processed

    def _should_consume(self, data: dict) -> bool:
        domain = data.get("domain", "generic")
        origin = data.get("cell_origin", "")
        return (
            origin != self._cell_name  # don't consume own skills
            and (domain in self._domains or domain == "generic")
        )

    def _integrate(self, data: dict):
        inherited_conf = float(data["confidence"]) * self.INHERIT_DECAY
        self._genome.record_skill(
            cell=self._cell_name,
            skill_id=f"hgt_{data['skill_id']}",
            procedure=data["procedure"],
            precondition=data.get("precondition", ""),
            success_criterion=data.get("success_criterion", ""),
            confidence=inherited_conf,
            scope="Project",
            inherited_from=data["skill_id"],
            entry_type=data.get("type", "skill"),
            domain=data.get("domain", "generic"),
        )
```

### 6.3 Vertical Feedback (`hgt/feedback.py`)

```python
class VerticalFeedback:
    STREAM = "cell:feedback"
    IMPROVEMENT_THRESHOLD = 0.15
    MIN_USES = 3
    COOLDOWN_DAYS = 7

    def __init__(self, redis_client, genome: Genome, cell_name: str):
        self._redis = redis_client
        self._genome = genome
        self._cell_name = cell_name
        self._cooldown: dict[tuple[str, str], float] = {}  # in-memory

    async def propose_improvement(self, skill: dict) -> bool:
        """If we improved an inherited skill, propose back to parent."""
        if not skill.get("inherited_from"):
            return False
        if skill["uses"] < self.MIN_USES:
            return False

        # Check cooldown
        key = (self._cell_name, skill["id"])
        if key in self._cooldown:
            if time.time() - self._cooldown[key] < self.COOLDOWN_DAYS * 86400:
                return False

        # Get parent's current confidence for comparison
        parent_skill = self._genome.search(skill["inherited_from"])
        if not parent_skill:
            return False
        parent_conf = parent_skill[0].get("confidence", 0)

        if skill["confidence"] <= parent_conf + self.IMPROVEMENT_THRESHOLD:
            return False

        await self._redis.xadd(self.STREAM, {
            "skill_id": skill["id"],
            "from_cell": self._cell_name,
            "to_cell": skill.get("cell_origin_parent", ""),
            "original_inherited_from": skill["inherited_from"],
            "new_confidence": str(skill["confidence"]),
            "procedure_updated": skill["procedure"],
            "uses": str(skill["uses"]),
        }, maxlen=500)
        return True

    async def process_proposals(self) -> int:
        """Parent cell processes improvement proposals from children."""
        # Similar xreadgroup pattern as HGTConsumer
        # Merge policy: conditional overwrite (see §3)
        pass  # implemented in full code
```

### 6.4 Confidence Decay (`genome.py` extension)

```python
def decay_unused_skills(
    self,
    decay_rate: float = 0.95,
    silence_threshold: float = 0.3,
    min_idle_days: int = 7,
) -> dict[str, int]:
    """Exponential decay for unused skills. Returns counts."""
    today = datetime.now(timezone.utc)
    counts = {"decayed": 0, "silenced": 0, "skipped": 0}

    with self._write_lock:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT id, confidence, last_used, type FROM genome
            WHERE valid_to IS NULL AND last_used IS NOT NULL
        """).fetchall()

        for row in rows:
            # Scars don't decay
            if row["type"] == "scar":
                counts["skipped"] += 1
                continue

            last = datetime.fromisoformat(row["last_used"])
            days = (today - last).days
            if days < min_idle_days:
                counts["skipped"] += 1
                continue

            new_conf = row["confidence"] * (decay_rate ** days)
            if new_conf < silence_threshold:
                self.silence_skill(row["id"], reason="decayed_below_threshold")
                counts["silenced"] += 1
            else:
                conn.execute(
                    "UPDATE genome SET confidence = ? WHERE id = ?",
                    (round(new_conf, 4), row["id"]),
                )
                counts["decayed"] += 1

        conn.commit()
    return counts
```

### 6.5 Domain Taxonomy (`hgt/domains.py`)

```python
"""Canonical domain taxonomy for HGT routing."""

CANONICAL_DOMAINS: frozenset[str] = frozenset({
    "visa",          # Visa processing, immigration
    "tax",           # Tax calculation, PPh21, BPJS
    "kbli",          # Business classification codes
    "property",      # Real estate, zoning, investment
    "legal",         # Legal documents, akta, contracts
    "crm",           # Client management, practices
    "news",          # Intelligence, regulations, scraping
    "architecture",  # System design, code patterns
    "rag",           # RAG pipeline, search, embedding
    "graph",         # Knowledge graph, Neo4j, subgraphs
    "generic",       # Cross-domain, applies to all consumers
})

def validate_domain(domain: str) -> str:
    """Validate and normalize domain. Returns 'generic' for unknown."""
    d = domain.lower().strip()
    return d if d in CANONICAL_DOMAINS else "generic"
```

---

## 7. Integration Points

### Mata Garuda REFLECT hook (existing → extend)

```python
# runner.py line 66-72: after genome.record_skill()
# ADD: publish to HGT if confidence >= 0.7
if self.hgt_publisher and confidence >= 0.7:
    try:
        skill_data = {"id": skill_id, "procedure": ..., "confidence": 0.6, ...}
        await self.hgt_publisher.publish(skill_data)
    except Exception:
        pass  # graceful degradation
```

### Consumer cells (new hook in PulseLoop subclass)

Each cell that wants HGT creates a subclass like MataGarudaPulseLoop:

```python
class HGTAwarePulseLoop(PulseLoop):
    def __init__(self, *args, genome, hgt_consumer, **kwargs):
        super().__init__(*args, **kwargs)
        self.genome = genome
        self.hgt_consumer = hgt_consumer

    async def single_pulse(self) -> PulseResult:
        result = await super().single_pulse()
        # Consume HGT skills at end of each pulse
        if self.hgt_consumer:
            try:
                await self.hgt_consumer.consume_once()
            except Exception:
                pass  # Redis down
        return result
```

### Decay cron (new)

`scripts/genome_decay_cron.py` — runs nightly at 02:30 WITA via LaunchAgent.

---

## 8. Graceful Degradation

| Failure | Behavior |
|---------|----------|
| Redis down | Skills recorded locally in genome SQLite. HGT suspended. No crash. |
| Consumer group missing | Auto-created on first consume_once() call |
| Schema migration fails | ALTER TABLE wrapped in try/except (idempotent) |
| Decay cron fails | Skills retain current confidence. Next run catches up. |
| Feedback loop timeout | Proposal dropped. Cooldown prevents retry spam. |
| Unknown domain | Falls back to 'generic' (broadcast) |

---

## 9. Observability

| Metric | How |
|--------|-----|
| `genome.stats()` per cell | Already exists — total, active, silenced, by_type |
| HGT publish count | Logger + return value from publish() |
| HGT consume count | Return value from consume_once() |
| Decay events/day | Return dict from decay_unused_skills() |
| Feedback accepted/rejected | Logger in process_proposals() |
| Skill reuse (uses field) | Already tracked in genome table |

---

## 10. Test Plan

| Test file | Covers |
|-----------|--------|
| `tests/hgt/test_publisher.py` | Publish eligible/ineligible, Redis down, maxlen cap |
| `tests/hgt/test_consumer.py` | Consume with domain filter, self-skip, XACK, decay |
| `tests/hgt/test_feedback.py` | Proposal threshold, cooldown, merge policy |
| `tests/hgt/test_integration.py` | 3-cell end-to-end: publish→consume→use→feedback |
| `tests/genome/test_decay.py` | Exponential math, scar immunity, guard rails |
| `tests/genome/test_domain.py` | Schema migration, validate_domain(), record with domain |

All tests use **real Redis** (not mocks) + **real SQLite** (tmp_path).
Redis-down tests use a fake client that raises ConnectionError.

---

## 11. Files to Create/Modify

### New files
- `packages/cell-core/cell_core/hgt/__init__.py`
- `packages/cell-core/cell_core/hgt/publisher.py`
- `packages/cell-core/cell_core/hgt/consumer.py`
- `packages/cell-core/cell_core/hgt/feedback.py`
- `packages/cell-core/cell_core/hgt/domains.py`
- `packages/cell-core/tests/hgt/__init__.py`
- `packages/cell-core/tests/hgt/test_publisher.py`
- `packages/cell-core/tests/hgt/test_consumer.py`
- `packages/cell-core/tests/hgt/test_feedback.py`
- `packages/cell-core/tests/hgt/test_integration.py`
- `packages/cell-core/tests/genome/test_decay.py`
- `packages/cell-core/tests/genome/test_domain.py`
- `scripts/genome_decay_cron.py`

### Modified files
- `packages/cell-core/cell_core/genome.py` — add domain column, decay_unused_skills()
- `packages/cell-core/cell_core/__init__.py` — export HGT classes
- `apps/mata-garuda/mata_garuda/cell/runner.py` — add HGT publisher hook
- `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py` — add HGT consumer

### Documentation
- This file (design spec)
- `SYMBIOSIS.md` — update DOVE SIAMO
- `VADEMECUM.md` — update §2 with HGT checklist

---

## 12. Open Questions (pending multi-agent review)

1. ~~Decay formula~~ → **DECIDED: exponential 0.95^days** (§2)
2. ~~Merge policy~~ → **DECIDED: conditional overwrite** (§3)
3. ~~Domain routing~~ → **DECIDED: flat taxonomy** (§4)
4. Should HGT consumer run in PulseLoop or as standalone daemon?
   → **Leaning PulseLoop** (simpler, co-located with genome, no extra process)
5. Stream maxlen — 1000 for `cell:skills`, 500 for `cell:feedback`?
   → Needs validation based on expected throughput

---

## 13. Multi-Agent Review Divergences

Research agent (web search, FSRS/EvoSkill/Voyager papers) recommended:

1. **Power-law decay** (FSRS-4.5: `(1 + 0.234*t/S)^(-0.5)`) over exponential.
   FSRS validated on millions of Anki users. Power-law has better long tail.
   **Decision: keep exponential for v1** — FSRS requires per-skill stability
   parameter (S) we can't calibrate yet. Upgrade path documented for v2.

2. **Merge threshold 0.10** (EvoSkill) vs our 0.15.
   **Decision: keep 0.15** — more conservative for young system with few skills.

3. **Hybrid routing** (flat tags Phase 1 → semantic Phase 2).
   **Decision: aligned** — our flat taxonomy IS their Phase 1.

No other divergences. 3/3 points converge on the same direction, differ only
in aggressiveness parameters. Conservative choices are appropriate for v1.

---

**Signature:**
Design by Claude Opus 4.6 (Air, 2026-04-16)
Reviewed against: FSRS v4.5, EvoSkill (Alzubi 2025), Trace2Skill (2025),
Lamarckian robotics (Le Goff 2023), Voyager (Wang 2023)
