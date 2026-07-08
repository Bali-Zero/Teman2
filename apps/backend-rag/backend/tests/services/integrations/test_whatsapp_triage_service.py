from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services.integrations import whatsapp_triage_service as triage_module
from backend.services.integrations.whatsapp_triage_service import (
    TriageDecision,
    WhatsAppTriageService,
)


def configure_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    personal_contacts: str = "",
    allowed_numbers: str = "",
) -> None:
    monkeypatch.setattr(
        triage_module,
        "settings",
        SimpleNamespace(
            whatsapp_personal_contacts=personal_contacts,
            whatsapp_allowed_numbers=allowed_numbers,
        ),
    )


def test_allowed_numbers_default_to_open_access(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    assert service.is_allowed("+6281") is True


def test_allowed_numbers_strip_plus_before_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch, allowed_numbers="6281,6282")
    service = WhatsAppTriageService()

    assert service.is_allowed("+6281") is True
    assert service.is_allowed("+6283") is False


@pytest.mark.asyncio
async def test_personal_contact_escalates_before_message_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_settings(monkeypatch, personal_contacts="6281")
    service = WhatsAppTriageService()

    decision, reason = await service.should_escalate("+6281", "berapa harga KITAS?")

    assert decision == TriageDecision.ESCALATE_PERSONAL
    assert reason == "personal_contact"


@pytest.mark.asyncio
async def test_explicit_human_request_escalates(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    decision, reason = await service.should_escalate("6281", "I want to talk to Zero")

    assert decision == TriageDecision.ESCALATE_REQUEST
    assert reason == "explicit_request"


@pytest.mark.asyncio
async def test_personal_context_escalates(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    decision, reason = await service.should_escalate("6281", "ci vediamo a cena?")

    assert decision == TriageDecision.ESCALATE_CONTEXT
    assert reason == "personal_context"


@pytest.mark.asyncio
async def test_business_query_is_handled_by_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    decision, reason = await service.should_escalate("6281", "quanto costa il KITAS?")

    assert decision == TriageDecision.BOT_CAN_HANDLE
    assert reason == "business_query"


@pytest.mark.asyncio
async def test_greeting_only_stays_on_ai_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    decision, reason = await service.should_escalate("6281", "ciao")

    assert decision == TriageDecision.BOT_CAN_HANDLE
    assert reason == "greeting_only"


@pytest.mark.asyncio
async def test_general_query_defaults_to_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    decision, reason = await service.should_escalate("6281", "Can you help me tomorrow?")

    assert decision == TriageDecision.BOT_CAN_HANDLE
    assert reason == "general_query"


def test_escalation_messages_match_decision_type() -> None:
    service = WhatsAppTriageService.__new__(WhatsAppTriageService)

    assert "Luca" in service.get_escalation_message(
        TriageDecision.ESCALATE_PERSONAL,
        sender_name="Luca",
    )
    assert "breve" in service.get_escalation_message(TriageDecision.ESCALATE_REQUEST)
    assert "secondo" in service.get_escalation_message(TriageDecision.ESCALATE_CONTEXT)
    assert service.get_escalation_message(TriageDecision.BOT_CAN_HANDLE) == "Un attimo..."


def test_welcome_message_mentions_zantara_and_sender() -> None:
    service = WhatsAppTriageService.__new__(WhatsAppTriageService)

    message = service.get_welcome_message("Luca")

    assert "Hi Luca!" in message
    assert "Zantara" in message
    assert "KITAS" in message
