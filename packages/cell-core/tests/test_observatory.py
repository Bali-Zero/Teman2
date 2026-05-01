import os
import pytest
from cell_core import observatory


def test_is_enabled_default_false(monkeypatch):
    monkeypatch.delenv("CELL_OBSERVATORY_EMIT", raising=False)
    assert observatory.is_enabled() is False


def test_is_enabled_when_true(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")
    assert observatory.is_enabled() is True


def test_is_enabled_case_insensitive(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "TRUE")
    assert observatory.is_enabled() is True


def test_is_enabled_other_values_are_false(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "yes")
    assert observatory.is_enabled() is False
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "1")
    assert observatory.is_enabled() is False


@pytest.mark.asyncio
async def test_get_or_create_pool_returns_pool(monkeypatch):
    """Lazy-init pool from EVENTBUS_DATABASE_URL env var."""
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://invalid-host/test")

    # Pool creation is lazy; we just verify the function returns a callable that
    # produces an asyncpg.Pool object (we don't actually connect — the URL is fake).
    from cell_core import observatory
    observatory._reset_pool_for_tests()  # test hook

    # We mock asyncpg.create_pool to avoid real network call
    import asyncpg
    called = {}

    async def fake_create_pool(dsn, **kwargs):
        called["dsn"] = dsn
        called["kwargs"] = kwargs
        # Return a minimal mock pool
        class _MockPool:
            async def close(self): pass
        return _MockPool()

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    pool = await observatory._get_or_create_pool()
    assert pool is not None
    assert called["dsn"] == "postgresql://invalid-host/test"
    assert called["kwargs"]["min_size"] == 1
    assert called["kwargs"]["max_size"] == 3


@pytest.mark.asyncio
async def test_get_or_create_pool_returns_none_if_url_unset(monkeypatch):
    monkeypatch.delenv("EVENTBUS_DATABASE_URL", raising=False)
    from cell_core import observatory
    observatory._reset_pool_for_tests()
    pool = await observatory._get_or_create_pool()
    assert pool is None
