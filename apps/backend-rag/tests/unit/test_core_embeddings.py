"""
Unit tests for Core Embeddings Module - Multi-provider embedding generation
Comprehensive coverage for OpenAI and Sentence Transformers
"""

from unittest.mock import Mock, patch

import pytest

from backend.core.embeddings import (
    EmbeddingsGenerator,
    create_embeddings_generator,
    generate_embeddings,
)


class TestEmbeddingsGeneratorOpenAI:
    """Test suite for EmbeddingsGenerator with OpenAI provider"""

    @patch("openai.OpenAI")
    def test_init_openai_with_api_key(self, mock_openai):
        """Test initialization with OpenAI provider and API key"""
        mock_settings = Mock()
        mock_settings.embedding_provider = "openai"
        mock_settings.openai_api_key = "test-key"
        mock_settings.embedding_model = "text-embedding-3-small"

        generator = EmbeddingsGenerator(
            api_key="test-key", provider="openai", settings=mock_settings
        )

        assert generator.provider == "openai"
        assert generator.model == "text-embedding-3-small"
        assert generator.dimensions == 1536
        assert generator.api_key == "test-key"

    @patch("openai.OpenAI")
    def test_init_openai_without_api_key_raises(self, mock_openai):
        """Test initialization without API key raises ValueError"""
        mock_settings = Mock()
        mock_settings.embedding_provider = "openai"
        mock_settings.openai_api_key = None

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            EmbeddingsGenerator(provider="openai", settings=mock_settings)

    @patch("openai.OpenAI")
    def test_init_openai_default_model(self, mock_openai):
        """Test OpenAI initialization uses default model"""
        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)

        assert generator.model == "text-embedding-3-small"

    @patch("openai.OpenAI")
    def test_generate_embeddings_openai_single_text(self, mock_openai):
        """Test generating embeddings for single text with OpenAI"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)
        result = generator.generate_embeddings(["Hello world"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()

    @patch("openai.OpenAI")
    def test_generate_embeddings_openai_multiple_texts(self, mock_openai):
        """Test generating embeddings for multiple texts with OpenAI"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2]),
            Mock(embedding=[0.3, 0.4]),
            Mock(embedding=[0.5, 0.6]),
        ]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)
        result = generator.generate_embeddings(["Text 1", "Text 2", "Text 3"])

        assert len(result) == 3
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]
        assert result[2] == [0.5, 0.6]

    @patch("openai.OpenAI")
    def test_generate_embeddings_openai_batching(self, mock_openai):
        """Test OpenAI embedding generation batches large requests"""
        mock_client = Mock()

        # Mock returns variable-length responses based on input
        def create_side_effect(**kwargs):
            batch_size = len(kwargs.get("input", []))
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(batch_size)]
            return mock_response

        mock_client.embeddings.create.side_effect = create_side_effect
        mock_openai.return_value = mock_client

        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)

        # Generate 3000 embeddings (should batch into 2 calls)
        texts = [f"Text {i}" for i in range(3000)]
        result = generator.generate_embeddings(texts)

        # Should make 2 API calls (2048 + 952)
        assert mock_client.embeddings.create.call_count == 2
        assert len(result) == 3000

    @patch("openai.OpenAI")
    def test_generate_single_embedding_openai(self, mock_openai):
        """Test generating single embedding with OpenAI"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)
        result = generator.generate_single_embedding("Hello world")

        assert result == [0.1, 0.2, 0.3]

    @patch("openai.OpenAI")
    def test_generate_query_embedding_openai(self, mock_openai):
        """Test generating query embedding with OpenAI"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2])]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)
        result = generator.generate_query_embedding("search query")

        assert result == [0.1, 0.2]


class TestEmbeddingsGeneratorSentenceTransformers:
    """Test suite for EmbeddingsGenerator with Sentence Transformers provider"""

    def test_init_sentence_transformers_default(self):
        """Test initialization with Sentence Transformers provider"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384

        mock_st_module = Mock()
        mock_st_module.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
            generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)

            assert generator.provider == "sentence-transformers"
            assert generator.model == "sentence-transformers/all-MiniLM-L6-v2"
            assert generator.dimensions == 384

    def test_init_sentence_transformers_custom_model(self):
        """Test initialization with custom Sentence Transformers model"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 768

        mock_st_module = Mock()
        mock_st_module.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
            generator = EmbeddingsGenerator(
                model="custom-model", provider="sentence-transformers", settings=None
            )

            assert generator.model == "custom-model"
            assert generator.dimensions == 768

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embeddings_sentence_transformers(self, mock_st):
        """Test generating embeddings with Sentence Transformers"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = Mock(tolist=lambda: [[0.1, 0.2], [0.3, 0.4]])
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)
        result = generator.generate_embeddings(["Text 1", "Text 2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    @patch("sentence_transformers.SentenceTransformer")
    def test_sentence_transformers_fallback_to_openai(self, mock_st):
        """Test fallback to OpenAI when Sentence Transformers fails"""
        mock_st.side_effect = Exception("Model load error")

        with patch("openai.OpenAI") as mock_openai:
            generator = EmbeddingsGenerator(
                api_key="test-key", provider="sentence-transformers", settings=None
            )

            # Should fallback to OpenAI
            assert generator.provider == "openai"

    def test_sentence_transformers_import_error_fallback(self):
        """Test fallback when sentence-transformers not installed"""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with patch("openai.OpenAI") as mock_openai:
                generator = EmbeddingsGenerator(
                    api_key="test-key", provider="sentence-transformers", settings=None
                )

                # Should fallback to OpenAI
                assert generator.provider == "openai"


class TestEmbeddingsGeneratorCommon:
    """Test suite for common EmbeddingsGenerator functionality"""

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embeddings_empty_list(self, mock_st):
        """Test generating embeddings with empty list"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)
        result = generator.generate_embeddings([])

        assert result == []

    @patch("openai.OpenAI")
    def test_generate_embeddings_error_handling(self, mock_openai):
        """Test error handling in generate_embeddings"""
        mock_client = Mock()
        mock_client.embeddings.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client

        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)

        with pytest.raises(Exception, match="API Error"):
            generator.generate_embeddings(["Text"])

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_batch_embeddings(self, mock_st):
        """Test generate_batch_embeddings alias"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = Mock(tolist=lambda: [[0.1, 0.2]])
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)
        result = generator.generate_batch_embeddings(["Text"])

        assert result == [[0.1, 0.2]]

    @patch("openai.OpenAI")
    def test_get_model_info_openai(self, mock_openai):
        """Test get_model_info for OpenAI provider"""
        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)
        info = generator.get_model_info()

        assert info["provider"] == "openai"
        assert info["model"] == "text-embedding-3-small"
        assert info["dimensions"] == 1536
        assert "Paid" in info["cost"]

    @patch("sentence_transformers.SentenceTransformer")
    def test_get_model_info_sentence_transformers(self, mock_st):
        """Test get_model_info for Sentence Transformers provider"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)
        info = generator.get_model_info()

        assert info["provider"] == "sentence-transformers"
        assert info["dimensions"] == 384
        assert "FREE" in info["cost"]

    def test_default_provider_selection(self):
        """Test default provider selection without settings"""
        with patch("sentence_transformers.SentenceTransformer"):
            generator = EmbeddingsGenerator(settings=None)
            assert generator.provider == "sentence-transformers"

    @patch("openai.OpenAI")
    def test_provider_from_settings(self, mock_openai):
        """Test provider selection from settings"""
        mock_settings = Mock()
        mock_settings.embedding_provider = "openai"
        mock_settings.openai_api_key = "test-key"

        generator = EmbeddingsGenerator(settings=mock_settings)
        assert generator.provider == "openai"


class TestFactoryFunctions:
    """Test suite for factory and convenience functions"""

    @patch("openai.OpenAI")
    def test_create_embeddings_generator(self, mock_openai):
        """Test factory function"""
        generator = create_embeddings_generator(api_key="test-key", provider="openai")

        assert isinstance(generator, EmbeddingsGenerator)
        assert generator.provider == "openai"

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embeddings_convenience_function(self, mock_st):
        """Test convenience function"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = Mock(tolist=lambda: [[0.1, 0.2]])
        mock_st.return_value = mock_model

        result = generate_embeddings(["Text"])

        assert result == [[0.1, 0.2]]


class TestEdgeCases:
    """Test suite for edge cases and error conditions"""

    @patch("openai.OpenAI")
    def test_generate_single_embedding_empty_result(self, mock_openai):
        """Test generate_single_embedding with empty result"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        generator = EmbeddingsGenerator(api_key="test-key", provider="openai", settings=None)
        result = generator.generate_single_embedding("Text")

        assert result == []

    @patch("sentence_transformers.SentenceTransformer")
    def test_sentence_transformers_encode_error(self, mock_st):
        """Test error handling in Sentence Transformers encoding"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.side_effect = Exception("Encoding error")
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)

        with pytest.raises(Exception, match="Encoding error"):
            generator.generate_embeddings(["Text"])

    @patch("openai.OpenAI")
    def test_init_openai_production_without_key(self, mock_openai):
        """Test OpenAI init in production without key raises critical error"""
        mock_settings = Mock()
        mock_settings.embedding_provider = "openai"
        mock_settings.openai_api_key = None
        mock_settings.environment = "production"

        with pytest.raises(ValueError, match="required for OpenAI provider in production"):
            EmbeddingsGenerator(provider="openai", settings=mock_settings)

    @patch("sentence_transformers.SentenceTransformer")
    def test_large_text_batch(self, mock_st):
        """Test handling large batch of texts"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        embeddings_list = [[0.1] * 384 for _ in range(100)]
        mock_model.encode.return_value = Mock(tolist=lambda: embeddings_list)
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)
        texts = [f"Text {i}" for i in range(100)]
        result = generator.generate_embeddings(texts)

        assert len(result) == 100

    @patch("openai.OpenAI")
    def test_custom_model_parameter(self, mock_openai):
        """Test using custom model parameter"""
        generator = EmbeddingsGenerator(
            api_key="test-key", model="text-embedding-ada-002", provider="openai", settings=None
        )

        assert generator.model == "text-embedding-ada-002"

    @patch("sentence_transformers.SentenceTransformer")
    def test_settings_model_override(self, mock_st):
        """Test settings model overrides default"""
        mock_settings = Mock()
        mock_settings.embedding_provider = "sentence-transformers"
        mock_settings.embedding_model = "custom-model-from-settings"

        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(settings=mock_settings)

        assert generator.model == "custom-model-from-settings"


class TestProviderFallback:
    """Test suite for provider fallback behavior"""

    def test_sentence_transformers_both_providers_fail(self):
        """Test when both providers fail"""
        with (
            patch("sentence_transformers.SentenceTransformer", side_effect=Exception("ST Error")),
            patch("openai.OpenAI", side_effect=Exception("OpenAI Error")),
        ):
            with pytest.raises(Exception, match="OpenAI Error"):
                EmbeddingsGenerator(provider="sentence-transformers", settings=None)

    @patch("sentence_transformers.SentenceTransformer")
    def test_progress_bar_for_large_batch(self, mock_st):
        """Test progress bar shown for large batches"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        embeddings_list = [[0.1] * 384 for _ in range(20)]
        mock_model.encode.return_value = Mock(tolist=lambda: embeddings_list)
        mock_st.return_value = mock_model

        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=None)
        texts = [f"Text {i}" for i in range(20)]
        generator.generate_embeddings(texts)

        # Verify encode called with show_progress_bar=True for >10 texts
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs["show_progress_bar"] is True
