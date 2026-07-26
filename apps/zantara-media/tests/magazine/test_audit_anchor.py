from __future__ import annotations

import asyncio
import base64
import hashlib
from pathlib import Path

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from zantara_media.magazine.audit_anchor import (
    AuditAnchorReceiptV1,
    AuditAnchorService,
    AuditChainMismatch,
    AuditEventRecord,
    AuditReleaseInterlock,
    AuditFeedPageV1,
    DurableAnchorLedger,
    ReleaseBinding,
    ReleaseBlockedError,
    build_audit_event_hash,
    verify_anchor_receipt,
    verify_audit_stream,
    verify_audit_feed_page,
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


def binding(first: AuditEventRecord, packet_id: str = "edition-1") -> ReleaseBinding:
    return ReleaseBinding(
        stream_id=first.stream_id,
        stream_seq=first.stream_seq,
        event_hash=first.event_hash,
        packet_id=packet_id,
        operation_id=f"/api/machine/publications/editions:{packet_id}",
    )


async def accept_anchor(
    service: AuditAnchorService,
    events: tuple[AuditEventRecord, ...],
    *,
    observed_at: str,
    release_binding: ReleaseBinding,
) -> AuditAnchorReceiptV1:
    async def accept(_: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "status": "created"}

    return await service.anchor_and_submit(
        events,
        observed_at=observed_at,
        submit=accept,
        release_binding=release_binding,
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
    receipt = await accept_anchor(
        service,
        (first,),
        observed_at="2026-07-19T00:00:00.000Z",
        release_binding=binding(first),
    )
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
async def test_same_sequence_replay_verifies_complete_event(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    ledger = DurableAnchorLedger(tmp_path / "anchors.jsonl")
    service = AuditAnchorService(key_id="pro-anchor-1", private_key=key, ledger=ledger)
    first = event(1, ZERO_HASH, {"event": "publication-ready"})
    await accept_anchor(
        service,
        (first,),
        observed_at="2026-07-19T00:00:00.000Z",
        release_binding=binding(first),
    )

    tampered = first.model_copy(update={"payload": {"event": "forged"}})
    with pytest.raises(AuditChainMismatch, match="event hash mismatch"):
        await accept_anchor(
            service,
            (tampered,),
            observed_at="2026-07-19T00:00:01.000Z",
            release_binding=binding(tampered),
        )


@pytest.mark.asyncio
async def test_checkpoint_conflict_blocks_later_release(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    service = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(tmp_path / "anchors.jsonl"),
    )
    first = event(1, ZERO_HASH, {"event": "published"})
    await accept_anchor(
        service,
        (first,),
        observed_at="2026-07-19T00:00:00.000Z",
        release_binding=binding(first),
    )
    rewritten = first.model_copy(update={"event_hash": "f" * 64})
    with pytest.raises(AuditChainMismatch):
        await accept_anchor(
            service,
            (rewritten,),
            observed_at="2026-07-19T00:01:00.000Z",
            release_binding=binding(rewritten),
        )
    assert service.release_blocked is True

    restarted = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(tmp_path / "anchors.jsonl"),
    )
    assert restarted.release_blocked is True


@pytest.mark.asyncio
async def test_release_unlocks_only_after_anchor_submission_acceptance(
    tmp_path: Path,
) -> None:
    key = Ed25519PrivateKey.generate()
    ledger = DurableAnchorLedger(tmp_path / "anchors.jsonl")
    interlock = AuditReleaseInterlock(
        tmp_path / "release.jsonl", ledger=ledger, public_key=key.public_key()
    )
    service = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=ledger,
        interlock=interlock,
    )
    first = event(1, ZERO_HASH, {"event": "publication-ready"})
    target = binding(first)

    async def reject(_: dict[str, object]) -> dict[str, object]:
        return {"ok": False, "status": "rejected"}

    with pytest.raises(ReleaseBlockedError):
        await service.anchor_and_submit(
            (first,),
            observed_at="2026-07-19T00:00:00.000Z",
            submit=reject,
            release_binding=target,
        )
    with pytest.raises(ReleaseBlockedError):
        interlock.require_release_allowed(target)
    assert await ledger.read_all(key.public_key()) == ()

    calls = 0

    async def must_not_reopen(_: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"ok": True, "status": "created"}

    with pytest.raises(AuditChainMismatch, match="terminal pending receipt"):
        await service.anchor_and_submit(
            (first,),
            observed_at="2026-07-19T00:00:00.000Z",
            submit=must_not_reopen,
            release_binding=target,
        )
    assert calls == 0

    async def accept_with_extra(_: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "status": "replay", "unexpected": True}

    with pytest.raises(ReleaseBlockedError):
        await service.anchor_and_submit(
            (first,),
            observed_at="2026-07-19T00:00:00.001Z",
            submit=accept_with_extra,
            release_binding=target,
        )

    async def accept(_: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "status": "replay"}

    await service.anchor_and_submit(
        (first,),
        observed_at="2026-07-19T00:00:00.002Z",
        submit=accept,
        release_binding=target,
    )
    interlock.require_release_allowed(target)


@pytest.mark.asyncio
async def test_rejected_later_anchor_does_not_advance_before_earlier_acceptance(
    tmp_path: Path,
) -> None:
    key = Ed25519PrivateKey.generate()
    ledger = DurableAnchorLedger(tmp_path / "anchors.jsonl")
    service = AuditAnchorService(key_id="pro-anchor-1", private_key=key, ledger=ledger)
    first = event(1, ZERO_HASH, {"event": "edition-a"})
    second = event(2, first.event_hash, {"event": "edition-b"})

    async def reject(_: dict[str, object]) -> dict[str, object]:
        return {"ok": False, "status": "rejected"}

    with pytest.raises(ReleaseBlockedError, match="not accepted"):
        await service.anchor_and_submit(
            (first, second),
            observed_at="2026-07-19T00:00:01.000Z",
            submit=reject,
            release_binding=binding(second, "edition-b"),
        )
    assert await ledger.read_all(key.public_key()) == ()

    async def accept(_: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "status": "created"}

    receipt = await service.anchor_and_submit(
        (first,),
        observed_at="2026-07-19T00:00:00.000Z",
        submit=accept,
        release_binding=binding(first, "edition-a"),
    )
    assert await ledger.read_all(key.public_key()) == (receipt,)


@pytest.mark.asyncio
async def test_created_response_cannot_promote_a_sequence_gap(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    ledger = DurableAnchorLedger(tmp_path / "anchors.jsonl")
    service = AuditAnchorService(key_id="pro-anchor-1", private_key=key, ledger=ledger)
    first = event(1, ZERO_HASH, {"event": "edition-a"})
    second = event(2, first.event_hash, {"event": "edition-b"})

    async def anomalous_created(_: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "status": "created"}

    with pytest.raises(AuditChainMismatch, match="sequence conflict"):
        await service.anchor_and_submit(
            (first, second),
            observed_at="2026-07-19T00:00:01.000Z",
            submit=anomalous_created,
            release_binding=binding(second, "edition-b"),
        )
    assert await ledger.read_all(key.public_key()) == ()


@pytest.mark.asyncio
async def test_unknown_submission_restarts_with_identical_pending_receipt(
    tmp_path: Path,
) -> None:
    key = Ed25519PrivateKey.generate()
    ledger_path = tmp_path / "anchors.jsonl"
    first = event(1, ZERO_HASH, {"event": "edition-a"})
    target = binding(first, "edition-a")
    submitted: list[dict[str, object]] = []

    async def lose_response(packet: dict[str, object]) -> dict[str, object]:
        submitted.append(packet)
        raise RuntimeError("response lost")

    first_service = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(ledger_path),
    )
    with pytest.raises(RuntimeError, match="response lost"):
        await first_service.anchor_and_submit(
            (first,),
            observed_at="2026-07-19T00:00:00.000Z",
            submit=lose_response,
            release_binding=target,
        )
    assert await DurableAnchorLedger(ledger_path).read_all(key.public_key()) == ()

    async def replay(packet: dict[str, object]) -> dict[str, object]:
        submitted.append(packet)
        return {"ok": True, "status": "replay"}

    restarted = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(ledger_path),
    )
    receipt = await restarted.anchor_and_submit(
        (first,),
        observed_at="2026-07-19T00:01:00.000Z",
        submit=replay,
        release_binding=target,
    )
    assert submitted == [receipt.model_dump(mode="json")] * 2
    assert await DurableAnchorLedger(ledger_path).read_all(key.public_key()) == (
        receipt,
    )

    calls = 0

    async def must_not_resubmit(_: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"ok": True, "status": "replay"}

    duplicate = await restarted.anchor_and_submit(
        (first,),
        observed_at="2026-07-19T00:02:00.000Z",
        submit=must_not_resubmit,
        release_binding=target,
    )
    assert duplicate == receipt
    assert calls == 0
    assert await DurableAnchorLedger(ledger_path).read_all(key.public_key()) == (
        receipt,
    )

    with pytest.raises(AuditChainMismatch, match="release binding mismatch"):
        await restarted.anchor_and_submit(
            (first,),
            observed_at="2026-07-19T00:03:00.000Z",
            submit=must_not_resubmit,
            release_binding=binding(first, "edition-forged"),
        )
    assert calls == 0


@pytest.mark.asyncio
async def test_filesystem_stream_lock_serializes_independent_services(
    tmp_path: Path,
) -> None:
    key = Ed25519PrivateKey.generate()
    ledger_path = tmp_path / "anchors.jsonl"
    first_event = event(1, ZERO_HASH, {"event": "edition-a"})
    target = binding(first_event, "edition-a")
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    second_submits = 0

    async def hold_first(_: dict[str, object]) -> dict[str, object]:
        first_entered.set()
        await release_first.wait()
        return {"ok": True, "status": "created"}

    async def must_not_submit(_: dict[str, object]) -> dict[str, object]:
        nonlocal second_submits
        second_submits += 1
        return {"ok": True, "status": "replay"}

    first_service = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(ledger_path),
    )
    second_service = AuditAnchorService(
        key_id="pro-anchor-1",
        private_key=key,
        ledger=DurableAnchorLedger(ledger_path),
    )
    first_task = asyncio.create_task(
        first_service.anchor_and_submit(
            (first_event,),
            observed_at="2026-07-19T00:00:00.000Z",
            submit=hold_first,
            release_binding=target,
        )
    )
    await first_entered.wait()
    second_task = asyncio.create_task(
        second_service.anchor_and_submit(
            (first_event,),
            observed_at="2026-07-19T00:00:01.000Z",
            submit=must_not_submit,
            release_binding=target,
        )
    )
    await asyncio.sleep(0.01)
    assert second_task.done() is False
    assert second_submits == 0

    release_first.set()
    first_receipt, second_receipt = await asyncio.gather(first_task, second_task)
    assert second_receipt == first_receipt
    assert second_submits == 0


@pytest.mark.asyncio
async def test_submit_exception_reblocks_previous_unlock_and_binds_target(
    tmp_path: Path,
) -> None:
    key = Ed25519PrivateKey.generate()
    ledger = DurableAnchorLedger(tmp_path / "anchors.jsonl")
    interlock = AuditReleaseInterlock(
        tmp_path / "release.jsonl", ledger=ledger, public_key=key.public_key()
    )
    service = AuditAnchorService(
        key_id="pro-anchor-1", private_key=key, ledger=ledger, interlock=interlock
    )
    first = event(1, ZERO_HASH, {"event": "publication-ready"})
    target = binding(first)

    async def accept(_: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "status": "created"}

    await service.anchor_and_submit(
        (first,),
        observed_at="2026-07-19T00:00:00.000Z",
        submit=accept,
        release_binding=target,
    )
    interlock.require_release_allowed(target)
    with pytest.raises(ReleaseBlockedError):
        interlock.require_release_allowed(
            target.model_copy(update={"packet_id": "edition-forged"})
        )

    async def explode(_: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("network down")

    second = event(2, first.event_hash, {"event": "publication-followup"})
    second_target = binding(second, "edition-2")
    with pytest.raises(RuntimeError, match="network down"):
        await service.anchor_and_submit(
            (second,),
            observed_at="2026-07-19T00:00:01.000Z",
            submit=explode,
            release_binding=second_target,
        )
    with pytest.raises(ReleaseBlockedError):
        interlock.require_release_allowed(target)


def test_release_journal_rejects_forged_or_corrupt_final_row(tmp_path: Path) -> None:
    path = tmp_path / "release.jsonl"
    path.write_text('{"state":"unlocked"}\n', encoding="utf-8")
    interlock = AuditReleaseInterlock(path)
    with pytest.raises(ReleaseBlockedError, match="invalid"):
        interlock.require_release_allowed(
            ReleaseBinding(
                stream_id="publication:main",
                stream_seq=1,
                event_hash="a" * 64,
                packet_id="edition-1",
                operation_id="/api/machine/publications/editions:edition-1",
            )
        )
    path.write_bytes(path.read_bytes() + b'{"schema_version":')
    with pytest.raises(ReleaseBlockedError, match="truncated"):
        interlock.require_release_allowed(
            ReleaseBinding(
                stream_id="publication:main",
                stream_seq=1,
                event_hash="a" * 64,
                packet_id="edition-1",
                operation_id="/api/machine/publications/editions:edition-1",
            )
        )


def test_feed_page_verifies_checkpoint_head_events_and_target_binding() -> None:
    payload = {
        "schema_version": "publication-operation.v1",
        "operation": "edition.publish",
        "packet_id": "edition-1",
    }
    event_hash = build_audit_event_hash(
        "magazine-publication.v1", 1, ZERO_HASH, payload
    )
    first = AuditEventRecord(
        stream_id="magazine-publication.v1",
        stream_seq=1,
        previous_event_hash=ZERO_HASH,
        event_hash=event_hash,
        payload=payload,
    )
    page = AuditFeedPageV1.model_validate(
        {
            "schema_version": "audit-feed.v1",
            "stream_id": "magazine-publication.v1",
            "checkpoint": {"stream_seq": "0", "event_hash": ZERO_HASH},
            "head": {"stream_seq": "1", "event_hash": first.event_hash},
            "events": [
                {
                    **first.model_dump(mode="json"),
                    "stream_seq": "1",
                }
            ],
            "promotion_target": {
                "operation": "edition.publish",
                "packet_id": "edition-1",
                "stream_seq": "1",
                "event_hash": first.event_hash,
            },
            "next_cursor": {"after_seq": "1", "checkpoint_hash": first.event_hash},
            "has_more": False,
        }
    )
    verified = verify_audit_feed_page(
        page,
        expected_stream_id="magazine-publication.v1",
        expected_sequence=0,
        expected_hash=ZERO_HASH,
        expected_operation="edition.publish",
        expected_packet_id="edition-1",
    )
    assert verified.target_binding is not None
    assert verified.target_binding.stream_seq == 1

    forged = page.model_copy(
        update={
            "promotion_target": page.promotion_target.model_copy(
                update={"packet_id": "edition-forged"}
            )
        }
    )
    with pytest.raises(AuditChainMismatch, match="promotion target"):
        verify_audit_feed_page(
            forged,
            expected_stream_id="magazine-publication.v1",
            expected_sequence=0,
            expected_hash=ZERO_HASH,
            expected_operation="edition.publish",
            expected_packet_id="edition-1",
        )

    unrelated_payload = {**payload, "packet_id": "edition-unrelated"}
    unrelated_hash = build_audit_event_hash(
        "magazine-publication.v1", 1, ZERO_HASH, unrelated_payload
    )
    payload_forged_raw = page.model_dump(mode="json")
    payload_forged_raw["head"]["event_hash"] = unrelated_hash
    payload_forged_raw["events"][0]["event_hash"] = unrelated_hash
    payload_forged_raw["events"][0]["payload"] = unrelated_payload
    payload_forged_raw["promotion_target"]["event_hash"] = unrelated_hash
    payload_forged_raw["next_cursor"]["checkpoint_hash"] = unrelated_hash
    payload_forged = AuditFeedPageV1.model_validate(payload_forged_raw)
    with pytest.raises(AuditChainMismatch, match="promotion target"):
        verify_audit_feed_page(
            payload_forged,
            expected_stream_id="magazine-publication.v1",
            expected_sequence=0,
            expected_hash=ZERO_HASH,
            expected_operation="edition.publish",
            expected_packet_id="edition-1",
        )


@pytest.mark.parametrize(
    ("target_packet_id", "target_sequence"),
    (("edition-a", 1), ("edition-b", 2)),
)
def test_feed_page_separates_verified_head_from_exact_promotion_target(
    target_packet_id: str,
    target_sequence: int,
) -> None:
    payload_a = {
        "schema_version": "publication-operation.v1",
        "operation": "edition.publish",
        "packet_id": "edition-a",
    }
    hash_a = build_audit_event_hash("magazine-publication.v1", 1, ZERO_HASH, payload_a)
    payload_b = {**payload_a, "packet_id": "edition-b"}
    hash_b = build_audit_event_hash("magazine-publication.v1", 2, hash_a, payload_b)
    target_hash = hash_a if target_sequence == 1 else hash_b
    page = AuditFeedPageV1.model_validate(
        {
            "schema_version": "audit-feed.v1",
            "stream_id": "magazine-publication.v1",
            "checkpoint": {"stream_seq": "0", "event_hash": ZERO_HASH},
            "head": {"stream_seq": "2", "event_hash": hash_b},
            "events": [
                {
                    "schema_version": "audit-event.v1",
                    "stream_id": "magazine-publication.v1",
                    "stream_seq": "1",
                    "previous_event_hash": ZERO_HASH,
                    "event_hash": hash_a,
                    "payload": payload_a,
                },
                {
                    "schema_version": "audit-event.v1",
                    "stream_id": "magazine-publication.v1",
                    "stream_seq": "2",
                    "previous_event_hash": hash_a,
                    "event_hash": hash_b,
                    "payload": payload_b,
                },
            ],
            "promotion_target": {
                "operation": "edition.publish",
                "packet_id": target_packet_id,
                "stream_seq": str(target_sequence),
                "event_hash": target_hash,
            },
            "next_cursor": {"after_seq": "2", "checkpoint_hash": hash_b},
            "has_more": False,
        }
    )

    verified = verify_audit_feed_page(
        page,
        expected_stream_id="magazine-publication.v1",
        expected_sequence=0,
        expected_hash=ZERO_HASH,
        expected_operation="edition.publish",
        expected_packet_id=target_packet_id,
    )

    assert verified.next_sequence == 2
    assert verified.next_hash == hash_b
    assert verified.target_binding is not None
    assert verified.target_binding.stream_seq == target_sequence
    assert verified.target_binding.event_hash == target_hash
