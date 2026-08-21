#!/usr/bin/env python3
"""check_flowkit_tunnel.py — liveness probe for the FlowKit SSH tunnel
(launchd job `com.balizero.flowkit-pro-tunnel`, M5-only: `ssh -N -T
-L 127.0.0.1:8100:127.0.0.1:8100 -L 127.0.0.1:9222:127.0.0.1:9222 pro`).

THE DISEASE IT KILLS (scar family #2, Esiste!=Armato): the launchd job existed
and even self-recovered on its own (KeepAlive + ThrottleInterval=10s correctly
retry an ssh tunnel through Tailscale flaps -- family #8 network-flap, not a
KeepAlive misconfig), but NOTHING watched it. Its stderr log accumulated 800+
"Operation timed out" lines across 5+ days (born 2026-08-15 04:25, last
failure 2026-08-21 00:55) with zero heartbeat sidecar, zero proprioception
registry entry, zero alert anywhere in the repo -- the only reason anyone
noticed was a manual `launchctl list` during an unrelated dispatch.

`launchctl list`'s own STATUS column is itself a trap: it prints the LAST
exit code even while the job is CURRENTLY RUNNING (measured live 2026-08-21:
PID alive 2h20m, tunnel forwarding real HTTP traffic, `launchctl list` still
read "255" from the prior failed attempt). This script never trusts that
column -- it judges a REAL process (`ps -p <pid>`) AND a REAL HTTP reply
through the forwarded port (scar W104: judge the reply, never the exit code
or PID-presence alone).

WR2 image-gen degrades gracefully when this tunnel is down
(WR2_IMAGE_BACKEND default "auto" silently falls back to Playwright --
scripts/wr2_image_generator.py) -- DOWN here is a cost/latency finding
(FlowKit ~5-15s/image vs Playwright's 30-90s), never a data-loss one.

Blind-scan guard (W84 "green-but-dead"): a run on a machine that has never
heard of this launchd job is NOT_CONFIGURED, not "clean" -- distinct from
DOWN (configured but unreachable). Exit 0 either way (this organ is M5-only
by design; NOT_CONFIGURED elsewhere is expected, not an alarm), but the JSON
`status` field always distinguishes the two.

Usage:
    python3 scripts/check_flowkit_tunnel.py            # human line, writes heartbeat
    python3 scripts/check_flowkit_tunnel.py --json      # machine-readable
    python3 scripts/check_flowkit_tunnel.py --quiet     # one summary line
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

LABEL = "com.balizero.flowkit-pro-tunnel"
DEFAULT_PROBE_URL = "http://127.0.0.1:8100/"
DEFAULT_TIMEOUT_S = 3.0
HEARTBEAT_DIR = Path.home() / ".organism" / "last_seen"

LIVE = "LIVE"
DOWN = "DOWN"
NOT_CONFIGURED = "NOT_CONFIGURED"


def machine_label() -> str:
    """Mirrors organism_stale_detector._machine_label / arsenal_probe.machine_label
    (small, deliberately duplicated -- these sibling receptors already carry
    their own copy each rather than a cross-module import, scripts/ is not a
    package)."""
    host = socket.gethostname().split(".")[0].lower()
    if "air-m5" in host:
        return "m5"
    if "mini" in host:
        return "mini"
    if host == "nuzantara":
        return "pro"
    return host


def plist_path(label: str = LABEL) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def _launchctl_pid(
    label: str,
    run: Optional[Callable[[list[str]], subprocess.CompletedProcess]] = None,
) -> Optional[int]:
    """Returns the PID launchd currently reports for `label`, or None if not
    running / not loaded. Never trusts the STATUS column (see module
    docstring) -- only the PID column, which ps then independently verifies."""
    run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=10))
    try:
        res = run(["launchctl", "list"])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2] == label:
            pid_str = parts[0].strip()
            if pid_str.isdigit():
                return int(pid_str)
            return None
    return None


def _pid_alive(
    pid: int,
    run: Optional[Callable[[list[str]], subprocess.CompletedProcess]] = None,
) -> bool:
    run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=5))
    try:
        res = run(["ps", "-p", str(pid)])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    return res.returncode == 0


def _http_probe(
    url: str,
    timeout: float,
    fetch: Optional[Callable[[str, float], tuple[Optional[int], str]]] = None,
) -> tuple[bool, str]:
    """Any HTTP response (even a 404) proves the tunnel forwards real bytes
    end-to-end. Only a connection-level failure (refused/timeout/DNS) is DOWN
    -- this is the same "judge the reply" contract arsenal_probe.py uses."""
    def _default(u: str, t: float) -> tuple[Optional[int], str]:
        req = urllib.request.Request(u, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=t) as resp:
                return resp.status, f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            return e.code, f"HTTP {e.code}"  # a real HTTP error status IS a live reply
        except urllib.error.URLError as e:
            return None, f"{type(e).__name__}: {e.reason}"
        except TimeoutError:
            return None, "timed out"
        except Exception as e:  # a probe must never crash the whole run
            return None, f"{type(e).__name__}: {e}"

    fetch = fetch or _default
    status, evidence = fetch(url, timeout)
    return status is not None, evidence


def check(
    label: str = LABEL,
    probe_url: str = DEFAULT_PROBE_URL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    plist_exists: Optional[Callable[[], bool]] = None,
    launchctl_pid_fn: Callable[[str], Optional[int]] = _launchctl_pid,
    pid_alive_fn: Callable[[int], bool] = _pid_alive,
    http_probe_fn: Callable[[str, float], tuple[bool, str]] = _http_probe,
) -> dict:
    """Pure-ish (all IO injectable) so tests never touch a real launchd/socket."""
    plist_exists = plist_exists or (lambda: plist_path(label).is_file())
    if not plist_exists():
        return {
            "organ": "flowkit_tunnel",
            "status": NOT_CONFIGURED,
            "healthy": True,  # not an alarm -- this machine doesn't run this job
            "evidence": f"{plist_path(label)} not present -- this machine has no flowkit tunnel job",
        }

    pid = launchctl_pid_fn(label)
    if pid is None:
        return {
            "organ": "flowkit_tunnel",
            "status": DOWN,
            "healthy": False,
            "evidence": "launchd job not running (no PID in `launchctl list`)",
        }
    if not pid_alive_fn(pid):
        return {
            "organ": "flowkit_tunnel",
            "status": DOWN,
            "healthy": False,
            "evidence": f"launchctl reports PID {pid} but `ps -p {pid}` finds no live process",
        }

    reachable, http_evidence = http_probe_fn(probe_url, timeout_s)
    if not reachable:
        return {
            "organ": "flowkit_tunnel",
            "status": DOWN,
            "healthy": False,
            "evidence": f"PID {pid} alive but {probe_url} unreachable through the tunnel: {http_evidence}",
        }
    return {
        "organ": "flowkit_tunnel",
        "status": LIVE,
        "healthy": True,
        "evidence": f"PID {pid} alive, {probe_url} answered ({http_evidence})",
    }


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.rename(path)


def write_heartbeat(result: dict, machine: Optional[str] = None) -> Path:
    """Skips the write entirely for NOT_CONFIGURED (scar #2 sibling lesson,
    2026-08-21: a heartbeat file that exists everywhere-but-means-nothing on
    most machines is exactly the collocation-not-entity trap family #3
    warns about -- only write a sidecar where this organ actually runs)."""
    machine = machine or machine_label()
    path = HEARTBEAT_DIR / f"{machine}.flowkit_tunnel.json"
    if result["status"] == NOT_CONFIGURED:
        return path
    heartbeat = {
        "organ": f"{machine}.flowkit_tunnel",
        "status": "ok" if result["healthy"] else "error",
        "degraded": not result["healthy"],
        "note": result["evidence"],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _atomic_write_json(path, heartbeat)
    return path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--probe-url", default=DEFAULT_PROBE_URL)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--no-heartbeat", action="store_true", help="skip the sidecar write (testing)")
    args = ap.parse_args(argv)

    result = check(probe_url=args.probe_url, timeout_s=args.timeout)

    if not args.no_heartbeat:
        try:
            write_heartbeat(result)
        except OSError as e:
            sys.stderr.write(f"check_flowkit_tunnel: heartbeat write FAILED: {e}\n")

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif args.quiet:
        print(f"flowkit_tunnel: {result['status']}")
    else:
        print(f"flowkit_tunnel: {result['status']} -- {result['evidence']}")

    if result["status"] == NOT_CONFIGURED:
        return 0
    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
