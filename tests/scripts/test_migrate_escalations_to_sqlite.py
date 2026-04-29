"""Tests for scripts/migrate_escalations_to_sqlite.py (P1-8).

Covers:
1. Import creates table + indexes.
2. Idempotent import (rerun = no duplicate rows).
3. Zero data loss (line count == row count for unique rows).
4. Prune deletes only resolved rows older than threshold.
5. Archive exports unresolved rows older than threshold to gzip JSONL.
6. Writer dual-writes to SQLite when env toggle is on.

All tests use tmp_path. No real ~/.agent/ writes.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Module loader (script lives at scripts/migrate_escalations_to_sqlite.py and
# is not on sys.path by default).
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "migrate_escalations_to_sqlite.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "migrate_escalations_to_sqlite", str(SCRIPT_PATH)
    )
    assert spec and spec.loader, f"could not load {SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def migrate():
    return _load_module()


@pytest.fixture
def sample_jsonl(tmp_path: Path) -> Path:
    """Three rows mirroring real shapes from shared/escalations_pro.jsonl."""
    rows = [
        {
            "job": "compliance_ops",
            "type": "dlq_autopilot_escalation",
            "error_summary": "OpenClaw consecutiveErrors=8",
            "priority": "HIGH",
            "task_file": "compliance_ops_1.json",
            "machine": "pro",
            "ts": 1775757354.478498,
            "status": "pending",
            "_writer": "pro",
        },
        {
            "job": "biz_orchestrator",
            "type": "dlq_autopilot_escalation",
            "error_summary": "",
            "priority": "NORMAL",
            "task_file": "biz_orchestrator_2.json",
            "machine": "pro",
            "ts": 1775757355.7944782,
            "status": "pending",
            "_writer": "pro",
        },
        {
            # Air row with audit_id
            "job": "air-a1-auth-surface",
            "type": "zero_decision",
            "priority": "HIGH",
            "ts": 1776457007,
            "machine": "air",
            "status": "pending",
            "_writer": "air",
            "audit_id": "2026-04-18-HIGH-5",
        },
    ]
    p = tmp_path / "escalations_pro.jsonl"
    with p.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


# ---------------------------------------------------------------------------
# Test 1 — schema + indexes
# ---------------------------------------------------------------------------
def test_import_creates_table_and_indexes(migrate, sample_jsonl, tmp_path):
    db = tmp_path / "escalations.sqlite"
    n = migrate.import_jsonl(sources=[sample_jsonl], db_path=db)
    assert n == 3

    conn = sqlite3.connect(str(db))
    try:
        # Table exists
        names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "escalations" in names

        # Required columns
        cols = {row[1] for row in conn.execute("PRAGMA table_info(escalations)").fetchall()}
        for required in (
            "id", "dedup_key", "audit_id", "job", "type", "severity",
            "machine", "error_summary", "task_file", "ts", "status",
            "resolved_at", "raw_json", "imported_at",
        ):
            assert required in cols, f"missing column: {required}"

        # Indexes (4 expected — including the active-only partial index)
        idx_names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='escalations' AND name NOT LIKE 'sqlite_autoindex%'"
        ).fetchall()}
        for required in (
            "idx_escalations_active",
            "idx_escalations_machine",
            "idx_escalations_ts",
            "idx_escalations_job_ts",
        ):
            assert required in idx_names, f"missing index: {required}"

        # WAL mode
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 2 — idempotent rerun
# ---------------------------------------------------------------------------
def test_import_no_duplicates_on_rerun(migrate, sample_jsonl, tmp_path):
    db = tmp_path / "escalations.sqlite"
    first = migrate.import_jsonl(sources=[sample_jsonl], db_path=db)
    second = migrate.import_jsonl(sources=[sample_jsonl], db_path=db)
    assert first == 3
    # Second run inserts 0 new rows (all dedup_keys already present).
    assert second == 0

    conn = sqlite3.connect(str(db))
    try:
        total = conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0]
        assert total == 3
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 3 — zero data loss
# ---------------------------------------------------------------------------
def test_import_preserves_all_jsonl_rows(migrate, tmp_path):
    src = tmp_path / "many.jsonl"
    n_rows = 100
    with src.open("w") as f:
        for i in range(n_rows):
            f.write(json.dumps({
                "job": f"job_{i}",
                "type": "dlq_autopilot_escalation",
                "priority": "NORMAL",
                "machine": "pro",
                "ts": 1700000000 + i,
                "status": "pending",
                "_writer": "pro",
            }) + "\n")

    db = tmp_path / "escalations.sqlite"
    inserted = migrate.import_jsonl(sources=[src], db_path=db)
    assert inserted == n_rows

    # Line count == row count
    line_count = sum(1 for _ in src.open())
    conn = sqlite3.connect(str(db))
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0]
    finally:
        conn.close()
    assert row_count == line_count == n_rows


# ---------------------------------------------------------------------------
# Test 4 — prune
# ---------------------------------------------------------------------------
def test_prune_resolved_older_than_30d(migrate, tmp_path):
    db = tmp_path / "escalations.sqlite"
    migrate.ensure_schema(db)
    now = time.time()

    rows = [
        # 3 resolved >30d → should be pruned
        {"job": "j1", "machine": "pro", "ts": now - 100 * 86400,
         "status": "resolved", "resolved_at": now - 40 * 86400, "audit_id": "a1"},
        {"job": "j2", "machine": "pro", "ts": now - 100 * 86400,
         "status": "resolved", "resolved_at": now - 35 * 86400, "audit_id": "a2"},
        {"job": "j3", "machine": "pro", "ts": now - 100 * 86400,
         "status": "resolved", "resolved_at": now - 31 * 86400, "audit_id": "a3"},
        # 1 resolved <30d → keep
        {"job": "j4", "machine": "pro", "ts": now - 100 * 86400,
         "status": "resolved", "resolved_at": now - 5 * 86400, "audit_id": "a4"},
        # 1 unresolved → keep
        {"job": "j5", "machine": "pro", "ts": now - 100 * 86400,
         "status": "pending", "audit_id": "a5"},
    ]
    conn = sqlite3.connect(str(db))
    try:
        for r in rows:
            migrate._insert_row(conn, r, json.dumps(r))
        conn.commit()
    finally:
        conn.close()

    deleted = migrate.prune(db_path=db, older_than_days=30)
    assert deleted == 3

    conn = sqlite3.connect(str(db))
    try:
        remaining = conn.execute("SELECT job FROM escalations ORDER BY job").fetchall()
        assert [r[0] for r in remaining] == ["j4", "j5"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 5 — archive
# ---------------------------------------------------------------------------
def test_archive_unresolved_older_than_90d(migrate, tmp_path):
    db = tmp_path / "escalations.sqlite"
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    migrate.ensure_schema(db)
    now = time.time()

    rows = [
        # 2 unresolved >90d → archive + delete
        {"job": "old1", "machine": "pro", "ts": now - 100 * 86400,
         "status": "pending", "audit_id": "old1"},
        {"job": "old2", "machine": "air", "ts": now - 91 * 86400,
         "status": "pending", "audit_id": "old2"},
        # 1 fresh → keep
        {"job": "fresh", "machine": "pro", "ts": now - 1 * 86400,
         "status": "pending", "audit_id": "fresh"},
    ]
    conn = sqlite3.connect(str(db))
    try:
        for r in rows:
            migrate._insert_row(conn, r, json.dumps(r))
        conn.commit()
    finally:
        conn.close()

    archived_path = migrate.archive(
        db_path=db, older_than_days=90, archive_dir=archive_dir
    )
    assert archived_path is not None
    assert archived_path.exists()
    assert archived_path.suffixes[-2:] == [".jsonl", ".gz"]

    # 2 rows in gzip file
    with gzip.open(archived_path, "rt") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert len(lines) == 2
    assert {r["job"] for r in lines} == {"old1", "old2"}

    # DB now has only the fresh row
    conn = sqlite3.connect(str(db))
    try:
        remaining = conn.execute("SELECT job FROM escalations").fetchall()
        assert [r[0] for r in remaining] == ["fresh"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 6 — writer dual-writes
# ---------------------------------------------------------------------------
def test_writer_dual_writes_to_sqlite(migrate, tmp_path, monkeypatch):
    """When ESCALATIONS_USE_SQLITE=true, the JSONL writer also INSERTs into SQLite.

    We import scripts/sentinel_lib/escalations.py from the project (NOT through
    the migrate module — we exercise the real writer with patched paths).
    """
    # Make sentinel_lib importable.
    scripts_dir = PROJECT_ROOT / "scripts"
    monkeypatch.syspath_prepend(str(scripts_dir))

    # Point JSONL output at tmp_path (per-machine writer picks file by hostname).
    import sentinel_lib.escalations as escalations_mod
    importlib_reload = __import__("importlib").reload
    # Keep a fresh module load so we can patch the constants.
    escalations_mod = importlib_reload(escalations_mod)

    fake_jsonl = tmp_path / "escalations_pro.jsonl"
    fake_db = tmp_path / "escalations.sqlite"

    # Patch the per-machine map and DB resolver. (current_machine returns 'pro'
    # on the dev workstation; if not, force it.)
    monkeypatch.setattr(
        escalations_mod, "_MACHINE_FILES", {"pro": fake_jsonl, "air": fake_jsonl}
    )
    monkeypatch.setattr(escalations_mod, "_current_machine", lambda: "pro")
    monkeypatch.setenv("ESCALATIONS_USE_SQLITE", "true")
    monkeypatch.setenv("ESCALATIONS_SQLITE_PATH", str(fake_db))

    escalations_mod.write_escalation({
        "job": "writer_dual_test",
        "type": "dlq_autopilot_escalation",
        "audit_id": "writer-1",
        "priority": "HIGH",
    })

    # JSONL got the line.
    assert fake_jsonl.exists()
    lines = [json.loads(line) for line in fake_jsonl.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["job"] == "writer_dual_test"
    assert lines[0]["audit_id"] == "writer-1"

    # SQLite got the row with matching dedup_key.
    assert fake_db.exists()
    conn = sqlite3.connect(str(fake_db))
    try:
        rows = conn.execute(
            "SELECT job, audit_id, dedup_key FROM escalations"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "writer_dual_test"
        assert rows[0][1] == "writer-1"
        assert rows[0][2] == "audit:writer-1|pro"
    finally:
        conn.close()
