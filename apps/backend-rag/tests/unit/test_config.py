"""
Unit tests for app.core.config
100% coverage target
"""

import sys
from pathlib import Path

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import Settings


def test_embedding_dimension_openai():
    """Test embedding_dimension is 1536 for OpenAI provider"""
    settings = Settings(embedding_provider="openai")
    assert settings.embedding_dimensions == 1536


def test_embedding_dimension_fallback():
    """Test embedding_dimension is 384 for non-OpenAI providers"""
    # Test sentence-transformers provider (covers line 36)
    settings = Settings(embedding_provider="sentence-transformers")
    assert settings.embedding_dimensions == 384  # sentence-transformers fallback


def test_embedding_dimension_huggingface():
    """Test embedding_dimension is 384 for HuggingFace"""
    settings = Settings(embedding_provider="huggingface")
    assert settings.embedding_dimensions == 384


def test_settings_creation():
    """Test Settings can be instantiated"""
    settings = Settings()
    assert settings is not None
    assert hasattr(settings, "database_url")
    assert hasattr(settings, "jwt_secret_key")


# ============================================================================
# SECURITY: Tests for credential validation
# ============================================================================


def test_jwt_secret_key_default_in_development():
    """Test that default JWT secret is allowed in development"""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        # Create Settings instance - validator will be called automatically
        from app.core.config import Settings

        # When jwt_secret_key is None and ENVIRONMENT=development, should get default
        settings = Settings(jwt_secret_key=None)
        assert settings.jwt_secret_key is not None
        assert len(settings.jwt_secret_key) >= 32


def test_jwt_secret_key_fails_in_production():
    """SECURITY: Test that production fails without explicit JWT_SECRET_KEY"""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        from app.core.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set"):
            Settings(jwt_secret_key=None)


def test_api_keys_default_in_development():
    """Test that default API key is allowed in development"""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
        from app.core.config import Settings

        # When api_keys is None and ENVIRONMENT=development, should get default
        settings = Settings(api_keys=None)
        assert settings.api_keys is not None


def test_api_keys_fails_in_production():
    """SECURITY: Test that production fails without explicit API_KEYS"""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        from app.core.config import Settings

        with pytest.raises(ValueError, match="API_KEYS must be set"):
            Settings(api_keys=None)


def test_openai_api_key_warning_in_production():
    """Test that missing OpenAI API key warns in production"""
    import os
    import warnings
    from unittest.mock import patch

    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        from app.core.config import Settings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Should warn but not fail - create Settings instance
            settings = Settings(openai_api_key=None)
            assert len(w) > 0
            assert any("OPENAI_API_KEY" in str(warning.message) for warning in w)


def test_qdrant_url_fails_in_production():
    """SECURITY: Test that production fails without QDRANT_URL"""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        from app.core.config import Settings

        with pytest.raises(ValueError, match="QDRANT_URL must be set"):
            Settings.validate_qdrant_url(None)
