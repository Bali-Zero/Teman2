from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from zantara_media.cli.magazine_prepare import fetch_intel_rows, load_intel_rows


class _FakeConnection:
    def __init__(self) -> None:
        self.query = ""
        self.arguments: tuple[Any, ...] = ()
        self.closed = False

    async def fetch(self, query: str, *arguments: Any) -> list[dict[str, Any]]:
        self.query = query
        self.arguments = arguments
        return [
            {
                "canonical_url": "https://example.com/story",
                "title": "Verified public story",
                "summary": "Public summary",
                "source_domain": "example.com",
                "language": "en",
                "topic_tags": ["visa"],
                "routing_status": "wr2",
                "confidence_score": 0.9,
                "first_seen_at": datetime(2026, 7, 21, tzinfo=timezone.utc),
                "last_seen_at": datetime(2026, 7, 21, tzinfo=timezone.utc),
                "published_at": datetime(2026, 7, 21, tzinfo=timezone.utc),
                "is_probe_sandbox": False,
            }
        ]

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_fetch_intel_rows_selects_only_public_columns_and_closes_connection() -> None:
    connection = _FakeConnection()

    async def connector(_: str) -> _FakeConnection:
        return connection

    cutoff = datetime(2026, 7, 21, tzinfo=timezone.utc)
    rows = await fetch_intel_rows(
        "postgresql://readonly@example.invalid/db",
        cutoff=cutoff,
        connector=connector,
    )

    assert rows[0]["title"] == "Verified public story"
    assert "raw_payload" not in connection.query
    assert "routing_targets" not in connection.query
    assert "NOT is_probe_sandbox" in connection.query
    assert "confidence_score >= 0.15" in connection.query
    assert connection.arguments == (cutoff, 50)
    assert connection.closed is True


@pytest.mark.asyncio
async def test_load_intel_rows_is_explicitly_unavailable_without_database_url() -> None:
    rows, status = await load_intel_rows(
        None,
        cutoff=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )

    assert rows == []
    assert status == "unavailable"
