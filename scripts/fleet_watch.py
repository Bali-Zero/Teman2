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
- dark ≥ DARK_AFTER_S (default 1800s) → first p0 for the dark-transition
- then RE-ESCALATION on a widening ladder (6h, 24h, daily thereafter).
  Genesis 2026-08-17: the Mini was dark 2026-08-14→17. fleet_watch alerted
  correctly at minute 30 and then logged the dark for 236762s (~65h) in
  silence, because one bool said "already alerted". A single message that
  is missed makes a three-day-dead node indistinguishable from a recovered
  one — the outage stops being reported the moment it stops being news.
  State carries the stage reached, so a skipped ladder rung (watcher itself
  down) collapses into ONE message for the CURRENT stage, never a burst.
  Dedup keys are per-stage, otherwise the gateway's own 6h dedup — the
  second belt against spam — would swallow every re-alert.
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


def _ladder() -> tuple[int, ...]:
    raw = os.environ.get("FLEET_WATCH_REALERT_LADDER_S", "21600,86400")
    return tuple(sorted(int(x) for x in raw.split(",") if x.strip()))


def _realert_period() -> int:
    return int(os.environ.get("FLEET_WATCH_REALERT_PERIOD_S", "86400"))

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


def due_alert_stage(dark_for: float) -> int:
    """How many p0s SHOULD have been sent by now for a dark of this length.

    0 = below threshold, 1 = the transition alert, 2+ = re-escalations.
    Monotonic in ``dark_for`` by construction: the caller compares it to the
    stage already sent, so an unsent rung is never replayed twice and a
    skipped one collapses to a single current-stage message.
    """
    if dark_for < DARK_AFTER_S:
        return 0
    stage = 1
    for rung in _ladder():
        if dark_for >= rung:
            stage += 1
    period = _realert_period()
    if period > 0 and dark_for >= period:
        stage += int((dark_for - period) // period)
    return stage


def _sent_stage(entry: dict) -> int:
    """Stage already delivered, tolerating state files written before this."""
    raw = entry.get("alert_stage")
    if isinstance(raw, int) and raw >= 0:
        return raw
    return 1 if entry.get("alerted") else 0


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
            name,
            {
                "dark_since": None,
                "alerted": False,
                "alert_stage": 0,
                "last_ok": None,
            },
        )
        if not signals:
            print(f"fleet_watch: {name} UNPROBEABLE (no signal ran)")
            continue
        if any(signals):
            if _sent_stage(entry) > 0:
                outcome = notify(
                    "digest",
                    f"fleet:{name}-recovered:{day}",
                    f"fleet-watch: {name} is BACK ONLINE "
                    f"(dark since {entry['dark_since']}, seen by "
                    f"{socket.gethostname().split('.')[0]}).",
                )
                print(f"fleet_watch: {name} recovered -> digest ({outcome})")
            entry.update(
                {
                    "dark_since": None,
                    "alerted": False,
                    "alert_stage": 0,
                    "last_ok": now,
                }
            )
            continue
        # both signals explicitly failed → dark
        if entry["dark_since"] is None:
            entry["dark_since"] = now
        dark_for = now - entry["dark_since"]
        due = due_alert_stage(dark_for)
        sent = _sent_stage(entry)
        if due > sent:
            mins = int(dark_for // 60)
            still = "" if sent == 0 else "STILL "
            outcome = notify(
                "p0",
                f"fleet:{name}-dark:{day}:s{due}",
                f"P0 fleet-watch: {name} is {still}DARK — Tailscale offline "
                f"AND ssh unreachable for {mins}m (watched from "
                f"{socket.gethostname().split('.')[0]}). Its own watchdogs "
                f"die with it: this is the only alarm. Needs power/network "
                f"check on site.",
            )
            entry["alert_stage"] = due
            entry["alerted"] = True
            print(f"fleet_watch: {name} DARK {mins}m -> p0 stage {due} ({outcome})")
        else:
            print(f"fleet_watch: {name} dark {int(dark_for)}s (threshold {DARK_AFTER_S}s)")
    return state, probes_run


def _dispatch_sos_probe() -> None:
    """Second carrier for the 2026-08-11 Mini inbound-outage probe.

    Mini-Pro2 has been unreachable since 2026-08-10 ~14:00: every INBOUND
    connection completes the handshake and is reset ~250 ms later, while
    outbound is healthy, a power-cycle changed nothing, and nobody can reach
    the machine's keyboard. The probe normally rides the Mini's 5-minute
    git-pull — but that path only works if the pull script's copy under $HOME
    has self-updated from the repo, and silently-diverged HOME copies are a
    standing failure mode in this fleet. fleet_watch is executed straight out
    of the repo checkout, so it is an INDEPENDENT carrier: whichever fires
    first delivers, and the probe's own marker keeps the report single.

    The probe is node-guarded to mini-pro2 and self-expiring, so this is a
    no-op everywhere else. Fail-open by construction: fleet_watch's verdict
    must never depend on it. Remove with the probe once the Mini is back.
    """
    probe = REPO_ROOT / "scripts" / "mini" / "mini_sos_report.sh"
    if not probe.is_file():
        return
    try:
        subprocess.run(
            ["/bin/bash", str(probe)],
            timeout=170,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001 — a rescue probe may never break its carrier
        pass


def main() -> int:
    if os.environ.get("FLEET_WATCH_ENABLED", "true").lower() == "false":
        print("fleet_watch: disabled by kill switch")
        return 0
    _dispatch_sos_probe()
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
