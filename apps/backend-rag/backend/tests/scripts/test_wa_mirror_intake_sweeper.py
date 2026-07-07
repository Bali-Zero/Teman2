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
import json
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


async def _noop_text_sweep(_pool: asyncpg.Pool, _batch: int) -> dict[str, int]:
    return {"scanned": 0, "resolved": 0, "skipped": 0}


def _load_sweeper_no_text(monkeypatch: pytest.MonkeyPatch):
    mod = _load_sweeper()
    monkeypatch.setattr(mod, "_sweep_text_clients", _noop_text_sweep)
    return mod


async def _wmc_schema_is_complete(conn: asyncpg.Connection) -> bool:
    """True iff whatsapp_message_context is the FULL wa-mirror runtime schema.

    The table is created + maintained by the wa-mirror Node (Baileys) service,
    NOT by the Python migrations_v2 system — so a migration-only CI database has
    a PARTIAL table that lacks columns the runtime adds (chat_type, group_jid,
    team_member_phone, ...). Migration 193 installs an AFTER INSERT trigger
    (notify_wa_message_inserted) that references NEW.chat_type, so any INSERT on
    the partial schema crashes with `record "new" has no field "chat_type"`.

    This sweeper test exercises a REAL INSERT path, so it is meaningful only
    where the full runtime table exists (the Pro's nuzantara_dev). On a partial
    CI schema we skip — NOT to hide a failure of the sweeper (the sweeper code is
    schema-agnostic; it only SELECTs), but because the test's synthetic-row setup
    depends on a Node-managed table CI does not fully reproduce.
    """
    cols = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'whatsapp_message_context'
           AND column_name IN ('chat_type','group_jid','team_member_phone',
                               'attention_priority','direction','media_type')
        """
    )
    present = {r["column_name"] for r in cols}
    required = {"chat_type", "group_jid", "team_member_phone",
                "attention_priority", "direction", "media_type"}
    return required.issubset(present)


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    p = await asyncpg.create_pool(dsn=_DB_URL, min_size=1, max_size=3)
    try:
        async with p.acquire() as conn:
            if not await _wmc_schema_is_complete(conn):
                pytest.skip(
                    "whatsapp_message_context is the partial migration-only schema "
                    "(no chat_type/group_jid) — wa-mirror runtime table absent. "
                    "Run on the Pro (nuzantara_dev) for full coverage."
                )
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture
async def wmc_rows(pool: asyncpg.Pool):
    """Track synthetic whatsapp_message_context baileys ids + intake blob_hashes for cleanup."""
    state: dict = {"baileys_ids": [], "blob_hashes": [], "phone_normalized": []}
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
        if state["phone_normalized"]:
            await conn.execute(
                """
                DELETE FROM clients
                 WHERE created_by = 'wa-mirror-crm-writer@balizero.com'
                   AND phone_normalized = ANY($1::text[])
                """,
                state["phone_normalized"],
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
    sender_phone: str | None = None,
    chat_type: str | None = "direct",
    group_jid: str | None = None,
) -> int:
    """Insert one synthetic row, return its id (the watermark cursor key)."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO whatsapp_message_context
                (baileys_message_id, media_stored_path, media_type, media_mime,
                 team_member_email, direction, sender_phone, chat_type, group_jid,
                 message_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
            RETURNING id
            """,
            baileys_id,
            blob_path,
            media_type,
            media_mime,
            team_email,
            direction,
            sender_phone,
            chat_type,
            group_jid,
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
    wms = _load_sweeper_no_text(monkeypatch)

    # Two eligible inbound rows (document + image) + one OUTBOUND (must be skipped).
    doc_path, doc_sha = _write_blob(tmp_path, "passport.pdf")
    img_path, img_sha = _write_blob(tmp_path, "ktp.jpg")
    out_path, out_sha = _write_blob(tmp_path, "we_sent.pdf")
    wmc_rows["blob_hashes"] += [doc_sha, img_sha, out_sha]

    bid_doc = f"wamir-doc-{uuid.uuid4()}"
    bid_img = f"wamir-img-{uuid.uuid4()}"
    bid_out = f"wamir-out-{uuid.uuid4()}"
    wmc_rows["baileys_ids"] += [bid_doc, bid_img, bid_out]
    phone_digits = f"62899{uuid.uuid4().int % 10**8:08d}"
    sender_phone = f"+{phone_digits}"
    wmc_rows["phone_normalized"].append(phone_digits)

    id_doc = await _insert_wmc(
        pool, baileys_id=bid_doc, blob_path=doc_path, media_type="document",
        media_mime="application/pdf", team_email="ari@balizero.com",
        sender_phone=sender_phone,
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
            "SELECT source, source_ref, received_by, sender_phone, client_id_hint, source_context"
            " FROM intake_queue WHERE blob_hash=$1",
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
    # m225: the raw transport sender phone is carried onto the queue row.
    assert doc_row["sender_phone"] == sender_phone
    assert doc_row["client_id_hint"] is not None
    direct_context = doc_row["source_context"]
    if isinstance(direct_context, str):
        direct_context = json.loads(direct_context)
    assert direct_context["chat_type"] == "direct"
    assert direct_context["crm_identity_policy"] == "phone_keyed_direct_chat"
    assert direct_context["routing_identity_policy"] == "sender_phone_enabled"
    assert direct_context["sender_phone_forwarded"] is True

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
async def test_sweep_enqueues_group_media_without_phone_identity(
    monkeypatch, tmp_path, pool, wmc_rows
):
    wms = _load_sweeper_no_text(monkeypatch)

    doc_path, doc_sha = _write_blob(tmp_path, "group-passport.pdf")
    wmc_rows["blob_hashes"].append(doc_sha)
    bid = f"wamir-group-{uuid.uuid4()}"
    wmc_rows["baileys_ids"].append(bid)
    sender_phone = f"+62877{uuid.uuid4().int % 10**8:08d}"
    rid = await _insert_wmc(
        pool,
        baileys_id=bid,
        blob_path=doc_path,
        media_type="document",
        media_mime="application/pdf",
        team_email="ari@balizero.com",
        sender_phone=sender_phone,
        chat_type="group",
        group_jid=f"120363{uuid.uuid4().int % 10**10:010d}@g.us",
    )

    monkeypatch.setenv("INTAKE_DATABASE_URL", _DB_URL)
    monkeypatch.setattr(wms, "_load_watermark", lambda: rid - 1)
    saved: dict = {}
    monkeypatch.setattr(wms, "_save_watermark", lambda v: saved.__setitem__("wm", v))

    assert await wms.run_one_tick() == 0

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT source_ref, received_by, sender_phone, client_id_hint, source_context"
            " FROM intake_queue WHERE blob_hash=$1",
            doc_sha,
        )

    assert row is not None
    assert row["source_ref"] == f"wa-mirror:{bid}"
    assert row["received_by"] == "ari@balizero.com"
    assert row["sender_phone"] is None
    assert row["client_id_hint"] is None
    context = row["source_context"]
    if isinstance(context, str):
        context = json.loads(context)
    assert context["chat_type"] == "group"
    assert context["crm_identity_policy"] == "disabled_for_group"
    assert context["routing_identity_policy"] == "group_participant_phone_suppressed"
    assert context["sender_phone_forwarded"] is False
    assert "group_jid_hash" in context
    assert "120363" not in str(context)
    assert saved.get("wm") == rid


@pytest.mark.asyncio
async def test_sweep_idempotent_rerun(monkeypatch, tmp_path, pool, wmc_rows):
    wms = _load_sweeper_no_text(monkeypatch)

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
    wms = _load_sweeper_no_text(monkeypatch)

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
    wms = _load_sweeper_no_text(monkeypatch)

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
    wms = _load_sweeper_no_text(monkeypatch)

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
