"""Integration test for the Pro media-pull worker (Anello 1, Piece C).

Runs run_one_poll() end-to-end against the LOCAL nuzantara_dev DB:
- the Fly bridge HTTP is faked via httpx.MockTransport (pending + ack);
- download_media is faked to write a real temp blob (no Meta, no token);
- enqueue writes a REAL intake_queue row, which we then assert + clean up.

This is NOT M5-skippable — it touches nuzantara_dev. Run on the Pro.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import asyncpg
import httpx
import pytest
import pytest_asyncio

# test file: apps/backend-rag/backend/tests/scripts/<this>
# parents: [0]=scripts [1]=tests [2]=backend [3]=backend-rag [4]=apps [5]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_WORKER_PATH = _REPO_ROOT / "scripts" / "wa_media_pull_worker.py"

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)
_CHANNEL = "whatsapp_media_pending"


def _load_worker():
    spec = importlib.util.spec_from_file_location("wamp_under_test", _WORKER_PATH)
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
async def cleanup(pool: asyncpg.Pool):
    """Purge intake rows + document_instances created during the test by blob_hash."""
    hashes: list[str] = []
    yield hashes
    if hashes:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM intake_stage_metrics WHERE queue_id IN "
                "(SELECT id FROM intake_queue WHERE blob_hash = ANY($1::text[]))",
                hashes,
            )
            await conn.execute(
                "DELETE FROM intake_queue WHERE blob_hash = ANY($1::text[])", hashes
            )
            await conn.execute(
                "DELETE FROM document_instances WHERE blob_hash = ANY($1::text[])", hashes
            )


@pytest.mark.asyncio
async def test_poll_downloads_enqueues_and_acks(monkeypatch, tmp_path, pool, cleanup):
    import hashlib
    import uuid

    wamp = _load_worker()

    # Unique blob → unique sha256 (the worker passes dl.sha256 as blob_hash).
    content = f"PDF-{uuid.uuid4()}".encode()
    sha = hashlib.sha256(content).hexdigest()
    cleanup.append(sha)

    pending_payload = {
        "items": [
            {
                "outbox_id": 4242,
                "media_id": "media-piece-c-1",
                "mime_type": "application/pdf",
                "message_type": "document",
                "filename": "passport.pdf",
                "declared_sha256": sha,
                "wa_message_id": "wamid.PC1",
                "from_phone": "62811",
                "phone_number_id": "1104946272705747",
                "sender_name": "Tester",
                "created_at": "2026-06-07T00:00:00+00:00",
            }
        ],
        "last_id": 4242,
    }

    ack_seen: dict = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/wa-media/pending"):
            assert request.headers.get("X-Bridge-Auth") == "k"
            return httpx.Response(200, json=pending_payload)
        if request.url.path.endswith("/wa-media/ack"):
            import json as _json

            ack_seen["body"] = _json.loads(request.content)
            return httpx.Response(200, json={"acked": ack_seen["body"]["outbox_ids"]})
        return httpx.Response(404)

    transport = httpx.MockTransport(_handler)
    real_async_client = httpx.AsyncClient

    def _client_factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_async_client(transport=transport)

    monkeypatch.setattr(wamp.httpx, "AsyncClient", _client_factory)

    # Fake the Meta download → write a real local blob, return DownloadedMedia.
    from backend.channels.whatsapp.media_download import DownloadedMedia

    async def fake_download(client, *, media_id, access_token, dest_dir, api_version="v18.0"):
        assert access_token == "fake-token"  # came from Keychain stub
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        blob = dest / f"{media_id}.pdf"
        blob.write_bytes(content)
        return DownloadedMedia(
            blob_path=str(blob),
            mime_type="application/pdf",
            sha256=sha,
            byte_size=len(content),
            media_id=media_id,
        )

    monkeypatch.setattr(wamp, "download_media", fake_download)
    monkeypatch.setattr(wamp, "_read_access_token", lambda: "fake-token")

    # Env: key present, local DB, sovereign blob root in tmp, fresh cursor.
    monkeypatch.setenv("BRIDGE_API_KEY", "k")
    monkeypatch.setenv("LOCAL_DATABASE_URL", _DB_URL)
    monkeypatch.setenv("INTAKE_BLOB_ROOT", str(tmp_path / "blobs"))
    monkeypatch.setenv("FLY_BRIDGE_URL", "https://fake.local")
    monkeypatch.setattr(wamp, "_load_since", lambda: 0)
    saved = {}
    monkeypatch.setattr(wamp, "_save_since", lambda v: saved.__setitem__("since", v))

    rc = await wamp.run_one_poll()
    assert rc == 0

    # A REAL intake_queue row landed locally, with our sha + source_ref.
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT source, source_ref, blob_hash, mime_type, received_by "
            "FROM intake_queue WHERE blob_hash = $1",
            sha,
        )
    assert row is not None
    assert row["source"] == "whatsapp"
    assert row["source_ref"] == "whatsapp-live:wamid.PC1"
    assert row["mime_type"] == "application/pdf"
    assert row["received_by"] is None  # v1 policy

    # Acked exactly the row we processed; cursor advanced.
    assert ack_seen["body"]["outbox_ids"] == [4242]
    assert saved.get("since") == 4242


@pytest.mark.asyncio
async def test_poll_no_pending_returns_zero(monkeypatch):
    wamp = _load_worker()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [], "last_id": 0})

    transport = httpx.MockTransport(_handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(
        wamp.httpx, "AsyncClient",
        lambda *a, **k: real(transport=transport),
    )
    monkeypatch.setattr(wamp, "_read_access_token", lambda: "fake-token")
    monkeypatch.setenv("BRIDGE_API_KEY", "k")
    monkeypatch.setattr(wamp, "_load_since", lambda: 0)

    rc = await wamp.run_one_poll()
    assert rc == 0


@pytest.mark.asyncio
async def test_poll_aborts_without_token(monkeypatch):
    wamp = _load_worker()
    monkeypatch.setenv("BRIDGE_API_KEY", "k")
    monkeypatch.setattr(wamp, "_read_access_token", lambda: "")
    rc = await wamp.run_one_poll()
    assert rc == 1
