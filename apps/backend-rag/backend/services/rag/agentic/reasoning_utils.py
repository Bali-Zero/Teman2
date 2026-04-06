"""
ReAct Reasoning Utilities

Helper functions extracted from reasoning.py to reduce file complexity.
Contains: domain detection, evidence scoring, tool validation, team query detection.
"""

import logging
import re
from typing import Any

from backend.app.core.config import settings

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
    if any(kw in query_lower for kw in legal_keywords):
        return "legal"
    if any(kw in query_lower for kw in pricing_keywords):
        return "pricing"
    if any(kw in query_lower for kw in procedure_keywords):
        return "procedure"
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

    FIXED: This score now properly reflects ACTUAL relevance between query and context.
    - Mismatched results (e.g., KITAS query returning KBLI) will score < 0.15
    - Nonsense queries ("xyzabc123") will score ~0.0
    - Relevant results with good sources score 0.6+

    Scoring Formula:
        - Base score: 0.0
        - Source quality component (0.0-0.4): Based on top source score
        - Context relevance (0.0-0.6): Based on keyword/semantic overlap
        - Maximum score: 1.0

    Args:
        sources: List of source dictionaries with 'score' field
        context_gathered: List of context strings from tool results
        query: Original user query string

    Returns:
        Evidence score between 0.0 and 1.0

    Note:
        - Score < 0.15: ABSTAIN (insufficient evidence)
        - Score 0.15-0.6: CAUTIOUS (low confidence, use fallback)
        - Score > 0.6: CONFIDENT (proceed with answer)
    """
    if not sources and not context_gathered:
        return 0.0

    # Extract meaningful query keywords (remove stop words, short words)
    query_lower = query.lower()
    stop_words = {
        # English stop words
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
        "should",
        "may",
        "might",
        "can",
        "shall",
        "this",
        "that",
        "these",
        "those",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "tell",
        "me",
        "about",
        "explain",
        "information",
        "with",
        "for",
        "from",
        "into",
        "during",
        "including",
        "until",
        "against",
        "among",
        "through",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "and",
        "but",
        "or",
        "yet",
        "as",
        "of",
        "at",
        "by",
        "on",
        "to",
        "in",
        "it",
        "its",
        # Italian stop words
        "questo",
        "questa",
        "questi",
        "queste",
        "quello",
        "quella",
        "quelli",
        "quelle",
        "che",
        "chi",
        "come",
        "quando",
        "dove",
        "perche",
        "perché",
        "dimmi",
        "spiegami",
        "informazioni",
        "sulla",
        "sullo",
        "sulle",
        "nel",
        "nello",
        "nella",
        "negli",
        "nelle",
        "del",
        "dello",
        "della",
        "dei",
        "degli",
        "delle",
        "al",
        "allo",
        "alla",
        "ai",
        "agli",
        "alle",
        "dal",
        "dallo",
        "dalla",
        "dai",
        "dagli",
        "dalle",
        "sul",
        "sui",
        "sugli",
        "nei",
        "col",
        "coi",
        "con",
        "per",
        "tra",
        "fra",
        "di",
        "da",
        "su",
        "ed",
        "o",
        "ma",
        "se",
        "non",
        "anche",
        "piu",
        "può",
        "puo",
        "deve",
        "essere",
        "avere",
        "fare",
        "andare",
        # Generic words that shouldn't count as matches
        "query",
        "question",
        "ask",
        "say",
        "get",
        "need",
        "want",
    }

    # Extract meaningful keywords (length > 3, not stop words)
    # Increased min length to 4 to avoid matching generic short words
    query_words = [
        w.strip(".,!?;:()[]{}\"'")
        for w in query_lower.split()
        if len(w) > 3 and w.strip(".,!?;:()[]{}\"'") not in stop_words
    ]

    # Remove duplicates while preserving order
    seen = set()
    query_keywords = []
    for w in query_words:
        if w not in seen and len(w) > 2:
            seen.add(w)
            query_keywords.append(w)

    # Combine all context for analysis
    context_text = " ".join(context_gathered).lower() if context_gathered else ""

    # ========== RELEVANCE SCORING ==========
    # Calculate keyword match ratio - how many query keywords appear in context
    keyword_hits = sum(1 for kw in query_keywords if kw in context_text)

    keyword_match_ratio = keyword_hits / len(query_keywords) if query_keywords else 0.0

    # Check for specific entity type mismatches (e.g., KITAS query returning KBLI)
    # This catches cases where the topic is completely wrong
    entity_type_mismatch = False
    if query_keywords:
        # Define topic categories
        visa_keywords = {"kitas", "kitap", "visa", "immigration", "imigrasi", "permit", "stay"}
        kbli_keywords = {"kbli", "classification", "business", "code", "kode", "klasifikasi"}
        tax_keywords = {"tax", "tasse", "pajak", "fiscal", "fiscale", "npwp", "pph"}
        company_keywords = {"pt", "pma", "company", "azienda", "usaha", "perusahaan"}

        query_has_visa = any(kw in visa_keywords for kw in query_keywords)
        query_has_kbli = any(kw in kbli_keywords for kw in query_keywords)
        query_has_tax = any(kw in tax_keywords for kw in query_keywords)
        query_has_company = any(kw in company_keywords for kw in query_keywords)

        context_has_visa = any(kw in context_text for kw in visa_keywords)
        context_has_kbli = any(kw in context_text for kw in kbli_keywords)
        context_has_tax = any(kw in context_text for kw in tax_keywords)
        context_has_company = any(kw in context_text for kw in company_keywords)

        # Detect mismatch: query about X but context about Y (where X != Y)
        # Only flag if context clearly belongs to a different category
        if query_has_visa and (context_has_kbli or context_has_tax) and not context_has_visa:
            entity_type_mismatch = True
        if query_has_kbli and (context_has_visa or context_has_tax) and not context_has_kbli:
            entity_type_mismatch = True
        if query_has_tax and (context_has_visa or context_has_kbli) and not context_has_tax:
            entity_type_mismatch = True
        if query_has_company and (context_has_visa or context_has_tax) and not context_has_company:
            entity_type_mismatch = True

        # If mismatch detected, force very low semantic relevance
        if entity_type_mismatch:
            keyword_match_ratio = min(keyword_match_ratio, 0.1)

    # Semantic relevance score (0.0 - 0.6)
    # Relevance is the PRIMARY factor - source quality only helps if relevance is good
    # - Full match: keyword_match_ratio >= 0.5 → 0.6 points
    # - Good match: keyword_match_ratio >= 0.3 → 0.4 points
    # - Partial match: keyword_match_ratio >= 0.15 → 0.2 points
    # - Poor match: keyword_match_ratio < 0.15 → 0.0 points (ABSTAIN territory)
    if keyword_match_ratio >= 0.5:
        semantic_relevance = 0.6  # Strong relevance
    elif keyword_match_ratio >= 0.3:
        semantic_relevance = 0.4  # Moderate relevance
    elif keyword_match_ratio >= 0.15:
        semantic_relevance = 0.2  # Weak relevance
    else:
        semantic_relevance = 0.0  # No relevant keywords found

    # ========== SOURCE QUALITY SCORING ==========
    # Source quality is SECONDARY - it can only boost score if relevance exists
    source_quality_score = 0.0

    if sources:
        # Get top source score (best evidence)
        source_scores = [s.get("score", 0.0) for s in sources if isinstance(s, dict)]

        if source_scores:
            top_score = max(source_scores)

            # Source quality based on top score
            # - Score 0.7+ : 0.4 points (excellent)
            # - Score 0.5-0.7: 0.3 points (good)
            # - Score 0.3-0.5: 0.2 points (acceptable)
            # - Score < 0.3: 0.0-0.1 points (weak)
            if top_score >= 0.7:
                source_quality_score = 0.4
            elif top_score >= 0.5:
                source_quality_score = 0.3
            elif top_score >= 0.3:
                source_quality_score = 0.2
            elif top_score >= 0.15:
                source_quality_score = 0.1
            else:
                source_quality_score = 0.0

    # ========== FINAL SCORE CALCULATION ==========
    # Semantic relevance is the PRIMARY factor (60-80% weight)
    # Source quality acts as a bonus/boost (20-40% weight)

    if semantic_relevance == 0.0:
        # No semantic relevance - score is based only on weak source quality
        # This ensures nonsense queries or complete mismatches score < 0.15
        final_score = min(source_quality_score * 0.2, 0.1)
    elif semantic_relevance < 0.3:
        # Weak relevance - cap the score regardless of source quality
        # Max possible: 0.2 + (0.4 * 0.25) = 0.3
        final_score = semantic_relevance + source_quality_score * 0.25
        final_score = min(final_score, 0.35)
    else:
        # Good relevance - can add source quality as bonus
        # But cap at 1.0 and weight source quality lower
        final_score = semantic_relevance + source_quality_score * 0.5

    return round(min(final_score, 1.0), 2)


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
