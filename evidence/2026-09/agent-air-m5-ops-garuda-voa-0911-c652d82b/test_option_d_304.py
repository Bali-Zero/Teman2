"""Independent, real-PG proof of the complete 304 migration via option D.

Requires run_disposable_pg.py: role names deliberately match production so
the unchanged runner and SQL constants are exercised. No customer data.
The substrate models the observed production prerequisites, not a fresh
installation: widened scope, runtime SELECT and REFERENCES, ledger owner.
"""

import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

from backend.db import migration_base
from backend.db.migration_base import BaseMigration, MigrationError, split_migration_sql
from backend.db.migration_manager import MigrationManager

ADMIN = os.environ['TEST_DATABASE_URL']
RUNTIME = 'backend_rag_v2'
LEDGER = 'visa_ledger_owner'
MIGRATOR = 'backend_rag_migrator'
SOURCE = BaseMigration.MIGRATIONS_DIR / '304_garuda_documents.sql'


def with_role(dsn, role):
    return 'postgresql://' + role + '@' + dsn.split('@', 1)[1]


def bracketed_sql():
    sql = SOURCE.read_text()
    start = 'DO $garuda_304_owner_transfer$\n'
    end = '$garuda_304_owner_transfer$;\n'
    assert sql.count(start) == sql.count(end) == 1
    return sql.replace(start, 'RESET ROLE;\n' + start).replace(end, end + 'SET ROLE backend_rag_v2;\n')


@pytest_asyncio.fixture
async def substrate(monkeypatch):
    # Refuse the operational DB/tunnel even if somebody bypasses the driver.
    assert ADMIN.startswith('postgresql://voa_proof_admin@127.0.0.1:')
    admin = await asyncpg.connect(ADMIN)
    name = 'voa_option_d_' + uuid.uuid4().hex[:12]
    for role in (RUNTIME, LEDGER, MIGRATOR):
        if not await admin.fetchval('SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=$1)', role):
            await admin.execute(f'CREATE ROLE {role} NOSUPERUSER LOGIN')
    await admin.execute(f'GRANT {RUNTIME}, {LEDGER} TO {MIGRATOR} WITH INHERIT TRUE, SET TRUE')
    await admin.execute(f'CREATE DATABASE {name}')
    dsn = ADMIN.rsplit('/', 1)[0] + '/' + name
    owner = await asyncpg.connect(dsn)
    try:
        await owner.execute(f'GRANT CREATE, USAGE ON SCHEMA public TO {RUNTIME}, {LEDGER}')
        await owner.execute('''
            CREATE TABLE visa_decision_retention_policies (
                id uuid PRIMARY KEY,
                environment text NOT NULL,
                policy_scope text NOT NULL CHECK (policy_scope IN
                  ('VISA_DECISION','GARUDA_CHECK','GARUDA_ORDER','GARUDA_MAGIC_LINK','GARUDA_DOCUMENT')),
                effective_period tstzrange NOT NULL,
                retention_interval interval NOT NULL,
                retention_anchor text NOT NULL
            );
            ALTER TABLE visa_decision_retention_policies OWNER TO visa_ledger_owner;
            GRANT SELECT, REFERENCES ON visa_decision_retention_policies TO backend_rag_v2;
        ''')
        await owner.execute('SET ROLE backend_rag_v2')
        migration = BaseMigration(304, SOURCE.name, 'VOA option D proof', rollback_sql='SELECT 1')
        await migration._ensure_migration_log(owner)
        await owner.execute(split_migration_sql(
            (SOURCE.parent / '299_schema_versions_provenance.sql').read_text())[0])
    finally:
        await owner.close()
    monkeypatch.setattr(migration_base.settings, 'database_url', with_role(dsn, RUNTIME))
    monkeypatch.setattr(migration_base.settings, 'migration_database_url', with_role(dsn, MIGRATOR))
    try:
        yield dsn
    finally:
        await admin.execute(f'DROP DATABASE {name} WITH (FORCE)')
        await admin.close()


def migration_at(tmp_path, *, bracket=True):
    sql = bracketed_sql() if bracket else SOURCE.read_text()
    target = tmp_path / SOURCE.name
    target.write_text(sql)
    return BaseMigration(304, target.name, 'VOA option D proof',
                         rollback_sql=split_migration_sql(sql)[1], _sql_dir=tmp_path)


@pytest.mark.asyncio
async def test_unbracketed_304_fails_atomically(substrate, tmp_path):
    async with MigrationManager() as manager:
        with pytest.raises(MigrationError, match='still owned by'):
            await manager.apply_migration(migration_at(tmp_path, bracket=False))
    conn = await asyncpg.connect(substrate)
    try:
        assert await conn.fetchval("SELECT to_regclass('garuda_documents')") is None
        for ledger in ('schema_migrations', '_schema_versions'):
            assert await conn.fetchval(f'SELECT count(*) FROM {ledger} WHERE migration_number=304') == 0
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('via_manager', [True, False])
async def test_full_304_owners_provenance_runtime_insert_and_replay(substrate, tmp_path, via_manager):
    migration = migration_at(tmp_path)
    if via_manager:
        async with MigrationManager() as manager:
            assert await manager.apply_migration(migration)
            assert await manager.apply_migration(migration)  # runner skip, not naked SQL replay
    else:
        assert await migration.apply()
        assert await migration.apply()
    conn = await asyncpg.connect(substrate)
    try:
        owners = dict(await conn.fetch("SELECT relname, pg_get_userbyid(relowner) FROM pg_class "
            "WHERE relname IN ('garuda_documents','garuda_document_review_fields','schema_migrations','_schema_versions')"))
        assert set(owners.values()) == {RUNTIME} and len(owners) == 4
        functions = dict(await conn.fetch("SELECT proname, pg_get_userbyid(proowner) FROM pg_proc "
            "WHERE proname IN ('bind_garuda_document_retention_policy','guard_garuda_document_mutation',"
            "'active_garuda_document_policy_available')"))
        assert functions == {'bind_garuda_document_retention_policy': LEDGER,
                             'guard_garuda_document_mutation': RUNTIME,
                             'active_garuda_document_policy_available': RUNTIME}
        for ledger in ('schema_migrations', '_schema_versions'):
            assert await conn.fetchval(f'SELECT count(*) FROM {ledger} WHERE migration_number=304') == 1
        assert await conn.fetchval('SELECT applied_as FROM _schema_versions WHERE migration_number=304') == (
            RUNTIME + ' (session_user=' + MIGRATOR + ')')
        assert not await conn.fetchval("SELECT pg_has_role('backend_rag_v2','visa_ledger_owner','MEMBER')")
        await conn.execute('SET ROLE backend_rag_v2')
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute('SELECT id FROM visa_decision_retention_policies FOR SHARE')
        insert = '''INSERT INTO garuda_documents
            (key_sha256, canonical_payload_sha256, document_id, environment, processing_state)
            VALUES ($1,$2,$3,'TEST','LOW_CONFIDENCE')'''
        with pytest.raises(asyncpg.RaiseError, match='no active Zero-approved retention policy'):
            await conn.execute(insert, b'a' * 32, b'b' * 32, 'c' * 32)
        await conn.execute('RESET ROLE')
        # Synthetic fixture interval; not a business retention-policy decision.
        await conn.execute("INSERT INTO visa_decision_retention_policies VALUES "
            "($1,'TEST','GARUDA_DOCUMENT',tstzrange(now()-interval '1 day',now()+interval '1 day'),"
            "interval '1 hour','CREATED_AT')", uuid.uuid4())
        await conn.execute('SET ROLE backend_rag_v2')
        await conn.execute(insert, b'a' * 32, b'b' * 32, 'c' * 32)
        await conn.execute("INSERT INTO garuda_document_review_fields VALUES ($1,'passport_number',true)", 'c' * 32)
        assert await conn.fetchval('SELECT count(*) FROM garuda_documents') == 1
        assert await conn.fetchval('SELECT count(*) FROM garuda_document_review_fields') == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_explicit_database_override_preserves_legacy_mode(substrate, tmp_path):
    # A dedicated DSN is set globally but this caller explicitly chooses a
    # different legacy connection. Its authenticated role must stay unchanged.
    path = tmp_path / '998_override_probe.sql'
    path.write_text('CREATE TABLE override_probe (id int);\n-- === ROLLBACK ===\nDROP TABLE override_probe;')
    migration = BaseMigration(998, path.name, 'explicit override proof',
                             rollback_sql='DROP TABLE override_probe;', _sql_dir=tmp_path)
    async with MigrationManager(database_url=substrate) as manager:
        assert await manager.apply_migration(migration)
    conn = await asyncpg.connect(substrate)
    try:
        assert await conn.fetchval("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='override_probe'::regclass") == 'voa_proof_admin'
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_pool_reacquire_restores_runtime_after_explicit_reset(substrate):
    async with MigrationManager() as manager:
        for _ in range(2):
            async with manager.pool.acquire() as conn:
                assert await conn.fetchval('SELECT current_user') == RUNTIME
                assert await conn.fetchval('SELECT session_user') == MIGRATOR
                await conn.execute('RESET ROLE')
                assert await conn.fetchval('SELECT current_user') == MIGRATOR


@pytest.mark.asyncio
async def test_manager_freezes_url_and_mode_together(substrate, tmp_path, monkeypatch):
    manager = MigrationManager()
    monkeypatch.setattr(migration_base.settings, 'database_url', ADMIN)
    monkeypatch.setattr(migration_base.settings, 'migration_database_url', None)
    async with manager:
        async with manager.pool.acquire() as conn:
            assert await conn.fetchval('SELECT current_database()') == substrate.rsplit('/', 1)[1]
            assert await conn.fetchval('SELECT current_user') == RUNTIME
        assert await manager.apply_migration(migration_at(tmp_path))
    conn = await asyncpg.connect(substrate)
    try:
        assert await conn.fetchval('SELECT applied_as FROM _schema_versions WHERE migration_number=304') == (
            RUNTIME + ' (session_user=' + MIGRATOR + ')')
    finally:
        await conn.close()
