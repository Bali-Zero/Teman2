from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[7]
SCRIPT = REPO_ROOT / "scripts" / "autonomous_lab_run.py"


def _load_run_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("autonomous_lab_run", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run_cli() -> ModuleType:
    return _load_run_cli()


def _input_payload(
    *,
    raw_phrase: str = "RAW_TEXT_MUST_NOT_LEAK",
    target_paths: list[str] | None = None,
) -> dict:
    return {
        "created_at": "2026-05-31T01:20:00+08:00",
        "objective": "run a bounded autonomous lab verification wrapper",
        "task_id": "run-cli-test",
        "worktree_lane": "ops",
        "target_paths": target_paths
        or ["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        "materials": [
            {
                "material_id": "m1",
                "source_type": "operator_note",
                "source_uri": "note://local/run-cli-test",
                "title": "Run CLI test material",
                "text": f"Planner evidence for a dry-run wrapper. {raw_phrase}",
                "captured_at": "2026-05-31T01:20:00+08:00",
                "metadata": {"scope": "unit-test"},
            }
        ],
    }


def _write_input(tmp_path: Path, payload: dict) -> Path:
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    return input_path


def test_dry_run_does_not_execute_verification_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_cli: ModuleType,
) -> None:
    input_path = _write_input(tmp_path, _input_payload())

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry-run must not invoke subprocess.run")

    monkeypatch.setattr(run_cli.subprocess, "run", fail_if_called)

    exit_code = run_cli.main([str(input_path)])
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)

    assert exit_code == 0
    assert summary["mode"] == "dry-run"
    assert summary["verification"]["execute_requested"] is False
    assert summary["verification"]["results"][0]["executed"] is False


def test_execute_refuses_unsafe_verification_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_cli: ModuleType,
) -> None:
    payload = _input_payload(target_paths=["apps/mouth/src/lib/api/crm/crm.api.ts"])
    input_path = _write_input(tmp_path, payload)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unsafe verification command must be refused before execution")

    monkeypatch.setattr(run_cli.subprocess, "run", fail_if_called)

    exit_code = run_cli.main([str(input_path), "--execute-verification"])
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)

    assert exit_code == 3
    assert summary["ok"] is False
    assert summary["unsafe_verification_refused"] is True
    assert summary["verification"]["refused_commands"] == [
        {
            "command": "cd apps/mouth && npm run lint",
            "reason": "command_not_allowlisted",
        }
    ]
    assert run_cli.refusal_reason("git push origin main") == "blocked_command_verb"
    assert run_cli.refusal_reason("fly deploy") == "blocked_command_verb"
    assert run_cli.refusal_reason("git merge main") == "blocked_command_verb"


def test_dry_run_marks_non_allowlisted_verification_as_not_ok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_cli: ModuleType,
) -> None:
    payload = _input_payload(target_paths=["apps/mouth/src/lib/api/crm/crm.api.ts"])
    input_path = _write_input(tmp_path, payload)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry-run must not execute refused verification commands")

    monkeypatch.setattr(run_cli.subprocess, "run", fail_if_called)

    exit_code = run_cli.main([str(input_path)])
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)

    assert exit_code == 3
    assert summary["ok"] is False
    assert summary["unsafe_verification_refused"] is True
    assert summary["verification"]["refused_commands"] == [
        {
            "command": "cd apps/mouth && npm run lint",
            "reason": "command_not_allowlisted",
        }
    ]
    assert summary["verification"]["results"][0]["allowed"] is False
    assert summary["verification"]["results"][0]["executed"] is False


def test_raw_text_is_omitted_from_lab_run_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    run_cli: ModuleType,
) -> None:
    raw_phrase = "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"
    input_path = _write_input(tmp_path, _input_payload(raw_phrase=raw_phrase))

    exit_code = run_cli.main([str(input_path)])
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)

    assert exit_code == 0
    assert raw_phrase not in stdout
    assert "content_fingerprint" in stdout
    assert summary["receipt"]["run_id"] == "run-cli-test"
    assert all("text" not in material for material in summary["receipt"]["materials"])


def test_execute_runs_only_allowlisted_commands_without_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_cli: ModuleType,
) -> None:
    payload = _input_payload(
        target_paths=[
            "apps/backend-rag/backend/services/autonomous_lab/planner.py",
            "research/operations/autonomous-lab/2026-05-31-technical-map.md",
        ]
    )
    input_path = _write_input(tmp_path, payload)
    calls: list[tuple[list[str], dict]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(run_cli.subprocess, "run", fake_run)

    exit_code = run_cli.main([str(input_path), "--execute-verification"])
    stdout = capsys.readouterr().out
    summary = json.loads(stdout)

    assert exit_code == 0
    assert len(calls) == 2
    assert all("shell" not in kwargs for _, kwargs in calls)
    assert calls[0][1]["cwd"] == run_cli.BACKEND_ROOT
    assert calls[0][1]["env"]["PYTHONPATH"] == "."
    assert calls[0][0][-2:] == ["backend/tests/unit/services/autonomous_lab", "-q"]
    assert calls[1][0] == [
        "git",
        "diff",
        "--check",
        "--",
        "research/operations/autonomous-lab",
    ]
    assert summary["verification_failed"] is False
    assert [result["executed"] for result in summary["verification"]["results"]] == [True, True]
