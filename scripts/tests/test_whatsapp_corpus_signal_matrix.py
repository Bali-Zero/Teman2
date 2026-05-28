from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "analyze_allowed_signal_matrix.py"


def _load_signal_matrix() -> ModuleType:
    spec = importlib.util.spec_from_file_location("allowed_signal_matrix", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synthetic_signal_hits_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "allowed_signal_hits.local.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE signal_hits (
                file_id TEXT NOT NULL,
                source_tag TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                signal_code TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO signal_hits
                (file_id, source_tag, message_index, timestamp, signal_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("file_a", "group", 1, "2026-05-01T10:00:00+00:00", "lead_intent"),
                ("file_a", "group", 1, "2026-05-01T10:00:00+00:00", "pricing"),
                ("file_a", "group", 2, "2026-05-02T10:00:00+00:00", "pricing"),
                ("file_a", "group", 5, "2026-06-01T10:00:00+00:00", "kbli"),
                ("file_b", "direct", 3, "2026-05-03T10:00:00+00:00", "lead_intent"),
                ("file_b", "direct", 3, "2026-05-03T10:00:00+00:00", "pricing"),
                ("file_b", "direct", 4, None, "pricing"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _fetch_one(db_path: Path, query: str, params: tuple[object, ...]) -> sqlite3.Row:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(query, params).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


def test_cli_writes_matrix_db_and_summary(synthetic_signal_hits_db: Path, tmp_path: Path) -> None:
    output_db = tmp_path / "allowed_signal_matrix.local.sqlite"
    summary = tmp_path / "allowed_signal_matrix_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(synthetic_signal_hits_db),
            "--output-db",
            str(output_db),
            "--summary",
            str(summary),
            "--summary-limit",
            "10",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_db.exists()
    assert summary.exists()
    assert '"hit_count": 7' in result.stdout

    pricing_group = _fetch_one(
        output_db,
        """
        SELECT hit_count, file_count, message_count
        FROM signal_source_matrix
        WHERE signal_code = ? AND source_tag = ?
        """,
        ("pricing", "group"),
    )
    assert dict(pricing_group) == {"hit_count": 2, "file_count": 1, "message_count": 2}

    pricing_unknown_month = _fetch_one(
        output_db,
        """
        SELECT hit_count, file_count, message_count
        FROM signal_month_matrix
        WHERE signal_code = ? AND month = ?
        """,
        ("pricing", "unknown"),
    )
    assert dict(pricing_unknown_month) == {
        "hit_count": 1,
        "file_count": 1,
        "message_count": 1,
    }

    file_a_density = _fetch_one(
        output_db,
        """
        SELECT total_hits, hit_message_count, message_span, unique_signal_count,
               hits_per_hit_message, hits_per_message_span
        FROM file_signal_density
        WHERE file_id = ?
        """,
        ("file_a",),
    )
    assert file_a_density["total_hits"] == 4
    assert file_a_density["hit_message_count"] == 3
    assert file_a_density["message_span"] == 5
    assert file_a_density["unique_signal_count"] == 3
    assert file_a_density["hits_per_hit_message"] == pytest.approx(1.333333)
    assert file_a_density["hits_per_message_span"] == pytest.approx(0.8)

    cooccurrence = _fetch_one(
        output_db,
        """
        SELECT message_count, file_count
        FROM signal_cooccurrence
        WHERE signal_code_a = ? AND signal_code_b = ?
        """,
        ("lead_intent", "pricing"),
    )
    assert dict(cooccurrence) == {"message_count": 2, "file_count": 2}

    summary_text = summary.read_text(encoding="utf-8")
    assert "# Allowed Signal Matrix Summary" in summary_text
    assert "## Signal x Source Tag" in summary_text
    assert "## Signal Co-Occurrence" in summary_text
    assert "lead_intent" in summary_text
    assert "pricing" in summary_text


def test_input_filename_guard_rejects_non_allowlisted_sqlite(tmp_path: Path) -> None:
    module = _load_signal_matrix()
    blocked_db = tmp_path / "not_allowed.local.sqlite"
    blocked_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read"):
        module.run_analysis(
            input_db=blocked_db,
            output_db=tmp_path / "allowed_signal_matrix.local.sqlite",
            summary_path=tmp_path / "allowed_signal_matrix_summary.md",
            summary_limit=10,
            generated_at_utc="2026-05-26T00:00:00+00:00",
        )


def test_artifact_builder_deduplicates_cooccurrence_per_message() -> None:
    module = _load_signal_matrix()
    hits = [
        module.SignalHit("file_a", "group", 1, "2026-05-01T00:00:00+00:00", "2026-05", "a"),
        module.SignalHit("file_a", "group", 1, "2026-05-01T00:00:00+00:00", "2026-05", "a"),
        module.SignalHit("file_a", "group", 1, "2026-05-01T00:00:00+00:00", "2026-05", "b"),
    ]

    artifacts = module.build_artifacts(hits)

    assert artifacts.signal_cooccurrence == [
        {
            "signal_code_a": "a",
            "signal_code_b": "b",
            "message_count": 1,
            "file_count": 1,
        }
    ]
    assert artifacts.signal_totals[0]["signal_code"] == "a"
    assert artifacts.signal_totals[0]["hit_count"] == 2
