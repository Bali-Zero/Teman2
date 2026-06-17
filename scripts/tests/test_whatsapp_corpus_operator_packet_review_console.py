from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_operator_packet_review_console import (
    build_operator_packet_review_console,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "whatsapp_corpus"
    / "build_operator_packet_review_console.py"
)


def _write_operator_execution_packets_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_execution_packet_runs (
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
                ready_packet_count INTEGER NOT NULL,
                blocked_packet_count INTEGER NOT NULL,
                deferred_packet_count INTEGER NOT NULL,
                rejected_packet_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_execution_packets (
                packet_id TEXT PRIMARY KEY,
                work_order_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                packet_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                source_work_order_status TEXT NOT NULL,
                packet_status TEXT NOT NULL,
                packet_type TEXT NOT NULL,
                packet_gate TEXT NOT NULL,
                packet_action TEXT NOT NULL,
                operator_instruction TEXT NOT NULL,
                escalation_target TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_work_order_hash TEXT NOT NULL,
                packet_hash TEXT NOT NULL UNIQUE,
                packet_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO operator_execution_packet_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, event_row_count,
                work_order_count, packet_count, ready_packet_count,
                blocked_packet_count, deferred_packet_count,
                rejected_packet_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 8, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 0, 0)
            """,
            (
                "2026-06-17T21:00:00+00:00",
                "2026-06-17T20:00:00+00:00",
                "local_only_operator_execution_packet_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "operator-packet-pending",
                "post-work-order-pending",
                "owner-event-pending",
                "ledger-entry-pending",
                "approval-route-pending",
                "card-owner-pending",
                "owner-brief-pending",
                "owner-pack-pending",
                1,
                "sahira",
                "owner",
                "approve_client_recovery_followup",
                "now",
                "owner_now",
                "pending",
                "blocked_awaiting_owner_decision",
                "blocked_awaiting_owner_decision",
                "owner_decision_required_packet",
                "owner_input_required",
                "wait_for_owner_decision",
                "no_operator_execution_until_owner_decides",
                "owner",
                "owner_decision_required",
                "a" * 64,
                "e" * 64,
            ),
            (
                "operator-packet-approve",
                "post-work-order-approve",
                "owner-event-approve",
                "ledger-entry-approve",
                "approval-route-approve",
                "card-owner-approve",
                "owner-brief-approve",
                "owner-pack-approve",
                2,
                "sahira",
                "sahira",
                "approve_client_recovery_followup",
                "now",
                "owner_now",
                "approve",
                "ready_for_operator_review",
                "ready_for_operator_review",
                "client_recovery_followup_packet",
                "human_review_before_send_or_crm",
                "prepare_client_recovery_followup_for_human_review",
                "review_client_recovery_followup_before_any_send",
                "owner",
                "approved recovery follow-up",
                "b" * 64,
                "f" * 64,
            ),
            (
                "operator-packet-defer",
                "post-work-order-defer",
                "owner-event-defer",
                "ledger-entry-defer",
                "approval-route-defer",
                "card-owner-defer",
                "owner-brief-defer",
                "owner-pack-defer",
                3,
                "ari",
                "owner",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
                "defer",
                "deferred_owner_followup",
                "deferred_owner_followup",
                "owner_deferred_packet",
                "owner_revisit_required",
                "schedule_owner_revisit",
                "hold_operator_execution_until_owner_revisits",
                "owner",
                "wait for immigration evidence",
                "c" * 64,
                "1" * 64,
            ),
            (
                "operator-packet-reject",
                "post-work-order-reject",
                "owner-event-reject",
                "ledger-entry-reject",
                "approval-route-reject",
                "card-owner-reject",
                "owner-brief-reject",
                "owner-pack-reject",
                4,
                "ari",
                "owner",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
                "reject",
                "rejected_no_action",
                "rejected_no_action",
                "owner_rejected_packet",
                "no_external_action",
                "record_rejection_and_stop",
                "do_not_execute_rejected_work_order",
                "owner",
                "do not proceed",
                "d" * 64,
                "2" * 64,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO operator_execution_packets (
                packet_id, work_order_id, event_id, entry_id, route_id,
                case_card_id, brief_id, pack_id, packet_rank, assigned_lane,
                operator_lane, decision_type, decision_priority, route_bucket,
                owner_decision, source_work_order_status, packet_status,
                packet_type, packet_gate, packet_action, operator_instruction,
                escalation_target, decision_note, source_work_order_hash,
                packet_hash, packet_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "operator_execution_packets.v1",
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


def test_build_operator_packet_review_console_maps_packets_to_review_items(
    tmp_path: Path,
) -> None:
    packets_db = tmp_path / "operator_execution_packets.local.sqlite"
    output_dir = tmp_path / "operator-packet-review-console"
    summary_path = output_dir / "operator_packet_review_console_summary.md"
    _write_operator_execution_packets_db(packets_db)

    result = build_operator_packet_review_console(
        packets_db=packets_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T22:00:00+00:00",
    )

    assert result.source_case_count == 8
    assert result.owner_item_count == 4
    assert result.pack_count == 4
    assert result.brief_count == 4
    assert result.queue_item_count == 4
    assert result.ledger_entry_count == 4
    assert result.event_row_count == 4
    assert result.work_order_count == 4
    assert result.packet_count == 4
    assert result.review_item_count == 4
    assert result.owner_decision_item_count == 1
    assert result.operator_ready_item_count == 1
    assert result.deferred_item_count == 1
    assert result.rejected_item_count == 1
    assert result.output_db == output_dir / "operator_packet_review_console.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.review_state_counts == {
        "deferred_owner_revisit": 1,
        "ready_for_human_review": 1,
        "rejected_closed": 1,
        "waiting_owner_decision": 1,
    }
    assert result.console_bucket_counts == {
        "closed_no_action": 1,
        "operator_review_queue": 1,
        "owner_decision_inbox": 1,
        "owner_revisit_queue": 1,
    }

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, packet_id, work_order_id, review_rank,
                   assigned_lane, operator_lane, owner_decision, packet_status,
                   review_state, console_bucket, review_priority,
                   visible_owner_action, operator_action, console_instruction,
                   review_gate, action_lock, send_whatsapp, crm_mutation,
                   requires_human_approval, review_hash, review_payload_json
            FROM operator_packet_review_items
            ORDER BY review_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count, brief_count,
                   queue_item_count, ledger_entry_count, event_row_count,
                   work_order_count, packet_count, review_item_count,
                   owner_decision_item_count, operator_ready_item_count,
                   deferred_item_count, rejected_item_count,
                   send_whatsapp_count, crm_mutation_count
            FROM operator_packet_review_console_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (8, 4, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 0, 0)
    assert rows[0][0:19] == (
        "card-owner-pending",
        "operator-packet-pending",
        "post-work-order-pending",
        1,
        "sahira",
        "owner",
        "pending",
        "blocked_awaiting_owner_decision",
        "waiting_owner_decision",
        "owner_decision_inbox",
        "owner_now",
        "capture_owner_decision",
        "no_operator_action",
        "owner_must_approve_reject_or_defer_before_team_work",
        "owner_input_required",
        "locked_until_owner_decision",
        0,
        0,
        1,
    )
    assert rows[1][0:19] == (
        "card-owner-approve",
        "operator-packet-approve",
        "post-work-order-approve",
        2,
        "sahira",
        "sahira",
        "approve",
        "ready_for_operator_review",
        "ready_for_human_review",
        "operator_review_queue",
        "operator_now",
        "no_owner_action_required",
        "review_packet_before_send_or_crm",
        "review_ready_packet_and_request_human_approval",
        "human_review_before_send_or_crm",
        "locked_until_human_review",
        0,
        0,
        1,
    )
    assert rows[2][8:16] == (
        "deferred_owner_revisit",
        "owner_revisit_queue",
        "owner_revisit",
        "revisit_deferred_decision",
        "no_operator_action",
        "owner_must_revisit_deferred_packet",
        "owner_revisit_required",
        "locked_until_owner_revisit",
    )
    assert rows[3][8:16] == (
        "rejected_closed",
        "closed_no_action",
        "closed",
        "no_action",
        "no_operator_action",
        "no_action_packet_rejected",
        "no_external_action",
        "closed_no_external_action",
    )
    assert len({row[19] for row in rows}) == 4
    assert all(len(row[19]) == 64 for row in rows)

    payload = json.loads(rows[0][20])
    assert payload["schema_version"] == "operator_packet_review_console.v1"
    assert payload["privacy_mode"] == "local_only_operator_packet_review_console_no_raw_text"
    assert payload["source_packet_rank"] == 1
    assert payload["packet_status"] == "blocked_awaiting_owner_decision"
    assert payload["review_state"] == "waiting_owner_decision"
    assert payload["console_bucket"] == "owner_decision_inbox"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Operator Packet Review Console Summary" in summary
    assert "| Source cases | 8 |" in summary
    assert "| Operator packets | 4 |" in summary
    assert "| Review items | 4 |" in summary
    assert "| Owner decision items | 1 |" in summary
    assert "| Operator-ready items | 1 |" in summary
    assert "| Deferred items | 1 |" in summary
    assert "| Rejected items | 1 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-pending" not in summary
    assert "operator-packet-pending" not in summary
    assert "post-work-order-pending" not in summary
    assert "owner-event-pending" not in summary
    assert "ledger-entry-pending" not in summary
    assert "approval-route-pending" not in summary


def test_build_operator_packet_review_console_rejects_unknown_packet_status(
    tmp_path: Path,
) -> None:
    packets_db = tmp_path / "operator_execution_packets.local.sqlite"
    output_dir = tmp_path / "operator-packet-review-console"
    _write_operator_execution_packets_db(packets_db)
    with sqlite3.connect(packets_db) as conn:
        conn.execute(
            """
            UPDATE operator_execution_packets
            SET packet_status = 'send_now'
            WHERE packet_id = 'operator-packet-approve'
            """
        )
        conn.commit()

    with pytest.raises(ValueError, match="Unsupported packet status"):
        build_operator_packet_review_console(
            packets_db=packets_db,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_build_operator_packet_review_console_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "operator_execution_packets.bad.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Operator Execution Packets DB",
    ):
        build_operator_packet_review_console(
            packets_db=unexpected_db,
            output_dir=tmp_path / "operator-packet-review-console",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_review_details(tmp_path: Path) -> None:
    packets_db = tmp_path / "operator_execution_packets.local.sqlite"
    output_dir = tmp_path / "operator-packet-review-console"
    summary_path = output_dir / "operator_packet_review_console_summary.md"
    _write_operator_execution_packets_db(packets_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--packets-db",
            str(packets_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T22:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "brief_count": 4,
        "crm_mutation_count": 0,
        "deferred_item_count": 1,
        "event_row_count": 4,
        "ledger_entry_count": 4,
        "operator_ready_item_count": 1,
        "owner_decision_item_count": 1,
        "owner_item_count": 4,
        "pack_count": 4,
        "packet_count": 4,
        "queue_item_count": 4,
        "rejected_item_count": 1,
        "review_item_count": 4,
        "send_whatsapp_count": 0,
        "source_case_count": 8,
        "work_order_count": 4,
    }
    assert "card-owner-pending" not in result.stdout
    assert "operator-packet-pending" not in result.stdout
    assert "post-work-order-pending" not in result.stdout
    assert "owner-event-pending" not in result.stdout
    assert "ledger-entry-pending" not in result.stdout
    assert "approval-route-pending" not in result.stdout
