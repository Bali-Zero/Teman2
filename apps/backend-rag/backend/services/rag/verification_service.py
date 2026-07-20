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


class VerificationService:
    """
    Service responsible for verifying RAG generated responses against source context.
    Uses a lightweight LLM call to act as a 'Guardian'.
    """

    def __init__(self) -> None:
        self._genai_client: GenAIClient | None = None
        self.model_name = "gemini-3.5-flash"

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

        try:
            # Use low temperature for deterministic evaluation
            result = await self._genai_client.generate_content(
                contents=prompt,
                model=self.model_name,
                temperature=0.0,
                max_output_tokens=8192,
            )

            # Gemini can return an EMPTY string for `text` (safety block or
            # content filter). The `"{}"` default on .get() only applies when
            # the key is MISSING, not when its value is "" — json.loads("")
            # raises, which used to fall through to the blanket except below
            # and mint a fake score=0.5. Downstream (reasoning.py) treated
            # that fake 0.5 as a real "half-supported" verdict and triggered
            # a wasted self-correction round-trip (rephrase LLM call, then
            # re-verify — same empty-response bug, ~23s wasted on a query
            # that was correct the first time). Guard explicitly so callers
            # can tell "no verdict" from "verdict genuinely says 0.5".
            text = (result.get("text") or "").strip()
            if not text:
                logger.warning(
                    "🛡️ [Verifier] LLM returned empty response "
                    "(possible safety block or content filter) — "
                    "verdict unavailable, passing through",
                )
                return VerificationResult(
                    is_valid=True,
                    status=VerificationStatus.PARTIALLY_VERIFIED,
                    score=0.5,
                    reasoning="Verifier LLM returned an empty response. Verdict unavailable.",
                    verdict_available=False,
                )

            result_json = json.loads(text)

            status = VerificationStatus(result_json.get("status", "unverified"))
            score = float(result_json.get("score", 0.0))

            # Determine validity threshold (strict)
            is_valid = score >= 0.7  # Allow minor deviations, but reject major issues

            logger.info("🛡️ [Verifier] Status: %s | Score: %s", status, score)

            return VerificationResult(
                is_valid=is_valid,
                status=status,
                score=score,
                reasoning=result_json.get("reasoning", ""),
                corrected_answer=result_json.get("corrections"),
                missing_citations=result_json.get("missing_citations", []),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Verdict could not be parsed (malformed JSON / invalid status
            # enum / missing key). Never a real verdict — never let it gate
            # self-correction downstream.
            logger.warning("🛡️ [Verifier] Could not parse verifier verdict: %s", e)
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.PARTIALLY_VERIFIED,
                score=0.5,
                reasoning=f"Verifier verdict could not be parsed: {e}",
                verdict_available=False,
            )

        except Exception as e:
            # Unexpected error (network, API, etc.). Fail safe: allow it but
            # log error — and, same as above, never let the placeholder
            # score gate self-correction.
            logger.error("❌ [Verifier] Error during verification: %s", e)
            return VerificationResult(
                is_valid=True,
                status=VerificationStatus.PARTIALLY_VERIFIED,
                score=0.5,
                reasoning=f"Verification failed processing: {e}",
                verdict_available=False,
            )


verification_service = VerificationService()
