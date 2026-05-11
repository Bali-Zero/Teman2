#!/usr/bin/env python3
"""
OpenClaw → Sentinel bridge.
Reads ~/.openclaw/cron/jobs.json and writes .last.json for every job.
Run every 5 minutes via cron (same frequency as sentinel).
"""
import json
import os
import pathlib
import time

OPENCLAW_JOBS = pathlib.Path.home() / ".openclaw" / "cron" / "jobs.json"
STATE_DIR = pathlib.Path.home() / ".agent" / "decisions" / "state"

# OpenClaw schedule_seconds per job — used to set staleness context
# (sentinel uses registry for thresholds, this is just FYI in the state file)
SCHEDULE_MAP = {
    "health-check":           14400,   # 4h
    "daily-ops-autopilot":    86400,
    "compliance-autopilot":   86400,
    "practice-lifecycle-check": 86400,
    "weekly-report":          604800,
    "client-health-monitor":  86400,
    "weekly-dep-audit":       604800,
    "nightly-code-quality":   86400,
    "kbli-indexing-daily":    86400,
    "articles-indexing-daily": 86400,
    "seo-guardian-measure":   86400,
    "seo-guardian-weekly":    604800,
    "conversation-cleanup":   86400,
    "biz-orchestrator":       86400,
    "tech-orchestrator":      86400,
    "quality-orchestrator":   604800,
    "system-doctor":          86400,
    "core-guardian":          10800,   # 3h
    "seo-guardian-observe":   86400,
}


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(OPENCLAW_JOBS.read_text())
    except Exception as e:
        print(f"[openclaw-bridge] Cannot read jobs.json: {e}")
        return

    jobs = data.get("jobs", [])
    written = 0

    for job in jobs:
        name = job.get("name", "")
        if not name:
            continue

        state = job.get("state", {})
        last_run_ms = state.get("lastRunAtMs")
        last_status = state.get("lastStatus", "unknown")
        consecutive_errors = state.get("consecutiveErrors", 0)

        # Convert lastRunAtMs (ms) to unix ts (s)
        ts = int(last_run_ms / 1000) if last_run_ms else int(time.time())

        # Map OpenClaw status → sentinel status.
        # Bug fix 2026-05-09: "unknown" lastStatus + consecutiveErrors==0 was
        # being mapped to "failed", flooding cell.organism with false-red
        # signals for jobs that simply hadn't completed yet (or whose
        # producer doesn't write final status). Now we only mark "failed"
        # when there is real evidence of failure (consecutiveErrors>0 OR
        # explicit fail/error/timeout status).
        if last_status in ("ok", "delivered"):
            sentinel_status = "ok"
        elif consecutive_errors > 0 or last_status in ("failed", "error", "timeout"):
            sentinel_status = "failed"
        else:
            # last_status is "unknown" / "" / "running" / etc with zero
            # consecutive errors — no failure signal. Mark "ok" so the
            # downstream sensor doesn't flood red on a benign state.
            sentinel_status = "ok"

        # Build last_error from consecutive errors
        last_error = None
        if sentinel_status == "failed":
            last_error = f"OpenClaw consecutiveErrors={consecutive_errors}, lastStatus={last_status}"

        heartbeat = {
            "job": name,
            "ts": ts,
            "status": sentinel_status,
            "host": "Nuzantara",
            "source": "openclaw-bridge",
        }
        if last_error:
            heartbeat["last_error"] = last_error
        if last_run_ms:
            heartbeat["duration_ms"] = state.get("lastDurationMs", 0)

        # Write state file (job name normalized: hyphens → underscores)
        filename = name.replace("-", "_") + ".last.json"
        (STATE_DIR / filename).write_text(json.dumps(heartbeat))
        written += 1

    print(f"[openclaw-bridge] Written {written}/{len(jobs)} state files")


if __name__ == "__main__":
    main()
