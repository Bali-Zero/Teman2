from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.whatsapp_corpus import build_owner_captain_shadow as owner_shadow_module
from scripts.whatsapp_corpus.build_owner_captain_shadow import build_owner_captain_shadow

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_captain_shadow.py"
GENERIC_OWNER_CLI_ERROR = "ERROR: Owner Captain input is missing or invalid.\n"
SYSTEM_OWNER_CLI_ERROR = "ERROR: Owner Captain shadow run failed safely.\n"


def _assert_no_raw_owner_markers(text: str, *, output_dir: Path, summary_path: Path) -> None:
    forbidden_markers = [
        "shadow-1",
        "shadow-2",
        "shadow-3",
        "team-sahira",
        "team-surya",
        "client_captain_shadow.local.sqlite",
        "team_captain_shadow.local.sqlite",
        str(output_dir),
        str(summary_path),
        "research/personal/wa-corpus",
    ]
    for marker in forbidden_markers:
        assert marker not in text


def _assert_sanitized_owner_cli_error(
    result: subprocess.CompletedProcess[str],
    *,
    forbidden_markers: list[str],
    expected_stderr: str = GENERIC_OWNER_CLI_ERROR,
) -> None:
    assert result.returncode == 1
    assert result.stderr == expected_stderr
    assert result.stdout == ""
    for marker in forbidden_markers:
        assert marker not in result.stderr


def _write_owner_inputs(client_db: Path, team_db: Path) -> None:
    with sqlite3.connect(client_db) as conn:
        conn.executescript(
            """
            CREATE TABLE shadow_drafts (
                shadow_id TEXT PRIMARY KEY,
                risk_level TEXT NOT NULL,
                action_type TEXT NOT NULL,
                human_specialist TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL,
                crm_mutation INTEGER NOT NULL,
                requires_human_approval INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO shadow_drafts VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("shadow-1", "P1", "crm_followup", "sahira", 0, 0, 1),
                ("shadow-2", "P1", "document_chase", "sahira", 0, 0, 1),
                ("shadow-3", "P2", "payment_reconcile", "surya", 0, 0, 1),
            ],
        )
        conn.commit()
    with sqlite3.connect(team_db) as conn:
        conn.executescript(
            """
            CREATE TABLE team_captain_findings (
                team_captain_id TEXT PRIMARY KEY,
                team_owner TEXT NOT NULL,
                human_specialist TEXT NOT NULL,
                draft_count INTEGER NOT NULL,
                p1_count INTEGER NOT NULL,
                p2_count INTEGER NOT NULL,
                primary_action_type TEXT NOT NULL,
                accountability_mode TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL,
                crm_mutation INTEGER NOT NULL,
                requires_human_approval INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO team_captain_findings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "team-sahira",
                    "zantara_team_captain",
                    "sahira",
                    2,
                    2,
                    0,
                    "crm_followup",
                    "firm_family_accountability",
                    0,
                    0,
                    1,
                ),
                (
                    "team-surya",
                    "zantara_team_captain",
                    "surya",
                    1,
                    0,
                    1,
                    "payment_reconcile",
                    "steady_family_motivation",
                    0,
                    0,
                    1,
                ),
            ],
        )
        conn.commit()


def test_build_owner_captain_shadow_writes_one_owner_finding_and_seven_layers(
    tmp_path: Path,
) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    output_dir = tmp_path / "owner-captain-shadow"
    summary_path = output_dir / "owner_captain_shadow_summary.md"
    _write_owner_inputs(client_db, team_db)

    result = build_owner_captain_shadow(
        client_shadow_db=client_db,
        team_shadow_db=team_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.finding_count == 1
    assert result.depth_layer_count == 7
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0

    with sqlite3.connect(result.output_db) as conn:
        finding = conn.execute(
            """
            SELECT owner_captain_id, owner_scope, draft_count, team_lane_count,
                   p1_count, primary_bottleneck_lane, owner_decision_mode,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM owner_captain_findings
            """
        ).fetchone()
        layers = conn.execute(
            """
            SELECT depth_level, layer_code, layer_payload_json
            FROM owner_captain_depth_layers
            ORDER BY depth_level
            """
        ).fetchall()

    assert finding[1] == "global_case_ops"
    assert finding[2] == 3
    assert finding[3] == 2
    assert finding[4] == 2
    assert finding[5] == "sahira"
    assert finding[6] == "owner_review_required"
    assert finding[7:] == (0, 0, 1)
    assert [row[0] for row in layers] == [1, 2, 3, 4, 5, 6, 7]
    assert layers[-1][1] == "owner_decision"
    assert json.loads(layers[-1][2])["send_whatsapp"] is False

    summary = summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Captain Shadow Summary" in summary
    assert "| Owner findings | 1 |" in summary
    assert "| Depth layers | 7 |" in summary
    assert "shadow-1" not in summary


def test_build_owner_captain_shadow_rejects_unexpected_input_names(tmp_path: Path) -> None:
    client_db = tmp_path / "client_captain_academy.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    client_db.write_bytes(b"")
    team_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read unexpected Client Shadow DB"):
        build_owner_captain_shadow(
            client_shadow_db=client_db,
            team_shadow_db=team_db,
            output_dir=tmp_path / "owner-captain-shadow",
            summary_path=tmp_path / "summary.md",
        )


def test_owner_cli_wrong_input_name_error_is_generic(tmp_path: Path) -> None:
    client_db = tmp_path / "client_captain_academy.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    client_db.write_bytes(b"")
    team_db.write_bytes(b"")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(client_db),
            "--team-shadow-db",
            str(team_db),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_owner_cli_error(
        result,
        forbidden_markers=[
            "client_captain_academy.local.sqlite",
            "team_captain_shadow.local.sqlite",
            str(client_db),
            str(team_db),
            str(tmp_path),
            "Traceback",
        ],
    )


def test_owner_cli_missing_input_error_is_generic(tmp_path: Path) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    team_db.write_bytes(b"")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(client_db),
            "--team-shadow-db",
            str(team_db),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_owner_cli_error(
        result,
        forbidden_markers=[
            "client_captain_shadow.local.sqlite",
            "team_captain_shadow.local.sqlite",
            str(client_db),
            str(team_db),
            str(tmp_path),
            "Traceback",
        ],
    )


def test_owner_cli_malformed_input_error_is_generic_system_failure(
    tmp_path: Path,
) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    client_db.write_bytes(b"not sqlite")
    team_db.write_bytes(b"")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(client_db),
            "--team-shadow-db",
            str(team_db),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_owner_cli_error(
        result,
        expected_stderr=SYSTEM_OWNER_CLI_ERROR,
        forbidden_markers=[
            "client_captain_shadow.local.sqlite",
            "team_captain_shadow.local.sqlite",
            str(client_db),
            str(team_db),
            str(tmp_path),
            "file is not a database",
            "Traceback",
        ],
    )


def test_owner_main_unexpected_error_is_generic_system_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_unexpected(**_: object) -> None:
        raise RuntimeError(
            "secret /tmp/raw owner_captain_shadow.local.sqlite owner_captain_findings"
        )

    monkeypatch.setattr(
        owner_shadow_module,
        "build_owner_captain_shadow",
        raise_unexpected,
    )

    assert owner_shadow_module.main(["--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == SYSTEM_OWNER_CLI_ERROR
    for marker in [
        "secret",
        "/tmp/raw",
        "owner_captain_shadow.local.sqlite",
        "owner_captain_findings",
        "RuntimeError",
        "Traceback",
    ]:
        assert marker not in captured.err


def test_owner_cli_null_numeric_input_error_is_generic(tmp_path: Path) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    valid_client_db = tmp_path / "valid_client_captain_shadow.local.sqlite"
    _write_owner_inputs(valid_client_db, team_db)
    with sqlite3.connect(client_db) as conn:
        conn.executescript(
            """
            CREATE TABLE shadow_drafts (
                shadow_id TEXT PRIMARY KEY,
                risk_level TEXT,
                action_type TEXT,
                human_specialist TEXT,
                send_whatsapp INTEGER,
                crm_mutation INTEGER,
                requires_human_approval INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO shadow_drafts VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("shadow-null", "P3", "crm_followup", "sahira", None, 0, 1),
        )
        conn.commit()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(client_db),
            "--team-shadow-db",
            str(team_db),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    _assert_sanitized_owner_cli_error(
        result,
        forbidden_markers=[
            "client_captain_shadow.local.sqlite",
            "team_captain_shadow.local.sqlite",
            str(client_db),
            str(team_db),
            str(tmp_path),
            "NoneType",
            "TypeError",
            "Traceback",
        ],
    )


def test_build_owner_captain_shadow_reports_upstream_contract_violations(
    tmp_path: Path,
) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    output_dir = tmp_path / "owner-captain-shadow"
    summary_path = output_dir / "owner_captain_shadow_summary.md"
    _write_owner_inputs(client_db, team_db)

    with sqlite3.connect(client_db) as conn:
        conn.execute(
            """
            UPDATE shadow_drafts
            SET send_whatsapp = 1, requires_human_approval = 0
            WHERE shadow_id = 'shadow-1'
            """
        )
        conn.commit()
    with sqlite3.connect(team_db) as conn:
        conn.execute(
            """
            UPDATE team_captain_findings
            SET crm_mutation = 1
            WHERE team_captain_id = 'team-surya'
            """
        )
        conn.commit()

    result = build_owner_captain_shadow(
        client_shadow_db=client_db,
        team_shadow_db=team_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    assert result.input_contract_violation_count == 2
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0

    with sqlite3.connect(result.output_db) as conn:
        run_count = conn.execute(
            """
            SELECT input_contract_violation_count, send_whatsapp_count,
                   crm_mutation_count
            FROM owner_runs
            WHERE id = 1
            """
        ).fetchone()
        finding_count = conn.execute(
            """
            SELECT input_contract_violation_count, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM owner_captain_findings
            """
        ).fetchone()
    assert run_count == (2, 0, 0)
    assert finding_count == (2, 0, 0, 1)

    summary = summary_path.read_text(encoding="utf-8")
    assert "| Input contract violations | 2 |" in summary
    _assert_no_raw_owner_markers(summary, output_dir=output_dir, summary_path=summary_path)


def test_contract_violations_alone_force_owner_review(
    tmp_path: Path,
) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    output_dir = tmp_path / "owner-captain-shadow"
    summary_path = output_dir / "owner_captain_shadow_summary.md"
    _write_owner_inputs(client_db, team_db)

    with sqlite3.connect(client_db) as conn:
        conn.execute("UPDATE shadow_drafts SET risk_level = 'P3'")
        conn.execute(
            """
            UPDATE shadow_drafts
            SET crm_mutation = 1
            WHERE shadow_id = 'shadow-3'
            """
        )
        conn.commit()
    with sqlite3.connect(team_db) as conn:
        conn.execute("UPDATE team_captain_findings SET p1_count = 0")
        conn.commit()

    result = build_owner_captain_shadow(
        client_shadow_db=client_db,
        team_shadow_db=team_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    with sqlite3.connect(result.output_db) as conn:
        finding = conn.execute(
            """
            SELECT p1_count, owner_decision_mode, input_contract_violation_count,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM owner_captain_findings
            """
        ).fetchone()

    assert finding == (0, "owner_review_required", 1, 0, 0, 1)
    summary = summary_path.read_text(encoding="utf-8")
    assert "| P1 count | 0 |" in summary
    assert "| Input contract violations | 1 |" in summary
    _assert_no_raw_owner_markers(summary, output_dir=output_dir, summary_path=summary_path)


def test_owner_captain_uses_team_p2_as_risk_fallback(
    tmp_path: Path,
) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    output_dir = tmp_path / "owner-captain-shadow"
    summary_path = output_dir / "owner_captain_shadow_summary.md"
    _write_owner_inputs(client_db, team_db)

    with sqlite3.connect(client_db) as conn:
        conn.execute("UPDATE shadow_drafts SET risk_level = 'P3'")
        conn.commit()
    with sqlite3.connect(team_db) as conn:
        conn.execute("UPDATE team_captain_findings SET p1_count = 0")
        conn.execute("UPDATE team_captain_findings SET p2_count = 0")
        conn.execute(
            """
            UPDATE team_captain_findings
            SET p2_count = 3
            WHERE team_captain_id = 'team-surya'
            """
        )
        conn.commit()

    result = build_owner_captain_shadow(
        client_shadow_db=client_db,
        team_shadow_db=team_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    with sqlite3.connect(result.output_db) as conn:
        finding = conn.execute(
            """
            SELECT p1_count, p2_count, owner_decision_mode
            FROM owner_captain_findings
            """
        ).fetchone()

    assert finding == (0, 3, "monitor")
    summary = summary_path.read_text(encoding="utf-8")
    assert "| P1 count | 0 |" in summary
    assert "| P2 count | 3 |" in summary


def test_build_owner_captain_shadow_uses_team_p1_as_review_fallback(
    tmp_path: Path,
) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    output_dir = tmp_path / "owner-captain-shadow"
    summary_path = output_dir / "owner_captain_shadow_summary.md"
    _write_owner_inputs(client_db, team_db)

    with sqlite3.connect(client_db) as conn:
        conn.execute("UPDATE shadow_drafts SET risk_level = 'P3'")
        conn.commit()
    with sqlite3.connect(team_db) as conn:
        conn.execute("UPDATE team_captain_findings SET p1_count = 0")
        conn.execute(
            """
            UPDATE team_captain_findings
            SET p1_count = 1
            WHERE team_captain_id = 'team-surya'
            """
        )
        conn.commit()

    result = build_owner_captain_shadow(
        client_shadow_db=client_db,
        team_shadow_db=team_db,
        output_dir=output_dir,
        summary_path=summary_path,
    )

    with sqlite3.connect(result.output_db) as conn:
        finding = conn.execute(
            """
            SELECT p1_count, owner_decision_mode, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM owner_captain_findings
            """
        ).fetchone()

    assert finding == (1, "owner_review_required", 0, 0, 1)
    assert "| P1 count | 1 |" in summary_path.read_text(encoding="utf-8")


def test_owner_cli_writes_json_without_raw_details(tmp_path: Path) -> None:
    client_db = tmp_path / "client_captain_shadow.local.sqlite"
    team_db = tmp_path / "team_captain_shadow.local.sqlite"
    output_dir = tmp_path / "owner-captain-shadow"
    summary_path = output_dir / "owner_captain_shadow_summary.md"
    _write_owner_inputs(client_db, team_db)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--client-shadow-db",
            str(client_db),
            "--team-shadow-db",
            str(team_db),
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
    assert payload["finding_count"] == 1
    assert payload["depth_layer_count"] == 7
    assert payload["send_whatsapp_count"] == 0
    assert payload["crm_mutation_count"] == 0
    assert payload["input_contract_violation_count"] == 0
    assert "output_db" not in payload
    assert "summary_path" not in payload
    _assert_no_raw_owner_markers(result.stdout, output_dir=output_dir, summary_path=summary_path)
