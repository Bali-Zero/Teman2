#!/usr/bin/env python3
"""NextDNS tamper-detection + blocked-attempt digest → private Telegram.

Detects corporate devices that stopped reporting to NextDNS (profile removed
by an Admin employee) and counts blocked WhatsApp/Telegram-Web attempts per
device. Sends a digest to the operator's Telegram chat only.

Pure functions (find_silent_devices, count_blocked_attempts, build_digest) are
network-free and unit-tested. main() wires NextDNS API + registry + Telegram.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DENYLIST = {
    "web.whatsapp.com",
    "web.telegram.org",
    "webk.telegram.org",
    "webz.telegram.org",
}
THRESHOLD_DAYS = 3


def find_silent_devices(
    enrolled: list[str],
    last_seen: dict[str, datetime],
    now: datetime,
    threshold_days: int = THRESHOLD_DAYS,
) -> list[str]:
    """Return enrolled devices whose last NextDNS report is older than the
    threshold, or that never reported at all. Sorted for stable output."""
    cutoff = now - timedelta(days=threshold_days)
    silent = []
    for dev in enrolled:
        seen = last_seen.get(dev)
        if seen is None or seen < cutoff:
            silent.append(dev)
    return sorted(silent)


def count_blocked_attempts(
    logs: list[dict], denylist: set[str] = DENYLIST
) -> dict[str, int]:
    """Count blocked denylist hits per device name from NextDNS log rows."""
    counts: dict[str, int] = {}
    for row in logs:
        if row.get("status") != "blocked":
            continue
        if row.get("domain") not in denylist:
            continue
        name = (row.get("device") or {}).get("name", "unknown")
        counts[name] = counts.get(name, 0) + 1
    return counts


def build_digest(silent: list[str], blocked: dict[str, int]) -> str:
    """Render the operator Telegram digest (HTML parse mode)."""
    lines = ["🛡️ <b>NextDNS Tamper-Detection (settimanale)</b>", ""]
    if silent:
        lines.append("🚨 <b>Device SPARITI dai log (profilo rimosso?):</b>")
        lines += [f"  • <code>{d}</code>" for d in silent]
        lines.append("→ verifica + clausola contratto (rimozione = pelanggaran)")
    else:
        lines.append("✅ Tutti i device enrolled riportano. 0 silenti.")
    lines.append("")
    if blocked:
        lines.append("📵 <b>Tentativi WA/Telegram Web bloccati:</b>")
        lines += [
            f"  • {d}: {n}"
            for d, n in sorted(blocked.items(), key=lambda x: -x[1])
        ]
    else:
        lines.append("📵 0 tentativi bloccati questa settimana.")
    return "\n".join(lines)


def _load_enrolled(registry_path: str) -> list[str]:
    """Parse the device_label column from the markdown registry table."""
    devices = []
    try:
        with open(os.path.expanduser(registry_path)) as f:
            for line in f:
                line = line.strip()
                if not line.startswith("|"):
                    continue
                cols = [c.strip() for c in line.strip("|").split("|")]
                label = cols[0] if cols else ""
                if label and label.lower() not in (
                    "device_label (nextdns)",
                    "---",
                    "",
                ) and not set(label) <= {"-", " "}:
                    devices.append(label)
    except FileNotFoundError:
        pass
    return devices


def _fetch_nextdns_logs(api_key: str, profile_id: str, from_iso: str) -> list[dict]:
    url = (
        f"https://api.nextdns.io/profiles/{profile_id}/logs"
        f"?from={urllib.parse.quote(from_iso)}&limit=1000"
    )
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read()).get("data", [])


def _last_seen_from_logs(logs: list[dict]) -> dict[str, datetime]:
    seen: dict[str, datetime] = {}
    for row in logs:
        name = (row.get("device") or {}).get("name")
        ts = row.get("timestamp")
        if not name or not ts:
            continue
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if name not in seen or dt > seen[name]:
            seen[name] = dt
    return seen


def _send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "parse_mode": "HTML", "text": text}
    ).encode()
    urllib.request.urlopen(
        urllib.request.Request(url, data=data), timeout=20
    ).read()


def main() -> int:
    api_key = os.environ.get("NEXTDNS_API_KEY")
    profile_id = os.environ.get("NEXTDNS_PROFILE_ID")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    registry = os.environ.get(
        "NEXTDNS_DEVICE_REGISTRY",
        os.path.expanduser(
            "~/Desktop/nuzantara/research/hr/device-enrollment-registry.md"
        ),
    )
    if not all([api_key, profile_id, tg_token, tg_chat]):
        print(
            "[tamper-detect] missing env (NEXTDNS_*/TELEGRAM_*) — aborting",
            file=sys.stderr,
        )
        return 1

    now = datetime.now(timezone.utc)
    from_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    enrolled = _load_enrolled(registry)
    try:
        logs = _fetch_nextdns_logs(api_key, profile_id, from_iso)
    except Exception as e:  # noqa: BLE001 — never silently skip (W55/W61 lesson)
        _send_telegram(tg_token, tg_chat, f"⚠️ NextDNS tamper-detect: API error: {e}")
        return 1

    silent = find_silent_devices(enrolled, _last_seen_from_logs(logs), now=now)
    blocked = count_blocked_attempts(logs)
    _send_telegram(tg_token, tg_chat, build_digest(silent, blocked))
    print(
        f"[tamper-detect] sent: {len(silent)} silent, "
        f"{sum(blocked.values())} blocked attempts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
