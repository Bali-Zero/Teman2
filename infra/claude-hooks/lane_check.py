#!/usr/bin/env python3
"""lane_check.py — the contract a lane declares about ITSELF, checked at the
stop boundary.

L04-PR1 (`docs/plans/2026-08-29-beyond-sota-craft-wave/L04-implementation-craft.md`).
A worktree may carry a `.lane-check.json` at its root, emitted by the DESIGN
stage of a lane:

    {"command": "pytest scripts/tests/test_foo.py -q",
     "expected_exit": 0, "timeout": 120, "scope_globs": ["scripts/**"]}

Every termination surface calls `evaluate()` and honours `blocks()`, so a lane
that broke its own declared check cannot end a turn quietly claiming success.

WHAT THIS IS NOT, and the sentence matters more than the module. A PASS here is
the lane's own cheap claim about itself. It does NOT replace generator≠grader:
the diff still faces an independent cross-family refuter afterwards, and nothing
in this file should ever be cited as review. Superscar #2 is "exists != armed";
the adjacent error this file could invite is "self-checked != graded", and it is
named here so the next reader does not make it.

THE FAIL DIRECTION IS DELIBERATE AND DIFFERS FROM ITS NEIGHBOURS. The safety
guards in this directory (host_boundary, worktree_isolation, subagent_stop_verify)
all fail OPEN, because they are imposed on the agent and a broken one would wall
it. This module fails CLOSED on a failure to MEASURE — an unusable contract or a
timed-out command blocks rather than passing. That is not an inconsistency: those
guards judge the agent, this one relays a check the LANE declared about itself,
and a lane that cannot run its own check has not passed it. "Could not measure"
recorded as "measured fine" is precisely the disease of W104 and W108. The escape
is explicit and one env var wide (`LANE_CHECK_OFF=1`), so nothing is ever walled
without a way out.

Reference: superscar #3 (the tautology rule is entity-wise, never a substring
match — see `_is_tautology`) · W104/W108 (a failure to measure reported as a
measurement) · `infra/claude-hooks/test_lane_check.py` (guilt, innocence, and
the under-match gemello, all executed).
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class LaneCheckStatus(str, Enum):
    """Verdict of a lane's self-declared BUILD-side termination check."""

    ABSENT = "absent"  # no .lane-check.json — the innocence baseline
    PASS = "pass"
    FAIL = "fail"  # ran, exit != expected_exit
    OUT_OF_SCOPE = "out_of_scope"  # scope_globs declared, no changed path matches
    INVALID = "invalid"  # the contract file itself is unusable
    ERROR = "error"  # could not run / timed out


@dataclass(frozen=True)
class LaneCheckResult:
    """Immutable record returned by evaluate()."""

    status: LaneCheckStatus
    message: str  # "" for ABSENT/PASS/OUT_OF_SCOPE; operator-facing block otherwise
    command: str | None
    exit_code: int | None
    stderr_tail: str | None


# Shell entities that cannot fail and therefore prove nothing about the lane.
# Superscar #3 "guard over-match / substring instead of entity": these are the
# EXACT entities we match, not substrings found anywhere in the command.
_TAUTOLOGICAL_ENTITIES = frozenset({"true", ":", "exit 0", "/bin/true"})
_SHELL_SEPARATORS = ("&&", "||", ";")


def _split_shell_entities(command: str) -> list[str]:
    """Split a command on `;`, `&&` and `||`, respecting quotes.

    Quote-awareness here is DEFENSIVE, and its limits are declared rather than
    overclaimed. A blind `str.replace` mangles ``git commit -m "fix && true"``
    into two nonsense entities, and a refuter of this file demonstrated exactly
    that. But an attempt to kill a quote-blind mutant with a test FAILED, and
    the reason is worth writing down instead of hiding behind a contrived case:
    a mangled fragment always keeps the closing quote (`true"`), which is never
    the exact token `_TAUTOLOGICAL_ENTITIES` holds — so quote-blindness cannot
    actually fabricate a false tautology verdict, only ugly entities nobody
    reads. This split is therefore correct-and-unproven rather than
    correct-and-proven; it is kept because the next rule added to this matcher
    might not be so lucky. We are not writing a shell parser —
    we only need to find the top-level separators well enough to judge the
    narrow tautology rule below, and anything we get wrong must fall on the
    side of NOT refusing a legitimate command.

    Returns a list of (separator_before, entity) pairs flattened to entities,
    with the `||` positions recorded separately by the caller via
    `_split_with_separators`.
    """
    return [ent for _, ent in _split_with_separators(command)]


def _split_with_separators(command: str) -> list[tuple[str, str]]:
    """(separator that PRECEDED this entity, entity). First entity gets ""."""
    out: list[tuple[str, str]] = []
    buf: list[str] = []
    quote: str | None = None
    prev_sep = ""
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            buf.append(ch)
            if ch == quote and (i == 0 or command[i - 1] != "\\"):
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        two = command[i : i + 2]
        if two in ("&&", "||"):
            out.append((prev_sep, "".join(buf).strip()))
            prev_sep = two
            buf = []
            i += 2
            continue
        if ch == ";":
            out.append((prev_sep, "".join(buf).strip()))
            prev_sep = ";"
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    out.append((prev_sep, "".join(buf).strip()))
    return [(sep, ent) for sep, ent in out if ent]


def _is_tautology(command: str) -> bool:
    """True if the command cannot fail, and therefore proves nothing.

    TWO shapes, and the second was missed on the first pass — a blind refuter
    of this file supplied it and it is the more likely one in practice:

      1. The whole command is no-op entities: ``true``, ``:``, ``exit 0``,
         alone or joined. This is the obvious one.
      2. A REAL check whose failure is SWALLOWED by an `||` tail:
         ``pytest test_foo.py || true``. Every entity but the last is
         legitimate, so an `all()` over the entities answers False and the
         command sails through, runs, exits 0 forever and reports PASS. That is
         precisely the reward-hacking shape this rule exists to refuse, dressed
         as a real check.

    Superscar #3 governs HOW the match is made: entity-wise, after a
    quote-aware split, never a substring. Rejecting the substring "true"
    anywhere would forbid ``pytest --assert=plain test_true_positive.py``,
    which is a legitimate command, and the corpus asserts it is not refused.
    """
    parts = _split_with_separators(command)
    if not parts:
        return False  # empty command is caught by contract validation
    if all(entity in _TAUTOLOGICAL_ENTITIES for _, entity in parts):
        return True
    # Shape 2: any `||`-guarded no-op tail makes the whole command unfailable.
    return any(sep == "||" and entity in _TAUTOLOGICAL_ENTITIES for sep, entity in parts)


def _stderr_tail(stderr: str | None) -> str:
    """Return the last 2000 characters of stderr.

    We keep the tail, not the head, because the assertion or traceback that
    explains the failure is usually at the end of the output. The beginning is
    often just test collection noise.
    """
    return (stderr or "")[-2000:]


#: FIX for the untrusted-clone vector, raised by a blind refuter of this file
#: and accepted: a subagent routinely clones an EXTERNAL repository to read or
#: summarise it. If that repository carries its own `.lane-check.json`, then
#: without this gate the harness would execute a stranger's shell command, with
#: shell=True, the moment the agent tried to end its turn — a zero-click remote
#: code execution reached by doing nothing more than cloning. The original
#: trust-boundary argument ("the command comes from a worktree the agent already
#: controls") is true of OUR worktrees and false of a clone, and was wrong to
#: state without that distinction.
#:
#: So the contract is honoured only inside a repository whose `origin` remote
#: matches a trusted pattern. Default: this organism's own repository.
#: `LANE_CHECK_TRUSTED_ORIGIN` overrides it (a Python regex) for a fleet that
#: forks or renames. An untrusted origin resolves ABSENT — SILENT, not a block:
#: refusing to run a stranger's command must never wall the agent that merely
#: read the stranger's code.
_DEFAULT_TRUSTED_ORIGIN = r"(github\.com[:/]Bali-Zero/Teman2(\.git)?$)|(^$)"


def _origin_is_trusted(cwd: str) -> bool:
    """True when this worktree's `origin` belongs to a trusted repository.

    A repo with NO origin at all is trusted: that is the shape of a throwaway
    fixture created by our own tests, and of a local-only worktree. The risk
    this gate exists for arrives WITH a remote, by cloning.
    """
    pattern = os.environ.get("LANE_CHECK_TRUSTED_ORIGIN", _DEFAULT_TRUSTED_ORIGIN)
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return False  # cannot tell -> do not execute a command we cannot attribute
    origin = proc.stdout.strip() if proc.returncode == 0 else ""
    try:
        return re.search(pattern, origin) is not None
    except re.error:
        return False  # a malformed override must not open the gate



def evaluate(
    cwd: str,
    changed_paths: list[str] | None = None,
    changed_paths_fn: "Callable[[], list[str] | None] | None" = None,
) -> LaneCheckResult:
    """Decide whether a lane's self-declared check still passes.

    This is BUILD-side self-verification only. A PASS here does NOT replace
    generator≠grader; it is the lane's own cheap claim about itself, run at
    termination so a finished surface can notice it broke its own contract.
    Superscar #2 "exists != armed": this module existing and passing is not
    the same as an independent grader having reviewed the work.
    """
    try:
        # Rule 3: explicit escape hatch. Checked before any file read so an
        # operator can always unblock a stuck turn without editing JSON.
        if os.environ.get("LANE_CHECK_OFF") == "1":
            return LaneCheckResult(
                status=LaneCheckStatus.ABSENT,
                message="",
                command=None,
                exit_code=None,
                stderr_tail=None,
            )

        # Rule 8: the contract file is read from <cwd>/.lane-check.json ONLY.
        # Resolve both paths and refuse any traversal or symlink escape.
        resolved_cwd = os.path.realpath(cwd)
        config_path = os.path.realpath(os.path.join(resolved_cwd, ".lane-check.json"))
        # `startswith(cwd + os.sep)` breaks at the filesystem root, where the
        # concatenation becomes "//" and a legitimate "/.lane-check.json" reads
        # as an escape. Compare the resolved PARENT to the resolved cwd instead
        # — the entity ("is this file directly in that directory") rather than a
        # string prefix. Raised by a refuter; an edge case, but the failure mode
        # was a hard block on an innocent path.
        if os.path.dirname(config_path) != resolved_cwd:
            return LaneCheckResult(
                status=LaneCheckStatus.INVALID,
                message=(
                    f"Lane check path escapes cwd: {config_path!r} is not inside "
                    f"{resolved_cwd!r}. Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                ),
                command=None,
                exit_code=None,
                stderr_tail=None,
            )

        # Rule 1: ABSENT is byte-identical to no-op. If the lane did not emit
        # a contract, there is nothing to measure and we do no work — no
        # subprocess, no git call, no scope math.
        if not os.path.isfile(config_path):
            return LaneCheckResult(
                status=LaneCheckStatus.ABSENT,
                message="",
                command=None,
                exit_code=None,
                stderr_tail=None,
            )

        # Untrusted origin -> ABSENT, silently. See _origin_is_trusted.
        if not _origin_is_trusted(resolved_cwd):
            return LaneCheckResult(
                status=LaneCheckStatus.ABSENT,
                message="",
                command=None,
                exit_code=None,
                stderr_tail=None,
            )

        # Parse the contract. A broken contract file is INVALID, not ERROR,
        # because the lane authored an unusable specification.
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            return LaneCheckResult(
                status=LaneCheckStatus.INVALID,
                message=(
                    f"Lane check file is not valid JSON at {config_path!r}: {exc!r}. "
                    "Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                ),
                command=None,
                exit_code=None,
                stderr_tail=None,
            )

        if not isinstance(payload, dict):
            return LaneCheckResult(
                status=LaneCheckStatus.INVALID,
                message=(
                    f"Lane check file must contain a JSON object, got "
                    f"{type(payload).__name__}. Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                ),
                command=None,
                exit_code=None,
                stderr_tail=None,
            )

        # Rule 5: contract validation, each field its own INVALID.
        command = payload.get("command")
        if not isinstance(command, str) or not command.strip():
            return LaneCheckResult(
                status=LaneCheckStatus.INVALID,
                message=(
                    f"Lane check field 'command' must be a non-empty string, got "
                    f"{command!r}. Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                ),
                command=None,
                exit_code=None,
                stderr_tail=None,
            )

        expected_exit = payload.get("expected_exit", 0)
        if "expected_exit" in payload and not isinstance(expected_exit, int):
            return LaneCheckResult(
                status=LaneCheckStatus.INVALID,
                message=(
                    f"Lane check field 'expected_exit' must be an int, got "
                    f"{expected_exit!r}. Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                ),
                command=command,
                exit_code=None,
                stderr_tail=None,
            )

        timeout = payload.get("timeout", 120)
        if "timeout" in payload:
            if (
                not isinstance(timeout, (int, float))
                or timeout <= 0
                or timeout > 300
            ):
                return LaneCheckResult(
                    status=LaneCheckStatus.INVALID,
                    message=(
                        f"Lane check field 'timeout' must be a positive number <= 300, "
                        f"got {timeout!r}. Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                    ),
                    command=command,
                    exit_code=None,
                    stderr_tail=None,
                )

        scope_globs: list[str] | None = payload.get("scope_globs")
        if "scope_globs" in payload:
            if not isinstance(scope_globs, list) or not all(
                isinstance(glob, str) for glob in scope_globs
            ):
                return LaneCheckResult(
                    status=LaneCheckStatus.INVALID,
                    message=(
                        f"Lane check field 'scope_globs' must be a list of strings, got "
                        f"{scope_globs!r}. Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                    ),
                    command=command,
                    exit_code=None,
                    stderr_tail=None,
                )

        # Rule 4: tautology refusal. A command that cannot fail proves nothing.
        if _is_tautology(command):
            return LaneCheckResult(
                status=LaneCheckStatus.INVALID,
                message=(
                    f"Lane check command is a tautology and cannot prove anything: "
                    f"{command!r}. Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                ),
                command=command,
                exit_code=None,
                stderr_tail=None,
            )

        # Rule 6: scope. Missing or empty scope_globs means the check always
        # applies. A non-empty list with changed_paths=None also always applies:
        # an unknown change set must not silently disable a declared check.
        # Only when changed_paths is a non-empty list and no path matches any
        # glob do we return OUT_OF_SCOPE. We match with fnmatch.fnmatchcase on
        # the repo-relative path as given. Note that in fnmatch, '*' already
        # crosses '/', so 'scripts/**' and 'scripts/*' behave the same; we do
        # not rewrite patterns — entity-wise, the pattern is taken as declared.
        # The change set is resolved HERE and not before, which is the whole
        # point of `changed_paths_fn`: computing it costs three git subprocesses,
        # and a caller that passed the value eagerly would pay them on EVERY
        # termination in the fleet, contract or no contract — breaking the
        # innocence guarantee this module's docstring makes. A refuter of this
        # file caught exactly that: the first wiring evaluated the change set as
        # a function ARGUMENT, so the "absent contract costs one os.path.isfile"
        # claim was false at the only place it mattered, and the library's own
        # test could not see it because it passes the list directly.
        if scope_globs:
            if changed_paths is None and changed_paths_fn is not None:
                try:
                    changed_paths = changed_paths_fn()
                except Exception:
                    changed_paths = None  # unknown -> the check still applies
            if changed_paths is not None and len(changed_paths) > 0:
                matched = any(
                    any(fnmatch.fnmatchcase(path, glob) for glob in scope_globs)
                    for path in changed_paths
                )
                if not matched:
                    return LaneCheckResult(
                        status=LaneCheckStatus.OUT_OF_SCOPE,
                        message="",
                        command=command,
                        exit_code=None,
                        stderr_tail=None,
                    )

        # Rule 7: run the declared command. shell=True is required because real
        # checks are pipelines (e.g. ``pytest a && ruff b``). The command comes
        # from a file inside the worktree the agent already controls and can
        # already run commands in, so this is not a privilege boundary and must
        # not be described as one.
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=resolved_cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            tail = _stderr_tail(exc.stderr)
            return LaneCheckResult(
                status=LaneCheckStatus.ERROR,
                message=(
                    f"Lane check timed out after {timeout}s: command={command!r}. "
                    f"Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)\n\nstderr tail:\n{tail}"
                ),
                command=command,
                exit_code=None,
                stderr_tail=tail,
            )
        except OSError as exc:
            return LaneCheckResult(
                status=LaneCheckStatus.ERROR,
                message=(
                    f"Lane check could not run: command={command!r}, error={exc!r}. "
                    "Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
                ),
                command=command,
                exit_code=None,
                stderr_tail=None,
            )

        if completed.returncode != expected_exit:
            tail = _stderr_tail(completed.stderr)
            return LaneCheckResult(
                status=LaneCheckStatus.FAIL,
                message=(
                    f"Lane check failed: command={command!r}, "
                    f"expected_exit={expected_exit}, actual_exit={completed.returncode}. "
                    f"Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)\n\nstderr tail:\n{tail}"
                ),
                command=command,
                exit_code=completed.returncode,
                stderr_tail=tail,
            )

        return LaneCheckResult(
            status=LaneCheckStatus.PASS,
            message="",
            command=command,
            exit_code=completed.returncode,
            stderr_tail=None,
        )

    except Exception as exc:  # Rule 10: never raise.
        # Any unexpected failure degrades to ERROR. ERROR still blocks, per
        # rule 2, because a lane that declared a check and then could not even
        # evaluate its contract must not end its turn silently.
        return LaneCheckResult(
            status=LaneCheckStatus.ERROR,
            message=(
                f"Lane check encountered an unexpected error: {exc!r}. "
                "Fix the check, or correct/remove .lane-check.json — both are things you can do from here. (LANE_CHECK_OFF=1 also bypasses, but it must be set in the environment that launches the harness, so it is the OPERATOR's escape, not yours.)"
            ),
            command=None,
            exit_code=None,
            stderr_tail=None,
        )


def blocks(result: LaneCheckResult) -> bool:
    """Return True if the lane check should prevent the turn from ending.

    This fails CLOSED on measurement failure. A lane that declared a check and
    then cannot run it must not end its turn reporting success; "could not
    measure" is not "measured fine". This is the opposite posture from the
    safety guards in this directory, which are imposed ON the agent and
    therefore fail open — a broken guard would wall the agent, so a guard that
    cannot run must let the turn proceed. Here the check is declared BY the
    lane ABOUT itself, and there is an explicit escape (LANE_CHECK_OFF=1).
    """
    return result.status in {
        LaneCheckStatus.FAIL,
        LaneCheckStatus.INVALID,
        LaneCheckStatus.ERROR,
    }
