"""Seed the disposable my.balizero.com prod-like QA database.

The script is deliberately fail-closed: only a loopback PostgreSQL database
whose name starts with ``my_portal_qa`` is accepted. Credentials arrive via
environment variables and are never logged.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import bcrypt

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_DATABASE_PREFIX = "my_portal_qa"
_SYNTHETIC_EMAIL_DOMAIN = "example.com"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "scripts" / "qa" / "portal_qa_schema.sql"


def validate_qa_database_url(database_url: str) -> str:
    """Return the database name after proving the target is disposable."""
    parsed = urlparse(database_url)
    database_name = parsed.path.lstrip("/")
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("QA seed requires a PostgreSQL DATABASE_URL")
    if (parsed.hostname or "").lower() not in _LOOPBACK_HOSTS:
        raise ValueError("QA seed refuses non-loopback database hosts")
    if not database_name.startswith(_DATABASE_PREFIX):
        raise ValueError(
            f"QA seed database name must start with {_DATABASE_PREFIX!r}",
        )
    return database_name


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def validate_synthetic_email(email: str) -> str:
    """Accept only a reserved, application-valid synthetic email domain."""
    normalized = email.strip().lower()
    if normalized.rpartition("@")[2] != _SYNTHETIC_EMAIL_DOMAIN:
        raise ValueError("Synthetic client email must use example.com")
    return normalized


def validate_synthetic_pin(pin: str) -> str:
    """Accept the same numeric PIN contract enforced by portal registration."""
    normalized = pin.strip()
    if not normalized.isdigit() or not (4 <= len(normalized) <= 6):
        raise ValueError("Synthetic client PIN must be 4-6 digits")
    return normalized


async def seed() -> None:
    """Create the minimal prod-like schema and one synthetic client account."""
    database_url = _required_environment("DATABASE_URL")
    validate_qa_database_url(database_url)
    email = validate_synthetic_email(
        _required_environment("MY_PORTAL_SYNTHETIC_CLIENT_EMAIL"),
    )
    pin = validate_synthetic_pin(
        _required_environment("MY_PORTAL_SYNTHETIC_CLIENT_PIN"),
    )

    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    pin_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = await asyncpg.connect(database_url)
    try:
        async with conn.transaction():
            await conn.execute(schema_sql)
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, nationality)
                VALUES ('Synthetic Portal Client', $1, 'Synthetic')
                ON CONFLICT (email) DO UPDATE
                SET full_name = EXCLUDED.full_name,
                    nationality = EXCLUDED.nationality,
                    deleted_at = NULL,
                    updated_at = NOW()
                RETURNING id
                """,
                email,
            )
            await conn.execute(
                """
                INSERT INTO team_members (
                    email, full_name, name, pin_hash, role, language, active,
                    linked_client_id, portal_access
                )
                VALUES ($1, 'Synthetic Portal Client', 'Synthetic Portal Client',
                        $2, 'client', 'en', TRUE, $3, TRUE)
                ON CONFLICT (email) DO UPDATE
                SET full_name = EXCLUDED.full_name,
                    name = EXCLUDED.name,
                    pin_hash = EXCLUDED.pin_hash,
                    role = 'client',
                    language = 'en',
                    active = TRUE,
                    linked_client_id = EXCLUDED.linked_client_id,
                    portal_access = TRUE,
                    failed_attempts = 0,
                    updated_at = NOW()
                """,
                email,
                pin_hash,
                client_id,
            )
            await conn.execute(
                """
                INSERT INTO client_preferences (
                    client_id, email_notifications, whatsapp_notifications,
                    language, timezone
                )
                VALUES ($1, FALSE, FALSE, 'en', 'Asia/Makassar')
                ON CONFLICT (client_id) DO UPDATE
                SET email_notifications = FALSE,
                    whatsapp_notifications = FALSE,
                    language = 'en',
                    timezone = 'Asia/Makassar',
                    updated_at = NOW()
                """,
                client_id,
            )
    finally:
        await conn.close()

    logger.info("Synthetic portal QA fixture ready in disposable loopback database")


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())


if __name__ == "__main__":
    main()
