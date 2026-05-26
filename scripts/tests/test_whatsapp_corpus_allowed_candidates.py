from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.extract_allowed_candidates import extract_allowed_candidates


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
                has_phone_like INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, source_tag, message_index, timestamp, sender_hash,
                body_text, has_url, has_email, has_phone_like
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "tag-fixture",
                    1,
                    "2026-05-26T10:00:00",
                    "sender-hash",
                    "passport A1234567 visa invoice Rp 1.000.000 fixture body",
                    0,
                    0,
                    1,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    2,
                    "2026-05-26T10:01:00",
                    "sender-hash",
                    "email fixture@example.com transfer 26/05/2026 fixture body",
                    0,
                    1,
                    0,
                ),
            ],
        )
        conn.commit()


def test_extract_allowed_candidates_writes_hashed_local_candidates(tmp_path: Path) -> None:
    messages_db = tmp_path / "allowed_messages.local.sqlite"
    output_dir = tmp_path / "analysis"
    write_messages_db(messages_db)

    messages, candidates = extract_allowed_candidates(
        messages_db=messages_db,
        output_dir=output_dir,
    )

    assert len(messages) == 2
    assert {candidate.category_code for candidate in candidates} >= {
        "identity_document",
        "visa_case",
        "tax_payment",
        "money_reference",
        "date_reference",
        "contact_reference",
    }
    summary = (output_dir / "allowed_candidates_summary.md").read_text(encoding="utf-8")
    assert "fixture body" not in summary
    assert "A1234567" not in summary
    assert "fixture@example.com" not in summary
    assert str(tmp_path) not in summary

    with sqlite3.connect(output_dir / "allowed_candidates.local.sqlite") as conn:
        table_info = conn.execute("SELECT name FROM pragma_table_info('extracted_candidates')").fetchall()
        columns = {row[0] for row in table_info}
        raw_values = conn.execute(
            """
            SELECT COUNT(*)
            FROM extracted_candidates
            WHERE value_hash LIKE '%A1234567%'
               OR value_hash LIKE '%fixture@example.com%'
            """
        ).fetchone()[0]
    assert "body_text" not in columns
    assert raw_values == 0
