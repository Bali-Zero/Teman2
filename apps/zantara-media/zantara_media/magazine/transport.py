"""Persistent async, byte-exact authenticated transport for Magazine ingress."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import struct
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zantara_media.magazine.contracts import (
    AssetProvenanceV2,
    AssetUploadMetadataV2,
    AssetUploadResponseV2,
)
from zantara_media.magazine.reconciler import (
    InMemoryOutcomeJournal,
    OutcomeJournal,
    OutcomeState,
    OutcomeUnknownError,
)

logger = logging.getLogger(__name__)

Reconcile = Callable[[str, str, str], Awaitable[OutcomeState]]
PacketFactory = Callable[[dict[str, str]], Mapping[str, Any]]


class TransportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    siwc_bearer_token: str
    hmac_key_id: str
    hmac_secret: str
    audience: str
    max_attempts: int = Field(default=3, ge=1, le=8)
    base_backoff_seconds: float = Field(default=0.25, ge=0, le=60)
    timeout_seconds: float = Field(default=30, gt=0, le=300)


def _image_metadata(body: bytes) -> tuple[str, int, int]:
    if body.startswith(b"\x89PNG\r\n\x1a\n") and len(body) >= 24:
        width, height = struct.unpack(">II", body[16:24])
        return "image/png", width, height
    if body.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(body):
            if body[index] != 0xFF:
                index += 1
                continue
            marker = body[index + 1]
            length = int.from_bytes(body[index + 2 : index + 4], "big")
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB}:
                height = int.from_bytes(body[index + 5 : index + 7], "big")
                width = int.from_bytes(body[index + 7 : index + 9], "big")
                return "image/jpeg", width, height
            index += 2 + length
    if body.startswith(b"RIFF") and body[8:12] == b"WEBP" and len(body) >= 30:
        chunk = body[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(body[24:27], "little")
            height = 1 + int.from_bytes(body[27:30], "little")
            return "image/webp", width, height
    raise ValueError("unsupported or malformed image source")


class MagazineTransport:
    """One persistent client; every signed request uses its exact transmitted bytes."""

    def __init__(
        self,
        config: TransportConfig,
        *,
        client: httpx.AsyncClient | None = None,
        journal: OutcomeJournal | None = None,
        reconcile: Reconcile | None = None,
    ) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )
        self._journal = journal or InMemoryOutcomeJournal()
        self._reconcile = reconcile

    async def aclose(self) -> None:
        await self._client.aclose()

    def _signed_headers(
        self,
        *,
        method: str,
        path: str,
        content_type: str,
        body: bytes,
        signed_headers: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        extra = {key.lower(): value for key, value in (signed_headers or {}).items()}
        components = [
            method.upper(),
            path,
            content_type.lower(),
            hashlib.sha256(body).hexdigest(),
            timestamp,
            nonce,
            self._config.hmac_key_id,
            self._config.audience,
            *(f"{name}:{extra[name]}" for name in sorted(extra)),
        ]
        signature = hmac.new(
            self._config.hmac_secret.encode(),
            "\n".join(components).encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "authorization": f"Bearer {self._config.siwc_bearer_token}",
            "content-type": content_type,
            "x-magazine-timestamp": timestamp,
            "x-magazine-nonce": nonce,
            "x-magazine-key-id": self._config.hmac_key_id,
            "x-magazine-audience": self._config.audience,
            "x-magazine-signature": signature,
            **extra,
        }

    async def _post_raw(
        self,
        path: str,
        body: bytes,
        *,
        content_type: str,
        operation_id: str,
        signed_headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        body_digest = hashlib.sha256(body).hexdigest()
        for attempt in range(1, self._config.max_attempts + 1):
            headers = self._signed_headers(
                method="POST",
                path=path,
                content_type=content_type,
                body=body,
                signed_headers=signed_headers,
            )
            await self._journal.set(operation_id, OutcomeState.pending)
            try:
                response = await self._client.post(
                    f"{self._config.base_url.rstrip('/')}{path}",
                    content=body,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                await self._journal.set(operation_id, OutcomeState.unknown)
                state = await self._reconcile_outcome(operation_id, path, body_digest)
                if state == OutcomeState.completed:
                    return httpx.Response(200, json={"ok": True, "status": "replay"})
                if state != OutcomeState.absent:
                    raise OutcomeUnknownError(
                        f"remote outcome_unknown for operation {operation_id}"
                    ) from exc
                await self._journal.set(operation_id, OutcomeState.absent)
                if attempt >= self._config.max_attempts:
                    raise
                await self._backoff(attempt)
                continue
            if response.status_code >= 500:
                await self._journal.set(operation_id, OutcomeState.unknown)
                state = await self._reconcile_outcome(operation_id, path, body_digest)
                if state != OutcomeState.absent:
                    raise OutcomeUnknownError(
                        f"remote outcome_unknown for operation {operation_id}"
                    )
                await self._journal.set(operation_id, OutcomeState.absent)
                if attempt < self._config.max_attempts:
                    await self._backoff(attempt)
                    continue
            response.raise_for_status()
            await self._journal.set(operation_id, OutcomeState.completed)
            return response
        raise RuntimeError("retry loop exhausted")

    async def _reconcile_outcome(
        self, operation_id: str, path: str, body_digest: str
    ) -> OutcomeState:
        if self._reconcile is None:
            return OutcomeState.unknown
        return await self._reconcile(operation_id, path, body_digest)

    async def _backoff(self, attempt: int) -> None:
        base = self._config.base_backoff_seconds * (2 ** (attempt - 1))
        jitter = base * (secrets.randbelow(1001) / 1000) if base else 0
        await asyncio.sleep(base + jitter)

    async def post_json(self, path: str, packet: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(
            packet,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        packet_id = str(packet.get("packet_id", hashlib.sha256(body).hexdigest()))
        response = await self._post_raw(
            path,
            body,
            content_type="application/json",
            operation_id=f"{path}:{packet_id}",
        )
        result = response.json()
        if not isinstance(result, dict):
            raise RuntimeError("machine endpoint returned a non-object response")
        return result

    async def upload_asset_bytes(
        self, source: bytes, provenance: AssetProvenanceV2
    ) -> AssetUploadResponseV2:
        mime_type, width, height = _image_metadata(source)
        source_digest = hashlib.sha256(source).hexdigest()
        metadata = AssetUploadMetadataV2(
            **provenance.model_dump(mode="json"),
            schema_version="asset-upload.v2",
            source_sha256=source_digest,
            source_byte_count=len(source),
            source_mime_type=mime_type,
            source_width=width,
            source_height=height,
        )
        metadata_raw = json.dumps(
            metadata.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        response = await self._post_raw(
            "/api/machine/assets",
            source,
            content_type=mime_type,
            operation_id=f"/api/machine/assets:{provenance.packet_id}",
            signed_headers={"x-magazine-asset-metadata": metadata_raw},
        )
        try:
            result = AssetUploadResponseV2.model_validate(response.json())
        except (ValidationError, ValueError, TypeError) as exc:
            raise RuntimeError(f"invalid AssetUploadV2 response: {exc}") from exc
        if result.source_sha256 != source_digest:
            raise RuntimeError("AssetUploadV2 source mismatch")
        return result

    async def publish_edition_with_assets(
        self,
        factory: PacketFactory,
        assets: Sequence[tuple[bytes, AssetProvenanceV2]],
    ) -> dict[str, Any]:
        canonical: dict[str, str] = {}
        for source, provenance in assets:
            result = await self.upload_asset_bytes(source, provenance)
            canonical[provenance.asset_id] = result.canonical_sha256
        packet = factory(canonical)
        return await self.post_json("/api/machine/publications/editions", packet)

    async def submit_collector_run(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        return await self.post_json("/api/machine/collector-runs", packet)

    async def publish_breaking(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        return await self.post_json("/api/machine/publications/breaking", packet)

    async def submit_audit_anchor(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        return await self.post_json("/api/machine/audit-anchor", packet)
