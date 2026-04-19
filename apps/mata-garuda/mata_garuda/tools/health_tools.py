"""
Mata Garuda — Health tools.

Helpers for the `mata-garuda health` CLI: stream lengths, LaunchAgent status,
log tails, KB stats, bridge cursor. Pure CLI subprocess — no new runtime deps.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("mata_garuda.tools.health")

WITA = timezone(timedelta(hours=8))

# Streams we care about in the health report (ordered)
HEALTH_STREAMS = [
    "garuda:raw",
    "garuda:enriched",
    "garuda:osint",
    "garuda:alerts",
    "garuda:digest",
    "garuda:feedback",
    "bridge:outbound",
    "bridge:inbound",
]

# LaunchAgent labels we expect to see loaded
EXPECTED_AGENTS = [
    "com.matagaruda.watcher.daily",
    "com.matagaruda.sentinel.daily",
    "com.matagaruda.bridge.adaptive",
    "com.matagaruda.council-weekly",
    "com.matagaruda.public-channel",
    "com.matagaruda.wr2-bridge",
    "com.matagaruda.kita-feed",
    "com.garuda.consumer.daily",
]


def _redis_cmd(*args: str, timeout: int = 5) -> str | None:
    """Run redis-cli, return stdout or None on error."""
    try:
        result = subprocess.run(
            ["redis-cli", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def stream_length(stream: str) -> int | None:
    """Return XLEN of stream, or None if redis/stream unavailable."""
    out = _redis_cmd("XLEN", stream)
    if out is None:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def stream_last_added_ts(stream: str) -> str | None:
    """Return ISO timestamp of most recent entry, or None."""
    out = _redis_cmd("XREVRANGE", stream, "+", "-", "COUNT", "1")
    if not out:
        return None
    # Look for a 'timestamp' field in the output; otherwise use the stream id
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    prev = ""
    for ln in lines:
        clean = ln.strip('"')
        if prev == "timestamp":
            return clean
        prev = clean
    # Fall back: parse the first line for stream id like "1734567890123-0"
    for ln in lines:
        m = re.search(r"\d{13}-\d+", ln)
        if m:
            try:
                ms = int(m.group(0).split("-")[0])
                return datetime.fromtimestamp(ms / 1000, WITA).isoformat(
                    timespec="seconds"
                )
            except ValueError:
                pass
    return None


def get_streams_snapshot() -> list[dict[str, Any]]:
    """Return list of stream statuses for the health CLI."""
    snapshot = []
    for s in HEALTH_STREAMS:
        length = stream_length(s)
        last = stream_last_added_ts(s) if length else None
        snapshot.append({"stream": s, "length": length, "last_added": last})
    return snapshot


def launchctl_list() -> dict[str, dict[str, str | int | None]]:
    """Return dict of {label: {status, pid}} from `launchctl list`.

    `launchctl list` output columns: PID  Status  Label.
    Missing labels return status=None.
    """
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    loaded: dict[str, dict[str, str | int | None]] = {}
    for line in result.stdout.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) < 3:
            continue
        pid_raw, status_raw, label = parts[0], parts[1], parts[2]
        pid: int | None
        try:
            pid = int(pid_raw) if pid_raw != "-" else None
        except ValueError:
            pid = None
        loaded[label] = {
            "pid": pid,
            "status": status_raw,
        }
    return loaded


def get_agents_snapshot(
    expected: list[str] | None = None,
    loader=None,
) -> list[dict[str, Any]]:
    """Return list of LaunchAgent statuses for the health CLI."""
    expected = expected or EXPECTED_AGENTS
    loader = loader or launchctl_list
    loaded = loader()
    out = []
    for label in expected:
        info = loaded.get(label)
        if info is None:
            out.append({"label": label, "loaded": False, "pid": None, "status": None})
        else:
            out.append(
                {
                    "label": label,
                    "loaded": True,
                    "pid": info.get("pid"),
                    "status": info.get("status"),
                }
            )
    return out


def tail_log(path: Path | str, lines: int = 20) -> list[str]:
    """Return last N lines of a log file, empty list on error/missing."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), str(p)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        return [ln for ln in result.stdout.splitlines() if ln.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def recent_errors_in_logs(
    log_dir: Path | str = Path("/tmp"),
    pattern: str = "matagaruda-*.stderr.log",
    hours: int = 1,
) -> list[dict[str, str]]:
    """Scan MG stderr logs for recent entries; return last few lines of each
    non-empty log."""
    out = []
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return out
    cutoff = datetime.now().timestamp() - hours * 3600
    for log_file in sorted(log_dir.glob(pattern)):
        try:
            mtime = log_file.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        tail = tail_log(log_file, lines=5)
        if tail:
            out.append({"file": log_file.name, "tail": "\n".join(tail)})
    return out


def get_kb_stats() -> dict[str, Any] | None:
    """Return KnowledgeBase stats (counts by type). None if unavailable."""
    try:
        from mata_garuda.runtime.knowledge import KnowledgeBase

        kb = KnowledgeBase()
        stats = kb.stats()
        kb.close()
        return stats
    except Exception as e:  # noqa: BLE001
        logger.warning("KB stats failed: %s", e)
        return None


def get_bridge_cursor() -> dict[str, Any] | None:
    """Return bridge cursor contents and mtime, or None."""
    from mata_garuda.config import BRIDGE_CURSOR_PATH

    path = Path(BRIDGE_CURSOR_PATH)
    if not path.exists():
        return {"path": str(path), "exists": False}
    try:
        data = json.loads(path.read_text())
        mtime = datetime.fromtimestamp(path.stat().st_mtime, WITA)
        return {
            "path": str(path),
            "exists": True,
            "last_id": data.get("last_id"),
            "mtime": mtime.isoformat(timespec="seconds"),
        }
    except Exception as e:  # noqa: BLE001
        return {"path": str(path), "exists": True, "error": str(e)}


def nlm_wired_count() -> tuple[int, int]:
    """Count NLM notebooks configured vs total defined. (configured, total)."""
    from mata_garuda.config import NLM_NOTEBOOKS

    total = len(NLM_NOTEBOOKS)
    configured = sum(1 for v in NLM_NOTEBOOKS.values() if v)
    return configured, total


def overall_status(streams: list[dict[str, Any]], agents: list[dict[str, Any]]) -> str:
    """Green/Yellow/Red roll-up."""
    # Red if redis completely unavailable
    if all(s["length"] is None for s in streams):
        return "RED"
    # Yellow if at least one expected agent is missing (not loaded) OR any
    # stream query errored but redis overall responds
    missing_agents = [a for a in agents if not a["loaded"]]
    any_stream_err = any(s["length"] is None for s in streams)
    if missing_agents or any_stream_err:
        return "YELLOW"
    return "GREEN"


def build_health_report(now: datetime | None = None) -> dict[str, Any]:
    """Compose the full health report dict."""
    now = now or datetime.now(WITA)
    streams = get_streams_snapshot()
    agents = get_agents_snapshot()
    status = overall_status(streams, agents)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "status": status,
        "streams": streams,
        "agents": agents,
        "kb": get_kb_stats(),
        "bridge_cursor": get_bridge_cursor(),
        "nlm": {
            "configured": nlm_wired_count()[0],
            "total": nlm_wired_count()[1],
        },
        "recent_errors": recent_errors_in_logs(),
    }


def format_report(report: dict[str, Any]) -> str:
    """Human-readable report for the terminal."""
    lines = []
    lines.append(f"Mata Garuda Health — {report['generated_at']} WITA")
    lines.append("")
    lines.append(f"OVERALL: {report['status']}")
    lines.append("")

    lines.append("STREAMS")
    for s in report["streams"]:
        length = s["length"]
        label = s["stream"]
        if length is None:
            lines.append(f"  {label:22s}  n/a (redis unavailable)")
        else:
            last = s.get("last_added") or "-"
            lines.append(f"  {label:22s}  {length:>6d} items  last={last}")
    lines.append("")

    lines.append("AGENTS (LaunchAgent)")
    for a in report["agents"]:
        marker = "✅" if a["loaded"] else "❌"
        pid = a.get("pid")
        pid_s = f"pid={pid}" if pid else "not-running"
        lines.append(f"  {marker} {a['label']:40s}  {pid_s}")
    lines.append("")

    kb = report.get("kb") or {}
    if kb:
        lines.append("NEXUS / Knowledge Base")
        lines.append(f"  total entries: {kb.get('total', 0)}")
        for key in sorted(k for k in kb if k != "total"):
            lines.append(f"    {key}: {kb[key]}")
        lines.append("")

    nlm = report.get("nlm") or {}
    if nlm:
        lines.append(
            f"NLM notebooks: {nlm.get('configured', 0)}/{nlm.get('total', 0)} wired"
        )
    cursor = report.get("bridge_cursor") or {}
    if cursor:
        if cursor.get("exists"):
            lines.append(
                f"Bridge cursor: last_id={cursor.get('last_id')} "
                f"(updated {cursor.get('mtime', '-')})"
            )
        else:
            lines.append(f"Bridge cursor: not yet initialised ({cursor.get('path')})")
    lines.append("")

    errs = report.get("recent_errors") or []
    if errs:
        lines.append("RECENT ERRORS (last hour)")
        for e in errs:
            lines.append(f"  [{e['file']}]")
            for ln in e["tail"].splitlines():
                lines.append(f"    {ln}")
        lines.append("")

    lines.append(f"TOTAL: {report['status']}")
    return "\n".join(lines)
