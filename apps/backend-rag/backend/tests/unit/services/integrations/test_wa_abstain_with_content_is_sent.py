"""An abstain that carries a real answer is sent, not thrown away.

Measured 2026-08-11 across 16 cold questions in 8 languages: **7 came back
`abstain=true`, and 3 of those carried a complete on-topic answer** — both German
runs and one Indonesian one opened straight into the real PT PMA steps. The
consumer discarded all 7, so the client got silence with the answer already
written.

This does NOT touch the abstain gates, and no test here asserts anything about
them. Their generation-vs-label divergence is panel-ruled and tripwire-tested
(CLAUDE.md §9): the label gate MARKS confidence, it does not decide whether
advice may exist. Reading the flag as "discard the text" was this consumer's
error. What is asserted is only what this module does with a payload it is given.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.integrations import wa_inbox_bot
from backend.services.integrations.wa_inbox_bot import (
    _ABSTAIN_MIN_SENDABLE_CHARS,
    _abstain_answer_worth_sending,
)
from backend.services.rag.agentic._reasoning_stubs import (
    PROTOCOL_LANGUAGES,
    get_localized_stub,
)

BOT = "backend.services.integrations.wa_inbox_bot"

# Shaped like the real thing: the measured German abstain opened directly into
# the steps and ran ~1,900 characters.
REAL_ANSWER = (
    "Um eine PT PMA Firma in Indonesien zu gründen, sind die folgenden Schritte "
    "erforderlich. Zuerst wählen Sie den Geschäftssektor und prüfen die KBLI-Codes. "
    "Danach reservieren Sie den Firmennamen und lassen die Gründungsurkunde beim "
    "Notar beurkunden. Anschließend beantragen Sie die NIB über das OSS-System. "
) * 3


def _payload(answer: str, reason: str = "low_evidence") -> dict:
    return {"abstain": True, "abstain_reason": reason, "answer": answer}


# ── the helper: what counts as worth sending ────────────────────────────────


def test_a_substantive_answer_survives() -> None:
    """GUILT: the shape that was being discarded."""
    out = _abstain_answer_worth_sending(_payload(REAL_ANSWER))
    assert out, "a full answer inside an abstain must be sendable"
    assert "PT PMA" in out


def test_a_short_refusal_is_not_mistaken_for_an_answer() -> None:
    """INNOCENCE: the residue of a refusal must still yield the stub.

    "Je suis prêt pour votre prochaine question." is verbatim from the live
    probe — 43 characters, zero content, returned to a real question.
    """
    assert _abstain_answer_worth_sending(_payload("Je suis prêt pour votre prochaine question.")) == ""
    assert _abstain_answer_worth_sending(_payload("")) == ""
    assert _abstain_answer_worth_sending(_payload("   ")) == ""


def test_a_payload_that_is_only_scaffold_is_not_rescued_by_its_raw_length() -> None:
    """The length check runs AFTER cleaning, not before.

    A KG workflow block is long. If the floor were applied only to the raw text,
    a payload that is mostly internal diagnostics would clear it and then be sent
    with whatever scrap survives the strip.

    The residue here is deliberately SHORT BUT NOT EMPTY. A first version used a
    pure-scaffold payload and the mutation survived: with the post-clean check
    deleted the function still returned "" — not because the guard worked but
    because `cleaned.strip()` was empty anyway. The test passed for a reason that
    had nothing to do with what it claimed to pin.
    """
    residue = "Ok, ecco."  # 9 chars — nobody's answer
    scaffold = (
        residue
        + "\n\n## SUGGESTED WORKFLOW (from kg, confidence: 70%)\n"
        + ("1. Do the thing.\n" * 20)
        + "IMPORTANT: This is a suggested workflow. "
        "Always verify current requirements with the user."
    )
    assert len(scaffold) > _ABSTAIN_MIN_SENDABLE_CHARS
    assert len(residue) < _ABSTAIN_MIN_SENDABLE_CHARS
    assert _abstain_answer_worth_sending(_payload(scaffold)) == ""


def test_what_it_returns_is_what_gets_sent() -> None:
    """It returns the CLEANED text, so the caller cannot ship something else.

    A version that returned a bool and let the caller re-derive the text is how
    two code paths end up disagreeing about the same message.
    """
    answer = (
        REAL_ANSWER
        + "\n\n## SUGGESTED WORKFLOW (from kg, confidence: 70%)\n1. Step.\n"
        "IMPORTANT: This is a suggested workflow. "
        "Always verify current requirements with the user."
    )
    out = _abstain_answer_worth_sending(_payload(answer))
    assert "SUGGESTED WORKFLOW" not in out
    assert "PT PMA" in out


# ── the copy ────────────────────────────────────────────────────────────────


def test_every_language_has_a_note_and_none_promises_a_reply() -> None:
    """The note may say the sources are unverified. It may not promise a person.

    Telegram accepting a message is not a colleague answering — the same rule
    `abstain_flagged` lives under.
    """
    forbidden = (
        "will reply", "will answer", "within", "shortly", "asap",
        "ti risponder", "risponderà", "entro",
        "akan membalas", "segera",
        "ответит", "в течение",
        "відповість", "протягом",
    )
    for language in PROTOCOL_LANGUAGES:
        note = get_localized_stub("low_confidence_note", language)
        assert note.strip(), f"{language} has no low_confidence_note"
        # the generic unknown-key fallback is itself a refusal — catching it here
        # is what stops a missing translation from apologising to the client
        assert "cannot fulfill this request" not in note, f"{language} fell back to the refusal stub"
        offenders = [f for f in forbidden if f in note.lower()]
        assert not offenders, f"{language} promises a reply: {offenders}"


# ── end to end through generate_bot_reply ───────────────────────────────────
#
# The RAG hop is faked at the SAME seam the existing suite uses
# (`_get_rag_client`), not at an invented one. A first draft patched a
# `_call_rag` that does not exist; `patch` said so immediately, which is the
# cheap version of the lesson — a fake placed at a boundary the code does not
# have proves nothing about the code.


def _mock_rag(monkeypatch, response_json: dict) -> None:
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=response_json)

    async def _post(url: str, json: dict):
        return resp

    client = MagicMock()
    client.post = AsyncMock(side_effect=_post)

    async def _get_client():
        return client

    monkeypatch.setattr(wa_inbox_bot, "_get_rag_client", _get_client)


_ROWS_NEWEST_FIRST = [
    {"direction": "inbound", "sender_role": "customer", "body": "Was brauche ich für eine PT PMA?"},
]


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, *_a, **_k):
        return self._rows

    async def fetchrow(self, *_a, **_k):
        return self._rows[0] if self._rows else None

    async def execute(self, *_a, **_k):
        return "OK"


class _Pool:
    def __init__(self, rows):
        self._rows = rows

    def acquire(self):
        rows = self._rows

        @asynccontextmanager
        async def _cm():
            yield _Conn(rows)

        return _cm()


def _thread(thread_id: int = 7, phone: str = "62811") -> dict:
    return {"thread_id": thread_id, "counterpart_phone": phone}


@pytest.mark.asyncio
async def test_generate_bot_reply_sends_the_answer_with_the_note(monkeypatch) -> None:
    """GUILT end to end: the client receives the answer, not a refusal."""
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(monkeypatch, _payload(REAL_ANSWER))

    with patch(f"{BOT}.notify_human_telegram", new=AsyncMock(return_value=True)):
        answer = await wa_inbox_bot.generate_bot_reply(_Pool(_ROWS_NEWEST_FIRST), _thread())

    assert "PT PMA" in answer, "the answer itself must reach the client"
    assert "_(" in answer, "and it must carry the caution note"


@pytest.mark.asyncio
async def test_generate_bot_reply_still_stubs_when_there_is_no_answer(monkeypatch) -> None:
    """INNOCENCE: a contentless abstain keeps today's behaviour — stub + notify."""
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(monkeypatch, _payload("Je suis prêt pour votre prochaine question."))
    notifier = AsyncMock(return_value=True)

    with patch(f"{BOT}.notify_human_telegram", new=notifier):
        answer = await wa_inbox_bot.generate_bot_reply(_Pool(_ROWS_NEWEST_FIRST), _thread())

    assert "PT PMA" not in answer
    assert notifier.await_count == 1, "a human is still told when we send only a stub"
