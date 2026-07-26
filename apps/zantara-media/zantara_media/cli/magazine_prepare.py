"""Prepare the four sanitized collector projections for a morning edition."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import asyncpg

from zantara_media.magazine.source_projections import prepare_morning_inputs

logger = logging.getLogger(__name__)

_INTEL_LIMIT = 50
_INTEL_QUERY = """
SELECT
    canonical_url,
    title,
    summary,
    source_domain,
    language,
    topic_tags,
    routing_status,
    confidence_score,
    first_seen_at,
    last_seen_at,
    published_at,
    is_probe_sandbox
FROM intel_items
WHERE NOT is_probe_sandbox
  AND last_seen_at >= $1 - INTERVAL '48 hours'
  AND routing_status IN ('blog', 'wr2', 'nb-intel', 'needs_review')
  AND confidence_score >= 0.15
ORDER BY confidence_score DESC, last_seen_at DESC
LIMIT $2
"""


class _IntelConnection(Protocol):
    async def fetch(self, query: str, *arguments: Any) -> Sequence[Mapping[str, Any]]: ...

    async def close(self) -> None: ...


_Connector = Callable[[str], Awaitable[_IntelConnection]]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magazine-prepare")
    subparsers = parser.add_subparsers(dest="command", required=True)
    morning = subparsers.add_parser("morning")
    morning.add_argument("--repo-root", type=Path, required=True)
    morning.add_argument("--state-dir", type=Path, required=True)
    morning.add_argument("--cutoff", required=True)
    return parser


def _cutoff(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("cutoff must be a UTC timestamp ending in Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")
    return parsed.astimezone(timezone.utc)


async def _connect(database_url: str) -> _IntelConnection:
    return await asyncpg.connect(database_url)


async def fetch_intel_rows(
    database_url: str,
    *,
    cutoff: datetime,
    connector: _Connector = _connect,
) -> list[dict[str, Any]]:
    """Read the closed public Intel Lake projection; never select raw columns."""
    connection = await connector(database_url)
    try:
        rows = await connection.fetch(_INTEL_QUERY, cutoff, _INTEL_LIMIT)
        return [dict(row) for row in rows]
    finally:
        await connection.close()


async def load_intel_rows(
    database_url: str | None,
    *,
    cutoff: datetime,
    connector: _Connector = _connect,
) -> tuple[list[dict[str, Any]], str]:
    if not database_url:
        logger.warning("intel lake unavailable reason=missing_database_url")
        return [], "unavailable"
    try:
        return await fetch_intel_rows(
            database_url,
            cutoff=cutoff,
            connector=connector,
        ), "healthy"
    except Exception as exc:  # fail closed while allowing a transparent quiet edition
        logger.warning("intel lake unavailable error_type=%s", type(exc).__name__)
        return [], "unavailable"


async def async_main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cutoff = _cutoff(args.cutoff)
    database_url = os.environ.get("MAGAZINE_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    intel_rows, intel_status = await load_intel_rows(database_url, cutoff=cutoff)
    prepared = prepare_morning_inputs(
        repo_root=args.repo_root.resolve(),
        state_dir=args.state_dir.resolve(),
        cutoff=cutoff,
        intel_rows=intel_rows,
        intel_status=intel_status,
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "intel_status": intel_status,
                "intel_item_count": len(intel_rows),
                "projection_count": len(prepared.projection_paths),
                "manifest_path": str(prepared.manifest_path),
                "asset_manifest_path": str(prepared.asset_manifest_path),
            },
            separators=(",", ":"),
        )
    )
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
