from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.build_review_manifest import (
    build_review_manifest,
    read_classified_rows,
    select_review_rows,
)
from scripts.whatsapp_corpus.build_registry import (
    build_registry,
    summarize_sources,
    write_sqlite as write_registry_sqlite,
)
from scripts.whatsapp_corpus.classify_chats import (
    classify_entries,
    read_registry_entries,
    write_sqlite as write_classification_sqlite,
)


def write_chat(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_classification_db(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "corpus"
    write_chat(
        root / "01_wa-mirror-db" / "00002_PrivateName.txt",
        [
            "2026-05-24 10:00 [SENT] private body",
            "2026-05-24 10:01 [RECEIVED] private body",
        ],
    )
    write_chat(
        root / "03_drive-icloud" / "FamilyPrivate.txt",
        ["[26/05/26, 15.00.06] Person A: body"],
    )

    registry_entries = build_registry(root)
    registry_db = tmp_path / "registry.sqlite"
    write_registry_sqlite(
        db_path=registry_db,
        root=root,
        entries=registry_entries,
        summaries=summarize_sources(root, registry_entries),
        target_total=sum(entry.message_start_count for entry in registry_entries),
    )

    classified = classify_entries(read_registry_entries(registry_db))
    classification_db = tmp_path / "chat_classification.sqlite"
    write_classification_sqlite(
        db_path=classification_db,
        registry_db=registry_db,
        classified=classified,
    )
    return root, classification_db


def test_select_review_rows_orders_by_volume(tmp_path: Path) -> None:
    _, classification_db = build_classification_db(tmp_path)
    rows = read_classified_rows(classification_db)

    selected = select_review_rows(rows, limit=1, gates=set(), labels=set())

    assert len(selected) == 1
    assert selected[0].message_start_count == 2


def test_select_review_rows_filters_by_source(tmp_path: Path) -> None:
    _, classification_db = build_classification_db(tmp_path)
    rows = read_classified_rows(classification_db)

    selected = select_review_rows(
        rows,
        limit=10,
        gates=set(),
        labels=set(),
        sources={"03_drive-icloud"},
    )

    assert len(selected) == 1
    assert selected[0].source == "03_drive-icloud"


def test_build_review_manifest_writes_private_paths_but_safe_summary(tmp_path: Path) -> None:
    root, classification_db = build_classification_db(tmp_path)
    output_dir = tmp_path / "review"
    private_manifest = output_dir / "review_manifest.local.tsv"
    summary_path = output_dir / "review_manifest_summary.md"

    rows = build_review_manifest(
        root=root,
        classification_db=classification_db,
        private_manifest_path=private_manifest,
        summary_path=summary_path,
        limit=10,
        gates=set(),
        labels=set(),
    )

    assert len(rows) == 2
    private_text = private_manifest.read_text(encoding="utf-8")
    summary = summary_path.read_text(encoding="utf-8")
    assert "PrivateName" in private_text
    assert "FamilyPrivate" in private_text
    assert "PrivateName" not in summary
    assert "FamilyPrivate" not in summary
    assert "private body" not in summary
    assert "review_manifest.local.tsv" in summary

    with sqlite3.connect(classification_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM classified_chats").fetchone()[0]
    assert count == 2
