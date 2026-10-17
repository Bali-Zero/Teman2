"""Regression coverage for the remote zsh preflight expansion hazard."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import harness_fable_gate  # noqa: E402


OLD_PREFLIGHT = (
    'M="$MERGER_STATE_DIR/repo.git"; R=refs/merger/wrapper; '
    'git -C "$M" cat-file -e "$R:scripts/localci/gate_ledger.py"'
)


def _zsh() -> str:
    zsh = os.environ.get("ZSH_BIN") or shutil.which("zsh")
    if zsh and Path(zsh).is_file():
        return zsh
    message = "zsh is not installed"
    if os.environ.get("REQUIRE_ZSH") == "1":
        pytest.fail(message)
    pytest.skip(message)


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def merger_repo(tmp_path: Path) -> tuple[Path, str, str]:
    work = tmp_path / "work"
    work.mkdir()
    _git("init", "-q", cwd=work)
    _git("config", "user.name", "test", cwd=work)
    _git("config", "user.email", "test@example.invalid", cwd=work)
    (work / "scripts/localci").mkdir(parents=True)
    (work / "scripts/localci/other.py").write_text("x\n")
    _git("add", ".", cwd=work)
    _git("commit", "-qm", "without ledger", cwd=work)
    without_ledger = _git("rev-parse", "HEAD", cwd=work)
    (work / "scripts/localci/gate_ledger.py").write_text("x\n")
    _git("add", ".", cwd=work)
    _git("commit", "-qm", "with ledger", cwd=work)
    with_ledger = _git("rev-parse", "HEAD", cwd=work)
    bare = tmp_path / "repo.git"
    _git("clone", "-q", "--bare", str(work), str(bare))
    _git("update-ref", "refs/merger/wrapper", with_ledger, cwd=bare)
    return bare, with_ledger, without_ledger


def _run(shell: str, script: str, state_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ | {
        "MERGER_STATE_DIR": str(state_dir),
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    return subprocess.run(
        [shell, "-c", script], env=env, capture_output=True, text=True
    )


@pytest.mark.parametrize("shell", ["/bin/bash", "zsh"])
def test_preflight_is_shell_agnostic(
    shell: str, tmp_path: Path, merger_repo: tuple[Path, str, str]
):
    bare, with_ledger, without_ledger = merger_repo
    wrapper = tmp_path / "wrapper"
    wrapper.write_text("#!/bin/sh\n# gate-append\n")
    script = harness_fable_gate.PREFLIGHT.format(w=wrapper)

    shell = _zsh() if shell == "zsh" else shell
    assert _run(shell, script, tmp_path).returncode == 0
    _git("update-ref", "refs/merger/wrapper", without_ledger, cwd=bare)
    assert _run(shell, script, tmp_path).returncode == 11
    wrapper.write_text("#!/bin/sh\n")
    assert _run(shell, script, tmp_path).returncode == 10


def test_old_unbraced_ref_expansion_fails_under_zsh(
    tmp_path: Path, merger_repo: tuple[Path, str, str]
):
    _, _, _ = merger_repo
    assert _run(_zsh(), OLD_PREFLIGHT, tmp_path).returncode != 0


def test_old_unbraced_ref_expansion_passes_under_bash(
    tmp_path: Path, merger_repo: tuple[Path, str, str]
):
    _, _, _ = merger_repo
    assert _run("/bin/bash", OLD_PREFLIGHT, tmp_path).returncode == 0
