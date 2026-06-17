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
from scripts.whatsapp_corpus.build_owner_decision_inbox import (
    build_owner_decision_inbox,
)
from scripts.whatsapp_corpus.build_owner_decision_intake import (
    build_owner_decision_intake,
)
from scripts.whatsapp_corpus.build_owner_decision_compiler import (
    build_owner_decision_compiler,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_decision_compiler.py"


def _build_inbox_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    inbox_dir = tmp_path / "owner-decision-inbox"
    _write_operator_packet_review_console_db(review_console_db)
    inbox_result = build_owner_decision_inbox(
        review_console_db=review_console_db,
        output_dir=inbox_dir,
        summary_path=inbox_dir / "owner_decision_inbox_summary.md",
        generated_at_utc="2026-06-18T00:00:00+00:00",
    )
    return (
        review_console_db,
        inbox_result.output_db,
        inbox_result.output_template,
        inbox_dir,
    )


def _write_edited_template(
    template_path: Path,
    *,
    decisions: list[str],
    timestamps: list[str] | None = None,
    extra_fields: dict[str, str] | None = None,
) -> None:
    rows = [
        json.loads(line)
        for line in template_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == len(decisions)
    for index, (row, decision) in enumerate(zip(rows, decisions, strict=True)):
        row["owner_decision"] = decision
        row["decision_note"] = f"owner note {decision}"
        if timestamps is not None:
            row["event_recorded_at_utc"] = timestamps[index]
        if extra_fields:
            row.update(extra_fields)
    template_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_build_owner_decision_compiler_emits_clean_input_for_real_intake(
    tmp_path: Path,
) -> None:
    review_console_db, inbox_db, template_path, _inbox_dir = _build_inbox_fixture(tmp_path)
    output_dir = tmp_path / "owner-decision-compiler"
    _write_edited_template(
        template_path,
        decisions=["approve", "reject"],
        timestamps=["2026-06-18T00:01:00+00:00", ""],
        extra_fields={
            "client_phone_number": "+62 812 0000 0000",
            "message_text": "raw text must never pass through",
        },
    )

    result = build_owner_decision_compiler(
        owner_inbox_db=inbox_db,
        edited_template_jsonl=template_path,
        output_dir=output_dir,
        summary_path=output_dir / "owner_decision_compiler_summary.md",
        generated_at_utc="2026-06-18T00:02:00+00:00",
    )

    assert result.source_inbox_item_count == 2
    assert result.template_row_count == 2
    assert result.compiled_decision_count == 2
    assert result.backfilled_timestamp_count == 1
    assert result.owner_supplied_timestamp_count == 1
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.output_jsonl == output_dir / "owner_decisions.local.jsonl"

    output_rows = [
        json.loads(line)
        for line in result.output_jsonl.read_text(encoding="utf-8").splitlines()
    ]
    assert output_rows == [
        {
            "decision_note": "owner note approve",
            "event_actor": "owner",
            "event_recorded_at_utc": "2026-06-18T00:01:00+00:00",
            "owner_decision": "approve",
            "review_item_id": "operator-packet-review-item-pending",
            "timestamp_source": "owner_supplied",
        },
        {
            "decision_note": "owner note reject",
            "event_actor": "owner",
            "event_recorded_at_utc": "2026-06-18T00:02:00+00:00",
            "owner_decision": "reject",
            "review_item_id": "operator-packet-review-item-defer",
            "timestamp_source": "compiler_generated_at_utc",
        },
    ]
    assert "client_phone_number" not in result.output_jsonl.read_text(encoding="utf-8")
    assert "message_text" not in result.output_jsonl.read_text(encoding="utf-8")

    with sqlite3.connect(result.output_db) as conn:
        run = conn.execute(
            """
            SELECT source_inbox_item_count, template_row_count,
                   compiled_decision_count, backfilled_timestamp_count,
                   owner_supplied_timestamp_count, send_whatsapp_count,
                   crm_mutation_count
            FROM owner_decision_compiler_runs
            WHERE id = 1
            """
        ).fetchone()
        db_rows = conn.execute(
            """
            SELECT review_item_id, owner_decision, timestamp_source,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM owner_decision_compiler_items
            ORDER BY compile_rank
            """
        ).fetchall()
    assert run == (2, 2, 2, 1, 1, 0, 0)
    assert db_rows == [
        (
            "operator-packet-review-item-pending",
            "approve",
            "owner_supplied",
            0,
            0,
            1,
        ),
        (
            "operator-packet-review-item-defer",
            "reject",
            "compiler_generated_at_utc",
            0,
            0,
            1,
        ),
    ]

    intake_dir = tmp_path / "owner-decision-intake"
    intake_result = build_owner_decision_intake(
        review_console_db=review_console_db,
        owner_decisions_jsonl=result.output_jsonl,
        output_dir=intake_dir,
        summary_path=intake_dir / "owner_decision_intake_summary.md",
        generated_at_utc="2026-06-18T00:03:00+00:00",
    )
    assert intake_result.captured_decision_count == 2
    assert intake_result.replay_event_count == 2
    assert intake_result.send_whatsapp_count == 0
    assert intake_result.crm_mutation_count == 0

    summary = result.summary_path.read_text(encoding="utf-8")
    assert "# Zantara Owner Decision Compiler Summary" in summary
    assert "| Compiled decisions | 2 |" in summary
    assert "| WhatsApp sends | 0 |" in summary
    assert "| CRM mutations | 0 |" in summary
    assert "operator-packet-review-item-pending" not in summary
    assert "client_phone_number" not in summary
    assert "message_text" not in summary


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda row: row.update({"owner_decision": ""}),
            "Owner decision is missing",
        ),
        (
            lambda row: row.update({"owner_decision": "maybe"}),
            "Owner decision is not allowed",
        ),
        (
            lambda row: row.update({"review_item_id": "unknown-review-item"}),
            "references unknown inbox item",
        ),
        (
            lambda row: row.update({"packet_id": "tampered-packet"}),
            "does not match inbox DB",
        ),
    ],
)
def test_build_owner_decision_compiler_rejects_invalid_template_rows(
    tmp_path: Path,
    mutator,
    message: str,
) -> None:
    _review_console_db, inbox_db, template_path, _inbox_dir = _build_inbox_fixture(tmp_path)
    _write_edited_template(
        template_path,
        decisions=["approve", "defer"],
        timestamps=["2026-06-18T00:01:00+00:00", "2026-06-18T00:02:00+00:00"],
    )
    rows = [
        json.loads(line)
        for line in template_path.read_text(encoding="utf-8").splitlines()
    ]
    mutator(rows[0])
    template_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        build_owner_decision_compiler(
            owner_inbox_db=inbox_db,
            edited_template_jsonl=template_path,
            output_dir=tmp_path / "owner-decision-compiler",
            summary_path=tmp_path / "summary.md",
            generated_at_utc="2026-06-18T00:02:00+00:00",
        )


def test_build_owner_decision_compiler_rejects_duplicate_review_items(
    tmp_path: Path,
) -> None:
    _review_console_db, inbox_db, template_path, _inbox_dir = _build_inbox_fixture(tmp_path)
    _write_edited_template(
        template_path,
        decisions=["approve", "reject"],
        timestamps=["2026-06-18T00:01:00+00:00", "2026-06-18T00:02:00+00:00"],
    )
    rows = [
        json.loads(line)
        for line in template_path.read_text(encoding="utf-8").splitlines()
    ]
    rows[1]["review_item_id"] = rows[0]["review_item_id"]
    template_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate owner decision compiler row"):
        build_owner_decision_compiler(
            owner_inbox_db=inbox_db,
            edited_template_jsonl=template_path,
            output_dir=tmp_path / "owner-decision-compiler",
            summary_path=tmp_path / "summary.md",
            generated_at_utc="2026-06-18T00:02:00+00:00",
        )


def test_build_owner_decision_compiler_removes_stale_outputs_on_invalid_rerun(
    tmp_path: Path,
) -> None:
    _review_console_db, inbox_db, template_path, _inbox_dir = _build_inbox_fixture(tmp_path)
    output_dir = tmp_path / "owner-decision-compiler"
    summary_path = output_dir / "owner_decision_compiler_summary.md"
    _write_edited_template(
        template_path,
        decisions=["approve", "reject"],
        timestamps=["2026-06-18T00:01:00+00:00", "2026-06-18T00:02:00+00:00"],
    )
    first_result = build_owner_decision_compiler(
        owner_inbox_db=inbox_db,
        edited_template_jsonl=template_path,
        output_dir=output_dir,
        summary_path=summary_path,
        generated_at_utc="2026-06-18T00:03:00+00:00",
    )
    assert first_result.output_db.exists()
    assert first_result.output_jsonl.exists()
    assert first_result.summary_path.exists()

    rows = [
        json.loads(line)
        for line in template_path.read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["owner_decision"] = ""
    template_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Owner decision is missing"):
        build_owner_decision_compiler(
            owner_inbox_db=inbox_db,
            edited_template_jsonl=template_path,
            output_dir=output_dir,
            summary_path=summary_path,
            generated_at_utc="2026-06-18T00:04:00+00:00",
        )

    assert not first_result.output_db.exists()
    assert not first_result.output_jsonl.exists()
    assert not first_result.summary_path.exists()


def test_readme_owner_decision_chain_consumes_compiler_output_path() -> None:
    readme = (REPO_ROOT / "scripts" / "whatsapp_corpus" / "README.md").read_text(
        encoding="utf-8"
    )
    compiler_path = (
        "research/personal/wa-corpus/owner-decision-compiler/"
        "owner_decisions.local.jsonl"
    )
    legacy_intake_path = (
        "research/personal/wa-corpus/owner-decision-intake/"
        "owner_decisions.local.jsonl"
    )

    assert f"--owner-decisions-jsonl {compiler_path} \\" in readme
    assert legacy_intake_path not in readme


def test_cli_writes_json_without_owner_item_ids(tmp_path: Path) -> None:
    _review_console_db, inbox_db, template_path, _inbox_dir = _build_inbox_fixture(tmp_path)
    output_dir = tmp_path / "owner-decision-compiler"
    _write_edited_template(
        template_path,
        decisions=["approve", "reject"],
        timestamps=["2026-06-18T00:01:00+00:00", "2026-06-18T00:02:00+00:00"],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-inbox-db",
            str(inbox_db),
            "--edited-template-jsonl",
            str(template_path),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(output_dir / "owner_decision_compiler_summary.md"),
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
        "backfilled_timestamp_count": 0,
        "compiled_decision_count": 2,
        "crm_mutation_count": 0,
        "owner_supplied_timestamp_count": 2,
        "send_whatsapp_count": 0,
        "source_inbox_item_count": 2,
        "template_row_count": 2,
    }
    assert "operator-packet-review-item-pending" not in result.stdout


def test_cli_derives_default_summary_from_output_dir(tmp_path: Path) -> None:
    _review_console_db, inbox_db, template_path, _inbox_dir = _build_inbox_fixture(tmp_path)
    output_dir = tmp_path / "custom-owner-decision-compiler"
    _write_edited_template(
        template_path,
        decisions=["approve", "reject"],
        timestamps=["2026-06-18T00:01:00+00:00", "2026-06-18T00:02:00+00:00"],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--owner-inbox-db",
            str(inbox_db),
            "--edited-template-jsonl",
            str(template_path),
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
    expected_summary = output_dir / "owner_decision_compiler_summary.md"
    assert "summary_path" not in payload
    assert expected_summary.exists()


def test_build_owner_decision_compiler_has_no_sender_or_cloud_imports() -> None:
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
