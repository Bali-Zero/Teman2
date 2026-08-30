"""One asyncpg pool factory for integration tests, shaped like production.

WHY THIS EXISTS. Six integration-test files each built their own
`asyncpg.create_pool(dsn, min_size=1, max_size=4)` with no `init=` hook. Both
production pools -- `service_initializer.py::initialize_services_light` for the
`api` process and `init_db_connection` for `rag` -- register a `jsonb` type
codec whose encoder is `json.dumps`. The test pools did not. So test and
production disagreed about how a `jsonb` parameter is encoded, and every test
that wrote jsonb was verifying a code path production never executes.

That gap was not theoretical. On 2026-08-27 GARUDA VOA's first customer action
answered HTTP 500 in production for every request shape, while
`test_check_to_order_journey.py` passed 10/10 against a real Postgres with the
real migration and the real trigger. The store pre-serialized `reason_codes`
with `json.dumps` and the production codec serialized it a second time, landing
a JSONB scalar string where migration 286's CHECK constraint calls
`jsonb_array_length()` -- SQLSTATE 22023. The test pool, lacking the codec,
passed the string straight through as JSON text and stored a correct array.
Two green paths, the same input, different answers.

So: integration tests acquire their pool HERE. A pool built inline in a test
file is, by construction, a pool that can drift from production again.

WHAT IS MIRRORED, AND WHAT IS NOT. Stated exactly, because the defect this
file exists to catch was born of a comment that claimed more than its code did.

Mirrored, because both production pools set it identically:
  * the `jsonb` and `json` type codecs (the load-bearing one)
  * `SET statement_timeout = '30s'`
  * `statement_cache_size=0`
  * `max_inactive_connection_lifetime=30.0`

NOT mirrored, deliberately:
  * `command_timeout` -- the two production pools DISAGREE (60s on `api`,
    30s-or-settings on `rag`), so there is no single value to mirror. A test
    that depends on it must set it explicitly and say why.
  * `min_size`/`max_size` -- production is 2/10; callers here pass small values
    on purpose, and a test that needs concurrency should ask for it.
  * TLS -- production may attach an `ssl` context; local test Postgres does not.

If production's `init` gains a step that both pools share, add it here in the
same commit. If the two pools disagree about it, add it to this list instead of
picking one -- a fixture that silently picks is worse than one that abstains.
"""

from __future__ import annotations

import json

import asyncpg


async def init_prod_shaped_connection(conn: asyncpg.Connection) -> None:
    """Exactly what production does to every new connection.

    Kept as its own function (not inlined into the pool factory) so a test can
    assert on it, and so the diff against production's own init hook is a
    two-file read rather than an archaeology exercise.
    """
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
    # Both production inits also do this, identically. Added after an
    # adversarial review pointed out that this module PROMISED to mirror
    # production's init and then mirrored only the codecs -- the same
    # over-claiming comment that caused the bug this file exists to catch.
    await conn.execute("SET statement_timeout = '30s'")


async def create_prod_shaped_pool(
    dsn: str, *, min_size: int = 1, max_size: int = 4
) -> asyncpg.Pool:
    """A pool whose connections encode jsonb the way production's do."""
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        init=init_prod_shaped_connection,
        # Identical on BOTH production pools, so mirrored here.
        statement_cache_size=0,
        max_inactive_connection_lifetime=30.0,
    )
