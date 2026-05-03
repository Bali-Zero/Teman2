"""
Unit tests for backend/services/rag/kg_subgraph_tax.py

Covers all 4 node functions:
  - identify_tax_type_node
  - get_tax_obligations_node
  - calculate_tax_requirements_node
  - synthesize_tax_workflow_node
Plus: build_tax_subgraph construction.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.kg_subgraph_tax import (
    build_tax_subgraph,
    calculate_tax_requirements_node,
    get_tax_obligations_node,
    identify_tax_type_node,
    synthesize_tax_workflow_node,
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
        "query": "What are my tax obligations?",
        "user_context": {},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
        "business_entity_type": None,
        "revenue_amount": None,
        "employee_count": None,
        "tax_obligations": [],
        "tax_rates": {},
        "vat_applicable": False,
        "npwp_required": False,
    }
    state.update(overrides)
    return state


# ============================================================
# identify_tax_type_node
# ============================================================


class TestIdentifyTaxType:
    @pytest.mark.asyncio
    async def test_pt_pma_from_query(self, mock_llm):
        state = _base_state(query="PT PMA tax obligations")
        result = await identify_tax_type_node(state, mock_llm)
        assert result["business_entity_type"] == "pt_pma"
        assert result["npwp_required"] is True

    @pytest.mark.asyncio
    async def test_cv_from_query(self, mock_llm):
        state = _base_state(query="CV tax requirements")
        result = await identify_tax_type_node(state, mock_llm)
        assert result["business_entity_type"] == "cv"

    @pytest.mark.asyncio
    async def test_perorangan_from_query(self, mock_llm):
        state = _base_state(query="perorangan tax filing")
        result = await identify_tax_type_node(state, mock_llm)
        assert result["business_entity_type"] == "perorangan"

    @pytest.mark.asyncio
    async def test_entity_from_context(self, mock_llm):
        state = _base_state(
            query="what taxes do I pay?",
            user_context={"business_entity_type": "cv"},
        )
        result = await identify_tax_type_node(state, mock_llm)
        assert result["business_entity_type"] == "cv"

    @pytest.mark.asyncio
    async def test_default_pt_pma(self, mock_llm):
        state = _base_state(query="how much tax for my business?")
        result = await identify_tax_type_node(state, mock_llm)
        assert result["business_entity_type"] == "pt_pma"

    @pytest.mark.asyncio
    async def test_pt_in_query(self, mock_llm):
        state = _base_state(query="PT company tax")
        result = await identify_tax_type_node(state, mock_llm)
        assert result["business_entity_type"] == "pt_pma"

    @pytest.mark.asyncio
    async def test_vat_applicable_high_revenue(self, mock_llm):
        state = _base_state(revenue_amount=5_000_000_000)
        result = await identify_tax_type_node(state, mock_llm)
        assert result["vat_applicable"] is True

    @pytest.mark.asyncio
    async def test_vat_not_applicable_low_revenue(self, mock_llm):
        state = _base_state(revenue_amount=1_000_000_000)
        result = await identify_tax_type_node(state, mock_llm)
        assert result["vat_applicable"] is False

    @pytest.mark.asyncio
    async def test_vat_not_applicable_no_revenue(self, mock_llm):
        state = _base_state(revenue_amount=None)
        result = await identify_tax_type_node(state, mock_llm)
        assert result["vat_applicable"] is False

    @pytest.mark.asyncio
    async def test_vat_threshold_exact(self, mock_llm):
        state = _base_state(revenue_amount=4_800_000_000)
        result = await identify_tax_type_node(state, mock_llm)
        assert result["vat_applicable"] is True


# ============================================================
# get_tax_obligations_node
# ============================================================


class TestGetTaxObligations:
    @pytest.mark.asyncio
    async def test_kg_has_data(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_id": "tax:pph_corporate",
                    "name": "PPh Badan",
                    "properties": {"rate": 0.22, "description": "Corporate tax"},
                }
            ]
        )

        state = _base_state(business_entity_type="pt_pma", vat_applicable=True)
        result = await get_tax_obligations_node(state, mock_db_pool)
        obligations = result["tax_obligations"]
        assert len(obligations) >= 1
        kg_entry = [o for o in obligations if o.get("source") == "knowledge_graph"]
        assert len(kg_entry) == 1

    @pytest.mark.asyncio
    async def test_kg_empty_uses_fallback(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        state = _base_state(business_entity_type="pt_pma", vat_applicable=False)
        result = await get_tax_obligations_node(state, mock_db_pool)
        obligations = result["tax_obligations"]
        assert len(obligations) >= 1
        fb_entry = [o for o in obligations if o.get("source") == "hardcoded_fallback"]
        assert len(fb_entry) == 1
        # VAT should be removed from fallback when not applicable
        assert "ppn" not in fb_entry[0]["details"]

    @pytest.mark.asyncio
    async def test_kg_error_uses_fallback(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(side_effect=Exception("DB error"))

        state = _base_state(business_entity_type="cv", vat_applicable=True)
        result = await get_tax_obligations_node(state, mock_db_pool)
        fb_entry = [o for o in result["tax_obligations"] if o.get("source") == "hardcoded_fallback"]
        assert len(fb_entry) == 1
        # VAT should be kept since vat_applicable=True
        assert "ppn" in fb_entry[0]["details"]

    @pytest.mark.asyncio
    async def test_perorangan_fallback(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        state = _base_state(business_entity_type="perorangan", vat_applicable=False)
        result = await get_tax_obligations_node(state, mock_db_pool)
        details = result["tax_obligations"][-1]["details"]
        assert "pph_personal" in details
        assert "ppn" not in details

    @pytest.mark.asyncio
    async def test_kg_sources_counted(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {"entity_id": "tax:pph_21", "name": "PPh 21", "properties": {}},
                {"entity_id": "tax:pph_23", "name": "PPh 23", "properties": {}},
            ]
        )

        state = _base_state(business_entity_type="pt_pma", vat_applicable=False)
        result = await get_tax_obligations_node(state, mock_db_pool)
        assert result.get("kg_sources_used", 0) == 2

    @pytest.mark.asyncio
    async def test_vat_removed_from_kg_when_not_applicable(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(
            return_value=[
                {"entity_id": "tax:ppn", "name": "PPN", "properties": {}},
                {"entity_id": "tax:pph_corporate", "name": "PPh", "properties": {}},
            ]
        )

        state = _base_state(business_entity_type="pt_pma", vat_applicable=False)
        result = await get_tax_obligations_node(state, mock_db_pool)
        kg_entry = [o for o in result["tax_obligations"] if o.get("source") == "knowledge_graph"]
        assert len(kg_entry) == 1
        assert "ppn" not in kg_entry[0]["details"]

    @pytest.mark.asyncio
    async def test_unknown_entity_type_fallback(self, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        state = _base_state(business_entity_type="unknown")
        result = await get_tax_obligations_node(state, mock_db_pool)
        fb = [o for o in result["tax_obligations"] if o.get("source") == "hardcoded_fallback"]
        assert len(fb) == 1
        # Unknown type returns empty dict
        assert fb[0]["details"] == {}


# ============================================================
# calculate_tax_requirements_node
# ============================================================


class TestCalculateTaxRequirements:
    @pytest.mark.asyncio
    async def test_no_revenue_skips(self):
        state = _base_state(business_entity_type="pt_pma", revenue_amount=None)
        result = await calculate_tax_requirements_node(state)
        # No estimated_tax obligation added
        estimated = [o for o in result.get("tax_obligations", []) if o.get("obligation_type") == "estimated_tax"]
        assert len(estimated) == 0

    @pytest.mark.asyncio
    async def test_corporate_tax_calculation(self):
        state = _base_state(
            business_entity_type="pt_pma",
            revenue_amount=1_000_000_000,
            vat_applicable=False,
        )
        result = await calculate_tax_requirements_node(state)
        estimated = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"]
        assert len(estimated) == 1
        calcs = estimated[0]["calculations"]
        # 1B * 0.20 (margin) * 0.22 (rate) = 44M
        assert calcs["corporate_tax_pph"] == pytest.approx(44_000_000)
        assert calcs["monthly_installment_pph25"] == pytest.approx(44_000_000 / 12)
        assert "vat_ppn" not in calcs

    @pytest.mark.asyncio
    async def test_corporate_with_vat(self):
        state = _base_state(
            business_entity_type="pt_pma",
            revenue_amount=5_000_000_000,
            vat_applicable=True,
        )
        result = await calculate_tax_requirements_node(state)
        estimated = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"]
        calcs = estimated[0]["calculations"]
        assert "vat_ppn" in calcs
        assert calcs["vat_ppn"] == pytest.approx(5_000_000_000 * 0.11)

    @pytest.mark.asyncio
    async def test_cv_tax_same_as_corporate(self):
        state = _base_state(
            business_entity_type="cv",
            revenue_amount=2_000_000_000,
            vat_applicable=False,
        )
        result = await calculate_tax_requirements_node(state)
        estimated = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"]
        calcs = estimated[0]["calculations"]
        net_profit = 2_000_000_000 * 0.20
        assert calcs["corporate_tax_pph"] == pytest.approx(net_profit * 0.22)

    @pytest.mark.asyncio
    async def test_perorangan_lowest_bracket(self):
        state = _base_state(
            business_entity_type="perorangan",
            revenue_amount=50_000_000,
            vat_applicable=False,
        )
        result = await calculate_tax_requirements_node(state)
        estimated = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"]
        calcs = estimated[0]["calculations"]
        assert calcs["personal_tax_pph"] == pytest.approx(50_000_000 * 0.05)

    @pytest.mark.asyncio
    async def test_perorangan_second_bracket(self):
        state = _base_state(
            business_entity_type="perorangan",
            revenue_amount=100_000_000,
            vat_applicable=False,
        )
        result = await calculate_tax_requirements_node(state)
        calcs = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"][0]["calculations"]
        expected = 3_000_000 + (100_000_000 - 60_000_000) * 0.15
        assert calcs["personal_tax_pph"] == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_perorangan_third_bracket(self):
        state = _base_state(
            business_entity_type="perorangan",
            revenue_amount=400_000_000,
        )
        result = await calculate_tax_requirements_node(state)
        calcs = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"][0]["calculations"]
        expected = 31_500_000 + (400_000_000 - 250_000_000) * 0.25
        assert calcs["personal_tax_pph"] == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_perorangan_top_bracket(self):
        state = _base_state(
            business_entity_type="perorangan",
            revenue_amount=1_000_000_000,
        )
        result = await calculate_tax_requirements_node(state)
        calcs = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"][0]["calculations"]
        expected = 94_000_000 + (1_000_000_000 - 500_000_000) * 0.30
        assert calcs["personal_tax_pph"] == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_perorangan_with_vat(self):
        state = _base_state(
            business_entity_type="perorangan",
            revenue_amount=5_000_000_000,
            vat_applicable=True,
        )
        result = await calculate_tax_requirements_node(state)
        calcs = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"][0]["calculations"]
        assert "vat_ppn" in calcs

    @pytest.mark.asyncio
    async def test_unknown_entity_empty_calcs(self):
        state = _base_state(
            business_entity_type="unknown",
            revenue_amount=100_000_000,
        )
        result = await calculate_tax_requirements_node(state)
        calcs = [o for o in result["tax_obligations"] if o.get("obligation_type") == "estimated_tax"][0]["calculations"]
        assert calcs == {}


# ============================================================
# synthesize_tax_workflow_node
# ============================================================


class TestSynthesizeTaxWorkflow:
    @pytest.mark.asyncio
    async def test_basic_workflow(self):
        state = _base_state(
            business_entity_type="pt_pma",
            vat_applicable=False,
        )
        result = await synthesize_tax_workflow_node(state)
        wf = result["workflow"]
        assert wf is not None
        assert wf["type"] == "tax_compliance"
        assert wf["id"] == "tax_compliance:pt_pma"
        assert wf["confidence"] > 0

    @pytest.mark.asyncio
    async def test_workflow_with_vat(self):
        state = _base_state(
            business_entity_type="pt_pma",
            vat_applicable=True,
        )
        result = await synthesize_tax_workflow_node(state)
        steps = result["workflow"]["steps"]
        step_actions = [s["action"] for s in steps]
        assert any("VAT" in a or "PKP" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_workflow_without_vat_no_pkp(self):
        state = _base_state(
            business_entity_type="perorangan",
            vat_applicable=False,
        )
        result = await synthesize_tax_workflow_node(state)
        steps = result["workflow"]["steps"]
        step_actions = [s["action"] for s in steps]
        assert not any("PKP" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_corporate_has_monthly_filings(self):
        state = _base_state(
            business_entity_type="pt_pma",
            vat_applicable=False,
        )
        result = await synthesize_tax_workflow_node(state)
        step_actions = [s["action"] for s in result["workflow"]["steps"]]
        assert any("Monthly" in a or "monthly" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_perorangan_no_monthly_filings_without_vat(self):
        state = _base_state(
            business_entity_type="perorangan",
            vat_applicable=False,
        )
        result = await synthesize_tax_workflow_node(state)
        step_actions = [s["action"] for s in result["workflow"]["steps"]]
        # perorangan without VAT has no monthly filings
        assert not any("Monthly" in a or "monthly" in a.lower() for a in step_actions if "filing" in a.lower())

    @pytest.mark.asyncio
    async def test_annual_return_always_present(self):
        for entity in ("pt_pma", "cv", "perorangan"):
            state = _base_state(business_entity_type=entity)
            result = await synthesize_tax_workflow_node(state)
            step_actions = [s["action"] for s in result["workflow"]["steps"]]
            assert any("Annual" in a or "SPT" in a for a in step_actions)

    @pytest.mark.asyncio
    async def test_npwp_always_first_step(self):
        state = _base_state(business_entity_type="pt_pma")
        result = await synthesize_tax_workflow_node(state)
        first_step = result["workflow"]["steps"][0]
        assert "NPWP" in first_step["action"]
        assert first_step["step"] == 1

    @pytest.mark.asyncio
    async def test_confidence_with_kg_sources(self):
        state = _base_state(
            business_entity_type="pt_pma",
            kg_sources_used=5,
        )
        result = await synthesize_tax_workflow_node(state)
        bd = result["workflow"]["confidence_breakdown"]
        # With DB validation (kg_sources > 0), entity_confidence_avg should be 0.8
        assert bd["entity_confidence_avg"] == 0.8

    @pytest.mark.asyncio
    async def test_confidence_without_kg_sources(self):
        state = _base_state(
            business_entity_type="perorangan",
            kg_sources_used=0,
        )
        result = await synthesize_tax_workflow_node(state)
        bd = result["workflow"]["confidence_breakdown"]
        assert bd["entity_confidence_avg"] == 0.5

    @pytest.mark.asyncio
    async def test_cv_monthly_filings(self):
        state = _base_state(
            business_entity_type="cv",
            vat_applicable=True,
        )
        result = await synthesize_tax_workflow_node(state)
        step_actions = [s["action"] for s in result["workflow"]["steps"]]
        # CV + VAT should have monthly filings
        monthly_steps = [a for a in step_actions if "onthly" in a]
        assert len(monthly_steps) == 1


# ============================================================
# build_tax_subgraph
# ============================================================


class TestBuildTaxSubgraph:
    def test_build_returns_state_graph(self, mock_db_pool, mock_llm):
        sg = build_tax_subgraph(mock_db_pool, mock_llm)
        assert sg is not None
        assert "identify_tax_type" in sg.nodes
        assert "get_tax_obligations" in sg.nodes
        assert "calculate_tax_requirements" in sg.nodes
        assert "synthesize_tax_workflow" in sg.nodes
