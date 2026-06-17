from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_next_best_action_ranker import build_next_best_action_ranker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_next_best_action_ranker.py"


def _write_case_memory_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE case_memory_card_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                card_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE case_memory_cards (
                case_card_id TEXT PRIMARY KEY,
                source_shadow_id TEXT NOT NULL,
                source_window_id TEXT NOT NULL,
                case_owner TEXT NOT NULL,
                case_status TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                next_best_action TEXT NOT NULL,
                assigned_lane TEXT NOT NULL,
                latest_movement TEXT NOT NULL,
                blocker_code TEXT NOT NULL,
                review_rank INTEGER NOT NULL,
                card_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO case_memory_card_runs VALUES (
                1, '2026-06-17T00:00:00+00:00',
                'local_only_case_memory_cards_no_raw_text_no_send_no_crm_mutation',
                2, 0, 0
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO case_memory_cards VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "card-followup",
                    "shadow-followup",
                    "cw-followup",
                    "zantara_client_captain",
                    "needs_human_review",
                    "P1",
                    "crm_followup",
                    "sahira",
                    "2026-06:42",
                    "case_stall_followup_risk",
                    1,
                    json.dumps(
                        {
                            "event_count": 21,
                            "message_count": 9,
                            "severity_high_count": 3,
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
                    "shadow-payment",
                    "cw-payment",
                    "zantara_client_captain",
                    "monitor_and_prepare",
                    "P2",
                    "payment_reconcile",
                    "surya",
                    "2026-04:15",
                    "payment_reconciliation_needed",
                    2,
                    json.dumps(
                        {
                            "event_count": 8,
                            "message_count": 4,
                            "severity_high_count": 0,
                            "raw_text_included": False,
                        },
                        sort_keys=True,
                    ),
                    0,
                    0,
                    1,
                ),
            ],
        )
        conn.commit()


def test_build_next_best_action_ranker_writes_top_three_actions_per_card(
    tmp_path: Path,
) -> None:
    case_memory_db = tmp_path / "case_memory_cards.local.sqlite"
    output_dir = tmp_path / "next-best-actions"
    summary_path = output_dir / "next_best_actions_summary.md"
    _write_case_memory_db(case_memory_db)

    result = build_next_best_action_ranker(
        case_memory_db=case_memory_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.case_count == 2
    assert result.action_count == 6
    assert result.output_db == output_dir / "next_best_actions.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.top_action_counts == {"crm_followup": 1, "payment_reconcile": 1}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, action_rank, action_code, reason_code,
                   urgency_score, impact_score, combined_score, assigned_lane,
                   send_whatsapp, crm_mutation, requires_human_approval,
                   action_payload_json
            FROM next_best_action_rankings
            ORDER BY case_card_id, action_rank
            """
        ).fetchall()

    followup_rows = [row for row in rows if row[0] == "card-followup"]
    payment_rows = [row for row in rows if row[0] == "card-payment"]
    assert [row[1] for row in followup_rows] == [1, 2, 3]
    assert [row[2] for row in followup_rows] == [
        "crm_followup",
        "operator_system_update",
        "client_status_draft_review",
    ]
    assert [row[3] for row in followup_rows] == [
        "stale_followup",
        "missing_system_update",
        "client_confused_or_silent",
    ]
    assert followup_rows[0][4:7] == (100, 85, 94)
    assert {row[7] for row in followup_rows} == {"sahira"}
    assert [row[2] for row in payment_rows] == [
        "payment_reconcile",
        "ledger_check",
        "proof_of_payment_review",
    ]
    assert payment_rows[0][3] == "payment_risk"
    assert payment_rows[0][4:7] == (70, 90, 78)
    assert {row[8] for row in rows} == {0}
    assert {row[9] for row in rows} == {0}
    assert {row[10] for row in rows} == {1}
    payload = json.loads(followup_rows[0][11])
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["source_case_status"] == "needs_human_review"

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Next Best Action Ranker Summary" in summary
    assert "| Ranked cases | 2 |" in summary
    assert "| Ranked actions | 6 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-followup" not in summary
    assert "shadow-followup" not in summary
    assert "cw-followup" not in summary


def test_build_next_best_action_ranker_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "client_captain_shadow.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Case Memory DB"):
        build_next_best_action_ranker(
            case_memory_db=unexpected_db,
            output_dir=tmp_path / "next-best-actions",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_raw_details(tmp_path: Path) -> None:
    case_memory_db = tmp_path / "case_memory_cards.local.sqlite"
    output_dir = tmp_path / "next-best-actions"
    summary_path = output_dir / "next_best_actions_summary.md"
    _write_case_memory_db(case_memory_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-memory-db",
            str(case_memory_db),
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
    assert payload["action_count"] == 6
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "card-followup" not in result.stdout
    assert "shadow-followup" not in result.stdout
