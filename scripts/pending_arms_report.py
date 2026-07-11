#!/usr/bin/env python3
"""pending_arms_report.py — superscar #2 "Esiste != Armato / Armamento Sospeso" (W81) reconciliation report.

The W81 ledger (`.claude/skills/modus/PENDING-ARMS.md`) records every artifact that was
BUILT but not yet {merged, installed, propagated, armed, committed}. This script is a
PURE SIGNALER over that ledger: it parses the open section, ages each entry, and alarms
on anything TECH-DEBT-classified that has sat unarmed for >48h — while distinguishing
that from legitimate, pre-declared firebreaks (operator gate / Legge 5 / business
decision) which are informational only, never an alarm, and from NATURAL-WAIT lines
(owner declares a passive wait on a dated calendar trigger, e.g. `me (passivo —
verifica 07-12)`): armed work whose proof needs the calendar is not overdue debt,
and alarming on it starves the healer's idle branch (genome convergence, 2026-07-06).

It NEVER writes, edits, or otherwise mutates anything — ledger, filesystem, or process
state. It only reads the ledger and prints a report (markdown by default, --json on
request). The only way this script affects control flow is its own exit code, and only
under --strict.

Ledger format (documented in the ledger's own header):

    - opened YYYY-MM-DD | artifact | missing arming step | owner (me|operator[<category>]) | proof-of-armed

The parser also accepts "- open YYYY-MM-DD" (dropped "-ed") — a verb-tense drift found
live in the real ledger that a bare "- opened " prefix check silently discarded as an
unrelated list item instead of parsing it as debt.

Entries are recognized ANYWHERE in the file by their own "- opened "/"- open " + date
prefix — never gated by position relative to a `## closed` heading. `- closed ` lines
(proof-of-armed history) are excluded by that same prefix check regardless of where
they live, so no positional cutoff is needed to keep them out. This matters in
practice: a strict "stop scanning at the first `## closed` heading" cutoff was found
2026-07-11 to silently swallow 14 real open-debt lines that had been appended BELOW
that heading over several sessions (mixed in with genuine closed history) — a
positional guard is itself a family #3 under-match the moment reality stops matching
the assumed document shape.

PHANTOM-OPERATOR rule (Zero, 2026-07-06: "io sono te — non c'è nessun operatore"):
sessions ARE the operator for all repo/infra work. An owner may say `operator` ONLY
for the true-operator categories — actions a session structurally cannot take — and
must DECLARE the category inline as `operator[<category>]` (see
TRUE_OPERATOR_CATEGORIES). An `operator` owner with no declared category, or an
unrecognized one, is classified PHANTOM-OPERATOR: work parked behind a human lane
that does not exist. It is the loudest bucket in the report, and both --strict and
--strict-phantom fail on it REGARDLESS OF AGE — a phantom is wrong the moment it is
written, not after 48h.

Usage:
    python3 scripts/pending_arms_report.py [--ledger PATH] [--now YYYY-MM-DD] [--json]
                                           [--strict] [--strict-phantom]

Exit codes:
    0   always, by default (pure signaler — a report is not a failure)
    1   with --strict, if >=1 overdue TECH-DEBT entry OR >=1 PHANTOM-OPERATOR entry
        exists; with --strict-phantom, if >=1 PHANTOM-OPERATOR entry exists (the
        narrow CI ledger gate — pre-existing overdue debt never blocks innocent PRs)
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

# Tolerates the 'opened'/'open' verb-tense drift seen in the real ledger (14 lines
# written "- open YYYY-MM-DD" instead of "- opened YYYY-MM-DD") — a bare-prefix
# entry-start check silently dropped every one of them (family #3 under-match: the
# guard watched one literal spelling and let the real debt through unclassified).
OPENED_RE = re.compile(r"-\s*open(?:ed)?\s+(\d{4}-\d{2}-\d{2})")
ENTRY_START_RE = re.compile(r"^-\s*open(?:ed)?\s+\d{4}-\d{2}-\d{2}")

CLASS_MALFORMED = "MALFORMED"
CLASS_FIREBREAK = "FIREBREAK"
CLASS_NATURAL_WAIT = "NATURAL-WAIT"
CLASS_OPERATOR_GATED = "OPERATOR-GATED"
CLASS_TECH_DEBT = "TECH-DEBT"
CLASS_PHANTOM_OPERATOR = "PHANTOM-OPERATOR"

# The ONLY categories for which owner=operator is legitimate — actions a session
# structurally cannot take (feedback_no_operator_lane_io_sono_te_2026_07_06). Anything
# else labeled `operator` is a phantom: repo/infra work a session can and must do.
TRUE_OPERATOR_CATEGORIES = frozenset(
    {
        "physical",  # physical device actions (IG app toggle, hardware, on-site)
        "gui",  # GUI-only surfaces: interactive logins, GitHub settings, external-UI paste
        "tcc",  # macOS TCC grants (System Settings, per-principal)
        "consent",  # consents only the human can give
        "secret",  # credentials/keychain material only the human holds
        "control-plane",  # ~/.claude/hooks one-liners (host_boundary stays hard by design)
        "business",  # Legge 5 / strategy decisions (incl. arming historically-broken crons)
    }
)

# Tag form: `operator[<category>]` — declared in the owner field. Word-anchored so the
# tag itself is structural, while phantom DETECTION below stays substring-based on the
# owner ("operatore" in Italian prose must not slip through as TECH-DEBT — W82 under-match).
OPERATOR_TAG_RE = re.compile(r"\boperator\s*\[\s*([a-z0-9-]+)\s*\]", re.IGNORECASE)

# NATURAL-WAIT: the owner declares a PASSIVE wait on a dated natural trigger
# (`me (passivo — verifica 07-12)`) — the arming is done, only the proof needs the
# calendar. NOT overdue debt: strict must not fail on it, and the healer's ledger
# receptor must not fire on it every tick (it starved the genome-convergence idle
# branch for a week the day it went live). Word-anchored (#3: "impassivo" in prose
# must not match; a bare `me` owner must stay TECH-DEBT).
NATURAL_WAIT_RE = re.compile(r"\b(?:passiv[oa]|passive)\b", re.IGNORECASE)


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
        """Report/JSON grouping key: MALFORMED > PHANTOM-OPERATOR > FIREBREAK > {cls}-OVERDUE > FRESH."""
        if self.cls == CLASS_MALFORMED:
            return CLASS_MALFORMED
        if self.cls == CLASS_PHANTOM_OPERATOR:
            # never FRESH: a phantom is wrong the moment it is written, not after 48h.
            return CLASS_PHANTOM_OPERATOR
        if self.cls == CLASS_FIREBREAK:
            return CLASS_FIREBREAK
        if self.cls == CLASS_NATURAL_WAIT:
            # never -OVERDUE: the wait is on a declared calendar trigger, not on work
            return CLASS_NATURAL_WAIT
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
    """Return the raw (continuation-concatenated) text of every open-ledger entry.

    The WHOLE file is scanned — no positional cutoff at a '## closed' heading. An
    entry starts at a line matching ENTRY_START_RE ('- opened ' or '- open '
    immediately followed by a YYYY-MM-DD date; both verb forms are accepted, and the
    date anchor keeps unrelated '- open ...' prose from being mistaken for a ledger
    entry). '- closed ' lines (proof-of-armed history) never match that prefix, so
    they're excluded wherever they live — no section boundary needed to keep them
    out. Any line following an entry-start that is non-blank, doesn't start a new
    '- ' list item, and isn't a heading/blockquote is treated as a wrapped
    continuation and appended (space-joined) to the current entry. A blank line, a
    new '- ' item, or a heading/blockquote line ends the current entry.

    A positional cutoff was tried and dropped 2026-07-11: it silently discarded 14
    real open-debt lines that sessions had appended below the '## closed' heading
    (mixed in with genuine closed history) — verified as the same under-match
    disease (family #3) as the 'opened' vs 'open' spelling drift this same fix
    addresses, just expressed structurally instead of lexically.
    """
    lines = ledger_text.splitlines()

    entries: List[str] = []
    current: Optional[str] = None

    def finalize() -> None:
        nonlocal current
        if current is not None:
            entries.append(current)
        current = None

    for line in lines:
        stripped = line.strip()
        if ENTRY_START_RE.match(stripped):
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
    elif NATURAL_WAIT_RE.search(owner):
        # owner-field only: "passivo" in the free-text body (e.g. quoting a log)
        # must not reclassify a line whose owner is active.
        cls = CLASS_NATURAL_WAIT
    elif "operator" in owner.lower():
        # Owner claims an operator lane. Legitimate ONLY if every declared tag names a
        # true-operator category; untagged (or unknown-category) = PHANTOM-OPERATOR.
        tags = [m.group(1).lower() for m in OPERATOR_TAG_RE.finditer(owner)]
        if tags and all(t in TRUE_OPERATOR_CATEGORIES for t in tags):
            cls = CLASS_OPERATOR_GATED
        else:
            cls = CLASS_PHANTOM_OPERATOR
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
        "phantom_operator": buckets.count(CLASS_PHANTOM_OPERATOR),
        "tech_debt_overdue": buckets.count(f"{CLASS_TECH_DEBT}-OVERDUE"),
        "operator_gated_overdue": buckets.count(f"{CLASS_OPERATOR_GATED}-OVERDUE"),
        "firebreak": buckets.count(CLASS_FIREBREAK),
        "natural_wait": buckets.count(CLASS_NATURAL_WAIT),
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
        "- counts: total={total} phantom_operator={phantom_operator} "
        "tech_debt_overdue={tech_debt_overdue} "
        "operator_gated_overdue={operator_gated_overdue} firebreak={firebreak} "
        "natural_wait={natural_wait} fresh={fresh} malformed={malformed}".format(**counts)
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
        "PHANTOM-OPERATOR (owner claims an operator lane with no true-operator "
        "category — there is no operator: re-own to a session or tag operator[<cat>])",
        by_bucket.get(CLASS_PHANTOM_OPERATOR, []),
        fmt_entry,
    )
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
    section(
        "NATURAL-WAIT (armed; proof waits on a declared calendar trigger — never overdue)",
        by_bucket.get(CLASS_NATURAL_WAIT, []),
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
        help=(
            "Exit 1 iff >=1 overdue TECH-DEBT entry OR >=1 PHANTOM-OPERATOR entry "
            "exists (otherwise always exit 0)."
        ),
    )
    parser.add_argument(
        "--strict-phantom",
        action="store_true",
        help=(
            "Exit 1 iff >=1 PHANTOM-OPERATOR entry exists — the narrow CI ledger "
            "gate: blocks writing new phantom-operator lines without turning "
            "pre-existing overdue tech-debt into a red check for innocent PRs."
        ),
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

    has_phantom = any(e.cls == CLASS_PHANTOM_OPERATOR for e in entries)
    if args.strict and (
        has_phantom
        or any(e.cls == CLASS_TECH_DEBT and e.overdue for e in entries)
    ):
        return 1
    if args.strict_phantom and has_phantom:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
