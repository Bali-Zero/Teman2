"""
Autonomous Research Agent - Phase 4 (Advanced Agent)

Self-directed research agent that iteratively explores Qdrant collections
to answer complex or ambiguous queries without human intervention.

Example: "How to open a crypto company in Indonesia?"
→ Iteration 1: Search kbli_eye → "crypto" not in KBLI database
→ Iteration 2: Expand to legal_updates → finds OJK crypto regulation 2024
→ Iteration 3: Search tax_genius → crypto tax treatment
→ Iteration 4: Search visa_oracle → fintech director visa requirements
→ Synthesis: Comprehensive answer despite no direct KBLI match

Key Features:
- Self-directed query expansion
- Iterative collection exploration
- Semantic similarity for expansion
- Reasoning chain transparency
- Automatic termination when sufficient info gathered
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ResearchStep:
    """Single step in research process"""

    step_number: int
    collection: str
    query: str
    rationale: str  # Why this search was performed
    results_found: int
    confidence: float
    key_findings: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ResearchResult:
    """Final result of autonomous research"""

    original_query: str
    total_steps: int
    collections_explored: list[str]
    research_steps: list[ResearchStep]
    final_answer: str
    confidence: float
    reasoning_chain: list[str]  # Explanation of research process
    sources_consulted: int
    duration_ms: float


class AutonomousResearchService:
    """
    Autonomous research agent that explores Qdrant collections iteratively.

    The agent:
    1. Starts with initial query
    2. Searches most relevant collection
    3. Analyzes results for gaps
    4. Expands query based on findings
    5. Searches additional collections
    6. Repeats until confident or max iterations
    7. Synthesizes findings into final answer using ZANTARA AI
    """

    MAX_ITERATIONS = 5  # Safety limit
    CONFIDENCE_THRESHOLD = 0.7  # Stop if confidence >= this
    MIN_RESULTS_THRESHOLD = 3  # Minimum results to consider

    def __init__(self, search_service, query_router, zantara_ai_service):
        """
        Initialize Autonomous Research Agent.

        Args:
            search_service: SearchService for collection queries
            query_router: QueryRouter for collection selection
            zantara_ai_service: ZANTARA AI for synthesis
        """
        self.search = search_service
        self.router = query_router
        self.zantara = zantara_ai_service

        self.research_stats = {
            "total_researches": 0,
            "avg_iterations": 0.0,
            "avg_confidence": 0.0,
            "max_iterations_reached": 0,
        }

        logger.info("✅ AutonomousResearchService initialized")
        logger.info(f"   Max iterations: {self.MAX_ITERATIONS}")
        logger.info(f"   Confidence threshold: {self.CONFIDENCE_THRESHOLD}")

    async def analyze_gaps(
        self, query: str, results: list[dict], collections_searched: list[str]
    ) -> tuple[bool, list[str], str]:
        """
        Analyze search results for information gaps.

        Args:
            query: Original query
            results: Search results so far
            collections_searched: Collections already explored

        Returns:
            Tuple of (has_gaps, suggested_queries, rationale)
        """
        # Simple gap detection (could be enhanced with LLM)

        if not results or len(results) < self.MIN_RESULTS_THRESHOLD:
            return (
                True,
                [query],  # Try same query in different collection
                "Insufficient results found",
            )

        # Check for low confidence scores
        avg_confidence = sum(r.get("score", 0) for r in results) / len(results)
        if avg_confidence < 0.5:
            return (
                True,
                [query, f"{query} requirements", f"{query} process"],
                "Low confidence in current results",
            )

        # Check if results contain uncertainty keywords
        all_text = " ".join(r.get("text", "") for r in results).lower()
        uncertainty_keywords = [
            "not clear",
            "uncertain",
            "depends",
            "varies",
            "may",
            "might",
            "tidak jelas",
            "tergantung",
            "mungkin",
        ]

        has_uncertainty = any(kw in all_text for kw in uncertainty_keywords)
        if has_uncertainty:
            return (
                True,
                [f"{query} specific requirements", f"{query} regulations"],
                "Results contain uncertainty - need more specific info",
            )

        # If we've only searched 1-2 collections, try more
        if len(collections_searched) < 3:
            return (True, [query], "Limited collection coverage - expanding search")

        # No gaps detected
        return (False, [], "Sufficient information gathered")

    def select_next_collection(self, query: str, collections_searched: list[str]) -> str | None:
        """
        Select next collection to search.

        Args:
            query: Current query
            collections_searched: Collections already explored

        Returns:
            Collection name or None if no more to try
        """
        # Use query router with fallback chain
        primary, confidence, all_collections = self.router.route_with_confidence(
            query, return_fallbacks=True
        )

        # Filter out already searched
        remaining = [c for c in all_collections if c not in collections_searched]

        if remaining:
            logger.info(f"   Next collection: {remaining[0]} (from {len(remaining)} remaining)")
            return remaining[0]

        logger.info("   No more collections to search")
        return None

    async def expand_query(self, original_query: str, findings_so_far: list[str]) -> list[str]:
        """
        Generate expanded queries based on findings.

        Args:
            original_query: Original user query
            findings_so_far: Key findings from previous iterations

        Returns:
            List of expanded query strings
        """
        # Simple expansion (could be enhanced with LLM)
        expansions = []

        # Add original query
        expansions.append(original_query)

        # If findings mention specific terms, create focused queries
        if findings_so_far:
            # Extract key nouns/entities (simple approach)
            all_findings_text = " ".join(findings_so_far)

            # Common Indonesian business terms
            business_terms = [
                "PT",
                "PMA",
                "KBLI",
                "NIB",
                "OSS",
                "NPWP",
                "KITAS",
                "visa",
                "tax",
                "license",
                "permit",
                "regulation",
            ]

            mentioned_terms = [
                term for term in business_terms if term.lower() in all_findings_text.lower()
            ]

            for term in mentioned_terms[:2]:  # Max 2 expansions
                expansions.append(f"{term} for {original_query}")

        return expansions[:3]  # Max 3 query variants

    async def research_iteration(
        self, query: str, step_number: int, collections_searched: list[str], user_level: int = 3
    ) -> ResearchStep:
        """
        Perform single research iteration.

        Args:
            query: Query for this iteration
            step_number: Iteration number
            collections_searched: Collections already searched
            user_level: User access level

        Returns:
            ResearchStep with results
        """
        logger.info(f"   [Step {step_number}] Query: '{query}'")

        # Select collection
        collection = self.select_next_collection(query, collections_searched)

        if not collection:
            # No more collections - return empty step
            return ResearchStep(
                step_number=step_number,
                collection="none",
                query=query,
                rationale="No more collections available",
                results_found=0,
                confidence=0.0,
                key_findings=[],
            )

        collections_searched.append(collection)

        # Search
        try:
            search_results = await self.search.search(
                query=query, user_level=user_level, limit=5, collection_override=collection
            )

            results = search_results.get("results", [])
            results_found = len(results)

            # Calculate confidence
            if results:
                avg_score = sum(r.get("score", 0) for r in results) / len(results)
                confidence = avg_score
            else:
                confidence = 0.0

            # Extract key findings (top 3 results, first 200 chars each)
            key_findings = []
            for result in results[:3]:
                text = result.get("text", "")
                finding = text[:200] + ("..." if len(text) > 200 else "")
                key_findings.append(finding)

            # Generate rationale
            rationale = f"Searched {collection} for relevant information"

            step = ResearchStep(
                step_number=step_number,
                collection=collection,
                query=query,
                rationale=rationale,
                results_found=results_found,
                confidence=confidence,
                key_findings=key_findings,
            )

            logger.info(
                f"   [Step {step_number}] {collection}: "
                f"{results_found} results, confidence={confidence:.2f}"
            )

            return step

        except Exception as e:
            logger.error(f"   [Step {step_number}] Error: {e}")
            return ResearchStep(
                step_number=step_number,
                collection=collection,
                query=query,
                rationale=f"Search failed: {e}",
                results_found=0,
                confidence=0.0,
                key_findings=[],
            )

    async def synthesize_research(
        self, original_query: str, research_steps: list[ResearchStep]
    ) -> tuple[str, float]:
        """
        Synthesize findings from all research steps into final answer.

        Args:
            original_query: Original user query
            research_steps: All research steps performed

        Returns:
            Tuple of (final_answer, confidence)
        """
        logger.info("🧠 Synthesizing research findings...")

        # Build context from all findings
        context_parts = []

        for step in research_steps:
            if step.results_found > 0:
                context_parts.append(
                    f"\n=== {step.collection.upper()} (Step {step.step_number}) ==="
                )
                for finding in step.key_findings:
                    context_parts.append(f"- {finding}")

        if not context_parts:
            return (
                f"I searched {len(research_steps)} collections but couldn't find sufficient information about: {original_query}",
                0.1,
            )

        context = "\n".join(context_parts)

        # Synthesis prompt
        prompt = f"""Based on autonomous research across multiple knowledge collections, provide a comprehensive answer.

Original Query: {original_query}

Research Process (explored {len(research_steps)} steps):
{context}

Task: Synthesize the findings above into a clear, actionable answer. If information is incomplete or uncertain, state what is known and what remains unclear. Be transparent about the research process.

Format:
## Answer
[Your comprehensive answer]

## Sources Consulted
[List collections searched]

## Confidence Level
[Your confidence in this answer: High/Medium/Low and why]
"""

        try:
            response = await self.zantara.conversational(
                message=prompt,
                user_id="autonomous_research",
                conversation_history=[],
                max_tokens=1000,
            )

            synthesis = response.get("text", "")

            # Calculate overall confidence
            # Base on: avg step confidence, number of steps, results coverage
            step_confidences = [s.confidence for s in research_steps if s.confidence > 0]
            avg_confidence = (
                sum(step_confidences) / len(step_confidences) if step_confidences else 0.0
            )

            total_results = sum(s.results_found for s in research_steps)
            coverage_bonus = min(total_results / 10, 0.2)  # Up to +0.2 for good coverage

            overall_confidence = min(avg_confidence + coverage_bonus, 1.0)

            logger.info(f"✅ Synthesis complete (confidence={overall_confidence:.2f})")

            return synthesis, overall_confidence

        except Exception as e:
            logger.error(f"❌ Synthesis error: {e}")
            # Fallback: simple concatenation
            fallback = f"Research findings for: {original_query}\n\n"
            for step in research_steps:
                if step.key_findings:
                    fallback += f"\nFrom {step.collection}:\n"
                    fallback += "\n".join(f"- {f}" for f in step.key_findings)

            return fallback, 0.5

    async def research(self, query: str, user_level: int = 3) -> ResearchResult:
        """
        Perform autonomous research to answer a query.

        Args:
            query: User query
            user_level: User access level

        Returns:
            ResearchResult with complete research process
        """
        import time

        start_time = time.time()

        self.research_stats["total_researches"] += 1

        logger.info(f"🔍 Starting autonomous research: '{query}'")

        research_steps = []
        collections_searched = []
        reasoning_chain = []

        current_query = query
        iteration = 0

        # Research loop
        while iteration < self.MAX_ITERATIONS:
            iteration += 1

            # Perform research step
            step = await self.research_iteration(
                query=current_query,
                step_number=iteration,
                collections_searched=collections_searched,
                user_level=user_level,
            )

            research_steps.append(step)

            # Add to reasoning chain
            reasoning_chain.append(
                f"Step {iteration}: Searched {step.collection} for '{current_query}' - "
                f"found {step.results_found} results (confidence={step.confidence:.2f})"
            )

            # Check termination conditions
            if step.confidence >= self.CONFIDENCE_THRESHOLD:
                reasoning_chain.append(
                    f"Terminating: High confidence achieved ({step.confidence:.2f})"
                )
                logger.info(f"   High confidence reached at step {iteration}")
                break

            if step.results_found == 0 and iteration > 1:
                # No results and not first iteration - might be dead end
                reasoning_chain.append("No results in this collection - trying different approach")

            # Analyze gaps
            all_findings = []
            for s in research_steps:
                all_findings.extend(s.key_findings)

            has_gaps, expanded_queries, gap_rationale = await self.analyze_gaps(
                query, [{"text": f, "score": 0.5} for f in all_findings], collections_searched
            )

            if not has_gaps:
                reasoning_chain.append("Terminating: Sufficient information gathered")
                logger.info(f"   Sufficient info at step {iteration}")
                break

            reasoning_chain.append(f"Gap detected: {gap_rationale}")

            # Expand query for next iteration
            if expanded_queries and len(expanded_queries) > iteration - 1:
                current_query = expanded_queries[min(iteration - 1, len(expanded_queries) - 1)]
            else:
                # Use same query but different collection
                current_query = query

        if iteration >= self.MAX_ITERATIONS:
            reasoning_chain.append(f"Terminating: Max iterations ({self.MAX_ITERATIONS}) reached")
            self.research_stats["max_iterations_reached"] += 1
            logger.warning("   Max iterations reached")

        # Synthesize findings
        final_answer, overall_confidence = await self.synthesize_research(query, research_steps)

        duration_ms = (time.time() - start_time) * 1000

        result = ResearchResult(
            original_query=query,
            total_steps=len(research_steps),
            collections_explored=collections_searched,
            research_steps=research_steps,
            final_answer=final_answer,
            confidence=overall_confidence,
            reasoning_chain=reasoning_chain,
            sources_consulted=sum(s.results_found for s in research_steps),
            duration_ms=duration_ms,
        )

        # Update stats
        self.research_stats["avg_iterations"] = (
            self.research_stats["avg_iterations"] * (self.research_stats["total_researches"] - 1)
            + len(research_steps)
        ) / self.research_stats["total_researches"]

        self.research_stats["avg_confidence"] = (
            self.research_stats["avg_confidence"] * (self.research_stats["total_researches"] - 1)
            + overall_confidence
        ) / self.research_stats["total_researches"]

        logger.info(
            f"✅ Research complete: {len(research_steps)} steps, "
            f"{len(collections_searched)} collections, "
            f"confidence={overall_confidence:.2f}, "
            f"{duration_ms:.0f}ms"
        )

        return result

    def get_research_stats(self) -> dict:
        """Get research statistics"""
        return {
            **self.research_stats,
            "max_iterations_rate": f"{(self.research_stats['max_iterations_reached'] / max(self.research_stats['total_researches'], 1) * 100):.1f}%",
        }
