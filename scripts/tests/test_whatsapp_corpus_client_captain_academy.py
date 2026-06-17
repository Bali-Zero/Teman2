from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.build_client_captain_academy import (
    build_client_captain_academy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_client_captain_academy.py"


def _write_case_windows_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE case_windows (
                window_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                window_ordinal INTEGER NOT NULL,
                first_timestamp TEXT,
                last_timestamp TEXT,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL,
                first_message_index INTEGER NOT NULL,
                last_message_index INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL,
                dominant_domain TEXT NOT NULL,
                severity_high_count INTEGER NOT NULL,
                top_event_codes_json TEXT NOT NULL
            );
            CREATE TABLE case_window_domains (
                window_id TEXT NOT NULL,
                domain_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                PRIMARY KEY (window_id, domain_code)
            );
            CREATE TABLE case_window_event_codes (
                window_id TEXT NOT NULL,
                rank INTEGER NOT NULL,
                domain_code TEXT NOT NULL,
                event_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                PRIMARY KEY (window_id, rank)
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO case_windows (
                window_id, file_id, window_ordinal, first_timestamp, last_timestamp,
                first_month, last_month, first_message_index, last_message_index,
                event_count, message_count, domain_count, dominant_domain,
                severity_high_count, top_event_codes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "cw-001",
                    "wa-file-alpha",
                    1,
                    "2026-05-01T08:00:00",
                    "2026-05-01T13:00:00",
                    "2026-05",
                    "2026-05",
                    10,
                    42,
                    61,
                    18,
                    3,
                    "immigration_lifecycle",
                    4,
                    json.dumps(
                        [
                            {
                                "domain_code": "immigration_lifecycle",
                                "event_code": "visa_stage",
                                "event_count": 9,
                            },
                            {
                                "domain_code": "document_requirement",
                                "event_code": "passport_identity_document",
                                "event_count": 5,
                            },
                        ]
                    ),
                ),
                (
                    "cw-002",
                    "wa-file-beta",
                    1,
                    "2026-05-02T08:00:00",
                    "2026-05-04T09:00:00",
                    "2026-05",
                    "2026-05",
                    3,
                    15,
                    18,
                    8,
                    2,
                    "tax_payment",
                    0,
                    json.dumps(
                        [
                            {
                                "domain_code": "tax_payment",
                                "event_code": "payment_or_transfer",
                                "event_count": 4,
                            }
                        ]
                    ),
                ),
            ],
        )
        conn.executemany(
            """
            INSERT INTO case_window_domains
                (window_id, domain_code, event_count, message_count)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("cw-001", "immigration_lifecycle", 40, 13),
                ("cw-001", "document_requirement", 14, 4),
                ("cw-001", "followup_risk", 7, 3),
                ("cw-002", "tax_payment", 12, 5),
                ("cw-002", "followup_risk", 6, 2),
            ],
        )
        conn.executemany(
            """
            INSERT INTO case_window_event_codes
                (window_id, rank, domain_code, event_code, event_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("cw-001", 1, "immigration_lifecycle", "visa_stage", 9),
                ("cw-001", 2, "document_requirement", "passport_identity_document", 5),
                ("cw-001", 3, "followup_risk", "deadline_or_urgency", 4),
                ("cw-002", 1, "tax_payment", "payment_or_transfer", 4),
                ("cw-002", 2, "followup_risk", "followup_waiting", 2),
            ],
        )
        conn.commit()


def test_build_client_captain_academy_writes_local_examples_and_replay(
    tmp_path: Path,
) -> None:
    case_windows_db = tmp_path / "allowed_case_windows.local.sqlite"
    output_dir = tmp_path / "client-captain"
    summary_path = output_dir / "client_captain_academy_summary.md"
    _write_case_windows_db(case_windows_db)

    result = build_client_captain_academy(
        case_windows_db=case_windows_db,
        output_dir=output_dir,
        summary_path=summary_path,
        max_examples=10,
    )

    assert result.example_count == 2
    assert result.replay_count == 2
    assert result.owner_counts == {"zantara_client_captain": 2}
    assert result.priority_counts == {"high": 1, "normal": 1}
    assert (output_dir / "client_captain_academy.local.sqlite").exists()
    assert (output_dir / "training_examples.local.jsonl").exists()

    jsonl_rows = [
        json.loads(line)
        for line in (output_dir / "training_examples.local.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert {row["case_owner"] for row in jsonl_rows} == {"zantara_client_captain"}
    assert jsonl_rows[0]["academy_task"] == "case_captain_next_action"
    assert jsonl_rows[0]["captain_output"]["next_action"] == "immigration_status_check"
    assert jsonl_rows[0]["captain_output"]["human_specialist"] == "ari"
    assert jsonl_rows[1]["captain_output"]["next_action"] == "payment_reconcile"
    assert jsonl_rows[1]["captain_output"]["human_specialist"] == "surya"

    with sqlite3.connect(output_dir / "client_captain_academy.local.sqlite") as conn:
        examples = conn.execute(
            """
            SELECT example_id, case_owner, priority, next_action, human_specialist
            FROM captain_training_examples
            ORDER BY example_id
            """
        ).fetchall()
        replay = conn.execute(
            """
            SELECT example_id, cut_message_index, expected_next_action
            FROM captain_replay_scenarios
            ORDER BY example_id
            """
        ).fetchall()

    assert examples == [
        ("cca-cw-001", "zantara_client_captain", "high", "immigration_status_check", "ari"),
        ("cca-cw-002", "zantara_client_captain", "normal", "payment_reconcile", "surya"),
    ]
    assert replay == [
        ("cca-cw-001", 26, "immigration_status_check"),
        ("cca-cw-002", 9, "payment_reconcile"),
    ]

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Client Captain Academy Summary" in summary
    assert "| Training examples | 2 |" in summary
    assert "| zantara_client_captain | 2 |" in summary
    assert "wa-file-alpha" not in summary
    assert "cw-001" not in summary
    assert "passport_identity_document" not in summary


def test_build_client_captain_academy_rejects_unexpected_input_name(
    tmp_path: Path,
) -> None:
    unexpected_db = tmp_path / "full_messages.local.sqlite"
    unexpected_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected input artifact"):
        build_client_captain_academy(
            case_windows_db=unexpected_db,
            output_dir=tmp_path / "client-captain",
            summary_path=tmp_path / "summary.md",
        )


def test_cli_writes_json_without_raw_window_details(tmp_path: Path) -> None:
    case_windows_db = tmp_path / "allowed_case_windows.local.sqlite"
    output_dir = tmp_path / "client-captain"
    summary_path = output_dir / "client_captain_academy_summary.md"
    _write_case_windows_db(case_windows_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-windows-db",
            str(case_windows_db),
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
    assert payload == {
        "example_count": 2,
        "replay_count": 2,
    }
    assert "wa-file-alpha" not in result.stdout
    assert "cw-001" not in result.stdout
    assert "passport_identity_document" not in result.stdout
    assert summary_path.exists()


def test_cli_error_is_sanitized_for_unexpected_input_name(tmp_path: Path) -> None:
    wrong_db = tmp_path / "wrong_input_should_not_leak.local.sqlite"
    wrong_db.write_bytes(b"")
    output_dir = tmp_path / "client-captain"
    summary_path = output_dir / "client_captain_academy_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-windows-db",
            str(wrong_db),
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

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "ERROR: Client Captain Academy input is missing or invalid.\n"
    forbidden_markers = [
        str(tmp_path),
        str(wrong_db),
        wrong_db.name,
        str(output_dir),
        str(summary_path),
        "Traceback",
        ".sqlite",
    ]
    for marker in forbidden_markers:
        assert marker not in result.stderr
