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

The wider pattern (a teammate's fleet audit, 2026-08-31): of 5 launchd
wrappers on Pro that call `gh` at all, this is the ONLY one that never does a
plain `cd` — because it runs from an ephemeral worktree and uses `git -C`
for every git call, the single safest idiom available for `git`. That is
exactly what created this hole: removing the script's own need for a correct
cwd also removed the signal that its two `gh` calls still needed one. The
other 4 (all under scripts/ or scripts/codex/, none in this directory) each
do a plain top-level `cd` before their `gh` call and were unaffected.

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

Extended directory-wide (2026-08-31, teammate scope request) to every `.sh`
file directly in infra/launchagents/wrappers/ — see `_WRAPPERS_DIR` below for
why the scope stops at this one directory. A second independent review pass
(spalla-review) then found: a real false-positive trap in 2 actual files in
this directory (`command -v gh` presence checks — see
`_GH_PRESENCE_CHECK_RE`), a real false-negative trap not yet exercised by any
real file here (backtick command substitution hiding inside a dquoted
string — see the `btick` handling in `_blank_comments_and_strings`), and
three further gaps deliberately left unfixed and named at the bottom of this
file (none exercised by any real file in this directory today).

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

# Directory-wide floor (2026-08-31, teammate scope request): catch the NEXT
# wrapper with this same defect class, not just this one. Scoped
# deliberately to infra/launchagents/wrappers/*.sh (non-recursive — direct
# children only) and NOT scripts/ or ~/scripts/: a teammate audited all 216
# launchd-invoked programs on Pro and found 4 other gh-calling wrappers, all
# living under scripts/ or scripts/codex/ (independently re-verified — NONE
# are actually in this directory; several of the teammate's filenames/line
# numbers were also off, corrected in the PR body), each guarded by a plain
# top-level `cd` earlier in the file rather than --repo/-R or the
# `(cd && ...)` subshell idiom this checker recognizes — a shape this
# lexical scanner cannot see, so scanning scripts/ directory-wide would
# misjudge them as violations (this is exactly why that directory is
# deliberately OUT of scope here). Verified empirically that
# infra/launchagents/wrappers/ itself has no such case: of the *.sh files
# directly in this directory, only regulatory-watcher-run.sh has a real `gh`
# invocation. Two others (queue-baseline.sh, suite-growth-probe.sh) only
# `command -v gh` a binary-presence check — a REAL false-positive trap this
# checker used to have no defense against (see _GH_PRESENCE_CHECK_RE below,
# found scanning these two actual files, not hypothesized).
_WRAPPERS_DIR_REL = "infra/launchagents/wrappers"
_WRAPPERS_DIR = _REPO_ROOT / _WRAPPERS_DIR_REL

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

# A real, empirically-found false-positive trap (found scanning the actual
# directory this test now covers, not hypothesized):
#   if ! command -v gh >/dev/null 2>&1; then
# (infra/launchagents/wrappers/queue-baseline.sh:78 and
# suite-growth-probe.sh:95, both real files) — "gh" there is the ARGUMENT to
# a binary-presence check, not the command being invoked, but
# _GH_INVOCATION_RE cannot tell a command word from an argument word; it
# only recognizes "gh" as an isolated token followed by more text. Matches
# every POSIX presence-check idiom that takes a bare command name as its
# next word: `command -v`/`command -V`, `which`, `type` (optionally `-p`),
# `hash`. Checked against the text immediately BEFORE the "gh" match, so it
# is blind to what comes after (the redirect, the semicolon, an assignment
# capturing the result) — none of that matters, only what precedes "gh".
_GH_PRESENCE_CHECK_RE = re.compile(
    r"(?:\bcommand\s+-[vV]\s+|\bwhich\s+|\btype\s+(?:-p\s+)?|\bhash\s+)$"
)


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

    Two refinements added after cross-family adversarial review (agy /
    Gemini 3.1 Pro, non-Anthropic, 2026-08-31 — generator != grader on this
    very checker):

    1. A `$(...)` command substitution INSIDE a double-quoted string is
       live code, not string content — `summary="$(gh pr create --head
       x)"` really does invoke `gh`. The blanker now tracks a `cmdsub`
       frame (with its own bare-paren depth counter, so a nested plain
       subshell inside the substitution doesn't close it early) and
       leaves that frame's content UNBLANKED, popping back to `dquote`
       when its matching `)` is reached. Counter-example that used to slip
       past undetected, now caught: see `_GUILT_CMDSUB_INSIDE_DQUOTE`.
    2. That same tracking made a HEREDOC opened inside such a `$(...)` —
       exactly this file's own `-m "$(cat <<EOF ... EOF)"` commit-message
       idiom — a correctness trap: a heredoc body is plain text (no quote
       semantics at all), but treating it as ordinary "cmdsub" code would
       let a stray apostrophe in the body (this file's body really has
       one: "main checkout's tracked tree") open a single-quote that only
       closes at the next unrelated `'` anywhere later in the file,
       corrupting everything scanned in between. Heredocs are now detected
       explicitly and their bodies treated as fully opaque (blanked)
       regardless of any quote characters inside them, ending at the
       physical line that matches the delimiter exactly (`<<-` strips
       leading tabs from that comparison, matching real shell). See
       `test_heredoc_with_apostrophe_in_body_does_not_corrupt_the_scan`.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    # Stack of open lexical frames. Each is ("code" | "comment" | "squote"
    # | "dquote" | "cmdsub", depth) — `depth` is only meaningful for
    # "cmdsub" (see above): it starts at 1 for the "$("'s own paren and
    # counts additional bare "(" seen directly inside this substitution,
    # so the matching ")" pops the RIGHT frame instead of an inner nested
    # subshell's ")" closing us prematurely (agy's counter-example 2).
    stack: list[list[object]] = [["code", None]]

    while i < n:
        ch = text[i]
        mode = stack[-1][0]

        if ch == "\n":
            if mode == "comment":
                stack.pop()
            out.append("\n")
            i += 1
            continue

        if mode == "comment":
            out.append(" ")
            i += 1
            continue

        if mode == "squote":
            out.append(" ")
            if ch == "'":
                stack.pop()
            i += 1
            continue

        if mode == "dquote":
            if ch == "\\" and i + 1 < n and text[i + 1] != "\n":
                out.append("  ")
                i += 2
                continue
            if ch == '"':
                stack.pop()
                out.append(" ")
                i += 1
                continue
            if ch == "$" and i + 1 < n and text[i + 1] == "(":
                # Live code starts here — do NOT blank it (agy gap 1).
                stack.append(["cmdsub", 1])
                out.append("$(")
                i += 2
                continue
            if ch == "`":
                # Live code starts here too — the OLDER command-substitution
                # syntax, same class of gap as `$(` above, found
                # independently by a second cross-family reviewer
                # (spalla-review, 2026-08-31):
                # `echo "...` + backtick + `gh pr create --head feat` +
                # backtick + `..."` is a real invocation hiding inside a
                # dquoted string. Simpler than cmdsub: no paren-balancing,
                # terminates at the next UNESCAPED backtick (nested backtick
                # substitution requires escaping the inner backticks with
                # `\`, which "btick" mode below preserves as a 2-char
                # passthrough so an escaped backtick is never mistaken for
                # the closing one). Deliberately does NOT special-case `#`
                # comments or nested quotes inside the backtick span (an
                # already-rare shape made rarer still by nesting something
                # else inside it) — a named, accepted simplification, not a
                # silent one; see the residual-risk note near the bottom of
                # this file.
                stack.append(["btick", None])
                out.append("`")
                i += 1
                continue
            out.append(" ")
            i += 1
            continue

        if mode == "btick":
            if ch == "\\" and i + 1 < n and text[i + 1] != "\n":
                out.append(text[i : i + 2])
                i += 2
                continue
            if ch == "`":
                stack.pop()
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
            continue

        # mode is "code" or "cmdsub" here: a live-code context. Heredocs
        # can start in either (agy gap 2's fix applies uniformly).
        heredoc = _HEREDOC_START_RE.match(text, i)
        if heredoc:
            delimiter = heredoc.group(1) or heredoc.group(2) or heredoc.group(3)
            strip_tabs = text[i : i + 3] == "<<-"
            out.append(text[i : heredoc.end()])
            i = heredoc.end()
            nl = text.find("\n", i)
            if nl == -1:
                out.append(text[i:])
                i = n
            else:
                out.append(text[i : nl + 1])
                i = nl + 1
            while i < n:
                line_end = text.find("\n", i)
                line = text[i:line_end] if line_end != -1 else text[i:]
                candidate = line.lstrip("\t") if strip_tabs else line
                if candidate == delimiter:
                    out.append(line)
                    if line_end != -1:
                        out.append("\n")
                        i = line_end + 1
                    else:
                        i = n
                    break
                out.append(" " * len(line))
                if line_end != -1:
                    out.append("\n")
                    i = line_end + 1
                else:
                    i = n
            continue
        if ch == "#":
            stack.append(["comment", None])
            out.append(" ")
            i += 1
            continue
        if ch == "'":
            stack.append(["squote", None])
            out.append(" ")
            i += 1
            continue
        if ch == '"':
            stack.append(["dquote", None])
            out.append(" ")
            i += 1
            continue
        if mode == "cmdsub":
            if ch == "(":
                stack[-1][1] = stack[-1][1] + 1
                out.append(ch)
                i += 1
                continue
            if ch == ")":
                depth = stack[-1][1] - 1
                if depth <= 0:
                    stack.pop()
                else:
                    stack[-1][1] = depth
                out.append(ch)
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


#: `<<EOF`, `<<-EOF`, `<<'EOF'`, `<<"EOF"` — the delimiter is group 1
#: (single-quoted), group 2 (double-quoted) or group 3 (bare word).
_HEREDOC_START_RE = re.compile(r"<<-?\s*(?:'([^']*)'|\"([^\"]*)\"|([A-Za-z_][A-Za-z0-9_]*))")


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
    (`(cd "$REGWATCH_REPO_ROOT" && git show ...)`).

    Walks a paren stack rather than `rfind("(")` + "any ')' after it means
    closed": found wrong by cross-family review (agy/Gemini, 2026-08-31) —
    `(cd "$_wt" && (echo init) && gh pr view 123)` has an unrelated nested
    subshell BEFORE the `gh` call; its own closing ')' made the old check
    conclude the outer group had already closed, and flag a legitimately
    cd-guarded call as a violation. The innermost STILL-OPEN paren is what
    matters, not the most recently seen one.
    """
    stack: list[int] = []
    for idx, ch in enumerate(prefix):
        if ch == "(":
            stack.append(idx)
        elif ch == ")" and stack:
            stack.pop()
    if not stack:
        return False
    segment = prefix[stack[-1] :]
    return bool(re.match(r"\(\s*cd\b", segment)) and "&&" in segment


def _iter_gh_invocations(blanked_text: str):
    """Yield (start_no, logical_line, match) for every `gh` occurrence in
    already-blanked text that is a REAL invocation — i.e. `gh` is not merely
    the argument to a binary-presence check (`command -v gh`, `which gh`,
    `type gh`, `hash gh` — see `_GH_PRESENCE_CHECK_RE`). Shared by
    `find_unguarded_gh_calls` and the exactly-N-invocations sanity test so
    the two can never silently drift apart on what counts as "a gh call"."""
    for start_no, logical in _iter_logical_lines(blanked_text):
        for m in _GH_INVOCATION_RE.finditer(logical):
            if _GH_PRESENCE_CHECK_RE.search(logical[: m.start()]):
                continue
            yield start_no, logical, m


def find_unguarded_gh_calls(text: str) -> list[tuple[int, str]]:
    """Return (line_number, line_text) for every REAL `gh` invocation in
    `text` (see `_iter_gh_invocations` — a bare presence check like
    `command -v gh` is not a violation, it doesn't invoke gh at all) that
    carries NEITHER `--repo`/`-R` on its own logical command NOR sits
    lexically inside a `(cd ... && ...)` subshell. Comments and quoted-string
    content are excluded from the scan (see `_blank_comments_and_strings`).
    """
    blanked = _blank_comments_and_strings(text)
    raw_lines = text.split("\n")
    violations: list[tuple[int, str]] = []
    for start_no, logical, m in _iter_gh_invocations(blanked):
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

# agy/Gemini adversarial-review finding 1 (2026-08-31): a `gh` invocation
# living inside a `$(...)` command substitution THAT ITSELF sits inside a
# double-quoted string is live code, not string content — the earlier
# blanker treated all double-quoted content as inert and missed it.
_GUILT_CMDSUB_INSIDE_DQUOTE = (
    '    summary="PR opened: $(gh pr create --head feat)"\n'
)

# agy/Gemini adversarial-review finding 2 (2026-08-31): an unrelated nested
# subshell BEFORE the gh call, inside the same cd-guard, used to make the
# naive "last '(' with no ')' after it" check conclude the outer group had
# already closed — a false-positive violation on a call that IS legitimately
# guarded.
_INNOCENCE_NESTED_SUBSHELL_BEFORE_GH = (
    '    (cd "$_wt" && (echo init) && gh pr view 123)\n'
)

# The trap fixing finding 1 could have introduced: this file's OWN real
# commit-message heredoc, MINIMIZED but keeping the one apostrophe that
# matters ("checkout's") and a `gh`-free body — a naive "cmdsub is just
# code" treatment would open a spurious single-quote on that apostrophe
# and only close it at the next unrelated "'" anywhere later in the text,
# corrupting the scan for everything in between.
_HEREDOC_WITH_APOSTROPHE = (
    '    git -C "$_wt" commit -m "$(cat <<EOF\n'
    "chore: promote delta\n"
    "\n"
    "main checkout's tracked tree stays untouched by this commit.\n"
    "EOF\n"
    '    )" >> "$LOG" 2>&1\n'
    "    if gh pr merge \"$_pr_num\" --auto; then\n"
    "        echo ok\n"
    "    fi\n"
)

# spalla-review adversarial-review finding (2026-08-31, second independent
# pass after agy's round): the OLDER backtick command-substitution syntax
# has the exact same dquote-hiding gap `$(...)` had before agy's fix —
# _blank_comments_and_strings only special-cased `$(`, never a bare `` ` ``.
_GUILT_GH_BACKTICK_INSIDE_DQUOTE = 'summary="PR opened: `gh pr create --head feat`"\n'

# The real, empirically-found false-positive trap (not hand-imagined): both
# fixtures below are minimized copies of REAL lines in
# infra/launchagents/wrappers/queue-baseline.sh:78 and
# suite-growth-probe.sh:95 respectively — "gh" as the argument to a
# binary-presence check, not an invocation. See the real-file regression
# test near the bottom of this file for the un-minimized originals.
_INNOCENCE_COMMAND_DASH_V_PRESENCE_CHECK = (
    'if ! command -v gh >/dev/null 2>&1; then\n'
    '    log "FATAL: gh CLI not on PATH"\n'
    "    exit 78\n"
    "fi\n"
)
_INNOCENCE_WHICH_PRESENCE_CHECK = 'GH_PATH=$(which gh) || exit 1\n'
_INNOCENCE_TYPE_DASH_P_PRESENCE_CHECK = 'if type -p gh >/dev/null; then echo found; fi\n'


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


def test_guilt_gh_inside_cmdsub_inside_dquote_is_flagged() -> None:
    """agy/Gemini finding 1: a live `gh` invocation must not hide behind an
    enclosing double-quoted string just because it sits inside `$(...)`."""
    violations = find_unguarded_gh_calls(_GUILT_CMDSUB_INSIDE_DQUOTE)
    assert len(violations) == 1, violations
    assert "gh pr create" in violations[0][1]


def test_innocence_nested_subshell_before_gh_still_passes() -> None:
    """agy/Gemini finding 2: an unrelated nested subshell earlier in the
    same cd-guarded group must not make the outer guard look closed."""
    assert find_unguarded_gh_calls(_INNOCENCE_NESTED_SUBSHELL_BEFORE_GH) == []


def test_heredoc_with_apostrophe_in_body_does_not_corrupt_the_scan() -> None:
    """The fix for finding 1 (treating a dquote-nested $(...) as live code)
    could have reintroduced a worse bug: this file's own commit-message
    heredoc contains a real apostrophe ("checkout's") that must NOT be
    read as a single-quote opening — if it were, everything after it up to
    the next unrelated "'" anywhere in the text would be silently
    swallowed, and the real `gh pr merge` call below would vanish instead
    of being correctly flagged."""
    violations = find_unguarded_gh_calls(_HEREDOC_WITH_APOSTROPHE)
    assert len(violations) == 1, violations
    assert "gh pr merge" in violations[0][1]


def test_guilt_gh_inside_backtick_inside_dquote_is_flagged() -> None:
    """spalla-review finding: a live `gh` invocation must not hide behind an
    enclosing double-quoted string just because it sits inside backticks —
    the older command-substitution syntax, same class of gap as agy's
    finding 1 (which only covered `$(...)`)."""
    violations = find_unguarded_gh_calls(_GUILT_GH_BACKTICK_INSIDE_DQUOTE)
    assert len(violations) == 1, violations
    assert "gh pr create" in violations[0][1]


def test_innocence_command_dash_v_presence_check_is_not_flagged() -> None:
    """The real false-positive trap found in
    infra/launchagents/wrappers/queue-baseline.sh:78 and
    suite-growth-probe.sh:95 — `command -v gh` checks whether the binary
    exists, it does not invoke it."""
    assert find_unguarded_gh_calls(_INNOCENCE_COMMAND_DASH_V_PRESENCE_CHECK) == []


def test_innocence_which_presence_check_is_not_flagged() -> None:
    assert find_unguarded_gh_calls(_INNOCENCE_WHICH_PRESENCE_CHECK) == []


def test_innocence_type_dash_p_presence_check_is_not_flagged() -> None:
    assert find_unguarded_gh_calls(_INNOCENCE_TYPE_DASH_P_PRESENCE_CHECK) == []


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
    count = sum(1 for _ in _iter_gh_invocations(blanked))
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


# --- directory-wide floor: catches the NEXT wrapper, not just this one -----


def test_all_wrappers_in_directory_have_no_unguarded_gh_calls() -> None:
    """Directory-wide floor (teammate scope request, 2026-08-31): every
    `.sh` file directly inside infra/launchagents/wrappers/ — not just the
    one this PR fixes — must carry the same invariant. Deliberately NOT
    recursive (`glob("*.sh")`, not `glob("**/*.sh")`) and deliberately NOT
    extended to scripts/ or ~/scripts/ — see the module-level comment next
    to `_WRAPPERS_DIR` for why. Reports every offending file, not just the
    first, so a future failure names its actual cause immediately instead
    of stopping at whichever file glob() happened to yield first."""
    sh_files = sorted(_WRAPPERS_DIR.glob("*.sh"))
    assert len(sh_files) > 0, (
        f"{_WRAPPERS_DIR_REL} matched zero *.sh files — the glob or the "
        f"path itself has drifted, this test is checking nothing"
    )
    violations_by_file: dict[str, list[tuple[int, str]]] = {}
    for sh_file in sh_files:
        text = sh_file.read_text(encoding="utf-8", errors="replace")
        violations = find_unguarded_gh_calls(text)
        if violations:
            violations_by_file[str(sh_file.relative_to(_REPO_ROOT))] = violations
    assert violations_by_file == {}, violations_by_file


def test_only_regulatory_watcher_has_real_gh_invocations_in_this_directory() -> None:
    """Precision floor, mirroring
    test_current_wrapper_still_has_exactly_two_gh_invocations's "not just
    >=N but ==N" principle: pins the CURRENT empirical shape of this
    directory (verified 2026-08-31 by independent re-investigation — the
    teammate's original audit named 4 other gh-calling wrappers, but none
    are actually located in this directory; see the PR body for the
    corrections) so this file's directory-wide coverage cannot silently rot
    into "zero violations because nothing was scanned". If this ever fails
    because a SECOND wrapper started calling `gh` for real, that is not a
    bug in this test — update the expectation deliberately and confirm the
    new caller is actually guarded, don't just widen this list."""
    sh_files = sorted(_WRAPPERS_DIR.glob("*.sh"))
    files_with_real_gh_calls = []
    for sh_file in sh_files:
        text = sh_file.read_text(encoding="utf-8", errors="replace")
        blanked = _blank_comments_and_strings(text)
        if list(_iter_gh_invocations(blanked)):
            files_with_real_gh_calls.append(str(sh_file.relative_to(_REPO_ROOT)))
    assert files_with_real_gh_calls == [_WRAPPER_REL], files_with_real_gh_calls


def test_real_presence_check_files_are_not_falsely_flagged() -> None:
    """The concrete counter-example that justified `_GH_PRESENCE_CHECK_RE`,
    read from disk (not a hand-fixture): both files are real, both are
    already covered by the directory-wide test above, but this test pins
    them BY NAME so a regression here fails with an unmistakable cause
    instead of vanishing into the directory-wide test's aggregate dict."""
    for rel in (
        "infra/launchagents/wrappers/queue-baseline.sh",
        "infra/launchagents/wrappers/suite-growth-probe.sh",
    ):
        path = _REPO_ROOT / rel
        assert path.is_file(), f"{rel} no longer exists — update this pin"
        text = path.read_text(encoding="utf-8")
        assert "command -v gh" in text, (
            f"{rel} no longer contains the presence-check shape this test "
            f"pins — update this test deliberately if the file changed"
        )
        assert find_unguarded_gh_calls(text) == []


# --- named, deliberately unfixed residual gaps (spalla-review, 2026-08-31) -
#
# Found by a second independent cross-family-adjacent review pass, none
# exercised by any real file in infra/launchagents/wrappers/ today (verified
# — no `case` statement, no backtick-in-dquote gh call, no two heredocs on
# one physical line anywhere in the 53 *.sh files this directory holds).
# Documented, not silently accepted (family #3 doctrine): a future counter-
# example that actually appears in a real file is a bug report against this
# checker, not a surprise.
#
#   1. A `case "$x" in pattern)` arm's pattern-terminating `)` inside a
#      `(cd ... && ...)` guard is not a real paren-close, but
#      `_in_cd_subshell`'s stack-walk cannot distinguish it from one — it
#      would pop the guard's own open paren early, false-positiving a
#      legitimately-guarded `gh` call that appears after the `case` block.
#   2. `_REPO_FLAG_RE` is pure text-presence search, not argv-aware: a `gh`
#      command whose `--repo` appears as a redirect target rather than an
#      actual flag (e.g. `gh pr create --head feat 2> --repo`) would be
#      misread as guarded.
#   3. Two heredocs opened on the same physical line
#      (`cmd1 <<EOF1 && cmd2 <<EOF2`) — only the first body is detected and
#      blanked; the second is scanned as ordinary code, so prose in it
#      mentioning "gh pr create" could be misflagged.
