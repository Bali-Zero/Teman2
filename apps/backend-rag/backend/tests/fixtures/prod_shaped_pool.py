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

Deliberately NOT a general-purpose fixture: this mirrors production's
connection init and nothing else. If production's `init` gains a step, add it
here in the same commit -- that is the whole point of one factory.
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


async def create_prod_shaped_pool(
    dsn: str, *, min_size: int = 1, max_size: int = 4
) -> asyncpg.Pool:
    """A pool whose connections encode jsonb the way production's do."""
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        init=init_prod_shaped_connection,
    )
