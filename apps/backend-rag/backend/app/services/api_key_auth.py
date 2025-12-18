"""
API Key Authentication Service
Provides simple API key validation to bypass database dependency for testing
"""

import logging
from datetime import datetime
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """
    API Key authentication service with static key management
    Designed for immediate testing relief while coordinating with colleague's API Key service
    """

    def __init__(self):
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
                "created_at": datetime.utcnow().isoformat() + "Z",
                "description": "API key loaded from environment variable",
            }

        self.key_stats = {key: {"usage_count": 0, "last_used": None} for key in self.valid_keys}

        logger.info(
            f"API Key service initialized with {len(self.valid_keys)} valid keys from environment"
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

        key_info = self.valid_keys.get(api_key)
        if not key_info:
            logger.warning(f"Invalid API key provided: {api_key[:10]}...")
            return None

        # Update usage statistics
        self.key_stats[api_key]["usage_count"] += 1
        self.key_stats[api_key]["last_used"] = datetime.utcnow().isoformat()

        logger.debug(
            f"Valid API key used: {key_info['role']} (usage: {self.key_stats[api_key]['usage_count']})"
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
            "created_at": datetime.utcnow().isoformat(),
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
