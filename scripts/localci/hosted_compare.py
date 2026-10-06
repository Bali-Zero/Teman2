#!/usr/bin/env python3
"""Read-only comparator: a local-CI ``status.json`` beside the HOSTED gate for the same commit.

For every context branch protection requires LIVE, it joins the hosted verdict (check runs and
commit statuses of the run's candidate sha) with the local per-context verdict and names the pair:

    AGREE           both green, or both red
    FALSE_GREEN     local green, hosted red — the one class that makes a local PASS a lie
    FALSE_RED       local red, hosted green
    LOCAL_BLIND     hosted has a verdict, local has none (BLOCKED / UNCOVERED / unmapped)
    HOSTED_PENDING  hosted has no complete verdict from the required source — nothing to compare

The hosted verdict of a context is order-free and RED-DOMINANT: red if ANY entry GitHub lists
under that name for the commit is red (the latest attempt of each check; a red that a re-run
replaced is not listed) (GitHub requires a same-named check and status to both pass, and a
later green from another event does not erase a red); green only when at least one entry from
the REQUIRED source (the pinned ``app_id``, or any source when none is pinned) is complete and
none is pending. No timestamp is compared.

It also reports DRIFT between the live required names and the names the local run was planned
with, and which required contexts pin no source app. Every GitHub call is a GET through
``gh api <path>``: this module posts nothing and needs no arming. ``--fixtures`` replays a saved
``{"repo", "branch", "sha", "required_checks", "check_runs", "statuses"}`` document offline; a
document for another repo, branch or commit is refused.

Exit 0 = compared, complete · 1 = a FALSE_GREEN or name drift · 2 = unusable input ·
3 = incomplete (a required context is still HOSTED_PENDING: not known yet, never "no failure").
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_BRANCH = "main"
CLASSES = ("AGREE", "FALSE_GREEN", "FALSE_RED", "LOCAL_BLIND", "HOSTED_PENDING")
# skipped/neutral satisfy a required check on GitHub, so they are green FOR THE GATE; the raw conclusions stay in the row.
HOSTED_GREEN = frozenset({"success", "skipped", "neutral"})
HOSTED_RED = frozenset({"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale", "error"})
MAX_PAGES = 20

EXIT_OK = 0
EXIT_FOUND = 1
EXIT_BAD_INPUT = 2
EXIT_INCOMPLETE = 3

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


class CompareError(ValueError):
    """The inputs cannot be compared — refuse rather than print a table that looks like evidence."""


def _verdict(conclusion) -> str:
    return "GREEN" if conclusion in HOSTED_GREEN else "RED" if conclusion in HOSTED_RED else "PENDING"


def hosted_entries(check_runs: list, statuses: list) -> dict:
    """Every hosted entry on the commit, grouped by context name (nothing is dropped or ordered)."""
    by: dict = {}
    for run in check_runs:
        concl = run.get("conclusion") if run.get("status") == "completed" else None
        app = run.get("app") if isinstance(run.get("app"), dict) else {}
        by.setdefault(run.get("name"), []).append({"verdict": _verdict(concl), "conclusion": concl, "app_id": app.get("id"),
                                                   "source": app.get("slug") or "check-run"})
    for st in statuses:
        state = st.get("state")
        by.setdefault(st.get("context"), []).append({"verdict": _verdict(None if state == "pending" else state), "conclusion": state,
                                                     "app_id": None, "source": "commit-status"})
    return by


def is_pinned(app_id) -> bool:
    return isinstance(app_id, int) and not isinstance(app_id, bool) and app_id > 0


def hosted_verdict(entries: list, app_id) -> dict:
    counted = [e for e in entries if not is_pinned(app_id) or e["app_id"] == app_id]
    if any(e["verdict"] == "RED" for e in entries):
        verdict = "RED"
    elif not counted or any(e["verdict"] == "PENDING" for e in counted):
        verdict = "PENDING"
    else:
        verdict = "GREEN"
    return {"verdict": verdict, "entries": len(entries), "counted": len(counted), "sources": sorted({e["source"] for e in entries}),
            "conclusions": sorted({str(e["conclusion"]) for e in entries})}


def local_verdicts(status: dict) -> dict:
    """GREEN / RED only where the runner recorded a per-context verdict; everything else is BLIND."""
    ctx = status.get("contexts")
    ctx = ctx if isinstance(ctx, dict) else {}
    results = ctx.get("results")
    results = results if isinstance(results, dict) else {}
    usable = ctx.get("status") == "ok"
    out = {}
    for name, res in results.items():
        res = res if isinstance(res, dict) else {}
        verdict = res.get("verdict")
        out[name] = {"verdict": ("GREEN" if verdict == "OK" else "RED" if verdict == "FAIL" else "BLIND") if usable else "BLIND",
                     "detail": f"{verdict}" + (f" ({res.get('mapping')})" if res.get("mapping") else "")}
    return out


def classify(local: str, hosted: str) -> str:
    if hosted == "PENDING":
        return "HOSTED_PENDING"
    if local == "BLIND":
        return "LOCAL_BLIND"
    if local == hosted:
        return "AGREE"
    return "FALSE_GREEN" if local == "GREEN" else "FALSE_RED"


def required_names(required_checks) -> list[str]:
    if not isinstance(required_checks, list) or not required_checks:
        raise CompareError("no required checks were read — an empty required set is a failed read, not a clean gate")
    names = [c.get("context") if isinstance(c, dict) else None for c in required_checks]
    if any(not isinstance(n, str) or not n.strip() for n in names):
        raise CompareError("a required check has no context name — refusing to skip it")
    if len(set(names)) != len(names):
        raise CompareError("the required set names a context twice")
    return names  # type: ignore[return-value]


def compare(status: dict, required_checks, check_runs, statuses) -> dict:
    names = required_names(required_checks)
    if not isinstance(check_runs, list) or not isinstance(statuses, list) or any(not isinstance(x, dict) for x in check_runs + statuses):
        raise CompareError("check_runs / statuses are not lists of objects")
    hosted, local = hosted_entries(check_runs, statuses), local_verdicts(status)
    rows = []
    for chk in required_checks:
        name, app_id = chk["context"], chk.get("app_id")
        h = hosted_verdict(hosted.get(name, []), app_id)
        lo = local.get(name, {"verdict": "BLIND", "detail": "unmapped"})
        rows.append({"context": name, "class": classify(lo["verdict"], h["verdict"]), "hosted": h["verdict"], "hosted_entries": h["entries"],
                     "hosted_counted": h["counted"], "hosted_sources": h["sources"], "hosted_conclusions": h["conclusions"],
                     "local": lo["verdict"], "local_detail": lo["detail"], "app_id": app_id, "source_pinned": is_pinned(app_id)})
    counts = {k: sum(1 for r in rows if r["class"] == k) for k in CLASSES}
    return {"candidate_sha": status.get("candidate_sha"), "run_id": status.get("run_id"), "local_overall": status.get("overall"),
            "required": len(rows), "rows": rows, "counts": counts, "agreement": f"{counts['AGREE']}/{len(rows)}",
            "drift": {"missing_locally": sorted(n for n in names if n not in local), "stale_locally": sorted(n for n in local if n not in names)},
            "unpinned_source": [r["context"] for r in rows if not r["source_pinned"]]}


def exit_code(report: dict) -> int:
    if report["counts"]["FALSE_GREEN"] or report["drift"]["missing_locally"] or report["drift"]["stale_locally"]:
        return EXIT_FOUND
    return EXIT_INCOMPLETE if report["counts"]["HOSTED_PENDING"] else EXIT_OK


def gh_argv(path: str) -> list[str]:
    return ["gh", "api", path]


def gh_get(path: str):
    res = subprocess.run(gh_argv(path), capture_output=True, text=True)
    if res.returncode != 0:
        raise CompareError(f"gh api {path} failed (rc={res.returncode}): {res.stderr.strip()[-200:]}")
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise CompareError(f"gh api {path} returned no JSON: {exc}") from exc


def _paged(path: str, key: str) -> list:
    out: list = []
    for page in range(1, MAX_PAGES + 1):
        doc = gh_get(f"{path}?per_page=100&page={page}")
        batch = doc.get(key) if isinstance(doc, dict) else None
        if not isinstance(batch, list):
            raise CompareError(f"gh api {path}: page {page} carries no `{key}` list")
        out += batch
        if len(batch) < 100:
            return out
    raise CompareError(f"gh api {path}: more than {MAX_PAGES} pages of `{key}` — refusing a truncated comparison")


def fetch_live(repo: str, branch: str, sha: str) -> dict:
    protection = gh_get(f"repos/{repo}/branches/{branch}/protection/required_status_checks")
    return {"repo": repo, "branch": branch, "sha": sha, "required_checks": protection.get("checks") if isinstance(protection, dict) else None,
            "check_runs": _paged(f"repos/{repo}/commits/{sha}/check-runs", "check_runs"),
            "statuses": _paged(f"repos/{repo}/commits/{sha}/status", "statuses")}


def bound_to(live, repo: str, branch: str, sha: str) -> dict:
    """A hosted document counts only for the repo, branch and commit it says it was read from."""
    if not isinstance(live, dict):
        raise CompareError("the hosted document is not a JSON object")
    for key, want in (("repo", repo), ("branch", branch), ("sha", sha)):
        if live.get(key) != want:
            raise CompareError(f"the hosted document is bound to {key}={live.get(key)!r}, this comparison needs {want!r}")
    runs = live.get("check_runs")
    if isinstance(runs, list) and any(isinstance(r, dict) and r.get("head_sha") not in (None, sha) for r in runs):
        raise CompareError("a check run in the hosted document belongs to another commit")
    return live


def render(report: dict) -> str:
    lines = [f"{'CLASS':15} {'HOSTED':10} {'LOCAL':6} {'PIN':4} CONTEXT"]
    for r in report["rows"]:
        hosted = f"{r['hosted']}({r['hosted_entries']})"
        lines.append(f"{r['class']:15} {hosted:10} {r['local']:6} {'app' if r['source_pinned'] else 'any':4} {r['context']}  [{r['local_detail']}]")
    c, d = report["counts"], report["drift"]
    lines.append(f"source={report['source']} sha={str(report['candidate_sha'])[:12]} local_overall={report['local_overall']} "
                 f"required={report['required']} agreement={report['agreement']} " + " ".join(f"{k.lower()}={c[k]}" for k in CLASSES[1:]))
    lines.append(f"drift: missing_locally={d['missing_locally']} stale_locally={d['stale_locally']} | "
                 f"unpinned_source={len(report['unpinned_source'])}/{report['required']}")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Read-only comparator: a local-CI status.json beside the hosted gate for the same commit.")
    ap.add_argument("status", type=Path, help="path to a local-CI status.json")
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default {DEFAULT_REPO})")
    ap.add_argument("--branch", default=DEFAULT_BRANCH, help=f"protected branch whose required set is read (default {DEFAULT_BRANCH})")
    ap.add_argument("--fixtures", type=Path, default=None, help="replay a saved hosted document (bound to repo, branch and sha) instead of calling gh")
    ap.add_argument("--out", type=Path, default=None, help="directory for hosted_compare.json (default: the status.json's directory)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        status = json.loads(args.status.read_text())
        if not isinstance(status, dict):
            raise CompareError("status.json is not a JSON object")
        sha = status.get("candidate_sha")
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            raise CompareError("candidate_sha is missing or not a full 40-hex sha")
        if not _REPO_RE.match(args.repo) or not _BRANCH_RE.match(args.branch):
            raise CompareError(f"repo {args.repo!r} / branch {args.branch!r} is not a plain owner/name and branch")
        live = json.loads(args.fixtures.read_text()) if args.fixtures else fetch_live(args.repo, args.branch, sha)
        live = bound_to(live, args.repo, args.branch, sha)
        report = compare(status, live.get("required_checks"), live.get("check_runs"), live.get("statuses"))
    except (OSError, json.JSONDecodeError, CompareError) as exc:
        print(f"hosted_compare: refusing — {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    report.update(source="fixtures" if args.fixtures else "live", repo=args.repo, branch=args.branch)
    out_dir = args.out if args.out is not None else args.status.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "hosted_compare.json").write_text(json.dumps(report, indent=2) + "\n")
    print(render(report))
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
