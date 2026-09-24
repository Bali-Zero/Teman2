"""Tests per infra/launchagents/wrappers/wa-codex-broker-wrapper.sh's D2
change (round 1 after PR #7313's security BLOCK): the daemon's own env
file (`.wa-codex-broker.env`, zantara-codex-writable) is sourced FIRST,
then the NEW root-owned `codex-pin.env` is sourced AFTER it, so the
root-owned values WIN for WA_CODEX_CLI_VERSION_PIN and WA_CODEX_BIN. The
wrapper's job is otherwise unchanged (guards, kill switch, exec) so this
file only pins the ONE thing that changed: sourcing order and precedence.

Technique: copy the wrapper, sed-rewrite HOME_DIR/RUNTIME_DIR into a
scratch tree, and replace the final `exec "$VENV_PY" -m backend...` line
with `exec /usr/bin/env` — the wrapper's own guards (env file present,
not __FILL_ME__, kill switch off, venv python executable) all still run
for real against scratch fixtures; only the actual daemon launch is
swapped for a command that dumps the resulting environment to stdout, so
the test can assert on precedence without a real venv/daemon.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER_SRC = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "wa-codex-broker-wrapper.sh"

_EXEC_LINE = 'exec "$VENV_PY" -m backend.services.integrations.wa_codex_daemon'


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture()
def scratch_wrapper(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Returns (wrapper copy, HOME_DIR, RUNTIME_DIR)."""
    home_dir = tmp_path / "home"
    runtime_dir = tmp_path / "runtime"
    (home_dir / ".organism" / "last_seen").mkdir(parents=True)
    venv_bin = runtime_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    _make_executable(venv_bin / "python3", "#!/bin/bash\necho should-never-run\n")

    text = _WRAPPER_SRC.read_text()
    text = text.replace('HOME_DIR="/Users/zantara-codex"', f'HOME_DIR="{home_dir}"')
    text = text.replace('RUNTIME_DIR="/usr/local/lib/wa-codex-broker"', f'RUNTIME_DIR="{runtime_dir}"')
    assert _EXEC_LINE in text, "the exec line moved — update this test's replacement target"
    text = text.replace(_EXEC_LINE, "exec /usr/bin/env")
    dst = tmp_path / "wrapper-copy.sh"
    _make_executable(dst, text)
    return dst, home_dir, runtime_dir


def _daemon_env_file(home_dir: Path, extra: str = "") -> None:
    (home_dir / ".wa-codex-broker.env").write_text(
        "WA_BROKER_KEY=fake-test-key\n"
        "WA_CODEX_CLI_VERSION_PIN=0.147.0\n"
        "WA_CODEX_BROKER_ENABLED=true\n"
        f"{extra}"
    )


def _run(wrapper: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(wrapper)], capture_output=True, text=True, timeout=15, check=False,
    )


def test_innocence_codex_pin_env_overrides_the_daemon_env_file(
    scratch_wrapper: tuple[Path, Path, Path],
) -> None:
    wrapper, home_dir, runtime_dir = scratch_wrapper
    _daemon_env_file(home_dir, extra="WA_CODEX_BIN=/old/shared/codex\n")
    (runtime_dir / "codex-pin.env").write_text(
        "WA_CODEX_CLI_VERSION_PIN=0.156.1\n"
        f"WA_CODEX_BIN={runtime_dir}/codex/0.156.1/bin/codex\n"
    )
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=0.156.1" in result.stdout
    assert f"WA_CODEX_BIN={runtime_dir}/codex/0.156.1/bin/codex" in result.stdout
    assert "WA_CODEX_CLI_VERSION_PIN=0.147.0" not in result.stdout
    assert "WA_CODEX_BIN=/old/shared/codex" not in result.stdout


def test_innocence_missing_codex_pin_env_keeps_the_legacy_daemon_values(
    scratch_wrapper: tuple[Path, Path, Path],
) -> None:
    wrapper, home_dir, runtime_dir = scratch_wrapper
    _daemon_env_file(home_dir, extra="WA_CODEX_BIN=/old/shared/codex\n")
    assert not (runtime_dir / "codex-pin.env").exists()
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=0.147.0" in result.stdout
    assert "WA_CODEX_BIN=/old/shared/codex" in result.stdout
