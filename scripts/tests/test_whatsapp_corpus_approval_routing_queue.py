from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_approval_routing_queue import (
    build_approval_routing_queue,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_approval_routing_queue.py"


def _write_owner_brief_renderer_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_brief_renderer_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                brief_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_briefs (
                brief_id TEXT PRIMARY KEY,
                pack_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                brief_title TEXT NOT NULL,
                owner_focus TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                safety_lock TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                brief_markdown TEXT NOT NULL,
                brief_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO owner_brief_renderer_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 4, 2, 2, 2, 0, 0)
            """,
            (
                "2026-06-17T16:00:00+00:00",
                "2026-06-17T15:00:00+00:00",
                "local_only_owner_brief_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "owner-brief-followup",
                "owner-pack-followup",
                "card-owner-followup",
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
                "# Client recovery follow-up approval\n\nPriority: now\nLane: sahira\n",
            ),
            (
                "owner-brief-status",
                "owner-pack-status",
                "card-owner-status",
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
                "# Immigration status escalation approval\n\nPriority: now\nLane: ari\n",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO owner_briefs (
                brief_id, pack_id, case_card_id, brief_rank, assigned_lane,
                decision_type, decision_priority, brief_title, owner_focus,
                recommended_decision, draft_action_type, safety_lock,
                approval_status, brief_markdown, brief_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "owner_brief_renderer.v1",
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


def test_build_approval_routing_queue_writes_owner_queue(
    tmp_path: Path,
) -> None:
    owner_briefs_db = tmp_path / "owner_brief_renderer.local.sqlite"
    output_dir = tmp_path / "approval-routing-queue"
    summary_path = output_dir / "approval_routing_queue_summary.md"
    _write_owner_brief_renderer_db(owner_briefs_db)

    result = build_approval_routing_queue(
        owner_briefs_db=owner_briefs_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T17:00:00+00:00",
    )

    assert result.source_case_count == 4
    assert result.owner_item_count == 2
    assert result.pack_count == 2
    assert result.brief_count == 2
    assert result.queue_item_count == 2
    assert result.output_db == output_dir / "approval_routing_queue.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.decision_type_counts == {
        "approve_client_recovery_followup": 1,
        "approve_immigration_status_escalation": 1,
    }
    assert result.lane_counts == {"sahira": 1, "ari": 1}
    assert result.route_bucket_counts == {"owner_now": 2}

    with sqlite3.connect(result.output_db) as conn:
        routes = conn.execute(
            """
            SELECT case_card_id, brief_id, pack_id, route_rank, assigned_lane,
                   decision_type, decision_priority, owner_focus, route_bucket,
                   next_actor, queue_status, allowed_decisions_json,
                   recommended_decision, draft_action_type, safety_lock,
                   approval_status, send_whatsapp, crm_mutation,
                   requires_human_approval, route_payload_json
            FROM approval_routing_items
            ORDER BY route_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT source_case_count, owner_item_count, pack_count, brief_count,
                   queue_item_count, now_count, send_whatsapp_count,
                   crm_mutation_count
            FROM approval_routing_queue_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (4, 2, 2, 2, 2, 2, 0, 0)
    assert routes[0][0:11] == (
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
    )
    assert json.loads(routes[0][11]) == ["approve", "reject", "defer"]
    assert routes[0][12:19] == (
        "approve_recovery_followup_after_review",
        "owner_review_client_followup_draft",
        "owner_approval_required_no_send_no_crm",
        "pending_owner_review",
        0,
        0,
        1,
    )
    assert routes[1][0:11] == (
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
    )
    assert json.loads(routes[1][11]) == ["approve", "reject", "defer"]

    payload = json.loads(routes[0][19])
    assert payload["schema_version"] == "approval_routing_queue.v1"
    assert payload["privacy_mode"] == "local_only_approval_routing_no_raw_text"
    assert payload["allowed_decisions"] == ["approve", "reject", "defer"]
    assert payload["owner_action_required"] is True
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Approval Routing Queue Summary" in summary
    assert "| Source cases | 4 |" in summary
    assert "| Owner briefs | 2 |" in summary
    assert "| Queue items | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner-followup" not in summary
    assert "card-owner-status" not in summary
    assert "owner-brief-followup" not in summary
    assert "owner-brief-status" not in summary
    assert "owner-pack-followup" not in summary
    assert "owner-pack-status" not in summary


def test_build_approval_routing_queue_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "owner_decision_packs.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(
        ValueError,
        match="Refusing to read unexpected Owner Brief Renderer DB",
    ):
        build_approval_routing_queue(
            owner_briefs_db=unexpected_db,
            output_dir=tmp_path / "approval-routing-queue",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_route_details(tmp_path: Path) -> None:
    owner_briefs_db = tmp_path / "owner_brief_renderer.local.sqlite"
    output_dir = tmp_path / "approval-routing-queue"
    summary_path = output_dir / "approval_routing_queue_summary.md"
    _write_owner_brief_renderer_db(owner_briefs_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-briefs-db",
            str(owner_briefs_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T17:00:00+00:00",
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
        "queue_item_count": 2,
        "send_whatsapp_count": 0,
        "source_case_count": 4,
    }
    assert "card-owner-followup" not in result.stdout
    assert "card-owner-status" not in result.stdout
    assert "owner-brief-followup" not in result.stdout
    assert "owner-brief-status" not in result.stdout
    assert "owner-pack-followup" not in result.stdout
    assert "owner-pack-status" not in result.stdout
