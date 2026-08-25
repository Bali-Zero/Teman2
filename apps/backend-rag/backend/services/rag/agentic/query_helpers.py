"""
Query Helper Functions for Agentic RAG Orchestrator

Extracted from orchestrator.py to improve modularity.
Contains:
- Language detection and wrapping
- Conversation recall detection
- Query preprocessing utilities
"""

import logging
import re

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Conversation recall trigger phrases (multilingual)
RECALL_TRIGGERS = [
    # Italian
    "ti ricordi",
    "ricordi quando",
    "di che parlavamo",
    "di che cliente",
    "il cliente di cui",
    "che mi hai detto",
    "prima hai detto",
    "il mio nome",
    "chi sono",
    "chi sono io",
    # English
    "do you remember",
    "remember when",
    "what did i say",
    "what did you say",
    "the client we discussed",
    "earlier you said",
    "you mentioned before",
    "recall our conversation",
    "what we talked about",
    "my name",
    "who am i",
    # Indonesian
    "ingat tidak",
    "kamu ingat",
    "tadi aku bilang",
    "sebelumnya",
    "klien yang tadi",
    "yang kita bahas",
]

# Indonesian language markers for detection.
#
# MATCHED AS WHOLE WORDS, never as bare substrings (see INDONESIAN_MARKER_RE below).
# Measured 2026-08-10 on the real inbound WhatsApp corpus (188 messages) plus a
# 20-question English domain corpus: the previous `marker in query_lower` scan
# misclassified 11 of those 20 plain-English questions as Indonesian, because
# "st(anda)rd", "m(anda)tory", "va(lu)e", "so(lu)tion", "inc(lu)de", "J(apa)n"
# and "cap(a)city" all embed a marker mid-word. An English speaker so classified
# is routed down the Indonesian branch and therefore receives NO language
# instruction at all — one of the two paths to the observed reply-language drift.
INDONESIAN_MARKERS = [
    # "ada" is deliberately absent: Ada is also a proper name. One ambiguous
    # token must not route an otherwise-English client question to Indonesian;
    # genuine Indonesian sentences containing "ada" carry another marker.
    "aku",
    "anda",
    "apa",
    "atau",
    "bagaimana",
    "banget",
    "beberapa",
    "belum",
    "berapa",
    "biaya",
    "bisa",
    "boleh",
    "buat",
    "bulan",
    "dari",
    "dengan",
    "dimana",
    "dong",
    "gak",
    "gimana",
    "gue",
    "gw",
    "hari",
    "harga",
    "ingin",
    "izin",
    "jelas",
    "jelaskan",
    "juga",
    "kalau",
    "kalo",
    "kamu",
    "kapan",
    "keluar",
    "kena",
    "kenapa",
    "keren",
    "lagi",
    "lu",
    "mantap",
    "masih",
    "mau",
    "mengapa",
    "mohon",
    "nggak",
    "nih",
    "pajak",
    "perlu",
    "punya",
    "sama",
    "saya",
    "selamat",
    "siapa",
    "sudah",
    "tahun",
    "terima kasih",
    "tidak",
    "tolong",
    "untuk",
    "urus",
    "yang",
]

# Indonesian is agglutinative on the right: "apa" legitimately appears as
# "apakah", "harga" as "harganya", "bisa" as "bisalah". A plain \b…\b match
# would therefore be an UNDER-match twin of the over-match it fixes — measured:
# on the same 188-message corpus a bare word-boundary matcher LOST 12 genuine
# Indonesian messages, 11 of them on "berapa" ("how much", i.e. the pricing
# question). Allowing the enclitic suffixes keeps those while still refusing
# any marker that merely sits inside a longer stem.
_INDONESIAN_ENCLITICS = r"(?:kah|nya|lah|pun|ku|mu)?"


def _whole_word_matcher(markers: list[str], suffix: str = "") -> re.Pattern[str]:
    """Compile markers so they match as WORDS, never inside a longer stem."""
    alternation = "|".join(re.escape(m) for m in sorted(markers, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternation}){suffix}\b")


INDONESIAN_MARKER_RE = _whole_word_matcher(INDONESIAN_MARKERS, _INDONESIAN_ENCLITICS)

# WhatsApp openers are elongated more often than they are spelled. Every
# matcher in this file is whole-word by design, so "ciaooo" and "grazieee" are
# unknown tokens that score ZERO for every language — and a zero score is not
# "unknown", it is the ENGLISH default, which the wrapper below renders to the
# model as a hard order to answer in English. That is the IT-in/EN-out drift
# this detector exists to prevent, reached through spelling rather than through
# vocabulary.
#
# The floor is THREE identical characters, not two, and that is load-bearing:
# Italian doubles constantly ("soggiorno", "permesso", "sarebbe") and folding a
# legitimate double would silently break markers this file already relies on.
# No marker in any list here contains a run of three.
_ELONGATION_RE = re.compile(r"(.)\1{2,}")

# The 3-character floor above leaves "graziee" and "ciaoo" — a doubled vowel is
# the commonest elongation of all, and the floor cannot be lowered globally
# without destroying real markers.
#
# It CAN be lowered for a doubled vowel at the END of a word, and the exact
# reason the rule is written this narrowly is German "muss": it is a decisive
# marker in the row below and it ends in a doubled CONSONANT, so a blanket
# trailing-double fold would silently delete it. Restricting to vowels also
# cannot invent a marker — no entry in any list here ends in a doubled vowel,
# so this fold can only recover a marker, never manufacture one. Checked
# against English words that do ("free", "three", "coffee", "committee"): each
# folds to a non-marker and changes no verdict.
_TRAILING_VOWEL_RUN_RE = re.compile(r"([aeiou])\1+\b")


def _collapse_elongation(text: str) -> str:
    """Fold elongation, so "ciaooo" and "graziee" both read as their word."""
    return _TRAILING_VOWEL_RUN_RE.sub(r"\1", _ELONGATION_RE.sub(r"\1", text))


# The same bare-substring defect lived in every Latin-script branch, and it is
# not theoretical: "in(come) tax" reads as ITALIAN and "com(merci)al licence" as
# FRENCH. The team beta test of 2026-07-28 recorded two English questions
# answered wholly in Italian with correct content — this is a mechanism that
# produces exactly that.
#
# Whole-word matching alone is not enough here, because two markers are also
# ordinary ENGLISH words: Italian "come" and French "comment". A single one of
# those is a coincidence, not a language — so they are HOMOGRAPHS and never
# decide on their own; they add one signal only after a decisive marker names
# the same language. To keep the recall that "come"/"comment" used to carry
# ("come funziona…", "comment ça marche"), the decisive lists are widened with
# the function words a real question in that language brings along.
#
# Order is preserved from the original (Italian → French → Spanish → German) as
# the tie-break after signal counting, so equal evidence resolves as before.
_LATIN_MARKERS: list[tuple[str, list[str], list[str]]] = [
    (
        "ITALIAN",
        # Decisive — none of these is an English word. "non" is deliberately
        # absent: \b makes it match "non-resident" / "non-profit", which this
        # domain says constantly.
        # "una" is deliberately absent: it is Italian AND Spanish, and Italian is
        # tested first, so it would answer a Spanish question in Italian. A marker
        # shared by two candidate languages decides neither.
        # "il" is deliberately absent too: it is an Italian article and a French
        # pronoun, so it cannot be decisive before the French signal check.
        [
            "ciao",
            "cosa",
            "voglio",
            "posso",
            "grazie",
            "perché",
            "quanto",
            "quale",
            "quali",
            "sono",
            "della",
            "vorrei",
            "devo",
            "per favore",
            "che",
            "anche",
            "gli",
            "funziona",
            "essere",
            "ottenere",
            # Greetings and courtesies, added 2026-08-25. A WhatsApp thread
            # opens with one far more often than with a business question, and
            # the row above carried exactly ONE ("ciao") — so "Buongiorno",
            # "Salve" and "Buonasera" each scored zero and were answered in
            # English. Measured on 16 real Italian openers before this change:
            # 10 returned ENGLISH.
            "buongiorno",
            "buonasera",
            "buonanotte",
            "arrivederci",
            "prego",
            "scusa",
            "scusi",
            "scusate",
            # "salve" is an English noun too (an ointment). It is DECISIVE here
            # anyway, deliberately: in an immigration/company bot the Italian
            # greeting is common and the English noun is close to unheard-of,
            # and the cost is asymmetric — a missed greeting mislabels the whole
            # reply, a stolen "salve" mislabels one query nobody sends. This is
            # the one entry in this row that knowingly breaks the shared-marker
            # rule stated above; do not read it as a licence to add more.
            "salve",
            # Question words and function words a real Italian question brings
            # along. "qual" is absent from the Spanish row ("cuál") and the
            # French row ("quel"), and bare "è" exists in neither.
            "qual",
            "è",
            "tra",
            "sapere",
            "aiuto",
            "bisogno",
            "soggiorno",
            "informazioni",
            "potete",
            "puoi",
            "volevo",
        ],
        # homographs: English "come", and English "dove" (the bird)
        ["come", "dove"],
    ),
    (
        "FRENCH",
        [
            "bonjour",
            "pourquoi",
            "merci",
            "s'il vous",
            "combien",
            "quel",
            "quelle",
            "est-ce",
            "vous",
            "je",
            "ça",
            "c'est",
            "votre",
            "nous",
            "faut",
            "avec",
            "dans",
            "être",
            "obtenir",
            # Greetings, same 2026-08-25 reason as the Italian row: this row
            # carried "bonjour" alone, so "Bonsoir" and "Salut" fell through.
            "bonsoir",
            "salut",
        ],
        ["comment"],  # homograph: English "comment"
    ),
    # Spanish and German used to carry FIVE markers each, and all five were
    # greetings or courtesies ("hola"/"gracias", "hallo"/"danke"). A client who
    # opens with a business question instead of a greeting — which is what a
    # business question looks like — scored ZERO and fell to the ENGLISH
    # default. Measured 2026-08-10: "Welche Dokumente brauche ich, um eine PT
    # PMA zu gruenden?" → ENGLISH, and the wrapper below then ordered the model
    # "YOUR ENTIRE RESPONSE MUST BE IN ENGLISH (English)".
    #
    # These rows now carry function words too, held to the same anti-homograph
    # rule the Italian and French rows document above: a marker shared with
    # English or with another candidate language decides neither, so it is not
    # a marker. Deliberately absent for that reason — German "die"/"was"/"man"/
    # "hat"/"war" (all English words), Spanish "una"/"como"/"con" (shared with
    # Italian), "para" (also an Indonesian plural marker).
    (
        "SPANISH",
        [
            "hola",
            "cómo",
            "como estas",
            "gracias",
            "por qué",
            "necesito",
            "quiero",
            "puedo",
            "quisiera",
            "cuánto",
            "cuál",
            "dónde",
            "qué",
            "documentos",
            "empresa",
            "extranjero",
            "trámite",
            "ustedes",
            "abrir",
            "están",
            "también",
            # Greetings, 2026-08-25. "hola" was the only one, so "Buenos días"
            # — the ordinary Spanish opener — scored zero and read as ENGLISH.
            # Both the accented and the bare spellings, because WhatsApp
            # clients send both.
            "buenos días",
            "buenos dias",
            "buenas tardes",
            "buenas noches",
        ],
        [],
    ),
    (
        "GERMAN",
        [
            "hallo",
            "wie geht",
            "danke",
            "warum",
            "können",
            "ich",
            "nicht",
            "und",
            "eine",
            "einen",
            "für",
            "möchte",
            "brauche",
            "benötige",
            "welche",
            "muss",
            "kann",
            "haben",
            "sind",
            "oder",
            "auch",
            "sehr",
            "bitte",
            "dokumente",
            "unternehmen",
            "gründen",
            "wie",
            # Greetings, 2026-08-25. "hallo" was the only one; "Guten Tag" and
            # its siblings scored zero and read as ENGLISH.
            "guten tag",
            "guten morgen",
            "guten abend",
            "tschüss",
        ],
        [],
    ),
]

LATIN_MARKER_RES: list[tuple[str, re.Pattern[str]]] = [
    (language, _whole_word_matcher(decisive)) for language, decisive, _homographs in _LATIN_MARKERS
]
_BY_LANGUAGE = dict(LATIN_MARKER_RES)
ITALIAN_MARKER_RE = _BY_LANGUAGE["ITALIAN"]
FRENCH_MARKER_RE = _BY_LANGUAGE["FRENCH"]
SPANISH_MARKER_RE = _BY_LANGUAGE["SPANISH"]
GERMAN_MARKER_RE = _BY_LANGUAGE["GERMAN"]

# Kept reachable so a test can assert these never decide alone.
LATIN_HOMOGRAPHS: dict[str, list[str]] = {
    language: homographs for language, _decisive, homographs in _LATIN_MARKERS if homographs
}
LATIN_HOMOGRAPH_RES: dict[str, re.Pattern[str]] = {
    language: _whole_word_matcher(homographs) for language, homographs in LATIN_HOMOGRAPHS.items()
}


def _latin_marker_score(query: str, language: str) -> int:
    """Count distinct decisive signals, then one supported homograph signal."""
    decisive_matches = {match.group(0) for match in _BY_LANGUAGE[language].finditer(query)}
    if not decisive_matches:
        return 0

    homograph_re = LATIN_HOMOGRAPH_RES.get(language)
    homograph_bonus = int(homograph_re is not None and homograph_re.search(query) is not None)
    return len(decisive_matches) + homograph_bonus


# Model Tiers
TIER_FLASH = 0
TIER_LITE = 1
TIER_PRO = 2
TIER_OPENROUTER = 3


# =============================================================================
# Language Detection
# =============================================================================


def detect_query_language(query: str) -> str:
    """
    Detect the language of a query.

    Returns a language identifier string like "ITALIAN", "CHINESE", etc.
    Returns "INDONESIAN" for Indonesian queries, "UNKNOWN" otherwise.
    """
    if not query or len(query.strip()) < 2:
        return "UNKNOWN"

    # Elongation is folded BEFORE any marker match — Indonesian included — so a
    # WhatsApp opener is scored on its word, not on its spelling. The non-Latin
    # script checks below deliberately keep reading the ORIGINAL `query`: they
    # test code points, and folding cannot help them.
    query_lower = _collapse_elongation(query.lower())

    # Check Indonesian first — WHOLE WORDS (+ enclitics) only, never substrings.
    if INDONESIAN_MARKER_RE.search(query_lower):
        return "INDONESIAN"

    # Chinese detection (contains Chinese characters)
    if any("\u4e00" <= char <= "\u9fff" for char in query):
        return "CHINESE"

    # Arabic detection
    if any("\u0600" <= char <= "\u06ff" for char in query):
        return "ARABIC"

    # Cyrillic (Russian/Ukrainian)
    if any("\u0400" <= char <= "\u04ff" for char in query):
        if any(word in query_lower for word in ["привіт", "як", "справи", "добре", "дякую"]):
            return "UKRAINIAN"
        return "RUSSIAN"

    # Latin-script markers, WHOLE WORDS only — see _LATIN_MARKERS for why.
    # Compare evidence before applying the historical order: otherwise one weak
    # early marker can mask several later signals from the actual language.
    #
    # Written as literal returns on purpose, NOT as a loop over LATIN_MARKER_RES:
    # `test_reasoning_stubs_language_coverage` derives the set of languages this
    # function can emit by walking its AST for returned string constants, so that
    # a new language cannot be added without either a translated stub or an
    # explicit declaration. A loop returning a variable makes those four
    # languages invisible to that guard — and it passes, quietly covering less.
    latin_scores = {
        "ITALIAN": _latin_marker_score(query_lower, "ITALIAN"),
        "FRENCH": _latin_marker_score(query_lower, "FRENCH"),
        "SPANISH": _latin_marker_score(query_lower, "SPANISH"),
        "GERMAN": _latin_marker_score(query_lower, "GERMAN"),
    }
    best_latin_score = max(latin_scores.values())

    if best_latin_score and latin_scores["ITALIAN"] == best_latin_score:
        return "ITALIAN"

    if best_latin_score and latin_scores["FRENCH"] == best_latin_score:
        return "FRENCH"

    if best_latin_score and latin_scores["SPANISH"] == best_latin_score:
        return "SPANISH"

    if best_latin_score and latin_scores["GERMAN"] == best_latin_score:
        return "GERMAN"

    return "ENGLISH"  # Default to English


# How each detector verdict is NAMED back to the model.
#
# Module-level on purpose: it must cover every value `detect_query_language` can
# return, and that invariant is only testable if the map is reachable from a
# test. It previously lived inside the wrapper as a literal, and ENGLISH — the
# detector's DEFAULT return, i.e. the largest bucket — was missing from it. The
# instruction therefore read "YOUR ENTIRE RESPONSE MUST BE IN the user's
# language": a self-reference naming no language and constraining nothing. That
# is one of the two paths to the reply-language drift seen in prod on
# 2026-07-30 (Indonesian question, French answer).
#
# "UNKNOWN" is deliberately absent: it is unreachable from the wrapper, which
# bails on the same `len(query.strip()) < 2` condition that produces it.
LANGUAGE_DISPLAY_NAMES = {
    "CHINESE": "CHINESE (中文)",
    "ARABIC": "ARABIC (العربية)",
    "UKRAINIAN": "UKRAINIAN (Українська)",
    "RUSSIAN": "RUSSIAN (Русский)",
    "ITALIAN": "ITALIAN (Italiano)",
    "FRENCH": "FRENCH (Français)",
    "SPANISH": "SPANISH (Español)",
    "GERMAN": "GERMAN (Deutsch)",
    "ENGLISH": "ENGLISH",
}


def wrap_query_with_language_instruction(query: str) -> str:
    """
    Wrap non-Indonesian queries with explicit language instruction.

    CRITICAL: When using function calling, Gemini often ignores system prompt
    language constraints. This function adds the language instruction directly
    to the query to ensure it's respected.

    Rules:
    - Indonesian queries -> No change (Jaksel style OK)
    - All other languages -> Add instruction to respond in SAME language, NO Jaksel
    """
    if not query or len(query.strip()) < 2:
        return query

    detected_lang = detect_query_language(query)

    if detected_lang == "INDONESIAN":
        # Indonesian detected - allow Jaksel, but still add tool instructions
        tool_instruction = """🛠️ TOOL USAGE:
Untuk pertanyaan faktual tentang visa, bisnis, pajak, harga, tim, atau regulasi:
→ SELALU gunakan vector_search tool DULU untuk mengambil informasi terverifikasi
→ Jangan jawab dari ingatan saja - cari di knowledge base
→ Jika tanya harga Bali Zero → gunakan pricing_tool
→ Jika tanya tentang tim → gunakan team_knowledge_tool

Pertanyaan User:
"""
        return tool_instruction + query

    # NOT Indonesian - add explicit instruction.
    lang_display = LANGUAGE_DISPLAY_NAMES.get(detected_lang, "the user's language")

    language_instruction = f"""
🔴 LANGUAGE: {lang_display}
🔴 YOUR ENTIRE RESPONSE MUST BE IN {lang_display}
🔴 DO NOT USE SLANG OR INFORMAL LANGUAGE unless specifically requested.

🛠️ TOOL USAGE INSTRUCTION:
→ ALWAYS use vector_search FIRST to retrieve verified documents from the knowledge base.
→ For relationship/prerequisite questions, use knowledge_graph_search AFTER vector_search (not instead of it).
→ Do NOT answer from memory alone - your evidence score depends on vector_search results.
→ WRONG: knowledge_graph_search only → Evidence=0 → ABSTAIN
→ RIGHT: vector_search → (optional) knowledge_graph_search → Answer with citations

User Query:
"""
    return language_instruction + query


# =============================================================================
# Conversation Recall Detection
# =============================================================================


def is_conversation_recall_query(query: str) -> bool:
    """
    Detect if user is asking to recall something from THIS conversation.

    These questions should NOT trigger RAG search because the information
    is in the conversation history, not in the knowledge base.

    Examples:
    - "Ti ricordi il cliente di cui abbiamo parlato?" → True
    - "Quanto costa un visto E31A?" → False
    """
    query_lower = query.lower()
    return any(trigger in query_lower for trigger in RECALL_TRIGGERS)


def format_conversation_history_for_recall(history: list[dict], max_messages: int = 20) -> str:
    """
    Format conversation history for recall prompts.

    Args:
        history: List of message dictionaries with 'role' and 'content'
        max_messages: Maximum number of messages to include

    Returns:
        Formatted string of conversation history
    """
    recent_history = history[-max_messages:]
    return "\n".join(
        [
            f"{'USER' if msg.get('role') == 'user' else 'ASSISTANT'}: {msg.get('content', '')}"
            for msg in recent_history
            if isinstance(msg, dict)
        ],
    )


def build_recall_prompt(query: str, history_text: str) -> str:
    """
    Build a prompt for conversation recall queries.

    Args:
        query: User's recall question
        history_text: Formatted conversation history

    Returns:
        Complete prompt for recall
    """
    return f"""You are ZANTARA. The user is asking you to recall something from THIS conversation.

CRITICAL: The answer is in the CONVERSATION HISTORY below. Do NOT say you don't have information - read the history!

CONVERSATION HISTORY:
{history_text}

USER QUESTION: {query}

Answer directly using information from the conversation above. Be specific with names, details, and facts the user mentioned.
Respond in the SAME language the user is using."""
