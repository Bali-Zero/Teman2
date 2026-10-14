"""Unit tests for the parsers and runner in scripts/ci/observe_visa_check_catalogue_e33.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

import observe_visa_check_catalogue_e33 as obs  # noqa: E402
from observe_visa_check_catalogue_e33 import (  # noqa: E402
    MIN_TESTS,
    REQUIRED_TESTS,
    required_names_ok,
    summary_ok,
)


@pytest.mark.parametrize(
    "line",
    [
        f"========== {MIN_TESTS - 1} passed in 0.02s ==========",
        f"========== {MIN_TESTS} skipped in 0.02s ==========",
        f"========== {MIN_TESTS - 2} passed in 0.02s ==========",
        "========== 5 passed in 0.02s ==========",
        f"========== 1 failed, {MIN_TESTS} passed in 0.02s ==========",
        f"========== {MIN_TESTS} passed, 1 skipped in 0.02s ==========",
        f"========== {MIN_TESTS} passed, 1 error in 0.02s ==========",
        f"========== {MIN_TESTS} passed, 1 xfailed in 0.02s ==========",
        f"========== {MIN_TESTS} passed, 2 deselected in 0.02s ==========",
        f"{MIN_TESTS} passed, 1 skipped in 0.02s",
        "",
        None,
    ],
)
def test_summary_rejects_anything_but_a_full_pass(line):
    assert summary_ok(line) is False


@pytest.mark.parametrize(
    "line",
    [
        f"========== {MIN_TESTS} passed in 0.02s ==========",
        f"========== {MIN_TESTS + 1} passed in 1.20s (0:00:01) ==========",
        f"========== {MIN_TESTS} passed, 1 warning in 0.02s ==========",
        f"{MIN_TESTS} passed in 0.04s",
    ],
)
def test_summary_accepts_full_pass_at_or_above_floor(line):
    assert summary_ok(line) is True


def test_required_names_accepts_ra_short_test_summary_output():
    lines = [
        f"PASSED backend/tests/services/visa_check/test_file.py::{name}"
        for name in REQUIRED_TESTS
    ]
    output = "\n".join(
        ["=== short test summary info ===", *lines, f"{MIN_TESTS} passed in 0.12s"]
    )
    assert required_names_ok(output) is True


def test_required_names_accepts_verbose_output():
    lines = [
        f"backend/tests/services/visa_check/test_file.py::{name} PASSED [100%]"
        for name in REQUIRED_TESTS
    ]
    assert required_names_ok("\n".join(lines)) is True


def test_required_names_rejects_missing_or_non_passed_test():
    for missing in REQUIRED_TESTS:
        partial = "\n".join(
            f"PASSED backend/tests/services/visa_check/test_file.py::{name}"
            for name in REQUIRED_TESTS
            if name != missing
        )
        assert required_names_ok(partial) is False

        failed = "\n".join(
            f"{'FAILED' if name == missing else 'PASSED'} "
            f"backend/tests/services/visa_check/test_file.py::{name}"
            for name in REQUIRED_TESTS
        )
        assert required_names_ok(failed) is False

    assert required_names_ok("") is False
    assert required_names_ok(None) is False


def test_main_succeeds_when_all_required_tests_and_summary_pass(monkeypatch, capsys):
    seen: dict[str, object] = {}
    passed_lines = [
        f"PASSED backend/tests/services/visa_check/test_file.py::{name}"
        for name in REQUIRED_TESTS
    ]
    stdout = "\n".join([*passed_lines, f"{MIN_TESTS} passed in 0.1s"])

    def fake(cmd, **kwargs):
        seen["cmd"] = cmd
        seen.update(kwargs)
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=stdout, stderr=""
        )

    monkeypatch.setattr(obs.subprocess, "run", fake)
    assert obs.main() == 0
    assert seen["cwd"] == obs.BACKEND_DIR
    assert seen["env"] == {"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"}
    assert seen["timeout"] == obs.TIMEOUT_SECONDS
    cmd = seen["cmd"]
    assert isinstance(cmd, list)
    assert "-m" in cmd and "pytest" in cmd
    assert "E33 and E33G catalogue notes hold" in capsys.readouterr().out


def test_main_returns_nonzero_on_pytest_failure(monkeypatch, capsys):
    passed_lines = [
        f"PASSED backend/tests/services/visa_check/test_file.py::{name}"
        for name in REQUIRED_TESTS
    ]
    stdout = "\n".join([*passed_lines, f"1 failed, {MIN_TESTS} passed in 0.1s"])

    def fake(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout=stdout, stderr=""
        )

    monkeypatch.setattr(obs.subprocess, "run", fake)
    assert obs.main() != 0
    assert "FAILED" in capsys.readouterr().out


def test_main_returns_one_on_timeout(monkeypatch, capsys):
    def fake(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(obs.subprocess, "run", fake)
    assert obs.main() == 1
    assert "timeout" in capsys.readouterr().out


def test_main_returns_nonzero_when_summary_passes_but_required_names_missing(
    monkeypatch, capsys
):
    stdout = f"{MIN_TESTS} passed in 0.1s\n"

    def fake(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=stdout, stderr=""
        )

    monkeypatch.setattr(obs.subprocess, "run", fake)
    assert obs.main() != 0
    assert "FAILED" in capsys.readouterr().out
