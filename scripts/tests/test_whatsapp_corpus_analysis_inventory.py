from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from scripts.whatsapp_corpus.build_analysis_inventory import (
    FORBIDDEN_COLUMNS,
    build_inventory,
    inspect_sqlite_artifact,
    write_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_analysis_inventory.py"


def _create_fixture_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                body_text TEXT,
                sender_raw TEXT,
                local_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE aggregate_counts (
                bucket TEXT NOT NULL,
                count_value INTEGER NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO parsed_messages
                (file_id, message_index, body_text, sender_raw, local_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("file-a", 1, "DO_NOT_READ_BODY_ALPHA", "DO_NOT_READ_SENDER_ALPHA", "/raw/a"),
                ("file-a", 2, "DO_NOT_READ_BODY_BETA", "DO_NOT_READ_SENDER_BETA", "/raw/b"),
            ],
        )
        conn.executemany(
            "INSERT INTO aggregate_counts (bucket, count_value) VALUES (?, ?)",
            [("x", 1), ("y", 2), ("z", 3)],
        )
        conn.commit()
    finally:
        conn.close()


def test_inspect_sqlite_artifact_counts_tables_without_private_reads(tmp_path: Path) -> None:
    db_path = tmp_path / "allowed_messages.local.sqlite"
    _create_fixture_db(db_path)

    artifact = inspect_sqlite_artifact(db_path)

    assert artifact.artifact_name == "allowed_messages.local.sqlite"
    assert artifact.status == "ok"
    assert artifact.total_rows == 5
    assert {table.table_name: table.row_count for table in artifact.table_counts} == {
        "aggregate_counts": 3,
        "parsed_messages": 2,
    }
    assert FORBIDDEN_COLUMNS == {"body_text", "sender_raw", "local_path"}


def test_write_summary_omits_raw_fixture_values(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    _create_fixture_db(analysis_dir / "allowed_messages.local.sqlite")
    (analysis_dir / "allowed_messages_summary.md").write_text(
        "# Allowed Messages\n\nDO_NOT_READ_BODY_SHOULD_STAY_OUT\n",
        encoding="utf-8",
    )

    inventory = build_inventory(analysis_dir)
    summary_path = analysis_dir / "analysis_inventory_summary.md"
    write_summary(
        inventory=inventory,
        summary_path=summary_path,
        generated_at_utc="2026-05-26T00:00:00+00:00",
    )

    summary = summary_path.read_text(encoding="utf-8")
    assert "# WhatsApp Analysis Inventory Summary" in summary
    assert "| allowed_messages.local.sqlite | ok | 2 | 5 |" in summary
    assert "Allowed Messages" in summary
    assert "DO_NOT_READ_BODY" not in summary
    assert "DO_NOT_READ_SENDER" not in summary
    assert "/raw/" not in summary


def test_cli_writes_summary_and_json(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    _create_fixture_db(analysis_dir / "allowed_messages.local.sqlite")
    summary_path = analysis_dir / "analysis_inventory_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--analysis-dir",
            str(analysis_dir),
            "--summary",
            str(summary_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert summary_path.exists()
    assert '"sqlite_count": 1' in result.stdout
    assert "DO_NOT_READ_BODY" not in result.stdout
