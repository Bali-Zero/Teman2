"""2026-06-21 — crm_guardian_gemini_cli_worker DB connect retry (superscar #8).

The worker reaches Fly Postgres through a long-running flyctl proxy on
localhost:15432. When the WireGuard tunnel flaps, asyncpg's single-shot connect
raised ConnectionDoesNotExistError mid-handshake and the whole 5-min tick exited 1
(~4 spurious FAILs/2.5h observed in System Doctor RED 2026-06-21). _connect_with_retry
rides over the transient flap with bounded exponential backoff, but re-raises once the
attempt budget is exhausted so a genuine outage is NOT masked.

The worker imports backend.services.crm_guardian.* at module top, so the module is
loaded via importlib with apps/backend-rag on sys.path. No real DB / asyncpg is
touched — a fake asyncpg (connect coroutine + exceptions namespace) drives the helper.
"""
import asyncio
import importlib.util
import os
import sys
import types

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ROOT = os.path.dirname(_SCRIPTS_DIR)
_BACKEND = os.path.join(_ROOT, "apps", "backend-rag")


class _ConnDoesNotExist(Exception):
    """Stand-in for asyncpg.exceptions.ConnectionDoesNotExistError."""


@pytest.fixture()
def worker():
    for p in (_BACKEND, _SCRIPTS_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(
        "cgw_retry", os.path.join(_SCRIPTS_DIR, "crm_guardian_gemini_cli_worker.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_asyncpg(fail_times: int, exc=_ConnDoesNotExist):
    """asyncpg double: connect() fails `fail_times`, then returns a sentinel conn."""
    calls = {"n": 0}

    async def connect(db_url):
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise exc("transient proxy flap")
        return f"CONN[{db_url}]"

    ns = types.SimpleNamespace()
    ns.connect = connect
    ns.exceptions = types.SimpleNamespace(ConnectionDoesNotExistError=exc)
    ns._calls = calls
    return ns


class TestConnectWithRetry:
    def test_recovers_after_transient_flaps(self, worker, monkeypatch):
        monkeypatch.setattr(worker, "DB_CONNECT_BASE_DELAY_S", 0.0)
        fake = _fake_asyncpg(fail_times=2)
        conn = asyncio.run(worker._connect_with_retry(fake, "postgres://x"))
        assert conn == "CONN[postgres://x]"
        assert fake._calls["n"] == 3  # 2 flaps + 1 success

    def test_reraises_after_exhausting_attempts(self, worker, monkeypatch):
        monkeypatch.setattr(worker, "DB_CONNECT_BASE_DELAY_S", 0.0)
        monkeypatch.setattr(worker, "DB_CONNECT_MAX_ATTEMPTS", 3)
        fake = _fake_asyncpg(fail_times=99)
        with pytest.raises(_ConnDoesNotExist):
            asyncio.run(worker._connect_with_retry(fake, "postgres://x"))
        assert fake._calls["n"] == 3  # exactly MAX_ATTEMPTS tries, no infinite loop

    def test_succeeds_first_try_no_sleep(self, worker, monkeypatch):
        monkeypatch.setattr(worker, "DB_CONNECT_BASE_DELAY_S", 0.0)
        fake = _fake_asyncpg(fail_times=0)
        conn = asyncio.run(worker._connect_with_retry(fake, "postgres://y"))
        assert conn == "CONN[postgres://y]"
        assert fake._calls["n"] == 1

    def test_non_retryable_error_raises_immediately(self, worker, monkeypatch):
        monkeypatch.setattr(worker, "DB_CONNECT_BASE_DELAY_S", 0.0)

        class Boom(Exception):
            pass

        calls = {"n": 0}

        async def connect(db_url):
            calls["n"] += 1
            raise Boom("auth failed — not a transient flap")

        fake = types.SimpleNamespace(
            connect=connect,
            exceptions=types.SimpleNamespace(ConnectionDoesNotExistError=_ConnDoesNotExist),
        )
        with pytest.raises(Boom):
            asyncio.run(worker._connect_with_retry(fake, "z"))
        assert calls["n"] == 1  # no retry on a non-connection error
