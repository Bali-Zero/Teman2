"""
Language Detection Utilities

Responsibility: Detect language from user queries and provide language-specific instructions
for the ZANTARA persona.

Supported languages:
- Italian (it)
- English (en)
- Indonesian (id)
- Ukrainian (uk/ua)
- Russian (ru)
- Auto - Adaptive detection
"""

import re
from typing import Literal

# Cyrillic letters unique to one of the two supported Cyrillic languages —
# decide script-first instead of falling through to the Latin it/en/id
# marker race, which never had any Cyrillic entries to begin with and used
# to leave every Cyrillic message scored 0/0/0 on it/en/id and 0 on
# whichever of uk/ru lost the substring race, i.e. it only "worked" when
# the uk/ru markers happened to dominate the (unrelated) max() over all
# five languages. є/ї/ґ/і are Ukrainian-only; ы/э/ъ/ё are Russian-only —
# neither pair exists in the other alphabet, so one hit decides outright.
_RUSSIAN_ONLY_CHARS = re.compile(r"[ыэъё]")
_UKRAINIAN_ONLY_CHARS = re.compile(r"[іїєґ]")
_ANY_CYRILLIC = re.compile(r"[а-яёіїєґ]")

# Correction round 1 (cross-family review, 2026-09-25): a SINGLE quoted
# Cyrillic word inside an otherwise-Latin/English message ('Please
# translate «привіт» for me.') used to force the Cyrillic branch on the
# presence of ANY Cyrillic character at all, discarding the rest of the
# (correctly classifiable) message. Cyrillic now only decides by SCRIPT
# when it is the MAJORITY of the letters in the text — otherwise this
# falls through to the ordinary Latin scoring below, where the quoted
# word simply matches no it/en/id/foreign marker and contributes nothing.
_ANY_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

# Runs of 3+ repeated characters ("ciaooo", "graziee" -> too few to trip
# this, "noooo") collapse to one — WhatsApp clients elongate vowels for
# emphasis and it silently defeated exact-word markers below.
_ELONGATED_RUN = re.compile(r"(.)\1{2,}")

# Italian markers — greetings/pronouns/question words carry the language on
# their own even in a 1-3 word WhatsApp message; "perche" (no accent) is
# listed alongside "perché" because WA clients routinely drop the accent.
_ITALIAN_MARKERS = [
    "ciao",
    "come",
    "cosa",
    "sono",
    "voglio",
    "posso",
    "grazie",
    "quando",
    "dove",
    "perché",
    "perche",
    "quanto",
    "costa",
    "io",
    "chi",
    "sei",
    "tu",
    "ti",
    "mi",
    "che",
    "questo",
    "tutto",
    "perfetto",
    "nome",
    "ecco",
    "scusa",
    "prego",
    "vorrei",
    "potrei",
    "parlare",
    "consulente",
    "ehi",
    "ricordi",
    "chiamo",
    "sai",
    "il",
    "quale",
    "suo",
    "un",
]

# English markers. "in"/"a"/"e" are deliberately excluded — they are also
# bare Italian words ("in", the article "a" doesn't apply but "e" = "and"
# does), and would have contributed evidence to the wrong language on the
# very short messages where a single marker decides the verdict.
_ENGLISH_MARKERS = [
    "hello",
    "what",
    "how",
    "can",
    "want",
    "need",
    "please",
    "is",
    "you",
    "your",
    "why",
    "hi",
    "which",
    "the",
    "and",
    "to",
    "for",
    "would",
    "my",
    "this",
    "do",
    "does",
    "will",
    "client",
    "clients",
    "company",
    "thanks",
    "thank",
    "hey",
    "speak",
    "talk",
    "contact",
    "human",
    "help",
    "documents",
    "document",
    "cost",
    "price",
    "much",
    "when",
    "where",
    "who",
    "register",
    "registration",
    "required",
    "capital",
    "are",
    "that",
    "from",
    "with",
    "about",
]

# Indonesian markers. "cara" ("way/method") is deliberately excluded — it is
# also the Italian word for "dear" (feminine); "di" is excluded because it
# is also the Italian word for "of". Both are common enough in each
# language that keeping them risks the wrong verdict on a single-marker
# message, which is exactly the failure mode this fix targets.
_INDONESIAN_MARKERS = [
    "apa",
    "bagaimana",
    "siapa",
    "dimana",
    "kapan",
    "mengapa",
    "saya",
    "kamu",
    "bisa",
    "mau",
    "terima",
    "kasih",
    "bantuan",
    "bantuannya",
    "berapa",
    "biaya",
    "klien",
    "yang",
    "untuk",
    "belum",
    "gimana",
    "kalau",
    "ini",
    "itu",
    "mana",
    "jelaskan",
    "masih",
    "karena",
    "wajib",
    "aku",
    "saja",
    "dan",
    "atau",
    "juga",
    "tidak",
    "ada",
    "akan",
    "sudah",
    "dengan",
    "dari",
    "ke",
    "pada",
    "tolong",
    "mohon",
    "silakan",
    "boleh",
    "jangan",
    "harus",
    "bulan",
    "tahun",
    "hari",
    "sama",
    "lapor",
    "laporan",
    "modal",
    "proses",
    "dokumen",
    "syarat",
    "izin",
    "usaha",
    "perusahaan",
    "kirim",
    "bayar",
    "halo",
    "kena",
    "punya",
    "ingin",
    "minta",
]

# Ukrainian/Russian marker fallback — only reached when a Cyrillic message
# has neither a Ukrainian-only nor a Russian-only letter (e.g. shared
# vocabulary like "как"/"что"), so script alone can't decide.
_UKRAINIAN_MARKERS = [
    "привіт",
    "як",
    "справи",
    "добре",
    "дякую",
    "будь ласка",
    "допоможіть",
    "це",
    "що",
    "чому",
]

_RUSSIAN_MARKERS = [
    "привет",
    "как",
    "дела",
    "хорошо",
    "спасибо",
    "пожалуйста",
    "помогите",
    "это",
    "что",
    "почему",
]

# Correction round 1 (cross-family review, 2026-09-25): the it/en/id marker
# lists above were expanded far enough that ordinary Spanish/French/German/
# Portuguese/Dutch/Tagalog/Malay text started winning a confident it/en/id
# verdict on a single shared word ("un" ES/FR/IT, "il" FR/IT, "mi" ES/IT,
# "nome" PT/IT, "contact" NL/EN, "documents"/"documentos" FR/EN, "boleh"/
# "dokumen" MS/ID) — none of these SEVEN languages are in this function's
# return vocabulary, so a confident it/en/id label on them is a worse
# outcome than 'auto': wa_outbox_worker._maybe_send_apology only consults
# thread history when detect_language returns 'auto', so a false non-auto
# label skips that fallback entirely, and a false 'it' also wrongly enables
# the emotional-acknowledgment insert in response_processor. These lists
# exist ONLY to detect "this is none of it/en/id" — never returned directly
# — so they favor words genuinely absent from Indonesian/Italian/English
# over exhaustive coverage; the guard in detect_language() below treats a
# tie between an in-vocabulary language and any of these as 'auto', so a
# short list still wins as long as ONE of its words is present alongside
# whatever it/en/id word the message coincidentally shares.
_SPANISH_MARKERS = [
    "hola",
    "gracias",
    "por favor",
    "cuánto",
    "cuanto",
    "cuesta",
    "dónde",
    "donde",
    "cómo",
    "cuándo",
    "cuando",
    "quiero",
    "necesito",
    "puedo",
    "perdón",
    "perdon",
    "señor",
    "señora",
    "visado",
    "pasaporte",
    "empresa",
    "documento",
    "documentos",
    "ayuda",
    "adiós",
    "adios",
    "está",
    "esta",
    "porque",
]

_FRENCH_MARKERS = [
    "bonjour",
    "bonsoir",
    "merci",
    "s'il vous plaît",
    "s'il vous plait",
    "combien",
    "coûte",
    "coute",
    "où",
    "comment",
    "je",
    "voudrais",
    "besoin",
    "pardon",
    "monsieur",
    "madame",
    "passeport",
    "entreprise",
    "aide",
    "au revoir",
    "voici",
    "voilà",
    "voila",
    "faut",
]

_GERMAN_MARKERS = [
    "hallo",
    "danke",
    "bitte",
    "wieviel",
    "wie viel",
    "kostet",
    "wo",
    "wann",
    "warum",
    "ich",
    "brauche",
    "möchte",
    "moechte",
    "visum",
    "reisepass",
    "unternehmen",
    "dokument",
    "dokumente",
    "hilfe",
    "guten tag",
    "guten morgen",
    "tschüss",
    "tschuss",
    "ein",
    "eine",
]

_PORTUGUESE_MARKERS = [
    "olá",
    "ola",
    "obrigado",
    "obrigada",
    "quanto",
    "custa",
    "onde",
    "quando",
    "preciso",
    "gostaria",
    "desculpe",
    "senhor",
    "senhora",
    "visto",
    "passaporte",
    "empresa",
    "documento",
    "documentos",
    "ajuda",
    "bom dia",
    "boa tarde",
    "qual",
    "prazo",
]

_DUTCH_MARKERS = [
    "hallo",
    "dank je",
    "dank u",
    "alsjeblieft",
    "alstublieft",
    "hoeveel",
    "kost",
    "waar",
    "wanneer",
    "waarom",
    "ik",
    "wil",
    "nodig",
    "paspoort",
    "visum",
    "bedrijf",
    "document",
    "documenten",
    "hulp",
    "goedemorgen",
    "goedemiddag",
    "kan",
    "je",
    "contact",
    "opnemen",
    "morgen",
]

_TAGALOG_MARKERS = [
    "kumusta",
    "salamat",
    "paano",
    "saan",
    "bakit",
    "magkano",
    "puwede",
    "pwede",
    "hindi",
    "opo",
    "po",
    "kailan",
    "gusto",
    "mga",
]

# Malay-specific — deliberately excludes vocabulary Malay shares with
# Indonesian (e.g. "boleh"/"tidak"/"kena"/"punya"/"tapi"/"bila"), because
# those would just double-count against _INDONESIAN_MARKERS instead of
# proving the text is Malay rather than Indonesian.
_MALAY_MARKERS = [
    "nak",
    "hantar",
    "esok",
    "caj",
    "awak",
    "kat",
    "mesti",
    "lah",
]

_FOREIGN_MARKER_LISTS: dict[str, list[str]] = {
    "es": _SPANISH_MARKERS,
    "fr": _FRENCH_MARKERS,
    "de": _GERMAN_MARKERS,
    "pt": _PORTUGUESE_MARKERS,
    "nl": _DUTCH_MARKERS,
    "tl": _TAGALOG_MARKERS,
    "ms": _MALAY_MARKERS,
}


def _count_matches(markers: list[str], text: str, use_word_boundary: bool = True) -> int:
    """Count how many markers appear in text."""
    count = 0
    for marker in markers:
        if use_word_boundary:
            # Word boundary works for Latin scripts
            if re.search(r"\b" + re.escape(marker) + r"\b", text):
                count += 1
        else:
            # Simple substring match for Cyrillic/non-Latin scripts
            if marker in text:
                count += 1
    return count


def detect_language(text: str) -> Literal["it", "en", "id", "uk", "ru", "auto"]:
    """
    Detect language from query text with Italian focus.

    Args:
        text: User query text

    Returns:
        One of "it", "en", "id", "uk", "ru", or **"auto"** when the evidence
        is weak (no marker matched), tied (two-plus languages matched the
        same number of markers — a genuinely mixed or too-short message,
        e.g. "ok", "?", an emoji, or "ciao hello apa"), or when the message
        is confidently in a language OUTSIDE this vocabulary (Spanish,
        French, German, Portuguese, Dutch, Tagalog, Malay — see the
        cross-family review correction below). "auto" is a real, frequently-
        returned value — the annotation omitted it and the docstring listed
        only three of the six, so callers were written against a vocabulary
        this function does not emit and silently took their own
        `.get(...)` default instead (measured 2026-08-10:
        `_add_emotional_acknowledgment` defaulted to Italian).
        `get_language_instruction` below has always had an "auto" entry.
    """
    if not text:
        return "it"

    text_lower = _ELONGATED_RUN.sub(r"\1", text.lower())

    # Cyrillic is decidable by SCRIPT — but only once Cyrillic letters are
    # the MAJORITY of the letters in the text (correction round 1,
    # 2026-09-25: a single quoted Cyrillic word inside an English sentence,
    # 'Please translate «привіт» for me.', used to force this branch on ANY
    # Cyrillic character at all and discard the rest of the — correctly
    # classifiable as English — message).
    cyrillic_letters = len(_ANY_CYRILLIC.findall(text_lower))
    total_letters = len(_ANY_LETTER.findall(text_lower))
    if total_letters > 0 and cyrillic_letters * 2 > total_letters:
        if _RUSSIAN_ONLY_CHARS.search(text_lower):
            return "ru"
        if _UKRAINIAN_ONLY_CHARS.search(text_lower):
            return "uk"
        uk_score = _count_matches(_UKRAINIAN_MARKERS, text_lower, use_word_boundary=False)
        ru_score = _count_matches(_RUSSIAN_MARKERS, text_lower, use_word_boundary=False)
        if uk_score == ru_score:
            return "auto"
        return "uk" if uk_score > ru_score else "ru"

    it_score = _count_matches(_ITALIAN_MARKERS, text_lower)
    en_score = _count_matches(_ENGLISH_MARKERS, text_lower)
    id_score = _count_matches(_INDONESIAN_MARKERS, text_lower)

    scores = {"it": it_score, "en": en_score, "id": id_score}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_lang, top_score = ranked[0]
    runner_up_score = ranked[1][1]

    # Weak (nothing matched) or tied (two-plus of it/en/id matched equally,
    # e.g. a mixed-language message) evidence both mean "don't guess".
    if top_score == 0 or top_score == runner_up_score:
        return "auto"

    # Foreign-language guard (correction round 1, 2026-09-25): it/en/id's
    # marker lists share individual WORDS with languages outside this
    # function's vocabulary ("un"/"il"/"mi"/"nome" are also Spanish/French/
    # Portuguese; "contact"/"documents" are also Dutch/French; "boleh"/
    # "dokumen" are also Malay) — a real Spanish/French/German/Portuguese/
    # Dutch/Tagalog/Malay message can score a "confident" it/en/id verdict
    # on exactly one such shared word. If ANY out-of-vocabulary language
    # scores at least as high as the winning in-vocabulary language, the
    # evidence does not actually distinguish "it/en/id" from "none of the
    # above" — abstain rather than borrow a neighbour's label.
    foreign_max = max(
        (_count_matches(markers, text_lower) for markers in _FOREIGN_MARKER_LISTS.values()),
        default=0,
    )
    if foreign_max >= top_score:
        return "auto"

    return top_lang  # type: ignore[return-value]


def get_language_instruction(language: str) -> str:
    """
    Get simplified language-specific instruction for the system prompt.
    """
    instructions = {
        "it": """
<language_instruction>
    **LINGUA OBBLIGATORIA: ITALIANO**
    Tu sei ZANTARA, consulente esperto di Bali Zero.
    Il tuo tono è professionale, diretto e orientato alla soluzione.
    Inizia sempre con la risposta diretta.
</language_instruction>
""",
        "en": """
<language_instruction>
    **MANDATORY LANGUAGE: ENGLISH**
    You are ZANTARA, expert consultant for Bali Zero.
    Your tone is professional, direct, and solution-oriented.
    Always start with the direct answer.
</language_instruction>
""",
        "id": """
<language_instruction>
    **BAHASA WAJIB: INDONESIA**
    Kamu adalah ZANTARA, konsultan ahli dari Bali Zero.
    Gunakan gaya "Business Jaksel" (campuran Bahasa + istilah bisnis Inggris) yang profesional.
    Langsung jawab intinya.
</language_instruction>
""",
        "uk": """
<language_instruction>
    **ОБОВ'ЯЗКОВА МОВА: УКРАЇНСЬКА**
    Ти ZANTARA, експерт-консультант Bali Zero.
    Твій тон професійний, прямий та орієнтований на рішення.
    Завжди починай з прямої відповіді.
</language_instruction>
""",
        "ua": """
<language_instruction>
    **ОБОВ'ЯЗКОВА МОВА: УКРАЇНСЬКА**
    Ти ZANTARA, експерт-консультант Bali Zero.
    Твій тон професійний, прямий та орієнтований на рішення.
    Завжди починай з прямої відповіді.
</language_instruction>
""",
        "ru": """
<language_instruction>
    **ОБЯЗАТЕЛЬНЫЙ ЯЗЫК: РУССКИЙ**
    Ты ZANTARA, эксперт-консультант Bali Zero.
    Твой тон профессиональный, прямой и ориентированный на решение.
    Всегда начинай с прямого ответа.
</language_instruction>
""",
        "auto": """
**LANGUAGE INSTRUCTION: ADAPTIVE**
- Respond in the SAME language as the user.
- Maintain a professional and expert tone.
""",
    }

    return instructions.get(language, instructions["auto"])
