"""
Mata Garuda — Kita Newsroom Feed Generator (Layer 5 Distribuzione).

Produces a static JSON file `apps/mata-garuda/data/kita_feed.json` with the
top N enriched items of the day, intended for future consumption by
`kita.balizero.com/newsroom`.

NO frontend wiring in this PR — we only produce the feed.

Selection:
- Latest items from `garuda:enriched`
- `public_safe=true` AND `relevance_score >= 3`
- Any domain allowed (kita is newsroom-style, broader than the TG channel)
- Cap at 20 items, sorted by relevance_score DESC then timestamp DESC
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.stream_tools import stream_length, stream_read
from mata_garuda.types import Agent

logger = logging.getLogger("mata_garuda.agents.kita_feed")

GENOME_FILE = str(Path(__file__).parent / "kita_feed_generator_GENOME.md")

WITA = timezone(timedelta(hours=8))

FEED_PATH = (
    Path(__file__).parent.parent.parent / "data" / "kita_feed.json"
).resolve()
MAX_ITEMS = 20
MIN_SCORE = 3


def _redis_cmd(*args: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["redis-cli", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _parse(raw: str) -> list[dict[str, str]]:
    from mata_garuda.agents.public_channel_publisher import _parse_xrange_output
    return _parse_xrange_output(raw)


def _is_kita_eligible(item: dict[str, str]) -> bool:
    if item.get("public_safe", "").lower() not in {"true", "1", "yes"}:
        return False
    try:
        if int(item.get("relevance_score", "0")) < MIN_SCORE:
            return False
    except ValueError:
        return False
    if not item.get("title"):
        return False
    return True


def _build_feed_entry(item: dict[str, str]) -> dict[str, Any]:
    return {
        "id": item.get("_id", ""),
        "title": item.get("title", "").strip(),
        "summary": (item.get("content") or "").strip()[:400],
        "url": item.get("url", "").strip(),
        "domain": item.get("domain", "").lower(),
        "relevance_score": _safe_int(item.get("relevance_score", "0")),
        "source": item.get("source") or item.get("agent", "unknown"),
        "timestamp": item.get("timestamp", ""),
    }


def _safe_int(raw: str, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def fetch_candidates(count: int = 200) -> list[dict[str, str]]:
    raw = _redis_cmd("XREVRANGE", "garuda:enriched", "+", "-", "COUNT", str(count))
    if not raw:
        return []
    return [e for e in _parse(raw) if _is_kita_eligible(e)]


def build_feed(
    fetch_fn=None,
    now=None,
) -> dict[str, Any]:
    """Build the full feed object (no I/O)."""
    fetch_fn = fetch_fn or fetch_candidates
    now = now or datetime.now(WITA)

    items = fetch_fn()

    # Sort: higher score first, then newest timestamp
    items.sort(
        key=lambda i: (
            -_safe_int(i.get("relevance_score", "0")),
            -_ts_numeric(i.get("timestamp", "")),
        )
    )
    top = items[:MAX_ITEMS]
    entries = [_build_feed_entry(i) for i in top]

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "version": 1,
        "count": len(entries),
        "items": entries,
    }


def _ts_numeric(ts: str) -> int:
    """Convert ISO-ish timestamp to int for sorting. Unparseable → 0."""
    if not ts:
        return 0
    try:
        # strip Z suffix, handle fractional seconds
        clean = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return 0


def write_feed(feed: dict[str, Any], path: Path | None = None) -> Path:
    """Write feed atomically."""
    path = path or FEED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=2))
    tmp.replace(path)
    return path


def run_kita_feed_cycle(
    fetch_fn=None,
    path: Path | None = None,
    now=None,
) -> dict[str, Any]:
    feed = build_feed(fetch_fn=fetch_fn, now=now)
    p = write_feed(feed, path=path)
    return {
        "status": "ok",
        "path": str(p),
        "count": feed["count"],
        "generated_at": feed["generated_at"],
    }


@register_agent(name="Kita Feed Generator", func_name="get_kita_feed_generator")
def get_kita_feed_generator(model: str = "claude") -> Agent:
    """Layer 5 agent: enriched items → data/kita_feed.json for newsroom."""

    def instructions(context_variables: dict) -> str:
        return """You are the Kita Feed Generator (Layer 5 Distribuzione).

Mission: produce `data/kita_feed.json` with up to 20 top enriched items for
future consumption by `kita.balizero.com/newsroom`. No frontend wiring yet.

Selection:
- public_safe=true AND relevance_score >= 3
- Any business domain allowed
- Sorted by score DESC, then timestamp DESC

WORKFLOW:
1. stream_read stream="garuda:enriched" count=200
2. Filter, sort, build 20-item JSON
3. Write to apps/mata-garuda/data/kita_feed.json
4. case_resolved

Output: only confirmation that feed was written."""

    return Agent(
        name="Kita Feed Generator",
        model=model,
        instructions=instructions,
        functions=[stream_read, stream_length, case_resolved, case_not_resolved],
        genome_path=GENOME_FILE,
        layer="distribuzione",
    )
