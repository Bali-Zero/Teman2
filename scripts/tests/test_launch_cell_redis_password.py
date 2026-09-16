"""Guilt + innocence for the scoped REDIS_PASSWORD load in `apps/cell/scripts/launch_cell.sh`.

Why this exists: Redis on the Pro runs with `requirepass`, `apps/cell/.env`
carries `REDIS_URL=redis://localhost:6379/0` with no userinfo, and
`cell/main.py` builds its client with
`password=os.environ.get("REDIS_PASSWORD") or None`. The launcher sourced only
`.env`, which never had the key — so every CELL safety cycle logged

    cell.safety: Redis unavailable, proceeding without kill switch:
    Authentication required.

and `cell/core/safety.py` took its fail-open branch. Two of CELL's three stop
switches (`cell:disabled`, `cell:maintenance`) were unreadable; only the
`/tmp/cell.disabled` file switch still worked. 2,290 such warnings were counted
in `~/logs/cell/organism.stderr.log` on 2026-09-16.

The PARSING contract lives in `test_read_secret_key.py`, next to the parser.
What is tested HERE is the shell around it, and after two review rounds the
property that matters most is the negative one: **no path through this block
may abort the launcher.** A credential file that stops CELL from starting is
worse than the fail-open being cured, so every failure mode below asserts
`returncode == 0` and a warning — not a value.

Behavioural, not source-greps: the launcher runs with a stub standing where
`.venv/bin/python` is invoked, and the assertions read what the real process
WOULD have been handed.

The stub dumps an ALLOWLIST, never `os.environ` wholesale — an earlier version
of this file wrote the entire test runner's environment to disk, which on a CI
runner means its credentials. A test proving a credential stays scoped must not
itself spill unrelated ones.

No real credential appears: every value is a literal invented by this file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
LAUNCHER = _REPO / "apps" / "cell" / "scripts" / "launch_cell.sh"
READER = _REPO / "apps" / "cell" / "scripts" / "read_secret_key.py"

_FALLBACK_VALUE = "fallback-pw-from-secrets-file"
_EXPLICIT_VALUE = "explicit-pw-from-dot-env"
_UNRELATED_KEY = "SOME_UNRELATED_OAUTH_TOKEN"
_UNRELATED_VALUE = "unrelated-token-that-must-not-travel"

# Every name this file invents, and nothing else. The stub reports presence or
# absence of exactly these, so an assertion about what did NOT cross over stays
# possible without materialising the runner's environment.
_DUMP_KEYS = (_UNRELATED_KEY, "ANOTHER_UNRELATED", "REDIS_PASSWORD", "REDIS_URL", "CELL_ID")

_STUB = f'''#!/usr/bin/env python3
"""Stands in for `.venv/bin/python`. Two callers, told apart by argv."""
import json, os, runpy, sys

_ALLOWLIST = {_DUMP_KEYS!r}

argv = sys.argv[1:]
if argv and argv[0].endswith("read_secret_key.py"):
    sys.argv = argv
    runpy.run_path(argv[0], run_name="__main__")
    raise SystemExit(0)

with open(os.environ["CELL_ENV_DUMP"], "w") as fh:
    json.dump({{k: os.environ[k] for k in _ALLOWLIST if k in os.environ}}, fh)
'''


def _cell_dir(tmp_path: Path, env_body: str, *, with_reader: bool = True) -> Path:
    cell_dir = tmp_path / "cell"
    # exist_ok: a test that sweeps several credential shapes reuses one tmp_path.
    (cell_dir / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
    (cell_dir / "scripts").mkdir(exist_ok=True)
    (cell_dir / ".env").write_text(env_body)
    if with_reader:
        shutil.copy(READER, cell_dir / "scripts" / "read_secret_key.py")
    stub = cell_dir / ".venv" / "bin" / "python"
    stub.write_text(_STUB)
    stub.chmod(0o755)
    return cell_dir


def _run(
    tmp_path: Path,
    *,
    env_body: str,
    secrets_body: str | None,
    secrets_mode: int = 0o600,
    preset: dict[str, str] | None = None,
    with_reader: bool = True,
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    cell_dir = _cell_dir(tmp_path, env_body, with_reader=with_reader)
    dump = tmp_path / "env.json"

    env = dict(os.environ)
    for k in _DUMP_KEYS:
        env.pop(k, None)
    # pytest writes the full test id here, parametrize values and all. Copying
    # it into the child made execve() fail with E2BIG on the large-file case —
    # the test harness breaking the thing it was measuring.
    env.pop("PYTEST_CURRENT_TEST", None)
    env.update(CELL_DIR=str(cell_dir), CELL_ENV_DUMP=str(dump))
    if secrets_body is None:
        env["NUZANTARA_SECRETS_FILE"] = str(tmp_path / "absent.env")
    else:
        secrets = tmp_path / "secrets.env"
        secrets.write_text(secrets_body, newline="")
        secrets.chmod(secrets_mode)
        env["NUZANTARA_SECRETS_FILE"] = str(secrets)
    if preset:
        env.update(preset)

    proc = subprocess.run(
        ["bash", str(LAUNCHER)], env=env, capture_output=True, text=True, timeout=120
    )
    child_env = json.loads(dump.read_text()) if dump.exists() else {}
    return proc, child_env


_ENV_NO_PASSWORD = "REDIS_URL=redis://localhost:6379/0\nCELL_ID=test-cell\n"
_ENV_WITH_PASSWORD = _ENV_NO_PASSWORD + f"REDIS_PASSWORD={_EXPLICIT_VALUE}\n"
_SECRETS = (
    f"{_UNRELATED_KEY}={_UNRELATED_VALUE}\n"
    f"REDIS_PASSWORD={_FALLBACK_VALUE}\n"
    "ANOTHER_UNRELATED=nope\n"
)


# ---------------------------------------------------------------- guilt


def test_redis_password_reaches_the_interpreter_when_dot_env_lacks_it(tmp_path: Path) -> None:
    """GUILT: the binding whose absence made CELL fail open for weeks."""
    proc, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=_SECRETS)

    assert proc.returncode == 0, proc.stderr
    assert child.get("REDIS_PASSWORD") == _FALLBACK_VALUE


# ------------------------------------------------------------- exposure


def test_only_redis_password_crosses_over_from_the_secrets_file(tmp_path: Path) -> None:
    """INNOCENCE (least exposure): the file is read, never sourced.

    `set -a; source ~/.nuzantara-secrets.env` would satisfy the guilt test
    above and hand a long-running daemon every unrelated credential in that
    file. This is the assertion that forbids it.
    """
    _, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=_SECRETS)

    assert child.get("REDIS_PASSWORD") == _FALLBACK_VALUE
    assert _UNRELATED_KEY not in child
    assert "ANOTHER_UNRELATED" not in child


def test_explicit_password_in_dot_env_is_never_overwritten(tmp_path: Path) -> None:
    """INNOCENCE: `.env` stays authoritative; the fallback only fills a hole."""
    _, child = _run(tmp_path, env_body=_ENV_WITH_PASSWORD, secrets_body=_SECRETS)

    assert child.get("REDIS_PASSWORD") == _EXPLICIT_VALUE


def test_explicit_password_in_the_environment_is_never_overwritten(tmp_path: Path) -> None:
    """INNOCENCE: an operator running the launcher by hand keeps control."""
    _, child = _run(
        tmp_path,
        env_body=_ENV_NO_PASSWORD,
        secrets_body=_SECRETS,
        preset={"REDIS_PASSWORD": "pw-from-the-caller"},
    )

    assert child.get("REDIS_PASSWORD") == "pw-from-the-caller"


def test_the_credential_never_appears_on_stderr(tmp_path: Path) -> None:
    """Across success AND every refusal path the shell can reach."""
    for body, mode in (
        (_SECRETS, 0o600),
        (_SECRETS, 0o644),
        (f"REDIS_PASSWORD={_FALLBACK_VALUE}\\ \n", 0o600),  # refused: backslash
    ):
        proc, _ = _run(
            tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=body, secrets_mode=mode
        )
        assert _FALLBACK_VALUE not in proc.stderr
        assert _FALLBACK_VALUE not in proc.stdout


# ---------------------------------------- no path may abort the launcher


_MANY_MATCHES = "many matching lines"


@pytest.mark.parametrize(
    ("label", "secrets_body", "mode"),
    [
        # Built inside the test, not here: a 300k-line parametrize VALUE becomes
        # part of the test id, which pytest exports as PYTEST_CURRENT_TEST.
        (_MANY_MATCHES, "", 0o600),
        ("mode not 0600", _SECRETS, 0o644),
        ("key absent", f"{_UNRELATED_KEY}={_UNRELATED_VALUE}\n", 0o600),
        ("empty assignment", "REDIS_PASSWORD=\n", 0o600),
        ("backslash escape", "REDIS_PASSWORD=abc\\ \n", 0o600),
        ("mid-value quote", 'REDIS_PASSWORD=ab"cd"\n', 0o600),
        ("control byte", "REDIS_PASSWORD=ab\tcd\n", 0o600),
        ("empty file", "", 0o600),
    ],
)
def test_no_credential_file_shape_can_stop_cell_from_starting(
    tmp_path: Path, label: str, secrets_body: str, mode: int
) -> None:
    """THE property this whole design turns on.

    The bash parser this replaced aborted the launcher outright on the first
    of these (`head -n 1` → SIGPIPE → `set -euo pipefail`, exit 141), and a
    review found further paths where any stage's nonzero status would do the
    same. A credential file that stops CELL from starting is worse than the
    fail-open being cured, so the shell now calls the parser inside an `if`
    condition — where a failure cannot trip `set -e`.

    Reaching the interpreter at all is what proves it: the stub only writes
    the dump file if the launcher got as far as exec'ing it.
    """
    if label == _MANY_MATCHES:
        secrets_body = "".join(f"REDIS_PASSWORD=pw-{i:06d}\n" for i in range(300_000))

    proc, child = _run(
        tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=secrets_body, secrets_mode=mode
    )

    assert proc.returncode == 0, f"{label}: launcher aborted — {proc.stderr[-400:]}"
    assert child.get("CELL_ID") == "test-cell", f"{label}: never reached the interpreter"
    if label == _MANY_MATCHES:
        # This one is readable, just pathological — last assignment wins.
        assert child.get("REDIS_PASSWORD") == "pw-299999"
    else:
        assert not child.get("REDIS_PASSWORD"), f"{label}: exported a value it could not trust"
        assert proc.stderr.strip(), f"{label}: failed silently — the bug's own signature"


def test_an_absent_secrets_file_warns_and_still_launches(tmp_path: Path) -> None:
    """INNOCENCE + visibility: a host with no credential file is valid, and
    saying so is what keeps it distinguishable from the outage."""
    proc, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=None)

    assert proc.returncode == 0, proc.stderr
    assert not child.get("REDIS_PASSWORD")
    assert child.get("REDIS_URL") == "redis://localhost:6379/0"
    assert "not present" in proc.stderr


def test_a_missing_reader_warns_and_still_launches(tmp_path: Path) -> None:
    """A half-deployed checkout must degrade, not refuse to boot."""
    cell_dir = tmp_path / "cell"
    (cell_dir / ".venv" / "bin").mkdir(parents=True)
    (cell_dir / "scripts").mkdir()
    (cell_dir / ".env").write_text(_ENV_NO_PASSWORD)
    stub = cell_dir / ".venv" / "bin" / "python"
    stub.write_text(_STUB)
    stub.chmod(0o755)
    secrets = tmp_path / "secrets.env"
    secrets.write_text(_SECRETS)
    secrets.chmod(0o600)

    env = dict(os.environ)
    for k in _DUMP_KEYS:
        env.pop(k, None)
    env.update(
        CELL_DIR=str(cell_dir),
        CELL_ENV_DUMP=str(tmp_path / "env.json"),
        NUZANTARA_SECRETS_FILE=str(secrets),
    )
    proc = subprocess.run(
        ["bash", str(LAUNCHER)], env=env, capture_output=True, text=True, timeout=120
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads((tmp_path / "env.json").read_text()).get("CELL_ID") == "test-cell"
    assert proc.stderr.strip()


# ---------------------------------------------------- untouched behaviour


def test_missing_env_file_still_fails_loudly(tmp_path: Path) -> None:
    """INNOCENCE: the launcher's pre-existing fatal path is untouched.

    `.env` absent IS fatal and always was — that is a broken deployment, not a
    missing credential, and the distinction is the point of this test sitting
    next to the ones above.
    """
    cell_dir = tmp_path / "cell"
    (cell_dir / ".venv" / "bin").mkdir(parents=True)

    env = dict(os.environ, CELL_DIR=str(cell_dir), CELL_ENV_DUMP=str(tmp_path / "unused.json"))
    env.pop("REDIS_PASSWORD", None)
    proc = subprocess.run(
        ["bash", str(LAUNCHER)], env=env, capture_output=True, text=True, timeout=60
    )

    assert proc.returncode == 1
    assert "FATAL: Missing" in proc.stderr
