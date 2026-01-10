"""
Query Helper Functions for Agentic RAG Orchestrator

Extracted from orchestrator.py to improve modularity.
Contains:
- Language detection and wrapping
- Conversation recall detection
- Query preprocessing utilities
"""

import logging
from typing import Literal

from app.core.config import settings

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
    # Indonesian
    "ingat tidak",
    "kamu ingat",
    "tadi aku bilang",
    "sebelumnya",
    "klien yang tadi",
    "yang kita bahas",
]

# Indonesian language markers for detection
INDONESIAN_MARKERS = [
    "apa",
    "bagaimana",
    "siapa",
    "dimana",
    "kapan",
    "mengapa",
    "yang",
    "dengan",
    "untuk",
    "dari",
    "saya",
    "aku",
    "kamu",
    "anda",
    "bisa",
    "mau",
    "ingin",
    "perlu",
    "tolong",
    "halo",
    "selamat",
    "terima kasih",
    "gimana",
    "gue",
    "gw",
    "lu",
    "dong",
    "nih",
    "banget",
    "keren",
    "mantap",
    "boleh",
]

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

    # Check Indonesian first
    indo_count = sum(1 for marker in INDONESIAN_MARKERS if marker in query_lower)
    if indo_count >= 1:
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

    # Italian
    if any(
        word in query_lower
        for word in ["ciao", "come", "cosa", "voglio", "posso", "grazie", "perché"]
    ):
        return "ITALIAN"

    # French
    if any(
        word in query_lower
        for word in ["bonjour", "comment", "pourquoi", "merci", "s'il vous"]
    ):
        return "FRENCH"

    # Spanish
    if any(
        word in query_lower
        for word in ["hola", "cómo", "como estas", "gracias", "por qué"]
    ):
        return "SPANISH"

    # German
    if any(
        word in query_lower for word in ["hallo", "wie geht", "danke", "warum", "können"]
    ):
        return "GERMAN"

    return "ENGLISH"  # Default to English


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

    # NOT Indonesian - add explicit instruction
    lang_display = {
        "CHINESE": "CHINESE (中文)",
        "ARABIC": "ARABIC (العربية)",
        "UKRAINIAN": "UKRAINIAN (Українська)",
        "RUSSIAN": "RUSSIAN (Русский)",
        "ITALIAN": "ITALIAN (Italiano)",
        "FRENCH": "FRENCH (Français)",
        "SPANISH": "SPANISH (Español)",
        "GERMAN": "GERMAN (Deutsch)",
    }.get(detected_lang, "the user's language")

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


def format_conversation_history_for_recall(
    history: list[dict], max_messages: int = 20
) -> str:
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
        ]
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
