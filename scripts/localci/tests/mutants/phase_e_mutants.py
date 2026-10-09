"""Replayable mutation sweep for the phase E flip (phase_e_flip.py) against test_phase_e_flip.py — the same harness, rules and
verdicts as merger_mutants.py (one textual rule on a temporary copy; KILLED only on a pytest failure; STALE when the rule's
text no longer occurs exactly once), kept in its own table so the flip's lane never edits the merger's.

    python3 scripts/localci/tests/mutants/phase_e_mutants.py [--only NAME ...] [--list]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from merger_mutants import copy_tree, run_tests, verdict

PEF, T = "scripts/localci/phase_e_flip.py", ("scripts/localci/tests/test_phase_e_flip.py",)

# name: (text that must occur once in phase_e_flip.py, replacement) — every rule must turn the test file red
MUTANTS = {
    # the operator's confirmation binds the very state the plan read
    "pe-confirm-unchecked": ('    if a.confirm != dig:\n        print("REFUSED: --confirm does not match this plan\'s digest (re-read',
                             '    if False:\n        print("REFUSED: --confirm does not match this plan\'s digest (re-read'),
    "pe-digest-unbound-to-state": ('json.dumps({"state": state, "writes": writes}', 'json.dumps({"writes": writes}'),
    "pe-rollback-confirm-unchecked": ('    if a.confirm != dig:\n        print("REFUSED: --confirm does not match this plan\'s digest", file',
                                      '    if False:\n        print("REFUSED: --confirm does not match this plan\'s digest", file'),
    "pe-blockers-ignored": ("    if all_blockers:\n", "    if False:\n"),
    # READY is the report's, fresh, of this repo, and consistent with its own window
    "pe-ready-not-required": ('if rep.get("phase_e_ready") is not True:', "if False:"),
    "pe-ready-truthy": ('if rep.get("phase_e_ready") is not True:', 'if not rep.get("phase_e_ready"):'),
    "pe-report-repo-unchecked": ('if rep.get("repo") != repo:', "if False:"),
    "pe-report-future-accepted": ("if age > REPORT_MAX_AGE or age < -REPORT_MAX_SKEW:", "if age > REPORT_MAX_AGE:"),
    "pe-report-age-unchecked": ("if age > REPORT_MAX_AGE or age < -REPORT_MAX_SKEW:", "if age < -REPORT_MAX_SKEW:"),
    "pe-window-merges-unchecked": ("cm >= READY_MERGES", "cm >= 0"),
    "pe-window-days-unchecked": ("cd >= READY_DAYS", "cd >= 0"),
    "pe-window-false-green-unchecked": ("and fg == 0)", "and True)"),
    # exactly one write deploy key, because the bypass covers each one
    "pe-keys-at-least-one": ('if len(state["write_keys"]) != 1:', 'if len(state["write_keys"]) < 1:'),
    "pe-read-only-key-counts": (' for k in keys if k.get("read_only") is False]', " for k in keys]"),
    # deletion and force-push stay forbidden by a ruleset nobody bypasses
    "pe-guard-not-required": ('    if not state["guards"]:', "    if False:"),
    "pe-guard-bypass-ignored": (' and not r.get("bypass_actors")', ""),
    "pe-guard-enforcement-ignored": (' r.get("enforcement") == "active" and', ""),
    "pe-guard-exclude-ignored": (' and not names & set(ref.get("exclude") or [])', ""),
    "pe-ruleset-coverage-unchecked": ('        if not state["ruleset_covers_branch"]:', "        if False:"),
    # the writes: the right bodies, in the safe order, after the state is on disk, proven after
    "pe-bypass-on-pull-requests-only": ('"actor_type": "DeployKey", "bypass_mode": "always"', '"actor_type": "DeployKey", "bypass_mode": "pull_request"'),
    "pe-update-allows-fetch-and-merge": ('"update_allows_fetch_and_merge": False', '"update_allows_fetch_and_merge": True'),
    "pe-writes-reversed": ("    for i, w in enumerate(writes, 1):\n        args =", "    for i, w in enumerate(reversed(writes), 1):\n        args ="),
    "pe-state-not-saved": ("saved = save_state(a.state_dir, state, dig)", "saved = a.state_dir"),
    "pe-post-flip-unverified": ('if phase(after) != "flipped":', "if False:"),
    # what is saved restores exactly, and what cannot be is refused
    "pe-any-source-saved-as-omitted": ('"app_id": -1 if c.get("app_id") is None else c["app_id"]', '"app_id": c.get("app_id")'),
    "pe-push-restrictions-dropped": ('    if doc.get("restrictions"):', "    if False:"),
    "pe-unreadable-protection-read-as-absent": ('if missing_ok and "(HTTP 404)" in res.stderr:', "if missing_ok:"),
    "pe-rollback-repo-unchecked": ('if (saved["repo"], saved["branch"]) != (a.repo, a.branch):', "if False:"),
    "pe-rollback-ruleset-unchecked": ('if live["ruleset_id"] != saved["ruleset_id"]:', "if False:"),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mutation sweep for the phase E flip against its tests.")
    ap.add_argument("--only", nargs="+", metavar="NAME", help="run only these mutants")
    ap.add_argument("--list", action="store_true", help="print the table and exit")
    a = ap.parse_args(argv)
    names = a.only or list(MUTANTS)
    if unknown := [n for n in names if n not in MUTANTS]:
        print(f"unknown mutant(s): {unknown}", file=sys.stderr)
        return 2
    if a.list:
        print("\n".join(names))
        return 0
    with tempfile.TemporaryDirectory(prefix="phase-e-mutants-") as tmp:
        tree = Path(tmp)
        copy_tree(tree)
        original = (tree / PEF).read_text()
        if (rc := run_tests(tree, T)) != 0:
            print(f"baseline: the unmutated copy gives pytest exit {rc} — nothing to measure", file=sys.stderr)
            return 2
        survived, stale, errors = [], [], []
        for n in names:
            old, new = MUTANTS[n]
            if original.count(old) != 1 or old == new:
                stale.append(n)
                print(f"{n:42} STALE (the rule's text occurs {original.count(old)} times)", flush=True)
                continue
            (tree / PEF).write_text(original.replace(old, new))
            v = verdict(run_tests(tree, T))
            (tree / PEF).write_text(original)
            if v == "SURVIVED":
                survived.append(n)
            elif v != "KILLED":
                errors.append(n)
            print(f"{n:42} {v}", flush=True)
    killed = len(names) - len(survived) - len(stale) - len(errors)
    print(f"{killed}/{len(names)} killed; survivors: {survived or 'none'}; errors: {errors or 'none'}; stale: {stale or 'none'}")
    return 1 if survived or stale or errors else 0


if __name__ == "__main__":
    sys.exit(main())
