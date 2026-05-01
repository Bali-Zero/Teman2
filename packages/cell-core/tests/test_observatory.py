import json
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


@pytest.mark.asyncio
async def test_emit_pulse_observed_disabled_no_op(monkeypatch):
    monkeypatch.delenv("CELL_OBSERVATORY_EMIT", raising=False)
    from cell_core import observatory
    observatory._reset_pool_for_tests()

    # Should NOT call create_pool when disabled
    import asyncpg
    monkeypatch.setattr(asyncpg, "create_pool",
                        lambda *a, **kw: pytest.fail("must not call create_pool when disabled"))

    await observatory.emit_pulse_observed(
        cell_id="test", cell_kind="test", pulse_id="01ABC",
        pulse_timestamp_ms=0, phase="homeostatic",
        sensors=[], pulse_result={}, homeostatic_state={},
    )


@pytest.mark.asyncio
async def test_emit_pulse_observed_writes_outbox_and_notifies(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://fake/db")

    from cell_core import observatory
    observatory._reset_pool_for_tests()

    captured = {"insert_sql": None, "notify_sql": None, "insert_args": None, "notify_args": None}

    class FakeConn:
        async def fetchrow(self, sql, *args):
            captured["insert_sql"] = sql
            captured["insert_args"] = args
            return {"id": 42}

        async def execute(self, sql, *args):
            captured["notify_sql"] = sql
            captured["notify_args"] = args

        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeTx:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeConnContext:
        def __init__(self, conn): self.conn = conn
        async def __aenter__(self): return self.conn
        async def __aexit__(self, *a): pass

    fake_conn = FakeConn()
    fake_conn.transaction = lambda: FakeTx()

    class FakePool:
        def acquire(self): return FakeConnContext(fake_conn)

    async def fake_create_pool(*a, **kw):
        return FakePool()

    import asyncpg
    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    await observatory.emit_pulse_observed(
        cell_id="organism", cell_kind="innervation",
        pulse_id="01TEST", pulse_timestamp_ms=1000,
        phase="homeostatic", sensors=[],
        pulse_result={"classifier_self": "green"}, homeostatic_state={"energy_pct": 80},
    )

    assert "INSERT INTO events_outbox" in captured["insert_sql"]
    assert "RETURNING id" in captured["insert_sql"]  # pins schema contract: PK is 'id', not 'outbox_id'
    assert captured["insert_args"][0] == "cell_pulse_observed"
    payload = json.loads(captured["insert_args"][1])
    assert payload["cell_id"] == "organism"
    assert payload["pulse_id"] == "01TEST"

    assert "pg_notify" in captured["notify_sql"]
    assert captured["notify_args"][0] == "cell_pulse_observed"
    notify_payload = json.loads(captured["notify_args"][1])
    assert notify_payload["_outbox_id"] == 42  # injected after insert


@pytest.mark.asyncio
async def test_emit_pulse_observed_swallows_db_errors(monkeypatch, caplog):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://fake/db")

    from cell_core import observatory
    observatory._reset_pool_for_tests()

    async def fake_create_pool(*a, **kw):
        raise asyncpg.PostgresError("connection refused")

    import asyncpg
    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    # Must NOT raise
    await observatory.emit_pulse_observed(
        cell_id="test", cell_kind="test", pulse_id="01X",
        pulse_timestamp_ms=0, phase="homeostatic",
        sensors=[], pulse_result={}, homeostatic_state={},
    )
    assert any("emit failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_get_or_create_pool_returns_none_if_asyncpg_missing(monkeypatch):
    """When asyncpg is not installed, _get_or_create_pool returns None silently."""
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x/y")
    from cell_core import observatory
    observatory._reset_pool_for_tests()

    # Simulate asyncpg ImportError by removing it from sys.modules + blocking import
    import sys
    saved = sys.modules.pop("asyncpg", None)
    try:
        # Insert a sentinel that raises ImportError when 'asyncpg' is imported
        class _BlockedFinder:
            def find_module(self, name, path=None):
                if name == "asyncpg":
                    raise ImportError("blocked by test")
                return None
        sys.meta_path.insert(0, _BlockedFinder())
        try:
            pool = await observatory._get_or_create_pool()
            assert pool is None
        finally:
            sys.meta_path.pop(0)
    finally:
        if saved is not None:
            sys.modules["asyncpg"] = saved
