"""
KG-Agentic RAG Orchestrator

Multi-step reasoning orchestrator that combines:
1. Intent classification and entity extraction
2. Knowledge Graph traversal and golden route matching
3. Vector search with KG-informed collection routing
4. LLM synthesis with structured reasoning trace

This orchestrator provides explainable, high-quality answers by integrating
structured knowledge (KG) with semantic search (vector) and reasoning (LLM).

Author: Nuzantara Team
Date: 2026-01-28
Version: 1.0.0
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from backend.app.utils.tracing import set_span_attribute, trace_span
from backend.services.classification.intent_classifier import IntentClassifier
from backend.services.rag.agentic.llm_gateway import TIER_FLASH, TIER_PRO, LLMGateway
from backend.services.rag.agentic.tools import VectorSearchTool
from backend.services.rag.kg_enhanced_retrieval import GoldenRoute, KGContext, KGEnhancedRetrieval

logger = logging.getLogger(__name__)


@dataclass
class AgenticResponse:
    """
    Structured response from KG-Agentic Orchestrator.

    Includes answer, confidence, reasoning trace, sources, and optional
    timeline/cost estimates from golden routes.
    """

    answer: str
    confidence: float
    reasoning_trace: list[str]
    sources: list[dict[str, Any]] = field(default_factory=list)
    estimated_timeline: str | None = None
    estimated_cost: str | None = None

    # Additional metadata
    intent_category: str | None = None
    golden_route_matched: str | None = None
    kg_entities_found: int = 0
    collections_searched: list[str] = field(default_factory=list)

    # Performance metrics
    total_time_ms: float = 0.0
    model_used: str | None = None


class KGAgenticOrchestrator:
    """
    Multi-step reasoning orchestrator combining KG + Vector Search + Reasoning.

    This orchestrator implements an agentic workflow that:
    1. Analyzes query intent (visa? company? tax?)
    2. Extracts entities and finds KG paths
    3. Matches golden routes for known scenarios
    4. Executes vector search on relevant collections
    5. Synthesizes answer with citation + KG path explanation
    6. Generates reasoning trace for explainability

    Architecture:
        - Uses KGEnhancedRetrieval for graph context and golden routes
        - Uses VectorSearchTool for semantic search across collections
        - Uses IntentClassifier for query understanding
        - Uses LLMGateway for synthesis and reasoning

    Example:
        >>> orchestrator = KGAgenticOrchestrator(db_pool=pool, retriever=search_service)
        >>> response = await orchestrator.process(
        ...     query="How to open a restaurant in Bali as a foreigner?",
        ...     session_id="session_123"
        ... )
        >>> logger.info(response.reasoning_trace)
        ['Detected intent: business_setup + immigration', ...]
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        retriever: Any,
        llm_gateway: LLMGateway | None = None,
        intent_classifier: IntentClassifier | None = None,
    ) -> None:
        """
        Initialize KG-Agentic Orchestrator.

        Args:
            db_pool: AsyncPG connection pool for KG database access
            retriever: SearchService instance for vector search
            llm_gateway: Optional LLMGateway for LLM synthesis
            intent_classifier: Optional IntentClassifier for query analysis
        """
        self.db_pool = db_pool
        self.retriever = retriever

        # Initialize KG Enhanced Retrieval
        self.kg_retrieval = KGEnhancedRetrieval(db_pool=db_pool)
        logger.info("✅ KGEnhancedRetrieval initialized")

        # Initialize Vector Search Tool
        self.vector_tool = VectorSearchTool(retriever=retriever, user_level=3)
        logger.info("✅ VectorSearchTool initialized")

        # Initialize LLM Gateway
        self.llm_gateway = llm_gateway or LLMGateway()
        logger.info("✅ LLMGateway initialized")

        # Initialize Intent Classifier
        self.intent_classifier = intent_classifier or IntentClassifier()
        logger.info("✅ IntentClassifier initialized")

        # Collection routing map (intent -> preferred collections)
        self.collection_routing = {
            "visa": ["visa_oracle"],
            "immigration": ["visa_oracle"],
            "company": ["legal_unified", "kbli_2025_final"],
            "business": ["legal_unified", "kbli_2025_final"],
            "tax": ["tax_genius"],
            "kbli": ["kbli_2025_final"],
            "pricing": ["bali_zero_pricing_hybrid"],
        }

        logger.info("✅ KGAgenticOrchestrator initialized")

    async def process(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
    ) -> AgenticResponse:
        """
        Process query with KG-enhanced agentic reasoning.

        Orchestration Flow:
        1. Intent classification + entity extraction
        2. KG traversal (use kg_enhanced_retrieval)
        3. Golden route matching (if applicable)
        4. Vector search with KG-informed collection selection
        5. LLM synthesis with structured output
        6. Generate reasoning trace for explainability

        Args:
            query: User query string
            session_id: Session identifier for context
            user_id: Optional user identifier

        Returns:
            AgenticResponse with answer, reasoning trace, sources, and metadata
        """
        start_time = time.time()
        reasoning_trace: list[str] = []

        with trace_span(
            "kg_agentic_orchestrator.process",
            {"query_length": len(query), "session_id": session_id},
        ):
            try:
                # Step 1: Intent Classification
                logger.info(f"🧠 [Step 1] Classifying intent for query: {query[:100]}...")
                intent_result = await self._classify_intent(query)
                reasoning_trace.append(
                    f"Detected intent: {intent_result['category']} "
                    f"(confidence: {intent_result['confidence']:.2f})"
                )
                set_span_attribute("intent_category", intent_result["category"])

                # Step 2: KG Context Retrieval
                logger.info("🔗 [Step 2] Retrieving KG context...")
                kg_context = await self._get_kg_context(query)

                if kg_context.entities_found:
                    entity_names = [e.get("name", "unknown") for e in kg_context.entities_found[:3]]
                    reasoning_trace.append(
                        f"Extracted entities: {', '.join(entity_names)} "
                        f"({len(kg_context.entities_found)} total)"
                    )
                    set_span_attribute("kg_entities_count", len(kg_context.entities_found))

                if kg_context.relationships:
                    reasoning_trace.append(
                        f"KG path: {len(kg_context.relationships)} relationships found"
                    )

                # Step 3: Golden Route Matching
                golden_route = kg_context.golden_route
                if golden_route:
                    logger.info(f"🌟 [Step 3] Golden route matched: {golden_route.route_id}")
                    reasoning_trace.append(f"Golden route matched: {golden_route.name}")
                    reasoning_trace.append(
                        f"Recommended path: {' → '.join(golden_route.path[:3])}..."
                    )
                    set_span_attribute("golden_route_id", golden_route.route_id)
                else:
                    logger.info("🌟 [Step 3] No golden route matched")
                    reasoning_trace.append("No pre-defined golden route matched")

                # Step 4: Vector Search with KG-informed routing
                logger.info("🔍 [Step 4] Executing vector search...")
                search_results, collections_searched = await self._execute_vector_search(
                    query=query,
                    intent_result=intent_result,
                    kg_context=kg_context,
                )

                reasoning_trace.append(
                    f"Vector search: {collections_searched} "
                    f"({len(search_results.get('sources', []))} chunks retrieved)"
                )
                set_span_attribute("collections_searched", str(collections_searched))

                # Step 5: LLM Synthesis
                logger.info("🤖 [Step 5] Synthesizing answer with LLM...")
                synthesis_result = await self._synthesize_answer(
                    query=query,
                    intent_result=intent_result,
                    kg_context=kg_context,
                    search_results=search_results,
                    golden_route=golden_route,
                )

                reasoning_trace.append(
                    f"LLM synthesis: {synthesis_result['model_used']} "
                    f"({synthesis_result['tokens_used']} tokens)"
                )

                # Step 6: Build Final Response
                logger.info("📦 [Step 6] Building final response...")
                response = self._build_response(
                    answer=synthesis_result["answer"],
                    confidence=synthesis_result["confidence"],
                    reasoning_trace=reasoning_trace,
                    sources=search_results.get("sources", []),
                    intent_result=intent_result,
                    kg_context=kg_context,
                    golden_route=golden_route,
                    collections_searched=collections_searched,
                    model_used=synthesis_result["model_used"],
                    start_time=start_time,
                )

                total_time = (time.time() - start_time) * 1000
                logger.info(
                    f"✅ KG-Agentic orchestration complete in {total_time:.0f}ms "
                    f"(confidence: {response.confidence:.2f})"
                )

                return response

            except Exception as e:
                logger.error(f"❌ KG-Agentic orchestration failed: {e}", exc_info=True)
                reasoning_trace.append(f"Error during orchestration: {str(e)}")

                # Return fallback response
                return AgenticResponse(
                    answer=(
                        "Mi dispiace, si è verificato un errore durante l'elaborazione "
                        "della tua richiesta. Per favore riprova."
                    ),
                    confidence=0.0,
                    reasoning_trace=reasoning_trace,
                    sources=[],
                    total_time_ms=(time.time() - start_time) * 1000,
                )

    async def _classify_intent(self, query: str) -> dict[str, Any]:
        """
        Classify query intent using IntentClassifier.

        Args:
            query: User query

        Returns:
            Intent classification result with category, confidence, suggested_ai
        """
        try:
            result = await self.intent_classifier.classify_intent(query)
            logger.debug(f"Intent classified: {result['category']} ({result['confidence']:.2f})")
            return result
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")
            return {
                "category": "unknown",
                "confidence": 0.5,
                "suggested_ai": "fast",
            }

    async def _get_kg_context(self, query: str) -> KGContext:
        """
        Retrieve KG context including entities, relationships, and golden routes.

        Args:
            query: User query

        Returns:
            KGContext with entities, relationships, chunk IDs, and golden route
        """
        try:
            kg_context = await self.kg_retrieval.get_context_for_query(
                query=query,
                max_depth=2,  # 2-hop traversal for richer context
                max_entities=15,  # Limit entities to avoid overwhelming context
            )

            logger.debug(
                f"KG context retrieved: {len(kg_context.entities_found)} entities, "
                f"{len(kg_context.relationships)} relationships, "
                f"golden_route={'matched' if kg_context.golden_route else 'none'}"
            )

            return kg_context

        except Exception as e:
            logger.warning(f"KG context retrieval failed: {e}")
            # Return empty context on error
            return KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.0,
                golden_route=None,
            )

    async def _execute_vector_search(
        self,
        query: str,
        intent_result: dict[str, Any],
        kg_context: KGContext,
    ) -> tuple[dict[str, Any], list[str]]:
        """
        Execute vector search with KG-informed collection routing.

        Uses intent classification and KG entities to intelligently select
        which collections to search.

        Args:
            query: User query
            intent_result: Intent classification result
            kg_context: KG context with entities and relationships

        Returns:
            Tuple of (search_results_dict, collections_searched_list)
        """
        try:
            # Determine target collections based on intent and KG entities
            target_collections = self._route_collections(intent_result, kg_context)

            # Execute search
            if target_collections:
                # Search specific collections
                logger.info(f"Searching collections: {target_collections}")

                # Execute searches in parallel for better performance
                search_tasks = []
                for collection in target_collections:
                    task = self.vector_tool.execute(
                        query=query,
                        collection=collection,
                        top_k=5,  # 5 per collection to avoid overwhelming context
                    )
                    search_tasks.append(task)

                results = await asyncio.gather(*search_tasks, return_exceptions=True)

                # Merge results
                all_sources = []
                for result in results:
                    if isinstance(result, str):
                        try:
                            parsed = json.loads(result)
                            all_sources.extend(parsed.get("sources", []))
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse search result")

                # Deduplicate and sort by score
                seen_ids = set()
                unique_sources = []
                for source in all_sources:
                    source_id = source.get("doc_id", source.get("id", ""))
                    if source_id and source_id not in seen_ids:
                        seen_ids.add(source_id)
                        unique_sources.append(source)

                unique_sources.sort(key=lambda x: x.get("score", 0), reverse=True)

                return (
                    {
                        "sources": unique_sources[:10],  # Top 10 overall
                        "content": "\n\n".join([s.get("title", "") for s in unique_sources[:10]]),
                    },
                    target_collections,
                )

            else:
                # Federated search across all collections
                logger.info("Executing federated search across all collections")
                result_str = await self.vector_tool.execute(
                    query=query,
                    collection=None,  # None triggers federated search
                    top_k=10,
                )

                try:
                    result = json.loads(result_str)
                    return result, ["federated_all"]
                except json.JSONDecodeError:
                    logger.warning("Failed to parse federated search result")
                    return {"sources": [], "content": ""}, ["federated_all"]

        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            return {"sources": [], "content": ""}, []

    def _route_collections(
        self,
        intent_result: dict[str, Any],
        kg_context: KGContext,
    ) -> list[str]:
        """
        Intelligently route to collections based on intent and KG entities.

        Args:
            intent_result: Intent classification result
            kg_context: KG context with entities

        Returns:
            List of collection names to search
        """
        collections = set()

        # Route based on intent category
        category = intent_result.get("category", "").lower()
        for keyword, cols in self.collection_routing.items():
            if keyword in category:
                collections.update(cols)

        # Route based on KG entity types
        for entity in kg_context.entities_found[:5]:  # Check top 5 entities
            entity_type = entity.get("entity_type", "").lower()

            if entity_type in ["kitas", "kitap", "vitas", "evisa", "visa"]:
                collections.add("visa_oracle")
            elif entity_type in ["kbli", "nib", "oss"]:
                collections.add("kbli_2025_final")
            elif entity_type in ["pph", "ppn", "pbb", "npwp", "tax"]:
                collections.add("tax_genius")
            elif entity_type in ["pt_pma", "pt_pmdn", "badan_usaha", "undang_undang"]:
                collections.add("legal_unified")

        # If golden route matched, add relevant collections
        if kg_context.golden_route:
            route_id = kg_context.golden_route.route_id
            if "restaurant" in route_id or "company" in route_id:
                collections.update(["legal_unified", "kbli_2025_final", "visa_oracle"])
            elif "work" in route_id or "kitas" in route_id:
                collections.add("visa_oracle")

        return list(collections) if collections else []

    async def _synthesize_answer(
        self,
        query: str,
        intent_result: dict[str, Any],
        kg_context: KGContext,
        search_results: dict[str, Any],
        golden_route: GoldenRoute | None,
    ) -> dict[str, Any]:
        """
        Synthesize final answer using LLM with KG context and search results.

        Args:
            query: User query
            intent_result: Intent classification
            kg_context: KG context
            search_results: Vector search results
            golden_route: Matched golden route (if any)

        Returns:
            Synthesis result with answer, confidence, model_used, tokens_used
        """
        try:
            # Build context for LLM
            context_parts = []

            # Add KG summary
            if kg_context.graph_summary:
                context_parts.append("**Knowledge Graph Context:**\n" + kg_context.graph_summary)

            # Add golden route if matched
            if golden_route:
                route_text = self.kg_retrieval.format_golden_route(golden_route)
                context_parts.append(route_text)

            # Add search results
            if search_results.get("sources"):
                sources_text = "\n\n".join(
                    [
                        f"[{i + 1}] {s.get('title', 'Document')}\n{s.get('snippet', '')}"
                        for i, s in enumerate(search_results["sources"][:5])
                    ]
                )
                context_parts.append("**Retrieved Documents:**\n" + sources_text)

            context = "\n\n---\n\n".join(context_parts)

            # Build prompt (KBLI-centric for business queries)
            # Detect if query involves business activity (KBLI should be primary)
            business_keywords = [
                "restaurant",
                "cafe",
                "hotel",
                "business",
                "company",
                "open",
                "start",
                "restoran",
                "kafe",
                "usaha",
                "bisnis",
                "buka",
                "pt",
                "pma",
            ]
            is_business_query = any(kw in query.lower() for kw in business_keywords)

            system_prompt = (
                "You are Zantara AI, expert in Indonesian business regulations (KBLI 2025) and immigration law. "
                "For business-related questions, ALWAYS structure your answer with the KBLI code as the foundation. "
                "Provide accurate, well-cited answers based on the provided context."
            )

            if is_business_query:
                user_message = f"""Query: {query}

Context:
{context}

IMPORTANT - Answer Structure for Business Queries:
1. START with the primary KBLI code and its full details:
   - Code number and name (Indonesian + English)
   - PMA status (TERBUKA/TERBATAS/TERTUTUP) and what it means
   - Capital requirements if PMA relevant
   - Licensing requirements by business scale

2. THEN address visa/immigration constraints if relevant to the query

3. THEN explain practical options/solutions (PT PMA, PT biasa with partner, etc.)

4. Cite specific sources and indicate uncertainties

Answer:"""
            else:
                user_message = f"""Query: {query}

Context:
{context}

Please provide a comprehensive answer that:
1. Directly answers the user's question
2. Cites specific sources from the context
3. Explains the reasoning path if a golden route was matched
4. Indicates any uncertainties or limitations

Answer:"""

            # Determine model tier based on intent
            tier = TIER_PRO if intent_result.get("suggested_ai") == "pro" else TIER_FLASH

            # Create chat session
            chat = self.llm_gateway.create_chat_with_history(
                history_to_use=[],
                model_tier=tier,
                system_instruction=system_prompt,
            )

            # Send message
            response, model_used, response_obj, _usage = await self.llm_gateway.send_message(
                chat=chat,
                message=user_message,
                tier=tier,
            )

            # Extract token usage
            tokens_used = 0
            if hasattr(response_obj, "usage_metadata"):
                tokens_used = getattr(response_obj.usage_metadata, "total_token_count", 0)

            # Calculate confidence based on multiple factors
            confidence = self._calculate_confidence(
                kg_context=kg_context,
                search_results=search_results,
                golden_route=golden_route,
                response_length=len(response),
            )

            return {
                "answer": response,
                "confidence": confidence,
                "model_used": model_used,
                "tokens_used": tokens_used,
            }

        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}", exc_info=True)
            return {
                "answer": (
                    "Mi dispiace, non sono riuscito a sintetizzare una risposta completa. "
                    "Per favore riprova o riformula la domanda."
                ),
                "confidence": 0.0,
                "model_used": "error",
                "tokens_used": 0,
            }

    def _calculate_confidence(
        self,
        kg_context: KGContext,
        search_results: dict[str, Any],
        golden_route: GoldenRoute | None,
        response_length: int,
    ) -> float:
        """
        Calculate confidence score based on multiple signals.

        Args:
            kg_context: KG context
            search_results: Vector search results
            golden_route: Matched golden route
            response_length: Length of generated response

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.5  # Base confidence

        # Boost for golden route match
        if golden_route:
            confidence += 0.25

        # Boost for KG entities found
        if kg_context.entities_found:
            confidence += min(0.15, len(kg_context.entities_found) * 0.03)

        # Boost for search results
        if search_results.get("sources"):
            num_sources = len(search_results["sources"])
            confidence += min(0.15, num_sources * 0.03)

        # Boost for substantial response
        if response_length > 200:
            confidence += 0.05

        # Cap at 0.95 (never 100% certain)
        return min(0.95, confidence)

    def _build_response(
        self,
        answer: str,
        confidence: float,
        reasoning_trace: list[str],
        sources: list[dict[str, Any]],
        intent_result: dict[str, Any],
        kg_context: KGContext,
        golden_route: GoldenRoute | None,
        collections_searched: list[str],
        model_used: str,
        start_time: float,
    ) -> AgenticResponse:
        """
        Build final AgenticResponse with all metadata.

        Args:
            answer: Generated answer
            confidence: Confidence score
            reasoning_trace: List of reasoning steps
            sources: Retrieved sources
            intent_result: Intent classification
            kg_context: KG context
            golden_route: Matched golden route
            collections_searched: Collections searched
            model_used: LLM model used
            start_time: Start timestamp

        Returns:
            Complete AgenticResponse
        """
        # Extract timeline and cost from golden route
        estimated_timeline = None
        estimated_cost = None

        if golden_route:
            if golden_route.estimated_timeline_months:
                months = golden_route.estimated_timeline_months
                estimated_timeline = (
                    f"~{months} months" if months > 1 else f"~{int(months * 30)} days"
                )

            if golden_route.estimated_cost_range_usd:
                low, high = golden_route.estimated_cost_range_usd
                estimated_cost = f"${low:,} - ${high:,} USD"

        return AgenticResponse(
            answer=answer,
            confidence=confidence,
            reasoning_trace=reasoning_trace,
            sources=sources,
            estimated_timeline=estimated_timeline,
            estimated_cost=estimated_cost,
            intent_category=intent_result.get("category"),
            golden_route_matched=golden_route.route_id if golden_route else None,
            kg_entities_found=len(kg_context.entities_found),
            collections_searched=collections_searched,
            total_time_ms=(time.time() - start_time) * 1000,
            model_used=model_used,
        )
