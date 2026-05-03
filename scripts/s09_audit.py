"""S09 services-layer audit: emit JSON with LOC/TODO/bare-except/mtime per file."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "apps" / "backend-rag" / "backend" / "services"
EXCLUDE_DIRS = {"events", "__pycache__"}
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
BROAD_EXCEPT_RE = re.compile(r"^\s*except\s+Exception\s*(?:as\s+\w+)?\s*:\s*$", re.MULTILINE)
LOGGER_RE = re.compile(r"\blogging\.getLogger\(|\blogger\s*=|\bstructlog\.")
ASYNC_CLIENT_RE = re.compile(r"httpx\.AsyncClient\s*\(")
SLEEP_RE = re.compile(r"\basyncio\.sleep\s*\(")
RETRY_RE = re.compile(r"\b(tenacity|retry|retries|max_retries|backoff)\b", re.IGNORECASE)
TIMEOUT_RE = re.compile(r"\btimeout\s*=")


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
        "asyncio_sleep": len(SLEEP_RE.findall(text)),
        "retry_markers": len(RETRY_RE.findall(text)),
        "timeout_kwarg": len(TIMEOUT_RE.findall(text)),
        "last_modified": git_last_mtime(path),
    }


def collect() -> list[dict]:
    files: list[dict] = []
    for py in SERVICES.rglob("*.py"):
        rel_parts = py.relative_to(SERVICES).parts
        if rel_parts and rel_parts[0] in EXCLUDE_DIRS:
            continue
        if any(part == "__pycache__" for part in rel_parts):
            continue
        entry = audit_file(py)
        if entry:
            files.append(entry)
    return files


def rank(files: list[dict]) -> list[dict]:
    # Score: LOC/100 + TODO*2 + bare_except*5 + broad_except*0.3 + httpx_inline*3 + (1 if not has_logger and LOC>50 else 0)*3
    for f in files:
        score = (
            f["loc"] / 100
            + f["todo"] * 2
            + f["bare_except"] * 5
            + f["broad_except"] * 0.3
            + f["httpx_asyncclient_inline"] * 3
            + (3 if (not f["has_logger"] and f["loc"] > 50) else 0)
        )
        f["score"] = round(score, 2)
    return sorted(files, key=lambda f: f["score"], reverse=True)


def main() -> int:
    files = collect()
    ranked = rank(files)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(SERVICES.relative_to(ROOT)),
        "excluded_subdirs": sorted(EXCLUDE_DIRS),
        "file_count": len(files),
        "total_loc": sum(f["loc"] for f in files),
        "total_todo": sum(f["todo"] for f in files),
        "total_bare_except": sum(f["bare_except"] for f in files),
        "total_broad_except": sum(f["broad_except"] for f in files),
        "files_without_logger_gt50loc": sum(1 for f in files if not f["has_logger"] and f["loc"] > 50),
        "files_with_httpx_inline": sum(1 for f in files if f["httpx_asyncclient_inline"] > 0),
        "top_20_by_score": ranked[:20],
        "top_10_loc": sorted(files, key=lambda f: f["loc"], reverse=True)[:10],
        "top_10_todo": sorted([f for f in files if f["todo"] > 0], key=lambda f: f["todo"], reverse=True)[:10],
        "top_10_broad_except": sorted([f for f in files if f["broad_except"] > 0], key=lambda f: f["broad_except"], reverse=True)[:10],
        "bare_except_offenders": [f for f in files if f["bare_except"] > 0],
        "httpx_inline_offenders": [f for f in files if f["httpx_asyncclient_inline"] > 0],
    }
    out_path = ROOT / "docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-2-s09-audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sys.stderr.write(f"Wrote {out_path} ({len(files)} files)\n")
    print(json.dumps({
        "file_count": summary["file_count"],
        "total_loc": summary["total_loc"],
        "total_todo": summary["total_todo"],
        "total_bare_except": summary["total_bare_except"],
        "total_broad_except": summary["total_broad_except"],
        "files_without_logger_gt50loc": summary["files_without_logger_gt50loc"],
        "files_with_httpx_inline": summary["files_with_httpx_inline"],
        "top5": [(f["path"], f["score"], f["loc"], f["todo"], f["bare_except"], f["broad_except"]) for f in ranked[:5]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
