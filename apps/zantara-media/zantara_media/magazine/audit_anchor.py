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
from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any, Literal

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_MILLISECOND_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_UNSIGNED_DECIMAL = re.compile(r"^(?:0|[1-9]\d*)$")
ZERO_HASH = "0" * 64


class AuditChainMismatch(RuntimeError):
    """The observed audit chain conflicts with canonical history."""


class ReleaseBlockedError(RuntimeError):
    """Publication promotion is fail-closed after an audit incident."""


class AuditAnchorRejectedError(RuntimeError):
    """Sites explicitly rejected a submitted anchor receipt."""


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
            raise ValueError(
                "observed_at must have exactly three fractional digits and Z"
            )
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


class ReleaseBinding(FrozenModel):
    """Exact canonical audit head and publication operation unlocked by a receipt."""

    stream_id: str
    stream_seq: int = Field(ge=1, le=9_007_199_254_740_991)
    event_hash: str
    packet_id: str
    operation_id: str

    @field_validator("event_hash")
    @classmethod
    def validate_event_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("release event_hash must be lowercase SHA-256")
        return value


class PendingAnchorRecordV1(FrozenModel):
    """Durable receipt state kept outside the canonical accepted ledger."""

    schema_version: Literal["audit-anchor-pending.v1"] = "audit-anchor-pending.v1"
    state: Literal["pending", "rejected", "accepted"]
    receipt: AuditAnchorReceiptV1
    release_binding: ReleaseBinding


class PreparedAnchor(FrozenModel):
    receipt: AuditAnchorReceiptV1
    release_binding: ReleaseBinding
    state: Literal["pending", "accepted"]


class PublicationOperationPayloadV1(FrozenModel):
    schema_version: Literal["publication-operation.v1"] = "publication-operation.v1"
    operation: Literal["edition.publish", "breaking.publish"]
    packet_id: str


class AuditFeedEventV1(FrozenModel):
    schema_version: Literal["audit-event.v1"] = "audit-event.v1"
    stream_id: str
    stream_seq: str
    previous_event_hash: str
    event_hash: str
    payload: PublicationOperationPayloadV1

    @field_validator("stream_seq")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        if not _UNSIGNED_DECIMAL.fullmatch(value) or value == "0":
            raise ValueError("feed stream_seq must be a positive decimal string")
        if int(value) > 9_007_199_254_740_991:
            raise ValueError("feed stream_seq exceeds safe integer range")
        return value

    @field_validator("previous_event_hash", "event_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("feed hashes must be lowercase SHA-256")
        return value

    def internal(self) -> AuditEventRecord:
        return AuditEventRecord(
            stream_id=self.stream_id,
            stream_seq=int(self.stream_seq),
            previous_event_hash=self.previous_event_hash,
            event_hash=self.event_hash,
            payload=self.payload.model_dump(mode="json"),
        )


class AuditFeedCheckpointV1(FrozenModel):
    stream_seq: str
    event_hash: str

    @field_validator("stream_seq")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        if not _UNSIGNED_DECIMAL.fullmatch(value):
            raise ValueError("feed checkpoint sequence must be unsigned decimal")
        if int(value) > 9_007_199_254_740_991:
            raise ValueError("feed checkpoint sequence exceeds safe integer range")
        return value

    @field_validator("event_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("feed checkpoint hash must be lowercase SHA-256")
        return value


class AuditFeedCursorV1(FrozenModel):
    after_seq: str
    checkpoint_hash: str

    @field_validator("after_seq")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        if not _UNSIGNED_DECIMAL.fullmatch(value):
            raise ValueError("feed cursor sequence must be unsigned decimal")
        if int(value) > 9_007_199_254_740_991:
            raise ValueError("feed cursor sequence exceeds safe integer range")
        return value

    @field_validator("checkpoint_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("feed cursor hash must be lowercase SHA-256")
        return value


class AuditPromotionTargetV1(FrozenModel):
    operation: Literal["edition.publish", "breaking.publish"]
    packet_id: str
    stream_seq: str
    event_hash: str

    @field_validator("stream_seq")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        if not _UNSIGNED_DECIMAL.fullmatch(value) or value == "0":
            raise ValueError("promotion target sequence must be positive decimal")
        return value

    @field_validator("event_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("promotion target hash must be lowercase SHA-256")
        return value


class AuditFeedPageV1(FrozenModel):
    schema_version: Literal["audit-feed.v1"] = "audit-feed.v1"
    stream_id: str
    checkpoint: AuditFeedCheckpointV1
    head: AuditFeedCheckpointV1
    events: tuple[AuditFeedEventV1, ...]
    promotion_target: AuditPromotionTargetV1 | None
    next_cursor: AuditFeedCursorV1
    has_more: bool


class VerifiedAuditFeedPage(FrozenModel):
    events: tuple[AuditEventRecord, ...]
    target_binding: ReleaseBinding | None
    next_sequence: int
    next_hash: str
    has_more: bool


def verify_audit_feed_page(
    page: AuditFeedPageV1,
    *,
    expected_stream_id: str,
    expected_sequence: int,
    expected_hash: str,
    expected_operation: Literal["edition.publish", "breaking.publish"],
    expected_packet_id: str,
) -> VerifiedAuditFeedPage:
    """Verify a closed canonical Sites page and bind its head to one promotion."""

    if page.stream_id != expected_stream_id:
        raise AuditChainMismatch("audit feed stream mismatch")
    if (
        page.checkpoint.stream_seq != str(expected_sequence)
        or page.checkpoint.event_hash != expected_hash
    ):
        raise AuditChainMismatch("audit feed checkpoint mismatch")
    events = tuple(item.internal() for item in page.events)
    if not events:
        raise AuditChainMismatch("audit feed page contains no promotion event")
    head = verify_audit_stream(
        events,
        expected_sequence=expected_sequence + 1,
        expected_previous_hash=expected_hash,
    )
    target = page.promotion_target
    matching: tuple[AuditEventRecord, ...] = ()
    if target is not None:
        if (
            target.operation != expected_operation
            or target.packet_id != expected_packet_id
        ):
            raise AuditChainMismatch("audit feed promotion target mismatch")
        matching = tuple(
            item
            for item in events
            if item.stream_seq == int(target.stream_seq)
            and item.event_hash == target.event_hash
            and item.payload.get("operation") == expected_operation
            and item.payload.get("packet_id") == expected_packet_id
        )
        if len(matching) != 1:
            raise AuditChainMismatch(
                "promotion target is absent from verified feed range"
            )
    if (
        page.next_cursor.after_seq != str(head.stream_seq)
        or page.next_cursor.checkpoint_hash != head.event_hash
    ):
        raise AuditChainMismatch("audit feed next cursor mismatch")
    if not page.has_more and (
        page.head.stream_seq != str(head.stream_seq)
        or page.head.event_hash != head.event_hash
    ):
        raise AuditChainMismatch("audit feed terminal head mismatch")
    if int(page.head.stream_seq) < head.stream_seq:
        raise AuditChainMismatch("audit feed head precedes verified range")
    target_event = matching[0] if matching else None
    return VerifiedAuditFeedPage(
        events=events,
        target_binding=(
            ReleaseBinding(
                stream_id=expected_stream_id,
                stream_seq=target_event.stream_seq,
                event_hash=target_event.event_hash,
                packet_id=expected_packet_id,
                operation_id=(
                    "/api/machine/publications/editions:"
                    if expected_operation == "edition.publish"
                    else "/api/machine/publications/breaking:"
                )
                + expected_packet_id,
            )
            if target_event is not None
            else None
        ),
        next_sequence=head.stream_seq,
        next_hash=head.event_hash,
        has_more=page.has_more,
    )


class ReleaseBlockedRecordV1(FrozenModel):
    schema_version: Literal["audit-release.v1"] = "audit-release.v1"
    state: Literal["blocked"] = "blocked"
    reason_code: str


class ReleaseUnlockedRecordV1(FrozenModel):
    schema_version: Literal["audit-release.v1"] = "audit-release.v1"
    state: Literal["unlocked"] = "unlocked"
    stream_id: str
    stream_seq: str
    event_hash: str
    packet_id: str
    operation_id: str
    receipt_hash: str

    @field_validator("stream_seq")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        if not _UNSIGNED_DECIMAL.fullmatch(value) or value == "0":
            raise ValueError("release stream_seq must be a positive decimal string")
        return value

    @field_validator("event_hash", "receipt_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("release hashes must be lowercase SHA-256")
        return value


ReleaseRecordV1 = ReleaseBlockedRecordV1 | ReleaseUnlockedRecordV1


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
    """Accepted receipts plus a separate durable pre-submission journal."""

    def __init__(self, path: Path, *, pending_path: Path | None = None) -> None:
        self._path = path
        self._pending_path = pending_path or path.with_suffix(".pending.jsonl")
        self._lock = asyncio.Lock()
        self._stream_locks: dict[str, asyncio.Lock] = {}

    @property
    def path(self) -> Path:
        return self._path

    @property
    def pending_path(self) -> Path:
        return self._pending_path

    @asynccontextmanager
    async def claim_stream(self, stream_id: str) -> AsyncIterator[None]:
        """Serialize prepare, submit, and commit across processes per stream."""

        normalized = unicodedata.normalize("NFC", stream_id)
        if not normalized:
            raise ValueError("audit stream id must not be empty")
        local = self._stream_locks.setdefault(normalized, asyncio.Lock())
        async with local:
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            lock_path = (
                self._path.parent / f"{self._path.name}.streams" / f"{digest}.lock"
            )
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                await asyncio.to_thread(fcntl.flock, descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    async def read_all(
        self, public_key: Ed25519PublicKey | None = None
    ) -> tuple[AuditAnchorReceiptV1, ...]:
        async with self._lock:
            raw = await asyncio.to_thread(self._read_sync)
        receipts = tuple(AuditAnchorReceiptV1.model_validate(item) for item in raw)
        self._verify_history(receipts, public_key)
        return receipts

    async def prepare_pending(
        self,
        events: tuple[AuditEventRecord, ...],
        *,
        observed_at: str,
        key_id: str,
        private_key: Ed25519PrivateKey,
        release_binding: ReleaseBinding,
    ) -> PreparedAnchor:
        """Create or resume one fsynced pending receipt without advancing accepted."""

        async with self._lock:
            return await asyncio.to_thread(
                self._prepare_pending_sync,
                events,
                observed_at,
                key_id,
                private_key,
                release_binding,
            )

    async def accept_pending(
        self,
        prepared: PreparedAnchor,
        public_key: Ed25519PublicKey,
    ) -> Literal["created", "replay"]:
        async with self._lock:
            return await asyncio.to_thread(
                self._accept_pending_sync, prepared, public_key
            )

    async def reject_pending(
        self,
        prepared: PreparedAnchor,
        public_key: Ed25519PublicKey,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(self._reject_pending_sync, prepared, public_key)

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

    def _prepare_pending_sync(
        self,
        events: tuple[AuditEventRecord, ...],
        observed_at: str,
        key_id: str,
        private_key: Ed25519PrivateKey,
        release_binding: ReleaseBinding,
    ) -> PreparedAnchor:
        if not events:
            raise AuditChainMismatch("audit stream is empty")
        stream_id = events[0].stream_id
        if release_binding.stream_id != stream_id:
            raise ReleaseBlockedError(
                "release binding stream does not match audit events"
            )
        accepted_descriptor, pending_descriptor = self._open_locked_ledgers()
        try:
            raw = self._read_descriptor(accepted_descriptor)
            receipts = tuple(AuditAnchorReceiptV1.model_validate(item) for item in raw)
            self._verify_history(receipts, private_key.public_key())
            stream_receipts = tuple(
                item for item in receipts if item.body.stream_id == stream_id
            )
            previous_receipt = stream_receipts[-1] if stream_receipts else None
            pending_rows = self._read_pending_descriptor(pending_descriptor)
            active = self._verify_pending_history(
                pending_rows, private_key.public_key()
            ).get(stream_id)
            terminal_hashes = {
                row.receipt.anchor_hash
                for row in pending_rows
                if row.state in {"accepted", "rejected"}
            }

            head, accepted_replay = self._verify_events_against_accepted(
                events, previous_receipt
            )
            if active is not None:
                if active.release_binding != release_binding:
                    raise AuditChainMismatch(
                        "unresolved pending anchor has a different release binding"
                    )
                if (
                    active.receipt.body.stream_seq != str(head.stream_seq)
                    or active.receipt.body.event_hash != head.event_hash
                ):
                    raise AuditChainMismatch(
                        "unresolved pending anchor conflicts with audit events"
                    )
                if active.receipt in receipts:
                    self._append_pending_row(
                        pending_descriptor,
                        active.model_copy(update={"state": "accepted"}),
                    )
                    return PreparedAnchor(
                        receipt=active.receipt,
                        release_binding=release_binding,
                        state="accepted",
                    )
                return PreparedAnchor(
                    receipt=active.receipt,
                    release_binding=release_binding,
                    state="pending",
                )

            if accepted_replay:
                assert previous_receipt is not None
                self._validate_receipt_binding(previous_receipt, release_binding)
                accepted_terminal = next(
                    (
                        row
                        for row in reversed(pending_rows)
                        if row.state == "accepted"
                        and row.receipt.anchor_hash == previous_receipt.anchor_hash
                    ),
                    None,
                )
                if (
                    accepted_terminal is None
                    or accepted_terminal.release_binding != release_binding
                ):
                    raise AuditChainMismatch("accepted anchor release binding mismatch")
                return PreparedAnchor(
                    receipt=previous_receipt,
                    release_binding=release_binding,
                    state="accepted",
                )

            previous_anchor_hash = (
                previous_receipt.anchor_hash
                if previous_receipt is not None
                else ZERO_HASH
            )
            receipt = _build_receipt(
                head,
                observed_at=observed_at,
                key_id=key_id,
                previous_anchor_hash=previous_anchor_hash,
                private_key=private_key,
            )
            if receipt.anchor_hash in terminal_hashes:
                raise AuditChainMismatch("terminal pending receipt cannot be reopened")
            self._validate_receipt_binding(receipt, release_binding)
            pending = PendingAnchorRecordV1(
                state="pending",
                receipt=receipt,
                release_binding=release_binding,
            )
            self._append_pending_row(pending_descriptor, pending)
            return PreparedAnchor(
                receipt=receipt,
                release_binding=release_binding,
                state="pending",
            )
        finally:
            self._close_locked_ledgers(accepted_descriptor, pending_descriptor)

    @staticmethod
    def _verify_events_against_accepted(
        events: tuple[AuditEventRecord, ...],
        previous_receipt: AuditAnchorReceiptV1 | None,
    ) -> tuple[AuditEventRecord, bool]:
        if previous_receipt is not None:
            previous_sequence = int(previous_receipt.body.stream_seq)
            if events and events[-1].stream_seq == previous_sequence:
                if len(events) != 1:
                    raise AuditChainMismatch("checkpoint replay must contain one event")
                replay = events[0]
                if replay.stream_id != previous_receipt.body.stream_id:
                    raise AuditChainMismatch("checkpoint replay stream mismatch")
                if replay.stream_seq != previous_sequence:
                    raise AuditChainMismatch("checkpoint replay sequence mismatch")
                if replay.stream_seq == 1 and replay.previous_event_hash != ZERO_HASH:
                    raise AuditChainMismatch("genesis replay previous hash mismatch")
                expected_hash = build_audit_event_hash(
                    replay.stream_id,
                    replay.stream_seq,
                    replay.previous_event_hash,
                    replay.payload,
                )
                if replay.event_hash != expected_hash:
                    raise AuditChainMismatch("audit stream event hash mismatch")
                if replay.event_hash != previous_receipt.body.event_hash:
                    raise AuditChainMismatch(
                        "checkpoint conflicts with prior Pro anchor"
                    )
                return replay, True
            head = verify_audit_stream(
                events,
                expected_sequence=previous_sequence + 1,
                expected_previous_hash=previous_receipt.body.event_hash,
            )
            return head, False
        return verify_audit_stream(events), False

    def _accept_pending_sync(
        self,
        prepared: PreparedAnchor,
        public_key: Ed25519PublicKey,
    ) -> Literal["created", "replay"]:
        accepted_descriptor, pending_descriptor = self._open_locked_ledgers()
        try:
            receipts = tuple(
                AuditAnchorReceiptV1.model_validate(item)
                for item in self._read_descriptor(accepted_descriptor)
            )
            self._verify_history(receipts, public_key)
            pending_rows = self._read_pending_descriptor(pending_descriptor)
            active = self._verify_pending_history(pending_rows, public_key).get(
                prepared.receipt.body.stream_id
            )
            matches = tuple(
                item
                for item in receipts
                if item.anchor_hash == prepared.receipt.anchor_hash
            )
            if matches:
                if matches != (prepared.receipt,):
                    raise AuditChainMismatch("accepted anchor identity conflict")
                if active is not None:
                    self._require_active_pending(active, prepared)
                    self._append_pending_row(
                        pending_descriptor,
                        active.model_copy(update={"state": "accepted"}),
                    )
                return "replay"
            if active is None:
                raise AuditChainMismatch("pending anchor is absent")
            self._require_active_pending(active, prepared)
            stream_receipts = tuple(
                item
                for item in receipts
                if item.body.stream_id == prepared.receipt.body.stream_id
            )
            prior = stream_receipts[-1] if stream_receipts else None
            if prepared.receipt.body.previous_anchor_hash != (
                prior.anchor_hash if prior is not None else ZERO_HASH
            ):
                raise AuditChainMismatch("pending anchor previous hash conflict")
            expected_sequence = (
                int(prior.body.stream_seq) + 1 if prior is not None else 1
            )
            if int(prepared.receipt.body.stream_seq) != expected_sequence:
                raise AuditChainMismatch("pending anchor sequence conflict")
            self._append_accepted_receipt(accepted_descriptor, prepared.receipt)
            self._append_pending_row(
                pending_descriptor,
                active.model_copy(update={"state": "accepted"}),
            )
            return "created"
        finally:
            self._close_locked_ledgers(accepted_descriptor, pending_descriptor)

    def _reject_pending_sync(
        self,
        prepared: PreparedAnchor,
        public_key: Ed25519PublicKey,
    ) -> None:
        accepted_descriptor, pending_descriptor = self._open_locked_ledgers()
        try:
            receipts = tuple(
                AuditAnchorReceiptV1.model_validate(item)
                for item in self._read_descriptor(accepted_descriptor)
            )
            self._verify_history(receipts, public_key)
            active = self._verify_pending_history(
                self._read_pending_descriptor(pending_descriptor), public_key
            ).get(prepared.receipt.body.stream_id)
            if active is None:
                if prepared.receipt in receipts:
                    raise AuditChainMismatch("accepted anchor cannot be rejected")
                return
            self._require_active_pending(active, prepared)
            self._append_pending_row(
                pending_descriptor,
                active.model_copy(update={"state": "rejected"}),
            )
        finally:
            self._close_locked_ledgers(accepted_descriptor, pending_descriptor)

    def _open_locked_ledgers(self) -> tuple[int, int]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._pending_path.parent.mkdir(parents=True, exist_ok=True)
        accepted: int | None = None
        pending: int | None = None
        accepted_locked = False
        pending_locked = False
        try:
            accepted = os.open(self._path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
            pending = os.open(
                self._pending_path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600
            )
            fcntl.flock(accepted, fcntl.LOCK_EX)
            accepted_locked = True
            fcntl.flock(pending, fcntl.LOCK_EX)
            pending_locked = True
            return accepted, pending
        except BaseException:
            if pending is not None:
                if pending_locked:
                    fcntl.flock(pending, fcntl.LOCK_UN)
                os.close(pending)
            if accepted is not None:
                if accepted_locked:
                    fcntl.flock(accepted, fcntl.LOCK_UN)
                os.close(accepted)
            raise

    @staticmethod
    def _close_locked_ledgers(accepted: int, pending: int) -> None:
        fcntl.flock(pending, fcntl.LOCK_UN)
        fcntl.flock(accepted, fcntl.LOCK_UN)
        os.close(pending)
        os.close(accepted)

    @staticmethod
    def _validate_receipt_binding(
        receipt: AuditAnchorReceiptV1, binding: ReleaseBinding
    ) -> None:
        if (
            receipt.body.stream_id != binding.stream_id
            or receipt.body.stream_seq != str(binding.stream_seq)
            or receipt.body.event_hash != binding.event_hash
        ):
            raise ReleaseBlockedError("anchor receipt does not match release binding")

    @staticmethod
    def _require_active_pending(
        active: PendingAnchorRecordV1, prepared: PreparedAnchor
    ) -> None:
        if (
            active.receipt != prepared.receipt
            or active.release_binding != prepared.release_binding
        ):
            raise AuditChainMismatch("pending anchor identity conflict")

    @staticmethod
    def _append_accepted_receipt(
        descriptor: int, receipt: AuditAnchorReceiptV1
    ) -> None:
        row = (
            json.dumps(
                receipt.model_dump(mode="json"),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        DurableAnchorLedger._append_row(descriptor, row)

    @staticmethod
    def _append_pending_row(descriptor: int, record: PendingAnchorRecordV1) -> None:
        row = (
            json.dumps(
                record.model_dump(mode="json"),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        DurableAnchorLedger._append_row(descriptor, row)

    @staticmethod
    def _append_row(descriptor: int, row: bytes) -> None:
        os.lseek(descriptor, 0, os.SEEK_END)
        view = memoryview(row)
        while view:
            view = view[os.write(descriptor, view) :]
        os.fsync(descriptor)

    @staticmethod
    def _verify_pending_history(
        rows: tuple[PendingAnchorRecordV1, ...],
        public_key: Ed25519PublicKey,
    ) -> dict[str, PendingAnchorRecordV1]:
        active: dict[str, PendingAnchorRecordV1] = {}
        terminal_hashes: set[str] = set()
        for row in rows:
            verify_anchor_receipt(row.receipt, public_key)
            DurableAnchorLedger._validate_receipt_binding(
                row.receipt, row.release_binding
            )
            stream_id = row.receipt.body.stream_id
            previous = active.get(stream_id)
            if row.state == "pending":
                if row.receipt.anchor_hash in terminal_hashes:
                    raise AuditChainMismatch("terminal pending receipt was reopened")
                if previous is not None:
                    raise AuditChainMismatch("pending anchor history overlaps")
                active[stream_id] = row
                continue
            if previous is None:
                raise AuditChainMismatch("pending anchor terminal state has no origin")
            if (
                previous.receipt != row.receipt
                or previous.release_binding != row.release_binding
            ):
                raise AuditChainMismatch("pending anchor terminal identity conflict")
            terminal_hashes.add(row.receipt.anchor_hash)
            del active[stream_id]
        return active

    @staticmethod
    def _read_pending_descriptor(
        descriptor: int,
    ) -> tuple[PendingAnchorRecordV1, ...]:
        return tuple(
            PendingAnchorRecordV1.model_validate(item)
            for item in DurableAnchorLedger._read_descriptor(descriptor)
        )

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

    def __init__(
        self,
        path: Path,
        *,
        ledger: DurableAnchorLedger | None = None,
        public_key: Ed25519PublicKey | None = None,
    ) -> None:
        self._path = path
        self._ledger = ledger
        self._public_key = public_key

    @property
    def blocked(self) -> bool:
        state = self._read_last()
        if not isinstance(state, ReleaseUnlockedRecordV1):
            return True
        try:
            self._verify_unlock(state)
        except ReleaseBlockedError:
            return True
        return False

    def require_release_allowed(self, binding: ReleaseBinding) -> None:
        state = self._read_last()
        if not isinstance(state, ReleaseUnlockedRecordV1):
            raise ReleaseBlockedError("release blocked by audit checkpoint interlock")
        expected = {
            "stream_id": binding.stream_id,
            "stream_seq": str(binding.stream_seq),
            "event_hash": binding.event_hash,
            "packet_id": binding.packet_id,
            "operation_id": binding.operation_id,
        }
        actual = state.model_dump(mode="json", include=set(expected))
        if actual != expected:
            raise ReleaseBlockedError(
                "release unlock does not match publication target"
            )
        self._verify_unlock(state)

    def block(self, reason_code: str) -> None:
        self._append(
            ReleaseBlockedRecordV1(reason_code=reason_code).model_dump(mode="json")
        )

    def unlock(self, binding: ReleaseBinding, receipt_hash: str) -> None:
        row = ReleaseUnlockedRecordV1(
            stream_id=binding.stream_id,
            stream_seq=str(binding.stream_seq),
            event_hash=binding.event_hash,
            packet_id=binding.packet_id,
            operation_id=binding.operation_id,
            receipt_hash=receipt_hash,
        )
        self._verify_unlock(row)
        self._append(row.model_dump(mode="json"))

    def _append(self, row: Mapping[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (
            json.dumps(dict(row), sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
        )
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

    def _read_last(self) -> ReleaseRecordV1 | None:
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
        if any(not line for line in data.splitlines()):
            raise ReleaseBlockedError(
                "release interlock journal contains a blank record"
            )
        try:
            parsed = [json.loads(line) for line in data.splitlines()]
            rows: list[ReleaseRecordV1] = []
            for item in parsed:
                if not isinstance(item, dict):
                    raise ReleaseBlockedError("release interlock record is invalid")
                if item.get("state") == "blocked":
                    rows.append(ReleaseBlockedRecordV1.model_validate(item))
                elif item.get("state") == "unlocked":
                    rows.append(ReleaseUnlockedRecordV1.model_validate(item))
                else:
                    raise ReleaseBlockedError("release interlock record is invalid")
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
            raise ReleaseBlockedError("release interlock record is invalid") from exc
        return rows[-1] if rows else None

    def _verify_unlock(self, row: ReleaseUnlockedRecordV1) -> None:
        if self._ledger is None or self._public_key is None:
            raise ReleaseBlockedError("release unlock has no trusted anchor ledger")
        try:
            raw = self._ledger._read_sync()
            receipts = tuple(AuditAnchorReceiptV1.model_validate(item) for item in raw)
            self._ledger._verify_history(receipts, self._public_key)
        except (AuditChainMismatch, ValidationError, OSError, ValueError) as exc:
            raise ReleaseBlockedError(
                "trusted anchor ledger validation failed"
            ) from exc
        matches = [item for item in receipts if item.anchor_hash == row.receipt_hash]
        if len(matches) != 1:
            raise ReleaseBlockedError(
                "release receipt hash is absent from anchor ledger"
            )
        receipt = matches[0]
        if (
            receipt.body.stream_id != row.stream_id
            or receipt.body.stream_seq != row.stream_seq
            or receipt.body.event_hash != row.event_hash
        ):
            raise ReleaseBlockedError("release unlock conflicts with anchor receipt")


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
            ledger.path.with_suffix(".release.jsonl"),
            ledger=ledger,
            public_key=private_key.public_key(),
        )

    @property
    def release_blocked(self) -> bool:
        return self._interlock.blocked

    def require_release_allowed(self, binding: ReleaseBinding) -> None:
        self._interlock.require_release_allowed(binding)

    async def anchor_and_submit(
        self,
        events: tuple[AuditEventRecord, ...],
        *,
        observed_at: str,
        submit: Callable[[Mapping[str, Any]], Awaitable[dict[str, Any]]],
        release_binding: ReleaseBinding,
    ) -> AuditAnchorReceiptV1:
        if not events:
            self._interlock.block("audit-anchor-attempt-failed")
            raise AuditChainMismatch("audit stream is empty")
        async with self._ledger.claim_stream(events[0].stream_id):
            self._interlock.block("audit-anchor-attempt")
            try:
                prepared = await self._ledger.prepare_pending(
                    events,
                    observed_at=observed_at,
                    key_id=self._key_id,
                    private_key=self._private_key,
                    release_binding=release_binding,
                )
                receipt = prepared.receipt
                if prepared.state == "accepted":
                    self._interlock.unlock(release_binding, receipt.anchor_hash)
                    return receipt
                try:
                    response = await submit(receipt.model_dump(mode="json"))
                except AuditAnchorRejectedError:
                    await self._ledger.reject_pending(
                        prepared, self._private_key.public_key()
                    )
                    raise
                if response not in (
                    {"ok": True, "status": "created"},
                    {"ok": True, "status": "replay"},
                ):
                    await self._ledger.reject_pending(
                        prepared, self._private_key.public_key()
                    )
                    raise ReleaseBlockedError(
                        "audit anchor submission was not accepted"
                    )
                await self._ledger.accept_pending(
                    prepared, self._private_key.public_key()
                )
                self._interlock.unlock(release_binding, receipt.anchor_hash)
                return receipt
            except BaseException:
                self._interlock.block("audit-anchor-attempt-failed")
                raise
