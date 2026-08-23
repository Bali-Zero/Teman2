from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from research_os.cli import FIXTURES_ROOT, PACKAGE_ROOT


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "research_os.cli", *args],
        check=False,
        capture_output=True,
        cwd=PACKAGE_ROOT,
        text=True,
    )


def test_validate_cli_returns_machine_readable_success() -> None:
    fixture = FIXTURES_ROOT / "object_successor_edge" / "valid_minimal.json"
    result = _run_cli("validate", "--contract", "object_successor_edge", "--file", str(fixture))
    assert result.returncode == 0
    assert json.loads(result.stdout)["valid"] is True


def test_validate_cli_returns_one_for_invalid_contract() -> None:
    fixture = FIXTURES_ROOT / "object_successor_edge" / "invalid_same_ref.json"
    result = _run_cli("validate", "--contract", "object_successor_edge", "--file", str(fixture))
    assert result.returncode == 1
    assert json.loads(result.stdout)["valid"] is False


def test_usage_error_returns_two() -> None:
    result = _run_cli("validate")
    assert result.returncode == 2


def test_fixtures_check_validates_full_tree() -> None:
    result = _run_cli("fixtures", "--check")
    assert result.returncode == 0
    assert json.loads(result.stdout)["valid"] is True


def test_hash_cli_prints_lowercase_sha256(tmp_path: Path) -> None:
    payload_path = tmp_path / "object.json"
    payload_path.write_text(
        json.dumps({"contract_version": "research-os/v1.0.0", "value": 1}), encoding="utf-8"
    )
    result = _run_cli("hash", "--file", str(payload_path))
    assert result.returncode == 0
    assert len(json.loads(result.stdout)["object_hash"]) == 64


def test_compat_cli_reports_breaking_reasons(tmp_path: Path) -> None:
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(json.dumps({"type": "string", "enum": ["a"]}), encoding="utf-8")
    new.write_text(json.dumps({"type": "string", "enum": ["a", "b"]}), encoding="utf-8")
    result = _run_cli("compat", "--old", str(old), "--new", str(new))
    assert result.returncode == 1
    assert "enum addition at $: b" in json.loads(result.stdout)["breaking_reasons"]
