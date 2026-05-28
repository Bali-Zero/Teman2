from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.whatsapp_corpus.parse_allowed_messages import parse_allowlist_to_outputs


def write_allowlist(path: Path, chat_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "file_id": "wa-file-0001",
        "source": "02_zip-extracted",
        "source_tag": "tag-private",
        "path_hash": "hash-private",
        "classification_label": "team_operator_archive_candidate",
        "privacy_tier": "team_sensitive",
        "processing_gate": "local_only_team_analysis_after_owner_approval",
        "effective_decision": "allow_team_local",
        "decision_bucket": "allow",
        "local_path": chat_path.as_posix(),
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_parse_allowlist_writes_raw_sqlite_and_safe_summary(tmp_path: Path) -> None:
    chat = tmp_path / "PrivateSource" / "Private Chat" / "_chat.txt"
    chat.parent.mkdir(parents=True)
    chat.write_text(
        "\n".join(
            [
                "[26/05/26, 15.00.01] Private Sender: first private body",
                "continuation line",
                "\u200e[26/05/26, 15.00.02] Private Sender: second body https://example.com",
                "[26/05/26, 15.00.03] Messages are end-to-end encrypted.",
            ]
        ),
        encoding="utf-8",
    )
    allowlist = tmp_path / "content_allowlist.local.jsonl"
    output_dir = tmp_path / "analysis"
    write_allowlist(allowlist, chat)

    messages, summaries = parse_allowlist_to_outputs(
        allowlist_path=allowlist,
        output_dir=output_dir,
    )

    assert len(messages) == 3
    assert summaries[0].parsed_messages == 3
    assert summaries[0].system_events == 1
    summary = (output_dir / "allowed_messages_summary.md").read_text(encoding="utf-8")
    assert "Private Sender" not in summary
    assert "private body" not in summary
    assert "PrivateSource" not in summary
    assert str(tmp_path) not in summary

    with sqlite3.connect(output_dir / "allowed_messages.local.sqlite") as conn:
        rows = conn.execute(
            "SELECT sender_raw, body_text, has_url FROM parsed_messages ORDER BY message_index"
        ).fetchall()
    assert rows[0][0] == "Private Sender"
    assert "first private body" in rows[0][1]
    assert rows[1][2] == 1


def test_parse_allowlist_handles_mirror_format(tmp_path: Path) -> None:
    chat = tmp_path / "01_wa-mirror-db" / "00002_Private.txt"
    chat.parent.mkdir(parents=True)
    chat.write_text(
        "\n".join(
            [
                "2026-05-24 10:00 [SENT] first",
                "2026-05-24 10:01 [RECEIVED] second",
            ]
        ),
        encoding="utf-8",
    )
    allowlist = tmp_path / "content_allowlist.local.jsonl"
    row = {
        "file_id": "wa-file-0002",
        "source": "01_wa-mirror-db",
        "source_tag": None,
        "path_hash": "hash-private",
        "classification_label": "mirror_contact_archive_unreviewed",
        "privacy_tier": "mixed_sensitive",
        "processing_gate": "manual_review_before_content_mining",
        "effective_decision": "allow_team_local",
        "decision_bucket": "allow",
        "local_path": chat.as_posix(),
    }
    allowlist.write_text(json.dumps(row) + "\n", encoding="utf-8")

    messages, _ = parse_allowlist_to_outputs(
        allowlist_path=allowlist,
        output_dir=tmp_path / "analysis",
    )

    assert len(messages) == 2
    assert messages[0].direction == "SENT"
    assert messages[1].direction == "RECEIVED"
