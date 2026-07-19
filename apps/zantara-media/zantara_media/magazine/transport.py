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
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zantara_media.magazine.contracts import (
    AssetProvenanceV2,
    AssetUploadMetadataV2,
    AssetUploadResponseV2,
)
from zantara_media.magazine.audit_anchor import ReleaseBlockedError
from zantara_media.magazine.reconciler import (
    InMemoryOutcomeJournal,
    OutcomeBindingError,
    OutcomeJournal,
    OutcomeRecord,
    OutcomeState,
    OutcomeUnknownError,
    ReconcileResult,
)

logger = logging.getLogger(__name__)

Reconcile = Callable[
    [str, str, str], Awaitable[ReconcileResult | OutcomeState]
]
PacketFactory = Callable[[dict[str, str]], Mapping[str, Any]]


class ReleaseGate(Protocol):
    def require_release_allowed(self) -> None: ...


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
        release_gate: ReleaseGate | None = None,
    ) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )
        if journal is None and client is None:
            raise ValueError("production transport requires an explicit durable journal")
        self._journal = journal or InMemoryOutcomeJournal()
        self._reconcile = reconcile
        self._release_gate = release_gate

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
        replay = await self._preflight(operation_id, path, body_digest)
        if replay is not None:
            return self._replay_response(path, replay)
        await self._record(
            operation_id, path, body_digest, OutcomeState.pending, response=None
        )
        for attempt in range(1, self._config.max_attempts + 1):
            headers = self._signed_headers(
                method="POST",
                path=path,
                content_type=content_type,
                body=body,
                signed_headers=signed_headers,
            )
            try:
                response = await self._client.post(
                    f"{self._config.base_url.rstrip('/')}{path}",
                    content=body,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                await self._record(
                    operation_id, path, body_digest, OutcomeState.unknown, response=None
                )
                result = await self._reconcile_outcome(operation_id, path, body_digest)
                if result.state == OutcomeState.completed:
                    if result.response is None:
                        raise OutcomeUnknownError("completed reconciliation omitted response")
                    await self._record(
                        operation_id,
                        path,
                        body_digest,
                        OutcomeState.completed,
                        response=result.response,
                    )
                    return self._replay_response(path, result.response)
                if result.state != OutcomeState.absent:
                    raise OutcomeUnknownError(
                        f"remote outcome_unknown for operation {operation_id}"
                    ) from exc
                await self._record(
                    operation_id, path, body_digest, OutcomeState.absent, response=None
                )
                if attempt >= self._config.max_attempts:
                    raise
                await self._backoff(attempt)
                await self._record(
                    operation_id, path, body_digest, OutcomeState.pending, response=None
                )
                continue
            if response.status_code >= 500:
                await self._record(
                    operation_id, path, body_digest, OutcomeState.unknown, response=None
                )
                result = await self._reconcile_outcome(operation_id, path, body_digest)
                if result.state == OutcomeState.completed:
                    if result.response is None:
                        raise OutcomeUnknownError("completed reconciliation omitted response")
                    await self._record(
                        operation_id,
                        path,
                        body_digest,
                        OutcomeState.completed,
                        response=result.response,
                    )
                    return self._replay_response(path, result.response)
                if result.state != OutcomeState.absent:
                    raise OutcomeUnknownError(
                        f"remote outcome_unknown for operation {operation_id}"
                    )
                await self._record(
                    operation_id, path, body_digest, OutcomeState.absent, response=None
                )
                if attempt < self._config.max_attempts:
                    await self._backoff(attempt)
                    await self._record(
                        operation_id, path, body_digest, OutcomeState.pending, response=None
                    )
                    continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("machine endpoint returned a non-object response")
            await self._record(
                operation_id,
                path,
                body_digest,
                OutcomeState.completed,
                response=payload,
            )
            return response
        raise RuntimeError("retry loop exhausted")

    async def _preflight(
        self, operation_id: str, path: str, body_digest: str
    ) -> dict[str, Any] | None:
        previous = await self._journal.get(operation_id)
        if previous is None:
            return None
        if previous.path != path or previous.body_sha256 != body_digest:
            raise OutcomeBindingError("operation binding mismatch")
        if previous.state == OutcomeState.completed:
            if previous.response is None:
                raise OutcomeUnknownError("completed journal record omitted response")
            return previous.response
        if previous.state == OutcomeState.absent:
            return None
        result = await self._reconcile_outcome(operation_id, path, body_digest)
        if result.state == OutcomeState.completed:
            if result.response is None:
                raise OutcomeUnknownError("completed reconciliation omitted response")
            await self._record(
                operation_id,
                path,
                body_digest,
                OutcomeState.completed,
                response=result.response,
            )
            return result.response
        if result.state == OutcomeState.absent:
            await self._record(
                operation_id, path, body_digest, OutcomeState.absent, response=None
            )
            return None
        raise OutcomeUnknownError(f"remote outcome_unknown for operation {operation_id}")

    async def _record(
        self,
        operation_id: str,
        path: str,
        body_digest: str,
        state: OutcomeState,
        *,
        response: dict[str, Any] | None,
    ) -> None:
        await self._journal.record(
            OutcomeRecord(
                operation_id=operation_id,
                path=path,
                body_sha256=body_digest,
                state=state,
                response=response,
            )
        )

    def _replay_response(
        self, path: str, payload: Mapping[str, Any]
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=dict(payload),
            request=httpx.Request(
                "POST", f"{self._config.base_url.rstrip('/')}{path}"
            ),
        )

    async def _reconcile_outcome(
        self, operation_id: str, path: str, body_digest: str
    ) -> ReconcileResult:
        if self._reconcile is None:
            return ReconcileResult(state=OutcomeState.unknown)
        result = await self._reconcile(operation_id, path, body_digest)
        if isinstance(result, OutcomeState):
            return ReconcileResult(state=result)
        return result

    async def _backoff(self, attempt: int) -> None:
        base = self._config.base_backoff_seconds * (2 ** (attempt - 1))
        jitter = base * (secrets.randbelow(1001) / 1000) if base else 0
        await asyncio.sleep(base + jitter)

    async def post_json(
        self,
        path: str,
        packet: Mapping[str, Any],
    ) -> dict[str, Any]:
        if path in {
            "/api/machine/publications/editions",
            "/api/machine/publications/breaking",
        }:
            if self._release_gate is None:
                raise ReleaseBlockedError("publication transport has no audit release interlock")
            self._release_gate.require_release_allowed()
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
            operation_id=(
                f"/api/machine/assets:{provenance.packet_id}:"
                f"{provenance.asset_id}:{source_digest}"
            ),
            signed_headers={"x-magazine-asset-metadata": metadata_raw},
        )
        try:
            result = AssetUploadResponseV2.model_validate(response.json())
        except (ValidationError, ValueError, TypeError) as exc:
            raise RuntimeError(f"invalid AssetUploadV2 response: {exc}") from exc
        if result.source_sha256 != source_digest:
            raise RuntimeError("AssetUploadV2 source mismatch")
        if result.asset_id != provenance.asset_id:
            raise RuntimeError("AssetUploadV2 asset identity mismatch")
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
