"""Pin: the manual topic path grounds the brief like the cron path.

Gap found 2026-07-08 (WR2-definitiva re-verify): `run_manual_topic` inserted the
draft WITHOUT calling `ground_enrichment`, so ad-hoc topics bypassed the KB
blood the cron path injects (topic_selector line ~626). This test locks the
cure: the manual path calls the grounder with the built brief and inserts the
GROUNDED brief; a grounder crash degrades gracefully (original brief inserted,
no raise).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_topic_selector as ts  # noqa: E402
import wr2_grounding  # noqa: E402


@pytest.mark.asyncio
async def test_manual_topic_calls_grounding_and_inserts_grounded_brief(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://stub")
    monkeypatch.setattr(ts, "_fetch_article", AsyncMock(return_value={
        "title": "LKPM Q2 deadline lands July 15",
        "body": "BKPM reminds investors of the quarterly LKPM obligation.",
        "source": "example.com",
    }))
    monkeypatch.setattr(ts, "_send_telegram", lambda *a, **k: None)

    grounded_marker = {"the_facts": ["Perka BKPM 5/2025 Art. 32: quarterly LKPM by day 15"]}

    async def fake_ground(brief, title):
        out = dict(brief)
        out["enrichment"] = grounded_marker
        out["grounding_source"] = "fly-oracle-http"
        return out

    inserted = {}

    class FakeConn:
        async def fetchval(self, sql, topic, register, brief):
            inserted["topic"] = topic
            inserted["brief"] = json.loads(brief)
            return "00000000-0000-0000-0000-000000000000"

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConn()
        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()
        async def close(self):
            return None

    async def fake_create_pool(**kw):
        return FakePool()

    monkeypatch.setattr(ts.asyncpg, "create_pool", fake_create_pool)
    with patch.object(wr2_grounding, "ground_enrichment", side_effect=fake_ground):
        rc = await ts.run_manual_topic(url="https://example.com/lkpm", dry_run=False)

    assert rc == 0
    assert inserted["brief"]["enrichment"] == grounded_marker
    assert inserted["brief"]["grounding_source"] == "fly-oracle-http"
    assert inserted["brief"]["manual_override"] is True


@pytest.mark.asyncio
async def test_manual_topic_grounding_crash_degrades_not_raises(monkeypatch):
    """Innocence: a grounder explosion must not block the manual insert."""
    monkeypatch.setenv("DATABASE_URL", "postgres://stub")
    monkeypatch.setattr(ts, "_fetch_article", AsyncMock(return_value={
        "title": "T", "body": "B", "source": "s",
    }))
    monkeypatch.setattr(ts, "_send_telegram", lambda *a, **k: None)

    inserted = {}

    class FakeConn:
        async def fetchval(self, sql, topic, register, brief):
            inserted["brief"] = json.loads(brief)
            return "00000000-0000-0000-0000-000000000001"

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConn()
        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()
        async def close(self):
            return None

    async def fake_create_pool(**kw):
        return FakePool()

    monkeypatch.setattr(ts.asyncpg, "create_pool", fake_create_pool)

    async def boom(brief, title):
        raise RuntimeError("oracle down")

    with patch.object(wr2_grounding, "ground_enrichment", side_effect=boom):
        rc = await ts.run_manual_topic(url="https://example.com/x", dry_run=False)

    assert rc == 0
    assert inserted["brief"]["enrichment"] == {}  # original brief, ungrounded but inserted
