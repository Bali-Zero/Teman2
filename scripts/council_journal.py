#!/usr/bin/env python3
"""council_journal.py — record a council seat AT DISPATCH, because it cannot be recorded
afterwards without inventing a timestamp.

WHY THIS EXISTS (measured 2026-09-02 while shipping PR #5519). R9
(`scripts/evidence_pack_lint.py::check_council_run_gear3`) counts a journal line only when it
carries `role == "review"` AND `ok is True` AND a non-empty `ts` —
`_read_council_journal_seats` `continue`s on anything else, its own comment saying "the declared
minimal schema requires 'ts' too". A qualifying line is therefore UNWRITEABLE without a
timestamp, and after the fact the only timestamp available is one you make up.

That is not hypothetical. On #5519 the two seats that really did review the diff appeared in
`lanes[]` and in `dissent[]` with their actual objections, but in no journal — and the only
dispatch line on disk named a DIFFERENT roster, so reusing its timestamp would have asserted
those seats took part in a dispatch that the line itself says they did not. There was no honest
journal left to write, so that pack declared `seat_override` instead. An override is legitimate
once; it should not become how this repo passes R9.

Twenty-five `council-journal.jsonl` files already exist under `evidence/2026-08/`, all
hand-authored, with no tool and no documented procedure anywhere in `docs/`, `.claude/skills/`
or `research/`. So the gap this fills is not "nobody journals" — it is that journaling correctly
depends entirely on remembering, at the right moment, a schema written down only inside the
linter that reads it. This makes the honest path the easy one.

WHAT IT DELIBERATELY WILL NOT DO:

  * It will not backdate. `ts` is always `datetime.now(timezone.utc)` at the moment of the call.
    There is no `--ts` flag, on purpose: a flag that accepts a timestamp is a flag that accepts
    an invented one, and inventing it is the exact failure this file exists to prevent.
  * It will not write `ok: true` without a `--note`. A qualifying line CLAIMS a seat returned a
    judgement; a claim with nothing behind it is the "receipt without a command" shape the
    evidence-pack contract already rejects.
  * It will not reimplement R9. `check` imports the real `check_council_run_gear3` and reports
    what THAT says, inheriting its path confinement and seat validation. A second copy of a rule
    is a second rule, and the two drift.
  * It will not write outside the pack directory, nor onto `pack.yml` / `brief.yml` — mirroring
    the confinement `scripts/ci/stage_council_journal.py` enforces on the CI side.

A seat that times out or refuses is recorded with `--outcome non-judgement`. That line does NOT
count toward quorum (R9 requires `ok is True`) and is not meant to — a silence is not an
agreement. Recording it still matters: it is the difference between "this seat was never asked"
and "this seat was asked and could not answer", which is precisely what a later reader needs in
order to judge whether a `seat_override` is honest.

Usage:
    python3 scripts/council_journal.py append \\
        --pack-dir evidence/2026-09/<task-slug>-<8hex> \\
        --seat codex-gpt-5.6-sol --outcome ok \\
        --note "one round on the finished diff, --sandbox read-only, effort=high"

    python3 scripts/council_journal.py check --pack-dir evidence/2026-09/<task-slug>-<8hex>

Exit codes:
    append: 0 = written; 2 = refused (unknown seat is a NOTE not a refusal; refusals are a
            missing note on `ok`, a path escape, a reserved name, or a missing pack dir)
    check:  0 = R9 satisfied on and after its enforcement date (or pack is not Gear-3);
            1 = R9 would fail on/after that date; 2 = could not evaluate
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

#: The filename every one of the 25 existing journals uses. Matching it is not cosmetic: a pack
#: declares `council_run: council-journal.jsonl` as a bare relative name, and a different
#: filename here would silently produce a journal R9 never looks at.
DEFAULT_JOURNAL_NAME = "council-journal.jsonl"

#: Names harness-floor.yml stages the pack and brief under. A journal must never land on one.
RESERVED_NAMES = frozenset({"pack.yml", "brief.yml"})

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_lint_module() -> Any:
    """Import evidence_pack_lint without requiring it on sys.path.

    Deliberately imports the REAL module rather than copying its constants: COUNCIL_REVIEW_SEATS
    is a moving list — `kimi-code/k3` was quota-dead for a whole week on 2026-09-01 — and a local
    copy would keep validating against a roster that no longer matches the rule.
    """
    path = _REPO_ROOT / "scripts" / "evidence_pack_lint.py"
    spec = importlib.util.spec_from_file_location("_council_journal_lint", path)
    if spec is None or spec.loader is None:  # pragma: no cover - import plumbing
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_journal(pack_dir: Path, name: str) -> tuple[Path | None, str | None]:
    """Resolve `name` inside `pack_dir`, refusing escapes and reserved names.

    Mirrors R9's own confinement — it resolves `council_run:` against the pack's OWN directory
    and rejects anything leaving it — so a journal written elsewhere would be invisible to the
    very rule meant to read it.
    """
    if not name or not name.strip():
        return None, "journal name is empty"
    if Path(name).is_absolute() or name.startswith("//"):
        return None, f"journal name {name!r} must be relative to the pack dir, not absolute"
    if Path(name).name in RESERVED_NAMES:
        return None, f"journal name {name!r} would collide with a staged {Path(name).name}"
    pack_resolved = pack_dir.resolve()
    journal = (pack_resolved / name).resolve()
    if pack_resolved not in (journal, *journal.parents):
        return None, f"journal name {name!r} escapes the pack directory"
    return journal, None


def cmd_append(args: argparse.Namespace) -> int:
    pack_dir = Path(args.pack_dir)
    if not pack_dir.is_dir():
        print(f"council_journal: {pack_dir} is not a directory", file=sys.stderr)
        return 2

    seat = args.seat.strip()
    if not seat:
        print("council_journal: --seat is empty", file=sys.stderr)
        return 2

    ok = args.outcome == "ok"
    if ok and not (args.note and args.note.strip()):
        print(
            "council_journal: --outcome ok requires --note. A qualifying line asserts this seat "
            "returned a judgement; record what it said, or use --outcome non-judgement.",
            file=sys.stderr,
        )
        return 2

    journal, err = _resolve_journal(pack_dir, args.journal)
    if journal is None:
        print(f"council_journal: {err}", file=sys.stderr)
        return 2

    # Field order matches every existing journal in the tree: seat, role, ok, ts, then extras.
    entry: dict[str, Any] = {
        "seat": seat,
        "role": "review",
        "ok": ok,
        # Never a parameter — see the module docstring.
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.note and args.note.strip():
        entry["note"] = args.note.strip()

    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"council_journal: appended seat={seat} ok={ok} ts={entry['ts']} -> {journal}")

    if ok:
        qualifying = set(getattr(_load_lint_module(), "COUNCIL_REVIEW_SEATS", ()))
        if seat not in qualifying:
            # A NOTE, not a refusal: a council may legitimately include seats R9 does not count
            # (agy/Gemini gave the single most plan-changing objection on #5519). Recording them
            # is right; letting the author believe they counted toward quorum is not.
            print(
                f"council_journal: NOTE — {seat!r} is not one of R9's qualifying seats "
                f"({', '.join(sorted(qualifying))}), so this line is recorded but does NOT "
                "count toward quorum.",
            )

    rel = journal.relative_to(pack_dir.resolve())
    print(f"council_journal: the pack must declare  council_run: {rel}")
    return 0


def _resolve_gear(pack: dict[str, Any], pack_dir: Path) -> tuple[int | None, str]:
    """Find the pack's gear, looking in the SIBLING BRIEF when the pack does not carry it.

    Measured 2026-09-02 across the 40 real evidence packs in this tree: **zero** declare `gear`
    in `pack.yml`; 37 declare it only in the sibling `brief.yml`, and 3 in neither. A checker
    that reads `pack.yml` alone therefore answers "not Gear-3, nothing to check" on every real
    pack in the repo — green on everything, which is worse than no checker at all. (`pack.yml`'s
    `brief_ref:` is the CI-staging literal `evidence/brief.yml`, not a path to the real sibling,
    so it cannot be followed from here; the sibling is found by name.)
    """
    if isinstance(pack.get("gear"), int):
        return pack["gear"], "pack.yml"

    import yaml

    brief = pack_dir / "brief.yml"
    if brief.is_file():
        try:
            data = yaml.safe_load(brief.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return None, "brief.yml (unparseable)"
        if isinstance(data, dict) and isinstance(data.get("gear"), int):
            return data["gear"], "brief.yml"
    return None, "nowhere"


def cmd_check(args: argparse.Namespace) -> int:
    import yaml  # local import so `append` still works where PyYAML is absent

    pack_dir = Path(args.pack_dir)
    pack_path = pack_dir / "pack.yml"
    if not pack_path.is_file():
        print(f"council_journal: no pack.yml under {pack_dir}", file=sys.stderr)
        return 2
    try:
        pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"council_journal: {pack_path} does not parse: {exc}", file=sys.stderr)
        return 2
    if not isinstance(pack, dict):
        print(f"council_journal: {pack_path} did not parse to a mapping", file=sys.stderr)
        return 2

    gear, gear_src = _resolve_gear(pack, pack_dir)
    if gear is None:
        # NEVER a silent pass. "I could not find the gear" and "this is not Gear-3" are different
        # answers, and collapsing them is how a checker reports green on everything.
        print(
            f"council_journal: cannot determine gear — absent from {pack_dir/'pack.yml'} and from "
            f"the sibling brief.yml. Refusing to report a verdict rather than assume not-Gear-3.",
            file=sys.stderr,
        )
        return 2
    if gear != 3:
        print(f"council_journal: gear={gear!r} (from {gear_src}) — R9 is Gear-3 only, nothing to check")
        return 0

    lint = _load_lint_module()
    flip: datetime.date = getattr(lint, "R9_R11_ENFORCEMENT_DATE")
    before = flip - datetime.timedelta(days=1)

    # Asked on BOTH sides of its own enforcement date. Reporting only today's verdict is exactly
    # how a pack sails into a dated cliff: before the flip R9 is a NOTICE, after it the identical
    # finding fails a required check.
    results: dict[str, tuple[list[str], str | None]] = {}
    for label, day in (("before", before), ("on/after", flip)):
        violations, notice = lint.check_council_run_gear3(
            pack, pack_dir=pack_dir, gear=3, today=day
        )
        results[label] = (list(violations or []), notice)

    if pack.get("seat_override"):
        print("council_journal: pack declares seat_override — R9 is reported, never failed.")
    print(f"council_journal: council_run = {pack.get('council_run')!r}")
    for label, day in (("before", before), ("on/after", flip)):
        violations, notice = results[label]
        if violations:
            state = f"VIOLATION — {violations[0]}"
        elif notice:
            state = f"notice — {notice}"
        else:
            state = "OK"
        print(f"  {label} the flip ({day.isoformat()}): {state}")

    return 1 if results["on/after"][0] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record a council seat at dispatch; check R9 quorum using the real rule."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ap = sub.add_parser("append", help="append one seat's outcome, stamped with the real clock")
    ap.add_argument("--pack-dir", required=True)
    ap.add_argument("--seat", required=True)
    ap.add_argument("--outcome", required=True, choices=("ok", "non-judgement"))
    ap.add_argument("--note", default="", help="what the seat returned; required for --outcome ok")
    ap.add_argument("--journal", default=DEFAULT_JOURNAL_NAME)
    ap.set_defaults(func=cmd_append)

    cp = sub.add_parser(
        "check", help="report what R9 says about this pack, before and after its flip date"
    )
    cp.add_argument("--pack-dir", required=True)
    cp.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
