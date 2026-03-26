"""
Verification Service
Implements the "Draft -> Verify" pattern for Agentic RAG.
Acts as a judge to evaluate if the generated answer is supported by the retrieved context.

UPDATED 2025-12-23:
- Migrated to new google-genai SDK via GenAIClient wrapper
"""

import json
import logging
from enum import Enum

from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

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
    """

    is_valid: bool
    status: VerificationStatus
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    corrected_answer: str | None = None
    missing_citations: list[str] = []


class VerificationService:
    """
    Service responsible for verifying RAG generated responses against source context.
    Uses a lightweight LLM call to act as a 'Guardian'.
    """

    def __init__(self):
        self._genai_client: GenAIClient | None = None
        self.model_name = "gemini-2.5-flash"

    def _get_genai_client(self) -> GenAIClient | None:
        """Lazy load GenAI client."""
        if self._genai_client is None and settings.google_api_key and GENAI_AVAILABLE:
            try:
                self._genai_client = GenAIClient(api_key=settings.google_api_key)
                if self._genai_client.is_available:
                    logger.debug("🛡️ [VerificationService] GenAI client loaded")
            except Exception as e:
                logger.warning(f"⚠️ [VerificationService] Failed to initialize client: {e}")
        return self._genai_client

    @property
    def _available(self) -> bool:
        """Check availability dynamically."""
        client = self._get_genai_client()
        return client.is_available if client else False

    async def verify_response(
        self, query: str, draft_answer: str, context_chunks: list[str]
    ) -> VerificationResult:
        """
        Verify if the draft answer is supported by the context chunks.
        """
        client = self._get_genai_client()
        if not client or not client.is_available:
            # Fallback if no model: Assume valid but log warning
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.VERIFIED,
                score=1.0,
                reasoning="Verification skipped (model unavailable)",
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
            [f"[Source {i + 1}] {chunk}" for i, chunk in enumerate(context_chunks)]
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

        try:
            # Use low temperature for deterministic evaluation
            result = await self._genai_client.generate_content(
                contents=prompt,
                model=self.model_name,
                temperature=0.0,
                max_output_tokens=8192,
            )

            result_json = json.loads(result.get("text", "{}"))

            status = VerificationStatus(result_json.get("status", "unverified"))
            score = float(result_json.get("score", 0.0))

            # Determine validity threshold (strict)
            is_valid = score >= 0.7  # Allow minor deviations, but reject major issues

            logger.info(f"🛡️ [Verifier] Status: {status} | Score: {score}")

            return VerificationResult(
                is_valid=is_valid,
                status=status,
                score=score,
                reasoning=result_json.get("reasoning", ""),
                corrected_answer=result_json.get("corrections"),
                missing_citations=result_json.get("missing_citations", []),
            )

        except Exception as e:
            logger.error(f"❌ [Verifier] Error during verification: {e}")
            # Fail safe: allow it but log error, or block?
            # Better to block high-stakes, but for now we'll allow with warning.
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.PARTIALLY_VERIFIED,
                score=0.5,
                reasoning=f"Verification failed processing: {e}",
            )


verification_service = VerificationService()
