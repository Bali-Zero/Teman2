"""Machine-readable replay-report generator -- the evidence artifact the
ENFORCE gate (Visa Oracle v2 skill, criterion G-b) cites: "20/20 gold
personas replay through the engine with zero unexplained divergences".

Not a fixture -- this module is RUN, never committed output. Two entry
points:

- ``build_report()`` -- pure function, reusable by ``test_gold_replay.py``
  (or any future caller) without touching the filesystem.
- ``python -m backend.tests.services.visa_engine.gold_harness.replay_report
  --out <path>`` -- CLI that writes the report JSON to ``<path>``.

The report's ``overall_pass`` is computed independently of pytest (it
re-runs ``expectations.resolve_expected`` + ``adapter.evaluate_all`` itself)
so it is a standalone artifact a non-pytest consumer (the ENFORCE-gate
checklist, a human) can read without re-deriving pytest's pass/fail logic.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import adapter, loader
from .expectations import resolve_expected


def _proof_to_dict(proof: adapter.ProductProof) -> dict[str, Any]:
    return {
        "proof_state": proof.state.value,
        "reason_codes": list(proof.reason_codes),
        "covered_purposes": sorted(proof.covered_purposes),
        "missing_purposes": sorted(proof.missing_purposes),
        "missing_facts": sorted(f.value for f in proof.missing_facts),
        "score": proof.score,
    }


def _expected_to_dict(expected) -> dict[str, Any]:
    return {
        "proof_state": expected.proof_state,
        "reason_codes": list(expected.reason_codes),
        "covered_purposes": sorted(expected.covered_purposes),
        "missing_purposes": sorted(expected.missing_purposes),
        "missing_facts": None if expected.missing_facts is None else list(expected.missing_facts),
    }


def _product_check_passes(actual: adapter.ProductProof, expected) -> bool:
    if actual.state.value != expected.proof_state:
        return False
    if expected.reason_codes and tuple(actual.reason_codes) != expected.reason_codes:
        return False
    if (
        expected.covered_purposes
        and frozenset(actual.covered_purposes) != expected.covered_purposes
    ):
        return False
    if (
        expected.missing_purposes
        and frozenset(actual.missing_purposes) != expected.missing_purposes
    ):
        return False
    if expected.missing_facts is not None:
        actual_mf = tuple(sorted(f.value for f in actual.missing_facts))
        if actual_mf != expected.missing_facts:
            return False
    return True


def build_report() -> dict[str, Any]:
    pack = loader.load_and_compile_rule_pack()
    personas = loader.load_all_personas()
    product_codes = sorted(p.product_code for p in pack.products)

    persona_reports: list[dict[str, Any]] = []
    total_checks = 0
    passed_checks = 0

    for persona in personas:
        snapshot = persona.derive_snapshot()
        proofs, global_decision = adapter.evaluate_all(
            pack, snapshot, effective_at=loader.GOLD_EFFECTIVE_AT
        )

        product_reports: dict[str, Any] = {}
        persona_pass = True
        for code in product_codes:
            actual = proofs[code]
            expected = resolve_expected(persona.expected, code, pack)
            ok = _product_check_passes(actual, expected)
            total_checks += 1
            passed_checks += int(ok)
            persona_pass = persona_pass and ok
            product_reports[code] = {
                "expected": _expected_to_dict(expected),
                "actual": _proof_to_dict(actual),
                "pass": ok,
            }

        exp = persona.expected
        global_ok = global_decision.state.value == exp["global_state"]
        if "global_reason_codes" in exp:
            global_ok = (
                global_ok and list(global_decision.reason_codes) == exp["global_reason_codes"]
            )
        if "global_missing_facts" in exp:
            actual_mf = sorted(f.value for f in global_decision.missing_facts)
            global_ok = global_ok and actual_mf == exp["global_missing_facts"]
        persona_pass = persona_pass and global_ok

        persona_reports.append(
            {
                "persona_id": persona.persona_id,
                "narrative": persona.narrative,
                "global": {
                    "expected_state": exp["global_state"],
                    "actual_state": global_decision.state.value,
                    "expected_reason_codes": exp.get("global_reason_codes"),
                    "actual_reason_codes": list(global_decision.reason_codes),
                    "expected_missing_facts": exp.get("global_missing_facts"),
                    "actual_missing_facts": sorted(f.value for f in global_decision.missing_facts),
                    "pass": global_ok,
                },
                "products": product_reports,
                "pass": persona_pass,
            }
        )

    overall_pass = all(p["pass"] for p in persona_reports)

    return {
        "gate": "G-b",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pack": {
            "rule_pack_id": str(pack.rule_pack_id),
            "sequence": pack.sequence,
            "version": pack.version,
            "product_count": len(pack.products),
            "rule_count": len(pack.rules),
        },
        "persona_count": len(personas),
        "product_count": len(product_codes),
        "personas": persona_reports,
        "summary": {
            "total_product_checks": total_checks,
            "passed_product_checks": passed_checks,
            "failed_product_checks": total_checks - passed_checks,
            "personas_all_pass": sum(1 for p in persona_reports if p["pass"]),
            "personas_with_divergence": sum(1 for p in persona_reports if not p["pass"]),
        },
        "overall_pass": overall_pass,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", required=True, type=Path, help="path to write the replay report JSON to"
    )
    args = parser.parse_args(argv)

    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=False)
        f.write("\n")

    print(f"wrote {args.out} -- overall_pass={report['overall_pass']}")
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
