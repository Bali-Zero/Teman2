from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus import build_client_captain_shadow as client_shadow_module
from scripts.whatsapp_corpus.build_client_captain_shadow import (
    build_client_captain_shadow,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_client_captain_shadow.py"
GENERIC_CLIENT_CLI_ERROR = "ERROR: Client Captain input is missing or invalid.\n"
SYSTEM_CLIENT_CLI_ERROR = "ERROR: Client Captain shadow run failed safely.\n"


def _assert_no_raw_client_markers(
    text: str, *, academy_db: Path, output_dir: Path, summary_path: Path
) -> None:
    forbidden_markers = [
        "wa-file-alpha",
        "cw-followup",
        "replay-followup",
        "client_captain_academy.local.sqlite",
        "client_captain_shadow.local.sqlite",
        str(academy_db),
        str(output_dir),
        str(summary_path),
        "research/personal/wa-corpus",
    ]
    for marker in forbidden_markers:
        assert marker not in text


def _assert_sanitized_client_cli_error(
    result: subprocess.CompletedProcess[str],
    *,
    forbidden_markers: list[str],
    expected_stderr: str = GENERIC_CLIENT_CLI_ERROR,
) -> None:
    assert result.returncode == 1
    assert result.stderr == expected_stderr
    assert result.stdout == ""
    for marker in forbidden_markers:
        assert marker not in result.stderr


def _write_academy_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE academy_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                example_count INTEGER NOT NULL,
                replay_count INTEGER NOT NULL
            );
            CREATE TABLE captain_training_examples (
                example_id TEXT PRIMARY KEY,
                source_window_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                case_owner TEXT NOT NULL,
                dominant_domain TEXT NOT NULL,
                priority TEXT NOT NULL,
                next_action TEXT NOT NULL,
                human_specialist TEXT NOT NULL,
                operator_coaching_mode TEXT NOT NULL,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL,
                first_message_index INTEGER NOT NULL,
                last_message_index INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL,
                severity_high_count INTEGER NOT NULL,
                captain_input_json TEXT NOT NULL,
                captain_output_json TEXT NOT NULL
            );
            CREATE TABLE captain_replay_scenarios (
                replay_id TEXT PRIMARY KEY,
                example_id TEXT NOT NULL,
                cut_message_index INTEGER NOT NULL,
                expected_next_action TEXT NOT NULL,
                expected_priority TEXT NOT NULL,
                expected_human_specialist TEXT NOT NULL,
                expected_case_owner TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO academy_runs (
                id, generated_at_utc, privacy_mode, example_count, replay_count
            )
            VALUES (1, '2026-06-16T00:00:00+00:00',
                    'local_only_case_windows_no_raw_text_no_raw_paths', 2, 2)
            """
        )
        conn.executemany(
            """
            INSERT INTO captain_training_examples (
                example_id, source_window_id, file_id, case_owner, dominant_domain,
                priority, next_action, human_specialist, operator_coaching_mode,
                first_month, last_month, first_message_index, last_message_index,
                event_count, message_count, domain_count, severity_high_count,
                captain_input_json, captain_output_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "cca-window-followup",
                    "cw-followup",
                    "wa-file-alpha",
                    "zantara_client_captain",
                    "followup_risk",
                    "high",
                    "crm_followup",
                    "sahira",
                    "firm_accountability_nudge",
                    "2026-05",
                    "2026-05",
                    10,
                    42,
                    21,
                    9,
                    2,
                    3,
                    json.dumps({"privacy_mode": "local_only_aggregate_no_raw_text"}),
                    json.dumps({"send_whatsapp": False, "crm_mutation": False}),
                ),
                (
                    "cca-window-tax",
                    "cw-tax",
                    "wa-file-beta",
                    "zantara_client_captain",
                    "tax_payment",
                    "normal",
                    "payment_reconcile",
                    "surya",
                    "steady_family_motivation",
                    "2026-05",
                    "2026-05",
                    3,
                    15,
                    8,
                    4,
                    1,
                    0,
                    json.dumps({"privacy_mode": "local_only_aggregate_no_raw_text"}),
                    json.dumps({"send_whatsapp": False, "crm_mutation": False}),
                ),
            ],
        )
        conn.executemany(
            """
            INSERT INTO captain_replay_scenarios (
                replay_id, example_id, cut_message_index, expected_next_action,
                expected_priority, expected_human_specialist, expected_case_owner
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "replay-followup",
                    "cca-window-followup",
                    26,
                    "crm_followup",
                    "high",
                    "sahira",
                    "zantara_client_captain",
                ),
                (
                    "replay-tax",
                    "cca-window-tax",
                    9,
                    "payment_reconcile",
                    "normal",
                    "surya",
                    "zantara_client_captain",
                ),
            ],
        )
        conn.commit()


def test_build_client_captain_shadow_writes_draft_only_diagnoses(
    tmp_path: Path,
) -> None:
    academy_db = tmp_path / "client_captain_academy.local.sqlite"
    output_dir = tmp_path / "client-captain-shadow"
    summary_path = output_dir / "client_captain_shadow_summary.md"
    _write_academy_db(academy_db)

    result = build_client_captain_shadow(
        academy_db=academy_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.draft_count == 2
    assert result.output_db == output_dir / "client_captain_shadow.local.sqlite"
    assert result.priority_counts == {"high": 1, "normal": 1}
    assert result.action_counts == {"crm_followup": 1, "payment_reconcile": 1}

    with sqlite3.connect(result.output_db) as conn:
        rows = conn.execute(
            """
            SELECT case_owner, status, action_type, diagnosis_code, risk_level,
                   draft_reply_intent, operator_coaching_mode, operator_nudge,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM shadow_drafts
            ORDER BY shadow_id
            """
        ).fetchall()
        depth_rows = conn.execute(
            """
            SELECT shadow_id, depth_level, layer_code, layer_title, layer_payload_json
            FROM shadow_depth_layers
            ORDER BY shadow_id, depth_level
            """
        ).fetchall()

    assert len(rows) == 2
    assert {row[0] for row in rows} == {"zantara_client_captain"}
    assert {row[1] for row in rows} == {"shadow_draft"}
    assert {row[8] for row in rows} == {0}
    assert {row[9] for row in rows} == {0}
    assert {row[10] for row in rows} == {1}
    assert rows[0][2] == "crm_followup"
    assert rows[0][3] == "case_stall_followup_risk"
    assert rows[0][4] == "P1"
    assert "system update" in rows[0][7]
    assert rows[1][2] == "payment_reconcile"
    assert rows[1][3] == "payment_reconciliation_needed"
    assert rows[1][4] == "P2"
    assert "payment status" in rows[1][5]
    assert len(depth_rows) == 10
    assert [row[1] for row in depth_rows[:5]] == [1, 2, 3, 4, 5]
    assert [row[2] for row in depth_rows[:5]] == [
        "signal_readout",
        "case_diagnosis",
        "captain_decision",
        "draft_gate",
        "operator_coaching",
    ]
    assert json.loads(depth_rows[0][4])["send_whatsapp"] is False
    assert json.loads(depth_rows[0][4])["crm_mutation"] is False

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Client Captain Shadow Mode Summary" in summary
    assert "| Shadow drafts | 2 |" in summary
    assert "| Depth layers | 10 |" in summary
    assert "wa-file-alpha" not in summary
    assert "cw-followup" not in summary
    assert "replay-followup" not in summary


def test_build_client_captain_shadow_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "allowed_messages.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Academy DB"):
        build_client_captain_shadow(
            academy_db=unexpected_db,
            output_dir=tmp_path / "client-captain-shadow",
            summary_path=tmp_path / "summary.md",
        )


def test_client_cli_wrong_input_name_error_is_generic(tmp_path: Path) -> None:
    unexpected_db = tmp_path / "allowed_messages.local.sqlite"
    unexpected_db.write_bytes(b"")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--academy-db",
            str(unexpected_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_client_cli_error(
        result,
        forbidden_markers=[
            "allowed_messages.local.sqlite",
            str(unexpected_db),
            str(tmp_path),
            "Refusing to read unexpected Academy DB",
            "Traceback",
        ],
    )


def test_client_cli_missing_input_error_is_generic(tmp_path: Path) -> None:
    missing_db = tmp_path / "client_captain_academy.local.sqlite"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--academy-db",
            str(missing_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_client_cli_error(
        result,
        forbidden_markers=[
            "client_captain_academy.local.sqlite",
            str(missing_db),
            str(tmp_path),
            "Academy DB not found",
            "Traceback",
        ],
    )


def test_client_cli_sqlite_error_is_generic_system_failure(tmp_path: Path) -> None:
    malformed_db = tmp_path / "client_captain_academy.local.sqlite"
    malformed_db.write_bytes(b"")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--academy-db",
            str(malformed_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_client_cli_error(
        result,
        expected_stderr=SYSTEM_CLIENT_CLI_ERROR,
        forbidden_markers=[
            "client_captain_academy.local.sqlite",
            str(malformed_db),
            str(tmp_path),
            "no such table",
            "sqlite",
            "Traceback",
        ],
    )


def test_client_main_unexpected_error_is_generic_system_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_unexpected(**_: object) -> None:
        raise RuntimeError(
            "secret /tmp/raw client_captain_shadow.local.sqlite shadow_drafts"
        )

    monkeypatch.setattr(
        client_shadow_module,
        "build_client_captain_shadow",
        raise_unexpected,
    )

    assert client_shadow_module.main(["--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == SYSTEM_CLIENT_CLI_ERROR
    for marker in [
        "secret",
        "/tmp/raw",
        "client_captain_shadow.local.sqlite",
        "shadow_drafts",
        "RuntimeError",
        "Traceback",
    ]:
        assert marker not in captured.err


def test_client_cli_writes_json_without_raw_details(tmp_path: Path) -> None:
    academy_db = tmp_path / "client_captain_academy.local.sqlite"
    output_dir = tmp_path / "client-captain-shadow"
    summary_path = output_dir / "client_captain_shadow_summary.md"
    _write_academy_db(academy_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--academy-db",
            str(academy_db),
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
    assert payload["draft_count"] == 2
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert "output_db" not in payload
    assert "summary_path" not in payload
    _assert_no_raw_client_markers(
        result.stdout,
        academy_db=academy_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )
