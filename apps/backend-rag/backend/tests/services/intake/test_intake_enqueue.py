"""Integration tests for the intake enqueue core (FASE 1B).

Runs against the LOCAL nuzantara_dev DB (same default as tests/db/conftest.py).
enqueue() opens its own transaction via the pool, so we cannot wrap the whole
test in a single rolled-back connection; instead each test uses a unique blob
(tmp file with random content → unique sha256) and cleans up its own rows by
blob_hash in teardown.
"""

from __future__ import annotations

import json
import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

from backend.services.intake.enqueue import (
    PIPELINE_VERSION,
    compute_blob_hash,
    compute_intake_key,
    enqueue,
)

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    p = await asyncpg.create_pool(dsn=_DB_URL, min_size=1, max_size=3)
    try:
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture
async def cleanup_hashes(pool: asyncpg.Pool):
    """Track blob_hashes created by a test and purge their rows at teardown."""
    hashes: list[str] = []
    yield hashes
    if hashes:
        async with pool.acquire() as conn:
            # Defense-in-depth: delete child rows first. Migration 210 sets
            # ON DELETE CASCADE on these FKs, but the explicit purge keeps the
            # teardown robust even if run against a pre-CASCADE schema.
            await conn.execute(
                "DELETE FROM intake_stage_metrics WHERE queue_id IN "
                "(SELECT id FROM intake_queue WHERE blob_hash = ANY($1::char(64)[]))",
                hashes,
            )
            await conn.execute(
                "DELETE FROM document_routing_proposal WHERE queue_id IN "
                "(SELECT id FROM intake_queue WHERE blob_hash = ANY($1::char(64)[]))",
                hashes,
            )
            await conn.execute(
                "DELETE FROM intake_corrections WHERE queue_id IN "
                "(SELECT id FROM intake_queue WHERE blob_hash = ANY($1::char(64)[]))",
                hashes,
            )
            await conn.execute(
                "DELETE FROM intake_queue WHERE blob_hash = ANY($1::char(64)[])", hashes
            )
            await conn.execute(
                "DELETE FROM document_instances WHERE blob_hash = ANY($1::char(64)[])", hashes
            )


def _make_blob(tmp_path, content: bytes | None = None) -> str:
    p = tmp_path / f"blob_{uuid.uuid4().hex}.bin"
    p.write_bytes(content if content is not None else uuid.uuid4().bytes * 8)
    return str(p)


def test_intake_key_is_deterministic_and_sep_pipe():
    k1 = compute_intake_key("whatsapp", "whatsapp:1", "a" * 64, "intake-v1")
    k2 = compute_intake_key("whatsapp", "whatsapp:1", "a" * 64, "intake-v1")
    assert k1 == k2
    import hashlib

    raw = "whatsapp|whatsapp:1|" + ("a" * 64) + "|intake-v1"
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert k1 == expected


async def test_enqueue_idempotent_same_blob(pool, cleanup_hashes, tmp_path):
    """Same blob from same source twice → 1 instance, 1 queue row, was_new False 2nd."""
    blob = _make_blob(tmp_path)
    bh = compute_blob_hash(blob)
    cleanup_hashes.append(bh)

    r1 = await enqueue(pool, source="whatsapp", source_ref="whatsapp:t1", blob_path=blob)
    r2 = await enqueue(pool, source="whatsapp", source_ref="whatsapp:t1", blob_path=blob)

    assert r1.was_new is True
    assert r2.was_new is False
    assert r1.instance_id == r2.instance_id
    assert r1.queue_id == r2.queue_id

    async with pool.acquire() as conn:
        n_inst = await conn.fetchval(
            "SELECT count(*) FROM document_instances WHERE blob_hash = $1", bh
        )
        n_queue = await conn.fetchval(
            "SELECT count(*) FROM intake_queue WHERE blob_hash = $1", bh
        )
    assert n_inst == 1
    assert n_queue == 1


async def test_enqueue_cross_source_dedup(pool, cleanup_hashes, tmp_path):
    """Same blob from whatsapp AND drive → 1 document_instance, 2 intake_queue rows."""
    blob = _make_blob(tmp_path)
    bh = compute_blob_hash(blob)
    cleanup_hashes.append(bh)

    r_wa = await enqueue(pool, source="whatsapp", source_ref="whatsapp:x", blob_path=blob)
    r_drive = await enqueue(pool, source="drive", source_ref="drive:fileX", blob_path=blob)

    # Same physical blob → same document_instance (exact cross-source dedup, X1).
    assert r_wa.instance_id == r_drive.instance_id
    # Different intake_key (source differs) → distinct queue rows.
    assert r_wa.queue_id != r_drive.queue_id
    assert r_wa.was_new is True
    assert r_drive.was_new is True

    async with pool.acquire() as conn:
        n_inst = await conn.fetchval(
            "SELECT count(*) FROM document_instances WHERE blob_hash = $1", bh
        )
        keys = await conn.fetch(
            "SELECT intake_key FROM intake_queue WHERE blob_hash = $1 ORDER BY source", bh
        )
    assert n_inst == 1
    assert len({k["intake_key"] for k in keys}) == 2


async def test_enqueue_persists_hint_and_pipeline(pool, cleanup_hashes, tmp_path):
    """client_id_hint stored as-is; pipeline_version + intake_key match contract."""
    blob = _make_blob(tmp_path)
    bh = compute_blob_hash(blob)
    cleanup_hashes.append(bh)

    res = await enqueue(
        pool,
        source="whatsapp",
        source_ref="whatsapp:hint",
        blob_path=blob,
        client_id_hint=4242,
        source_context={
            "transport": "wa-mirror",
            "chat_type": "direct",
            "crm_identity_policy": "phone_keyed_direct_chat",
        },
    )
    expected_key = compute_intake_key("whatsapp", "whatsapp:hint", bh, PIPELINE_VERSION)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT client_id_hint, pipeline_version, intake_key, status, source_context "
            "FROM intake_queue WHERE id = $1",
            res.queue_id,
        )
    assert row["client_id_hint"] == 4242
    assert row["pipeline_version"] == PIPELINE_VERSION
    assert row["intake_key"] == expected_key
    assert row["status"] == "pending"
    source_context = row["source_context"]
    if isinstance(source_context, str):
        source_context = json.loads(source_context)
    assert source_context == {
        "transport": "wa-mirror",
        "chat_type": "direct",
        "crm_identity_policy": "phone_keyed_direct_chat",
    }


async def test_enqueue_rejects_bad_source(pool, tmp_path):
    blob = _make_blob(tmp_path)
    with pytest.raises(ValueError):
        await enqueue(pool, source="email", source_ref="email:1", blob_path=blob)
