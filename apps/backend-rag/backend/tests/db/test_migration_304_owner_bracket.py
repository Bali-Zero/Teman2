"""Real-PostgreSQL tests that apply the actual migration 304 file through BaseMigration.apply."""

from __future__ import annotations

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
    BaseMigration,
    MigrationError,
    split_migration_sql,
)
from backend.db.migration_manager import MigrationManager  # noqa: E402

pytestmark = pytest.mark.asyncio

RUNTIME = "backend_rag_v2"
LEDGER = "visa_ledger_owner"
MIGRATOR = "backend_rag_migrator"
SOURCE = BaseMigration.MIGRATIONS_DIR / "304_garuda_documents.sql"
PROVENANCE = BaseMigration.MIGRATIONS_DIR / "299_schema_versions_provenance.sql"
RESUME_TAGS = (
    "garuda_304_resume_runtime_role_after_scope",
    "garuda_304_resume_runtime_role_after_transfer",
    "garuda_304_resume_runtime_role_after_rollback",
)
RECORD = "SELECT set_config('garuda.migration_304_resume_role', current_user, true);\n"
NARROW_SCOPES = ("VISA_DECISION", "GARUDA_CHECK", "GARUDA_ORDER", "GARUDA_MAGIC_LINK")
WIDENED_SCOPES = (*NARROW_SCOPES, "GARUDA_DOCUMENT")
FUNCTIONS = (
    "bind_garuda_document_retention_policy",
    "guard_garuda_document_mutation",
    "active_garuda_document_policy_available",
)

_CI_ADMIN_URL = (
    os.environ.get("TEST_DATABASE_URL", "postgresql://nuzantara@localhost:5432/nuzantara_test").rsplit(
        "/", 1
    )[0]
    + "/postgres"
)
_DISPOSABLE_ADMIN_URL = os.environ.get("OPTION_D_DISPOSABLE_PG_URL")


def _policies_ddl(scopes: tuple[str, ...]) -> str:
    """Returns DDL for visa_decision_retention_policies with the columns 304 reads and the given scope list."""
    listed = ", ".join(f"'{scope}'" for scope in scopes)
    return f"""
        CREATE TABLE public.visa_decision_retention_policies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            environment TEXT NOT NULL CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
            policy_scope TEXT NOT NULL CHECK (policy_scope IN ({listed})),
            retention_interval INTERVAL NOT NULL CHECK (retention_interval > INTERVAL '0 seconds'),
            retention_anchor TEXT NOT NULL CHECK (retention_anchor IN ('EVALUATED_AT', 'CREATED_AT')),
            effective_period TSTZRANGE NOT NULL
        )
    """


def _dsn_as(dsn: str, role: str) -> str:
    """Returns dsn with its user replaced by role and no password."""
    parts = urlsplit(dsn)
    host = f"{parts.hostname}:{parts.port}" if parts.port else str(parts.hostname)
    return urlunsplit((parts.scheme, f"{role}@{host}", parts.path, parts.query, parts.fragment))


def _migration(sql_dir: Path = BaseMigration.MIGRATIONS_DIR) -> BaseMigration:
    """Returns a BaseMigration for 304_garuda_documents.sql read from sql_dir."""
    sql = (sql_dir / SOURCE.name).read_text(encoding="utf-8")
    return BaseMigration(
        304,
        SOURCE.name,
        "garuda documents",
        rollback_sql=split_migration_sql(sql)[1],
        _sql_dir=sql_dir,
    )


def _without_bracket(sql: str) -> str:
    """Returns sql with its three set_config records, three RESET ROLE statements and three resume blocks removed."""
    assert sql.count(RECORD) == 3
    assert sql.count("RESET ROLE;\n") == 3
    sql = sql.replace(RECORD, "").replace("RESET ROLE;\n", "")
    for tag in RESUME_TAGS:
        start = sql.index(f"DO ${tag}$")
        end = sql.index(f"${tag}$;") + len(f"${tag}$;")
        sql = sql[:start] + sql[end:]
    return sql


async def _build_substrate(admin_url: str, *, split_owners: bool, scopes: tuple[str, ...]) -> str:
    """Creates a database with the policy table and both ledgers (299 columns included); returns its admin DSN."""
    name = f"m304_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    dsn = admin_url.rsplit("/", 1)[0] + f"/{name}"
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(_policies_ddl(scopes))
        if split_owners:
            await conn.execute(f"GRANT CREATE, USAGE ON SCHEMA public TO {RUNTIME}, {LEDGER}")
            await conn.execute(f"ALTER TABLE public.visa_decision_retention_policies OWNER TO {LEDGER}")
            await conn.execute(
                f"GRANT SELECT, REFERENCES ON public.visa_decision_retention_policies TO {RUNTIME}"
            )
            await conn.execute(f"SET ROLE {RUNTIME}")
        await BaseMigration(304, SOURCE.name, "substrate", rollback_sql="SELECT 1")._ensure_migration_log(
            conn
        )
        await conn.execute(split_migration_sql(PROVENANCE.read_text(encoding="utf-8"))[0])
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


async def _catalogue(dsn: str) -> dict[str, object]:
    """Reads 304's table and function owners, both ledger counts, applied_as and whether the scope CHECK lists GARUDA_DOCUMENT."""
    conn = await asyncpg.connect(dsn)
    try:
        return {
            "tables": dict(
                await conn.fetch(
                    "SELECT relname, pg_get_userbyid(relowner) FROM pg_class WHERE relkind = 'r' "
                    "AND relname IN ('garuda_documents', 'garuda_document_review_fields')"
                )
            ),
            "functions": dict(
                await conn.fetch(
                    "SELECT proname, pg_get_userbyid(proowner) FROM pg_proc WHERE proname = ANY($1::text[])",
                    list(FUNCTIONS),
                )
            ),
            "ledgers": {
                ledger: await conn.fetchval(f"SELECT count(*) FROM {ledger} WHERE migration_number = 304")
                for ledger in ("schema_migrations", "_schema_versions")
            },
            "applied_as": await conn.fetchval(
                "SELECT applied_as FROM _schema_versions WHERE migration_number = 304"
            ),
            "scope_widened": await conn.fetchval(
                "SELECT bool_or(pg_get_constraintdef(oid) LIKE '%GARUDA_DOCUMENT%') FROM pg_constraint "
                "WHERE conrelid = 'public.visa_decision_retention_policies'::regclass AND contype = 'c'"
            ),
        }
    finally:
        await conn.close()


async def test_304_applies_as_a_superuser_session_with_the_production_roles_absent() -> None:
    try:
        probe = await asyncpg.connect(_CI_ADMIN_URL)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no admin Postgres reachable: {type(exc).__name__}")
    try:
        shape = await probe.fetchrow(
            "SELECT session_user AS su, "
            "(SELECT rolsuper FROM pg_roles WHERE rolname = session_user) AS su_super, "
            "to_regrole('backend_rag_v2') IS NULL AND to_regrole('visa_ledger_owner') IS NULL AS roles_absent"
        )
    finally:
        await probe.close()
    if not (shape["su_super"] and shape["roles_absent"]):
        pytest.skip("needs a superuser session with backend_rag_v2 and visa_ledger_owner absent")

    dsn = await _build_substrate(_CI_ADMIN_URL, split_owners=False, scopes=NARROW_SCOPES)
    try:
        assert await _migration().apply(database_url=dsn, dedicated=False)
        assert await _migration().apply(database_url=dsn, dedicated=False)
        catalogue = await _catalogue(dsn)
        session = shape["su"]
        assert catalogue["applied_as"] == session
        assert catalogue["ledgers"] == {"schema_migrations": 1, "_schema_versions": 1}
        assert catalogue["tables"] == {"garuda_documents": session, "garuda_document_review_fields": session}
        assert catalogue["functions"] == dict.fromkeys(FUNCTIONS, session)
        assert catalogue["scope_widened"] is True

        async with MigrationManager(database_url=dsn) as manager:
            assert manager._dedicated is False
            assert await manager.rollback_migration(_migration().migration_name)
        catalogue = await _catalogue(dsn)
        assert catalogue["tables"] == {} and catalogue["functions"] == {}
        assert catalogue["ledgers"] == {"schema_migrations": 0, "_schema_versions": 0}
        assert catalogue["scope_widened"] is False
    finally:
        await _drop_database(_CI_ADMIN_URL, dsn)


@pytest_asyncio.fixture
async def disposable_cluster() -> AsyncIterator[str]:
    """Yields a local cluster's superuser DSN after creating the three production role names; skips if any pre-exists; drops them after."""
    if not _DISPOSABLE_ADMIN_URL:
        pytest.skip("OPTION_D_DISPOSABLE_PG_URL unset: this shape creates cluster-wide production role names")
    if urlsplit(_DISPOSABLE_ADMIN_URL).hostname not in ("127.0.0.1", "localhost"):
        pytest.skip("OPTION_D_DISPOSABLE_PG_URL must name a local cluster")
    admin = await asyncpg.connect(_DISPOSABLE_ADMIN_URL)
    created: list[str] = []
    try:
        assert await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = session_user")
        if await admin.fetchval(
            "SELECT count(*) FROM pg_roles WHERE rolname = ANY($1::text[])", [RUNTIME, LEDGER, MIGRATOR]
        ):
            pytest.skip("a production role name already exists on this cluster")
        for role, login in ((RUNTIME, "LOGIN"), (LEDGER, "NOLOGIN"), (MIGRATOR, "LOGIN")):
            await admin.execute(f"CREATE ROLE {role} NOSUPERUSER INHERIT {login}")
            created.append(role)
        options = "WITH INHERIT TRUE, SET TRUE" if await admin.fetchval(
            "SELECT current_setting('server_version_num')::int >= 160000"
        ) else ""
        await admin.execute(f"GRANT {RUNTIME}, {LEDGER} TO {MIGRATOR} {options}")
        yield _DISPOSABLE_ADMIN_URL
    finally:
        for role in reversed(created):
            await admin.execute(f"DROP ROLE IF EXISTS {role}")
        await admin.close()


@pytest.mark.parametrize("scopes", [WIDENED_SCOPES, NARROW_SCOPES], ids=["scope-prewidened", "scope-narrow"])
async def test_304_applies_through_the_dedicated_migrator(
    disposable_cluster: str, monkeypatch: pytest.MonkeyPatch, scopes: tuple[str, ...]
) -> None:
    dsn = await _build_substrate(disposable_cluster, split_owners=True, scopes=scopes)
    try:
        monkeypatch.setattr(migration_base.settings, "migration_database_url", _dsn_as(dsn, MIGRATOR))
        async with MigrationManager() as manager:
            assert manager._dedicated is True
            assert await manager.apply_migration(_migration())
            assert await manager.apply_migration(_migration())
        catalogue = await _catalogue(dsn)
        assert catalogue["applied_as"] == f"{RUNTIME} (session_user={MIGRATOR})"
        assert catalogue["ledgers"] == {"schema_migrations": 1, "_schema_versions": 1}
        assert catalogue["tables"] == {"garuda_documents": RUNTIME, "garuda_document_review_fields": RUNTIME}
        assert catalogue["functions"] == {
            "bind_garuda_document_retention_policy": LEDGER,
            "guard_garuda_document_mutation": RUNTIME,
            "active_garuda_document_policy_available": RUNTIME,
        }
        assert catalogue["scope_widened"] is True
        conn = await asyncpg.connect(dsn)
        try:
            assert await conn.fetchval(f"SELECT pg_has_role('{RUNTIME}', '{LEDGER}', 'MEMBER')") is False
        finally:
            await conn.close()

        async with MigrationManager() as manager:
            assert await manager.rollback_migration(_migration().migration_name)
        catalogue = await _catalogue(dsn)
        assert catalogue["tables"] == {} and catalogue["functions"] == {}
        assert catalogue["ledgers"] == {"schema_migrations": 0, "_schema_versions": 0}
        assert catalogue["scope_widened"] is False
    finally:
        await _drop_database(disposable_cluster, dsn)


async def test_304_fails_atomically_when_the_runtime_role_applies_it_on_the_single_dsn(
    disposable_cluster: str,
) -> None:
    dsn = await _build_substrate(disposable_cluster, split_owners=True, scopes=WIDENED_SCOPES)
    try:
        with pytest.raises(MigrationError, match="still owned by"):
            await _migration().apply(database_url=_dsn_as(dsn, RUNTIME), dedicated=False)
        catalogue = await _catalogue(dsn)
        assert catalogue["tables"] == {}
        assert catalogue["ledgers"] == {"schema_migrations": 0, "_schema_versions": 0}
    finally:
        await _drop_database(disposable_cluster, dsn)


async def test_304_rollback_without_its_role_bracket_fails_atomically_through_the_migrator(
    disposable_cluster: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    sql = SOURCE.read_text(encoding="utf-8")
    migration = BaseMigration(
        304, SOURCE.name, "garuda documents", rollback_sql=split_migration_sql(_without_bracket(sql))[1]
    )
    dsn = await _build_substrate(disposable_cluster, split_owners=True, scopes=WIDENED_SCOPES)
    try:
        monkeypatch.setattr(migration_base.settings, "migration_database_url", _dsn_as(dsn, MIGRATOR))
        async with MigrationManager() as manager:
            assert await manager.apply_migration(migration)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await manager.rollback_migration(migration.migration_name)
        catalogue = await _catalogue(dsn)
        assert catalogue["tables"] == {"garuda_documents": RUNTIME, "garuda_document_review_fields": RUNTIME}
        assert catalogue["functions"]["bind_garuda_document_retention_policy"] == LEDGER
        assert catalogue["ledgers"] == {"schema_migrations": 1, "_schema_versions": 1}
    finally:
        await _drop_database(disposable_cluster, dsn)


async def test_304_applies_and_rolls_back_as_a_superuser_session_with_ungranted_production_roles_present(
    disposable_cluster: str,
) -> None:
    dsn = await _build_substrate(disposable_cluster, split_owners=False, scopes=NARROW_SCOPES)
    conn = await asyncpg.connect(dsn)
    try:
        session = await conn.fetchval("SELECT session_user")
        assert await conn.fetchval(f"SELECT has_schema_privilege('{RUNTIME}', 'public', 'CREATE')") is False
    finally:
        await conn.close()
    try:
        assert await _migration().apply(database_url=dsn, dedicated=False)
        catalogue = await _catalogue(dsn)
        assert catalogue["applied_as"] == session
        assert catalogue["ledgers"] == {"schema_migrations": 1, "_schema_versions": 1}
        assert catalogue["tables"] == {"garuda_documents": session, "garuda_document_review_fields": session}
        assert catalogue["functions"] == {
            "bind_garuda_document_retention_policy": LEDGER,
            "guard_garuda_document_mutation": session,
            "active_garuda_document_policy_available": session,
        }

        async with MigrationManager(database_url=dsn) as manager:
            assert await manager.rollback_migration(_migration().migration_name)
        catalogue = await _catalogue(dsn)
        assert catalogue["tables"] == {} and catalogue["functions"] == {}
        assert catalogue["ledgers"] == {"schema_migrations": 0, "_schema_versions": 0}
    finally:
        await _drop_database(disposable_cluster, dsn)


@pytest.mark.parametrize(
    ("scopes", "sqlstate"),
    [(WIDENED_SCOPES, "P0001"), (NARROW_SCOPES, "42501")],
    ids=["scope-prewidened", "scope-narrow"],
)
async def test_304_without_its_role_bracket_fails_atomically_through_the_migrator(
    disposable_cluster: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scopes: tuple[str, ...],
    sqlstate: str,
) -> None:
    (tmp_path / SOURCE.name).write_text(_without_bracket(SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
    dsn = await _build_substrate(disposable_cluster, split_owners=True, scopes=scopes)
    try:
        monkeypatch.setattr(migration_base.settings, "migration_database_url", _dsn_as(dsn, MIGRATOR))
        async with MigrationManager() as manager:
            with pytest.raises(MigrationError) as excinfo:
                await manager.apply_migration(_migration(tmp_path))
        assert excinfo.value.__cause__.sqlstate == sqlstate
        catalogue = await _catalogue(dsn)
        assert catalogue["tables"] == {}
        assert catalogue["ledgers"] == {"schema_migrations": 0, "_schema_versions": 0}
        assert catalogue["scope_widened"] is (scopes == WIDENED_SCOPES)
    finally:
        await _drop_database(disposable_cluster, dsn)


async def test_304_fails_atomically_under_a_connection_time_role_and_applies_once_it_is_reset(
    disposable_cluster: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    dsn = await _build_substrate(disposable_cluster, split_owners=True, scopes=WIDENED_SCOPES)
    admin = await asyncpg.connect(disposable_cluster)
    try:
        monkeypatch.setattr(migration_base.settings, "migration_database_url", _dsn_as(dsn, MIGRATOR))
        await admin.execute(f"ALTER ROLE {MIGRATOR} SET role = '{RUNTIME}'")
        try:
            async with MigrationManager() as manager:
                with pytest.raises(MigrationError, match="still owned by"):
                    await manager.apply_migration(_migration())
        finally:
            await admin.execute(f"ALTER ROLE {MIGRATOR} RESET role")
        catalogue = await _catalogue(dsn)
        assert catalogue["tables"] == {}
        assert catalogue["ledgers"] == {"schema_migrations": 0, "_schema_versions": 0}

        async with MigrationManager() as manager:
            assert await manager.apply_migration(_migration())
        catalogue = await _catalogue(dsn)
        assert catalogue["applied_as"] == f"{RUNTIME} (session_user={MIGRATOR})"
        assert catalogue["functions"]["bind_garuda_document_retention_policy"] == LEDGER
        assert catalogue["ledgers"] == {"schema_migrations": 1, "_schema_versions": 1}
    finally:
        await admin.close()
        await _drop_database(disposable_cluster, dsn)
