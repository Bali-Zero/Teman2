#!/usr/bin/env python3
"""
Job Health Dashboard — Aggregates cron wrapper JSONL logs + detects dead jobs.

Usage:
    python3 scripts/job_health.py                # Summary table
    python3 scripts/job_health.py --json         # JSON output (for MCP)
    python3 scripts/job_health.py --alert        # Send Telegram alert for dead/failed jobs

Reads from: ~/logs/cron/*.jsonl (cron-wrapper.sh structured output)
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

WITA = timezone(timedelta(hours=8))
CRON_LOG_DIR = Path.home() / "logs" / "cron"
SECRETS_FILE = Path.home() / ".nuzantara-secrets.env"

# Expected jobs and their max intervals (hours).
# If a job hasn't run in 2× this interval, it's considered dead.
EXPECTED_JOBS = {
    "fly-pg-backup":    {"interval_h": 28, "critical": True},
    "qdrant-snapshot":  {"interval_h": 192, "critical": True},   # weekly
    "system-doctor":    {"interval_h": 28, "critical": False},
    "rag-canary":       {"interval_h": 8, "critical": True},
    "kb-ingest":        {"interval_h": 28, "critical": False},
    "crm-automation":   {"interval_h": 28, "critical": False},
    "seo-guardian":     {"interval_h": 28, "critical": False},
    "drive-watchdog":   {"interval_h": 8, "critical": True},
    "t4-monitor":       {"interval_h": 8, "critical": False},
    "db-nlm-sync":      {"interval_h": 28, "critical": False},
}


def load_secrets() -> dict[str, str]:
    secrets = {}
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip().strip('"').strip("'")
    return secrets


def load_job_logs() -> dict[str, list[dict]]:
    """Load all JSONL log files, return {job_name: [entries]}."""
    jobs: dict[str, list[dict]] = {}
    if not CRON_LOG_DIR.exists():
        return jobs

    for f in CRON_LOG_DIR.glob("*.jsonl"):
        job_name = f.stem
        entries = []
        for line in f.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        jobs[job_name] = entries
    return jobs


def analyze_jobs(job_logs: dict[str, list[dict]]) -> list[dict]:
    """Analyze each job's health status."""
    now = time.time()
    results = []

    # Process known jobs
    all_job_names = set(EXPECTED_JOBS.keys()) | set(job_logs.keys())

    for job_name in sorted(all_job_names):
        entries = job_logs.get(job_name, [])
        config = EXPECTED_JOBS.get(job_name, {"interval_h": 36, "critical": False})

        if not entries:
            results.append({
                "job": job_name,
                "status": "missing",
                "message": "No log entries found",
                "critical": config["critical"],
                "last_run": None,
                "last_status": None,
                "last_duration": None,
                "total_runs": 0,
                "fail_rate": 0.0,
            })
            continue

        last = entries[-1]
        last_ts_str = last.get("ts", "")
        last_status = last.get("status", "unknown")
        last_exit = last.get("exit_code", -1)
        last_duration = last.get("duration_s", 0)

        # Parse timestamp
        try:
            last_dt = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
            age_h = (now - last_dt.timestamp()) / 3600
            last_run = last_dt.astimezone(WITA).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            age_h = 999
            last_run = "unknown"

        # Calculate fail rate (last 10 runs)
        recent = entries[-10:]
        failures = sum(1 for e in recent if e.get("status") != "ok")
        fail_rate = failures / len(recent) if recent else 0.0

        # Determine health status
        max_age = config["interval_h"] * 2
        if age_h > max_age:
            status = "dead"
            message = f"No run in {age_h:.0f}h (expected every {config['interval_h']}h)"
        elif last_status != "ok":
            status = "failing"
            message = f"Last run failed (exit {last_exit}, {last_duration}s)"
        elif fail_rate > 0.3:
            status = "flaky"
            message = f"Fail rate {fail_rate:.0%} in last {len(recent)} runs"
        else:
            status = "healthy"
            message = f"OK ({last_duration}s, {age_h:.1f}h ago)"

        results.append({
            "job": job_name,
            "status": status,
            "message": message,
            "critical": config["critical"],
            "last_run": last_run,
            "last_status": last_status,
            "last_duration": last_duration,
            "total_runs": len(entries),
            "fail_rate": round(fail_rate, 2),
        })

    return results


def print_table(results: list[dict]) -> None:
    """Print human-readable table."""
    icons = {"healthy": "✅", "failing": "❌", "dead": "💀", "flaky": "⚠️", "missing": "❓"}

    print(f"\n{'Job':<20} {'Status':<10} {'Last Run':<18} {'Dur':>5} {'Fail%':>6} {'Message'}")
    print("─" * 90)

    for r in results:
        icon = icons.get(r["status"], "?")
        dur = f"{r['last_duration']}s" if r["last_duration"] is not None else "—"
        fail = f"{r['fail_rate']:.0%}" if r["total_runs"] > 0 else "—"
        last = r["last_run"] or "never"
        crit = " [CRIT]" if r["critical"] and r["status"] in ("dead", "failing") else ""
        print(f"{icon} {r['job']:<18} {r['status']:<10} {last:<18} {dur:>5} {fail:>6} {r['message'][:30]}{crit}")

    # Summary
    total = len(results)
    healthy = sum(1 for r in results if r["status"] == "healthy")
    print(f"\n{healthy}/{total} healthy")


def send_alert(results: list[dict]) -> None:
    """Send Telegram alert for dead/failing critical jobs."""
    alerts = [r for r in results if r["status"] in ("dead", "failing") and r["critical"]]
    if not alerts:
        return

    secrets = load_secrets()
    token = secrets.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = secrets.get("TELEGRAM_ADMIN_CHAT_ID", secrets.get("TELEGRAM_OWNER_CHAT_ID", ""))
    if not token or not chat_id:
        print("WARN: No Telegram credentials for alerting", file=sys.stderr)
        return

    lines = ["<b>CRON HEALTH ALERT</b>", ""]
    for r in alerts:
        icon = "💀" if r["status"] == "dead" else "❌"
        lines.append(f"{icon} <b>{r['job']}</b>: {r['message'][:80]}")

    msg = "\n".join(lines)
    try:
        data = f"chat_id={chat_id}&parse_mode=HTML&text={msg}".encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"WARN: Telegram alert failed: {e}", file=sys.stderr)


def main() -> None:
    job_logs = load_job_logs()
    results = analyze_jobs(job_logs)

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)

    if "--alert" in sys.argv:
        send_alert(results)


if __name__ == "__main__":
    main()
