"""Real PG acceptance for the existing stream consumer's persistence seam.

Synthetic fixtures only. Run through this mandate's run_disposable_pg.py.
The target identity guard runs before any schema write.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from backend.core.pg_json_codec import init_asyncpg_connection
from backend.db.repositories.conversation_repository import ConversationRepository
from backend.services.common import cache

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def conversation_pool(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[asyncpg.Pool]:
    expected = os.environ.get("NUZ_UNIVERSAL_PG_SYSTEM_ID")
    dsn = os.environ.get("NUZ_UNIVERSAL_PG_DSN")
    if not expected or not dsn:
        pytest.skip("Requires mandate-owned disposable PostgreSQL")
    admin = await asyncpg.connect(dsn)
    try:
        identity = await admin.fetchrow(
            "SELECT current_user AS role, current_database() AS db, "
            "system_identifier::text AS system_id FROM pg_control_system()"
        )
        if dict(identity) != {
            "role": "universal_db_test_owner",
            "db": "universal_db_test",
            "system_id": expected,
        }:
            pytest.fail("Refusing a database outside this disposable test cluster")
        schema = "universal_test_" + uuid4().hex
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        pool = await asyncpg.create_pool(
            dsn,
            min_size=2,
            max_size=10,
            command_timeout=10,
            init=init_asyncpg_connection,
            server_settings={"search_path": schema + ",public"},
        )
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE conversations (
                        id SERIAL PRIMARY KEY,
                        user_id varchar(255), session_id varchar(255),
                        messages jsonb, metadata jsonb,
                        created_at timestamptz DEFAULT now()
                    );
                    CREATE INDEX ON conversations(session_id);
                    CREATE FUNCTION universal_delay() RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN PERFORM pg_sleep(0.03); RETURN NEW; END $$;
                    CREATE TRIGGER force_overlap BEFORE INSERT OR UPDATE ON conversations
                    FOR EACH ROW EXECUTE FUNCTION universal_delay();
                """)

            async def ignore_cache(_pattern: str) -> int:
                return 0

            monkeypatch.setattr(cache, "_invalidate_cache", ignore_cache)
            yield pool
        finally:
            await pool.close()
            await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
    finally:
        await admin.close()


@pytest.mark.asyncio
async def test_reader_uses_same_tied_timestamp_order_as_writer(
    conversation_pool: asyncpg.Pool,
) -> None:
    async with conversation_pool.acquire() as conn:
        await conn.execute("""INSERT INTO conversations(session_id, messages, created_at) VALUES
            ('synthetic-tie', '[{"content":"older-id"}]', '2026-01-01T00:00:00Z'),
            ('synthetic-tie', '[{"content":"newer-id"}]', '2026-01-01T00:00:00Z')""")
    assert await ConversationRepository(conversation_pool).get_messages("synthetic-tie") == [
        {"content": "newer-id"}
    ]


@pytest.mark.asyncio
async def test_sequential_save_preserves_id_and_messages(conversation_pool: asyncpg.Pool) -> None:
    repo = ConversationRepository(conversation_pool)
    first = await repo.save_messages(
        "synthetic-session", "synthetic-user", [{"role": "user", "content": "first"}]
    )
    second = await repo.save_messages(
        "synthetic-session", "synthetic-user", [{"role": "assistant", "content": "second"}]
    )
    assert first is not None and first == second
    async with conversation_pool.acquire() as conn:
        assert await conn.fetchval("SELECT jsonb_array_length(messages) FROM conversations") == 2


@pytest.mark.asyncio
async def test_concurrent_first_saves_have_one_id(conversation_pool: asyncpg.Pool) -> None:
    repo = ConversationRepository(conversation_pool)
    ids = await asyncio.gather(
        *(
            repo.save_messages(
                "synthetic-session", "synthetic-user", [{"role": "user", "content": f"item-{i}"}]
            )
            for i in range(8)
        )
    )
    assert None not in ids
    assert len(set(ids)) == 1
    async with conversation_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM conversations") == 1
        assert await conn.fetchval("SELECT jsonb_array_length(messages) FROM conversations") == 8


@pytest.mark.asyncio
async def test_concurrent_appends_do_not_lose_updates(conversation_pool: asyncpg.Pool) -> None:
    repo = ConversationRepository(conversation_pool)
    first = await repo.save_messages(
        "synthetic-session", "synthetic-user", [{"role": "user", "content": "seed"}]
    )
    ids = await asyncio.gather(
        *(
            repo.save_messages(
                "synthetic-session", "synthetic-user", [{"role": "user", "content": f"item-{i}"}]
            )
            for i in range(8)
        )
    )
    assert all(identifier == first for identifier in ids)
    async with conversation_pool.acquire() as conn:
        messages = await conn.fetchval("SELECT messages FROM conversations")
    assert {message["content"] for message in messages} == {"seed"} | {
        f"item-{i}" for i in range(8)
    }


@pytest.mark.asyncio
async def test_adjacent_replay_preserves_legacy_dedup(conversation_pool: asyncpg.Pool) -> None:
    repo = ConversationRepository(conversation_pool)
    payload = [{"role": "user", "content": "repeat"}]
    first = await repo.save_messages("synthetic-session", "synthetic-user", payload)
    assert await repo.save_messages("synthetic-session", "synthetic-user", payload) == first
    async with conversation_pool.acquire() as conn:
        assert await conn.fetchval("SELECT jsonb_array_length(messages) FROM conversations") == 1


@pytest.mark.asyncio
async def test_database_rejection_does_not_log_payload_or_leave_partial_write(
    conversation_pool: asyncpg.Pool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = ConversationRepository(conversation_pool)
    async with conversation_pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE conversations ADD CHECK (messages::text NOT LIKE '%synthetic-private-sentinel%')"
        )
    with caplog.at_level("WARNING"):
        assert (
            await repo.save_messages(
                "synthetic-secret-session",
                "synthetic-user",
                [{"content": "synthetic-private-sentinel"}],
            )
            is None
        )
    assert "synthetic-private-sentinel" not in caplog.text
    assert "synthetic-secret-session" not in caplog.text
    assert "CheckViolationError" in caplog.text
    async with conversation_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM conversations") == 0
    assert (
        await repo.save_messages(
            "synthetic-secret-session", "synthetic-user", [{"content": "safe"}]
        )
        is not None
    )


@pytest.mark.asyncio
async def test_cache_outage_keeps_committed_data_and_safe_logs(
    conversation_pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def cache_failure(pattern: str) -> None:
        raise RuntimeError("synthetic-private-cache-value " + pattern)

    monkeypatch.setattr(cache, "_invalidate_cache", cache_failure)
    with caplog.at_level("WARNING"):
        identifier = await ConversationRepository(conversation_pool).save_messages(
            "synthetic-secret-session",
            "synthetic-user",
            [{"content": "safe"}],
        )
    assert identifier is not None
    assert "synthetic-private-cache-value" not in caplog.text
    assert "synthetic-secret-session" not in caplog.text
    async with conversation_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM conversations") == 1


@pytest.mark.asyncio
async def test_cancelled_transaction_releases_session_lock(conversation_pool: asyncpg.Pool) -> None:
    repo = ConversationRepository(conversation_pool)
    async with conversation_pool.acquire() as conn:
        await conn.execute("""CREATE OR REPLACE FUNCTION universal_delay() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(10); RETURN NEW; END $$""")
    task = asyncio.create_task(
        repo.save_messages("synthetic-session", "synthetic-user", [{"content": "cancelled"}])
    )
    try:
        async with conversation_pool.acquire() as conn:
            for _ in range(100):
                locked = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND classid=$1 AND granted)",
                    0x43564E53,
                )
                if locked:
                    break
                await asyncio.sleep(0.01)
            assert locked, "Writer did not reach its transaction lock"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with conversation_pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM conversations") == 0
            await conn.execute("DROP TRIGGER force_overlap ON conversations")
        assert (
            await asyncio.wait_for(
                repo.save_messages(
                    "synthetic-session", "synthetic-user", [{"content": "after-cancel"}]
                ),
                timeout=2,
            )
            is not None
        )
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_synthetic_backup_restore_preserves_post_change_records(
    conversation_pool: asyncpg.Pool,
    tmp_path: Path,
) -> None:
    if not os.environ.get("NUZ_UNIVERSAL_PG_BIN"):
        pytest.skip("Requires disposable cluster backup binaries")
    repo = ConversationRepository(conversation_pool)
    identifier = await repo.save_messages(
        "synthetic-session", "synthetic-user", [{"content": "before"}]
    )
    await repo.save_messages(
        "synthetic-session", "synthetic-user", [{"content": "after-candidate"}]
    )
    async with conversation_pool.acquire() as conn:
        schema = await conn.fetchval("SELECT current_schema()")
        before = dict(
            await conn.fetchrow(
                "SELECT id, user_id, session_id, messages, metadata FROM conversations"
            )
        )
    binary = Path(os.environ["NUZ_UNIVERSAL_PG_BIN"])
    dump = tmp_path / "synthetic.dump"
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"HOME", "PATH", "LANG", "LC_ALL", "TMPDIR"}
    }
    # The harness creates a credential-free DSN; do not put any DSN in argv.
    target = urlsplit(os.environ["NUZ_UNIVERSAL_PG_DSN"])
    assert target.hostname == "127.0.0.1" and target.password is None and target.port
    env.update(
        PGHOST=target.hostname,
        PGPORT=str(target.port),
        PGUSER=target.username,
        PGDATABASE="universal_db_test",
        PGPASSFILE=os.devnull,
    )
    result = await asyncio.to_thread(
        subprocess.run,
        [str(binary / "pg_dump"), "--format=custom", "--schema", schema, "--file", str(dump)],
        env=env,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, "Synthetic backup failed"
    async with conversation_pool.acquire() as conn:
        await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
    result = await asyncio.to_thread(
        subprocess.run,
        [str(binary / "pg_restore"), "--dbname", "universal_db_test", "--exit-on-error", str(dump)],
        env=env,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, "Synthetic restore failed"
    await conversation_pool.expire_connections()
    async with conversation_pool.acquire() as conn:
        after = dict(
            await conn.fetchrow(
                "SELECT id, user_id, session_id, messages, metadata FROM conversations"
            )
        )
    assert after == before and after["id"] == identifier
    assert [message["content"] for message in after["messages"]] == ["before", "after-candidate"]
