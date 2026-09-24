"""Tests per scripts/install_wa_codex_admin.sh — D7 (round 1 after PR
#7313's security BLOCK): the installer rejects ANY argument before
anything else runs, and only reaches the (also hard, unconditional) root
check on a clean zero-arg invocation. Both refusals happen BEFORE the
script ever touches `/usr/local/libexec` or `/etc/sudoers.d` — real system
paths, hardcoded, on purpose (this script's whole job is to write there as
root) — so these tests are safe to run for real, un-privileged, as long as
they never get past that first gate. No sed-patched copy needed here: the
argv check and the root check are both pure, no-I/O, first things the
script does.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INSTALLER = _REPO_ROOT / "scripts" / "install_wa_codex_admin.sh"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(_INSTALLER), *args],
        capture_output=True, text=True, timeout=30, check=False,
    )


@pytest.mark.parametrize("args", [["--help"], ["-h"], ["bump"], ["anything"], ["a", "b"]])
def test_guilt_any_argument_is_refused_before_any_effect(args: list[str]) -> None:
    result = _run(args)
    assert result.returncode != 0
    assert "takes no arguments" in result.stderr


def test_guilt_zero_args_as_non_root_refuses_before_any_write() -> None:
    # This process is never root in CI/sandbox — assert the script agrees
    # and refuses at the root check, the very next gate after the (passed)
    # argv check, before any `install`/`_atomic_install` call.
    result = _run([])
    assert result.returncode != 0
    assert "must run as root" in result.stderr
