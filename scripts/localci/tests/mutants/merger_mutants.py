"""Replayable mutation sweep for the merger (merger.py, localci_merger_tick.sh) against its two test files.

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

# name: (file, text that must occur once, replacement, test files that must turn red)
MUTANTS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # which hosted verdict judges a decision, and when a merge counts for phase E
    "parents-membership": (PY, 'return mc if parents[mc] == [d.get("base_sha")] else', 'return mc if d.get("base_sha") in parents[mc] else', (REPORT,)),
    "merged-here-any-base": (PY, 'merged_here = sha != head and sha == prs[n].get("merge_commit_sha")',
                             'merged_here = prs[n].get("merged") is True and head_of(prs[n]) == head', (REPORT,)),
    "min-contexts-minus-one": (PY, "compared_ctx >= MIN_COMPARED_CONTEXTS})", "compared_ctx >= MIN_COMPARED_CONTEXTS - 1})", (REPORT,)),
    "min-contexts-ignored": (PY, "compared_ctx >= MIN_COMPARED_CONTEXTS})", "True})", (REPORT,)),
    "merges-not-deduped": (PY, 'merges = sorted({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())',
                           'merges = sorted(r["merged_at"] for r in rows if r["compared_merge"])', (REPORT,)),
    "merges-unsorted": (PY, 'merges = sorted({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())',
                        'merges = list({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())', (REPORT,)),
    "merged-at-unrequired": (PY, "            if merged_here and not is_ts(merged_at):", "            if False:", (REPORT,)),
    "merged-is-green": (PY, '''    if merged_here:
        return "RED" if "RED" in seen else "GREEN"''', '''    if merged_here:
        return "GREEN"''', (REPORT,)),
    "hosted-red-merged-unclassed": (PY, '"class": "HOSTED_RED_MERGED" if merged_here and github == "RED" else classify(',
                                    '"class": classify(', (REPORT,)),
    "pr-number-always": (PY, 'if runner_takes(base_wt, "--pr-number"):', "if True:", (TICK,)),
    "pr-number-never": (PY, 'if runner_takes(base_wt, "--pr-number"):', "if False:", (TICK,)),
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
}


def copy_tree(dest: Path) -> None:
    for rel in ("scripts/localci", "scripts/lib"):
        shutil.copytree(ROOT / rel, dest / rel, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))


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
        originals = {f: (tree / f).read_text() for f in (PY, SH)}
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
