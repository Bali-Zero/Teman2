"""
Shared fixtures for channel adapter unit tests.
"""

import os

import pytest

# Set env vars before any backend imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.channels.base import ChannelResponse


@pytest.fixture
def simple_response() -> ChannelResponse:
    """A basic text-only ChannelResponse."""
    return ChannelResponse(text="Hello, how can I help you?", metadata={})


@pytest.fixture
def response_with_sources() -> ChannelResponse:
    """ChannelResponse with sources attached."""
    return ChannelResponse(
        text="Here is the answer.",
        sources=[
            {"title": "Visa Guide", "url": "https://example.com/visa", "collection": "visa_oracle"},
            {"title": "Tax Info", "url": "https://example.com/tax", "collection": "tax_genius"},
            {"title": "Local Doc", "collection": "legal_unified"},
        ],
        metadata={},
    )


@pytest.fixture
def response_with_workflow() -> ChannelResponse:
    """ChannelResponse with a workflow plan."""
    return ChannelResponse(
        text="Follow these steps.",
        workflow={
            "name": "PT PMA Setup",
            "steps": [
                {"description": "Prepare documents"},
                {"description": "Submit to notary"},
                {"description": "Register at OSS"},
            ],
        },
        metadata={},
    )


@pytest.fixture
def long_response() -> ChannelResponse:
    """ChannelResponse with text longer than most platform limits."""
    return ChannelResponse(text="A" * 5000, metadata={})
