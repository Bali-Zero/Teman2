"""
User Context Service
Responsibility: Manage user profile, memory, and personality context
"""

import logging
from typing import Any

from services.memory_service_postgres import MemoryServicePostgres
from services.oracle_database import db_manager
from services.personality_service import PersonalityService

logger = logging.getLogger(__name__)


class UserContextService:
    """
    Service for managing user context.

    Responsibility: Load and manage user profile, memory, and personality information.
    """

    def __init__(
        self,
        personality_service: PersonalityService | None = None,
        memory_service: MemoryServicePostgres | None = None,
    ):
        """
        Initialize user context service.

        Args:
            personality_service: Optional PersonalityService instance
            memory_service: Optional MemoryServicePostgres instance
        """
        self.personality_service = personality_service
        self.memory_service = memory_service

    async def get_user_profile(self, user_email: str) -> dict[str, Any] | None:
        """
        Get user profile from database.

        Args:
            user_email: User email address

        Returns:
            User profile dictionary or None
        """
        try:
            return await db_manager.get_user_profile(user_email)
        except Exception as e:
            logger.warning(f"Error loading user profile: {e}")
            return None

    async def get_user_personality(self, user_email: str) -> dict[str, Any]:
        """
        Get user personality information.

        Args:
            user_email: User email address

        Returns:
            Personality information dictionary
        """
        if not self.personality_service:
            return {"personality_type": "professional"}

        try:
            return self.personality_service.get_user_personality(user_email)
        except Exception as e:
            logger.warning(f"PersonalityService error: {e}")
            return {"personality_type": "professional"}

    async def get_user_memory_facts(self, user_email: str) -> list[str]:
        """
        Get user memory facts from PostgreSQL.

        Args:
            user_email: User email address

        Returns:
            List of memory facts
        """
        if not self.memory_service:
            return []

        try:
            if not self.memory_service.pool:
                await self.memory_service.connect()
            user_memory = await self.memory_service.get_memory(user_email)
            if user_memory and user_memory.profile_facts:
                return user_memory.profile_facts
        except Exception as e:
            logger.warning(f"MemoryService error: {e}")

        return []

    async def get_full_user_context(self, user_email: str | None) -> dict[str, Any]:
        """
        Get complete user context (profile, personality, memory).

        Args:
            user_email: User email address (optional)

        Returns:
            Dictionary with user context:
            - profile: User profile dict
            - personality: Personality info dict
            - memory_facts: List of memory facts
            - user_name: User name
            - user_role: User role
        """
        if not user_email:
            return {
                "profile": None,
                "personality": {"personality_type": "professional"},
                "memory_facts": [],
                "user_name": "User",
                "user_role": "member",
            }

        # Load profile
        profile = await self.get_user_profile(user_email)

        # Load personality
        personality = await self.get_user_personality(user_email)

        # Load memory
        memory_facts = await self.get_user_memory_facts(user_email)

        return {
            "profile": profile,
            "personality": personality,
            "memory_facts": memory_facts,
            "user_name": profile.get("name", "User") if profile else "User",
            "user_role": (profile.get("role_level", "member") if profile else "member"),
        }
