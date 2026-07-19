"""Byte-exact audit verification and Pro-local Ed25519 checkpoint ledger."""

from __future__ import annotations

import asyncio
import base64
import fcntl
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, field_validator

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_MILLISECOND_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)
_UNSIGNED_DECIMAL = re.compile(r"^(?:0|[1-9]\d*)$")
ZERO_HASH = "0" * 64


class AuditChainMismatch(RuntimeError):
    """The observed audit chain conflicts with canonical history."""


class ReleaseBlockedError(RuntimeError):
    """Publication promotion is fail-closed after an audit incident."""


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuditEventRecord(FrozenModel):
    stream_id: str
    stream_seq: int
    previous_event_hash: str
    event_hash: str
    payload: Any


class AuditAnchorBodyV1(FrozenModel):
    schema_version: str
    anchor_id: str
    stream_id: str
    stream_seq: str
    event_hash: str
    previous_anchor_hash: str
    observed_at: str
    key_id: str

    @field_validator("stream_seq")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        if not _UNSIGNED_DECIMAL.fullmatch(value):
            raise ValueError("stream_seq must be an unsigned decimal string")
        return value

    @field_validator("event_hash", "previous_anchor_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("anchor hashes must be lowercase SHA-256 digests")
        return value

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: str) -> str:
        if not _MILLISECOND_TIMESTAMP.fullmatch(value):
            raise ValueError("observed_at must have exactly three fractional digits and Z")
        return value


class AuditAnchorReceiptV1(FrozenModel):
    body: AuditAnchorBodyV1
    signature: str
    anchor_hash: str

    @field_validator("anchor_hash")
    @classmethod
    def validate_anchor_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("anchor_hash must be a lowercase SHA-256 digest")
        return value


def _raw_hash(value: str) -> bytes:
    if not _SHA256.fullmatch(value):
        raise ValueError("audit hashes must be lowercase SHA-256 digests")
    return bytes.fromhex(value)


def build_audit_event_hash(
    stream_id: str,
    stream_seq: int,
    previous_event_hash: str,
    payload: Any,
) -> str:
    normalized = unicodedata.normalize("NFC", stream_id)
    if not normalized:
        raise ValueError("audit stream id must not be empty")
    if stream_seq < 0:
        raise ValueError("audit stream sequence must be unsigned")
    stream = normalized.encode("utf-8")
    body = rfc8785.dumps(payload)
    preimage = b"".join(
        (
            b"BZM-AUDIT-EVENT-V1\0",
            len(stream).to_bytes(4, "big"),
            stream,
            stream_seq.to_bytes(8, "big"),
            _raw_hash(previous_event_hash),
            len(body).to_bytes(8, "big"),
            body,
        )
    )
    return hashlib.sha256(preimage).hexdigest()


def verify_audit_stream(
    events: tuple[AuditEventRecord, ...],
    *,
    expected_sequence: int = 1,
    expected_previous_hash: str = ZERO_HASH,
) -> AuditEventRecord:
    if not events:
        raise AuditChainMismatch("audit stream is empty")
    stream_id = events[0].stream_id
    previous = expected_previous_hash
    sequence = expected_sequence
    for item in events:
        if item.stream_id != stream_id:
            raise AuditChainMismatch("audit stream id changed within checkpoint")
        if item.stream_seq != sequence:
            raise AuditChainMismatch("audit stream contains a sequence gap")
        if item.previous_event_hash != previous:
            raise AuditChainMismatch("audit stream previous hash mismatch")
        expected_hash = build_audit_event_hash(
            item.stream_id,
            item.stream_seq,
            item.previous_event_hash,
            item.payload,
        )
        if item.event_hash != expected_hash:
            raise AuditChainMismatch("audit stream event hash mismatch")
        previous = item.event_hash
        sequence += 1
    return events[-1]


def _anchor_body_bytes(body: AuditAnchorBodyV1) -> bytes:
    return rfc8785.dumps(body.model_dump(mode="json"))


def _signature_preimage(body_bytes: bytes) -> bytes:
    return b"BZM-AUDIT-ANCHOR-V1\0" + len(body_bytes).to_bytes(8, "big") + body_bytes


def _decode_signature(value: str) -> bytes:
    if "=" in value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise AuditChainMismatch("anchor signature is not unpadded base64url")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError as exc:
        raise AuditChainMismatch("anchor signature encoding is malformed") from exc
    if len(decoded) != 64:
        raise AuditChainMismatch("anchor signature must contain 64 bytes")
    return decoded


def verify_anchor_receipt(
    receipt: AuditAnchorReceiptV1,
    public_key: Ed25519PublicKey,
) -> None:
    body_bytes = _anchor_body_bytes(receipt.body)
    signature = _decode_signature(receipt.signature)
    try:
        public_key.verify(signature, _signature_preimage(body_bytes))
    except InvalidSignature as exc:
        raise AuditChainMismatch("anchor Ed25519 signature mismatch") from exc
    expected = hashlib.sha256(
        b"BZM-AUDIT-ANCHOR-RECORD-V1\0"
        + len(body_bytes).to_bytes(8, "big")
        + body_bytes
        + signature
    ).hexdigest()
    if receipt.anchor_hash != expected:
        raise AuditChainMismatch("anchor record hash mismatch")


class DurableAnchorLedger:
    """Append-only, fsynced receipt ledger; never truncates or rewrites."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def append(self, receipt: AuditAnchorReceiptV1) -> None:
        row = json.dumps(
            receipt.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode() + b"\n"
        async with self._lock:
            await asyncio.to_thread(self._append_sync, row)

    async def read_all(self) -> tuple[AuditAnchorReceiptV1, ...]:
        async with self._lock:
            raw = await asyncio.to_thread(self._read_sync)
        receipts = tuple(AuditAnchorReceiptV1.model_validate(item) for item in raw)
        prior_by_stream: dict[str, str] = {}
        for receipt in receipts:
            expected = prior_by_stream.get(receipt.body.stream_id, ZERO_HASH)
            if receipt.body.previous_anchor_hash != expected:
                raise AuditChainMismatch("append-only anchor ledger chain mismatch")
            prior_by_stream[receipt.body.stream_id] = receipt.anchor_hash
        return receipts

    def _append_sync(self, row: bytes) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            view = memoryview(row)
            while view:
                view = view[os.write(descriptor, view) :]
            os.fsync(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_sync(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                data = handle.read()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        if data and not data.endswith(b"\n"):
            raise AuditChainMismatch("anchor ledger has a truncated final record")
        try:
            return [json.loads(line) for line in data.splitlines() if line]
        except json.JSONDecodeError as exc:
            raise AuditChainMismatch("anchor ledger contains malformed JSON") from exc


class AuditAnchorService:
    def __init__(
        self,
        *,
        key_id: str,
        private_key: Ed25519PrivateKey,
        ledger: DurableAnchorLedger,
    ) -> None:
        self._key_id = key_id
        self._private_key = private_key
        self._ledger = ledger
        self.release_blocked = False

    def require_release_allowed(self) -> None:
        if self.release_blocked:
            raise ReleaseBlockedError("release blocked by audit checkpoint conflict")

    async def anchor(
        self,
        events: tuple[AuditEventRecord, ...],
        *,
        observed_at: str,
    ) -> AuditAnchorReceiptV1:
        try:
            prior = await self._ledger.read_all()
            stream_id = events[0].stream_id if events else ""
            stream_receipts = tuple(item for item in prior if item.body.stream_id == stream_id)
            previous_receipt = stream_receipts[-1] if stream_receipts else None
            if previous_receipt is not None:
                previous_sequence = int(previous_receipt.body.stream_seq)
                if events and events[-1].stream_seq == previous_sequence:
                    if events[-1].event_hash != previous_receipt.body.event_hash:
                        raise AuditChainMismatch("checkpoint conflicts with prior Pro anchor")
                    return previous_receipt
                head = verify_audit_stream(
                    events,
                    expected_sequence=previous_sequence + 1,
                    expected_previous_hash=previous_receipt.body.event_hash,
                )
                previous_anchor_hash = previous_receipt.anchor_hash
            else:
                head = verify_audit_stream(events)
                previous_anchor_hash = ZERO_HASH
            anchor_seed = (
                f"{head.stream_id}\0{head.stream_seq}\0{head.event_hash}\0{observed_at}\0{self._key_id}"
            ).encode()
            body = AuditAnchorBodyV1(
                schema_version="audit-anchor.v1",
                anchor_id=f"anchor-{hashlib.sha256(anchor_seed).hexdigest()[:24]}",
                stream_id=unicodedata.normalize("NFC", head.stream_id),
                stream_seq=str(head.stream_seq),
                event_hash=head.event_hash,
                previous_anchor_hash=previous_anchor_hash,
                observed_at=observed_at,
                key_id=self._key_id,
            )
            body_bytes = _anchor_body_bytes(body)
            signature_bytes = self._private_key.sign(_signature_preimage(body_bytes))
            signature = base64.urlsafe_b64encode(signature_bytes).decode().rstrip("=")
            anchor_hash = hashlib.sha256(
                b"BZM-AUDIT-ANCHOR-RECORD-V1\0"
                + len(body_bytes).to_bytes(8, "big")
                + body_bytes
                + signature_bytes
            ).hexdigest()
            receipt = AuditAnchorReceiptV1(
                body=body,
                signature=signature,
                anchor_hash=anchor_hash,
            )
            verify_anchor_receipt(receipt, self._private_key.public_key())
            await self._ledger.append(receipt)
            return receipt
        except (AuditChainMismatch, OSError, ValueError):
            self.release_blocked = True
            raise
