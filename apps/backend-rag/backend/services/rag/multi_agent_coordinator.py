"""
Multi-Agent Coordinator (Phase 6)

Coordinates specialized sub-agents (Legal, Financial, Timeline) using LangGraph
to answer complex queries requiring multi-domain expertise.

Architecture:
    User Query → Orchestrator detects multi-agent need →
    MultiAgentCoordinator runs Legal + Financial in parallel,
    then Timeline (depends on legal output), then Synthesizer.

Example:
    >>> coordinator = MultiAgentCoordinator(db_pool=pool)
    >>> result = await coordinator.process("How much will PT PMA cost and when can I start?", {})
    >>> print(result["final_answer"])

Author: Nuzantara Team
Date: 2026-02-09
"""

import logging
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.services.pricing.pricing_service import PricingService, get_pricing_service
from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

logger = logging.getLogger(__name__)

# Lazy imports for LLM providers (matching kg_langgraph_orchestrator.py pattern)
try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None  # type: ignore[assignment,misc]

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]


# ============================================================================
# State Definition
# ============================================================================


def _merge_agent_outputs(
    existing: list[dict[str, Any]], new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reducer: append new agent outputs to existing list."""
    return existing + new


class MultiAgentState(TypedDict):
    """
    Shared state for multi-agent coordination workflow.

    Attributes:
        query: Original user query
        user_context: User metadata (citizenship, intent, etc.)
        legal_analysis: Output from LegalAgent
        financial_breakdown: Output from FinancialAgent
        timeline_estimate: Output from TimelineAgent
        agent_outputs: Accumulated outputs from all agents (append-only)
        final_answer: Synthesized answer combining all agents
        errors: List of non-fatal errors encountered during processing
    """

    query: str
    user_context: dict[str, Any]
    legal_analysis: str
    financial_breakdown: str
    timeline_estimate: str
    agent_outputs: Annotated[list[dict[str, Any]], _merge_agent_outputs]
    final_answer: str
    errors: list[str]


# ============================================================================
# LLM Configuration (reuses pattern from kg_langgraph_orchestrator.py)
# ============================================================================


def _get_multi_agent_llm() -> Any:
    """
    Get LLM instance for multi-agent reasoning.

    Uses Claude Sonnet 4.5 for complex multi-domain synthesis,
    falls back to OpenAI GPT-4 if Anthropic unavailable.

    Returns:
        LangChain LLM instance

    Raises:
        ValueError: If no LLM provider is available
    """
    import os

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if anthropic_key and ChatAnthropic is not None:
        logger.info("🤖 [MultiAgent] Using Claude Sonnet 4.5 for reasoning")
        return ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.2,
            api_key=anthropic_key,
        )
    if openai_key and ChatOpenAI is not None:
        logger.info("🤖 [MultiAgent] Using OpenAI GPT-4 for reasoning (Anthropic unavailable)")
        return ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.2,
            api_key=openai_key,
        )
    raise ValueError(
        "No LLM available for multi-agent reasoning. "
        f"ANTHROPIC_API_KEY={'set' if anthropic_key else 'missing'} "
        f"(lib={'ok' if ChatAnthropic else 'missing'}), "
        f"OPENAI_API_KEY={'set' if openai_key else 'missing'} "
        f"(lib={'ok' if ChatOpenAI else 'missing'})",
    )


# ============================================================================
# Specialized Agents
# ============================================================================


class LegalAgent:
    """Analyzes legal requirements (documents, compliance, regulations)."""

    def __init__(self, llm: Any, kg_retrieval: KGEnhancedRetrieval | None) -> None:
        self.llm = llm
        self.kg_retrieval = kg_retrieval

    async def analyze(self, state: MultiAgentState) -> dict[str, Any]:
        """
        Extract legal requirements from query using KG + LLM.

        Returns state update with:
            - legal_analysis: Required documents, legal entities, compliance steps
            - agent_outputs: Appended legal agent output
        """
        query = state["query"]
        start_time = time.time()

        try:
            # Use KG to find legal entities
            legal_entities: list[dict[str, Any]] = []
            if self.kg_retrieval:
                mentions = self.kg_retrieval.extract_entities_from_query(query)
                if mentions:
                    kg_entities = await self.kg_retrieval.find_kg_entities(
                        mentions, limit_per_mention=5,
                    )
                    legal_entities = [
                        e
                        for e in kg_entities
                        if e.get("entity_type")
                        in (
                            "dokumen",
                            "undang_undang",
                            "pasal",
                            "pt_pma",
                            "pt_pmdn",
                            "pt_perorangan",
                            "badan_usaha",
                            "npwp",
                            "oss",
                            "nib",
                            "izin_usaha",
                            "kitas",
                            "kitap",
                            "vitas",
                            "rptka",
                            "imta",
                        )
                    ]

            # Build LLM prompt with KG evidence
            entity_summary = ""
            if legal_entities:
                entity_names = [
                    e.get("name", e.get("entity_id", "unknown")) for e in legal_entities[:10]
                ]
                entity_summary = (
                    "\n\nRelevant legal entities from Knowledge Graph:\n- "
                    + "\n- ".join(entity_names)
                )

            prompt = (
                f"You are a legal requirements analyst for Indonesian business and immigration.\n\n"
                f'Query: "{query}"\n'
                f"{entity_summary}\n\n"
                f"List the required documents and compliance steps in order.\n"
                f"Focus on: required documents (NPWP, Akta, passport, etc.), "
                f"legal entities involved (PT PMA, Perorangan, etc.), "
                f"and compliance requirements (BKPM, notary, OSS, etc.).\n"
                f"Format as bullet points. Be specific to Indonesian regulations."
            )

            response = await self.llm.ainvoke(prompt)
            analysis = response.content if hasattr(response, "content") else str(response)
            duration = time.time() - start_time

            logger.info(
                f"⚖️ [LegalAgent] Analysis complete in {duration:.2f}s "
                f"({len(legal_entities)} KG entities used)",
            )

            return {
                "legal_analysis": analysis,
                "agent_outputs": [
                    {
                        "agent": "legal",
                        "output": analysis,
                        "entities_used": len(legal_entities),
                        "duration_s": round(duration, 2),
                    },
                ],
            }

        except Exception as e:
            logger.error(f"❌ [LegalAgent] Failed: {e}", exc_info=True)
            return {
                "legal_analysis": "Legal analysis unavailable due to processing error.",
                "agent_outputs": [
                    {
                        "agent": "legal",
                        "output": "",
                        "error": str(e),
                    },
                ],
                "errors": [f"LegalAgent: {e}"],
            }


class FinancialAgent:
    """Calculates total costs (government fees + Bali Zero services)."""

    def __init__(self, llm: Any, pricing_service: PricingService) -> None:
        self.llm = llm
        self.pricing_service = pricing_service

    async def analyze(self, state: MultiAgentState) -> dict[str, Any]:
        """
        Calculate cost breakdown using PricingService + LLM.

        Returns state update with:
            - financial_breakdown: Itemized cost breakdown
            - agent_outputs: Appended financial agent output
        """
        query = state["query"]
        start_time = time.time()

        try:
            # Determine service type from query
            service_type = self._extract_service_type(query)

            # Get official Bali Zero pricing (NEVER generate prices)
            self.pricing_service.get_pricing(service_type)
            pricing_context = self.pricing_service.format_for_llm_context(service_type)

            prompt = (
                f"You are a financial analyst for Indonesian business services.\n\n"
                f'Query: "{query}"\n\n'
                f"Official Bali Zero pricing data:\n{pricing_context}\n\n"
                f"Based on the query and official pricing above:\n"
                f"1. Identify the relevant Bali Zero service fee\n"
                f"2. List known government fees (PNBP) if applicable\n"
                f"3. Mention notary/third-party fees if relevant\n"
                f"4. Provide a total estimate range\n\n"
                f"IMPORTANT: Use ONLY the official prices above. "
                f"Do NOT generate or estimate Bali Zero prices. "
                f"If a specific price is not listed, say 'Contact Bali Zero for quote'."
            )

            response = await self.llm.ainvoke(prompt)
            breakdown = response.content if hasattr(response, "content") else str(response)
            duration = time.time() - start_time

            logger.info(
                f"💰 [FinancialAgent] Breakdown complete in {duration:.2f}s "
                f"(service_type={service_type})",
            )

            return {
                "financial_breakdown": breakdown,
                "agent_outputs": [
                    {
                        "agent": "financial",
                        "output": breakdown,
                        "service_type": service_type,
                        "pricing_loaded": self.pricing_service.loaded,
                        "duration_s": round(duration, 2),
                    },
                ],
            }

        except Exception as e:
            logger.error(f"❌ [FinancialAgent] Failed: {e}", exc_info=True)
            return {
                "financial_breakdown": "Financial breakdown unavailable due to processing error.",
                "agent_outputs": [
                    {
                        "agent": "financial",
                        "output": "",
                        "error": str(e),
                    },
                ],
                "errors": [f"FinancialAgent: {e}"],
            }

    @staticmethod
    def _extract_service_type(query: str) -> str:
        """Map query keywords to PricingService service type."""
        q = query.lower()

        if any(kw in q for kw in ("pt pma", "pt pmdn", "company", "perusahaan", "badan usaha")):
            return "business_setup"
        if any(kw in q for kw in ("kitas", "kitap", "work permit", "izin kerja", "stay permit")):
            return "kitas"
        if any(kw in q for kw in ("visa", "vitas", "e-visa")):
            return "visa"
        if any(kw in q for kw in ("tax", "pajak", "npwp", "spt")):
            return "tax_consulting"
        if any(kw in q for kw in ("legal", "hukum", "notaris")):
            return "legal"
        return "all"


class TimelineAgent:
    """Estimates timelines and deadlines based on legal steps and KG data."""

    def __init__(self, llm: Any, kg_retrieval: KGEnhancedRetrieval | None) -> None:
        self.llm = llm
        self.kg_retrieval = kg_retrieval

    async def analyze(self, state: MultiAgentState) -> dict[str, Any]:
        """
        Estimate timeline with phase breakdown.

        Uses legal_analysis from LegalAgent (if available) to create
        a realistic phase-by-phase timeline.

        Returns state update with:
            - timeline_estimate: Phase-by-phase timeline
            - agent_outputs: Appended timeline agent output
        """
        query = state["query"]
        legal_steps = state.get("legal_analysis", "")
        start_time = time.time()

        try:
            # Use KG to find duration-related entities
            duration_entities: list[dict[str, Any]] = []
            if self.kg_retrieval:
                mentions = self.kg_retrieval.extract_entities_from_query(query)
                # Also look for time-related mentions
                time_mentions = [
                    m
                    for m in mentions
                    if m[1] in ("jangka_waktu", "pendaftaran", "permohonan", "perpanjangan")
                ]
                if time_mentions:
                    duration_entities = await self.kg_retrieval.find_kg_entities(
                        time_mentions, limit_per_mention=3,
                    )

            # Build prompt with legal context
            legal_context = ""
            if legal_steps and legal_steps != "Legal analysis unavailable due to processing error.":
                legal_context = f"\n\nLegal steps already identified:\n{legal_steps}"

            duration_context = ""
            if duration_entities:
                dur_names = [e.get("name", "unknown") for e in duration_entities[:5]]
                duration_context = "\n\nKnown duration entities from KG:\n- " + "\n- ".join(
                    dur_names,
                )

            prompt = (
                f"You are a timeline estimation specialist for Indonesian business processes.\n\n"
                f'Query: "{query}"\n'
                f"{legal_context}"
                f"{duration_context}\n\n"
                f"Create a phase-by-phase timeline:\n"
                f"1. Document preparation: X days\n"
                f"2. Submission to authority: Y days\n"
                f"3. Approval/processing: Z days\n"
                f"4. Post-approval steps: W days\n\n"
                f"Include buffer for common delays. Give total estimate.\n"
                f"Be realistic about Indonesian government processing times."
            )

            response = await self.llm.ainvoke(prompt)
            estimate = response.content if hasattr(response, "content") else str(response)
            duration = time.time() - start_time

            logger.info(
                f"⏱️ [TimelineAgent] Estimate complete in {duration:.2f}s "
                f"({len(duration_entities)} duration entities used)",
            )

            return {
                "timeline_estimate": estimate,
                "agent_outputs": [
                    {
                        "agent": "timeline",
                        "output": estimate,
                        "duration_entities_used": len(duration_entities),
                        "had_legal_context": bool(legal_context),
                        "duration_s": round(duration, 2),
                    },
                ],
            }

        except Exception as e:
            logger.error(f"❌ [TimelineAgent] Failed: {e}", exc_info=True)
            return {
                "timeline_estimate": "Timeline estimate unavailable due to processing error.",
                "agent_outputs": [
                    {
                        "agent": "timeline",
                        "output": "",
                        "error": str(e),
                    },
                ],
                "errors": [f"TimelineAgent: {e}"],
            }


# ============================================================================
# Multi-Agent Coordinator (LangGraph)
# ============================================================================


class MultiAgentCoordinator:
    """
    Coordinates Legal, Financial, and Timeline agents using LangGraph StateGraph.

    Graph topology:
        legal ──→ timeline ──→ synthesize ──→ END
        financial ─────────↗

    Legal and Financial run first (could be parallelized in future LangGraph versions),
    then Timeline uses legal output, then Synthesizer combines all.
    """

    def __init__(
        self,
        kg_retrieval: KGEnhancedRetrieval | None = None,
        pricing_service: PricingService | None = None,
        db_pool: Any = None,
    ) -> None:
        """
        Initialize MultiAgentCoordinator.

        Args:
            kg_retrieval: Optional KGEnhancedRetrieval for graph queries
            pricing_service: Optional PricingService (uses singleton if None)
            db_pool: Optional database pool (used to create KGEnhancedRetrieval if needed)
        """
        self._kg_retrieval = kg_retrieval
        self._pricing_service = pricing_service or get_pricing_service()
        self._db_pool = db_pool
        self._llm: Any = None
        self._graph: Any = None

        # Agents (lazy-initialized)
        self._legal_agent: LegalAgent | None = None
        self._financial_agent: FinancialAgent | None = None
        self._timeline_agent: TimelineAgent | None = None

    def _ensure_initialized(self) -> None:
        """Lazy-initialize LLM and agents on first use."""
        if self._llm is not None:
            return

        self._llm = _get_multi_agent_llm()

        # Create KG retrieval from db_pool if not provided
        kg = self._kg_retrieval
        if kg is None and self._db_pool is not None:
            kg = KGEnhancedRetrieval(self._db_pool)

        self._legal_agent = LegalAgent(self._llm, kg)
        self._financial_agent = FinancialAgent(self._llm, self._pricing_service)
        self._timeline_agent = TimelineAgent(self._llm, kg)

        # Build LangGraph
        self._graph = self._build_graph()
        logger.info("✅ [MultiAgentCoordinator] Initialized with LangGraph workflow")

    def _build_graph(self) -> Any:
        """
        Build LangGraph StateGraph for multi-agent coordination.

        Topology:
            START → legal → financial → timeline → synthesize → END

        Legal runs first (provides context for timeline),
        Financial runs second, Timeline third (uses legal output),
        then Synthesizer combines everything.
        """
        workflow = StateGraph(MultiAgentState)

        # Add nodes
        workflow.add_node("legal", self._legal_agent.analyze)
        workflow.add_node("financial", self._financial_agent.analyze)
        workflow.add_node("timeline", self._timeline_agent.analyze)
        workflow.add_node("synthesize", self._synthesize_outputs)

        # Define edges: legal → financial → timeline → synthesize → END
        workflow.set_entry_point("legal")
        workflow.add_edge("legal", "financial")
        workflow.add_edge("financial", "timeline")
        workflow.add_edge("timeline", "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    async def _synthesize_outputs(self, state: MultiAgentState) -> dict[str, Any]:
        """
        Combine agent outputs into a coherent final answer.

        Uses LLM to synthesize legal, financial, and timeline analyses
        into a structured, user-friendly response.
        """
        start_time = time.time()

        try:
            prompt = (
                f"You are a senior business consultant for Bali Zero, "
                f"helping clients with Indonesian business and immigration.\n\n"
                f'User query: "{state["query"]}"\n\n'
                f"**Legal Analysis:**\n{state.get('legal_analysis', 'Not available')}\n\n"
                f"**Financial Breakdown:**\n{state.get('financial_breakdown', 'Not available')}\n\n"
                f"**Timeline Estimate:**\n{state.get('timeline_estimate', 'Not available')}\n\n"
                f"Synthesize these into a coherent, actionable answer for the client.\n"
                f"Format:\n"
                f"**Legal Requirements:** ...\n"
                f"**Cost Breakdown:** ...\n"
                f"**Timeline:** ...\n"
                f"**Next Steps:** ...\n\n"
                f"Be professional, clear, and specific. "
                f"If any section had errors, acknowledge the gap and suggest contacting Bali Zero."
            )

            response = await self._llm.ainvoke(prompt)
            answer = response.content if hasattr(response, "content") else str(response)
            duration = time.time() - start_time

            logger.info(f"🔗 [Synthesizer] Combined answer in {duration:.2f}s")

            return {
                "final_answer": answer,
                "agent_outputs": [
                    {
                        "agent": "synthesizer",
                        "duration_s": round(duration, 2),
                    },
                ],
            }

        except Exception as e:
            logger.error(f"❌ [Synthesizer] Failed: {e}", exc_info=True)
            # Fallback: concatenate raw outputs
            fallback = (
                f"**Legal Requirements:**\n{state.get('legal_analysis', 'N/A')}\n\n"
                f"**Cost Breakdown:**\n{state.get('financial_breakdown', 'N/A')}\n\n"
                f"**Timeline:**\n{state.get('timeline_estimate', 'N/A')}"
            )
            return {
                "final_answer": fallback,
                "errors": [f"Synthesizer: {e}"],
            }

    async def process(
        self,
        query: str,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run multi-agent workflow for a complex query.

        Args:
            query: User query requiring multi-domain expertise
            user_context: Optional user metadata

        Returns:
            Dict with keys: query, legal_analysis, financial_breakdown,
            timeline_estimate, agent_outputs, final_answer, errors,
            execution_time_s
        """
        start_time = time.time()
        logger.info(f'🚀 [MultiAgentCoordinator] Processing: "{query[:80]}..."')

        initial_state: MultiAgentState = {
            "query": query,
            "user_context": user_context or {},
            "legal_analysis": "",
            "financial_breakdown": "",
            "timeline_estimate": "",
            "agent_outputs": [],
            "final_answer": "",
            "errors": [],
        }

        try:
            self._ensure_initialized()
            result = await self._graph.ainvoke(initial_state)
            execution_time = time.time() - start_time

            # Count successful agents
            successful_agents = [o for o in result.get("agent_outputs", []) if "error" not in o]
            error_agents = [o for o in result.get("agent_outputs", []) if "error" in o]

            logger.info(
                f"✅ [MultiAgentCoordinator] Complete in {execution_time:.2f}s "
                f"({len(successful_agents)} agents succeeded, {len(error_agents)} failed)",
            )

            result["execution_time_s"] = round(execution_time, 2)
            return dict(result)

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"❌ [MultiAgentCoordinator] Workflow failed in {execution_time:.2f}s: {e}",
                exc_info=True,
            )
            return {
                **initial_state,
                "final_answer": f"Multi-agent processing failed: {e}. Please try a simpler query.",
                "errors": [str(e)],
                "execution_time_s": round(execution_time, 2),
            }


# ============================================================================
# Query Detection
# ============================================================================


def requires_multi_agent(query: str, entities: list[dict[str, Any]] | None = None) -> bool:
    """
    Detect if a query needs multi-agent coordination.

    Triggers when:
        - Query asks about cost AND timeline ("how much and when")
        - Query mentions multiple domains (visa + tax, company + timeline)
        - Entity count > 5 (complex query spanning multiple topics)

    Args:
        query: User query string
        entities: Optional extracted entities from entity extractor

    Returns:
        True if multi-agent coordination is recommended
    """
    q = query.lower()

    # Cost + Timeline patterns (bilingual: EN + ID + IT)
    cost_keywords = {
        "cost",
        "price",
        "biaya",
        "harga",
        "berapa",
        "quanto",
        "costa",
        "prezzo",
        "fee",
    }
    time_keywords = {
        "when",
        "kapan",
        "timeline",
        "duration",
        "lama",
        "quanto tempo",
        "how long",
        "waktu",
    }

    has_cost = any(kw in q for kw in cost_keywords)
    has_time = any(kw in q for kw in time_keywords)

    if has_cost and has_time:
        logger.debug("🔀 [MultiAgent] Triggered: cost+time pattern in query")
        return True

    # Multiple domain detection
    if entities:
        domains: set[str] = set()
        for entity in entities:
            entity_type = entity.get("entity_type", "")
            if entity_type in ("kitas", "kitap", "vitas", "rptka", "imta", "tka", "izin_tinggal"):
                domains.add("immigration")
            elif entity_type in ("pph", "pph_21", "pph_23", "ppn", "pbb", "tax", "spt"):
                domains.add("tax")
            elif entity_type in ("pt_pma", "pt_pmdn", "pt_perorangan", "badan_usaha", "cv"):
                domains.add("company")
            elif entity_type in ("biaya", "amount"):
                domains.add("financial")

        if len(domains) >= 2:
            logger.debug(f"🔀 [MultiAgent] Triggered: {len(domains)} domains detected: {domains}")
            return True

        # High entity count
        if len(entities) > 5:
            logger.debug(f"🔀 [MultiAgent] Triggered: {len(entities)} entities (>5)")
            return True

    # Multi-part question patterns
    multi_part_patterns = [
        " and ",
        " dan ",
        " e ",  # Italian "and"
        " serta ",
        "how much",
        "berapa lama",
    ]
    conjunction_count = sum(1 for p in multi_part_patterns if p in q)
    if conjunction_count >= 2:
        logger.debug(f"🔀 [MultiAgent] Triggered: {conjunction_count} conjunctions")
        return True

    return False
