from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.analyze_allowed_signals import analyze_allowed_signals


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
                file_id, source_tag, message_index, timestamp, body_text,
                has_url, has_email, has_phone_like
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "tag-private",
                    1,
                    "2026-05-26T10:00:00",
                    "passport visa urgent fixture body",
                    0,
                    0,
                    0,
                ),
                (
                    "wa-file-0001",
                    "tag-private",
                    2,
                    "2026-05-26T10:01:00",
                    "invoice payment transfer fixture body",
                    1,
                    1,
                    1,
                ),
            ],
        )
        conn.commit()


def test_analyze_allowed_signals_writes_safe_summary(tmp_path: Path) -> None:
    messages_db = tmp_path / "allowed_messages.local.sqlite"
    output_dir = tmp_path / "analysis"
    write_messages_db(messages_db)

    messages, hits = analyze_allowed_signals(
        messages_db=messages_db,
        output_dir=output_dir,
    )

    assert len(messages) == 2
    assert {hit.signal_code for hit in hits} >= {
        "identity_document",
        "immigration",
        "urgency_risk",
        "tax_accounting",
        "contains_url",
        "contains_email",
        "contains_phone_like",
    }
    summary = (output_dir / "allowed_signal_summary.md").read_text(encoding="utf-8")
    assert "fixture body" not in summary
    assert "passport visa urgent" not in summary
    assert str(tmp_path) not in summary
    assert "identity_document" in summary

    with sqlite3.connect(output_dir / "allowed_signal_hits.local.sqlite") as conn:
        body_column = conn.execute(
            """
            SELECT COUNT(*)
            FROM pragma_table_info('signal_hits')
            WHERE name = 'body_text'
            """
        ).fetchone()[0]
    assert body_column == 0
