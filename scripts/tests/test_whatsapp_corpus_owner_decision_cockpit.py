from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.tests.test_whatsapp_corpus_owner_decision_intake import (
    _write_operator_packet_review_console_db,
)
from scripts.whatsapp_corpus.build_owner_decision_compiler import (
    build_owner_decision_compiler,
)
from scripts.whatsapp_corpus.build_owner_decision_cockpit import (
    build_owner_decision_cockpit,
)
from scripts.whatsapp_corpus.build_owner_decision_inbox import (
    build_owner_decision_inbox,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_decision_cockpit.py"


def _build_inbox_fixture(tmp_path: Path) -> tuple[Path, Path]:
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    inbox_dir = tmp_path / "owner-decision-inbox"
    _write_operator_packet_review_console_db(review_console_db)
    inbox_result = build_owner_decision_inbox(
        review_console_db=review_console_db,
        output_dir=inbox_dir,
        summary_path=inbox_dir / "owner_decision_inbox_summary.md",
        generated_at_utc="2026-06-18T00:00:00+00:00",
    )
    return inbox_result.output_db, inbox_result.output_template


def _write_owner_inputs(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_build_owner_decision_cockpit_writes_template_for_compiler(
    tmp_path: Path,
) -> None:
    inbox_db, _blank_template = _build_inbox_fixture(tmp_path)
    owner_inputs = tmp_path / "owner_inputs.local.jsonl"
    output_dir = tmp_path / "owner-decision-cockpit"
    _write_owner_inputs(
        owner_inputs,
        [
            {
                "decision_note": "owner approved recovery",
                "event_recorded_at_utc": "2026-06-18T00:01:00+00:00",
                "owner_decision": "approve",
                "review_item_id": "operator-packet-review-item-pending",
            },
            {
                "decision_note": "owner rejects escalation",
                "owner_decision": "reject",
                "review_item_id": "operator-packet-review-item-defer",
            },
        ],
    )

    result = build_owner_decision_cockpit(
        owner_inbox_db=inbox_db,
        owner_inputs_jsonl=owner_inputs,
        output_dir=output_dir,
        summary_path=output_dir / "owner_decision_cockpit_summary.md",
        generated_at_utc="2026-06-18T00:02:00+00:00",
    )

    assert result.inbox_item_count == 2
    assert result.captured_decision_count == 2
    assert result.awaiting_owner_input_count == 0
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.output_template == output_dir / "owner_decisions_template.local.jsonl"

    template_rows = [
        json.loads(line)
        for line in result.output_template.read_text(encoding="utf-8").splitlines()
    ]
    assert template_rows == [
        {
            "allowed_decisions": ["approve", "reject", "defer"],
            "assigned_lane": "sahira",
            "console_bucket": "owner_decision_inbox",
            "decision_note": "owner approved recovery",
            "decision_type": "approve_client_recovery_followup",
            "entry_id": "ledger-entry-pending",
            "event_actor": "owner",
            "event_recorded_at_utc": "2026-06-18T00:01:00+00:00",
            "owner_decision": "approve",
            "packet_id": "operator-packet-pending",
            "review_item_id": "operator-packet-review-item-pending",
            "review_state": "waiting_owner_decision",
        },
        {
            "allowed_decisions": ["approve", "reject", "defer"],
            "assigned_lane": "ari",
            "console_bucket": "owner_revisit_queue",
            "decision_note": "owner rejects escalation",
            "decision_type": "approve_immigration_status_escalation",
            "entry_id": "ledger-entry-defer",
            "event_actor": "owner",
            "event_recorded_at_utc": "",
            "owner_decision": "reject",
            "packet_id": "operator-packet-defer",
            "review_item_id": "operator-packet-review-item-defer",
            "review_state": "deferred_owner_revisit",
        },
    ]

    with sqlite3.connect(result.output_db) as conn:
        run = conn.execute(
            """
            SELECT inbox_item_count, captured_decision_count,
                   awaiting_owner_input_count, send_whatsapp_count, crm_mutation_count
            FROM owner_decision_cockpit_runs
            WHERE id = 1
            """
        ).fetchone()
        rows = conn.execute(
            """
            SELECT review_item_id, owner_decision, cockpit_status,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM owner_decision_cockpit_items
            ORDER BY cockpit_rank
            """
        ).fetchall()
    assert run == (2, 2, 0, 0, 0)
    assert rows == [
        (
            "operator-packet-review-item-pending",
            "approve",
            "ready_for_compile",
            0,
            0,
            1,
        ),
        (
            "operator-packet-review-item-defer",
            "reject",
            "ready_for_compile",
            0,
            0,
            1,
        ),
    ]

    compiler_result = build_owner_decision_compiler(
        owner_inbox_db=inbox_db,
        edited_template_jsonl=result.output_template,
        output_dir=tmp_path / "owner-decision-compiler",
        generated_at_utc="2026-06-18T00:03:00+00:00",
    )
    assert compiler_result.compiled_decision_count == 2
    assert compiler_result.send_whatsapp_count == 0
    assert compiler_result.crm_mutation_count == 0


def test_build_owner_decision_cockpit_keeps_missing_decisions_blank(
    tmp_path: Path,
) -> None:
    inbox_db, _blank_template = _build_inbox_fixture(tmp_path)
    owner_inputs = tmp_path / "owner_inputs.local.jsonl"
    output_dir = tmp_path / "owner-decision-cockpit"
    _write_owner_inputs(
        owner_inputs,
        [
            {
                "owner_decision": "defer",
                "review_item_id": "operator-packet-review-item-pending",
            },
        ],
    )

    result = build_owner_decision_cockpit(
        owner_inbox_db=inbox_db,
        owner_inputs_jsonl=owner_inputs,
        output_dir=output_dir,
        summary_path=output_dir / "owner_decision_cockpit_summary.md",
        generated_at_utc="2026-06-18T00:02:00+00:00",
    )

    assert result.captured_decision_count == 1
    assert result.awaiting_owner_input_count == 1
    rows = [
        json.loads(line)
        for line in result.output_template.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["owner_decision"] for row in rows] == ["defer", ""]
    assert rows[1]["decision_note"] == ""
    assert rows[1]["event_recorded_at_utc"] == ""


@pytest.mark.parametrize(
    ("owner_row", "message"),
    [
        (
            {
                "owner_decision": "maybe",
                "review_item_id": "operator-packet-review-item-pending",
            },
            "Owner cockpit decision is not allowed",
        ),
        (
            {
                "owner_decision": "approve",
                "review_item_id": "unknown-review-item",
            },
            "references unknown inbox item",
        ),
        (
            {
                "owner_decision": "approve",
                "review_item_id": "operator-packet-review-item-pending",
                "event_actor": "operator",
            },
            "has invalid actor",
        ),
    ],
)
def test_build_owner_decision_cockpit_rejects_invalid_owner_inputs(
    tmp_path: Path,
    owner_row: dict[str, str],
    message: str,
) -> None:
    inbox_db, _blank_template = _build_inbox_fixture(tmp_path)
    owner_inputs = tmp_path / "owner_inputs.local.jsonl"
    _write_owner_inputs(owner_inputs, [owner_row])

    with pytest.raises(ValueError, match=message):
        build_owner_decision_cockpit(
            owner_inbox_db=inbox_db,
            owner_inputs_jsonl=owner_inputs,
            output_dir=tmp_path / "owner-decision-cockpit",
            generated_at_utc="2026-06-18T00:02:00+00:00",
        )


def test_build_owner_decision_cockpit_rejects_duplicate_review_items(
    tmp_path: Path,
) -> None:
    inbox_db, _blank_template = _build_inbox_fixture(tmp_path)
    owner_inputs = tmp_path / "owner_inputs.local.jsonl"
    _write_owner_inputs(
        owner_inputs,
        [
            {
                "owner_decision": "approve",
                "review_item_id": "operator-packet-review-item-pending",
            },
            {
                "owner_decision": "reject",
                "review_item_id": "operator-packet-review-item-pending",
            },
        ],
    )

    with pytest.raises(ValueError, match="Duplicate owner cockpit decision"):
        build_owner_decision_cockpit(
            owner_inbox_db=inbox_db,
            owner_inputs_jsonl=owner_inputs,
            output_dir=tmp_path / "owner-decision-cockpit",
            generated_at_utc="2026-06-18T00:02:00+00:00",
        )


def test_cli_writes_json_without_owner_item_ids(tmp_path: Path) -> None:
    inbox_db, _blank_template = _build_inbox_fixture(tmp_path)
    owner_inputs = tmp_path / "owner_inputs.local.jsonl"
    output_dir = tmp_path / "owner-decision-cockpit"
    summary_path = output_dir / "owner_decision_cockpit_summary.md"
    _write_owner_inputs(
        owner_inputs,
        [
            {
                "owner_decision": "approve",
                "review_item_id": "operator-packet-review-item-pending",
            },
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-inbox-db",
            str(inbox_db),
            "--owner-inputs-jsonl",
            str(owner_inputs),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-18T00:02:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "awaiting_owner_input_count": 1,
        "captured_decision_count": 1,
        "crm_mutation_count": 0,
        "inbox_item_count": 2,
        "send_whatsapp_count": 0,
    }
    assert "operator-packet-review-item-pending" not in result.stdout


def test_cli_accepts_inline_owner_decisions_without_editing_jsonl(tmp_path: Path) -> None:
    inbox_db, _blank_template = _build_inbox_fixture(tmp_path)
    output_dir = tmp_path / "owner-decision-cockpit"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-inbox-db",
            str(inbox_db),
            "--decision",
            "operator-packet-review-item-pending=approve",
            "--decision",
            "operator-packet-review-item-defer=defer",
            "--decision-note",
            "operator-packet-review-item-pending=owner approved inline",
            "--output-dir",
            str(output_dir),
            "--generated-at-utc",
            "2026-06-18T00:02:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["captured_decision_count"] == 2
    rows = [
        json.loads(line)
        for line in (output_dir / "owner_decisions_template.local.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["owner_decision"] for row in rows] == ["approve", "defer"]
    assert rows[0]["decision_note"] == "owner approved inline"
    assert rows[1]["decision_note"] == ""


def test_readme_documents_cockpit_before_compiler() -> None:
    readme = (REPO_ROOT / "scripts" / "whatsapp_corpus" / "README.md").read_text(
        encoding="utf-8"
    )

    cockpit_index = readme.index("## Build Owner Decision Cockpit")
    compiler_index = readme.index("## Build Owner Decision Compiler")
    assert cockpit_index < compiler_index
    assert "python -m scripts.whatsapp_corpus.build_owner_decision_cockpit" in readme
    assert "--decision operator-packet-review-item-pending=approve" in readme


def test_build_owner_decision_cockpit_has_no_sender_or_cloud_imports() -> None:
    forbidden_imports = (
        "anthropic",
        "backend.app.services.crm",
        "backend.channels.whatsapp",
        "httpx",
        "openai",
        "requests",
    )
    import_lines = [
        line.strip()
        for line in SCRIPT.read_text(encoding="utf-8").splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]

    for import_line in import_lines:
        assert not any(forbidden in import_line for forbidden in forbidden_imports)
