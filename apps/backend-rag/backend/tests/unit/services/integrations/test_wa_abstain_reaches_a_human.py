"""An abstain on the WhatsApp Meta line must reach the client AND a human.

Before 2026-08-11 `generate_bot_reply` raised on abstain; the worker burned five
retries and the client got nothing. Two things made that worse than a plain gap:

* the message being discarded was, on the cases probed live, the persona telling
  the client "the team has been notified and will reach out within one business
  hour" — a promise the prompt's ESCALATION section teaches and which nothing on
  this path performed;
* so un-silencing the path WITHOUT wiring the notification would have converted
  a silence into a lie. That is why every test here asserts BOTH halves.

What these tests do NOT prove, said plainly so nobody reads coverage into them:
Telegram accepting a message is not a human reading it, owning it, or replying.
The copy is written to assert only the flagging (see `abstain_flagged` in
`_reasoning_stubs.py`), and `test_the_flagged_copy_promises_no_reply` is what
keeps a future edit from quietly promoting it to a promise.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.rag.agentic._reasoning_stubs import (
    PROTOCOL_LANGUAGES,
    get_localized_stub,
)

BOT = "backend.services.integrations.wa_inbox_bot"


class _Resp:
    """Minimal stand-in for the httpx response the bot reads."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _thread(thread_id: int = 42, phone: str = "621234567890") -> dict:
    return {"thread_id": thread_id, "counterpart_phone": phone}


async def _run(payload: dict, *, query: str = "What documents do I need for a KITAS?"):
    """Drive generate_bot_reply against a canned RAG payload.

    Returns (reply_or_exception, notifier_mock).
    """
    from backend.services.integrations import wa_inbox_bot

    notifier = AsyncMock(return_value=True)
    client = AsyncMock()
    client.post = AsyncMock(return_value=_Resp(payload))

    with (
        patch(f"{BOT}.is_bot_autoreply_enabled", return_value=True),
        patch(f"{BOT}._load_thread_context", AsyncMock(return_value=(query, []))),
        patch(f"{BOT}._get_rag_client", AsyncMock(return_value=client)),
        patch(f"{BOT}.notify_human_telegram", notifier),
    ):
        reply = await wa_inbox_bot.generate_bot_reply(None, _thread())
    return reply, notifier


@pytest.mark.asyncio
async def test_abstain_answers_the_client_and_notifies_a_human() -> None:
    """GUILT: both halves happen, and no RuntimeError escapes."""
    reply, notifier = await _run(
        {"abstain": True, "abstain_reason": "no_relevant_context", "answer": "…"}
    )

    notifier.assert_awaited_once()
    kwargs = notifier.await_args.kwargs
    assert kwargs["reason"] == "rag_abstain"
    assert kwargs["thread_ref"] == "42"
    assert reply == get_localized_stub("abstain_flagged", "ENGLISH")


@pytest.mark.asyncio
async def test_the_client_message_is_not_shipped_to_telegram() -> None:
    """PII: the new trigger withholds the body — it does not widen the payload.

    The router's own call still sends the body; that is unchanged and lives in
    its own test. This asserts only that the trigger added here passes None,
    because routing a NEW trigger through the cleartext payload is exactly the
    §14 widening the design refused.
    """
    secret = "my passport number is very much not for telegram"
    _, notifier = await _run(
        {"abstain": True, "abstain_reason": "no_relevant_context"}, query=secret
    )

    kwargs = notifier.await_args.kwargs
    assert kwargs["message_text"] is None
    assert secret not in repr(notifier.await_args)


@pytest.mark.asyncio
async def test_a_failed_notification_downgrades_the_copy() -> None:
    """The promise tracks reality: no send accepted → the stub claims nothing.

    This is the whole reason `notify_human_telegram` returns a bool. If it ever
    stops mattering, this test goes red rather than the client being told a
    colleague was alerted when none was.
    """
    from backend.services.integrations import wa_inbox_bot

    notifier = AsyncMock(return_value=False)
    client = AsyncMock()
    client.post = AsyncMock(return_value=_Resp({"abstain": True, "abstain_reason": "x"}))

    with (
        patch(f"{BOT}.is_bot_autoreply_enabled", return_value=True),
        patch(f"{BOT}._load_thread_context", AsyncMock(return_value=("hello?", []))),
        patch(f"{BOT}._get_rag_client", AsyncMock(return_value=client)),
        patch(f"{BOT}.notify_human_telegram", notifier),
    ):
        reply = await wa_inbox_bot.generate_bot_reply(None, _thread())

    assert reply == get_localized_stub("abstain", "ENGLISH")
    assert reply != get_localized_stub("abstain_flagged", "ENGLISH")


@pytest.mark.asyncio
async def test_the_refusal_follows_the_asker_language() -> None:
    """An Italian client reads an Italian refusal, not an English one."""
    reply, _ = await _run(
        {"abstain": True, "abstain_reason": "no_relevant_context"},
        query="Quanto costa un KITAS investor? Non ho capito bene.",
    )
    assert reply == get_localized_stub("abstain_flagged", "ITALIAN")


@pytest.mark.asyncio
async def test_a_normal_answer_notifies_nobody() -> None:
    """INNOCENCE: the ordinary path is untouched — answer through, no alert."""
    reply, notifier = await _run({"abstain": False, "answer": "A KITAS needs X, Y, Z."})

    notifier.assert_not_awaited()
    assert "KITAS needs X, Y, Z" in reply


@pytest.mark.asyncio
async def test_an_empty_answer_still_raises() -> None:
    """INNOCENCE: the retry ladder survives for the failures it was built for.

    Only the ABSTAIN branch changed. An empty answer is a broken generation, not
    a refusal, and must still park the row for retry rather than send a stub.
    """
    with pytest.raises(RuntimeError):
        await _run({"abstain": False, "answer": "   "})


@pytest.mark.asyncio
async def test_the_flagged_copy_promises_no_reply() -> None:
    """The copy may assert the flagging and nothing downstream of it.

    A Telegram 200 proves Telegram accepted a message — not that a person is on
    shift, has read it, or owns it. The prompt's escalation example does promise
    an hour; that SLA is a staffing commitment, and it must not migrate here.
    Asserted per language so a translation cannot smuggle it back in one locale.
    """
    forbidden = (
        "business hour",
        "ora lavorativa",
        "jam kerja",
        "will reply",
        "ti rispond",
        "akan menghubungi",
        "свяжется",
        "зв'яжеться",
    )
    for language in PROTOCOL_LANGUAGES:
        text = get_localized_stub("abstain_flagged", language).lower()
        assert text, f"{language} has no abstain_flagged copy"
        offenders = [f for f in forbidden if f.lower() in text]
        assert not offenders, f"{language} promises a reply: {offenders}"


@pytest.mark.asyncio
async def test_the_escalate_marker_notifies_and_leaves_the_answer_intact() -> None:
    """The marker path: additive escalation, byte-identical answer.

    INERT in production today — no prompt asks the model to emit the token
    (0/14 on a live probe, and the only occurrences in the backend are the two
    places that look for it). This test injects it, so it verifies the READER,
    never the emitter. Arming the emitter is a separate change with its own
    gate: the prompt is shared, and blog/web consumers do not strip the token.
    """
    reply, notifier = await _run(
        {"abstain": False, "answer": "Here is your answer.[ESCALATE]"}
    )

    notifier.assert_awaited_once()
    assert notifier.await_args.kwargs["reason"] == "persona_escalate_marker"
    assert reply == "Here is your answer."
    assert "[ESCALATE]" not in reply
