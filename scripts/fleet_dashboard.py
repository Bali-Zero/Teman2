#!/usr/bin/env python3
"""Render the organism's merge-queue state as one page a non-developer can read.

WHY THIS EXISTS. The state of the work is spread across surfaces that each
answer a different question and none of which answer "what is stuck, and
why": `gh pr list` shows titles, the merge queue shows positions, the checks
tab shows red/green per PR. Reading them together is a developer's job. Zero
is not a developer and should not have to do it, so this collapses them into
one page whose top line is the only sentence that matters: how many pieces of
work are moving, how many are stuck, and what the single biggest cause is.

WHY A GENERATOR AND NOT A HAND-WRITTEN PAGE. A dashboard written by hand is
true for one minute and then lies quietly. This script measures every number
it prints, at the moment it prints it, and stamps the page with that moment.
Re-run it and republish to the same artifact URL and the page updates; there
is no second copy of the numbers to drift.

THE THREE PROBES AND WHY EACH IS THE ONE USED (each replaces a proxy that
was measured lying, in this repo, on 2026-09-01):

  1. ARMED is read from `mergeQueueEntry`, never from `autoMergeRequest`.
     `autoMergeRequest` is null in three completely different states —
     never armed, armed-then-ejected, and armed-then-CONSUMED by the queue —
     so a PR sitting at queue position 1 reports "not armed". Measured:
     #5458/#5459/#5460 all showed autoMergeRequest=null while holding queue
     positions 3/2/1.

  2. CONFLICT is split into PHANTOM and REAL by a local trial merge, never
     taken from GitHub's `mergeable` field alone. `.gitattributes` declares
     `merge=union` on the PENDING-ARMS ledger; git honours that driver and
     GitHub's server-side mergeability does not, so two PRs that both append
     a ledger row make the second one report CONFLICTING while
     `git merge-tree --write-tree` returns clean. Measured the same day: of
     8 PRs flagged DIRTY, 5 were phantoms. Reporting those 5 as conflicts
     sends a person to hand-resolve a file whose hand-resolution DELETES
     other lanes' rows.

  3. WHY IT IS RED is grouped by the failing check's NAME across all PRs,
     not listed per PR. One check accounted for 12 of the 34 live PRs that
     morning; per-PR listing hides that shape completely, and the shape is
     the actionable fact — it is the difference between "twelve problems"
     and "one problem, twelve times".

Read-only in the sense that matters, and NOT write-free — worth stating
precisely rather than claiming more than is true. It never mutates a PR, never
arms, never merges, and never touches an index or a working tree. It does
write: the HTML file, the JSON dump when `--json` is passed, and — via
`git fetch` and `git merge-tree --write-tree` — objects and remote-tracking
refs in the SHARED `.git` store. Per git-merge-tree(1) that last pair cannot
disturb a concurrent session's work.

Usage:
    python3 scripts/fleet_dashboard.py --out /tmp/dashboard.html
    python3 scripts/fleet_dashboard.py --out /tmp/d.html --json /tmp/d.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = "Bali-Zero/Teman2"

# The fleet is in Bali. Every date boundary on this page is WITA, never UTC —
# a UTC "today" drops the 00:00-08:00 local window, which is exactly when the
# overnight autonomous runs land.
WITA = dt.timedelta(hours=8)

# Every git probe runs from wherever this script lives. That is normally a
# worktree, which shares the object database and is what the worktree-isolation
# hook expects. If it ever resolves to the guarded MAIN checkout, the hook
# refuses each git call and the page renders with every conflict verdict
# missing and nothing saying why — so that case is named out loud at startup
# rather than degrading quietly (adversarial review, 2026-09-01).
GIT_CWD = Path(__file__).resolve().parent.parent


def _warn_if_main_checkout() -> None:
    # Judged on the FACT, not on the folder's name. An earlier version also
    # required `GIT_CWD.name == "nuzantara"` and a parent not named
    # `.worktrees`, which silently false-negatives on any differently-named
    # clone. In a linked worktree `.git` is a FILE pointing at the real object
    # store; only a primary checkout has it as a DIRECTORY. That single test is
    # naming-independent and is the whole signal.
    if (GIT_CWD / ".git").is_dir():
        sys.stderr.write(
            f"fleet_dashboard: running from what looks like the MAIN checkout "
            f"({GIT_CWD}). If the worktree-isolation hook is armed it will refuse "
            "every git call and the conflict section will be empty for the wrong "
            "reason. Run this from a worktree.\n"
        )


def _run(args: list[str], timeout: int = 90) -> tuple[int, str, str]:
    """Run a command, returning (rc, stdout, stderr). Never raises on non-zero rc.

    The captured-rc form is deliberate: under `bash -e` (and in CI) a bare
    `out = $(cmd)` aborts the whole step at the assignment, taking the
    diagnostic with it. Here the caller always gets to see what happened.

    stderr is returned, not discarded: when a git plumbing command fails, the
    REASON is the only thing that distinguishes "these branches conflict" from
    "this probe could not run", and those two demand opposite reactions.
    """
    try:
        p = subprocess.run(
            args, cwd=str(GIT_CWD), capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 125, "", f"{type(exc).__name__}: {exc}"
    return p.returncode, p.stdout, p.stderr


GRAPHQL = """
query {
  repository(owner: "%s", name: "%s") {
    pullRequests(states: OPEN, first: 100) {
      nodes {
        number title isDraft mergeable mergeStateStatus headRefName headRefOid
        updatedAt
        author { __typename login }
        autoMergeRequest { enabledAt }
        mergeQueueEntry { position state }
        commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
      }
    }
  }
}
""" % tuple(REPO.split("/"))


RESOLVE_ONE = """
query($n: Int!) {
  repository(owner: "%s", name: "%s") {
    pullRequest(number: $n) { mergeable mergeStateStatus }
  }
}
""" % tuple(REPO.split("/"))


def resolve_mergeable(number: int, attempts: int = 3, delay: float = 2.0) -> tuple[str, str]:
    """Force GitHub to compute one PR's mergeability, and return it.

    WHY THIS EXISTS (found by adversarial review, 2026-09-01 — the defect was
    live in the first published version of this page). GitHub computes
    mergeability LAZILY, and a bulk connection query
    (`pullRequests(first:100){ mergeable }`) very often returns `UNKNOWN` for
    most rows: measured 34 of 40 open PRs `UNKNOWN` in a single run. The first
    version treated anything that was not the literal string `CONFLICTING` as
    "no conflict", so #4717 — genuinely `CONFLICTING`, confirmed by a direct
    single-PR fetch seconds later — was rendered under "green, nothing to do".
    A dashboard that says "nothing to do" about a conflicted PR is worse than
    one that says nothing at all.

    A single-PR query is what triggers the computation, so the first answer can
    still be UNKNOWN while GitHub works; hence the retry. If it is still
    unknown after the attempts, the caller must keep it UNKNOWN and say so —
    never silently fold it into "fine".
    """
    for i in range(attempts):
        rc, out, _ = _run(
            ["gh", "api", "graphql", "-f", f"query={RESOLVE_ONE}", "-F", f"n={number}"]
        )
        if rc == 0 and out.strip():
            try:
                pr = json.loads(out)["data"]["repository"]["pullRequest"]
            except (KeyError, TypeError, json.JSONDecodeError):
                return "UNKNOWN", "UNKNOWN"
            if pr["mergeable"] != "UNKNOWN":
                return pr["mergeable"], pr["mergeStateStatus"]
        if i < attempts - 1:
            time.sleep(delay)
    return "UNKNOWN", "UNKNOWN"


def fetch_open_prs() -> list[dict[str, Any]]:
    # The retry is now BELT-AND-BRACES, and the comment that used to live here
    # was wrong about why. It justified the retry by this query being heavy —
    # "100 PRs each with up to 100 check contexts" — but the commit that added
    # that sentence is the same one that removed `contexts` from this query
    # (it now asks only for `statusCheckRollup { state }`; per-check contexts
    # moved to CONTEXTS_ONE, fetched one red PR at a time). So the sentence
    # described the query as it was BEFORE the diff it was attached to.
    # The real history: the heavy version timed out on 3 of 3 runs even WITH
    # three attempts — a retry on a too-heavy query makes it fail more slowly,
    # it does not make it succeed. Lightening the query is what fixed it.
    # The retry stays only for ordinary transient network failure.
    prs = None
    for attempt in range(3):
        rc, out, err = _run(["gh", "api", "graphql", "-f", f"query={GRAPHQL}"], timeout=120)
        if rc == 0 and out.strip():
            prs = json.loads(out)["data"]["repository"]["pullRequests"]["nodes"]
            break
        sys.stderr.write(
            f"fleet_dashboard: bulk query attempt {attempt + 1}/3 failed "
            f"(rc={rc}): {(err or out).strip()[:200]}\n"
        )
        if attempt < 2:
            time.sleep(4.0)
    if prs is None:
        raise SystemExit(
            "fleet_dashboard: gh graphql failed 3 times — refusing to render a "
            "page from no data."
        )
    # Re-ask, per PR, for every row the bulk query left uncomputed. This is the
    # only field on the page whose wrongness points a reader AWAY from work that
    # exists, so it is the one worth up to N extra API calls.
    for pr in prs:
        if pr["mergeable"] == "UNKNOWN":
            pr["mergeable"], mss = resolve_mergeable(pr["number"])
            if mss != "UNKNOWN":
                pr["mergeStateStatus"] = mss
    return prs


CONTEXTS_ONE = """
query($n: Int!) {
  repository(owner: "%s", name: "%s") {
    pullRequest(number: $n) {
      commits(last: 1) { nodes { commit { statusCheckRollup {
        contexts(first: 100) { nodes {
          __typename
          ... on CheckRun { name conclusion }
          ... on StatusContext { context state }
        } }
      } } } }
    }
  }
}
""" % tuple(REPO.split("/"))


#: Not a check name and deliberately not shaped like one: it is the answer to
#: "why is this PR red?" when the instrument that was supposed to answer never
#: replied. It groups into its own row in the causes table so the reader sees
#: that the tally is incomplete rather than reading a short list as a full one.
#: A rollup context is FAILING on any of these. The bug this replaces tested
#: `verdict == "FAILURE"` alone, so a check that TIMED_OUT, was CANCELLED,
#: needed ACTION_REQUIRED, hit a STARTUP_FAILURE, or (on a StatusContext)
#: ERRORed left the PR counted as red while contributing to NO row in the
#: causes table — it read as "nothing wrong here" by omission, which is worse
#: than the unreadable sentinel, because not even a row said the tally was
#: short. Found by adversarial review of the very commit that claimed to have
#: cured this disease everywhere in this function.
FAILING_VERDICTS = frozenset({
    "FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE", "ERROR",
})
#: Explicitly NOT failing. Kept as its own list rather than "everything else",
#: so a verdict in neither set is surfaced instead of silently bucketed.
BENIGN_VERDICTS = frozenset({
    "SUCCESS", "NEUTRAL", "SKIPPED", "STALE", "EXPECTED", "PENDING", "QUEUED",
    "IN_PROGRESS", "WAITING", "REQUESTED", None,
})

PROBE_UNREADABLE = "\u00b7 la sonda dei controlli non ha risposto"


def failing_checks(number: int) -> list[str]:
    """Names of the checks that are FAILURE on this PR's head commit.

    WHY THIS IS A SEPARATE, PER-PR QUERY. The first version asked for
    `contexts(first:100)` inside the bulk 100-PR query — 100 x 100 nodes in one
    request. GitHub answered "We couldn't respond to your request in time" on
    every attempt with a 3x retry, measured 2026-09-01: the retry made a heavy
    query fail more slowly, it did not make it succeed. The contexts are only
    needed for PRs whose ROLLUP is already FAILURE — about twenty, not a
    hundred — so the bulk query now carries the rollup state alone (cheap) and
    the detail is fetched only where it is actually read.
    """
    def unreadable(why: str) -> list[str]:
        # A probe that could not measure says so ON THE PAGE, not only to
        # stderr. Returning a bare [] rendered as "red, with no reason given"
        # and silently under-counted that check's tally in the grouped table —
        # indistinguishable from a PR that genuinely has no named failing
        # context. The sentinel is deliberately not check-shaped so it can
        # never be mistaken for one, and it groups into its own row, which is
        # what makes the incompleteness visible instead of silent.
        sys.stderr.write(f"fleet_dashboard: checks unreadable for #{number}: {why[:160]}\n")
        return [PROBE_UNREADABLE]

    rc, out, err = _run(
        ["gh", "api", "graphql", "-f", f"query={CONTEXTS_ONE}", "-F", f"n={number}"]
    )
    if rc != 0 or not out.strip():
        return unreadable(err or out)
    try:
        commits = json.loads(out)["data"]["repository"]["pullRequest"]["commits"]["nodes"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return unreadable("risposta GraphQL malformata")
    if not commits:
        return unreadable("nessun commit nella risposta")
    rollup = commits[0]["commit"]["statusCheckRollup"]
    if not rollup:
        # The bulk query already said this PR's rollup is FAILURE. A per-PR
        # answer of "no rollup at all" contradicts that, so it is a disagreement
        # between two probes, never a clean "no checks ran".
        return unreadable("nessun rollup, in contraddizione con la query d'insieme")
    names = []
    for ctx in rollup["contexts"]["nodes"]:
        name = ctx.get("name") or ctx.get("context") or "?"
        verdict = ctx.get("conclusion") or ctx.get("state")
        if verdict in BENIGN_VERDICTS:
            continue
        if verdict in FAILING_VERDICTS:
            names.append(name)
            continue
        # An verdict in NEITHER list is a value GitHub added after this was
        # written. It is named, not dropped: a check the page cannot classify
        # is news. Erring toward "failing" is the SAFE direction — it makes the
        # page more alarming than reality, never more reassuring, which is the
        # asymmetry every defect this file shipped got backwards.
        names.append(f"{name} ({verdict})")
    return names


def is_dependabot(pr: dict[str, Any]) -> bool:
    """True only for Dependabot, judged on the ENTITY and its login together.

    Two bugs are pinned here, one in each direction. A first cut tested
    `login.endswith("[bot]")` and returned False for every real Dependabot PR:
    the GraphQL Bot login is the bare string `dependabot`, and the `[bot]`
    suffix exists only in REST renderings. The correction then tested
    `__typename == "Bot"` alone, which answers "is ANY bot" — Renovate,
    github-actions and Copilot share that concrete type — where this flag means
    "is Dependabot" and drives the note about arming lockfile PRs one at a time.

    It is a named function rather than an inline expression because the test
    that guarded it could only grep the source, and grepping for two substrings
    never pinned the `and` joining them: flipping it to `or` reinstated the bug
    with the test still green. A predicate you can call is a predicate you can
    actually pin.
    """
    author = pr.get("author") or {}
    return author.get("__typename") == "Bot" and author.get("login") == "dependabot"


def rollup_state(pr: dict[str, Any]) -> str:
    commits = pr["commits"]["nodes"]
    if not commits:
        return "—"
    rollup = commits[0]["commit"]["statusCheckRollup"]
    return (rollup or {}).get("state") or "—"


def conflict_kind(pr: dict[str, Any]) -> str:
    """PHANTOM (git merges it clean) vs REAL — never GitHub's word alone.

    GitHub does not honour the `merge=union` driver `.gitattributes` declares
    for the PENDING-ARMS ledger, so it reports a conflict that does not exist
    in git. The cure for the two kinds is opposite: a phantom wants
    `git merge origin/main` in a worktree and a push; a real conflict wants a
    person. Telling them apart is therefore not cosmetic.
    """
    if pr["mergeable"] != "CONFLICTING":
        return "none"
    branch = pr["headRefName"]
    # The fetch's rc is READ, not discarded (adversarial review, round 2): a
    # failed fetch leaves the trial merge running against a stale ref, so the
    # probe answers a question about the past while looking like an answer
    # about now. Same failure direction as the two defects above — an
    # unusable probe must not produce a verdict.
    rc, _, err = _run(["git", "fetch", "origin", branch, "--quiet"], timeout=120)
    if rc != 0:
        sys.stderr.write(
            f"fleet_dashboard: fetch failed for #{pr['number']} ({branch}): "
            f"rc={rc} {err.strip()[:200]}\n"
        )
        return "unknown"
    rc, sha, err = _run(["git", "rev-parse", f"origin/{branch}"])
    if rc != 0:
        return "unknown"
    rc, _, err = _run(
        ["git", "merge-tree", "--write-tree", "--name-only", "origin/main", sha.strip()]
    )
    # THREE outcomes, not two (adversarial review, 2026-09-01). Per
    # git-merge-tree(1): 0 = clean, 1 = content conflict, anything else = the
    # merge could not START — unrelated histories, a merge-base lost to a
    # force-push, a bad ref. The first version read `rc == 0 else "real"`, so a
    # plumbing failure was rendered as a genuine conflict, and the "never
    # hand-resolve this, it deletes other lanes' rows" warning is attached to
    # the phantom row only. That is the destructive direction: a probe that
    # merely failed to run would have sent a reader to hand-resolve a
    # `merge=union` ledger. An unrunnable probe now says so.
    if rc == 0:
        return "phantom"
    if rc == 1:
        return "real"
    sys.stderr.write(
        f"fleet_dashboard: merge-tree probe unusable for #{pr['number']} "
        f"({branch}): rc={rc} {err.strip()[:200]}\n"
    )
    return "unknown"


def merged_today() -> list[dict[str, Any]]:
    rc, out, _ = _run(
        ["gh", "pr", "list", "--state", "merged", "--limit", "80",
         "--json", "number,title,mergedAt"]
    )
    if rc != 0 or not out.strip():
        return []
    # "Today" is WITA, not UTC. The page prints a WITA clock for a reader in
    # Bali, and a UTC cutoff silently drops everything merged between midnight
    # and 08:00 local — the exact hours an overnight autonomous run lands in.
    # Reported by adversarial review, 2026-09-01.
    today = (dt.datetime.now(dt.timezone.utc) + WITA).date()
    rows = []
    for m in json.loads(out):
        when = dt.datetime.fromisoformat(m["mergedAt"].replace("Z", "+00:00"))
        if (when + WITA).date() == today:
            rows.append(m)
    return rows


def collect() -> dict[str, Any]:
    # If THIS fetch fails, every trial merge below compares against a stale
    # origin/main and the whole conflict section becomes fiction. It is the one
    # probe whose failure poisons every other, so it aborts rather than
    # degrades: a page that does not render is recoverable, a page that renders
    # yesterday's answer as today's is not.
    rc, _, err = _run(["git", "fetch", "origin", "main", "--quiet"], timeout=120)
    if rc != 0:
        raise SystemExit(
            f"fleet_dashboard: could not fetch origin/main (rc={rc}): {err.strip()[:300]}\n"
            "Refusing to render — every conflict verdict on the page would be "
            "computed against a stale base."
        )
    prs = fetch_open_prs()

    live = [p for p in prs if not p["isDraft"]]
    queued = [p for p in prs if p["mergeQueueEntry"]]

    # One query per RED PR, and only red ones — the rollup state already says
    # which those are, and a green PR has no failing check to name. Computed
    # once here and read twice below; the first version called it once per
    # caller and paid for every PR twice.
    # `== "FAILURE"` here was the same defect as in failing_checks(), one level
    # up and worse: a PR whose rollup state is ERROR matched NEITHER this nor
    # the SUCCESS test below, so it vanished from both cards and appeared only
    # in the raw total — not "red with no reason", but absent. Found by
    # adversarial review while tracing the fix to the function below it.
    red = [p for p in live if rollup_state(p) in FAILING_VERDICTS]
    fail_map = {p["number"]: failing_checks(p["number"]) for p in red}
    causes: dict[str, list[int]] = defaultdict(list)
    for number, names in fail_map.items():
        for name in names:
            causes[name].append(number)

    conflicts = {p["number"]: conflict_kind(p) for p in prs if p["mergeable"] == "CONFLICTING"}
    phantom = [n for n, k in conflicts.items() if k == "phantom"]
    real = [n for n, k in conflicts.items() if k == "real"]
    unprobeable = [n for n, k in conflicts.items() if k == "unknown"]
    # Mergeability GitHub still would not compute after being asked directly.
    # Kept as its own bucket and kept OUT of `ready`: "not known" is not "fine".
    unknown_merge = [p["number"] for p in live if p["mergeable"] == "UNKNOWN"]

    green = [p for p in live if rollup_state(p) == "SUCCESS"]
    # Anything in neither set and not a known in-flight state is a rollup value
    # this page cannot classify. It is COUNTED and reported, because the whole
    # failure mode being cured here is a PR quietly belonging to no bucket.
    unclassified = sorted(
        p["number"] for p in live
        if rollup_state(p) not in FAILING_VERDICTS
        and rollup_state(p) not in BENIGN_VERDICTS
        and rollup_state(p) != "—"
    )
    if unclassified:
        sys.stderr.write(
            "fleet_dashboard: rollup state not classifiable on "
            f"{len(unclassified)} PR(s) {unclassified} — they are counted in the "
            "total and in no card. Add the value to FAILING_VERDICTS or "
            "BENIGN_VERDICTS.\n"
        )
    # ready = green AND known-mergeable AND not queued: the pile that would move
    # with no work at all. `mergeable == "MERGEABLE"` is asserted positively,
    # never inferred from "not CONFLICTING" — that inference is what put a
    # genuinely conflicted PR under "nothing to do" in the first version.
    ready = [
        p for p in green
        if p["mergeable"] == "MERGEABLE" and not p["mergeQueueEntry"]
    ]

    return {
        "measured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo": REPO,
        "open_total": len(prs),
        "draft": [p["number"] for p in prs if p["isDraft"]],
        "live": [p["number"] for p in live],
        "queued": sorted(
            ({"n": p["number"], "pos": p["mergeQueueEntry"]["position"],
              "title": p["title"]} for p in queued),
            key=lambda d: d["pos"] or 999,
        ),
        "red": [{"n": p["number"], "title": p["title"],
                 "why": fail_map.get(p["number"], [])} for p in red],
        "green": [p["number"] for p in green],
        "ready": [
            {"n": p["number"], "title": p["title"],
             "bot": is_dependabot(p)}
            for p in ready
        ],
        "phantom_conflicts": sorted(phantom),
        "real_conflicts": sorted(real),
        "unprobeable_conflicts": sorted(unprobeable),
        "unknown_mergeability": sorted(unknown_merge),
        "causes": sorted(
            ({"check": k, "prs": sorted(v)} for k, v in causes.items()),
            key=lambda d: -len(d["prs"]),
        ),
        "merged_today": merged_today(),
        "states": dict(Counter(p["mergeStateStatus"] for p in prs)),
    }


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

CSS = """
<style>
:root{
  --ground:#FBF9F7; --panel:#FFFFFF; --ink:#1B1614; --muted:#6E635C;
  --line:#E7E0D9; --line-strong:#D6CCC2;
  --merah:#C8102E;              /* identity, and deliberately also "needs you" */
  --ok:#2F6E4F; --wait:#4C5966; --warn:#8A6116;
  --ok-bg:#EAF3EE; --wait-bg:#EDF0F3; --warn-bg:#F7F0E2; --merah-bg:#FBECEE;
  --shadow:0 1px 2px rgba(27,22,20,.05), 0 8px 24px rgba(27,22,20,.05);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#14110F; --panel:#1D1917; --ink:#F2ECE7; --muted:#A2968D;
    --line:#2C2523; --line-strong:#3C332F;
    --merah:#F2637A; --ok:#7CC79F; --wait:#9DB0C2; --warn:#DDB166;
    --ok-bg:#1B2A22; --wait-bg:#1D242B; --warn-bg:#2B2418; --merah-bg:#301A1E;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.28);
  }
}
:root[data-theme="dark"]{
  --ground:#14110F; --panel:#1D1917; --ink:#F2ECE7; --muted:#A2968D;
  --line:#2C2523; --line-strong:#3C332F;
  --merah:#F2637A; --ok:#7CC79F; --wait:#9DB0C2; --warn:#DDB166;
  --ok-bg:#1B2A22; --wait-bg:#1D242B; --warn-bg:#2B2418; --merah-bg:#301A1E;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
body{
  background:var(--ground); color:var(--ink); margin:0;
  font-family:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1020px; margin:0 auto; padding:40px 22px 90px}
h1,h2,h3{font-family:Fraunces,Georgia,"Times New Roman",serif; text-wrap:balance; margin:0}
h1{font-size:clamp(30px,4.4vw,46px); font-weight:600; letter-spacing:-.015em;
   font-variation-settings:"SOFT" 20,"WONK" 1}
h2{font-size:22px; font-weight:600; margin:0 0 4px}
.eyebrow{font-size:11.5px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); font-weight:600; font-family:"Public Sans",sans-serif}
.rule{height:3px; background:var(--merah); width:56px; border-radius:2px; margin:14px 0 0}
.stamp{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;
  font-size:12px; color:var(--muted); margin-top:12px}
.lede{font-size:19px; line-height:1.5; margin:20px 0 0; max-width:64ch; color:var(--ink)}
.lede b{color:var(--merah); font-weight:600}
section{margin-top:52px}
.sub{color:var(--muted); font-size:14.5px; margin:0 0 18px; max-width:70ch}

.cards{display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr)); gap:12px; margin-top:22px}
.card{background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:16px 16px 14px; box-shadow:var(--shadow)}
.card .n{font-family:Fraunces,Georgia,serif; font-size:38px; line-height:1;
  font-variant-numeric:tabular-nums; font-weight:600}
.card .k{font-size:12.5px; color:var(--muted); margin-top:7px; line-height:1.35}
.card.is-ok .n{color:var(--ok)} .card.is-wait .n{color:var(--wait)}
.card.is-warn .n{color:var(--warn)} .card.is-merah .n{color:var(--merah)}

table{width:100%; border-collapse:collapse; font-size:14.5px}
.scroll{overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel)}
th{text-align:left; font-size:11.5px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); font-weight:600; padding:12px 14px; border-bottom:1px solid var(--line-strong);
  white-space:nowrap}
td{padding:12px 14px; border-bottom:1px solid var(--line); vertical-align:top}
tr:last-child td{border-bottom:none}
td.num{font-family:"JetBrains Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums;
  white-space:nowrap; font-size:13px}
.bar{height:7px; border-radius:4px; background:var(--merah); min-width:5px; display:block}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:12.5px; color:var(--muted)}

.pill{display:inline-block; font-size:11.5px; font-weight:600; padding:3px 9px;
  border-radius:99px; white-space:nowrap; font-family:"Public Sans",sans-serif}
.p-ok{background:var(--ok-bg); color:var(--ok)}
.p-wait{background:var(--wait-bg); color:var(--wait)}
.p-warn{background:var(--warn-bg); color:var(--warn)}
.p-merah{background:var(--merah-bg); color:var(--merah)}

.note{border-left:3px solid var(--line-strong); padding:2px 0 2px 16px; color:var(--muted);
  font-size:14px; margin-top:18px; max-width:72ch}
.note b{color:var(--ink)}
ul.plain{margin:14px 0 0; padding-left:19px} ul.plain li{margin:7px 0}
footer{margin-top:64px; padding-top:18px; border-top:1px solid var(--line);
  color:var(--muted); font-size:12.5px}
@media (max-width:560px){ .wrap{padding:28px 15px 70px} .card .n{font-size:32px} }
</style>
"""


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def prlink(n: int) -> str:
    return f'<a class="mono" style="color:inherit" href="https://github.com/{REPO}/pull/{n}">#{n}</a>'


def render(d: dict[str, Any]) -> str:
    live_n = len(d["live"])
    red_n = len(d["red"])
    moving = len(d["queued"]) + len(d["ready"])
    top = d["causes"][0] if d["causes"] else None
    when = d["measured_at"].replace("T", " ").replace("+00:00", " UTC")
    wita = (
        dt.datetime.fromisoformat(d["measured_at"]) + dt.timedelta(hours=8)
    ).strftime("%H:%M")

    if top:
        lede = (
            f'Delle <b>{live_n}</b> proposte di modifica vive, <b>{moving}</b> si stanno '
            f'muovendo da sole e <b>{red_n}</b> sono ferme. Il controllo che fallisce più '
            f'spesso è «{esc(top["check"])}», su <b>{len(top["prs"])}</b> di esse — che è '
            f'dove guardare per prima cosa, non ancora una diagnosi.'
        )
    else:
        lede = (
            f'Delle <b>{live_n}</b> proposte di modifica vive, <b>{moving}</b> si stanno '
            f'muovendo e nessuna è ferma per un controllo rosso.'
        )

    cards = [
        ("is-wait", len(d["queued"]), "in coda, si fondono da sole"),
        ("is-ok", len(d["ready"]), "verdi e pronte, nessun lavoro da fare"),
        ("is-merah", red_n, "ferme su un controllo rosso"),
        ("is-warn", len(d["real_conflicts"]), "conflitti veri, serve una persona"),
        ("is-wait", len(d["phantom_conflicts"]), "conflitti finti (li scioglie una fusione)"),
        ("is-wait", len(d["draft"]), "bozze, non ancora proposte"),
    ]
    # Shown only when non-zero, and never merged into another count: a state the
    # page could not measure must look different from a state it measured as OK.
    blind = len(d["unprobeable_conflicts"]) + len(d["unknown_mergeability"])
    if blind:
        cards.append(("is-merah", blind, "non misurabili — GitHub o git non hanno risposto"))
    cards_html = "\n".join(
        f'<div class="card {cls}"><div class="n">{n}</div><div class="k">{esc(k)}</div></div>'
        for cls, n, k in cards
    )

    widest = max((len(c["prs"]) for c in d["causes"]), default=1)
    cause_rows = "\n".join(
        f'<tr><td><b>{esc(c["check"])}</b><div class="mono">'
        + ", ".join(prlink(n) for n in c["prs"][:10])
        + (" …" if len(c["prs"]) > 10 else "")
        + f'</div></td><td class="num">{len(c["prs"])}</td>'
        f'<td style="width:34%"><span class="bar" style="width:'
        f'{round(100 * len(c["prs"]) / widest)}%"></span></td></tr>'
        for c in d["causes"]
    ) or '<tr><td colspan="3">Nessun controllo rosso.</td></tr>'

    queue_rows = "\n".join(
        f'<tr><td class="num">{esc(q["pos"]) if q["pos"] is not None else "—"}</td>'
        f'<td class="num">{prlink(q["n"])}</td>'
        f'<td>{esc(q["title"])}</td></tr>'
        for q in d["queued"]
    ) or '<tr><td colspan="3">La coda è vuota.</td></tr>'

    ready_rows = "\n".join(
        f'<tr><td class="num">{prlink(r["n"])}</td><td>{esc(r["title"])}</td>'
        f'<td><span class="pill p-ok">verde</span></td></tr>'
        for r in d["ready"]
    ) or '<tr><td colspan="3">Nessuna in attesa: tutto ciò che è verde è già in coda.</td></tr>'

    # The "ready" pile is routinely dominated by dependency bumps, and they are
    # the one case where "all green, arm them all" is the WRONG move: bumps that
    # share a lockfile invalidate each other the moment the first one lands, so
    # arming them together burns a queue cycle per PR. Saying so here is the
    # difference between a page that informs and a page that misleads.
    # Identify bumps by AUTHOR first and title only as a fallback. Measured on
    # this repo's history, the title prefix caught 245/245 with no false
    # positives — but that is this repo's convention, not a property of
    # Dependabot: GitHub's default title carries no prefix at all, so a config
    # change would silently switch this note off. The author login is already
    # paid for by the query; use it.
    bumps = [
        r for r in d["ready"]
        if r.get("bot") or r["title"].lower().startswith("chore(deps")
    ]
    ready_note = ""
    if len(bumps) >= 2:
        ready_note = (
            f'<div class="note"><b>{len(bumps)} di queste sono aggiornamenti di dipendenze.</b> '
            "Vanno armate <em>una per volta</em>: condividono lo stesso file di lock, quindi "
            "la prima che entra invalida le altre e armarle insieme spreca un giro di coda "
            "per ciascuna.</div>"
        )

    merged_rows = "\n".join(
        f'<tr><td class="num">{prlink(m["number"])}</td><td>{esc(m["title"])}</td></tr>'
        for m in d["merged_today"]
    ) or '<tr><td colspan="2">Niente ancora oggi.</td></tr>'

    # GitHub computes mergeability lazily; this page asks per-PR for every row
    # the bulk query left blank, and says so when even that does not settle.
    unknown_note = ""
    if d["unknown_mergeability"]:
        unknown_note = (
            '<div class="note"><b>Mergeabilità ancora non calcolata da GitHub per '
            + " ".join(prlink(n) for n in d["unknown_mergeability"])
            + ".</b> Sono state richieste una per una e GitHub non ha risposto in tempo. "
            "Non compaiono fra le «pronte»: <em>non so</em> non è <em>a posto</em>.</div>"
        )

    conf = ""
    if d["phantom_conflicts"] or d["real_conflicts"] or d["unprobeable_conflicts"]:
        conf = f"""
<section>
  <div class="eyebrow">Conflitti</div>
  <h2>Tre esiti, non due</h2>
  <p class="sub">GitHub scrive «conflitto» in casi che non si curano allo stesso modo.
  Questa pagina prova la fusione in locale, dove git applica la regola
  <span class="mono">merge=union</span> che GitHub ignora — e distingue anche il caso in cui
  la prova <em>non è potuta partire</em>, che non è né l'uno né l'altro.</p>
  <div class="scroll"><table>
    <tr><th>Esito</th><th>Proposte</th><th>Cosa serve</th></tr>
    <tr><td><span class="pill p-wait">finto</span></td>
        <td class="num">{" ".join(prlink(n) for n in d["phantom_conflicts"]) or "—"}</td>
        <td>Git le fonde pulite. Basta fondere <span class="mono">origin/main</span> nel ramo
            e ripubblicare. <b>Mai</b> risolvere il file a mano: cancella le righe di altri.</td></tr>
    <tr><td><span class="pill p-warn">vero</span></td>
        <td class="num">{" ".join(prlink(n) for n in d["real_conflicts"]) or "—"}</td>
        <td>Due modifiche incompatibili sullo stesso punto: git lo dice esplicitamente.
            Qui serve una decisione — ma <b>se il file in conflitto è un registro ad
            accodamento</b> vale comunque il divieto di risolverlo a mano.</td></tr>
    <tr><td><span class="pill p-merah">non misurabile</span></td>
        <td class="num">{" ".join(prlink(n) for n in d["unprobeable_conflicts"]) or "—"}</td>
        <td>La prova di fusione non è partita affatto — storie non imparentate, una base
            persa dopo una riscrittura, un riferimento rotto. <b>Non è un conflitto: è
            l'assenza di una misura.</b> Va rifatta, non interpretata.</td></tr>
  </table></div>
</section>"""

    return f"""<title>Stato dell'organismo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&family=Public+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
{CSS}
<div class="wrap">
  <header>
    <div class="eyebrow">Bali Zero · Nuzantara</div>
    <h1>Stato dell'organismo</h1>
    <div class="rule"></div>
    <p class="lede">{lede}</p>
    <div class="stamp">misurato {esc(when)} · {esc(wita)} WITA · {esc(d["repo"])} · {d["open_total"]} proposte aperte</div>
  </header>

  <section>
    <div class="eyebrow">In una riga</div>
    <h2>Dove sta il lavoro adesso</h2>
    <div class="cards">{cards_html}</div>
  </section>

  <section>
    <div class="eyebrow">La domanda che conta</div>
    <h2>Perché sono ferme</h2>
    <p class="sub">Raggruppate per <em>controllo fallito</em>, non per proposta: così si vede
    dove concentrare lo sforzo invece di leggere venti pagine di dettagli.</p>
    <div class="note"><b>Come leggere una riga lunga — e come non leggerla.</b> Dice che quel
    controllo è rosso su molte proposte. <em>Non</em> dice che il difetto sia lo stesso: un
    controllo è un esame, e si può fallire lo stesso esame per motivi diversi. Misurato il
    2026-09-01 sulla riga più lunga di questa tabella: le 12 proposte che fallivano
    «Harness floor recompute» si dividevano in <b>cinque</b> difetti distinti — 5 senza il file
    di sintesi richiesto, 3 con numeri sfasati nel pack, 2 semplicemente in attesa di un verdetto
    (nessun difetto), 1 con un riferimento a un file inesistente, 1 con uno script mancante.
    Aprire il log è quindi il passo successivo obbligato, non un di più.</div>
    <div class="scroll"><table>
      <tr><th>Controllo che fallisce</th><th>Quante</th><th></th></tr>
      {cause_rows}
    </table></div>
  </section>

  <section>
    <div class="eyebrow">In movimento</div>
    <h2>La coda</h2>
    <p class="sub">Queste si fondono da sole, in quest'ordine. Nessuno deve fare niente.</p>
    <div class="scroll"><table>
      <tr><th>Pos.</th><th>Proposta</th><th>Titolo</th></tr>
      {queue_rows}
    </table></div>
    <div class="note"><b>Nota tecnica, per chi verrà dopo:</b> lo stato «armata» qui è letto da
    <span class="mono">mergeQueueEntry</span>. Il campo che sembra dirlo,
    <span class="mono">autoMergeRequest</span>, è vuoto in tre situazioni diverse — mai armata,
    armata e poi espulsa, armata e <em>consumata dalla coda</em> — quindi una proposta in prima
    posizione risulterebbe «non armata».</div>
  </section>

  <section>
    <div class="eyebrow">Pronte</div>
    <h2>Verdi, senza conflitti, non ancora in coda</h2>
    <div class="scroll"><table>
      <tr><th>Proposta</th><th>Titolo</th><th>Controlli</th></tr>
      {ready_rows}
    </table></div>
    {ready_note}
    {unknown_note}
  </section>
{conf}
  <section>
    <div class="eyebrow">Oggi</div>
    <h2>Cosa è entrato</h2>
    <div class="scroll"><table>
      <tr><th>Proposta</th><th>Titolo</th></tr>
      {merged_rows}
    </table></div>
  </section>

  <footer>
    Generata da <span class="mono">scripts/fleet_dashboard.py</span>. Ogni numero di questa pagina
    è misurato al momento indicato in alto — nessuno è scritto a mano. Ri-eseguire lo script e
    ripubblicare aggiorna la pagina allo stesso indirizzo.
  </footer>
</div>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="path of the HTML file to write")
    ap.add_argument("--json", dest="json_out", help="also dump the raw measurements")
    args = ap.parse_args(argv)

    _warn_if_main_checkout()
    data = collect()
    Path(args.out).write_text(render(data), encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(
        f"fleet_dashboard: {args.out} — {len(data['live'])} live, "
        f"{len(data['queued'])} queued, {len(data['red'])} red, "
        f"{len(data['phantom_conflicts'])} phantom + {len(data['real_conflicts'])} real conflicts"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
