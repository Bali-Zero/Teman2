# Self-Evolving Organism — Implementation Plan v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Review history:** v1 reviewed by Gemini 2.5 Pro (2026-04-09). 7/9 critiques accepted. Key changes: eliminated redundant skills.py (unified into SQLite KB), switched reflection parsing from regex to JSON, removed process_score vanity metric, added KB singleton, added integration test, added token budget for prompt injection.

**Goal:** Transform Mata Garuda from a static scraper into a self-evolving organism that learns from both success and failure, accumulates knowledge, and grows smarter with every cycle.

**Architecture:** Two new runtime modules (reflection, knowledge) plug into the existing Lamarckian loop. Every agent run triggers a post-run reflection via `claude --print` with JSON output. Reflections, skills, and facts all live in a single SQLite KB (stdlib, zero deps). The fitness tracker expands from binary to include tokens_used and duration_ms. Recent reflections are injected into the next run's prompt with a token budget cap.

**Tech Stack:** Python stdlib (sqlite3, json, pathlib), pydantic (existing), pytest (existing), `claude --print` via existing CLIRuntime subprocess

**Constraints:**
- Zero new dependencies (sqlite3 is stdlib)
- CLI-only: all LLM calls via subprocess `claude --print`
- OSINT blindato: all data stays local
- Existing 105 tests must keep passing
- GENOME mutation still requires Zero review for strategic changes
- Technical auto-mutations (regex, timeout) can auto-apply if pytest passes

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `mata_garuda/runtime/reflection.py` | Post-run reflection engine: builds prompt, parses JSON output, saves to KB |
| `mata_garuda/runtime/knowledge.py` | SQLite knowledge base: CRUD, FTS5 search, decay. Single source of truth for ALL knowledge (facts, insights, skills) |
| `mata_garuda/tools/knowledge_tools.py` | Agent-facing tools: `kb_search`, `kb_store`, `kb_get_skill` |
| `tests/test_knowledge.py` | Tests for knowledge base |
| `tests/test_reflection.py` | Tests for reflection engine |
| `tests/test_organism_integration.py` | End-to-end integration test: run → reflect → store → inject |

### Modified files
| File | Change |
|------|--------|
| `mata_garuda/runtime/lamarckian.py` | Hook reflection after every run (success AND failure), inject recent reflections into prompt with token budget |
| `mata_garuda/runtime/fitness.py` | Add tokens_used and duration_ms to `record_run()` |
| `mata_garuda/types.py` | Add `RunOutcome` model for richer fitness data |
| `mata_garuda/agents/regulation_watcher.py` | Wire knowledge tools into agent functions list |

### Eliminated (per Gemini review)
| File | Why removed |
|------|------------|
| ~~`mata_garuda/runtime/skills.py`~~ | Redundant — skills are `type='skill'` entries in SQLite KB. One source of truth. |
| ~~`tests/test_skills.py`~~ | No longer needed |

### Unchanged files (verify compatibility)
| File | Why |
|------|-----|
| `mata_garuda/registry.py` | No changes needed — decorator pattern handles new tools |
| `mata_garuda/runtime/loop.py` | No changes — reflection hooks at Lamarckian level |
| `mata_garuda/runtime/genome.py` | No changes — mutation system stays as-is |
| `mata_garuda/security/path_firewall.py` | No changes — SQLite path is within allowed dirs |

---

## Design Decisions (from review)

### D1: No separate skills.py — unified KB
Skills are `type='skill'` rows in the knowledge table. `kb_get_skill` queries `WHERE type='skill' AND content MATCH ?`. One source of truth, no filesystem/DB divergence.

### D2: JSON reflection output, not regex parsing
The reflection prompt instructs Claude to output a ```json block. Parser extracts and `json.loads()` it. Fallback: save raw text if JSON fails. This is robust to formatting changes.

### D3: No process_score — only measurable metrics
Removed the LLM-rated 1-10 score (noisy, non-reproducible). Keep only: `tokens_used`, `duration_ms`, `success`. Efficiency = tokens/ms, computed post-hoc.

### D4: KB singleton per run
`KnowledgeBase` instance is passed through `context_variables` during a run. No new connection per tool call.

### D5: Token budget for reflection injection
Max 2000 chars of reflection context injected into prompt. Truncate oldest reflections first.

### D6: Confidence decay on access
Entries that get retrieved but lead to failed runs have their confidence decremented. Prevents self-reinforcing wrong beliefs.

---

## Task 1: RunOutcome model in types.py

Extend fitness tracking from binary success/fail to measurable metrics.

**Files:**
- Modify: `mata_garuda/types.py`
- Test: `tests/test_registry.py` (add to existing)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_registry.py`:

```python
def test_run_outcome_model():
    from mata_garuda.types import RunOutcome

    outcome = RunOutcome(
        agent_name="Regulation Watcher",
        success=True,
        tokens_used=1500,
        duration_ms=4200,
    )
    assert outcome.success is True
    assert outcome.tokens_used == 1500
    assert outcome.efficiency == pytest.approx(1500 / 4200, rel=0.01)


def test_run_outcome_defaults():
    from mata_garuda.types import RunOutcome

    outcome = RunOutcome(agent_name="test", success=False)
    assert outcome.tokens_used is None
    assert outcome.duration_ms is None
    assert outcome.efficiency is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_registry.py::test_run_outcome_model -v`
Expected: FAIL with `ImportError: cannot import name 'RunOutcome'`

- [ ] **Step 3: Write minimal implementation**

Add to `mata_garuda/types.py` after the `Result` class:

```python
class RunOutcome(BaseModel):
    """Rich outcome of a single agent run, for multi-dimensional fitness."""

    agent_name: str
    success: bool
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None

    @property
    def efficiency(self) -> Optional[float]:
        """Tokens per millisecond — lower is more efficient."""
        if self.tokens_used and self.duration_ms and self.duration_ms > 0:
            return self.tokens_used / self.duration_ms
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_registry.py -v`
Expected: All existing tests PASS + 2 new tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/mata-garuda
git add mata_garuda/types.py tests/test_registry.py
git commit -m "feat: add RunOutcome model for multi-dimensional fitness"
```

---

## Task 2: SQLite Knowledge Base (unified — facts, insights, skills)

The single source of truth for ALL organism knowledge. No separate skill files.

**Files:**
- Create: `mata_garuda/runtime/knowledge.py`
- Create: `tests/test_knowledge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_knowledge.py`:

```python
"""Tests for SQLite knowledge base — unified store for facts, insights, skills."""
import pytest
from pathlib import Path


@pytest.fixture
def kb(tmp_path):
    from mata_garuda.runtime.knowledge import KnowledgeBase
    return KnowledgeBase(db_path=tmp_path / "test_kb.db")


class TestKnowledgeBase:
    def test_init_creates_tables(self, kb):
        """DB and tables should exist after init."""
        assert kb.db_path.exists()
        rows = kb.search("nonexistent")
        assert rows == []

    def test_store_and_retrieve(self, kb):
        """Store a fact and retrieve it by search."""
        kb.store(
            agent="Regulation Watcher",
            entry_type="fact",
            content="Perpres 31/2025 changes investment rules for PMA",
            source="peraturan.go.id",
            confidence=0.9,
        )
        results = kb.search("investment PMA")
        assert len(results) == 1
        assert "Perpres 31/2025" in results[0]["content"]
        assert results[0]["agent"] == "Regulation Watcher"

    def test_store_multiple_and_fts(self, kb):
        """FTS5 search should rank by relevance."""
        kb.store("agent1", "fact", "Tax regulation PMK 25/2025", "source1", 0.8)
        kb.store("agent1", "fact", "Immigration visa B211 abolished", "source2", 0.9)
        kb.store("agent1", "fact", "Tax PMK 30/2025 new brackets", "source1", 0.7)

        results = kb.search("tax PMK")
        assert len(results) == 2
        assert all("PMK" in r["content"] or "Tax" in r["content"] for r in results)

    def test_store_increments_accessed_count(self, kb):
        """Accessing an entry should increment its accessed_count."""
        kb.store("agent1", "fact", "Test content", "source", 0.5)
        results = kb.search("Test content")
        assert results[0]["accessed_count"] == 0

        kb.touch(results[0]["id"])
        results2 = kb.search("Test content")
        assert results2[0]["accessed_count"] == 1

    def test_decay_removes_stale(self, kb):
        """Entries with zero access and old age should be decayed."""
        kb.store("agent1", "fact", "Old unused fact", "source", 0.3)
        kb._execute(
            "UPDATE knowledge SET created_at = datetime('now', '-60 days') WHERE id = 1"
        )
        removed = kb.decay(max_age_days=30, min_access=1)
        assert removed == 1
        assert kb.search("Old unused fact") == []

    def test_stats(self, kb):
        """Stats should return counts by type."""
        kb.store("a", "fact", "f1", "s", 0.5)
        kb.store("a", "skill", "s1", "s", 0.8)
        kb.store("a", "fact", "f2", "s", 0.6)
        stats = kb.stats()
        assert stats["fact"] == 2
        assert stats["skill"] == 1
        assert stats["total"] == 3

    def test_skill_stored_and_retrieved_as_type(self, kb):
        """Skills are just type='skill' entries — no separate store."""
        kb.store("Regulation Watcher", "skill",
                 "Always check HTTP status before scraping: curl -sI $URL, verify 200",
                 "reflection_20260409", 0.9)
        skills = kb.get_by_type("skill")
        assert len(skills) == 1
        assert "check HTTP status" in skills[0]["content"]

    def test_decrement_confidence(self, kb):
        """Confidence should decrease when an entry leads to failure."""
        kb.store("agent1", "insight", "Source X is always down", "reflection", 0.8)
        results = kb.search("Source X")
        kb.decrement_confidence(results[0]["id"], amount=0.2)
        results2 = kb.search("Source X")
        assert results2[0]["confidence"] == pytest.approx(0.6, rel=0.01)

    def test_decrement_confidence_floors_at_zero(self, kb):
        """Confidence cannot go below 0."""
        kb.store("agent1", "fact", "Test", "src", 0.1)
        results = kb.search("Test")
        kb.decrement_confidence(results[0]["id"], amount=0.5)
        results2 = kb.search("Test")
        assert results2[0]["confidence"] >= 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_knowledge.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `mata_garuda/runtime/knowledge.py`:

```python
"""
Mata Garuda — SQLite Knowledge Base.

Unified store for ALL organism knowledge: facts, insights, patterns, skills.
Uses SQLite FTS5 for full-text search (stdlib, zero dependencies).

Design decision: skills are type='skill' rows, NOT separate files.
This was a key review finding — one source of truth prevents divergence.

Storage: data/knowledge.db (gitignored)
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mata_garuda.runtime")

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "knowledge.db"


class KnowledgeBase:
    """SQLite-backed knowledge base with FTS5 full-text search."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                confidence REAL DEFAULT 0.5,
                created_at TEXT DEFAULT (datetime('now')),
                accessed_count INTEGER DEFAULT 0,
                last_accessed TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(content, source, content='knowledge', content_rowid='id');
            CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                INSERT INTO knowledge_fts(rowid, content, source)
                VALUES (new.id, new.content, new.source);
            END;
            CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, content, source)
                VALUES ('delete', old.id, old.content, old.source);
            END;
        """)
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cursor = self._conn.execute(sql, params)
        self._conn.commit()
        return cursor

    def store(
        self,
        agent: str,
        entry_type: str,
        content: str,
        source: str,
        confidence: float = 0.5,
    ) -> int:
        """Store a knowledge entry. Returns the row id."""
        cursor = self._execute(
            "INSERT INTO knowledge (agent, type, content, source, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (agent, entry_type, content, source, confidence),
        )
        logger.info(f"[kb] Stored {entry_type} from {agent}: {content[:60]}...")
        return cursor.lastrowid

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search over knowledge entries."""
        try:
            cursor = self._conn.execute(
                "SELECT k.* FROM knowledge k "
                "JOIN knowledge_fts fts ON k.id = fts.rowid "
                "WHERE knowledge_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (query, limit),
            )
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in cursor.fetchall()]

    def get_by_type(self, entry_type: str, limit: int = 50) -> list[dict]:
        """Get all entries of a specific type (e.g., 'skill')."""
        cursor = self._conn.execute(
            "SELECT * FROM knowledge WHERE type = ? ORDER BY confidence DESC LIMIT ?",
            (entry_type, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def touch(self, entry_id: int) -> None:
        """Increment accessed_count for an entry."""
        self._execute(
            "UPDATE knowledge SET accessed_count = accessed_count + 1, "
            "last_accessed = datetime('now') WHERE id = ?",
            (entry_id,),
        )

    def decrement_confidence(self, entry_id: int, amount: float = 0.1) -> None:
        """Decrease confidence when an entry led to a failed outcome."""
        self._execute(
            "UPDATE knowledge SET confidence = MAX(0.0, confidence - ?) WHERE id = ?",
            (amount, entry_id),
        )

    def decay(self, max_age_days: int = 30, min_access: int = 1) -> int:
        """Remove stale entries: old + never accessed. Returns count removed."""
        cursor = self._execute(
            "DELETE FROM knowledge WHERE accessed_count < ? "
            "AND created_at < datetime('now', ?)",
            (min_access, f"-{max_age_days} days"),
        )
        removed = cursor.rowcount
        if removed > 0:
            logger.info(f"[kb] Decayed {removed} stale entries")
        return removed

    def stats(self) -> dict:
        """Return counts by type."""
        cursor = self._conn.execute(
            "SELECT type, COUNT(*) as cnt FROM knowledge GROUP BY type"
        )
        result = {row["type"]: row["cnt"] for row in cursor.fetchall()}
        result["total"] = sum(result.values())
        return result

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_knowledge.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Add `data/` to .gitignore**

Append to `.gitignore`:
```
data/
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/mata-garuda
git add mata_garuda/runtime/knowledge.py tests/test_knowledge.py .gitignore
git commit -m "feat: add unified SQLite knowledge base with FTS5 and confidence decay"
```

---

## Task 3: Reflection Engine (JSON output, not regex)

After every run, `claude --print` analyzes what happened and produces a JSON reflection. Reflections are stored in the KB.

**Files:**
- Create: `mata_garuda/runtime/reflection.py`
- Create: `tests/test_reflection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reflection.py`:

```python
"""Tests for reflection engine — JSON-based, not regex."""
import pytest
import json
from pathlib import Path


class TestReflectionPrompt:
    def test_build_reflection_prompt_success(self):
        from mata_garuda.runtime.reflection import build_reflection_prompt

        prompt = build_reflection_prompt(
            agent_name="Regulation Watcher",
            query="check latest regulations",
            outcome_success=True,
            messages_summary="Scraped 10 regs, published to garuda:raw",
            genome_snippet="Primary source: peraturan.go.id",
        )
        assert "Regulation Watcher" in prompt
        assert "SUCCESS" in prompt
        assert "```json" in prompt  # Must instruct JSON output

    def test_build_reflection_prompt_failure(self):
        from mata_garuda.runtime.reflection import build_reflection_prompt

        prompt = build_reflection_prompt(
            agent_name="Regulation Watcher",
            query="check latest regulations",
            outcome_success=False,
            messages_summary="Source unreachable, HTTP 503",
            genome_snippet="Primary source: peraturan.go.id",
        )
        assert "FAILURE" in prompt
        assert "```json" in prompt


class TestParseReflection:
    def test_parse_json_reflection(self):
        from mata_garuda.runtime.reflection import parse_reflection

        raw = '''Here is my reflection:

```json
{
    "what_worked": "Fast source check",
    "what_didnt": "Nothing",
    "skill": "Check source availability before scraping",
    "insight": "peraturan.go.id responds fastest at 06:00 WITA"
}
```

That's my analysis.'''

        parsed = parse_reflection(raw)
        assert parsed["what_worked"] == "Fast source check"
        assert parsed["skill"] == "Check source availability before scraping"
        assert parsed["insight"] == "peraturan.go.id responds fastest at 06:00 WITA"

    def test_parse_fallback_on_bad_json(self):
        from mata_garuda.runtime.reflection import parse_reflection

        raw = "The run was successful. All 10 regulations published."
        parsed = parse_reflection(raw)
        assert parsed["raw"] == raw
        assert "what_worked" not in parsed

    def test_parse_json_without_fence(self):
        from mata_garuda.runtime.reflection import parse_reflection

        raw = '{"what_worked": "everything", "insight": "test"}'
        parsed = parse_reflection(raw)
        assert parsed["what_worked"] == "everything"


class TestReflectionStorage:
    def test_store_reflection_in_kb(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import store_reflection_in_kb

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        parsed = {
            "what_worked": "Fast scraping",
            "insight": "06:00 is best time",
            "skill": "Check HTTP before scraping",
        }
        ids = store_reflection_in_kb(kb, "Regulation Watcher", parsed)
        assert len(ids) >= 2  # insight + skill at minimum

        skills = kb.get_by_type("skill")
        assert len(skills) == 1
        assert "Check HTTP" in skills[0]["content"]

        insights = kb.get_by_type("insight")
        assert len(insights) == 1
        kb.close()


class TestGetRecentReflections:
    def test_returns_latest_n_from_kb(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import get_recent_reflections

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        for i in range(5):
            kb.store("test_agent", "reflection", f"Reflection {i}", "run", 0.7)
        recent = get_recent_reflections(kb, "test_agent", n=3)
        assert len(recent) == 3
        kb.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_reflection.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `mata_garuda/runtime/reflection.py`:

```python
"""
Mata Garuda — Reflection Engine.

After every run (success OR failure), generates a structured JSON reflection
via claude --print. Reflections are stored in the unified SQLite KB.

Design: JSON output (not regex) per Gemini review — robust to formatting changes.
Pattern: Reflexion (Shinn 2023) + RKC (Tanaike 2026)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.runtime")

# Max chars of reflection context to inject into prompt (token budget)
MAX_REFLECTION_CHARS = 2000


def build_reflection_prompt(
    agent_name: str,
    query: str,
    outcome_success: bool,
    messages_summary: str,
    genome_snippet: str,
) -> str:
    """Build the prompt for claude --print to generate a JSON reflection."""
    status = "SUCCESS" if outcome_success else "FAILURE"
    focus = (
        "What worked well? What pattern should be repeated? What reusable skill emerged?"
        if outcome_success
        else "What was the root cause? What should the agent do differently? What constraint was violated?"
    )
    return f"""You are the reflection engine for agent "{agent_name}".

The agent just completed a run with outcome: {status}

Query: {query}
Run summary: {messages_summary}
GENOME constraints: {genome_snippet}

Produce a structured reflection as a JSON object inside a ```json fence.
Focus: {focus}

```json
{{
    "what_worked": "one sentence — what went well",
    "what_didnt": "one sentence — what failed or was inefficient",
    "skill": "one reusable procedure extracted from this run, or null",
    "insight": "one non-obvious insight useful for future runs, or null"
}}
```

Output ONLY the JSON block. No other text."""


def parse_reflection(raw: str) -> dict:
    """Parse a JSON reflection from claude output. Fallback to raw text."""
    # Try to extract ```json ... ``` block
    fence_match = re.search(r"```json\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    json_str = fence_match.group(1) if fence_match else raw.strip()

    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    return {"raw": raw}


def store_reflection_in_kb(
    kb: KnowledgeBase,
    agent_name: str,
    parsed: dict,
) -> list[int]:
    """Store parsed reflection fields in the KB. Returns list of row IDs."""
    ids = []
    source = f"reflection_{agent_name}"

    if "insight" in parsed and parsed["insight"]:
        row_id = kb.store(agent_name, "insight", parsed["insight"], source, 0.7)
        ids.append(row_id)

    if "skill" in parsed and parsed["skill"]:
        row_id = kb.store(agent_name, "skill", parsed["skill"], source, 0.8)
        ids.append(row_id)

    # Store full reflection as type='reflection' for history
    full_text = json.dumps(parsed, ensure_ascii=False) if "raw" not in parsed else parsed["raw"]
    row_id = kb.store(agent_name, "reflection", full_text, source, 0.5)
    ids.append(row_id)

    return ids


def get_recent_reflections(
    kb: KnowledgeBase,
    agent_name: str,
    n: int = 5,
) -> list[str]:
    """Get the N most recent reflections for an agent from the KB."""
    cursor = kb._conn.execute(
        "SELECT content FROM knowledge WHERE agent = ? AND type = 'reflection' "
        "ORDER BY created_at DESC LIMIT ?",
        (agent_name, n),
    )
    return [row["content"] for row in cursor.fetchall()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_reflection.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/mata-garuda
git add mata_garuda/runtime/reflection.py tests/test_reflection.py
git commit -m "feat: add JSON-based reflection engine with KB storage"
```

---

## Task 4: Knowledge Tools for Agents

Agent-facing tools. KB singleton passed via context_variables.

**Files:**
- Create: `mata_garuda/tools/knowledge_tools.py`
- Modify: `mata_garuda/agents/regulation_watcher.py`
- Test: `tests/test_sprint4.py` (add registration test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sprint4.py`:

```python
class TestKnowledgeTools:
    def test_tools_registered(self):
        from mata_garuda.tools.knowledge_tools import kb_search, kb_store, kb_get_skill
        from mata_garuda.registry import registry

        assert "kb_search" in registry.tools
        assert "kb_store" in registry.tools
        assert "kb_get_skill" in registry.tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_sprint4.py::TestKnowledgeTools -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `mata_garuda/tools/knowledge_tools.py`:

```python
"""
Mata Garuda — Knowledge Tools for agents.

These tools let agents query and store knowledge during runs.
KB instance is passed via context_variables['kb'] (singleton per run).
If not available, creates a default instance.
"""
from __future__ import annotations

import json

from mata_garuda.registry import register_tool
from mata_garuda.runtime.knowledge import KnowledgeBase


def _get_kb(context_variables: dict | None) -> KnowledgeBase:
    """Get KB from context or create default."""
    ctx = context_variables or {}
    if "kb" in ctx:
        return ctx["kb"]
    return KnowledgeBase()


@register_tool(name="kb_search")
def kb_search(query: str, limit: int = 5, context_variables: dict | None = None) -> str:
    """Search the knowledge base for relevant facts, insights, or skills.

    Args:
        query: Search query (full-text)
        limit: Max results (default 5)
    """
    kb = _get_kb(context_variables)
    results = kb.search(query, limit=limit)

    if not results:
        return json.dumps({"results": [], "message": "No matching knowledge found."})

    for r in results:
        kb.touch(r["id"])

    return json.dumps({"results": [
        {"id": r["id"], "type": r["type"], "content": r["content"],
         "confidence": r["confidence"]}
        for r in results
    ]})


@register_tool(name="kb_store")
def kb_store(
    entry_type: str,
    content: str,
    source: str,
    confidence: float = 0.7,
    context_variables: dict | None = None,
) -> str:
    """Store a new fact, insight, or skill in the knowledge base.

    Args:
        entry_type: One of: fact, insight, pattern, skill
        content: The knowledge content
        source: Where this knowledge came from
        confidence: How confident (0.0-1.0)
    """
    agent_name = (context_variables or {}).get("agent_name", "unknown")
    kb = _get_kb(context_variables)
    row_id = kb.store(agent=agent_name, entry_type=entry_type, content=content,
                       source=source, confidence=confidence)
    return json.dumps({"stored": True, "id": row_id})


@register_tool(name="kb_get_skill")
def kb_get_skill(query: str, context_variables: dict | None = None) -> str:
    """Search for a reusable skill in the knowledge base.

    Args:
        query: What kind of skill you need
    """
    kb = _get_kb(context_variables)
    skills = kb.get_by_type("skill")

    if not skills:
        return json.dumps({"skills": [], "message": "No skills stored yet."})

    # Simple relevance: check if query words appear in content
    query_lower = query.lower()
    matching = [s for s in skills if any(w in s["content"].lower() for w in query_lower.split())]

    if not matching:
        matching = skills[:3]  # Return top 3 by confidence

    return json.dumps({"skills": [
        {"content": s["content"], "confidence": s["confidence"], "agent": s["agent"]}
        for s in matching[:5]
    ]})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_sprint4.py::TestKnowledgeTools -v`
Expected: PASS

- [ ] **Step 5: Wire tools into Regulation Watcher**

In `mata_garuda/agents/regulation_watcher.py`, add import:

```python
from mata_garuda.tools.knowledge_tools import kb_search, kb_store, kb_get_skill
```

Add to the `functions` list:

```python
        functions=[
            check_regulation_source,
            scrape_regulations,
            scrape_regulation_detail,
            stream_publish,
            stream_length,
            stream_info,
            kb_search,
            kb_store,
            kb_get_skill,
            case_resolved,
            case_not_resolved,
        ],
```

- [ ] **Step 6: Run ALL tests**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/mata-garuda
git add mata_garuda/tools/knowledge_tools.py mata_garuda/agents/regulation_watcher.py tests/test_sprint4.py
git commit -m "feat: add KB tools for agents with singleton pattern"
```

---

## Task 5: Hook Reflection into Lamarckian Loop + Prompt Injection

Wire reflection after every run AND inject recent reflections into new runs with token budget.

**Files:**
- Modify: `mata_garuda/runtime/lamarckian.py`
- Test: `tests/test_lamarckian.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lamarckian.py`:

```python
class TestReflectionHook:
    def test_reflection_called_on_success(self, monkeypatch):
        """Reflection should fire after a successful run."""
        from mata_garuda.runtime.lamarckian import run_with_lamarckian_feedback
        from mata_garuda.types import Agent, Response

        reflections_called = []

        def mock_generate(agent_name, query, success, messages, genome, kb):
            reflections_called.append({"agent": agent_name, "success": success})

        monkeypatch.setattr(
            "mata_garuda.runtime.lamarckian.generate_and_save_reflection",
            mock_generate,
        )

        def mock_loop(agent, query, context_variables=None):
            return Response(
                messages=[{"role": "assistant", "content": "Case resolved. The result is: done"}]
            )

        monkeypatch.setattr("mata_garuda.runtime.lamarckian.run_agent_loop", mock_loop)
        monkeypatch.setattr("mata_garuda.runtime.lamarckian.record_run", lambda *a, **kw: None)
        monkeypatch.setattr("mata_garuda.runtime.lamarckian.get_mutation_version", lambda _: 0)
        monkeypatch.setattr("mata_garuda.runtime.lamarckian.check_and_auto_revert", lambda _: False)

        agent = Agent(name="Test", model="claude")
        run_with_lamarckian_feedback(agent=agent, query="test query")

        assert len(reflections_called) == 1
        assert reflections_called[0]["success"] is True


class TestPromptInjection:
    def test_enriched_query_has_reflections(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.lamarckian import _build_enriched_query

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        kb.store("Test", "reflection", "Previous insight: check source first", "run", 0.7)

        enriched = _build_enriched_query("Test", "check regulations", kb)
        assert "check regulations" in enriched
        assert "Previous insight" in enriched
        assert "PAST REFLECTIONS" in enriched
        kb.close()

    def test_enriched_query_respects_token_budget(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.lamarckian import _build_enriched_query

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        # Store a very long reflection
        kb.store("Test", "reflection", "x" * 5000, "run", 0.7)

        enriched = _build_enriched_query("Test", "query", kb, max_chars=500)
        # The reflection context should be truncated
        reflection_part = enriched.split("PAST REFLECTIONS")[1] if "PAST REFLECTIONS" in enriched else ""
        assert len(reflection_part) <= 600  # 500 + header overhead
        kb.close()

    def test_enriched_query_no_reflections(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.lamarckian import _build_enriched_query

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        enriched = _build_enriched_query("Test", "query", kb)
        assert enriched == "query"
        assert "PAST REFLECTIONS" not in enriched
        kb.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_lamarckian.py::TestReflectionHook tests/test_lamarckian.py::TestPromptInjection -v`
Expected: FAIL

- [ ] **Step 3: Modify lamarckian.py**

Add imports at top of `mata_garuda/runtime/lamarckian.py`:

```python
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.runtime.reflection import (
    build_reflection_prompt,
    parse_reflection,
    store_reflection_in_kb,
    get_recent_reflections,
    MAX_REFLECTION_CHARS,
)
```

Add helper functions after `_parse_case_status`:

```python
def _build_enriched_query(
    agent_name: str,
    query: str,
    kb: KnowledgeBase,
    n_reflections: int = 3,
    max_chars: int = MAX_REFLECTION_CHARS,
) -> str:
    """Enrich the query with recent reflections, respecting token budget."""
    reflections = get_recent_reflections(kb, agent_name, n=n_reflections)
    if not reflections:
        return query

    # Build reflection block within budget
    block_parts = []
    chars_used = 0
    for r in reflections:
        if chars_used + len(r) > max_chars:
            remaining = max_chars - chars_used
            if remaining > 50:
                block_parts.append(r[:remaining] + "...")
            break
        block_parts.append(r)
        chars_used += len(r)

    if not block_parts:
        return query

    reflection_block = "\n---\n".join(block_parts)
    return (
        f"{query}\n\n"
        f"[PAST REFLECTIONS — learn from these]\n"
        f"{reflection_block}"
    )


def generate_and_save_reflection(
    agent_name: str,
    query: str,
    success: bool,
    messages: list[dict],
    genome: str,
    kb: KnowledgeBase,
) -> None:
    """Generate reflection via claude --print and store in KB."""
    messages_summary = ""
    for msg in messages[-5:]:
        role = msg.get("role", "?")
        content = msg.get("content", "")[:200]
        messages_summary += f"[{role}] {content}\n"

    prompt = build_reflection_prompt(
        agent_name=agent_name,
        query=query,
        outcome_success=success,
        messages_summary=messages_summary,
        genome_snippet=genome[:500] if genome else "N/A",
    )

    try:
        runtime = CLIRuntime(model="claude")
        result = runtime.invoke(
            prompt=prompt,
            system_prompt="Output ONLY a JSON block inside ```json fences. No other text.",
        )
        if result.success:
            parsed = parse_reflection(result.output)
            store_reflection_in_kb(kb, agent_name, parsed)
        else:
            logger.warning(f"[reflection] CLI failed: {result.stderr[:100]}")
    except Exception as e:
        logger.warning(f"[reflection] Generation failed: {e}")
```

In `run_with_lamarckian_feedback`, add KB init at the start:

```python
    kb = KnowledgeBase()
```

Replace initial query enrichment:

```python
        else:
            current_query = _build_enriched_query(agent.name, query, kb)
```

After success (line ~144), add reflection:

```python
            genome = read_genome(agent.name)
            generate_and_save_reflection(agent.name, query, True, all_messages, genome, kb)
```

After failure (line ~160), add reflection:

```python
            genome = read_genome(agent.name)
            generate_and_save_reflection(agent.name, query, False, all_messages, genome, kb)
```

At end of function, before return, close KB:

```python
    kb.close()
```

- [ ] **Step 4: Run ALL tests**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/ -v`
Expected: All tests PASS (105 existing + all new)

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/mata-garuda
git add mata_garuda/runtime/lamarckian.py tests/test_lamarckian.py
git commit -m "feat: hook reflection into Lamarckian with prompt injection and token budget"
```

---

## Task 6: Integration Test

End-to-end test proving the learning loop works: run → reflect → store → inject into next run.

**Files:**
- Create: `tests/test_organism_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_organism_integration.py`:

```python
"""Integration test: the full learning loop.

Verifies: run → reflect → store in KB → inject into next run's prompt.
This catches failures in parsing, storage, or injection that unit tests miss.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch


class TestLearningLoop:
    def test_reflection_flows_to_next_run(self, tmp_path):
        """A reflection from run 1 should appear in run 2's enriched query."""
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import (
            parse_reflection,
            store_reflection_in_kb,
        )
        from mata_garuda.runtime.lamarckian import _build_enriched_query

        kb = KnowledgeBase(db_path=tmp_path / "test.db")

        # Simulate run 1 reflection output from claude
        claude_output = '''```json
{
    "what_worked": "Fast scraping of peraturan.go.id",
    "what_didnt": "Redundant stream_length check",
    "skill": "Always verify HTTP 200 before scraping",
    "insight": "peraturan.go.id updates at 05:00 WITA"
}
```'''
        # Parse and store
        parsed = parse_reflection(claude_output)
        assert "what_worked" in parsed
        assert parsed["skill"] == "Always verify HTTP 200 before scraping"

        ids = store_reflection_in_kb(kb, "Regulation Watcher", parsed)
        assert len(ids) >= 2  # insight + skill + reflection

        # Verify KB has the data
        skills = kb.get_by_type("skill")
        assert len(skills) == 1
        insights = kb.get_by_type("insight")
        assert len(insights) == 1

        # Simulate run 2: enriched query should contain the reflection
        enriched = _build_enriched_query("Regulation Watcher", "check regulations", kb)
        assert "PAST REFLECTIONS" in enriched
        # The reflection content should be in the enriched query
        assert "peraturan.go.id" in enriched or "HTTP 200" in enriched

        kb.close()

    def test_bad_reflection_does_not_poison_kb(self, tmp_path):
        """If claude returns garbage, KB should get raw text, not crash."""
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import (
            parse_reflection,
            store_reflection_in_kb,
        )

        kb = KnowledgeBase(db_path=tmp_path / "test.db")

        # Garbage output
        parsed = parse_reflection("I don't know what happened lol")
        assert "raw" in parsed
        assert "what_worked" not in parsed

        ids = store_reflection_in_kb(kb, "Broken Agent", parsed)
        assert len(ids) == 1  # Only the raw reflection, no insight/skill

        # KB should have 1 entry, type='reflection'
        stats = kb.stats()
        assert stats.get("skill", 0) == 0
        assert stats.get("insight", 0) == 0
        assert stats["reflection"] == 1

        kb.close()
```

- [ ] **Step 2: Run test**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/test_organism_integration.py -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/mata-garuda
git add tests/test_organism_integration.py
git commit -m "test: add integration test for learning loop (reflect → KB → inject)"
```

---

## Task 7: Update CLAUDE.md and full verification

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.gitignore`

- [ ] **Step 1: Add section to CLAUDE.md**

Add after section 6 (Cron):

```markdown
## 6.5 Self-Evolving Organism (Sprint 5)

### Reflection Engine (`runtime/reflection.py`)
- Every run (success AND failure) triggers `claude --print` JSON reflection
- Reflections stored in SQLite KB (type='reflection', 'insight', 'skill')
- Recent reflections injected into next run's prompt (2000 char budget)
- Pattern: Reflexion (Shinn 2023)

### Knowledge Base (`runtime/knowledge.py`)
- SQLite with FTS5 in `data/knowledge.db` (gitignored)
- Unified store for ALL knowledge: facts, insights, skills, reflections
- No separate skill files — skills are `type='skill'` rows
- Confidence decay on entries that lead to failures
- Stale entries (30 days, 0 access) auto-decayed
- Agents access via `kb_search`, `kb_store`, `kb_get_skill` tools

### How the organism learns
1. Agent runs → case_resolved or case_not_resolved
2. `claude --print` generates JSON reflection
3. Reflection parsed → insight and skill extracted → stored in KB
4. Next run: recent reflections injected into prompt
5. Agent uses KB tools to query accumulated knowledge
6. Failed insights get confidence decremented → eventually decay
```

- [ ] **Step 2: Verify .gitignore**

Ensure `.gitignore` contains:
```
data/
```

- [ ] **Step 3: Run FULL test suite**

Run: `cd ~/Desktop/mata-garuda && .venv/bin/pytest tests/ -v`
Expected: All tests PASS (105 existing + ~20 new = ~125 total)

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/mata-garuda
git add CLAUDE.md .gitignore
git commit -m "docs: add self-evolving organism section to CLAUDE.md"
```

---

## Summary

| Task | What it builds | New tests | Depends on |
|------|---------------|-----------|------------|
| 1 | RunOutcome model | 2 | — |
| 2 | SQLite Knowledge Base (unified) | 9 | — |
| 3 | Reflection Engine (JSON-based) | 7 | 2 |
| 4 | Knowledge tools for agents | 1 | 2 |
| 5 | Hook reflection + prompt injection | 4 | 2, 3 |
| 6 | Integration test | 2 | 2, 3, 5 |
| 7 | Docs + verification | 0 | All |

**Tasks 1-2 are independent and can run in parallel.**
**Task 3 depends on 2 (KB for storage).**
**Task 4 depends on 2.**
**Task 5 depends on 2, 3.**
**Task 6 depends on 2, 3, 5.**
**Task 7 is final verification.**

Total: ~25 new tests, 5 new files, 3 modified files, zero new dependencies.

---

## Review Fixes Applied (from Gemini 2.5 Pro review)

| Gemini critique | Action taken |
|----------------|-------------|
| skills.py is redundant — two sources of truth | **FIXED:** Eliminated skills.py. Skills are `type='skill'` in KB |
| parse_reflection regex is brittle | **FIXED:** JSON output with ```json fence + json.loads() fallback |
| No knowledge consolidation | **ACKNOWLEDGED:** Deferred to Sprint 6 (requires careful design) |
| No skill validation | **PARTIALLY FIXED:** Skills stored with confidence, decayable. Full validation deferred |
| No token budget for reflection injection | **FIXED:** MAX_REFLECTION_CHARS = 2000, truncation logic |
| Recursive self-delusion risk | **FIXED:** `decrement_confidence()` on entries that lead to failures |
| process_score is noise | **FIXED:** Removed. Only tokens_used/duration_ms |
| No integration test | **FIXED:** Task 6 added |
| DB contention | **FIXED:** KB singleton via context_variables, not new connection per call |
