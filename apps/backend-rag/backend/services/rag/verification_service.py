"""
Verification Service
Implements the "Draft -> Verify" pattern for Agentic RAG.
Acts as a judge to evaluate if the generated answer is supported by the retrieved context.

UPDATED 2025-12-23:
- Migrated to new google-genai SDK via GenAIClient wrapper
"""

import logging
import os
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient, LLMStructuredOutputError

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """
    Verification status for RAG-generated responses.

    Attributes:
        VERIFIED: Response is fully supported by retrieved context.
        PARTIALLY_VERIFIED: Mostly supported with minor unsupported claims.
        UNVERIFIED: Not supported or contradicts the context.
        HALLUCINATION: Clear fabrication with no basis in context.
    """

    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partial"
    UNVERIFIED = "unverified"
    HALLUCINATION = "hallucination"


class VerificationResult(BaseModel):
    """
    Result of response verification against source context.

    Attributes:
        is_valid: Whether the response passes verification.
        status: Detailed verification status.
        score: Confidence score from 0.0 to 1.0.
        reasoning: Explanation of the verification decision.
        corrected_answer: Suggested correction if verification failed.
        missing_citations: List of claims that lack source citations.
        verdict_available: False when the LLM judge never produced a real
            verdict (empty response, unparseable JSON, or an unexpected
            error) — `score`/`status` in that case are a placeholder, not
            a real judgment, and MUST NOT gate self-correction downstream.
    """

    is_valid: bool
    status: VerificationStatus
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    corrected_answer: str | None = None
    missing_citations: list[str] = []
    verdict_available: bool = True


class VerifierVerdict(BaseModel):
    """Schema the verifier LLM is constrained to via generate_structured()'s
    response_schema (JSON mode — response_mime_type="application/json",
    no markdown fence, ever; PR #311 convention: `reasoning` FIRST forces
    think-before-commit).

    `status`/`score` are bounded here (round-2 red-team fix, Codex): an
    unconstrained schema let a malformed model output (e.g. score=1.2, or
    a status value outside VerificationStatus) pass generate_structured()
    cleanly, then blow up VerificationResult's own Field(ge=0.0, le=1.0)
    UNCAUGHT in the mapping step below (outside the try/except). Bounding
    it here means generate_structured()'s own model_validate_json +
    one-retry catches it first, surfacing as the already-handled
    LLMStructuredOutputError instead. `status` values must equal
    VerificationStatus's `.value`s 1:1 (see the try/except right below the
    call site, which still maps VerificationStatus(verdict.status))."""

    reasoning: str
    status: Literal["verified", "partial", "unverified", "hallucination"]
    score: float = Field(ge=0.0, le=1.0)
    corrections: str | None = None
    missing_citations: list[str] = []


class VerificationService:
    """
    Service responsible for verifying RAG generated responses against source context.
    Uses a lightweight LLM call to act as a 'Guardian'.
    """

    def __init__(self) -> None:
        self._genai_client: GenAIClient | None = None
        # Default = the model this service has always used. Flipping via env
        # is a deploy-time lever (increment-2, evidence-gated by
        # scripts/verifier_model_ab.py) — default behavior is UNCHANGED.
        self.model_name = os.getenv("VERIFIER_MODEL", "gemini-3.5-flash")
        logger.info("🛡️ [VerificationService] verifier model: %s", self.model_name)

    def _get_genai_client(self) -> GenAIClient | None:
        """Lazy load GenAI client."""
        if self._genai_client is None and settings.google_api_key and GENAI_AVAILABLE:
            try:
                self._genai_client = GenAIClient(api_key=settings.google_api_key)
                if self._genai_client.is_available:
                    logger.debug("🛡️ [VerificationService] GenAI client loaded")
            except Exception as e:
                logger.warning("⚠️ [VerificationService] Failed to initialize client: %s", e)
        return self._genai_client

    @property
    def _available(self) -> bool:
        """Check availability dynamically."""
        client = self._get_genai_client()
        return client.is_available if client else False

    async def verify_response(
        self,
        query: str,
        draft_answer: str,
        context_chunks: list[str],
    ) -> VerificationResult:
        """
        Verify if the draft answer is supported by the context chunks.
        """
        client = self._get_genai_client()
        if not client or not client.is_available:
            # No verdict path, same as the others below (round-2 red-team
            # fix, Codex): this used to mint a false "verified"
            # (score=1.0, verdict_available defaulting True) when the
            # verifier itself was dead — never let a no-verdict case look
            # like a real judgment.
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.PARTIALLY_VERIFIED,
                score=0.5,
                reasoning="Verification skipped (model unavailable) — verdict unavailable.",
                verdict_available=False,
            )

        if not context_chunks:
            # If no context but answer claims facts, it's risky.
            # However, for general chit-chat it might be fine.
            # We'll rely on the agent to not act without context.
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.PARTIALLY_VERIFIED,
                score=0.5,
                reasoning="No context provided for verification.",
            )

        # Prepare context text
        context_text = "\n\n".join(
            [f"[Source {i + 1}] {chunk}" for i, chunk in enumerate(context_chunks)],
        )

        # Prompt for the verifier
        prompt = f"""
### VERIFICATION TASK
You are an expert Fact Checker for a Legal/Business AI Assistant.
Your job is to verify if the DRAFT ANSWER is fully supported by the RETRIEVED CONTEXT.

**USER QUERY:**
{query}

**RETRIEVED CONTEXT:**
{context_text}

**DRAFT ANSWER:**
{draft_answer}

### INSTRUCTIONS
1. Analyze if every claim in the Draft Answer is supported by the Context.
2. Check for Hallucinations (invented laws, wrong numbers, fake requirements).
3. Ignore stylistic differences, focus on FACTS.
4. If the answer mentions specific regulations/laws, they MUST be in the context.

### OUTPUT FORMAT
Return a JSON object with this exact structure:
{{
    "status": "verified" | "partial" | "unverified" | "hallucination",
    "score": 0.0 to 1.0,
    "reasoning": "Brief explanation of findings",
    "corrections": "If needed, specific corrections based ONLY on context",
    "missing_citations": ["List of claims not found in context"]
}}
"""

        # Use low temperature for deterministic evaluation.
        # Verdict JSON (status/score/reasoning/corrections/missing_citations)
        # is small — 8192 was a leftover generation-sized cap for a
        # judge-sized output. Trimmed to 2048 (increment-1, latency): a
        # representative sample verdict on this exact prompt schema
        # measured ~95 output tokens (see scripts/verifier_model_ab.py /
        # self-correction-speed-design.md validation note), leaving ~20x
        # headroom. generate_structured() (PR #311) forces JSON mode
        # (response_mime_type="application/json" + response_schema) — the
        # model can no longer wrap its verdict in a markdown ```json fence,
        # which is what silently killed the fact-check gate in prod (the
        # fence made json.loads() raise, minting a fake score=0.5 that
        # reasoning.py's self-correction gate treated as a real verdict).
        # Failure mode if the model still can't produce schema-valid JSON
        # (after generate_structured's own one retry) is safe-by-design:
        # LLMStructuredOutputError, caught below as verdict_available=False
        # — never a corrupted verdict silently gating downstream behavior.
        try:
            verdict = await self._genai_client.generate_structured(
                contents=prompt,
                response_schema=VerifierVerdict,
                model=self.model_name,
                temperature=0.0,
                max_output_tokens=2048,
                endpoint="rag.verifier",
            )
        except LLMStructuredOutputError:
            # PII boundary (round-2 red-team fix, Codex — UU PDP /
            # SYMBIOSIS Law 2 is ABSOLUTE): LLMStructuredOutputError's
            # message embeds pydantic ValidationError's str(), which
            # includes input_value=... — the model's malformed output,
            # which can itself echo client PII from the verifier prompt
            # (draft_answer/context_chunks). Never log or store the raw
            # exception text.
            logger.warning(
                "🛡️ [Verifier] Model failed to produce a schema-valid verdict "
                "— verdict unavailable",
            )
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.PARTIALLY_VERIFIED,
                score=0.5,
                reasoning="Verifier verdict unavailable (schema validation failed).",
                verdict_available=False,
            )
        except Exception as e:
            # Unexpected error (network, API, etc.). Fail safe: allow it but
            # log error — and, same as above, never let the placeholder
            # score gate self-correction. Same PII boundary as above: log
            # the exception TYPE only, never str(e).
            logger.error("❌ [Verifier] Error during verification: %s", type(e).__name__)
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.PARTIALLY_VERIFIED,
                score=0.5,
                reasoning="Verification failed processing (unexpected error).",
                verdict_available=False,
            )

        try:
            status = VerificationStatus(verdict.status)
        except ValueError:
            status = VerificationStatus.UNVERIFIED
        score = float(verdict.score)

        # Determine validity threshold (strict)
        is_valid = score >= 0.7  # Allow minor deviations, but reject major issues

        logger.info("🛡️ [Verifier] Status: %s | Score: %s", status, score)

        return VerificationResult(
            is_valid=is_valid,
            status=status,
            score=score,
            reasoning=verdict.reasoning,
            corrected_answer=verdict.corrections,
            missing_citations=verdict.missing_citations,
        )


verification_service = VerificationService()
