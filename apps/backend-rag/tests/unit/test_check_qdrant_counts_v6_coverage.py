import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import check_qdrant_counts_v6 as checker
import pytest


@pytest.mark.asyncio
async def test_check_stats_success(capsys):
    info = SimpleNamespace(points_count=10, status="green")
    client = AsyncMock()
    client.get_collection = AsyncMock(return_value=info)

    settings = SimpleNamespace(QDRANT_URL="http://qdrant", QDRANT_API_KEY="secret")
    with patch("check_qdrant_counts_v6.settings", settings):
        with patch("check_qdrant_counts_v6.AsyncQdrantClient", return_value=client):
            await checker.check_stats()

    output = capsys.readouterr().out
    assert "Connecting to Qdrant at: http://qdrant" in output
    assert "Qdrant Collection Stats" in output
    assert "[legal_unified_hybrid]" in output
    assert client.get_collection.await_count == 7


@pytest.mark.asyncio
async def test_check_stats_collection_error(capsys):
    ok_info = SimpleNamespace(points_count=1, status="green")
    side_effects = [
        ok_info,
        RuntimeError("missing"),
        ok_info,
        ok_info,
        ok_info,
        ok_info,
        ok_info,
    ]
    client = AsyncMock()
    client.get_collection = AsyncMock(side_effect=side_effects)

    settings = SimpleNamespace(QDRANT_URL="http://qdrant", QDRANT_API_KEY="secret")
    with patch("check_qdrant_counts_v6.settings", settings):
        with patch("check_qdrant_counts_v6.AsyncQdrantClient", return_value=client):
            await checker.check_stats()

    output = capsys.readouterr().out
    assert "ERROR/NOT FOUND" in output


@pytest.mark.asyncio
async def test_check_stats_fatal_error(capsys):
    settings = SimpleNamespace(QDRANT_URL="http://qdrant", QDRANT_API_KEY="secret")
    with patch("check_qdrant_counts_v6.settings", settings):
        with patch(
            "check_qdrant_counts_v6.AsyncQdrantClient",
            side_effect=RuntimeError("down"),
        ):
            await checker.check_stats()
    output = capsys.readouterr().out
    assert "Fatal connection error: down" in output


def test_main_runs_check_stats():
    called = {"ran": False}

    def run_coroutine(coro):
        called["ran"] = True
        coro.close()
        return None

    with patch("asyncio.run", side_effect=run_coroutine):
        runpy.run_module("check_qdrant_counts_v6", run_name="__main__")

    assert called["ran"] is True
