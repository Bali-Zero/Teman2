"""StateGraph construction — the central graph definition.

This module builds the LangGraph StateGraph that orchestrates the entire
query flow. Each node mutates GraphState and grader nodes provide
correction cycles with fail-fast support.

Fail-fast: if a grader scores < 0.2 (FAIL), the graph skips all downstream
nodes and routes to synthesize_fail_fast which produces a polite
"rephrase your question" response. This saves tokens and avoids
reasoning over garbage retrieval results.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from nuzantara_graph.graph.constants import NodeName, RouteDecision
from nuzantara_graph.graph.router import (
    route_after_grade,
    route_after_understand,
    route_after_visa_subgraph,
)
from nuzantara_graph.graders import (
    make_retrieval_grader,
    make_reasoning_grader,
    make_answer_grader,
    make_hallucination_grader,
    make_pricing_grader,
)
from nuzantara_graph.nodes.understand import make_understand_node
from nuzantara_graph.nodes.retrieve import make_retrieve_node
from nuzantara_graph.nodes.reason import make_reason_node
from nuzantara_graph.nodes.synthesize import (
    make_synthesize_node,
    make_synthesize_direct_node,
    make_synthesize_fail_fast_node,
)
from nuzantara_graph.nodes.tools import make_tools_node
from nuzantara_graph.subgraphs import (
    make_company_subgraph,
    make_visa_subgraph,
    make_property_subgraph,
    make_tax_subgraph,
)
from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState


def build_graph(services: Services | None = None) -> StateGraph:
    """Build and return the StateGraph.

    Args:
        services: Service container for DI. If None, uses defaults
                  (useful for structural tests that don't invoke nodes).
    """
    svc = services or Services()

    graph = StateGraph(GraphState)

    # --- Core nodes ---
    graph.add_node(NodeName.UNDERSTAND, make_understand_node(svc))
    graph.add_node(NodeName.RETRIEVE, make_retrieve_node(svc))
    graph.add_node(NodeName.REASON, make_reason_node(svc))
    graph.add_node(NodeName.SYNTHESIZE, make_synthesize_node(svc))
    graph.add_node(NodeName.TOOLS, make_tools_node(svc))
    graph.add_node(NodeName.SYNTHESIZE_DIRECT, make_synthesize_direct_node(svc))
    graph.add_node(NodeName.SYNTHESIZE_FAIL_FAST, make_synthesize_fail_fast_node(svc))

    # --- Grader nodes (real implementations) ---
    graph.add_node(NodeName.GRADE_RETRIEVAL, make_retrieval_grader(svc))
    graph.add_node(NodeName.GRADE_REASONING, make_reasoning_grader(svc))
    graph.add_node(NodeName.GRADE_ANSWER, make_answer_grader(svc))
    graph.add_node(NodeName.GRADE_HALLUCINATION, make_hallucination_grader(svc))
    graph.add_node(NodeName.GRADE_PRICING, make_pricing_grader(svc))

    # --- Subgraph nodes ---
    graph.add_node(NodeName.SUBGRAPH_COMPANY, make_company_subgraph(svc))
    graph.add_node(NodeName.SUBGRAPH_VISA, make_visa_subgraph(svc))
    graph.add_node(NodeName.SUBGRAPH_PROPERTY, make_property_subgraph(svc))
    graph.add_node(NodeName.SUBGRAPH_TAX, make_tax_subgraph(svc))

    # --- Entry point ---
    graph.set_entry_point(NodeName.UNDERSTAND)

    # --- Edges: understand -> route (conditional) ---
    graph.add_conditional_edges(
        NodeName.UNDERSTAND,
        route_after_understand,
        {
            RouteDecision.RETRIEVE: NodeName.RETRIEVE,
            RouteDecision.SUBGRAPH_COMPANY: NodeName.SUBGRAPH_COMPANY,
            RouteDecision.SUBGRAPH_VISA: NodeName.SUBGRAPH_VISA,
            RouteDecision.SUBGRAPH_PROPERTY: NodeName.SUBGRAPH_PROPERTY,
            RouteDecision.SUBGRAPH_TAX: NodeName.SUBGRAPH_TAX,
            RouteDecision.TOOLS: NodeName.TOOLS,
            RouteDecision.DIRECT: NodeName.SYNTHESIZE_DIRECT,
        },
    )

    # --- Retrieval → Grade Retrieval → [retry | continue | fail_fast] ---
    graph.add_edge(NodeName.RETRIEVE, NodeName.GRADE_RETRIEVAL)
    graph.add_conditional_edges(
        NodeName.GRADE_RETRIEVAL,
        lambda state: route_after_grade(state, NodeName.RETRIEVE, NodeName.REASON),
        {
            "retry": NodeName.RETRIEVE,
            "continue": NodeName.REASON,
            "fail_fast": NodeName.SYNTHESIZE_FAIL_FAST,
        },
    )

    # --- Reason → Grade Reasoning → [retry | continue | fail_fast] ---
    graph.add_edge(NodeName.REASON, NodeName.GRADE_REASONING)
    graph.add_conditional_edges(
        NodeName.GRADE_REASONING,
        lambda state: route_after_grade(state, NodeName.REASON, NodeName.SYNTHESIZE),
        {
            "retry": NodeName.REASON,
            "continue": NodeName.SYNTHESIZE,
            "fail_fast": NodeName.SYNTHESIZE_FAIL_FAST,
        },
    )

    # --- Synthesize → Grade Answer → [retry | continue | fail_fast] ---
    graph.add_edge(NodeName.SYNTHESIZE, NodeName.GRADE_ANSWER)
    graph.add_conditional_edges(
        NodeName.GRADE_ANSWER,
        lambda state: route_after_grade(state, NodeName.SYNTHESIZE, NodeName.GRADE_HALLUCINATION),
        {
            "retry": NodeName.SYNTHESIZE,
            "continue": NodeName.GRADE_HALLUCINATION,
            "fail_fast": NodeName.SYNTHESIZE_FAIL_FAST,
        },
    )

    # --- Hallucination grader → END (terminal, no retry) ---
    graph.add_edge(NodeName.GRADE_HALLUCINATION, END)

    # --- Subgraph exits → reason ---
    graph.add_edge(NodeName.SUBGRAPH_COMPANY, NodeName.REASON)
    graph.add_edge(NodeName.SUBGRAPH_PROPERTY, NodeName.REASON)
    graph.add_edge(NodeName.SUBGRAPH_TAX, NodeName.REASON)

    # --- Visa subgraph exit is conditional: the multi-step planner may
    #     already have produced a fully-cited answer, in which case we
    #     skip REASON/SYNTHESIZE and go straight to the hallucination
    #     grader as the final safety check.
    graph.add_conditional_edges(
        NodeName.SUBGRAPH_VISA,
        route_after_visa_subgraph,
        {
            "direct": NodeName.GRADE_HALLUCINATION,
            "reason": NodeName.REASON,
        },
    )

    # --- Tools → reason ---
    graph.add_edge(NodeName.TOOLS, NodeName.REASON)

    # --- Terminal nodes → END ---
    graph.add_edge(NodeName.SYNTHESIZE_DIRECT, END)
    graph.add_edge(NodeName.SYNTHESIZE_FAIL_FAST, END)

    return graph
