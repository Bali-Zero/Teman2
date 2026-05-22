#!/usr/bin/env python3
"""W22 launchd cron audit — programmatic health matrix.

Panel consenso 3/3 (Gemini/Codex/DeepSeek W11-W21 review 2026-05-23):
"NO kickstart blind; build matrix per plist with last_fire, exit_code,
log signature, mtime delta vs schedule."

Audits:
- ~/Library/LaunchAgents/com.matagaruda.*.plist
- ~/Library/LaunchAgents/com.balizero.*.plist

For each plist, surface:
- last exit code (from launchctl print)
- error.log size + signature analysis (Fatal Python / Operational / TCC noise / silence)
- stdout log mtime vs expected next fire (proxy for "alive?")
- ProgramArguments uses *sh -lc anti-pattern (W19+ flag)

Read-only. No kickstart. No mutations. Just diagnose.
"""
from __future__ import annotations

import json
import plistlib
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
LAUNCH_DIR = HOME / "Library" / "LaunchAgents"

# Patterns that indicate REAL errors (not TCC noise)
REAL_ERROR_PATTERNS = [
    "Fatal Python error",
    "InterruptedError",
    "Traceback",
    "OperationalError",
    "Exception",
    "ConnectionError",
    "Timeout",
    "PermissionError",
    "FileNotFoundError",
    "ImportError",
    "ModuleNotFoundError",
]

# Patterns that indicate "ignorable" TCC noise
NOISE_PATTERNS = [
    "getcwd: cannot access parent",
    "shell-init",
    "job-working-directory",
    ".venv/bin/activate: Operation not permitted",
    ".venv/bin/activate: Interrupted system call",
]


def launchctl_print(label: str) -> dict:
    """Return dict of state/last-exit/path/etc. Empty dict if not loaded."""
    try:
        out = subprocess.check_output(
            ["launchctl", "print", f"gui/{__import__('os').getuid()}/{label}"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {}
    info: dict[str, str] = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("state ="):
            info["state"] = line.split("=", 1)[1].strip()
        elif line.startswith("last exit code ="):
            info["last_exit"] = line.split("=", 1)[1].strip()
        elif line.startswith("path ="):
            info["path"] = line.split("=", 1)[1].strip()
    return info


def analyze_log(path: Path) -> dict:
    """Return {lines, size, noise_lines, real_error_lines, sample_errors}."""
    if not path.exists():
        return {"exists": False}
    try:
        size = path.stat().st_size
    except OSError:
        return {"exists": False}
    if size == 0:
        return {"exists": True, "lines": 0, "size": 0, "noise": 0, "real": 0,
                "sample_errors": []}
    try:
        content = path.read_text(errors="replace")
    except OSError as e:
        return {"exists": True, "error": str(e)}
    lines = content.splitlines()
    noise = sum(1 for ln in lines if any(p in ln for p in NOISE_PATTERNS))
    real_errors = [ln for ln in lines if any(p in ln for p in REAL_ERROR_PATTERNS)]
    return {
        "exists": True,
        "lines": len(lines),
        "size": size,
        "noise": noise,
        "real": len(real_errors),
        "sample_errors": real_errors[-3:] if real_errors else [],
        "mtime": int(path.stat().st_mtime),
    }


def schedule_expected_interval_s(plist_data: dict) -> int | None:
    """Return expected interval between fires in seconds, or None if irregular."""
    if "StartInterval" in plist_data:
        return int(plist_data["StartInterval"])
    if "StartCalendarInterval" in plist_data:
        # Daily/weekly schedules — assume 86400s (daily) as upper-bound proxy
        sci = plist_data["StartCalendarInterval"]
        if isinstance(sci, dict):
            if "Weekday" in sci:
                return 604800  # 7d
            return 86400  # daily
        if isinstance(sci, list):
            return 86400 // max(len(sci), 1)
    return None


def has_lc_antipattern(plist_data: dict) -> bool:
    """True if ProgramArguments uses /bin/{bash,zsh} -lc anti-pattern."""
    pa = plist_data.get("ProgramArguments", [])
    if len(pa) < 2:
        return False
    return pa[0].endswith(("/bash", "/zsh")) and pa[1] in ("-lc", "-l", "-lic")


def audit_plist(plist_path: Path) -> dict:
    """Return audit row for one plist."""
    try:
        with plist_path.open("rb") as f:
            data = plistlib.load(f)
    except Exception as e:
        return {"plist": plist_path.name, "error": f"plist parse: {e}"}

    label = data.get("Label", plist_path.stem)
    info = launchctl_print(label)
    err_path = data.get("StandardErrorPath", "")
    out_path = data.get("StandardOutPath", "")
    err_analysis = analyze_log(Path(err_path)) if err_path else {"exists": False}
    out_analysis = analyze_log(Path(out_path)) if out_path else {"exists": False}

    expected_s = schedule_expected_interval_s(data)
    # Use stdout mtime as proxy for "alive" — stderr may be 0 if no errors
    now = int(time.time())
    last_activity_s = None
    if out_analysis.get("exists") and "mtime" in out_analysis:
        last_activity_s = now - out_analysis["mtime"]

    healthy = True
    diagnosis: list[str] = []

    # Anti-pattern flag
    if has_lc_antipattern(data):
        diagnosis.append("USES_LC_ANTIPATTERN")
        healthy = False

    # Real errors in stderr
    if err_analysis.get("real", 0) > 0:
        diagnosis.append(f"REAL_ERRORS={err_analysis['real']}")
        healthy = False

    # Mostly noise in stderr (W21 silent-dead signal)
    if (err_analysis.get("noise", 0) > 50 and err_analysis.get("real", 0) == 0
            and err_analysis.get("lines", 0) > 50):
        diagnosis.append(f"HIGH_NOISE={err_analysis['noise']}")
        healthy = False

    # Liveness check: last_activity > 2× expected interval = stale
    if expected_s and last_activity_s and last_activity_s > 2 * expected_s:
        diagnosis.append(
            f"STALE(last_activity={last_activity_s}s, expected={expected_s}s)"
        )
        healthy = False
    if last_activity_s is None and "state" not in info:
        diagnosis.append("NEVER_FIRED_OR_NOT_LOADED")
        healthy = False

    # Non-zero exit code
    last_exit = info.get("last_exit", "")
    if last_exit and last_exit not in ("0", "(never exited)"):
        try:
            ec = int(last_exit)
            if ec != 0:
                diagnosis.append(f"NONZERO_EXIT={ec}")
                healthy = False
        except ValueError:
            pass

    return {
        "plist": plist_path.name,
        "label": label,
        "loaded": "state" in info,
        "last_exit": last_exit or "—",
        "expected_interval_s": expected_s,
        "last_activity_s": last_activity_s,
        "stderr_lines": err_analysis.get("lines", 0),
        "stderr_noise": err_analysis.get("noise", 0),
        "stderr_real_errors": err_analysis.get("real", 0),
        "stderr_sample": err_analysis.get("sample_errors", []),
        "stdout_lines": out_analysis.get("lines", 0),
        "uses_lc_antipattern": has_lc_antipattern(data),
        "healthy": healthy,
        "diagnosis": diagnosis,
    }


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "com.{matagaruda,balizero,cell}.*.plist"
    plists = sorted(LAUNCH_DIR.glob(pattern))
    if not plists:
        # Glob doesn't expand braces in pathlib — manual fallback
        plists = sorted(
            list(LAUNCH_DIR.glob("com.matagaruda.*.plist"))
            + list(LAUNCH_DIR.glob("com.balizero.*.plist"))
            + list(LAUNCH_DIR.glob("com.cell.*.plist"))
        )

    rows = [audit_plist(p) for p in plists]
    summary = {
        "audit_ts": int(time.time()),
        "audit_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_plists": len(rows),
        "healthy": sum(1 for r in rows if r.get("healthy")),
        "unhealthy": sum(1 for r in rows if not r.get("healthy")),
        "with_lc_antipattern": sum(1 for r in rows if r.get("uses_lc_antipattern")),
        "with_real_errors": sum(1 for r in rows if r.get("stderr_real_errors", 0) > 0),
        "with_high_noise": sum(1 for r in rows if "HIGH_NOISE" in str(r.get("diagnosis", []))),
        "never_fired": sum(1 for r in rows if "NEVER_FIRED_OR_NOT_LOADED" in r.get("diagnosis", [])),
    }
    print(json.dumps({"summary": summary, "rows": rows}, indent=2, default=str))

    sys.exit(0 if summary["unhealthy"] == 0 else 1)


if __name__ == "__main__":
    main()
