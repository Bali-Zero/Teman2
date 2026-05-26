from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.build_case_window_manual_review import (
    build_manual_review_pack,
)


def _write_queue(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "rank",
                "window_id",
                "file_id",
                "window_ordinal",
                "first_month",
                "last_month",
                "first_message_index",
                "last_message_index",
                "event_count",
                "message_count",
                "domain_count",
                "dominant_domain",
                "severity_high_count",
                "review_score",
                "review_reasons",
                "top_event_codes_json",
            ]
        )
        writer.writerow(
            [
                1,
                "window-a",
                "wa-file-0001",
                3,
                "2026-05",
                "2026-05",
                2,
                3,
                12,
                2,
                2,
                "followup_risk",
                1,
                42,
                "high_severity,followup_dominant",
                '[{"domain_code":"followup_risk","event_code":"deadline_followup"}]',
            ]
        )


def _write_messages_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                direction TEXT,
                body_text TEXT NOT NULL,
                body_char_count INTEGER NOT NULL
            )
            """
        )
        rows = [
            (
                "wa-file-0001",
                1,
                "2026-05-01T08:00:00",
                "sender-a",
                "received",
                "Before context",
                14,
            ),
            (
                "wa-file-0001",
                2,
                "2026-05-01T09:00:00",
                "sender-b",
                "sent",
                "Email test@example.com phone +62 812 3456 7890 passport A1234567",
                72,
            ),
            (
                "wa-file-0001",
                3,
                "2026-05-01T10:00:00",
                "sender-a",
                "received",
                "Open https://example.com and check NIB 1234567890123",
                55,
            ),
            (
                "wa-file-0001",
                4,
                "2026-05-01T11:00:00",
                "sender-b",
                "sent",
                "After context",
                13,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, message_index, timestamp, sender_hash, direction,
                body_text, body_char_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def _write_events_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE domain_events (
                file_id TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                domain_code TEXT NOT NULL,
                event_code TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO domain_events (
                file_id, message_index, domain_code, event_code
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                ("wa-file-0001", 2, "followup_risk", "deadline_followup"),
                ("wa-file-0001", 3, "document_requirement", "business_document"),
            ],
        )
        conn.commit()


def test_build_manual_review_pack_writes_local_redacted_context(tmp_path: Path) -> None:
    queue_tsv = tmp_path / "allowed_case_window_review.local.tsv"
    messages_db = tmp_path / "allowed_messages.local.sqlite"
    events_db = tmp_path / "allowed_domain_events.local.sqlite"
    workbook = tmp_path / "case_window_review_workbook.local.tsv"
    context = tmp_path / "case_window_context.local.tsv"
    summary = tmp_path / "case_window_manual_review_summary.md"
    _write_queue(queue_tsv)
    _write_messages_db(messages_db)
    _write_events_db(events_db)

    pack = build_manual_review_pack(
        queue_tsv=queue_tsv,
        messages_db=messages_db,
        events_db=events_db,
        workbook_path=workbook,
        context_path=context,
        summary_path=summary,
        limit=100,
        context_radius=1,
        max_chars=200,
    )

    assert len(pack.queue_rows) == 1
    assert len(pack.context_rows) == 4

    workbook_text = workbook.read_text(encoding="utf-8")
    assert "owner_decision" in workbook_text
    assert "window-a" in workbook_text
    assert "\ttodo\t" not in workbook_text

    context_text = context.read_text(encoding="utf-8")
    assert "[EMAIL]" in context_text
    assert "[PHONE]" in context_text
    assert "[URL]" in context_text
    assert "[ID]" in context_text
    assert "test@example.com" not in context_text
    assert "+62 812 3456 7890" not in context_text
    assert "https://example.com" not in context_text
    assert "A1234567" not in context_text
    assert "1234567890123" not in context_text
    assert "followup_risk:deadline_followup" in context_text

    summary_text = summary.read_text(encoding="utf-8")
    assert "test@example.com" not in summary_text
    assert "+62" not in summary_text
    assert "Review windows | 1" in summary_text
    assert "Context rows | 4" in summary_text


def test_build_manual_review_pack_preserves_owner_fields(tmp_path: Path) -> None:
    queue_tsv = tmp_path / "allowed_case_window_review.local.tsv"
    messages_db = tmp_path / "allowed_messages.local.sqlite"
    events_db = tmp_path / "allowed_domain_events.local.sqlite"
    workbook = tmp_path / "case_window_review_workbook.local.tsv"
    context = tmp_path / "case_window_context.local.tsv"
    summary = tmp_path / "case_window_manual_review_summary.md"
    _write_queue(queue_tsv)
    _write_messages_db(messages_db)
    _write_events_db(events_db)

    workbook.write_text(
        "\t".join(
            [
                "review_status",
                "owner_decision",
                "action_type",
                "priority",
                "action_owner",
                "due_date",
                "owner_notes",
                "window_id",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "reviewed",
                "approve",
                "crm_followup",
                "P1",
                "ops",
                "2026-06-01",
                "local note",
                "window-a",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    pack = build_manual_review_pack(
        queue_tsv=queue_tsv,
        messages_db=messages_db,
        events_db=events_db,
        workbook_path=workbook,
        context_path=context,
        summary_path=summary,
        limit=100,
        context_radius=0,
        max_chars=200,
    )

    assert pack.preserved_owner_rows == 1
    workbook_text = workbook.read_text(encoding="utf-8")
    assert "approve" in workbook_text
    assert "crm_followup" in workbook_text
    assert "local note" in workbook_text
