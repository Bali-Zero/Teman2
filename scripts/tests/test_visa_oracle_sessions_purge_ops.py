"""Ops-shape tests for the Visa Oracle SESSIONS purge scheduler payload —
mirrors `scripts/tests/test_visa_oracle_retention_ops.py`'s own
launchagent/wrapper checks (that file covers visa DECISIONS retention; this
one covers the separate sessions purge added alongside migration 317's
enforcement). No database needed — plist parsing + subprocess syntax/argv
checks only.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLIST_PATH = (
    _REPO_ROOT
    / "infra"
    / "launchagents"
    / "com.nuzantara.visa-oracle-sessions-purge.15min.plist.example"
)
_WRAPPER_PATH = (
    _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "visa-oracle-sessions-purge-run.sh"
)


def test_launchagent_is_one_shot_dry_run_and_uses_existing_cron_wrapper() -> None:
    with _PLIST_PATH.open("rb") as handle:
        manifest = plistlib.load(handle)

    assert manifest["KeepAlive"] is False
    assert manifest["RunAtLoad"] is False
    assert manifest["StartInterval"] == 900
    # A failed purge tick must page immediately, not retry into a hidden
    # backlog — same rationale as the visa-oracle-retention plist.
    assert manifest["EnvironmentVariables"]["CRON_MAX_RETRIES"] == "0"
    assert manifest["EnvironmentVariables"]["VISA_ORACLE_SESSIONS_PURGE_APPLY"] == "false"
    arguments = manifest["ProgramArguments"]
    assert "/Users/nuzantara/nuzantara/scripts/cron-wrapper.sh" in arguments
    assert "visa-oracle-sessions-purge" in arguments


def test_payload_wrapper_is_syntax_valid_and_never_hardcodes_apply() -> None:
    result = subprocess.run(
        ["bash", "-n", str(_WRAPPER_PATH)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    source = _WRAPPER_PATH.read_text(encoding="utf-8")
    assert 'APPLY_MODE="${VISA_ORACLE_SESSIONS_PURGE_APPLY:-false}"' in source
    assert "visa_oracle_sessions_purge_worker --apply" in source
    assert 'exec env PYTHONPATH=. "$PYTHON_BIN"' in source


def test_payload_wrapper_apply_mode_is_explicit(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    backend_root = fake_repo / "apps" / "backend-rag"
    backend_root.mkdir(parents=True)
    captured = tmp_path / "arguments.txt"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" > "$CAPTURED_ARGUMENTS"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o700)

    for apply, expect_apply_flag in (("false", False), ("true", True)):
        environment = os.environ.copy()
        environment.update(
            {
                "CAPTURED_ARGUMENTS": str(captured),
                "NUZANTARA_REPO_ROOT": str(fake_repo),
                "VISA_ORACLE_PYTHON_BIN": str(fake_python),
                "VISA_ORACLE_SESSIONS_PURGE_APPLY": apply,
            }
        )

        result = subprocess.run(
            ["bash", str(_WRAPPER_PATH)],
            cwd=_REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        arguments = captured.read_text(encoding="utf-8").splitlines()
        expected = ["-m", "backend.scripts.visa_engine.visa_oracle_sessions_purge_worker"]
        if expect_apply_flag:
            expected.append("--apply")
        assert arguments == expected


def test_payload_wrapper_rejects_a_non_boolean_apply_value() -> None:
    environment = os.environ.copy()
    environment["VISA_ORACLE_SESSIONS_PURGE_APPLY"] = "yes"

    result = subprocess.run(
        ["bash", str(_WRAPPER_PATH)],
        cwd=_REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 78
    assert "must be exactly true or false" in result.stderr
