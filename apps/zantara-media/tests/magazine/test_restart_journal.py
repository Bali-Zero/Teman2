from __future__ import annotations

import asyncio
import hashlib
import json
import multiprocessing
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from zantara_media.magazine.reconciler import (
    DurableOutcomeJournal,
    OutcomeBindingError,
    OutcomeRecord,
    OutcomeState,
    ReconcileResult,
)
from zantara_media.magazine.transport import MagazineTransport, TransportConfig
from zantara_media.magazine.audit_anchor import ReleaseBinding


PATH = "/api/machine/publications/editions"
PACKET = {"packet_id": "p-restart"}
BODY = json.dumps(PACKET, sort_keys=True, separators=(",", ":")).encode()
BODY_SHA256 = hashlib.sha256(BODY).hexdigest()
OPERATION_ID = f"{PATH}:p-restart"


class _AllowRelease:
    def require_release_allowed(self, _: ReleaseBinding) -> None:
        return None


RELEASE_BINDING = ReleaseBinding(
    stream_id="magazine-publication.v1",
    stream_seq=1,
    event_hash="a" * 64,
    packet_id="p-restart",
    operation_id=OPERATION_ID,
)


def _config() -> TransportConfig:
    return TransportConfig(
        base_url="https://magazine.example",
        siwc_bearer_token="dispatcher-token",
        hmac_key_id="key-1",
        hmac_secret="hmac-secret",
        audience="bali-zero-magazine",
        max_attempts=2,
        base_backoff_seconds=0,
    )


def _seed_process(path: str, state: str) -> None:
    journal = DurableOutcomeJournal(Path(path))
    asyncio.run(
        journal.record(
            OutcomeRecord(
                schema_version="magazine-outcome.v1",
                operation_id=OPERATION_ID,
                path=PATH,
                body_sha256=BODY_SHA256,
                state=OutcomeState(state),
                response=None,
            )
        )
    )


def _seed_in_separate_process(path: Path, state: OutcomeState) -> None:
    process = multiprocessing.get_context("spawn").Process(
        target=_seed_process,
        args=(str(path), state.value),
    )
    process.start()
    process.join(timeout=10)
    assert process.exitcode == 0


def _claim_process(path: str, active: Any, maximum: Any) -> None:
    async def run() -> None:
        journal = DurableOutcomeJournal(Path(path))
        async with journal.claim(OPERATION_ID):
            with active.get_lock():
                active.value += 1
                maximum.value = max(maximum.value, active.value)
            time.sleep(0.1)
            with active.get_lock():
                active.value -= 1

    asyncio.run(run())


def test_durable_operation_claim_is_exclusive_across_processes(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    active = context.Value("i", 0)
    maximum = context.Value("i", 0)
    path = str(tmp_path / "outcomes.jsonl")
    processes = [
        context.Process(target=_claim_process, args=(path, active, maximum))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    assert maximum.value == 1


@pytest.mark.asyncio
async def test_restart_reconciles_durable_unknown_before_any_send(tmp_path: Path) -> None:
    journal_path = tmp_path / "outcomes.jsonl"
    _seed_in_separate_process(journal_path, OutcomeState.unknown)
    sends = 0
    reconciliations: list[tuple[str, str, str]] = []

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal sends
        sends += 1
        return httpx.Response(201, json={"ok": True, "status": "created"})

    async def reconcile(operation_id: str, path: str, body_sha256: str) -> ReconcileResult:
        reconciliations.append((operation_id, path, body_sha256))
        return ReconcileResult(
            state=OutcomeState.completed,
            response={"ok": True, "status": "replay", "packet_id": "p-restart"},
        )

    transport = MagazineTransport(
        _config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        journal=DurableOutcomeJournal(journal_path),
        reconcile=reconcile,
        release_gate=_AllowRelease(),
    )
    result = await transport.post_json(PATH, PACKET, release_binding=RELEASE_BINDING)
    assert result["status"] == "replay"
    assert sends == 0
    assert reconciliations == [(OPERATION_ID, PATH, BODY_SHA256)]
    await transport.aclose()


@pytest.mark.asyncio
async def test_restart_retries_only_after_reconcile_proves_absent(tmp_path: Path) -> None:
    journal_path = tmp_path / "outcomes.jsonl"
    _seed_in_separate_process(journal_path, OutcomeState.pending)
    sends = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal sends
        sends += 1
        return httpx.Response(201, json={"ok": True, "status": "created"})

    async def reconcile(_: str, __: str, ___: str) -> ReconcileResult:
        return ReconcileResult(state=OutcomeState.absent, response=None)

    transport = MagazineTransport(
        _config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        journal=DurableOutcomeJournal(journal_path),
        reconcile=reconcile,
        release_gate=_AllowRelease(),
    )
    assert (
        await transport.post_json(PATH, PACKET, release_binding=RELEASE_BINDING)
    )["status"] == "created"
    assert sends == 1
    persisted = await DurableOutcomeJournal(journal_path).get(OPERATION_ID)
    assert persisted is not None
    assert persisted.state == OutcomeState.completed
    assert persisted.path == PATH
    assert persisted.body_sha256 == BODY_SHA256
    assert persisted.response == {"ok": True, "status": "created"}
    await transport.aclose()


@pytest.mark.asyncio
async def test_journal_rejects_operation_id_reuse_with_changed_body(tmp_path: Path) -> None:
    journal = DurableOutcomeJournal(tmp_path / "outcomes.jsonl")
    await journal.record(
        OutcomeRecord(
            schema_version="magazine-outcome.v1",
            operation_id=OPERATION_ID,
            path=PATH,
            body_sha256=BODY_SHA256,
            state=OutcomeState.completed,
            response={"ok": True},
        )
    )
    changed: dict[str, Any] = {"packet_id": "p-restart", "changed": True}
    transport = MagazineTransport(
        _config(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
        journal=journal,
        release_gate=_AllowRelease(),
    )
    with pytest.raises(OutcomeBindingError, match="operation binding mismatch"):
        await transport.post_json(PATH, changed, release_binding=RELEASE_BINDING)
    await transport.aclose()


def test_durable_journal_rejects_torn_or_open_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "outcomes.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": "magazine-outcome.v1",
                "operation_id": OPERATION_ID,
                "path": PATH,
                "body_sha256": BODY_SHA256,
                "state": "pending",
                "response": None,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="truncated final record"):
        asyncio.run(DurableOutcomeJournal(path).get(OPERATION_ID))
