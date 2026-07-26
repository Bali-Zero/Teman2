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
    CodeOwnedOperationsDomainService,
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
    "target_key": "collector:collector-run-0123456789abcdef",
    "actor_key": "b" * 64,
    "request_hash": "a" * 64,
    "reason_code": "collector_recovery",
    "status": "claimed",
    "claim_token": "claim-token-0123456789abcdef",
    "fencing_token": 1,
    "target_fencing_token": 1,
    "lease_deadline": "2026-07-19T05:00:00.000Z",
    "attempt_count": 1,
}

RELEASE_CLAIM: dict[str, Any] = {
    **CLAIM,
    "intent_kind": "release_story",
    "params": {
        "story_id": "story-0123456789abcdef",
        "story_version": 2,
        "expected_visibility_seq": 1,
        "release_attestation_id": "release-attestation-0123456789abcdef",
    },
    "target_id": "story-0123456789abcdef",
    "target_key": "story:story-0123456789abcdef",
    "reason_code": "gates_reverified",
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
        claim = self.claim or CLAIM
        return {
            "ok": True,
            "attestation": {
                "schema_version": "ops-effect-attestation.v1",
                "authorized": self.authorized,
                "status": "running" if self.authorized else "cancelled_revoked",
                "intent_id": claim["intent_id"],
                "request_hash": claim["request_hash"],
                "actor_key": claim["actor_key"],
                "target_id": claim["target_id"],
                "target_key": claim["target_key"],
                "fencing_token": claim["fencing_token"],
                "target_fencing_token": claim["target_fencing_token"],
                "policy_version": "roles.operations.v2",
                "effect_token": "effect-token-0123456789abcdef" if self.authorized else None,
                "attested_at": "2026-07-19T04:30:00.000Z",
                "expires_at": "2026-07-19T04:30:30.000Z",
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
        self.effects: list[tuple[str, Mapping[str, Any], int, int, str]] = []

    async def prepare(self, kind: str, params: Mapping[str, Any]) -> None:
        return None

    async def execute(
        self,
        kind: str,
        params: Mapping[str, Any],
        *,
        target_key: str,
        fencing_token: int,
        target_fencing_token: int,
        effect_token: str,
    ) -> Mapping[str, Any]:
        self.effects.append((kind, params, fencing_token, target_fencing_token, effect_token))
        target_id = next(
            value
            for key, value in params.items()
            if key.endswith("_id") and key not in {"collector_id", "release_attestation_id"}
        )
        return {
            "schema_version": "ops-domain-receipt.v1",
            "code": "effect_acknowledged",
            "intent_kind": kind,
            "target_id": target_id,
            "target_key": target_key,
            "fencing_token": fencing_token,
            "target_fencing_token": target_fencing_token,
            "effect_token": effect_token,
        }


def test_worker_rejects_unknown_kinds_and_arbitrary_execution_fields(tmp_path: Path) -> None:
    for contaminated in (
        {**CLAIM, "intent_kind": "run_command"},
        {**CLAIM, "params": {**CLAIM["params"], "shell": "rm -rf /"}},
        {**CLAIM, "params": {**CLAIM["params"], "url": "https://evil.example"}},
        {**CLAIM, "params": {**CLAIM["params"], "path": "/tmp/client"}},
    ):
        with pytest.raises(OperationsWorkerError):
            OperationsWorker.validate_intent(contaminated)


def test_worker_accepts_sites_valid_release_story_claim_and_rejects_schema_drift() -> None:
    assert OperationsWorker.validate_intent(RELEASE_CLAIM)["params"] == RELEASE_CLAIM["params"]

    invalid_release_attestation_ids = [None, "", "ops-intent-0123456789abcdef"]
    for value in invalid_release_attestation_ids:
        with pytest.raises(OperationsWorkerError):
            OperationsWorker.validate_intent(
                {
                    **RELEASE_CLAIM,
                    "params": {
                        **RELEASE_CLAIM["params"],
                        "release_attestation_id": value,
                    },
                }
            )

    with pytest.raises(OperationsWorkerError):
        OperationsWorker.validate_intent(
            {
                **RELEASE_CLAIM,
                "params": {
                    "story_id": RELEASE_CLAIM["params"]["story_id"],
                    "story_version": RELEASE_CLAIM["params"]["story_version"],
                    "expected_visibility_seq": RELEASE_CLAIM["params"]["expected_visibility_seq"],
                },
            }
        )

    with pytest.raises(OperationsWorkerError):
        OperationsWorker.validate_intent(
            {
                **RELEASE_CLAIM,
                "params": {**RELEASE_CLAIM["params"], "attestation_id": "generic-id-0001"},
            }
        )

    with pytest.raises(OperationsWorkerError):
        OperationsWorker.validate_intent(
            {
                **CLAIM,
                "intent_kind": "quarantine_story",
                "reason_code": "content_safety",
                "params": {
                    "story_id": "story-0123456789abcdef",
                    "story_version": 2,
                    "expected_visibility_seq": 1,
                    "release_attestation_id": "release-attestation-0123456789abcdef",
                },
                "target_id": "story-0123456789abcdef",
                "target_key": "story:story-0123456789abcdef",
            }
        )


@pytest.mark.asyncio
async def test_worker_runs_sites_valid_release_story_claim_through_effect_path(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(RELEASE_CLAIM)
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
        (
            "release_story",
            RELEASE_CLAIM["params"],
            1,
            1,
            "effect-token-0123456789abcdef",
        ),
    ]
    assert transport.results[0]["status"] == "succeeded"
    assert transport.results[0]["receipt"]["target_id"] == RELEASE_CLAIM["target_id"]


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
        (
            "rerun_collector",
            CLAIM["params"],
            1,
            1,
            "effect-token-0123456789abcdef",
        ),
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
        "target_fencing_token",
        "actor_key",
        "target_key",
        "target_id",
        "effect_token",
        "attested_policy_version",
        "attestation_expires_at",
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
        async def execute(
            self,
            kind: str,
            params: Mapping[str, Any],
            *,
            target_key: str,
            fencing_token: int,
            target_fencing_token: int,
            effect_token: str,
        ) -> Mapping[str, Any]:
            self.effects.append((kind, params, fencing_token, target_fencing_token, effect_token))
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
async def test_production_factory_dispatches_five_code_owned_effects_with_full_authority() -> None:
    class Runner:
        def __init__(self) -> None:
            self.labels: list[str] = []

        async def kickstart(self, label: str) -> None:
            self.labels.append(label)

    class EffectTransport:
        def __init__(self) -> None:
            self.effects: list[Mapping[str, Any]] = []

        async def apply_operation_effect(self, effect: Mapping[str, Any]) -> Mapping[str, Any]:
            self.effects.append(effect)
            return {
                "schema_version": "ops-domain-receipt.v1",
                "code": "effect_acknowledged",
                **{
                    key: effect[key]
                    for key in (
                        "intent_kind",
                        "target_id",
                        "target_key",
                        "fencing_token",
                        "target_fencing_token",
                        "effect_token",
                    )
                },
            }

    runner = Runner()
    transport = EffectTransport()
    cases: dict[str, Mapping[str, Any]] = {
        "rerun_collector": CLAIM["params"],
        "rebuild_edition": {
            "edition_id": "edition-0123456789abcdef",
            "expected_revision": 2,
        },
        "quarantine_story": {
            "story_id": "story-0123456789abcdef",
            "story_version": 2,
            "expected_visibility_seq": 1,
        },
        "release_story": {
            "story_id": "story-0123456789abcdef",
            "story_version": 2,
            "expected_visibility_seq": 1,
            "release_attestation_id": "release-attestation-0123456789abcdef",
        },
        "refresh_research_job": {"research_job_id": "research-job-0123456789abcdef"},
    }
    service = build_operations_domain_service(transport=transport, runner=runner)
    for kind, params in cases.items():
        await service.prepare(kind, params)
        receipt = await service.execute(
            kind,
            params,
            target_key=f"{'collector' if kind == 'rerun_collector' else 'edition' if kind == 'rebuild_edition' else 'research' if kind == 'refresh_research_job' else 'story'}:{next(value for key, value in params.items() if key.endswith('_id') and key != 'collector_id' and key != 'release_attestation_id')}",
            fencing_token=1,
            target_fencing_token=2,
            effect_token="effect-token-0123456789abcdef",
        )
        assert receipt == {
            "schema_version": "ops-domain-receipt.v1",
            "code": "effect_acknowledged",
            "intent_kind": kind,
            "target_id": next(
                value
                for key, value in params.items()
                if key.endswith("_id") and key != "collector_id" and key != "release_attestation_id"
            ),
            "target_key": f"{'collector' if kind == 'rerun_collector' else 'edition' if kind == 'rebuild_edition' else 'research' if kind == 'refresh_research_job' else 'story'}:{next(value for key, value in params.items() if key.endswith('_id') and key != 'collector_id' and key != 'release_attestation_id')}",
            "fencing_token": 1,
            "target_fencing_token": 2,
            "effect_token": "effect-token-0123456789abcdef",
        }

    assert runner.labels == [
        "com.balizero.regulatory-watcher.daily",
        "com.balizero.magazine.publisher",
        "com.balizero.magazine.research-worker",
    ]
    assert [effect["intent_kind"] for effect in transport.effects] == [
        "quarantine_story",
        "release_story",
    ]

    with pytest.raises(CapabilityUnavailableError):
        await service.prepare("rerun_collector", {**CLAIM["params"], "command": "forbidden"})

    with pytest.raises(OperationsRuntimeConfigError):
        CodeOwnedOperationsDomainService(transport=transport, runner=None)


@pytest.mark.asyncio
async def test_worker_rejects_every_unbound_or_expired_attestation(tmp_path: Path) -> None:
    mutations = {
        "intent_id": "ops-intent-fedcba9876543210",
        "request_hash": "f" * 64,
        "actor_key": "c" * 64,
        "target_id": "collector-run-fedcba9876543210",
        "target_key": "collector:collector-run-fedcba9876543210",
        "fencing_token": 2,
        "target_fencing_token": 2,
        "expires_at": "2026-07-19T04:29:59.000Z",
    }
    for field, value in mutations.items():
        transport = FakeTransport()
        original = transport.attest_operation_intent

        async def altered(*, _field: str = field, _value: Any = value, **kwargs: Any):
            response = await original(**kwargs)
            response["attestation"][_field] = _value
            return response

        transport.attest_operation_intent = altered  # type: ignore[method-assign]
        domain = FakeDomain()
        worker = OperationsWorker(
            transport=transport,
            domain=domain,
            journal=OperationsJournal(tmp_path / f"{field}.sqlite3"),
            now=lambda: "2026-07-19T04:30:00.000Z",
        )
        with pytest.raises(OperationsWorkerError, match="attestation"):
            await worker.run_once()
        assert domain.effects == []


@pytest.mark.asyncio
async def test_target_fence_cas_rejects_stale_and_reused_effect_authority(
    tmp_path: Path,
) -> None:
    journal = OperationsJournal(tmp_path / "operations.sqlite3")
    await journal.authorize_effect(
        target_key=CLAIM["target_key"],
        target_fencing_token=2,
        effect_token="effect-token-2222222222222222",
        expires_at="2026-07-19T04:30:30.000Z",
        now="2026-07-19T04:30:00.000Z",
    )
    with pytest.raises(OperationsWorkerError, match="stale target fence"):
        await journal.authorize_effect(
            target_key=CLAIM["target_key"],
            target_fencing_token=1,
            effect_token="effect-token-1111111111111111",
            expires_at="2026-07-19T04:30:30.000Z",
            now="2026-07-19T04:30:00.000Z",
        )
    with pytest.raises(OperationsWorkerError, match="effect authority replay"):
        await journal.authorize_effect(
            target_key=CLAIM["target_key"],
            target_fencing_token=2,
            effect_token="effect-token-2222222222222222",
            expires_at="2026-07-19T04:30:30.000Z",
            now="2026-07-19T04:30:00.000Z",
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
