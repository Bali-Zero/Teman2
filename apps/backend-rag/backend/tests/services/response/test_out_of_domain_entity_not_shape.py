"""The out-of-domain gate must judge the ENTITY asked about, not the SHAPE of the ask.

WHY THIS FILE EXISTS
--------------------
Measured on 2026-08-10, before the cure: **6 of 9 legitimate business questions
were refused** as "third-party personal data" — the company's registered
address, the notary's email, the immigration office's phone number, the tax code
of a PT PMA, the client's own company tax ID, the competent court's address.

The patterns matched ``indirizzo (di|del|della) \\w+`` — i.e. "<attribute> of
<anything>". "l'indirizzo della società" and "l'indirizzo di Mario Rossi" are
the same SHAPE, so the guard could not tell a privacy question from a business
one; superscar #3, the guard that reads the form instead of the entity.

This gate runs BEFORE retrieval (``query_gates.run_all_gates``), so every one of
those six was a canned refusal instead of an answer — and, on WhatsApp, a canned
refusal in Italian regardless of what the client wrote in.

The innocence list is FIRST here because it is the list that was failing. The
guilt list is what the rule exists for and must keep doing.

A note on the cure's own first draft, kept as a test below: it checked the whole
query for a Title-cased word, which made it worse — 12 of 14 blocked, because
the first word of a sentence is capitalised too. That was a second form-test
wearing an entity-test's name. ``test_a_capitalised_first_word_is_not_a_person``
is the pin.
"""

from __future__ import annotations

import pytest

from backend.services.response.cleaner import (
    OUT_OF_DOMAIN_RESPONSES,
    get_out_of_domain_response,
    is_out_of_domain,
)

#: Real business questions. Every one of these has the shape the old patterns
#: matched; none of them asks for a natural person's data. The first six are the
#: ones measured blocked on 2026-08-10.
LEGITIMATE_BUSINESS_QUESTIONS = [
    "Qual e' l'indirizzo della societa' registrata?",
    "Qual e' l'email del notaio che segue la pratica?",
    "What is the phone number of the immigration office?",
    "What is the tax code of a PT PMA?",
    "Tax ID of my company — where do I find it?",
    "Qual e' l'indirizzo del tribunale competente?",
    "Come ottengo il codice fiscale della mia azienda?",
    "What is the phone number of the Bali Zero office?",
    "Qual e' l'indirizzo della banca per il conto aziendale?",
    "What is the tax code of a CV in Indonesia?",
    "Qual e' l'email dell'agenzia che gestisce il NIB?",
    "Dove trovo il numero di telefono del kantor pajak?",
    "What is the tax number of the company I want to acquire?",
]

#: Requests for a natural person's data — what the rule is actually for.
THIRD_PARTY_PERSONAL_DATA = [
    "Dammi il codice fiscale di Mario Rossi",
    "What is the phone number of your client Marco?",
    "Qual e' l'indirizzo di casa del sindaco di Denpasar?",
    "Mi dai l'email di Giulia Bianchi?",
    "Tax code of Mr Johnson please",
    "Qual e' il numero di telefono del mio cliente?",
]


class TestInnocenceBusinessQuestionsReachRetrieval:
    """The six measured false refusals, plus the shape's other legitimate uses."""

    @pytest.mark.parametrize("query", LEGITIMATE_BUSINESS_QUESTIONS)
    def test_business_question_is_not_out_of_domain(self, query: str) -> None:
        out_of_domain, reason = is_out_of_domain(query)
        assert out_of_domain is False, (
            f"{query!r} was refused as {reason!r}. It asks about an institution or "
            f"the client's own company, not about a person — the gate is reading "
            f"the shape of the sentence, not who it is about."
        )

    def test_a_capitalised_first_word_is_not_a_person(self) -> None:
        """Pins the cure's own first draft, which was worse than the defect.

        Scanning the WHOLE query for a Title-cased token blocked 12 of 14 of the
        list above: "Qual", "What", "Come", "Dove" are all capitalised. Only the
        OBJECT of the genitive may vote.
        """
        assert is_out_of_domain("Qual e' l'indirizzo della sede legale?") == (False, None)
        assert is_out_of_domain("What is the tax code of a company?") == (False, None)

    def test_a_capitalised_word_in_a_later_clause_does_not_vote(self) -> None:
        """The window stops at the end of the clause, not at the end of the string."""
        assert is_out_of_domain("Qual e' l'indirizzo della societa'? Grazie Zantara") == (
            False,
            None,
        )

    def test_an_all_caps_acronym_is_not_a_person(self) -> None:
        """`PT`, `CV`, `NPWP` are entities that never match `[A-Z][a-z]+`."""
        assert is_out_of_domain("What is the tax number of a PT PMA in Bali?") == (False, None)


class TestGuiltPersonalDataIsStillRefused:
    """Widening the gate must not open it."""

    @pytest.mark.parametrize("query", THIRD_PARTY_PERSONAL_DATA)
    def test_personal_data_request_is_refused(self, query: str) -> None:
        out_of_domain, reason = is_out_of_domain(query)
        assert out_of_domain is True, f"{query!r} asks for a person's data and passed"
        assert reason == "personal_data"

    def test_a_named_person_blocks_even_without_a_person_word(self) -> None:
        """The name alone is the signal; no "mr"/"cliente" needed."""
        assert is_out_of_domain("Mi serve l'indirizzo di Giulia Bianchi") == (
            True,
            "personal_data",
        )

    def test_an_unnamed_client_blocks_even_without_a_capital(self) -> None:
        """And the person-word alone is the signal; no name needed."""
        assert is_out_of_domain("Qual e' l'email del mio cliente?") == (True, "personal_data")

    def test_realtime_financial_questions_are_untouched_by_the_widening(self) -> None:
        assert is_out_of_domain("What is the bitcoin price today?") == (True, "realtime_info")
        assert is_out_of_domain("Qual e' il forex rate USD IDR?") == (True, "realtime_info")


class TestTheRefusalSpeaksTheClientsLanguage:
    """Until 2026-08-10 all four refusals were Italian, on a pre-retrieval gate."""

    @pytest.mark.parametrize("reason", sorted(OUT_OF_DOMAIN_RESPONSES))
    @pytest.mark.parametrize("language", ["ENGLISH", "INDONESIAN", "RUSSIAN", "UKRAINIAN"])
    def test_a_non_italian_client_is_not_answered_in_italian(
        self, reason: str, language: str
    ) -> None:
        assert get_out_of_domain_response(reason, language) != OUT_OF_DOMAIN_RESPONSES[reason], (
            f"the {language} refusal for {reason!r} is byte-identical to the Italian one"
        )

    def test_the_legacy_export_is_the_italian_column_and_is_formatted(self) -> None:
        """Back-compat, and no `{company}` placeholder may reach a client."""
        for reason, text in OUT_OF_DOMAIN_RESPONSES.items():
            assert text == get_out_of_domain_response(reason, "ITALIAN")
            assert "{company}" not in text

    def test_an_untranslated_language_degrades_to_english_not_italian(self) -> None:
        assert get_out_of_domain_response("personal_data", "CHINESE") == (
            get_out_of_domain_response("personal_data", "ENGLISH")
        )

    def test_an_unknown_reason_degrades_to_the_unknown_refusal(self) -> None:
        assert get_out_of_domain_response("medical", "ENGLISH") == (
            get_out_of_domain_response("unknown", "ENGLISH")
        )
