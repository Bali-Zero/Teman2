"""Tests for infra/launchagents/wrappers/wa-codex-broker-wrapper.sh's
dedicated-binary pin section (S7, scripts/install_wa_codex_pinned.sh spec
v2) — the round-2 finding on PR #7313: an admin-verb env file the daemon
can write let a `RUNTIME_DIR` reassignment inside the SOURCED daemon env
redirect which pin file got read next, since the pin path used to be built
from that same variable AFTER the source point.

The fix reads the pin from a path that is never built from any variable
the sourced env could touch. These tests prove it by trying the exact
redirection attempt and checking which value actually reaches the daemon
process — not by reading the source and trusting intent (W107/superscar
#2: read proves intent, running proves behaviour).

No real launchd, no real /Users/zantara-codex, no real /usr/local/lib
anywhere — every test copies the wrapper and `sed`-patches its plain path
constants (HOME_DIR, RUNTIME_DIR, VENV_PY, CODEX_PIN_FILE) into a scratch
tree, then substitutes VENV_PY for a stub that just dumps the two pin-
relevant env vars instead of actually execing the daemon.
"""

from __future__ import annotations

import re
import stat
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "wa-codex-broker-wrapper.sh"

_PATCHABLE_KEYS = ("HOME_DIR", "RUNTIME_DIR", "VENV_PY", "CODEX_PIN_FILE")

_DUMP_ENV_STUB = """#!/usr/bin/env python3
import os
print("WA_CODEX_CLI_VERSION_PIN=" + os.environ.get("WA_CODEX_CLI_VERSION_PIN", "<unset>"))
print("WA_CODEX_BIN=" + os.environ.get("WA_CODEX_BIN", "<unset>"))
"""


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _patched_wrapper(tmp_path: Path, **overrides: str) -> Path:
    dst = tmp_path / "wrapper-copy.sh"
    text = _WRAPPER.read_text()
    for key, value in overrides.items():
        assert key in _PATCHABLE_KEYS, f"{key} is not a declared patchable constant"
        pattern = rf'^{key}=.*$'
        replacement = f'{key}="{value}"'
        text, n = re.subn(pattern, replacement, text, count=1, flags=re.M)
        assert n == 1, f"could not patch {key}= in a copy of {_WRAPPER}"
    dst.write_text(text)
    dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dst


@pytest.fixture()
def world(tmp_path: Path) -> dict:
    home = tmp_path / "home"
    (home / ".organism" / "last_seen").mkdir(parents=True)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    stub_py = tmp_path / "dump_env.py"
    _make_executable(stub_py, _DUMP_ENV_STUB)
    return {"home": home, "runtime": runtime, "stub_py": stub_py}


def _write_daemon_env(world: dict, **extra_lines: str) -> Path:
    env_file = world["home"] / ".wa-codex-broker.env"
    lines = [f'{k}={v}' for k, v in extra_lines.items()]
    env_file.write_text("\n".join(lines) + "\n")
    return env_file


def _run(wrapper: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(wrapper)], capture_output=True, text=True, timeout=15, check=False,
    )


def test_innocence_pin_file_overrides_daemon_env(tmp_path: Path, world: dict) -> None:
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    pin_file = tmp_path / "codex-pin.env"
    trusted_bin = "/usr/local/lib/wa-codex-broker/codex/9.9.9/bin/codex"
    pin_file.write_text(f"WA_CODEX_CLI_VERSION_PIN=9.9.9\nWA_CODEX_BIN={trusted_bin}\n")

    wrapper = _patched_wrapper(
        tmp_path, HOME_DIR=str(world["home"]), RUNTIME_DIR=str(world["runtime"]),
        VENV_PY=str(world["stub_py"]), CODEX_PIN_FILE=str(pin_file),
    )
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in result.stdout
    assert f"WA_CODEX_BIN={trusted_bin}" in result.stdout


def test_guilt_daemon_env_cannot_redirect_the_pin_path(tmp_path: Path, world: dict) -> None:
    """The round-2 attack: the daemon-writable env file reassigns
    RUNTIME_DIR, hoping a pin path built from it (after the source point)
    would follow to an attacker-controlled file. The fix never builds the
    pin path from RUNTIME_DIR (or any sourced variable) — the pin actually
    read is the one at the test's literal CODEX_PIN_FILE, not anything
    under the redirected RUNTIME_DIR."""
    evil_runtime = tmp_path / "evil-runtime-the-daemon-pointed-at"
    evil_runtime.mkdir()
    evil_pin = evil_runtime / "codex-pin.env"
    evil_pin.write_text(
        "WA_CODEX_CLI_VERSION_PIN=6.6.6\nWA_CODEX_BIN=/usr/local/lib/wa-codex-broker/codex/6.6.6/bin/codex\n"
    )
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
        RUNTIME_DIR=str(evil_runtime),
    )
    real_pin = tmp_path / "codex-pin.env"
    real_bin = "/usr/local/lib/wa-codex-broker/codex/9.9.9/bin/codex"
    real_pin.write_text(f"WA_CODEX_CLI_VERSION_PIN=9.9.9\nWA_CODEX_BIN={real_bin}\n")

    wrapper = _patched_wrapper(
        tmp_path, HOME_DIR=str(world["home"]), RUNTIME_DIR=str(world["runtime"]),
        VENV_PY=str(world["stub_py"]), CODEX_PIN_FILE=str(real_pin),
    )
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in result.stdout
    assert f"WA_CODEX_BIN={real_bin}" in result.stdout
    assert "6.6.6" not in result.stdout


def test_guilt_bin_path_outside_the_pattern_is_rejected(tmp_path: Path, world: dict) -> None:
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text(
        "WA_CODEX_CLI_VERSION_PIN=9.9.9\nWA_CODEX_BIN=/tmp/evil/codex\n"
    )
    wrapper = _patched_wrapper(
        tmp_path, HOME_DIR=str(world["home"]), RUNTIME_DIR=str(world["runtime"]),
        VENV_PY=str(world["stub_py"]), CODEX_PIN_FILE=str(pin_file),
    )
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    # version pin is well-formed and DOES win...
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in result.stdout
    # ...but the out-of-pattern bin path is refused: the daemon's own
    # (untouched) value survives instead.
    assert "WA_CODEX_BIN=/opt/homebrew/bin/codex" in result.stdout
    assert "/tmp/evil/codex" not in result.stdout


def test_innocence_missing_pin_file_is_legacy_behaviour(tmp_path: Path, world: dict) -> None:
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    missing_pin = tmp_path / "no-such-pin.env"
    wrapper = _patched_wrapper(
        tmp_path, HOME_DIR=str(world["home"]), RUNTIME_DIR=str(world["runtime"]),
        VENV_PY=str(world["stub_py"]), CODEX_PIN_FILE=str(missing_pin),
    )
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=0.0.1" in result.stdout
    assert "WA_CODEX_BIN=/opt/homebrew/bin/codex" in result.stdout


@pytest.mark.parametrize(
    "value,expect_ok",
    [
        ("9.9.9", True),
        ("0.156.1", True),
        ("9.9", False),
        ("9.9.9.9", False),
        ("9.9.9;id", False),
        ("latest", False),
        ("", False),
    ],
)
def test_is_semver_validator(tmp_path: Path, value: str, expect_ok: bool) -> None:
    snippet = tmp_path / "snippet.sh"
    snippet.write_text(
        "_is_semver() {\n"
        "    expr \"$1\" : '[0-9][0-9]*\\.[0-9][0-9]*\\.[0-9][0-9]*$' >/dev/null\n"
        "}\n"
        f'_is_semver "{value}"\n'
    )
    result = subprocess.run(["sh", str(snippet)], capture_output=True, text=True, check=False)
    assert (result.returncode == 0) is expect_ok


@pytest.mark.parametrize(
    "value,expect_ok",
    [
        ("/usr/local/lib/wa-codex-broker/codex/9.9.9/bin/codex", True),
        ("/usr/local/lib/wa-codex-broker/codex/0.156.1/bin/codex", True),
        ("/tmp/evil/codex", False),
        ("/usr/local/lib/wa-codex-broker/codex/9.9.9/bin/codex-evil", False),
        ("/usr/local/lib/wa-codex-broker/codex/../../etc/passwd", False),
        ("relative/bin/codex", False),
    ],
)
def test_is_trusted_bin_path_validator(tmp_path: Path, value: str, expect_ok: bool) -> None:
    snippet = tmp_path / "snippet.sh"
    snippet.write_text(
        "_is_trusted_bin_path() {\n"
        "    expr \"$1\" : '/usr/local/lib/wa-codex-broker/codex/[0-9][0-9]*\\.[0-9][0-9]*\\.[0-9][0-9]*/bin/codex$' >/dev/null\n"
        "}\n"
        f'_is_trusted_bin_path "{value}"\n'
    )
    result = subprocess.run(["sh", str(snippet)], capture_output=True, text=True, check=False)
    assert (result.returncode == 0) is expect_ok
