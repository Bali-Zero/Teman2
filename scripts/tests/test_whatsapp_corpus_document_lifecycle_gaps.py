from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.analyze_document_lifecycle_gaps import (
    analyze_document_lifecycle_gaps,
)


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
                    "immigration_lifecycle",
                    "application_submission",
                    "signal:immigration",
                    "file-a",
                    1,
                    "2026-05-01T10:00:00",
                    "2026-05",
                    "source-hash",
                    "",
                    1,
                    "",
                    "",
                ),
                (
                    "e2",
                    "document_requirement",
                    "passport_identity_document",
                    "passport_keyword",
                    "file-a",
                    1,
                    "2026-05-01T10:00:00",
                    "2026-05",
                    "source-hash",
                    "sender-hash",
                    1,
                    "",
                    "hash-only",
                ),
                (
                    "e3",
                    "immigration_lifecycle",
                    "approval_issuance",
                    "body_keyword:approval",
                    "file-a",
                    2,
                    "2026-05-02T10:00:00",
                    "2026-05",
                    "source-hash",
                    "",
                    1,
                    "",
                    "",
                ),
                (
                    "e4",
                    "document_requirement",
                    "payment_proof",
                    "payment_keyword",
                    "file-a",
                    3,
                    "2026-05-03T10:00:00",
                    "2026-05",
                    "source-hash",
                    "sender-hash",
                    1,
                    "",
                    "hash-only-2",
                ),
                (
                    "e5",
                    "tax_payment",
                    "invoice_payment_proof",
                    "invoice_keyword",
                    "file-a",
                    1,
                    "2026-05-01T10:00:00",
                    "2026-05",
                    "source-hash",
                    "",
                    1,
                    "",
                    "",
                ),
            ],
        )
        conn.commit()


def test_analyze_document_lifecycle_gaps_writes_aggregate_outputs(
    tmp_path: Path,
) -> None:
    events_db = tmp_path / "allowed_domain_events.local.sqlite"
    output_db = tmp_path / "allowed_document_lifecycle_gaps.local.sqlite"
    summary_path = tmp_path / "allowed_document_lifecycle_gaps_summary.md"
    _write_events_db(events_db)

    analysis = analyze_document_lifecycle_gaps(
        events_db=events_db,
        output_db=output_db,
        summary_path=summary_path,
        summary_limit=10,
    )

    assert analysis.lifecycle_message_count == 2
    assert analysis.document_message_count == 2
    assert analysis.overlap_message_count == 1
    assert ("application_submission", 1, 1, 0, 1.0) in analysis.stage_coverage
    assert ("approval_issuance", 1, 0, 1, 0.0) in analysis.stage_coverage
    assert ("passport_identity_document", 1, 1, 0, 1.0) in analysis.document_coverage
    assert ("payment_proof", 1, 0, 1, 0.0) in analysis.document_coverage

    summary = summary_path.read_text(encoding="utf-8")
    assert "raw message text" in summary
    assert "hash-only" not in summary
    assert "application_submission" in summary
    assert "passport_identity_document" in summary

    with sqlite3.connect(output_db) as conn:
        row = conn.execute(
            """
            SELECT with_document_message_count, without_document_message_count
            FROM lifecycle_stage_document_coverage
            WHERE stage_code = 'approval_issuance'
            """
        ).fetchone()
        matrix_count = conn.execute(
            "SELECT COUNT(*) FROM stage_document_matrix"
        ).fetchone()[0]

    assert row == (0, 1)
    assert matrix_count == 1


def test_analyze_document_lifecycle_gaps_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "allowed_messages.local.sqlite"
    unexpected_db.write_bytes(b"")

    try:
        analyze_document_lifecycle_gaps(
            events_db=unexpected_db,
            output_db=tmp_path / "allowed_document_lifecycle_gaps.local.sqlite",
            summary_path=tmp_path / "allowed_document_lifecycle_gaps_summary.md",
        )
    except ValueError as exc:
        assert "Refusing to read unexpected input artifact" in str(exc)
    else:
        raise AssertionError("unexpected input DB name was accepted")
