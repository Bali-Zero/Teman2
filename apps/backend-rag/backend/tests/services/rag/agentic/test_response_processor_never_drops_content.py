"""Guilt + innocence for the two post-generation mutators that rewrite a
finished answer: `_format_as_numbered_list` and `_add_emotional_acknowledgment`.

Measured 2026-08-10, on the live WhatsApp path (`create_default_pipeline` ->
`PostProcessingStage` -> `post_process_response`):

  * the numbered-list formatter returned ONLY the sentences whose text matched
    an action verb and discarded every other sentence — 56% / 57% / 61% of a
    five-sentence procedural answer deleted in en / it / id respectively, and
    what went with it was the Bali Zero service fee and the overstay penalty.
    The client received a tidy numbered list that reads COMPLETE. That is worse
    than an empty answer: an empty answer is visibly nothing, this is
    confidently wrong.
  * `_add_emotional_acknowledgment` carried three languages while
    `detect_language()` emits six, and defaulted to ITALIAN — reachable
    end-to-end on a Russian message (lang='ru', emotional=True).

Both are the same disease as the cleaner: a heuristic allowed to REMOVE or
REPLACE parts of an answer that already passed retrieval and the abstain gate.
"""

import typing

import pytest

from backend.services.communication import detect_language
from backend.services.rag.agentic.response_processor import (
    _add_emotional_acknowledgment,
    _format_as_numbered_list,
    _has_emotional_acknowledgment,
    post_process_response,
)

# ---------------------------------------------------------------------------
# INNOCENCE — formatting may never delete a fact
# ---------------------------------------------------------------------------

PROCEDURAL_ANSWERS = [
    pytest.param(
        "en",
        "What are the steps to extend my C1 tourist visa?",
        "To extend a C1 tourist visa you must act before it expires. "
        "Prepare your passport with at least 6 months validity. "
        "The Bali Zero service fee is IDR 1,500,000 all inclusive. "
        "Submit the application at least 7 working days before expiry. "
        "Overstaying costs IDR 1,000,000 per day.",
        ["IDR 1,500,000", "IDR 1,000,000 per day", "before it expires"],
        id="en",
    ),
    pytest.param(
        "it",
        "Quali sono i passaggi per estendere il visto turistico C1?",
        "Per estendere il visto C1 devi muoverti prima della scadenza. "
        "Prepara il passaporto con almeno 6 mesi di validita. "
        "Il costo del servizio Bali Zero e IDR 1.500.000 tutto incluso. "
        "Invia la domanda almeno 7 giorni lavorativi prima della scadenza. "
        "L'overstay costa IDR 1.000.000 al giorno.",
        ["IDR 1.500.000", "IDR 1.000.000 al giorno", "prima della scadenza"],
        id="it",
    ),
    pytest.param(
        "id",
        "Bagaimana langkah-langkah memperpanjang visa turis C1?",
        "Untuk memperpanjang visa C1 Anda harus bertindak sebelum kadaluarsa. "
        "Siapkan paspor dengan masa berlaku minimal 6 bulan. "
        "Biaya layanan Bali Zero adalah IDR 1.500.000 sudah termasuk semua. "
        "Kirim permohonan minimal 7 hari kerja sebelum kadaluarsa. "
        "Overstay dikenakan IDR 1.000.000 per hari.",
        ["IDR 1.500.000", "IDR 1.000.000 per hari", "sebelum kadaluarsa"],
        id="id",
    ),
]


@pytest.mark.parametrize(("lang", "query", "answer", "facts"), PROCEDURAL_ANSWERS)
def test_post_processing_a_procedural_answer_deletes_no_fact(
    lang: str, query: str, answer: str, facts: list[str]
) -> None:
    """End-to-end through the function the pipeline actually calls."""
    out = post_process_response(answer, query)
    missing = [f for f in facts if f not in out]
    assert not missing, f"[{lang}] post-processing deleted {missing} from the answer:\n{out}"


@pytest.mark.parametrize(("lang", "query", "answer", "facts"), PROCEDURAL_ANSWERS)
def test_the_formatter_declines_when_it_would_drop_a_sentence(
    lang: str, query: str, answer: str, facts: list[str]
) -> None:
    """The conservation guard: partial-match input is left ALONE, not filtered.

    Asserted as identity, not as "no fact missing" — the point is that a
    formatter has no licence to choose which sentences of an answer survive.
    """
    assert _format_as_numbered_list(answer, lang) == answer


def test_an_unknown_language_is_not_reformatted_with_english_verbs() -> None:
    russian = (
        "Подготовьте паспорт со сроком действия не менее 6 месяцев. "
        "Отправьте заявление за 7 рабочих дней до истечения срока."
    )
    assert _format_as_numbered_list(russian, "auto") == russian
    assert _format_as_numbered_list(russian, "ru") == russian


def test_a_language_with_no_verb_table_declines_even_when_english_verbs_match() -> None:
    """Isolates the BRANCH from the payload — the Russian test above cannot.

    Measured 2026-08-10 by mutation: restoring the old
    `action_verbs.get(language, action_verbs["en"])` fallback left the Russian
    case GREEN, because Russian prose matches no English verb and so returns
    unchanged through a different branch. The assertion held with the branch it
    names deleted. A surviving mutant is not always a missing test — sometimes
    it is a test that reaches the right answer down the wrong path.

    So: English-looking sentences, declared as a language we have no vocabulary
    for. The content is artificial on purpose; the branch under test is not.
    """
    text = "Prepare your passport. Submit the form at the immigration office."
    assert _format_as_numbered_list(text, "fr") == text
    assert _format_as_numbered_list(text, "auto") == text
    # Innocence: the same sentences under a language we DO have are numbered.
    assert _format_as_numbered_list(text, "en").startswith("1. Prepare your passport")


def test_indonesian_prose_is_not_renumbered_because_isi_hides_inside_revisi() -> None:
    """Word boundary, not substring (superscar #3).

    Under the old bare `verb in sentence` rule BOTH sentences matched the
    action verb "isi" — inside "revisi" — so this administrative prose was
    renumbered as a two-step procedure.
    """
    prose = (
        "Kami melakukan revisi administrasi untuk efisiensi proses ini. "
        "Ada revisi lain pada dokumen administrasi tersebut juga."
    )
    assert _format_as_numbered_list(prose, "id") == prose


# ---------------------------------------------------------------------------
# GUILT — the formatter must still do its job
# ---------------------------------------------------------------------------


def test_an_all_steps_answer_is_still_numbered() -> None:
    steps = (
        "Prepare your passport and two photographs. "
        "Submit the form at the immigration office. "
        "Collect the receipt from the counter."
    )
    out = _format_as_numbered_list(steps, "en")
    assert out.startswith("1. Prepare your passport")
    assert "\n2. Submit the form" in out
    assert "\n3. Collect the receipt" in out


def test_a_single_step_is_not_a_list() -> None:
    one = "Prepare your passport with at least six months of remaining validity."
    assert _format_as_numbered_list(one, "en") == one


# ---------------------------------------------------------------------------
# The emotional prefix must never speak a language the client did not use
# ---------------------------------------------------------------------------

ANSWER = "Your KITAS can be renewed within 30 days of expiry."

EXPECTED_PREFIX_MARKER = {
    "it": "Capisco",
    "en": "I understand",
    "id": "Saya mengerti",
    "ru": "Понимаю",
    "uk": "Розумію",
}


@pytest.mark.parametrize(("lang", "marker"), sorted(EXPECTED_PREFIX_MARKER.items()))
def test_the_acknowledgment_is_written_in_the_clients_language(lang: str, marker: str) -> None:
    out = _add_emotional_acknowledgment(ANSWER, lang)
    assert out.startswith(marker), f"[{lang}] got: {out[:60]!r}"
    assert out.endswith(ANSWER), "the answer itself must survive the prepend"


@pytest.mark.parametrize("lang", ["auto", "fr", "es", "de", ""])
def test_an_unknown_language_gets_no_acknowledgment_rather_than_an_italian_one(
    lang: str,
) -> None:
    """The old default was Italian. There is no safe language to guess."""
    assert _add_emotional_acknowledgment(ANSWER, lang) == ANSWER


def test_an_acknowledgment_is_not_prepended_twice() -> None:
    once = _add_emotional_acknowledgment(ANSWER, "it")
    assert _add_emotional_acknowledgment(once, "it") == once


def test_an_unknown_language_answer_is_not_judged_to_be_missing_its_acknowledgment() -> None:
    """`_has_emotional_acknowledgment` searched ENGLISH keywords in any unknown
    language, never matched, and so reported "missing" — which is precisely
    what made the caller graft a foreign sentence on."""
    assert _has_emotional_acknowledgment("Понимаю ваше беспокойство, всё решаемо.", "auto")


def test_a_russian_answer_that_already_acknowledges_is_recognised() -> None:
    assert _has_emotional_acknowledgment("Понимаю ваше беспокойство, есть решение.", "ru")


def test_a_russian_answer_without_acknowledgment_is_recognised_as_missing() -> None:
    """Innocence for the check above: "unknown language" must not become
    "always satisfied" for languages we DO have keywords for."""
    assert not _has_emotional_acknowledgment("Ваш KITAS истекает через 14 дней.", "ru")


# ---------------------------------------------------------------------------
# STRUCTURAL — the two sides must agree by construction, not by coincidence
# ---------------------------------------------------------------------------


def _emitted_languages() -> set[str]:
    """Every value `detect_language` declares it can return."""
    hints = typing.get_type_hints(detect_language)
    return set(typing.get_args(hints["return"]))


def test_detect_language_declares_the_auto_sentinel_it_actually_returns() -> None:
    """It returns "auto" whenever no marker matched — the annotation used to
    omit it, so every consumer was written against a vocabulary the function
    does not emit and silently fell through to its own default."""
    assert detect_language("xyzzy 12345") == "auto"
    assert "auto" in _emitted_languages()


def test_every_emitted_language_is_either_translated_or_explicitly_declined() -> None:
    """The 3-vs-5 drift that produced the Italian default cannot come back.

    A language the detector emits must EITHER have its own copy OR be declined
    outright — what it must never do is silently borrow another language's.
    """
    for lang in sorted(_emitted_languages()):
        out = _add_emotional_acknowledgment(ANSWER, lang)
        if out == ANSWER:
            continue  # explicitly declined - acceptable
        marker = EXPECTED_PREFIX_MARKER.get(lang)
        assert marker, f"{lang!r} is prepended text but has no declared copy of its own"
        assert out.startswith(marker), f"{lang!r} borrowed another language's copy: {out[:50]!r}"
