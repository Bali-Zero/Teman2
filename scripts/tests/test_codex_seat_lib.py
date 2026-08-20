"""Corpus for scripts/lib/codex_seat.sh — which ChatGPT Pro seat a call uses.

The lib is sourced by wrappers written in sh, bash AND zsh, so the core
behaviour is asserted under all three: a POSIX construct that happens to work
in zsh is not evidence that it works where cron actually runs it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# `["codex", "exec", ...]` in either quote style — an argv element, not prose.
# Up to 6 intervening quoted tokens are tolerated between "codex" and "exec"
# (2026-08-20, W-class under-match found while arming seat rotation on the
# nightly cron trio: `create_subprocess_exec("codex", "--profile", "xhigh",
# "exec", ...)` has "--profile", "xhigh" between them — the old adjacency-only
# pattern missed codex_xhigh_fix.py and codex_visual_orchestrator.py, both
# real spawns with no seat).
_ARGV_CODEX_EXEC = re.compile(
    r"""(['"])codex\1\s*,\s*(?:['"][^'"]*['"]\s*,\s*){0,6}(['"])exec\2"""
)
# `codex exec` as a command word: start of line/pipe/`&&`/`$(`, optionally with
# a leading path, an `env VAR=…` prefix, or a `timeout N` prefix. Up to 6
# `--flag [value]` tokens are tolerated between "codex" and "exec" for the
# same reason as the argv pattern above — `codex --profile xhigh exec "$P"`
# and `codex --ignore-user-config --sandbox workspace-write --ephemeral --cd
# "$ROOT" exec "$P"` are both real invocations the bare-adjacency pattern
# missed (all three nightly codex/*.sh crons, live on Pro, none seat-aware
# until this fix).
_SHELL_CODEX_EXEC = re.compile(
    r"(^|[|&;(]|\s)(\S*/)?codex(\s+--?[\w][\w-]*(=\S+)?(\s+\S+)?){0,6}\s+exec\b"
)

LIB = Path(__file__).resolve().parents[2] / "scripts" / "lib" / "codex_seat.sh"

# `sh` is the portable default: it exists on every machine and on the CI
# runner. zsh and bash are parametrised because real callers use them —
# claude-cascade.sh and regulatory-watcher-run.sh are zsh, the supervisor is
# bash 3.2 — and a shell that is genuinely absent is SKIPPED with its name in
# the reason, never silently dropped: "9 passed" must not be able to mean
# "the shell that matters was never run".
SHELLS = ("sh", "bash", "zsh")


def _seat(home: Path, name: str, *, logged_in: bool = True) -> Path:
    d = home / name
    d.mkdir(parents=True, exist_ok=True)
    if logged_in:
        (d / "auth.json").write_text("{}", encoding="utf-8")
    return d


def _run(home: Path, snippet: str, shell: str = "sh", **env: str) -> str:
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
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} not installed on this machine — coverage NOT claimed")
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
            # Join `\`-newline continuations into their logical line first —
            # the real codex-nightly-autofix-ci.sh invocation puts `codex
            # --ignore-user-config ... \` and `exec "$PROMPT" ...` on two
            # separate physical lines; scanning physical lines alone can
            # never see them as one command (same class of miss as the
            # adjacency-only pattern above, one line up the stack).
            logical_body = re.sub(r"\\\n[ \t]*", " ", body)
            real = any(
                _SHELL_CODEX_EXEC.search(line)
                and not line.lstrip().startswith("#")
                for line in logical_body.splitlines()
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


# ---------------------------------------------------------------------------
# Per-call-site: the four scripts/codex/*.sh nightly crons (2026-08-20 arming)
#
# Each guilt case proves the wrapper ITSELF — not just the lib in isolation
# above — now resolves and exports a seat before it would spawn codex. Each
# innocence case proves the opposite direction: with no live seat anywhere
# under HOME, the wrapper degrades to codex's own default (no CODEX_HOME
# forced empty, no crash, no seat line printed) rather than failing loud or
# silently on a class of input the guilt case doesn't cover.
#
# All four are run with their own DRY_RUN escape hatch so no `codex`
# subprocess, no GitHub API, and no runtime-worktree git checkout ever
# fires — CODEX_AUTOMATION_LIB is pointed at a nonexistent path so the real
# ~/scripts/codex/automation-lib.sh (which does a real `git fetch` before its
# own dry-run gate — codex-nightly-autofix-ci.sh only) never loads either.
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

_SEAT_LINE_RE = re.compile(r"codex seat: (\S+)")


def _cron_case(
    script: str, dry_run_var: str, *, extra_env: dict[str, str] | None = None
) -> dict[str, str]:
    return {"script": script, "dry_run_var": dry_run_var, "extra": extra_env or {}}


CRON_CASES = [
    _cron_case("codex-daily-research-actor.sh", "CODEX_RESEARCH_DRY_RUN"),
    _cron_case("codex-nightly-coverage-improver.sh", "CODEX_COVERAGE_DRY_RUN"),
    _cron_case("codex-overnight-runner.sh", "CODEX_OVERNIGHT_DRY_RUN"),
    _cron_case(
        "codex-nightly-autofix-ci.sh",
        "CODEX_AUTOFIX_DRY_RUN",
        # Short-circuits at "No failed runs found" before ever reaching its
        # own dry-run gate — same clean, codex-free exit, no `gh` call.
        extra_env={"CODEX_AUTOFIX_FAILED_RUNS_JSON": "[]"},
    ),
]


def _run_cron(tmp_path: Path, case: dict[str, str], *, seat: bool) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    if seat:
        _seat(home, ".codex-o2")
    else:
        home.mkdir(parents=True, exist_ok=True)
    # Every *_STATE_DIR / *_LOG_DIR / *_REPO_ROOT env var this family of
    # scripts reads shares one prefix per script — set the ones each script
    # actually consults to keep every side effect inside tmp_path.
    prefix = case["dry_run_var"].removesuffix("_DRY_RUN")
    env = {
        **os.environ,
        "HOME": str(home),
        case["dry_run_var"]: "1",
        f"{prefix}_STATE_DIR": str(tmp_path / "state"),
        f"{prefix}_LOG_DIR": str(tmp_path / "log"),
        f"{prefix}_REPO_ROOT": str(tmp_path / "repo"),
        "CODEX_AUTOMATION_LIB": str(tmp_path / "no-such-lib.sh"),
        **case["extra"],
    }
    (tmp_path / "repo").mkdir(parents=True, exist_ok=True)
    if prefix == "CODEX_RESEARCH":
        env["CODEX_RESEARCH_OVERNIGHT_BACKLOG_DIR"] = str(tmp_path / "backlog")
    return subprocess.run(
        ["bash", str(ROOT / "scripts" / "codex" / case["script"])],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


@pytest.mark.parametrize("case", CRON_CASES, ids=[c["script"] for c in CRON_CASES])
def test_guilt_the_cron_wrapper_now_resolves_a_seat_before_running(
    tmp_path: Path, case: dict[str, str]
) -> None:
    proc = _run_cron(tmp_path, case, seat=True)
    assert proc.returncode == 0, proc.stderr
    m = _SEAT_LINE_RE.search(proc.stderr)
    assert m, f"no seat line in stderr:\n{proc.stderr}"
    assert m.group(1).endswith(".codex-o2")


@pytest.mark.parametrize("case", CRON_CASES, ids=[c["script"] for c in CRON_CASES])
def test_innocence_the_cron_wrapper_degrades_cleanly_with_no_live_seat(
    tmp_path: Path, case: dict[str, str]
) -> None:
    """No seat anywhere under HOME must NOT crash the wrapper and must NOT
    print a seat line — CODEX_HOME stays unset (codex's own default), the
    fail-open this class of fix must keep, never a silent wrong seat."""
    proc = _run_cron(tmp_path, case, seat=False)
    assert proc.returncode == 0, proc.stderr
    assert "codex seat:" not in proc.stderr, proc.stderr


def test_all_four_cron_wrappers_source_the_one_true_seat_lib() -> None:
    """Static shape check, cheap and specific: every wrapper's seat block
    sources scripts/lib/codex_seat.sh by its real relative path and calls
    codex_seat_pick — not a hand-rolled re-derivation of the seat list
    (W106b), and not a typo'd path that would silently no-op every run."""
    for case in CRON_CASES:
        body = (ROOT / "scripts" / "codex" / case["script"]).read_text(encoding="utf-8")
        assert "../lib" in body and "codex_seat.sh" in body, case["script"]
        assert "codex_seat_pick" in body, case["script"]
        assert "export CODEX_HOME=" in body, case["script"]
