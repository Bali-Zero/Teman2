#!/usr/bin/env python3
"""proprioception.py — the boundary-reconciliation organ (the reconciler of reconcilers).

THE DISEASE IT KILLS (TAC 2026-07-02, meta-pattern "unreconciled boundaries"): a signal
emitted on ONE side of a boundary (repo<->$HOME, machine<->fleet, wrapper<->payload,
produced<->promoted, code<->docs) is trusted as truth for BOTH sides, and nothing probes
across. The organism owns several per-boundary reconcilers — this organ runs them all,
adds probes for the uncovered boundaries, and emits ONE normalized report consumed by ONE
SessionStart receptor. A stale guardian is itself a finding (guardian-of-guardians).

SIGNALER, NEVER ACTUATOR (W33/W81): no restart, no pull, no unload, no fix. Content
comparison over proxies (W88): blob/sha, never timestamps or exit codes, wherever both
sides are readable. Machine-aware (balizero on M5, nuzantara on Pro/Mini). No secret
values ever appear in config, report, or evidence — paths, counts and ages only.

Anti-calm-liar contracts (Codex red-team 2026-07-02, panel run 1):
- the report stamps runner_version, config source+sha, repo HEAD, expected vs actual
  probe counts — a report that can't prove its own provenance is not a clean report;
- wrapped-tool output that doesn't match its declared schema is UNPROBEABLE, never
  RECONCILED (schema drift must not normalize into calm);
- boundary classes with no probe on this machine are listed as UNWATCHED in every report
  (visible debt, not silent absence);
- exit 2 on infrastructure failure (no probes ran / report unwritable / registry invalid) —
  exit 0 means "the organ itself worked", not "all is well";
- v1 has NO cron: with no session there is no alarm. This is ACCEPTED and recorded
  (PENDING-ARMS); the receptor is the consumption point.

Usage:
    python3 scripts/proprioception.py                 # run all probes for this machine, write report
    python3 scripts/proprioception.py --json          # also print full JSON to stdout
    python3 scripts/proprioception.py --fleet         # + stream self to the other machines over ssh
    python3 scripts/proprioception.py --tags fast     # subset by tag
    python3 scripts/proprioception.py --strict        # exit 1 if any P1 DIVERGED (cron/CI)
    python3 scripts/proprioception.py --selftest      # registry + parser-guard self-checks
    cat scripts/proprioception.py | ssh pro 'python3 - --json --no-report'   # bootstrap-safe remote

Report: ~/.nuzantara-proprioception/last.json + last.md (atomic rename). The summary line
is ALWAYS present — an empty report is impossible by construction.
Kill switch: PROPRIOCEPTION_DISABLED=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

RUNNER_VERSION = "1.0.0"
SCHEMA_VERSION = 1
RECONCILED, DIVERGED, UNPROBEABLE = "RECONCILED", "DIVERGED", "UNPROBEABLE"
REPORT_DIR = Path.home() / ".nuzantara-proprioception"

# The boundary taxonomy. A class with no probe scoped to this machine appears as
# UNWATCHED in the report tail — absence must be visible, never silent (red-team #2).
KNOWN_BOUNDARY_CLASSES = [
    "checkout<->origin",        # git lag, ledger freshness
    "home<->repo",              # HOME-fork drift (#1)
    "wrapper<->payload",        # exit code vs log content (W84/#2)
    "produced<->promoted",      # artifacts stranded on the producing side
    "guardian<->cadence",       # stale guardians (guardian-of-guardians)
    "executed<->committed",     # the code a probe RUNS vs origin/main's (2026-08-08)
    "canon<->installed",        # repo launchagent canon vs ~/Library vs launchctl (#1926)
    "organ<->heartbeat",        # declared organs vs sidecar liveness
    "code<->docs",              # W86
    "defined<->live",           # e.g. Qdrant collections — NO PROBE in v1 (A6)
    "process<->process",        # e.g. /health/detailed provenance — NO PROBE in v1 (A2)
    "seat<->armed",             # AI-seat credential/quota vs live probe (arsenal, #2)
    "worktree<->gate",          # does git actually invoke a pre-push hook in this worktree (#2)
    "tunnel<->reachable",       # declared network tunnel/forward vs live reachability (2026-08-21)
]

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
            "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=10",
            "-o", "ServerAliveCountMax=2"]


# ---------------------------------------------------------------- environment

def repo_root() -> Path | None:
    env = os.environ.get("NUZ_REPO_ROOT")
    if env and (Path(env) / ".git").exists():
        return Path(env)
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except Exception:
        pass
    fallback = Path.home() / "Desktop" / "nuzantara"
    return fallback if (fallback / ".git").exists() else None


def machine_label() -> str:
    host = socket.gethostname().split(".")[0].lower()
    if "air-m5" in host:
        return "m5"
    if "mini" in host:
        return "mini"
    if host == "nuzantara":
        return "pro"
    return host


def sh(cmd: list[str], timeout: int, cwd: Path | None = None,
       stdin_text: str | None = None) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       cwd=str(cwd) if cwd else None, input=stdin_text)
    return p.returncode, p.stdout, p.stderr


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def git_head(root: Path) -> str:
    try:
        rc, out, _ = sh(["git", "rev-parse", "--short", "HEAD"], timeout=10, cwd=root)
        return out.strip() if rc == 0 else "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- verdict

# Evidence lines may quote wrapped-tool output (log markers, json items). A log line can
# carry a credential — redact token-shaped substrings before anything reaches the report
# (spalla finding #5: the organ must never become the leak).
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|ghp_[A-Za-z0-9]{8,}|xox[a-z]-[A-Za-z0-9\-]{8,}"
    r"|Bearer\s+[A-Za-z0-9._\-]{12,}|[A-Fa-f0-9]{40,}|eyJ[A-Za-z0-9._\-]{20,})")


def redact(line: str) -> str:
    return _SECRET_RE.sub("<REDACTED>", line)


def verdict(pid: str, boundary: str, bclass: str, status: str, severity: str, n: int,
            evidence: list[str], fix_hint: str, t0: float) -> dict:
    return {
        "id": pid,
        "boundary": boundary,
        "class": bclass,
        "status": status,
        "severity": severity,
        "n_findings": n,
        "evidence": [redact(e)[:200] for e in evidence[:5]],
        "fix_hint": fix_hint,
        "duration_ms": int((time.monotonic() - t0) * 1000),
    }


def finding_label(probe: dict) -> str:
    """`id` plus a "1 of N" marker when the probe carries more findings than the
    one line about to be printed shows.

    Every surface that renders a DIVERGED probe prints ONE finding: the receptor
    line, the CLI line, and the per-host fleet summary. `evidence` holds at most
    5 items (run_wrap's `items[:5]`) and `n_findings` is the true total, which is
    routinely far larger. Printing `evidence[0]` with nothing naming the total is
    W97 — a truncated list read downstream as complete.

    MEASURED 2026-08-26 on Pro: launchagent_canon 55 findings, launchd_liveness
    22, organs_heartbeat 7, worktree_gate_shim 4 — each rendered as a single
    line. The last one caused real damage: read as "one worktree pushes with no
    gate", three others kept pushing with no hooks at all until a hand census
    found them.

    Silent for n <= 1: a "[1 of 1]" on every single-finding line would be noise
    on a report injected into every session on three machines.
    """
    n = probe.get("n_findings")
    if probe.get("evidence") and isinstance(n, int) and n > 1:
        return f"{probe.get('id')} [1 of {n}]"
    return str(probe.get("id"))


# ------------------------------------------------------- machine-aware remedy selection

# A registry entry's fix_hint is a STATIC string chosen at authoring time — it cannot
# know which machine or which finding-shape it will be printed for. Two entries in
# DEFAULT_REGISTRY carry a standing decision that a generic remedy actively violates on
# one machine, the same disease probe_guardian_freshness already cured for freshness
# ITSELF (per-item `machines` scoping, W106b/#2): before printing a remedy, ask whether
# a standing decision already forbids it. These two small pure functions are that ask —
# called once per matching entry in main()'s probe loop, never touching the registry's
# static fix_hint for anything else.

_BEHIND_RE = re.compile(r"main checkout: (-?\d+) behind origin/main")
_SELF_STALE_RE = re.compile(r"^SELF STALE: ")


CURRENT, STALE, AHEAD, EDITED, UNVERIFIABLE = "current", "stale", "ahead", "edited", "unverifiable"


def _version_vs_main(root: Path, rel: str, actual_sha: str) -> tuple[str, str]:
    """Attribute ONE tracked path: is the version actually in play behind origin/main?

    Returns (state, detail). For CURRENT and STALE, detail is origin/main's blob sha;
    otherwise it is the sentence explaining why no direction could be assigned. One
    engine, two callers — `_self_code_staleness` (whose `actual_sha` is the bytes this
    process loaded) and `probe_executed_code_currency` (whose `actual_sha` is the file on
    disk, because that is what the wrap will execute). A second hand-written copy is how
    twins drift apart while both look cured (W106b, fourth layer).

    DIFFERING IS NOT BEHIND — the whole lesson of W106b is that a comparison knows THAT
    two copies differ and never WHICH is stale. STALE is returned only on positive
    evidence, and the evidence is about THIS PATH, not about the branch: the bytes are
    what HEAD holds, AND they are also what the merge-base held, so main is the only side
    that moved. Everything git could not decide is UNVERIFIABLE, never a quiet pass.

    Cost: one `rev-parse` when the path is current (the overwhelmingly common case), five
    when it differs. Nothing here is cached across paths on purpose — a cache keyed by
    root would answer for the HEAD it was filled at, which is the disease.
    """
    rc2, main_blob, _ = sh(["git", "rev-parse", f"origin/main:{rel}"], timeout=10, cwd=root)
    if rc2 != 0 or not main_blob.strip():
        return UNVERIFIABLE, (f"cannot compare {rel} against origin/main "
                              f"(offline, or this path is new on this branch)")
    if actual_sha == main_blob.strip():
        return CURRENT, main_blob.strip()
    rc3, head_blob, _ = sh(["git", "rev-parse", f"HEAD:{rel}"], timeout=10, cwd=root)
    if rc3 != 0:
        return UNVERIFIABLE, (f"{rel} is not readable at this HEAD (new, "
                              f"untracked, or unborn HEAD) — direction cannot be attributed")
    if head_blob.strip() != actual_sha:
        return EDITED, (f"{rel} differs from origin/main because it has "
                        f"UNCOMMITTED edits — it is being worked on, not left behind")
    # Direction is a question about THIS PATH, and the obvious proxy for it — "is my
    # branch an ancestor of origin/main" — answers a DIFFERENT one. A single local commit
    # touching an unrelated file makes `merge-base --is-ancestor HEAD origin/main` say
    # "no", and the old code read that as "ahead, not stale" and went silent, while the
    # file actually in play was exactly the version main had replaced. That is a
    # false-clean produced by the very confusion this probe exists to catch (W88: the
    # proxy lies; #3: judge the entity, not the form). So ask git about the file:
    # at the merge-base, was this path the bytes we are running?
    rcs, shallow, _ = sh(["git", "rev-parse", "--is-shallow-repository"], timeout=10, cwd=root)
    if rcs != 0:
        # Not knowing whether the history is truncated is not the same as knowing it is
        # whole. Reporting a determination we did not make is the calm liar (W84).
        return UNVERIFIABLE, (f"{rel} differs from origin/main and git could not say "
                              f"whether this clone is shallow (exit {rcs}) — direction unknown")
    if shallow.strip() == "true":
        return UNVERIFIABLE, (f"{rel} differs from origin/main and this "
                              f"clone is SHALLOW, so history cannot be decided — direction unknown")
    rcb, base, _ = sh(["git", "merge-base", "HEAD", "origin/main"], timeout=10, cwd=root)
    if rcb != 0 or not base.strip():
        return UNVERIFIABLE, (f"{rel} differs from origin/main but they share no "
                              f"reachable merge-base (exit {rcb}) — direction unknown, not a verdict")
    rc5, base_blob, _ = sh(["git", "rev-parse", f"{base.strip()}:{rel}"], timeout=10, cwd=root)
    if rc5 != 0:
        return UNVERIFIABLE, (f"{rel} differs from origin/main and did not exist at their "
                              f"merge-base — both sides added it, so neither is behind the other")
    if base_blob.strip() != actual_sha:
        return AHEAD, (f"{rel} differs from origin/main because THIS side changed it "
                       f"since the merge-base — it is our own newer code, not old code")
    return STALE, main_blob.strip()


def _blob_sha(data: bytes) -> str:
    """`git hash-object` in pure Python — sha1 of `blob <len>\\0` + content."""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def _read_runner_source() -> tuple[str, str]:
    """Hash the bytes of THIS file at import, returning (sha, reason-if-none).

    Deliberately at import rather than inside the probe. An adversarial review of the
    first draft caught the window: hashing the PATH later answers "what is on disk now",
    while the claim being made is "what wrote this report". A file replaced between
    interpreter start and probe time makes that a lie in both directions — a genuinely
    stale runner reported clean, or a current one accused. Reading at import narrows the
    window to the microseconds between the interpreter reading the file and this line,
    which is as close as Python gets: the compiled bytes are not recoverable afterwards.
    """
    try:
        if "__file__" not in globals():
            return "", "stdin"                      # `... | python3 -`, nothing on disk
        p = Path(__file__)
        return _blob_sha(p.read_bytes()), ""
    except OSError:
        return "", "unreadable"


_RUNNER_SHA, _RUNNER_NO_SHA_REASON = _read_runner_source()
_LEDGER_STALE_RE = re.compile(r"^LEDGER STALE: (\S+) differs from origin/main")


def _git_alignment_remedy(entry: dict, machine: str, ev: list[str]) -> str:
    """m5's main checkout is BY DESIGN left behind origin/main — Rule 0 of this
    organ's own SessionStart contract (scripts/hooks/proprioception_sessionstart.sh)
    and the probe_home_fork_scripts docstring above (W106b, 2026-07-27): pulling it
    races live worktrees. The registry's static "interactive pull" fix_hint is correct
    on pro/mini, where the checkout IS auto-pulled and 0-behind is the norm — return it
    UNCHANGED there. On m5, override it only when the behind-count is actually part of
    this finding (a fully RECONCILED probe, or one driven by ledger-drift alone at
    behind=0, has nothing to caveat about pulling — the by-design text must not appear
    spuriously): state the by-design truth instead of prescribing the destructive act,
    and name the ledger as the one actionable half when it is stale too.
    """
    default = entry["fix_hint"]
    if machine != "m5":
        return default
    behind = -1
    for e in ev:
        m = _BEHIND_RE.search(e)
        if m:
            behind = int(m.group(1))
            break
    if behind <= 0:
        return default
    by_design = ("m5's main checkout is deliberately left behind origin/main by design "
                 "(pulling it races live worktrees — see probe_home_fork_scripts docstring, "
                 "W106b): do NOT pull it, interactively or from an agent session.")
    ledger = None
    for e in ev:
        m = _LEDGER_STALE_RE.search(e)
        if m:
            ledger = m.group(1)
            break
    if ledger:
        # Was: "refresh just that file from origin/main (e.g. `git checkout
        # origin/main -- <ledger>` in the main checkout)". Correct in intent and
        # UNEXECUTABLE in fact — worktree_isolation.py refuses mutating git in the
        # main checkout for every agent session, and the only documented way past
        # it disarms the guard wholesale. With no operator lane, that prescribed a
        # lane that does not exist, which is how a reader learns to skip this
        # probe. #3824 gave the reader a read-only way to the same truth, so the
        # remedy now names it: the fix is a READ, not a repair.
        return (f"{by_design} The actionable half is the ledger, and it is a READ rather than "
                f"a repair: `python3 scripts/pending_arms_report.py --ref origin/main` reports "
                f"against main's copy of {ledger} with no pull and no write, which is the only "
                f"form a session can carry out here. Do not repair the checkout copy — read "
                f"main's.")
    return f"{by_design} No other actionable half in this finding right now."


def _arsenal_seats_vcr_m5_remedy(entry: dict) -> str:
    """arsenal_seats_vcr_m5 is registered machines: ["m5"] only — every call to this
    function IS on m5 by construction. docs/runbooks/arsenal-probe.md names Mini as
    the primary for arsenal-seat freshness (the healer refreshes there every <=20h);
    the sibling `arsenal_seats` entry (mini/pro) is what that cadence actually feeds.
    FRESHNESS_EXPIRED here, between m5's own interactive runs, is the expected state of
    a non-primary pilot subset — not a live-seat outage — so say that BEFORE the check
    command, or the finding reads as arsenal trouble it usually isn't.
    """
    return ("Mini is the documented primary for arsenal-seat freshness "
            '(docs/runbooks/arsenal-probe.md "Mini (primary)"); FRESHNESS_EXPIRED on m5 '
            "between interactive runs is expected, not a seat outage. " + entry["fix_hint"])


def _guardian_freshness_remedy(entry: dict, ev: list[str]) -> str:
    """guardian_freshness now reports two different diseases and they have OPPOSITE cures.

    The registry's static hint answers a stale OUTPUT: "run it by hand, read ITS log,
    then fix its scheduler". A stale RUNNER is the reverse — the scheduler is fine, it
    ran on time, and what it wrote is old because the CODE is old. Printing the
    scheduler advice under a SELF STALE line would be the handoff-§6 defect verbatim: a
    remedy that does not match the finding it sits under, which trains the reader to
    skip the fix line — and then to skip the one that mattered.
    """
    if ev and _SELF_STALE_RE.match(ev[0]):
        return ("the guardian's SCHEDULE is not the problem, its CODE is: it ran on time "
                "and wrote old text. Do NOT repair the checkout to fix this (W106b) — run "
                "main's copy out of tree exactly as the evidence line spells out, and read "
                "the report THAT writes.")
    return entry["fix_hint"]


# ---------------------------------------------------------------- builtins

def probe_git_alignment(root: Path, args: dict, timeout: int) -> tuple[str, int, list[str]]:
    # DECLARED EXCEPTION to signaler-only: `git fetch` refreshes remote-tracking refs
    # (refs/remotes + FETCH_HEAD) — it changes what this checkout KNOWS, never what it
    # RUNS (no working-tree/branch mutation). Without it the behind-count lies stale,
    # which is the very disease this organ hunts. Escape hatch: --no-fetch.
    ev: list[str] = []
    if not args.get("no_fetch"):
        try:
            rc, _, err = sh(["git", "fetch", "--quiet", "origin"], timeout=min(timeout, 25), cwd=root)
            if rc != 0:
                ev.append(f"fetch failed (offline is a natural state — using last-known origin): {err.strip()[:80]}")
        except subprocess.TimeoutExpired:
            ev.append("fetch timed out — using last-known origin")
    findings = 0
    rc, out, _ = sh(["git", "rev-list", "--count", "HEAD..origin/main"], timeout=15, cwd=root)
    behind = int(out.strip()) if rc == 0 and out.strip().isdigit() else -1
    rc, out, _ = sh(["git", "status", "--porcelain"], timeout=15, cwd=root)
    dirty = len([l for l in out.splitlines() if l.strip()]) if rc == 0 else -1
    ev.append(f"main checkout: {behind} behind origin/main, {dirty} dirty entries")
    if behind > int(args.get("behind_warn", 10)):
        findings += 1
    # ledger freshness — the "TRIAGE read a stale ledger" killer (content, not timestamp)
    ledger = args.get("ledger_path", ".claude/skills/modus/PENDING-ARMS.md")
    lf = root / ledger
    if lf.exists():
        rc1, local_blob, _ = sh(["git", "hash-object", str(lf)], timeout=10, cwd=root)
        rc2, origin_blob, _ = sh(["git", "rev-parse", f"origin/main:{ledger}"], timeout=10, cwd=root)
        if rc1 == 0 and rc2 == 0 and local_blob.strip() != origin_blob.strip():
            findings += 1
            ev.append(f"LEDGER STALE: {ledger} differs from origin/main — TRIAGE would read old state")
    status = DIVERGED if findings else RECONCILED
    if behind < 0:
        status = UNPROBEABLE
    return status, findings, ev


def probe_produced_promoted(root: Path, args: dict, timeout: int) -> tuple[str, int, list[str]]:
    ev, findings = [], 0
    for pair in args.get("pairs", []):
        glob, label = pair["glob"], pair.get("label", pair["glob"])
        # uncommitted (untracked + modified + gitignored artifacts — red-team #10)
        rc, out, _ = sh(["git", "status", "--porcelain", "--ignored=matching", "--", glob],
                        timeout=15, cwd=root)
        if rc != 0:
            ev.append(f"{label}: status failed")
            continue
        stranded = [l for l in out.splitlines() if l.strip()]
        # committed locally but never pushed (still invisible to the fleet)
        rc, out, _ = sh(["git", "log", "--oneline", "origin/main..HEAD", "--", glob],
                        timeout=15, cwd=root)
        unpushed = len([l for l in out.splitlines() if l.strip()]) if rc == 0 else 0
        if stranded or unpushed:
            findings += len(stranded) + unpushed
            parts = []
            if stranded:
                parts.append(f"{len(stranded)} not committed (newest: {stranded[-1][3:][:50]})")
            if unpushed:
                parts.append(f"{unpushed} committed-not-pushed")
            ev.append(f"{label}: " + ", ".join(parts))
    return (DIVERGED if findings else RECONCILED), findings, ev


def load_declared_fork_pairs(root: Path, machine: str) -> list[dict]:
    """Merge in infra/home-fork/declared-pairs.json pairs applicable to this machine.

    lint_home_fork.py already imports THIS probe's embedded pairs and merges them
    with declared-pairs.json for its own check — but the merge never ran in the
    other direction, so pairs added only to declared-pairs.json (e.g. the
    Mini-only kg-query-api-wrapper.sh/mlx-server-run.sh entries) were invisible
    to this probe, which kept reporting UNPROBEABLE on machines that do have
    live home-fork pairs to check. Best-effort: a missing/malformed config
    degrades to empty, never raises — the embedded pairs remain the fallback.
    """
    cfg_path = root / "infra" / "home-fork" / "declared-pairs.json"
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for pair in data.get("pairs", []):
        machines = pair.get("machines", ["all"])
        if ("all" in machines or machine in machines) and "live" in pair and "repo" in pair:
            entry = {"live": pair["live"], "repo": pair["repo"]}
            if pair.get("live_may_extend_repo"):
                entry["live_may_extend_repo"] = True
            out.append(entry)
    return out


def origin_main_sha(root: Path, rel: str) -> str | None:
    """sha256 of `origin/main:<rel>` — the fleet's copy, not this checkout's.

    Twin of lint_home_fork.origin_main_sha (kept local: lint_home_fork already
    imports THIS module's pairs, so importing back would close a cycle). If you
    change the attribution rule, change BOTH — they are pinned by tests that
    name each other.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show", f"origin/main:{rel}"],
            capture_output=True, timeout=15,
        )
        if proc.returncode != 0:
            return None
        out = proc.stdout
        blob = out.encode("utf-8", "replace") if isinstance(out, str) else bytes(out)
        return hashlib.sha256(blob).hexdigest()
    except (OSError, subprocess.TimeoutExpired, TypeError, ValueError, AttributeError):
        # A probe that raises takes the whole proprioception run with it.
        return None


def _live_extends_repo_verbatim(live: Path, repo: Path) -> bool:
    """True iff repo's bytes appear whole in live, split into one prefix and
    one suffix, with exactly one contiguous span of NEW content inserted
    between them (also covers the degenerate append-only/prepend-only cases,
    where the other span is empty).

    A pure `live.startswith(repo)` prefix check is too narrow: the real first
    case (2026-08-28, a live-only Ghostty colour override on Mini, marked in
    the dotfile itself as "live dotfile only") turned out to be a MID-FILE
    insertion — the fleet installer places new upstream sections before an
    existing trailing comment block, so a host-local addition lands in the
    middle, not appended at the end. A file that merely happens to be longer
    is not proof of anything; the proof is the longest-common-prefix plus the
    longest-common-suffix, measured independently from each end, together
    accounting for the ENTIRE repo file byte-for-byte. Any genuine drift —
    a changed value, a removed line, a reordering — breaks the prefix match
    or the suffix match (or both) at the point of the change, so
    prefix_len + suffix_len falls short of len(repo) and this correctly
    returns False, reporting DIVERGED normally. This is the structural test
    for the declared-pairs.json `live_may_extend_repo` flag, distinct from
    CHECKOUT-STALE (live matches origin/main, the checkout is behind): here
    repo agrees with what it should say and live legitimately carries MORE,
    never less, changed, or reordered.
    """
    try:
        repo_bytes = repo.read_bytes()
        if not repo_bytes:
            return False  # an empty repo file prefix/suffix-matches anything — refuse to trust it
        live_bytes = live.read_bytes()
    except OSError:
        return False
    if len(live_bytes) <= len(repo_bytes):
        return False
    cap = len(repo_bytes)  # never let prefix+suffix search past repo's own length
    prefix_len = 0
    while prefix_len < cap and live_bytes[prefix_len] == repo_bytes[prefix_len]:
        prefix_len += 1
    suffix_len = 0
    max_suffix = cap - prefix_len  # the two spans must not overlap within repo
    while suffix_len < max_suffix and live_bytes[-1 - suffix_len] == repo_bytes[-1 - suffix_len]:
        suffix_len += 1
    return prefix_len + suffix_len == cap


def probe_home_fork_scripts(root: Path, args: dict, timeout: int) -> tuple[str, int, list[str]]:
    """Live-vs-checkout sha256 over declared pairs — with the side ATTRIBUTED.

    A bare live≠checkout comparison cannot say which side is stale, yet the
    remedy it printed ("realign live from repo") only makes sense when the
    checkout is the current one. On 2026-07-27 this probe reported P1 DIVERGED
    on M5 for two files whose LIVE copies matched origin/main exactly — the M5
    checkout was 144 commits behind, and it is deliberately left behind
    (pulling it races ~45 live worktrees). Acting on that P1 would have
    overwritten a current worktree-isolation hook with a two-day-old one.
    So: only the LIVE copy being stale is a finding.
    """
    ev, findings, probeable = [], 0, 0
    seen: set[tuple[str, str]] = set()
    pairs = list(args.get("pairs", [])) + load_declared_fork_pairs(root, machine_label())
    for pair in pairs:
        key = (pair["live"], pair["repo"])
        if key in seen:
            continue
        seen.add(key)
        live = Path(os.path.expanduser(pair["live"]))
        repo = root / pair["repo"]
        if not live.exists():
            continue  # this machine doesn't run that copy — not a finding
        probeable += 1
        if not repo.exists():
            # Absence is a proxy too — the twin `lint_home_fork.check_pairs`
            # carries the identical branch and both were cured together on
            # 2026-08-08. Curing only one is the W106b fourth layer verbatim:
            # calling two tools "twins with the same logic" and fixing one.
            # A file merged to origin/main but not yet pulled into THIS
            # checkout is a trailing checkout, not a live copy without a
            # source of truth.
            upstream = origin_main_sha(root, pair["repo"])
            if upstream is not None and sha256_file(live) == upstream:
                ev.append(
                    f"CHECKOUT-STALE: {pair['repo']} is absent from this checkout "
                    f"but present on origin/main, and the LIVE copy {live} already "
                    f"matches it. Update the checkout; do NOT realign live from it."
                )
                continue
            findings += 1
            if upstream is None:
                ev.append(
                    f"NO REPO COUNTERPART: {live} executes live with no source of truth in repo"
                )
            else:
                ev.append(
                    f"DIVERGED: {live} != origin/main:{pair['repo']} (absent from this "
                    f"checkout) — the LIVE copy is stale; realign it from origin/main"
                )
            continue
        live_sha, repo_sha = sha256_file(live), sha256_file(repo)
        if live_sha == repo_sha:
            continue
        if pair.get("live_may_extend_repo") and _live_extends_repo_verbatim(live, repo):
            continue  # declared + verified: repo is a verbatim prefix, the rest is a local addition
        upstream = origin_main_sha(root, pair["repo"])
        if upstream is not None and live_sha == upstream:
            ev.append(
                f"CHECKOUT-STALE: {pair['repo']} — the LIVE copy {live} already "
                f"matches origin/main. Update the checkout; do NOT realign live from it."
            )
            continue
        findings += 1
        if upstream is None:
            why = "no origin/main to compare — direction unattributable"
        elif repo_sha == upstream:
            why = "the checkout matches origin/main, so the LIVE copy is stale"
        else:
            why = "BOTH sides differ from origin/main — read both before porting"
        ev.append(f"DIVERGED: {live} != {pair['repo']} — a fix is stranded on one side ({why})")
    if probeable == 0:
        return UNPROBEABLE, 0, ["no configured live copies exist on this machine"]
    return (DIVERGED if findings else RECONCILED), findings, ev


def _self_code_staleness(root: Path | None) -> tuple[int, list[str]]:
    """Is the code WRITING this report the code origin/main says it should be?

    The loop below answers "did each guardian speak RECENTLY". Nothing answered "is
    what it said CURRENT" — and on 2026-08-08 the difference bit: the live report was
    6.7h old, comfortably inside the 48h gate, so this probe stayed silent, and it
    prescribed `interactive pull on this machine's main` — an action #3723 and #3826
    had already replaced with an explicit "do NOT pull it". It had been written by the
    main checkout, 219 commits behind. mtime is a proxy for "current" and it lies when
    the writer is old (W88); on m5 it lies BY DESIGN, because that checkout is
    deliberately never pulled (W106b) — so the one machine where a cure takes longest
    to reach the executed copy is also the one where nothing was watching.

    Same two commands probe_git_alignment already runs against the ledger — hash-object
    the working copy, rev-parse main's — pointed at __file__ instead. It reads the
    origin/main ref that probe_git_alignment refreshed earlier in this same run
    (registry order: git_alignment precedes guardian_freshness); under --no-fetch it
    compares against the last-known ref, exactly like every other probe here.

    Cannot-verify is EVIDENCE, never a finding. This is a signaler a human reads and
    offline is a natural state (Law 6); the lint twin is the one that owes an exit code
    for the same fact (W106b, "where the twins must diverge").

    DECLARED LIMIT — a copy without this check cannot warn about itself. The m5 main
    checkout that wrote the 2026-08-08 report does not contain this function and will
    not until that checkout advances past this merge, which is not something a session
    may make happen (pulling it races live worktrees). So this closes the class from
    here forward and on the auto-pulled machines; it does not retroactively make today's
    frozen copy honest. Until then the way to a truthful report on m5 is the out-of-tree
    invocation this probe's own remedy prints — run main's code, point NUZ_REPO_ROOT at
    the checkout. Stated rather than implied, because a cure whose reach is assumed
    wider than it is becomes the next false clean.
    """
    if root is None:
        return 0, ["self-version: no repo root — this copy cannot be attributed"]
    if not _RUNNER_SHA:
        # Neither shape is a finding, and they are NOT the same shape: stdin is the
        # deliberate run-main's-copy escape prescribed below, "unreadable" is a real
        # blind spot. Naming one for the other would be a false statement written while
        # fixing a false statement (W113).
        return 0, [f"self-version: no source bytes to compare ({_RUNNER_NO_SHA_REASON}) "
                   f"— nothing on disk that could be stale"]
    # The PATH is only used to name the file to git; the VERSION comes from _RUNNER_SHA,
    # read at import. So a file deleted mid-run is still attributable.
    self_file = Path(__file__).resolve()
    try:
        rel = self_file.relative_to(root.resolve())
    except ValueError:
        return 0, [f"self-version: the executing copy is outside the checkout "
                   f"({self_file}) — version not attributable"]
    state, detail = _version_vs_main(root, rel.as_posix(), _RUNNER_SHA)
    if state == CURRENT:
        return 0, []
    if state != STALE:
        return 0, [f"self-version: {detail}"]
    main_blob = detail
    return 1, [f"SELF STALE: the copy that wrote this report ({rel.as_posix()} "
               f"{_RUNNER_SHA[:8]}) is not origin/main's ({main_blob.strip()[:8]}) "
               f"— every finding and every remedy on this report is that copy's OLD text, "
               f"however fresh the timestamp. Run main's copy without touching the "
               f"checkout: `git -C {root} show origin/main:{rel.as_posix()} > /tmp/prop_main.py "
               f"&& NUZ_REPO_ROOT={root} python3 /tmp/prop_main.py`"]


def _self_blob() -> str:
    """Provenance for the report header: WHICH copy produced it. `repo_head` is the
    checkout's HEAD, which does not pin this file — a worktree, an out-of-tree copy and
    stdin can all report the same head. Diagnosing the 2026-08-08 incident took three
    steps (read repo_head, resolve it, diff the file); this field makes it one.

    Takes no repo: it reports the bytes this process loaded, which is true even outside
    a checkout, and it must never disagree with the comparison above by construction."""
    return _RUNNER_SHA[:12] if _RUNNER_SHA else (_RUNNER_NO_SHA_REASON or "unknown")


def probe_guardian_freshness(root: Path, args: dict, timeout: int) -> tuple[str, int, list[str]]:
    findings, ev = _self_code_staleness(root)
    seen = 0
    now = time.time()
    for item in args.get("items", []):
        # Per-item machine scoping (v1.1): a Pro-only guardian probed on M5 is a
        # false DIVERGED — jurisdiction, not divergence (found by the organ's own
        # first fleet runs: pro.runtime_reconcile flagged stale on M5 while alive
        # and fresh on Pro, where it belongs).
        mach = item.get("machines", ["all"])
        if "all" not in mach and machine_label() not in mach:
            continue
        max_age_h = float(item.get("max_age_h", 48))
        label = item.get("label", item["glob"])
        base = Path(os.path.expanduser(item["glob"]))
        paths = sorted(base.parent.glob(base.name), key=lambda p: p.stat().st_mtime,
                       reverse=True) if base.parent.exists() else []
        if not paths:
            if item.get("required"):
                findings += 1
                ev.append(f"{label}: guardian output MISSING entirely (silent-when-broken)")
            continue
        seen += 1
        age_h = (now - paths[0].stat().st_mtime) / 3600
        if age_h > max_age_h:
            findings += 1
            ev.append(f"{label}: guardian last spoke {age_h:.1f}h ago (max {max_age_h:.0f}h) — a stale guardian is a lying guardian")
    if seen == 0 and findings == 0:
        # APPEND, never replace: "no outputs found" must not overwrite a self-version
        # cannot-verify line, or the blind case reads as the clean one (W84).
        return UNPROBEABLE, 0, ev + ["no guardian outputs found on this machine"]
    return (DIVERGED if findings else RECONCILED), findings, ev


_REPO_TOKEN = "{repo}/"


def _wrap_repo_targets(entry: dict) -> list[str]:
    """Every repo-relative path a `wrap` entry executes; empty list if none.

    Scans the WHOLE target list for elements beginning with `{repo}/`: a wrap may carry
    flags before or after the path, so indexing element 1 would judge by POSITION instead
    of by entity — the form/entity confusion of superscar #3, in a new costume. Returning
    only the FIRST match is the same mistake wearing the other sleeve: a runner given two
    repo payloads executes both, and stopping early silences the second.
    """
    if entry.get("type") != "wrap":
        return []
    target = entry.get("target")
    # A bare string iterates CHARACTER by character and silently yields nothing — the
    # entry would drop out of the audit with no trace. Normalise instead of iterating.
    if isinstance(target, str):
        target = [target]
    elif not isinstance(target, list):
        return []
    # ALL of them, not the first: `["pytest", "{repo}/a.py", "{repo}/b.py"]` executes two
    # payloads, and stopping at the first silences the second.
    return [t[len(_REPO_TOKEN):] for t in target
            if isinstance(t, str) and t.startswith(_REPO_TOKEN)]


def _disk_blob(p: Path) -> str:
    """The blob git would store for what is ON DISK at `p`.

    For a symlink git stores the LINK TEXT, while `read_bytes()` follows the link and
    hashes the referent — two different representations of two different things, and the
    mismatch would read as "uncommitted edits" (silent) on a tracked symlink that is
    genuinely stale.
    """
    if p.is_symlink():
        return _blob_sha(os.readlink(p).encode())
    return _blob_sha(p.read_bytes())


def probe_executed_code_currency(root: Path, args: dict, timeout: int) -> tuple[str, int, list[str]]:
    """Every `{repo}/…` payload this organ EXECUTES — not just the one it is.

    `_self_code_staleness` covers proprioception.py itself. But seven registry entries
    shell out to OTHER scripts in the same tree, and on 2026-08-08 three of the six in
    m5's jurisdiction were behind origin/main there, one demonstrably lying: `launchagent_canon`
    reported `repo_divergent: 1` from the pre-#3799 reconciler while the merged copy
    reported 0 on the same plists in the same minute. Curing the runner and calling the
    disease closed is W107 — "I cured one wrapper of five".

    Judged by BLOB. This never runs a target to find out whether it is stale: an alarm
    that executes the code whose health it reports shares that code's failure mode (W108).

    Scope is declared, not silent (W97), and the two boundaries are drawn for opposite
    reasons. It DOES audit wraps a `--probes`/`--tags` run did not select — a currency
    finding about a probe you skipped this time is still true, and hiding it would make
    the narrow run read cleaner than the machine is. It does NOT audit wraps outside this
    machine's jurisdiction — those payloads are never executed here, so a finding about
    them is a P1 nobody on this host can act on, and the host that does run them audits
    them itself.
    """
    ev, findings, seen = [], 0, 0
    # The registry that main() actually runs, not the embedded default: `config/
    # boundaries.json` may add or replace a wrap, and auditing the defaults would report
    # on payloads nobody executes while staying silent about the ones they do.
    registry, _, _ = load_registry(root)
    me = machine_label()
    for entry in registry:
        # Jurisdiction, exactly as main() scopes it. `arsenal_seats` is mini/pro-only, so
        # on m5 its payload is never executed — calling it a stale PAYLOAD there is a
        # finding about code this machine does not run, and the machine that does run it
        # audits it itself. Same doctrine the heartbeat detector already applies to
        # guardians that legitimately do not exist on a given host.
        machines = entry.get("machines", ["all"])
        if "all" not in machines and me not in machines:
            continue
        for rel in _wrap_repo_targets(entry):
            seen += 1
            try:
                sha = _disk_blob(root / rel)
            except OSError as e:
                ev.append(f"{entry['id']}: {rel} unreadable on disk ({type(e).__name__}) "
                          f"— currency cannot be attributed")
                continue
            state, detail = _version_vs_main(root, rel, sha)
            if state == STALE:
                findings += 1
                ev.append(f"STALE PAYLOAD: {entry['id']} runs {rel} {sha[:8]}, not "
                          f"origin/main's {detail[:8]} — whatever it reported on this run is "
                          f"that older code's verdict, however fresh the report")
            elif state == UNVERIFIABLE:
                ev.append(f"{entry['id']}: {detail}")
    if seen == 0:
        return UNPROBEABLE, 0, ev + ["no {repo}-executed wrap targets in the registry"]
    return (DIVERGED if findings else RECONCILED), findings, ev


BUILTINS = {
    "git_alignment": probe_git_alignment,
    "executed_code_currency": probe_executed_code_currency,
    "produced_promoted": probe_produced_promoted,
    "home_fork_scripts": probe_home_fork_scripts,
    "guardian_freshness": probe_guardian_freshness,
}


# ---------------------------------------------------------------- wraps

_EXIT_CODE_EVIDENCE_CAP = 5


def _parse_exit_code(rc: int, out: str, err: str) -> tuple[str, int, list[str]]:
    """`parse: exit_code` verdict: RECONCILED/0-findings iff rc==0, otherwise DIVERGED
    with a finding count that reflects the tool's own output — not a hardcoded 1.

    §5-docsync-underreport (2026-08-07): the previous version took only the LAST line
    of the wrapped tool's combined output and hardcoded n_findings=1 regardless of how
    many things actually failed. Against docs_sync.py --check (2 stale files: README.md
    + docs/AI_ONBOARDING.md, one line each under a "DOCSYNC STALE — run: ..." header)
    this silently dropped README.md and reported "1 finding" when there were 2 — the
    report SessionStart and the healers read under-counted by construction. A tool that
    fails with MULTIPLE lines is assumed to emit one header/summary line (own name for
    the problem, not itself a finding) followed by the real per-item detail lines; a
    tool that fails with a SINGLE line, or with empty output, keeps the original shape
    (that line — or "exit {rc}" — as the one finding) since there is no header to strip.
    """
    if rc == 0:
        return RECONCILED, 0, []
    combined = (out or err).strip()
    if not combined:
        return DIVERGED, 1, [f"exit {rc}"]
    lines = [ln[:160] for ln in combined.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return DIVERGED, 1, lines
    detail = lines[1:]  # drop the tool's own header/summary line — never a finding itself
    n = len(detail)
    ev = detail[:_EXIT_CODE_EVIDENCE_CAP]
    if n > _EXIT_CODE_EVIDENCE_CAP:
        ev = ev + [f"... ({_EXIT_CODE_EVIDENCE_CAP} of {n} shown)"]
    return DIVERGED, n, ev


def run_wrap(root: Path, entry: dict, timeout: int) -> tuple[str, int, list[str]]:
    argv = [a.replace("{repo}", str(root)) for a in entry["target"]]
    if argv[0].startswith("python") and len(argv) > 1:
        if not Path(argv[1]).exists():
            return UNPROBEABLE, 0, [f"wrapped reconciler not on this checkout yet: {Path(argv[1]).name}"]
    elif shutil.which(argv[0]) is None and not Path(argv[0]).exists():
        return UNPROBEABLE, 0, [f"wrapped command not found: {argv[0]}"]
    try:
        rc, out, err = sh(argv, timeout=timeout, cwd=root)
    except subprocess.TimeoutExpired:
        return UNPROBEABLE, 0, [f"wrapped reconciler timed out after {timeout}s"]
    except FileNotFoundError as e:
        return UNPROBEABLE, 0, [f"wrapped reconciler missing: {e}"]
    parse = entry.get("parse", "exit_code")
    if parse == "exit_code":
        return _parse_exit_code(rc, out, err)
    try:
        data = json.loads(out.strip() or "null")
    except json.JSONDecodeError:
        return UNPROBEABLE, 0, [f"non-JSON output (exit {rc}): {(err or out).strip()[:120]}"]
    if parse == "findings_list":
        # Schema drift must not normalize into calm (red-team #6): a list whose items
        # lack the declared verdict_key is an unknown schema, never RECONCILED.
        if isinstance(data, dict) and entry.get("unwrap_key"):
            if entry["unwrap_key"] not in data:
                return UNPROBEABLE, 0, [f"schema drift: key '{entry['unwrap_key']}' absent (got: {', '.join(list(data.keys())[:6])})"]
            data = data[entry["unwrap_key"]]
        if not isinstance(data, list):
            return UNPROBEABLE, 0, [f"expected JSON list, got {type(data).__name__}"]
        bad_key, ok_values = entry.get("verdict_key"), set(entry.get("ok_values", []))
        if bad_key and data and not any(bad_key in i for i in data if isinstance(i, dict)):
            return UNPROBEABLE, 0, [f"schema drift: no item carries key '{bad_key}'"]
        items = [i for i in data if not bad_key or str(i.get(bad_key, "")) not in ok_values]
        ev = [json.dumps(i, ensure_ascii=False)[:160] for i in items[:5]]
        return (DIVERGED if items else RECONCILED), len(items), ev
    if parse == "category_counts":
        if not isinstance(data, dict):
            return UNPROBEABLE, 0, [f"expected JSON object, got {type(data).__name__}"]
        known = set(entry.get("bad_categories", [])) | set(entry.get("ok_categories", []))
        if known and not (known & set(data.keys())):
            return UNPROBEABLE, 0, [f"schema drift: none of the declared categories present (got: {', '.join(list(data.keys())[:6])})"]
        bad = {k: len(v) for k, v in data.items()
               if k in set(entry.get("bad_categories", [])) and v}
        ev = [f"{k}: {n}" for k, n in bad.items()]
        return (DIVERGED if bad else RECONCILED), sum(bad.values()), ev
    return UNPROBEABLE, 0, [f"unknown parse mode {parse}"]


# ---------------------------------------------------------------- registry

DEFAULT_REGISTRY: list[dict] = [
    {
        "id": "git_alignment", "type": "builtin", "target": "git_alignment",
        "class": "checkout<->origin",
        "boundary": "machine-checkout <-> origin/main",
        "machines": ["all"], "tags": ["fast", "remote-safe"], "timeout_sec": 40,
        "severity": "P1", "args": {"behind_warn": 10},
        "fix_hint": "interactive pull on this machine's main (never from an agent session)",
    },
    {
        "id": "regulatory_promotion", "type": "builtin", "target": "produced_promoted",
        "class": "produced<->promoted",
        "boundary": "produced-on-host <-> committed-to-repo",
        "machines": ["all"], "tags": ["fast", "remote-safe"], "timeout_sec": 20,
        "severity": "P1",
        "args": {"pairs": [{"glob": "research/regulatory/*-delta.json", "label": "regulatory deltas"}]},
        "fix_hint": "promote stranded deltas: git add research/regulatory/*-delta.json + PR",
    },
    {
        "id": "home_fork_scripts", "type": "builtin", "target": "home_fork_scripts",
        "class": "home<->repo",
        "boundary": "$HOME live copy <-> repo source of truth",
        "machines": ["all"], "tags": ["fast"], "timeout_sec": 20,
        "severity": "P1",
        "args": {"pairs": [
            {"live": "~/.fly/bin/fly_pg_tunnel_supervisor.sh", "repo": "scripts/fly_pg_tunnel_supervisor.sh"},
            {"live": "~/.nuzantara-cron/agent_worktree_cleanup_cron.sh", "repo": "scripts/agent_worktree_cleanup_cron.sh"},
            {"live": "~/.nuzantara-cron/verify_connectome_run.sh", "repo": "scripts/verify_connectome_run.sh"},
            {"live": "~/scripts/regulatory-watcher-run.sh", "repo": "infra/launchagents/wrappers/regulatory-watcher-run.sh"},
        ]},
        "fix_hint": "diff the pair, port the newer content into the repo, then refresh the live copy from repo",
    },
    {
        "id": "executed_code_currency", "type": "builtin", "target": "executed_code_currency",
        "class": "executed<->committed",
        "boundary": "the {repo}/… payloads this organ RUNS <-> origin/main",
        "machines": ["all"], "tags": ["fast"], "timeout_sec": 30,
        "severity": "P1",
        "args": {},
        "fix_hint": ("the SCHEDULE is fine and the report is fresh — the code that produced "
                     "the named verdicts is old. Do NOT pull the checkout to fix it (W106b); "
                     "re-run that probe's target from origin/main, e.g. "
                     "`git show origin/main:<path> > /tmp/p.py && python3 /tmp/p.py`, and "
                     "believe THAT output. On pro/mini this finding should never appear: "
                     "their checkouts auto-pull (measured 0/8 stale, 2026-08-08)."),
    },
    {
        "id": "guardian_freshness", "type": "builtin", "target": "guardian_freshness",
        "class": "guardian<->cadence",
        "boundary": "guardian output <-> its promised cadence",
        "machines": ["all"], "tags": ["fast"], "timeout_sec": 15,
        "severity": "P2",
        "args": {"items": [
            {"glob": "~/.nuzantara-proprioception/last.json", "max_age_h": 48, "label": "proprioception (self)"},
            {"glob": "~/.organism/last_seen/pro.runtime_reconcile.json", "max_age_h": 26, "label": "runtime-reconcile (W81 watchdog)", "machines": ["pro"]},
            {"glob": "~/logs/verify-connectome*.log", "max_age_h": 192, "label": "verify-connectome (weekly)"},
            {"glob": "~/.organism/arsenal/last.json", "max_age_h": 26, "label": "arsenal seats probe (healer-armed)", "machines": ["mini", "pro"]},
        ]},
        "fix_hint": "a stale guardian: run it by hand, read ITS log, then fix its scheduler",
    },
    {
        # The detector was written, tested and CI-verified — and then run by nobody.
        # `lint_worktree_husky_symlink.py` has exactly one caller in the tree
        # (immune-enforcement.yml), and what that workflow runs is its unit TEST.
        # A GitHub runner cannot see a worktree on M5, so the tool had never once
        # answered the question it was built for. Measured by hand on M5 2026-07-27:
        # 15 of 115 worktrees had no `.husky/_` at all — every push from them ran NO
        # hook and exited 0 silently. That is family #2 one level up: not a missing
        # detector, a detector that is never asked. This entry is the asking, and it
        # reuses the real tool rather than growing a twin probe next to it (the twin
        # was written first and deleted on discovering this file — anti-twin: grep for
        # the existing tool BEFORE building the cure).
        #
        # ok_values keeps GONE deliberately: a GONE record is a stale worktree-registry
        # entry (the directory is gone), which is `git worktree prune` territory and the
        # gc cron's job — not a worktree pushing without a gate. The tool itself scores
        # it the same way (FINDING_HEALTHS = MISSING | DANGLING); if the two ever
        # disagree, this list is the side that is wrong.
        "id": "worktree_gate_shim", "type": "wrap",
        "target": ["python3", "{repo}/scripts/lint_worktree_husky_symlink.py", "--json"],
        "class": "worktree<->gate",
        "boundary": "worktree <-> the pre-push hook git actually invokes there",
        "machines": ["all"], "tags": ["fast"], "timeout_sec": 60,
        "severity": "P1",
        "parse": "findings_list", "unwrap_key": "worktrees",
        "verdict_key": "health", "ok_values": ["OK", "GONE"],
        "fix_hint": "recreate via `python scripts/agent_start.py` (it symlinks .husky/_), or "
                    "`ln -sfn <main-checkout>/.husky/_ <worktree>/.husky/_` — a worktree born from a "
                    "bare `git worktree add` pushes with NO gate and reports a clean push",
    },
    {
        "id": "launchd_liveness", "type": "wrap",
        "target": ["python3", "{repo}/scripts/launchd_liveness_detector.py", "--json"],
        "class": "wrapper<->payload",
        "boundary": "launchd exit-code <-> payload log content (W84)",
        "machines": ["all"], "tags": ["launchd"], "timeout_sec": 60,
        "severity": "P1", "parse": "findings_list", "unwrap_key": "findings",
        # DISABLED added 2026-07-19: launchd_liveness_detector.py (PR #2710, 2026-07-18)
        # excludes DISABLED from its own ALARM_VERDICTS ("deliberate disarm — launchctl
        # disable (not an alarm)") — a stale ok_values here still flagged it P1 DIVERGED
        # every tick (found live on Mini: com.balizero.wa-mirror, correctly disabled
        # per the W67c single-node-Telegram fix). Keep aligned with the detector's own
        # alarm semantics, not a second, drifted opinion of what counts as ok.
        "verdict_key": "verdict", "ok_values": ["OK", "NOT-LOADED", "RECOVERED", "DISABLED"],
        "fix_hint": "read the job's real log; DEAD-GREEN = TCC re-grant (operator); ARMED-TO-NOTHING = retire or repoint the plist",
    },
    {
        "id": "launchagent_canon", "type": "wrap",
        "target": ["python3", "{repo}/scripts/launchagent_reconcile.py", "--json"],
        "class": "canon<->installed",
        "boundary": "~/Library/LaunchAgents <-> launchctl <-> repo canon (#1926)",
        "machines": ["all"], "tags": ["launchd"], "timeout_sec": 90,
        "severity": "P2", "parse": "category_counts",
        "bad_categories": ["zombie_loaded", "broken_target", "home_fork_target", "repo_divergent"],
        "ok_categories": ["junk", "present_not_loaded", "repo_symlinked", "canon_paired"],
        "fix_hint": "scripts/launchagent_reconcile.py (markdown mode) for the full categorized report",
    },
    {
        "id": "organs_heartbeat", "type": "wrap",
        "target": ["python3", "{repo}/scripts/organism_stale_detector.py", "--json"],
        "class": "organ<->heartbeat",
        "boundary": "organ heartbeat sidecar <-> declared liveness",
        "machines": ["all"], "tags": ["organs"], "timeout_sec": 45,
        "severity": "P1", "parse": "findings_list",
        # kind="warning" (added 2026-08-22) is "breathing, not working this tick" —
        # real enough to print in the SessionStart report a human reads, NOT a P1
        # boundary divergence. Without this exemption the three permanent
        # *.agent_worktree_cleanup advisories ("WIP worktree skipped") would sit at
        # P1 on every node forever, which is how a channel earns being ignored —
        # the failure this detector was born to end, re-created one severity up.
        # stale / dead_channel / corrupt / unhealthy still DIVERGE, unchanged.
        "verdict_key": "kind", "ok_values": ["warning"],
        "fix_hint": "read the organ's own log — restart is NOT the cure (heartbeat TAC 2026-07-02)",
    },
    {
        "id": "docs_sync", "type": "wrap",
        "target": ["python3", "{repo}/scripts/docs_sync.py", "--check"],
        "class": "code<->docs",
        "boundary": "protected docs pointers <-> canonical generator output",
        "machines": ["all"], "tags": ["docs"], "timeout_sec": 60,
        "severity": "P3", "parse": "exit_code",
        "fix_hint": "restore the protected pointer with: python3 scripts/docs_sync.py",
    },
    {
        # Reader, not prober: re-emits the last arsenal_probe report (no live LLM
        # calls here — the heavy probe is healer-armed on Mini AND on Pro since
        # 2026-07-18, pro-healer Receptor D). Transients
        # (QUOTA/SHED/TIMEOUT) are ok_values: they belong to transition alerting,
        # not boundary reconciliation — only persistent seat-death DIVERGEs.
        "id": "arsenal_seats", "type": "wrap",
        "target": ["python3", "{repo}/scripts/arsenal_probe.py", "--read-last", "--json"],
        "class": "seat<->armed",
        "boundary": "AI-seat credential/quota <-> last live probe (cascade depth)",
        "machines": ["mini", "pro"], "tags": ["fast", "arsenal"], "timeout_sec": 15,
        "severity": "P1", "parse": "findings_list", "unwrap_key": "findings",
        "verdict_key": "status",
        "ok_values": ["LIVE", "CRED_UNAVAILABLE", "NOT_INSTALLED", "CONTEXT_AUTH",
                       "SHED", "QUOTA_DEAD", "TIMEOUT"],
        "fix_hint": "scripts/arsenal_probe.py --table for detail; AUTH/BALANCE dead = operator relogin/top-up (see docs/runbooks/arsenal-probe.md)",
    },
    {
        # ADDS m5 arsenal-seat coverage (the entry above is mini/pro only — m5
        # has never had one). Deliberately a NEW entry, not a replacement of
        # the one above: this pilot registers only 3 seats (VCR spec §4/R8),
        # narrower than arsenal_probe's full 5-seat REQUIRED_SEATS["m5"] —
        # swapping the existing entry's target here would silently shrink a
        # P1 boundary that's out of this pilot's scope to touch. Routed
        # through the VCR accessor (infra/vcr/), not a raw --read-last parse:
        # hysteresis-debounced + verifier-hash-audited, cache-only (no live
        # probe from inside proprioception's own budget loop).
        "id": "arsenal_seats_vcr_m5", "type": "wrap",
        "target": ["python3", "{repo}/infra/vcr/cli.py", "findings", "--json"],
        "class": "seat<->armed",
        "boundary": "AI-seat credential/quota <-> VCR-accessor materialized state (m5 pilot subset)",
        "machines": ["m5"], "tags": ["fast", "arsenal", "vcr"], "timeout_sec": 15,
        "severity": "P2", "parse": "findings_list", "unwrap_key": "findings",
        # ok_values is deliberately EMPTY — unlike the sibling "arsenal_seats"
        # entry above (which reads arsenal_probe's raw --read-last vocabulary
        # and treats some raw statuses as "handled elsewhere, don't escalate"),
        # cmd_findings() already filters to ONLY claims where
        # MaterializedState.all_healthy() is False (verifier/coverage/
        # freshness/truth-debounced) and reports an axis-derived reason
        # string, never a raw arsenal_probe status. Any entry present here IS
        # a real problem by construction — there is no secondary "ignore
        # this subtype" concept for the VCR-routed consumer. Copying the
        # sibling's ok_values list here was a same-shape-different-contract
        # bug (Codex red-team, 2026-08-03): it would have silently absolved
        # a verifier-DRIFTED claim whose last raw probe happened to read
        # "LIVE" — exactly the failure mode this pilot exists to catch.
        "verdict_key": "status",
        "ok_values": [],
        "fix_hint": "python3 infra/vcr/cli.py check --seat <s> --host m5 --auth-context interactive (drafts/2026-08-03-vcr-pilot-v2.1-and-build-workflow.md)",
    },
    {
        # M5-only launchd SSH tunnel (com.balizero.flowkit-pro-tunnel) that
        # WR2 image-gen depends on for FlowKit reachability. Found live
        # 2026-08-21 (dispatch "revive dead organs") with ZERO coverage
        # anywhere: no heartbeat sidecar, no proprioception entry, no alert —
        # its stderr log accumulated 800+ "Operation timed out" lines across
        # 5+ days while nothing watched. This entry is the cure: on-demand
        # (no M5 daemon per CLAUDE.md §1), piggybacking on whatever already
        # triggers a proprioception sweep each session, same pattern as
        # arsenal_seats_vcr_m5 above. Severity P2, not P1: WR2_IMAGE_BACKEND
        # "auto" (default) silently falls back to Playwright when this tunnel
        # is down — a cost/latency finding, never data loss.
        "id": "flowkit_tunnel", "type": "wrap",
        "target": ["python3", "{repo}/scripts/check_flowkit_tunnel.py", "--quiet"],
        "class": "tunnel<->reachable",
        "boundary": "flowkit ssh tunnel (M5->Pro, 127.0.0.1:8100/9222) <-> live HTTP reachability",
        "machines": ["m5"], "tags": ["fast", "wr2"], "timeout_sec": 15,
        "severity": "P2", "parse": "exit_code",
        "fix_hint": "launchctl print gui/$(id -u)/com.balizero.flowkit-pro-tunnel; tail ~/Library/Logs/flowkit-pro-tunnel.err — WR2 falls back to Playwright automatically (auto backend), no data loss while down",
    },
]

REQUIRED_KEYS = {"id", "type", "target", "class", "boundary", "machines", "severity", "fix_hint"}


def validate_registry(registry: list[dict]) -> list[str]:
    errors = []
    seen_ids = set()
    for i, e in enumerate(registry):
        missing = REQUIRED_KEYS - set(e.keys())
        if missing:
            errors.append(f"probe[{i}] ({e.get('id', '?')}): missing keys {sorted(missing)}")
        if e.get("id") in seen_ids:
            errors.append(f"probe[{i}]: duplicate id {e['id']}")
        seen_ids.add(e.get("id"))
        if e.get("type") == "builtin" and e.get("target") not in BUILTINS:
            errors.append(f"probe[{i}] ({e.get('id')}): unknown builtin '{e.get('target')}'")
        if e.get("class") not in KNOWN_BOUNDARY_CLASSES:
            errors.append(f"probe[{i}] ({e.get('id')}): class '{e.get('class')}' not in taxonomy")
    return errors


def load_registry(root: Path | None) -> tuple[list[dict], str, str]:
    """Returns (registry, source, sha) — provenance stamped into the report (red-team #3/#7)."""
    if root:
        cfg = root / "config" / "boundaries.json"
        if cfg.exists():
            try:
                raw = cfg.read_text()
                data = json.loads(raw)
                if isinstance(data.get("probes"), list) and data["probes"]:
                    return data["probes"], "config/boundaries.json", hashlib.sha256(raw.encode()).hexdigest()[:12]
            except (json.JSONDecodeError, OSError) as e:
                sys.stderr.write(f"proprioception: boundaries.json unreadable ({e}) — using embedded defaults\n")
    blob = json.dumps(DEFAULT_REGISTRY, sort_keys=True).encode()
    return DEFAULT_REGISTRY, "embedded", hashlib.sha256(blob).hexdigest()[:12]


# ---------------------------------------------------------------- fleet

def fleet_probe(hosts: list[str], self_path: Path) -> list[dict]:
    results = []
    src = self_path.read_text()
    for host in hosts:
        t0 = time.monotonic()
        try:
            p = subprocess.run(
                ["ssh", *SSH_OPTS, host, "python3 - --json --no-report --tags remote-safe --no-fetch"],
                input=src, capture_output=True, text=True, timeout=120,
            )
            if p.returncode not in (0, 1) or not p.stdout.strip():
                results.append(verdict(f"fleet:{host}", "fleet <-> this machine", "checkout<->origin",
                                       UNPROBEABLE, "P2", 0,
                                       [f"remote run failed (exit {p.returncode}): {p.stderr.strip()[:120]}"],
                                       f"ssh {host} then run proprioception by hand", t0))
                continue
            remote = json.loads(p.stdout)
            div = [r for r in remote.get("probes", []) if r["status"] == DIVERGED]
            # div[:4] truncates the PROBE list too; say so rather than let four
            # stand in for forty (same W97 shape, one level up).
            ev = [f"{finding_label(r)}: {r['evidence'][0] if r['evidence'] else r['n_findings']}" for r in div[:4]]
            if len(div) > 4:
                ev.append(f"(+{len(div) - 4} more diverged probes on {host} not listed)")
            results.append(verdict(f"fleet:{host}", f"fleet({host}) <-> origin", "checkout<->origin",
                                   DIVERGED if div else RECONCILED, "P1" if div else "P2",
                                   sum(r["n_findings"] for r in div),
                                   ev or [f"{len(remote.get('probes', []))} remote probes clean"],
                                   f"ssh {host} → python3 scripts/proprioception.py for the full local report", t0))
        except Exception as e:  # ssh hang/timeout/json — fleet stays probeable-degraded, never fatal
            results.append(verdict(f"fleet:{host}", "fleet <-> this machine", "checkout<->origin",
                                   UNPROBEABLE, "P2", 0,
                                   [f"{type(e).__name__}: {str(e)[:120]}"],
                                   f"check ssh {host} reachability (pro-lan fallback on M5)", t0))
    return results


# ---------------------------------------------------------------- report

def write_report(report: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REPORT_DIR / "last.json.tmp"
    tmp.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    tmp.rename(REPORT_DIR / "last.json")
    lines = [f"# proprioception — {report['machine']} — {report['ts']}",
             f"{report['summary']}",
             f"provenance: runner {report['runner_version']} · config {report['config_source']}@{report['config_sha']} · repo {report['repo_head']} · probes {report['probes_run']}/{report['probes_expected']}",
             ""]
    for r in report["probes"]:
        mark = {"RECONCILED": "OK ", "DIVERGED": "!! ", "UNPROBEABLE": "?? "}[r["status"]]
        lines.append(f"- {mark}[{r['severity']}] {r['id']} ({r['boundary']}) — {r['n_findings']} findings, {r['duration_ms']}ms")
        for e in r["evidence"]:
            lines.append(f"    - {e}")
        if r["status"] == DIVERGED:
            lines.append(f"    fix: {r['fix_hint']}")
    if report["unwatched_classes"]:
        lines.append("")
        lines.append(f"UNWATCHED boundary classes on this machine: {', '.join(report['unwatched_classes'])}")
    tmp_md = REPORT_DIR / "last.md.tmp"
    tmp_md.write_text("\n".join(lines) + "\n")
    tmp_md.rename(REPORT_DIR / "last.md")


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    failures = []
    errs = validate_registry(DEFAULT_REGISTRY)
    if errs:
        failures.append(f"default registry invalid: {errs}")
    # Parser guards: garbage and schema-drift must yield UNPROBEABLE, never RECONCILED.
    # ABSOLUTE /bin/echo — a bare "echo" fails the exists-check and fake-passes the test
    # without ever exercising the guards (spalla finding #6: the selftest itself lied).
    echo = shutil.which("echo") or "/bin/echo"
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cases = [
            ({"target": [echo, "not json"], "parse": "findings_list", "verdict_key": "verdict"},
             "garbage output"),
            ({"target": [echo, '[{"foo": 1}]'], "parse": "findings_list", "verdict_key": "verdict"},
             "verdict-key drift"),
            ({"target": [echo, '{"renamed": []}'], "parse": "category_counts",
              "bad_categories": ["zombie_loaded"], "ok_categories": ["junk"]},
             "category drift"),
            ({"target": [echo, '{"other": 1}'], "parse": "findings_list", "unwrap_key": "findings",
              "verdict_key": "verdict"},
             "unwrap-key drift"),
        ]
        for entry, label in cases:
            st, _, ev = run_wrap(root, entry, 10)
            if st != UNPROBEABLE:
                failures.append(f"{label} parsed as {st}, want UNPROBEABLE ({ev[:1]})")
        # and a POSITIVE control: a well-formed payload must actually parse (guards must
        # not be so paranoid that nothing ever reconciles)
        ok_entry = {"target": [echo, '{"findings": [], "alarms": 0}'], "parse": "findings_list",
                    "unwrap_key": "findings", "verdict_key": "verdict"}
        st, _, _ = run_wrap(root, ok_entry, 10)
        if st != RECONCILED:
            failures.append(f"well-formed payload parsed as {st}, want RECONCILED")
        # 2026-07-19: DISABLED is a deliberate `launchctl disable` per the detector's own
        # ALARM_VERDICTS (it is NOT in that set) — the launchd_liveness probe's ok_values
        # must agree, or every intentionally-disabled job (e.g. wa-mirror on Mini, W67c)
        # cries wolf as P1 DIVERGED forever.
        launchd_entry = next(e for e in DEFAULT_REGISTRY if e["id"] == "launchd_liveness")
        disabled_payload = json.dumps({"findings": [{"label": "com.balizero.wa-mirror", "verdict": "DISABLED"}], "alarms": 0})
        disabled_entry = {**launchd_entry, "target": [echo, disabled_payload]}
        st, _, ev = run_wrap(root, disabled_entry, 10)
        if st != RECONCILED:
            failures.append(f"DISABLED verdict parsed as {st}, want RECONCILED ({ev[:1]})")
        if redact("token Bearer abcdef123456789012 end") == "token Bearer abcdef123456789012 end":
            failures.append("redact() failed to mask a Bearer token")
    if failures:
        print("SELFTEST FAIL:\n  " + "\n  ".join(failures))
        return 2
    print(f"SELFTEST OK — registry valid ({len(DEFAULT_REGISTRY)} probes), parser guards hold, redaction holds")
    return 0


# ---------------------------------------------------------------- main

def main() -> int:
    if os.environ.get("PROPRIOCEPTION_DISABLED") == "1":
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fleet", action="store_true")
    ap.add_argument("--no-report", action="store_true", help="don't write ~/.nuzantara-proprioception")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--tags", default="", help="comma-set: run only probes with any of these tags")
    ap.add_argument("--probes", default="", help="comma-set: run only these probe ids")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any P1 DIVERGED")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    root = repo_root()
    me = machine_label()
    registry, config_source, config_sha = load_registry(root)
    reg_errors = validate_registry(registry)
    if reg_errors:
        sys.stderr.write("proprioception: REGISTRY INVALID — refusing to run half-blind:\n  "
                         + "\n  ".join(reg_errors) + "\n")
        return 2

    want_tags = {t for t in args.tags.split(",") if t}
    want_ids = {p for p in args.probes.split(",") if p}

    scoped = [e for e in registry
              if ("all" in e.get("machines", ["all"]) or me in e.get("machines", []))]
    selected = [e for e in scoped
                if (not want_tags or want_tags & set(e.get("tags", [])))
                and (not want_ids or e["id"] in want_ids)]

    results: list[dict] = []
    for entry in selected:
        t0 = time.monotonic()
        timeout = int(entry.get("timeout_sec", 60))
        if root is None:
            results.append(verdict(entry["id"], entry["boundary"], entry["class"], UNPROBEABLE,
                                   entry["severity"], 0, ["no repo checkout found on this machine"],
                                   entry["fix_hint"], t0))
            continue
        try:
            if entry["type"] == "builtin":
                probe_args = dict(entry.get("args", {}))
                if entry["target"] == "git_alignment" and args.no_fetch:
                    probe_args["no_fetch"] = True
                status, n, ev = BUILTINS[entry["target"]](root, probe_args, timeout)
            else:
                status, n, ev = run_wrap(root, entry, timeout)
        except subprocess.TimeoutExpired:
            status, n, ev = UNPROBEABLE, 0, [f"probe timed out after {timeout}s"]
        except Exception as e:  # a probe must never kill the organ
            status, n, ev = UNPROBEABLE, 0, [f"{type(e).__name__}: {str(e)[:140]}"]
        fix_hint = entry["fix_hint"]
        if entry["id"] == "git_alignment":
            fix_hint = _git_alignment_remedy(entry, me, ev)
        elif entry["id"] == "arsenal_seats_vcr_m5":
            fix_hint = _arsenal_seats_vcr_m5_remedy(entry)
        elif entry["id"] == "guardian_freshness":
            fix_hint = _guardian_freshness_remedy(entry, ev)
        results.append(verdict(entry["id"], entry["boundary"], entry["class"], status,
                               entry["severity"], n, ev, fix_hint, t0))

    if args.fleet:
        self_path = Path(__file__) if "__file__" in globals() and Path(__file__).exists() else None
        if self_path is None:
            sys.stderr.write("proprioception: --fleet requires running from a file, not stdin\n")
        else:
            hosts = [h for h in ("pro", "mini", "m5") if h != me][:2]
            results.extend(fleet_probe(hosts, self_path))

    if not results:
        sys.stderr.write("proprioception: zero probes ran — selection too narrow or registry empty\n")
        return 2

    watched = {e["class"] for e in scoped}
    unwatched = [c for c in KNOWN_BOUNDARY_CLASSES if c not in watched]
    diverged = [r for r in results if r["status"] == DIVERGED]
    unprobeable = [r for r in results if r["status"] == UNPROBEABLE]
    summary = (f"proprioception: {len(results)} probes on {me} — "
               f"{len(diverged)} DIVERGED, {len(unprobeable)} unprobeable, "
               f"{len(results) - len(diverged) - len(unprobeable)} reconciled")
    report = {
        "schema": SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "machine": me,
        "repo_head": git_head(root) if root else "no-repo",
        "runner_blob": _self_blob(),
        "config_source": config_source,
        "config_sha": config_sha,
        "probes_expected": len(selected) + (2 if args.fleet else 0),
        "probes_run": len(results),
        "unwatched_classes": unwatched,
        "summary": summary,
        "probes": results,
    }
    if not args.no_report:
        try:
            write_report(report)
        except OSError as e:
            sys.stderr.write(f"proprioception: report write FAILED: {e}\n")
            return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(summary)
        for r in diverged:
            # Same finding-level truncation the SessionStart receptor carries — see
            # the W97 note in scripts/hooks/proprioception_sessionstart.sh. evidence
            # holds up to 5 items (run_wrap's items[:5]) and n_findings is the true
            # total, which can be far larger; printing evidence[0] alone reads as
            # "one finding" for a probe reporting fifty-five.
            print(f"  !! [{r['severity']}] {finding_label(r)}: "
                  f"{r['evidence'][0] if r['evidence'] else r['n_findings']}")
            print(f"     fix: {r['fix_hint']}")
        if unwatched:
            print(f"  (unwatched classes: {', '.join(unwatched)})")
    if args.strict and any(r["severity"] == "P1" for r in diverged):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
