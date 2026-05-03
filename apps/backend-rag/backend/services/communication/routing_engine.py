"""Context-Aware Routing Engine — intent classification, priority scoring, assignment.

Rule-based (no LLM cost). Classifies incoming messages into CRM-oriented
intents, scores priority using client data, and suggests team assignment.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.services.communication.models import (
    MessageIntent,
    Priority,
    RoutingDecision,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent keyword patterns (multilingual: IT, EN, ID)
# ---------------------------------------------------------------------------

_COMPLAINT_PATTERNS: list[str] = [
    # Italian
    r"\b(reclamo|lamentela|problema|inaccettabile|vergogna|schifo|assurdo|incapaci)\b",
    r"\b(non funziona|non va|non risponde|ancora aspett|troppo lento|pessim)\b",
    r"\b(deluso|arrabbiato|furioso|stufo|insoddisfatt)\b",
    # English
    r"\b(complaint|unacceptable|terrible|awful|worst|ridiculous|incompetent)\b",
    r"\b(not working|broken|still waiting|too slow|fed up|disgusted)\b",
    r"\b(disappointed|angry|furious|frustrated|unsatisfied)\b",
    # Indonesian
    r"\b(keluhan|komplain|masalah|tidak bisa|kapan selesai|terlalu lama|kecewa)\b",
]

_LEAD_PATTERNS: list[str] = [
    # Italian
    r"\b(quanto costa|preventivo|prezzo|listino|offerta|sconto|consulenza gratuita)\b",
    r"\b(vorrei apr|voglio apr|interessat[oa] a|come faccio a|come posso)\b",
    r"\b(nuova azienda|nuova societ|aprire pt|aprire pma|company setup)\b",
    # English
    r"\b(how much|price|quote|cost|offer|discount|free consultation)\b",
    r"\b(want to open|interested in|how can i|how do i|start a business)\b",
    r"\b(new company|new business|setup company|register company)\b",
    # Indonesian
    r"\b(berapa biaya|harga|penawaran|diskon|konsultasi gratis)\b",
    r"\b(ingin buka|mau buka|cara buka|mendirikan pt|bikin pt)\b",
]

_SUPPORT_PATTERNS: list[str] = [
    # Italian
    r"\b(aiuto|assistenza|supporto|non riesco|errore|bloccato)\b",
    r"\b(come si fa|dove trovo|dove posso|mi serve|ho bisogno)\b",
    r"\b(stato del|aggiornamento|update|status|tracking)\b",
    # English
    r"\b(help|support|assist|can't|error|stuck|issue)\b",
    r"\b(how to|where can|where do|i need|status|update|tracking)\b",
    # Indonesian
    r"\b(bantu|tolong|bantuan|tidak bisa|error|gimana caranya)\b",
    r"\b(bagaimana cara|dimana|status|update|perkembangan)\b",
]

_QUESTION_PATTERNS: list[str] = [
    # Italian
    r"\b(cos[ae'] |che cos|qual[ei]|perch[eé]|quando|dove|come)\b",
    r"\?$",  # ends with question mark
    # English
    r"\b(what|which|why|when|where|how|can you|could you|do you)\b",
    # Indonesian
    r"\b(apa|siapa|kapan|dimana|bagaimana|kenapa|bisa)\b",
]

_GREETING_PATTERNS: list[str] = [
    r"^(ciao|hello|hi|hey|salve|buongiorno|buonasera|halo|hallo|selamat\s)",
    r"^(good\s(morning|afternoon|evening))",
]

_SPAM_PATTERNS: list[str] = [
    r"\b(bitcoin|crypto|forex|invest\s+now|click\s+here|lottery|winner)\b",
    r"\b(free\s+money|make\s+\$|earn\s+\$|100%\s+guaranteed)\b",
    r"(https?://\S+){3,}",  # 3+ URLs = likely spam
]


def classify_intent(text: str) -> MessageIntent:
    """Classify message intent using keyword pattern matching.

    Priority order: spam → complaint → lead → support → question → greeting → unknown.

    Args:
        text: Message text.

    Returns:
        Classified MessageIntent.
    """
    if not text or not text.strip():
        return MessageIntent.UNKNOWN

    lower = text.lower().strip()

    # Spam first (block immediately)
    if _matches_any(lower, _SPAM_PATTERNS):
        return MessageIntent.SPAM

    # Complaint (highest business priority)
    if _matches_any(lower, _COMPLAINT_PATTERNS):
        return MessageIntent.COMPLAINT

    # Lead (revenue opportunity)
    if _matches_any(lower, _LEAD_PATTERNS):
        return MessageIntent.LEAD

    # Support (existing client needs help)
    if _matches_any(lower, _SUPPORT_PATTERNS):
        return MessageIntent.SUPPORT

    # Question (general inquiry)
    if _matches_any(lower, _QUESTION_PATTERNS):
        return MessageIntent.QUESTION

    # Greeting (simple salutation)
    if _matches_any(lower, _GREETING_PATTERNS):
        return MessageIntent.GREETING

    return MessageIntent.UNKNOWN


async def score_priority(
    client_id: int | None,
    intent: MessageIntent,
    db_pool: Any,
) -> tuple[Priority, bool]:
    """Score priority based on intent and CRM data.

    Args:
        client_id: CRM client ID (None for unidentified).
        intent: Classified message intent.
        db_pool: Database pool.

    Returns:
        Tuple of (Priority, is_vip).
    """
    # Intent-based base priority
    intent_priority = {
        MessageIntent.COMPLAINT: Priority.HIGH,
        MessageIntent.LEAD: Priority.NORMAL,
        MessageIntent.SUPPORT: Priority.NORMAL,
        MessageIntent.QUESTION: Priority.LOW,
        MessageIntent.GREETING: Priority.LOW,
        MessageIntent.SPAM: Priority.LOW,
        MessageIntent.FOLLOWUP: Priority.NORMAL,
        MessageIntent.UNKNOWN: Priority.NORMAL,
    }
    priority = intent_priority.get(intent, Priority.NORMAL)
    is_vip = False

    if not client_id or not db_pool:
        return priority, is_vip

    # VIP detection: count active practices
    try:
        active_count = await db_pool.fetchval(
            """
            SELECT COUNT(*) FROM practices
            WHERE client_id = $1 AND status NOT IN ('cancelled', 'completed')
            """,
            client_id,
        )
        if active_count is not None:
            if active_count >= 10:
                priority = Priority.URGENT
                is_vip = True
            elif active_count >= 5:
                if priority.value in ("low", "normal"):
                    priority = Priority.HIGH
                is_vip = True
            elif active_count >= 3:
                is_vip = True
    except Exception as e:
        logger.debug(f"VIP check failed (non-fatal): {e}")

    # Complaint always at least HIGH
    if intent == MessageIntent.COMPLAINT and priority == Priority.NORMAL:
        priority = Priority.HIGH

    return priority, is_vip


async def suggest_assignment(
    intent: MessageIntent,
    priority: Priority,
    _db_pool: Any,
) -> str | None:
    """Suggest team member assignment based on intent.

    Returns email of suggested assignee, or None for AI-handled.
    """
    # Complaints → admin (zero@balizero.com)
    if intent == MessageIntent.COMPLAINT:
        return "zero@balizero.com"

    # High-priority leads → admin
    if intent == MessageIntent.LEAD and priority in (Priority.HIGH, Priority.URGENT):
        return "zero@balizero.com"

    # Questions and greetings → Zantara AI (no assignment)
    if intent in (MessageIntent.QUESTION, MessageIntent.GREETING, MessageIntent.UNKNOWN):
        return None

    # Support → check for existing assigned team member
    return None


async def route_message(
    text: str,
    client_id: int | None,
    db_pool: Any,
    *,
    channel: str = "unknown",
) -> RoutingDecision:
    """Full routing pipeline: classify → score → assign.

    Args:
        text: Message text.
        client_id: CRM client ID (can be None).
        db_pool: Database pool.
        channel: Channel name.

    Returns:
        RoutingDecision with all fields populated.
    """
    intent = classify_intent(text)
    priority, is_vip = await score_priority(client_id, intent, db_pool)
    assignee = await suggest_assignment(intent, priority, db_pool)

    decision = RoutingDecision(
        intent=intent,
        priority=priority,
        suggested_assignee=assignee,
        client_id=client_id,
        is_vip=is_vip,
        reason=f"intent={intent.value}, vip={is_vip}, channel={channel}",
    )

    logger.info(
        f"Routing: intent={intent.value} priority={priority.value} "
        f"vip={is_vip} assignee={assignee} client={client_id}",
    )
    return decision


def _matches_any(text: str, patterns: list[str]) -> bool:
    """Check if text matches any regex pattern."""
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)
