from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_owner_decision_event_capture import (
    build_owner_decision_event_capture,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "whatsapp_corpus"
    / "build_owner_decision_event_capture.py"
)


def _write_approve_reject_ledger_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE approve_reject_ledger_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                brief_count INTEGER NOT NULL,
                queue_item_count INTEGER NOT NULL,
                ledger_entry_count INTEGER NOT NULL,
                pending_decision_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE approve_reject_ledger_entries (
                entry_id TEXT PRIMARY KEY,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                ledger_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                next_actor TEXT NOT NULL,
                queue_status TEXT NOT NULL,
                decision_status TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                allowed_decisions_json TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                immutable_event_type TEXT NOT NULL,
                ledger_entry_hash TEXT NOT NULL UNIQUE,
                ledger_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO approve_reject_ledger_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, pending_decision_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 4, 2, 2, 2, 2, 2, 2, 0, 0)
            """,
            (
                "2026-06-17T18:00:00+00:00",
                "2026-06-17T17:00:00+00:00",
                "local_only_approve_reject_ledger_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "ledger-entry-followup",
                "approval-route-followup",
                "card-owner-followup",
                "owner-brief-followup",
                "owner-pack-followup",
                1,
                "sahira",
                "approve_client_recovery_followup",
                "now",
                "owner_now",
                "owner",
                "waiting_owner_decision",
                "awaiting_owner_decision",
                "pending",
                "approve_recovery_followup_after_review",
                "owner_review_client_followup_draft",
                "a" * 64,
            ),
            (
                "ledger-entry-status",
                "approval-route-status",
                "card-owner-status",
                "owner-brief-status",
                "owner-pack-status",
                2,
                "ari",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
                "owner",
                "waiting_owner_decision",
                "awaiting_owner_decision",
                "pending",
                "approve_status_escalation_after_review",
                "owner_review_status_escalation_draft",
                "b" * 64,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO approve_reject_ledger_entries (
                entry_id, route_id, case_card_id, brief_id, pack_id, ledger_rank,
                assigned_lane, decision_type, decision_priority, route_bucket,
                next_actor, queue_status, decision_status, owner_decision,
                allowed_decisions_json, recommended_decision, draft_action_type,
                immutable_event_type, ledger_entry_hash, ledger_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row[0:14],
                    json.dumps(["approve", "reject", "defer"]),
                    row[14],
                    row[15],
                    "decision_slot_opened",
                    row[16],
                    json.dumps(
                        {
                            "schema_version": "approve_reject_ledger.v1",
                            "raw_text_included": False,
                            "send_whatsapp": False,
                            "crm_mutation": False,
                            "requires_human_approval": True,
                        },
                        sort_keys=True,
                    ),
                )
                for row in rows
            ],
        )
        conn.commit()


def test_build_owner_decision_event_capture_keeps_missing_events_awaiting_owner(
    tmp_path: Path,
) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    output_dir = tmp_path / "owner-decision-events"
    summary_path = output_dir / "owner_decision_event_capture_summary.md"
    _write_approve_reject_ledger_db(ledger_db)

    result = build_owner_decision_event_capture(
        ledger_db=ledger_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T19:00:00+00:00",
    )

    assert result.source_case_count == 4
    assert result.owner_item_count == 2
    assert result.pack_count == 2
    assert result.brief_count == 2
    assert result.queue_item_count == 2
    assert result.ledger_entry_count == 2
    assert result.captured_event_count == 0
    assert result.awaiting_input_count == 2
    assert result.output_db == output_dir / "owner_decision_event_capture.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.capture_status_counts == {"awaiting_owner_input": 2}
    assert result.owner_decision_counts == {"pending": 2}
    assert result.event_type_counts == {"owner_decision_not_submitted": 2}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, entry_id, route_id, event_rank, assigned_lane,
                   decision_type, route_bucket, capture_status, owner_decision,
                   event_type, event_source, event_actor, allowed_decisions_json,
                   decision_note, send_whatsapp, crm_mutation,
                   requires_human_approval, event_hash, event_payload_json
            FROM owner_decision_event_rows
            ORDER BY event_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count, brief_count,
                   queue_item_count, ledger_entry_count, captured_event_count,
                   awaiting_input_count, send_whatsapp_count, crm_mutation_count
            FROM owner_decision_event_capture_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (4, 2, 2, 2, 2, 2, 0, 2, 0, 0)
    assert rows[0][0:12] == (
        "card-owner-followup",
        "ledger-entry-followup",
        "approval-route-followup",
        1,
        "sahira",
        "approve_client_recovery_followup",
        "owner_now",
        "awaiting_owner_input",
        "pending",
        "owner_decision_not_submitted",
        "local_owner_event_capture",
        "owner",
    )
    assert json.loads(rows[0][12]) == ["approve", "reject", "defer"]
    assert rows[0][13:17] == ("owner_decision_required", 0, 0, 1)
    assert len(rows[0][17]) == 64
    int(rows[0][17], 16)

    payload = json.loads(rows[0][18])
    assert payload["schema_version"] == "owner_decision_event_capture.v1"
    assert payload["privacy_mode"] == "local_only_owner_decision_event_no_raw_text"
    assert payload["source_ledger_rank"] == 1
    assert payload["capture_status"] == "awaiting_owner_input"
    assert payload["owner_decision"] == "pending"
    assert payload["event_type"] == "owner_decision_not_submitted"
    assert payload["event_actor"] == "owner"
    assert payload["decision_note"] == "owner_decision_required"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Decision Event Capture Summary" in summary
    assert "| Source cases | 4 |" in summary
    assert "| Ledger entries | 2 |" in summary
    assert "| Captured owner events | 0 |" in summary
    assert "| Awaiting owner input | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-followup" not in summary
    assert "ledger-entry-followup" not in summary
    assert "approval-route-followup" not in summary
    assert "owner-brief-followup" not in summary
    assert "owner-pack-followup" not in summary


def test_build_owner_decision_event_capture_captures_local_owner_events(
    tmp_path: Path,
) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    output_dir = tmp_path / "owner-decision-events"
    summary_path = output_dir / "owner_decision_event_capture_summary.md"
    owner_events_jsonl = output_dir / "owner_events.local.jsonl"
    _write_approve_reject_ledger_db(ledger_db)
    output_dir.mkdir(parents=True, exist_ok=True)
    owner_events_jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "entry_id": "ledger-entry-followup",
                        "owner_decision": "approve",
                        "decision_note": "approved recovery follow-up",
                        "event_actor": "owner",
                        "event_recorded_at_utc": "2026-06-17T19:01:00+00:00",
                    }
                ),
                json.dumps(
                    {
                        "entry_id": "ledger-entry-status",
                        "owner_decision": "defer",
                        "decision_note": "wait for immigration evidence",
                        "event_actor": "owner",
                        "event_recorded_at_utc": "2026-06-17T19:02:00+00:00",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = build_owner_decision_event_capture(
        ledger_db=ledger_db,
        owner_events_jsonl=owner_events_jsonl,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T19:00:00+00:00",
    )

    assert result.captured_event_count == 2
    assert result.awaiting_input_count == 0
    assert result.capture_status_counts == {"captured": 2}
    assert result.owner_decision_counts == {"approve": 1, "defer": 1}
    assert result.event_type_counts == {"owner_decision_captured": 2}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT entry_id, capture_status, owner_decision, event_type,
                   decision_note, event_hash
            FROM owner_decision_event_rows
            ORDER BY event_rank
            """
        ).fetchall()

    assert rows[0][0:5] == (
        "ledger-entry-followup",
        "captured",
        "approve",
        "owner_decision_captured",
        "approved recovery follow-up",
    )
    assert rows[1][0:5] == (
        "ledger-entry-status",
        "captured",
        "defer",
        "owner_decision_captured",
        "wait for immigration evidence",
    )
    assert len({row[5] for row in rows}) == 2
    assert all(len(row[5]) == 64 for row in rows)


def test_build_owner_decision_event_capture_rejects_invalid_owner_decision(
    tmp_path: Path,
) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    output_dir = tmp_path / "owner-decision-events"
    owner_events_jsonl = output_dir / "owner_events.local.jsonl"
    _write_approve_reject_ledger_db(ledger_db)
    output_dir.mkdir(parents=True, exist_ok=True)
    owner_events_jsonl.write_text(
        json.dumps(
            {
                "entry_id": "ledger-entry-followup",
                "owner_decision": "send_now",
                "decision_note": "bad",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Owner decision is not allowed"):
        build_owner_decision_event_capture(
            ledger_db=ledger_db,
            owner_events_jsonl=owner_events_jsonl,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_build_owner_decision_event_capture_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "approve_reject_ledger.bad.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Approve/Reject Ledger DB",
    ):
        build_owner_decision_event_capture(
            ledger_db=unexpected_db,
            output_dir=tmp_path / "owner-decision-events",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_decision_details(tmp_path: Path) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    output_dir = tmp_path / "owner-decision-events"
    summary_path = output_dir / "owner_decision_event_capture_summary.md"
    _write_approve_reject_ledger_db(ledger_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ledger-db",
            str(ledger_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T19:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "awaiting_input_count": 2,
        "brief_count": 2,
        "captured_event_count": 0,
        "crm_mutation_count": 0,
        "ledger_entry_count": 2,
        "owner_item_count": 2,
        "pack_count": 2,
        "queue_item_count": 2,
        "send_whatsapp_count": 0,
        "source_case_count": 4,
    }
    assert "card-owner-followup" not in result.stdout
    assert "ledger-entry-followup" not in result.stdout
    assert "approval-route-followup" not in result.stdout
    assert "owner-brief-followup" not in result.stdout
    assert "owner-pack-followup" not in result.stdout
