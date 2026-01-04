import asyncio
import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import verify_db


class DummyAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyPool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return DummyAcquire(self._conn)


@pytest.mark.asyncio
async def test_db_success(capsys):
    async def dummy_fetchrow(*_args, **_kwargs):
        return {"id": "test-user"}

    async def pass_through(coro, timeout=None):
        return await coro

    conn = SimpleNamespace(fetchrow=dummy_fetchrow)
    pool = DummyPool(conn)

    with patch("verify_db.asyncpg.create_pool", AsyncMock(return_value=pool)):
        with patch("verify_db.asyncio.wait_for", side_effect=pass_through):
            await verify_db.test_db()

    output = capsys.readouterr().out
    assert "DB Connected" in output
    assert "Query Result" in output


@pytest.mark.asyncio
async def test_db_timeout(capsys):
    async def dummy_fetchrow(*_args, **_kwargs):
        return None

    conn = SimpleNamespace(fetchrow=dummy_fetchrow)
    pool = DummyPool(conn)

    async def raise_timeout(_coro, timeout=None):
        _coro.close()
        raise asyncio.TimeoutError

    with patch("verify_db.asyncpg.create_pool", AsyncMock(return_value=pool)):
        with patch("verify_db.asyncio.wait_for", side_effect=raise_timeout):
            await verify_db.test_db()
    output = capsys.readouterr().out
    assert "DB Query TIMED OUT" in output


@pytest.mark.asyncio
async def test_db_exception(capsys):
    with patch("verify_db.asyncpg.create_pool", AsyncMock(side_effect=RuntimeError("boom"))):
        await verify_db.test_db()
    output = capsys.readouterr().out
    assert "DB Failed: boom" in output


def test_main_runs():
    called = {"ran": False}

    def run_coroutine(coro):
        called["ran"] = True
        coro.close()
        return None

    with patch("asyncio.run", side_effect=run_coroutine):
        runpy.run_module("verify_db", run_name="__main__")

    assert called["ran"] is True
