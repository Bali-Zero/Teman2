from __future__ import annotations

import logging
import re
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


# ── F7: raw phone must NEVER appear in a log record (guilt/innocence) ──────
#
# Every branch of should_escalate() logs the phone at least once. Guilt +
# innocence per cicatrix-superscar.md family #3, same discipline as the
# reference fix in messaging_identity_service.py.

_TRIAGE_LOGGER_NAME = "backend.services.integrations.whatsapp_triage_service"
_NON_DIGITS_RE = re.compile(r"\D+")

# Obviously-synthetic — never a shape mistakable for a real client's number.
_SYNTHETIC_PHONE = "6285556667778"


def _digits_only(text: str) -> str:
    return _NON_DIGITS_RE.sub("", text)


def _all_log_text(records: list[logging.LogRecord]) -> str:
    return "\n".join(r.getMessage() for r in records)


@pytest.mark.asyncio
async def test_whitelist_contact_escalation_never_logs_raw_phone(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_settings(monkeypatch, personal_contacts=_SYNTHETIC_PHONE)
    service = WhatsAppTriageService()

    with caplog.at_level(logging.INFO, logger=_TRIAGE_LOGGER_NAME):
        decision, reason = await service.should_escalate(_SYNTHETIC_PHONE, "berapa harga KITAS?")

    assert decision == TriageDecision.ESCALATE_PERSONAL
    text = _all_log_text(caplog.records)
    assert _SYNTHETIC_PHONE not in text
    assert _SYNTHETIC_PHONE not in _digits_only(text)
    assert "id:" in text


@pytest.mark.asyncio
async def test_general_query_default_never_logs_raw_phone(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    with caplog.at_level(logging.INFO, logger=_TRIAGE_LOGGER_NAME):
        decision, reason = await service.should_escalate(
            _SYNTHETIC_PHONE, "Can you help me tomorrow?"
        )

    assert decision == TriageDecision.BOT_CAN_HANDLE
    assert reason == "general_query"
    text = _all_log_text(caplog.records)
    assert _SYNTHETIC_PHONE not in text
    assert _SYNTHETIC_PHONE not in _digits_only(text)
    assert "id:" in text


@pytest.mark.asyncio
async def test_same_phone_yields_same_digest_across_two_calls(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_settings(monkeypatch)
    service = WhatsAppTriageService()

    with caplog.at_level(logging.INFO, logger=_TRIAGE_LOGGER_NAME):
        await service.should_escalate(_SYNTHETIC_PHONE, "hello")
        first_text = _all_log_text(caplog.records)
        caplog.clear()

        await service.should_escalate(_SYNTHETIC_PHONE, "hello again")
        second_text = _all_log_text(caplog.records)

    first_digest = next(tok for tok in first_text.split() if "id:" in tok)
    second_digest = next(tok for tok in second_text.split() if "id:" in tok)
    assert first_digest == second_digest
