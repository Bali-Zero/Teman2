from __future__ import annotations

from pathlib import Path

from scripts.whatsapp_corpus.parse_full_corpus import parse_full_corpus_to_outputs


def test_parse_full_corpus_writes_raw_local_db_and_safe_summary(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    source_dir = root / "02_zip-extracted" / "Team"
    source_dir.mkdir(parents=True)
    (source_dir / "_chat.txt").write_text(
        "\u200e[01/05/26, 08.00.00] Alice: Hello raw message\n"
        "continued line\n"
        "[01/05/26, 09.00.00] Bob: Email test@example.com and phone +62 812 3456 7890\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "full_messages.local.sqlite"
    summary_path = tmp_path / "full_corpus_parse_summary.md"

    messages, summaries = parse_full_corpus_to_outputs(
        corpus_root=root,
        db_path=db_path,
        summary_path=summary_path,
    )

    assert len(summaries) == 1
    assert len(messages) == 2
    assert messages[0].body_text == "Hello raw message\ncontinued line"
    assert messages[1].has_email is True
    assert messages[1].has_phone_like is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "Hello raw message" not in summary
    assert "test@example.com" not in summary
    assert "+62" not in summary
    assert "| Files parsed | 1 |" in summary
    assert "| Parsed messages | 2 |" in summary
