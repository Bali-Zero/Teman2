from __future__ import annotations

from pathlib import Path

from scripts.whatsapp_corpus.resolve_refs import build_file_refs, filter_refs


def test_resolve_refs_maps_file_id_to_local_path(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    chat = root / "02_zip-extracted" / "PrivateSource" / "Private Chat" / "_chat.txt"
    chat.parent.mkdir(parents=True)
    chat.write_text("[26/05/26, 15.00.01] Person A: body", encoding="utf-8")

    refs = build_file_refs(root)
    rows = filter_refs(
        refs,
        file_ids={"wa-file-0001"},
        path_hashes=set(),
        source_tags=set(),
    )

    assert len(rows) == 1
    assert rows[0].file_id == "wa-file-0001"
    assert rows[0].path == chat
    assert rows[0].source_tag is not None


def test_resolve_refs_requires_matching_identifier(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    chat = root / "01_wa-mirror-db" / "00001_PrivateName.txt"
    chat.parent.mkdir(parents=True)
    chat.write_text("2026-05-24 10:00 [SENT] body", encoding="utf-8")

    refs = build_file_refs(root)
    rows = filter_refs(
        refs,
        file_ids={"wa-file-9999"},
        path_hashes=set(),
        source_tags=set(),
    )

    assert rows == []
