#!/usr/bin/env python3
"""verify_connectome.py — re-walk the declared system arteries and detect silent edge death.

The connectome (docs/connectome/edges/*.yaml) is the empirical census of every
producer→consumer edge in the Nuzantara organism (PG channels, queues, launchd
fleet, GH workflows, sync daemons, HOME-forks, webhooks, hooks, MCP servers).
This verifier re-probes the edges that carry a runnable probe and reports drift
against the declared status — the antibody for the recurring disease class
"edges die silently" (W55/W62/W64/W67/W70/W71 family).

Classification per edge:
  CONFIRMED   probe outcome matches declared status
  REGRESSED   declared healthy (ALIVE/ARMED/GATING/...) but probe FAILED  ← the alarm
  RECOVERED   declared dead-ish but probe PASSED (census is stale — update it)
  STATIC      no probe declared/derivable (documentation-only edge)
  SKIPPED     probe targets an unreachable machine

Probe spec (optional per edge):
  probe:
    type: cmd | file_exists | file_age_max_h | grep | launchd_label | md5_pair
    via: local | ssh:<host>          # default local
    # type=cmd:           cmd: "...", expect_regex: "..." (optional)
    # type=file_exists:   path: "~/..."
    # type=file_age_max_h: path: "~/...", max_age_h: 26
    # type=grep:          path: "...", pattern: "..."
    # type=launchd_label: label defaults to edge id; bad_exit_ok: false
    # type=md5_pair:      path_a: "...", path_b: "..." (DRIFTED edges: pass = still drifted? no:
    #                     pass = files identical; declare expected: identical|drifted)

Kind-default probes (when no explicit probe):
  kind=launchd on the current/reachable machine → launchd_label(id)

Usage:
  apps/backend-rag/.venv/bin/python scripts/verify_connectome.py [--json out.json]
      [--edges-dir docs/connectome/edges] [--only-kind launchd] [--machine auto]
      [--no-ssh]

Exit codes: 0 = no REGRESSED · 1 = at least one REGRESSED · 2 = loader error.

Healthy-declared statuses: ALIVE, ARMED, GATING, SCHEDULED_ALIVE, IDENTICAL,
ALIVE-ACTIVE, ALIVE (mechanism), RUN_ONLY. Everything else counts as dead-ish
for RECOVERED detection. Substring match on the first token before whitespace.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("verify_connectome")

HEALTHY_PREFIXES = (
    "ALIVE",
    "ARMED",
    "GATING",
    "SCHEDULED_ALIVE",
    "IDENTICAL",
    "RUN_ONLY",
    "OK",
)

SSH_HOSTS: dict[str, str] = {
    # logical machine -> ssh alias (LAN-first: Tailscale degrades silently)
    "pro": "pro-lan",
}

PROBE_TIMEOUT_S = 30


def detect_machine() -> str:
    user = getpass.getuser()
    host = socket.gethostname().lower()
    if user == "balizero":
        return "m5"
    if "mini" in host:
        return "mini"
    if user == "nuzantara":
        return "pro"
    return "unknown"


def is_healthy(declared: str) -> bool:
    head = (declared or "").strip().upper()
    return any(head.startswith(p) for p in HEALTHY_PREFIXES)


LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def plist_intentionally_disabled(label: str) -> str | None:
    """If a LaunchAgent plist for `label` exists ONLY in a disabled/renamed form
    (e.g. *.plist.disabled-W81-*, *.disabled-*), the edge is a deliberate firebreak,
    not a regression. Returns the disabled filename if so, else None.

    An active plist == exactly '<label>.plist'. Anything else carrying the label as a
    prefix (disabled-*, superseded-*, .bak) is an intentional non-arming. An
    active-but-dead plist still has '<label>.plist' present → returns None → it still
    REGRESSES (a genuine silent death is never masked).
    """
    if not label.startswith("com.") or not LAUNCHAGENTS_DIR.is_dir():
        return None
    if (LAUNCHAGENTS_DIR / f"{label}.plist").exists():
        return None
    for f in LAUNCHAGENTS_DIR.glob(f"{label}.plist.*"):
        if "disabled" in f.name or "superseded" in f.name or f.name.endswith(".bak"):
            return f.name
    return None


@dataclass
class ProbeResult:
    ok: bool
    detail: str = ""


@dataclass
class EdgeReport:
    edge_id: str
    kind: str
    machine: str
    declared: str
    verdict: str
    detail: str = ""
    source_file: str = ""


def _run(cmd: str, via: str, no_ssh: bool) -> ProbeResult:
    if via.startswith("ssh:"):
        if no_ssh:
            return ProbeResult(False, "ssh disabled (--no-ssh)")
        host = via.split(":", 1)[1]
        full = ["ssh", "-o", "ConnectTimeout=8", host, cmd]
    else:
        full = ["/bin/bash", "-lc", cmd]
    try:
        proc = subprocess.run(
            full, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(False, f"timeout {PROBE_TIMEOUT_S}s")
    except OSError as exc:
        return ProbeResult(False, f"spawn error: {exc}")
    out = (proc.stdout or "") + (proc.stderr or "")
    return ProbeResult(proc.returncode == 0, out.strip()[:300])


def _expand(path: str, via: str) -> str:
    # ~ expansion must happen on the TARGET machine for ssh probes
    return os.path.expanduser(path) if via == "local" else path


def _normalize_via(via: str, this_machine: str) -> str:
    """An explicit ssh:<alias> that points at THIS machine must run locally.

    The alias only resolves from OTHER machines (e.g. pro-lan exists on M5,
    not on the Pro itself) — without this, a Pro-side cron self-ssh-fails
    every pro-edge into a false REGRESSED.
    """
    if via.startswith("ssh:") and SSH_HOSTS.get(this_machine) == via.split(":", 1)[1]:
        return "local"
    return via


def run_probe(edge: dict[str, Any], no_ssh: bool, this_machine: str) -> ProbeResult | None:
    """Return ProbeResult, or None if the edge has no runnable probe."""
    probe = edge.get("probe")
    kind = edge.get("kind", "")
    machine = str(edge.get("machine", "")).lower()

    # Kind-default probe: launchd label liveness
    if probe is None and kind == "launchd":
        label = edge.get("id", "")
        if not label.startswith("com."):
            return None
        probe = {"type": "launchd_label", "label": label}
        if machine and machine != this_machine:
            if machine in SSH_HOSTS:
                probe["via"] = f"ssh:{SSH_HOSTS[machine]}"
            else:
                return ProbeResult(False, f"machine {machine} unreachable (no ssh map)")

    if probe is None:
        return None

    via = _normalize_via(probe.get("via", "local"), this_machine)
    ptype = probe.get("type", "cmd")

    if ptype == "cmd":
        res = _run(probe["cmd"], via, no_ssh)
        if res.ok and probe.get("expect_regex"):
            if not re.search(probe["expect_regex"], res.detail, re.MULTILINE):
                return ProbeResult(False, f"regex miss: {res.detail[:120]}")
        return res

    if ptype == "file_exists":
        path = probe["path"]
        if via == "local":
            ok = Path(_expand(path, via)).exists()
            return ProbeResult(ok, path if ok else f"ENOENT {path}")
        return _run(f"test -e {shlex.quote(path)}", via, no_ssh)

    if ptype == "file_age_max_h":
        path, max_h = probe["path"], float(probe.get("max_age_h", 26))
        if via == "local":
            p = Path(_expand(path, via))
            if not p.exists():
                return ProbeResult(False, f"ENOENT {path}")
            age_h = (time.time() - p.stat().st_mtime) / 3600
            return ProbeResult(age_h <= max_h, f"age {age_h:.1f}h (max {max_h}h)")
        cmd = (
            f'python3 -c "import os,time,sys;'
            f"p={path!r};"
            f's=os.stat(os.path.expanduser(p));'
            f'a=(time.time()-s.st_mtime)/3600;'
            f'print(f\'age {{a:.1f}}h\');'
            f'sys.exit(0 if a<={max_h} else 1)"'
        )
        return _run(cmd, via, no_ssh)

    if ptype == "grep":
        path, pattern = probe["path"], probe["pattern"]
        return _run(f"grep -qE {shlex.quote(pattern)} {shlex.quote(path)}", via, no_ssh)

    if ptype == "launchd_label":
        label = probe.get("label", edge.get("id", ""))
        res = _run(f"launchctl list | grep -F {shlex.quote(label)}", via, no_ssh)
        if not res.ok:
            return ProbeResult(False, f"label not loaded: {label}")
        if not probe.get("bad_exit_ok", True):
            # column 2 of launchctl list = last exit status
            m = re.search(r"^\S+\s+(-?\d+)\s", res.detail)
            if m and m.group(1) not in ("0", "-"):
                return ProbeResult(False, f"last exit {m.group(1)}")
        return res

    if ptype == "md5_pair":
        pa, pb = probe["path_a"], probe["path_b"]
        expected = probe.get("expected", "identical")

        def _md5(path: str, pvia: str) -> str | None:
            if pvia == "local":
                fp = Path(_expand(path, "local"))
                if not fp.exists():
                    return None
                return hashlib.md5(fp.read_bytes()).hexdigest()
            r = _run(f"md5 -q {shlex.quote(path)}", pvia, no_ssh)
            return r.detail.split()[0] if r.ok and r.detail else None

        via_a = _normalize_via(probe.get("via_a", via), this_machine)
        via_b = _normalize_via(probe.get("via_b", via), this_machine)
        ha, hb = _md5(pa, via_a), _md5(pb, via_b)
        if ha is None or hb is None:
            return ProbeResult(False, f"missing copy a={ha is not None} b={hb is not None}")
        same = ha == hb
        ok = same if expected == "identical" else not same
        return ProbeResult(ok, "identical" if same else f"DRIFT {ha[:8]}≠{hb[:8]}")

    return ProbeResult(False, f"unknown probe type {ptype}")


def load_edges(edges_dir: Path) -> list[tuple[dict[str, Any], str]]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        logger.error("PyYAML required — run under apps/backend-rag/.venv")
        sys.exit(2)
    out: list[tuple[dict[str, Any], str]] = []
    for f in sorted(edges_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.error("YAML parse failure in %s: %s", f.name, exc)
            sys.exit(2)
        for edge in doc.get("edges", []):
            if isinstance(edge, dict) and edge.get("id"):
                out.append((edge, f.name))
    return out


def ssh_reachable(no_ssh: bool) -> set[str]:
    if no_ssh:
        return set()
    reachable = set()
    for machine, alias in SSH_HOSTS.items():
        r = _run("true", f"ssh:{alias}", no_ssh=False)
        if r.ok:
            reachable.add(machine)
    return reachable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--edges-dir", default="docs/connectome/edges")
    parser.add_argument("--json", dest="json_out", default=None)
    parser.add_argument("--only-kind", default=None)
    parser.add_argument("--machine", default="auto")
    parser.add_argument("--no-ssh", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    this_machine = detect_machine() if args.machine == "auto" else args.machine
    edges_dir = Path(args.edges_dir)
    if not edges_dir.is_dir():
        logger.error("edges dir not found: %s", edges_dir)
        return 2

    edges = load_edges(edges_dir)
    reachable = ssh_reachable(args.no_ssh)
    logger.info(
        "machine=%s edges=%d ssh_reachable=%s", this_machine, len(edges), sorted(reachable)
    )

    reports: list[EdgeReport] = []
    for edge, src in edges:
        if args.only_kind and edge.get("kind") != args.only_kind:
            continue
        declared = str(edge.get("status", "UNKNOWN"))
        machine = str(edge.get("machine", "")).lower()

        # Skip probes that need an unreachable remote machine
        needs_remote = machine not in ("", this_machine, "github", "cloud", "fly")
        if needs_remote and machine not in reachable and machine != this_machine:
            probe = edge.get("probe")
            derivable = probe is not None or edge.get("kind") == "launchd"
            if derivable:
                reports.append(
                    EdgeReport(edge["id"], edge.get("kind", ""), machine, declared,
                               "SKIPPED", f"{machine} unreachable", src)
                )
                continue

        result = run_probe(edge, args.no_ssh, this_machine)
        if result is None:
            reports.append(
                EdgeReport(edge["id"], edge.get("kind", ""), machine, declared,
                           "STATIC", "", src)
            )
            continue

        healthy = is_healthy(declared)
        if result.ok and healthy:
            verdict = "CONFIRMED"
        elif result.ok and not healthy:
            verdict = "RECOVERED"
        elif not result.ok and healthy:
            # Before calling a failed-probe healthy edge REGRESSED, distinguish a
            # deliberate firebreak (plist intentionally renamed *.disabled-*) and a
            # completed one-shot (its sentinel exists on disk) from a true silent
            # death — both are "Esiste≠Armato" (#2): census says ALIVE but the
            # activation state on disk says intentionally-not-armed.
            disabled_as = (
                plist_intentionally_disabled(edge["id"])
                if (machine in ("", this_machine) and edge.get("kind") == "launchd")
                else None
            )
            sentinel = edge.get("oneshot_sentinel")
            sentinel_present = bool(
                sentinel and Path(os.path.expanduser(str(sentinel))).exists()
            )
            if disabled_as:
                verdict = "DISABLED"
                result = ProbeResult(False, f"intentional firebreak: {disabled_as}")
            elif sentinel_present:
                verdict = "COMPLETED"
                result = ProbeResult(False, f"one-shot done: sentinel {sentinel}")
            else:
                verdict = "REGRESSED"
        else:
            verdict = "CONFIRMED"  # declared dead, still dead
        reports.append(
            EdgeReport(edge["id"], edge.get("kind", ""), machine, declared,
                       verdict, result.detail, src)
        )

    counts: dict[str, int] = {}
    for r in reports:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1

    regressed = [r for r in reports if r.verdict == "REGRESSED"]
    recovered = [r for r in reports if r.verdict == "RECOVERED"]

    logger.info("verdicts: %s", counts)
    for r in regressed:
        logger.warning("REGRESSED %-50s [%s/%s] %s", r.edge_id, r.kind, r.machine, r.detail)
    for r in recovered:
        logger.info("RECOVERED %-50s [%s/%s] — update census status", r.edge_id, r.kind, r.machine)

    if args.json_out:
        payload = {
            "ts": time.time(),
            "machine": this_machine,
            "counts": counts,
            "reports": [r.__dict__ for r in reports],
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=1))
        logger.info("json written: %s", args.json_out)

    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
