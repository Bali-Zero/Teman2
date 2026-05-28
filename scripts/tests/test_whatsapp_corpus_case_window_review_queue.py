from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.build_case_window_review_queue import (
    build_case_window_review_queue,
)


def _write_case_windows_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE case_windows (
                window_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                window_ordinal INTEGER NOT NULL,
                first_timestamp TEXT,
                last_timestamp TEXT,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL,
                first_message_index INTEGER NOT NULL,
                last_message_index INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL,
                dominant_domain TEXT NOT NULL,
                severity_high_count INTEGER NOT NULL,
                top_event_codes_json TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO case_windows (
                window_id, file_id, window_ordinal, first_timestamp, last_timestamp,
                first_month, last_month, first_message_index, last_message_index,
                event_count, message_count, domain_count, dominant_domain,
                severity_high_count, top_event_codes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "window-a",
                    "file-a",
                    1,
                    "2026-01-01T00:00:00",
                    "2026-01-03T00:00:00",
                    "2026-01",
                    "2026-01",
                    1,
                    40,
                    55,
                    40,
                    4,
                    "document_requirement",
                    2,
                    '[{"domain_code":"document_requirement","event_code":"passport_identity_document","event_count":5}]',
                ),
                (
                    "window-b",
                    "file-b",
                    2,
                    "2026-01-05T00:00:00",
                    "2026-02-06T00:00:00",
                    "2026-01",
                    "2026-02",
                    5,
                    120,
                    18,
                    17,
                    3,
                    "followup_risk",
                    1,
                    '[{"domain_code":"followup_risk","event_code":"deadline_followup","event_count":8}]',
                ),
                (
                    "window-c",
                    "file-c",
                    1,
                    "2026-03-01T00:00:00",
                    "2026-03-01T01:00:00",
                    "2026-03",
                    "2026-03",
                    1,
                    4,
                    4,
                    4,
                    1,
                    "tax_payment",
                    0,
                    '[{"domain_code":"tax_payment","event_code":"invoice_payment_proof","event_count":4}]',
                ),
            ],
        )
        conn.commit()


def test_build_case_window_review_queue_writes_aggregate_outputs(
    tmp_path: Path,
) -> None:
    input_db = tmp_path / "allowed_case_windows.local.sqlite"
    output_tsv = tmp_path / "allowed_case_window_review.local.tsv"
    summary_path = tmp_path / "allowed_case_window_review_summary.md"
    _write_case_windows_db(input_db)

    index = build_case_window_review_queue(
        input_db=input_db,
        output_tsv=output_tsv,
        summary_path=summary_path,
        limit=10,
    )

    assert len(index.windows) == 3
    assert len(index.queue_rows) == 2
    assert index.queue_rows[0].window.window_id == "window-a"
    assert "high_severity" in index.queue_rows[0].review_reasons
    assert "cross_month" in index.queue_rows[1].review_reasons

    summary = summary_path.read_text(encoding="utf-8")
    assert "window-a" not in summary
    assert "window-b" not in summary
    assert "high_severity" in summary
    assert "| Queue windows | 2 |" in summary
    assert "| followup_risk | 1 |" in summary

    tsv_text = output_tsv.read_text(encoding="utf-8")
    assert "window-a" in tsv_text
    assert "window-b" in tsv_text
    assert "review_score" in tsv_text


def test_build_case_window_review_queue_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "allowed_domain_events.local.sqlite"
    unexpected_db.write_bytes(b"")

    try:
        build_case_window_review_queue(
            input_db=unexpected_db,
            output_tsv=tmp_path / "allowed_case_window_review.local.tsv",
            summary_path=tmp_path / "allowed_case_window_review_summary.md",
        )
    except ValueError as exc:
        assert "Refusing to read unexpected input artifact" in str(exc)
    else:
        raise AssertionError("unexpected input DB name was accepted")
