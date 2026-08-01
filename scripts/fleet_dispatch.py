#!/usr/bin/env python3
"""fleet_dispatch — place implementation lanes across M5/Pro/Mini, in parallel,
without losing quality.

WHY THIS EXISTS (measured on M5 2026-08-01 12:07 WITA, not recalled): the fleet
was perfectly ALIGNED (all three nodes on 8f2a3545e, 0 behind) and perfectly
IMBALANCED — normalized load M5 7.76/10 = 0.78, Pro 5.81/14 = 0.42, Mini
2.28/12 = 0.19 with 38 days of uptime. Zero suite locks were held anywhere. The
fleet was not saturated; the work simply had no way to reach the idle machine.

Everything needed to run a lane already existed EXCEPT the two decisions that
come before it:

  1. WHERE can a lane go?   `agent_start.py` has no --machine flag: it derives
     the branch namespace from the LOCAL `socket.gethostname()`, so a session
     on M5 can only ever create worktrees on M5. `proprioception.py` has no
     load/memory probe at all, and `fleet_watch.py` answers only alive-vs-dark
     — liveness, never capacity.
  2. MAY a lane go there?   Nothing in the tree knows that a lane on Mini and a
     lane on M5 are editing the same file.

This module supplies exactly those two answers and nothing else. It does not
schedule, does not daemonize, does not run the agent — it is a CLI that a
session calls before opening a lane. (No new cron: 176 daemons already exist and
W84 proved launchd fragile.)

THE QUALITY HALF, and why it is a REFUSAL rather than a warning: the repo has
already ratified the finding in `federation_parallelize.py` §4 cond. 2 (Google
arXiv 2512.08296) — of the four kinds of parallelism, three are free and one is
actively negative: **coders on the SAME artifact degrade ~70%**. Parallelism
that collides is worth less than serial work, so `place` treats an overlap as a
hard refusal (exit 1), never a printed caveat. Same doctrine as that module:
**ambiguity resolves to serial**, and here that phrase is load-bearing in three
places an earlier draft got wrong (all three found by an adversarial review on
2026-08-01, all three reproduced before being fixed):

  * a node that cannot be probed is NOT skipped. If Pro holds a lane on the
    file you asked for and Pro's ssh is down, the honest answer is "I cannot
    prove this is free", and that refuses. The first draft printed a warning
    and placed the lane anyway — the advertised fail-closed contract was false
    on the exact path it existed for.
  * the lane scan proves it RAN. `git ... | awk | while` yields the exit status
    of the `while`, so a missing repo produced rc=0 with empty stdout, which is
    byte-identical to "this node has no lanes". This module's own docstring
    quotes W84 ("a blind sweep is not a clean sweep") — and the first draft had
    the disease it names. Now the snippet must terminate with FLEET_LANES_DONE
    or the scan is treated as failed.
  * `--files` is REQUIRED. It was optional, and omitting it silently skipped
    the only check that makes parallel lanes safe.

PROBE DISCIPLINE (the rest of the scars this is built against):

* **Judge the REPLY, never the exit code** (W104). Every probe carries a
  sentinel; a node whose output lacks it is UNPROBEABLE, never "fine". A
  TRUNCATED reply is equally not fine: `classify` requires every capacity field
  it reasons about to be present, because a partial line missing only `lock`
  read as READY in the first draft.
* **A blind sweep is not a clean sweep** (W84): zero nodes answered → exit 4.
* **Never claim alignment from a possibly-stale ref** (W106b): HEADs are
  compared to EACH OTHER — a claim this data supports — not to origin, unless
  `--fetch` makes each node re-fetch and answer for itself.
* **The local node runs the SAME snippet as the remote ones**, via `sh -c`
  instead of `ssh`. A control that does not share the mechanism under test
  proves nothing about it.
* **No `set -e` in the probe snippets, deliberately** (W101/W108, four
  generations deep): under errexit a failing sub-probe aborts before the line
  that would REPORT the failure.
* **Git output is parsed in Python, not in awk.** `git status --porcelain`
  collapses a wholly-untracked directory to `dir/` (so `-uall` is mandatory or
  `dir/a.py` never collides) and renders a rename as `R  old -> new` (so taking
  the last field loses `old`, and a lane asking for `old` is waved through).
  Both were live false-negatives. Word-splitting `for F in $ALL` in sh also
  glob-expanded and split on spaces; the shell now emits raw lines and Python
  does every bit of the parsing.

DECLARED SCOPE, and why a fresh lane does not block the fleet: a worktree
created seconds ago has no files, and "no files" cannot prove non-overlap — so
strict fail-closed would mean the second `place` in a row always refuses, which
would make the tool useless and get it switched off (superscar #3's endgame: an
over-match annoying enough to disarm the guard). `place` therefore RECORDS the
scope it was given, in a sidecar on the target machine
(~/.organism/fleet_dispatch/lanes/<worktree>.scope), and the scan reports it. A
lane opened through `place` is knowable from birth; a lane made by a bare
`git worktree add` still blocks, which is the correct incentive.

KNOWN RESIDUAL RACE, declared rather than hidden: the check and the creation are
not atomic across machines. Two `place` calls issued concurrently from two
different sessions can both observe no collision and then both create a lane on
the same file. The sidecar is written by `agent_start.py`'s target before this
command returns, which narrows the window to the probe-plus-create duration, but
it does not close it. Closing it needs a fleet-wide reservation (the Redis lease
registry in `scripts/agent_lease.py` is the natural home). Tracked in
PENDING-ARMS; do not read the collision check as a mutex.

Exit codes:
  0  success (capacity printed / lane placed)
  1  refused — no node has capacity, the requested files collide with a live
     lane, or a lane's scope (or a whole node) could not be verified
  2  usage error
  4  BLIND — not a single node answered; no verdict is possible

Kill switch: FLEET_DISPATCH_ENABLED=false (exit 0, does nothing).

Usage:
    fleet_dispatch.py capacity [--json] [--fetch]
    fleet_dispatch.py place --lane infra --task-id my-task --files a.py b.py \\
                            [--prefer mini] [--dry-run] [--allow-unknown-scope]
    fleet_dispatch.py place --lane infra --task-id t --no-collision-check
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import shlex
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
NODES_CONFIG = REPO_ROOT / "infra" / "fleet" / "nodes.json"

SSH_TIMEOUT_S = int(os.environ.get("FLEET_DISPATCH_SSH_TIMEOUT", "20"))
PROBE_TIMEOUT_S = SSH_TIMEOUT_S + 25

# Normalized load = load1 / cores, so a 10-core M5 and a 14-core Pro compare.
LOAD_BUSY = float(os.environ.get("FLEET_DISPATCH_LOAD_BUSY", "0.60"))
LOAD_SATURATED = float(os.environ.get("FLEET_DISPATCH_LOAD_SATURATED", "1.00"))
# A full backend suite has been measured taking a machine to ~124MB free (see
# prepush_suite_lock.sh's header). Below this, adding a lane is how a push gets
# SIGTERM-killed mid-suite — silent work loss.
MIN_AVAIL_MB = int(os.environ.get("FLEET_DISPATCH_MIN_AVAIL_MB", "2048"))

VERDICT_READY = "READY"
VERDICT_BUSY = "BUSY"
VERDICT_SATURATED = "SATURATED"
VERDICT_DARK = "DARK"

PLACEABLE = (VERDICT_READY, VERDICT_BUSY)

# Every field classify() reasons about. A reply missing any of them is
# TRUNCATED, and a truncated reply is not a green one.
REQUIRED_CAP_FIELDS = ("cores", "load1", "avail_mb", "lock")

# The lockfile .husky/pre-push hands to prepush_suite_lock.sh. Held == a full
# backend suite is running on that machine right now.
SUITE_LOCKFILE = "/tmp/nuzantara-prepush-backend-suite.lock"

# Where `place` records the scope it was given, on the TARGET machine.
SCOPE_DIR = "$HOME/.organism/fleet_dispatch/lanes"

# ---------------------------------------------------------------------------
# The probe snippets. POSIX sh, run byte-identically on every node (local via
# `sh -c`, remote via ssh) so the local answer can never be produced by a
# different mechanism than the remote one.
# ---------------------------------------------------------------------------

CAPACITY_SH = r"""
set -u
# LC_ALL=C is load-bearing, not hygiene. Zero's Macs run LANG=it_IT.UTF-8, and
# under it `sysctl -n vm.loadavg` prints `{ 3,38 4,82 4,95 }` — a COMMA decimal
# separator that float() rejects, so load1 degraded to -1 and classify() called
# every machine in the fleet SATURATED. Fail-closed meant the tool was never
# WRONG, only useless: it would have refused to place a single lane anywhere,
# on all three machines, forever. Caught by the corpus actually EXECUTING this
# snippet (a parser test would have passed happily on hand-written dot input).
# Fixed at the source rather than by teaching the parser to accept both forms:
# the reading should not depend on who is reading it.
export LC_ALL=C
REPO="$HOME/nuzantara"

CORES=$(sysctl -n hw.ncpu 2>/dev/null || echo 0)
LOAD1=$(sysctl -n vm.loadavg 2>/dev/null | tr -d '{}' | awk '{print $1}')
[ -z "${LOAD1:-}" ] && LOAD1=-1

PAGESZ=$(vm_stat 2>/dev/null | head -1 | sed -n 's/.*page size of \([0-9]*\).*/\1/p')
[ -z "${PAGESZ:-}" ] && PAGESZ=4096
PAGES=$(vm_stat 2>/dev/null | awk '
    /^Pages free/        {f=$3}
    /^Pages inactive/    {i=$3}
    /^Pages speculative/ {s=$3}
    END {gsub(/\./,"",f); gsub(/\./,"",i); gsub(/\./,"",s);
         print (f+0)+(i+0)+(s+0)}')
[ -z "${PAGES:-}" ] && PAGES=0
AVAIL_MB=$(( PAGES * PAGESZ / 1048576 ))

LOCK="__SUITE_LOCKFILE__"
LOCK_STATE=free
LOCK_PID=none
if [ -d "$LOCK" ]; then
    LOCK_PID=$(cat "$LOCK/pid" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        LOCK_STATE=held
    else
        LOCK_STATE=stale
        [ -z "$LOCK_PID" ] && LOCK_PID=none
    fi
fi

HEAD=unknown
WORKTREES=-1
DIRTY=-1
BEHIND=-1
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
    __FETCH__
    HEAD=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)
    WT_RAW=$(git -C "$REPO" worktree list 2>/dev/null | wc -l | tr -d ' ')
    WORKTREES=$(( WT_RAW - 1 ))
    # `git status` failing must not silently read as a clean tree: wc -l would
    # turn its empty output into 0. Capture the status separately.
    ST=$(git -C "$REPO" status --porcelain 2>/dev/null)
    if [ $? -eq 0 ]; then
        DIRTY=$(printf '%s' "$ST" | grep -c . || true)
    fi
    BEHIND=$(git -C "$REPO" rev-list --count HEAD..origin/main 2>/dev/null || echo -1)
fi

printf 'FLEET_CAP host=%s cores=%s load1=%s avail_mb=%s lock=%s lock_pid=%s head=%s worktrees=%s dirty=%s behind=%s\n' \
    "$(hostname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')" \
    "$CORES" "$LOAD1" "$AVAIL_MB" "$LOCK_STATE" "$LOCK_PID" \
    "$HEAD" "$WORKTREES" "$DIRTY" "$BEHIND"
"""

# Emits RAW git output, one record per line, and MUST terminate with
# FLEET_LANES_DONE. Everything is parsed in Python: `awk '{print $NF}'` lost the
# source side of a rename and could not see inside an untracked directory, and
# `for F in $list` in sh word-split and glob-expanded real paths.
#
# `-uall` is mandatory: without it git reports a wholly-untracked directory as
# `?? dir/`, so a lane writing dir/a.py advertises nothing that would collide
# with a request for dir/a.py.
LANES_SH = r"""
set -u
export LC_ALL=C
REPO="$HOME/nuzantara"
SCOPE_DIR="__SCOPE_DIR__"

if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
    printf 'FLEET_LANES_ERR no-repo-at %s\n' "$REPO"
    exit 0
fi

WT_LIST=$(git -C "$REPO" worktree list --porcelain 2>/dev/null)
if [ -z "$WT_LIST" ]; then
    printf 'FLEET_LANES_ERR worktree-list-empty-or-failed\n'
    exit 0
fi

N=0
printf '%s\n' "$WT_LIST" | awk '/^worktree /{print substr($0, 10)}' | while IFS= read -r WT; do
    [ "$WT" = "$REPO" ] && continue
    NAME=$(basename "$WT")
    BR=$(git -C "$WT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)
    printf 'FLEET_LANE_BEGIN %s %s\n' "$NAME" "$BR"

    # Scope declared at creation time by `place`, if this lane came from it.
    # The sidecar outlives the worktree (nothing reaps it), so a task-id reused
    # for different work would inherit a stale declaration and be refused for
    # files it never touches. Bind it to the branch: a declaration for another
    # branch is ignored outright rather than trusted or half-trusted.
    SCOPE_FILE="$SCOPE_DIR/$NAME.scope"
    if [ -f "$SCOPE_FILE" ]; then
        SCOPE_BR=$(head -1 "$SCOPE_FILE" 2>/dev/null | sed -n 's/^branch=//p')
        if [ -n "$SCOPE_BR" ] && [ "$SCOPE_BR" = "$BR" ]; then
            tail -n +2 "$SCOPE_FILE" | while IFS= read -r DECL; do
                [ -n "$DECL" ] && printf 'FLEET_LANE_DECL %s %s\n' "$NAME" "$DECL"
            done
            printf 'FLEET_LANE_DECLOK %s\n' "$NAME"
        else
            printf 'FLEET_LANE_DECLSTALE %s\n' "$NAME"
        fi
    fi

    MB=$(git -C "$WT" merge-base origin/main HEAD 2>/dev/null || echo "")
    if [ -n "$MB" ]; then
        if DIFF=$(git -C "$WT" diff --name-only "$MB" HEAD 2>/dev/null); then
            printf '%s\n' "$DIFF" | while IFS= read -r F; do
                [ -n "$F" ] && printf 'FLEET_LANE_DIFF %s %s\n' "$NAME" "$F"
            done
            printf 'FLEET_LANE_DIFFOK %s\n' "$NAME"
        fi
    else
        printf 'FLEET_LANE_DIFFOK %s\n' "$NAME"
    fi

    if ST=$(git -C "$WT" status --porcelain -uall 2>/dev/null); then
        printf '%s\n' "$ST" | while IFS= read -r L; do
            [ -n "$L" ] && printf 'FLEET_LANE_WIP %s %s\n' "$NAME" "$L"
        done
        printf 'FLEET_LANE_WIPOK %s\n' "$NAME"
    fi

    printf 'FLEET_LANE_END %s\n' "$NAME"
done

printf 'FLEET_LANES_DONE\n'
"""

Runner = Callable[[list[str], int], "subprocess.CompletedProcess[str]"]


def _run(cmd: list[str], timeout: int) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
    )


def load_nodes(config: Path = NODES_CONFIG) -> list[dict]:
    data = json.loads(config.read_text())
    nodes = data.get("nodes") or []
    if not nodes:
        raise ValueError(f"{config}: roster has no nodes")
    return nodes


def local_hostname() -> str:
    return socket.gethostname().split(".")[0].lower()


def is_local(node: dict, hostname: str) -> bool:
    """Exact-match on the canonical hostname — never a substring.

    Superscar family #3: a substring test would make `mini` match `mini-pro2`
    AND any future `mini-*`, and the failure is silent (a remote node probed as
    if it were this one).
    """
    return node.get("hostname", "").lower() == hostname


def build_command(node: dict, script: str, hostname: str) -> list[str]:
    if is_local(node, hostname):
        return ["sh", "-c", script]
    return [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={SSH_TIMEOUT_S}",
        node["ssh_alias"],
        script,
    ]


def normalize_path(raw: str) -> str:
    """Repo-relative, normalized, no leading `./`, no trailing slash.

    Without this, `./scripts/x.py` and `scripts/x.py` are different strings and
    a set intersection misses a real collision — verified live before the fix.
    """
    cleaned = raw.strip().strip('"')
    if cleaned.startswith(str(REPO_ROOT)):
        cleaned = cleaned[len(str(REPO_ROOT)):]
    cleaned = posixpath.normpath(cleaned.lstrip("/"))
    return "" if cleaned in (".", "") else cleaned


def paths_conflict(a: str, b: str) -> bool:
    """True when two paths name the same work — equal, or one contains the other.

    A lane editing `apps/mouth/` and a request for `apps/mouth/page.tsx` are the
    same artifact; comparing only for equality would wave that through.
    """
    if a == b:
        return True
    return a.startswith(b + "/") or b.startswith(a + "/")


def parse_capacity_line(line: str) -> dict | None:
    """Parse one `FLEET_CAP k=v ...` line. Returns None for anything else."""
    if not line.startswith("FLEET_CAP "):
        return None
    fields: dict = {}
    for token in line[len("FLEET_CAP "):].split():
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        fields[key] = value
    present = {k for k in REQUIRED_CAP_FIELDS if k in fields}
    fields["_missing"] = sorted(set(REQUIRED_CAP_FIELDS) - present)
    for key in ("cores", "avail_mb", "worktrees", "dirty", "behind"):
        try:
            fields[key] = int(fields.get(key, -1))
        except (TypeError, ValueError):
            fields[key] = -1
    try:
        fields["load1"] = float(fields.get("load1", -1))
    except (TypeError, ValueError):
        fields["load1"] = -1.0
    return fields


def probe_node(node: dict, hostname: str, fetch: bool, run: Runner = _run) -> dict:
    """Probe one node. Always returns a dict; DARK when it did not answer."""
    script = CAPACITY_SH.replace("__SUITE_LOCKFILE__", SUITE_LOCKFILE).replace(
        "__FETCH__",
        'git -C "$REPO" fetch --quiet origin main 2>/dev/null || true' if fetch else "",
    )
    result = {"name": node["name"], "verdict": VERDICT_DARK, "reason": ""}
    try:
        proc = run(build_command(node, script, hostname), PROBE_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["reason"] = f"probe did not run: {type(exc).__name__}"
        return result

    # W104: the exit code is NOT the reply. Look for the sentinel; a node that
    # exits 0 with no FLEET_CAP line has told us nothing and is not "fine".
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith("FLEET_CAP ")),
        None,
    )
    if line is None:
        stderr = (proc.stderr or "").strip().splitlines()
        result["reason"] = (
            f"no FLEET_CAP sentinel (rc={proc.returncode})"
            + (f": {stderr[-1][:120]}" if stderr else "")
        )
        return result

    fields = parse_capacity_line(line) or {}
    result.update(fields)
    result["load_norm"] = (
        round(fields["load1"] / fields["cores"], 3)
        if fields.get("cores", 0) > 0 and fields.get("load1", -1) >= 0
        else -1.0
    )
    result["verdict"], result["reason"] = classify(result)
    return result


def classify(cap: dict) -> tuple[str, str]:
    """Verdict for one probed node. Unknowable signals degrade to SATURATED.

    Not to READY: an unreadable or ABSENT reading is a reason to withhold work
    from a machine, never a reason to send it there. The missing-field check is
    the second half of that — a truncated FLEET_CAP line carrying a healthy load
    and no `lock` field classified as READY before it existed.
    """
    missing = cap.get("_missing") or []
    if missing:
        return VERDICT_SATURATED, f"truncated reply, missing {', '.join(missing)}"
    load_norm = cap.get("load_norm", -1.0)
    avail_mb = cap.get("avail_mb", -1)
    if load_norm < 0 or avail_mb < 0:
        return VERDICT_SATURATED, "capacity signals unreadable — fail-closed"
    if avail_mb < MIN_AVAIL_MB:
        return VERDICT_SATURATED, f"only {avail_mb}MB available (min {MIN_AVAIL_MB})"
    if load_norm >= LOAD_SATURATED:
        return VERDICT_SATURATED, f"load {load_norm} >= {LOAD_SATURATED} per core"
    if cap.get("lock") == "held":
        return VERDICT_BUSY, f"backend suite running (lock pid {cap.get('lock_pid')})"
    if load_norm >= LOAD_BUSY:
        return VERDICT_BUSY, f"load {load_norm} >= {LOAD_BUSY} per core"
    return VERDICT_READY, f"load {load_norm} per core, {avail_mb}MB available"


def choose(caps: list[dict], prefer: str | None = None) -> tuple[dict | None, str]:
    """Pick the node to place a lane on. Returns (node_cap, why)."""
    if prefer:
        match = next((c for c in caps if c["name"] == prefer), None)
        if match is None:
            return None, f"--prefer {prefer}: no such node in the roster"
        if match["verdict"] not in PLACEABLE:
            return None, f"--prefer {prefer}: node is {match['verdict']} ({match['reason']})"
        return match, f"explicitly requested (--prefer {prefer})"

    ready = [c for c in caps if c["verdict"] == VERDICT_READY]
    pool, tier = (ready, "READY") if ready else (
        [c for c in caps if c["verdict"] == VERDICT_BUSY], "BUSY (no READY node)"
    )
    if not pool:
        return None, "no node is placeable — every node is SATURATED or DARK"
    # Freest first; ties broken by the node carrying fewer lanes already.
    pool.sort(key=lambda c: (c.get("load_norm", 99), c.get("worktrees", 99)))
    winner = pool[0]
    return winner, (
        f"freest {tier} node: load {winner.get('load_norm')} per core, "
        f"{winner.get('avail_mb')}MB available, {winner.get('worktrees')} lane(s) open"
    )


def parse_porcelain_paths(line: str) -> tuple[list[str], bool]:
    """Paths named by one `git status --porcelain -uall` line.

    Returns (paths, opaque). A rename yields BOTH sides: `R  old -> new` means
    the lane owns `old` as much as `new`, and keeping only the last field let a
    request for `old` through. A git-quoted path (spaces/specials) is reported
    opaque rather than guessed at — dequoting C-style escapes by hand is how a
    scanner invents a path that does not exist.
    """
    body = line[3:] if len(line) > 3 else ""
    if '"' in body:
        return [], True
    if " -> " in body:
        old, _, new = body.partition(" -> ")
        return [p for p in (old.strip(), new.strip()) if p], False
    stripped = body.strip()
    return ([stripped] if stripped else []), False


def parse_lane_lines(lines: list[str], node_name: str) -> tuple[list[dict], bool]:
    """Turn FLEET_LANE* output into lane records. Returns (lanes, completed).

    `completed` is False unless the terminal FLEET_LANES_DONE sentinel arrived:
    a scan that died halfway prints a prefix of the truth, which is exactly the
    shape that reads as "no lanes here".
    """
    lanes: dict[str, dict] = {}
    completed = False

    def lane(name: str) -> dict:
        return lanes.setdefault(
            name,
            {"node": node_name, "worktree": name, "branch": "unknown",
             "files": set(), "declared": set(),
             "diff_ok": False, "wip_ok": False, "decl_ok": False,
             "opaque": False},
        )

    for raw in lines:
        parts = raw.split(" ", 2)
        tag = parts[0]
        if tag == "FLEET_LANES_DONE":
            completed = True
        elif tag == "FLEET_LANES_ERR":
            return [], False
        elif tag == "FLEET_LANE_BEGIN" and len(parts) >= 3:
            lane(parts[1])["branch"] = parts[2].strip()
        elif tag == "FLEET_LANE_DIFF" and len(parts) >= 3:
            path = normalize_path(parts[2])
            if path:
                lane(parts[1])["files"].add(path)
        elif tag == "FLEET_LANE_WIP" and len(parts) >= 3:
            paths, opaque = parse_porcelain_paths(parts[2])
            entry = lane(parts[1])
            entry["opaque"] = entry["opaque"] or opaque
            for path in paths:
                normalized = normalize_path(path)
                if normalized:
                    entry["files"].add(normalized)
        elif tag == "FLEET_LANE_DECL" and len(parts) >= 3:
            path = normalize_path(parts[2])
            if path:
                lane(parts[1])["declared"].add(path)
        elif tag == "FLEET_LANE_DIFFOK" and len(parts) >= 2:
            lane(parts[1])["diff_ok"] = True
        elif tag == "FLEET_LANE_WIPOK" and len(parts) >= 2:
            lane(parts[1])["wip_ok"] = True
        elif tag == "FLEET_LANE_DECLOK" and len(parts) >= 2:
            lane(parts[1])["decl_ok"] = True
        elif tag == "FLEET_LANE_DECLSTALE" and len(parts) >= 2:
            # A sidecar left by a PREVIOUS lane of the same name. Not trusted,
            # and not treated as a declaration: the lane falls back to whatever
            # its files say, which for a fresh one is `empty`.
            lane(parts[1])["decl_stale"] = True

    for entry in lanes.values():
        entry["scope"] = _scope_of(entry)
    return list(lanes.values()), completed


def _scope_of(entry: dict) -> str:
    """known | declared | opaque | partial | empty — why we do or don't trust it."""
    if entry["opaque"]:
        return "opaque"
    if not (entry["diff_ok"] and entry["wip_ok"]):
        return "partial"
    if entry["files"]:
        return "known"
    if entry["decl_ok"]:
        # Created through `place`, which recorded what it intends to touch.
        return "declared"
    return "empty"


def probe_lanes(node: dict, hostname: str, run: Runner = _run) -> tuple[list[dict], bool]:
    """Return (lanes, answered). `answered` False means the scan is not trustworthy."""
    script = LANES_SH.replace("__SCOPE_DIR__", SCOPE_DIR)
    try:
        proc = run(build_command(node, script, hostname), PROBE_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return [], False
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLEET_LANE")]
    lanes, completed = parse_lane_lines(lines, node["name"])
    return lanes, completed


# A scan that COMPLETED and found no files has measured zero. A scan that could
# not read a path (`opaque`) or never confirmed a step (`partial`) has failed to
# measure. Only the second kind justifies refusing: conflating them is the same
# mistake as reading a blind sweep as a clean one, pointed the other way, and it
# was not theoretical — two long-idle empty worktrees on Pro blocked EVERY
# placement across the whole fleet the first time this ran for real. A guard
# that stops all work because a lane elsewhere might one day touch your file is
# how a guard gets switched off (superscar #3's endgame).
UNMEASURABLE_SCOPES = ("opaque", "partial")


def find_collisions(
    files: set[str], lanes: list[dict]
) -> tuple[list[dict], list[dict]]:
    """(blocking, advisory) for placing a lane that touches `files`.

    BLOCKING:
      - overlap: the lane provably touches one of these paths, by equality or
        containment (federation_parallelize §4 cond. 2 — coders on the SAME
        artifact degrade ~70%). This is the measured case and it is a refusal.
      - unmeasurable: the lane's scope could not be read, so non-overlap cannot
        be proven. Ambiguity resolves to serial, as that module's default does.

    ADVISORY:
      - empty: the scan completed and this lane owns nothing right now. That is
        evidence, not ignorance. It could still start editing your file in a
        moment — but so could a lane that currently owns something else, and no
        pre-flight check closes that race (see the module docstring). Reported
        so the caller can look, never a refusal.
    """
    blocking, advisory = [], []
    for entry in lanes:
        owned = entry["files"] | entry["declared"]
        shared = sorted({w for w in files for o in owned if paths_conflict(w, o)})
        if shared:
            blocking.append({**entry, "why": "overlap", "shared": shared})
        elif entry["scope"] in UNMEASURABLE_SCOPES:
            blocking.append({**entry, "why": f"scope-{entry['scope']}", "shared": []})
        elif entry["scope"] == "empty":
            advisory.append({**entry, "why": "scope-empty", "shared": []})
    return blocking, advisory


def head_agreement(caps: list[dict]) -> tuple[str, list[str]]:
    heads = {c.get("head") for c in caps if c.get("head") not in (None, "unknown")}
    if not heads:
        return "UNKNOWN", []
    if len(heads) == 1:
        return "AGREE", sorted(heads)
    return "DIVERGE", sorted(heads)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _probe_all(fetch: bool, run: Runner) -> tuple[list[dict], list[dict], str]:
    hostname = local_hostname()
    nodes = load_nodes()
    caps = [probe_node(n, hostname, fetch, run) for n in nodes]
    return nodes, caps, hostname


def cmd_capacity(as_json: bool, fetch: bool, run: Runner = _run) -> int:
    _, caps, _ = _probe_all(fetch, run)
    answered = [c for c in caps if c["verdict"] != VERDICT_DARK]

    if as_json:
        print(json.dumps(
            {"nodes": caps, "answered": len(answered), "total": len(caps),
             "head_agreement": head_agreement(answered)[0]},
            indent=2, sort_keys=True, default=str,
        ))
    else:
        print(f"{'node':<6} {'verdict':<10} {'load/core':>9} {'avail':>8} "
              f"{'lanes':>5} {'suite':>6}  why")
        for cap in caps:
            print(
                f"{cap['name']:<6} {cap['verdict']:<10} "
                f"{cap.get('load_norm', -1):>9} "
                f"{str(cap.get('avail_mb', -1)) + 'MB':>8} "
                f"{cap.get('worktrees', -1):>5} {str(cap.get('lock', '?')):>6}  "
                f"{cap['reason']}"
            )
        state, heads = head_agreement(answered)
        print(f"\nprobed {len(answered)}/{len(caps)} node(s) · HEADs {state}"
              + (f" ({heads[0][:9]})" if state == "AGREE" else ""))
        if state == "DIVERGE":
            print("  ⚠️  nodes are on different commits — align MAIN checkouts "
                  "before treating them as one organism (modus ALIGN-FLEET)")
        for cap in caps:
            if cap["verdict"] == VERDICT_DARK:
                print(f"  ⚠️  {cap['name']} DARK: {cap['reason']}")

    # W84: zero probes ran is not a clean bill of health.
    if not answered:
        print("fleet_dispatch: BLIND — not a single node answered; no verdict "
              "is possible (W84)", file=sys.stderr)
        return 4
    return 0


def _collect_lanes(
    nodes: list[dict], caps: list[dict], hostname: str, run: Runner
) -> tuple[list[dict], list[str]]:
    """(lanes across the fleet, names of nodes we could NOT verify)."""
    all_lanes: list[dict] = []
    unverifiable: list[str] = []
    for node in nodes:
        cap = next(c for c in caps if c["name"] == node["name"])
        if cap["verdict"] == VERDICT_DARK:
            unverifiable.append(node["name"])
            continue
        lanes, ok = probe_lanes(node, hostname, run)
        if not ok:
            unverifiable.append(node["name"])
            continue
        all_lanes.extend(lanes)
    return all_lanes, unverifiable


def cmd_place(
    lane: str,
    task_id: str,
    files: list[str],
    prefer: str | None,
    dry_run: bool,
    allow_unknown_scope: bool,
    no_collision_check: bool,
    run: Runner = _run,
) -> int:
    nodes, caps, hostname = _probe_all(False, run)
    answered = [c for c in caps if c["verdict"] != VERDICT_DARK]
    if not answered:
        print("fleet_dispatch: BLIND — not a single node answered (W84)", file=sys.stderr)
        return 4

    wanted = {p for p in (normalize_path(f) for f in files) if p}

    if no_collision_check:
        print("⚠️  --no-collision-check: placing WITHOUT verifying that another "
              "lane is editing these files. Two coders on one artifact measure "
              "~70% worse than one.")
    else:
        all_lanes, unverifiable = _collect_lanes(nodes, caps, hostname, run)

        # A machine we could not read is not a machine with no lanes. Refusing
        # here is the whole fail-closed contract: the first draft warned and
        # placed anyway, so a lane on an ssh-down Pro was invisible.
        if unverifiable and not allow_unknown_scope:
            for name in unverifiable:
                print(f"❌ REFUSED — {name} could not be verified: its lanes "
                      f"cannot be checked for collisions.", file=sys.stderr)
            print("   'I could not look' is not 'nothing is there'. Fix the node, "
                  "or pass --allow-unknown-scope to place anyway.", file=sys.stderr)
            return 1
        for name in unverifiable:
            print(f"⚠️  {name} unverifiable — overridden by --allow-unknown-scope")

        blocking, advisory = find_collisions(wanted, all_lanes)
        hard = [b for b in blocking if b["why"] == "overlap"]
        soft = [b for b in blocking if b["why"] != "overlap"]

        for block in hard:
            print(f"❌ REFUSED — {block['node']}:{block['worktree']} "
                  f"({block['branch']}) already touches: {', '.join(block['shared'])}",
                  file=sys.stderr)
        if hard:
            print("   Two coders on the same artifact measure ~70% WORSE than "
                  "one (federation_parallelize.py §4 cond. 2). Wait for that "
                  "lane, or split the work by file.", file=sys.stderr)
            return 1

        if soft and not allow_unknown_scope:
            for block in soft:
                print(f"❌ REFUSED — {block['node']}:{block['worktree']} "
                      f"({block['branch']}) scope could not be READ "
                      f"({block['why']}): non-overlap cannot be proven.",
                      file=sys.stderr)
            print("   This is a failed measurement, not an empty lane. Fix the "
                  "lane (a git-quoted path or a half-finished scan), or pass "
                  "--allow-unknown-scope once you have checked by hand.",
                  file=sys.stderr)
            return 1
        for block in soft:
            print(f"⚠️  {block['node']}:{block['worktree']} scope {block['why']} "
                  f"— overridden by --allow-unknown-scope")
        for note in advisory:
            print(f"ℹ️  {note['node']}:{note['worktree']} ({note['branch']}) owns "
                  f"nothing yet — measured empty, not unknown; it could still "
                  f"start on your files.")

    winner, why = choose(caps, prefer)
    if winner is None:
        print(f"❌ REFUSED — {why}", file=sys.stderr)
        return 1

    node = next(n for n in nodes if n["name"] == winner["name"])
    create = (
        f'cd "$HOME/nuzantara" && python3 scripts/agent_start.py '
        f"--lane {shlex.quote(lane)} --task-id {shlex.quote(task_id)}"
    )
    print(f"\n→ {winner['name']}: {why}")

    if dry_run:
        print(f"   [dry-run] would run on {winner['name']}: {create}")
        return 0

    try:
        proc = run(build_command(node, create, hostname), PROBE_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"❌ worktree creation did not run on {winner['name']}: {exc}",
              file=sys.stderr)
        return 1

    # agent_start.py's success contract is the WORKTREE_READY line, not rc=0.
    ready = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith("WORKTREE_READY ")),
        None,
    )
    if ready is None:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        print(f"❌ no WORKTREE_READY from {winner['name']} (rc={proc.returncode})",
              file=sys.stderr)
        for line in tail:
            print(f"   {line}", file=sys.stderr)
        return 1

    path = ready.split(" ", 1)[1].strip()
    scope_written = _record_scope(node, hostname, path, wanted, run)
    print(f"✅ WORKTREE_READY {winner['name']}:{path}")
    if wanted and not scope_written:
        print("   ⚠️  scope sidecar NOT written — this lane will read as "
              "'empty' and block the next placement until it has files.")
    if is_local(node, hostname):
        print(f"   enter: cd {shlex.quote(path)} && claude")
    else:
        print(f"   enter: ssh -t {node['ssh_alias']} "
              f"'cd {shlex.quote(path)} && claude'")
    return 0


def _record_scope(
    node: dict, hostname: str, worktree_path: str, files: set[str], run: Runner
) -> bool:
    """Write the declared scope beside the lane, on the TARGET machine.

    This is what lets a freshly created lane — which has no files yet — still
    announce what it is about to touch, so the NEXT placement can see it.

    The first line is `branch=<the lane's branch>`, read back by the scan: the
    sidecar outlives the worktree (nothing reaps it), so without that binding a
    reused task-id would inherit a stale declaration and be refused for files it
    never touches.
    """
    if not files:
        return True
    body = "\n".join(sorted(files))
    name = Path(worktree_path).name
    script = (
        f'mkdir -p "{SCOPE_DIR}" && '
        f'BR=$(git -C {shlex.quote(worktree_path)} rev-parse --abbrev-ref HEAD '
        f"2>/dev/null) && [ -n \"$BR\" ] && "
        f'{{ printf "branch=%s\\n" "$BR"; cat <<\'FLEETEOF\'\n'
        f"{body}\nFLEETEOF\n"
        f'}} > "{SCOPE_DIR}/{shlex.quote(name)}.scope" && '
        f'echo FLEET_SCOPE_WRITTEN'
    )
    try:
        proc = run(build_command(node, script, hostname), PROBE_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "FLEET_SCOPE_WRITTEN" in proc.stdout


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fleet_dispatch.py",
        description="Place implementation lanes across the fleet, in parallel, "
                    "without putting two coders on the same artifact.",
    )
    sub = parser.add_subparsers(dest="command")

    cap = sub.add_parser("capacity", help="where can a lane go right now?")
    cap.add_argument("--json", action="store_true", help="machine-readable output")
    cap.add_argument("--fetch", action="store_true",
                     help="make each node fetch origin/main first, so `behind` "
                          "is authoritative instead of a possibly-stale local ref")

    place = sub.add_parser("place", help="create a lane on the best node")
    place.add_argument("--lane", required=True, help="lane id (see agent_start.py KNOWN_LANES)")
    place.add_argument("--task-id", required=True, help="short task slug")
    place.add_argument("--files", nargs="+", default=[],
                       help="repo-relative files this lane will touch — the "
                            "collision check runs on these, and they are recorded "
                            "so this lane does not block the next one")
    place.add_argument("--no-collision-check", action="store_true",
                       help="place without checking collisions (requires no --files)")
    place.add_argument("--prefer", help="force a node by roster name (m5|pro|mini)")
    place.add_argument("--dry-run", action="store_true", help="decide, create nothing")
    place.add_argument("--allow-unknown-scope", action="store_true",
                       help="place even when a live lane's scope, or a whole "
                            "node, could not be verified (default: refuse)")
    return parser


def main(argv: list[str] | None = None) -> int:
    if os.environ.get("FLEET_DISPATCH_ENABLED", "true").lower() == "false":
        print("fleet_dispatch: disabled by kill switch")
        return 0
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "capacity":
        return cmd_capacity(args.json, args.fetch)
    if args.command == "place":
        # Ambiguity resolves to serial: skipping the check is a decision the
        # caller states out loud, never the default they get by forgetting.
        if not args.files and not args.no_collision_check:
            parser.error(
                "--files is required (the collision check runs on it). Pass "
                "--no-collision-check to place without it, deliberately."
            )
        if args.files and args.no_collision_check:
            parser.error("--files and --no-collision-check are mutually exclusive")
        return cmd_place(
            args.lane, args.task_id, args.files, args.prefer,
            args.dry_run, args.allow_unknown_scope, args.no_collision_check,
        )
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
