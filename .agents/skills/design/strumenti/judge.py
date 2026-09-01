#!/usr/bin/env python3
"""Round-two judge: did the revision fix what was named, and what did it break?

Three axes, and the third is the one that matters. Anyone can delete the line a
critic pointed at. The question is whether the correction was itself correct --
the fix-of-a-fix trap. So every defect class and every declared value is
compared against round one, and a defect that appears only in round two is
reported as INTRODUCED, weighted the same as one that PERSISTS.

Composes the two calibrated instruments rather than re-implementing them:
  measure.py  declaration <-> pixels
  defects.py  the five classes round one had to find by hand
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SEATS = ("qwen", "agy", "claude", "codex")
CLASSES = ("dead_controls", "duplicate_strings", "heading_order", "double_announced", "struck_text")
CHECKED = ("ground", "accent", "dark_travel_multiplier", "type_base_px", "type_tiers")


def sig(cls: str, item: dict) -> str:
    """A stable identity for one defect, so round 1 and round 2 can be compared."""
    if cls == "dead_controls":
        return f"{item['kind']}:{item.get('label', '')}"
    if cls == "duplicate_strings":
        return f"dup:{item['text']}"
    if cls == "heading_order":
        return f"{item['kind']}:{item['detail']}"
    if cls == "double_announced":
        return f"double:{item['label'][:50]}"
    if cls == "struck_text":
        return f"struck:{item['text']}"
    return json.dumps(item, sort_keys=True)


def defect_set(res: dict) -> set[str]:
    return {sig(c, it) for c in CLASSES for it in res.get(c, [])}


def near(a, b, tol=0.06) -> bool:
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return str(a).upper() == str(b).upper()
    return abs(a - b) <= max(tol, abs(b) * tol)


def derivability(decl: dict, der: dict) -> list[tuple[str, str, str, bool]]:
    rows = []
    pairs = {
        "ground": (decl.get("ground"), der.get("ground_light")),
        "accent": (decl.get("accent"), None),          # accent is not derivable from ground alone
        "dark_travel_multiplier": (decl.get("dark_travel_multiplier"), der.get("dark_travel_multiplier")),
        "type_base_px": (decl.get("type_base_px"), der.get("type_base_px")),
        "type_tiers": (decl.get("type_tiers"), der.get("type_tiers")),
    }
    for k in CHECKED:
        d, m = pairs[k]
        if m is None:
            continue
        rows.append((k, str(d), str(m), near(d, m)))
    return rows


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1])            # ui-contest
    r1, r2 = root / "final", root / "r2" / "entries"
    here = pathlib.Path(__file__).parent.parent

    present = [s for s in SEATS if (r2 / s / "ui.html").exists()]
    if not present:
        print("no round-two entries on disk yet")
        return 1

    subprocess.run([sys.executable, str(here / "defects.py"), str(r1)],
                   capture_output=True, cwd="/tmp", check=True)
    subprocess.run([sys.executable, str(here / "defects.py"), str(r2)],
                   capture_output=True, cwd="/tmp", check=True)
    d1 = json.loads((r1 / "defects.json").read_text())["seats"]
    d2 = json.loads((r2 / "defects.json").read_text())["seats"]

    m2 = json.loads(subprocess.run(
        [sys.executable, str(here / "measure.py")] + [str(r2 / s / "ui.html") for s in present],
        capture_output=True, text=True, cwd="/tmp", check=True).stdout)

    report = {}
    for s in present:
        before, after = defect_set(d1[s]), defect_set(d2[s])
        decl = json.loads((r2 / s / "generator.json").read_text())
        rows = derivability(decl, m2[s]["derived"])
        hard = m2[s]
        report[s] = {
            "fixed": sorted(before - after),
            "persists": sorted(before & after),
            "introduced": sorted(after - before),
            "derivability": rows,
            "derivability_score": f"{sum(1 for r in rows if r[3])}/{len(rows)}",
            "contrast_failures": {k: len(v["contrast_failures"]) for k, v in hard["states"].items()},
            "overflow": {k: v.get("h_overflow") for k, v in hard["states"].items()},
            "small_targets": hard["states"]["mobile/light"].get("small_targets", []),
            "unsettled": hard.get("unsettled", []),
        }

    for s, r in report.items():
        print(f"== {s} ==")
        print(f"  FIXED      ({len(r['fixed'])}): " + ("; ".join(r["fixed"]) or "-"))
        print(f"  PERSISTS   ({len(r['persists'])}): " + ("; ".join(r["persists"]) or "-"))
        print(f"  INTRODUCED ({len(r['introduced'])}): " + ("; ".join(r["introduced"]) or "-"))
        print(f"  derivability {r['derivability_score']}")
        for k, d, m, ok in r["derivability"]:
            print(f"    {'ok ' if ok else 'NO '} {k}: declared {d} / measured {m}")
        cf = sum(r["contrast_failures"].values())
        ov = [k for k, v in r["overflow"].items() if v]
        print(f"  contrast failures {cf} | overflow {ov or 'none'} | small targets {len(r['small_targets'])}")
        if r["unsettled"]:
            print(f"  UNSETTLED (colour still moving when read): {r['unsettled']}")
        print()

    (root / "r2" / "judgement.json").write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
