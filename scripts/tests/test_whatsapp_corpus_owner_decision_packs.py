from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_owner_decision_packs import (
    build_owner_decision_packs,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_decision_packs.py"


def _write_owner_approval_console_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_approval_console_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                urgent_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_approval_items (
                approval_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                approval_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                closure_status TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                owner_prompt_code TEXT NOT NULL,
                recommended_owner_action TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                top_gap_code TEXT NOT NULL,
                top_gap_category TEXT NOT NULL,
                top_gap_severity TEXT NOT NULL,
                resolution_gate TEXT NOT NULL,
                owner_decision_required INTEGER NOT NULL CHECK (owner_decision_required = 1),
                approval_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO owner_approval_console_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, urgent_item_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 4, 2, 2, 0, 0)
            """,
            (
                "2026-06-17T14:00:00+00:00",
                "2026-06-17T13:00:00+00:00",
                "local_only_owner_approval_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "owner-approval-followup",
                "card-owner-followup",
                1,
                "sahira",
                "crm_followup",
                "owner_review_blocked",
                "approve_client_recovery_followup",
                "now",
                "owner_client_recovery_followup",
                "Review and approve the client recovery follow-up before any message is sent.",
                "pending_owner_review",
                "client_followup_confirmation_missing",
                "client_response",
                "urgent",
                "owner_review_required",
            ),
            (
                "owner-approval-status",
                "card-owner-status",
                2,
                "ari",
                "immigration_status_check",
                "owner_review_blocked",
                "approve_immigration_status_escalation",
                "now",
                "owner_immigration_status_escalation",
                "Review and approve the immigration status escalation before any message is sent.",
                "pending_owner_review",
                "immigration_status_evidence_missing",
                "status",
                "urgent",
                "owner_review_required",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO owner_approval_items (
                approval_id, case_card_id, approval_rank, assigned_lane,
                primary_action, closure_status, decision_type, decision_priority,
                owner_prompt_code, recommended_owner_action, approval_status,
                top_gap_code, top_gap_category, top_gap_severity, resolution_gate,
                owner_decision_required, approval_payload_json, send_whatsapp,
                crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "owner_approval_console.v1",
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


def test_build_owner_decision_packs_writes_owner_ready_packets(tmp_path: Path) -> None:
    owner_approval_db = tmp_path / "owner_approval_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-packs"
    summary_path = output_dir / "owner_decision_packs_summary.md"
    _write_owner_approval_console_db(owner_approval_db)

    result = build_owner_decision_packs(
        owner_approval_db=owner_approval_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T15:00:00+00:00",
    )

    assert result.source_case_count == 4
    assert result.owner_item_count == 2
    assert result.pack_count == 2
    assert result.output_db == output_dir / "owner_decision_packs.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.decision_type_counts == {
        "approve_client_recovery_followup": 1,
        "approve_immigration_status_escalation": 1,
    }
    assert result.lane_counts == {"sahira": 1, "ari": 1}

    with sqlite3.connect(result.output_db) as conn:
        packs = conn.execute(
            """
            SELECT case_card_id, pack_rank, assigned_lane, decision_type,
                   decision_priority, pack_title, risk_brief,
                   recommended_decision, draft_action_type,
                   draft_action_status, approval_status, top_gap_code,
                   top_gap_category, top_gap_severity, resolution_gate,
                   owner_decision_required, send_whatsapp, crm_mutation,
                   requires_human_approval, pack_payload_json
            FROM owner_decision_packs
            ORDER BY pack_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count,
                   urgent_pack_count, send_whatsapp_count, crm_mutation_count
            FROM owner_decision_pack_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (4, 2, 2, 2, 0, 0)
    assert packs[0][0:16] == (
        "card-owner-followup",
        1,
        "sahira",
        "approve_client_recovery_followup",
        "now",
        "Client recovery follow-up approval",
        "Urgent client response gap requires owner-approved recovery follow-up.",
        "approve_recovery_followup_after_review",
        "owner_review_client_followup_draft",
        "draft_ready_for_owner_review",
        "pending_owner_review",
        "client_followup_confirmation_missing",
        "client_response",
        "urgent",
        "owner_review_required",
        1,
    )
    assert packs[1][0:16] == (
        "card-owner-status",
        2,
        "ari",
        "approve_immigration_status_escalation",
        "now",
        "Immigration status escalation approval",
        "Urgent immigration status gap requires owner-approved escalation.",
        "approve_status_escalation_after_review",
        "owner_review_status_escalation_draft",
        "draft_ready_for_owner_review",
        "pending_owner_review",
        "immigration_status_evidence_missing",
        "status",
        "urgent",
        "owner_review_required",
        1,
    )
    assert {row[16] for row in packs} == {0}
    assert {row[17] for row in packs} == {0}
    assert {row[18] for row in packs} == {1}

    payload = json.loads(packs[0][19])
    assert payload["schema_version"] == "owner_decision_packs.v1"
    assert payload["privacy_mode"] == "local_only_owner_decision_pack_no_raw_text"
    assert payload["source_owner_prompt_code"] == "owner_client_recovery_followup"
    assert payload["owner_decision_required"] is True
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Decision Packs Summary" in summary
    assert "| Source cases | 4 |" in summary
    assert "| Owner approval items | 2 |" in summary
    assert "| Owner decision packs | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-followup" not in summary
    assert "card-owner-status" not in summary
    assert "owner-approval-followup" not in summary
    assert "owner-approval-status" not in summary


def test_build_owner_decision_packs_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "case_closure_judge.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Owner Approval Console DB",
    ):
        build_owner_decision_packs(
            owner_approval_db=unexpected_db,
            output_dir=tmp_path / "owner-decision-packs",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_owner_case_details(tmp_path: Path) -> None:
    owner_approval_db = tmp_path / "owner_approval_console.local.sqlite"
    output_dir = tmp_path / "owner-decision-packs"
    summary_path = output_dir / "owner_decision_packs_summary.md"
    _write_owner_approval_console_db(owner_approval_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-approval-db",
            str(owner_approval_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T15:00:00+00:00",
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
        "pack_count": 2,
        "send_whatsapp_count": 0,
        "source_case_count": 4,
    }
    assert "card-owner-followup" not in result.stdout
    assert "card-owner-status" not in result.stdout
    assert "owner-approval-followup" not in result.stdout
    assert "owner-approval-status" not in result.stdout
