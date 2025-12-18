"""
Unit tests for Embeddings Generator
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.embeddings import EmbeddingsGenerator


@pytest.fixture
def mock_settings():
    """Mock settings"""
    mock = MagicMock()
    mock.embedding_provider = "openai"
    mock.embedding_model = "text-embedding-3-small"
    mock.openai_api_key = "test-key"
    return mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536), MagicMock(embedding=[0.2] * 1536)]
    client.embeddings.create = MagicMock(return_value=mock_response)
    return client


# ============================================================================
# Tests for EmbeddingsGenerator
# ============================================================================


def test_init_openai_provider(mock_settings, mock_openai_client):
    """Test initialization with OpenAI provider"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        assert generator.provider == "openai"
        assert generator.dimensions == 1536
        assert generator.model == "text-embedding-3-small"


def test_init_openai_missing_api_key(mock_settings):
    """Test _init_openai raises ValueError when API key is missing"""
    mock_settings.openai_api_key = None

    with patch("openai.OpenAI"), pytest.raises(ValueError, match="OpenAI API key is required"):
        EmbeddingsGenerator(provider="openai", api_key=None, settings=mock_settings)


def test_init_sentence_transformers(mock_settings):
    """Test initialization with Sentence Transformers"""
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        assert generator.provider == "sentence-transformers"
        assert generator.dimensions == 384


def test_generate_embeddings_openai(mock_settings, mock_openai_client):
    """Test generating embeddings with OpenAI"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        embeddings = generator.generate_embeddings(["text1", "text2"])

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1536
        assert len(embeddings[1]) == 1536
        mock_openai_client.embeddings.create.assert_called_once()


def test_generate_embeddings_empty_list(mock_settings):
    """Test generating embeddings with empty list"""
    mock_transformer = MagicMock()
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        embeddings = generator.generate_embeddings([])
        assert embeddings == []


def test_generate_single_embedding(mock_settings, mock_openai_client):
    """Test generating single embedding"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        embedding = generator.generate_single_embedding("test text")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536


def test_generate_query_embedding(mock_settings, mock_openai_client):
    """Test generating query embedding"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        embedding = generator.generate_query_embedding("test query")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536


def test_get_model_info_openai(mock_settings, mock_openai_client):
    """Test getting model info for OpenAI"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        info = generator.get_model_info()

        assert info["provider"] == "openai"
        assert info["dimensions"] == 1536
        assert "Paid" in info["cost"]


def test_get_model_info_sentence_transformers(mock_settings):
    """Test getting model info for Sentence Transformers"""
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        info = generator.get_model_info()

        assert info["provider"] == "sentence-transformers"
        assert info["dimensions"] == 384
        assert "FREE" in info["cost"]


def test_fallback_to_openai_on_sentence_transformers_error(mock_settings, mock_openai_client):
    """Test fallback to OpenAI when Sentence Transformers fails"""
    with (
        patch(
            "sentence_transformers.SentenceTransformer", side_effect=ImportError("Not available")
        ),
        patch("openai.OpenAI", return_value=mock_openai_client),
    ):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        # Should fallback to OpenAI
        assert generator.provider == "openai"


def test_settings_injection(mock_settings, mock_openai_client):
    """Test that settings can be injected for testing"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        # Create with injected settings
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )

        # Verify it uses injected settings
        assert generator._settings is mock_settings
        assert generator.provider == "openai"


def test_default_settings_when_none_provided(mock_openai_client):
    """Test that default settings are used when None provided"""
    # Mock the module-level settings
    with patch("core.embeddings._default_settings") as mock_default:
        mock_default.embedding_provider = "openai"
        mock_default.openai_api_key = "test-key"
        mock_default.embedding_model = "text-embedding-3-small"

        with patch("openai.OpenAI", return_value=mock_openai_client):
            generator = EmbeddingsGenerator(provider="openai", api_key="test-key")
            assert generator.provider == "openai"


def test_generate_batch_embeddings_alias(mock_settings, mock_openai_client):
    """Test that generate_batch_embeddings is an alias for generate_embeddings"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        embeddings1 = generator.generate_embeddings(["text1", "text2"])
        embeddings2 = generator.generate_batch_embeddings(["text1", "text2"])

        assert embeddings1 == embeddings2
        assert len(embeddings1) == 2
        assert len(embeddings2) == 2


def test_init_with_custom_model_openai(mock_settings, mock_openai_client):
    """Test initialization with custom OpenAI model"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai",
            api_key="test-key",
            model="text-embedding-3-large",
            settings=mock_settings,
        )
        assert generator.model == "text-embedding-3-large"
        assert generator.provider == "openai"


def test_init_with_custom_model_sentence_transformers(mock_settings):
    """Test initialization with custom Sentence Transformers model"""
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=768)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(
            provider="sentence-transformers",
            model="sentence-transformers/all-mpnet-base-v2",
            settings=mock_settings,
        )
        assert generator.model == "sentence-transformers/all-mpnet-base-v2"
        assert generator.dimensions == 768


def test_init_without_settings_no_provider():
    """Test initialization without settings and no provider specified"""
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        with patch("core.embeddings._default_settings", None):
            generator = EmbeddingsGenerator(provider=None, settings=None)
            # Should default to sentence-transformers
            assert generator.provider == "sentence-transformers"


def test_init_sentence_transformers_generic_exception(mock_settings, mock_openai_client):
    """Test generic exception fallback in Sentence Transformers initialization"""
    with (
        patch(
            "sentence_transformers.SentenceTransformer", side_effect=RuntimeError("Generic error")
        ),
        patch("openai.OpenAI", return_value=mock_openai_client),
    ):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        # Should fallback to OpenAI
        assert generator.provider == "openai"


def test_init_sentence_transformers_both_providers_fail(mock_settings):
    """Test when both Sentence Transformers and OpenAI fail"""
    with patch("sentence_transformers.SentenceTransformer", side_effect=RuntimeError("ST error")):
        with patch("openai.OpenAI", side_effect=ValueError("OpenAI error")):
            with pytest.raises(ValueError, match="OpenAI error"):
                EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)


def test_generate_embeddings_sentence_transformers(mock_settings):
    """Test generating embeddings with Sentence Transformers"""
    import numpy as np

    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)
    # Simulate numpy array return
    mock_embeddings = np.array([[0.1] * 384, [0.2] * 384])
    mock_transformer.encode = MagicMock(return_value=mock_embeddings)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        embeddings = generator.generate_embeddings(["text1", "text2"])

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384
        assert isinstance(embeddings[0], list)
        mock_transformer.encode.assert_called_once()


def test_generate_embeddings_sentence_transformers_large_batch(mock_settings):
    """Test Sentence Transformers with large batch (shows progress bar)"""
    import numpy as np

    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)
    # Simulate numpy array return for large batch (>10 items)
    texts = [f"text{i}" for i in range(15)]
    mock_embeddings = np.array([[0.1] * 384] * 15)
    mock_transformer.encode = MagicMock(return_value=mock_embeddings)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        embeddings = generator.generate_embeddings(texts)

        assert len(embeddings) == 15
        # Verify show_progress_bar was True
        call_kwargs = mock_transformer.encode.call_args[1]
        assert call_kwargs["show_progress_bar"] is True


def test_generate_embeddings_sentence_transformers_error(mock_settings):
    """Test error handling in Sentence Transformers generate_embeddings"""
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)
    mock_transformer.encode = MagicMock(side_effect=RuntimeError("Encoding error"))

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)

        with pytest.raises(RuntimeError, match="Encoding error"):
            generator.generate_embeddings(["text1"])


def test_generate_embeddings_openai_error(mock_settings, mock_openai_client):
    """Test error handling in OpenAI generate_embeddings"""
    mock_openai_client.embeddings.create = MagicMock(side_effect=Exception("API error"))

    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )

        with pytest.raises(Exception, match="API error"):
            generator.generate_embeddings(["text1"])


def test_generate_single_embedding_empty_result(mock_settings, mock_openai_client):
    """Test generate_single_embedding when generate_embeddings returns empty list"""
    # Mock to return empty response
    mock_response = MagicMock()
    mock_response.data = []
    mock_openai_client.embeddings.create = MagicMock(return_value=mock_response)

    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        # Override generate_embeddings to return empty list
        generator.generate_embeddings = MagicMock(return_value=[])

        embedding = generator.generate_single_embedding("test")
        assert embedding == []


def test_model_from_settings(mock_settings, mock_openai_client):
    """Test that model is read from settings when not provided"""
    mock_settings.embedding_model = "text-embedding-3-small"

    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        assert generator.model == "text-embedding-3-small"


def test_model_default_when_not_in_settings(mock_openai_client):
    """Test default model when settings doesn't have embedding_model"""
    mock_settings = MagicMock()
    mock_settings.openai_api_key = "test-key"
    # No embedding_model attribute
    del mock_settings.embedding_model

    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        # Should use default
        assert generator.model == "text-embedding-3-small"


def test_sentence_transformers_model_from_settings():
    """Test Sentence Transformers model from settings"""
    mock_settings = MagicMock()
    mock_settings.embedding_provider = "sentence-transformers"
    mock_settings.embedding_model = "sentence-transformers/paraphrase-MiniLM-L6-v2"

    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)

    with patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_transformer
    ) as mock_st:
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        # Verify it used the model from settings
        mock_st.assert_called_once_with("sentence-transformers/paraphrase-MiniLM-L6-v2")


def test_sentence_transformers_default_model():
    """Test Sentence Transformers with default model"""
    mock_settings = MagicMock()
    # No embedding_model attribute
    del mock_settings.embedding_model

    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)

    with patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_transformer
    ) as mock_st:
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        # Should use default model
        mock_st.assert_called_once_with("sentence-transformers/all-MiniLM-L6-v2")


def test_convenience_function_generate_embeddings(mock_openai_client):
    """Test the convenience function generate_embeddings"""
    from core.embeddings import generate_embeddings

    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_openai_client.embeddings.create = MagicMock(return_value=mock_response)

    with patch("openai.OpenAI", return_value=mock_openai_client):
        embeddings = generate_embeddings(["test text"], api_key="test-key")
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536


def test_convenience_function_without_api_key():
    """Test convenience function without API key (uses sentence transformers)"""
    import numpy as np
    from core.embeddings import generate_embeddings

    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)
    mock_embeddings = np.array([[0.1] * 384])
    mock_transformer.encode = MagicMock(return_value=mock_embeddings)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        with patch("core.embeddings._default_settings", None):
            embeddings = generate_embeddings(["test text"])
            assert len(embeddings) == 1
            assert len(embeddings[0]) == 384


def test_api_key_from_settings(mock_openai_client):
    """Test that API key is read from settings when not provided"""
    mock_settings = MagicMock()
    mock_settings.embedding_provider = "openai"
    mock_settings.openai_api_key = "settings-api-key"
    mock_settings.embedding_model = "text-embedding-3-small"

    with patch("openai.OpenAI", return_value=mock_openai_client) as mock_openai_init:
        generator = EmbeddingsGenerator(provider="openai", settings=mock_settings)
        # Verify it used the API key from settings
        mock_openai_init.assert_called_once_with(api_key="settings-api-key")


def test_provider_from_settings(mock_openai_client):
    """Test that provider is determined from settings"""
    mock_settings = MagicMock()
    mock_settings.embedding_provider = "openai"
    mock_settings.openai_api_key = "test-key"
    mock_settings.embedding_model = "text-embedding-3-small"

    with patch("openai.OpenAI", return_value=mock_openai_client):
        # Don't specify provider - should come from settings
        generator = EmbeddingsGenerator(settings=mock_settings)
        assert generator.provider == "openai"


def test_default_provider_sentence_transformers():
    """Test default provider is sentence-transformers when no provider specified"""
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        with patch("core.embeddings._default_settings", None):
            generator = EmbeddingsGenerator()
            assert generator.provider == "sentence-transformers"


def test_get_model_info_includes_all_fields(mock_settings, mock_openai_client):
    """Test that get_model_info returns all expected fields"""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )
        info = generator.get_model_info()

        assert "model" in info
        assert "dimensions" in info
        assert "provider" in info
        assert "cost" in info
        assert info["model"] == "text-embedding-3-small"
        assert info["dimensions"] == 1536
        assert info["provider"] == "openai"
        assert info["cost"] == "Paid (OpenAI API)"


def test_get_model_info_sentence_transformers_cost(mock_settings):
    """Test that Sentence Transformers shows FREE in cost"""
    mock_transformer = MagicMock()
    mock_transformer.get_sentence_embedding_dimension = MagicMock(return_value=384)

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_transformer):
        generator = EmbeddingsGenerator(provider="sentence-transformers", settings=mock_settings)
        info = generator.get_model_info()

        assert info["cost"] == "FREE (Local)"


def test_multiple_calls_to_generate_embeddings(mock_settings):
    """Test multiple calls to generate_embeddings work correctly"""
    # Create a fresh mock client for this test
    client = MagicMock()

    # Setup different responses for each call
    def create_response(model, input):
        response = MagicMock()
        response.data = [MagicMock(embedding=[0.1] * 1536) for _ in input]
        return response

    client.embeddings.create = MagicMock(side_effect=create_response)

    with patch("openai.OpenAI", return_value=client):
        generator = EmbeddingsGenerator(
            provider="openai", api_key="test-key", settings=mock_settings
        )

        # First call
        embeddings1 = generator.generate_embeddings(["text1"])
        assert len(embeddings1) == 1

        # Second call
        embeddings2 = generator.generate_embeddings(["text2", "text3"])
        assert len(embeddings2) == 2

        # Verify client was called multiple times
        assert client.embeddings.create.call_count == 2
