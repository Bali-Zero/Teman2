from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_owner_brief_renderer import build_owner_brief_renderer

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_brief_renderer.py"


def _write_owner_decision_packs_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_decision_pack_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                urgent_pack_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_decision_packs (
                pack_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                pack_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                owner_prompt_code TEXT NOT NULL,
                pack_title TEXT NOT NULL,
                risk_brief TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                draft_action_status TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                top_gap_code TEXT NOT NULL,
                top_gap_category TEXT NOT NULL,
                top_gap_severity TEXT NOT NULL,
                resolution_gate TEXT NOT NULL,
                owner_decision_required INTEGER NOT NULL CHECK (owner_decision_required = 1),
                pack_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_pack_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count,
                urgent_pack_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 4, 2, 2, 2, 0, 0)
            """,
            (
                "2026-06-17T15:00:00+00:00",
                "2026-06-17T14:00:00+00:00",
                "local_only_owner_decision_pack_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "owner-pack-followup",
                "card-owner-followup",
                1,
                "sahira",
                "approve_client_recovery_followup",
                "now",
                "owner_client_recovery_followup",
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
            ),
            (
                "owner-pack-status",
                "card-owner-status",
                2,
                "ari",
                "approve_immigration_status_escalation",
                "now",
                "owner_immigration_status_escalation",
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
            ),
        ]
        conn.executemany(
            """
            INSERT INTO owner_decision_packs (
                pack_id, case_card_id, pack_rank, assigned_lane, decision_type,
                decision_priority, owner_prompt_code, pack_title, risk_brief,
                recommended_decision, draft_action_type, draft_action_status,
                approval_status, top_gap_code, top_gap_category, top_gap_severity,
                resolution_gate, owner_decision_required, pack_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "owner_decision_packs.v1",
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


def test_build_owner_brief_renderer_writes_readable_owner_briefs(
    tmp_path: Path,
) -> None:
    owner_packs_db = tmp_path / "owner_decision_packs.local.sqlite"
    output_dir = tmp_path / "owner-brief-renderer"
    summary_path = output_dir / "owner_brief_renderer_summary.md"
    _write_owner_decision_packs_db(owner_packs_db)

    result = build_owner_brief_renderer(
        owner_packs_db=owner_packs_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T16:00:00+00:00",
    )

    assert result.source_case_count == 4
    assert result.owner_item_count == 2
    assert result.pack_count == 2
    assert result.brief_count == 2
    assert result.output_db == output_dir / "owner_brief_renderer.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.decision_type_counts == {
        "approve_client_recovery_followup": 1,
        "approve_immigration_status_escalation": 1,
    }
    assert result.lane_counts == {"sahira": 1, "ari": 1}

    with sqlite3.connect(result.output_db) as conn:
        briefs = conn.execute(
            """
            SELECT case_card_id, pack_id, brief_rank, assigned_lane,
                   decision_type, decision_priority, brief_title,
                   owner_focus, recommended_decision, draft_action_type,
                   safety_lock, approval_status, send_whatsapp,
                   crm_mutation, requires_human_approval, brief_markdown,
                   brief_payload_json
            FROM owner_briefs
            ORDER BY brief_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count,
                   brief_count, send_whatsapp_count, crm_mutation_count
            FROM owner_brief_renderer_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (4, 2, 2, 2, 0, 0)
    assert briefs[0][0:15] == (
        "card-owner-followup",
        "owner-pack-followup",
        1,
        "sahira",
        "approve_client_recovery_followup",
        "now",
        "Client recovery follow-up approval",
        "review_client_recovery_language",
        "approve_recovery_followup_after_review",
        "owner_review_client_followup_draft",
        "owner_approval_required_no_send_no_crm",
        "pending_owner_review",
        0,
        0,
        1,
    )
    assert briefs[1][0:15] == (
        "card-owner-status",
        "owner-pack-status",
        2,
        "ari",
        "approve_immigration_status_escalation",
        "now",
        "Immigration status escalation approval",
        "review_immigration_status_escalation",
        "approve_status_escalation_after_review",
        "owner_review_status_escalation_draft",
        "owner_approval_required_no_send_no_crm",
        "pending_owner_review",
        0,
        0,
        1,
    )

    markdown = briefs[0][15]
    assert "# Client recovery follow-up approval" in markdown
    assert "Priority: now" in markdown
    assert "Lane: sahira" in markdown
    assert "Safety lock: owner approval required before send or CRM mutation." in markdown
    assert "card-owner-followup" not in markdown
    assert "owner-pack-followup" not in markdown

    payload = json.loads(briefs[0][16])
    assert payload["schema_version"] == "owner_brief_renderer.v1"
    assert payload["privacy_mode"] == "local_only_owner_brief_no_raw_text"
    assert payload["rendered_markdown_includes_ids"] is False
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Brief Renderer Summary" in summary
    assert "| Source cases | 4 |" in summary
    assert "| Owner decision packs | 2 |" in summary
    assert "| Rendered owner briefs | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-followup" not in summary
    assert "card-owner-status" not in summary
    assert "owner-pack-followup" not in summary
    assert "owner-pack-status" not in summary


def test_build_owner_brief_renderer_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "owner_approval_console.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Owner Decision Packs DB",
    ):
        build_owner_brief_renderer(
            owner_packs_db=unexpected_db,
            output_dir=tmp_path / "owner-brief-renderer",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_owner_brief_details(tmp_path: Path) -> None:
    owner_packs_db = tmp_path / "owner_decision_packs.local.sqlite"
    output_dir = tmp_path / "owner-brief-renderer"
    summary_path = output_dir / "owner_brief_renderer_summary.md"
    _write_owner_decision_packs_db(owner_packs_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-packs-db",
            str(owner_packs_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T16:00:00+00:00",
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
        "owner_item_count": 2,
        "pack_count": 2,
        "send_whatsapp_count": 0,
        "source_case_count": 4,
    }
    assert "card-owner-followup" not in result.stdout
    assert "card-owner-status" not in result.stdout
    assert "owner-pack-followup" not in result.stdout
    assert "owner-pack-status" not in result.stdout
