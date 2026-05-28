from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.mine_full_gold_signals import (
    mine_full_gold_signals_to_outputs,
)


def _write_full_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                body_text TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, source, source_tag, path_hash, message_index,
                timestamp, sender_hash, body_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "02_zip-extracted",
                    "tag-a",
                    "path-a",
                    1,
                    "2026-05-01T08:00:00",
                    "sender-a",
                    "New client asked visa KITAS price and passport document.",
                ),
                (
                    "wa-file-0001",
                    "02_zip-extracted",
                    "tag-a",
                    "path-a",
                    2,
                    "2026-05-01T09:00:00",
                    "sender-b",
                    "Please follow up payment transfer proof today.",
                ),
                (
                    "wa-file-0002",
                    "03_drive-icloud",
                    "tag-b",
                    "path-b",
                    1,
                    "2026-05-02T09:00:00",
                    "sender-c",
                    "This quarantined file should not be mined even with visa.",
                ),
            ],
        )
        conn.commit()


def _write_usable_tsv(path: Path) -> None:
    path.write_text(
        "file_id\tsource\tsource_tag\tpath_hash\tlocal_path\tparsed_messages\t"
        "min_timestamp\tmax_timestamp\thard_hits\tsoft_hits\thit_codes_json\t"
        "quarantine_decision\tquarantine_reason\n"
        "wa-file-0001\t02_zip-extracted\ttag-a\tpath-a\t/private/a\t2\t"
        "2026-05-01T08:00:00\t2026-05-01T09:00:00\t0\t0\t[]\tusable\t"
        "no_explicit_spicy_hit\n",
        encoding="utf-8",
    )


def test_mine_full_gold_signals_uses_only_usable_messages(tmp_path: Path) -> None:
    input_db = tmp_path / "full_messages.local.sqlite"
    usable_tsv = tmp_path / "usable_after_spicy_quarantine.local.tsv"
    output_db = tmp_path / "full_gold_signals.local.sqlite"
    summary = tmp_path / "full_gold_signals_summary.md"
    _write_full_db(input_db)
    _write_usable_tsv(usable_tsv)

    messages, hits, usable_files = mine_full_gold_signals_to_outputs(
        input_db=input_db,
        usable_tsv=usable_tsv,
        output_db=output_db,
        summary_path=summary,
    )

    assert usable_files == 1
    assert len(messages) == 2
    assert {hit.signal_group for hit in hits} >= {
        "crm_lead_intake",
        "document_ops",
        "immigration_lifecycle",
        "tax_payment",
        "followup_risk",
    }
    assert all(hit.file_id == "wa-file-0001" for hit in hits)

    summary_text = summary.read_text(encoding="utf-8")
    assert "New client asked" not in summary_text
    assert "This quarantined file should not be mined" not in summary_text
    assert "| Usable files | 1 |" in summary_text
    assert "crm_lead_intake" in summary_text

    with sqlite3.connect(output_db) as conn:
        hit_rows = conn.execute("SELECT COUNT(*) FROM gold_signal_hits").fetchone()[0]
        raw_rows = conn.execute(
            "SELECT COUNT(*) FROM gold_signal_hits WHERE body_hash LIKE '%New client%'"
        ).fetchone()[0]
    assert hit_rows == len(hits)
    assert raw_rows == 0
