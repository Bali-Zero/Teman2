from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_evidence_gap_detector import (
    build_evidence_gap_detector,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_evidence_gap_detector.py"


def _write_case_timelines_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE case_timeline_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                war_room_case_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE case_timelines (
                case_card_id TEXT PRIMARY KEY,
                timeline_rank INTEGER NOT NULL,
                timeline_status TEXT NOT NULL,
                highest_risk TEXT NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                latest_movement TEXT NOT NULL,
                blocker_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                has_war_room_item INTEGER NOT NULL,
                timeline_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE TABLE case_timeline_events (
                event_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                event_rank INTEGER NOT NULL,
                event_stage TEXT NOT NULL,
                event_status TEXT NOT NULL,
                event_lane TEXT NOT NULL,
                action_code TEXT NOT NULL,
                event_signal TEXT NOT NULL,
                event_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO case_timeline_runs (
                id, generated_at_utc, privacy_mode, case_count, event_count,
                war_room_case_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, 3, 3, 1, 0, 0)
            """,
            (
                "2026-06-17T10:10:00+00:00",
                "local_only_case_timeline_no_raw_text_no_send_no_crm_mutation",
            ),
        )
        rows = [
            (
                "card-hot-followup",
                1,
                "war_room_active",
                "P1",
                "sahira",
                "crm_followup",
                "client_followup_due",
                "case_stall_followup_risk",
                4,
                1,
            ),
            (
                "card-doc",
                2,
                "operator_due_today",
                "P2",
                "adit",
                "document_chase",
                "document_request_due",
                "document_gap_today",
                3,
                0,
            ),
            (
                "card-pay",
                3,
                "operator_due_today",
                "P2",
                "surya",
                "payment_reconcile",
                "payment_check_due",
                "payment_reconciliation_needed",
                3,
                0,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO case_timelines (
                case_card_id, timeline_rank, timeline_status, highest_risk,
                assigned_lane, primary_action, latest_movement, blocker_code,
                event_count, has_war_room_item, timeline_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    *row,
                    json.dumps(
                        {
                            "schema_version": "case_timeline_synthesizer.v1",
                            "raw_text_included": False,
                        },
                        sort_keys=True,
                    ),
                )
                for row in rows
            ],
        )
        conn.executemany(
            """
            INSERT INTO case_timeline_events (
                event_id, case_card_id, event_rank, event_stage, event_status,
                event_lane, action_code, event_signal, event_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, 1, 'case_memory', ?, ?, ?, ?, ?, 0, 0, 1)
            """,
            [
                (
                    f"event-{row[0]}",
                    row[0],
                    row[2],
                    row[4],
                    row[5],
                    row[7],
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                )
                for row in rows
            ],
        )
        conn.commit()


def test_build_evidence_gap_detector_writes_local_gap_queue(tmp_path: Path) -> None:
    case_timelines_db = tmp_path / "case_timelines.local.sqlite"
    output_dir = tmp_path / "evidence-gaps"
    summary_path = output_dir / "evidence_gaps_summary.md"
    _write_case_timelines_db(case_timelines_db)

    result = build_evidence_gap_detector(
        case_timelines_db=case_timelines_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T11:00:00+00:00",
    )

    assert result.case_count == 3
    assert result.gap_count == 3
    assert result.output_db == output_dir / "evidence_gaps.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.category_counts == {"client_response": 1, "document": 1, "finance": 1}
    assert result.severity_counts == {"urgent": 1, "medium": 2}

    with sqlite3.connect(result.output_db) as conn:
        gaps = conn.execute(
            """
            SELECT case_card_id, gap_rank, assigned_lane, primary_action,
                   gap_code, gap_category, gap_severity, closure_blocker,
                   resolution_gate, send_whatsapp, crm_mutation,
                   requires_human_approval, gap_payload_json
            FROM evidence_gaps
            ORDER BY gap_rank
            """
        ).fetchall()
        run = conn.execute(
            """
            SELECT case_count, gap_count, closure_blocker_count,
                   send_whatsapp_count, crm_mutation_count
            FROM evidence_gap_runs
            WHERE id = 1
            """
        ).fetchone()

    assert run == (3, 3, 3, 0, 0)
    assert gaps[0][0:9] == (
        "card-hot-followup",
        1,
        "sahira",
        "crm_followup",
        "client_followup_confirmation_missing",
        "client_response",
        "urgent",
        1,
        "owner_review_required",
    )
    assert gaps[1][0:9] == (
        "card-doc",
        2,
        "adit",
        "document_chase",
        "required_document_evidence_missing",
        "document",
        "medium",
        1,
        "operator_upload_required",
    )
    assert gaps[2][0:9] == (
        "card-pay",
        3,
        "surya",
        "payment_reconcile",
        "payment_reconciliation_evidence_missing",
        "finance",
        "medium",
        1,
        "operator_upload_required",
    )
    assert {row[9] for row in gaps} == {0}
    assert {row[10] for row in gaps} == {0}
    assert {row[11] for row in gaps} == {1}

    payload = json.loads(gaps[0][12])
    assert payload["schema_version"] == "evidence_gap_detector.v1"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Evidence Gap Detector Summary" in summary
    assert "| Cases reviewed | 3 |" in summary
    assert "| Evidence gaps | 3 |" in summary
    assert "| Closure blockers | 3 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-hot-followup" not in summary
    assert "card-doc" not in summary
    assert "card-pay" not in summary


def test_build_evidence_gap_detector_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "operator_sla_clock.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Case Timelines DB"):
        build_evidence_gap_detector(
            case_timelines_db=unexpected_db,
            output_dir=tmp_path / "evidence-gaps",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_case_details(tmp_path: Path) -> None:
    case_timelines_db = tmp_path / "case_timelines.local.sqlite"
    output_dir = tmp_path / "evidence-gaps"
    summary_path = output_dir / "evidence_gaps_summary.md"
    _write_case_timelines_db(case_timelines_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-timelines-db",
            str(case_timelines_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T11:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "case_count": 3,
        "crm_mutation_count": 0,
        "gap_count": 3,
        "output_db": str(output_dir / "evidence_gaps.local.sqlite"),
        "send_whatsapp_count": 0,
        "summary_path": str(summary_path),
    }
    assert "card-hot-followup" not in result.stdout
    assert "card-doc" not in result.stdout
    assert "card-pay" not in result.stdout
