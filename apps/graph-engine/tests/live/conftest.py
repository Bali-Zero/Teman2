"""Conftest for live-tier tests.

Live tests hit a real LLM provider (Gemini via ``LLMGateway``) and are
**skipped by default** unless an API key is present and pytest is
invoked with ``-m live`` (or without a ``-m`` expression that excludes
the live marker).

Set ``NUZANTARA_GOOGLE_API_KEY`` in the env to enable. All live tests
are expected to complete in under 30 seconds per case.
"""

from __future__ import annotations

import os

import pytest

from nuzantara_graph.services import Services
from nuzantara_graph.services.llm_gateway import LLMGateway


def _api_key() -> str:
    return (
        os.environ.get("NUZANTARA_GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )


@pytest.fixture(scope="session")
def live_services() -> Services:
    """A Services container wired to the real Gemini gateway.

    Skips the test if no API key is present in the env. Uses the default
    mock KG store and vector store — live tests only need a real LLM.
    """
    api_key = _api_key()
    if not api_key:
        pytest.skip(
            "No NUZANTARA_GOOGLE_API_KEY / GOOGLE_API_KEY in env — live test skipped."
        )

    llm = LLMGateway(
        primary_model="gemini-2.0-flash",
        fallback_model="gemini-1.5-flash",
        google_api_key=api_key,
    )
    return Services(llm=llm)
