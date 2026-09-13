#!/usr/bin/env python3
"""Evaluation harness for LAYER 2 (mos_recall_sessionstart.py) against a
fixed 12-scenario query -> expected-file set, plus a baseline comparison
against the existing `mem recall` CLI (~/.claude/scripts/mem).

Read-only on MEMDIR. Writes only inside the scratchpad dir given via --out.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mos_recall_sessionstart as mos  # noqa: E402

SCENARIOS = [
    ("merge PR apps/backend-rag migration release_command",
     "discovery_merging_a_backend_rag_pr_deploys_by_itself_2026_09_01.md"),
    ("flyctl ssh console postgres superuser psql stdin",
     "discovery_flyctl_ssh_console_without_dash_C_swallows_piped_stdin_2026_08_30.md"),
    ("merge queue phantom conflict armed PR autoMergeRequest",
     "discovery_curing_a_phantom_conflict_on_an_armed_pr_is_merging_it_2026_09_01.md"),
    ("rollback script dry-run flag parsing",
     "lesson_a_rollback_script_that_executes_on_any_unknown_flag_2026_09_02.md"),
    ("git checkout -- after mutation test uncommitted cure",
     "lesson_a_guilt_mutation_restored_with_git_checkout_wipes_the_uncommitted_cure_2026_09_04.md"),
    ("github secret scanning alerts list api",
     "discovery_github_secret_scanning_api_returns_the_secret_itself_2026_08_20.md"),
    ("WR2 carousel launchd cron rearm",
     "decision_wr2_runs_only_on_command_2026_09_01.md"),
    ("launchctl kickstart plist environment reload",
     "discovery_launchctl_kickstart_does_not_reload_environment_variables_2026_09_02.md"),
    ("jsonb double encoded json.dumps asyncpg",
     "discovery_jsonb_codec_double_encodes_and_test_pools_hide_it_2026_08_27.md"),
    ("worktree reaper prune squash merged branch",
     "discovery_the_worktree_reaper_is_a_guard_that_can_only_ever_say_no_2026_09_01.md"),
    ("ssh mini LAN tailscale office",
     "fact_mini_is_in_the_office_on_a_separate_isp_line_2026_08_12.md"),
    ("context diet /context tokens CLAUDE.md MEMORY.md",
     "project_context_diet_index_architecture_2026_09_04.md"),
]

PII_PATTERNS = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone_id_it", re.compile(r"\+(?:62|39)[\s.-]?\d[\d\s.-]{6,}\d")),
    ("digit_run_8plus", re.compile(r"\d{8,}")),
    ("passport_ktp", re.compile(r"\b(?:passport|KTP)\b\D{0,10}\d", re.IGNORECASE)),
]


def pii_scan(text: str) -> list[str]:
    hits = []
    for name, pat in PII_PATTERNS:
        if pat.search(text):
            hits.append(name)
    return hits


def verify_expected_files_exist(memdir: str) -> list[str]:
    missing = []
    for _q, expected in SCENARIOS:
        if not os.path.exists(os.path.join(memdir, expected)):
            missing.append(expected)
    return missing


def rank_of(expected_filename: str, ranked_filenames: list[str]) -> int | None:
    try:
        return ranked_filenames.index(expected_filename) + 1
    except ValueError:
        return None


def run_prototype(memdir: str, cache_path: str, query: str, k: int = 6):
    t0 = time.time()
    results, stats = mos.recall(memdir, cache_path, query, topk=k, use_cache=True)
    elapsed = time.time() - t0
    ranked = [r["filename"] for r in results]
    out_text = mos.format_output(results)
    return ranked, elapsed, out_text, stats


def run_baseline(mem_bin: str, query: str, k: int = 6):
    """Baseline: ~/.claude/scripts/mem recall "<q>" -k 6"""
    t0 = time.time()
    try:
        proc = subprocess.run(
            [mem_bin, "recall", query, "-k", str(k)],
            capture_output=True, text=True, timeout=30,
        )
        out = proc.stdout
        err = proc.stderr
        rc = proc.returncode
    except Exception as e:  # noqa: BLE001
        out, err, rc = "", str(e), -1
    elapsed = time.time() - t0
    # extract .md filenames mentioned in the baseline's output, in order of appearance
    filenames = re.findall(r"([A-Za-z0-9_.\-]+\.md)", out)
    # de-dup preserving order
    seen = set()
    ranked = []
    for fn in filenames:
        if fn not in seen:
            seen.add(fn)
            ranked.append(fn)
    return ranked, elapsed, out, err, rc


def main() -> int:
    ap = argparse.ArgumentParser()
    # mos_recall_sessionstart.py renamed its MEMDIR_DEFAULT constant to resolve_memdir(), a
    # function: called from an agent worktree, a bare constant can only ever point at the
    # worktree's own (nonexistent) memdir, whereas resolve_memdir() falls back to the MAIN
    # worktree's memdir via `git rev-parse --git-common-dir`. Nothing caught this rename
    # while this bench lived only in an unmerged worktree — which is exactly why it is being
    # landed now. The companion test (scripts/tests/test_recall_eval_bench.py) pins this API
    # surface with inspect.signature so the next rename fails loudly instead of rotting quietly.
    ap.add_argument("--memdir", default=mos.resolve_memdir())
    ap.add_argument("--cache-path", required=True)
    ap.add_argument("--mem-bin", default=os.path.expanduser("~/.claude/scripts/mem"))
    ap.add_argument("--out", required=True, help="scratchpad dir to write JSON report + session-mode output")
    ap.add_argument("--skip-baseline", action="store_true")
    args = ap.parse_args()

    # DEFECT 2 fix: the docstring above claims this bench is "read-only on MEMDIR", but
    # nothing enforced it -- mos.recall(..., use_cache=True) calls build_or_refresh_index
    # -> save_cache(cache_path, index), and that cache serialises each memory's `name`,
    # `description` and a body preview UNREDACTED. If --cache-path (or --out) points inside
    # --memdir, this bench itself becomes the leak: an unredacted copy of the operator's
    # real memory content written back into the memory dir it is supposed to only measure.
    # This is not a theoretical concern -- it is the concrete failure mode of the very cache
    # this bench forces on (use_cache=True in run_prototype). Resolve real paths and refuse
    # to run rather than silently write there.
    memdir_real = Path(args.memdir).resolve() if args.memdir else None
    out_real = Path(args.out).resolve()
    cache_real = Path(args.cache_path).resolve()

    def _is_inside(path: Path, base: Path) -> bool:
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False

    if memdir_real is not None:
        offenders = [flag for flag, p in (("--out", out_real), ("--cache-path", cache_real)) if _is_inside(p, memdir_real)]
        if offenders:
            raise SystemExit(
                f"recall_eval.py: {', '.join(offenders)} resolve(s) inside --memdir ({memdir_real}) -- "
                "this bench is read-only on MEMDIR by contract. mos.recall(..., use_cache=True) writes "
                "an UNREDACTED cache (memory name/description/body preview) to --cache-path, so a "
                "--cache-path (or --out) under MEMDIR is a concrete PII/content leak into the memory "
                "dir, not a theoretical one. Point --out and --cache-path outside --memdir."
            )

    os.makedirs(args.out, exist_ok=True)

    missing = verify_expected_files_exist(args.memdir)
    if missing:
        print(f"WARNING: {len(missing)} expected file(s) not found in MEMDIR: {missing}", file=sys.stderr)

    rows = []
    proto_hit1 = proto_hit3 = proto_hit6 = 0
    base_hit1 = base_hit3 = base_hit6 = 0
    proto_latencies = []
    base_latencies = []
    pii_findings = []

    for query, expected in SCENARIOS:
        p_ranked, p_elapsed, p_out, p_stats = run_prototype(args.memdir, args.cache_path, query)
        p_rank = rank_of(expected, p_ranked)
        proto_latencies.append(p_elapsed)
        if p_rank == 1:
            proto_hit1 += 1
        if p_rank and p_rank <= 3:
            proto_hit3 += 1
        if p_rank and p_rank <= 6:
            proto_hit6 += 1

        p_hits = pii_scan(p_out)
        if p_hits:
            pii_findings.append({"scenario": query, "layer": "prototype", "hits": p_hits})

        row = {
            "query": query,
            "expected": expected,
            "prototype_rank": p_rank,
            "prototype_output_bytes": len(p_out.encode("utf-8")),
            "prototype_elapsed_s": round(p_elapsed, 4),
        }

        if not args.skip_baseline:
            b_ranked, b_elapsed, b_out, b_err, b_rc = run_baseline(args.mem_bin, query)
            b_rank = rank_of(expected, b_ranked)
            base_latencies.append(b_elapsed)
            if b_rank == 1:
                base_hit1 += 1
            if b_rank and b_rank <= 3:
                base_hit3 += 1
            if b_rank and b_rank <= 6:
                base_hit6 += 1
            b_hits = pii_scan(b_out)
            if b_hits:
                pii_findings.append({"scenario": query, "layer": "baseline", "hits": b_hits})
            row.update({
                "baseline_rank": b_rank,
                "baseline_returncode": b_rc,
                "baseline_elapsed_s": round(b_elapsed, 4),
                # DEFECT 4 fix: the raw baseline stderr used to be copied verbatim into the
                # report ("baseline_stderr_snippet": b_err[:200]) -- `mem recall` is free to
                # echo back fragments of the query or matched memory content on error, and
                # this report is a shared artifact (CLAUDE.md Part A rule 4: no client PII/
                # OSINT in cleartext in any shared artifact). Record only the fact that stderr
                # was non-empty, never its content.
                "baseline_stderr_nonempty": bool((b_err or "").strip()),
            })

        rows.append(row)

    n = len(SCENARIOS)
    report = {
        "n_scenarios": n,
        "missing_expected_files": missing,
        "prototype": {
            "hit_at_1": proto_hit1, "hit_at_3": proto_hit3, "hit_at_6": proto_hit6,
            "hit_at_1_pct": round(100 * proto_hit1 / n, 1),
            "hit_at_3_pct": round(100 * proto_hit3 / n, 1),
            "hit_at_6_pct": round(100 * proto_hit6 / n, 1),
            "mean_latency_s": round(sum(proto_latencies) / n, 4),
        },
        "baseline": None if args.skip_baseline else {
            "hit_at_1": base_hit1, "hit_at_3": base_hit3, "hit_at_6": base_hit6,
            "hit_at_1_pct": round(100 * base_hit1 / n, 1),
            "hit_at_3_pct": round(100 * base_hit3 / n, 1),
            "hit_at_6_pct": round(100 * base_hit6 / n, 1),
            "mean_latency_s": round(sum(base_latencies) / n, 4) if base_latencies else None,
        },
        "pii_findings": pii_findings,
        "pii_finding_count": len(pii_findings),
        "rows": rows,
    }

    report_path = os.path.join(args.out, "recall_eval_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    print(f"\n[recall_eval] wrote {report_path}", file=sys.stderr)

    # DEFECT 4 fix: a PII hit used to sit quietly in the report's pii_findings list with
    # exit code 0 -- a green CI/cron run and a positive PII finding looked identical from
    # the outside (exactly the "green != working" shape this repo's scar family #2 names).
    # Surface it on stderr and fail the process so a caller (human or cron) cannot miss it.
    if pii_findings:
        print(f"[recall_eval] PII findings: {len(pii_findings)}", file=sys.stderr)
        for finding in pii_findings:
            print(f"  scenario={finding['scenario']!r} layer={finding['layer']} hits={finding['hits']}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
