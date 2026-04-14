# Organism Phase 1 — Sinapsi (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect Mata Garuda (Pro) and Backend RAG (Fly.io) via a bidirectional bridge, consume the 552 pending gaps in `nexus:gaps`, and add the LHKPN harvester that fills 4 of the 8 gap types.

**Architecture:** Bridge bidirezionale (cursor-based pull + POST push, polling adattivo) + gap consumer worker + new harvester agent. Standard envelope a 5 campi su tutti gli stream nuovi (`bridge:outbound`, `bridge:inbound`). Backend espone 3 endpoint nuovi e 1 tabella `bridge_outbox` con retention 30gg.

**Tech Stack:** Python 3.11+, Pydantic v2, redis-cli (subprocess), asyncpg, FastAPI, BeautifulSoup4 (già disponibile via httpx), pytest, launchd. Zero nuove dipendenze.

**Reference:** `docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md`

---

## File Structure

### Files to create

```
apps/mata-garuda/mata_garuda/
├── bridge/
│   ├── __init__.py                 # package marker
│   ├── envelope.py                 # Envelope Pydantic model (5 fields)
│   ├── nerve.py                    # Pull + Push worker (cursor-based)
│   └── cursor.py                   # Atomic file cursor read/write
├── workers/
│   └── gap_consumer.py             # nexus:gaps consumer (dispatch by type)
├── agents/
│   ├── lhkpn_harvester.py          # New harvester
│   └── lhkpn_harvester_GENOME.md   # GENOME constraints
└── tools/
    └── lhkpn_tools.py              # scrape_lhkpn_search, scrape_lhkpn_profile

apps/backend-rag/backend/
├── migrations/
│   └── migration_101_bridge_outbox.py    # bridge_outbox table
├── app/routers/
│   └── bridge.py                          # 3 endpoints (events, ingest article, ingest enrichment)
└── services/bridge/
    ├── __init__.py
    └── outbox.py                          # insert_outbox_event() helper

apps/mata-garuda/tests/
├── test_envelope.py
├── test_cursor.py
├── test_nerve.py
├── test_gap_consumer.py
├── test_lhkpn_harvester.py
└── test_lhkpn_tools.py

apps/backend-rag/backend/tests/
├── routers/test_bridge_router.py
├── services/test_outbox.py
└── services/test_handlers_outbox.py

LaunchAgents (~/Library/LaunchAgents/):
├── com.matagaruda.bridge.adaptive.plist
└── com.matagaruda.gap.consumer.plist

Scripts (~/scripts/):
├── matagaruda-bridge.sh
└── matagaruda-gap-consumer.sh
```

### Files to modify

```
apps/mata-garuda/mata_garuda/config.py
  → Add STREAM_BRIDGE_OUTBOUND, STREAM_BRIDGE_INBOUND, STREAM_NEXUS_GAPS, BRIDGE_API_KEY_ENV

apps/backend-rag/backend/services/events/handlers.py
  → on_client_changed: insert outbox events (crm.client_created, crm.client_sector_changed)
  → on_practice_status_changed: insert outbox events (crm.practice_completed, crm.practice_created)
  → on_compliance_alert: insert outbox events (compliance.critical_alert)

apps/backend-rag/backend/services/rag/answer.py
  → After answer with confidence < 0.3, insert outbox event (rag.low_confidence) with 24h dedup

apps/backend-rag/backend/app/setup/router_registration.py
  → Register bridge router

scripts/automation_catalog.json
  → Add 3 entries: bridge.adaptive, gap.consumer, lhkpn_harvester

~/.agent/decisions/job_registry.json
  → Add 2 entries for bridge + gap consumer (Sentinel monitoring)

~/.nuzantara-secrets.env
  → Add BRIDGE_API_KEY (32-char random)
```

---

## Conventions

- **Branch:** create `feat/organism-phase1-sinapsi` from `main` before Task 1
- **Worktree:** if you have `superpowers:using-git-worktrees` available, use it; otherwise work in main repo on the branch
- **Commits:** one per task (after all tests in that task pass)
- **Test runner Mata Garuda:** `cd apps/mata-garuda && source .venv/bin/activate && pytest tests/<file> -v`
- **Test runner Backend:** `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/<file> -v`
- **Logger:** always `logging.getLogger(__name__)`, never `print()`
- **Type hints:** full annotations on every function signature
- **Pydantic:** v2 syntax (`model_config = ConfigDict(...)`, `Field(default_factory=...)`)
- **DRY/YAGNI/TDD:** every behavioral feature has a test written FIRST that fails

---

## Task 1: Bridge envelope model (Pydantic)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/bridge/__init__.py`
- Create: `apps/mata-garuda/mata_garuda/bridge/envelope.py`
- Test: `apps/mata-garuda/tests/test_envelope.py`

- [ ] **Step 1: Create empty package marker**

```bash
mkdir -p apps/mata-garuda/mata_garuda/bridge
touch apps/mata-garuda/mata_garuda/bridge/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `apps/mata-garuda/tests/test_envelope.py`:

```python
"""Tests for bridge envelope model."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from mata_garuda.bridge.envelope import Envelope


def test_envelope_minimal_creation():
    """Envelope with only required fields should validate."""
    env = Envelope(
        type="crm.client_created",
        source="bridge",
        priority=3,
        payload={"client_id": 42},
    )
    assert env.type == "crm.client_created"
    assert env.source == "bridge"
    assert env.priority == 3
    assert env.payload == {"client_id": 42}
    # Auto-generated fields
    assert env.id is not None
    assert len(env.id) == 36  # UUID v4 string
    assert env.timestamp.endswith("+08:00")  # WITA timezone


def test_envelope_priority_validation():
    """Priority must be 1-5."""
    with pytest.raises(ValidationError):
        Envelope(type="x", source="x", priority=0, payload={})
    with pytest.raises(ValidationError):
        Envelope(type="x", source="x", priority=6, payload={})


def test_envelope_type_dot_notation():
    """Type must use dot notation (category.subtype)."""
    # Valid
    Envelope(type="crm.client_created", source="b", priority=3, payload={})
    # Invalid: no dot
    with pytest.raises(ValidationError):
        Envelope(type="invalid", source="b", priority=3, payload={})


def test_envelope_to_redis_dict():
    """to_redis_dict() returns flat dict ready for XADD."""
    env = Envelope(
        type="harvest.lhkpn",
        source="lhkpn_harvester",
        priority=2,
        payload={"nip": "123"},
    )
    d = env.to_redis_dict()
    assert d["type"] == "harvest.lhkpn"
    assert d["source"] == "lhkpn_harvester"
    assert d["priority"] == "2"  # XADD requires strings
    assert isinstance(d["payload"], str)  # JSON-encoded
    parsed = json.loads(d["payload"])
    assert parsed == {"nip": "123"}


def test_envelope_from_redis_dict_roundtrip():
    """from_redis_dict() can reconstruct an envelope from XREADGROUP output."""
    original = Envelope(
        type="gap.missing_nip",
        source="gap_detector",
        priority=2,
        payload={"person_name": "Budi"},
    )
    redis_data = original.to_redis_dict()
    restored = Envelope.from_redis_dict(redis_data)
    assert restored.type == original.type
    assert restored.source == original.source
    assert restored.priority == original.priority
    assert restored.payload == original.payload
    assert restored.id == original.id


def test_envelope_filter_by_prefix():
    """Type prefix matching for consumer routing."""
    env = Envelope(type="crm.client_created", source="b", priority=3, payload={})
    assert env.matches_prefix("crm")
    assert env.matches_prefix("crm.client")
    assert not env.matches_prefix("intel")
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd apps/mata-garuda && source .venv/bin/activate
pytest tests/test_envelope.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mata_garuda.bridge.envelope'`

- [ ] **Step 4: Implement the envelope**

Create `apps/mata-garuda/mata_garuda/bridge/envelope.py`:

```python
"""
Mata Garuda — Bridge Envelope.

Standard envelope a 5 campi obbligatori per tutti i messaggi sui nuovi stream
(bridge:outbound, bridge:inbound, organism:metrics).

Stream esistenti (garuda:raw, nexus:gaps, garuda:enriched, garuda:alerts) NON
sono migrati subito — lo saranno gradualmente quando i consumer vengono
riscritti.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §3
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


WITA = timezone(timedelta(hours=8))


def _now_wita() -> str:
    """Current ISO 8601 timestamp in WITA timezone."""
    return datetime.now(WITA).isoformat(timespec="seconds")


class Envelope(BaseModel):
    """Standard envelope per tutti gli stream nuovi.

    5 campi obbligatori, payload libero. Puro JSON, zero dipendenze esterne
    oltre pydantic. Compatibile con redis-cli XADD/XREADGROUP.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = Field(..., description="dot notation: category.subtype")
    source: str = Field(..., description="organo produttore")
    timestamp: str = Field(default_factory=_now_wita)
    priority: int = Field(..., ge=1, le=5, description="1=urgente, 5=bassa")
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _validate_dot_notation(cls, v: str) -> str:
        if "." not in v:
            raise ValueError(f"type must use dot notation (got {v!r})")
        return v

    def to_redis_dict(self) -> dict[str, str]:
        """Flat dict ready for redis-cli XADD (all values stringified)."""
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp,
            "priority": str(self.priority),
            "payload": json.dumps(self.payload, ensure_ascii=False),
        }

    @classmethod
    def from_redis_dict(cls, data: dict[str, str]) -> "Envelope":
        """Reconstruct an Envelope from XREADGROUP output."""
        return cls(
            id=data["id"],
            type=data["type"],
            source=data["source"],
            timestamp=data["timestamp"],
            priority=int(data["priority"]),
            payload=json.loads(data["payload"]) if data.get("payload") else {},
        )

    def matches_prefix(self, prefix: str) -> bool:
        """True if type starts with prefix (exact or with following dot)."""
        return self.type == prefix or self.type.startswith(prefix + ".")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_envelope.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/bridge/__init__.py \
        apps/mata-garuda/mata_garuda/bridge/envelope.py \
        apps/mata-garuda/tests/test_envelope.py
git commit -m "feat(bridge): add Envelope model with 5 mandatory fields and dot-notation type"
```

---

## Task 2: Bridge cursor (atomic file read/write)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/bridge/cursor.py`
- Test: `apps/mata-garuda/tests/test_cursor.py`

- [ ] **Step 1: Write the failing test**

Create `apps/mata-garuda/tests/test_cursor.py`:

```python
"""Tests for bridge cursor — atomic file read/write."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mata_garuda.bridge.cursor import BridgeCursor


def test_cursor_read_missing_file_returns_zero(tmp_path: Path):
    """Reading a non-existent cursor file returns 0 (start from beginning)."""
    cursor = BridgeCursor(tmp_path / "cursor.json")
    assert cursor.read() == 0


def test_cursor_write_then_read(tmp_path: Path):
    """Write then read returns the value."""
    cursor = BridgeCursor(tmp_path / "cursor.json")
    cursor.write(1234)
    assert cursor.read() == 1234


def test_cursor_write_overwrites(tmp_path: Path):
    """Subsequent writes overwrite the value."""
    cursor = BridgeCursor(tmp_path / "cursor.json")
    cursor.write(1234)
    cursor.write(5678)
    assert cursor.read() == 5678


def test_cursor_write_creates_parent_dir(tmp_path: Path):
    """Write creates parent directories if missing."""
    cursor = BridgeCursor(tmp_path / "deep" / "nested" / "cursor.json")
    cursor.write(42)
    assert cursor.read() == 42


def test_cursor_atomic_write_no_partial_file(tmp_path: Path):
    """Atomic write uses tmp file + rename — no partial files visible."""
    cursor_path = tmp_path / "cursor.json"
    cursor = BridgeCursor(cursor_path)
    cursor.write(999)
    # No .tmp file left behind
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []
    # Final file is valid JSON
    data = json.loads(cursor_path.read_text())
    assert data == {"last_id": 999}


def test_cursor_corrupt_file_returns_zero(tmp_path: Path):
    """A corrupt cursor file returns 0 (safe degradation)."""
    cursor_path = tmp_path / "cursor.json"
    cursor_path.write_text("not valid json {{{")
    cursor = BridgeCursor(cursor_path)
    assert cursor.read() == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_cursor.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement BridgeCursor**

Create `apps/mata-garuda/mata_garuda/bridge/cursor.py`:

```python
"""
Mata Garuda — Bridge Cursor.

Atomic file-based cursor per il polling Pull (Fly→Pro). Salva l'ultimo id
processato dalla outbox del backend in ~/.agent/decisions/bridge_cursor.json.

Atomic write: tmp file + rename per evitare cursor corrotti su crash.
Corrupt file → torna 0 (safe degradation, ricomincia dall'inizio).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("mata_garuda.bridge.cursor")


class BridgeCursor:
    """File-based cursor per la outbox del backend."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read(self) -> int:
        """Return last_id consumed, or 0 if missing/corrupt."""
        if not self.path.exists():
            return 0
        try:
            data = json.loads(self.path.read_text())
            return int(data.get("last_id", 0))
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("Corrupt cursor at %s: %s — returning 0", self.path, e)
            return 0

    def write(self, last_id: int) -> None:
        """Atomically write last_id to disk (tmp + rename)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps({"last_id": int(last_id)}))
        os.replace(tmp_path, self.path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_cursor.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/bridge/cursor.py \
        apps/mata-garuda/tests/test_cursor.py
git commit -m "feat(bridge): add BridgeCursor with atomic write-rename pattern"
```

---

## Task 3: Backend migration 101 — `bridge_outbox` table

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_101_bridge_outbox.py`
- Test: `apps/backend-rag/backend/tests/migrations/test_migration_101.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/migrations/test_migration_101.py`:

```python
"""Test migration 101 (bridge_outbox table) — apply and rollback."""
from __future__ import annotations

import pytest
import asyncpg

from backend.migrations.migration_101_bridge_outbox import apply, rollback


@pytest.mark.asyncio
async def test_migration_101_apply_creates_table(pg_test_conn: asyncpg.Connection):
    """apply() creates bridge_outbox with correct schema and indexes."""
    await apply(pg_test_conn)

    # Table exists
    exists = await pg_test_conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_name = 'bridge_outbox')"
    )
    assert exists is True

    # Columns present
    cols = await pg_test_conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'bridge_outbox' ORDER BY ordinal_position"
    )
    col_names = [r["column_name"] for r in cols]
    assert col_names == ["id", "type", "payload", "created_at"]

    # Indexes present
    idx = await pg_test_conn.fetch(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'bridge_outbox'"
    )
    idx_names = {r["indexname"] for r in idx}
    assert "idx_outbox_id" in idx_names or "bridge_outbox_pkey" in idx_names
    assert "idx_outbox_type" in idx_names

    # Insert + select roundtrip
    await pg_test_conn.execute(
        "INSERT INTO bridge_outbox (type, payload) VALUES ($1, $2::jsonb)",
        "crm.client_created",
        '{"client_id": 42}',
    )
    row = await pg_test_conn.fetchrow(
        "SELECT type, payload FROM bridge_outbox WHERE type = $1",
        "crm.client_created",
    )
    assert row["type"] == "crm.client_created"
    assert row["payload"] == {"client_id": 42}

    # Cleanup
    await rollback(pg_test_conn)


@pytest.mark.asyncio
async def test_migration_101_rollback_drops_table(pg_test_conn: asyncpg.Connection):
    """rollback() drops the table cleanly."""
    await apply(pg_test_conn)
    await rollback(pg_test_conn)

    exists = await pg_test_conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_name = 'bridge_outbox')"
    )
    assert exists is False


@pytest.mark.asyncio
async def test_migration_101_idempotent_apply(pg_test_conn: asyncpg.Connection):
    """apply() can be run twice without error (uses IF NOT EXISTS)."""
    await apply(pg_test_conn)
    await apply(pg_test_conn)  # second time should not raise
    await rollback(pg_test_conn)
```

If `pg_test_conn` fixture doesn't exist in your conftest, add it to `apps/backend-rag/backend/tests/migrations/conftest.py`:

```python
"""Conftest for migration tests."""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
import asyncpg


@pytest_asyncio.fixture
async def pg_test_conn():
    """Real PG connection for migration tests.

    Requires TEST_DATABASE_URL env var (defaults to local test DB).
    """
    dsn = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/nuzantara_test",
    )
    conn = await asyncpg.connect(dsn)
    yield conn
    await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/migrations/test_migration_101.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.migrations.migration_101_bridge_outbox'`

- [ ] **Step 3: Implement the migration**

Create `apps/backend-rag/backend/migrations/migration_101_bridge_outbox.py`:

```python
"""
Migration 101: bridge_outbox table for Pro<->Fly bidirectional bridge.

Purpose:
- Accumulate events (crm.*, compliance.*, rag.*) for the Pro to pull via
  GET /api/bridge/events?after_id={cursor}
- BIGSERIAL id is used as the cursor (monotonic, gap-free, timezone-free)
- 30-day retention via separate cron (DELETE WHERE created_at < NOW() - INTERVAL '30 days')

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4

Author: Claude Opus 4.6
Date: 2026-04-14
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply migration 101 — create bridge_outbox table and indexes."""
    logger.info("Applying migration 101: bridge_outbox table")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bridge_outbox (
            id BIGSERIAL PRIMARY KEY,
            type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    logger.info("Created table bridge_outbox")

    # Note: id index implicit via PRIMARY KEY, but we add a named idx for
    # clarity in monitoring queries.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_id ON bridge_outbox (id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_type ON bridge_outbox (type);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_created_at
            ON bridge_outbox (created_at);
    """)
    logger.info("Created indexes on bridge_outbox (id, type, created_at)")

    logger.info("Applied migration 101: bridge_outbox table")


async def rollback(conn: Any) -> None:
    """Rollback migration 101 — drop bridge_outbox table."""
    logger.info("Rolling back migration 101: bridge_outbox table")

    await conn.execute("DROP INDEX IF EXISTS idx_outbox_created_at;")
    await conn.execute("DROP INDEX IF EXISTS idx_outbox_type;")
    await conn.execute("DROP INDEX IF EXISTS idx_outbox_id;")
    await conn.execute("DROP TABLE IF EXISTS bridge_outbox;")

    logger.info("Rolled back migration 101: bridge_outbox table")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=. pytest backend/tests/migrations/test_migration_101.py -v
```

Expected: PASS (3 tests). If `TEST_DATABASE_URL` isn't set and there's no local PG, document the skip with `pytest -k test_migration_101 --collect-only` and proceed manually:

```bash
# Manual apply check (only if no test DB):
psql "$DATABASE_URL" -c "\d bridge_outbox"
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_101_bridge_outbox.py \
        apps/backend-rag/backend/tests/migrations/
git commit -m "feat(backend): add migration 101 — bridge_outbox table"
```

---

## Task 4: Backend `outbox` service helper

**Files:**

- Create: `apps/backend-rag/backend/services/bridge/__init__.py`
- Create: `apps/backend-rag/backend/services/bridge/outbox.py`
- Test: `apps/backend-rag/backend/tests/services/test_outbox.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/services/test_outbox.py`:

```python
"""Tests for outbox helper."""
from __future__ import annotations

import pytest
import asyncpg

from backend.services.bridge.outbox import insert_outbox_event, fetch_outbox_events
from backend.migrations.migration_101_bridge_outbox import apply, rollback


@pytest.mark.asyncio
async def test_insert_outbox_event(pg_test_conn: asyncpg.Connection):
    """insert_outbox_event() inserts a row and returns the id."""
    await apply(pg_test_conn)
    try:
        new_id = await insert_outbox_event(
            pg_test_conn,
            event_type="crm.client_created",
            payload={"client_id": 42, "email": "t@x"},
        )
        assert isinstance(new_id, int) and new_id > 0

        row = await pg_test_conn.fetchrow(
            "SELECT type, payload FROM bridge_outbox WHERE id = $1", new_id
        )
        assert row["type"] == "crm.client_created"
        assert row["payload"] == {"client_id": 42, "email": "t@x"}
    finally:
        await rollback(pg_test_conn)


@pytest.mark.asyncio
async def test_fetch_outbox_events_after_id(pg_test_conn: asyncpg.Connection):
    """fetch_outbox_events() returns rows after the given cursor."""
    await apply(pg_test_conn)
    try:
        id1 = await insert_outbox_event(pg_test_conn, "crm.client_created", {"a": 1})
        id2 = await insert_outbox_event(pg_test_conn, "crm.practice_created", {"b": 2})
        id3 = await insert_outbox_event(pg_test_conn, "rag.low_confidence", {"c": 3})

        rows = await fetch_outbox_events(pg_test_conn, after_id=id1, limit=10)
        assert len(rows) == 2
        assert rows[0]["id"] == id2
        assert rows[1]["id"] == id3
        assert rows[0]["type"] == "crm.practice_created"
        assert rows[0]["payload"] == {"b": 2}
    finally:
        await rollback(pg_test_conn)


@pytest.mark.asyncio
async def test_fetch_outbox_events_respects_limit(pg_test_conn: asyncpg.Connection):
    """limit caps the number of returned rows."""
    await apply(pg_test_conn)
    try:
        for i in range(5):
            await insert_outbox_event(pg_test_conn, "crm.client_created", {"i": i})
        rows = await fetch_outbox_events(pg_test_conn, after_id=0, limit=3)
        assert len(rows) == 3
    finally:
        await rollback(pg_test_conn)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/test_outbox.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the helper**

Create `apps/backend-rag/backend/services/bridge/__init__.py`:

```python
"""Bridge service — outbox helpers for Pro<->Fly bidirectional bridge."""
```

Create `apps/backend-rag/backend/services/bridge/outbox.py`:

```python
"""
Bridge outbox helper.

The outbox accumulates events that the Pro will pull via
GET /api/bridge/events?after_id=<cursor>.

Used by EventBus handlers (handlers.py) and the RAG low-confidence trigger.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


# Whitelisted event types — anything else is rejected to keep the contract tight.
ALLOWED_TYPES: frozenset[str] = frozenset({
    # Phase 1
    "crm.client_created",
    "crm.client_sector_changed",
    "crm.practice_completed",
    "crm.practice_created",
    # Phase 2 (entries pre-allowed so Phase 2 doesn't need a migration)
    "compliance.critical_alert",
    "rag.low_confidence",
})


async def insert_outbox_event(
    conn: asyncpg.Connection,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    """Insert an event into bridge_outbox. Returns the new BIGSERIAL id.

    Raises ValueError if event_type is not in ALLOWED_TYPES.
    """
    if event_type not in ALLOWED_TYPES:
        raise ValueError(
            f"event_type {event_type!r} not in ALLOWED_TYPES "
            f"({sorted(ALLOWED_TYPES)})"
        )

    row = await conn.fetchrow(
        "INSERT INTO bridge_outbox (type, payload) "
        "VALUES ($1, $2::jsonb) RETURNING id",
        event_type,
        json.dumps(payload, ensure_ascii=False),
    )
    new_id = int(row["id"])
    logger.debug("Inserted outbox event id=%d type=%s", new_id, event_type)
    return new_id


async def fetch_outbox_events(
    conn: asyncpg.Connection,
    after_id: int,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch events with id > after_id, ordered by id, capped at limit.

    Returns list of dicts with keys: id, type, payload, created_at (str).
    """
    rows = await conn.fetch(
        "SELECT id, type, payload, created_at "
        "FROM bridge_outbox "
        "WHERE id > $1 "
        "ORDER BY id ASC "
        "LIMIT $2",
        int(after_id),
        int(limit),
    )
    return [
        {
            "id": int(r["id"]),
            "type": r["type"],
            "payload": r["payload"],  # asyncpg auto-decodes JSONB
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=. pytest backend/tests/services/test_outbox.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/bridge/ \
        apps/backend-rag/backend/tests/services/test_outbox.py
git commit -m "feat(backend): add bridge.outbox helpers (insert_outbox_event, fetch_outbox_events)"
```

---

## Task 5: Backend `bridge` router (3 endpoints)

**Files:**

- Create: `apps/backend-rag/backend/app/routers/bridge.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`
- Test: `apps/backend-rag/backend/tests/routers/test_bridge_router.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/routers/test_bridge_router.py`:

```python
"""Tests for /api/bridge/* endpoints."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.migrations.migration_101_bridge_outbox import apply, rollback
from backend.services.bridge.outbox import insert_outbox_event


VALID_KEY = "test-bridge-key-12345"


@pytest.fixture(autouse=True)
def set_bridge_key(monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", VALID_KEY)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_get_events_unauthorized(client):
    """Missing X-Bridge-Auth header returns 401."""
    r = client.get("/api/bridge/events?after_id=0")
    assert r.status_code == 401


def test_get_events_wrong_key(client):
    """Wrong key returns 401."""
    r = client.get(
        "/api/bridge/events?after_id=0",
        headers={"X-Bridge-Auth": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_events_returns_outbox(pg_test_conn, client):
    """Authorized GET returns events after cursor with last_id."""
    await apply(pg_test_conn)
    try:
        id1 = await insert_outbox_event(pg_test_conn, "crm.client_created", {"a": 1})
        id2 = await insert_outbox_event(pg_test_conn, "crm.practice_created", {"b": 2})

        r = client.get(
            f"/api/bridge/events?after_id=0&limit=50",
            headers={"X-Bridge-Auth": VALID_KEY},
        )
        assert r.status_code == 200
        body = r.json()
        assert "events" in body
        assert "last_id" in body
        assert len(body["events"]) >= 2
        assert body["last_id"] == id2
    finally:
        await rollback(pg_test_conn)


def test_post_ingest_article_unauthorized(client):
    """Missing key on ingest returns 401."""
    r = client.post("/api/bridge/ingest/article", json={"article_id": "x"})
    assert r.status_code == 401


def test_post_ingest_article_minimal(client):
    """Authorized POST returns 200 with status."""
    r = client.post(
        "/api/bridge/ingest/article",
        headers={"X-Bridge-Auth": VALID_KEY},
        json={
            "article_id": "abc-123",
            "title": "Test article",
            "body_mdx": "# Hello",
            "topic": "test",
        },
    )
    # 200 = published; 202 = queued for processing — both are acceptable
    assert r.status_code in (200, 202)
    body = r.json()
    assert body.get("article_id") == "abc-123"
    assert body.get("status") in ("published", "queued")


def test_post_ingest_enrichment_minimal(client):
    """Authorized POST enrichment returns 200 with vector_id."""
    r = client.post(
        "/api/bridge/ingest/enrichment",
        headers={"X-Bridge-Auth": VALID_KEY},
        json={
            "kb_entry_id": "kb-1",
            "content": "Test enrichment text",
            "source": "lhkpn_harvester",
        },
    )
    assert r.status_code in (200, 202)
    body = r.json()
    assert body.get("status") in ("indexed", "queued")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/routers/test_bridge_router.py -v
```

Expected: FAIL — router missing.

- [ ] **Step 3: Implement the router**

Create `apps/backend-rag/backend/app/routers/bridge.py`:

```python
"""
Bridge router — Pro<->Fly bidirectional bridge.

3 endpoints:
- GET  /api/bridge/events           — Pro pulls outbox events
- POST /api/bridge/ingest/article   — Pro pushes a published article
- POST /api/bridge/ingest/enrichment — Pro pushes a KB enrichment

Auth: X-Bridge-Auth header must match BRIDGE_API_KEY env var.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.services.bridge.outbox import fetch_outbox_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bridge", tags=["bridge"])


def _check_auth(x_bridge_auth: str | None) -> None:
    """Raise 401 if header doesn't match BRIDGE_API_KEY."""
    expected = os.getenv("BRIDGE_API_KEY", "")
    if not expected:
        logger.error("BRIDGE_API_KEY not set in environment")
        raise HTTPException(status_code=503, detail="Bridge auth not configured")
    if not x_bridge_auth or x_bridge_auth != expected:
        raise HTTPException(status_code=401, detail="Invalid bridge credentials")


# ── GET /api/bridge/events ──────────────────────────────────────────────


class EventsResponse(BaseModel):
    events: list[dict[str, Any]]
    last_id: int


@router.get("/events", response_model=EventsResponse)
async def get_events(
    request: Request,
    after_id: int = Query(0, ge=0, description="Return events with id > after_id"),
    limit: int = Query(50, ge=1, le=500, description="Max events per request"),
    x_bridge_auth: str | None = Header(default=None, alias="X-Bridge-Auth"),
) -> EventsResponse:
    """Pro polls this endpoint to pull queued events from the outbox."""
    _check_auth(x_bridge_auth)

    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        events = await fetch_outbox_events(conn, after_id=after_id, limit=limit)

    last_id = events[-1]["id"] if events else after_id
    return EventsResponse(events=events, last_id=last_id)


# ── POST /api/bridge/ingest/article ─────────────────────────────────────


class ArticleIngestRequest(BaseModel):
    article_id: str = Field(..., description="UUID generated by Intel Scraper")
    title: str
    body_mdx: str
    topic: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArticleIngestResponse(BaseModel):
    article_id: str
    status: str  # "published" | "queued"


@router.post("/ingest/article", response_model=ArticleIngestResponse)
async def ingest_article(
    body: ArticleIngestRequest,
    x_bridge_auth: str | None = Header(default=None, alias="X-Bridge-Auth"),
) -> ArticleIngestResponse:
    """Pro pushes a published article. Currently logs and queues — full
    CMS integration deferred to Phase 1.5 (post-MVP).
    """
    _check_auth(x_bridge_auth)
    logger.info(
        "Bridge ingest article: id=%s title=%s len=%d",
        body.article_id,
        body.title[:80],
        len(body.body_mdx),
    )
    # Phase 1: log + return queued. Actual MDX write happens in Phase 1.5
    # via the existing post-publish-poller. The Pro retries until 200.
    return ArticleIngestResponse(article_id=body.article_id, status="queued")


# ── POST /api/bridge/ingest/enrichment ──────────────────────────────────


class EnrichmentIngestRequest(BaseModel):
    kb_entry_id: str
    content: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnrichmentIngestResponse(BaseModel):
    kb_entry_id: str
    status: str  # "indexed" | "queued"


@router.post("/ingest/enrichment", response_model=EnrichmentIngestResponse)
async def ingest_enrichment(
    body: EnrichmentIngestRequest,
    x_bridge_auth: str | None = Header(default=None, alias="X-Bridge-Auth"),
) -> EnrichmentIngestResponse:
    """Pro pushes a KB enrichment for the RAG. Currently queued — full
    Qdrant write deferred to Phase 2 (RAG enrichment agent).
    """
    _check_auth(x_bridge_auth)
    logger.info(
        "Bridge ingest enrichment: id=%s source=%s len=%d",
        body.kb_entry_id,
        body.source,
        len(body.content),
    )
    return EnrichmentIngestResponse(kb_entry_id=body.kb_entry_id, status="queued")
```

- [ ] **Step 4: Register the router**

Read `apps/backend-rag/backend/app/setup/router_registration.py`, then add the bridge import + registration alongside the other routers (look for the existing `from backend.app.routers import ...` block and the `app.include_router(...)` block).

```python
# Add to imports near the top of router_registration.py:
from backend.app.routers import bridge as bridge_router

# Add inside register_routers() (or equivalent function):
app.include_router(bridge_router.router)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
PYTHONPATH=. pytest backend/tests/routers/test_bridge_router.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 6: Verify import chain still works**

```bash
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/app/routers/bridge.py \
        apps/backend-rag/backend/app/setup/router_registration.py \
        apps/backend-rag/backend/tests/routers/test_bridge_router.py
git commit -m "feat(backend): add /api/bridge router (events GET, ingest article/enrichment POST)"
```

---

## Task 6: EventBus → outbox triggers (handlers.py)

**Files:**

- Modify: `apps/backend-rag/backend/services/events/handlers.py`
- Test: `apps/backend-rag/backend/tests/services/test_handlers_outbox.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/services/test_handlers_outbox.py`:

```python
"""Tests for EventBus handlers writing to bridge_outbox."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_on_client_changed_inserts_outbox_on_insert():
    """INSERT operation triggers crm.client_created in outbox."""
    from backend.services.events import handlers

    insert_mock = AsyncMock(return_value=42)

    # Mock pool.acquire() context manager
    fake_conn = MagicMock()
    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_AcquireCM(fake_conn))

    # Patch the helper used inside the handler
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        "backend.services.events.handlers.insert_outbox_event",
        insert_mock,
    )

    # Build a minimal bus stub
    bus_stub = MagicMock()
    bus_stub.subscribe = MagicMock()

    handlers.register_handlers(bus_stub, fake_pool)

    # Find the registered on_client_changed
    calls = bus_stub.subscribe.call_args_list
    on_client = next(c.args[1] for c in calls if c.args[0] == "client.changed")

    # First call: INSERT → should write outbox
    handlers._recent_events.clear()
    await on_client({"client_id": 7, "operation": "INSERT", "email": "a@b"})

    insert_mock.assert_called_once()
    args, kwargs = insert_mock.call_args
    assert args[1] == "crm.client_created"  # event_type
    assert args[2]["client_id"] == 7

    monkey.undo()


@pytest.mark.asyncio
async def test_on_client_changed_emits_sector_changed_on_update_with_sector():
    """UPDATE with sector field triggers crm.client_sector_changed."""
    from backend.services.events import handlers

    insert_mock = AsyncMock(return_value=43)
    fake_conn = MagicMock()
    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_AcquireCM(fake_conn))

    monkey = pytest.MonkeyPatch()
    monkey.setattr("backend.services.events.handlers.insert_outbox_event", insert_mock)

    bus_stub = MagicMock()
    bus_stub.subscribe = MagicMock()
    handlers.register_handlers(bus_stub, fake_pool)
    on_client = next(
        c.args[1] for c in bus_stub.subscribe.call_args_list
        if c.args[0] == "client.changed"
    )

    handlers._recent_events.clear()
    await on_client({
        "client_id": 7,
        "operation": "UPDATE",
        "changed_fields": ["sector"],
        "sector": "PMA-Tax",
    })

    insert_mock.assert_called_once()
    assert insert_mock.call_args.args[1] == "crm.client_sector_changed"

    monkey.undo()


@pytest.mark.asyncio
async def test_on_practice_status_changed_completed():
    """Practice status COMPLETED triggers crm.practice_completed."""
    from backend.services.events import handlers

    insert_mock = AsyncMock(return_value=44)
    fake_conn = MagicMock()
    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_AcquireCM(fake_conn))

    monkey = pytest.MonkeyPatch()
    monkey.setattr("backend.services.events.handlers.insert_outbox_event", insert_mock)

    bus_stub = MagicMock()
    bus_stub.subscribe = MagicMock()
    handlers.register_handlers(bus_stub, fake_pool)
    on_practice = next(
        c.args[1] for c in bus_stub.subscribe.call_args_list
        if c.args[0] == "practice.status_changed"
    )

    handlers._recent_events.clear()
    await on_practice({
        "practice_id": 100,
        "client_id": 7,
        "old_status": "in_progress",
        "new_status": "completed",
    })

    insert_mock.assert_called_once()
    assert insert_mock.call_args.args[1] == "crm.practice_completed"

    monkey.undo()


# Helper async context manager for asyncpg pool.acquire() mocking
class _AcquireCM:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/services/test_handlers_outbox.py -v
```

Expected: FAIL — `insert_outbox_event` not yet imported in handlers.

- [ ] **Step 3: Modify handlers.py to write outbox events**

Open `apps/backend-rag/backend/services/events/handlers.py` and:

1. Add this import near the top (after `import asyncpg`):

```python
from backend.services.bridge.outbox import insert_outbox_event
```

2. Inside `on_client_changed` (around line 100, after the dedup guard but before the cache invalidation), add:

```python
        # ── Bridge outbox: notify Pro of CRM changes ─────────────────
        try:
            async with db_pool.acquire() as conn:
                if operation == "INSERT":
                    await insert_outbox_event(
                        conn,
                        event_type="crm.client_created",
                        payload={
                            "client_id": client_id,
                            "email": email,
                            "sector": payload.get("sector"),
                        },
                    )
                elif operation == "UPDATE" and "sector" in (payload.get("changed_fields") or []):
                    await insert_outbox_event(
                        conn,
                        event_type="crm.client_sector_changed",
                        payload={
                            "client_id": client_id,
                            "sector": payload.get("sector"),
                            "old_sector": payload.get("old_sector"),
                        },
                    )
        except Exception as e:
            logger.error("Bridge outbox write failed for client %s: %s", client_id, e)
```

3. Inside `on_practice_status_changed`, after the dedup guard, add:

```python
        # ── Bridge outbox: notify Pro of practice lifecycle ──────────
        try:
            async with db_pool.acquire() as conn:
                if new_status == "completed":
                    await insert_outbox_event(
                        conn,
                        event_type="crm.practice_completed",
                        payload={
                            "practice_id": practice_id,
                            "client_id": payload.get("client_id"),
                            "completed_at": payload.get("completed_at"),
                        },
                    )
                elif old_status is None and new_status in ("created", "open", "in_progress"):
                    await insert_outbox_event(
                        conn,
                        event_type="crm.practice_created",
                        payload={
                            "practice_id": practice_id,
                            "client_id": payload.get("client_id"),
                            "practice_type": payload.get("practice_type"),
                        },
                    )
        except Exception as e:
            logger.error("Bridge outbox write failed for practice %s: %s", practice_id, e)
```

4. Inside `on_compliance_alert`, after the dedup guard, add:

```python
        # ── Bridge outbox: notify Pro of critical alerts ─────────────
        if severity == "critical" and (payload.get("days_until_expiry") or 999) <= 7:
            try:
                async with db_pool.acquire() as conn:
                    await insert_outbox_event(
                        conn,
                        event_type="compliance.critical_alert",
                        payload={
                            "client_id": payload.get("client_id"),
                            "document_type": payload.get("document_type"),
                            "days_until_expiry": payload.get("days_until_expiry"),
                            "expires_at": payload.get("expires_at"),
                        },
                    )
            except Exception as e:
                logger.error("Bridge outbox write failed for compliance alert: %s", e)
```

(Read existing handler bodies for the actual variable names; the snippets above use `practice_id`, `old_status`, `new_status`, `severity` — verify they match.)

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=. pytest backend/tests/services/test_handlers_outbox.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Re-run existing handler tests to catch regressions**

```bash
PYTHONPATH=. pytest backend/tests/services/events/ -v
```

Expected: all existing tests still PASS (the new outbox writes are wrapped in try/except so they can't break the handler).

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/services/events/handlers.py \
        apps/backend-rag/backend/tests/services/test_handlers_outbox.py
git commit -m "feat(backend): EventBus handlers write outbox events for CRM + compliance"
```

---

## Task 7: RAG low-confidence trigger

**Files:**

- Modify: `apps/backend-rag/backend/services/rag/answer.py`
- Test: `apps/backend-rag/backend/tests/services/rag/test_low_confidence_trigger.py`

- [ ] **Step 1: Locate the answer function and confidence variable**

```bash
cd apps/backend-rag
grep -nE "def (answer|generate_answer|build_answer)" backend/services/rag/answer.py | head
grep -nE "confidence|evidence_score" backend/services/rag/answer.py | head -20
```

Identify the function that returns the final answer with a confidence/evidence score. Note its name and the variable name (likely `confidence_score` or `evidence_score`).

- [ ] **Step 2: Write the failing test**

Create `apps/backend-rag/backend/tests/services/rag/test_low_confidence_trigger.py`:

```python
"""Tests for RAG low-confidence outbox trigger."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_low_confidence_inserts_outbox_event():
    """When confidence < 0.3, an outbox event is inserted."""
    from backend.services.rag import answer as answer_mod

    insert_mock = AsyncMock(return_value=99)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        "backend.services.rag.answer.insert_outbox_event",
        insert_mock,
    )

    fake_conn = MagicMock()
    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_AcquireCM(fake_conn))

    await answer_mod.maybe_emit_low_confidence(
        pool=fake_pool,
        query="What is the price of foo?",
        confidence=0.2,
    )

    insert_mock.assert_called_once()
    assert insert_mock.call_args.args[1] == "rag.low_confidence"
    payload = insert_mock.call_args.args[2]
    assert payload["confidence"] == 0.2
    assert payload["query"] == "What is the price of foo?"

    monkey.undo()


@pytest.mark.asyncio
async def test_high_confidence_does_not_insert():
    """When confidence >= 0.3, no outbox event."""
    from backend.services.rag import answer as answer_mod

    insert_mock = AsyncMock(return_value=99)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        "backend.services.rag.answer.insert_outbox_event",
        insert_mock,
    )

    fake_pool = MagicMock()
    await answer_mod.maybe_emit_low_confidence(
        pool=fake_pool, query="Test", confidence=0.7
    )
    insert_mock.assert_not_called()
    monkey.undo()


@pytest.mark.asyncio
async def test_low_confidence_dedup_24h():
    """Same query within 24h is not re-inserted."""
    from backend.services.rag import answer as answer_mod

    insert_mock = AsyncMock(return_value=99)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        "backend.services.rag.answer.insert_outbox_event",
        insert_mock,
    )

    fake_conn = MagicMock()
    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_AcquireCM(fake_conn))

    answer_mod._low_confidence_dedup.clear()

    await answer_mod.maybe_emit_low_confidence(fake_pool, "same query", 0.2)
    await answer_mod.maybe_emit_low_confidence(fake_pool, "same query", 0.2)
    assert insert_mock.call_count == 1
    monkey.undo()


class _AcquireCM:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False
```

- [ ] **Step 3: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_low_confidence_trigger.py -v
```

Expected: FAIL — `maybe_emit_low_confidence` does not exist yet.

- [ ] **Step 4: Add the helper to answer.py**

In `apps/backend-rag/backend/services/rag/answer.py`, add near the top of the file (after existing imports):

```python
import hashlib
import time

from backend.services.bridge.outbox import insert_outbox_event

# Dedup window for low-confidence events (24h)
_LOW_CONFIDENCE_DEDUP_S = 24 * 3600
_low_confidence_dedup: dict[str, float] = {}


async def maybe_emit_low_confidence(
    pool,
    query: str,
    confidence: float,
) -> None:
    """If confidence < 0.3 and we haven't seen this query in 24h, write
    a rag.low_confidence event to the bridge_outbox.

    Failures are logged and swallowed — the RAG path must never fail
    because the bridge write failed.
    """
    if confidence >= 0.3:
        return

    # Dedup by query hash, 24h window
    key = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    now = time.monotonic()
    # Prune old entries
    stale = [k for k, t in _low_confidence_dedup.items() if now - t > _LOW_CONFIDENCE_DEDUP_S]
    for k in stale:
        del _low_confidence_dedup[k]
    if key in _low_confidence_dedup:
        return
    _low_confidence_dedup[key] = now

    try:
        async with pool.acquire() as conn:
            await insert_outbox_event(
                conn,
                event_type="rag.low_confidence",
                payload={
                    "query": query[:500],
                    "confidence": float(confidence),
                    "query_hash": key,
                },
            )
    except Exception as e:
        logger.error("Failed to emit rag.low_confidence event: %s", e)
```

- [ ] **Step 5: Wire the call in the answer pipeline**

Locate the function identified in Step 1 (the one that returns the final answer + confidence). At the end of that function, just before `return`, add:

```python
        # Emit low-confidence event for bridge (Pro picks it up via polling)
        try:
            await maybe_emit_low_confidence(
                pool=request.app.state.db_pool,  # adjust to actual pool reference
                query=query,
                confidence=evidence_score,  # adjust to actual variable name
            )
        except Exception as e:
            logger.warning("Low-confidence emit skipped: %s", e)
```

(Variable names depend on the existing function — read it before edit. The wrapper try/except above is defensive: it must never break the RAG.)

- [ ] **Step 6: Run test to verify it passes**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_low_confidence_trigger.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 7: Run existing RAG tests for regressions**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/ -q
```

Expected: existing tests still PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/backend-rag/backend/services/rag/answer.py \
        apps/backend-rag/backend/tests/services/rag/test_low_confidence_trigger.py
git commit -m "feat(backend): emit rag.low_confidence outbox event when confidence < 0.3"
```

---

## Task 8: Mata Garuda config — bridge constants

**Files:**

- Modify: `apps/mata-garuda/mata_garuda/config.py`
- Test: `apps/mata-garuda/tests/test_config_bridge.py`

- [ ] **Step 1: Write the failing test**

Create `apps/mata-garuda/tests/test_config_bridge.py`:

```python
"""Tests that bridge constants are exported by config."""
from mata_garuda import config


def test_bridge_stream_constants_exist():
    assert config.STREAM_BRIDGE_OUTBOUND == "bridge:outbound"
    assert config.STREAM_BRIDGE_INBOUND == "bridge:inbound"


def test_nexus_gaps_stream_exists():
    assert config.STREAM_NEXUS_GAPS == "nexus:gaps"


def test_bridge_api_key_env_name():
    assert config.BRIDGE_API_KEY_ENV == "BRIDGE_API_KEY"


def test_bridge_backend_url_default():
    assert config.BRIDGE_BACKEND_URL.startswith("https://")


def test_bridge_cursor_path_default():
    assert "bridge_cursor.json" in str(config.BRIDGE_CURSOR_PATH)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/mata-garuda && source .venv/bin/activate
pytest tests/test_config_bridge.py -v
```

Expected: FAIL — constants missing.

- [ ] **Step 3: Append constants to config.py**

Append to `apps/mata-garuda/mata_garuda/config.py`:

```python

# ── Phase 1 — Bridge & Nexus integration ──────────────────────────────
from pathlib import Path

# New streams
STREAM_BRIDGE_OUTBOUND = "bridge:outbound"
STREAM_BRIDGE_INBOUND = "bridge:inbound"
STREAM_NEXUS_GAPS = "nexus:gaps"

# Bridge config
BRIDGE_API_KEY_ENV = "BRIDGE_API_KEY"
BRIDGE_BACKEND_URL = "https://nuzantara-rag.fly.dev"
BRIDGE_CURSOR_PATH = Path.home() / ".agent" / "decisions" / "bridge_cursor.json"

# Polling cadence (seconds)
BRIDGE_POLL_INTERVAL_DAY_S = 30      # 08:00-18:00 WITA
BRIDGE_POLL_INTERVAL_NIGHT_S = 300   # 18:00-08:00 WITA
BRIDGE_PULL_LIMIT = 50
BRIDGE_PUSH_BATCH = 10
BRIDGE_HTTP_TIMEOUT_S = 15
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config_bridge.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/config.py \
        apps/mata-garuda/tests/test_config_bridge.py
git commit -m "feat(mg/config): add bridge stream constants and polling cadence"
```

---

## Task 9: Bridge nerve — pull (Fly→Pro)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/bridge/nerve.py`
- Test: `apps/mata-garuda/tests/test_nerve_pull.py`

- [ ] **Step 1: Write the failing test**

Create `apps/mata-garuda/tests/test_nerve_pull.py`:

```python
"""Tests for bridge nerve — pull side (Fly→Pro)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mata_garuda.bridge.cursor import BridgeCursor
from mata_garuda.bridge.envelope import Envelope
from mata_garuda.bridge.nerve import pull_once


def test_pull_once_no_events_does_nothing(tmp_path: Path):
    """Empty response: cursor unchanged, nothing published."""
    cursor = BridgeCursor(tmp_path / "c.json")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"events": [], "last_id": 0}

    fake_redis = MagicMock(return_value="ok")
    fake_get = MagicMock(return_value=fake_resp)

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="key",
        http_get=fake_get,
        redis_xadd=fake_redis,
    )

    assert stats == {"fetched": 0, "published": 0, "errors": 0}
    assert cursor.read() == 0
    fake_redis.assert_not_called()


def test_pull_once_publishes_each_event_and_advances_cursor(tmp_path: Path):
    """Each event becomes an Envelope and is XADDed to bridge:inbound."""
    cursor = BridgeCursor(tmp_path / "c.json")

    events = [
        {"id": 10, "type": "crm.client_created", "payload": {"a": 1}, "created_at": "2026-04-14T00:00:00+00:00"},
        {"id": 11, "type": "crm.practice_created", "payload": {"b": 2}, "created_at": "2026-04-14T00:00:01+00:00"},
    ]
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"events": events, "last_id": 11}

    fake_get = MagicMock(return_value=fake_resp)
    fake_redis = MagicMock(return_value="1-0")

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=fake_get,
        redis_xadd=fake_redis,
    )

    assert stats["fetched"] == 2
    assert stats["published"] == 2
    assert stats["errors"] == 0
    assert cursor.read() == 11
    assert fake_redis.call_count == 2
    # Verify first XADD: stream name + envelope dict
    stream, envelope_dict = fake_redis.call_args_list[0].args
    assert stream == "bridge:inbound"
    assert envelope_dict["type"] == "crm.client_created"
    assert envelope_dict["source"] == "bridge"


def test_pull_once_http_error_does_not_advance_cursor(tmp_path: Path):
    """On HTTP error cursor stays put — Pro retries next cycle."""
    cursor = BridgeCursor(tmp_path / "c.json")
    cursor.write(5)  # pretend we already consumed up to 5

    def bad_get(*a, **kw):
        raise ConnectionError("Fly is down")

    fake_redis = MagicMock()
    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=bad_get,
        redis_xadd=fake_redis,
    )

    assert stats["errors"] == 1
    assert stats["fetched"] == 0
    assert cursor.read() == 5  # unchanged
    fake_redis.assert_not_called()


def test_pull_once_unauthorized_does_not_advance(tmp_path: Path):
    """401 response: log and do nothing."""
    cursor = BridgeCursor(tmp_path / "c.json")
    cursor.write(7)

    fake_resp = MagicMock()
    fake_resp.status_code = 401
    fake_resp.text = "unauthorized"
    fake_get = MagicMock(return_value=fake_resp)
    fake_redis = MagicMock()

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="bad",
        http_get=fake_get,
        redis_xadd=fake_redis,
    )

    assert stats["errors"] == 1
    assert cursor.read() == 7
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_nerve_pull.py -v
```

Expected: FAIL — `nerve` module missing.

- [ ] **Step 3: Implement `pull_once`**

Create `apps/mata-garuda/mata_garuda/bridge/nerve.py`:

```python
"""
Mata Garuda — Bridge Nerve.

Bidirectional bridge worker between Pro (local) and Fly.io (cloud).

Pull side (this file): GET /api/bridge/events?after_id={cursor} → wrap each
event in an Envelope and XADD to bridge:inbound.

Push side: see push_once() (Task 10).

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any, Callable

from mata_garuda.bridge.cursor import BridgeCursor
from mata_garuda.bridge.envelope import Envelope
from mata_garuda.config import (
    BRIDGE_API_KEY_ENV,
    BRIDGE_BACKEND_URL,
    BRIDGE_CURSOR_PATH,
    BRIDGE_HTTP_TIMEOUT_S,
    BRIDGE_PULL_LIMIT,
    STREAM_BRIDGE_INBOUND,
)

logger = logging.getLogger("mata_garuda.bridge.nerve")


# ── Default I/O implementations (replaceable for tests) ────────────────


def _default_http_get(url: str, headers: dict[str, str], timeout: int):
    """Default HTTP GET via httpx (sync — bridge runs as a script, not async)."""
    import httpx
    return httpx.get(url, headers=headers, timeout=timeout)


def _default_redis_xadd(stream: str, fields: dict[str, str]) -> str:
    """Default XADD via redis-cli subprocess (matches existing MG pattern)."""
    args = ["redis-cli", "XADD", stream, "*"]
    for k, v in fields.items():
        args.extend([k, v])
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"redis-cli XADD failed: {result.stderr.strip()}")
    return result.stdout.strip()


# ── Pull side ──────────────────────────────────────────────────────────


def pull_once(
    cursor: BridgeCursor,
    backend_url: str,
    api_key: str,
    http_get: Callable = _default_http_get,
    redis_xadd: Callable = _default_redis_xadd,
    limit: int = BRIDGE_PULL_LIMIT,
    timeout: int = BRIDGE_HTTP_TIMEOUT_S,
) -> dict[str, int]:
    """Run one pull cycle. Returns stats {fetched, published, errors}."""
    stats = {"fetched": 0, "published": 0, "errors": 0}

    after_id = cursor.read()
    url = f"{backend_url.rstrip('/')}/api/bridge/events?after_id={after_id}&limit={limit}"
    headers = {"X-Bridge-Auth": api_key}

    try:
        resp = http_get(url, headers=headers, timeout=timeout)
    except Exception as e:
        logger.warning("Bridge pull HTTP error: %s — cursor unchanged", e)
        stats["errors"] = 1
        return stats

    if resp.status_code != 200:
        logger.warning(
            "Bridge pull non-200: status=%d body=%s",
            resp.status_code,
            getattr(resp, "text", "")[:200],
        )
        stats["errors"] = 1
        return stats

    try:
        body = resp.json()
        events = body.get("events", [])
        last_id = int(body.get("last_id", after_id))
    except Exception as e:
        logger.error("Bridge pull JSON parse error: %s", e)
        stats["errors"] = 1
        return stats

    stats["fetched"] = len(events)

    for event in events:
        try:
            env = Envelope(
                type=event["type"],
                source="bridge",
                priority=3,  # default; type-specific priority TBD per use case
                payload={
                    **event.get("payload", {}),
                    "_outbox_id": event["id"],
                    "_outbox_created_at": event.get("created_at"),
                },
            )
            redis_xadd(STREAM_BRIDGE_INBOUND, env.to_redis_dict())
            stats["published"] += 1
        except Exception as e:
            logger.error("Failed to publish event %s: %s", event.get("id"), e)
            stats["errors"] += 1

    # Advance cursor only if at least one event was successfully published
    # (or if list was empty — then last_id == after_id, no-op write skipped)
    if stats["published"] > 0:
        cursor.write(last_id)
        logger.info(
            "Bridge pull: fetched=%d published=%d cursor=%d",
            stats["fetched"], stats["published"], last_id,
        )

    return stats


def pull_loop_main() -> None:
    """Entry point for the pull worker (single iteration — cron driven)."""
    api_key = os.getenv(BRIDGE_API_KEY_ENV, "")
    if not api_key:
        logger.error("BRIDGE_API_KEY not set — aborting pull")
        return

    cursor = BridgeCursor(BRIDGE_CURSOR_PATH)
    pull_once(cursor=cursor, backend_url=BRIDGE_BACKEND_URL, api_key=api_key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    pull_loop_main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_nerve_pull.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/bridge/nerve.py \
        apps/mata-garuda/tests/test_nerve_pull.py
git commit -m "feat(bridge): add nerve.pull_once — Fly→Pro polling with cursor"
```

---

## Task 10: Bridge nerve — push (Pro→Fly)

**Files:**

- Modify: `apps/mata-garuda/mata_garuda/bridge/nerve.py` (append push_once + push_loop_main)
- Test: `apps/mata-garuda/tests/test_nerve_push.py`

- [ ] **Step 1: Write the failing test**

Create `apps/mata-garuda/tests/test_nerve_push.py`:

```python
"""Tests for bridge nerve — push side (Pro→Fly)."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from mata_garuda.bridge.envelope import Envelope
from mata_garuda.bridge.nerve import push_once


def _xreadgroup_stub_factory(envelopes_with_ids):
    """Build a stub that returns the given (msg_id, envelope) pairs once,
    then [] forever after.
    """
    state = {"called": False}

    def stub(stream, group, consumer, count, block_ms):
        if state["called"]:
            return []
        state["called"] = True
        return [
            {"id": msg_id, "envelope": env}
            for msg_id, env in envelopes_with_ids
        ]

    return stub


def test_push_once_routes_article_to_correct_endpoint():
    """intel.article_ready → POST /api/bridge/ingest/article."""
    env = Envelope(
        type="intel.article_ready",
        source="intel_scraper",
        priority=2,
        payload={
            "article_id": "abc-123",
            "title": "Test",
            "body_mdx": "# x",
            "topic": "test",
        },
    )

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"article_id": "abc-123", "status": "queued"}
    fake_post = MagicMock(return_value=fake_resp)
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("17-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats == {"sent": 1, "acked": 1, "errors": 0}
    fake_post.assert_called_once()
    args, kwargs = fake_post.call_args
    assert args[0].endswith("/api/bridge/ingest/article")
    fake_xack.assert_called_once_with("bridge:outbound", "bridge-push", "17-0")


def test_push_once_routes_enrichment_to_correct_endpoint():
    """enrichment.kb_entry → POST /api/bridge/ingest/enrichment."""
    env = Envelope(
        type="enrichment.kb_entry",
        source="enrichment_agent",
        priority=3,
        payload={"kb_entry_id": "kb-1", "content": "x", "source": "test"},
    )

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"kb_entry_id": "kb-1", "status": "queued"}
    fake_post = MagicMock(return_value=fake_resp)
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("18-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats == {"sent": 1, "acked": 1, "errors": 0}
    args, _ = fake_post.call_args
    assert args[0].endswith("/api/bridge/ingest/enrichment")


def test_push_once_does_not_ack_on_http_error():
    """If POST fails, do NOT XACK — message redelivered next cycle."""
    env = Envelope(
        type="intel.article_ready",
        source="intel_scraper",
        priority=2,
        payload={"article_id": "x", "title": "t", "body_mdx": "b"},
    )

    fake_resp = MagicMock()
    fake_resp.status_code = 500
    fake_resp.text = "server error"
    fake_post = MagicMock(return_value=fake_resp)
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("19-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats["sent"] == 1
    assert stats["acked"] == 0
    assert stats["errors"] == 1
    fake_xack.assert_not_called()


def test_push_once_skips_unknown_type_with_ack():
    """Unknown type: log + ACK (we'd loop forever otherwise) + count error."""
    env = Envelope(
        type="intel.unknown_subtype",
        source="x",
        priority=3,
        payload={},
    )

    fake_post = MagicMock()
    fake_xack = MagicMock()
    fake_read = _xreadgroup_stub_factory([("20-0", env)])

    stats = push_once(
        backend_url="https://x",
        api_key="k",
        http_post=fake_post,
        redis_xreadgroup=fake_read,
        redis_xack=fake_xack,
    )

    assert stats["sent"] == 0
    assert stats["acked"] == 1
    assert stats["errors"] == 1
    fake_post.assert_not_called()
    fake_xack.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_nerve_push.py -v
```

Expected: FAIL — `push_once` missing.

- [ ] **Step 3: Append push implementation to nerve.py**

Append to `apps/mata-garuda/mata_garuda/bridge/nerve.py`:

```python


# ── Push side ──────────────────────────────────────────────────────────


PUSH_CONSUMER_GROUP = "bridge-push"
PUSH_CONSUMER_NAME = "nerve-1"

# Map envelope type → backend ingest endpoint path
PUSH_ROUTING = {
    "intel.article_ready": "/api/bridge/ingest/article",
    "enrichment.kb_entry": "/api/bridge/ingest/enrichment",
}


def _default_http_post(url: str, headers: dict[str, str], json_body: dict, timeout: int):
    """Default HTTP POST via httpx."""
    import httpx
    return httpx.post(url, headers=headers, json=json_body, timeout=timeout)


def _default_redis_xreadgroup(
    stream: str, group: str, consumer: str, count: int, block_ms: int
) -> list[dict[str, Any]]:
    """Read new messages from a consumer group, return list of {id, envelope}."""
    # Ensure group exists
    subprocess.run(
        ["redis-cli", "XGROUP", "CREATE", stream, group, "0", "MKSTREAM"],
        capture_output=True, text=True, timeout=5,
    )

    args = [
        "redis-cli", "XREADGROUP", "GROUP", group, consumer,
        "COUNT", str(count),
    ]
    if block_ms > 0:
        args.extend(["BLOCK", str(block_ms)])
    args.extend(["STREAMS", stream, ">"])

    result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    if result.returncode != 0 or not result.stdout.strip():
        return []

    # Parse redis-cli flat output (same logic as base_worker._parse_xreadgroup)
    items: list[dict[str, Any]] = []
    lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if "-" in line and line[0].isdigit():
            msg_id = line
            data: dict[str, str] = {}
            j = i + 1
            while j < len(lines) and not (lines[j][0].isdigit() and "-" in lines[j]):
                if j + 1 < len(lines):
                    data[lines[j]] = lines[j + 1]
                    j += 2
                else:
                    break
            if data:
                try:
                    env = Envelope.from_redis_dict(data)
                    items.append({"id": msg_id, "envelope": env})
                except Exception as e:
                    logger.error("Failed to parse envelope %s: %s", msg_id, e)
            i = j
        else:
            i += 1
    return items


def _default_redis_xack(stream: str, group: str, msg_id: str) -> None:
    """ACK a message in a consumer group."""
    subprocess.run(
        ["redis-cli", "XACK", stream, group, msg_id],
        capture_output=True, text=True, timeout=5,
    )


def push_once(
    backend_url: str,
    api_key: str,
    batch: int = 10,
    timeout: int = BRIDGE_HTTP_TIMEOUT_S,
    http_post: Callable = _default_http_post,
    redis_xreadgroup: Callable = _default_redis_xreadgroup,
    redis_xack: Callable = _default_redis_xack,
) -> dict[str, int]:
    """Run one push cycle. Returns stats {sent, acked, errors}."""
    stats = {"sent": 0, "acked": 0, "errors": 0}

    items = redis_xreadgroup(
        STREAM_BRIDGE_OUTBOUND,
        PUSH_CONSUMER_GROUP,
        PUSH_CONSUMER_NAME,
        batch,
        1000,  # 1s block
    )

    if not items:
        return stats

    headers = {"X-Bridge-Auth": api_key, "Content-Type": "application/json"}

    for item in items:
        msg_id = item["id"]
        env: Envelope = item["envelope"]

        endpoint_path = PUSH_ROUTING.get(env.type)
        if endpoint_path is None:
            logger.warning(
                "Unknown push type %s (msg_id=%s) — ACKing to avoid loop",
                env.type, msg_id,
            )
            redis_xack(STREAM_BRIDGE_OUTBOUND, PUSH_CONSUMER_GROUP, msg_id)
            stats["acked"] += 1
            stats["errors"] += 1
            continue

        url = f"{backend_url.rstrip('/')}{endpoint_path}"
        try:
            resp = http_post(url, headers=headers, json_body=env.payload, timeout=timeout)
            stats["sent"] += 1
            if resp.status_code in (200, 202):
                redis_xack(STREAM_BRIDGE_OUTBOUND, PUSH_CONSUMER_GROUP, msg_id)
                stats["acked"] += 1
            else:
                logger.warning(
                    "Push %s non-2xx: status=%d body=%s — NOT acked",
                    env.type, resp.status_code, getattr(resp, "text", "")[:200],
                )
                stats["errors"] += 1
        except Exception as e:
            logger.warning("Push %s HTTP error: %s — NOT acked", env.type, e)
            stats["errors"] += 1

    if stats["sent"] or stats["errors"]:
        logger.info(
            "Bridge push: sent=%d acked=%d errors=%d",
            stats["sent"], stats["acked"], stats["errors"],
        )

    return stats


def push_loop_main() -> None:
    """Entry point for the push worker (single iteration — cron driven)."""
    api_key = os.getenv(BRIDGE_API_KEY_ENV, "")
    if not api_key:
        logger.error("BRIDGE_API_KEY not set — aborting push")
        return
    push_once(backend_url=BRIDGE_BACKEND_URL, api_key=api_key)


def bridge_main() -> None:
    """Entry point: run pull then push (one cycle)."""
    api_key = os.getenv(BRIDGE_API_KEY_ENV, "")
    if not api_key:
        logger.error("BRIDGE_API_KEY not set — aborting bridge cycle")
        return

    cursor = BridgeCursor(BRIDGE_CURSOR_PATH)
    pull_once(cursor=cursor, backend_url=BRIDGE_BACKEND_URL, api_key=api_key)
    push_once(backend_url=BRIDGE_BACKEND_URL, api_key=api_key)
```

Also add `STREAM_BRIDGE_OUTBOUND` to the imports at the top of `nerve.py`:

```python
from mata_garuda.config import (
    BRIDGE_API_KEY_ENV,
    BRIDGE_BACKEND_URL,
    BRIDGE_CURSOR_PATH,
    BRIDGE_HTTP_TIMEOUT_S,
    BRIDGE_PULL_LIMIT,
    STREAM_BRIDGE_INBOUND,
    STREAM_BRIDGE_OUTBOUND,
)
```

Update the `if __name__ == "__main__":` block at the bottom to call `bridge_main()` instead of `pull_loop_main()`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_nerve_push.py tests/test_nerve_pull.py -v
```

Expected: PASS (8 tests total)

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/bridge/nerve.py \
        apps/mata-garuda/tests/test_nerve_push.py
git commit -m "feat(bridge): add nerve.push_once + bridge_main (full pull+push cycle)"
```

---

## Task 11: Gap consumer worker

**Files:**

- Create: `apps/mata-garuda/mata_garuda/workers/gap_consumer.py`
- Test: `apps/mata-garuda/tests/test_gap_consumer.py`

- [ ] **Step 1: Write the failing test**

Create `apps/mata-garuda/tests/test_gap_consumer.py`:

```python
"""Tests for gap consumer — reads nexus:gaps and dispatches agents."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from mata_garuda.workers.gap_consumer import (
    GAP_DISPATCH,
    process_gap,
    run_gap_consumer,
)


def test_gap_dispatch_table_complete():
    """All 8 gap types from the design spec are mapped (1 to None for Phase 2)."""
    expected = {
        "gap.missing_nip",
        "gap.missing_lhkpn",
        "gap.missing_angkatan",
        "gap.stale_official",
        "gap.orphan_org",
        "gap.missing_office",
        "gap.kanim_struktur",
        "gap.missing_procurement",
    }
    assert set(GAP_DISPATCH.keys()) == expected
    # Phase 1: 7 gaps mapped to an agent, 1 unmapped (procurement)
    mapped = {k for k, v in GAP_DISPATCH.items() if v is not None}
    assert "gap.missing_procurement" not in mapped
    assert len(mapped) == 7


def test_process_gap_skips_unmapped():
    """Unmapped gap (Phase 2) is skipped + acked."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="1-0",
        gap_type="gap.missing_procurement",
        payload={"x": 1},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result == {"status": "skipped", "agent": None}
    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()


def test_process_gap_unknown_type_skips_with_ack():
    """Unknown gap type is logged and acked (no infinite loop)."""
    fake_dispatch = MagicMock()
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="2-0",
        gap_type="gap.totally_unknown",
        payload={},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result["status"] == "unknown"
    fake_dispatch.assert_not_called()
    fake_xack.assert_called_once()


def test_process_gap_dispatches_lhkpn_for_missing_nip():
    """gap.missing_nip → lhkpn_harvester."""
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="3-0",
        gap_type="gap.missing_nip",
        payload={"person_name": "Budi"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    fake_dispatch.assert_called_once_with(
        agent_name="lhkpn_harvester",
        payload={"person_name": "Budi", "_gap_type": "gap.missing_nip"},
    )
    assert result["status"] == "resolved"
    assert result["agent"] == "lhkpn_harvester"
    fake_xack.assert_called_once()


def test_process_gap_does_not_ack_on_failure():
    """case_not_resolved: do NOT ack — let it redeliver."""
    fake_dispatch = MagicMock(return_value={"case_resolved": False, "reason": "403"})
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="4-0",
        gap_type="gap.missing_nip",
        payload={"person_name": "x"},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result["status"] == "failed"
    fake_xack.assert_not_called()


def test_process_gap_dispatch_exception_is_caught():
    """Exception from dispatcher is caught and logged — no crash."""
    fake_dispatch = MagicMock(side_effect=RuntimeError("boom"))
    fake_xack = MagicMock()

    result = process_gap(
        msg_id="5-0",
        gap_type="gap.missing_nip",
        payload={},
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert result["status"] == "error"
    fake_xack.assert_not_called()


def test_run_gap_consumer_processes_batch():
    """run_gap_consumer reads N messages and processes each."""
    msgs = [
        {"id": "10-0", "data": {"type": "gap.missing_nip", "payload": '{"person_name": "A"}'}},
        {"id": "11-0", "data": {"type": "gap.stale_official", "payload": '{"nip": "123"}'}},
    ]

    fake_read = MagicMock(return_value=msgs)
    fake_dispatch = MagicMock(return_value={"case_resolved": True})
    fake_xack = MagicMock()

    stats = run_gap_consumer(
        max_items=10,
        stream_read=fake_read,
        dispatch_agent=fake_dispatch,
        xack=fake_xack,
    )

    assert stats["read"] == 2
    assert stats["resolved"] == 2
    assert stats["failed"] == 0
    assert fake_dispatch.call_count == 2
    assert fake_xack.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_gap_consumer.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement gap_consumer**

Create `apps/mata-garuda/mata_garuda/workers/gap_consumer.py`:

```python
"""
Mata Garuda — Gap Consumer Worker.

Reads nexus:gaps stream, dispatches the appropriate agent for each gap type,
and acks on success. On failure does NOT ack — the message is redelivered.

Dispatch table:
- gap.missing_nip       → lhkpn_harvester
- gap.missing_lhkpn     → lhkpn_harvester
- gap.missing_angkatan  → lhkpn_harvester
- gap.stale_official    → regulation_watcher
- gap.orphan_org        → regulation_watcher
- gap.missing_office    → regulation_watcher
- gap.kanim_struktur    → regulation_watcher
- gap.missing_procurement → None (Phase 2: lpse_harvester)

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Optional

from mata_garuda.config import STREAM_NEXUS_GAPS
from mata_garuda.workers.base_worker import stream_ack, stream_read_new

logger = logging.getLogger("mata_garuda.workers.gap_consumer")


CONSUMER_GROUP = "gap-consumer"
CONSUMER_NAME = "consumer-1"

# Rate limit: max dispatches per run + sleep between them
MAX_DISPATCH_PER_RUN = 5
DISPATCH_SLEEP_S = 2

# Gap type → agent name (None = Phase 2, skipped with ack)
GAP_DISPATCH: dict[str, Optional[str]] = {
    "gap.missing_nip":          "lhkpn_harvester",
    "gap.missing_lhkpn":        "lhkpn_harvester",
    "gap.missing_angkatan":     "lhkpn_harvester",
    "gap.stale_official":       "regulation_watcher",
    "gap.orphan_org":           "regulation_watcher",
    "gap.missing_office":       "regulation_watcher",
    "gap.kanim_struktur":       "regulation_watcher",
    "gap.missing_procurement":  None,  # Phase 2: lpse_harvester
}


def _default_dispatch_agent(agent_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Default dispatcher: invokes the registered agent via MetaChain.

    Returns {"case_resolved": bool, "result": ..., "reason": str}.
    Exceptions propagate so the caller can convert them to status="error".
    """
    from mata_garuda.registry import Registry
    from mata_garuda.runtime.lamarckian import run_with_lamarckian

    registry = Registry()
    agent = registry.get_agent(agent_name)
    if agent is None:
        return {"case_resolved": False, "reason": f"agent {agent_name!r} not registered"}

    # Format payload as a query string the agent can understand
    query = json.dumps(payload, ensure_ascii=False)
    outcome = run_with_lamarckian(agent, query)
    return {
        "case_resolved": bool(outcome.success),
        "result": outcome.result if hasattr(outcome, "result") else None,
        "reason": getattr(outcome, "reason", ""),
    }


def _default_xack(stream: str, group: str, msg_id: str) -> None:
    stream_ack(stream, group, msg_id)


def process_gap(
    msg_id: str,
    gap_type: str,
    payload: dict[str, Any],
    dispatch_agent: Callable = _default_dispatch_agent,
    xack: Callable = _default_xack,
) -> dict[str, Any]:
    """Process a single gap message.

    Returns dict with status: "resolved" | "failed" | "skipped" | "unknown" | "error"
    """
    if gap_type not in GAP_DISPATCH:
        logger.warning("Unknown gap type %s (msg_id=%s) — ACKing to skip", gap_type, msg_id)
        xack(STREAM_NEXUS_GAPS, CONSUMER_GROUP, msg_id)
        return {"status": "unknown", "agent": None}

    agent_name = GAP_DISPATCH[gap_type]
    if agent_name is None:
        logger.info("Gap %s mapped to None (Phase 2) — ACKing", gap_type)
        xack(STREAM_NEXUS_GAPS, CONSUMER_GROUP, msg_id)
        return {"status": "skipped", "agent": None}

    # Inject _gap_type so the agent knows what it's solving
    enriched = {**payload, "_gap_type": gap_type}

    try:
        result = dispatch_agent(agent_name=agent_name, payload=enriched)
    except Exception as e:
        logger.error("Dispatch %s for %s raised: %s — NOT acking", agent_name, gap_type, e)
        return {"status": "error", "agent": agent_name, "reason": str(e)}

    if result.get("case_resolved"):
        xack(STREAM_NEXUS_GAPS, CONSUMER_GROUP, msg_id)
        logger.info("Gap %s resolved by %s (msg %s)", gap_type, agent_name, msg_id)
        return {"status": "resolved", "agent": agent_name}
    else:
        logger.warning(
            "Gap %s NOT resolved by %s (msg %s): %s — NOT acking",
            gap_type, agent_name, msg_id, result.get("reason", ""),
        )
        return {"status": "failed", "agent": agent_name}


def run_gap_consumer(
    max_items: int = MAX_DISPATCH_PER_RUN,
    stream_read: Callable = None,
    dispatch_agent: Callable = _default_dispatch_agent,
    xack: Callable = _default_xack,
) -> dict[str, int]:
    """One cycle: read up to max_items from nexus:gaps and process each.

    Returns stats {read, resolved, failed, skipped, unknown, errors}.
    """
    if stream_read is None:
        stream_read = lambda: stream_read_new(
            STREAM_NEXUS_GAPS, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
        )

    stats = {"read": 0, "resolved": 0, "failed": 0, "skipped": 0, "unknown": 0, "errors": 0}

    items = stream_read()
    if not items:
        logger.info("Gap consumer: no new gaps in %s", STREAM_NEXUS_GAPS)
        return stats

    stats["read"] = len(items)

    for i, item in enumerate(items):
        msg_id = item["id"]
        data = item["data"]
        gap_type = data.get("type", "")
        try:
            payload = json.loads(data.get("payload", "{}"))
        except (json.JSONDecodeError, TypeError):
            payload = {}

        result = process_gap(
            msg_id=msg_id,
            gap_type=gap_type,
            payload=payload,
            dispatch_agent=dispatch_agent,
            xack=xack,
        )
        # Map status to stats key
        key = {
            "resolved": "resolved",
            "failed": "failed",
            "skipped": "skipped",
            "unknown": "unknown",
            "error": "errors",
        }.get(result["status"], "errors")
        stats[key] += 1

        # Rate limit between dispatches (skip last + skip if not actually dispatched)
        if i < len(items) - 1 and result.get("agent"):
            time.sleep(DISPATCH_SLEEP_S)

    logger.info("Gap consumer cycle: %s", stats)
    return stats


def main() -> None:
    """Entry point for the cron worker (single iteration)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_gap_consumer()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_gap_consumer.py -v
```

Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/workers/gap_consumer.py \
        apps/mata-garuda/tests/test_gap_consumer.py
git commit -m "feat(workers): add gap_consumer (8 gap types → 2 agents + 1 Phase 2 stub)"
```

---

## Task 12: LHKPN scraper tools

**Files:**

- Create: `apps/mata-garuda/mata_garuda/tools/lhkpn_tools.py`
- Test: `apps/mata-garuda/tests/test_lhkpn_tools.py`

- [ ] **Step 1: Write the failing test**

Create `apps/mata-garuda/tests/test_lhkpn_tools.py`:

```python
"""Tests for LHKPN scraper tools (parsing only — HTTP mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mata_garuda.tools.lhkpn_tools import (
    parse_lhkpn_search_html,
    parse_lhkpn_profile_html,
    LHKPN_USER_AGENTS,
)


SEARCH_FIXTURE = """
<html><body><table id="resultsTable">
<tr><td>Budi Santoso</td><td>199001012010011001</td><td>Direktur Jenderal Pajak</td><td>2024</td></tr>
<tr><td>Ahmad Wijaya</td><td>198805052012021002</td><td>Sekretaris Jenderal</td><td>2023</td></tr>
</table></body></html>
"""

PROFILE_FIXTURE = """
<html><body>
<div class="profile">
<span id="nama">Budi Santoso</span>
<span id="nip">199001012010011001</span>
<span id="jabatan">Direktur Jenderal Pajak</span>
<span id="angkatan">1995</span>
<span id="totalHarta">Rp 12.500.000.000</span>
<table id="properties"><tr><td>Tanah</td></tr><tr><td>Tanah</td></tr></table>
<table id="vehicles"><tr><td>Mobil</td></tr></table>
<table id="accounts"><tr><td>BCA</td></tr><tr><td>Mandiri</td></tr></table>
</div></body></html>
"""


def test_parse_search_extracts_results():
    results = parse_lhkpn_search_html(SEARCH_FIXTURE)
    assert len(results) == 2
    assert results[0]["nama"] == "Budi Santoso"
    assert results[0]["nip"] == "199001012010011001"
    assert results[0]["jabatan"] == "Direktur Jenderal Pajak"
    assert results[0]["report_year"] == "2024"


def test_parse_search_empty_returns_empty_list():
    assert parse_lhkpn_search_html("<html></html>") == []


def test_parse_profile_extracts_assets():
    profile = parse_lhkpn_profile_html(PROFILE_FIXTURE)
    assert profile["nama"] == "Budi Santoso"
    assert profile["nip"] == "199001012010011001"
    assert profile["jabatan"] == "Direktur Jenderal Pajak"
    assert profile["angkatan"] == "1995"
    assert profile["total_harta_idr"] == 12_500_000_000
    assert profile["properties_count"] == 2
    assert profile["vehicles_count"] == 1
    assert profile["accounts_count"] == 2


def test_parse_profile_handles_missing_fields():
    profile = parse_lhkpn_profile_html("<html><body><div class='profile'></div></body></html>")
    assert profile["nama"] == ""
    assert profile["total_harta_idr"] == 0
    assert profile["properties_count"] == 0


def test_user_agents_pool_has_3_variants():
    """3 User-Agents for rotation per the GENOME constraint."""
    assert len(LHKPN_USER_AGENTS) == 3
    for ua in LHKPN_USER_AGENTS:
        assert "Mozilla" in ua
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_lhkpn_tools.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the tools**

Create `apps/mata-garuda/mata_garuda/tools/lhkpn_tools.py`:

```python
"""
Mata Garuda — LHKPN scraping tools.

Targets antv.kpk.go.id/elhkpn/ — Indonesian state officials' wealth
declarations. Tools are pure functions where possible; HTTP calls are
isolated for testability.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5
GENOME constraints: max 10 req/min, User-Agent rotation, fallback on 403.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

logger = logging.getLogger("mata_garuda.tools.lhkpn")


LHKPN_BASE_URL = "https://antv.kpk.go.id/elhkpn"
LHKPN_RATE_LIMIT_S = 6  # 10 req/min = 6s between requests

LHKPN_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


# ── Pure parsers (no I/O, easy to test) ────────────────────────────────


def parse_lhkpn_search_html(html: str) -> list[dict[str, Any]]:
    """Extract search results from antv.kpk.go.id search page.

    Returns list of dicts with: nama, nip, jabatan, report_year.
    """
    # Simple regex-based parsing — avoids bs4 dependency for v1.
    # The site's search results are wrapped in <table id="resultsTable">.
    table_match = re.search(
        r'<table[^>]*id="resultsTable"[^>]*>(.*?)</table>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not table_match:
        return []

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.DOTALL | re.IGNORECASE)
    results = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) >= 4:
            results.append({
                "nama": _strip_html(cells[0]),
                "nip": _strip_html(cells[1]),
                "jabatan": _strip_html(cells[2]),
                "report_year": _strip_html(cells[3]),
            })
    return results


def parse_lhkpn_profile_html(html: str) -> dict[str, Any]:
    """Extract profile fields from antv.kpk.go.id detail page."""
    def get_span(span_id: str) -> str:
        m = re.search(
            rf'<span[^>]*id="{span_id}"[^>]*>(.*?)</span>',
            html, re.DOTALL | re.IGNORECASE,
        )
        return _strip_html(m.group(1)) if m else ""

    def count_table_rows(table_id: str) -> int:
        m = re.search(
            rf'<table[^>]*id="{table_id}"[^>]*>(.*?)</table>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if not m:
            return 0
        return len(re.findall(r"<tr[^>]*>", m.group(1), re.IGNORECASE))

    return {
        "nama": get_span("nama"),
        "nip": get_span("nip"),
        "jabatan": get_span("jabatan"),
        "angkatan": get_span("angkatan"),
        "total_harta_idr": _parse_idr(get_span("totalHarta")),
        "properties_count": count_table_rows("properties"),
        "vehicles_count": count_table_rows("vehicles"),
        "accounts_count": count_table_rows("accounts"),
    }


def _strip_html(s: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def _parse_idr(s: str) -> int:
    """Parse 'Rp 12.500.000.000' → 12500000000."""
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else 0


# ── HTTP wrappers (effectful — invoked by the agent) ───────────────────


def _http_get_with_rotation(
    url: str,
    timeout: int = 15,
    user_agent_index: int = 0,
) -> tuple[int, str]:
    """GET with User-Agent rotation. Returns (status_code, body)."""
    import httpx

    ua = LHKPN_USER_AGENTS[user_agent_index % len(LHKPN_USER_AGENTS)]
    headers = {
        "User-Agent": ua,
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        return resp.status_code, resp.text
    except Exception as e:
        logger.warning("LHKPN HTTP error %s: %s", url, e)
        return 0, ""


def scrape_lhkpn_search(query: str) -> list[dict[str, Any]]:
    """Search LHKPN by name. Honors rate limit + UA rotation on 403."""
    # URL-encode query
    from urllib.parse import quote_plus
    url = f"{LHKPN_BASE_URL}/index.php/searchpenyelenggara/searchpencarian?q={quote_plus(query)}"

    for attempt in range(len(LHKPN_USER_AGENTS)):
        time.sleep(LHKPN_RATE_LIMIT_S)
        status, body = _http_get_with_rotation(url, user_agent_index=attempt)
        if status == 200:
            return parse_lhkpn_search_html(body)
        if status == 403:
            logger.warning("LHKPN search 403 attempt %d — rotating UA", attempt + 1)
            continue
        logger.error("LHKPN search non-200/403: status=%d", status)
        return []

    logger.error("LHKPN search exhausted UA rotation for query=%s", query)
    return []


def scrape_lhkpn_profile(nip: str) -> dict[str, Any]:
    """Fetch detail page for a NIP. Honors rate limit + UA rotation on 403."""
    url = f"{LHKPN_BASE_URL}/index.php/searchpenyelenggara/profilelhkpn/{nip}"

    for attempt in range(len(LHKPN_USER_AGENTS)):
        time.sleep(LHKPN_RATE_LIMIT_S)
        status, body = _http_get_with_rotation(url, user_agent_index=attempt)
        if status == 200:
            return parse_lhkpn_profile_html(body)
        if status == 403:
            logger.warning("LHKPN profile 403 attempt %d — rotating UA", attempt + 1)
            continue
        logger.error("LHKPN profile non-200/403: status=%d", status)
        return {}

    logger.error("LHKPN profile exhausted UA rotation for nip=%s", nip)
    return {}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_lhkpn_tools.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/tools/lhkpn_tools.py \
        apps/mata-garuda/tests/test_lhkpn_tools.py
git commit -m "feat(tools): add LHKPN scraper (parsers + UA rotation + 6s rate limit)"
```

---

## Task 13: LHKPN harvester agent + GENOME

**Files:**

- Create: `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py`
- Create: `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester_GENOME.md`
- Test: `apps/mata-garuda/tests/test_lhkpn_harvester.py`

- [ ] **Step 1: Write the failing test**

Create `apps/mata-garuda/tests/test_lhkpn_harvester.py`:

```python
"""Tests for the LHKPN harvester agent (registration + harvest function)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mata_garuda.agents.lhkpn_harvester import (
    harvest_lhkpn_for_nip,
    harvest_lhkpn_by_name,
)


def test_harvest_by_nip_publishes_to_garuda_raw():
    """Successful profile fetch publishes harvest.lhkpn to garuda:raw."""
    profile = {
        "nama": "Budi Santoso",
        "nip": "199001012010011001",
        "jabatan": "Dirjen Pajak",
        "angkatan": "1995",
        "total_harta_idr": 12_500_000_000,
        "properties_count": 7,
        "vehicles_count": 3,
        "accounts_count": 12,
    }

    fake_scrape = MagicMock(return_value=profile)
    fake_publish = MagicMock(return_value="1-0")

    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile", fake_scrape), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish", fake_publish):
        result = harvest_lhkpn_for_nip("199001012010011001")

    assert result["case_resolved"] is True
    assert result["nip"] == "199001012010011001"
    fake_scrape.assert_called_once_with("199001012010011001")
    fake_publish.assert_called_once()
    # Verify the published payload
    stream, fields = fake_publish.call_args.args
    assert stream == "garuda:raw"
    assert fields["agent"] == "lhkpn_harvester"
    assert "Budi Santoso" in fields["title"]


def test_harvest_by_nip_empty_result_fails():
    """Empty profile (HTTP failure) returns case_not_resolved."""
    fake_scrape = MagicMock(return_value={})
    fake_publish = MagicMock()

    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile", fake_scrape), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish", fake_publish):
        result = harvest_lhkpn_for_nip("000")

    assert result["case_resolved"] is False
    assert "empty" in result.get("reason", "").lower() or "no data" in result.get("reason", "").lower()
    fake_publish.assert_not_called()


def test_harvest_by_name_picks_first_then_fetches_profile():
    """Search returns hits → fetch first NIP's profile → publish."""
    search_hits = [
        {"nama": "Ahmad Wijaya", "nip": "111", "jabatan": "x", "report_year": "2024"},
    ]
    profile = {
        "nama": "Ahmad Wijaya", "nip": "111", "jabatan": "x", "angkatan": "1990",
        "total_harta_idr": 5_000_000, "properties_count": 1,
        "vehicles_count": 0, "accounts_count": 1,
    }

    fake_search = MagicMock(return_value=search_hits)
    fake_profile = MagicMock(return_value=profile)
    fake_publish = MagicMock(return_value="2-0")

    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_search", fake_search), \
         patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_profile", fake_profile), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish", fake_publish):
        result = harvest_lhkpn_by_name("Ahmad")

    assert result["case_resolved"] is True
    fake_search.assert_called_once_with("Ahmad")
    fake_profile.assert_called_once_with("111")
    fake_publish.assert_called_once()


def test_harvest_by_name_no_results_fails():
    """Empty search returns case_not_resolved."""
    with patch("mata_garuda.agents.lhkpn_harvester.scrape_lhkpn_search", return_value=[]), \
         patch("mata_garuda.agents.lhkpn_harvester.stream_publish") as fake_publish:
        result = harvest_lhkpn_by_name("nonexistent")

    assert result["case_resolved"] is False
    fake_publish.assert_not_called()


def test_agent_registered_in_registry():
    """Importing the module registers lhkpn_harvester in the global registry."""
    # Re-import to trigger decorator
    import importlib
    import mata_garuda.agents.lhkpn_harvester as mod
    importlib.reload(mod)

    from mata_garuda.registry import Registry
    registry = Registry()
    agent = registry.get_agent("lhkpn_harvester")
    assert agent is not None
    assert agent.name == "lhkpn_harvester"
    assert agent.layer == "harvester"


def test_genome_md_exists_and_has_constraints():
    """GENOME.md exists alongside the agent file."""
    from pathlib import Path
    p = Path(__file__).parent.parent / "mata_garuda" / "agents" / "lhkpn_harvester_GENOME.md"
    assert p.exists(), f"Missing GENOME at {p}"
    text = p.read_text()
    assert "rate" in text.lower() or "10 req" in text.lower()
    assert "User-Agent" in text or "user-agent" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_lhkpn_harvester.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the agent**

Create `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py`:

```python
"""
Mata Garuda — LHKPN Harvester Agent.

Harvests Indonesian state officials' wealth declarations from
antv.kpk.go.id/elhkpn/. Closes 4 of 8 gap types from the gap detector:
- gap.missing_nip
- gap.missing_lhkpn
- gap.missing_angkatan
- gap.stale_official (when the staleness is on LHKPN-related fields)

Layer: 1 (Harvester)

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5
GENOME: lhkpn_harvester_GENOME.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mata_garuda.config import STREAM_RAW
from mata_garuda.registry import register_agent
from mata_garuda.tools.lhkpn_tools import (
    scrape_lhkpn_profile,
    scrape_lhkpn_search,
)
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import stream_publish

logger = logging.getLogger("mata_garuda.agents.lhkpn_harvester")

GENOME_PATH = str(Path(__file__).parent / "lhkpn_harvester_GENOME.md")


# ── Tool functions exposed to the agent ───────────────────────────────


def harvest_lhkpn_for_nip(nip: str) -> dict[str, Any]:
    """Fetch the LHKPN profile for a given NIP and publish to garuda:raw.

    Returns {"case_resolved": bool, "nip": str, "reason": str}.
    """
    profile = scrape_lhkpn_profile(nip)
    if not profile or not profile.get("nip"):
        return {
            "case_resolved": False,
            "nip": nip,
            "reason": "empty profile (HTTP failure or NIP not found)",
        }

    title = f"LHKPN {profile.get('nama', 'unknown')} ({profile.get('jabatan', '?')})"
    content = json.dumps(profile, ensure_ascii=False)

    fields = {
        "title": title,
        "url": f"https://antv.kpk.go.id/elhkpn/index.php/searchpenyelenggara/profilelhkpn/{nip}",
        "source": "antv.kpk.go.id",
        "source_type": "lhkpn",
        "content": content,
        "agent": "lhkpn_harvester",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    msg_id = stream_publish(STREAM_RAW, fields)
    logger.info("Published LHKPN profile for NIP %s (msg %s)", nip, msg_id)

    return {"case_resolved": True, "nip": nip, "reason": "", "msg_id": msg_id}


def harvest_lhkpn_by_name(name: str) -> dict[str, Any]:
    """Search LHKPN by name; on first hit, fetch and publish the profile.

    Returns {"case_resolved": bool, "name": str, "reason": str, ...}.
    """
    hits = scrape_lhkpn_search(name)
    if not hits:
        return {
            "case_resolved": False,
            "name": name,
            "reason": "no search results",
        }

    first = hits[0]
    nip = first.get("nip", "")
    if not nip:
        return {
            "case_resolved": False,
            "name": name,
            "reason": "first search hit has no NIP",
        }

    result = harvest_lhkpn_for_nip(nip)
    result["name"] = name
    result["matched_nip"] = nip
    return result


# ── Agent registration ────────────────────────────────────────────────


@register_agent("lhkpn_harvester")
def lhkpn_harvester() -> Agent:
    """Harvester agent for LHKPN wealth declarations."""
    return Agent(
        name="lhkpn_harvester",
        model="claude",  # CLI subprocess (claude --print)
        instructions=(
            "You are the LHKPN Harvester agent for Mata Garuda.\n"
            "Your job: given a person's name or NIP, fetch their wealth declaration\n"
            "from antv.kpk.go.id and publish to garuda:raw.\n\n"
            "Tools available:\n"
            "- harvest_lhkpn_for_nip(nip): fetch by NIP (preferred when NIP is known)\n"
            "- harvest_lhkpn_by_name(name): search by name then fetch first match\n\n"
            "Honor the GENOME constraints: 6s between requests, UA rotation on 403.\n"
            "End with case_resolved() on success, case_not_resolved() on failure."
        ),
        functions=[harvest_lhkpn_for_nip, harvest_lhkpn_by_name],
        layer="harvester",
        genome_path=GENOME_PATH,
    )
```

Create `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester_GENOME.md`:

````markdown
# LHKPN Harvester — GENOME

> Lamarckian constraints. Updated only with Zero review. Auto-revert if fitness drops.

## Identity

- **Name:** lhkpn_harvester
- **Layer:** 1 — Harvester
- **Source:** antv.kpk.go.id/elhkpn/ (Komisi Pemberantasan Korupsi — KPK)
- **Output stream:** `garuda:raw` (type: `harvest.lhkpn`)

## Immutable Constraints

1. **Rate limit:** max 10 requests per minute (6 seconds between calls). Honored in `tools/lhkpn_tools.py:LHKPN_RATE_LIMIT_S`.
2. **User-Agent rotation:** 3 desktop browser UAs in `LHKPN_USER_AGENTS`. Rotate on 403 response.
3. **No deep crawl:** only fetch profiles when explicitly requested (gap consumer or manual). Never crawl listings autonomously.
4. **OSINT blindato:** output goes to `garuda:raw` only. Never to frontend, never to clients, never to cloud (Legge 2 SYMBIOSIS.md).
5. **No PII enrichment:** publish raw payload only; downstream Nexus does the entity resolution.

## Cron Schedule

Not scheduled. Triggered by `gap_consumer` worker on `nexus:gaps` messages of types:

- `gap.missing_nip`
- `gap.missing_lhkpn`
- `gap.missing_angkatan`
- `gap.stale_official` (LHKPN subset)

## Escalation

- 3 consecutive failures (HTTP 403/500/timeout) → meta-agent review
- Site structure change (parser returns empty for known-good NIP) → notify Zero via TG
- Banned IP → Zero rotates outbound IP manually

## Output Format

```json
{
  "title": "LHKPN <nama> (<jabatan>)",
  "url": "https://antv.kpk.go.id/...",
  "source": "antv.kpk.go.id",
  "source_type": "lhkpn",
  "content": "<JSON profile>",
  "agent": "lhkpn_harvester",
  "timestamp": "<iso>"
}
```
````

## Genome Mutation History

- **2026-04-14** — Initial creation (Phase 1 organism plan)

````

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_lhkpn_harvester.py -v
````

Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite to catch regressions**

```bash
pytest tests/ -q
```

Expected: all tests PASS (existing 105+ + new ~30).

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py \
        apps/mata-garuda/mata_garuda/agents/lhkpn_harvester_GENOME.md \
        apps/mata-garuda/tests/test_lhkpn_harvester.py
git commit -m "feat(agents): add lhkpn_harvester (closes 4 of 8 gap types)"
```

---

## Task 14: Bridge LaunchAgent + shell wrapper

**Files:**

- Create: `~/scripts/matagaruda-bridge.sh`
- Create: `~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist`
- Modify: `scripts/automation_catalog.json` (add bridge entry)
- Modify: `~/.agent/decisions/job_registry.json` (add bridge entry)
- Modify: `~/.nuzantara-secrets.env` (add BRIDGE_API_KEY)

- [ ] **Step 1: Generate the BRIDGE_API_KEY and add to secrets**

```bash
# Generate a 32-char random key
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
echo "BRIDGE_API_KEY=$NEW_KEY" >> ~/.nuzantara-secrets.env
echo "Generated key (first 8 chars): ${NEW_KEY:0:8}..."

# Verify it's in the file
grep -c "BRIDGE_API_KEY" ~/.nuzantara-secrets.env
```

Expected: prints first 8 chars + line count `1`.

- [ ] **Step 2: Set the same key as a Fly secret (for the backend)**

```bash
# Read it back from the local env file
KEY=$(grep "^BRIDGE_API_KEY=" ~/.nuzantara-secrets.env | cut -d= -f2)
fly secrets set BRIDGE_API_KEY="$KEY" --app nuzantara-rag --stage
```

Expected: "Secrets staged for ..." — Fly will apply on next deploy.

If you're not deploying yet, skip the `fly secrets` for now and document this as a pre-deploy gate.

- [ ] **Step 3: Create the bridge bash wrapper (TCC-safe)**

Create `~/scripts/matagaruda-bridge.sh`:

```bash
#!/bin/zsh
# Mata Garuda Bridge — bidirectional Pro<->Fly nerve.
# Invoked by com.matagaruda.bridge.adaptive.plist every 30s (day) / 5min (night).
#
# TCC-safe: calls venv python directly (adhoc-signed binaries bypass TCC).

set -e

# Load secrets
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

REPO="$HOME/Desktop/nuzantara/apps/mata-garuda"
VENV_PY="$REPO/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[bridge] venv python not found at $VENV_PY" >&2
    exit 1
fi

cd "$REPO"
PYTHONPATH="$REPO" "$VENV_PY" -m mata_garuda.bridge.nerve
```

Make executable:

```bash
chmod +x ~/scripts/matagaruda-bridge.sh
```

- [ ] **Step 4: Test the wrapper manually**

```bash
~/scripts/matagaruda-bridge.sh 2>&1 | head -20
```

Expected: log lines (no crash). May log "Bridge pull non-200" if Fly hasn't deployed yet — that's fine.

- [ ] **Step 5: Create the LaunchAgent plist**

Create `~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.matagaruda.bridge.adaptive</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/scripts/matagaruda-bridge.sh</string>
    </array>

    <key>StartInterval</key>
    <integer>60</integer>

    <key>RunAtLoad</key>
    <false/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin</string>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/matagaruda-bridge.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/matagaruda-bridge-err.log</string>
</dict>
</plist>
```

**Note on schedule:** v1 uses a flat 60-second interval (simpler, less plist juggling). The adaptive day/night cadence (30s vs 5min) is deferred — at 60s the cost is negligible. Document this trade-off in the catalog entry.

- [ ] **Step 6: Load the LaunchAgent**

```bash
mkdir -p ~/logs
launchctl load ~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist
launchctl list com.matagaruda.bridge.adaptive
```

Expected: `LastExitStatus = 0` (or first run not yet completed — re-check after 90s).

- [ ] **Step 7: Add to automation_catalog.json**

Edit `scripts/automation_catalog.json` and add a new entry inside `launchagents`:

```json
"com.matagaruda.bridge.adaptive": {
  "description": "Mata Garuda bridge — bidirectional Pro<->Fly nerve. Pulls bridge_outbox events from Fly backend, pushes intel.article_ready / enrichment.kb_entry to backend ingest endpoints. Runs every 60s.",
  "type": "scheduled",
  "produces": "Redis stream bridge:inbound, POST to backend",
  "consumes": "GET /api/bridge/events, Redis stream bridge:outbound",
  "uses_llm": "—",
  "llm_interface": "—",
  "tools_called": ["redis-cli (XADD/XREADGROUP/XACK)", "httpx (GET/POST)"],
  "apis_called": ["nuzantara-rag.fly.dev/api/bridge/events", "nuzantara-rag.fly.dev/api/bridge/ingest/*"],
  "schedule": "every 60s"
}
```

- [ ] **Step 8: Add to job_registry.json (Sentinel monitoring)**

Edit `~/.agent/decisions/job_registry.json` and add:

```json
"com.matagaruda.bridge.adaptive": {
  "host": "pro",
  "type": "launchagent",
  "plist": "~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist",
  "schedule_seconds": 60,
  "staleness_threshold_s": 300,
  "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.matagaruda.bridge.adaptive",
  "repair_scope": "infra",
  "critical": false
}
```

- [ ] **Step 9: Verify the bridge is running**

```bash
sleep 90
tail -30 ~/logs/matagaruda-bridge.log
launchctl list com.matagaruda.bridge.adaptive | grep -E "LastExitStatus|PID"
```

Expected: at least one log entry (pull cycle), LastExitStatus = 0.

- [ ] **Step 10: Commit catalog updates**

```bash
git add scripts/automation_catalog.json
git commit -m "chore(catalog): register com.matagaruda.bridge.adaptive"
```

(The plist and shell script live outside the repo — document in the commit message.)

---

## Task 15: Gap consumer LaunchAgent + shell wrapper

**Files:**

- Create: `~/scripts/matagaruda-gap-consumer.sh`
- Create: `~/Library/LaunchAgents/com.matagaruda.gap.consumer.plist`
- Modify: `scripts/automation_catalog.json`
- Modify: `~/.agent/decisions/job_registry.json`

- [ ] **Step 1: Create the gap consumer wrapper**

Create `~/scripts/matagaruda-gap-consumer.sh`:

```bash
#!/bin/zsh
# Mata Garuda Gap Consumer — reads nexus:gaps, dispatches agents.
# Runs every 10 minutes during 06:00-22:00 WITA.

set -e

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

REPO="$HOME/Desktop/nuzantara/apps/mata-garuda"
VENV_PY="$REPO/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[gap_consumer] venv python not found at $VENV_PY" >&2
    exit 1
fi

# Skip outside operating window (06:00-22:00 WITA — local time)
HOUR=$(date +%H)
if [ "$HOUR" -lt 6 ] || [ "$HOUR" -ge 22 ]; then
    echo "[gap_consumer] Outside operating window ($HOUR:00) — skipping"
    exit 0
fi

cd "$REPO"
PYTHONPATH="$REPO" "$VENV_PY" -m mata_garuda.workers.gap_consumer
```

Make executable:

```bash
chmod +x ~/scripts/matagaruda-gap-consumer.sh
```

- [ ] **Step 2: Test the wrapper**

```bash
~/scripts/matagaruda-gap-consumer.sh 2>&1 | head -20
```

Expected: log lines, no crash. May say "no new gaps" if the consumer group is up-to-date or "consumer group exists" warnings — both fine.

- [ ] **Step 3: Create the LaunchAgent plist**

Create `~/Library/LaunchAgents/com.matagaruda.gap.consumer.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.matagaruda.gap.consumer</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/scripts/matagaruda-gap-consumer.sh</string>
    </array>

    <key>StartInterval</key>
    <integer>600</integer>

    <key>RunAtLoad</key>
    <false/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin</string>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/matagaruda-gap-consumer.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/matagaruda-gap-consumer-err.log</string>
</dict>
</plist>
```

- [ ] **Step 4: Load the LaunchAgent**

```bash
launchctl load ~/Library/LaunchAgents/com.matagaruda.gap.consumer.plist
launchctl list com.matagaruda.gap.consumer
```

Expected: `LastExitStatus = 0`.

- [ ] **Step 5: Add to automation_catalog.json**

In `scripts/automation_catalog.json`, inside `launchagents`, add:

```json
"com.matagaruda.gap.consumer": {
  "description": "Mata Garuda gap consumer — reads nexus:gaps stream (currently 552 entries), dispatches agents per gap type. Maps 7 of 8 gap types to lhkpn_harvester or regulation_watcher; missing_procurement deferred to Phase 2.",
  "type": "scheduled",
  "produces": "garuda:raw entries (via dispatched agents)",
  "consumes": "Redis stream nexus:gaps",
  "uses_llm": "claude --print (via dispatched agents)",
  "llm_interface": "MetaChain CLI subprocess",
  "tools_called": ["redis-cli (XREADGROUP/XACK)", "MetaChain.run()"],
  "apis_called": ["antv.kpk.go.id (via lhkpn_harvester)", "peraturan.go.id (via regulation_watcher)"],
  "schedule": "every 10min, 06:00-22:00 WITA"
}
```

- [ ] **Step 6: Add to job_registry.json**

```json
"com.matagaruda.gap.consumer": {
  "host": "pro",
  "type": "launchagent",
  "plist": "~/Library/LaunchAgents/com.matagaruda.gap.consumer.plist",
  "schedule_seconds": 600,
  "staleness_threshold_s": 1800,
  "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.matagaruda.gap.consumer",
  "repair_scope": "infra",
  "critical": false
}
```

- [ ] **Step 7: Add lhkpn_harvester to automation_catalog**

In the same file, add an `agents.lhkpn_harvester` section (or under whatever Mata Garuda agents structure exists):

```json
"lhkpn_harvester": {
  "description": "Mata Garuda Layer 1 harvester for LHKPN wealth declarations (antv.kpk.go.id). Dispatched by gap_consumer for 4 gap types: missing_nip, missing_lhkpn, missing_angkatan, stale_official.",
  "produces": "garuda:raw entries (type: harvest.lhkpn)",
  "consumes": "antv.kpk.go.id HTTP, gap_consumer dispatch",
  "uses_llm": "claude --print (via MetaChain)",
  "llm_interface": "Claude CLI subprocess",
  "tools_called": ["scrape_lhkpn_search()", "scrape_lhkpn_profile()", "stream_publish()"]
}
```

- [ ] **Step 8: Commit catalog + registry updates**

```bash
git add scripts/automation_catalog.json
git commit -m "chore(catalog): register gap_consumer + lhkpn_harvester"
```

---

## Task 16: End-to-end verification

**Files:** none — purely operational verification. No commit unless something needs fixing.

- [ ] **Step 1: Verify Mata Garuda full test suite passes**

```bash
cd apps/mata-garuda && source .venv/bin/activate
pytest tests/ -q
```

Expected: all tests PASS (existing 105+ + ~30 new).

- [ ] **Step 2: Verify backend full test suite passes**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/ -q -x --ignore=backend/tests/integration
```

Expected: all tests PASS.

- [ ] **Step 3: Verify import chain (catches rogue AI removals)**

```bash
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Verify the bridge cycle on real Redis (no Fly required)**

```bash
# Insert a fake event in bridge:outbound
redis-cli XADD bridge:outbound '*' \
  id "test-uuid-1" \
  type "intel.article_ready" \
  source "manual_test" \
  timestamp "$(date -u +'%Y-%m-%dT%H:%M:%S+00:00')" \
  priority "3" \
  payload '{"article_id": "test-1", "title": "Manual test", "body_mdx": "# x", "topic": "test"}'

# Verify it landed
redis-cli XLEN bridge:outbound
```

Expected: increments by 1.

- [ ] **Step 5: Verify the gap consumer is reading**

```bash
# Check that the consumer group exists and is positioned
redis-cli XINFO GROUPS nexus:gaps
```

Expected: shows `gap-consumer` group with a `last-delivered-id`.

- [ ] **Step 6: Check that the bridge is live**

```bash
launchctl list com.matagaruda.bridge.adaptive
launchctl list com.matagaruda.gap.consumer
tail -20 ~/logs/matagaruda-bridge.log
tail -20 ~/logs/matagaruda-gap-consumer.log
```

Expected: both `LastExitStatus = 0`, log files have recent entries.

- [ ] **Step 7: Capture before/after metrics**

```bash
echo "=== ORGANISM PHASE 1 — METRICS SNAPSHOT $(date) ===" > /tmp/phase1_metrics.txt
echo "" >> /tmp/phase1_metrics.txt
echo "Stream lengths:" >> /tmp/phase1_metrics.txt
for s in garuda:raw garuda:enriched garuda:alerts nexus:gaps bridge:outbound bridge:inbound; do
    L=$(redis-cli XLEN $s 2>/dev/null || echo "n/a")
    printf "  %-20s %s\n" "$s" "$L" >> /tmp/phase1_metrics.txt
done
echo "" >> /tmp/phase1_metrics.txt
echo "Gap consumer group:" >> /tmp/phase1_metrics.txt
redis-cli XINFO GROUPS nexus:gaps 2>/dev/null >> /tmp/phase1_metrics.txt || echo "  (no group yet)" >> /tmp/phase1_metrics.txt
echo "" >> /tmp/phase1_metrics.txt
echo "Bridge cursor:" >> /tmp/phase1_metrics.txt
cat ~/.agent/decisions/bridge_cursor.json 2>/dev/null >> /tmp/phase1_metrics.txt || echo "  (cursor not yet written)" >> /tmp/phase1_metrics.txt

cat /tmp/phase1_metrics.txt
```

Save the snapshot. After 7 days re-run and compare — that's the empirical "before/after" the spec requires (§11 Phase 1 metrics).

- [ ] **Step 8: Save MOS memories**

```bash
~/.claude/scripts/mem save discovery "Phase 1 Sinapsi deployed: bridge live (60s), gap consumer live (600s), lhkpn_harvester registered. Redis streams baseline saved to /tmp/phase1_metrics.txt. Compare in 7 days." 8

~/.claude/scripts/mem save fact "Phase 1 endpoints live: GET /api/bridge/events, POST /api/bridge/ingest/article, POST /api/bridge/ingest/enrichment. Auth via X-Bridge-Auth header. BRIDGE_API_KEY in ~/.nuzantara-secrets.env and Fly secret." 8
```

- [ ] **Step 9: Final commit (only if anything changed in Step 1-8)**

If automation_catalog.json or job_registry.json were updated based on real behavior observed in Step 4-7, commit them:

```bash
git add scripts/automation_catalog.json
git commit -m "chore(verify): Phase 1 Sinapsi end-to-end verified — baseline metrics captured"
```

---

## Self-Review (Plan Author)

**1. Spec coverage:** Walked through `docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md`:

| Spec section                                     | Plan task      | OK  |
| ------------------------------------------------ | -------------- | --- |
| §3 Envelope (5 fields, dot notation)             | Task 1         | ✓   |
| §4 Bridge nerve (pull+push)                      | Tasks 9, 10    | ✓   |
| §4 BridgeCursor (atomic)                         | Task 2         | ✓   |
| §4 bridge_outbox table                           | Task 3         | ✓   |
| §4 Backend bridge router                         | Tasks 4, 5     | ✓   |
| §4 EventBus → outbox triggers                    | Task 6         | ✓   |
| §4 RAG low_confidence trigger                    | Task 7         | ✓   |
| §5 Gap consumer + dispatch table                 | Task 11        | ✓   |
| §5 LHKPN harvester + GENOME                      | Tasks 12, 13   | ✓   |
| §11 Phase 1 task 1.10 (LaunchAgent bridge)       | Task 14        | ✓   |
| §11 Phase 1 task 1.11 (LaunchAgent gap consumer) | Task 15        | ✓   |
| §11 Phase 1 task 1.12 (catalog update)           | Tasks 14, 15   | ✓   |
| §11 Phase 1 task 1.13 (job_registry)             | Tasks 14, 15   | ✓   |
| §11 Phase 1 task 1.14 (BRIDGE_API_KEY)           | Task 14 step 1 | ✓   |
| §11 Phase 1 metrics (before/after)               | Task 16 step 7 | ✓   |

No gaps. The "30-day retention cron" mentioned in spec §4 is documented in migration 101's docstring — consciously deferred (it's a separate cron not strictly part of Phase 1 Sinapsi). Add as Task 17 if Zero wants it now.

**2. Placeholder scan:** Searched for "TBD", "TODO", "implement later", "appropriate", "similar to" — none in actionable steps. Two "Phase 2" tags in Task 11/12 are explicit deferrals (gap.missing_procurement → lpse_harvester, full Qdrant write for enrichment), documented in spec.

**3. Type consistency:**

- `Envelope.priority` is `int` everywhere (Task 1, 9, 10).
- `BridgeCursor` constructor takes `Path`, used consistently.
- `insert_outbox_event(conn, event_type, payload)` signature matches across Tasks 4, 6, 7.
- `process_gap()` and `run_gap_consumer()` return type stats dict — keys consistent (`read`, `resolved`, `failed`, `skipped`, `unknown`, `errors`).
- Stream constants (`STREAM_BRIDGE_OUTBOUND`, `STREAM_BRIDGE_INBOUND`, `STREAM_NEXUS_GAPS`) defined once in Task 8, imported everywhere.

**4. Ambiguity check:**

- Adaptive 30s/5min schedule simplified to flat 60s with documented trade-off (Task 14 step 5).
- `confidence` variable name in answer.py is left as TBD-by-grep in Task 7 step 1 — engineer must look it up. This is not a placeholder; it's a "read the existing code first" instruction with grep commands provided.

Plan ready.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-14-organism-phase1-sinapsi.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Each task is bite-sized (15-30 min). 16 tasks total → ~6-10 hours of subagent work over multiple sessions, but minimal main-context usage.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints for review. More main-context usage but tighter feedback loop.

**Which approach?**
