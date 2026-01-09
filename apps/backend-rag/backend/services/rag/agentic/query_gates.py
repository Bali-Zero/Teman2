"""
Query Gates for Agentic RAG Orchestrator

Pre-processing gates that can bypass the full RAG pipeline:
- Security gate (prompt injection detection)
- Greeting gate (simple greetings)
- Casual conversation gate
- Identity gate (hardcoded responses)
- Out-of-domain gate
- Clarification gate (ambiguous queries)

These gates are applied BEFORE the expensive RAG processing to save
compute resources and improve response latency.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from services.misc.clarification_service import ClarificationService
from services.response.cleaner import OUT_OF_DOMAIN_RESPONSES, is_out_of_domain

from .prompt_builder import SystemPromptBuilder
from .schema import CoreResult

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result from a query gate check."""

    triggered: bool
    response: str | None = None
    gate_name: str | None = None
    metadata: dict[str, Any] | None = None


class QueryGates:
    """
    Collection of pre-processing gates for query handling.

    Each gate can short-circuit the RAG pipeline by returning
    a direct response when appropriate.
    """

    def __init__(
        self,
        prompt_builder: SystemPromptBuilder,
        clarification_service: ClarificationService | None = None,
    ):
        """
        Initialize QueryGates.

        Args:
            prompt_builder: SystemPromptBuilder for pattern detection
            clarification_service: Optional ClarificationService for ambiguity detection
        """
        self.prompt_builder = prompt_builder
        self.clarification_service = clarification_service

    def check_security_gate(self, query: str) -> GateResult:
        """
        SECURITY GATE: Detect and block prompt injection attempts.

        Must be the FIRST gate checked to prevent security bypasses.

        Args:
            query: User's query

        Returns:
            GateResult with triggered=True if injection detected
        """
        is_injection, injection_response = self.prompt_builder.detect_prompt_injection(query)
        if is_injection:
            logger.warning("Blocked prompt injection/off-topic request")
            return GateResult(
                triggered=True,
                response=injection_response,
                gate_name="security",
                metadata={"reason": "prompt_injection"},
            )
        return GateResult(triggered=False)

    def check_greeting_gate(self, query: str, user_context: dict[str, Any]) -> GateResult:
        """
        GREETING GATE: Handle simple greetings without RAG.

        Args:
            query: User's query
            user_context: User context for personalization

        Returns:
            GateResult with greeting response if triggered
        """
        greeting_response = self.prompt_builder.check_greetings(query, context=user_context)
        if greeting_response:
            logger.info("Returning direct greeting response (skipping RAG)")
            return GateResult(
                triggered=True,
                response=greeting_response,
                gate_name="greeting",
            )
        return GateResult(triggered=False)

    def check_casual_gate(self, query: str, user_context: dict[str, Any]) -> GateResult:
        """
        CASUAL GATE: Handle casual conversation without RAG.

        Examples: "come stai", "how are you", etc.

        Args:
            query: User's query
            user_context: User context for personalization

        Returns:
            GateResult with casual response if triggered
        """
        casual_response = self.prompt_builder.get_casual_response(query, context=user_context)
        if casual_response:
            logger.info("Returning direct casual response (skipping RAG)")
            return GateResult(
                triggered=True,
                response=casual_response,
                gate_name="casual",
            )
        return GateResult(triggered=False)

    def check_identity_gate(self, query: str, user_context: dict[str, Any]) -> GateResult:
        """
        IDENTITY GATE: Handle hardcoded identity questions.

        Examples: "chi sei", "what is your name", etc.

        Args:
            query: User's query
            user_context: User context

        Returns:
            GateResult with identity response if triggered
        """
        identity_response = self.prompt_builder.check_identity_questions(
            query, context=user_context
        )
        if identity_response:
            logger.info("Returning hardcoded identity response")
            return GateResult(
                triggered=True,
                response=identity_response,
                gate_name="identity",
            )
        return GateResult(triggered=False)

    def check_out_of_domain_gate(self, query: str) -> GateResult:
        """
        OUT-OF-DOMAIN GATE: Block queries outside business scope.

        Args:
            query: User's query

        Returns:
            GateResult with rejection response if out of domain
        """
        out_of_domain, reason = is_out_of_domain(query)
        if out_of_domain and reason:
            logger.info(f"Query rejected as out-of-domain: {reason}")
            answer_text = OUT_OF_DOMAIN_RESPONSES.get(reason, OUT_OF_DOMAIN_RESPONSES["unknown"])
            return GateResult(
                triggered=True,
                response=answer_text,
                gate_name="out_of_domain",
                metadata={"reason": reason},
            )
        return GateResult(triggered=False)

    def check_clarification_gate(
        self, query: str, conversation_history: list[dict], confidence_threshold: float = 0.6
    ) -> GateResult:
        """
        CLARIFICATION GATE: Detect ambiguous queries needing clarification.

        Args:
            query: User's query
            conversation_history: Previous conversation messages
            confidence_threshold: Minimum confidence to trigger clarification

        Returns:
            GateResult with clarification question if ambiguous
        """
        if not self.clarification_service:
            return GateResult(triggered=False)

        ambiguity_info = self.clarification_service.detect_ambiguity(
            query, conversation_history
        )

        if (
            ambiguity_info["is_ambiguous"]
            and ambiguity_info["confidence"] > confidence_threshold
            and ambiguity_info["clarification_needed"]
        ):
            logger.info(f"Stopped ambiguous query: {ambiguity_info['reasons']}")
            clarification_msg = self.clarification_service.generate_clarification_request(
                query, ambiguity_info
            )
            return GateResult(
                triggered=True,
                response=clarification_msg,
                gate_name="clarification",
                metadata={
                    "is_ambiguous": True,
                    "confidence": ambiguity_info["confidence"],
                    "reasons": ambiguity_info["reasons"],
                    "entities": ambiguity_info.get("entities", {}),
                },
            )

        return GateResult(triggered=False)

    def run_all_gates(
        self,
        query: str,
        user_context: dict[str, Any],
        conversation_history: list[dict] | None = None,
    ) -> GateResult:
        """
        Run all gates in order and return the first triggered result.

        Gate order (security first):
        1. Security gate (prompt injection)
        2. Greeting gate
        3. Casual gate
        4. Identity gate
        5. Clarification gate
        6. Out-of-domain gate

        Args:
            query: User's query
            user_context: User context dict
            conversation_history: Optional conversation history

        Returns:
            First triggered GateResult, or GateResult(triggered=False)
        """
        # 1. Security gate (MUST be first)
        result = self.check_security_gate(query)
        if result.triggered:
            return result

        # 2. Greeting gate
        result = self.check_greeting_gate(query, user_context)
        if result.triggered:
            return result

        # 3. Casual gate
        result = self.check_casual_gate(query, user_context)
        if result.triggered:
            return result

        # 4. Identity gate
        result = self.check_identity_gate(query, user_context)
        if result.triggered:
            return result

        # 5. Clarification gate
        if conversation_history:
            result = self.check_clarification_gate(query, conversation_history)
            if result.triggered:
                return result

        # 6. Out-of-domain gate
        result = self.check_out_of_domain_gate(query)
        if result.triggered:
            return result

        return GateResult(triggered=False)

    def gate_result_to_core_result(
        self, gate_result: GateResult, start_time: float
    ) -> CoreResult:
        """
        Convert a triggered GateResult to a CoreResult.

        Args:
            gate_result: The triggered gate result
            start_time: Query start time for timing calculation

        Returns:
            CoreResult with appropriate values for the gate type
        """
        verification_status = "passed"
        if gate_result.gate_name in ("security", "out_of_domain"):
            verification_status = "blocked"
        elif gate_result.gate_name == "clarification":
            verification_status = "skipped"

        return CoreResult(
            answer=gate_result.response or "",
            sources=[],
            verification_score=1.0 if gate_result.gate_name not in ("security", "out_of_domain") else 0.0,
            evidence_score=1.0 if gate_result.gate_name not in ("security", "out_of_domain", "clarification") else 0.0,
            is_ambiguous=gate_result.gate_name == "clarification",
            clarification_question=gate_result.response if gate_result.gate_name == "clarification" else None,
            entities=gate_result.metadata.get("entities", {}) if gate_result.metadata else {},
            model_used=f"{gate_result.gate_name}-gate",
            timings={"total": time.time() - start_time},
            verification_status=verification_status,
            document_count=0,
            warnings=[f"Query blocked: {gate_result.metadata.get('reason', 'unknown')}"]
            if gate_result.gate_name in ("security", "out_of_domain")
            else [],
        )
