"""289 must SURVIVE the role that actually runs it in production, not assume ownership.

WHY THIS FILE EXISTS
--------------------
`test_retention_binders_scope_to_visa_decision.py` proves 289 does the right
thing when the applying role owns the two binders. That is the CI world and it
is not the production world.

Measured on production 2026-08-27 (read-only, `nuzantara_readonly`):

    pg_has_role('backend_rag_v2', 'visa_ledger_owner', 'USAGE')  ->  false
    pg_roles.rolsuper for backend_rag_v2                         ->  false
    login roles that ARE members of visa_ledger_owner            ->  flypgadmin,
                                                                    postgres,
                                                                    repmgr
                                                                    (all superusers)

and `bind_visa_decision_retention_policy` /
`bind_visa_evaluate_idempotency_retention_policy` are both owned by
`visa_ledger_owner`.

Migrations connect with `settings.database_url` (`migration_manager.py:96`) --
the SAME DSN the runtime uses, with no `SET ROLE` anywhere in the chain. So the
role that runs `release_command` is `backend_rag_v2`, and
`CREATE OR REPLACE FUNCTION` on a function it does not own raises
`must be owner of function`.

That is not hypothetical. It already happened, on 2026-08-26, to the five
GARUDA migrations -- see the header of
`backend/tests/db/test_post_d1_migrations_guard_ledger_owned_ddl.py`. The
release command failed and **the deploy aborted**, which is a strictly larger
blast radius than the outage being repaired: it blocks every unrelated deploy
too, until someone applies the migrations by hand as a superuser (which is what
has 281/284-287 recorded as applied in production today).

WHAT THE GUARD DOES, AND THE TRAP IT DELIBERATELY AVOIDS
--------------------------------------------------------
289 wraps each `CREATE OR REPLACE FUNCTION` in a `DO $guardN$` block that runs
it only when `pg_has_role(current_user, proowner, 'USAGE')` -- true for the
owner and for any superuser -- and otherwise emits a NOTICE and returns. The
deploy survives.

The obvious objection to that shape is correct and is scar #2 (esiste !=
armato): a migration that no-ops still gets recorded APPLIED, so it is never
retried, and the outage would continue behind a green deploy. That is why the
no-op is NOT the end of the story -- `operational_preflight.py` fails while the
LIVE binder body lacks the `policy_scope` predicate, so the unarmed state is
loud somewhere that is actually read. This file's job is only the narrower
claim: **the migration does not abort the deploy, and it does not lie about
having applied the fix.**

Both directions are asserted here, because a guard that only ever declines is
as broken as one that only ever fires:
  - GUILT     -- non-owner, non-superuser role  -> no exception, NOTICE emitted,
                 binder body UNCHANGED (still scope-blind).
  - INNOCENCE -- owner/superuser role           -> binder body CHANGED (carries
                 the policy_scope predicate).

Run standalone against a local Postgres::

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \\
    PYTHONPATH=. pytest \\
      backend/tests/scripts/visa_engine/test_retention_binder_scope_survives_a_non_owner_runner.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import NamedTuple
from urllib.parse import quote, urlsplit, urlunsplit

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.scripts.visa_engine import fullstack_smoke, operational_preflight

pytestmark = pytest.mark.asyncio

_ADMIN_URL = (
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://nuzantara@localhost:5432/nuzantara_test",
    ).rsplit("/", 1)[0]
    + "/postgres"
)

# Same self-contained subset the sibling file proved standalone-applicable to an
# empty database. 289 is applied SEPARATELY here, by a chosen role -- that is
# the whole point of this file, so it is deliberately absent from this tuple.
_MIGRATIONS_BEFORE_289: tuple[int, ...] = (
    250, 251, 252, 253, 254, 255, 256, 257,
    261, 262, 263, 264, 265, 266, 267, 268,
    276, 281,
)

_LEDGER_BINDERS: tuple[str, ...] = (
    "bind_visa_decision_retention_policy",
    "bind_visa_evaluate_idempotency_retention_policy",
)


def _base_url() -> str:
    return _ADMIN_URL.rsplit("/", 1)[0]


def _resolve_migration(number: int):
    migrations_dir = (
        fullstack_smoke._backend_root() / "backend" / "db" / "migrations_v2"
    )
    matches = sorted(migrations_dir.glob(f"{number}_*.sql"))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one migration {number}, found {[p.name for p in matches]}"
        )
    return matches[0]


def _forward_sql(number: int) -> str:
    forward, _rollback = split_migration_sql(
        _resolve_migration(number).read_text(encoding="utf-8")
    )
    return forward


class _Sandbox(NamedTuple):
    owner_dsn: str
    runtime_dsn: str
    runtime_role: str
    ledger_role: str


@pytest_asyncio.fixture
async def split_ownership_sandbox() -> AsyncIterator[_Sandbox]:
    """A database that reproduces the D1 ownership split.

    The connecting user owns nothing of the ledger; a separate `t_ledger_*`
    role owns the two binders, exactly as `visa_ledger_owner` does in
    production. The `t_runtime_*` login role holds only SELECT, exactly as
    `backend_rag_v2` does (measured: relacl `backend_rag_v2=r/visa_ledger_owner`).
    """

    suffix = uuid.uuid4().hex[:12]
    db_name = f"nuzantara_test_m289_owner_{suffix}"
    ledger_role = f"t_ledger_owner_{suffix}"
    runtime_role = f"t_runtime_{suffix}"
    runtime_password = uuid.uuid4().hex

    admin = await asyncpg.connect(_ADMIN_URL)
    try:
        await admin.execute(f'CREATE DATABASE "{db_name}"')
        await admin.execute(f'CREATE ROLE "{ledger_role}" NOSUPERUSER NOLOGIN')
        await admin.execute(
            f'CREATE ROLE "{runtime_role}" NOSUPERUSER LOGIN '
            f"PASSWORD '{runtime_password}'"
        )
        await admin.execute(f'GRANT CONNECT ON DATABASE "{db_name}" TO "{runtime_role}"')
    finally:
        await admin.close()

    owner_dsn = f"{_base_url()}/{db_name}"
    # Rebuild the DSN rather than string-patching it: the base URL may or may
    # not already carry a username, and a `.replace()` that guesses wrong
    # produces a DSN that silently connects as the WRONG role -- which would
    # make the guilt test pass for the wrong reason.
    parsed = urlsplit(owner_dsn)
    runtime_dsn = urlunsplit(
        (
            parsed.scheme,
            f"{quote(runtime_role, safe='')}:{quote(runtime_password, safe='')}"
            f"@{parsed.hostname}" + (f":{parsed.port}" if parsed.port else ""),
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )

    try:
        yield _Sandbox(
            owner_dsn=owner_dsn,
            runtime_dsn=runtime_dsn,
            runtime_role=runtime_role,
            ledger_role=ledger_role,
        )
    finally:
        admin = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                db_name,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            await admin.execute(f'DROP ROLE IF EXISTS "{runtime_role}"')
            await admin.execute(f'DROP ROLE IF EXISTS "{ledger_role}"')
        finally:
            await admin.close()


async def _build_ledger_owned_schema(sandbox: _Sandbox) -> None:
    """Apply everything before 289, then hand the binders to the ledger role."""

    connection = await asyncpg.connect(sandbox.owner_dsn)
    try:
        for number in _MIGRATIONS_BEFORE_289:
            async with connection.transaction():
                await connection.execute(_forward_sql(number))

        for binder in _LEDGER_BINDERS:
            await connection.execute(
                f'ALTER FUNCTION public.{binder}() OWNER TO "{sandbox.ledger_role}"'
            )
        await connection.execute(
            "GRANT SELECT ON public.visa_decision_retention_policies "
            f'TO "{sandbox.runtime_role}"'
        )
        # USAGE *and* CREATE. Production's `backend_rag_v2` demonstrably holds
        # CREATE on schema public -- it owns `garuda_orders`,
        # `garuda_magic_link_tokens`, `garuda_voa_check_results`,
        # `garuda_practices` and `bind_garuda_magic_link_token_retention_policy`,
        # all created by migrations 284-287. A fixture that withheld CREATE
        # would fail these statements with `permission denied for schema public`
        # instead of `must be owner of function`, i.e. it would prove a
        # STRICTER, different, and non-production restriction -- and the
        # unguarded-statement probe below would pass for the wrong reason.
        await connection.execute(
            f'GRANT USAGE, CREATE ON SCHEMA public TO "{sandbox.runtime_role}"'
        )
    finally:
        await connection.close()


async def _binder_bodies(dsn: str) -> dict[str, str]:
    connection = await asyncpg.connect(dsn)
    try:
        rows = await connection.fetch(
            "SELECT proname, prosrc FROM pg_proc WHERE proname = ANY($1::text[])",
            list(_LEDGER_BINDERS),
        )
        return {row["proname"]: row["prosrc"] for row in rows}
    finally:
        await connection.close()


async def test_289_does_not_abort_the_deploy_when_the_runner_does_not_own_the_binders(
    split_ownership_sandbox: _Sandbox,
) -> None:
    """GUILT: the production shape. A non-owner, non-superuser role applies 289.

    The assertion that matters is the ABSENCE of an exception: on 2026-08-26 an
    exception here is precisely what aborted the deploy for the five GARUDA
    migrations. A NOTICE must be emitted (so the skip is not mute in the
    migration log), and the binder body must be HONESTLY unchanged -- the
    migration must not leave a database that looks repaired and is not.
    """

    await _build_ledger_owned_schema(split_ownership_sandbox)

    before = await _binder_bodies(split_ownership_sandbox.owner_dsn)
    assert before, "fixture built no binders -- the probe would be vacuous"
    for binder, body in before.items():
        assert "policy_scope" not in body, (
            f"{binder} already carries the scope predicate BEFORE 289 -- "
            "this test could not tell a no-op from a real apply"
        )

    connection = await asyncpg.connect(split_ownership_sandbox.runtime_dsn)
    notices: list[str] = []
    try:
        # Prove the fixture really reproduces the production privilege shape,
        # rather than silently handing us an owner. Without this, a broken
        # fixture would make the whole test pass for the wrong reason.
        assert await connection.fetchval("SELECT current_user") == (
            split_ownership_sandbox.runtime_role
        )
        assert await connection.fetchval(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        ) is False
        assert await connection.fetchval(
            "SELECT pg_has_role(current_user, $1, 'USAGE')",
            split_ownership_sandbox.ledger_role,
        ) is False

        connection.add_log_listener(lambda _conn, message: notices.append(str(message)))

        # The load-bearing line: this must NOT raise.
        async with connection.transaction():
            await connection.execute(_forward_sql(289))
    finally:
        await connection.close()

    assert notices, (
        "289 declined silently -- a skip nobody can see in the migration log is "
        "the same failure mode as no guard at all"
    )
    joined = "\n".join(notices)
    for binder in _LEDGER_BINDERS:
        assert binder in joined, f"the NOTICE never names {binder}"
    assert "visa_ledger_owner" in joined or "superuser" in joined, (
        "the NOTICE must name the role that CAN apply it, or it is not actionable"
    )

    after = await _binder_bodies(split_ownership_sandbox.owner_dsn)
    for binder, body in after.items():
        assert "policy_scope" not in body, (
            f"{binder} changed under a role that cannot own it -- impossible, so "
            "the fixture is not reproducing the ownership split"
        )


async def test_an_unguarded_create_or_replace_really_would_abort_the_deploy(
    split_ownership_sandbox: _Sandbox,
) -> None:
    """The danger the guard exists for, reproduced in the same sandbox.

    Without this, the two tests above are consistent with a world where the
    ownership split is harmless and the `DO $guardN$` wrappers are decoration.
    Here the SAME role runs the SAME replacement with no guard around it, and
    PostgreSQL refuses -- which inside `release_command` is a failed migration
    and an aborted deploy.

    Deliberately a hand-written statement rather than a mutated copy of 289:
    mutating the shipped file to prove a point is how a RED proof ends up
    committed, and the mechanism under test is PostgreSQL's ownership rule, not
    289's prose.
    """

    await _build_ledger_owned_schema(split_ownership_sandbox)

    connection = await asyncpg.connect(split_ownership_sandbox.runtime_dsn)
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError) as raised:
            await connection.execute(
                """
                CREATE OR REPLACE FUNCTION public.bind_visa_decision_retention_policy()
                RETURNS trigger
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = pg_catalog, pg_temp
                AS $probe$
                BEGIN
                    RETURN NEW;
                END;
                $probe$;
                """
            )
    finally:
        await connection.close()

    assert "must be owner of function" in str(raised.value)


async def test_289_really_does_apply_when_the_runner_can_own_the_binders(
    split_ownership_sandbox: _Sandbox,
) -> None:
    """INNOCENCE: same database, same ownership split, an ABLE role.

    Without this, `test_..._does_not_abort_the_deploy...` would also pass on a
    289 that had been gutted to a no-op for everybody. The pivot between the two
    tests is ONLY the applying role -- the migration text is byte-identical.
    """

    await _build_ledger_owned_schema(split_ownership_sandbox)

    connection = await asyncpg.connect(split_ownership_sandbox.owner_dsn)
    try:
        # The sandbox owner must genuinely be able to replace ledger-owned
        # functions, or "innocence" would be proving nothing.
        assert await connection.fetchval(
            "SELECT pg_has_role(current_user, $1, 'USAGE')",
            split_ownership_sandbox.ledger_role,
        ) is True

        async with connection.transaction():
            await connection.execute(_forward_sql(289))
    finally:
        await connection.close()

    after = await _binder_bodies(split_ownership_sandbox.owner_dsn)
    assert set(after) == set(_LEDGER_BINDERS)
    for binder, body in after.items():
        assert "policy_scope" in body, (
            f"{binder} did NOT receive the scope predicate from an able role -- "
            "the catalog guard is declining when it should fire"
        )

    # The W114 bridge. `operational_preflight`'s `binder:retention-policy-scoped`
    # check is exercised elsewhere against an in-memory fake whose bodies and
    # whose matching regex were BOTH written by hand -- so on their own they only
    # prove that two of my inventions agree with each other. Here the pattern
    # meets a body PostgreSQL actually stored after running the shipped
    # migration. If 289's predicate is ever reworded, this fails and the fake
    # does not.
    for binder, body in after.items():
        assert operational_preflight._SCOPE_PREDICATE_RE.search(body), (
            f"the preflight probe would call the REAL post-289 {binder} unscoped: "
            "the shipped predicate and the pattern that looks for it have drifted"
        )
