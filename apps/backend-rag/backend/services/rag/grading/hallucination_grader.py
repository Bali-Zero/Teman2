"""Hallucination grader — checks answer is grounded in retrieved sources.

Two-phase verification:
  1. Fast heuristic: keyword overlap ratio (no LLM cost)
  2. LLM verification: called only when heuristic score is borderline (0.5-0.8)
     to avoid false positives on well-written paraphrases.

Fail-fast at <0.2: answer is entirely fabricated.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.rag.grading.base import BaseGrader
from backend.services.rag.grading.context import GradingContext
from backend.services.rag.grading.schemas import GradeDecision, GradeResult

logger = logging.getLogger(__name__)

# Score band where LLM verification is worth the cost
_LLM_VERIFY_LOW = 0.50
_LLM_VERIFY_HIGH = 0.80

_HALLUCINATION_PROMPT = """\
You are a strict factual grounding checker.

TASK: Determine if the ANSWER is fully supported by the SOURCE MATERIAL.
Look for claims, numbers, names, prices, and legal terms that appear in the answer
but are NOT present in the sources.

SOURCE MATERIAL:
{sources}

ANSWER TO CHECK:
{answer}

Respond ONLY with a JSON object:
{{
  "grounding_score": <float 0.0 to 1.0>,
  "unsupported_claims": [<list of strings>],
  "reasoning": "<one sentence>"
}}

Rules:
- 1.0 = every claim in the answer is directly supported by sources
- 0.0 = answer is completely fabricated / not in sources
- Be strict about numbers, prices, durations, and legal requirements
- Paraphrasing of source content counts as supported
"""

_COMMON_WORDS = frozenset({
    "about", "would", "could", "should", "their", "there", "these",
    "which", "where", "after", "before", "other", "because", "through",
    "between", "under", "untuk", "dalam", "dengan", "dapat", "harus",
    "yang", "dari", "this", "that", "have", "will", "from", "also",
})


class HallucinationGrader(BaseGrader):
    """Synchronous heuristic hallucination grader.

    For LLM-verified grading, use `grade_with_llm_verification()`.
    """

    grader_name = "hallucination"
    pass_threshold = 0.8  # stricter — hallucinations are dangerous
    fail_fast_threshold = 0.2

    def _evaluate(self, ctx: GradingContext) -> tuple[float, str, str]:
        """Heuristic evaluation — synchronous, no LLM call."""
        answer = ctx.answer

        if not answer or not answer.strip():
            return 1.0, "No answer to check for hallucination", ""

        if not ctx.retrieved_documents and not ctx.kg_entities:
            return 0.1, "No source material to verify answer against", ""

        answer_lower = answer.lower()
        source_texts = [d.content.lower() for d in ctx.retrieved_documents]
        source_texts += [
            str(e.get("description", "")).lower() + " " + str(e.get("label", "")).lower()
            for e in ctx.kg_entities
        ]
        all_source_text = " ".join(source_texts)

        answer_terms = {
            w for w in answer_lower.split()
            if len(w) > 4 and w not in _COMMON_WORDS
        }

        if not answer_terms:
            return 0.5, "Could not extract meaningful terms from answer", ""

        grounded_terms = sum(1 for t in answer_terms if t in all_source_text)
        grounding_ratio = grounded_terms / len(answer_terms)
        source_bonus = 0.1 if ctx.sources else 0.0
        score = min(1.0, grounding_ratio + source_bonus)

        if score < self.fail_fast_threshold:
            return score, f"Answer appears heavily hallucinated (grounding={grounding_ratio:.2f})", ""

        if score < self.pass_threshold:
            return score, f"Partial grounding (ratio={grounding_ratio:.2f}), some claims unverified", ""

        return score, f"Well-grounded answer (ratio={grounding_ratio:.2f})", ""


async def llm_verify_grounding(
    ctx: GradingContext,
    llm_gateway: Any,
) -> float | None:
    """Call LLM to verify grounding when heuristic score is borderline.

    Args:
        ctx: Grading context with answer and documents
        llm_gateway: LLMGateway instance with generate() method

    Returns:
        Refined score or None if LLM call fails.
    """
    answer = ctx.answer or ""
    docs = ctx.retrieved_documents or []

    # Truncate sources to avoid token overflow
    source_snippets = "\n\n---\n\n".join(
        d.content[:500] for d in docs[:5]
    )
    if not source_snippets:
        return None

    prompt = _HALLUCINATION_PROMPT.format(
        sources=source_snippets,
        answer=answer[:1500],
    )

    try:
        response = await llm_gateway.generate(
            messages=[{"role": "user", "content": prompt}],
            model_override="gemini-2.0-flash",
            max_tokens=256,
        )

        raw = response.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        score = float(data.get("grounding_score", 0.5))

        unsupported = data.get("unsupported_claims", [])
        if unsupported:
            logger.info(
                "hallucination_llm_unsupported_claims count=%d claims=%s",
                len(unsupported),
                unsupported[:3],
            )

        return max(0.0, min(1.0, score))

    except Exception as e:
        logger.warning("hallucination_llm_verify_failed: %s", e)
        return None


async def grade_with_llm_verification(
    ctx: GradingContext,
    llm_gateway: Any | None = None,
) -> GradeResult:
    """Full 2-phase hallucination grading: heuristic + optional LLM verification.

    Args:
        ctx: Grading context
        llm_gateway: Optional LLM gateway for phase 2 verification

    Returns:
        GradeResult with final decision
    """
    grader = HallucinationGrader()
    result = grader.grade(ctx)
    heuristic_score = result.score

    # Phase 2: LLM verification for borderline scores
    if (
        llm_gateway is not None
        and _LLM_VERIFY_LOW <= heuristic_score <= _LLM_VERIFY_HIGH
    ):
        logger.debug(
            "hallucination_borderline_llm_check heuristic_score=%.2f",
            heuristic_score,
        )
        llm_score = await llm_verify_grounding(ctx, llm_gateway)
        if llm_score is not None:
            # Blend: LLM result takes priority (0.7), heuristic as safety net (0.3)
            blended = (llm_score * 0.7) + (heuristic_score * 0.3)

            retry_hint = ""
            if blended >= grader.pass_threshold:
                decision = GradeDecision.PASS
                msg = f"LLM-verified grounding (score={blended:.2f})"
            elif blended < grader.fail_fast_threshold:
                decision = GradeDecision.FAIL
                msg = f"LLM confirmed hallucination (score={blended:.2f})"
            else:
                decision = GradeDecision.RETRY
                msg = f"LLM: partial grounding (score={blended:.2f}), retry"
                retry_hint = "Rephrase answer to stay closer to source material"

            result = GradeResult(
                grader=grader.grader_name,
                score=blended,
                decision=decision,
                reason=msg,
                retry_hint=retry_hint,
            )
            logger.info(
                "hallucination_llm_decision heuristic=%.2f llm=%.2f blended=%.2f decision=%s",
                heuristic_score,
                llm_score,
                blended,
                decision,
            )

    return result
