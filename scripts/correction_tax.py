#!/usr/bin/env python3
"""correction_tax.py — the correction tax: the share of the commit stream, over a
CLOSED window, that exists to repair a claim a PREVIOUS commit made.

Read-only against `git log`. Its only side effect is an optional JSONL ledger row
(`--ledger-append`) — no network, no database, nothing else on disk.

REPORT ONLY, NEVER A TARGET (adversarial review, HIGH, survives — MANDATORY). Never
wired into a merge gate, a required CI check, or council-composition, and must not
be optimised against: a correction-tax that goes DOWN because people stopped writing
honest correction commits — buried a fix in an unrelated commit instead of saying
"this corrects #NNNN" — is WORSE than one that goes up, because the same error rate
then travels unlabelled. No `--check`-style pass/fail flag exists on purpose; wiring
this into a gate needs its own Zero ruling (spec's "Needs-ruling carried" §3).

VERSIONED, ADDITIVE-ONLY HEURISTIC. `HEURISTICS` maps a version string to a
compiled, case-insensitive regex over each commit's full message (subject+body via
`%B`). Once shipped, a version's pattern is NEVER edited in place — v2 goes BESIDE
v1 as a new key, never over it, or the kill-switch ("if two heuristic revisions
move the number more than real change does, stop publishing") becomes meaningless.
An unrecognised `--heuristic` is refused by argparse's own `choices=` (exit 2,
names every known version).

HONEST LIMITS. Measures the WORDING of a commit message, never the WORK it did. A
repair that never uses any of these words is invisible (an unbounded false
negative). A commit that only MENTIONS one of these words without correcting
anything is a false positive counted anyway — the commit adding this very script
is itself an example — and `scripts/tests/test_correction_tax.py` pins that on
purpose rather than special-casing it away. A single window's value means little
alone; it is only a signal as a TREND across windows on the SAME heuristic version.

V1 IS NOT YET A USABLE KPI ON THIS CORPUS, AND THE MEASUREMENT SAYS SO. Run
against the exact frozen window the spec names (--since 2026-08-14 --until
2026-08-28), v1 reports 547/858 = 0.638. The spec cites a baseline of 106/866
(~12.2%). That is a FIVE-FOLD disagreement, and it was traced rather than
explained away:

  * `mente` is a BARE SUBSTRING. 212 commits in that window contain
    `implemented`, `documented` or `commented`. It was meant to catch the
    Italian for "lies".
  * `lied` is the same bug again. 183 commits contain `applied`, `supplied`,
    `implied` or `multiplied`; exactly 6 contain the standalone word.
  * `claim` (295) and `correct(s|ed|ion)` (219) are not bugs but are ambient:
    this repo's whole vocabulary is claims and corrections, so they fire on
    commits that make a claim as readily as on commits that repair one.

A SEPARATE, ONE-COMMIT DISCREPANCY, LEFT UNTRACED RATHER THAN LAUNDERED. The
same run was also checked against plain `git log` with no tool in the loop, and
that check reported 548/858 for the numerator — one MORE than the tool's own
547. An earlier draft of this docstring called that "the same number"; it is
not, and asserting it was is exactly the disease this KPI exists to cure. A
concrete mechanism was tried as the explanation (the record separator this
script used to split `git log`'s output on — `\x1e` — is NOT forbidden in a
commit message, verified empirically: `git commit -m "$(printf 'aa\x1ebb')")`
survives byte-for-byte into `%B`, so a single such commit would silently split
into two records and shift a count by one) and that mechanism IS real — fixed
below regardless — but it could not be CONNECTED to this specific 547-vs-548
case: the corpus underlying the original 858-commit total is not reproducible
from any git ref reachable today (re-walking history from the exact commit
that made the 858 claim, which is an immutable point since a commit's own
ancestry cannot change, gives 865 commits for the same window, not 858 — this
repo's commit dates do not track wall-clock authoring order tightly enough for
a "closed" window in the past to stay closed; a related but distinct risk from
the out-of-order-rewrite case already named below), and the live corpus at the
time of this fix contains zero commit messages carrying the old separator
byte in this window. So: 547 vs 548, they differ by one, and the cause of
THIS particular gap is UNTRACED — stated plainly rather than resolved by
narration.

Two substring collisions in a fourteen-alternative pattern is superscar #3
inside a KPI. THE PATTERN IS NOT EDITED HERE: v1 is pinned by the spec, and
tuning a heuristic until it reproduces a target is the exact failure the
"report only, never a target" rule exists to prevent — the number would then
measure the tuning. A v2 with word boundaries is a SPEC decision (what should
this KPI measure?), not an implementation one, and it belongs in its own PR
beside v1, never on top of it.

What ships instead is honesty at the point of use: every run — human or
`--json` — carries the breakdown and the report-only disclaimer WITH the
number, not beside it in a paragraph a machine consumer never reads (see
"BOTH BOUNDS MANDATORY" below for the same principle applied to the window,
and the `--json` section for what "carries with" means concretely).

BOTH BOUNDS MANDATORY, BOTH CLOSED. `--since`/`--until` pass straight to
`git log --since=... --until=...`; neither has a default, and omitting either is
refused (exit 2) — an open-ended window silently changes its answer as commits
land, which would make a frozen, citable number impossible. `git log` itself
prunes its walk assuming roughly date-monotonic history; a rebase/filter-branch
that leaves commit dates out of topological order can make it silently skip
in-window commits — a real repo's normal (squash-)merge history does not do
this, but a `--repo` pointed at rewritten history should be treated as suspect.

A CLOSED WINDOW WITH ZERO COMMITS IS REFUSED, NEVER MINTED AS 0/0. Transposed
bounds (`--since` after `--until`), a mistyped year, or a genuinely quiet repo
all make `git log` return nothing with exit 0 — that is not a measurement,
it is an empty query, and printing "0/0 = 0.000" would hand someone a citable
number for a window that was never actually read. `compute()` refuses this
(exit 1, same path as a `git log` failure) instead of returning a share, and
nothing is ever appended to `--ledger-append` for a window this refuses.

`--json` CARRIES ITS OWN DISCLAIMER. The breakdown-in-every-run principle
above only holds if the machine-readable path carries it too: a bare
`{"share": 0.638}` is exactly the number this script exists to make
un-quotable alone, and the report-only statement plus the "these overlap, do
not sum" warning on `top_tokens` are FIELDS of the JSON payload for that
reason, not just of the human-readable line. This does NOT make the share
impossible to gate on programmatically (`jq '.share > 0.5'` still works fine
on the same payload) — claiming otherwise would be the same kind of overclaim
this module exists to avoid. What it does is make the disclaimer travel WITH
the number instead of being left behind at the terminal.

LEDGER CONFLICTS FAIL LOUDLY, NEVER SILENTLY. `--ledger-append` is idempotent
on (since, until, heuristic) — but idempotent means "the SAME measurement
re-recorded is a no-op", not "any later measurement for this key is ignored".
A re-run over an already-closed window can legitimately compute a DIFFERENT
answer (a backdated merge landing inside a closed window is real git
behaviour on this repo — see above), and silently treating that as "already
recorded" would let a stale or wrong row sit in the trend line forever with
no signal that anything was ever wrong. A same-key row with DIFFERENT numbers
refuses (exit 1) instead of skipping. The check-then-append is also
serialised with an exclusive `flock` on the ledger file itself, re-checked
INSIDE the lock, so two concurrent runs over the same window cannot both see
"no existing row" and both append.

Usage: python3 scripts/correction_tax.py --since 2026-08-14 --until 2026-08-28
       [--heuristic v1] [--repo .] [--json] [--ledger-append PATH]

Exit codes: 0 always on a successful measurement (share is not pass/fail) · 1 git
log itself failed, the window contained zero commits, or a ledger row already
exists for this window+heuristic with DIFFERENT numbers · 2 argparse's own code
(missing bound, unknown --heuristic).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import subprocess
import sys
from pathlib import Path

# Additive only — see module docstring. Never tune v1's pattern in place.
HEURISTICS: dict[str, re.Pattern[str]] = {
    "v1": re.compile(
        r"recidiv|actually|was wrong|wrongly|false.positive|false.green|"
        r"mislabel|mente|lied|stale claim|correct(s|ed|ion)|retract|"
        r"W1[0-9][0-9]|claim",
        re.IGNORECASE,
    ),
}

def _split_alternatives(pattern: str) -> tuple[str, ...]:
    """Split a regex on its TOP-LEVEL `|` only.

    A naive `.split("|")` tears `correct(s|ed|ion)` into `correct(s`, `ed` and
    `ion)` — two of which are not valid regexes at all. Measured, not guessed:
    the naive version raised on this repo's own v1 pattern the first time it
    ran. Depth-tracking keeps grouped alternations whole.

    Also tracks bracket character classes (`[...]`): a `|`, `(` or `)` INSIDE
    a class is a literal character, not an alternation operator or a group
    boundary, and ignoring that is a real crash, not a theoretical one —
    reproduced with `a[|]b|c` (a depth tracker with no class-awareness yields
    `('a[', ']b', 'c')`, and `re.compile('a[')` raises
    `re.error: unterminated character set`) and with `x[(]|y` (yields
    `('x[(]|y',)` — one alternative where there should be two, because the
    literal `(` inside the class inflated the group-depth counter). v1's own
    pattern has no classes today, so this was LATENT: a future v2 (additive
    only — see module docstring) that adds one would hit it blind.

    Also handles the two POSIX bracket-expression positions where `]` is
    itself a literal character rather than the class terminator: immediately
    after the opening `[` (`[]]`) and immediately after a negating `^`
    (`[^]]`) — both verified to round-trip through `re.compile` unsplit.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    escaped = False
    # None outside a class; otherwise the ONE-character window in which a
    # literal `]` is still legal: "just_opened" right after `[`,
    # "after_caret" right after `[^`, "normal" everywhere else inside.
    class_state: str | None = None
    for ch in pattern:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            current.append(ch)
            escaped = True
            continue
        if class_state is not None:
            current.append(ch)
            if class_state == "just_opened" and ch == "^":
                class_state = "after_caret"
                continue
            if class_state in ("just_opened", "after_caret") and ch == "]":
                class_state = "normal"
                continue
            if ch == "]":
                class_state = None
            else:
                class_state = "normal"
            continue
        if ch == "[":
            class_state = "just_opened"
            current.append(ch)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return tuple(p for p in parts if p)


#: The same alternatives, listed separately so a share can be decomposed.
#: DERIVED FROM the pattern above, never re-typed: a second hand-kept copy of
#: a regex is a second thing to drift (this repo has scars for exactly that).
HEURISTIC_TOKENS: dict[str, tuple[str, ...]] = {
    version: _split_alternatives(pattern.pattern) for version, pattern in HEURISTICS.items()
}

#: Record TERMINATOR, not separator, and a NUL — the one byte git itself
#: forbids in a commit message (verified empirically: a raw NUL embedded in a
#: `commit-tree`-authored message is silently truncated by git before it is
#: even stored, so it can never appear mid-message the way the old `\x1e`
#: separator could — that byte is legal content and DID survive into `%B`,
#: which is precisely the bug this replaced). Prefixed to `%B`, not
#: appended, so a `tformat:` terminator can never be mistaken for a second
#: record's leading byte — see `_git_log_messages` for the exact split.
_RECORD_PREFIX = "%x00"

_DECODE_TIMEOUT_S = 120

# Git log itself failing, a decode it cannot recover from, or the process
# outrunning its own timeout all land in the same "could not read history"
# bucket — the caller (`compute`) does not need to distinguish them, and a
# `TimeoutExpired` left uncaught here would crash `main` instead of exiting 1
# through the existing RuntimeError path.
_GIT_LOG_FAILURE_EXC = (OSError, subprocess.TimeoutExpired)


def _git_log_messages(repo: Path, since: str, until: str) -> list[str]:
    """One full message (``%B``, subject+body) per commit in [since, until)."""
    cmd = ["git", "-C", str(repo), "log", f"--since={since}", f"--until={until}",
           f"--pretty=tformat:{_RECORD_PREFIX}%B"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=_DECODE_TIMEOUT_S, check=False,
        )
    except _GIT_LOG_FAILURE_EXC as exc:
        raise RuntimeError(f"git log could not run: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(f"git log exit {result.returncode}: {result.stderr.strip()[:300]}")
    # Every record is PREFIXED with a NUL, including the first — splitting on
    # NUL therefore always yields one empty leading element (dropped by
    # slicing, never by a content guess) followed by exactly one element per
    # commit. Verified empirically across 0/1/N commits: the split count is
    # always len(commits)+1, with element 0 always "".
    return result.stdout.split("\x00")[1:]


def compute(repo: Path, since: str, until: str, heuristic: str) -> dict:
    """Return the correction-tax measurement for one window+heuristic.

    A ZERO-COMMIT WINDOW IS NOT ONLY A TYPO. Measured at the gate: git returns
    ZERO commits for ``--until=2100-01-01`` on a repo whose commits are all in
    2026, while ``--until=2027-01-01`` returns all of them — a plausible
    far-future bound silently empties the window with exit 0 and no warning.
    So the refusal below is not merely a guard against transposed dates; it is
    the only thing standing between an ordinary-looking argument and a citable
    ``0/0 = 0.000`` in the trend ledger.

    Raises RuntimeError (never returns a share) when the window contains no
    commits at all — see module docstring's "CLOSED WINDOW WITH ZERO COMMITS"
    section: 0/0 is an unread window, not a measurement of zero.
    """
    pattern = HEURISTICS[heuristic]
    messages = _git_log_messages(repo, since, until)
    total = len(messages)
    if total == 0:
        raise RuntimeError(
            f"window {since}..{until} contains zero commits — refusing to "
            "report 0/0 as a measurement. Check the bounds: --since after "
            "--until, a mistyped year, or a --repo with no activity in this "
            "period all produce this. Not appended to any ledger."
        )
    corrections = sum(1 for msg in messages if pattern.search(msg))
    share = round(corrections / total, 3)
    return {"window": {"since": since, "until": until}, "heuristic": heuristic,
            "corrections": corrections, "total": total, "share": share,
            "top_tokens": _token_contributions(messages, heuristic),
            "report_only": (
                "never a target, never wired to a gate — see this script's "
                "module docstring for what this heuristic version does and "
                "does not measure"
            ),
            "top_tokens_overlap_note": (
                "top_tokens alternatives overlap by construction (one "
                "message can match several) and do NOT sum to corrections"
            )}


#: The alternatives of a heuristic's pattern, so a number can never travel
#: without its composition. This exists because of what v1 measured on the
#: spec's own frozen window: 547/858 = 63.8%, against a cited baseline of
#: ~12.2%. The single largest contributor is `mente` — a BARE SUBSTRING that
#: matches `implemented`, `documented` and `commented` (212 commits in that
#: window contain one of those words). A share that is five times its own
#: baseline because of a substring collision is not a trend line, and printing
#: it alone would be handing someone a number to quote.
def _token_contributions(messages: list[str], heuristic: str) -> list[list]:
    """How many messages each ALTERNATIVE of the pattern matches, descending.

    Overlapping by construction — one message can match several alternatives —
    so these do NOT sum to `corrections`. That is the point: the reader is
    meant to see WHICH words are carrying the number, not to re-derive it.
    """
    counts: list[list] = []
    for alt in HEURISTIC_TOKENS[heuristic]:
        sub = re.compile(alt, re.IGNORECASE)
        counts.append([alt, sum(1 for m in messages if sub.search(m))])
    # LISTS, not tuples, deliberately: `compute()`'s return value is emitted
    # verbatim as JSON, and json round-trips a tuple into a list. Returning a
    # shape JSON cannot preserve makes the in-memory result and the emitted
    # result differ — which is exactly what the round-trip test caught.
    return sorted(counts, key=lambda kv: kv[1], reverse=True)[:5]


def append_ledger(path: Path, result: dict) -> bool:
    """Append one JSONL row for ``result`` to ``path`` unless a row already
    exists for the same (since, until, heuristic) key with the SAME numbers
    — idempotent, so re-running the same window twice never double-writes a
    trend line. Returns True if written, False if skipped as a genuine
    duplicate.

    A same-key row with DIFFERENT numbers is a conflict, not a duplicate —
    raises RuntimeError rather than silently keeping the stale row (see
    module docstring's "LEDGER CONFLICTS FAIL LOUDLY" section). The
    check-then-append is serialised under an exclusive `flock` on `path`
    itself, taken BEFORE the existing rows are read, so two concurrent
    callers over the same window cannot both observe "no row yet" and both
    append.
    """
    w = result["window"]
    row = {"since": w["since"], "until": w["until"], "heuristic": result["heuristic"],
           "corrections": result["corrections"], "total": result["total"], "share": result["share"]}
    key = (row["since"], row["until"], row["heuristic"])

    path.touch(exist_ok=True)
    with path.open("r+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0)
            existing_row = None
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (existing.get("since"), existing.get("until"), existing.get("heuristic")) == key:
                    existing_row = existing
                    break
            if existing_row is not None:
                existing_numbers = (
                    existing_row.get("corrections"),
                    existing_row.get("total"),
                    existing_row.get("share"),
                )
                new_numbers = (row["corrections"], row["total"], row["share"])
                if existing_numbers == new_numbers:
                    return False
                raise RuntimeError(
                    f"ledger conflict at {path} for window {key}: existing row "
                    f"has corrections={existing_numbers[0]} total={existing_numbers[1]} "
                    f"share={existing_numbers[2]}, this run computed "
                    f"corrections={new_numbers[0]} total={new_numbers[1]} "
                    f"share={new_numbers[2]} — refusing to silently skip a stale "
                    "row or silently overwrite it"
                )
            fh.seek(0, 2)
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            return True
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Correction-tax share of the commit stream over a closed "
        "window. Report only — never a gate, never a target (see docstring)."
    )
    parser.add_argument("--since", required=True, help="Window start (git --since date). Mandatory.")
    parser.add_argument("--until", required=True, help="Window end (git --until date). Mandatory.")
    parser.add_argument("--heuristic", default="v1", choices=sorted(HEURISTICS),
                         help="Heuristic version (additive-only registry — see docstring).")
    parser.add_argument("--repo", default=".", help="Repo root to read git log from (default: cwd).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a human line.")
    parser.add_argument("--ledger-append", metavar="PATH",
                         help="Append one JSONL trend row for this window+heuristic to PATH (idempotent).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = compute(Path(args.repo), args.since, args.until, args.heuristic)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result))
    else:
        w = result["window"]
        print(f"correction-tax: {result['corrections']}/{result['total']} "
              f"= {result['share']:.3f} (heuristic {result['heuristic']}, "
              f"window {w['since']}..{w['until']})")
        # The breakdown is NOT optional output. A bare share invites quotation;
        # the top contributors are what make it interpretable, and on v1 they
        # are the reason the number is not yet a usable KPI.
        top = ", ".join(f"{tok}={n}" for tok, n in result["top_tokens"] if n)
        print(f"  top contributors (overlapping, do not sum): {top or 'none'}")

    # Printed on stderr UNCONDITIONALLY — including under --json, whose
    # stdout must stay pure machine-parseable JSON. This is the same
    # disclaimer `report_only`/`top_tokens_overlap_note` carry AS FIELDS of
    # the JSON payload itself (see module docstring's "--json CARRIES ITS
    # OWN DISCLAIMER"); printing it here too means a human watching the
    # terminal sees it even when stdout is being piped into `jq`.
    print(f"  {result['report_only']}. {result['top_tokens_overlap_note']}.",
          file=sys.stderr)

    if args.ledger_append:
        try:
            wrote = append_ledger(Path(args.ledger_append), result)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        note = "appended" if wrote else "skipped (duplicate since+until+heuristic already recorded)"
        print(f"ledger: {note} -> {args.ledger_append}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
