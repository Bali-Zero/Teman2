"""Shape D for migration 313: a disposable PostgreSQL 17 with the three
PRODUCTION role names actually provisioned -- `backend_rag_migrator` (the
migrator LOGIN, explicitly NOT a superuser, a member of the other two),
`backend_rag_v2` (the runtime role) and `visa_ledger_owner` (the NOLOGIN
ledger owner).

`test_migration_313_garuda_practice_artifacts.py` runs against a database
where these roles do NOT exist, so every role-conditional branch in 313 --
the two ownership transfers, the runtime grants, and the guard trigger's
actual bite against a role that only holds those grants -- has never
executed under test. This file is that gear-3 precondition (Imperator
mandate, this window): it applies 313 through the REAL `BaseMigration`
path (`backend/db/migration_base.py`), never by pasting SQL, because the
runner's own role handling -- `assume_runtime_role`'s SET ROLE dance, and
313's own RESET ROLE / resume brackets -- is exactly what is under test.

Model: migration 304's own shape-D suite, `test_migration_304_owner_
bracket.py` (unmerged, `origin/agent/air-m5/db/voa-304` --
`origin/agent/air-m5/ops/garuda-voa-documents` does NOT carry it, despite
an earlier pointer to that branch; found by searching every `origin/agent/
...` branch for the filename). Same `disposable_cluster` fixture shape
(role names, membership grants, PG16+/PG15 SET-vs-MEMBER split), same
`_dsn_as` helper, same refusal of any DSN naming a real database.

Two substrate choices diverge from 304's model because 313's own shape
differs from 304's:

* 313's table (not just its functions) is transferred to `visa_ledger_
  owner` -- Sol's F8 (BLOCKER): a trigger cannot bind an owner, so the
  guard in (3) is a convention, not a boundary, until the table and the
  guard function both leave `backend_rag_v2`. The substrate below builds
  a MINIMAL stand-in for `garuda_practices` (the one real table 313's own
  FK reaches) rather than replaying migrations 284/287/304 in full --
  313's own SQL only cares that `garuda_practices.practice_id` exists as
  a unique TEXT column, and a synthetic substrate that supplies exactly
  that (plus a `visa_decision_retention_policies` with the GARUDA_DOCUMENT
  scope PRE-widened) is what 304's own `_build_substrate` already does
  for the ONE upstream table it depends on.
* Pre-widening the policy_scope CHECK (rather than exercising block (0)'s
  own ALTER path here) is deliberate: that ALTER needs ALTER-TABLE
  privilege on `visa_decision_retention_policies`, which this fixture's
  whole point is NOT to hand either `backend_rag_v2` or the migrator, and
  block (0)'s widen-or-skip logic is already proven structurally by
  `test_migration_313_garuda_practice_artifacts.py::
  test_both_halves_carry_the_ownership_privilege_bracket`'s sibling in
  that same file plus 313's own idempotent-no-op design (see 313's module
  header). What is UNPROVEN anywhere else, and is this file's entire
  reason to exist, is what happens once the roles are real.

A one-row-per-tag scratch table, `public._shape_d_role_probe`, is the
mechanism for point 4 (Sol O2, new finding 2): `BaseMigration.apply()`
opens and closes its OWN connection, so `current_role` cannot be read
from outside once `apply()` returns -- the only way to observe it is a
statement INSIDE the same transaction, on the same connection, that
writes it somewhere that outlives the connection. `_with_role_probes`
appends exactly one such INSERT to the end of the forward section (before
the `-- === ROLLBACK ===` marker) and one to the end of the rollback
section (the very end of the file) -- neither probe touches any object
313 itself creates or removes, so they cannot perturb the ownership/ACL
assertions the rest of this file makes.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio

asyncpg = pytest.importorskip("asyncpg")

from backend.db import migration_base  # noqa: E402
from backend.db.migration_base import (  # noqa: E402
    ROLLBACK_MARKER_RE,
    BaseMigration,
    split_migration_sql,
)
from backend.db.migration_manager import MigrationManager  # noqa: E402

pytestmark = pytest.mark.asyncio

RUNTIME = "backend_rag_v2"
LEDGER = "visa_ledger_owner"
MIGRATOR = "backend_rag_migrator"
SOURCE = BaseMigration.MIGRATIONS_DIR / "313_garuda_practice_artifacts.sql"

# Same env var 304's own shape-D suite reads (`OPTION_D_DISPOSABLE_PG_URL`):
# one disposable-cluster convention serves both suites rather than adding a
# second knob for the identical concept (a local cluster with the three
# production role names free to provision). What THIS file adds on top is
# the PG17 floor -- Fly's `nuzantara-postgres` runs postgres-flex 17.7
# (apps/backend-rag/CLAUDE.md SS11), and nothing about 313's own SQL
# requires 17 specifically (its `server_version_num >= 160000` branch
# degrades correctly on 15), but shape D is the one place fidelity to the
# real cluster version is cheap, and PG17 was measured present on this
# machine (`/opt/homebrew/opt/postgresql@17`, 17.10) when this file was
# written.
_DISPOSABLE_ADMIN_URL = os.environ.get("OPTION_D_DISPOSABLE_PG_URL")

_SYNTHETIC_DIGEST = hashlib.sha256(b"shape-d synthetic fixture, no real document").hexdigest()

_PROBE_TABLE = "public._shape_d_role_probe"


def _dsn_as(dsn: str, role: str) -> str:
    """Returns dsn with its user replaced by role and no password."""
    parts = urlsplit(dsn)
    host = f"{parts.hostname}:{parts.port}" if parts.port else str(parts.hostname)
    return urlunsplit((parts.scheme, f"{role}@{host}", parts.path, parts.query, parts.fragment))


def _with_role_probes(sql: str) -> str:
    """Returns sql with two INSERT probes spliced in: one at the end of the
    forward section (still before the ROLLBACK marker, so `split_migration_
    sql` keeps it in `forward`), one appended at the very end of the file
    (inside `rollback`, since it comes after the marker). Each records
    `current_role` INSIDE the same session that just ran the surrounding
    DDL -- the only way to observe a role a since-closed connection can no
    longer report (see module docstring)."""
    match = ROLLBACK_MARKER_RE.search(sql)
    assert match, "313 must carry the ROLLBACK marker for this fixture to locate the split point"
    probe = (
        "\nINSERT INTO {table} (tag, observed_role) VALUES ('{tag}', current_role) "
        "ON CONFLICT (tag) DO UPDATE SET observed_role = EXCLUDED.observed_role;\n"
    )
    forward_probe = probe.format(table=_PROBE_TABLE, tag="forward_end")
    rollback_probe = probe.format(table=_PROBE_TABLE, tag="rollback_end")
    return sql[: match.start()] + forward_probe + sql[match.start() :] + rollback_probe


def _migration(tmp_path: Path) -> BaseMigration:
    """Returns a BaseMigration for a role-probed COPY of 313's real file,
    written into tmp_path under 313's own filename (BaseMigration requires
    the file to exist under `_sql_dir`)."""
    sql = _with_role_probes(SOURCE.read_text(encoding="utf-8"))
    (tmp_path / SOURCE.name).write_text(sql, encoding="utf-8")
    return BaseMigration(
        313,
        SOURCE.name,
        "garuda practice artifacts (shape D)",
        rollback_sql=split_migration_sql(sql)[1],
        _sql_dir=tmp_path,
    )


async def _build_substrate(admin_url: str) -> str:
    """Creates a throwaway database with a MINIMAL `garuda_practices` stand-in
    and an ALREADY-widened `visa_decision_retention_policies` -- the two
    upstream objects 313's own DDL reaches via FK/trigger -- owned exactly
    as production splits them: `backend_rag_v2` owns `garuda_practices`
    (matching 313's module header: every OTHER garuda_* table is "otherwise
    owned by backend_rag_v2"), `visa_ledger_owner` owns the retention
    authority (304's own split, replicated because 304 is unmerged), with
    `backend_rag_v2` granted SELECT+REFERENCES on it -- the FK from
    `garuda_practice_artifacts.retention_policy_id` needs exactly that, no
    more. See the module docstring for why this is synthetic rather than
    284/287/304 replayed in full."""
    name = f"m313_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    dsn = admin_url.rsplit("/", 1)[0] + f"/{name}"
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("CREATE TABLE public.garuda_practices (practice_id TEXT PRIMARY KEY)")
        await conn.execute(
            "CREATE TABLE public.visa_decision_retention_policies ("
            "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
            "  environment TEXT NOT NULL CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),"
            "  policy_scope TEXT NOT NULL CHECK (policy_scope IN "
            "    ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK', 'GARUDA_DOCUMENT')),"
            "  retention_interval INTERVAL NOT NULL CHECK (retention_interval > INTERVAL '0 seconds'),"
            "  retention_anchor TEXT NOT NULL CHECK (retention_anchor IN ('EVALUATED_AT', 'CREATED_AT')),"
            "  effective_period TSTZRANGE NOT NULL"
            ")"
        )
        await conn.execute(f"GRANT CREATE, USAGE ON SCHEMA public TO {RUNTIME}, {LEDGER}")
        await conn.execute(f"ALTER TABLE public.garuda_practices OWNER TO {RUNTIME}")
        await conn.execute(f"ALTER TABLE public.visa_decision_retention_policies OWNER TO {LEDGER}")
        await conn.execute(
            f"GRANT SELECT, REFERENCES ON public.visa_decision_retention_policies TO {RUNTIME}"
        )
        await conn.execute(
            f"CREATE TABLE {_PROBE_TABLE} (tag TEXT PRIMARY KEY, observed_role TEXT NOT NULL)"
        )
        # UPDATE too: the probe is `INSERT ... ON CONFLICT (tag) DO UPDATE`,
        # and Postgres checks UPDATE privilege for the conflict-update
        # branch even though the common path is a fresh INSERT.
        await conn.execute(
            f"GRANT INSERT, SELECT, UPDATE ON {_PROBE_TABLE} TO {RUNTIME}, {LEDGER}, {MIGRATOR}"
        )
        await conn.execute(
            "INSERT INTO public.visa_decision_retention_policies "
            "(environment, policy_scope, retention_interval, retention_anchor, effective_period) "
            "VALUES ('TEST', 'GARUDA_DOCUMENT', INTERVAL '30 days', 'CREATED_AT', "
            "tstzrange(now() - interval '1 day', NULL, '[)'))"
        )
    finally:
        await conn.close()
    return dsn


async def _drop_database(admin_url: str, dsn: str) -> None:
    """Terminates other sessions on dsn's database and drops it."""
    name = dsn.rsplit("/", 1)[1]
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            name,
        )
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        await admin.close()


async def _owners(conn: asyncpg.Connection) -> dict[str, str | None]:
    """Reads the REAL owner of 313's table and its THREE transferred
    functions from the catalogue (`pg_class.relowner` / `pg_proc.proowner`),
    never inferred from the migration's own claims. `helper` --
    `active_garuda_practice_artifact_policy_available` -- joined the loop in
    (3bis) after this fixture's own first run found it left behind (Sol
    F9's own outcome surviving inside F9's cure); asserting its owner here,
    alongside the other three, is the regression lock: a fourth function
    added to 313 tomorrow without joining that loop should fail HERE, not
    surface as a production rollback that aborts with "must be owner of"."""
    row = await conn.fetchrow(
        "SELECT "
        "  pg_get_userbyid((SELECT relowner FROM pg_class "
        "     WHERE oid = 'public.garuda_practice_artifacts'::regclass)) AS tbl, "
        "  pg_get_userbyid((SELECT proowner FROM pg_proc "
        "     WHERE oid = 'public.guard_garuda_practice_artifacts_mutation()'::regprocedure)) AS guard, "
        "  pg_get_userbyid((SELECT proowner FROM pg_proc "
        "     WHERE oid = 'public.bind_garuda_practice_artifact_retention_policy()'::regprocedure)) AS bind, "
        "  pg_get_userbyid((SELECT proowner FROM pg_proc "
        "     WHERE oid = 'public.active_garuda_practice_artifact_policy_available"
        "(text,timestamptz)'::regprocedure)) AS helper"
    )
    return dict(row)


async def _seed_practice(conn: asyncpg.Connection) -> str:
    practice_id = f"prc_shaped_{uuid.uuid4().hex[:16]}"
    await conn.execute("INSERT INTO garuda_practices (practice_id) VALUES ($1)", practice_id)
    return practice_id


async def _insert_artifact(
    conn: asyncpg.Connection, *, practice_id: str, artifact_id: str | None = None
) -> str:
    artifact_id = artifact_id or f"art_{uuid.uuid4().hex[:20]}"
    await conn.execute(
        "INSERT INTO garuda_practice_artifacts "
        "(artifact_id, practice_id, storage_key, artifact_digest, byte_length, content_type, "
        " produced_by, environment) "
        "VALUES ($1, $2, $3, $4, 42, 'application/pdf', 'staff@balizero.com', 'TEST')",
        artifact_id,
        practice_id,
        f"artifacts/TEST/{practice_id}/{artifact_id}",
        _SYNTHETIC_DIGEST,
    )
    return artifact_id


@pytest_asyncio.fixture
async def disposable_cluster() -> AsyncIterator[str]:
    """Yields a local PG17 cluster's superuser DSN after creating the three
    production role names; skips (loudly, with the reason) if the DSN is
    unset, points off-loopback, pre-dates PG17, or any target role name
    already exists. Drops the roles after. Identical shape to 304's own
    fixture -- see this file's module docstring for why the env var is
    shared."""
    if not _DISPOSABLE_ADMIN_URL:
        pytest.skip(
            "OPTION_D_DISPOSABLE_PG_URL unset: shape D needs a disposable PG17 cluster with the "
            "three production role names free to provision (backend_rag_migrator, backend_rag_v2, "
            "visa_ledger_owner) -- see this file's module docstring for how to boot one"
        )
    if urlsplit(_DISPOSABLE_ADMIN_URL).hostname not in ("127.0.0.1", "localhost"):
        pytest.skip("OPTION_D_DISPOSABLE_PG_URL must name a local cluster")
    admin = await asyncpg.connect(_DISPOSABLE_ADMIN_URL)
    created: list[str] = []
    try:
        assert await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = session_user")
        # `pytest.raises(match=...)` below matches literal English text
        # ("permission denied for table" / "must be owner of"). `lc_messages`
        # is a SUSET GUC -- a non-superuser connection gets "permission
        # denied to set parameter" if it tries this itself at connect time
        # (measured directly), so it has to be forced cluster-wide, once,
        # by the superuser admin connection, rather than per-connection.
        await admin.execute("ALTER SYSTEM SET lc_messages = 'C'")
        await admin.execute("SELECT pg_reload_conf()")
        version = await admin.fetchval("SELECT current_setting('server_version_num')::int")
        if version < 170000:
            pytest.skip(
                f"OPTION_D_DISPOSABLE_PG_URL points at server_version_num={version}, below the "
                "PG17 floor shape D pins to match Fly's postgres-flex 17.7 (apps/backend-rag/"
                "CLAUDE.md SS11) -- boot a postgresql@17 cluster instead"
            )
        if await admin.fetchval(
            "SELECT count(*) FROM pg_roles WHERE rolname = ANY($1::text[])", [RUNTIME, LEDGER, MIGRATOR]
        ):
            pytest.skip("a production role name already exists on this cluster")
        for role, login in ((RUNTIME, "LOGIN"), (LEDGER, "NOLOGIN"), (MIGRATOR, "LOGIN")):
            await admin.execute(f"CREATE ROLE {role} NOSUPERUSER INHERIT {login}")
            created.append(role)
        options = (
            "WITH INHERIT TRUE, SET TRUE"
            if await admin.fetchval("SELECT current_setting('server_version_num')::int >= 160000")
            else ""
        )
        await admin.execute(f"GRANT {RUNTIME}, {LEDGER} TO {MIGRATOR} {options}")
        yield _DISPOSABLE_ADMIN_URL
    finally:
        for role in reversed(created):
            await admin.execute(f"DROP ROLE IF EXISTS {role}")
        await admin.close()


async def test_313_applies_through_the_dedicated_migrator_with_the_full_privilege_bracket(
    disposable_cluster: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """FORWARD, dedicated migrator -- Option D's real `assume_runtime_role`
    path, not a no-op: `backend_rag_migrator` connects, is refused if it
    were superuser or the runtime role itself, then genuinely `SET ROLE
    backend_rag_v2`s before a single statement of 313 runs.

    Proves, against the real catalogue and the real ACL:
      1. the table and BOTH transferred functions end up owned by
         `visa_ledger_owner` (F8's cure, decision #16) -- read from
         `pg_class.relowner` / `pg_proc.proowner`.
      2. `backend_rag_v2`'s table-level ACL (`pg_class.relacl`) is exactly
         {SELECT, INSERT} -- no DELETE/TRUNCATE/REFERENCES/TRIGGER at all --
         and its COLUMN-level ACL (`information_schema.column_privileges`,
         a different catalogue entirely: `GRANT UPDATE (cols)` never
         touches `relacl`) is exactly UPDATE on `superseded_at` and
         `superseded_by`, nothing else.
      3. GUILT, acting AS `backend_rag_v2` with exactly that grant set:
         removing a row, emptying the table, disabling the guard trigger,
         dropping the guard trigger, and replacing the guard function's
         body each fail -- and the first two fail at the ACL layer
         ("permission denied for table") WITHOUT the guard trigger's own
         message ever firing, because DELETE/TRUNCATE were never granted
         at all. That is the point of moving from "the trigger blocks it"
         to "the grant set cannot reach it".
      6. a legal same-practice supersession succeeds under this exact
         grant set (not an owner's unrestricted rights), and a
         cross-practice successor is still refused by the deferred
         composite FK (Sol F7) even though `backend_rag_v2` can UPDATE
         the pair.
    """
    migration = _migration(tmp_path)
    dsn = await _build_substrate(disposable_cluster)
    try:
        monkeypatch.setattr(migration_base.settings, "migration_database_url", _dsn_as(dsn, MIGRATOR))
        async with MigrationManager() as manager:
            assert manager._dedicated is True
            assert await manager.apply_migration(migration)

        admin = await asyncpg.connect(dsn)
        try:
            owners = await _owners(admin)
            assert owners == {"tbl": LEDGER, "guard": LEDGER, "bind": LEDGER, "helper": LEDGER}, owners

            table_acl = {
                r["privilege_type"]
                for r in await admin.fetch(
                    "SELECT a.privilege_type FROM pg_class c "
                    "CROSS JOIN LATERAL aclexplode(c.relacl) AS a "
                    "WHERE c.oid = 'public.garuda_practice_artifacts'::regclass "
                    "AND CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END = $1",
                    RUNTIME,
                )
            }
            assert table_acl == {"SELECT", "INSERT"}, table_acl

            # `information_schema.column_privileges` is NOT column-grants-
            # only: Postgres expands a table-level SELECT/INSERT into one
            # row per column there too (measured directly -- an earlier
            # version of this assertion expected only the two UPDATE rows
            # and instead saw SELECT/INSERT rows for every column as well).
            # Filtering to privilege_type='UPDATE' is what isolates the
            # COLUMN-level grant block(4) actually issued -- table-level
            # UPDATE never appears in `pg_class.relacl` at all, only here.
            column_updates = {
                r["column_name"]
                for r in await admin.fetch(
                    "SELECT column_name FROM information_schema.column_privileges "
                    "WHERE table_schema = 'public' AND table_name = 'garuda_practice_artifacts' "
                    "AND grantee = $1 AND privilege_type = 'UPDATE'",
                    RUNTIME,
                )
            }
            assert column_updates == {"superseded_at", "superseded_by"}, column_updates

            for priv in ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                assert not await admin.fetchval(
                    "SELECT has_table_privilege($1, 'public.garuda_practice_artifacts', $2)",
                    RUNTIME,
                    priv,
                ), f"backend_rag_v2 must not hold {priv}"
        finally:
            await admin.close()

        runtime_dsn = _dsn_as(dsn, RUNTIME)

        setup_conn = await asyncpg.connect(runtime_dsn)
        try:
            practice_id = await _seed_practice(setup_conn)
            artifact_id = await _insert_artifact(setup_conn, practice_id=practice_id)
        finally:
            await setup_conn.close()

        async def _attempt_as_runtime(sql: str) -> None:
            conn = await asyncpg.connect(runtime_dsn)
            try:
                await conn.execute(sql)
            finally:
                await conn.close()

        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="permission denied for table"):
            await _attempt_as_runtime(
                f"DELETE FROM garuda_practice_artifacts WHERE artifact_id = '{artifact_id}'"
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="permission denied for table"):
            await _attempt_as_runtime("TRUNCATE TABLE garuda_practice_artifacts")
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="must be owner of"):
            await _attempt_as_runtime(
                "ALTER TABLE garuda_practice_artifacts "
                "DISABLE TRIGGER trg_guard_garuda_practice_artifacts_mutation"
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="must be owner of"):
            await _attempt_as_runtime(
                "DROP TRIGGER trg_guard_garuda_practice_artifacts_mutation "
                "ON garuda_practice_artifacts"
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="must be owner of"):
            await _attempt_as_runtime(
                "CREATE OR REPLACE FUNCTION public.guard_garuda_practice_artifacts_mutation() "
                "RETURNS trigger LANGUAGE plpgsql AS $body$ BEGIN RETURN NEW; END; $body$"
            )

        survivor = await asyncpg.connect(runtime_dsn)
        try:
            assert (
                await survivor.fetchval(
                    "SELECT superseded_at FROM garuda_practice_artifacts WHERE artifact_id = $1",
                    artifact_id,
                )
                is None
            ), "every sabotage attempt failed -- the guilt row must be untouched"
        finally:
            await survivor.close()

        conn = await asyncpg.connect(runtime_dsn)
        try:
            tx = conn.transaction()
            await tx.start()
            try:
                successor_id = f"art_{uuid.uuid4().hex[:20]}"
                await conn.execute(
                    "UPDATE garuda_practice_artifacts "
                    "SET superseded_at = clock_timestamp(), superseded_by = $2 "
                    "WHERE artifact_id = $1",
                    artifact_id,
                    successor_id,
                )
                await _insert_artifact(conn, practice_id=practice_id, artifact_id=successor_id)
                await conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                row = await conn.fetchrow(
                    "SELECT superseded_by FROM garuda_practice_artifacts WHERE artifact_id = $1",
                    artifact_id,
                )
                assert row["superseded_by"] == successor_id
            finally:
                await tx.rollback()

            other_practice_id = await _seed_practice(conn)
            tx = conn.transaction()
            await tx.start()
            try:
                stranger_id = await _insert_artifact(conn, practice_id=other_practice_id)
                await conn.execute(
                    "UPDATE garuda_practice_artifacts "
                    "SET superseded_at = clock_timestamp(), superseded_by = $2 "
                    "WHERE artifact_id = $1",
                    artifact_id,
                    stranger_id,
                )
                with pytest.raises(asyncpg.ForeignKeyViolationError):
                    await conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            finally:
                await tx.rollback()
        finally:
            await conn.close()
    finally:
        await _drop_database(disposable_cluster, dsn)


async def test_313_forward_restores_the_measured_prior_role_never_a_named_one(
    disposable_cluster: str, tmp_path: Path
) -> None:
    """Sol O2's new finding 2: a resume block that asks 'may I become
    backend_rag_v2?' answers yes for ANY role that is a MEMBER of it --
    including a role that never left its own login to begin with. Single-
    DSN shape (`dedicated=False`, matching CI / a laptop / Fly before the
    dedicated secret exists): the migrator connects DIRECTLY, `assume_
    runtime_role` never fires, and nothing in 313's own file ever moves
    `current_role` away from the migrator's login -- every `RESET ROLE` is
    a true no-op and every resume block's `prior_role IS DISTINCT FROM
    current_role` guard is false, so the `SET ROLE` inside it never even
    executes. The table and both transferred functions still end up owned
    by `visa_ledger_owner` regardless (INHERIT membership, not literal
    `current_role`, is what lets the migrator ALTER OWNER TO a role it
    never became) -- which is exactly the property that makes "restore the
    MEASURED role" safe here: the file's own privilege dance never has to
    touch `current_role` in this shape at all, and the probe row below
    proves that directly, not merely infers it from the ownership outcome.
    """
    migration = _migration(tmp_path)
    dsn = await _build_substrate(disposable_cluster)
    migrator_dsn = _dsn_as(dsn, MIGRATOR)
    try:
        assert await migration.apply(database_url=migrator_dsn, dedicated=False)

        admin = await asyncpg.connect(dsn)
        try:
            forward_role = await admin.fetchval(
                f"SELECT observed_role FROM {_PROBE_TABLE} WHERE tag = 'forward_end'"
            )
            assert forward_role == MIGRATOR, (
                f"expected the session to still be on {MIGRATOR!r} at the end of the forward "
                f"apply (single-DSN shape never assumes backend_rag_v2), got {forward_role!r}"
            )
            owners = await _owners(admin)
            assert owners == {"tbl": LEDGER, "guard": LEDGER, "bind": LEDGER, "helper": LEDGER}, owners
        finally:
            await admin.close()
    finally:
        await _drop_database(disposable_cluster, dsn)


async def test_313_rollback_removes_all_four_ledger_owned_objects_and_restores_the_migrator(
    disposable_cluster: str, tmp_path: Path
) -> None:
    """Sol F9's own outcome, surviving inside F9's cure, for the one object
    (3bis)'s original loop did not enumerate -- found by THIS fixture's
    first run, now cured in 313.sql itself (Imperatore, this window).

    What broke: `$garuda_313_rollback_assume_owner$` switches the session to
    `visa_ledger_owner` UNCONDITIONALLY, once, before every removal
    statement in the rollback. The table and two of the three transferred
    functions were fine under that -- but `active_garuda_practice_artifact_
    policy_available(TEXT, TIMESTAMPTZ)` was never in (3bis)'s transfer
    loop (it has no privilege of its own -- a plain STABLE SQL function --
    so nobody had reason to move it there for security). Once the session
    became `visa_ledger_owner` for the DROP FUNCTION statements, dropping
    THIS one specifically failed with "must be owner of function ...": the
    rollback transaction aborted before reaching `DROP TABLE`, the forward
    migration stayed fully applied, and the caller was told an undo had
    run. Measured directly against real PG17 with all three roles present
    -- this file's `test_313_rollback_currently_aborts_on_the_
    untransferred_helper_function` watched it happen before the cure.

    The cure adds the helper function to (3bis)'s transfer loop, so every
    object 313 creates now has ONE owner regime instead of two, and the
    rollback's blanket assume-owner switch is correct for all of them. This
    test is the property that holds now that it's cured: the single-DSN
    migrator (never having left its own login role, `assume_runtime_role`
    being a no-op in this shape) can roll 313 all the way back, remove
    every one of the four ledger-owned objects, and land back on its own
    role -- not stuck on `visa_ledger_owner`, which the assume-owner
    bracket's own resume block (`$garuda_313_rollback_resume_runtime_
    role$`) is what guarantees.
    """
    migration = _migration(tmp_path)
    dsn = await _build_substrate(disposable_cluster)
    migrator_dsn = _dsn_as(dsn, MIGRATOR)
    try:
        assert await migration.apply(database_url=migrator_dsn, dedicated=False)

        async with MigrationManager(database_url=migrator_dsn, dedicated=False) as manager:
            assert manager._dedicated is False
            assert await manager.rollback_migration(migration.migration_name)

        admin = await asyncpg.connect(dsn)
        try:
            for signature, kind in (
                ("public.garuda_practice_artifacts", "regclass"),
                ("public.guard_garuda_practice_artifacts_mutation()", "regprocedure"),
                ("public.bind_garuda_practice_artifact_retention_policy()", "regprocedure"),
                (
                    "public.active_garuda_practice_artifact_policy_available(text,timestamptz)",
                    "regprocedure",
                ),
            ):
                gone = await admin.fetchval(f"SELECT to_{kind}($1) IS NULL", signature)
                assert gone, f"{signature} should have been removed by the rollback"

            rollback_role = await admin.fetchval(
                f"SELECT observed_role FROM {_PROBE_TABLE} WHERE tag = 'rollback_end'"
            )
            assert rollback_role == MIGRATOR, (
                f"expected the rollback to leave the session on {MIGRATOR!r}, got {rollback_role!r}"
            )
        finally:
            await admin.close()
    finally:
        await _drop_database(disposable_cluster, dsn)
