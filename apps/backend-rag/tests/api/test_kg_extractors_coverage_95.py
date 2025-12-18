"""
API Tests for kg_extractors - Coverage 95% Target
Tests EntityExtractor and RelationshipExtractor

Coverage:
- EntityExtractor.__init__
- EntityExtractor.extract_entities
- RelationshipExtractor.__init__
- RelationshipExtractor.extract_relationships
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestEntityExtractor:
    """Test EntityExtractor class"""

    def test_init_with_ai_client(self):
        """Test EntityExtractor initialization with AI client"""
        from backend.agents.services.kg_extractors import EntityExtractor

        mock_ai_client = MagicMock()
        extractor = EntityExtractor(ai_client=mock_ai_client)

        assert extractor.ai_client == mock_ai_client

    def test_init_without_ai_client(self):
        """Test EntityExtractor initialization without AI client"""
        from backend.agents.services.kg_extractors import EntityExtractor

        with patch("backend.agents.services.kg_extractors.ZANTARA_AVAILABLE", False):
            extractor = EntityExtractor(ai_client=None)

            assert extractor.ai_client is None

    @pytest.mark.asyncio
    async def test_extract_entities_success(self):
        """Test extract_entities with successful extraction"""
        from backend.agents.services.kg_extractors import EntityExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(
            return_value='[{"type": "law", "name": "UU No. 13 Tahun 2003", "canonical_name": "UU Ketenagakerjaan", "context": "mentioned in conversation"}]'
        )

        extractor = EntityExtractor(ai_client=mock_ai_client)

        result = await extractor.extract_entities("Test legal text about UU No. 13 Tahun 2003")

        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["type"] == "law"

    @pytest.mark.asyncio
    async def test_extract_entities_empty_text(self):
        """Test extract_entities with empty text"""
        from backend.agents.services.kg_extractors import EntityExtractor

        mock_ai_client = MagicMock()
        extractor = EntityExtractor(ai_client=mock_ai_client)

        result = await extractor.extract_entities("")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_no_ai_client(self):
        """Test extract_entities without AI client"""
        from backend.agents.services.kg_extractors import EntityExtractor

        extractor = EntityExtractor(ai_client=None)

        result = await extractor.extract_entities("Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_timeout(self):
        """Test extract_entities with timeout"""
        import asyncio

        from backend.agents.services.kg_extractors import EntityExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())

        extractor = EntityExtractor(ai_client=mock_ai_client)

        result = await extractor.extract_entities("Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_json_decode_error(self):
        """Test extract_entities with JSON decode error"""
        from backend.agents.services.kg_extractors import EntityExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(return_value="Invalid JSON response")

        extractor = EntityExtractor(ai_client=mock_ai_client)

        result = await extractor.extract_entities("Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_exception(self):
        """Test extract_entities with exception"""
        from backend.agents.services.kg_extractors import EntityExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(side_effect=Exception("AI error"))

        extractor = EntityExtractor(ai_client=mock_ai_client)

        result = await extractor.extract_entities("Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_entities_long_text(self):
        """Test extract_entities with text longer than MAX_TEXT_LENGTH"""
        from backend.agents.services.kg_extractors import MAX_TEXT_LENGTH, EntityExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(return_value="[]")

        extractor = EntityExtractor(ai_client=mock_ai_client)

        long_text = "A" * (MAX_TEXT_LENGTH + 1000)
        result = await extractor.extract_entities(long_text)

        # Should truncate to MAX_TEXT_LENGTH
        mock_ai_client.generate_text.assert_called_once()
        call_args = mock_ai_client.generate_text.call_args
        # The prompt includes the text snippet, so total length will be longer
        # Just verify the text snippet is truncated
        prompt_text = call_args[1]["prompt"]
        # Find where the text snippet starts
        text_start = prompt_text.find("Text:\n")
        if text_start >= 0:
            text_snippet = prompt_text[text_start + 6 :]  # After "Text:\n"
            # The text snippet should be truncated to MAX_TEXT_LENGTH
            # But we need to account for the fact that the code does text[:MAX_TEXT_LENGTH]
            # So the actual snippet in the prompt should be <= MAX_TEXT_LENGTH
            assert len(text_snippet.split("\n\nExtract:")[0]) <= MAX_TEXT_LENGTH


class TestRelationshipExtractor:
    """Test RelationshipExtractor class"""

    def test_init_with_ai_client(self):
        """Test RelationshipExtractor initialization with AI client"""
        from backend.agents.services.kg_extractors import RelationshipExtractor

        mock_ai_client = MagicMock()
        extractor = RelationshipExtractor(ai_client=mock_ai_client)

        assert extractor.ai_client == mock_ai_client

    def test_init_without_ai_client(self):
        """Test RelationshipExtractor initialization without AI client"""
        from backend.agents.services.kg_extractors import RelationshipExtractor

        with patch("backend.agents.services.kg_extractors.ZANTARA_AVAILABLE", False):
            extractor = RelationshipExtractor(ai_client=None)

            assert extractor.ai_client is None

    @pytest.mark.asyncio
    async def test_extract_relationships_success(self):
        """Test extract_relationships with successful extraction"""
        from backend.agents.services.kg_extractors import RelationshipExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(
            return_value='[{"source": "Entity1", "target": "Entity2", "relationship": "relates_to", "strength": 0.8, "evidence": "text evidence"}]'
        )

        extractor = RelationshipExtractor(ai_client=mock_ai_client)

        entities = [
            {"name": "Entity1", "type": "law"},
            {"name": "Entity2", "type": "topic"},
        ]

        result = await extractor.extract_relationships(entities, "Test text context")

        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["source"] == "Entity1"
        assert result[0]["target"] == "Entity2"

    @pytest.mark.asyncio
    async def test_extract_relationships_insufficient_entities(self):
        """Test extract_relationships with less than 2 entities"""
        from backend.agents.services.kg_extractors import RelationshipExtractor

        extractor = RelationshipExtractor(ai_client=MagicMock())

        result = await extractor.extract_relationships([{"name": "Entity1"}], "Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_no_ai_client(self):
        """Test extract_relationships without AI client"""
        from backend.agents.services.kg_extractors import RelationshipExtractor

        extractor = RelationshipExtractor(ai_client=None)

        entities = [
            {"name": "Entity1", "type": "law"},
            {"name": "Entity2", "type": "topic"},
        ]

        result = await extractor.extract_relationships(entities, "Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_timeout(self):
        """Test extract_relationships with timeout"""
        import asyncio

        from backend.agents.services.kg_extractors import RelationshipExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(side_effect=asyncio.TimeoutError())

        extractor = RelationshipExtractor(ai_client=mock_ai_client)

        entities = [
            {"name": "Entity1", "type": "law"},
            {"name": "Entity2", "type": "topic"},
        ]

        result = await extractor.extract_relationships(entities, "Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_json_decode_error(self):
        """Test extract_relationships with JSON decode error"""
        from backend.agents.services.kg_extractors import RelationshipExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(return_value="Invalid JSON response")

        extractor = RelationshipExtractor(ai_client=mock_ai_client)

        entities = [
            {"name": "Entity1", "type": "law"},
            {"name": "Entity2", "type": "topic"},
        ]

        result = await extractor.extract_relationships(entities, "Test text")

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_relationships_exception(self):
        """Test extract_relationships with exception"""
        from backend.agents.services.kg_extractors import RelationshipExtractor

        mock_ai_client = MagicMock()
        mock_ai_client.generate_text = AsyncMock(side_effect=Exception("AI error"))

        extractor = RelationshipExtractor(ai_client=mock_ai_client)

        entities = [
            {"name": "Entity1", "type": "law"},
            {"name": "Entity2", "type": "topic"},
        ]

        result = await extractor.extract_relationships(entities, "Test text")

        assert result == []
