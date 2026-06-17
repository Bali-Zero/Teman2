from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_approve_reject_ledger import (
    build_approve_reject_ledger,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_approve_reject_ledger.py"


def _write_approval_routing_queue_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE approval_routing_queue_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                brief_count INTEGER NOT NULL,
                queue_item_count INTEGER NOT NULL,
                now_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE approval_routing_items (
                route_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                route_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                owner_focus TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                next_actor TEXT NOT NULL,
                queue_status TEXT NOT NULL,
                allowed_decisions_json TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                safety_lock TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                route_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO approval_routing_queue_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, now_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 4, 2, 2, 2, 2, 2, 0, 0)
            """,
            (
                "2026-06-17T17:00:00+00:00",
                "2026-06-17T16:00:00+00:00",
                "local_only_approval_routing_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "approval-route-followup",
                "card-owner-followup",
                "owner-brief-followup",
                "owner-pack-followup",
                1,
                "sahira",
                "approve_client_recovery_followup",
                "now",
                "review_client_recovery_language",
                "owner_now",
                "owner",
                "waiting_owner_decision",
                "approve_recovery_followup_after_review",
                "owner_review_client_followup_draft",
                "owner_approval_required_no_send_no_crm",
                "pending_owner_review",
            ),
            (
                "approval-route-status",
                "card-owner-status",
                "owner-brief-status",
                "owner-pack-status",
                2,
                "ari",
                "approve_immigration_status_escalation",
                "now",
                "review_immigration_status_escalation",
                "owner_now",
                "owner",
                "waiting_owner_decision",
                "approve_status_escalation_after_review",
                "owner_review_status_escalation_draft",
                "owner_approval_required_no_send_no_crm",
                "pending_owner_review",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO approval_routing_items (
                route_id, case_card_id, brief_id, pack_id, route_rank,
                assigned_lane, decision_type, decision_priority, owner_focus,
                route_bucket, next_actor, queue_status, allowed_decisions_json,
                recommended_decision, draft_action_type, safety_lock,
                approval_status, route_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row[0:12],
                    json.dumps(["approve", "reject", "defer"]),
                    row[12],
                    row[13],
                    row[14],
                    row[15],
                    json.dumps(
                        {
                            "schema_version": "approval_routing_queue.v1",
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


def test_build_approve_reject_ledger_writes_pending_decision_slots(
    tmp_path: Path,
) -> None:
    approval_routing_db = tmp_path / "approval_routing_queue.local.sqlite"
    output_dir = tmp_path / "approve-reject-ledger"
    summary_path = output_dir / "approve_reject_ledger_summary.md"
    _write_approval_routing_queue_db(approval_routing_db)

    result = build_approve_reject_ledger(
        approval_routing_db=approval_routing_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T18:00:00+00:00",
    )

    assert result.source_case_count == 4
    assert result.owner_item_count == 2
    assert result.pack_count == 2
    assert result.brief_count == 2
    assert result.queue_item_count == 2
    assert result.ledger_entry_count == 2
    assert result.pending_decision_count == 2
    assert result.output_db == output_dir / "approve_reject_ledger.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.decision_status_counts == {"awaiting_owner_decision": 2}
    assert result.owner_decision_counts == {"pending": 2}
    assert result.event_type_counts == {"decision_slot_opened": 2}
    assert result.route_bucket_counts == {"owner_now": 2}

    with sqlite3.connect(result.output_db) as conn:
        entries = conn.execute(
            """
            SELECT case_card_id, route_id, brief_id, pack_id, ledger_rank,
                   assigned_lane, decision_type, decision_priority, route_bucket,
                   next_actor, queue_status, decision_status, owner_decision,
                   allowed_decisions_json, recommended_decision, draft_action_type,
                   immutable_event_type, send_whatsapp, crm_mutation,
                   requires_human_approval, ledger_entry_hash, ledger_payload_json
            FROM approve_reject_ledger_entries
            ORDER BY ledger_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count, brief_count,
                   queue_item_count, ledger_entry_count, pending_decision_count,
                   send_whatsapp_count, crm_mutation_count
            FROM approve_reject_ledger_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (4, 2, 2, 2, 2, 2, 2, 0, 0)
    assert entries[0][0:13] == (
        "card-owner-followup",
        "approval-route-followup",
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
    )
    assert json.loads(entries[0][13]) == ["approve", "reject", "defer"]
    assert entries[0][14:20] == (
        "approve_recovery_followup_after_review",
        "owner_review_client_followup_draft",
        "decision_slot_opened",
        0,
        0,
        1,
    )
    assert entries[1][0:13] == (
        "card-owner-status",
        "approval-route-status",
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
    )
    assert json.loads(entries[1][13]) == ["approve", "reject", "defer"]

    entry_hash = entries[0][20]
    assert len(entry_hash) == 64
    int(entry_hash, 16)

    payload = json.loads(entries[0][21])
    assert payload["schema_version"] == "approve_reject_ledger.v1"
    assert payload["privacy_mode"] == "local_only_approve_reject_ledger_no_raw_text"
    assert payload["source_route_rank"] == 1
    assert payload["source_queue_status"] == "waiting_owner_decision"
    assert payload["decision_status"] == "awaiting_owner_decision"
    assert payload["owner_decision"] == "pending"
    assert payload["allowed_decisions"] == ["approve", "reject", "defer"]
    assert payload["immutable_event_type"] == "decision_slot_opened"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Approve/Reject Ledger Summary" in summary
    assert "| Source cases | 4 |" in summary
    assert "| Queue items | 2 |" in summary
    assert "| Ledger entries | 2 |" in summary
    assert "| Pending owner decisions | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-followup" not in summary
    assert "card-owner-status" not in summary
    assert "approval-route-followup" not in summary
    assert "approval-route-status" not in summary
    assert "owner-brief-followup" not in summary
    assert "owner-pack-followup" not in summary


def test_build_approve_reject_ledger_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "owner_brief_renderer.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Approval Routing Queue DB",
    ):
        build_approve_reject_ledger(
            approval_routing_db=unexpected_db,
            output_dir=tmp_path / "approve-reject-ledger",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_ledger_details(tmp_path: Path) -> None:
    approval_routing_db = tmp_path / "approval_routing_queue.local.sqlite"
    output_dir = tmp_path / "approve-reject-ledger"
    summary_path = output_dir / "approve_reject_ledger_summary.md"
    _write_approval_routing_queue_db(approval_routing_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--approval-routing-db",
            str(approval_routing_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T18:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "brief_count": 2,
        "crm_mutation_count": 0,
        "ledger_entry_count": 2,
        "owner_item_count": 2,
        "pack_count": 2,
        "pending_decision_count": 2,
        "queue_item_count": 2,
        "send_whatsapp_count": 0,
        "source_case_count": 4,
    }
    assert "card-owner-followup" not in result.stdout
    assert "card-owner-status" not in result.stdout
    assert "approval-route-followup" not in result.stdout
    assert "approval-route-status" not in result.stdout
    assert "owner-brief-followup" not in result.stdout
    assert "owner-pack-followup" not in result.stdout
