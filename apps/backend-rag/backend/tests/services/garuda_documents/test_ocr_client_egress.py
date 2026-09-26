"""G-OCR-LOCAL guardrail: OLLAMA_URL must be a loopback destination before a passport
image is ever POSTed. Ledger L1397 — the guardrail was a docstring only; this pins it as
code. No network calls: `client.post` is asserted never-called on the refusal path.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest

from backend.app.core.config import settings
from backend.services.garuda_documents import ocr_client
from backend.services.garuda_documents.ocr_client import (
    OcrEgressBlocked,
    _assert_loopback_ollama_url,
    extract_passport_biodata_dual_pass,
)

_IMAGE_B64 = base64.b64encode(b"not-a-real-image").decode("ascii")


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://127.4.5.6:11434",
        "http://[::1]:11434",
    ],
)
def test_loopback_urls_are_accepted(url: str) -> None:
    _assert_loopback_ollama_url(url)  # must not raise


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:11434",
        "http://93.184.216.34:11434",
        "http://10.0.0.5:11434",
        "http://mini.internal:11434",
    ],
)
def test_non_loopback_urls_are_refused(url: str) -> None:
    with pytest.raises(OcrEgressBlocked):
        _assert_loopback_ollama_url(url)


@pytest.mark.asyncio
async def test_dual_pass_never_posts_when_ollama_url_points_off_box(monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://93.184.216.34:11434", raising=False)

    fake_client = AsyncMock()
    monkeypatch.setattr(ocr_client, "_get_client", lambda: fake_client)

    result = await extract_passport_biodata_dual_pass(_IMAGE_B64)

    assert result is None, "a non-loopback OLLAMA_URL must fail closed, not silently succeed"
    fake_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_dual_pass_still_posts_for_a_loopback_url(monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:11434", raising=False)

    fake_resp = AsyncMock()
    fake_resp.raise_for_status = lambda: None
    fake_resp.json = lambda: {"message": {"content": '{"full_name": "A", "self_confidence": {}}'}}
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(ocr_client, "_get_client", lambda: fake_client)

    result = await extract_passport_biodata_dual_pass(_IMAGE_B64)

    assert result is not None
    assert fake_client.post.await_count == 2  # dual pass, both go through
