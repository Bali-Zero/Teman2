"""The WhatsApp persona layer must not dictate Italian, and must allow honesty.

Two defects, one file, one theme — what this layer FORCES the model to do.

1. `whatsapp_chat.py` injects the persona as a fake first exchange in the
   conversation history. Both halves were hardcoded Italian, including the
   assistant turn: the model's own most recent precedent for "how I speak
   here" was Italian, planted before the client had said a word — twenty
   lines away from a comment explaining that the persona is written four
   times over so "an English-speaking client never sees Italian instructions
   in their system context".

2. `expert_rules` forbids saying "I don't have access" / "I have no info in
   the system". The 2026-07-28 team beta caught the consequence: asked about
   a colleague's client deadlines it has no tool to see, the bot answered
   "semuanya sudah aman" — an invented reassurance about real client
   deadlines, stated confidently. The corner's own reading is that "the
   defect is not the missing tool, it is the absence of ONE honest way to say
   'I don't have access'". This prompt is what forbade it.

Both are asserted per-language from the module's own tables, so a fifth
language added later inherits the guard.
"""

import pytest

from backend.prompts import whatsapp_persona

_LANGS = ["en", "it", "id", "de"]


class TestPrimingTurnsSpeakTheClientsLanguage:
    @pytest.mark.parametrize("lang", _LANGS)
    def test_guilt_the_assistant_turn_is_not_italian_for_non_italian_clients(self, lang):
        """The planted assistant line is the strongest pull into a language."""
        turns = whatsapp_persona.build_priming_turns("PERSONA", lang)
        assistant = turns[1]["content"]

        if lang == "it":
            assert "rispondo come Zan" in assistant
        else:
            assert "Capito, rispondo come Zan" not in assistant
            assert "niente markdown" not in assistant

    @pytest.mark.parametrize("lang", _LANGS)
    def test_guilt_the_user_turn_header_and_closing_follow_the_language(self, lang):
        turns = whatsapp_persona.build_priming_turns("PERSONA", lang)
        user = turns[0]["content"]

        if lang == "it":
            assert "[CONTESTO WHATSAPP]" in user
        else:
            assert "[CONTESTO WHATSAPP]" not in user
            assert "Rispondi sempre come Zan" not in user

    def test_guilt_an_english_client_gets_no_italian_anywhere_in_the_pair(self):
        """The measured shape: English in, Italian framing planted anyway."""
        blob = " ".join(t["content"] for t in whatsapp_persona.build_priming_turns("PERSONA", "en"))

        for italian in ("Rispondi sempre", "Capito,", "CONTESTO", "niente markdown"):
            assert italian not in blob

    def test_innocence_the_persona_itself_is_carried_through_verbatim(self):
        """Framing the pair must not edit, truncate or reorder the persona."""
        persona = "PERSONA-SENTINEL-9f3a\nsecond line"
        turns = whatsapp_persona.build_priming_turns(persona, "id")

        assert persona in turns[0]["content"]
        assert turns[0]["role"] == "user"
        assert turns[1]["role"] == "assistant"
        assert len(turns) == 2

    def test_innocence_an_unknown_language_falls_back_to_english(self):
        """Same fallback rule every other block in this module uses.

        `detect_query_language` emits more values than this table carries, so
        the fallback is the common case, not the corner case.
        """
        for unknown in (None, "uk", "ru", "fr", "sv"):
            turns = whatsapp_persona.build_priming_turns("PERSONA", unknown)
            assert "Understood" in turns[1]["content"], f"{unknown!r} did not fall back to English"


class TestTheRouterDoesNotKeepItsOwnFraming:
    """The defect was not in this module — it was in the CALLER.

    A perfectly multilingual persona is worthless if the router staples its
    own Italian onto it, so pin the caller too. This reads the source rather
    than driving the webhook: the whole branch needs Meta, Postgres and an
    orchestrator to reach, and what regresses here is the literal, not the
    control flow.
    """

    def _router_source(self) -> str:
        from pathlib import Path

        import backend.app.routers.whatsapp_chat as router_module

        return Path(router_module.__file__).read_text(encoding="utf-8")

    def test_guilt_the_router_delegates_the_framing(self):
        source = self._router_source()

        assert "build_priming_turns(" in source, (
            "the router must build the priming pair through the persona module, "
            "which is where every other language rule lives"
        )

    def test_guilt_the_italian_priming_literals_are_gone_from_the_router(self):
        source = self._router_source()

        for literal in (
            "[CONTESTO WHATSAPP]",
            "Rispondi sempre come Zan di Bali Zero",
            "Capito, rispondo come Zan su WhatsApp",
        ):
            assert literal not in source, f"router still hardcodes {literal!r}"


class TestTheModelMaySayItCannotSee:
    @pytest.mark.parametrize("lang", _LANGS)
    def test_guilt_every_language_grants_the_honest_refusal(self, lang):
        """Each language must carry the carve-out, not just English."""
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)

        grants = {
            "en": "THE ONE THING YOU MAY ALWAYS SAY",
            "it": "L'UNICA COSA CHE PUOI SEMPRE DIRE",
            "id": "SATU HAL YANG SELALU BOLEH ANDA KATAKAN",
            "de": "DAS EINE, WAS SIE IMMER SAGEN DÜRFEN",
        }
        assert grants[lang] in prompt

    @pytest.mark.parametrize("lang", _LANGS)
    def test_guilt_every_language_forbids_the_invented_all_clear(self, lang):
        """The exact behaviour the beta caught: "semuanya sudah aman"."""
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)

        bans = {
            "en": "situation is fine, handled or up to date unless the verified",
            "it": "a posto, sistemata o in regola se non lo dicono i dati",
            "id": "sudah aman, sudah beres, atau sudah lengkap kecuali data",
            "de": "in Ordnung, erledigt oder aktuell, wenn die geprüften Daten",
        }
        assert bans[lang] in prompt

    @pytest.mark.parametrize("lang", _LANGS)
    def test_innocence_the_anti_software_voice_rule_survives(self, lang):
        """The old rule exists for a reason — a canned brush-off is also a bug.

        The beta caught that too: the same LKPM question asked four times got
        the identical "Got it! 😊" four times. The carve-out must not read as
        permission to sound like software.
        """
        prompt = whatsapp_persona.build_system_prompt(detected_language=lang)

        keeps = {
            "en": "You are an expert consultant, not a piece of software",
            "it": "Tu sei un consulente esperto, non un software",
            "id": "Anda adalah konsultan ahli, bukan perangkat lunak",
            "de": "Sie sind ein Experte, keine Software",
        }
        assert keeps[lang] in prompt

    def test_innocence_the_pricing_and_context_blocks_are_untouched(self):
        prompt = whatsapp_persona.build_system_prompt(
            client_name="Test Client",
            detected_language="en",
            is_first_message=True,
        )

        assert "Always call the get_pricing tool" in prompt
        assert "CLIENT CONTEXT:" in prompt
        assert "Client name: Test Client." in prompt
