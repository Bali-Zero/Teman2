"""Deterministic scripted greeting turn for the WhatsApp product.

WHY THIS EXISTS (measured, cycle 359, 2026-09-01, WhatsApp thread 30)
---------------------------------------------------------------------
A bare ``halo`` — the single most likely first message a real client ever
sends — took **7m45s** and answered an English technical-error stub to an
Indonesian greeting. The chain, all of it working as written:

``QueryPlanner`` classifies the message correctly as ``QueryDomain.GREETING``;
``_DOMAIN_COLLECTIONS[GREETING]`` is ``[]`` by design (there is nothing to
retrieve for "hello"); ``wa_package_builder.build_context_package`` therefore
raises ``PackageUnbuildable("greeting_domain")``; the codex leg falls off; and
since the Gemini leg was cut for WhatsApp on 2026-08-27 there is no second
generator to hand it to, so the row takes the full retry ladder — five
attempts, ~7 minutes of backoff — and terminalizes as ``failed`` with the
localized apology (English whenever ``detect_language`` returns ``'auto'``,
which it does for most ordinary phrasings).

Nothing in that chain is a bug. The missing piece is that a greeting has an
answer and it is not a retrieval answer. Published practice says the same:
Google Dialogflow CX and Rasa both reach a scripted greeting/capability turn
BEFORE any retrieval or generation, never a generation attempt with no topic.

CONTRACT
--------
- **No LLM, no retrieval, no I/O.** Pure function over the message text.
- **Whole-message only.** ``halo`` is a greeting; ``halo, berapa harga PT
  PMA?`` is a pricing question that happens to open politely, and it MUST fall
  through to the normal route untouched. Guilt without innocence is how a
  guard eats the traffic it was meant to let past (scar family #3).
- **Conservative by construction.** Anything this module is not sure about
  returns ``None`` and costs nothing — the normal route still runs.
- **The greeting token decides the language**, not ``detect_language``. That
  detector returns ``'auto'`` for ordinary phrasings (measured 6 of 9 on
  2026-08-11) and its consumers then fall back to English. Here the entire
  input IS the greeting, so the token itself is the strongest available
  signal and there is nothing else to weigh.
- **No citation, no price, no client data.** Per ZERO-DECISIONS item 3 case
  (b), a courtesy turn carries no source line; prices come from PricingTool on
  the answering path, never from a canned string.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Single-word greetings → the language they are written in. One language per
# token on purpose: a token that would need a coin-flip (e.g. "hallo", read as
# German, Dutch or Indonesian) is assigned the reading most likely on THIS
# number's traffic, and being wrong costs a greeting in the wrong language,
# never a wrong fact.
_GREETING_TOKENS: dict[str, str] = {
    # Indonesian
    "halo": "id",
    "hallo": "id",
    "hai": "id",
    "pagi": "id",
    "siang": "id",
    "sore": "id",
    "malam": "id",
    "permisi": "id",
    "assalamualaikum": "id",
    "assalamualaykum": "id",
    # English
    "hi": "en",
    "hello": "en",
    "hey": "en",
    "hiya": "en",
    "greetings": "en",
    # Italian
    "ciao": "it",
    "buongiorno": "it",
    "buonasera": "it",
    "salve": "it",
    # Russian
    "привет": "ru",
    "здравствуйте": "ru",
    "здравствуй": "ru",
    "приветствую": "ru",
    # Ukrainian
    "привіт": "uk",
    "вітаю": "uk",
}

# Multi-word greetings, matched against the WHOLE normalized message before
# the token pass. Keys are already normalized.
_GREETING_PHRASES: dict[str, str] = {
    "selamat pagi": "id",
    "selamat siang": "id",
    "selamat sore": "id",
    "selamat malam": "id",
    "selamat datang": "id",
    "apa kabar": "id",
    "good morning": "en",
    "good afternoon": "en",
    "good evening": "en",
    "good day": "en",
    "buon giorno": "it",
    "buona sera": "it",
    "добрый день": "ru",
    "добрый вечер": "ru",
    "доброе утро": "ru",
    "доброго дня": "uk",
    "добрий день": "uk",
}

# Tokens allowed to keep a message a greeting when at least one real greeting
# token is present: a vocative or an intensifier. "halo zantara" and "hi hi"
# are greetings; "bali zero" alone is not (no greeting token → no match).
_VOCATIVE_TOKENS: frozenset[str] = frozenset(
    {
        "zantara",
        "bali",
        "zero",
        "balizero",
        "admin",
        "min",
        "kak",
        "pak",
        "bu",
        "ibu",
        "bapak",
        "mas",
        "mbak",
        "team",
        "tim",
        "there",
        "everyone",
        "all",
    }
)

# A greeting is short. The cap is a second, independent brake on over-match:
# whatever slips past the token rules, a long message is never answered from a
# canned string.
_MAX_GREETING_TOKENS = 4
_MAX_GREETING_CHARS = 40

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+", flags=re.UNICODE)

# Scripted greeting + capability turn, one per supported language. Deliberately
# names service FAMILIES and never a price: what the client may ask about, so
# the next turn lands on the answering path with a topic. English is the
# fallback for a language we recognise but do not script.
_GREETING_REPLIES: dict[str, str] = {
    "id": (
        "Halo! Saya Zantara, asisten Bali Zero.\n\n"
        "Saya bisa bantu soal:\n"
        "• Visa & izin tinggal (KITAS, KITAP, visa kunjungan)\n"
        "• Pendirian perusahaan & perizinan (PT PMA, NIB, OSS, KBLI)\n"
        "• Pajak & pelaporan (NPWP, SPT, LKPM)\n"
        "• Properti & sertifikat tanah\n\n"
        "Silakan tulis pertanyaan Anda — makin spesifik, makin tepat jawabannya."
    ),
    "en": (
        "Hello! I'm Zantara, the Bali Zero assistant.\n\n"
        "I can help you with:\n"
        "• Visas & stay permits (KITAS, KITAP, visit visas)\n"
        "• Company setup & licensing (PT PMA, NIB, OSS, KBLI)\n"
        "• Tax & reporting (NPWP, SPT, LKPM)\n"
        "• Property & land titles\n\n"
        "Just write your question — the more specific, the better the answer."
    ),
    "it": (
        "Ciao! Sono Zantara, l'assistente di Bali Zero.\n\n"
        "Posso aiutarti con:\n"
        "• Visti e permessi di soggiorno (KITAS, KITAP, visti turistici)\n"
        "• Apertura società e licenze (PT PMA, NIB, OSS, KBLI)\n"
        "• Tasse e adempimenti (NPWP, SPT, LKPM)\n"
        "• Immobili e titoli di proprietà\n\n"
        "Scrivimi pure la tua domanda — più è precisa, più la risposta sarà utile."
    ),
    "ru": (
        "Здравствуйте! Я Зантара, ассистент Bali Zero.\n\n"
        "Я могу помочь с:\n"
        "• Визами и видами на жительство (KITAS, KITAP, гостевые визы)\n"
        "• Регистрацией компании и лицензиями (PT PMA, NIB, OSS, KBLI)\n"
        "• Налогами и отчётностью (NPWP, SPT, LKPM)\n"
        "• Недвижимостью и правами на землю\n\n"
        "Напишите ваш вопрос — чем конкретнее, тем точнее ответ."
    ),
    "uk": (
        "Вітаю! Я Зантара, асистент Bali Zero.\n\n"
        "Я можу допомогти з:\n"
        "• Візами та дозволами на проживання (KITAS, KITAP, гостьові візи)\n"
        "• Реєстрацією компанії та ліцензіями (PT PMA, NIB, OSS, KBLI)\n"
        "• Податками та звітністю (NPWP, SPT, LKPM)\n"
        "• Нерухомістю та правами на землю\n\n"
        "Напишіть ваше запитання — що конкретніше, то точніша відповідь."
    ),
}

_FALLBACK_LANG = "en"


@dataclass(frozen=True)
class GreetingTurn:
    """A matched greeting and the scripted answer for it."""

    language: str
    text: str


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation and emoji, collapse whitespace.

    NFKC first so a full-width or decomposed form normalizes to the same
    tokens as the plain one.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    stripped = _PUNCT_RE.sub(" ", folded)
    return _WS_RE.sub(" ", stripped).strip()


def match_greeting(text: str | None) -> GreetingTurn | None:
    """Return the scripted turn when `text` is a bare greeting, else None.

    Never raises, never performs I/O. `None` is the safe answer and means
    "not my business" — the caller runs the normal generation route.
    """
    if not text:
        return None
    if len(text) > _MAX_GREETING_CHARS:
        return None

    normalized = _normalize(text)
    if not normalized:
        return None

    language = _GREETING_PHRASES.get(normalized)
    if language is None:
        tokens = normalized.split()
        if not tokens or len(tokens) > _MAX_GREETING_TOKENS:
            return None
        languages = [_GREETING_TOKENS.get(tok) for tok in tokens]
        # Every token must be either a greeting or an allowed vocative, and at
        # least one must be an actual greeting. A message carrying any other
        # word carries a question, and questions are not answered from here.
        for tok, lang in zip(tokens, languages, strict=True):
            if lang is None and tok not in _VOCATIVE_TOKENS:
                return None
        greeting_langs = [lang for lang in languages if lang is not None]
        if not greeting_langs:
            return None
        language = greeting_langs[0]

    reply = _GREETING_REPLIES.get(language) or _GREETING_REPLIES[_FALLBACK_LANG]
    return GreetingTurn(language=language, text=reply)
