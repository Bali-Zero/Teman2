"""
Messaging Identity Service
Maps messaging channel identifiers (phone, telegram_chat_id) to users (team + portal clients).

Enables:
- Cross-channel conversation history (WhatsApp + Telegram + Web unified)
- User recognition across channels (team members + portal clients)
- Direct notifications with correct chat_id

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    MESSAGING IDENTITY SERVICE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  WhatsApp: +628123456789  ──┐                                   │
│                              ├──→  user_id: abc-123             │
│  Telegram: chat_id=98765    ─┘    (from user_profiles)          │
│                                                                  │
│  Supports: Team members + Portal clients (thousands)            │
│  Result: Unified conversation history across ALL channels       │
└─────────────────────────────────────────────────────────────────┘
"""

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class MessagingIdentityService:
    """Maps messaging identifiers to users (team + portal clients) for unified identity."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        """
        Initialize service.

        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool

    async def get_user_by_phone(self, phone: str) -> dict[str, Any] | None:
        """
        Get user ID mapped to a WhatsApp phone number.

        Args:
            phone: WhatsApp phone (normalized, no + prefix)

        Returns:
            Dict with user_id, display_name, verified, or None if not mapped
        """
        # Normalize phone (remove + prefix if present)
        normalized_phone = phone.lstrip("+")

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT user_id, display_name, verified, last_message_at
                    FROM messaging_users
                    WHERE phone = $1 AND channel = 'whatsapp' AND active = TRUE
                    """,
                    normalized_phone,
                )

                if row:
                    logger.info(
                        f"Found user mapping for phone {normalized_phone}: {row['user_id']}",
                    )
                    return dict(row)

                return None

        except asyncpg.PostgresError as e:
            logger.error(f"Database error getting user by phone {normalized_phone}: {e}")
            return None

    async def get_user_by_telegram(self, chat_id: int) -> dict[str, Any] | None:
        """
        Get user ID mapped to a Telegram chat ID.

        Args:
            chat_id: Telegram numeric chat ID

        Returns:
            Dict with user_id, display_name, verified, or None if not mapped
        """
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT user_id, display_name, verified, last_message_at
                    FROM messaging_users
                    WHERE telegram_chat_id = $1 AND channel = 'telegram' AND active = TRUE
                    """,
                    chat_id,
                )

                if row:
                    logger.info(f"Found user mapping for Telegram {chat_id}: {row['user_id']}")
                    return dict(row)

                return None

        except asyncpg.PostgresError as e:
            logger.error(f"Database error getting user by telegram {chat_id}: {e}")
            return None

    async def create_mapping(
        self,
        user_id: str,
        channel: str,
        phone: str | None = None,
        telegram_chat_id: int | None = None,
        display_name: str | None = None,
        verified: bool = False,
    ) -> bool:
        """
        Create new mapping between messaging identifier and user (team member or portal client).

        Args:
            user_id: UUID from user_profiles (team member or portal client)
            channel: 'whatsapp' or 'telegram'
            phone: WhatsApp phone (for WhatsApp channel)
            telegram_chat_id: Telegram chat ID (for Telegram channel)
            display_name: Name from profile (optional)
            verified: Whether association is verified (default: False)

        Returns:
            True if created successfully, False otherwise
        """
        if channel not in ("whatsapp", "telegram"):
            logger.error(f"Invalid channel: {channel}")
            return False

        if channel == "whatsapp" and not phone:
            logger.error("Phone required for WhatsApp channel")
            return False

        if channel == "telegram" and not telegram_chat_id:
            logger.error("telegram_chat_id required for Telegram channel")
            return False

        # Normalize phone if WhatsApp
        if phone:
            phone = phone.lstrip("+")

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO messaging_users (
                        user_id, channel, phone, telegram_chat_id,
                        display_name, verified, last_message_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (phone) WHERE phone IS NOT NULL
                    DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        display_name = EXCLUDED.display_name,
                        verified = EXCLUDED.verified,
                        updated_at = NOW()
                    """,
                    user_id,
                    channel,
                    phone,
                    telegram_chat_id,
                    display_name,
                    verified,
                )

                logger.info(
                    f"Created mapping: {channel} ({phone or telegram_chat_id}) → user {user_id}",
                )
                return True

        except asyncpg.UniqueViolationError:
            logger.warning(f"Mapping already exists for {channel} ({phone or telegram_chat_id})")
            return False
        except asyncpg.PostgresError as e:
            logger.error(f"Database error creating mapping: {e}")
            return False

    async def update_last_message(
        self, phone: str | None = None, telegram_chat_id: int | None = None,
    ) -> bool:
        """
        Update last_message_at timestamp for a user.

        Args:
            phone: WhatsApp phone (if WhatsApp)
            telegram_chat_id: Telegram chat ID (if Telegram)

        Returns:
            True if updated successfully
        """
        if not phone and not telegram_chat_id:
            return False

        try:
            async with self.db_pool.acquire() as conn:
                if phone:
                    normalized_phone = phone.lstrip("+")
                    await conn.execute(
                        """
                        UPDATE messaging_users
                        SET last_message_at = NOW()
                        WHERE phone = $1 AND channel = 'whatsapp'
                        """,
                        normalized_phone,
                    )
                elif telegram_chat_id:
                    await conn.execute(
                        """
                        UPDATE messaging_users
                        SET last_message_at = NOW()
                        WHERE telegram_chat_id = $1 AND channel = 'telegram'
                        """,
                        telegram_chat_id,
                    )

                return True

        except asyncpg.PostgresError as e:
            logger.error(f"Error updating last_message timestamp: {e}")
            return False

    async def get_mappings_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """
        Get all messaging channel mappings for a user (team member or portal client).

        Args:
            user_id: UUID from user_profiles

        Returns:
            List of mappings (phone, telegram_chat_id, channel, verified)
        """
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, channel, phone, telegram_chat_id,
                           display_name, verified, last_message_at
                    FROM messaging_users
                    WHERE user_id = $1 AND active = TRUE
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )

                return [dict(row) for row in rows]

        except asyncpg.PostgresError as e:
            logger.error(f"Error getting mappings for user {user_id}: {e}")
            return []

    async def deactivate_mapping(
        self, phone: str | None = None, telegram_chat_id: int | None = None,
    ) -> bool:
        """
        Deactivate a mapping (soft delete).

        Args:
            phone: WhatsApp phone
            telegram_chat_id: Telegram chat ID

        Returns:
            True if deactivated successfully
        """
        if not phone and not telegram_chat_id:
            return False

        try:
            async with self.db_pool.acquire() as conn:
                if phone:
                    normalized_phone = phone.lstrip("+")
                    await conn.execute(
                        """
                        UPDATE messaging_users
                        SET active = FALSE, updated_at = NOW()
                        WHERE phone = $1 AND channel = 'whatsapp'
                        """,
                        normalized_phone,
                    )
                elif telegram_chat_id:
                    await conn.execute(
                        """
                        UPDATE messaging_users
                        SET active = FALSE, updated_at = NOW()
                        WHERE telegram_chat_id = $1 AND channel = 'telegram'
                        """,
                        telegram_chat_id,
                    )

                logger.info(f"Deactivated mapping for {phone or telegram_chat_id}")
                return True

        except asyncpg.PostgresError as e:
            logger.error(f"Error deactivating mapping: {e}")
            return False


# Singleton instance (initialized on demand)
_messaging_identity_service: MessagingIdentityService | None = None


def get_messaging_identity_service(db_pool: asyncpg.Pool) -> MessagingIdentityService:
    """
    Get or create messaging identity service singleton.

    Args:
        db_pool: Database connection pool

    Returns:
        MessagingIdentityService instance
    """
    global _messaging_identity_service
    if _messaging_identity_service is None:
        _messaging_identity_service = MessagingIdentityService(db_pool)
    return _messaging_identity_service
