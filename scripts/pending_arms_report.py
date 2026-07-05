#!/usr/bin/env python3
"""pending_arms_report.py — superscar #2 "Esiste != Armato / Armamento Sospeso" (W81) reconciliation report.

The W81 ledger (`.claude/skills/modus/PENDING-ARMS.md`) records every artifact that was
BUILT but not yet {merged, installed, propagated, armed, committed}. This script is a
PURE SIGNALER over that ledger: it parses the open section, ages each entry, and alarms
on anything TECH-DEBT-classified that has sat unarmed for >48h — while distinguishing
that from legitimate, pre-declared firebreaks (operator gate / Legge 5 / business
decision) which are informational only, never an alarm.

It NEVER writes, edits, or otherwise mutates anything — ledger, filesystem, or process
state. It only reads the ledger and prints a report (markdown by default, --json on
request). The only way this script affects control flow is its own exit code, and only
under --strict.

Ledger format (documented in the ledger's own header):

    - opened YYYY-MM-DD | artifact | missing arming step | owner (me|operator) | proof-of-armed

Entries live as markdown list items BEFORE a line starting with `## closed`; closed
entries (after that heading, starting with `- closed `) are proof-of-armed history and
are never read by this script.

Usage:
    python3 scripts/pending_arms_report.py [--ledger PATH] [--now YYYY-MM-DD] [--json] [--strict]

Exit codes:
    0   always, by default (pure signaler — a report is not a failure)
    1   only with --strict, and only if >=1 overdue TECH-DEBT entry exists
    2   ledger file not found, or a CLI argument error (argparse's own exit code)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# 48h at day-precision: the ledger records opened-dates, not timestamps, so "overdue"
# is age_days >= 2 (i.e. the entry has survived at least one full day beyond the day
# it was opened, which is the closest day-precision proxy for >48h — declared here and
# in every report header so nobody mistakes it for hour-precision).
OVERDUE_AGE_DAYS = 2

OPENED_RE = re.compile(r"-\s*opened\s+(\d{4}-\d{2}-\d{2})")
CLOSED_HEADING_PREFIX = "## closed"

CLASS_MALFORMED = "MALFORMED"
CLASS_FIREBREAK = "FIREBREAK"
CLASS_OPERATOR_GATED = "OPERATOR-GATED"
CLASS_TECH_DEBT = "TECH-DEBT"


@dataclass
class Entry:
    """One parsed open-ledger entry (after continuation-line concatenation)."""

    raw: str
    opened_date: Optional[date]
    artifact: str
    owner: str
    missing_step: str
    proof: str
    malformed: bool
    malformed_reasons: List[str] = field(default_factory=list)
    age_days: Optional[int] = None
    overdue: bool = False
    cls: str = CLASS_TECH_DEBT

    @property
    def bucket(self) -> str:
        """Report/JSON grouping key: MALFORMED > FIREBREAK > {cls}-OVERDUE > FRESH."""
        if self.cls == CLASS_MALFORMED:
            return CLASS_MALFORMED
        if self.cls == CLASS_FIREBREAK:
            return CLASS_FIREBREAK
        if self.overdue:
            return f"{self.cls}-OVERDUE"
        return "FRESH"


def _safe_get(parts: Sequence[str], idx: int) -> str:
    try:
        return parts[idx].strip()
    except IndexError:
        return ""


def _extract_missing_step(parts: Sequence[str]) -> str:
    """Best-effort recovery of the 'missing arming step' field.

    Well-formed entries have exactly 5 pipe-fields (date-prefix, artifact, missing
    step, owner, proof). If the free-text itself contains extra '|' characters the
    split grows past 5 — field[1] (artifact) and the last two fields (owner, proof)
    stay anchored from the outside in, so everything left in the middle belongs to
    the missing-arming-step description; rejoin it with '|' to restore it verbatim.
    """
    middle = parts[2:-2]
    if middle:
        return "|".join(p.strip() for p in middle).strip()
    return _safe_get(parts, 2)


def _truncate(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def extract_open_entries(ledger_text: str) -> List[str]:
    """Return the raw (continuation-concatenated) text of every open-section entry.

    Only lines BEFORE the first line starting with '## closed' are considered. Within
    that open section, an entry starts at a line starting with '- opened '; any
    following line that is non-blank, doesn't start a new '- ' list item, and isn't a
    heading/blockquote is treated as a wrapped continuation and appended (space-joined)
    to the current entry. A blank line, a new '- ' item, or a heading/blockquote line
    ends the current entry.
    """
    lines = ledger_text.splitlines()

    cutoff = len(lines)
    for i, line in enumerate(lines):
        if line.strip().startswith(CLOSED_HEADING_PREFIX):
            cutoff = i
            break
    open_lines = lines[:cutoff]

    entries: List[str] = []
    current: Optional[str] = None

    def finalize() -> None:
        nonlocal current
        if current is not None:
            entries.append(current)
        current = None

    for line in open_lines:
        stripped = line.strip()
        if stripped.startswith("- opened "):
            finalize()
            current = stripped
        elif stripped.startswith("- "):
            # some other list item (not a ledger entry) — ends any entry in progress,
            # is not itself collected.
            finalize()
        elif stripped == "":
            finalize()
        elif stripped.startswith("#") or stripped.startswith(">"):
            finalize()
        else:
            if current is not None:
                current = f"{current} {stripped}"

    finalize()
    return entries


def parse_entry(raw: str, now: date) -> Entry:
    """Parse one raw entry string into a structured, never-crashing Entry."""
    reasons: List[str] = []

    date_match = OPENED_RE.search(raw)
    opened_dt: Optional[date] = None
    if date_match:
        opened_dt = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
    else:
        reasons.append("no 'opened YYYY-MM-DD' date found")

    parts = raw.split("|")
    if len(parts) < 3:
        reasons.append(f"only {len(parts)} pipe-segment(s) (need >= 3)")

    artifact = _safe_get(parts, 1)
    owner = _safe_get(parts, -2)
    proof = _safe_get(parts, -1)
    missing_step = _extract_missing_step(parts)

    age_days: Optional[int] = None
    overdue = False
    if opened_dt is not None:
        age_days = (now - opened_dt).days
        overdue = age_days >= OVERDUE_AGE_DAYS

    malformed = bool(reasons)
    if malformed:
        cls = CLASS_MALFORMED
    elif "firebreak" in raw.lower():
        cls = CLASS_FIREBREAK
    elif "operator" in owner.lower():
        cls = CLASS_OPERATOR_GATED
    else:
        cls = CLASS_TECH_DEBT

    return Entry(
        raw=raw,
        opened_date=opened_dt,
        artifact=artifact,
        owner=owner,
        missing_step=missing_step,
        proof=proof,
        malformed=malformed,
        malformed_reasons=reasons,
        age_days=age_days,
        overdue=overdue,
        cls=cls,
    )


def load_entries(ledger_path: Path, now: date) -> List[Entry]:
    text = ledger_path.read_text(encoding="utf-8")
    return [parse_entry(raw, now) for raw in extract_open_entries(text)]


def compute_counts(entries: List[Entry]) -> Dict[str, int]:
    buckets = [e.bucket for e in entries]
    return {
        "total": len(entries),
        "tech_debt_overdue": buckets.count(f"{CLASS_TECH_DEBT}-OVERDUE"),
        "operator_gated_overdue": buckets.count(f"{CLASS_OPERATOR_GATED}-OVERDUE"),
        "firebreak": buckets.count(CLASS_FIREBREAK),
        "fresh": buckets.count("FRESH"),
        "malformed": buckets.count(CLASS_MALFORMED),
    }


def render_report(ledger_path: Path, now: date, entries: List[Entry]) -> str:
    counts = compute_counts(entries)
    lines: List[str] = []
    lines.append("# PENDING-ARMS reconciliation report")
    lines.append("")
    lines.append(f"- ledger: `{ledger_path}`")
    lines.append(
        f"- now: {now.isoformat()} (day-precision dates; overdue = age_days >= "
        f"{OVERDUE_AGE_DAYS}, the closest day-precision proxy for >48h)"
    )
    lines.append(
        "- counts: total={total} tech_debt_overdue={tech_debt_overdue} "
        "operator_gated_overdue={operator_gated_overdue} firebreak={firebreak} "
        "fresh={fresh} malformed={malformed}".format(**counts)
    )
    lines.append("")

    def fmt_entry(e: Entry) -> str:
        opened = e.opened_date.isoformat() if e.opened_date else "?"
        age = e.age_days if e.age_days is not None else "?"
        return (
            f"- {e.artifact or '(no artifact parsed)'} "
            f"(opened {opened}, age {age}d, owner={e.owner or '?'}): "
            f"{_truncate(e.missing_step, 120)}"
        )

    def fmt_malformed(e: Entry) -> str:
        reasons = "; ".join(e.malformed_reasons) or "unknown parse failure"
        return f"- {_truncate(e.raw, 80)}  [reason: {reasons}]"

    def section(title: str, items: List[Entry], formatter) -> None:
        lines.append(f"## {title}")
        if not items:
            lines.append("none")
        else:
            for item in items:
                lines.append(formatter(item))
        lines.append("")

    by_bucket: Dict[str, List[Entry]] = {}
    for e in entries:
        by_bucket.setdefault(e.bucket, []).append(e)

    section(
        "TECH-DEBT overdue (>48h)",
        by_bucket.get(f"{CLASS_TECH_DEBT}-OVERDUE", []),
        fmt_entry,
    )
    section(
        "OPERATOR-GATED overdue",
        by_bucket.get(f"{CLASS_OPERATOR_GATED}-OVERDUE", []),
        fmt_entry,
    )
    section(
        "FIREBREAK (legitimate, informational)",
        by_bucket.get(CLASS_FIREBREAK, []),
        fmt_entry,
    )
    section("Fresh (<48h)", by_bucket.get("FRESH", []), fmt_entry)
    section("MALFORMED", by_bucket.get(CLASS_MALFORMED, []), fmt_malformed)

    return "\n".join(lines).rstrip() + "\n"


def build_json(ledger_path: Path, now: date, entries: List[Entry]) -> Dict[str, Any]:
    return {
        "now": now.isoformat(),
        "ledger": str(ledger_path),
        "counts": compute_counts(entries),
        "entries": [
            {
                "opened": e.opened_date.isoformat() if e.opened_date else None,
                "age_days": e.age_days,
                "artifact": e.artifact,
                "owner": e.owner,
                "class": e.cls,
                "overdue": e.overdue,
                "raw_head": e.raw[:80],
            }
            for e in entries
        ],
    }


def _default_ledger_path() -> Path:
    # scripts/pending_arms_report.py -> parent = scripts/, parent.parent = repo root.
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"


def _parse_now(value: Optional[str]) -> date:
    if value is None:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pending_arms_report.py",
        description=(
            "Reconciliation report over the W81 PENDING-ARMS ledger: alarms on "
            "built-but-not-armed TECH-DEBT entries overdue >48h, separates "
            "legitimate firebreaks. Pure signaler — never writes anything."
        ),
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help="Path to PENDING-ARMS.md (default: <repo-root>/.claude/skills/modus/PENDING-ARMS.md)",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="Override 'today' as YYYY-MM-DD, for deterministic runs/tests.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the markdown report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 iff >=1 overdue TECH-DEBT entry exists (otherwise always exit 0).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    ledger_path: Path = args.ledger if args.ledger is not None else _default_ledger_path()

    if not ledger_path.exists():
        print(
            f"pending_arms_report: ledger not found: {ledger_path}",
            file=sys.stderr,
        )
        return 2

    try:
        now = _parse_now(args.now)
    except ValueError:
        print(
            f"pending_arms_report: invalid --now value {args.now!r}, expected YYYY-MM-DD",
            file=sys.stderr,
        )
        return 2

    entries = load_entries(ledger_path, now)

    if args.json:
        print(json.dumps(build_json(ledger_path, now, entries), indent=2))
    else:
        print(render_report(ledger_path, now, entries), end="")

    if args.strict and any(
        e.cls == CLASS_TECH_DEBT and e.overdue for e in entries
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
