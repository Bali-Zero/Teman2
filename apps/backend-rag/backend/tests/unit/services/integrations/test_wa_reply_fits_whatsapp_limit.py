"""A reply too long for WhatsApp is cut at a boundary and says so.

WhatsApp Cloud API refuses a body over 4096 characters and
`whatsapp_service.send_message` enforces that with `text[:4096]` — a silent cut,
mid-word, with nothing telling the client anything was removed. Measured before
this change: 4 of 311 production bot replies were cut that way (worst 7521
chars), and a live probe got 5097 characters back for the single word "kitas".

Two things are asserted here and they are not the same thing:

* the OUTPUT fits and is marked — the client-facing contract;
* the chunker's own docstring promise ("each within max_length") is now TRUE —
  it was not, and the cure above is built on it, so it gets its own test rather
  than being taken on faith.

What these tests do NOT claim: that the client receives the whole answer. They
do not, and the copy deliberately never says they will — nothing retains the
remainder, so "ask me to continue" would be a promise this path cannot keep.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services.integrations.wa_inbox_bot import (
    _WHATSAPP_HARD_SEND_LIMIT,
    _fit_to_whatsapp_limit,
)
from backend.services.rag.agentic._reasoning_stubs import (
    PROTOCOL_LANGUAGES,
    get_localized_stub,
)
from backend.utils.message_chunker import chunk_message

BOT = "backend.services.integrations.wa_inbox_bot"


def _long_paragraphs(total: int) -> str:
    """Realistic shape: many paragraphs, together longer than the limit."""
    para = ("Setting up a PT PMA requires several documents and steps. " * 6).strip()
    out = []
    while len("\n\n".join(out)) < total:
        out.append(para)
    return "\n\n".join(out)


def test_an_over_limit_reply_comes_back_within_the_limit_and_marked() -> None:
    """GUILT: the whole point — it fits, and the client is told it was shortened."""
    answer = _long_paragraphs(9000)
    assert len(answer) > _WHATSAPP_HARD_SEND_LIMIT

    out = _fit_to_whatsapp_limit(answer, "ENGLISH")

    assert len(out) <= _WHATSAPP_HARD_SEND_LIMIT
    assert out.endswith(get_localized_stub("truncated_tail", "ENGLISH"))
    assert out.startswith(answer[:50])


def test_a_reply_that_already_fits_is_returned_untouched() -> None:
    """INNOCENCE: the ordinary reply — the overwhelming majority — is not rewritten."""
    answer = "A KITAS needs a sponsor, a passport valid 18 months, and a photo."
    assert _fit_to_whatsapp_limit(answer, "ENGLISH") == answer


def test_the_cut_does_not_sever_a_word() -> None:
    """A boundary cut is the difference between this and `text[:4096]`."""
    answer = _long_paragraphs(9000)
    out = _fit_to_whatsapp_limit(answer, "ENGLISH")
    body = out[: -len(get_localized_stub("truncated_tail", "ENGLISH"))]
    # The kept text must end exactly where the source has a boundary, so the
    # last kept character is followed in the ORIGINAL by whitespace or nothing.
    nxt = answer[len(body) : len(body) + 1]
    assert nxt == "" or nxt.isspace(), f"cut mid-word, next char was {nxt!r}"


def test_one_enormous_line_with_no_newlines_still_fits() -> None:
    """The shape the old chunker let through whole — an LLM paragraph.

    `chunk_message` split on `\\n\\n` then `\\n`; text containing neither came
    back as ONE oversized chunk while the docstring promised the opposite. This
    is the case the cure depends on, so it is pinned at BOTH levels.
    """
    one_line = "word " * 2000  # 10,000 chars, no newline anywhere
    assert "\n" not in one_line

    for piece in chunk_message(one_line, max_length=4000):
        assert len(piece) <= 4000

    out = _fit_to_whatsapp_limit(one_line, "ENGLISH")
    assert len(out) <= _WHATSAPP_HARD_SEND_LIMIT


def test_a_single_unbreakable_token_is_hard_cut_rather_than_left_oversized() -> None:
    """No whitespace to cut at (a URL, a CJK run): the limit still wins.

    Losing a word boundary is worse than a cut word; being rejected or silently
    truncated by the platform is worse than both.
    """
    for piece in chunk_message("x" * 9000, max_length=4000):
        assert len(piece) <= 4000


def test_the_marker_follows_the_asker_language() -> None:
    """An Italian client reads an Italian note, not an English one."""
    answer = _long_paragraphs(9000)
    out = _fit_to_whatsapp_limit(answer, "ITALIAN")
    assert out.endswith(get_localized_stub("truncated_tail", "ITALIAN"))
    assert out != _fit_to_whatsapp_limit(answer, "ENGLISH")


def test_every_protocol_language_has_a_marker_and_none_promises_the_rest() -> None:
    """The copy may say the answer was shortened and nothing more.

    Nothing retains the remainder, so a translation that says "I'll send the
    rest" or "ask me to continue" would be a promise this path cannot keep —
    the same class of defect as the callback the abstain path used to promise.
    """
    forbidden = (
        "continue", "continua", "lanjutkan", "продолж", "продовж",
        "the rest", "il resto", "sisanya", "остальн", "решту",
        "next message", "prossimo messaggio",
    )
    for language in PROTOCOL_LANGUAGES:
        text = get_localized_stub("truncated_tail", language)
        assert text.strip(), f"{language} has no truncated_tail copy"
        offenders = [f for f in forbidden if f in text.lower()]
        assert not offenders, f"{language} promises the remainder: {offenders}"


@pytest.mark.parametrize("language", list(PROTOCOL_LANGUAGES))
def test_the_marker_itself_never_eats_the_budget(language: str) -> None:
    """Whatever the translation, the result fits — the budget is computed from it."""
    out = _fit_to_whatsapp_limit(_long_paragraphs(9000), language)
    assert len(out) <= _WHATSAPP_HARD_SEND_LIMIT


def test_it_fails_open_to_todays_behaviour() -> None:
    """A broken marker lookup must not cost the client the message.

    Failing open here means `send_message` truncates exactly as it did before —
    a worse message, never a lost one.
    """
    answer = _long_paragraphs(9000)
    with patch(f"{BOT}.get_localized_stub", side_effect=RuntimeError("boom")):
        assert _fit_to_whatsapp_limit(answer, "ENGLISH") == answer
