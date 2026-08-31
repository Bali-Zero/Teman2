"""Guard: every `gh` invocation in the regulatory-watcher wrapper must carry an
explicit repository context.

Context (2026-08-31, measured on Pro from `~/logs/regulatory-watcher.log`, not
from the code): `promote_delta_via_pr()` in
infra/launchagents/wrappers/regulatory-watcher-run.sh makes every `git` call
cwd-independent (`git -C "$_wt" ...`) but left its two `gh` calls (`gh pr
create` line ~379, `gh pr merge --auto` line ~392 in the fixed file) to
inherit launchd's cwd, which is not a git checkout. `gh` cannot resolve which
repo it targets from that cwd and fails resolution before ever reaching the
GitHub API:

    failed to run git: fatal: not a git repository (or any of the parent
    directories): .git

— reproduced in the log for TEN consecutive days (2026-08-21..31), every day
right after the branch push succeeded. Cwd-safety had been applied per TOOL
(every `git` invocation), not per REQUIREMENT ("this command needs to know
which repo it is in") — the two `gh` calls were simply missed by that pattern.

Proven live (non-destructive, cwd=/tmp, a nonexistent probe branch so nothing
could actually be created):
    $ (cd /tmp && gh pr create --repo Bali-Zero/Teman2 --head probe-xyz \\
         --base main --title t --body b)
    pull request create failed: GraphQL: Head sha can't be blank, Base sha
    can't be blank, No commits between main and probe-nonexistent-branch-xyz,
    Head ref must be a branch (createPullRequest)
— reaches the GraphQL API and fails on the fake branch, not on repo
resolution. `--repo`/`-R` is `gh`'s own cwd-independent form (also supported
by `gh pr merge`), matching the existing convention in scripts/lane_ship.sh.

This test pins the INVARIANT ("every `gh` call in this wrapper names its repo
— either `--repo`/`-R` on the same logical command, or lexically inside a
`(cd ... && ...)` subshell, the idiom this same file already uses for `git`"),
not a literal string — see cicatrix-superscar.md family #3 (guard-over-match /
under-match): a guard here needs both a GUILT case (would it have caught the
real bug?) and an INNOCENCE case (does a legitimately-guarded call still
pass?), or it is worth nothing.

No network: everything below reads local text — either the wrapper file on
disk, hand-written fixtures, or a historical blob from THIS repo's own git
object store (`git show <pinned SHA>:<path>`, a local read once the commit is
in history — no fetch performed by the test).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER_REL = "infra/launchagents/wrappers/regulatory-watcher-run.sh"
_WRAPPER = _REPO_ROOT / _WRAPPER_REL

# origin/main's tip immediately before this fix (captured 2026-08-31, the
# commit named in the mandate this test was written to satisfy). Pinned by
# SHA, not the floating `origin/main` ref: the ref moves past the fix the
# moment this PR merges, but a commit object never changes, so this stays a
# valid, permanently-red-against-the-old-bug regression pin forever — where a
# `git show origin/main:...`-based test would silently degrade into a no-op
# (always green, nothing left to catch) the instant this PR lands.
# Verified live 2026-08-31: `git show <this sha>:infra/launchagents/wrappers/
# regulatory-watcher-run.sh` still has both calls with no --repo/-R and no
# enclosing `(cd ... && ...)` subshell.
_PRE_FIX_SHA = "f70d7d4c5cee1b0feb7ee191871f00b176ce9673"

# --- the checker (invariant, not a string match) --------------------------

# "gh" as a command word: not glued onto a preceding word/dot/hyphen char (so
# "high", "github.io" as a bareword, "foo-gh" don't match; a path prefix like
# "/opt/homebrew/bin/gh" DOES, since "/" is not excluded) and followed by
# whitespace then a non-space subcommand token.
_GH_INVOCATION_RE = re.compile(r"(?<![\w.-])gh(?=\s+\S)")
_REPO_FLAG_RE = re.compile(r"--repo\b|(?<![\w-])-R(?=\s|$)")
_SEPARATOR_RE = re.compile(r"&&|\|\||;|\|")


def _blank_comments_and_strings(text: str) -> str:
    """Replace shell comment bodies and quoted-string CONTENTS with spaces,
    preserving every newline (line numbers stay meaningful) and every other
    character (so `gh`, `--repo`, `(`, `cd`, `&&` stay visible to the scan).

    Single-pass over the whole text, not line-by-line: a quote that spans
    multiple physical lines — e.g. this very file's own
    `commit -m "$(cat <<EOF ... EOF)"` commit-message heredoc — must not leak
    its body into "code" context just because a naive per-line scanner loses
    the open-quote state at each newline. Without this, an unrelated mention
    of "gh" inside prose (a log message, a comment, a commit body) would
    register as a fake invocation — the over-match failure mode family #3
    warns about, mirrored here as under-guard against false alarms.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    in_squote = False
    in_dquote = False
    in_comment = False
    while i < n:
        ch = text[i]
        if ch == "\n":
            in_comment = False  # comments end at newline; quotes do not
            out.append("\n")
            i += 1
            continue
        if in_comment:
            out.append(" ")
            i += 1
            continue
        if in_squote:
            out.append(" ")
            if ch == "'":
                in_squote = False
            i += 1
            continue
        if in_dquote:
            if ch == "\\" and i + 1 < n and text[i + 1] != "\n":
                out.append(" ")
                i += 1
                out.append(" ")
                i += 1
                continue
            if ch == '"':
                in_dquote = False
            out.append(" ")
            i += 1
            continue
        # Not inside any quote/comment right now.
        if ch == "#":
            in_comment = True
            out.append(" ")
            i += 1
            continue
        if ch == "'":
            in_squote = True
            out.append(" ")
            i += 1
            continue
        if ch == '"':
            in_dquote = True
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _iter_logical_lines(blanked_text: str) -> list[tuple[int, str]]:
    """Join `\\`-continued physical lines into one logical line each,
    returning (1-indexed starting line number, joined text)."""
    raw = blanked_text.split("\n")
    result: list[tuple[int, str]] = []
    i = 0
    n = len(raw)
    while i < n:
        start_no = i + 1
        buf = raw[i]
        while buf.rstrip().endswith("\\") and i + 1 < n:
            buf = buf.rstrip()[:-1] + " " + raw[i + 1]
            i += 1
        result.append((start_no, buf))
        i += 1
    return result


def _in_cd_subshell(prefix: str) -> bool:
    """True if `prefix` (everything on the logical line before the `gh`
    occurrence) ends inside a still-open `(cd ... && ...` subshell — the
    idiom this file already uses for every `git` call in the same function
    (`(cd "$REGWATCH_REPO_ROOT" && git show ...)`)."""
    last_open = prefix.rfind("(")
    if last_open == -1:
        return False
    span = prefix[last_open:]
    if ")" in span:
        return False  # that subshell already closed before our gh call
    return bool(re.search(r"\(\s*cd\b.*&&", span))


def find_unguarded_gh_calls(text: str) -> list[tuple[int, str]]:
    """Return (line_number, line_text) for every `gh` invocation in `text`
    that carries NEITHER `--repo`/`-R` on its own logical command NOR sits
    lexically inside a `(cd ... && ...)` subshell. Comments and quoted-string
    content are excluded from the scan (see `_blank_comments_and_strings`).
    """
    blanked = _blank_comments_and_strings(text)
    raw_lines = text.split("\n")
    violations: list[tuple[int, str]] = []
    for start_no, logical in _iter_logical_lines(blanked):
        for m in _GH_INVOCATION_RE.finditer(logical):
            start = m.start()
            sep = _SEPARATOR_RE.search(logical, start)
            segment = logical[start : sep.start() if sep else len(logical)]
            if _REPO_FLAG_RE.search(segment):
                continue
            if _in_cd_subshell(logical[:start]):
                continue
            violations.append((start_no, raw_lines[start_no - 1].strip()))
    return violations


# --- guilt fixtures: hand-pinned, independent of any moving git ref -------

_GUILT_GH_PR_CREATE = (
    '    _pr_url=$(gh pr create --base main --head "$_branch" \\\n'
    '        --title "chore(regulatory): promote ${DATE} delta" \\\n'
    '        --body "Automated promotion of $_rel." \\\n'
    '        2>>"$LOG")\n'
)

_GUILT_GH_PR_MERGE = (
    '    if gh pr merge "$_pr_num" --auto >> "$LOG" 2>&1; then\n'
    '        echo ok\n'
    "    fi\n"
)

# The exact false-positive trap present in the real wrapper: an echo message
# that MENTIONS "gh pr create" twice as plain text, inside one double-quoted
# string. A checker that greps for the substring "gh pr create" anywhere in
# the file, rather than for an actual invocation, would misfire here.
_INNOCENCE_ECHO_MENTIONING_GH = (
    '        echo "[$(date)] promote: gh pr create failed — branch $_branch '
    'pushed, PR NOT opened, manual recovery: gh pr create --head $_branch" '
    '>> "$LOG"\n'
)

_INNOCENCE_REPO_FLAG = (
    '    _pr_url=$(gh pr create --repo "$REGWATCH_GH_REPO" --base main '
    '--head "$_branch" \\\n'
    '        --title "chore(regulatory): promote ${DATE} delta" \\\n'
    '        2>>"$LOG")\n'
)

_INNOCENCE_SHORT_R_FLAG = '    if gh pr merge "$_pr_num" -R "$REGWATCH_GH_REPO" --auto; then\n'

_INNOCENCE_CD_SUBSHELL = (
    '    _n=$(cd "$_wt" && gh pr view "$_pr_num" --json number -q .number)\n'
)


def test_guilt_bare_gh_pr_create_is_flagged() -> None:
    violations = find_unguarded_gh_calls(_GUILT_GH_PR_CREATE)
    assert len(violations) == 1, violations
    assert "gh pr create" in violations[0][1]


def test_guilt_bare_gh_pr_merge_is_flagged() -> None:
    violations = find_unguarded_gh_calls(_GUILT_GH_PR_MERGE)
    assert len(violations) == 1, violations
    assert "gh pr merge" in violations[0][1]


def test_innocence_echo_mentioning_gh_is_not_flagged() -> None:
    """The over-match trap: prose that says "gh pr create failed" is not a
    `gh` invocation and must never be flagged."""
    assert find_unguarded_gh_calls(_INNOCENCE_ECHO_MENTIONING_GH) == []


def test_innocence_repo_flag_on_same_command_passes() -> None:
    assert find_unguarded_gh_calls(_INNOCENCE_REPO_FLAG) == []


def test_innocence_short_r_flag_passes() -> None:
    assert find_unguarded_gh_calls(_INNOCENCE_SHORT_R_FLAG) == []


def test_innocence_cd_subshell_form_passes() -> None:
    assert find_unguarded_gh_calls(_INNOCENCE_CD_SUBSHELL) == []


def test_checker_does_not_flag_a_file_with_no_gh_calls_at_all() -> None:
    assert find_unguarded_gh_calls("echo hello\ngit status\n") == []


# --- the real thing: the wrapper as it exists on disk ----------------------


def test_current_wrapper_has_no_unguarded_gh_calls() -> None:
    """The actual fix this test was written to guard: both real `gh` call
    sites in the live wrapper must carry --repo (or an equivalent form)."""
    text = _WRAPPER.read_text(encoding="utf-8")
    violations = find_unguarded_gh_calls(text)
    assert violations == [], (
        f"{_WRAPPER_REL} has {len(violations)} gh call(s) with no explicit "
        f"repo context (see module docstring — this is the exact class that "
        f"broke PR promotion for ten days): {violations}"
    )


def test_current_wrapper_still_has_exactly_two_gh_invocations() -> None:
    """Sanity floor: if this drops to 0, the anchors this suite (and the
    mandate) reasons about have drifted and the guard above would be
    checking nothing. Not >=2 — exactly 2, so a THIRD unguarded call added
    later still trips the assertion above, not this one silently absorbing
    it as "more of the same two"."""
    text = _WRAPPER.read_text(encoding="utf-8")
    blanked = _blank_comments_and_strings(text)
    count = sum(
        len(list(_GH_INVOCATION_RE.finditer(logical)))
        for _, logical in _iter_logical_lines(blanked)
    )
    assert count == 2, (
        f"expected exactly 2 gh invocations (pr create, pr merge) in "
        f"{_WRAPPER_REL}, found {count} — update this test's expectations "
        f"deliberately if a new gh call was added"
    )


# --- the regression pin: proves this guard would have caught the real bug --


def _read_historical_wrapper(sha: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{sha}:{_WRAPPER_REL}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            f"cannot read {sha}:{_WRAPPER_REL} from local git history "
            f"(shallow clone missing this object?): {result.stderr.strip()}"
        )
    return result.stdout


def test_regression_pin_pre_fix_commit_fails_this_guard() -> None:
    """PROOF this guard is not vacuous: run it against the wrapper exactly as
    it stood at `_PRE_FIX_SHA` (origin/main's tip immediately before this
    fix) and confirm it goes RED — catching precisely the two call sites the
    live incident (ten days, zero PRs opened) came from.
    """
    historical = _read_historical_wrapper(_PRE_FIX_SHA)
    assert "gh pr create --base main" in historical, (
        "the pinned pre-fix SHA no longer matches the expected pre-fix text "
        "— re-verify _PRE_FIX_SHA against the actual fix commit"
    )
    violations = find_unguarded_gh_calls(historical)
    assert len(violations) == 2, (
        f"expected the pre-fix wrapper at {_PRE_FIX_SHA} to fail this guard "
        f"with exactly 2 unguarded gh calls (pr create + pr merge), got "
        f"{violations}"
    )
    joined = " ".join(v[1] for v in violations)
    assert "gh pr create" in joined and "gh pr merge" in joined, violations
