from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_post_decision_work_order_queue import (
    build_post_decision_work_order_queue,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "whatsapp_corpus"
    / "build_post_decision_work_order_queue.py"
)


def _write_owner_decision_event_capture_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_decision_event_capture_runs (
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
                captured_event_count INTEGER NOT NULL,
                awaiting_input_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_decision_event_rows (
                event_id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                event_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                capture_status TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_source TEXT NOT NULL,
                event_actor TEXT NOT NULL,
                event_recorded_at_utc TEXT NOT NULL,
                allowed_decisions_json TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_ledger_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                event_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_event_capture_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, captured_event_count,
                awaiting_input_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 8, 4, 4, 4, 4, 4, 3, 1, 0, 0)
            """,
            (
                "2026-06-17T19:00:00+00:00",
                "2026-06-17T18:00:00+00:00",
                "local_only_owner_decision_event_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
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
                "awaiting_owner_input",
                "pending",
                "owner_decision_not_submitted",
                "owner_decision_required",
                "a" * 64,
            ),
            (
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
                "captured",
                "approve",
                "owner_decision_captured",
                "approved recovery follow-up",
                "b" * 64,
            ),
            (
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
                "captured",
                "defer",
                "owner_decision_captured",
                "wait for immigration evidence",
                "c" * 64,
            ),
            (
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
                "captured",
                "reject",
                "owner_decision_captured",
                "do not proceed",
                "d" * 64,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO owner_decision_event_rows (
                event_id, entry_id, route_id, case_card_id, brief_id, pack_id,
                event_rank, assigned_lane, decision_type, decision_priority,
                route_bucket, capture_status, owner_decision, event_type,
                event_source, event_actor, event_recorded_at_utc,
                allowed_decisions_json, recommended_decision, draft_action_type,
                decision_note, source_ledger_hash, event_hash,
                event_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row[0:14],
                    "local_owner_event_capture",
                    "owner",
                    f"2026-06-17T19:0{row[6]}:00+00:00",
                    json.dumps(["approve", "reject", "defer"]),
                    (
                        "approve_recovery_followup_after_review"
                        if row[8] == "approve_client_recovery_followup"
                        else "approve_status_escalation_after_review"
                    ),
                    (
                        "owner_review_client_followup_draft"
                        if row[8] == "approve_client_recovery_followup"
                        else "owner_review_status_escalation_draft"
                    ),
                    row[14],
                    f"ledger-{row[15]}",
                    row[15],
                    json.dumps(
                        {
                            "schema_version": "owner_decision_event_capture.v1",
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


def test_build_post_decision_work_order_queue_maps_owner_decisions_to_work_orders(
    tmp_path: Path,
) -> None:
    events_db = tmp_path / "owner_decision_event_capture.local.sqlite"
    output_dir = tmp_path / "post-decision-work-orders"
    summary_path = output_dir / "post_decision_work_order_queue_summary.md"
    _write_owner_decision_event_capture_db(events_db)

    result = build_post_decision_work_order_queue(
        owner_events_db=events_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T20:00:00+00:00",
    )

    assert result.source_case_count == 8
    assert result.owner_item_count == 4
    assert result.pack_count == 4
    assert result.brief_count == 4
    assert result.queue_item_count == 4
    assert result.ledger_entry_count == 4
    assert result.event_row_count == 4
    assert result.work_order_count == 4
    assert result.ready_count == 1
    assert result.blocked_count == 1
    assert result.deferred_count == 1
    assert result.rejected_count == 1
    assert result.output_db == output_dir / "post_decision_work_order_queue.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.work_order_status_counts == {
        "blocked_awaiting_owner_decision": 1,
        "deferred_owner_followup": 1,
        "ready_for_operator_review": 1,
        "rejected_no_action": 1,
    }
    assert result.owner_decision_counts == {
        "approve": 1,
        "defer": 1,
        "pending": 1,
        "reject": 1,
    }

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, event_id, entry_id, work_order_rank,
                   assigned_lane, owner_decision, source_capture_status,
                   work_order_status, work_order_type, execution_gate,
                   next_actor, action_intent, decision_effect, decision_note,
                   send_whatsapp, crm_mutation, requires_human_approval,
                   work_order_hash, work_order_payload_json
            FROM post_decision_work_orders
            ORDER BY work_order_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count, brief_count,
                   queue_item_count, ledger_entry_count, event_row_count,
                   work_order_count, ready_count, blocked_count, deferred_count,
                   rejected_count, send_whatsapp_count, crm_mutation_count
            FROM post_decision_work_order_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (8, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 0, 0)
    assert rows[0][0:17] == (
        "card-owner-pending",
        "owner-event-pending",
        "ledger-entry-pending",
        1,
        "sahira",
        "pending",
        "awaiting_owner_input",
        "blocked_awaiting_owner_decision",
        "owner_decision_required",
        "owner_input_required",
        "owner",
        "wait_for_owner_decision",
        "no_action_until_owner_decision",
        "owner_decision_required",
        0,
        0,
        1,
    )
    assert rows[1][0:17] == (
        "card-owner-approve",
        "owner-event-approve",
        "ledger-entry-approve",
        2,
        "sahira",
        "approve",
        "captured",
        "ready_for_operator_review",
        "approved_client_recovery_followup",
        "human_review_before_send_or_crm",
        "sahira",
        "prepare_client_recovery_followup_for_human_review",
        "owner_approved_internal_work_order",
        "approved recovery follow-up",
        0,
        0,
        1,
    )
    assert rows[2][7:13] == (
        "deferred_owner_followup",
        "owner_deferred_followup",
        "owner_revisit_required",
        "owner",
        "schedule_owner_revisit",
        "deferred_no_external_action",
    )
    assert rows[3][7:13] == (
        "rejected_no_action",
        "owner_rejected_no_action",
        "no_external_action",
        "owner",
        "record_rejection_and_stop",
        "rejected_no_external_action",
    )
    assert len({row[17] for row in rows}) == 4
    assert all(len(row[17]) == 64 for row in rows)

    payload = json.loads(rows[0][18])
    assert payload["schema_version"] == "post_decision_work_order_queue.v1"
    assert payload["privacy_mode"] == "local_only_post_decision_work_order_no_raw_text"
    assert payload["source_event_rank"] == 1
    assert payload["source_capture_status"] == "awaiting_owner_input"
    assert payload["owner_decision"] == "pending"
    assert payload["work_order_status"] == "blocked_awaiting_owner_decision"
    assert payload["execution_gate"] == "owner_input_required"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Post-Decision Work Order Queue Summary" in summary
    assert "| Source cases | 8 |" in summary
    assert "| Event rows | 4 |" in summary
    assert "| Work orders | 4 |" in summary
    assert "| Ready work orders | 1 |" in summary
    assert "| Blocked work orders | 1 |" in summary
    assert "| Deferred work orders | 1 |" in summary
    assert "| Rejected work orders | 1 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-pending" not in summary
    assert "owner-event-pending" not in summary
    assert "ledger-entry-pending" not in summary
    assert "approval-route-pending" not in summary


def test_build_post_decision_work_order_queue_rejects_unknown_owner_decision(
    tmp_path: Path,
) -> None:
    events_db = tmp_path / "owner_decision_event_capture.local.sqlite"
    output_dir = tmp_path / "post-decision-work-orders"
    _write_owner_decision_event_capture_db(events_db)
    with sqlite3.connect(events_db) as conn:
        conn.execute(
            """
            UPDATE owner_decision_event_rows
            SET owner_decision = 'send_now'
            WHERE event_id = 'owner-event-approve'
            """
        )
        conn.commit()

    with pytest.raises(ValueError, match="Unsupported owner decision"):
        build_post_decision_work_order_queue(
            owner_events_db=events_db,
            output_dir=output_dir,
            summary_path=output_dir / "summary.md",
        )


def test_build_post_decision_work_order_queue_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "owner_decision_event_capture.bad.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Owner Decision Event Capture DB",
    ):
        build_post_decision_work_order_queue(
            owner_events_db=unexpected_db,
            output_dir=tmp_path / "post-decision-work-orders",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_work_order_details(tmp_path: Path) -> None:
    events_db = tmp_path / "owner_decision_event_capture.local.sqlite"
    output_dir = tmp_path / "post-decision-work-orders"
    summary_path = output_dir / "post_decision_work_order_queue_summary.md"
    _write_owner_decision_event_capture_db(events_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-events-db",
            str(events_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T20:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "blocked_count": 1,
        "brief_count": 4,
        "crm_mutation_count": 0,
        "deferred_count": 1,
        "event_row_count": 4,
        "ledger_entry_count": 4,
        "owner_item_count": 4,
        "pack_count": 4,
        "queue_item_count": 4,
        "ready_count": 1,
        "rejected_count": 1,
        "send_whatsapp_count": 0,
        "source_case_count": 8,
        "work_order_count": 4,
    }
    assert "card-owner-pending" not in result.stdout
    assert "owner-event-pending" not in result.stdout
    assert "ledger-entry-pending" not in result.stdout
    assert "approval-route-pending" not in result.stdout
