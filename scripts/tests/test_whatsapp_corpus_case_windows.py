from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.build_case_windows import build_case_windows


def _write_events_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE domain_events (
                event_id TEXT PRIMARY KEY,
                domain_code TEXT NOT NULL,
                event_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                file_id TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                month TEXT NOT NULL,
                source_ref_hash TEXT NOT NULL,
                sender_hash TEXT NOT NULL,
                score REAL NOT NULL,
                severity TEXT NOT NULL,
                reference_hash TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO domain_events (
                event_id, domain_code, event_code, evidence_code, file_id,
                message_index, timestamp, month, source_ref_hash, sender_hash,
                score, severity, reference_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "e1",
                    "tax_payment",
                    "invoice_payment_proof",
                    "synthetic_signal",
                    "anon-file-a",
                    1,
                    "2026-01-01T00:00:00",
                    "2026-01",
                    "source-hash-a",
                    "sender-hash-a",
                    1.0,
                    "high",
                    "value-hash-a",
                ),
                (
                    "e2",
                    "document_requirement",
                    "passport_identity_document",
                    "synthetic_signal",
                    "anon-file-a",
                    1,
                    "2026-01-01T00:00:00",
                    "2026-01",
                    "source-hash-a",
                    "sender-hash-a",
                    1.0,
                    "",
                    "value-hash-b",
                ),
                (
                    "e3",
                    "tax_payment",
                    "invoice_payment_proof",
                    "synthetic_signal",
                    "anon-file-a",
                    40,
                    "2026-01-02T00:00:00",
                    "2026-01",
                    "source-hash-a",
                    "sender-hash-a",
                    1.0,
                    "",
                    "value-hash-c",
                ),
                (
                    "e4",
                    "immigration_lifecycle",
                    "approval_issuance",
                    "synthetic_signal",
                    "anon-file-a",
                    41,
                    "2026-01-06T00:30:00",
                    "2026-01",
                    "source-hash-a",
                    "sender-hash-a",
                    1.0,
                    "critical",
                    "value-hash-d",
                ),
                (
                    "e5",
                    "followup_risk",
                    "deadline_followup",
                    "synthetic_signal",
                    "anon-file-a",
                    130,
                    "2026-01-06T01:00:00",
                    "2026-01",
                    "source-hash-a",
                    "sender-hash-a",
                    1.0,
                    "urgent",
                    "value-hash-e",
                ),
                (
                    "e6",
                    "document_requirement",
                    "company_deed",
                    "synthetic_signal",
                    "anon-file-b",
                    5,
                    "2026-02-01T00:00:00",
                    "2026-02",
                    "source-hash-b",
                    "sender-hash-b",
                    1.0,
                    "",
                    "value-hash-f",
                ),
            ],
        )
        conn.commit()


def test_build_case_windows_splits_by_time_and_message_gap(tmp_path: Path) -> None:
    events_db = tmp_path / "allowed_domain_events.local.sqlite"
    output_db = tmp_path / "allowed_case_windows.local.sqlite"
    summary_path = tmp_path / "allowed_case_windows_summary.md"
    _write_events_db(events_db)

    index = build_case_windows(
        events_db=events_db,
        output_db=output_db,
        summary_path=summary_path,
        max_gap_hours=72,
        max_message_gap=80,
        top_event_codes_limit=3,
        summary_limit=10,
    )

    assert len(index.events) == 6
    assert len(index.windows) == 4
    assert [window.event_count for window in index.windows] == [3, 1, 1, 1]
    assert [window.message_count for window in index.windows] == [2, 1, 1, 1]

    first_window = index.windows[0]
    assert first_window.file_id == "anon-file-a"
    assert first_window.first_message_index == 1
    assert first_window.last_message_index == 40
    assert first_window.dominant_domain == "tax_payment"
    assert first_window.severity_high_count == 1
    assert first_window.domain_count == 2
    assert first_window.window_id

    with sqlite3.connect(output_db) as conn:
        run = conn.execute(
            """
            SELECT event_rows_read, window_count, file_count, message_count, domain_count
            FROM case_runs
            """
        ).fetchone()
        rows = conn.execute(
            """
            SELECT file_id, dominant_domain, severity_high_count, top_event_codes_json
            FROM case_windows
            ORDER BY file_id, first_message_index
            """
        ).fetchall()
        top_codes = json.loads(rows[0][3])

    assert run == (6, 4, 2, 5, 4)
    assert rows[0][0] == "anon-file-a"
    assert rows[0][1] == "tax_payment"
    assert rows[0][2] == 1
    assert top_codes[0] == {
        "domain_code": "tax_payment",
        "event_code": "invoice_payment_proof",
        "event_count": 2,
    }


def test_build_case_windows_summary_is_aggregate_only(tmp_path: Path) -> None:
    events_db = tmp_path / "allowed_domain_events.local.sqlite"
    output_db = tmp_path / "allowed_case_windows.local.sqlite"
    summary_path = tmp_path / "allowed_case_windows_summary.md"
    _write_events_db(events_db)

    build_case_windows(
        events_db=events_db,
        output_db=output_db,
        summary_path=summary_path,
        max_gap_hours=72,
        max_message_gap=80,
        top_event_codes_limit=3,
        summary_limit=10,
    )

    summary = summary_path.read_text(encoding="utf-8")
    assert "anon-file-a" not in summary
    assert "source-hash" not in summary
    assert "value-hash" not in summary
    assert "invoice_payment_proof" not in summary
    assert "| Case windows | 4 |" in summary
    assert "| 1 | 3 |" in summary
    assert "| tax_payment | 2 | 2 | 1 | 1 |" in summary
    assert "| 2026-01 | 3 | 5 | 4 |" in summary


def test_build_case_windows_rejects_unexpected_input_name(tmp_path: Path) -> None:
    unexpected_db = tmp_path / "allowed_messages.local.sqlite"
    unexpected_db.write_bytes(b"")

    try:
        build_case_windows(
            events_db=unexpected_db,
            output_db=tmp_path / "allowed_case_windows.local.sqlite",
            summary_path=tmp_path / "allowed_case_windows_summary.md",
        )
    except ValueError as exc:
        assert "Refusing to read unexpected input artifact" in str(exc)
    else:
        raise AssertionError("unexpected input DB name was accepted")
