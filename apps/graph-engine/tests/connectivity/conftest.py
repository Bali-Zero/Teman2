"""Fixtures for connectivity tests.

These tests require local infrastructure (docker-compose up or equivalent).
They are skipped automatically if the service cannot be reached with the
expected credentials.

The detection helpers here deliberately go beyond a TCP port check: a
local Postgres running under a different role configuration (e.g. a
Homebrew postgresql without the ``postgres`` role) would pass a port
check but fail every test. We probe with a real connection attempt
using the exact URL the tests will use, so the skip fires cleanly when
the service is not actually usable.
"""

from __future__ import annotations

import asyncio

import pytest

from nuzantara_graph.config import Settings

# Canonical local URLs used by the connectivity tier. These mirror the
# ``local_settings`` fixture below and serve as the single source of
# truth for both test skipping and test execution.
_LOCAL_POSTGRES_URL = "postgresql://postgres:postgres@localhost:5432/nuzantara_v6"
_LOCAL_QDRANT_URL = "http://localhost:6333"
_LOCAL_REDIS_URLS = ("redis://localhost:6379/0", "redis://localhost:6380/0")


def _run_sync(coro):
    """Run an async probe to completion, returning the result or False.

    Uses an explicit new event loop instead of ``asyncio.run`` so this
    function works whether or not an outer loop is already running —
    ``asyncio.run`` raises ``RuntimeError: asyncio.run() cannot be
    called from a running event loop``, which would break any caller
    importing the conftest from inside an async context (e.g. pytest
    collection under ``asyncio_mode=auto`` in some configurations).

    Any exception (connection refused, auth failure, timeout, library
    missing, running loop conflicts) is swallowed and treated as "not
    available".
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    except Exception:
        return False
    finally:
        if loop is not None:
            try:
                loop.close()
            except Exception:
                pass


async def _probe_postgres(url: str, timeout: float = 2.0) -> bool:
    try:
        import asyncpg
    except ImportError:
        return False
    try:
        conn = await asyncio.wait_for(asyncpg.connect(url), timeout=timeout)
    except Exception:
        return False
    try:
        await conn.fetchval("SELECT 1")
    finally:
        await conn.close()
    return True


async def _probe_qdrant(url: str, timeout: float = 2.0) -> bool:
    try:
        from qdrant_client import AsyncQdrantClient
    except ImportError:
        return False
    client = AsyncQdrantClient(url=url, timeout=int(timeout))
    try:
        # get_collections does a real HTTP round-trip and validates that
        # the service speaks the Qdrant protocol (not a random server
        # happening to answer on port 6333).
        await asyncio.wait_for(client.get_collections(), timeout=timeout)
        return True
    except Exception:
        return False
    finally:
        try:
            await client.close()
        except Exception:
            pass


async def _probe_redis(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return False, ""
    try:
        client = aioredis.from_url(
            url,
            decode_responses=True,
            socket_timeout=timeout,
            socket_connect_timeout=timeout,
        )
    except ValueError:
        return False, ""
    try:
        pong = await asyncio.wait_for(client.ping(), timeout=timeout)
        if pong:
            return True, url
        return False, ""
    except Exception:
        return False, ""
    finally:
        try:
            # redis-py >= 5.0.1 renamed ``close`` to ``aclose``; fall back
            # for older versions installed in downstream dev environments.
            closer = getattr(client, "aclose", None) or client.close
            await closer()
        except Exception:
            pass


async def _first_available_redis(urls: tuple[str, ...]) -> str:
    for url in urls:
        ok, resolved = await _probe_redis(url)
        if ok:
            return resolved
    return ""


# Module-level availability flags — evaluated once at import time and
# consumed by @pytest.mark.skipif in each test file. A real connection
# attempt catches mismatched credentials, wrong db name, and libraries
# that aren't installed, not just a missing TCP listener.
POSTGRES_AVAILABLE = bool(_run_sync(_probe_postgres(_LOCAL_POSTGRES_URL)))
QDRANT_AVAILABLE = bool(_run_sync(_probe_qdrant(_LOCAL_QDRANT_URL)))

_resolved_redis_url = _run_sync(_first_available_redis(_LOCAL_REDIS_URLS)) or ""
REDIS_AVAILABLE = bool(_resolved_redis_url)
LOCAL_REDIS_URL = _resolved_redis_url or _LOCAL_REDIS_URLS[0]


@pytest.fixture(scope="module")
def local_settings() -> Settings:
    """Settings pointing to local docker-compose services."""
    return Settings(
        qdrant_url=_LOCAL_QDRANT_URL,
        qdrant_api_key="",
        database_url=_LOCAL_POSTGRES_URL,
        redis_url=LOCAL_REDIS_URL,
        openai_api_key="",
        google_api_key="",
    )
