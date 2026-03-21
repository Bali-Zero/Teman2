"""
Unit tests for app/core/config.py database URL resolution.
"""

from backend.app.core.config import Settings


class TestConfig:
    """Tests for settings resolution."""

    def test_database_url_normalizes_postgres_scheme_for_flycast(self, monkeypatch):
        """postgres:// URLs should be normalized to postgresql:// regardless of environment."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgres://backend_rag_v2:secret@nuzantara-postgres.flycast:5432/nuzantara_rag",
        )
        monkeypatch.delenv("DATABASE_URL_LOCAL", raising=False)

        settings = Settings(_env_file=None)

        assert (
            settings.database_url
            == "postgresql://backend_rag_v2:secret@nuzantara-postgres.flycast:5432/nuzantara_rag"
        )

    def test_database_url_keeps_explicit_local_value(self, monkeypatch):
        """An already-local DATABASE_URL should not be replaced."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara",
        )
        monkeypatch.setenv(
            "DATABASE_URL_LOCAL",
            "postgresql://nuzantara:other@localhost:5432/other_db",
        )

        settings = Settings(_env_file=None)

        assert (
            settings.database_url
            == "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
        )

    def test_database_url_normalizes_postgres_scheme(self, monkeypatch):
        """Legacy postgres:// URLs should be normalized."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("API_KEYS", "test-api-key-which-is-long-enough-for-production")
        monkeypatch.setenv("DATABASE_URL", "postgres://user:secret@db.example.com:5432/app")
        monkeypatch.delenv("DATABASE_URL_LOCAL", raising=False)

        settings = Settings(_env_file=None)

        assert settings.database_url == "postgresql://user:secret@db.example.com:5432/app"
