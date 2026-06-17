from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_owner_decision_intake import (
    build_owner_decision_intake,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_decision_intake.py"


def _write_operator_packet_review_console_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_packet_review_console_runs (
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
                event_row_count INTEGER NOT NULL,
                work_order_count INTEGER NOT NULL,
                packet_count INTEGER NOT NULL,
                review_item_count INTEGER NOT NULL,
                owner_decision_item_count INTEGER NOT NULL,
                operator_ready_item_count INTEGER NOT NULL,
                deferred_item_count INTEGER NOT NULL,
                rejected_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_packet_review_items (
                review_item_id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                work_order_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                review_rank INTEGER NOT NULL,
                source_packet_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                packet_status TEXT NOT NULL,
                packet_type TEXT NOT NULL,
                packet_gate TEXT NOT NULL,
                packet_action TEXT NOT NULL,
                operator_instruction TEXT NOT NULL,
                escalation_target TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                review_priority TEXT NOT NULL,
                visible_owner_action TEXT NOT NULL,
                operator_action TEXT NOT NULL,
                console_instruction TEXT NOT NULL,
                review_gate TEXT NOT NULL,
                action_lock TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_packet_hash TEXT NOT NULL,
                review_hash TEXT NOT NULL UNIQUE,
                review_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO operator_packet_review_console_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, event_row_count,
                work_order_count, packet_count, review_item_count,
                owner_decision_item_count, operator_ready_item_count,
                deferred_item_count, rejected_item_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 8, 4, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 0, 0)
            """,
            (
                "2026-06-17T22:00:00+00:00",
                "2026-06-17T21:00:00+00:00",
                "local_only_operator_packet_review_console_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "operator-packet-review-item-pending",
                "operator-packet-pending",
                "post-work-order-pending",
                "owner-event-pending",
                "ledger-entry-pending",
                "approval-route-pending",
                "card-owner-pending",
                "owner-brief-pending",
                "owner-pack-pending",
                1,
                1,
                "sahira",
                "owner",
                "approve_client_recovery_followup",
                "now",
                "owner_now",
                "pending",
                "blocked_awaiting_owner_decision",
                "owner_decision_required_packet",
                "owner_input_required",
                "wait_for_owner_decision",
                "no_operator_execution_until_owner_decides",
                "owner",
                "waiting_owner_decision",
                "owner_decision_inbox",
                "owner_now",
                "capture_owner_decision",
                "no_operator_action",
                "owner_must_approve_reject_or_defer_before_team_work",
                "owner_input_required",
                "locked_until_owner_decision",
                "owner_decision_required",
                "a" * 64,
                "b" * 64,
            ),
            (
                "operator-packet-review-item-ready",
                "operator-packet-ready",
                "post-work-order-ready",
                "owner-event-ready",
                "ledger-entry-ready",
                "approval-route-ready",
                "card-owner-ready",
                "owner-brief-ready",
                "owner-pack-ready",
                2,
                2,
                "sahira",
                "sahira",
                "approve_client_recovery_followup",
                "now",
                "owner_now",
                "approve",
                "ready_for_operator_review",
                "client_recovery_followup_packet",
                "human_review_before_send_or_crm",
                "prepare_client_recovery_followup_for_human_review",
                "review_client_recovery_followup_before_any_send",
                "owner",
                "ready_for_human_review",
                "operator_review_queue",
                "operator_now",
                "no_owner_action_required",
                "review_packet_before_send_or_crm",
                "review_ready_packet_and_request_human_approval",
                "human_review_before_send_or_crm",
                "locked_until_human_review",
                "approved recovery follow-up",
                "c" * 64,
                "d" * 64,
            ),
            (
                "operator-packet-review-item-defer",
                "operator-packet-defer",
                "post-work-order-defer",
                "owner-event-defer",
                "ledger-entry-defer",
                "approval-route-defer",
                "card-owner-defer",
                "owner-brief-defer",
                "owner-pack-defer",
                3,
                3,
                "ari",
                "owner",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
                "defer",
                "deferred_owner_followup",
                "owner_deferred_packet",
                "owner_revisit_required",
                "schedule_owner_revisit",
                "hold_operator_execution_until_owner_revisits",
                "owner",
                "deferred_owner_revisit",
                "owner_revisit_queue",
                "owner_revisit",
                "revisit_deferred_decision",
                "no_operator_action",
                "owner_must_revisit_deferred_packet",
                "owner_revisit_required",
                "locked_until_owner_revisit",
                "wait for immigration evidence",
                "e" * 64,
                "f" * 64,
            ),
            (
                "operator-packet-review-item-reject",
                "operator-packet-reject",
                "post-work-order-reject",
                "owner-event-reject",
                "ledger-entry-reject",
                "approval-route-reject",
                "card-owner-reject",
                "owner-brief-reject",
                "owner-pack-reject",
                4,
                4,
                "ari",
                "owner",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
                "reject",
                "rejected_no_action",
                "owner_rejected_packet",
                "no_external_action",
                "record_rejection_and_stop",
                "do_not_execute_rejected_work_order",
                "owner",
                "rejected_closed",
                "closed_no_action",
                "closed",
                "no_action",
                "no_operator_action",
                "no_action_packet_rejected",
                "no_external_action",
                "closed_no_external_action",
                "do not proceed",
                "1" * 64,
                "2" * 64,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO operator_packet_review_items (
                review_item_id, packet_id, work_order_id, event_id, entry_id,
                route_id, case_card_id, brief_id, pack_id, review_rank,
                source_packet_rank, assigned_lane, operator_lane, decision_type,
                decision_priority, route_bucket, owner_decision, packet_status,
                packet_type, packet_gate, packet_action, operator_instruction,
                escalation_target, review_state, console_bucket, review_priority,
                visible_owner_action, operator_action, console_instruction,
                review_gate, action_lock, decision_note, source_packet_hash,
                review_hash, review_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "operator_packet_review_console.v1",
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


def test_build_owner_decision_intake_exports_replay_jsonl_for_owner_actions(
    tmp_path: Path,
) -> None:
    review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-intake"
    summary_path = output_dir / "owner_decision_intake_summary.md"
    owner_decisions_jsonl = output_dir / "owner_decisions.local.jsonl"
    _write_operator_packet_review_console_db(review_db)
    output_dir.mkdir(parents=True, exist_ok=True)
    owner_decisions_jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "review_item_id": "operator-packet-review-item-pending",
                        "owner_decision": "approve",
                        "decision_note": "approved recovery follow-up",
                        "event_actor": "owner",
                        "event_recorded_at_utc": "2026-06-17T23:01:00+00:00",
                    }
                ),
                json.dumps(
                    {
                        "packet_id": "operator-packet-defer",
                        "owner_decision": "reject",
                        "decision_note": "do not proceed after revisit",
                        "event_actor": "owner",
                        "event_recorded_at_utc": "2026-06-17T23:02:00+00:00",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = build_owner_decision_intake(
        review_console_db=review_db,
        owner_decisions_jsonl=owner_decisions_jsonl,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T23:00:00+00:00",
    )

    assert result.source_case_count == 8
    assert result.packet_count == 4
    assert result.review_item_count == 4
    assert result.intake_item_count == 4
    assert result.captured_decision_count == 2
    assert result.awaiting_owner_decision_count == 0
    assert result.awaiting_owner_revisit_count == 0
    assert result.no_owner_action_required_count == 1
    assert result.closed_item_count == 1
    assert result.replay_event_count == 2
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.output_db == output_dir / "owner_decision_intake.local.sqlite"
    assert result.output_jsonl == output_dir / "owner_events.local.jsonl"
    assert result.output_template == output_dir / "owner_decisions_template.local.jsonl"
    assert result.intake_status_counts == {
        "captured": 2,
        "closed_no_owner_action": 1,
        "no_owner_action_required": 1,
    }

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT review_item_id, packet_id, entry_id, intake_rank,
                   review_state, console_bucket, visible_owner_action,
                   submitted_owner_decision, intake_status, replay_event_status,
                   replay_event_type, event_actor, event_recorded_at_utc,
                   decision_note, send_whatsapp, crm_mutation,
                   requires_human_approval, intake_hash, intake_payload_json
            FROM owner_decision_intake_items
            ORDER BY intake_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, packet_count, review_item_count,
                   intake_item_count, captured_decision_count,
                   awaiting_owner_decision_count, awaiting_owner_revisit_count,
                   no_owner_action_required_count, closed_item_count,
                   replay_event_count, send_whatsapp_count, crm_mutation_count
            FROM owner_decision_intake_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (8, 4, 4, 4, 2, 0, 0, 1, 1, 2, 0, 0)
    assert rows[0][0:17] == (
        "operator-packet-review-item-pending",
        "operator-packet-pending",
        "ledger-entry-pending",
        1,
        "waiting_owner_decision",
        "owner_decision_inbox",
        "capture_owner_decision",
        "approve",
        "captured",
        "emitted_to_owner_events_jsonl",
        "owner_decision_intake_captured",
        "owner",
        "2026-06-17T23:01:00+00:00",
        "approved recovery follow-up",
        0,
        0,
        1,
    )
    assert rows[1][7:11] == (
        "approve",
        "no_owner_action_required",
        "not_emitted",
        "owner_action_not_required",
    )
    assert rows[2][7:11] == (
        "reject",
        "captured",
        "emitted_to_owner_events_jsonl",
        "owner_decision_intake_captured",
    )
    assert rows[3][7:11] == (
        "reject",
        "closed_no_owner_action",
        "not_emitted",
        "owner_action_closed",
    )
    assert len({row[17] for row in rows}) == 4
    assert all(len(row[17]) == 64 for row in rows)

    payload = json.loads(rows[0][18])
    assert payload["schema_version"] == "owner_decision_intake.v1"
    assert payload["privacy_mode"] == "local_only_owner_decision_intake_no_raw_text"
    assert payload["source_review_rank"] == 1
    assert payload["submitted_owner_decision"] == "approve"
    assert payload["intake_status"] == "captured"
    assert payload["replay_event_status"] == "emitted_to_owner_events_jsonl"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    replay_rows = [
        json.loads(line)
        for line in result.output_jsonl.read_text(encoding="utf-8").splitlines()
    ]
    assert replay_rows == [
        {
            "decision_note": "approved recovery follow-up",
            "entry_id": "ledger-entry-pending",
            "event_actor": "owner",
            "event_recorded_at_utc": "2026-06-17T23:01:00+00:00",
            "owner_decision": "approve",
        },
        {
            "decision_note": "do not proceed after revisit",
            "entry_id": "ledger-entry-defer",
            "event_actor": "owner",
            "event_recorded_at_utc": "2026-06-17T23:02:00+00:00",
            "owner_decision": "reject",
        },
    ]
    assert result.output_template.read_text(encoding="utf-8") == ""

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Decision Intake Summary" in summary
    assert "| Source cases | 8 |" in summary
    assert "| Review items | 4 |" in summary
    assert "| Captured decisions | 2 |" in summary
    assert "| Replay events | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "operator-packet-review-item-pending" not in summary
    assert "operator-packet-pending" not in summary
    assert "ledger-entry-pending" not in summary


def test_build_owner_decision_intake_keeps_missing_owner_items_awaiting(
    tmp_path: Path,
) -> None:
    review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-intake"
    _write_operator_packet_review_console_db(review_db)

    result = build_owner_decision_intake(
        review_console_db=review_db,
        output_dir=output_dir,
        summary_path=output_dir / "summary.md",
        generated_at_utc="2026-06-17T23:00:00+00:00",
    )

    assert result.captured_decision_count == 0
    assert result.awaiting_owner_decision_count == 1
    assert result.awaiting_owner_revisit_count == 1
    assert result.no_owner_action_required_count == 1
    assert result.closed_item_count == 1
    assert result.replay_event_count == 0
    assert result.output_jsonl.read_text(encoding="utf-8") == ""
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
            "event_recorded_at_utc": "2026-06-17T23:00:00+00:00",
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
            "event_recorded_at_utc": "2026-06-17T23:00:00+00:00",
            "owner_decision": "",
            "packet_id": "operator-packet-defer",
            "review_item_id": "operator-packet-review-item-defer",
            "review_state": "deferred_owner_revisit",
        },
    ]
    assert result.intake_status_counts == {
        "awaiting_owner_decision": 1,
        "awaiting_owner_revisit": 1,
        "closed_no_owner_action": 1,
        "no_owner_action_required": 1,
    }


def test_build_owner_decision_intake_rejects_invalid_decision(
    tmp_path: Path,
) -> None:
    review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-intake"
    owner_decisions_jsonl = output_dir / "owner_decisions.local.jsonl"
    _write_operator_packet_review_console_db(review_db)
    output_dir.mkdir(parents=True, exist_ok=True)
    owner_decisions_jsonl.write_text(
        json.dumps(
            {
                "review_item_id": "operator-packet-review-item-pending",
                "owner_decision": "send_now",
                "decision_note": "bad",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Owner decision is not allowed"):
        build_owner_decision_intake(
            review_console_db=review_db,
            owner_decisions_jsonl=owner_decisions_jsonl,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_build_owner_decision_intake_rejects_non_owner_action_item(
    tmp_path: Path,
) -> None:
    review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-intake"
    owner_decisions_jsonl = output_dir / "owner_decisions.local.jsonl"
    _write_operator_packet_review_console_db(review_db)
    output_dir.mkdir(parents=True, exist_ok=True)
    owner_decisions_jsonl.write_text(
        json.dumps(
            {
                "review_item_id": "operator-packet-review-item-ready",
                "owner_decision": "reject",
                "decision_note": "bad target",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not owner-actionable"):
        build_owner_decision_intake(
            review_console_db=review_db,
            owner_decisions_jsonl=owner_decisions_jsonl,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_build_owner_decision_intake_rejects_duplicate_references(
    tmp_path: Path,
) -> None:
    review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-intake"
    owner_decisions_jsonl = output_dir / "owner_decisions.local.jsonl"
    _write_operator_packet_review_console_db(review_db)
    output_dir.mkdir(parents=True, exist_ok=True)
    owner_decisions_jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "review_item_id": "operator-packet-review-item-pending",
                        "owner_decision": "approve",
                    }
                ),
                json.dumps(
                    {
                        "entry_id": "ledger-entry-pending",
                        "owner_decision": "defer",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate owner decision intake"):
        build_owner_decision_intake(
            review_console_db=review_db,
            owner_decisions_jsonl=owner_decisions_jsonl,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_build_owner_decision_intake_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "operator_packet_review_console.bad.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Operator Packet Review Console DB",
    ):
        build_owner_decision_intake(
            review_console_db=unexpected_db,
            output_dir=tmp_path / "owner-decision-intake",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_intake_details(tmp_path: Path) -> None:
    review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-intake"
    summary_path = output_dir / "owner_decision_intake_summary.md"
    _write_operator_packet_review_console_db(review_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--review-console-db",
            str(review_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T23:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "awaiting_owner_decision_count": 1,
        "awaiting_owner_revisit_count": 1,
        "captured_decision_count": 0,
        "closed_item_count": 1,
        "crm_mutation_count": 0,
        "intake_item_count": 4,
        "no_owner_action_required_count": 1,
        "packet_count": 4,
        "replay_event_count": 0,
        "review_item_count": 4,
        "send_whatsapp_count": 0,
        "source_case_count": 8,
    }
    assert "operator-packet-review-item-pending" not in result.stdout
    assert "operator-packet-pending" not in result.stdout
    assert "ledger-entry-pending" not in result.stdout
