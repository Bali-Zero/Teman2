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
explained away, then confirmed against plain `git log` with no tool in the
loop (548/858 — the same number):

  * `mente` is a BARE SUBSTRING. 212 commits in that window contain
    `implemented`, `documented` or `commented`. It was meant to catch the
    Italian for "lies".
  * `lied` is the same bug again. 183 commits contain `applied`, `supplied`,
    `implied` or `multiplied`; exactly 6 contain the standalone word.
  * `claim` (295) and `correct(s|ed|ion)` (219) are not bugs but are ambient:
    this repo's whole vocabulary is claims and corrections, so they fire on
    commits that make a claim as readily as on commits that repair one.

Two substring collisions in a fourteen-alternative pattern is superscar #3
inside a KPI. THE PATTERN IS NOT EDITED HERE: v1 is pinned by the spec, and
tuning a heuristic until it reproduces a target is the exact failure the
"report only, never a target" rule exists to prevent — the number would then
measure the tuning. A v2 with word boundaries is a SPEC decision (what should
this KPI measure?), not an implementation one, and it belongs in its own PR
beside v1, never on top of it.

What ships instead is honesty at the point of use: every human run prints the
top contributing alternatives alongside the share, so the number cannot travel
without its composition, and anyone about to quote 63.8% sees `mente` and
`lied` carrying it.

BOTH BOUNDS MANDATORY, BOTH CLOSED. `--since`/`--until` pass straight to
`git log --since=... --until=...`; neither has a default, and omitting either is
refused (exit 2) — an open-ended window silently changes its answer as commits
land, which would make a frozen, citable number impossible. `git log` itself
prunes its walk assuming roughly date-monotonic history; a rebase/filter-branch
that leaves commit dates out of topological order can make it silently skip
in-window commits — a real repo's normal (squash-)merge history does not do
this, but a `--repo` pointed at rewritten history should be treated as suspect.

Usage: python3 scripts/correction_tax.py --since 2026-08-14 --until 2026-08-28
       [--heuristic v1] [--repo .] [--json] [--ledger-append PATH]

Exit codes: 0 always on a successful measurement (share is not pass/fail) · 1 git
log itself failed · 2 argparse's own code (missing bound, unknown --heuristic).
"""

from __future__ import annotations

import argparse
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
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    escaped = False
    for ch in pattern:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            current.append(ch)
            escaped = True
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

_RECORD_SEP = "\x1e"  # git commit messages cannot contain this byte


def _git_log_messages(repo: Path, since: str, until: str) -> list[str]:
    """One full message (``%B``, subject+body) per commit in [since, until)."""
    cmd = ["git", "-C", str(repo), "log", f"--since={since}", f"--until={until}",
           f"--pretty=tformat:%B{_RECORD_SEP}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except OSError as exc:
        raise RuntimeError(f"git log could not run: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(f"git log exit {result.returncode}: {result.stderr.strip()[:300]}")
    # tformat auto-appends "\n" after each record's own RECORD_SEP, leaving
    # one trailing artefact — drop it by CONTENT, never a fixed count, so a
    # genuine empty-message commit mid-list survives.
    parts = result.stdout.split(_RECORD_SEP)
    if parts and parts[-1].strip("\n") == "":
        parts = parts[:-1]
    return parts


def compute(repo: Path, since: str, until: str, heuristic: str) -> dict:
    """Return the correction-tax measurement for one window+heuristic."""
    pattern = HEURISTICS[heuristic]
    messages = _git_log_messages(repo, since, until)
    total = len(messages)
    corrections = sum(1 for msg in messages if pattern.search(msg))
    share = round(corrections / total, 3) if total else 0.0
    return {"window": {"since": since, "until": until}, "heuristic": heuristic,
            "corrections": corrections, "total": total, "share": share,
            "top_tokens": _token_contributions(messages, heuristic)}


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
    exists for the same (since, until, heuristic) key — idempotent, so
    re-running the same window twice never double-writes a trend line.
    Returns True if written, False if skipped as a duplicate.
    """
    w = result["window"]
    row = {"since": w["since"], "until": w["until"], "heuristic": result["heuristic"],
           "corrections": result["corrections"], "total": result["total"], "share": result["share"]}
    key = (row["since"], row["until"], row["heuristic"])
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (existing.get("since"), existing.get("until"), existing.get("heuristic")) == key:
                    return False
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return True


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
        print("  REPORT ONLY — never a target, never wired to a gate. See this "
              "script's docstring for what v1 does and does not measure.")

    if args.ledger_append:
        wrote = append_ledger(Path(args.ledger_append), result)
        note = "appended" if wrote else "skipped (duplicate since+until+heuristic already recorded)"
        print(f"ledger: {note} -> {args.ledger_append}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
