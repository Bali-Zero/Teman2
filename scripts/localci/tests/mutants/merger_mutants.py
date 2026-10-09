"""Replayable mutation sweep for the merger (merger.py, localci_merger_tick.sh) against its two test files, and for the B3
honesty rules (coverage, disk-full, the free-space floor) in hosted_compare.py and runner.py against theirs.

Every mutant is ONE textual rule applied to a temporary copy of scripts/localci and scripts/lib — the checkout is never
touched, so a killed sweep leaves nothing behind. A mutant is KILLED only when pytest ran its tests and one failed (exit 1);
exit 0 is SURVIVED, and any other exit (nothing collected, a collection or usage error) is ERROR, never a kill. pytest runs
without inherited PYTEST_* options, so a caller's -k or plugin cannot deselect the guilt. A rule whose text no longer
occurs exactly once is STALE (the code moved and the table must follow it), never skipped. Exit 0 only when every test
file set passes unmutated and every mutant is killed; 1 on a survivor, an error or a stale rule; 2 when a baseline fails.

    python3 scripts/localci/tests/mutants/merger_mutants.py [--only NAME ...] [--list]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# B4: the backend shards' worker cap (contexts_matrix.yaml) and the dead-worker timeout reason (runner.py), against their tests
MATRIX, RUN_PY = "scripts/localci/contexts_matrix.yaml", "scripts/localci/runner.py"
SW = "scripts/localci/tests/test_shard_workers.py"
SW_CAP = (f"{SW}::test_the_cap_is_declared_once_on_the_backend_shard_job_and_nowhere_else_in_the_matrix",)
SW_DEAD = tuple(f"{SW}::{t}" for t in ("test_a_timeout_after_a_dead_xdist_worker_names_the_worker_and_its_log_line_and_is_no_verdict",
                                      "test_every_xdist_wording_of_a_dead_worker_is_named_from_its_first_line",
                                      "test_a_timeout_without_a_dead_worker_keeps_the_old_reason",
                                      "test_a_dead_worker_in_a_run_that_finished_changes_nothing"))

# B6: the merger's own retention (prune.py) and the tick's host floor, against their tests
PRUNE, PRUNE_T = "scripts/localci/prune.py", "scripts/localci/tests/test_prune.py"
MERGER_T = "scripts/localci/tests/test_merger.py"
B6_WRAP = tuple(f"{MERGER_T}::{t}" for t in ("test_the_tick_decides_first_then_prunes_with_fstrim_and_passes_the_host_reading",
                                             "test_under_the_floor_the_tick_journals_its_skip_the_prune_still_runs_and_the_organ_says_warning",
                                             "test_a_failed_prune_is_a_warning_and_a_failed_tick_is_an_error_after_which_the_prune_still_runs"))
B6_FLOOR = (f"{MERGER_T}::test_the_tick_refuses_to_start_a_run_under_the_floor_and_journals_why",)
FLOOR_SH, FLOOR_T = "scripts/ops/pro_disk_floor_tick.sh", "scripts/localci/tests/test_disk_floor.py"

STALE = "scripts/localci/tests/test_hosted_stale.py"
REPLAY = "scripts/localci/tests/test_replay.py"
ROOT = Path(__file__).resolve().parents[4]
REPORT = "scripts/localci/tests/test_merger_report.py"
TICK = "scripts/localci/tests/test_merger.py"
PY, SH = "scripts/localci/merger.py", "scripts/localci/localci_merger_tick.sh"
HC, RUNNER = "scripts/localci/hosted_compare.py", "scripts/localci/runner.py"
HCT, RUNT = "scripts/localci/tests/test_hosted_compare.py", "scripts/localci/tests/test_runner.py"
HD = "scripts/localci/tests/test_host_disk.py"
RUNT_COV = tuple(f"{RUNT}::{t}" for t in ("test_the_matrix_coverage_is_full_by_default_partial_where_declared_and_never_full_when_unreadable",
                                         "test_every_context_result_in_the_status_carries_the_base_matrix_coverage",
                                         "test_the_real_matrix_declares_e2e_partial_with_its_reason"))
# B5: a red read with a rewritten BASE judge, a skip compared as a skip, and the report's count of skip agreements
JR, SKC = "scripts/localci/tests/test_judge_rewritten.py", "scripts/localci/tests/test_skip_compare.py"
REPORT_SKIP = tuple(f"{REPORT}::{t}" for t in (
    "test_eleven_full_of_which_three_are_skip_agreements_and_one_partial_still_count_and_the_lines_say_three",
    "test_a_skip_here_beside_a_hosted_run_is_partial_so_it_cannot_make_up_the_full_count"))
TICK_SKIP = (f"{TICK}::test_a_tick_journals_a_change_map_skip_beside_its_verdict_and_only_there",)

# name: (file, text that must occur once, replacement, test files that must turn red)
MUTANTS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # which hosted verdict judges a decision, and when a merge counts for phase E
    "parents-membership": (PY, 'return mc if parents[mc] == [d.get("base_sha")] else', 'return mc if d.get("base_sha") in parents[mc] else', (REPORT,)),
    "merged-here-any-base": (PY, 'merged_here = sha != head and sha == prs[n].get("merge_commit_sha")',
                             'merged_here = prs[n].get("merged") is True and head_of(prs[n]) == head', (REPORT,)),
    # the ruled threshold (2026-10-08): >= 12 compared, >= 11 full, at most 1 partial. MIN_COMPARED_FULL 11 -> 10 is an EQUIVALENT
    # mutant (12 compared with at most 1 partial already means >= 11 full), so it is not in the table; 11 -> 12 is.
    "min-contexts-minus-one": (PY, "MIN_COMPARED_CONTEXTS = 12\n", "MIN_COMPARED_CONTEXTS = 11\n", (REPORT,)),
    "min-contexts-ignored": (PY, "return full + partial >= MIN_COMPARED_CONTEXTS and full", "return full", (REPORT,)),
    "min-full-plus-one": (PY, "MIN_COMPARED_FULL = 11 ", "MIN_COMPARED_FULL = 12 ", (REPORT,)),
    "max-partial-zero": (PY, "MAX_COMPARED_PARTIAL = 1\n", "MAX_COMPARED_PARTIAL = 0\n", (REPORT,)),
    "max-partial-two": (PY, "MAX_COMPARED_PARTIAL = 1\n", "MAX_COMPARED_PARTIAL = 2\n", (REPORT,)),
    "compared-enough-ignores-partial": (PY, 'compared_enough(compared_ctx, len(not_full["partial"]))', "compared_enough(compared_ctx, 0)", (REPORT,)),
    "with-partial-uncounted": (PY, 'with_partial = {r["pr"] for r in rows if r["compared_merge"] and r["compared_partial"]}', "with_partial = set()",
                               (REPORT,)),
    "compared-merge-hosted-pending": (PY, 'merged_here and github != "PENDING" and d.get("contexts_status")', 'merged_here and d.get("contexts_status")', (REPORT,)),
    "merges-not-deduped": (PY, 'merges = sorted({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())',
                           'merges = sorted(r["merged_at"] for r in rows if r["compared_merge"])', (REPORT,)),
    "merges-unsorted": (PY, 'merges = sorted({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())',
                        'merges = list({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())', (REPORT,)),
    "merged-at-unrequired": (PY, "            if merged_here and not is_ts(merged_at):", "            if False:", (REPORT,)),
    "merged-pending-is-green": (PY, "            github = github_side(live)", "            github = github_side(live)\n            github = \"GREEN\" if merged_here and github == \"PENDING\" else github", (REPORT,)),
    "merged-red-is-green": (PY, "            github = github_side(live)", "            github = \"GREEN\" if merged_here else github_side(live)", (REPORT,)),
    "hosted-red-merged-never": (PY, "            if red:\n                hosted_red_merged.append(", "            if False:\n                hosted_red_merged.append(", (REPORT,)),
    "hosted-red-merged-any-not-green": (PY, 'red = sorted(k for k, v in required_verdicts(lives[mc]).items() if v == "RED")',
                                        'red = sorted(k for k, v in required_verdicts(lives[mc]).items() if v != "GREEN")', (REPORT,)),
    "hosted-red-merged-compared-only": (PY, "        for n in sorted(k for k, v in prs.items() if v.get(\"merged\") is True):",
                                        "        for n in sorted(r[\"pr\"] for r in rows if r[\"compared_merge\"]):", (REPORT,)),
    "hosted-red-merged-no-sha-skipped": (PY, '                raise hc.CompareError(f"#{n} is merged but carries no merge commit sha")', "                continue", (REPORT,)),
    "hosted-red-merged-first-only": (PY, '                hosted_red_merged.append({"pr": n, "merge_commit_sha": mc, "red": red})',
                                     '                hosted_red_merged.append({"pr": n, "merge_commit_sha": mc, "red": red})\n                break', (REPORT,)),
    "hosted-red-merged-all-contexts": (PY, 'red = sorted(k for k, v in required_verdicts(lives[mc]).items() if v == "RED")',
                                       'red = sorted(required_verdicts(lives[mc])) if "RED" in required_verdicts(lives[mc]).values() else []', (REPORT,)),
    "github-side-green-dominant": (PY, '    return "RED" if "RED" in seen else "PENDING" if "PENDING" in seen else "GREEN"',
                                   '    return "GREEN" if "GREEN" in seen else "RED" if "RED" in seen else "PENDING"', (REPORT,)),
    "github-side-pending-over-red": (PY, '    return "RED" if "RED" in seen else "PENDING" if "PENDING" in seen else "GREEN"',
                                     '    return "PENDING" if "PENDING" in seen else "RED" if "RED" in seen else "GREEN"', (REPORT,)),
    "pr-number-always": (PY, 'if runner_takes(base_wt, "--pr-number"):', "if True:", (TICK,)),
    "pr-number-never": (PY, 'if runner_takes(base_wt, "--pr-number"):', "if False:", (TICK,)),
    "pr-number-substring": (PY, '        tree = ast.parse((base_wt / "scripts" / "localci" / "runner.py").read_text())',
                            '        return flag in (base_wt / "scripts" / "localci" / "runner.py").read_text()', (TICK,)),
    "pr-number-undecodable-crashes": (PY, "    except (OSError, SyntaxError, ValueError):\n        return False\n    return any(",
                                      "    except (OSError, SyntaxError):\n        return False\n    return any(", (TICK,)),
    "pr-number-any-call": (PY, 'isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"', "True", (TICK,)),
    # the false-green count and the READY line
    "recorded-or-zero": (PY, '    value = counts.get("FALSE_GREEN") if isinstance(counts, dict) else None',
                         '    value = (counts.get("FALSE_GREEN") or 0) if isinstance(counts, dict) else 0', (REPORT,)),
    "recorded-any-type": (PY, "    if type(value) is not int or value < 0:", "    if False:", (REPORT,)),
    "ready-either": (PY, "ready = fg == 0 and compared_merges >= 50 and compared_days >= 14",
                     "ready = fg == 0 and (compared_merges >= 50 or compared_days >= 14)", (REPORT,)),
    "ready-on-days-alone": (PY, "ready = fg == 0 and compared_merges >= 50 and compared_days >= 14",
                            "ready = fg == 0 and compared_merges >= 50 and days >= 14", (REPORT,)),
    "ready-ignores-ctx-fg": (PY, "ready = fg == 0 and", 'ready = (counts["FALSE_GREEN"] + recorded_fg) == 0 and', (REPORT,)),
    "ready-49": (PY, "compared_merges >= 50 and", "compared_merges >= 49 and", (REPORT,)),
    "ready-days-boundary": (PY, "compared_days >= 14   #", "compared_days >= 13.999   #", (REPORT,)),
    "days-float": (PY, "return (int(_epoch(last) - _epoch(first)) * 1000 // 86400) / 1000",
                   "return round((_epoch(last) - _epoch(first)) / 86400, 3)", (REPORT,)),
    # B4: two xdist workers on the backend shards and nowhere else; a timeout after a dead worker names it and stays no verdict
    "b4-cap-key-misspelt": (MATRIX, 'env: { PYTEST_XDIST_AUTO_NUM_WORKERS: "2" }', 'env: { PYTEST_XDIST_AUTO_NUM_WORKER: "2" }', SW_CAP),
    "b4-cap-value-4": (MATRIX, 'env: { PYTEST_XDIST_AUTO_NUM_WORKERS: "2" }', 'env: { PYTEST_XDIST_AUTO_NUM_WORKERS: "4" }', SW_CAP),
    "b4-cap-dropped": (MATRIX, '          env: { PYTEST_XDIST_AUTO_NUM_WORKERS: "2" }\n', "", SW_CAP),
    "b4-cap-leaks-to-static": (MATRIX, "        - job_id: backend-static\n",
                               '        - job_id: backend-static\n          env: { PYTEST_XDIST_AUTO_NUM_WORKERS: "2" }\n', SW_CAP),
    "b4-node-down-unmatched": (RUN_PY, "node down: Not properly terminated|", "node down: Not properly terminatedX|", SW_DEAD),
    "b4-crashed-unmatched": (RUN_PY, """|\\bworker '?gw\\d+'? crashed")""", '")', SW_DEAD),
    "b4-node-down-over-match": (RUN_PY, "\\[gw\\d+\\] node down: Not properly terminated|", "node down|", SW_DEAD),
    "b4-crashed-over-match": (RUN_PY, """\\bworker '?gw\\d+'? crashed")""", 'worker.*crashed")', SW_DEAD),
    "b4-line-zero-based": (RUN_PY, "for n, raw in enumerate(fh, 1):", "for n, raw in enumerate(fh):", SW_DEAD),
    "b4-last-not-first": (RUN_PY, "for n, raw in enumerate(fh, 1):", "for n, raw in reversed(list(enumerate(fh, 1))):", SW_DEAD),
    "b4-dead-worker-fail-rc": (RUN_PY, 'return None, (f"timeout after {timeout}s — an xdist', 'return 1, (f"timeout after {timeout}s — an xdist', SW_DEAD),
    "b4-dead-worker-a-verdict": (RUN_PY, "if (dead := xdist_dead_worker(log)):",
                                 "if (dead := xdist_dead_worker(log)):\n                    return 1, None\n                if dead:", SW_DEAD),
    "b4-marker-judges-a-finished-run": (RUN_PY, "timeout=timeout, env=denv).returncode",
                                        'timeout=timeout, env=denv).returncode\n                if xdist_dead_worker(log):\n'
                                        '                    return None, "an xdist worker died"', SW_DEAD),
    "b4-always-named": (RUN_PY, "if (dead := xdist_dead_worker(log)):",
                        'if (dead := xdist_dead_worker(log) or ("?", 0)):', SW_DEAD),
    # inputs the report must refuse
    "sha-match-not-full": (PY, "return isinstance(x, str) and _FULL_SHA.fullmatch(x) is not None",
                           "return isinstance(x, str) and _FULL_SHA.match(x) is not None", (REPORT, TICK)),
    "ts-match-not-full": (PY, "return isinstance(x, str) and _TS_RE.fullmatch(x) is not None",
                          "return isinstance(x, str) and _TS_RE.match(x) is not None", (REPORT,)),
    # silences, counts and provenance in the window
    "decision-gap-all-lines": (PY, 'decision_gap_h = _longest_gap_h(r["ts"] for r in rows)', 'decision_gap_h = _longest_gap_h(r["ts"] for r in window)', (REPORT,)),
    "last-line-age-dropped": (PY, '"last_line_age_h": last_line_age_h,', '"last_line_age_h": 0,', (REPORT,)),
    "last-line-age-unclamped": (PY, "round(max(0.0, clock - max(_epoch(r[\"ts\"]) for r in window)) / 3600, 2)",
                                "round((clock - max(_epoch(r[\"ts\"]) for r in window)) / 3600, 2)", (REPORT,)),
    "future-lines-uncounted": (PY, 'future_lines = sum(1 for r in window if _epoch(r["ts"]) > clock)', "future_lines = 0", (REPORT,)),
    "errors-uncounted": (PY, 'errors = sum(1 for r in window if r.get("kind") == "error")', "errors = 0", (REPORT,)),
    "skips-uncounted": (PY, 'Counter(str(r.get("why")) for r in window if r.get("kind") == "skipped")',
                        'Counter(str(r.get("why")) for r in window if False)', (REPORT,)),
    "rows-lose-code-sha": (PY, '"code_sha": d.get("code_sha"),', '"code_sha": None,', (REPORT,)),
    "no-code-sha-any-string": (PY, 'without_code_sha = sum(1 for r in rows if not is_sha(r["code_sha"]))',
                               'without_code_sha = sum(1 for r in rows if not r["code_sha"])', (REPORT,)),
    "check-max-last": (PY, "check_max_s[k] = max(check_max_s.get(k, 0), v)", "check_max_s[k] = v", (REPORT,)),
    "check-max-unsorted": (PY, "dict(sorted(check_max_s.items(), key=lambda kv: -kv[1]))", "dict(sorted(check_max_s.items()))", (REPORT,)),
    "is-num-any-number": (PY, "return type(x) in (int, float) and x >= 0", "return isinstance(x, (int, float))", (REPORT,)),
    "median-is-mean": (PY, '"median_s": round(median(t for t, _ in timed), 1) if timed else None',
                       '"median_s": round(sum(t for t, _ in timed) / len(timed), 1) if timed else None', (REPORT,)),
    "longest-is-first": (PY, '"longest_s": timed[-1][0] if timed else None', '"longest_s": timed[0][0] if timed else None', (REPORT,)),
    # B6-1: deps images by explicit tag, 48 h unreferenced, never the newest of a recipe, never the candidate or base images
    "b6-ref-window-shorter": (PRUNE, "REF_WINDOW_H = 48", "REF_WINDOW_H = 46", (PRUNE_T,)),
    "b6-ref-window-longer": (PRUNE, "REF_WINDOW_H = 48", "REF_WINDOW_H = 72", (PRUNE_T,)),
    "b6-newest-guard-off": (PRUNE, 'elif top is None or im["created"] is None or im["created"] == top["created"]:', 'elif top is None or im["created"] is None:', (PRUNE_T,)),
    "b6-never-list-off": (PRUNE, "    return tag.startswith(NEVER) or tag in stand_ins\n", "    return False\n", (PRUNE_T,)),
    # lead's addenda (2026-10-08): service stand-ins from the BASE matrix, a cap of 2 per recipe, a tick in flight, the run in progress
    "b6-stand-ins-ignored": (PRUNE, "    return tag.startswith(NEVER) or tag in stand_ins\n", "    return tag.startswith(NEVER)\n", (PRUNE_T,)),
    "b6-stand-ins-unread-removes": (PRUNE, "    for d in decided if blind else []:", "    for d in []:", (PRUNE_T,)),
    "b6-stand-in-rule-unnamed": (PRUNE, "    if tag in stand_ins:\n        return \"service stand-in", "    if False:\n        return \"service stand-in", (PRUNE_T,)),
    "b6-cap-3": (PRUNE, "MAX_IMAGES_PER_RECIPE = 2 ", "MAX_IMAGES_PER_RECIPE = 3 ", (PRUNE_T,)),
    "b6-run-in-progress-ignored": (PRUNE, "        elif im[\"tag\"] in in_progress or im[\"id\"] in in_progress:", "        elif False:", (PRUNE_T,)),
    "b6-cap-off": (PRUNE, 'if im["id"] not in slots and len(used) < MAX_IMAGES_PER_RECIPE:', 'if im["id"] not in slots:', (PRUNE_T,)),
    "b6-twin-tag-untagged": (PRUNE, 'if ref_of(im) is None and im["id"] in slots:', "if False:", (PRUNE_T,)),
    "b6-second-kept-unnamed": (PRUNE, '(True, f"not the newest of recipe', '(False, f"not the newest of recipe', (PRUNE_T,)),
    # B8 (Pro, 2026-10-08T15:27Z, the VM full): the lease not a clock, slot 2 by plans, a VM floor over slot 2, the cache by budget
    "b8-clock-grace-back": (PRUNE, '(True, f"recipe {r} already keeps', '(ref_of(im) >= 6, f"recipe {r} already keeps', (PRUNE_T,)),
    "b8-slot-1-not-reserved": (PRUNE, "used = {1} if top is not None else set()", "used = set()", (PRUNE_T,)),
    "b8-slot-2-by-age": (PRUNE, "key=lambda im: (-count_of(im), ref_of(im), -(im", "key=lambda im: (-(im", (PRUNE_T,)),
    "b8-slot-2-count-ignored": (PRUNE, "key=lambda im: (-count_of(im), ref_of(im),", "key=lambda im: (ref_of(im),", (PRUNE_T,)),
    "b8-slot-2-tie-oldest-ref": (PRUNE, "key=lambda im: (-count_of(im), ref_of(im),", "key=lambda im: (-count_of(im), -ref_of(im),", (PRUNE_T,)),
    "b8-count-max-not-union": (PRUNE, 'len(set(named.get(im["tag"], ())) | set(named.get(im["id"], ())))', 'max(len(named.get(im["tag"], ())), len(named.get(im["id"], ())))', (PRUNE_T,)),
    "b8-count-sum-not-union": (PRUNE, 'len(set(named.get(im["tag"], ())) | set(named.get(im["id"], ())))', 'len(named.get(im["tag"], ())) + len(named.get(im["id"], ()))', (PRUNE_T,)),
    "b8-floor-14": (PRUNE, "VM_MIN_FREE_GB = 15.0 ", "VM_MIN_FREE_GB = 14.0 ", (PRUNE_T,)),
    "b8-floor-16": (PRUNE, "VM_MIN_FREE_GB = 15.0 ", "VM_MIN_FREE_GB = 16.0 ", (PRUNE_T,)),
    "b8-floor-off": (PRUNE, 'if rec["vm_free_gb"]["after"] >= floor:\n                break', "if True:\n                break", (PRUNE_T,)),
    "b8-floor-at-the-floor": (PRUNE, 'if rec["vm_free_gb"]["after"] >= floor:\n                break', 'if rec["vm_free_gb"]["after"] > floor:\n                break', (PRUNE_T,)),
    "b8-floor-env-ignored": (PRUNE, 'floor = _env_gb("LOCALCI_VM_MIN_FREE_GB", VM_MIN_FREE_GB)', "floor = VM_MIN_FREE_GB", (PRUNE_T,)),
    "b8-floor-unmeasured-acts": (PRUNE, 'elif rec["vm_free_gb"]["after"] is None:', "elif False:", (PRUNE_T,)),
    "b8-floor-on-dry-run": (PRUNE, "    if dry or blind:\n", "    if blind:\n", (PRUNE_T,)),
    "b8-floor-blind": (PRUNE, "    if dry or blind:\n", "    if dry:\n", (PRUNE_T,)),
    "b8-floor-gated-on-errors": (PRUNE, "    if dry or blind:\n", "    if dry or errors:\n", (PRUNE_T,)),
    "b8-floor-no-remeasure": (PRUNE, '            rec["vm_free_gb"]["after"] = vm_free_gb(docker, state)\n            if rec', "            if rec", (PRUNE_T,)),
    # B8 amended (Pro, 17:26Z: a 60 GiB VM holds one image per recipe plus scratch): under the floor, fewest references first,
    # the newest of a recipe not protected; the cache pruned with -a after every image removal, its size journalled
    "b8-floor-by-age-only": (PRUNE, 'key=lambda d: (d["refs"], d["created"] is None,', 'key=lambda d: (d["created"] is None,', (PRUNE_T,)),
    "b8-floor-most-refs-first": (PRUNE, 'key=lambda d: (d["refs"], d["created"] is None,', 'key=lambda d: (-d["refs"], d["created"] is None,', (PRUNE_T,)),
    "b8-floor-newest-first": (PRUNE, 'd["created"] or 0, d["tag"])', '-(d["created"] or 0), d["tag"])', (PRUNE_T,)),
    "b8-floor-keeps-newest": (PRUNE, 'not d["remove"] and not d["live"] and not never(', 'not d["remove"] and d["slot"] != 1 and not d["live"] and not never(', (PRUNE_T,)),
    "b8-floor-takes-lease-run": (PRUNE, 'not d["remove"] and not d["live"] and not never(', 'not d["remove"] and not never(', (PRUNE_T,)),
    "b8-live-flag-off": (PRUNE, '"live": im["tag"] in in_progress or im["id"] in in_progress}', '"live": False}', (PRUNE_T,)),
    "b8-cache-by-age": (PRUNE, '"builder", "prune", "-af", "--keep-storage", f"{budget_gb:g}GB"', '"builder", "prune", "-f", "--filter", "until=24h"', (PRUNE_T,)),
    "b8-cache-without-a": (PRUNE, '"builder", "prune", "-af",', '"builder", "prune", "-f",', (PRUNE_T,)),
    "b8-cache-env-ignored": (PRUNE, 'cache_budget = _env_gb("LOCALCI_BUILDER_CACHE_GB", BUILDER_CACHE_GB)', "cache_budget = BUILDER_CACHE_GB", (PRUNE_T,)),
    "b8-cache-not-after-floor-removal": (PRUNE, "            builder_prune(docker, rec, cache_budget)   # the cache entries", "            pass   # the cache entries", (PRUNE_T,)),
    "b8-cache-size-after-unread": (PRUNE, 'rec["builder_prune"]["cache_gb"]["after"] = build_cache_gb(docker)', 'rec["builder_prune"]["cache_gb"]["after"] = None', (PRUNE_T,)),
    "b8-cache-first-rc-kept": (PRUNE, '    bp["rc"] = rc   # the last call', '    bp["rc"] = rc if bp["rc"] == 0 else bp["rc"]   # the last call', (PRUNE_T,)),
    "b8-floor-undated-first": (PRUNE, 'key=lambda d: (d["refs"], d["created"] is None, d["created"] or 0,', 'key=lambda d: (d["refs"], d["created"] or 0,', (PRUNE_T,)),
    "b8-cache-size-mb-as-gb": (PRUNE, '"MB": 1e6', '"MB": 1e9', (PRUNE_T,)),
    # B8a (Pro, 2026-10-09T02:49:24Z: "built -5.3 h ago"): Created is a UTC instant whatever its offset
    "b8a-offset-ignored": (PRUNE, '+ float(m.group(2) or 0) - off_s', '+ float(m.group(2) or 0)', (PRUNE_T,)),
    "b8a-offset-sign-flipped": (PRUNE, '(1 if m.group(3) == "+" else -1)', '(-1 if m.group(3) == "+" else 1)', (PRUNE_T,)),
    "b8a-offset-minutes-dropped": (PRUNE, "int(m.group(4)) * 3600 + int(m.group(5)) * 60", "int(m.group(4)) * 3600", (PRUNE_T,)),
    "b8a-bad-offset-accepted": (PRUNE, "if not m or (m.group(3) and (int(m.group(4)) > 23 or int(m.group(5)) > 59)):", "if not m:", (PRUNE_T,)),
    "b8a-trailing-text-accepted": (PRUNE, "m = TS_RE.fullmatch((text or \"\").strip())", "m = TS_RE.match((text or \"\").strip())", (PRUNE_T,)),
    "b8-cache-budget-8": (PRUNE, "BUILDER_CACHE_GB = 4 ", "BUILDER_CACHE_GB = 8 ", (PRUNE_T,)),
    "b8-env-inf-accepted": (PRUNE, "return v if math.isfinite(v) and v >= 0 else default", "return v if v >= 0 else default", (PRUNE_T,)),
    "b6-rm-forced": (PRUNE, 'None if dry else _docker(docker, "image", "rm", im["tag"])', 'None if dry else _docker(docker, "image", "rm", "-f", im["tag"])', (PRUNE_T,)),
    "b8-floor-rm-forced": (PRUNE, 'r = _docker(docker, "image", "rm", im["tag"])', 'r = _docker(docker, "image", "rm", "-f", im["tag"])', (PRUNE_T,)),
    "b6-builder-never": (PRUNE, "    if not dry:   # the build cache grows", "    if False:   # the build cache grows", (PRUNE_T,)),
    "b6-dry-run-removes": (PRUNE, "r = None if dry else _docker(", "r = None if False else _docker(", (PRUNE_T,)),
    # B6-2: 7 days full, then the bulk goes; 30 days, then only the verdict files
    "b6-full-days-6": (PRUNE, "FULL_DAYS, VERDICT_DAYS = 7, 30", "FULL_DAYS, VERDICT_DAYS = 6, 30", (PRUNE_T,)),
    "b6-full-days-8": (PRUNE, "FULL_DAYS, VERDICT_DAYS = 7, 30", "FULL_DAYS, VERDICT_DAYS = 8, 30", (PRUNE_T,)),
    "b6-verdict-days-29": (PRUNE, "FULL_DAYS, VERDICT_DAYS = 7, 30", "FULL_DAYS, VERDICT_DAYS = 7, 29", (PRUNE_T,)),
    "b6-verdict-days-31": (PRUNE, "FULL_DAYS, VERDICT_DAYS = 7, 30", "FULL_DAYS, VERDICT_DAYS = 7, 31", (PRUNE_T,)),
    "b6-verdict-files-lost": (PRUNE, "rel not in VERDICT", "True", (PRUNE_T,)),
    "b6-call-graphs-kept": (PRUNE, "f in BULK)", "False)", (PRUNE_T,)),
    "b6-undated-run-trimmed": (PRUNE, "if age_h is None or age_h < FULL_DAYS * 24:", "if age_h is not None and age_h < FULL_DAYS * 24:", (PRUNE_T,)),
    # B6-3: the tick decides, then prunes and trims the VM; under 60 GB host-free no run starts
    "b6-wrapper-floor-59": (SH, 'FLOOR_GB="${MERGER_MIN_HOST_FREE_GB:-60}"', 'FLOOR_GB="${MERGER_MIN_HOST_FREE_GB:-59}"', B6_WRAP),
    "b6-wrapper-floor-le": (SH, '[ "$FREE" -lt "$FLOOR_GB" ]', '[ "$FREE" -le "$FLOOR_GB" ]', B6_WRAP),
    "b6-wrapper-no-fstrim": (SH, 'prune --state-dir "$STATE" --fstrim', 'prune --state-dir "$STATE"', B6_WRAP),
    "b6-wrapper-prune-failure-silent": (SH, 'if [ "$PRUNE_RC" -ne 0 ]; then', "if false; then", B6_WRAP),
    "b6-wrapper-never-prunes": (SH, """if [ -f "$CODE/prune.py" ] && grep -q -- '"prune"' "$CODE/merger.py"; then""", "if false; then", B6_WRAP),
    "b6-merger-floor-off": (PY, "if a.host_free_gb is not None and a.host_free_gb < a.min_host_free_gb:", "if False:", B6_FLOOR),
    "b6-merger-floor-59": (PY, "type=float, default=60.0,", "type=float, default=59.0,", B6_FLOOR),
    "b7-fstrim-only-after-removal": (PRUNE, "    if fstrim and not dry:   # every real prune", "    if fstrim and removed and not dry:   # every real prune", (PRUNE_T,)),
    "b7-fstrim-on-dry-run": (PRUNE, "    if fstrim and not dry:   # every real prune", "    if fstrim:   # every real prune", (PRUNE_T,)),
    "b6-prune-code-sha-dropped": (PY, "    CODE_SHA = a.code_sha or None\n", "    CODE_SHA = None\n", (PRUNE_T,)),
    # council round 1 (2026-10-08): the confirmed findings, each with its guard
    "b6-unreadable-plan-ignored": (PRUNE, "            unreadable.append(", "            0 and unreadable.append(", (PRUNE_T,)),
    "b6-half-plan-unread": (PRUNE, "        except ValueError:\n            doc = None\n", "        except ValueError:\n            continue\n", (PRUNE_T,)),
    "b6-runs-link-followed": (PRUNE, "    if runs.is_symlink():   # the prune never leaves", "    if False:   # the prune never leaves", (PRUNE_T,)),
    "b6-nanoseconds-dropped": (PRUNE, "+ float(m.group(2) or 0) - off_s", "- off_s", (PRUNE_T,)),
    "b6-prune-failure-ok": (PY, 'return 1 if rec["failed"] else 0', 'return 1 if rec["images"]["errors"] else 0', (PRUNE_T,)),
    "b6-prune-beside-tick": (PY, "    if fh is None:\n        journal(state, {\"kind\": \"prune\"", "    if False:\n        journal(state, {\"kind\": \"prune\"", (PRUNE_T,)),
    "b6-wrapper-df-unread-ticks": (SH, 'if [ -z "$FREE" ]; then WARN="host free space unreadable', 'if false; then WARN="host free space unreadable', (f"{MERGER_T}::test_an_unreadable_host_reading_starts_no_run_and_the_organ_says_warning",)),
    "b6-floor-organ-alive-ok": (FLOOR_SH, 'heartbeat "warning" "skipped: previous run alive', 'heartbeat "ok" "skipped: previous run alive', (FLOOR_T,)),
    "b6-prune-code-sha-unvalidated": (PY, "if a.code_sha and not is_sha(a.code_sha):", "if False:", (PRUNE_T,)),
    # B6-4: pro.disk_floor — ok above 100 GB, warning 60-100, failed under 60
    "b6-floor-organ-ok-at-100": (FLOOR_SH, 'if [ "$FREE_MB" -gt "$OK_ABOVE_MB" ]; then VERDICT="ok"', 'if [ "$FREE_MB" -ge "$OK_ABOVE_MB" ]; then VERDICT="ok"', (FLOOR_T,)),
    "b6-floor-organ-ok-above-101": (FLOOR_SH, "OK_ABOVE_MB=100000 ", "OK_ABOVE_MB=101000 ", (FLOOR_T,)),
    "b6-floor-organ-fail-under-59": (FLOOR_SH, "FAIL_UNDER_MB=60000 ", "FAIL_UNDER_MB=59000 ", (FLOOR_T,)),
    "b6-floor-organ-fail-under-61": (FLOOR_SH, "FAIL_UNDER_MB=60000 ", "FAIL_UNDER_MB=61000 ", (FLOOR_T,)),
    "b6-floor-organ-failed-as-warning": (FLOOR_SH, '*) heartbeat "error" "failed: $NOTE"', '*) heartbeat "warning" "failed: $NOTE"', (FLOOR_T,)),
    # the tick's journal
    "durations-not-journalled": (PY, '                               "durations": {k: (v or {}).get("duration_s") for k, v in (status.get("checks") or {}).items()},\n',
                                 "", (TICK,)),
    "code-sha-not-stamped": (PY, '**({"code_sha": CODE_SHA} if CODE_SHA else {}), ', "", (TICK,)),
    "code-sha-unvalidated": (PY, "if a.code_sha is not None and not is_sha(a.code_sha):", "if False:", (TICK,)),
    "code-sha-sticky": (PY, "    CODE_SHA = a.code_sha\n", "    CODE_SHA = a.code_sha or CODE_SHA\n", (TICK,)),
    # the enqueue path (C3a-2): each sub-criterion, the two halves of the arm, the one mutation
    "enqueue-env-any-value": (PY, "armed_env = os.environ.get(ARM_ENV) == \"1\"", "armed_env = bool(os.environ.get(ARM_ENV))", (TICK,)),
    "enqueue-label-not-an-arm": (PY, 'if not (armed_env and criterion["label_privileged"]) else', "if not armed_env else", (TICK,)),
    "enqueue-label-any-role": (PY, "(None if role in ARM_ROLES else", "(None if role else", (TICK,)),
    "enqueue-label-first-actor": (PY, 'actor = ev.get("actor") if ev.get("__typename") == "LabeledEvent" else None', 'actor = actor or ev.get("actor")', (TICK,)),
    "enqueue-blocked-executed-ok": (PY, 'if res.get("mapping") in NON_EXECUTED and res.get("verdict") == "BLOCKED":', 'if res.get("verdict") == "BLOCKED":', (TICK,)),
    "enqueue-check-blocked-only-fail": (PY, 'v not in CHECK_OK}', 'v == "FAIL"}', (TICK,)),
    "enqueue-review-any": (PY, 'None if review in ("QUEUED", "PASS") else', 'None if review != "FAIL" else', (TICK,)),
    "enqueue-hosted-pending-ok": (PY, 'if v != "GREEN"}', 'if v == "RED"}', (TICK,)),
    "enqueue-head-moved-ignored": (PY, "None if live_head == head else", "None if live_head else", (TICK,)),
    "enqueue-queue-entry-ignored": (PY, 'p.get("isInMergeQueue") is False and entry is None', 'p.get("isInMergeQueue") is False', (TICK,)),
    "enqueue-twice": (PY, '"this head was enqueued by an earlier tick" if again else None', "None", (TICK,)),
    "enqueue-no-entry-is-success": (PY, 'if not isinstance(entry, dict) or not entry.get("id"):', "if False:", (TICK,)),
    "enqueue-unread-is-true": (PY, 'criterion = {k: k in why and why[k] is None for k in CRITERION}', 'criterion = {k: why.get(k) is None for k in CRITERION}', (TICK,)),
    "report-would-enqueue-any": (PY, 'r.get("kind") == "would_enqueue" and r.get("ok") is True', 'r.get("kind") == "would_enqueue"', (REPORT,)),
    # F1 (phase F, shadow): the rehearsed merge — one would_merge line, never a ref, never a push
    "f1-kind-string": (PY, '{"kind": "would_merge", "pr": enq["pr"]', '{"kind": "would_merged", "pr": enq["pr"]', (TICK,)),
    "f1-step-not-called": (PY, "            merge_shadow_step(state, repo_dir, enq, a.base)\n", "            pass\n", (TICK,)),
    "f1-ok-ignores-criterion": (PY, "bool(crit) and all(crit.values()) and", "bool(crit) and True and", (TICK,)),
    "f1-ok-empty-criterion": (PY, "bool(crit) and all(crit.values()) and", "all(crit.values()) and", (TICK,)),
    "f1-ok-ignores-base-moved": (PY, 'and line["base_current"] and line["clean"]', 'and line["clean"]', (TICK,)),
    "f1-ok-ignores-conflict": (PY, 'and line["base_current"] and line["clean"]', 'and line["base_current"]', (TICK,)),
    "f1-base-current-always": (PY, 'line["base_current"] = line["remote_main"] == base_sha', 'line["base_current"] = True', (TICK,)),
    "f1-base-current-vs-mirror": (PY, 'line["base_current"] = line["remote_main"] == base_sha', 'line["base_current"] = line["mirror_main"] == base_sha', (TICK,)),
    "f1-remote-read-without-timeout": (PY, "check=False, timeout=REMOTE_TIMEOUT_S)", "check=False)", (TICK,)),
    "f1-remote-error-is-current": (PY, "        errors.append(redact(f\"{type(exc).__name__}: {exc}\"))\n    try:\n        line[\"mirror_main\"]",
                                   "        line[\"base_current\"] = True\n    try:\n        line[\"mirror_main\"]", (TICK,)),
    "f1-journal-failure-reaches-decide": (PY, "        except Exception as exc:  # noqa: BLE001 — a shadow never turns a decision", "        except ZeroDivisionError as exc:  # noqa: BLE001", (TICK,)),
    "f1-report-error-is-conflict": (PY, 'r.get("clean") is False and is_sha(r.get("merge_tree")) and not r.get("error")', 'r.get("clean") is False', (REPORT,)),
    "f1-report-error-is-base-moved": (PY, 'r.get("base_current") is False and is_sha(r.get("remote_main"))', 'r.get("base_current") is False', (REPORT,)),
    "f1-report-errors-uncounted": (PY, '"errors": sum(1 for r in wm if r.get("error"))', '"errors": 0', (REPORT,)),
    "f1-head-unchanged-always": (PY, '"head_unchanged": crit.get("head_unchanged") is True', '"head_unchanged": True', (TICK,)),
    "f1-rehearses-on-decided-base": (PY, 'line["mirror_main"], head, check=False)', 'base_sha, head, check=False)', (TICK,)),
    "f1-clean-always": (PY, 'line["clean"] = parts[0], res.returncode == 0', 'line["clean"] = parts[0], True', (TICK,)),
    "f1-conflicts-unread": (PY, 'line["conflicts"] = (names[:names.index("")] if "" in names else names)[:50]', 'line["conflicts"] = []', (TICK,)),
    "f1-conflicts-take-messages": (PY, 'names[:names.index("")] if "" in names else names', "names", (TICK,)),
    "f1-writes-a-ref": (PY, 'line["merge_tree"], line["clean"] = parts[0], res.returncode == 0',
                        'line["merge_tree"], line["clean"] = parts[0], res.returncode == 0; git(repo_dir, "update-ref", "refs/merger/shadow", parts[0])', (TICK,)),
    "f1-error-unredacted": (PY, "a shadow never raises into the decision\n        errors.append(redact(f\"{type(exc).__name__}: {exc}\"))",
                            "a shadow never raises into the decision\n        errors.append(f\"{type(exc).__name__}: {exc}\")", (TICK,)),
    "f1-remote-error-unredacted": (PY, "not known to be current\n        errors.append(redact(f\"{type(exc).__name__}: {exc}\"))",
                                   "not known to be current\n        errors.append(f\"{type(exc).__name__}: {exc}\")", (TICK,)),
    "f1-raises-into-decision": (PY, "    except Exception as exc:  # noqa: BLE001 — a shadow never raises into the decision",
                                "    except ZeroDivisionError as exc:  # noqa: BLE001", (TICK,)),
    "f1-bites-always": (PY, '"bites": isinstance(p.get("body"), str) and BITES_RE.search(p["body"]) is not None', '"bites": True', (TICK,)),
    "f1-bites-case-sensitive": (PY, "re.M | re.I)   # the PR contract", "re.M)   # the PR contract", (TICK,)),
    "f1-bites-anywhere": (PY, 'BITES_RE = re.compile(r"^[ \\t>*_-]*Bites', 'BITES_RE = re.compile(r".*Bites', (TICK,)),
    "f1-report-counts-other-kinds": (PY, 'wm = [r for r in window if r.get("kind") == "would_merge"]', 'wm = [r for r in window if r.get("kind") in ("would_merge", "would_enqueue")]', (REPORT,)),
    "f1-report-ok-any": (PY, '"ok": sum(1 for r in wm if r.get("ok") is True)', '"ok": len(wm)', (REPORT,)),
    "f1-report-conflicted-inverted": (PY, 'sum(1 for r in wm if r.get("clean") is False and', 'sum(1 for r in wm if r.get("clean") is True and', (REPORT,)),
    "f1-report-base-moved-inverted": (PY, 'sum(1 for r in wm if r.get("base_current") is False and', 'sum(1 for r in wm if r.get("base_current") is True and', (REPORT,)),
    "f1-report-phase-f-live": (PY, '"phase_f": "shadow"', '"phase_f": "live"', (REPORT,)),
    # B10 (phase D): a hosted verdict given on an older main than the local run judged is HOSTED_STALE, only on evidence
    "b10-stale-without-path-test": (PY, 'return {"stale": bool(selected), "hosted_main": main,', 'return {"stale": bool(paths), "hosted_main": main,', (STALE,)),
    "b10-stale-any-flag": (PY, 'if cm.get("run_all") or flag in (cm.get("suggested_jobs") or []):', "if True:", (STALE,)),
    "b10-stale-before-flag-read": (PY, "        if not isinstance(self._flags[name], str):\n            raise", "        if False:\n            raise", (STALE,)),
    "b10-stale-main-after": (PY, 'f"--before={completed_at}"', 'f"--after={completed_at}"', (STALE,)),
    "b10-stale-on-unreadable-time": (HC, 'return {**base, "stale": None, "stale_check": "unknown (the hosted verdict carries no readable completed_at)"}',
                                     'return {**base, "stale": True, "stale_check": "unknown (the hosted verdict carries no readable completed_at)"}', (STALE,)),
    "b10-stale-on-judge-failure": (HC, 'return {**base, "stale": None, "stale_check": f"unknown ({type(exc).__name__}',
                                   'return {**base, "stale": True, "stale_check": f"unknown ({type(exc).__name__}', (STALE,)),
    "b10-agree-left-as-agree": (HC, 'if reading.get("stale") is True:\n            reading["class_before"]', 'if reading.get("stale") is True and klass != "AGREE":\n            reading["class_before"]', (STALE,)),
    "b10-stale-counts-as-compared": (HC, 'COMPARED = ("AGREE", "FALSE_GREEN", "FALSE_RED")', 'COMPARED = ("AGREE", "FALSE_GREEN", "FALSE_RED", "HOSTED_STALE")', (STALE,)),
    "b10-oldest-entry-times-the-verdict": (HC, "when = max(stamps) if", "when = min(stamps) if", (STALE,)),
    "b10-judge-unwired-in-the-tick": (PY, "run_dir, StaleJudge(repo_dir, base_sha))", "run_dir, None)", (TICK,)),
    "b10-tick-drops-the-stale-rows": (PY, '**({"stale": stale} if stale else {})', "**{}", (STALE,)),
    "b10-report-compare-without-judge": (PY, 'rep = hc.compare(status, live["required_checks"], live["check_runs"], live["statuses"], stale_judge=judge)\n                for k, v',
                                         'rep = hc.compare(status, live["required_checks"], live["check_runs"], live["statuses"])\n                for k, v', (REPORT,)),
    "b10-report-reclassifies-without-evidence": (PY, 'if reading["stale"] is True:\n            out.append', 'if True:\n            out.append', (REPORT,)),
    "b10-report-reclassifies-a-red-that-went": (PY, 'if h["verdict"] != "RED":\n            kept.append(', "if False:\n            kept.append(", (REPORT,)),
    "b10-report-never-subtracts": (PY, "recorded_fg += raw - len(got)", "recorded_fg += raw", (REPORT,)),
    "b10-report-hides-the-raw-count": (PY, "recorded_raw += raw\n", "recorded_raw += raw - len(got)\n", (REPORT,)),
    "b10-first-parent-dropped": (PY, '"rev-list", "-1", "--first-parent", f"--before=', '"rev-list", "-1", f"--before=', (STALE,)),
    "b10-per-path-classify-blind": (PY, "cm = change_map.classify([p])", "cm = change_map.classify([])", (STALE,)),
    "b10-report-kept-unsaid": (PY, '"why": reading["stale_check"]})', '"why": ""})', (REPORT,)),
    "b10-report-read-failure-unsaid": (PY, '"why": redact(f"unknown ({type(exc).__name__}: {exc})")}]', '"why": ""}]', (REPORT,)),
    "b10-report-red-gone-unsaid": (PY, "the hosted verdict is now {h['verdict']}, not the red the tick recorded", "kept", (REPORT,)),
    # B11 (phase D): the merger also judges the exact commit GitHub merged — a replay, BASE = its first parent, alternating with PR decisions
    "b11-base-is-the-merge-commit": (PY, '"base_sha": parents.split()[0]', '"base_sha": sha', (REPLAY,)),
    "b11-alternation-off": (PY, 'after_replay = bool(last and last[0].get("replay"))', "after_replay = False", (REPLAY,)),
    "b11-open-pull-journalled-unmapped": (PY, 'if isinstance(p, dict) and p.get("state") == "open":\n                    continue', 'if False:\n                    continue', (REPLAY,)),
    "b11-oldest-merge-first": (PY, "for line in log:   # newest first (B11b)", "for line in reversed(log):   # (B11b)", (REPLAY,)),
    "b11-replayed-again": (PY, "if sha in done or not m or not parents.split():", "if not m or not parents.split():", (REPLAY,)),
    "b11-unconfirmed-commit-replayed": (PY, 'p.get("merged") is True and p.get("merge_commit_sha") == sha and head_of(p)', 'p.get("merged") is True and head_of(p)', (REPLAY,)),
    "b11-stale-judge-on-a-replay": (PY, "hosted_summary(a.repo, a.base, status, cand_sha, run_dir, None, REPLAY_NOTE)",
                                    "hosted_summary(a.repo, a.base, status, cand_sha, run_dir, StaleJudge(repo_dir, base_sha), REPLAY_NOTE)", (REPLAY,)),
    "b11-replay-enqueues": (PY, "        if replay:\n            return 0\n        enq = ", "        if False:\n            return 0\n        enq = ", (REPLAY,)),
    "b11-replay-counted-without-threshold": (PY, 'and compared_enough(compared_ctx, len(not_full["partial"]))})', 'and (d.get("replay") is True or compared_enough(compared_ctx, len(not_full["partial"]))) })', (REPORT,)),
    "b11-pr-counted-twice": (PY, 'merges = sorted({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())', 'merges = sorted(r["merged_at"] for r in rows if r["compared_merge"])', (REPORT,)),
    "b11-unconfirmed-merge-commit-trusted": (PY, 'return mc if pr.get("merged") is True and is_sha(mc) and pr.get("merge_commit_sha") == mc else', "return mc if True else", (REPORT,)),
    "b11-replay-judged-for-stale": (PY, 'judge = None if d.get("replay") else judges.setdefault', "judge = judges.setdefault", (REPORT,)),
    "b11-replay-credit-to-any": (PY, "if all(flags))   # a PR that also qualified", "if any(flags))   # a PR that also qualified", (REPORT,)),
    "b11-second-parent-base": (PY, '"base_sha": parents.split()[0]', '"base_sha": parents.split()[-1]', (REPLAY,)),
    "b11-not-first-parent-line": (PY, '"log", "--first-parent", "--format=%H%x00%P%x00%s"', '"log", "--format=%H%x00%P%x00%s"', (REPLAY,)),
    "b11-replay-crash-unjournalled": (PY, "if not (replay or isinstance(exc, (MergerError, OSError))):", "if not isinstance(exc, (MergerError, OSError)):", (REPLAY,)),
    "b11-any-crash-journalled": (PY, "if not (replay or isinstance(exc, (MergerError, OSError))):", "if False:", (REPLAY,)),
    "b11-replay-stop-journalled": (PY, "    except Stopped:\n        raise\n    except Exception as exc:  # noqa: BLE001 — a decision with no verdict",
                                   "    except Exception as exc:  # noqa: BLE001 — a decision with no verdict", (REPLAY,)),
    "b11-replay-false-green-unlisted": (PY, '"why": REPLAY_KEPT}]', '"why": REPLAY_KEPT}][:0]', (REPORT,)),
    # the launchd wrapper
    "sh-code-flag-always": (SH, 'if grep -q -- "--code-sha" "$CODE/merger.py"; then', "if true; then", (TICK,)),
    "sh-code-flag-never": (SH, 'if grep -q -- "--code-sha" "$CODE/merger.py"; then', "if false; then", (TICK,)),
    "sh-heartbeat-sourced": (SH, '"$BASH" "$HB_LIB" "$ORGAN_ID" "$1" "$2" ||', '{ source "$HB_LIB"; organism_heartbeat "$ORGAN_ID" "$1" "$2"; } ||', (TICK,)),
    "sh-heartbeat-from-checkout": (SH, 'HB_LIB="${MERGER_HEARTBEAT_LIB:-$STATE/heartbeat.sh}"',
                                   'HB_LIB="${MERGER_HEARTBEAT_LIB:-$HOME/nuzantara/scripts/lib/heartbeat.sh}"', (TICK,)),
    "sh-heartbeat-not-refreshed": (SH, '  mv -f "$HB_NEW" "$STATE/heartbeat.sh"', "  :", (TICK,)),
    "sh-heartbeat-empty-runs": (SH, 'if [ -r "$HB_LIB" ] && [ -s "$HB_LIB" ]; then', 'if [ -r "$HB_LIB" ]; then', (TICK,)),
    "sh-python-x-unchecked": (SH, 'if [ ! -x "$PY" ]; then', "if false; then", (TICK,)),
    "sh-required-check-gone": (SH, 'if [ -z "$PY" ] || [ -z "$NODE" ]; then', "if false; then", (TICK,)),
    "sh-required-via-expansion": (SH, 'PY="${MERGER_PYTHON:-}"    # the interpreter that runs the BASE runner', 'PY="${MERGER_PYTHON:?required}"', (TICK,)),
    "sh-kill-switch-ignored": (SH, 'if [ "${LOCALCI_MERGER_ENABLED:-true}" = "false" ]; then', "if false; then", (TICK,)),
    "sh-heartbeat-always-ok": (SH, 'if [ "$rc" -ne 0 ]; then heartbeat error', "if false; then heartbeat error", (TICK,)),   # B6-3 reordered the trap
    # B3 — coverage travels with the verdict: only a full context counts toward the >= 12
    "report-counts-partial": (PY, 'compared_ctx = rep["coverage"]["compared_full"]', 'compared_ctx = sum(rep["counts"][k] for k in hc.COMPARED)', (REPORT,)),
    "report-coverage-not-read": (PY, 'k: {"verdict": v, "coverage": cov.get(k), ', 'k: {"verdict": v, "coverage": "full", ', (REPORT,)),
    "report-unrecorded-is-full": (PY, 'cov = d.get("coverage") if isinstance(d.get("coverage"), dict) else {}',
                                  'cov = d.get("coverage") if isinstance(d.get("coverage"), dict) else dict.fromkeys(d.get("contexts") or {}, "full")',
                                  (REPORT,)),
    "report-partial-unshown": (PY, 'compared_partial = sum(len(r["compared_partial"]) for r in rows)', "compared_partial = 0", (REPORT,)),
    "report-unrecorded-unshown": (PY, 'compared_unrecorded = sum(len(r["compared_unrecorded"]) for r in rows)', "compared_unrecorded = 0", (REPORT,)),
    "tick-coverage-not-journalled": (PY, '                               "coverage": {k: (v or {}).get("coverage") for k, v in results.items()},\n', "",
                                     (TICK,)),
    "enqueue-partial-unnamed": (PY, 'elif res.get("coverage") != "full":   # executed', "elif False:   # executed", (TICK,)),
    "enqueue-partial-refuses": (PY, '        elif res.get("verdict") != "OK":\n            not_ok[str(name)]',
                                '        elif res.get("verdict") != "OK" or res.get("coverage") != "full":\n            not_ok[str(name)]', (TICK,)),
    "hc-unrecorded-is-full": (HC, '"coverage": cov if cov in COVERAGES else "unrecorded",', '"coverage": cov if cov in COVERAGES else "full",', (HCT,)),
    "hc-compared-full-counts-all": (HC, '"compared_full": sum(1 for r in compared if r["coverage"] == "full"),', '"compared_full": len(compared),',
                                    (HCT,)),
    "hc-row-drops-coverage": (HC, '"coverage": lo["coverage"], "coverage_note": lo["coverage_note"],', '"coverage": "full", "coverage_note": None,', (HCT,)),
    "hc-agreement-full-is-agreement": (HC, "r['class'] == 'AGREE' and r['coverage'] == 'full')", "r['class'] == 'AGREE')", (HCT,)),
    "runner-absent-coverage-partial": (RUNNER, 'coverage = it.get("coverage", "full")', 'coverage = it.get("coverage", "partial")', RUNT_COV),
    "runner-unreadable-coverage-full": (RUNNER, "        if coverage not in COVERAGES:\n", "        if False:\n", RUNT_COV),
    "runner-results-drop-coverage": (RUNNER, '        cov = {"coverage": ctx.get("coverage") or "unrecorded",', '        cov = {"coverage": "full",', RUNT_COV),
    # B3 — a full disk is no verdict: matched on error lines, never FAIL, never OK
    "runner-disk-full-ignored-jobs": (RUNNER, 'if (full := host_disk_full(r.get("logs") or [r.get("log")], r["label"])):', "if (full := None):", (HD,)),
    "runner-disk-full-ignored-contained": (RUNNER, "if (full := host_disk_full([log], name)):", "if (full := None):", (HD,)),
    "runner-disk-full-egress-unread": (RUNNER, 'r.get("logs") or [r.get("log")]', '[r.get("log")]', (HD,)),
    "runner-disk-full-substring": (RUNNER, '    r"ENOSPC: no space left on device"                         #',
                                   '    r"(?i)enospc|no[ _]space[ _]left|diskfull|ENOSPC: no space left on device"                         #', (HD,)),
    "runner-disk-full-python-exception-ok": (RUNNER, r'r"|^(?!.*\b\w*(?:Error|Exception)\b).*: [Nn]o space left on device\s*$")',
                                             r'r"|^.*: [Nn]o space left on device\s*$")', (HD,)),
    "runner-recovery-alone": (RUNNER, "                if DISK_FULL_LINE.search(line):\n",
                              "                if DISK_FULL_LINE.search(line) or RECOVERY_LINE.search(line):\n", (HD,)),
    "runner-no-verdict-any-status": (RUNNER, 'if s in ("ERROR", "BLOCKED") and (host := HOST_NO_VERDICT.match(reason)):',
                                     "if (host := HOST_NO_VERDICT.match(reason)):", (HD,)),
    "runner-no-verdict-anywhere": (RUNNER, 'HOST_NO_VERDICT = re.compile(r"^(?:host_disk_full|', 'HOST_NO_VERDICT = re.compile(r".*?(?:host_disk_full|',
                                   (HD,)),
    "hc-no-verdict-unnamed": (HC, '''+ (f" {res['no_verdict']}" if isinstance(res.get("no_verdict"), str) else "")''', '+ ""', (HCT,)),
    "enqueue-host-counted-executed": (PY, "{len(required) - len(non_executed) - len(host)}/", "{len(required) - len(non_executed)}/", (TICK,)),
    "enqueue-host-passes": (PY, '                                                               if host else "") if x) or None)}',
                            '                                                               if False else "") if x) or None)}', (TICK,)),
    "enqueue-host-any-verdict": (PY, 'elif res.get("verdict") in ("ERROR", "BLOCKED") and nv.split(" ")[0] in HOST_NO_VERDICT:',
                                 'elif nv.split(" ")[0] in HOST_NO_VERDICT:', (TICK,)),
    # B3 — the free-space floor: BLOCKED before a service leg starts, never a FAIL
    "floor-ignored": (RUNNER, 'if (floor := disk_floor_refusal(iso["docker"], iso["image_id"], run_dir)):', "if (floor := None):", (HD,)),
    "floor-default-zero": (RUNNER, 'MIN_FREE_ENV, DEFAULT_MIN_FREE_GB = "LOCALCI_MIN_FREE_GB", 12.0', 'MIN_FREE_ENV, DEFAULT_MIN_FREE_GB = "LOCALCI_MIN_FREE_GB", 0.0',
                           (HD,)),
    "floor-boundary": (RUNNER, "    if free < floor:\n", "    if free <= floor:\n", (HD,)),
    "floor-zero-still-reads": (RUNNER, "    if floor == 0:\n        return None\n", "", (HD,)),
    "floor-unmeasured-runs": (RUNNER, "    if free is None:\n        return f\"host_disk_unmeasured:", "    if free is None and False:\n        return f\"host_disk_unmeasured:",
                              (HD,)),
    "floor-invalid-is-default": (RUNNER, '        floor = float("nan")\n', "        floor = DEFAULT_MIN_FREE_GB\n", (HD,)),
    "floor-not-cached": (RUNNER, "    if key not in _HOST_FREE:\n", "    if True:\n", (HD,)),
    "floor-probe-wrong-column": (RUNNER, "return int(fields[3]) * 1024 / 1e9, None", "return int(fields[2]) * 1024 / 1e9, None", (HD,)),
    "floor-probe-networked": (RUNNER, '"--rm", "--network", "none", "--cap-drop", "ALL",', '"--rm", "--network", "bridge", "--cap-drop", "ALL",', (HD,)),
    "floor-no-verdict-unnamed": (RUNNER, r"|host_disk_below_floor \d+(?:\.\d+)?GB<\d+(?:\.\d+)?GB|", "|", (HD,)),
    "merger-floor-env-dropped": (PY, '              "LOCALCI_MIN_FREE_GB")  # an allowlist', "              )  # an allowlist", (TICK,)),
    "merger-floor-not-host": (PY, 'HOST_NO_VERDICT = ("host_disk_full", "host_disk_below_floor", "host_disk_unmeasured", "host_disk_floor_invalid")',
                              'HOST_NO_VERDICT = ("host_disk_full",)', (TICK,)),
    # B5-1: the scope of a rewritten judge is the step; where the plan cannot attribute, the context, said
    "b5-judge-scope-context": (RUNNER, "return [f for f in mod if f in planned[step]] + everyone", "return mod", (JR,)),
    "b5-judge-red-claimed": (RUNNER, 's["status"] in ("FAIL", "ERROR")', 's["status"] in ()', (JR,)),
    "b5-judge-error-claimed": (RUNNER, 's["status"] in ("FAIL", "ERROR")', 's["status"] in ("FAIL",)', (JR,)),
    "b5-judge-unattributed-ignored": (RUNNER, 'return mod, " (context scope: the plan attributes no judge to this step)"',
                                      'return [], " (context scope: the plan attributes no judge to this step)"', (JR,)),
    "b5-judge-unnamed-file-ignored": (RUNNER, "everyone = [f for f in mod if f not in named]", "everyone = []", (JR,)),
    "b5-judge-plan-unattributed": (RUNNER, 'st["trusted"] = step_judges([st], files)', 'st["trusted"] = []', (JR,)),
    "b5-judge-no-verdict-unnamed": (RUNNER, 'out["results"][name]["no_verdict"] = "judge_rewritten"', "pass", (JR,)),
    "b5-judge-rewritten-is-fail": (RUNNER, 'return "BLOCKED", ("judge_rewritten: "', 'return "FAIL", ("judge_rewritten: "', (JR,)),
    # B5-2: the skip rides on the result and the row says what was compared
    "b5-skip-unmarked": (RUNNER, '"skipped": "change_map",', "", (SKC,)),
    "b5-skip-not-carried": (RUNNER, 'if s == "NOT_APPLICABLE" and isinstance(skip := ', 'if False and isinstance(skip := ', (SKC,)),
    "b5-label-agreed-as-executed": (HC, """"local_detail": f"NOT_APPLICABLE (skip agreed: {lo['skipped']})\"""", '"local_detail": lo["detail"]', (SKC,)),
    "b5-label-hosted-ran-as-executed": (HC, '"NOT_APPLICABLE (skipped here; hosted ran)"', '"OK (executed)"', (SKC,)),
    "b5-label-hosted-skipped-unsaid": (HC, 'lo["detail"][:-1] + "; hosted skipped)"', 'lo["detail"]', (SKC,)),
    "b5-hosted-ran-counted-full": (HC, '"coverage": "partial",', '"coverage": lo["coverage"],', (SKC, *REPORT_SKIP)),
    "b5-agreed-keeps-execution-coverage": (HC, '"coverage": "full", "coverage_note": None}', '"coverage": lo["coverage"], "coverage_note": lo["coverage_note"]}', (SKC,)),
    "b5-pending-read-as-ran": (HC, 'if h["verdict"] != "PENDING":', "if True:", (SKC,)),
    "b5-agreed-uncounted": (HC, 'if r["skip"] == "agreed"]', 'if r["skip"] == "hosted_skipped"]', (SKC, *REPORT_SKIP)),
    # B5-3: journalled by the tick, read back by the report, counted apart on both lines
    "b5-tick-skip-unjournalled": (PY, '"skipped": {k: v["skipped"] for k, v in results.items() if isinstance((v or {}).get("skipped"), str)},', "", TICK_SKIP),
    "b5-report-skip-unread": (PY, '"skipped": skip.get(k)}', '"skipped": None}', REPORT_SKIP),
    "b5-report-window-uncounted": (PY, 'compared_skip_agreed = sum(len(r["compared_skip_agreed"]) for r in rows)', "compared_skip_agreed = 0", REPORT_SKIP),
    "b5-report-merges-uncounted": (PY, 'merged_skip_agreed = sum(', "merged_skip_agreed = 0 * sum(", REPORT_SKIP),
}


def copy_tree(dest: Path) -> None:
    for rel in ("scripts/localci", "scripts/lib", "scripts/ci"):   # scripts/ci: the trusted classifier the runner's fixture repo copies
        shutil.copytree(ROOT / rel, dest / rel, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (dest / "scripts" / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "tests" / "test_ban_predicates.py", dest / "scripts" / "tests" / "test_ban_predicates.py")
    for rel in ("scripts/ops/pro_disk_floor_tick.sh", "infra/launchagents/com.nuzantara.disk-floor.plist", "infra/home-fork/declared-pairs.json"):
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)   # B6-4: the disk-floor organ and the files its test reads
        shutil.copy2(ROOT / rel, dest / rel)


def run_tests(tree: Path, files: tuple[str, ...]) -> int:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env.update(PYTHONPATH=str(tree), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *files], cwd=tree, env=env,
                          capture_output=True, text=True).returncode


def verdict(rc: int) -> str:
    return {0: "SURVIVED", 1: "KILLED"}.get(rc, f"ERROR (pytest exit {rc})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="+", metavar="NAME", help="run only these mutants")
    ap.add_argument("--list", action="store_true", help="print the table and exit")
    a = ap.parse_args(argv)
    names = a.only or list(MUTANTS)
    if unknown := [n for n in names if n not in MUTANTS]:
        print(f"unknown mutant(s): {unknown}", file=sys.stderr)
        return 2
    if a.list:
        for n in names:
            print(f"{n:30} {MUTANTS[n][0]}")
        return 0
    with tempfile.TemporaryDirectory(prefix="merger-mutants-") as tmp:
        tree = Path(tmp)
        copy_tree(tree)
        originals = {f: (tree / f).read_text() for f in sorted({m[0] for m in MUTANTS.values()})}
        for files in sorted({MUTANTS[n][3] for n in names}):
            if (rc := run_tests(tree, files)) != 0:
                print(f"baseline: the unmutated copy gives pytest exit {rc} on {' '.join(files)} — nothing to measure", file=sys.stderr)
                return 2
        survived, stale, errors = [], [], []
        for n in names:
            target, old, new, tests = MUTANTS[n]
            if originals[target].count(old) != 1 or old == new:
                stale.append(n)
                print(f"{n:30} STALE (the rule's text occurs {originals[target].count(old)} times)", flush=True)
                continue
            (tree / target).write_text(originals[target].replace(old, new))
            v = verdict(run_tests(tree, tests))
            (tree / target).write_text(originals[target])
            if v == "SURVIVED":
                survived.append(n)
            elif v != "KILLED":
                errors.append(n)
            print(f"{n:30} {v}", flush=True)
    killed = len(names) - len(survived) - len(stale) - len(errors)
    print(f"{killed}/{len(names)} killed; survivors: {survived or 'none'}; errors: {errors or 'none'}; stale: {stale or 'none'}")
    return 1 if survived or stale or errors else 0


if __name__ == "__main__":
    sys.exit(main())
