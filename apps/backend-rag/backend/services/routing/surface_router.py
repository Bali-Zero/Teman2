"""SurfaceRouter — R5 Phase 3.

2-layer routing:
  Layer 1: Keyword scoring via QueryRouterIntegration (< 1 ms, ~80 % of queries).
  Layer 2: Claude Haiku 4.5 classifier when confidence < HAIKU_THRESHOLD (async, mocked in tests).

Feature flag: SURFACE_ROUTER_ENABLED env var (default "false" — shadow mode).
Skills surface: bali_zero_skills_hybrid on Qdrant Cloud (R5 AIL #1, 2026-05-17).

Ref: docs/superpowers/specs/2026-05-16-r5-phase3-surface-router-design.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.routing.query_router_integration import QueryRouterIntegration

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HAIKU_CONFIDENCE_THRESHOLD: float = 0.60
HAIKU_TIMEOUT_S: float = 3.0
SURFACE_ROUTER_ENABLED: bool = os.getenv("SURFACE_ROUTER_ENABLED", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Surface names (string enum pattern — avoids enum import overhead)
# ---------------------------------------------------------------------------

class Surface:
    QDRANT_VISA = "qdrant_visa"
    QDRANT_TAX = "qdrant_tax"
    QDRANT_COMPANY = "qdrant_company"
    QDRANT_PROPERTY = "qdrant_property"
    QDRANT_PRICING = "qdrant_pricing"
    QDRANT_NEWS = "qdrant_news"
    QDRANT_SKILLS = "qdrant_skills"


# ---------------------------------------------------------------------------
# Canonical surface → collections mapping (aligns with collection_registry.py)
# ---------------------------------------------------------------------------

SURFACE_COLLECTIONS: dict[str, tuple[str, list[str]]] = {
    # surface → (primary_collection, [primary, fallback1, ...])
    Surface.QDRANT_VISA: (
        "visa_oracle",
        ["visa_oracle", "immigration_circulars", "legal_unified_hybrid_hybrid"],
    ),
    Surface.QDRANT_TAX: (
        "tax_genius_hybrid",
        ["tax_genius_hybrid", "legal_unified_hybrid_hybrid"],
    ),
    Surface.QDRANT_COMPANY: (
        "kbli_2025_final_hybrid",
        ["kbli_2025_final_hybrid", "training_conversations_hybrid", "legal_unified_hybrid_hybrid"],
    ),
    Surface.QDRANT_PROPERTY: (
        "legal_unified_hybrid_hybrid",
        ["legal_unified_hybrid_hybrid", "kbli_2025_final_hybrid"],
    ),
    Surface.QDRANT_PRICING: (
        "bali_zero_pricing_hybrid",
        ["bali_zero_pricing_hybrid"],
    ),
    Surface.QDRANT_NEWS: (
        "balizero_news",
        ["balizero_news", "visa_oracle", "legal_unified_hybrid_hybrid"],
    ),
    Surface.QDRANT_SKILLS: (
        "bali_zero_skills_hybrid",
        ["bali_zero_skills_hybrid"],
    ),
}

# Domain → Surface mapping (derived from QueryRouter domain scoring)
_DOMAIN_TO_SURFACE: dict[str, str] = {
    "visa": Surface.QDRANT_VISA,
    "circular": Surface.QDRANT_VISA,
    "tax": Surface.QDRANT_TAX,
    "kbli": Surface.QDRANT_COMPANY,
    "legal": Surface.QDRANT_COMPANY,
    "business": Surface.QDRANT_COMPANY,
    "property": Surface.QDRANT_PROPERTY,
    "news": Surface.QDRANT_NEWS,
    "team": Surface.QDRANT_PRICING,  # team queries → pricing (same as QueryRouter)
    "books": Surface.QDRANT_VISA,    # books → fallback (same as QueryRouter)
}

# Skills-trigger keywords (ops/internal queries)
_SKILLS_KEYWORDS: frozenset[str] = frozenset({
    "internal workflow",
    "ops procedure",
    "internal skill",
    "team workflow",
    "onboarding checklist",
    "skill for",
    "internal ops",
    "checklist",
    "procedure",
    "workflow",
})

# KITAS/KITAP acronyms — not in QueryRouter's VISA_KEYWORDS, must intercept here
_VISA_ACRONYMS: frozenset[str] = frozenset({
    "kitas", "kitap", "imta", "itas", "itap", "vitas", "skt",
})

# Tax terms not in QueryRouter's TAX_KEYWORDS (or suppressed by pricing check upstream)
_TAX_INTERCEPTS: frozenset[str] = frozenset({
    "pph", "pph21", "pph 21", "ppn", "pajak penghasilan",
    "bphtb", "spt", "efin", "npwp", "nppn",
    # These appear in queries where "rate"/"charge"/"fee" would mis-fire pricing:
    "income tax rate", "corporate income tax", "corporate tax rate",
    "tax rate for", "withholding tax rate",
})

# News-specific terms — when present AND news is in active_domains, news wins
_NEWS_TERMS: frozenset[str] = frozenset({
    "berita", "terbaru", "news", "latest news", "recent changes",
    "pengumuman", "announcement",
})


# ---------------------------------------------------------------------------
# SurfaceDecision dataclass
# ---------------------------------------------------------------------------

@dataclass
class SurfaceDecision:
    surface: str
    primary_collection: str
    collections: list[str]
    domain: str
    confidence: float
    layer_used: int           # 1 = keyword, 2 = haiku
    is_local_only: bool
    latency_ms: float


def _make_decision(
    surface: str,
    domain: str,
    confidence: float,
    layer_used: int,
    latency_ms: float,
) -> SurfaceDecision:
    primary, colls = SURFACE_COLLECTIONS[surface]
    return SurfaceDecision(
        surface=surface,
        primary_collection=primary,
        collections=list(colls),
        domain=domain,
        confidence=confidence,
        layer_used=layer_used,
        is_local_only=False,  # R5 AIL #1: skills moved to Qdrant Cloud (bali_zero_skills_hybrid)
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# QueryRouterIntegration proxy (lazy import to avoid circular dep)
# ---------------------------------------------------------------------------

def _get_integration() -> QueryRouterIntegration:
    from backend.services.routing.query_router_integration import QueryRouterIntegration
    return QueryRouterIntegration()


# ---------------------------------------------------------------------------
# Haiku classifier prompt
# ---------------------------------------------------------------------------

_HAIKU_SYSTEM = (
    "You are a query router for Bali Zero, an Indonesian business services company. "
    "Classify the user query into exactly ONE domain from this list: "
    "visa, tax, company, property, pricing, news, skills. "
    "Reply ONLY with a JSON object: "
    '{"domain": "<domain>", "confidence": <0.0-1.0>}'
)


# ---------------------------------------------------------------------------
# SurfaceRouter
# ---------------------------------------------------------------------------

class SurfaceRouter:
    """Intelligent 2-layer surface router for Bali Zero RAG.

    Layer 1: Keyword scoring via QueryRouterIntegration (< 1 ms).
    Layer 2: Claude Haiku when Layer 1 confidence < 0.60.

    Usage:
        router = SurfaceRouter()
        decision = router.decide(query)
        # async callers can use await router.adecide(query) for Haiku support
    """

    def __init__(
        self,
        enabled: bool = SURFACE_ROUTER_ENABLED,
        haiku_threshold: float = HAIKU_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.enabled = enabled
        self.haiku_threshold = haiku_threshold
        self._integration: QueryRouterIntegration | None = None
        logger.info(
            "SurfaceRouter init: enabled=%s haiku_threshold=%.2f",
            enabled, haiku_threshold,
        )

    def _router(self) -> QueryRouterIntegration:
        if self._integration is None:
            self._integration = _get_integration()
        return self._integration

    # ------------------------------------------------------------------
    # Skills detection (pre-check before domain routing)
    # ------------------------------------------------------------------

    def _is_skills_query(self, query: str) -> bool:
        q = query.lower()
        # "internal workflow", "ops procedure", "skill for", etc.
        # Must have 2+ signals to avoid false positives on "checklist for visa"
        hits = sum(1 for kw in _SKILLS_KEYWORDS if kw in q)
        return hits >= 1 and any(kw in q for kw in ("internal", "ops", "skill", "workflow", "procedure"))

    # ------------------------------------------------------------------
    # Pricing detection (delegate to integration's is_pricing_query)
    # ------------------------------------------------------------------

    def _is_pricing_query(self, query: str) -> bool:
        return self._router().is_pricing_query(query)

    # ------------------------------------------------------------------
    # Layer 1: keyword routing via QueryRouterIntegration
    # ------------------------------------------------------------------

    def _layer1(self, query: str) -> tuple[str, float, str]:
        """Returns (surface, confidence, domain)."""
        result = self._router().route_query(query, enable_fallbacks=True)

        collection = result.get("collection_name", "")
        confidence: float = result.get("confidence", 1.0)
        active_domains: list[str] = result.get("active_domains", [])

        # News signal: when news is in active_domains and news terms present, news wins
        if self._has_news_signal(query, active_domains):
            return Surface.QDRANT_NEWS, confidence, "news"

        # Primary domain from collection
        domain = _collection_to_domain(collection)

        # Property override: 'property' in active_domains + legal_unified primary → property
        # BUT only when kbli is NOT in active_domains (kbli beats property on company queries)
        # "business" alone (e.g. "foreigner") does NOT override property — check counts via
        # the router directly if kbli is the stronger signal.
        if (
            "property" in active_domains
            and "kbli" not in active_domains
            and collection in ("legal_unified", "legal_unified_hybrid_hybrid")
        ):
            domain = "property"

        surface = _domain_to_surface(domain, collection)
        return surface, confidence, domain

    # ------------------------------------------------------------------
    # Layer 2: Haiku classifier (async)
    # ------------------------------------------------------------------

    async def _classify_with_haiku(self, query: str) -> SurfaceDecision | None:
        """Classify with Claude Haiku. Returns None on any failure."""
        try:
            from backend.llm.claude_oauth_client import ClaudeOAuthClient
            client = ClaudeOAuthClient(model="claude-haiku-4-5-20251001", timeout_s=int(HAIKU_TIMEOUT_S))
            prompt = f"{_HAIKU_SYSTEM}\n\nUser query: {query}"
            text = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: client.complete(prompt)
                ),
                timeout=HAIKU_TIMEOUT_S,
            )
            data = json.loads(text.strip())
            domain: str = data.get("domain", "visa")
            haiku_confidence: float = float(data.get("confidence", 0.5))

            # Map Haiku domain → surface
            domain_surface_map = {
                "visa": Surface.QDRANT_VISA,
                "tax": Surface.QDRANT_TAX,
                "company": Surface.QDRANT_COMPANY,
                "property": Surface.QDRANT_PROPERTY,
                "pricing": Surface.QDRANT_PRICING,
                "news": Surface.QDRANT_NEWS,
                "skills": Surface.QDRANT_SKILLS,
            }
            surface = domain_surface_map.get(domain, Surface.QDRANT_VISA)
            return _make_decision(surface, domain, haiku_confidence, layer_used=2, latency_ms=0.0)
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning("SurfaceRouter: Haiku timeout on query '%s'", query[:60])
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("SurfaceRouter: Haiku error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Public API: sync decide() (keyword only)
    # ------------------------------------------------------------------

    def _is_visa_acronym_query(self, query: str) -> bool:
        # Strip punctuation for matching (handles "KITAS?" "KITAS.")
        import re
        q = re.sub(r"[^\w\s]", " ", query.lower())
        return any(f" {kw} " in f" {q} " or q.strip().startswith(kw) for kw in _VISA_ACRONYMS)

    def _is_tax_intercept(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in _TAX_INTERCEPTS)

    def _has_news_signal(self, query: str, active_domains: list[str]) -> bool:
        q = query.lower()
        return "news" in active_domains and any(kw in q for kw in _NEWS_TERMS)

    def decide(self, query: str) -> SurfaceDecision:
        """Route a query synchronously (keyword path only).

        For Haiku enrichment on ambiguous queries, use adecide() from async context.
        """
        t0 = time.perf_counter()

        # Fast pre-checks (ordered by specificity — pricing first to catch "KITAS renewal cost")
        if self._is_skills_query(query):
            elapsed = (time.perf_counter() - t0) * 1000
            return _make_decision(Surface.QDRANT_SKILLS, "skills", 0.90, 1, elapsed)

        # Tax intercepts first: PPh/PPN/BPHTB/NPWP not in QueryRouter's TAX_KEYWORDS.
        # Must come BEFORE pricing check so "tax rate" / "income tax" don't mis-fire pricing.
        if self._is_tax_intercept(query):
            elapsed = (time.perf_counter() - t0) * 1000
            return _make_decision(Surface.QDRANT_TAX, "tax", 0.85, 1, elapsed)

        if self._is_pricing_query(query):
            # Suppress pricing if query has "tax" context to avoid "tax rate" → pricing.
            q_lower = query.lower()
            has_tax_context = any(
                kw in q_lower for kw in ("tax ", " tax", "pajak", "withholding", "income tax", "corporate tax")
            )
            if not has_tax_context:
                elapsed = (time.perf_counter() - t0) * 1000
                return _make_decision(Surface.QDRANT_PRICING, "pricing", 0.95, 1, elapsed)

        # KITAS/KITAP acronyms — intercept after pricing (e.g. "KITAS cost" → pricing wins)
        if self._is_visa_acronym_query(query):
            elapsed = (time.perf_counter() - t0) * 1000
            return _make_decision(Surface.QDRANT_VISA, "visa", 0.88, 1, elapsed)

        surface, confidence, domain = self._layer1(query)
        elapsed = (time.perf_counter() - t0) * 1000

        logger.info(
            "SurfaceRouter L1: surface=%s domain=%s confidence=%.2f latency=%.1fms",
            surface, domain, confidence, elapsed,
        )

        return _make_decision(surface, domain, confidence, layer_used=1, latency_ms=elapsed)

    # ------------------------------------------------------------------
    # Public API: async adecide() (keyword + Haiku when ambiguous)
    # ------------------------------------------------------------------

    async def adecide(self, query: str) -> SurfaceDecision:
        """Route a query with optional Haiku enrichment for ambiguous cases."""
        t0 = time.perf_counter()

        # Fast pre-checks (no Haiku needed)
        if self._is_skills_query(query):
            elapsed = (time.perf_counter() - t0) * 1000
            return _make_decision(Surface.QDRANT_SKILLS, "skills", 0.90, 1, elapsed)

        if self._is_pricing_query(query):
            elapsed = (time.perf_counter() - t0) * 1000
            return _make_decision(Surface.QDRANT_PRICING, "pricing", 0.95, 1, elapsed)

        # Layer 1
        surface, confidence, domain = self._layer1(query)

        # Layer 2: only when enabled AND confidence is low
        if self.enabled and confidence < self.haiku_threshold:
            logger.info(
                "SurfaceRouter: L1 confidence=%.2f < threshold=%.2f → Haiku",
                confidence, self.haiku_threshold,
            )
            try:
                haiku_decision = await self._classify_with_haiku(query)
                if haiku_decision is not None:
                    haiku_decision.latency_ms = (time.perf_counter() - t0) * 1000
                    return haiku_decision
            except (TimeoutError, asyncio.TimeoutError):
                pass  # fall through to keyword result

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(
            "SurfaceRouter final: surface=%s domain=%s conf=%.2f layer=%d lat=%.1fms",
            surface, domain, confidence, 1, elapsed,
        )
        return _make_decision(surface, domain, confidence, layer_used=1, latency_ms=elapsed)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _collection_to_domain(collection: str) -> str:
    """Derive domain from physical collection name."""
    mapping = {
        "visa_oracle": "visa",
        "immigration_circulars": "visa",
        "tax_genius": "tax",
        "tax_genius_hybrid": "tax",
        "kbli_2025_final": "company",
        "kbli_2025_final_hybrid": "company",
        "legal_unified": "legal",
        "legal_unified_hybrid_hybrid": "legal",
        "legal_architect": "legal",
        "training_conversations_hybrid": "company",
        "bali_zero_pricing_hybrid": "pricing",
        "balizero_news": "news",
        "bali_zero_skills_hybrid": "skills",
    }
    return mapping.get(collection, "legal")


def _domain_to_surface(domain: str, collection: str) -> str:
    """Map domain (+ collection hint) to surface."""
    if collection == "bali_zero_pricing_hybrid":
        return Surface.QDRANT_PRICING

    if domain == "property":
        return Surface.QDRANT_PROPERTY

    if domain == "news":
        return Surface.QDRANT_NEWS

    if domain in ("legal", "company", "kbli", "business"):
        return Surface.QDRANT_COMPANY

    return _DOMAIN_TO_SURFACE.get(domain, Surface.QDRANT_COMPANY)
