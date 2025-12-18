"""
Integration Tests for CrossOracleSynthesisService
Tests multi-oracle query orchestration and synthesis
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCrossOracleSynthesisServiceIntegration:
    """Comprehensive integration tests for CrossOracleSynthesisService"""

    @pytest_asyncio.fixture
    async def mock_search_service(self):
        """Create mock search service"""
        mock_service = MagicMock()
        mock_service.search = AsyncMock(
            return_value={
                "results": [{"text": "Test result", "metadata": {"id": "doc1"}}],
                "total": 1,
            }
        )
        return mock_service

    @pytest_asyncio.fixture
    async def mock_zantara_client(self):
        """Create mock Zantara AI client"""
        mock_client = MagicMock()
        mock_client.generate_text = AsyncMock(
            return_value="Synthesized answer with timeline and investment"
        )
        return mock_client

    @pytest_asyncio.fixture
    async def service(self, mock_search_service, mock_zantara_client):
        """Create CrossOracleSynthesisService instance"""
        from services.cross_oracle_synthesis_service import CrossOracleSynthesisService

        return CrossOracleSynthesisService(
            search_service=mock_search_service,
            zantara_ai_client=mock_zantara_client,
        )

    def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.search_service is not None

    @pytest.mark.asyncio
    async def test_synthesize_business_setup(self, service):
        """Test synthesizing business setup scenario"""
        result = await service.synthesize(
            query="I want to open a restaurant in Canggu",
        )

        assert result is not None
        assert result.scenario_type == "business_setup"
        assert len(result.oracles_consulted) > 0

    @pytest.mark.asyncio
    async def test_synthesize_visa_application(self, service):
        """Test synthesizing visa application scenario"""
        result = await service.synthesize(
            query="How to get a work permit KITAS?",
        )

        assert result is not None
        assert result.scenario_type == "visa_application"

    @pytest.mark.asyncio
    async def test_synthesize_property_investment(self, service):
        """Test synthesizing property investment scenario"""
        result = await service.synthesize(
            query="I want to buy property in Bali",
        )

        assert result is not None
        assert result.scenario_type == "property_investment"

    @pytest.mark.asyncio
    async def test_synthesize_tax_optimization(self, service):
        """Test synthesizing tax optimization scenario"""
        result = await service.synthesize(
            query="How to optimize taxes for my business?",
        )

        assert result is not None
        assert result.scenario_type == "tax_optimization"

    @pytest.mark.asyncio
    async def test_synthesize_compliance_check(self, service):
        """Test synthesizing compliance check scenario"""
        result = await service.synthesize(
            query="What are the compliance requirements for PT PMA?",
        )

        assert result is not None
        assert result.scenario_type == "compliance_check"

    @pytest.mark.asyncio
    async def test_synthesize_generic_query(self, service):
        """Test synthesizing generic query"""
        result = await service.synthesize(
            query="General question about Indonesia",
        )

        assert result is not None
        # Should still synthesize even without specific scenario

    def test_detect_scenario(self, service):
        """Test scenario detection"""
        scenario = service._detect_scenario("I want to open a restaurant")

        assert scenario is not None
        assert scenario == "business_setup"

    def test_detect_scenario_visa(self, service):
        """Test visa scenario detection"""
        scenario = service._detect_scenario("How to get KITAS?")

        assert scenario == "visa_application"

    def test_build_oracle_queries(self, service):
        """Test building oracle queries for scenario"""
        queries = service._build_oracle_queries("business_setup", "open restaurant")

        assert queries is not None
        assert len(queries) > 0
        assert all(q.collection for q in queries)
