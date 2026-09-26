"""Tests for infra/launchagents/wrappers/wa-codex-broker-wrapper.sh's D5 pin
section (spec v3, F5) — the wrapper's dedicated codex-version pin, parsed
BEFORE the daemon env is sourced, using ONLY shell builtins (`read`, `case`,
`[`, parameter expansion — no `expr`, no PATH lookup), so nothing the
daemon's own env file can set (a redirected PATH, a shadowed `expr`, an
alias) reaches the pin validators.

Supersedes the wrapper's pin section from the SUSPENDED PR #7340. That
version validated with `expr` (itself PATH-resolved: `expr` lives only at
`/bin/expr` on macOS) AFTER sourcing the daemon env, and a present-but-
invalid pin there silently fell back to legacy behaviour at rc 0 — both
reproduced against the real #7340 head and reported in the PR body rather
than pinned here as a fixture against another ref (main's own wrapper
becomes this v3 wrapper the moment this PR merges, so a "guilt against a
git ref" fixture would test nothing the day after merge).

No real launchd, no real /Users/zantara-codex, no real /usr/local/lib
anywhere — every test copies the SHIPPED wrapper and `sed`-patches its
plain path constants (HOME_DIR, RUNTIME_DIR, VENV_PY, CODEX_PIN_FILE,
PINNED_CODEX_ROOT) into a scratch tree (`_patched_wrapper()` below, the
#7340 mechanism, kept because the shipped file has no env/flag test-mode
branch — D6). VENV_PY is replaced by a stub that dumps the two
pin-relevant env vars instead of execing the real daemon. The stub is a
plain `#!/bin/sh` script, never `#!/usr/bin/env python3` — a python
shebang needs its own PATH lookup at exec time, which would make the F5
regression tests below (daemon env's PATH deliberately poisoned) fail for
a reason that has nothing to do with the wrapper's own pin logic.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "wa-codex-broker-wrapper.sh"

_PATCHABLE_KEYS = ("HOME_DIR", "RUNTIME_DIR", "VENV_PY", "CODEX_PIN_FILE", "PINNED_CODEX_ROOT")

_DUMP_ENV_STUB = """#!/bin/sh
printf 'WA_CODEX_CLI_VERSION_PIN=%s\\n' "${WA_CODEX_CLI_VERSION_PIN:-<unset>}"
printf 'WA_CODEX_BIN=%s\\n' "${WA_CODEX_BIN:-<unset>}"
"""

_FAKE_CODEX_STUB = """#!/bin/sh
echo "codex-cli {version}"
"""


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _patched_wrapper(tmp_path: Path, name: str = "wrapper-copy.sh", **overrides: str) -> Path:
    """Copy the SHIPPED wrapper and sed-rewrite ONLY the named constants'
    assignment lines (anchored `^NAME=`, never a comment mentioning the
    same name) — this tests the shipped predicate text itself, not a copy
    pasted into the test file (D6)."""
    dst = tmp_path / name
    text = _WRAPPER.read_text()
    for key, value in overrides.items():
        assert key in _PATCHABLE_KEYS, f"{key} is not a declared patchable constant"
        pattern = rf"^{key}=.*$"
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
    stub_sh = tmp_path / "dump_env.sh"
    _make_executable(stub_sh, _DUMP_ENV_STUB)
    return {"home": home, "runtime": runtime, "stub_sh": stub_sh, "pinned_root": runtime / "codex"}


def _write_daemon_env(world: dict, **extra_lines: str) -> Path:
    env_file = world["home"] / ".wa-codex-broker.env"
    lines = [f"{k}={v}" for k, v in extra_lines.items()]
    env_file.write_text("\n".join(lines) + "\n")
    return env_file


def _plant_pinned_codex(world: dict, version: str) -> Path:
    bin_path = world["pinned_root"] / version / "bin" / "codex"
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    _make_executable(bin_path, _FAKE_CODEX_STUB.format(version=version))
    return bin_path


def _run(wrapper: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(wrapper)], capture_output=True, text=True, timeout=15, check=False,
    )


def _base_wrapper(tmp_path: Path, world: dict, pin_file: Path) -> Path:
    return _patched_wrapper(
        tmp_path,
        HOME_DIR=str(world["home"]),
        RUNTIME_DIR=str(world["runtime"]),
        VENV_PY=str(world["stub_sh"]),
        CODEX_PIN_FILE=str(pin_file),
        PINNED_CODEX_ROOT=str(world["pinned_root"]),
    )


# --- F5: env PATH cannot disable the pin ------------------------------------

@pytest.mark.parametrize(
    "hostile_path",
    ["/does-not-exist", "/opt/homebrew/bin:/usr/bin"],
    ids=["nonexistent", "homebrew_usr_bin"],
)
def test_guilt_env_path_cannot_disable_the_pin(tmp_path: Path, world: dict, hostile_path: str) -> None:
    """SUSPENDED #7340 finding F5. Reproduced against the real #7340 head
    (see PR body for the transcript, not repeated here as a fixture
    against another git ref): with either PATH value `expr` is not
    reachable (it lives only at /bin/expr on macOS — verified), so
    #7340's `_is_semver`/`_is_trusted_bin_path` — both thin wrappers
    around `expr ... : ...` — silently error out and the daemon gets the
    ENV's WA_CODEX_BIN, rc 0. D5 never calls `expr` and parses the pin
    before the daemon env is even sourced, so the same hostile PATH
    cannot touch it: the pinned values still reach the daemon."""
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
        PATH=hostile_path,
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    pinned_bin = _plant_pinned_codex(world, "9.9.9")

    wrapper = _base_wrapper(tmp_path, world, pin_file)
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in result.stdout
    assert f"WA_CODEX_BIN={pinned_bin}" in result.stdout


# --- F5: a present-but-invalid pin fails closed -----------------------------

def _invalid_pin_case(tmp_path: Path, world: dict, kind: str) -> Path:
    pin_file = tmp_path / "codex-pin.env"
    if kind == "bad_semver":
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9\n")
    elif kind == "unknown_key":
        pin_file.write_text("SOMETHING_ELSE=9.9.9\n")
    elif kind == "two_lines":
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\nWA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    elif kind == "empty":
        pin_file.write_text("")
    elif kind == "bin_missing":
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=1.2.3\n")
        # Deliberately do NOT plant runtime/codex/1.2.3/bin/codex.
    elif kind == "symlink_pin":
        real = tmp_path / "real-pin.env"
        real.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
        _plant_pinned_codex(world, "9.9.9")
        pin_file.symlink_to(real)
    elif kind == "directory":
        pin_file.mkdir()
    elif kind == "dev_null":
        pin_file = Path("/dev/null")
    elif kind == "fifo":
        os.mkfifo(pin_file)
    elif kind == "embedded_nul":
        pin_file.write_bytes(b"WA_CODEX_CLI_VERSION_PIN=9.9.9\n\x00JUNK\n")
    else:
        raise AssertionError(f"unknown case {kind!r}")
    return pin_file


@pytest.mark.parametrize(
    "kind",
    [
        "bad_semver", "unknown_key", "two_lines", "empty", "bin_missing", "symlink_pin",
        "directory", "dev_null", "fifo", "embedded_nul",
    ],
)
def test_guilt_present_but_invalid_pin_refuses(tmp_path: Path, world: dict, kind: str) -> None:
    """#7340's pin parse silently skipped an invalid VALUE and kept going
    with whatever the daemon env already set (rc 0 — reproduced, see PR
    body). D5 fails closed for every one of these ten faults: exit 78
    plus a `refused` / `pin invalid` heartbeat, never a silent legacy
    fallback once something exists at the pin path. `directory`/`dev_null`/
    `fifo` (spalla review 2026-09-26) catch the case where the path exists
    but is not a regular file and not a symlink either — the original
    `-L`/`-f`/else fell through straight into the legacy branch there,
    since `-f` alone cannot distinguish "absent" from "present, wrong
    type". `embedded_nul` (same review) catches a shell variable's
    inability to represent a NUL byte at all: `read -r` alone silently
    truncates a line AT its first NUL, so content after it could slip past
    an exactly-one-line count undetected without the dedicated NUL probe."""
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    pin_file = _invalid_pin_case(tmp_path, world, kind)
    wrapper = _base_wrapper(tmp_path, world, pin_file)
    result = _run(wrapper)
    assert result.returncode == 78, (result.returncode, result.stdout, result.stderr)
    heartbeat_file = world["home"] / ".organism" / "last_seen" / "pro.wa_codex_broker.json"
    hb = heartbeat_file.read_text()
    assert '"status":"refused"' in hb, hb
    assert '"note":"pin invalid"' in hb, hb


def test_guilt_daemon_env_cannot_clobber_the_resolved_pin(tmp_path: Path, world: dict) -> None:
    """Spalla review 2026-09-26: a plain DATA assignment in the daemon env
    — no alias, no function, nothing that needs code execution to work —
    used to reach the resolved pin's shell variables across the
    `. "$ENV_FILE"` source, because `set -a` exports whatever NAME the env
    file assigns and the wrapper's first draft carried the resolved pin in
    ordinary named variables (`PIN_VER`/`PIN_BIN`). The fix carries the
    resolved pin as POSITIONAL PARAMETERS ($1/$2, set via `set --` right
    before the source) instead: a `KEY=value` env-file line cannot touch
    $1/$2 at all, named collision or not. This tries the collision on
    BOTH the retired names and a generic unrelated one, confirming the
    pinned values still reach the daemon regardless."""
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
        PIN_VER="",
        PIN_BIN="/opt/homebrew/bin/codex",
        _wcbw_pin_ver="",
        _wcbw_pin_bin="/opt/homebrew/bin/codex",
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    pinned_bin = _plant_pinned_codex(world, "9.9.9")

    wrapper = _base_wrapper(tmp_path, world, pin_file)
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in result.stdout
    assert f"WA_CODEX_BIN={pinned_bin}" in result.stdout


# --- innocence ---------------------------------------------------------------

def test_innocence_valid_pin_overrides_env(tmp_path: Path, world: dict) -> None:
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    pinned_bin = _plant_pinned_codex(world, "9.9.9")

    wrapper = _base_wrapper(tmp_path, world, pin_file)
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in result.stdout
    assert f"WA_CODEX_BIN={pinned_bin}" in result.stdout


def test_innocence_missing_pin_is_legacy(tmp_path: Path, world: dict) -> None:
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    missing_pin = tmp_path / "no-such-pin.env"
    wrapper = _base_wrapper(tmp_path, world, missing_pin)
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=0.0.1" in result.stdout
    assert "WA_CODEX_BIN=/opt/homebrew/bin/codex" in result.stdout
    assert f"no pin file at {missing_pin}" in result.stderr
    assert "legacy" in result.stderr


# --- spec §6 live-proof line ---------------------------------------------------

def test_pin_applied_log_line(tmp_path: Path, world: dict) -> None:
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    pinned_bin = _plant_pinned_codex(world, "9.9.9")

    wrapper = _base_wrapper(tmp_path, world, pin_file)
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    pattern = r"wa-codex-broker-wrapper: \S+ pin applied: codex 9\.9\.9 at " + re.escape(str(pinned_bin))
    assert re.search(pattern, result.stderr), result.stderr


# --- N3: protocol line ---------------------------------------------------------

def test_wrapper_declares_pin_protocol_line() -> None:
    text = _WRAPPER.read_text()
    matches = [line for line in text.splitlines() if line.strip() == "# pin-protocol: wa-codex-pin/1"]
    assert len(matches) == 1, matches
