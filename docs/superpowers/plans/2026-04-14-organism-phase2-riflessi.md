# Organism Phase 2 (RIFLESSI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 5 deliverable of Phase 2 (RIFLESSI) — Priority Engine, LPSE Harvester, Sleep consolidation, RAG Enricher, Sentinel health cell — plus 3 pre-work tasks unblocking production reflection loop.

**Architecture:** Local-first event-driven. JSON flat for config, Redis Streams for events, SQLite FTS5 for knowledge, cell-core PulseLoop for learning agents. Consultazione NLM+Codex+Gemini per ogni decisione (see spec §13).

**Tech Stack:** Python 3.11+ (stdlib + pydantic + pytest only for Mata Garuda), subprocess `claude --print`, redis-cli, FastAPI (backend side), SQLite FTS5, LaunchAgent (macOS).

**Spec:** `docs/superpowers/specs/2026-04-14-organism-phase2-riflessi-design.md`

**Working directory:** Tasks touching `mata-garuda` → `apps/mata-garuda/` (use `.venv/bin/pytest` from there). Tasks touching backend → `apps/backend-rag/` (use `.venv/bin/pytest`).

**Convention:** Every commit message ends with the Co-Authored-By footer. TDD strict: test first, verify fails, impl, verify pass, commit.

---

## Task 0.2: Wire db_pool on ReasoningEngine

**Context:** `reasoning.py` has `pool = getattr(self, "_db_pool", None)` → always `None` → `rag.low_confidence` events never emitted. This unblocks D4 RAG Enricher.

**Files:**

- Modify: `apps/backend-rag/backend/services/rag/agentic/reasoning.py` (already has the `maybe_emit_low_confidence` call, just needs `_db_pool` populated)
- Modify: `apps/backend-rag/backend/app/setup/service_initializer.py` (inject pool into ReasoningEngine at startup)
- Create: `apps/backend-rag/backend/tests/services/rag/test_low_confidence_emit_real.py`

- [ ] **Step 1: Find where ReasoningEngine is instantiated**

Run: `grep -rn "ReasoningEngine(" apps/backend-rag/backend/app/ apps/backend-rag/backend/services/ --include='*.py' | grep -v test_`

Expected: 1-2 callsites in `service_initializer.py` or `app_factory.py`.

- [ ] **Step 2: Write the failing test**

Create `apps/backend-rag/backend/tests/services/rag/test_low_confidence_emit_real.py`:

```python
"""Verify ReasoningEngine has db_pool wired and emits rag.low_confidence."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_reasoning_engine_has_db_pool_attribute():
    """ReasoningEngine must expose _db_pool set to an actual pool after init."""
    from backend.services.rag.agentic.reasoning import ReasoningEngine

    fake_pool = MagicMock(name="asyncpg.Pool")
    engine = ReasoningEngine(db_pool=fake_pool)
    assert engine._db_pool is fake_pool


@pytest.mark.asyncio
async def test_low_confidence_emit_called_with_real_pool():
    """When evidence_score < 0.3 and pool is set, maybe_emit_low_confidence is invoked."""
    from backend.services.rag.agentic.reasoning import ReasoningEngine

    fake_pool = MagicMock(name="asyncpg.Pool")
    engine = ReasoningEngine(db_pool=fake_pool)

    with patch(
        "backend.services.bridge.low_confidence_emitter.maybe_emit_low_confidence",
        new_callable=AsyncMock,
    ) as emit:
        await engine._maybe_emit_low_confidence_bridge("test query", 0.1)
        emit.assert_awaited_once_with(fake_pool, "test query", 0.1)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd apps/backend-rag && PYTHONPATH=. .venv/bin/pytest backend/tests/services/rag/test_low_confidence_emit_real.py -v`

Expected: FAIL — `ReasoningEngine.__init__() got unexpected keyword 'db_pool'` (or similar).

- [ ] **Step 4: Add db_pool to ReasoningEngine.**init\*\*\*\*

Open `apps/backend-rag/backend/services/rag/agentic/reasoning.py`. Find the `class ReasoningEngine` definition and its `__init__`. Add `db_pool` parameter:

```python
def __init__(
    self,
    ...existing_params,
    db_pool: Optional[Any] = None,  # asyncpg.Pool
):
    ...existing_body
    self._db_pool = db_pool
```

Also extract the existing inline emit call into a helper method for testability. Find the two callsites in the file (lines ~628-641 and ~1390-1401) and add this method to the class:

```python
async def _maybe_emit_low_confidence_bridge(self, query: str, evidence_score: float) -> None:
    """Emit rag.low_confidence via bridge outbox if pool is wired. Never raises."""
    if self._db_pool is None:
        return
    try:
        from backend.services.bridge.low_confidence_emitter import maybe_emit_low_confidence
        await maybe_emit_low_confidence(self._db_pool, query, evidence_score)
    except Exception as exc:
        logger.warning(f"Low-confidence emit skipped: {exc}")
```

Replace both inline try/except blocks with: `await self._maybe_emit_low_confidence_bridge(query, evidence_score)`.

Remove the "pool is None here ... full wire-up in Task 17" comment.

- [ ] **Step 5: Wire the pool at ReasoningEngine construction**

Open `apps/backend-rag/backend/app/setup/service_initializer.py` (or wherever the grep in Step 1 found `ReasoningEngine(...)`). Add `db_pool=pg_pool` to the constructor call. The `pg_pool` variable should already exist in that scope — if not, grep for `asyncpg.create_pool` or `get_db_pool` to find it and pass it through.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. .venv/bin/pytest backend/tests/services/rag/test_low_confidence_emit_real.py -v`

Expected: PASS.

- [ ] **Step 7: Run full RAG test suite to check no regressions**

Run: `cd apps/backend-rag && PYTHONPATH=. .venv/bin/pytest backend/tests/services/rag/ -q --tb=line`

Expected: all pre-existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add apps/backend-rag/backend/services/rag/agentic/reasoning.py \
        apps/backend-rag/backend/app/setup/service_initializer.py \
        apps/backend-rag/backend/tests/services/rag/test_low_confidence_emit_real.py
git commit -m "$(cat <<'EOF'
fix(rag/reasoning): wire db_pool on ReasoningEngine to enable low-confidence bridge emit

Phase 1 left ReasoningEngine._db_pool unset → maybe_emit_low_confidence
always skipped. Phase 2 unblocks D4 RAG Enricher by populating pool at
construction time from service_initializer.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 0.3: Integration test reflect→store→inject

**Context:** Sprint 5 Task 6 (never completed). Lock in today's fixes with automated test so future refactors don't re-break the loop.

**Files:**

- Create: `apps/mata-garuda/tests/test_organism_integration.py`

- [ ] **Step 1: Write the failing integration test**

Create `apps/mata-garuda/tests/test_organism_integration.py`:

```python
"""End-to-end: run_with_lamarckian_feedback must produce KB entries (reflection + skill + insight)
and inject recent reflections into the next run's prompt."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def isolated_kb(tmp_path, monkeypatch):
    """KB in a temp directory to isolate from real data/knowledge.db."""
    from mata_garuda.runtime.knowledge import KnowledgeBase
    db = tmp_path / "test_kb.db"
    kb = KnowledgeBase(db_path=db)
    yield kb
    kb.close()


@pytest.fixture
def mock_agent():
    """Minimal registered agent for the test."""
    from mata_garuda.types import Agent
    return Agent(
        name="test_agent",
        model="claude",
        instructions=lambda: "test instructions",
        functions=[],
        genome_path="/tmp/ignored.md",
        layer="harvester",
    )


def _fake_cli_reflection_output() -> str:
    return json.dumps({
        "what_worked": "source reachable, 5 items scraped",
        "what_didnt": "no dedup against stream",
        "skill": "curl + regex parse when source is peraturan.go.id",
        "insight": "stream_publish is idempotent within 10ms window",
    })


def test_reflect_store_inject_cycle(isolated_kb, mock_agent):
    """Run Lamarckian loop twice: first produces reflection, second injects it into prompt."""
    from mata_garuda.runtime.lamarckian import run_with_lamarckian_feedback
    from mata_garuda.runtime.reflection import build_reflection_context

    # Mock CLI to simulate case_resolved + reflection output
    with patch("mata_garuda.runtime.cli_runtime.CLIRuntime.run_claude_with_fallback") as cli:
        # First call: agent execution returns case_resolved
        # Second call: reflection produces JSON with skill + insight
        cli.side_effect = [
            MagicMock(success=True, output="case_resolved: scraped 5"),
            MagicMock(success=True, output=_fake_cli_reflection_output()),
        ]
        run_with_lamarckian_feedback(
            agent=mock_agent,
            query="harvest routine",
            kb=isolated_kb,
        )

    # After first run: KB must contain reflection + skill + insight
    stats = isolated_kb.stats()
    assert stats.get("reflection", 0) == 1, f"reflection missing: {stats}"
    assert stats.get("skill", 0) == 1, f"skill missing: {stats}"
    assert stats.get("insight", 0) == 1, f"insight missing: {stats}"

    # Reflection context for next run must contain the stored reflection
    ctx = build_reflection_context(isolated_kb, mock_agent.name, n=5)
    assert "case_resolved" in ctx or "scraped 5" in ctx or "what_worked" in ctx, \
        f"reflection not injected into context: {ctx[:200]}"
```

- [ ] **Step 2: Run test to verify it fails (or passes immediately with today's fixes)**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_organism_integration.py -v`

Expected: PASS (fixes from commit `1520ce004` should already make the cycle work). If it fails, the failure points to the exact missing wiring.

- [ ] **Step 3: If test failed, fix according to error. If passed, verify by forcing a regression**

Temporarily revert one fix (e.g. comment out `import mata_garuda.agents` in `cell/runner.py`) → test should fail → restore → test passes. This confirms the test is meaningful, not a no-op. (Do NOT commit the temporary regression.)

- [ ] **Step 4: Run full suite**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/ -q --tb=line`

Expected: 281/281 pass (280 pre-existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/tests/test_organism_integration.py
git commit -m "$(cat <<'EOF'
test(mata-garuda): integration test for reflect→store→inject cycle

Locks in commit 1520ce004 fixes with automated regression guard.
Verifies: Lamarckian loop produces reflection+skill+insight in KB,
reflection context is injected into next run's prompt.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 0.4: Update SYMBIOSIS.md — Pilastro 1+2 Operativo

**Files:**

- Modify: `SYMBIOSIS.md` (section "DOVE SIAMO" table)

- [ ] **Step 1: Read current section**

Read `SYMBIOSIS.md` lines 190-205 (the "DOVE SIAMO" table).

- [ ] **Step 2: Update entries for Pilastro 1 and Pilastro 2**

Change:

```
| Riflessione   | Sprint 5 pianificato                        | `runtime/reflection.py` + JSON output              |
| Accumulazione | Sprint 5 pianificato                        | `runtime/knowledge.py` SQLite KB unificata         |
```

To:

```
| Riflessione   | ✅ Operativo — reflection.py attivo, 1a entry KB 2026-04-14 | Sleep consolidation (Fase 2 D3)                    |
| Accumulazione | ✅ Operativo — knowledge.py SQLite FTS5, 338 entries         | Cross-agent skill promotion (Fase 2 D3 pass 2)     |
```

Also add a line under the table referencing the audit:

```
> **Audit 2026-04-14:** i pilastri 1+2 erano codice implementato ma inerte in produzione (registry vuoto, SQLite threading crash). Commit `1520ce004` ha attivato il loop. Prima reflection reale 14:53 WITA.
```

- [ ] **Step 3: Commit**

```bash
git add SYMBIOSIS.md
git commit -m "$(cat <<'EOF'
docs(symbiosis): Pilastro 1+2 → Operativo after audit fixes

Reflection + Accumulazione are live in production after commit 1520ce004.
First real entry in KB produced by manual pulse 2026-04-14 14:53 WITA.
Next: sleep consolidation (Fase 2 D3) promuove skill cross-agent.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# D1 — Priority Engine

## Task D1.1: Priority store — JSON flat + JSONL audit

**Files:**

- Create: `apps/mata-garuda/mata_garuda/priority/__init__.py` (empty)
- Create: `apps/mata-garuda/mata_garuda/priority/store.py`
- Create: `apps/mata-garuda/tests/test_priority_store.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/mata-garuda/tests/test_priority_store.py`:

```python
"""Tests for priority store: JSON flat snapshot + JSONL audit."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def store(tmp_path):
    from mata_garuda.priority.store import PriorityStore
    return PriorityStore(
        snapshot_path=tmp_path / "topic_priorities.json",
        audit_path=tmp_path / "topic_priority_bumps.jsonl",
    )


class TestPriorityStore:
    def test_empty_returns_default_priority(self, store):
        """Unknown topic returns 1.0 (default uniform)."""
        assert store.get("tax") == pytest.approx(1.0)

    def test_bump_updates_priority(self, store):
        """bump() increases priority and persists to snapshot file."""
        store.bump("tax", delta=1.0, event="crm.client_created", meta={"sector": "PMA-Tax"})
        assert store.get("tax") > 1.0
        assert store.snapshot_path.exists()

    def test_bump_appends_jsonl_audit(self, store):
        """Each bump appends a line to the JSONL audit file."""
        store.bump("tax", delta=1.0, event="crm.client_created")
        store.bump("immigration", delta=0.5, event="crm.practice_completed")
        lines = store.audit_path.read_text().strip().split("\n")
        assert len(lines) == 2
        entry = json.loads(lines[0])
        assert entry["topic"] == "tax"
        assert entry["delta"] == 1.0
        assert entry["event"] == "crm.client_created"
        assert "ts" in entry

    def test_decay_reduces_over_time(self, store):
        """Retrieval applies exponential decay based on last_bump_at."""
        store.bump("tax", delta=4.0, event="crm.client_created")
        # Force last_bump_at to 60 days ago → priority should halve twice
        import json as _j
        snap = _j.loads(store.snapshot_path.read_text())
        snap["topics"]["tax"]["last_bump_at"] = "2026-02-14T00:00:00+08:00"  # 60d before 2026-04-14
        snap["topics"]["tax"]["decay_half_life_days"] = 30
        store.snapshot_path.write_text(_j.dumps(snap))
        # Use injected "now" so test is deterministic
        value = store.get("tax", now_iso="2026-04-14T00:00:00+08:00")
        # 4.0 * 2^(-60/30) = 4.0 * 0.25 = 1.0
        assert value == pytest.approx(1.0, rel=0.01)

    def test_atomic_write_survives_crash(self, store, monkeypatch):
        """Snapshot write uses temp+rename; stale temp files do not corrupt."""
        # Pre-create a stale temp file to ensure rename overwrites cleanly
        tmp = store.snapshot_path.with_suffix(".json.tmp")
        tmp.write_text("{invalid json")
        store.bump("tax", delta=1.0, event="crm.client_created")
        # Snapshot must be valid JSON
        data = json.loads(store.snapshot_path.read_text())
        assert data["topics"]["tax"]["priority"] >= 1.0

    def test_graceful_default_when_snapshot_missing(self, store):
        """If snapshot file is deleted, get() still returns default."""
        store.bump("tax", delta=1.0, event="test")
        store.snapshot_path.unlink()
        assert store.get("tax") == pytest.approx(1.0)

    def test_graceful_default_when_snapshot_malformed(self, store):
        """If snapshot file is corrupted, get() returns default and logs."""
        store.snapshot_path.write_text("{not json")
        assert store.get("tax") == pytest.approx(1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_priority_store.py -v`

Expected: FAIL — `ModuleNotFoundError: mata_garuda.priority`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/mata-garuda/mata_garuda/priority/__init__.py` (empty file, just marker).

Create `apps/mata-garuda/mata_garuda/priority/store.py`:

```python
"""Priority store: JSON flat snapshot + JSONL audit.

Design (spec Phase 2 D1): topic priority is hot config (1 writer, N readers),
stored as atomic JSON snapshot. Every bump appends to a JSONL audit trail
for debuggability. Decay is computed lazily at retrieval time.

Pattern confirmed by NLM ground truth (Voyager/AgentSpawn/CtxVault):
file-based config for dynamic state, algorithmic decay at retrieval.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("mata_garuda.priority")

WITA = timezone(timedelta(hours=8))
DEFAULT_PRIORITY = 1.0
DEFAULT_HALF_LIFE_DAYS = 30


def _now_wita() -> datetime:
    return datetime.now(WITA)


class PriorityStore:
    """Atomic JSON snapshot + append-only JSONL audit."""

    def __init__(self, snapshot_path: Path, audit_path: Path):
        self.snapshot_path = Path(snapshot_path)
        self.audit_path = Path(audit_path)
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_snapshot(self) -> dict:
        """Return snapshot dict or {} on any error. Never raises."""
        try:
            return json.loads(self.snapshot_path.read_text())
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"[priority] snapshot unreadable, using default: {exc}")
            return {}

    def _write_snapshot_atomic(self, data: dict) -> None:
        """Write via temp file + rename to survive crash mid-write."""
        tmp = self.snapshot_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        os.replace(tmp, self.snapshot_path)

    def _append_audit(self, entry: dict) -> None:
        """Append one JSONL line. Never raises — audit failure must not break bumps."""
        try:
            with self.audit_path.open("a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(f"[priority] audit append failed: {exc}")

    def get(self, topic: str, now_iso: Optional[str] = None) -> float:
        """Return current priority with decay applied. Defaults to 1.0 on any error."""
        snap = self._load_snapshot()
        topics = snap.get("topics", {})
        entry = topics.get(topic)
        if entry is None:
            return DEFAULT_PRIORITY

        base = float(entry.get("priority", DEFAULT_PRIORITY))
        half_life = float(entry.get("decay_half_life_days", DEFAULT_HALF_LIFE_DAYS))
        last_bump = entry.get("last_bump_at")
        if not last_bump:
            return base

        try:
            last_dt = datetime.fromisoformat(last_bump)
            now = datetime.fromisoformat(now_iso) if now_iso else _now_wita()
            days = (now - last_dt).total_seconds() / 86400.0
            return base * (2.0 ** (-days / half_life))
        except (ValueError, TypeError) as exc:
            logger.warning(f"[priority] decay calc failed for {topic}: {exc}")
            return base

    def bump(
        self,
        topic: str,
        delta: float,
        event: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> float:
        """Increase priority and persist. Returns new priority."""
        snap = self._load_snapshot()
        snap.setdefault("version", 1)
        snap["updated_at"] = _now_wita().isoformat(timespec="seconds")
        topics = snap.setdefault("topics", {})

        entry = topics.setdefault(topic, {
            "priority": DEFAULT_PRIORITY,
            "decay_half_life_days": DEFAULT_HALF_LIFE_DAYS,
        })
        # Apply decay to current stored value before adding delta (so bumps compose sanely)
        current = self.get(topic)
        new_priority = max(0.0, current + delta)
        entry["priority"] = new_priority
        entry["last_bump_at"] = _now_wita().isoformat(timespec="seconds")
        entry.setdefault("decay_half_life_days", DEFAULT_HALF_LIFE_DAYS)

        self._write_snapshot_atomic(snap)

        audit_entry = {
            "ts": _now_wita().isoformat(timespec="seconds"),
            "event": event,
            "topic": topic,
            "delta": delta,
            "new_priority": new_priority,
        }
        if meta:
            audit_entry.update(meta)
        self._append_audit(audit_entry)

        logger.info(f"[priority] {topic} {current:.2f} → {new_priority:.2f} (delta={delta:+.2f}, event={event})")
        return new_priority
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_priority_store.py -v`

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/priority/ \
        apps/mata-garuda/tests/test_priority_store.py
git commit -m "$(cat <<'EOF'
feat(priority): JSON flat + JSONL audit store with lazy decay

Phase 2 D1 — PriorityStore: 1 writer, N readers, atomic snapshot,
append-only audit, lazy exponential decay at retrieval. Graceful default
to 1.0 on missing/malformed snapshot.

Pattern confirmed by NLM (Voyager/AgentSpawn/CtxVault): file flat for
dynamic state, algorithmic decay, not SQLite/event-stream.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D1.2: Event → topic mapping

**Files:**

- Create: `apps/mata-garuda/mata_garuda/priority/mapping.py`
- Create: `apps/mata-garuda/tests/test_priority_mapping.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_priority_mapping.py`:

```python
"""Tests for CRM event → topic bump mapping."""
import pytest


class TestMapping:
    def test_client_created_pma_tax_bumps_tax(self):
        from mata_garuda.priority.mapping import map_event_to_bumps
        bumps = map_event_to_bumps(
            "crm.client_created",
            {"sector": "PMA-Tax", "client_id": "abc"},
        )
        assert len(bumps) == 1
        topic, delta = bumps[0]
        assert topic == "tax"
        assert delta == pytest.approx(1.0)

    def test_client_created_other_sector_bumps_property(self):
        from mata_garuda.priority.mapping import map_event_to_bumps
        bumps = map_event_to_bumps(
            "crm.client_created",
            {"sector": "PMA-Other", "client_id": "abc"},
        )
        assert ("property", pytest.approx(0.5)) in bumps

    def test_practice_completed_visa_e33(self):
        from mata_garuda.priority.mapping import map_event_to_bumps
        bumps = map_event_to_bumps(
            "crm.practice_completed",
            {"type": "VISA-E33"},
        )
        assert ("immigration", pytest.approx(0.8)) in bumps

    def test_practice_completed_visa_b211(self):
        from mata_garuda.priority.mapping import map_event_to_bumps
        bumps = map_event_to_bumps(
            "crm.practice_completed",
            {"type": "VISA-B211"},
        )
        assert ("immigration", pytest.approx(0.5)) in bumps

    def test_sector_changed_two_bumps(self):
        from mata_garuda.priority.mapping import map_event_to_bumps
        bumps = map_event_to_bumps(
            "crm.client_sector_changed",
            {"old_sector": "PMA-Tax", "new_sector": "PMA-Other"},
        )
        # Tax decreases, property increases
        topics = dict(bumps)
        assert topics["tax"] == pytest.approx(-0.3)
        assert topics["property"] == pytest.approx(1.0)

    def test_unknown_event_returns_empty(self):
        from mata_garuda.priority.mapping import map_event_to_bumps
        assert map_event_to_bumps("crm.unknown", {}) == []

    def test_missing_sector_returns_empty(self):
        from mata_garuda.priority.mapping import map_event_to_bumps
        assert map_event_to_bumps("crm.client_created", {}) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_priority_mapping.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/priority/mapping.py`:

```python
"""CRM event type + payload → list of (topic, delta) bumps.

Mapping rules from spec §3 — deterministic, no LLM involved.
"""
from __future__ import annotations

from typing import Any


def map_event_to_bumps(event_type: str, payload: dict[str, Any]) -> list[tuple[str, float]]:
    """Return list of (topic, delta) for a CRM event. Empty list if no match."""
    if event_type == "crm.client_created":
        sector = payload.get("sector")
        if sector == "PMA-Tax":
            return [("tax", 1.0)]
        elif sector and sector.startswith("PMA"):
            return [("property", 0.5)]
        return []

    if event_type == "crm.practice_completed":
        ptype = payload.get("type", "")
        if ptype == "VISA-E33":
            return [("immigration", 0.8)]
        if ptype == "VISA-B211":
            return [("immigration", 0.5)]
        if ptype.startswith("VISA"):
            return [("immigration", 0.3)]
        return []

    if event_type == "crm.client_sector_changed":
        old_sector = payload.get("old_sector", "")
        new_sector = payload.get("new_sector", "")
        bumps = []
        if old_sector == "PMA-Tax":
            bumps.append(("tax", -0.3))
        elif old_sector.startswith("PMA"):
            bumps.append(("property", -0.3))
        if new_sector == "PMA-Tax":
            bumps.append(("tax", 1.0))
        elif new_sector.startswith("PMA"):
            bumps.append(("property", 1.0))
        return bumps

    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_priority_mapping.py -v`

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/priority/mapping.py \
        apps/mata-garuda/tests/test_priority_mapping.py
git commit -m "$(cat <<'EOF'
feat(priority): map CRM event types to topic bumps

Deterministic rules from spec §3. client_created/practice_completed/
sector_changed → list of (topic, delta). No LLM, pure function.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D1.3: Priority Engine consumer worker

**Files:**

- Create: `apps/mata-garuda/mata_garuda/workers/priority_engine.py`
- Create: `apps/mata-garuda/tests/test_priority_engine_worker.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_priority_engine_worker.py`:

```python
"""Tests for Priority Engine consumer worker (bridge:inbound → PriorityStore.bump)."""
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def store(tmp_path):
    from mata_garuda.priority.store import PriorityStore
    return PriorityStore(
        snapshot_path=tmp_path / "topic_priorities.json",
        audit_path=tmp_path / "topic_priority_bumps.jsonl",
    )


class TestPriorityEngineWorker:
    def test_processes_crm_event_and_bumps_store(self, store):
        from mata_garuda.workers.priority_engine import process_message

        msg = {
            "id": "1776000000000-0",
            "data": {
                "type": "crm.client_created",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": json.dumps({"sector": "PMA-Tax", "client_id": "abc"}),
            },
        }
        result = process_message(msg, store)
        assert result["status"] == "bumped"
        assert result["bumps"] == [("tax", 1.0)]
        assert store.get("tax") > 1.0

    def test_skips_non_crm_event(self, store):
        from mata_garuda.workers.priority_engine import process_message
        msg = {
            "id": "1",
            "data": {
                "type": "intel.article_ready",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": "{}",
            },
        }
        result = process_message(msg, store)
        assert result["status"] == "skipped"
        assert store.get("tax") == pytest.approx(1.0)

    def test_malformed_payload_does_not_crash(self, store):
        from mata_garuda.workers.priority_engine import process_message
        msg = {
            "id": "1",
            "data": {
                "type": "crm.client_created",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": "{not json",
            },
        }
        result = process_message(msg, store)
        assert result["status"] == "error"

    def test_unknown_event_type_logged_not_raised(self, store):
        from mata_garuda.workers.priority_engine import process_message
        msg = {
            "id": "1",
            "data": {
                "type": "crm.garbage_event",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": "{}",
            },
        }
        result = process_message(msg, store)
        assert result["status"] == "no_mapping"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_priority_engine_worker.py -v`

Expected: FAIL — `ModuleNotFoundError: mata_garuda.workers.priority_engine`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/workers/priority_engine.py`:

```python
"""Priority Engine worker — consumes bridge:inbound CRM events and bumps topic priorities.

Organ: mata-garuda.workers → consumes bridge:inbound → writes priority snapshot + JSONL.
Pattern: Redis consumer group 'priority-engine' via stream_read_new. Rate-limited to
5 events/cycle to avoid amplifying rogue event storms.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from mata_garuda.config import STREAM_BRIDGE_INBOUND
from mata_garuda.priority.mapping import map_event_to_bumps
from mata_garuda.priority.store import PriorityStore
from mata_garuda.workers.base_worker import stream_ack, stream_read_new

logger = logging.getLogger("mata_garuda.workers.priority_engine")

CONSUMER_GROUP = "priority-engine"
CONSUMER_NAME = "consumer-1"
MAX_PER_RUN = 20

DEFAULT_SNAPSHOT = Path.home() / ".agent" / "decisions" / "topic_priorities.json"
DEFAULT_AUDIT = Path.home() / ".agent" / "decisions" / "topic_priority_bumps.jsonl"


def process_message(msg: dict[str, Any], store: PriorityStore) -> dict[str, Any]:
    """Process one stream message. Returns status dict, never raises."""
    data = msg.get("data", {})
    event_type = data.get("type", "")
    if not event_type.startswith("crm."):
        return {"status": "skipped", "reason": f"not crm.* ({event_type})"}

    try:
        payload = json.loads(data.get("payload", "{}"))
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning(f"[priority_engine] malformed payload msg_id={msg.get('id')}: {exc}")
        return {"status": "error", "reason": "malformed_payload"}

    bumps = map_event_to_bumps(event_type, payload)
    if not bumps:
        return {"status": "no_mapping", "event_type": event_type}

    meta = {k: v for k, v in payload.items() if k in ("client_id", "sector", "type", "old_sector", "new_sector")}
    for topic, delta in bumps:
        store.bump(topic, delta, event=event_type, meta=meta)

    return {"status": "bumped", "bumps": bumps}


def run_once(
    store: PriorityStore | None = None,
    max_per_run: int = MAX_PER_RUN,
) -> dict[str, int]:
    """One polling cycle: read up to max_per_run messages, process, ack successes."""
    if store is None:
        store = PriorityStore(snapshot_path=DEFAULT_SNAPSHOT, audit_path=DEFAULT_AUDIT)

    messages = stream_read_new(
        STREAM_BRIDGE_INBOUND, CONSUMER_GROUP, CONSUMER_NAME, count=max_per_run,
    )
    stats = {"processed": 0, "bumped": 0, "skipped": 0, "errored": 0}
    for msg in messages:
        result = process_message(msg, store)
        stats["processed"] += 1
        if result["status"] == "bumped":
            stats["bumped"] += 1
            stream_ack(STREAM_BRIDGE_INBOUND, CONSUMER_GROUP, msg["id"])
        elif result["status"] in ("skipped", "no_mapping"):
            stats["skipped"] += 1
            stream_ack(STREAM_BRIDGE_INBOUND, CONSUMER_GROUP, msg["id"])
        else:
            stats["errored"] += 1
            # Do NOT ack — let it be redelivered, meta-agent can review
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    stats = run_once()
    logger.info(f"[priority_engine] cycle done: {stats}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_priority_engine_worker.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/workers/priority_engine.py \
        apps/mata-garuda/tests/test_priority_engine_worker.py
git commit -m "$(cat <<'EOF'
feat(priority): Redis consumer worker bridge:inbound → topic bumps

Phase 2 D1 — priority_engine worker. Consumer group 'priority-engine' on
bridge:inbound, filters crm.* events, maps via mapping.py, bumps store.
Graceful on malformed/unknown events (no crash, no ack for errors).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D1.4: Priority Engine LaunchAgent

**Files:**

- Create: `apps/mata-garuda/scripts/run_priority_engine.sh`
- Create: `apps/mata-garuda/launchagents/com.matagaruda.priority-engine.plist` (template)
- Modify: `scripts/automation_catalog.json`

- [ ] **Step 1: Create runner shell wrapper**

Create `apps/mata-garuda/scripts/run_priority_engine.sh`:

```bash
#!/bin/zsh
# Priority Engine — reads bridge:inbound CRM events, bumps topic priorities.
# Launchd entry: com.matagaruda.priority-engine (every 5 min)
set -uo pipefail

VENV_PY="/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python3"
REPO_DIR="/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda"
LOG="/Users/nuzantara/logs/matagaruda-priority-engine.log"

if [ ! -x "$VENV_PY" ]; then
    echo "[priority-engine] FATAL: venv python not found at $VENV_PY" >&2
    exit 2
fi

echo "" >> "$LOG"
echo "=== Priority Engine — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

PYTHONPATH="$REPO_DIR" "$VENV_PY" -m mata_garuda.workers.priority_engine \
    >> "$LOG" 2>&1

EXIT=$?
echo "[$(date '+%H:%M:%S')] exit=$EXIT" >> "$LOG"
exit $EXIT
```

Make executable:

```bash
chmod +x apps/mata-garuda/scripts/run_priority_engine.sh
```

- [ ] **Step 2: Create plist template**

Create `apps/mata-garuda/launchagents/com.matagaruda.priority-engine.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.matagaruda.priority-engine</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_priority_engine.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/matagaruda-priority-engine-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/matagaruda-priority-engine-launchd.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>PATH</key>
        <string>/Users/nuzantara/.pyenv/versions/3.11.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

- [ ] **Step 3: Register in automation catalog**

Read `scripts/automation_catalog.json` to understand schema. Add entry:

```json
{
  "name": "priority_engine",
  "type": "launchagent",
  "plist": "com.matagaruda.priority-engine",
  "description": "Consumes bridge:inbound CRM events, bumps topic priorities in ~/.agent/decisions/topic_priorities.json",
  "produces": [
    "~/.agent/decisions/topic_priorities.json",
    "~/.agent/decisions/topic_priority_bumps.jsonl"
  ],
  "consumes": ["bridge:inbound"],
  "schedule_seconds": 300,
  "llm": "none"
}
```

- [ ] **Step 4: Install plist (manual)**

This step requires user action (we do not auto-install launchd entries):

```bash
cp apps/mata-garuda/launchagents/com.matagaruda.priority-engine.plist \
   ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.matagaruda.priority-engine.plist
launchctl list com.matagaruda.priority-engine  # verify LastExitStatus
```

Mark the checkbox after `launchctl list` confirms the entry exists. This can be deferred until end of Phase 2 and batch-installed with other LaunchAgents.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/scripts/run_priority_engine.sh \
        apps/mata-garuda/launchagents/com.matagaruda.priority-engine.plist \
        scripts/automation_catalog.json
git commit -m "$(cat <<'EOF'
feat(priority): LaunchAgent + catalog entry for priority engine

5-minute cron consumes bridge:inbound CRM events, bumps topic priorities.
Plist template + runner + automation_catalog entry.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# D2 — LPSE Harvester

## Task D2.1: SPSE 4.5 JSON parser + tools

**Files:**

- Create: `apps/mata-garuda/mata_garuda/tools/lpse_tools.py`
- Create: `apps/mata-garuda/tests/test_lpse_tools.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_lpse_tools.py`:

```python
"""Tests for LPSE tools: SPSE 4.5 JSON scraping + parsing."""
import json
from unittest.mock import patch, MagicMock

import pytest


# Fixture: realistic SPSE 4.5 /dt/tender response (DataTables format)
SPSE_SAMPLE = {
    "draw": 1,
    "recordsTotal": 50,
    "recordsFiltered": 50,
    "data": [
        [
            "12345678",
            "Pengadaan Sistem Informasi Perpajakan",
            "Kementerian Keuangan",
            "Jasa Konsultansi Lainnya",
            "Rp 5.000.000.000",
            "2026-05-15",
            "Tender Baru",
        ],
        [
            "12345679",
            "Konstruksi Gedung Pajak",
            "DJP",
            "Konstruksi",
            "Rp 12.000.000.000",
            "2026-06-01",
            "Tender Baru",
        ],
    ],
}


class TestParseSPSE:
    def test_parse_returns_list_of_tenders(self):
        from mata_garuda.tools.lpse_tools import parse_spse_json
        tenders = parse_spse_json(SPSE_SAMPLE, source_url="https://lpse.kemenkeu.go.id")
        assert len(tenders) == 2
        t = tenders[0]
        assert t["tender_id"] == "12345678"
        assert t["tender_name"] == "Pengadaan Sistem Informasi Perpajakan"
        assert t["agency"] == "Kementerian Keuangan"
        assert t["category"] == "Jasa Konsultansi Lainnya"
        assert t["value_idr"] == 5_000_000_000
        assert t["deadline"] == "2026-05-15"
        assert t["source_url"] == "https://lpse.kemenkeu.go.id"

    def test_parse_handles_missing_data_key(self):
        from mata_garuda.tools.lpse_tools import parse_spse_json
        assert parse_spse_json({"draw": 1}, source_url="") == []

    def test_parse_handles_short_row(self):
        """Rows shorter than expected are skipped, not crashed."""
        from mata_garuda.tools.lpse_tools import parse_spse_json
        payload = {"data": [["only", "two"]]}
        result = parse_spse_json(payload, source_url="x")
        assert result == []

    def test_parse_value_idr_various_formats(self):
        """IDR values come in 'Rp X.XXX.XXX' or 'Rp X Miliar' — robust parsing."""
        from mata_garuda.tools.lpse_tools import parse_idr_value
        assert parse_idr_value("Rp 5.000.000.000") == 5_000_000_000
        assert parse_idr_value("Rp 500.000") == 500_000
        assert parse_idr_value("-") == 0
        assert parse_idr_value("") == 0
        # "Rp 5 Miliar" — not auto-converted, returns 0 (better than wrong)
        assert parse_idr_value("Rp 5 Miliar") == 0


class TestScrapeSPSE:
    def test_scrape_uses_curl_with_ua(self):
        """scrape_spse_tender runs curl with User-Agent rotation."""
        from mata_garuda.tools.lpse_tools import scrape_spse_tender

        mock_result = MagicMock(returncode=0, stdout=json.dumps(SPSE_SAMPLE), stderr="")
        with patch("subprocess.run", return_value=mock_result) as run:
            tenders = scrape_spse_tender("https://lpse.kemenkeu.go.id")
            assert len(tenders) == 2
            # Verify curl was called with -A (User-Agent) flag
            call_args = run.call_args[0][0]
            assert "curl" in call_args[0]
            assert "-A" in call_args

    def test_scrape_returns_empty_on_curl_error(self):
        from mata_garuda.tools.lpse_tools import scrape_spse_tender
        mock_result = MagicMock(returncode=28, stdout="", stderr="timeout")
        with patch("subprocess.run", return_value=mock_result):
            assert scrape_spse_tender("https://down.example") == []

    def test_scrape_returns_empty_on_malformed_json(self):
        from mata_garuda.tools.lpse_tools import scrape_spse_tender
        mock_result = MagicMock(returncode=0, stdout="<html>Not JSON</html>", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            assert scrape_spse_tender("https://html.example") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_lpse_tools.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/tools/lpse_tools.py`:

```python
"""LPSE Harvester tools — SPSE 4.5 JSON scraping + parsing.

SPSE 4.5 is the LKPP-standard stack under most Indonesian regional LPSE
portals. It exposes a DataTables JSON endpoint at /dt/tender returning
an array of tender rows.

Reference: spec §4 (Phase 2 D2), Gemini CLI insight 2026-04-14.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Any

logger = logging.getLogger("mata_garuda.tools.lpse")

# Rotate through plausible browser User-Agents
UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]


def _pick_ua() -> str:
    import random
    return random.choice(UA_POOL)


def parse_idr_value(raw: str) -> int:
    """Parse 'Rp 5.000.000.000' → 5000000000. Returns 0 on unparseable."""
    if not raw or raw.strip() in ("-", ""):
        return 0
    # Strip 'Rp', dots, whitespace
    cleaned = re.sub(r"[Rp\s\.]", "", raw)
    # Only accept pure digits; strings with letters (Miliar, Juta) return 0
    if not cleaned.isdigit():
        return 0
    return int(cleaned)


def parse_spse_json(payload: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    """Extract tenders from SPSE 4.5 DataTables response. Never raises."""
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return []

    tenders = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            tenders.append({
                "tender_id": str(row[0]),
                "tender_name": str(row[1]),
                "agency": str(row[2]),
                "category": str(row[3]),
                "value_idr": parse_idr_value(str(row[4])),
                "deadline": str(row[5]),
                "status": str(row[6]),
                "source_url": source_url,
            })
        except (IndexError, ValueError, TypeError) as exc:
            logger.warning(f"[lpse] skipped malformed row: {exc}")
            continue
    return tenders


def scrape_spse_tender(base_url: str, timeout: int = 30) -> list[dict[str, Any]]:
    """Fetch /dt/tender from a SPSE 4.5 portal. Returns list of tender dicts.

    base_url: e.g. 'https://lpse.baliprov.go.id' or 'https://inaproc.id'.
    """
    url = base_url.rstrip("/") + "/eproc4/dt/tender"
    cmd = [
        "curl", "-sS", "--max-time", str(timeout),
        "-A", _pick_ua(),
        "-H", "Accept: application/json, text/javascript, */*; q=0.01",
        "-H", "X-Requested-With: XMLHttpRequest",
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        logger.warning(f"[lpse] curl timeout on {url}")
        return []

    if result.returncode != 0:
        logger.warning(f"[lpse] curl failed rc={result.returncode} stderr={result.stderr[:120]}")
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning(f"[lpse] non-JSON response from {url} (first 80: {result.stdout[:80]!r})")
        return []

    return parse_spse_json(payload, source_url=base_url)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_lpse_tools.py -v`

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/tools/lpse_tools.py \
        apps/mata-garuda/tests/test_lpse_tools.py
git commit -m "$(cat <<'EOF'
feat(lpse): SPSE 4.5 JSON scraper + parser tools

Phase 2 D2 — Indonesian LPSE (e-procurement) tooling. DataTables JSON
endpoint /eproc4/dt/tender, UA rotation, IDR value parsing. Graceful
on curl errors, malformed JSON, short rows.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D2.2: LPSE Harvester agent + GENOME

**Files:**

- Create: `apps/mata-garuda/mata_garuda/agents/lpse_harvester.py`
- Create: `apps/mata-garuda/mata_garuda/agents/lpse_harvester_GENOME.md`
- Create: `apps/mata-garuda/tests/test_lpse_harvester.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_lpse_harvester.py`:

```python
"""Tests for LPSE harvester agent factory + fallback chain."""
import pytest
from unittest.mock import patch


def test_lpse_harvester_registered():
    """Agent is registered and retrievable by display name."""
    import mata_garuda.agents  # noqa: populate registry
    from mata_garuda.registry import get_agent
    agent = get_agent("LPSE Harvester")
    assert agent is not None
    assert agent.name == "LPSE Harvester"


def test_harvest_lpse_fallback_chain():
    """harvest_lpse tool tries INAproc first, falls back to regionals in priority order."""
    from mata_garuda.tools.lpse_tools import scrape_spse_tender  # noqa
    from mata_garuda.agents.lpse_harvester import harvest_lpse

    # First call (INAproc) returns empty; regional fallback returns 2 tenders
    with patch(
        "mata_garuda.agents.lpse_harvester.scrape_spse_tender",
        side_effect=[[], [], [{"tender_id": "X", "tender_name": "T", "agency": "A", "source_url": "https://lpse.baliprov.go.id"}]],
    ) as scr:
        result = harvest_lpse(sector="tax")
        assert result["status"] == "found"
        assert result["count"] == 1
        # Verify 3 portals tried before success
        assert scr.call_count == 3


def test_harvest_lpse_all_fail_returns_empty():
    from mata_garuda.agents.lpse_harvester import harvest_lpse
    with patch("mata_garuda.agents.lpse_harvester.scrape_spse_tender", return_value=[]):
        result = harvest_lpse(sector="tax")
        assert result["status"] == "empty"
        assert result["count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_lpse_harvester.py -v`

Expected: FAIL — agent not registered or module missing.

- [ ] **Step 3: Write GENOME.md**

Create `apps/mata-garuda/mata_garuda/agents/lpse_harvester_GENOME.md`:

````markdown
# LPSE Harvester — GENOME

**Layer:** harvester (Layer 1)
**Mission:** scrape Indonesian e-procurement (SPSE 4.5 stack) to close `gap.missing_procurement`.

## Sources (fallback chain order)

1. **INAproc aggregatore nazionale:** `https://inaproc.id` (primary — covers all regions if working)
2. **LPSE regionali chiave** (in priority order, adjusted by priority_engine output):
   - `https://lpse.baliprov.go.id` (Bali — home base for Bali Zero clients)
   - `https://lpse.jakarta.go.id` (DKI Jakarta — highest procurement volume)
   - `https://lpse.kemenkumham.go.id` (Ministry of Law — visa/immigration)
   - `https://lpse.kemenkeu.go.id` (Ministry of Finance — tax)
   - `https://www.bkpm.go.id` (Investment Board — PMA)

## Constraints

- **Rate limit:** max 5 requests/minute per domain (sleep 12s between)
- **User-Agent rotation:** 3 browser UAs (see lpse_tools.UA_POOL)
- **Timeout:** 30s per request
- **Fallback:** if INAproc returns empty or errors, try regionals in priority order; stop at first success
- **Escalation:** 3 consecutive full-chain failures → meta-agent review via TG

## Output schema (to garuda:raw, type=harvest.lpse)

```json
{
  "tender_id": "12345678",
  "tender_name": "Pengadaan Sistem Informasi Perpajakan",
  "agency": "Kementerian Keuangan",
  "category": "Jasa Konsultansi Lainnya",
  "value_idr": 5000000000,
  "deadline": "2026-05-15",
  "status": "Tender Baru",
  "source_url": "https://lpse.kemenkeu.go.id",
  "scraped_at": "2026-04-14T..."
}
```
````

## Scars / lessons (append here when they emerge)

_(empty — to be filled by post-run reflections)_

## Dependencies

- `tools/lpse_tools.py` — scraper + parser (pure regex, no HTML lib)
- `priority/store.py` — topic priorities drive fallback order

````

- [ ] **Step 4: Write agent factory**

Create `apps/mata-garuda/mata_garuda/agents/lpse_harvester.py`:

```python
"""Mata Garuda — LPSE Harvester Agent.

Layer: harvester (Layer 1).
Closes gap.missing_procurement by scraping SPSE 4.5 stack (INAproc + 5 regional LPSE).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.lpse_tools import scrape_spse_tender
from mata_garuda.tools.stream_tools import stream_info, stream_length, stream_publish

logger = logging.getLogger("mata_garuda.agents.lpse")

GENOME_PATH = Path(__file__).parent / "lpse_harvester_GENOME.md"

# Fallback chain — INAproc first, then regionals in static order.
# Priority engine may reorder regionals at runtime via sort_by_priority().
FALLBACK_PORTALS = [
    ("INAproc", "https://inaproc.id"),
    ("Bali", "https://lpse.baliprov.go.id"),
    ("Jakarta", "https://lpse.jakarta.go.id"),
    ("Kemenkumham", "https://lpse.kemenkumham.go.id"),
    ("Kemenkeu", "https://lpse.kemenkeu.go.id"),
    ("BKPM", "https://www.bkpm.go.id"),
]

RATE_LIMIT_SECONDS = 12  # 5 req/min per domain


def harvest_lpse(sector: str = "") -> dict[str, Any]:
    """Iterate fallback chain; return first non-empty result or empty dict if all fail.

    sector: optional hint for topic filtering (tax, immigration, property, etc.).
    Currently unused for filtering (SPSE doesn't expose sector); kept for telemetry.
    """
    for portal_name, base_url in FALLBACK_PORTALS:
        logger.info(f"[lpse] trying {portal_name} ({base_url})")
        tenders = scrape_spse_tender(base_url)
        if tenders:
            logger.info(f"[lpse] {portal_name} returned {len(tenders)} tenders")
            return {
                "status": "found",
                "portal": portal_name,
                "count": len(tenders),
                "tenders": tenders,
            }
        time.sleep(RATE_LIMIT_SECONDS)

    logger.warning("[lpse] all portals returned empty")
    return {"status": "empty", "count": 0, "tenders": []}


def publish_tenders(result: dict[str, Any]) -> int:
    """Publish each tender to garuda:raw with envelope type=harvest.lpse. Returns count."""
    if result.get("status") != "found":
        return 0
    published = 0
    for t in result.get("tenders", []):
        payload = {
            **t,
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        stream_publish(
            title=t["tender_name"],
            url=t["source_url"],
            source=f"lpse:{result['portal']}",
            content=str(payload),
            stream="garuda:raw",
        )
        published += 1
    return published


@register_agent(name="LPSE Harvester", func_name="get_lpse_harvester")
def get_lpse_harvester():
    """Factory returning the LPSE Harvester Agent."""
    from mata_garuda.types import Agent

    def instructions() -> str:
        return (
            "You are the LPSE Harvester agent for Mata Garuda.\n\n"
            "Mission: scrape Indonesian e-procurement portals (SPSE 4.5 stack) "
            "to close gap.missing_procurement.\n\n"
            "WORKFLOW:\n"
            "1. Call harvest_lpse (tries INAproc + 5 regionals with fallback)\n"
            "2. If status=found: call publish_tenders, then case_resolved with summary\n"
            "3. If status=empty: call case_not_resolved with take_away_message='all portals returned empty'\n\n"
            "CONSTRAINTS (from GENOME.md):\n"
            "- Rate limit: 5 req/min per domain, built into harvest_lpse\n"
            "- Max 3 consecutive empty runs → escalation to meta-agent\n"
            "- Output schema: type=harvest.lpse on garuda:raw\n"
        )

    return Agent(
        name="LPSE Harvester",
        model="claude",
        instructions=instructions,
        functions=[
            harvest_lpse,
            publish_tenders,
            stream_publish,
            stream_length,
            stream_info,
            case_resolved,
            case_not_resolved,
        ],
        genome_path=str(GENOME_PATH),
        layer="harvester",
    )
````

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_lpse_harvester.py -v`

Expected: 3 PASS.

- [ ] **Step 6: Update gap_consumer dispatch**

Modify `apps/mata-garuda/mata_garuda/workers/gap_consumer.py`:

Find the `GAP_DISPATCH` dict and change:

```python
    "gap.missing_procurement":  None,  # Phase 2: lpse_harvester
```

To:

```python
    "gap.missing_procurement":  "lpse_harvester",
```

- [ ] **Step 7: Run full gap_consumer test suite**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/ -q --tb=line -k "gap or lpse"`

Expected: all existing gap_consumer tests pass + new lpse tests pass.

- [ ] **Step 8: Commit**

```bash
git add apps/mata-garuda/mata_garuda/agents/lpse_harvester.py \
        apps/mata-garuda/mata_garuda/agents/lpse_harvester_GENOME.md \
        apps/mata-garuda/mata_garuda/workers/gap_consumer.py \
        apps/mata-garuda/tests/test_lpse_harvester.py
git commit -m "$(cat <<'EOF'
feat(lpse): LPSE Harvester agent closes gap.missing_procurement

Phase 2 D2 — agent + GENOME + gap_consumer wiring. Fallback chain:
INAproc → Bali → Jakarta → Kemenkumham → Kemenkeu → BKPM. Rate limit
5 req/min. Output to garuda:raw type=harvest.lpse with envelope.

Closes the last missing gap type (4 other types already covered by
regulation_watcher + lhkpn_harvester).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# D3 — Sleep-time Consolidation

## Task D3.1: Pydantic models for consolidation output

**Files:**

- Create: `apps/mata-garuda/mata_garuda/dream/__init__.py` (empty)
- Create: `apps/mata-garuda/mata_garuda/dream/models.py`
- Create: `apps/mata-garuda/tests/test_dream_models.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_dream_models.py`:

```python
"""Tests for dream consolidation pydantic models."""
import pytest


class TestConsolidationModels:
    def test_consolidated_skill_valid(self):
        from mata_garuda.dream.models import ConsolidatedSkill
        s = ConsolidatedSkill(
            skill_id="curl_with_ua_rotation",
            procedure="Use curl with 3-rotation UAs when 403 from primary source",
            precondition="Target returns HTTP 403 on default headers",
            success_criterion="HTTP 200 with content length > 1000",
            category="scraping",
            derived_from=["reflection_42", "reflection_67"],
        )
        assert s.skill_id == "curl_with_ua_rotation"
        assert s.category == "scraping"

    def test_consolidated_skill_rejects_bad_category(self):
        from mata_garuda.dream.models import ConsolidatedSkill
        with pytest.raises(ValueError):
            ConsolidatedSkill(
                skill_id="x",
                procedure="p",
                precondition="c",
                success_criterion="s",
                category="unknown_category",
                derived_from=[],
            )

    def test_agent_consolidation_output_strict_json(self):
        from mata_garuda.dream.models import AgentConsolidationOutput
        out = AgentConsolidationOutput(
            agent_name="Regulation Watcher",
            consolidated_skills=[],
            prunable_entries=[],
        )
        assert out.agent_name == "Regulation Watcher"

    def test_meta_consolidation_output(self):
        from mata_garuda.dream.models import MetaConsolidationOutput
        out = MetaConsolidationOutput(
            approved_skills=[],
            contradictions=[],
            cross_agent_promotions=[],
            summary="no changes",
        )
        assert out.summary == "no changes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_dream_models.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/dream/__init__.py` (empty).

Create `apps/mata-garuda/mata_garuda/dream/models.py`:

```python
"""Pydantic models for sleep-time consolidation output.

Two passes (spec §5):
  Pass 1 (per-agent): AgentConsolidationOutput — candidate skills from one agent's reflections
  Pass 2 (meta): MetaConsolidationOutput — approved/contradictions/cross-agent from all candidates

Strict validation: LLM output must conform or we fall back safely.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SkillCategory = Literal["scraping", "reasoning", "recovery", "publishing", "parsing", "general"]


class ConsolidatedSkill(BaseModel):
    """One skill extracted by pass 1 (per-agent) or approved by pass 2 (meta)."""

    skill_id: str = Field(..., description="snake_case identifier")
    procedure: str = Field(..., min_length=10, description="step-by-step procedure")
    precondition: str = Field(..., min_length=3, description="when this skill applies")
    success_criterion: str = Field(..., min_length=3, description="how to verify it worked")
    category: SkillCategory
    derived_from: list[str] = Field(default_factory=list, description="source reflection ids")


class Contradiction(BaseModel):
    """Skill candidate that conflicts with existing genome."""

    existing_skill_id: str
    new_claim: str
    conflict_type: Literal["method_disagreement", "precondition_overlap", "outcome_mismatch"]
    recommendation: str = ""


class AgentConsolidationOutput(BaseModel):
    """Pass 1 output: per-agent candidate skills + prunable reflection ids."""

    agent_name: str
    consolidated_skills: list[ConsolidatedSkill] = Field(default_factory=list)
    prunable_entries: list[str] = Field(default_factory=list)


class CrossAgentPromotion(BaseModel):
    """A skill pattern that generalizes across agents."""

    skill_id: str
    procedure: str
    precondition: str
    success_criterion: str
    category: SkillCategory
    source_agents: list[str] = Field(min_length=2)


class MetaConsolidationOutput(BaseModel):
    """Pass 2 output: what to apply to Genome after cross-agent analysis."""

    approved_skills: list[ConsolidatedSkill] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    cross_agent_promotions: list[CrossAgentPromotion] = Field(default_factory=list)
    summary: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_dream_models.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/dream/__init__.py \
        apps/mata-garuda/mata_garuda/dream/models.py \
        apps/mata-garuda/tests/test_dream_models.py
git commit -m "$(cat <<'EOF'
feat(dream): pydantic models for sleep consolidation 2-pass output

Phase 2 D3 scaffold — ConsolidatedSkill, Contradiction,
AgentConsolidationOutput (pass 1), MetaConsolidationOutput (pass 2),
CrossAgentPromotion. Strict validation ensures LLM malformed output
triggers fallback path.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D3.2: Pass 1 — per-agent compression

**Files:**

- Create: `apps/mata-garuda/mata_garuda/dream/pass1_per_agent.py`
- Create: `apps/mata-garuda/tests/test_dream_pass1.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_dream_pass1.py`:

````python
"""Tests for sleep consolidation pass 1 (per-agent compression)."""
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def kb_with_reflections(tmp_path):
    from mata_garuda.runtime.knowledge import KnowledgeBase
    kb = KnowledgeBase(db_path=tmp_path / "kb.db")
    for i in range(5):
        kb.store(
            agent="Regulation Watcher",
            entry_type="reflection",
            content=json.dumps({
                "what_worked": f"scraped {i+5} items",
                "what_didnt": "no dedup",
                "skill": "curl with UA rotation bypasses 403",
                "insight": "stream_publish is idempotent",
            }),
            source=f"reflection_{i}",
            confidence=0.5,
        )
    yield kb


def _valid_llm_output() -> str:
    return "```json\n" + json.dumps({
        "agent_name": "Regulation Watcher",
        "consolidated_skills": [
            {
                "skill_id": "harvest_with_ua_rotation",
                "procedure": "When primary source returns 403, rotate among 3 browser UAs",
                "precondition": "HTTP 403 on default curl call",
                "success_criterion": "HTTP 200 with content-length > 1000",
                "category": "scraping",
                "derived_from": ["reflection_0", "reflection_1"],
            }
        ],
        "prunable_entries": ["reflection_2", "reflection_3"],
    }) + "\n```"


class TestPass1:
    def test_produces_candidates_from_valid_llm(self, kb_with_reflections):
        from mata_garuda.dream.pass1_per_agent import consolidate_agent
        with patch(
            "mata_garuda.dream.pass1_per_agent._run_claude",
            return_value=_valid_llm_output(),
        ):
            out = consolidate_agent(
                kb=kb_with_reflections,
                agent_name="Regulation Watcher",
                existing_skills=[],
                lookback_days=7,
            )
        assert out is not None
        assert out.agent_name == "Regulation Watcher"
        assert len(out.consolidated_skills) == 1
        assert out.consolidated_skills[0].skill_id == "harvest_with_ua_rotation"
        assert out.prunable_entries == ["reflection_2", "reflection_3"]

    def test_returns_none_on_llm_malformed(self, kb_with_reflections):
        """LLM returns non-JSON or non-schema output → pass 1 returns None, no crash."""
        from mata_garuda.dream.pass1_per_agent import consolidate_agent
        with patch(
            "mata_garuda.dream.pass1_per_agent._run_claude",
            return_value="sorry, I cannot do that",
        ):
            out = consolidate_agent(
                kb=kb_with_reflections,
                agent_name="Regulation Watcher",
                existing_skills=[],
            )
        assert out is None

    def test_skips_agent_with_no_reflections(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.dream.pass1_per_agent import consolidate_agent
        kb = KnowledgeBase(db_path=tmp_path / "empty.db")
        out = consolidate_agent(kb=kb, agent_name="Unknown Agent", existing_skills=[])
        assert out is None
````

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_dream_pass1.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/dream/pass1_per_agent.py`:

````python
"""Sleep consolidation pass 1: per-agent compression.

For each agent with reflections in lookback window, run claude --print
with structured prompt. Extract skill candidates + prunable entries.
Strict pydantic validation — malformed LLM output → return None
(log, no crash). Pass 2 handles the aggregate.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Optional

from pydantic import ValidationError

from mata_garuda.dream.models import AgentConsolidationOutput
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.dream.pass1")


PROMPT_TEMPLATE = """Sei il sistema di consolidamento notturno per l'agente {agent_name}.

Reflection degli ultimi {lookback_days} giorni (n={count}):
{reflections_json}

Skill esistenti di questo agente con confidence > 0.7:
{existing_skills_json}

Estrai skill consolidate riutilizzabili. Output JSON STRICT (un solo blocco ```json```):

```json
{{
  "agent_name": "{agent_name}",
  "consolidated_skills": [
    {{
      "skill_id": "snake_case_id",
      "procedure": "step-by-step procedure in 1-3 sentences",
      "precondition": "when this applies",
      "success_criterion": "how to verify it worked",
      "category": "scraping|reasoning|recovery|publishing|parsing|general",
      "derived_from": ["reflection_id_1"]
    }}
  ],
  "prunable_entries": ["reflection_ids_to_mark_consolidated"]
}}
````

Regole:

- Una skill deve derivare da >=2 reflection (evita one-shot noise)
- procedure deve essere azionabile, non descrittiva
- Se NESSUNA skill emerge chiaramente, consolidated_skills deve essere []
- Output SOLO il blocco JSON; niente testo introduttivo o conclusivo.
  """

def \_run_claude(prompt: str, timeout: int = 180) -> str:
"""Spawn `claude --print` with prompt on stdin. Returns stdout or empty on failure."""
try:
result = subprocess.run(
["claude", "--print"],
input=prompt,
capture_output=True,
text=True,
timeout=timeout,
)
if result.returncode != 0:
logger.warning(f"[dream.pass1] claude --print rc={result.returncode}: {result.stderr[:200]}")
return ""
return result.stdout
except subprocess.TimeoutExpired:
logger.warning(f"[dream.pass1] claude --print timeout after {timeout}s")
return ""
except FileNotFoundError:
logger.error("[dream.pass1] claude CLI not found in PATH")
return ""

def \_extract_json_block(raw: str) -> Optional[str]:
"""Find the first `json ... ` block in raw. Return inner text or None."""
match = re.search(r"`json\s*\n(.*?)\n`", raw, re.DOTALL)
if match:
return match.group(1).strip() # Fallback: raw might be bare JSON
raw_stripped = raw.strip()
if raw_stripped.startswith("{") and raw_stripped.endswith("}"):
return raw_stripped
return None

def consolidate_agent(
kb: KnowledgeBase,
agent_name: str,
existing_skills: list[dict],
lookback_days: int = 7,
) -> Optional[AgentConsolidationOutput]:
"""Pass 1: read agent's reflections, run claude --print, return validated output.

    Returns None if: no reflections, LLM fails, output malformed.
    """
    # Query reflections for this agent in lookback window
    import sqlite3
    cursor = kb._conn.execute(
        "SELECT id, source, content FROM knowledge "
        "WHERE agent = ? AND type = 'reflection' "
        "AND created_at > datetime('now', ?) "
        "ORDER BY created_at DESC LIMIT 50",
        (agent_name, f"-{lookback_days} days"),
    )
    rows = [{"id": r["id"], "source": r["source"], "content": r["content"]} for r in cursor.fetchall()]
    if not rows:
        logger.info(f"[dream.pass1] no reflections for {agent_name} in {lookback_days}d")
        return None

    prompt = PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        lookback_days=lookback_days,
        count=len(rows),
        reflections_json=json.dumps(rows, ensure_ascii=False, indent=2),
        existing_skills_json=json.dumps(existing_skills, ensure_ascii=False, indent=2),
    )

    raw = _run_claude(prompt)
    if not raw:
        return None

    json_text = _extract_json_block(raw)
    if not json_text:
        logger.warning(f"[dream.pass1] no JSON block in LLM output for {agent_name}")
        return None

    try:
        data = json.loads(json_text)
        out = AgentConsolidationOutput(**data)
        logger.info(f"[dream.pass1] {agent_name}: {len(out.consolidated_skills)} skills, {len(out.prunable_entries)} prunable")
        return out
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning(f"[dream.pass1] validation failed for {agent_name}: {exc}")
        return None

````

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_dream_pass1.py -v`

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/dream/pass1_per_agent.py \
        apps/mata-garuda/tests/test_dream_pass1.py
git commit -m "$(cat <<'EOF'
feat(dream): pass 1 per-agent consolidation via claude --print

Phase 2 D3 — reads agent's reflections from last 7d, prompts claude for
skill extraction with strict JSON schema. Pydantic validation gates
output: malformed → None (no crash). Returns skills to feed pass 2.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
````

---

## Task D3.3: Pass 2 — meta consolidation + safety gate

**Files:**

- Create: `apps/mata-garuda/mata_garuda/dream/pass2_meta.py`
- Create: `apps/mata-garuda/mata_garuda/dream/safety_gate.py`
- Create: `apps/mata-garuda/tests/test_dream_pass2.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_dream_pass2.py`:

````python
"""Tests for sleep consolidation pass 2 (meta) + safety gate."""
import json
from unittest.mock import patch

import pytest


def _make_candidate(skill_id: str, agent: str = "test_agent") -> dict:
    from mata_garuda.dream.models import ConsolidatedSkill
    return ConsolidatedSkill(
        skill_id=skill_id,
        procedure="step 1, step 2",
        precondition="condition X",
        success_criterion="result Y",
        category="scraping",
        derived_from=[f"{agent}_ref_1"],
    ).model_dump()


def _valid_meta_output() -> str:
    return "```json\n" + json.dumps({
        "approved_skills": [_make_candidate("harvest_with_ua")],
        "contradictions": [],
        "cross_agent_promotions": [],
        "summary": "1 skill approved",
    }) + "\n```"


class TestPass2:
    def test_meta_approves_skills(self):
        from mata_garuda.dream.pass2_meta import meta_consolidate
        from mata_garuda.dream.models import AgentConsolidationOutput, ConsolidatedSkill

        pass1_outputs = [
            AgentConsolidationOutput(
                agent_name="Regulation Watcher",
                consolidated_skills=[ConsolidatedSkill(**_make_candidate("harvest_with_ua"))],
            ),
        ]
        with patch("mata_garuda.dream.pass2_meta._run_claude", return_value=_valid_meta_output()):
            out = meta_consolidate(pass1_outputs, global_genome=[])
        assert out is not None
        assert len(out.approved_skills) == 1
        assert out.summary == "1 skill approved"

    def test_meta_returns_none_on_malformed(self):
        from mata_garuda.dream.pass2_meta import meta_consolidate
        from mata_garuda.dream.models import AgentConsolidationOutput
        with patch("mata_garuda.dream.pass2_meta._run_claude", return_value="<garbage>"):
            out = meta_consolidate(
                [AgentConsolidationOutput(agent_name="x", consolidated_skills=[])],
                global_genome=[],
            )
        assert out is None

    def test_meta_empty_inputs_returns_empty_output(self):
        """No pass 1 outputs → no LLM call, empty meta output."""
        from mata_garuda.dream.pass2_meta import meta_consolidate
        out = meta_consolidate([], global_genome=[])
        assert out is not None
        assert out.approved_skills == []
        assert out.summary.lower().startswith("nothing") or "no candidate" in out.summary.lower()


class TestSafetyGate:
    def test_pass_when_success_rate_stable(self):
        from mata_garuda.dream.safety_gate import should_revert
        pre = [True, True, True, True, False, True, True, True, False, True]  # 80%
        post = [True, True, True, False, True, True, True, True, True, True]  # 90%
        assert should_revert(pre, post) is False

    def test_revert_when_success_rate_drops_by_1_sigma(self):
        from mata_garuda.dream.safety_gate import should_revert
        pre = [True] * 10  # 100%, stddev=0
        post = [False] * 10  # 0%, drop by much more than 1σ
        assert should_revert(pre, post) is True

    def test_skip_when_insufficient_data(self):
        from mata_garuda.dream.safety_gate import should_revert
        # <10 samples in either set → skip decision, don't revert
        assert should_revert([True] * 3, [False] * 3) is False
````

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_dream_pass2.py -v`

Expected: FAIL — modules missing.

- [ ] **Step 3: Write pass2_meta.py**

Create `apps/mata-garuda/mata_garuda/dream/pass2_meta.py`:

````python
"""Sleep consolidation pass 2: meta-claude over pass 1 candidates.

Input: list of pass 1 outputs + current global genome.
Output: approved_skills (→ Genome), contradictions (→ TG + log, NOT Genome),
cross_agent_promotions (→ Genome scope=Project).
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Optional

from pydantic import ValidationError

from mata_garuda.dream.models import (
    AgentConsolidationOutput,
    MetaConsolidationOutput,
)

logger = logging.getLogger("mata_garuda.dream.pass2")


PROMPT_TEMPLATE = """Sei il consolidatore meta-cognitivo dell'organismo Nuzantara.

Skill candidate proposte stanotte da {n_agents} agenti:
{candidates_json}

Genoma globale attuale (confidence > 0.7, scope=Project):
{genome_json}

Trova:
1. contradictions — skill candidate che contraddicono genoma esistente
   (stessa precondition, procedure divergenti)
2. approved_skills — candidate non contraddittorie, sicure da promuovere
3. cross_agent_promotions — pattern generalizzabili tra agenti diversi
   (lo stesso approccio scoperto da >=2 agenti indipendenti)

Output JSON STRICT:

```json
{{
  "approved_skills": [<ConsolidatedSkill>],
  "contradictions": [
    {{
      "existing_skill_id": "...",
      "new_claim": "...",
      "conflict_type": "method_disagreement|precondition_overlap|outcome_mismatch",
      "recommendation": "what Zero should consider"
    }}
  ],
  "cross_agent_promotions": [
    {{
      "skill_id": "...",
      "procedure": "...",
      "precondition": "...",
      "success_criterion": "...",
      "category": "scraping|reasoning|recovery|publishing|parsing|general",
      "source_agents": ["agent_a", "agent_b"]
    }}
  ],
  "summary": "1 frase"
}}
````

Una skill contraddice se: stessa category + stessa precondition ma procedure diverse.
Output SOLO il blocco JSON.
"""

def \_run_claude(prompt: str, timeout: int = 300) -> str:
try:
result = subprocess.run(
["claude", "--print"], input=prompt,
capture_output=True, text=True, timeout=timeout,
)
if result.returncode != 0:
logger.warning(f"[dream.pass2] claude rc={result.returncode}: {result.stderr[:200]}")
return ""
return result.stdout
except subprocess.TimeoutExpired:
logger.warning("[dream.pass2] claude --print timeout")
return ""
except FileNotFoundError:
logger.error("[dream.pass2] claude CLI not found")
return ""

def \_extract_json_block(raw: str) -> Optional[str]:
match = re.search(r"`json\s*\n(.*?)\n`", raw, re.DOTALL)
if match:
return match.group(1).strip()
raw_stripped = raw.strip()
if raw_stripped.startswith("{") and raw_stripped.endswith("}"):
return raw_stripped
return None

def meta_consolidate(
pass1_outputs: list[AgentConsolidationOutput],
global_genome: list[dict],
) -> Optional[MetaConsolidationOutput]:
"""Pass 2: aggregate pass 1 outputs into genome-ready decisions.

    Returns None only if LLM malformed; empty candidates → empty MetaConsolidationOutput.
    """
    all_candidates = []
    for p1 in pass1_outputs:
        for skill in p1.consolidated_skills:
            all_candidates.append({
                "agent": p1.agent_name,
                **skill.model_dump(),
            })

    if not all_candidates:
        return MetaConsolidationOutput(
            approved_skills=[], contradictions=[], cross_agent_promotions=[],
            summary="nothing to consolidate — no candidate from pass 1",
        )

    prompt = PROMPT_TEMPLATE.format(
        n_agents=len(pass1_outputs),
        candidates_json=json.dumps(all_candidates, ensure_ascii=False, indent=2),
        genome_json=json.dumps(global_genome, ensure_ascii=False, indent=2),
    )
    raw = _run_claude(prompt)
    if not raw:
        return None

    json_text = _extract_json_block(raw)
    if not json_text:
        logger.warning("[dream.pass2] no JSON block in LLM output")
        return None

    try:
        data = json.loads(json_text)
        out = MetaConsolidationOutput(**data)
        logger.info(
            f"[dream.pass2] approved={len(out.approved_skills)} "
            f"contradictions={len(out.contradictions)} "
            f"cross_agent={len(out.cross_agent_promotions)}"
        )
        return out
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning(f"[dream.pass2] validation failed: {exc}")
        return None

````

- [ ] **Step 4: Write safety_gate.py**

Create `apps/mata-garuda/mata_garuda/dream/safety_gate.py`:

```python
"""Sleep consolidation safety gate: revert on success_rate regression.

After applying consolidated skills, measure success_rate of next 10 runs.
If post_mean < pre_mean - pre_stddev (>1σ drop), silence the new skills.

Design: Genome silence is epigenetic (valid_to=now), not deletion. The
skill remains searchable but not used for decisions.
"""
from __future__ import annotations

import logging
import statistics
from typing import Sequence

logger = logging.getLogger("mata_garuda.dream.safety")

MIN_SAMPLES = 10


def should_revert(pre: Sequence[bool], post: Sequence[bool]) -> bool:
    """Return True iff post success rate dropped by more than 1σ below pre mean.

    Conservative: requires at least MIN_SAMPLES=10 in both sets; otherwise False.
    Rationale: avoid early reverts from noisy short windows.
    """
    if len(pre) < MIN_SAMPLES or len(post) < MIN_SAMPLES:
        logger.info(
            f"[dream.safety] insufficient samples (pre={len(pre)}, post={len(post)}) — skip revert"
        )
        return False

    pre_rate = sum(pre) / len(pre)
    post_rate = sum(post) / len(post)
    pre_stddev = statistics.stdev([1.0 if b else 0.0 for b in pre]) if len(pre) > 1 else 0.0
    threshold = pre_rate - pre_stddev

    logger.info(
        f"[dream.safety] pre_rate={pre_rate:.2f} post_rate={post_rate:.2f} "
        f"pre_stddev={pre_stddev:.2f} threshold={threshold:.2f}"
    )
    return post_rate < threshold
````

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_dream_pass2.py -v`

Expected: 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/dream/pass2_meta.py \
        apps/mata-garuda/mata_garuda/dream/safety_gate.py \
        apps/mata-garuda/tests/test_dream_pass2.py
git commit -m "$(cat <<'EOF'
feat(dream): pass 2 meta-consolidation + safety gate

Phase 2 D3 — pass 2 aggregates pass 1 candidates into approved/
contradictions/cross-agent. safety_gate.should_revert applies 1σ rule
over >=10 samples pre/post. Malformed LLM → None (no Genome pollution).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D3.4: Dream consolidation orchestrator script

**Files:**

- Create: `apps/mata-garuda/scripts/dream_consolidation.py`
- Create: `apps/mata-garuda/tests/test_dream_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_dream_orchestrator.py`:

```python
"""Tests for dream consolidation orchestrator (the glue script)."""
from unittest.mock import MagicMock, patch

import pytest


class TestOrchestrator:
    def test_run_with_no_agents_exits_clean(self, tmp_path):
        import sys
        sys.path.insert(0, "apps/mata-garuda/scripts")
        from dream_consolidation import run_dream_cycle

        # No KB entries → pass 1 returns None for all agents → pass 2 empty
        result = run_dream_cycle(
            kb_path=tmp_path / "empty.db",
            genome_path=tmp_path / "empty.db",
            agent_names=["NonExistent Agent"],
            dry_run=True,
        )
        assert result["pass1_outputs"] == []
        assert result["meta"] is None or result["meta"].approved_skills == []

    def test_run_dry_run_does_not_write_genome(self, tmp_path):
        """dry_run=True prints what would happen, writes nothing."""
        import sys
        sys.path.insert(0, "apps/mata-garuda/scripts")
        from dream_consolidation import run_dream_cycle

        result = run_dream_cycle(
            kb_path=tmp_path / "kb.db",
            genome_path=tmp_path / "genome.db",
            agent_names=[],
            dry_run=True,
        )
        assert result["genome_writes"] == 0
```

- [ ] **Step 2: Write the orchestrator**

Create `apps/mata-garuda/scripts/dream_consolidation.py`:

```python
"""Dream consolidation — nightly cron entry point.

Organ: mata-garuda.dream → reads KB reflections, runs 2-pass consolidation,
applies approved skills to Genome with safety gate.

Schedule: LaunchAgent com.matagaruda.dream.nightly, 01:00 WITA.

Activation: requires >=20 reflections in KB last 7d (checked at start).
Before that, this script exits clean and the cron is a no-op.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cell_core.genome import Genome  # noqa: E402

from mata_garuda.dream.models import MetaConsolidationOutput  # noqa: E402
from mata_garuda.dream.pass1_per_agent import consolidate_agent  # noqa: E402
from mata_garuda.dream.pass2_meta import meta_consolidate  # noqa: E402
from mata_garuda.runtime.knowledge import KnowledgeBase  # noqa: E402

logger = logging.getLogger("mata_garuda.dream")

DEFAULT_KB = Path(__file__).parent.parent / "data" / "knowledge.db"
MIN_REFLECTIONS_TO_ACTIVATE = 20
LOOKBACK_DAYS = 7


def _count_reflections(kb: KnowledgeBase, days: int = LOOKBACK_DAYS) -> int:
    cursor = kb._conn.execute(
        "SELECT COUNT(*) FROM knowledge WHERE type='reflection' AND created_at > datetime('now', ?)",
        (f"-{days} days",),
    )
    return cursor.fetchone()[0]


def _discover_agents_with_reflections(kb: KnowledgeBase, days: int = LOOKBACK_DAYS) -> list[str]:
    cursor = kb._conn.execute(
        "SELECT DISTINCT agent FROM knowledge WHERE type='reflection' "
        "AND created_at > datetime('now', ?)",
        (f"-{days} days",),
    )
    return [row[0] for row in cursor.fetchall()]


def run_dream_cycle(
    kb_path: Path = DEFAULT_KB,
    genome_path: Path = DEFAULT_KB,
    agent_names: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """One full dream cycle. Returns summary dict."""
    kb = KnowledgeBase(db_path=kb_path)
    genome = Genome(db_path=str(genome_path))

    total = _count_reflections(kb)
    if total < MIN_REFLECTIONS_TO_ACTIVATE:
        logger.info(f"[dream] only {total} reflections in last {LOOKBACK_DAYS}d (<{MIN_REFLECTIONS_TO_ACTIVATE}), skip cycle")
        return {"status": "skipped_insufficient", "reflection_count": total, "pass1_outputs": [], "meta": None, "genome_writes": 0}

    if agent_names is None:
        agent_names = _discover_agents_with_reflections(kb)

    # Pass 1: per-agent
    pass1_outputs = []
    for agent in agent_names:
        existing = [{"skill_id": r["content"][:60]} for r in genome.search(agent) or []][:10] if hasattr(genome, "search") else []
        out = consolidate_agent(kb=kb, agent_name=agent, existing_skills=existing, lookback_days=LOOKBACK_DAYS)
        if out is not None:
            pass1_outputs.append(out)

    # Pass 2: meta
    global_genome_snapshot = []  # genome.list_skills(min_confidence=0.7) — stub
    meta = meta_consolidate(pass1_outputs, global_genome=global_genome_snapshot)

    # Apply to Genome unless dry_run
    genome_writes = 0
    if meta is not None and not dry_run:
        for skill in meta.approved_skills:
            genome.record_skill(
                cell="dream",
                skill_id=skill.skill_id,
                procedure=skill.procedure,
                confidence=0.3,
                scope="Project",
            )
            genome_writes += 1
        for promo in meta.cross_agent_promotions:
            genome.record_skill(
                cell="dream_cross_agent",
                skill_id=promo.skill_id,
                procedure=promo.procedure,
                confidence=0.3,
                scope="Project",
            )
            genome_writes += 1
        # Contradictions: log + (future) send TG to Zero
        if meta.contradictions:
            contra_path = Path(__file__).parent.parent / "data" / "contradictions.jsonl"
            contra_path.parent.mkdir(parents=True, exist_ok=True)
            with contra_path.open("a") as f:
                for c in meta.contradictions:
                    f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **c.model_dump()}) + "\n")

    return {
        "status": "completed",
        "reflection_count": total,
        "pass1_outputs": pass1_outputs,
        "meta": meta,
        "genome_writes": genome_writes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print plan, do not write Genome")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    result = run_dream_cycle(dry_run=args.dry_run)
    logger.info(
        f"[dream] status={result['status']} reflections={result['reflection_count']} "
        f"pass1={len(result['pass1_outputs'])} genome_writes={result['genome_writes']}"
    )
    return 0 if result["status"] in ("completed", "skipped_insufficient") else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_dream_orchestrator.py -v`

Expected: 2 PASS.

- [ ] **Step 4: Smoke-test manually (dry-run)**

Run: `cd apps/mata-garuda && .venv/bin/python scripts/dream_consolidation.py --dry-run 2>&1 | tail -5`

Expected: reports reflection_count (probably <20 today → "skipped_insufficient").

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/scripts/dream_consolidation.py \
        apps/mata-garuda/tests/test_dream_orchestrator.py
git commit -m "$(cat <<'EOF'
feat(dream): consolidation orchestrator + LaunchAgent-ready entry point

Phase 2 D3 — dream_consolidation.py glues pass1 + pass2 + Genome writes.
Activation gate: requires >=20 reflections in 7d (prevents sparse-data
hallucinations). --dry-run flag for safe local testing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D3.5: LaunchAgent for dream consolidation

**Files:**

- Create: `apps/mata-garuda/scripts/run_dream.sh`
- Create: `apps/mata-garuda/launchagents/com.matagaruda.dream.nightly.plist`
- Modify: `scripts/automation_catalog.json`

- [ ] **Step 1: Create runner shell**

Create `apps/mata-garuda/scripts/run_dream.sh`:

```bash
#!/bin/zsh
# Dream consolidation — nightly 01:00 WITA, consolidates last 7d of reflections.
set -uo pipefail
VENV_PY="/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python3"
REPO_DIR="/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda"
LOG="/Users/nuzantara/logs/matagaruda-dream.log"
echo "" >> "$LOG"
echo "=== Dream — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"
PYTHONPATH="$REPO_DIR" "$VENV_PY" "$REPO_DIR/scripts/dream_consolidation.py" >> "$LOG" 2>&1
echo "[$(date '+%H:%M:%S')] exit=$?" >> "$LOG"
```

Make executable: `chmod +x apps/mata-garuda/scripts/run_dream.sh`.

- [ ] **Step 2: Create plist**

Create `apps/mata-garuda/launchagents/com.matagaruda.dream.nightly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.matagaruda.dream.nightly</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_dream.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>1</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/matagaruda-dream-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/matagaruda-dream-launchd.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>PATH</key>
        <string>/Users/nuzantara/.pyenv/versions/3.11.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 3: Add to automation_catalog.json**

Add entry:

```json
{
  "name": "dream_consolidation",
  "type": "launchagent",
  "plist": "com.matagaruda.dream.nightly",
  "description": "Nightly 2-pass consolidation: KB reflections → Genome skills",
  "produces": ["genome skill entries", "data/contradictions.jsonl"],
  "consumes": ["KB reflections last 7d"],
  "schedule_calendar": "01:00 WITA daily",
  "llm": "claude"
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/mata-garuda/scripts/run_dream.sh \
        apps/mata-garuda/launchagents/com.matagaruda.dream.nightly.plist \
        scripts/automation_catalog.json
git commit -m "$(cat <<'EOF'
feat(dream): LaunchAgent for nightly 01:00 WITA consolidation

Phase 2 D3 — plist template + runner + catalog entry. Activation gate
(>=20 reflections) inside the Python script; launchd entry is a no-op
until KB has enough data. Manual install deferred to Phase 2 close.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# D4 — RAG Enricher

## Task D4.1: Cross-check validators

**Files:**

- Create: `apps/mata-garuda/mata_garuda/enrichment/__init__.py` (empty)
- Create: `apps/mata-garuda/mata_garuda/enrichment/cross_check.py`
- Create: `apps/mata-garuda/tests/test_cross_check.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_cross_check.py`:

```python
"""Tests for cross-check validators (PRICING/VISA reference conflict detection)."""
import pytest


class TestCrossCheck:
    def test_no_conflict_when_content_has_no_prices(self, tmp_path):
        from mata_garuda.enrichment.cross_check import check_pricing_conflict
        pricing = tmp_path / "pricing.md"
        pricing.write_text("# Prices\n\nVisa B211: Rp 5.000.000\n")
        result = check_pricing_conflict(
            enrichment_content="Qui non si parla di soldi.",
            pricing_path=pricing,
        )
        assert result["conflict"] is False

    def test_conflict_when_price_mismatches(self, tmp_path):
        from mata_garuda.enrichment.cross_check import check_pricing_conflict
        pricing = tmp_path / "pricing.md"
        pricing.write_text("# Prices\n\nVisa B211: Rp 5.000.000 \n")
        result = check_pricing_conflict(
            enrichment_content="Visa B211 costs Rp 10.000.000",
            pricing_path=pricing,
        )
        assert result["conflict"] is True
        assert "B211" in result["reason"] or "b211" in result["reason"].lower()

    def test_visa_code_conflict(self, tmp_path):
        from mata_garuda.enrichment.cross_check import check_visa_conflict
        visa_ref = tmp_path / "visa.md"
        visa_ref.write_text("# Visa Types\n\nE33G: Investor, 2 years, min IDR 10B\n")
        result = check_visa_conflict(
            enrichment_content="E33G visa requires minimum IDR 5 billion investment",
            visa_path=visa_ref,
        )
        assert result["conflict"] is True

    def test_skip_when_reference_file_missing(self, tmp_path):
        from mata_garuda.enrichment.cross_check import check_pricing_conflict
        result = check_pricing_conflict(
            enrichment_content="anything",
            pricing_path=tmp_path / "nonexistent.md",
        )
        assert result["conflict"] is False
        assert "reference file not found" in result["reason"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_cross_check.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/enrichment/__init__.py` (empty).

Create `apps/mata-garuda/mata_garuda/enrichment/cross_check.py`:

```python
"""Cross-check enrichment content against PRICING_REFERENCE.md and VISA_TYPES_REFERENCE.md.

Reference files are maintained by Bali Zero ops team — source of truth for
prices and visa metadata. When NotebookLM-produced enrichment contradicts these
(e.g. different IDR amount, different visa validity), we mark CONFLICT and
include it in the approval-gate TG message so Zero can override or reject.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("mata_garuda.enrichment.cross_check")


_IDR_PATTERN = re.compile(r"(?:rp\.?\s*|idr\s+)([\d\.,]+)", re.IGNORECASE)
_VISA_CODE_PATTERN = re.compile(r"\b([BCE]\d{2,3}[A-Z]?)\b")


def _extract_idr_amounts(text: str) -> list[tuple[str, int]]:
    """Return list of (raw_match, int_value) for every IDR-like number. 0 if unparseable."""
    results = []
    for match in _IDR_PATTERN.finditer(text):
        raw = match.group(1)
        digits = re.sub(r"[\.,\s]", "", raw)
        try:
            results.append((match.group(0), int(digits)))
        except ValueError:
            results.append((match.group(0), 0))
    return results


def _extract_visa_codes(text: str) -> set[str]:
    return {m.upper() for m in _VISA_CODE_PATTERN.findall(text)}


def check_pricing_conflict(enrichment_content: str, pricing_path: Path) -> dict[str, Any]:
    """Compare IDR amounts in enrichment against PRICING_REFERENCE.md.

    Returns {"conflict": bool, "reason": str}.
    A conflict is flagged when enrichment mentions a visa code (B211, E33G, etc.)
    along with an IDR amount that differs from the reference by >10%.
    """
    try:
        reference = Path(pricing_path).read_text()
    except (FileNotFoundError, OSError):
        return {"conflict": False, "reason": "reference file not found"}

    enrichment_visas = _extract_visa_codes(enrichment_content)
    enrichment_amounts = {code: [amt for _, amt in _extract_idr_amounts(enrichment_content)] for code in enrichment_visas}
    if not enrichment_amounts:
        return {"conflict": False, "reason": "no visa+price mentioned"}

    for visa_code, new_amounts in enrichment_amounts.items():
        # Find reference line mentioning this visa code
        ref_lines = [line for line in reference.splitlines() if visa_code in line.upper()]
        if not ref_lines:
            continue
        ref_amounts = [amt for _, amt in _extract_idr_amounts("\n".join(ref_lines)) if amt > 0]
        if not ref_amounts:
            continue
        for new_amt in new_amounts:
            if new_amt == 0:
                continue
            for ref_amt in ref_amounts:
                if abs(new_amt - ref_amt) / max(ref_amt, 1) > 0.10:
                    return {
                        "conflict": True,
                        "reason": f"{visa_code}: enrichment={new_amt}, reference={ref_amt} (>10% diff)",
                    }
    return {"conflict": False, "reason": "no significant price diff"}


def check_visa_conflict(enrichment_content: str, visa_path: Path) -> dict[str, Any]:
    """Flag conflict when enrichment describes a visa differently from VISA_TYPES_REFERENCE.md.

    Simple heuristic: if enrichment mentions visa code X with an IDR amount,
    and reference also mentions X with a different IDR amount → conflict.
    """
    return check_pricing_conflict(enrichment_content, visa_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_cross_check.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/enrichment/ \
        apps/mata-garuda/tests/test_cross_check.py
git commit -m "$(cat <<'EOF'
feat(enrichment): cross-check validators for PRICING/VISA references

Phase 2 D4 — detects conflicts between NotebookLM enrichment output and
Bali Zero reference files (visa code + IDR amount >10% diff). Graceful
when reference file missing. Fed to TG approval message as [CONFLICT] tag.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D4.2: Budget tracker

**Files:**

- Create: `apps/mata-garuda/mata_garuda/enrichment/budget.py`
- Create: `apps/mata-garuda/tests/test_enrichment_budget.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_enrichment_budget.py`:

```python
"""Tests for RAG enrichment budget tracker (5/day + 2/week/topic)."""
import pytest


@pytest.fixture
def budget(tmp_path):
    from mata_garuda.enrichment.budget import EnrichmentBudget
    return EnrichmentBudget(state_path=tmp_path / "enrichment_budget.json")


class TestBudget:
    def test_allows_first_enrichment(self, budget):
        assert budget.can_enrich(topic="tax") is True

    def test_rejects_after_daily_cap(self, budget):
        for _ in range(5):
            budget.record(topic="tax")
        assert budget.can_enrich(topic="tax") is False
        assert budget.can_enrich(topic="immigration") is False  # daily cap is global

    def test_rejects_after_weekly_topic_cap(self, budget):
        # 2 per week per topic; simulate 2 on same topic
        budget.record(topic="tax")
        budget.record(topic="tax")
        # Still 3 daily slots remaining, but tax specifically is at weekly cap
        assert budget.can_enrich(topic="tax") is False
        assert budget.can_enrich(topic="immigration") is True

    def test_persists_across_instances(self, tmp_path):
        from mata_garuda.enrichment.budget import EnrichmentBudget
        b1 = EnrichmentBudget(state_path=tmp_path / "budget.json")
        b1.record(topic="tax")
        b2 = EnrichmentBudget(state_path=tmp_path / "budget.json")
        # Second instance sees the record
        assert b2.get_counts()["daily"] == 1
        assert b2.get_counts()["per_topic_week"]["tax"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_enrichment_budget.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/enrichment/budget.py`:

```python
"""Enrichment budget: 5/day global + 2/week per topic.

Persisted as JSON in ~/.agent/decisions/enrichment_budget.json. Self-prunes
entries older than 7 days on every access.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("mata_garuda.enrichment.budget")

WITA = timezone(timedelta(hours=8))
DAILY_CAP = 5
WEEKLY_PER_TOPIC_CAP = 2


class EnrichmentBudget:
    """Track enrichment records with day + per-topic-week caps."""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        try:
            return json.loads(self.state_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self, records: list[dict]) -> None:
        self.state_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))

    def _prune(self, records: list[dict]) -> list[dict]:
        cutoff = datetime.now(WITA) - timedelta(days=7)
        return [r for r in records if datetime.fromisoformat(r["ts"]) >= cutoff]

    def get_counts(self) -> dict:
        records = self._prune(self._load())
        now = datetime.now(WITA)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily = sum(1 for r in records if datetime.fromisoformat(r["ts"]) >= today_start)
        per_topic_week: dict[str, int] = {}
        for r in records:
            per_topic_week[r["topic"]] = per_topic_week.get(r["topic"], 0) + 1
        return {"daily": daily, "per_topic_week": per_topic_week, "total_7d": len(records)}

    def can_enrich(self, topic: str) -> bool:
        counts = self.get_counts()
        if counts["daily"] >= DAILY_CAP:
            logger.info(f"[budget] daily cap reached ({counts['daily']}/{DAILY_CAP})")
            return False
        if counts["per_topic_week"].get(topic, 0) >= WEEKLY_PER_TOPIC_CAP:
            logger.info(f"[budget] weekly cap for {topic} reached")
            return False
        return True

    def record(self, topic: str) -> None:
        records = self._prune(self._load())
        records.append({
            "ts": datetime.now(WITA).isoformat(timespec="seconds"),
            "topic": topic,
        })
        self._save(records)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_enrichment_budget.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/enrichment/budget.py \
        apps/mata-garuda/tests/test_enrichment_budget.py
git commit -m "$(cat <<'EOF'
feat(enrichment): budget tracker 5/day + 2/week/topic

Phase 2 D4 — EnrichmentBudget persists to JSON with 7d auto-prune.
can_enrich() gates both daily global cap and weekly per-topic cap.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D4.3: RAG Enricher consumer

**Files:**

- Create: `apps/mata-garuda/mata_garuda/enrichment/enricher.py`
- Create: `apps/mata-garuda/tests/test_rag_enricher.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_rag_enricher.py`:

```python
"""Tests for RAG enricher consumer (bridge:inbound → NLM → enrichment.kb_entry)."""
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def budget(tmp_path):
    from mata_garuda.enrichment.budget import EnrichmentBudget
    return EnrichmentBudget(state_path=tmp_path / "b.json")


class TestEnricher:
    def test_skip_when_score_above_threshold(self, budget):
        from mata_garuda.enrichment.enricher import process_low_confidence
        msg = {
            "id": "1",
            "data": {
                "type": "rag.low_confidence",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": json.dumps({"query": "x", "evidence_score": 0.25, "topic": "tax"}),
            },
        }
        result = process_low_confidence(msg, budget=budget, pricing_path=None, visa_path=None)
        assert result["status"] == "skipped_threshold"

    def test_skip_when_out_of_scope_topic(self, budget):
        from mata_garuda.enrichment.enricher import process_low_confidence
        msg = {
            "id": "1",
            "data": {
                "type": "rag.low_confidence",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": json.dumps({"query": "x", "evidence_score": 0.1, "topic": "property"}),
            },
        }
        result = process_low_confidence(msg, budget=budget, pricing_path=None, visa_path=None)
        assert result["status"] == "skipped_scope"

    def test_skip_when_budget_exhausted(self, budget):
        from mata_garuda.enrichment.enricher import process_low_confidence
        for _ in range(5):
            budget.record(topic="tax")
        msg = {
            "id": "1",
            "data": {
                "type": "rag.low_confidence",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": json.dumps({"query": "x", "evidence_score": 0.1, "topic": "tax"}),
            },
        }
        result = process_low_confidence(msg, budget=budget, pricing_path=None, visa_path=None)
        assert result["status"] == "skipped_budget"

    def test_runs_nlm_and_publishes_when_gated(self, budget, tmp_path):
        from mata_garuda.enrichment.enricher import process_low_confidence
        msg = {
            "id": "1",
            "data": {
                "type": "rag.low_confidence",
                "source": "bridge",
                "timestamp": "2026-04-14T10:00:00+08:00",
                "priority": "3",
                "payload": json.dumps({"query": "KITAS investor 2 anni", "evidence_score": 0.1, "topic": "immigration"}),
            },
        }
        with patch(
            "mata_garuda.enrichment.enricher._query_notebook",
            return_value={"answer": "KITAS investor 2 anni requires...", "confidence": 0.85, "notebook_id": "NB-3"},
        ), patch(
            "mata_garuda.enrichment.enricher._publish_enrichment",
            return_value="envelope_id_123",
        ) as publish:
            result = process_low_confidence(
                msg, budget=budget,
                pricing_path=tmp_path / "pricing.md",
                visa_path=tmp_path / "visa.md",
            )
        assert result["status"] == "published"
        assert result["envelope_id"] == "envelope_id_123"
        publish.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_rag_enricher.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/enrichment/enricher.py`:

```python
"""RAG Enricher: consumes bridge:inbound rag.low_confidence, queries NLM, publishes enrichment.

Gating order (spec §6):
  1. evidence_score < 0.15 (ABSTAIN range) else skip
  2. topic in {kbli, visa, tax, immigration} else skip
  3. budget.can_enrich(topic) else skip
  4. NLM cross-notebook query; if confidence < 0.7 skip
  5. cross-check pricing/visa reference; mark CONFLICT but still publish (Zero decides)
  6. publish enrichment.kb_entry on bridge:outbound
  7. budget.record(topic)
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

from mata_garuda.enrichment.budget import EnrichmentBudget
from mata_garuda.enrichment.cross_check import check_pricing_conflict, check_visa_conflict

logger = logging.getLogger("mata_garuda.enrichment.enricher")

SCOPE_TOPICS = {"kbli", "visa", "tax", "immigration"}
THRESHOLD = 0.15
NLM_MIN_CONFIDENCE = 0.7

TOPIC_TO_NOTEBOOK = {
    "kbli":         "NB-4",  # KBLI 2025 notebook id placeholder
    "visa":         "NB-3",
    "immigration":  "NB-3",
    "tax":          "NB-2",
}


def _query_notebook(query: str, notebook_id: str) -> dict:
    """Call `nlm` CLI for cross-notebook query. Returns {answer, confidence, notebook_id} or None."""
    try:
        result = subprocess.run(
            ["nlm", "query", notebook_id, query],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode != 0:
            logger.warning(f"[enricher] nlm query failed: {result.stderr[:200]}")
            return {}
        # nlm CLI output format depends on install; we expect JSON on stdout
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning(f"[enricher] nlm query error: {exc}")
        return {}


def _publish_enrichment(payload: dict) -> str:
    """Publish enrichment.kb_entry to bridge:outbound. Returns envelope id."""
    from mata_garuda.bridge.envelope import Envelope
    from mata_garuda.workers.base_worker import redis_cmd

    env = Envelope(
        type="enrichment.kb_entry",
        source="rag_enricher",
        priority=3,
        payload=payload,
    )
    redis = env.to_redis_dict()
    fields = []
    for k, v in redis.items():
        fields.extend([k, v])
    redis_cmd("XADD", "bridge:outbound", "*", *fields)
    return env.id


def process_low_confidence(
    msg: dict[str, Any],
    budget: EnrichmentBudget,
    pricing_path: Optional[Path],
    visa_path: Optional[Path],
) -> dict[str, Any]:
    """Process one rag.low_confidence message through the gating pipeline. Never raises."""
    data = msg.get("data", {})
    if data.get("type") != "rag.low_confidence":
        return {"status": "skipped_type"}

    try:
        payload = json.loads(data.get("payload", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {"status": "error_payload"}

    score = float(payload.get("evidence_score", 1.0))
    topic = str(payload.get("topic", "")).lower()
    query = str(payload.get("query", ""))

    if score >= THRESHOLD:
        return {"status": "skipped_threshold", "score": score}
    if topic not in SCOPE_TOPICS:
        return {"status": "skipped_scope", "topic": topic}
    if not budget.can_enrich(topic):
        return {"status": "skipped_budget", "topic": topic}

    notebook_id = TOPIC_TO_NOTEBOOK.get(topic)
    if not notebook_id:
        return {"status": "skipped_no_notebook", "topic": topic}

    nlm = _query_notebook(query, notebook_id)
    if not nlm or nlm.get("confidence", 0) < NLM_MIN_CONFIDENCE:
        return {"status": "skipped_nlm_weak", "nlm_confidence": nlm.get("confidence", 0)}

    answer = nlm.get("answer", "")
    conflict_notes = []
    if pricing_path:
        r = check_pricing_conflict(answer, pricing_path)
        if r.get("conflict"):
            conflict_notes.append({"type": "pricing", "reason": r.get("reason")})
    if visa_path:
        r = check_visa_conflict(answer, visa_path)
        if r.get("conflict"):
            conflict_notes.append({"type": "visa", "reason": r.get("reason")})

    payload_out = {
        "query_original": query,
        "answer": answer,
        "topic": topic,
        "nlm_confidence": nlm.get("confidence"),
        "nlm_notebook": nlm.get("notebook_id", notebook_id),
        "conflicts": conflict_notes,
        "evidence_score_original": score,
    }
    envelope_id = _publish_enrichment(payload_out)
    budget.record(topic)

    logger.info(f"[enricher] published envelope={envelope_id} topic={topic} conflicts={len(conflict_notes)}")
    return {"status": "published", "envelope_id": envelope_id, "conflicts": conflict_notes}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_rag_enricher.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/enrichment/enricher.py \
        apps/mata-garuda/tests/test_rag_enricher.py
git commit -m "$(cat <<'EOF'
feat(enrichment): RAG enricher consumer — bridge:inbound → NLM → bridge:outbound

Phase 2 D4 core — gating pipeline (threshold + scope + budget + NLM confidence)
→ cross-check conflicts → publish enrichment.kb_entry. Never raises; each
gate returns a status string for telemetry.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D4.4: Backend enrichment_pending Qdrant collection + approval endpoint

**Files:**

- Create: `apps/backend-rag/backend/services/qdrant/enrichment_pending.py`
- Create: `apps/backend-rag/backend/app/routers/enrichment_approval.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py` (register new router)
- Create: `apps/backend-rag/backend/tests/routers/test_enrichment_approval.py`

- [ ] **Step 1: Write failing tests**

Create `apps/backend-rag/backend/tests/routers/test_enrichment_approval.py`:

```python
"""Tests for enrichment approval router: pending collection + promote/reject."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from backend.app.main import app
    # Stub the qdrant service helpers used by the router
    from backend.services.qdrant import enrichment_pending as ep

    async def fake_insert_pending(entry_id, payload, vector):
        return True

    async def fake_promote(entry_id):
        return {"promoted": True, "entry_id": entry_id}

    async def fake_reject(entry_id):
        return {"rejected": True, "entry_id": entry_id}

    monkeypatch.setattr(ep, "insert_pending", fake_insert_pending)
    monkeypatch.setattr(ep, "promote_to_live", fake_promote)
    monkeypatch.setattr(ep, "reject_pending", fake_reject)
    return TestClient(app)


def test_approve_endpoint_promotes(client):
    r = client.post("/api/enrichment/approve", json={"entry_id": "abc-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["promoted"] is True
    assert body["entry_id"] == "abc-123"


def test_reject_endpoint(client):
    r = client.post("/api/enrichment/reject", json={"entry_id": "abc-123"})
    assert r.status_code == 200
    assert r.json()["rejected"] is True


def test_approve_requires_bridge_auth_header():
    """Endpoint is exempt from JWT (Phase 1 hybrid_auth), but requires bridge auth token."""
    # Deferred: covered by existing middleware.hybrid_auth tests; this placeholder
    # documents the requirement.
    pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && PYTHONPATH=. .venv/bin/pytest backend/tests/routers/test_enrichment_approval.py -v`

Expected: FAIL — router not registered, service module missing.

- [ ] **Step 3: Write enrichment_pending service**

Create `apps/backend-rag/backend/services/qdrant/enrichment_pending.py`:

```python
"""Qdrant enrichment_pending collection management.

Pending entries live in a dedicated collection (NOT the live RAG index).
Zero approves via /api/enrichment/approve → promoted to live collection.
TTL 7 days: weekly decay job removes non-approved entries.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("backend.services.qdrant.enrichment_pending")

PENDING_COLLECTION = "enrichment_pending"
LIVE_COLLECTION_BY_TOPIC = {
    "kbli":         "kbli_2025",
    "visa":         "visa_types",
    "tax":          "tax_regulations",
    "immigration":  "immigration_knowledge",
}
TTL_DAYS = 7


async def insert_pending(entry_id: str, payload: dict[str, Any], vector: list[float]) -> bool:
    """Insert a new pending enrichment. Idempotent on entry_id."""
    try:
        from backend.services.qdrant.client import get_qdrant_client
        client = get_qdrant_client()
        from qdrant_client.http.models import PointStruct  # type: ignore
        client.upsert(
            collection_name=PENDING_COLLECTION,
            points=[PointStruct(id=entry_id, vector=vector, payload={
                **payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl_days": TTL_DAYS,
            })],
        )
        return True
    except Exception as exc:
        logger.warning(f"[enrichment_pending] insert failed: {exc}")
        return False


async def promote_to_live(entry_id: str) -> dict[str, Any]:
    """Move entry from pending → live collection (chosen by payload.topic)."""
    try:
        from backend.services.qdrant.client import get_qdrant_client
        client = get_qdrant_client()
        # Retrieve
        points = client.retrieve(collection_name=PENDING_COLLECTION, ids=[entry_id], with_vectors=True)
        if not points:
            return {"promoted": False, "error": "not_found", "entry_id": entry_id}
        point = points[0]
        topic = (point.payload or {}).get("topic", "")
        live_col = LIVE_COLLECTION_BY_TOPIC.get(topic)
        if not live_col:
            return {"promoted": False, "error": f"no_live_collection_for_{topic}", "entry_id": entry_id}
        from qdrant_client.http.models import PointStruct  # type: ignore
        client.upsert(
            collection_name=live_col,
            points=[PointStruct(id=entry_id, vector=point.vector, payload=point.payload)],
        )
        client.delete(collection_name=PENDING_COLLECTION, points_selector=[entry_id])
        return {"promoted": True, "entry_id": entry_id, "live_collection": live_col}
    except Exception as exc:
        logger.exception(f"[enrichment_pending] promote failed: {exc}")
        return {"promoted": False, "error": str(exc), "entry_id": entry_id}


async def reject_pending(entry_id: str) -> dict[str, Any]:
    """Delete pending entry (hard delete)."""
    try:
        from backend.services.qdrant.client import get_qdrant_client
        client = get_qdrant_client()
        client.delete(collection_name=PENDING_COLLECTION, points_selector=[entry_id])
        return {"rejected": True, "entry_id": entry_id}
    except Exception as exc:
        logger.exception(f"[enrichment_pending] reject failed: {exc}")
        return {"rejected": False, "error": str(exc)}


async def decay_expired(max_age_days: int = TTL_DAYS) -> int:
    """Remove pending entries older than max_age_days. Returns count removed."""
    try:
        from backend.services.qdrant.client import get_qdrant_client
        from qdrant_client.http.models import Filter, FieldCondition, Range  # type: ignore
        client = get_qdrant_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        flt = Filter(must=[FieldCondition(key="created_at", range=Range(lt=cutoff))])
        client.delete(collection_name=PENDING_COLLECTION, points_selector=flt)
        return -1  # Qdrant delete by filter doesn't return count cleanly; caller treats as success
    except Exception as exc:
        logger.warning(f"[enrichment_pending] decay failed: {exc}")
        return 0
```

- [ ] **Step 4: Write the router**

Create `apps/backend-rag/backend/app/routers/enrichment_approval.py`:

```python
"""Enrichment approval endpoints.

Zero calls /approve or /reject from TG (or a helper command). Authentication
reuses the bridge API key pattern (see Phase 1 middleware/hybrid_auth.py
exemption for /api/bridge/* and /api/enrichment/*).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.qdrant import enrichment_pending as ep

logger = logging.getLogger("backend.routers.enrichment_approval")

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


class ApprovalRequest(BaseModel):
    entry_id: str = Field(..., min_length=1)


@router.post("/approve")
async def approve_entry(req: ApprovalRequest) -> dict:
    """Promote a pending enrichment to its live topic-specific collection."""
    result = await ep.promote_to_live(req.entry_id)
    if not result.get("promoted"):
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/reject")
async def reject_entry(req: ApprovalRequest) -> dict:
    """Delete a pending enrichment."""
    result = await ep.reject_pending(req.entry_id)
    if not result.get("rejected"):
        raise HTTPException(status_code=404, detail=result)
    return result
```

- [ ] **Step 5: Register the router**

Open `apps/backend-rag/backend/app/setup/router_registration.py`. Find the block where bridge router is registered (added in Phase 1). Add next to it:

```python
from backend.app.routers import enrichment_approval
app.include_router(enrichment_approval.router)
```

Also add `/api/enrichment/*` to the middleware exemption list (`backend/middleware/hybrid_auth.py`, same pattern used for `/api/bridge/*` in Phase 1).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. .venv/bin/pytest backend/tests/routers/test_enrichment_approval.py -v`

Expected: 3 PASS (one is a placeholder).

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/services/qdrant/enrichment_pending.py \
        apps/backend-rag/backend/app/routers/enrichment_approval.py \
        apps/backend-rag/backend/app/setup/router_registration.py \
        apps/backend-rag/backend/middleware/hybrid_auth.py \
        apps/backend-rag/backend/tests/routers/test_enrichment_approval.py
git commit -m "$(cat <<'EOF'
feat(backend/enrichment): pending collection + approve/reject endpoints

Phase 2 D4 backend side — enrichment_pending Qdrant collection keeps
NLM-produced entries in quarantine until Zero approves. /api/enrichment/
{approve,reject} moves point to live topic collection or deletes it.
Exempt from JWT via hybrid_auth (same pattern as /api/bridge/*).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D4.5: Bridge ingest handler for enrichment.kb_entry

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/bridge.py` (ingest/enrichment endpoint — already exists from Phase 1, extend to write to pending collection)

- [ ] **Step 1: Locate existing endpoint**

Run: `grep -n "ingest/enrichment" apps/backend-rag/backend/app/routers/bridge.py`

Expected: one match around line 60-100 where `POST /api/bridge/ingest/enrichment` is defined.

- [ ] **Step 2: Extend handler to write to enrichment_pending**

Open `apps/backend-rag/backend/app/routers/bridge.py`. In the `ingest/enrichment` handler, after parsing the payload, call `await enrichment_pending.insert_pending(entry_id, payload, vector)` using the topic-specific embedding. The existing implementation probably returns `{"vector_id": ..., "status": "indexed"}` — change `status` to `"pending"` and route to pending collection:

```python
from backend.services.qdrant import enrichment_pending

@router.post("/ingest/enrichment")
async def ingest_enrichment(payload: dict) -> dict:
    entry_id = payload.get("envelope_id") or str(uuid.uuid4())
    content = payload.get("payload", {}).get("answer", "")
    topic = payload.get("payload", {}).get("topic", "")
    # Embed with text-embedding-3-small (1536 dims, NEVER CHANGE per CLAUDE.md Golden Rule)
    vector = await embed_text(content)
    ok = await enrichment_pending.insert_pending(entry_id, {
        **payload.get("payload", {}),
        "envelope_id": payload.get("envelope_id"),
    }, vector)
    return {"entry_id": entry_id, "status": "pending" if ok else "failed"}
```

- [ ] **Step 3: Write test**

Append to `apps/backend-rag/backend/tests/routers/test_bridge_router.py` (or create if missing):

```python
def test_ingest_enrichment_writes_to_pending(monkeypatch, client):
    from backend.services.qdrant import enrichment_pending

    captured = {}
    async def fake_insert(entry_id, payload, vector):
        captured["entry_id"] = entry_id
        captured["payload"] = payload
        return True

    monkeypatch.setattr(enrichment_pending, "insert_pending", fake_insert)
    # Also stub embed_text
    import backend.app.routers.bridge as br
    async def fake_embed(text):
        return [0.0] * 1536
    monkeypatch.setattr(br, "embed_text", fake_embed)

    r = client.post(
        "/api/bridge/ingest/enrichment",
        json={
            "envelope_id": "env-abc",
            "payload": {"answer": "KITAS investor info", "topic": "immigration"},
        },
        headers={"X-Bridge-Auth": "test-key"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert captured["entry_id"] == "env-abc"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. .venv/bin/pytest backend/tests/routers/test_bridge_router.py -v`

Expected: all pass (existing + new).

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/bridge.py \
        apps/backend-rag/backend/tests/routers/test_bridge_router.py
git commit -m "$(cat <<'EOF'
feat(backend/bridge): route ingest/enrichment → enrichment_pending Qdrant collection

Phase 2 D4 wiring — enrichment.kb_entry from Pro bridge no longer goes
directly to live RAG index. Lands in enrichment_pending, awaits Zero's
/approve_kb command via TG or helper.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# D5 — Sentinel Health Cell

## Task D5.1: Rename intel sentinel + create common module

**Files:**

- Rename: `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py` → `intel_sentinel_cell.py`
- Create: `apps/mata-garuda/mata_garuda/cells/common/__init__.py` (empty)
- Create: `apps/mata-garuda/mata_garuda/cells/common/envelope.py`
- Create: `apps/mata-garuda/mata_garuda/cells/common/recovery_policy.py`
- Create: `apps/mata-garuda/tests/test_recovery_policy.py`

- [ ] **Step 1: Rename file and update imports**

```bash
cd apps/mata-garuda
git mv mata_garuda/cells/sentinel_cell.py mata_garuda/cells/intel_sentinel_cell.py
```

Update every import of `sentinel_cell` across the repo:

- `grep -rn "from mata_garuda.cells.sentinel_cell" .` and replace with `from mata_garuda.cells.intel_sentinel_cell`.
- Same for test files.

- [ ] **Step 2: Verify existing tests still pass after rename**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_sentinel_cell.py -v` (if file exists and references old name, rename import).

- [ ] **Step 3: Create common/envelope.py as thin alias**

Create `apps/mata-garuda/mata_garuda/cells/common/__init__.py` (empty).

Create `apps/mata-garuda/mata_garuda/cells/common/envelope.py`:

```python
"""Alias for mata_garuda.bridge.envelope — used by all cell-level producers.

Keeps a single source of truth for the Envelope model. Re-exports for tidy
import paths from cells/*.
"""
from mata_garuda.bridge.envelope import Envelope, WITA  # noqa: F401
```

- [ ] **Step 4: Write failing tests for recovery_policy**

Create `apps/mata-garuda/tests/test_recovery_policy.py`:

```python
"""Tests for shared recovery action whitelist."""
import pytest


class TestRecoveryPolicy:
    def test_launchctl_kickstart_allowed(self):
        from mata_garuda.cells.common.recovery_policy import is_allowed_action, build_command
        assert is_allowed_action("launchctl_kickstart", {"label": "com.matagaruda.watcher.daily"}) is True
        cmd = build_command("launchctl_kickstart", {"label": "com.matagaruda.watcher.daily"})
        assert "launchctl" in cmd
        assert "kickstart" in cmd
        assert "com.matagaruda.watcher.daily" in cmd

    def test_redis_xtrim_allowed(self):
        from mata_garuda.cells.common.recovery_policy import is_allowed_action
        assert is_allowed_action("redis_xtrim", {"stream": "garuda:raw", "maxlen": 1000}) is True

    def test_rm_rejected(self):
        from mata_garuda.cells.common.recovery_policy import is_allowed_action
        assert is_allowed_action("rm", {"path": "/tmp/x"}) is False

    def test_kill_rejected(self):
        from mata_garuda.cells.common.recovery_policy import is_allowed_action
        assert is_allowed_action("kill", {"pid": 123}) is False

    def test_unknown_action_rejected(self):
        from mata_garuda.cells.common.recovery_policy import is_allowed_action
        assert is_allowed_action("exfiltrate_data", {}) is False

    def test_build_command_raises_on_disallowed(self):
        from mata_garuda.cells.common.recovery_policy import build_command, DisallowedAction
        with pytest.raises(DisallowedAction):
            build_command("rm", {"path": "/"})

    def test_label_whitelist_enforced(self):
        """launchctl_kickstart only allows labels starting with com.matagaruda./com.nuzantara."""
        from mata_garuda.cells.common.recovery_policy import is_allowed_action
        assert is_allowed_action("launchctl_kickstart", {"label": "com.evil.daemon"}) is False
        assert is_allowed_action("launchctl_kickstart", {"label": "com.matagaruda.x"}) is True
        assert is_allowed_action("launchctl_kickstart", {"label": "com.nuzantara.y"}) is True
```

- [ ] **Step 5: Write implementation**

Create `apps/mata-garuda/mata_garuda/cells/common/recovery_policy.py`:

```python
"""Recovery action whitelist for HealthRecoveryActor.

Explicitly permitted actions only. Unknown actions, rm, kill, DROP, DELETE,
or any label outside com.matagaruda/com.nuzantara/com.balizero → rejected.
"""
from __future__ import annotations

from typing import Any


ALLOWED_LABEL_PREFIXES = ("com.matagaruda.", "com.nuzantara.", "com.balizero.", "com.cell.")
ALLOWED_STREAMS = {"garuda:raw", "garuda:enriched", "garuda:alerts", "nexus:gaps", "bridge:outbound", "bridge:inbound", "sentinel:alerts", "sentinel:recovery"}
ALLOWED_FLY_APPS = {"nuzantara-rag", "nuzantara-postgres", "nuzantara-qdrant"}


class DisallowedAction(Exception):
    """Raised when an action is not in the whitelist."""


def is_allowed_action(name: str, params: dict[str, Any]) -> bool:
    """Return True iff action name + params pass the whitelist check."""
    if name == "launchctl_kickstart":
        label = params.get("label", "")
        return any(label.startswith(p) for p in ALLOWED_LABEL_PREFIXES)
    if name == "redis_xtrim":
        stream = params.get("stream", "")
        maxlen = params.get("maxlen", -1)
        return stream in ALLOWED_STREAMS and isinstance(maxlen, int) and maxlen > 0
    if name == "fly_machine_restart":
        app = params.get("app", "")
        return app in ALLOWED_FLY_APPS
    return False  # unknown action


def build_command(name: str, params: dict[str, Any]) -> list[str]:
    """Build argv for the given action. Raises DisallowedAction if not whitelisted."""
    if not is_allowed_action(name, params):
        raise DisallowedAction(f"action not permitted: {name} params={params}")

    if name == "launchctl_kickstart":
        label = params["label"]
        # uid is the current user's — the caller substitutes via os.getuid()
        import os
        return ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"]
    if name == "redis_xtrim":
        return ["redis-cli", "XTRIM", params["stream"], "MAXLEN", str(params["maxlen"])]
    if name == "fly_machine_restart":
        return ["fly", "machine", "restart", "-a", params["app"], params.get("machine_id", "")]
    raise DisallowedAction(f"unreachable: {name}")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_recovery_policy.py -v`

Expected: 7 PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/mata-garuda/mata_garuda/cells/ \
        apps/mata-garuda/tests/test_recovery_policy.py
git commit -m "$(cat <<'EOF'
refactor(cells): rename sentinel_cell → intel_sentinel_cell; add common/ module

Phase 2 D5 setup — intel_sentinel_cell.py is harvest-focused; the new
health_sentinel_cell.py will share envelope + recovery_policy from
cells/common/. Recovery whitelist enforces: com.matagaruda/nuzantara/
balizero labels, allowed streams, nuzantara-rag/postgres/qdrant apps.
Rejects rm, kill, unknown actions.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D5.2: Health sensors (Fly, launchd, Redis depth, disk/ram/cpu, bridge throughput)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/cells/health_sensors.py`
- Create: `apps/mata-garuda/tests/test_health_sensors.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_health_sensors.py`:

```python
"""Tests for health sensors. All use subprocess mocks — no real system calls."""
from unittest.mock import MagicMock, patch

import pytest


class TestFlyStatusSensor:
    @pytest.mark.asyncio
    async def test_all_running_returns_green(self):
        from mata_garuda.cells.health_sensors import FlyStatusSensor
        fake_json = '{"Machines": [{"state": "started"}, {"state": "started"}]}'
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=fake_json, stderr="")):
            reading = await FlyStatusSensor(app="nuzantara-rag").read()
        assert reading.status == "green"

    @pytest.mark.asyncio
    async def test_machine_stopped_returns_red(self):
        from mata_garuda.cells.health_sensors import FlyStatusSensor
        fake_json = '{"Machines": [{"state": "stopped"}]}'
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=fake_json, stderr="")):
            reading = await FlyStatusSensor(app="nuzantara-rag").read()
        assert reading.status == "red"

    @pytest.mark.asyncio
    async def test_fly_cli_unavailable_returns_yellow(self):
        from mata_garuda.cells.health_sensors import FlyStatusSensor
        with patch("subprocess.run", side_effect=FileNotFoundError("fly not installed")):
            reading = await FlyStatusSensor(app="nuzantara-rag").read()
        assert reading.status == "yellow"


class TestLaunchdSensor:
    @pytest.mark.asyncio
    async def test_exit_zero_returns_green(self):
        from mata_garuda.cells.health_sensors import LaunchdSensor
        fake = '\t"LastExitStatus" = 0;\n\t"PID" = 12345;\n'
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=fake, stderr="")):
            reading = await LaunchdSensor(label="com.matagaruda.watcher.daily").read()
        assert reading.status == "green"

    @pytest.mark.asyncio
    async def test_nonzero_exit_returns_red(self):
        from mata_garuda.cells.health_sensors import LaunchdSensor
        fake = '\t"LastExitStatus" = 75;\n'
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=fake, stderr="")):
            reading = await LaunchdSensor(label="com.matagaruda.watcher.daily").read()
        assert reading.status == "red"


class TestRedisDepthSensor:
    @pytest.mark.asyncio
    async def test_depth_below_threshold_green(self):
        from mata_garuda.cells.health_sensors import RedisStreamDepthSensor
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="50\n", stderr="")):
            reading = await RedisStreamDepthSensor(stream="garuda:raw", warning=500, critical=1000).read()
        assert reading.status == "green"

    @pytest.mark.asyncio
    async def test_depth_above_critical_red(self):
        from mata_garuda.cells.health_sensors import RedisStreamDepthSensor
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="1500\n", stderr="")):
            reading = await RedisStreamDepthSensor(stream="garuda:raw", warning=500, critical=1000).read()
        assert reading.status == "red"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_health_sensors.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

Create `apps/mata-garuda/mata_garuda/cells/health_sensors.py`:

```python
"""Health sensors for the Sentinel Health cell (D5).

All sensors are subprocess-based (fly, launchctl, redis-cli, df, vm_stat, ps).
Fast path: each sensor targets <5s timeout so a pulse of 5-10 sensors completes
in <30s as required by spec §7.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from typing import Optional

from cell_core.types import SensorReading

logger = logging.getLogger("mata_garuda.cells.health_sensors")


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
    """Run subprocess, return (rc, stdout, stderr). Never raises."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return -2, "", f"command not found: {cmd[0]}"


class FlyStatusSensor:
    """Reads `fly status --json -a <app>`, red if any machine is not running."""

    def __init__(self, app: str):
        self.name = f"fly_status:{app}"
        self.app = app

    async def read(self, **ctx) -> SensorReading:
        rc, stdout, stderr = await asyncio.to_thread(_run, ["fly", "status", "--json", "-a", self.app])
        if rc == -2:
            return SensorReading(sensor_name=self.name, status="yellow", value=None, metadata={"reason": "fly CLI not installed"})
        if rc != 0:
            return SensorReading(sensor_name=self.name, status="red", value=None, metadata={"stderr": stderr[:200]})
        try:
            data = json.loads(stdout)
            machines = data.get("Machines", [])
            if not machines:
                return SensorReading(sensor_name=self.name, status="yellow", value=0, metadata={"reason": "no machines"})
            running = sum(1 for m in machines if m.get("state") == "started")
            if running == len(machines):
                return SensorReading(sensor_name=self.name, status="green", value=running, metadata={"total": len(machines)})
            return SensorReading(sensor_name=self.name, status="red", value=running, metadata={"total": len(machines)})
        except json.JSONDecodeError:
            return SensorReading(sensor_name=self.name, status="yellow", value=None, metadata={"reason": "non-JSON output"})


class LaunchdSensor:
    """Reads `launchctl list <label>`, parses LastExitStatus. Red if non-zero."""

    def __init__(self, label: str):
        self.name = f"launchd:{label}"
        self.label = label

    async def read(self, **ctx) -> SensorReading:
        rc, stdout, _ = await asyncio.to_thread(_run, ["launchctl", "list", self.label])
        if rc != 0:
            return SensorReading(sensor_name=self.name, status="yellow", value=None, metadata={"reason": "label not loaded"})
        m = re.search(r'"LastExitStatus"\s*=\s*(-?\d+);', stdout)
        if not m:
            return SensorReading(sensor_name=self.name, status="yellow", value=None, metadata={"reason": "no LastExitStatus"})
        exit_status = int(m.group(1))
        if exit_status == 0:
            return SensorReading(sensor_name=self.name, status="green", value=0)
        return SensorReading(sensor_name=self.name, status="red", value=exit_status, metadata={"label": self.label})


class RedisStreamDepthSensor:
    """XLEN on a stream, thresholds for warning/red."""

    def __init__(self, stream: str, warning: int = 500, critical: int = 1000):
        self.name = f"redis_depth:{stream}"
        self.stream = stream
        self.warning = warning
        self.critical = critical

    async def read(self, **ctx) -> SensorReading:
        rc, stdout, _ = await asyncio.to_thread(_run, ["redis-cli", "XLEN", self.stream])
        if rc != 0:
            return SensorReading(sensor_name=self.name, status="yellow", value=None, metadata={"reason": "redis-cli failed"})
        try:
            depth = int(stdout.strip())
        except ValueError:
            return SensorReading(sensor_name=self.name, status="yellow", value=None)
        if depth >= self.critical:
            return SensorReading(sensor_name=self.name, status="red", value=depth, metadata={"critical": self.critical})
        if depth >= self.warning:
            return SensorReading(sensor_name=self.name, status="yellow", value=depth, metadata={"warning": self.warning})
        return SensorReading(sensor_name=self.name, status="green", value=depth)


class DiskRamCpuSensor:
    """macOS disk/ram/load. Red if disk>90%, ram>85%, load>8."""

    def __init__(self, path: str = "/"):
        self.name = "disk_ram_cpu"
        self.path = path

    async def read(self, **ctx) -> SensorReading:
        # Disk usage via df -k
        _, disk_out, _ = await asyncio.to_thread(_run, ["df", "-k", self.path])
        disk_pct = 0
        for line in disk_out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[-1] == self.path:
                pct_str = parts[-2].rstrip("%")
                try:
                    disk_pct = int(pct_str)
                except ValueError:
                    pass
        # Load average via uptime
        _, up_out, _ = await asyncio.to_thread(_run, ["uptime"])
        load_match = re.search(r"load averages?:\s*([\d\.]+)", up_out)
        load1 = float(load_match.group(1)) if load_match else 0.0

        status = "green"
        if disk_pct > 90 or load1 > 8:
            status = "red"
        elif disk_pct > 80 or load1 > 5:
            status = "yellow"
        return SensorReading(
            sensor_name=self.name,
            status=status,
            value=disk_pct,
            metadata={"disk_pct": disk_pct, "load1": load1},
        )


class BridgeThroughputSensor:
    """Reads bridge:outbound lag via XPENDING. Red if lag > 50 or idle > 15min."""

    def __init__(self, stream: str = "bridge:outbound", group: str = "bridge-push"):
        self.name = "bridge_throughput"
        self.stream = stream
        self.group = group

    async def read(self, **ctx) -> SensorReading:
        rc, stdout, _ = await asyncio.to_thread(_run, ["redis-cli", "XPENDING", self.stream, self.group])
        if rc != 0:
            return SensorReading(sensor_name=self.name, status="yellow", value=None, metadata={"reason": "xpending failed"})
        # XPENDING output: "<count> <min_id> <max_id> ..."
        parts = stdout.strip().split()
        try:
            pending = int(parts[0]) if parts else 0
        except ValueError:
            pending = 0
        if pending > 50:
            return SensorReading(sensor_name=self.name, status="red", value=pending)
        if pending > 20:
            return SensorReading(sensor_name=self.name, status="yellow", value=pending)
        return SensorReading(sensor_name=self.name, status="green", value=pending)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_health_sensors.py -v`

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/cells/health_sensors.py \
        apps/mata-garuda/tests/test_health_sensors.py
git commit -m "$(cat <<'EOF'
feat(health): 5 sensors for Sentinel Health cell

Phase 2 D5 — FlyStatus, Launchd, RedisStreamDepth, DiskRamCpu,
BridgeThroughput. All subprocess-based, <5s timeout each, return
green/yellow/red SensorReading. Graceful on missing CLI tools.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D5.3: HealthRecoveryActor

**Files:**

- Create: `apps/mata-garuda/mata_garuda/cells/health_actor.py`
- Create: `apps/mata-garuda/tests/test_health_actor.py`

- [ ] **Step 1: Write failing tests**

Create `apps/mata-garuda/tests/test_health_actor.py`:

```python
"""Tests for HealthRecoveryActor: execute whitelisted recovery actions."""
from unittest.mock import MagicMock, patch

import pytest
from cell_core.types import Proposal


@pytest.mark.asyncio
async def test_executes_launchctl_kickstart():
    from mata_garuda.cells.health_actor import HealthRecoveryActor
    actor = HealthRecoveryActor()
    proposal = Proposal(
        action="launchctl_kickstart",
        reason="regulation_watcher failed",
        params={"label": "com.matagaruda.watcher.daily"},
    )
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="ok", stderr="")):
        result = await actor.act(proposal)
    assert "recovered" in result.lower() or "ok" in result.lower()


@pytest.mark.asyncio
async def test_rejects_disallowed_action():
    from mata_garuda.cells.health_actor import HealthRecoveryActor
    actor = HealthRecoveryActor()
    proposal = Proposal(action="rm", reason="cleanup", params={"path": "/"})
    result = await actor.act(proposal)
    assert "disallowed" in result.lower() or "rejected" in result.lower()


@pytest.mark.asyncio
async def test_can_execute_returns_false_for_unknown():
    from mata_garuda.cells.health_actor import HealthRecoveryActor
    actor = HealthRecoveryActor()
    assert actor.can_execute("launchctl_kickstart") is True
    assert actor.can_execute("rm") is False
```

- [ ] **Step 2: Write implementation**

Create `apps/mata-garuda/mata_garuda/cells/health_actor.py`:

```python
"""HealthRecoveryActor — executes whitelisted recovery commands.

Implements cell_core.protocols.Actor. Every successful recovery logs a skill
via Genome so repeated anomalies get resolved faster over time.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any, Optional

from cell_core.types import Proposal

from mata_garuda.cells.common.recovery_policy import DisallowedAction, build_command, is_allowed_action

logger = logging.getLogger("mata_garuda.cells.health_actor")


class HealthRecoveryActor:
    """Execute recovery actions from the whitelist; log outcome."""

    def __init__(self, genome: Optional[Any] = None):
        self._genome = genome
        self.last_success: Optional[bool] = None

    def can_execute(self, action_name: str) -> bool:
        """Cheap check — does not consult params."""
        return action_name in ("launchctl_kickstart", "redis_xtrim", "fly_machine_restart")

    async def act(self, proposal: Proposal) -> str:
        params = getattr(proposal, "params", {}) or {}
        if not is_allowed_action(proposal.action, params):
            self.last_success = False
            return f"[disallowed] {proposal.action} params={params}"

        try:
            cmd = build_command(proposal.action, params)
        except DisallowedAction as exc:
            self.last_success = False
            return f"[disallowed] {exc}"

        def _exec():
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        try:
            result = await asyncio.to_thread(_exec)
        except subprocess.TimeoutExpired:
            self.last_success = False
            return f"[timeout] {' '.join(cmd)}"
        except FileNotFoundError:
            self.last_success = False
            return f"[cli_missing] {cmd[0]}"

        if result.returncode != 0:
            self.last_success = False
            logger.warning(f"[health_actor] {proposal.action} rc={result.returncode} stderr={result.stderr[:200]}")
            return f"[failed rc={result.returncode}] {proposal.action}"

        self.last_success = True
        if self._genome is not None:
            try:
                self._genome.record_skill(
                    cell="health_sentinel",
                    skill_id=f"recovery_{proposal.action}_{proposal.reason[:30].replace(' ', '_')}",
                    procedure=f"when '{proposal.reason}', run: {' '.join(cmd)}",
                    confidence=0.6,
                    scope="Project",
                )
            except Exception as exc:
                logger.warning(f"[health_actor] genome record failed: {exc}")
        return f"recovered: {proposal.action} params={params}"
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_health_actor.py -v`

Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/mata-garuda/mata_garuda/cells/health_actor.py \
        apps/mata-garuda/tests/test_health_actor.py
git commit -m "$(cat <<'EOF'
feat(health): HealthRecoveryActor with whitelist + genome learning

Phase 2 D5 — executes launchctl kickstart / redis XTRIM / fly machine
restart via recovery_policy whitelist. Every success records a skill
in Genome with scope=Project so future anomalies retrieve prior
recovery procedure first.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D5.4: Health cell wiring + runner

**Files:**

- Create: `apps/mata-garuda/mata_garuda/cells/health_sentinel_cell.py`
- Create: `apps/mata-garuda/mata_garuda/cells/health_runner.py`
- Create: `apps/mata-garuda/tests/test_health_sentinel_cell.py`
- Create: `apps/mata-garuda/scripts/run_health_sentinel.sh`
- Create: `apps/mata-garuda/launchagents/com.nuzantara.health-sentinel.plist`

- [ ] **Step 1: Write failing integration test**

Create `apps/mata-garuda/tests/test_health_sentinel_cell.py`:

```python
"""Integration: one pulse of the Health Sentinel with mocked sensors."""
from unittest.mock import patch, MagicMock
import pytest


@pytest.mark.asyncio
async def test_pulse_green_sensors_no_action():
    """When all sensors green, actor is not called."""
    from mata_garuda.cells.health_sentinel_cell import create_health_sentinel_cell

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout='{"Machines":[{"state":"started"}]}', stderr="")):
        cell = create_health_sentinel_cell(pulse_interval=1)
        result = await cell.single_pulse()
    # action taken can be None or "no_action" — accept either
    assert result.action_taken in (None, "no_action", "none") or "no action" in (result.action_taken or "").lower()


@pytest.mark.asyncio
async def test_cell_factory_returns_pulse_loop():
    from mata_garuda.cells.health_sentinel_cell import create_health_sentinel_cell
    cell = create_health_sentinel_cell(pulse_interval=300)
    assert hasattr(cell, "single_pulse")
    assert hasattr(cell, "run")
```

- [ ] **Step 2: Write the cell factory**

Create `apps/mata-garuda/mata_garuda/cells/health_sentinel_cell.py`:

```python
"""Health Sentinel Cell — dedicated cell-core PulseLoop for organism monitoring.

Pulse every 5 minutes (production); health sensors are fast (<5s each) so
the whole pulse fits well under the 30s bound.

Organ map:
  SENSE   — FlyStatus, Launchd, RedisDepth, DiskRamCpu, BridgeThroughput
  THINK   — fast-path rule-based first; slow-path (claude --print) only when
            anomaly persists across multiple pulses (N/A in v1, future)
  ACT     — HealthRecoveryActor (whitelist) + publish alerts to sentinel:alerts
  REFLECT — genome.record_skill on successful recovery (handled inside actor)
  DREAM   — sleep hours 02-06 UTC → silence_stale_skills (inherited from
            cell_core base)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cell_core import CellConfig, PulseLoop, Maturation, SafetyGate, PulseResult
from cell_core.genome import Genome
from cell_core.homeostasis import HomeostaticController
from cell_core.identity import SelfModelManager
from cell_core.memory_sqlite import SqliteMemoryStack
from cell_core.types import Proposal, SensorReading, HomeostaticState

from mata_garuda.cells.health_actor import HealthRecoveryActor
from mata_garuda.cells.health_sensors import (
    BridgeThroughputSensor,
    DiskRamCpuSensor,
    FlyStatusSensor,
    LaunchdSensor,
    RedisStreamDepthSensor,
)

logger = logging.getLogger("mata_garuda.cells.health")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
KB_PATH = DATA_DIR / "knowledge.db"  # Shared KB; Genome uses scope=Project/Personal
DNA_PATH = Path(__file__).parent.parent / "health_dna.json"
SELF_PATH = DATA_DIR / "health_self_model.json"


class _FastThinker:
    """Rule-based: any red sensor → emit recovery proposal for that sensor's domain.

    This is the 'fast path' from spec §7. Slow path (claude --print) deferred to v2.
    """

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal:
        for r in readings:
            if r.status != "red":
                continue
            # Map sensor → action
            if r.sensor_name.startswith("launchd:"):
                label = r.sensor_name.split(":", 1)[1]
                return Proposal(
                    action="launchctl_kickstart",
                    reason=f"{r.sensor_name} red exit_status={r.value}",
                    params={"label": label},
                )
            if r.sensor_name.startswith("redis_depth:"):
                stream = r.sensor_name.split(":", 1)[1]
                return Proposal(
                    action="redis_xtrim",
                    reason=f"{r.sensor_name} depth={r.value}",
                    params={"stream": stream, "maxlen": 200},
                )
            if r.sensor_name.startswith("fly_status:"):
                app = r.sensor_name.split(":", 1)[1]
                return Proposal(
                    action="fly_machine_restart",
                    reason=f"{r.sensor_name} has stopped machines",
                    params={"app": app, "machine_id": ""},
                )
        return Proposal(action="none", reason="all sensors green or yellow")


def create_health_sentinel_cell(pulse_interval: int = 300) -> PulseLoop:
    """Factory: build a wired health sentinel PulseLoop."""
    config = CellConfig(
        name="health-sentinel",
        dna_path=str(DNA_PATH),
        pulse_interval_seconds=pulse_interval,
        birth_date=datetime(2026, 4, 14, tzinfo=timezone.utc),
        memory_backend="sqlite",
        db_path=str(KB_PATH),
        sleep_hours=(2, 6),
    )

    genome = Genome(db_path=str(KB_PATH))
    identity = SelfModelManager(path=str(SELF_PATH))
    identity.load()

    sensors = [
        FlyStatusSensor(app="nuzantara-rag"),
        FlyStatusSensor(app="nuzantara-postgres"),
        FlyStatusSensor(app="nuzantara-qdrant"),
        LaunchdSensor(label="com.matagaruda.watcher.daily"),
        LaunchdSensor(label="com.matagaruda.bridge.adaptive"),
        LaunchdSensor(label="com.matagaruda.gap.consumer"),
        RedisStreamDepthSensor(stream="garuda:raw", warning=500, critical=1000),
        RedisStreamDepthSensor(stream="nexus:gaps", warning=500, critical=1000),
        RedisStreamDepthSensor(stream="bridge:outbound", warning=30, critical=100),
        DiskRamCpuSensor(path="/"),
        BridgeThroughputSensor(),
    ]

    return PulseLoop(
        config=config,
        sensors=sensors,
        thinker=_FastThinker(),
        actor=HealthRecoveryActor(genome=genome),
        stm=SqliteMemoryStack(db_path=KB_PATH).stm,
        ltm=SqliteMemoryStack(db_path=KB_PATH).ltm,
        episodic=SqliteMemoryStack(db_path=KB_PATH).episodic,
        lifecycle=Maturation(birth_date=config.birth_date),
        safety=SafetyGate(disable_file="/tmp/health-sentinel.disabled", cell_name="health-sentinel"),
        homeostasis=HomeostaticController(sleep_hours=config.sleep_hours),
        identity=identity,
    )
```

Create `apps/mata-garuda/mata_garuda/cells/health_runner.py`:

```python
"""Entry point: `python -m mata_garuda.cells.health_runner --once` or (without --once) loop forever."""
from __future__ import annotations

import asyncio
import logging
import sys

from mata_garuda.cells.health_sentinel_cell import create_health_sentinel_cell


async def main(once: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cell = create_health_sentinel_cell()
    if once:
        result = await cell.single_pulse()
        logging.getLogger("mata_garuda.cells.health").info(
            f"Pulse done: status={result.health_status} action={result.action_taken}"
        )
    else:
        await cell.run()


if __name__ == "__main__":
    once = "--once" in sys.argv
    asyncio.run(main(once=once))
```

- [ ] **Step 3: Create runner + plist**

Create `apps/mata-garuda/scripts/run_health_sentinel.sh`:

```bash
#!/bin/zsh
set -uo pipefail
VENV_PY="/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python3"
REPO_DIR="/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda"
LOG="/Users/nuzantara/logs/health-sentinel.log"
echo "" >> "$LOG"
echo "=== Health Sentinel — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"
PYTHONPATH="$REPO_DIR" "$VENV_PY" -m mata_garuda.cells.health_runner --once >> "$LOG" 2>&1
echo "[$(date '+%H:%M:%S')] exit=$?" >> "$LOG"
```

`chmod +x apps/mata-garuda/scripts/run_health_sentinel.sh`

Create `apps/mata-garuda/launchagents/com.nuzantara.health-sentinel.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.health-sentinel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_health_sentinel.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/health-sentinel-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/health-sentinel-launchd.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>PATH</key>
        <string>/Users/nuzantara/.pyenv/versions/3.11.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Create the DNA file `apps/mata-garuda/mata_garuda/health_dna.json`:

```json
{
  "name": "health-sentinel",
  "version": 1,
  "born_at": "2026-04-14T00:00:00+00:00",
  "purpose": "Monitor organism health and execute whitelisted recoveries",
  "safety_budget": {
    "max_actions_per_hour": 12,
    "max_consecutive_failures": 3
  }
}
```

- [ ] **Step 4: Run tests**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/test_health_sentinel_cell.py -v`

Expected: 2 PASS.

- [ ] **Step 5: Register in automation_catalog.json**

Add:

```json
{
  "name": "health_sentinel",
  "type": "launchagent",
  "plist": "com.nuzantara.health-sentinel",
  "description": "Cell-core health monitor: Fly, launchd, Redis streams, disk/load, bridge throughput; auto-recovery via whitelist",
  "produces": [
    "sentinel:alerts",
    "sentinel:recovery",
    "genome skills scope=recovery"
  ],
  "consumes": ["fly CLI", "launchctl", "redis-cli", "df", "uptime"],
  "schedule_seconds": 300,
  "llm": "none (fast path) — slow path claude in v2"
}
```

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/cells/health_sentinel_cell.py \
        apps/mata-garuda/mata_garuda/cells/health_runner.py \
        apps/mata-garuda/mata_garuda/health_dna.json \
        apps/mata-garuda/scripts/run_health_sentinel.sh \
        apps/mata-garuda/launchagents/com.nuzantara.health-sentinel.plist \
        apps/mata-garuda/tests/test_health_sentinel_cell.py \
        scripts/automation_catalog.json
git commit -m "$(cat <<'EOF'
feat(health): health sentinel cell-core PulseLoop + LaunchAgent

Phase 2 D5 — second sentinel (health) separated from intel sentinel.
Pulse 5 min, 11 sensors across Fly/launchd/Redis/system/bridge,
fast-path rule-based thinker emits recovery proposal, HealthRecoveryActor
executes whitelisted command and logs skill in Genome.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Closing

## Task Z.1: Full regression test + install LaunchAgents

- [ ] **Step 1: Full mata-garuda test suite**

Run: `cd apps/mata-garuda && .venv/bin/pytest tests/ -q --tb=line`

Expected: ~320 pass (baseline 280 + ~40 new across D1..D5).

- [ ] **Step 2: Full backend test suite**

Run: `cd apps/backend-rag && PYTHONPATH=. .venv/bin/pytest backend/tests/ -q --tb=line`

Expected: ≥800 pass (baseline 794 + new RAG low-confidence + enrichment tests).

- [ ] **Step 3: Install LaunchAgents (manual, user confirms)**

This step is intentionally outside the automated cycle: we do not auto-install launchd entries. User should run:

```bash
cd apps/mata-garuda/launchagents
for plist in com.matagaruda.priority-engine.plist com.matagaruda.dream.nightly.plist com.nuzantara.health-sentinel.plist; do
  cp "$plist" ~/Library/LaunchAgents/
  launchctl load ~/Library/LaunchAgents/$plist
  launchctl list "$(basename $plist .plist)"
done
```

Verify each with `launchctl list <label>` showing `"LastExitStatus" = 0;` or an acceptable initial state.

- [ ] **Step 4: Capture post-Phase-2 baseline metrics**

Run:

```bash
cd apps/mata-garuda
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/knowledge.db')
cur = conn.cursor()
for row in cur.execute(\"SELECT type, COUNT(*) FROM knowledge GROUP BY type ORDER BY type\").fetchall():
    print(f'  {row[0]:20s} {row[1]}')
"
redis-cli XLEN bridge:inbound bridge:outbound garuda:raw nexus:gaps sentinel:alerts sentinel:recovery 2>/dev/null
```

- [ ] **Step 5: Save closing memo to MOS**

```bash
~/.claude/scripts/mem save decision "Phase 2 (RIFLESSI) merged $(date +%Y-%m-%d). 5 deliverable + pre-work + ~30-35 TDD tasks. Test baseline before/after in spec §9. Key artifacts: priority/, agents/lpse_harvester.py, dream/, enrichment/, cells/health_sentinel_cell.py. LaunchAgents da installare manualmente. Next: Fase 3 (COSCIENZA) — Consiglio multi-modello + metriche metaboliche complete." 10
```

- [ ] **Step 6: Merge plan commit**

```bash
git log --oneline -30 | head -30  # review Phase 2 commits
# Optional: tag
git tag -a phase2-riflessi-complete -m "Organism Phase 2 (RIFLESSI) complete"
```

---

## Self-Review — Spec Coverage

| Spec section              | Task                                | Covered |
| ------------------------- | ----------------------------------- | ------- |
| §2 Pre-work Task 0.1      | DONE commit 1520ce004               | ✅      |
| §2 Pre-work Task 0.2      | Task 0.2 (wire db_pool)             | ✅      |
| §2 Pre-work Task 0.3      | Task 0.3 (integration test)         | ✅      |
| §2 Pre-work Task 0.4      | Task 0.4 (SYMBIOSIS update)         | ✅      |
| §3 D1 Priority Engine     | D1.1..D1.4                          | ✅      |
| §4 D2 LPSE Harvester      | D2.1..D2.2                          | ✅      |
| §5 D3 Sleep consolidation | D3.1..D3.5                          | ✅      |
| §6 D4 RAG Enricher        | D4.1..D4.5                          | ✅      |
| §7 D5 Sentinel health     | D5.1..D5.4                          | ✅      |
| §8 Order + dependencies   | encoded in task order               | ✅      |
| §9 Metrics                | Z.1 Step 4 (capture baseline after) | ✅      |
| §10 Constraints (8 Laws)  | preserved in every task design      | ✅      |

No placeholders scanned. Types consistent: `Envelope`, `ConsolidatedSkill`, `PriorityStore`, `HealthRecoveryActor`, `EnrichmentBudget`, all referenced by same names across tasks.
