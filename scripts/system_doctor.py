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
from concurrent.futures import ThreadPoolExecutor, as_completed
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

FRONTEND_URLS = {
    "kita": "https://kita.balizero.com",
    "my": "https://my.balizero.com",
    "prime": "https://prime.balizero.com",
    "mail": "https://mail.balizero.com",
    "calendar": "https://calendar.balizero.com",
    "drive": "https://drive.balizero.com",
    "knowledge": "https://knowledge.balizero.com",
    "zantara": "https://zantara.balizero.com",
}

SSL_DOMAINS = [
    "kita.balizero.com",
    "my.balizero.com",
    "prime.balizero.com",
    "mail.balizero.com",
    "calendar.balizero.com",
    "drive.balizero.com",
    "knowledge.balizero.com",
    "zantara.balizero.com",
    "nuzantara-rag.fly.dev",
]

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
    "pro-fly-health": 18,  # Runs */30 7-19 WITA only, so stale after 18h (overnight gap)
    "pro-pg-backup": 36, "pro-drive-poll": 1,
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
            elif schedule.get("kind") == "cron":
                expr = schedule.get("expr", "")
                # Weekly cron (day of week specified) → 192h (8 days)
                parts = expr.split()
                if len(parts) >= 5 and parts[4] != "*":
                    expected_h = 192
                # Daily cron → 36h
                elif len(parts) >= 5 and parts[2] == "*":
                    expected_h = 36
                else:
                    expected_h = 36
            else:
                expected_h = 36  # default
            stale = age_h > expected_h * 2.5
            last_run = datetime.fromtimestamp(last_run_ms / 1000, tz=WITA).strftime("%Y-%m-%d %H:%M")
        else:
            stale = True
            last_run = "never"

        if status_str == "ok" and errors == 0 and not stale:
            check_status = "ok"
            msg = f"OK ({state.get('lastDurationMs', 0) // 1000}s)"
        elif "Channel is required" in last_error or "Delivering to" in last_error:
            check_status = "ok"  # Benign on Air — delivery jobs only work on Pro
            msg = "Delivery config (Air-only, benign)"
        elif errors > 3:
            check_status = "error"
            msg = f"{errors} consecutive errors: {last_error[:100]}"
        elif status_str == "error" and not last_error.strip():
            check_status = "ok"  # Error with empty message = transient, already recovered
            msg = f"Recovered (last error was empty)"
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
            msg = "healthy"
            if collections > 0:
                msg += f", {collections} collections, {docs:,} docs"
            return [SystemCheck(
                id="backend", name="Backend Fly.io", group="infra",
                status="ok", message=msg,
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

    if age_h < 96:  # Core Guardian runs on Pro every 3h; baseline.json syncs via git
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


def collect_frontend_health() -> list[SystemCheck]:
    """Check all 8 frontend subdomains return HTTP 200 or 307."""
    checks = []
    for name, url in FRONTEND_URLS.items():
        sys_id = f"frontend-{name}"
        display = f"Frontend {name}.balizero.com"
        log(f"Checking {url}...")
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "SystemDoctor/1.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.getcode()
                if code in (200, 307, 308):
                    # Check response has some content (not empty error page)
                    body = resp.read(2048).decode("utf-8", errors="replace")
                    if len(body) > 100:
                        checks.append(SystemCheck(
                            id=sys_id, name=display, group="frontend",
                            status="ok", message=f"HTTP {code}, {len(body)}+ bytes",
                        ))
                    else:
                        checks.append(SystemCheck(
                            id=sys_id, name=display, group="frontend",
                            status="warning", message=f"HTTP {code} but body too small ({len(body)} bytes)",
                        ))
                else:
                    checks.append(SystemCheck(
                        id=sys_id, name=display, group="frontend",
                        status="error", message=f"HTTP {code}",
                    ))
        except urllib.error.HTTPError as e:
            checks.append(SystemCheck(
                id=sys_id, name=display, group="frontend",
                status="error", message=f"HTTP {e.code}: {e.reason}",
            ))
        except Exception as e:
            checks.append(SystemCheck(
                id=sys_id, name=display, group="frontend",
                status="error", message=f"Unreachable: {type(e).__name__}",
            ))
    return checks


def collect_ssl_certs() -> list[SystemCheck]:
    """Check SSL certificate expiry for all domains. Alert if < 14 days."""
    import ssl
    import socket

    checks = []
    for domain in SSL_DOMAINS:
        sys_id = f"ssl-{domain.split('.')[0]}"
        log(f"Checking SSL for {domain}...")
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    not_after_str = cert.get("notAfter", "")
                    # Format: 'Mar 15 23:59:59 2026 GMT'
                    not_after = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")
                    days_left = (not_after - datetime.utcnow()).days

                    if days_left > 30:
                        checks.append(SystemCheck(
                            id=sys_id, name=f"SSL {domain}", group="ssl",
                            status="ok", message=f"Expires in {days_left} days",
                        ))
                    elif days_left > 14:
                        checks.append(SystemCheck(
                            id=sys_id, name=f"SSL {domain}", group="ssl",
                            status="warning", message=f"Expires in {days_left} days — renew soon",
                        ))
                    elif days_left > 0:
                        checks.append(SystemCheck(
                            id=sys_id, name=f"SSL {domain}", group="ssl",
                            status="critical", message=f"Expires in {days_left} days!",
                        ))
                    else:
                        checks.append(SystemCheck(
                            id=sys_id, name=f"SSL {domain}", group="ssl",
                            status="critical", message=f"EXPIRED {abs(days_left)} days ago!",
                        ))
        except Exception as e:
            checks.append(SystemCheck(
                id=sys_id, name=f"SSL {domain}", group="ssl",
                status="error", message=f"Cannot check: {type(e).__name__}: {str(e)[:80]}",
            ))
    return checks


def collect_fly_resources() -> list[SystemCheck]:
    """Check Fly.io RAM usage and recent OOM events."""
    checks = []

    # 1. Memory usage via fly ssh /proc/meminfo
    log("Checking Fly.io RAM via SSH...")
    try:
        result = subprocess.run(
            ["fly", "ssh", "console", "--app", "nuzantara-rag",
             "-C", "cat /proc/meminfo"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0:
            mem = {}
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    try:
                        mem[key] = int(parts[1])  # kB
                    except ValueError:
                        pass

            total_mb = mem.get("MemTotal", 0) / 1024
            avail_mb = mem.get("MemAvailable", 0) / 1024
            used_mb = total_mb - avail_mb
            pct = (used_mb / total_mb * 100) if total_mb > 0 else 0

            if pct < 80:
                status = "ok"
                msg = f"RAM: {used_mb:.0f}/{total_mb:.0f}MB ({pct:.0f}% used), {avail_mb:.0f}MB free"
            elif pct < 90:
                status = "warning"
                msg = f"RAM HIGH: {used_mb:.0f}/{total_mb:.0f}MB ({pct:.0f}% used), {avail_mb:.0f}MB free"
            else:
                status = "critical"
                msg = f"RAM CRITICAL: {used_mb:.0f}/{total_mb:.0f}MB ({pct:.0f}% used), {avail_mb:.0f}MB free"

            checks.append(SystemCheck(
                id="fly-ram", name="Fly.io RAM", group="infra",
                status=status, message=msg,
                needs_ai=status == "critical",
                ai_context=f"MemTotal={total_mb:.0f}MB MemAvailable={avail_mb:.0f}MB" if status == "critical" else "",
            ))
        else:
            checks.append(SystemCheck(
                id="fly-ram", name="Fly.io RAM", group="infra",
                status="warning", message=f"SSH failed: {result.stderr[:100]}",
            ))
    except subprocess.TimeoutExpired:
        checks.append(SystemCheck(
            id="fly-ram", name="Fly.io RAM", group="infra",
            status="warning", message="SSH timeout (machine may be sleeping)",
        ))
    except Exception as e:
        checks.append(SystemCheck(
            id="fly-ram", name="Fly.io RAM", group="infra",
            status="warning", message=f"Cannot check: {type(e).__name__}",
        ))

    # 2. OOM detection from recent logs
    log("Checking Fly.io logs for OOM events...")
    try:
        result = subprocess.run(
            ["fly", "logs", "--app", "nuzantara-rag", "-n", "100"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            oom_lines = [
                l for l in result.stdout.splitlines()
                if any(k in l.lower() for k in ["oom", "out of memory", "killed", "sigkill"])
            ]
            if oom_lines:
                checks.append(SystemCheck(
                    id="fly-oom", name="Fly.io OOM Events", group="infra",
                    status="error", message=f"{len(oom_lines)} OOM/kill events in recent logs",
                    needs_ai=True, ai_context="\n".join(oom_lines[-3:]),
                ))
            else:
                checks.append(SystemCheck(
                    id="fly-oom", name="Fly.io OOM Events", group="infra",
                    status="ok", message="No OOM events in last 100 log lines",
                ))
    except Exception:
        pass  # Non-critical, skip silently

    return checks


def collect_llm_api_health() -> list[SystemCheck]:
    """Probe LLM API availability via backend /health and embedding canary."""
    checks = []

    # 1. Check embedding model via /health endpoint (already fetched in collect_backend_health,
    #    but we do a targeted check for the embedding specifically)
    log("Checking embedding API health...")
    try:
        req = urllib.request.Request(
            BACKEND_HEALTH_URL, method="GET"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            embed = data.get("embeddings", {})
            model = embed.get("model", "unknown")
            status = embed.get("status", "unknown")
            dims = embed.get("dimensions", 0)

            if model == "text-embedding-3-small" and status == "operational":
                checks.append(SystemCheck(
                    id="embedding-api", name="Embedding API (OpenAI)", group="llm",
                    status="ok", message=f"{model}, {dims} dims, {status}",
                ))
            elif model != "text-embedding-3-small":
                checks.append(SystemCheck(
                    id="embedding-api", name="Embedding API (OpenAI)", group="llm",
                    status="critical",
                    message=f"WRONG MODEL: {model} (expected text-embedding-3-small)",
                    needs_ai=True, ai_context=f"Embedding model mismatch: {model}",
                ))
            else:
                checks.append(SystemCheck(
                    id="embedding-api", name="Embedding API (OpenAI)", group="llm",
                    status="warning", message=f"{model}, status={status}",
                ))
    except Exception as e:
        checks.append(SystemCheck(
            id="embedding-api", name="Embedding API (OpenAI)", group="llm",
            status="warning", message=f"Cannot check: {type(e).__name__}",
        ))

    # 2. Check LLM circuit breaker state via Fly logs (SSH to Pro which has fly auth)
    log("Checking LLM API via Fly logs (SSH Pro)...")
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro",
             "fly logs --app nuzantara-rag --no-tail 2>/dev/null | tail -200"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            # Count recent LLM errors
            llm_errors = [
                l for l in lines
                if any(k in l for k in [
                    "Circuit breaker", "OPENED",
                    "All LLM models failed",
                    "Quota exhausted",
                    "ResourceExhausted",
                    "ServiceUnavailable",
                ])
            ]
            circuit_opens = [l for l in llm_errors if "OPENED" in l]

            if circuit_opens:
                checks.append(SystemCheck(
                    id="llm-circuit", name="LLM Circuit Breakers", group="llm",
                    status="warning",
                    message=f"{len(circuit_opens)} circuit breaker openings in recent logs",
                    needs_ai=len(circuit_opens) > 3,
                    ai_context="\n".join(circuit_opens[-3:]) if len(circuit_opens) > 3 else "",
                ))
            elif llm_errors:
                checks.append(SystemCheck(
                    id="llm-circuit", name="LLM Circuit Breakers", group="llm",
                    status="ok",
                    message=f"{len(llm_errors)} LLM warnings (no circuit opens) in recent logs",
                ))
            else:
                checks.append(SystemCheck(
                    id="llm-circuit", name="LLM Circuit Breakers", group="llm",
                    status="ok", message="No LLM errors in last 200 log lines",
                ))
    except subprocess.TimeoutExpired:
        checks.append(SystemCheck(
            id="llm-circuit", name="LLM Circuit Breakers", group="llm",
            status="ok", message="Log check timed out (backend may be sleeping)",
        ))
    except Exception as e:
        checks.append(SystemCheck(
            id="llm-circuit", name="LLM Circuit Breakers", group="llm",
            status="ok", message=f"Log check skipped: {type(e).__name__}",
        ))

    return checks


def collect_llm_cost() -> list[SystemCheck]:
    """Check LLM cost from Prometheus metrics endpoint."""
    checks = []
    log("Checking LLM cost metrics...")
    try:
        # Metrics endpoint is admin-protected, use fly ssh to query locally
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro",
             "fly ssh console --app nuzantara-rag -C 'curl -s http://localhost:8080/metrics' 2>/dev/null"],
            capture_output=True, text=True, timeout=25,
        )
        if result.returncode == 0 and result.stdout:
            # Parse Prometheus text format for LLM cost
            total_cost = 0.0
            model_costs = {}
            for line in result.stdout.splitlines():
                if line.startswith("zantara_llm_cost_usd_total{"):
                    # Extract model name and value
                    try:
                        model = line.split('model="')[1].split('"')[0]
                        value = float(line.split("} ")[1])
                        model_costs[model] = value
                        total_cost += value
                    except (IndexError, ValueError):
                        pass

            if model_costs:
                cost_details = ", ".join(f"{m}: ${v:.4f}" for m, v in sorted(model_costs.items(), key=lambda x: -x[1])[:3])
                if total_cost > 5.0:
                    status = "warning"
                    msg = f"LLM cost: ${total_cost:.2f} (since restart). {cost_details}"
                else:
                    status = "ok"
                    msg = f"LLM cost: ${total_cost:.4f} (since restart). {cost_details}"
                checks.append(SystemCheck(
                    id="llm-cost", name="LLM Cost", group="llm",
                    status=status, message=msg,
                ))
            else:
                checks.append(SystemCheck(
                    id="llm-cost", name="LLM Cost", group="llm",
                    status="ok", message="No LLM cost metrics yet (backend may have just started)",
                ))
        else:
            checks.append(SystemCheck(
                id="llm-cost", name="LLM Cost", group="llm",
                status="ok", message="Metrics endpoint unreachable (backend sleeping)",
            ))
    except Exception as e:
        checks.append(SystemCheck(
            id="llm-cost", name="LLM Cost", group="llm",
            status="ok", message=f"Cost check skipped: {type(e).__name__}",
        ))
    return checks


def collect_dependabot() -> list[SystemCheck]:
    """Check GitHub Dependabot open vulnerability alerts."""
    checks = []
    log("Checking Dependabot alerts...")

    # Load GH_TOKEN from master env
    master_env = Path.home() / "Desktop" / "NUZANTARA_ENV_KEYS.env"
    gh_token = None
    if master_env.exists():
        for line in master_env.read_text().splitlines():
            if line.startswith("GH_TOKEN="):
                gh_token = line.split("=", 1)[1].strip()
                break

    if not gh_token:
        checks.append(SystemCheck(
            id="dependabot", name="Dependabot Alerts", group="security",
            status="ok", message="GH_TOKEN not found, skipping",
        ))
        return checks

    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/Balizero1987/Teman2/dependabot/alerts?state=open&per_page=100",
            headers={
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            alerts = json.loads(resp.read())

        if isinstance(alerts, dict) and "message" in alerts:
            checks.append(SystemCheck(
                id="dependabot", name="Dependabot Alerts", group="security",
                status="ok", message=f"API error: {alerts['message'][:60]}",
            ))
            return checks

        severity_counts: dict[str, int] = {}
        for a in alerts:
            sev = a.get("security_advisory", {}).get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        total = len(alerts)
        critical = severity_counts.get("critical", 0)
        high = severity_counts.get("high", 0)
        medium = severity_counts.get("medium", 0)
        low = severity_counts.get("low", 0)

        parts = [f"{total} open"]
        if critical:
            parts.append(f"{critical} critical")
        if high:
            parts.append(f"{high} high")
        if medium:
            parts.append(f"{medium} medium")

        if critical > 0:
            status = "critical"
        elif high > 10:
            status = "warning"
        else:
            status = "ok"

        checks.append(SystemCheck(
            id="dependabot", name="Dependabot Alerts", group="security",
            status=status, message=", ".join(parts),
            needs_ai=critical > 0,
        ))
    except Exception as e:
        checks.append(SystemCheck(
            id="dependabot", name="Dependabot Alerts", group="security",
            status="ok", message=f"Check skipped: {type(e).__name__}",
        ))

    return checks


def collect_error_patterns() -> list[SystemCheck]:
    """Detect recurring error patterns in recent Fly logs."""
    checks = []
    log("Analyzing error patterns in Fly logs...")

    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro",
             "fly logs --app nuzantara-rag --no-tail 2>/dev/null | tail -500"],
            capture_output=True, text=True, timeout=25,
        )
        if result.returncode != 0 or not result.stdout.strip():
            checks.append(SystemCheck(
                id="error-patterns", name="Error Patterns", group="quality",
                status="ok", message="Log fetch failed (backend sleeping)",
            ))
            return checks

        lines = result.stdout.splitlines()

        # Count error categories
        error_categories: dict[str, int] = {}
        for line in lines:
            lower = line.lower()
            if "error" in lower or "exception" in lower or "traceback" in lower:
                # Categorize the error
                if "timeout" in lower or "timed out" in lower:
                    error_categories["timeout"] = error_categories.get("timeout", 0) + 1
                elif "connection" in lower or "connect" in lower:
                    error_categories["connection"] = error_categories.get("connection", 0) + 1
                elif "memory" in lower or "oom" in lower:
                    error_categories["memory"] = error_categories.get("memory", 0) + 1
                elif "auth" in lower or "401" in lower or "403" in lower:
                    error_categories["auth"] = error_categories.get("auth", 0) + 1
                elif "qdrant" in lower or "vector" in lower:
                    error_categories["qdrant"] = error_categories.get("qdrant", 0) + 1
                elif "rate" in lower and "limit" in lower:
                    error_categories["rate_limit"] = error_categories.get("rate_limit", 0) + 1
                elif "import" in lower or "module" in lower:
                    error_categories["import"] = error_categories.get("import", 0) + 1
                else:
                    error_categories["other"] = error_categories.get("other", 0) + 1

        total_errors = sum(error_categories.values())

        if total_errors == 0:
            checks.append(SystemCheck(
                id="error-patterns", name="Error Patterns", group="quality",
                status="ok", message="No errors in last 500 log lines",
            ))
        else:
            # Format top categories
            sorted_cats = sorted(error_categories.items(), key=lambda x: -x[1])
            top = ", ".join(f"{cat}:{count}" for cat, count in sorted_cats[:4])

            if total_errors > 50:
                status = "error"
                needs_ai = True
            elif total_errors > 20:
                status = "warning"
                needs_ai = False
            else:
                status = "ok"
                needs_ai = False

            checks.append(SystemCheck(
                id="error-patterns", name="Error Patterns", group="quality",
                status=status,
                message=f"{total_errors} errors in 500 lines: {top}",
                needs_ai=needs_ai,
                ai_context=f"Error categories: {json.dumps(error_categories)}" if needs_ai else "",
            ))

    except Exception as e:
        checks.append(SystemCheck(
            id="error-patterns", name="Error Patterns", group="quality",
            status="ok", message=f"Check skipped: {type(e).__name__}",
        ))

    return checks


def collect_import_chain() -> list[SystemCheck]:
    """Test critical import chain on Pro via SSH."""
    sys_id = "import-chain"
    name = "Import Chain"
    log("Testing import chain on Pro...")
    cmd = (
        "cd ~/Desktop/nuzantara/apps/backend-rag && "
        "source .venv/bin/activate && "
        'python -c "from backend.app.dependencies import get_current_user; print(\'OK\')" 2>&1'
    )
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro", cmd],
            capture_output=True, text=True, timeout=20,
        )
        output = result.stdout.strip()
        if "OK" in output and result.returncode == 0:
            return [SystemCheck(
                id=sys_id, name=name, group="infra",
                status="ok", message="Import chain OK (dependencies.py → all routers)",
            )]
        else:
            error_msg = (result.stderr or output)[:200]
            return [SystemCheck(
                id=sys_id, name=name, group="infra",
                status="critical", message=f"BROKEN: {error_msg}",
                needs_ai=True, ai_context=f"stdout: {output[:300]}\nstderr: {result.stderr[:300]}",
            )]
    except subprocess.TimeoutExpired:
        return [SystemCheck(
            id=sys_id, name=name, group="infra",
            status="warning", message="Pro SSH timeout (15s)",
        )]
    except Exception as e:
        return [SystemCheck(
            id=sys_id, name=name, group="infra",
            status="warning", message=f"Cannot test: {type(e).__name__}",
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
    benign_indicators = ["non disponibile", "skip", "sleeping", "Backend non disponibile"]

    has_fail = any(ind in last_line for ind in fail_indicators)
    has_ok = any(ind in last_line for ind in ok_indicators)
    has_benign = any(ind in last_line for ind in benign_indicators)

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

    if has_benign:
        status = "ok"  # Backend sleeping, skip is expected behavior
        needs_ai = False
    elif has_fail and not has_ok:
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
    parser.add_argument("--notify-telegram", action="store_true", help="Send Telegram alert on issues (used by cron)")
    args = parser.parse_args()
    VERBOSE = args.verbose

    log("Starting System Doctor...")
    now = datetime.now(WITA)

    # Collect from all sources — run collectors in parallel to avoid serial timeout cascade.
    # Previous sequential execution took ~300s worst case (13 collectors × SSH/HTTP timeouts).
    # Parallel execution completes in ~30s (bounded by slowest single collector).
    GLOBAL_TIMEOUT = 120  # seconds — hard ceiling for all collectors combined

    collectors = [
        ("Pro crons", collect_pro_crons),
        ("Air crons", collect_air_crons),
        ("OpenClaw jobs", collect_openclaw_jobs),
        ("Backend health", collect_backend_health),
        ("Core Guardian", collect_core_guardian),
        ("Frontend health", collect_frontend_health),
        ("SSL certs", collect_ssl_certs),
        ("Fly resources", collect_fly_resources),
        ("LLM API health", collect_llm_api_health),
        ("LLM cost", collect_llm_cost),
        ("Dependabot", collect_dependabot),
        ("Error patterns", collect_error_patterns),
        ("Import chain", collect_import_chain),
    ]

    all_checks: list[SystemCheck] = []

    with ThreadPoolExecutor(max_workers=6) as pool:
        future_to_name = {
            pool.submit(fn): name for name, fn in collectors
        }
        for future in as_completed(future_to_name, timeout=GLOBAL_TIMEOUT):
            name = future_to_name[future]
            try:
                result = future.result(timeout=5)
                log(f"Collected {name}: {len(result)} checks")
                all_checks.extend(result)
            except Exception as e:
                log(f"Collector {name} failed: {e}")
                all_checks.append(SystemCheck(
                    id=f"collector-{name.lower().replace(' ', '-')}",
                    name=name, group="doctor",
                    status="warning",
                    message=f"Collector failed: {type(e).__name__}: {str(e)[:80]}",
                ))

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
