import functools
import json
import logging

import asyncpg

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Pool configuration constants
_POOL_MIN_SIZE = 2
_POOL_MAX_SIZE = 5
_COMMAND_TIMEOUT = 60  # seconds — query execution timeout
_MAX_INACTIVE_CONN_LIFETIME = 300  # seconds — idle connections recycled after 5 min
_ACQUIRE_TIMEOUT = 10  # seconds — max wait for a free connection

# The one JSONB/JSON encoder every asyncpg pool in this repo must register.
#
# `default=str` is not decoration — it is the reason this object exists at all.
# A bare `json.dumps` codec raises `TypeError` on the first `datetime`/`Decimal`
# a caller hands it, which is precisely why callers were pre-serializing with
# their own `json.dumps(..., default=str)` before binding to a jsonb
# placeholder. With that pre-serialized string bound to the parameter, the
# codec then serializes it a SECOND time and Postgres stores a JSONB *string
# scalar* instead of the intended object/array (2026-08-27 GARUDA VOA
# incident — see `init_asyncpg_connection` below and
# `backend/tests/fixtures/prod_shaped_pool.py`).
#
# `default=str` makes this codec a strict superset of every caller's own
# `default=str` serializer: a caller can now hand it a native Python
# container (dict/list, possibly containing datetimes/Decimals) and never
# pre-serialize at all. Any caller that still calls `json.dumps` before
# binding to a jsonb/json parameter is being broken by this codec, not
# protected by it — the codec will encode the resulting string as a JSON
# string literal, not parse it back into an object.
JSONB_ENCODER = functools.partial(json.dumps, default=str)


async def init_asyncpg_connection(conn: asyncpg.Connection) -> None:
    """The canonical `init=` hook for every asyncpg pool in this repo.

    Registers the `jsonb` and `json` type codecs with `JSONB_ENCODER` /
    `json.loads`. This is the SINGLE registration point: every pool this
    codebase creates (the full `rag`-process pool in
    `service_initializer.py::_initialize_database`, the light `api`-process
    pool in `service_initializer.py::initialize_services_light`, the
    standalone `get_db_pool()` below, and the test fixture in
    `backend/tests/fixtures/prod_shaped_pool.py`) must pass THIS object to
    `asyncpg.create_pool(init=...)` — directly, or by awaiting it from its
    own thin wrapper that adds pool-specific extras (a statement timeout, a
    validation `SELECT 1`) on top.

    Deliberately narrow: codec registration only. No `SET statement_timeout`,
    no `SELECT 1` validation — those are call-site concerns (some pools want
    a 30s statement timeout, `get_db_pool()` here does not; some callers want
    a connectivity probe on every new connection, others do not). Baking them
    in here would make this function do two unrelated jobs and would force
    every future caller to accept both.
    """
    await conn.set_type_codec(
        "jsonb",
        encoder=JSONB_ENCODER,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=JSONB_ENCODER,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def get_db_pool() -> asyncpg.Pool:
    """
    Get a standalone database pool for scripts/testing.

    Pool hardening:
    - command_timeout: kills queries running longer than 60s
    - max_inactive_connection_lifetime: recycles idle connections after 5 min
      (prevents stale connections after Fly.io network blips)
    - statement_cache_size=0: required for PgBouncer transaction mode
    """

    pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=_POOL_MIN_SIZE,
        max_size=_POOL_MAX_SIZE,
        command_timeout=_COMMAND_TIMEOUT,
        max_inactive_connection_lifetime=_MAX_INACTIVE_CONN_LIFETIME,
        init=init_asyncpg_connection,
        # Required for PgBouncer transaction mode — prevents prepared statement leak
        statement_cache_size=0,
    )
    logger.info(
        "DB pool created: min=%s, max=%s, cmd_timeout=%ss, idle_recycle=%ss",
        _POOL_MIN_SIZE,
        _POOL_MAX_SIZE,
        _COMMAND_TIMEOUT,
        _MAX_INACTIVE_CONN_LIFETIME,
    )
    return pool
