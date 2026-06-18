from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_operator_action_inbox import build_operator_action_inbox

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_operator_action_inbox.py"


def _write_next_best_actions_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE next_best_action_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                action_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE next_best_action_rankings (
                case_card_id TEXT NOT NULL,
                action_rank INTEGER NOT NULL,
                action_code TEXT NOT NULL,
                action_title TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                urgency_score INTEGER NOT NULL,
                impact_score INTEGER NOT NULL,
                combined_score INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                action_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1),
                PRIMARY KEY (case_card_id, action_rank)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO next_best_action_runs VALUES (
                1, '2026-06-17T00:00:00+00:00',
                'local_only_next_best_actions_no_raw_text_no_send_no_crm_mutation',
                2, 6, 0, 0
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO next_best_action_rankings VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "card-followup",
                    1,
                    "crm_followup",
                    "Crm Followup",
                    "stale_followup",
                    100,
                    85,
                    94,
                    "sahira",
                    json.dumps(
                        {
                            "source_case_status": "needs_human_review",
                            "source_risk_level": "P1",
                            "source_blocker_code": "case_stall_followup_risk",
                            "latest_movement": "2026-06:42",
                            "raw_text_included": False,
                        },
                        sort_keys=True,
                    ),
                    0,
                    0,
                    1,
                ),
                (
                    "card-followup",
                    2,
                    "operator_system_update",
                    "Operator System Update",
                    "missing_system_update",
                    95,
                    80,
                    89,
                    "sahira",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
                (
                    "card-followup",
                    3,
                    "client_status_draft_review",
                    "Client Status Draft Review",
                    "client_confused_or_silent",
                    90,
                    75,
                    84,
                    "sahira",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
                (
                    "card-payment",
                    1,
                    "payment_reconcile",
                    "Payment Reconcile",
                    "payment_risk",
                    70,
                    90,
                    78,
                    "surya",
                    json.dumps(
                        {
                            "source_case_status": "monitor_and_prepare",
                            "source_risk_level": "P2",
                            "source_blocker_code": "payment_reconciliation_needed",
                            "latest_movement": "2026-04:15",
                            "raw_text_included": False,
                        },
                        sort_keys=True,
                    ),
                    0,
                    0,
                    1,
                ),
                (
                    "card-payment",
                    2,
                    "ledger_check",
                    "Ledger Check",
                    "finance_verification",
                    65,
                    80,
                    71,
                    "surya",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
                (
                    "card-payment",
                    3,
                    "proof_of_payment_review",
                    "Proof Of Payment Review",
                    "payment_evidence_gap",
                    60,
                    75,
                    66,
                    "surya",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
            ],
        )
        conn.commit()


def test_build_operator_action_inbox_writes_one_review_item_per_case(
    tmp_path: Path,
) -> None:
    next_best_db = tmp_path / "next_best_actions.local.sqlite"
    output_dir = tmp_path / "operator-inbox"
    summary_path = output_dir / "operator_action_inbox_summary.md"
    _write_next_best_actions_db(next_best_db)

    result = build_operator_action_inbox(
        next_best_actions_db=next_best_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.case_count == 2
    assert result.candidate_action_count == 6
    assert result.inbox_item_count == 2
    assert result.output_db == output_dir / "operator_action_inbox.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.priority_counts == {"now": 1, "today": 1}
    assert result.lane_counts == {"sahira": 1, "surya": 1}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT inbox_item_id, case_card_id, queue_rank, assigned_lane,
                   priority_label, queue_bucket, action_code, reason_code,
                   urgency_score, combined_score, operator_instruction,
                   approval_mode, send_whatsapp, crm_mutation,
                   requires_human_approval, item_payload_json
            FROM operator_action_inbox
            ORDER BY queue_rank
            """
        ).fetchall()

    assert [row[1] for row in rows] == ["card-followup", "card-payment"]
    assert [row[2] for row in rows] == [1, 2]
    assert rows[0][3:10] == (
        "sahira",
        "now",
        "follow_up_now",
        "crm_followup",
        "stale_followup",
        100,
        94,
    )
    assert rows[1][3:10] == (
        "surya",
        "today",
        "finance_today",
        "payment_reconcile",
        "payment_risk",
        70,
        78,
    )
    assert "review the CRM follow-up" in rows[0][10]
    assert rows[0][11] == "human_review_required"
    assert {row[12] for row in rows} == {0}
    assert {row[13] for row in rows} == {0}
    assert {row[14] for row in rows} == {1}
    payload = json.loads(rows[0][15])
    assert payload["schema_version"] == "operator_action_inbox.v1"
    assert payload["source_action_rank"] == 1
    assert payload["candidate_action_count"] == 3
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Operator Action Inbox Summary" in summary
    assert "| Inbox items | 2 |" in summary
    assert "| Candidate actions reviewed | 6 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-followup" not in summary
    assert "card-payment" not in summary


def test_build_operator_action_inbox_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "case_memory_cards.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Next Best Actions DB"):
        build_operator_action_inbox(
            next_best_actions_db=unexpected_db,
            output_dir=tmp_path / "operator-inbox",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_raw_case_details(tmp_path: Path) -> None:
    next_best_db = tmp_path / "next_best_actions.local.sqlite"
    output_dir = tmp_path / "operator-inbox"
    summary_path = output_dir / "operator_action_inbox_summary.md"
    _write_next_best_actions_db(next_best_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--next-best-actions-db",
            str(next_best_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["case_count"] == 2
    assert payload["candidate_action_count"] == 6
    assert payload["inbox_item_count"] == 2
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "card-followup" not in result.stdout
    assert "card-payment" not in result.stdout
