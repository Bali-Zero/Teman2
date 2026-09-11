#!/usr/bin/env python3
"""snapshot_required_contexts.py — regenerate infra/required.d/contexts.json.

WHY THIS EXISTS (Merge-OS v2 Wave 0, spec §4 "required.d snapshot (advisory)":
research/operations/2026-08-10-merge-os-v2-submission-system.md). The live
branch-protection required-status-check list is authoritative but invisible
to a PR diff — nothing in the repo could previously say, in a reviewable
text file, "these are the 27 contexts main requires, and this is which
workflow file produces each one." infra/required.d/contexts.json is that
snapshot: ADVISORY (a data file other tools read — right now
scripts/ci/check_required_workflow_conformance.py), never authoritative.
Drift between this file and the live branch-protection API is EXPECTED
(someone adds/removes a required check via GitHub Settings, or a workflow
job is renamed) and is cured by re-running this script, never by hand-
editing the JSON.

SOURCE OF TRUTH, TWO TIERS:
  1. `gh api repos/<owner>/<repo>/branches/<branch>/protection/required_status_checks`
     — the classic branch-protection contexts endpoint. This is what main
     actually enforces (verified live 2026-08-10: 27 contexts, the
     `merge-queue-main` ruleset id 19779175 governs queue MECHANICS —
     grouping/batching — not the required-context list itself, which still
     lives on branches/main/protection). `source: "api"` when this succeeds.
  2. Fallback — `gh pr checks <PR>` on a recent MERGED pr — used only if the
     API call is denied (some tokens can read a repo's workflows but not its
     branch-protection settings). `source: "derived"` in that case, and the
     PR number used is recorded, because a derived list is a snapshot of
     "checks that ran on one PR," not a verified requirement list — the
     conformance guard and any human reading this file need to know which
     kind of ground truth they are trusting.

WORKFLOW RESOLUTION: scripts/ci/required_context_map.py (shared with the
guard) maps each context name back to the `.github/workflows/*.yml` file +
job id that reports it, by parsing every workflow's `jobs:` (+ matrix
expansion). A context with zero or more-than-one matching job is recorded
with `workflow_file: null` and a `resolution` note — this is the allowlist
path: `scripts/ci/check_required_workflow_conformance.py` requires a
`reason` for any such entry before it will accept it as "not workflow-
produced" rather than "the mapper's most likely explanation is a bug."

Usage:
    python3 scripts/ci/snapshot_required_contexts.py [--branch main] [--out infra/required.d/contexts.json]

No mutation of GitHub state — read-only `gh api`/`gh pr checks` calls only.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from required_context_map import resolve  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = REPO_ROOT / "infra" / "required.d" / "contexts.json"


def _gh(args: list[str]) -> str | None:
    try:
        out = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def repo_slug() -> str:
    out = _gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if not out or not out.strip():
        print("FATAL: could not resolve repo slug via `gh repo view`", file=sys.stderr)
        sys.exit(2)
    return out.strip()


def fetch_via_api(repo: str, branch: str) -> list[dict] | None:
    out = _gh(
        [
            "api",
            f"repos/{repo}/branches/{branch}/protection/required_status_checks",
        ]
    )
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    checks = data.get("checks")
    if not isinstance(checks, list):
        return None
    return [{"name": c.get("context"), "app_id": c.get("app_id")} for c in checks if c.get("context")]


def fetch_via_derived_pr(repo: str, pr_number: str) -> list[dict] | None:
    out = _gh(["pr", "checks", pr_number, "--repo", repo, "--json", "name"])
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return [{"name": row.get("name"), "app_id": None} for row in data if row.get("name")]


def build_snapshot(branch: str, derived_pr: str | None) -> dict:
    repo = repo_slug()
    source = "api"
    checks = fetch_via_api(repo, branch)
    if checks is None:
        if not derived_pr:
            print(
                "FATAL: branch-protection API denied and no --derived-from-pr given — "
                "refusing to write a blind-empty snapshot (W84)",
                file=sys.stderr,
            )
            sys.exit(2)
        source = "derived"
        checks = fetch_via_derived_pr(repo, derived_pr)
        if checks is None:
            print(f"FATAL: could not derive contexts from PR #{derived_pr} either", file=sys.stderr)
            sys.exit(2)

    contexts = []
    for c in sorted(checks, key=lambda x: x["name"]):
        match = resolve(c["name"])
        entry = {
            "name": c["name"],
            "app_id": c.get("app_id"),
        }
        if match:
            entry["workflow_file"] = f".github/workflows/{match[0]}"
            entry["job_id"] = match[1]
        else:
            entry["workflow_file"] = None
            entry["allowlist_reason"] = (
                "UNRESOLVED by scripts/ci/required_context_map.py — either a genuinely "
                "external check (Vercel, GitHub-native code scanning not backed by a "
                "workflow file in this repo, a required Copilot review, ...) or the "
                "mapper needs a fix. Do not leave this placeholder in place without "
                "checking which one it is."
            )
        contexts.append(entry)

    return {
        "_doc": (
            "Advisory snapshot of main's required-status-check contexts (Merge-OS v2 "
            "Wave 0, research/operations/2026-08-10-merge-os-v2-submission-system.md "
            "§4). Read by scripts/ci/check_required_workflow_conformance.py. Drift vs "
            "live branch protection is expected and cured by REGEN, never hand-edit — "
            "see regen_command below."
        ),
        "generated_at": datetime.date.today().isoformat(),
        "source": source,
        "derived_from_pr": derived_pr if source == "derived" else None,
        "repo": repo,
        "branch": branch,
        "regen_command": (
            "python3 scripts/ci/snapshot_required_contexts.py "
            f"--branch {branch} --out infra/required.d/contexts.json"
        ),
        "contexts": contexts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--derived-from-pr",
        default=None,
        help="Fallback PR number to derive the context list from if the branch-"
        "protection API call is denied.",
    )
    args = parser.parse_args()

    snapshot = build_snapshot(args.branch, args.derived_from_pr)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    unresolved = [c["name"] for c in snapshot["contexts"] if c["workflow_file"] is None]
    print(f"wrote {out_path} — {len(snapshot['contexts'])} contexts, source={snapshot['source']}")
    if unresolved:
        print(f"  {len(unresolved)} UNRESOLVED (need a workflow_file or a real allowlist reason):")
        for name in unresolved:
            print(f"    - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
