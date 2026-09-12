"""
ReAct Reasoning Utilities

Helper functions extracted from reasoning.py to reduce file complexity.
Contains: domain detection, evidence scoring, tool validation, team query detection.
"""

import logging
import os
import re
from typing import Any, Final

from backend.app.core.config import settings
from backend.core import score_provenance
from backend.services.rag.agentic._support_signal import SupportVerdict

logger = logging.getLogger(__name__)

# ============================================================================
# B2.1 — provenance-primary relevance bands (build spec §2).
#
# Four ordered bands, reusing the EXACT four values the legacy keyword-ratio
# path has always produced (0.0/0.2/0.4/0.6) so the final_score combination
# formula below — untouched — sees the same magnitudes it was tuned against
# regardless of which path fed it.
# ============================================================================

_BAND_NONE: Final = 0
_BAND_WEAK: Final = 1
_BAND_MODERATE: Final = 2
_BAND_STRONG: Final = 3
_BAND_VALUES: Final[tuple[float, float, float, float]] = (0.0, 0.2, 0.4, 0.6)


def _band_index_from_ratio(ratio: float) -> int:
    """Band a [0,1]-ish ratio using the SAME cut points the legacy semantic-
    relevance bucketing has always used (0.5/0.3/0.15) — one definition, used
    for the legacy path, the hybrid-normalised band and the lexical
    corroboration step, so the three never drift apart by accident."""
    if ratio >= 0.5:
        return _BAND_STRONG
    if ratio >= 0.3:
        return _BAND_MODERATE
    if ratio >= 0.15:
        return _BAND_WEAK
    return _BAND_NONE


def _hybrid_band_index(score: float) -> int:
    """`hybrid_rrf_formatted` measured range is [0.508, 1.000] (score_provenance.py):
    0.5 means "last of a long list", not "half similar". Normalising
    `(score-0.5)/0.5` maps that measured range onto [0.016, 1.0] and the SAME
    ratio cut points used everywhere else in this module band it — no new
    magic numbers for a number that is, once normalised, the same shape as
    `keyword_match_ratio`."""
    return _band_index_from_ratio((score - 0.5) / 0.5)


def _dense_band_index(score: float, score_raw: float | None) -> int:
    """`dense_formatted`'s `score_raw` is the cosine (score_provenance.py); prefer
    it, and recover it exactly (`raw = 2 - 1/score`, the formatter's own inverse)
    only when a writer omitted `score_raw`.

    WEAK is deliberately COLLAPSED into NONE here — the two negative anchors
    already measured on this tree (docstring of
    `test_evidence_cross_language.py`: an unrelated pair at cosine 0.038, a
    wrong-domain-shares-vocabulary pair at 0.155) must read as no relevance,
    and so must a THIRD, freshly measured one: the standing nonsense-query
    tripwire `test_nonsense_query_zero_score_pipeline_variant` declares a
    dense_formatted source at cosine 0.22 and must still score < 0.15. A
    0.20-0.32 WEAK band would clear that gate (0.22 lands in it) and turn a
    green tripwire red. MODERATE starts at 0.32 — the exact boundary the same
    docstring already names ("comfortably above a 0.32 band") for the one
    measured POSITIVE anchor, 0.373. STRONG (>=0.55) is reserved for a
    confident cosine well above that midpoint; unmeasured beyond these three
    anchors, so kept conservative rather than tuned."""
    if score_raw is not None:
        cosine = score_raw
    elif score:
        cosine = 2.0 - (1.0 / score)
    else:
        return _BAND_NONE
    if cosine >= 0.55:
        return _BAND_STRONG
    if cosine >= 0.32:
        return _BAND_MODERATE
    return _BAND_NONE


def _reranked_band_index(score: float) -> int:
    """`reranked`'s scale is NOT measured anywhere in this repo (build spec §2).
    A flat, conservative WEAK band — never NONE for a POSITIVE score (a
    declared retrieved kind IS a retrieval signal) and never MODERATE/STRONG
    (that would claim confidence this repo has not measured) — is the declared
    residual: named here, and in the PR's `pack.yml`, for the Dux to size with
    a real reranker-score measurement in a follow-up.

    A score of 0.0 or below is the ONE case that must read NONE, and it was a
    real defect until the adversarial seat (codex-gpt-5.6-sol, round 1) named
    the category and the Dux reproduced it: a source declaring `reranked` with
    `score: 0.0` scored 0.2 relevance against a NONSENSE query and unrelated
    context — relevance CREATED where the reranker itself measured none, which
    is exactly what this module promises never to do. An unmeasured scale is
    not a licence to read its floor as evidence."""
    if score <= 0.0:
        return _BAND_NONE
    return _BAND_WEAK


def _declared_band_index(declared: list[dict]) -> int:
    """The best band across every declared retrieved-kind source — same
    "best evidence wins" shape as the legacy `top_score = max(...)` line."""
    best = _BAND_NONE
    for source in declared:
        if not isinstance(source, dict):
            continue
        kind = score_provenance.kind_of(source)
        score = source.get("score", 0.0)
        if not isinstance(score, (int, float)):
            score = 0.0
        if kind == score_provenance.HYBRID_RRF_FORMATTED:
            idx = _hybrid_band_index(score)
        elif kind == score_provenance.DENSE_FORMATTED:
            idx = _dense_band_index(score, score_provenance.raw_of(source))
        elif kind == score_provenance.RERANKED:
            idx = _reranked_band_index(score)
        else:  # pragma: no cover - RETRIEVED_KINDS has exactly the three above
            idx = _BAND_NONE
        if idx > best:
            best = idx
    return best


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


# Short business identifiers that MUST survive keyword extraction. Every one is
# <= 3 characters and would otherwise be discarded as noise, taking the subject
# of the question with it. Lower-cased because the extractor folds case first.
#
# EXCLUDED ON PURPOSE (Opus gate PASS-WITH-CONDITIONS, measured 2026-09-10):
# `pt`, `rp`, `idr`, `usd`, `cv` are NOT discriminating — each is a free hit on
# almost any chunk regardless of topic. `pt` prefixes nearly every Indonesian
# company name, `rp`/`idr`/`usd` sit on every price line, and `cv` is both
# another company-name prefix and the everyday word for a résumé. Measured
# worst case with these still in the vocabulary: "Apa itu PT PMA?" against a
# chunk that only names an unrelated company ("PT Warung Bali menjual nasi
# goreng ...") went 0.080 -> 0.800 (with sources) — abstain became an answer
# from an unrelated chunk. See
# test_non_discriminating_two_character_tokens_were_removed_from_the_vocabulary.
_SHORT_IDENTIFIERS: frozenset[str] = frozenset(
    {
        # Company / licensing
        "pma", "nib", "oss", "tdp",
        # `sk` (Surat Keputusan / decision letter) stays: measured, unlike
        # `pt`/`cv` it is not a common standalone word in ordinary Indonesian
        # or English prose, so it is not a systemic free hit.
        "sk",
        # Tax
        "pph", "ppn", "spt", "pbb", "pkp",
        # Immigration — the permit codes a client actually types
        "voa", "imk", "tka", "wna", "wni",
        "b1", "c1", "c2", "c7", "d1", "d2", "e23", "e28", "e31", "e32", "e33",
        # Property
        "hgb", "shm", "imb", "pbg", "slf", "ajb", "hak",
    }
)


def calculate_evidence_score(
    sources: list[dict] | None,
    context_gathered: list[str],
    query: str,
    *,
    support: SupportVerdict | None = None,
) -> float:
    """
    Calculate evidence score based on source quality and context relevance.

    FIXED: This score now properly reflects ACTUAL relevance between query and context.
    - Mismatched results (e.g., KITAS query returning KBLI) will score < 0.15
    - Nonsense queries ("xyzabc123") will score ~0.0
    - Relevant results with good sources score 0.6+

    B2.1 — the inversion (build spec §2). When any source DECLARES a retrieved
    kind (`score_provenance.RETRIEVED_KINDS`), relevance comes PRIMARILY from a
    per-kind provenance band, and the lexical ratio below only CORROBORATES it
    (raises the band by at most one step, never lowers it, never gates alone).
    When no source declares a kind, this function is UNCHANGED: an `unknown`
    kind is a fact about our knowledge, not a low grade, and every standing
    tripwire's fixture declares none — that is what keeps them byte-identical.

    Scoring Formula:
        - Base score: 0.0
        - Source quality component (0.0-0.4): Based on top source score
        - Context relevance (0.0-0.6): Based on keyword/semantic overlap,
          or on the provenance band when a source declares a retrieved kind
        - Maximum score: 1.0

    Args:
        sources: List of source dictionaries with 'score' field
        context_gathered: List of context strings from tool results
        query: Original user query string
        support: The support signal's verdict for this (query, context), or
            `None` when it was not consulted. Fail-closed (build spec §2.5):
            `None` changes nothing; `SUPPORTED` keeps the relevance computed
            below; anything else (`NOT_SUPPORTED`/`UNKNOWN`/`UNAVAILABLE`)
            zeroes it, landing the package in the no-relevance branch so it
            abstains at both gates. Applied identically regardless of which
            relevance path fed it — this function stays synchronous and pure,
            the verdict is only ever an INPUT.

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

    # Extract meaningful keywords: not a stop word, and either long enough to
    # be unlikely to collide OR a known short identifier.
    #
    # WHY (spec criterion 2, measured live 2026-09-01): the `len(w) > 3` rule
    # this replaces discarded every token of three characters or fewer, which
    # in THIS business throws away the subject of the sentence.
    # "Harga PT PMA berapa all in?" reduced to `harga` and `berapa` — the two
    # most generic words in it — while `PT`, `PMA`, `NIB` and `OSS` vanished.
    # `KITAS`, `NPWP` and `E28A` survived only by an accident of length.
    #
    # It also matters far beyond token count: a business identifier is spelled
    # the SAME in every language, so it is the natural bridge between an
    # Indonesian question and an English chunk. Keeping it is what lets the
    # lexical ratio see across languages at all — measured, it closes seven of
    # the eight cross-language cases in the golden set.
    #
    # A rule keyed on token LENGTH cannot express "keep the entity", so it is
    # now keyed on VOCABULARY.
    query_words = [
        stripped
        for w in query_lower.split()
        if (stripped := w.strip(".,!?;:()[]{}\"'")) not in stop_words
        and (len(stripped) > 3 or stripped in _SHORT_IDENTIFIERS)
    ]

    # Remove duplicates while preserving order
    seen = set()
    query_keywords = []
    for w in query_words:
        # The vocabulary exemption has to be repeated here: this second filter
        # is `len(w) > 2`, so without it every TWO-character identifier the
        # extractor above just kept — `PT` above all, the one the spec names
        # first — was silently dropped again one loop later. Measured
        # 2026-09-03 on this branch before the fix: `pt`, `rp`, `sk`, `cv`,
        # `b1`, `c1`, `c2`, `c7`, `d1`, `d2` never reached the matcher at all.
        if w not in seen and (len(w) > 2 or w in _SHORT_IDENTIFIERS):
            seen.add(w)
            query_keywords.append(w)

    # Combine all context for analysis
    context_text = " ".join(context_gathered).lower() if context_gathered else ""

    # ========== RELEVANCE SCORING ==========
    # Calculate keyword match ratio - how many query keywords appear in context
    # EVERY identifier in the vocabulary is matched on WORD BOUNDARIES; only
    # ordinary keywords keep substring matching.
    #
    # The split is by VOCABULARY, not by length, and that distinction is the
    # whole finding. A first version of this guard drew the line at two
    # characters, on the reasoning that only the shortest tokens collide. It
    # is false, and measured: `oss` is inside `loss`, `cross`, `across`,
    # `possible`; `hak` is inside `shake`; `imb` is inside `climb` and `limb`;
    # `pt` is inside `receipt`, `script`, `empty`, `accept`; `rp` is inside
    # `corporate`. Measured on this tree before the fix, with no sources at
    # all: "Apa itu OSS?" against a chunk about quarterly earnings scored
    # **0.600**, and "Apa itu hak milik?" against a chunk about shaking a
    # bottle scored **0.600** — both far over the 0.15 ABSTAIN gate, on text
    # with no topical relation whatever.
    #
    # Substring matching stays for ordinary keywords because Indonesian
    # morphology depends on it (`pendirian` inside `pendiriannya`). An
    # identifier does not inflect, so it loses nothing by being matched whole.
    #
    # PERF: the whole-context tokenisation only matters for the (rare) query
    # that actually names a vocabulary identifier — most queries contain
    # none, and `re.findall` over the full joined context is the one
    # non-trivial cost in this function. Computed lazily, on the first
    # identifier lookup, and cached so the two `_hits` call sites (query
    # keywords, then the legacy keyword set below) share one pass. Behaviour
    # is identical to the eager version; only the WHEN changes.
    _context_tokens_cache: set[str] | None = None

    def _context_tokens() -> set[str]:
        nonlocal _context_tokens_cache
        if _context_tokens_cache is None:
            _context_tokens_cache = set(re.findall(r"[a-z0-9]+", context_text))
        return _context_tokens_cache

    def _hits(kw: str) -> bool:
        return kw in _context_tokens() if kw in _SHORT_IDENTIFIERS else kw in context_text

    keyword_hits = sum(1 for kw in query_keywords if _hits(kw))

    keyword_match_ratio = keyword_hits / len(query_keywords) if query_keywords else 0.0

    # ---- THE VOCABULARY MAY ONLY ADD EVIDENCE, NEVER SUBTRACT IT ----------
    #
    # The ratio is hits/keywords, so every token this change newly KEEPS also
    # enlarges the denominator. On a chunk that answers part of a composite
    # question, that reads as less evidence than before — the opposite of the
    # intent. Measured on the same relevant KITAS chunk, before this clamp:
    # "syarat visa KITAS" scored 0.600, "syarat visa KITAS NIB OSS" 0.400, and
    # a twelve-identifier question **0.000 — below the gate, where the old
    # rule scored 0.600**. Naming more of the right things made the bot
    # abstain.
    #
    # Dilution is inherited (it is what hits/keywords means, and it applied to
    # ordinary keywords long before this change); what this change controls is
    # how many tokens enter the denominator. So the ratio is computed a second
    # time over exactly the token set the OLD length rule would have produced,
    # and the better of the two wins. The floor is therefore, by construction
    # and not by testing, the score this function returned before the
    # vocabulary existed: adding an identifier can raise a score and can never
    # lower one.
    #
    # ONE DECLARED EXCEPTION, and it is deliberate: the legacy ratio reuses
    # `_hits`, so it inherits the old TOKEN SET but not the old MATCHING. The
    # old length rule was applied to the RAW token, so a three-letter
    # identifier written with punctuation behind it — `OSS?` is four
    # characters — passed it, and was then matched as a substring. Measured:
    # "Apa itu OSS?" against a chunk about a quarterly net LOSS scores 0.600
    # on origin/main and 0.000 here. That is the only direction in which this
    # function may now return less than it used to, it is a precision gain on
    # a safety gate, and it is pinned by a test rather than left to be
    # rediscovered as a regression.
    legacy_seen: set[str] = set()
    legacy_keywords: list[str] = []
    for w in query_lower.split():
        if len(w) > 3 and (stripped := w.strip(".,!?;:()[]{}\"'")) not in stop_words:
            if stripped not in legacy_seen and len(stripped) > 2:
                legacy_seen.add(stripped)
                legacy_keywords.append(stripped)
    if legacy_keywords:
        legacy_hits = sum(1 for kw in legacy_keywords if _hits(kw))
        keyword_match_ratio = max(keyword_match_ratio, legacy_hits / len(legacy_keywords))

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

    # ========== RELEVANCE: PROVENANCE-PRIMARY WHEN A KIND IS DECLARED =======
    # B2.1 inversion (build spec §2). `declared` is the subset of `sources`
    # that named a real retrieved kind — `curated_synthetic`/`trusted_tool_bypass`/
    # `kg_entity` are labels, not measurements, and are excluded by
    # `RETRIEVED_KINDS` itself (score_provenance.py), so they never enter this
    # branch and (per §2.6) keep boosting `source_quality_score` below exactly
    # as they always have.
    declared = [
        s for s in (sources or []) if score_provenance.kind_of(s) in score_provenance.RETRIEVED_KINDS
    ]

    if declared:
        band_index = _declared_band_index(declared)
        # Lexical CORROBORATES: it may raise the band by at most one step,
        # never lower it, and (since we are inside `if declared`) `sources`
        # is provably non-empty, so it never creates relevance out of nothing.
        lexical_band_index = _band_index_from_ratio(keyword_match_ratio)
        # CORROBORATION REQUIRES SOMETHING TO CORROBORATE. A provenance band of
        # NONE is not a weak signal to be helped along — it is the retrieval
        # saying "not relevant", and letting the lexical ratio lift it would be
        # lexical GATING ALONE wearing corroboration's clothes. Round-1
        # adversarial lead (codex-gpt-5.6-sol), reproduced before curing: a
        # `dense_formatted` source at cosine 0.02 (band NONE) with a high
        # keyword ratio scored 0.28 against a 0.15 gate — the exact
        # false-acceptance shape this whole inversion exists to remove, leaking
        # back in through the one source that had DECLARED its irrelevance.
        if band_index >= _BAND_WEAK and lexical_band_index > band_index:
            band_index = min(band_index + 1, _BAND_STRONG)
        # The entity/topic-mismatch guard above is orthogonal to provenance:
        # a chunk can be a strong dense/hybrid hit and still be about the
        # WRONG topic (the measured KITAS-query/KBLI-docs failure mode this
        # guard exists for). Legacy behaviour already forces this case to the
        # zero band (the ratio clamp above always lands under the 0.15 cut),
        # so the override here is not a new rule — it is the same one,
        # carried into the branch provenance now also drives. Without it, a
        # declared dense source's own cosine could outvote a detected topic
        # mismatch, which would regress the dense-declared pipeline-variant
        # tripwires (test_evidence_scoring_abstain.py) that exist precisely
        # to check a provenance-aware scorer against this failure mode.
        if entity_type_mismatch:
            band_index = _BAND_NONE
        semantic_relevance = _BAND_VALUES[band_index]
    else:
        # UNCHANGED legacy path: no declared retrieved kind means no
        # provenance to be primary about — an `unknown` kind is a fact about
        # our knowledge, not a low grade (score_provenance.py). Same four
        # values, same cut points, as before this PR.
        semantic_relevance = _BAND_VALUES[_band_index_from_ratio(keyword_match_ratio)]

    # ========== SUPPORT GATE, FAIL-CLOSED (build spec §2.5) =================
    # Applied identically regardless of which relevance path fed it. `None`
    # means "not consulted" and changes nothing; anything but SUPPORTED zeroes
    # relevance, which routes final_score into the capped no-relevance branch
    # below (never above ~0.08), abstaining at every gate this repo has,
    # including the strictest per-domain LABEL gate (tax, 0.10).
    if support is not None and support is not SupportVerdict.SUPPORTED:
        semantic_relevance = 0.0

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

    # ========== SEMANTIC ALIGNMENT PENALTY (v3 quick-win #1) ==========
    # Use Qdrant's per-source cosine similarity as a sanity gate. If retrieval
    # returned sources but the BEST one has cosine < 0.5 with the query, the
    # keyword-overlap path was probably misled (e.g. KITAS query → KBLI docs
    # share the word "business" but are semantically unrelated). Penalize
    # final score by 0.7× — does not create false negatives because a truly
    # weak retrieval already had low source_quality_score; this just prevents
    # the keyword-driven semantic_relevance from inflating the verdict.
    #
    # Source `score` is set by Qdrant (cosine similarity for our hybrid
    # collections). Skip when sources are absent or top_score is missing.
    #
    # B2.1 (build spec §2.7): retired ONLY when a source declares a retrieved
    # kind. `score_provenance` measured hybrid_rrf_formatted in [0.508, 1] and
    # dense_formatted in [0.5, 1], so `0 < top < 0.5` cannot be entered from
    # any live DECLARED path — the predicate below is structurally unreachable
    # whenever `declared` is non-empty, and skipping it here just says so
    # instead of relying on that being self-evident. Kept, unchanged, for
    # sources that declare NO kind: the legacy `POOR_RETRIEVAL` fixtures sit
    # at a raw 0.18 and their tripwires depend on this branch firing for them.
    if sources and not declared:
        top_source_cosine = max(
            (s.get("score", 0.0) for s in sources if isinstance(s, dict)),
            default=0.0,
        )
        if 0 < top_source_cosine < 0.5 and final_score > 0.15:
            penalized = round(final_score * 0.7, 2)
            logger.info(
                "evidence_score: semantic-alignment penalty applied (top_cosine=%.2f, %.2f → %.2f)",
                top_source_cosine,
                final_score,
                penalized,
            )
            final_score = penalized

    return round(min(final_score, 1.0), 2)


# ============================================================================
# Domain-aware ABSTAIN thresholds (v3 quick-win #2)
# ============================================================================
# A single global ABSTAIN_THRESHOLD (0.15) over-rejects on Indonesian-language
# domains (tax, visa) where docs naturally have lower keyword overlap with
# IT/EN queries, and under-rejects on KBLI where false-positive risk is
# higher (many business-vocabulary collisions). Per-domain thresholds let
# the gate breathe in the right direction.
#
# The ENV override DOMAIN_ABSTAIN_THRESHOLDS=tax:0.10,kbli:0.20,default:0.15
# is read at process start and merged on top of these defaults.

DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT: dict[str, float] = {
    "tax": 0.10,  # Indonesian tax docs, lower keyword overlap with IT/EN
    "visa": 0.12,  # immigration docs are mostly Indonesian/English mix
    "pricing": 0.15,  # baseline
    "kbli": 0.20,  # higher bar — business vocabulary creates false positives
    "default": 0.15,
}


def _parse_domain_threshold_overrides(spec: str) -> dict[str, float]:
    """Parse `DOMAIN_ABSTAIN_THRESHOLDS=tax:0.10,kbli:0.20` env var format."""
    out: dict[str, float] = {}
    for raw in (spec or "").split(","):
        raw = raw.strip()
        if not raw or ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        try:
            value = float(val)
        except ValueError:
            logger.warning(
                "DOMAIN_ABSTAIN_THRESHOLDS: skipping malformed entry %r",
                raw,
            )
            continue
        # Evidence scores live in [0.0, 1.0]; an override outside that range
        # (including nan/inf, which fail this comparison) would silently
        # disable or force the abstain gate for a whole domain — skip it.
        if not (0.0 <= value <= 1.0):
            logger.warning(
                "DOMAIN_ABSTAIN_THRESHOLDS: skipping out-of-range entry %r",
                raw,
            )
            continue
        out[key.strip().lower()] = value
    return out


def _build_domain_thresholds() -> dict[str, float]:
    merged = dict(DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT)
    merged.update(
        _parse_domain_threshold_overrides(
            os.environ.get("DOMAIN_ABSTAIN_THRESHOLDS", ""),
        ),
    )
    return merged


_DOMAIN_THRESHOLDS = _build_domain_thresholds()


def classify_query_domain(query: str) -> str:
    """Lightweight domain classifier for ABSTAIN-threshold lookup.

    Returns one of: tax, visa, pricing, kbli, default.

    Intentionally a tiny heuristic — full intent classification happens
    elsewhere; this is just the routing key for per-domain ABSTAIN tuning.
    """
    q = (query or "").lower()
    if any(
        kw in q
        for kw in (
            "tax",
            "tasse",
            "imposta",
            "pajak",
            "ppn",
            "pph",
            "npwp",
            "spt",
            "pkp",
            "fiscal",
            "fiscale",
            "tarif pajak",
        )
    ):
        return "tax"
    if any(
        kw in q
        for kw in (
            "visa",
            "visto",
            "kitas",
            "kitap",
            "imigrasi",
            "immigration",
            "stay permit",
            "permesso di soggiorno",
            "rptka",
            "itk",
            "c1",
            "c2",
            "d1",
            "d2",
            "e33g",
            "b211",
        )
    ):
        return "visa"
    if any(
        kw in q
        for kw in (
            "kbli",
            "codice kbli",
            "kode kbli",
            "klasifikasi",
            "classification",
            "kegiatan usaha",
            "business activity",
        )
    ):
        return "kbli"
    if any(
        kw in q
        for kw in (
            "quanto costa",
            "price",
            "prezzo",
            "costo",
            "harga",
            "berapa biaya",
            "cost",
            "pricing",
            "tariffa",
            "fee",
        )
    ):
        return "pricing"
    return "default"


def get_abstain_threshold(query: str) -> float:
    """Return the ABSTAIN threshold to apply for ``query``.

    Falls back to the ``"default"`` entry, which itself defaults to 0.15
    (matching the legacy global ``ABSTAIN_THRESHOLD`` from
    ``EvidenceScoreConstants``).
    """
    domain = classify_query_domain(query)
    return _DOMAIN_THRESHOLDS.get(domain, _DOMAIN_THRESHOLDS["default"])


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
