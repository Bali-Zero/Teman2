"""
Unit tests for backend/services/rag/kg_subgraph_company.py

Covers all 4 node functions:
  - identify_company_type_node
  - check_pma_eligibility_node
  - get_capital_requirements_node
  - synthesize_company_workflow_node
Plus: build_company_subgraph construction.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.kg_subgraph_company import (
    build_company_subgraph,
    check_pma_eligibility_node,
    get_capital_requirements_node,
    identify_company_type_node,
    synthesize_company_workflow_node,
)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


def _base_state(**overrides):
    state = {
        "query": "How to set up a company?",
        "user_context": {},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
        "company_type": None,
        "is_foreign_investor": False,
        "capital_amount": None,
        "kbli_codes": [],
        "licensing_requirements": [],
        "shareholders": [],
        "legal_structure_recommendations": [],
    }
    state.update(overrides)
    return state


# ============================================================
# identify_company_type_node
# ============================================================


class TestIdentifyCompanyType:
    @pytest.mark.asyncio
    async def test_pt_pma_in_query(self, mock_llm):
        state = _base_state(query="I want to set up a PT PMA in Bali")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_pma"

    @pytest.mark.asyncio
    async def test_foreign_citizen_company(self, mock_llm):
        state = _base_state(
            query="I want to start a company",
            user_context={"citizenship": "foreign"},
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_pma"
        assert result["is_foreign_investor"] is True

    @pytest.mark.asyncio
    async def test_cv_in_query(self, mock_llm):
        state = _base_state(query="How to register a CV?")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "cv"

    @pytest.mark.asyncio
    async def test_commanditaire_in_query(self, mock_llm):
        state = _base_state(query="commanditaire vennootschap setup")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "cv"

    @pytest.mark.asyncio
    async def test_perorangan_in_query(self, mock_llm):
        state = _base_state(query="I want perorangan business")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "perorangan"

    @pytest.mark.asyncio
    async def test_sole_proprietor_in_query(self, mock_llm):
        state = _base_state(query="sole proprietor registration")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "perorangan"

    @pytest.mark.asyncio
    async def test_pt_lokal_in_query(self, mock_llm):
        state = _base_state(query="setup PT in Jakarta")
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_lokal"

    @pytest.mark.asyncio
    async def test_default_foreign(self, mock_llm):
        state = _base_state(
            query="I want to start a business",
            user_context={"citizenship": "foreign"},
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "pt_pma"

    @pytest.mark.asyncio
    async def test_default_local(self, mock_llm):
        state = _base_state(
            query="I want to start a business",
            user_context={"citizenship": "indonesian"},
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=None)
        assert result["company_type"] == "perorangan"

    @pytest.mark.asyncio
    async def test_kbli_from_query_with_db(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=True)

        state = _base_state(query="KBLI 47111 company setup")
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        assert result["company_type"] == "pt_pma"
        assert result["is_foreign_investor"] is True

    @pytest.mark.asyncio
    async def test_kbli_from_entities_with_db(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=False)

        state = _base_state(
            query="company setup help",
            current_entities=["kbli:47111", "visa:b211"],
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        # KBLI does NOT require pt_pma, so keep heuristic default
        assert result["company_type"] is not None

    @pytest.mark.asyncio
    async def test_kbli_db_failure_uses_heuristic(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(side_effect=Exception("DB error"))

        state = _base_state(query="KBLI 47111 setup")
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        # Falls back to heuristic
        assert result["company_type"] is not None

    @pytest.mark.asyncio
    async def test_kbli_codes_from_state(self, mock_llm, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=True)

        state = _base_state(
            query="company setup",
            kbli_codes=["kbli:62011"],
        )
        result = await identify_company_type_node(state, mock_llm, db_pool=mock_db_pool)
        assert result["company_type"] == "pt_pma"


# ============================================================
# check_pma_eligibility_node
# ============================================================


class TestCheckPMAEligibility:
    @pytest.mark.asyncio
    async def test_skips_non_foreign(self, mock_db_pool):
        state = _base_state(is_foreign_investor=False)
        result = await check_pma_eligibility_node(state, mock_db_pool)
        # Should return state unchanged (no DB call)
        mock_db_pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_kbli_codes_warns(self, mock_db_pool):
        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=[],
            current_entities=[],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        # Should return without error
        assert result is not None

    @pytest.mark.asyncio
    async def test_kbli_allowed(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:47111",
                    "name": "Perdagangan Eceran",
                    "properties": {"pma_status": "allowed"},
                }
            ]
        )

        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=["kbli:47111"],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        assert len(result["licensing_requirements"]) >= 1
        req = result["licensing_requirements"][-1]
        assert req["requirement_type"] == "pma_eligibility"
        assert req["details"][0]["eligible"] is True

    @pytest.mark.asyncio
    async def test_kbli_restricted(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "kbli:01111",
                    "name": "Pertanian Padi",
                    "properties": {"pma_status": "restricted"},
                }
            ]
        )

        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=["kbli:01111"],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        pma_detail = result["licensing_requirements"][-1]["details"][0]
        assert pma_detail["eligible"] is False

    @pytest.mark.asyncio
    async def test_extract_kbli_from_entities(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        state = _base_state(
            is_foreign_investor=True,
            kbli_codes=[],
            current_entities=["kbli:62011"],
        )
        result = await check_pma_eligibility_node(state, mock_db_pool)
        assert result["kbli_codes"] == ["kbli:62011"]


# ============================================================
# get_capital_requirements_node
# ============================================================


class TestGetCapitalRequirements:
    @pytest.mark.asyncio
    async def test_pt_pma_capital(self, mock_db_pool):
        state = _base_state(company_type="pt_pma")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] == 10_000_000_000
        req = result["licensing_requirements"][-1]
        assert req["requirement_type"] == "capital"
        assert req["details"]["min_capital"] == 10_000_000_000

    @pytest.mark.asyncio
    async def test_pt_lokal_capital(self, mock_db_pool):
        state = _base_state(company_type="pt_lokal")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] == 50_000_000

    @pytest.mark.asyncio
    async def test_cv_no_capital(self, mock_db_pool):
        state = _base_state(company_type="cv")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] is None

    @pytest.mark.asyncio
    async def test_perorangan_no_capital(self, mock_db_pool):
        state = _base_state(company_type="perorangan")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] is None

    @pytest.mark.asyncio
    async def test_unknown_type_empty(self, mock_db_pool):
        state = _base_state(company_type="unknown_type")
        result = await get_capital_requirements_node(state, mock_db_pool)
        assert result["capital_amount"] is None


# ============================================================
# synthesize_company_workflow_node
# ============================================================


class TestSynthesizeCompanyWorkflow:
    @pytest.mark.asyncio
    async def test_pt_pma_workflow(self):
        state = _base_state(
            company_type="pt_pma",
            is_foreign_investor=True,
            capital_amount=10_000_000_000,
            kbli_codes=["kbli:62011"],
        )
        result = await synthesize_company_workflow_node(state)
        wf = result["workflow"]
        assert wf is not None
        assert wf["type"] == "company_setup"
        assert wf["id"] == "company_setup:pt_pma"
        assert "PT_PMA" in wf["name"]
        # Should have: structure, capital, registration, licensing, bank
        assert len(wf["steps"]) == 5
        assert wf["confidence"] > 0
        assert "confidence_breakdown" in wf

    @pytest.mark.asyncio
    async def test_cv_workflow_no_capital_step(self):
        state = _base_state(
            company_type="cv",
            is_foreign_investor=False,
            capital_amount=None,
        )
        result = await synthesize_company_workflow_node(state)
        wf = result["workflow"]
        # No capital step, no KBLI step => structure + registration + bank = 3
        assert len(wf["steps"]) == 3
        step_actions = [s["action"] for s in wf["steps"]]
        assert any("CV" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_workflow_with_kbli(self):
        state = _base_state(
            company_type="pt_lokal",
            capital_amount=50_000_000,
            kbli_codes=["kbli:47111"],
        )
        result = await synthesize_company_workflow_node(state)
        step_actions = [s["action"] for s in result["workflow"]["steps"]]
        assert any("KBLI" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_workflow_without_kbli(self):
        state = _base_state(
            company_type="perorangan",
            capital_amount=None,
            kbli_codes=[],
        )
        result = await synthesize_company_workflow_node(state)
        step_actions = [s["action"] for s in result["workflow"]["steps"]]
        assert not any("KBLI" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_confidence_with_db_validation(self):
        state = _base_state(
            company_type="pt_pma",
            is_foreign_investor=True,
            capital_amount=10_000_000_000,
        )
        result = await synthesize_company_workflow_node(state)
        # is_foreign_investor = True means has_db_validation = True
        assert result["workflow"]["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_confidence_without_db_validation(self):
        state = _base_state(
            company_type="cv",
            is_foreign_investor=False,
            capital_amount=None,
        )
        result = await synthesize_company_workflow_node(state)
        assert result["workflow"]["confidence"] > 0


# ============================================================
# build_company_subgraph
# ============================================================


class TestBuildCompanySubgraph:
    def test_build_returns_state_graph(self, mock_db_pool, mock_llm):
        sg = build_company_subgraph(mock_db_pool, mock_llm)
        # Should be a StateGraph instance (not compiled)
        assert sg is not None
        # Verify it has the expected nodes
        assert "identify_company_type" in sg.nodes
        assert "check_pma_eligibility" in sg.nodes
        assert "get_capital_requirements" in sg.nodes
        assert "synthesize_company_workflow" in sg.nodes
