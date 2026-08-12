"""Corpus for scripts/lib/codex_seat.sh — which ChatGPT Pro seat a call uses.

The lib is sourced by wrappers written in sh, bash AND zsh, so the core
behaviour is asserted under all three: a POSIX construct that happens to work
in zsh is not evidence that it works where cron actually runs it.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

# `["codex", "exec", ...]` in either quote style — an argv element, not prose.
_ARGV_CODEX_EXEC = re.compile(r"""(['"])codex\1\s*,\s*(['"])exec\2""")
# `codex exec` as a command word: start of line/pipe/`&&`/`$(`, optionally with
# a leading path, an `env VAR=…` prefix, or a `timeout N` prefix.
_SHELL_CODEX_EXEC = re.compile(r"(^|[|&;(]|\s)(\S*/)?codex\s+exec\b")

LIB = Path(__file__).resolve().parents[2] / "scripts" / "lib" / "codex_seat.sh"

SHELLS = ("sh", "bash", "zsh")


def _seat(home: Path, name: str, *, logged_in: bool = True) -> Path:
    d = home / name
    d.mkdir(parents=True, exist_ok=True)
    if logged_in:
        (d / "auth.json").write_text("{}", encoding="utf-8")
    return d


def _run(home: Path, snippet: str, shell: str = "zsh", **env: str) -> str:
    full = {**os.environ, "HOME": str(home), **env}
    full.pop("CODEX_SEAT_DIRS", None)
    full.pop("CODEX_SEAT_STATE_FILE", None)
    full.update(env)
    proc = subprocess.run(
        [shell, "-c", f'. "{LIB}"\n{snippet}'],
        capture_output=True,
        text=True,
        env=full,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_guilt_the_last_seat_in_the_list_is_not_dropped(
    tmp_path: Path, shell: str
) -> None:
    """`read` returns non-zero at EOF even when it read a partial last line, so
    a list without a trailing newline silently loses its final entry — and the
    final entry is the second subscription, i.e. exactly the thing this lib
    exists to reach. Lived on 2026-08-12 before this test existed."""
    for name in (".codex", ".codex-o2", ".codex-acct2"):
        _seat(tmp_path, name)

    out = _run(tmp_path, "codex_seat_dirs", shell=shell).split()

    assert [Path(p).name for p in out] == [".codex", ".codex-o2", ".codex-acct2"]


@pytest.mark.parametrize("second", [".codex-o2", ".codex-acct2"])
def test_both_names_of_the_second_seat_are_recognised(
    tmp_path: Path, second: str
) -> None:
    """The repo SSOT calls it ~/.codex-o2, the global CLAUDE.md calls it
    ~/.codex-acct2, and BOTH exist in the fleet today on different machines. A
    list that knows one name makes the other machine's second seat invisible."""
    _seat(tmp_path, ".codex")
    _seat(tmp_path, second)

    out = _run(tmp_path, "codex_seat_dirs").split()

    assert [Path(p).name for p in out] == [".codex", second]


def test_innocence_a_directory_without_auth_json_is_not_a_seat(
    tmp_path: Path,
) -> None:
    """Measured on Pro: ~/.codex exists as a directory and answers 401. Naming
    it as a seat spends an attempt that cannot possibly succeed."""
    _seat(tmp_path, ".codex", logged_in=False)
    _seat(tmp_path, ".codex-acct2")

    out = _run(tmp_path, "codex_seat_dirs").split()

    assert [Path(p).name for p in out] == [".codex-acct2"]


def test_no_seat_prints_nothing_rather_than_the_default(tmp_path: Path) -> None:
    """`CODEX_HOME=` empty means "use the default seat", the opposite of "there
    is no seat" — so an empty answer must stay empty and never fall back."""
    assert _run(tmp_path, "codex_seat_pick") == ""
    assert _run(tmp_path, "codex_seat_nth 0") == ""
    assert _run(tmp_path, "codex_seat_count").strip() == "0"


def test_nth_wraps_around_the_live_seats(tmp_path: Path) -> None:
    _seat(tmp_path, ".codex")
    _seat(tmp_path, ".codex-acct2")

    picks = [Path(_run(tmp_path, f"codex_seat_nth {i}").strip()).name for i in range(4)]

    assert picks == [".codex", ".codex-acct2", ".codex", ".codex-acct2"]


def test_the_offset_advances_so_successive_runs_open_on_different_seats(
    tmp_path: Path,
) -> None:
    _seat(tmp_path, ".codex")
    _seat(tmp_path, ".codex-acct2")
    state = tmp_path / "rotation"

    picks = [
        Path(
            _run(tmp_path, "codex_seat_pick", CODEX_SEAT_STATE_FILE=str(state)).strip()
        ).name
        for _ in range(4)
    ]

    assert picks == [".codex", ".codex-acct2", ".codex", ".codex-acct2"], picks


def test_an_unwritable_state_file_degrades_to_a_fixed_order_not_a_failure(
    tmp_path: Path,
) -> None:
    """Bookkeeping is best-effort BY DESIGN: no call may fail to reach a
    provider because a counter could not be written. Unwritable state means the
    old fixed order, which is exactly the pre-rotation behaviour."""
    _seat(tmp_path, ".codex")
    _seat(tmp_path, ".codex-acct2")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    state = locked / "rotation"

    try:
        picks = [
            Path(
                _run(
                    tmp_path, "codex_seat_pick", CODEX_SEAT_STATE_FILE=str(state)
                ).strip()
            ).name
            for _ in range(2)
        ]
    finally:
        locked.chmod(0o700)

    assert picks == [".codex", ".codex"], picks


def test_a_process_keeps_one_seat_so_its_health_check_speaks_for_its_work(
    tmp_path: Path,
) -> None:
    """The counter advances on every read, so an unmemoised pick hands a
    different seat to each subprocess of one run — and a pre-flight probe then
    answers for a seat the real work never touches. The post-publish poller is
    exactly that shape: probe codex, and only if it passes, spend the tick."""
    import importlib.util

    _seat(tmp_path, ".codex")
    _seat(tmp_path, ".codex-acct2")
    spec = importlib.util.spec_from_file_location(
        "_codex_seat_under_test", LIB.with_suffix(".py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    env = {**os.environ, "HOME": str(tmp_path)}
    env["CODEX_SEAT_STATE_FILE"] = str(tmp_path / "rotation")
    old = dict(os.environ)
    os.environ.update(env)
    try:
        picks = [mod.codex_seat_pick() for _ in range(3)]
        moved = mod.codex_seat_pick(refresh=True)
    finally:
        os.environ.clear()
        os.environ.update(old)

    assert len(set(picks)) == 1, picks
    assert moved != picks[0], (moved, picks[0])


def test_the_census_detector_tells_an_invocation_from_prose() -> None:
    """Guilt and innocence for the census's own two patterns.

    The first draft matched the words `codex exec` anywhere, so a docstring
    that merely NAMES the command was reported as a call site — and an
    exemption list padded with false positives is a list nobody reads. The
    reverse error is worse: a real argv the pattern cannot see joins the
    dead-seat class in silence."""
    # guilty: real invocations, both languages, both quote styles
    assert _ARGV_CODEX_EXEC.search('["codex", "exec", "--sandbox"]')
    assert _ARGV_CODEX_EXEC.search("['codex', 'exec', prompt]")
    assert _SHELL_CODEX_EXEC.search("codex exec --sandbox read-only")
    assert _SHELL_CODEX_EXEC.search("/opt/homebrew/bin/codex exec -m gpt-5.6-luna")
    assert _SHELL_CODEX_EXEC.search('timeout 30 env FOO=1 codex exec "$p"')
    assert _SHELL_CODEX_EXEC.search("cat x | codex exec -")

    # innocent: prose, and a different command that merely starts the same way
    assert not _ARGV_CODEX_EXEC.search('"""Briefs for codex exec → Image 2."""')
    assert not _ARGV_CODEX_EXEC.search("# run codex exec by hand")
    assert not _SHELL_CODEX_EXEC.search("mycodex exec")
    assert not _SHELL_CODEX_EXEC.search("codex execute-plan")


def test_no_call_site_invokes_codex_without_choosing_a_seat() -> None:
    """The class, not the instance.

    Curing the one wrapper that bit you does not lower the risk of a fifth
    (W107): it only changes WHICH caller dies on a dead seat. So the guard is a
    census — every file in the tree that invokes `codex exec` must resolve a
    seat, and a new one that forgets fails HERE instead of on Pro at 03:00.

    Scope, declared rather than silent: files tracked by git, excluding docs,
    research, tests and vendor. A call site in a language with no door onto the
    lib (currently one Swift file) is listed as an exemption with its reason —
    never quietly skipped.
    """
    root = Path(__file__).resolve().parents[2]
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    ).stdout.splitlines()

    exempt = {
        "apps/wr2-control-app/Sources/Conversationalist.swift": (
            "Swift; no door onto the shell lib, and it runs interactively on a "
            "machine whose default seat is live"
        ),
        "scripts/lib/codex_seat.py": "the door itself",
        "scripts/lib/codex_seat.sh": "the door itself",
    }

    skip_prefixes = ("docs/", "research/", "scripts/tests/", ".claude/skills/")
    offenders = []
    for rel in tracked:
        if rel in exempt or rel.startswith(skip_prefixes):
            continue
        path = root / rel
        if path.suffix not in {".sh", ".py", ".zsh", ".bash"}:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Prose says `codex exec`; an invocation is either an argv element
        # (Python) or a command word on a non-comment line (shell). Matching
        # prose would push real files into the exemption list, and an
        # exemption list padded with false positives stops being read.
        if path.suffix == ".py":
            real = bool(_ARGV_CODEX_EXEC.search(body))
        else:
            real = any(
                _SHELL_CODEX_EXEC.search(line)
                and not line.lstrip().startswith("#")
                for line in body.splitlines()
            )
        if not real:
            continue
        if "codex_seat" not in body:
            offenders.append(rel)

    assert not offenders, (
        "these invoke codex without resolving a seat — source "
        "scripts/lib/codex_seat.sh (shell) or import scripts/lib/codex_seat.py "
        f"(python), or add an exemption with a reason: {offenders}"
    )


def test_the_search_list_is_overridable(tmp_path: Path) -> None:
    """A machine that keeps its seats somewhere else must be able to say so
    without editing the lib — otherwise the next fleet layout forks the file."""
    _seat(tmp_path, ".codex")
    elsewhere = _seat(tmp_path, "custom-seat")

    out = _run(
        tmp_path, "codex_seat_dirs", CODEX_SEAT_DIRS=f"{elsewhere}:{tmp_path}/.codex"
    ).split()

    assert [Path(p).name for p in out] == ["custom-seat", ".codex"]
