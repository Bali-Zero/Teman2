"""Indonesia Domain Agent — internal RAG + NLM + gov sources.

This is the key differentiator of Naga vs commercial research tools.
The domain agent taps into Bali Zero's proprietary knowledge stack:

1. **ask_legal** — RAG over the legal/visa/tax vector store.
2. **search_intel** — intelligence articles from the intel pipeline.
3. **notebook_query** — Google NLM domain notebooks (NB-2 .. NB-5).
4. **exa_call** — neural search restricted to Indonesian gov domains.
5. **recall_similar** — episodic memory of past research episodes.

All five sources are called sequentially.  Each is individually
wrapped in ``try/except`` so a single failure never blocks the rest.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from backend.services.naga.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOV_DOMAINS: list[str] = [
    "imigrasi.go.id",
    "pajak.go.id",
    "kemenkumham.go.id",
    "oss.go.id",
    "bkpm.go.id",
    "peraturan.bpk.go.id",
    "jdih.kemenkumham.go.id",
]

# NLM Notebook IDs by domain
_NB_IMMIGRATION = "NB-2"
_NB_COMPANY = "NB-3"
_NB_TAX = "NB-4"
_NB_PROPERTY = "NB-5"
_NB_DEFAULT = _NB_IMMIGRATION

# Keyword patterns for notebook selection (compiled once at module load)
_IMMIGRATION_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:visa|kitas|kitap|imigrasi|immigration|izin tinggal"
    r"|golden visa|investor visa|retirement visa|sponsor"
    r"|stay permit|residence permit|telex)\b",
    re.IGNORECASE,
)

_COMPANY_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:pt pma|perseroan|company|perusahaan|cv|yayasan"
    r"|kbli|nib|oss|akta|notaris|ahu|incorporation"
    r"|business setup|izin usaha)\b",
    re.IGNORECASE,
)

_TAX_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:pajak|tax|npwp|pph|ppn|fiscal|withholding"
    r"|tax return|spt|efin|pkp)\b",
    re.IGNORECASE,
)

_PROPERTY_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:property|properti|hak pakai|hgb|land|tanah"
    r"|real estate|bangunan|sertifikat|imb|pbg"
    r"|ownership|lahan)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Notebook selector
# ---------------------------------------------------------------------------


def _select_notebooks(combined_query: str) -> list[str]:
    """Return up to 2 NLM notebook IDs based on keyword hits.

    The first match always wins priority; a second domain match is
    appended.  If nothing matches, ``NB-2`` (immigration) is returned
    as the default.
    """
    candidates: list[str] = []

    if _IMMIGRATION_PATTERN.search(combined_query):
        candidates.append(_NB_IMMIGRATION)
    if _COMPANY_PATTERN.search(combined_query):
        candidates.append(_NB_COMPANY)
    if _TAX_PATTERN.search(combined_query):
        candidates.append(_NB_TAX)
    if _PROPERTY_PATTERN.search(combined_query):
        candidates.append(_NB_PROPERTY)

    if not candidates:
        return [_NB_DEFAULT]

    return candidates[:2]


# ---------------------------------------------------------------------------
# IndonesiaDomainAgent
# ---------------------------------------------------------------------------


class IndonesiaDomainAgent(BaseSearchAgent):
    """Search agent that combines internal RAG, NLM, and gov sources.

    Every callable is optional except *ask_legal* and *search_intel*.
    When a callable is ``None`` it is silently skipped (no error).
    """

    name: str = "domain_indonesia"

    def __init__(
        self,
        ask_legal: Callable[..., Any],
        search_intel: Callable[..., Any],
        notebook_query: Callable[..., Any] | None = None,
        recall_similar: Callable[..., Any] | None = None,
        exa_call: Callable[..., Any] | None = None,
    ) -> None:
        self._ask_legal = ask_legal
        self._search_intel = search_intel
        self._notebook_query = notebook_query
        self._recall_similar = recall_similar
        self._exa_call = exa_call

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
    ) -> AgentResponse:
        """Run all domain sources and merge into an :class:`AgentResponse`."""
        combined = f"{query} {sub_question}".strip()
        results: list[SearchResult] = []
        search_calls: int = 0

        # 1. ask_legal
        search_calls += 1
        results.extend(await self._call_ask_legal(combined))

        # 2. search_intel
        search_calls += 1
        results.extend(await self._call_search_intel(combined))

        # 3. notebook_query (up to 2 notebooks)
        if self._notebook_query is not None:
            notebooks = _select_notebooks(combined)
            for nb_id in notebooks:
                search_calls += 1
                results.extend(await self._call_notebook_query(nb_id, combined))

        # 4. exa_call (gov domains)
        if self._exa_call is not None:
            search_calls += 1
            results.extend(await self._call_exa(combined))

        # 5. recall_similar (episodic memory)
        if self._recall_similar is not None:
            search_calls += 1
            results.extend(await self._call_recall_similar(combined))

        return AgentResponse(
            agent_name=self.name,
            results=results[:max_results],
            search_calls_used=search_calls,
        )

    # ------------------------------------------------------------------
    # Individual tool callers (each wrapped in try/except)
    # ------------------------------------------------------------------

    async def _call_ask_legal(self, combined: str) -> list[SearchResult]:
        try:
            resp = await self._ask_legal(query=combined)
            answer = resp.get("answer", "") if isinstance(resp, dict) else str(resp)
            return [
                SearchResult(
                    url="internal://ask_legal",
                    title="Legal RAG",
                    content=answer,
                    relevance_score=0.85,
                    source_type="internal",
                )
            ]
        except Exception:
            logger.warning("ask_legal failed for query: %s", combined[:80], exc_info=True)
            return []

    async def _call_search_intel(self, combined: str) -> list[SearchResult]:
        try:
            items = await self._search_intel(query=combined)
            if not isinstance(items, list):
                items = []
            return [
                SearchResult(
                    url=item.get("url", "internal://search_intel"),
                    title=item.get("title", "Intel"),
                    content=item.get("content", ""),
                    relevance_score=0.75,
                    source_type="internal",
                )
                for item in items
                if isinstance(item, dict)
            ]
        except Exception:
            logger.warning("search_intel failed for query: %s", combined[:80], exc_info=True)
            return []

    async def _call_notebook_query(
        self, notebook_id: str, combined: str
    ) -> list[SearchResult]:
        try:
            resp = await self._notebook_query(notebook_id=notebook_id, query=combined)
            text = resp.get("text", "") if isinstance(resp, dict) else str(resp)
            if not text:
                return []
            return [
                SearchResult(
                    url=f"internal://nlm/{notebook_id}",
                    title=f"NLM {notebook_id}",
                    content=text,
                    relevance_score=0.80,
                    source_type="internal",
                )
            ]
        except Exception:
            logger.warning(
                "notebook_query failed for %s: %s",
                notebook_id,
                combined[:80],
                exc_info=True,
            )
            return []

    async def _call_exa(self, combined: str) -> list[SearchResult]:
        try:
            resp = await self._exa_call(
                query=combined,
                numResults=5,
                type="neural",
                includeDomains=GOV_DOMAINS,
            )
            raw_results = resp.get("results", []) if isinstance(resp, dict) else []
            return [
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("text", ""),
                    relevance_score=0.70,
                    source_type="gov",
                )
                for item in raw_results
                if isinstance(item, dict) and item.get("url")
            ]
        except Exception:
            logger.warning("exa_call failed for query: %s", combined[:80], exc_info=True)
            return []

    async def _call_recall_similar(self, combined: str) -> list[SearchResult]:
        try:
            episodes = await self._recall_similar(query=combined)
            if not isinstance(episodes, list):
                episodes = []
            return [
                SearchResult(
                    url="internal://recall_similar",
                    title="Past Episode",
                    content=ep.get("content", "") if isinstance(ep, dict) else str(ep),
                    relevance_score=ep.get("score", 0.60) if isinstance(ep, dict) else 0.60,
                    source_type="internal",
                )
                for ep in episodes
                if ep
            ]
        except Exception:
            logger.warning("recall_similar failed for query: %s", combined[:80], exc_info=True)
            return []
