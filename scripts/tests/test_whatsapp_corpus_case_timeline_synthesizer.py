from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_case_timeline_synthesizer import (
    build_case_timeline_synthesizer,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_case_timeline_synthesizer.py"


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
                1, '2026-06-17T08:00:00+00:00',
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
                    "card-hot",
                    "shadow-hot",
                    "window-hot",
                    "zantara",
                    "needs_human_review",
                    "P1",
                    "crm_followup",
                    "sahira",
                    "2026-06:42",
                    "case_stall_followup_risk",
                    1,
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
                (
                    "card-cool",
                    "shadow-cool",
                    "window-cool",
                    "zantara",
                    "monitor_and_prepare",
                    "P2",
                    "document_chase",
                    "adit",
                    "2026-04:15",
                    "document_gap",
                    2,
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
            ],
        )
        conn.commit()


def _write_operator_inbox_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_action_inbox_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                inbox_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_action_inbox (
                inbox_item_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                queue_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                priority_label TEXT NOT NULL,
                queue_bucket TEXT NOT NULL,
                action_code TEXT NOT NULL,
                action_title TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                urgency_score INTEGER NOT NULL,
                impact_score INTEGER NOT NULL,
                combined_score INTEGER NOT NULL,
                operator_instruction TEXT NOT NULL,
                approval_mode TEXT NOT NULL,
                item_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO operator_action_inbox_runs VALUES (
                1, '2026-06-17T09:00:00+00:00',
                'local_only_operator_action_inbox_no_raw_text_no_send_no_crm_mutation',
                2, 2, 0, 0
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO operator_action_inbox VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "inbox-hot",
                    "card-hot",
                    1,
                    "sahira",
                    "now",
                    "follow_up_now",
                    "crm_followup",
                    "Crm Followup",
                    "stale_followup",
                    100,
                    85,
                    94,
                    "Operator must review the CRM follow-up.",
                    "human_review_required",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
                (
                    "inbox-cool",
                    "card-cool",
                    2,
                    "adit",
                    "today",
                    "document_gap_today",
                    "document_chase",
                    "Document Chase",
                    "document_gap",
                    70,
                    75,
                    72,
                    "Operator must review document evidence.",
                    "human_review_required",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
            ],
        )
        conn.commit()


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
                1, '2026-06-17T10:00:00+00:00',
                'local_only_operator_sla_clock_no_raw_text_no_send_no_crm_mutation',
                '2026-06-17T09:00:00+00:00',
                '2026-06-17T10:00:00+00:00',
                2, 2, 0, 1, 0, 0
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO operator_sla_clock VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "inbox-hot",
                    "card-hot",
                    1,
                    "sahira",
                    "now",
                    "follow_up_now",
                    "crm_followup",
                    "stale_followup",
                    240,
                    "2026-06-17T09:00:00+00:00",
                    "2026-06-17T13:00:00+00:00",
                    "2026-06-17T10:00:00+00:00",
                    180,
                    60,
                    "due_today",
                    "high",
                    "lane_lead_watch",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
                (
                    "inbox-cool",
                    "card-cool",
                    2,
                    "adit",
                    "today",
                    "document_gap_today",
                    "document_chase",
                    "document_gap",
                    1440,
                    "2026-06-17T09:00:00+00:00",
                    "2026-06-18T09:00:00+00:00",
                    "2026-06-17T10:00:00+00:00",
                    1380,
                    60,
                    "due_today",
                    "medium",
                    "operator_watch",
                    json.dumps({"raw_text_included": False}, sort_keys=True),
                    0,
                    0,
                    1,
                ),
            ],
        )
        conn.commit()


def _write_breach_war_room_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE breach_war_room_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_sla_clock_generated_at_utc TEXT NOT NULL,
                source_as_of_utc TEXT NOT NULL,
                clock_count INTEGER NOT NULL,
                room_item_count INTEGER NOT NULL,
                critical_count INTEGER NOT NULL,
                hot_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE breach_war_room (
                room_item_id TEXT PRIMARY KEY,
                inbox_item_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                source_queue_rank INTEGER NOT NULL,
                war_room_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                priority_label TEXT NOT NULL,
                queue_bucket TEXT NOT NULL,
                action_code TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                due_at_utc TEXT NOT NULL,
                as_of_utc TEXT NOT NULL,
                minutes_until_due INTEGER NOT NULL,
                aging_minutes INTEGER NOT NULL,
                sla_status TEXT NOT NULL,
                breach_risk TEXT NOT NULL,
                escalation_label TEXT NOT NULL,
                severity_band TEXT NOT NULL,
                command_channel TEXT NOT NULL,
                decision_gate TEXT NOT NULL,
                captain_instruction TEXT NOT NULL,
                war_room_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO breach_war_room_runs VALUES (
                1, '2026-06-17T10:05:00+00:00',
                'local_only_breach_war_room_no_raw_text_no_send_no_crm_mutation',
                '2026-06-17T10:00:00+00:00',
                '2026-06-17T10:00:00+00:00',
                2, 1, 0, 1, 0, 0
            )
            """
        )
        conn.execute(
            """
            INSERT INTO breach_war_room VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                "war-room-hot",
                "inbox-hot",
                "card-hot",
                1,
                1,
                "sahira",
                "now",
                "follow_up_now",
                "crm_followup",
                "stale_followup",
                "2026-06-17T13:00:00+00:00",
                "2026-06-17T10:00:00+00:00",
                180,
                60,
                "due_today",
                "high",
                "lane_lead_watch",
                "hot",
                "lane_hot_queue",
                "lane_lead_review_required",
                "Review Sahira CRM follow-up SLA clock.",
                json.dumps({"raw_text_included": False}, sort_keys=True),
                0,
                0,
                1,
            ),
        )
        conn.commit()


def test_build_case_timeline_synthesizer_writes_operational_timeline(
    tmp_path: Path,
) -> None:
    case_memory_db = tmp_path / "case_memory_cards.local.sqlite"
    operator_inbox_db = tmp_path / "operator_action_inbox.local.sqlite"
    operator_sla_clock_db = tmp_path / "operator_sla_clock.local.sqlite"
    breach_war_room_db = tmp_path / "breach_war_room.local.sqlite"
    output_dir = tmp_path / "case-timelines"
    summary_path = output_dir / "case_timelines_summary.md"
    _write_case_memory_db(case_memory_db)
    _write_operator_inbox_db(operator_inbox_db)
    _write_operator_sla_clock_db(operator_sla_clock_db)
    _write_breach_war_room_db(breach_war_room_db)

    result = build_case_timeline_synthesizer(
        case_memory_db=case_memory_db,
        operator_inbox_db=operator_inbox_db,
        operator_sla_clock_db=operator_sla_clock_db,
        breach_war_room_db=breach_war_room_db,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-17T10:10:00+00:00",
    )

    assert result.case_count == 2
    assert result.event_count == 7
    assert result.output_db == output_dir / "case_timelines.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.status_counts == {"war_room_active": 1, "operator_due_today": 1}
    assert result.lane_counts == {"sahira": 1, "adit": 1}

    with sqlite3.connect(result.output_db) as conn:
        timelines = conn.execute(
            """
            SELECT case_card_id, timeline_status, highest_risk, assigned_lane,
                   primary_action, event_count, has_war_room_item,
                   send_whatsapp, crm_mutation, requires_human_approval,
                   timeline_payload_json
            FROM case_timelines
            ORDER BY timeline_rank
            """
        ).fetchall()
        events = conn.execute(
            """
            SELECT case_card_id, event_rank, event_stage, event_status,
                   event_lane, action_code, event_payload_json,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM case_timeline_events
            ORDER BY case_card_id, event_rank
            """
        ).fetchall()

    assert timelines[0][0:7] == (
        "card-hot",
        "war_room_active",
        "P1",
        "sahira",
        "crm_followup",
        4,
        1,
    )
    assert timelines[1][0:7] == (
        "card-cool",
        "operator_due_today",
        "P2",
        "adit",
        "document_chase",
        3,
        0,
    )
    assert {row[7] for row in timelines} == {0}
    assert {row[8] for row in timelines} == {0}
    assert {row[9] for row in timelines} == {1}
    payload = json.loads(timelines[0][10])
    assert payload["schema_version"] == "case_timeline_synthesizer.v1"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True

    hot_stages = [row[2] for row in events if row[0] == "card-hot"]
    cool_stages = [row[2] for row in events if row[0] == "card-cool"]
    assert hot_stages == ["case_memory", "operator_action", "sla_clock", "war_room"]
    assert cool_stages == ["case_memory", "operator_action", "sla_clock"]
    assert {row[7] for row in events} == {0}
    assert {row[8] for row in events} == {0}
    assert {row[9] for row in events} == {1}
    assert json.loads(events[0][6])["raw_text_included"] is False

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Case Timeline Synthesizer Summary" in summary
    assert "| Cases synthesized | 2 |" in summary
    assert "| Timeline events | 7 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-hot" not in summary
    assert "inbox-hot" not in summary
    assert "war-room-hot" not in summary


def test_build_case_timeline_synthesizer_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "operator_sla_clock.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Case Memory DB"):
        build_case_timeline_synthesizer(
            case_memory_db=unexpected_db,
            operator_inbox_db=tmp_path / "operator_action_inbox.local.sqlite",
            operator_sla_clock_db=tmp_path / "operator_sla_clock.local.sqlite",
            breach_war_room_db=tmp_path / "breach_war_room.local.sqlite",
            output_dir=tmp_path / "case-timelines",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_raw_case_details(tmp_path: Path) -> None:
    case_memory_db = tmp_path / "case_memory_cards.local.sqlite"
    operator_inbox_db = tmp_path / "operator_action_inbox.local.sqlite"
    operator_sla_clock_db = tmp_path / "operator_sla_clock.local.sqlite"
    breach_war_room_db = tmp_path / "breach_war_room.local.sqlite"
    output_dir = tmp_path / "case-timelines"
    summary_path = output_dir / "case_timelines_summary.md"
    _write_case_memory_db(case_memory_db)
    _write_operator_inbox_db(operator_inbox_db)
    _write_operator_sla_clock_db(operator_sla_clock_db)
    _write_breach_war_room_db(breach_war_room_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-memory-db",
            str(case_memory_db),
            "--operator-inbox-db",
            str(operator_inbox_db),
            "--operator-sla-clock-db",
            str(operator_sla_clock_db),
            "--breach-war-room-db",
            str(breach_war_room_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-17T10:10:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["case_count"] == 2
    assert payload["event_count"] == 7
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "card-hot" not in result.stdout
    assert "inbox-hot" not in result.stdout
    assert "war-room-hot" not in result.stdout
