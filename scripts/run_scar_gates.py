#!/usr/bin/env python3
"""A1 / Loop-B scar-gate runner — the wiring half that closes Ring A1.

The pieces existed but were never connected (TAC self-loop 2026-06-27):
  - check_scar_test() in verify_the_verifiers.py  → the engine (ARMED/WARN/DISARMED)
  - infra/scar-gates/test_W82_*.py                → 1 real gate
  - infra/scar-gates/MANIFEST.json                → maps all 65 scars (1 armed, 64 prose-debt)
…but nothing RAN the engine over the manifest. This does. It makes the Loop-B debt
CONTABILE (a number you can watch shrink), not invisible — the superscar #2 antidote
applied to A1 itself.

Verdict:
  - exit 0  → no scar has RE-BITTEN (no DISARMED). WARN (prose-only debt) is allowed.
  - exit 1  → at least one armed scar's regression test FAILS = the disease re-opened.
Prose-only scars are visible WARN debt, never silent-green and never a hard fail —
you cannot be blocked by a test you haven't written yet, only by one that regressed.

    python3 scripts/run_scar_gates.py            # human report
    python3 scripts/run_scar_gates.py --json     # machine report
    python3 scripts/run_scar_gates.py --strict   # exit 1 also if armed-coverage drops (CI ratchet)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_the_verifiers as v  # noqa: E402

REPO = HERE.parent
MANIFEST = REPO / "infra" / "scar-gates" / "MANIFEST.json"
GATES_DIR = REPO / "infra" / "scar-gates"


def _resolve_target(gate: dict) -> dict:
    """MANIFEST targets are relative to infra/scar-gates/; make them absolute for the engine."""
    g = dict(gate)
    if not g.get("prose_only") and "target" in g:
        g["target"] = str((GATES_DIR / g["target"]).resolve())
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if armed-coverage drops below the manifest's recorded count")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print(f"FATAL: manifest not found: {MANIFEST}", file=sys.stderr)
        return 2
    manifest = json.loads(MANIFEST.read_text())
    gates = manifest.get("gates", [])

    results = [v.check_scar_test(_resolve_target(g)) for g in gates]
    armed = [r for r in results if r.verdict == v.ARMED]
    warn = [r for r in results if r.verdict == v.WARN]
    disarmed = [r for r in results if r.verdict == v.DISARMED]

    summary = {
        "total": len(results),
        "armed": len(armed),
        "warn_prose_debt": len(warn),
        "disarmed_regressed": len(disarmed),
        "manifest_recorded_armed": manifest.get("armed", 0),
    }

    if args.json:
        print(json.dumps({
            "summary": summary,
            "disarmed": [{"id": r.gate_id, "detail": r.detail} for r in disarmed],
        }, indent=2))
    else:
        print(f"=== Scar-gate runner (A1/Loop-B) — {manifest.get('generated','?')} ===")
        print(f"  ARMED (disease still dead)   : {len(armed)}")
        print(f"  WARN  (prose-only debt)      : {len(warn)}")
        print(f"  DISARMED (scar RE-BIT!)      : {len(disarmed)}")
        for r in disarmed:
            print(f"    ✗ {r.gate_id}: {r.detail}")
        if not disarmed:
            print("  VERDICT: GREEN — no scar regressed (prose debt is visible, not silent)")
        else:
            print("  VERDICT: RED — a scar re-opened; fix before merge")

    if disarmed:
        return 1
    if args.strict and len(armed) < manifest.get("armed", 0):
        print(f"STRICT: armed coverage dropped {manifest.get('armed',0)}→{len(armed)} "
              f"(a gate file went missing)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
