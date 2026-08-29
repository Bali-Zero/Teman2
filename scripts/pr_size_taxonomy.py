#!/usr/bin/env python3
"""pr_size_taxonomy.py — advisory classifier for the repo's <=400-net-line PR contract.

L04-PR3. REPORT-ONLY: never exits non-zero because a PR is big, no `--check`
flag, workflow never a required check. Answers what a flat net-line count
cannot: of PRs over contract, how many are over ONLY because of artifacts this
repo MANDATES (evidence pack, guilt+innocence corpus, spec/research capture) vs
over in actual code. Measured on the 100 most-recently-merged PRs at authoring
time: 31 exceed 400 net lines total; 11 still exceed it after excluding
mandated artifacts — a MEASUREMENT of what the flat metric miscounted as
bloat, not a claim anything shrank. Every number is RECOMPUTED from input on
each run (--fixture for tests/offline, gh otherwise), never a constant (W106).

TAXONOMY (match order below, defined before classification runs):
  evidence   evidence/**                       mandated per-PR artifact; inseparable from its diff.
  tests      **/tests/**, test_*.py, *.spec.*, splitting a guilt+innocence corpus from its subject is
             *.test.*                           the W81 shipped-guard-without-arming trap.
  docs       docs/**, research/**, .claude/**  a spec/plan/scar is ONE artifact; 400-line chunks unreadable.
  lockfile   *.lock, package-lock.json, ...    regenerated, not authored.
  generated  content-marker ONLY               NEVER path-inferred (no glob, e.g. no "fixture"-substring
                                                 guess); fires only on a literal machine-authorship comment
                                                 line in the file's first 20 lines. No such marker is in
                                                 live use on this repo's code today — honestly, never fires yet.
  code       everything else                   the ONLY class where >400 net lines is a real signal.

Verdict: `exempt(<class>)` when CODE-only residual <= contract (mandated
artifacts explain the overage), else `split-required` regardless of exempt
payload size — a huge evidence+tests pack beside 5,000 real code lines still
reads split-required (the composition trap this is pinned against).

SPLIT RECIPES (name the chosen one in a split-required PR's body): by-files
(one PR per unrelated concern), horizontal (split by LAYER: contract, impl,
wiring), vertical (split by SLICE: one working code path per PR), stacked
(real dependency order — PR A, then B on A, then C on B; each child stays
under contract).

`--explain <PR>` prints every counted file's class, for auditability.

SIGNED NET, NOT MAGNITUDE — a definitional choice, stated because it is
invisible at every call site. Both gates compare the SIGNED value, so a PR
deleting 5,000 code lines reads `within-contract` (net -5000) while one adding
5,000 reads `split-required`. Defensible (a pure removal is not the bloat this
measures) but not an arithmetic fact. It matters: the orchestrator's independent
ground measurement of this window used `abs(net) > 400` and got the same 31 —
a property of THIS window (all 31 are net-positive), not agreement between the
definitions. Pinned by `test_the_over_contract_test_is_on_signed_net_not_magnitude`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CONTRACT_DEFAULT = 400
TESTS_RE = re.compile(r"(^|/)tests?/|(^|/)test_[^/]+\.py$|\.spec\.[^/.]+$|\.test\.[^/.]+$", re.I)
LOCKFILE_RE = re.compile(
    r"(^|/)(package-lock\.json|poetry\.lock|uv\.lock|Cargo\.lock|Gemfile\.lock|yarn\.lock)$|\.lock$"
)
# `generated` header marker — NOT a path glob (see docstring): only a literal
# machine-authorship comment line in a file's own first 20 lines counts.
GENERATED_MARKER_RE = re.compile(r"^\s*(#|//|/\*|<!--)\s*@?generated\b", re.I)

CLASS_EVIDENCE, CLASS_TESTS, CLASS_DOCS = "evidence", "tests", "docs"
CLASS_LOCKFILE, CLASS_GENERATED, CLASS_CODE = "lockfile", "generated", "code"
EXEMPT_CLASSES = (CLASS_EVIDENCE, CLASS_TESTS, CLASS_DOCS, CLASS_LOCKFILE, CLASS_GENERATED)

def classify_path(path: str) -> str:
    """Path-only classification. `generated` is deliberately absent here — it is
    never inferred from a path, only from content (see `_has_generated_marker`)."""
    if path.startswith("evidence/"):
        return CLASS_EVIDENCE
    if TESTS_RE.search(path):
        return CLASS_TESTS
    if path.startswith("docs/") or path.startswith("research/") or path.startswith(".claude/"):
        return CLASS_DOCS
    if LOCKFILE_RE.search(path):
        return CLASS_LOCKFILE
    return CLASS_CODE

def _has_generated_marker(text: str) -> bool:
    return any(GENERATED_MARKER_RE.match(line) for line in text.splitlines()[:20])

def _probe_generated_via_git(sha: str | None, path: str) -> bool:
    """Best-effort, never raises: missing sha / missing local git object / any
    subprocess failure means "not generated" — degrades to never-firing, never
    to a crash."""
    if not sha:
        return False
    try:
        proc = subprocess.run(["git", "show", f"{sha}:{path}"], capture_output=True, text=True, timeout=5)
        return proc.returncode == 0 and _has_generated_marker(proc.stdout)
    except Exception:
        return False

def classify_files(files: list[dict], sha: str | None, probe_generated: bool) -> list[dict]:
    out = []
    for f in files:
        p, a, d = f["p"], int(f.get("a", 0)), int(f.get("d", 0))
        cls = classify_path(p)
        if cls == CLASS_CODE and probe_generated and _probe_generated_via_git(sha, p):
            cls = CLASS_GENERATED
        out.append({"p": p, "a": a, "d": d, "net": a - d, "churn": a + d, "cls": cls})
    return out

def pr_verdict(pr: dict, contract: int = CONTRACT_DEFAULT, probe_generated: bool = False) -> dict:
    """`total_net` is derived from the file list (single source of truth with the
    per-class attribution below) when files are present; a PR never fetched past
    the within-contract fast check falls back to PR-level net."""
    files = classify_files(pr.get("files") or [], pr.get("mergeSha"), probe_generated)
    total_net = sum(f["net"] for f in files) if files else pr.get("net", 0)
    if total_net <= contract:
        return {"n": pr["n"], "t": pr.get("t", ""), "total_net": total_net,
                "code_residual_net": None, "by_class_net": {}, "by_class_churn": {},
                "verdict": "within-contract", "label": None, "files": files}

    by_net: dict[str, int] = defaultdict(int)
    by_churn: dict[str, int] = defaultdict(int)
    for f in files:
        by_net[f["cls"]] += f["net"]
        by_churn[f["cls"]] += f["churn"]
    code_residual = by_net.get(CLASS_CODE, 0)

    if code_residual <= contract:
        contribs = {c: by_net.get(c, 0) for c in EXEMPT_CLASSES if by_net.get(c, 0) > 0}
        dominant = max(contribs, key=contribs.get) if contribs else CLASS_CODE
        verdict, label = "exempt", f"exempt({dominant})"
    else:
        verdict, label = "split-required", "split-required"
    return {"n": pr["n"], "t": pr.get("t", ""), "total_net": total_net,
            "code_residual_net": code_residual, "by_class_net": dict(by_net),
            "by_class_churn": dict(by_churn), "verdict": verdict, "label": label, "files": files}

def build_report(prs: list[dict], contract: int = CONTRACT_DEFAULT, probe_generated: bool = False) -> dict:
    verdicts = [pr_verdict(pr, contract, probe_generated) for pr in prs]
    over = [v for v in verdicts if v["verdict"] != "within-contract"]
    split_required = [v for v in over if v["verdict"] == "split-required"]
    churn_totals: dict[str, int] = defaultdict(int)
    total_churn = 0
    for v in over:
        for cls, val in v["by_class_churn"].items():
            churn_totals[cls] += val
            total_churn += val
    churn_share = {c: (v / total_churn if total_churn else 0.0) for c, v in churn_totals.items()}
    return {"examined": len(prs), "contract": contract,
            "over_contract_total": len(over), "over_contract_nonexempt": len(split_required),
            "exempt_count": len(over) - len(split_required),
            "churn_share": churn_share, "verdicts": verdicts}

def render_markdown(report: dict) -> str:
    lines = [
        "# PR size taxonomy (advisory — report-only, never gates a merge)", "",
        f"Examined {report['examined']} merged PRs against the <={report['contract']}-net-line contract.",
        f"- Over contract, total diff: **{report['over_contract_total']}**",
        f"- Over contract, code residual after exemptions: **{report['over_contract_nonexempt']}**",
        f"- Exempt (mandated artifacts alone explain the overage): **{report['exempt_count']}**", "",
        "Nothing here was reduced — this measures what a flat net-line count was",
        "miscounting as bloat; it is not a claim that any PR shrank.", "",
        "| PR | title | total net | code residual | verdict |",
        "|---|---|---:|---:|---|",
    ]
    for v in report["verdicts"]:
        if v["verdict"] == "within-contract":
            continue
        title = (v["t"] or "")[:60]
        lines.append(f"| #{v['n']} | {title} | {v['total_net']} | {v['code_residual_net']} | {v['label']} |")
    if report["churn_share"]:
        lines.append("")
        lines.append("Churn share (add+del) across over-contract PRs, by class:")
        for cls, share in sorted(report["churn_share"].items(), key=lambda kv: -kv[1]):
            lines.append(f"- {cls}: {share * 100:.1f}%")
    return "\n".join(lines) + "\n"

def render_explain(v: dict) -> str:
    lines = [f"# PR #{v['n']} — {v['t']}", "",
             f"total net: {v['total_net']}  verdict: {v['label'] or v['verdict']}", "",
             "| file | net (add-del) | class |", "|---|---:|---|"]
    for f in v["files"]:
        lines.append(f"| {f['p']} | {f['net']} | {f['cls']} |")
    return "\n".join(lines) + "\n"

# --- gh I/O, kept apart from the pure classification above so the whole -----
# --- taxonomy is testable offline via --fixture, no network dependency. -----

def _gh_json(args: list[str]) -> Any:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)

def fetch_pr_files(number: int) -> list[dict]:
    proc = subprocess.run(
        ["gh", "api", f"repos/:owner/:repo/pulls/{number}/files", "--paginate",
         "--jq", ".[] | {p: .filename, a: .additions, d: .deletions}"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh api pulls/{number}/files failed: {proc.stderr.strip()}")
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

def _pr_shell(r: dict) -> dict:
    return {"n": r["number"], "t": r["title"], "add": r["additions"], "del": r["deletions"],
            "net": r["additions"] - r["deletions"], "mergeSha": (r.get("mergeCommit") or {}).get("oid")}

def fetch_merged_prs(limit: int, contract: int) -> list[dict]:
    """Two-phase, mirroring how this contract was measured: one cheap list call
    for `limit` PRs, then per-file detail only for the subset whose PR-level net
    already exceeds contract (the rest need no classification)."""
    raw = _gh_json(["pr", "list", "--state", "merged", "--limit", str(limit),
                     "--json", "number,additions,deletions,title,mergedAt,mergeCommit"])
    prs = []
    for r in raw:
        pr = _pr_shell(r)
        pr["files"] = fetch_pr_files(pr["n"]) if pr["net"] > contract else []
        prs.append(pr)
    return prs

def fetch_single_pr(number: int) -> dict:
    r = _gh_json(["pr", "view", str(number),
                  "--json", "number,additions,deletions,title,mergedAt,mergeCommit"])
    pr = _pr_shell(r)
    pr["files"] = fetch_pr_files(number)
    return pr

def _pr_from_fixture(fixture: dict, number: int) -> dict:
    for pr in fixture["prs"]:
        if pr["n"] == number:
            return pr
    raise KeyError(f"PR #{number} not found in fixture")

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Advisory PR-size taxonomy (report-only).")
    ap.add_argument("--limit", type=int, default=100, help="how many recent merged PRs to examine")
    ap.add_argument("--contract", type=int, default=CONTRACT_DEFAULT, help="net-line contract threshold")
    ap.add_argument("--fixture", type=Path, default=None,
                     help="JSON {'prs': [...]} — bypasses gh entirely (tests / offline reproduction)")
    ap.add_argument("--explain", type=int, default=None, metavar="PR",
                     help="print full per-file classification for one PR")
    ap.add_argument("--probe-generated", action="store_true",
                     help="best-effort content-marker check for `generated` (needs local git objects)")
    ap.add_argument("--json", type=Path, default=None, help="write the full report as JSON")
    ap.add_argument("--md", type=Path, default=None, help="write the report as markdown")
    args = ap.parse_args(argv)

    fixture = json.loads(args.fixture.read_text()) if args.fixture else None
    if args.explain is not None:
        pr = _pr_from_fixture(fixture, args.explain) if fixture else fetch_single_pr(args.explain)
        print(render_explain(pr_verdict(pr, args.contract, args.probe_generated)))
        return 0

    prs = fixture["prs"] if fixture else fetch_merged_prs(args.limit, args.contract)
    report = build_report(prs, args.contract, args.probe_generated)
    md = render_markdown(report)
    print(md)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
    if args.md:
        args.md.write_text(md)
    return 0

if __name__ == "__main__":
    sys.exit(main())
