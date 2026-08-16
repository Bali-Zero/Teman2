#!/usr/bin/env python3
"""suite_growth_probe.py — Merge-OS v3 build-order step 3 slice 1 (MEASUREMENT ONLY).

Spec: research/operations/2026-08-14-merge-os-v3-research-council.md §6 step 3
"Suite-growth governance (the dominant lever, C1): ... rolling p50/p95 + slot-minutes
+ top-N-by-duration telemetry per lane with weekly delta and owner". This script is
the FIRST slice of that step: telemetry + an alarm on the derivative. It changes
NOTHING about how tests.yml jobs are gated, retried, or timed out — it only RECORDS
what already happened and, when the numbers cross a declared line, tells a human via
Telegram. No test selection, no auto-deletion, no gate-semantics change (§6 step 3's
own scope: "NO auto-deletion on slowness/flake alone").

WHY THIS EXISTS (§8 meta-pattern, restated concretely): the backend test suite's
median wall time grew from ~18 to ~29 minutes over five weeks (~+10%/week) while
`backend-tests.timeout-minutes` in tests.yml has stayed 30. When the median crosses
that ceiling, `Backend Tests (Python)` — a required check on `main` and `merge_group`
— starts reporting `cancelled`, not `failure` (the exact scar family #9 trap
`scripts/lint_workflow_timeout_floor.py` documents for `actions/checkout`, one layer
up the same job). A cancelled required check never turns green by itself and the
merge queue jams with nothing red to fix. Nothing in this repo measured or alarmed
on that derivative before this script existed (scar family #2 "esiste != armato" —
the growth was happening in full view of seven weeks of CI logs and no organ read
them as a trend).

Invoked nightly (Pro) by infra/launchagents/wrappers/suite-growth-probe.sh via the
(NOT-YET-ARMED — W81, built != armed) com.nuzantara.suite-growth-probe.plist.template.
Writes one record per invocation to `~/.nuzantara-mq/suite-growth/<date>.json`
(`--out-dir` overridable).

WHAT IS MEASURED, per job of `--workflow` (default tests.yml), over the last
`--window-days` (default 7) days of *completed* runs whose event is `push` (with
`head_branch == main`, so `develop` pushes and PR-triggered runs are excluded) or
`merge_group` — the two events step 2's own council doc names as this repo's real
gate load, distinct from the 2-hourly `schedule` run (§6 step 2's own subject: that
schedule is a documented independent health probe, not gate load):

  1. Per-job wall time (job `completed_at` - `started_at`, GitHub Actions Jobs API),
     bucketed into a CURRENT window (`now - window_days .. now`) and a PREVIOUS
     window (`now - 2*window_days .. now - window_days`) — p50/p95 each, computed by
     the same dependency-free linear-interpolation percentile() this repo's
     queue_baseline_probe.py already uses (numpy 'linear' method), duplicated here
     rather than imported: scripts/ is a flat bag of standalone tools, not a package
     (see that module's own docstring / scripts/tests/test_queue_baseline_probe.py
     header for the same declared convention).
  2. Weekly trend: `(current_p50 - previous_p50) / previous_p50 * 100`. `None` when
     the previous window has no sample (first week this organ runs, or a job that
     did not exist 7-14 days ago) — never coerced to 0.0, which would silently claim
     "measured, and it was flat".
  3. Distance from timeout: `current_p95 / timeout_minutes * 100`, where
     `timeout_minutes` is read from `--workflow`'s own YAML (best-effort: this
     script tries `import yaml`; if PyYAML is unavailable the timeout is left
     `None` for every job and the gap is recorded in `errors[]`, never silently
     treated as "no timeout configured" — see `read_job_timeouts()`).
  4. Test file count: `find <repo-root>/apps/backend-rag/backend/tests -name
     'test_*.py'` equivalent (`Path.rglob`, no subprocess) — a correlate for the
     suite-growth trend, not itself alarmed on.

DECLARED LIMITATION (early-exit bias): `backend-tests`' own "Run unit tests" step
runs pytest with `-x` (stop at first failure). A run that fails early finishes
FASTER than a full pass, which can pull a window's p50 DOWN exactly when the suite
is least healthy. This script does not attempt to correct for that — it records
wall time for every `status == "completed"` job regardless of `conclusion`,
matching what the merge queue itself experiences (a cancelled-on-timeout job's
duration lands at/near the timeout ceiling, which is precisely the signal
`p95_pct_of_timeout` needs to see). A future slice could split by conclusion; this
one does not, and says so rather than presenting a falsely-precise number.

ALARM (env-overridable via SUITE_GROWTH_P95_TIMEOUT_PCT / SUITE_GROWTH_WEEKLY_GROWTH_PCT,
defaults 85.0 / 8.0):
  - `near_timeout`   := current window has a sample AND timeout_minutes is known AND
                         p95_pct_of_timeout >= SUITE_GROWTH_P95_TIMEOUT_PCT   -> P1
  - `weekly_growth`  := both windows have a sample AND previous_p50 > 0 AND
                         trend_delta_pct > SUITE_GROWTH_WEEKLY_GROWTH_PCT     -> P1
  - both true for the same job                                               -> P0
Alerts go through `scripts/tg_notify.py` — the ONE gateway every Telegram message in
this repo passes through (scar W104: judge the gateway's printed verdict line, never
its exit code, which is always 0 by the gateway's own spool-best-effort contract).
P0 -> `--tier p0` (actionable now). P1-only -> `--tier digest` (informative). A job
whose alert already escalated to P0 does not also fire a separate P1 — one message
per job per run, dedup-keyed `suite-growth:<job-id>` so the gateway's own repeat
ladder (scripts/tg_notify.py docstring) quiets a persisting condition instead of
re-alerting every night. NO alert originates from GitHub Actions itself — the
TELEGRAM_BOT_TOKEN in this repo's Actions secrets is dead (cicatrix-superscar.md
family #9, C8/W102) — this organ lives on Pro launchd, never in a workflow.

FAIL-VISIBLE (scar family #2): every `gh` denial, timeout, or unparseable response is
appended to the record's top-level `errors[]`. The record is ALWAYS written, even
when data collection failed completely. `main()` returns 0 only when `errors` is
empty; a non-empty `errors[]` exits 1 (independent of whether an alert fired — a
growth/timeout finding is a legitimate result, not a probe failure, and must not be
conflated with one).

PAGINATION CAP (empirically hit on this organ's first real run, 2026-08-14): the
`actions/runs` list endpoint's own `list_workflow_runs()` is census-checked — every
paginated response's `total_count` is compared with the number of unique run IDs actually
fetched. GitHub's REST docs state this endpoint "will return up to 1,000 results" for any
query using the `created` filter (docs.github.com/en/rest/actions/workflow-runs); the
first live run against `Bali-Zero/Teman2` confirmed it (`fetched=1000 reported_total=2782`
over the `[since, now]` 2*window_days span). `--paginate` cannot get past this — the cap is
server-side per QUERY, not a client pagination limit — so `list_workflow_runs()` recursively
bisects the `[since, now]` window by `created` timestamp whenever a window's raw fetch hits
the cap while its own `total_count` reports more, deduping runs by id across sibling windows,
bounded by `MAX_BISECT_DEPTH`/`MIN_WINDOW_SECONDS` (a leaf still short at that bound is a
genuine, reported shortfall in `errors[]`, never a silent truncation — scar family #2 / W97).
Same mitigation as `scripts/queue_baseline_probe.py`'s own `list_workflow_runs()` (#4185) —
one cure for both organs, not two independently-invented ones (scar W106b).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import socket
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("suite_growth_probe")

DEFAULT_REPO = "Bali-Zero/Teman2"
DEFAULT_WORKFLOW = "tests.yml"
DEFAULT_OUT_DIR = Path.home() / ".nuzantara-mq" / "suite-growth"
DEFAULT_WINDOW_DAYS = 7
DEFAULT_TEST_DIR = "apps/backend-rag/backend/tests"
SCHEMA_VERSION = 1

GH_TIMEOUT_LIST_RUNS = 120
GH_TIMEOUT_SHORT = 30
GH_TIMEOUT_TG = 30

# GitHub REST docs: the `actions/runs` endpoint returns "up to 1,000 results" for any query
# using the `created` filter (docs.github.com/en/rest/actions/workflow-runs) — a server-side
# cap per query, not a client-side pagination limit. Empirically confirmed 2026-08-14 on this
# exact endpoint+workflow (fetched=1000 reported_total=2782, first live run of this organ) —
# the same defect queue_baseline_probe.py's list_workflow_runs already carries the fix for
# (#4185); same cure applied here rather than a new one invented per-organ (scar W106b: two
# organs sharing one query pattern get ONE fix, not whichever one happened to break first).
PAGE_CAP = 1000

# Bisection safety bound (scar W97 — never a silent truncation): a window still short of its
# own total_count after being split this many times is reported as a genuine shortfall in
# errors[], not silently dropped. Values match queue_baseline_probe.py's own constants —
# twin organs, one cure, not two independently-tuned numbers.
MAX_BISECT_DEPTH = 10
MIN_WINDOW_SECONDS = 1

GATE_EVENTS = ("push", "merge_group")

# tg_notify.py prints its real outcome as `tg_notify: <verdict>` on stderr — the
# gateway's own exit code is always 0 (W104), so this is the only place a caller
# can tell "sent" from "deduped"/"p0_overflow_spooled"/etc. Same convention as
# scripts/job_health.py's _GATEWAY_VERDICT_RE.
_GATEWAY_VERDICT_RE = re.compile(r"^tg_notify:\s*(\S+)", re.MULTILINE)


def _env_float(name: str, default: float) -> float:
    """Garbage in an env knob must never crash a nightly cron (fail-open contract,
    same shape as tg_notify.py's own `_env_num`)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("ignoring unparseable %s=%r, using default %s", name, raw, default)
        return default


P95_TIMEOUT_PCT_THRESHOLD = _env_float("SUITE_GROWTH_P95_TIMEOUT_PCT", 85.0)
WEEKLY_GROWTH_PCT_THRESHOLD = _env_float("SUITE_GROWTH_WEEKLY_GROWTH_PCT", 8.0)


# ---------------------------------------------------------------------------
# Pure functions (no I/O)
# ---------------------------------------------------------------------------


def percentile(values: list[float], pct: float) -> float | None:
    """Linear-interpolation percentile (numpy 'linear' method), dependency-free.

    Duplicated from scripts/queue_baseline_probe.py by declared convention — see
    module docstring. Returns None for an empty sample, never coerced to 0.0.
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    d0 = ordered[int(f)] * (c - k)
    d1 = ordered[int(c)] * (k - f)
    return d0 + d1


def job_window(created_at: datetime, now: datetime, window_days: int) -> str | None:
    """Classify a run's created_at into "current" / "previous" / None (out of range).

    Pure — no I/O. `None` means the run is older than the two windows combined and
    is simply not part of this record (not an error: the API query already bounds
    the fetch, this is a defensive second check on the exact cutoff).
    """
    current_start = now - timedelta(days=window_days)
    previous_start = now - timedelta(days=2 * window_days)
    if current_start <= created_at <= now:
        return "current"
    if previous_start <= created_at < current_start:
        return "previous"
    return None


def qualifies_as_gate_run(run: dict[str, Any]) -> bool:
    """True when a workflow run counts as gate load (module docstring: push-to-main
    or merge_group — NOT develop pushes, NOT PR runs, NOT the 2-hourly schedule
    probe, which the council doc treats as an independent health check, not load).
    """
    event = run.get("event")
    if event == "merge_group":
        return True
    if event == "push" and run.get("head_branch") == "main":
        return True
    return False


def job_wall_minutes(job: dict[str, Any]) -> float | None:
    """(completed_at - started_at) in minutes for one Jobs-API job dict.

    None when the job never reached "completed" status or is missing a timestamp —
    caller records that as a skip, not a zero (a zero would silently claim "ran
    instantly").
    """
    if job.get("status") != "completed":
        return None
    started = job.get("started_at")
    completed = job.get("completed_at")
    if not started or not completed:
        return None
    try:
        t0 = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = (t1 - t0).total_seconds() / 60.0
    return delta if delta >= 0 else None


def compute_job_verdict(
    current_p50: float | None,
    current_p95: float | None,
    previous_p50: float | None,
    timeout_minutes: int | None,
) -> dict[str, Any]:
    """The alarm logic (module docstring "ALARM"), pure and independently testable.

    Never raises: every branch is guarded by an explicit None check so a job with a
    thin sample degrades to "cannot evaluate that condition" rather than a crash or
    a fabricated verdict.
    """
    p95_pct_of_timeout: float | None = None
    near_timeout = False
    if current_p95 is not None and timeout_minutes:
        p95_pct_of_timeout = current_p95 / timeout_minutes * 100.0
        near_timeout = p95_pct_of_timeout >= P95_TIMEOUT_PCT_THRESHOLD

    trend_delta_pct: float | None = None
    weekly_growth = False
    if current_p50 is not None and previous_p50 is not None and previous_p50 > 0:
        trend_delta_pct = (current_p50 - previous_p50) / previous_p50 * 100.0
        weekly_growth = trend_delta_pct > WEEKLY_GROWTH_PCT_THRESHOLD

    if near_timeout and weekly_growth:
        severity = "P0"
    elif near_timeout or weekly_growth:
        severity = "P1"
    else:
        severity = None

    return {
        "p95_pct_of_timeout": p95_pct_of_timeout,
        "near_timeout": near_timeout,
        "trend_delta_pct": trend_delta_pct,
        "weekly_growth": weekly_growth,
        "severity": severity,
    }


def read_job_timeouts(workflow_path: Path) -> tuple[dict[str, dict[str, Any]], str | None]:
    """job-id -> {"name": <API job name>, "timeout_minutes": int|None} from the
    workflow's own YAML.

    Best-effort: PyYAML is not a stdlib module and this repo's other workflow-YAML
    reader (scripts/lint_workflow_timeout_floor.py) already depends on it, but
    unlike scripts/queue_baseline_probe.py this script is therefore NOT
    stdlib-only. A missing/broken PyYAML degrades to an empty map plus a declared
    error string — every job's timeout_minutes is then None in the record, which
    read_job_timeouts' caller must treat as "distance-from-timeout not computable
    this run", never as "no timeout configured".
    """
    try:
        import yaml  # noqa: PLC0415 — deliberately lazy, see docstring
    except ImportError as exc:
        return {}, f"PyYAML unavailable ({exc}); job timeout-minutes not populated this run"

    try:
        doc = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {}, f"could not parse {workflow_path}: {exc}"
    if not isinstance(doc, dict):
        return {}, f"{workflow_path} did not parse to a mapping"

    out: dict[str, dict[str, Any]] = {}
    for job_id, job in (doc.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        timeout = job.get("timeout-minutes")
        if not isinstance(timeout, int) or isinstance(timeout, bool):
            timeout = None
        out[str(job_id)] = {
            "name": job.get("name") or str(job_id),
            "timeout_minutes": timeout,
        }
    return out, None


def count_test_files(repo_root: Path, test_dir: str) -> tuple[int | None, str | None]:
    """`test_*.py` count under `<repo_root>/<test_dir>` — a correlate, not itself
    alarmed on. None + error string when the directory does not exist (never a
    silent 0, which would read as "test suite is empty")."""
    target = repo_root / test_dir
    if not target.is_dir():
        return None, f"test dir not found: {target}"
    return sum(1 for _ in target.rglob("test_*.py")), None


# ---------------------------------------------------------------------------
# subprocess boundaries — one for gh, one for tg_notify, so tests intercept each
# shape independently (mirrors queue_baseline_probe.py's single `_run_gh` boundary).
# ---------------------------------------------------------------------------


def _run_gh(cmd: list[str], timeout: int = GH_TIMEOUT_SHORT) -> subprocess.CompletedProcess[str]:
    """The one subprocess boundary this module crosses for `gh` calls. Never raises
    on a non-zero exit; may raise `subprocess.TimeoutExpired`, caught by callers."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _run_tg_notify(cmd: list[str], timeout: int = GH_TIMEOUT_TG) -> subprocess.CompletedProcess[str]:
    """The one subprocess boundary this module crosses to reach tg_notify.py. Kept
    separate from `_run_gh` so a test can fake one without accidentally answering
    for the other (scar W114: the fake belongs at the boundary the real code
    crosses, matched one-for-one, not merged into a single do-everything stub).

    tg_notify.py always exits 0 (W104) — sent/logged/spooled/deduped/
    p0_overflow_spooled/p0_unsent_spooled are all rc=0. The gateway prints the
    real outcome as `tg_notify: <verdict>` on its own stderr; a caller that never
    parses that line reads a refusal as a delivery
    (scripts/tests/test_gateway_callers_read_the_verdict.py). Parse and log it
    here, at the one place this module crosses the subprocess boundary, so every
    caller of this function inherits the reading for free instead of each one
    re-deriving it (or forgetting to)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    m = _GATEWAY_VERDICT_RE.search(proc.stderr or "")
    print(
        f"tg_notify: {m.group(1) if m else f'NESSUN verdetto rc={proc.returncode}'}",
        file=sys.stderr,
    )
    return proc


def _parse_concatenated_json(text: str) -> list[dict[str, Any]]:
    """Parse zero or more whitespace-separated JSON objects (`gh api --paginate`
    output) — identical to queue_baseline_probe.py's own helper, duplicated by the
    same flat-bag-of-scripts convention."""
    decoder = json.JSONDecoder()
    text = text.strip()
    objs: list[dict[str, Any]] = []
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        objs.append(obj)
        idx = end
    return objs


# ---------------------------------------------------------------------------
# I/O-fetching functions — each returns (data, errors), never raises for a normal
# gh failure.
# ---------------------------------------------------------------------------


def _fetch_runs_window(
    repo: str,
    workflow: str,
    start: datetime,
    end: datetime,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], int | None, int, list[str]]:
    """Fetch every page `gh api --paginate` will give us for one `[start, end]` UTC window of
    `workflow`'s completed runs (both ends inclusive, matching GitHub's `created`
    range-qualifier semantics).

    Pure I/O primitive — mirrors queue_baseline_probe.py's `_fetch_runs_window` in structure
    (same twin-organ cure, module docstring PAGINATION CAP section). Does not decide whether
    the window needs to be split further; that decision belongs to `list_workflow_runs` so
    this stays a single, independently testable fetch. Returns
    `(runs_by_id, runs_without_id, reported_total, raw_item_count, errors)` where
    `raw_item_count` is the number of `workflow_runs` entries actually returned across all
    pages BEFORE dedup — the number `PAGE_CAP` is measured against, since GitHub's documented
    1,000-result cap is on items served, not on the dedup'd id count.
    """
    created_query = f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}..{end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    cmd = [
        "gh", "api", f"repos/{repo}/actions/workflows/{workflow}/runs",
        "-X", "GET",
        "-f", "status=completed",
        "-f", f"created={created_query}",
        "-f", "per_page=100",
        "--paginate",
    ]
    errors: list[str] = []
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_LIST_RUNS)
    except subprocess.TimeoutExpired as exc:
        return {}, [], None, 0, [f"list_workflow_runs timeout window={created_query}: {exc}"]
    except OSError as exc:
        return {}, [], None, 0, [f"list_workflow_runs OSError window={created_query}: {exc}"]
    if proc.returncode != 0:
        return {}, [], None, 0, [
            f"list_workflow_runs failed window={created_query} rc={proc.returncode} "
            f"stderr={proc.stderr.strip()[:400]}"
        ]
    try:
        pages = _parse_concatenated_json(proc.stdout)
    except json.JSONDecodeError as exc:
        return {}, [], None, 0, [f"list_workflow_runs bad JSON window={created_query}: {exc}"]

    reported_totals = {
        int(page["total_count"]) for page in pages if isinstance(page.get("total_count"), int)
    }
    positive_totals = {t for t in reported_totals if t > 0}
    reported_total = max(reported_totals) if reported_totals else None
    if len(positive_totals) > 1:
        errors.append(
            "list_workflow_runs inconsistent positive total_count values across pages "
            f"window={created_query}: {sorted(positive_totals)}"
        )
    if reported_total is None:
        errors.append(f"list_workflow_runs response missing integer total_count window={created_query}")

    runs_by_id: dict[int, dict[str, Any]] = {}
    runs_without_id: list[dict[str, Any]] = []
    raw_item_count = 0
    for page in pages:
        for run in page.get("workflow_runs") or []:
            raw_item_count += 1
            run_id = run.get("id") if isinstance(run, dict) else None
            if isinstance(run_id, int):
                runs_by_id[run_id] = run
            elif isinstance(run, dict):
                runs_without_id.append(run)
    return runs_by_id, runs_without_id, reported_total, raw_item_count, errors


def list_workflow_runs(
    repo: str,
    workflow: str,
    since: datetime,
    now: datetime,
) -> tuple[list[dict[str, Any]], int | None, list[str]]:
    """Completed runs of `workflow` created in `[since, now]` (UTC), with a census check.

    Returns `(unique_runs, reported_total, errors)`. `reported_total` is the whole window's
    real total (from the initial, unsplit `[since, now]` fetch — bisection never changes what
    "the window's total" means, only how many requests it takes to actually fetch it).

    GitHub's `actions/runs` list endpoint returns "up to 1,000 results" for any query using
    the `created` filter (module docstring, PAGINATION CAP) — a cap on the QUERY, so
    `--paginate` alone cannot get past it. Whenever a window's raw fetch hits that cap
    (`>= PAGE_CAP`) while its own `total_count` says there is more, the window is bisected by
    `created` timestamp and each half is fetched independently, recursing until every leaf is
    fully resolved or the recursion bound (`MAX_BISECT_DEPTH` / `MIN_WINDOW_SECONDS`) is hit.
    A shortfall NOT explained by the cap (raw fetch below `PAGE_CAP`, yet still short of
    `total_count` — e.g. a data anomaly) is reported immediately without attempting to bisect:
    a narrower window cannot return more than a wider one already failed to. Same strategy as
    `scripts/queue_baseline_probe.py`'s `list_workflow_runs` (#4185) — one cure for both
    organs (scar W106b).
    """
    runs_by_id: dict[int, dict[str, Any]] = {}
    runs_without_id: list[dict[str, Any]] = []
    errors: list[str] = []
    window_reported_total: list[int | None] = [None]  # set once, from the depth-0 fetch

    def _collect(start: datetime, end: datetime, depth: int) -> None:
        window_runs, window_no_id, reported_total, raw_count, window_errors = _fetch_runs_window(
            repo, workflow, start, end
        )
        errors.extend(window_errors)
        if depth == 0:
            window_reported_total[0] = reported_total
        runs_by_id.update(window_runs)
        runs_without_id.extend(window_no_id)

        unique_count = len(window_runs) + len(window_no_id)
        if reported_total is None or unique_count >= reported_total:
            return  # this window is fully accounted for (or totally unknown — nothing more to do)

        if raw_count < PAGE_CAP:
            # Short of total_count but never even reached the documented cap — not a
            # capacity problem, bisecting cannot help. Depth-0 keeps the exact historical
            # message shape (no window suffix) since that IS the whole requested window.
            if depth == 0:
                errors.append(
                    "list_workflow_runs pagination shortfall: "
                    f"fetched={unique_count} reported_total={reported_total}; record is partial"
                )
            else:
                errors.append(
                    "list_workflow_runs pagination shortfall: "
                    f"fetched={unique_count} reported_total={reported_total} "
                    f"window={start.isoformat()}..{end.isoformat()}; record is partial"
                )
            return

        window_seconds = (end - start).total_seconds()
        if depth >= MAX_BISECT_DEPTH or window_seconds <= MIN_WINDOW_SECONDS:
            errors.append(
                "list_workflow_runs pagination shortfall even after bisection: "
                f"fetched={unique_count} reported_total={reported_total} "
                f"window={start.isoformat()}..{end.isoformat()} depth={depth}; "
                "window not further splittable"
            )
            return

        mid = start + (end - start) / 2
        _collect(start, mid, depth + 1)
        _collect(mid, end, depth + 1)

    _collect(since, now, 0)

    runs = [*runs_by_id.values(), *runs_without_id]
    return runs, window_reported_total[0], errors


def fetch_run_jobs(repo: str, run_id: int) -> tuple[list[dict[str, Any]], str | None]:
    """GET .../actions/runs/{run_id}/jobs -> jobs list (name/status/started_at/completed_at).

    `-X GET` is NOT optional here: `gh api` switches its default method to POST
    the instant any `-f`/`-F` field is present, unless `-X`/`--method` says
    otherwise (verified live against this endpoint during this script's own
    dry-run — every job fetch 404'd until this flag was added; see the PR
    description for the reproduction). `list_workflow_runs()` above already had
    this right; this function did not, which is exactly the kind of drift a
    single shared `_run_gh` boundary is supposed to prevent from mattering —
    it didn't, because the argv is still assembled per call-site.
    """
    cmd = ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs", "-X", "GET", "-f", "per_page=100", "--paginate"]
    try:
        proc = _run_gh(cmd, timeout=GH_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired as exc:
        return [], f"jobs fetch timeout run={run_id}: {exc}"
    except OSError as exc:
        return [], f"jobs fetch OSError run={run_id}: {exc}"
    if proc.returncode != 0:
        return [], f"jobs fetch failed run={run_id} rc={proc.returncode} stderr={proc.stderr.strip()[:300]}"
    try:
        pages = _parse_concatenated_json(proc.stdout)
    except json.JSONDecodeError as exc:
        return [], f"jobs fetch bad JSON run={run_id}: {exc}"
    jobs: list[dict[str, Any]] = []
    for page in pages:
        jobs.extend(page.get("jobs") or [])
    return jobs, None


def send_alert(
    tier: str,
    source: str,
    dedup_key: str,
    message: str,
    tg_notify_path: Path,
    python_executable: str | None = None,
) -> tuple[bool, str]:
    """Dispatch one message through scripts/tg_notify.py (job_health.py's own
    subprocess-invocation pattern, --tier/--source/--dedup-key/-- <msg>).

    Returns (dispatched, detail). `dispatched` is True whenever the subprocess call
    itself completed (tg_notify.py's own contract is to always exit 0 — W104: a
    caller judges the printed verdict line, never the exit code, so this function
    surfaces stdout/stderr in `detail` for the caller to log, but does not treat a
    non-zero rc as proof the alert failed to spool).
    """
    if not tg_notify_path.is_file():
        return False, f"tg_notify.py not found at {tg_notify_path}"
    python_executable = python_executable or sys.executable
    cmd = [
        python_executable, str(tg_notify_path),
        "--tier", tier,
        "--source", source,
        "--dedup-key", dedup_key,
        "--", message,
    ]
    try:
        proc = _run_tg_notify(cmd)
    except subprocess.TimeoutExpired as exc:
        return False, f"tg_notify timeout: {exc}"
    except OSError as exc:
        return False, f"tg_notify OSError: {exc}"
    detail = (proc.stdout + proc.stderr).strip()[:400]
    return True, detail or f"rc={proc.returncode}"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _empty_record(repo: str, workflow: str, now: datetime, window_days: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo,
        "workflow": workflow,
        "window_days": window_days,
        "thresholds": {
            "p95_timeout_pct": P95_TIMEOUT_PCT_THRESHOLD,
            "weekly_growth_pct": WEEKLY_GROWTH_PCT_THRESHOLD,
        },
        "run_collection": {"reported_total": None, "fetched": 0, "complete": False},
        "jobs": {},
        "test_file_count": None,
        "alerts_sent": [],
        "errors": [],
    }


def build_record(
    repo: str,
    workflow: str,
    repo_root: Path,
    test_dir: str,
    now: datetime,
    window_days: int,
    tg_notify_path: Path,
    dispatch_alerts: bool = True,
) -> dict[str, Any]:
    """Build one record. Never raises — a crash mid-way is caught by main() and
    turned into an emergency record carrying the traceback, same contract as
    queue_baseline_probe.build_record / _emergency_record."""
    record = _empty_record(repo, workflow, now, window_days)
    errors: list[str] = record["errors"]

    since = now - timedelta(days=2 * window_days)
    runs, reported_total, run_errors = list_workflow_runs(repo, workflow, since, now)
    errors.extend(run_errors)
    record["run_collection"] = {
        "reported_total": reported_total,
        "fetched": len(runs),
        "complete": reported_total == len(runs),
    }

    gate_runs = [r for r in runs if qualifies_as_gate_run(r)]

    # job_id -> window -> list[minutes]; job_id -> observed API display name
    samples: dict[str, dict[str, list[float]]] = {}
    display_names: dict[str, str] = {}

    for run in gate_runs:
        run_id = run.get("id")
        created_at_raw = run.get("created_at")
        if run_id is None or not created_at_raw:
            errors.append(f"gate run missing id/created_at, skipped: {run.get('name', '?')!r}")
            continue
        try:
            created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
        except ValueError as exc:
            errors.append(f"unparseable created_at run={run_id}: {exc}")
            continue
        window = job_window(created_at, now, window_days)
        if window is None:
            continue

        jobs, jobs_error = fetch_run_jobs(repo, run_id)
        if jobs_error:
            errors.append(jobs_error)
            continue
        for job in jobs:
            minutes = job_wall_minutes(job)
            if minutes is None:
                continue
            job_name = str(job.get("name") or "unknown")
            job_key = re.sub(r"\s*\(.*?\)\s*$", "", job_name).strip() or job_name
            job_key = re.sub(r"[^a-zA-Z0-9]+", "-", job_key).strip("-").lower() or "unknown"
            display_names.setdefault(job_key, job_name)
            samples.setdefault(job_key, {"current": [], "previous": []})[window].append(minutes)

    workflow_path = repo_root / ".github" / "workflows" / workflow
    timeout_map, timeout_error = read_job_timeouts(workflow_path)
    if timeout_error:
        errors.append(timeout_error)
    # name -> timeout_minutes, matched on the same normalized-name key as `samples`
    timeout_by_key: dict[str, int | None] = {}
    for meta in timeout_map.values():
        key = re.sub(r"\s*\(.*?\)\s*$", "", str(meta["name"])).strip() or str(meta["name"])
        key = re.sub(r"[^a-zA-Z0-9]+", "-", key).strip("-").lower() or "unknown"
        timeout_by_key[key] = meta["timeout_minutes"]

    jobs_out: dict[str, Any] = {}
    alerts_sent: list[dict[str, Any]] = []
    for job_key, windows in sorted(samples.items()):
        current_samples = windows.get("current", [])
        previous_samples = windows.get("previous", [])
        current_p50 = percentile(current_samples, 50)
        current_p95 = percentile(current_samples, 95)
        previous_p50 = percentile(previous_samples, 50)
        timeout_minutes = timeout_by_key.get(job_key)
        if job_key not in timeout_by_key:
            errors.append(f"no timeout-minutes entry found for job '{job_key}' in {workflow}")

        verdict = compute_job_verdict(current_p50, current_p95, previous_p50, timeout_minutes)

        jobs_out[job_key] = {
            "api_job_name": display_names.get(job_key, job_key),
            "timeout_minutes": timeout_minutes,
            "current_window": {
                "sample_size": len(current_samples),
                "p50_minutes": current_p50,
                "p95_minutes": current_p95,
            },
            "previous_window": {
                "sample_size": len(previous_samples),
                "p50_minutes": previous_p50,
            },
            **verdict,
        }

        if verdict["severity"] is not None:
            reasons = []
            if verdict["near_timeout"]:
                pct = verdict["p95_pct_of_timeout"]
                reasons.append(
                    f"p95={current_p95:.1f}min is {pct:.0f}% of the {timeout_minutes}min timeout"
                )
            if verdict["weekly_growth"]:
                reasons.append(f"p50 grew {verdict['trend_delta_pct']:.1f}% week-over-week")
            message = (
                f"suite-growth {verdict['severity']}: {display_names.get(job_key, job_key)} "
                f"({workflow}) — {'; '.join(reasons)}."
            )
            tier = "p0" if verdict["severity"] == "P0" else "digest"
            dedup_key = f"suite-growth:{job_key}"
            alert_entry = {
                "job": job_key,
                "severity": verdict["severity"],
                "tier": tier,
                "dedup_key": dedup_key,
                "message": message,
                "dispatched": None,
                "detail": None,
            }
            if dispatch_alerts:
                dispatched, detail = send_alert(
                    tier, "suite-growth-probe", dedup_key, message, tg_notify_path
                )
                alert_entry["dispatched"] = dispatched
                alert_entry["detail"] = detail
                if not dispatched:
                    errors.append(f"alert dispatch failed for job={job_key}: {detail}")
            alerts_sent.append(alert_entry)

    record["jobs"] = jobs_out
    record["alerts_sent"] = alerts_sent

    count, count_error = count_test_files(repo_root, test_dir)
    if count_error:
        errors.append(count_error)
    record["test_file_count"] = {"path": test_dir, "count": count}

    return record


def _emergency_record(
    repo: str, workflow: str, now: datetime, window_days: int, exc: BaseException
) -> dict[str, Any]:
    record = _empty_record(repo, workflow, now, window_days)
    record["errors"].append(
        f"FATAL uncaught exception while building record: {exc!r}\n{traceback.format_exc()}"
    )
    return record


def write_record(out_dir: Path, record: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = record["generated_at_utc"].replace(":", "").replace("-", "")
    out_path = out_dir / f"{stamp}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(out_path)  # atomic on the same filesystem
    return out_path


def write_pointer(out_dir: Path, record: dict[str, Any], record_path: Path) -> Path:
    """Same rationale as queue_baseline_probe.write_pointer: one computation of
    "what did the last run produce", read by the wrapper, never recomputed twice."""
    pointer_path = out_dir / ".last-run-pointer.json"
    pointer = {
        "generated_at_utc": record["generated_at_utc"],
        "record_path": str(record_path),
        "errors_count": len(record["errors"]),
        "alerts_sent_count": len(record["alerts_sent"]),
    }
    tmp_path = pointer_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(pointer_path)
    return pointer_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo, default %(default)s")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="workflow file, default %(default)s")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="local checkout root, for reading the workflow YAML + counting test files",
    )
    parser.add_argument("--test-dir", default=DEFAULT_TEST_DIR, help="relative test dir, default %(default)s")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="directory for records, default %(default)s")
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS, help="default %(default)s")
    parser.add_argument(
        "--now",
        default=None,
        help="UTC ISO-8601 instant to treat as 'now' (default: real now — for test determinism)",
    )
    parser.add_argument(
        "--tg-notify-path",
        default=None,
        help="override path to tg_notify.py (default: <repo-root>/scripts/tg_notify.py)",
    )
    parser.add_argument(
        "--no-alert",
        action="store_true",
        help="build the record and compute verdicts, but never dispatch to tg_notify.py "
        "(dry-run / local inspection)",
    )
    parser.add_argument("--verbose", action="store_true", help="DEBUG-level logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )

    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(timezone.utc)
    )
    repo_root = Path(args.repo_root)
    tg_notify_path = Path(args.tg_notify_path) if args.tg_notify_path else repo_root / "scripts" / "tg_notify.py"
    out_dir = Path(args.out_dir)

    try:
        record = build_record(
            args.repo,
            args.workflow,
            repo_root,
            args.test_dir,
            now,
            args.window_days,
            tg_notify_path,
            dispatch_alerts=not args.no_alert,
        )
    except Exception as exc:  # noqa: BLE001 — last-resort guard, see module docstring
        logger.exception("uncaught exception building record")
        record = _emergency_record(args.repo, args.workflow, now, args.window_days, exc)

    out_path = write_record(out_dir, record)
    write_pointer(out_dir, record, out_path)

    n_errors = len(record["errors"])
    n_alerts = len(record["alerts_sent"])
    if n_errors:
        logger.warning("wrote %s with %d error(s) — see errors[] in the record", out_path, n_errors)
        for err in record["errors"]:
            logger.warning("  - %s", err.splitlines()[0] if err else err)
    else:
        logger.info(
            "wrote %s on %s — jobs=%d alerts=%d",
            out_path,
            socket.gethostname().split(".")[0],
            len(record["jobs"]),
            n_alerts,
        )
    if n_alerts:
        for alert in record["alerts_sent"]:
            logger.info("  alert %s job=%s dispatched=%s", alert["severity"], alert["job"], alert["dispatched"])

    return 1 if n_errors else 0


if __name__ == "__main__":
    sys.exit(main())
