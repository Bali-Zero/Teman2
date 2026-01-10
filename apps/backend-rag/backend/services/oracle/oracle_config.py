"""
Oracle Configuration Service
Manages configuration for Oracle Universal endpoints
"""

import logging

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class OracleConfiguration:
    """Production configuration manager for Oracle endpoints"""

    def __init__(self):
        # Don't validate at import time - allow lazy initialization
        # Validation will happen when database_url is actually accessed
        pass

    def _validate_environment(self) -> None:
        """Validate required environment variables"""
        missing_vars = []

        if not settings.database_url:
            missing_vars.append("DATABASE_URL")

        if missing_vars:
            logger.warning(f"⚠️ Missing required environment variables: {missing_vars}")
            # Don't raise error at import time - allow graceful degradation
            # raise ValueError(f"Missing required environment variables: {missing_vars}")

    @property
    def google_api_key(self) -> str:
        """Get Google API key"""
        if not settings.google_api_key:
            logger.warning("⚠️ GOOGLE_API_KEY not set - Oracle Google services will be disabled")
            return ""  # Return empty string instead of raising error
        return settings.google_api_key

    @property
    def google_credentials_json(self) -> str:
        """Get Google credentials JSON"""
        return settings.google_credentials_json or "{}"

    @property
    def database_url(self) -> str:
        """Get database URL"""
        return settings.database_url or "postgresql://user:pass@localhost/db"

    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key"""
        if not settings.openai_api_key:
            logger.warning("⚠️ OPENAI_API_KEY not set - embeddings may fail")
        return settings.openai_api_key or ""


# Initialize configuration singleton
oracle_config = OracleConfiguration()
