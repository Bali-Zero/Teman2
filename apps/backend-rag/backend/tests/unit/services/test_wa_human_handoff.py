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

from backend.app.routers.crm_notifications import BELL_ALERT_TYPES
from backend.services.integrations import human_escalation_notifier, wa_human_handoff
from backend.services.integrations.wa_human_handoff import (
    ALERT_TYPE,
    HumanRequestTurn,
    _resolve_assignee,
    match_human_request,
    notify_human_handoff,
)
from backend.services.integrations.wa_identity import match_identity_question


class _RecordingConn:
    """Captures every execute() so a test can assert on the real SQL + args."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple] = []
        self._fail = fail

    async def execute(self, sql: str, *args: object) -> None:
        if self._fail:
            raise RuntimeError("deadlock detected")
        self.calls.append((sql, args))


class _RecordingPool:
    def __init__(self, conn: _RecordingConn) -> None:
        self.conn = conn

    def acquire(self) -> object:
        conn = self.conn

        class _CM:
            async def __aenter__(self) -> _RecordingConn:
                return conn

            async def __aexit__(self, *exc: object) -> bool:
                return False

        return _CM()


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
        wa_human_handoff._recent_failed_attempts.clear()

    @pytest.mark.asyncio
    async def test_resolves_assignee_and_sends_to_them(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pool = object()
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(4242, "consultant@balizero.com")),
        )
        sent = AsyncMock(return_value=True)
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
        sent = AsyncMock(return_value=True)
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
        """S1 (spec_Fa_r3.md, round 3): the dedup-suppressed second call is
        True, not False — a colleague WAS reached, just not by THIS call.
        `sent.assert_awaited_once()` is the assertion that actually proves
        "no second email": the return value alone cannot."""
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock(return_value=True)
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
        assert second is True
        sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedup_window_is_per_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        a = await notify_human_handoff(object(), thread_id=1, counterpart_phone=None, language="en")
        b = await notify_human_handoff(object(), thread_id=2, counterpart_phone=None, language="en")

        assert a is True
        assert b is True
        assert sent.await_count == 2

    @pytest.mark.asyncio
    async def test_email_raise_is_caught_and_counted_as_a_failed_send(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`notify_human_handoff`'s own contract is an unconditional "never
        raises" (see docstring). The real `send_internal_email` already
        never raises by default (`raise_on_failure=False`); this simulates
        an unexpected bug that bypasses that anyway, and pins that it is
        still caught here — logged by TYPE only — and counted as a failed
        send rather than propagated. The call site (`wa_codex_leg.py`)
        keeps its own belt-and-suspenders try/except as a second,
        independent layer; see test_wa_codex_leg.py's failure-isolation
        test."""
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email",
            AsyncMock(side_effect=RuntimeError("brevo down")),
        )

        result = await notify_human_handoff(
            object(), thread_id=7, counterpart_phone=None, language="it"
        )

        assert result is False


class TestNotifyHumanHandoffDeliveryTruth:
    """The return value must mean DELIVERED, not merely ATTEMPTED.

    Before 2026-09-25, `send_internal_email`'s `raise_on_failure=False`
    swallowed a Brevo failure silently and `notify_human_handoff` still
    returned True and recorded dedup — an unknown client with a broken
    email transport produced NO in-app alert (client_id is None), NO email,
    an audit row logged `failed`, and a caller that believed the True could
    tell a client "a colleague was alerted" when nobody was. Dedup then
    suppressed the retry that could have reached someone on the client's
    next message.
    """

    def setup_method(self) -> None:
        human_escalation_notifier._recent_escalations.clear()
        wa_human_handoff._recent_failed_attempts.clear()

    @pytest.mark.asyncio
    async def test_guilt_both_channels_fail_returns_false_and_throttles_repeats(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown client (no in-app row possible) + email transport fails
        silently (mirrors real `send_internal_email(raise_on_failure=False)`
        returning False, never raising) -> False. No SUCCESS dedup is
        recorded (nobody was told) — but the SEPARATE failed-attempt
        cooldown throttles an immediate repeat on the same thread, so a
        burst does not become a storm of attempts. A retry after the
        cooldown window elapses still gets a real attempt."""
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        first = await notify_human_handoff(
            object(), thread_id=321, counterpart_phone="628111222333", language="en"
        )
        second = await notify_human_handoff(
            object(), thread_id=321, counterpart_phone="628111222333", language="en"
        )

        assert first is False
        assert second is False
        # The second call was throttled by the cooldown, not a second real
        # attempt.
        assert sent.await_count == 1

        # Simulate the 5-minute cooldown window having elapsed.
        dedup_key = "human_handoff:321"
        wa_human_handoff._recent_failed_attempts[dedup_key] -= (
            wa_human_handoff._FAILED_ATTEMPT_COOLDOWN_S + 1
        )

        third = await notify_human_handoff(
            object(), thread_id=321, counterpart_phone="628111222333", language="en"
        )

        assert third is False
        assert sent.await_count == 2

    @pytest.mark.asyncio
    async def test_innocence_email_delivered_returns_true_and_records_dedup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        first = await notify_human_handoff(
            object(), thread_id=322, counterpart_phone=None, language="en"
        )
        second = await notify_human_handoff(
            object(), thread_id=322, counterpart_phone=None, language="en"
        )

        assert first is True
        # Dedup IS recorded on a real delivery: the second call is suppressed
        # (never attempts a second send) but is STILL True — a colleague was
        # reached, by the first call (S1, round 3).
        assert second is True
        sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_innocence_inapp_delivered_email_failed_still_returns_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Known client: the in-app bell row is written even though the
        email transport fails — one delivered channel is enough to be
        truthfully True, and SUCCESS dedup still applies.

        Mutation killer for `if delivered:` -> `if email_sent:` (round-2
        review, 2026-09-25: the previous version of this test did not
        actually kill that mutation — under the mutation, the first call's
        `delivered` return value is untouched (the mutation only changes
        which bookkeeping branch runs), and the FAILED-attempt cooldown
        that branch wrongly sets makes the second call return False via
        `_recently_failed`, the same False `_already_escalated` would have
        given for a correctly-recorded success dedup — so the old
        `second is False` / `sent.assert_awaited_once()` pair could not
        tell the two apart). This version asserts the map state directly:
        under the mutation, `email_sent` is False, so the success-dedup map
        is never written and the assertion below fails BEFORE the second
        call even runs."""
        conn = _RecordingConn()
        pool = _RecordingPool(conn)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(4242, "consultant@balizero.com")),
        )
        sent = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        dedup_key = "human_handoff:323"
        first = await notify_human_handoff(
            pool, thread_id=323, counterpart_phone="628111222333", language="en"
        )

        assert first is True
        assert len(conn.calls) == 1
        # The success-dedup map, not just the return value: proves the
        # branch taken was `if delivered:` (in_app=True), not a mutated
        # `if email_sent:` (False) that would have skipped this write and
        # set the failed-attempt cooldown instead.
        assert dedup_key in human_escalation_notifier._recent_escalations
        assert dedup_key not in wa_human_handoff._recent_failed_attempts

        second = await notify_human_handoff(
            pool, thread_id=323, counterpart_phone="628111222333", language="en"
        )

        assert second is True
        assert len(conn.calls) == 1
        sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_innocence_a_swallowed_email_failure_never_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The real `send_internal_email` contract (default
        `raise_on_failure=False`) never raises on a transport failure — it
        returns False. `notify_human_handoff` must surface that as a plain
        False return, not an exception, regardless of whether the in-app
        leg also failed."""
        pool = _RecordingPool(_RecordingConn(fail=True))
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(4242, "consultant@balizero.com")),
        )
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email",
            AsyncMock(return_value=False),
        )

        result = await notify_human_handoff(
            pool, thread_id=324, counterpart_phone="628111222333", language="en"
        )

        assert result is False


class TestInAppAlert:
    """The kita bell half — where the team actually looks during the day."""

    def setup_method(self) -> None:
        human_escalation_notifier._recent_escalations.clear()
        wa_human_handoff._recent_failed_attempts.clear()

    def test_the_alert_type_is_on_the_bells_guest_list(self) -> None:
        """The row is written AND rendered.

        `notification_alerts` is read by /api/crm/notifications through a
        fixed allow-list of alert types. Writing a type absent from that
        list produces a row nobody sees — which, for a lead, is the same
        outcome as not writing it. This pins the pair by ENTITY (the two
        constants), not by grepping a string out of a SQL literal.
        """
        assert ALERT_TYPE in BELL_ALERT_TYPES

    @pytest.mark.asyncio
    async def test_known_client_gets_a_pending_bell_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conn = _RecordingConn()
        pool = _RecordingPool(conn)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(4242, "consultant@balizero.com")),
        )
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email",
            AsyncMock(return_value=True),
        )

        await notify_human_handoff(
            pool, thread_id=99, counterpart_phone="628111222333", language="id"
        )

        assert len(conn.calls) == 1
        sql, args = conn.calls[0]
        assert "notification_alerts" in sql
        # 'pending' is what the bell COUNTS — a 'sent' row shows no badge.
        assert "'pending'" in sql
        # The daily unique constraint would otherwise raise on a second ask.
        assert "ON CONFLICT" in sql
        assert args[0] == 4242
        assert args[1] == ALERT_TYPE
        # PII: neither the phone nor the client's own words reach the row.
        assert "628111222333" not in " ".join(str(a) for a in args)

    @pytest.mark.asyncio
    async def test_an_unknown_number_still_gets_the_email(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The newest lead is the one no client row matches yet.

        `notification_alerts.client_id` is NOT NULL with an FK to `clients`,
        so an unrecognised number CANNOT have an in-app row. The email is
        therefore unconditional — it is the only channel that lead has.
        """
        conn = _RecordingConn()
        pool = _RecordingPool(conn)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(None, None)),
        )
        sent = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        result = await notify_human_handoff(
            pool, thread_id=7, counterpart_phone="628999000111", language="en"
        )

        assert result is True
        assert conn.calls == []
        sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_failing_bell_insert_never_costs_the_email(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pool = _RecordingPool(_RecordingConn(fail=True))
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff._resolve_assignee",
            AsyncMock(return_value=(4242, "consultant@balizero.com")),
        )
        sent = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "backend.services.integrations.wa_human_handoff.send_internal_email", sent
        )

        result = await notify_human_handoff(
            pool, thread_id=8, counterpart_phone="628111222333", language="it"
        )

        assert result is True
        sent.assert_awaited_once()


class TestPresentationKeepsItsPromise:
    """Every "you can ask for a human" line must be a phrase that MATCHES.

    `wa_identity`'s presentation tells the client, in their own language,
    that they may ask to speak to a person. Until this slice nothing
    detected that ask, and the line was a promise no code kept. The pairing
    is only real if the exact wording the presentation suggests is wording
    `match_human_request` recognises — so this walks every presentation and
    requires the detector to find a request inside it.
    """

    @pytest.mark.parametrize("language", ["id", "en", "it", "ru", "uk"])
    def test_each_presentation_contains_a_phrase_the_detector_matches(
        self, language: str
    ) -> None:
        from backend.services.integrations.wa_identity import _IDENTITY_REPLIES

        presentation = _IDENTITY_REPLIES[language]
        # The handoff sentence is the last line of every presentation.
        offer = presentation.strip().splitlines()[-1]
        assert match_human_request(offer) is not None, (
            f"{language}: the presentation offers a human but the detector "
            f"does not recognise the wording it suggests — {offer!r}"
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
