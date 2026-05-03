"""Telegram alerter with md5 dedup (same pattern as fly-health-check.sh)."""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

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


def send_alert(message: str, level: str = "INFO") -> bool:
    """
    Send Telegram message with dedup. Returns True if sent, False if deduped or failed.
    level: INFO | WARNING | CRITICAL | DEADMAN
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", "1125336968"))

    if not bot_token:
        print(f"[ALERT-NO-TOKEN] {level}: {message[:100]}")
        return False

    # Dedup key = md5 of message content (not timestamp)
    dedup_key = hashlib.md5(message.encode()).hexdigest()
    if _is_duplicate(dedup_key):
        return False

    prefix = {"INFO": "🔧", "WARNING": "🟡", "CRITICAL": "🔴", "DEADMAN": "⚫"}.get(level, "ℹ️")
    # Strip Markdown formatting — use plain text to avoid 400 errors from underscores/special chars
    clean_message = message.replace("*", "").replace("`", "").replace("_", "-")
    full_message = f"{prefix} Sentinel | {clean_message}"

    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": full_message}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=data,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                _mark_sent(dedup_key)
                return True
    except Exception as e:
        print(f"[ALERT-FAILED] {e}")
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
