"""The dual-capability check must be proven against a REAL Postgres.

`test_operational_preflight.py` drives `collect_preflight_checks` through a
hand-written fake whose `fetchval` returns a preset value the moment it sees
``string_agg`` in the query text. That fake answers identically whether or not
the query carries ``AND NOT role.rolsuper`` -- the test and the code share the
same imagination (scar #9 / W114), so no assertion made against it can settle
whether this predicate is right.

So this file does not use the fake. It creates a throwaway database, creates
the two capability roles, and creates two logins that both hold BOTH
capabilities by the only two routes that exist: one by an actual GRANT, one by
being a superuser. Then it runs the shipped query -- extracted from the module
rather than retyped, so the test cannot drift from the code it guards -- and
asserts the granted login is reported and the superuser is not.

Guilt and innocence in one pass:
  * innocence -- `postgres`, and any superuser, must NOT be reported, because
    `pg_has_role` answers true for a superuser against every role whether or
    not a grant exists. Before the fix this made the gate structurally unable
    to return 0 on any real install.
  * guilt -- a NON-superuser login that genuinely holds both capabilities MUST
    still be reported. A fix that silenced the check entirely would pass the
    innocence case alone.
"""

from __future__ import annotations

import os
import re
import uuid

import asyncpg
import pytest
import pytest_asyncio

from backend.scripts.visa_engine import operational_preflight

pytestmark = [pytest.mark.integration]

_ADMIN_URL = (
    os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/postgres").rsplit(
        "/", 1
    )[0]
    + "/postgres"
)


def _shipped_dual_capability_query() -> str:
    """Read the query out of the shipped module, never a retyped copy.

    A retyped query would let the module drift while this test kept passing --
    the same failure mode as the fake, one level up.
    """

    source = operational_preflight.collect_preflight_checks.__code__.co_consts
    candidates = [
        const
        for const in source
        if isinstance(const, str) and "string_agg" in const and "pg_has_role" in const
    ]
    assert len(candidates) == 1, (
        "expected exactly one dual-capability query literal in "
        f"collect_preflight_checks, found {len(candidates)}"
    )
    return candidates[0]


@pytest_asyncio.fixture
async def dual_capability_sandbox():
    suffix = uuid.uuid4().hex[:12]
    db_name = f"nuzantara_test_preflight_{suffix}"
    granted = f"vo_granted_{suffix}"
    superuser = f"vo_super_{suffix}"
    pack_writer = f"visa_pack_writer_{suffix}"
    activation = f"visa_activation_executor_{suffix}"

    admin = await asyncpg.connect(_ADMIN_URL)
    try:
        await admin.execute(f'CREATE DATABASE "{db_name}"')
        await admin.execute(f'CREATE ROLE "{pack_writer}" NOLOGIN')
        await admin.execute(f'CREATE ROLE "{activation}" NOLOGIN')
        await admin.execute(f'CREATE ROLE "{granted}" LOGIN')
        await admin.execute(f'GRANT "{pack_writer}", "{activation}" TO "{granted}"')
        await admin.execute(f'CREATE ROLE "{superuser}" LOGIN SUPERUSER')
    finally:
        await admin.close()

    dsn = _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"
    try:
        yield {
            "dsn": dsn,
            "granted": granted,
            "superuser": superuser,
            "pack_writer": pack_writer,
            "activation": activation,
        }
    finally:
        admin = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                db_name,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            for role in (granted, superuser, pack_writer, activation):
                await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        finally:
            await admin.close()


@pytest.mark.asyncio
async def test_superuser_is_not_reported_but_a_genuinely_granted_login_is(
    dual_capability_sandbox: dict,
) -> None:
    sandbox = dual_capability_sandbox
    query = _shipped_dual_capability_query().replace(
        "'visa_pack_writer'", f"'{sandbox['pack_writer']}'"
    ).replace("'visa_activation_executor'", f"'{sandbox['activation']}'")

    connection = await asyncpg.connect(sandbox["dsn"])
    try:
        reported = await connection.fetchval(query)
        reported_names = set((reported or "").split(", ")) - {""}

        # GUILT: the login that really holds both capabilities must be caught.
        assert sandbox["granted"] in reported_names, (
            "a non-superuser login holding BOTH capabilities by real GRANT was "
            f"not reported -- the check has been silenced, not fixed: {reported!r}"
        )
        # INNOCENCE: the superuser must not be, and neither must `postgres`.
        assert sandbox["superuser"] not in reported_names, (
            "a superuser was reported as combining capabilities -- pg_has_role "
            f"answers true for superusers against any role: {reported!r}"
        )
        assert "postgres" not in reported_names, reported

        # And the reason the superuser is innocent is that no grant exists:
        # asserted directly, so the innocence case cannot pass for a wrong
        # reason (e.g. a typo in the role name making the whole query empty).
        real_grant = await connection.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_auth_members AS am
                  JOIN pg_roles AS granted_role ON granted_role.oid = am.roleid
                  JOIN pg_roles AS member ON member.oid = am.member
                 WHERE member.rolname = $1 AND granted_role.rolname = $2
            )
            """,
            sandbox["superuser"],
            sandbox["pack_writer"],
        )
        assert real_grant is False
    finally:
        await connection.close()


def test_the_shipped_query_excludes_superusers() -> None:
    """A cheap structural backstop for environments without a live Postgres.

    Deliberately NOT the only coverage -- on its own this is a text match, and
    a text match cannot tell whether the predicate works. It exists so that a
    CI shard that skips integration tests still fails if the exclusion is
    deleted.
    """

    query = _shipped_dual_capability_query()
    assert re.search(r"NOT\s+role\.rolsuper", query), query
