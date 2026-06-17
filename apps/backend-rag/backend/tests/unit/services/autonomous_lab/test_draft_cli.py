from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[7]
SCRIPT = REPO_ROOT / "scripts" / "autonomous_lab_draft.py"


def _input_payload(raw_phrase: str = "RAW_TEXT_MUST_NOT_LEAK") -> dict:
    return {
        "created_at": "2026-05-31T01:20:00+08:00",
        "objective": "draft an autonomous lab receipt",
        "task_id": "cli-test-run",
        "worktree_lane": "ops",
        "target_paths": [
            "apps/backend-rag/backend/services/autonomous_lab/planner.py",
            "scripts/autonomous_lab_draft.py",
        ],
        "materials": [
            {
                "material_id": "m1",
                "source_type": "operator_note",
                "source_uri": "note://local/test",
                "title": "CLI test material",
                "text": f"Use source agnostic materials and do not leak raw content. {raw_phrase}",
                "captured_at": "2026-05-31T01:20:00+08:00",
                "metadata": {"scope": "unit-test"},
            }
        ],
    }


def test_cli_writes_receipt_and_omits_raw_text(tmp_path: Path) -> None:
    raw_phrase = "RAW_TEXT_MUST_NOT_LEAK"
    input_path = tmp_path / "input.json"
    receipt_dir = tmp_path / "receipts"
    input_path.write_text(json.dumps(_input_payload(raw_phrase)), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(input_path),
            "--receipt-dir",
            str(receipt_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = json.loads(result.stdout)
    receipt_path = Path(stdout["receipt_path"])
    receipt_text = receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)

    assert stdout["ok"] is True
    assert stdout["worktree_command"].endswith("--task-id cli-test-run")
    assert receipt["run_id"] == "cli-test-run"
    assert raw_phrase not in receipt_text
    assert "content_fingerprint" in receipt_text


def test_cli_blocks_workspace_write_requests(tmp_path: Path) -> None:
    payload = _input_payload()
    payload["materials"][0]["metadata"]["requires_google_workspace_write"] = "true"
    input_path = tmp_path / "input.json"
    receipt_dir = tmp_path / "receipts"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(input_path),
            "--receipt-dir",
            str(receipt_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    stdout = json.loads(result.stdout)
    assert stdout["blocked"] is True
    assert stdout["failed_blockers"] == ["google_workspace_write_block"]
    receipt = json.loads(Path(stdout["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["blocked"] is True


def test_cli_invalid_input_returns_receipt_safe_json_error(tmp_path: Path) -> None:
    bad_path = "apps/backend-rag/backend/services/autonomous_lab/planner.py\nBAD"
    payload = _input_payload()
    payload["target_paths"] = [bad_path]
    input_path = tmp_path / "input.json"
    receipt_dir = tmp_path / "receipts"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(input_path),
            "--receipt-dir",
            str(receipt_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = json.loads(result.stdout)
    assert result.returncode == 1
    assert result.stderr == ""
    assert stdout["ok"] is False
    assert stdout["failed_blockers"] == ["input_validation"]
    assert "error_reference" in stdout
    assert bad_path not in result.stdout
    assert "control characters" not in result.stdout
