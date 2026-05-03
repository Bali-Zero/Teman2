"""
Consiglio v1 — Consensus scoring.

Two-tier scoring:
1. Primary: LLM-as-Judge via Ollama (semantically meaningful, CLI-only)
2. Fallback: Jaccard similarity (zero dependencies)

Why NOT embedding cosine:
- SYMBIOSIS Law 1 prohibits HTTP API to OpenAI (text-embedding-3-small)
- LLM-as-Judge is semantically meaningful AND CLI-only compliant
"""
from __future__ import annotations

import asyncio
import itertools
import logging
import re
import subprocess
from statistics import mean

from mata_garuda.council.models import AgentVote, ConsensusResult
from mata_garuda.council.prompts import CONSENSUS_JUDGE_PROMPT

logger = logging.getLogger("mata_garuda.council.consensus")

# Groupthink detection thresholds (tunable)
GROUPTHINK_CONSENSUS_THRESHOLD = 0.85
GROUPTHINK_TIME_THRESHOLD_S = 30.0

# Stopwords for Jaccard (minimal, English-only)
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "and", "or", "but", "if", "then", "else", "when", "at", "by", "for",
    "with", "about", "against", "between", "through", "during", "before",
    "after", "above", "below", "to", "from", "in", "on", "of", "not",
    "no", "it", "its", "this", "that", "these", "those", "i", "we", "you",
    "he", "she", "they", "me", "us", "him", "her", "them", "my", "our",
    "your", "his", "their",
})


async def score_consensus(
    votes: list[AgentVote],
    judge_model: str = "gemma4:26b",
    judge_timeout: int = 30,
) -> ConsensusResult:
    """Score pairwise consensus between agent votes.

    Tries LLM-as-judge first, falls back to Jaccard on failure.
    """
    if len(votes) < 2:
        return ConsensusResult(
            score=1.0 if len(votes) == 1 else 0.0,
            method="jaccard",
            avg_response_time=votes[0].elapsed_seconds if votes else 0.0,
        )

    pairs = list(itertools.combinations(votes, 2))
    avg_time = mean(v.elapsed_seconds for v in votes)

    # Try LLM-as-judge
    try:
        pairwise = await _score_llm_judge(pairs, judge_model, judge_timeout)
        overall = mean(pairwise.values()) if pairwise else 0.0
        groupthink, reason = _detect_groupthink(overall, avg_time, votes)
        return ConsensusResult(
            score=round(overall, 3),
            method="llm_judge",
            pairwise_scores=pairwise,
            avg_response_time=round(avg_time, 2),
            groupthink_detected=groupthink,
            groupthink_reason=reason,
        )
    except Exception as e:
        logger.warning(f"[consensus] LLM judge failed, falling back to Jaccard: {e}")

    # Fallback: Jaccard
    pairwise = _score_jaccard(pairs)
    overall = mean(pairwise.values()) if pairwise else 0.0
    groupthink, reason = _detect_groupthink(overall, avg_time, votes)
    return ConsensusResult(
        score=round(overall, 3),
        method="jaccard",
        pairwise_scores=pairwise,
        avg_response_time=round(avg_time, 2),
        groupthink_detected=groupthink,
        groupthink_reason=reason,
    )


def _detect_groupthink(
    consensus_score: float,
    avg_response_time: float,
    votes: list[AgentVote],
) -> tuple[bool, str]:
    """Detect groupthink from consensus score and response timing.

    Two triggers:
    1. High consensus + fast response (everyone agrees too quickly)
    2. Zero risks identified by ALL agents (nobody considered downsides)
    """
    # Trigger 1: high consensus + fast answers
    if (consensus_score > GROUPTHINK_CONSENSUS_THRESHOLD
            and avg_response_time < GROUPTHINK_TIME_THRESHOLD_S):
        return True, (
            f"consensus={consensus_score:.2f} > {GROUPTHINK_CONSENSUS_THRESHOLD} "
            f"AND avg_time={avg_response_time:.1f}s < {GROUPTHINK_TIME_THRESHOLD_S}s"
        )

    # Trigger 2: no agent identified any risk
    all_no_risks = all(len(v.risks_identified) == 0 for v in votes)
    if all_no_risks and len(votes) >= 2:
        return True, "all agents identified zero risks"

    return False, ""


async def _score_llm_judge(
    pairs: list[tuple[AgentVote, AgentVote]],
    model: str,
    timeout: int,
) -> dict[str, float]:
    """Score pairwise agreement using Ollama as judge."""
    results: dict[str, float] = {}

    async def _judge_pair(a: AgentVote, b: AgentVote) -> tuple[str, float]:
        key = f"{a.agent_name}_vs_{b.agent_name}"
        prompt = CONSENSUS_JUDGE_PROMPT.format(
            agent_a=a.agent_name,
            position_a=a.position,
            agent_b=b.agent_name,
            position_b=b.position,
        )
        score = await asyncio.to_thread(_ollama_judge, model, prompt, timeout)
        return key, score

    tasks = [_judge_pair(a, b) for a, b in pairs]
    judge_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in judge_results:
        if isinstance(result, Exception):
            raise result  # Let the caller catch and fallback
        key, score = result
        results[key] = round(score, 3)

    return results


def _ollama_judge(model: str, prompt: str, timeout: int) -> float:
    """Run ollama to judge pairwise agreement. Returns float 0.0-1.0."""
    result = subprocess.run(
        ["ollama", "run", model, prompt],
        capture_output=True, text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ollama judge failed: {result.stderr[:100]}")

    # Extract float from output
    match = re.search(r"([01]\.?\d*)", result.stdout.strip())
    if match:
        val = float(match.group(1))
        return max(0.0, min(1.0, val))

    raise ValueError(f"Could not parse score from: {result.stdout[:100]}")


def _score_jaccard(pairs: list[tuple[AgentVote, AgentVote]]) -> dict[str, float]:
    """Score pairwise agreement using Jaccard similarity. Zero deps."""
    results: dict[str, float] = {}
    for a, b in pairs:
        key = f"{a.agent_name}_vs_{b.agent_name}"
        tokens_a = _tokenize(a.position)
        tokens_b = _tokenize(b.position)
        if not tokens_a and not tokens_b:
            results[key] = 1.0
            continue
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        results[key] = round(len(intersection) / len(union), 3) if union else 0.0
    return results


def _tokenize(text: str) -> set[str]:
    """Tokenize text for Jaccard: lowercase, remove stopwords."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}
