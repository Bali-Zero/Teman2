from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.tests.test_whatsapp_corpus_owner_decision_intake import (
    _write_operator_packet_review_console_db,
)
from scripts.whatsapp_corpus.build_owner_decision_inbox import (
    build_owner_decision_inbox,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_decision_inbox.py"


def test_build_owner_decision_inbox_writes_actionable_rows_and_template(
    tmp_path: Path,
) -> None:
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-inbox"
    summary_path = output_dir / "owner_decision_inbox_summary.md"
    _write_operator_packet_review_console_db(review_console_db)

    result = build_owner_decision_inbox(
        review_console_db=review_console_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-18T00:01:00+00:00",
    )

    assert result.source_case_count == 8
    assert result.source_review_item_count == 4
    assert result.inbox_item_count == 2
    assert result.waiting_decision_count == 1
    assert result.revisit_decision_count == 1
    assert result.excluded_review_item_count == 2
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.output_db == output_dir / "owner_decision_inbox.local.sqlite"
    assert result.output_template == output_dir / "owner_decisions_template.local.jsonl"

    with sqlite3.connect(result.output_db) as conn:
        run = conn.execute(
            """
            SELECT source_case_count, source_review_item_count, inbox_item_count,
                   waiting_decision_count, revisit_decision_count,
                   excluded_review_item_count, send_whatsapp_count,
                   crm_mutation_count
            FROM owner_decision_inbox_runs
            WHERE id = 1
            """
        ).fetchone()
        rows = conn.execute(
            """
            SELECT owner_inbox_item_id, review_item_id, packet_id, entry_id,
                   inbox_rank, assigned_lane, operator_lane, decision_type,
                   review_state, console_bucket, review_priority,
                   visible_owner_action, owner_decision_status,
                   template_status, allowed_decisions_json,
                   owner_decision_input, decision_note_input,
                   send_whatsapp, crm_mutation, requires_human_approval,
                   inbox_payload_json
            FROM owner_decision_inbox_items
            ORDER BY inbox_rank
            """
        ).fetchall()

    assert run == (8, 4, 2, 1, 1, 2, 0, 0)
    assert [row[1] for row in rows] == [
        "operator-packet-review-item-pending",
        "operator-packet-review-item-defer",
    ]
    assert rows[0][4:14] == (
        1,
        "sahira",
        "owner",
        "approve_client_recovery_followup",
        "waiting_owner_decision",
        "owner_decision_inbox",
        "owner_now",
        "capture_owner_decision",
        "needs_owner_decision",
        "blank_owner_decision_required",
    )
    assert rows[1][4:14] == (
        2,
        "ari",
        "owner",
        "approve_immigration_status_escalation",
        "deferred_owner_revisit",
        "owner_revisit_queue",
        "owner_revisit",
        "revisit_deferred_decision",
        "needs_owner_revisit",
        "blank_owner_decision_required",
    )
    assert json.loads(rows[0][14]) == ["approve", "reject", "defer"]
    assert rows[0][15] == ""
    assert rows[0][16] == ""
    assert {row[17] for row in rows} == {0}
    assert {row[18] for row in rows} == {0}
    assert {row[19] for row in rows} == {1}
    payload = json.loads(rows[0][20])
    assert payload["schema_version"] == "owner_decision_inbox.v1"
    assert payload["privacy_mode"] == "local_only_owner_decision_inbox_no_raw_text"
    assert payload["source_review_rank"] == 1
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    template_rows = [
        json.loads(line)
        for line in result.output_template.read_text(encoding="utf-8").splitlines()
    ]
    assert template_rows == [
        {
            "allowed_decisions": ["approve", "reject", "defer"],
            "assigned_lane": "sahira",
            "console_bucket": "owner_decision_inbox",
            "decision_note": "",
            "decision_type": "approve_client_recovery_followup",
            "entry_id": "ledger-entry-pending",
            "event_actor": "owner",
            "event_recorded_at_utc": "",
            "owner_decision": "",
            "packet_id": "operator-packet-pending",
            "review_item_id": "operator-packet-review-item-pending",
            "review_state": "waiting_owner_decision",
        },
        {
            "allowed_decisions": ["approve", "reject", "defer"],
            "assigned_lane": "ari",
            "console_bucket": "owner_revisit_queue",
            "decision_note": "",
            "decision_type": "approve_immigration_status_escalation",
            "entry_id": "ledger-entry-defer",
            "event_actor": "owner",
            "event_recorded_at_utc": "",
            "owner_decision": "",
            "packet_id": "operator-packet-defer",
            "review_item_id": "operator-packet-review-item-defer",
            "review_state": "deferred_owner_revisit",
        },
    ]

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Decision Inbox Summary" in summary
    assert "| Source cases | 8 |" in summary
    assert "| Owner inbox items | 2 |" in summary
    assert "| Waiting owner decision | 1 |" in summary
    assert "| Owner revisit needed | 1 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "operator-packet-review-item-pending" not in summary
    assert "ledger-entry-pending" not in summary


def test_build_owner_decision_inbox_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "owner_decision_intake.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected"):
        build_owner_decision_inbox(
            review_console_db=unexpected_db,
            output_dir=tmp_path / "owner-decision-inbox",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_owner_item_ids(tmp_path: Path) -> None:
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-inbox"
    summary_path = output_dir / "owner_decision_inbox_summary.md"
    _write_operator_packet_review_console_db(review_console_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--review-console-db",
            str(review_console_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-18T00:01:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "crm_mutation_count": 0,
        "excluded_review_item_count": 2,
        "inbox_item_count": 2,
        "revisit_decision_count": 1,
        "send_whatsapp_count": 0,
        "source_case_count": 8,
        "source_review_item_count": 4,
        "waiting_decision_count": 1,
    }
    assert "operator-packet-review-item-pending" not in result.stdout
    assert "ledger-entry-pending" not in result.stdout
