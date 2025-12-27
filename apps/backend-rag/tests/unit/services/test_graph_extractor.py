"""
Comprehensive unit tests for backend/services/graph_extractor.py
Target: 90%+ coverage

Tests cover:
- Initialization
- Successful graph extraction
- JSON parsing edge cases
- Error handling and fallback
- Empty/malformed responses
- Large text truncation
- Various entity and relationship structures
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(backend_path))

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from services.misc.graph_extractor import GraphExtractor, ExtractedGraph


class TestExtractedGraph:
    """Test suite for ExtractedGraph Pydantic model"""

    def test_extracted_graph_creation_success(self):
        """Test creating ExtractedGraph with valid data"""
        entities = [
            {
                "id": "law_12_2024",
                "type": "REGULATION",
                "name": "Law 12/2024",
                "description": "Immigration law",
            }
        ]
        relationships = [
            {"source": "law_12_2024", "target": "visa_b211", "type": "DEFINES", "strength": 0.9}
        ]

        graph = ExtractedGraph(entities=entities, relationships=relationships)

        assert graph.entities == entities
        assert graph.relationships == relationships

    def test_extracted_graph_empty_lists(self):
        """Test ExtractedGraph with empty entities and relationships"""
        graph = ExtractedGraph(entities=[], relationships=[])

        assert graph.entities == []
        assert graph.relationships == []

    def test_extracted_graph_validation_error(self):
        """Test ExtractedGraph with invalid data types"""
        with pytest.raises(ValidationError):
            ExtractedGraph(entities="not a list", relationships=[])

    def test_extracted_graph_dict_conversion(self):
        """Test ExtractedGraph model_dump() method"""
        entities = [{"id": "test", "type": "TEST"}]
        relationships = [{"source": "a", "target": "b", "type": "LINK"}]

        graph = ExtractedGraph(entities=entities, relationships=relationships)
        data = graph.model_dump()

        assert data["entities"] == entities
        assert data["relationships"] == relationships


class TestGraphExtractorInit:
    """Test suite for GraphExtractor initialization"""

    def test_init_success(self):
        """Test GraphExtractor initialization with mock AI client"""
        mock_client = MagicMock()
        extractor = GraphExtractor(ai_client=mock_client)

        assert extractor.ai == mock_client

    def test_init_with_real_client_mock(self):
        """Test initialization with a properly mocked ZantaraAIClient"""
        mock_client = MagicMock()
        mock_client.generate_response = AsyncMock()

        extractor = GraphExtractor(ai_client=mock_client)

        assert hasattr(extractor, "ai")
        assert extractor.ai == mock_client


class TestGraphExtractorExtractFromText:
    """Test suite for extract_from_text method"""

    @pytest.fixture
    def mock_ai_client(self):
        """Create a mock AI client with generate_response method"""
        client = MagicMock()
        client.generate_response = AsyncMock()
        return client

    @pytest.fixture
    def extractor(self, mock_ai_client):
        """Create GraphExtractor instance with mock client"""
        return GraphExtractor(ai_client=mock_ai_client)

    @pytest.mark.asyncio
    async def test_extract_from_text_success(self, extractor, mock_ai_client):
        """Test successful extraction with valid JSON response"""
        # Mock AI response
        response_data = {
            "entities": [
                {
                    "id": "law_12_2024",
                    "type": "REGULATION",
                    "name": "Law 12/2024",
                    "description": "Immigration regulation",
                }
            ],
            "relationships": [
                {
                    "source": "law_12_2024",
                    "target": "visa_b211",
                    "type": "DEFINES",
                    "strength": 0.9,
                }
            ],
        }
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        # Execute
        result = await extractor.extract_from_text("Test legal text about immigration")

        # Verify
        assert isinstance(result, ExtractedGraph)
        assert len(result.entities) == 1
        assert result.entities[0]["id"] == "law_12_2024"
        assert len(result.relationships) == 1
        assert result.relationships[0]["type"] == "DEFINES"

        # Verify AI was called correctly
        mock_ai_client.generate_response.assert_called_once()
        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        assert "prompt" in call_kwargs
        assert "system_prompt" in call_kwargs
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_extract_from_text_with_context(self, extractor, mock_ai_client):
        """Test extraction with additional context"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        context = "This is about visa regulations"
        result = await extractor.extract_from_text("Legal text", context=context)

        # Verify context was included in prompt
        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        assert context in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_extract_from_text_long_text_truncation(self, extractor, mock_ai_client):
        """Test that long text is truncated to 2000 characters"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        # Create text longer than 2000 chars
        long_text = "A" * 3000

        result = await extractor.extract_from_text(long_text)

        # Verify truncation occurred
        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        prompt = call_kwargs["prompt"]
        # The prompt should contain truncated text (2000 chars + "... (truncated)")
        assert "... (truncated)" in prompt
        # Original long text should not be fully in prompt
        assert ("A" * 3000) not in prompt

    @pytest.mark.asyncio
    async def test_extract_from_text_relationships_alias(self, extractor, mock_ai_client):
        """Test extraction handles 'relations' as alias for 'relationships'"""
        # Use 'relations' instead of 'relationships'
        response_data = {
            "entities": [{"id": "test_entity", "type": "TEST"}],
            "relations": [{"source": "a", "target": "b", "type": "LINK"}],
        }
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text")

        # Verify 'relations' was mapped to 'relationships'
        assert len(result.relationships) == 1
        assert result.relationships[0]["type"] == "LINK"

    @pytest.mark.asyncio
    async def test_extract_from_text_empty_response(self, extractor, mock_ai_client):
        """Test extraction with empty entities and relationships"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text")

        assert isinstance(result, ExtractedGraph)
        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_missing_entities_key(self, extractor, mock_ai_client):
        """Test extraction when 'entities' key is missing"""
        response_data = {"relationships": [{"source": "a", "target": "b", "type": "LINK"}]}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text")

        # Should default to empty list
        assert result.entities == []
        assert len(result.relationships) == 1

    @pytest.mark.asyncio
    async def test_extract_from_text_missing_relationships_key(self, extractor, mock_ai_client):
        """Test extraction when both 'relationships' and 'relations' are missing"""
        response_data = {"entities": [{"id": "test", "type": "TEST"}]}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text")

        # Should default to empty list
        assert len(result.entities) == 1
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_invalid_json(self, extractor, mock_ai_client):
        """Test extraction with invalid JSON response"""
        # Return malformed JSON
        mock_ai_client.generate_response.return_value = "{invalid json"

        result = await extractor.extract_from_text("Test text")

        # Should return empty graph on error
        assert isinstance(result, ExtractedGraph)
        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_json_decode_error(self, extractor, mock_ai_client):
        """Test extraction handles JSONDecodeError"""
        # Return non-JSON string
        mock_ai_client.generate_response.return_value = "This is not JSON at all"

        result = await extractor.extract_from_text("Test text")

        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_ai_exception(self, extractor, mock_ai_client):
        """Test extraction handles AI client exceptions"""
        # AI client raises exception
        mock_ai_client.generate_response.side_effect = Exception("API Error")

        result = await extractor.extract_from_text("Test text")

        # Should return empty graph
        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_connection_error(self, extractor, mock_ai_client):
        """Test extraction handles connection errors"""
        mock_ai_client.generate_response.side_effect = ConnectionError("Network error")

        result = await extractor.extract_from_text("Test text")

        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_timeout_error(self, extractor, mock_ai_client):
        """Test extraction handles timeout errors"""
        mock_ai_client.generate_response.side_effect = TimeoutError("Request timeout")

        result = await extractor.extract_from_text("Test text")

        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_value_error(self, extractor, mock_ai_client):
        """Test extraction handles ValueError from AI client"""
        mock_ai_client.generate_response.side_effect = ValueError("Invalid parameter")

        result = await extractor.extract_from_text("Test text")

        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_complex_entities(self, extractor, mock_ai_client):
        """Test extraction with multiple complex entities"""
        response_data = {
            "entities": [
                {
                    "id": "law_12_2024",
                    "type": "REGULATION",
                    "name": "Immigration Law 12/2024",
                    "description": "Primary immigration regulation",
                },
                {
                    "id": "visa_b211",
                    "type": "VISA",
                    "name": "B211 Visa",
                    "description": "Social-cultural visa",
                },
                {
                    "id": "ditjen_imigrasi",
                    "type": "AGENCY",
                    "name": "Directorate General of Immigration",
                    "description": "Issuing authority",
                },
            ],
            "relationships": [
                {
                    "source": "law_12_2024",
                    "target": "visa_b211",
                    "type": "DEFINES",
                    "strength": 1.0,
                },
                {
                    "source": "visa_b211",
                    "target": "ditjen_imigrasi",
                    "type": "ISSUED_BY",
                    "strength": 1.0,
                },
            ],
        }
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Complex legal text")

        assert len(result.entities) == 3
        assert len(result.relationships) == 2
        assert result.entities[0]["type"] == "REGULATION"
        assert result.entities[1]["type"] == "VISA"
        assert result.entities[2]["type"] == "AGENCY"

    @pytest.mark.asyncio
    async def test_extract_from_text_system_prompt_structure(self, extractor, mock_ai_client):
        """Test that system prompt contains expected instructions"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        await extractor.extract_from_text("Test text")

        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        system_prompt = call_kwargs["system_prompt"]

        # Verify key instructions are present
        assert "Legal Knowledge Graph Architect" in system_prompt
        assert "Indonesian Law" in system_prompt
        assert "REGULATION" in system_prompt
        assert "VISA" in system_prompt
        assert "REQUIREMENT" in system_prompt
        assert "snake_case" in system_prompt
        assert "valid JSON only" in system_prompt

    @pytest.mark.asyncio
    async def test_extract_from_text_user_prompt_structure(self, extractor, mock_ai_client):
        """Test that user prompt is properly formatted"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        text = "Sample legal text"
        context = "Immigration context"

        await extractor.extract_from_text(text, context=context)

        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        user_prompt = call_kwargs["prompt"]

        # Verify prompt structure
        assert "Context:" in user_prompt
        assert context in user_prompt
        assert "Text to Analyze:" in user_prompt
        assert text in user_prompt
        assert "Extract the knowledge graph JSON" in user_prompt

    @pytest.mark.asyncio
    async def test_extract_from_text_empty_string(self, extractor, mock_ai_client):
        """Test extraction with empty string input"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("")

        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_special_characters(self, extractor, mock_ai_client):
        """Test extraction with special characters in text"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        special_text = "Text with special chars: @#$%^&*(){}[]|\\<>?/~`"

        result = await extractor.extract_from_text(special_text)

        # Should handle gracefully
        assert isinstance(result, ExtractedGraph)
        mock_ai_client.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_from_text_unicode_characters(self, extractor, mock_ai_client):
        """Test extraction with Unicode/Indonesian characters"""
        response_data = {
            "entities": [{"id": "uu_imigrasi", "type": "REGULATION", "name": "UU Imigrasi"}],
            "relationships": [],
        }
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        indonesian_text = "Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian"

        result = await extractor.extract_from_text(indonesian_text)

        assert len(result.entities) == 1
        assert result.entities[0]["name"] == "UU Imigrasi"

    @pytest.mark.asyncio
    async def test_extract_from_text_null_values_in_response(self, extractor, mock_ai_client):
        """Test extraction when response contains null values"""
        response_data = {"entities": None, "relationships": None}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text")

        # Should handle None gracefully and default to empty lists
        assert result.entities == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_extract_from_text_nested_data_structures(self, extractor, mock_ai_client):
        """Test extraction with nested data in entities"""
        response_data = {
            "entities": [
                {
                    "id": "complex_entity",
                    "type": "REGULATION",
                    "name": "Complex Reg",
                    "description": "Has nested data",
                    "metadata": {"version": "1.0", "tags": ["immigration", "visa"]},
                }
            ],
            "relationships": [],
        }
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text")

        assert len(result.entities) == 1
        assert "metadata" in result.entities[0]
        assert result.entities[0]["metadata"]["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_extract_from_text_logging_on_error(self, extractor, mock_ai_client):
        """Test that errors are logged properly"""
        mock_ai_client.generate_response.side_effect = Exception("Test error")

        with patch("services.misc.graph_extractor.logger") as mock_logger:
            result = await extractor.extract_from_text("Test text")

            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Graph extraction failed" in error_call
            assert "Test error" in error_call

    @pytest.mark.asyncio
    async def test_extract_from_text_relationships_both_keys_present(self, extractor, mock_ai_client):
        """Test when both 'relationships' and 'relations' keys are present"""
        # 'relationships' should take precedence
        response_data = {
            "entities": [],
            "relationships": [{"source": "a", "target": "b", "type": "PRIMARY"}],
            "relations": [{"source": "x", "target": "y", "type": "SECONDARY"}],
        }
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text")

        # Should use 'relationships' when both present
        assert len(result.relationships) == 1
        assert result.relationships[0]["type"] == "PRIMARY"

    @pytest.mark.asyncio
    async def test_extract_from_text_response_format_json_object(self, extractor, mock_ai_client):
        """Test that response_format is set to json_object"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        await extractor.extract_from_text("Test text")

        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_extract_from_text_empty_context(self, extractor, mock_ai_client):
        """Test extraction with empty context string"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        result = await extractor.extract_from_text("Test text", context="")

        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        assert "Context: " in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_extract_from_text_boundary_truncation(self, extractor, mock_ai_client):
        """Test text truncation exactly at 2000 characters"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        # Exactly 2000 characters
        exact_text = "A" * 2000

        await extractor.extract_from_text(exact_text)

        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        prompt = call_kwargs["prompt"]
        # Should include the full 2000 chars without truncation marker
        assert exact_text in prompt

    @pytest.mark.asyncio
    async def test_extract_from_text_2001_chars_truncation(self, extractor, mock_ai_client):
        """Test text truncation at 2001 characters triggers truncation"""
        response_data = {"entities": [], "relationships": []}
        mock_ai_client.generate_response.return_value = json.dumps(response_data)

        # 2001 characters (1 over limit)
        over_limit_text = "A" * 2001

        await extractor.extract_from_text(over_limit_text)

        call_kwargs = mock_ai_client.generate_response.call_args.kwargs
        prompt = call_kwargs["prompt"]
        # Should be truncated
        assert "... (truncated)" in prompt
        assert over_limit_text not in prompt


class TestGraphExtractorIntegration:
    """Integration-style tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_full_extraction_workflow(self):
        """Test complete extraction workflow from start to finish"""
        mock_client = MagicMock()
        mock_client.generate_response = AsyncMock()

        # Complete realistic response
        response_data = {
            "entities": [
                {
                    "id": "pp_31_2013",
                    "type": "REGULATION",
                    "name": "PP 31/2013",
                    "description": "Immigration regulation",
                },
                {"id": "visa_211", "type": "VISA", "name": "Visa 211", "description": "Tourist visa"},
            ],
            "relationships": [
                {"source": "pp_31_2013", "target": "visa_211", "type": "DEFINES", "strength": 1.0}
            ],
        }
        mock_client.generate_response.return_value = json.dumps(response_data)

        extractor = GraphExtractor(ai_client=mock_client)
        result = await extractor.extract_from_text(
            "PP 31/2013 defines visa 211 requirements", context="Indonesian immigration law"
        )

        # Verify complete workflow
        assert isinstance(result, ExtractedGraph)
        assert len(result.entities) == 2
        assert len(result.relationships) == 1
        assert result.entities[0]["id"] == "pp_31_2013"
        assert result.entities[1]["id"] == "visa_211"
        assert result.relationships[0]["type"] == "DEFINES"
