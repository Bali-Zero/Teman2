#!/usr/bin/env python3
"""MEASURE-ONLY weekly coverage report for the `tests.yml` change-map gate.

Over a rolling window (default 7 days) of `tests.yml` `merge_group` and
`pull_request` runs: how often did `scripts/ci/change_map.py` classify
cleanly, how often did each heavy suite skip, and — the interesting
question — how often did a suite RUN when the classifier's own domain
routing (`_suggested_jobs`) would not have selected it, because the run fell
back to `run_all` for a non-domain reason? That corpus is "the allowlist
could safely be narrower here" evidence, not a proposal to narrow it. This
script changes no allowlist, workflow file, or classifier rule; it only
reads `gh run`/`gh api` output and reports. CI metadata only (run ids, job
conclusions, PR numbers from the public merge-queue branch name, the
classifier's own domains/reason/paths) — no client data or PII ever.

Structure: fetch_* is the only side-effecting code (subprocess -> gh CLI,
on-disk cache); analyze_*/render_* are pure (fixture-testable, see
test_change_map_coverage.py). JOB_TRIGGER_DOMAINS is derived by CALLING the
real `change_map._suggested_jobs` per domain (not hand-copied), so this
module cannot silently drift from the classifier it measures.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_map as cm  # noqa: E402  (path insert above must run first)

REPO = os.environ.get("CHANGE_MAP_COVERAGE_REPO", "Bali-Zero/Teman2")
WORKFLOW = "tests.yml"
DEFAULT_DAYS = 7
MAX_WORKERS = 8
RETRIES = 1  # one retry on top of the first attempt, per task instruction

CACHE_ROOT = Path(os.environ.get("TMPDIR", "/tmp")) / "change_map_coverage"

REPO_ROOT = Path(__file__).resolve().parents[2]

# The six required heavy jobs by their tests.yml `name:` (verified 2026-09-10).
# frontend-tests is a matrix; only the required `mouth` leg is tracked here.
HEAVY_JOBS: tuple[str, ...] = (
    "Backend Tests (Python)",
    "E2E Tests (Playwright)",
    "MCP Server Tests",
    "Evaluator Critical Tests",
    "Shared Core Package Tests",
    "Frontend Tests (Next.js) (mouth, true)",
)

# change_map.TEST_JOBS slug -> the HEAVY_JOBS name it gates (verified 2026-09-10).
SLUG_TO_JOB_NAME: dict[str, str] = {
    "backend-tests": "Backend Tests (Python)",
    "mcp-tests": "MCP Server Tests",
    "evaluator-critical-tests": "Evaluator Critical Tests",
    "frontend-tests": "Frontend Tests (Next.js) (mouth, true)",
    "packages-core-tests": "Shared Core Package Tests",
    "e2e-tests": "E2E Tests (Playwright)",
}

# Reasons change_map.py::classify() emits. Fallback reasons the *workflow*
# emits (manual_override_disabled/classifier_runtime_failure) and "unreadable"
# (this script found no verdict) are tracked separately — see reason_counts().
CLASSIFY_REASONS: tuple[str, ...] = (
    "classified",
    "unclassified_paths",
    "enumeration_failed",
    "empty_changed_set",
)
FAIL_OPEN_REASONS = frozenset({"unclassified_paths", "enumeration_failed", "empty_changed_set"})

PR_BRANCH_RE = re.compile(r"^gh-readonly-queue/main/pr-(\d+)-")
NOTICE_RE = re.compile(r"##\[notice\]change-map:\s*(\{.*\})\s*$")

SKIPPED_CONCLUSIONS = frozenset({"skipped"})


def _job_trigger_domains() -> dict[str, frozenset[str]]:
    """Domains that ALONE (run_all=False) make change_map._suggested_jobs
    select each HEAVY_JOBS name — called per-domain rather than hand-copied,
    so this cannot drift from change_map.py's actual routing. `infra_workflows`
    is excluded here: it forces every job by design, and is its own bucket in
    legitimate_domain_counts() instead of a per-job trigger."""

    triggers: dict[str, set[str]] = {slug: set() for slug in cm.TEST_JOBS}
    for domain in cm.DOMAIN_NAMES:
        if domain == "infra_workflows":
            continue
        for slug in cm._suggested_jobs({domain}, run_all=False):
            triggers[slug].add(domain)
    return {SLUG_TO_JOB_NAME[slug]: frozenset(d) for slug, d in triggers.items()}


JOB_TRIGGER_DOMAINS: dict[str, frozenset[str]] = _job_trigger_domains()


# Fetch layer — the ONLY side-effecting code in this module.


def _run_gh(args: list[str], timeout: int = 60) -> tuple[bool, str, str]:
    """Run `gh`, retrying once on failure. Returns (ok, stdout, err); never raises."""

    err = ""
    for attempt in range(RETRIES + 1):
        try:
            proc = subprocess.run(
                ["gh", *args], capture_output=True, text=True, timeout=timeout
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            err = f"{type(exc).__name__}: {exc}"
            continue
        if proc.returncode == 0:
            return True, proc.stdout, ""
        err = proc.stderr.strip()[:500] or f"gh exited {proc.returncode}"
    return False, "", err


def _cache_path(kind: str, event: str, run_id: int) -> Path:
    return CACHE_ROOT / f"{kind}_{event}_{run_id}.json"


def _cache_read(path: Path) -> dict[str, Any] | None:
    try:
        with path.open() as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _cache_write(path: Path, data: dict[str, Any]) -> None:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as fh:
        json.dump(data, fh)
    tmp.replace(path)


def fetch_run_list(event: str, days: int, repo: str = REPO) -> tuple[list[dict[str, Any]], str | None]:
    """Not cached: the 7-day window shifts daily. Only per-run lookups below are
    cached (keyed by run id), since a concluded run's own data never changes."""

    since = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ok, out, err = _run_gh(
        [
            "run", "list",
            "--repo", repo,
            "--workflow", WORKFLOW,
            "--event", event,
            "--created", f">={since}",
            "--json", "databaseId,conclusion,createdAt,headBranch,headSha",
            "--limit", "1500",
        ],
        timeout=90,
    )
    if not ok:
        return [], err
    try:
        return json.loads(out), None
    except json.JSONDecodeError as exc:
        return [], f"json decode: {exc}"


def fetch_jobs_for_run(event: str, run_id: int, repo: str = REPO) -> dict[str, Any]:
    path = _cache_path("jobs", event, run_id)
    cached = _cache_read(path)
    if cached is not None and cached.get("ok"):
        return cached
    ok, out, err = _run_gh(["run", "view", str(run_id), "--repo", repo, "--json", "jobs"])
    if not ok:
        data = {"ok": False, "err": err}
    else:
        try:
            data = {"ok": True, "jobs": json.loads(out).get("jobs", [])}
        except json.JSONDecodeError as exc:
            data = {"ok": False, "err": f"json decode: {exc}"}
    _cache_write(path, data)
    return data


def _find_change_map_job_id(jobs: list[dict[str, Any]]) -> int | None:
    for job in jobs:
        if job.get("name") == "Change map":
            return job.get("databaseId")
    return None


def fetch_classifier_for_run(
    event: str, run_id: int, job_id: int, repo: str = REPO
) -> dict[str, Any]:
    path = _cache_path("cm", event, run_id)
    cached = _cache_read(path)
    if cached is not None and cached.get("ok"):
        return cached
    ok, out, err = _run_gh(
        ["api", f"repos/{repo}/actions/jobs/{job_id}/logs", "--allow-escape-sequences"]
    )
    if not ok:
        data = {"ok": False, "err": err}
    else:
        match_json = None
        for line in out.splitlines():
            m = NOTICE_RE.search(line)
            if m:
                match_json = m.group(1)
        if match_json is None:
            # Expected, not a bug: the notice only fires when "Enumerate and
            # classify" actually runs — a manual-override run has none.
            data = {"ok": False, "err": "no notice line found"}
        else:
            try:
                data = {"ok": True, "classifier": json.loads(match_json)}
            except json.JSONDecodeError as exc:
                data = {"ok": False, "err": f"parse fail: {exc}"}
    _cache_write(path, data)
    return data


def _pr_number_from_branch(head_branch: str | None) -> int | None:
    if not head_branch:
        return None
    m = PR_BRANCH_RE.match(head_branch)
    return int(m.group(1)) if m else None


def build_batch_record(
    event: str, run: dict[str, Any], jobs_data: dict[str, Any], cm_data: dict[str, Any] | None
) -> dict[str, Any]:
    """Pure: the canonical per-batch shape every analyze_* function consumes."""

    run_id = run["databaseId"]
    record: dict[str, Any] = {
        "run_id": run_id,
        "conclusion": run.get("conclusion"),
        "created_at": run.get("createdAt"),
        "pr_number": _pr_number_from_branch(run.get("headBranch")),
        "jobs_ok": bool(jobs_data.get("ok")),
        "job_conclusions": {},
        "classifier_ok": bool(cm_data and cm_data.get("ok")),
        "classifier": (cm_data or {}).get("classifier"),
    }
    if record["jobs_ok"]:
        jobmap = {j["name"]: j.get("conclusion") for j in jobs_data.get("jobs", [])}
        record["job_conclusions"] = {name: jobmap.get(name) for name in HEAVY_JOBS}
    return record


def fetch_all(
    event: str, days: int, repo: str = REPO, max_workers: int = MAX_WORKERS
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """List runs, then fetch jobs + classifier for each in a bounded thread
    pool. Returns (records, fetch_stats)."""

    runs, list_err = fetch_run_list(event, days, repo)
    stats: dict[str, Any] = {
        "runs_total": len(runs),
        "list_err": list_err,
        "jobs_unreadable": 0,
        "classifier_unreadable": 0,
    }
    if not runs:
        return [], stats

    def _one(run: dict[str, Any]) -> dict[str, Any]:
        run_id = run["databaseId"]
        jobs_data = fetch_jobs_for_run(event, run_id, repo)
        cm_data = None
        if jobs_data.get("ok"):
            job_id = _find_change_map_job_id(jobs_data.get("jobs", []))
            if job_id is not None:
                cm_data = fetch_classifier_for_run(event, run_id, job_id, repo)
        return build_batch_record(event, run, jobs_data, cm_data)

    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for record in pool.map(_one, runs):
            records.append(record)

    stats["jobs_unreadable"] = sum(1 for r in records if not r["jobs_ok"])
    stats["classifier_unreadable"] = sum(1 for r in records if not r["classifier_ok"])
    return records, stats


# Analysis layer — pure. Every function here takes only plain dicts/lists.


def reason_counts(records: list[dict[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for r in records:
        if not r["classifier_ok"]:
            counts["unreadable"] += 1
            continue
        reason = r["classifier"].get("reason", "unreadable")
        counts[reason] += 1
    return counts


def job_stats(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for job in HEAVY_JOBS:
        present = 0
        skipped = 0
        for r in records:
            if not r["jobs_ok"]:
                continue
            concl = r["job_conclusions"].get(job)
            if concl is None:
                continue
            present += 1
            if concl in SKIPPED_CONCLUSIONS:
                skipped += 1
        pct = (skipped / present * 100) if present else 0.0
        stats[job] = {"runs": present, "skipped": skipped, "skip_pct": pct}
    return stats


def _job_ran(conclusion: str | None) -> bool:
    return conclusion is not None and conclusion not in SKIPPED_CONCLUSIONS


def eligible_for_skip_but_ran(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batches where a heavy job RAN while `domains` held none of that job's
    JOB_TRIGGER_DOMAINS — it ran only because `reason` was fail-open, not
    because a domain it actually reads was touched."""

    out: list[dict[str, Any]] = []
    for r in records:
        if not (r["jobs_ok"] and r["classifier_ok"]):
            continue
        classifier = r["classifier"]
        reason = classifier.get("reason")
        if reason not in FAIL_OPEN_REASONS:
            continue
        domains = {d for d, present in classifier.get("domains", {}).items() if present}
        unknown_paths = classifier.get("unknown_paths", [])
        for job in HEAVY_JOBS:
            if not _job_ran(r["job_conclusions"].get(job)):
                continue
            if domains & JOB_TRIGGER_DOMAINS.get(job, frozenset()):
                continue  # would have run anyway on its own domain
            out.append(
                {
                    "run_id": r["run_id"],
                    "pr_number": r["pr_number"],
                    "job": job,
                    "reason": reason,
                    "unknown_paths": unknown_paths,
                }
            )
    return out


def unknown_path_frequency(
    eligible: list[dict[str, Any]], top_n: int = 25
) -> list[tuple[str, int, list[int]]]:
    """Frequency table of `unknown_paths` across eligible batches, each with
    the deduped, sorted PR numbers that carried it."""

    counts: Counter = Counter()
    prs: dict[str, set[int]] = {}
    for item in eligible:
        for path in item["unknown_paths"]:
            counts[path] += 1
            if item["pr_number"] is not None:
                prs.setdefault(path, set()).add(item["pr_number"])
    ranked = counts.most_common(top_n)
    return [(path, count, sorted(prs.get(path, set()))) for path, count in ranked]


def legitimate_domain_counts(records: list[dict[str, Any]]) -> Counter:
    """For `reason == "classified"` batches, counts (job, domain) pairs where
    `domain` is why that job legitimately ran: `infra_workflows` (forces
    every job) or one of that job's own JOB_TRIGGER_DOMAINS."""

    counts: Counter = Counter()
    for r in records:
        if not (r["jobs_ok"] and r["classifier_ok"]):
            continue
        classifier = r["classifier"]
        if classifier.get("reason") != "classified":
            continue
        domains = {d for d, present in classifier.get("domains", {}).items() if present}
        for job in HEAVY_JOBS:
            if not _job_ran(r["job_conclusions"].get(job)):
                continue
            if "infra_workflows" in domains:
                counts[(job, "infra_workflows")] += 1
                continue
            for domain in domains & JOB_TRIGGER_DOMAINS.get(job, frozenset()):
                counts[(job, domain)] += 1
    return counts


# Rendering — pure (markdown text, no I/O).


def render_event_section(event: str, records: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    lines: list[str] = []
    label = {"merge_group": "merge_group (post-merge-queue)", "pull_request": "pull_request (pre-merge)"}.get(
        event, event
    )
    lines.append(f"## `{event}` runs — {label}")
    lines.append("")
    lines.append(f"- Total batches fetched: **{stats['runs_total']}**")
    if stats.get("list_err"):
        lines.append(f"- `gh run list` error: `{stats['list_err']}`")
    lines.append(f"- Jobs unreadable: **{stats['jobs_unreadable']}**")
    lines.append(f"- Classifier unreadable (no/garbled notice line): **{stats['classifier_unreadable']}**")
    lines.append("")

    lines.append("### 1. Batches per classifier reason")
    lines.append("")
    lines.append("| reason | batches |")
    lines.append("|---|---|")
    counts = reason_counts(records)
    for reason in CLASSIFY_REASONS:
        lines.append(f"| `{reason}` | {counts.get(reason, 0)} |")
    other = {k: v for k, v in counts.items() if k not in CLASSIFY_REASONS}
    for reason, n in sorted(other.items()):
        lines.append(f"| `{reason}` | {n} |")
    lines.append("")

    lines.append("### 2. Per heavy job: runs / skipped / skip %")
    lines.append("")
    lines.append("| job | runs | skipped | skip % |")
    lines.append("|---|---|---|---|")
    jstats = job_stats(records)
    for job in HEAVY_JOBS:
        s = jstats[job]
        lines.append(f"| {job} | {s['runs']} | {s['skipped']} | {s['skip_pct']:.1f}% |")
    lines.append("")

    lines.append("### 3. Eligible for a skip that did not skip")
    lines.append("")
    eligible = eligible_for_skip_but_ran(records)
    by_job: Counter = Counter(item["job"] for item in eligible)
    lines.append("| job | batches eligible-for-skip-but-ran |")
    lines.append("|---|---|")
    for job in HEAVY_JOBS:
        lines.append(f"| {job} | {by_job.get(job, 0)} |")
    lines.append("")
    lines.append("Top unclassified/fail-open paths that kept these batches in the full battery:")
    lines.append("")
    lines.append("| path | count | PRs |")
    lines.append("|---|---|---|")
    for path, count, prs in unknown_path_frequency(eligible):
        pr_txt = ", ".join(f"#{n}" for n in prs) if prs else "(no PR number resolved)"
        lines.append(f"| `{path}` | {count} | {pr_txt} |")
    if not eligible:
        lines.append("| _(none — every batch that ran a heavy job had a classified domain match)_ | | |")
    lines.append("")

    lines.append("### 4. Domains that legitimately forced each suite")
    lines.append("")
    lines.append("| job | domain | batches |")
    lines.append("|---|---|---|")
    dom_counts = legitimate_domain_counts(records)
    for (job, domain), n in sorted(dom_counts.items(), key=lambda kv: (kv[0][0], -kv[1])):
        lines.append(f"| {job} | `{domain}` | {n} |")
    if not dom_counts:
        lines.append("| _(none)_ | | |")
    lines.append("")
    return "\n".join(lines)


def render_report(all_data: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]], days: int) -> str:
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Change-map coverage report (measure-only)",
        "",
        f"Generated {generated} · window: last {days} days · workflow: `tests.yml` · repo: `{REPO}`.",
        "",
        "This report is **measure-only**: it changes no allowlist, no workflow file, and no "
        "classifier rule in `scripts/ci/change_map.py`. It exists to make the change-map gate's "
        "actual behavior visible — see `docs/reports/change-map-coverage/README.md`.",
        "",
    ]
    for event in ("merge_group", "pull_request"):
        records, stats = all_data[event]
        lines.append(render_event_section(event, records, stats))
    return "\n".join(lines)


def render_mail_summary(all_data: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]], report_path: str) -> str:
    parts = [f"change-map-coverage: weekly report ({report_path})"]
    for event in ("merge_group", "pull_request"):
        records, stats = all_data[event]
        eligible = eligible_for_skip_but_ran(records)
        parts.append(
            f"{event}: {stats['runs_total']} batches, "
            f"{stats['classifier_unreadable']} unreadable, "
            f"{len(eligible)} eligible-for-skip-but-ran"
        )
    return " | ".join(parts)


# Mail delivery — reuses scripts/fleet_mail.sh exactly (same argv shape,
# same missing-file/non-zero-rc handling as queue_stall_notify.py::send_notification).

MAIL_KEY = "change-map-coverage:weekly"
MAIL_TTL_HOURS = int(os.environ.get("CHANGE_MAP_COVERAGE_MAIL_TTL_HOURS", "192"))  # 8 days > weekly cadence
MAIL_HOST = os.environ.get("CHANGE_MAP_COVERAGE_MAIL_HOST", "pro")


def send_mail(message: str, *, dry_run: bool, repo_root: Path = REPO_ROOT) -> tuple[bool, str]:
    if dry_run:
        return True, f"[dry-run] would fleet-mail {MAIL_HOST} broadcast --key {MAIL_KEY}: {message}"
    fleet_mail = repo_root / "scripts" / "fleet_mail.sh"
    if not fleet_mail.is_file():
        return False, f"fleet_mail.sh not found at {fleet_mail}"
    proc = subprocess.run(
        ["bash", str(fleet_mail), MAIL_HOST, "broadcast", "--key", MAIL_KEY, "--ttl", str(MAIL_TTL_HOURS), message],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        return False, f"fleet_mail FAILED rc={proc.returncode}: {proc.stderr.strip()[:300]}"
    return True, proc.stdout.strip() or "sent"


# main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2] if __doc__ else "")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    parser.add_argument(
        "--out",
        default=None,
        help="report file path (default: docs/reports/change-map-coverage/<YYYY-MM-DD>.md)",
    )
    parser.add_argument("--no-mail", action="store_true", help="skip the fleet-mail broadcast entirely")
    parser.add_argument(
        "--dry-run-mail", action="store_true", help="print what would be mailed without sending"
    )
    args = parser.parse_args(argv)

    all_data: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
    for event in ("merge_group", "pull_request"):
        records, stats = fetch_all(event, args.days, repo=args.repo, max_workers=args.max_workers)
        all_data[event] = (records, stats)

    report = render_report(all_data, args.days)
    print(report)

    out_path = Path(args.out) if args.out else (
        REPO_ROOT / "docs" / "reports" / "change-map-coverage"
        / f"{datetime.date.today().isoformat()}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report + "\n", encoding="utf-8")
    print(f"\n[written] {out_path}", file=sys.stderr)

    if not args.no_mail:
        summary = render_mail_summary(all_data, str(out_path.relative_to(REPO_ROOT)))
        ok, detail = send_mail(summary, dry_run=args.dry_run_mail)
        print(f"[mail] ok={ok}: {detail}", file=sys.stderr)
        if not ok and not args.dry_run_mail:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
