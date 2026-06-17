from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus import build_team_captain_shadow as team_shadow_module
from scripts.whatsapp_corpus.build_team_captain_shadow import (
    OperatorReviewConsoleRow,
    build_operator_coaching_cards,
    build_team_captain_shadow,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_team_captain_shadow.py"
GENERIC_TEAM_CLI_ERROR = "ERROR: Team Captain input is missing or invalid.\n"
SYSTEM_TEAM_CLI_ERROR = "ERROR: Team Captain shadow run failed safely.\n"


def _assert_no_raw_team_markers(
    text: str,
    *,
    client_shadow_db: Path,
    output_dir: Path,
    summary_path: Path,
) -> None:
    forbidden_markers = [
        "wa-file-1",
        "cw-1",
        "shadow-1",
        "operator-packet-deferred",
        "case-deferred",
        "work-deferred",
        "client_captain_shadow.local.sqlite",
        "team_captain_shadow.local.sqlite",
        str(client_shadow_db),
        str(output_dir),
        str(summary_path),
        "research/personal/wa-corpus",
    ]
    for marker in forbidden_markers:
        assert marker not in text


def _assert_sanitized_team_cli_error(
    result: subprocess.CompletedProcess[str],
    *,
    forbidden_markers: list[str],
    expected_stderr: str = GENERIC_TEAM_CLI_ERROR,
) -> None:
    assert result.returncode == 1
    assert result.stderr == expected_stderr
    assert result.stdout == ""
    for marker in forbidden_markers:
        assert marker not in result.stderr


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
                send_whatsapp INTEGER NOT NULL,
                crm_mutation INTEGER NOT NULL,
                requires_human_approval INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO shadow_runs VALUES (
                1, '2026-06-16T00:00:00+00:00',
                'local_only_shadow_drafts_no_send_no_crm_mutation', 3, 0, 0
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
                    "shadow-1",
                    "ex-1",
                    "replay-1",
                    "cw-1",
                    "wa-file-1",
                    "zantara_client_captain",
                    "shadow_draft",
                    "high",
                    "P1",
                    "crm_followup",
                    "sahira",
                    "case_stall_followup_risk",
                    "Draft follow-up.",
                    "firm_accountability_nudge",
                    "Firm: operator must make a system update.",
                    "2026-05",
                    "2026-05",
                    1,
                    10,
                    5,
                    "followup_risk",
                    20,
                    7,
                    2,
                    3,
                    0,
                    0,
                    1,
                ),
                (
                    "shadow-2",
                    "ex-2",
                    "replay-2",
                    "cw-2",
                    "wa-file-2",
                    "zantara_client_captain",
                    "shadow_draft",
                    "normal",
                    "P2",
                    "payment_reconcile",
                    "surya",
                    "payment_reconciliation_needed",
                    "Draft payment status.",
                    "steady_family_motivation",
                    "Supportive: keep moving.",
                    "2026-05",
                    "2026-05",
                    11,
                    18,
                    14,
                    "tax_payment",
                    9,
                    4,
                    1,
                    0,
                    0,
                    0,
                    1,
                ),
                (
                    "shadow-3",
                    "ex-3",
                    "replay-3",
                    "cw-3",
                    "wa-file-3",
                    "zantara_client_captain",
                    "shadow_draft",
                    "high",
                    "P1",
                    "document_chase",
                    "sahira",
                    "missing_document_chase_needed",
                    "Draft document chase.",
                    "supportive_urgent_nudge",
                    "Urgent: close the loop.",
                    "2026-05",
                    "2026-05",
                    20,
                    40,
                    30,
                    "document_requirement",
                    12,
                    5,
                    2,
                    1,
                    0,
                    0,
                    1,
                ),
            ],
        )
        conn.commit()


def _write_operator_review_console_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_packet_review_items (
                packet_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                work_order_id TEXT NOT NULL,
                review_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                review_priority TEXT NOT NULL,
                operator_action TEXT NOT NULL,
                console_instruction TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO operator_packet_review_items VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1
            )
            """,
            [
                (
                    "operator-packet-ready",
                    "case-ready",
                    "work-ready",
                    1,
                    "sahira",
                    "sahira",
                    "ready_for_human_review",
                    "operator_review_queue",
                    "operator_now",
                    "review_packet_before_send_or_crm",
                    "review_ready_packet_and_request_human_approval",
                ),
                (
                    "operator-packet-mismatch",
                    "case-mismatch",
                    "work-mismatch",
                    2,
                    "surya",
                    "ari",
                    "ready_for_human_review",
                    "operator_review_queue",
                    "operator_now",
                    "review_packet_before_send_or_crm",
                    "review_ready_packet_and_request_human_approval",
                ),
                (
                    "operator-packet-owner",
                    "case-owner",
                    "work-owner",
                    3,
                    "sahira",
                    "owner",
                    "waiting_owner_decision",
                    "owner_decision_inbox",
                    "owner_now",
                    "no_operator_action",
                    "owner_must_approve_reject_or_defer_before_team_work",
                ),
                (
                    "operator-packet-rejected",
                    "case-rejected",
                    "work-rejected",
                    4,
                    "ari",
                    "owner",
                    "rejected_closed",
                    "closed_no_action",
                    "closed",
                    "no_operator_action",
                    "no_action_packet_rejected",
                ),
            ],
        )
        conn.commit()


def _write_minimal_operator_review_console_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_packet_review_items (
                packet_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                work_order_id TEXT NOT NULL,
                review_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                review_priority TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO operator_packet_review_items VALUES (
                'operator-packet-deferred', 'case-deferred', 'work-deferred',
                1, 'sahira', 'owner', 'deferred_owner_revisit',
                'owner_revisit_queue', 'owner_later', 0, 0, 1
            )
            """
        )
        conn.commit()


def test_build_team_captain_shadow_groups_lanes_with_six_depth_layers(
    tmp_path: Path,
) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    output_dir = tmp_path / "team-captain-shadow"
    summary_path = output_dir / "team_captain_shadow_summary.md"
    _write_client_shadow_db(client_shadow_db)

    result = build_team_captain_shadow(
        client_shadow_db=client_shadow_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.finding_count == 2
    assert result.depth_layer_count == 12
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0

    with sqlite3.connect(result.output_db) as conn:
        findings = conn.execute(
            """
            SELECT team_captain_id, team_owner, human_specialist, draft_count,
                   p1_count, primary_action_type, accountability_mode,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM team_captain_findings
            ORDER BY human_specialist
            """
        ).fetchall()
        layers = conn.execute(
            """
            SELECT team_captain_id, depth_level, layer_code, layer_payload_json
            FROM team_captain_depth_layers
            ORDER BY team_captain_id, depth_level
            """
        ).fetchall()

    assert findings[0][2] == "sahira"
    assert findings[0][3] == 2
    assert findings[0][4] == 2
    assert findings[0][6] == "firm_family_accountability"
    assert {row[7] for row in findings} == {0}
    assert {row[8] for row in findings} == {0}
    assert {row[9] for row in findings} == {1}
    assert [row[1] for row in layers[:6]] == [1, 2, 3, 4, 5, 6]
    assert json.loads(layers[0][3])["raw_text_included"] is False

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Team Captain Shadow Summary" in summary
    assert "| Team findings | 2 |" in summary
    assert "| Depth layers | 12 |" in summary
    assert "wa-file-1" not in summary
    assert "cw-1" not in summary


def test_client_shadow_contract_violation_is_aggregated_without_actions(
    tmp_path: Path,
) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    output_dir = tmp_path / "team-captain-shadow"
    summary_path = output_dir / "team_captain_shadow_summary.md"
    _write_client_shadow_db(client_shadow_db)
    with sqlite3.connect(client_shadow_db) as conn:
        conn.execute(
            """
            UPDATE shadow_drafts
            SET send_whatsapp = 1, requires_human_approval = 0
            WHERE shadow_id = 'shadow-1'
            """
        )
        conn.commit()

    result = build_team_captain_shadow(
        client_shadow_db=client_shadow_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.input_contract_violation_count == 1
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT human_specialist, input_contract_violation_count,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM team_captain_findings
            ORDER BY human_specialist
            """
        ).fetchall()

    assert rows == [
        ("sahira", 1, 0, 0, 1),
        ("surya", 0, 0, 0, 1),
    ]

    summary = summary_path.read_text(encoding="utf-8")
    assert "| Input contract violations | 1 |" in summary
    assert "shadow-1" not in summary


def test_build_team_captain_shadow_adds_operator_coaching_cards(
    tmp_path: Path,
) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    operator_review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "team-captain-shadow"
    summary_path = output_dir / "team_captain_shadow_summary.md"
    _write_client_shadow_db(client_shadow_db)
    _write_operator_review_console_db(operator_review_db)

    result = build_team_captain_shadow(
        client_shadow_db=client_shadow_db,
        operator_review_console_db=operator_review_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.operator_coaching_card_count == 4

    with sqlite3.connect(result.output_db) as conn:
        run = conn.execute(
            """
            SELECT operator_coaching_card_count, send_whatsapp_count, crm_mutation_count
            FROM team_runs
            WHERE id = 1
            """
        ).fetchone()
        rows = conn.execute(
            """
            SELECT assigned_lane, operator_lane, review_state, team_signal,
                   captain_tone, operator_push, system_discipline,
                   send_whatsapp, crm_mutation, requires_human_approval,
                   coaching_payload_json
            FROM team_operator_coaching_cards
            ORDER BY assigned_lane, operator_lane, review_state
            """
        ).fetchall()

    assert run == (4, 0, 0)
    assert len(rows) == 4
    cards = {
        (row[0], row[1], row[2]): {
            "team_signal": row[3],
            "captain_tone": row[4],
            "operator_push": row[5],
            "system_discipline": row[6],
            "send_whatsapp": row[7],
            "crm_mutation": row[8],
            "requires_human_approval": row[9],
            "payload": json.loads(row[10]),
        }
        for row in rows
    }
    assert cards[("sahira", "sahira", "ready_for_human_review")] == {
        "team_signal": "operator_action_required",
        "captain_tone": "warm_family_push",
        "operator_push": "review_ready_packet_now",
        "system_discipline": "use_review_console_before_any_send_or_crm",
        "send_whatsapp": 0,
        "crm_mutation": 0,
        "requires_human_approval": 1,
        "payload": {
            "assigned_lane": "sahira",
            "captain_tone": "warm_family_push",
            "console_bucket": "operator_review_queue",
            "crm_mutation": False,
            "input_contract_violation": False,
            "operator_lane": "sahira",
            "operator_push": "review_ready_packet_now",
            "raw_text_included": False,
            "requires_human_approval": True,
            "review_state": "ready_for_human_review",
            "send_whatsapp": False,
            "system_discipline": "use_review_console_before_any_send_or_crm",
            "team_signal": "operator_action_required",
        },
    }
    assert cards[("surya", "ari", "ready_for_human_review")]["team_signal"] == (
        "routing_mismatch"
    )
    assert cards[("surya", "ari", "ready_for_human_review")]["captain_tone"] == (
        "firm_system_correction"
    )
    assert cards[("sahira", "owner", "waiting_owner_decision")]["operator_push"] == (
        "do_not_execute_until_owner_decides"
    )
    assert cards[("ari", "owner", "rejected_closed")]["team_signal"] == "closed_no_action"

    db_surface = "\n".join(str(tuple(row)) for row in rows)
    assert "review_packet_before_send_or_crm" not in db_surface
    assert "review_ready_packet_and_request_human_approval" not in db_surface
    assert "owner_must_approve_reject_or_defer_before_team_work" not in db_surface

    summary = summary_path.read_text(encoding="utf-8")
    assert "| Operator coaching cards | 4 |" in summary
    assert "firm_system_correction" in summary
    assert "operator-packet-ready" not in summary
    assert "case-ready" not in summary
    assert "work-ready" not in summary
    assert "review_packet_before_send_or_crm" not in summary
    assert "review_ready_packet_and_request_human_approval" not in summary
    assert "owner_must_approve_reject_or_defer_before_team_work" not in summary


def test_team_captain_reads_operator_console_without_free_text_columns(
    tmp_path: Path,
) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    operator_review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "team-captain-shadow"
    summary_path = output_dir / "team_captain_shadow_summary.md"
    _write_client_shadow_db(client_shadow_db)
    _write_minimal_operator_review_console_db(operator_review_db)

    result = build_team_captain_shadow(
        client_shadow_db=client_shadow_db,
        operator_review_console_db=operator_review_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.operator_coaching_card_count == 1

    with sqlite3.connect(result.output_db) as conn:
        row = conn.execute(
            """
            SELECT review_state, team_signal, captain_tone, operator_push,
                   system_discipline, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM team_operator_coaching_cards
            """
        ).fetchone()

    assert row == (
        "deferred_owner_revisit",
        "owner_revisit_required",
        "steady_owner_followup",
        "support_owner_revisit_without_client_action",
        "hold_deferred_case_until_owner_revisits",
        0,
        0,
        1,
    )

    summary = summary_path.read_text(encoding="utf-8")
    assert "operator-packet-deferred" not in summary
    assert "case-deferred" not in summary
    assert "work-deferred" not in summary


def test_runtime_contract_violation_becomes_safe_team_correction() -> None:
    cards = build_operator_coaching_cards(
        (
            OperatorReviewConsoleRow(
                assigned_lane="sahira",
                operator_lane="sahira",
                review_state="ready_for_human_review",
                console_bucket="operator_review_queue",
                review_priority="operator_now",
                send_whatsapp=True,
                crm_mutation=False,
                requires_human_approval=True,
            ),
        )
    )

    assert len(cards) == 1
    card = cards[0]
    assert card.team_signal == "runtime_contract_violation"
    assert card.captain_tone == "firm_system_correction"
    assert card.operator_push == "stop_and_restore_human_approval_gate"
    assert card.system_discipline == "no_send_no_crm_requires_human_approval"
    assert card.send_whatsapp is False
    assert card.crm_mutation is False
    assert card.requires_human_approval is True
    assert card.coaching_payload["input_contract_violation"] is True


def test_unknown_operator_review_state_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported operator review state"):
        build_operator_coaching_cards(
            (
                OperatorReviewConsoleRow(
                    assigned_lane="sahira",
                    operator_lane="sahira",
                    review_state="unexpected_future_state",
                    console_bucket="operator_review_queue",
                    review_priority="operator_now",
                    send_whatsapp=False,
                    crm_mutation=False,
                    requires_human_approval=True,
                ),
            )
        )


def test_build_team_captain_shadow_rejects_unexpected_input_name(tmp_path: Path) -> None:
    unexpected_db = tmp_path / "client_captain_academy.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Client Shadow DB"):
        build_team_captain_shadow(
            client_shadow_db=unexpected_db,
            output_dir=tmp_path / "team-captain-shadow",
            summary_path=tmp_path / "summary.md",
        )


def test_team_cli_wrong_input_name_error_is_generic(tmp_path: Path) -> None:
    unexpected_db = tmp_path / "client_captain_academy.local.sqlite"
    unexpected_db.write_bytes(b"")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(unexpected_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_team_cli_error(
        result,
        forbidden_markers=[
            "client_captain_academy.local.sqlite",
            str(unexpected_db),
            str(tmp_path),
            "Refusing to read unexpected Client Shadow DB",
            "Traceback",
        ],
    )
    assert result.returncode == 1


def test_team_cli_missing_input_error_is_generic(tmp_path: Path) -> None:
    missing_db = tmp_path / "client_captain_shadow.local.sqlite"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(missing_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_team_cli_error(
        result,
        forbidden_markers=[
            "client_captain_shadow.local.sqlite",
            str(missing_db),
            str(tmp_path),
            "Client Shadow DB not found",
            "Traceback",
        ],
    )
    assert result.returncode == 1


def test_team_cli_sqlite_error_is_generic_system_failure(tmp_path: Path) -> None:
    malformed_db = tmp_path / "client_captain_shadow.local.sqlite"
    malformed_db.write_bytes(b"")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(malformed_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_team_cli_error(
        result,
        expected_stderr=SYSTEM_TEAM_CLI_ERROR,
        forbidden_markers=[
            "client_captain_shadow.local.sqlite",
            str(malformed_db),
            str(tmp_path),
            "no such table",
            "sqlite",
            "Traceback",
        ],
    )
    assert result.returncode == 1


def test_team_main_unexpected_error_is_generic_system_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_unexpected(**_: object) -> None:
        raise RuntimeError(
            "secret /tmp/raw team_captain_shadow.local.sqlite team_captain_findings"
        )

    monkeypatch.setattr(
        team_shadow_module,
        "build_team_captain_shadow",
        raise_unexpected,
    )

    assert team_shadow_module.main(["--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == SYSTEM_TEAM_CLI_ERROR
    for marker in [
        "secret",
        "/tmp/raw",
        "team_captain_shadow.local.sqlite",
        "team_captain_findings",
        "RuntimeError",
        "Traceback",
    ]:
        assert marker not in captured.err


def test_team_cli_writes_json_without_raw_details(tmp_path: Path) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    output_dir = tmp_path / "team-captain-shadow"
    summary_path = output_dir / "team_captain_shadow_summary.md"
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
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["finding_count"] == 2
    assert payload["depth_layer_count"] == 12
    assert payload["input_contract_violation_count"] == 0
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "output_db" not in payload
    assert "summary_path" not in payload
    _assert_no_raw_team_markers(
        result.stdout,
        client_shadow_db=client_shadow_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )


def test_team_cli_writes_json_with_operator_console_without_raw_details(
    tmp_path: Path,
) -> None:
    client_shadow_db = tmp_path / "client_captain_shadow.local.sqlite"
    operator_review_db = tmp_path / "operator_packet_review_console.local.sqlite"
    output_dir = tmp_path / "team-captain-shadow"
    summary_path = output_dir / "team_captain_shadow_summary.md"
    _write_client_shadow_db(client_shadow_db)
    _write_minimal_operator_review_console_db(operator_review_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(client_shadow_db),
            "--operator-review-console-db",
            str(operator_review_db),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["finding_count"] == 2
    assert payload["depth_layer_count"] == 12
    assert payload["operator_coaching_card_count"] == 1
    assert payload["input_contract_violation_count"] == 0
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "operator-packet-deferred" not in result.stdout
    assert "case-deferred" not in result.stdout
    assert "work-deferred" not in result.stdout
