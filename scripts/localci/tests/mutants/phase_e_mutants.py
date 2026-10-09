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
    "pe-window-false-green-unchecked": ("and all(type(x) is int and x == 0 for x in fgs)", "and True"),
    "pe-false-green-one-level-only": ('fgs = (counts.get("FALSE_GREEN"), ctx.get("FALSE_GREEN"), rep.get("recorded_context_false_green"))',
                                      'fgs = (counts.get("FALSE_GREEN"),)'),
    "pe-false-green-bool-accepted": ("all(type(x) is int and x == 0 for x in fgs)", "all(x == 0 for x in fgs)"),
    "pe-report-not-object-crashes": ("    if not isinstance(rep, dict):\n", "    if False:\n"),
    "pe-report-bad-date-crashes": ("        except ValueError:\n            age = None", "        except KeyError:\n            age = None"),
    # exactly one write deploy key, because the bypass covers each one
    "pe-keys-at-least-one": ('if len(state["write_keys"]) != 1:', 'if len(state["write_keys"]) < 1:'),
    # deletion and force-push stay forbidden by a ruleset nobody bypasses
    "pe-guard-not-required": ('    if not state["guards"]:', "    if False:"),
    "pe-guard-bypass-ignored": (' and r.get("bypass_actors", None) == []', ""),
    "pe-guard-bypass-unknown-read-as-none": ('r.get("bypass_actors", None) == []', 'not r.get("bypass_actors")'),
    "pe-guard-enforcement-ignored": (' r.get("enforcement") == "active" and', ""),
    "pe-guard-exclude-ignored": (" and not names & set(exclude)", ""),
    "pe-ruleset-coverage-unchecked": ('        if not state["ruleset_covers_branch"]:', "        if False:"),
    # the writes: the right bodies, in the safe order, after the state is on disk, proven after
    "pe-bypass-on-pull-requests-only": ('"actor_type": "DeployKey", "bypass_mode": "always"', '"actor_type": "DeployKey", "bypass_mode": "pull_request"'),
    "pe-update-allows-fetch-and-merge": ('"update_allows_fetch_and_merge": False', '"update_allows_fetch_and_merge": True'),
    "pe-state-not-saved": ("saved = save_state(a.state_dir, state, dig)", "saved = a.state_dir"),
    # what is saved restores exactly, and what cannot be is refused
    "pe-any-source-saved-as-omitted": ('"app_id": -1 if c.get("app_id") is None else c["app_id"]', '"app_id": c.get("app_id")'),
    "pe-push-restrictions-dropped": ('    if doc.get("restrictions"):', "    if False:"),
    "pe-unreadable-protection-read-as-absent": ('if missing and missing in res.stderr and "(HTTP 404)" in res.stderr:', "if missing:"),
    "pe-any-404-read-as-absent": ('if missing and missing in res.stderr and "(HTTP 404)" in res.stderr:', 'if missing and "(HTTP 404)" in res.stderr:'),
    "pe-keys-first-page-only": ("        if len(batch) < 100:\n            return out", "        if True:\n            return out"),
    "pe-fingerprint-not-ssh-keygen-form": ('return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")',
                                           "return hashlib.sha256(blob).hexdigest()"),
    "pe-classic-flag-dropped": ('"required_conversation_resolution", "lock_branch"', '"lock_branch"'),
    "pe-checks-compared-in-order": ("    return norm(a) == norm(b)", "    return a == b"),
    "pe-rollback-repo-unchecked": ('if (saved["repo"], saved["branch"]) != (a.repo, a.branch):', "if False:"),
    "pe-rollback-ruleset-unchecked": ('if live["ruleset_id"] != saved["ruleset_id"]:', "if False:"),
    "pe-restrictions-none-dropped": ('"required_pull_request_reviews": reviews, "restrictions": None}', '"required_pull_request_reviews": reviews}'),
    "pe-contexts-sent-beside-checks": ('checks = {"strict": bool(rsc.get("strict")),', 'checks = {"strict": bool(rsc.get("strict")), "contexts": rsc.get("contexts"),'),
    "pe-empty-dismissal-accepted": ("if reviews.get(key) is not None:", 'if any((reviews.get(key) or {}).get(k) for k in ("users", "teams", "apps")):'),
    # the classic protection goes only after the ruleset's answer shows it restricted
    "pe-ruleset-answer-conditions-unchecked": (' and answer.get("conditions") == state["ruleset"]["conditions"]', ""),
    "pe-enforcement-not-forced": ('rules=TARGET_RULES, bypass_actors=TARGET_BYPASS, enforcement="active")', "rules=TARGET_RULES, bypass_actors=TARGET_BYPASS)"),
    # flipped is a meaning: enforced, covering, the one actor — and an old flip is re-judged, never trusted
    "pe-flipped-ignores-enforcement": ('return (rs.get("enforcement") == "active" and len(rules) == 1', "return (len(rules) == 1"),
    "pe-flipped-ignores-coverage": ('if state["classic"] is None and is_target(state["ruleset"]) and state["ruleset_covers_branch"]:',
                                    'if state["classic"] is None and is_target(state["ruleset"]):'),
    "pe-flipped-by-classic-alone": ('if state["classic"] is None and is_target(state["ruleset"]) and state["ruleset_covers_branch"]:',
                                    'if state["classic"] is None:'),
    "pe-flipped-extra-actor-accepted": ('and len(bypass) == 1 and bypass[0].get("actor_type") == "DeployKey"', 'and bypass[0].get("actor_type") == "DeployKey"'),
    "pe-flipped-by-spelling": ('if state["classic"] is None and is_target(state["ruleset"]) and state["ruleset_covers_branch"]:',
                               'if state["classic"] is None and state["ruleset"]["bypass_actors"] == TARGET_BYPASS and state["ruleset_covers_branch"]:'),
    "pe-flipped-health-unchecked": ("if unsafe := plan_blockers(state, flip=False, merger_key=merger_key):", "if unsafe := []:"),
    # the one write key is the merger's, the ruleset no wider than the branch, a pattern exclusion never trusted
    "pe-key-identity-unchecked": ('elif state["write_keys"][0]["fingerprint"] != merger_key:', "elif False:"),
    "pe-key-unreadable-unnamed": ("elif merger_key is None:", "elif False:"),
    "pe-wider-ruleset-accepted": ('if not state["ruleset_only_branch"]:', "if False:"),
    "pe-exclude-pattern-ignored": (" and not any(_GLOB.search(x) for x in exclude)", ""),
    # the write discipline (README "Phase E flip", W1-W4)
    "pe-read-only-key-counts": (' for k in keys if k.get("read_only") is not True]', " for k in keys]"),
    "pe-unknown-read-only-trusted": ('k.get("read_only") is not True', 'k.get("read_only") is False'),
    "pe-writes-reversed": ("    for i, w in enumerate(writes, 1):\n        if i in before:", "    for i, w in enumerate(reversed(writes), 1):\n        if i in before:"),
    "pe-w1-before-write-unread": ("        if i in before:\n            settled(", "        if False:\n            settled("),
    "pe-w1-after-last-unread": ('    settled(repo, branch, after, f"after write {len(writes)}/{len(writes)}")', "    pass"),
    "pe-answer-unjudged": ("        if i in took and (why := took[i](answer)):", "        if False:"),
    "pe-flip-answer-not-passed": ("expect_mid}, expect_end, {1: ruleset_took})", "expect_mid}, expect_end, {})"),
    "pe-rollback-answer-not-passed": ("expect_mid}, expect_end, {1: classic_took})", "expect_mid}, expect_end, {})"),
    "pe-flip-mid-unread": ("{2: expect_mid}, expect_end, {1: ruleset_took}", "{}, expect_end, {1: ruleset_took}"),
    "pe-rollback-mid-unread": ("{2: expect_mid}, expect_end, {1: classic_took}", "{}, expect_end, {1: classic_took}"),
    "pe-expect-mid-without-the-target": ('expect_mid = with_ruleset(state, writes[0]["body"])', "expect_mid = state"),
    "pe-expected-rules-not-advanced": ('"branch_rules": sorted([*(x for x in state["branch_rules"] if x[0] != rid), *own], key=str)}', '"branch_rules": state["branch_rules"]}'),
    "pe-diverges-ignores-classic": ('    if not same_classic(fresh["classic"], expected["classic"]):\n        out.append("classic protection")',
                                    '    if False:\n        out.append("classic protection")'),
    "pe-diverges-ignores-guards": ('for k in ("guards", "write_keys",', 'for k in ("write_keys",'),
    "pe-diverges-ignores-keys": ('("guards", "write_keys", "ruleset_covers_branch"', '("guards", "ruleset_covers_branch"'),
    "pe-diverges-ignores-applied-rules": ('"ruleset_only_branch", "branch_rules") if fresh[k]', '"ruleset_only_branch") if fresh[k]'),
    "pe-diverges-target-by-spelling": ("if is_target(rx) else rf == rx", "if False else rf == rx"),
    "pe-w1-no-retry": ("        if attempt + 1 < READ_RETRIES:\n            pause(READ_DELAY_S)", "        if False:\n            pause(READ_DELAY_S)"),
    "pe-w1-one-read": ("    for attempt in range(READ_RETRIES):", "    for attempt in range(1):"),
    "pe-w4-only-flip-errors-owned": ("    except Exception as exc:   # W4: after the first write", "    except FlipError as exc:   # W4: after the first write"),
    "pe-w2-unchecked": ('if beside := [f"{t} (ruleset {rid})" for rid, t in state["branch_rules"] if rid != state["ruleset_id"] and t not in ALLOWED_BESIDE]:',
                        "if beside := []:"),
    "pe-w2-own-rule-counted": ('if rid != state["ruleset_id"] and t not in ALLOWED_BESIDE]', "if t not in ALLOWED_BESIDE]"),
    "pe-w2-rules-not-read": ('"branch_rules": sorted(([r.get("ruleset_id"), r.get("type")] for r in applied), key=str),', '"branch_rules": [],'),
    "pe-w3-base-unchecked": ('    if rep.get("base") != branch:', "    if False:"),
    "pe-w3-since-unchecked": ('    if rep.get("since") is not None:', "    if False:"),
    "pe-w3-constants-accepted": (", parse_constant=_no_constant)", ")"),
    "pe-w3-infinite-accepted": (" and math.isfinite(cd) and", " and"),
    "pe-key-title-kept": ('"fingerprint": key_fingerprint(k.get("key"))}', '"fingerprint": key_fingerprint(k.get("key")), "title": k.get("title")}'),
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
