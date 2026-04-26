"""
Orchestrator Response Builder

Responsabilità singola: Response formatting e post-processing.
Include:
- CoreResult building da AgentState
- Response validation
- Verification status calculation
- Entity injection

Questo modulo è testabile in isolamento mockando AgentState.
"""

import logging
from typing import Any

from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.agentic.schema import CoreResult
from backend.services.tools.definitions import AgentState

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging for response building


class OrchestratorResponseBuilder:
    """
    Gestisce response formatting e post-processing.

    Responsabilità:
    - Costruisce CoreResult da AgentState
    - Calcola verification status
    - Inietta entities e metadata
    - Valida response structure
    """

    def __init__(self, entity_extractor: EntityExtractionService | None = None) -> None:
        """
        Inizializza il response builder.

        Args:
            entity_extractor: Optional entity extractor per entity injection
        """
        self.entity_extractor = entity_extractor

    def build_core_result(
        self,
        state: AgentState,
        sources: list[Any],
        extracted_entities: dict[str, Any],
        model_used: str,
        token_usage: Any,  # TokenUsage
        timings: dict[str, float],
        start_time: float,
        workflow: dict | None = None,
        reasoning: str | None = None,
    ) -> CoreResult:
        """
        Costruisce CoreResult da AgentState e metadata.

        Args:
            state: AgentState completato
            sources: Lista di sources trovati
            extracted_entities: Entities estratte dalla query
            model_used: Nome modello usato
            token_usage: TokenUsage object
            timings: Dict con timing breakdown
            start_time: Timestamp di inizio
            workflow: Optional KG LangGraph workflow dict
            reasoning: Optional reasoning chain from KG LangGraph

        Returns:
            CoreResult completo
        """
        from backend.app.core.constants import EvidenceScoreConstants
        from backend.services.rag.agentic.reasoning_utils import (
            get_abstain_threshold,
        )

        timings.get("total", 0.0)
        verification_score = getattr(state, "verification_score", 0.0)
        evidence_score = getattr(state, "evidence_score", None) or 0.0

        # Determine if this is an ABSTAIN response.
        # v3 quick-win #2: per-domain threshold (tax/visa lower, KBLI higher)
        # so over-rejection on Indonesian tax/visa queries goes away while
        # KBLI false-positives (business-vocabulary collisions) get filtered
        # out more aggressively. Falls back to the legacy global 0.15 when
        # the domain classifier returns "default".
        query_str = getattr(state, "query", "") or ""
        abstain_threshold = get_abstain_threshold(query_str)
        abstain = evidence_score < abstain_threshold

        abstain_reason = None
        if abstain:
            if evidence_score < 0.05:
                abstain_reason = "no_relevant_context"
            elif evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD:
                abstain_reason = "low_confidence"
            else:
                # New bucket: above legacy 0.15 but below domain-specific cutoff
                abstain_reason = "below_domain_threshold"

        if abstain_threshold != EvidenceScoreConstants.ABSTAIN_THRESHOLD:
            logger.debug(
                "abstain_gate: query=%r domain_threshold=%.2f score=%.2f abstain=%s",
                query_str[:60], abstain_threshold, evidence_score, abstain,
            )

        return CoreResult(
            answer=state.final_answer,
            sources=sources,
            verification_score=verification_score,
            evidence_score=evidence_score,
            abstain=abstain,
            abstain_reason=abstain_reason,
            is_ambiguous=False,
            entities=extracted_entities,
            model_used=model_used,
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            total_tokens=token_usage.total_tokens,
            cost_usd=token_usage.cost_usd,
            verification_status="passed" if verification_score > 0.7 else "unchecked",
            document_count=len(sources),
            timings=timings,
            warnings=[],
            workflow=workflow,
            reasoning=reasoning,
        )

    def build_gate_response(
        self,
        answer: str,
        model_used: str,
        verification_score: float = 1.0,
        evidence_score: float = 1.0,
        verification_status: str = "passed",
        entities: dict[str, Any] | None = None,
        start_time: float | None = None,
    ) -> CoreResult:
        """
        Costruisce CoreResult per gate responses (greeting, identity, etc.).

        Args:
            answer: Risposta testuale
            model_used: Nome modello/gate usato
            verification_score: Verification score (default 1.0 per trusted gates)
            evidence_score: Evidence score (default 1.0 per trusted gates)
            verification_status: Status verification
            entities: Optional entities
            start_time: Timestamp di inizio (per timing)

        Returns:
            CoreResult per gate response
        """
        import time

        execution_time = (time.time() - start_time) if start_time else 0.0

        return CoreResult(
            answer=answer,
            sources=[],
            verification_score=verification_score,
            evidence_score=evidence_score,
            is_ambiguous=False,
            entities=entities or {},
            model_used=model_used,
            timings={"total": execution_time},
            verification_status=verification_status,
            document_count=0,
        )

    def build_clarification_response(
        self,
        clarification_msg: str,
        ambiguity_info: dict[str, Any],
        start_time: float,
    ) -> CoreResult:
        """
        Costruisce CoreResult per clarification requests.

        Args:
            clarification_msg: Messaggio di chiarimento
            ambiguity_info: Info su ambiguità rilevata
            start_time: Timestamp di inizio

        Returns:
            CoreResult per clarification
        """
        import time

        execution_time = time.time() - start_time

        return CoreResult(
            answer=clarification_msg,
            sources=[],
            verification_score=0.0,
            evidence_score=0.0,
            is_ambiguous=True,
            clarification_question=clarification_msg,
            entities=ambiguity_info.get("entities", {}),
            model_used="clarification-gate",
            timings={"total": execution_time},
            verification_status="skipped",
            document_count=0,
        )

    def build_out_of_domain_response(
        self,
        answer_text: str,
        reason: str,
        start_time: float,
    ) -> CoreResult:
        """
        Costruisce CoreResult per out-of-domain queries.

        Args:
            answer_text: Risposta per out-of-domain
            reason: Ragione del blocco
            start_time: Timestamp di inizio

        Returns:
            CoreResult per out-of-domain
        """
        import time

        execution_time = time.time() - start_time

        return CoreResult(
            answer=answer_text,
            sources=[],
            verification_score=0.0,
            evidence_score=0.0,
            is_ambiguous=False,
            entities={},
            model_used=f"out-of-domain-{reason}",
            timings={"total": execution_time},
            verification_status="blocked",
            document_count=0,
            warnings=[f"Query blocked: {reason}"],
        )
