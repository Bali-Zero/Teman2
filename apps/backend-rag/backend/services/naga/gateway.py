"""Naga Gateway — fast rule-based query classifier.

Routes every incoming query into ``(tier, domain, mode, ttl)`` using
pure regex / keyword matching.  No LLM calls, no network — sub-millisecond.

Usage::

    from backend.services.naga.gateway import classify_query

    result = classify_query("qual e il costo del KITAS 2026?", channel="telegram")
    # GatewayResult(tier='flash', domain='indonesia', mode='oneshot', ttl_seconds=30)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.services.naga.config.naga_config import NagaConfig

# ---------------------------------------------------------------------------
# Singleton config — built once at import time
# ---------------------------------------------------------------------------

_config = NagaConfig()

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GatewayResult:
    """Immutable classification output.

    Attributes:
        tier: Research depth — ``flash`` | ``deep`` | ``exhaustive``.
        domain: Content domain — ``indonesia`` | ``general`` | ``hybrid``.
        mode: Interaction style — ``oneshot`` | ``conversational``.
        ttl_seconds: Cache TTL in seconds.
    """

    tier: str
    domain: str
    mode: str
    ttl_seconds: int


# ---------------------------------------------------------------------------
# Compiled regex patterns (built once at module load)
# ---------------------------------------------------------------------------

_INDONESIA_KW_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:"
    r"kitas|kitap|visa|visto|imigrasi|izin tinggal"
    r"|kbli|pt pma|perseroan|cv|yayasan"
    r"|pajak|tax|npwp|pph|ppn"
    r"|notaris|akta|ahu"
    r"|oss|nib"
    r"|bali|indonesia|jakarta"
    r"|regulasi|peraturan|undang|permen|pp|perpres"
    r"|golden visa|investor visa|retirement visa"
    r"|izin usaha|sertifikat|hak pakai|hgb"
    r"|ditjen|kemenkumham|bkpm"
    r"|tarif|biaya|pnbp|retribusi"
    r")\b",
    re.IGNORECASE,
)

_COMPLEXITY_SIGNAL_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:"
    r"analis[ie]|analyze"
    r"|compare|confronto"
    r"|comprehensive"
    r"|report"
    r"|research"
    r"|studio"
    r"|impatto|impact"
    r"|pro e contro|trade-off"
    r"|completa|dettagliata"
    r"|storia|timeline"
    r")\b",
    re.IGNORECASE,
)

_CONVERSATIONAL_SIGNAL_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:"
    r"esplora|explore"
    r"|investigate"
    r"|non sono sicuro"
    r"|diverse prospettive"
    r")\b",
    re.IGNORECASE,
)

# Valid tiers and domains for force-override validation
_VALID_TIERS = frozenset({"flash", "deep", "exhaustive"})
_VALID_DOMAINS = frozenset({"indonesia", "general", "hybrid"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_query(
    query: str,
    channel: str | None = None,
    force_tier: str | None = None,
    force_domain: str | None = None,
) -> GatewayResult:
    """Classify *query* into tier / domain / mode / TTL.

    Pure regex + keyword matching — no LLM, no I/O.  Designed to run in
    well under 1 ms.

    Args:
        query: Raw user query text.
        channel: Optional channel name (``telegram``, ``web_chat``, etc.).
            Affects TTL and may force tier to ``flash`` (telegram).
        force_tier: Override the classified tier (``flash`` / ``deep`` /
            ``exhaustive``).  Invalid values are silently ignored.
        force_domain: Override the classified domain (``indonesia`` /
            ``general`` / ``hybrid``).  Invalid values are silently ignored.

    Returns:
        Frozen :class:`GatewayResult` with the classification.
    """
    # -- Domain ----------------------------------------------------------
    domain = _classify_domain(query)
    if force_domain is not None and force_domain in _VALID_DOMAINS:
        domain = force_domain

    # -- Tier ------------------------------------------------------------
    tier = _classify_tier(query)

    # Telegram forces flash (unless force_tier overrides)
    if channel == "telegram" and force_tier is None:
        tier = "flash"

    if force_tier is not None and force_tier in _VALID_TIERS:
        tier = force_tier

    # -- Mode ------------------------------------------------------------
    mode = _classify_mode(query, tier)

    # -- TTL -------------------------------------------------------------
    ttl = _resolve_ttl(tier, channel)

    return GatewayResult(tier=tier, domain=domain, mode=mode, ttl_seconds=ttl)


# ---------------------------------------------------------------------------
# Internal classifiers
# ---------------------------------------------------------------------------


def _classify_domain(query: str) -> str:
    """Return ``indonesia``, ``general``, or ``hybrid``."""
    matches = _INDONESIA_KW_PATTERN.findall(query)
    count = len(matches)

    if count == 0:
        return "general"

    # Heuristic: if 2+ Indonesia keywords AND query also contains
    # non-Indonesia country/concept references → hybrid.
    if count >= 2 and _has_general_content(query):
        return "hybrid"

    return "indonesia"


def _has_general_content(query: str) -> bool:
    """Detect non-Indonesia geographic or conceptual references.

    Used to distinguish *hybrid* from pure *indonesia* when Indonesia
    keywords are present.
    """
    # Countries / regions that signal a cross-domain comparison
    general_markers = re.compile(
        r"\b(?:"
        r"portogallo|portugal|singapore|malaysia|thailand|tailandia"
        r"|dubai|europe|europa|usa|states|vietnam|philippines|filippine"
        r"|hong kong|japan|giappone|korea|corea|australia|uk|canada"
        r"|quantum|blockchain|ai|machine learning"
        r")\b",
        re.IGNORECASE,
    )
    return bool(general_markers.search(query))


def _classify_tier(query: str) -> str:
    """Return ``flash``, ``deep``, or ``exhaustive``."""
    signals = _COMPLEXITY_SIGNAL_PATTERN.findall(query)
    word_count = len(query.split())

    if len(signals) >= 3 or word_count > 40:
        return "exhaustive"
    if len(signals) >= 1 or word_count > 15:
        return "deep"
    return "flash"


def _classify_mode(query: str, tier: str) -> str:
    """Return ``oneshot`` or ``conversational``."""
    if tier == "exhaustive":
        return "conversational"
    if _CONVERSATIONAL_SIGNAL_PATTERN.search(query):
        return "conversational"
    return "oneshot"


def _resolve_ttl(tier: str, channel: str | None) -> int:
    """Pick TTL from channel overrides or fall back to tier default."""
    if channel is not None and channel in _config.channel_ttls:
        return _config.channel_ttls[channel]

    budget = _config.tier_budgets.get(tier)
    if budget is not None:
        return budget.default_ttl_seconds

    # Defensive fallback — should never happen with valid tiers
    return 60
