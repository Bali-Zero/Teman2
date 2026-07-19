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
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    schema_version: Literal["audit-event.v1"] = "audit-event.v1"
    stream_id: str
    stream_seq: int = Field(ge=0, le=9_007_199_254_740_991)
    previous_event_hash: str
    event_hash: str
    payload: Any


class AuditAnchorBodyV1(FrozenModel):
    schema_version: Literal["audit-anchor.v1"]
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

    @property
    def path(self) -> Path:
        return self._path

    async def read_all(
        self, public_key: Ed25519PublicKey | None = None
    ) -> tuple[AuditAnchorReceiptV1, ...]:
        async with self._lock:
            raw = await asyncio.to_thread(self._read_sync)
        receipts = tuple(AuditAnchorReceiptV1.model_validate(item) for item in raw)
        self._verify_history(receipts, public_key)
        return receipts

    async def anchor_atomic(
        self,
        events: tuple[AuditEventRecord, ...],
        *,
        observed_at: str,
        key_id: str,
        private_key: Ed25519PrivateKey,
    ) -> AuditAnchorReceiptV1:
        """Verify history, create, append and fsync under one exclusive file lock."""

        async with self._lock:
            return await asyncio.to_thread(
                self._anchor_sync,
                events,
                observed_at,
                key_id,
                private_key,
            )

    @staticmethod
    def _verify_history(
        receipts: tuple[AuditAnchorReceiptV1, ...],
        public_key: Ed25519PublicKey | None,
    ) -> None:
        prior_by_stream: dict[str, str] = {}
        for receipt in receipts:
            expected = prior_by_stream.get(receipt.body.stream_id, ZERO_HASH)
            if receipt.body.previous_anchor_hash != expected:
                raise AuditChainMismatch("append-only anchor ledger chain mismatch")
            if public_key is not None:
                verify_anchor_receipt(receipt, public_key)
            prior_by_stream[receipt.body.stream_id] = receipt.anchor_hash

    def _anchor_sync(
        self,
        events: tuple[AuditEventRecord, ...],
        observed_at: str,
        key_id: str,
        private_key: Ed25519PrivateKey,
    ) -> AuditAnchorReceiptV1:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            raw = self._read_descriptor(descriptor)
            receipts = tuple(AuditAnchorReceiptV1.model_validate(item) for item in raw)
            self._verify_history(receipts, private_key.public_key())
            stream_id = events[0].stream_id if events else ""
            stream_receipts = tuple(
                item for item in receipts if item.body.stream_id == stream_id
            )
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
            receipt = _build_receipt(
                head,
                observed_at=observed_at,
                key_id=key_id,
                previous_anchor_hash=previous_anchor_hash,
                private_key=private_key,
            )
            row = (
                json.dumps(
                    receipt.model_dump(mode="json"),
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )
            os.lseek(descriptor, 0, os.SEEK_END)
            view = memoryview(row)
            while view:
                view = view[os.write(descriptor, view) :]
            os.fsync(descriptor)
            return receipt
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_sync(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        descriptor = os.open(self._path, os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            return self._read_descriptor(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _read_descriptor(descriptor: int) -> list[dict[str, Any]]:
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65_536):
            chunks.append(chunk)
        data = b"".join(chunks)
        if data and not data.endswith(b"\n"):
            raise AuditChainMismatch("anchor ledger has a truncated final record")
        try:
            if any(not line for line in data.splitlines()):
                raise AuditChainMismatch("anchor ledger contains a blank record")
            return [json.loads(line) for line in data.splitlines()]
        except json.JSONDecodeError as exc:
            raise AuditChainMismatch("anchor ledger contains malformed JSON") from exc


def _build_receipt(
    head: AuditEventRecord,
    *,
    observed_at: str,
    key_id: str,
    previous_anchor_hash: str,
    private_key: Ed25519PrivateKey,
) -> AuditAnchorReceiptV1:
    anchor_seed = (
        f"{head.stream_id}\0{head.stream_seq}\0{head.event_hash}\0{observed_at}\0{key_id}"
    ).encode()
    body = AuditAnchorBodyV1(
        schema_version="audit-anchor.v1",
        anchor_id=f"anchor-{hashlib.sha256(anchor_seed).hexdigest()[:24]}",
        stream_id=unicodedata.normalize("NFC", head.stream_id),
        stream_seq=str(head.stream_seq),
        event_hash=head.event_hash,
        previous_anchor_hash=previous_anchor_hash,
        observed_at=observed_at,
        key_id=key_id,
    )
    body_bytes = _anchor_body_bytes(body)
    signature_bytes = private_key.sign(_signature_preimage(body_bytes))
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
    verify_anchor_receipt(receipt, private_key.public_key())
    return receipt


class AuditReleaseInterlock:
    """Persistent fail-closed publication gate shared across process restarts."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def blocked(self) -> bool:
        state = self._read_last()
        return state is None or state["state"] != "unlocked"

    def require_release_allowed(self) -> None:
        if self.blocked:
            raise ReleaseBlockedError("release blocked by audit checkpoint interlock")

    def block(self, reason_code: str) -> None:
        self._append({"schema_version": "audit-release.v1", "state": "blocked", "reason_code": reason_code})

    def unlock(self, anchor_hash: str) -> None:
        if not _SHA256.fullmatch(anchor_hash):
            raise ValueError("unlock requires a valid anchor hash")
        self._append({"schema_version": "audit-release.v1", "state": "unlocked", "anchor_hash": anchor_hash})

    def _append(self, row: Mapping[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(dict(row), sort_keys=True, separators=(",", ":")).encode() + b"\n"
        descriptor = os.open(self._path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            view = memoryview(encoded)
            while view:
                view = view[os.write(descriptor, view) :]
            os.fsync(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_last(self) -> dict[str, str] | None:
        if not self._path.exists():
            return None
        descriptor = os.open(self._path, os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 65_536):
                chunks.append(chunk)
            data = b"".join(chunks)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        if data and not data.endswith(b"\n"):
            raise ReleaseBlockedError("release interlock journal is truncated")
        rows = [json.loads(line) for line in data.splitlines()]
        return rows[-1] if rows else None


class AuditAnchorService:
    def __init__(
        self,
        *,
        key_id: str,
        private_key: Ed25519PrivateKey,
        ledger: DurableAnchorLedger,
        interlock: AuditReleaseInterlock | None = None,
    ) -> None:
        self._key_id = key_id
        self._private_key = private_key
        self._ledger = ledger
        self._interlock = interlock or AuditReleaseInterlock(
            ledger.path.with_suffix(".release.jsonl")
        )

    @property
    def release_blocked(self) -> bool:
        return self._interlock.blocked

    def require_release_allowed(self) -> None:
        self._interlock.require_release_allowed()

    async def anchor(
        self,
        events: tuple[AuditEventRecord, ...],
        *,
        observed_at: str,
    ) -> AuditAnchorReceiptV1:
        try:
            return await self._ledger.anchor_atomic(
                events,
                observed_at=observed_at,
                key_id=self._key_id,
                private_key=self._private_key,
            )
        except (AuditChainMismatch, OSError, ValueError):
            self._interlock.block("audit-chain-conflict")
            raise

    async def anchor_and_submit(
        self,
        events: tuple[AuditEventRecord, ...],
        *,
        observed_at: str,
        submit: Callable[[Mapping[str, Any]], Awaitable[dict[str, Any]]],
    ) -> AuditAnchorReceiptV1:
        receipt = await self.anchor(events, observed_at=observed_at)
        response = await submit(receipt.model_dump(mode="json"))
        if response.get("ok") is not True or response.get("status") not in {"created", "replay"}:
            self._interlock.block("audit-anchor-not-accepted")
            raise ReleaseBlockedError("audit anchor submission was not accepted")
        self._interlock.unlock(receipt.anchor_hash)
        return receipt
