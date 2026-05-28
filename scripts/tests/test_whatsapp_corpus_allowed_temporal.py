from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.analyze_allowed_temporal import (
    FORBIDDEN_COLUMNS,
    analyze_allowed_temporal,
    build_safe_select_sql,
)


def _create_allowed_messages_fixture(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE allowed_messages (
                file_id TEXT NOT NULL,
                source_tag TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                sender_hash TEXT NOT NULL,
                direction TEXT NOT NULL,
                is_system_event INTEGER NOT NULL,
                body_char_count INTEGER NOT NULL,
                has_attachment INTEGER NOT NULL,
                feature_follow_up INTEGER NOT NULL,
                is_response_gap INTEGER NOT NULL,
                body_text TEXT,
                sender_raw TEXT,
                local_path TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO allowed_messages (
                file_id,
                source_tag,
                message_index,
                timestamp,
                sender_hash,
                direction,
                is_system_event,
                body_char_count,
                has_attachment,
                feature_follow_up,
                is_response_gap,
                body_text,
                sender_raw,
                local_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "file-a",
                    "export-alpha",
                    0,
                    "2024-01-01T00:15:00",
                    "hash-a",
                    "inbound",
                    0,
                    10,
                    1,
                    0,
                    0,
                    "DO_NOT_READ_BODY_ALPHA",
                    "DO_NOT_READ_SENDER_ALPHA",
                    "/do/not/read/alpha.txt",
                ),
                (
                    "file-a",
                    "export-alpha",
                    1,
                    "2024-01-01T13:00:00",
                    "hash-b",
                    "outbound",
                    1,
                    20,
                    0,
                    1,
                    1,
                    "DO_NOT_READ_BODY_BETA",
                    "DO_NOT_READ_SENDER_BETA",
                    "/do/not/read/beta.txt",
                ),
                (
                    "file-b",
                    "export-beta",
                    0,
                    "2024-01-02T13:30:00",
                    "hash-c",
                    "inbound",
                    0,
                    30,
                    1,
                    1,
                    1,
                    "DO_NOT_READ_BODY_GAMMA",
                    "DO_NOT_READ_SENDER_GAMMA",
                    "/do/not/read/gamma.txt",
                ),
                (
                    "file-c",
                    "export-beta",
                    0,
                    "2024-02-03T23:45:00",
                    "hash-d",
                    "inbound",
                    0,
                    40,
                    0,
                    1,
                    0,
                    "DO_NOT_READ_BODY_DELTA",
                    "DO_NOT_READ_SENDER_DELTA",
                    "/do/not/read/delta.txt",
                ),
                (
                    "file-a",
                    "export-alpha",
                    2,
                    "2025-01-04T07:00:00",
                    "hash-e",
                    "outbound",
                    0,
                    50,
                    0,
                    0,
                    0,
                    "DO_NOT_READ_BODY_EPSILON",
                    "DO_NOT_READ_SENDER_EPSILON",
                    "/do/not/read/epsilon.txt",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_build_safe_select_sql_excludes_forbidden_columns() -> None:
    available_columns = (
        "file_id",
        "source_tag",
        "message_index",
        "timestamp",
        "sender_hash",
        "direction",
        "is_system_event",
        "body_char_count",
        "has_attachment",
        "feature_follow_up",
        "is_response_gap",
        "body_text",
        "sender_raw",
        "local_path",
    )

    safe_select = build_safe_select_sql("allowed_messages", available_columns)

    assert safe_select.selected_columns == (
        "file_id",
        "source_tag",
        "timestamp",
        "is_system_event",
        "body_char_count",
        "has_attachment",
        "feature_follow_up",
        "is_response_gap",
    )
    assert not FORBIDDEN_COLUMNS.intersection(safe_select.selected_columns)
    for forbidden_column in FORBIDDEN_COLUMNS:
        assert forbidden_column not in safe_select.sql


def test_analyze_allowed_temporal_generates_aggregate_outputs(tmp_path: Path) -> None:
    input_db = tmp_path / "allowed_messages.local.sqlite"
    output_db = tmp_path / "allowed_temporal.local.sqlite"
    summary_path = tmp_path / "allowed_temporal_summary.md"
    _create_allowed_messages_fixture(input_db)

    result = analyze_allowed_temporal(
        input_db=input_db,
        output_db=output_db,
        summary_path=summary_path,
        top_limit=2,
    )

    assert result.total_messages == 5
    assert result.system_event_count == 1
    assert result.year_counts == [(2024, 4), (2025, 1)]
    assert dict(result.month_counts) == {"2024-01": 3, "2024-02": 1, "2025-01": 1}
    assert dict(result.hour_counts)[13] == 2
    assert dict(result.source_tag_counts) == {"export-alpha": 3, "export-beta": 2}
    assert result.top_files[0].file_id == "file-a"
    assert result.top_files[0].message_count == 3
    assert dict((month, median) for month, median, _ in result.monthly_median_body_chars)[
        "2024-01"
    ] == 20.0
    assert dict((flag, count) for flag, count, _ in result.feature_flag_counts) == {
        "feature_follow_up": 3,
        "has_attachment": 2,
        "is_response_gap": 2,
    }

    conn = sqlite3.connect(output_db)
    try:
        assert (
            conn.execute(
                "SELECT message_count FROM messages_by_month WHERE month = '2024-01'"
            ).fetchone()[0]
            == 3
        )
        assert (
            conn.execute(
                "SELECT median_body_chars FROM median_body_chars_by_month WHERE month = '2024-01'"
            ).fetchone()[0]
            == 20.0
        )
        assert conn.execute("SELECT event_count FROM system_event_count").fetchone()[0] == 1
    finally:
        conn.close()

    summary = summary_path.read_text(encoding="utf-8")
    assert "DO_NOT_READ_BODY" not in summary
    assert "DO_NOT_READ_SENDER" not in summary
    assert "/do/not/read" not in summary
    assert "| 2024-01 | 3 |" in summary
