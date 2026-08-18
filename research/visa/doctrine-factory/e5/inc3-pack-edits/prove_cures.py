"""E5 increment 3, Step 3 — throwaway proof script (NOT a repo test, NOT
imported by anything). Loads the two ORIGINAL defective seq-7 rules and the
E33G cure objects in ``cure-e33g.json`` and runs the real inc-2 lint
functions from ``backend.scripts.visa_engine.compile_claims`` against their
``when`` clauses — guilt on the originals, innocence on the cure.

E33E has NO cure object (see cure-e33e.md: the claims ledger supports
BOTH-required/AND, not OR, for the deposit/income basis, so this session
stopped per the spec's own explicit STOP-and-flag clause rather than
author an ungrounded rule) — this script therefore only reconfirms guilt
on the original ``el.e33e.deposit-income-basis``, run fresh in THIS turn
rather than cited from the doctrine card's prior claim.

Run from apps/backend-rag with the venv active:

    PYTHONPATH=. python ../../research/visa/doctrine-factory/e5/inc3-pack-edits/prove_cures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
PACK_PATH = (
    REPO_ROOT
    / "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json"
)
CURE_E33G_PATH = Path(__file__).resolve().parent / "cure-e33g.json"

sys.path.insert(0, str(REPO_ROOT / "apps/backend-rag"))

from backend.scripts.visa_engine.compile_claims import (  # noqa: E402
    lint_duplicate_subtree,
    lint_unsatisfiable_condition,
)
from backend.services.visa_engine.ast import collect_fact_paths, parse_condition  # noqa: E402
from backend.services.visa_engine.models import Rule  # noqa: E402


def find_rule(pack: dict, rule_id: str) -> dict:
    for rule in pack["rules"]:
        if rule["rule_id"] == rule_id:
            return rule
    raise KeyError(f"rule_id {rule_id!r} not found in pack")


def report(label: str, findings: list, *, expect_clean: bool) -> bool:
    ok = (not findings) == expect_clean
    verdict = "PASS" if ok else "FAIL"
    print(f"[{verdict}] {label} — expect_clean={expect_clean}, findings={len(findings)}")
    for f in findings:
        print(f"    - {f}")
    return ok


def main() -> int:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    cure = json.loads(CURE_E33G_PATH.read_text(encoding="utf-8"))

    all_ok = True

    # --- GUILT: original seq-7 defective rules -----------------------------
    orig_e33e = find_rule(pack, "el.e33e.deposit-income-basis")
    unsat_findings, skip_note = lint_unsatisfiable_condition(
        rule_id="el.e33e.deposit-income-basis", when=orig_e33e["when"]
    )
    assert skip_note is None, f"unexpected skip: {skip_note}"
    all_ok &= report(
        "GUILT: original el.e33e.deposit-income-basis is UNSATISFIABLE",
        unsat_findings,
        expect_clean=False,
    )

    orig_e33g = find_rule(pack, "el.e33g.income-60k-manual")
    dup_findings = lint_duplicate_subtree(
        rule_id="el.e33g.income-60k-manual", when=orig_e33g["when"]
    )
    all_ok &= report(
        "GUILT: original el.e33g.income-60k-manual has a duplicate subtree",
        dup_findings,
        expect_clean=False,
    )
    # The original is also NOT unsatisfiable (it fires for every clean
    # remote worker) — worth recording explicitly since VACUOUS and UNSAT
    # are different defects and this rule is only guilty of the former.
    unsat_findings_orig_e33g, skip_note2 = lint_unsatisfiable_condition(
        rule_id="el.e33g.income-60k-manual", when=orig_e33g["when"]
    )
    assert skip_note2 is None, f"unexpected skip: {skip_note2}"
    report(
        "INFO (not a defect): original el.e33g.income-60k-manual is satisfiable "
        "(fires for every clean remote worker — that's the VACUOUS problem, "
        "not an UNSAT one)",
        unsat_findings_orig_e33g,
        expect_clean=True,
    )

    # --- INNOCENCE: cured E33G rules ----------------------------------------
    cured_rules = {r["rule_id"]: r for r in cure["rules"]}

    remote_work_config = cured_rules["el.e33g.remote-work-configuration"]
    dup_findings_cured = lint_duplicate_subtree(
        rule_id="el.e33g.remote-work-configuration", when=remote_work_config["when"]
    )
    all_ok &= report(
        "INNOCENCE: cured el.e33g.remote-work-configuration has NO duplicate subtree",
        dup_findings_cured,
        expect_clean=True,
    )
    unsat_findings_cured, skip_note3 = lint_unsatisfiable_condition(
        rule_id="el.e33g.remote-work-configuration", when=remote_work_config["when"]
    )
    assert skip_note3 is None, f"unexpected skip: {skip_note3}"
    all_ok &= report(
        "INNOCENCE: cured el.e33g.remote-work-configuration is satisfiable",
        unsat_findings_cured,
        expect_clean=True,
    )

    income_evidence = cured_rules["review.e33g.income-evidence"]
    dup_findings_review = lint_duplicate_subtree(
        rule_id="review.e33g.income-evidence", when=income_evidence["when"]
    )
    all_ok &= report(
        "INNOCENCE: new review.e33g.income-evidence has NO duplicate subtree",
        dup_findings_review,
        expect_clean=True,
    )
    unsat_findings_review, skip_note4 = lint_unsatisfiable_condition(
        rule_id="review.e33g.income-evidence", when=income_evidence["when"]
    )
    assert skip_note4 is None, f"unexpected skip: {skip_note4}"
    all_ok &= report(
        "INNOCENCE: new review.e33g.income-evidence is satisfiable",
        unsat_findings_review,
        expect_clean=True,
    )

    # --- Schema validation: both cured rule objects parse as real Rule -----
    for rule_id, rule_dict in cured_rules.items():
        # Strip the informational, non-schema keys this file annotates with
        # (never part of the Rule schema — mirrors how compile_claims.py's
        # manifest entries carry claim_ids/caveats alongside `rule`).
        clean = {
            k: v for k, v in rule_dict.items() if not k.startswith("_")
        }
        parsed_when = parse_condition(clean["when"])
        derived_facts = sorted(collect_fact_paths(parsed_when))
        payload = {**clean, "required_facts": derived_facts}
        try:
            Rule.model_validate(payload)
            print(f"[PASS] {rule_id} validates as a real Rule (required_facts derived: {derived_facts})")
        except Exception as exc:  # noqa: BLE001 - proof script, want to see everything
            print(f"[FAIL] {rule_id} failed Rule.model_validate: {exc}")
            all_ok = False

    print()
    print("=== SUMMARY ===")
    print("ALL CHECKS PASSED" if all_ok else "AT LEAST ONE CHECK FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
