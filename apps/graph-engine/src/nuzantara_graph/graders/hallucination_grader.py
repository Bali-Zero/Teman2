"""Hallucination grader — checks answer is grounded in retrieved sources.

Two-phase verification:
  1. Fast heuristic: keyword overlap ratio (no LLM cost)
  2. LLM verification: called only when heuristic score is borderline (0.5–0.8)
     to avoid false positives on well-written paraphrases.

Fail-fast at <0.2: answer is entirely fabricated — skip LLM, return FAIL immediately.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from nuzantara_graph.graders.base import BaseGrader
from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState

logger = structlog.get_logger()

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
  "unsupported_claims": [<list of strings — claims NOT found in sources>],
  "reasoning": "<one sentence>"
}}

Rules:
- 1.0 = every claim in the answer is directly supported by sources
- 0.0 = answer is completely fabricated / not in sources
- Be strict about numbers, prices, durations, and legal requirements
- Paraphrasing of source content counts as supported
"""

_COMMON_WORDS = {
    "about", "would", "could", "should", "their", "there", "these",
    "which", "where", "after", "before", "other", "because", "through",
    "between", "under", "untuk", "dalam", "dengan", "dapat", "harus",
    "yang", "dari", "this", "that", "have", "will", "from", "also",
}

# System-fallback sentinel prefixes. When an answer begins with one of
# these, it is an explicit escalation message produced by a fail-fast or
# planner fallback path — NOT a real answer that needs grounding. The
# grader short-circuits to a neutral PASS so downstream consumers see a
# clean decision instead of a fake 1.0 score (from keyword overlap on
# generic words like "cannot" and "rephrase") or a fake FAIL (from the
# no-sources-found branch).
_FALLBACK_PREFIXES = (
    "i cannot produce a fully-cited answer",
    "i apologize, but i was unable to generate",
    "i wasn't able to provide a reliable answer",
    "i couldn't find relevant information",
    "i found some information but couldn't put together",
)


def _is_system_fallback(answer: str) -> bool:
    """True if the answer is a known fallback/escalation message."""
    if not answer:
        return False
    normalized = answer.strip().lower()
    return any(normalized.startswith(prefix) for prefix in _FALLBACK_PREFIXES)


class HallucinationGrader(BaseGrader):
    grader_name = "hallucination"
    pass_threshold = 0.8  # stricter — hallucinations are dangerous
    fail_fast_threshold = 0.2

    def __init__(self, services: Services | None = None) -> None:
        self._services = services

    def _evaluate(self, state: GraphState) -> tuple[float, str, str]:
        """Heuristic evaluation — synchronous, no LLM call."""
        answer = state.answer
        docs = state.retrieved_documents
        kg_entities = state.kg_entities

        if not answer or not answer.strip():
            return 1.0, "No answer to check for hallucination", ""

        # System-fallback short-circuit: explicit escalation messages are
        # not real answers — they carry no factual claims, so there is
        # nothing to hallucinate. Record a neutral PASS with a clear
        # reason so downstream observability shows the decision was
        # intentional, not a heuristic fluke.
        if _is_system_fallback(answer):
            return 1.0, "System fallback / escalation message — no claims to verify", ""

        if not docs and not kg_entities:
            return 0.1, "No source material to verify answer against", ""

        answer_lower = answer.lower()
        source_texts = [d.content.lower() for d in docs]
        source_texts += [
            str(e.get("description", "")).lower() + " " + str(e.get("label", "")).lower()
            for e in kg_entities
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
        source_bonus = 0.1 if state.sources else 0.0
        score = min(1.0, grounding_ratio + source_bonus)

        if score < self.fail_fast_threshold:
            return score, f"Answer appears heavily hallucinated (grounding={grounding_ratio:.2f})", ""

        if score < self.pass_threshold:
            return score, f"Partial grounding (ratio={grounding_ratio:.2f}), some claims unverified", ""

        return score, f"Well-grounded answer (ratio={grounding_ratio:.2f})", ""


async def _llm_verify_grounding(
    state: GraphState,
    services: Services,
) -> float | None:
    """Call LLM to verify grounding when heuristic score is borderline.

    Returns refined score or None if LLM call fails.
    """
    answer = state.answer or ""
    docs = state.retrieved_documents or []

    # Truncate sources to avoid token overflow (keep most relevant)
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
        llm = services.llm_gateway
        response = await llm.generate(
            messages=[{"role": "user", "content": prompt}],
            model_override="gemini-2.0-flash",  # fast + cheap for grading
            max_tokens=256,
        )

        raw = response.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        score = float(data.get("grounding_score", 0.5))

        unsupported = data.get("unsupported_claims", [])
        if unsupported:
            logger.info(
                "hallucination_llm_unsupported_claims",
                count=len(unsupported),
                claims=unsupported[:3],
            )

        logger.debug(
            "hallucination_llm_verify",
            score=score,
            reasoning=data.get("reasoning", "")[:100],
        )
        return max(0.0, min(1.0, score))

    except Exception as e:
        logger.warning("hallucination_llm_verify_failed", error=str(e))
        return None


def make_hallucination_grader(services: Services | None = None):
    """Factory that creates a hallucination grader node with optional LLM verification."""
    grader = HallucinationGrader(services=services)

    async def hallucination_grader_node(state: GraphState) -> dict[str, Any]:
        # Phase 1: fast heuristic
        result = grader.grade(state)
        heuristic_score = result.score

        # Phase 2: LLM verification for borderline scores
        if (
            services is not None
            and _LLM_VERIFY_LOW <= heuristic_score <= _LLM_VERIFY_HIGH
        ):
            logger.debug(
                "hallucination_borderline_llm_check",
                heuristic_score=heuristic_score,
            )
            llm_score = await _llm_verify_grounding(state, services)
            if llm_score is not None:
                # Blend: LLM result takes priority (0.7 weight), heuristic as safety net
                blended = (llm_score * 0.7) + (heuristic_score * 0.3)
                # Re-run grader logic with blended score to get correct decision
                from nuzantara_schemas.grading import GradeDecision, GradeResult
                if blended >= grader.pass_threshold:
                    decision = GradeDecision.PASS
                    msg = f"LLM-verified grounding (score={blended:.2f})"
                elif blended < grader.fail_fast_threshold:
                    decision = GradeDecision.FAIL
                    msg = f"LLM confirmed hallucination (score={blended:.2f})"
                else:
                    decision = GradeDecision.RETRY
                    msg = f"LLM: partial grounding (score={blended:.2f}), retry"

                result = GradeResult(
                    grader=grader.grader_name,
                    score=blended,
                    decision=decision,
                    reason=msg,
                )
                logger.info(
                    "hallucination_llm_decision",
                    heuristic=heuristic_score,
                    llm=llm_score,
                    blended=blended,
                    decision=decision,
                )

        grades = list(state.grades) + [result]
        return {
            "grades": grades,
            "current_node": "grade_hallucination",
        }

    return hallucination_grader_node
