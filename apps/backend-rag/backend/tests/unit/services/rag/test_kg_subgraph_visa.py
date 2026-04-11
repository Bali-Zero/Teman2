"""
Unit tests for kg_subgraph_visa.py.

Tests all 4 subgraph nodes (identify, RPTKA check, requirements, synthesize)
and the build_visa_subgraph constructor with mocked DB and LLM.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_pool(conn=None):
    pool = MagicMock()
    conn = conn or AsyncMock()

    class _Ctx:
        async def __aenter__(self): return conn
        async def __aexit__(self, *a): pass

    pool.acquire = MagicMock(return_value=_Ctx())
    return pool, conn


def _make_state(**kwargs):
    """Create a minimal VisaState dict for testing."""
    state = {
        "query": "I need a KITAS work visa",
        "user_context": {},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
        "visa_type": None,
        "purpose": None,
        "employment_type": None,
        "requires_rptka": False,
        "sponsor_company": None,
        "duration_months": None,
        "visa_requirements": [],
        "kg_sources_used": 0,
    }
    state.update(kwargs)
    return state


# ---------------------------------------------------------------------------
# Node 1: identify_visa_type_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIdentifyVisaTypeNode:
    async def test_kitas_from_keyword(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="I need a KITAS for work")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["visa_type"] == "kitas"
        assert result["purpose"] == "work"
        assert result["requires_rptka"] is True

    async def test_kitap_from_keyword(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="How to get KITAP for retirement")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["visa_type"] == "kitap"
        assert result["purpose"] == "retirement"

    async def test_vitas_from_keyword(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="I need a VITAS social visit visa")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["visa_type"] == "vitas"

    async def test_tourist_visa(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="tourist visit to Bali")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["visa_type"] == "visa_on_arrival"
        assert result["purpose"] == "tourism"

    async def test_work_indicators_default_kitas(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="I need to work as a chef in Bali")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["visa_type"] == "kitas"
        assert result["purpose"] == "work"

    async def test_default_vitas_for_generic(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="What are my options for staying in Indonesia")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["visa_type"] == "vitas"

    async def test_director_employment_type(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="I am a director and need a KITAS")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["employment_type"] == "director"

    async def test_employee_employment_type(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="employee visa for staff chef")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["employment_type"] == "employee"

    async def test_investor_employment_type(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node
        state = _make_state(query="investor shareholder visa")
        result = await identify_visa_type_node(state, MagicMock())
        assert result["employment_type"] == "shareholder"

    async def test_kg_override_with_db_pool(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node

        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = "visa:kitap"
        mock_pool = MagicMock()

        class _Ctx:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_Ctx())

        state = _make_state(query="I am a director looking for a visa")
        result = await identify_visa_type_node(state, MagicMock(), db_pool=mock_pool)
        assert result["visa_type"] == "kitap"  # KG overrode

    async def test_kg_lookup_failure_graceful(self):
        from backend.services.rag.kg_subgraph_visa import identify_visa_type_node

        mock_conn = AsyncMock()
        mock_conn.fetchval.side_effect = RuntimeError("DB error")
        mock_pool = MagicMock()

        class _Ctx:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_Ctx())

        state = _make_state(query="director KITAS visa")
        result = await identify_visa_type_node(state, MagicMock(), db_pool=mock_pool)
        assert result["visa_type"] == "kitas"


# ---------------------------------------------------------------------------
# Node 2: check_rptka_requirements_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckRPTKARequirementsNode:
    async def test_skips_when_not_required(self):
        from backend.services.rag.kg_subgraph_visa import check_rptka_requirements_node
        state = _make_state(requires_rptka=False)
        result = await check_rptka_requirements_node(state, AsyncMock())
        assert len(result.get("visa_requirements", [])) == 0

    async def test_uses_kg_data(self):
        from backend.services.rag.kg_subgraph_visa import check_rptka_requirements_node

        conn = AsyncMock()
        conn.fetchrow.return_value = {"entity_id": "rptka:1", "name": "RPTKA", "properties": {"duration": "3-4 weeks", "validity": "5 years"}}
        conn.fetch.return_value = [
            {"req": "Submit application", "dur": None, "val": None},
            {"req": "Pay DKP-TKA", "dur": None, "val": None},
        ]
        pool, _ = _make_pool(conn)

        state = _make_state(requires_rptka=True)
        result = await check_rptka_requirements_node(state, pool)
        reqs = result["visa_requirements"]
        assert len(reqs) == 1
        assert reqs[0]["requirement_type"] == "rptka"
        assert len(reqs[0]["steps"]) >= 2

    async def test_uses_fallback_when_kg_empty(self):
        from backend.services.rag.kg_subgraph_visa import check_rptka_requirements_node

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        conn.fetch.return_value = []
        pool, _ = _make_pool(conn)

        state = _make_state(requires_rptka=True)
        result = await check_rptka_requirements_node(state, pool)
        reqs = result["visa_requirements"]
        assert len(reqs) == 1
        assert len(reqs[0]["steps"]) == 5

    async def test_kg_query_failure_uses_fallback(self):
        from backend.services.rag.kg_subgraph_visa import check_rptka_requirements_node

        pool = MagicMock()
        pool.acquire.side_effect = RuntimeError("DB connection failed")

        state = _make_state(requires_rptka=True)
        result = await check_rptka_requirements_node(state, pool)
        reqs = result["visa_requirements"]
        assert len(reqs) == 1
        assert len(reqs[0]["steps"]) == 5


# ---------------------------------------------------------------------------
# Node 3: get_visa_requirements_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetVisaRequirementsNode:
    async def test_uses_kg_data(self):
        from backend.services.rag.kg_subgraph_visa import get_visa_requirements_node

        conn = AsyncMock()
        conn.fetchrow.side_effect = [
            {"entity_id": "kitas:1", "name": "KITAS", "properties": {"documents": ["Passport"], "processing_time": "14 days", "validity": "1 year"}},
            {"dur_desc": "12 months", "dur_name": "KITAS Duration"},
        ]
        conn.fetch.side_effect = [
            [{"name": "Health Insurance", "entity_type": "document", "properties": {}}],
            [{"name": "PNBP", "amount": "3500000", "currency": "IDR", "fee_desc": "PNBP Fee"}],
        ]
        pool, _ = _make_pool(conn)

        state = _make_state(visa_type="kitas")
        result = await get_visa_requirements_node(state, pool)
        reqs = result["visa_requirements"]
        assert len(reqs) == 1
        details = reqs[0]["details"]
        assert any("Passport" in d for d in details["documents"])

    async def test_uses_fallback_when_kg_empty(self):
        from backend.services.rag.kg_subgraph_visa import get_visa_requirements_node

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        conn.fetch.return_value = []
        pool, _ = _make_pool(conn)

        state = _make_state(visa_type="kitas")
        result = await get_visa_requirements_node(state, pool)
        reqs = result["visa_requirements"]
        assert len(reqs) == 1
        assert len(reqs[0]["details"]["documents"]) > 0
        assert result["duration_months"] == 12

    async def test_unknown_visa_type(self):
        from backend.services.rag.kg_subgraph_visa import get_visa_requirements_node

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        conn.fetch.return_value = []
        pool, _ = _make_pool(conn)

        state = _make_state(visa_type="unknown")
        result = await get_visa_requirements_node(state, pool)
        assert len(result["visa_requirements"]) == 1


# ---------------------------------------------------------------------------
# Node 4: synthesize_visa_workflow_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSynthesizeVisaWorkflowNode:
    async def test_kitas_work_visa_workflow(self):
        from backend.services.rag.kg_subgraph_visa import synthesize_visa_workflow_node

        state = _make_state(
            visa_type="kitas",
            requires_rptka=True,
            duration_months=12,
            kg_sources_used=2,
        )

        from backend.services.rag.confidence import ConfidenceBreakdown
        breakdown = ConfidenceBreakdown(overall=0.82)

        with patch("backend.services.rag.confidence.calculate_subgraph_confidence", return_value=breakdown):
            result = await synthesize_visa_workflow_node(state)

        wf = result["workflow"]
        assert wf["type"] == "visa_processing"
        assert "kitas" in wf["id"]
        assert len(wf["steps"]) == 5
        assert wf["confidence"] == 0.82

    async def test_kitap_workflow(self):
        from backend.services.rag.kg_subgraph_visa import synthesize_visa_workflow_node
        from backend.services.rag.confidence import ConfidenceBreakdown

        state = _make_state(visa_type="kitap", requires_rptka=False, duration_months=60, kg_sources_used=1)
        breakdown = ConfidenceBreakdown(overall=0.75)

        with patch("backend.services.rag.confidence.calculate_subgraph_confidence", return_value=breakdown):
            result = await synthesize_visa_workflow_node(state)

        assert len(result["workflow"]["steps"]) == 3

    async def test_voa_workflow(self):
        from backend.services.rag.kg_subgraph_visa import synthesize_visa_workflow_node
        from backend.services.rag.confidence import ConfidenceBreakdown

        state = _make_state(visa_type="visa_on_arrival", requires_rptka=False, duration_months=1, kg_sources_used=0)
        breakdown = ConfidenceBreakdown(overall=0.60)

        with patch("backend.services.rag.confidence.calculate_subgraph_confidence", return_value=breakdown):
            result = await synthesize_visa_workflow_node(state)

        assert len(result["workflow"]["steps"]) == 1


# ---------------------------------------------------------------------------
# build_visa_subgraph
# ---------------------------------------------------------------------------


class TestBuildVisaSubgraph:
    def test_builds_graph(self):
        from backend.services.rag.kg_subgraph_visa import build_visa_subgraph

        mock_pool = AsyncMock()
        mock_llm = MagicMock()
        graph = build_visa_subgraph(mock_pool, mock_llm)
        # Should be a compiled StateGraph
        assert graph is not None


# ---------------------------------------------------------------------------
# Fallback data validation
# ---------------------------------------------------------------------------


class TestFallbackData:
    def test_all_visa_types_have_fallback(self):
        from backend.services.rag.kg_subgraph_visa import _FALLBACK_REQUIREMENTS
        assert "kitas" in _FALLBACK_REQUIREMENTS
        assert "kitap" in _FALLBACK_REQUIREMENTS
        assert "vitas" in _FALLBACK_REQUIREMENTS
        assert "visa_on_arrival" in _FALLBACK_REQUIREMENTS

    def test_fallback_durations(self):
        from backend.services.rag.kg_subgraph_visa import _FALLBACK_DURATION_MONTHS
        assert _FALLBACK_DURATION_MONTHS["kitas"] == 12
        assert _FALLBACK_DURATION_MONTHS["kitap"] == 60
        assert _FALLBACK_DURATION_MONTHS["vitas"] == 2
        assert _FALLBACK_DURATION_MONTHS["visa_on_arrival"] == 1

    def test_rptka_fallback_steps(self):
        from backend.services.rag.kg_subgraph_visa import _FALLBACK_RPTKA_STEPS
        assert len(_FALLBACK_RPTKA_STEPS) == 5

    def test_entity_type_mapping(self):
        from backend.services.rag.kg_subgraph_visa import _VISA_TYPE_TO_ENTITY_TYPE
        assert _VISA_TYPE_TO_ENTITY_TYPE["kitas"] == "kitas"
        assert _VISA_TYPE_TO_ENTITY_TYPE["visa_on_arrival"] == "voa"
