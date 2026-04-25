"""Naga Orchestrator — research loop coordinator (v1, sequential).

Ties together the gateway, search agents, quality pipeline, and synthesis
into a complete research workflow. Uses a sequential async pattern that is
clean enough to migrate to LangGraph StateGraph in v1.1.

State follows the **Pointer State Pattern**: the evidence map is NOT
stored inline in the state dict — only its URI. Large data lives on disk.

Usage::

    from backend.services.naga.orchestrator import NagaOrchestrator

    orch = NagaOrchestrator(deps)
    result = await orch.research("What is KITAS?", tier="auto")
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, TypedDict

from backend.core.claims.extractor import extract_claims_from_response
from backend.core.claims.models import ClaimRecord
from backend.services.naga.config import NagaConfig
from backend.services.naga.gateway import classify_query
from backend.services.naga.quality.convergence import check_convergence
from backend.services.naga.quality.crag_light import crag_evaluate
from backend.services.naga.quality.source_scorer import score_sources
from backend.services.naga.readers.gemini_reader import gemini_bulk_read
from backend.services.naga.readers.ollama_reader import (
    OllamaFallbackDegraded,
    ollama_bulk_read_hierarchical,
)
from backend.services.naga.search_agents.base import AgentResponse, SearchResult
from backend.services.naga.search_agents.brave_agent import BraveSearchAgent
from backend.services.naga.search_agents.domain_agent import IndonesiaDomainAgent
from backend.services.naga.search_agents.exa_agent import ExaSearchAgent
from backend.services.naga.state.budget_tracker import BudgetTracker
from backend.services.naga.state.url_history import URLHistory
from backend.services.naga.synthesis.report_writer import generate_report

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schema (Pointer State Pattern)
# ---------------------------------------------------------------------------


class NagaResearchState(TypedDict):
    """Full research state. evidence_map lives on disk — only URI stored."""

    # Input
    query: str
    tier: str
    domain: str
    mode: str
    channel: str
    session_id: str

    # Search state (lightweight — Pointer State)
    sub_questions: list[str]
    search_results: list[dict]  # [{url, title, source_type, relevance_score}]
    url_history: list[str]
    search_calls_used: int
    iteration: int

    # Quality state
    evidence_map_uri: str  # pointer to file, NOT inline data
    claims_extracted: int
    avg_confidence: float
    convergence_decision: str  # CONVERGED / ITERATE / TIMEOUT

    # Output
    report_markdown: str
    action_items: list[dict]
    status: str  # running / completed / failed
    error: str


# ---------------------------------------------------------------------------
# Query decomposition heuristic (v1)
# ---------------------------------------------------------------------------

_VS_PATTERN = re.compile(r"\bvs\.?\b|\bversus\b", re.IGNORECASE)
_CONFRONTO_PATTERN = re.compile(
    r"\bconfronto\b\s+(.+?)\s+(?:e|and|&)\s+(.+)",
    re.IGNORECASE,
)


def _decompose_query(query: str, tier: str) -> list[str]:
    """Decompose *query* into sub-questions using a simple heuristic.

    - Flash: no decomposition (returns ``[query]``).
    - If "vs" / "confronto" in query: split into 3 comparative sub-questions.
    - Otherwise: ``[query, "What are the latest developments regarding {query}?"]``.
    """
    if tier == "flash":
        return [query]

    # Italian comparison: "confronto X e Y"
    confronto_match = _CONFRONTO_PATTERN.search(query)
    if confronto_match:
        side_a = confronto_match.group(1).strip()
        side_b = confronto_match.group(2).strip()
        if side_a and side_b:
            return [
                f"What is {side_a}?",
                f"What is {side_b}?",
                f"What are the key differences between {side_a} and {side_b}?",
            ]

    # English comparison: "X vs Y"
    match = _VS_PATTERN.search(query)
    if match:
        parts = _VS_PATTERN.split(query, maxsplit=1)
        side_a = parts[0].strip() if len(parts) > 0 else query
        side_b = parts[1].strip() if len(parts) > 1 else ""
        if side_a and side_b:
            return [
                f"What is {side_a}?",
                f"What is {side_b}?",
                f"What are the key differences between {side_a} and {side_b}?",
            ]

    return [
        query,
        f"What are the latest developments regarding: {query}?",
    ]


# ---------------------------------------------------------------------------
# NagaOrchestrator
# ---------------------------------------------------------------------------


class NagaOrchestrator:
    """Orchestrates the full Naga research loop.

    Parameters
    ----------
    deps:
        Dependency container providing callables:
        ``exa_search``, ``brave_search``, ``fetch``, ``ask_legal``,
        ``search_intel``, ``notebook_query``, ``recall_similar``,
        ``gemini_generate``.
    config:
        Optional NagaConfig override.  When ``None`` a default is created.
    """

    def __init__(self, deps: Any, config: NagaConfig | None = None) -> None:
        self._deps = deps
        self._config = config or NagaConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def research(
        self,
        query: str,
        tier: str = "auto",
        domain: str = "auto",
        mode: str = "oneshot",
        channel: str | None = None,
        trusted_mode: bool = False,
    ) -> dict:
        """Execute the full research loop. Returns final state dict."""
        session_id = uuid.uuid4().hex[:12]
        start_ms = _monotonic_ms()

        logger.info(
            "Naga research started: session=%s tier=%s domain=%s query=%.80s",
            session_id,
            tier,
            domain,
            query,
        )

        # ---- 1. Gateway classification (if tier/domain="auto") --------
        if tier == "auto" or domain == "auto":
            gw = classify_query(query, channel=channel)
            if tier == "auto":
                tier = gw.tier
            if domain == "auto":
                domain = gw.domain
            mode = gw.mode
            logger.info(
                "Gateway classified: tier=%s domain=%s mode=%s",
                tier,
                domain,
                mode,
            )

        # ---- 2. Decompose query into sub_questions --------------------
        sub_questions = _decompose_query(query, tier)
        logger.info("Decomposed into %d sub-questions", len(sub_questions))

        # ---- 3. Create BudgetTracker from tier config -----------------
        tier_budget = self._config.tier_budgets.get(tier)
        if tier_budget is None:
            tier_budget = self._config.tier_budgets["flash"]
            logger.warning("Unknown tier %r, falling back to flash", tier)

        budget = BudgetTracker(
            max_search_calls=tier_budget.max_searches,
            ttl_seconds=tier_budget.default_ttl_seconds,
        )

        # ---- Build agents once ----------------------------------------
        exa_agent = ExaSearchAgent(mcp_call=self._deps.exa_search)
        brave_agent = BraveSearchAgent(
            brave_call=self._deps.brave_search,
            fetch_call=self._deps.fetch,
        )
        domain_agent = IndonesiaDomainAgent(
            ask_legal=self._deps.ask_legal,
            search_intel=self._deps.search_intel,
            notebook_query=self._deps.notebook_query,
            recall_similar=self._deps.recall_similar,
        )

        # ---- Mutable loop state ---------------------------------------
        url_history = URLHistory()
        all_results: list[SearchResult] = []
        all_claims: list[ClaimRecord] = []
        evidence_map: dict[str, Any] = {}
        evidence_map_uri: str = ""
        convergence_decision: str = "ITERATE"
        iteration: int = 0
        max_iterations = tier_budget.max_iterations
        fallback_reader: str = ""

        # ---- 4. Research loop -----------------------------------------
        while iteration < max_iterations:
            iteration += 1
            logger.info(
                "Iteration %d/%d — budget: %s",
                iteration,
                max_iterations,
                budget.summary(),
            )

            # 4a. Dispatch search agents (based on domain)
            agent_responses: list[AgentResponse] = []

            for sq in sub_questions:
                if not budget.can_search:
                    logger.info("Budget exhausted, skipping remaining sub-questions")
                    break

                responses = await self._dispatch_agents(
                    query, sq, domain, exa_agent, brave_agent, domain_agent
                )
                agent_responses.extend(responses)

                # Track search calls in budget
                for resp in responses:
                    budget.record_search(resp.search_calls_used)

            # 4b. Merge responses, dedup URLs
            merged = AgentResponse.merge(agent_responses)
            new_urls = url_history.add_many(
                [r.url for r in merged.results if r.url]
            )
            new_results = [r for r in merged.results if r.url in new_urls]
            all_results.extend(new_results)

            logger.info(
                "Merged: %d results (%d new URLs)",
                len(merged.results),
                len(new_urls),
            )

            # 4c. CRAG-light evaluation per sub-question
            for sq in sub_questions:
                sq_content = [r.content for r in new_results if r.content]
                crag = crag_evaluate(sq, sq_content)
                logger.debug("CRAG %s for sub-q '%.60s': %s", crag.action, sq, crag.reason)

            # 4d. If tier != flash: score sources, bulk read with Gemini, extract claims
            new_claims_this_iteration = 0

            if tier != "flash" and new_results:
                # Score sources
                scored = score_sources(new_results, config=self._config)

                # Gemini bulk read
                if scored and tier_budget.max_gemini_sources > 0:
                    sources_for_gemini = scored[:tier_budget.max_gemini_sources]
                    sources_content = [
                        {
                            "id": f"s{i}",
                            "url": s.url,
                            "content": s.content,
                        }
                        for i, s in enumerate(sources_for_gemini)
                    ]

                    try:
                        evidence_map, evidence_map_uri = await gemini_bulk_read(
                            sub_questions=sub_questions,
                            sources_content=sources_content,
                            generate_fn=self._deps.gemini_generate,
                            session_id=session_id,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Gemini bulk read failed (%s), falling back to deepseek-r1:32b",
                            type(exc).__name__,
                        )
                        try:
                            evidence_map = await ollama_bulk_read_hierarchical(
                                sources=sources_content,
                                sub_questions=sub_questions,
                            )
                            evidence_map_uri = ""
                            fallback_reader = "ollama_deepseek_r1_32b"
                        except OllamaFallbackDegraded as fb_exc:
                            logger.error(
                                "Both Gemini and Ollama fallback failed: %s", fb_exc
                            )
                            raise

                # Extract claims from new results
                combined_content = "\n\n".join(r.content for r in new_results if r.content)
                if combined_content:
                    source_ids = [f"s{i}" for i in range(len(new_results))]
                    new_extracted = extract_claims_from_response(
                        response_text=combined_content,
                        source_ids=source_ids,
                        query_cluster="NAGA",
                    )
                    all_claims.extend(new_extracted)
                    new_claims_this_iteration = len(new_extracted)
            else:
                # Flash tier: extract claims from content for the report
                combined_content = "\n\n".join(r.content for r in new_results if r.content)
                if combined_content:
                    source_ids = [f"s{i}" for i in range(len(new_results))]
                    new_extracted = extract_claims_from_response(
                        response_text=combined_content,
                        source_ids=source_ids,
                        query_cluster="NAGA",
                    )
                    all_claims.extend(new_extracted)
                    new_claims_this_iteration = len(new_extracted)

            # 4e. Check convergence
            claims_per_q: dict[str, int] = {}
            for sq in sub_questions:
                # Count claims whose text overlaps with the sub-question
                claims_per_q[sq] = sum(
                    1 for c in all_claims
                    if any(word.lower() in c.claim_text.lower()
                           for word in sq.split() if len(word) > 3)
                )

            conv = check_convergence(
                sub_questions=sub_questions,
                claims_per_question=claims_per_q,
                new_claims_this_iteration=new_claims_this_iteration,
                total_claims=len(all_claims),
                iteration=iteration,
                budget_can_search=budget.can_search,
                coverage_threshold=self._config.convergence_coverage_threshold,
                novelty_threshold=self._config.convergence_novelty_threshold,
            )
            convergence_decision = conv.decision

            logger.info(
                "Convergence: %s — coverage=%.2f novelty=%.2f gaps=%d",
                conv.decision,
                conv.coverage,
                conv.novelty,
                len(conv.gap_questions),
            )

            if conv.decision in ("CONVERGED", "TIMEOUT"):
                break

        # ---- 5. Generate report ---------------------------------------
        duration_ms = _monotonic_ms() - start_ms
        gaps = list(conv.gap_questions) if conv.gap_questions else []

        report = generate_report(
            query=query,
            tier=tier,
            claims=all_claims,
            evidence_map=evidence_map,
            sources_count=len(all_results),
            duration_ms=duration_ms,
            gaps=gaps,
        )

        # ---- 6. Build and return final state dict ---------------------
        avg_conf = (
            sum(c.confidence_score for c in all_claims) / len(all_claims)
            if all_claims
            else 0.0
        )

        search_results_summary = [
            {
                "url": r.url,
                "title": r.title,
                "source_type": r.source_type,
                "relevance_score": r.relevance_score,
            }
            for r in all_results
        ]

        state: dict[str, Any] = {
            # Input
            "query": query,
            "tier": tier,
            "domain": domain,
            "mode": mode,
            "channel": channel or "",
            "session_id": session_id,
            # Search state
            "sub_questions": sub_questions,
            "search_results": search_results_summary,
            "url_history": list(url_history._seen),
            "search_calls_used": budget._search_calls_used,
            "iteration": iteration,
            # Quality state
            "evidence_map_uri": evidence_map_uri,
            "claims_extracted": len(all_claims),
            "avg_confidence": round(avg_conf, 4),
            "convergence_decision": convergence_decision,
            # Output
            "report_markdown": report,
            "action_items": [],
            "status": "completed",
            "error": "",
            # Internal (not serialized to API, used by persist)
            "_claims": all_claims,
        }
        if fallback_reader:
            state["fallback_reader"] = fallback_reader

        # ---- 7. Persist to PostgreSQL (non-blocking) ------------------
        db_pool = getattr(self._deps, "db_pool", None)
        if db_pool is not None:
            try:
                from backend.services.naga.persist import save_session

                saved_id = await save_session(db_pool, state)
                if saved_id:
                    state["session_id"] = saved_id
            except Exception as exc:
                logger.warning("Naga DB persist failed (non-fatal): %s", exc)

        logger.info(
            "Naga research completed: session=%s tier=%s iterations=%d claims=%d duration=%dms",
            session_id,
            tier,
            iteration,
            len(all_claims),
            duration_ms,
        )

        return state

    # ------------------------------------------------------------------
    # Agent dispatch
    # ------------------------------------------------------------------

    async def _dispatch_agents(
        self,
        query: str,
        sub_question: str,
        domain: str,
        exa_agent: ExaSearchAgent,
        brave_agent: BraveSearchAgent,
        domain_agent: IndonesiaDomainAgent,
    ) -> list[AgentResponse]:
        """Dispatch search agents based on domain. Returns list of responses."""
        responses: list[AgentResponse] = []

        if domain in ("general", "hybrid"):
            responses.append(
                await _safe_search(exa_agent, query, sub_question)
            )
            responses.append(
                await _safe_search(brave_agent, query, sub_question)
            )

        if domain in ("indonesia", "hybrid"):
            responses.append(
                await _safe_search(domain_agent, query, sub_question)
            )

        # Fallback: if no domain matched, use Exa + Brave as default
        if not responses:
            logger.warning("No agents matched domain=%r, falling back to general", domain)
            responses.append(
                await _safe_search(exa_agent, query, sub_question)
            )
            responses.append(
                await _safe_search(brave_agent, query, sub_question)
            )

        return responses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _safe_search(
    agent: Any,
    query: str,
    sub_question: str,
) -> AgentResponse:
    """Call agent.search() wrapped in try/except for resilience."""
    try:
        return await agent.search(query=query, sub_question=sub_question)
    except Exception as exc:
        logger.error(
            "Agent %s failed: %s",
            getattr(agent, "name", "unknown"),
            exc,
        )
        return AgentResponse(
            agent_name=getattr(agent, "name", "unknown"),
            results=[],
            search_calls_used=1,
            error=str(exc),
        )


def _monotonic_ms() -> int:
    """Return monotonic time in milliseconds."""
    return int(time.monotonic() * 1000)
