# SYMBIOSIS W2 — KG → Pro MCP Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose mata-garuda SQLite KG (Mini, 409e/1549r/622o) as Pro-side MCP tool via Tailscale-only HTTP, with admin-gated access and no OSINT body leakage.

**Architecture:** Mini runs a stdlib `http.server` daemon on `100.93.236.6:8990` reading `~/.agent/mata-garuda/kg.db` read-only. Pro `apps/nuzantara-mcp/` adds a `kg_intel.py` tool that calls Mini via `httpx.AsyncClient`. Three tools registered: `kg_intel_search`, `kg_intel_entity`, `kg_intel_health`. Six logical commits enforce doctrine-first sequencing.

**Tech Stack:** Python 3.11, stdlib `http.server` + `sqlite3` (Mini, no new deps), `fastmcp` + `httpx` + `pytest-asyncio` (Pro, already present), `launchd` plist (Mini daemon).

**Spec:** [`docs/superpowers/specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md`](../specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md)

**Worktree:** `.worktrees/symbiosis-W2/` (already created, on branch `feat/symbiosis-W2-kg-zantara-bridge-2026-05-07`).

**All commands assume CWD = `.worktrees/symbiosis-W2/`** unless noted otherwise.

---

## File Structure

```
apps/mata-garuda/
├── CLAUDE.md                              # MODIFY: append §1.4 (commit 1)
├── mata_garuda/
│   └── api/                               # CREATE
│       ├── __init__.py                    # CREATE (empty)
│       └── kg_query.py                    # CREATE: stdlib HTTP server + handlers
├── tests/
│   └── api/                               # CREATE
│       ├── __init__.py                    # CREATE (empty)
│       └── test_kg_query.py               # CREATE: T1-T12
└── scripts/                               # CREATE if missing
    └── bench_kg_api.py                    # CREATE: latency benchmark

apps/nuzantara-mcp/
├── nuzantara_mcp/
│   ├── server.py                          # MODIFY: 2 lines (commit 5)
│   └── tools/
│       └── kg_intel.py                    # CREATE: 3 tools, register()
└── tests/
    └── test_tools_kg_intel.py             # CREATE: P1-P8

infra/launchagents/
└── com.matagaruda.kg-query-api.plist      # CREATE

scripts/
└── mata-garuda-kg-api.sh                  # CREATE: launchd bridge

docs/
└── symbiosis/
    └── W2-kg-bridge-runbook.md            # CREATE (commit 6)
```

---

## Task 1: Doctrine commit — append §1.4 to mata-garuda CLAUDE.md

**Files:**

- Modify: `apps/mata-garuda/CLAUDE.md` (append after `## 1. Vincoli inviolabili` block, before `## 2.`)

This commit lands FIRST. Zero pre-approved the verbatim text; we just paste it in. Zero code touched.

- [ ] **Step 1: Locate insertion point**

Run: `grep -n "^## 2\. Comportamento Claude Code" apps/mata-garuda/CLAUDE.md`
Expected: one line number reported. The new §1.4 block is inserted immediately before that line (so it becomes the last subsection of §1).

- [ ] **Step 2: Insert §1.4 block**

Use `Edit` tool with `old_string` = the existing `## 2. Comportamento Claude Code` line and `new_string` = the §1.4 block + blank line + `## 2. Comportamento Claude Code` (preserves heading). Block content:

```markdown
### §1.4 Eccezione Pillar 3 SYMBIOSIS — KG metadata sharing

Deroga esplicita autorizzata da Zero 2026-05-06: il KG SQLite locale
(~/.agent/mata-garuda/kg.db) può esporre metadata operativi (entity
names, type, neighbor list, observation_count) verso organi locali Pro
via Tailscale loopback (NO Fly, NO cloud, NO frontend, NO team).

Payload ammesso: name, type, source_count, last_seen, neighbor_names,
observation_count, observation.source_url (sempre URL pubblico, mai
body content).

Payload VIETATO: observation.value (può contenere title/snippet OSINT
raw), content fields, full text article.

Justification: SYMBIOSIS.md Pilastro 3 Condivisione: "ogni agente
pubblica conoscenza operativa, mai dati OSINT". L'identità di una
entità menzionata è conoscenza operativa, l'articolo grezzo no.

Implementation reference: `docs/superpowers/specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md`.
```

- [ ] **Step 3: Verify**

Run: `grep -A 2 "Eccezione Pillar 3" apps/mata-garuda/CLAUDE.md | head -5`
Expected: the heading + first 2 lines visible.

- [ ] **Step 4: Commit**

```bash
git add apps/mata-garuda/CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(mata-garuda): add §1.4 SYMBIOSIS Pillar 3 doctrine exception for KG metadata sharing

Approved-by-Zero verbatim exception authorising operational-metadata
export from ~/.agent/mata-garuda/kg.db towards Pro-side organs via
Tailscale loopback. Required precursor to feat(symbiosis) commits.

Payload allowed: name, type, source_count, last_seen, neighbor_names,
observation_count, observation.source_url. Payload forbidden:
observation.value, content fields, full article body.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Mini-side — create `kg_query.py` skeleton + read-only DB connection

**Files:**

- Create: `apps/mata-garuda/mata_garuda/api/__init__.py` (empty)
- Create: `apps/mata-garuda/mata_garuda/api/kg_query.py`

This task creates only the module skeleton + read-only DB helper. Endpoints arrive in later tasks. Ensures we don't accidentally open a writable connection.

- [ ] **Step 1: Create `__init__.py`**

```bash
mkdir -p apps/mata-garuda/mata_garuda/api
: > apps/mata-garuda/mata_garuda/api/__init__.py
```

- [ ] **Step 2: Create test file with skeleton + first failing test (T-skel-1)**

Create `apps/mata-garuda/tests/api/__init__.py` (empty), then `apps/mata-garuda/tests/api/test_kg_query.py`:

```python
"""Tests for mata_garuda.api.kg_query (stdlib HTTP API for KG metadata)."""
from __future__ import annotations

import http.client
import json
import sqlite3
import threading
import time
import urllib.parse
from pathlib import Path

import pytest

from mata_garuda.api import kg_query


@pytest.fixture
def kg_db_seeded(tmp_path: Path) -> Path:
    """Build a temp KG with 3 entities, 2 relations, 4 observations."""
    db = tmp_path / "kg.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE kg_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            aliases_json TEXT NOT NULL DEFAULT '[]',
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            source_count INTEGER NOT NULL DEFAULT 1,
            UNIQUE(type, canonical_name)
        );
        CREATE TABLE kg_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            predicate TEXT NOT NULL,
            object_id INTEGER NOT NULL,
            evidence_url TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            source_count INTEGER NOT NULL DEFAULT 1,
            UNIQUE(subject_id, predicate, object_id)
        );
        CREATE TABLE kg_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL,
            field TEXT NOT NULL,
            value TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            source_url TEXT
        );
        """
    )
    # Seed
    conn.executemany(
        "INSERT INTO kg_entities(type, canonical_name, first_seen, last_seen, source_count) VALUES (?, ?, ?, ?, ?)",
        [
            ("organizations", "Direktorat Jenderal Imigrasi", "2026-03-12T08:11:02+00:00", "2026-04-30T12:14:09+00:00", 17),
            ("topics", "KITAS Investor", "2026-03-15T00:00:00+00:00", "2026-04-30T00:00:00+00:00", 9),
            ("laws", "Permenkumham 22/2023", "2026-03-10T00:00:00+00:00", "2026-04-12T00:00:00+00:00", 4),
        ],
    )
    conn.executemany(
        "INSERT INTO kg_relations(subject_id, predicate, object_id, evidence_url, first_seen, last_seen, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "regulates", 2, "https://imigrasi.go.id/announcement", "2026-04-01T00:00:00+00:00", "2026-04-30T00:00:00+00:00", 0.78),
            (1, "issued_by", 3, "https://kemenkumham.go.id/uu", "2026-03-20T00:00:00+00:00", "2026-04-12T00:00:00+00:00", 0.85),
        ],
    )
    conn.executemany(
        "INSERT INTO kg_observations(entity_id, field, value, observed_at, source_url) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "headline", "Imigrasi tightens KITAS rules — SECRET RAW BODY", "2026-04-30T12:14:09+00:00", "https://imigrasi.go.id/2026/04/30/announcement"),
            (1, "headline", "Imigrasi appoints new director — SECRET RAW BODY", "2026-04-21T03:00:00+00:00", "https://kemenkumham.go.id/news/12345"),
            (2, "mention", "KITAS investor visa explained — SECRET RAW BODY", "2026-04-30T00:00:00+00:00", "https://example.org/k1"),
            (3, "mention", "UU Permenkumham 22 — SECRET RAW BODY", "2026-04-12T00:00:00+00:00", "https://example.org/k2"),
        ],
    )
    conn.commit()
    conn.close()
    return db


def _start_server(db_path: Path) -> tuple["kg_query.KGServer", threading.Thread, int]:
    """Start the server on 127.0.0.1:0 and return (server, thread, port)."""
    server = kg_query.build_server(bind="127.0.0.1", port=0, db_path=db_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    # Tiny readiness wait
    for _ in range(20):
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
            c.request("GET", "/health")
            c.getresponse().read()
            c.close()
            break
        except Exception:
            time.sleep(0.05)
    return server, thread, port


@pytest.fixture
def running_server(kg_db_seeded: Path):
    server, thread, port = _start_server(kg_db_seeded)
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get(port: int, path: str) -> tuple[int, dict]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    c.request("GET", path)
    resp = c.getresponse()
    body = resp.read().decode("utf-8")
    c.close()
    parsed: dict = json.loads(body) if body else {}
    return resp.status, parsed


def test_skel_module_exposes_build_server(kg_db_seeded: Path) -> None:
    """T-skel-1: kg_query exposes build_server(bind, port, db_path) returning a KGServer."""
    server = kg_query.build_server(bind="127.0.0.1", port=0, db_path=kg_db_seeded)
    try:
        assert isinstance(server, kg_query.KGServer)
    finally:
        server.server_close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/mata-garuda && source .venv/bin/activate && python -m pytest tests/api/test_kg_query.py::test_skel_module_exposes_build_server -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mata_garuda.api'` or similar.

- [ ] **Step 4: Implement minimum `kg_query.py` to make T-skel-1 pass**

Create `apps/mata-garuda/mata_garuda/api/kg_query.py`:

```python
"""HTTP API exposing mata-garuda KG metadata over Tailscale loopback.

Hard rules (see apps/mata-garuda/CLAUDE.md §1.4):
- Bind only to Tailscale interface or 127.0.0.1 (test). Refuse 0.0.0.0 / ::.
- Never return observation.value, evidence_url, aliases_json, content/title/body.
- Read-only sqlite connection (mode=ro URI).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logger = logging.getLogger("mata_garuda.api.kg_query")

DEFAULT_KG_PATH = Path.home() / ".agent" / "mata-garuda" / "kg.db"
DEFAULT_BIND = "100.93.236.6"
DEFAULT_PORT = 8990
SEARCH_LIMIT_HARD_CAP = 100
SEARCH_LIMIT_DEFAULT = 20
NEIGHBOR_HARD_CAP = 50

FORBIDDEN_BIND_PREFIXES = ("0.0.0.0", "::", "0:0:0:0")

ENTITY_TYPES = {"persons", "organizations", "locations", "laws", "topics"}

# Path safety: name must not contain / or .. or null bytes after URL decoding.
_SAFE_NAME_RE = re.compile(r"^[^\x00/]+$")


def _ro_conn(db_path: Path) -> sqlite3.Connection:
    """Open a read-only connection. Safe even if writer is active (WAL)."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class KGQueryHandler(BaseHTTPRequestHandler):
    server_version = "matagaruda-kg-query/1.0"

    # Suppress default stdout-noisy log_message; we use our logger.
    def log_message(self, fmt: str, *args: Any) -> None:
        # Audit line: status + path only, never body.
        try:
            ip = self.client_address[0]
        except Exception:
            ip = "?"
        logger.info("%s - %s", ip, fmt % args)

    # endpoints implemented in later tasks; skeleton serves nothing yet
    def do_GET(self) -> None:  # noqa: N802
        self._send_json(404, {"error": "not_found", "detail": "endpoint not implemented yet"})

    # ── helpers ──────────────────────────────────────────────────
    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


class _ConfiguredServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that carries the configured KG path."""

    def __init__(self, server_address: tuple[str, int], handler_cls: type, db_path: Path) -> None:
        super().__init__(server_address, handler_cls)
        self.db_path = db_path


def build_server(*, bind: str, port: int, db_path: Path | None = None) -> _ConfiguredServer:
    """Construct the HTTP server. Refuse forbidden bind addresses."""
    if any(bind == p or bind.startswith(p + ":") for p in FORBIDDEN_BIND_PREFIXES):
        raise RuntimeError(f"refusing to bind on wildcard address {bind!r}")
    db = db_path or DEFAULT_KG_PATH
    return _ConfiguredServer((bind, port), KGQueryHandler, db)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mata-garuda KG query API")
    parser.add_argument("--bind", default=os.getenv("KG_API_BIND", DEFAULT_BIND))
    parser.add_argument("--port", type=int, default=int(os.getenv("KG_API_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--db-path", type=Path, default=DEFAULT_KG_PATH)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = build_server(bind=args.bind, port=args.port, db_path=args.db_path)
    logger.info("kg-query listening on %s:%s db=%s", args.bind, args.port, args.db_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

The test references `kg_query.KGServer` (a public alias for `_ConfiguredServer`). Add at the end of `kg_query.py`:

```python
# Public alias used by tests; we keep `_ConfiguredServer` private so the
# stdlib `ThreadingHTTPServer` name in this file is unambiguously the base
# class from `http.server`.
KGServer = _ConfiguredServer
```

(The test already imports it as `kg_query.KGServer` — no edit needed.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/mata-garuda && python -m pytest tests/api/test_kg_query.py::test_skel_module_exposes_build_server -v`
Expected: PASS.

- [ ] **Step 6: Add T10 (refuse 0.0.0.0)**

Append to `tests/api/test_kg_query.py`:

```python
def test_t10_refuses_wildcard_bind(tmp_path: Path) -> None:
    """T10: server refuses 0.0.0.0 bind at startup."""
    db = tmp_path / "kg.db"
    db.touch()
    with pytest.raises(RuntimeError, match="wildcard"):
        kg_query.build_server(bind="0.0.0.0", port=0, db_path=db)
    with pytest.raises(RuntimeError, match="wildcard"):
        kg_query.build_server(bind="::", port=0, db_path=db)
```

- [ ] **Step 7: Run T10**

Run: `python -m pytest tests/api/test_kg_query.py -v`
Expected: 2 PASS.

- [ ] **Step 8: Commit (work-in-progress, no push yet)**

```bash
git add apps/mata-garuda/mata_garuda/api/ apps/mata-garuda/tests/api/
git commit -m "feat(mata-garuda): add kg_query HTTP API skeleton (build_server + bind guardrail)"
```

(This commit is intermediate; final commit-2 from spec §13 will be reached after T1-T12.)

---

## Task 3: Implement `/health` endpoint (T1, T2)

**Files:**

- Modify: `apps/mata-garuda/mata_garuda/api/kg_query.py`
- Modify: `apps/mata-garuda/tests/api/test_kg_query.py`

- [ ] **Step 1: Add T1 + T2 tests**

Append to `tests/api/test_kg_query.py`:

```python
def test_t1_health_ok(running_server: int) -> None:
    """T1: /health reports counts when KG is seeded."""
    status, body = _get(running_server, "/health")
    assert status == 200
    assert body["ok"] is True
    assert body["entities_count"] == 3
    assert body["relations_count"] == 2
    assert body["observations_count"] == 4
    assert body["schema_ok"] is True


def test_t2_health_schema_missing(tmp_path: Path) -> None:
    """T2: /health returns schema_ok=false fail-soft if a table is missing."""
    db = tmp_path / "broken.db"
    conn = sqlite3.connect(str(db))
    # Only kg_entities, no relations/observations
    conn.execute(
        "CREATE TABLE kg_entities (id INTEGER, type TEXT, canonical_name TEXT, "
        "aliases_json TEXT DEFAULT '[]', first_seen TEXT, last_seen TEXT, source_count INTEGER DEFAULT 1)"
    )
    conn.commit()
    conn.close()
    server, thread, port = _start_server(db)
    try:
        status, body = _get(port, "/health")
        assert status == 200
        assert body["ok"] is True  # server lives even if KG broken
        assert body["schema_ok"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
```

- [ ] **Step 2: Run T1 + T2 to verify failure**

Run: `python -m pytest tests/api/test_kg_query.py::test_t1_health_ok tests/api/test_kg_query.py::test_t2_health_schema_missing -v`
Expected: FAIL — 404 from skeleton.

- [ ] **Step 3: Implement `/health`**

In `kg_query.py`, replace `do_GET` with:

```python
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/health":
            return self._handle_health()
        self._send_json(404, {"error": "not_found", "detail": "no such endpoint"})

    def _handle_health(self) -> None:
        db_path = self.server.db_path
        try:
            conn = _ro_conn(db_path)
        except sqlite3.Error as exc:
            return self._send_json(500, {
                "ok": False,
                "kg_path": str(db_path),
                "error": "kg_unavailable",
                "detail": str(exc),
            })
        try:
            schema_ok = True
            counts = {"entities_count": 0, "relations_count": 0, "observations_count": 0}
            for tbl, key in (
                ("kg_entities", "entities_count"),
                ("kg_relations", "relations_count"),
                ("kg_observations", "observations_count"),
            ):
                try:
                    counts[key] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                except sqlite3.Error:
                    schema_ok = False
            self._send_json(200, {
                "ok": True,
                "kg_path": str(db_path),
                "schema_ok": schema_ok,
                **counts,
            })
        finally:
            conn.close()
```

- [ ] **Step 4: Run T1 + T2 to verify they pass**

Run: `python -m pytest tests/api/test_kg_query.py -v`
Expected: all tests so far PASS (skel + T10 + T1 + T2).

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/api/kg_query.py apps/mata-garuda/tests/api/test_kg_query.py
git commit -m "feat(mata-garuda): kg_query /health endpoint with fail-soft schema check"
```

---

## Task 4: Implement `/kg/search` (T3, T4, T5, T12)

**Files:**

- Modify: `apps/mata-garuda/mata_garuda/api/kg_query.py`
- Modify: `apps/mata-garuda/tests/api/test_kg_query.py`

- [ ] **Step 1: Add T3, T4, T5, T12 tests**

Append:

```python
def test_t3_search_substring_case_insensitive(running_server: int) -> None:
    """T3: search returns substring matches with metadata only."""
    status, body = _get(running_server, "/kg/search?q=imigrasi")
    assert status == 200
    assert body["query"] == "imigrasi"
    names = [r["name"] for r in body["results"]]
    assert "Direktorat Jenderal Imigrasi" in names
    rec = next(r for r in body["results"] if r["name"] == "Direktorat Jenderal Imigrasi")
    assert rec["type"] == "organizations"
    assert rec["source_count"] == 17
    assert "last_seen" in rec
    assert "value" not in rec
    assert "aliases_json" not in rec


def test_t4_search_empty_query_400(running_server: int) -> None:
    """T4: empty q returns 400."""
    status, body = _get(running_server, "/kg/search?q=")
    assert status == 400
    assert body["error"] == "bad_request"


def test_t5_search_limit_hard_capped(running_server: int) -> None:
    """T5: limit param is hard-capped to 100."""
    status, body = _get(running_server, "/kg/search?q=i&limit=999")
    assert status == 200
    # The seeded fixture has 3 entities total; we just assert the cap is applied.
    assert body["limit"] == 100


def test_t12_search_path_traversal_rejected(running_server: int) -> None:
    """T12: path traversal in /kg/entity/.. is rejected."""
    status, body = _get(running_server, "/kg/entity/..%2Fetc%2Fpasswd?type=persons")
    # This belongs in the entity test, but we put it here pre-emptively
    # since path safety applies to all routes.
    assert status == 400
    assert body["error"] == "bad_request"
```

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest tests/api/test_kg_query.py -v -k "t3 or t4 or t5 or t12"`
Expected: FAIL.

- [ ] **Step 3: Implement `/kg/search` + path safety helper**

Update `do_GET` to add the `/kg/search` branch and a path-safety helper. In `kg_query.py`, replace `do_GET` and add helpers:

```python
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if path == "/health":
            return self._handle_health()
        if path == "/kg/search":
            return self._handle_search(qs)
        if path.startswith("/kg/entity/"):
            raw = path[len("/kg/entity/"):]
            return self._handle_entity(raw, qs)
        self._send_json(404, {"error": "not_found", "detail": "no such endpoint"})

    def _handle_search(self, qs: dict[str, list[str]]) -> None:
        q = (qs.get("q", [""])[0] or "").strip()
        if not q:
            return self._send_json(400, {"error": "bad_request", "detail": "q is required"})
        try:
            limit_raw = int(qs.get("limit", [str(SEARCH_LIMIT_DEFAULT)])[0])
        except ValueError:
            return self._send_json(400, {"error": "bad_request", "detail": "limit must be int"})
        limit = max(1, min(SEARCH_LIMIT_HARD_CAP, limit_raw))
        try:
            conn = _ro_conn(self.server.db_path)
        except sqlite3.Error as exc:
            return self._send_json(503, {"error": "kg_unavailable", "detail": str(exc)})
        try:
            rows = conn.execute(
                "SELECT type, canonical_name, source_count, last_seen "
                "FROM kg_entities "
                "WHERE LOWER(canonical_name) LIKE ? "
                "ORDER BY source_count DESC, last_seen DESC LIMIT ?",
                (f"%{q.lower()}%", limit),
            ).fetchall()
        except sqlite3.Error as exc:
            return self._send_json(503, {"error": "kg_unavailable", "detail": str(exc)})
        finally:
            conn.close()
        results = [
            {
                "name": r["canonical_name"],
                "type": r["type"],
                "source_count": r["source_count"],
                "last_seen": r["last_seen"],
            }
            for r in rows
        ]
        self._send_json(200, {"query": q, "limit": limit, "results": results})

    def _handle_entity(self, raw_name: str, qs: dict[str, list[str]]) -> None:
        # Path-safety: decode and reject traversal/control-byte names
        decoded = urllib.parse.unquote(raw_name)
        if not decoded or not _SAFE_NAME_RE.match(decoded) or ".." in decoded:
            return self._send_json(400, {"error": "bad_request", "detail": "invalid name"})
        # Endpoint full implementation arrives in Task 5.
        self._send_json(501, {"error": "not_implemented", "detail": "entity endpoint pending"})
```

- [ ] **Step 4: Run, expect T3/T4/T5/T12 to pass**

Run: `python -m pytest tests/api/test_kg_query.py -v`
Expected: all current tests PASS (skel + T1 + T2 + T3 + T4 + T5 + T10 + T12).

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/api/kg_query.py apps/mata-garuda/tests/api/test_kg_query.py
git commit -m "feat(mata-garuda): kg_query /kg/search + path-safety helper for /kg/entity"
```

---

## Task 5: Implement `/kg/entity/{name}` (T6, T7, T8)

**Files:**

- Modify: `apps/mata-garuda/mata_garuda/api/kg_query.py`
- Modify: `apps/mata-garuda/tests/api/test_kg_query.py`

- [ ] **Step 1: Add T6, T7, T8**

Append:

```python
def test_t6_entity_full_record(running_server: int) -> None:
    """T6: entity returns name/type/source_count/last_seen + neighbors + observations(no value)."""
    status, body = _get(
        running_server,
        "/kg/entity/" + urllib.parse.quote("Direktorat Jenderal Imigrasi") + "?type=organizations",
    )
    assert status == 200
    assert body["name"] == "Direktorat Jenderal Imigrasi"
    assert body["type"] == "organizations"
    assert body["source_count"] == 17
    assert body["observation_count"] == 2
    assert len(body["neighbor_names"]) == 2
    pred = {n["predicate"] for n in body["neighbor_names"]}
    assert {"regulates", "issued_by"} == pred
    assert all("name" in n and "type" in n and "confidence" in n for n in body["neighbor_names"])
    # Forbidden fields absent in any observation
    for obs in body["observations"]:
        assert "value" not in obs
        assert "field" not in obs
        assert "source_url" in obs
        assert "observed_at" in obs


def test_t7_entity_missing_type_400(running_server: int) -> None:
    """T7: missing type query param returns 400."""
    status, body = _get(running_server, "/kg/entity/Imigrasi")
    assert status == 400
    assert body["error"] == "bad_request"


def test_t8_entity_unknown_404(running_server: int) -> None:
    """T8: unknown entity returns 404 entity_not_found."""
    status, body = _get(running_server, "/kg/entity/Zaphod?type=persons")
    assert status == 404
    assert body["error"] == "entity_not_found"
```

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest tests/api/test_kg_query.py -v -k "t6 or t7 or t8"`
Expected: FAIL.

- [ ] **Step 3: Implement entity handler**

In `kg_query.py`, replace the stub `_handle_entity` with the full version:

```python
    def _handle_entity(self, raw_name: str, qs: dict[str, list[str]]) -> None:
        decoded = urllib.parse.unquote(raw_name)
        if not decoded or not _SAFE_NAME_RE.match(decoded) or ".." in decoded:
            return self._send_json(400, {"error": "bad_request", "detail": "invalid name"})
        entity_type = (qs.get("type", [""])[0] or "").strip()
        if not entity_type:
            return self._send_json(400, {"error": "bad_request", "detail": "type is required"})
        if entity_type not in ENTITY_TYPES:
            return self._send_json(400, {"error": "bad_request", "detail": f"unknown type {entity_type!r}"})
        try:
            conn = _ro_conn(self.server.db_path)
        except sqlite3.Error as exc:
            return self._send_json(503, {"error": "kg_unavailable", "detail": str(exc)})
        try:
            ent = conn.execute(
                "SELECT id, source_count, first_seen, last_seen "
                "FROM kg_entities WHERE type=? AND canonical_name=?",
                (entity_type, decoded),
            ).fetchone()
            if ent is None:
                return self._send_json(404, {"error": "entity_not_found", "detail": "no such entity"})
            ent_id = ent["id"]
            neighbors = conn.execute(
                "SELECT r.predicate, r.confidence, e.type AS object_type, e.canonical_name AS object_name "
                "FROM kg_relations r JOIN kg_entities e ON e.id = r.object_id "
                "WHERE r.subject_id=? "
                "ORDER BY r.confidence DESC, r.source_count DESC LIMIT ?",
                (ent_id, NEIGHBOR_HARD_CAP),
            ).fetchall()
            observations = conn.execute(
                "SELECT observed_at, source_url FROM kg_observations "
                "WHERE entity_id=? ORDER BY observed_at DESC LIMIT 50",
                (ent_id,),
            ).fetchall()
            obs_total = conn.execute(
                "SELECT COUNT(*) FROM kg_observations WHERE entity_id=?",
                (ent_id,),
            ).fetchone()[0]
        except sqlite3.Error as exc:
            return self._send_json(503, {"error": "kg_unavailable", "detail": str(exc)})
        finally:
            conn.close()
        self._send_json(200, {
            "name": decoded,
            "type": entity_type,
            "source_count": ent["source_count"],
            "first_seen": ent["first_seen"],
            "last_seen": ent["last_seen"],
            "neighbor_names": [
                {
                    "name": n["object_name"],
                    "type": n["object_type"],
                    "predicate": n["predicate"],
                    "confidence": n["confidence"],
                }
                for n in neighbors
            ],
            "observation_count": obs_total,
            "observations": [
                {"observed_at": o["observed_at"], "source_url": o["source_url"]}
                for o in observations
            ],
        })
```

- [ ] **Step 4: Run, expect pass**

Run: `python -m pytest tests/api/test_kg_query.py -v`
Expected: all tests PASS (skel + T1 + T2 + T3 + T4 + T5 + T6 + T7 + T8 + T10 + T12).

- [ ] **Step 5: Commit**

```bash
git add apps/mata-garuda/mata_garuda/api/kg_query.py apps/mata-garuda/tests/api/test_kg_query.py
git commit -m "feat(mata-garuda): kg_query /kg/entity/{name}?type= with neighbor + obs metadata"
```

---

## Task 6: Forbidden-fields deep-walk guarantee (T9) + concurrency (T11)

**Files:**

- Modify: `apps/mata-garuda/tests/api/test_kg_query.py`

- [ ] **Step 1: Add T9 + T11**

Append:

```python
def _walk_keys(obj: Any) -> set[str]:
    """Recursively collect all dict keys present in obj."""
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            found |= _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            found |= _walk_keys(item)
    return found


def test_t9_no_forbidden_fields_anywhere(running_server: int) -> None:
    """T9: NO forbidden field name in any response payload."""
    forbidden = {"value", "evidence_url", "aliases_json", "aliases", "content", "title", "body", "excerpt", "summary", "field"}
    paths = [
        "/health",
        "/kg/search?q=i&limit=99",
        "/kg/entity/" + urllib.parse.quote("Direktorat Jenderal Imigrasi") + "?type=organizations",
    ]
    for path in paths:
        status, body = _get(running_server, path)
        assert status == 200, f"{path} returned {status}"
        keys = _walk_keys(body)
        leaks = forbidden & keys
        assert not leaks, f"{path} leaks forbidden fields: {leaks}"


def test_t11_concurrent_reads(running_server: int) -> None:
    """T11: 10 threads x 50 reads, no deadlock, all 200."""
    import concurrent.futures

    def worker() -> int:
        ok = 0
        for _ in range(50):
            s, _ = _get(running_server, "/kg/search?q=i")
            if s == 200:
                ok += 1
        return ok

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: worker(), range(10)))
    assert sum(results) == 500
```

- [ ] **Step 2: Run, expect both PASS (the implementation should already satisfy them)**

Run: `python -m pytest tests/api/test_kg_query.py -v`
Expected: 12/12 PASS (T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12 + skel = 13 actually, including the skeleton check).

If T9 fails because of any leaked field, fix the relevant handler in `kg_query.py` (do NOT relax the test).
If T11 fails (deadlock), the issue is most likely accidentally sharing one connection across threads — the code already opens a fresh `_ro_conn` per request so this should be OK; if not, switch to creating the connection inside the handler method (already done).

- [ ] **Step 3: Commit**

```bash
git add apps/mata-garuda/tests/api/test_kg_query.py
git commit -m "test(mata-garuda): forbidden-fields deep-walk + concurrent-read tests for kg_query"
```

---

## Task 7: Latency benchmark script

**Files:**

- Create: `apps/mata-garuda/scripts/bench_kg_api.py`

Standalone single-file script using stdlib only. Run from Pro: `python scripts/bench_kg_api.py http://100.93.236.6:8990`.

- [ ] **Step 1: Write benchmark**

Create `apps/mata-garuda/scripts/bench_kg_api.py`:

```python
#!/usr/bin/env python3
"""Latency benchmark for mata-garuda kg-query API.

Usage:
    python scripts/bench_kg_api.py http://100.93.236.6:8990 [N=100] [path=/kg/search?q=imigrasi]
"""
from __future__ import annotations

import statistics
import sys
import time
import urllib.parse
import urllib.request


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    base = sys.argv[1].rstrip("/")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    path = sys.argv[3] if len(sys.argv) > 3 else "/kg/search?q=imigrasi"
    url = base + path
    durations: list[float] = []
    errors = 0
    for i in range(n):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                resp.read()
                if resp.status != 200:
                    errors += 1
        except Exception:
            errors += 1
            continue
        durations.append((time.perf_counter() - t0) * 1000.0)
    durations.sort()
    if not durations:
        print(f"all {n} requests failed")
        return 1
    p50 = statistics.median(durations)
    p95 = durations[int(0.95 * len(durations)) - 1]
    p99 = durations[int(0.99 * len(durations)) - 1]
    print(f"target  : {url}")
    print(f"samples : {len(durations)}/{n} (errors={errors})")
    print(f"p50_ms  : {p50:.1f}")
    print(f"p95_ms  : {p95:.1f}")
    print(f"p99_ms  : {p99:.1f}")
    print(f"min_ms  : {min(durations):.1f}")
    print(f"max_ms  : {max(durations):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test against local 127.0.0.1 fixture**

In a second terminal start a temporary server (or just sanity-check the script syntax):

```bash
python scripts/bench_kg_api.py --help 2>&1 || python -c "import scripts.bench_kg_api"
```

(Actual benchmark against Mini happens at deploy time, in Task 12.)

- [ ] **Step 3: Commit**

```bash
git add apps/mata-garuda/scripts/bench_kg_api.py
git commit -m "feat(mata-garuda): kg_query latency benchmark script (stdlib only)"
```

---

## Task 8: Mini-side launchd plist + bridge script

**Files:**

- Create: `infra/launchagents/com.matagaruda.kg-query-api.plist`
- Create: `scripts/mata-garuda-kg-api.sh`

These are repo-canonical copies. Manual install on Mini happens in Task 12 (post-merge ops).

- [ ] **Step 1: Create bridge script**

Create `scripts/mata-garuda-kg-api.sh` with mode 0755:

```bash
#!/usr/bin/env bash
# Bridge: launchd entry point for mata-garuda kg-query-api.
# TCC note: launchd-spawned /bin/zsh cannot open ~/Desktop files; we exec
# the venv python directly (adhoc-signed, bypasses TCC).
set -euo pipefail

REPO_ROOT="${MATA_GARUDA_REPO:-${HOME}/Desktop/nuzantara}"
VENV_PY="${REPO_ROOT}/apps/mata-garuda/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[$(date -u +%FT%TZ)] ERROR: venv python missing at $VENV_PY" >&2
    exit 78  # EX_CONFIG
fi

cd "${REPO_ROOT}/apps/mata-garuda"
exec "$VENV_PY" -m mata_garuda.api.kg_query
```

```bash
chmod 0755 scripts/mata-garuda-kg-api.sh
```

- [ ] **Step 2: Create plist**

Create `infra/launchagents/com.matagaruda.kg-query-api.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.matagaruda.kg-query-api</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/Desktop/nuzantara/scripts/mata-garuda-kg-api.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>KG_API_BIND</key>
        <string>100.93.236.6</string>
        <key>KG_API_PORT</key>
        <string>8990</string>
        <key>MATA_GARUDA_REPO</key>
        <string>/Users/nuzantara/Desktop/nuzantara</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/mata-garuda-kg-api.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/mata-garuda-kg-api.err</string>
    <key>ThrottleInterval</key>
    <integer>15</integer>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara</string>
</dict>
</plist>
```

- [ ] **Step 3: Lint plist**

Run: `plutil -lint infra/launchagents/com.matagaruda.kg-query-api.plist`
Expected: `infra/launchagents/com.matagaruda.kg-query-api.plist: OK`.

- [ ] **Step 4: Commit (this completes the spec §13 commit-3 boundary)**

```bash
git add infra/launchagents/com.matagaruda.kg-query-api.plist scripts/mata-garuda-kg-api.sh
git commit -m "$(cat <<'EOF'
feat(mata-garuda): launchd plist + bridge for kg-query-api daemon

Mini-side daemon, KeepAlive=true, binds Tailscale IP only via
KG_API_BIND env. Bridge script uses venv python (TCC-bypass per
mata-garuda-watcher.sh pattern).

Manual install on Mini:
  install -m 0444 infra/launchagents/com.matagaruda.kg-query-api.plist \
    ~/Library/LaunchAgents/
  launchctl load ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Pro-side MCP tool — `kg_intel.py` (P1, P2, P3, P6, P8)

**Files:**

- Create: `apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py`
- Create: `apps/nuzantara-mcp/tests/test_tools_kg_intel.py`

- [ ] **Step 1: Examine existing test pattern**

Run: `cat apps/nuzantara-mcp/tests/test_http_helpers.py | head -50`
Expected: see `httpx.MockTransport` usage. Note: tests for MCP tools expect `register(mcp, _call, _call_safe)` to be invoked against a fake `mcp` that captures registered tools — see if any existing test does that pattern (`test_tools_admin.py`).

Run: `head -80 apps/nuzantara-mcp/tests/test_tools_admin.py`
Expected: shows how a fake MCP captures tool refs. Reuse that pattern.

- [ ] **Step 2: Write the test file**

Create `apps/nuzantara-mcp/tests/test_tools_kg_intel.py`:

```python
"""Tests for kg_intel tool (Bridge A: Pro MCP -> Mini KG)."""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

import httpx
import pytest

from nuzantara_mcp.tools import kg_intel


class _FakeMCP:
    """Minimal stand-in for FastMCP capturing decorated tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Awaitable[Any]]] = {}

    def tool(self):  # noqa: D401
        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self.tools[func.__name__] = func
            return func
        return decorator


@pytest.fixture
def fake_mcp_with_kg(monkeypatch: pytest.MonkeyPatch) -> tuple[_FakeMCP, list[httpx.Request]]:
    """Register kg_intel against a fake MCP, with mocked HTTP transport."""
    captured: list[httpx.Request] = []
    routes: dict[str, tuple[int, dict]] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        path_q = str(request.url.path)
        if request.url.query:
            path_q += "?" + request.url.query.decode("ascii") if isinstance(request.url.query, (bytes, bytearray)) else "?" + str(request.url.query)
        # Direct match against query-less first, then add a wildcard match.
        for key, (status, body) in routes.items():
            if key in path_q:
                return httpx.Response(status, json=body)
        return httpx.Response(500, json={"error": "no_route", "path": path_q})

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(kg_intel, "_TRANSPORT_OVERRIDE", transport, raising=False)
    # Force re-creation of the singleton with the test transport
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)

    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)  # backend client args unused by this tool
    fake.routes = routes  # type: ignore[attr-defined]
    return fake, captured


@pytest.mark.asyncio
async def test_p1_kg_intel_search_returns_results(fake_mcp_with_kg) -> None:
    """P1: search returns dict with 'results' list."""
    fake, _ = fake_mcp_with_kg
    fake.routes["/kg/search"] = (200, {
        "query": "imigrasi", "limit": 20,
        "results": [{"name": "Imigrasi", "type": "organizations", "source_count": 17, "last_seen": "2026-04-30T12:14:09+00:00"}],
    })
    out = await fake.tools["kg_intel_search"]("imigrasi")
    assert isinstance(out, dict)
    assert out["results"][0]["name"] == "Imigrasi"


@pytest.mark.asyncio
async def test_p2_kg_intel_entity(fake_mcp_with_kg) -> None:
    """P2: entity returns parsed entity record."""
    fake, _ = fake_mcp_with_kg
    fake.routes["/kg/entity/"] = (200, {
        "name": "Imigrasi", "type": "organizations", "source_count": 17,
        "first_seen": "2026-03-12T08:11:02+00:00", "last_seen": "2026-04-30T12:14:09+00:00",
        "neighbor_names": [], "observation_count": 0, "observations": [],
    })
    out = await fake.tools["kg_intel_entity"]("Imigrasi", "organizations")
    assert out["name"] == "Imigrasi"
    assert out["type"] == "organizations"


@pytest.mark.asyncio
async def test_p3_kg_intel_health(fake_mcp_with_kg) -> None:
    """P3: health returns counts."""
    fake, _ = fake_mcp_with_kg
    fake.routes["/health"] = (200, {"ok": True, "entities_count": 409, "relations_count": 1549, "observations_count": 622, "schema_ok": True, "kg_path": "/x"})
    out = await fake.tools["kg_intel_health"]()
    assert out["ok"] is True
    assert out["entities_count"] == 409


@pytest.mark.asyncio
async def test_p4_connect_error_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    """P4: ConnectError returns kg_unavailable dict, no raise."""
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Tailscale flap")

    transport = httpx.MockTransport(fail)
    monkeypatch.setattr(kg_intel, "_TRANSPORT_OVERRIDE", transport, raising=False)
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)

    out = await fake.tools["kg_intel_search"]("imigrasi")
    assert out["error"] == "kg_unavailable"


@pytest.mark.asyncio
async def test_p5_timeout_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    """P5: TimeoutException returns kg_unavailable dict."""
    def slow(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    transport = httpx.MockTransport(slow)
    monkeypatch.setattr(kg_intel, "_TRANSPORT_OVERRIDE", transport, raising=False)
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)

    out = await fake.tools["kg_intel_health"]()
    assert out["error"] == "kg_unavailable"


@pytest.mark.asyncio
async def test_p6_404_entity_not_found(fake_mcp_with_kg) -> None:
    """P6: HTTP 404 returns entity_not_found error dict."""
    fake, _ = fake_mcp_with_kg
    fake.routes["/kg/entity/"] = (404, {"error": "entity_not_found", "detail": "no such entity"})
    out = await fake.tools["kg_intel_entity"]("Zaphod", "persons")
    assert out["error"] == "entity_not_found"


def test_p7_register_decorates_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """P7: each registered tool is wrapped with require_role('admin')."""
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)
    for fn in fake.tools.values():
        # require_role attaches __required_role__ marker per nuzantara_mcp/auth.py
        assert getattr(fn, "__required_role__", None) == "admin", (
            f"{fn.__name__} not gated by admin role"
        )


def test_p8_module_importable() -> None:
    """P8: regression: kg_intel module imports successfully."""
    import importlib

    importlib.import_module("nuzantara_mcp.tools.kg_intel")
```

- [ ] **Step 3: Run tests, expect failure**

Run: `cd apps/nuzantara-mcp && source .venv/bin/activate && python -m pytest tests/test_tools_kg_intel.py -v`
Expected: ImportError on `from nuzantara_mcp.tools import kg_intel`.

- [ ] **Step 4: Implement `kg_intel.py`**

Create `apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py`:

```python
"""KG Intelligence Tools — Bridge A: Pro MCP -> Mini mata-garuda KG.

Three tools: kg_intel_search, kg_intel_entity, kg_intel_health.
All admin-gated. Calls Mini via Tailscale (http://100.93.236.6:8990 by
default, override via MATA_GARUDA_KG_BASE_URL). Returns
{"error": "kg_unavailable", ...} on Tailscale flap (NEVER raises).

Doctrine: see apps/mata-garuda/CLAUDE.md §1.4 (Pillar 3 exception).
Spec: docs/superpowers/specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md
"""
from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Any, Optional

import httpx

from nuzantara_mcp.auth import require_role

logger = logging.getLogger("nuzantara-mcp.kg_intel")

KG_BASE_URL = os.getenv("MATA_GARUDA_KG_BASE_URL", "http://100.93.236.6:8990")
KG_TIMEOUT_S = float(os.getenv("MATA_GARUDA_KG_TIMEOUT_S", "3.0"))

# Test seam: tests inject httpx.MockTransport via this attribute.
_TRANSPORT_OVERRIDE: httpx.MockTransport | None = None
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        kwargs: dict[str, Any] = {
            "base_url": KG_BASE_URL,
            "timeout": KG_TIMEOUT_S,
        }
        if _TRANSPORT_OVERRIDE is not None:
            kwargs["transport"] = _TRANSPORT_OVERRIDE
        _client = httpx.AsyncClient(**kwargs)
    return _client


async def _safe_get(path: str) -> dict[str, Any]:
    """GET path, return parsed JSON or graceful error dict."""
    try:
        client = _get_client()
        resp = await client.get(path)
        body: dict[str, Any]
        try:
            body = resp.json()
        except Exception:
            body = {"error": "internal_error", "detail": "non-json body"}
        if resp.status_code >= 400:
            # Surface structured error from Mini if present, else generic
            if "error" not in body:
                body = {"error": "internal_error", "detail": f"HTTP {resp.status_code}"}
            return body
        return body
    except httpx.ConnectError as exc:
        logger.warning("kg-bridge ConnectError: %s", exc)
        return {"error": "kg_unavailable", "detail": "Mata Garuda KG bridge unreachable (Tailscale flap or daemon down)"}
    except (httpx.TimeoutException, httpx.ReadError, httpx.RemoteProtocolError) as exc:
        logger.warning("kg-bridge transport error: %s", exc)
        return {"error": "kg_unavailable", "detail": f"transport error: {type(exc).__name__}"}


def register(mcp, _call, _call_safe):  # noqa: ARG001
    """Register kg_intel_* tools on the MCP server.

    The _call/_call_safe args from server.py are unused — this tool talks
    directly to Mini via Tailscale, not to the Fly backend.
    """

    @mcp.tool()
    @require_role("admin")
    async def kg_intel_search(query: str, limit: int = 20) -> dict:
        """
        Search mata-garuda KG entities by name substring.

        Returns entities whose canonical_name matches `query` case-insensitively.
        Operational metadata only — no OSINT body content.

        Args:
            query: Substring to match (case-insensitive). Empty string -> 400.
            limit: Max results (default 20, hard-capped at 100 server-side).

        Returns:
            {
              "query": str, "limit": int,
              "results": [{"name": str, "type": str, "source_count": int, "last_seen": iso8601}, ...]
            }
            Or {"error": "kg_unavailable" | "bad_request", "detail": str} on failure.

        Citation: when relaying any fact downstream, ALWAYS cite the
        observation.source_url returned by `kg_intel_entity`.
        """
        params = {"q": query, "limit": str(limit)}
        path = "/kg/search?" + urllib.parse.urlencode(params)
        return await _safe_get(path)

    @mcp.tool()
    @require_role("admin")
    async def kg_intel_entity(name: str, entity_type: str) -> dict:
        """
        Fetch full mata-garuda KG record for a named entity.

        Args:
            name: Canonical name (URL-decoded). Required.
            entity_type: One of {persons, organizations, locations, laws, topics}.

        Returns:
            {
              "name": str, "type": str, "source_count": int,
              "first_seen": iso8601, "last_seen": iso8601,
              "neighbor_names": [{"name": str, "type": str, "predicate": str, "confidence": float}, ...],
              "observation_count": int,
              "observations": [{"observed_at": iso8601, "source_url": str}, ...]
            }
            Or {"error": "entity_not_found" | "kg_unavailable" | "bad_request", "detail": str}.

        Citation: cite observation.source_url for every fact relayed.
        """
        encoded = urllib.parse.quote(name, safe="")
        path = f"/kg/entity/{encoded}?type={urllib.parse.quote(entity_type, safe='')}"
        return await _safe_get(path)

    @mcp.tool()
    @require_role("admin")
    async def kg_intel_health() -> dict:
        """
        Check mata-garuda KG bridge health.

        Returns:
            {"ok": bool, "entities_count": int, "relations_count": int,
             "observations_count": int, "schema_ok": bool, "kg_path": str}
            Or {"error": "kg_unavailable", "detail": str} if bridge unreachable.
        """
        return await _safe_get("/health")
```

- [ ] **Step 5: Run tests, expect mostly pass**

Run: `python -m pytest tests/test_tools_kg_intel.py -v`
Expected: P1, P2, P3, P4, P5, P6, P8 pass. P7 may fail because we need to verify how `require_role` records the marker.

- [ ] **Step 6: Verify P7 passes**

Run: `grep -n "__required_role__\|@wraps\|@require_role" apps/nuzantara-mcp/nuzantara_mcp/auth.py | head -20`

If `__required_role__` is set on the wrapper via `setattr` in `auth.py`, P7 passes. If a different attribute name is used (e.g. `_role`, `__role__`), update the test in Step 2 to read the correct attribute.

If `require_role` does NOT attach a marker and only enforces at call-time, change P7 to verify enforcement instead — call the wrapped tool with `AGENT_ROLE` env unset and expect a denial response. Update the test to:

```python
def test_p7_register_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    """P7: each registered tool denies non-admin role."""
    monkeypatch.delenv("AGENT_ROLE", raising=False)
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)
    import asyncio
    for name, fn in fake.tools.items():
        # Default-unknown role should be denied for an admin-only tool.
        result = asyncio.get_event_loop().run_until_complete(fn() if name == "kg_intel_health" else fn("x") if name == "kg_intel_search" else fn("x", "persons"))
        assert isinstance(result, dict) and result.get("error") in {"unauthorized", "forbidden"}, (
            f"{name} did not deny non-admin: {result}"
        )
```

(Pick whichever pattern matches the actual `auth.py` semantics; both are acceptable. The point is to assert the gate exists.)

- [ ] **Step 7: Run all tests**

Run: `python -m pytest tests/test_tools_kg_intel.py -v`
Expected: 8/8 PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py apps/nuzantara-mcp/tests/test_tools_kg_intel.py
git commit -m "$(cat <<'EOF'
feat(nuzantara-mcp): add kg_intel tool (3 tools, role=admin, Tailscale-only)

Three tools (kg_intel_search, kg_intel_entity, kg_intel_health) calling
mata-garuda kg-query API on Mini (http://100.93.236.6:8990) via
httpx.AsyncClient with 3s timeout. Returns
{"error": "kg_unavailable", ...} on flap, never raises.

Citation contract documented in tool docstrings: always cite
observation.source_url when relaying KG facts.

NOT YET wired in nuzantara_mcp/server.py — registration lands in next
commit so this can be cherry-picked / reverted in isolation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Wire `kg_intel` into the MCP server

**Files:**

- Modify: `apps/nuzantara-mcp/nuzantara_mcp/server.py`
- Modify: `apps/nuzantara-mcp/tests/test_server_imports.py` (regression coverage)

- [ ] **Step 1: Add server-imports regression test**

Run: `cat apps/nuzantara-mcp/tests/test_server_imports.py | head -30`

If the file lists registered tool names, add `"kg_intel_search"`, `"kg_intel_entity"`, `"kg_intel_health"` to that list. If it just imports `nuzantara_mcp.server`, add a new test:

```python
def test_kg_intel_registered() -> None:
    """Regression: kg_intel tools are registered on the MCP server."""
    from nuzantara_mcp import server

    # FastMCP exposes a `_tool_manager` or similar — adapt to the actual API.
    # Fallback: check the registration import line is present.
    import inspect

    src = inspect.getsource(server)
    assert "register_kg_intel" in src
    assert "from nuzantara_mcp.tools.kg_intel import register as register_kg_intel" in src
    assert "register_kg_intel(mcp, _call, _call_safe)" in src
```

- [ ] **Step 2: Run, expect failure**

Run: `python -m pytest tests/test_server_imports.py -v -k kg_intel`
Expected: FAIL.

- [ ] **Step 3: Patch `server.py`**

In `apps/nuzantara-mcp/nuzantara_mcp/server.py`, locate the `from nuzantara_mcp.tools.intel import register as register_intel` line (around 132) and add immediately after:

```python
from nuzantara_mcp.tools.kg_intel import register as register_kg_intel
```

Then locate `register_intel(mcp, _call, _call_safe)` (around 177) and add immediately after:

```python
register_kg_intel(mcp, _call, _call_safe)
```

- [ ] **Step 4: Run server-imports test**

Run: `python -m pytest tests/test_server_imports.py -v`
Expected: all PASS.

- [ ] **Step 5: Run full nuzantara-mcp test suite (no regressions)**

Run: `python -m pytest -q`
Expected: same green count as baseline plus our new tests. Note baseline count BEFORE the patch (from a fresh `git stash` + run) — NO drop in green count.

- [ ] **Step 6: Commit**

```bash
git add apps/nuzantara-mcp/nuzantara_mcp/server.py apps/nuzantara-mcp/tests/test_server_imports.py
git commit -m "feat(nuzantara-mcp): wire kg_intel into MCP server registration"
```

---

## Task 11: Documentation runbook + tri-LLM review excerpts

**Files:**

- Create: `docs/symbiosis/W2-kg-bridge-runbook.md`

- [ ] **Step 1: Draft runbook**

Create `docs/symbiosis/W2-kg-bridge-runbook.md`:

````markdown
# SYMBIOSIS W2 — KG Bridge A Operational Runbook

## Install on Mini (one-time)

```bash
ssh nuzantara@100.93.236.6
cd ~/Desktop/nuzantara
git pull origin main

# Install plist (mode 0444 per cicatrix structural-3 plist-tampering hardening)
mkdir -p ~/logs
install -m 0444 infra/launchagents/com.matagaruda.kg-query-api.plist \
  ~/Library/LaunchAgents/

# Load
launchctl load ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
launchctl print gui/$(id -u)/com.matagaruda.kg-query-api | head -30
```
````

Verify daemon up:

```bash
sleep 2
curl -fsS http://100.93.236.6:8990/health | python3 -m json.tool
```

Expected: `{"ok": true, "entities_count": 409, ...}`.

## Verify from Pro

```bash
curl -fsS http://100.93.236.6:8990/health | python3 -m json.tool
curl -fsS "http://100.93.236.6:8990/kg/search?q=imigrasi&limit=5" | python3 -m json.tool
```

## Use the MCP tool

From Claude Code (with kg_intel tools loaded via `nuzantara-mcp` stdio):

```
kg_intel_health()                                       -> bridge state
kg_intel_search("imigrasi", 10)                         -> top 10 matches
kg_intel_entity("Direktorat Jenderal Imigrasi", "organizations")  -> full record
```

## Logs

- `~/logs/mata-garuda-kg-api.log` — request audit (status + path + duration)
- `~/logs/mata-garuda-kg-api.err` — stderr / startup failures

## Restart

```bash
launchctl kickstart -k gui/$(id -u)/com.matagaruda.kg-query-api
```

## Latency benchmark

```bash
# From Pro
python3 ~/Desktop/nuzantara/apps/mata-garuda/scripts/bench_kg_api.py \
  http://100.93.236.6:8990 100 "/kg/search?q=imigrasi"
```

Pass threshold: p99 < 800ms.

## Rollback (Mini)

```bash
launchctl unload ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
chmod u+w ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
rm ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
```

The Pro-side MCP tool will then return `{"error": "kg_unavailable", ...}`
on every call — graceful, no crash. To remove the tool entirely revert
the wiring commit on `apps/nuzantara-mcp/nuzantara_mcp/server.py`.

## Latency benchmark result

(Filled in at deploy time via Task 12.)

## Tri-LLM review

(Filled in at PR-prep time via Task 12.)

````

- [ ] **Step 2: Commit**

```bash
git add docs/symbiosis/W2-kg-bridge-runbook.md
git commit -m "docs(symbiosis): W2 KG-bridge operational runbook (install, verify, rollback)"
````

---

## Task 12: Deploy + benchmark + tri-LLM review (live operations)

**Files (filled-in at runtime):**

- Modify: `docs/symbiosis/W2-kg-bridge-runbook.md` (latency + tri-LLM sections)

This task is **live operations**. It happens after Tasks 1-11 are committed and pushed and **before** opening the PR. It is the equivalent of post-deploy QA but pre-merge.

- [ ] **Step 1: Push branch and verify CI**

```bash
git push -u origin feat/symbiosis-W2-kg-zantara-bridge-2026-05-07
gh run list --branch feat/symbiosis-W2-kg-zantara-bridge-2026-05-07 --limit 5
```

Wait for any required CI checks (PR-check tests, lint, etc.) to be green or non-blocking. Fix red checks before proceeding.

- [ ] **Step 2: Deploy daemon on Mini**

```bash
ssh nuzantara@100.93.236.6 'cd ~/Desktop/nuzantara && git fetch origin && git checkout feat/symbiosis-W2-kg-zantara-bridge-2026-05-07 && cd apps/mata-garuda && .venv/bin/pip install -e . && cd ~/Desktop/nuzantara && install -m 0444 infra/launchagents/com.matagaruda.kg-query-api.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist'
sleep 2
curl -fsS http://100.93.236.6:8990/health
```

Expected: 200 + JSON with counts matching `409/1549/622` (or whatever Mini's KG currently has).

If the daemon does not start, check `~/logs/mata-garuda-kg-api.err` on Mini for traceback. Common causes: venv path wrong (fix bridge script), bind address mismatch (Tailscale IP changed — update plist `KG_API_BIND`), kg.db missing.

- [ ] **Step 3: Run latency benchmark**

```bash
python3 apps/mata-garuda/scripts/bench_kg_api.py \
  http://100.93.236.6:8990 100 "/kg/search?q=imigrasi" \
  | tee /tmp/kg-bench.txt
```

Expected: p99_ms < 800.0. If exceeded, investigate (Mini load? Tailscale latency? cold SQLite cache on first query — re-run.) Re-run until 3 consecutive passes.

Append the output verbatim to `docs/symbiosis/W2-kg-bridge-runbook.md` under "Latency benchmark result".

- [ ] **Step 4: Tri-LLM review**

Three reviews, ≥2/3 explicit approvals required.

**A. DeepSeek R1** (always on):

```bash
git diff origin/main..HEAD -- \
  apps/mata-garuda/mata_garuda/api/ \
  apps/mata-garuda/tests/api/ \
  apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py \
  apps/nuzantara-mcp/tests/test_tools_kg_intel.py \
  > /tmp/w2-diff.patch

# Use the existing project DeepSeek wrapper, e.g.
~/scripts/deepseek-review.sh /tmp/w2-diff.patch \
  "Review this PR for: (1) single point of failure between Mini daemon and Pro tool; \
   (2) information leak — any way OSINT body could escape via this API; \
   (3) race conditions in the async tool path. Be specific; cite file:line." \
  > /tmp/w2-deepseek-review.txt
```

(If `~/scripts/deepseek-review.sh` does not exist, use whatever path the
project canonically uses for DeepSeek API calls. The wrapper budget is
~$0.01.)

**B. NotebookLM NB-1** (if MCP available):

```bash
# Check if mcp__notebooklm-mcp__notebook_query is exposed in this session
# If yes, query NB-1 with the diff context for backend-rag MCP architecture
# alignment. If not loaded in this session, skip and note in PR body.
```

**C. Codex / Gemini** (opportunistic):

```bash
# Codex (if quota free)
codex exec --sandbox read-only \
  "Review the diff at /tmp/w2-diff.patch — focus on unhandled exceptions \
   and the test seam (_TRANSPORT_OVERRIDE)." || echo "Codex quota likely hit — skip"

# Gemini (if quota free)
gemini -m gemini-3.1-pro-preview --sandbox -p \
  "Review /tmp/w2-diff.patch for race conditions in async path between \
   Mini http.server (threading) and Pro httpx.AsyncClient." \
  || echo "Gemini quota likely hit — skip"
```

Append all reviewer outputs (or quota-exhausted notes) to
`docs/symbiosis/W2-kg-bridge-runbook.md` under "Tri-LLM review".

For each substantive concern: either fix it in a follow-up commit on the
branch, or add a "Deferred" line in the runbook with the reason.

Threshold: ≥2/3 explicit approvals (DeepSeek + NB-1 minimum, or DeepSeek

- one of Codex/Gemini if NB-1 unavailable).

* [ ] **Step 5: Commit review excerpts + bench result**

```bash
git add docs/symbiosis/W2-kg-bridge-runbook.md
git commit -m "docs(symbiosis): W2 latency benchmark + tri-LLM review excerpts"
git push
```

- [ ] **Step 6: Open PR**

```bash
gh pr create \
  --title "feat(symbiosis): KG → Pro MCP tool (Bridge A, Pillar 3 doctrine)" \
  --body "$(cat <<'EOF'
## Summary

- Bridge A: mata-garuda KG SQLite (Mini, 409e/1549r/622o) exposed as
  Pro-side MCP tool via Tailscale-only HTTP.
- 3 tools: `kg_intel_search`, `kg_intel_entity`, `kg_intel_health`.
- Doctrine exception §1.4 added to `apps/mata-garuda/CLAUDE.md` (commit 1).
- No OSINT body fields in any payload — `observation.value`,
  `evidence_url`, `aliases_json`, content/title/body all forbidden
  (T9 deep-walk test enforces).

Bridge B (Fly→Mini for end-user Zantara) explicitly **out of scope** —
future separate PR.

## Test coverage

- Mini-side: 12/12 (T1-T12) — bind guardrail, fail-soft schema,
  search, entity, forbidden-fields walk, concurrency, path traversal.
- Pro-side: 8/8 (P1-P8) — happy path, ConnectError, Timeout, 404,
  admin gate, server-imports regression.

## Latency benchmark (Pro→Mini via Tailscale, 100 calls /kg/search)

(Insert /tmp/kg-bench.txt content)

## Tri-LLM review

(Insert outputs from `docs/symbiosis/W2-kg-bridge-runbook.md`)

## Security checklist

- [x] Mini server refuses `0.0.0.0` bind (T10)
- [x] No OSINT body fields in any response (T9 deep-walk)
- [x] Tool returns graceful degradation dict on flap, never raises (P4/P5)
- [x] Tool decorated `@require_role("admin")` (P7)
- [x] Plist file mode 0444
- [x] Daemon log audits path+status only, NEVER body
- [x] Path traversal rejected (T12)
- [x] kg.db opened read-only (`mode=ro` URI)
- [x] Tailscale auth = sole network gate

## E2E demo

```

$ kg_intel_search("imigrasi", 5)
{"query": "imigrasi", "limit": 5, "results": [{"name": "...", ...}]}

```

(Replace with real captured output from Pro after deploy.)

## Doctrine commit

Commit 1 lands the §1.4 exception verbatim BEFORE any code commit, so
the legitimacy precedes the export-shaped code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 7: Update task list**

```bash
git push
echo "PR opened. Pending Zero approval + ≥2/3 LLM approvals before merge."
```

---

## Self-Review Checklist (run before handing back)

- [ ] Spec coverage: every section in the design spec has a corresponding task above. Doctrine (Task 1), Mini API (Tasks 2-6), bench (7), plist (8), MCP tool (9), wiring (10), runbook (11), live ops (12). ✅
- [ ] Placeholder scan: no "TBD", "TODO", "implement later" in plan body — only "(Filled in at deploy time via Task 12)" in the runbook itself, which is correct (those are runtime-filled artifacts, not plan placeholders). ✅
- [ ] Type consistency: `KGServer = _ConfiguredServer` exported in Task 2 Step 4 and used in Task 2 Step 2 fixture; `_TRANSPORT_OVERRIDE` referenced in Task 9 tests + implementation; tool names `kg_intel_search`/`kg_intel_entity`/`kg_intel_health` consistent across Tasks 9-10-runbook. ✅
- [ ] Doctrine first: Task 1 lands BEFORE any code commits (Tasks 2-10). ✅
- [ ] No raise-on-flap: Task 9 implementation explicitly catches ConnectError/Timeout and returns `{"error": "kg_unavailable", ...}` (P4/P5 enforce). ✅

---

## Execution Handoff

**Plan complete and committed to branch.** Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch with checkpoints.

**Which approach?**
