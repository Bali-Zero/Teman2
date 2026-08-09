"""Lightweight, history-aware language detection for channel boundaries.

This module intentionally depends only on the Python standard library.  API
processes can therefore classify a client message without importing a RAG or
communication package whose ``__init__`` performs eager service imports.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final, Literal, TypeAlias

LanguageCode: TypeAlias = Literal["it", "en", "id", "uk", "ru", "de", "fr", "es"]

_LANGUAGE_PATTERNS: Final[dict[LanguageCode, re.Pattern[str]]] = {
    "it": re.compile(
        r"\b(?:ciao|buongiorno|buonasera|grazie|prego|quanto|costa|vorrei|"
        r"posso|sono|cosa|quando|dove|perch[eé]|anche|molto|quest[oaie]|"
        r"quell[oaie]|voglio|bisogno|serve|aiuto|informazioni?|visti?|"
        r"aprire|societ[aà]|aziend[ae]|italian[oa]|"
        r"come\s+(?:funzion(?:a|ano)|posso|faccio|si|ottenere|richiedere|fare)|"
        r"qual(?:e|i)?|document[io]|servono|richied\w*|ott(?:en|eng)\w*|"
        r"fare\s+domanda|domand[ae]|procedura|requisit[io]|necessari[oaie])\b",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(?:hello|hi|thanks?|please|how\s+much|how|i\s+want|i\s+need|"
        r"can\s+i|what\s+is|what|help|information|looking\s+for|interested|"
        r"english|costs?|which|documents?|required|requirements?|apply|"
        r"process|works?|get|takes?)\b",
        re.IGNORECASE,
    ),
    "id": re.compile(
        r"\b(?:halo|terima\s+kasih|tolong|berapa|biaya|saya|mau|bisa|apa|"
        r"bagaimana|butuh|informasi|bantu(?:an)?|bahasa\s+indonesia|gimana|"
        r"cara|mendapatkan|mengurus|mengajukan|dokumen|diperlukan|syarat|"
        r"persyaratan|proses|lama|ingin|permohonan|daftar|untuk)\b",
        re.IGNORECASE,
    ),
    "uk": re.compile(
        r"\b(?:привіт|скільки|коштує|віза|візи|дякую|будь\s+ласка|"
        r"допоможіть|допомога|допомогу|потрібн\w*|хочу|можу|це|що|чому|"
        r"українськ\w*|як|отрим\w*|які|документи|документів|документах|"
        r"триває|тривати|процес|оформ(?:ити|лення|лювати)|подати|заяв\w*|"
        r"віз\w*|вимог\w*)\b",
        re.IGNORECASE,
    ),
    "ru": re.compile(
        r"\b(?:привет|сколько|стоит|виза|визы|спасибо|пожалуйста|помогите|"
        r"помощь|нужн\w*|хочу|могу|это|что|почему|русск\w*|как|получ\w*|"
        r"какие|документы|документов|документах|длится|процесс|"
        r"оформ(?:ить|ление|ления|лять|ляется)|подать|заявлен\w*|виз\w*|"
        r"требован\w*)\b",
        re.IGNORECASE,
    ),
    "de": re.compile(
        r"\b(?:hallo|danke|bitte|wie\s+viel|ich|möchte|kann|brauche|hilfe|"
        r"informationen|deutsch)\b",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        r"\b(?:bonjour|merci|s['’]il\s+vous\s+plaît|combien|je\s+veux|"
        r"puis-je|aide|informations|français)\b",
        re.IGNORECASE,
    ),
    "es": re.compile(
        r"\b(?:hola|gracias|por\s+favor|cuánto|quiero|puedo|necesito|"
        r"ayuda|información|español)\b",
        re.IGNORECASE,
    ),
}


def _score_text(text: str) -> dict[LanguageCode, int]:
    """Return positive marker counts for one message."""
    return {
        language: len(tuple(pattern.finditer(text)))
        for language, pattern in _LANGUAGE_PATTERNS.items()
        if pattern.search(text)
    }


def _highest_scoring_language(scores: Mapping[LanguageCode, int]) -> LanguageCode | None:
    """Resolve a score map, preserving pattern order as the tie-breaker."""
    if not scores:
        return None
    return max(scores, key=scores.__getitem__)


def detect_language(
    text: str,
    history: Sequence[Mapping[str, str]] | None = None,
) -> LanguageCode:
    """Detect an ISO language code from a message and recent user history.

    A signal in the current message always wins.  This lets a short explicit
    correction such as ``English please`` override an older Italian thread.
    When the current turn is ambiguous, the last three user messages provide
    continuity without another database read.  Unknown input defaults to
    English, matching the existing WhatsApp context-builder contract.
    """
    current_language = _highest_scoring_language(_score_text(text))
    if current_language is not None:
        return current_language

    history_scores: dict[LanguageCode, int] = {}
    if history:
        recent_user_texts = [
            message.get("content", "")
            for message in history
            if message.get("role") == "user"
            and isinstance(message.get("content"), str)
            and message.get("content")
        ][-3:]
        for user_text in recent_user_texts:
            for language, score in _score_text(user_text).items():
                history_scores[language] = history_scores.get(language, 0) + score

    return _highest_scoring_language(history_scores) or "en"
