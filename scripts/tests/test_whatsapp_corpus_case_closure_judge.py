from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_case_closure_judge import (
    build_case_closure_judge,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_case_closure_judge.py"


def _write_evidence_gaps_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE evidence_gap_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                gap_count INTEGER NOT NULL,
                closure_blocker_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE evidence_gaps (
                gap_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                gap_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                timeline_status TEXT NOT NULL,
                highest_risk TEXT NOT NULL,
                blocker_code TEXT NOT NULL,
                gap_code TEXT NOT NULL,
                gap_category TEXT NOT NULL,
                gap_severity TEXT NOT NULL,
                closure_blocker INTEGER NOT NULL CHECK (closure_blocker = 1),
                resolution_gate TEXT NOT NULL,
                gap_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO evidence_gap_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                case_count, gap_count, closure_blocker_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 3, 3, 3, 0, 0)
            """,
            (
                "2026-06-17T11:00:00+00:00",
                "2026-06-17T10:10:00+00:00",
                "local_only_evidence_gap_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "gap-owner",
                "card-owner",
                1,
                "sahira",
                "crm_followup",
                "war_room_active",
                "P1",
                "case_stall_followup_risk",
                "client_followup_confirmation_missing",
                "client_response",
                "urgent",
                "owner_review_required",
            ),
            (
                "gap-doc",
                "card-doc",
                2,
                "adit",
                "document_chase",
                "operator_due_today",
                "P2",
                "document_gap_today",
                "required_document_evidence_missing",
                "document",
                "medium",
                "operator_upload_required",
            ),
            (
                "gap-lane",
                "card-lane",
                3,
                "ari",
                "immigration_status_check",
                "operator_due_today",
                "P2",
                "immigration_status_gap",
                "immigration_status_evidence_missing",
                "status",
                "medium",
                "lane_review_required",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO evidence_gaps (
                gap_id, case_card_id, gap_rank, assigned_lane, primary_action,
                timeline_status, highest_risk, blocker_code, gap_code,
                gap_category, gap_severity, closure_blocker, resolution_gate,
                gap_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "evidence_gap_detector.v1",
                            "raw_text_included": False,
                        },
                        sort_keys=True,
                    ),
                )
                for row in rows
            ],
        )
        conn.commit()


def test_build_case_closure_judge_writes_case_judgments(tmp_path: Path) -> None:
    evidence_gaps_db = tmp_path / "evidence_gaps.local.sqlite"
    output_dir = tmp_path / "case-closure-judge"
    summary_path = output_dir / "case_closure_judge_summary.md"
    _write_evidence_gaps_db(evidence_gaps_db)

    result = build_case_closure_judge(
        evidence_gaps_db=evidence_gaps_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T12:00:00+00:00",
    )

    assert result.case_count == 3
    assert result.blocked_count == 3
    assert result.ready_to_close_count == 0
    assert result.output_db == output_dir / "case_closure_judge.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.status_counts == {
        "owner_review_blocked": 1,
        "evidence_upload_blocked": 1,
        "lane_review_blocked": 1,
    }

    with sqlite3.connect(result.output_db) as conn:
        judgments = conn.execute(
            """
            SELECT case_card_id, judgment_rank, assigned_lane, primary_action,
                   closure_status, closure_blocker_count, top_gap_code,
                   top_gap_category, top_gap_severity, resolution_gate,
                   owner_attention_required, operator_evidence_required,
                   lane_review_required, send_whatsapp, crm_mutation,
                   requires_human_approval, judge_payload_json
            FROM case_closure_judgments
            ORDER BY judgment_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT case_count, blocked_count, ready_to_close_count,
                   owner_review_count, operator_evidence_count,
                   lane_review_count, send_whatsapp_count, crm_mutation_count
            FROM case_closure_judge_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (3, 3, 0, 1, 1, 1, 0, 0)
    assert judgments[0][0:13] == (
        "card-owner",
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
    )
    assert judgments[1][0:13] == (
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
    )
    assert judgments[2][0:13] == (
        "card-lane",
        3,
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
    )
    assert {row[13] for row in judgments} == {0}
    assert {row[14] for row in judgments} == {0}
    assert {row[15] for row in judgments} == {1}

    payload = json.loads(judgments[0][16])
    assert payload["schema_version"] == "case_closure_judge.v1"
    assert payload["raw_text_included"] is False
    assert payload["closure_decision"] == "blocked"
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Case Closure Judge Summary" in summary
    assert "| Cases judged | 3 |" in summary
    assert "| Blocked cases | 3 |" in summary
    assert "| Ready to close | 0 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-owner" not in summary
    assert "card-doc" not in summary
    assert "card-lane" not in summary


def test_build_case_closure_judge_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "case_timelines.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Evidence Gaps DB"):
        build_case_closure_judge(
            evidence_gaps_db=unexpected_db,
            output_dir=tmp_path / "case-closure-judge",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_case_details(tmp_path: Path) -> None:
    evidence_gaps_db = tmp_path / "evidence_gaps.local.sqlite"
    output_dir = tmp_path / "case-closure-judge"
    summary_path = output_dir / "case_closure_judge_summary.md"
    _write_evidence_gaps_db(evidence_gaps_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--evidence-gaps-db",
            str(evidence_gaps_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T12:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "blocked_count": 3,
        "case_count": 3,
        "crm_mutation_count": 0,
        "output_db": str(output_dir / "case_closure_judge.local.sqlite"),
        "ready_to_close_count": 0,
        "send_whatsapp_count": 0,
        "summary_path": str(summary_path),
    }
    assert "card-owner" not in result.stdout
    assert "card-doc" not in result.stdout
    assert "card-lane" not in result.stdout
