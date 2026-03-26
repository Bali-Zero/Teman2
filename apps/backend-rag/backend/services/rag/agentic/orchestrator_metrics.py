"""
Orchestrator Metrics Manager

Responsabilità singola: Metrics collection e timing tracking.
Include:
- Timing extraction da ReAct loop steps
- Prometheus metrics recording
- Token usage tracking
- Structured logging per analytics

Questo modulo è testabile in isolamento mockando metrics_collector.
"""

import logging
import time
from typing import Any

from backend.app.metrics import metrics_collector
from backend.services.llm_clients.pricing import TokenUsage
from backend.services.tools.definitions import AgentState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Info level for metrics operations


class OrchestratorMetricsManager:
    """
    Gestisce metrics collection e timing tracking.

    Responsabilità:
    - Estrae timing da ReAct loop steps
    - Registra metrics Prometheus
    - Traccia token usage
    - Logging strutturato per analytics
    """

    def __init__(self):
        """Inizializza il metrics manager."""
        pass

    def extract_timings_from_state(
        self,
        state: AgentState,
        reasoning_duration: float,
        start_time: float,
    ) -> dict[str, float]:
        """
        Estrae timing dettagliati da AgentState steps.

        Analizza ogni step per estrarre:
        - Tool execution time
        - Search latency
        - LLM time (reasoning - tools)

        Args:
            state: AgentState con steps completati
            reasoning_duration: Durata totale del ReAct loop
            start_time: Timestamp di inizio query

        Returns:
            Dict con keys: total, search, tools, llm, reasoning
        """
        execution_time = time.time() - start_time

        timings = {
            "total": execution_time,
            "embedding": 0.0,
            "search": 0.0,
            "rerank": 0.0,
            "llm": 0.0,
            "reasoning": reasoning_duration,
        }

        # Extract REAL timings from tool execution_time
        # Each ToolCall now has execution_time populated by execute_tool()
        search_latency_accum = 0.0
        tool_latency_accum = 0.0

        for step in state.steps:
            if step.action:
                # Get real execution time from the tool call
                tool_time = getattr(step.action, "execution_time", 0.0)
                tool_latency_accum += tool_time

                if step.action.tool_name == "vector_search":
                    search_latency_accum += tool_time

        # Calculate timing breakdown
        timings["tools"] = tool_latency_accum
        if tool_latency_accum > 0:
            timings["search"] = search_latency_accum
            # LLM time = total reasoning time minus tool execution time
            timings["llm"] = max(0, reasoning_duration - tool_latency_accum)
        else:
            # No tools executed - all time was LLM
            timings["llm"] = reasoning_duration

        return timings

    def extract_collections_from_state(self, state: AgentState) -> set[str]:
        """
        Estrae collezioni usate dai tool calls.

        Args:
            state: AgentState con steps

        Returns:
            Set di collection names usate
        """
        collections_used = set()

        for step in state.steps:
            if step.action and step.action.tool_name == "vector_search":
                if step.action.arguments:
                    col = step.action.arguments.get("collection")
                    if col:
                        collections_used.add(col)

        return collections_used

    def extract_sources_from_state(self, state: AgentState) -> list[Any]:
        """
        Estrae sources da AgentState steps.

        Args:
            state: AgentState con steps

        Returns:
            Lista di sources (tool results)
        """
        if hasattr(state, "sources") and state.sources:
            return state.sources
        else:
            return [s.action.result for s in state.steps if s.action and s.action.result]

    def calculate_context_used(self, state: AgentState) -> int:
        """
        Calcola context tokens usati (sum di observation lengths).

        Args:
            state: AgentState con steps

        Returns:
            Numero approssimativo di token context usati
        """
        return sum(len(s.observation or "") for s in state.steps)

    def record_rag_metrics(
        self,
        state: AgentState,
        collections_used: set[str],
        tool_execution_count: int,
        context_used: int,
        execution_time: float,
        sources: list[Any],
    ) -> None:
        """
        Registra metrics Prometheus per RAG query.

        Args:
            state: AgentState completato
            collections_used: Set di collection names
            tool_execution_count: Numero di tool eseguiti
            context_used: Token context usati
            execution_time: Durata totale esecuzione
            sources: Lista di sources trovati
        """
        primary_collection = next(iter(collections_used), "unknown")
        route_used = "agentic" if tool_execution_count > 0 else "direct"
        evidence_score = getattr(state, "evidence_score", None) or 0.0

        # Record RAG query metrics
        metrics_collector.record_rag_query(
            collection=primary_collection,
            route_used=route_used,
            status="success",
            context_tokens=context_used,
        )

        # Record detailed histogram metrics
        metrics_collector.record_rag_detailed_metrics(
            duration_seconds=execution_time,
            evidence_score=evidence_score,
            documents_count=len(sources),
            collection=primary_collection,
            route_used=route_used,
        )

    def record_token_usage(
        self,
        model_used: str,
        token_usage: TokenUsage,
        endpoint: str = "chat",
    ) -> None:
        """
        Registra token usage metrics.

        Args:
            model_used: Nome modello usato
            token_usage: TokenUsage object con stats
            endpoint: Endpoint name per tagging
        """
        metrics_collector.record_llm_token_usage(
            model=model_used,
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            cost_usd=token_usage.cost_usd,
            endpoint=endpoint,
        )

    def log_query_completion(
        self,
        user_id: str | None,
        query: str,
        model_used: str,
        execution_time: float,
        state: AgentState,
        collections_used: set[str],
        tool_execution_count: int,
        token_usage: TokenUsage,
    ) -> None:
        """
        Log strutturato per query completion.

        Args:
            user_id: User ID
            query: Query originale
            model_used: Modello usato
            execution_time: Durata esecuzione
            state: AgentState completato
            collections_used: Collezioni usate
            tool_execution_count: Tool eseguiti
            token_usage: Token usage stats
        """
        evidence_score = getattr(state, "evidence_score", None) or 0.0
        sources = self.extract_sources_from_state(state)

        logger.info(
            "✅ [AgenticRAG] Query completed successfully",
            extra={
                "user_id": user_id or "anonymous",
                "query_hash": str(hash(query))[:8],
                "model_used": model_used,
                "duration_s": round(execution_time, 3),
                "evidence_score": round(evidence_score, 2),
                "doc_count": len(sources),
                "steps": len(state.steps),
                "tokens_total": token_usage.total_tokens,
                "cost_usd": round(token_usage.cost_usd, 6),
                "route": "agentic" if tool_execution_count > 0 else "direct",
                "tools": list(collections_used) if collections_used else [],
            },
        )
