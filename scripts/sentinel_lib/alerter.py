"""Telegram alerter with md5 dedup — routes through the notification gateway.

Since 2026-07-07 (cohort-2, PR #2067 follow-up) the network send is delegated
to scripts/tg_notify.py: CRITICAL/DEADMAN → tier p0 (immediate, daily budget),
WARNING/INFO → tier digest (grouped 2×/day). The gateway owns token resolution
(env → secrets file → ssh relay) and its own 6h dedup; the local md5 dedup here
stays as a 1h fast-path so callers keep the sent/deduped return contract.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

DEDUP_FILE = os.path.expanduser("~/.agent/decisions/alert_dedup.json")
DEDUP_WINDOW_S = 3600  # 1 hour
ESCALATION_COOLDOWN_S = 14400  # D1.2: 4h per-job cooldown to prevent alert storms
_ESCALATION_STATE_FILE = os.path.expanduser("~/.agent/decisions/escalation_cooldown.json")


def _load_dedup() -> dict:
    try:
        return json.loads(open(DEDUP_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_dedup(data: dict) -> None:
    with open(DEDUP_FILE, "w") as f:
        json.dump(data, f)


def _is_duplicate(key: str) -> bool:
    data = _load_dedup()
    entry = data.get(key)
    if not entry:
        return False
    return (time.time() - entry["ts"]) < DEDUP_WINDOW_S


def _mark_sent(key: str) -> None:
    data = _load_dedup()
    data[key] = {"ts": time.time()}
    # Prune old entries
    data = {k: v for k, v in data.items() if (time.time() - v["ts"]) < DEDUP_WINDOW_S * 24}
    _save_dedup(data)


def _load_escalation_state() -> dict:
    try:
        return json.loads(open(_ESCALATION_STATE_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_escalation_state(data: dict) -> None:
    with open(_ESCALATION_STATE_FILE, "w") as f:
        json.dump(data, f)


def check_escalation_cooldown(job_id: str) -> bool:
    """D1.2: Returns True if alert for this job is on cooldown (should NOT send)."""
    data = _load_escalation_state()
    sent_at = data.get(job_id, {}).get("escalation_sent_at", 0)
    return (time.time() - sent_at) < ESCALATION_COOLDOWN_S


def mark_escalation_sent(job_id: str) -> None:
    """D1.2: Record that an escalation alert was just sent for this job."""
    data = _load_escalation_state()
    # Prune entries older than 7 days
    cutoff = time.time() - 7 * 86400
    data = {k: v for k, v in data.items() if v.get("escalation_sent_at", 0) > cutoff}
    data[job_id] = {"escalation_sent_at": time.time(), "_writer": "alerter"}
    _save_escalation_state(data)


def _gateway_script() -> str:
    """Locate scripts/tg_notify.py relative to this file, NUZANTARA_ROOT fallback."""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tg_notify.py")
    if os.path.isfile(here):
        return here
    root = os.environ.get("NUZANTARA_ROOT", os.path.expanduser("~/Desktop/nuzantara"))
    return os.path.join(root, "scripts", "tg_notify.py")


def send_alert(message: str, level: str = "INFO") -> bool:
    """
    Send Telegram alert via the notification gateway (tg_notify.py), with dedup.
    Returns True if the gateway accepted it (sent / spooled for the digest),
    False if deduped or failed. level: INFO | WARNING | CRITICAL | DEADMAN.

    Tier mapping: CRITICAL/DEADMAN → p0 (immediate, daily budget);
    WARNING/INFO → digest (ONE grouped message 2×/day).
    """
    # Dedup key = md5 of message content (not timestamp). Local 1h fast-path
    # keeps the historical return contract; the gateway adds its own 6h window.
    dedup_key = hashlib.md5(message.encode()).hexdigest()
    if _is_duplicate(dedup_key):
        return False

    prefix = {"INFO": "🔧", "WARNING": "🟡", "CRITICAL": "🔴", "DEADMAN": "⚫"}.get(level, "ℹ️")
    # Strip Markdown formatting — gateway sends plain text
    clean_message = message.replace("*", "").replace("`", "").replace("_", "-")
    full_message = f"{prefix} Sentinel | {clean_message}"
    tier = "p0" if level in ("CRITICAL", "DEADMAN") else "digest"

    # W55 retry lives inside the gateway now (spool-on-failure is strictly
    # better than 3 urllib attempts: a lost send resurfaces in the next digest).
    try:
        proc = subprocess.run(
            [sys.executable, _gateway_script(),
             "--tier", tier, "--source", "sentinel",
             "--dedup-key", f"sentinel:{dedup_key}", "--", full_message],
            capture_output=True, text=True, timeout=90,
        )
        # tg_notify prints "tg_notify: <outcome>" on STDERR (stdout stays clean
        # for callers) — scan both streams, last line wins.
        raw = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        outcome = ""
        for line in raw.splitlines():
            if line.startswith("tg_notify:"):
                outcome = line.split(":", 1)[1].strip().split(" ")[0]
        if outcome in ("sent", "spooled", "logged", "p0_overflow_spooled", "p0_unsent_spooled"):
            _mark_sent(dedup_key)
            return True
        if outcome == "deduped":
            return False
        print(f"[ALERT-FAILED] gateway outcome={outcome or 'empty'} rc={proc.returncode} err={(proc.stderr or '')[:200]}")
        return False
    except Exception as e:
        print(f"[ALERT-FAILED] gateway unreachable: {type(e).__name__}: {e}")
        return False


def send_daily_report(fleet_status: dict) -> None:
    """Send daily fleet health summary."""
    healthy = sum(1 for j in fleet_status.values() if j.get("status") == "ok")
    total = len(fleet_status)
    stale = [j for j, s in fleet_status.items() if s.get("status") == "stale"]
    failed = [j for j, s in fleet_status.items() if s.get("status") == "failed"]

    lines = [f"🤖 *Fleet Status* — {total} automations"]
    lines.append(f"✅ {healthy}/{total} healthy")
    if stale:
        lines.append(f"⚠️ Stale: {', '.join(stale)}")
    if failed:
        lines.append(f"🔴 Failed: {', '.join(failed)}")

    send_alert("\n".join(lines), level="INFO")
