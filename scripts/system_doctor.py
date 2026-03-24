#!/usr/bin/env python3
"""
System Doctor — Unified health collector, auto-fixer, and reporter.
Pure Python stdlib. Zero external dependencies. Runs in ~10-15 seconds.

Usage:
    python3 scripts/system_doctor.py              # Full run with auto-fixes
    python3 scripts/system_doctor.py --dry-run    # Read-only, no fixes
    python3 scripts/system_doctor.py --verbose    # Debug output to stderr
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# --- Constants ---

PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OPENCLAW_JOBS = Path.home() / ".openclaw" / "cron" / "jobs.json"
GUARDIAN_BASELINE = PROJECT_ROOT / ".agent" / "decisions" / "baseline.json"
BACKEND_HEALTH_URL = "https://nuzantara-rag.fly.dev/health"
WITA = timezone(timedelta(hours=8))

PRO_LOGS = {
    "pro-fly-health": "/tmp/cron-fly-health.log",
    "pro-pg-backup": "/Users/nuzantara/backups/fly-postgres/backup.log",
    "pro-drive-poll": "/tmp/cron-drive-poll.log",
    "pro-kg-builder": "/tmp/cron-kg-builder.log",
    "pro-conversation-trainer": "/tmp/cron-conversation-trainer.log",
}

AIR_LOGS = {
    "air-ollama": LOGS_DIR / "ollama_cron.log",
    "air-auto-test": LOGS_DIR / "auto_test.log",
    "air-sentinel": LOGS_DIR / "sentinel_nightly.log",
    "air-kb-ingest": LOGS_DIR / "kb_ingest.log",
    "air-judgement-day": LOGS_DIR / "judgement_day.log",
}

# Staleness thresholds in hours
STALENESS = {
    "pro-fly-health": 2, "pro-pg-backup": 36, "pro-drive-poll": 0.5,
    "pro-kg-builder": 8, "pro-conversation-trainer": 12,
    "air-ollama": 36, "air-auto-test": 36, "air-sentinel": 36,
    "air-kb-ingest": 36, "air-judgement-day": 192,  # weekly
}

VERBOSE = False


def log(msg: str) -> None:
    if VERBOSE:
        print(f"[doctor] {msg}", file=sys.stderr)


# --- Data classes ---

@dataclass
class SystemCheck:
    id: str
    name: str
    group: str
    status: str  # ok, warning, error, critical
    last_run: str = ""
    message: str = ""
    stale: bool = False
    needs_ai: bool = False
    ai_context: str = ""


@dataclass
class AutoFix:
    system: str
    fix: str
    result: str = "ok"


@dataclass
class Escalation:
    system: str
    severity: str
    description: str
    context: str = ""


@dataclass
class DoctorReport:
    timestamp: str = ""
    summary: dict = field(default_factory=dict)
    auto_fixes_applied: list = field(default_factory=list)
    systems: list = field(default_factory=list)
    escalations: list = field(default_factory=list)
    telegram_summary: str = ""


# --- Collectors ---

def collect_pro_crons() -> list[SystemCheck]:
    """Single SSH to Pro, read all 5 log tails."""
    checks = []
    separator = "===DOCTOR_SEP==="
    cmd_parts = []
    for log_path in PRO_LOGS.values():
        cmd_parts.append(f"tail -3 {log_path} 2>/dev/null || echo 'FILE_NOT_FOUND'")
    cmd = f"; echo '{separator}'; ".join(cmd_parts)

    log("SSH to Pro for 5 log tails...")
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro", cmd],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            log(f"SSH failed: {result.stderr[:200]}")
            for sys_id, name in [
                ("pro-fly-health", "Fly Health Check"),
                ("pro-pg-backup", "PostgreSQL Backup"),
                ("pro-drive-poll", "Drive Poll"),
                ("pro-kg-builder", "KG Builder"),
                ("pro-conversation-trainer", "Conversation Trainer"),
            ]:
                checks.append(SystemCheck(
                    id=sys_id, name=name, group="pro-cron",
                    status="warning", message="Pro unreachable via SSH",
                ))
            return checks

        sections = result.stdout.split(separator)
        for (sys_id, _log_path), section in zip(PRO_LOGS.items(), sections):
            name = sys_id.replace("pro-", "").replace("-", " ").title()
            check = _parse_log_section(sys_id, name, "pro-cron", section.strip())
            checks.append(check)

    except (subprocess.TimeoutExpired, Exception) as e:
        log(f"SSH exception: {e}")
        for sys_id in PRO_LOGS:
            name = sys_id.replace("pro-", "").replace("-", " ").title()
            checks.append(SystemCheck(
                id=sys_id, name=name, group="pro-cron",
                status="warning", message=f"Pro unreachable: {type(e).__name__}",
            ))

    return checks


def collect_air_crons() -> list[SystemCheck]:
    """Read local Air log files."""
    checks = []
    for sys_id, log_path in AIR_LOGS.items():
        name = sys_id.replace("air-", "").replace("-", " ").title()
        if not log_path.exists():
            checks.append(SystemCheck(
                id=sys_id, name=name, group="air-cron",
                status="warning", message="Log file not found",
            ))
            continue

        try:
            # Read last 3 meaningful lines
            lines = log_path.read_text().strip().splitlines()[-5:]
            section = "\n".join(lines)
            check = _parse_log_section(sys_id, name, "air-cron", section)
            checks.append(check)
        except Exception as e:
            checks.append(SystemCheck(
                id=sys_id, name=name, group="air-cron",
                status="warning", message=f"Cannot read log: {e}",
            ))

    return checks


def collect_openclaw_jobs() -> list[SystemCheck]:
    """Parse OpenClaw jobs.json state for all enabled jobs."""
    checks = []
    if not OPENCLAW_JOBS.exists():
        return [SystemCheck(
            id="openclaw", name="OpenClaw", group="openclaw",
            status="error", message="jobs.json not found",
        )]

    try:
        data = json.loads(OPENCLAW_JOBS.read_text())
    except json.JSONDecodeError as e:
        return [SystemCheck(
            id="openclaw", name="OpenClaw", group="openclaw",
            status="error", message=f"Invalid JSON: {e}",
        )]

    for job in data.get("jobs", []):
        if not job.get("enabled", False):
            continue
        if job.get("name") == "system-doctor":
            continue  # Don't monitor ourselves

        state = job.get("state", {})
        name = job.get("name", job["id"])
        sys_id = f"oc-{name}"
        status_str = state.get("lastRunStatus", "unknown")
        errors = state.get("consecutiveErrors", 0)
        last_error = state.get("lastError", "")
        last_run_ms = state.get("lastRunAtMs", 0)

        # Check staleness
        if last_run_ms > 0:
            age_h = (time.time() * 1000 - last_run_ms) / 3_600_000
            schedule = job.get("schedule", {})
            if schedule.get("kind") == "every":
                expected_h = schedule.get("everyMs", 0) / 3_600_000
            else:
                expected_h = 24  # default for cron jobs
            stale = age_h > expected_h * 2.5
            last_run = datetime.fromtimestamp(last_run_ms / 1000, tz=WITA).strftime("%Y-%m-%d %H:%M")
        else:
            stale = True
            last_run = "never"

        if status_str == "ok" and errors == 0 and not stale:
            check_status = "ok"
            msg = f"OK ({state.get('lastDurationMs', 0) // 1000}s)"
        elif "Channel is required" in last_error or "Delivering to" in last_error:
            check_status = "warning"
            msg = "Delivery config issue (benign on Air)"
        elif errors > 3:
            check_status = "error"
            msg = f"{errors} consecutive errors: {last_error[:100]}"
        elif status_str == "error":
            check_status = "warning"
            msg = f"Last error: {last_error[:100]}"
        elif stale:
            check_status = "warning"
            msg = f"Stale: last run {last_run}"
        else:
            check_status = "ok"
            msg = f"{status_str} ({state.get('lastDurationMs', 0) // 1000}s)"

        needs_ai = check_status == "error" and "Channel" not in last_error

        checks.append(SystemCheck(
            id=sys_id, name=name, group="openclaw",
            status=check_status, last_run=last_run, message=msg,
            stale=stale, needs_ai=needs_ai,
            ai_context=last_error[:300] if needs_ai else "",
        ))

    return checks


def collect_backend_health() -> list[SystemCheck]:
    """curl /health on Fly.io backend."""
    log(f"Checking {BACKEND_HEALTH_URL}...")
    try:
        req = urllib.request.Request(BACKEND_HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        status = data.get("status", "unknown")
        embed_model = data.get("embeddings", {}).get("model", "unknown")
        collections = data.get("database", {}).get("collections", 0)
        docs = data.get("database", {}).get("total_documents", 0)

        if status == "healthy" and embed_model == "text-embedding-3-small":
            return [SystemCheck(
                id="backend", name="Backend Fly.io", group="infra",
                status="ok", message=f"healthy, {collections} collections, {docs:,} docs",
            )]
        elif status == "degraded":
            return [SystemCheck(
                id="backend", name="Backend Fly.io", group="infra",
                status="warning", message=f"degraded: {data}",
                needs_ai=True, ai_context=json.dumps(data)[:500],
            )]
        else:
            return [SystemCheck(
                id="backend", name="Backend Fly.io", group="infra",
                status="critical", message=f"status={status}, model={embed_model}",
                needs_ai=True, ai_context=json.dumps(data)[:500],
            )]

    except urllib.error.URLError:
        # Backend might be sleeping (auto_stop=true, min=0)
        return [SystemCheck(
            id="backend", name="Backend Fly.io", group="infra",
            status="warning", message="Unreachable (may be cold/sleeping)",
        )]
    except Exception as e:
        return [SystemCheck(
            id="backend", name="Backend Fly.io", group="infra",
            status="warning", message=f"Health check failed: {type(e).__name__}",
        )]


def collect_core_guardian() -> list[SystemCheck]:
    """Check Core Guardian baseline freshness."""
    if not GUARDIAN_BASELINE.exists():
        return [SystemCheck(
            id="guardian", name="Core Guardian", group="evaluator",
            status="warning", message="baseline.json not found",
        )]

    mtime = GUARDIAN_BASELINE.stat().st_mtime
    age_h = (time.time() - mtime) / 3600
    last_run = datetime.fromtimestamp(mtime, tz=WITA).strftime("%Y-%m-%d %H:%M")

    if age_h < 12:
        return [SystemCheck(
            id="guardian", name="Core Guardian", group="evaluator",
            status="ok", last_run=last_run, message=f"Baseline updated {age_h:.1f}h ago",
        )]
    else:
        return [SystemCheck(
            id="guardian", name="Core Guardian", group="evaluator",
            status="warning", last_run=last_run, message=f"Stale baseline: {age_h:.0f}h ago",
            stale=True,
        )]


# --- Log parsing helper ---

def _parse_log_section(sys_id: str, name: str, group: str, text: str) -> SystemCheck:
    """Parse a log section to extract status."""
    if not text or text == "FILE_NOT_FOUND":
        return SystemCheck(id=sys_id, name=name, group=group,
                           status="warning", message="Log file empty or missing")

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return SystemCheck(id=sys_id, name=name, group=group,
                           status="warning", message="No log entries")

    last_line = lines[-1]
    # Try to extract timestamp [YYYY-MM-DD HH:MM:SS]
    last_run = ""
    if last_line.startswith("["):
        ts_end = last_line.find("]")
        if ts_end > 0:
            last_run = last_line[1:ts_end]

    # Check for failure indicators
    fail_indicators = ["ERROR", "FAIL", "❌", "error", "failed", "CRITICAL"]
    ok_indicators = ["✅", "OK", "healthy", "passed", "completed", "success"]

    has_fail = any(ind in last_line for ind in fail_indicators)
    has_ok = any(ind in last_line for ind in ok_indicators)

    # Staleness check
    stale = False
    threshold = STALENESS.get(sys_id, 36)
    if last_run:
        try:
            ts = datetime.strptime(last_run, "%Y-%m-%d %H:%M:%S")
            age_h = (datetime.now() - ts).total_seconds() / 3600
            stale = age_h > threshold
        except ValueError:
            pass

    if has_fail and not has_ok:
        status = "error"
        needs_ai = True
    elif stale:
        status = "warning"
        needs_ai = False
    elif has_ok:
        status = "ok"
        needs_ai = False
    else:
        status = "ok"  # No clear indicator = assume ok
        needs_ai = False

    msg = ANSI_RE.sub("", last_line)[:150]
    ai_ctx = "\n".join(lines[-3:]) if needs_ai else ""

    return SystemCheck(
        id=sys_id, name=name, group=group, status=status,
        last_run=last_run, message=msg, stale=stale,
        needs_ai=needs_ai, ai_context=ai_ctx,
    )


# --- Auto-fixers ---

def fix_openclaw_errors(dry_run: bool) -> list[AutoFix]:
    """Reset consecutiveErrors > 3 to 0."""
    fixes = []
    if not OPENCLAW_JOBS.exists():
        return fixes

    data = json.loads(OPENCLAW_JOBS.read_text())
    changed = False
    for job in data.get("jobs", []):
        errs = job.get("state", {}).get("consecutiveErrors", 0)
        if errs > 3:
            if not dry_run:
                job["state"]["consecutiveErrors"] = 0
                changed = True
            fixes.append(AutoFix(
                system=job.get("name", job["id"]),
                fix=f"reset consecutiveErrors from {errs} to 0",
                result="dry-run" if dry_run else "ok",
            ))

    if changed:
        tmp = OPENCLAW_JOBS.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.rename(OPENCLAW_JOBS)

    return fixes


ACTIVE_SCRIPTS = {
    "auto_test.sh", "auto_sentinel.sh", "auto_kb_ingest.sh",
    "auto_judgement_day.sh", "ollama_cron_window.sh",
}


def fix_permissions(dry_run: bool) -> list[AutoFix]:
    """chmod +x only active cron scripts that should be executable."""
    fixes = []
    for name in ACTIVE_SCRIPTS:
        sh = SCRIPTS_DIR / name
        if sh.exists() and not os.access(sh, os.X_OK):
            if not dry_run:
                os.chmod(sh, 0o755)
            fixes.append(AutoFix(
                system=sh.name, fix="chmod +x",
                result="dry-run" if dry_run else "ok",
            ))
    return fixes


def fix_log_rotation(dry_run: bool) -> list[AutoFix]:
    """Rotate logs > 100MB."""
    fixes = []
    if not LOGS_DIR.exists():
        return fixes
    for logf in LOGS_DIR.glob("*.log"):
        try:
            size = logf.stat().st_size
            if size > 100_000_000:
                size_mb = size // 1_000_000
                if not dry_run:
                    logf.rename(logf.with_suffix(".log.old"))
                    logf.touch()
                fixes.append(AutoFix(
                    system=logf.name, fix=f"rotated ({size_mb}MB)",
                    result="dry-run" if dry_run else "ok",
                ))
        except OSError:
            pass
    return fixes


# --- Report formatting ---

def build_telegram_summary(report: DoctorReport) -> str:
    """Build Telegram-friendly markdown summary."""
    s = report.summary
    now = datetime.now(WITA).strftime("%Y-%m-%d %H:%M")
    lines = [f"🏥 System Doctor — {now} WITA", ""]

    # Summary line
    parts = [f"✅ {s['healthy']}/{s['total']}"]
    if s["warning"]:
        parts.append(f"⚠️ {s['warning']} warn")
    if s["error"]:
        parts.append(f"❌ {s['error']} error")
    if s["critical"]:
        parts.append(f"🔴 {s['critical']} critical")
    lines.append(" | ".join(parts))

    # Auto-fixes (compact: just count + first 3)
    if report.auto_fixes_applied:
        lines.append("")
        n = len(report.auto_fixes_applied)
        lines.append(f"🔧 Auto-fixed ({n}):")
        for fix in report.auto_fixes_applied[:3]:
            f = fix if isinstance(fix, dict) else asdict(fix)
            lines.append(f"• {f['system']} → {f['fix']}")
        if n > 3:
            lines.append(f"  ...+{n - 3} more")

    # Errors
    errors = [c for c in report.systems if (c if isinstance(c, dict) else asdict(c)).get("status") in ("error", "critical")]
    if errors:
        lines.append("")
        lines.append("❌ Issues:")
        for c in errors:
            c = c if isinstance(c, dict) else asdict(c)
            lines.append(f"• {c['name']}: {c['message'][:80]}")

    # Warnings (compact)
    warnings = [c for c in report.systems if (c if isinstance(c, dict) else asdict(c)).get("status") == "warning"]
    if warnings:
        lines.append("")
        lines.append(f"⚠️ Warnings ({len(warnings)}):")
        for c in warnings[:5]:  # Max 5 to keep message short
            c = c if isinstance(c, dict) else asdict(c)
            lines.append(f"• {c['name']}: {c['message'][:60]}")
        if len(warnings) > 5:
            lines.append(f"  ...and {len(warnings) - 5} more")

    return "\n".join(lines)


# --- Main ---

def main() -> None:
    global VERBOSE

    parser = argparse.ArgumentParser(description="System Doctor — health collector & auto-fixer")
    parser.add_argument("--dry-run", action="store_true", help="Read-only, no auto-fixes")
    parser.add_argument("--verbose", action="store_true", help="Debug output to stderr")
    args = parser.parse_args()
    VERBOSE = args.verbose

    log("Starting System Doctor...")
    now = datetime.now(WITA)

    # Collect from all sources
    all_checks: list[SystemCheck] = []

    log("Collecting Pro cron status...")
    all_checks.extend(collect_pro_crons())

    log("Collecting Air cron status...")
    all_checks.extend(collect_air_crons())

    log("Collecting OpenClaw job status...")
    all_checks.extend(collect_openclaw_jobs())

    log("Checking backend health...")
    all_checks.extend(collect_backend_health())

    log("Checking Core Guardian...")
    all_checks.extend(collect_core_guardian())

    # Apply auto-fixes
    log("Applying auto-fixes...")
    all_fixes: list[AutoFix] = []
    all_fixes.extend(fix_openclaw_errors(args.dry_run))
    all_fixes.extend(fix_permissions(args.dry_run))
    all_fixes.extend(fix_log_rotation(args.dry_run))

    # Build summary
    statuses = [c.status for c in all_checks]
    summary = {
        "total": len(all_checks),
        "healthy": statuses.count("ok"),
        "warning": statuses.count("warning"),
        "error": statuses.count("error"),
        "critical": statuses.count("critical"),
        "auto_fixed": len(all_fixes),
    }

    # Build escalations
    escalations = []
    for c in all_checks:
        if c.needs_ai:
            escalations.append(Escalation(
                system=c.id, severity=c.status,
                description=c.message, context=c.ai_context,
            ))

    # Build report
    report = DoctorReport(
        timestamp=now.isoformat(),
        summary=summary,
        auto_fixes_applied=[asdict(f) for f in all_fixes],
        systems=[asdict(c) for c in all_checks],
        escalations=[asdict(e) for e in escalations],
    )

    # Telegram summary (only if issues exist)
    if summary["warning"] > 0 or summary["error"] > 0 or summary["critical"] > 0 or all_fixes:
        report.telegram_summary = build_telegram_summary(report)

    # Output JSON
    print(json.dumps(asdict(report), indent=2, default=str))

    log(f"Done. {summary['healthy']}/{summary['total']} healthy, {len(all_fixes)} auto-fixed, {len(escalations)} escalations.")


if __name__ == "__main__":
    main()
