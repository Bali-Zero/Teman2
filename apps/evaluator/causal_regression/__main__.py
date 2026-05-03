"""CLI entry for the causal regression harness.

Usage:
    python -m apps.evaluator.causal_regression \
        --range HEAD~30..HEAD \
        --eval-set apps/evaluator/causal_regression/data/eval_visa.jsonl \
        --out outputs/

The command is pure: same repo state + same inputs -> byte-identical JSON.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._gitblob import GitError
from .causal_diff import diff_snapshots
from .commit_walker import DEFAULT_PATH_FILTER, walk_range
from .regression_report import (
    ReportInputs,
    build_json,
    write_html,
    write_json,
    write_report,
)
from .replay_engine import load_eval_set, run_eval_set


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="causal_regression")
    p.add_argument("--range", default="HEAD~30..HEAD", help="git revision range")
    p.add_argument("--eval-set", help="path to JSONL eval set")
    p.add_argument("--out", default="outputs/", help="directory for JSON+HTML reports")
    p.add_argument("--kb-root", default="apps/backend-rag/backend/kb")
    p.add_argument("--repo", default=".", help="path to git repo root")
    p.add_argument(
        "--path-filter",
        default=DEFAULT_PATH_FILTER,
        help="restrict walker to commits touching this path (empty to disable)",
    )
    p.add_argument(
        "--cache-root",
        default="/tmp/causal-kb-cache",
        help="directory where per-SHA KB snapshots are materialized",
    )
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--coverage-threshold", type=float, default=0.5)
    p.add_argument(
        "--trim-json",
        action="store_true",
        help="emit a slim JSON (no per-query results, no retrieval_delta arrays)",
    )
    p.add_argument("--dry-run", action="store_true", help="walk only, print counts")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p


def _log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(msg, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _make_parser().parse_args(argv)

    repo = str(Path(args.repo).resolve())
    cache_root = Path(args.cache_root)

    try:
        snapshots = walk_range(args.range, repo, args.path_filter or "")
    except GitError as e:
        print(f"git range invalid: {e}", file=sys.stderr)
        return 4

    if not snapshots:
        print(f"no commits matched range {args.range}", file=sys.stderr)
        return 2

    _log(f"walked {len(snapshots)} commits", args.quiet)

    if args.dry_run:
        for s in snapshots:
            print(f"{s.short_sha} {s.subject}")
        return 0

    if not args.eval_set:
        print("--eval-set is required unless --dry-run", file=sys.stderr)
        return 3

    try:
        eval_rows = load_eval_set(args.eval_set)
    except (OSError, ValueError) as e:
        print(f"failed to load eval set: {e}", file=sys.stderr)
        return 3

    _log(f"loaded {len(eval_rows)} eval rows", args.quiet)

    all_results = []
    all_warnings: list[str] = []
    per_commit_results: dict[str, list] = {}
    for snap in snapshots:
        results, warns = run_eval_set(
            snap,
            eval_rows,
            repo=repo,
            kb_root=args.kb_root,
            cache_root=cache_root,
            top_k=args.top_k,
            coverage_pass_threshold=args.coverage_threshold,
        )
        per_commit_results[snap.sha] = results
        all_results.extend(results)
        all_warnings.extend(warns)
        if args.verbose:
            passes = sum(1 for r in results if r.passed)
            _log(
                f"  {snap.short_sha} {passes}/{len(results)} pass",
                args.quiet,
            )

    # Pairwise diffs: walker yields oldest-first; we diff i vs i-1.
    all_diffs = []
    for i in range(1, len(snapshots)):
        prev_snap = snapshots[i - 1]
        curr_snap = snapshots[i]
        all_diffs.extend(
            diff_snapshots(
                prev_snap,
                curr_snap,
                per_commit_results[prev_snap.sha],
                per_commit_results[curr_snap.sha],
            )
        )

    inputs = ReportInputs(
        range_expr=args.range,
        snapshots=snapshots,
        results=all_results,
        diffs=all_diffs,
        warnings=all_warnings,
        kb_root=args.kb_root,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "causal_report.json"
    html_path = out_dir / "causal_report.html"
    write_json(build_json(inputs, trim=args.trim_json), json_path)
    write_html(inputs, html_path)
    _log(f"wrote {json_path}", args.quiet)
    _log(f"wrote {html_path}", args.quiet)

    return 0


if __name__ == "__main__":
    sys.exit(main())
