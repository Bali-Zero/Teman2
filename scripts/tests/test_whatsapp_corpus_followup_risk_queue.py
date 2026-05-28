from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_followup_risk_queue.py"


def _load_followup_queue() -> ModuleType:
    spec = importlib.util.spec_from_file_location("followup_risk_queue", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_allowed_messages_fixture(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_raw TEXT,
                sender_hash TEXT,
                direction TEXT,
                is_system_event INTEGER NOT NULL,
                body_text TEXT NOT NULL,
                body_char_count INTEGER NOT NULL,
                body_line_count INTEGER NOT NULL,
                has_url INTEGER NOT NULL,
                has_email INTEGER NOT NULL,
                has_phone_like INTEGER NOT NULL,
                has_media_omitted INTEGER NOT NULL,
                PRIMARY KEY (file_id, message_index)
            )
            """
        )
        rows = [
            (
                "file_a",
                "02_zip-extracted",
                "tag-alpha",
                "path-hash-a",
                1,
                "2026-05-01T08:00:00+00:00",
                "DO_NOT_READ_NAME_A",
                "sender-client",
                None,
                0,
                "Could you update us? DO_NOT_READ_BODY_A +621234 secret@example.com",
                66,
                1,
                0,
                0,
                1,
                0,
            ),
            (
                "file_a",
                "02_zip-extracted",
                "tag-alpha",
                "path-hash-a",
                2,
                "2026-05-01T12:00:00+00:00",
                "DO_NOT_READ_NAME_A",
                "sender-client",
                None,
                0,
                "Reminder, still waiting for the status.",
                39,
                1,
                0,
                0,
                0,
                0,
            ),
            (
                "file_a",
                "02_zip-extracted",
                "tag-alpha",
                "path-hash-a",
                3,
                "2026-05-01T13:00:00+00:00",
                "DO_NOT_READ_NAME_A",
                "sender-client",
                None,
                0,
                "Urgent problem, deadline tomorrow.",
                35,
                1,
                0,
                0,
                0,
                0,
            ),
            (
                "file_a",
                "02_zip-extracted",
                "tag-alpha",
                "path-hash-a",
                4,
                "2026-05-03T10:00:00+00:00",
                "DO_NOT_READ_NAME_B",
                "sender-team",
                None,
                0,
                "Received.",
                9,
                1,
                0,
                0,
                0,
                0,
            ),
            (
                "file_b",
                "02_zip-extracted",
                "tag-beta",
                "path-hash-b",
                1,
                "2026-05-02T08:00:00+00:00",
                "DO_NOT_READ_NAME_C",
                "sender-other",
                None,
                0,
                "Please send status when possible.",
                33,
                1,
                0,
                0,
                0,
                0,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, source, source_tag, path_hash, message_index, timestamp,
                sender_raw, sender_hash, direction, is_system_event, body_text,
                body_char_count, body_line_count, has_url, has_email,
                has_phone_like, has_media_omitted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _create_signal_hits_fixture(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE signal_hits (
                file_id TEXT NOT NULL,
                source_tag TEXT,
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
                (
                    "file_a",
                    "tag-alpha",
                    1,
                    "2026-05-01T08:00:00+00:00",
                    "scheduling_followup",
                ),
                (
                    "file_a",
                    "tag-alpha",
                    2,
                    "2026-05-01T12:00:00+00:00",
                    "scheduling_followup",
                ),
                ("file_a", "tag-alpha", 3, "2026-05-01T13:00:00+00:00", "urgency_risk"),
                (
                    "file_b",
                    "tag-beta",
                    1,
                    "2026-05-02T08:00:00+00:00",
                    "scheduling_followup",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _create_temporal_fixture(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO metadata (key, value) VALUES ('total_messages', '5')")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def synthetic_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    messages_db = tmp_path / "allowed_messages.local.sqlite"
    signal_db = tmp_path / "allowed_signal_hits.local.sqlite"
    temporal_db = tmp_path / "allowed_temporal.local.sqlite"
    _create_allowed_messages_fixture(messages_db)
    _create_signal_hits_fixture(signal_db)
    _create_temporal_fixture(temporal_db)
    return messages_db, signal_db, temporal_db


def _fetch_one(db_path: Path, query: str, params: tuple[object, ...]) -> sqlite3.Row:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(query, params).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


def test_cli_writes_followup_risk_queue_and_summary(
    synthetic_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    messages_db, signal_db, temporal_db = synthetic_inputs
    output_db = tmp_path / "allowed_followup_risk.local.sqlite"
    summary = tmp_path / "allowed_followup_risk_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--messages-db",
            str(messages_db),
            "--signal-db",
            str(signal_db),
            "--temporal-db",
            str(temporal_db),
            "--output-db",
            str(output_db),
            "--summary",
            str(summary),
            "--threshold-hours",
            "24",
            "--repeat-window-hours",
            "72",
            "--summary-limit",
            "20",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["message_count"] == 5
    assert payload["signal_hit_count"] == 4
    assert payload["queue_message_count"] == 4
    assert output_db.exists()
    assert summary.exists()

    unanswered = _fetch_one(
        output_db,
        """
        SELECT queue_message_count, file_count, high_severity_count
        FROM reason_counts
        WHERE reason_code = ?
        """,
        ("unanswered_later_than_threshold",),
    )
    assert dict(unanswered) == {
        "queue_message_count": 4,
        "file_count": 2,
        "high_severity_count": 4,
    }

    repeated = _fetch_one(
        output_db,
        """
        SELECT queue_message_count, file_count
        FROM reason_counts
        WHERE reason_code = ?
        """,
        ("repeated_request_thread",),
    )
    assert dict(repeated) == {"queue_message_count": 2, "file_count": 1}

    high = _fetch_one(
        output_db,
        "SELECT queue_message_count FROM severity_counts WHERE severity = ?",
        ("high",),
    )
    assert high["queue_message_count"] == 4

    file_a = _fetch_one(
        output_db,
        """
        SELECT queue_message_count, high_severity_count, distinct_reason_count
        FROM file_counts
        WHERE file_id = ?
        """,
        ("file_a",),
    )
    assert dict(file_a) == {
        "queue_message_count": 3,
        "high_severity_count": 3,
        "distinct_reason_count": 8,
    }

    summary_text = summary.read_text(encoding="utf-8")
    assert "# WhatsApp Follow-Up Risk Queue Summary" in summary_text
    assert "unanswered_later_than_threshold" in summary_text
    assert "repeated_request_thread" in summary_text
    assert "DO_NOT_READ" not in summary_text
    assert "+62" not in summary_text
    assert "secret@example.com" not in summary_text
    assert "path-hash" not in summary_text


def test_input_filename_guards_reject_non_allowlisted_names(tmp_path: Path) -> None:
    module = _load_followup_queue()
    messages_db = tmp_path / "not_allowed_messages.local.sqlite"
    signal_db = tmp_path / "allowed_signal_hits.local.sqlite"
    temporal_db = tmp_path / "allowed_temporal.local.sqlite"
    messages_db.write_bytes(b"")
    _create_signal_hits_fixture(signal_db)
    _create_temporal_fixture(temporal_db)

    with pytest.raises(ValueError, match="Refusing to read"):
        module.run_analysis(
            messages_db=messages_db,
            signal_db=signal_db,
            temporal_db=temporal_db,
            output_db=tmp_path / "allowed_followup_risk.local.sqlite",
            summary_path=tmp_path / "allowed_followup_risk_summary.md",
            threshold_hours=24,
            repeat_window_hours=72,
            summary_limit=10,
            generated_at_utc="2026-05-05T08:00:00+00:00",
        )


def test_builder_uses_generated_time_for_open_unanswered_requests(
    synthetic_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    module = _load_followup_queue()
    messages_db, signal_db, temporal_db = synthetic_inputs

    artifacts = module.run_analysis(
        messages_db=messages_db,
        signal_db=signal_db,
        temporal_db=temporal_db,
        output_db=tmp_path / "allowed_followup_risk.local.sqlite",
        summary_path=tmp_path / "allowed_followup_risk_summary.md",
        threshold_hours=24,
        repeat_window_hours=72,
        summary_limit=10,
        generated_at_utc="2026-05-05T08:00:00+00:00",
    )

    file_b_items = [item for item in artifacts.queue_items if item.file_id == "file_b"]
    assert len(file_b_items) == 1
    assert file_b_items[0].response_gap_hours == pytest.approx(72.0)
    assert file_b_items[0].severity == "high"
