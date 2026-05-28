from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.build_registry import (
    build_registry,
    summarize_sources,
    write_sqlite,
    write_summary,
)


def test_build_registry_counts_mirror_message_starts(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    mirror = root / "01_wa-mirror-db"
    mirror.mkdir(parents=True)
    chat = mirror / "00003_12345_PrivateName.txt"
    chat.write_text(
        "\n".join(
            [
                "=== PrivateName | +620000000 | 3 msgs ===",
                "2026-05-24 10:00 [SENT] first private body",
                "continuation line should not count",
                "2026-05-24 10:01 [RECEIVED] second body",
                "2026-05-24 10:02 [SENT] third body",
            ]
        ),
        encoding="utf-8",
    )

    entries = build_registry(root)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.message_start_count == 3
    assert entry.filename_claimed_count == 3
    assert entry.header_claimed_count == 3
    assert entry.warning_codes == ()
    assert entry.min_timestamp == "2026-05-24T10:00"
    assert entry.max_timestamp == "2026-05-24T10:02"


def test_build_registry_counts_whatsapp_export_variants(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    export = root / "02_zip-extracted" / "GoogleDrive" / "Private_Chat"
    export.mkdir(parents=True)
    chat = export / "_chat.txt"
    chat.write_text(
        "\n".join(
            [
                "[26/05/26, 15.00.01] Person A: first body",
                "continuation should not count",
                "[26/05/2026, 15:01:02] Person B: second body",
                "26/05/26, 15:02 - Messages are end-to-end encrypted.",
            ]
        ),
        encoding="utf-8",
    )

    entries = build_registry(root)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.parser == "whatsapp_export"
    assert entry.source_tag is not None
    assert entry.source_tag.startswith("tag-")
    assert entry.message_start_count == 3
    assert entry.system_event_count == 1
    assert entry.min_timestamp == "2026-05-26T15:00:01"
    assert entry.max_timestamp == "2026-05-26T15:02:00"


def test_build_registry_keeps_baseline_and_normalized_export_counts(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    export = root / "03_drive-icloud"
    export.mkdir(parents=True)
    chat = export / "standalone.txt"
    chat.write_text(
        "\n".join(
            [
                "[26/05/26, 15.00.01] Person A: baseline body",
                "\u200e[26/05/26, 15.00.02] Person B: unicode-prefixed body",
            ]
        ),
        encoding="utf-8",
    )

    entries = build_registry(root)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.message_start_count == 1
    assert entry.normalized_message_start_count == 2
    assert entry.warning_codes == ("unicode_prefixed_export_starts",)


def test_outputs_do_not_include_raw_message_text_or_raw_paths(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    mirror = root / "01_wa-mirror-db"
    mirror.mkdir(parents=True)
    secret_name = "VeryPrivateName"
    secret_body = "super secret message body"
    chat = mirror / f"00002_99999_{secret_name}.txt"
    chat.write_text(
        "\n".join(
            [
                f"=== {secret_name} | +620000000 | 1 msgs ===",
                f"2026-05-24 10:00 [SENT] {secret_body}",
            ]
        ),
        encoding="utf-8",
    )
    entries = build_registry(root)
    summaries = summarize_sources(root, entries)
    output_dir = tmp_path / "out"
    db_path = output_dir / "registry.sqlite"
    summary_path = output_dir / "registry_summary.md"

    write_sqlite(db_path=db_path, root=root, entries=entries, summaries=summaries, target_total=1)
    write_summary(
        summary_path=summary_path,
        root=root,
        db_path=db_path,
        entries=entries,
        summaries=summaries,
        target_total=1,
        mismatch_limit=10,
    )

    summary = summary_path.read_text(encoding="utf-8")
    assert secret_name not in summary
    assert secret_body not in summary
    assert "99999" not in summary
    assert "+620000000" not in summary

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT file_id, path_hash, warning_codes_json FROM corpus_files"
        ).fetchall()
    assert rows == [("wa-file-0001", entries[0].path_hash, '["filename_count_mismatch"]')]


def test_source_summaries_include_empty_top_level_dirs(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    (root / "01_wa-mirror-db").mkdir(parents=True)
    (root / "99_logs").mkdir(parents=True)
    (root / "01_wa-mirror-db" / "00001_11111_PrivateName.txt").write_text(
        "\n".join(
            [
                "=== PrivateName | +620000000 | 1 msgs ===",
                "2026-05-24 10:00 [SENT] body",
            ]
        ),
        encoding="utf-8",
    )

    entries = build_registry(root)
    summaries = {summary.source: summary for summary in summarize_sources(root, entries)}

    assert summaries["01_wa-mirror-db"].files == 1
    assert summaries["01_wa-mirror-db"].message_starts == 1
    assert summaries["99_logs"].files == 0
    assert summaries["99_logs"].message_starts == 0
