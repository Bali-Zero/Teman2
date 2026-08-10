import logging
import re

from backend.app.core.config import settings

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
        f"Questo argomento è fuori dalla mia area di competenza. Sono Zantara, "
        f"l'assistente AI di {settings.COMPANY_NAME}, specializzato in visa, immigrazione, "
        "setup aziendale (PT PMA) e questioni legali per stranieri in Indonesia. "
        "Come posso aiutarti in questi ambiti?"
    ),
    "unknown": (
        "Non ho informazioni specifiche su questo argomento. "
        "Posso aiutarti con visa, KITAS, setup PT PMA/Lokal, "
        "o altre questioni business in Indonesia?"
    ),
}


def is_out_of_domain(query: str) -> tuple[bool, str | None]:
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

    # Real-time FINANCIAL information (blocked - cannot verify)
    # NOTE: Weather, news, tourism info are NOW ALLOWED - handled by web_search tool
    realtime_financial_patterns = [
        r"stock price",
        r"bitcoin price",
        r"crypto (price|value)",
        r"forex (rate|exchange)",
    ]

    for pattern in realtime_financial_patterns:
        if re.search(pattern, query_lower):
            return True, "realtime_info"

    # NOTE: off_topic patterns REMOVED (2026-01-28)
    # Gemini 3 is now allowed to answer ANY question, not just business-related.
    # This allows users to leverage the full power of the LLM while still using
    # RAG for Tier 1 (business-specific) queries.
    # Previous patterns blocked: ricetta, calcio, film, canzone, politica, poesia, gossip, oroscopo

    # Questions about people's personal info
    if re.search(r"(sindaco|presidente|ministro) di", query_lower):
        if any(term in query_lower for term in ["codice", "telefono", "indirizzo", "email"]):
            return True, "personal_data"

    return False, None


# ============================================================================
# INTERNAL-MONOLOGUE FILTERING
# ============================================================================
#
# Three classes, three anchorings. The split IS the cure for a measured defect:
# every pattern below used to be applied with `re.MULTILINE`, so a `^`-anchored
# "strip the leading preamble" rule matched at EVERY line start and ate lines
# out of the middle of a correct answer. Measured 2026-08-10 against the real
# pattern list: 20 of 22 legitimate answer fragments were altered and 15 were
# deleted outright — `"The power of attorney must be notarised before
# submission."` cleaned to `""`.
#
# The two failure directions are NOT symmetric here, which is why several
# patterns below are NARROWER than the ones they replace:
#   * false negative -> a line of model filler reaches the client;
#   * false positive -> advice the client asked for is deleted from an answer
#     that already passed retrieval AND the abstain gate, and on WhatsApp an
#     emptied answer is silence (`wa_inbox_bot` sends nothing).
# So narrow deliberately. Do not widen any pattern back without a measured
# innocence case; the guilt/innocence corpus lives in
# `backend/tests/services/response/test_cleaner_anchor_not_multiline.py`.

# Protocol markers: tokens the model emits as ReAct/system scaffolding. These
# genuinely can start ANY line of a leaked monologue, so they keep MULTILINE.
_MARKER_PATTERNS: tuple[str, ...] = (
    r"^THOUGHT:.*?\n",
    r"^THOUGHT\s*:.*?\n",
    r"^Thought:.*?\n",
    r"^Thought\s*:.*?\n",
    r"^Observation:.*?\n",
    r"^Observation\s*:.*?\n",
    r"^Next thought:.*?\n",
    r"^ACTION:\s*[a-z_]+\([^)]*\)\.?\s*",
    r"^ACTION:\s*No tool call needed[^.]*\.\s*",
    r"^vector_search\([^)]*\)\s*",
    r"^User Query:\s*[^\n]*\n*",
    # Prefix-only strips: the marker goes, the sentence after it stays.
    r"^Final Answer:\s*",
    r"^FINAL ANSWER:\s*",
    # CRITICAL:/IMPORTANT: are system-prompt leaks ONLY when they direct the
    # MODEL. `IMPORTANT: the LKPM must be filed quarterly.` and `IMPORTANT:
    # Always carry your KITAS.` are exactly how compliance answers are written,
    # and the old bare-prefix form deleted the whole line. A directive verb
    # alone does not separate the two (a client warning is imperative too), so
    # the line must ALSO name something only the assistant does.
    # The lookahead is the load-bearing half, mutation-measured: an intermediate
    # draft listed `Your\b` as a directive opener and ate "CRITICAL: your KITAS
    # expires in 14 days.", but re-adding `Your\b` NOW kills no test, because
    # the lookahead already rejects that line. `You\b` does not match "your"
    # (the `\b` needs a non-word char after it); the opener list is a second
    # filter, not the guard.
    r"^(CRITICAL|IMPORTANT):\s*"
    r"(?=[^\n]*\b(?:invent|fabricate|guess|hallucinat\w*|cite|reveal|disclose|"
    r"respond|reply|output|tool|tools|search results|system prompt|instructions|"
    r"the user|the client)\b)"
    r"(You\b|Never\b|Always\b|Do not\b|Don't\b|Use\b|Remember\b|Ensure\b|"
    r"Make sure\b)[^\n]*\n*",
)

# Leading preamble: filler the model puts BEFORE the answer. Compiled without
# MULTILINE, so `^` means start-of-string and these can never reach into the
# body of an answer.
_PREAMBLE_PATTERNS: tuple[str, ...] = (
    r"^Okay[,.]?\s*(since|with|given|without|lacking|based|in the absence)[^.]*observation[^.]*\.\s*",
    r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*prior (information|context)[^.]*\.\s*",
    r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*context[^.]*\.\s*",
    r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*input[^.]*\.\s*",
    r"^Okay[,.]?\s*I need to (either|understand|consider)[^.]*\.\s*",
    r"^Okay[,.]?\s*Given the (observation|lack)[^.]*\.\s*",
    r"^Okay\.\s*[A-Z][^.]*?(observation|context|information)[^.]*\.\s*",
    r'^My "?next thought"?[^.]*\.\s*',
    # NARROWED: `^What (could|do|are|is) (I|we)` deleted the legitimate
    # rhetorical "What are we required to file for the SPT Tahunan?".
    r"^What (could|should|shall) I[^?]*\?\s*",
    r"^What do I (know|have|need)[^?]*\?\s*",
    # NARROWED: `^Perhaps (the|I|we)` deleted "Perhaps the most common case is
    # a PT PMA with a single foreign shareholder.".
    r"^Perhaps I (should|could|need|will|can)[^.]*\.\s*",
    r"^Given (no|the lack of) (specific )?observation[^.]*\.\s*",
    r"^I will proceed with a general thought[^.]*\.\s*",
    r"^I\'ll (just )?offer a general[^.]*\.\s*",
    r"^In the absence of (an )?observation[^.]*\.\s*",
    r"^Since (there\'s|I have) no (prior )?observation[^.]*\.\s*",
    # SPLIT: "observation" is ReAct vocabulary and safe to delete on sight;
    # "Without any prior context, I would still advise filing before 31 March."
    # is a real answer, so the context/information arm now also requires the
    # model to be declaring its own incapacity.
    r"^Without (any )?(specific |prior )?observation[^.]*\.\s*",
    r"^Without (any )?(specific |prior )?(context|information)[^.]*\b"
    r"(I (will|can only|cannot|can\'t|am unable to)|I\'ll) "
    r"(offer|provide|give|proceed|make|assume)[^.]*\.\s*",
    r"^How can I be helpful[^?]*\?\s*",
    # NARROWED: the qualifier is now REQUIRED. Unqualified "The search results
    # confirm the 2026 rate is 11%." carries the fact in the sentence being
    # deleted; the qualified form carries nothing.
    r"^The search results (mostly|don\'t|didn\'t|do not|did not|only)\b[^.]*\.\s*",
    # NARROWED: bare `^I need to answer based on` deleted "…based on the akta
    # you sent - page 2 lists the directors." The object list is what makes it
    # monologue; an answer grounded in a client document is not.
    r"^I need to answer based on (the |my )?"
    r"(observation|context|search results|what I have|nothing|no information)"
    r"[^.]*\.\s*",
    # PREFIX-ONLY (was sentence-delete): keeps "the KBLI code is 68111.".
    r"^Based on (the |my )?search results[,:]?\s*",
    r"^(From |Looking at )the (search |observation |)results[,:]?\s*",
    r"^Non ho bisogno di pensieri aggiuntivi[^.]*\.\s*",
    r"^Ho già fornito[^.]*\.\s*",
    r"^I don\'t need additional thoughts[^.]*\.\s*",
    r"^I\'ve already provided[^.]*\.\s*",
    r"^But there are still things[^.]*\.\s*",
    # NARROWED with `[^.:]`: a colon means the sentence introduces content
    # ("Let me check: the E33G is valid for 5 years."), which must survive.
    # A bare intention ("Let me check the knowledge base.") still goes.
    r"^Let me (check|search|look|find)[^.:]*\.\s*",
    r"^Fammi (cercare|controllare|verificare)[^.:]*\.\s*",
    # Stub responses — anchored, because unanchored they matched mid-answer
    # ("Waiting for your passport scan, we can start the application." -> "").
    r"^Waiting for (your|user) (next |new )?"
    r"(quer(y|ies)|input|response|message|instruction)s?\b[^.]*\.\s*",
)

# DROPPED, not moved — each was measured deleting ordinary consultant English
# and has no monologue-only trigger left to narrow onto:
#   r"^Scenario \d+:[^.]*\.\s*"                      -> ate "Scenario 1: you already hold a KITAS."
#   r"^Possible Next Steps[^:]*:\s*"                 -> ate a legitimate answer heading
#   r"^The (power|importance|interplay) of[^.]*\.\s*" -> ate "The power of attorney must be notarised."
#   r"[Pp]rovide me with some context[^.]*\.\s*"     -> ate the bot's own clarifying request
#   r"^Humans are remarkably[^.]*\.\s*"             -> ate "…patient with Indonesian
#       bureaucracy, but the deadline is fixed." - same shape-guess at philosophical
#       filler as `The importance of`, same whole-sentence loss.
#   r"^No new quer(y|ies)[^.]*\.\s*"                -> ate "No new query is needed - the
#       NIB already covers this KBLI."; "query" alone is not monologue-only vocabulary.
# The monologue framing they were meant to catch is still covered by the
# "solicit input" / "my next thought" patterns below.

# Unanchored: phrases that are monologue wherever they appear.
_ANYWHERE_PATTERNS: tuple[str, ...] = (
    r"[Mm]y next thought is to solicit input[^.]*\.\s*",
    r"[Ss]olicit input to understand[^.]*\.\s*",
    r"[Mm]y next thought is:?\s*[^.]*\.\s*",
    r"Zantara has provided the final answer\.?\s*",
    r"ZANTARA has provided the final answer\.?\s*",
    r"\(No further action needed[^)]*\)\s*",
)

_MARKER_RE = tuple(re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _MARKER_PATTERNS)
_PREAMBLE_RE = tuple(re.compile(p, re.IGNORECASE) for p in _PREAMBLE_PATTERNS)
_ANYWHERE_RE = tuple(re.compile(p, re.IGNORECASE) for p in _ANYWHERE_PATTERNS)

# A response can open with several stacked preamble sentences; each pass peels
# at most one per pattern, so re-run until nothing changes (bounded).
_PREAMBLE_MAX_PASSES = 5


def clean_response(response: str) -> str:
    """
    Remove internal reasoning patterns from user-facing response.

    Filters out THOUGHT leaks, observation statements, and generic philosophical
    reasoning that should not be exposed to users.

    Never returns an empty string for a non-blank input: if the filters would
    consume the whole answer that is a filter defect, not a monologue-only
    answer, and the caller (`PostProcessingStage` -> `wa_inbox_bot`) turns an
    emptied answer into client-facing silence. The original is returned and the
    event logged instead.

    Args:
        response: Raw response from LLM

    Returns:
        Cleaned response without internal reasoning patterns
    """
    if not response:
        return ""

    cleaned = response
    for regex in _ANYWHERE_RE:
        cleaned = regex.sub("", cleaned)
    for regex in _MARKER_RE:
        cleaned = regex.sub("", cleaned)
    for _ in range(_PREAMBLE_MAX_PASSES):
        before = cleaned
        for regex in _PREAMBLE_RE:
            cleaned = regex.sub("", cleaned, count=1)
        if cleaned == before:
            break

    # Remove multiple consecutive newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()

    # Prefix-only strips ("Final Answer: ", "Based on the search results, ")
    # leave the answer opening mid-sentence. Restore sentence case only when
    # the raw answer did NOT start lowercase, i.e. only when we are the ones
    # who chopped its opening.
    if cleaned[:1].islower() and not response.lstrip()[:1].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    if not cleaned and response.strip():
        logger.warning(
            "🧹 Cleaner would have emptied a %d-char response - returning it unfiltered "
            "(a monologue filter matched the whole answer; this is a pattern defect)",
            len(response.strip()),
        )
        return response.strip()

    # NO TRUNCATION for business responses - let the LLM decide response length
    # Only log extremely long responses for monitoring
    if len(cleaned) > 15000:
        logger.warning(f"⚠️ Very long response: {len(cleaned)} chars (not truncated)")

    logger.info(f"🧹 Cleaned response length: {len(cleaned)}")
    return cleaned
