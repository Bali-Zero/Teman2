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
        # count=0 (all occurrences): N1 (gate 2026-09-26) re-asserts
        # HOME_DIR/RUNTIME_DIR/VENV_PY a second time after `set +a`, so a
        # patched copy must rewrite BOTH declarations or the test would
        # silently exercise the wrapper's real production paths post-source.
        text, n = re.subn(pattern, replacement, text, count=0, flags=re.M)
        assert n >= 1, f"could not patch {key}= in a copy of {_WRAPPER}"
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
    # N2 (gate 2026-09-26): explicit `/bin/sh`, never a PATH-resolved `sh`
    # — the NUL-probe's `read -d ''` is a bash extension dash rejects, and
    # macOS's own `/bin/sh` IS bash 3.2 (the wrapper's only two real
    # runtimes: this, and macos-latest CI's bash), so this must never
    # silently resolve to a dash on some other PATH.
    return subprocess.run(
        ["/bin/sh", str(wrapper)], capture_output=True, text=True, timeout=15, check=False,
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
    elif kind == "nul_same_line_planted":
        # C1 (gate 2026-09-26): the existing `embedded_nul` case puts the
        # NUL on its OWN line (a `\n` before it), so the exactly-one-line
        # check alone already rejects it — non-discriminating for the NUL
        # probe specifically. This one is genuinely ONE line (a single
        # trailing newline, NUL mid-content) WITH the binary planted, so
        # removing only the NUL probe is provably what flips the verdict
        # (mutation-verified below, not merely asserted).
        pin_file.write_bytes(b"WA_CODEX_CLI_VERSION_PIN=9.9.9\x00JUNK\n")
        _plant_pinned_codex(world, "9.9.9")
    elif kind == "two_lines_diff_versions_planted":
        # The existing `two_lines` case repeats the SAME version on both
        # lines, so removing the line-count guard cannot be told apart
        # from keeping it (either way the resolved version is 9.9.9).
        # Different versions, BOTH planted, make the guard's effect
        # observable: with it, exit 78; without it, the read loop's last
        # line wins and 9.9.9 gets silently applied.
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=1.1.1\nWA_CODEX_CLI_VERSION_PIN=9.9.9\n")
        _plant_pinned_codex(world, "1.1.1")
        _plant_pinned_codex(world, "9.9.9")
    elif kind == "bad_semver_planted":
        # The existing `bad_semver` case never plants a binary, so
        # removing `_is_semver` alone would still fail closed at the
        # binary-existence check instead — masking the guard under test.
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9\n")
        _plant_pinned_codex(world, "9.9")
    elif kind == "traversal_escape_planted":
        # `_is_semver` is the ONLY guard keeping the derived binary path
        # under PINNED_CODEX_ROOT at all — nothing canonicalizes
        # `$PINNED_CODEX_ROOT/$ver/bin/codex` before the `-f`/`-x` check.
        # Planted one level ABOVE pinned_root (a sibling "escape" dir) so
        # that, without the semver guard, the derived path would resolve
        # there and be accepted.
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=../escape\n")
        # `codex/..` only resolves through a REAL `codex` directory — the
        # kernel cannot walk `..` past a path component that does not
        # exist on disk, even though the final target one level up does.
        world["pinned_root"].mkdir(parents=True, exist_ok=True)
        escape_bin = world["pinned_root"].parent / "escape" / "bin" / "codex"
        escape_bin.parent.mkdir(parents=True, exist_ok=True)
        _make_executable(escape_bin, _FAKE_CODEX_STUB.format(version="../escape"))
    elif kind == "bin_is_directory":
        # C2 (gate 2026-09-26): a directory at the derived binary path is
        # traversable (`-x` on a 0755 dir is true), so the OLD `-x`-only
        # check silently APPLIED it. A valid pin, a valid version — only
        # the binary itself is wrong.
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
        bin_path = world["pinned_root"] / "9.9.9" / "bin" / "codex"
        bin_path.mkdir(parents=True)
        bin_path.chmod(0o755)
    elif kind == "bare_version_planted":
        # R3 (fresh re-gate, 2026-09-27, 2nd occurrence of the fixture-
        # masking class): the `case "$_pin_line" in
        # WA_CODEX_CLI_VERSION_PIN=*)` guard is the ONLY thing requiring
        # the key prefix at all. `unknown_key` (SOMETHING_ELSE=9.9.9) does
        # NOT isolate it: with the case guard deleted (accept any line,
        # `_wcbw_pin_ver="${_pin_line#WA_CODEX_CLI_VERSION_PIN=}"`
        # unconditional), "SOMETHING_ELSE=9.9.9" still fails `_is_semver`
        # on its `=`/`_` characters either way, so that mutant stayed
        # GREEN. A bare, keyless line that is ALREADY a valid semver, with
        # the tree planted, is the one input whose acceptance the case
        # guard alone decides: with the guard, the missing prefix makes it
        # "unrecognized" (78); without it, the unchanged line parses as a
        # valid version and the planted binary lets it through (0).
        pin_file.write_text("9.9.9\n")
        _plant_pinned_codex(world, "9.9.9")
    elif kind == "bin_not_executable_planted":
        # R3 (fresh re-gate, 2026-09-27): `bin_is_directory` above isolates
        # the `-f` half of `[ -f ] && [ -x ]` (a directory fails -f, but a
        # mode-0755 directory still passes -x, which is the ORIGINAL C2
        # defect). Neither existing fixture isolates the `-x` half:
        # `bin_missing` fails BOTH -f and -x (nothing exists), so reverting
        # to `-f`-only would still correctly refuse it. A REGULAR, 0644,
        # non-executable file at the derived path passes -f but must still
        # be refused — only the `-x` half decides this one.
        pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
        bin_path = world["pinned_root"] / "9.9.9" / "bin" / "codex"
        bin_path.parent.mkdir(parents=True, exist_ok=True)
        bin_path.write_text(_FAKE_CODEX_STUB.format(version="9.9.9"))
        bin_path.chmod(0o644)
    else:
        raise AssertionError(f"unknown case {kind!r}")
    return pin_file


@pytest.mark.parametrize(
    "kind",
    [
        "bad_semver", "unknown_key", "two_lines", "empty", "bin_missing", "symlink_pin",
        "directory", "dev_null", "fifo", "embedded_nul",
        "nul_same_line_planted", "two_lines_diff_versions_planted", "bad_semver_planted",
        "traversal_escape_planted", "bin_is_directory",
        "bare_version_planted", "bin_not_executable_planted",
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


def test_guilt_unsearchable_runtime_dir_refuses_not_legacy(tmp_path: Path, world: dict) -> None:
    """C3 (gate 2026-09-26, corrected per the delta-council catch: the
    first version of this test broke RUNTIME_DIR's mode while the pin file
    lived OUTSIDE it — siblings, not container/contents — so `[ -e
    "$CODEX_PIN_FILE" ]` was never actually blocked by the broken mode; the
    test only proved the new top-level guard fires, not the real defect).
    The pin file now lives INSIDE RUNTIME_DIR: `[ -e "$CODEX_PIN_FILE" ]`
    cannot traverse an unsearchable RUNTIME_DIR to even STAT it, so a pin
    file that genuinely exists behind a broken directory mode used to read
    as "no pin file here" and fall into legacy (rc 0, whatever the env's
    WA_CODEX_BIN says) — reproduced live on Pro's own layout (gate's
    eacces.py E1/E2). RUNTIME_DIR EXISTS here (unlike a fresh,
    never-provisioned machine) but is not other-traversable, which is a
    broken/obstructed state, never legitimate absence."""
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    pin_file = world["runtime"] / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    _plant_pinned_codex(world, "9.9.9")
    wrapper = _base_wrapper(tmp_path, world, pin_file)
    world["runtime"].chmod(0o644)
    try:
        result = _run(wrapper)
    finally:
        world["runtime"].chmod(0o755)
    assert result.returncode == 78, (result.returncode, result.stdout, result.stderr)
    assert "not searchable" in result.stderr, result.stderr
    heartbeat_file = world["home"] / ".organism" / "last_seen" / "pro.wa_codex_broker.json"
    hb = heartbeat_file.read_text()
    assert '"status":"refused"' in hb, hb
    assert '"note":"pin invalid"' in hb, hb


def test_guilt_invalid_pin_beats_the_kill_switch(tmp_path: Path, world: dict) -> None:
    """N3 (gate 2026-09-26): pin validation happens strictly BEFORE the
    daemon env is even sourced, so an invalid pin must refuse (exit 78)
    even when that same env also sets the kill switch — the kill switch
    is checked only after `set +a`, which an invalid pin never reaches."""
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="false",
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9\n")  # bad_semver, no binary planted
    wrapper = _base_wrapper(tmp_path, world, pin_file)
    result = _run(wrapper)
    assert result.returncode == 78, (result.returncode, result.stdout, result.stderr)
    heartbeat_file = world["home"] / ".organism" / "last_seen" / "pro.wa_codex_broker.json"
    hb = heartbeat_file.read_text()
    assert '"status":"refused"' in hb, hb
    assert '"note":"pin invalid"' in hb, hb


def test_guilt_env_cannot_clobber_post_source_literals(tmp_path: Path, world: dict) -> None:
    """N1 (gate 2026-09-26, dedicated regression requested by the delta
    council — the existing clobber test only tries the pin's OWN
    variables). A plain DATA assignment in the daemon env, exported by
    `set -a`, would otherwise redefine RUNTIME_DIR/VENV_PY/TAG for the
    REST of the script (the cd target, the exec target, and the §6
    proof-line prefix) after the source. The re-assert right after
    `set +a` must win: the daemon still execs the wrapper's OWN (here,
    test-patched) VENV_PY/RUNTIME_DIR, and the proof line still carries
    the real TAG, never the env's.

    Round 2 (codex-gpt-5.6-sol delta, 2026-09-27): the original version of
    this test only clobbered 3 of the 6 wrapper-private literals the N1
    block re-asserts (RUNTIME_DIR/VENV_PY/TAG), never HOME_DIR/ORGAN_ID/
    SIDECAR_DIR, and never looked at the heartbeat file at all — proven by
    a live mutation that dropped the HOME_DIR/ORGAN_ID/SIDECAR_DIR lines
    from the wrapper's re-assert block while this test stayed green. Now
    all six are clobbered, and the heartbeat is asserted to land at the
    wrapper's OWN (test-patched) HOME_DIR/ORGAN_ID path, never the
    hostile one.

    Round 3 (fresh re-gate, 2026-09-27): dropped two vacuous asserts this
    test carried — `not (tmp_path / "nonexistent-evil-sidecar").exists()`
    checked a path the absolute hostile SIDECAR_DIR can never reach (it is
    not rooted at tmp_path at all), and `not Path("/nonexistent-evil-home"
    ).exists()` cannot fail for a non-root runner on the sealed root
    volume regardless of what the wrapper does. Neither added
    discriminating power beyond `heartbeat_path.is_file()` plus its
    content assertions below, which is what actually proves the hostile
    HOME_DIR/ORGAN_ID/SIDECAR_DIR values were never used."""
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
        RUNTIME_DIR="/nonexistent-evil-runtime",
        VENV_PY="/nonexistent-evil-venv",
        TAG="stale-tag",
        HOME_DIR="/nonexistent-evil-home",
        ORGAN_ID="evil.organ",
        SIDECAR_DIR="/nonexistent-evil-sidecar",
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    pinned_bin = _plant_pinned_codex(world, "9.9.9")

    wrapper = _base_wrapper(tmp_path, world, pin_file)
    result = _run(wrapper)
    assert result.returncode == 0, result.stderr
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in result.stdout
    assert f"WA_CODEX_BIN={pinned_bin}" in result.stdout
    assert "wa-codex-broker-wrapper: " in result.stderr
    assert "stale-tag:" not in result.stderr
    assert "evil" not in result.stderr

    heartbeat_path = world["home"] / ".organism" / "last_seen" / "pro.wa_codex_broker.json"
    assert heartbeat_path.is_file(), (
        "heartbeat must land at the wrapper's OWN HOME_DIR/ORGAN_ID, "
        f"not the hostile one; not found at {heartbeat_path}"
    )
    heartbeat_body = heartbeat_path.read_text()
    assert '"status":"starting"' in heartbeat_body
    assert '"note":"exec daemon"' in heartbeat_body


def test_guilt_mode_000_pin_reports_unreadable_not_line_count(tmp_path: Path, world: dict) -> None:
    """N4 (gate 2026-09-26): before this fix, a pin file with permission
    bits 0000 misreported "must carry exactly one line" — the read loop
    silently sees zero lines under EACCES, which happens to also be a
    truthy `_pin_lines -ne 1`, but the wrong DIAGNOSIS. A dedicated
    `[ -r ]` check names the real cause."""
    _write_daemon_env(
        world,
        WA_CODEX_CLI_VERSION_PIN="0.0.1",
        WA_CODEX_BIN="/opt/homebrew/bin/codex",
        WA_CODEX_BROKER_ENABLED="true",
    )
    pin_file = tmp_path / "codex-pin.env"
    pin_file.write_text("WA_CODEX_CLI_VERSION_PIN=9.9.9\n")
    pin_file.chmod(0o000)
    try:
        wrapper = _base_wrapper(tmp_path, world, pin_file)
        result = _run(wrapper)
    finally:
        pin_file.chmod(0o644)
    assert result.returncode == 78, (result.returncode, result.stdout, result.stderr)
    assert "not readable" in result.stderr, result.stderr
    assert "must carry exactly one line" not in result.stderr


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
    # N5 (gate 2026-09-26): `\S+` accepted anything for the timestamp;
    # tightened to the `date -u +%Y-%m-%dT%H:%M:%SZ` shape the wrapper
    # actually emits.
    pattern = (
        r"wa-codex-broker-wrapper: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z pin applied: codex 9\.9\.9 at "
        + re.escape(str(pinned_bin))
    )
    assert re.search(pattern, result.stderr), result.stderr


# --- N3: protocol line ---------------------------------------------------------

def test_wrapper_declares_pin_protocol_line() -> None:
    text = _WRAPPER.read_text()
    matches = [line for line in text.splitlines() if line.strip() == "# pin-protocol: wa-codex-pin/1"]
    assert len(matches) == 1, matches
