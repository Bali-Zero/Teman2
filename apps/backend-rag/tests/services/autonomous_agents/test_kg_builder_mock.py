from unittest.mock import AsyncMock, patch

import pytest

from backend.services.autonomous_agents.knowledge_graph_builder import (
    KnowledgeGraphBuilder,
)


@pytest.fixture
def mock_db_pool():
    pool = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def mock_llm_gateway():
    gateway = AsyncMock()
    gateway.conversational = AsyncMock(
        return_value={
            "text": """
        ```json
        {
            "entities": [
                {"id": "person_marco", "type": "Person", "name": "Marco", "description": "Client"}
            ],
            "relationships": [
                {"source": "person_marco", "target": "company_pt", "type": "OWNS", "description": "Owner"}
            ]
        }
        ```
        """
        }
    )
    return gateway


@pytest.mark.asyncio
async def test_kg_extraction_round_trip(mock_db_pool, mock_llm_gateway):
    """Test full extraction flow: Text -> LLM -> DB Persistence"""

    # Initialize builder with mocks
    builder = KnowledgeGraphBuilder(db_pool=mock_db_pool, llm_gateway=mock_llm_gateway)

    # Mock text input
    text = "Marco owns PT Bali Tech."

    # Execute extraction
    result = await builder.extract_entities(text)

    # Verify extraction results
    assert len(result["entities"]) == 1
    assert result["entities"][0]["name"] == "Marco"
    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["relationship_type"] == "OWNS"

    # Verify DB persistence calls
    assert mock_db_pool.execute.call_count >= 2  # At least 1 entity + 1 relationship

    # Verify metrics recording (mock metrics_collector)
    with patch(
        "backend.services.autonomous_agents.knowledge_graph_builder.metrics_collector"
    ) as mock_metrics:
        await builder.extract_entities(text)
        mock_metrics.record_kg_metrics.assert_called_with(1, 1, "llm")


@pytest.mark.asyncio
async def test_kg_extraction_regex_fallback(mock_db_pool):
    """Test fallback to regex when LLM is unavailable"""

    # Initialize builder WITHOUT LLM
    builder = KnowledgeGraphBuilder(db_pool=mock_db_pool, llm_gateway=None)

    # Input matching regex patterns (KBLI code)
    text = "Business with KBLI 62019 for software development."

    # Execute extraction
    result = await builder.extract_entities(text)

    # Verify regex extraction
    assert len(result["entities"]) >= 1
    assert result["entities"][0]["entity_type"] == "kbli_code"

    # Verify metrics for regex
    with patch(
        "backend.services.autonomous_agents.knowledge_graph_builder.metrics_collector"
    ) as mock_metrics:
        await builder.extract_entities(text)
        mock_metrics.record_kg_metrics.assert_called()
