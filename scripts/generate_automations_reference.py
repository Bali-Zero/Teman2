#!/usr/bin/env python3
"""
D3.2 — Generate docs/AUTOMATIONS_REFERENCE.md from job_registry.json + sentinel_status.json.

Auto-generated file. DO NOT edit manually — changes will be overwritten.
Edit job_registry.json to change job metadata.
Run: python scripts/generate_automations_reference.py

D3.1 compliance: CLAUDE.md, zantara_core.py, fly.toml, .env* are in WRITE_BLOCKLIST.
This script will raise SystemExit(1) if asked to write to any of those files.
"""
import json
import os
import sys
import time
from pathlib import Path

NUZANTARA_ROOT = Path(__file__).parent.parent
REGISTRY_FILE = Path.home() / ".agent" / "decisions" / "job_registry.json"
STATUS_FILE = Path.home() / ".agent" / "decisions" / "sentinel_status.json"
CIRCUIT_FILE = Path.home() / ".agent" / "decisions" / "circuit_breakers.json"
DLQ_FILE = Path.home() / ".agent" / "decisions" / "dlq.json"
OUTPUT_FILE = NUZANTARA_ROOT / "docs" / "AUTOMATIONS_REFERENCE.md"

# D3.1: Write-blocklist — doc generators must never touch these files
WRITE_BLOCKLIST = {
    "CLAUDE.md",
    "zantara_core.py",
    "fly.toml",
    ".env",
    ".env.production",
    ".env.local",
}


def _check_output_safety(path: Path) -> None:
    """D3.1: Refuse to write to any file in WRITE_BLOCKLIST."""
    if path.name in WRITE_BLOCKLIST or any(bl in str(path) for bl in (".env",)):
        print(f"ERROR: {path} is in the doc generator write-blocklist (D3.1). Aborting.")
        sys.exit(1)


def _load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _format_schedule(seconds: int | None) -> str:
    if not seconds:
        return "—"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h" + (f" {m}m" if m else "")
    d = seconds // 86400
    return f"{d}d"


def _circuit_state(job_id: str, circuits: dict) -> str:
    cb = circuits.get(job_id, {})
    state = cb.get("state", "CLOSED")
    phase = cb.get("phase", "T0")
    if state == "CLOSED":
        return "✅ CLOSED"
    if state == "OPEN":
        return f"🔴 OPEN ({phase})"
    return f"🟡 HALF_OPEN"


def _dlq_status(job_id: str, dlq_entries: list) -> str:
    for e in dlq_entries:
        if e.get("job") == job_id:
            s = e.get("status", "?")
            attempts = e.get("autopilot_attempts", 0)
            if s == "TERMINAL":
                return f"🛑 TERMINAL ({attempts} attempts)"
            return f"🟠 DLQ ({s})"
    return ""


def generate(dry_run: bool = False) -> str:
    _check_output_safety(OUTPUT_FILE)

    registry_data = _load_json(REGISTRY_FILE, {})
    jobs = registry_data.get("jobs", {})

    status = _load_json(STATUS_FILE, {})
    circuits = _load_json(CIRCUIT_FILE, {})

    dlq_data = _load_json(DLQ_FILE, {})
    dlq_list = dlq_data if isinstance(dlq_data, list) else dlq_data.get("queue", [])

    generated_at = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    checksum = registry_data.get("checksum", "—")[:12]

    # Group jobs by machine
    by_machine: dict[str, list] = {"Pro": [], "Air": [], "Fly.io": [], "Other": []}
    for job_id, reg in sorted(jobs.items()):
        host = reg.get("host", "")
        if host in ("Nuzantara", "pro"):
            by_machine["Pro"].append((job_id, reg))
        elif host in ("Nuzantara-9", "Nuzantara-9.local", "air"):
            by_machine["Air"].append((job_id, reg))
        elif "fly" in host.lower():
            by_machine["Fly.io"].append((job_id, reg))
        else:
            by_machine["Other"].append((job_id, reg))

    lines = [
        "# NUZANTARA — AUTOMATIONS REFERENCE",
        "",
        "> **Auto-generated** — do not edit manually.",
        f"> Source: `job_registry.json` (checksum `{checksum}…`) + `sentinel_status.json`",
        f"> Generated: {generated_at}",
        "",
        "---",
        "",
    ]

    # System health summary from sentinel_status.json
    if status:
        total = status.get("jobs_total", len(jobs))
        healthy = status.get("jobs_healthy", "?")
        circuit_open = status.get("jobs_circuit_open", 0)
        dlq_count = status.get("dlq_entries", len(dlq_list))
        dlq_terminal = status.get("dlq_terminal", 0)
        oc_gw = status.get("openclaw_gateway", "unknown")
        duration = status.get("last_sentinel_duration_s", "?")
        gw_icon = "✅" if oc_gw == "healthy" else "🔴"
        lines += [
            "## System Health",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Jobs total | {total} |",
            f"| Jobs healthy | {healthy} |",
            f"| Circuits OPEN | {circuit_open} |",
            f"| DLQ entries | {dlq_count} |",
            f"| DLQ TERMINAL | {dlq_terminal} |",
            f"| OpenClaw gateway | {gw_icon} {oc_gw} |",
            f"| Last sentinel run | {duration}s |",
            "",
            "---",
            "",
        ]

    # Per-machine job tables
    for machine, job_list in by_machine.items():
        if not job_list:
            continue

        lines += [f"## {machine} Jobs ({len(job_list)})", ""]
        lines += [
            "| Job | Type | Schedule | repair_scope | idempotent | critical | Circuit | DLQ |",
            "|-----|------|----------|--------------|-----------|---------|---------|-----|",
        ]

        for job_id, reg in job_list:
            jtype = reg.get("type", "—")
            schedule = _format_schedule(reg.get("schedule_seconds") or reg.get("interval_s"))
            repair_scope = reg.get("repair_scope", "—")
            is_idempotent = "✅" if reg.get("is_idempotent", True) else "❌"
            is_critical = "🔴" if reg.get("critical") else "—"
            circuit = _circuit_state(job_id, circuits)
            dlq = _dlq_status(job_id, dlq_list)

            lines.append(
                f"| `{job_id}` | {jtype} | {schedule} | {repair_scope} "
                f"| {is_idempotent} | {is_critical} | {circuit} | {dlq} |"
            )

        lines.append("")

    # DLQ section (active entries)
    active_dlq = [e for e in dlq_list if e.get("status") != "TERMINAL"]
    terminal_dlq = [e for e in dlq_list if e.get("status") == "TERMINAL"]

    if active_dlq or terminal_dlq:
        lines += ["---", "", "## Dead Letter Queue", ""]
        if active_dlq:
            lines += [
                "### Active Entries",
                "",
                "| Job | Status | Attempts | Error |",
                "|-----|--------|----------|-------|",
            ]
            for e in sorted(active_dlq, key=lambda x: x.get("added_ts", 0), reverse=True):
                job = e.get("job", "?")
                status_str = e.get("status", "?")
                attempts = e.get("autopilot_attempts", 0)
                error = (e.get("error_summary") or "")[:60].replace("|", "\\|")
                lines.append(f"| `{job}` | {status_str} | {attempts} | {error} |")
            lines.append("")

        if terminal_dlq:
            lines += [
                "### TERMINAL Entries (manual intervention required)",
                "",
                "| Job | Attempts | First terminal at | Error |",
                "|-----|----------|------------------|-------|",
            ]
            for e in terminal_dlq:
                job = e.get("job", "?")
                attempts = e.get("autopilot_attempts", 0)
                first_at = e.get("first_abandoned_at", "?")
                error = (e.get("error_summary") or "")[:60].replace("|", "\\|")
                lines.append(f"| `{job}` | {attempts} | {first_at} | {error} |")
            lines.append("")
            lines.append("> Run `python scripts/dlq_autopilot.py clear <job_id>` after resolving.")
            lines.append("")

    lines += [
        "---",
        "",
        f"*Generated by `scripts/generate_automations_reference.py` — {generated_at}*",
    ]

    content = "\n".join(lines) + "\n"

    if dry_run:
        print(content)
        return content

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content)
    print(f"Written: {OUTPUT_FILE} ({len(jobs)} jobs, {len(lines)} lines)")

    # Auto-format with prettier so pre-commit hook passes
    import subprocess
    try:
        subprocess.run(
            ["npx", "prettier", "--write", str(OUTPUT_FILE)],
            capture_output=True, cwd=str(NUZANTARA_ROOT)
        )
    except Exception:
        pass  # prettier not available — pre-commit will catch it

    return content


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate docs/AUTOMATIONS_REFERENCE.md")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout, don't write")
    args = parser.parse_args()
    generate(dry_run=args.dry_run)
