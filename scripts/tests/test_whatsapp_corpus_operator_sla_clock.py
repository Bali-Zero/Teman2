from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_operator_sla_clock import build_operator_sla_clock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_operator_sla_clock.py"


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
                1, '2026-06-17T08:00:00+00:00',
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
                    "inbox-card-followup",
                    "card-followup",
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
                    json.dumps(
                        {
                            "source_risk_level": "P1",
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
                    "inbox-card-payment",
                    "card-payment",
                    2,
                    "surya",
                    "today",
                    "finance_today",
                    "payment_reconcile",
                    "Payment Reconcile",
                    "payment_risk",
                    70,
                    90,
                    78,
                    "Operator must reconcile payment evidence.",
                    "human_review_required",
                    json.dumps(
                        {
                            "source_risk_level": "P2",
                            "latest_movement": "2026-04:15",
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


def test_build_operator_sla_clock_marks_overdue_and_due_today(
    tmp_path: Path,
) -> None:
    inbox_db = tmp_path / "operator_action_inbox.local.sqlite"
    output_dir = tmp_path / "operator-sla-clock"
    summary_path = output_dir / "operator_sla_clock_summary.md"
    _write_operator_inbox_db(inbox_db)

    result = build_operator_sla_clock(
        operator_inbox_db=inbox_db,
        output_dir=output_dir,
        summary_path=summary_path,
        as_of_utc="2026-06-17T13:00:00+00:00",
        generated_at_utc="2026-06-17T13:05:00+00:00",
    )

    assert result.inbox_item_count == 2
    assert result.clock_count == 2
    assert result.output_db == output_dir / "operator_sla_clock.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.status_counts == {"due_today": 1, "overdue": 1}
    assert result.breach_risk_counts == {"breached": 1, "high": 1}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT inbox_item_id, case_card_id, queue_rank, assigned_lane,
                   priority_label, queue_bucket, action_code, sla_minutes,
                   source_inbox_generated_at_utc, due_at_utc, as_of_utc,
                   minutes_until_due, aging_minutes, sla_status, breach_risk,
                   escalation_label, send_whatsapp, crm_mutation,
                   requires_human_approval, clock_payload_json
            FROM operator_sla_clock
            ORDER BY queue_rank
            """
        ).fetchall()

    followup = rows[0]
    payment = rows[1]
    assert followup[0:8] == (
        "inbox-card-followup",
        "card-followup",
        1,
        "sahira",
        "now",
        "follow_up_now",
        "crm_followup",
        240,
    )
    assert followup[8:16] == (
        "2026-06-17T08:00:00+00:00",
        "2026-06-17T12:00:00+00:00",
        "2026-06-17T13:00:00+00:00",
        -60,
        300,
        "overdue",
        "breached",
        "owner_review",
    )
    assert payment[7:16] == (
        480,
        "2026-06-17T08:00:00+00:00",
        "2026-06-17T16:00:00+00:00",
        "2026-06-17T13:00:00+00:00",
        180,
        300,
        "due_today",
        "high",
        "lane_lead_watch",
    )
    assert {row[16] for row in rows} == {0}
    assert {row[17] for row in rows} == {0}
    assert {row[18] for row in rows} == {1}
    payload = json.loads(followup[19])
    assert payload["schema_version"] == "operator_sla_clock.v1"
    assert payload["raw_text_included"] is False
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert payload["requires_human_approval"] is True
    assert payload["source_priority_label"] == "now"

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Operator SLA Clock Summary" in summary
    assert "| Inbox items reviewed | 2 |" in summary
    assert "| SLA clocks | 2 |" in summary
    assert "| Overdue clocks | 1 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "card-followup" not in summary
    assert "inbox-card-followup" not in summary


def test_build_operator_sla_clock_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "next_best_actions.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Operator Inbox DB"):
        build_operator_sla_clock(
            operator_inbox_db=unexpected_db,
            output_dir=tmp_path / "operator-sla-clock",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_raw_case_details(tmp_path: Path) -> None:
    inbox_db = tmp_path / "operator_action_inbox.local.sqlite"
    output_dir = tmp_path / "operator-sla-clock"
    summary_path = output_dir / "operator_sla_clock_summary.md"
    _write_operator_inbox_db(inbox_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--operator-inbox-db",
            str(inbox_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--as-of-utc",
            "2026-06-17T13:00:00+00:00",
            "--generated-at-utc",
            "2026-06-17T13:05:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["inbox_item_count"] == 2
    assert payload["clock_count"] == 2
    assert payload["overdue_count"] == 1
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "card-followup" not in result.stdout
    assert "inbox-card-followup" not in result.stdout
