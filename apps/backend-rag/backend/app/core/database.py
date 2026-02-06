import json
import logging

import asyncpg

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


async def get_db_pool() -> asyncpg.Pool:
    """
    Get a standalone database pool for scripts/testing.
    """

    async def init_db_connection(conn):
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=5,
        command_timeout=60,
        init=init_db_connection,
    )
