"""Unit tests for Anello 1a — Meta WhatsApp media download.

Runs anywhere (M5/Pro/CI): no network, no DB, no Fly. The two Meta GETs are
served by an ``httpx.MockTransport`` that asserts the request shape (Bearer
header, the metadata-then-bytes sequence) and returns canned responses.
"""

from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from backend.channels.whatsapp.media_download import (
    DownloadedMedia,
    MediaDownloadError,
    download_media,
)

_TOKEN = "test-access-token"
_MEDIA_ID = "1234567890"
_API_VERSION = "v18.0"
_PAYLOAD = b"%PDF-1.4 fake passport scan bytes"
_SIGNED_URL = "https://lookaside.fbsbx.com/whatsapp_business/attachments/abc?token=xyz"


def _make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _metadata_response(*, sha256: str | None, mime: str = "application/pdf") -> httpx.Response:
    body: dict = {"url": _SIGNED_URL, "mime_type": mime, "file_size": len(_PAYLOAD)}
    if sha256 is not None:
        body["sha256"] = sha256
    return httpx.Response(200, content=json.dumps(body).encode(), headers={"content-type": "application/json"})


@pytest.mark.asyncio
async def test_download_happy_path_two_step_sequence(tmp_path):
    """media_id → metadata GET → bytes GET → file on disk, correct fields."""
    calls: list[str] = []
    real_sha = hashlib.sha256(_PAYLOAD).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        # Both calls MUST carry the Bearer token.
        assert request.headers.get("Authorization") == f"Bearer {_TOKEN}"
        if request.url.path.endswith(_MEDIA_ID):
            return _metadata_response(sha256=real_sha)
        if str(request.url) == _SIGNED_URL:
            return httpx.Response(200, content=_PAYLOAD)
        return httpx.Response(404)

    async with _make_client(handler) as client:
        result = await download_media(
            client,
            media_id=_MEDIA_ID,
            access_token=_TOKEN,
            dest_dir=tmp_path,
            api_version=_API_VERSION,
        )

    # Two GETs, metadata first then the signed URL.
    assert len(calls) == 2
    assert calls[0].endswith(f"/{_API_VERSION}/{_MEDIA_ID}")
    assert calls[1] == _SIGNED_URL

    assert isinstance(result, DownloadedMedia)
    assert result.media_id == _MEDIA_ID
    assert result.mime_type == "application/pdf"
    assert result.byte_size == len(_PAYLOAD)
    assert result.sha256 == real_sha
    # File really exists with the exact bytes, .pdf extension, no .part left.
    with open(result.blob_path, "rb") as fh:
        assert fh.read() == _PAYLOAD
    assert result.blob_path.endswith(".pdf")
    assert not result.blob_path.endswith(".part")


@pytest.mark.asyncio
async def test_recomputes_sha_when_meta_omits_it(tmp_path):
    """Meta may omit sha256; we still return a locally-computed one."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(_MEDIA_ID):
            return _metadata_response(sha256=None)
        return httpx.Response(200, content=_PAYLOAD)

    async with _make_client(handler) as client:
        result = await download_media(
            client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
        )
    assert result.sha256 == hashlib.sha256(_PAYLOAD).hexdigest()


@pytest.mark.asyncio
async def test_sha_mismatch_raises_and_writes_nothing(tmp_path):
    """If Meta's declared sha256 disagrees with the bytes, fail hard."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(_MEDIA_ID):
            return _metadata_response(sha256="deadbeef" * 8)  # wrong
        return httpx.Response(200, content=_PAYLOAD)

    async with _make_client(handler) as client:
        with pytest.raises(MediaDownloadError, match="sha256 mismatch"):
            await download_media(
                client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
            )
    # No blob and no stray .part file left behind.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_metadata_http_error_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b'{"error":"invalid token"}')

    async with _make_client(handler) as client:
        with pytest.raises(MediaDownloadError, match="media-metadata GET failed"):
            await download_media(
                client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
            )


@pytest.mark.asyncio
async def test_missing_url_in_metadata_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"mime_type":"application/pdf"}')

    async with _make_client(handler) as client:
        with pytest.raises(MediaDownloadError, match="missing 'url'"):
            await download_media(
                client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
            )


@pytest.mark.asyncio
async def test_empty_body_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(_MEDIA_ID):
            return _metadata_response(sha256=None)
        return httpx.Response(200, content=b"")

    async with _make_client(handler) as client:
        with pytest.raises(MediaDownloadError, match="empty media body"):
            await download_media(
                client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
            )


@pytest.mark.asyncio
async def test_oversize_body_raises(tmp_path):
    big = b"x" * (100 * 1024 * 1024 + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(_MEDIA_ID):
            return _metadata_response(sha256=None)
        return httpx.Response(200, content=big)

    async with _make_client(handler) as client:
        with pytest.raises(MediaDownloadError, match="exceeds"):
            await download_media(
                client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
            )


@pytest.mark.asyncio
async def test_extension_inferred_from_mime(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(_MEDIA_ID):
            return _metadata_response(sha256=None, mime="image/jpeg")
        return httpx.Response(200, content=_PAYLOAD)

    async with _make_client(handler) as client:
        result = await download_media(
            client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
        )
    assert result.blob_path.endswith(".jpg")


@pytest.mark.asyncio
async def test_unknown_mime_falls_back_to_bin(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(_MEDIA_ID):
            return _metadata_response(sha256=None, mime="application/x-weird")
        return httpx.Response(200, content=_PAYLOAD)

    async with _make_client(handler) as client:
        result = await download_media(
            client, media_id=_MEDIA_ID, access_token=_TOKEN, dest_dir=tmp_path
        )
    assert result.blob_path.endswith(".bin")
