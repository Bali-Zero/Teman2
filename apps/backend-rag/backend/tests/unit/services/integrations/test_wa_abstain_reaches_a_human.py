"""When the WhatsApp bot cannot answer, a human has to hear about it.

`whatsapp_chat.py` (the router) captures the persona's `[ESCALATE]` marker,
strips it, sends the answer and then calls `notify_human_telegram`.
`wa_inbox_bot.py` — the background service behind `wa_outbox_worker` — stripped
the same marker under a comment reading *"mirror whatsapp_chat.py"* and called
nothing. It mirrored the FORM and not the EFFECT. Verified on `origin/main`
before this change: **zero** telegram/notify references in the whole module.

Main already fixed what the CLIENT reads: an abstain no longer raises, it serves
`_safe_abstain_reply`. Nobody was told, though — measured over the whole history
of `meta_inbox_threads`, 28 threads, 26 with at least one failed outbox row, and
exactly 4 ever touched by a human. This wires the other half.

**What this change does NOT touch, on purpose:** the text the client receives.
Every branch below leaves `answer` exactly as main computes it. Whether an
abstain that carries a substantive answer should ship that answer with a caution
note instead of the refusal is a live product question (see the `/bot` corner) —
it is a client-facing safety call on tax and immigration advice, and it is not
smuggled in under a notification PR.

**Declared limit, so nobody reads reach into this:** Telegram accepting a
message is not a human reading it, owning it, or replying. And the
`[ESCALATE]` branch is INERT in production today — no prompt asks the model to
emit the token (0/14 on a live probe; the only occurrences in the backend are
the two places that look for it). The marker tests below inject it, so they
verify the READER, never the emitter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.rag.agentic._reasoning_stubs import get_localized_stub

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

    Returns (reply, notifier_mock).
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


class TestGuiltAHumanIsTold:
    @pytest.mark.asyncio
    async def test_an_abstain_notifies_a_human(self) -> None:
        reply, notifier = await _run(
            {"abstain": True, "abstain_reason": "no_relevant_context", "answer": "…"}
        )

        notifier.assert_awaited_once()
        kwargs = notifier.await_args.kwargs
        assert kwargs["reason"] == "rag_abstain"
        assert kwargs["thread_ref"] == "42"
        # Main's client-facing choice, unchanged by this PR.
        assert reply == get_localized_stub("abstain", "ENGLISH")

    @pytest.mark.asyncio
    async def test_the_escalate_marker_notifies_and_leaves_the_answer_intact(self) -> None:
        """The form/effect gap this PR exists to close.

        Byte-identical answer: escalating is additive, it never edits the reply.
        """
        reply, notifier = await _run(
            {"abstain": False, "answer": "Here is your answer.[ESCALATE]"}
        )

        notifier.assert_awaited_once()
        assert notifier.await_args.kwargs["reason"] == "persona_escalate_marker"
        assert reply == "Here is your answer."
        assert "[ESCALATE]" not in reply

    @pytest.mark.asyncio
    async def test_a_discarded_monologue_leak_notifies_a_human(self) -> None:
        """The client asked something real and got a refusal because the model
        leaked its scratchpad. That is precisely a thread a person should see."""
        reply, notifier = await _run(
            {
                "abstain": False,
                "answer": "internal_monologue The user is asking about PT PMA capital.",
            }
        )

        notifier.assert_awaited_once()
        assert notifier.await_args.kwargs["reason"] == "internal_monologue_leak"
        assert reply == get_localized_stub("abstain", "ENGLISH")

    @pytest.mark.asyncio
    async def test_a_workflow_only_payload_notifies_a_human(self) -> None:
        """The RAG returned nothing but KG scaffolding, so the client gets the
        refusal. This is the `FAIL_SILENCE` shape from the 25-question
        benchmark (Q20/Q21) — the emptiest possible answer to a real ask."""
        scaffold = (
            "## SUGGESTED WORKFLOW (from KG)\n"
            "1. Do a thing\n"
            "IMPORTANT: This is a suggested workflow. "
            "Always verify current requirements with the user."
        )
        reply, notifier = await _run({"abstain": False, "answer": scaffold})

        notifier.assert_awaited_once()
        assert notifier.await_args.kwargs["reason"] == "workflow_only_output"
        assert reply == get_localized_stub("abstain", "ENGLISH")

    @pytest.mark.asyncio
    async def test_the_reason_names_the_first_cause_not_the_last(self) -> None:
        """Two causes CAN hold at once, and the report must not depend on which
        check happens to run last.

        The pair has to be chosen carefully, and most candidates are vacuous:
        `abstain` is exclusive with the whole `else` branch, and a monologue
        leak REPLACES the answer, so neither can co-occur with anything after
        it. Marker + workflow-only is the one real pair — the marker is
        stripped, the scaffold survives that strip, and then strips to empty.
        Written with `abstain` first, this test passed for free.
        """
        marked_scaffold = (
            "[ESCALATE]## SUGGESTED WORKFLOW (from KG)\n"
            "1. Do a thing\n"
            "IMPORTANT: This is a suggested workflow. "
            "Always verify current requirements with the user."
        )
        _, notifier = await _run({"abstain": False, "answer": marked_scaffold})

        assert notifier.await_args.kwargs["reason"] == "persona_escalate_marker"


class TestPIIThePayloadIsNotWidened:
    @pytest.mark.asyncio
    async def test_the_client_message_is_not_shipped_to_telegram(self) -> None:
        """The router's own call still sends the body; that is unchanged and
        lives in its own test. This asserts only that the trigger added HERE
        passes None, because routing a new trigger through the cleartext
        payload is exactly the §14 widening the design refused.
        """
        secret = "my passport number is very much not for telegram"
        _, notifier = await _run(
            {"abstain": True, "abstain_reason": "no_relevant_context"}, query=secret
        )

        kwargs = notifier.await_args.kwargs
        assert kwargs["message_text"] is None
        assert secret not in repr(notifier.await_args)


class TestInnocenceTheOrdinaryPathIsUntouched:
    @pytest.mark.asyncio
    async def test_a_normal_answer_notifies_nobody(self) -> None:
        reply, notifier = await _run(
            {"abstain": False, "answer": "A KITAS needs X, Y, Z."}
        )

        notifier.assert_not_awaited()
        assert "KITAS needs X, Y, Z" in reply

    @pytest.mark.asyncio
    async def test_an_answer_merely_discussing_escalation_notifies_nobody(self) -> None:
        """Entity, not substring: the WORD is not the MARKER.

        A client asking how to escalate a case gets an answer about escalation.
        Only the literal bracketed token is the persona's signal.
        """
        reply, notifier = await _run(
            {
                "abstain": False,
                "answer": "To escalate a rejected KITAS you file an appeal.",
            }
        )

        notifier.assert_not_awaited()
        assert "escalate a rejected KITAS" in reply

    @pytest.mark.asyncio
    async def test_an_empty_answer_still_raises(self) -> None:
        """The retry ladder survives for the failures it was built for: an empty
        answer is a broken generation, not a refusal, and must still park the
        row rather than notify and send."""
        with pytest.raises(RuntimeError):
            await _run({"abstain": False, "answer": "   "})
