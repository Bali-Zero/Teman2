"""NLM Orchestrator — unified NotebookLM routing with multi-domain support.

Wraps NLMEnrichmentService + NotebookLMCacheService + CrossNotebookCorrelator
into a single interface. Expands from 4 to 8+ domains.

# Organo: backend-rag/oracle → produce NLMResult → consuma da orchestrator_core
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Base domain → notebook mapping (4 NB today).
# NB IDs taken from nlm_verifier.py + nlm_notebook_registry.py.
# This is the SAFE default the chat has always shipped with.
# NOTE: the "property" entry still points at NB-3 Company here because that
# was the historical fallback when NB-5 did not yet exist in production.
# The extended map below corrects this; enable via NLM_EXTENDED_ROUTING.
_BASE_DOMAIN_NOTEBOOK_MAP: dict[str, list[str]] = {
    "visa": ["cff93ab0-813a-42f2-a8de-36987e724271"],          # NB-2
    "immigration": ["cff93ab0-813a-42f2-a8de-36987e724271"],    # NB-2
    "tax": ["d4b2eedb-9863-4a1a-81ff-a11b0b45d853"],           # NB-4
    "legal": ["933509f9-1561-403d-bd44-4a7a67a36df2"],          # NB-3
    "company": ["933509f9-1561-403d-bd44-4a7a67a36df2"],        # NB-3
    "kbli": ["cff93ab0-813a-42f2-a8de-36987e724271"],           # NB-2
    "property": ["933509f9-1561-403d-bd44-4a7a67a36df2"],       # NB-3 (historical fallback)
}

# Extended map — adds NB-5..8 and NB-10 so RAG can reach every notebook the
# evaluator pipelines already feed nightly. Also corrects the `property`
# entry to point at NB-5 and adds an `operations`/`editorial`/`lifestyle`/
# `team` alias set that mirrors the keywords used by
# `nlm_notebook_registry.NLM_NOTEBOOKS` (the authoritative registry).
#
# Sources:
#   - NB-5 (property)    d9438180-5e63-4e2a-a473-6061101f6a8d
#   - NB-6 (operations)  85207af3-352f-4554-8d2a-18f42cc541ba
#   - NB-7 (editorial)   f51ab8a0-50d0-49f1-a64f-ebc131fed7b8
#   - NB-8 (lifestyle)   4fd8cd0f-93f1-4e43-9c9e-86c0d581852c
#   - NB-10 (team)       f0307c2c-9220-4160-93c8-f4a6ef4a3b65
_EXTENDED_DOMAIN_NOTEBOOK_MAP: dict[str, list[str]] = {
    **_BASE_DOMAIN_NOTEBOOK_MAP,
    "property": ["d9438180-5e63-4e2a-a473-6061101f6a8d"],       # NB-5 (corrected)
    "real_estate": ["d9438180-5e63-4e2a-a473-6061101f6a8d"],    # NB-5
    "zoning": ["d9438180-5e63-4e2a-a473-6061101f6a8d"],         # NB-5
    "operations": ["85207af3-352f-4554-8d2a-18f42cc541ba"],     # NB-6
    "compliance": ["85207af3-352f-4554-8d2a-18f42cc541ba"],     # NB-6
    "editorial": ["f51ab8a0-50d0-49f1-a64f-ebc131fed7b8"],      # NB-7
    "content": ["f51ab8a0-50d0-49f1-a64f-ebc131fed7b8"],        # NB-7
    "lifestyle": ["4fd8cd0f-93f1-4e43-9c9e-86c0d581852c"],      # NB-8
    "expat": ["4fd8cd0f-93f1-4e43-9c9e-86c0d581852c"],          # NB-8
    "healthcare": ["4fd8cd0f-93f1-4e43-9c9e-86c0d581852c"],     # NB-8
    "team": ["f0307c2c-9220-4160-93c8-f4a6ef4a3b65"],           # NB-10
    "hr": ["f0307c2c-9220-4160-93c8-f4a6ef4a3b65"],             # NB-10
    "payroll": ["f0307c2c-9220-4160-93c8-f4a6ef4a3b65"],        # NB-10
}


def _extended_routing_enabled() -> bool:
    """Read env var at call time so tests and dev restarts flip cleanly."""
    import os
    raw = os.environ.get("NLM_EXTENDED_ROUTING", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _active_domain_map() -> dict[str, list[str]]:
    """Return the map used for real routing — extended only when the flag is set."""
    return (
        _EXTENDED_DOMAIN_NOTEBOOK_MAP
        if _extended_routing_enabled()
        else _BASE_DOMAIN_NOTEBOOK_MAP
    )


# Public alias retained for backwards-compat with any importer that
# references DOMAIN_NOTEBOOK_MAP_V2 directly. It mirrors the base map so
# existing behavior is unchanged when the flag is off, and points at the
# extended map when the flag is on at import time.
DOMAIN_NOTEBOOK_MAP_V2: dict[str, list[str]] = _active_domain_map()

# Cross-domain queries fan out to multiple notebooks
CROSS_DOMAIN_NOTEBOOKS: dict[str, list[str]] = {
    "visa+tax": [
        "cff93ab0-813a-42f2-a8de-36987e724271",  # NB-2
        "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # NB-4
    ],
    "company+visa": [
        "933509f9-1561-403d-bd44-4a7a67a36df2",  # NB-3
        "cff93ab0-813a-42f2-a8de-36987e724271",  # NB-2
    ],
    # Extended cross-domain patterns only kick in when NLM_EXTENDED_ROUTING=1
    # (guarded inside _resolve_notebooks). Declared here so the shapes are
    # visible in one place.
    "property+tax": [
        "d9438180-5e63-4e2a-a473-6061101f6a8d",  # NB-5
        "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # NB-4
    ],
    "property+company": [
        "d9438180-5e63-4e2a-a473-6061101f6a8d",  # NB-5
        "933509f9-1561-403d-bd44-4a7a67a36df2",  # NB-3
    ],
    "team+tax": [
        "f0307c2c-9220-4160-93c8-f4a6ef4a3b65",  # NB-10
        "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # NB-4
    ],
    "operations+compliance": [
        "85207af3-352f-4554-8d2a-18f42cc541ba",  # NB-6
    ],
}

# Pairs that only become meaningful once extended routing is on
_EXTENDED_CROSS_KEYS = frozenset(
    {"property+tax", "property+company", "team+tax", "operations+compliance"}
)

# Redis cache config
NLM_CACHE_TTL = 86400  # 24 hours
NLM_CACHE_PREFIX = "zantara:nlm_orch"

# Rate limiting
RATE_KEY = "nlm_orch:rate_count"
RATE_LIMIT = 10
RATE_TTL = 3600  # 1 hour


@dataclass
class NLMResult:
    """Structured result from NLM orchestrator."""

    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    domain: str = ""
    notebooks_queried: list[str] = field(default_factory=list)
    cached: bool = False
    synthesis: str = ""  # For multi-NB queries


class NLMOrchestrator:
    """Unified NLM routing: single-NB query, multi-NB fan-out, caching.

    Graceful degradation: if NLM bridge is unreachable, returns None
    without blocking the caller. All errors are caught and logged.
    """

    def __init__(
        self,
        enrichment_service: Any = None,
        cache_service: Any = None,
        correlator: Any = None,
        redis_client: Any = None,
    ) -> None:
        self._enrichment = enrichment_service
        self._cache = cache_service
        self._correlator = correlator
        self._redis = redis_client

    async def query(
        self,
        question: str,
        domain: str = "general",
        is_cross_domain: bool = False,
        timeout: float = 10.0,
    ) -> NLMResult | None:
        """Route query to appropriate notebook(s) and return result.

        Args:
            question: The question to ask NLM.
            domain: Primary query domain (visa, tax, etc.).
            is_cross_domain: Whether to fan out to multiple notebooks.
            timeout: Per-notebook query timeout.

        Returns:
            NLMResult on success, None on any failure.
        """
        try:
            # Rate limit check
            if not await self._check_rate_limit():
                logger.debug("NLM orchestrator: rate limit reached")
                return None

            # Check cache
            cached = await self._check_cache(question, domain)
            if cached is not None:
                return cached

            # Resolve notebooks
            notebooks = self._resolve_notebooks(domain, is_cross_domain)
            if not notebooks:
                logger.debug("NLM orchestrator: no notebook for domain=%s", domain)
                return None

            # Query notebook(s)
            if len(notebooks) == 1:
                result = await self._query_single(question, notebooks[0], domain, timeout)
            else:
                result = await self._query_multi(question, notebooks, domain, timeout)

            # Cache result
            if result is not None:
                await self._cache_result(question, domain, result)

            # Increment rate counter
            await self._increment_rate()

            return result

        except Exception as exc:
            logger.warning("NLM orchestrator: unexpected error (%s)", exc, exc_info=True)
            return None

    def _resolve_notebooks(self, domain: str, is_cross_domain: bool) -> list[str]:
        """Resolve which notebook(s) to query for a domain.

        Behaviour is controlled by the ``NLM_EXTENDED_ROUTING`` env var:

        - ``unset`` / ``0`` / ``false`` — only the base 4-NB map is used for
          routing (visa/immigration/kbli → NB-2, legal/company/property →
          NB-3, tax → NB-4). A *shadow-mode* log line is emitted whenever the
          extended map would have picked a different notebook, so the
          divergence is observable without changing user-visible responses.
        - ``1`` / ``true`` / ``yes`` — the extended map is the live map:
          ``property`` resolves to NB-5, ``operations`` to NB-6, ``editorial``
          to NB-7, ``lifestyle`` to NB-8, ``team`` to NB-10 (plus aliases).
        """
        extended = _extended_routing_enabled()

        if is_cross_domain and self._correlator is not None:
            for key, nbs in CROSS_DOMAIN_NOTEBOOKS.items():
                if domain not in key:
                    continue
                if key in _EXTENDED_CROSS_KEYS and not extended:
                    # Don't ship a cross-NB fan-out to a freshly-added NB
                    # until Zero flips the flag; log the would-be choice.
                    logger.info(
                        "nlm_routing shadow: cross '%s' -> %s (extended only)",
                        key,
                        nbs,
                    )
                    continue
                return nbs

        active = _active_domain_map()
        notebooks = active.get(domain, [])

        if not extended:
            # Shadow-mode observability: log when the extended map would have
            # returned something different from the base map (typically the
            # property/operations/editorial/lifestyle/team branches).
            ext_choice = _EXTENDED_DOMAIN_NOTEBOOK_MAP.get(domain, [])
            if ext_choice and ext_choice != notebooks:
                logger.info(
                    "nlm_routing shadow: domain='%s' live=%s extended=%s "
                    "(set NLM_EXTENDED_ROUTING=1 to make extended the live map)",
                    domain,
                    notebooks or None,
                    ext_choice,
                )

        return notebooks

    async def _query_single(
        self, question: str, notebook_id: str, domain: str, timeout: float
    ) -> NLMResult | None:
        """Query a single notebook via enrichment service."""
        if self._enrichment is None:
            logger.debug("NLM orchestrator: no enrichment service")
            return None

        response = await self._enrichment.query(notebook_id, question, timeout=timeout)
        if response is None:
            return None

        return NLMResult(
            answer=response.get("answer", ""),
            citations=response.get("citations", []),
            domain=domain,
            notebooks_queried=[notebook_id],
        )

    async def _query_multi(
        self, question: str, notebook_ids: list[str], domain: str, timeout: float
    ) -> NLMResult | None:
        """Fan out to multiple notebooks and synthesize."""
        import asyncio

        if self._enrichment is None:
            return None

        tasks = [
            self._enrichment.query(nb_id, question, timeout=timeout)
            for nb_id in notebook_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        answers: list[str] = []
        all_citations: list[dict[str, Any]] = []
        queried: list[str] = []

        for nb_id, result in zip(notebook_ids, results):
            if isinstance(result, Exception):
                logger.warning("NLM multi-query: %s failed (%s)", nb_id, result)
                continue
            if result is None:
                continue
            answer = result.get("answer", "")
            if answer:
                answers.append(answer)
                all_citations.extend(result.get("citations", []))
                queried.append(nb_id)

        if not answers:
            return None

        synthesis = " | ".join(answers) if len(answers) > 1 else answers[0]

        return NLMResult(
            answer=answers[0] if answers else "",
            citations=all_citations,
            domain=domain,
            notebooks_queried=queried,
            synthesis=synthesis,
        )

    async def _check_cache(self, question: str, domain: str) -> NLMResult | None:
        """Check cache for previous NLM response."""
        if self._cache is None:
            return None

        try:
            notebooks = _active_domain_map().get(domain, [])
            if not notebooks:
                return None

            cached = await self._cache.get(question, notebooks[0])
            if cached is not None:
                return NLMResult(
                    answer=cached.get("answer", ""),
                    citations=cached.get("citations", []),
                    domain=domain,
                    notebooks_queried=notebooks[:1],
                    cached=True,
                )
        except Exception as exc:
            logger.debug("NLM orchestrator: cache check failed (%s)", exc)

        return None

    async def _cache_result(self, question: str, domain: str, result: NLMResult) -> None:
        """Cache NLM result."""
        if self._cache is None or not result.answer:
            return
        try:
            notebooks = result.notebooks_queried or _active_domain_map().get(domain, [])
            if notebooks:
                await self._cache.set(
                    question,
                    result.answer,
                    {"citations": result.citations, "domain": domain},
                    notebooks[0],
                )
        except Exception as exc:
            logger.debug("NLM orchestrator: cache set failed (%s)", exc)

    async def _check_rate_limit(self) -> bool:
        """Check rate limit via Redis. Returns True if within limit."""
        if self._redis is None:
            return True
        try:
            count = await self._redis.get(RATE_KEY)
            if count is not None and int(count) >= RATE_LIMIT:
                return False
        except Exception:
            pass  # fail-open
        return True

    async def _increment_rate(self) -> None:
        """Increment rate counter in Redis."""
        if self._redis is None:
            return
        try:
            count = await self._redis.incr(RATE_KEY)
            if count == 1:
                await self._redis.expire(RATE_KEY, RATE_TTL)
        except Exception:
            pass
