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
`asyncpg.create_pool(init=...)`. This file has two halves:

STRUCTURAL (no database, always runs): the encoder object is the right
shape, the identity is shared (not four independent copies that can drift
again the way the pre-2026-08-27 codecs did), and a static AST scan proves no
`set_type_codec` call anywhere in the three canonical files still names a
bare `json.dumps` encoder.

LIVE (skipped unless `TEST_DATABASE_URL` is set): a real round-trip through
`create_prod_shaped_pool` proving (a) a native Python container round-trips
correctly, (b) `default=str` is load-bearing — a container holding a
`datetime`/`Decimal` would raise under the OLD bare codec and now succeeds,
and (c) the scar this whole lane exists to prevent a false cure for: a
PRE-serialized string still lands as a JSONB string scalar whether bound bare
or through an explicit `::jsonb` cast. That cast is NOT a bypass of the
codec's double-encoding behavior — measured against a real Postgres
2026-08-27, pinned here so a future reader cannot re-derive the disproven
"the cast protects us" claim.
"""

from __future__ import annotations

import ast
import functools
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.core import database as database_module
from backend.app.setup import service_initializer as service_initializer_module
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
