"""Guilt + innocence for the scoped REDIS_PASSWORD load in `apps/cell/scripts/launch_cell.sh`.

Why this file exists: Redis on the Pro runs with `requirepass`, `apps/cell/.env`
carries `REDIS_URL=redis://localhost:6379/0` with no userinfo, and
`cell/main.py` builds its client with
`password=os.environ.get("REDIS_PASSWORD") or None`. The launcher sourced only
`.env`, which never had the key — so from the moment auth was turned on, every
CELL safety cycle logged

    cell.safety: Redis unavailable, proceeding without kill switch:
    Authentication required.

and `cell/core/safety.py` took its fail-open branch. Two of CELL's three stop
switches (`cell:disabled`, `cell:maintenance`) were unreadable; only the
`/tmp/cell.disabled` file switch still worked. 2,290 such warnings were counted
in `~/logs/cell/organism.stderr.log` on 2026-09-16.

The tests are BEHAVIOURAL — the launcher is executed with a stub interpreter
that records the environment it was handed. A test that greps the script's
source would pass with the block deleted-and-commented, which is the shape
superscar #3 is about.

Three families of assertion, and the first is NOT the interesting one:

  guilt      the password reaches the interpreter at all
  exposure   exactly ONE key crosses over, an explicit value always wins, and
             a credential file that is not 0600 is refused and reported
  parsing    the value that crosses over is the RIGHT one, and a malformed
             credential file cannot take the launcher down with it

That last family exists because an independent review of the first version of
this change found a defect the guilt test could never see: the parser used
`head -n 1`, which closes the pipe after one line, so on a file with more than
one match `sed` took SIGPIPE and — under `set -euo pipefail` — the failing
command substitution aborted the launcher outright (exit 141, measured). A
credential fix that can stop CELL from starting is worse than the bug. The
`\r` and trailing-blank cases belong to the same family for the opposite
reason: they are SILENT, producing a wrong password whose only symptom is the
very fail-open this change exists to end.

No real credential appears here: every value is a literal invented by this file.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[2] / "apps" / "cell" / "scripts" / "launch_cell.sh"

_FALLBACK_VALUE = "fallback-pw-from-secrets-file"
_EXPLICIT_VALUE = "explicit-pw-from-dot-env"
_UNRELATED_KEY = "SOME_UNRELATED_OAUTH_TOKEN"
_UNRELATED_VALUE = "unrelated-token-that-must-not-travel"


def _cell_dir(tmp_path: Path, env_body: str) -> Path:
    """A fake CELL_DIR: the .env the launcher sources, and a stub interpreter.

    The stub stands where `.venv/bin/python -m cell.main` would exec, and dumps
    the environment it received as JSON — so the assertions read what the real
    process WOULD have seen, not what the script says.
    """
    cell_dir = tmp_path / "cell"
    (cell_dir / ".venv" / "bin").mkdir(parents=True)
    (cell_dir / ".env").write_text(env_body)
    stub = cell_dir / ".venv" / "bin" / "python"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "json.dump(dict(os.environ), open(os.environ['CELL_ENV_DUMP'], 'w'))\n"
    )
    stub.chmod(0o755)
    return cell_dir


def _run(
    tmp_path: Path,
    *,
    env_body: str,
    secrets_body: str | None,
    secrets_mode: int = 0o600,
    preset: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    cell_dir = _cell_dir(tmp_path, env_body)
    dump = tmp_path / "env.json"

    env = dict(os.environ)
    env.pop("REDIS_PASSWORD", None)
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
    assert _UNRELATED_VALUE not in child.values()


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


def test_a_secrets_file_that_is_not_0600_is_refused_and_reported(tmp_path: Path) -> None:
    """INNOCENCE: a world-readable credential file is skipped, not trusted.

    And it is REPORTED — a silent skip here would look exactly like the bug
    this change fixes, with nothing in the log to distinguish them.

    It is deliberately NOT fatal: CELL's documented policy is to fail open on
    an unreachable Redis and rely on the file kill switch, and a host whose
    Redis has no `requirepass` at all is a valid configuration.
    """
    proc, child = _run(
        tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=_SECRETS, secrets_mode=0o644
    )

    assert proc.returncode == 0
    assert not child.get("REDIS_PASSWORD")
    assert "refusing to read REDIS_PASSWORD" in proc.stderr
    assert _FALLBACK_VALUE not in proc.stderr  # reported, never echoed


def test_a_0600_file_without_the_key_warns_instead_of_skipping_silently(tmp_path: Path) -> None:
    """INNOCENCE: the last silent path is closed.

    Correct permissions and no usable value is the one case that otherwise
    produced no output at all — visually identical to the outage.
    """
    proc, child = _run(
        tmp_path,
        env_body=_ENV_NO_PASSWORD,
        secrets_body=f"{_UNRELATED_KEY}={_UNRELATED_VALUE}\n",
    )

    assert proc.returncode == 0
    assert not child.get("REDIS_PASSWORD")
    assert "no usable REDIS_PASSWORD" in proc.stderr


# -------------------------------------------------------------- parsing


def test_a_credential_file_with_many_matches_does_not_abort_the_launcher(
    tmp_path: Path,
) -> None:
    """REGRESSION for the defect that closed PR #6616 before it merged.

    The first version piped through `head -n 1`. head closes the pipe after
    one line; with enough upstream output sed then takes SIGPIPE, and under
    `set -euo pipefail` the failing command substitution aborts the launcher —
    CELL would not start at all. Measured on the head form: exit 141.

    300k lines is not a realistic secrets file; it is the smallest input that
    makes the class reproduce deterministically rather than by buffer luck.
    """
    body = "".join(f"REDIS_PASSWORD=pw-{i:06d}\n" for i in range(300_000))
    proc, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=body)

    assert proc.returncode == 0, f"launcher aborted: rc={proc.returncode} {proc.stderr[-400:]}"
    assert child.get("REDIS_PASSWORD") == "pw-299999"


def test_the_last_assignment_wins_exactly_as_source_would(tmp_path: Path) -> None:
    """Two readers of one file must not disagree about what it says.

    `.env` is consumed with `set -a; source`, which takes the LAST assignment.
    A fallback that took the first would quietly use a different credential
    than every other consumer of the same file.
    """
    body = "REDIS_PASSWORD=first-value\nREDIS_PASSWORD=second-value\n"
    _, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=body)

    assert child.get("REDIS_PASSWORD") == "second-value"


def test_a_crlf_line_ending_does_not_ride_into_the_password(tmp_path: Path) -> None:
    """SILENT-WRONG guard: `\\r` in the password means auth fails and CELL
    fails open again — the exact outage, with a correct-looking config."""
    _, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body="REDIS_PASSWORD=abc\r\n")

    assert child.get("REDIS_PASSWORD") == "abc"


def test_unquoted_trailing_whitespace_is_stripped(tmp_path: Path) -> None:
    """Same silent-wrong class, and again what `source` would have done."""
    _, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body="REDIS_PASSWORD=abc   \n")

    assert child.get("REDIS_PASSWORD") == "abc"


def test_whitespace_inside_quotes_is_deliberate_and_survives(tmp_path: Path) -> None:
    """INNOCENCE for the strip above: quoted blanks are part of the value.

    Without this, the cure for trailing whitespace would silently corrupt a
    legitimate password that ends in a space.
    """
    _, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body='REDIS_PASSWORD="abc "\n')

    assert child.get("REDIS_PASSWORD") == "abc "


def test_a_commented_out_assignment_is_not_read(tmp_path: Path) -> None:
    """INNOCENCE: `#REDIS_PASSWORD=` is a disabled line, not a credential."""
    body = f"#REDIS_PASSWORD=commented-out\nREDIS_PASSWORD={_FALLBACK_VALUE}\n"
    _, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=body)

    assert child.get("REDIS_PASSWORD") == _FALLBACK_VALUE


# ---------------------------------------------------- untouched behaviour


def test_absent_secrets_file_still_launches(tmp_path: Path) -> None:
    """INNOCENCE: `set -u` plus a missing fallback must not abort the daemon.

    An unauthenticated Redis (a dev machine without `requirepass`) is a valid
    configuration, and CELL still has its file kill switch either way.
    """
    proc, child = _run(tmp_path, env_body=_ENV_NO_PASSWORD, secrets_body=None)

    assert proc.returncode == 0, proc.stderr
    assert not child.get("REDIS_PASSWORD")
    assert child.get("REDIS_URL") == "redis://localhost:6379/0"


def test_missing_env_file_still_fails_loudly(tmp_path: Path) -> None:
    """INNOCENCE: the launcher's pre-existing fatal path is untouched."""
    cell_dir = tmp_path / "cell"
    (cell_dir / ".venv" / "bin").mkdir(parents=True)

    env = dict(os.environ, CELL_DIR=str(cell_dir), CELL_ENV_DUMP=str(tmp_path / "unused.json"))
    env.pop("REDIS_PASSWORD", None)
    proc = subprocess.run(
        ["bash", str(LAUNCHER)], env=env, capture_output=True, text=True, timeout=60
    )

    assert proc.returncode == 1
    assert "FATAL: Missing" in proc.stderr


@pytest.mark.skipif(os.uname().sysname != "Darwin", reason="stat -f is BSD/macOS syntax")
def test_permission_check_uses_syntax_that_works_on_this_host() -> None:
    """The 0600 gate is only a gate where `stat -f` parses.

    On Linux `stat -f` reads a FILESYSTEM, not a file, so the check would fall
    through to `|| echo unknown` and refuse every file — the fallback would be
    disabled rather than enforced, and the refusal is at least reported. CELL
    runs on the Pro (Darwin); this states the dependency instead of leaving it
    implicit.
    """
    out = subprocess.run(
        ["stat", "-f", "%OLp", str(LAUNCHER)], capture_output=True, text=True
    )
    assert out.returncode == 0
    assert out.stdout.strip().isdigit()
