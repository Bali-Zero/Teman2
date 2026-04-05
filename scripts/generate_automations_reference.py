#!/usr/bin/env python3
"""
Generate docs/AUTOMATIONS_REFERENCE.md by scanning LIVE system state.

Sources (in order):
  1. crontab -l  (Pro — local)
  2. crontab -l  (Air — via SSH)
  3. launchctl list + ~/Library/LaunchAgents/*.plist  (Pro)
  4. launchctl list + ~/Library/LaunchAgents/*.plist  (Air — via SSH)
  5. Log files — last line + mtime for health status

Run:  python scripts/generate_automations_reference.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

NUZANTARA_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = NUZANTARA_ROOT / "docs" / "AUTOMATIONS_REFERENCE.md"

# D3.1 write-blocklist
WRITE_BLOCKLIST = {"CLAUDE.md", "zantara_core.py", "fly.toml", ".env", ".env.production", ".env.local"}


def _check_output_safety(path: Path) -> None:
    if path.name in WRITE_BLOCKLIST or ".env" in str(path):
        print(f"ERROR: {path} is in the doc generator write-blocklist (D3.1). Aborting.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Job:
    name: str
    machine: str  # Pro | Air
    kind: str     # cron | launchagent
    schedule: str  # human-readable schedule (e.g., "*/5 * * * *" or "RunAtLoad")
    command: str
    log_file: str = ""
    last_status: str = ""  # ✅ OK | ❌ FAIL | ⚠️ ... | ? unknown
    last_run: str = ""     # mtime of log file
    exit_code: str = ""    # for launchagents
    plist_label: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------

def _run(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def _ssh_air(cmd: str, timeout: int = 10) -> str:
    return _run(f"ssh -o ConnectTimeout=5 -o BatchMode=yes air '{cmd}'", timeout=timeout)


# ---------------------------------------------------------------------------
# Cron parser
# ---------------------------------------------------------------------------

_CRON_RE = re.compile(
    r"^(?P<schedule>[\d*/,\-]+\s+[\d*/,\-]+\s+[\d*/,\-]+\s+[\d*/,\-]+\s+[\d*/,\-]+)\s+(?P<cmd>.+)$"
)


def _parse_crontab(raw: str, machine: str) -> list[Job]:
    jobs: list[Job] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("PATH=") or line.startswith("TELEGRAM_BOT_TOKEN="):
            continue
        m = _CRON_RE.match(line)
        if not m:
            continue
        sched = m.group("schedule")
        cmd_full = m.group("cmd")

        # Extract log file from >> redirect
        log_file = ""
        log_match = re.search(r">>\s*(\S+)", cmd_full)
        if log_match:
            log_file = log_match.group(1)

        # Derive name from script path or command
        name = _derive_name(cmd_full)

        jobs.append(Job(
            name=name,
            machine=machine,
            kind="cron",
            schedule=sched,
            command=cmd_full[:120],
            log_file=log_file,
        ))
    return jobs


def _derive_name(cmd: str) -> str:
    """Extract a human-readable job name from a cron command."""
    # Special cases — commands that are not scripts
    if "touch ~/.pro_heartbeat" in cmd:
        return "pro_heartbeat"
    if "nlm_bridge.last.json" in cmd:
        return "nlm_bridge_state"
    if "cp ~/.claude/memory" in cmd:
        return "mos_backup"
    if "find ~/.claude/backups" in cmd:
        return "mos_prune_backups"
    if "sqlite3 ~/.claude/memory" in cmd and "ttl_days" in cmd:
        return "mos_ttl_cleanup"
    if "npm cache clean" in cmd:
        return "cache_cleanup"
    if "notifiers/all" in cmd:
        return "notifiers_all"
    if "notifiers/birthday" in cmd:
        return "notifiers_birthday"
    if "notifiers/welcome" in cmd:
        return "notifiers_welcome"
    if "warroom_test" in cmd:
        return "war_room_test"
    if "crontab -l | grep" in cmd:
        return "war_room_test"  # one-shot self-removing cron

    # Match script filename
    m = re.search(r"/([a-zA-Z0-9_\-]+)\.(?:sh|py)\b", cmd)
    if m:
        raw = m.group(1).replace("-", "_")
        # Strip run_ prefix for NLM scripts
        if raw.startswith("run_"):
            raw = raw[4:]
        return raw
    # Fallback: first meaningful token
    for token in cmd.split():
        if "/" in token and not token.startswith("-"):
            return Path(token).stem.replace("-", "_")
    return cmd[:30].replace(" ", "_")


# ---------------------------------------------------------------------------
# LaunchAgent parser
# ---------------------------------------------------------------------------

def _parse_launchagents_pro() -> list[Job]:
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    launchctl_raw = _run("launchctl list 2>/dev/null")
    running = _parse_launchctl(launchctl_raw)

    jobs: list[Job] = []
    # Filter to our plists only
    our_prefixes = ("ai.openclaw.", "com.balizero.", "com.nuzantara.", "com.cell.", "com.claude-max-api")
    for plist_file in sorted(plist_dir.glob("*.plist")):
        label = plist_file.stem
        if not any(label.startswith(p) for p in our_prefixes):
            continue
        info = running.get(label, {})
        pid = info.get("pid", "-")
        ec = info.get("exit_code", "?")

        if pid not in ("-", "0", ""):
            status = f"🔄 Running (PID={pid})"
        elif str(ec) == "0":
            status = "✅ OK"
        elif label in running:
            status = f"❌ FAILED (exit={ec})"
        else:
            status = "⚠️ NOT LOADED"

        jobs.append(Job(
            name=label.replace(".", "_"),
            machine="Pro",
            kind="launchagent",
            schedule="RunAtLoad",
            command=label,
            plist_label=label,
            last_status=status,
            exit_code=str(ec),
        ))
    return jobs


def _parse_launchagents_air() -> list[Job]:
    launchctl_raw = _ssh_air("launchctl list 2>/dev/null")
    plist_list = _ssh_air("ls ~/Library/LaunchAgents/*.plist 2>/dev/null")
    running = _parse_launchctl(launchctl_raw)

    our_prefixes = ("ai.openclaw.", "com.balizero.", "com.nuzantara.", "com.cell.",
                    "com.claude-max-api", "com.openclaw.", "com.user.", "homebrew.mxcl.")
    jobs: list[Job] = []
    for plist_path in plist_list.splitlines():
        plist_path = plist_path.strip()
        if not plist_path:
            continue
        label = Path(plist_path).stem
        if not any(label.startswith(p) for p in our_prefixes):
            continue
        info = running.get(label, {})
        pid = info.get("pid", "-")
        ec = info.get("exit_code", "?")

        if pid not in ("-", "0", ""):
            status = f"🔄 Running (PID={pid})"
        elif str(ec) == "0":
            status = "✅ OK"
        elif label in running:
            status = f"❌ FAILED (exit={ec})"
        else:
            status = "⚠️ NOT LOADED"

        jobs.append(Job(
            name=label.replace(".", "_"),
            machine="Air",
            kind="launchagent",
            schedule="RunAtLoad",
            command=label,
            plist_label=label,
            last_status=status,
            exit_code=str(ec),
        ))
    return jobs


def _parse_launchctl(raw: str) -> dict[str, dict]:
    """Parse `launchctl list` output → {label: {pid, exit_code}}."""
    result: dict[str, dict] = {}
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        pid, ec, label = parts[0].strip(), parts[1].strip(), parts[2].strip()
        result[label] = {"pid": pid, "exit_code": ec}
    return result


# ---------------------------------------------------------------------------
# Log health checker
# ---------------------------------------------------------------------------

PRO_LOG_MAP = {
    "fly_health_check": "/tmp/cron-fly-health.log",
    "drive_poll": "/tmp/cron-drive-poll.log",
    "nb1_refresh": "/tmp/cron-nlm-nb1-refresh.log",
    "nb2_pipeline": "/tmp/cron-nlm-nb2-pipeline.log",
    "nb3_pipeline": "/tmp/cron-nlm-nb3-pipeline.log",
    "nb4_pipeline": "/tmp/cron-nlm-nb4-pipeline.log",
    "nb5_pipeline": "/tmp/cron-nlm-nb5-pipeline.log",
    "nb5_t4_monitor": "/tmp/cron-nb5-t4-monitor.log",
    "nb6_pipeline": "/tmp/cron-nlm-nb6-pipeline.log",
    "nb7_pipeline": "/tmp/cron-nlm-nb7-pipeline.log",
    "nb8_pipeline": "/tmp/cron-nlm-nb8-pipeline.log",
    "nb10_pipeline": "/tmp/cron-nlm-nb10-pipeline.log",
    "yt_monitor": "/tmp/cron-yt-monitor.log",
    "gap_scanner": "/tmp/cron-gap-scanner.log",
    "freshness_monitor": "/tmp/cron-freshness-monitor.log",
    "multimodal": "/tmp/cron-multimodal.log",
    "heartbeat_check": "/tmp/cron-heartbeat.log",
    "ops_briefing": "/tmp/cron-ops-briefing.log",
    "persona_validate": "/tmp/cron-persona-validate.log",
    "peraturan_ingestion": "/tmp/cron-peraturan-ingestion.log",
    "openclaw_state_bridge": "/tmp/openclaw-bridge.log",
    "launchagent_state_bridge": "/tmp/launchagent-bridge.log",
    "expiry_alerter": "~/logs/expiry_alerter.log",
    "fly_backup": "~/logs/fly-backup.log",
}

AIR_LOG_MAP = {
    "ollama_cron": "~/Projects/nuzantara/logs/ollama_cron.log",
    "auto_test": "~/Projects/nuzantara/logs/auto_test.log",
    "sentinel_nightly": "~/Projects/nuzantara/logs/sentinel_nightly.log",
    "kb_ingest": "~/Projects/nuzantara/logs/kb_ingest.log",
    "judgement_day": "~/Projects/nuzantara/logs/judgement_day.log",
    "rag_canary": "~/Projects/nuzantara/logs/rag_canary.log",
    "system_doctor": "~/Projects/nuzantara/logs/system_doctor.log",
    "drive_watchdog": "~/Projects/nuzantara/logs/drive_watchdog.log",
    "ragas_eval": "~/Projects/nuzantara/logs/ragas_eval.log",
    "seo_guardian": "~/Projects/nuzantara/logs/seo_guardian.log",
    "t4_monitor": "~/.openclaw/logs/t4_monitor.log",
    "crm_automation": "~/Projects/nuzantara/apps/backend-rag/logs/crm_automation.log",
    "fly_pg_backup": "~/logs/fly-pg-backup.log",
    "cron_notifiers": "~/logs/cron_notifiers.log",
    "cron_welcome": "~/logs/cron_welcome.log",
    "db_nlm_sync": "~/.openclaw/logs/db_nlm_sync_cron.log",
}


def _check_log_health_pro(jobs: list[Job]) -> None:
    """Check last line of log files for status indicators."""
    for job in jobs:
        if job.machine != "Pro" or job.kind != "cron":
            continue
        log = job.log_file or PRO_LOG_MAP.get(job.name, "")
        if not log:
            continue
        log = log.replace("~", str(Path.home()))
        result = _run(f'stat -f "%Sm" -t "%Y-%m-%d %H:%M" "{log}" 2>/dev/null')
        if result:
            job.last_run = result
        last = _run(f'tail -3 "{log}" 2>/dev/null | grep -iE "error|fail|success|complete|done|ok|✅|❌|warn|skip|abort|Operation not permitted" | tail -1')
        if not last:
            last = _run(f'tail -1 "{log}" 2>/dev/null')
        if last:
            if any(kw in last.lower() for kw in ("error", "fail", "not permitted", "abort", "❌")):
                job.last_status = "❌ FAIL"
            elif any(kw in last.lower() for kw in ("ok", "success", "complete", "done", "✅", "healthy")):
                job.last_status = "✅ OK"
            elif any(kw in last.lower() for kw in ("warn", "skip", "⚠")):
                job.last_status = "⚠️ WARN"
            else:
                job.last_status = "? unknown"
            job.notes = last[:80]
        elif not Path(log).exists():
            job.last_status = "⚠️ NO LOG"


def _check_log_health_air(jobs: list[Job]) -> None:
    """Batch-check Air log files via single SSH call."""
    air_jobs = [j for j in jobs if j.machine == "Air" and j.kind == "cron"]
    if not air_jobs:
        return

    # Build a single SSH command that checks all logs
    checks = []
    for job in air_jobs:
        log = job.log_file or AIR_LOG_MAP.get(job.name, "")
        if not log:
            continue
        checks.append(f'echo "JOB:{job.name}"; echo "MTIME:$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" {log} 2>/dev/null || echo NONE)"; echo "LAST:$(tail -3 {log} 2>/dev/null | grep -iE "error|fail|success|complete|done|ok|warn|skip|abort" | tail -1)"; echo "---"')

    if not checks:
        return
    cmd = "; ".join(checks)
    raw = _ssh_air(cmd, timeout=15)

    # Parse results
    current_job = None
    for line in raw.splitlines():
        if line.startswith("JOB:"):
            current_job = line[4:].strip()
        elif line == "---":
            current_job = None
        elif current_job:
            matching = [j for j in air_jobs if j.name == current_job]
            if not matching:
                continue
            job = matching[0]
            if line.startswith("MTIME:"):
                val = line[6:].strip()
                if val and val != "NONE":
                    job.last_run = val
                elif val == "NONE":
                    job.last_status = "⚠️ NO LOG"
            elif line.startswith("LAST:"):
                val = line[5:].strip()
                if not val:
                    continue
                if any(kw in val.lower() for kw in ("error", "fail", "not permitted", "abort", "❌")):
                    job.last_status = "❌ FAIL"
                elif any(kw in val.lower() for kw in ("ok", "success", "complete", "done", "✅", "healthy", "passed")):
                    job.last_status = "✅ OK"
                elif any(kw in val.lower() for kw in ("warn", "skip", "⚠")):
                    job.last_status = "⚠️ WARN"
                else:
                    job.last_status = "? check"
                job.notes = val[:80]


# ---------------------------------------------------------------------------
# Cron schedule humanizer
# ---------------------------------------------------------------------------

def _consolidate_cron(jobs: list[Job]) -> list[Job]:
    """Merge duplicate cron entries (same name+machine) into one, combining schedules."""
    seen: dict[str, Job] = {}
    for j in jobs:
        key = f"{j.machine}:{j.name}"
        if key in seen:
            existing = seen[key]
            # Combine schedules
            if j.schedule not in existing.schedule:
                existing.schedule += f" + {j.schedule}"
            # Keep the latest log info
            if j.last_run and (not existing.last_run or j.last_run > existing.last_run):
                existing.last_run = j.last_run
                existing.last_status = j.last_status
                existing.notes = j.notes
            if j.log_file and not existing.log_file:
                existing.log_file = j.log_file
        else:
            seen[key] = j
    return list(seen.values())


def _humanize_schedule(sched: str) -> str:
    """Convert cron schedule to human-readable."""
    parts = sched.split()
    if len(parts) != 5:
        return sched
    minute, hour, dom, month, dow = parts

    if minute.startswith("*/") and hour == "*":
        return f"every {minute[2:]}m"
    if hour.startswith("*/") and minute != "*":
        return f"every {hour[2:]}h (:{minute})"
    if dow == "0" and dom == "*":
        return f"Sun {hour}:{minute.zfill(2)} UTC"
    if dow == "1":
        return f"Mon {hour}:{minute.zfill(2)} UTC"
    if dow == "1-6":
        return f"Mon-Sat {hour}:{minute.zfill(2)} UTC"
    if dow == "0-5":
        return f"Sun-Fri {hour}:{minute.zfill(2)} UTC"
    if dow == "2,4":
        return f"Tue,Thu {hour}:{minute.zfill(2)} UTC"
    if dom == "1,15":
        return f"1st+15th {hour}:{minute.zfill(2)} UTC"
    if hour != "*" and minute != "*" and dow == "*" and dom == "*":
        return f"daily {hour}:{minute.zfill(2)} UTC"
    return sched


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(dry_run: bool = False) -> str:
    _check_output_safety(OUTPUT_FILE)

    generated_at = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    # 1. Collect cron jobs
    pro_cron_raw = _run("crontab -l 2>/dev/null")
    air_cron_raw = _ssh_air("crontab -l 2>/dev/null")

    pro_cron_jobs = _parse_crontab(pro_cron_raw, "Pro")
    air_cron_jobs = _parse_crontab(air_cron_raw, "Air")

    # 2. Collect LaunchAgents
    pro_la_jobs = _parse_launchagents_pro()
    air_la_jobs = _parse_launchagents_air()

    # 2.5 Consolidate duplicate cron entries (e.g., multimodal 6 days → 1 entry)
    pro_cron_jobs = _consolidate_cron(pro_cron_jobs)
    air_cron_jobs = _consolidate_cron(air_cron_jobs)

    # 3. Check log health
    all_jobs = pro_cron_jobs + air_cron_jobs + pro_la_jobs + air_la_jobs
    _check_log_health_pro(all_jobs)
    _check_log_health_air(all_jobs)

    # 4. Count stats
    total = len(all_jobs)
    ok_count = sum(1 for j in all_jobs if "✅" in j.last_status)
    fail_count = sum(1 for j in all_jobs if "❌" in j.last_status)
    warn_count = sum(1 for j in all_jobs if "⚠" in j.last_status)
    running_count = sum(1 for j in all_jobs if "🔄" in j.last_status)

    # 5. Build markdown
    lines = [
        "# NUZANTARA — AUTOMATIONS REFERENCE",
        "",
        "> **Auto-generated from live system state** — do not edit manually.",
        f"> Generated: {generated_at}",
        "> Source: `crontab -l` (Pro+Air) + `launchctl list` (Pro+Air) + log file health",
        "",
        "---",
        "",
        "## System Health Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total jobs | **{total}** |",
        f"| ✅ Healthy | **{ok_count}** |",
        f"| 🔄 Running (daemons) | **{running_count}** |",
        f"| ⚠️ Warning/Skip | **{warn_count}** |",
        f"| ❌ Failed | **{fail_count}** |",
        "",
        "---",
        "",
    ]

    # Per-machine sections
    for machine, label in [("Pro", "Pro (nuzantara@Nuzantara — M4 Pro 48GB)"),
                           ("Air", "Air (antonellosiano@Nuzantara-9 — M4 16GB, H24)")]:
        machine_jobs = [j for j in all_jobs if j.machine == machine]
        if not machine_jobs:
            continue

        # Split by kind
        cron_jobs = sorted([j for j in machine_jobs if j.kind == "cron"], key=lambda j: j.name)
        la_jobs = sorted([j for j in machine_jobs if j.kind == "launchagent"], key=lambda j: j.name)

        lines += [f"## {label}", ""]

        if la_jobs:
            lines += [
                "### LaunchAgents",
                "",
                "| Label | Status | Exit |",
                "|-------|--------|------|",
            ]
            for j in la_jobs:
                lines.append(f"| `{j.plist_label}` | {j.last_status} | {j.exit_code} |")
            lines.append("")

        if cron_jobs:
            lines += [
                "### Cron Jobs",
                "",
                "| Job | Schedule | Last Run | Status | Notes |",
                "|-----|----------|----------|--------|-------|",
            ]
            for j in cron_jobs:
                human_sched = _humanize_schedule(j.schedule)
                notes_clean = j.notes.replace("|", "\\|")[:60] if j.notes else ""
                lines.append(
                    f"| `{j.name}` | {human_sched} | {j.last_run} | {j.last_status} | {notes_clean} |"
                )
            lines.append("")

        lines += ["---", ""]

    lines += [
        f"*Generated by `scripts/generate_automations_reference.py` — {generated_at}*",
        "",
    ]

    content = "\n".join(lines)

    if dry_run:
        print(content)
        return content

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content)
    job_count = len(all_jobs)
    print(f"Written: {OUTPUT_FILE} ({job_count} jobs, {len(lines)} lines)")

    return content


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate docs/AUTOMATIONS_REFERENCE.md from live system")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout, don't write")
    args = parser.parse_args()
    generate(dry_run=args.dry_run)
