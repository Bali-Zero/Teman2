"""Tests per infra/launchagents/wrappers/wa-codex-broker-admin.sh.

W136 cure: la daemon della WA codex broker (Pro) va in pausa quando
`codex --version` non combacia con `WA_CODEX_CLI_VERSION_PIN`, e finora la
cura richiedeva una sudo interattiva. Questo script aggiunge i verbi
`status`/`bump <semver>`, passwordless via sudoers, che spostano la daemon
sul SUO binario dedicato — MAI sul pacchetto Homebrew condiviso che altri
seat aggiornano.

Ogni claim ha il suo test di COLPEVOLEZZA e il suo di INNOCENZA: un
validatore d'argomenti senza il primo e un guardiano decorativo (accetta
tutto), senza il secondo un allarme che urla su input legittimo. Qui la
colpevolezza e "l'argomento e rifiutato E NULLA e stato eseguito" — non
basta un exit code non zero, serve la prova che curl non e mai partito e
che l'albero /usr/local scratch resta intonso.

MAI eseguito come root, MAI tocca /usr/local, /etc o /Library/LaunchDaemons
veri, MAI invoca un launchctl vero: ogni test passa
WA_CODEX_ADMIN_TEST_MODE=1 + WA_CODEX_ADMIN_ROOT_PREFIX=<scratch dir> (il
carve-out che lo script onora SOLO in quella modalita) e antepone alla PATH
una directory con curl/launchctl finti — il curl finto logga i suoi argv e
esce sempre non-zero, cosi il flusso non arriva mai a un vero download, a
tar/openssl su un file reale, o a un vero `launchctl kickstart`.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ADMIN_SCRIPT = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "wa-codex-broker-admin.sh"

_ENV_FILE_CONTENT = """\
WA_BROKER_BASE_URL=https://nuzantara-rag.fly.dev
WA_BROKER_KEY=fake-test-key-not-real
WA_CODEX_CLI_VERSION_PIN=0.147.0
WA_CODEX_MODEL=gpt-5.6-terra
CODEX_HOME=/Users/zantara-codex/.codex
WA_CODEX_BROKER_ENABLED=true
"""

_CURL_STUB = """#!/bin/bash
echo "$@" >> "$WA_STUB_CURL_LOG"
exit 42
"""

_LAUNCHCTL_STUB = """#!/bin/bash
echo "$@" >> "$WA_STUB_LAUNCHCTL_LOG"
exit 1
"""


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture()
def scratch(tmp_path: Path) -> Path:
    root = tmp_path / "root-prefix"
    home = root / "Users" / "zantara-codex"
    home.mkdir(parents=True)
    (home / ".wa-codex-broker.env").write_text(_ENV_FILE_CONTENT)
    (root / "usr" / "local" / "lib" / "wa-codex-broker").mkdir(parents=True)
    return root


@pytest.fixture()
def stub_bin(tmp_path: Path) -> Path:
    bindir = tmp_path / "stubbin"
    bindir.mkdir()
    _make_executable(bindir / "curl", _CURL_STUB)
    _make_executable(bindir / "launchctl", _LAUNCHCTL_STUB)
    return bindir


def _run(
    args: list[str],
    scratch: Path,
    stub_bin: Path,
    tmp_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WA_CODEX_ADMIN_TEST_MODE"] = "1"
    env["WA_CODEX_ADMIN_ROOT_PREFIX"] = str(scratch)
    env["PATH"] = f"{stub_bin}:{env.get('PATH', '')}"
    env["WA_STUB_CURL_LOG"] = str(tmp_path / "curl.log")
    env["WA_STUB_LAUNCHCTL_LOG"] = str(tmp_path / "launchctl.log")
    return subprocess.run(
        ["bash", str(_ADMIN_SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _env_file(scratch: Path) -> str:
    return (scratch / "Users" / "zantara-codex" / ".wa-codex-broker.env").read_text()


def _assert_nothing_executed(result: subprocess.CompletedProcess[str], scratch: Path, tmp_path: Path) -> None:
    assert result.returncode != 0
    assert not (tmp_path / "curl.log").exists(), "curl must never be invoked when validation refuses"
    assert not (tmp_path / "launchctl.log").exists(), "launchctl must never be invoked when validation refuses"
    assert not (scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex").exists()
    assert _env_file(scratch) == _ENV_FILE_CONTENT, "the env file must be byte-identical — nothing rewritten"


# --- guilt: bad `bump` argument -> refused, nothing executed ---------------


def test_guilt_bump_two_part_version_is_refused(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run(["bump", "1.2"], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)
    assert "invalid version" in result.stderr


def test_guilt_bump_semicolon_injection_is_refused(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run(["bump", "1.2.3;id"], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)
    assert "invalid version" in result.stderr


def test_guilt_bump_path_traversal_is_refused(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run(["bump", "../x"], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)
    assert "invalid version" in result.stderr


def test_guilt_bump_extra_argument_is_refused(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run(["bump", "1.2.3", "extra"], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)
    assert "exactly one argument" in result.stderr


def test_guilt_bump_with_no_argument_is_refused(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run(["bump"], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)


def test_guilt_unknown_verb_is_refused(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run(["frobnicate"], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)
    assert "unknown verb" in result.stderr


def test_guilt_no_verb_at_all_is_refused(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run([], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)


def test_guilt_status_rejects_extra_arguments(scratch: Path, stub_bin: Path, tmp_path: Path) -> None:
    result = _run(["status", "extra"], scratch, stub_bin, tmp_path)
    _assert_nothing_executed(result, scratch, tmp_path)
    assert "takes no arguments" in result.stderr


# --- innocence: a well-formed `bump` reaches the fetch step ----------------


def test_innocence_bump_valid_version_reaches_the_fetch_step(
    scratch: Path, stub_bin: Path, tmp_path: Path
) -> None:
    result = _run(["bump", "0.156.1"], scratch, stub_bin, tmp_path)
    # The stub curl always exits 42, so the overall run still fails — this
    # proves the script REACHED the network call and stopped there, not
    # that the whole flow succeeds (that full path is verified separately,
    # live against the real registry — see the PR body).
    assert result.returncode != 0
    curl_log = tmp_path / "curl.log"
    assert curl_log.exists(), "curl must be invoked once validation accepts the version"
    logged = curl_log.read_text()
    assert "registry.npmjs.org/@openai%2fcodex/0.156.1" in logged
    # launchctl kickstart is far downstream of the fetch step (extract +
    # env rewrite both come first) — the stub curl's exit 42 must never let
    # execution reach it.
    assert not (tmp_path / "launchctl.log").exists()
    assert not (scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex").exists()
    assert _env_file(scratch) == _ENV_FILE_CONTENT


def test_innocence_bump_reuses_an_already_verified_directory(
    scratch: Path, stub_bin: Path, tmp_path: Path
) -> None:
    """A directory that is already present AND reports the right --version
    is reused untouched — no curl call at all. This is the `bump <old>`
    rollback path: it must not re-fetch what is already on disk."""
    codex_ver_dir = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex" / "0.156.1" / "bin"
    codex_ver_dir.mkdir(parents=True)
    fake_bin = codex_ver_dir / "codex"
    _make_executable(fake_bin, "#!/bin/bash\necho 'codex-cli 0.156.1'\n")

    result = _run(["bump", "0.156.1"], scratch, stub_bin, tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "curl.log").exists(), "an already-verified dir must not trigger a re-fetch"
    assert "WA_CODEX_CLI_VERSION_PIN=0.156.1" in _env_file(scratch)
    assert f"WA_CODEX_BIN={fake_bin}" in _env_file(scratch)
    assert "WA_BROKER_KEY=fake-test-key-not-real" in _env_file(scratch), "the secret line must survive untouched"


def test_innocence_status_reports_unset_dedicated_binary(
    scratch: Path, stub_bin: Path, tmp_path: Path
) -> None:
    result = _run(["status"], scratch, stub_bin, tmp_path)
    assert "pin: 0.147.0" in result.stdout
    assert "dedicated binary: <unset or missing" in result.stdout
    # launchctl IS called by status (it is the whole point of that verb) —
    # the stub logs the call instead of touching a real launchd.
    assert (tmp_path / "launchctl.log").exists()
