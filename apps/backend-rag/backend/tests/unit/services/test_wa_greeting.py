"""Guilt AND innocence for the scripted greeting turn.

The defect this cures (cycle 359, real delivery): a bare "halo" fell off the
package builder and took ~7m45s to answer an English error stub.

The defect a careless cure would INTRODUCE: swallowing "halo, berapa harga PT
PMA?" — a real pricing question that opens politely — into a canned capability
message. Scar family #3 is over-match, and it is the more expensive half here,
so the innocence set below is deliberately larger than the guilt set.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.services.integrations.wa_greeting import (
    _GREETING_REPLIES,
    GreetingTurn,
    match_greeting,
)


class TestGuilt:
    """Bare greetings MUST be answered from the script, in their language."""

    @pytest.mark.parametrize(
        ("message", "language"),
        [
            # The four the mandate names.
            ("halo", "id"),
            ("hi", "en"),
            ("ciao", "it"),
            ("привет", "ru"),
            # The rest of the front door, per language.
            ("Halo", "id"),
            ("HALO!", "id"),
            ("halo 👋", "id"),
            ("hai", "id"),
            ("Selamat pagi", "id"),
            ("selamat sore", "id"),
            ("assalamualaikum", "id"),
            ("hello", "en"),
            ("Hello!", "en"),
            ("hey", "en"),
            ("Good morning", "en"),
            ("good evening", "en"),
            ("Ciao!", "it"),
            ("buongiorno", "it"),
            ("Buonasera", "it"),
            ("salve", "it"),
            ("Привет!", "ru"),
            ("здравствуйте", "ru"),
            ("добрый день", "ru"),
            ("привіт", "uk"),
            ("доброго дня", "uk"),
            # Cross-family refuter (Codex GPT-5.6 Sol, 2026-09-03) finding 2:
            # both of these were MISSED by the first draft and therefore still
            # cost the full 7m45s. The apostrophe is stripped by _normalize, so
            # the transliteration arrives as two tokens; and a multi-word
            # greeting followed by an honorific was not matchable at all while
            # phrases were keyed on the whole message.
            ("Assalamu'alaikum", "id"),
            ("Selamat pagi, Kak", "id"),
            ("selamat malam pak", "id"),
            ("good morning zantara", "en"),
        ],
    )
    def test_a_bare_greeting_is_answered_from_the_script(
        self, message: str, language: str
    ) -> None:
        turn = match_greeting(message)
        assert turn is not None, f"{message!r} must be recognised as a greeting"
        assert turn.language == language
        assert turn.text == _GREETING_REPLIES[language]

    @pytest.mark.parametrize(
        "message",
        ["halo zantara", "hi there", "ciao Bali Zero", "halo halo", "halo kak"],
    )
    def test_a_greeting_with_a_vocative_is_still_a_greeting(self, message: str) -> None:
        assert match_greeting(message) is not None

    def test_an_indonesian_honorific_outranks_an_english_greeting(self) -> None:
        """Refuter finding 5: "Hi kak" answered in English.

        "hi" is used on this number in every language; "kak" is not. The
        override is one-directional — a vocative may displace the FALLBACK
        language, never an explicit non-English one.
        """
        hi_kak = match_greeting("Hi kak")
        assert hi_kak is not None and hi_kak.language == "id"

        ciao_kak = match_greeting("ciao kak")
        assert ciao_kak is not None and ciao_kak.language == "it"

    def test_the_answer_names_what_the_bot_can_do(self) -> None:
        """A greeting turn that only greets sends the client back to square one.

        The measured shape (Dialogflow CX / Rasa) is greeting + capability, so
        the NEXT turn arrives with a topic the retrieval path can serve.
        """
        for language, reply in _GREETING_REPLIES.items():
            assert reply.count("•") >= 4, f"{language} reply lists no capabilities"
            assert "KITAS" in reply and "PT PMA" in reply

    def test_the_answer_carries_no_citation_and_no_price(self) -> None:
        """ZERO-DECISIONS item 3 case (b): a courtesy turn cites nothing.

        And prices come from PricingTool on the answering path — never from a
        canned string (Golden Rule 11, and Zero's single-price ruling).
        """
        for reply in _GREETING_REPLIES.values():
            assert "📜" not in reply
            assert "Sumber:" not in reply and "Source:" not in reply
            assert "Rp" not in reply
            assert "IDR" not in reply


class TestInnocence:
    """A question that merely OPENS with a greeting is not a greeting."""

    @pytest.mark.parametrize(
        "message",
        [
            # The exact shape the cure must not eat, in four languages.
            "halo, berapa harga PT PMA?",
            "Halo saya mau tanya soal visa",
            "hi, my KITAS expired last week",
            "Hello, how much is a PT PMA?",
            "ciao, quanto costa aprire una PT PMA?",
            "Buongiorno, ho bisogno di rinnovare il KITAS",
            "привет, сколько стоит KITAS?",
            "Здравствуйте, я хочу открыть компанию",
            # Not greetings at all.
            "berapa harga PT PMA?",
            "What is the minimum paid-up capital for a PT PMA?",
            "posso pagare con bonifico?",
            # A vocative with no greeting in it is not a greeting.
            "bali zero",
            "zantara",
            # Refuter finding 1, the BLOCKING one. "admin"/"team" are not
            # politeness — they are a request for a PERSON, and answering them
            # with a capability list is this module's own defect pointed the
            # other way. They must reach the normal route, which carries the
            # human-notification wiring.
            "admin",
            "Halo admin?",
            "Hi, admin?",
            "Ciao, admin?",
            "halo team",
            "hi everyone",
            # Nonsense must fall through, not be greeted.
            "xyzabc123",
            "?",
            "👍",
        ],
    )
    def test_a_message_carrying_a_question_falls_through(self, message: str) -> None:
        assert match_greeting(message) is None, (
            f"{message!r} was swallowed by the greeting path — it carries content "
            "the retrieval route must answer"
        )

    @pytest.mark.parametrize("message", ["", "   ", None])
    def test_empty_input_falls_through(self, message: str | None) -> None:
        assert match_greeting(message) is None

    def test_a_long_message_is_never_greeted(self) -> None:
        """The character cap is a second, independent brake on over-match."""
        assert match_greeting("halo " * 20) is None


def test_the_return_type_is_frozen() -> None:
    """The turn is a value, not a mutable bag the caller can edit."""
    turn = match_greeting("halo")
    assert isinstance(turn, GreetingTurn)
    with pytest.raises(dataclasses.FrozenInstanceError):
        turn.text = "something else"  # type: ignore[misc]
