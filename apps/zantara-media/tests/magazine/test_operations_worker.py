from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest

from zantara_media.cli.magazine_operations_worker import _parser
from zantara_media.magazine.operations_worker import (
    OperationsJournal,
    OperationsWorker,
    OperationsWorkerError,
)
from zantara_media.magazine.operations_runtime import (
    CapabilityUnavailableError,
    FixedOperationsDomainService,
    OperationsRuntimeConfigError,
    build_operations_domain_service,
)
from zantara_media.magazine.transport import MagazineTransport, TransportConfig


CLAIM: dict[str, Any] = {
    "schema_version": "ops-claim-result.v1",
    "intent_id": "ops-intent-0123456789abcdef",
    "intent_kind": "rerun_collector",
    "params": {
        "collector_id": "regulatory-watcher",
        "failed_run_id": "collector-run-0123456789abcdef",
    },
    "target_id": "collector-run-0123456789abcdef",
    "request_hash": "a" * 64,
    "reason_code": "collector_recovery",
    "status": "claimed",
    "claim_token": "claim-token-0123456789abcdef",
    "fencing_token": 1,
    "lease_deadline": "2026-07-19T05:00:00.000Z",
    "attempt_count": 1,
}


class FakeTransport:
    def __init__(self, claim: Mapping[str, Any] | None = CLAIM) -> None:
        self.claim = claim
        self.events: list[str] = []
        self.results: list[Mapping[str, Any]] = []
        self.authorized = True
        self.terminal_ack = asyncio.Event()

    async def claim_operation_intent(self, *, worker_id: str, lease_seconds: int):
        self.events.append("claim")
        return self.claim

    async def start_operation_intent(self, **kwargs: Any):
        self.events.append("start")
        return {"ok": True, "status": "running"}

    async def heartbeat_operation_intent(self, **kwargs: Any):
        self.events.append("heartbeat")
        return {"ok": True, "status": "running"}

    async def attest_operation_intent(self, **kwargs: Any):
        self.events.append("attest")
        return {
            "ok": True,
            "attestation": {
                "authorized": self.authorized,
                "status": "running" if self.authorized else "cancelled_revoked",
                "policy_version": "roles.operations.v2",
                "effect_token": "effect-token-0123456789abcdef" if self.authorized else None,
            },
        }

    async def submit_operation_result(self, *, intent_id: str, result: Mapping[str, Any]):
        self.events.append("result")
        self.results.append(result)
        await asyncio.sleep(0.02)
        self.terminal_ack.set()
        return {"ok": True, "status": "created"}


class FakeDomain:
    def __init__(self) -> None:
        self.effects: list[tuple[str, Mapping[str, Any], int]] = []

    async def prepare(self, kind: str, params: Mapping[str, Any]) -> None:
        return None

    async def execute(self, kind: str, params: Mapping[str, Any], *, fencing_token: int) -> str:
        self.effects.append((kind, params, fencing_token))
        return "effect_acknowledged"


def test_worker_rejects_unknown_kinds_and_arbitrary_execution_fields(tmp_path: Path) -> None:
    for contaminated in (
        {**CLAIM, "intent_kind": "run_command"},
        {**CLAIM, "params": {**CLAIM["params"], "shell": "rm -rf /"}},
        {**CLAIM, "params": {**CLAIM["params"], "url": "https://evil.example"}},
        {**CLAIM, "params": {**CLAIM["params"], "path": "/tmp/client"}},
    ):
        with pytest.raises(OperationsWorkerError):
            OperationsWorker.validate_intent(contaminated)


@pytest.mark.asyncio
async def test_worker_attests_immediately_before_effect_and_heartbeats_until_receipt(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    domain = FakeDomain()
    worker = OperationsWorker(
        transport=transport,
        domain=domain,
        journal=OperationsJournal(tmp_path / "operations.sqlite3"),
        now=lambda: "2026-07-19T04:30:00.000Z",
        heartbeat_interval_seconds=0.005,
    )
    assert await worker.run_once() is True
    assert domain.effects == [
        ("rerun_collector", CLAIM["params"], 1),
    ]
    assert transport.events.index("attest") < transport.events.index("result")
    assert "heartbeat" in transport.events
    assert transport.terminal_ack.is_set()
    record = await worker.journal.load(CLAIM["intent_id"])
    assert record is not None and record.phase == "receipt_acknowledged"
    assert set(transport.results[0]) == {
        "schema_version",
        "intent_id",
        "request_hash",
        "status",
        "completed_at",
        "receipt",
        "failure",
        "claim_token",
        "fencing_token",
        "effect_token",
        "attested_policy_version",
    }


@pytest.mark.asyncio
async def test_final_revocation_prevents_domain_effect(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.authorized = False
    domain = FakeDomain()
    worker = OperationsWorker(
        transport=transport,
        domain=domain,
        journal=OperationsJournal(tmp_path / "operations.sqlite3"),
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    assert await worker.run_once() is True
    assert domain.effects == []
    assert transport.results == []


@pytest.mark.asyncio
async def test_possible_effect_crash_becomes_outcome_unknown_without_replay(
    tmp_path: Path,
) -> None:
    class AmbiguousDomain(FakeDomain):
        async def execute(self, kind: str, params: Mapping[str, Any], *, fencing_token: int) -> str:
            self.effects.append((kind, params, fencing_token))
            raise TimeoutError("private downstream detail")

    transport = FakeTransport()
    domain = AmbiguousDomain()
    worker = OperationsWorker(
        transport=transport,
        domain=domain,
        journal=OperationsJournal(tmp_path / "operations.sqlite3"),
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    assert await worker.run_once() is True
    assert len(domain.effects) == 1
    assert transport.results[0]["status"] == "outcome_unknown"
    assert transport.results[0]["failure"] == {"code": "outcome_ambiguous"}
    assert "private" not in str(transport.results[0])
    assert (await worker.journal.load(CLAIM["intent_id"])).phase == "receipt_acknowledged"


@pytest.mark.asyncio
async def test_journal_rejects_stale_fence_and_preserves_effect_started(tmp_path: Path) -> None:
    journal = OperationsJournal(tmp_path / "operations.sqlite3")
    await journal.record(
        intent_id=CLAIM["intent_id"],
        request_hash=CLAIM["request_hash"],
        target_key="rerun_collector:collector-run-0123456789abcdef",
        fencing_token=2,
        phase="effect_started",
        result=None,
    )
    with pytest.raises(OperationsWorkerError, match="stale fence"):
        await journal.record(
            intent_id=CLAIM["intent_id"],
            request_hash=CLAIM["request_hash"],
            target_key="rerun_collector:collector-run-0123456789abcdef",
            fencing_token=1,
            phase="claimed",
            result=None,
        )
    assert (await journal.load(CLAIM["intent_id"])).phase == "effect_started"


@pytest.mark.asyncio
async def test_journal_rejects_same_fence_phase_regression(tmp_path: Path) -> None:
    journal = OperationsJournal(tmp_path / "operations.sqlite3")
    binding = {
        "intent_id": CLAIM["intent_id"],
        "request_hash": CLAIM["request_hash"],
        "target_key": "rerun_collector:collector-run-0123456789abcdef",
        "fencing_token": 1,
    }
    await journal.record(**binding, phase="effect_started", result=None)
    with pytest.raises(OperationsWorkerError, match="phase regression"):
        await journal.record(**binding, phase="claimed", result=None)
    assert (await journal.load(CLAIM["intent_id"])).phase == "effect_started"


@pytest.mark.asyncio
async def test_production_factory_is_exact_and_fails_closed() -> None:
    service = build_operations_domain_service()
    for kind in (
        "rerun_collector",
        "rebuild_edition",
        "quarantine_story",
        "release_story",
        "refresh_research_job",
    ):
        with pytest.raises(CapabilityUnavailableError):
            await service.prepare(kind, {})

    with pytest.raises(OperationsRuntimeConfigError):
        FixedOperationsDomainService(
            {
                "rerun_collector": lambda: None,
                "rebuild_edition": lambda: None,
                "quarantine_story": lambda: None,
                "release_story": lambda: None,
                "refresh_research_job": lambda: None,
                "shell": lambda: None,
            }
        )


@pytest.mark.asyncio
async def test_transport_uses_only_fixed_signed_operations_routes() -> None:
    captured: list[tuple[str, Mapping[str, Any], str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(await request.aread())
        captured.append(
            (
                request.url.path,
                body,
                request.headers.get("authorization"),
            )
        )
        if request.url.path.endswith("/claim"):
            return httpx.Response(200, json={"ok": True, "intent": CLAIM})
        if request.url.path.endswith("/pre-effect-attest"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "attestation": {
                        "authorized": True,
                        "effect_token": "effect-token-0123456789abcdef",
                    },
                },
            )
        return httpx.Response(201, json={"ok": True, "status": "created"})

    transport = MagazineTransport(
        TransportConfig(
            base_url="https://magazine.example",
            siwc_bearer_token="dispatcher-token",
            hmac_key_id="key-1",
            hmac_secret="hmac-secret",
            audience="bali-zero-magazine",
            max_attempts=1,
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await transport.claim_operation_intent(worker_id="worker:pro-magazine", lease_seconds=60)
    common = {
        "intent_id": CLAIM["intent_id"],
        "claim_token": CLAIM["claim_token"],
        "fencing_token": 1,
    }
    await transport.start_operation_intent(**common)
    await transport.heartbeat_operation_intent(**common, lease_seconds=60)
    await transport.attest_operation_intent(**common)
    await transport.submit_operation_result(
        intent_id=CLAIM["intent_id"],
        result={"schema_version": "ops-result.v1"},
    )
    await transport.aclose()

    assert [item[0] for item in captured] == [
        "/api/machine/operations/intents/claim",
        f"/api/machine/operations/intents/{CLAIM['intent_id']}/start",
        f"/api/machine/operations/intents/{CLAIM['intent_id']}/heartbeat",
        f"/api/machine/operations/intents/{CLAIM['intent_id']}/pre-effect-attest",
        f"/api/machine/operations/intents/{CLAIM['intent_id']}/result",
    ]
    assert [item[1]["schema_version"] for item in captured] == [
        "ops-claim.v1",
        "ops-start.v1",
        "ops-heartbeat.v1",
        "ops-pre-effect-attest.v1",
        "ops-result.v1",
    ]
    assert all(item[2] == "Bearer dispatcher-token" for item in captured)


def test_production_cli_exposes_no_command_url_or_path_arguments() -> None:
    parser = _parser()
    assert parser.parse_args([]).min_backoff_seconds == 1.0
    for field in ("--command", "--url", "--path", "--shell"):
        with pytest.raises(SystemExit):
            parser.parse_args([field, "forbidden"])
