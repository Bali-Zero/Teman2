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
**ambiguity resolves to serial**, so a lane whose file scope cannot be
determined blocks placement unless the caller overrides it explicitly.

PROBE DISCIPLINE (the scars this is built against):

* **Judge the REPLY, never the exit code** (W104: `redis-cli` exits 0 while
  putting NOAUTH on stdout). Every probe must return its `FLEET_CAP` /
  `FLEET_LANE` sentinel; a node whose output lacks the sentinel is UNPROBEABLE
  and is reported as such — it is never folded into "everything looks fine".
* **A blind sweep is not a clean sweep** (W84, and `fleet_watch.py`'s own exit-4
  guard): if ZERO nodes answered, exit 4. Zero nodes probed ≠ zero problems.
* **Never claim alignment from a possibly-stale ref** (W106b: the checkout is
  itself a proxy, and the guard that compared against it prescribed overwriting
  the CURRENT copy). This tool therefore compares the three nodes' HEADs
  *against each other* — a claim its own data supports — and says AGREE /
  DIVERGE. It says nothing about origin/main unless `--fetch` is passed, which
  makes each node re-fetch and answer for itself.
* **The local node runs the SAME snippet as the remote ones**, via `sh -c`
  instead of `ssh`. A control that does not share the mechanism under test
  proves nothing about it, and a locally-special-cased probe is exactly how the
  local answer stays green while the remote path is broken.
* **No `set -e` in the probe snippets, deliberately.** W101/W108, four
  generations deep: under errexit a failing sub-probe aborts the script before
  the line that would have REPORTED the failure, so the reporting path is dead
  code on the only run that needs it. Every field degrades to a sentinel value
  on its own.

Exit codes:
  0  success (capacity printed / lane placed)
  1  refused — no node has capacity, or the requested files collide with a live
     lane, or a live lane's scope is unknowable (fail-closed)
  2  usage error
  4  BLIND — not a single node answered; no verdict is possible

Kill switch: FLEET_DISPATCH_ENABLED=false (exit 0, does nothing).

Usage:
    fleet_dispatch.py capacity [--json] [--fetch]
    fleet_dispatch.py place --lane infra --task-id my-task \\
                            [--files a.py b.py] [--prefer mini] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
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

# Verdict thresholds. Normalized load = load1 / cores, so they are comparable
# across a 10-core M5 and a 14-core Pro.
LOAD_BUSY = float(os.environ.get("FLEET_DISPATCH_LOAD_BUSY", "0.60"))
LOAD_SATURATED = float(os.environ.get("FLEET_DISPATCH_LOAD_SATURATED", "1.00"))
# A full backend suite has been measured taking the machine to ~124MB free
# (see prepush_suite_lock.sh's header). Below this, adding a lane is how a
# push gets SIGTERM-killed mid-suite — silent work loss.
MIN_AVAIL_MB = int(os.environ.get("FLEET_DISPATCH_MIN_AVAIL_MB", "2048"))

VERDICT_READY = "READY"
VERDICT_BUSY = "BUSY"
VERDICT_SATURATED = "SATURATED"
VERDICT_DARK = "DARK"

PLACEABLE = (VERDICT_READY, VERDICT_BUSY)

# The lockfile .husky/pre-push hands to prepush_suite_lock.sh. Held == a full
# backend suite is running on that machine right now.
SUITE_LOCKFILE = "/tmp/nuzantara-prepush-backend-suite.lock"

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
    WORKTREES=$(git -C "$REPO" worktree list 2>/dev/null | wc -l | tr -d ' ')
    WORKTREES=$(( WORKTREES - 1 ))
    DIRTY=$(git -C "$REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    BEHIND=$(git -C "$REPO" rev-list --count HEAD..origin/main 2>/dev/null || echo -1)
fi

printf 'FLEET_CAP host=%s cores=%s load1=%s avail_mb=%s lock=%s lock_pid=%s head=%s worktrees=%s dirty=%s behind=%s\n' \
    "$(hostname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')" \
    "$CORES" "$LOAD1" "$AVAIL_MB" "$LOCK_STATE" "$LOCK_PID" \
    "$HEAD" "$WORKTREES" "$DIRTY" "$BEHIND"
"""

# Emits one line per (worktree, file). A lane with no files at all is EMPTY
# (freshly created, nothing written yet) and a lane whose git output contains a
# quote is OPAQUE — git quotes paths with spaces/specials, and word-splitting
# such a path would silently drop the real name while inventing fragments of
# it. Both are unknowable scopes, and both fail closed at the caller.
LANES_SH = r"""
set -u
export LC_ALL=C
REPO="$HOME/nuzantara"
git -C "$REPO" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}' |
while IFS= read -r WT; do
    [ "$WT" = "$REPO" ] && continue
    NAME=$(basename "$WT")
    BR=$(git -C "$WT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)
    MB=$(git -C "$WT" merge-base origin/main HEAD 2>/dev/null || echo "")
    COMMITTED=""
    [ -n "$MB" ] && COMMITTED=$(git -C "$WT" diff --name-only "$MB" HEAD 2>/dev/null || echo "")
    WIP=$(git -C "$WT" status --porcelain 2>/dev/null | awk '{print $NF}' || echo "")
    ALL="$COMMITTED
$WIP"
    case "$ALL" in
        *'"'*) printf 'FLEET_LANE_OPAQUE %s %s\n' "$NAME" "$BR"; continue ;;
    esac
    N=0
    for F in $ALL; do
        printf 'FLEET_LANE %s %s %s\n' "$NAME" "$BR" "$F"
        N=$(( N + 1 ))
    done
    [ "$N" -eq 0 ] && printf 'FLEET_LANE_EMPTY %s %s\n' "$NAME" "$BR"
done
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
        "git -C \"$REPO\" fetch --quiet origin main 2>/dev/null || true" if fetch else "",
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

    Not to READY: an unreadable load or memory reading is a reason to withhold
    work from a machine, never a reason to send it there (fail-closed).
    """
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


def parse_lane_lines(lines: list[str], node_name: str) -> list[dict]:
    """Turn FLEET_LANE* output into lane records with their file sets."""
    lanes: dict[str, dict] = {}

    def lane(name: str, branch: str) -> dict:
        return lanes.setdefault(
            name,
            {"node": node_name, "worktree": name, "branch": branch,
             "files": set(), "scope": "known"},
        )

    for raw in lines:
        parts = raw.split()
        if raw.startswith("FLEET_LANE ") and len(parts) >= 4:
            lane(parts[1], parts[2])["files"].add(parts[3])
        elif raw.startswith("FLEET_LANE_EMPTY ") and len(parts) >= 3:
            lane(parts[1], parts[2])["scope"] = "empty"
        elif raw.startswith("FLEET_LANE_OPAQUE ") and len(parts) >= 3:
            lane(parts[1], parts[2])["scope"] = "opaque"
    return list(lanes.values())


def probe_lanes(node: dict, hostname: str, run: Runner = _run) -> tuple[list[dict], bool]:
    """Return (lanes, answered). `answered` False means the node told us nothing."""
    try:
        proc = run(build_command(node, LANES_SH, hostname), PROBE_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return [], False
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLEET_LANE")]
    # A node with no worktrees legitimately prints nothing, so "no lines" is
    # only trustworthy when the probe itself succeeded.
    if not lines and proc.returncode != 0:
        return [], False
    return parse_lane_lines(lines, node["name"]), True


def find_collisions(files: set[str], lanes: list[dict]) -> list[dict]:
    """Every live lane that blocks placing a lane touching `files`.

    Two blocking shapes, and the second is the one that gets skipped:
      - overlap: the lane provably edits one of these files (federation_parallelize
        §4 cond. 2 — coders on the same artifact degrade ~70%).
      - unknowable: the lane's scope is empty or opaque, so NON-overlap cannot be
        proven. Ambiguity resolves to serial, exactly as that module's default does.
    """
    blocking = []
    for lane in lanes:
        shared = files & lane["files"]
        if shared:
            blocking.append({**lane, "why": "overlap", "shared": sorted(shared)})
        elif lane["scope"] in ("empty", "opaque"):
            blocking.append({**lane, "why": f"scope-{lane['scope']}", "shared": []})
    return blocking


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
            indent=2, sort_keys=True,
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


def cmd_place(
    lane: str,
    task_id: str,
    files: list[str],
    prefer: str | None,
    dry_run: bool,
    allow_unknown_scope: bool,
    run: Runner = _run,
) -> int:
    nodes, caps, hostname = _probe_all(False, run)
    answered = [c for c in caps if c["verdict"] != VERDICT_DARK]
    if not answered:
        print("fleet_dispatch: BLIND — not a single node answered (W84)", file=sys.stderr)
        return 4
    if len(answered) < len(caps):
        dark = ", ".join(c["name"] for c in caps if c["verdict"] == VERDICT_DARK)
        print(f"⚠️  placing across {len(answered)}/{len(caps)} nodes — DARK: {dark}. "
              f"A lane on an unreachable node cannot be checked for collisions.")

    # Collision check FIRST: a placement that must be refused should never
    # create a worktree, on any machine.
    if files:
        wanted = set(files)
        all_lanes: list[dict] = []
        for node in nodes:
            cap = next(c for c in caps if c["name"] == node["name"])
            if cap["verdict"] == VERDICT_DARK:
                continue
            lanes, ok = probe_lanes(node, hostname, run)
            if not ok:
                print(f"⚠️  {node['name']}: lane scan failed — its lanes cannot "
                      f"be checked for collisions", file=sys.stderr)
                continue
            all_lanes.extend(lanes)

        blocking = find_collisions(wanted, all_lanes)
        hard = [b for b in blocking if b["why"] == "overlap"]
        soft = [b for b in blocking if b["why"] != "overlap"]

        for block in hard:
            print(f"❌ REFUSED — {block['node']}:{block['worktree']} "
                  f"({block['branch']}) already edits: {', '.join(block['shared'])}",
                  file=sys.stderr)
        if hard:
            print("   Two coders on the same artifact measure ~70% WORSE than "
                  "one (federation_parallelize.py §4 cond. 2). Wait for that "
                  "lane, or split the work by file.", file=sys.stderr)
            return 1

        if soft and not allow_unknown_scope:
            for block in soft:
                print(f"❌ REFUSED — {block['node']}:{block['worktree']} "
                      f"({block['branch']}) has an unknowable scope "
                      f"({block['why']}): non-overlap cannot be proven.",
                      file=sys.stderr)
            print("   Ambiguity resolves to serial. Re-run with "
                  "--allow-unknown-scope once you have confirmed by hand that "
                  "those lanes do not touch your files.", file=sys.stderr)
            return 1
        for block in soft:
            print(f"⚠️  {block['node']}:{block['worktree']} scope {block['why']} "
                  f"— overridden by --allow-unknown-scope")
    else:
        print("⚠️  no --files given: collision checking is SKIPPED. This is the "
              "one thing that makes parallel lanes safe — pass the files you "
              "intend to touch.")

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
    print(f"✅ WORKTREE_READY {winner['name']}:{path}")
    if is_local(node, hostname):
        print(f"   enter: cd {shlex.quote(path)} && claude")
    else:
        print(f"   enter: ssh -t {node['ssh_alias']} "
              f"'cd {shlex.quote(path)} && claude'")
    return 0


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
    place.add_argument("--files", nargs="*", default=[],
                       help="repo-relative files this lane will touch — the "
                            "collision check runs on these")
    place.add_argument("--prefer", help="force a node by roster name (m5|pro|mini)")
    place.add_argument("--dry-run", action="store_true", help="decide, create nothing")
    place.add_argument("--allow-unknown-scope", action="store_true",
                       help="place even when a live lane's file scope cannot be "
                            "determined (default: refuse)")
    return parser


def main(argv: list[str] | None = None) -> int:
    if os.environ.get("FLEET_DISPATCH_ENABLED", "true").lower() == "false":
        print("fleet_dispatch: disabled by kill switch")
        return 0
    args = _build_parser().parse_args(argv)
    if args.command == "capacity":
        return cmd_capacity(args.json, args.fetch)
    if args.command == "place":
        return cmd_place(
            args.lane, args.task_id, args.files, args.prefer,
            args.dry_run, args.allow_unknown_scope,
        )
    _build_parser().print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
