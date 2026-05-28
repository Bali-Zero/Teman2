from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.build_registry import (
    build_registry,
    summarize_sources,
    write_sqlite as write_registry_sqlite,
)
from scripts.whatsapp_corpus.classify_chats import (
    classify_entries,
    read_registry_entries,
    write_sqlite as write_classification_sqlite,
    write_summary,
)


def write_chat(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_test_registry(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    write_chat(
        root / "01_wa-mirror-db" / "00002_12345_PrivateName.txt",
        [
            "=== PrivateName | +620000000 | 2 msgs ===",
            "2026-05-24 10:00 [SENT] private body",
            "2026-05-24 10:01 [RECEIVED] private body",
        ],
    )
    write_chat(
        root / "02_zip-extracted" / "BulkDrive" / "Chat One" / "_chat.txt",
        [
            "[26/05/26, 15.00.01] Person A: body",
            "[26/05/26, 15.00.02] Person B: body",
        ],
    )
    write_chat(
        root / "02_zip-extracted" / "BulkDrive" / "Chat Two" / "_chat.txt",
        ["[26/05/26, 15.00.03] Person A: body"],
    )
    write_chat(
        root / "02_zip-extracted" / "TeamSource" / "Team One" / "_chat.txt",
        ["[26/05/26, 15.00.04] Person A: body"],
    )
    write_chat(
        root / "02_zip-extracted" / "TeamSource" / "Team Two" / "_chat.txt",
        ["[26/05/26, 15.00.05] Person A: body"],
    )
    write_chat(
        root / "02_zip-extracted" / "PilotSource" / "Pilot One" / "_chat.txt",
        ["[26/05/26, 15.00.06] Person A: body"],
    )
    write_chat(
        root / "03_drive-icloud" / "FamilyPrivate.txt",
        ["[26/05/26, 15.00.07] Person A: body"],
    )

    entries = build_registry(root)
    summaries = summarize_sources(root, entries)
    registry_db = tmp_path / "registry.sqlite"
    write_registry_sqlite(
        db_path=registry_db,
        root=root,
        entries=entries,
        summaries=summaries,
        target_total=sum(entry.message_start_count for entry in entries),
    )
    return registry_db


def test_classify_entries_assigns_privacy_first_gates(tmp_path: Path) -> None:
    registry_db = build_test_registry(tmp_path)
    entries = read_registry_entries(registry_db)

    classified = classify_entries(entries)

    labels = {row.classification_label for row in classified}
    gates = {row.processing_gate for row in classified}
    assert "mirror_contact_archive_unreviewed" in labels
    assert "bulk_drive_export_candidate" in labels
    assert "team_operator_archive_candidate" in labels
    assert "pilot_or_test_archive_candidate" in labels
    assert "private_drive_icloud_candidate" in labels
    assert "deny_content_mining_until_owner_allowlist" in gates
    assert "local_only_team_analysis_after_owner_approval" in gates
    assert all(row.review_required for row in classified)


def test_classification_outputs_do_not_include_raw_names_or_paths(tmp_path: Path) -> None:
    registry_db = build_test_registry(tmp_path)
    entries = read_registry_entries(registry_db)
    classified = classify_entries(entries)
    output_dir = tmp_path / "classification"
    classification_db = output_dir / "chat_classification.sqlite"
    summary_path = output_dir / "classification_summary.md"

    write_classification_sqlite(
        db_path=classification_db,
        registry_db=registry_db,
        classified=classified,
    )
    write_summary(
        summary_path=summary_path,
        registry_db=registry_db,
        classification_db=classification_db,
        classified=classified,
        review_limit=20,
    )

    summary = summary_path.read_text(encoding="utf-8")
    forbidden_terms = [
        "PrivateName",
        "BulkDrive",
        "TeamSource",
        "PilotSource",
        "FamilyPrivate",
        "+620000000",
        "private body",
    ]
    for term in forbidden_terms:
        assert term not in summary

    with sqlite3.connect(classification_db) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source, path_hash, classification_label, evidence_codes_json
            FROM classified_chats
            ORDER BY file_id
            """
        ).fetchall()

    serialized = "\n".join("|".join(str(value) for value in row) for row in rows)
    for term in forbidden_terms:
        assert term not in serialized
    assert "source_tag:hashed" in serialized
