"""Replayable mutation sweep for the phase E flip (phase_e_flip.py) against test_phase_e_flip.py, and for its step 1
(hand_report.sh, and the tick's extraction it must equal) against test_hand_report.py — the same harness, rules and verdicts
as merger_mutants.py (one textual rule on a temporary copy; KILLED only on a pytest failure; STALE when the rule's text no
longer occurs exactly once), kept in its own table so the flip's lane never edits the merger's.

    python3 scripts/localci/tests/mutants/phase_e_mutants.py [--only NAME ...] [--list]
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from merger_mutants import ROOT, copy_tree, run_tests, verdict

PEF, T = "scripts/localci/phase_e_flip.py", ("scripts/localci/tests/test_phase_e_flip.py",)
HR, TICK, TH = "scripts/localci/hand_report.sh", "scripts/localci/localci_merger_tick.sh", ("scripts/localci/tests/test_hand_report.py",)
PLIST = "infra/launchagents/com.balizero.localci-merger.plist"   # test_hand_report.py reads launchd's PATH from it

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
    "pe-report-age-unchecked": ("        elif age > max_age:", "        elif False:"),
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
    "pe-guard-bypass-ignored": (' and r.get("bypass_actors", None) == []', ""),
    "pe-guard-bypass-unknown-read-as-none": ('r.get("bypass_actors", None) == []', 'not r.get("bypass_actors")'),
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
    "pe-answer-unjudged": ("        if i in took and (why := took[i](answer)):", "        if False:"),
    "pe-expect-mid-without-the-target": ('expect_mid = with_ruleset(state, writes[0]["body"])', "expect_mid = state"),
    "pe-diverges-ignores-classic": ('    if not same_classic(fresh["classic"], expected["classic"]):\n        out.append("classic protection")',
                                    '    if False:\n        out.append("classic protection")'),
    "pe-diverges-ignores-guards": ('for k in ("guards", "write_keys",', 'for k in ("write_keys",'),
    "pe-diverges-ignores-keys": ('("guards", "write_keys", "ruleset_covers_branch"', '("guards", "ruleset_covers_branch"'),
    "pe-diverges-target-by-spelling": ("if is_target(rx) else rf == rx", "if False else rf == rx"),
    "pe-w1-no-retry": ("        if attempt + 1 < READ_RETRIES:\n            pause(READ_DELAY_S)", "        if False:\n            pause(READ_DELAY_S)"),
    "pe-w1-one-read": ("    for attempt in range(READ_RETRIES):", "    for attempt in range(1):"),
    "pe-w2-own-rule-counted": ('if rid != state["ruleset_id"] and t not in ALLOWED_BESIDE]', "if t not in ALLOWED_BESIDE]"),
    "pe-w3-base-unchecked": ('    if rep.get("base") != branch:', "    if False:"),
    "pe-w3-constants-accepted": (", parse_constant=_no_constant)", ")"),
    # the write discipline RULED 2026-10-10 (Q, W1 before every write, W5 after every write, W2-W4)
    # (no rule for the guard's enforcement check: rules/branches lists active rules only, so the GitHub-side proof below
    # already refuses a disabled guard — the two are equivalent by construction)
    "pe-guard-not-required": ("    if not proven:", "    if False:"),
    "pe-list-target-trusted": ('if r.get("source_type", "Repository") == "Repository"]', 'if r.get("source_type", "Repository") == "Repository" and r.get("target") == "branch"]'),
    "pe-writes-reversed": ("    for i, w in enumerate(writes, 1):\n        try:\n            fresh = read_state(repo, branch)",
                           "    for i, w in enumerate(reversed(writes), 1):\n        try:\n            fresh = read_state(repo, branch)"),
    "pe-w1-before-write-unread": ("        if differ := diverges(fresh, expected[i - 1]):", "        if False:"),
    "pe-w5-after-write-unread": ('        settled(repo, branch, expected[i], f"after write {i}/{n}")', "        pass"),
    "pe-w5-read-error-not-retried": ("        except FlipError as exc:   # a failed read is no read", "        except KeyError as exc:   # a failed read is no read"),
    "pe-flip-answer-not-passed": ("execute(a.repo, a.branch, writes, expected, {1: ruleset_took}, sent, recheck=still_ready)", "execute(a.repo, a.branch, writes, expected, {}, sent, recheck=still_ready)"),
    "pe-rollback-first-answer-unjudged": ("{1: classic_took, 2: ruleset_back}, sent)", "{2: ruleset_back}, sent)"),
    "pe-rollback-second-answer-unjudged": ("{1: classic_took, 2: ruleset_back}, sent)", "{1: classic_took}, sent)"),
    "pe-flip-intends-no-change": ('expected = [state, expect_mid, {**expect_mid, "classic": None}]', 'expected = [state, state, {**expect_mid, "classic": None}]'),
    "pe-rollback-intends-no-change": ('expected = [live, expect_mid, with_ruleset(expect_mid, saved["ruleset"])]', 'expected = [live, live, with_ruleset(expect_mid, saved["ruleset"])]'),
    "pe-w4-ctrl-c-escapes": ("    except BaseException as exc:   # W4: Ctrl-C included", "    except Exception as exc:   # W4: Ctrl-C included"),
    "pe-w4-unsent-read-as-written": ("        if not sent:\n            print(f\"REFUSED: {type(exc).__name__}: {exc}\\n  nothing was written; the state file",
                                     "        if False:\n            print(f\"REFUSED: {type(exc).__name__}: {exc}\\n  nothing was written; the state file"),
    "pe-w4-sent-recorded-never": ("        sent.append(i)   # from here the write may have landed", "        pass   # from here the write may have landed"),
    "pe-quiescence-unrequired-flip": ("    if not a.quiescent:\n        print(\"REFUSED: \" + QUIESCENCE, file=sys.stderr)\n        return EXIT_REFUSED\n    if all_blockers:",
                                      "    if False:\n        print(\"REFUSED: \" + QUIESCENCE, file=sys.stderr)\n        return EXIT_REFUSED\n    if all_blockers:"),
    "pe-w3-since-unchecked": ('    elif rep["since"] is not None:', "    elif False:"),
    "pe-w3-since-key-optional": ('    if "since" not in rep:', "    if False:"),
    "pe-w3-infinite-accepted": ("(type(cd) is int or (type(cd) is float and math.isfinite(cd)))", "(type(cd) is int or type(cd) is float)"),
    "pe-applied-rule-parameters-dropped": ('[r.get("ruleset_id"), r.get("type"), r.get("ruleset_source_type"), r.get("parameters")]', '[r.get("ruleset_id"), r.get("type")]'),
    "pe-applied-rules-compared-by-type-only": ("    if applied_rules(fresh) != applied_rules(expected):", "    if [x[:2] for x in fresh[\"branch_rules\"]] != [x[:2] for x in expected[\"branch_rules\"]]:"),
    "pe-enforce-admins-as-int": ('"enforce_admins": bool((doc.get("enforce_admins") or {}).get("enabled"))', '"enforce_admins": int(bool((doc.get("enforce_admins") or {}).get("enabled")))'),
    "pe-expected-rules-not-advanced": ('"branch_rules": sorted([*(x for x in state["branch_rules"] if x[0] != rid), *own], key=lambda x: json.dumps(x, sort_keys=True))}',
                                       '"branch_rules": state["branch_rules"]}'),
    "pe-diverges-ignores-applied-rules": ("    if applied_rules(fresh) != applied_rules(expected):", "    if False:"),
    "pe-w2-unchecked": ('if beside := [f"{t} (ruleset {rid})" for rid, t, *_ in state["branch_rules"] if rid != state["ruleset_id"] and t not in ALLOWED_BESIDE]:',
                        "if beside := []:"),
    "pe-w2-rules-not-read": ('            "branch_rules": sorted(([r.get("ruleset_id"), r.get("type"), r.get("ruleset_source_type"), r.get("parameters")] for r in applied),',
                             '            "branch_rules": sorted(([r.get("ruleset_id"), r.get("type"), r.get("ruleset_source_type"), r.get("parameters")] for r in []),'),
    "pe-guard-not-proven-by-github": ('proven = [g for g in state["guards"] if {(g["id"], "deletion"), (g["id"], "non_fast_forward")} <= {tuple(x[:2]) for x in state["branch_rules"]}]',
                                      'proven = state["guards"]'),
    "pe-quiescence-unrequired-rollback": ("    if not a.quiescent:\n        print(\"REFUSED: \" + QUIESCENCE, file=sys.stderr)\n        return EXIT_REFUSED\n    # the intended states",
                                          "    if False:\n        print(\"REFUSED: \" + QUIESCENCE, file=sys.stderr)\n        return EXIT_REFUSED\n    # the intended states"),
    "pe-w4-rollback-ctrl-c-escapes": ("    except BaseException as exc:   # W4\n", "    except Exception as exc:   # W4\n"),
    "pe-rollback-saved-ruleset-unchecked": ('    if not isinstance(saved["ruleset"], dict) or ruleset_body(saved["ruleset"]) != saved["ruleset"] or not (',
                                            '    if False and ('),
    "pe-rollback-saved-classic-unchecked": ("    if not classic_fields <= set(saved[\"classic\"]):", "    if False:"),
    "pe-diverges-ruleset-id-ignored": ('fresh["ruleset_id"] != expected["ruleset_id"] or not same_ruleset', "not same_ruleset"),
    "pe-state-checksum-unchecked": ('        if not isinstance(saved, dict) or saved.get("checksum") != state_checksum(saved):', "        if not isinstance(saved, dict):"),
    "pe-state-checksum-not-saved": ('json.dump({**doc, "checksum": state_checksum(doc)}, fh, indent=2, sort_keys=True)', "json.dump(doc, fh, indent=2, sort_keys=True)"),
    "pe-key-pub-not-text-crashes": ("    except (OSError, UnicodeError):   # missing", "    except OSError:   # missing"),
    "pe-pre-write-error-traceback": ("    except (Exception, KeyboardInterrupt) as exc:   # Ctrl-C included", "    except (FlipError, KeyboardInterrupt) as exc:   # Ctrl-C included"),
    "pe-ruleset-bool-for-int": ("    return {k: doc[k] for k in RULESET_FIELDS}",
                                "    return {k: (json.loads(json.dumps(doc[k]).replace('\"min_entries_to_merge\": 1', '\"min_entries_to_merge\": true')) if k == \"rules\" else doc[k]) for k in RULESET_FIELDS}"),
    # the fake is specified by GitHub's own request schemas (RULED 2026-10-10): bodies GitHub would refuse must fail the suite
    "pe-ruleset-rule-type-typo": ("    return {k: doc[k] for k in RULESET_FIELDS}",
                                  "    return {k: (json.loads(json.dumps(doc[k]).replace('\"merge_queue\"', '\"merge_queu\"')) if k == \"rules\" else doc[k]) for k in RULESET_FIELDS}"),
    "pe-ruleset-exclude-string": ("    return {k: doc[k] for k in RULESET_FIELDS}",
                                  "    return {k: (json.loads(json.dumps(doc[k]).replace('\"exclude\": []', '\"exclude\": \"\"')) if k == \"conditions\" else doc[k]) for k in RULESET_FIELDS}"),
    "pe-report-not-rechecked": ("{1: ruleset_took}, sent, recheck=still_ready)", "{1: ruleset_took}, sent, recheck=None)"),
    "pe-flip-sent-not-tracked": ("    a.sent = sent   # main reads it", "    pass   # main reads it"),
    "pe-rollback-sent-not-tracked": ("    a.sent, a.state_file = sent, a.rollback", "    a.state_file = a.rollback"),
    "pe-main-ctrl-c-escapes": ("    except (Exception, KeyboardInterrupt) as exc:   # Ctrl-C included", "    except Exception as exc:   # Ctrl-C included"),
    "pe-plan-margin-ignored": ("rep_blockers, rep_line = read_report(a.report, a.repo, a.branch, max_age=REPORT_MAX_AGE - APPLY_MARGIN)",
                               "rep_blockers, rep_line = read_report(a.report, a.repo, a.branch)"),
    "pe-recheck-uses-margin": ('        return "; ".join(read_report(a.report, a.repo, a.branch)[0])',
                               '        return "; ".join(read_report(a.report, a.repo, a.branch, max_age=REPORT_MAX_AGE - APPLY_MARGIN)[0])'),
    "pe-report-ahead-accepted": ("        elif age < -REPORT_MAX_SKEW:", "        elif False:"),
    "pe-after-send-state-file-lost": ("    a.sent, a.state_file = sent, a.rollback", "    a.sent, a.state_file = sent, None"),
    "pe-key-title-kept": ('"fingerprint": key_fingerprint(k.get("key"))}', '"fingerprint": key_fingerprint(k.get("key")), "title": k.get("title")}'),
}

# name: (file, text that must occur once in it, replacement) — every rule must turn test_hand_report.py red
HAND_MUTANTS = {
    "hr-ref-order-swapped": (HR, 'REF=refs/merger/wrapper\nSHA="$(git -C "$STATE/repo.git" rev-parse --verify --quiet "$REF^{commit}")" \\\n'
                                 '  || { REF=refs/merger/base;',
                             'REF=refs/merger/base\nSHA="$(git -C "$STATE/repo.git" rev-parse --verify --quiet "$REF^{commit}")" \\\n'
                                 '  || { REF=refs/merger/wrapper;'),
    "hr-partial-scrub": (HR, 'exec env -i HOME="$HOME"', 'exec env -u GH_TOKEN -u GIT_DIR -u PYTHONPATH HOME="$HOME"'),
    "hr-sentinel-presettable": (HR, 'if [ "${LOCALCI_HAND_REPORT_CLEAN:-}" != "$$" ]; then', 'if [ -z "${LOCALCI_HAND_REPORT_CLEAN:-}" ]; then'),
    "hr-path-without-homebrew": (HR, 'PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"', 'PATH="/usr/bin:/bin"'),
    "hr-not-isolated": (HR, '"$STATE/venv/bin/python" -I ', '"$STATE/venv/bin/python" '),
    "hr-git-isolation-dropped": (HR, "export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_ATTR_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0", ":"),
    "hr-git-config-count-unexported": (HR, "export GIT_CONFIG_COUNT=3 ", "GIT_CONFIG_COUNT=3 "),
    "hr-no-cleanup": (HR, "trap 'rm -rf \"$CODE\"' EXIT\n", ""),
    "hr-runner-dropped": (HR, "merger.py hosted_compare.py runner.py prune.py", "merger.py hosted_compare.py prune.py"),
    "hr-repo-dropped": (HR, " report --repo Bali-Zero/Teman2 --state-dir", " report --state-dir"),
    # the comparison must see a file the tick starts to extract, in any shape
    "tick-adds-a-literal-show": (TICK, 'HB_NEW="$(mktemp', 'git -C "$STATE/repo.git" show "$SHA:scripts/localci/newdep.py" > "$CODE/newdep.py"\nHB_NEW="$(mktemp'),
    "tick-adds-an-indented-loop": (TICK, 'HB_NEW="$(mktemp', 'if true; then\n  for f in newdep.py; do\n    git -C "$STATE/repo.git" show '
                                         '"$SHA:scripts/localci/$f" > "$CODE/$f"\n  done\nfi\nHB_NEW="$(mktemp'),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mutation sweep for the phase E flip against its tests.")
    ap.add_argument("--only", nargs="+", metavar="NAME", help="run only these mutants")
    ap.add_argument("--list", action="store_true", help="print the table and exit")
    a = ap.parse_args(argv)
    table = {**{n: (PEF, *r) for n, r in MUTANTS.items()}, **HAND_MUTANTS}
    names = a.only or list(table)
    if unknown := [n for n in names if n not in table]:
        print(f"unknown mutant(s): {unknown}", file=sys.stderr)
        return 2
    if a.list:
        print("\n".join(names))
        return 0
    with tempfile.TemporaryDirectory(prefix="phase-e-mutants-") as tmp:
        tree = Path(tmp)
        copy_tree(tree)
        (tree / PLIST).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / PLIST, tree / PLIST)
        originals = {f: (tree / f).read_text() for f in (PEF, HR, TICK)}
        if (rc := run_tests(tree, T + TH)) != 0:
            print(f"baseline: the unmutated copy gives pytest exit {rc} — nothing to measure", file=sys.stderr)
            return 2
        survived, stale, errors = [], [], []
        for n in names:
            f, old, new = table[n]
            original = originals[f]
            if original.count(old) != 1 or old == new:
                stale.append(n)
                print(f"{n:42} STALE (the rule's text occurs {original.count(old)} times)", flush=True)
                continue
            (tree / f).write_text(original.replace(old, new))
            v = verdict(run_tests(tree, T if f == PEF else TH))
            (tree / f).write_text(original)
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
