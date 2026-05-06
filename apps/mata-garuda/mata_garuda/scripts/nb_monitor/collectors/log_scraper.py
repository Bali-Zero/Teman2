"""Claude Code JSONL session log scraper.

Counts tool_use events for `mcp__notebooklm-mcp__*` tools, grouped by NB
UUID. Reads from PRIMARY_PATHS (the Pro project session dir) and falls
back to SECONDARY_PATHS for completeness. UUID extracted from
`input.notebook_id` OR `input.notebookId` (schema variant guard).

Per spec §3.3 / §7.4: read-only, no side effects on existing pipeline.
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

logger = logging.getLogger(__name__)

PRIMARY_PATHS: tuple[Path, ...] = (
    Path.home() / ".claude" / "projects" / "-Users-nuzantara",
)
SECONDARY_PATHS: tuple[Path, ...] = (
    Path.home() / ".claude" / "projects",
)

NLM_TOOL_PREFIX = "mcp__notebooklm"


@dataclass(frozen=True)
class NLMEvent:
    uuid: str
    tool_name: str
    source_file: Path


def discover_session_files(
    primary: tuple[Path, ...] = PRIMARY_PATHS,
    secondary: tuple[Path, ...] = SECONDARY_PATHS,
    cutoff_mtime: float | None = None,
) -> list[Path]:
    """Discover JSONL session files newer than cutoff_mtime."""
    out: list[Path] = []
    seen: set[Path] = set()
    for root in (*primary, *secondary):
        if not root.exists():
            continue
        for f in root.rglob("*.jsonl"):
            if f in seen:
                continue
            try:
                if cutoff_mtime is not None and f.stat().st_mtime < cutoff_mtime:
                    continue
            except OSError:
                continue
            out.append(f)
            seen.add(f)
    return out


def iter_nlm_events(files: Iterable[Path]) -> Iterator[NLMEvent]:
    """Yield NLMEvent for every NLM tool_use entry in the given files.

    Malformed JSON lines are skipped silently.
    """
    for f in files:
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield from _extract_events(record, source=f)
        except OSError as e:
            logger.warning("log_scraper: cannot read %s: %s", f, e)


def _extract_events(record: dict, source: Path) -> Iterator[NLMEvent]:
    """Walk the record's content array looking for NLM tool_use entries."""
    msg = record.get("message")
    if not isinstance(msg, dict):
        return
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use":
            continue
        name = item.get("name", "")
        if not isinstance(name, str) or not name.startswith(NLM_TOOL_PREFIX):
            continue
        inp = item.get("input")
        if not isinstance(inp, dict):
            continue
        uuid = inp.get("notebook_id") or inp.get("notebookId")
        if not uuid or not isinstance(uuid, str):
            continue
        yield NLMEvent(uuid=uuid, tool_name=name, source_file=source)


def count_nlm_events_by_uuid(
    files: Iterable[Path],
    window_seconds: int,
    now: float | None = None,
) -> dict[str, int]:
    """Count NLM tool_use events per UUID across files within window.

    `files` may include ones older than the window — we filter by file mtime
    so we don't pay the parse cost on stale logs. The cutoff is computed
    against wall-clock time; an explicit `now` clamps to wall-clock so a
    test sentinel like ``now=10**12`` does not push cutoff past file mtimes.
    """
    wall = time.time()
    effective_now = wall if now is None else min(now, wall)
    cutoff = effective_now - window_seconds
    fresh = [f for f in files if _safe_mtime(f) >= cutoff]
    counter: Counter[str] = Counter()
    for ev in iter_nlm_events(fresh):
        counter[ev.uuid] += 1
    return dict(counter)


def _safe_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0
