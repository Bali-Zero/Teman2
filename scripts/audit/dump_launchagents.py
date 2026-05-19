#!/usr/bin/env python3
"""Read-only launchd dump tool — emits a canonical cron-schedule snapshot.

PR-B3 of Intel Lake + WR2 perfect-production plan (2026-05-20).

Reads every plist in ``~/Library/LaunchAgents/com.balizero.*`` and emits a
machine-readable table (markdown by default, JSON via ``--json``). The
output is intended to feed ``docs/operations/cron-canonical-YYYY-MM-DD.md``
so that future Claude/Codex agents can trust a single source of truth for
"what runs and when".

Properties:
- Pure read-only. Never calls ``launchctl bootout/bootstrap/kickstart``.
- Pure Python stdlib (plistlib, argparse, json, pathlib, subprocess).
- Skips ``.disabled-*`` and ``.backup-*`` files (per cicatrix 2026-05-13
  protocol — disabled plists must live in a separate directory or be
  renamed).
- Cross-references ``launchctl list`` to detect file-on-disk vs loaded
  drift.

Usage:
    python scripts/audit/dump_launchagents.py
    python scripts/audit/dump_launchagents.py --json
    python scripts/audit/dump_launchagents.py --filter wr2
    python scripts/audit/dump_launchagents.py --filter intel-lake
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
from pathlib import Path
from typing import Any

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def _list_plists(filter_substring: str | None) -> list[Path]:
    """Enumerate com.balizero.*.plist files (skips .disabled-* / .backup-*)."""
    if not LAUNCH_AGENTS_DIR.is_dir():
        return []
    out: list[Path] = []
    for entry in sorted(LAUNCH_AGENTS_DIR.iterdir()):
        name = entry.name
        if not name.startswith("com.balizero."):
            continue
        if not name.endswith(".plist"):
            continue
        if ".disabled-" in name or ".backup-" in name:
            continue
        if filter_substring and filter_substring not in name:
            continue
        out.append(entry)
    return out


def _read_plist(path: Path) -> dict[str, Any]:
    """Parse plist XML safely; on malformed file return ``{"_error": ...}``."""
    try:
        with path.open("rb") as fh:
            return plistlib.load(fh)
    except Exception as exc:
        return {"_error": str(exc)}


def _launchctl_state(label: str) -> dict[str, Any]:
    """Capture launchctl-print fields (state/pid/runs/last exit)."""
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return {"loaded": False, "error": str(exc)}
    if result.returncode != 0:
        return {"loaded": False}
    state: dict[str, Any] = {"loaded": True}
    for line in result.stdout.splitlines():
        s = line.strip()
        if s.startswith("state = "):
            state["state"] = s.split("=", 1)[1].strip()
        elif s.startswith("pid = "):
            state["pid"] = s.split("=", 1)[1].strip()
        elif s.startswith("runs = "):
            state["runs"] = s.split("=", 1)[1].strip()
        elif s.startswith("last exit code = "):
            state["last_exit_code"] = s.split("=", 1)[1].strip()
        elif s.startswith("run interval = "):
            state["run_interval"] = s.split("=", 1)[1].strip()
    return state


def _schedule_summary(plist: dict[str, Any]) -> str:
    """Compact human-readable schedule (StartInterval or StartCalendarInterval)."""
    if "StartInterval" in plist:
        sec = plist["StartInterval"]
        if sec >= 86400:
            return f"every {sec // 86400}d"
        if sec >= 3600:
            return f"every {sec // 3600}h"
        if sec >= 60:
            return f"every {sec // 60}min"
        return f"every {sec}s"
    if "StartCalendarInterval" in plist:
        ci = plist["StartCalendarInterval"]
        if isinstance(ci, dict):
            return _format_calendar(ci)
        if isinstance(ci, list):
            return "; ".join(_format_calendar(c) for c in ci)
        return "calendar"
    if plist.get("RunAtLoad"):
        if plist.get("KeepAlive"):
            return "daemon (always-on)"
        return "at-load (one-shot)"
    return "no schedule"


def _format_calendar(ci: dict[str, Any]) -> str:
    """Render a CalendarInterval dict like ``{Hour:1, Minute:0}`` → ``01:00``."""
    if not isinstance(ci, dict):
        return str(ci)
    parts = []
    if "Weekday" in ci:
        weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        try:
            parts.append(weekdays[int(ci["Weekday"]) % 7])
        except Exception:
            parts.append(f"weekday={ci['Weekday']}")
    if "Day" in ci:
        parts.append(f"day={ci['Day']}")
    hour = ci.get("Hour")
    minute = ci.get("Minute")
    if hour is not None or minute is not None:
        parts.append(f"{int(hour or 0):02d}:{int(minute or 0):02d}")
    return " ".join(parts) if parts else "calendar"


def _program_summary(plist: dict[str, Any]) -> str:
    """Short summary of ProgramArguments target script."""
    args = plist.get("ProgramArguments") or []
    if not args:
        return plist.get("Program", "<none>")
    # Find first arg that looks like a script path (.py / .sh / .applescript)
    for a in args:
        if isinstance(a, str) and (
            a.endswith(".py") or a.endswith(".sh") or a.endswith(".applescript")
        ):
            return a
    # Otherwise return joined first 2-3 args
    return " ".join(str(a)[:60] for a in args[:3])


def _entry(plist_path: Path) -> dict[str, Any]:
    """Return one canonical record for the cron table."""
    plist = _read_plist(plist_path)
    if "_error" in plist:
        return {
            "file": plist_path.name,
            "label": "<malformed>",
            "error": plist["_error"],
        }
    label = plist.get("Label", "<missing-label>")
    rec: dict[str, Any] = {
        "file": plist_path.name,
        "label": label,
        "schedule": _schedule_summary(plist),
        "program": _program_summary(plist),
        "keep_alive": bool(plist.get("KeepAlive")),
        "run_at_load": bool(plist.get("RunAtLoad")),
        "stdout": plist.get("StandardOutPath"),
        "stderr": plist.get("StandardErrorPath"),
    }
    rec["live"] = _launchctl_state(label)
    return rec


def _emit_markdown(records: list[dict[str, Any]]) -> str:
    """Render canonical markdown table grouped by family."""
    if not records:
        return "_(no plists found)_"
    # Sort by label
    records = sorted(records, key=lambda r: r["label"])
    lines: list[str] = []
    lines.append("| Label | Schedule | Program | Loaded | State | Runs | Last exit |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in records:
        live = r.get("live", {})
        if "error" in r:
            lines.append(
                f"| `{r['file']}` | _(malformed plist)_ | | | | | _{r['error']}_ |"
            )
            continue
        lines.append(
            f"| `{r['label']}` | {r['schedule']} | `{r['program']}` | "
            f"{'✅' if live.get('loaded') else '❌'} | "
            f"{live.get('state', '-')} | {live.get('runs', '-')} | "
            f"{live.get('last_exit_code', '-')} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--filter",
        help="Substring to filter plist names (e.g. wr2, intel-lake)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of markdown",
    )
    args = parser.parse_args()

    plists = _list_plists(args.filter)
    records = [_entry(p) for p in plists]

    if args.json:
        print(json.dumps(records, indent=2, default=str))
    else:
        print(_emit_markdown(records))
        print()
        print(f"_Total: {len(records)} plists scanned._")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
