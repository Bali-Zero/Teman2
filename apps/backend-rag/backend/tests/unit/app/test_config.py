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


class TestPortalInviteUrl:
    """The base URL every client-portal invitation email is built on.

    `FRONTEND_PORTAL_URL` is unset on the production machine (measured on the
    running nuzantara-rag machine 2026-09-10), so the FIELD DEFAULT — not an
    env var — is what `portal_invite.send_invitation` prefixes to
    `InviteService.create_invitation`'s `/portal/register?token=...`. The
    previous default `https://nuzantara-mouth.vercel.app` answers 404 on every
    path and the mouth project carries no such alias, so an invitation the CRM
    reported as "sent" handed the client a dead link and no portal login could
    follow.
    """

    def test_default_is_the_live_portal_domain(self, monkeypatch):
        monkeypatch.delenv("FRONTEND_PORTAL_URL", raising=False)

        settings = Settings(_env_file=None)

        assert settings.frontend_portal_url == "https://my.balizero.com"

    def test_default_is_not_a_vercel_deployment_alias(self, monkeypatch):
        """A deployment alias can stop resolving; the custom domain is the contract.

        This is the regression that matters, and it is about the KIND of host,
        not one spelling: any `*.vercel.app` default puts the invite link on a
        host whose lifetime is a deploy's, not the product's.
        """
        monkeypatch.delenv("FRONTEND_PORTAL_URL", raising=False)

        settings = Settings(_env_file=None)

        assert ".vercel.app" not in settings.frontend_portal_url

    def test_composed_invite_url_matches_the_registration_route(self, monkeypatch):
        """Compose the link exactly as the invite router does.

        `send_invitation` does `settings.frontend_portal_url + result["invite_url"]`,
        and `invite_url` is `/portal/register?token=<token>`. The composed value
        is the one the client clicks.
        """
        monkeypatch.delenv("FRONTEND_PORTAL_URL", raising=False)

        settings = Settings(_env_file=None)
        composed = f"{settings.frontend_portal_url}/portal/register?token=abc123"

        assert composed == "https://my.balizero.com/portal/register?token=abc123"

    def test_env_var_still_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv("FRONTEND_PORTAL_URL", "https://portal.example.test")

        settings = Settings(_env_file=None)

        assert settings.frontend_portal_url == "https://portal.example.test"
