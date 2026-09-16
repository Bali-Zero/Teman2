"""Guilt AND innocence for the scripted identity ("who are you") turn.

The defect this cures (measured, 2026-09-15 15:47-15:49 WITA): a client opened
the thread with "ciao tu sei Zantara?" and got the ABSTAIN stub — no chunk in
any collection says who Zantara is, so the evidence gate correctly refused.
Asked again, plainly, "ti ho chiesto chi sei tu?", the bot repeated the
refusal, in ENGLISH, to a client writing Italian.

The defect a careless cure would INTRODUCE: swallowing "chi deve firmare la
LKPM?" or "cosa puoi fare per la mia PT PMA?" into a canned presentation
instead of the real case answer. Scar family #3 is over-match, and the domain
veto is the expensive half of this guard — so, as with the greeting turn, the
innocence set below is deliberately at least as large as the guilt set.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.services.integrations.wa_identity import (
    _IDENTITY_REPLIES,
    IdentityTurn,
    _normalize,
    match_identity_question,
)


class TestGuilt:
    """A genuine identity question MUST be answered from the script, in its language."""

    @pytest.mark.parametrize(
        ("message", "language"),
        [
            # The two real production messages (measured, 2026-09-15).
            ("ciao tu sei Zantara?", "it"),
            ("ti ho chiesto chi sei tu?", "it"),
            # The mandate's Indonesian case.
            ("siapa kamu?", "id"),
            # Rest of the Italian phrase table.
            ("chi sei", "it"),
            ("chi sei tu", "it"),
            ("tu chi sei", "it"),
            ("ma chi sei", "it"),
            ("sei un bot", "it"),
            ("sei un robot", "it"),
            ("sei una macchina", "it"),
            ("sei umano", "it"),
            ("sei zantara", "it"),
            ("chi è zantara", "it"),
            ("chi e zantara", "it"),
            ("cosa sai fare", "it"),
            ("cosa puoi fare", "it"),
            ("come funzioni", "it"),
            ("chi ti ha creato", "it"),
            ("con chi sto parlando", "it"),
            # English.
            ("who are you", "en"),
            ("what are you", "en"),
            ("are you a bot", "en"),
            ("are you human", "en"),
            ("are you real", "en"),
            ("who is zantara", "en"),
            ("what can you do", "en"),
            ("how do you work", "en"),
            ("who made you", "en"),
            ("who created you", "en"),
            # Indonesian.
            ("siapa kamu", "id"),
            ("kamu siapa", "id"),
            ("siapa anda", "id"),
            ("kamu bot", "id"),
            ("kamu manusia", "id"),
            ("kamu zantara", "id"),
            ("siapa zantara", "id"),
            ("kamu bisa apa", "id"),
            ("apa yang bisa kamu bantu", "id"),
        ],
    )
    def test_an_identity_question_is_answered_from_the_script(
        self, message: str, language: str
    ) -> None:
        turn = match_identity_question(message)
        assert turn is not None, f"{message!r} must be recognised as an identity question"
        assert turn.language == language
        assert turn.text == _IDENTITY_REPLIES[language]

    def test_case_and_punctuation_do_not_matter(self) -> None:
        turn = match_identity_question("Ti ho chiesto CHI SEI TU???")
        assert turn is not None and turn.language == "it"

    def test_no_punctuation_ordinary_spelling_still_matches(self) -> None:
        """A real client rarely types the question mark."""
        turn = match_identity_question("chi sei tu")
        assert turn is not None and turn.language == "it"

    def test_a_trailing_emoji_does_not_block_the_match(self) -> None:
        turn = match_identity_question("chi sei? 😄")
        assert turn is not None and turn.language == "it"

    def test_a_whatsapp_list_ordinal_prefix_still_matches(self) -> None:
        """ "11.  chi sei" — a client replying to a numbered menu.

        Unlike `wa_greeting`, this module does not need a dedicated ordinal
        strip: the phrase match scans every whole-token WINDOW of the
        message (not just from position 0), so the leading "11" is simply an
        extra token the scan skips past on its way to "chi sei".
        """
        turn = match_identity_question("11.  chi sei")
        assert turn is not None and turn.language == "it"

    def test_the_phrase_is_found_embedded_mid_sentence(self) -> None:
        """The docstring's own example: whole-token match, not whole-message."""
        turn = match_identity_question("ti ho chiesto chi sei tu")
        assert turn is not None and turn.language == "it"

    def test_the_answer_names_what_the_bot_can_do(self) -> None:
        for language, reply in _IDENTITY_REPLIES.items():
            assert reply.count("•") >= 4, f"{language} reply lists no capabilities"
            assert "KITAS" in reply and "PT PMA" in reply

    def test_the_answer_carries_no_citation_and_no_price(self) -> None:
        for reply in _IDENTITY_REPLIES.values():
            assert "📜" not in reply
            assert "Sumber:" not in reply and "Source:" not in reply
            assert "Rp" not in reply
            assert "IDR" not in reply

    def test_the_answer_makes_no_handoff_promise(self) -> None:
        """CURE 1: nothing in this repository detects a handoff phrase today
        (see the comment above `_IDENTITY_REPLIES`), so the presentation must
        not promise one. It returns in the slice that wires the detector."""
        for reply in _IDENTITY_REPLIES.values():
            lowered = reply.lower()
            assert "human" not in lowered
            assert "manusia" not in lowered
            assert "operatore" not in lowered


class TestInnocence:
    """A question about a CASE, or a bare greeting, is not an identity question."""

    @pytest.mark.parametrize(
        "message",
        [
            # The mandate's required innocence cases — a person in a CASE is
            # not a question about the assistant.
            "chi deve firmare la LKPM?",
            "siapa yang harus tanda tangan akta?",
            "who signs the deed?",
            # Domain veto must win even though an identity phrase is textually
            # present ("cosa puoi fare" / "what can you do" / phrase-adjacent
            # bahasa) — the veto runs BEFORE the phrase match.
            "cosa puoi fare per la mia PT PMA?",
            "what can you do about my overstay?",
            "kamu bisa bantu apa untuk visa saya?",
            "berapa harga PT PMA all in",
            # Bare greetings stay the GREETING module's business.
            "halo",
            "ciao",
            "hi",
            # An ordinary client opening that is not about identity at all.
            "hi kak",
            # A message that carries an identity phrase but is far too long
            # to be a scripted turn (>120 chars).
            (
                "Ciao, volevo chiederti chi sei tu esattamente e come funzioni "
                "perche' ho bisogno di sapere se posso fidarmi prima di mandarti "
                "i documenti del mio passaporto e della mia KITAS"
            ),
            # A different person-in-a-case phrasing per language.
            "chi ha diritto alla proprieta' del terreno?",
            "siapa pemilik sertifikat tanah ini?",
            "who is the sponsor listed on the KITAS?",
            # Pure noise / no signal at all.
            "xyzabc123",
            "?",
            "👍",
            "",
            "   ",
        ],
    )
    def test_a_case_question_or_bare_greeting_falls_through(self, message: str) -> None:
        assert match_identity_question(message) is None, (
            f"{message!r} was swallowed by the identity path — it must reach "
            "the normal route (a case question) or the greeting module (a "
            "bare greeting)"
        )

    def test_none_input_falls_through(self) -> None:
        assert match_identity_question(None) is None

    def test_a_long_message_is_never_answered_from_the_script(self) -> None:
        """The character cap is a second, independent brake on over-match."""
        long_message = "chi sei " * 20
        assert len(long_message) > 120
        assert match_identity_question(long_message) is None

    def test_a_token_count_over_the_cap_falls_through(self) -> None:
        assert match_identity_question("chi " * 25) is None

    @pytest.mark.parametrize(
        "veto_token",
        [
            "pma",
            "kitas",
            "npwp",
            "harga",
            "visa",
            "villa",
            "overstay",
            "notaris",
        ],
    )
    def test_any_domain_veto_token_blocks_an_otherwise_matching_phrase(
        self, veto_token: str
    ) -> None:
        """Structural veto, not a list of counter-examples: pair "chi sei"
        with each family's own token and confirm the veto still wins."""
        assert match_identity_question(f"chi sei tu esperto di {veto_token}") is None


def test_the_return_type_is_frozen() -> None:
    turn = match_identity_question("chi sei")
    assert isinstance(turn, IdentityTurn)
    with pytest.raises(dataclasses.FrozenInstanceError):
        turn.text = "something else"  # type: ignore[misc]


def test_zantara_and_bali_zero_are_not_domain_veto_tokens() -> None:
    """Asking who Zantara is IS the identity question — the module's own
    contract (docstring) says these two tokens are deliberately excluded
    from the veto list."""
    assert match_identity_question("sei zantara") is not None
    assert match_identity_question("chi è zantara") is not None


def test_cyrillic_survives_normalization_into_the_expected_tokens() -> None:
    """CURE 4 pre-flight: `_PUNCT_RE` is `[^\\w\\s]` and `\\w` is
    Unicode-aware, and `casefold()` lowercases non-Latin scripts too — but
    that is a claim about the stdlib, not a fact until it is measured. If
    Cyrillic did NOT survive, the ru/uk phrase table below could never match
    anything and every test after this one would be testing a dead table."""
    assert _normalize("Кто Ты?") == "кто ты"
    assert _normalize("ХТО ТИ?") == "хто ти"


class TestRussianAndUkrainian:
    """CURE 4: `wa_greeting` already scripts `ru`/`uk`; `wa_identity` must
    too, or a Russian/Ukrainian client asking who this is falls through to
    the abstain refusal — the exact defect this slice exists to close."""

    @pytest.mark.parametrize(
        "message",
        [
            "кто ты",
            "кто вы",
            "ты кто",
            "ты бот",
            "ты робот",
            "ты человек",
            "кто тебя создал",
            "что ты умеешь",
        ],
    )
    def test_a_russian_identity_question_is_answered_in_russian(self, message: str) -> None:
        turn = match_identity_question(message)
        assert turn is not None, f"{message!r} must be recognised as an identity question"
        assert turn.language == "ru"
        assert turn.text == _IDENTITY_REPLIES["ru"]

    @pytest.mark.parametrize(
        "message",
        [
            "хто ти",
            "хто ви",
            "ти хто",
            "ти бот",
            "ти робот",
            "ти людина",
            "хто тебе створив",
            "що ти вмієш",
        ],
    )
    def test_a_ukrainian_identity_question_is_answered_in_ukrainian(self, message: str) -> None:
        turn = match_identity_question(message)
        assert turn is not None, f"{message!r} must be recognised as an identity question"
        assert turn.language == "uk"
        assert turn.text == _IDENTITY_REPLIES["uk"]

    @pytest.mark.parametrize(
        "message",
        [
            # A Russian sentence naming a Latin-script domain token — the
            # veto reads tokens, not scripts, so it must still win.
            "что ты умеешь по моей визе KITAS?",
            "что ты можешь сделать для моей PT PMA?",
        ],
    )
    def test_a_russian_case_question_with_a_domain_token_is_vetoed(self, message: str) -> None:
        assert match_identity_question(message) is None

    @pytest.mark.parametrize(
        "message",
        [
            "що ти вмієш щодо моєї візи KITAS?",
            "що ти можеш зробити для моєї PT PMA?",
        ],
    )
    def test_a_ukrainian_case_question_with_a_domain_token_is_vetoed(self, message: str) -> None:
        assert match_identity_question(message) is None


class TestAIPhrasing:
    """CURE 6: the Dux's 32-guilt/23-innocence census found exactly one
    under-match shape — "are you an AI" — and it is very likely the single
    most common way a client phrases this question today."""

    @pytest.mark.parametrize(
        ("message", "language"),
        [
            ("are you an AI?", "en"),
            ("are you AI", "en"),
            ("is this an AI", "en"),
            ("am I talking to an AI", "en"),
            ("are you a chatbot", "en"),
            ("sei un IA?", "it"),
            ("sei un chatbot?", "it"),
            ("apakah kamu AI?", "id"),
            ("kamu AI?", "id"),
            ("apakah kamu chatbot?", "id"),
            ("ты искусственный интеллект?", "ru"),
            ("это ИИ?", "ru"),
            ("ты чатбот?", "ru"),
            ("ти штучний інтелект?", "uk"),
            ("це штучний інтелект?", "uk"),
            ("ти чатбот?", "uk"),
        ],
    )
    def test_the_ai_question_is_recognised_in_every_language(
        self, message: str, language: str
    ) -> None:
        turn = match_identity_question(message)
        assert turn is not None, f"{message!r} must be recognised as an identity question"
        assert turn.language == language

    def test_the_apostrophe_form_normalizes_into_the_dict_key(self) -> None:
        """`_PUNCT_RE` strips the apostrophe to a space, so the dict key is
        written "un intelligenza" (two tokens), never "un'intelligenza" — a
        key written with the apostrophe could never match anything, and
        nothing would tell you. Prove the client's actual typed form (with
        the apostrophe) still matches."""
        assert _normalize("sei un'intelligenza artificiale?") == "sei un intelligenza artificiale"
        turn = match_identity_question("sei un'intelligenza artificiale?")
        assert turn is not None and turn.language == "it"

    def test_a_domain_case_question_about_ai_is_still_vetoed(self) -> None:
        assert match_identity_question("what can this AI do for my PT PMA?") is None
