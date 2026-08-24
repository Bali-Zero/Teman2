"""ClientBotEngine — the top-level orchestration loop. See its own module
docstring for the fail-closed DeliveryFence default and the "ships dark"
claim this test suite backs with actual assertions, not just prose.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import pytest

from backend.channels.models import ClientSurface
from backend.services.client_bot.contracts import BrainCandidate, BrainRequest, EvidenceItem
from backend.services.client_bot.engine import (
    ClientBotEngine,
    default_send_gate_from_settings,
)
from backend.services.client_bot.grounding import GroundingBundleBuilder
from backend.services.client_bot.policy.final_gate import DeliveryFence
from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.services.client_bot.provider_router import ClientBrainProviderRouter
from backend.services.client_bot.providers.base import ProviderFailure, ProviderFailureKind
from backend.tests.duebot.goldens.builders import make_canonical_message, make_evidence_item


class _EchoProvider:
    """Builds a BrainCandidate that structurally matches whatever
    BrainRequest it receives (echoes package_sha256) — needed because
    GroundingBundleBuilder computes a real sha256 this test cannot predict
    ahead of time. `answer_script` is a list of answer texts returned in
    order, one per call — lets a test drive the one-retry loop.
    """

    def __init__(self, name: str, answer_script: list[str]) -> None:
        self.name = name
        self._answers = list(answer_script)
        self.calls = 0

    async def generate(self, request: BrainRequest) -> BrainCandidate:
        self.calls += 1
        answer = self._answers.pop(0)
        return BrainCandidate(
            schema_version="1.0",
            disposition="answer",
            answer=answer,
            claims=(),
            cited_evidence_ids=(),
            handoff_reason_code=None,
            provider_name=self.name,
            model_name="test-model",
            package_sha256=request.grounding.package_sha256,
        )

    async def health(self):
        raise NotImplementedError


class _AlwaysFailingProvider:
    def __init__(self, name: str, kind: ProviderFailureKind) -> None:
        self.name = name
        self._kind = kind

    async def generate(self, request: BrainRequest) -> BrainCandidate:
        raise ProviderFailure(self.name, self._kind, "simulated failure")

    async def health(self):
        raise NotImplementedError


def _router(provider) -> ClientBrainProviderRouter:
    return ClientBrainProviderRouter(
        {"gemini": provider},
        primary_provider="gemini",
        fallback_provider=None,
        shadow_provider=None,
        codex_broker_enabled=False,
        future_metered_enabled=False,
    )


_OPEN_FENCE = DeliveryFence(
    thread_owned=True,
    thread_epoch_current=True,
    human_taken_over=False,
    terminal_response_already_sent=False,
    service_window_expired=False,
)


@pytest.mark.asyncio
async def test_zero_wiring_fails_closed_on_the_delivery_fence() -> None:
    provider = _EchoProvider("gemini", ["Jawaban singkat yang jelas."])
    engine = ClientBotEngine(provider_router=_router(provider))
    message = make_canonical_message("eng")
    result = await engine.handle(message, domain="immigration")
    assert result.decision.verdict == GateVerdict.DROP
    assert result.decision.reason == GateReason.THREAD_OWNERSHIP_LOST
    assert result.should_send is False
    assert result.regenerated is False
    # No EvidenceRetriever wired (the default) — every result from this
    # engine must say so structurally, per the team lead's 2026-08-25
    # ruling: a shadow/quality number must never be computable from an
    # EngineResult without this flag right next to it.
    assert result.evidence_retrieval_stubbed is True
    assert engine.evidence_retrieval_is_stubbed is True


@pytest.mark.asyncio
async def test_allow_with_send_gate_off_is_shadow_mode() -> None:
    provider = _EchoProvider("gemini", ["Jawaban singkat yang jelas."])
    engine = ClientBotEngine(
        provider_router=_router(provider),
        delivery_fence_probe=lambda _message: _OPEN_FENCE,
    )
    message = make_canonical_message("eng")
    result = await engine.handle(message, domain="immigration")
    assert result.decision.verdict == GateVerdict.ALLOW
    assert result.should_send is False  # no send_gate wired -> always False (fail-dark default)


@pytest.mark.asyncio
async def test_allow_with_send_gate_on_is_deliverable() -> None:
    provider = _EchoProvider("gemini", ["Jawaban singkat yang jelas."])
    engine = ClientBotEngine(
        provider_router=_router(provider),
        delivery_fence_probe=lambda _message: _OPEN_FENCE,
        send_gate=lambda surface: surface == ClientSurface.WHATSAPP,
    )
    message = make_canonical_message("eng", surface=ClientSurface.WHATSAPP)
    result = await engine.handle(message, domain="immigration")
    assert result.decision.verdict == GateVerdict.ALLOW
    assert result.should_send is True


@pytest.mark.asyncio
async def test_send_gate_is_per_surface_not_global() -> None:
    provider = _EchoProvider("gemini", ["Jawaban singkat yang jelas."])
    engine = ClientBotEngine(
        provider_router=_router(provider),
        delivery_fence_probe=lambda _message: _OPEN_FENCE,
        send_gate=lambda surface: surface == ClientSurface.WHATSAPP,
    )
    message = make_canonical_message("eng", surface=ClientSurface.INSTAGRAM)
    result = await engine.handle(message, domain="immigration")
    assert result.decision.verdict == GateVerdict.ALLOW
    assert result.should_send is False


@pytest.mark.asyncio
async def test_text_defect_triggers_exactly_one_regeneration() -> None:
    provider = _EchoProvider("gemini", ["broken\x07answer", "Jawaban singkat yang jelas."])
    engine = ClientBotEngine(
        provider_router=_router(provider),
        delivery_fence_probe=lambda _message: _OPEN_FENCE,
    )
    message = make_canonical_message("eng")
    result = await engine.handle(message, domain="immigration")
    assert provider.calls == 2
    assert result.regenerated is True
    assert result.decision.verdict == GateVerdict.ALLOW


@pytest.mark.asyncio
async def test_text_defect_persisting_after_retry_is_not_retried_again() -> None:
    provider = _EchoProvider("gemini", ["broken\x07one", "broken\x07two"])
    engine = ClientBotEngine(
        provider_router=_router(provider),
        delivery_fence_probe=lambda _message: _OPEN_FENCE,
    )
    message = make_canonical_message("eng")
    result = await engine.handle(message, domain="immigration")
    assert provider.calls == 2  # exactly one retry, never a third attempt
    assert result.regenerated is True
    assert result.decision.verdict == GateVerdict.TEXT_DEFECT


@pytest.mark.asyncio
async def test_all_providers_exhausted_is_a_terminal_handoff_never_a_gate_call() -> None:
    provider = _AlwaysFailingProvider("gemini", ProviderFailureKind.TIMEOUT)
    engine = ClientBotEngine(
        provider_router=_router(provider),
        delivery_fence_probe=lambda _message: _OPEN_FENCE,
    )
    message = make_canonical_message("eng")
    result = await engine.handle(message, domain="immigration")
    assert result.decision.verdict == GateVerdict.HANDOFF
    assert result.decision.reason == GateReason.PROVIDERS_EXHAUSTED
    assert result.decision.rendered_text is None
    assert result.should_send is False
    assert result.regenerated is False
    assert "gemini:timeout" in result.decision.reason_detail


class _FixedRetriever:
    def __init__(self, items: tuple[EvidenceItem, ...]) -> None:
        self._items = items

    async def retrieve(self, query: str, domain: str) -> tuple[EvidenceItem, ...]:
        return self._items


@pytest.mark.asyncio
async def test_evidence_retrieval_stubbed_is_false_once_a_real_retriever_is_wired() -> None:
    retriever = _FixedRetriever((make_evidence_item("eng", suffix="ev1"),))
    provider = _EchoProvider("gemini", ["Jawaban singkat yang jelas."])
    engine = ClientBotEngine(
        provider_router=_router(provider),
        grounding_builder=GroundingBundleBuilder(evidence_retriever=retriever),
        delivery_fence_probe=lambda _message: _OPEN_FENCE,
    )
    assert engine.evidence_retrieval_is_stubbed is False
    message = make_canonical_message("eng")
    result = await engine.handle(message, domain="immigration")
    assert result.evidence_retrieval_stubbed is False


def test_default_send_gate_from_settings_reads_the_four_kill_switch_fields() -> None:
    class _FakeSettings:
        client_bot_wa_send_enabled = True
        client_bot_ig_send_enabled = False
        client_bot_portal_send_enabled = False
        client_bot_kbli_send_enabled = False

    gate = default_send_gate_from_settings(_FakeSettings())
    assert gate(ClientSurface.WHATSAPP) is True
    assert gate(ClientSurface.INSTAGRAM) is False
    assert gate(ClientSurface.PORTAL) is False
    assert gate(ClientSurface.KBLI_WIDGET) is False


def test_default_send_gate_from_settings_defaults_missing_attrs_to_false() -> None:
    class _EmptySettings:
        pass

    gate = default_send_gate_from_settings(_EmptySettings())
    assert gate(ClientSurface.WHATSAPP) is False
