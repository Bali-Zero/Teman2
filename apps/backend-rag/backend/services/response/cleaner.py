import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================================
# OUT-OF-DOMAIN DETECTION
# ============================================================================

OUT_OF_DOMAIN_RESPONSES = {
    "personal_data": (
        "Non ho accesso a dati personali di terze persone come codici fiscali, "
        "numeri di telefono o indirizzi privati. Posso aiutarti con informazioni "
        "su visa, business setup o questioni legali in Indonesia?"
    ),
    "realtime_info": (
        "Non ho accesso a informazioni in tempo reale come meteo, news o risultati sportivi. "
        "Per queste informazioni ti consiglio di consultare fonti aggiornate. "
        "Posso invece aiutarti con visa, KITAS, o business in Indonesia?"
    ),
    "off_topic": (
        "Questo argomento è fuori dalla mia area di competenza. Sono Zantara, "
        "l'assistente AI di Bali Zero, specializzato in visa, immigrazione, "
        "setup aziendale (PT PMA) e questioni legali per stranieri in Indonesia. "
        "Come posso aiutarti in questi ambiti?"
    ),
    "unknown": (
        "Non ho informazioni specifiche su questo argomento. "
        "Posso aiutarti con visa, KITAS, setup PT PMA/Lokal, "
        "o altre questioni business in Indonesia?"
    ),
}


def is_out_of_domain(query: str) -> tuple[bool, Optional[str]]:
    """
    Check if query is outside Zantara's domain of expertise.
    """
    query_lower = query.lower()

    # Personal data of third parties
    personal_data_patterns = [
        r"codice fiscale (di|del|della|dello) \w+",
        r"numero (di )?telefono (di|del|della) \w+",
        r"indirizzo (di|del|della) \w+",
        r"email (di|del|della) \w+",
        r"tax (code|id|number) of \w+",
        r"phone number of \w+",
    ]

    for pattern in personal_data_patterns:
        if re.search(pattern, query_lower):
            return True, "personal_data"

    # Real-time information
    realtime_patterns = [
        r"(che )?tempo fa",
        r"meteo (a|di|in)",
        r"news\b",
        r"notizie (di )?oggi",
        r"weather (in|at|for)",
        r"stock price",
        r"bitcoin price",
    ]

    for pattern in realtime_patterns:
        if re.search(pattern, query_lower):
            return True, "realtime_info"

    # Off-topic
    off_topic_patterns = [
        r"ricetta (di|per|del)",
        r"risultat[oi] (di )?calcio",
        r"film (da )?vedere",
        r"canzone (di|del)",
        r"politica italian[ao]",
        r"scrivi (un[ao]? )?(poema|poesia)",
        r"gossip",
        r"oroscopo",
    ]

    for pattern in off_topic_patterns:
        if re.search(pattern, query_lower):
            return True, "off_topic"

    # Questions about people's personal info
    if re.search(r"(sindaco|presidente|ministro) di", query_lower):
        if any(term in query_lower for term in ["codice", "telefono", "indirizzo", "email"]):
            return True, "personal_data"

    return False, None


def clean_response(response: str) -> str:
    """
    Remove internal reasoning patterns from user-facing response.

    Filters out THOUGHT leaks, observation statements, and generic philosophical
    reasoning that should not be exposed to users.

    Args:
        response: Raw response from LLM

    Returns:
        Cleaned response without internal reasoning patterns
    """
    if not response:
        return ""

    patterns = [
        # Remove "Okay, since/with/given..." patterns
        r"^Okay[,.]?\s*(since|with|given|without|lacking|based|in the absence)[^.]*observation[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*prior (information|context)[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*context[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*input[^.]*\.\s*",
        r"^Okay[,.]?\s*I need to (either|understand|consider)[^.]*\.\s*",
        r"^Okay[,.]?\s*Given the (observation|lack)[^.]*\.\s*",
        # Remove entire "Okay. Based/Given/Without..." sentences at start (non-greedy)
        r"^Okay\.\s*[A-Z][^.]*?(observation|context|information)[^.]*\.\s*",
        # Remove "solicit input" patterns
        r"[Mm]y next thought is to solicit input[^.]*\.\s*",
        r"[Ss]olicit input to understand[^.]*\.\s*",
        r"[Pp]rovide me with some context[^.]*\.\s*",
        # Remove THOUGHT: markers (case-insensitive)
        r"^THOUGHT:.*?\n",
        r"^THOUGHT\s*:.*?\n",
        r"^Thought:.*?\n",
        r"^Thought\s*:.*?\n",
        # Remove Observation: markers (case-insensitive)
        r"^Observation:.*?\n",
        r"^Observation\s*:.*?\n",
        # Remove stub responses
        r"Zantara has provided the final answer\.?\s*",
        r"ZANTARA has provided the final answer\.?\s*",
        r"\(No further action needed[^)]*\)\s*",
        r"No new query[^.]*\.\s*",
        r"Waiting for (your|user)[^.]*\.\s*",
        # Remove "Next thought" patterns
        r"^Next thought:.*?\n",
        r'^My "?next thought"?[^.]*\.\s*',
        r"[Mm]y next thought is:?\s*[^.]*\.\s*",
        # Remove generic philosophical reasoning
        r"^What (could|do|are|is) (I|we)[^?]*\?\s*",
        r"^Perhaps (the|I|we)[^.]*\.\s*",
        r"^Given (no|the lack of) (specific )?observation[^.]*\.\s*",
        r"^I will proceed with a general thought[^.]*\.\s*",
        r"^I\'ll (just )?offer a general[^.]*\.\s*",
        r"^In the absence of (an )?observation[^.]*\.\s*",
        r"^Since (there\'s|I have) no (prior )?observation[^.]*\.\s*",
        r"^Without (any )?(specific |prior )?(context|observation|information)[^.]*\.\s*",
        # Remove scenario/possibility statements that don't add value
        r"^Scenario \d+:[^.]*\.\s*",
        r"^Possible Next Steps[^:]*:\s*",
        # Remove meta-commentary about reasoning process
        r"^How can I be helpful[^?]*\?\s*",
        r"^The (power|importance|interplay) of[^.]*\.\s*",
        r"^Humans are remarkably[^.]*\.\s*",
        # Remove "Final Answer:" prefix if present
        r"^Final Answer:\s*",
        r"^FINAL ANSWER:\s*",
        # Remove "The search results..." reasoning leaks
        r"^The search results (mostly |don\'t |didn\'t |only )?[^.]*\.\s*",
        r"^I need to answer based on[^.]*\.\s*",
        r"^Based on (the |my )?search results[^.]*\.\s*",
        r"^(From |Looking at )the (search |observation |)results[^.]*\.\s*",
        # Remove internal notes about lack of information
        r"^Non ho bisogno di pensieri aggiuntivi[^.]*\.\s*",
        r"^Ho già fornito[^.]*\.\s*",
        r"^I don\'t need additional thoughts[^.]*\.\s*",
        r"^I\'ve already provided[^.]*\.\s*",
        # Remove "But there are still things..." patterns
        r"^But there are still things[^.]*\.\s*",
        # Remove "Let me..." patterns
        r"^Let me (check|search|look|find)[^.]*\.\s*",
        r"^Fammi (cercare|controllare|verificare)[^.]*\.\s*",
        # Remove standalone ACTION patterns that leaked
        r"^ACTION:\s*[a-z_]+\([^)]*\)\.?\s*",
        r"^ACTION:\s*No tool call needed[^.]*\.\s*",
        # Remove CRITICAL/IMPORTANT system message leaks
        r"^CRITICAL:\s*[^\n]*\n*",
        r"^IMPORTANT:\s*[^\n]*\n*",
        # Remove "User Query:" prompt leaks
        r"^User Query:\s*[^\n]*\n*",
        # Remove vector_search call leaks
        r"^vector_search\([^)]*\)\s*",
    ]

    cleaned = response
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # Remove multiple consecutive newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()

    # Truncate if too long (strict limit)
    if len(cleaned) > 1000:
        logger.warning(f"⚠️ Response truncated from {len(cleaned)} to 1000 chars")
        cleaned = cleaned[:997] + "..."

    logger.info(f"🧹 Cleaned response length: {len(cleaned)}")
    return cleaned
