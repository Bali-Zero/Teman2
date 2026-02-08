"""
ReAct Reasoning Utilities

Helper functions extracted from reasoning.py to reduce file complexity.
Contains: domain detection, evidence scoring, tool validation, team query detection.
"""

import logging
import re
from typing import Any

from backend.app.core.config import settings
from backend.app.core.constants import EvidenceScoreConstants

logger = logging.getLogger(__name__)


def get_critical_domain_type(query: str) -> str:
    """
    Determine the type of critical domain for metrics.

    Analyzes the query text to identify which business domain it relates to.
    Used for routing decisions and metrics tracking.

    Args:
        query: The user's query string

    Returns:
        Domain type: "visa", "legal", "pricing", "procedure", or "business_complex"

    Examples:
        >>> get_critical_domain_type("How do I get a KITAS?")
        "visa"
        >>> get_critical_domain_type("What are the PPh 21 rates?")
        "pricing"
    """
    query_lower = query.lower()

    visa_keywords = {
        "visa",
        "kitas",
        "kitap",
        "immigration",
        "imigrasi",
        "stay permit",
        "residence permit",
        "b211",
        "e33",
        "e28",
        "d1",
        "d2",
    }
    legal_keywords = {
        "legge",
        "law",
        "contract",
        "contratto",
        "compliance",
        "regolamento",
        "regulation",
        "pasal",
        "ayat",
        "legal",
        "legale",
    }
    pricing_keywords = {
        "prezzo",
        "price",
        "costo",
        "cost",
        "tariffa",
        "fee",
        "fees",
        "quanto costa",
        "how much",
        "harga",
        "biaya",
    }
    procedure_keywords = {
        "documento",
        "document",
        "procedura",
        "procedure",
        "requisito",
        "requirement",
        "documentazione",
        "documentation",
    }

    if any(kw in query_lower for kw in visa_keywords):
        return "visa"
    elif any(kw in query_lower for kw in legal_keywords):
        return "legal"
    elif any(kw in query_lower for kw in pricing_keywords):
        return "pricing"
    elif any(kw in query_lower for kw in procedure_keywords):
        return "procedure"
    else:
        return "business_complex"


def is_critical_domain(query: str, intent_type: str) -> bool:
    """
    Determine if a query is in a critical domain that requires strict ABSTAIN.

    Critical domains: Visa/Immigration, Legal, Pricing, Business complex, Document procedures
    """
    query_lower = query.lower()

    if intent_type in {"business_complex", "business_strategic"}:
        return True

    critical_keywords = {
        # Visa/Immigration
        "visa",
        "kitas",
        "kitap",
        "immigration",
        "imigrasi",
        "stay permit",
        "residence permit",
        "b211",
        "e33",
        "e28",
        "d1",
        "d2",
        # Legal
        "legge",
        "law",
        "contract",
        "contratto",
        "compliance",
        "regolamento",
        "regulation",
        "pasal",
        "ayat",
        "legal",
        "legale",
        # Pricing
        "prezzo",
        "price",
        "costo",
        "cost",
        "tariffa",
        "fee",
        "fees",
        "quanto costa",
        "how much",
        "harga",
        "biaya",
        # Critical procedures
        "documento",
        "document",
        "procedura",
        "procedure",
        "requisito",
        "requirement",
        "documentazione",
        "documentation",
    }

    return any(keyword in query_lower for keyword in critical_keywords)


def is_valid_tool_call(tool_call: Any) -> bool:
    """
    Validate that a tool call has all required fields.

    Prevents using partially parsed tool calls that could cause downstream errors.
    """
    if tool_call is None:
        return False
    if not hasattr(tool_call, "tool_name") or not tool_call.tool_name:
        return False
    if not isinstance(tool_call.tool_name, str):
        return False
    if not hasattr(tool_call, "arguments"):
        return False
    return tool_call.arguments is not None


def calculate_evidence_score(
    sources: list[dict] | None,
    context_gathered: list[str],
    query: str,
) -> float:
    """
    Calculate evidence score based on source quality and context relevance.

    This score helps determine confidence in RAG responses and whether to
    proceed with answering or abstain due to insufficient evidence.

    Scoring Formula:
        - Base score: 0.0
        - High-quality source bonus (+0.5): At least 1 source with score > 0.3
        - Multiple sources bonus (+0.2): More than 3 total sources
        - Context relevance bonus (+0.3): Context contains query keywords
        - Maximum score: 1.0

    Args:
        sources: List of source dictionaries with 'score' field
        context_gathered: List of context strings from tool results
        query: Original user query string

    Returns:
        Evidence score between 0.0 and 1.0

    Note:
        A score >= 0.5 is generally considered sufficient for answering.
        A score < 0.5 may trigger ABSTAIN response for critical domains.
    """
    base_score = 0.0

    if sources:
        high_quality_sources = [
            s
            for s in sources
            if isinstance(s, dict)
            and s.get("score", 0.0) > EvidenceScoreConstants.HIGH_QUALITY_SOURCE_THRESHOLD
        ]
        if len(high_quality_sources) >= 1:
            base_score += EvidenceScoreConstants.HIGH_QUALITY_SOURCE_BONUS

        if len(sources) > EvidenceScoreConstants.MIN_SOURCES_FOR_BONUS:
            base_score += EvidenceScoreConstants.MULTIPLE_SOURCES_BONUS
    elif context_gathered:
        total_context_length = sum(len(ctx) for ctx in context_gathered)
        if total_context_length > EvidenceScoreConstants.SUBSTANTIAL_CONTEXT_LENGTH:
            base_score += EvidenceScoreConstants.CONTEXT_KEYWORD_BONUS

    # Check if context contains query keywords
    if context_gathered:
        query_lower = query.lower()
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
        }
        query_words = [w for w in query_lower.split() if len(w) > 3 and w not in stop_words]
        context_text = " ".join(context_gathered).lower()
        matches = sum(1 for word in query_words if word in context_text)
        if matches >= 2 or (matches >= 1 and len(query_words) <= 3):
            base_score += EvidenceScoreConstants.CONTEXT_KEYWORD_BONUS

    return min(base_score, 1.0)


def detect_team_query(query: str) -> tuple[bool, str, str]:
    """
    Detect if query is asking about team members.

    Returns:
        Tuple of (is_team_query, query_type, search_term)
    """
    if not isinstance(query, str):
        return False, "", ""

    q = query.strip()
    if not q:
        return False, "", ""

    ql = q.lower()

    # 1) List-all team requests
    list_all_markers = (
        "list all team",
        "list team",
        "team members",
        "membri del team",
        "lista team",
        "elenco team",
        "tutti i membri",
        "quanti dipendenti",
        "vostri dipendenti",
        f"i dipendenti {settings.COMPANY_NAME.lower()}",
        "dipendenti del team",
        "tutto lo staff",
        "vostro staff",
        "il vostro personale",
    )
    if any(marker in ql for marker in list_all_markers):
        return True, "list_all", ""

    # 2) Email lookup
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", q)
    if email_match:
        return True, "search_by_email", email_match.group(0)

    # 3) Role/title lookup - ONLY with team context
    team_context_markers = (
        "chi si occupa",
        "chi gestisce",
        "chi segue",
        "chi è il",
        "chi è la",
        "who handles",
        "who manages",
        "who is the",
        "who is your",
        "your team",
        "nel team",
        "del team",
        "in the team",
        "team member",
        "staff member",
        "il vostro",
        "la vostra",
        "avete qualcuno",
        "c'è qualcuno",
        "esperto di",
        "specialist",
        "manager",
        "responsabile",
    )
    has_team_context = any(marker in ql for marker in team_context_markers)

    if has_team_context:
        role_map: dict[str, tuple[str, ...]] = {
            "ceo": ("ceo", "chief executive", "amministratore delegato", "a.d.", "ad "),
            "founder": ("founder", "cofounder", "co-founder", "fondatore", "fondatrice"),
            "tax": ("tax", "tasse", "fiscale", "fiscal", "pajak"),
            "visa": ("visa", "visti", "immigrazione", "immigration"),
            "setup": ("setup", "set up", "onboarding"),
            "legal": ("legal", "legale", "law", "avvocato"),
            "property": ("property", "immobiliare", "real estate"),
            "marketing": ("marketing", "social", "content"),
            "support": ("support", "assistenza", "customer care"),
        }
        for role, keywords in role_map.items():
            if any(k in ql for k in keywords):
                return True, "search_by_role", role

    # 4) Name lookup patterns
    name_patterns = (
        r"\bchi\s*[eè]['']?\s*(?P<term>[^?.,!;:\n]{1,64})",
        r"\bwho\s+is\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\btell\s+me\s+about\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\binfo(?:rmazioni)?\s+su\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\bdimmi\s+(?:di\s+)?(?P<term>[^?.,!;:\n]{1,64})",
        r"\bparlami\s+di\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\bconosci\s+(?!qualche|qualcuno|qualcosa|un\s|una\s|il\s|la\s|dei\s|delle\s|alcuni|alcune|ristorante|posto|luogo|bar|cafe|hotel)(?P<term>[A-Z][a-zA-Zàèéìòù\s]{1,30})",
    )
    for pat in name_patterns:
        m = re.search(pat, q, flags=re.IGNORECASE)
        if not m:
            continue
        raw_term = (m.group("term") or "").strip()
        raw_term = re.sub(
            r"^(il|lo|la|i|gli|le|the|a|an|un|uno|una)\s+",
            "",
            raw_term,
            flags=re.IGNORECASE,
        ).strip()
        raw_term = raw_term.strip(chr(34) + chr(39) + chr(8220) + chr(8221))
        raw_term = " ".join(raw_term.split()[:3])
        if raw_term:
            return True, "search_by_name", raw_term

    # 5) Generic handler patterns
    handler_patterns = (
        r"\bchi\s+si\s+occupa\s+di\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\bwho\s+handles\s+(?P<term>[^?.,!;:\n]{1,64})",
    )
    for pat in handler_patterns:
        m = re.search(pat, q, flags=re.IGNORECASE)
        if not m:
            continue
        raw_term = (m.group("term") or "").strip().strip(chr(34) + chr(39) + chr(8220) + chr(8221))
        raw_term = " ".join(raw_term.split()[:3])
        if raw_term:
            return True, "search_by_role", raw_term.lower()

    return False, "", ""
