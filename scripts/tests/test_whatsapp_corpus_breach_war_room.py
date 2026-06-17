from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_breach_war_room import build_breach_war_room

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_breach_war_room.py"


def _write_operator_sla_clock_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_sla_clock_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_inbox_generated_at_utc TEXT NOT NULL,
                as_of_utc TEXT NOT NULL,
                inbox_item_count INTEGER NOT NULL,
                clock_count INTEGER NOT NULL,
                overdue_count INTEGER NOT NULL,
                breach_risk_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_sla_clock (
                inbox_item_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                queue_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                priority_label TEXT NOT NULL,
                queue_bucket TEXT NOT NULL,
                action_code TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                sla_minutes INTEGER NOT NULL,
                source_inbox_generated_at_utc TEXT NOT NULL,
                due_at_utc TEXT NOT NULL,
                as_of_utc TEXT NOT NULL,
                minutes_until_due INTEGER NOT NULL,
                aging_minutes INTEGER NOT NULL,
                sla_status TEXT NOT NULL,
                breach_risk TEXT NOT NULL,
                escalation_label TEXT NOT NULL,
                clock_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO operator_sla_clock_runs VALUES (
                1, '2026-06-17T14:00:00+00:00',
                'local_only_operator_sla_clock_no_raw_text_no_send_no_crm_mutation',
                '2026-06-17T08:00:00+00:00',
                '2026-06-17T14:00:00+00:00',
                4, 4, 1, 2, 0, 0
            )
            """
        )
        rows = [
            (
                "inbox-breached",
                "case-breached",
                4,
                "sahira",
                "now",
                "follow_up_now",
                "crm_followup",
                "stale_followup",
                240,
                "2026-06-17T08:00:00+00:00",
                "2026-06-17T12:00:00+00:00",
                "2026-06-17T14:00:00+00:00",
                -120,
                360,
                "overdue",
                "breached",
                "owner_review",
                json.dumps(
                    {
                        "schema_version": "operator_sla_clock.v1",
                        "raw_text_included": False,
                        "send_whatsapp": False,
                        "crm_mutation": False,
                    },
                    sort_keys=True,
                ),
                0,
                0,
                1,
            ),
            (
                "inbox-high",
                "case-high",
                1,
                "ari",
                "now",
                "status_check_now",
                "immigration_status_check",
                "status_stale",
                240,
                "2026-06-17T08:00:00+00:00",
                "2026-06-17T12:00:00+00:00",
                "2026-06-17T14:00:00+00:00",
                45,
                360,
                "due_today",
                "high",
                "lane_lead_watch",
                json.dumps(
                    {
                        "schema_version": "operator_sla_clock.v1",
                        "raw_text_included": False,
                        "send_whatsapp": False,
                        "crm_mutation": False,
                    },
                    sort_keys=True,
                ),
                0,
                0,
                1,
            ),
            (
                "inbox-medium",
                "case-medium",
                2,
                "adit",
                "today",
                "document_gap_today",
                "document_chase",
                "document_gap",
                1440,
                "2026-06-17T08:00:00+00:00",
                "2026-06-18T08:00:00+00:00",
                "2026-06-17T14:00:00+00:00",
                1080,
                360,
                "due_today",
                "medium",
                "operator_watch",
                json.dumps(
                    {
                        "schema_version": "operator_sla_clock.v1",
                        "raw_text_included": False,
                        "send_whatsapp": False,
                        "crm_mutation": False,
                    },
                    sort_keys=True,
                ),
                0,
                0,
                1,
            ),
            (
                "inbox-low",
                "case-low",
                3,
                "surya",
                "next",
                "finance_next",
                "payment_reconcile",
                "payment_risk",
                4320,
                "2026-06-17T08:00:00+00:00",
                "2026-06-20T08:00:00+00:00",
                "2026-06-17T14:00:00+00:00",
                3960,
                360,
                "scheduled",
                "low",
                "none",
                json.dumps(
                    {
                        "schema_version": "operator_sla_clock.v1",
                        "raw_text_included": False,
                        "send_whatsapp": False,
                        "crm_mutation": False,
                    },
                    sort_keys=True,
                ),
                0,
                0,
                1,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO operator_sla_clock VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )
        conn.commit()


def test_build_breach_war_room_filters_and_orders_hot_clocks(
    tmp_path: Path,
) -> None:
    sla_db = tmp_path / "operator_sla_clock.local.sqlite"
    output_dir = tmp_path / "breach-war-room"
    summary_path = output_dir / "breach_war_room_summary.md"
    _write_operator_sla_clock_db(sla_db)

    result = build_breach_war_room(
        operator_sla_clock_db=sla_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T14:05:00+00:00",
    )

    assert result.clock_count == 4
    assert result.room_item_count == 2
    assert result.output_db == output_dir / "breach_war_room.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.severity_counts == {"critical": 1, "hot": 1}
    assert result.lane_counts == {"sahira": 1, "ari": 1}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT room_item_id, inbox_item_id, case_card_id, war_room_rank,
                   assigned_lane, action_code, breach_risk, sla_status,
                   severity_band, command_channel, decision_gate,
                   send_whatsapp, crm_mutation, requires_human_approval,
                   war_room_payload_json
            FROM breach_war_room
            ORDER BY war_room_rank
            """
        ).fetchall()

    critical = rows[0]
    hot = rows[1]
    assert critical[0:11] == (
        "war-room-000001",
        "inbox-breached",
        "case-breached",
        1,
        "sahira",
        "crm_followup",
        "breached",
        "overdue",
        "critical",
        "owner_war_room",
        "owner_review_required",
    )
    assert hot[0:11] == (
        "war-room-000002",
        "inbox-high",
        "case-high",
        2,
        "ari",
        "immigration_status_check",
        "high",
        "due_today",
        "hot",
        "lane_hot_queue",
        "lane_lead_review_required",
    )
    assert {row[11] for row in rows} == {0}
    assert {row[12] for row in rows} == {0}
    assert {row[13] for row in rows} == {1}
    payload = json.loads(critical[14])
    assert payload["schema_version"] == "breach_war_room.v1"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Breach War Room Summary" in summary
    assert "| SLA clocks reviewed | 4 |" in summary
    assert "| War room items | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "inbox-breached" not in summary
    assert "case-breached" not in summary


def test_build_breach_war_room_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "operator_action_inbox.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected SLA Clock DB"):
        build_breach_war_room(
            operator_sla_clock_db=unexpected_db,
            output_dir=tmp_path / "breach-war-room",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_raw_case_details(tmp_path: Path) -> None:
    sla_db = tmp_path / "operator_sla_clock.local.sqlite"
    output_dir = tmp_path / "breach-war-room"
    summary_path = output_dir / "breach_war_room_summary.md"
    _write_operator_sla_clock_db(sla_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--operator-sla-clock-db",
            str(sla_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T14:05:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["clock_count"] == 4
    assert payload["room_item_count"] == 2
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "inbox-breached" not in result.stdout
    assert "case-breached" not in result.stdout
