#!/usr/bin/env python3
"""lint_plist_keepalive.py — executable antidote for superscar #7
(Daemon-vs-cron KeepAlive misconfig).

THE FAMILY (cicatrix-superscar.md #7 — W67/W67b wa-mirror reconnect storm,
W60 Fly machine flapping, 2026-04-29 "53 LaunchAgents, only 13% KeepAlive
correct"): a launchd job is configured `KeepAlive=true` (or a KeepAlive dict
that isn't the empty/disabled form) while its actual payload is a ONE-SHOT
script — a wrapper that `exec`s a process which can legitimately exit, or
that backgrounds its real work with `nohup ... &` and returns. Every time
the one-shot exits, launchd reads it as "the daemon died" and restarts it —
and any `nohup`-detached child in the old process group gets SIGTERM'd on
the way out. The result is a restart storm, not a running daemon.

THE ANTIDOTE, verbatim (cicatrix-superscar.md #7): "sostituire lo
pseudo-demone con un loop bloccante reale nel wrapper (`while true; do …;
sleep N; done`) così launchd non cicla mai; oppure, se è davvero un cron,
StartInterval + niente KeepAlive. Grep `exec ` in tutto ciò che gira
KeepAlive=true."

This lint makes that grep executable, static, and CI-able: it walks
TRACKED plists in the repo (never live ~/Library/LaunchAgents — that's
lint_home_fork.py's job, a different superscar), and for every plist whose
KeepAlive is truthy, resolves its wrapper script (if that script is itself
tracked in the repo) and classifies the wrapper body for one-shot smells.

Detection classes:
  (a) FAIL  — a line matching `^\\s*exec\\s+<payload>` where <payload> is
              not itself a bare fd-redirection (`exec 9>lockfile`, which is
              the standard "open a file descriptor" bash idiom, not a
              process-replacing exec — see Design decision below).
  (b) FAIL  — `nohup ...` with trailing ` &` backgrounding on the same
              line (W67: the backgrounded child dies to SIGTERM every
              KeepAlive restart cycle).
  (c) WARN  — no (a)/(b) smell AND the wrapper is under 200 lines AND it
              contains none of the recognized blocking markers (`while
              true`, `while :`, `sleep infinity`, `wait `, `tail -f`,
              `caffeinate`). This is *absence of evidence*, not evidence of
              guilt (a 200+-line orchestrator very plausibly blocks by some
              means this lint doesn't enumerate) — so it is a WARN, and
              never fails the build.
  UNRESOLVED (informational, --verbose only) — payload is a direct binary,
              an inline `bash -c`/`-lc` shell string, or not resolvable to
              a tracked file at all. Nothing to read, nothing to classify.

Design decision (fd-redirect carve-out, superscar #3 discipline applied to
this lint itself): a naive `^\\s*exec\\s` substring match would also fire on
`exec 9>"${LOCKFILE}"` (open fd 9 for a lockfile) — a real line found in
this repo's own apps/backend-rag/backend/services/intake/intake-worker-run.sh
(a genuinely long-running KeepAlive worker). That is a guard-over-match
(#3 family): matching the word "exec", not the intent "replace this process
with something that can exit". This lint therefore excludes `exec <fd>>`/
`exec <fd><` forms from class (a) — see test
test_classify_innocence_exec_fd_redirect. Every FAIL class ships with an
innocence test; no guard merges here without one (superscar #3 doctrine).

Payload resolution (best-effort, read-only, never crashes): Program string
or ProgramArguments list, merged into one argv. `bash -c` / `zsh -lc`
inline shell strings are UNRESOLVED by construction (there is no separate
file to read). Otherwise each path-looking argv token is tried in order:
first as a repo-relative existing path, then (for ~/... and absolute
/Users/*/... tokens — the HOME-fork bridge shape, superscar #1 W68/W72) by
basename lookup across the SAME roots this run scanned for plists. The
first token that resolves wins; a direct binary (venv python, node, fly,
...) with no resolvable script argument is UNRESOLVED.

Exit contract is a 2-bit mask (deliberately narrower than lint_home_fork's
1|2|4 — this lint has no third arm):
    0 = clean · 1 = one or more (a)/(b) findings ·
    4 = operational error (unparseable/unreadable plist or wrapper — a scan
        that cannot see is not clean; W84 fail-visible discipline).
WARN class (c) is printed but NEVER contributes to the exit code.

Scope notes (deliberate): default roots are infra/launchagents,
scripts/launchd, infra/, apps/ (pruned of node_modules/.venv/.git) — NOT
bare top-level scripts/, which holds ~300 unrelated automation scripts and
would make basename lookup noisy and slow. A wrapper that lives directly
under scripts/ (e.g. scripts/intake_review_reader_run.sh) is UNRESOLVED
under the default roots; pass `--root scripts` to widen coverage. This is a
scope limitation, not a bug — verified against this repo's real inventory.

Complementary, not duplicative: scripts/lint_home_fork.py polices the
live-vs-repo divergence axis (superscar #1); this lint polices the
KeepAlive-vs-payload-shape axis (superscar #7) on the tracked tree alone.
Neither reads the other's state.

Tests: scripts/tests/test_lint_plist_keepalive.py.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ROOTS: tuple[str, ...] = (
    "infra/launchagents",
    "scripts/launchd",
    "infra",
    "apps",
)

_PRUNE_DIRS = {"node_modules", ".venv", ".git"}

# Executed-payload extensions considered "a script" for path-likeness / basename lookup.
_EXEC_EXTS = {".sh", ".bash", ".zsh", ".py", ".rb", ".pl", ".js", ".mjs"}

_INLINE_SHELL_FLAGS = {"-c", "-lc", "-cl"}

_EXEC_LINE_RE = re.compile(r"^(\s*)exec\s+(\S.*)$")
_FD_REDIRECT_RE = re.compile(r"^\d*[<>]")

_NOHUP_RE = re.compile(r"\bnohup\b")
_BG_TRAILING_RE = re.compile(r"(?<!&)&\s*(#.*)?$")

_BLOCKING_MARKERS = (
    "while true",
    "while :",
    "sleep infinity",
    "wait ",
    "tail -f",
    "caffeinate",
)

_WARN_LINE_LIMIT = 200

_SMELL_EXEC = (
    "exec replaces the process — if the payload exits, KeepAlive misreads "
    "it as death and restarts (W67/W60 restart-storm risk)"
)
_SMELL_NOHUP = (
    "nohup ... & backgrounds a child that launchd SIGTERMs on every "
    "KeepAlive restart cycle (W67 wa-mirror reconnect storm)"
)


# ---------------------------------------------------------------- KeepAlive


def is_keepalive_managed(value: Any) -> bool:
    """True/non-empty-dict = keepalive-managed. Anything else (False, None,
    missing, empty dict) is not — mirrors the plist's own truthiness rules,
    kept deliberately simple per the antidote's scope (see module docstring)."""
    if value is True:
        return True
    if isinstance(value, dict):
        return bool(value)
    return False


# ---------------------------------------------------------------- discovery


def _walk_files(root: Path, errors: list[str], suffix: Optional[str] = None) -> list[Path]:
    """os.walk with node_modules/.venv/.git pruned; unreadable dirs become
    operational errors (fail-visible), never a silent skip."""
    found: list[Path] = []
    if not root.exists():
        return found

    def _onerror(exc: OSError) -> None:
        errors.append(f"root unreadable ({type(exc).__name__}): {exc.filename or root}")

    for dirpath, dirnames, filenames in os.walk(root, onerror=_onerror):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
        for fn in filenames:
            if suffix is None or fn.endswith(suffix):
                found.append(Path(dirpath) / fn)
    return found


def collect_plists(root_paths: list[Path], errors: list[str]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for root in root_paths:
        for path in _walk_files(root, errors, suffix=".plist"):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            ordered.append(path)
    return sorted(ordered)


def build_basename_index(root_paths: list[Path], errors: list[str]) -> dict[str, list[Path]]:
    """basename -> tracked file path(s), scoped to the SAME roots scanned for
    plists — this is the HOME-fork bridge lookup (superscar #1 W68/W72
    shape): a plist references an absolute/`~` path, we ask "does a
    same-named file live somewhere in the tracked tree we're scanning?"."""
    index: dict[str, list[Path]] = {}
    seen: set[Path] = set()
    for root in root_paths:
        for path in _walk_files(root, errors, suffix=None):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            index.setdefault(path.name, []).append(path)
    return index


# ---------------------------------------------------------------- payload resolution


def extract_argv(payload: dict[str, Any]) -> list[str]:
    """Program string or ProgramArguments list, merged into one argv.
    ProgramArguments (the fuller argv) wins when both are present."""
    prog_args = payload.get("ProgramArguments")
    if isinstance(prog_args, list) and prog_args:
        return [str(a) for a in prog_args]
    program = payload.get("Program")
    if isinstance(program, str) and program:
        return [program]
    return []


def _has_inline_shell_flag(argv: list[str]) -> bool:
    return any(arg in _INLINE_SHELL_FLAGS for arg in argv)


def _looks_like_path(arg: str) -> bool:
    if not arg or arg.startswith("-"):
        return False
    if arg.startswith("/") or arg.startswith("~"):
        return True
    if "/" in arg:
        return True
    return Path(arg).suffix.lower() in _EXEC_EXTS


def _try_resolve_one(
    arg: str, repo_root: Path, basename_index: dict[str, list[Path]]
) -> Optional[Path]:
    p = Path(arg)
    if not p.is_absolute() and not arg.startswith("~"):
        candidate = repo_root / arg
        if candidate.is_file():
            return candidate
    matches = basename_index.get(p.name)
    if matches:
        return sorted(matches)[0]
    return None


def resolve_wrapper(
    argv: list[str], repo_root: Path, basename_index: dict[str, list[Path]]
) -> tuple[Optional[Path], Optional[str]]:
    """Returns (wrapper_path, None) on success, or (None, reason) when the
    payload is UNRESOLVED — a direct binary, an inline -c/-lc shell string,
    or simply not found among tracked files."""
    if not argv:
        return None, "empty-payload"
    if _has_inline_shell_flag(argv):
        return None, "inline-shell(-c/-lc)"
    for arg in argv:
        if not _looks_like_path(arg):
            continue
        candidate = _try_resolve_one(arg, repo_root, basename_index)
        if candidate is not None:
            return candidate, None
    return None, "not-resolvable-in-repo"


# ---------------------------------------------------------------- classification


def _has_blocking_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _BLOCKING_MARKERS)


def _is_process_exec(rest_of_line: str) -> bool:
    """False for `exec 9>lockfile` / `exec >log 2>&1` — fd-manipulation, not
    a process-replacing exec (the superscar #3 carve-out, see docstring)."""
    stripped = rest_of_line.strip()
    if not stripped:
        return False
    return not _FD_REDIRECT_RE.match(stripped)


def classify_wrapper(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]], bool]:
    """Returns (findings, exec_warns, warn).

    findings   = [(line_no, smell)] — class (b) `nohup ... &`: unambiguous
                 W67 disease (children SIGTERM'd every KeepAlive cycle).
    exec_warns = [(line_no, smell)] — class (a) `exec ...`: DEMOTED to WARN
                 after day-1 calibration on the real repo (superscar #3
                 discipline applied to this very linter): exec-into-a-server
                 (livekit, wa-mirror node bridge) is the CORRECT daemon idiom
                 under KeepAlive; only exec-into-a-one-shot is the disease,
                 and one-shot-ness of the target is statically undecidable.
                 `--strict` elevates these to findings.
    warn       = True iff class (c): no smells, short wrapper, no recognized
                 blocking construct either.
    """
    lines = text.splitlines()
    findings: list[tuple[int, str]] = []
    exec_warns: list[tuple[int, str]] = []
    for line_no, line in enumerate(lines, start=1):
        m = _EXEC_LINE_RE.match(line)
        if m and _is_process_exec(m.group(2)):
            exec_warns.append((line_no, _SMELL_EXEC))
        if _NOHUP_RE.search(line) and _BG_TRAILING_RE.search(line.rstrip()):
            findings.append((line_no, _SMELL_NOHUP))
    warn = (
        not findings
        and not exec_warns
        and len(lines) < _WARN_LINE_LIMIT
        and not _has_blocking_marker(text)
    )
    return findings, exec_warns, warn


# ---------------------------------------------------------------- main


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def run(
    root_paths: list[Path], repo_root: Path, verbose: bool
) -> dict[str, Any]:
    errors: list[str] = []
    findings: list[str] = []
    warns: list[str] = []
    unresolved: list[str] = []

    plist_paths = collect_plists(root_paths, errors)
    basename_index = build_basename_index(root_paths, errors)

    for plist_path in plist_paths:
        plist_rel = _rel(plist_path, repo_root)
        try:
            payload = plistlib.loads(plist_path.read_bytes())
        except Exception as exc:  # noqa: BLE001 — fail-visible, never crash
            errors.append(f"plist unreadable/unparseable ({type(exc).__name__}): {plist_rel}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"plist root is not a dict: {plist_rel}")
            continue
        if not is_keepalive_managed(payload.get("KeepAlive")):
            continue

        argv = extract_argv(payload)
        wrapper, reason = resolve_wrapper(argv, repo_root, basename_index)
        if wrapper is None:
            if verbose:
                unresolved.append(f"{plist_rel}: KeepAlive=true, payload UNRESOLVED ({reason}): {argv!r}")
            continue

        try:
            text = wrapper.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"wrapper unreadable ({type(exc).__name__}): {_rel(wrapper, repo_root)}")
            continue

        wrapper_rel = _rel(wrapper, repo_root)
        smells, exec_warns, warn = classify_wrapper(text)
        for line_no, smell in smells:
            findings.append(f"{plist_rel}: KeepAlive=true but {wrapper_rel}:{line_no} {smell}")
        for line_no, smell in exec_warns:
            warns.append(
                f"{plist_rel}: KeepAlive=true and {wrapper_rel}:{line_no} {smell} "
                f"(WARN: legitimate iff the exec target runs forever — verify, or run --strict)"
            )
        if warn:
            warns.append(
                f"{plist_rel}: KeepAlive=true but {wrapper_rel} has no exec/nohup smell "
                f"and no blocking construct detected either — cannot confirm it stays "
                f"alive under KeepAlive (WARN, W60)"
            )

    exit_code = (1 if findings else 0) | (4 if errors else 0)
    return {
        "schema": 1,
        "findings": findings,
        "warns": warns,
        "unresolved": unresolved,
        "errors": errors,
        "exit": exit_code,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", action="append", default=None,
        help="repeatable; default: " + ", ".join(DEFAULT_ROOTS),
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--verbose", action="store_true", help="also print UNRESOLVED payloads")
    parser.add_argument(
        "--strict", action="store_true",
        help="elevate WARN-class smells (exec-into-payload, no-blocking-construct) to findings",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    roots = args.root if args.root else list(DEFAULT_ROOTS)
    root_paths = [
        (Path(r) if Path(r).is_absolute() else repo_root / r) for r in roots
    ]

    result = run(root_paths, repo_root, args.verbose)
    if args.strict and result["warns"]:
        result["findings"] = result["findings"] + [f"[strict] {w}" for w in result["warns"]]
        result["warns"] = []
        result["exit"] = result["exit"] | 1

    if args.json:
        print(json.dumps(result, indent=2))
        return result["exit"]

    print(f"[keepalive-lint] scanned roots: {', '.join(str(_rel(r, repo_root)) for r in root_paths)}")
    print(f"[findings] {len(result['findings'])}")
    for f in result["findings"]:
        print(f"  - {f}")
    print(f"[warns] {len(result['warns'])}")
    for w in result["warns"]:
        print(f"  - {w}")
    if args.verbose:
        print(f"[unresolved] {len(result['unresolved'])}")
        for u in result["unresolved"]:
            print(f"  - {u}")
    if result["errors"]:
        print(f"[errors] {len(result['errors'])} operational error(s) — scan is PARTIAL, not clean:")
        for e in result["errors"]:
            print(f"  - {e}")
    if not result["findings"] and not result["errors"]:
        print("  clean — no KeepAlive=true wrapper shows a one-shot smell")
    if result["exit"]:
        print(
            f"KEEPALIVE LINT FAIL (exit {result['exit']}: 1=one-shot-smell 4=scan-error) — "
            f"superscar #7: replace the exec/nohup one-shot with a real blocking loop "
            f"(while true; do ...; sleep N; done), or switch to StartInterval + no KeepAlive"
        )
    return result["exit"]


if __name__ == "__main__":
    sys.exit(main())
