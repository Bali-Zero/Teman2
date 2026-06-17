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
from scripts.whatsapp_corpus.build_owner_decision_replay import (
    build_owner_decision_replay,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_decision_replay.py"


def _write_matching_approve_reject_ledger_db(db_path: Path) -> None:
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
            VALUES (1, ?, ?, ?, 8, 2, 2, 2, 2, 2, 2, 0, 0)
            """,
            (
                "2026-06-17T23:00:00+00:00",
                "2026-06-17T22:00:00+00:00",
                "local_only_approve_reject_ledger_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
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
                "approve_recovery_followup_after_review",
                "owner_review_client_followup_draft",
                "a" * 64,
            ),
            (
                "ledger-entry-defer",
                "approval-route-defer",
                "card-owner-defer",
                "owner-brief-defer",
                "owner-pack-defer",
                2,
                "ari",
                "approve_immigration_status_escalation",
                "now",
                "owner_now",
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'owner',
                    'waiting_owner_decision', 'awaiting_owner_decision',
                    'pending', ?, ?, ?, 'decision_slot_opened', ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row[0:10],
                    json.dumps(["approve", "reject", "defer"]),
                    row[10],
                    row[11],
                    row[12],
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


def test_build_owner_decision_replay_runs_full_local_chain(tmp_path: Path) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    owner_decisions_jsonl = tmp_path / "owner_decisions.local.jsonl"
    output_dir = tmp_path / "owner-decision-replay"
    summary_path = output_dir / "owner_decision_replay_summary.md"
    _write_matching_approve_reject_ledger_db(ledger_db)
    _write_operator_packet_review_console_db(review_console_db)
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

    result = build_owner_decision_replay(
        ledger_db=ledger_db,
        review_console_db=review_console_db,
        owner_decisions_jsonl=owner_decisions_jsonl,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T23:03:00+00:00",
    )

    assert result.source_case_count == 8
    assert result.source_review_item_count == 4
    assert result.intake_item_count == 4
    assert result.captured_owner_decision_count == 2
    assert result.replay_event_count == 2
    assert result.captured_event_count == 2
    assert result.awaiting_input_count == 0
    assert result.work_order_count == 2
    assert result.ready_work_order_count == 1
    assert result.rejected_work_order_count == 1
    assert result.packet_count == 2
    assert result.ready_packet_count == 1
    assert result.rejected_packet_count == 1
    assert result.final_review_item_count == 2
    assert result.final_operator_ready_item_count == 1
    assert result.final_rejected_item_count == 1
    assert result.final_owner_decision_item_count == 0
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.output_db == output_dir / "owner_decision_replay.local.sqlite"

    assert result.intake_db == output_dir / "owner-decision-intake/owner_decision_intake.local.sqlite"
    assert result.owner_events_db == (
        output_dir / "owner-decision-events/owner_decision_event_capture.local.sqlite"
    )
    assert result.work_orders_db == (
        output_dir / "post-decision-work-orders/post_decision_work_order_queue.local.sqlite"
    )
    assert result.operator_packets_db == (
        output_dir / "operator-execution-packets/operator_execution_packets.local.sqlite"
    )
    assert result.final_review_console_db == (
        output_dir
        / "operator-packet-review-console/operator_packet_review_console.local.sqlite"
    )

    with sqlite3.connect(result.output_db) as conn:
        run = conn.execute(
            """
            SELECT source_case_count, source_review_item_count, intake_item_count,
                   captured_owner_decision_count, replay_event_count,
                   captured_event_count, awaiting_input_count, work_order_count,
                   ready_work_order_count, rejected_work_order_count,
                   packet_count, ready_packet_count, rejected_packet_count,
                   final_review_item_count, final_operator_ready_item_count,
                   final_rejected_item_count, send_whatsapp_count,
                   crm_mutation_count
            FROM owner_decision_replay_runs
            WHERE id = 1
            """
        ).fetchone()
        stages = conn.execute(
            """
            SELECT stage_name, item_count, output_db, output_summary
            FROM owner_decision_replay_stage_outputs
            ORDER BY stage_rank
            """
        ).fetchall()

    assert run == (8, 4, 4, 2, 2, 2, 0, 2, 1, 1, 2, 1, 1, 2, 1, 1, 0, 0)
    assert [stage[0:2] for stage in stages] == [
        ("owner_decision_intake", 4),
        ("owner_decision_event_capture", 2),
        ("post_decision_work_order_queue", 2),
        ("operator_execution_packets", 2),
        ("operator_packet_review_console", 2),
    ]
    assert all(stage[2] for stage in stages)
    assert all(stage[3] for stage in stages)

    with sqlite3.connect(result.final_review_console_db) as conn:
        final_rows = conn.execute(
            """
            SELECT owner_decision, review_state, console_bucket, send_whatsapp,
                   crm_mutation, requires_human_approval
            FROM operator_packet_review_items
            ORDER BY review_rank
            """
        ).fetchall()

    assert final_rows == [
        ("approve", "ready_for_human_review", "operator_review_queue", 0, 0, 1),
        ("reject", "rejected_closed", "closed_no_action", 0, 0, 1),
    ]

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Decision Replay Summary" in summary
    assert "| Source cases | 8 |" in summary
    assert "| Captured owner decisions | 2 |" in summary
    assert "| Work orders | 2 |" in summary
    assert "| Final review items | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "operator-packet-review-item-pending" not in summary
    assert "ledger-entry-pending" not in summary


def test_build_owner_decision_replay_accepts_empty_owner_decision_file(
    tmp_path: Path,
) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    owner_decisions_jsonl = tmp_path / "owner_decisions.local.jsonl"
    output_dir = tmp_path / "owner-decision-replay"
    _write_matching_approve_reject_ledger_db(ledger_db)
    _write_operator_packet_review_console_db(review_console_db)
    owner_decisions_jsonl.write_text("", encoding="utf-8")

    result = build_owner_decision_replay(
        ledger_db=ledger_db,
        review_console_db=review_console_db,
        owner_decisions_jsonl=owner_decisions_jsonl,
        output_dir=output_dir,
        summary_path=output_dir / "summary.md",
        generated_at_utc="2026-06-17T23:03:00+00:00",
    )

    assert result.captured_owner_decision_count == 0
    assert result.replay_event_count == 0
    assert result.captured_event_count == 0
    assert result.awaiting_input_count == 2
    assert result.final_owner_decision_item_count == 2
    assert result.final_operator_ready_item_count == 0
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0


def test_build_owner_decision_replay_rejects_invalid_decision(
    tmp_path: Path,
) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    owner_decisions_jsonl = tmp_path / "owner_decisions.local.jsonl"
    output_dir = tmp_path / "owner-decision-replay"
    _write_matching_approve_reject_ledger_db(ledger_db)
    _write_operator_packet_review_console_db(review_console_db)
    owner_decisions_jsonl.write_text(
        json.dumps(
            {
                "review_item_id": "operator-packet-review-item-pending",
                "owner_decision": "send_now",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Owner decision is not allowed"):
        build_owner_decision_replay(
            ledger_db=ledger_db,
            review_console_db=review_console_db,
            owner_decisions_jsonl=owner_decisions_jsonl,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_cli_writes_json_without_replay_details(tmp_path: Path) -> None:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    owner_decisions_jsonl = tmp_path / "owner_decisions.local.jsonl"
    output_dir = tmp_path / "owner-decision-replay"
    summary_path = output_dir / "owner_decision_replay_summary.md"
    _write_matching_approve_reject_ledger_db(ledger_db)
    _write_operator_packet_review_console_db(review_console_db)
    owner_decisions_jsonl.write_text("", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ledger-db",
            str(ledger_db),
            "--review-console-db",
            str(review_console_db),
            "--owner-decisions-jsonl",
            str(owner_decisions_jsonl),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T23:03:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "awaiting_input_count": 2,
        "captured_event_count": 0,
        "captured_owner_decision_count": 0,
        "crm_mutation_count": 0,
        "final_operator_ready_item_count": 0,
        "final_owner_decision_item_count": 2,
        "final_rejected_item_count": 0,
        "final_review_item_count": 2,
        "packet_count": 2,
        "replay_event_count": 0,
        "send_whatsapp_count": 0,
        "source_case_count": 8,
        "source_review_item_count": 4,
        "work_order_count": 2,
    }
    assert "operator-packet-review-item-pending" not in result.stdout
    assert "ledger-entry-pending" not in result.stdout
