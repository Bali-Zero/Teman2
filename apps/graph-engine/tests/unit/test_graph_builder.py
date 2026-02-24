"""Tests for graph construction."""

from nuzantara_graph.graph.builder import build_graph
from nuzantara_graph.graph.constants import NodeName


class TestGraphBuilder:
    def test_graph_builds_without_error(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_all_core_nodes(self):
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        for node in [
            NodeName.UNDERSTAND,
            NodeName.RETRIEVE,
            NodeName.REASON,
            NodeName.SYNTHESIZE,
        ]:
            assert node in node_names, f"Missing node: {node}"

    def test_graph_has_all_grader_nodes(self):
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        for node in [
            NodeName.GRADE_RETRIEVAL,
            NodeName.GRADE_REASONING,
            NodeName.GRADE_ANSWER,
            NodeName.GRADE_HALLUCINATION,
        ]:
            assert node in node_names, f"Missing grader: {node}"

    def test_graph_has_all_subgraph_nodes(self):
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        for node in [
            NodeName.SUBGRAPH_COMPANY,
            NodeName.SUBGRAPH_VISA,
            NodeName.SUBGRAPH_PROPERTY,
            NodeName.SUBGRAPH_TAX,
        ]:
            assert node in node_names, f"Missing subgraph: {node}"

    def test_graph_compiles(self):
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_with_custom_services(self):
        from nuzantara_graph.services import Services
        svc = Services()
        graph = build_graph(services=svc)
        compiled = graph.compile()
        assert compiled is not None
