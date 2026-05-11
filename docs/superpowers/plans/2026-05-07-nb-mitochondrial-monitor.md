# NB Mitochondrial Value Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily cron monitor that records per-NB metrics into SQLite, classifies each NB into ALIVE/IDLE/DYING tiers, generates a weekly markdown report, and sends Telegram alerts on top-5 drops or tier transitions — measuring which NotebookLM notebooks produce value consumed downstream by Nuzantara.

**Architecture:** Python module `apps/mata-garuda/mata_garuda/scripts/nb_monitor/` with five small files (collectors, tier classifier, alert engine, persistence, report generator) glued by `run.py`. SQLite WAL store at `~/.agent/nb-mitochondrial/metrics.db`. Bootstrap NB list as a JSON file at `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json` (JSON not YAML — avoids adding pyyaml dep; content identical to spec §4.2). LaunchAgent runs `python -m mata_garuda.scripts.nb_monitor.run` daily at 02:30 WITA.

**Tech Stack:** Python 3.11+, stdlib only (`sqlite3`, `json`, `pathlib`, `datetime`, `subprocess`, `argparse`, `logging`, `dataclasses`, `urllib`), pytest 9 + pytest-asyncio (already in `apps/mata-garuda/.venv`). NO new pip dependencies. Telegram via `urllib.request` POST to bot API (no `httpx` needed for a single fire-and-forget call). Spec reference: `docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md`.

---

## File map (created/modified)

**Created:**

- `apps/mata-garuda/mata_garuda/scripts/__init__.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/registry.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/persist.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/tier.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/alerts.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/report.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/__init__.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/log_scraper.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/feeder_log.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/nlm_freshness.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/skill_derivation.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/cite_rate.py`
- `apps/mata-garuda/mata_garuda/scripts/nb_monitor/README.md`
- `apps/mata-garuda/tests/nb_monitor/__init__.py`
- `apps/mata-garuda/tests/nb_monitor/conftest.py`
- `apps/mata-garuda/tests/nb_monitor/test_registry.py`
- `apps/mata-garuda/tests/nb_monitor/test_persist.py`
- `apps/mata-garuda/tests/nb_monitor/test_log_scraper.py`
- `apps/mata-garuda/tests/nb_monitor/test_feeder_log.py`
- `apps/mata-garuda/tests/nb_monitor/test_nlm_freshness.py`
- `apps/mata-garuda/tests/nb_monitor/test_tier.py`
- `apps/mata-garuda/tests/nb_monitor/test_alerts.py`
- `apps/mata-garuda/tests/nb_monitor/test_report.py`
- `apps/mata-garuda/tests/nb_monitor/test_integration_e2e.py`
- `apps/mata-garuda/tests/nb_monitor/fixtures/bootstrap.json`
- `apps/mata-garuda/tests/nb_monitor/fixtures/jsonl_sample.jsonl`
- `apps/mata-garuda/tests/nb_monitor/fixtures/feeder_sample.jsonl`
- `scripts/nb-monitor/show.py` (CLI dashboard)
- `infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist`
- `docs/operations/nb-mitochondrial-monitor.md`
- `docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md`
- `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json` (NOT git-tracked)

**Modified:** none (read-only on existing pipeline per spec §7.1).

---

## Conventions and shared snippets

All paths assume **CWD = repo root** (`/Users/nuzantara/Desktop/nuzantara/.worktrees/nb-mitochondrial` during this work).

**Run all nb_monitor tests:**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/ -v
```

**Run one test:**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_registry.py::test_load_returns_dataclass_list -v
```

**WIP commit pattern** (cicatrix antibody — every ~10 min while untracked files exist):

```bash
if git ls-files --others --exclude-standard | grep -q .; then
  git add -A apps/mata-garuda/mata_garuda/scripts/nb_monitor/ apps/mata-garuda/tests/nb_monitor/
  git commit -m "WIP(nb-monitor): checkpoint $(date +%H:%M)"
  git push origin feat/nb-mitochondrial-monitor-2026-05-07
fi
```

**Imports — use absolute throughout** (mata-garuda golden rule):

```python
from mata_garuda.scripts.nb_monitor.registry import NotebookEntry, load_registry
```

**Type hints — full annotations on every function** (mata-garuda golden rule).

**Logging — `logging.getLogger(__name__)`, never `print()`.**

---

## COMMIT BLOCK 1 — Bootstrap registry + LaunchAgent skeleton

### Task 1: Create package directories and **init**.py files

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/__init__.py`
- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py`
- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/__init__.py`
- Create: `apps/mata-garuda/tests/nb_monitor/__init__.py`

- [ ] **Step 1: Create empty package init files**

```bash
mkdir -p apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors
mkdir -p apps/mata-garuda/tests/nb_monitor/fixtures
touch apps/mata-garuda/mata_garuda/scripts/__init__.py
touch apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/__init__.py
touch apps/mata-garuda/tests/nb_monitor/__init__.py
```

- [ ] **Step 2: Write package docstring in `nb_monitor/__init__.py`**

```python
"""
NB Mitochondrial Value Monitor.

Daily cron that measures which NotebookLM notebooks produce value consumed
downstream by Nuzantara. Five metric collectors → tier classifier → SQLite
snapshot → optional Telegram alert + weekly markdown report.

Spec: docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md
Plan: docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md
"""
__version__ = "0.1.0"
```

Write this content to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py`.

- [ ] **Step 3: Verify package imports**

```bash
cd apps/mata-garuda && .venv/bin/python -c "from mata_garuda.scripts.nb_monitor import __version__; print(__version__)"
```

Expected: `0.1.0`

- [ ] **Step 4: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/__init__.py \
        apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py \
        apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/__init__.py \
        apps/mata-garuda/tests/nb_monitor/__init__.py
git commit -m "feat(nb-monitor): scaffold package directories"
```

---

### Task 2: NotebookEntry dataclass and registry loader (TDD)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/registry.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_registry.py`
- Test fixture: `apps/mata-garuda/tests/nb_monitor/fixtures/bootstrap.json`

- [ ] **Step 1: Write the test fixture**

Write to `apps/mata-garuda/tests/nb_monitor/fixtures/bootstrap.json`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-07",
  "source": "test fixture",
  "notebooks": [
    {
      "uuid": "1ed02e54-542f-426a-94f8-53c5ffde4b7d",
      "name": "NB-INTEL-Immigration",
      "family": "INTEL",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Curated High Value"
    },
    {
      "uuid": "9d262101-abeb-4e15-af9c-c38e028c62fe",
      "name": "NB-INTEL-Press",
      "family": "INTEL",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Curated High Value"
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Write to `apps/mata-garuda/tests/nb_monitor/test_registry.py`:

```python
"""Tests for nb_monitor.registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.registry import (
    NotebookEntry,
    load_registry,
    RegistryLoadError,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_returns_dataclass_list():
    path = FIXTURES / "bootstrap.json"
    entries = load_registry(path)
    assert len(entries) == 2
    assert all(isinstance(e, NotebookEntry) for e in entries)
    assert entries[0].uuid == "1ed02e54-542f-426a-94f8-53c5ffde4b7d"
    assert entries[0].name == "NB-INTEL-Immigration"
    assert entries[0].family == "INTEL"
    assert entries[0].lifecycle_stage == "TAC"
    assert entries[0].active_routing is True
    assert entries[0].first_audited == "2026-05-04"
    assert entries[0].round2_classification == "Curated High Value"


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(RegistryLoadError, match="not found"):
        load_registry(tmp_path / "nonexistent.json")


def test_load_malformed_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(RegistryLoadError, match="invalid JSON"):
        load_registry(bad)


def test_load_missing_required_field_raises(tmp_path):
    bad = tmp_path / "incomplete.json"
    bad.write_text('{"schema_version": 1, "notebooks": [{"uuid": "x"}]}')
    with pytest.raises(RegistryLoadError, match="missing required field"):
        load_registry(bad)


def test_load_wrong_schema_version_raises(tmp_path):
    bad = tmp_path / "v999.json"
    bad.write_text('{"schema_version": 999, "notebooks": []}')
    with pytest.raises(RegistryLoadError, match="schema_version"):
        load_registry(bad)
```

- [ ] **Step 3: Run test to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_registry.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mata_garuda.scripts.nb_monitor.registry'`

- [ ] **Step 4: Implement `registry.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/registry.py`:

```python
"""NB registry loader.

Reads the bootstrap JSON file at ~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json
and returns a list of NotebookEntry dataclasses. ADR-006 documents the
migration plan to apps/mata-garuda/mata_garuda/notebook_registry.py post-FASE-2 merge.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
REQUIRED_FIELDS = (
    "uuid",
    "name",
    "family",
    "lifecycle_stage",
    "active_routing",
    "first_audited",
)


class RegistryLoadError(Exception):
    """Raised when the bootstrap registry cannot be parsed."""


@dataclass(frozen=True)
class NotebookEntry:
    uuid: str
    name: str
    family: str  # INTEL | MATA-GARUDA | CORE | RESEARCH | SUBHI | META
    lifecycle_stage: str  # DM | TAC | SENESCENT | KILL_PENDING | APOPTOSIS_DONE | ORPHAN_REVIEW
    active_routing: bool
    first_audited: str  # ISO date
    last_audited: str | None = None
    round2_classification: str | None = None


def load_registry(path: Path) -> list[NotebookEntry]:
    """Load the bootstrap JSON file and return a list of NotebookEntry."""
    if not path.exists():
        raise RegistryLoadError(f"registry file not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise RegistryLoadError(f"invalid JSON in {path}: {e}") from e

    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise RegistryLoadError(
            f"unsupported schema_version {schema_version!r} (expected {SCHEMA_VERSION})"
        )

    notebooks = data.get("notebooks", [])
    return list(_parse_entries(notebooks, source=str(path)))


def _parse_entries(notebooks: Iterable[dict], source: str) -> Iterable[NotebookEntry]:
    for idx, nb in enumerate(notebooks):
        for field in REQUIRED_FIELDS:
            if field not in nb:
                raise RegistryLoadError(
                    f"{source}: notebooks[{idx}] missing required field '{field}'"
                )
        yield NotebookEntry(
            uuid=nb["uuid"],
            name=nb["name"],
            family=nb["family"],
            lifecycle_stage=nb["lifecycle_stage"],
            active_routing=bool(nb["active_routing"]),
            first_audited=nb["first_audited"],
            last_audited=nb.get("last_audited"),
            round2_classification=nb.get("round2_classification"),
        )
```

- [ ] **Step 5: Run test to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_registry.py -v
```

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/registry.py \
        apps/mata-garuda/tests/nb_monitor/test_registry.py \
        apps/mata-garuda/tests/nb_monitor/fixtures/bootstrap.json
git commit -m "feat(nb-monitor): registry loader with NotebookEntry dataclass"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 3: SQLite persistence layer (TDD)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/persist.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_persist.py`

- [ ] **Step 1: Write failing tests for schema + WAL pragma**

Write to `apps/mata-garuda/tests/nb_monitor/test_persist.py`:

```python
"""Tests for nb_monitor.persist."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.persist import (
    MetricRow,
    AlertRecord,
    connect,
    ensure_schema,
    insert_metric_row,
    insert_alert_record,
    fetch_latest_per_uuid,
    fetch_alert_last_sent,
)


def _open(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    ensure_schema(conn)
    return conn


def test_ensure_schema_creates_tables(tmp_path):
    conn = _open(tmp_path / "m.db")
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [r[0] for r in cursor.fetchall()]
    assert "schema_version" in tables
    assert "nb_metrics" in tables
    assert "alerts_sent" in tables
    conn.close()


def test_ensure_schema_records_version(tmp_path):
    conn = _open(tmp_path / "m.db")
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 1
    conn.close()


def test_ensure_schema_is_idempotent(tmp_path):
    db = tmp_path / "m.db"
    conn1 = _open(db)
    conn1.close()
    conn2 = _open(db)
    rows = conn2.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert rows == 1
    conn2.close()


def test_wal_mode_enabled(tmp_path):
    conn = _open(tmp_path / "m.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    conn.close()


def test_foreign_keys_enabled(tmp_path):
    conn = _open(tmp_path / "m.db")
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    conn.close()


def test_insert_metric_row_round_trip(tmp_path):
    conn = _open(tmp_path / "m.db")
    row = MetricRow(
        uuid="u1",
        ts_capture=1700000000,
        tier="ALIVE",
        read_freq_7d=42,
        read_freq_30d=200,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=10,
        push_success_rate=0.99,
        instrumentation_status="ok",
    )
    insert_metric_row(conn, row)
    fetched = conn.execute(
        "SELECT uuid, tier, read_freq_7d, push_success_rate, instrumentation_status "
        "FROM nb_metrics WHERE uuid=?",
        ("u1",),
    ).fetchone()
    assert fetched == ("u1", "ALIVE", 42, 0.99, "ok")
    conn.close()


def test_insert_metric_row_handles_nulls(tmp_path):
    conn = _open(tmp_path / "m.db")
    row = MetricRow(
        uuid="u2",
        ts_capture=1700000001,
        tier="IDLE",
        read_freq_7d=None,
        read_freq_30d=None,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=None,
        push_success_rate=None,
        instrumentation_status="parse_failure",
    )
    insert_metric_row(conn, row)
    fetched = conn.execute(
        "SELECT read_freq_7d, push_success_rate FROM nb_metrics WHERE uuid=?",
        ("u2",),
    ).fetchone()
    assert fetched == (None, None)
    conn.close()


def test_fetch_latest_per_uuid_returns_most_recent(tmp_path):
    conn = _open(tmp_path / "m.db")
    for ts in [1700000000, 1700000100, 1700000050]:
        insert_metric_row(
            conn,
            MetricRow(
                uuid="u1",
                ts_capture=ts,
                tier="ALIVE",
                read_freq_7d=ts % 100,
                read_freq_30d=None,
                skill_derivation_count=None,
                downstream_cite_rate=None,
                source_freshness_age_days=None,
                push_success_rate=None,
                instrumentation_status="ok",
            ),
        )
    latest = fetch_latest_per_uuid(conn, "u1")
    assert latest is not None
    assert latest.ts_capture == 1700000100
    assert latest.read_freq_7d == 0
    conn.close()


def test_fetch_latest_per_uuid_returns_none_when_missing(tmp_path):
    conn = _open(tmp_path / "m.db")
    assert fetch_latest_per_uuid(conn, "missing") is None
    conn.close()


def test_insert_and_fetch_alert(tmp_path):
    conn = _open(tmp_path / "m.db")
    insert_alert_record(
        conn,
        AlertRecord(
            uuid="u1",
            condition="top5_drop_50pct",
            sent_at=1700000000,
            payload='{"prev":100,"now":40}',
        ),
    )
    last = fetch_alert_last_sent(conn, "u1", "top5_drop_50pct")
    assert last == 1700000000
    conn.close()


def test_fetch_alert_last_sent_returns_none_for_unknown(tmp_path):
    conn = _open(tmp_path / "m.db")
    assert fetch_alert_last_sent(conn, "u1", "top5_drop_50pct") is None
    conn.close()


def test_metric_row_primary_key_uuid_ts(tmp_path):
    """Inserting same (uuid, ts_capture) twice should raise IntegrityError."""
    conn = _open(tmp_path / "m.db")
    row = MetricRow(
        uuid="u1",
        ts_capture=1700000000,
        tier="ALIVE",
        read_freq_7d=1,
        read_freq_30d=None,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=None,
        push_success_rate=None,
        instrumentation_status="ok",
    )
    insert_metric_row(conn, row)
    with pytest.raises(sqlite3.IntegrityError):
        insert_metric_row(conn, row)
    conn.close()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_persist.py -v
```

Expected: FAIL — `ModuleNotFoundError: persist`

- [ ] **Step 3: Implement `persist.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/persist.py`:

```python
"""SQLite persistence layer for nb_monitor.

Schema versioning: v1 = initial. PRAGMA journal_mode=WAL for safe
concurrent reads while a daily writer is appending.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MetricRow:
    uuid: str
    ts_capture: int
    tier: str
    read_freq_7d: int | None
    read_freq_30d: int | None
    skill_derivation_count: int | None
    downstream_cite_rate: float | None
    source_freshness_age_days: int | None
    push_success_rate: float | None
    instrumentation_status: str


@dataclass(frozen=True)
class AlertRecord:
    uuid: str
    condition: str
    sent_at: int
    payload: str | None = None


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with WAL + FK pragmas applied."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and record schema version. Idempotent."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nb_metrics (
            uuid                       TEXT NOT NULL,
            ts_capture                 INTEGER NOT NULL,
            tier                       TEXT NOT NULL,
            read_freq_7d               INTEGER,
            read_freq_30d              INTEGER,
            skill_derivation_count     INTEGER,
            downstream_cite_rate       REAL,
            source_freshness_age_days  INTEGER,
            push_success_rate          REAL,
            instrumentation_status     TEXT,
            PRIMARY KEY (uuid, ts_capture)
        );
        CREATE INDEX IF NOT EXISTS idx_uuid_ts ON nb_metrics(uuid, ts_capture DESC);
        CREATE INDEX IF NOT EXISTS idx_ts_capture ON nb_metrics(ts_capture DESC);

        CREATE TABLE IF NOT EXISTS alerts_sent (
            uuid       TEXT NOT NULL,
            condition  TEXT NOT NULL,
            sent_at    INTEGER NOT NULL,
            payload    TEXT,
            PRIMARY KEY (uuid, condition, sent_at)
        );
        CREATE INDEX IF NOT EXISTS idx_alert_lookup
          ON alerts_sent(uuid, condition, sent_at DESC);
        """
    )
    existing = conn.execute(
        "SELECT version FROM schema_version WHERE version=?",
        (CURRENT_SCHEMA_VERSION,),
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (CURRENT_SCHEMA_VERSION, int(time.time())),
        )
    conn.commit()


def insert_metric_row(conn: sqlite3.Connection, row: MetricRow) -> None:
    conn.execute(
        """
        INSERT INTO nb_metrics (
            uuid, ts_capture, tier, read_freq_7d, read_freq_30d,
            skill_derivation_count, downstream_cite_rate,
            source_freshness_age_days, push_success_rate, instrumentation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.uuid,
            row.ts_capture,
            row.tier,
            row.read_freq_7d,
            row.read_freq_30d,
            row.skill_derivation_count,
            row.downstream_cite_rate,
            row.source_freshness_age_days,
            row.push_success_rate,
            row.instrumentation_status,
        ),
    )
    conn.commit()


def insert_alert_record(conn: sqlite3.Connection, record: AlertRecord) -> None:
    conn.execute(
        """
        INSERT INTO alerts_sent (uuid, condition, sent_at, payload)
        VALUES (?, ?, ?, ?)
        """,
        (record.uuid, record.condition, record.sent_at, record.payload),
    )
    conn.commit()


def fetch_latest_per_uuid(conn: sqlite3.Connection, uuid: str) -> MetricRow | None:
    cursor = conn.execute(
        """
        SELECT uuid, ts_capture, tier, read_freq_7d, read_freq_30d,
               skill_derivation_count, downstream_cite_rate,
               source_freshness_age_days, push_success_rate, instrumentation_status
          FROM nb_metrics
         WHERE uuid=?
         ORDER BY ts_capture DESC
         LIMIT 1
        """,
        (uuid,),
    )
    r = cursor.fetchone()
    if r is None:
        return None
    return MetricRow(*r)


def fetch_alert_last_sent(
    conn: sqlite3.Connection, uuid: str, condition: str
) -> int | None:
    r = conn.execute(
        "SELECT MAX(sent_at) FROM alerts_sent WHERE uuid=? AND condition=?",
        (uuid, condition),
    ).fetchone()
    return r[0] if r and r[0] is not None else None
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_persist.py -v
```

Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/persist.py \
        apps/mata-garuda/tests/nb_monitor/test_persist.py
git commit -m "feat(nb-monitor): SQLite persistence layer with WAL + schema v1"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 4: Bootstrap registry JSON file (24 entries)

**Files:**

- Create: `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json` (NOT git-tracked)
- Modify: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py` (add path constant)

**Note:** The bootstrap file lives outside the repo at `~/.agent/nb-monitor/`. This task creates it on disk on Pro. The format mirrors spec §4.2. The 24 UUIDs are derived per question 1/4 in the brainstorm: 6 from `config.py NLM_NOTEBOOKS` + ~18 placeholders for FASE-2 SENESCENT/APOPTOSIS_DONE candidates. UUIDs that are not yet known are filled with a `placeholder-N-XXXX` synthetic value and marked `lifecycle_stage: "ORPHAN_REVIEW"` until FASE-2 publishes the SSOT.

- [ ] **Step 1: Create the bootstrap directory**

```bash
mkdir -p ~/.agent/nb-monitor
```

- [ ] **Step 2: Write the bootstrap JSON**

Write to `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-07",
  "source": "config.py NLM_NOTEBOOKS + Round 2 memory + manual curation. ADR-006: migrate to mata_garuda.notebook_registry on FASE 2 merge.",
  "notebooks": [
    {
      "uuid": "1ed02e54-542f-426a-94f8-53c5ffde4b7d",
      "name": "NB-INTEL-Immigration",
      "family": "INTEL",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Curated High Value"
    },
    {
      "uuid": "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f",
      "name": "NB-INTEL-Tax",
      "family": "INTEL",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Curated High Value"
    },
    {
      "uuid": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76",
      "name": "NB-INTEL-Regulation",
      "family": "INTEL",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Curated High Value"
    },
    {
      "uuid": "9d262101-abeb-4e15-af9c-c38e028c62fe",
      "name": "NB-INTEL-Press",
      "family": "INTEL",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Curated High Value"
    },
    {
      "uuid": "dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
      "name": "NB-INTEL-AIResearch",
      "family": "INTEL",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Curated High Value"
    },
    {
      "uuid": "305f5f2e-d2f4-4f77-a771-c2b7aa0867e4",
      "name": "Mata Garuda Self-Evolving Research",
      "family": "RESEARCH",
      "lifecycle_stage": "TAC",
      "active_routing": true,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Ghiandola Epigenetica"
    },
    {
      "uuid": "d9438180-5e63-4e2a-a473-6061101f6a8d",
      "name": "NB-5 Property",
      "family": "CORE",
      "lifecycle_stage": "DM",
      "active_routing": false,
      "first_audited": "2026-05-04",
      "last_audited": "2026-05-07",
      "round2_classification": "Codice Genetico Procedurale"
    }
  ]
}
```

**Note:** Initial seed with 7 confirmed UUIDs. The remaining 17 (KILL/EXPORT placeholders for FASE-2 work) are NOT included — better to start with verified entries. The cron will warn if the registry has fewer than 24 entries; that warning is documented in Task 18 as informational, not blocking. ADR-006 (Task 30) describes the FASE-2 migration that will populate the rest.

- [ ] **Step 3: Verify file is valid JSON and loadable**

```bash
python3 -c "import json; data=json.load(open('$HOME/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json')); print('entries:', len(data['notebooks']))"
```

Expected: `entries: 7`

- [ ] **Step 4: Add path constant to `__init__.py`**

Modify `apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py` to add the bootstrap path constant. The full file becomes:

```python
"""
NB Mitochondrial Value Monitor.

Daily cron that measures which NotebookLM notebooks produce value consumed
downstream by Nuzantara. Five metric collectors → tier classifier → SQLite
snapshot → optional Telegram alert + weekly markdown report.

Spec: docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md
Plan: docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md
"""
from __future__ import annotations

import os
from pathlib import Path

__version__ = "0.1.0"

DATA_DIR = Path(os.environ.get("NB_MONITOR_DATA_DIR", str(Path.home() / ".agent" / "nb-mitochondrial")))
REGISTRY_DIR = Path(os.environ.get("NB_MONITOR_REGISTRY_DIR", str(Path.home() / ".agent" / "nb-monitor")))
BOOTSTRAP_FILE = REGISTRY_DIR / "active_notebooks_bootstrap_2026-05-07.json"
METRICS_DB = DATA_DIR / "metrics.db"
LOG_FILE = DATA_DIR / "logs" / "nb-monitor.log"
```

- [ ] **Step 5: Verify constants resolve**

```bash
cd apps/mata-garuda && .venv/bin/python -c "from mata_garuda.scripts.nb_monitor import BOOTSTRAP_FILE, METRICS_DB; print('bootstrap:', BOOTSTRAP_FILE); print('db:', METRICS_DB)"
```

Expected:

```
bootstrap: /Users/nuzantara/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json
db: /Users/nuzantara/.agent/nb-mitochondrial/metrics.db
```

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py
git commit -m "feat(nb-monitor): add path constants for bootstrap + db locations"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 5: LaunchAgent plist (skeleton, not yet loaded)

**Files:**

- Create: `infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist`

**Note:** This task creates the plist file in the repo. It is NOT loaded into launchd in this task — that happens after the smoke test in Task 28.

- [ ] **Step 1: Verify infra/launchagents directory**

```bash
ls infra/launchagents/ 2>&1 | head -5
```

If missing: `mkdir -p infra/launchagents`.

- [ ] **Step 2: Write the plist**

Write to `infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.nb-mitochondrial-monitor.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python</string>
        <string>-m</string>
        <string>mata_garuda.scripts.nb_monitor.run</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/.agent/nb-mitochondrial/logs/nb-monitor.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/.agent/nb-mitochondrial/logs/nb-monitor.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>PATH</key>
        <string>/Users/nuzantara/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 3: Verify plist is valid**

```bash
plutil -lint infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist
```

Expected: `... OK`

- [ ] **Step 4: Commit**

```bash
git add infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist
git commit -m "feat(nb-monitor): launchagent plist for daily 02:30 WITA cron"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

## COMMIT BLOCK 2 — Live metric collectors

### Task 6: Log scraper for Claude Code JSONL — read frequency (TDD part 1)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/log_scraper.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_log_scraper.py`
- Test fixture: `apps/mata-garuda/tests/nb_monitor/fixtures/jsonl_sample.jsonl`

- [ ] **Step 1: Write the JSONL fixture**

Write to `apps/mata-garuda/tests/nb_monitor/fixtures/jsonl_sample.jsonl`:

```jsonl
{"type":"user","content":"hello"}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"1ed02e54-542f-426a-94f8-53c5ffde4b7d","query":"x"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebookId":"7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f","query":"y"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"1ed02e54-542f-426a-94f8-53c5ffde4b7d","query":"z"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__source_add","input":{"notebook_id":"d9438180-5e63-4e2a-a473-6061101f6a8d"}}]}}
not valid json
{"type":"user","content":"end"}
```

- [ ] **Step 2: Write failing tests**

Write to `apps/mata-garuda/tests/nb_monitor/test_log_scraper.py`:

```python
"""Tests for nb_monitor.collectors.log_scraper."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.collectors.log_scraper import (
    iter_nlm_events,
    count_nlm_events_by_uuid,
    NLMEvent,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_iter_nlm_events_yields_only_nlm_tool_calls(tmp_path):
    src = FIXTURES / "jsonl_sample.jsonl"
    target = tmp_path / "session.jsonl"
    target.write_bytes(src.read_bytes())

    events = list(iter_nlm_events([target]))
    assert len(events) == 4  # 3 notebook_query + 1 source_add
    uuids = [e.uuid for e in events]
    assert "1ed02e54-542f-426a-94f8-53c5ffde4b7d" in uuids
    assert "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f" in uuids
    assert all(isinstance(e, NLMEvent) for e in events)


def test_iter_nlm_events_supports_both_field_variants(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebookId":"b"}}]}}\n'
    )
    events = list(iter_nlm_events([p]))
    assert {e.uuid for e in events} == {"a", "b"}


def test_iter_nlm_events_skips_malformed_lines(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        "not json\n"
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a"}}]}}\n'
        "still not json\n"
    )
    events = list(iter_nlm_events([p]))
    assert len(events) == 1


def test_iter_nlm_events_skips_non_nlm_tools(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"x"}}]}}\n'
    )
    events = list(iter_nlm_events([p]))
    assert events == []


def test_count_nlm_events_by_uuid(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a","query":"1"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a","query":"2"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebookId":"b","query":"x"}}]}}\n'
    )
    counts = count_nlm_events_by_uuid([p], window_seconds=86400 * 30, now=10**12)
    assert counts == {"a": 2, "b": 1}


def test_count_nlm_events_filters_by_window(tmp_path, monkeypatch):
    """File mtime older than window must be skipped entirely."""
    import os

    old = tmp_path / "old.jsonl"
    old.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a"}}]}}\n'
    )
    # Set mtime to 60 days ago.
    sixty_days_ago = int(__import__("time").time()) - 60 * 86400
    os.utime(old, (sixty_days_ago, sixty_days_ago))

    new = tmp_path / "new.jsonl"
    new.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"b"}}]}}\n'
    )

    counts = count_nlm_events_by_uuid([old, new], window_seconds=7 * 86400)
    assert counts == {"b": 1}


def test_count_nlm_events_returns_empty_on_no_files(tmp_path):
    counts = count_nlm_events_by_uuid([], window_seconds=86400)
    assert counts == {}
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_log_scraper.py -v
```

Expected: FAIL `ModuleNotFoundError: log_scraper`

- [ ] **Step 4: Implement `log_scraper.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/log_scraper.py`:

```python
"""Claude Code JSONL session log scraper.

Counts tool_use events for `mcp__notebooklm-mcp__*` tools, grouped by NB
UUID. Reads from PRIMARY_PATHS (the Pro project session dir) and falls
back to SECONDARY_PATHS for completeness. UUID extracted from
`input.notebook_id` OR `input.notebookId` (schema variant guard).

Per spec §3.3 / §7.4: read-only, no side effects on existing pipeline.
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

logger = logging.getLogger(__name__)

PRIMARY_PATHS: tuple[Path, ...] = (
    Path.home() / ".claude" / "projects" / "-Users-nuzantara",
)
SECONDARY_PATHS: tuple[Path, ...] = (
    Path.home() / ".claude" / "projects",
)

NLM_TOOL_PREFIX = "mcp__notebooklm"


@dataclass(frozen=True)
class NLMEvent:
    uuid: str
    tool_name: str
    source_file: Path


def discover_session_files(
    primary: tuple[Path, ...] = PRIMARY_PATHS,
    secondary: tuple[Path, ...] = SECONDARY_PATHS,
    cutoff_mtime: float | None = None,
) -> list[Path]:
    """Discover JSONL session files newer than cutoff_mtime."""
    out: list[Path] = []
    seen: set[Path] = set()
    for root in (*primary, *secondary):
        if not root.exists():
            continue
        for f in root.rglob("*.jsonl"):
            if f in seen:
                continue
            try:
                if cutoff_mtime is not None and f.stat().st_mtime < cutoff_mtime:
                    continue
            except OSError:
                continue
            out.append(f)
            seen.add(f)
    return out


def iter_nlm_events(files: Iterable[Path]) -> Iterator[NLMEvent]:
    """Yield NLMEvent for every NLM tool_use entry in the given files.

    Malformed JSON lines are skipped silently.
    """
    for f in files:
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield from _extract_events(record, source=f)
        except OSError as e:
            logger.warning("log_scraper: cannot read %s: %s", f, e)


def _extract_events(record: dict, source: Path) -> Iterator[NLMEvent]:
    """Walk the record's content array looking for NLM tool_use entries."""
    msg = record.get("message")
    if not isinstance(msg, dict):
        return
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use":
            continue
        name = item.get("name", "")
        if not isinstance(name, str) or not name.startswith(NLM_TOOL_PREFIX):
            continue
        inp = item.get("input")
        if not isinstance(inp, dict):
            continue
        uuid = inp.get("notebook_id") or inp.get("notebookId")
        if not uuid or not isinstance(uuid, str):
            continue
        yield NLMEvent(uuid=uuid, tool_name=name, source_file=source)


def count_nlm_events_by_uuid(
    files: Iterable[Path],
    window_seconds: int,
    now: float | None = None,
) -> dict[str, int]:
    """Count NLM tool_use events per UUID across files within window.

    `files` may include ones older than the window — we filter by file mtime
    so we don't pay the parse cost on stale logs.
    """
    now = now if now is not None else time.time()
    cutoff = now - window_seconds
    fresh = [f for f in files if _safe_mtime(f) >= cutoff]
    counter: Counter[str] = Counter()
    for ev in iter_nlm_events(fresh):
        counter[ev.uuid] += 1
    return dict(counter)


def _safe_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_log_scraper.py -v
```

Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/log_scraper.py \
        apps/mata-garuda/tests/nb_monitor/test_log_scraper.py \
        apps/mata-garuda/tests/nb_monitor/fixtures/jsonl_sample.jsonl
git commit -m "feat(nb-monitor): JSONL log scraper for read_freq metric"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 7: Feeder log parser — push success rate (TDD)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/feeder_log.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_feeder_log.py`
- Test fixture: `apps/mata-garuda/tests/nb_monitor/fixtures/feeder_sample.jsonl`

**Note:** The feeder log at `~/logs/matagaruda-nlm-feeder-stream.log` only carries **global per-stream totals** (alerts/enriched), not per-UUID. So `push_success_rate` for THIS PR is computed as a **global rolling rate** and applied to every UUID where `active_routing=True`. UUIDs with `active_routing=False` get `push_success_rate=None`. This limitation is documented in the report banner (§7.3 of spec) and the README. A future PR can wire per-UUID per-line logging into `nlm_feeder_stream`.

- [ ] **Step 1: Write feeder log fixture**

Write to `apps/mata-garuda/tests/nb_monitor/fixtures/feeder_sample.jsonl`:

```jsonl
{"agent": "nlm_feeder_stream", "alerts": {"processed": 10, "fed": 9, "skipped": 1, "errors": 0}, "enriched": {"processed": 5, "fed": 5, "skipped": 0, "errors": 0}}
{"agent": "nlm_feeder_stream", "alerts": {"processed": 8, "fed": 6, "skipped": 1, "errors": 1}, "enriched": {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}}
not json line
{"agent": "nlm_feeder_stream", "alerts": {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}, "enriched": {"processed": 3, "fed": 3, "skipped": 0, "errors": 0}}
{"agent": "nlm_feeder_stream", "stats": {"processed": 5, "fed": 4, "skipped": 0, "errors": 1}}
```

- [ ] **Step 2: Write failing tests**

Write to `apps/mata-garuda/tests/nb_monitor/test_feeder_log.py`:

```python
"""Tests for nb_monitor.collectors.feeder_log."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.collectors.feeder_log import (
    parse_feeder_log,
    compute_global_push_success_rate,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_feeder_log_extracts_alerts_and_enriched():
    rows = list(parse_feeder_log(FIXTURES / "feeder_sample.jsonl"))
    # 4 valid lines (3 with alerts/enriched + 1 with stats; "not json" skipped)
    assert len(rows) == 4
    first = rows[0]
    assert first["alerts"]["processed"] == 10
    assert first["alerts"]["fed"] == 9
    assert first["alerts"]["errors"] == 0


def test_parse_feeder_log_skips_malformed():
    rows = list(parse_feeder_log(FIXTURES / "feeder_sample.jsonl"))
    # Line 3 is "not json" and must be skipped.
    assert all("not" not in (r.get("agent") or "") for r in rows)


def test_parse_feeder_log_returns_empty_for_missing_file(tmp_path):
    rows = list(parse_feeder_log(tmp_path / "nope.log"))
    assert rows == []


def test_compute_global_push_success_rate_uses_alerts_plus_enriched():
    # processed=23, fed=20, errors=1 → success rate = (fed) / (processed)
    # = 20 / 23 ≈ 0.8696
    rate = compute_global_push_success_rate(FIXTURES / "feeder_sample.jsonl", window_seconds=10**9)
    assert rate is not None
    assert 0.86 <= rate <= 0.88


def test_compute_global_push_success_rate_returns_none_when_no_processed():
    """If processed=0 across all lines, rate is undefined → None."""
    p = Path(os.environ.get("PYTEST_TMP", "/tmp")) / "empty_feeder.jsonl"
    p.write_text(
        '{"alerts":{"processed":0,"fed":0,"skipped":0,"errors":0},"enriched":{"processed":0,"fed":0,"skipped":0,"errors":0}}\n'
    )
    rate = compute_global_push_success_rate(p, window_seconds=10**9)
    assert rate is None


def test_compute_global_push_success_rate_filters_by_mtime(tmp_path):
    p = tmp_path / "old_feeder.jsonl"
    p.write_text(
        '{"alerts":{"processed":10,"fed":9,"skipped":0,"errors":1},"enriched":{"processed":0,"fed":0,"skipped":0,"errors":0}}\n'
    )
    long_ago = int(time.time()) - 30 * 86400
    os.utime(p, (long_ago, long_ago))
    # Window 7 days → file is older than window → must be ignored.
    rate = compute_global_push_success_rate(p, window_seconds=7 * 86400)
    assert rate is None


def test_compute_global_push_success_rate_handles_stats_legacy_shape(tmp_path):
    """Older log lines used `stats` instead of `alerts/enriched`."""
    p = tmp_path / "legacy.jsonl"
    p.write_text(
        '{"agent":"nlm_feeder_stream","stats":{"processed":10,"fed":7,"skipped":0,"errors":3}}\n'
    )
    rate = compute_global_push_success_rate(p, window_seconds=10**9)
    assert rate == 0.7
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_feeder_log.py -v
```

Expected: FAIL `ModuleNotFoundError: feeder_log`

- [ ] **Step 4: Implement `feeder_log.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/feeder_log.py`:

```python
"""Parser for nlm_feeder_stream JSONL log.

The feeder log lives at ~/logs/matagaruda-nlm-feeder-stream.log and writes
a JSON line per cron tick with shape:

    {"agent": "nlm_feeder_stream",
     "alerts": {"processed": N, "fed": N, "skipped": N, "errors": N},
     "enriched": {"processed": N, "fed": N, "skipped": N, "errors": N}}

Older entries used a single "stats" object instead of two streams. We
sum alerts+enriched (or read stats if present) to compute push_success_rate.

GLOBAL ONLY: this log has no per-UUID breakdown. The same rate is applied
to every UUID with active_routing=True. Per-UUID per-message logging is
out of scope for this PR (see ADR-006).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path.home() / "logs" / "matagaruda-nlm-feeder-stream.log"


def parse_feeder_log(path: Path) -> Iterator[dict]:
    """Yield each parsed JSON line from the feeder log. Malformed lines skipped."""
    if not path.exists():
        return
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.warning("feeder_log: cannot read %s: %s", path, e)


def compute_global_push_success_rate(
    path: Path,
    window_seconds: int,
    now: float | None = None,
) -> float | None:
    """Compute global push success rate over the rolling window.

    Returns None if total processed is 0 (undefined rate) or file is older
    than window or missing.
    """
    now = now if now is not None else time.time()
    if not path.exists():
        return None
    try:
        if path.stat().st_mtime < now - window_seconds:
            return None
    except OSError:
        return None

    processed = 0
    fed = 0
    for record in parse_feeder_log(path):
        for key in ("alerts", "enriched", "stats"):
            block = record.get(key)
            if isinstance(block, dict):
                p = block.get("processed", 0)
                f = block.get("fed", 0)
                if isinstance(p, int):
                    processed += p
                if isinstance(f, int):
                    fed += f
    if processed == 0:
        return None
    return fed / processed
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_feeder_log.py -v
```

Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/feeder_log.py \
        apps/mata-garuda/tests/nb_monitor/test_feeder_log.py \
        apps/mata-garuda/tests/nb_monitor/fixtures/feeder_sample.jsonl
git commit -m "feat(nb-monitor): feeder log parser for global push_success_rate"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 8: NLM freshness collector (best-effort) — TDD

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/nlm_freshness.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_nlm_freshness.py`

**Note:** This collector calls the `nlm` CLI as a subprocess. In tests we **mock subprocess.run** — never call the real CLI. Cookie-expired path → return None. Spec §7.2 graceful-degrade matrix.

- [ ] **Step 1: Write failing tests**

Write to `apps/mata-garuda/tests/nb_monitor/test_nlm_freshness.py`:

```python
"""Tests for nb_monitor.collectors.nlm_freshness."""
from __future__ import annotations

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from mata_garuda.scripts.nb_monitor.collectors.nlm_freshness import (
    fetch_source_count,
    fetch_source_freshness_age_days,
    NLMFreshnessError,
)


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["nlm"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_fetch_source_count_parses_json_output():
    fake_out = '{"sources": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]}'
    with patch("subprocess.run", return_value=_completed(fake_out)):
        n = fetch_source_count("uuid-1")
    assert n == 3


def test_fetch_source_count_returns_none_on_cookie_error():
    with patch(
        "subprocess.run",
        return_value=_completed("Authentication required: re-run nlm login", returncode=1),
    ):
        n = fetch_source_count("uuid-1")
    assert n is None


def test_fetch_source_count_returns_none_on_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nlm", timeout=10)):
        n = fetch_source_count("uuid-1")
    assert n is None


def test_fetch_source_freshness_age_days_uses_oldest_source():
    """Median age across N sources, in days, rounded down."""
    fake_out = (
        '{"sources":['
        '{"updated_at":"2026-04-01T00:00:00Z"},'
        '{"updated_at":"2026-05-01T00:00:00Z"},'
        '{"updated_at":"2026-04-15T00:00:00Z"}'
        "]}"
    )
    with patch("subprocess.run", return_value=_completed(fake_out)):
        # Force a deterministic "now" so the age does not drift between runs.
        age = fetch_source_freshness_age_days(
            "uuid-1", now_iso="2026-05-07T00:00:00Z"
        )
    # Median is 2026-04-15 → 22 days before 2026-05-07.
    assert age == 22


def test_fetch_source_freshness_age_days_returns_none_on_empty_sources():
    fake_out = '{"sources": []}'
    with patch("subprocess.run", return_value=_completed(fake_out)):
        age = fetch_source_freshness_age_days("uuid-1", now_iso="2026-05-07T00:00:00Z")
    assert age is None


def test_fetch_source_freshness_age_days_returns_none_on_malformed():
    with patch("subprocess.run", return_value=_completed("not json")):
        age = fetch_source_freshness_age_days("uuid-1", now_iso="2026-05-07T00:00:00Z")
    assert age is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_nlm_freshness.py -v
```

Expected: FAIL `ModuleNotFoundError: nlm_freshness`

- [ ] **Step 3: Implement `nlm_freshness.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/nlm_freshness.py`:

```python
"""nlm CLI based freshness collector.

Best-effort: cookie has 5min TTL. Any error path returns None and signals
`cookie_refresh_pending` upstream (the run loop translates None into
instrumentation_status). Spec §7.2.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Sequence

logger = logging.getLogger(__name__)

NLM_BINARY = "nlm"
DEFAULT_TIMEOUT_S = 15
COOKIE_ERROR_MARKERS = ("authentication required", "re-run nlm login", "cookie expired")


class NLMFreshnessError(Exception):
    """Raised by callers that explicitly want the failure to bubble. Default path returns None."""


def _run_nlm(args: Sequence[str], timeout: int = DEFAULT_TIMEOUT_S) -> str | None:
    try:
        proc = subprocess.run(
            [NLM_BINARY, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("nlm_freshness: subprocess failure: %s", e)
        return None
    if proc.returncode != 0:
        merged = (proc.stdout + proc.stderr).lower()
        if any(m in merged for m in COOKIE_ERROR_MARKERS):
            logger.warning("nlm_freshness: cookie/auth error")
        else:
            logger.warning("nlm_freshness: nlm returncode=%d stderr=%s", proc.returncode, proc.stderr[:200])
        return None
    return proc.stdout


def fetch_source_count(uuid: str) -> int | None:
    """Return the number of sources in the notebook, or None on any failure."""
    out = _run_nlm(["notebook", "info", uuid, "--json"])
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    sources = data.get("sources")
    if not isinstance(sources, list):
        return None
    return len(sources)


def fetch_source_freshness_age_days(uuid: str, now_iso: str | None = None) -> int | None:
    """Return median age (days) of NB sources at `now_iso`, or None on failure."""
    out = _run_nlm(["notebook", "info", uuid, "--json"])
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        return None

    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(timezone.utc)
    ages: list[int] = []
    for s in sources:
        updated = s.get("updated_at") or s.get("created_at")
        if not isinstance(updated, str):
            continue
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except ValueError:
            continue
        ages.append((now - ts).days)
    if not ages:
        return None
    ages.sort()
    return ages[len(ages) // 2]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_nlm_freshness.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/nlm_freshness.py \
        apps/mata-garuda/tests/nb_monitor/test_nlm_freshness.py
git commit -m "feat(nb-monitor): nlm CLI freshness collector with cookie-error degradation"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 9: Placeholder collectors for skill_derivation + cite_rate

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/skill_derivation.py`
- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/cite_rate.py`

**Note:** These two metrics are **N/A pending FASE 1 (skill_derivation) and FASE 4 (cite_rate)** as per spec §3.3 and §7.3. The placeholders return `None` with documented `instrumentation_status`. They are NOT wired to any external system. Tests for them are minimal — just confirm the placeholder contract.

- [ ] **Step 1: Implement `skill_derivation.py` placeholder**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/skill_derivation.py`:

```python
"""Placeholder collector for Qdrant local skill_derivation_count.

Returns None until FASE 1 ships `bali_zero_skills_local` Qdrant collection
on Pro. When ready, this module will query
`point.payload.source_cell` for matches against the NB UUID and return the count.

Spec §3.3, §7.3. ADR-006.
"""
from __future__ import annotations

INSTRUMENTATION_STATUS = "pending_qdrant_local_post_fase1"


def count_skills_for_uuid(uuid: str) -> int | None:
    """Always None pre-FASE-1. Returns the count post-FASE-1."""
    return None
```

- [ ] **Step 2: Implement `cite_rate.py` placeholder**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/cite_rate.py`:

```python
"""Placeholder collector for downstream_cite_rate.

Returns None until FASE 4 wires Oracle citation logging in
apps/backend-rag/backend/services/oracle/. When ready, this module will
read the citation log and compute the rate of Zantara responses citing
source URLs that map to the NB UUID.

Spec §3.3, §7.3. ADR-006.
"""
from __future__ import annotations

INSTRUMENTATION_STATUS = "pending_oracle_logging_post_fase4"


def compute_rate_for_uuid(uuid: str) -> float | None:
    """Always None pre-FASE-4. Returns the cite rate post-FASE-4."""
    return None
```

- [ ] **Step 3: Verify imports work**

```bash
cd apps/mata-garuda && .venv/bin/python -c "from mata_garuda.scripts.nb_monitor.collectors import skill_derivation, cite_rate; print(skill_derivation.count_skills_for_uuid('x')); print(cite_rate.compute_rate_for_uuid('x'))"
```

Expected:

```
None
None
```

- [ ] **Step 4: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/skill_derivation.py \
        apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/cite_rate.py
git commit -m "feat(nb-monitor): placeholder collectors for FASE-1 + FASE-4 metrics"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

## COMMIT BLOCK 3 — Tier classifier + alerts + report + integration

### Task 10: Tier classifier (TDD)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/tier.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_tier.py`

- [ ] **Step 1: Write failing tests**

Write to `apps/mata-garuda/tests/nb_monitor/test_tier.py`:

```python
"""Tests for nb_monitor.tier."""
from __future__ import annotations

import pytest

from mata_garuda.scripts.nb_monitor.tier import (
    Tier,
    TierInputs,
    classify,
)


def _inputs(**overrides) -> TierInputs:
    base = dict(read_freq_7d=20, push_success_rate=0.99, age_days=30)
    base.update(overrides)
    return TierInputs(**base)


def test_alive_when_engaged_and_matured():
    assert classify(_inputs(read_freq_7d=10)) == Tier.ALIVE


def test_alive_when_psr_is_none():
    """psr=None must not downgrade — neutral default."""
    assert classify(_inputs(push_success_rate=None)) == Tier.ALIVE


def test_idle_when_age_is_below_bootstrap_window():
    assert classify(_inputs(age_days=3, read_freq_7d=100)) == Tier.IDLE


def test_idle_when_freq_below_alive_threshold():
    assert classify(_inputs(read_freq_7d=4)) == Tier.IDLE


def test_idle_when_push_success_below_alive_threshold():
    assert classify(_inputs(push_success_rate=0.85)) == Tier.IDLE


def test_dying_when_idle_long_and_psr_low():
    assert (
        classify(_inputs(read_freq_7d=0, age_days=30, push_success_rate=0.5))
        == Tier.DYING
    )


def test_dying_when_idle_long_and_psr_none():
    """psr=None should still be eligible for DYING (Round 2 decision)."""
    assert (
        classify(_inputs(read_freq_7d=0, age_days=30, push_success_rate=None))
        == Tier.DYING
    )


def test_idle_takes_precedence_over_dying_for_young_nb():
    assert (
        classify(_inputs(read_freq_7d=0, age_days=10, push_success_rate=0.5))
        == Tier.IDLE
    )


def test_read_freq_zero_when_none_treated_as_zero_for_classification():
    assert (
        classify(_inputs(read_freq_7d=None, age_days=20, push_success_rate=None))
        == Tier.IDLE
    )
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_tier.py -v
```

Expected: FAIL `ModuleNotFoundError: tier`

- [ ] **Step 3: Implement `tier.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/tier.py`:

```python
"""Tier classifier for nb_monitor.

Decision rules from spec §5 / brainstorm question 3-D HYBRID:

    ALIVE: read_freq_7d >= 5 AND (psr is None OR psr >= 0.95) AND age_days > 7
    DYING: read_freq_7d < 1 AND age_days > 14 AND (psr is None OR psr < 0.7)
    IDLE:  everything else (including bootstrap NB age_days <= 7)

`psr is None` branches are NEUTRAL — missing data must not auto-downgrade.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    ALIVE = "ALIVE"
    IDLE = "IDLE"
    DYING = "DYING"


@dataclass(frozen=True)
class TierInputs:
    read_freq_7d: int | None
    push_success_rate: float | None
    age_days: int


def classify(inputs: TierInputs) -> Tier:
    rf7 = inputs.read_freq_7d or 0
    psr = inputs.push_success_rate
    age = inputs.age_days

    psr_alive_ok = psr is None or psr >= 0.95
    psr_dying_ok = psr is None or psr < 0.7

    if rf7 >= 5 and psr_alive_ok and age > 7:
        return Tier.ALIVE

    if rf7 < 1 and age > 14 and psr_dying_ok:
        return Tier.DYING

    return Tier.IDLE
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_tier.py -v
```

Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/tier.py \
        apps/mata-garuda/tests/nb_monitor/test_tier.py
git commit -m "feat(nb-monitor): tier classifier (ALIVE/IDLE/DYING)"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 11: Alerts engine — pure logic with cooldown + floor (TDD)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/alerts.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_alerts.py`

- [ ] **Step 1: Write failing tests**

Write to `apps/mata-garuda/tests/nb_monitor/test_alerts.py`:

```python
"""Tests for nb_monitor.alerts (pure logic, no I/O)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from mata_garuda.scripts.nb_monitor.alerts import (
    AlertCondition,
    AlertContext,
    AlertDecision,
    evaluate_alerts,
    can_send,
    COOLDOWNS,
)
from mata_garuda.scripts.nb_monitor.tier import Tier


def _ctx(**over) -> AlertContext:
    base = dict(
        uuid="u1",
        name="NB-X",
        tier_now=Tier.ALIVE,
        tier_lastweek=Tier.ALIVE,
        read_freq_7d_now=20,
        read_freq_7d_lastweek=50,
        age_days=30,
        skill_derivation_count=None,
        in_top5_alive_lastweek=True,
        consecutive_dying_days=0,
        rf7_30d_window_max=15,
    )
    base.update(over)
    return AlertContext(**base)


def test_top5_drop_alert_fires_when_drop_meets_pct_and_floor():
    decisions = evaluate_alerts(_ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT in conds


def test_top5_drop_alert_blocked_by_floor():
    """5→2 is 60% drop but absolute drop is 3 < floor 10 → no alert."""
    decisions = evaluate_alerts(_ctx(read_freq_7d_now=2, read_freq_7d_lastweek=5))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT not in conds


def test_top5_drop_alert_requires_top5_membership():
    decisions = evaluate_alerts(
        _ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50, in_top5_alive_lastweek=False)
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT not in conds


def test_top5_drop_alert_requires_alive_lastweek():
    decisions = evaluate_alerts(
        _ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50, tier_lastweek=Tier.IDLE)
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.TOP5_DROP_50PCT not in conds


def test_lifecycle_drop_alert_fires_on_alive_to_idle():
    decisions = evaluate_alerts(_ctx(tier_now=Tier.IDLE, tier_lastweek=Tier.ALIVE))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TIER_TRANSITION in conds


def test_lifecycle_drop_alert_skipped_in_bootstrap_window():
    decisions = evaluate_alerts(_ctx(tier_now=Tier.IDLE, tier_lastweek=Tier.ALIVE, age_days=10))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TIER_TRANSITION not in conds


def test_lifecycle_drop_alert_skipped_for_promotion():
    """IDLE→ALIVE is good news, not an alert."""
    decisions = evaluate_alerts(_ctx(tier_now=Tier.ALIVE, tier_lastweek=Tier.IDLE))
    conds = {d.condition for d in decisions}
    assert AlertCondition.TIER_TRANSITION not in conds


def test_dying_no_action_alert_requires_skill_derivation_zero():
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=14,
            skill_derivation_count=0,
            rf7_30d_window_max=0,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION in conds


def test_dying_no_action_alert_self_suppresses_when_skill_count_is_none():
    """Pre-FASE-1 default: skill_derivation_count is None → alert MUST NOT fire."""
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=14,
            skill_derivation_count=None,
            rf7_30d_window_max=0,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION not in conds


def test_dying_no_action_requires_consecutive_streak():
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=5,
            skill_derivation_count=0,
            rf7_30d_window_max=0,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION not in conds


def test_dying_no_action_blocked_when_recent_traffic():
    """If rf7 was non-zero anywhere in the 30d window, no alert."""
    decisions = evaluate_alerts(
        _ctx(
            tier_now=Tier.DYING,
            consecutive_dying_days=14,
            skill_derivation_count=0,
            rf7_30d_window_max=3,
        )
    )
    conds = {d.condition for d in decisions}
    assert AlertCondition.DYING_NO_ACTION not in conds


def test_can_send_returns_true_when_no_prior_send():
    assert can_send(uuid="u1", condition=AlertCondition.TOP5_DROP_50PCT, last_sent=None, now=10**9) is True


def test_can_send_returns_false_within_cooldown():
    last = 10**9
    now = last + 100  # well within 86400s cooldown
    assert can_send(uuid="u1", condition=AlertCondition.TOP5_DROP_50PCT, last_sent=last, now=now) is False


def test_can_send_returns_true_after_cooldown():
    last = 10**9
    now = last + COOLDOWNS[AlertCondition.TOP5_DROP_50PCT] + 1
    assert can_send(uuid="u1", condition=AlertCondition.TOP5_DROP_50PCT, last_sent=last, now=now) is True


def test_dying_cooldown_is_seven_days():
    assert COOLDOWNS[AlertCondition.DYING_NO_ACTION] == 7 * 86400


def test_alert_decision_includes_payload_with_facts():
    decisions = evaluate_alerts(_ctx(read_freq_7d_now=10, read_freq_7d_lastweek=50))
    top5 = next(d for d in decisions if d.condition == AlertCondition.TOP5_DROP_50PCT)
    assert "u1" in top5.payload
    assert "50" in top5.payload
    assert "10" in top5.payload
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_alerts.py -v
```

Expected: FAIL `ModuleNotFoundError: alerts`

- [ ] **Step 3: Implement `alerts.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/alerts.py`:

```python
"""Alert evaluator for nb_monitor (pure logic, no I/O).

Three independent alerts per spec §6:

    1. TOP5_DROP_50PCT  — top-5 ALIVE NB drop ≥50% AND ≥10 absolute
    2. TIER_TRANSITION  — tier degraded vs last week, age > 14d
    3. DYING_NO_ACTION  — DYING for ≥14d, skill_derivation_count==0, no traffic

Cooldowns:
    TOP5_DROP_50PCT, TIER_TRANSITION → 24h
    DYING_NO_ACTION                  → 7d
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from mata_garuda.scripts.nb_monitor.tier import Tier


class AlertCondition(str, Enum):
    TOP5_DROP_50PCT = "top5_drop_50pct"
    TIER_TRANSITION = "tier_transition"
    DYING_NO_ACTION = "dying_no_action"


COOLDOWNS: dict[AlertCondition, int] = {
    AlertCondition.TOP5_DROP_50PCT: 86400,
    AlertCondition.TIER_TRANSITION: 86400,
    AlertCondition.DYING_NO_ACTION: 7 * 86400,
}

TIER_RANK = {Tier.ALIVE: 2, Tier.IDLE: 1, Tier.DYING: 0}

DROP_PCT_THRESHOLD = 0.5
DROP_ABSOLUTE_FLOOR = 10
TIER_BOOTSTRAP_GUARD_DAYS = 14
DYING_STREAK_DAYS = 14


@dataclass(frozen=True)
class AlertContext:
    uuid: str
    name: str
    tier_now: Tier
    tier_lastweek: Tier | None
    read_freq_7d_now: int | None
    read_freq_7d_lastweek: int | None
    age_days: int
    skill_derivation_count: int | None
    in_top5_alive_lastweek: bool
    consecutive_dying_days: int
    rf7_30d_window_max: int


@dataclass(frozen=True)
class AlertDecision:
    condition: AlertCondition
    message: str
    payload: str  # JSON


def evaluate_alerts(ctx: AlertContext) -> list[AlertDecision]:
    out: list[AlertDecision] = []
    if _should_top5_drop(ctx):
        out.append(_top5_drop_decision(ctx))
    if _should_tier_transition(ctx):
        out.append(_tier_transition_decision(ctx))
    if _should_dying_no_action(ctx):
        out.append(_dying_no_action_decision(ctx))
    return out


def _should_top5_drop(ctx: AlertContext) -> bool:
    if ctx.tier_lastweek != Tier.ALIVE:
        return False
    if not ctx.in_top5_alive_lastweek:
        return False
    prev = ctx.read_freq_7d_lastweek or 0
    now = ctx.read_freq_7d_now or 0
    if prev <= 0:
        return False
    drop = prev - now
    if drop < DROP_ABSOLUTE_FLOOR:
        return False
    return now < (prev * DROP_PCT_THRESHOLD)


def _top5_drop_decision(ctx: AlertContext) -> AlertDecision:
    prev = ctx.read_freq_7d_lastweek or 0
    now = ctx.read_freq_7d_now or 0
    drop = prev - now
    pct = (drop / prev * 100) if prev else 0.0
    payload = json.dumps(
        {
            "uuid": ctx.uuid,
            "name": ctx.name,
            "prev": prev,
            "now": now,
            "drop": drop,
            "pct": round(pct, 1),
            "tier_lastweek": ctx.tier_lastweek.value if ctx.tier_lastweek else None,
            "tier_now": ctx.tier_now.value,
        }
    )
    msg = (
        f"NB drop alert: {ctx.name} read_freq_7d {prev} -> {now} "
        f"(-{drop} / -{round(pct, 1)}%); tier_lastweek={ctx.tier_lastweek.value if ctx.tier_lastweek else 'NA'} "
        f"tier_now={ctx.tier_now.value}"
    )
    return AlertDecision(condition=AlertCondition.TOP5_DROP_50PCT, message=msg, payload=payload)


def _should_tier_transition(ctx: AlertContext) -> bool:
    if ctx.age_days <= TIER_BOOTSTRAP_GUARD_DAYS:
        return False
    if ctx.tier_lastweek is None:
        return False
    return TIER_RANK[ctx.tier_now] < TIER_RANK[ctx.tier_lastweek]


def _tier_transition_decision(ctx: AlertContext) -> AlertDecision:
    payload = json.dumps(
        {
            "uuid": ctx.uuid,
            "name": ctx.name,
            "tier_lastweek": ctx.tier_lastweek.value if ctx.tier_lastweek else None,
            "tier_now": ctx.tier_now.value,
            "read_freq_7d_now": ctx.read_freq_7d_now,
            "read_freq_7d_lastweek": ctx.read_freq_7d_lastweek,
        }
    )
    msg = (
        f"NB tier transition: {ctx.name} {ctx.tier_lastweek.value if ctx.tier_lastweek else 'NA'} -> "
        f"{ctx.tier_now.value}; read_freq_7d {ctx.read_freq_7d_lastweek} -> {ctx.read_freq_7d_now}"
    )
    return AlertDecision(condition=AlertCondition.TIER_TRANSITION, message=msg, payload=payload)


def _should_dying_no_action(ctx: AlertContext) -> bool:
    if ctx.tier_now != Tier.DYING:
        return False
    if ctx.consecutive_dying_days < DYING_STREAK_DAYS:
        return False
    if ctx.skill_derivation_count is None or ctx.skill_derivation_count != 0:
        return False
    if ctx.rf7_30d_window_max > 0:
        return False
    return True


def _dying_no_action_decision(ctx: AlertContext) -> AlertDecision:
    payload = json.dumps(
        {
            "uuid": ctx.uuid,
            "name": ctx.name,
            "consecutive_dying_days": ctx.consecutive_dying_days,
            "skill_derivation_count": ctx.skill_derivation_count,
        }
    )
    msg = (
        f"NB dying-no-action: {ctx.name} DYING for {ctx.consecutive_dying_days}d, "
        f"skill_derivation_count=0, no recent traffic. Propose APOPTOSIS (Zero approval)."
    )
    return AlertDecision(condition=AlertCondition.DYING_NO_ACTION, message=msg, payload=payload)


def can_send(uuid: str, condition: AlertCondition, last_sent: int | None, now: int) -> bool:
    if last_sent is None:
        return True
    return (now - last_sent) >= COOLDOWNS[condition]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_alerts.py -v
```

Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/alerts.py \
        apps/mata-garuda/tests/nb_monitor/test_alerts.py
git commit -m "feat(nb-monitor): alert evaluator with floor + cooldown + 3 conditions"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 12: Telegram dispatcher (small, with mock-able transport)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/telegram_send.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_telegram_send.py`

- [ ] **Step 1: Write failing tests**

Write to `apps/mata-garuda/tests/nb_monitor/test_telegram_send.py`:

```python
"""Tests for nb_monitor.telegram_send."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mata_garuda.scripts.nb_monitor.telegram_send import send_telegram


def test_send_telegram_returns_true_on_success():
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b'{"ok": true}'
    with patch("urllib.request.urlopen", return_value=_ctx_mgr(fake_resp)):
        ok = send_telegram(bot_token="t", chat_id="123", text="hi")
    assert ok is True


def test_send_telegram_returns_false_on_non_2xx():
    fake_resp = MagicMock()
    fake_resp.status = 401
    fake_resp.read.return_value = b'{"ok": false}'
    with patch("urllib.request.urlopen", return_value=_ctx_mgr(fake_resp)):
        ok = send_telegram(bot_token="t", chat_id="123", text="hi")
    assert ok is False


def test_send_telegram_returns_false_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        ok = send_telegram(bot_token="t", chat_id="123", text="hi")
    assert ok is False


def test_send_telegram_skips_when_bot_token_empty():
    """Empty token → don't even attempt the call. Returns False, no exception."""
    with patch("urllib.request.urlopen") as mocked:
        ok = send_telegram(bot_token="", chat_id="123", text="hi")
    assert ok is False
    mocked.assert_not_called()


def _ctx_mgr(resp):
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_telegram_send.py -v
```

Expected: FAIL `ModuleNotFoundError: telegram_send`

- [ ] **Step 3: Implement `telegram_send.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/telegram_send.py`:

```python
"""Tiny Telegram sender with no external deps.

Uses urllib stdlib. Returns bool (success). Never raises — caller decides
how to handle a failed send (see spec §7.2).
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 5


def send_telegram(
    bot_token: str,
    chat_id: str,
    text: str,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> bool:
    """POST to Telegram bot API. Returns True on 2xx response, False otherwise."""
    if not bot_token or not chat_id:
        logger.warning("telegram_send: empty bot_token or chat_id, skipping")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            if 200 <= status < 300:
                return True
            logger.warning("telegram_send: non-2xx status %s", status)
            return False
    except Exception as e:
        logger.warning("telegram_send: %s", e)
        return False
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_telegram_send.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/telegram_send.py \
        apps/mata-garuda/tests/nb_monitor/test_telegram_send.py
git commit -m "feat(nb-monitor): minimal Telegram sender (urllib stdlib)"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 13: Weekly report markdown generator (TDD)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/report.py`
- Test: `apps/mata-garuda/tests/nb_monitor/test_report.py`

- [ ] **Step 1: Write failing tests**

Write to `apps/mata-garuda/tests/nb_monitor/test_report.py`:

```python
"""Tests for nb_monitor.report."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from mata_garuda.scripts.nb_monitor.report import (
    ReportEntry,
    render_weekly_report,
    iso_year_week,
)
from mata_garuda.scripts.nb_monitor.tier import Tier


def _entry(**over) -> ReportEntry:
    base = dict(
        rank=1,
        uuid="1ed02e54-542f-426a-94f8-53c5ffde4b7d",
        name="NB-INTEL-Immigration",
        tier=Tier.ALIVE,
        read_freq_7d=120,
        read_freq_30d=480,
        delta_7d_vs_lastweek=10,
        age_days=30,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=15,
        push_success_rate=0.99,
        instrumentation_status="ok",
    )
    base.update(over)
    return ReportEntry(**base)


def test_iso_year_week_format():
    assert iso_year_week(datetime(2026, 5, 7, tzinfo=timezone.utc)) == "2026-W19"


def test_render_weekly_report_includes_header():
    md = render_weekly_report(
        [_entry()],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "# NB Mitochondrial Value Monitor — 2026-W19" in md
    assert "Baseline period" in md  # banner present


def test_render_weekly_report_includes_ranking_table():
    md = render_weekly_report(
        [_entry(), _entry(rank=2, uuid="x", name="NB-2", read_freq_7d=80)],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "| rank |" in md
    assert "NB-INTEL-Immigration" in md
    assert "NB-2" in md
    assert "120" in md
    assert "80" in md


def test_render_weekly_report_includes_diagnostic_block():
    md = render_weekly_report(
        [_entry()],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    # Diagnostic block uses HTML <details> for collapsibility.
    assert "<details>" in md
    assert "Diagnostic columns" in md
    assert "skill_derivation_count" in md
    assert "downstream_cite_rate" in md


def test_render_weekly_report_omits_baseline_after_window():
    md = render_weekly_report(
        [_entry()],
        generated_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
        baseline_window=False,
    )
    assert "Baseline period" not in md


def test_render_weekly_report_renders_na_for_none_metrics():
    md = render_weekly_report(
        [_entry(skill_derivation_count=None, downstream_cite_rate=None, source_freshness_age_days=None)],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "N/A" in md


def test_render_weekly_report_handles_empty_entries():
    md = render_weekly_report(
        [],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "no entries" in md.lower() or "0 NB" in md
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_report.py -v
```

Expected: FAIL `ModuleNotFoundError: report`

- [ ] **Step 3: Implement `report.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/report.py`:

```python
"""Weekly markdown report generator for nb_monitor.

Output path: ~/Desktop/nuzantara/research/nb-monitor/report-YYYY-Www.md
Renderer is pure — takes entries + timestamp, returns markdown string. The
caller writes to disk.

Spec §7.3 (banner content), §6 (alert format reference for footer link).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import StringIO

from mata_garuda.scripts.nb_monitor.tier import Tier


@dataclass(frozen=True)
class ReportEntry:
    rank: int
    uuid: str
    name: str
    tier: Tier
    read_freq_7d: int | None
    read_freq_30d: int | None
    delta_7d_vs_lastweek: int | None
    age_days: int
    skill_derivation_count: int | None
    downstream_cite_rate: float | None
    source_freshness_age_days: int | None
    push_success_rate: float | None
    instrumentation_status: str


BASELINE_BANNER = """\
> **Baseline period — first 14 days post-deploy. Score reliability degraded:**
> - `read_freq_7d/30d`: live (Claude Code JSONL scraper).
> - `source_freshness_age`: best-effort (nlm cookie 5min TTL).
> - `push_success_rate`: live (matagaruda-nlm-feeder-stream.log; **GLOBAL** — same value applied per active_routing UUID).
> - `skill_derivation_count`: **N/A pending FASE 1 merge**.
> - `downstream_cite_rate`: **N/A pending FASE 4 merge**.
"""


def iso_year_week(dt: datetime) -> str:
    iy, iw, _ = dt.isocalendar()
    return f"{iy}-W{iw:02d}"


def render_weekly_report(
    entries: list[ReportEntry],
    generated_at: datetime,
    baseline_window: bool,
) -> str:
    week = iso_year_week(generated_at)
    out = StringIO()
    out.write(f"# NB Mitochondrial Value Monitor — {week}\n\n")
    out.write(f"_Generated at {generated_at.isoformat()}_\n\n")
    if baseline_window:
        out.write(BASELINE_BANNER)
        out.write("\n")

    if not entries:
        out.write("_No entries (0 NB recorded). Check cron + bootstrap registry._\n")
        return out.getvalue()

    out.write("## Ranking\n\n")
    out.write("| rank | name | tier | rf7 | rf30 | Δ vs lastweek | age (d) |\n")
    out.write("|---:|---|:---:|---:|---:|---:|---:|\n")
    for e in entries:
        out.write(
            f"| {e.rank} | `{e.name}` | {e.tier.value} | "
            f"{_fmt_int(e.read_freq_7d)} | {_fmt_int(e.read_freq_30d)} | "
            f"{_fmt_delta(e.delta_7d_vs_lastweek)} | {e.age_days} |\n"
        )

    out.write("\n<details>\n")
    out.write("<summary>Diagnostic columns (skill_derivation_count, downstream_cite_rate, freshness, push_success, instrumentation_status)</summary>\n\n")
    out.write("| name | skill_derivation_count | downstream_cite_rate | source_freshness_age_days | push_success_rate | instrumentation_status |\n")
    out.write("|---|---:|---:|---:|---:|:---|\n")
    for e in entries:
        out.write(
            f"| `{e.name}` | {_fmt_int(e.skill_derivation_count)} | "
            f"{_fmt_rate(e.downstream_cite_rate)} | {_fmt_int(e.source_freshness_age_days)} | "
            f"{_fmt_rate(e.push_success_rate)} | {e.instrumentation_status} |\n"
        )
    out.write("\n</details>\n")
    return out.getvalue()


def _fmt_int(v: int | None) -> str:
    return "N/A" if v is None else str(v)


def _fmt_rate(v: float | None) -> str:
    return "N/A" if v is None else f"{v:.2f}"


def _fmt_delta(v: int | None) -> str:
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v}"
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_report.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/report.py \
        apps/mata-garuda/tests/nb_monitor/test_report.py
git commit -m "feat(nb-monitor): weekly markdown report renderer"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 14: Run loop (`run.py`) — orchestrates one execution

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py`

**Note:** `run.py` is the heart that wires everything together. It is NOT directly unit-tested — the integration test in Task 15 is the e2e validation. We do dependency injection on the I/O bits (collectors + telegram + paths) so the integration test can substitute test doubles.

- [ ] **Step 1: Write `run.py`**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py`:

```python
"""Entrypoint for nb_monitor daily run.

Usage:
    python -m mata_garuda.scripts.nb_monitor.run         # full daily run
    python -m mata_garuda.scripts.nb_monitor.run --once  # alias, ad-hoc

Wires registry → collectors → tier classifier → SQLite snapshot →
alert evaluator → optional Telegram dispatch → optional weekly report.

Spec §3.3 data flow. All paths and external commands are injectable for
the integration test in tests/nb_monitor/test_integration_e2e.py.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from mata_garuda.scripts.nb_monitor import (
    BOOTSTRAP_FILE,
    DATA_DIR,
    METRICS_DB,
)
from mata_garuda.scripts.nb_monitor.alerts import (
    AlertCondition,
    AlertContext,
    AlertDecision,
    can_send,
    evaluate_alerts,
)
from mata_garuda.scripts.nb_monitor.collectors import (
    cite_rate,
    feeder_log,
    log_scraper,
    nlm_freshness,
    skill_derivation,
)
from mata_garuda.scripts.nb_monitor.persist import (
    AlertRecord,
    MetricRow,
    connect,
    ensure_schema,
    fetch_alert_last_sent,
    fetch_latest_per_uuid,
    insert_alert_record,
    insert_metric_row,
)
from mata_garuda.scripts.nb_monitor.registry import (
    NotebookEntry,
    RegistryLoadError,
    load_registry,
)
from mata_garuda.scripts.nb_monitor.report import (
    ReportEntry,
    render_weekly_report,
)
from mata_garuda.scripts.nb_monitor.telegram_send import send_telegram
from mata_garuda.scripts.nb_monitor.tier import Tier, TierInputs, classify

logger = logging.getLogger(__name__)

WINDOW_7D = 7 * 86400
WINDOW_30D = 30 * 86400


@dataclass
class RunConfig:
    bootstrap_path: Path = BOOTSTRAP_FILE
    db_path: Path = METRICS_DB
    feeder_log_path: Path = Path.home() / "logs" / "matagaruda-nlm-feeder-stream.log"
    report_dir: Path = Path.home() / "Desktop" / "nuzantara" / "research" / "nb-monitor"
    deploy_date: datetime = datetime(2026, 5, 7, tzinfo=timezone.utc)
    telegram_bot_token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "1125336968")
    # Test doubles. Production defaults call the real functions.
    collect_read_freq_7d: Callable[[str], int | None] | None = None
    collect_read_freq_30d: Callable[[str], int | None] | None = None
    collect_freshness: Callable[[str], int | None] | None = None
    collect_push_success: Callable[[], float | None] | None = None
    telegram_send: Callable[[str, str, str], bool] = send_telegram


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nb_monitor.run")
    parser.add_argument("--once", action="store_true", help="alias; the run is always one-shot")
    parser.add_argument("--no-telegram", action="store_true", help="suppress Telegram dispatch")
    parser.add_argument("--report", action="store_true", help="force-generate weekly report regardless of weekday")
    args = parser.parse_args(argv)

    _configure_logging()
    cfg = RunConfig()
    if args.no_telegram:
        cfg.telegram_send = lambda *_args, **_kwargs: False  # type: ignore[assignment]

    return execute_once(cfg, force_report=args.report)


def execute_once(cfg: RunConfig, force_report: bool = False, now: float | None = None) -> int:
    now = now if now is not None else time.time()
    ts_capture = int(now)
    logger.info("nb_monitor: starting run ts_capture=%d", ts_capture)

    try:
        entries = load_registry(cfg.bootstrap_path)
    except RegistryLoadError as e:
        logger.error("nb_monitor: cannot load registry: %s", e)
        return 0  # exit 0 — see spec §7.2 graceful-degrade

    if len(entries) < 24:
        logger.warning(
            "nb_monitor: only %d notebooks in registry (expected up to 24 per FASE 2)",
            len(entries),
        )

    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.db_path)
    try:
        ensure_schema(conn)
        rows = _collect_all(entries, cfg, ts_capture)
        report_entries: list[ReportEntry] = []

        for entry, row, prev in rows:
            insert_metric_row(conn, row)
            decisions = _build_alert_decisions(entry, row, prev, conn, ts_capture, cfg)
            for d in decisions:
                _dispatch_alert(d, entry.uuid, conn, ts_capture, cfg)

        # Build report entries — ranking by tier then rf7d desc.
        report_entries = _build_report_entries(rows)

        # Write report on Sunday OR when forced.
        if force_report or _is_sunday(ts_capture):
            _write_report(cfg, report_entries, ts_capture)

        logger.info("nb_monitor: completed run, processed=%d", len(rows))
    except Exception as e:  # noqa: BLE001 (graceful-degrade per spec §7.2)
        logger.exception("nb_monitor: unhandled exception: %s", e)
    finally:
        conn.close()

    return 0


def _configure_logging() -> None:
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / "nb-monitor.log")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
    )
    root = logging.getLogger()
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stderr))
    root.setLevel(logging.INFO)


def _collect_all(
    entries: list[NotebookEntry],
    cfg: RunConfig,
    ts_capture: int,
) -> list[tuple[NotebookEntry, MetricRow, MetricRow | None]]:
    # JSONL files used for read_freq are discovered ONCE per run (cheaper than per-NB).
    files = log_scraper.discover_session_files(cutoff_mtime=ts_capture - WINDOW_30D)
    rf_7d_counts = log_scraper.count_nlm_events_by_uuid(files, window_seconds=WINDOW_7D, now=ts_capture)
    rf_30d_counts = log_scraper.count_nlm_events_by_uuid(files, window_seconds=WINDOW_30D, now=ts_capture)

    if cfg.collect_push_success is not None:
        global_psr = cfg.collect_push_success()
    else:
        global_psr = feeder_log.compute_global_push_success_rate(
            cfg.feeder_log_path, window_seconds=WINDOW_7D, now=ts_capture
        )

    out: list[tuple[NotebookEntry, MetricRow, MetricRow | None]] = []
    conn = connect(cfg.db_path)
    try:
        for entry in entries:
            try:
                rf7 = (
                    cfg.collect_read_freq_7d(entry.uuid)
                    if cfg.collect_read_freq_7d is not None
                    else rf_7d_counts.get(entry.uuid, 0)
                )
                rf30 = (
                    cfg.collect_read_freq_30d(entry.uuid)
                    if cfg.collect_read_freq_30d is not None
                    else rf_30d_counts.get(entry.uuid, 0)
                )
                fresh = (
                    cfg.collect_freshness(entry.uuid)
                    if cfg.collect_freshness is not None
                    else nlm_freshness.fetch_source_freshness_age_days(entry.uuid)
                )
                psr = global_psr if entry.active_routing else None
                skill = skill_derivation.count_skills_for_uuid(entry.uuid)
                cite = cite_rate.compute_rate_for_uuid(entry.uuid)

                age = _age_days(entry.first_audited, ts_capture)
                tier = classify(
                    TierInputs(read_freq_7d=rf7, push_success_rate=psr, age_days=age)
                )
                row = MetricRow(
                    uuid=entry.uuid,
                    ts_capture=ts_capture,
                    tier=tier.value,
                    read_freq_7d=rf7,
                    read_freq_30d=rf30,
                    skill_derivation_count=skill,
                    downstream_cite_rate=cite,
                    source_freshness_age_days=fresh,
                    push_success_rate=psr,
                    instrumentation_status=_status(rf7, fresh, psr),
                )
                prev = fetch_latest_per_uuid(conn, entry.uuid)
                out.append((entry, row, prev))
            except Exception as e:  # noqa: BLE001
                logger.warning("nb_monitor: collector failure for %s: %s", entry.name, e)
    finally:
        conn.close()
    return out


def _build_alert_decisions(
    entry: NotebookEntry,
    row: MetricRow,
    prev: MetricRow | None,
    conn: sqlite3.Connection,
    ts_capture: int,
    cfg: RunConfig,
) -> list[AlertDecision]:
    age = _age_days(entry.first_audited, ts_capture)
    tier_now = Tier(row.tier)
    tier_lastweek = Tier(prev.tier) if prev else None

    # Compute consecutive_dying_days and rf7_30d_window_max from history.
    consecutive_dying = _consecutive_dying_days(conn, entry.uuid, ts_capture)
    rf7_max_30d = _rf7_30d_window_max(conn, entry.uuid, ts_capture)

    in_top5 = _was_in_top5_alive_lastweek(conn, entry.uuid, ts_capture)

    ctx = AlertContext(
        uuid=entry.uuid,
        name=entry.name,
        tier_now=tier_now,
        tier_lastweek=tier_lastweek,
        read_freq_7d_now=row.read_freq_7d,
        read_freq_7d_lastweek=prev.read_freq_7d if prev else None,
        age_days=age,
        skill_derivation_count=row.skill_derivation_count,
        in_top5_alive_lastweek=in_top5,
        consecutive_dying_days=consecutive_dying,
        rf7_30d_window_max=rf7_max_30d,
    )
    return evaluate_alerts(ctx)


def _dispatch_alert(
    decision: AlertDecision,
    uuid: str,
    conn: sqlite3.Connection,
    ts_capture: int,
    cfg: RunConfig,
) -> None:
    last_sent = fetch_alert_last_sent(conn, uuid, decision.condition.value)
    if not can_send(uuid, decision.condition, last_sent, ts_capture):
        logger.info("nb_monitor: alert suppressed by cooldown: %s %s", uuid, decision.condition.value)
        return
    ok = cfg.telegram_send(cfg.telegram_bot_token, cfg.telegram_chat_id, decision.message)
    if not ok:
        logger.warning("nb_monitor: Telegram send failed; alert NOT recorded")
        return
    insert_alert_record(
        conn,
        AlertRecord(
            uuid=uuid,
            condition=decision.condition.value,
            sent_at=ts_capture,
            payload=decision.payload,
        ),
    )


def _build_report_entries(
    rows: list[tuple[NotebookEntry, MetricRow, MetricRow | None]],
) -> list[ReportEntry]:
    # Rank by tier (ALIVE > IDLE > DYING) then rf7 desc, ties broken by rf30 desc.
    tier_order = {"ALIVE": 0, "IDLE": 1, "DYING": 2}
    sorted_rows = sorted(
        rows,
        key=lambda t: (
            tier_order[t[1].tier],
            -(t[1].read_freq_7d or 0),
            -(t[1].read_freq_30d or 0),
        ),
    )
    out: list[ReportEntry] = []
    for rank, (entry, row, prev) in enumerate(sorted_rows, start=1):
        delta = (
            (row.read_freq_7d - prev.read_freq_7d)
            if (prev and row.read_freq_7d is not None and prev.read_freq_7d is not None)
            else None
        )
        out.append(
            ReportEntry(
                rank=rank,
                uuid=entry.uuid,
                name=entry.name,
                tier=Tier(row.tier),
                read_freq_7d=row.read_freq_7d,
                read_freq_30d=row.read_freq_30d,
                delta_7d_vs_lastweek=delta,
                age_days=_age_days(entry.first_audited, row.ts_capture),
                skill_derivation_count=row.skill_derivation_count,
                downstream_cite_rate=row.downstream_cite_rate,
                source_freshness_age_days=row.source_freshness_age_days,
                push_success_rate=row.push_success_rate,
                instrumentation_status=row.instrumentation_status,
            )
        )
    return out


def _write_report(cfg: RunConfig, entries: list[ReportEntry], ts_capture: int) -> None:
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.fromtimestamp(ts_capture, tz=timezone.utc)
    iy, iw, _ = now.isocalendar()
    path = cfg.report_dir / f"report-{iy}-W{iw:02d}.md"
    baseline = (now - cfg.deploy_date).days < 14
    content = render_weekly_report(entries, generated_at=now, baseline_window=baseline)
    path.write_text(content)
    logger.info("nb_monitor: weekly report written to %s", path)


def _age_days(first_audited: str, ts_capture: int) -> int:
    try:
        d = datetime.fromisoformat(first_audited).replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    now = datetime.fromtimestamp(ts_capture, tz=timezone.utc)
    return max(0, (now - d).days)


def _is_sunday(ts_capture: int) -> bool:
    return datetime.fromtimestamp(ts_capture, tz=timezone.utc).weekday() == 6


def _consecutive_dying_days(conn: sqlite3.Connection, uuid: str, ts_capture: int) -> int:
    """Count consecutive most-recent rows where tier='DYING'."""
    cursor = conn.execute(
        "SELECT tier FROM nb_metrics WHERE uuid=? ORDER BY ts_capture DESC LIMIT 30",
        (uuid,),
    )
    streak = 0
    for (tier,) in cursor.fetchall():
        if tier == "DYING":
            streak += 1
        else:
            break
    return streak


def _rf7_30d_window_max(conn: sqlite3.Connection, uuid: str, ts_capture: int) -> int:
    """Max of read_freq_7d in last 30 days (used to decide if traffic is truly absent)."""
    cutoff = ts_capture - WINDOW_30D
    r = conn.execute(
        "SELECT MAX(read_freq_7d) FROM nb_metrics WHERE uuid=? AND ts_capture >= ?",
        (uuid, cutoff),
    ).fetchone()
    return int(r[0]) if r and r[0] is not None else 0


def _was_in_top5_alive_lastweek(conn: sqlite3.Connection, uuid: str, ts_capture: int) -> bool:
    """True if the UUID was in the top-5 by read_freq_7d among ALIVE NB ~7 days ago."""
    target = ts_capture - 7 * 86400
    target_low = target - 86400
    target_high = target + 86400
    rows = conn.execute(
        """
        SELECT uuid FROM nb_metrics
         WHERE tier='ALIVE'
           AND ts_capture BETWEEN ? AND ?
         ORDER BY read_freq_7d DESC
         LIMIT 5
        """,
        (target_low, target_high),
    ).fetchall()
    top5 = {r[0] for r in rows}
    return uuid in top5


def _status(
    rf7: int | None, freshness: int | None, psr: float | None
) -> str:
    """Compose instrumentation_status from collector outcomes."""
    if rf7 is None:
        return "parse_failure"
    parts = []
    if freshness is None:
        parts.append("cookie_refresh_pending")
    parts.append("pending_qdrant_local_post_fase1")
    parts.append("pending_oracle_logging_post_fase4")
    return "ok" if not parts[:1] else ";".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify it imports without error**

```bash
cd apps/mata-garuda && .venv/bin/python -c "from mata_garuda.scripts.nb_monitor.run import execute_once, RunConfig; print('imports ok')"
```

Expected: `imports ok`

- [ ] **Step 3: Verify --help works**

```bash
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --help 2>&1 | head -10
```

Expected: argparse usage line printed.

- [ ] **Step 4: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py
git commit -m "feat(nb-monitor): orchestrator run.py wiring registry+collectors+alerts+report"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 15: Integration test (TDD — end-to-end with mocked Telegram)

**Files:**

- Create: `apps/mata-garuda/tests/nb_monitor/test_integration_e2e.py`
- Create: `apps/mata-garuda/tests/nb_monitor/conftest.py`

- [ ] **Step 1: Write conftest with shared fixtures**

Write to `apps/mata-garuda/tests/nb_monitor/conftest.py`:

```python
"""Shared fixtures for nb_monitor tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def make_jsonl(tmp_path):
    """Return a factory that creates a JSONL session file with given UUID counts."""

    def _make(file_name: str, uuid_counts: dict[str, int]) -> Path:
        f = tmp_path / file_name
        lines = []
        for uuid, n in uuid_counts.items():
            for _ in range(n):
                lines.append(
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [
                                    {
                                        "type": "tool_use",
                                        "name": "mcp__notebooklm-mcp__notebook_query",
                                        "input": {"notebook_id": uuid},
                                    }
                                ]
                            },
                        }
                    )
                )
        f.write_text("\n".join(lines) + "\n")
        return f

    return _make


@pytest.fixture
def fake_bootstrap(tmp_path):
    bp = tmp_path / "bootstrap.json"
    bp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-07",
                "source": "test",
                "notebooks": [
                    {
                        "uuid": "uuid-A",
                        "name": "NB-A",
                        "family": "INTEL",
                        "lifecycle_stage": "TAC",
                        "active_routing": True,
                        "first_audited": "2026-04-01",
                        "round2_classification": "Test",
                    },
                    {
                        "uuid": "uuid-B",
                        "name": "NB-B",
                        "family": "INTEL",
                        "lifecycle_stage": "TAC",
                        "active_routing": True,
                        "first_audited": "2026-04-01",
                        "round2_classification": "Test",
                    },
                    {
                        "uuid": "uuid-C",
                        "name": "NB-C",
                        "family": "RESEARCH",
                        "lifecycle_stage": "DM",
                        "active_routing": False,
                        "first_audited": "2026-05-01",
                        "round2_classification": "Test",
                    },
                ],
            }
        )
    )
    return bp
```

- [ ] **Step 2: Write the integration test**

Write to `apps/mata-garuda/tests/nb_monitor/test_integration_e2e.py`:

```python
"""End-to-end integration test for nb_monitor.

Runs execute_once with all I/O substituted: registry from tmpdir, collectors
faked via RunConfig injection, Telegram dispatch counted via a stub. Asserts
that metrics.db has the right shape and that alerts logic runs.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.run import RunConfig, execute_once


def _cfg(tmp_path, fake_bootstrap, **over):
    sent: list[tuple[str, str, str]] = []

    def stub_send(token, chat, text):
        sent.append((token, chat, text))
        return True

    cfg = RunConfig(
        bootstrap_path=fake_bootstrap,
        db_path=tmp_path / "metrics.db",
        feeder_log_path=tmp_path / "missing_feeder.log",  # missing → None
        report_dir=tmp_path / "report",
        deploy_date=datetime(2026, 5, 7, tzinfo=timezone.utc),
        telegram_bot_token="fake",
        telegram_chat_id="0",
        telegram_send=stub_send,
    )
    cfg.collect_read_freq_7d = lambda u: {"uuid-A": 100, "uuid-B": 3, "uuid-C": 0}.get(u, 0)
    cfg.collect_read_freq_30d = lambda u: {"uuid-A": 400, "uuid-B": 12, "uuid-C": 0}.get(u, 0)
    cfg.collect_freshness = lambda u: 5
    cfg.collect_push_success = lambda: 0.99
    cfg.__dict__.update(over)
    return cfg, sent


def _now(date_str: str) -> int:
    return int(datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc).timestamp())


def test_first_run_persists_three_rows(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    rc = execute_once(cfg, now=_now("2026-05-15"))
    assert rc == 0

    conn = sqlite3.connect(cfg.db_path)
    rows = conn.execute(
        "SELECT uuid, tier, read_freq_7d, instrumentation_status FROM nb_metrics ORDER BY uuid"
    ).fetchall()
    conn.close()
    assert {r[0] for r in rows} == {"uuid-A", "uuid-B", "uuid-C"}
    by_uuid = {r[0]: r for r in rows}
    assert by_uuid["uuid-A"][1] == "ALIVE"
    assert by_uuid["uuid-B"][1] == "IDLE"
    assert by_uuid["uuid-C"][1] == "IDLE"  # age 14 days, age_days <= 7? No — 14d > 7 but rf7=0 also <1. Stays IDLE per tier rules.


def test_first_run_does_not_alert_without_history(tmp_path, fake_bootstrap):
    cfg, sent = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"))
    # No prior week's snapshot → tier_lastweek=None → tier_transition cannot fire.
    # No top5_alive_lastweek population yet → top5 cannot fire.
    # skill_derivation=None → dying_no_action self-suppressed.
    assert sent == []


def test_second_run_after_drop_emits_top5_drop_alert(tmp_path, fake_bootstrap):
    cfg, sent = _cfg(tmp_path, fake_bootstrap)
    # Day 1 — uuid-A is ALIVE with rf7=100 (top-1 of one ALIVE).
    execute_once(cfg, now=_now("2026-05-15"))
    sent.clear()

    # Mutate collector to drop uuid-A from 100 → 5.
    cfg.collect_read_freq_7d = lambda u: {"uuid-A": 5, "uuid-B": 3, "uuid-C": 0}.get(u, 0)
    execute_once(cfg, now=_now("2026-05-22"))  # 7 days later

    # Cooldown is 24h, lastweek window matches. Alert should fire.
    msgs = [m[2] for m in sent]
    assert any("NB-A" in m and "drop" in m.lower() for m in msgs)


def test_alert_cooldown_suppresses_duplicate_within_window(tmp_path, fake_bootstrap):
    cfg, sent = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"))
    sent.clear()
    cfg.collect_read_freq_7d = lambda u: {"uuid-A": 5, "uuid-B": 3, "uuid-C": 0}.get(u, 0)
    execute_once(cfg, now=_now("2026-05-22"))
    n_first = len(sent)
    # Second call same day → cooldown should suppress.
    execute_once(cfg, now=_now("2026-05-22"))
    assert len(sent) == n_first


def test_report_written_on_sunday(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    # 2026-05-17 is a Sunday.
    execute_once(cfg, now=_now("2026-05-17"))
    report_files = list((tmp_path / "report").glob("report-*.md"))
    assert len(report_files) == 1
    content = report_files[0].read_text()
    assert "NB-A" in content


def test_report_force_flag_writes_on_any_weekday(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    # 2026-05-15 is a Friday.
    execute_once(cfg, now=_now("2026-05-15"), force_report=True)
    report_files = list((tmp_path / "report").glob("report-*.md"))
    assert len(report_files) == 1


def test_active_routing_false_gets_null_psr(tmp_path, fake_bootstrap):
    cfg, _ = _cfg(tmp_path, fake_bootstrap)
    execute_once(cfg, now=_now("2026-05-15"))
    conn = sqlite3.connect(cfg.db_path)
    psr_C = conn.execute(
        "SELECT push_success_rate FROM nb_metrics WHERE uuid='uuid-C'"
    ).fetchone()[0]
    conn.close()
    # uuid-C has active_routing=false → psr should be NULL.
    assert psr_C is None


def test_run_exits_zero_on_missing_registry(tmp_path):
    cfg = RunConfig(
        bootstrap_path=tmp_path / "absent.json",
        db_path=tmp_path / "m.db",
        feeder_log_path=tmp_path / "missing.log",
        report_dir=tmp_path / "report",
    )
    assert execute_once(cfg, now=_now("2026-05-15")) == 0
```

- [ ] **Step 3: Run integration tests**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/test_integration_e2e.py -v
```

Expected: 8 passed. If failing — read the assertion message, check `run.py`. Iterate until green.

- [ ] **Step 4: Run full test suite**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/ -v
```

Expected: all tests pass (sum of all individual files: 5 + 11 + 7 + 7 + 6 + 9 + 14 + 4 + 7 + 8 ≈ 78).

- [ ] **Step 5: Coverage check**

```bash
cd apps/mata-garuda && .venv/bin/pip install --quiet coverage 2>&1 | tail -2
cd apps/mata-garuda && .venv/bin/coverage run --source=mata_garuda/scripts/nb_monitor -m pytest tests/nb_monitor/ -q
cd apps/mata-garuda && .venv/bin/coverage report -m | tail -25
```

Expected: total ≥80%. If below, identify uncovered lines via `coverage report -m` and add a focused test.

- [ ] **Step 6: Commit**

```bash
git add apps/mata-garuda/tests/nb_monitor/conftest.py \
        apps/mata-garuda/tests/nb_monitor/test_integration_e2e.py
git commit -m "feat(nb-monitor): integration e2e test with full collector injection"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 16: CLI dashboard `show.py`

**Files:**

- Create: `scripts/nb-monitor/show.py`

**Note:** This is a tiny user-facing CLI that prints latest snapshot from `metrics.db`. Not heavily tested — manual smoke is sufficient for a read-only display tool.

- [ ] **Step 1: Create script directory**

```bash
mkdir -p scripts/nb-monitor
```

- [ ] **Step 2: Write `show.py`**

Write to `scripts/nb-monitor/show.py`:

```python
#!/usr/bin/env python3
"""CLI dashboard for nb_monitor.

Reads ~/.agent/nb-mitochondrial/metrics.db and prints a table with the
latest snapshot per UUID, plus delta vs the row from ~7 days ago.

Usage:
    python scripts/nb-monitor/show.py
    python scripts/nb-monitor/show.py --db /path/to/metrics.db
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".agent" / "nb-mitochondrial" / "metrics.db"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nb-monitor-show")
    p.add_argument("--db", default=str(DEFAULT_DB))
    args = p.parse_args(argv)

    db = Path(args.db)
    if not db.exists():
        print(f"metrics.db not found at {db} — has the cron run yet?")
        return 1

    conn = sqlite3.connect(db)
    try:
        latest = conn.execute(
            """
            SELECT uuid, MAX(ts_capture) AS ts, tier, read_freq_7d, read_freq_30d,
                   push_success_rate, source_freshness_age_days, instrumentation_status
              FROM nb_metrics
             GROUP BY uuid
             ORDER BY tier ASC, read_freq_7d DESC
            """
        ).fetchall()

        if not latest:
            print("(no rows yet)")
            return 0

        header = f"{'UUID-PREFIX':12} {'TIER':6} {'rf7':>5} {'rf30':>6} {'Δ':>5} {'psr':>5} {'fresh_d':>7}  STATUS"
        print(header)
        print("-" * len(header))
        for uuid, ts, tier, rf7, rf30, psr, fresh, status in latest:
            prev_rf7 = conn.execute(
                """
                SELECT read_freq_7d FROM nb_metrics
                 WHERE uuid=? AND ts_capture <= ?
                 ORDER BY ts_capture DESC LIMIT 1 OFFSET 1
                """,
                (uuid, ts),
            ).fetchone()
            delta = (
                (rf7 - prev_rf7[0])
                if (prev_rf7 and rf7 is not None and prev_rf7[0] is not None)
                else None
            )
            print(
                f"{uuid[:12]:12} {tier:6} "
                f"{_fmt(rf7, 5)} {_fmt(rf30, 6)} {_fmt(delta, 5)} "
                f"{_fmt_rate(psr, 5)} {_fmt(fresh, 7)}  {status or ''}"
            )
    finally:
        conn.close()
    return 0


def _fmt(v, width: int) -> str:
    return f"{v:>{width}d}" if v is not None else f"{'N/A':>{width}}"


def _fmt_rate(v, width: int) -> str:
    return f"{v:>{width}.2f}" if v is not None else f"{'N/A':>{width}}"


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Make executable**

```bash
chmod +x scripts/nb-monitor/show.py
```

- [ ] **Step 4: Verify --help works**

```bash
python scripts/nb-monitor/show.py --help 2>&1 | head -5
```

Expected: argparse usage line.

- [ ] **Step 5: Commit**

```bash
git add scripts/nb-monitor/show.py
git commit -m "feat(nb-monitor): CLI dashboard show.py reading metrics.db"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

## COMMIT BLOCK 4 — Documentation + ADR + smoke

### Task 17: Operational runbook

**Files:**

- Create: `docs/operations/nb-mitochondrial-monitor.md`

- [ ] **Step 1: Write the runbook**

Write to `docs/operations/nb-mitochondrial-monitor.md`:

````markdown
# NB Mitochondrial Value Monitor — Operational Runbook

## What it is

Daily cron at 02:30 WITA that records per-NB metrics to SQLite and sends
Telegram alerts on tier regressions. See spec
[`docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md`](../superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md)
for the full design.

## Files and paths

| Artefact           | Path                                                                        |
| ------------------ | --------------------------------------------------------------------------- |
| Bootstrap registry | `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json`            |
| SQLite metrics     | `~/.agent/nb-mitochondrial/metrics.db`                                      |
| Run log            | `~/.agent/nb-mitochondrial/logs/nb-monitor.log`                             |
| Run error log      | `~/.agent/nb-mitochondrial/logs/nb-monitor.error.log`                       |
| LaunchAgent plist  | `~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist` |
| Repo plist source  | `infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist`     |
| Weekly reports     | `~/Desktop/nuzantara/research/nb-monitor/report-YYYY-Www.md`                |
| CLI dashboard      | `scripts/nb-monitor/show.py`                                                |

## Initial deploy

```bash
# 1. Install plist (copy from repo)
cp infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist \
   ~/Library/LaunchAgents/

# 2. Verify lint
plutil -lint ~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist

# 3. Smoke test (no LaunchAgent involved)
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --no-telegram

# 4. Inspect output
sqlite3 ~/.agent/nb-mitochondrial/metrics.db \
  "SELECT uuid, tier, read_freq_7d FROM nb_metrics ORDER BY ts_capture DESC LIMIT 24;"
python scripts/nb-monitor/show.py

# 5. Bootstrap into launchd
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist
launchctl print gui/$(id -u)/com.nuzantara.nb-mitochondrial-monitor.daily | head -20
```

## Force a one-off run

```bash
launchctl kickstart -k gui/$(id -u)/com.nuzantara.nb-mitochondrial-monitor.daily
# OR direct (bypasses launchd)
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once
```

## Tail logs

```bash
tail -f ~/.agent/nb-mitochondrial/logs/nb-monitor.log
tail -f ~/.agent/nb-mitochondrial/logs/nb-monitor.error.log
```

## Force a weekly report

```bash
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --report
```

Report appears at `~/Desktop/nuzantara/research/nb-monitor/report-YYYY-Www.md`.

## Troubleshooting

### Symptom: cron run completed but `metrics.db` empty

- Check `~/.agent/nb-mitochondrial/logs/nb-monitor.error.log` — is `RegistryLoadError` logged? → fix bootstrap JSON.
- Check `ls ~/.claude/projects/-Users-nuzantara/*.jsonl` — empty? Pro session dir may have moved → update `PRIMARY_PATHS` in `collectors/log_scraper.py`.

### Symptom: too many Telegram alerts

- Cooldowns: 24h for top5/tier-transition, 7d for dying-no-action. If duplicate firings, inspect:
  ```
  sqlite3 ~/.agent/nb-mitochondrial/metrics.db \
    "SELECT uuid, condition, datetime(sent_at,'unixepoch') FROM alerts_sent ORDER BY sent_at DESC LIMIT 10;"
  ```
- Set `TELEGRAM_BOT_TOKEN=` empty in plist `EnvironmentVariables` to fully suppress dispatch (the plist will need to be reloaded).

### Symptom: `cookie_refresh_pending` in `instrumentation_status`

- nlm CLI cookie has expired (5min TTL). Run `nlm login --clear` interactively to refresh, then rerun.

### Symptom: `parse_failure` in `instrumentation_status`

- Means the JSONL scraper found zero NLM events across all session files. Either the user has not used NotebookLM in the window OR the JSONL schema changed. Check a recent `~/.claude/projects/-Users-nuzantara/*.jsonl` and grep for `mcp__notebooklm-mcp__notebook_query` — if absent, no real issue; if present and parser missed it, regression in `log_scraper.py`.

### Disable the cron

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist
```

## Future-work pointers

When FASE 1 (Qdrant local skills) merges:

- Wire `collectors/skill_derivation.py::count_skills_for_uuid` to query `bali_zero_skills_local`.
- Tests in `test_skill_derivation.py` (new file) for the wiring.

When FASE 2 (`notebook_registry.py`) merges:

- Update `registry.py::load_registry` to prefer `notebook_registry.NB_REGISTRY` if importable.
- Delete `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json` after one full week of clean runs.

When FASE 4 (Oracle citation logging) merges:

- Wire `collectors/cite_rate.py::compute_rate_for_uuid` to query the citation log.
````

- [ ] **Step 2: Verify markdown lint (best-effort)**

```bash
head -30 docs/operations/nb-mitochondrial-monitor.md
```

Expected: header + first paragraph.

- [ ] **Step 3: Commit**

```bash
git add docs/operations/nb-mitochondrial-monitor.md
git commit -m "docs(nb-monitor): operational runbook with deploy + troubleshooting"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
```

---

### Task 18: ADR — bootstrap JSON migration plan

**Files:**

- Create: `docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md`

- [ ] **Step 1: Verify ADR dir exists**

```bash
ls docs/adr/ 2>&1 | head -3
```

If missing: `mkdir -p docs/adr`.

- [ ] **Step 2: Write the ADR**

Write to `docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md`:

````markdown
# ADR-006: nb_monitor bootstrap JSON registry, migrate to notebook_registry post-FASE-2

**Status:** Accepted (2026-05-07)
**Authors:** Antonello Siano (Zero), Claude Opus 4.7
**Related:** spec `2026-05-07-nb-mitochondrial-monitor-design.md`

## Context

FASE 5 (NB Mitochondrial Value Monitor) needs a list of "active" notebook UUIDs to iterate per cron run. FASE 2 (SENESCENT decommissioning, separate session) is concurrently building `apps/mata-garuda/mata_garuda/notebook_registry.py` as the SSOT for NB classification (`active_routing`, `lifecycle_stage`, `family`, etc.).

Two scope conflicts:

1. FASE 5 cannot wait for FASE 2 to land — they're independent. Need a registry NOW.
2. We do NOT want two registries permanently — drift would compound across PRs.

## Decision

For this PR, FASE 5 reads from `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json` (NOT git-tracked, lives on Pro disk). Schema mirrors what FASE 2 will publish in `notebook_registry.py`. The bootstrap file is hand-curated from `apps/mata-garuda/mata_garuda/config.py::NLM_NOTEBOOKS` (6 UUIDs) plus 1 manually added Property NB; further entries to be added as FASE 2 produces classification data.

`registry.py::load_registry` is written so that — once `notebook_registry.py` exists — a future PR can swap the loader to:

```python
try:
    from mata_garuda.notebook_registry import NB_REGISTRY
    return _from_registry_dict(NB_REGISTRY)
except ImportError:
    return load_from_bootstrap_json(BOOTSTRAP_FILE)
```
````

…without changing any callsite.

JSON instead of YAML to avoid adding `pyyaml` to `apps/mata-garuda/pyproject.toml` deps (mata-garuda venv is intentionally minimal: `pydantic`, `pytest`, `pytest-asyncio`).

## Consequences

- Two registry sources transiently coexist for ≤7 days post FASE-2 merge.
- A follow-up PR (`feat(nb-monitor): consume notebook_registry SSOT`) will:
  1. Update `registry.py::load_registry` to prefer the import path.
  2. Add a deprecation warning (one log line, info-level) when the bootstrap JSON is used.
  3. After 14 days of clean runs against the SSOT, delete the bootstrap JSON.
- Drift risk during the transition: if someone adds an NB to the bootstrap JSON manually but not to `notebook_registry.py`, the cron logs a WARN at the next run (`registry: <uuid> in bootstrap but missing in SSOT`). No silent divergence.

## Alternatives considered

- **Block this PR until FASE 2 ships.** Rejected: FASE 2 and FASE 5 deliver value independently; blocking is sequential coupling without reason.
- **Read from `config.py NLM_NOTEBOOKS` only (6 UUIDs).** Rejected: 6/60+ is too narrow — produces a partial mitochondrial picture. The bootstrap JSON adds CORE/RESEARCH NBs that `NLM_NOTEBOOKS` does not contain.
- **YAML format.** Rejected: pyyaml is a 1-MB dep added solely for human readability. JSON is human-readable enough for a 7-NB file and is part of stdlib.
- **Live MCP `nlm notebook list`.** Rejected: cookie 5min TTL makes this fragile for daily cron. Cookie expiry would result in NULL metrics for every UUID daily.

````

- [ ] **Step 3: Commit**

```bash
git add docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md
git commit -m "docs(adr): ADR-006 bootstrap JSON registry, migrate post-FASE-2"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
````

---

### Task 19: Module README

**Files:**

- Create: `apps/mata-garuda/mata_garuda/scripts/nb_monitor/README.md`

- [ ] **Step 1: Write the README**

Write to `apps/mata-garuda/mata_garuda/scripts/nb_monitor/README.md`:

````markdown
# nb_monitor

Daily cron measuring which NotebookLM notebooks produce value consumed downstream by Nuzantara.

## Quick start (Pro)

```bash
cd apps/mata-garuda
.venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --no-telegram
python ../../scripts/nb-monitor/show.py
```
````

## Architecture

- `registry.py` — loads bootstrap JSON registry, returns `NotebookEntry` dataclasses.
- `collectors/` — five small modules, one per metric (3 live, 2 placeholder).
- `tier.py` — pure decision tree, classifies (`ALIVE`/`IDLE`/`DYING`).
- `alerts.py` — pure logic, evaluates 3 alert conditions with floor + cooldown.
- `telegram_send.py` — minimal urllib-based Telegram dispatcher.
- `persist.py` — SQLite WAL helper + dataclasses.
- `report.py` — markdown weekly report renderer.
- `run.py` — entrypoint that wires it all together. Hard-coded paths via env-overrideable
  constants in `__init__.py`.

## See also

- Spec: [`docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md`](../../../../../docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md)
- Plan: [`docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md`](../../../../../docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md)
- Runbook: [`docs/operations/nb-mitochondrial-monitor.md`](../../../../../docs/operations/nb-mitochondrial-monitor.md)
- ADR: [`docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md`](../../../../../docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md)
- Round 2 memo: `~/.claude/projects/-Users-nuzantara/memory/project_nb_lifecycle_round2_2026_05_04.md`

````

- [ ] **Step 2: Commit**

```bash
git add apps/mata-garuda/mata_garuda/scripts/nb_monitor/README.md
git commit -m "docs(nb-monitor): module README with quick start"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
````

---

### Task 20: Smoke test on Pro and prepare PR

- [ ] **Step 1: Verify all tests still pass**

```bash
cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/ -v --tb=short
```

Expected: all green.

- [ ] **Step 2: Run the monitor live with --once and --no-telegram**

```bash
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --no-telegram
```

Expected: process exits 0, log file created, `metrics.db` populated.

- [ ] **Step 3: Inspect outputs**

```bash
sqlite3 ~/.agent/nb-mitochondrial/metrics.db \
  "SELECT uuid, tier, read_freq_7d, instrumentation_status FROM nb_metrics ORDER BY ts_capture DESC LIMIT 24;"
python scripts/nb-monitor/show.py
ls -la ~/.agent/nb-mitochondrial/logs/
```

Expected: rows with non-zero `read_freq_7d` for at least the most-queried NB UUIDs (per live grep `d9438180` should be top).

- [ ] **Step 4: Force a weekly report**

```bash
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --no-telegram --report
ls ~/Desktop/nuzantara/research/nb-monitor/
head -40 ~/Desktop/nuzantara/research/nb-monitor/report-*.md | head -30
```

Expected: a `report-YYYY-Www.md` file present, banner visible, ranking table printed.

- [ ] **Step 5: Open the PR**

````bash
gh pr create --title "feat(nb-monitor): mitochondrial value monitor cron + weekly report (Round 2)" --body "$(cat <<'EOF'
## Summary

Daily cron `com.nuzantara.nb-mitochondrial-monitor.daily` (02:30 WITA) recording per-NB metrics into SQLite (`~/.agent/nb-mitochondrial/metrics.db`, WAL, schema v1), classifying each NB into ALIVE/IDLE/DYING tiers, and sending Telegram alerts on top-5 drops and tier transitions.

Implements FASE 5 of NB Lifecycle Round 2 ("mitochondrial value monitor": measure which NB produces value consumed downstream by Nuzantara).

## Design + Plan

- Spec: `docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md`
- Plan: `docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md`
- ADR: `docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md`
- Runbook: `docs/operations/nb-mitochondrial-monitor.md`

## Architecture

- 8 small Python modules in `apps/mata-garuda/mata_garuda/scripts/nb_monitor/`.
- 3 live collectors (read_freq via Claude Code JSONL scraper, push_success_rate via feeder log, source_freshness via nlm CLI) + 2 placeholders (skill_derivation pending FASE 1, cite_rate pending FASE 4).
- Tier classifier ALIVE/IDLE/DYING with explicit thresholds (rf7≥5, age>7, psr≥0.95).
- 3 alerts with floor (≥10 absolute drop) + cooldown (24h/7d).
- Pure-logic units (`tier`, `alerts`, `report`) covered by table-driven tests.
- Integration e2e test runs the full pipeline with mocked I/O.

## Sample SQLite schema

```sql
CREATE TABLE nb_metrics (
    uuid TEXT, ts_capture INTEGER, tier TEXT,
    read_freq_7d INTEGER, read_freq_30d INTEGER,
    skill_derivation_count INTEGER,
    downstream_cite_rate REAL,
    source_freshness_age_days INTEGER,
    push_success_rate REAL,
    instrumentation_status TEXT,
    PRIMARY KEY (uuid, ts_capture)
);
CREATE TABLE alerts_sent (
    uuid TEXT, condition TEXT, sent_at INTEGER, payload TEXT,
    PRIMARY KEY (uuid, condition, sent_at)
);
````

## Sample weekly report header

```
# NB Mitochondrial Value Monitor — 2026-W19

> **Baseline period — first 14 days post-deploy. Score reliability degraded:**
> - read_freq_7d/30d: live (Claude Code JSONL scraper)
> - source_freshness_age: best-effort (nlm cookie 5min TTL)
> - push_success_rate: live (matagaruda-nlm-feeder-stream.log; GLOBAL — same value applied per active_routing UUID)
> - skill_derivation_count: N/A pending FASE 1 merge
> - downstream_cite_rate: N/A pending FASE 4 merge
```

## LaunchAgent plist

```xml
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>2</integer>
  <key>Minute</key><integer>30</integer>
</dict>
```

## Alert conditions + cooldowns

| Condition       | Trigger                                                                            | Cooldown |
| --------------- | ---------------------------------------------------------------------------------- | -------- |
| top5_drop_50pct | tier_lastweek=ALIVE AND in top-5 lastweek AND rf7 dropped ≥50% AND ≥10 absolute    | 24h      |
| tier_transition | tier degraded vs lastweek AND age_days > 14                                        | 24h      |
| dying_no_action | tier=DYING for ≥14d AND skill_derivation_count==0 (post FASE-1) AND no traffic 30d | 7d       |

## Test plan

- [x] Unit tests pass: `cd apps/mata-garuda && .venv/bin/pytest tests/nb_monitor/ -v`
- [x] Coverage ≥80% verified via `coverage run --source=mata_garuda/scripts/nb_monitor`
- [x] Smoke test: `python -m mata_garuda.scripts.nb_monitor.run --once --no-telegram` exits 0, populates metrics.db
- [x] Force-report flag: `--once --report --no-telegram` writes `report-YYYY-Www.md`
- [x] CLI dashboard: `python scripts/nb-monitor/show.py` prints ranking
- [x] `plutil -lint` on `infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist`
- [ ] Post-merge: `cp infra/launchagents/...plist ~/Library/LaunchAgents/` + `launchctl bootstrap`
- [ ] Post-merge: confirm first cron run produces ≥18/24 NB rows non-zero (per spec §11)

## Limitations documented

- `push_success_rate` is GLOBAL (no per-UUID breakdown in feeder log today). Same value applied per `active_routing=True` UUID. Per-UUID logging is a follow-up PR.
- 7 of planned 24 bootstrap entries shipped; remaining ~17 await FASE 2 SSOT classification per ADR-006.

## Cicatrix awareness

- Read-only on existing pipeline (spec §7.1).
- WIP-commit-every-10min cadence followed during implementation (cicatrix-scars 2026-04-29 STRUCTURAL "branch hijack antibody").

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

````

- [ ] **Step 6: Mark all plan tasks complete in this file**

Verify by editing this plan and changing the relevant `- [ ]` to `- [x]` for all tasks executed. Commit + push the plan with checkboxes ticked. (This is the convention for executing-plans skill.)

```bash
# Manually edit checkboxes, then:
git add docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md
git commit -m "docs(plan): mark tasks complete"
git push origin feat/nb-mitochondrial-monitor-2026-05-07
````

- [ ] **Step 7: Final summary message to user**

Print a one-liner with: PR URL, total LOC, test count, coverage %.

---

## Self-review checklist (filled by author)

**1. Spec coverage:** every section of `2026-05-07-nb-mitochondrial-monitor-design.md` is addressed:

- §1 Goal → Plan goal line.
- §2 In-scope → Tasks 1-19.
- §2 Out-of-scope → respected (no notebook_registry.py modification, no auto-reconcile script, no cell-observatory monitoring).
- §3 Architecture diagram → File map + Tasks 1-16.
- §3.2 File layout → File map matches exactly.
- §3.3 Data flow → Task 14 `run.py` + Task 15 integration test.
- §4 Data model → Task 3 (schema) + Task 4 (bootstrap JSON).
- §5 Tier classifier → Task 10.
- §6 Alerts (top5/tier/dying) → Task 11 + Task 12.
- §7.1 Read-only → no modifications to existing pipeline.
- §7.2 Graceful degrade → `_collect_all` per-UUID try/except + `execute_once` outer try/except + exit 0.
- §7.3 First-14-days banner → Task 13 `BASELINE_BANNER` + `baseline_window` flag.
- §7.4 No backpressure → off-peak 02:30 + read-only.
- §8 Test plan → Tasks 2,3,6,7,8,10,11,12,13,15.
- §9 Build sequence → 4 commit blocks + WIP convention.
- §10 ADR → Task 18.
- §11 Success criteria → smoke step in Task 20 references the criteria.

**2. Placeholder scan:** none of the forbidden phrases ("TBD", "TODO", "implement later", "similar to Task N") used. Every code step has full code, every command step has the exact invocation.

**3. Type consistency:**

- `MetricRow` and `AlertRecord` defined in Task 3 used identically in Tasks 14, 15, 16.
- `Tier` enum from Task 10 used in Tasks 11 (alerts), 13 (report), 14 (run), 15 (integration).
- `AlertCondition` enum from Task 11 used by name in Task 14.
- `NotebookEntry` from Task 2 used in Tasks 14 and 15.
- `RunConfig` injected via dataclass; `collect_*` callable types match between definition (Task 14) and stubs (Task 15 conftest).

**4. Ambiguity check:**

- "Active routing" is bool — only TRUE UUIDs receive `psr` from global feeder rate; FALSE UUIDs get None.
- "first_audited" is the only mandatory date field; `last_audited` and `round2_classification` are optional.
- 24 NB target — bootstrap ships with 7 confirmed; warn (don't fail) if registry has fewer.
- Sunday detection uses `datetime.weekday() == 6`.

No outstanding ambiguity. Ready to execute.
