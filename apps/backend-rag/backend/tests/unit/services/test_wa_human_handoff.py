"""Guilt AND innocence for the human-handoff detector + notification (B2.5-2).

The defect this cures: a client asking to speak to a person is the highest-
intent message the bot ever receives, and today nothing detects it — the
message falls through to retrieval, abstains, and reaches nobody.

The defect a careless cure would introduce: copying `wa_identity`'s domain
veto here would swallow exactly the highest-value case — a client naming
their case WHILE asking for a human ("voglio parlare con una persona
riguardo alla mia PT PMA") must match, not be vetoed. There is no veto here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.integrations import human_escalation_notifier
from backend.services.integrations.wa_human_handoff import (
    HumanRequestTurn,
    _resolve_assignee,
    match_human_request,
    notify_human_handoff,
)
from backend.services.integrations.wa_identity import match_identity_question


class TestGuilt:
    """A genuine human-handoff request MUST match, in its language."""

    @pytest.mark.parametrize(
        "message",
        [
            # The mandate's own examples.
            "voglio parlare con una persona riguardo alla mia PT PMA",
            "saya mau bicara dengan konsultan soal KITAS saya",
            # Rest of the phrase table, one per core phrase.
            "vorrei parlare con un umano",
            "posso parlare con un operatore",
            "parlare con un consulente per favore",
            "parlare con qualcuno del team",
            "can I talk to a human",
            "I want to talk to a person",
            "please speak to a human",
            "speak to a person now",
            "talk to an agent",
            "can I speak to someone",
            "talk to a consultant",
            "mau bicara dengan manusia",
            "bisa bicara dengan orang",
            "mau ngobrol dengan orang",
            "mau bicara dengan admin",
            "хочу поговорить с человеком",
            "поговорить с консультантом пожалуйста",
            "поговорить с оператором",
            "хочу поговорити з людиною",
            "поговорити з консультантом",
            "поговорити з оператором будь ласка",
        ],
    )
    def test_matches_and_returns_a_confirmation(self, message: str) -> None:
        result = match_human_request(message)
        assert result is not None
        assert isinstance(result, HumanRequestTurn)
        assert result.text


class TestInnocence:
    """A message that does NOT ask to reach a human must fall through."""

    @pytest.mark.parametrize(
        "message",
        [
            # Third-person WHO question about staff — asking WHO, not FOR one.
            "chi è il notaio che usate?",
            "siapa konsultan yang menangani kasus saya?",
            # The bot's own nature — wa_identity's vocabulary, not this one.
            "sei un umano?",
            "are you human?",
            "apakah kamu manusia",
            # Ordinary case questions with no request for a person.
            "quanto costa una PT PMA?",
            "berapa harga KITAS?",
            "what documents do I need for NPWP?",
            "",
            None,
        ],
    )
    def test_does_not_match(self, message: str | None) -> None:
        assert match_human_request(message) is None

    def test_third_person_who_question_decision_documented(self) -> None:
        """Deliberate call: "siapa konsultan yang menangani kasus saya?" asks
        WHO handles the case (information), not to BE CONNECTED to someone.
        Judged as innocence — a WHO-question is answered by retrieval (the
        consultant's name, if known), not by firing a human notification."""
        assert match_human_request("siapa konsultan yang menangani kasus saya?") is None


class TestTwoAuthorities:
    """A message can carry both an identity phrase and a human-request phrase.

    Both authorities must not both claim it silently — this test only proves
    BOTH modules independently match; the ORDER that decides which one wins
    is pinned at the call site (test_wa_codex_leg.py), not here.
    """

    @pytest.mark.parametrize(
        "message",
        [
            "are you human or can I talk to a person",
            "sei un umano o posso parlare con una persona?",
        ],
    )
    def test_both_authorities_independently_match(self, message: str) -> None:
        assert match_identity_question(message) is not None
        assert match_human_request(message) is not None


class TestNotifyHumanHandoff:
    """Half B: resolve the consultant, send the email, dedup, isolate failure."""

    def setup_method(self) -> None:
        # The dedup TTL map is module-global and shared with
        # human_escalation_notifier's own callers — clear it so tests never
        # see another test's window.
        human_escalation_notifier._recent_escalations.clear()

    @pytest.mark.asyncio
    async def test_resolves_assignee_and_sends_to_them(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pool = object()
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(4242, "consultant@balizero.com")),
        )
        sent = AsyncMock()
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        result = await notify_human_handoff(
            pool, thread_id=99, counterpart_phone="628111222333", language="id"
        )

        assert result is True
        sent.assert_awaited_once()
        kwargs = sent.await_args.kwargs
        assert kwargs["to"] == "consultant@balizero.com"
        assert kwargs["email_type"] == "wa_human_handoff"
        assert kwargs["pool"] is pool
        assert kwargs["client_id"] == 4242
        # PII: the phone number never appears in subject or body.
        assert "628111222333" not in kwargs["subject"]
        assert "628111222333" not in kwargs["body"]
        assert "99" in kwargs["body"]  # thread_id, not PII

    @pytest.mark.asyncio
    async def test_falls_back_to_zero_when_no_assignee_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock()
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        result = await notify_human_handoff(
            object(), thread_id=1, counterpart_phone=None, language="en"
        )

        assert result is True
        assert sent.await_args.kwargs["to"] == "zero@balizero.com"
        assert sent.await_args.kwargs["client_id"] is None

    @pytest.mark.asyncio
    async def test_second_request_inside_window_sends_no_second_email(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock()
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        first = await notify_human_handoff(
            object(), thread_id=55, counterpart_phone=None, language="en"
        )
        second = await notify_human_handoff(
            object(), thread_id=55, counterpart_phone=None, language="en"
        )

        assert first is True
        assert second is False
        sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedup_window_is_per_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock()
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        a = await notify_human_handoff(object(), thread_id=1, counterpart_phone=None, language="en")
        b = await notify_human_handoff(object(), thread_id=2, counterpart_phone=None, language="en")

        assert a is True
        assert b is True
        assert sent.await_count == 2

    @pytest.mark.asyncio
    async def test_email_raise_propagates_for_the_caller_to_isolate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`notify_human_handoff` does not itself swallow a send failure —
        the call site (`wa_codex_leg.py`) is the layer that guarantees the
        client's confirmation survives an email failure; see
        test_wa_codex_leg.py's failure-isolation test."""
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email",
            AsyncMock(side_effect=RuntimeError("brevo down")),
        )

        with pytest.raises(RuntimeError):
            await notify_human_handoff(
                object(), thread_id=7, counterpart_phone=None, language="it"
            )


class TestResolveAssignee:
    @pytest.mark.asyncio
    async def test_no_phone_resolves_to_nothing(self) -> None:
        assert await _resolve_assignee(object(), None) == (None, None)

    @pytest.mark.asyncio
    async def test_db_error_falls_back_to_nothing(self) -> None:
        class _BoomConn:
            async def fetchrow(self, *args: object) -> None:
                raise RuntimeError("connection reset")

        class _BoomPool:
            def acquire(self) -> object:
                class _CM:
                    async def __aenter__(self) -> _BoomConn:
                        return _BoomConn()

                    async def __aexit__(self, *exc: object) -> bool:
                        return False

                return _CM()

        assert await _resolve_assignee(_BoomPool(), "628111") == (None, None)
