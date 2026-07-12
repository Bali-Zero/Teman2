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
    "canon<->installed",        # repo launchagent canon vs ~/Library vs launchctl (#1926)
    "organ<->heartbeat",        # declared organs vs sidecar liveness
    "code<->docs",              # W86
    "defined<->live",           # e.g. Qdrant collections — NO PROBE in v1 (A6)
    "process<->process",        # e.g. /health/detailed provenance — NO PROBE in v1 (A2)
    "seat<->armed",             # AI-seat credential/quota vs live probe (arsenal, #2)
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
            out.append({"live": pair["live"], "repo": pair["repo"]})
    return out


def probe_home_fork_scripts(root: Path, args: dict, timeout: int) -> tuple[str, int, list[str]]:
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
            findings += 1
            ev.append(f"NO REPO COUNTERPART: {live} executes live with no source of truth in repo")
            continue
        if sha256_file(live) != sha256_file(repo):
            findings += 1
            ev.append(f"DIVERGED: {live} != {pair['repo']} — a fix is stranded on one side")
    if probeable == 0:
        return UNPROBEABLE, 0, ["no configured live copies exist on this machine"]
    return (DIVERGED if findings else RECONCILED), findings, ev


def probe_guardian_freshness(root: Path, args: dict, timeout: int) -> tuple[str, int, list[str]]:
    ev, findings, seen = [], 0, 0
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
        return UNPROBEABLE, 0, ["no guardian outputs found on this machine"]
    return (DIVERGED if findings else RECONCILED), findings, ev


BUILTINS = {
    "git_alignment": probe_git_alignment,
    "produced_promoted": probe_produced_promoted,
    "home_fork_scripts": probe_home_fork_scripts,
    "guardian_freshness": probe_guardian_freshness,
}


# ---------------------------------------------------------------- wraps

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
        return (RECONCILED if rc == 0 else DIVERGED), (0 if rc == 0 else 1), \
            ([] if rc == 0 else [(out or err).strip().splitlines()[-1][:160] if (out or err).strip() else f"exit {rc}"])
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
        "id": "guardian_freshness", "type": "builtin", "target": "guardian_freshness",
        "class": "guardian<->cadence",
        "boundary": "guardian output <-> its promised cadence",
        "machines": ["all"], "tags": ["fast"], "timeout_sec": 15,
        "severity": "P2",
        "args": {"items": [
            {"glob": "~/.nuzantara-proprioception/last.json", "max_age_h": 48, "label": "proprioception (self)"},
            {"glob": "~/.organism/last_seen/pro.runtime_reconcile.json", "max_age_h": 26, "label": "runtime-reconcile (W81 watchdog)", "machines": ["pro"]},
            {"glob": "~/logs/verify-connectome*.log", "max_age_h": 192, "label": "verify-connectome (weekly)"},
            {"glob": "~/.organism/arsenal/last.json", "max_age_h": 26, "label": "arsenal seats probe (healer-armed)", "machines": ["mini"]},
        ]},
        "fix_hint": "a stale guardian: run it by hand, read ITS log, then fix its scheduler",
    },
    {
        "id": "launchd_liveness", "type": "wrap",
        "target": ["python3", "{repo}/scripts/launchd_liveness_detector.py", "--json"],
        "class": "wrapper<->payload",
        "boundary": "launchd exit-code <-> payload log content (W84)",
        "machines": ["all"], "tags": ["launchd"], "timeout_sec": 60,
        "severity": "P1", "parse": "findings_list", "unwrap_key": "findings",
        "verdict_key": "verdict", "ok_values": ["OK", "NOT-LOADED", "RECOVERED"],
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
        "fix_hint": "read the organ's own log — restart is NOT the cure (heartbeat TAC 2026-07-02)",
    },
    {
        "id": "docs_sync", "type": "wrap",
        "target": ["python3", "{repo}/scripts/docs_sync.py", "--check"],
        "class": "code<->docs",
        "boundary": "code counts <-> docs numbers (W86)",
        "machines": ["all"], "tags": ["docs"], "timeout_sec": 60,
        "severity": "P3", "parse": "exit_code",
        "fix_hint": "python3 scripts/docs_sync.py  (regen in the SAME commit as the feature)",
    },
    {
        # Reader, not prober: re-emits the last arsenal_probe report (no live LLM
        # calls here — the heavy probe is healer-armed on Mini). Transients
        # (QUOTA/SHED/TIMEOUT) are ok_values: they belong to transition alerting,
        # not boundary reconciliation — only persistent seat-death DIVERGEs.
        "id": "arsenal_seats", "type": "wrap",
        "target": ["python3", "{repo}/scripts/arsenal_probe.py", "--read-last", "--json"],
        "class": "seat<->armed",
        "boundary": "AI-seat credential/quota <-> last live probe (cascade depth)",
        "machines": ["mini"], "tags": ["fast", "arsenal"], "timeout_sec": 15,
        "severity": "P1", "parse": "findings_list", "unwrap_key": "findings",
        "verdict_key": "status",
        "ok_values": ["LIVE", "CRED_UNAVAILABLE", "NOT_INSTALLED", "CONTEXT_AUTH",
                       "SHED", "QUOTA_DEAD", "TIMEOUT"],
        "fix_hint": "scripts/arsenal_probe.py --table for detail; AUTH/BALANCE dead = operator relogin/top-up (see docs/runbooks/arsenal-probe.md)",
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
            ev = [f"{r['id']}: {r['evidence'][0] if r['evidence'] else r['n_findings']}" for r in div[:4]]
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
        results.append(verdict(entry["id"], entry["boundary"], entry["class"], status,
                               entry["severity"], n, ev, entry["fix_hint"], t0))

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
            print(f"  !! [{r['severity']}] {r['id']}: {r['evidence'][0] if r['evidence'] else r['n_findings']}")
            print(f"     fix: {r['fix_hint']}")
        if unwatched:
            print(f"  (unwatched classes: {', '.join(unwatched)})")
    if args.strict and any(r["severity"] == "P1" for r in diverged):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
