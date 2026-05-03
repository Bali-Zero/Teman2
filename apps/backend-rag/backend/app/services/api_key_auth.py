import hmac
"""
API Key Authentication Service
Provides simple API key validation to bypass database dependency for testing
"""

import logging
from datetime import datetime, timezone
from typing import Any

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """
    API Key authentication service with static key management
    Designed for immediate testing relief while coordinating with colleague's API Key service
    """

    def __init__(self) -> None:
        """Initialize API key service with valid keys and permissions from settings"""
        # Load API keys from environment variable (comma-separated)
        api_keys_str = settings.api_keys
        api_key_list = [key.strip() for key in api_keys_str.split(",") if key.strip()]

        # Initialize valid_keys dictionary from environment variable
        self.valid_keys = {}
        for api_key in api_key_list:
            # Default role and permissions - can be customized per key if needed
            self.valid_keys[api_key] = {
                "role": (
                    "admin" if "admin" in api_key.lower() or "secret" in api_key.lower() else "user"
                ),
                "permissions": (
                    ["*"] if "admin" in api_key.lower() or "secret" in api_key.lower() else ["read"]
                ),
                "created_at": datetime.now(timezone.utc).isoformat() + "Z",
                "description": "API key loaded from environment variable",
            }

        self.key_stats = {key: {"usage_count": 0, "last_used": None} for key in self.valid_keys}

        logger.info(
            f"API Key service initialized with {len(self.valid_keys)} valid keys from environment",
        )

    def validate_api_key(self, api_key: str) -> dict[str, Any] | None:
        """
        Validate API key and return user context

        Args:
            api_key: API key from X-API-Key header

        Returns:
            User context dict or None if invalid
        """
        if not api_key:
            logger.warning("No API key provided")
            return None

        # Constant-time comparison to prevent timing attacks
        key_info = None
        for stored_key, info in self.valid_keys.items():
            if hmac.compare_digest(api_key, stored_key):
                key_info = info
                break
        if not key_info:
            logger.warning("Invalid API key provided")
            return None

        # Update usage statistics
        self.key_stats[api_key]["usage_count"] += 1
        self.key_stats[api_key]["last_used"] = datetime.now(timezone.utc).isoformat()

        logger.debug(
            f"Valid API key used: {key_info['role']} (usage: {self.key_stats[api_key]['usage_count']})",
        )

        return {
            "id": f"api_key_{api_key[:8]}",
            "email": f"{key_info['role']}@zantara.dev",
            "name": f"API User ({key_info['role']})",
            "role": key_info["role"],
            "status": "active",
            "auth_method": "api_key",
            "permissions": key_info["permissions"],
            "metadata": {
                "key_created_at": key_info["created_at"],
                "key_description": key_info["description"],
                "usage_count": self.key_stats[api_key]["usage_count"],
                "last_used": self.key_stats[api_key]["last_used"],
            },
        }

    async def validate_api_key_enhanced(
        self, api_key: str, conn: Any | None = None,
    ) -> dict[str, Any] | None:
        """
        Enhanced API key validation with DB-backed role resolution (S03).

        Flow: DB lookup -> legacy fallback -> auto-migrate on fallback hit.
        Falls back to legacy sync validation if no DB connection available.

        Args:
            api_key: API key from X-API-Key header
            conn: Optional asyncpg connection for DB lookup

        Returns:
            User context dict or None if invalid
        """
        if not api_key:
            return None

        # Step 1: Try DB resolution if connection available
        if conn:
            db_role = await self.resolve_role_from_db(api_key, conn)
            if db_role:
                # Update usage stats
                if api_key in self.key_stats:
                    self.key_stats[api_key]["usage_count"] = self.key_stats[api_key].get("usage_count", 0) + 1
                    self.key_stats[api_key]["last_used"] = datetime.now(timezone.utc).isoformat()

                logger.info(f"S03: API key resolved from DB (role={db_role['role']})")
                return {
                    "id": f"api_key_{api_key[:8]}",
                    "email": f"{db_role['role']}@zantara.dev",
                    "name": f"API User ({db_role['role']})",
                    "role": db_role["role"],
                    "status": "active",
                    "auth_method": "api_key",
                    "permissions": db_role["permissions"],
                }

        # Step 2: Legacy fallback (sync in-memory validation)
        result = self.validate_api_key(api_key)

        # Step 3: Auto-migrate on legacy hit (if DB available)
        if result and conn:
            legacy_role = result["role"]
            legacy_perms = result.get("permissions", ["read"])
            await self.auto_migrate_key(api_key, legacy_role, legacy_perms, conn)
            logger.info(f"S03: Legacy API key used, auto-migrating to DB (role={legacy_role})")

        return result

    def is_valid_key(self, api_key: str) -> bool:
        """Check if API key is valid (simplified validation)"""
        return api_key in self.valid_keys

    def get_key_info(self, api_key: str) -> dict[str, Any] | None:
        """Get key information without incrementing usage stats"""
        return self.valid_keys.get(api_key)

    def get_service_stats(self) -> dict[str, Any]:
        """Get service statistics for monitoring"""
        total_usage = sum(stats["usage_count"] for stats in self.key_stats.values())
        return {
            "total_keys": len(self.valid_keys),
            "total_usage": total_usage,
            "key_usage": self.key_stats,
            "service_up": True,
            "service_type": "static_api_key",
        }

    def add_key(self, key: str, role: str = "test", permissions: list = None) -> bool:
        """Add new API key programmatically (for future dynamic support)"""
        if permissions is None:
            permissions = ["read"]

        if key in self.valid_keys:
            logger.warning(f"Attempt to add existing API key: {key[:10]}...")
            return False

        self.valid_keys[key] = {
            "role": role,
            "permissions": permissions,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "description": f"Programmatically added key ({role})",
        }
        self.key_stats[key] = {"usage_count": 0, "last_used": None}

        logger.info(f"Added new API key: {key[:10]}... (role: {role})")
        return True

    def remove_key(self, key: str) -> bool:
        """Remove API key from valid keys"""
        if key not in self.valid_keys:
            logger.warning(f"Attempt to remove non-existent API key: {key[:10]}...")
            return False

        del self.valid_keys[key]
        del self.key_stats[key]

        logger.info(f"Removed API key: {key[:10]}...")
        return True

    async def resolve_role_from_db(
        self, api_key: str, conn: Any,
    ) -> dict[str, Any] | None:
        """
        Resolve API key role from database (S03 hardening).

        Looks up key hash in api_key_records table. Returns role and
        permissions if found and active, None otherwise.

        Args:
            api_key: Raw API key string
            conn: asyncpg connection

        Returns:
            Dict with role/permissions if found, None otherwise
        """
        import hashlib

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            row = await conn.fetchrow(
                """
                SELECT role, permissions, is_active
                FROM api_key_records
                WHERE key_hash = $1
                """,
                key_hash,
            )

            if row and row["is_active"]:
                # Update last_used
                await conn.execute(
                    "UPDATE api_key_records SET last_used_at = NOW() WHERE key_hash = $1",
                    key_hash,
                )
                return {
                    "role": row["role"],
                    "permissions": list(row["permissions"]) if row["permissions"] else ["read"],
                }
        except Exception as e:
            logger.warning(f"DB API key lookup failed: {e}")

        return None

    async def auto_migrate_key(
        self, api_key: str, legacy_role: str, legacy_permissions: list[str], conn: Any,
    ) -> None:
        """
        Auto-migrate a legacy key to the database (S03 hardening).

        Called on every legacy fallback hit. Writes the key hash and its
        current role to api_key_records with source='auto_migrated'.

        Args:
            api_key: Raw API key string
            legacy_role: Role inferred from legacy name-based logic
            legacy_permissions: Permissions from legacy logic
            conn: asyncpg connection
        """
        import hashlib

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_name = f"migrated_{api_key[:8]}"

        try:
            await conn.execute(
                """
                INSERT INTO api_key_records (key_hash, name, role, permissions, source)
                VALUES ($1, $2, $3, $4, 'auto_migrated')
                ON CONFLICT (key_hash) DO NOTHING
                """,
                key_hash, key_name, legacy_role,
                legacy_permissions,
            )
            logger.info(f"S03: Auto-migrated API key {api_key[:8]}... to DB (role={legacy_role})")
        except Exception as e:
            logger.warning(f"S03: Auto-migration failed for {api_key[:8]}...: {e}")
