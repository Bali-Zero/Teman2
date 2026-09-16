"""Unit tests for `apps/cell/scripts/read_secret_key.py`.

This parser exists because two review rounds on a bash equivalent found four
separate ways for it to abort CELL or export a silently wrong password. Its
whole contract is: return the RIGHT value, or refuse and say why — never guess.
So the interesting tests here are the refusals.

No real credential appears: every value is a literal invented by this file.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_HELPER = (
    Path(__file__).resolve().parents[2] / "apps" / "cell" / "scripts" / "read_secret_key.py"
)

_spec = importlib.util.spec_from_file_location("read_secret_key", _HELPER)
assert _spec is not None and _spec.loader is not None
rsk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rsk)


def _file(tmp_path: Path, body: str | bytes, mode: int = 0o600) -> Path:
    p = tmp_path / "secrets.env"
    if isinstance(body, bytes):
        p.write_bytes(body)
    else:
        p.write_text(body, newline="")
    p.chmod(mode)
    return p


def _read(tmp_path: Path, body: str | bytes, mode: int = 0o600, key: str = "REDIS_PASSWORD"):
    """Run the helper as the launcher does — a real process, real exit code."""
    p = _file(tmp_path, body, mode)
    return subprocess.run(
        [sys.executable, str(_HELPER), str(p), key], capture_output=True, text=True, timeout=60
    )


# ------------------------------------------------------------- accepted


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("REDIS_PASSWORD=plain\n", "plain"),
        ("REDIS_PASSWORD=plain", "plain"),  # no trailing newline
        ("REDIS_PASSWORD=abc\r\n", "abc"),  # CRLF must not ride into the value
        ("REDIS_PASSWORD=abc   \n", "abc"),  # unquoted trailing blanks are separators
        ('REDIS_PASSWORD="abc "\n', "abc "),  # ...but inside quotes they are the value
        ("REDIS_PASSWORD='abc '\n", "abc "),
        ("REDIS_PASSWORD=a=b=c\n", "a=b=c"),  # '=' inside the value is ordinary
        ("REDIS_PASSWORD=has#hash\n", "has#hash"),  # '#' is not a comment mid-value
        ("#REDIS_PASSWORD=off\nREDIS_PASSWORD=on\n", "on"),  # commented line is not an assignment
        ("REDIS_PASSWORD_EXTRA=no\nREDIS_PASSWORD=yes\n", "yes"),  # exact key, not a prefix
        ("REDIS_PASSWORD=first\nREDIS_PASSWORD=second\n", "second"),  # LAST wins, like `source`
    ],
)
def test_accepted_shapes(tmp_path: Path, body: str, expected: str) -> None:
    out = _read(tmp_path, body)

    assert out.returncode == 0, out.stderr
    assert out.stdout == expected


def test_a_very_large_file_is_read_without_incident(tmp_path: Path) -> None:
    """The bash version aborted the launcher on this input (SIGPIPE, exit 141)."""
    body = "".join(f"REDIS_PASSWORD=pw-{i:06d}\n" for i in range(300_000))
    out = _read(tmp_path, body)

    assert out.returncode == 0, out.stderr
    assert out.stdout == "pw-299999"


# -------------------------------------------------------------- refused


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("backslash escape", "REDIS_PASSWORD=abc\\ \n"),
        ("mid-value double quote", 'REDIS_PASSWORD=ab"cd"\n'),
        ("unbalanced quote", "REDIS_PASSWORD=\"abc\n"),
        ("control byte", "REDIS_PASSWORD=ab\tcd\n"),
        ("empty assignment", "REDIS_PASSWORD=\n"),
        ("blanks only", "REDIS_PASSWORD=    \n"),
        ("empty quotes", 'REDIS_PASSWORD=""\n'),
    ],
)
def test_ambiguous_or_empty_values_are_refused_not_guessed(
    tmp_path: Path, label: str, body: str
) -> None:
    """A wrong password fails auth and lands back in the fail-open being cured.

    Shell would resolve some of these with `eval`; `eval` on a credential file
    is not a trade worth making. Refusing is loud, and loud is recoverable.
    """
    out = _read(tmp_path, body)

    assert out.returncode != 0, f"{label} should be refused, got stdout={out.stdout!r}"
    assert out.stdout == ""
    assert out.stderr.strip()


def test_the_key_being_absent_is_refused(tmp_path: Path) -> None:
    out = _read(tmp_path, "SOMETHING_ELSE=value\n")

    assert out.returncode != 0
    assert "no REDIS_PASSWORD assignment" in out.stderr


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o666, 0o700])
def test_a_file_that_is_not_0600_is_refused(tmp_path: Path, mode: int) -> None:
    """The posture scripts/pg.sh documents: a loosely permissioned credential
    file is reported and skipped, never trusted."""
    out = _read(tmp_path, "REDIS_PASSWORD=plain\n", mode=mode)

    assert out.returncode != 0
    assert "!= 0600" in out.stderr
    assert out.stdout == ""


def test_nul_bytes_are_refused_rather_than_parsed(tmp_path: Path) -> None:
    out = _read(tmp_path, b"REDIS_PASSWORD=ab\x00cd\n")

    assert out.returncode != 0
    assert "NUL" in out.stderr


def test_invalid_utf8_is_refused_rather_than_crashing(tmp_path: Path) -> None:
    out = _read(tmp_path, b"REDIS_PASSWORD=ab\xff\xfecd\n")

    assert out.returncode != 0
    assert out.stdout == ""
    assert "UTF-8" in out.stderr


def test_a_missing_file_is_refused_cleanly(tmp_path: Path) -> None:
    out = subprocess.run(
        [sys.executable, str(_HELPER), str(tmp_path / "nope.env"), "REDIS_PASSWORD"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert out.returncode != 0
    assert "cannot stat" in out.stderr


# ------------------------------------------------------- never leaks it


def test_no_refusal_message_ever_contains_the_value(tmp_path: Path) -> None:
    """Every failure is reported; none of them reports the credential.

    The ambiguous-value branch is the one that has the value in hand at the
    moment it refuses, which is exactly why it is asserted here.
    """
    secret = "SuperSecretValue123"
    for body in (
        f"REDIS_PASSWORD={secret}\\ \n",  # refused: backslash
        f'REDIS_PASSWORD=x"{secret}"\n',  # refused: mid-value quote
    ):
        out = _read(tmp_path, body)
        assert out.returncode != 0
        assert secret not in out.stderr, "the refusal echoed the credential"
        assert secret not in out.stdout

    out = _read(tmp_path, f"REDIS_PASSWORD={secret}\n", mode=0o644)
    assert out.returncode != 0
    assert secret not in out.stderr


def test_usage_error_is_not_a_traceback(tmp_path: Path) -> None:
    out = subprocess.run(
        [sys.executable, str(_HELPER)], capture_output=True, text=True, timeout=60
    )

    assert out.returncode != 0
    assert "Traceback" not in out.stderr
    assert "usage" in out.stderr
