"""Tests for mata_garuda.api.kg_query (stdlib HTTP API for KG metadata)."""
from __future__ import annotations

import http.client
import json
import sqlite3
import threading
import time
import urllib.parse
from collections.abc import Generator
from pathlib import Path
from typing import Any

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
def running_server(kg_db_seeded: Path) -> Generator[int, None, None]:
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


def test_t10_refuses_wildcard_bind(tmp_path: Path) -> None:
    """T10: server refuses 0.0.0.0 bind at startup."""
    db = tmp_path / "kg.db"
    db.touch()
    with pytest.raises(RuntimeError, match="wildcard"):
        kg_query.build_server(bind="0.0.0.0", port=0, db_path=db)
    with pytest.raises(RuntimeError, match="wildcard"):
        kg_query.build_server(bind="::", port=0, db_path=db)


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


def test_t7b_entity_unknown_type_400(running_server: int) -> None:
    """T7b: type value not in ENTITY_TYPES also returns 400."""
    status, body = _get(running_server, "/kg/entity/Imigrasi?type=robots")
    assert status == 400
    assert body["error"] == "bad_request"


def test_t8_entity_unknown_404(running_server: int) -> None:
    """T8: unknown entity returns 404 entity_not_found."""
    status, body = _get(running_server, "/kg/entity/Zaphod?type=persons")
    assert status == 404
    assert body["error"] == "entity_not_found"
