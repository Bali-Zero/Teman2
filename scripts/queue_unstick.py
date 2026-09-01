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
     SCOPE NOTE (cicatrix W111, `docs/scars/cicatrix-scars.md` ~line 160,
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
    QUEUE_UNSTICK_CAP (default 1) per tick (anti-storm).
  - mergeStateStatus == DIRTY (true conflict) -> NEVER touch the branch
    (2026-08-21 scar: second-writer race). Signal ONCE per (PR, head SHA)
    to the fleet mailbox via scripts/fleet_mail.sh, deduped against a local
    state file so a PR stuck dirty for 6 hours doesn't emit 36 messages.
  - everything else -> no action.

KNOWN SIDE EFFECT — `gh pr update-branch` is a push, so it can silently
RE-ARM auto-merge on a PR whose auto-merge was disarmed without a
`hold`/`suspended` label. This is cicatrix **W123** ("hold disarmato si
ri-arma al push", `.claude/rules/cicatrix-superscar.md` family #2) —
mechanism, exact workflow/trigger, and antibody are documented there;
not re-derived here. Applies narrowly: only to PRs matching
auto-merge-whitelist.yml's own branch (`docs/auto-sync-*`,
`dependabot/(pip|npm_and_yarn)/*`, `chore/fmt-*`) and author
(`dependabot[bot]`, `github-actions[bot]`, `Balizero1987`) filters.
This script does NOT special-case that PR shape: no API signal reliably
distinguishes "disarmed on purpose" from "never armed" (`autoMergeRequest
== null` means both, and per W111 below is independently ambiguous with
queue state too) — a branch/author heuristic would just as reliably
narrow BEHIND-unsticking coverage for the automation PRs this cron exists
to help, on a guess this script cannot verify. Per the conductor's
explicit call: this citation is the fix for this round. The durable way
to make a disarm survive this script (and the whitelist workflow itself)
is `gh pr ready --undo` (draft) — the one state both this script's
draft-exclusion and the whitelist's own `if` gate honor.

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
  QUEUE_UNSTICK_CAP             default 1 (max update-branch calls per tick;
                                a PLACEHOLDER — see the constant's comment)
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
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

REPO = os.environ.get("QUEUE_UNSTICK_REPO", "Bali-Zero/Teman2")
# PLACEHOLDER, NOT A TUNED NUMBER. A cross-family refuter (agy/Gemini 3.1 Pro,
# 2026-08-25) showed every candidate cap is uncalibrated in BOTH directions until
# two things are measured: (i) queued-to-start latency — a concurrency cap only
# binds if jobs actually queue — and then (ii) baseline concurrent load at the hour
# this cron fires. Research: research/operations/2026-08-23-runner-slot-audit.md
# (§Adversarial review, findings 4 and 5). 1 is chosen because it is the only value
# safe under EVERY unmeasured baseline, not because it was derived. Raising it
# requires those measurements first — see PENDING-ARMS S12/C3 item (c).
UPDATE_CAP = int(os.environ.get("QUEUE_UNSTICK_CAP", "1"))
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
    """Run a command; never raises. Returns (rc, stdout, stderr).

    `errors="replace"` is what makes "never raises" TRUE rather than merely
    intended. With the default strict decoding, `text=True` raises
    UnicodeDecodeError — a ValueError, caught by neither arm of the except
    below — the moment git prints a path whose bytes are not valid UTF-8, which
    `git diff -z --name-only` will happily do. A cross-family refuter found this
    by reading the contract rather than the code; the docstring had been lying
    since it was written, and the fail-quiet argument for every caller rests on
    it being true.
    """
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=timeout
        )
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
      "signal_dirty": [{"number":..., "sha":...}, ...],   # ALL dirty candidates;
                                                         # dedup happens in main()
                                                         # on the conflict fingerprint
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
            # DEDUP DELIBERATELY NOT DONE HERE ANYMORE (S12/C3 finding 2).
            # It used to compare `seen_dirty[number] == head_sha`, which is
            # blind to the exact case that matters: `main` advances, the SET
            # OF CONFLICTING FILES changes, and the PR's head does NOT — so no
            # new signal was emitted and the fleet mailbox kept stale paths.
            # The real key needs the conflict fingerprint, which requires a
            # local merge simulation; this function is pure and network-free
            # by design, so the dedup now lives in main() where that
            # fingerprint exists. See _dirty_fingerprint().
            signal_dirty.append({"number": number, "sha": pr.get("head_sha")})
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


SINGLE_PR_QUEUE_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) { mergeQueueEntry { state } }
  }
}
"""


def is_queued_now(number: int, *, repo: str = REPO, timeout: int = 20):
    """Re-read `mergeQueueEntry` for THIS ONE PR, right now.

    Returns (True, detail) queued · (False, detail) not queued ·
    (None, detail) UNVERIFIABLE.

    Why this exists (S12/C3 red-team finding, confirmed against the merged
    source before being acted on): `classify()` decides "not queued" from a
    BULK GraphQL read taken at the top of the tick. Between that read and
    the mutation below, a PR can enter the merge queue — and
    `gh pr update-branch` on a queued PR EVICTS it, which is the single most
    destructive thing this script can do. The window is not theoretical:
    PRs entered and left the queue continuously during the session that
    measured this. Ordering the checks differently does not close it; only
    re-reading immediately before the mutation does.

    UNVERIFIABLE is deliberately NOT treated as "not queued": an
    unverifiable queue state must never authorise an eviction.
    """
    owner, _, name = repo.partition("/")
    rc, out, err = _run(
        ["gh", "api", "graphql",
         "-f", f"query={SINGLE_PR_QUEUE_QUERY}",
         "-f", f"owner={owner}", "-f", f"repo={name}", "-F", f"number={number}",
         "--jq", ".data.repository.pullRequest.mergeQueueEntry"],
        timeout=timeout,
    )
    if rc != 0:
        return None, f"queue re-check rc={rc}: {err.strip()[:200]}"
    raw = out.strip()
    if not raw:
        return None, "queue re-check returned empty output"
    if raw == "null":
        return False, "not in merge queue at mutation time"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, f"queue re-check unparseable: {raw[:120]!r}"
    if parsed is None:
        return False, "not in merge queue at mutation time"
    state = parsed.get("state") if isinstance(parsed, dict) else None
    return True, f"in merge queue (state={state})"


def do_update_branch(
    number: int, *, repo: str = REPO, dry_run: bool, queue_recheck=None
) -> tuple[str, str]:
    """Returns (outcome, detail) where outcome is "ok" | "aborted" | "failed".

    "aborted" is a THIRD outcome on purpose. An abort means the guard did its
    job — the PR entered the queue, or its state could not be verified — and
    counting that as a failure would turn a correct refusal into a red cron
    tick on an ordinary race (cicatrix W116: an alarm that fires on the right
    outcome is an alarm nobody reads).
    """
    # KNOWN SIDE EFFECT — cicatrix W123 ("hold disarmato si ri-arma al
    # push", cicatrix-superscar.md family #2): this push can re-arm
    # auto-merge-whitelist.yml for whitelisted-branch/allowlisted-author
    # PRs. See module docstring for scope + why no heuristic is added.
    if dry_run:
        return "ok", f"[dry-run] would run: gh pr update-branch {number} --repo {repo}"

    recheck = queue_recheck or is_queued_now
    queued, why = recheck(number, repo=repo)
    if queued is None:
        return "aborted", (
            f"update-branch ABORTED PR #{number}: queue state UNVERIFIABLE ({why}) — "
            f"refusing to update; an unverifiable queue state must not authorise an eviction"
        )
    if queued:
        return "aborted", (
            f"update-branch ABORTED PR #{number}: {why} — it entered the queue after "
            f"planning; updating now would EVICT it"
        )

    rc, out, err = _run(["gh", "pr", "update-branch", str(number), "--repo", repo], timeout=60)
    if rc != 0:
        return "failed", f"update-branch FAILED PR #{number} rc={rc}: {err.strip()[:300]}"
    return "ok", f"update-branch OK PR #{number}: {out.strip() or 'requested'}"


#: How many changed paths `check-attr` is asked about PER CALL. This is a batch
#: size, NOT a limit: every path is examined, in successive calls. The first cut
#: of this function truncated at 200 and examined nothing beyond, so a large PR
#: whose union path sorted late was reported as a race — "0 found" and "not
#: looked at" producing the same answer, which is the failure this whole probe
#: exists to stop making.
_ATTR_BATCH = 200

#: `check-attr` values that mean "git merges this file the ordinary way", i.e. the
#: same way GitHub's merge machinery does. Anything ELSE is a declared driver, and
#: GitHub honours no merge driver at all — so the two disagree by construction.
#: Keyed on the complement rather than on the literal "union" because `merge=ours`
#: diverges identically and would have silently regressed to the race wording
#: (superscar #3's under-match twin, W82: a guard watching one literal string).
#: `unset` (`-merge`) is excluded deliberately: it makes git ALWAYS conflict, so a
#: file carrying it cannot reach this code path, which only runs when git said clean.
_ORDINARY_MERGE_VALUES = frozenset({"unspecified", "unset", "set", "text"})


def _driver_merged_changed_paths(
    *, repo_root: Path, base_ref: str, pr_ref: str, timeout: int = 25
) -> list[tuple[str, str]]:
    """`(path, driver)` for each changed path `.gitattributes` gives a merge driver.

    Read-only, and deliberately fail-quiet: every failure returns `[]`, which
    makes the caller fall back to its pre-existing "race" wording. An empty
    list therefore means "no driver path FOUND", never "no driver path EXISTS" —
    so this can only ever add a diagnosis, never suppress one.

    Both git calls use `-z`. That is not a style choice: `core.quotePath` defaults
    to true, so `git diff --name-only` emits a NON-ASCII path as the C-quoted
    literal `"caf\303\251.md"`, which `check-attr` then fails to match, returning
    `unspecified` for a file that is in fact union-merged. Measured against the
    first cut of this function in a real repo: it returned [] where the truth was
    ['café.md']. `-z` also removes the `<path>: merge: <value>` parse entirely,
    and with it the class of bug where a path containing ": " is truncated.
    """
    rc, out, _err = _run(
        ["git", "-C", str(repo_root), "diff", "-z", "--name-only", f"{base_ref}...{pr_ref}"],
        timeout=timeout,
    )
    if rc != 0:
        return []
    paths = [p for p in out.split("\0") if p]
    if not paths:
        return []
    # Paths go after `--` so a leading-dash filename is not read as a flag.
    # Capped because a huge PR would otherwise blow argv; the cap is reported by
    # the caller rather than silently swallowed.
    found: list[tuple[str, str]] = []
    for start in range(0, len(paths), _ATTR_BATCH):
        batch = paths[start:start + _ATTR_BATCH]
        rc, out, _err = _run(
            ["git", "-C", str(repo_root), "check-attr", "-z", "merge", "--", *batch],
            timeout=timeout,
        )
        if rc != 0:
            return []
        # -z output is a flat NUL-separated stream of (path, attr, value) triples.
        fields = out.split("\0")
        for i in range(0, len(fields) - 2, 3):
            path, attr, value = fields[i], fields[i + 1], fields[i + 2]
            if attr != "merge" or not path:
                continue
            if value in _ORDINARY_MERGE_VALUES:
                continue
            found.append((path, value))
    return found


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
            # GitHub says DIRTY and the local merge says clean. There are two
            # causes, and they want OPPOSITE responses, so naming the right one
            # is the whole value of this branch.
            #
            #   1. A race: the PR moved between the GraphQL read and this probe.
            #      Transient — the next tick reports it correctly.
            #   2. A declared merge driver (`merge=union`, `merge=ours`, ...).
            #      git honours it and exits 0; GitHub's merge machinery honours
            #      NO driver and reports a real conflict. PERMANENT — re-probing
            #      can never clear it.
            #
            # Measured 2026-08-31 on PRs #5331 and #5373: both DIRTY on GitHub
            # with `merge-tree` rc=0, both touching the repo's one union path,
            # `.claude/skills/modus/PENDING-ARMS.md`. Reported as a race, that is
            # a permanent condition wearing a transient label.
            #
            # WHAT THIS MESSAGE MUST NEVER SAY, and briefly did (2026-08-31):
            # "hand rebase that file". Hand-resolving a union file is precisely
            # how the other lane's appended row gets deleted in silence — the
            # loss the driver exists to prevent, which `check-ledger-no-silent-loss`
            # then catches in CI (seen live on #5355). And `git rebase` is no
            # safer in the other reading: rebase DOES apply the union driver, so
            # replaying an append over a base that already carries it duplicates
            # the row (measured on #4060), which a set-based gate cannot see.
            # The cure is neither. It is to rebuild the append on a branch cut
            # from fresh origin/main and prove the file's diff is +N/-0.
            drivers = _driver_merged_changed_paths(
                repo_root=repo_root, base_ref=base_ref, pr_ref=pr_ref, timeout=timeout
            )
            if drivers:
                shown = ", ".join(
                    f"{path} (merge={driver})" for path, driver in drivers[:5]
                ) + (" (+more)" if len(drivers) > 5 else "")
                return (
                    f"none locally, but this is NOT a race: {shown} — git honours that "
                    "driver, GitHub's merge machinery honours none, so the two disagree "
                    "permanently and re-probing will never clear it. DO NOT hand-resolve "
                    "the file and DO NOT rebase onto it: the first silently deletes the "
                    "other lane's appended row, the second replays the append and "
                    "duplicates it. Rebuild your addition on a branch cut from fresh "
                    "origin/main, then verify `git diff origin/main -- <file>` is +N/-0."
                )
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


def _dirty_fingerprint(sha: str | None, files_desc: str) -> str:
    """Dedup key for a DIRTY signal: the head SHA AND the conflict set.

    Keyed on head_sha alone (the pre-2026-08-25 behaviour) this cron went mute
    exactly when it had something new to say — `main` moves, the conflicting
    files change, the PR head does not. Hashing keeps the state file bounded
    when a PR conflicts on twenty paths.
    """
    digest = hashlib.sha256((files_desc or "").encode("utf-8")).hexdigest()[:16]
    return f"{sha or 'unknown'}:{digest}"


def send_dirty_signal(
    pr: dict, *, dry_run: bool, repo_root: Path = REPO_ROOT, files_desc: str | None = None
) -> tuple[bool, str]:
    number = pr.get("number")
    sha = pr.get("head_sha") or "unknown"
    short_sha = sha[:12] if sha and sha != "unknown" else "unknown"

    # S3 (2026-08-27): a state key, not the SHA/fingerprint the LOCAL
    # dirty_seen dedup (below, in main()) already uses. This is a SEPARATE,
    # complementary dedup at the mailbox layer: dirty_seen only guards
    # sends from THIS machine's own state file, so if queue_unstick ever
    # runs as a cron on more than one machine (or the state file is lost),
    # each sender's local fingerprint check can't see the others' sends —
    # the mailbox-side `key: queue_unstick:<PR>` still collapses them to
    # the newest, fleet-wide, regardless of which host sent it.
    mailbox_key = f"queue_unstick:{number}"

    if dry_run:
        return True, (
            f"[dry-run] would signal DIRTY PR #{number} at {short_sha} "
            f"(conflicting files not computed in dry-run) via fleet_mail.sh {FLEET_MAIL_HOST} "
            f"broadcast --key {mailbox_key}"
        )

    if files_desc is None:
        files_desc = get_conflicting_files(pr, repo_root=repo_root)
    msg = (
        f"queue_unstick: PR #{number} is DIRTY (merge conflict) at {short_sha}. "
        f"conflicting files: {files_desc}. Will NOT touch this branch — needs manual resolution."
    )
    fleet_mail = repo_root / "scripts" / "fleet_mail.sh"
    if not fleet_mail.is_file():
        return False, f"signal FAILED PR #{number}: fleet_mail.sh not found at {fleet_mail}"
    rc, out, err = _run(
        ["bash", str(fleet_mail), FLEET_MAIL_HOST, "broadcast", "--key", mailbox_key, msg], timeout=30
    )
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
    update_aborted: list[int] = []
    for number in plan["update_branch"]:
        outcome, detail = do_update_branch(number, repo=args.repo, dry_run=args.dry_run)
        print(detail)
        if outcome == "ok":
            updated.append(number)
        elif outcome == "aborted":
            # NOT a failure — the queue guard refused an eviction. Counted and
            # printed separately so a normal race never reddens the tick (W116).
            update_aborted.append(number)
        else:
            update_failed.append(number)

    prs_by_number = {pr["number"]: pr for pr in prs}
    signalled: list[int] = []
    signal_failed: list[int] = []
    dirty_deduped: list[int] = []
    new_seen = dict(seen_dirty)
    for entry in plan["signal_dirty"]:
        number = entry["number"]
        pr = prs_by_number.get(number, entry)

        if args.dry_run:
            ok, detail = send_dirty_signal(pr, dry_run=True)
            print(detail)
            signalled.append(number)
            continue

        # Compute the conflict set FIRST, because it is half the dedup key.
        files_desc = get_conflicting_files(pr)
        key = _dirty_fingerprint(entry.get("sha"), files_desc)
        if seen_dirty.get(str(number)) == key:
            dirty_deduped.append(number)
            print(
                f"dirty already signalled PR #{number}: same head AND same conflict set "
                f"({files_desc[:80]}) — not repeating"
            )
            continue

        ok, detail = send_dirty_signal(pr, dry_run=False, files_desc=files_desc)
        print(detail)
        if ok:
            signalled.append(number)
            new_seen[str(number)] = key
        else:
            signal_failed.append(number)

    if not args.dry_run and new_seen != seen_dirty:
        save_dirty_seen(new_seen)

    skip_reasons: dict[str, int] = {}
    for reason in plan["skipped"].values():
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    # Structured summary line, printed on EVERY tick regardless of outcome —
    # cron-runner.sh's own receipt (job/status/exit_code/last_error) cannot
    # express "examined N, acted on M, skipped K (why)", so this line is the
    # thing that keeps this cron from being a mute one (superscar #2).
    if dirty_deduped:
        skip_reasons["dirty_already_signalled"] = len(dirty_deduped)

    summary = (
        f"QUEUE_UNSTICK_SUMMARY examined={plan['examined']} "
        f"updated={len(updated)} update_failed={len(update_failed)} "
        f"update_aborted={len(update_aborted)} "
        f"dirty_signalled={len(signalled)} dirty_signal_failed={len(signal_failed)} "
        f"dirty_deduped={len(dirty_deduped)} "
        f"cap={UPDATE_CAP} "
        f"skipped={len(plan['skipped']) + len(dirty_deduped)} dry_run={str(args.dry_run).lower()} "
        f"skip_reasons={json.dumps(skip_reasons, sort_keys=True)}"
    )
    print(summary)

    return 0 if not update_failed and not signal_failed else 1


if __name__ == "__main__":
    sys.exit(main())
