"""Proves the real qwen2.5vl:7b pipeline is wired correctly end-to-end.

Skipped by default — it makes a real network call to the fleet's Ollama host and takes
tens of seconds. Run explicitly with:

    RUN_OLLAMA_LIVE=1 PYTHONPATH=. pytest \
        backend/tests/services/garuda_documents/test_ocr_client_live.py -q

Never uses a real client document — `synthetic_passport_biodata_png` renders a clearly
fake specimen.
"""

from __future__ import annotations

import base64
import os

import pytest

from backend.services.garuda_documents.ocr_client import (
    close_ocr_client,
    extract_passport_biodata_dual_pass,
    is_ocr_available,
)
from backend.tests.services.garuda_documents.fixtures.synthetic_images import (
    synthetic_passport_biodata_png,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_OLLAMA_LIVE"),
    reason="live model call — set RUN_OLLAMA_LIVE=1 to run against the real qwen2.5vl:7b",
)


@pytest.fixture(autouse=True)
async def _close_shared_ocr_client_between_tests():
    # `ocr_client` keeps one module-global httpx.AsyncClient across calls (Golden Rule #10:
    # persistent client, closed in lifespan) — correct for one long-lived event loop in
    # production, but pytest-asyncio gives each test its own loop, so a client created in
    # test N's loop is dead by test N+1. Close it after every test in THIS suite so the
    # next test lazily builds a fresh one on its own loop.
    yield
    await close_ocr_client()


@pytest.mark.asyncio
async def test_qwen_vl_is_reachable_and_named_correctly():
    assert await is_ocr_available() is True


@pytest.mark.asyncio
async def test_dual_pass_extraction_actually_calls_the_model_and_reads_something():
    image_b64 = base64.b64encode(synthetic_passport_biodata_png()).decode("ascii")
    result = await extract_passport_biodata_dual_pass(image_b64)

    assert result is not None, "OCR pipeline returned None — model call failed"
    pass_a, pass_b = result
    # This is a synthetic specimen, not a real passport photo, so we assert only that the
    # model actually READ something (proving real invocation) — not exact field accuracy.
    extracted_any = any(v for v in pass_a.values.values()) or any(v for v in pass_b.values.values())
    assert extracted_any, f"model returned no fields at all: pass_a={pass_a} pass_b={pass_b}"
