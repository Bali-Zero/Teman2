#!/usr/bin/env python3
"""Report whether the Autonomous Ops contract has lapsed, from its DECLARED date.

WHY THIS LIVES IN THE REPO, AND NOT IN THE HOOK
================================================
`AUTONOMOUS_OPS.md` promises that a contract older than 30 days drops the session
into conservative mode. The thing that was supposed to enforce that promise is a
SessionStart hook in `~/.claude/settings.json`, and it computes the age with
`date -r "$F"` — the file's MTIME.

That exact defect was already found and already fixed once. Commit `2d26dea7d`
(2026-06-11, PR #1269, audit finding F04) says so verbatim:

    the SessionStart staleness hook measured the wrong thing — it computed file
    age from `date -r` (mtime), which any unrelated edit reset, so it would never
    fire the >30d warning the contract itself promises.
    ...
    ~/.claude/settings.json (out-of-repo, local-only): hook now extracts the
    declared YYYY-MM-DD from the "active since" line and computes the real age
    from it. Verified: reports "declared age 51d STALE" against the old date

Measured on Pro 2026-08-31, eighty-one days later: that hook computes from mtime
again. The cure was real, it was verified, and it was LOST — because it lived in
a file that no repository tracks, no CI reads, and no review protects. Scar
family #1 (HOME-fork drift), in its purest form: not "the repo fix never reached
the live copy", but "the fix only ever existed in the live copy".

Measured the same day on all three machines: Pro has the hook and it is wrong;
Mini and M5 do not have it at all. So the mechanism that announces the contract's
own expiry works on zero of three machines.

Re-doing that fix in the same non-durable place would be the third attempt at the
same repair in the same losable location. This script is the durable half: it
lives in the repo, it is version-controlled, it is covered by tests, and it reads
the same bytes on every machine. Whoever repairs the hook should make the hook
call THIS, rather than re-implement the date arithmetic a third time.

TWO TRAPS A NAIVE FIX FALLS INTO
=================================
1. The hook's own grep is `^\\*\\*Level [12] — active since`, which matches ONLY
   the first line of the block. The latest re-certification does not live there —
   it lives in a `(re-certified YYYY-MM-DD ...)` parenthetical below it. A fix
   that "parses the declared date" but keeps that grep reads 2026-06-11 (81 days)
   instead of 2026-07-19 (43 days): still wrong, just wrong differently. This
   script therefore takes the MAXIMUM of every declared date in the block.
2. The file carries 24 ISO dates in total — changelog entries, audit stamps,
   unrelated corrections. Only the ones inside the `## Active level` section, on
   a line that actually declares activation or re-certification, may count.

EXIT CODES
==========
0 by default, ALWAYS — this reports, it does not block. Zero's standing constraint
on the merge queue ("non voglio regressioni") means a lapsed contract must not
turn every open PR red; a lapse is a message for the owner, not a gate. Pass
`--strict` to exit 1 on a lapse, for a caller that has decided it wants that.
2 is reserved for the script failing to answer at all (file missing, no declared
date found) — an unanswerable probe must never read as "fresh".
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CONTRACT = REPO_ROOT / "AUTONOMOUS_OPS.md"

# The contract's own rule, quoted from AUTONOMOUS_OPS.md:
#   "If today's date is >30 days after 'active since' without a refresh commit,
#    Claude falls back to conservative mode and pings the user to re-certify."
STALE_AFTER_DAYS = 30

SECTION_HEADING = re.compile(r"^##\s+Active level\s*$", re.IGNORECASE)
SECTION_END = re.compile(r"^(---\s*$|##\s+)")
ISO_DATE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
# A date only counts when its own line declares activation or re-certification.
DECLARING_LINE = re.compile(r"active since|re-certified", re.IGNORECASE)


class ContractUnreadable(Exception):
    """The probe could not answer. Never silently degrades to 'fresh'."""


def active_level_block(text: str) -> list[str]:
    """Return the lines of the '## Active level' section, heading excluded.

    Bounded deliberately: the file carries two dozen ISO dates elsewhere
    (changelog, audit stamps), and none of them govern the contract.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if SECTION_HEADING.match(line):
            start = i + 1
            break
    if start is None:
        raise ContractUnreadable("no '## Active level' section in the contract")

    block: list[str] = []
    for line in lines[start:]:
        if SECTION_END.match(line) and block:
            break
        block.append(line)
    return block


def declared_dates(text: str) -> list[datetime.date]:
    """Every activation/re-certification date declared in the Active level block.

    Order is irrelevant on purpose — the caller takes the max. The first match is
    NOT the governing one (see trap 1 in the module docstring).
    """
    found: list[datetime.date] = []
    for line in active_level_block(text):
        if not DECLARING_LINE.search(line):
            continue
        for match in ISO_DATE.finditer(line):
            year, month, day = (int(part) for part in match.groups())
            try:
                found.append(datetime.date(year, month, day))
            except ValueError:
                # A malformed stamp is not a date; skip it rather than crash,
                # but never let it become the governing one.
                continue
    return found


def evaluate(text: str, today: datetime.date) -> tuple[datetime.date, int, bool]:
    """Return (governing date, age in days, is_stale)."""
    dates = declared_dates(text)
    if not dates:
        raise ContractUnreadable(
            "no 'active since' / 're-certified' date found in the Active level block"
        )
    governing = max(dates)
    age = (today - governing).days
    return governing, age, age > STALE_AFTER_DAYS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--contract",
        type=pathlib.Path,
        default=DEFAULT_CONTRACT,
        help="path to AUTONOMOUS_OPS.md (default: repo root)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when the contract has lapsed (default: report only, exit 0)",
    )
    parser.add_argument(
        "--today",
        help="ISO date to evaluate against, for tests (default: today, UTC)",
    )
    args = parser.parse_args(argv)

    today = (
        datetime.date.fromisoformat(args.today)
        if args.today
        else datetime.datetime.now(datetime.timezone.utc).date()
    )

    try:
        text = args.contract.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"UNREADABLE: {args.contract}: {exc}", file=sys.stderr)
        return 2

    try:
        governing, age, stale = evaluate(text, today)
    except ContractUnreadable as exc:
        print(f"UNREADABLE: {exc}", file=sys.stderr)
        return 2

    all_dates = ", ".join(d.isoformat() for d in sorted(set(declared_dates(text))))
    if stale:
        print(
            f"LAPSED: Autonomous Ops contract certified {governing.isoformat()} "
            f"is {age} days old (limit {STALE_AFTER_DAYS}). "
            f"Fall back to conservative mode and ask the owner to re-certify."
        )
    else:
        print(
            f"CURRENT: Autonomous Ops contract certified {governing.isoformat()}, "
            f"{age} days old (limit {STALE_AFTER_DAYS})."
        )
    print(f"  declared dates in the Active level block: {all_dates}")
    print("  measured from the DECLARED date, never the file mtime — see module docstring")

    return 1 if (stale and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
