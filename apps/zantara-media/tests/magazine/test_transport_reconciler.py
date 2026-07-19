from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest

from zantara_media.magazine.contracts import AssetProvenanceV2
from zantara_media.magazine.reconciler import (
    InMemoryOutcomeJournal,
    OutcomeState,
    OutcomeUnknownError,
)
from zantara_media.magazine.audit_anchor import ReleaseBinding, ZERO_HASH, build_audit_event_hash
from zantara_media.magazine.transport import (
    MagazineTransport,
    TransportConfig,
    _image_metadata,
)


PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c02"
    "0000000b4944415478da6364f80f00010501012718e3660000000049454e44ae426082"
)


class _AllowRelease:
    def require_release_allowed(self, _: ReleaseBinding) -> None:
        return None


def config() -> TransportConfig:
    return TransportConfig(
        base_url="https://magazine.example",
        siwc_bearer_token="dispatcher-token",
        hmac_key_id="key-1",
        hmac_secret="hmac-secret",
        audience="bali-zero-magazine",
        max_attempts=2,
        base_backoff_seconds=0,
    )


def provenance() -> AssetProvenanceV2:
    return AssetProvenanceV2(
        packet_id="asset-packet-1",
        asset_id="asset-1",
        captured_at="2026-07-19T00:00:00Z",
        alt_text="Bali Zero editorial image",
        source="Bali Zero editorial desk",
        source_url=None,
        rights_basis="internal-owned",
        rights_status="approved",
        usage_status="approved",
        dlp_status="passed",
        sanitization_status="passed",
        perceptual_dedup_status="unique",
    )


def release_binding(packet_id: str, *, breaking: bool = False) -> ReleaseBinding:
    path = (
        "/api/machine/publications/breaking"
        if breaking
        else "/api/machine/publications/editions"
    )
    return ReleaseBinding(
        stream_id="magazine-publication.v1",
        stream_seq=1,
        event_hash="a" * 64,
        packet_id=packet_id,
        operation_id=f"{path}:{packet_id}",
    )


@pytest.mark.asyncio
async def test_transport_signs_exact_raw_body_and_metadata_header() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        captured.update(body=body, headers=request.headers, path=request.url.raw_path.decode())
        source_hash = hashlib.sha256(body).hexdigest()
        return httpx.Response(
            201,
            json={
                "ok": True,
                "status": "created",
                "asset_id": "asset-1",
                "source_sha256": source_hash,
                "canonical_sha256": "b" * 64,
                "canonical_mime_type": "image/png",
                "canonical_byte_count": len(body),
                "width": 1,
                "height": 1,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = MagazineTransport(config(), client=client)
    result = await transport.upload_asset_bytes(PNG, provenance())
    assert result.canonical_sha256 == "b" * 64
    assert result.source_sha256 == hashlib.sha256(PNG).hexdigest()
    metadata = captured["headers"]["x-magazine-asset-metadata"]
    signed = "\n".join(
        [
            "POST",
            "/api/machine/assets",
            "image/png",
            hashlib.sha256(PNG).hexdigest(),
            captured["headers"]["x-magazine-timestamp"],
            captured["headers"]["x-magazine-nonce"],
            "key-1",
            "bali-zero-magazine",
            f"x-magazine-asset-metadata:{metadata}",
        ]
    )
    assert captured["headers"]["x-magazine-signature"] == hmac.new(
        b"hmac-secret", signed.encode(), hashlib.sha256
    ).hexdigest()
    assert json.loads(metadata)["source_sha256"] == hashlib.sha256(PNG).hexdigest()
    await transport.aclose()


@pytest.mark.asyncio
async def test_asset_upload_rejects_source_mismatch_or_missing_canonical_digest() -> None:
    responses = [
        {
            "ok": True,
            "status": "created",
            "asset_id": "asset-1",
            "source_sha256": "c" * 64,
            "canonical_sha256": "b" * 64,
            "canonical_mime_type": "image/png",
            "canonical_byte_count": len(PNG),
            "width": 1,
            "height": 1,
        },
        {
            "ok": True,
            "status": "created",
            "asset_id": "asset-1",
            "source_sha256": hashlib.sha256(PNG).hexdigest(),
            "canonical_mime_type": "image/png",
            "canonical_byte_count": len(PNG),
            "width": 1,
            "height": 1,
        },
    ]

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=responses.pop(0))

    first_transport = MagazineTransport(
        config(), client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(RuntimeError, match="source mismatch"):
        await first_transport.upload_asset_bytes(PNG, provenance())
    await first_transport.aclose()

    transport = MagazineTransport(
        config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        release_gate=_AllowRelease(),
    )
    with pytest.raises(RuntimeError, match="canonical_sha256"):
        await transport.upload_asset_bytes(PNG, provenance())
    await transport.aclose()


@pytest.mark.asyncio
async def test_assets_are_uploaded_before_packet_factory_receives_canonical_digests() -> None:
    order: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        if request.url.path == "/api/machine/assets":
            order.append("asset")
            return httpx.Response(
                201,
                json={
                    "ok": True,
                    "status": "created",
                    "asset_id": "asset-1",
                    "source_sha256": hashlib.sha256(body).hexdigest(),
                    "canonical_sha256": "d" * 64,
                    "canonical_mime_type": "image/png",
                    "canonical_byte_count": len(body),
                    "width": 1,
                    "height": 1,
                },
            )
        order.append("edition")
        packet = json.loads(body)
        assert packet["asset_digests"] == ["d" * 64]
        return httpx.Response(201, json={"ok": True, "status": "created"})

    transport = MagazineTransport(
        config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        release_gate=_AllowRelease(),
    )

    def factory(digests: dict[str, str]) -> dict[str, Any]:
        return {"packet_id": "edition-1", "asset_digests": [digests["asset-1"]]}

    await transport.publish_edition_with_assets(
        factory,
        ((PNG, provenance()),),
        release_binding=release_binding("edition-1"),
    )
    assert order == ["asset", "edition"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_outcome_unknown_is_reconciled_before_retry() -> None:
    calls = 0
    reconciliations = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadError("connection dropped after send")
        return httpx.Response(201, json={"ok": True, "status": "created"})

    async def reconcile(_: str, __: str, ___: str) -> OutcomeState:
        nonlocal reconciliations
        reconciliations += 1
        return OutcomeState.absent

    transport = MagazineTransport(
        config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        journal=InMemoryOutcomeJournal(),
        reconcile=reconcile,
        release_gate=_AllowRelease(),
    )
    await transport.post_json(
        "/api/machine/publications/editions",
        {"packet_id": "p1"},
        release_binding=release_binding("p1"),
    )
    assert calls == 2
    assert reconciliations == 1
    await transport.aclose()


@pytest.mark.asyncio
async def test_unknown_remote_outcome_blocks_automatic_retry() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("connection dropped")

    async def reconcile(_: str, __: str, ___: str) -> OutcomeState:
        return OutcomeState.unknown

    transport = MagazineTransport(
        config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        journal=InMemoryOutcomeJournal(),
        reconcile=reconcile,
        release_gate=_AllowRelease(),
    )
    with pytest.raises(OutcomeUnknownError):
        await transport.post_json(
            "/api/machine/publications/breaking",
            {"packet_id": "p2"},
            release_binding=release_binding("p2", breaking=True),
        )
    await transport.aclose()


@pytest.mark.asyncio
async def test_canonical_audit_feed_get_signs_exact_query_and_empty_body() -> None:
    payload = {
        "schema_version": "publication-operation.v1",
        "operation": "edition.publish",
        "packet_id": "edition-1",
    }
    event_hash = build_audit_event_hash(
        "magazine-publication.v1", 1, ZERO_HASH, payload
    )
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        captured.update(path=request.url.raw_path.decode(), body=body, headers=request.headers)
        return httpx.Response(
            200,
            headers={"cache-control": "no-store"},
            json={
                "schema_version": "audit-feed.v1",
                "stream_id": "magazine-publication.v1",
                "checkpoint": {"stream_seq": "0", "event_hash": ZERO_HASH},
                "head": {"stream_seq": "1", "event_hash": event_hash},
                "events": [
                    {
                        "schema_version": "audit-event.v1",
                        "stream_id": "magazine-publication.v1",
                        "stream_seq": "1",
                        "previous_event_hash": ZERO_HASH,
                        "event_hash": event_hash,
                        "payload": payload,
                    }
                ],
                "promotion_target": {
                    "operation": "edition.publish",
                    "packet_id": "edition-1",
                    "stream_seq": "1",
                    "event_hash": event_hash,
                },
                "next_cursor": {"after_seq": "1", "checkpoint_hash": event_hash},
                "has_more": False,
            },
        )

    transport = MagazineTransport(
        config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        release_gate=_AllowRelease(),
    )
    page = await transport.fetch_audit_feed_page(
        stream_id="magazine-publication.v1",
        after_seq=0,
        checkpoint_hash=ZERO_HASH,
        limit=100,
        operation="edition.publish",
        packet_id="edition-1",
    )
    assert page.head.stream_seq == "1"
    assert captured["body"] == b""
    assert captured["path"] == (
        "/api/machine/audit-events/v1?stream_id=magazine-publication.v1&after_seq=0&"
        f"checkpoint_hash={ZERO_HASH}&limit=100&operation=edition.publish&packet_id=edition-1"
    )
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["headers"]["x-magazine-signature"]
    await transport.aclose()


@pytest.mark.asyncio
async def test_publication_stage_requires_private_no_store_response() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "ok": False,
                "error": "promotion_blocked",
                "operation": "edition.publish",
                "packet_id": "edition-1",
            },
        )

    transport = MagazineTransport(
        config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        journal=InMemoryOutcomeJournal(),
        release_gate=_AllowRelease(),
    )
    with pytest.raises(RuntimeError, match="must be no-store"):
        await transport.stage_publication({"packet_id": "edition-1"}, breaking=False)
    await transport.aclose()


def _webp(*chunks: tuple[bytes, bytes]) -> bytes:
    encoded = b"".join(
        chunk
        + len(data).to_bytes(4, "little")
        + data
        + (b"\x00" if len(data) & 1 else b"")
        for chunk, data in chunks
    )
    body = b"WEBP" + encoded
    return b"RIFF" + len(body).to_bytes(4, "little") + body


@pytest.mark.parametrize(
    ("source", "size"),
    [
        (_webp((b"VP8 ", b"\x00\x00\x00\x9d\x01\x2a\x07\x00\x05\x00")), (7, 5)),
        (
            _webp(
                (
                    b"VP8L",
                    b"\x2f" + (((7 - 1) | ((5 - 1) << 14))).to_bytes(4, "little"),
                )
            ),
            (7, 5),
        ),
        (
            _webp(
                (b"VP8X", b"\x00\x00\x00\x00\x06\x00\x00\x04\x00\x00"),
                (b"VP8 ", b"\x00\x00\x00\x9d\x01\x2a\x07\x00\x05\x00"),
            ),
            (7, 5),
        ),
    ],
)
def test_all_sites_supported_webp_variants_are_accepted(
    source: bytes, size: tuple[int, int]
) -> None:
    assert _image_metadata(source) == ("image/webp", *size)
