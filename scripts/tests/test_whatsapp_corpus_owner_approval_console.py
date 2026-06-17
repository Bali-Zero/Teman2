from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_owner_approval_console import (
    build_owner_approval_console,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_approval_console.py"


def _write_case_closure_judge_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE case_closure_judge_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                blocked_count INTEGER NOT NULL,
                ready_to_close_count INTEGER NOT NULL,
                owner_review_count INTEGER NOT NULL,
                operator_evidence_count INTEGER NOT NULL,
                lane_review_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE case_closure_judgments (
                judgment_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                judgment_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                closure_status TEXT NOT NULL,
                closure_blocker_count INTEGER NOT NULL,
                top_gap_code TEXT NOT NULL,
                top_gap_category TEXT NOT NULL,
                top_gap_severity TEXT NOT NULL,
                resolution_gate TEXT NOT NULL,
                owner_attention_required INTEGER NOT NULL,
                operator_evidence_required INTEGER NOT NULL,
                lane_review_required INTEGER NOT NULL,
                judge_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO case_closure_judge_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                case_count, blocked_count, ready_to_close_count,
                owner_review_count, operator_evidence_count, lane_review_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 4, 4, 0, 2, 1, 1, 0, 0)
            """,
            (
                "2026-06-17T12:00:00+00:00",
                "2026-06-17T11:00:00+00:00",
                "local_only_case_closure_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "closure-owner-followup",
                "card-owner-followup",
                1,
                "sahira",
                "crm_followup",
                "owner_review_blocked",
                1,
                "client_followup_confirmation_missing",
                "client_response",
                "urgent",
                "owner_review_required",
                1,
                0,
                0,
            ),
            (
                "closure-doc",
                "card-doc",
                2,
                "adit",
                "document_chase",
                "evidence_upload_blocked",
                1,
                "required_document_evidence_missing",
                "document",
                "medium",
                "operator_upload_required",
                0,
                1,
                0,
            ),
            (
                "closure-owner-status",
                "card-owner-status",
                3,
                "ari",
                "immigration_status_check",
                "owner_review_blocked",
                1,
                "immigration_status_evidence_missing",
                "status",
                "urgent",
                "owner_review_required",
                1,
                0,
                0,
            ),
            (
                "closure-lane",
                "card-lane",
                4,
                "ari",
                "immigration_status_check",
                "lane_review_blocked",
                1,
                "immigration_status_evidence_missing",
                "status",
                "medium",
                "lane_review_required",
                0,
                0,
                1,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO case_closure_judgments (
                judgment_id, case_card_id, judgment_rank, assigned_lane,
                primary_action, closure_status, closure_blocker_count,
                top_gap_code, top_gap_category, top_gap_severity,
                resolution_gate, owner_attention_required,
                operator_evidence_required, lane_review_required,
                judge_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "case_closure_judge.v1",
                            "raw_text_included": False,
                        },
                        sort_keys=True,
                    ),
                )
                for row in rows
            ],
        )
        conn.commit()


def test_build_owner_approval_console_filters_owner_decisions(tmp_path: Path) -> None:
    case_closure_db = tmp_path / "case_closure_judge.local.sqlite"
    output_dir = tmp_path / "owner-approval-console"
    summary_path = output_dir / "owner_approval_console_summary.md"
    _write_case_closure_judge_db(case_closure_db)

    result = build_owner_approval_console(
        case_closure_db=case_closure_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T13:00:00+00:00",
    )

    assert result.source_case_count == 4
    assert result.owner_item_count == 2
    assert result.output_db == output_dir / "owner_approval_console.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.decision_type_counts == {
        "approve_client_recovery_followup": 1,
        "approve_immigration_status_escalation": 1,
    }
    assert result.lane_counts == {"sahira": 1, "ari": 1}

    with sqlite3.connect(result.output_db) as conn:
        items = conn.execute(
            """
            SELECT case_card_id, approval_rank, assigned_lane, primary_action,
                   decision_type, decision_priority, owner_prompt_code,
                   recommended_owner_action, approval_status, top_gap_code,
                   top_gap_category, top_gap_severity, resolution_gate,
                   owner_decision_required, send_whatsapp, crm_mutation,
                   requires_human_approval, approval_payload_json
            FROM owner_approval_items
            ORDER BY approval_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, urgent_item_count,
                   send_whatsapp_count, crm_mutation_count
            FROM owner_approval_console_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (4, 2, 2, 0, 0)
    assert items[0][0:14] == (
        "card-owner-followup",
        1,
        "sahira",
        "crm_followup",
        "approve_client_recovery_followup",
        "now",
        "owner_client_recovery_followup",
        "Review and approve the client recovery follow-up before any message is sent.",
        "pending_owner_review",
        "client_followup_confirmation_missing",
        "client_response",
        "urgent",
        "owner_review_required",
        1,
    )
    assert items[1][0:14] == (
        "card-owner-status",
        2,
        "ari",
        "immigration_status_check",
        "approve_immigration_status_escalation",
        "now",
        "owner_immigration_status_escalation",
        "Review and approve the immigration status escalation before any message is sent.",
        "pending_owner_review",
        "immigration_status_evidence_missing",
        "status",
        "urgent",
        "owner_review_required",
        1,
    )
    assert {row[14] for row in items} == {0}
    assert {row[15] for row in items} == {0}
    assert {row[16] for row in items} == {1}

    payload = json.loads(items[0][17])
    assert payload["schema_version"] == "owner_approval_console.v1"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Approval Console Summary" in summary
    assert "| Source cases judged | 4 |" in summary
    assert "| Owner approval items | 2 |" in summary
    assert "| Urgent owner items | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-followup" not in summary
    assert "card-owner-status" not in summary
    assert "card-doc" not in summary
    assert "card-lane" not in summary


def test_build_owner_approval_console_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "evidence_gaps.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Case Closure DB"):
        build_owner_approval_console(
            case_closure_db=unexpected_db,
            output_dir=tmp_path / "owner-approval-console",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_case_details(tmp_path: Path) -> None:
    case_closure_db = tmp_path / "case_closure_judge.local.sqlite"
    output_dir = tmp_path / "owner-approval-console"
    summary_path = output_dir / "owner_approval_console_summary.md"
    _write_case_closure_judge_db(case_closure_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-closure-db",
            str(case_closure_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T13:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "crm_mutation_count": 0,
        "owner_item_count": 2,
        "send_whatsapp_count": 0,
        "source_case_count": 4,
    }
    assert "card-owner-followup" not in result.stdout
    assert "card-owner-status" not in result.stdout
    assert "card-doc" not in result.stdout
    assert "card-lane" not in result.stdout
