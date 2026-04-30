"""Tests for Knowledge Graph LangGraph Orchestrator."""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We must patch heavy imports before importing the module under test
# to avoid needing langgraph/langchain installed in test env.


@pytest.fixture(autouse=True)
def _reset_llm_cache() -> None:
    """Reset cached LLM singleton between tests."""
    import backend.services.rag.kg_langgraph_orchestrator as mod
    mod._cached_reasoning_llm = None


class TestGetLlmForReasoning:
    """Tests for get_llm_for_reasoning function.

    After the OAuth migration (2026-04-17), preference order is:
    1. Claude via Max OAuth subprocess (primary) — unless
       ``KG_REASONING_PROVIDER=openai``.
    2. OpenAI GPT-4o-mini (explicit opt-in or fallback when Claude
       LangChain wrapper is unavailable).
    ``ANTHROPIC_API_KEY`` is never consulted.
    """

    def test_claude_oauth_preferred(self) -> None:
        """Default path returns the OAuth-backed Claude chat model."""
        from backend.services.rag.kg_langgraph_orchestrator import get_llm_for_reasoning

        mock_llm = MagicMock()
        with patch.dict(os.environ, {"KG_REASONING_PROVIDER": "", "ANTHROPIC_API_KEY": ""}, clear=False):
            with patch(
                "backend.llm.claude_oauth_langchain.build_claude_oauth_chat_model",
                return_value=mock_llm,
            ) as mock_builder:
                result = get_llm_for_reasoning()
                assert result is mock_llm
                mock_builder.assert_called_once_with(model="claude-sonnet-4-6")

    def test_openai_explicit_optin(self) -> None:
        """``KG_REASONING_PROVIDER=openai`` skips the Claude path entirely."""
        from backend.services.rag.kg_langgraph_orchestrator import get_llm_for_reasoning

        mock_llm = MagicMock()
        with patch.dict(os.environ, {"KG_REASONING_PROVIDER": "openai", "OPENAI_API_KEY": "k"}):
            with patch(
                "backend.services.rag.kg_langgraph_orchestrator.ChatOpenAI",
                return_value=mock_llm,
            ) as mock_cls:
                result = get_llm_for_reasoning()
                assert result is mock_llm
                mock_cls.assert_called_once_with(
                    model="gpt-4o-mini",
                    temperature=0.2,
                    api_key="k",
                )

    def test_openai_fallback_when_claude_import_fails(self) -> None:
        """Falls back to OpenAI if the Claude OAuth wrapper can't be built."""
        from backend.services.rag.kg_langgraph_orchestrator import get_llm_for_reasoning

        mock_llm = MagicMock()
        with patch.dict(os.environ, {"KG_REASONING_PROVIDER": "", "OPENAI_API_KEY": "k"}):
            with patch(
                "backend.llm.claude_oauth_langchain.build_claude_oauth_chat_model",
                side_effect=ImportError("no langchain-core"),
            ):
                with patch(
                    "backend.services.rag.kg_langgraph_orchestrator.ChatOpenAI",
                    return_value=mock_llm,
                ):
                    result = get_llm_for_reasoning()
                    assert result is mock_llm

    def test_no_llm_raises(self) -> None:
        """No Claude, no OpenAI → explicit ValueError."""
        from backend.services.rag.kg_langgraph_orchestrator import get_llm_for_reasoning

        with patch.dict(os.environ, {"KG_REASONING_PROVIDER": "openai", "OPENAI_API_KEY": ""}):
            with patch("backend.services.rag.kg_langgraph_orchestrator.ChatOpenAI", None):
                with pytest.raises(ValueError, match="No LLM available"):
                    get_llm_for_reasoning()

    def test_singleton_caching(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import get_llm_for_reasoning

        mock_llm = MagicMock()
        with patch.dict(os.environ, {"KG_REASONING_PROVIDER": "", "ANTHROPIC_API_KEY": ""}):
            with patch(
                "backend.llm.claude_oauth_langchain.build_claude_oauth_chat_model",
                return_value=mock_llm,
            ):
                first = get_llm_for_reasoning()
                second = get_llm_for_reasoning()
                assert first is second


class TestNodeWrappers:
    """Tests for node wrapper functions."""

    @pytest.mark.asyncio
    async def test_understand_query_wrapper(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import understand_query_wrapper

        mock_llm = MagicMock()
        mock_state: dict[str, Any] = {"query": "test"}
        expected_state: dict[str, Any] = {"query": "test", "intent": "company_setup"}

        with patch("backend.services.rag.kg_langgraph_orchestrator.get_llm_for_reasoning", return_value=mock_llm):
            with patch("backend.services.rag.kg_langgraph_orchestrator.understand_query_node", new_callable=AsyncMock, return_value=expected_state) as mock_node:
                result = await understand_query_wrapper(mock_state)
                assert result == expected_state
                mock_node.assert_called_once_with(mock_state, mock_llm)

    @pytest.mark.asyncio
    async def test_resolve_entities_wrapper(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import resolve_entities_wrapper

        mock_pool = MagicMock()
        mock_state: dict[str, Any] = {"query": "test"}
        expected: dict[str, Any] = {"query": "test", "current_entities": ["e1"]}

        with patch("backend.services.rag.kg_langgraph_orchestrator.resolve_entities_node", new_callable=AsyncMock, return_value=expected) as mock_node:
            result = await resolve_entities_wrapper(mock_state, mock_pool)
            assert result == expected
            mock_node.assert_called_once_with(mock_state, mock_pool)

    @pytest.mark.asyncio
    async def test_traverse_graph_wrapper(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import traverse_graph_wrapper

        mock_pool = MagicMock()
        mock_state: dict[str, Any] = {"query": "test"}
        expected: dict[str, Any] = {"query": "test", "relationship_chains": []}

        with patch("backend.services.rag.kg_langgraph_orchestrator.traverse_graph_node", new_callable=AsyncMock, return_value=expected) as mock_node:
            result = await traverse_graph_wrapper(mock_state, mock_pool)
            assert result == expected
            mock_node.assert_called_once_with(mock_state, mock_pool, max_depth=3)

    @pytest.mark.asyncio
    async def test_reason_wrapper(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import reason_wrapper

        mock_llm = MagicMock()
        mock_state: dict[str, Any] = {"query": "test"}
        expected: dict[str, Any] = {"query": "test", "reasoning_steps": ["step1"]}

        with patch("backend.services.rag.kg_langgraph_orchestrator.get_llm_for_reasoning", return_value=mock_llm):
            with patch("backend.services.rag.kg_langgraph_orchestrator.reason_over_graph_node", new_callable=AsyncMock, return_value=expected) as mock_node:
                result = await reason_wrapper(mock_state)
                assert result == expected
                mock_node.assert_called_once_with(mock_state, mock_llm)

    @pytest.mark.asyncio
    async def test_synthesize_workflow_wrapper(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import synthesize_workflow_wrapper

        mock_pool = MagicMock()
        mock_state: dict[str, Any] = {"query": "test"}
        expected: dict[str, Any] = {"query": "test", "workflow": {"name": "test_wf"}}

        with patch("backend.services.rag.kg_langgraph_orchestrator.synthesize_workflow_node", new_callable=AsyncMock, return_value=expected) as mock_node:
            result = await synthesize_workflow_wrapper(mock_state, mock_pool)
            assert result == expected
            mock_node.assert_called_once_with(mock_state, mock_pool)


class TestRouteAfterQueryUnderstanding:
    """Tests for route_after_query_understanding function."""

    def _make_state(self, **kwargs: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "query": "",
            "intent": None,
            "domain": "general",
            "extracted_entities": [],
        }
        base.update(kwargs)
        return base

    def test_domain_visa(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        state = self._make_state(domain="visa")
        assert route_after_query_understanding(state) == "visa_subgraph"

    def test_domain_tax(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        state = self._make_state(domain="tax")
        assert route_after_query_understanding(state) == "tax_subgraph"

    def test_domain_property(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        state = self._make_state(domain="property")
        assert route_after_query_understanding(state) == "property_subgraph"

    def test_domain_company(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        state = self._make_state(domain="company")
        assert route_after_query_understanding(state) == "company_subgraph"

    def test_domain_kbli(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        state = self._make_state(domain="kbli")
        assert route_after_query_understanding(state) == "company_subgraph"

    # ────────────────────────────────────────────────────────────────────
    # Intent-only routing tests
    #
    # The router was refactored to route PRIMARILY on `domain`
    # (`route_after_query_understanding` PHASE 1). Intent only matters when
    # it lands in the small `golden_route_intents` allowlist (PHASE 2:
    # `pt_pma_setup`, `kitas_work`, `nib_oss`, `npwp_registration`). The
    # broader intent-name-to-subgraph mapping below was removed when the
    # Pydantic-validated domain field became the routing contract.
    #
    # These tests now lock in the new contract: an `intent="..."` set
    # WITHOUT a corresponding `domain` does NOT route to a subgraph — it
    # falls through to PHASE 4 and terminates (END) so the upstream
    # vector-search fallback handles the query.
    # ────────────────────────────────────────────────────────────────────

    def test_intent_company_setup_without_domain_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(intent="company_setup")  # domain="general"
        assert route_after_query_understanding(state) == END

    def test_intent_visa_application_without_domain_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(intent="visa_application")
        assert route_after_query_understanding(state) == END

    def test_intent_property_acquisition_without_domain_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(intent="property_acquisition")
        assert route_after_query_understanding(state) == END

    def test_intent_tax_compliance_without_domain_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(intent="tax_compliance")
        assert route_after_query_understanding(state) == END

    def test_intent_pt_pma_setup_takes_golden_route(self) -> None:
        """PHASE 2: intents in the golden_route_intents allowlist still
        route to use_golden_route, even without a domain hint."""
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        state = self._make_state(intent="pt_pma_setup")
        assert route_after_query_understanding(state) == "use_golden_route"

    # ────────────────────────────────────────────────────────────────────
    # Keyword-only routing tests
    #
    # The router does NOT look at `state["query"]` for routing decisions
    # (only `domain` and `intent` are read). Keyword-based routing was
    # moved upstream into `_detect_domain_from_query` inside
    # `understand_query_node`, which populates `state["domain"]` BEFORE
    # this function runs. So setting only `query="..."` here exercises a
    # bypass of the upstream classifier and must terminate.
    # ────────────────────────────────────────────────────────────────────

    def test_keyword_pt_pma_query_only_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(query="How to set up PT PMA in Bali")
        assert route_after_query_understanding(state) == END

    def test_keyword_kitas_query_only_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(query="I need a kitas for work")
        assert route_after_query_understanding(state) == END

    def test_keyword_villa_query_only_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(query="Buy a villa in Bali")
        assert route_after_query_understanding(state) == END

    def test_keyword_pajak_query_only_terminates(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import (
            END,
            route_after_query_understanding,
        )
        state = self._make_state(query="How to pay pajak in Indonesia")
        assert route_after_query_understanding(state) == END

    def test_complex_query_with_multiple_entities(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        state = self._make_state(
            query="something general",
            extracted_entities=["e1", "e2"],
        )
        assert route_after_query_understanding(state) == "resolve_entities"

    def test_complex_query_with_and(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        # Use a query that has AND but does NOT match any domain keyword
        state = self._make_state(query="Documents AND permits needed")
        assert route_after_query_understanding(state) == "resolve_entities"

    def test_simple_query_fallback_to_end(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_query_understanding
        from langgraph.graph import END
        state = self._make_state(query="hello world")
        assert route_after_query_understanding(state) == END


class TestRouteAfterTraversal:
    """Tests for route_after_traversal function."""

    def test_many_chains(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_traversal
        state: dict[str, Any] = {"relationship_chains": [1, 2, 3, 4, 5]}
        assert route_after_traversal(state) == "reason"

    def test_few_chains(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_traversal
        state: dict[str, Any] = {"relationship_chains": [1, 2]}
        assert route_after_traversal(state) == "reason"

    def test_no_chains(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import route_after_traversal
        from langgraph.graph import END
        state: dict[str, Any] = {"relationship_chains": []}
        assert route_after_traversal(state) == END


class TestInvokeSubgraph:
    """Tests for invoke_subgraph function.

    Note: invoke_subgraph uses a local import `from backend.services.rag.kg_cache import get_kg_cache`,
    so we patch it at the source module path.
    """

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import invoke_subgraph

        cached_workflow = {"name": "cached_workflow", "steps": []}
        mock_cache = AsyncMock()
        mock_cache.get_subgraph_result = AsyncMock(return_value=cached_workflow)

        state: dict[str, Any] = {"query": "test query", "workflow": None}
        compiled_sg = MagicMock()

        with patch("backend.services.rag.kg_cache.get_kg_cache", return_value=mock_cache):
            result = await invoke_subgraph(state, compiled_sg, "Company", "icon")
            assert result["workflow"] == cached_workflow
            compiled_sg.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_invokes_subgraph(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import invoke_subgraph

        mock_cache = AsyncMock()
        mock_cache.get_subgraph_result = AsyncMock(return_value=None)
        mock_cache.set_subgraph_result = AsyncMock()

        subgraph_result = {"workflow": {"name": "company_setup", "steps": ["step1"]}}
        compiled_sg = AsyncMock()
        compiled_sg.ainvoke = AsyncMock(return_value=subgraph_result)

        state: dict[str, Any] = {"query": "test query", "workflow": None}

        with patch("backend.services.rag.kg_cache.get_kg_cache", return_value=mock_cache):
            result = await invoke_subgraph(state, compiled_sg, "Company", "icon")
            assert result["workflow"] == {"name": "company_setup", "steps": ["step1"]}
            mock_cache.set_subgraph_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_subgraph_error_increments_counter(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import invoke_subgraph

        mock_cache = AsyncMock()
        mock_cache.get_subgraph_result = AsyncMock(return_value=None)

        compiled_sg = AsyncMock()
        compiled_sg.ainvoke = AsyncMock(side_effect=RuntimeError("Subgraph failed"))

        state: dict[str, Any] = {"query": "test", "workflow": None}

        with patch("backend.services.rag.kg_cache.get_kg_cache", return_value=mock_cache):
            with pytest.raises(RuntimeError, match="Subgraph failed"):
                await invoke_subgraph(state, compiled_sg, "Test", "icon")


class TestUseGoldenRouteNode:
    """Tests for use_golden_route_node function.

    Note: KGEnhancedRetrieval is imported locally inside the function body,
    so we patch the source module, not the orchestrator.
    """

    @pytest.mark.asyncio
    async def test_matching_golden_route(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import use_golden_route_node

        mock_route = MagicMock()
        mock_route.route_id = "pt_pma_setup"
        mock_route.name = "PT PMA Setup"
        mock_route.description = "Steps to set up PT PMA"
        mock_route.path = ["e1", "e2", "e3"]

        mock_kg = AsyncMock()
        mock_kg.get_golden_routes = AsyncMock(return_value=[mock_route])

        mock_pool = MagicMock()
        state: dict[str, Any] = {"intent": "pt_pma_setup", "workflow": None, "golden_route_match": None}

        with patch("backend.services.rag.kg_enhanced_retrieval.KGEnhancedRetrieval", return_value=mock_kg):
            result = await use_golden_route_node(state, mock_pool)
            assert result["workflow"]["type"] == "golden_route"
            assert result["workflow"]["confidence"] == 1.0
            assert result["golden_route_match"] == "pt_pma_setup"

    @pytest.mark.asyncio
    async def test_no_matching_golden_route(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import use_golden_route_node

        mock_route = MagicMock()
        mock_route.route_id = "kitas_work"

        mock_kg = AsyncMock()
        mock_kg.get_golden_routes = AsyncMock(return_value=[mock_route])

        mock_pool = MagicMock()
        state: dict[str, Any] = {"intent": "nonexistent_intent", "workflow": None, "golden_route_match": None}

        with patch("backend.services.rag.kg_enhanced_retrieval.KGEnhancedRetrieval", return_value=mock_kg):
            result = await use_golden_route_node(state, mock_pool)
            assert result["workflow"] is None  # No match found


class TestKGLangGraphOrchestrator:
    """Tests for KGLangGraphOrchestrator class."""

    def test_init(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

        mock_pool = MagicMock()
        orch = KGLangGraphOrchestrator(mock_pool)
        assert orch.db_pool is mock_pool
        assert orch.app is None
        assert orch._compiled_subgraphs == {}

    @pytest.mark.asyncio
    async def test_query_initializes_if_needed(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

        mock_pool = MagicMock()
        orch = KGLangGraphOrchestrator(mock_pool)

        final_state = {
            "intent": "company_setup",
            "workflow": {"name": "test"},
        }
        mock_app = AsyncMock()
        mock_app.ainvoke = AsyncMock(return_value=final_state)

        with patch.object(orch, "initialize", new_callable=AsyncMock) as mock_init:
            orch.app = mock_app  # simulate initialized
            result = await orch.query("How to open PT PMA?")
            assert result["intent"] == "company_setup"
            mock_init.assert_not_called()  # Already has app

    @pytest.mark.asyncio
    async def test_query_auto_initializes(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

        mock_pool = MagicMock()
        orch = KGLangGraphOrchestrator(mock_pool)

        final_state = {"intent": "visa", "workflow": None}
        mock_app = AsyncMock()
        mock_app.ainvoke = AsyncMock(return_value=final_state)

        async def fake_init() -> None:
            orch.app = mock_app

        with patch.object(orch, "initialize", new_callable=AsyncMock, side_effect=fake_init):
            result = await orch.query("visa query")
            assert result == final_state

    @pytest.mark.asyncio
    async def test_query_error_returns_empty(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

        mock_pool = MagicMock()
        orch = KGLangGraphOrchestrator(mock_pool)

        mock_app = AsyncMock()
        mock_app.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        orch.app = mock_app

        result = await orch.query("test query")
        assert result["workflow"] is None
        assert "error" in result

    @pytest.mark.asyncio
    async def test_query_with_thread_id(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

        mock_pool = MagicMock()
        orch = KGLangGraphOrchestrator(mock_pool)

        final_state = {"intent": "tax", "workflow": {"name": "tax_wf"}}
        mock_app = AsyncMock()
        mock_app.ainvoke = AsyncMock(return_value=final_state)
        orch.app = mock_app

        result = await orch.query("pajak query", thread_id="custom-thread-123")
        assert result == final_state
        call_kwargs = mock_app.ainvoke.call_args
        assert call_kwargs[1]["config"]["configurable"]["thread_id"] == "custom-thread-123"

    @pytest.mark.asyncio
    async def test_get_visual_graph(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

        mock_pool = MagicMock()
        orch = KGLangGraphOrchestrator(mock_pool)

        mock_graph = MagicMock()
        mock_graph.draw_mermaid.return_value = "graph TD; A-->B"
        mock_app = MagicMock()
        mock_app.get_graph.return_value = mock_graph
        orch.app = mock_app

        result = await orch.get_visual_graph()
        assert "graph TD" in result

    @pytest.mark.asyncio
    async def test_get_visual_graph_subgraph(self) -> None:
        from backend.services.rag.kg_langgraph_orchestrator import KGLangGraphOrchestrator

        mock_pool = MagicMock()
        orch = KGLangGraphOrchestrator(mock_pool)

        mock_main_graph = MagicMock()
        mock_main_graph.draw_mermaid.return_value = "main"
        mock_main_app = MagicMock()
        mock_main_app.get_graph.return_value = mock_main_graph
        orch.app = mock_main_app

        mock_sub_graph = MagicMock()
        mock_sub_graph.draw_mermaid.return_value = "subgraph visa"
        mock_sub_app = MagicMock()
        mock_sub_app.get_graph.return_value = mock_sub_graph
        orch._compiled_subgraphs = {"visa": mock_sub_app}

        result = await orch.get_visual_graph(subgraph="visa")
        assert "subgraph visa" in result
