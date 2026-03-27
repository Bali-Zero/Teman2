"""
Client Identity Resolver - Omnichannel Entity Resolution

Risolve l'identità del cliente attraverso tutti i canali:
- Telegram chat_id → client_id
- WhatsApp phone → client_id
- Email → client_id
- Auto-linking quando cliente fornisce nuova info

Author: Claude Sonnet 4.5
Date: 2026-01-19
"""

import logging
from typing import Any

import asyncpg

from backend.services.crm.validators import normalize_phone_e164

logger = logging.getLogger(__name__)


def normalize_phone(phone: str | None) -> str | None:
    """
    Normalize phone number to E.164 format.

    Delegates to the canonical implementation in validators.py.

    Examples:
        "+62 812 3456 7890" → "+6281234567890"
        "0812-3456-7890" → "+6281234567890"
        "812 3456 7890" → "+6281234567890"
    """
    if not phone:
        return None
    return normalize_phone_e164(phone)


class ClientIdentityResolver:
    """
    Resolve client identity across multiple channels.

    Handles:
    - Finding existing clients by channel identifier
    - Auto-linking messaging_users to clients
    - Creating new clients when needed
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    async def find_client_by_telegram(self, telegram_chat_id: str) -> int | None:
        """
        Find client by Telegram chat_id.

        Args:
            telegram_chat_id: Telegram chat ID

        Returns:
            client_id if found, None otherwise
        """
        async with self.db_pool.acquire() as conn:
            client_id = await conn.fetchval(
                """
                SELECT client_id
                FROM messaging_users
                WHERE telegram_chat_id = $1
                  AND client_id IS NOT NULL
            """,
                str(telegram_chat_id),
            )

            return client_id

    async def find_client_by_whatsapp(self, phone: str) -> int | None:
        """
        Find client by WhatsApp phone number.

        Args:
            phone: Phone number (will be normalized)

        Returns:
            client_id if found, None otherwise
        """
        normalized = normalize_phone(phone)
        if not normalized:
            return None

        async with self.db_pool.acquire() as conn:
            # Try messaging_users first (if linked)
            client_id = await conn.fetchval(
                """
                SELECT client_id
                FROM messaging_users
                WHERE phone = $1
                  AND client_id IS NOT NULL
            """,
                normalized,
            )

            if client_id:
                return client_id

            # Fallback: search clients table by whatsapp/phone
            client_id = await conn.fetchval(
                """
                SELECT id
                FROM clients
                WHERE whatsapp = $1 OR phone = $1
                LIMIT 1
            """,
                normalized,
            )

            return client_id

    async def find_client_by_email(self, email: str) -> int | None:
        """
        Find client by email.

        Args:
            email: Email address

        Returns:
            client_id if found, None otherwise
        """
        if not email:
            return None

        async with self.db_pool.acquire() as conn:
            client_id = await conn.fetchval(
                """
                SELECT id
                FROM clients
                WHERE LOWER(email) = LOWER($1)
            """,
                email,
            )

            return client_id

    async def link_messaging_user_to_client(
        self, channel: str, identifier: str, client_id: int
    ) -> bool:
        """
        Link a messaging_user to a client.

        Args:
            channel: 'telegram' or 'whatsapp'
            identifier: telegram_chat_id or whatsapp_number
            client_id: Client ID to link to

        Returns:
            True if linked successfully, False otherwise
        """
        async with self.db_pool.acquire() as conn:
            if channel == "telegram":
                result = await conn.execute(
                    """
                    UPDATE messaging_users
                    SET client_id = $1
                    WHERE telegram_chat_id = $2
                      AND client_id IS NULL
                """,
                    client_id,
                    identifier,
                )
            elif channel == "whatsapp":
                normalized = normalize_phone(identifier)
                result = await conn.execute(
                    """
                    UPDATE messaging_users
                    SET client_id = $1
                    WHERE phone = $2
                      AND client_id IS NULL
                """,
                    client_id,
                    normalized,
                )
            else:
                logger.warning(f"Unknown channel: {channel}")
                return False

            rows_affected = result.split()[-1] if result else "0"
            success = int(rows_affected) > 0

            if success:
                logger.info(f"✅ Linked {channel} {identifier} → client #{client_id}")

            return success

    async def resolve_or_create_client(
        self, channel: str, identifier: str, client_data: dict[str, Any] | None = None
    ) -> tuple[int, bool]:
        """
        Resolve client identity or create new client.

        Args:
            channel: 'telegram', 'whatsapp', 'email', etc.
            identifier: Channel-specific identifier
            client_data: Optional data to create client if not found

        Returns:
            Tuple of (client_id, is_new_client)
        """
        # 1. Try to find existing client
        client_id = None

        if channel == "telegram":
            client_id = await self.find_client_by_telegram(identifier)
        elif channel == "whatsapp":
            client_id = await self.find_client_by_whatsapp(identifier)
        elif channel == "email":
            client_id = await self.find_client_by_email(identifier)

        if client_id:
            logger.info(f"✅ Found existing client #{client_id} via {channel}")
            return (client_id, False)

        # 2. Client not found - create new if data provided
        if not client_data:
            logger.warning(f"⚠️ Client not found for {channel}={identifier}, no data to create")
            return (None, False)

        async with self.db_pool.acquire() as conn:
            # Create new client
            row = await conn.fetchrow(
                """
                INSERT INTO clients (
                    full_name, email, phone, whatsapp, nationality, status,
                    client_type, source, notes, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, NOW()
                )
                RETURNING id
            """,
                client_data.get("full_name", "Unknown"),
                client_data.get("email"),
                client_data.get("phone"),
                client_data.get("whatsapp") or client_data.get("phone"),
                client_data.get("nationality"),
                client_data.get("status", "prospect"),
                client_data.get("client_type", "individual"),
                client_data.get("source", channel),
                client_data.get("notes"),
            )

            new_client_id = row["id"]
            logger.info(f"✅ Created new client #{new_client_id} from {channel}")

            # Auto-link to messaging_user
            await self.link_messaging_user_to_client(channel, identifier, new_client_id)

            return (new_client_id, True)

    async def get_client_channels(self, client_id: int) -> list[dict[str, Any]]:
        """
        Get all channels where client is active.

        Args:
            client_id: Client ID

        Returns:
            List of dicts with channel info:
            [
                {'channel': 'telegram', 'identifier': '123456', 'active': True},
                {'channel': 'whatsapp', 'identifier': '+6281234567890', 'active': True}
            ]
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    channel,
                    COALESCE(telegram_chat_id::text, phone) as identifier,
                    active,
                    created_at,
                    last_message_at
                FROM messaging_users
                WHERE client_id = $1
                ORDER BY last_message_at DESC NULLS LAST
            """,
                client_id,
            )

            return [dict(row) for row in rows]
