from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.quarantine_spicy_conversations import quarantine_to_outputs


def _write_full_messages_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
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
            );

            CREATE TABLE file_parse_summaries (
                file_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                parser TEXT NOT NULL,
                local_path TEXT NOT NULL,
                parsed_messages INTEGER NOT NULL,
                system_events INTEGER NOT NULL,
                distinct_sender_hashes INTEGER NOT NULL,
                min_timestamp TEXT,
                max_timestamp TEXT,
                body_chars INTEGER NOT NULL,
                warning_codes_json TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO file_parse_summaries (
                file_id, source, source_tag, path_hash, parser, local_path,
                parsed_messages, system_events, distinct_sender_hashes,
                min_timestamp, max_timestamp, body_chars, warning_codes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "02_zip-extracted",
                    "tag-a",
                    "path-a",
                    "whatsapp_export",
                    "/private/a",
                    2,
                    0,
                    2,
                    "2026-05-01T08:00:00",
                    "2026-05-01T09:00:00",
                    50,
                    "[]",
                ),
                (
                    "wa-file-0002",
                    "02_zip-extracted",
                    "tag-b",
                    "path-b",
                    "whatsapp_export",
                    "/private/b",
                    1,
                    0,
                    1,
                    "2026-05-02T08:00:00",
                    "2026-05-02T08:00:00",
                    20,
                    "[]",
                ),
            ],
        )
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
            [
                (
                    "wa-file-0001",
                    "02_zip-extracted",
                    "tag-a",
                    "path-a",
                    1,
                    "2026-05-01T08:00:00",
                    "A",
                    "sender-a",
                    None,
                    0,
                    "I love you baby",
                    15,
                    1,
                    0,
                    0,
                    0,
                    0,
                ),
                (
                    "wa-file-0001",
                    "02_zip-extracted",
                    "tag-a",
                    "path-a",
                    2,
                    "2026-05-01T09:00:00",
                    "B",
                    "sender-b",
                    None,
                    0,
                    "This is an explicit sex message",
                    31,
                    1,
                    0,
                    0,
                    0,
                    0,
                ),
                (
                    "wa-file-0002",
                    "02_zip-extracted",
                    "tag-b",
                    "path-b",
                    1,
                    "2026-05-02T08:00:00",
                    "C",
                    "sender-c",
                    None,
                    0,
                    "Please send the document",
                    24,
                    1,
                    0,
                    0,
                    0,
                    0,
                ),
            ],
        )
        conn.commit()


def test_quarantine_sets_aside_only_explicit_spicy_hits(tmp_path: Path) -> None:
    input_db = tmp_path / "full_messages.local.sqlite"
    output_db = tmp_path / "spicy_quarantine.local.sqlite"
    quarantine_tsv = tmp_path / "spicy_quarantine.local.tsv"
    usable_tsv = tmp_path / "usable_after_spicy_quarantine.local.tsv"
    summary = tmp_path / "spicy_quarantine_summary.md"
    _write_full_messages_db(input_db)

    result = quarantine_to_outputs(
        input_db=input_db,
        output_db=output_db,
        quarantine_tsv=quarantine_tsv,
        usable_tsv=usable_tsv,
        summary_path=summary,
    )

    decisions = {row.file_summary.file_id: row for row in result.decisions}
    assert decisions["wa-file-0001"].quarantine_decision == "quarantine_spicy_candidate"
    assert decisions["wa-file-0002"].quarantine_decision == "usable"

    quarantine_text = quarantine_tsv.read_text(encoding="utf-8")
    usable_text = usable_tsv.read_text(encoding="utf-8")
    assert "wa-file-0001" in quarantine_text
    assert "wa-file-0002" not in quarantine_text
    assert "wa-file-0002" in usable_text

    summary_text = summary.read_text(encoding="utf-8")
    assert "explicit sex message" not in summary_text
    assert "| Quarantined files | 1 |" in summary_text
    assert "| Usable files | 1 |" in summary_text
