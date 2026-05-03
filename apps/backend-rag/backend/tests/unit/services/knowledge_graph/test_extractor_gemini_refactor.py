"""
Structural + behavioural tests for the extractor_gemini refactor.

Task 4 — TDD: ensure GeminiKGExtractor delegates to the genai_client
facade rather than importing the raw google-genai SDK directly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_extractor_no_longer_imports_genai_directly():
    """Structural check: the file must not import the raw google SDK anymore."""
    import backend.services.knowledge_graph.extractor_gemini as mod

    with open(mod.__file__, encoding="utf-8") as f:
        src = f.read()

    assert "from google import genai" not in src, (
        "extractor_gemini.py still imports 'from google import genai' "
        "— should delegate to genai_client"
    )
    assert "genai.Client(" not in src, (
        "extractor_gemini.py still instantiates genai.Client(...) "
        "— should delegate to get_genai_client()"
    )


@pytest.mark.asyncio
async def test_extractor_delegates_to_genai_client_facade():
    """
    Behaviour check: calling extract() hits the genai_client facade,
    not the google SDK directly.

    The facade's generate_content() is async and returns a dict with key 'text'.
    """
    from backend.services.knowledge_graph.extractor_gemini import GeminiKGExtractor

    fake_client = MagicMock()
    # Facade method is `generate_content` (async), returns dict {"text": ..., ...}
    fake_client.generate_content = AsyncMock(return_value={
        "text": '{"entities": [], "relations": []}',
        "model": "gemini-2.0-flash",
        "usage": {"input_tokens": 50, "output_tokens": 20},
    })

    with patch(
        "backend.services.knowledge_graph.extractor_gemini.get_genai_client",
        return_value=fake_client,
    ):
        extractor = GeminiKGExtractor(model="gemini-2.0-flash")
        result = await extractor.extract(text="Test document about Indonesian law.")

    # The facade method was awaited — refactor is in place.
    fake_client.generate_content.assert_awaited()
    # Result shape is preserved.
    assert result is not None
