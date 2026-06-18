from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_operator_execution_packets import (
    build_operator_execution_packets,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "whatsapp_corpus"
    / "build_operator_execution_packets.py"
)


def _write_post_decision_work_order_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE post_decision_work_order_runs (
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
                ready_count INTEGER NOT NULL,
                blocked_count INTEGER NOT NULL,
                deferred_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE post_decision_work_orders (
                work_order_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                work_order_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                source_capture_status TEXT NOT NULL,
                work_order_status TEXT NOT NULL,
                work_order_type TEXT NOT NULL,
                execution_gate TEXT NOT NULL,
                next_actor TEXT NOT NULL,
                action_intent TEXT NOT NULL,
                decision_effect TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_event_hash TEXT NOT NULL,
                work_order_hash TEXT NOT NULL UNIQUE,
                work_order_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO post_decision_work_order_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, event_row_count,
                work_order_count, ready_count, blocked_count, deferred_count,
                rejected_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 8, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 0, 0)
            """,
            (
                "2026-06-17T20:00:00+00:00",
                "2026-06-17T19:00:00+00:00",
                "local_only_post_decision_work_order_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "post-work-order-pending",
                "owner-event-pending",
                "ledger-entry-pending",
                "approval-route-pending",
                "card-owner-pending",
                "owner-brief-pending",
                "owner-pack-pending",
                1,
                "sahira",
                "approve_client_recovery_followup",
                "now",
                "owner_now",
                "pending",
                "awaiting_owner_input",
                "blocked_awaiting_owner_decision",
                "owner_decision_required",
                "owner_input_required",
                "owner",
                "wait_for_owner_decision",
                "no_action_until_owner_decision",
                "owner_decision_required",
                "event-a",
                "a" * 64,
            ),
            (
                "post-work-order-approve",
                "owner-event-approve",
                "ledger-entry-approve",
                "approval-route-approve",
                "card-owner-approve",
                "owner-brief-approve",
                "owner-pack-approve",
                2,
                "sahira",
                "approve_client_recovery_followup",
                "now",
                "owner_now",
                "approve",
                "captured",
                "ready_for_operator_review",
                "approved_client_recovery_followup",
                "human_review_before_send_or_crm",
                "sahira",
                "prepare_client_recovery_followup_for_human_review",
                "owner_approved_internal_work_order",
                "approved recovery follow-up",
                "event-b",
                "b" * 64,
            ),
            (
                "post-work-order-defer",
                "owner-event-defer",
                "ledger-entry-defer",
                "approval-route-defer",
                "card-owner-defer",
                "owner-brief-defer",
                "owner-pack-defer",
                3,
                "ari",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
                "defer",
                "captured",
                "deferred_owner_followup",
                "owner_deferred_followup",
                "owner_revisit_required",
                "owner",
                "schedule_owner_revisit",
                "deferred_no_external_action",
                "wait for immigration evidence",
                "event-c",
                "c" * 64,
            ),
            (
                "post-work-order-reject",
                "owner-event-reject",
                "ledger-entry-reject",
                "approval-route-reject",
                "card-owner-reject",
                "owner-brief-reject",
                "owner-pack-reject",
                4,
                "ari",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
                "reject",
                "captured",
                "rejected_no_action",
                "owner_rejected_no_action",
                "no_external_action",
                "owner",
                "record_rejection_and_stop",
                "rejected_no_external_action",
                "do not proceed",
                "event-d",
                "d" * 64,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO post_decision_work_orders (
                work_order_id, event_id, entry_id, route_id, case_card_id,
                brief_id, pack_id, work_order_rank, assigned_lane, decision_type,
                decision_priority, route_bucket, owner_decision,
                source_capture_status, work_order_status, work_order_type,
                execution_gate, next_actor, action_intent, decision_effect,
                decision_note, source_event_hash, work_order_hash,
                work_order_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "post_decision_work_order_queue.v1",
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


def test_build_operator_execution_packets_maps_work_orders_to_internal_packets(
    tmp_path: Path,
) -> None:
    work_orders_db = tmp_path / "post_decision_work_order_queue.local.sqlite"
    output_dir = tmp_path / "operator-execution-packets"
    summary_path = output_dir / "operator_execution_packets_summary.md"
    _write_post_decision_work_order_db(work_orders_db)

    result = build_operator_execution_packets(
        work_orders_db=work_orders_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T21:00:00+00:00",
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
    assert result.ready_packet_count == 1
    assert result.blocked_packet_count == 1
    assert result.deferred_packet_count == 1
    assert result.rejected_packet_count == 1
    assert result.output_db == output_dir / "operator_execution_packets.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.packet_status_counts == {
        "blocked_awaiting_owner_decision": 1,
        "deferred_owner_followup": 1,
        "ready_for_operator_review": 1,
        "rejected_no_action": 1,
    }
    assert result.operator_lane_counts == {"owner": 3, "sahira": 1}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, work_order_id, event_id, packet_rank,
                   assigned_lane, operator_lane, owner_decision,
                   source_work_order_status, packet_status, packet_type,
                   packet_gate, packet_action, operator_instruction,
                   escalation_target, send_whatsapp, crm_mutation,
                   requires_human_approval, packet_hash, packet_payload_json
            FROM operator_execution_packets
            ORDER BY packet_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count, brief_count,
                   queue_item_count, ledger_entry_count, event_row_count,
                   work_order_count, packet_count, ready_packet_count,
                   blocked_packet_count, deferred_packet_count,
                   rejected_packet_count, send_whatsapp_count, crm_mutation_count
            FROM operator_execution_packet_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (8, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 0, 0)
    assert rows[0][0:17] == (
        "card-owner-pending",
        "post-work-order-pending",
        "owner-event-pending",
        1,
        "sahira",
        "owner",
        "pending",
        "blocked_awaiting_owner_decision",
        "blocked_awaiting_owner_decision",
        "owner_decision_required_packet",
        "owner_input_required",
        "wait_for_owner_decision",
        "no_operator_execution_until_owner_decides",
        "owner",
        0,
        0,
        1,
    )
    assert rows[1][0:17] == (
        "card-owner-approve",
        "post-work-order-approve",
        "owner-event-approve",
        2,
        "sahira",
        "sahira",
        "approve",
        "ready_for_operator_review",
        "ready_for_operator_review",
        "client_recovery_followup_packet",
        "human_review_before_send_or_crm",
        "prepare_client_recovery_followup_for_human_review",
        "review_client_recovery_followup_before_any_send",
        "owner",
        0,
        0,
        1,
    )
    assert rows[2][8:14] == (
        "deferred_owner_followup",
        "owner_deferred_packet",
        "owner_revisit_required",
        "schedule_owner_revisit",
        "hold_operator_execution_until_owner_revisits",
        "owner",
    )
    assert rows[3][8:14] == (
        "rejected_no_action",
        "owner_rejected_packet",
        "no_external_action",
        "record_rejection_and_stop",
        "do_not_execute_rejected_work_order",
        "owner",
    )
    assert len({row[17] for row in rows}) == 4
    assert all(len(row[17]) == 64 for row in rows)

    payload = json.loads(rows[0][18])
    assert payload["schema_version"] == "operator_execution_packets.v1"
    assert payload["privacy_mode"] == "local_only_operator_execution_packet_no_raw_text"
    assert payload["source_work_order_rank"] == 1
    assert payload["source_work_order_status"] == "blocked_awaiting_owner_decision"
    assert payload["owner_decision"] == "pending"
    assert payload["packet_status"] == "blocked_awaiting_owner_decision"
    assert payload["packet_gate"] == "owner_input_required"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Operator Execution Packets Summary" in summary
    assert "| Source cases | 8 |" in summary
    assert "| Work orders | 4 |" in summary
    assert "| Operator packets | 4 |" in summary
    assert "| Ready packets | 1 |" in summary
    assert "| Blocked packets | 1 |" in summary
    assert "| Deferred packets | 1 |" in summary
    assert "| Rejected packets | 1 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-pending" not in summary
    assert "post-work-order-pending" not in summary
    assert "owner-event-pending" not in summary
    assert "ledger-entry-pending" not in summary
    assert "approval-route-pending" not in summary


def test_build_operator_execution_packets_rejects_unknown_work_order_status(
    tmp_path: Path,
) -> None:
    work_orders_db = tmp_path / "post_decision_work_order_queue.local.sqlite"
    output_dir = tmp_path / "operator-execution-packets"
    _write_post_decision_work_order_db(work_orders_db)
    with sqlite3.connect(work_orders_db) as conn:
        conn.execute(
            """
            UPDATE post_decision_work_orders
            SET work_order_status = 'send_now'
            WHERE work_order_id = 'post-work-order-approve'
            """
        )
        conn.commit()

    with pytest.raises(ValueError, match="Unsupported work order status"):
        build_operator_execution_packets(
            work_orders_db=work_orders_db,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_build_operator_execution_packets_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "post_decision_work_order_queue.bad.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Post-Decision Work Order Queue DB",
    ):
        build_operator_execution_packets(
            work_orders_db=unexpected_db,
            output_dir=tmp_path / "operator-execution-packets",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_packet_details(tmp_path: Path) -> None:
    work_orders_db = tmp_path / "post_decision_work_order_queue.local.sqlite"
    output_dir = tmp_path / "operator-execution-packets"
    summary_path = output_dir / "operator_execution_packets_summary.md"
    _write_post_decision_work_order_db(work_orders_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--work-orders-db",
            str(work_orders_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T21:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "blocked_packet_count": 1,
        "brief_count": 4,
        "crm_mutation_count": 0,
        "deferred_packet_count": 1,
        "event_row_count": 4,
        "ledger_entry_count": 4,
        "operator_packet_count": 4,
        "owner_item_count": 4,
        "pack_count": 4,
        "queue_item_count": 4,
        "ready_packet_count": 1,
        "rejected_packet_count": 1,
        "send_whatsapp_count": 0,
        "source_case_count": 8,
        "work_order_count": 4,
    }
    assert "card-owner-pending" not in result.stdout
    assert "post-work-order-pending" not in result.stdout
    assert "owner-event-pending" not in result.stdout
    assert "ledger-entry-pending" not in result.stdout
    assert "approval-route-pending" not in result.stdout
