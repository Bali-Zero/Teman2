"""Tripwires for the stdlib-only shared client-language detector."""

from __future__ import annotations

import pytest

from backend.services.common.language_detection import detect_language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Come funziona il KITAS?", "it"),
        ("Come posso ottenere un KITAS?", "it"),
        ("Quali documenti servono per richiedere il visto?", "it"),
        ("Vorrei fare domanda per un KITAS.", "it"),
        ("Quanto dura la procedura per il visto?", "it"),
        ("Bagaimana cara mendapatkan KITAS?", "id"),
        ("Dokumen apa yang diperlukan untuk visa?", "id"),
        ("Berapa lama proses KITAS?", "id"),
        ("Saya ingin mengajukan KITAS.", "id"),
        ("Apa syarat untuk mendapatkan visa?", "id"),
        ("How does the KITAS process work?", "en"),
        ("How can I get a KITAS?", "en"),
        ("Which documents are required for the visa?", "en"),
        ("I want to apply for a KITAS.", "en"),
        ("How long does the visa process take?", "en"),
        ("Как получить KITAS?", "ru"),
        ("Какие документы нужны для визы?", "ru"),
        ("Сколько длится процесс оформления?", "ru"),
        ("Я хочу подать заявление на KITAS.", "ru"),
        ("Как оформить визу?", "ru"),
        ("Як отримати KITAS?", "uk"),
        ("Які документи потрібні для візи?", "uk"),
        ("Скільки триває процес оформлення?", "uk"),
        ("Я хочу подати заяву на KITAS.", "uk"),
        ("Як оформити візу?", "uk"),
    ],
)
def test_protocol_language_detection(text: str, expected: str) -> None:
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    ("history_text", "expected"),
    [
        ("Come funziona il KITAS?", "it"),
        ("Bagaimana cara mendapatkan KITAS?", "id"),
        ("How can I get a KITAS?", "en"),
        ("Как получить KITAS?", "ru"),
        ("Як отримати KITAS?", "uk"),
    ],
)
def test_ambiguous_short_turn_inherits_recent_user_language(
    history_text: str,
    expected: str,
) -> None:
    history = [
        {"role": "user", "content": history_text},
        {"role": "assistant", "content": "Can you clarify?"},
    ]

    assert detect_language("ok", history) == expected


@pytest.mark.parametrize(
    ("current_text", "expected"),
    [
        ("English please", "en"),
        ("Bagaimana cara mendapatkan KITAS?", "id"),
        ("Как получить KITAS?", "ru"),
        ("Як отримати KITAS?", "uk"),
    ],
)
def test_explicit_current_language_correction_wins_over_history(
    current_text: str,
    expected: str,
) -> None:
    history = [
        {"role": "user", "content": "Come funziona il KITAS?"},
        {"role": "assistant", "content": "Quale informazione ti serve?"},
    ]

    assert detect_language(current_text, history) == expected


def test_english_verb_come_is_not_an_italian_signal() -> None:
    history = [{"role": "user", "content": "Come funziona il KITAS?"}]

    assert detect_language("Please come to Bali", history) == "en"
