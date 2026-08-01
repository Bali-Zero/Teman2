"""The KBLI completion scoreboard — one number per axis, and a ratchet.

WHY THIS EXISTS. For a year this programme measured progress in LOTS ("Batch A
Lot 8 closed"), which answers "what did we do" and never "how far are we". Worse,
a lot count cannot regress-check: a later data-plane write can silently undo an
earlier lot's honesty and no lot number moves. This turns the Definition of DONE
into something a machine computes and CI defends:

    for every (code, fact): a locator + vintage, OR a declared gap. Never bare.

USAGE
    python3 scripts/kbli_filiera/kbli_coverage_scoreboard.py            # human table
    python3 scripts/kbli_filiera/kbli_coverage_scoreboard.py --json     # machine
    python3 scripts/kbli_filiera/kbli_coverage_scoreboard.py --check    # CI ratchet
    python3 scripts/kbli_filiera/kbli_coverage_scoreboard.py --update-baseline

EXIT CODES (`--check`)
    0  no regression
    1  REGRESSION — an axis lost honest coverage, or gained a bare fact
    4  CANNOT VERIFY — canonical or baseline unreadable

Bit 4 is deliberately NOT bit 1: "I could not measure" must never be reported as
"it regressed" (W106b — an healer that acts on a mis-attributed failure spends a
session on a false premise).

THE RATCHET IS ONE-WAY AND IT IS NOT A TARGET. It asserts only that honesty does
not go DOWN. It never asserts a number is good: the PMA axis is allowed to sit at
1% forever as far as this gate is concerned — F2 of the plan is what moves it.
A gate that failed until the programme finished would be turned off in a week.

DELIBERATELY NOT MEASURED HERE: the downstream surfaces (`kbli_documents`, the
KG, Qdrant, gold). This file reads canonical ONLY, so it can run in CI with no
credentials. A canonical that is honest while a surface lies is exactly the shape
that has bitten this project four times — that half is
`kbli_surface_conformance.py`, and neither file is a substitute for the other.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Sibling-module import: works when executed directly (Python auto-adds this
# file's directory to sys.path[0]) and when a test has already inserted it —
# same pattern as `emit_l4bali_gap_disclosure_spec.py`.
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from _coverage_basis import (  # noqa: E402
    AXES,
    CODE_FIELD,
    crosswalk_is_adjudicated,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
DEFAULT_BASELINE = REPO_ROOT / "data/kbli-filiera/coverage-baseline.json"

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_CANNOT_VERIFY = 4

# How many offending codes to PRINT per defect state. The full list always
# travels in the JSON payload; the human table declares "N of M" rather than
# showing a truncated list that reads as complete (W97).
PRINT_SAMPLE = 12


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload["data"] if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path}: expected a non-empty record list")
    codes = [str(r.get(CODE_FIELD)) for r in records]
    if len(set(codes)) != len(codes):
        # Without this, a code could be duplicated and another dropped while
        # every aggregate count stays put — a swap the ratchet would never see.
        duplicates = sorted({c for c in codes if codes.count(c) > 1})
        raise ValueError(f"{path}: duplicate codes: {duplicates[:PRINT_SAMPLE]}")
    return records


def build_scoreboard(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure. Every record lands in exactly one state per axis — a code that
    matched nothing would be invisible, and an invisible population is how a
    selector hides a defect (corner §1: "the selector is the disease")."""
    total = len(records)
    axes: dict[str, Any] = {}

    for axis_name, (classify, honest_states, strong_states) in AXES.items():
        states: dict[str, int] = {}
        defect_codes: list[str] = []
        strong_codes: list[str] = []
        for record in records:
            code = str(record.get(CODE_FIELD))
            state = classify(record)
            states[state] = states.get(state, 0) + 1
            if state not in honest_states:
                defect_codes.append(code)
            if state in strong_states:
                strong_codes.append(code)
        honest = sum(n for state, n in states.items() if state in honest_states)
        if honest + len(defect_codes) != total:
            raise AssertionError(
                f"axis {axis_name}: {honest} honest + {len(defect_codes)} defect != {total} records"
            )
        axes[axis_name] = {
            "total": total,
            "honest": honest,
            "defect": len(defect_codes),
            "strong": len(strong_codes),
            "states": dict(sorted(states.items())),
            "defect_codes": sorted(defect_codes),
            "strong_codes": sorted(strong_codes),
        }

    axes["crosswalk"]["adjudicated"] = sum(1 for r in records if crosswalk_is_adjudicated(r))
    return {"total_codes": total, "axes": axes}


def ratchet_regressions(current: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Pure. One-way comparison, per axis. An axis absent from the baseline is
    NOT a regression (it is a new axis); an axis absent from `current` IS one
    (someone deleted a measurement, which is how coverage silently vanishes)."""
    problems: list[str] = []
    # Read BOTH sides through .get(): a malformed payload must produce a report,
    # never a KeyError. A gate that raises instead of reporting is a gate whose
    # verdict nobody sees.
    base_total = baseline.get("total_codes", 0)
    now_total = current.get("total_codes", 0)
    if now_total < base_total:
        problems.append(f"catalogue shrank {base_total} -> {now_total} codes")
    for axis_name, base in sorted(baseline.get("axes", {}).items()):
        now = current.get("axes", {}).get(axis_name)
        if now is None:
            problems.append(f"{axis_name}: axis disappeared from the scoreboard")
            continue

        # THE ARM THAT MATTERS. Aggregate honesty is gameable: turning every
        # sourced code into a declared gap keeps `honest` at 100% while deleting
        # the whole verified layer. Per-code strong-state retention is not.
        lost_strong = sorted(set(base.get("strong_codes", [])) - set(now.get("strong_codes", [])))
        if lost_strong:
            shown = ", ".join(lost_strong[:PRINT_SAMPLE])
            problems.append(
                f"{axis_name}: {len(lost_strong)} code(s) LOST their government locator "
                f"(showing {min(len(lost_strong), PRINT_SAMPLE)}): {shown}"
            )
        if axis_name == "crosswalk" and now.get("adjudicated", 0) < base.get("adjudicated", 0):
            problems.append(
                f"crosswalk: adjudicated inheritance fell "
                f"{base['adjudicated']} -> {now['adjudicated']}"
            )
        if now["honest"] < base["honest"]:
            problems.append(
                f"{axis_name}: honest coverage fell {base['honest']} -> {now['honest']} "
                f"(-{base['honest'] - now['honest']})"
            )
        if now["defect"] > base["defect"]:
            new_codes = sorted(set(now["defect_codes"]) - set(base.get("defect_codes", [])))
            shown = ", ".join(new_codes[:PRINT_SAMPLE])
            suffix = f" (showing {min(len(new_codes), PRINT_SAMPLE)} of {len(new_codes)})" if new_codes else ""
            problems.append(
                f"{axis_name}: bare facts rose {base['defect']} -> {now['defect']}; "
                f"newly bare: {shown}{suffix}"
            )
    return problems


def render(scoreboard: dict[str, Any]) -> str:
    total = scoreboard["total_codes"]
    lines = [f"KBLI completion scoreboard — {total} codes", ""]
    for axis_name, axis in scoreboard["axes"].items():
        pct = 100.0 * axis["honest"] / total if total else 0.0
        lines.append(
            f"  {axis_name:<10} honest {axis['honest']:>5}/{total}  ({pct:.1f}%)"
            f"   locator-bearing: {axis['strong']}"
        )
        for state, count in axis["states"].items():
            lines.append(f"      {state:<32} {count:>5}")
        if axis["defect"]:
            codes = axis["defect_codes"]
            shown = ", ".join(codes[:PRINT_SAMPLE])
            lines.append(f"      BARE codes ({min(len(codes), PRINT_SAMPLE)} of {len(codes)}): {shown}")
        lines.append("")
    xw = scoreboard["axes"]["crosswalk"]
    lines.append(
        f"  crosswalk inheritance adjudicated: {xw['adjudicated']}/{total} "
        "(a mechanical ancestor is honest, not adjudicated — see _coverage_basis)"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--json", action="store_true", help="emit the machine payload")
    parser.add_argument("--check", action="store_true", help="fail on regression vs the baseline")
    parser.add_argument(
        "--update-baseline", action="store_true", help="rewrite the baseline from the current dataset"
    )
    parser.add_argument(
        "--accept-regression",
        action="store_true",
        help="with --update-baseline: record a WORSE state on purpose (say why in the PR)",
    )
    args = parser.parse_args(argv)

    try:
        records = load_records(args.canonical)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: canonical unreadable ({args.canonical}): {exc}")
        return EXIT_CANNOT_VERIFY

    scoreboard = build_scoreboard(records)

    if args.update_baseline:
        # `--update-baseline` is the ratchet's only escape hatch, so it must not
        # be a silent one: rewriting the baseline over a regression would launder
        # the very degradation the gate exists to catch, and the diff would look
        # like routine bookkeeping. Refuse unless the intent is spelled out.
        if args.baseline.exists() and not args.accept_regression:
            try:
                previous = json.loads(args.baseline.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous = None
            if previous:
                problems = ratchet_regressions(scoreboard, previous)
                if problems:
                    print("REFUSING to overwrite the baseline — this would record a regression:")
                    for problem in problems:
                        print(f"  - {problem}")
                    print("\nIf the degradation is intended, re-run with --accept-regression and")
                    print("say why in the PR body; the flag is greppable in the diff on purpose.")
                    return EXIT_REGRESSION
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(scoreboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline written: {args.baseline}")
        return EXIT_OK

    if args.json:
        print(json.dumps(scoreboard, indent=2, sort_keys=True))
    else:
        print(render(scoreboard))

    if not args.check:
        return EXIT_OK

    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: baseline unreadable ({args.baseline}): {exc}")
        return EXIT_CANNOT_VERIFY

    if not baseline.get("axes"):
        # An empty axis map compares nothing and would pass everything. That is
        # "I traversed zero things", which is cannot-verify, never clean (W84).
        print(f"CANNOT VERIFY: baseline has no axes to compare ({args.baseline})")
        return EXIT_CANNOT_VERIFY

    problems = ratchet_regressions(scoreboard, baseline)
    if problems:
        print("\nCOVERAGE REGRESSION — the catalogue got less honest:")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "\nIf this is intentional (a state was redefined), regenerate with "
            "--update-baseline IN THE SAME COMMIT and say why in the PR body."
        )
        return EXIT_REGRESSION

    print("\nratchet OK — no axis lost honest coverage, no new bare facts.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
