#!/usr/bin/env python3
"""
Generate docs/AUTOMATIONS_REFERENCE.md by scanning LIVE system state.

Sources (in order):
  1. crontab -l  (Pro — local)
  2. crontab -l  (Air — via SSH)
  3. launchctl list + ~/Library/LaunchAgents/*.plist  (Pro)
  4. launchctl list + ~/Library/LaunchAgents/*.plist  (Air — via SSH)
  5. Log files — last line + mtime for health status

D3.1 compliance: CLAUDE.md, zantara_core.py, fly.toml, .env* are in WRITE_BLOCKLIST.

Run:  python scripts/generate_automations_reference.py [--dry-run]
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

NUZANTARA_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = NUZANTARA_ROOT / "docs" / "AUTOMATIONS_REFERENCE.md"

WRITE_BLOCKLIST = {"CLAUDE.md", "zantara_core.py", "fly.toml", ".env", ".env.production", ".env.local"}


def _check_output_safety(path: Path) -> None:
    if path.name in WRITE_BLOCKLIST or ".env" in str(path):
        print(f"ERROR: {path} is in the doc generator write-blocklist (D3.1). Aborting.")
        sys.exit(1)


@dataclass
class Job:
    name: str
    machine: str
    kind: str
    schedule: str
    command: str
    log_file: str = ""
    last_status: str = ""
    last_run: str = ""
    exit_code: str = ""
    plist_label: str = ""
    notes: str = ""


def _run(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def _ssh_air(cmd: str, timeout: int = 10) -> str:
    return _run(f"ssh -o ConnectTimeout=5 -o BatchMode=yes air '{cmd}'", timeout=timeout)


_CRON_RE = re.compile(
    r"^(?P<schedule>[\d*/,\-]+\s+[\d*/,\-]+\s+[\d*/,\-]+\s+[\d*/,\-]+\s+[\d*/,\-]+)\s+(?P<cmd>.+)$"
)


def _derive_name(cmd: str) -> str:
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
    if "warroom_test" in cmd or ("crontab -l | grep" in cmd):
        return "war_room_oneshot"

    m = re.search(r"/([a-zA-Z0-9_\-]+)\.(?:sh|py)\b", cmd)
    if m:
        raw = m.group(1).replace("-", "_")
        if raw.startswith("run_"):
            raw = raw[4:]
        return raw
    for token in cmd.split():
        if "/" in token and not token.startswith("-"):
            return Path(token).stem.replace("-", "_")
    return cmd[:30].replace(" ", "_")


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
        log_file = ""
        log_match = re.search(r">>\s*(\S+)", cmd_full)
        if log_match:
            log_file = log_match.group(1)
        name = _derive_name(cmd_full)
        jobs.append(Job(
            name=name, machine=machine, kind="cron",
            schedule=sched, command=cmd_full[:120], log_file=log_file,
        ))
    return jobs


def _consolidate_cron(jobs: list[Job]) -> list[Job]:
    seen: dict[str, Job] = {}
    for j in jobs:
        key = f"{j.machine}:{j.name}"
        if key in seen:
            existing = seen[key]
            if j.schedule not in existing.schedule:
                existing.schedule += f" + {j.schedule}"
            if j.last_run and (not existing.last_run or j.last_run > existing.last_run):
                existing.last_run = j.last_run
                existing.last_status = j.last_status
                existing.notes = j.notes
            if j.log_file and not existing.log_file:
                existing.log_file = j.log_file
        else:
            seen[key] = j
    return list(seen.values())


def _parse_launchctl(raw: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        pid, ec, label = parts[0].strip(), parts[1].strip(), parts[2].strip()
        result[label] = {"pid": pid, "exit_code": ec}
    return result


def _parse_launchagents(machine: str) -> list[Job]:
    our_prefixes = (
        "ai.openclaw.", "com.balizero.", "com.nuzantara.", "com.cell.",
        "com.claude-max-api", "com.openclaw.", "com.user.", "homebrew.mxcl.",
    )

    if machine == "Pro":
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        launchctl_raw = _run("launchctl list 2>/dev/null")
        plist_labels = [p.stem for p in sorted(plist_dir.glob("*.plist"))]
    else:
        launchctl_raw = _ssh_air("launchctl list 2>/dev/null")
        plist_list = _ssh_air("ls ~/Library/LaunchAgents/*.plist 2>/dev/null")
        plist_labels = [Path(p.strip()).stem for p in plist_list.splitlines() if p.strip()]

    running = _parse_launchctl(launchctl_raw)
    jobs: list[Job] = []

    for label in plist_labels:
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
            name=label.replace(".", "_"), machine=machine, kind="launchagent",
            schedule="RunAtLoad", command=label, plist_label=label,
            last_status=status, exit_code=str(ec),
        ))
    return jobs


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
    "ollama_cron_window": "~/Projects/nuzantara/logs/ollama_cron.log",
    "auto_test": "~/Projects/nuzantara/logs/auto_test.log",
    "auto_sentinel": "~/Projects/nuzantara/logs/sentinel_nightly.log",
    "auto_kb_ingest": "~/Projects/nuzantara/logs/kb_ingest.log",
    "auto_judgement_day": "~/Projects/nuzantara/logs/judgement_day.log",
    "rag_canary": "~/Projects/nuzantara/logs/rag_canary.log",
    "system_doctor": "~/Projects/nuzantara/logs/system_doctor.log",
    "drive_token_watchdog": "~/Projects/nuzantara/logs/drive_watchdog.log",
    "ragas_eval": "~/Projects/nuzantara/logs/ragas_eval.log",
    "seo_guardian_agent": "~/Projects/nuzantara/logs/seo_guardian.log",
    "t4_monitor": "~/.openclaw/logs/t4_monitor.log",
    "crm_automation_engine": "~/Projects/nuzantara/apps/backend-rag/logs/crm_automation.log",
    "fly_pg_backup": "~/logs/fly-pg-backup.log",
    "notifiers_all": "~/logs/cron_notifiers.log",
    "notifiers_welcome": "~/logs/cron_welcome.log",
    "db_nlm_sync": "~/.openclaw/logs/db_nlm_sync_cron.log",
    "sync_memory_to_nlm": "/tmp/cron-mos-sync.log",
}

_STATUS_KW_FAIL = ("error", "fail", "not permitted", "abort", "broken")
_STATUS_KW_OK = ("ok", "success", "complete", "done", "healthy", "passed")
_STATUS_KW_WARN = ("warn", "skip")


def _classify_line(line: str) -> str:
    ll = line.lower()
    if any(kw in ll for kw in _STATUS_KW_FAIL):
        return "❌ FAIL"
    if any(kw in ll for kw in _STATUS_KW_OK):
        return "✅ OK"
    if any(kw in ll for kw in _STATUS_KW_WARN):
        return "⚠️ WARN"
    return "? check"


def _check_log_health_pro(jobs: list[Job]) -> None:
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
        last = _run(
            f'tail -3 "{log}" 2>/dev/null | grep -iE '
            f'"error|fail|success|complete|done|ok|warn|skip|abort|not.permitted" | tail -1'
        )
        if not last:
            last = _run(f'tail -1 "{log}" 2>/dev/null')
        if last:
            job.last_status = _classify_line(last)
            job.notes = last[:80]
        elif not Path(log).exists():
            job.last_status = "⚠️ NO LOG"


def _check_log_health_air(jobs: list[Job]) -> None:
    air_jobs = [j for j in jobs if j.machine == "Air" and j.kind == "cron"]
    if not air_jobs:
        return
    checks = []
    for job in air_jobs:
        log = job.log_file or AIR_LOG_MAP.get(job.name, "")
        if not log:
            continue
        checks.append(
            f'echo "JOB:{job.name}";'
            f' echo "MTIME:$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" {log} 2>/dev/null || echo NONE)";'
            f' echo "LAST:$(tail -3 {log} 2>/dev/null | grep -iE "error|fail|success|complete|done|ok|warn|skip|abort" | tail -1)";'
            f' echo "---"'
        )
    if not checks:
        return
    raw = _ssh_air("; ".join(checks), timeout=15)
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
                job.last_status = _classify_line(val)
                job.notes = val[:80]


def _humanize_schedule(sched: str) -> str:
    if " + " in sched:
        parts_list = sched.split(" + ")
        first = _humanize_single(parts_list[0].strip())
        return f"{first} (+{len(parts_list) - 1} more)"
    return _humanize_single(sched)


def _humanize_single(sched: str) -> str:
    parts = sched.split()
    if len(parts) != 5:
        return sched
    mi, hr, dom, _mo, dow = parts
    if mi.startswith("*/") and hr == "*":
        return f"every {mi[2:]}m"
    if hr.startswith("*/") and mi != "*":
        return f"every {hr[2:]}h (:{mi})"
    if dow == "0" and dom == "*":
        return f"Sun {hr}:{mi.zfill(2)} UTC"
    if dow == "1" and dom == "*":
        return f"Mon {hr}:{mi.zfill(2)} UTC"
    if dow == "1-6":
        return f"Mon-Sat {hr}:{mi.zfill(2)} UTC"
    if dow == "0-5":
        return f"Sun-Fri {hr}:{mi.zfill(2)} UTC"
    if dow == "2,4":
        return f"Tue,Thu {hr}:{mi.zfill(2)} UTC"
    if dom == "1,15":
        return f"1st+15th {hr}:{mi.zfill(2)} UTC"
    if hr != "*" and mi != "*" and dow == "*" and dom == "*":
        return f"daily {hr}:{mi.zfill(2)} UTC"
    if hr != "*" and mi != "*":
        return f"{dow} {hr}:{mi.zfill(2)} UTC"
    return sched


def generate(dry_run: bool = False) -> str:
    _check_output_safety(OUTPUT_FILE)
    generated_at = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    pro_cron = _consolidate_cron(_parse_crontab(_run("crontab -l 2>/dev/null"), "Pro"))
    air_cron = _consolidate_cron(_parse_crontab(_ssh_air("crontab -l 2>/dev/null"), "Air"))
    pro_la = _parse_launchagents("Pro")
    air_la = _parse_launchagents("Air")

    all_jobs = pro_cron + air_cron + pro_la + air_la
    _check_log_health_pro(all_jobs)
    _check_log_health_air(all_jobs)

    total = len(all_jobs)
    ok = sum(1 for j in all_jobs if "OK" in j.last_status)
    fail = sum(1 for j in all_jobs if "FAIL" in j.last_status)
    warn = sum(1 for j in all_jobs if "WARN" in j.last_status or "NO LOG" in j.last_status or "NOT LOADED" in j.last_status)
    run = sum(1 for j in all_jobs if "Running" in j.last_status)

    lines = [
        "# NUZANTARA — AUTOMATIONS REFERENCE",
        "",
        "> **Auto-generated from live system state** — do not edit manually.",
        f"> Generated: {generated_at}",
        "> Source: `crontab -l` (Pro+Air) + `launchctl list` (Pro+Air) + log health",
        "",
        "---",
        "",
        "## System Health Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total jobs | **{total}** |",
        f"| ✅ Healthy | **{ok}** |",
        f"| 🔄 Running (daemons) | **{run}** |",
        f"| ⚠️ Warning/Skip/NoLog | **{warn}** |",
        f"| ❌ Failed | **{fail}** |",
        "",
        "---",
        "",
    ]

    for machine, label in [
        ("Pro", "Pro (nuzantara@Nuzantara — M4 Pro 48GB)"),
        ("Air", "Air (antonellosiano@Nuzantara-9 — M4 16GB, H24)"),
    ]:
        mj = [j for j in all_jobs if j.machine == machine]
        if not mj:
            continue
        cron = sorted([j for j in mj if j.kind == "cron"], key=lambda j: j.name)
        la = sorted([j for j in mj if j.kind == "launchagent"], key=lambda j: j.name)
        lines += [f"## {label}", ""]

        if la:
            lines += ["### LaunchAgents", "", "| Label | Status | Exit |", "|-------|--------|------|"]
            for j in la:
                lines.append(f"| `{j.plist_label}` | {j.last_status} | {j.exit_code} |")
            lines.append("")

        if cron:
            lines += [
                "### Cron Jobs", "",
                "| Job | Schedule | Last Run | Status | Notes |",
                "|-----|----------|----------|--------|-------|",
            ]
            for j in cron:
                hs = _humanize_schedule(j.schedule)
                n = j.notes.replace("|", "\\|")[:60] if j.notes else ""
                lines.append(f"| `{j.name}` | {hs} | {j.last_run} | {j.last_status} | {n} |")
            lines.append("")

        lines += ["---", ""]

    lines.append(f"*Generated by `scripts/generate_automations_reference.py` — {generated_at}*")
    lines.append("")

    content = "\n".join(lines)
    if dry_run:
        print(content)
        return content

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content)
    print(f"Written: {OUTPUT_FILE} ({total} jobs, {len(lines)} lines)")
    return content


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate docs/AUTOMATIONS_REFERENCE.md from live system")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout, don't write")
    args = parser.parse_args()
    generate(dry_run=args.dry_run)
