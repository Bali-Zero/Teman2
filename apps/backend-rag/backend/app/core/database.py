import logging

import asyncpg

from backend.app.core.config import settings
from backend.core.pg_json_codec import (
    JSONB_ENCODER as JSONB_ENCODER,
)
from backend.core.pg_json_codec import (
    init_asyncpg_connection as init_asyncpg_connection,
)

logger = logging.getLogger(__name__)

# Pool configuration constants
_POOL_MIN_SIZE = 2
_POOL_MAX_SIZE = 5
_COMMAND_TIMEOUT = 60  # seconds — query execution timeout
_MAX_INACTIVE_CONN_LIFETIME = 300  # seconds — idle connections recycled after 5 min
_ACQUIRE_TIMEOUT = 10  # seconds — max wait for a free connection


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
