"""The migration runner on a DEDICATED role (option D, RULED 2026-09-11).

WHY THIS FILE EXISTS
--------------------
Production applied every migration as the runtime role `backend_rag_v2`
through the single `DATABASE_URL`. That role is not a member of
`visa_ledger_owner`, so every migration that transfers a SECURITY DEFINER
binder to the ledger owner (253, 268, 281, 286, 300, 301 -- and 304, the one
that blocked GARUDA VOA step 5 for ten days) either aborted the deploy
(2026-08-26) or was applied by hand under a superuser. Zero ruled option D on
2026-09-11: a dedicated LOGIN role `backend_rag_migrator`, member of both,
reached through `MIGRATION_DATABASE_URL`; the runner assumes the runtime role
right after connecting. Measured costs and the rejected options:
`docs/plans/2026-08-24-garuda-voa-live/STEP5-PRIVILEGE-DECISION.md`.

WHAT IS ASSERTED, IN BOTH DIRECTIONS
------------------------------------
Unit (a fake connection, no database):
  - DSN precedence: `MIGRATION_DATABASE_URL` wins for the runner, and ONLY
    for the runner (`settings.database_url` is untouched); the manager hands
    ITS DSN to every `apply()` so ledger, lock and SQL hit one database.
  - SINGLE DSN is an unconditional no-op: not even a catalogue read (a
    superuser is a member of every role, so a member-based rule would have
    made CI's `test` superuser SET ROLE -- codex finding 3, 2026-09-11).
  - GUILT, dedicated DSN, refused before any statement: superuser; the
    runtime role itself; a connection-time role setting; runtime role absent;
    no SET privilege on it; not a member of the ledger role.
  - INNOCENCE -- dedicated member of both -> exactly one SET ROLE, verified
    against the server's own `current_user` afterwards.
  - a catalogue failure during the assumption closes the connection.

Real Postgres (skipped when no admin DB is reachable, like its siblings):
  - the full 304 choreography: runtime-owned DDL, `RESET ROLE`, ALTER a
    LEDGER-owned table (304 widens a CHECK on one), transfer a function to the
    ledger role, hand a table created while reset back to the runtime role,
    `SET ROLE` back, more runtime-owned DDL; every owner read from pg_class /
    pg_proc. Provenance records `runtime (session_user=migrator)`.
  - the counter-proof: connected AS the runtime role the transfer raises
    `insufficient_privilege` -- the 2026-08-26 deploy abort in eight lines.
  - a dedicated DSN that is a superuser, or the runtime role itself, is
    refused on a real server too.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import NamedTuple
from urllib.parse import quote, urlsplit, urlunsplit

import asyncpg
import pytest
import pytest_asyncio

from backend.db import migration_base
from backend.db.migration_base import (
    RUNTIME_ROLE,
    MigrationError,
    assume_runtime_role,
    resolve_applied_as,
    resolve_migration_dsn,
)
from backend.db.migration_manager import MigrationManager

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Unit: DSN precedence
# ---------------------------------------------------------------------------


def test_runner_dsn_prefers_the_dedicated_url(monkeypatch):
    monkeypatch.setattr(migration_base.settings, "database_url", "postgresql://rt@h/db")
    monkeypatch.setattr(migration_base.settings, "migration_database_url", "postgresql://mig@h/db")
    assert resolve_migration_dsn() == "postgresql://mig@h/db"
    # The runtime's own DSN is untouched: the migrator is the runner's, only.
    assert migration_base.settings.database_url == "postgresql://rt@h/db"


def test_runner_dsn_falls_back_to_the_runtime_url(monkeypatch):
    monkeypatch.setattr(migration_base.settings, "database_url", "postgresql://rt@h/db")
    monkeypatch.setattr(migration_base.settings, "migration_database_url", None)
    assert resolve_migration_dsn() == "postgresql://rt@h/db"


async def test_manager_hands_its_own_dsn_to_every_apply(monkeypatch):
    """Codex finding 1: pool/ledger/lock on DSN A, SQL on DSN B was possible."""
    monkeypatch.setattr(migration_base.settings, "database_url", "postgresql://b@h/db")
    manager = MigrationManager(database_url="postgresql://a@h/db")
    seen: dict = {}

    class _Mig:
        async def apply(self, database_url=None):
            seen["dsn"] = database_url
            return True

    assert await manager.apply_migration(_Mig()) is True
    assert seen["dsn"] == "postgresql://a@h/db"


# ---------------------------------------------------------------------------
# Unit: assume_runtime_role on a fake connection
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, row: dict | None, *, current_user_after: str | None = None):
        self._row = row
        self._after = current_user_after
        self.executed: list[str] = []
        self.fetches = 0

    async def fetchrow(self, _sql, *_args):
        self.fetches += 1
        return self._row

    async def fetchval(self, _sql, *_args):
        return self._after

    async def execute(self, sql, *_args):
        self.executed.append(sql)


def _row(
    cu,
    su,
    *,
    is_super=False,
    reaches_super=False,
    runtime_exists=True,
    can_set_runtime=True,
    ledger_exists=True,
    ledger_member=True,
):
    return {
        "cu": cu,
        "su": su,
        "is_super": is_super,
        "reaches_super": reaches_super,
        "runtime_exists": runtime_exists,
        "can_set_runtime": can_set_runtime,
        "ledger_exists": ledger_exists,
        "ledger_member": ledger_member,
    }


async def test_single_dsn_is_an_unconditional_no_op():
    conn = _FakeConn(_row("test", "test", is_super=True))
    assert await assume_runtime_role(conn, dedicated=False) is None
    assert conn.fetches == 0
    assert conn.executed == []


async def test_dedicated_reads_the_setting_when_not_told(monkeypatch):
    monkeypatch.setattr(migration_base.settings, "migration_database_url", None)
    conn = _FakeConn(_row("postgres", "postgres", is_super=True))
    assert await assume_runtime_role(conn) is None  # unset -> single DSN -> no-op
    monkeypatch.setattr(migration_base.settings, "migration_database_url", "postgresql://m@h/d")
    with pytest.raises(MigrationError, match="SUPERUSER"):
        await assume_runtime_role(conn)


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (_row("postgres", "postgres", is_super=True), "SUPERUSER"),
        (_row("mig", "mig", reaches_super=True), "member of a SUPERUSER role"),
        (_row(RUNTIME_ROLE, RUNTIME_ROLE), "AS the runtime role"),
        (_row("someone_else", "mig"), "connection-time role"),
        (_row("mig", "mig", runtime_exists=False, can_set_runtime=False), "does not exist"),
        (_row("mig", "mig", can_set_runtime=False), "cannot SET ROLE"),
        (_row("mig", "mig", ledger_member=False), "not a member of 'visa_ledger_owner'"),
    ],
    ids=[
        "superuser",
        "reaches-superuser",
        "is-runtime",
        "conn-time-role",
        "no-runtime",
        "no-set",
        "no-ledger",
    ],
)
async def test_guilt_dedicated_dsn_shapes_are_refused_before_any_statement(row, reason):
    conn = _FakeConn(row)
    with pytest.raises(MigrationError, match=reason):
        await assume_runtime_role(conn, dedicated=True)
    assert conn.executed == []


async def test_innocence_dedicated_member_assumes_the_runtime_role():
    conn = _FakeConn(_row("mig", "mig"), current_user_after=RUNTIME_ROLE)
    assert await assume_runtime_role(conn, dedicated=True) == RUNTIME_ROLE
    assert conn.executed == [f'SET ROLE "{RUNTIME_ROLE}"']


async def test_innocence_without_a_ledger_role_still_assumes():
    # A database that has no ledger role at all (a fresh clone) is not refused.
    conn = _FakeConn(
        _row("mig", "mig", ledger_exists=False, ledger_member=False),
        current_user_after=RUNTIME_ROLE,
    )
    assert await assume_runtime_role(conn, dedicated=True) == RUNTIME_ROLE


async def test_already_assumed_connection_is_idempotent():
    # A pool re-acquire where the release did NOT reset the role: no second
    # SET ROLE, no refusal -- and the memberships are still checked first.
    conn = _FakeConn(_row(RUNTIME_ROLE, "mig"))
    assert await assume_runtime_role(conn, dedicated=True) == RUNTIME_ROLE
    assert conn.executed == []
    conn = _FakeConn(_row(RUNTIME_ROLE, "mig", ledger_member=False))
    with pytest.raises(MigrationError, match="not a member"):
        await assume_runtime_role(conn, dedicated=True)


async def test_set_role_that_did_not_take_is_refused():
    conn = _FakeConn(_row("mig", "mig"), current_user_after="mig")
    with pytest.raises(MigrationError, match="after SET ROLE"):
        await assume_runtime_role(conn, dedicated=True)


async def test_apply_closes_the_connection_when_the_catalogue_read_fails(monkeypatch, tmp_path):
    """Codex finding 6: only MigrationError used to close the connection."""
    closed = []

    class _BoomConn:
        async def fetchrow(self, *_a):
            raise asyncpg.InterfaceError("boom")

        async def close(self):
            closed.append(True)

    async def _connect(_dsn):
        return _BoomConn()

    monkeypatch.setattr(migration_base.asyncpg, "connect", _connect)
    monkeypatch.setattr(migration_base.settings, "migration_database_url", "postgresql://m@h/d")
    sql = tmp_path / "999_probe.sql"
    sql.write_text("SELECT 1;\n", encoding="utf-8")
    mig = migration_base.BaseMigration(999, str(sql), "probe", rollback_sql="SELECT 1;")
    with pytest.raises(MigrationError, match="Cannot assume the runtime role"):
        await mig.apply()
    assert closed == [True]


# ---------------------------------------------------------------------------
# Real Postgres: the 304 choreography, end to end
# ---------------------------------------------------------------------------

from backend.tests.scripts.visa_engine.test_retention_binder_scope_survives_a_non_owner_runner import (  # noqa: E402
    _ADMIN_URL,
)


class _Sandbox(NamedTuple):
    base_dsn: str  # admin user, sandbox database
    password: str
    runtime_role: str
    ledger_role: str
    migrator_role: str

    def dsn_for(self, role: str) -> str:
        parsed = urlsplit(self.base_dsn)
        netloc = f"{quote(role, safe='')}:{quote(self.password, safe='')}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


@pytest_asyncio.fixture
async def option_d_sandbox() -> AsyncIterator[_Sandbox]:
    """A database with the three production roles, uuid-suffixed.

    runtime  -- NOSUPERUSER LOGIN, owns tables (as `backend_rag_v2` does)
    ledger   -- NOSUPERUSER NOLOGIN, owns binders and one table
                (as `visa_ledger_owner` owns visa_decision_retention_policies)
    migrator -- NOSUPERUSER LOGIN IN ROLE runtime, ledger (option D)
    """
    try:
        admin = await asyncpg.connect(_ADMIN_URL)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no admin Postgres at {_ADMIN_URL.rsplit('@', 1)[-1]}: {exc}")
    suffix = uuid.uuid4().hex[:12]
    db_name = f"nuzantara_test_optd_{suffix}"
    runtime = f"t_runtime_{suffix}"
    ledger = f"t_ledger_{suffix}"
    migrator = f"t_migrator_{suffix}"
    password = uuid.uuid4().hex
    try:
        await admin.execute(f'CREATE DATABASE "{db_name}"')
        await admin.execute(f"CREATE ROLE \"{runtime}\" NOSUPERUSER LOGIN PASSWORD '{password}'")
        await admin.execute(f'CREATE ROLE "{ledger}" NOSUPERUSER NOLOGIN')
        await admin.execute(
            f"CREATE ROLE \"{migrator}\" NOSUPERUSER LOGIN PASSWORD '{password}' "
            f'IN ROLE "{runtime}", "{ledger}"'
        )
        for role in (runtime, migrator):
            await admin.execute(f'GRANT CONNECT ON DATABASE "{db_name}" TO "{role}"')
    finally:
        await admin.close()

    base = _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"
    owner = await asyncpg.connect(base)
    try:
        # Production: both roles may CREATE in public (measured 2026-09-02).
        await owner.execute(f'GRANT CREATE, USAGE ON SCHEMA public TO "{runtime}", "{ledger}"')
        # The ledger-owned table 304 must ALTER (a CHECK it widens).
        await owner.execute(
            "CREATE TABLE public.t_policies (policy_scope text "
            "CONSTRAINT t_policies_scope_check CHECK (policy_scope IN ('A')))"
        )
        await owner.execute(f'ALTER TABLE public.t_policies OWNER TO "{ledger}"')
        await owner.execute(f'GRANT SELECT ON public.t_policies TO "{runtime}"')
    finally:
        await owner.close()

    try:
        yield _Sandbox(
            base_dsn=base,
            password=password,
            runtime_role=runtime,
            ledger_role=ledger,
            migrator_role=migrator,
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
            for role in (migrator, runtime, ledger):
                await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        finally:
            await admin.close()


async def _owners(conn: asyncpg.Connection, *relnames: str) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT relname, pg_get_userbyid(relowner) AS owner FROM pg_class "
        "WHERE relname = ANY($1::text[])",
        list(relnames),
    )
    return {r["relname"]: r["owner"] for r in rows}


async def test_real_pg_option_d_choreography(option_d_sandbox: _Sandbox):
    sb = option_d_sandbox
    conn = await asyncpg.connect(sb.dsn_for(sb.migrator_role))
    try:
        assumed = await assume_runtime_role(
            conn, runtime_role=sb.runtime_role, ledger_role=sb.ledger_role, dedicated=True
        )
        assert assumed == sb.runtime_role
        assert await conn.fetchval("SELECT current_user") == sb.runtime_role
        assert await conn.fetchval("SELECT session_user") == sb.migrator_role
        # Provenance tells the truth about both roles.
        assert await resolve_applied_as(conn) == (
            f"{sb.runtime_role} (session_user={sb.migrator_role})"
        )

        async with conn.transaction():
            # (1) ordinary DDL -> owned by the RUNTIME role, as today
            await conn.execute("CREATE TABLE public.t_docs (id int)")
            await conn.execute(
                "CREATE FUNCTION public.t_bind() RETURNS trigger LANGUAGE plpgsql "
                "SECURITY DEFINER AS $f$ BEGIN RETURN NEW; END $f$"
            )
            # (2) the 304-shaped bracket: RESET to the migrator ...
            await conn.execute("RESET ROLE")
            assert await conn.fetchval("SELECT current_user") == sb.migrator_role
            # ... ALTER the LEDGER-owned table (304 widens a CHECK on one) ...
            await conn.execute(
                "ALTER TABLE public.t_policies DROP CONSTRAINT t_policies_scope_check"
            )
            await conn.execute(
                "ALTER TABLE public.t_policies ADD CONSTRAINT t_policies_scope_check "
                "CHECK (policy_scope IN ('A', 'B'))"
            )
            # ... transfer the binder to the ledger role ...
            await conn.execute(f'ALTER FUNCTION public.t_bind() OWNER TO "{sb.ledger_role}"')
            # ... a table created while reset is MIGRATOR-owned and must be handed back ...
            await conn.execute("CREATE TABLE public.t_while_reset (id int)")
            assert (await _owners(conn, "t_while_reset"))["t_while_reset"] == sb.migrator_role
            await conn.execute(f'ALTER TABLE public.t_while_reset OWNER TO "{sb.runtime_role}"')
            # ... and SET back.
            await conn.execute(f'SET ROLE "{sb.runtime_role}"')
            # (3) DDL after the bracket is runtime-owned again
            await conn.execute("CREATE TABLE public.t_review (id int)")

        assert await _owners(conn, "t_docs", "t_while_reset", "t_review", "t_policies") == {
            "t_docs": sb.runtime_role,
            "t_while_reset": sb.runtime_role,
            "t_review": sb.runtime_role,
            "t_policies": sb.ledger_role,
        }
        assert (
            await conn.fetchval(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE proname = 't_bind'"
            )
            == sb.ledger_role
        )
        assert (
            await conn.fetchval(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 't_policies_scope_check'"
            )
            == "CHECK ((policy_scope = ANY (ARRAY['A'::text, 'B'::text])))"
        )
    finally:
        await conn.close()


async def test_real_pg_pool_setup_survives_release_and_reacquire(option_d_sandbox: _Sandbox):
    """asyncpg resets the session on release; the role must come back on acquire."""
    import functools

    sb = option_d_sandbox
    hook = functools.partial(
        assume_runtime_role,
        runtime_role=sb.runtime_role,
        ledger_role=sb.ledger_role,
        dedicated=True,
    )
    pool = await asyncpg.create_pool(
        sb.dsn_for(sb.migrator_role), min_size=1, max_size=1, setup=hook
    )
    try:
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT current_user") == sb.runtime_role
        async with pool.acquire() as conn:
            # Same physical connection (max_size=1); whether or not the release
            # reset the role, the effective role on acquire is the runtime role.
            assert await conn.fetchval("SELECT current_user") == sb.runtime_role
            assert await conn.fetchval("SELECT session_user") == sb.migrator_role
    finally:
        await pool.close()


async def test_real_pg_reset_role_is_undone_by_an_aborted_transaction(option_d_sandbox: _Sandbox):
    """A migration that fails mid-bracket must not leave the pool connection reset."""
    sb = option_d_sandbox
    conn = await asyncpg.connect(sb.dsn_for(sb.migrator_role))
    try:
        await assume_runtime_role(
            conn, runtime_role=sb.runtime_role, ledger_role=sb.ledger_role, dedicated=True
        )
        with pytest.raises(asyncpg.PostgresError):
            async with conn.transaction():
                await conn.execute("RESET ROLE")
                await conn.execute("SELECT 1/0")
        assert await conn.fetchval("SELECT current_user") == sb.runtime_role
    finally:
        await conn.close()


async def test_real_pg_runtime_role_alone_cannot_do_the_transfer(option_d_sandbox: _Sandbox):
    """The counter-proof: without option D the same bracket fails.

    Connecting AS the runtime role (the pre-2026-09-11 production shape), the
    `OWNER TO ledger` statement raises `insufficient_privilege` -- which is the
    2026-08-26 deploy abort, reproduced in eight lines.
    """
    sb = option_d_sandbox
    conn = await asyncpg.connect(sb.dsn_for(sb.runtime_role))
    try:
        assert (
            await assume_runtime_role(conn, runtime_role=sb.runtime_role, dedicated=False) is None
        )
        await conn.execute(
            "CREATE FUNCTION public.t_bind2() RETURNS trigger LANGUAGE plpgsql "
            "SECURITY DEFINER AS $f$ BEGIN RETURN NEW; END $f$"
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(f'ALTER FUNCTION public.t_bind2() OWNER TO "{sb.ledger_role}"')
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "ALTER TABLE public.t_policies DROP CONSTRAINT t_policies_scope_check"
            )
    finally:
        await conn.close()


async def test_real_pg_dedicated_dsn_as_the_runtime_role_is_refused(option_d_sandbox: _Sandbox):
    sb = option_d_sandbox
    conn = await asyncpg.connect(sb.dsn_for(sb.runtime_role))
    try:
        with pytest.raises(MigrationError, match="AS the runtime role"):
            await assume_runtime_role(
                conn, runtime_role=sb.runtime_role, ledger_role=sb.ledger_role, dedicated=True
            )
    finally:
        await conn.close()


async def test_real_pg_superuser_dedicated_dsn_is_refused(option_d_sandbox: _Sandbox):
    conn = await asyncpg.connect(option_d_sandbox.base_dsn)
    try:
        if not await conn.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"):
            pytest.skip("admin DSN is not a superuser here")
        with pytest.raises(MigrationError, match="SUPERUSER"):
            await assume_runtime_role(
                conn, runtime_role=option_d_sandbox.runtime_role, dedicated=True
            )
    finally:
        await conn.close()
