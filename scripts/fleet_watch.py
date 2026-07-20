#!/usr/bin/env python3
"""fleet_watch — cross-node liveness sentinel.

Genesis: 2026-07-07, the Pro dropped off Tailscale AND the Bali LAN for 5+
hours with ZERO alarms — every watchdog lived ON the Pro (family #2: a
guardian that dies with its patient guards nothing). The Mini is the H24
survivor, so it watches the Pro. Config maps watcher-hostname → peers, so
the same script installs on any node (family #10 guard included).

Verdict per peer (structured signals, never substring — W82):
- ``tailscale status --json`` → peer ``Online`` bool (signal 1)
- ``ssh -o BatchMode=yes -o ConnectTimeout=8 <alias> true`` (signal 2)
- OK = either signal ok · DARK = both explicitly failed ·
  if NO probe machinery ran at all → exit 4 (W84: a blind sentinel must
  not report green).

Alerting (via tg gateway, never the Bot API directly):
- dark ≥ DARK_AFTER_S (default 1800s) → ONE p0 per dark-transition
  (state file remembers; the gateway's 6h dedup is the second belt)
- recovery after an alerted dark → digest event
State: ``~/.organism/fleet_watch/state.json``.

Kill switch: ``FLEET_WATCH_ENABLED=false``. Node guard: runs only when
``hostname -s`` has an entry in the peers config; otherwise graceful exit 0.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
PEERS_CONFIG = REPO_ROOT / "infra" / "fleet-watch" / "peers.json"
DARK_AFTER_S = int(os.environ.get("FLEET_WATCH_DARK_AFTER_S", "1800"))
SSH_TIMEOUT_S = 8

TAILSCALE_CANDIDATES = (
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    "/opt/homebrew/bin/tailscale",
    "/usr/local/bin/tailscale",
    "tailscale",
)

Runner = Callable[[list[str], int], "subprocess.CompletedProcess[str]"]


def _run(cmd: list[str], timeout: int) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )


def _state_dir() -> Path:
    return Path(
        os.environ.get(
            "FLEET_WATCH_STATE_DIR",
            os.path.expanduser("~/.organism/fleet_watch"),
        )
    )


def load_state(state_dir: Path) -> dict:
    try:
        return json.loads((state_dir / "state.json").read_text())
    except (OSError, ValueError):
        return {}


def save_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    tmp = state_dir / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(state_dir / "state.json")


def check_tailscale(ts_hostname: str, run: Runner = _run) -> bool | None:
    """True=online, False=offline, None=signal unavailable."""
    for exe in TAILSCALE_CANDIDATES:
        try:
            proc = run([exe, "status", "--json"], 20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            continue
        try:
            peers = json.loads(proc.stdout).get("Peer") or {}
        except ValueError:
            continue
        for peer in peers.values():
            if str(peer.get("HostName", "")).lower() == ts_hostname.lower():
                return bool(peer.get("Online"))
        return False  # authoritative status, peer not in tailnet at all
    return None


def check_ssh(alias: str, run: Runner = _run) -> bool | None:
    cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={SSH_TIMEOUT_S}",
        alias,
        "true",
    ]
    try:
        proc = run(cmd, SSH_TIMEOUT_S + 10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def notify_gateway(
    tier: str, dedup_key: str, text: str, run: Runner = _run
) -> str:
    gateway = REPO_ROOT / "scripts" / "tg_notify.py"
    if not gateway.is_file():
        gateway = Path(
            os.path.expanduser("~/nuzantara/scripts/tg_notify.py")
        )
    proc = run(
        [
            sys.executable, str(gateway),
            "--tier", tier,
            "--source", "fleet-watch",
            "--dedup-key", dedup_key,
            "--", text,
        ],
        120,
    )
    for line in reversed((proc.stderr + "\n" + proc.stdout).splitlines()):
        if line.startswith("tg_notify:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def tick(
    peers: list[dict],
    state: dict,
    now: float,
    ts_check: Callable[[str], bool | None] = check_tailscale,
    ssh_check: Callable[[str], bool | None] = check_ssh,
    notify: Callable[[str, str, str], str] = notify_gateway,
) -> tuple[dict, int]:
    """Probe every peer, mutate state, fire alerts. Returns (state, probes_run)."""
    probes_run = 0
    day = time.strftime("%Y%m%d", time.localtime(now))
    for peer in peers:
        name = peer["name"]
        ts_ok = ts_check(peer["tailscale_host"])
        ssh_ok = ssh_check(peer["ssh_alias"])
        signals = [s for s in (ts_ok, ssh_ok) if s is not None]
        probes_run += len(signals)
        entry = state.setdefault(
            name, {"dark_since": None, "alerted": False, "last_ok": None}
        )
        if not signals:
            print(f"fleet_watch: {name} UNPROBEABLE (no signal ran)")
            continue
        if any(signals):
            if entry["alerted"]:
                outcome = notify(
                    "digest",
                    f"fleet:{name}-recovered:{day}",
                    f"fleet-watch: {name} is BACK ONLINE "
                    f"(dark since {entry['dark_since']}, seen by "
                    f"{socket.gethostname().split('.')[0]}).",
                )
                print(f"fleet_watch: {name} recovered -> digest ({outcome})")
            entry.update({"dark_since": None, "alerted": False, "last_ok": now})
            continue
        # both signals explicitly failed → dark
        if entry["dark_since"] is None:
            entry["dark_since"] = now
        dark_for = now - entry["dark_since"]
        if dark_for >= DARK_AFTER_S and not entry["alerted"]:
            mins = int(dark_for // 60)
            outcome = notify(
                "p0",
                f"fleet:{name}-dark:{day}",
                f"P0 fleet-watch: {name} is DARK — Tailscale offline AND ssh "
                f"unreachable for {mins}m (watched from "
                f"{socket.gethostname().split('.')[0]}). Its own watchdogs "
                f"die with it: this is the only alarm. Needs power/network "
                f"check on site.",
            )
            entry["alerted"] = True
            print(f"fleet_watch: {name} DARK {mins}m -> p0 ({outcome})")
        else:
            print(f"fleet_watch: {name} dark {int(dark_for)}s (threshold {DARK_AFTER_S}s)")
    return state, probes_run


def main() -> int:
    if os.environ.get("FLEET_WATCH_ENABLED", "true").lower() == "false":
        print("fleet_watch: disabled by kill switch")
        return 0
    hostname = socket.gethostname().split(".")[0].lower()
    try:
        config = json.loads(PEERS_CONFIG.read_text())
    except (OSError, ValueError) as exc:
        print(f"fleet_watch: peers config unreadable: {exc}")
        return 4
    peers = config.get(hostname)
    if not peers:
        print(f"fleet_watch: no peers assigned to {hostname} — nothing to do")
        return 0
    state_dir = _state_dir()
    state = load_state(state_dir)
    state, probes_run = tick(peers, state, time.time())
    save_state(state_dir, state)
    if probes_run == 0:
        print("fleet_watch: BLIND — zero probes ran (W84), refusing green")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
