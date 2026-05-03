from unittest.mock import patch

import pytest

from backend.services.knowledge_graph.kbli_enricher import KBLIEnricher


@pytest.fixture
def mock_qdrant():
    with patch("backend.services.knowledge_graph.kbli_enricher.QdrantClient") as mock:
        yield mock.return_value


@pytest.mark.asyncio
async def test_enrich_single_code_success(mock_qdrant):
    # Setup
    enricher = KBLIEnricher(retries=3, concurrency=2)
    sample_payload = {"id": "123", "kode_kbli": "47111", "judul": "Retail Test"}

    # Execute
    result = await enricher.enrich_single_code(sample_payload, "High market demand in Bali 2026")

    # Assert
    assert result is True
    assert mock_qdrant.overwrite_payload.called
    args, kwargs = mock_qdrant.overwrite_payload.call_args
    assert kwargs["payload"]["is_enriched"] is True
    assert kwargs["payload"]["market_insights_2026"] == "High market demand in Bali 2026"


@pytest.mark.asyncio
async def test_enrich_single_code_retry_logic(mock_qdrant):
    # Setup
    enricher = KBLIEnricher(retries=2, concurrency=1)
    sample_payload = {"id": "123", "kode_kbli": "47111"}

    # Mock fail then success
    mock_qdrant.overwrite_payload.side_effect = [Exception("Network error"), True]

    # Execute
    result = await enricher.enrich_single_code(sample_payload)

    # Assert
    assert result is True
    assert mock_qdrant.overwrite_payload.call_count == 2


@pytest.mark.asyncio
async def test_concurrency_control():
    enricher = KBLIEnricher(concurrency=2)
    # Verifichiamo che il semaforo sia inizializzato correttamente
    assert enricher.semaphore._value == 2
