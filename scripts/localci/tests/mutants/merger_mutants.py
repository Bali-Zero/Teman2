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

# name: (file, text that must occur once, replacement, test files that must turn red)
MUTANTS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # which hosted verdict judges a decision, and when a merge counts for phase E
    "parents-membership": (PY, 'return mc if parents[mc] == [d.get("base_sha")] else', 'return mc if d.get("base_sha") in parents[mc] else', (REPORT,)),
    "merged-here-any-base": (PY, 'merged_here = sha != head and sha == prs[n].get("merge_commit_sha")',
                             'merged_here = prs[n].get("merged") is True and head_of(prs[n]) == head', (REPORT,)),
    "min-contexts-minus-one": (PY, "compared_ctx >= MIN_COMPARED_CONTEXTS})", "compared_ctx >= MIN_COMPARED_CONTEXTS - 1})", (REPORT,)),
    "min-contexts-ignored": (PY, "compared_ctx >= MIN_COMPARED_CONTEXTS})", "True})", (REPORT,)),
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
    "sh-heartbeat-always-ok": (SH, 'if [ "$rc" -eq 0 ]; then heartbeat ok', "if true; then heartbeat ok", (TICK,)),
    # B3 — coverage travels with the verdict: only a full context counts toward the >= 12
    "report-counts-partial": (PY, 'compared_ctx = rep["coverage"]["compared_full"]', 'compared_ctx = sum(rep["counts"][k] for k in hc.COMPARED)', (REPORT,)),
    "report-coverage-not-read": (PY, 'k: {"verdict": v, "coverage": cov.get(k)}', 'k: {"verdict": v, "coverage": "full"}', (REPORT,)),
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
}


def copy_tree(dest: Path) -> None:
    for rel in ("scripts/localci", "scripts/lib", "scripts/ci"):   # scripts/ci: the trusted classifier the runner's fixture repo copies
        shutil.copytree(ROOT / rel, dest / rel, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (dest / "scripts" / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "tests" / "test_ban_predicates.py", dest / "scripts" / "tests" / "test_ban_predicates.py")


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
