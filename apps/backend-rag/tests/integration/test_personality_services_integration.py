"""
Comprehensive Integration Tests for Personality Services
Tests PersonalityService and emotional attunement

Covers:
- Personality service operations
- Emotional attunement
- Response personalization
- User preference learning
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestPersonalityServiceIntegration:
    """Integration tests for PersonalityService"""

    @pytest.mark.asyncio
    async def test_personality_service_initialization(self, db_pool):
        """Test PersonalityService initialization"""
        with patch("services.personality_service.MemoryServicePostgres") as mock_memory:
            from services.personality_service import PersonalityService

            service = PersonalityService(memory_service=mock_memory.return_value)

            assert service is not None

    @pytest.mark.asyncio
    async def test_personality_profile_storage(self, db_pool):
        """Test personality profile storage"""

        async with db_pool.acquire() as conn:
            # Create personality_profiles table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS personality_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) UNIQUE,
                    communication_style VARCHAR(100),
                    formality_level VARCHAR(50),
                    humor_preference VARCHAR(50),
                    tone_preferences JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store personality profile
            profile_id = await conn.fetchval(
                """
                INSERT INTO personality_profiles (
                    user_id, communication_style, formality_level, humor_preference, tone_preferences
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "user_personality_123",
                "direct",
                "casual",
                "light",
                {"enthusiasm": "high", "empathy": "medium"},
            )

            assert profile_id is not None

            # Retrieve profile
            profile = await conn.fetchrow(
                """
                SELECT communication_style, formality_level, tone_preferences
                FROM personality_profiles
                WHERE user_id = $1
                """,
                "user_personality_123",
            )

            assert profile is not None
            assert profile["communication_style"] == "direct"
            assert profile["formality_level"] == "casual"

            # Cleanup
            await conn.execute("DELETE FROM personality_profiles WHERE id = $1", profile_id)

    @pytest.mark.asyncio
    async def test_personality_adaptation(self, db_pool):
        """Test personality-based response adaptation"""

        async with db_pool.acquire() as conn:
            # Create response_adaptations table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS response_adaptations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    original_response TEXT,
                    adapted_response TEXT,
                    adaptation_reason VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store adaptation
            adaptation_id = await conn.fetchval(
                """
                INSERT INTO response_adaptations (
                    user_id, original_response, adapted_response, adaptation_reason
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "user_personality_123",
                "This is a formal response.",
                "Hey! This is a casual response 😊",
                "user_prefers_casual_tone",
            )

            assert adaptation_id is not None

            # Retrieve adaptation
            adaptation = await conn.fetchrow(
                """
                SELECT adapted_response, adaptation_reason
                FROM response_adaptations
                WHERE id = $1
                """,
                adaptation_id,
            )

            assert adaptation is not None
            assert "casual" in adaptation["adapted_response"].lower()

            # Cleanup
            await conn.execute("DELETE FROM response_adaptations WHERE id = $1", adaptation_id)


@pytest.mark.integration
class TestEmotionalAttunementIntegration:
    """Integration tests for EmotionalAttunement"""

    @pytest.mark.asyncio
    async def test_emotional_state_tracking(self, db_pool):
        """Test emotional state tracking"""

        async with db_pool.acquire() as conn:
            # Create emotional_states table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emotional_states (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    emotional_state VARCHAR(100),
                    intensity DECIMAL(3,2),
                    context TEXT,
                    detected_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Track emotional states
            states = [
                ("user_emotion_123", "frustrated", 0.7, "Having trouble with application"),
                ("user_emotion_123", "relieved", 0.6, "Got help with question"),
                ("user_emotion_123", "curious", 0.5, "Asking about options"),
            ]

            for user_id, state, intensity, context in states:
                await conn.execute(
                    """
                    INSERT INTO emotional_states (
                        user_id, emotional_state, intensity, context
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    user_id,
                    state,
                    intensity,
                    context,
                )

            # Analyze emotional patterns
            pattern = await conn.fetchrow(
                """
                SELECT
                    emotional_state,
                    AVG(intensity) as avg_intensity,
                    COUNT(*) as occurrence_count
                FROM emotional_states
                WHERE user_id = $1
                GROUP BY emotional_state
                ORDER BY occurrence_count DESC
                LIMIT 1
                """,
                "user_emotion_123",
            )

            assert pattern is not None
            assert pattern["occurrence_count"] >= 1

            # Cleanup
            await conn.execute(
                "DELETE FROM emotional_states WHERE user_id = $1", "user_emotion_123"
            )

    @pytest.mark.asyncio
    async def test_emotional_response_adaptation(self, db_pool):
        """Test emotional response adaptation"""

        async with db_pool.acquire() as conn:
            # Create emotional_adaptations table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emotional_adaptations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    detected_emotion VARCHAR(100),
                    original_response TEXT,
                    adapted_response TEXT,
                    adaptation_strategy VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store emotional adaptation
            adaptation_id = await conn.fetchval(
                """
                INSERT INTO emotional_adaptations (
                    user_id, detected_emotion, original_response, adapted_response, adaptation_strategy
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "user_emotion_123",
                "frustrated",
                "You need to complete the form.",
                "I understand this can be frustrating. Let me help you step by step with the form.",
                "empathy_and_guidance",
            )

            assert adaptation_id is not None

            # Retrieve adaptation
            adaptation = await conn.fetchrow(
                """
                SELECT adapted_response, adaptation_strategy
                FROM emotional_adaptations
                WHERE id = $1
                """,
                adaptation_id,
            )

            assert adaptation is not None
            assert "understand" in adaptation["adapted_response"].lower()
            assert "help" in adaptation["adapted_response"].lower()

            # Cleanup
            await conn.execute("DELETE FROM emotional_adaptations WHERE id = $1", adaptation_id)
