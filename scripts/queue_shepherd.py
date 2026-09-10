#!/usr/bin/env python3
"""queue_shepherd.py — Merge-OS v3 Codex F7 disposition: budgeted auto-rearm + stale-run janitor.

WHY THIS EXISTS (Zero GO 2026-08-27). Two failure modes measured live in one night on this
repo's merge queue: (1) merge-queue entries silently drop and auto-merge disarms — 6+ manual
re-arms in one session, #5052 vanished from the queue un-merged; (2) stale Actions runs pile up
in the runner queue — 119 found by hand, `pull_request` runs for superseded PR heads and
`merge_group` runs for dead `gh-readonly-queue` branches that will never build.

GOVERNING SPEC (read before touching this file):
research/operations/2026-08-14-merge-os-v3-research-council.md §5, row "Codex F7 (retry
counter resets)": "durable budget keyed (repo, PR, head SHA), never queue entry; CODE=0
auto-requeue, INFRA<=3/24h, CONFLICT/HEAD_MOVED=none until new head passes smoke, UNKNOWN=
fail-closed; no atomic cross-run store exists in Actions -> if no organic durable store, the
conservative choice is NO autonomous rearm (launchd organ on Pro can own the counter file)."
This script IS that launchd organ; the counter file is `~/logs/queue-shepherd/rearm-budget.json`.

ATTRIBUTION METHOD (agy-F3 disposition, same council doc): attribute an ejection from the PR's
OWN GraphQL timeline (`RemovedFromMergeQueueEvent`), never from a `merge_group` run's `actor`
(always the queue's own service account). `scripts/queue_ejection_attribution.py` already
implements a full historical AUDIT of this signal with its own declared STANDALONE-by-design
note ("duplicated, not imported" — it does not want a coupling with a sibling file that other
PRs are actively editing). This script is a live-action organ, not an audit tool, and follows
the SAME declared convention for the same reason: the small classification heuristic
(`classify_ejection_reason`, `_run_has_infra_signature`) is duplicated here in miniature, not
imported, so this organ never breaks because that audit module's shape changed underneath it
(and vice versa). If that module's heuristic changes, re-check this one too.

TWO INDEPENDENT ACTIONS PER TICK:

(a) RE-ARM (budgeted). A PR counts as "armed by this repo's convention" if its branch is under
    the `agent/` namespace (CLAUDE.md Agent PR Contract §6) OR it carries a `harness/fable-gate`
    (or `harness-floor`) status/check context — the final on-disk gate. Among those, a PR is a
    re-arm CANDIDATE only when it is open, non-draft, currently disarmed (`autoMergeRequest` is
    null AND it holds no `mergeQueueEntry` — per W111, either field alone is ambiguous, see
    `docs/scars/cicatrix-scars.md` ~line 160; ONLY both-null means truly disarmed) and its
    `mergeStateStatus` is CLEAN/UNSTABLE, or BLOCKED with a green status-check rollup (a required
    review gate blocking merge, not a red check). For each candidate, its most recent
    `RemovedFromMergeQueueEvent` (if any) is classified CODE / INFRA / CONFLICT / MANUAL /
    UNKNOWN. Only INFRA re-arms under budget (<=3 per (PR, head SHA) per rolling 24h, see
    `count_recent_infra_rearms`); CODE, CONFLICT, MANUAL and no-event-found (UNKNOWN) NEVER
    auto-rearm — the last two fail closed with a one-time Telegram alert (deduped per
    (PR, head SHA) so a stuck PR doesn't spam every 10 minutes).

(b) JANITOR (stale-run cancellation). Cancels QUEUED (never in_progress/completed) Actions runs
    that can no longer build anything useful: a `pull_request`-event run whose `head_sha` is not
    the current head of ANY open PR (the PR's head moved — a new run superseded it), or a
    `merge_group`-event run whose `head_branch` (`gh-readonly-queue/main/pr-N-<sha>`) no longer
    exists (the queue already ejected or merged that entry). Liveness is RE-VERIFIED with a
    fresh fetch immediately before each cancel call, not from the list used to build the
    candidate set — a run can go from stale to live (or vice versa) in the seconds a tick takes
    to walk its candidates, and cancelling on a stale READ would be a real mutation on a false
    premise (this repo's own fail-visible discipline, superscar #2/#9).

FAIL-CLOSED DISCIPLINE: any `gh` fetch failure raises (never returns a fabricated empty list —
an empty candidate set must never be confused with "gh api failed"). `--tick` catches such
errors at the top level, logs CANNOT-VERIFY, and exits without having mutated anything.

QUARANTINE (added 2026-08-31, squad-S disposition on issue #5316): measured live on Pro the
night of 2026-08-30/31 — four run ids (32217208723, 32217208752, 32217399769, 32212086540)
failed `cancel_run` with the IDENTICAL `HTTP 500 "Failed to cancel workflow run"` on EVERY
10-minute tick, forever, because that outcome classifies as "failed" (see cancel_run's own
docstring), and "failed" was — by design — never persisted to UNCANCELLABLE_FILE, on the
reasoning that a single such failure might be transient. It was not: the same four ids repeated
for hours. `record_cancel_failure` now counts CONSECUTIVE non-"cancelled" outcomes per run id;
after UNCANCELLABLE_FAILURE_THRESHOLD (3 — long enough that one or two genuinely-transient
blips never trip it, short enough that a truly-stuck run stops being retried inside the hour)
it is quarantined into UNCANCELLABLE_FILE alongside its last error and a timestamp, and the
janitor's per-tick loop skips it via `is_quarantined`. A single "uncancellable_409" outcome
(GitHub's OWN plain-cancel AND force-cancel endpoints both refusing) still quarantines on the
same tick it is first seen — nothing is learned by retrying that specific class three more
times; this is unchanged from before. EXPIRY: quarantining stamps `quarantined_at`; past
UNCANCELLABLE_RETRY_COOLDOWN_HOURS (24h) the janitor allows exactly one retry. A successful
cancel on that retry (or any retry) clears the run's entry outright via `clear_cancel_entry` —
"reset the counter if a later attempt succeeds". A retry that fails again refreshes
`quarantined_at` to the new attempt, restarting the cooldown, so a permanently-broken run is
retried at most once per cooldown window forever, never hammered every tick again.

S1 "ARM THE ARMER" (2026-09-10): the organ's candidate read had been CANNOT-VERIFY on every real
tick since 2026-08-28 (1892 `CANNOT-VERIFY rearm candidates` lines in queue-shepherd.err.log,
zero PRs ever classified). Error mix of those reads: 1143 "Resource limits for this query
exceeded", 474 HTTP 502, 266 HTTP 504 "couldn't respond in time" (plus a handful of truncated-
JSON/timeout/connect-error outliers). Live probe: `REARM_CANDIDATES_QUERY` verbatim fails (504 at
`first:100`, "Resource limits" at `first:25`); the SAME query without the
`checkSuites(first:20){checkRuns(first:20){...}}` line succeeds (4.3s, cost 1, at `first:100`).
That branch was dead weight anyway (harness/fable-gate is a commit STATUS context, never a
check-run). Dropped it,
page size to `first:50`, and added one retry (RETRY_BACKOFF_SECONDS, via the `_sleep` seam) per
candidate page. `run_rearm_pass`/`run_janitor_pass` now return a documented result dict, never a
bare int — `examined`/`candidates`/`unknown` come from a NEW `fetch_open_prs` (every open PR,
unfiltered; `fetch_rearm_candidate_prs` is now a filtering wrapper over it, no double fetch).
CANNOT-VERIFY is a tick OUTCOME: `tick()` logs it at ERROR, heartbeats `error`, sends ONE
`send_telegram(..., dedup_key="queue-shepherd:cannot-verify")` (unless dry-run), and returns 2 —
never folded into a silent "rearmed=0, nothing to do".

SAME-CAUSE SUSPENSION (Builder Contract §1: "three reds for the SAME cause and the PR suspends
instead of taking a fourth round"). A red = an observed `RemovedFromMergeQueueEvent` with reason
`failed_checks`; its cause is `red_cause_fingerprint(run, jobs)` on the SAME correlated
merge_group run `fetch_infra_hint_and_fingerprint` (one fetch, both signals) already locates —
`fetch_infra_hint` is now a thin wrapper over it. Durable, PR-level (not head-level — a new head
SHA does NOT reset this) state in `QUEUE_SHEPHERD_RED_FILE` (default
`~/logs/queue-shepherd/red-causes.json`). RED_SAME_CAUSE_LIMIT=3 non-None-cause reds sets
`suspended` (sticky, no time-based unsuspend — GC only drops an entry once its PR is no longer
open) and overrides `allowed` regardless of class or budget; no Telegram (Mini's stall notifier
already reports the disarmed PR). A None cause (no correlated run found) never counts.

NEVER-QUEUED IS NOT AN EJECTION: `fetch_last_ejection` returns the literal string "NEVER_QUEUED"
(never plain None, which stays reserved for "last item is Added" / genuinely UNKNOWN) when a PR's
timeline carries no Added/Removed-from-merge-queue event at all — that PR simply never went
through the queue, so it is not an ejection this organ caused, is not alerted on, and
`decide_rearm` refuses it as `never_queued_not_ours`. Before this, the first live tick would have
sent a false P0 "no readable ejection reason" for exactly this shape (measured live on #5838 and
#6054), duplicating Mini's own not-armed signal.

DRY-RUN FIDELITY: dry-run now READS every state file (budget/alerted/uncancellable/red) exactly
as a live tick would — only the WRITE at the end of each pass is skipped. Before this, dry-run
substituted `{}` for all of them, so a dry-run preview's numbers (would-rearm, would-cancel)
disagreed with what the SAME tick would actually do live — e.g. reporting `cancelled=6` for runs
the live janitor would in fact skip as already-quarantined.

Kill switch: QUEUE_SHEPHERD_ENABLED=false makes every invocation a no-op that still prints a
receipt line (superscar #2: a mute cron reads as a dead cron with nothing to report — never
let silence be the only signal).

--dry-run (tick only): zero mutations — no `gh pr merge`, no run-cancel, no Telegram send, no
state-file write (mirrors queue_unstick.py's `--dry-run` contract exactly).

Env overrides:
    QUEUE_SHEPHERD_ENABLED       "false"/"0"/"no"/"off" -> no-op (default: on)
    QUEUE_SHEPHERD_REPO          default "Bali-Zero/Teman2"
    QUEUE_SHEPHERD_BUDGET_FILE   default ~/logs/queue-shepherd/rearm-budget.json
    QUEUE_SHEPHERD_ALERTED_FILE  default ~/logs/queue-shepherd/alerted-unknown.json
    QUEUE_SHEPHERD_LOG_FILE      default ~/logs/queue-shepherd.log
    TELEGRAM_OWNER_CHAT_ID       read at send time, never hardcoded in this file (per mandate —
                                 the CI-secret path is for GitHub Actions; a local organ reads
                                 the process env). Missing -> WARN + skip send, never fatal.

Tests: scripts/tests/test_queue_shepherd.py.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

REPO = os.environ.get("QUEUE_SHEPHERD_REPO", "Bali-Zero/Teman2")
BUDGET_FILE = Path(
    os.environ.get(
        "QUEUE_SHEPHERD_BUDGET_FILE", os.path.expanduser("~/logs/queue-shepherd/rearm-budget.json")
    )
)
RED_FILE = Path(
    os.environ.get(
        "QUEUE_SHEPHERD_RED_FILE", os.path.expanduser("~/logs/queue-shepherd/red-causes.json")
    )
)
ALERTED_FILE = Path(
    os.environ.get(
        "QUEUE_SHEPHERD_ALERTED_FILE",
        os.path.expanduser("~/logs/queue-shepherd/alerted-unknown.json"),
    )
)
UNCANCELLABLE_FILE = Path(
    os.environ.get(
        "QUEUE_SHEPHERD_UNCANCELLABLE_FILE",
        os.path.expanduser("~/logs/queue-shepherd/uncancellable.json"),
    )
)
LOG_FILE = Path(
    os.environ.get("QUEUE_SHEPHERD_LOG_FILE", os.path.expanduser("~/logs/queue-shepherd.log"))
)

# Organism heartbeat sidecar (organ-conformance G2, born 2026-08-27): the organ must prove its
# own liveness every run, on BOTH the success and failure path (superscar #2, esiste != armato —
# a launchd job with KeepAlive/StartInterval "green" tells you nothing about whether its last
# tick actually did anything). Mirrors dlq_autopilot.py's unconditional-heartbeat pattern.
ORGANISM_DIR = Path(os.path.expanduser("~/.organism/last_seen"))
ORGAN_ID = "pro.queue_shepherd"

INFRA_BUDGET_MAX = 3
BUDGET_WINDOW_HOURS = 24
BUDGET_GC_DAYS = 7  # prune (pr,sha) entries older than this so the file never grows unbounded

# One retry per candidate-read page (S1, 2026-09-10) — see the module docstring's S1 section for
# the measured error mix. A single transient blip must not CANNOT-VERIFY an entire tick.
# `_sleep` is a module-level seam (monkeypatchable in tests), never a bare time.sleep() call.
RETRY_BACKOFF_SECONDS = 5
_sleep = time.sleep

# Quarantine (2026-08-31, squad-S / issue #5316) — see module docstring QUARANTINE section.
UNCANCELLABLE_FAILURE_THRESHOLD = 3  # consecutive non-"cancelled" outcomes before quarantine
UNCANCELLABLE_RETRY_COOLDOWN_HOURS = 24  # past this since quarantined_at, allow ONE retry

# Same-cause suspension (letter E, S1 2026-09-10 — Builder Contract §1: "three reds for the SAME
# cause and the PR suspends instead of taking a fourth round"). PR-level, not head-level: a new
# head SHA does NOT reset this (unlike the INFRA budget) — the cause, not the commit, is what
# repeats. No cap on history length (B3(a), Codex review 2026-09-11): the PR's full red history
# is kept for as long as the PR stays open — see record_red / gc_red_state.
RED_SAME_CAUSE_LIMIT = 3

_UNCANCELLABLE_ERROR_LABELS = {
    "uncancellable_409": "both cancel and force-cancel endpoints answered HTTP 409 (not queued yet)",
    "failed": "cancel_run failed (non-409) repeatedly — see queue-shepherd.log for the gh stderr",
}

FABLE_GATE_CONTEXT_NAMES = ("harness/fable-gate", "harness-floor")

EJECTION_CLASSES = ("CODE", "INFRA", "CONFLICT", "MANUAL", "NEVER_QUEUED", "UNKNOWN")

# K-5 (Kimi council finding, S1 2026-09-11): the signatures are matched against a job's WHOLE
# NAME, never as bare substrings. queue_ejection_attribution.py and queue_baseline_probe.py keep
# the substring form on purpose — they are RETROSPECTIVE readers, and over-reading INFRA there
# costs a mislabelled row in an audit. This module MUTATES (it re-arms), so it takes the same
# deliberate divergence already taken for all()-vs-ANY: when the two rules disagree, the mutating
# one is the strict one. The substrings were unsafe as substrings, and not hypothetically —
# measured against the 72 real check names of PR #6144, exactly one matched: `Snyk Docker
# Security`, whose failure is the least infra-flavoured event in the repository. `docker` used to
# read it as INFRA and re-arm a real security red. Anchored, it reads CODE.
#
# Whole-name match means a job called `checkout` or `setup-python` is still INFRA, while
# `Build Docker image`, `Cache dependencies` and `docker-build` are CODE. Failing closed in this
# direction is the safe one: a missed INFRA costs one un-re-armed PR that the next human notices,
# an over-read INFRA re-arms a red that a human never sees.
INFRA_JOB_NAME_PATTERNS = (
    re.compile(r"^set up job$"),
    re.compile(r"^complete job$"),
    re.compile(r"^checkout$"),
    re.compile(r"^cache$"),
    re.compile(r"^docker$"),
    re.compile(r"^runner$"),
    re.compile(r"^setup-[\w.+-]+$"),
    re.compile(r"^set up [\w.+ -]+$"),
)


def _is_infra_job_name(name: Any) -> bool:
    """True when a job's WHOLE name is one of the infra shapes (K-5). Whitespace-normalised and
    lowercased first, so `  Set Up   Job ` matches and `Snyk Docker Security` does not."""
    normalized = " ".join(str(name or "").lower().split())
    return any(pattern.match(normalized) for pattern in INFRA_JOB_NAME_PATTERNS)

PR_SHA_RE = re.compile(r"pr-(\d+)-([0-9a-f]{40})")

logger = logging.getLogger("queue_shepherd")


def _configure_logging(dry_run: bool = False) -> None:
    """B4 (Codex review, 2026-09-11): dry-run writes nothing, anywhere — including LOG_FILE.
    main() now parses args BEFORE calling this, so a --dry-run invocation never creates the
    RotatingFileHandler at all; logging goes to stderr only via the plain stream handler."""
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    if not dry_run:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = logging.handlers.RotatingFileHandler(
                LOG_FILE, maxBytes=1_000_000, backupCount=5
            )
        except OSError:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream)


# ---------------------------------------------------------------------------
# Pure functions — classification, budget, janitor selection. No I/O. These
# are what scripts/tests/test_queue_shepherd.py exercises directly.
# ---------------------------------------------------------------------------


def classify_ejection_reason(reason_raw: str | None, infra_hint: bool | None) -> str:
    """Map a RemovedFromMergeQueueEvent's raw `reason` (or None if no event was found at all)
    to a declared bucket in EJECTION_CLASSES. Mirrors
    queue_ejection_attribution.py::classify_removal_reason by declared design (duplicated, not
    imported — see module docstring).

    `reason_raw is None` means "no ejection event was found on the PR's timeline at all" — the
    PR looks disarmed right now but this script cannot say why. That is UNKNOWN, not CODE: never
    assume comprehension it does not have.
    """
    if reason_raw is None:
        return "UNKNOWN"
    if reason_raw == "failed_checks":
        if infra_hint is True:
            return "INFRA"
        return "CODE"  # infra_hint False or None — conservative default, never invented INFRA
    if reason_raw == "manual":
        return "MANUAL"
    if reason_raw == "merge_conflict":
        return "CONFLICT"
    return "UNKNOWN"  # a reason string this module has never seen — fail visible, never guessed


def _run_has_infra_signature(run: dict[str, Any], jobs: list[dict[str, Any]]) -> bool:
    """Mirrors queue_ejection_attribution.py::_run_is_infra_flavoured (duplicated, not
    imported — see module docstring). Caller only invokes this for a run that already failed.

    CODE wins over cancelled siblings (refuter round, agy pass, 2026-08-27): a matrix workflow
    with fail-fast cancels every OTHER job the instant one job fails for real. That cancellation
    is a symptom of the real failure, not an infra signal of its own — so a run containing ANY
    job that failed for a non-infra reason is CODE, full stop, even if the fail-fast cascade also
    cancelled its siblings. Only when NO job failed for a real reason do cancelled/timed-out jobs
    (or the run's own cancelled/timed-out conclusion) count as INFRA."""
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        name = str(job.get("name") or "").lower()
        if not _is_infra_job_name(name):
            return False  # a real (non-infra-flavoured) job failure -> CODE, regardless of siblings
    if run.get("conclusion") in ("cancelled", "timed_out"):
        return True
    for job in jobs:
        job_conclusion = job.get("conclusion")
        if job_conclusion in ("cancelled", "timed_out"):
            return True
        name = str(job.get("name") or "").lower()
        if job_conclusion == "failure" and _is_infra_job_name(name):
            return True
    return False


def red_cause_fingerprint(run: dict[str, Any] | None, jobs: list[dict[str, Any]]) -> str | None:
    """Pure: a stable fingerprint for WHY a merge_group run failed, used to detect the Builder
    Contract §1 condition ("three reds for the SAME cause and the PR suspends instead of taking a
    fourth round"). `run`/`jobs` are the SAME correlated-run + jobs pair _run_has_infra_signature
    already receives (see fetch_infra_hint_and_fingerprint, the single fetch both now share).

    None means "no correlated run" (or nothing failed on it) and must NEVER itself count as a
    repeated cause — the caller (run_rearm_pass) never lets a None fingerprint contribute toward
    RED_SAME_CAUSE_LIMIT, however many pile up."""
    if run is None:
        return None
    name = str(run.get("name") or "")
    failed_job_names = sorted(
        str(job.get("name") or "")
        for job in jobs
        if job.get("conclusion") in ("failure", "timed_out")
    )
    if failed_job_names:
        return f"{name}::{'|'.join(failed_job_names)}"
    # B3(c) (Codex review, 2026-09-11): no job failed/timed_out for real, but some WERE cancelled
    # (e.g. a fail-fast sibling of a real failure this correlation didn't see) — a job-level
    # cancelled fingerprint is more specific than the coarser run-level fallback below, so it
    # wins whenever it exists.
    cancelled_job_names = sorted(
        str(job.get("name") or "") for job in jobs if job.get("conclusion") == "cancelled"
    )
    if cancelled_job_names:
        return f"{name}::cancelled:{'|'.join(cancelled_job_names)}"
    if run.get("conclusion") in ("cancelled", "timed_out"):
        return f"{name}::run:{run.get('conclusion')}"
    return None  # no job-level detail and the run's own conclusion doesn't say infra either


def is_rearm_candidate(pr: dict[str, Any]) -> bool:
    """Pure gate: is this open PR a re-arm candidate this tick?

    `pr` fields expected: is_draft, head_ref_name, has_fable_gate_status, in_queue,
    auto_merge_enabled, merge_state_status, status_rollup_state.

    W111 guard (`docs/scars/cicatrix-scars.md` ~line 160): neither `autoMergeRequest` nor
    `mergeQueueEntry`/`isInMergeQueue` ALONE says "armed" — a queued PR has autoMergeRequest
    consumed (null) while carrying mergeQueueEntry; an armed-but-not-yet-queued PR has the
    inverse. Only BOTH null means truly disarmed, which is the only state this organ may act on.
    """
    if pr.get("is_draft"):
        return False
    if pr.get("in_queue") or pr.get("auto_merge_enabled"):
        return False  # already armed or already queued — W111, not our concern
    head_ref = pr.get("head_ref_name") or ""
    if not (head_ref.startswith("agent/") or pr.get("has_fable_gate_status")):
        return False  # not armed by this repo's own convention — never touch a PR we didn't arm
    status = pr.get("merge_state_status")
    if status in ("CLEAN", "UNSTABLE"):
        return True
    if status == "BLOCKED" and pr.get("status_rollup_state") == "SUCCESS":
        return True  # blocked on a review/approval gate, not on a red check
    return False


def _parse_iso(ts: str | None) -> _dt.datetime | None:
    """Returns an AWARE (UTC) datetime, or None. Every real caller compares the result against
    `_now()` (always tz-aware) — a naive result would raise TypeError at comparison time
    (uncaught anywhere between here and `tick()`, i.e. a full tick crash), not at parse time,
    which is why this went unnoticed (refuter round, agy pass, 2026-08-27). GitHub API timestamps
    always carry a Z/offset in practice, but this function must not depend on that being true
    forever (a hand-edited state file, a future API shape) — so a parse that comes back naive is
    coerced to UTC-aware here, once, rather than trusted to every call site."""
    if not ts:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def count_recent_infra_rearms(
    budget_state: dict[str, Any], pr_number: int, head_sha: str, now: _dt.datetime
) -> int:
    """Pure: how many INFRA re-arms have already been RECORDED for this exact (PR, head SHA)
    within the trailing BUDGET_WINDOW_HOURS. A head-SHA change is a fresh key with zero prior
    re-arms by construction — this IS the "head moved = reset" rule from the council spec; no
    separate reset code path is needed."""
    key = f"{pr_number}:{head_sha}"
    entry = budget_state.get(key) or {}
    timestamps = entry.get("infra_rearm_timestamps") or []
    cutoff = now - _dt.timedelta(hours=BUDGET_WINDOW_HOURS)
    count = 0
    for ts_raw in timestamps:
        ts = _parse_iso(ts_raw)
        if ts is not None and ts >= cutoff:
            count += 1
    return count


def record_infra_rearm(
    budget_state: dict[str, Any], pr_number: int, head_sha: str, now: _dt.datetime
) -> dict[str, Any]:
    """Pure: returns a NEW budget_state with this re-arm recorded. Never mutates the input dict
    in place (callers own persistence, mirrors dlq_autopilot.py's sweep-and-return contract)."""
    key = f"{pr_number}:{head_sha}"
    new_state = json.loads(json.dumps(budget_state))  # cheap deep copy, JSON-safe by contract
    entry = new_state.setdefault(key, {"infra_rearm_timestamps": []})
    entry["infra_rearm_timestamps"].append(now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    entry["pr_number"] = pr_number
    entry["head_sha"] = head_sha
    entry["last_seen"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return new_state


def gc_budget_state(budget_state: dict[str, Any], now: _dt.datetime) -> dict[str, Any]:
    """Pure: drop (pr, sha) entries whose every recorded timestamp is older than BUDGET_GC_DAYS,
    so the file never grows unbounded across the life of the repo. Never drops an entry that
    still has a timestamp inside the window — GC is a size bound, not a budget bypass."""
    cutoff = now - _dt.timedelta(days=BUDGET_GC_DAYS)
    kept: dict[str, Any] = {}
    for key, entry in budget_state.items():
        timestamps = entry.get("infra_rearm_timestamps") or []
        parsed = [t for t in (_parse_iso(ts) for ts in timestamps) if t is not None]
        if parsed and max(parsed) >= cutoff:
            kept[key] = entry
    return kept


def record_red(
    red_state: dict[str, Any], pr_number: int, removed_at: str, cause: str | None, head_sha: str
) -> dict[str, Any]:
    """Pure: returns a NEW red_state (never mutates the input) with one more red recorded for
    pr_number — PR-level, not head-level (unlike the INFRA budget, a new head SHA does NOT reset
    this; the recurring CAUSE is what matters, not the commit). Deduped by removed_at: the SAME
    RemovedFromMergeQueueEvent read again on a later tick (the timeline query re-reads the last
    10 items every time) must never double-count toward RED_SAME_CAUSE_LIMIT. No history cap
    (B3(a), Codex review 2026-09-11 — RED_HISTORY_MAX removed): a capped history could evict the
    very reds a same-cause count depends on once enough OTHER-cause reds piled up after them,
    silently losing progress toward RED_SAME_CAUSE_LIMIT. The file is bounded by the PR's
    lifetime instead — gc_red_state drops the whole entry once the PR is no longer open. A None
    cause is still recorded (for --report visibility) — count_same_cause_reds is what refuses to
    ever count it. B3(b): if the SAME removed_at is already recorded with cause None and this
    call resolves a real (non-None) cause, the existing entry is UPGRADED in place — a later
    tick correlating what an earlier tick could not must not be lost as a second, competing
    record of the identical event; an already-resolved cause is never downgraded back to None."""
    new_state = json.loads(json.dumps(red_state))  # cheap deep copy, JSON-safe by contract
    key = str(pr_number)
    entry = new_state.setdefault(key, {"reds": []})
    reds = entry.get("reds") or []
    for r in reds:
        if r.get("removed_at") == removed_at:
            if r.get("cause") is None and cause is not None:
                r["cause"] = cause
            return new_state  # dedup either way — never a second entry for the same event
    reds = reds + [{"removed_at": removed_at, "cause": cause, "head_sha": head_sha}]
    reds.sort(key=lambda r: r.get("removed_at") or "")
    entry["reds"] = reds
    return new_state


def count_same_cause_reds(reds: list[dict[str, Any]], cause: str | None) -> int:
    """Pure: how many reds in this PR's recorded history share EXACTLY `cause`. A None cause
    ALWAYS returns 0 — "no correlated run found" must never itself count as a repeated cause,
    however many pile up (Builder Contract §1's "same cause" only ever means a real, resolved
    fingerprint)."""
    if cause is None:
        return 0
    return sum(1 for r in reds if r.get("cause") == cause)


def gc_red_state(red_state: dict[str, Any], open_pr_numbers: set[int]) -> dict[str, Any]:
    """Pure: drop red-file entries whose PR number is no longer in THIS TICK's examined open-PR
    set. Suspension is sticky until the PR is no longer open — no time-based unsuspend — so the
    ONLY thing that ever clears an entry is the PR itself closing/merging. Caller must only call
    this after a SUCCESSFUL fetch_open_prs read (a partial/failed set would wrongly GC every
    entry as "not open")."""
    return {key: entry for key, entry in red_state.items() if int(key) in open_pr_numbers}


def gc_uncancellable_state(
    uncancellable_state: dict[str, Any], candidate_ids: set[str]
) -> dict[str, Any]:
    """Pure: drop any recorded run id that is no longer present in THIS TICK's candidate query
    (the janitor's own stale-run discovery, before skip-list filtering) — the run stopped showing
    up as a stale-queued candidate (GitHub finally resolved it, it aged past the queued-run query
    window, or the PR/queue branch it belonged to is simply gone), so remembering it forever would
    let the file grow unbounded. Presence-based, not time-based (unlike gc_budget_state): there is
    no useful TTL for "GitHub told us twice it cannot cancel this" — the only trustworthy signal
    that it is safe to forget an id is that the janitor no longer sees it at all."""
    return {run_id: entry for run_id, entry in uncancellable_state.items() if run_id in candidate_ids}


def record_cancel_failure(
    uncancellable_state: dict[str, Any], run_id: str, outcome: str, now: _dt.datetime
) -> dict[str, Any]:
    """Pure: returns a NEW uncancellable_state (never mutates the input) with one more failed
    cancel_run() attempt recorded against `run_id`. `outcome` is whatever cancel_run() returned
    as its second element on a FAILURE — "failed" or "uncancellable_409" (never "cancelled"; a
    success goes through clear_cancel_entry instead, never this function).

    QUARANTINE THRESHOLD (module docstring QUARANTINE section has the full incident this
    responds to): "uncancellable_409" — GitHub's plain-cancel AND force-cancel endpoints BOTH
    answered 409, the strongest signal this module can get that GitHub itself cannot resolve the
    run's state through either instrument — quarantines on the SAME tick it is first seen:
    consecutive_failures jumps straight to UNCANCELLABLE_FAILURE_THRESHOLD, because nothing is
    learned by retrying it three more times. "failed" (a plain non-409 error — HTTP 500, network
    blip, timeout) is treated as POSSIBLY transient and only increments the counter by one; the
    run is quarantined only once UNCANCELLABLE_FAILURE_THRESHOLD consecutive "failed" outcomes
    have landed on the identical run_id with no success in between.

    EXPIRY: quarantining sets/refreshes `quarantined_at` to `now`. is_quarantined() (below)
    treats a quarantine as expired UNCANCELLABLE_RETRY_COOLDOWN_HOURS after that timestamp, at
    which point the janitor allows exactly one retry attempt. If that retry fails again (this
    function is called again), `quarantined_at` is refreshed to the NEW `now`, restarting the
    cooldown — so a permanently-broken run is retried at most once per cooldown window forever,
    never hammered every tick again. If the retry SUCCEEDS, the caller uses clear_cancel_entry
    instead of this function, dropping the entry outright — that is the other way a quarantine
    ends ("reset the counter if a later attempt succeeds")."""
    new_state = json.loads(json.dumps(uncancellable_state))  # cheap deep copy, JSON-safe by contract
    entry = new_state.setdefault(run_id, {"consecutive_failures": 0})
    if outcome == "uncancellable_409":
        entry["consecutive_failures"] = max(
            entry.get("consecutive_failures", 0), UNCANCELLABLE_FAILURE_THRESHOLD
        )
    else:
        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
    entry["last_error"] = _UNCANCELLABLE_ERROR_LABELS.get(outcome, outcome)
    entry["last_attempt_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if entry["consecutive_failures"] >= UNCANCELLABLE_FAILURE_THRESHOLD:
        entry["quarantined_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")  # (re)start the cooldown
    return new_state


def clear_cancel_entry(uncancellable_state: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Pure: a successful cancel_run() (outcome == "cancelled") drops any tracked failure state
    for run_id entirely — "reset the counter if a later attempt succeeds". A no-op (returns the
    SAME object, not a copy) when run_id was never tracked, which is the common case since most
    cancels succeed on the first try — mirrors gc_uncancellable_state's own no-op-when-absent
    convention just below it."""
    if run_id not in uncancellable_state:
        return uncancellable_state
    new_state = json.loads(json.dumps(uncancellable_state))
    new_state.pop(run_id, None)
    return new_state


def is_quarantined(entry: dict[str, Any] | None, now: _dt.datetime) -> bool:
    """Pure: True if a run tracked by `entry` (its uncancellable_state record, or None/{} if
    untracked) should be SKIPPED this tick. An entry with no `quarantined_at` yet (still under
    UNCANCELLABLE_FAILURE_THRESHOLD consecutive failures) is never skipped — it is still being
    retried every tick, exactly like an untracked run. A quarantined entry stops being skipped
    once UNCANCELLABLE_RETRY_COOLDOWN_HOURS have elapsed since `quarantined_at` — see
    record_cancel_failure's docstring for what happens on that retry, in both directions."""
    if not entry:
        return False
    quarantined_at = _parse_iso(entry.get("quarantined_at"))
    if quarantined_at is None:
        return False
    return now < quarantined_at + _dt.timedelta(hours=UNCANCELLABLE_RETRY_COOLDOWN_HOURS)


def decide_rearm(
    klass: str, budget_state: dict[str, Any], pr_number: int, head_sha: str, now: _dt.datetime
) -> tuple[bool, str]:
    """Pure decision: (allowed, reason_code). Never mutates budget_state — the caller records a
    successful INFRA re-arm separately via record_infra_rearm, only after the real `gh` call
    (recorded by outcome in production, immediately in tests) succeeds."""
    if klass == "INFRA":
        count = count_recent_infra_rearms(budget_state, pr_number, head_sha, now)
        if count >= INFRA_BUDGET_MAX:
            return False, f"infra_budget_exhausted({count}/{INFRA_BUDGET_MAX})"
        return True, f"infra_budget_ok({count}/{INFRA_BUDGET_MAX})"
    if klass == "CODE":
        return False, "code_never_rearm"
    if klass in ("CONFLICT", "MANUAL"):
        return False, f"{klass.lower()}_no_auto_rearm"
    if klass == "NEVER_QUEUED":
        # letter F, S1 2026-09-10: a PR that never went through the merge queue at all is not an
        # ejection this organ caused or should act on — never the same bucket as a genuinely
        # unreadable ejection reason (UNKNOWN), and never alerted on (Mini's stall notifier
        # already reports the disarmed PR).
        return False, "never_queued_not_ours"
    return False, "unknown_fail_closed"  # UNKNOWN, or any class this module has never seen


def select_stale_pull_request_runs(
    queued_runs: list[dict[str, Any]], live_pr_heads: set[str]
) -> list[dict[str, Any]]:
    """Pure: `pull_request`-event queued runs whose head_sha is not the CURRENT head of any
    open PR. A run whose head_sha IS a live PR head is never selected, however old the run —
    liveness is the only test, never age (a slow runner queue is not this organ's business)."""
    return [
        run
        for run in queued_runs
        if run.get("event") == "pull_request" and run.get("head_sha") not in live_pr_heads
    ]


def select_stale_merge_group_runs(
    queued_runs: list[dict[str, Any]], live_queue_branches: set[str]
) -> list[dict[str, Any]]:
    """Pure: `merge_group`-event queued runs whose head_branch no longer exists as a live
    gh-readonly-queue ref — the queue already ejected or merged that entry."""
    return [
        run
        for run in queued_runs
        if run.get("event") == "merge_group" and run.get("head_branch") not in live_queue_branches
    ]


# ---------------------------------------------------------------------------
# I/O — subprocess + gh wrappers. Monkeypatched wholesale in tests (same seam
# convention as queue_unstick.py / queue_ejection_attribution.py: a module-level
# `_run`, replaced by the test, never a mock library).
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command; never raises. Returns (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def _gh_graphql(query: str, variables: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    """Raises RuntimeError on any failure — never returns a fabricated empty structure
    (superscar #2/#9: a failed fetch must never be read as 'nothing to do')."""
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        flag = "-F" if isinstance(value, (int, bool)) else "-f"
        args += [flag, f"{key}={value}"]
    rc, out, err = _run(args, timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"gh api graphql failed rc={rc}: {err.strip()[:500]}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"unparseable graphql response: {exc!s}: {out[:300]}") from exc


def _expect_list(obj: Any, key: str, where: str) -> list:
    """The read contract (H, S1 spec R2): a read is a response whose SHAPE is what the code
    consumes — anything else is a failed read, never a fabricated empty list. Raises RuntimeError
    when `obj` is not a dict or `obj[key]` is not a list; `{key: []}` stays legitimate."""
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(obj, dict) or not isinstance(value, list):
        raise RuntimeError(f"{where}: expected a dict with list '{key}', got: {str(obj)[:300]}")
    return value


def _expect_total_count(obj: dict[str, Any], items: list, where: str) -> None:
    """J (S1 spec R3): completeness guard for a read that is small BY CONSTRUCTION (a per-sha or
    per-run page, never a `created<=` sweep over the repo's whole history — that total_count can
    never serve as a completeness check, see fetch_infra_hint_and_fingerprint's docstring).
    Raises RuntimeError unless `total_count` is an int with total_count <= len(items): a larger
    total means THIS read is incomplete, never that the attempt/job set is legitimately big."""
    total_count = obj.get("total_count")
    if not isinstance(total_count, int) or isinstance(total_count, bool) or total_count > len(items):
        raise RuntimeError(
            f"{where}: total_count guard failed: total_count={total_count!r} len={len(items)}"
        )


def _expect_pull_requests_page(data: Any, where: str) -> dict[str, Any]:
    """H3/H4 (S1 spec R2): the GraphQL pullRequests connection shape shared by fetch_open_prs
    (via _fetch_candidates_page, with a retry) and fetch_open_pr_heads (no retry). Raises
    RuntimeError unless data.repository.pullRequests is a dict, 'nodes' is a list, 'pageInfo' is
    a dict with a bool 'hasNextPage', and — when hasNextPage is True — 'endCursor' is a non-empty
    str. `nodes: []` stays legitimate."""
    try:
        page = data["data"]["repository"]["pullRequests"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"{where}: unexpected graphql shape: {exc}: {str(data)[:300]}") from exc
    _expect_list(page, "nodes", where)
    page_info = page.get("pageInfo") if isinstance(page, dict) else None
    if not isinstance(page_info, dict) or not isinstance(page_info.get("hasNextPage"), bool):
        raise RuntimeError(f"{where}: pageInfo malformed: {str(page_info)[:300]}")
    if page_info["hasNextPage"] and not (
        isinstance(page_info.get("endCursor"), str) and page_info["endCursor"]
    ):
        raise RuntimeError(
            f"{where}: hasNextPage True but endCursor missing/empty: {str(page_info)[:300]}"
        )
    return page


REARM_CANDIDATES_QUERY = """
query($owner:String!, $repo:String!, $cursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequests(states:OPEN, first:50, after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        isDraft
        headRefName
        headRefOid
        mergeStateStatus
        autoMergeRequest { enabledAt }
        mergeQueueEntry { state }
        commits(last:1) {
          nodes {
            commit {
              statusCheckRollup { state }
              status { contexts { context } }
            }
          }
        }
      }
    }
  }
}
"""


def _pr_has_fable_gate_status(node: dict[str, Any]) -> bool:
    # checkRuns branch removed 2026-09-10 (S1 disposition): no workflow job / check-run is ever
    # named harness-floor / harness/fable-gate (the floor check-run is "Harness floor recompute");
    # harness/fable-gate is a commit STATUS context posted by scripts/harness_fable_gate.py. The
    # dropped checkSuites(first:20){checkRuns(first:20){...}} line was also dead weight against
    # GitHub's query-cost limit — see the module docstring's S1 section for the measured numbers.
    commits = (node.get("commits") or {}).get("nodes") or []
    if not commits:
        return False
    commit = commits[0].get("commit") or {}
    contexts = [c.get("context") for c in ((commit.get("status") or {}).get("contexts") or [])]
    return any(ctx in FABLE_GATE_CONTEXT_NAMES for ctx in contexts if ctx)


def _normalize_rearm_pr(node: dict[str, Any]) -> dict[str, Any]:
    commits = (node.get("commits") or {}).get("nodes") or []
    rollup_state = None
    if commits:
        rollup_state = ((commits[0].get("commit") or {}).get("statusCheckRollup") or {}).get(
            "state"
        )
    return {
        "number": node["number"],
        "is_draft": bool(node.get("isDraft")),
        "head_ref_name": node.get("headRefName") or "",
        "head_sha": node.get("headRefOid") or "",
        "merge_state_status": node.get("mergeStateStatus"),
        "auto_merge_enabled": bool(node.get("autoMergeRequest")),
        "in_queue": bool(node.get("mergeQueueEntry")),
        "status_rollup_state": rollup_state,
        "has_fable_gate_status": _pr_has_fable_gate_status(node),
    }


def _fetch_candidates_page(variables: dict[str, Any]) -> dict[str, Any]:
    """One retry, after RETRY_BACKOFF_SECONDS, for a single REARM_CANDIDATES_QUERY page. A
    second consecutive failure propagates RuntimeError unchanged (see _gh_graphql) — CANNOT-
    VERIFY must never be swallowed by a retry that also failed. H3 (S1 spec R2): a malformed-
    shape response (via _expect_pull_requests_page) is retried exactly like a transport failure,
    through this same except branch."""
    try:
        data = _gh_graphql(REARM_CANDIDATES_QUERY, variables)
        _expect_pull_requests_page(data, "candidate page")
        return data
    except RuntimeError as exc:
        logger.warning(
            "candidate page fetch failed, retrying once after %ss: %s", RETRY_BACKOFF_SECONDS, exc
        )
        _sleep(RETRY_BACKOFF_SECONDS)
        data = _gh_graphql(REARM_CANDIDATES_QUERY, variables)
        _expect_pull_requests_page(data, "candidate page")
        return data


def fetch_open_prs(repo: str = REPO) -> list[dict[str, Any]]:
    """Every open PR, normalized (via _normalize_rearm_pr) but NOT filtered through
    is_rearm_candidate — the caller learns how many PRs were examined, how many carry
    mergeStateStatus UNKNOWN, and the full open-PR number set (for GC) before any candidate
    filtering happens. One retry per page (_fetch_candidates_page); a second failure raises —
    CANNOT-VERIFY must never be read as an empty list. `fetch_rearm_candidate_prs` below is a
    filtering wrapper over this — no double fetch."""
    owner, name = repo.split("/", 1)
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        variables: dict[str, Any] = {"owner": owner, "repo": name}
        if cursor:
            variables["cursor"] = cursor
        data = _fetch_candidates_page(variables)
        # H3 (S1 spec R2): shape is already guaranteed by _fetch_candidates_page's own
        # _expect_pull_requests_page call — this navigation can no longer raise KeyError/TypeError.
        page = data["data"]["repository"]["pullRequests"]
        for node in page["nodes"]:
            out.append(_normalize_rearm_pr(node))
        if page["pageInfo"]["hasNextPage"]:
            cursor = page["pageInfo"]["endCursor"]
        else:
            break
    return out


def fetch_rearm_candidate_prs(repo: str = REPO) -> list[dict[str, Any]]:
    """Every open PR, normalized + filtered through is_rearm_candidate. Raises on fetch
    failure (see fetch_open_prs) — CANNOT-VERIFY must never be read as an empty candidate list."""
    return [pr for pr in fetch_open_prs(repo) if is_rearm_candidate(pr)]


TIMELINE_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      timelineItems(last:10, itemTypes:[REMOVED_FROM_MERGE_QUEUE_EVENT, ADDED_TO_MERGE_QUEUE_EVENT]) {
        nodes {
          __typename
          ... on RemovedFromMergeQueueEvent { createdAt reason beforeCommit { oid } }
          ... on AddedToMergeQueueEvent { createdAt }
        }
      }
    }
  }
}
"""


def fetch_last_ejection(repo: str, number: int) -> dict[str, Any] | None | str:
    """The PR's most recent timeline item among Added/Removed-from-merge-queue events. Returns:
      - a dict (reason/removed_at/before_commit) when the last item is a Removed event.
      - None when the last item is an Added event — queued, then vanished with no Removed event
        on record. The caller must treat this as UNKNOWN, never as CODE (unchanged from before
        letter F).
      - the literal string "NEVER_QUEUED" when there is NO Added/Removed timeline item at all —
        the PR was simply never through the merge queue, ever (letter F, S1 2026-09-10). This is
        NOT the same "unknown" as the Added-last case: a PR that never queued is not an ejection
        this organ caused or should alert on, so it must never collapse into the same None the
        Added-last case returns — the two need different tick outcomes (silent no-op vs a P0
        alert). Never a plain None: that would make NEVER_QUEUED indistinguishable from
        Added-last at the call site.

    Raises on fetch failure (see _gh_graphql)."""
    owner, name = repo.split("/", 1)
    data = _gh_graphql(TIMELINE_QUERY, {"owner": owner, "repo": name, "number": number})
    try:
        timeline_items = data["data"]["repository"]["pullRequest"]["timelineItems"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"unexpected graphql shape: {exc}: {json.dumps(data)[:300]}") from exc
    # H5 (S1 spec R2): `nodes` must be a list; a `null`/non-list value raises instead of silently
    # becoming NEVER_QUEUED (a malformed read is a failed read, never a legitimate empty answer).
    nodes = _expect_list(timeline_items, "nodes", "fetch_last_ejection timeline")
    if not nodes:
        return "NEVER_QUEUED"
    last = nodes[-1]
    if last.get("__typename") != "RemovedFromMergeQueueEvent":
        return None
    return {
        "reason": last.get("reason"),
        "removed_at": last.get("createdAt"),
        "before_commit": (last.get("beforeCommit") or {}).get("oid"),
    }


def _fetch_run_jobs(owner: str, name: str, run_id: int) -> list[dict[str, Any]]:
    """H2 (S1 spec R2) + J2 (S1 spec R3): one run's jobs list, `per_page=100`. Raises RuntimeError
    on a failed fetch, a malformed body (`jobs` missing or not a list), or a `total_count` larger
    than the page returned (J2 — the read is incomplete, never guess); `{"jobs": [],
    "total_count": 0}` is legitimate."""
    rc, jobs_out, jobs_err = _run(
        ["gh", "api", f"repos/{owner}/{name}/actions/runs/{run_id}/jobs?per_page=100"],
        timeout=30,
    )
    if rc != 0:
        raise RuntimeError(f"fetch_infra_hint: gh api jobs failed rc={rc}: {jobs_err.strip()[:300]}")
    try:
        parsed = json.loads(jobs_out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"fetch_infra_hint: unparseable jobs response: {exc!s}: {jobs_out[:300]}"
        ) from exc
    jobs = _expect_list(parsed, "jobs", "fetch_infra_hint jobs")
    _expect_total_count(parsed, jobs, "fetch_infra_hint jobs")
    return jobs


def _fetch_attempt_runs_by_head_sha(
    owner: str, name: str, number: int, head_sha: str, removed_dt: _dt.datetime | None
) -> list[dict[str, Any]]:
    """J1 (S1 spec R3, Kimi F1 BLOCKER, dispositioned by the Dux 2026-09-10): re-read the queue
    attempt by its OWN head_sha rather than trusting the first read's page. Measured live:
    `actions/runs?event=merge_group&head_sha=<sha>&per_page=100` returns exactly one attempt (13
    runs, total_count 13, one head_sha) — a read that is small BY CONSTRUCTION, so `total_count`
    can validly guard its own completeness here (unlike the first read's `created<=` sweep, where
    total_count is the repository's whole history and total_count<=len would CANNOT-VERIFY every
    tick — Kimi's originally suggested fix). Raises RuntimeError on a failed fetch, a malformed
    body, a total_count exceeding the runs returned, or (the latest candidate itself must be in
    its own attempt) an empty match."""
    url = f"repos/{owner}/{name}/actions/runs?event=merge_group&head_sha={head_sha}&per_page=100"
    rc, out, err = _run(["gh", "api", url], timeout=30)
    if rc != 0:
        raise RuntimeError(f"fetch_infra_hint: gh api per-sha runs failed rc={rc}: {err.strip()[:300]}")
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"fetch_infra_hint: unparseable per-sha runs response: {exc!s}: {out[:300]}"
        ) from exc
    runs = _expect_list(parsed, "workflow_runs", "fetch_infra_hint per-sha runs")
    _expect_total_count(parsed, runs, "fetch_infra_hint per-sha runs")
    attempt_runs = []
    for r in runs:
        match = PR_SHA_RE.search(str(r.get("head_branch") or ""))
        if (
            match
            and int(match.group(1)) == number
            and r.get("conclusion") in ("failure", "cancelled", "timed_out")
        ):
            attempt_runs.append(r)
    if removed_dt is not None:
        attempt_runs = [
            r for r in attempt_runs
            if (_parse_iso(r.get("created_at")) or removed_dt) <= removed_dt
        ]
    if not attempt_runs:
        raise RuntimeError(
            f"fetch_infra_hint: per-sha re-read for {head_sha} matched no attempt runs for PR #{number}"
        )
    return attempt_runs


def fetch_infra_hint_and_fingerprint(
    repo: str, number: int, removed_at: str | None
) -> tuple[bool | None, str | None]:
    """One runs-list fetch, plus one jobs fetch per run in the correlated ATTEMPT (I3, S1 spec
    R2, via _fetch_run_jobs), yielding BOTH the existing best-effort INFRA correlation (see
    fetch_infra_hint, now a thin wrapper over this — letter E, S1 2026-09-10) AND a same-cause
    fingerprint (red_cause_fingerprint) for the Builder Contract §1 suspension.

    Best-effort, honest about its own gap: this looks at the PR's most recent merge_group runs by
    branch-name prefix (`pr-<number>-`), NOT an exhaustive day-window reconstruction like
    queue_ejection_attribution.py's audit-grade version — that module exists for retrospective
    accuracy across a whole day; this one exists to make ONE re-arm decision right now, and a
    None (unresolved) hint here falls through to the conservative CODE default in
    classify_ejection_reason, never to a guessed INFRA. "No correlated run found" (a genuinely
    resolved, non-failure answer) stays (None, None) — but a FAILED or unparseable read (the runs
    list, or any attempt run's jobs list — H1/H2) now RAISES RuntimeError: before this fix a read
    failure silently collapsed to the SAME (None, None) a clean "nothing correlates" answer
    produces, which a jobs-fetch failure in particular made actively wrong — jobs=[] on a run
    whose own conclusion is cancelled/timed_out reads as INFRA (_run_has_infra_signature's OWN
    documented rule), so a transient jobs-fetch error could get a PR re-armed on a fabricated
    INFRA verdict. The caller (run_rearm_pass, via B2) turns this raise into a CANNOT-VERIFY
    outcome, never a guess.

    ONE QUEUE ATTEMPT (I, S1 spec R2): a merge-queue attempt launches ~13 runs sharing one
    head_sha; the old tie-break `candidates.sort()[0]` picked an arbitrary sibling of the attempt
    (a `cancelled` run instead of the real `failure` run) and read it alone. The runs list is now
    fetched with `per_page=100` plus `created=<=<removed_at>` server-side (removed_at None omits
    it), the prior client-side `created_at <= removed_at` filter kept as a second fence. The
    ATTEMPT: the latest failing candidate by (created_at, id) defines head_sha; every failing
    candidate sharing that head_sha is the attempt (just that one run if head_sha is missing); an
    older attempt of the same PR (a different head_sha) is never mixed in. `infra` is `all()`
    across the attempt's runs — CODE wins across runs exactly as it wins across one run's jobs, a
    DELIBERATE divergence from queue_ejection_attribution.py's ANY rule (that module is
    retrospective; this one makes a re-arm decision and fails closed). `fingerprint` is the
    sorted, deduped, "||"-joined union of each run's own fingerprint — independent of API order.

    RE-READ BY HEAD_SHA (J1, S1 spec R3): this first read's `per_page=100` page can still cut the
    ejecting attempt's ~13-run cluster at the page boundary -- the real `failure` run falls off
    while a `cancelled` sibling stays, and `all()` over that surviving subset alone would read
    INFRA (a CODE failure re-armed on a read that reports itself successful). So once the latest
    failing candidate is picked above and it carries a head_sha, the attempt's OWN runs are not
    taken from this first read's `candidates` -- they are RE-FETCHED, scoped server-side by that
    head_sha (`_fetch_attempt_runs_by_head_sha`), which is what lets `total_count` legitimately
    guard completeness on that second, small-by-construction read. A candidate missing head_sha
    still stays alone (no second read to scope by).
    """
    owner, name = repo.split("/", 1)
    removed_dt = _parse_iso(removed_at)
    url = f"repos/{owner}/{name}/actions/runs?event=merge_group&per_page=100"
    if removed_dt is not None:
        url += f"&created=<={removed_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    rc, out, err = _run(["gh", "api", url], timeout=30)
    if rc != 0:
        raise RuntimeError(f"fetch_infra_hint: gh api runs failed rc={rc}: {err.strip()[:300]}")
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"fetch_infra_hint: unparseable runs response: {exc!s}: {out[:300]}") from exc
    # H1 (S1 spec R2): `workflow_runs` must be a list — a malformed body (e.g. `{}`) raises
    # instead of silently becoming `[]` (which used to make a cancelled sibling read as "no
    # correlated run found", a legitimate-looking but fabricated answer).
    runs = _expect_list(parsed, "workflow_runs", "fetch_infra_hint runs")
    # W111-adjacent fix (refuter round, agy pass, 2026-08-27): a merge_group run's real
    # head_branch is the full `gh-readonly-queue/main/pr-<n>-<sha>` ref, never a bare
    # `pr-<n>-<sha>` — a plain .startswith(f"pr-{number}-") NEVER matches it. PR_SHA_RE is
    # matched anywhere in the ref, and the captured PR number is compared numerically so it
    # never confuses PR #4 with PR #47.
    candidates = []
    for r in runs:
        match = PR_SHA_RE.search(str(r.get("head_branch") or ""))
        if (
            match
            and int(match.group(1)) == number
            and r.get("conclusion") in ("failure", "cancelled", "timed_out")
        ):
            candidates.append(r)
    if removed_dt is not None:
        candidates = [
            r for r in candidates if (_parse_iso(r.get("created_at")) or removed_dt) <= removed_dt
        ]
    if not candidates:
        return None, None
    # I2: the attempt = the latest failing candidate by (created_at, id); its head_sha defines
    # every OTHER run of the same attempt. A candidate missing head_sha stands alone.
    latest = max(candidates, key=lambda r: (r.get("created_at") or "", r.get("id") or 0))
    attempt_head_sha = latest.get("head_sha")
    if attempt_head_sha:
        # J1 (S1 spec R3): re-read the attempt by its own head_sha rather than trusting this
        # first read's page — see _fetch_attempt_runs_by_head_sha's docstring for why.
        attempt_runs = _fetch_attempt_runs_by_head_sha(owner, name, number, attempt_head_sha, removed_dt)
    else:
        attempt_runs = [latest]
    attempt_runs.sort(key=lambda r: r.get("id") or 0)
    # I3: one jobs fetch per run of the attempt — any failure raises (H2, via _fetch_run_jobs).
    jobs_by_id = {r["id"]: _fetch_run_jobs(owner, name, r["id"]) for r in attempt_runs}
    # I4: CODE wins across the attempt's runs (all() — see the docstring's ANY-vs-all divergence).
    infra = all(_run_has_infra_signature(r, jobs_by_id[r["id"]]) for r in attempt_runs)
    # I5: fingerprint independent of API order — a sorted, deduped, joined set.
    fingerprints = {red_cause_fingerprint(r, jobs_by_id[r["id"]]) for r in attempt_runs}
    fingerprints.discard(None)
    fingerprint = "||".join(sorted(fingerprints)) if fingerprints else None
    return infra, fingerprint


def fetch_infra_hint(repo: str, number: int, removed_at: str | None) -> bool | None:
    """Thin wrapper over fetch_infra_hint_and_fingerprint, kept for callers that only want the
    INFRA correlation (see that function's docstring for the shared single fetch)."""
    return fetch_infra_hint_and_fingerprint(repo, number, removed_at)[0]


def fetch_open_pr_heads(repo: str = REPO) -> set[str]:
    """Fresh set of CURRENT head SHAs for every open PR — used both to build the stale-run
    candidate set and, separately called again, to re-verify liveness immediately before each
    cancel. Raises on fetch failure."""
    owner, name = repo.split("/", 1)
    query = """
    query($owner:String!, $repo:String!, $cursor:String) {
      repository(owner:$owner, name:$repo) {
        pullRequests(states:OPEN, first:100, after:$cursor) {
          pageInfo { hasNextPage endCursor }
          nodes { headRefOid }
        }
      }
    }
    """
    heads: set[str] = set()
    cursor: str | None = None
    while True:
        variables: dict[str, Any] = {"owner": owner, "repo": name}
        if cursor:
            variables["cursor"] = cursor
        data = _gh_graphql(query, variables)
        # H4 (S1 spec R2): same page validator fetch_open_prs uses (via _fetch_candidates_page),
        # no retry added here.
        page = _expect_pull_requests_page(data, "fetch_open_pr_heads page")
        for node in page["nodes"]:
            sha = node.get("headRefOid")
            if sha:
                heads.add(sha)
        if page["pageInfo"]["hasNextPage"]:
            cursor = page["pageInfo"]["endCursor"]
        else:
            break
    return heads


def fetch_live_queue_branches(repo: str = REPO) -> set[str]:
    """Fresh set of live `gh-readonly-queue/main/...` ref names, paginated. Raises on fetch
    failure — the caller (run_janitor_pass and the per-run cancel-time recheck) already treats a
    RuntimeError here as CANNOT-VERIFY and cancels NOTHING that tick, so failing loud here is
    what keeps the janitor fail-closed rather than fail-open.

    Paginated (refuter round, agy pass, 2026-08-27): `git/matching-refs` defaults to 30 refs per
    page like every other GitHub REST list endpoint. Un-paginated, a busy merge queue with more
    than 30 live entries would silently drop the tail — and a branch missing from this set reads
    to `select_stale_merge_group_runs` as "already ejected", which cancels a run that is still
    building. Mirrors fetch_queued_runs's page-count loop + safety bound (W97 style)."""
    owner, name = repo.split("/", 1)
    branches: set[str] = set()
    page = 1
    while True:
        rc, out, err = _run(
            [
                "gh", "api",
                f"repos/{owner}/{name}/git/matching-refs/heads/gh-readonly-queue"
                f"?per_page=100&page={page}",
            ],
            timeout=30,
        )
        if rc != 0:
            raise RuntimeError(f"gh api matching-refs failed rc={rc}: {err.strip()[:300]}")
        try:
            refs = json.loads(out)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"unparseable matching-refs response: {exc!s}") from exc
        # H6 (S1 spec R2): the endpoint's own body is a bare list — malformed (e.g. a dict)
        # raises instead of a TypeError surfacing later at iteration time.
        if not isinstance(refs, list):
            raise RuntimeError(f"fetch_live_queue_branches: expected a list, got: {str(refs)[:300]}")
        for ref in refs:
            name_ref = str(ref.get("ref") or "")
            if name_ref.startswith("refs/heads/"):
                branches.add(name_ref[len("refs/heads/"):])
        if len(refs) < 100:
            break
        page += 1
        if page > 20:  # a 2,000-entry live queue is not a realistic shape; a safety bound
            logger.warning("fetch_live_queue_branches: hit page safety bound at page=%s", page)
            break
    return branches


def fetch_queued_runs(repo: str = REPO) -> list[dict[str, Any]]:
    """Every currently-QUEUED (never in_progress/completed) Actions run, paginated, normalized
    to {id, event, head_sha, head_branch, name}. Raises on fetch failure."""
    owner, name = repo.split("/", 1)
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        rc, body, err = _run(
            [
                "gh", "api",
                f"repos/{owner}/{name}/actions/runs?status=queued&per_page=100&page={page}",
            ],
            timeout=45,
        )
        if rc != 0:
            raise RuntimeError(f"gh api actions/runs failed rc={rc}: {err.strip()[:300]}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"unparseable actions/runs response: {exc!s}") from exc
        # H6 (S1 spec R2): `workflow_runs` must be a list; `{}` raises instead of becoming `[]`.
        runs = _expect_list(payload, "workflow_runs", "fetch_queued_runs")
        for run in runs:
            out.append(
                {
                    "id": run.get("id"),
                    "event": run.get("event"),
                    "head_sha": run.get("head_sha"),
                    "head_branch": run.get("head_branch"),
                    "name": run.get("name"),
                }
            )
        if len(runs) < 100:
            break
        page += 1
        if page > 20:  # 2,000 queued runs is not a realistic shape; a safety bound (W97 style)
            logger.warning("fetch_queued_runs: hit page safety bound at page=%s", page)
            break
    return out


def rearm_pr(repo: str, number: int) -> bool:
    """`gh pr merge N --auto` BARE — this repo's merge queue rejects every strategy flag
    (--squash included), per docs/runbooks/merge-queue-discipline.md session discipline."""
    rc, out, err = _run(["gh", "pr", "merge", str(number), "--auto", "--repo", repo], timeout=30)
    if rc != 0:
        logger.warning("rearm_pr(#%s) failed rc=%s out=%s err=%s", number, rc, out.strip()[:200], err.strip()[:200])
        return False
    return True


def cancel_run(repo: str, run_id: int) -> tuple[bool, str]:
    """Cancels a queued Actions run. Returns (cancelled, outcome), outcome one of:
      "cancelled"          — cancelled via the plain endpoint, or the force-cancel fallback.
      "uncancellable_409"  — BOTH the plain cancel AND the force-cancel fallback answered HTTP
                              409 ("not been queued yet") — a run whose real state GitHub itself
                              cannot resolve through either endpoint (measured live: post-outage
                              orphans left `status=queued` for 2-9 days). The caller may persist
                              this id to a skip-list; the run will never cancel by retrying —
                              GitHub's own two cancellation endpoints both refuse it.
      "failed"              — any other failure (non-409 on the first attempt, or the
                              force-cancel fallback failing with something other than 409, e.g.
                              the HTTP 500s seen on very old 3221xxxx runs). MUST NEVER enter the
                              skip-list — a transient error may simply succeed on a later tick.

    Post-outage (and on very old runs), GitHub's plain cancel endpoint answers HTTP 409 "Cannot
    cancel a workflow run that has not been queued yet" for a run whose real state has already
    moved past QUEUED — the janitor's own discovery-to-cancel gap, or GitHub settling state after
    an incident. On EXACTLY that 409 class, falls back once to the force-cancel endpoint, which
    GitHub accepts regardless of the run's current state. Force-cancel is deliberately NOT the
    default path — only the 409 fallback — because it is a stronger, less-reversible instrument
    than plain cancel and unconditional use would widen this guard past what the janitor's mandate
    (cancel stale QUEUED runs) actually needs.

    No retry loop lives here: superscar #2 (exist != armed) is exactly a "still working" façade
    that quietly burns a tick's time budget on a run that will never cancel — the janitor's own
    10-min tick cadence is the retry, not this call."""
    owner, name = repo.split("/", 1)
    rc, out, err = _run(
        ["gh", "api", "-X", "POST", f"repos/{owner}/{name}/actions/runs/{run_id}/cancel"],
        timeout=30,
    )
    if rc == 0:
        return True, "cancelled"
    if "HTTP 409" not in err:
        logger.warning("cancel_run(%s) failed rc=%s err=%s", run_id, rc, err.strip()[:200])
        return False, "failed"

    logger.info(
        "cancel_run(%s): plain cancel got HTTP 409 (not queued yet) — falling back to force-cancel",
        run_id,
    )
    fc_rc, fc_out, fc_err = _run(
        ["gh", "api", "-X", "POST", f"repos/{owner}/{name}/actions/runs/{run_id}/force-cancel"],
        timeout=30,
    )
    if fc_rc == 0:
        return True, "cancelled"
    if "HTTP 409" in fc_err:
        logger.warning(
            "cancel_run(%s): force-cancel ALSO got HTTP 409 — GitHub cannot resolve this run's "
            "state through either endpoint, marking uncancellable",
            run_id,
        )
        return False, "uncancellable_409"
    logger.warning(
        "cancel_run(%s): force-cancel fallback also failed rc=%s err=%s",
        run_id, fc_rc, fc_err.strip()[:200],
    )
    return False, "failed"


def send_telegram(message: str, dedup_key: str = "") -> bool:
    """Delegates to the repo's existing notification gateway (scripts/tg_notify.py — same
    convention scripts/dlq_autopilot.py already uses). The gateway owns token resolution
    (reads TELEGRAM_OWNER_CHAT_ID / bot token from the process env at send time), dedup and
    the daily P0 budget; this function never reads or hardcodes a chat id itself (mandate:
    the GitHub-secret path is for CI, a local organ reads the env — via the gateway).

    Returns whether the send actually succeeded (refuter round, agy pass, 2026-08-27): the
    caller must record `alerted_state` ONLY on a successful send, or a transient gateway/network
    failure on the FIRST attempt permanently swallows the alert — the dedup key would already be
    marked "delivered" for a message nobody ever received."""
    gateway = SCRIPTS_DIR / "tg_notify.py"
    if not gateway.exists():  # HOME-fork copy: fall back to the repo checkout (superscar #1)
        gateway = REPO_ROOT / "scripts" / "tg_notify.py"
    if not gateway.exists():
        logger.warning("send_telegram: tg_notify.py not found, skipping send")
        return False
    cmd = [sys.executable, str(gateway), "--tier", "p0", "--source", "queue-shepherd"]
    if dedup_key:
        cmd += ["--dedup-key", dedup_key]
    cmd += ["--", f"\U0001f9ed QueueShepherd | {message}"]
    rc, _out, err = _run(cmd, timeout=30)
    if rc != 0:
        logger.warning("send_telegram: tg_notify failed rc=%s err=%s", rc, err.strip()[:200])
        return False
    return True


# ---------------------------------------------------------------------------
# State (budget + alerted-dedup) persistence.
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    """A missing file means "no state yet" -> {} (normal on first run). A file that EXISTS but
    fails to parse (torn write, disk corruption, hand-edit gone wrong) is a different situation
    entirely and must never collapse to the same {} — that is precisely the "budget silently
    resets" bypass the council barred (refuter round, agy pass, 2026-08-27). Raises RuntimeError
    in that case so the caller can fail closed instead of granting a fresh, unlimited budget."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RuntimeError(f"unreadable state file {path}: {exc!s}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"corrupt/unparseable state file {path}: {exc!s}") from exc


def _save_json(path: Path, data: dict[str, Any]) -> None:
    """Atomic write: write-then-rename so a crash/kill mid-write never leaves a torn file for the
    next `_load_json` to trip over (refuter round, agy pass, 2026-08-27 — same finding as above,
    the other half of the fix). `os.replace` is atomic on the same filesystem, which the tmp file
    is guaranteed to be since it lives in the same parent directory as the real path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------------------------------------------------------------------
# Tick orchestration.
# ---------------------------------------------------------------------------


def _enabled() -> bool:
    return os.environ.get("QUEUE_SHEPHERD_ENABLED", "true").strip().lower() not in (
        "false", "0", "no", "off",
    )


def run_rearm_pass(dry_run: bool, now: _dt.datetime) -> dict[str, Any]:
    """Returns {rearmed, examined, candidates, unknown, suspended, unverified, cannot_verify,
    detail}. CANNOT-VERIFY is a tick OUTCOME the caller must surface, never silently folded into
    a zero (S1, 2026-09-10 — see the module docstring's S1 section for the measured incident this
    responds to). `cannot_verify` is None on a clean
    read, else "rearm_state" (budget/alerted state file corrupt) or "rearm_candidates" (the gh
    candidate-PR fetch failed after its one retry). `detail` carries the first 300 chars of the
    triggering exception, for tick()'s heartbeat/alert — not part of the spec-named fields, purely
    a passthrough. `unverified` counts candidates whose OWN per-PR timeline read failed (skipped
    that PR, not the whole tick).

    Fail-closed on state corruption (refuter round, agy pass, 2026-08-27): a torn/corrupt budget
    file must NEVER be read as "no re-arms recorded yet" — that silently grants a fresh
    INFRA_BUDGET_MAX allowance, exactly the bypass the council barred. `_load_json` now raises on
    a parse failure (vs. a simply-missing file, which is normal and returns {}); this pass treats
    that as CANNOT-VERIFY and re-arms NOTHING this tick, same posture as a `gh` fetch failure."""
    result: dict[str, Any] = {
        "rearmed": 0,
        "examined": 0,
        "candidates": 0,
        "unknown": 0,
        "suspended": 0,
        "unverified": 0,
        "cannot_verify": None,
        "detail": None,
    }
    try:
        # Letter G (S1, 2026-09-10): dry-run READS every state file — budget/alerted/red — same
        # as a live tick; only the WRITE at the end of this pass is skipped for dry_run. Before
        # this fix, dry-run substituted {} here, so a dry-run tick's rearm decisions (INFRA
        # budget, alerted-dedup, same-cause suspension) never matched what the SAME tick would
        # decide live — a dry-run's whole purpose is to preview the live decision.
        budget_state = _load_json(BUDGET_FILE)
        alerted_state = _load_json(ALERTED_FILE)
        red_state = _load_json(RED_FILE)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY rearm/alert/red state: %s", exc)
        result["cannot_verify"] = "rearm_state"
        result["detail"] = str(exc)[:300]
        return result
    budget_state = gc_budget_state(budget_state, now)

    try:
        all_prs = fetch_open_prs(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY rearm candidates: %s", exc)
        result["cannot_verify"] = "rearm_candidates"
        result["detail"] = str(exc)[:300]
        return result
    examined = len(all_prs)
    unknown = sum(1 for pr in all_prs if pr.get("merge_state_status") == "UNKNOWN")
    open_pr_numbers = {pr["number"] for pr in all_prs}
    red_state = gc_red_state(red_state, open_pr_numbers)  # only after a successful read
    candidates = [pr for pr in all_prs if is_rearm_candidate(pr)]
    result["examined"] = examined
    result["unknown"] = unknown
    result["candidates"] = len(candidates)

    rearmed = 0
    unverified = 0
    new_unknown_keys: list[str] = []  # collected, sent as ONE alert after the loop (MEDIUM fix)
    for pr in candidates:
        number = pr["number"]
        head_sha = pr["head_sha"]
        try:
            ejection = fetch_last_ejection(REPO, number)
        except RuntimeError as exc:
            # B2 (Codex review, 2026-09-11): a late per-PR read failure is CANNOT-VERIFY for the
            # WHOLE pass, never a quiet skip — before this fix `unverified` counted it but the
            # pass still reported cannot_verify=None, so a tick with every candidate unreadable
            # still logged as a clean success.
            logger.error("PR #%s: CANNOT-VERIFY ejection timeline: %s", number, exc)
            unverified += 1
            result["cannot_verify"] = "rearm_pr_reads"
            result["detail"] = str(exc)[:300]
            continue
        if ejection == "NEVER_QUEUED":
            # letter F, S1 2026-09-10: no Added/Removed timeline event at all — this PR never
            # went through the merge queue, so this is NOT an ejection this organ caused or
            # should act on. Never the same UNKNOWN bucket fetch_last_ejection's OTHER "no
            # signal" case (last item Added) uses — that one still fails closed AND alerts.
            klass = "NEVER_QUEUED"
            allowed, why = decide_rearm(klass, budget_state, number, head_sha, now)
            logger.info(
                "PR #%s head=%s class=%s allowed=%s (%s)", number, head_sha[:8], klass, allowed, why
            )
            continue
        reason_raw = ejection["reason"] if ejection else None
        infra_hint: bool | None = None
        fingerprint: str | None = None
        removed_at = ejection.get("removed_at") if ejection else None
        if reason_raw == "failed_checks":
            try:
                infra_hint, fingerprint = fetch_infra_hint_and_fingerprint(REPO, number, removed_at)
            except RuntimeError as exc:
                # B2 (Codex review, 2026-09-11): skip this PR outright on a failed infra-
                # correlation read — no re-arm decision, no red recorded this tick (the next
                # tick re-reads the SAME removed_at and records it then). Never silently fall
                # through with infra_hint=None, which used to look identical to the legitimate
                # "no correlated run found" answer.
                logger.error("PR #%s: CANNOT-VERIFY infra_hint fetch: %s", number, exc)
                unverified += 1
                result["cannot_verify"] = "rearm_pr_reads"
                result["detail"] = str(exc)[:300]
                continue
            if removed_at:  # a red = an observed failed_checks removal (Builder Contract §1)
                red_state = record_red(red_state, number, removed_at, fingerprint, head_sha)
        klass = classify_ejection_reason(reason_raw, infra_hint)
        allowed, why = decide_rearm(klass, budget_state, number, head_sha, now)

        pr_key = str(number)
        existing_suspended = (red_state.get(pr_key) or {}).get("suspended")
        if existing_suspended:
            allowed, why = False, f"suspended_same_cause({existing_suspended.get('cause')})"
            result["suspended"] += 1
        elif fingerprint is not None:
            reds = (red_state.get(pr_key) or {}).get("reds") or []
            if count_same_cause_reds(reds, fingerprint) >= RED_SAME_CAUSE_LIMIT:
                red_state.setdefault(pr_key, {"reds": reds})["suspended"] = {
                    "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "cause": fingerprint,
                }
                allowed, why = False, f"suspended_same_cause({fingerprint})"
                result["suspended"] += 1
                logger.warning("PR #%s suspended: 3 reds, same cause %s", number, fingerprint)

        logger.info(
            "PR #%s head=%s class=%s allowed=%s (%s)", number, head_sha[:8], klass, allowed, why
        )
        alert_key = f"{number}:{head_sha}"
        if not allowed:
            if klass == "UNKNOWN" and not alerted_state.get(alert_key):
                new_unknown_keys.append(alert_key)  # batched below (MEDIUM fix)
            continue
        if dry_run:
            logger.info("[dry-run] would run: gh pr merge %s --auto", number)
            rearmed += 1
            continue
        if rearm_pr(REPO, number):
            budget_state = record_infra_rearm(budget_state, number, head_sha, now)
            alerted_state.pop(alert_key, None)  # a live re-arm supersedes any stale alert
            rearmed += 1

    if new_unknown_keys and not dry_run:
        # MEDIUM (Codex review, 2026-09-11): ONE batched alert per tick listing every newly-
        # UNKNOWN PR, not one send per PR — a first tick with N newly-disarmed PRs used to fire
        # N separate Telegram sends. A DELIVERED send records EVERY listed key; a failed send
        # records none, so every key is retried together on the next tick (same posture as the
        # single-PR case this replaces).
        sorted_keys = sorted(new_unknown_keys)
        sent = send_telegram(
            "PRs look disarmed with no readable ejection reason — fail-closed, no auto-rearm. "
            "Needs a human look:\n" + "\n".join(f"  PR {k}" for k in sorted_keys),
            dedup_key="queue-shepherd-unknown-" + "+".join(sorted_keys),
        )
        if sent:
            for k in sorted_keys:
                alerted_state[k] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    result["rearmed"] = rearmed
    result["unverified"] = unverified
    if not dry_run:
        _save_json(BUDGET_FILE, budget_state)
        _save_json(ALERTED_FILE, alerted_state)
        _save_json(RED_FILE, red_state)
    return result


def run_janitor_pass(dry_run: bool) -> dict[str, Any]:
    """Returns {cancelled, cannot_verify, detail} — same CANNOT-VERIFY-is-an-outcome contract as
    run_rearm_pass (see its docstring). `cannot_verify` is None on a clean read, else one of
    "queued_runs" / "open_pr_heads" / "live_queue_branches" / "uncancellable_state" naming which
    fetch/state-load failed. Skips any run currently is_quarantined() (module docstring
    QUARANTINE section) — a quarantined id is never passed to cancel_run() at all, which is what
    actually stops the repeated-failure log line (see this module's test suite for the exact live
    incident this responds to)."""
    result: dict[str, Any] = {"cancelled": 0, "cannot_verify": None, "detail": None}
    try:
        queued_runs = fetch_queued_runs(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY queued runs: %s", exc)
        result["cannot_verify"] = "queued_runs"
        result["detail"] = str(exc)[:300]
        return result

    try:
        live_heads = fetch_open_pr_heads(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY open PR heads: %s", exc)
        result["cannot_verify"] = "open_pr_heads"
        result["detail"] = str(exc)[:300]
        return result
    try:
        live_branches = fetch_live_queue_branches(REPO)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY live queue branches: %s", exc)
        result["cannot_verify"] = "live_queue_branches"
        result["detail"] = str(exc)[:300]
        return result

    stale = select_stale_pull_request_runs(queued_runs, live_heads) + select_stale_merge_group_runs(
        queued_runs, live_branches
    )

    # Fail-closed on state corruption (same posture as run_rearm_pass's budget-file guard): a
    # torn/corrupt uncancellable skip-list must never be silently read as "nothing known
    # uncancellable" — that would burn this whole tick re-hammering ids GitHub has already told us
    # twice it cannot cancel. `_load_json` raises on a parse failure (vs. a simply-missing file,
    # which is normal and returns {}); this pass treats that as CANNOT-VERIFY and cancels NOTHING
    # this tick — placed AFTER the discovery fetches above so a corrupt skip-list never masks a
    # genuine "CANNOT-VERIFY queued runs" fetch failure as the same zero-action outcome.
    try:
        # Letter G (S1, 2026-09-10): dry-run READS the skip-list too — a quarantined run id must
        # be skipped in dry-run exactly as it would be live, or a dry-run tick over-reports
        # "would cancel" for runs the live janitor actually skips (measured live: reported
        # cancelled=6 for runs the live janitor skips). Only the WRITE below stays gated on
        # dry_run.
        uncancellable_state = _load_json(UNCANCELLABLE_FILE)
    except RuntimeError as exc:
        logger.error("CANNOT-VERIFY uncancellable skip-list: %s", exc)
        result["cannot_verify"] = "uncancellable_state"
        result["detail"] = str(exc)[:300]
        return result

    now = _now()
    skip_ids = {
        run_id for run_id, entry in uncancellable_state.items() if is_quarantined(entry, now)
    }
    to_process = [run for run in stale if str(run["id"]) not in skip_ids]
    skipped_count = len(stale) - len(to_process)
    if skipped_count:
        logger.info("skipping %s known-uncancellable runs", skipped_count)

    cancelled = 0
    for run in to_process:
        # Re-verify liveness AT CANCEL TIME with a fresh fetch — never trust the list above,
        # which may already be stale by the time this specific run is reached (mandate: "not
        # from a stale list").
        try:
            if run["event"] == "pull_request":
                still_stale = run["head_sha"] not in fetch_open_pr_heads(REPO)
            else:
                still_stale = run["head_branch"] not in fetch_live_queue_branches(REPO)
        except RuntimeError as exc:
            # B2 (Codex review, 2026-09-11): a failed cancel-time recheck is CANNOT-VERIFY for
            # the whole pass, not a quiet per-run skip — before this fix the run was skipped but
            # the pass still reported cannot_verify=None.
            logger.error("run %s: CANNOT-VERIFY at cancel-time recheck, skipping: %s", run["id"], exc)
            result["cannot_verify"] = "janitor_recheck"
            result["detail"] = str(exc)[:300]
            continue
        if not still_stale:
            logger.info("run %s (%s): became live between discovery and cancel, skipping", run["id"], run.get("name"))
            continue
        if dry_run:
            logger.info("[dry-run] would cancel run %s (%s, event=%s)", run["id"], run.get("name"), run["event"])
            cancelled += 1
            continue
        run_id = str(run["id"])
        ok, outcome = cancel_run(REPO, run["id"])
        if ok:
            logger.info("cancelled stale run %s (%s, event=%s)", run["id"], run.get("name"), run["event"])
            cancelled += 1
            uncancellable_state = clear_cancel_entry(uncancellable_state, run_id)
        else:
            uncancellable_state = record_cancel_failure(uncancellable_state, run_id, outcome, now)
            entry = uncancellable_state.get(run_id, {})
            if is_quarantined(entry, now):
                logger.warning(
                    "run %s (%s): quarantined after %s consecutive cancel failures (last=%s)",
                    run["id"], run.get("name"), entry.get("consecutive_failures"), outcome,
                )

    if not dry_run:
        candidate_ids = {str(run["id"]) for run in stale}
        uncancellable_state = gc_uncancellable_state(uncancellable_state, candidate_ids)
        _save_json(UNCANCELLABLE_FILE, uncancellable_state)
    result["cancelled"] = cancelled
    return result


def _write_heartbeat(status: str, metadata: dict[str, Any]) -> None:
    """Unconditional organism heartbeat sidecar — never raises (a heartbeat write must never
    break the run it is reporting on). Atomic write via tmp+replace, same pattern as
    dlq_autopilot.py's organ heartbeat."""
    try:
        ORGANISM_DIR.mkdir(parents=True, exist_ok=True)
        organ_path = ORGANISM_DIR / f"{ORGAN_ID}.json"
        organ_tmp = organ_path.with_suffix(f".json.tmp.{os.getpid()}")
        organ_tmp.write_text(
            json.dumps(
                {
                    "ts": time.time(),
                    "status": status,
                    "organ_id": ORGAN_ID,
                    "metadata": metadata,
                }
            )
        )
        organ_tmp.replace(organ_path)
    except Exception as exc:  # noqa: BLE001 — heartbeat must never break the run
        logger.warning("organ heartbeat emit failed: %s", exc)


def tick(dry_run: bool) -> int:
    if not _enabled():
        logger.info("QUEUE_SHEPHERD_ENABLED=false — no-op tick (receipt line, superscar #2)")
        # G5: a kill-switched organ is alive-but-idle, not silent — write an explicit
        # disabled heartbeat so the staleness monitor never mistakes this for a dead
        # organ (agy cross-family review, PR #5071: "disabled state is ambiguous").
        # B4 (Codex review, 2026-09-11): dry-run writes NOTHING, anywhere — including this path.
        if not dry_run:
            _write_heartbeat("disabled", {"reason": "QUEUE_SHEPHERD_ENABLED=false"})
        return 0
    now = _now()
    try:
        rearm_result = run_rearm_pass(dry_run, now)
        janitor_result = run_janitor_pass(dry_run)
    except Exception as exc:  # noqa: BLE001 — G2: heartbeat the failure path too, then re-raise
        if not dry_run:  # B4: no heartbeat write on the exception path in dry-run either
            _write_heartbeat("error", {"error": str(exc), "dry_run": dry_run})
        raise

    rearmed = rearm_result["rearmed"]
    cancelled = janitor_result["cancelled"]
    # The two passes stay independent — each already fails closed on its OWN cannot_verify
    # without raising, so both always ran this tick regardless of the other's outcome.
    cannot_verify_labels = [
        label for label in (rearm_result["cannot_verify"], janitor_result["cannot_verify"]) if label
    ]

    if cannot_verify_labels:
        # CANNOT-VERIFY is a tick OUTCOME, never a zero (S1, 2026-09-10 — see the module
        # docstring's S1 section for the measured incident this branch responds to).
        # examined/candidates are only unknowable when the LIST READ itself failed
        # (rearm_candidates/rearm_state, before examined/candidates are ever computed) — a "-"
        # makes that explicit. "rearm_pr_reads" fails AFTER that read succeeds, so examined/
        # candidates are real numbers then and must be printed, not masked.
        labels_str = ",".join(cannot_verify_labels)
        list_read_failed = rearm_result["cannot_verify"] in ("rearm_candidates", "rearm_state")
        examined_str = "-" if list_read_failed else str(rearm_result["examined"])
        candidates_str = "-" if list_read_failed else str(rearm_result["candidates"])
        logger.error(
            "tick complete: CANNOT-VERIFY=%s examined=%s candidates=%s rearmed=%s cancelled=%s "
            "dry_run=%s",
            labels_str, examined_str, candidates_str, rearmed, cancelled, dry_run,
        )
        details = [d for d in (rearm_result["detail"], janitor_result["detail"]) if d]
        if not dry_run:  # B4: no heartbeat write, no send, anywhere in dry-run
            _write_heartbeat(
                "error",
                {
                    "cannot_verify": cannot_verify_labels,
                    "error": "; ".join(details)[:300],
                    "dry_run": dry_run,
                },
            )
            # ONE dedup_key for every CANNOT-VERIFY label, so the gateway's dedup ladder turns
            # a whole outage into one alert, never one per tick per label.
            send_telegram(
                f"CANNOT-VERIFY ({labels_str}) this tick — it could not read, so nothing was "
                're-armed or cancelled on the unreadable side. This is NOT "nothing to do": '
                "needs a human look.",
                dedup_key="queue-shepherd:cannot-verify",
            )
        return 2

    logger.info(
        "tick complete: examined=%s candidates=%s unknown=%s rearmed=%s suspended=%s "
        "unverified=%s cancelled=%s dry_run=%s",
        rearm_result["examined"], rearm_result["candidates"], rearm_result["unknown"],
        rearmed, rearm_result["suspended"], rearm_result["unverified"], cancelled, dry_run,
    )
    if not dry_run:  # B4 (Codex review, 2026-09-11): dry-run writes nothing, anywhere
        _write_heartbeat(
            "ok",
            {
                "examined": rearm_result["examined"],
                "candidates": rearm_result["candidates"],
                "unknown": rearm_result["unknown"],
                "rearmed": rearmed,
                "suspended": rearm_result["suspended"],
                "unverified": rearm_result["unverified"],
                "cancelled": cancelled,
                "dry_run": dry_run,
            },
        )
    return 0


def report() -> int:
    try:
        budget_state = _load_json(BUDGET_FILE)
    except RuntimeError as exc:
        logger.error("%s", exc)
        print(f"budget file: {BUDGET_FILE} — CORRUPT, cannot parse ({exc})")
        budget_state = {}
    try:
        alerted_state = _load_json(ALERTED_FILE)
    except RuntimeError as exc:
        logger.error("%s", exc)
        print(f"alerted file: {ALERTED_FILE} — CORRUPT, cannot parse ({exc})")
        alerted_state = {}
    print(f"queue_shepherd report — repo={REPO} enabled={_enabled()}")
    print(f"budget file: {BUDGET_FILE} ({'exists' if BUDGET_FILE.exists() else 'missing'})")
    print(f"  tracked (pr,sha) keys: {len(budget_state)}")
    now = _now()
    for key, entry in sorted(budget_state.items()):
        count = count_recent_infra_rearms(
            budget_state, entry.get("pr_number", 0), entry.get("head_sha", ""), now
        )
        print(f"    {key}: {count}/{INFRA_BUDGET_MAX} infra rearms in last {BUDGET_WINDOW_HOURS}h")
    print(f"alerted (UNKNOWN, undelivered-until-resolved) keys: {len(alerted_state)}")
    for key, ts in sorted(alerted_state.items()):
        print(f"    {key}: alerted at {ts}")
    try:
        red_state = _load_json(RED_FILE)
    except RuntimeError as exc:
        logger.error("%s", exc)
        print(f"red-causes file: {RED_FILE} — CORRUPT, cannot parse ({exc})")
        red_state = {}
    suspended = {k: v for k, v in red_state.items() if v.get("suspended")}
    print(f"red-causes file: {RED_FILE} ({'exists' if RED_FILE.exists() else 'missing'})")
    print(f"  PRs with tracked reds: {len(red_state)}, suspended: {len(suspended)}")
    for key, entry in sorted(red_state.items()):
        susp = entry.get("suspended")
        susp_note = f" SUSPENDED at {susp.get('at')} (cause={susp.get('cause')})" if susp else ""
        print(f"    PR #{key}: {len(entry.get('reds') or [])} reds{susp_note}")
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"last log lines ({LOG_FILE}):")
        for line in lines[-10:]:
            print(f"    {line}")
    else:
        print(f"log file not found yet: {LOG_FILE}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tick", action="store_true", help="run one shepherd tick (cron entry)")
    parser.add_argument("--report", action="store_true", help="print state, budget, last actions")
    parser.add_argument("--dry-run", action="store_true", help="tick only: zero mutations")
    args = parser.parse_args(argv)
    # B4 (Codex review, 2026-09-11): args parsed BEFORE logging is configured, so --dry-run can
    # steer _configure_logging away from ever creating the RotatingFileHandler on LOG_FILE.
    _configure_logging(dry_run=args.dry_run)

    if args.report:
        return report()
    if args.tick:
        return tick(dry_run=args.dry_run)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
