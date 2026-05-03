"""Tests for the DLP module (zantara_media.security.dlp).

External calls (Ollama/httpx) are mocked so no real network access is needed.
"""

from __future__ import annotations

import pytest
import pytest_asyncio  # noqa: F401 — ensures async support is registered
from unittest.mock import AsyncMock, MagicMock, patch

from zantara_media.security.dlp import DLPResult, dlp_check

# ---------------------------------------------------------------------------
# Fixtures / samples
# ---------------------------------------------------------------------------

PII_SAMPLES = [
    ("nik_number.txt", "Nomor KTP: 3171023456789012 atas nama Budi Santoso"),
    ("passport.txt", "Passport B1234567 expired"),
    ("npwp.txt", "NPWP: 12.345.678.9-001.000"),
    ("phone.txt", "Hubungi kami di +62812345678901"),
    ("akta_docs.txt", "some content"),  # filename trigger only
]

CLEAN_SAMPLES = [
    ("article.txt", "Bali is a beautiful island with rich culture and traditions."),
    ("recipe.txt", "Mix 200g of tempeh with garlic and chili."),
    ("news.txt", "The government announced new tourism regulations for 2026."),
    ("photo_desc.txt", "Sunset at Seminyak Beach, golden hour photography."),
    ("research.txt", "Market analysis shows 15% growth in property sector."),
]


# ---------------------------------------------------------------------------
# Helper: mock a clean Ollama response (no PII found by LLM)
# ---------------------------------------------------------------------------

def _mock_clean_llm_response() -> MagicMock:
    """Return a mock httpx response that says no PII found."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": '{"contains_pii": false, "reason": "No PII detected"}'}
    return mock_resp


def _mock_pii_llm_response() -> MagicMock:
    """Return a mock httpx response that says PII found."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "response": '{"contains_pii": true, "reason": "Contains personal name"}'
    }
    return mock_resp


# ---------------------------------------------------------------------------
# PII samples — should trigger Layer 1 or Layer 2 (no LLM needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nik_number_detected():
    filename, text = PII_SAMPLES[0]
    result = await dlp_check(text, filename)
    assert result.has_pii is True
    assert "NIK" in result.patterns


@pytest.mark.asyncio
async def test_passport_filename_trigger():
    filename, text = PII_SAMPLES[1]
    result = await dlp_check(text, filename)
    assert result.has_pii is True
    # "passport" is both a filename trigger and the content contains PASSPORT_ID pattern
    assert result.has_pii


@pytest.mark.asyncio
async def test_npwp_detected():
    filename, text = PII_SAMPLES[2]
    result = await dlp_check(text, filename)
    assert result.has_pii is True
    assert "NPWP" in result.patterns


@pytest.mark.asyncio
async def test_indonesian_phone_detected():
    filename, text = PII_SAMPLES[3]
    result = await dlp_check(text, filename)
    assert result.has_pii is True
    assert "PHONE_INDONESIAN" in result.patterns


@pytest.mark.asyncio
async def test_akta_filename_trigger():
    filename, text = PII_SAMPLES[4]
    result = await dlp_check(text, filename)
    assert result.has_pii is True
    assert any("FILENAME" in p for p in result.patterns)


# ---------------------------------------------------------------------------
# Clean samples — LLM is called; mock returns no PII
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("filename,text", CLEAN_SAMPLES)
async def test_clean_samples(filename: str, text: str):
    """Clean samples should resolve to has_pii=False (LLM mocked to agree)."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_clean_llm_response())

    with patch("zantara_media.security.dlp.httpx.AsyncClient", return_value=mock_client):
        result = await dlp_check(text, filename)

    assert result.has_pii is False


# ---------------------------------------------------------------------------
# Layer 3 (LLM) only called when layers 1+2 find nothing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_layer_called_only_on_clean_regex():
    """Layer 3 should be invoked for clean text, and NOT for PII text."""
    clean_text = "Bali is a beautiful island."
    clean_filename = "article.txt"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_clean_llm_response())

    with patch("zantara_media.security.dlp.httpx.AsyncClient", return_value=mock_client) as mock_cls:
        await dlp_check(clean_text, clean_filename)
        # LLM should have been called
        assert mock_cls.call_count >= 1

    # Now with PII text — LLM should NOT be called
    pii_text = "Nomor KTP: 3171023456789012"
    mock_client2 = AsyncMock()
    mock_client2.__aenter__ = AsyncMock(return_value=mock_client2)
    mock_client2.__aexit__ = AsyncMock(return_value=False)
    mock_client2.post = AsyncMock(return_value=_mock_clean_llm_response())

    with patch("zantara_media.security.dlp.httpx.AsyncClient", return_value=mock_client2) as mock_cls2:
        result = await dlp_check(pii_text, "some_file.txt")
        assert result.has_pii is True
        # LLM should NOT have been called (layers 1+2 caught it)
        assert mock_cls2.call_count == 0


@pytest.mark.asyncio
async def test_llm_pii_detection():
    """When LLM finds PII, result should reflect it with confidence=0.5."""
    clean_filename = "meeting_notes.txt"
    text_without_regex_pii = "The subject mentioned their details verbally."

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_pii_llm_response())

    with patch("zantara_media.security.dlp.httpx.AsyncClient", return_value=mock_client):
        result = await dlp_check(text_without_regex_pii, clean_filename)

    assert result.has_pii is True
    assert result.confidence == 0.5
    assert "LLM_CLASSIFIER" in result.patterns


@pytest.mark.asyncio
async def test_confidence_high_for_multiple_patterns():
    """Confidence should be 1.0 when 2+ patterns match."""
    text = "KTP: 3171023456789012 dan email: user@example.com"
    result = await dlp_check(text, "document.txt")
    assert result.has_pii is True
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_llm_timeout_fails_open():
    """Timeout in LLM layer should fail open (has_pii=False) for clean content."""
    import httpx as real_httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=real_httpx.TimeoutException("timeout"))

    with patch("zantara_media.security.dlp.httpx.AsyncClient", return_value=mock_client):
        result = await dlp_check("Some clean text with no patterns.", "notes.txt")

    assert result.has_pii is False
