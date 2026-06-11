#!/usr/bin/env python3
"""Auto-archive resolved/info/old cicatrix scars to keep the active file under
the 40k-char agent auto-load threshold.

WHY THIS EXISTS
---------------
`cicatrix-scars.md` grows monotonically: the `/scar` skill APPENDS new entries,
but nothing ever PRUNES. Past size-control was done by hand ("Archived YYYY-MM-DD
sweep" notes in the file) and a checker (`check_cicatrix_size.sh`) that only
BLOCKS at commit time and was never even wired into the pre-commit hook. Result:
the file repeatedly blows past 40k and the Claude Code harness warns
"... is over the 40.0k-char limit · /memory to free up context".

This script closes the loop: append (by /scar) + auto-archive (by this) =
bounded size.

CRITERION (chosen by Antonello 2026-06-07): "RESOLVED/INFO + age", with an
age-based STRUCTURAL fallback because the file's MASS is open ⚠️ STRUCTURAL
entries ~30-39d old — RESOLVED/INFO alone can never bring it under 40k.

  Stage 1 — archive ✅ RESOLVED / ℹ️ INFO / META entries older than
            --resolved-age-days (default 14), oldest first, until under target.
  Stage 2 — if STILL over target, fall back to archiving ⚠️ STRUCTURAL entries
            older than --structural-age-days (default 15), oldest first, ONLY as
            many as needed to reach target.
  NEVER archive open 🚨 P0/P1 SECURITY / PENDING entries, regardless of age.

PAIR SAFETY
-----------
If an entry is archived and the entry immediately after it back-references it
("CORRECTION to above", "above scar", a follow-up pointing up), the dependent
follow-up is archived together so the archive stays self-coherent and the active
file never keeps a dangling "see above" reference.

Idempotent and safe to run repeatedly. With nothing eligible or already under
target, it is a no-op (exit 0, no writes).

Usage:
  python3 scripts/archive_cicatrix_scars.py --dry-run      # show plan, write nothing
  python3 scripts/archive_cicatrix_scars.py                # archive in place
  python3 scripts/archive_cicatrix_scars.py --target 32000 # custom rentry target

Exit codes: 0 = ok (archived or no-op). 1 = error / could not get under target.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE = REPO_ROOT / ".claude" / "rules" / "cicatrix-scars.md"
ARCHIVE = REPO_ROOT / ".claude" / "rules" / "cicatrix-scars-archive.md"

# Hard ceiling the harness enforces. We archive down to TARGET (< LIMIT) so a
# fresh /scar append doesn't immediately re-cross the line.
LIMIT_CHARS = 40_000
DEFAULT_TARGET_CHARS = 32_000
DEFAULT_RESOLVED_AGE_DAYS = 14
# Antonello 2026-06-07: file mass is OPEN ⚠️ STRUCTURAL ~30-39d old; a 60d
# fallback could never bring it under 40k. 15d makes old-but-open structural
# scars archivable as a Stage-2 fallback ONLY when Stage 1 isn't enough.
DEFAULT_STRUCTURAL_AGE_DAYS = 15

# Trailing (YYYY-MM-DD) dates in a header. Multiple may appear
# ("(2026-05-06 / confirmed 2026-05-12)"); take the LATEST as the entry's
# effective age so a recently-updated scar isn't archived as "old".
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
UPREF_RE = re.compile(r"\babove\b", re.IGNORECASE)


class Entry:
    __slots__ = ("header", "body", "status", "latest_date", "is_uppref")

    def __init__(self, header: str, body: str):
        self.header = header
        self.body = body
        self.status = classify(header)
        self.latest_date = latest_date(header)
        self.is_uppref = False


def classify(header: str) -> str:
    h = header
    if "✅ RESOLVED" in h or "RESOLVED:" in h or h.strip().startswith("### ✅"):
        return "RESOLVED"
    # Never-archive: open critical / pending security (after RESOLVED check, so a
    # 🚨 entry explicitly marked RESOLVED is still archivable).
    if "🚨" in h or "P0" in h or "P1 SECURITY" in h or "PENDING APPROVAL" in h:
        return "OPEN_CRITICAL"
    if "ℹ️" in h or "META:" in h or h.lstrip("# ").startswith("INFO"):
        return "INFO"
    if "⚠️" in h or "STRUCTURAL" in h:
        return "STRUCTURAL"
    # Unmarked follow-ups (e.g. "### CORRECTION to above ...") default OPEN —
    # they ride along with their parent via pair-safety, not on their own.
    return "OPEN"


def latest_date(header: str):
    best = None
    for y, m, d in DATE_RE.findall(header):
        try:
            cand = _dt.date(int(y), int(m), int(d))
        except ValueError:
            continue
        if best is None or cand > best:
            best = cand
    return best


def parse_active(text: str):
    """Return (preamble_lines, entries, tail_lines).

    preamble = everything before the first '### ' entry.
    entries  = the live '### ...' scar blocks, in order.
    tail     = everything from the '## Archived' section onward (untouched).
    """
    lines = text.splitlines(keepends=True)
    archived_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("## Archived")), None
    )
    floor = archived_idx if archived_idx is not None else len(lines)

    header_idxs = [i for i in range(floor) if lines[i].startswith("### ")]
    if not header_idxs:
        return lines, [], []

    preamble = lines[: header_idxs[0]]
    entries = []
    for n, hidx in enumerate(header_idxs):
        end = header_idxs[n + 1] if n + 1 < len(header_idxs) else floor
        entries.append(Entry(lines[hidx].rstrip("\n"), "".join(lines[hidx:end])))

    for n, e in enumerate(entries):
        if n == 0:
            continue
        first = "\n".join(e.body.splitlines()[:6])
        if UPREF_RE.search(first) and (
            "CORRECTION" in e.header.upper()
            or "above" in e.header.lower()
            or "above scar" in first.lower()
        ):
            e.is_uppref = True

    return preamble, entries, lines[floor:]


def select_for_archive(entries, today, target, resolved_age, structural_age,
                       preamble_len, tail_len):
    fixed = preamble_len + tail_len
    removed: set[int] = set()

    def projected():
        return fixed + sum(len(e.body) for i, e in enumerate(entries) if i not in removed)

    def try_remove(idx):
        if idx in removed or entries[idx].status == "OPEN_CRITICAL":
            return
        removed.add(idx)
        j = idx + 1
        while j < len(entries) and entries[j].is_uppref:
            if entries[j].status != "OPEN_CRITICAL":
                removed.add(j)
            j += 1

    def eligible(statuses, max_age_days):
        out = []
        for i, e in enumerate(entries):
            if i in removed or e.is_uppref or e.status not in statuses:
                continue
            if e.latest_date is None:
                continue
            if (today - e.latest_date).days < max_age_days:
                continue
            out.append((e.latest_date, i))
        out.sort(key=lambda t: t[0])  # oldest first
        return [i for _, i in out]

    if projected() <= target:
        return []

    for i in eligible({"RESOLVED", "INFO"}, resolved_age):
        if projected() <= target:
            break
        try_remove(i)

    if projected() > target:
        for i in eligible({"STRUCTURAL"}, structural_age):
            if projected() <= target:
                break
            try_remove(i)

    return sorted(removed)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print plan, write nothing")
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET_CHARS,
                    help=f"char target to archive down to (default {DEFAULT_TARGET_CHARS})")
    ap.add_argument("--limit", type=int, default=LIMIT_CHARS,
                    help=f"hard ceiling that triggers archiving (default {LIMIT_CHARS})")
    ap.add_argument("--resolved-age-days", type=int, default=DEFAULT_RESOLVED_AGE_DAYS)
    ap.add_argument("--structural-age-days", type=int, default=DEFAULT_STRUCTURAL_AGE_DAYS)
    ap.add_argument("--today", default=None, help="override today (YYYY-MM-DD) for testing")
    args = ap.parse_args()

    if not ACTIVE.exists():
        print(f"ERROR: {ACTIVE} not found", file=sys.stderr)
        return 1

    today = _dt.date.fromisoformat(args.today) if args.today else _dt.date.today()

    text = ACTIVE.read_text(encoding="utf-8")
    size = len(text)
    if size <= args.limit:
        print(f"OK: {ACTIVE.name} is {size} chars (<= limit {args.limit}). No archiving needed.")
        return 0

    preamble, entries, tail = parse_active(text)
    if not entries:
        print(f"WARN: {size} chars but no '### ' entries found to archive.", file=sys.stderr)
        return 1

    preamble_len = sum(len(x) for x in preamble)
    tail_len = sum(len(x) for x in tail)

    idxs = select_for_archive(
        entries, today, args.target,
        args.resolved_age_days, args.structural_age_days,
        preamble_len, tail_len,
    )

    if not idxs:
        print(
            f"WARN: {size} chars (> limit {args.limit}) but NOTHING eligible to archive "
            f"(no RESOLVED/INFO >= {args.resolved_age_days}d, no STRUCTURAL >= "
            f"{args.structural_age_days}d). Manual sweep needed.",
            file=sys.stderr,
        )
        return 1

    sel = set(idxs)
    archived = [entries[i] for i in idxs]
    kept = [e for i, e in enumerate(entries) if i not in sel]

    new_active = "".join(preamble) + "".join(e.body for e in kept) + "".join(tail)
    new_active_size = len(new_active)

    print(f"== archive_cicatrix_scars: {size} -> {new_active_size} chars "
          f"(target {args.target}, limit {args.limit}) ==")
    print(f"Archiving {len(archived)} entr{'y' if len(archived)==1 else 'ies'}:")
    for e in archived:
        d = e.latest_date.isoformat() if e.latest_date else "no-date"
        tag = " [up-ref pair]" if e.is_uppref else ""
        print(f"  [{e.status:<13}] {d}  {e.header[4:90].strip()}{tag}")

    over = new_active_size > args.limit
    if over:
        print(f"WARNING: still {new_active_size} > limit {args.limit} after archiving "
              f"all eligible entries. Consider lowering --structural-age-days.",
              file=sys.stderr)

    if args.dry_run:
        print("\n(dry-run: no files written)")
        return 0

    arch_text = ARCHIVE.read_text(encoding="utf-8") if ARCHIVE.exists() else (
        "# cicatrix-scars-archive.md\n\n"
        "Resolved scars archived from `cicatrix-scars.md`.\n\n---\n"
    )
    stamp = today.isoformat()
    addition = (
        f"\n### 🗄️ Auto-archived {stamp} (archive_cicatrix_scars.py)\n\n"
        f"_{len(archived)} entr{'y' if len(archived)==1 else 'ies'} moved from the "
        f"active file to keep it under the {args.limit}-char auto-load threshold._\n\n---\n\n"
    )
    arch_text = (arch_text.rstrip() + "\n\n" + addition
                 + "\n".join(e.body.rstrip() + "\n\n---\n" for e in archived))
    ARCHIVE.write_text(arch_text.rstrip() + "\n", encoding="utf-8")
    ACTIVE.write_text(new_active, encoding="utf-8")

    print(f"\nWrote {ACTIVE.name} ({new_active_size} chars) and appended to {ARCHIVE.name}.")
    return 0 if not over else 1


if __name__ == "__main__":
    raise SystemExit(main())
