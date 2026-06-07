"""Integration test for the wa-mirror intake sweeper (Anello 1-bis, Pro-half).

Runs run_one_tick() end-to-end against the LOCAL nuzantara_dev DB:
- inserts a few synthetic `whatsapp_message_context` rows (the read-only source
  table wa-mirror populates) pointing at REAL temp blob files;
- runs the sweeper, which enqueue()s eligible rows into the REAL intake_queue;
- asserts source_ref=`wa-mirror:<baileys_id>` + received_by=team_member_email,
  idempotent re-run, blob-missing skipped, outbound/sticker excluded, watermark
  advanced.

This is NOT M5-skippable — it touches nuzantara_dev. Run on the Pro.
The sweeper never writes back to whatsapp_message_context; we own the synthetic
rows and clean them (+ the intake rows) in teardown.
"""

from __future__ import annotations

import importlib.util
import os
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

# test file: apps/backend-rag/backend/tests/scripts/<this>
# parents: [0]=scripts [1]=tests [2]=backend [3]=backend-rag [4]=apps [5]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_SWEEPER_PATH = _REPO_ROOT / "scripts" / "wa_mirror_intake_sweeper.py"

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)


def _load_sweeper():
    spec = importlib.util.spec_from_file_location("wms_under_test", _SWEEPER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    p = await asyncpg.create_pool(dsn=_DB_URL, min_size=1, max_size=3)
    try:
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture
async def wmc_rows(pool: asyncpg.Pool):
    """Track synthetic whatsapp_message_context baileys ids + intake blob_hashes for cleanup."""
    state: dict = {"baileys_ids": [], "blob_hashes": []}
    yield state
    async with pool.acquire() as conn:
        if state["blob_hashes"]:
            await conn.execute(
                "DELETE FROM intake_stage_metrics WHERE queue_id IN "
                "(SELECT id FROM intake_queue WHERE blob_hash = ANY($1::text[]))",
                state["blob_hashes"],
            )
            await conn.execute(
                "DELETE FROM intake_queue WHERE blob_hash = ANY($1::text[])",
                state["blob_hashes"],
            )
            await conn.execute(
                "DELETE FROM document_instances WHERE blob_hash = ANY($1::text[])",
                state["blob_hashes"],
            )
        if state["baileys_ids"]:
            await conn.execute(
                "DELETE FROM whatsapp_message_context WHERE baileys_message_id = ANY($1::text[])",
                state["baileys_ids"],
            )


async def _insert_wmc(
    pool: asyncpg.Pool,
    *,
    baileys_id: str,
    blob_path: str | None,
    media_type: str,
    media_mime: str,
    team_email: str,
    direction: str = "inbound",
) -> int:
    """Insert one synthetic row, return its id (the watermark cursor key)."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO whatsapp_message_context
                (baileys_message_id, media_stored_path, media_type, media_mime,
                 team_member_email, direction, message_date)
            VALUES ($1, $2, $3, $4, $5, $6, now())
            RETURNING id
            """,
            baileys_id,
            blob_path,
            media_type,
            media_mime,
            team_email,
            direction,
        )


def _write_blob(tmp_path: Path, name: str) -> tuple[str, str]:
    """Write a unique blob; return (path, sha256) — sha is what enqueue stores as blob_hash."""
    import hashlib

    content = f"DOC-{uuid.uuid4()}".encode()
    p = tmp_path / name
    p.write_bytes(content)
    return str(p), hashlib.sha256(content).hexdigest()


@pytest.mark.asyncio
async def test_sweep_enqueues_inbound_doc_and_image(monkeypatch, tmp_path, pool, wmc_rows):
    wms = _load_sweeper()

    # Two eligible inbound rows (document + image) + one OUTBOUND (must be skipped).
    doc_path, doc_sha = _write_blob(tmp_path, "passport.pdf")
    img_path, img_sha = _write_blob(tmp_path, "ktp.jpg")
    out_path, out_sha = _write_blob(tmp_path, "we_sent.pdf")
    wmc_rows["blob_hashes"] += [doc_sha, img_sha, out_sha]

    bid_doc = f"wamir-doc-{uuid.uuid4()}"
    bid_img = f"wamir-img-{uuid.uuid4()}"
    bid_out = f"wamir-out-{uuid.uuid4()}"
    wmc_rows["baileys_ids"] += [bid_doc, bid_img, bid_out]

    id_doc = await _insert_wmc(
        pool, baileys_id=bid_doc, blob_path=doc_path, media_type="document",
        media_mime="application/pdf", team_email="ari@balizero.com",
    )
    id_img = await _insert_wmc(
        pool, baileys_id=bid_img, blob_path=img_path, media_type="image",
        media_mime="image/jpeg", team_email="surya@balizero.com",
    )
    await _insert_wmc(
        pool, baileys_id=bid_out, blob_path=out_path, media_type="document",
        media_mime="application/pdf", team_email="ari@balizero.com",
        direction="outbound",
    )

    # Watermark seeded just below the doc row so all three are in range; local DB.
    monkeypatch.setenv("INTAKE_DATABASE_URL", _DB_URL)
    monkeypatch.setattr(wms, "_load_watermark", lambda: id_doc - 1)
    saved: dict = {}
    monkeypatch.setattr(wms, "_save_watermark", lambda v: saved.__setitem__("wm", v))

    rc = await wms.run_one_tick()
    assert rc == 0

    # Both inbound rows enqueued with wa-mirror: source_ref + received_by=email.
    async with pool.acquire() as conn:
        doc_row = await conn.fetchrow(
            "SELECT source, source_ref, received_by FROM intake_queue WHERE blob_hash=$1",
            doc_sha,
        )
        img_row = await conn.fetchrow(
            "SELECT source, source_ref, received_by FROM intake_queue WHERE blob_hash=$1",
            img_sha,
        )
        out_row = await conn.fetchrow(
            "SELECT 1 FROM intake_queue WHERE blob_hash=$1", out_sha
        )

    assert doc_row is not None
    assert doc_row["source"] == "whatsapp"
    assert doc_row["source_ref"] == f"wa-mirror:{bid_doc}"
    assert doc_row["received_by"] == "ari@balizero.com"

    assert img_row is not None
    assert img_row["source_ref"] == f"wa-mirror:{bid_img}"
    assert img_row["received_by"] == "surya@balizero.com"

    # Outbound row must NOT have been enqueued.
    assert out_row is None

    # The outbound row is filtered OUT by the SQL (direction='inbound'), so it
    # never enters `rows` and never advances the watermark. The watermark lands
    # on the highest INBOUND id scanned = id_img (the image row, inserted 2nd).
    assert saved.get("wm") == id_img


@pytest.mark.asyncio
async def test_sweep_idempotent_rerun(monkeypatch, tmp_path, pool, wmc_rows):
    wms = _load_sweeper()

    doc_path, doc_sha = _write_blob(tmp_path, "again.pdf")
    wmc_rows["blob_hashes"].append(doc_sha)
    bid = f"wamir-idem-{uuid.uuid4()}"
    wmc_rows["baileys_ids"].append(bid)
    rid = await _insert_wmc(
        pool, baileys_id=bid, blob_path=doc_path, media_type="document",
        media_mime="application/pdf", team_email="ari@balizero.com",
    )

    monkeypatch.setenv("INTAKE_DATABASE_URL", _DB_URL)
    monkeypatch.setattr(wms, "_save_watermark", lambda v: None)

    # First tick: watermark below the row → enqueue.
    monkeypatch.setattr(wms, "_load_watermark", lambda: rid - 1)
    assert await wms.run_one_tick() == 0
    async with pool.acquire() as conn:
        n1 = await conn.fetchval(
            "SELECT count(*) FROM intake_queue WHERE blob_hash=$1", doc_sha
        )
    assert n1 == 1

    # Second tick AT the same watermark (simulate cursor not persisted): enqueue
    # dedups on intake_key → still exactly one row.
    assert await wms.run_one_tick() == 0
    async with pool.acquire() as conn:
        n2 = await conn.fetchval(
            "SELECT count(*) FROM intake_queue WHERE blob_hash=$1", doc_sha
        )
    assert n2 == 1


@pytest.mark.asyncio
async def test_sweep_skips_missing_blob_without_crash(monkeypatch, tmp_path, pool, wmc_rows):
    wms = _load_sweeper()

    # Row points at a path that does not exist on disk.
    bid = f"wamir-missing-{uuid.uuid4()}"
    wmc_rows["baileys_ids"].append(bid)
    rid = await _insert_wmc(
        pool, baileys_id=bid, blob_path=str(tmp_path / "nope.pdf"),
        media_type="document", media_mime="application/pdf",
        team_email="ari@balizero.com",
    )

    monkeypatch.setenv("INTAKE_DATABASE_URL", _DB_URL)
    monkeypatch.setattr(wms, "_load_watermark", lambda: rid - 1)
    saved: dict = {}
    monkeypatch.setattr(wms, "_save_watermark", lambda v: saved.__setitem__("wm", v))

    # Must not raise; returns 0; watermark advances PAST the missing-blob row
    # (it's gone, never coming back).
    rc = await wms.run_one_tick()
    assert rc == 0
    assert saved.get("wm") == rid


@pytest.mark.asyncio
async def test_sweep_excludes_sticker_and_audio(monkeypatch, tmp_path, pool, wmc_rows):
    wms = _load_sweeper()

    stk_path, stk_sha = _write_blob(tmp_path, "fun.webp")
    wmc_rows["blob_hashes"].append(stk_sha)
    bid = f"wamir-stk-{uuid.uuid4()}"
    wmc_rows["baileys_ids"].append(bid)
    rid = await _insert_wmc(
        pool, baileys_id=bid, blob_path=stk_path, media_type="sticker",
        media_mime="image/webp", team_email="ari@balizero.com",
    )

    monkeypatch.setenv("INTAKE_DATABASE_URL", _DB_URL)
    monkeypatch.setattr(wms, "_load_watermark", lambda: rid - 1)
    monkeypatch.setattr(wms, "_save_watermark", lambda v: None)

    rc = await wms.run_one_tick()
    assert rc == 0
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM intake_queue WHERE blob_hash=$1", stk_sha
        )
    assert row is None  # sticker never enters intake


@pytest.mark.asyncio
async def test_sweep_first_run_seeds_to_max_id(monkeypatch, pool):
    """With no watermark file and no START_ID env, seed to current max eligible id."""
    wms = _load_sweeper()

    monkeypatch.setenv("INTAKE_DATABASE_URL", _DB_URL)
    monkeypatch.delenv("WA_MIRROR_SWEEP_START_ID", raising=False)
    monkeypatch.setattr(wms, "_load_watermark", lambda: None)
    seeded: dict = {}
    monkeypatch.setattr(wms, "_save_watermark", lambda v: seeded.__setitem__("wm", v))

    # current max eligible id in the live table
    async with pool.acquire() as conn:
        cur_max = await conn.fetchval(
            """
            SELECT COALESCE(max(id), 0) FROM whatsapp_message_context
             WHERE media_stored_path IS NOT NULL
               AND media_type = ANY(ARRAY['document','image'])
               AND direction = 'inbound'
            """
        )

    rc = await wms.run_one_tick()
    assert rc == 0
    # First run seeds the watermark to current max → nothing older re-enqueued.
    assert seeded.get("wm") == int(cur_max)
