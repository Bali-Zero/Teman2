from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.extract_document_requirements import (
    extract_document_requirements,
    stable_hash,
)


def write_messages_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                body_text TEXT NOT NULL,
                has_url INTEGER NOT NULL,
                has_email INTEGER NOT NULL,
                has_phone_like INTEGER NOT NULL,
                has_media_omitted INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, source_tag, message_index, timestamp, sender_hash,
                body_text, has_url, has_email, has_phone_like, has_media_omitted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "raw-source-tag-for-test",
                    1,
                    "2026-05-26T10:00:00",
                    "sender-hash-1",
                    "Please send passport A1234567, visa sponsor letter, and passport photo.",
                    0,
                    0,
                    0,
                    1,
                ),
                (
                    "wa-file-0001",
                    "raw-source-tag-for-test",
                    2,
                    "2026-05-26T10:05:00",
                    "sender-hash-2",
                    "Need tax document NPWP 12.345.678.9-012.345 and payment proof IDR 1500000.",
                    0,
                    0,
                    1,
                    0,
                ),
                (
                    "wa-file-0002",
                    "another-raw-source-tag",
                    1,
                    "2026-05-27T11:00:00",
                    "sender-hash-3",
                    "Company documents: akta, NIB 1234567890123, lease agreement, notary copy.",
                    0,
                    0,
                    0,
                    0,
                ),
            ],
        )
        conn.commit()


def write_candidates_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE extracted_candidates (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                category_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                value_hash TEXT
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO extracted_candidates (
                file_id, source_tag, message_index, timestamp, sender_hash,
                category_code, evidence_code, body_hash, value_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "raw-source-tag-for-test",
                    2,
                    "2026-05-26T10:05:00",
                    "sender-hash-2",
                    "money_reference",
                    "money_like_hash",
                    stable_hash(
                        "Need tax document NPWP 12.345.678.9-012.345 and payment proof IDR 1500000.",
                        length=32,
                    ),
                    stable_hash("idr 1500000"),
                ),
                (
                    "wa-file-0002",
                    "another-raw-source-tag",
                    1,
                    "2026-05-27T11:00:00",
                    "sender-hash-3",
                    "property_case",
                    "category_keyword",
                    stable_hash(
                        "Company documents: akta, NIB 1234567890123, lease agreement, notary copy.",
                        length=32,
                    ),
                    None,
                ),
            ],
        )
        conn.commit()


def test_extract_document_requirements_writes_safe_artifacts(tmp_path: Path) -> None:
    messages_db = tmp_path / "allowed_messages.local.sqlite"
    candidates_db = tmp_path / "allowed_candidates.local.sqlite"
    output_db = tmp_path / "allowed_document_requirements.local.sqlite"
    summary_path = tmp_path / "allowed_document_requirements_summary.md"
    write_messages_db(messages_db)
    write_candidates_db(candidates_db)

    result = extract_document_requirements(
        messages_db=messages_db,
        candidates_db=candidates_db,
        output_db=output_db,
        summary_path=summary_path,
    )

    assert len(result.messages) == 3
    assert result.candidate_count == 2
    assert {hit.requirement_code for hit in result.hits} >= {
        "passport_identity_document",
        "visa_immigration_document",
        "photo_biometric",
        "tax_document",
        "payment_proof",
        "company_document",
        "property_document",
        "translation_legalization_notary",
    }
    assert any(hit.value_hash for hit in result.hits)

    summary = summary_path.read_text(encoding="utf-8")
    assert "Please send passport" not in summary
    assert "A1234567" not in summary
    assert "12.345.678.9-012.345" not in summary
    assert "IDR 1500000" not in summary
    assert "raw-source-tag-for-test" not in summary
    assert str(tmp_path) not in summary
    assert "passport_identity_document" in summary
    assert "payment_proof" in summary

    with sqlite3.connect(output_db) as conn:
        columns = {
            row[1]
            for row in conn.execute(
                "SELECT * FROM pragma_table_info('requirement_hits')"
            )
        }
        category_rows = conn.execute(
            "SELECT COUNT(*) FROM requirement_category_counts"
        ).fetchone()[0]
        raw_source_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM requirement_hits
            WHERE source_tag_hash IN ('raw-source-tag-for-test', 'another-raw-source-tag')
            """
        ).fetchone()[0]
        value_hash_rows = conn.execute(
            "SELECT COUNT(*) FROM requirement_hits WHERE value_hash != ''"
        ).fetchone()[0]

    assert "body_text" not in columns
    assert "source_tag" not in columns
    assert "raw_value" not in columns
    assert category_rows >= 8
    assert raw_source_rows == 0
    assert value_hash_rows >= 1
