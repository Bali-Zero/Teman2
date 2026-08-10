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
    "ada",
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

# The same bare-substring defect lived in every Latin-script branch, and it is
# not theoretical: "in(come) tax" reads as ITALIAN and "com(merci)al licence" as
# FRENCH. The team beta test of 2026-07-28 recorded two English questions
# answered wholly in Italian with correct content — this is a mechanism that
# produces exactly that.
#
# Whole-word matching alone is not enough here, because two markers are also
# ordinary ENGLISH words: Italian "come" and French "comment". A single one of
# those is a coincidence, not a language — so they are HOMOGRAPHS and never
# decide on their own; they only reinforce a language already named by a
# decisive marker. To keep the recall that "come"/"comment" used to carry
# ("come funziona…", "comment ça marche"), the decisive lists are widened with
# the function words a real question in that language brings along.
#
# Order is preserved from the original (Italian → French → Spanish → German) so
# that a query these lists genuinely disagree on resolves as it did before.
_LATIN_MARKERS: list[tuple[str, list[str], list[str]]] = [
    (
        "ITALIAN",
        # Decisive — none of these is an English word. "non" is deliberately
        # absent: \b makes it match "non-resident" / "non-profit", which this
        # domain says constantly.
        # "una" is deliberately absent: it is Italian AND Spanish, and Italian is
        # tested first, so it would answer a Spanish question in Italian. A marker
        # shared by two candidate languages decides neither.
        ["ciao", "cosa", "voglio", "posso", "grazie", "perché", "quanto", "quale",
         "quali", "sono", "della", "vorrei", "devo", "per favore", "il",
         "che", "anche", "gli", "funziona", "essere"],
        ["come"],  # homograph: English "come"
    ),
    (
        "FRENCH",
        ["bonjour", "pourquoi", "merci", "s'il vous", "combien", "quel", "quelle",
         "est-ce", "vous", "je", "ça", "c'est", "votre", "nous", "faut", "avec",
         "dans", "être"],
        ["comment"],  # homograph: English "comment"
    ),
    ("SPANISH", ["hola", "cómo", "como estas", "gracias", "por qué"], []),
    ("GERMAN", ["hallo", "wie geht", "danke", "warum", "können"], []),
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

    query_lower = query.lower()

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
    #
    # Written as literal returns on purpose, NOT as a loop over LATIN_MARKER_RES:
    # `test_reasoning_stubs_language_coverage` derives the set of languages this
    # function can emit by walking its AST for returned string constants, so that
    # a new language cannot be added without either a translated stub or an
    # explicit declaration. A loop returning a variable makes those four
    # languages invisible to that guard — and it passes, quietly covering less.
    if ITALIAN_MARKER_RE.search(query_lower):
        return "ITALIAN"

    if FRENCH_MARKER_RE.search(query_lower):
        return "FRENCH"

    if SPANISH_MARKER_RE.search(query_lower):
        return "SPANISH"

    if GERMAN_MARKER_RE.search(query_lower):
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
