"""Visa multi-step planner — LangGraph StateGraph.

Pipeline:
    1. b211_rewrite  (sync)
    2. decompose     (1 LLM call)
    3. plan_execute  (≤ N × 2 LLM calls, bounded by max_llm_calls)
    4. compose       (1 LLM call)
    5. terminate     (sync, produces contract dict)

Termination proof
-----------------
Let N = len(sub_questions) after decompose truncates to ≤ 5.

- decompose runs exactly once
- plan_execute iterates a topologically sorted list ONCE
  - each sub-question triggers at most 2 LLM calls (initial + 1 retry)
  - retries_used is monotonically increasing, never reset
  - llm_call_count is globally monotonic
  - the loop terminates when (a) all sub_qs processed, or (b) budget exhausted
- compose runs exactly once
- No edge in the StateGraph loops back to a prior node

Total LLM calls: 1 + N×2 + 1 ≤ 12, clamped to max_llm_calls (default 8).
Graph acyclic + finite list + monotonic budget ⇒ guaranteed termination.
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from nuzantara_graph.services import Services
from nuzantara_graph.subgraphs.visa.compose import compose
from nuzantara_graph.subgraphs.visa.decompose import (
    decompose,
    rewrite_legacy_visa_terms,
)
from nuzantara_graph.subgraphs.visa.execute import plan_execute
from nuzantara_graph.subgraphs.visa.specs import _identify_visa_type
from nuzantara_graph.subgraphs.visa.types import PlannerState
from nuzantara_schemas.state import GraphState, RetrievedDocument

logger = structlog.get_logger()


async def _node_b211_rewrite(state: PlannerState) -> dict[str, Any]:
    rewritten, note = rewrite_legacy_visa_terms(state.query)
    updates: dict[str, Any] = {"rewritten_query": rewritten}
    if note is not None:
        updates["system_notes"] = [note]
    return updates


def _make_decompose_node(services: Services):
    async def _node_decompose(state: PlannerState) -> dict[str, Any]:
        sub_qs = await decompose(
            state.rewritten_query or state.query,
            services.llm,
            max_sub_questions=state.max_sub_questions,
        )
        return {
            "sub_questions": sub_qs,
            "llm_call_count": state.llm_call_count + 1,
        }

    return _node_decompose


def _make_execute_node(services: Services):
    async def _node_execute(state: PlannerState) -> dict[str, Any]:
        new_state = await plan_execute(state, services)
        return {
            "evidences": new_state.evidences,
            "llm_call_count": new_state.llm_call_count,
        }

    return _node_execute


def _make_compose_node(services: Services):
    async def _node_compose(state: PlannerState) -> dict[str, Any]:
        answer = await compose(
            query=state.query,
            evidences=state.evidences,
            system_notes=state.system_notes,
            llm=services.llm,
        )
        return {
            "final_answer": answer,
            "llm_call_count": state.llm_call_count + 1,
        }

    return _node_compose


def _build_planner_graph(services: Services) -> Any:
    graph = StateGraph(PlannerState)

    graph.add_node("b211_rewrite", _node_b211_rewrite)
    graph.add_node("decompose", _make_decompose_node(services))
    graph.add_node("plan_execute", _make_execute_node(services))
    graph.add_node("compose", _make_compose_node(services))

    graph.set_entry_point("b211_rewrite")
    graph.add_edge("b211_rewrite", "decompose")
    graph.add_edge("decompose", "plan_execute")
    graph.add_edge("plan_execute", "compose")
    graph.add_edge("compose", END)

    return graph.compile()


def _to_retrieved_documents(state: PlannerState) -> list[RetrievedDocument]:
    """Pack planner outputs into RetrievedDocument list for REASON node."""
    docs: list[RetrievedDocument] = []

    for note in state.system_notes:
        docs.append(
            RetrievedDocument(
                id=note.doc_id,
                content=note.content,
                score=note.score,
                metadata={"source": "system_note"},
                source="domain",
            )
        )

    for ev in state.evidences:
        for c in ev.chunks:
            docs.append(
                RetrievedDocument(
                    id=c.doc_id,
                    content=c.content,
                    score=c.score,
                    metadata={
                        "span_start": c.span_start,
                        "span_end": c.span_end,
                        "sub_question_idx": ev.sub_question.idx,
                        "sub_question_text": ev.sub_question.text,
                    },
                    source="vector",
                )
            )

    if state.final_answer:
        docs.append(
            RetrievedDocument(
                id="visa_planner:final_answer",
                content=state.final_answer,
                score=1.0,
                metadata={"kind": "planner_answer"},
                source="domain",
            )
        )

    return docs


def _dominant_visa(state: GraphState) -> str:
    """Pick the dominant visa type using the legacy identification helper."""
    try:
        return _identify_visa_type(state).value
    except Exception:
        return "general"


def make_visa_subgraph(services: Services):
    """Factory that creates the multi-step visa planner node.

    Backward-compatible: the returned callable accepts a GraphState and
    returns a dict with the keys expected by the main REASON node.
    """
    compiled_graph = _build_planner_graph(services)

    async def visa_planner_node(state: GraphState) -> dict[str, Any]:
        logger.info(
            "visa_planner_start",
            query=state.query[:80],
            intent=getattr(state.intent, "value", state.intent),
        )

        planner_state = PlannerState(query=state.query)
        final: PlannerState

        try:
            result = await compiled_graph.ainvoke(planner_state)
            if isinstance(result, dict):
                final = PlannerState(**{**planner_state.model_dump(), **result})
            else:
                final = result
        except Exception as e:
            logger.error("visa_planner_graph_failed", error=str(e))
            final = planner_state.model_copy(update={"error": str(e)})

        docs = _to_retrieved_documents(final)

        kg_entities: list[dict[str, Any]] = []
        kg_relationships: list[dict[str, Any]] = []
        try:
            dominant = _dominant_visa(state)
            kg_entities = await services.kg_store.get_entities(
                entity_ids=[f"visa:{dominant}"],
            )
        except Exception as e:
            logger.warning("visa_planner_kg_failed", error=str(e))

        logger.info(
            "visa_planner_complete",
            doc_count=len(docs),
            llm_calls=final.llm_call_count,
            sub_questions=len(final.sub_questions),
        )

        sources = _extract_sources(final)

        return {
            "retrieved_documents": docs,
            "kg_entities": kg_entities,
            "kg_relationships": kg_relationships,
            "domain": _dominant_visa(state),
            "current_node": "subgraph_visa",
            "answer": final.final_answer,
            "sources": sources,
            "visa_planner_trace": {
                "llm_calls": final.llm_call_count,
                "sub_questions": [sq.model_dump() for sq in final.sub_questions],
                "evidences_count": len(final.evidences),
                "final_answer": final.final_answer,
            },
        }

    return visa_planner_node


def _extract_sources(state: PlannerState) -> list[dict[str, Any]]:
    """Collapse planner evidence chunks into a deduped sources list."""
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []

    for note in state.system_notes:
        if note.doc_id in seen:
            continue
        seen.add(note.doc_id)
        sources.append(
            {
                "id": note.doc_id,
                "title": note.doc_id,
                "snippet": note.content[:200],
                "source": "system_note",
            }
        )

    for ev in state.evidences:
        for c in ev.chunks:
            if c.doc_id in seen:
                continue
            seen.add(c.doc_id)
            sources.append(
                {
                    "id": c.doc_id,
                    "title": c.doc_id,
                    "span": f"{c.span_start}-{c.span_end}",
                    "snippet": c.content[:200],
                    "score": round(c.score, 3),
                    "source": "vector",
                }
            )

    return sources
