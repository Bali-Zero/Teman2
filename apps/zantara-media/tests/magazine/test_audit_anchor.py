from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from zantara_media.magazine.audit_anchor import (
    AuditAnchorService,
    AuditChainMismatch,
    AuditEventRecord,
    AuditReleaseInterlock,
    DurableAnchorLedger,
    ReleaseBlockedError,
    build_audit_event_hash,
    verify_anchor_receipt,
    verify_audit_stream,
)


ZERO_HASH = "0" * 64


def event(sequence: int, previous: str, payload: dict[str, object]) -> AuditEventRecord:
    event_hash = build_audit_event_hash("publication:main", sequence, previous, payload)
    return AuditEventRecord(
        stream_id="publication:main",
        stream_seq=sequence,
        previous_event_hash=previous,
        event_hash=event_hash,
        payload=payload,
    )


def test_audit_event_hash_matches_byte_exact_spec() -> None:
    payload = {"z": 1, "a": "é"}
    actual = build_audit_event_hash("publication:e\u0301", 1, ZERO_HASH, payload)
    stream = "publication:é".encode()
    body = rfc8785.dumps(payload)
    preimage = b"".join(
        [
            b"BZM-AUDIT-EVENT-V1\0",
            len(stream).to_bytes(4, "big"),
            stream,
            (1).to_bytes(8, "big"),
            bytes(32),
            len(body).to_bytes(8, "big"),
            body,
        ]
    )
    assert actual == hashlib.sha256(preimage).hexdigest()


def test_stream_verification_rejects_gap_or_rewrite() -> None:
    first = event(1, ZERO_HASH, {"event": "published"})
    second = event(2, first.event_hash, {"event": "anchored"})
    assert verify_audit_stream((first, second)).event_hash == second.event_hash
    with pytest.raises(AuditChainMismatch):
        verify_audit_stream((first, second.model_copy(update={"stream_seq": 3})))
    with pytest.raises(AuditChainMismatch):
        verify_audit_stream((first, second.model_copy(update={"event_hash": "f" * 64})))


@pytest.mark.asyncio
async def test_anchor_receipt_is_byte_exact_ed25519_and_ledger_is_append_only(
    tmp_path: Path,
) -> None:
    key = Ed25519PrivateKey.generate()
    ledger = DurableAnchorLedger(tmp_path / "anchors.jsonl")
    service = AuditAnchorService(key_id="pro-anchor-1", private_key=key, ledger=ledger)
    first = event(1, ZERO_HASH, {"event": "published"})
    receipt = await service.anchor((first,), observed_at="2026-07-19T00:00:00.000Z")
    verify_anchor_receipt(receipt, key.public_key())
    assert "=" not in receipt.signature
    signature = base64.urlsafe_b64decode(receipt.signature + "==")
    body = rfc8785.dumps(receipt.body.model_dump(mode="json"))
    expected_hash = hashlib.sha256(
        b"BZM-AUDIT-ANCHOR-RECORD-V1\0"
        + len(body).to_bytes(8, "big")
        + body
        + signature
    ).hexdigest()
    assert receipt.anchor_hash == expected_hash
    rows = await ledger.read_all()
    assert rows == (receipt,)
    assert (tmp_path / "anchors.jsonl").read_bytes().endswith(b"\n")


@pytest.mark.asyncio
async def test_checkpoint_conflict_blocks_later_release(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    service = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(tmp_path / "anchors.jsonl"),
    )
    first = event(1, ZERO_HASH, {"event": "published"})
    await service.anchor((first,), observed_at="2026-07-19T00:00:00.000Z")
    rewritten = first.model_copy(update={"event_hash": "f" * 64})
    with pytest.raises(AuditChainMismatch):
        await service.anchor((rewritten,), observed_at="2026-07-19T00:01:00.000Z")
    assert service.release_blocked is True
    with pytest.raises(ReleaseBlockedError):
        service.require_release_allowed()

    restarted = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(tmp_path / "anchors.jsonl"),
    )
    with pytest.raises(ReleaseBlockedError):
        restarted.require_release_allowed()


@pytest.mark.asyncio
async def test_release_unlocks_only_after_anchor_submission_acceptance(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    interlock = AuditReleaseInterlock(tmp_path / "release.jsonl")
    service = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(tmp_path / "anchors.jsonl"),
        interlock=interlock,
    )
    first = event(1, ZERO_HASH, {"event": "publication-ready"})

    async def reject(_: dict[str, object]) -> dict[str, object]:
        return {"ok": False, "status": "rejected"}

    with pytest.raises(ReleaseBlockedError):
        await service.anchor_and_submit(
            (first,), observed_at="2026-07-19T00:00:00.000Z", submit=reject
        )
    with pytest.raises(ReleaseBlockedError):
        AuditReleaseInterlock(tmp_path / "release.jsonl").require_release_allowed()

    async def accept(_: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "status": "replay"}

    await service.anchor_and_submit(
        (first,), observed_at="2026-07-19T00:00:00.000Z", submit=accept
    )
    AuditReleaseInterlock(tmp_path / "release.jsonl").require_release_allowed()
