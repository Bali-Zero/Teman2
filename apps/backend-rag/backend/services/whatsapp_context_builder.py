"""
WhatsApp Context Builder
Builds rich context for each incoming WhatsApp message.

Responsibilities:
- Load conversation history from PostgreSQL
- Detect client language from message history
- Build & update incremental client profile (stored in conversations.metadata JSONB)
- Determine if first message
- Provide time-of-day for appropriate greetings
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Visa/service codes to detect in messages
VISA_CODES = [
    "c1",
    "c2",
    "c7a",
    "c7b",
    "c18",
    "c22a",
    "c22b",
    "d12",
    "e33g",
    "voa",
    "b211",
    "kitas",
    "kitap",
    "merp",
    "epo",
    "erp",
    "pma",
    "virtual office",
    "npwp",
    "spt",
    "freelance",
    "investor",
    "retirement",
    "spouse",
    "dependent",
    "working kitas",
    "sktt",
    "skck",
    "domicilie",
]

# Interest keywords
INTEREST_KEYWORDS = {
    "remote_work": [
        "remote work",
        "lavoro da remoto",
        "digital nomad",
        "nomade digitale",
        "kerja remote",
        "work from bali",
        "lavorare da bali",
    ],
    "company_setup": [
        "company",
        "azienda",
        "pt pma",
        "perusahaan",
        "business setup",
        "aprire azienda",
        "buka perusahaan",
    ],
    "family_relocation": [
        "family",
        "famiglia",
        "keluarga",
        "wife",
        "moglie",
        "children",
        "figli",
        "anak",
        "spouse",
        "dependent",
    ],
    "retirement": ["retirement", "pensione", "pensiun", "retire", "pensionato"],
    "investment": ["invest", "investimento", "investasi", "property", "properti", "immobiliare"],
    "tax": ["tax", "tasse", "pajak", "npwp", "spt", "fiscal"],
}

# Simple language detection patterns
LANGUAGE_PATTERNS = {
    "it": [
        r"\b(ciao|buongiorno|buonasera|grazie|prego|quanto|costa|vorrei|posso|sono|come|perch[eé]|anche|molto|questo|quello|voglio|bisogno|serve|aiuto|informazioni)\b",
    ],
    "en": [
        r"\b(hello|hi|thanks|please|how much|i want|i need|can i|what is|help|information|looking for|interested)\b",
    ],
    "id": [
        r"\b(halo|terima kasih|tolong|berapa|saya|mau|bisa|apa|bagaimana|butuh|informasi|bantu)\b",
    ],
    "de": [
        r"\b(hallo|danke|bitte|wie viel|ich|möchte|kann|brauche|hilfe|informationen)\b",
    ],
    "fr": [
        r"\b(bonjour|merci|s'il vous plaît|combien|je veux|puis-je|aide|informations)\b",
    ],
    "es": [
        r"\b(hola|gracias|por favor|cuánto|quiero|puedo|necesito|ayuda|información)\b",
    ],
    "ru": [
        r"\b(привет|спасибо|пожалуйста|сколько|хочу|могу|нужно|помощь|информация)\b",
    ],
}


def detect_language(text: str, history: list[dict[str, str]] | None = None) -> str:
    """
    Detect language from text and optionally conversation history.

    Uses pattern matching on the current message + last few messages for accuracy.
    Returns ISO 639-1 code.
    """
    # Combine current message with last 3 user messages from history for better detection
    texts_to_check = [text.lower()]
    if history:
        recent_user_msgs = [m["content"].lower() for m in history[-6:] if m.get("role") == "user"]
        texts_to_check.extend(recent_user_msgs[-3:])

    combined = " ".join(texts_to_check)

    scores = {}
    for lang, patterns in LANGUAGE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, combined, re.IGNORECASE)
            score += len(matches)
        if score > 0:
            scores[lang] = score

    if scores:
        return max(scores, key=lambda lang: scores[lang])

    return "en"  # Default to English


def extract_visa_mentions(text: str) -> list[str]:
    """Extract visa/service codes mentioned in a message."""
    text_lower = text.lower()
    found = []
    for code in VISA_CODES:
        if code in text_lower:
            found.append(code.upper())
    return list(set(found))


def extract_interests(text: str) -> list[str]:
    """Extract interest categories from a message."""
    text_lower = text.lower()
    found = []
    for interest, keywords in INTEREST_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(interest)
    return found


def get_time_of_day() -> str:
    """Get time of day in WITA (Bali timezone, UTC+8)."""
    # Simple UTC+8 offset
    now_utc = datetime.now(timezone.utc)
    hour_wita = (now_utc.hour + 8) % 24

    if 5 <= hour_wita < 12:
        return "morning"
    if 12 <= hour_wita < 17:
        return "afternoon"
    return "evening"


def infer_client_type(profile: dict[str, Any]) -> str:
    """Infer client type from their interests and discussions."""
    interests = set(profile.get("interests", []))
    visas = {v.lower() for v in profile.get("visa_discussed", [])}

    if "retirement" in interests or "retirement" in visas:
        return "retiree"
    if "company_setup" in interests or "pma" in visas:
        return "entrepreneur"
    if "remote_work" in interests or "e33g" in visas:
        return "digital_nomad"
    if "family_relocation" in interests:
        return "family_relocating"
    if "investment" in interests:
        return "investor"
    if any(v in visas for v in ["kitas", "working kitas"]):
        return "potential_expat"
    if any(v in visas for v in ["d12", "c1", "c2", "voa"]):
        return "visitor"

    return "potential_client"


async def build_context(
    phone: str,
    sender_name: str | None,
    message_text: str,
    db_pool: asyncpg.Pool | None,
) -> dict[str, Any]:
    """
    Build rich context for a WhatsApp message.

    Loads conversation history from PostgreSQL, detects language,
    builds/updates client profile, and returns everything needed
    for the system prompt and LLM call.

    Args:
        phone: Client phone number
        sender_name: WhatsApp profile name
        message_text: Current message text
        db_pool: PostgreSQL connection pool

    Returns:
        Dict with: client_name, phone, conversation_history, client_profile,
                   is_first_message, detected_language, time_of_day
    """
    wa_user_id = f"whatsapp_{phone}"
    session_id = f"wa_session_{phone}"

    conversation_history = []
    client_profile = {}
    is_first_message = True
    existing_row_id = None

    # Load from PostgreSQL
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, messages, metadata FROM conversations WHERE user_id = $1 AND session_id = $2 ORDER BY created_at DESC LIMIT 1",
                    wa_user_id,
                    session_id,
                )
                if row:
                    existing_row_id = row["id"]

                    # Load messages
                    msgs = row["messages"]
                    if isinstance(msgs, str):
                        msgs = json.loads(msgs)
                    if msgs:
                        conversation_history = msgs[-20:]  # Last 20 messages
                        is_first_message = False

                    # Load existing profile from metadata
                    meta = row["metadata"]
                    if isinstance(meta, str):
                        meta = json.loads(meta)
                    if meta:
                        client_profile = meta

        except Exception as e:
            logger.warning(f"Failed to load context for {phone}: {e}")

    # Detect language from current message + history
    detected_language = detect_language(message_text, conversation_history)

    # Update client profile incrementally
    # Preserve existing data
    if not client_profile.get("channel"):
        client_profile["channel"] = "whatsapp"
    if not client_profile.get("phone"):
        client_profile["phone"] = f"+{phone}"
    if sender_name and (
        not client_profile.get("sender_name") or client_profile["sender_name"] != sender_name
    ):
        client_profile["sender_name"] = sender_name
    if not client_profile.get("first_contact"):
        client_profile["first_contact"] = datetime.now(timezone.utc).isoformat()

    # Update detected language (use latest detection)
    client_profile["detected_language"] = detected_language

    # Update message count
    client_profile["message_count"] = client_profile.get("message_count", 0) + 1

    # Extract and merge visa mentions
    new_visas = extract_visa_mentions(message_text)
    existing_visas = set(client_profile.get("visa_discussed", []))
    existing_visas.update(new_visas)
    if existing_visas:
        client_profile["visa_discussed"] = sorted(existing_visas)

    # Extract and merge interests
    new_interests = extract_interests(message_text)
    existing_interests = set(client_profile.get("interests", []))
    existing_interests.update(new_interests)
    if existing_interests:
        client_profile["interests"] = sorted(existing_interests)

    # Infer client type
    client_profile["client_type"] = infer_client_type(client_profile)

    # Save updated profile back to PostgreSQL
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                if existing_row_id:
                    await conn.execute(
                        "UPDATE conversations SET metadata = $1::jsonb WHERE id = $2",
                        json.dumps(client_profile),
                        existing_row_id,
                    )
                # If no existing row, it will be created when we save the conversation later
        except Exception as e:
            logger.warning(f"Failed to save profile for {phone}: {e}")

    return {
        "client_name": sender_name,
        "phone": phone,
        "conversation_history": conversation_history,
        "client_profile": client_profile,
        "is_first_message": is_first_message,
        "detected_language": detected_language,
        "time_of_day": get_time_of_day(),
        # Internal — used by the router for DB operations
        "_wa_user_id": wa_user_id,
        "_session_id": session_id,
        "_existing_row_id": existing_row_id,
    }
