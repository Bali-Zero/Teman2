#!/usr/bin/env python3
"""queue_unstick.py — the DIRTY/BEHIND stall killer (S12 concern C3).

The disease (measured 2026-08-23): 5+ episodes today of PRs stuck
BEHIND/DIRTY for 40-90 min each, waiting for a human gesture (`gh pr
update-branch`) that a cron can make in 10 minutes. This script IS that
cron's payload.

Candidate set: open, non-draft PRs. Three exclusions, each for a reason
measured or scarred by another lane today:

  1. PR is in the merge queue — updating a queued PR EVICTS it. Verified
     live against the GitHub GraphQL API 2026-08-23: `gh pr view --json
     isInMergeQueue` does NOT exist ("Unknown JSON field"); the real field
     is `pullRequest.mergeQueueEntry` (non-null iff queued). Command that
     verified it:
       gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){
         repository(owner:$o,name:$r){pullRequest(number:$n){
           mergeQueueEntry{state position}}}}' -f o=Bali-Zero -f r=Teman2 -F n=4662
     → {"mergeQueueEntry": null} for a non-queued PR. Field exists, shape
     confirmed (no GraphQL error), used as the sole queue-membership check.
     SCOPE NOTE (cicatrix W111, `.claude/rules/cicatrix-scars.md` ~line 160,
     read directly — not a paraphrase): W111's GOTCHA is that neither
     `autoMergeRequest` nor `mergeQueueEntry`/`isInMergeQueue` ALONE answers
     "is this PR armed for auto-merge" — a PR mid-queue often has
     `autoMergeRequest: null` (the request is consumed on entry) while one
     armed-but-not-yet-queued has `mergeQueueEntry: null` with
     `autoMergeRequest.enabledAt` set. That ambiguity is real but does NOT
     apply here: this script asks a narrower question — "is this PR
     currently occupying a queue slot that update-branch would evict" —
     and `mergeQueueEntry` alone answers exactly that, correctly, in both
     of W111's cases (non-null in the mid-queue case, null in the
     armed-but-unqueued case, where an update-branch push is harmless to
     queue position because there IS no queue position yet). This script
     never reads `autoMergeRequest` and never asserts an "armed/disarmed"
     verdict about any PR — do not extend it to do so on this one field
     alone without re-reading W111 first.
  2. Last commit younger than QUEUE_UNSTICK_RECENT_SECONDS (default 300s) —
     a lane is actively working; a branch update under its feet is a
     second-writer race (superscar #5).
  3. Labelled `hold` or `suspended`.

Actions on what survives:
  - mergeStateStatus == BEHIND  -> `gh pr update-branch <N>`, hard cap
    QUEUE_UNSTICK_CAP (default 5) per tick (anti-storm).
  - mergeStateStatus == DIRTY (true conflict) -> NEVER touch the branch
    (2026-08-21 scar: second-writer race). Signal ONCE per (PR, head SHA)
    to the fleet mailbox via scripts/fleet_mail.sh, deduped against a local
    state file so a PR stuck dirty for 6 hours doesn't emit 36 messages.
  - everything else -> no action.

KNOWN SIDE EFFECT — `gh pr update-branch` can silently RE-ARM auto-merge
(flagged by another lane 2026-08-23, verified here by reading the live
workflow, not their paraphrase): `.github/workflows/auto-merge-whitelist.yml`
triggers on `pull_request_target` with
`types: [opened, reopened, synchronize, ready_for_review, labeled]` (line 25)
gated by the single condition `if: github.event.pull_request.draft == false`
(line 35). `synchronize` fires on every push to the PR branch, and
`gh pr update-branch` IS a push. So: if a PR (a) is non-draft, (b) has a
branch matching the workflow's own whitelist (`docs/auto-sync-*`,
`dependabot/(pip|npm_and_yarn)/*`, `chore/fmt-*` — see branch_check step),
(c) has an allowlisted author (`dependabot[bot]`, `github-actions[bot]`,
`Balizero1987`), and (d) doesn't touch a protected path — then calling
update-branch on it re-enables auto-merge, even if a human had just run
`gh pr merge --disable-auto` on it WITHOUT a `hold`/`suspended` label. That
would be this script silently overriding a human decision.
This script does NOT special-case that PR shape. Reason: there is no
reliable API signal that distinguishes "auto-merge was explicitly disarmed
on purpose" from "auto-merge was never armed" — `autoMergeRequest == null`
means both (and, per cicatrix W111, is independently ambiguous with
`mergeQueueEntry` state: a request is consumed once a PR actually enters
the queue, so `null` can also mean "already queued, not disarmed"). Adding
a heuristic here (e.g. "skip if branch matches the whitelist pattern")
would silently narrow the BEHIND-unsticking coverage for exactly the
automation-authored PRs (dependabot/docs-sync/chore-fmt) this cron most
needs to help, on a guess about intent this script cannot verify. Per the
conductor's explicit call: this note is the fix for this round. The
reliable way to make a disarm durable against this script (and against
the whitelist workflow itself) is `gh pr ready --undo` (draft), which is
the one state both this script's draft-exclusion and the whitelist's own
`if` gate both honor.

Kill switch: QUEUE_UNSTICK_ENABLED=false makes every invocation a no-op
that still prints a receipt line (superscar #2: a mute cron is a dead
cron — silence must never be the only signal that nothing happened).

--dry-run performs ZERO mutations (no `gh pr update-branch`, no fleet-mail
send, no local state-file write, no local git-ref fetch for conflict-file
detection) and prints exactly what it would have done. This is how the
conductor verifies this script.

Env overrides:
  QUEUE_UNSTICK_ENABLED         "false"/"0"/"no"/"off" -> no-op (default: on)
  QUEUE_UNSTICK_REPO            default "Bali-Zero/Teman2"
  QUEUE_UNSTICK_CAP             default 5 (max update-branch calls per tick)
  QUEUE_UNSTICK_RECENT_SECONDS  default 300 (second-writer-race guard window)
  QUEUE_UNSTICK_STATE_DIR       default ~/.agent/decisions/state
  QUEUE_UNSTICK_FLEET_MAIL_HOST default "pro" (host arg to fleet_mail.sh —
                                 WHERE the broadcast write executes, per
                                 that script's local|pro|mini contract; the
                                 mailbox itself is fleet-visible regardless)

Exit codes: 0 = ran (whether or not it acted); 4 = CANNOT-VERIFY (the PR
list itself could not be fetched — never read this as "nothing to do",
superscar #2/#9); 1 = ran but at least one action (update-branch or
signal) failed.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

REPO = os.environ.get("QUEUE_UNSTICK_REPO", "Bali-Zero/Teman2")
UPDATE_CAP = int(os.environ.get("QUEUE_UNSTICK_CAP", "5"))
RECENT_COMMIT_SECONDS = int(os.environ.get("QUEUE_UNSTICK_RECENT_SECONDS", "300"))
HOLD_LABELS = {"hold", "suspended"}
STATE_DIR = Path(os.environ.get("QUEUE_UNSTICK_STATE_DIR", os.path.expanduser("~/.agent/decisions/state")))
DIRTY_SEEN_FILE = STATE_DIR / "queue_unstick_dirty_seen.json"
FLEET_MAIL_HOST = os.environ.get("QUEUE_UNSTICK_FLEET_MAIL_HOST", "pro")

GRAPHQL_QUERY = """
query($owner:String!, $repo:String!, $cursor:String) {
  repository(owner:$owner, name:$repo) {
    pullRequests(states:OPEN, first:100, after:$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        isDraft
        mergeStateStatus
        updatedAt
        headRefOid
        baseRefName
        labels(first:20) { nodes { name } }
        commits(last:1) { nodes { commit { committedDate } } }
        mergeQueueEntry { state }
      }
    }
  }
}
"""


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command; never raises. Returns (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


# ── fetch (network) ─────────────────────────────────────────────────────────


def fetch_open_prs(repo: str = REPO) -> list[dict]:
    """Fetch every open PR via GraphQL, paginated. Raises on any failure —
    a failed query is CANNOT-VERIFY, never an empty PR list (superscar #2/#9:
    `gh api` failing must never be read as "nothing to do")."""
    owner, name = repo.split("/", 1)
    prs: list[dict] = []
    cursor: str | None = None
    while True:
        args = [
            "gh", "api", "graphql",
            "-f", f"query={GRAPHQL_QUERY}",
            "-f", f"owner={owner}",
            "-f", f"repo={name}",
        ]
        if cursor:
            args += ["-f", f"cursor={cursor}"]
        rc, out, err = _run(args, timeout=45)
        if rc != 0:
            raise RuntimeError(f"gh api graphql failed rc={rc}: {err.strip()[:500]}")
        try:
            data = json.loads(out)
            page = data["data"]["repository"]["pullRequests"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError(f"unparseable graphql response: {exc!s}: {out[:300]}") from exc
        for node in page["nodes"]:
            prs.append(_normalize_pr(node))
        if page["pageInfo"]["hasNextPage"]:
            cursor = page["pageInfo"]["endCursor"]
        else:
            break
    return prs


def _normalize_pr(node: dict) -> dict:
    commits = (node.get("commits") or {}).get("nodes") or []
    last_commit_date = commits[0]["commit"]["committedDate"] if commits else node.get("updatedAt")
    labels = [entry["name"] for entry in (node.get("labels") or {}).get("nodes", [])]
    return {
        "number": node["number"],
        "is_draft": bool(node.get("isDraft")),
        "merge_state_status": node.get("mergeStateStatus"),
        "labels": labels,
        "last_commit_date": last_commit_date,
        "head_sha": node.get("headRefOid"),
        "base_ref": node.get("baseRefName") or "main",
        "queued": node.get("mergeQueueEntry") is not None,
    }


# ── pure classification (network-free, unit-tested) ────────────────────────


def is_hold_labelled(pr: dict) -> bool:
    labels = {str(label).strip().lower() for label in pr.get("labels", [])}
    return bool(labels & HOLD_LABELS)


def _parse_iso8601(raw: str):
    try:
        return _dt.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def is_recent_commit(pr: dict, now: _dt.datetime, threshold_seconds: int = RECENT_COMMIT_SECONDS) -> bool:
    """True if the last commit is younger than the second-writer-race window.
    An unparseable/missing timestamp is CANNOT-VERIFY-shaped: treated as
    recent (i.e. skip touching the branch) rather than assumed stale."""
    raw = pr.get("last_commit_date")
    if not raw:
        return True
    ts = _parse_iso8601(raw)
    if ts is None:
        return True
    age = (now - ts).total_seconds()
    return age < threshold_seconds


def classify(pr: dict, now: _dt.datetime, *, recent_seconds: int = RECENT_COMMIT_SECONDS) -> dict:
    """Classify a single PR dict. Returns {"number", "action", "reason"}.
    action is one of: "skip", "update_branch", "signal_dirty"."""
    number = pr.get("number")
    if pr.get("is_draft"):
        return {"number": number, "action": "skip", "reason": "draft"}
    if pr.get("queued"):
        return {"number": number, "action": "skip", "reason": "queued"}
    if is_hold_labelled(pr):
        return {"number": number, "action": "skip", "reason": "hold_label"}
    if is_recent_commit(pr, now, recent_seconds):
        return {"number": number, "action": "skip", "reason": "recent_commit"}
    status = pr.get("merge_state_status")
    if status == "BEHIND":
        return {"number": number, "action": "update_branch", "reason": "behind"}
    if status == "DIRTY":
        return {"number": number, "action": "signal_dirty", "reason": "dirty"}
    return {"number": number, "action": "skip", "reason": f"status_{status}"}


def plan_actions(
    prs: list[dict],
    now: _dt.datetime,
    *,
    cap: int = UPDATE_CAP,
    recent_seconds: int = RECENT_COMMIT_SECONDS,
    seen_dirty: dict | None = None,
) -> dict:
    """Pure planning over already-fetched PR dicts. No network, no side
    effects — this is the function the tests exercise directly.

    Returns {
      "update_branch": [pr_number, ...],                 # in input order, capped
      "signal_dirty": [{"number":..., "sha":...}, ...],   # excludes already-seen sha
      "skipped": {pr_number: reason, ...},
      "examined": N,
    }
    """
    seen_dirty = seen_dirty or {}
    update_branch: list[int] = []
    signal_dirty: list[dict] = []
    skipped: dict[int, str] = {}

    for pr in prs:
        c = classify(pr, now, recent_seconds=recent_seconds)
        number = c["number"]

        if c["action"] == "skip":
            skipped[number] = c["reason"]
            continue

        if c["action"] == "update_branch":
            if len(update_branch) >= cap:
                skipped[number] = "cap_reached"
                continue
            update_branch.append(number)
            continue

        if c["action"] == "signal_dirty":
            sha = pr.get("head_sha")
            if seen_dirty.get(str(number)) == sha:
                skipped[number] = "dirty_already_signalled"
                continue
            signal_dirty.append({"number": number, "sha": sha})
            continue

    return {
        "update_branch": update_branch,
        "signal_dirty": signal_dirty,
        "skipped": skipped,
        "examined": len(prs),
    }


# ── dirty-signal dedup state (local file, mutated only outside --dry-run) ──


def load_dirty_seen(path: Path = DIRTY_SEEN_FILE) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_dirty_seen(state: dict, path: Path = DIRTY_SEEN_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(path)


# ── side-effecting actions ──────────────────────────────────────────────────


def do_update_branch(number: int, *, repo: str = REPO, dry_run: bool) -> tuple[bool, str]:
    # KNOWN SIDE EFFECT (see module docstring): this push can re-arm
    # .github/workflows/auto-merge-whitelist.yml's `synchronize` trigger for
    # whitelisted-branch/allowlisted-author PRs, even ones a human just
    # disarmed without a hold/suspended label. No reliable API signal
    # distinguishes "disarmed on purpose" from "never armed" — documented,
    # not heuristically guessed at.
    if dry_run:
        return True, f"[dry-run] would run: gh pr update-branch {number} --repo {repo}"
    rc, out, err = _run(["gh", "pr", "update-branch", str(number), "--repo", repo], timeout=60)
    if rc != 0:
        return False, f"update-branch FAILED PR #{number} rc={rc}: {err.strip()[:300]}"
    return True, f"update-branch OK PR #{number}: {out.strip() or 'requested'}"


def get_conflicting_files(pr: dict, *, repo_root: Path = REPO_ROOT, timeout: int = 25) -> str:
    """Best-effort LOCAL merge simulation (git merge-tree --write-tree
    --name-only) to name the real conflicting files, without ever touching
    the PR's remote branch or any persistent ref. Falls back to the literal
    'unobtainable via API' string on any failure — never invents filenames.

    GitHub's REST/GraphQL API exposes no "conflicting files" field for a PR
    (verified 2026-08-23: neither the PullRequest type nor the REST merge
    endpoint returns a diff3 conflict list), so a real answer requires a
    local, read-only merge attempt against scratch refs that are deleted
    before this function returns.
    """
    number = pr.get("number")
    base = pr.get("base_ref") or "main"
    if not number:
        return "unobtainable via API"

    pid = os.getpid()
    pr_ref = f"refs/queue-unstick/pr-{number}-{pid}"
    base_ref = f"refs/queue-unstick/base-{number}-{pid}"
    try:
        rc, _out, _err = _run(
            ["git", "-C", str(repo_root), "fetch", "--quiet", "origin",
             f"refs/pull/{number}/head:{pr_ref}", f"{base}:{base_ref}"],
            timeout=timeout,
        )
        if rc != 0:
            return "unobtainable via API"
        rc, out, _err = _run(
            ["git", "-C", str(repo_root), "merge-tree", "--write-tree",
             "--name-only", "--no-messages", base_ref, pr_ref],
            timeout=timeout,
        )
        lines = [line for line in out.splitlines() if line.strip()]
        if rc == 0:
            # No conflict after all (race: PR was updated between the
            # GraphQL read and this probe) — say so plainly, don't lie.
            return "none (merge-tree found no conflict at probe time)"
        # First line is the (conflicted) tree OID; the rest, with
        # --name-only, are the conflicting paths.
        files = lines[1:] if len(lines) > 1 else []
        if not files:
            return "unobtainable via API"
        return ", ".join(files[:20]) + (" (+more)" if len(files) > 20 else "")
    except Exception:
        return "unobtainable via API"
    finally:
        for ref in (pr_ref, base_ref):
            _run(["git", "-C", str(repo_root), "update-ref", "-d", ref], timeout=10)


def send_dirty_signal(pr: dict, *, dry_run: bool, repo_root: Path = REPO_ROOT) -> tuple[bool, str]:
    number = pr.get("number")
    sha = pr.get("head_sha") or "unknown"
    short_sha = sha[:12] if sha and sha != "unknown" else "unknown"

    if dry_run:
        return True, (
            f"[dry-run] would signal DIRTY PR #{number} at {short_sha} "
            f"(conflicting files not computed in dry-run) via fleet_mail.sh {FLEET_MAIL_HOST} broadcast"
        )

    files_desc = get_conflicting_files(pr, repo_root=repo_root)
    msg = (
        f"queue_unstick: PR #{number} is DIRTY (merge conflict) at {short_sha}. "
        f"conflicting files: {files_desc}. Will NOT touch this branch — needs manual resolution."
    )
    fleet_mail = repo_root / "scripts" / "fleet_mail.sh"
    if not fleet_mail.is_file():
        return False, f"signal FAILED PR #{number}: fleet_mail.sh not found at {fleet_mail}"
    rc, out, err = _run(["bash", str(fleet_mail), FLEET_MAIL_HOST, "broadcast", msg], timeout=30)
    if rc != 0:
        return False, f"signal FAILED PR #{number} rc={rc}: {err.strip()[:300]}"
    return True, f"signal OK PR #{number}: {out.strip() or 'sent'}"


# ── main ─────────────────────────────────────────────────────────────────


def _enabled() -> bool:
    return os.environ.get("QUEUE_UNSTICK_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "queue_unstick")
    parser.add_argument("--dry-run", action="store_true", help="perform zero mutations; print exactly what would happen")
    parser.add_argument("--repo", default=REPO)
    args = parser.parse_args(argv)

    if not _enabled():
        print("QUEUE_UNSTICK_SUMMARY disabled=true examined=0 updated=0 dirty_signalled=0 dry_run=%s" % str(args.dry_run).lower())
        return 0

    now = _dt.datetime.now(_dt.timezone.utc)

    try:
        prs = fetch_open_prs(args.repo)
    except Exception as exc:
        print(f"QUEUE_UNSTICK_SUMMARY cannot_verify=true error={str(exc)[:400]!r}")
        return 4

    seen_dirty = {} if args.dry_run else load_dirty_seen()
    plan = plan_actions(prs, now, cap=UPDATE_CAP, recent_seconds=RECENT_COMMIT_SECONDS, seen_dirty=seen_dirty)

    updated: list[int] = []
    update_failed: list[int] = []
    for number in plan["update_branch"]:
        ok, detail = do_update_branch(number, repo=args.repo, dry_run=args.dry_run)
        print(detail)
        (updated if ok else update_failed).append(number)

    prs_by_number = {pr["number"]: pr for pr in prs}
    signalled: list[int] = []
    signal_failed: list[int] = []
    new_seen = dict(seen_dirty)
    for entry in plan["signal_dirty"]:
        pr = prs_by_number.get(entry["number"], entry)
        ok, detail = send_dirty_signal(pr, dry_run=args.dry_run)
        print(detail)
        if ok:
            signalled.append(entry["number"])
            if not args.dry_run:
                new_seen[str(entry["number"])] = entry["sha"]
        else:
            signal_failed.append(entry["number"])

    if not args.dry_run and new_seen != seen_dirty:
        save_dirty_seen(new_seen)

    skip_reasons: dict[str, int] = {}
    for reason in plan["skipped"].values():
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    # Structured summary line, printed on EVERY tick regardless of outcome —
    # cron-runner.sh's own receipt (job/status/exit_code/last_error) cannot
    # express "examined N, acted on M, skipped K (why)", so this line is the
    # thing that keeps this cron from being a mute one (superscar #2).
    summary = (
        f"QUEUE_UNSTICK_SUMMARY examined={plan['examined']} "
        f"updated={len(updated)} update_failed={len(update_failed)} "
        f"dirty_signalled={len(signalled)} dirty_signal_failed={len(signal_failed)} "
        f"skipped={len(plan['skipped'])} dry_run={str(args.dry_run).lower()} "
        f"skip_reasons={json.dumps(skip_reasons, sort_keys=True)}"
    )
    print(summary)

    return 0 if not update_failed and not signal_failed else 1


if __name__ == "__main__":
    sys.exit(main())
