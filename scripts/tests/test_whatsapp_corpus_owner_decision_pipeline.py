from __future__ import annotations

import ast
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.whatsapp_corpus.build_owner_decision_pipeline as pipeline_module
from scripts.tests.test_whatsapp_corpus_owner_decision_intake import (
    _write_operator_packet_review_console_db,
)
from scripts.tests.test_whatsapp_corpus_owner_decision_replay import (
    _write_matching_approve_reject_ledger_db,
)
from scripts.whatsapp_corpus.build_owner_decision_pipeline import (
    OwnerDecisionPipelineBuildResult,
    StageOutput,
    build_owner_decision_pipeline,
    _write_manifest_sqlite,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "build_owner_decision_pipeline.py"


def _write_pipeline_sources(tmp_path: Path) -> tuple[Path, Path]:
    ledger_db = tmp_path / "approve_reject_ledger.local.sqlite"
    review_console_db = tmp_path / "operator_packet_review_console.local.sqlite"
    _write_matching_approve_reject_ledger_db(ledger_db)
    _write_operator_packet_review_console_db(review_console_db)
    return ledger_db, review_console_db


def test_build_owner_decision_pipeline_runs_full_local_chain_from_inline_decisions(
    tmp_path: Path,
) -> None:
    ledger_db, review_console_db = _write_pipeline_sources(tmp_path)
    output_dir = tmp_path / "owner-decision-pipeline"

    result = build_owner_decision_pipeline(
        ledger_db=ledger_db,
        review_console_db=review_console_db,
        inline_decisions=(
            "operator-packet-review-item-pending=approve",
            "operator-packet-review-item-defer=reject",
        ),
        inline_decision_notes=(
            "operator-packet-review-item-pending=owner approved recovery",
        ),
        output_dir=output_dir,
        summary_path=output_dir / "owner_decision_pipeline_summary.md",
        generated_at_utc="2026-06-18T01:00:00+00:00",
    )

    assert result.pipeline_status == "replayed"
    assert result.inbox_item_count == 2
    assert result.captured_decision_count == 2
    assert result.awaiting_owner_input_count == 0
    assert result.compiled_decision_count == 2
    assert result.replay_event_count == 2
    assert result.final_review_item_count == 2
    assert result.final_operator_ready_item_count == 1
    assert result.final_rejected_item_count == 1
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.output_db == output_dir / "owner_decision_pipeline.local.sqlite"
    assert result.owner_inbox_db == (
        output_dir / "owner-decision-inbox/owner_decision_inbox.local.sqlite"
    )
    assert result.owner_cockpit_db == (
        output_dir / "owner-decision-cockpit/owner_decision_cockpit.local.sqlite"
    )
    assert result.owner_compiler_db == (
        output_dir / "owner-decision-compiler/owner_decision_compiler.local.sqlite"
    )
    assert result.owner_replay_db == (
        output_dir / "owner-decision-replay/owner_decision_replay.local.sqlite"
    )
    summary = result.summary_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in summary
    assert "research/personal/wa-corpus" not in summary

    with sqlite3.connect(result.output_db) as conn:
        run = conn.execute(
            """
            SELECT pipeline_status, inbox_item_count, captured_decision_count,
                   awaiting_owner_input_count, compiled_decision_count,
                   replay_event_count, final_review_item_count,
                   send_whatsapp_count, crm_mutation_count
            FROM owner_decision_pipeline_runs
            WHERE id = 1
            """
        ).fetchone()
        stages = conn.execute(
            """
            SELECT stage_name, item_count
            FROM owner_decision_pipeline_stage_outputs
            ORDER BY stage_rank
            """
        ).fetchall()
    assert run == ("replayed", 2, 2, 0, 2, 2, 2, 0, 0)
    assert stages == [
        ("owner_decision_inbox", 2),
        ("owner_decision_cockpit", 2),
        ("owner_decision_compiler", 2),
        ("owner_decision_replay", 2),
    ]


def test_build_owner_decision_pipeline_stops_before_compiler_when_input_is_missing(
    tmp_path: Path,
) -> None:
    ledger_db, review_console_db = _write_pipeline_sources(tmp_path)
    output_dir = tmp_path / "owner-decision-pipeline"

    result = build_owner_decision_pipeline(
        ledger_db=ledger_db,
        review_console_db=review_console_db,
        inline_decisions=("operator-packet-review-item-pending=defer",),
        output_dir=output_dir,
        summary_path=output_dir / "owner_decision_pipeline_summary.md",
        generated_at_utc="2026-06-18T01:00:00+00:00",
    )

    assert result.pipeline_status == "awaiting_owner_input"
    assert result.inbox_item_count == 2
    assert result.captured_decision_count == 1
    assert result.awaiting_owner_input_count == 1
    assert result.compiled_decision_count == 0
    assert result.replay_event_count == 0
    assert result.final_review_item_count == 0
    assert result.send_whatsapp_count == 0
    assert result.crm_mutation_count == 0
    assert result.owner_compiler_db is None
    assert result.owner_replay_db is None
    assert not (output_dir / "owner-decision-compiler").exists()
    assert not (output_dir / "owner-decision-replay").exists()

    with sqlite3.connect(result.output_db) as conn:
        stages = conn.execute(
            """
            SELECT stage_name, item_count
            FROM owner_decision_pipeline_stage_outputs
            ORDER BY stage_rank
            """
        ).fetchall()
    assert stages == [
        ("owner_decision_inbox", 2),
        ("owner_decision_cockpit", 2),
    ]


def test_pipeline_removes_stale_downstream_outputs_when_later_awaiting(
    tmp_path: Path,
) -> None:
    ledger_db, review_console_db = _write_pipeline_sources(tmp_path)
    output_dir = tmp_path / "owner-decision-pipeline"

    replayed = build_owner_decision_pipeline(
        ledger_db=ledger_db,
        review_console_db=review_console_db,
        inline_decisions=(
            "operator-packet-review-item-pending=approve",
            "operator-packet-review-item-defer=reject",
        ),
        output_dir=output_dir,
        summary_path=output_dir / "owner_decision_pipeline_summary.md",
        generated_at_utc="2026-06-18T01:00:00+00:00",
    )
    assert replayed.pipeline_status == "replayed"
    assert (output_dir / "owner-decision-compiler").exists()
    assert (output_dir / "owner-decision-replay").exists()

    awaiting = build_owner_decision_pipeline(
        ledger_db=ledger_db,
        review_console_db=review_console_db,
        inline_decisions=("operator-packet-review-item-pending=defer",),
        output_dir=output_dir,
        summary_path=output_dir / "owner_decision_pipeline_summary.md",
        generated_at_utc="2026-06-18T01:00:00+00:00",
    )

    assert awaiting.pipeline_status == "awaiting_owner_input"
    assert not (output_dir / "owner-decision-compiler").exists()
    assert not (output_dir / "owner-decision-replay").exists()


def test_cli_writes_json_without_review_item_ids(tmp_path: Path) -> None:
    ledger_db, review_console_db = _write_pipeline_sources(tmp_path)
    output_dir = tmp_path / "owner-decision-pipeline"
    summary_path = output_dir / "owner_decision_pipeline_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ledger-db",
            str(ledger_db),
            "--review-console-db",
            str(review_console_db),
            "--decision",
            "operator-packet-review-item-pending=approve",
            "--decision",
            "operator-packet-review-item-defer=reject",
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary_path),
            "--generated-at-utc",
            "2026-06-18T01:00:00+00:00",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "awaiting_owner_input_count": 0,
        "captured_decision_count": 2,
        "compiled_decision_count": 2,
        "crm_mutation_count": 0,
        "final_review_item_count": 2,
        "inbox_item_count": 2,
        "pipeline_status": "replayed",
        "replay_event_count": 2,
        "send_whatsapp_count": 0,
    }
    assert str(tmp_path) not in result.stdout
    assert "operator-packet-review-item-pending" not in result.stdout
    assert "ledger-entry-pending" not in result.stdout


def test_cli_errors_do_not_leak_absolute_paths(tmp_path: Path) -> None:
    missing_review_console = (
        tmp_path / "missing" / "operator_packet_review_console.local.sqlite"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--review-console-db",
            str(missing_review_console),
            "--output-dir",
            str(tmp_path / "owner-decision-pipeline"),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "ERROR: Owner decision pipeline input is missing or invalid.\n"
    assert str(tmp_path) not in result.stderr
    assert "operator_packet_review_console.local.sqlite" not in result.stderr
    assert ".sqlite" not in result.stderr


def test_readme_documents_owner_decision_pipeline() -> None:
    readme = (REPO_ROOT / "scripts" / "whatsapp_corpus" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "## Build Owner Decision Pipeline" in readme
    assert "python -m scripts.whatsapp_corpus.build_owner_decision_pipeline" in readme
    assert "awaiting_owner_input" in readme


@pytest.mark.parametrize(("send_count", "crm_count"), ((1, 0), (0, 1)))
def test_manifest_rejects_nonzero_send_or_crm_counts(
    tmp_path: Path,
    send_count: int,
    crm_count: int,
) -> None:
    result = OwnerDecisionPipelineBuildResult(
        pipeline_status="replayed",
        inbox_item_count=1,
        captured_decision_count=1,
        awaiting_owner_input_count=0,
        compiled_decision_count=1,
        replay_event_count=1,
        final_review_item_count=1,
        final_operator_ready_item_count=1,
        final_rejected_item_count=0,
        send_whatsapp_count=send_count,
        crm_mutation_count=crm_count,
        output_db=tmp_path / "owner_decision_pipeline.local.sqlite",
        summary_path=tmp_path / "owner_decision_pipeline_summary.md",
        owner_inbox_db=tmp_path / "owner_decision_inbox.local.sqlite",
        owner_cockpit_db=tmp_path / "owner_decision_cockpit.local.sqlite",
        owner_compiler_db=tmp_path / "owner_decision_compiler.local.sqlite",
        owner_replay_db=tmp_path / "owner_decision_replay.local.sqlite",
    )

    with pytest.raises(sqlite3.IntegrityError):
        _write_manifest_sqlite(
            result.output_db,
            result=result,
            stages=(
                StageOutput(
                    1,
                    "owner_decision_inbox",
                    1,
                    result.owner_inbox_db,
                    tmp_path / "owner_decision_inbox_summary.md",
                ),
            ),
            generated_at_utc="2026-06-18T01:00:00+00:00",
        )


def test_pipeline_manifest_counts_include_all_invoked_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "owner-decision-pipeline"

    def fake_inbox(**_: object) -> SimpleNamespace:
        return SimpleNamespace(
            inbox_item_count=1,
            send_whatsapp_count=1,
            crm_mutation_count=0,
            output_db=output_dir / "owner-decision-inbox/owner_decision_inbox.local.sqlite",
        )

    def fake_cockpit(**_: object) -> SimpleNamespace:
        return SimpleNamespace(
            inbox_item_count=1,
            captured_decision_count=1,
            awaiting_owner_input_count=0,
            send_whatsapp_count=0,
            crm_mutation_count=0,
            output_db=output_dir / "owner-decision-cockpit/owner_decision_cockpit.local.sqlite",
            output_template=output_dir
            / "owner-decision-cockpit/owner_decisions_template.local.jsonl",
        )

    def fake_compiler(**_: object) -> SimpleNamespace:
        return SimpleNamespace(
            compiled_decision_count=1,
            send_whatsapp_count=0,
            crm_mutation_count=0,
            output_db=output_dir / "owner-decision-compiler/owner_decision_compiler.local.sqlite",
            output_jsonl=output_dir / "owner-decision-compiler/owner_decisions.local.jsonl",
        )

    def fake_replay(**_: object) -> SimpleNamespace:
        return SimpleNamespace(
            replay_event_count=1,
            final_review_item_count=1,
            final_operator_ready_item_count=1,
            final_rejected_item_count=0,
            send_whatsapp_count=0,
            crm_mutation_count=0,
            output_db=output_dir / "owner-decision-replay/owner_decision_replay.local.sqlite",
        )

    monkeypatch.setattr(pipeline_module, "build_owner_decision_inbox", fake_inbox)
    monkeypatch.setattr(pipeline_module, "build_owner_decision_cockpit", fake_cockpit)
    monkeypatch.setattr(pipeline_module, "build_owner_decision_compiler", fake_compiler)
    monkeypatch.setattr(pipeline_module, "build_owner_decision_replay", fake_replay)

    with pytest.raises(sqlite3.IntegrityError):
        build_owner_decision_pipeline(
            ledger_db=tmp_path / "ledger.local.sqlite",
            review_console_db=tmp_path / "review.local.sqlite",
            output_dir=output_dir,
            summary_path=output_dir / "owner_decision_pipeline_summary.md",
            generated_at_utc="2026-06-18T01:00:00+00:00",
        )


def test_build_owner_decision_pipeline_has_no_sender_or_cloud_imports() -> None:
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


def _collect_whatsapp_corpus_import_closure(entrypoint: Path) -> set[Path]:
    pending = [entrypoint]
    visited: set[Path] = set()
    while pending:
        script = pending.pop()
        if script in visited:
            continue
        visited.add(script)
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            prefix = "scripts.whatsapp_corpus."
            module_names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                module_names.append(node.module)
            elif isinstance(node, ast.Import):
                module_names.extend(alias.name for alias in node.names)
            for module_name in module_names:
                if not module_name.startswith(prefix):
                    continue
                local_module = module_name.removeprefix(prefix)
                module_path = (
                    REPO_ROOT / "scripts" / "whatsapp_corpus" / f"{local_module}.py"
                )
                if module_path.exists() and module_path not in visited:
                    pending.append(module_path)
    return visited


def test_invoked_owner_decision_modules_have_no_sender_or_cloud_imports() -> None:
    forbidden_imports = (
        "anthropic",
        "backend.app.services.crm",
        "backend.channels.whatsapp",
        "httpx",
        "openai",
        "requests",
    )
    invoked_scripts = _collect_whatsapp_corpus_import_closure(
        REPO_ROOT
        / "scripts"
        / "whatsapp_corpus"
        / "build_owner_decision_pipeline.py"
    )

    assert {
        script.name for script in invoked_scripts
    } >= {
        "build_owner_decision_pipeline.py",
        "build_owner_decision_inbox.py",
        "build_owner_decision_cockpit.py",
        "build_owner_decision_compiler.py",
        "build_owner_decision_replay.py",
    }

    for script in invoked_scripts:
        import_lines = [
            line.strip()
            for line in script.read_text(encoding="utf-8").splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        assert not any(
            forbidden in import_line
            for import_line in import_lines
            for forbidden in forbidden_imports
        ), script.name
