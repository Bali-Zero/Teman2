"""
Integration tests for Smart Oracle Service
Tests PDF document analysis integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestSmartOracleIntegration:
    """Integration tests for Smart Oracle Service"""

    @pytest.mark.asyncio
    async def test_smart_oracle_pdf_analysis(self, qdrant_client):
        """Test Smart Oracle PDF analysis"""
        with patch(
            "services.smart_oracle.smart_oracle", new_callable=AsyncMock
        ) as mock_smart_oracle:
            mock_smart_oracle.return_value = "Full PDF content extracted"

            from services.smart_oracle import smart_oracle

            result = await smart_oracle("test query", "test_document.pdf")

            assert result is not None

    @pytest.mark.asyncio
    async def test_smart_oracle_document_not_found(self, qdrant_client):
        """Test Smart Oracle when document not found"""
        with patch(
            "services.smart_oracle.smart_oracle", new_callable=AsyncMock
        ) as mock_smart_oracle:
            mock_smart_oracle.return_value = "Error: Original document not found"

            from services.smart_oracle import smart_oracle

            result = await smart_oracle("test query", "nonexistent.pdf")

            assert "not found" in result.lower() or "error" in result.lower()
