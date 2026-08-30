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
    `json.loads`. This is the SINGLE registration point for every pool that
    registers a jsonb/json codec at all: the full `rag`-process pool in
    `service_initializer.py::_initialize_database`, the light `api`-process
    pool in `service_initializer.py::initialize_services_light`, the
    standalone `get_db_pool()` below, the KG staging-promotion job's pool in
    `backend/scripts/kg_staging_promotion.py`, and the test fixture in
    `backend/tests/fixtures/prod_shaped_pool.py`. Each passes THIS object to
    `asyncpg.create_pool(init=...)` — directly, or by awaiting it from its
    own thin wrapper that adds pool-specific extras (a statement timeout, a
    validation `SELECT 1`) on top.

    SCOPED DELIBERATELY, because the previous wording said "every pool this
    codebase creates" and that was FALSE (corrected 2026-08-30 after a blind
    cross-family refuter found the kg_staging_promotion pool registering its
    own codecs with a bare `json.dumps`). Five further `asyncpg.create_pool`
    call sites outside the test tree register NO codec at all and are NOT
    converted here: `app/intake_review_reader.py`,
    `core/legal/hierarchical_indexer.py`, `app/routers/admin_zoho_auth.py`
    (x2), `app/routers/admin_drive_health.py`, and
    `migrations/migration_084a_nlm_verification_log.py`. Measured, not
    assumed: none of the five references `garuda_orders`, `garuda_portal`,
    `journal` or `idempotency`, so none can reach the four writers that now
    bind native containers. A pool with no codec has a DIFFERENT failure mode
    from one with a bare-`json.dumps` codec — it cannot bind a `dict` at all
    (loud `DataError`) rather than silently storing a string scalar — so it is
    not this lane's defect class. Converting them is real work with its own
    blast radius, not a rider on this diff. If you add a jsonb write path to
    any of the five, import this hook rather than writing a sixth codec.

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
