"""Tests for NLM Enrichment Service — HMAC signing, graceful fallback."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.services.oracle.nlm_enrichment_service import NLMEnrichmentService
from backend.utils.hmac_utils import sign_request, verify_signature


@pytest.fixture
def service() -> NLMEnrichmentService:
    return NLMEnrichmentService(
        bridge_url="http://localhost:11301",
        bridge_secret="test-secret-key",
    )


@pytest.mark.asyncio
async def test_query_success(service: NLMEnrichmentService) -> None:
    """Mock successful response, verify answer and citations returned."""
    mock_response = httpx.Response(
        status_code=200,
        json={
            "answer": "The KITAS visa requires a sponsor.",
            "citations": [
                {"source": "immigration_guide.pdf", "page": 12},
            ],
        },
        request=httpx.Request("POST", "http://localhost:11301/nlm/query"),
    )

    with patch.object(
        httpx.AsyncClient,
        "post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await service.query(
            notebook_id="nb-immigration",
            question="What does KITAS require?",
        )

    assert result is not None
    assert result["answer"] == "The KITAS visa requires a sponsor."
    assert len(result["citations"]) == 1
    assert result["citations"][0]["source"] == "immigration_guide.pdf"

    await service.close()


@pytest.mark.asyncio
async def test_query_timeout(service: NLMEnrichmentService) -> None:
    """Mock TimeoutException, verify returns None."""
    with patch.object(
        httpx.AsyncClient,
        "post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("Request timed out"),
    ):
        result = await service.query(
            notebook_id="nb-immigration",
            question="What does KITAS require?",
        )

    assert result is None

    await service.close()


@pytest.mark.asyncio
async def test_query_bridge_down(service: NLMEnrichmentService) -> None:
    """Mock ConnectError, verify returns None."""
    with patch.object(
        httpx.AsyncClient,
        "post",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        result = await service.query(
            notebook_id="nb-immigration",
            question="What does KITAS require?",
        )

    assert result is None

    await service.close()


@pytest.mark.asyncio
async def test_hmac_signature_included(service: NLMEnrichmentService) -> None:
    """Verify X-Bridge-Signature header is sent in the request."""
    mock_response = httpx.Response(
        status_code=200,
        json={"answer": "test", "citations": []},
        request=httpx.Request("POST", "http://localhost:11301/nlm/query"),
    )

    captured_kwargs: dict = {}

    async def capture_post(*args: object, **kwargs: object) -> httpx.Response:
        captured_kwargs.update(kwargs)
        return mock_response

    with patch.object(
        httpx.AsyncClient,
        "post",
        new=capture_post,
    ):
        await service.query(
            notebook_id="nb-immigration",
            question="What does KITAS require?",
        )

    headers = captured_kwargs.get("headers", {})
    assert "X-Bridge-Signature" in headers
    assert len(headers["X-Bridge-Signature"]) == 64  # SHA-256 hex digest

    await service.close()


def test_hmac_cross_verification() -> None:
    """Verify HMAC round-trip: sign -> verify passes; tampered/wrong-secret fails."""
    secret = "test-secret-key"
    payload = json.dumps({"notebook_id": "nb-1", "question": "hello"})

    # Round-trip: sign then verify
    signature = sign_request(payload, secret)
    assert verify_signature(payload, signature, secret) is True

    # Tampered payload fails
    tampered = json.dumps({"notebook_id": "nb-1", "question": "tampered"})
    assert verify_signature(tampered, signature, secret) is False

    # Wrong secret fails
    wrong_secret = "wrong-secret"
    assert verify_signature(payload, signature, wrong_secret) is False
