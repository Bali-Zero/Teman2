from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.build_domain_event_index import (
    build_domain_event_index,
    stable_hash,
)


def _write_document_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE requirement_hits (
                file_id TEXT NOT NULL,
                source_tag_hash TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                month TEXT NOT NULL,
                sender_hash TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                requirement_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                context_code TEXT NOT NULL,
                value_hash TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO requirement_hits
                (file_id, source_tag_hash, message_index, timestamp, month, sender_hash,
                 body_hash, requirement_code, evidence_code, context_code, value_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "wa-file-test",
                "source-hash",
                1,
                "2026-05-01T10:00:00",
                "2026-05",
                "sender-hash",
                "body-hash",
                "passport_identity_document",
                "passport_keyword",
                "explicit_requirement_context",
                "",
            ),
        )
        conn.commit()


def _write_lifecycle_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE stage_hits (
                file_id TEXT NOT NULL,
                source_tag TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                month TEXT NOT NULL,
                stage_code TEXT NOT NULL,
                stage_label TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                score INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO stage_hits
                (file_id, source_tag, message_index, timestamp, month, stage_code,
                 stage_label, evidence_code, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "wa-file-test",
                "raw-source-tag-do-not-leak",
                1,
                "2026-05-01T10:00:00",
                "2026-05",
                "identity_passport",
                "identity/passport",
                "body_keyword:identity_passport",
                2,
            ),
        )
        conn.commit()


def _write_tax_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE tax_payment_hits (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                category_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                value_hash TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO tax_payment_hits
                (file_id, source_tag, message_index, timestamp, sender_hash,
                 category_code, evidence_code, body_hash, value_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "wa-file-test",
                "raw-source-tag-do-not-leak",
                2,
                "2026-05-02T10:00:00",
                "sender-hash",
                "invoice_payment_proof",
                "reference_hash",
                "body-hash-2",
                stable_hash("DO_NOT_LEAK_REFERENCE"),
            ),
        )
        conn.commit()


def _write_followup_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE queue_items (
                file_id TEXT NOT NULL,
                source_tag TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                month TEXT NOT NULL,
                sender_hash TEXT,
                direction TEXT,
                queue_bucket TEXT NOT NULL,
                severity TEXT NOT NULL,
                score INTEGER NOT NULL,
                reason_codes_json TEXT NOT NULL,
                signal_codes_json TEXT NOT NULL,
                response_gap_hours REAL,
                body_char_count INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO queue_items
                (file_id, source_tag, message_index, timestamp, month, sender_hash,
                 direction, queue_bucket, severity, score, reason_codes_json,
                 signal_codes_json, response_gap_hours, body_char_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "wa-file-test",
                "raw-source-tag-do-not-leak",
                2,
                "2026-05-02T10:05:00",
                "2026-05",
                "sender-hash",
                "incoming",
                "deadline_followup",
                "high",
                8,
                '["deadline_mention", "repeated_request_thread"]',
                "[]",
                72.0,
                40,
            ),
        )
        conn.commit()


def test_build_domain_event_index_writes_safe_outputs(tmp_path: Path) -> None:
    document_db = tmp_path / "allowed_document_requirements.local.sqlite"
    lifecycle_db = tmp_path / "allowed_immigration_lifecycle.local.sqlite"
    tax_db = tmp_path / "allowed_tax_payment.local.sqlite"
    followup_db = tmp_path / "allowed_followup_risk.local.sqlite"
    output_db = tmp_path / "allowed_domain_events.local.sqlite"
    summary_path = tmp_path / "allowed_domain_events_summary.md"
    _write_document_db(document_db)
    _write_lifecycle_db(lifecycle_db)
    _write_tax_db(tax_db)
    _write_followup_db(followup_db)

    index = build_domain_event_index(
        document_db=document_db,
        lifecycle_db=lifecycle_db,
        tax_db=tax_db,
        followup_db=followup_db,
        output_db=output_db,
        summary_path=summary_path,
        summary_limit=10,
    )

    assert len(index.events) == 5
    assert index.input_status == {
        "document_requirement": 1,
        "followup_risk": 2,
        "immigration_lifecycle": 1,
        "tax_payment": 1,
    }

    summary = summary_path.read_text(encoding="utf-8")
    assert "raw-source-tag-do-not-leak" not in summary
    assert "DO_NOT_LEAK_REFERENCE" not in summary
    assert "passport_identity_document" in summary
    assert "deadline_followup" in summary

    with sqlite3.connect(output_db) as conn:
        domain_counts = dict(
            conn.execute("SELECT domain_code, event_count FROM domain_totals")
        )
        raw_source_rows = conn.execute(
            "SELECT COUNT(*) FROM domain_events WHERE source_ref_hash = ?",
            ("raw-source-tag-do-not-leak",),
        ).fetchone()[0]
        cooccurrence_rows = conn.execute(
            "SELECT COUNT(*) FROM domain_cooccurrence"
        ).fetchone()[0]

    assert domain_counts == {
        "document_requirement": 1,
        "followup_risk": 2,
        "immigration_lifecycle": 1,
        "tax_payment": 1,
    }
    assert raw_source_rows == 0
    assert cooccurrence_rows >= 2


def test_build_domain_event_index_rejects_unexpected_input_name(tmp_path: Path) -> None:
    unexpected_db = tmp_path / "raw_messages.sqlite"
    unexpected_db.write_bytes(b"")
    valid_db = tmp_path / "allowed_document_requirements.local.sqlite"
    _write_document_db(valid_db)

    try:
        build_domain_event_index(
            document_db=unexpected_db,
            lifecycle_db=valid_db,
            tax_db=valid_db,
            followup_db=valid_db,
            output_db=tmp_path / "allowed_domain_events.local.sqlite",
            summary_path=tmp_path / "allowed_domain_events_summary.md",
        )
    except ValueError as exc:
        assert "Refusing to read unexpected input artifact" in str(exc)
    else:
        raise AssertionError("unexpected input DB name was accepted")
