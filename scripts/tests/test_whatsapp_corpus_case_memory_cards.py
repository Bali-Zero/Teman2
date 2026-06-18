from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_case_memory_cards import build_case_memory_cards

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_case_memory_cards.py"


def _write_client_shadow_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE shadow_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                draft_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE shadow_drafts (
                shadow_id TEXT PRIMARY KEY,
                source_example_id TEXT NOT NULL,
                source_replay_id TEXT NOT NULL,
                source_window_id TEXT NOT NULL,
                source_file_id TEXT NOT NULL,
                case_owner TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                action_type TEXT NOT NULL,
                human_specialist TEXT NOT NULL,
                diagnosis_code TEXT NOT NULL,
                draft_reply_intent TEXT NOT NULL,
                operator_coaching_mode TEXT NOT NULL,
                operator_nudge TEXT NOT NULL,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL,
                first_message_index INTEGER NOT NULL,
                last_message_index INTEGER NOT NULL,
                cut_message_index INTEGER NOT NULL,
                dominant_domain TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL,
                severity_high_count INTEGER NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE TABLE shadow_depth_layers (
                shadow_id TEXT NOT NULL,
                depth_level INTEGER NOT NULL,
                layer_code TEXT NOT NULL,
                layer_title TEXT NOT NULL,
                layer_payload_json TEXT NOT NULL,
                PRIMARY KEY (shadow_id, depth_level)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO shadow_runs VALUES (
                1, '2026-06-16T00:00:00+00:00',
                'local_only_shadow_drafts_no_send_no_crm_mutation', 2, 0, 0
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO shadow_drafts VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "shadow-followup",
                    "cca-followup",
                    "replay-followup",
                    "cw-followup",
                    "wa-file-alpha",
                    "zantara_client_captain",
                    "shadow_draft",
                    "high",
                    "P1",
                    "crm_followup",
                    "sahira",
                    "case_stall_followup_risk",
                    "Draft a status follow-up after a human confirms the latest system update.",
                    "firm_accountability_nudge",
                    "Firm: operator must make a system update before continuing.",
                    "2026-05",
                    "2026-06",
                    10,
                    42,
                    26,
                    "followup_risk",
                    21,
                    9,
                    2,
                    3,
                    0,
                    0,
                    1,
                ),
                (
                    "shadow-payment",
                    "cca-payment",
                    "replay-payment",
                    "cw-payment",
                    "wa-file-beta",
                    "zantara_client_captain",
                    "shadow_draft",
                    "normal",
                    "P2",
                    "payment_reconcile",
                    "surya",
                    "payment_reconciliation_needed",
                    "Draft a payment clarification after finance verifies the ledger.",
                    "steady_family_motivation",
                    "Supportive: keep the operator moving.",
                    "2026-04",
                    "2026-04",
                    3,
                    15,
                    9,
                    "tax_payment",
                    8,
                    4,
                    1,
                    0,
                    0,
                    0,
                    1,
                ),
            ],
        )
        layer_rows = []
        for shadow_id in ("shadow-followup", "shadow-payment"):
            for level, code in enumerate(
                [
                    "signal_readout",
                    "case_diagnosis",
                    "captain_decision",
                    "draft_gate",
                    "operator_coaching",
                ],
                start=1,
            ):
                layer_rows.append(
                    (
                        shadow_id,
                        level,
                        code,
                        code.replace("_", " ").title(),
                        json.dumps(
                            {
                                "send_whatsapp": False,
                                "crm_mutation": False,
                                "requires_human_approval": True,
                            },
                            sort_keys=True,
                        ),
                    )
                )
        conn.executemany(
            """
            INSERT INTO shadow_depth_layers (
                shadow_id, depth_level, layer_code, layer_title, layer_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            layer_rows,
        )
        conn.commit()


def test_build_case_memory_cards_writes_compact_local_cards(tmp_path: Path) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    output_dir = tmp_path / "case-memory-cards"
    summary_path = output_dir / "case_memory_cards_summary.md"
    _write_client_shadow_db(client_shadow_db)

    result = build_case_memory_cards(
        client_shadow_db=client_shadow_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.card_count == 2
    assert result.output_db == output_dir / "case_memory_cards.local.sqlite"
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.risk_counts == {"P1": 1, "P2": 1}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, source_shadow_id, case_status, risk_level,
                   next_best_action, assigned_lane, latest_movement, blocker_code,
                   review_rank, send_whatsapp, crm_mutation, requires_human_approval,
                   card_payload_json
            FROM case_memory_cards
            ORDER BY review_rank, case_card_id
            """
        ).fetchall()

    assert len(rows) == 2
    assert rows[0][0] == "card-shadow-followup"
    assert rows[0][1] == "shadow-followup"
    assert rows[0][2] == "needs_human_review"
    assert rows[0][3] == "P1"
    assert rows[0][4] == "crm_followup"
    assert rows[0][5] == "sahira"
    assert rows[0][6] == "2026-06:42"
    assert rows[0][7] == "case_stall_followup_risk"
    assert rows[0][8] == 1
    assert {row[9] for row in rows} == {0}
    assert {row[10] for row in rows} == {0}
    assert {row[11] for row in rows} == {1}
    payload = json.loads(rows[0][12])
    assert payload["raw_text_included"] is False
    assert payload["depth_layer_count"] == 5
    assert payload["send_whatsapp"] is False
    assert payload["crm_mutation"] is False
    assert rows[1][2] == "monitor_and_prepare"
    assert rows[1][4] == "payment_reconcile"
    assert rows[1][6] == "2026-04:15"

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Case Memory Cards Summary" in summary
    assert "| Case memory cards | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "shadow-followup" not in summary
    assert "wa-file-alpha" not in summary
    assert "cw-followup" not in summary


def test_build_case_memory_cards_rejects_unexpected_input_name(tmp_path: Path) -> None:
    unexpected_db = tmp_path / "client_captain_academy.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Client Shadow DB"):
        build_case_memory_cards(
            client_shadow_db=unexpected_db,
            output_dir=tmp_path / "case-memory-cards",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_raw_details(tmp_path: Path) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    output_dir = tmp_path / "case-memory-cards"
    summary_path = output_dir / "case_memory_cards_summary.md"
    _write_client_shadow_db(client_shadow_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(client_shadow_db),
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
    assert payload["card_count"] == 2
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "shadow-followup" not in result.stdout
    assert "wa-file-alpha" not in result.stdout
