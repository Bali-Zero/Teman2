"""Parity tests for the canonical asyncpg jsonb codec (L12-PR1, 2026-08-29).

The disease this file guards against: three asyncpg pools
(`backend/app/core/database.py::get_db_pool`, both pool paths in
`backend/app/setup/service_initializer.py`) each registered a `jsonb`/`json`
type codec with a BARE `json.dumps` encoder. Four caller sites
(`garuda_orders/journal.py` x2, `garuda_orders/idempotency.py`,
`garuda_portal/idempotency.py`) pre-serialized with
`json.dumps(..., default=str)` before binding to a jsonb placeholder because
the bare codec would raise `TypeError` on the first `datetime`/`Decimal`. With
the codec active that pre-serialization is WRONG, not merely redundant:
asyncpg encodes the already-serialized string a SECOND time and Postgres
stores a JSONB *string scalar* instead of the intended object/array
(2026-08-27 GARUDA VOA incident — see `backend/tests/fixtures/prod_shaped_pool.py`
and the `test_jsonb_double_encoding_class_guard.py` registry in this same
directory).

The cure widens the codec's encoder to `JSONB_ENCODER =
functools.partial(json.dumps, default=str)` — a strict superset of every
caller's own `default=str` serializer — and makes it the ONE object every
pool (`database.py`, both `service_initializer.py` paths, and the
`prod_shaped_pool` test fixture) imports and passes to
`asyncpg.create_pool(init=...)`. This file has three parts:

STRUCTURAL (no database, always runs): the encoder object is the right
shape, the identity is shared (not four independent copies that can drift
again the way the pre-2026-08-27 codecs did), and a static AST scan proves no
`set_type_codec` call anywhere in the three canonical files still names a
bare `json.dumps` encoder.

LIVE (in practice ALWAYS runs -- see below): a real round-trip through
`create_prod_shaped_pool` proving (a) a native Python container round-trips
correctly, (b) `default=str` is load-bearing — a container holding a
`datetime`/`Decimal` would raise under the OLD bare codec and now succeeds,
and (c) the scar this whole lane exists to prevent a false cure for: a
PRE-serialized string still lands as a JSONB string scalar whether bound bare
or through an explicit `::jsonb` cast. That cast is NOT a bypass of the
codec's double-encoding behavior — measured against a real Postgres
2026-08-27, pinned here so a future reader cannot re-derive the disproven
"the cast protects us" claim.

CORRECTED 2026-08-30 (was: "skipped unless TEST_DATABASE_URL is set", an
over-claim of the same class this file exists to punish). The `skipif`
below is real code, but the skip it guards is UNREACHABLE in this repo's
own test tree: `backend/tests/conftest.py:42-48` runs
`os.environ.setdefault("TEST_DATABASE_URL", "postgresql://nuzantara@"
"localhost:5432/nuzantara_test")` at collection time, before this module is
even imported, so the variable is ALWAYS set by the time `_live_only` is
evaluated. In THIS repo's pytest, the live half always runs -- against
whatever Postgres that default (or an operator/CI override) resolves to --
never against "no database". The `skipif` is belt-and-braces for a
conftest-less invocation (importing this file directly outside pytest, or
a future test runner that does not carry that root conftest), not a real
day-to-day escape hatch.

REAL-CALL-SITE PROOF (added 2026-08-30, closes the proof-of-armed the
PENDING-ARMS row at `.claude/skills/modus/PENDING-ARMS.md` ~line 1462
actually asked for). The temp-table tests above prove the CODEC works
against an arbitrary jsonb column; they do not touch the four real
production call sites the row names by column: `garuda_order_journal.detail`,
`garuda_order_outbox.payload`, and both `response_body` columns
(`garuda_order_idempotency`, `garuda_magic_link_idempotency`). The third
part below drives `journal.append_event`, `journal.enqueue_outbox`,
`garuda_orders.idempotency.complete`, and `garuda_portal.idempotency.complete`
-- the ACTUAL functions this lane's caller-site fix touched -- against those
FOUR REAL tables, and asserts `jsonb_typeof` is `object` (never `string`) on
each. Rows are deleted in a `finally` wherever the schema allows it
(`garuda_orders`, `garuda_order_outbox`); THREE of the four target tables
structurally forbid it and the rows are left in place, tagged
`jsonbparity-`, DOCUMENTED per-test rather than silently omitted:
`garuda_order_journal` is append-only (migration 284
`guard_garuda_order_journal_append_only` raises on ANY UPDATE OR DELETE),
and both `garuda_order_idempotency` and `garuda_magic_link_idempotency`
forbid DELETE while unexpired (migrations 284/285's own
`guard_*_idempotency_mutation`, +30 days / +1 day from INSERT
respectively) -- an idempotency replay cache that could be wiped by
whoever is testing it would not protect a real retry. This is the correct
behavior of the real production code path, not a test-hygiene gap: a
`finally: DELETE ...` was tried first and it raised
`asyncpg.exceptions.RaiseError` on both idempotency tables, which is how
this was discovered, not assumed. Each test skips CLEANLY -- not a failure
-- if its required table is absent, so this file stays usable against a
`TEST_DATABASE_URL` target that has not run the GARUDA migrations.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest

from backend.app.core import database as database_module
from backend.app.setup import service_initializer as service_initializer_module
from backend.services.garuda_orders import idempotency as garuda_orders_idempotency
from backend.services.garuda_orders import journal as garuda_orders_journal
from backend.services.garuda_portal import idempotency as garuda_portal_idempotency
from backend.tests.fixtures import prod_shaped_pool as prod_shaped_pool_module
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

_live_only = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set",
)

# backend/tests/db/.. -> backend/ (same convention as
# test_jsonb_double_encoding_class_guard.py in this directory).
BACKEND_ROOT = Path(__file__).resolve().parents[2]

_CANONICAL_CODEC_FILES = (
    BACKEND_ROOT / "app" / "core" / "database.py",
    BACKEND_ROOT / "app" / "setup" / "service_initializer.py",
    BACKEND_ROOT / "tests" / "fixtures" / "prod_shaped_pool.py",
)


# --------------------------------------------------------------------------
# STRUCTURAL — no database required.
# --------------------------------------------------------------------------


def test_jsonb_encoder_is_json_dumps_with_default_str() -> None:
    """`JSONB_ENCODER` is `json.dumps` widened by `default=str` — not a
    different serializer, and not bare `json.dumps` re-exported under a new
    name (either of which would silently reintroduce the disease)."""
    encoder = database_module.JSONB_ENCODER
    assert isinstance(encoder, functools.partial)
    assert encoder.func is json.dumps
    assert encoder.keywords.get("default") is str
    assert encoder.args == ()


def test_jsonb_encoder_widens_bare_json_dumps() -> None:
    """The whole reason `default=str` exists: a value bare `json.dumps`
    cannot serialize must succeed through `JSONB_ENCODER`, or callers are
    forced back into pre-serializing (the exact anti-pattern this lane
    removes from `garuda_orders/journal.py` and both `idempotency.py` files).
    """
    value = {"when": datetime(2026, 1, 1, tzinfo=timezone.utc), "amount": Decimal("12.50")}

    with pytest.raises(TypeError):
        json.dumps(value)

    encoded = database_module.JSONB_ENCODER(value)
    assert isinstance(encoded, str)
    decoded = json.loads(encoded)
    assert decoded["amount"] == "12.50"
    assert decoded["when"] == "2026-01-01 00:00:00+00:00"


def test_prod_shaped_pool_imports_the_canonical_initializer_by_identity() -> None:
    """Not "an equivalent copy" — the SAME function object. A fixture that
    re-implements `set_type_codec` calls of its own can drift from
    production the way the pre-2026-08-29 duplicate did; importing the name
    makes drift structurally impossible without editing this import."""
    assert (
        prod_shaped_pool_module.init_asyncpg_connection
        is database_module.init_asyncpg_connection
    )


def test_service_initializer_imports_the_canonical_initializer_by_identity() -> None:
    """Both `service_initializer.py` pool paths call
    `init_asyncpg_connection(conn)` (imported at module level from
    `backend.app.core.database`), never their own `set_type_codec`."""
    assert (
        service_initializer_module.init_asyncpg_connection
        is database_module.init_asyncpg_connection
    )


def _encoder_kwarg_is_canonical(node: ast.expr) -> bool:
    """True iff `node` names (directly or via `module.JSONB_ENCODER`) the
    one canonical encoder — never a bare `json.dumps`/`json.dumps` lambda/
    anything else."""
    if isinstance(node, ast.Name):
        return node.id == "JSONB_ENCODER"
    if isinstance(node, ast.Attribute):
        return node.attr == "JSONB_ENCODER"
    return False


def _set_type_codec_violations(path: Path) -> list[str]:
    """Every `conn.set_type_codec(...)` call in `path` whose `encoder=`
    keyword is missing or is not the canonical `JSONB_ENCODER` object,
    formatted as `path:line: <reason>`.

    AST-based, not regex — this is the tripwire the PR asked for: it must
    fire if anyone reintroduces `encoder=json.dumps` in any of the three
    canonical files, including inside a helper this test's authors did not
    anticipate.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "set_type_codec"):
            continue
        encoder_kw = next((kw for kw in node.keywords if kw.arg == "encoder"), None)
        if encoder_kw is None:
            violations.append(f"{path}:{node.lineno}: set_type_codec call has no encoder= keyword")
            continue
        if not _encoder_kwarg_is_canonical(encoder_kw.value):
            violations.append(
                f"{path}:{node.lineno}: set_type_codec encoder= is not JSONB_ENCODER "
                f"(got {ast.dump(encoder_kw.value)})"
            )
    return violations


def test_no_bare_json_dumps_set_type_codec_encoder_anywhere_canonical() -> None:
    """GUILT-side source scan: none of the three files that are allowed to
    call `set_type_codec` at all may do so with a bare/non-canonical
    encoder. `database.py` is expected to contain the two calls that
    register `JSONB_ENCODER` itself — those must pass; `service_initializer.py`
    and `prod_shaped_pool.py` are expected to contain ZERO `set_type_codec`
    calls at all post-2026-08-29 (they delegate to `init_asyncpg_connection`),
    so they pass vacuously. A future PR that reintroduces
    `encoder=json.dumps` in ANY of the three must fail this test."""
    all_violations: list[str] = []
    for path in _CANONICAL_CODEC_FILES:
        assert path.exists(), f"expected canonical codec file missing: {path}"
        all_violations.extend(_set_type_codec_violations(path))
    assert not all_violations, "\n".join(all_violations)


def test_scanner_actually_detects_a_bare_encoder(tmp_path: Path) -> None:
    """Self-test of `_set_type_codec_violations`: a scanner that always
    returns `[]` would make the guilt test above vacuous. Prove it fires on
    the exact pre-2026-08-29 shape before trusting it to stay silent on the
    real files."""
    guilty = tmp_path / "guilty.py"
    guilty.write_text(
        "import json\n"
        "import asyncpg\n"
        "\n"
        "async def init_db_connection(conn: asyncpg.Connection) -> None:\n"
        "    await conn.set_type_codec(\n"
        "        'jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'\n"
        "    )\n"
    )
    violations = _set_type_codec_violations(guilty)
    assert len(violations) == 1
    assert "guilty.py:5" in violations[0]

    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        "import asyncpg\n"
        "from backend.app.core.database import JSONB_ENCODER\n"
        "\n"
        "async def init_db_connection(conn: asyncpg.Connection) -> None:\n"
        "    await conn.set_type_codec(\n"
        "        'jsonb', encoder=JSONB_ENCODER, decoder=None, schema='pg_catalog'\n"
        "    )\n"
    )
    assert _set_type_codec_violations(innocent) == []


# --------------------------------------------------------------------------
# LIVE — requires TEST_DATABASE_URL (a real Postgres).
# --------------------------------------------------------------------------


def _probe_table_name() -> str:
    return f"_jsonb_codec_parity_probe_{uuid.uuid4().hex[:8]}"


@_live_only
@pytest.mark.asyncio
async def test_native_python_list_round_trips_as_jsonb_array() -> None:
    """INNOCENCE: a native Python container (never `json.dumps`-ed by the
    caller) round-trips through `create_prod_shaped_pool` as a real JSONB
    array, structurally equal on the way back out."""
    pool = await create_prod_shaped_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    table = _probe_table_name()
    try:
        async with pool.acquire() as conn:
            await conn.execute(f"CREATE TABLE {table} (id serial primary key, payload jsonb)")
            native = [1, "two", {"three": 3}]
            await conn.execute(f"INSERT INTO {table} (payload) VALUES ($1)", native)

            typeof = await conn.fetchval(f"SELECT jsonb_typeof(payload) FROM {table}")
            assert typeof == "array"

            round_tripped = await conn.fetchval(f"SELECT payload FROM {table}")
            assert round_tripped == native
    finally:
        async with pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
        await pool.close()


@_live_only
@pytest.mark.asyncio
async def test_native_dict_with_datetime_and_decimal_succeeds_via_default_str() -> None:
    """INNOCENCE 2 — the `default=str` proof: a native dict containing a
    `datetime` and a `Decimal` INSERTs successfully and lands as a JSONB
    object. Under the pre-2026-08-29 bare `json.dumps` codec this raised
    `TypeError` inside asyncpg's own encoder, which is exactly why callers
    were pre-serializing with their own `default=str` before this lane."""
    pool = await create_prod_shaped_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    table = _probe_table_name()
    try:
        async with pool.acquire() as conn:
            await conn.execute(f"CREATE TABLE {table} (id serial primary key, payload jsonb)")
            native = {
                "occurred_at": datetime(2026, 8, 29, tzinfo=timezone.utc),
                "amount": Decimal("199.99"),
            }
            await conn.execute(f"INSERT INTO {table} (payload) VALUES ($1)", native)

            typeof = await conn.fetchval(f"SELECT jsonb_typeof(payload) FROM {table}")
            assert typeof == "object"
    finally:
        async with pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
        await pool.close()


@_live_only
@pytest.mark.asyncio
async def test_pre_serialized_string_still_becomes_jsonb_string_scalar() -> None:
    """SCAR / CONTRAST: a caller that STILL pre-serializes with `json.dumps`
    before binding to a jsonb placeholder is double-encoded by the codec —
    with `default=str` in place this is now the ONLY way to reintroduce the
    2026-08-27 disease, and it must still be caught structurally.

    Pins the 2026-08-27 measurement: binding the SAME pre-serialized string
    to a bare `$N` placeholder and to an explicit `$N::jsonb` cast BOTH store
    `jsonb_typeof = 'string'`. The `::jsonb` cast is NOT a bypass of the
    codec's double-encoding behavior — a future reader must not re-derive
    "the cast protects us" from first principles; it was measured false
    against a real Postgres and is pinned here.
    """
    pool = await create_prod_shaped_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    table = _probe_table_name()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                f"CREATE TABLE {table} "
                "(id serial primary key, bare_payload jsonb, cast_payload jsonb)"
            )
            pre_serialized = json.dumps([1, 2, 3])
            await conn.execute(
                f"INSERT INTO {table} (bare_payload, cast_payload) VALUES ($1, $2::jsonb)",
                pre_serialized,
                pre_serialized,
            )

            row = await conn.fetchrow(
                f"SELECT jsonb_typeof(bare_payload) AS bare_type, "
                f"jsonb_typeof(cast_payload) AS cast_type FROM {table}"
            )
            assert row["bare_type"] == "string", (
                "a pre-serialized string bound to a bare jsonb placeholder must "
                "still be double-encoded into a JSONB string scalar by the codec"
            )
            assert row["cast_type"] == "string", (
                "the `::jsonb` cast does not route around the codec's own "
                "encode step -- it is NOT an escape hatch (measured 2026-08-27)"
            )
    finally:
        async with pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
        await pool.close()


# --------------------------------------------------------------------------
# REAL CALL-SITE PROOF -- the four production writers, the four real tables.
# See the module docstring's "REAL-CALL-SITE PROOF" paragraph for why this
# section exists on top of the temp-table tests above.
# --------------------------------------------------------------------------


async def _table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = $1)",
            table_name,
        )
    )


@_live_only
@pytest.mark.asyncio
async def test_journal_append_event_writes_a_real_jsonb_object_on_garuda_order_journal() -> None:
    """`garuda_orders/journal.py::append_event` -> `garuda_order_journal.detail`.

    Covers the `datetime` half of "include a datetime or Decimal in at
    least one payload": a `detail` dict holding a `datetime` would raise
    `TypeError` inside the OLD bare-`json.dumps` codec, which is exactly
    why this call site used to pre-serialize with its own `default=str`.
    """
    pool = await create_prod_shaped_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            if not await _table_exists(conn, "garuda_order_journal"):
                pytest.skip("garuda_order_journal not present in TEST_DATABASE_URL target")

            aggregate_id = f"jsonbparity-order-{uuid.uuid4().hex[:12]}"
            event_id = await garuda_orders_journal.append_event(
                conn,
                event_name="jsonb_codec_parity.probe",
                aggregate_type="order",
                aggregate_id=aggregate_id,
                transition_id="OP-00",
                customer_visible=False,
                detail={
                    "probe": "jsonb_codec_parity",
                    "occurred_at": datetime(2026, 8, 30, tzinfo=timezone.utc),
                },
            )
            # NOTE: garuda_order_journal is append-only -- migration 284's
            # trg_guard_garuda_order_journal_append_only raises on ANY
            # UPDATE OR DELETE, unconditionally. This row is deliberately
            # NOT cleaned up (there is no code path that could clean it up);
            # the jsonbparity- prefix on aggregate_id/event_name marks it as
            # test noise for anyone auditing the table.
            typeof = await conn.fetchval(
                "SELECT jsonb_typeof(detail) FROM garuda_order_journal WHERE event_id = $1",
                event_id,
            )
            assert typeof == "object", (
                f"garuda_order_journal.detail has jsonb_typeof={typeof!r}, expected "
                "'object' -- journal.append_event no longer hands the codec a native "
                "dict, or the codec regressed"
            )
    finally:
        await pool.close()


@_live_only
@pytest.mark.asyncio
async def test_journal_enqueue_outbox_writes_a_real_jsonb_object_on_garuda_order_outbox() -> None:
    """`garuda_orders/journal.py::enqueue_outbox` -> `garuda_order_outbox.payload`.

    Covers the `Decimal` half of the same requirement. `garuda_order_outbox`
    FK-references `garuda_orders`/`garuda_order_journal`, so this test seeds
    a minimal synthetic order row (deleted in the `finally`) -- the journal
    row it also creates is append-only and left in place, same as the test
    above.
    """
    pool = await create_prod_shaped_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    order_id = f"jsonbparity-order-{uuid.uuid4().hex[:12]}"
    try:
        async with pool.acquire() as conn:
            if not await _table_exists(conn, "garuda_order_outbox") or not await _table_exists(
                conn, "garuda_orders"
            ):
                pytest.skip(
                    "garuda_order_outbox/garuda_orders not present in TEST_DATABASE_URL target"
                )

            await conn.execute(
                """
                INSERT INTO garuda_orders
                    (order_id, result_id_ref, case_type, applicant_full_name,
                     applicant_email, applicant_phone, applicant_passport_number,
                     price_idr, price_catalogue_key)
                VALUES ($1, $2, 'issuance', 'JSONB Codec Parity Probe',
                        'jsonbparity-probe@example.com', '+00000000000',
                        'X0000000', 100000, 'jsonbparity-catalogue-key')
                """,
                order_id,
                f"jsonbparity-result-{uuid.uuid4().hex[:12]}",
            )
            try:
                event_id = await garuda_orders_journal.append_event(
                    conn,
                    event_name="jsonb_codec_parity.probe",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    transition_id="OP-00",
                    customer_visible=False,
                    detail={},
                )
                await garuda_orders_journal.enqueue_outbox(
                    conn,
                    order_id=order_id,
                    journal_event_id=event_id,
                    job_type="jsonb_codec_parity_probe",
                    payload={
                        "probe": "jsonb_codec_parity",
                        "amount": Decimal("199.99"),
                    },
                )
                typeof = await conn.fetchval(
                    "SELECT jsonb_typeof(payload) FROM garuda_order_outbox "
                    "WHERE journal_event_id = $1 AND job_type = 'jsonb_codec_parity_probe'",
                    event_id,
                )
                assert typeof == "object", (
                    f"garuda_order_outbox.payload has jsonb_typeof={typeof!r}, expected "
                    "'object' -- journal.enqueue_outbox no longer hands the codec a "
                    "native dict, or the codec regressed"
                )
            finally:
                await conn.execute(
                    "DELETE FROM garuda_order_outbox WHERE order_id = $1", order_id
                )
                await conn.execute("DELETE FROM garuda_orders WHERE order_id = $1", order_id)
                # garuda_order_journal row: append-only, left in place (see
                # the test above).
    finally:
        await pool.close()


@_live_only
@pytest.mark.asyncio
async def test_garuda_orders_idempotency_complete_writes_a_real_jsonb_object() -> None:
    """`garuda_orders/idempotency.py::complete` -> `garuda_order_idempotency.response_body`.

    `complete()` is an UPDATE, not an INSERT -- `reserve()` must run first
    to create the row (the same order the real `create_order_and_checkout`
    flow calls them in). `order_id` is nullable on this table, so no
    `garuda_orders` row is needed here.

    NOT cleaned up in a `finally`, and this is not an oversight: migration
    284's `guard_garuda_order_idempotency_mutation` raises `'unexpired
    garuda_order_idempotency rows are immutable'` on ANY DELETE while
    `clock_timestamp() < expires_at` (default +30 days from INSERT) --
    there is no way to delete a row this test just created without
    bypassing the exact guard the real replay-cache relies on. Tagged with
    a `jsonbparity-` key derivation so it is identifiable as test noise.
    """
    pool = await create_prod_shaped_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    key_sha256 = hashlib.sha256(f"jsonbparity-orders-{uuid.uuid4().hex}".encode()).digest()
    try:
        async with pool.acquire() as conn:
            if not await _table_exists(conn, "garuda_order_idempotency"):
                pytest.skip("garuda_order_idempotency not present in TEST_DATABASE_URL target")

            payload_sha256 = hashlib.sha256(b"jsonbparity-orders-payload").digest()
            await garuda_orders_idempotency.reserve(
                conn, key_sha256=key_sha256, payload_sha256=payload_sha256
            )
            await garuda_orders_idempotency.complete(
                conn,
                key_sha256=key_sha256,
                response_status=201,
                response_body={
                    "probe": "jsonb_codec_parity",
                    "issued_at": datetime(2026, 8, 30, tzinfo=timezone.utc),
                },
            )
            typeof = await conn.fetchval(
                "SELECT jsonb_typeof(response_body) FROM garuda_order_idempotency "
                "WHERE key_sha256 = $1",
                key_sha256,
            )
            assert typeof == "object", (
                f"garuda_order_idempotency.response_body has jsonb_typeof={typeof!r}, "
                "expected 'object' -- idempotency.complete no longer hands the codec "
                "a native dict, or the codec regressed"
            )
    finally:
        await pool.close()


@_live_only
@pytest.mark.asyncio
async def test_garuda_portal_idempotency_complete_writes_a_real_jsonb_object() -> None:
    """`garuda_portal/idempotency.py::complete` -> `garuda_magic_link_idempotency.response_body`.

    Same `reserve()`-then-`complete()` order as the L3 sibling above;
    `garuda_magic_link_idempotency` has no FK at all.

    NOT cleaned up in a `finally`, same reason as the L3 sibling above:
    migration 285's `guard_garuda_magic_link_idempotency_mutation` raises on
    ANY DELETE while unexpired (default +1 day from INSERT).
    """
    pool = await create_prod_shaped_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    key_sha256 = hashlib.sha256(f"jsonbparity-portal-{uuid.uuid4().hex}".encode()).digest()
    try:
        async with pool.acquire() as conn:
            if not await _table_exists(conn, "garuda_magic_link_idempotency"):
                pytest.skip(
                    "garuda_magic_link_idempotency not present in TEST_DATABASE_URL target"
                )

            payload_sha256 = hashlib.sha256(b"jsonbparity-portal-payload").digest()
            await garuda_portal_idempotency.reserve(
                conn, key_sha256=key_sha256, payload_sha256=payload_sha256
            )
            await garuda_portal_idempotency.complete(
                conn,
                key_sha256=key_sha256,
                response_status=200,
                response_body={
                    "probe": "jsonb_codec_parity",
                    "authorized": True,
                    "amount": Decimal("42.00"),
                },
            )
            typeof = await conn.fetchval(
                "SELECT jsonb_typeof(response_body) FROM garuda_magic_link_idempotency "
                "WHERE key_sha256 = $1",
                key_sha256,
            )
            assert typeof == "object", (
                f"garuda_magic_link_idempotency.response_body has jsonb_typeof={typeof!r}, "
                "expected 'object' -- idempotency.complete no longer hands the codec "
                "a native dict, or the codec regressed"
            )
    finally:
        await pool.close()
