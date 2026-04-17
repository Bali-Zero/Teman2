"""S11 agents-layer audit: emit JSON with LOC/TODO/bare-except/mtime per file.

Scope: backend/agents/ + backend/channels/ (Agent Mesh V1 hot path).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "apps" / "backend-rag" / "backend" / "agents"
CHANNELS = ROOT / "apps" / "backend-rag" / "backend" / "channels"
EXCLUDE_DIRS = {"__pycache__"}
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
BROAD_EXCEPT_RE = re.compile(r"^\s*except\s+Exception\s*(?:as\s+\w+)?\s*:\s*$", re.MULTILINE)
LOGGER_RE = re.compile(r"\blogging\.getLogger\(|\blogger\s*=|\bstructlog\.")
ASYNC_CLIENT_RE = re.compile(r"httpx\.AsyncClient\s*\(")
CREATE_TASK_RE = re.compile(r"\basyncio\.create_task\s*\(")
SLEEP_RE = re.compile(r"\basyncio\.sleep\s*\(")
RETRY_RE = re.compile(r"\b(tenacity|retry|retries|max_retries|backoff)\b", re.IGNORECASE)
TIMEOUT_RE = re.compile(r"\btimeout\s*=")
PRINT_RE = re.compile(r"^\s*print\s*\(", re.MULTILINE)


def git_last_mtime(path: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%cI", "--", str(path)],
            stderr=subprocess.DEVNULL, timeout=5,
        ).decode().strip()
        return out or None
    except Exception:
        return None


def audit_file(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    loc = sum(1 for line in text.splitlines() if line.strip() and not line.strip().startswith("#"))
    total_lines = text.count("\n") + 1
    return {
        "path": str(path.relative_to(ROOT)),
        "loc": loc,
        "total_lines": total_lines,
        "todo": len(TODO_RE.findall(text)),
        "bare_except": len(BARE_EXCEPT_RE.findall(text)),
        "broad_except": len(BROAD_EXCEPT_RE.findall(text)),
        "has_logger": bool(LOGGER_RE.search(text)),
        "httpx_asyncclient_inline": len(ASYNC_CLIENT_RE.findall(text)),
        "asyncio_create_task": len(CREATE_TASK_RE.findall(text)),
        "asyncio_sleep": len(SLEEP_RE.findall(text)),
        "retry_markers": len(RETRY_RE.findall(text)),
        "timeout_kwarg": len(TIMEOUT_RE.findall(text)),
        "print_calls": len(PRINT_RE.findall(text)),
        "last_modified": git_last_mtime(path),
    }


def collect(base: Path) -> list[dict]:
    files: list[dict] = []
    for py in base.rglob("*.py"):
        rel_parts = py.relative_to(base).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        entry = audit_file(py)
        if entry:
            files.append(entry)
    return files


def rank(files: list[dict]) -> list[dict]:
    for f in files:
        score = (
            f["loc"] / 100
            + f["todo"] * 2
            + f["bare_except"] * 5
            + f["broad_except"] * 0.4
            + f["httpx_asyncclient_inline"] * 3
            + f["asyncio_create_task"] * 1.5
            + f["print_calls"] * 0.5
            + (3 if (not f["has_logger"] and f["loc"] > 50) else 0)
        )
        f["score"] = round(score, 2)
    return sorted(files, key=lambda f: f["score"], reverse=True)


def main() -> int:
    files_agents = collect(AGENTS)
    files_channels = collect(CHANNELS)
    all_files = files_agents + files_channels
    ranked = rank(all_files)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [str(AGENTS.relative_to(ROOT)), str(CHANNELS.relative_to(ROOT))],
        "excluded_subdirs": sorted(EXCLUDE_DIRS),
        "file_count": len(all_files),
        "file_count_agents": len(files_agents),
        "file_count_channels": len(files_channels),
        "total_loc": sum(f["loc"] for f in all_files),
        "total_todo": sum(f["todo"] for f in all_files),
        "total_bare_except": sum(f["bare_except"] for f in all_files),
        "total_broad_except": sum(f["broad_except"] for f in all_files),
        "total_asyncio_create_task": sum(f["asyncio_create_task"] for f in all_files),
        "total_httpx_inline": sum(f["httpx_asyncclient_inline"] for f in all_files),
        "total_print_calls": sum(f["print_calls"] for f in all_files),
        "files_without_logger_gt50loc": sum(1 for f in all_files if not f["has_logger"] and f["loc"] > 50),
        "files_with_httpx_inline": sum(1 for f in all_files if f["httpx_asyncclient_inline"] > 0),
        "files_with_create_task": sum(1 for f in all_files if f["asyncio_create_task"] > 0),
        "top_20_by_score": ranked[:20],
        "top_10_loc": sorted(all_files, key=lambda f: f["loc"], reverse=True)[:10],
        "top_10_todo": sorted([f for f in all_files if f["todo"] > 0], key=lambda f: f["todo"], reverse=True)[:10],
        "top_10_broad_except": sorted([f for f in all_files if f["broad_except"] > 0], key=lambda f: f["broad_except"], reverse=True)[:10],
        "bare_except_offenders": [f for f in all_files if f["bare_except"] > 0],
        "httpx_inline_offenders": [f for f in all_files if f["httpx_asyncclient_inline"] > 0],
        "create_task_offenders": [f for f in all_files if f["asyncio_create_task"] > 0],
    }
    out_path = ROOT / "docs/superpowers/sessions/2026-04-18-strategic-9/logs/air-c3-s11-audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sys.stderr.write(f"Wrote {out_path} ({len(all_files)} files)\n")
    print(json.dumps({
        "file_count": summary["file_count"],
        "file_count_agents": summary["file_count_agents"],
        "file_count_channels": summary["file_count_channels"],
        "total_loc": summary["total_loc"],
        "total_todo": summary["total_todo"],
        "total_bare_except": summary["total_bare_except"],
        "total_broad_except": summary["total_broad_except"],
        "total_asyncio_create_task": summary["total_asyncio_create_task"],
        "total_httpx_inline": summary["total_httpx_inline"],
        "files_without_logger_gt50loc": summary["files_without_logger_gt50loc"],
        "top10": [(f["path"], f["score"], f["loc"], f["todo"], f["broad_except"], f["asyncio_create_task"], f["httpx_asyncclient_inline"]) for f in ranked[:10]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
