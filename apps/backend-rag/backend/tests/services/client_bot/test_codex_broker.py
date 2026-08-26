"""CodexBrokerClientBrainProvider — lane B2 (research capture Sol §1.5/§2,
MANDATE.md F3).

Tests the adapter's OWN logic (package building, deadline bounding, offer/
wait/consume orchestration, error-class -> ProviderFailureKind mapping) by
monkeypatching the ``wa_broker`` module functions it calls — ``wa_broker``'s
own SQL/admission/breaker behavior is exercised by
``tests/unit/services/test_wa_broker.py`` (including the new
``offer_client_job`` cases this lane added there); re-simulating that SQL
here would test the same thing twice while leaving this adapter's real
contract (how it REACTS to each outcome) unverified.

Guilt AND innocence throughout: every failure-path test proves the adapter
degrades correctly (guilt of the failure, innocence of the adapter), and the
happy-path tests prove it does not over-fire on a normal completion.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from backend.channels.profiles import CLIENT_WA_V1
from backend.services.client_bot.contracts import BrainCandidate
from backend.services.client_bot.providers.base import (
    ClientBrainProvider,
    ProviderFailure,
    ProviderFailureKind,
)
from backend.services.client_bot.providers.codex_broker import (
    CodexBrokerClientBrainProvider,
    _build_wire_package,
    _effective_deadline_s,
    _error_class_to_kind,
)
from backend.services.integrations import wa_broker
from backend.tests.duebot.goldens.builders import (
    FIXED_NOW,
    make_brain_request,
    make_canonical_message,
    make_grounding_bundle,
)

JOB_ID = uuid.uuid4()


class _FakeConn:
    """Stand-in for an acquired asyncpg connection. Only used by tests that
    exercise ``health()`` (which issues its own ``fetchrow`` directly) —
    every other test monkeypatches the ``wa_broker`` functions themselves,
    so the connection object those tests pass through is never actually
    used for SQL and only needs to exist.
    """

    def __init__(self, fetchrow_result: Any = None) -> None:
        self._fetchrow_result = fetchrow_result

    async def fetchrow(self, *_args: Any, **_kwargs: Any) -> Any:
        return self._fetchrow_result


class _FakePool:
    def __init__(self, conn: Any = None) -> None:
        self._conn = conn if conn is not None else _FakeConn()

    def acquire(self) -> Any:
        @asynccontextmanager
        async def _cm():
            yield self._conn

        return _cm()


def _request(case_id: str = "codex-broker-case", *, deadline_at: datetime = FIXED_NOW):
    message = make_canonical_message(case_id)
    grounding = make_grounding_bundle(case_id)
    return make_brain_request(
        case_id, message=message, profile=CLIENT_WA_V1, grounding=grounding, deadline_at=deadline_at
    )


def _valid_candidate_json(request) -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "disposition": "answer",
            "answer": "Jawaban singkat.",
            "claims": [],
            "cited_evidence_ids": [],
            "handoff_reason_code": None,
            "provider_name": "codex_broker",
            "model_name": "gpt-5.6-terra",
            "package_sha256": request.grounding.package_sha256,
        }
    )


# ── Protocol shape + identity ───────────────────────────────────────────


def test_protocol_shape_is_satisfied() -> None:
    provider = CodexBrokerClientBrainProvider(_FakePool())
    assert isinstance(provider, ClientBrainProvider)


def test_name_matches_router_codex_broker_literal() -> None:
    """provider_router.py's private _CODEX_BROKER_NAME and config.py's
    CLIENT_BOT_PRIMARY_PROVIDER/SHADOW_PROVIDER description both spell this
    literal exactly this way — a drift here would silently make the router
    unable to ever select this provider by name."""
    provider = CodexBrokerClientBrainProvider(_FakePool())
    assert provider.name == "codex_broker"


# ── _build_wire_package ─────────────────────────────────────────────────


def test_build_wire_package_is_valid_json_and_echoes_grounding_hash() -> None:
    request = _request()
    package, package_hash = _build_wire_package(request, output_schema_version="1.0")

    envelope = json.loads(package)  # must be valid JSON
    assert envelope["request_id"] == str(request.request_id)
    assert envelope["output_schema_version"] == "1.0"
    # The model must be told the grounding's own package_sha256 so it can
    # echo it verbatim (FinalPolicyGate check #2 compares against this).
    assert envelope["grounding"]["package_sha256"] == request.grounding.package_sha256
    assert "instructions" in envelope
    assert "package_sha256" in envelope["instructions"]

    import hashlib

    assert package_hash == hashlib.sha256(package.encode("utf-8")).hexdigest()


def test_build_wire_package_deterministic_for_same_request() -> None:
    request = _request()
    package_a, hash_a = _build_wire_package(request, output_schema_version="1.0")
    package_b, hash_b = _build_wire_package(request, output_schema_version="1.0")
    assert package_a == package_b
    assert hash_a == hash_b


def test_build_wire_package_carries_surface_constraints_from_profile() -> None:
    request = _request()
    package, _ = _build_wire_package(request, output_schema_version="1.0")
    constraints = json.loads(package)["surface_constraints"]
    assert constraints["surface"] == request.profile.surface.value
    assert constraints["hard_max_chars"] == request.profile.hard_max_chars
    assert constraints["citation_policy"] == request.profile.citation_policy.value


# ── _effective_deadline_s ───────────────────────────────────────────────


def test_effective_deadline_uses_configured_when_request_deadline_is_far() -> None:
    # _effective_deadline_s reads real wall-clock time (not an injectable
    # clock), so "far" must be relative to datetime.now(), not the fixed
    # fixture timestamp FIXED_NOW (which is a fixed PAST date and would
    # floor to 1 regardless of the configured budget).
    request = _request(deadline_at=datetime.now(timezone.utc) + timedelta(hours=1))
    assert _effective_deadline_s(request, 10) == 10


def test_effective_deadline_uses_remaining_when_smaller_than_configured() -> None:
    near_deadline = datetime.now(timezone.utc) + timedelta(seconds=3)
    request = _request(deadline_at=near_deadline)
    result = _effective_deadline_s(request, 15)
    assert 1 <= result <= 3


def test_effective_deadline_floors_at_one_when_already_passed() -> None:
    past_deadline = datetime.now(timezone.utc) - timedelta(seconds=5)
    request = _request(deadline_at=past_deadline)
    assert _effective_deadline_s(request, 15) == 1


def test_effective_deadline_defaults_to_wa_broker_deadline_seconds_when_unset() -> None:
    request = _request(deadline_at=datetime.now(timezone.utc) + timedelta(hours=1))
    assert _effective_deadline_s(request, None) == wa_broker.deadline_seconds()


# ── _error_class_to_kind ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("error_class", "expected"),
    [
        ("AUTH_DEAD", ProviderFailureKind.AUTH_DEAD),
        ("QUOTA", ProviderFailureKind.QUOTA),
        ("TIMEOUT", ProviderFailureKind.TIMEOUT),
        ("HOST_OFFLINE", ProviderFailureKind.HOST_OFFLINE),
        ("OUTPUT_INVALID", ProviderFailureKind.OUTPUT_INVALID),
        ("POLICY_BLOCKED", ProviderFailureKind.POLICY_BLOCKED),
        ("INTERNAL", ProviderFailureKind.INTERNAL),
    ],
)
def test_error_class_to_kind_maps_f3_vocabulary_1to1(
    error_class: str, expected: ProviderFailureKind
) -> None:
    assert _error_class_to_kind(error_class) is expected


@pytest.mark.parametrize(
    ("error_class", "expected"),
    [
        ("exec_timeout", ProviderFailureKind.TIMEOUT),
        # Documented gap (F3: "auth and quota MUST be distinct (today they
        # collapse; split before arming)") — the legacy daemon vocabulary
        # cannot express AUTH_DEAD/QUOTA separately yet, so this collapses
        # to INTERNAL rather than guessing either one.
        ("cli_failure", ProviderFailureKind.INTERNAL),
        ("cli_version_mismatch", ProviderFailureKind.INTERNAL),
        ("spawn_failure", ProviderFailureKind.HOST_OFFLINE),
        ("oversized_output", ProviderFailureKind.OUTPUT_INVALID),
        ("empty_output", ProviderFailureKind.OUTPUT_INVALID),
        ("policy_refusal", ProviderFailureKind.POLICY_BLOCKED),
    ],
)
def test_error_class_to_kind_maps_legacy_daemon_vocabulary(
    error_class: str, expected: ProviderFailureKind
) -> None:
    assert _error_class_to_kind(error_class) is expected


def test_error_class_to_kind_unknown_value_falls_back_to_internal() -> None:
    assert _error_class_to_kind("some_future_daemon_value") is ProviderFailureKind.INTERNAL


def test_error_class_to_kind_none_falls_back_to_internal() -> None:
    assert _error_class_to_kind(None) is ProviderFailureKind.INTERNAL


# ── generate(): happy path ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_happy_path_returns_parsed_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        assert kwargs["request_id"] == request.request_id
        assert kwargs["surface"] == request.message.surface.value
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        assert job_id == JOB_ID
        return wa_broker.WaitResult(wa_broker.WaitOutcome.COMPLETED)

    async def fake_consume(conn, job_id):  # noqa: ANN001
        assert job_id == JOB_ID
        return _valid_candidate_json(request)

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)
    monkeypatch.setattr(wa_broker, "consume_result", fake_consume)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    candidate = await provider.generate(request)

    assert isinstance(candidate, BrainCandidate)
    assert candidate.disposition == "answer"
    assert candidate.package_sha256 == request.grounding.package_sha256


@pytest.mark.asyncio
async def test_generate_passes_bounded_deadline_and_output_schema_to_offer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    near_deadline = datetime.now(timezone.utc) + timedelta(seconds=2)
    request = _request(deadline_at=near_deadline)
    captured: dict[str, Any] = {}

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        captured.update(kwargs)
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        return wa_broker.WaitResult(wa_broker.WaitOutcome.COMPLETED)

    async def fake_consume(conn, job_id):  # noqa: ANN001
        return _valid_candidate_json(request)

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)
    monkeypatch.setattr(wa_broker, "consume_result", fake_consume)

    provider = CodexBrokerClientBrainProvider(_FakePool(), deadline_s=15)
    await provider.generate(request)

    # The request's own deadline (2s out) is tighter than the configured
    # 15s budget — the SMALLER value must reach offer_client_job.
    assert 1 <= captured["deadline_s"] <= 2
    assert captured["output_schema_version"] == "1.0"


# ── generate(): offer-path failures ─────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected_kind"),
    [
        (wa_broker.OfferOutcome.BROKER_ABSENT, ProviderFailureKind.HOST_OFFLINE),
        (wa_broker.OfferOutcome.BREAKER_OPEN, ProviderFailureKind.HOST_OFFLINE),
        (wa_broker.OfferOutcome.QUEUE_FULL, ProviderFailureKind.TIMEOUT),
    ],
)
async def test_generate_maps_non_offered_outcomes(
    monkeypatch: pytest.MonkeyPatch, outcome: wa_broker.OfferOutcome, expected_kind: ProviderFailureKind
) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(outcome)

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.provider_name == "codex_broker"
    assert exc_info.value.kind is expected_kind


@pytest.mark.asyncio
async def test_generate_offer_raising_maps_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        raise RuntimeError("pool exploded")

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.INTERNAL


# ── generate(): wait-path failures ──────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_wait_deadline_maps_to_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        return wa_broker.WaitResult(wa_broker.WaitOutcome.DEADLINE)

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.TIMEOUT


@pytest.mark.asyncio
async def test_generate_wait_failed_uses_error_class_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        return wa_broker.WaitResult(wa_broker.WaitOutcome.FAILED, error_class="QUOTA")

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.QUOTA


@pytest.mark.asyncio
async def test_generate_wait_raising_maps_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        raise RuntimeError("db exploded")

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.INTERNAL


# ── generate(): consume-path failures ───────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_result", [None, "", "   "])
async def test_generate_consume_lost_maps_to_timeout(
    monkeypatch: pytest.MonkeyPatch, bad_result: str | None
) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        return wa_broker.WaitResult(wa_broker.WaitOutcome.COMPLETED)

    async def fake_consume(conn, job_id):  # noqa: ANN001
        return bad_result

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)
    monkeypatch.setattr(wa_broker, "consume_result", fake_consume)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.TIMEOUT


@pytest.mark.asyncio
async def test_generate_consume_raising_maps_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        return wa_broker.WaitResult(wa_broker.WaitOutcome.COMPLETED)

    async def fake_consume(conn, job_id):  # noqa: ANN001
        raise RuntimeError("db exploded")

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)
    monkeypatch.setattr(wa_broker, "consume_result", fake_consume)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.INTERNAL


@pytest.mark.asyncio
async def test_generate_invalid_json_maps_to_output_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        return wa_broker.WaitResult(wa_broker.WaitOutcome.COMPLETED)

    async def fake_consume(conn, job_id):  # noqa: ANN001
        return "not valid json {{{"

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)
    monkeypatch.setattr(wa_broker, "consume_result", fake_consume)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.OUTPUT_INVALID


@pytest.mark.asyncio
async def test_generate_schema_valid_json_but_contract_invalid_maps_to_output_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid JSON, but violates BrainCandidate's own model_validator (an
    'answer' disposition with a blank answer) — proves this adapter relies
    on real Pydantic validation, not just json.loads succeeding."""
    request = _request()

    async def fake_offer(conn, **kwargs):  # noqa: ANN001, ANN003
        return wa_broker.OfferResult(wa_broker.OfferOutcome.OFFERED, job_id=JOB_ID)

    async def fake_wait(pool, job_id):  # noqa: ANN001
        return wa_broker.WaitResult(wa_broker.WaitOutcome.COMPLETED)

    async def fake_consume(conn, job_id):  # noqa: ANN001
        return json.dumps(
            {
                "schema_version": "1.0",
                "disposition": "answer",
                "answer": "   ",  # whitespace-only — invalid per contracts.py
                "claims": [],
                "cited_evidence_ids": [],
                "handoff_reason_code": None,
                "provider_name": "codex_broker",
                "model_name": "gpt-5.6-terra",
                "package_sha256": request.grounding.package_sha256,
            }
        )

    monkeypatch.setattr(wa_broker, "offer_client_job", fake_offer)
    monkeypatch.setattr(wa_broker, "wait_for_job", fake_wait)
    monkeypatch.setattr(wa_broker, "consume_result", fake_consume)

    provider = CodexBrokerClientBrainProvider(_FakePool())
    with pytest.raises(ProviderFailure) as exc_info:
        await provider.generate(request)

    assert exc_info.value.kind is ProviderFailureKind.OUTPUT_INVALID


# ── health() ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_unhealthy_when_gauge_unseeded() -> None:
    provider = CodexBrokerClientBrainProvider(_FakePool(_FakeConn(fetchrow_result=None)))
    health = await provider.health()
    assert health.healthy is False
    assert health.detail == "gauge_unseeded"


@pytest.mark.asyncio
async def test_health_unhealthy_when_broker_alive_false() -> None:
    conn = _FakeConn(fetchrow_result={"breaker_state": "closed", "broker_alive": False})
    provider = CodexBrokerClientBrainProvider(_FakePool(conn))
    health = await provider.health()
    assert health.healthy is False
    assert health.detail == "host_offline"


@pytest.mark.asyncio
async def test_health_unhealthy_when_breaker_open() -> None:
    conn = _FakeConn(fetchrow_result={"breaker_state": "open", "broker_alive": True})
    provider = CodexBrokerClientBrainProvider(_FakePool(conn))
    health = await provider.health()
    assert health.healthy is False
    assert health.detail == "breaker_open"


@pytest.mark.asyncio
async def test_health_healthy_when_closed_and_alive() -> None:
    conn = _FakeConn(fetchrow_result={"breaker_state": "closed", "broker_alive": True})
    provider = CodexBrokerClientBrainProvider(_FakePool(conn))
    health = await provider.health()
    assert health.healthy is True
    assert health.detail == "breaker_closed"


@pytest.mark.asyncio
async def test_health_query_failure_reports_unhealthy_never_raises() -> None:
    class _RaisingConn:
        async def fetchrow(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("connection reset")

    provider = CodexBrokerClientBrainProvider(_FakePool(_RaisingConn()))
    health = await provider.health()
    assert health.healthy is False
    assert health.detail is not None and health.detail.startswith("gauge_query_error")
