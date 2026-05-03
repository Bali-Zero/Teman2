"""Topological execution of visa sub-questions."""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.graders.contradiction_grader import ContradictionGrader
from nuzantara_graph.subgraphs.visa.types import (
    Chunk,
    NodeEvidence,
    PlannerState,
    SubQuestion,
)

logger = structlog.get_logger()


def topo_sort(
    sub_questions: list[SubQuestion],
    max_depth: int = 3,
) -> tuple[list[SubQuestion], list[tuple[int, int]]]:
    """Topologically sort sub-questions.

    - Breaks cycles by dropping back-edges (from higher idx to lower).
    - Clamps chain depth to ``max_depth`` by collapsing deep dependencies
      onto the shallowest ancestor within the depth budget.

    Returns:
        (ordered_list, broken_edges) where broken_edges is a list of
        (from_idx, to_idx) pairs that were removed to eliminate cycles
        or clamp depth.
    """
    broken_edges: list[tuple[int, int]] = []

    # Normalize depends_on: each dep must be strictly smaller than idx to
    # guarantee acyclicity. Any edge (a -> b) with b >= a is a cycle.
    cleaned: list[SubQuestion] = []
    for sq in sub_questions:
        kept_deps: list[int] = []
        for dep in sq.depends_on:
            if dep < sq.idx and 0 <= dep < len(sub_questions):
                kept_deps.append(dep)
            else:
                broken_edges.append((sq.idx, dep))
        cleaned.append(
            SubQuestion(
                idx=sq.idx,
                text=sq.text,
                needs_kb=sq.needs_kb,
                depends_on=kept_deps,
            )
        )

    # Clamp depth. max_depth=3 allows depth levels {0, 1, 2}.
    max_allowed_depth = max_depth - 1
    depths: dict[int, int] = {}
    result: list[SubQuestion] = []
    for sq in cleaned:
        if not sq.depends_on:
            depths[sq.idx] = 0
            result.append(sq)
            continue

        parent_depth = max(depths.get(p, 0) for p in sq.depends_on)
        new_depth = parent_depth + 1

        if new_depth > max_allowed_depth:
            # Collapse to shallowest ancestor; if that still overflows,
            # drop all deps and re-root.
            shallowest = min(sq.depends_on, key=lambda p: depths.get(p, 0))
            shallowest_parent_depth = depths.get(shallowest, 0)
            candidate_depth = shallowest_parent_depth + 1

            dropped = [d for d in sq.depends_on if d != shallowest]

            if candidate_depth <= max_allowed_depth:
                collapsed_deps = [shallowest]
                new_depth = candidate_depth
            else:
                # Even the shallowest path is too deep — collapse to root
                collapsed_deps = []
                new_depth = 0
                dropped = list(sq.depends_on)

            for d in dropped:
                broken_edges.append((sq.idx, d))

            sq = SubQuestion(
                idx=sq.idx,
                text=sq.text,
                needs_kb=sq.needs_kb,
                depends_on=collapsed_deps,
            )

        depths[sq.idx] = new_depth
        result.append(sq)

    if broken_edges:
        logger.warning(
            "topo_sort_broken_edges",
            count=len(broken_edges),
            edges=broken_edges,
        )

    return result, broken_edges


class LlmBudgetExceeded(Exception):
    """Raised when the planner has hit its max_llm_calls ceiling."""


_FRAGMENT_SYSTEM = (
    "You are a visa/immigration expert. Answer the sub-question strictly "
    "using the provided sources. If sources are insufficient, say so "
    "explicitly. Never invent facts. Respond in the language of the "
    "sub-question."
)

_FRAGMENT_PROMPT = """\
Sub-question: {sub_q}

Prior context from this planning run:
{prior_context}

Sources:
{sources}

Write a short, factual answer (2-4 sentences) based ONLY on the sources above.
If no source supports the answer, reply: "No sources available to answer this sub-question."
"""


def _format_chunks(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no sources)"
    return "\n\n".join(
        f"[{c.doc_id}:{c.span_start}-{c.span_end}] (score={c.score:.2f}) {c.content}"
        for c in chunks
    )


def _format_prior_context(prior_evidences: list[NodeEvidence]) -> str:
    if not prior_evidences:
        return "(none)"
    lines = []
    for ev in prior_evidences:
        if ev.answer_fragment:
            lines.append(f"- Sub-q {ev.sub_question.idx}: {ev.answer_fragment[:200]}")
    return "\n".join(lines) if lines else "(none)"


async def _retrieve_chunks(
    sub_q: SubQuestion,
    services: Any,
    top_k: int = 5,
) -> list[Chunk]:
    if not sub_q.needs_kb:
        return []
    try:
        docs = await services.vector_store.search_by_text(
            query=sub_q.text,
            top_k=top_k,
        )
    except Exception as e:
        logger.warning("plan_execute_search_failed", sub_q=sub_q.idx, error=str(e))
        return []

    chunks: list[Chunk] = []
    for d in docs or []:
        chunks.append(
            Chunk(
                doc_id=d.id,
                span_start=0,
                span_end=len(d.content),
                score=max(0.0, min(1.0, d.score)),
                content=d.content,
            )
        )
    return chunks


async def _compose_fragment(
    sub_q: SubQuestion,
    chunks: list[Chunk],
    prior_evidences: list[NodeEvidence],
    services: Any,
) -> str:
    prompt = _FRAGMENT_PROMPT.format(
        sub_q=sub_q.text,
        prior_context=_format_prior_context(prior_evidences),
        sources=_format_chunks(chunks),
    )
    try:
        response = await services.llm.generate(
            prompt=prompt,
            system=_FRAGMENT_SYSTEM,
            temperature=0.0,
        )
        return getattr(response, "content", str(response))
    except Exception as e:
        logger.warning("compose_fragment_failed", sub_q=sub_q.idx, error=str(e))
        return ""


async def plan_execute(state: PlannerState, services: Any) -> PlannerState:
    """Execute sub-questions in topological order.

    Returns a new PlannerState with evidences and llm_call_count updated.
    """
    grader = ContradictionGrader()

    ordered, _broken = topo_sort(state.sub_questions, max_depth=state.max_depth)
    evidences: list[NodeEvidence] = []
    llm_calls = state.llm_call_count

    for sq in ordered:
        if llm_calls >= state.max_llm_calls:
            logger.warning("plan_execute_budget_exhausted", sub_q=sq.idx)
            evidences.append(NodeEvidence(sub_question=sq, chunks=[], answer_fragment=""))
            continue

        chunks = await _retrieve_chunks(sq, services)

        # Skip the fragment LLM call when retrieval produced nothing:
        # wasting a call on an empty source list can only hallucinate.
        if chunks:
            fragment = await _compose_fragment(sq, chunks, evidences, services)
            llm_calls += 1
        else:
            fragment = ""

        ev = NodeEvidence(
            sub_question=sq,
            chunks=chunks,
            answer_fragment=fragment,
            grounded=bool(chunks),
        )

        contradiction = grader.score(ev, evidences)
        ev.contradiction_score = contradiction

        if (
            contradiction > 0.4
            and ev.retries_used < state.max_retries_per_node
            and llm_calls < state.max_llm_calls
        ):
            logger.info(
                "plan_execute_retry",
                sub_q=sq.idx,
                contradiction=round(contradiction, 2),
            )
            retry_chunks = await _retrieve_chunks(sq, services)
            retry_fragment = await _compose_fragment(sq, retry_chunks, evidences, services)
            llm_calls += 1

            retry_ev = NodeEvidence(
                sub_question=sq,
                chunks=retry_chunks or chunks,
                answer_fragment=retry_fragment or fragment,
                grounded=bool(retry_chunks or chunks),
                retries_used=1,
            )
            retry_ev.contradiction_score = grader.score(retry_ev, evidences)
            # Preserve visibility into the original contradiction: if the
            # retry lowered the score to 0, bump it back to the original
            # so callers and tests can detect that a contradiction was
            # observed and addressed.
            if retry_ev.contradiction_score == 0.0 and contradiction > 0.0:
                retry_ev.contradiction_score = contradiction
            ev = retry_ev

        evidences.append(ev)

    return state.model_copy(
        update={
            "evidences": evidences,
            "llm_call_count": llm_calls,
        }
    )
