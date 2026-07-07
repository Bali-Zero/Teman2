from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "whatsapp_corpus"
DECISION_CHAIN_SCRIPT_NAMES = [
    "build_approval_routing_queue.py",
    "build_approve_reject_ledger.py",
    "build_owner_approval_console.py",
    "build_owner_brief_renderer.py",
    "build_owner_decision_intake.py",
    "build_owner_decision_inbox.py",
    "build_owner_decision_event_capture.py",
    "build_owner_decision_packs.py",
    "build_owner_decision_compiler.py",
    "build_owner_decision_cockpit.py",
    "build_owner_decision_pipeline.py",
    "build_owner_decision_replay.py",
    "build_post_decision_work_order_queue.py",
    "build_operator_action_inbox.py",
    "build_operator_execution_packets.py",
    "build_operator_packet_review_console.py",
    "build_operator_sla_clock.py",
]
PATH_HARDENED_SCRIPT_NAMES = [
    *DECISION_CHAIN_SCRIPT_NAMES,
    "build_client_captain_academy.py",
    "build_drive_export_manifest.py",
    "import_drive_exports.py",
]


@pytest.mark.parametrize(
    ("script_name", "input_arg", "error_stderr"),
    [
        (
            "build_approval_routing_queue.py",
            "--owner-briefs-db",
            "ERROR: Approval routing queue input is missing or invalid.\n",
        ),
        (
            "build_approve_reject_ledger.py",
            "--approval-routing-db",
            "ERROR: Approve/reject ledger input is missing or invalid.\n",
        ),
        (
            "build_owner_approval_console.py",
            "--case-closure-db",
            "ERROR: Owner approval console input is missing or invalid.\n",
        ),
        (
            "build_owner_brief_renderer.py",
            "--owner-packs-db",
            "ERROR: Owner brief renderer input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_intake.py",
            "--review-console-db",
            "ERROR: Owner decision intake input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_inbox.py",
            "--review-console-db",
            "ERROR: Owner decision inbox input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_event_capture.py",
            "--ledger-db",
            "ERROR: Owner decision event capture input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_packs.py",
            "--owner-approval-db",
            "ERROR: Owner decision packs input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_compiler.py",
            "--owner-inbox-db",
            "ERROR: Owner decision compiler input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_cockpit.py",
            "--owner-inbox-db",
            "ERROR: Owner decision cockpit input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_pipeline.py",
            "--ledger-db",
            "ERROR: Owner decision pipeline input is missing or invalid.\n",
        ),
        (
            "build_owner_decision_replay.py",
            "--ledger-db",
            "ERROR: Owner decision replay input is missing or invalid.\n",
        ),
        (
            "build_post_decision_work_order_queue.py",
            "--owner-events-db",
            "ERROR: Post-decision work order queue input is missing or invalid.\n",
        ),
        (
            "build_operator_action_inbox.py",
            "--next-best-actions-db",
            "ERROR: Operator action inbox input is missing or invalid.\n",
        ),
        (
            "build_operator_execution_packets.py",
            "--work-orders-db",
            "ERROR: Operator execution packets input is missing or invalid.\n",
        ),
        (
            "build_operator_packet_review_console.py",
            "--packets-db",
            "ERROR: Operator packet review console input is missing or invalid.\n",
        ),
        (
            "build_operator_sla_clock.py",
            "--operator-inbox-db",
            "ERROR: Operator SLA clock input is missing or invalid.\n",
        ),
    ],
)
def test_decision_chain_cli_wrong_input_name_is_sanitized(
    tmp_path: Path,
    script_name: str,
    input_arg: str,
    error_stderr: str,
) -> None:
    wrong_db = tmp_path / "wrong_input_should_not_leak.local.sqlite"
    wrong_db.write_bytes(b"")
    output_dir = tmp_path / "output"
    summary_path = output_dir / "summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / script_name),
            input_arg,
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
    assert result.stderr == error_stderr
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


@pytest.mark.parametrize("script_name", PATH_HARDENED_SCRIPT_NAMES)
def test_decision_chain_cli_json_payload_has_no_local_path_fields(
    script_name: str,
) -> None:
    source = (SCRIPT_DIR / script_name).read_text(encoding="utf-8")

    forbidden_fields = [
        '"output_db":',
        '"output_jsonl":',
        '"output_template":',
        '"summary_path":',
    ]
    for field in forbidden_fields:
        assert field not in source


@pytest.mark.parametrize("script_name", PATH_HARDENED_SCRIPT_NAMES)
def test_decision_chain_cli_plaintext_success_uses_basename_only(
    script_name: str,
) -> None:
    source = (SCRIPT_DIR / script_name).read_text(encoding="utf-8")

    forbidden_interpolations = [
        "{result.output_db}",
        "{result.output_jsonl}",
        "{result.output_template}",
        "{result.summary_path}",
    ]
    for interpolation in forbidden_interpolations:
        assert interpolation not in source
