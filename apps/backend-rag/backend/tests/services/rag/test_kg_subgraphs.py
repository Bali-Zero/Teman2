"""
Test Suite for KG Subgraphs (Phase 3)

Tests the 4 domain-specific subgraphs:
- Company Setup Subgraph (PT PMA, Perorangan, CV)
- Visa/Immigration Subgraph (KITAS, KITAP, VITAS)
- Property Acquisition Subgraph (Hak Pakai, HGB, Rental)
- Tax Compliance Subgraph (PPh, PPN, NPWP)

Author: Nuzantara Team
Date: 2026-02-09
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# Import subgraph state types
from backend.services.rag.kg_subgraph_company import (
    CompanyState,
    build_company_subgraph,
    check_pma_eligibility_node,
    get_capital_requirements_node,
    identify_company_type_node,
    synthesize_company_workflow_node,
)
from backend.services.rag.kg_subgraph_property import (
    PropertyState,
    build_property_subgraph,
    get_property_requirements_node,
    identify_property_type_node,
    synthesize_property_workflow_node,
)
from backend.services.rag.kg_subgraph_tax import (
    TaxState,
    build_tax_subgraph,
    calculate_tax_requirements_node,
    get_tax_obligations_node,
    identify_tax_type_node,
    synthesize_tax_workflow_node,
)
from backend.services.rag.kg_subgraph_visa import (
    VisaState,
    build_visa_subgraph,
    check_rptka_requirements_node,
    get_visa_requirements_node,
    identify_visa_type_node,
    synthesize_visa_workflow_node,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_llm():
    """Mock LLM for reasoning tasks."""
    llm = MagicMock()
    llm.model = "claude-sonnet-4-5-20250929"
    return llm


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool."""
    pool = MagicMock()
    conn = AsyncMock()

    # Mock async context manager
    class AsyncContextManager:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=AsyncContextManager())
    return pool, conn


# ============================================================================
# Company Subgraph Tests
# ============================================================================


@pytest.mark.asyncio
async def test_identify_company_type_pt_pma(mock_llm):
    """Test: Identify PT PMA for foreign investor."""
    state: CompanyState = {
        "query": "Apro una PT PMA a Bali",
        "user_context": {"citizenship": "foreign"},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await identify_company_type_node(state, mock_llm)

    assert result["company_type"] == "pt_pma"
    assert result["is_foreign_investor"] is True


@pytest.mark.asyncio
async def test_identify_company_type_perorangan(mock_llm):
    """Test: Identify Perorangan for Indonesian citizen."""
    state: CompanyState = {
        "query": "Voglio aprire un perorangan",
        "user_context": {"citizenship": "indonesian"},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await identify_company_type_node(state, mock_llm)

    assert result["company_type"] == "perorangan"
    assert result["is_foreign_investor"] is False


@pytest.mark.asyncio
async def test_check_pma_eligibility(mock_db_pool):
    """Test: Check PMA eligibility for KBLI codes."""
    pool, conn = mock_db_pool

    # Mock database response
    conn.fetch = AsyncMock(
        return_value=[
            {
                "entity_id": "kbli:56101",
                "name": "Restoran",
                "properties": {"pma_status": "allowed"},
            }
        ]
    )

    state: CompanyState = {
        "query": "Apro ristorante",
        "user_context": {"citizenship": "foreign"},
        "company_type": "pt_pma",
        "is_foreign_investor": True,
        "kbli_codes": ["kbli:56101"],
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await check_pma_eligibility_node(state, pool)

    assert len(result["licensing_requirements"]) > 0
    pma_req = result["licensing_requirements"][0]
    assert pma_req["requirement_type"] == "pma_eligibility"
    assert pma_req["details"][0]["eligible"] is True


@pytest.mark.asyncio
async def test_get_capital_requirements_pt_pma(mock_db_pool):
    """Test: Get capital requirements for PT PMA (10B IDR)."""
    pool, _ = mock_db_pool

    state: CompanyState = {
        "query": "Apro PT PMA",
        "user_context": {"citizenship": "foreign"},
        "company_type": "pt_pma",
        "is_foreign_investor": True,
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await get_capital_requirements_node(state, pool)

    assert result["capital_amount"] == 10_000_000_000  # 10B IDR
    assert len(result["licensing_requirements"]) > 0
    capital_req = result["licensing_requirements"][-1]
    assert capital_req["requirement_type"] == "capital"
    assert capital_req["details"]["min_capital"] == 10_000_000_000


@pytest.mark.asyncio
async def test_synthesize_company_workflow():
    """Test: Synthesize company workflow with 5 steps."""
    state: CompanyState = {
        "query": "Apro PT PMA",
        "user_context": {"citizenship": "foreign"},
        "company_type": "pt_pma",
        "is_foreign_investor": True,
        "capital_amount": 10_000_000_000,
        "kbli_codes": ["kbli:56101"],
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await synthesize_company_workflow_node(state)

    assert result["workflow"] is not None
    workflow = result["workflow"]
    assert workflow["type"] == "company_setup"
    assert workflow["id"] == "company_setup:pt_pma"
    assert len(workflow["steps"]) >= 4  # At least: choose, capital, register, bank


# ============================================================================
# Visa Subgraph Tests
# ============================================================================


@pytest.mark.asyncio
async def test_identify_visa_type_kitas(mock_llm):
    """Test: Identify KITAS for work visa."""
    state: VisaState = {
        "query": "Ho bisogno di KITAS per lavorare come chef",
        "user_context": {"citizenship": "foreign"},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await identify_visa_type_node(state, mock_llm)

    assert result["visa_type"] == "kitas"
    assert result["purpose"] == "work"
    assert result["employment_type"] == "employee"
    assert result["requires_rptka"] is True


@pytest.mark.asyncio
async def test_identify_visa_type_kitas_with_kg(mock_llm, mock_db_pool):
    """Test: Identify KITAS with KG lookup for employment type."""
    pool, conn = mock_db_pool

    # KG returns that employee employment REQUIRES visa:kitas
    conn.fetchval = AsyncMock(return_value="visa:kitas")

    state: VisaState = {
        "query": "Ho bisogno di un visto per lavorare come employee",
        "user_context": {"citizenship": "foreign"},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await identify_visa_type_node(state, mock_llm, pool)

    assert result["visa_type"] == "kitas"
    assert result["employment_type"] == "employee"
    assert result["requires_rptka"] is True


@pytest.mark.asyncio
async def test_identify_visa_type_kitap(mock_llm):
    """Test: Identify KITAP for retirement."""
    state: VisaState = {
        "query": "Voglio KITAP per retirement",
        "user_context": {"citizenship": "foreign"},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await identify_visa_type_node(state, mock_llm)

    assert result["visa_type"] == "kitap"
    assert result["purpose"] == "retirement"
    assert result["requires_rptka"] is False


@pytest.mark.asyncio
async def test_check_rptka_requirements_from_kg(mock_db_pool):
    """Test: Check RPTKA requirements with KG data."""
    pool, conn = mock_db_pool

    # Mock KG returns real RPTKA data
    conn.fetchrow = AsyncMock(
        return_value={
            "entity_id": "rptka:main",
            "name": "RPTKA",
            "properties": {
                "duration": "3-4 weeks",
                "validity": "Max 5 years",
            },
        }
    )
    conn.fetch = AsyncMock(
        return_value=[
            {
                "req": "Submit RPTKA application via TKA Online",
                "dur": "3-4 weeks",
                "val": "Max 5 years",
            },
            {
                "req": "Pay DKP-TKA compensation",
                "dur": None,
                "val": None,
            },
        ]
    )

    state: VisaState = {
        "query": "KITAS work",
        "user_context": {},
        "visa_type": "kitas",
        "purpose": "work",
        "requires_rptka": True,
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await check_rptka_requirements_node(state, pool)

    assert len(result["visa_requirements"]) > 0
    rptka_req = result["visa_requirements"][0]
    assert rptka_req["requirement_type"] == "rptka"
    assert "Work Permit" in rptka_req["description"]
    assert len(rptka_req["steps"]) == 2  # From KG, not fallback
    assert rptka_req["duration"] == "3-4 weeks"


@pytest.mark.asyncio
async def test_check_rptka_requirements_fallback(mock_db_pool):
    """Test: Check RPTKA falls back to hardcoded when KG is empty."""
    pool, conn = mock_db_pool

    # KG returns no data
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    state: VisaState = {
        "query": "KITAS work",
        "user_context": {},
        "visa_type": "kitas",
        "purpose": "work",
        "requires_rptka": True,
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await check_rptka_requirements_node(state, pool)

    assert len(result["visa_requirements"]) > 0
    rptka_req = result["visa_requirements"][0]
    assert rptka_req["requirement_type"] == "rptka"
    assert len(rptka_req["steps"]) == 5  # Fallback has 5 hardcoded steps


@pytest.mark.asyncio
async def test_get_visa_requirements_from_kg(mock_db_pool):
    """Test: Get KITAS requirements from KG nodes/edges."""
    pool, conn = mock_db_pool

    # Mock KG visa node
    conn.fetchrow = AsyncMock(
        side_effect=[
            {
                "entity_id": "kitas:main",
                "name": "KITAS",
                "properties": {
                    "documents": ["Passport", "E-Visa approval", "Sponsorship letter"],
                    "processing_time": "14-30 days",
                    "validity": "1-2 years",
                },
            },
            # dur_row (HAS_DURATION query)
            {"dur_desc": "1-2 years (renewable)", "dur_name": "KITAS validity"},
        ]
    )

    # Mock REQUIRES and HAS_FEE queries
    conn.fetch = AsyncMock(
        side_effect=[
            # REQUIRES edges (documents)
            [
                {
                    "name": "Employment contract",
                    "entity_type": "dokumen",
                    "properties": {},
                },
            ],
            # HAS_FEE edges
            [
                {
                    "name": "PNBP",
                    "amount": "3500000",
                    "currency": "IDR",
                    "fee_desc": "PNBP",
                },
            ],
        ]
    )

    state: VisaState = {
        "query": "KITAS",
        "user_context": {},
        "visa_type": "kitas",
        "purpose": "work",
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await get_visa_requirements_node(state, pool)

    assert len(result["visa_requirements"]) > 0
    visa_req = result["visa_requirements"][-1]
    assert visa_req["visa_type"] == "kitas"
    assert "details" in visa_req
    assert "documents" in visa_req["details"]
    assert "fees" in visa_req["details"]
    assert visa_req["details"]["fees"]["PNBP"] == 3_500_000  # IDR from KG
    assert result.get("kg_sources_used", 0) > 0


@pytest.mark.asyncio
async def test_get_visa_requirements_fallback(mock_db_pool):
    """Test: Get KITAS requirements falls back when KG is empty."""
    pool, conn = mock_db_pool

    # KG returns no data
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    state: VisaState = {
        "query": "KITAS",
        "user_context": {},
        "visa_type": "kitas",
        "purpose": "work",
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await get_visa_requirements_node(state, pool)

    assert len(result["visa_requirements"]) > 0
    visa_req = result["visa_requirements"][-1]
    assert visa_req["visa_type"] == "kitas"
    assert "details" in visa_req
    assert "documents" in visa_req["details"]
    assert "fees" in visa_req["details"]
    # Fallback values
    assert visa_req["details"]["fees"]["PNBP"] == 3_500_000  # IDR


@pytest.mark.asyncio
async def test_synthesize_visa_workflow_with_rptka():
    """Test: Synthesize visa workflow with RPTKA step."""
    state: VisaState = {
        "query": "KITAS work",
        "user_context": {},
        "visa_type": "kitas",
        "purpose": "work",
        "requires_rptka": True,
        "duration_months": 12,
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await synthesize_visa_workflow_node(state)

    assert result["workflow"] is not None
    workflow = result["workflow"]
    assert workflow["type"] == "visa_processing"
    assert workflow["id"] == "visa_processing:kitas"
    # Should have RPTKA, VITAS, Entry, Conversion, MERP steps
    assert len(workflow["steps"]) == 5
    # First step should be IMTA TKA (work permit, formerly RPTKA)
    assert workflow["steps"][0]["entity_id"] == "imta_tka"


# ============================================================================
# Property Subgraph Tests
# ============================================================================


@pytest.mark.asyncio
async def test_identify_property_type_hak_pakai(mock_llm):
    """Test: Identify Hak Pakai for foreign buyer."""
    state: PropertyState = {
        "query": "Comprare villa con Hak Pakai",
        "user_context": {"citizenship": "foreign"},
        "current_entities": [],
        "workflow": None,
    }

    result = await identify_property_type_node(state, mock_llm)

    assert result["property_type"] == "hak_pakai"
    assert result["is_foreign_buyer"] is True


@pytest.mark.asyncio
async def test_identify_property_type_hgb(mock_llm):
    """Test: Identify HGB for Indonesian buyer."""
    state: PropertyState = {
        "query": "HGB property purchase",
        "user_context": {"citizenship": "indonesian"},
        "current_entities": [],
        "workflow": None,
    }

    result = await identify_property_type_node(state, mock_llm)

    assert result["property_type"] == "hgb"
    assert result["is_foreign_buyer"] is False


@pytest.mark.asyncio
async def test_get_property_requirements_hak_pakai(mock_db_pool):
    """Test: Get Hak Pakai requirements."""
    pool, _ = mock_db_pool

    state: PropertyState = {
        "query": "Hak Pakai",
        "user_context": {"citizenship": "foreign"},
        "property_type": "hak_pakai",
        "is_foreign_buyer": True,
        "current_entities": [],
        "workflow": None,
    }

    result = await get_property_requirements_node(state, pool)

    assert len(result["property_requirements"]) > 0
    req = result["property_requirements"][0]
    assert req["requirement_type"] == "ownership"
    assert req["details"]["allowed_for_foreigners"] is True
    assert "30 years" in req["details"]["max_duration"]


@pytest.mark.asyncio
async def test_synthesize_property_workflow():
    """Test: Synthesize property acquisition workflow."""
    state: PropertyState = {
        "query": "Hak Pakai",
        "user_context": {"citizenship": "foreign"},
        "property_type": "hak_pakai",
        "is_foreign_buyer": True,
        "current_entities": [],
        "workflow": None,
    }

    result = await synthesize_property_workflow_node(state)

    assert result["workflow"] is not None
    workflow = result["workflow"]
    assert workflow["type"] == "property_acquisition"
    assert workflow["id"] == "property:hak_pakai"
    assert len(workflow["steps"]) == 7  # Identify, due diligence, negotiate, etc.


# ============================================================================
# Tax Subgraph Tests
# ============================================================================


@pytest.mark.asyncio
async def test_identify_tax_type_pt_pma(mock_llm):
    """Test: Identify corporate tax for PT PMA."""
    state: TaxState = {
        "query": "Tax obligations for PT PMA",
        "user_context": {"business_entity_type": "pt_pma"},
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await identify_tax_type_node(state, mock_llm)

    assert result["business_entity_type"] == "pt_pma"
    assert result["npwp_required"] is True
    assert result["vat_applicable"] is False  # No revenue provided


@pytest.mark.asyncio
async def test_identify_tax_type_with_vat(mock_llm):
    """Test: VAT applicable for revenue > 4.8B IDR."""
    state: TaxState = {
        "query": "Tax obligations",
        "user_context": {},
        "revenue_amount": 5_000_000_000,  # 5B IDR > 4.8B threshold
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await identify_tax_type_node(state, mock_llm)

    assert result["vat_applicable"] is True
    assert result["npwp_required"] is True


@pytest.mark.asyncio
async def test_get_tax_obligations_pt_pma(mock_db_pool):
    """Test: Get tax obligations for PT PMA (PPh 22%, PPh 21, 23, 26, PPN)."""
    pool, _ = mock_db_pool

    state: TaxState = {
        "query": "Tax",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "vat_applicable": True,
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await get_tax_obligations_node(state, pool)

    assert len(result["tax_obligations"]) > 0
    obligations = result["tax_obligations"][0]
    assert "pph_corporate" in obligations["details"]
    assert obligations["details"]["pph_corporate"]["rate"] == 0.22  # 22%
    assert "ppn" in obligations["details"]
    assert obligations["details"]["ppn"]["rate"] == 0.11  # 11% VAT


@pytest.mark.asyncio
async def test_calculate_tax_requirements_with_revenue():
    """Test: Calculate tax amounts for PT PMA with revenue."""
    state: TaxState = {
        "query": "Tax calculation",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "revenue_amount": 10_000_000_000,  # 10B IDR
        "vat_applicable": True,
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await calculate_tax_requirements_node(state)

    assert len(result["tax_obligations"]) > 0
    tax_calc = result["tax_obligations"][-1]
    assert tax_calc["obligation_type"] == "estimated_tax"
    assert "corporate_tax_pph" in tax_calc["calculations"]
    assert "vat_ppn" in tax_calc["calculations"]


@pytest.mark.asyncio
async def test_synthesize_tax_workflow():
    """Test: Synthesize tax compliance workflow."""
    state: TaxState = {
        "query": "Tax obligations",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "vat_applicable": True,
        "capital_amount": 10_000_000_000,
        "current_entities": [],
        "visited_entities": set(),
        "relationship_chains": [],
        "workflow": None,
    }

    result = await synthesize_tax_workflow_node(state)

    assert result["workflow"] is not None
    workflow = result["workflow"]
    assert workflow["type"] == "tax_compliance"
    assert workflow["id"] == "tax_compliance:pt_pma"
    # Should have NPWP, PKP (VAT), bookkeeping, monthly, annual steps
    assert len(workflow["steps"]) >= 4


# ============================================================================
# Integration Tests (Subgraph Compilation)
# ============================================================================


@pytest.mark.asyncio
async def test_build_company_subgraph_compiles(mock_db_pool, mock_llm):
    """Test: CompanySubgraph compiles without errors."""
    pool, _ = mock_db_pool

    subgraph = build_company_subgraph(pool, mock_llm)
    compiled = subgraph.compile()

    assert compiled is not None


@pytest.mark.asyncio
async def test_build_visa_subgraph_compiles(mock_db_pool, mock_llm):
    """Test: VisaSubgraph compiles without errors."""
    pool, _ = mock_db_pool

    subgraph = build_visa_subgraph(pool, mock_llm)
    compiled = subgraph.compile()

    assert compiled is not None


@pytest.mark.asyncio
async def test_build_property_subgraph_compiles(mock_db_pool, mock_llm):
    """Test: PropertySubgraph compiles without errors."""
    pool, _ = mock_db_pool

    subgraph = build_property_subgraph(pool, mock_llm)
    compiled = subgraph.compile()

    assert compiled is not None


@pytest.mark.asyncio
async def test_build_tax_subgraph_compiles(mock_db_pool, mock_llm):
    """Test: TaxSubgraph compiles without errors."""
    pool, _ = mock_db_pool

    subgraph = build_tax_subgraph(pool, mock_llm)
    compiled = subgraph.compile()

    assert compiled is not None
