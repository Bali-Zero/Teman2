"""A German or Spanish client reads a refusal in their own language, not English.

RECORDED DEFECT
----------------
``detect_query_language`` (query_helpers.py) could already emit ``"GERMAN"``
and ``"SPANISH"`` — the ``_LATIN_MARKERS`` detector rows cover both — but
``STUB_MESSAGES`` (``_reasoning_stubs.py``) only translated five protocol
languages and silently declared GERMAN/SPANISH as English-fallback. Every
call site that resolves an abstain/error/confused stub from the detected
language (``reasoning.py``'s ReAct loop, ``wa_finalize.py``'s
``_safe_abstain_reply``) therefore answered a German or Spanish question with
English copy, and nothing failed — the exact shape ``test_reasoning_stubs_
language_coverage.py``'s own docstring describes for Russian/Ukrainian before
2026-07-27.

THE TRAP THIS FILE DOES NOT WALK INTO
--------------------------------------
A SEPARATE detector, ``backend.services.communication.language_detector.
detect_language``, emits lowercase codes ("de" is not even one of its five
codes — it has no German/Spanish support at all, only it/en/id/uk/ru) and is
used by the WA outbox worker's ack/apology sends, which key their OWN small
dict on those lowercase codes. This file never touches that detector or that
dict — mixing the two vocabularies is the documented regression, not a fix
(see ``test_whatsapp_send_fits_limit.py::
test_an_unknown_language_name_must_not_silently_become_an_english_apology``).

GUILT below proves a real German/Spanish query is detected AND answered in
that language, end to end through both the reasoning-engine stub table and
the WA-finalize abstain path. INNOCENCE proves the five previously-covered
protocol languages are byte-identical to what they were before this change —
this addition only ADDS coverage, it does not touch existing translations.
"""

from __future__ import annotations

from backend.services.integrations.wa_finalize import _safe_abstain_reply
from backend.services.rag.agentic._reasoning_stubs import (
    PROTOCOL_LANGUAGES,
    STUB_MESSAGES,
    get_localized_stub,
)
from backend.services.rag.agentic.query_helpers import detect_query_language

# Real questions, not synthetic language tags — the detector must fire on the
# actual marker words, not on a hand-picked language name.
GERMAN_QUERY = "Welche Dokumente brauche ich, um eine PT PMA zu gründen?"
SPANISH_QUERY = "¿Qué documentos necesito para abrir una empresa en Indonesia?"


class TestGuiltGermanAndSpanishAreDetectedAndAnswered:
    def test_german_query_is_detected_as_german(self) -> None:
        assert detect_query_language(GERMAN_QUERY) == "GERMAN"

    def test_spanish_query_is_detected_as_spanish(self) -> None:
        assert detect_query_language(SPANISH_QUERY) == "SPANISH"

    def test_german_stub_is_german_not_english(self) -> None:
        stub = get_localized_stub("abstain", "GERMAN")
        assert stub != STUB_MESSAGES["abstain"]["ENGLISH"]
        # A cheap but real signal this is actually German prose, not a
        # mistranslated copy-paste: the umlaut/eszett characters this
        # vocabulary uses show up somewhere in the sentence.
        assert any(ch in stub for ch in "äöüßÄÖÜ")

    def test_spanish_stub_is_spanish_not_english(self) -> None:
        stub = get_localized_stub("abstain", "SPANISH")
        assert stub != STUB_MESSAGES["abstain"]["ENGLISH"]
        assert any(ch in stub for ch in "áéíóúñ¿¡")

    def test_german_query_gets_the_german_stub_end_to_end(self) -> None:
        """The full path a client actually hits: detect -> resolve -> send."""
        reply = _safe_abstain_reply(GERMAN_QUERY)
        assert reply == get_localized_stub("abstain", "GERMAN")
        assert reply != get_localized_stub("abstain", "ENGLISH")

    def test_spanish_query_gets_the_spanish_stub_end_to_end(self) -> None:
        reply = _safe_abstain_reply(SPANISH_QUERY)
        assert reply == get_localized_stub("abstain", "SPANISH")
        assert reply != get_localized_stub("abstain", "ENGLISH")

    def test_german_and_spanish_are_now_protocol_languages(self) -> None:
        assert "GERMAN" in PROTOCOL_LANGUAGES
        assert "SPANISH" in PROTOCOL_LANGUAGES


class TestInnocenceExistingLanguagesAreUnchanged:
    """This addition must not have touched any previously-shipped translation."""

    _PREVIOUSLY_SHIPPED_ABSTAIN = {
        "ITALIAN": (
            "Su questo non ho una fonte certa e preferisco non tirare a indovinare: "
            "con permessi e scadenze una risposta sbagliata costa. "
            "Questa la deve guardare un collega di Bali Zero. "
            "Se intanto mi mandi un documento o una data di riferimento, "
            "posso riprovare con quelli."
        ),
        "ENGLISH": (
            "I don't have a reliable source for this one, and I'd rather not guess — "
            "with permits and deadlines a wrong answer is expensive. "
            "This one needs a Bali Zero colleague to look at it. "
            "If you can send me a document or a reference date in the meantime, "
            "I can try again with those."
        ),
        "INDONESIAN": (
            "Untuk yang ini saya tidak punya sumber yang pasti, dan saya lebih baik "
            "tidak menebak — untuk izin dan tenggat waktu, jawaban yang salah itu mahal. "
            "Yang ini perlu dilihat oleh rekan dari Bali Zero. "
            "Sementara itu, kalau Anda kirim dokumen atau tanggal acuan, "
            "saya bisa coba lagi dengan itu."
        ),
        "RUSSIAN": (
            "По этому вопросу у меня нет надёжного источника, и я предпочитаю не гадать: "
            "когда речь идёт о разрешениях и сроках, неверный ответ обходится дорого. "
            "Здесь нужен взгляд коллеги из Bali Zero. "
            "Если пока пришлёте документ или дату, на которую опираетесь, "
            "я попробую ещё раз с ними."
        ),
        "UKRAINIAN": (
            "Щодо цього я не маю надійного джерела і волію не вгадувати: "
            "коли йдеться про дозволи та строки, неправильна відповідь дорого коштує. "
            "Це має подивитися колега з Bali Zero. "
            "Якщо тим часом надішлете документ або дату, на яку спираєтесь, "
            "я спробую ще раз із ними."
        ),
    }

    def test_the_five_original_protocol_languages_are_byte_identical(self) -> None:
        for language, text in self._PREVIOUSLY_SHIPPED_ABSTAIN.items():
            assert get_localized_stub("abstain", language) == text, (
                f"{language}'s 'abstain' stub changed — this cure must only ADD "
                f"GERMAN/SPANISH, never touch an existing translation"
            )

    def test_the_five_original_languages_still_route_correctly(self) -> None:
        cases = {
            "ENGLISH": "What documents do I need to open a company in Indonesia?",
            "ITALIAN": "Di cosa ho bisogno per aprire una società in Indonesia?",
            "INDONESIAN": "Saya mau tanya berapa biaya untuk bikin PT PMA?",
            "RUSSIAN": "Здравствуйте, подскажите пожалуйста как открыть компанию?",
            "UKRAINIAN": "Доброго дня, підкажіть будь ласка як відкрити компанію?",
        }
        for expected_language, query in cases.items():
            assert detect_query_language(query) == expected_language, (
                f"query written for {expected_language} was misdetected — "
                f"this cure must not have perturbed the existing detector rows"
            )
