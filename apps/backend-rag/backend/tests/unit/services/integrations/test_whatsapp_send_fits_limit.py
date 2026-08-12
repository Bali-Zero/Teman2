"""An over-long WhatsApp body is cut at a boundary and marked, not severed.

WhatsApp Cloud API refuses a body over 4096 characters and `send_message` used to
enforce that with `text[:4096]` — a silent cut, mid-word, with nothing telling the
recipient anything was removed.

**Why these tests target the SERVICE and not the bot.** A first version of this
cure lived in `wa_inbox_bot`, and the pre-existing test for the old behaviour
(`test_wa_inbox_bot.py::test_oversized_reply_logs_non_silently`) said in its own
docstring that truncation is "whatsapp_service.py's job". A census agreed:
`send_message` has ~14 non-test call sites — the outbox worker, the conversations
router, compliance alerts, the client-value predictor — and only the two in
`whatsapp_chat.py` chunk beforehand. Curing the bot would have cured one producer
and left the other eleven severing words. The suite caught that, not review.

Three things are asserted here and they are not the same thing:

* the BODY that reaches the wire fits and is marked — the recipient-facing
  contract, tested through `send_message` rather than only through the helper;
* the marker never promises the remainder — nothing retains it;
* the chunker's own docstring promise ("each within max_length") is now TRUE — it
  was not, and the cure is built on it, so it is pinned rather than trusted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.integrations.whatsapp_service import (
    WHATSAPP_BODY_LIMIT,
    WhatsAppService,
    fit_to_whatsapp_limit,
)
from backend.services.rag.agentic._reasoning_stubs import (
    PROTOCOL_LANGUAGES,
    get_localized_stub,
)
from backend.utils.message_chunker import chunk_message

SVC = "backend.services.integrations.whatsapp_service"


def _long_paragraphs(total: int) -> str:
    """Realistic shape: many paragraphs, together longer than the limit."""
    para = ("Setting up a PT PMA requires several documents and steps. " * 6).strip()
    out: list[str] = []
    while len("\n\n".join(out)) < total:
        out.append(para)
    return "\n\n".join(out)


# ── the recipient-facing contract, through the real send path ───────────────


async def _captured_body(text: str, **kwargs) -> str:
    """Drive `send_message` with the HTTP hop faked, return the body it built."""
    svc = WhatsAppService()
    svc._token = "t"  # noqa: SLF001 — constructing the service under test
    svc._phone_number_id = "p"  # noqa: SLF001

    response = AsyncMock()
    response.status_code = 200
    response.json = lambda: {"messages": [{"id": "wamid.X"}]}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with patch.object(WhatsAppService, "_get_client", AsyncMock(return_value=client)):
        await svc.send_message(phone="62811", text=text, **kwargs)

    return client.post.call_args.kwargs["json"]["text"]["body"]


@pytest.mark.asyncio
async def test_the_body_that_reaches_the_wire_fits_and_is_marked() -> None:
    """GUILT, end to end: what Meta receives is within the limit and says it was cut."""
    text = _long_paragraphs(9000)
    assert len(text) > WHATSAPP_BODY_LIMIT

    body = await _captured_body(text, language="ENGLISH")

    assert len(body) <= WHATSAPP_BODY_LIMIT
    assert body.endswith(get_localized_stub("truncated_tail", "ENGLISH"))
    assert body.startswith(text[:50])


@pytest.mark.asyncio
async def test_an_ordinary_message_reaches_the_wire_byte_identical() -> None:
    """INNOCENCE: the overwhelming majority of sends must be untouched.

    This is the assertion that lets ~14 call sites — alerts, acks, operator
    sends — adopt the choke-point fix without auditing each one.
    """
    text = "A KITAS needs a sponsor, a passport valid 18 months, and a photo."
    assert await _captured_body(text) == text
    assert await _captured_body(text, language="ITALIAN") == text


@pytest.mark.asyncio
async def test_a_caller_that_does_not_know_the_language_still_gets_a_boundary_cut() -> None:
    """The 11 call sites that cannot name a language are the reason this exists.

    They get the neutral ellipsis rather than an English apology under a message
    that may not be English — `detect_query_language` returns ENGLISH for an
    Italian *answer*, so guessing here would be wrong more often than silent.
    """
    text = _long_paragraphs(9000)
    body = await _captured_body(text)

    assert len(body) <= WHATSAPP_BODY_LIMIT
    assert body.endswith("…")
    # and it must NOT have guessed a language
    assert get_localized_stub("truncated_tail", "ENGLISH") not in body


# ── properties of the cut itself ────────────────────────────────────────────


def test_the_cut_does_not_sever_a_word() -> None:
    """A boundary cut is the whole difference between this and `text[:4096]`."""
    text = _long_paragraphs(9000)
    out = fit_to_whatsapp_limit(text, "ENGLISH")
    body = out[: -len(get_localized_stub("truncated_tail", "ENGLISH"))]
    nxt = text[len(body) : len(body) + 1]
    assert nxt == "" or nxt.isspace(), f"cut mid-word, next char was {nxt!r}"


def test_one_enormous_line_with_no_newlines_still_fits() -> None:
    """The shape the old chunker let through whole — an ordinary LLM paragraph.

    `chunk_message` split on `\\n\\n` then `\\n`; text containing neither came back
    as ONE oversized chunk while the docstring promised the opposite. The cure
    depends on it, so it is pinned at BOTH levels.
    """
    one_line = "word " * 2000  # 10,000 chars, no newline anywhere
    assert "\n" not in one_line

    for piece in chunk_message(one_line, max_length=4000):
        assert len(piece) <= 4000

    assert len(fit_to_whatsapp_limit(one_line, "ENGLISH")) <= WHATSAPP_BODY_LIMIT


def test_a_single_unbreakable_token_is_hard_cut_rather_than_left_oversized() -> None:
    """No whitespace to cut at (a URL, a CJK run): the limit still wins.

    Losing a word boundary is worse than a cut word; being rejected or silently
    truncated by the platform is worse than both.
    """
    for piece in chunk_message("x" * 9000, max_length=4000):
        assert len(piece) <= 4000


# ── the copy ────────────────────────────────────────────────────────────────


def test_the_marker_follows_the_language_the_caller_names() -> None:
    """An Italian client reads an Italian note, not an English one."""
    text = _long_paragraphs(9000)
    out = fit_to_whatsapp_limit(text, "ITALIAN")
    assert out.endswith(get_localized_stub("truncated_tail", "ITALIAN"))
    assert out != fit_to_whatsapp_limit(text, "ENGLISH")


def test_every_protocol_language_has_a_marker_and_none_promises_the_rest() -> None:
    """The copy may say the reply was shortened and nothing more.

    Nothing retains the remainder, so a translation saying "I'll send the rest"
    or "ask me to continue" would be a promise this path cannot keep — the same
    class of defect as the callback the abstain path used to promise.
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
    assert len(fit_to_whatsapp_limit(_long_paragraphs(9000), language)) <= WHATSAPP_BODY_LIMIT


def test_an_unknown_language_name_must_not_silently_become_an_english_apology() -> None:
    """`get_localized_stub` degrades to ENGLISH silently — measured: 'it', 'IT'
    and 'italian' all return the ENGLISH sentence, only 'ITALIAN' works.

    That is a live trap for the next caller, because the outbox worker's OTHER
    detector (`services.communication.detect_language`) speaks lowercase codes
    ('it'), not protocol names. Wiring that vocabulary straight in would put an
    English apology under an Italian message and nothing would say so. This test
    does not fix the mismatch — it pins that an unrecognised name is NOT treated
    as a correctly-localized one, so the day someone wires it, this fails.
    """
    out_lower = fit_to_whatsapp_limit(_long_paragraphs(9000), "it")
    english = get_localized_stub("truncated_tail", "ENGLISH")
    italian = get_localized_stub("truncated_tail", "ITALIAN")
    assert out_lower.endswith(english), "stub behaviour changed — re-read the wiring note"
    assert not out_lower.endswith(italian), (
        "'it' now resolves to Italian; the vocabulary mismatch is closed, so the "
        "outbox worker's detector can finally be wired through — do that, then "
        "rewrite this test"
    )


def test_it_fails_open_to_todays_behaviour() -> None:
    """A broken marker lookup must not cost the recipient the message.

    Failing open means the payload builder truncates exactly as it did before —
    a worse message, never a lost one.
    """
    text = _long_paragraphs(9000)
    with patch(f"{SVC}.get_localized_stub", side_effect=RuntimeError("boom")):
        assert fit_to_whatsapp_limit(text, "ENGLISH") == text
