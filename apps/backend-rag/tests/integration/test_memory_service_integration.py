"""
Integration tests for MemoryServicePostgres with real PostgreSQL database.

These tests verify that MemoryService correctly interacts with PostgreSQL,
including user memory storage, retrieval, and updates.
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.database
class TestMemoryServiceIntegration:
    """Integration tests for MemoryServicePostgres with real PostgreSQL"""

    @pytest.mark.asyncio
    async def test_memory_service_initialization(self, memory_service):
        """Test that MemoryService initializes correctly with PostgreSQL"""
        assert memory_service is not None
        # use_postgres should be True if DATABASE_URL is set
        assert memory_service.use_postgres is True
        # Pool should be initialized after connect()
        assert memory_service.pool is not None

    @pytest.mark.asyncio
    async def test_save_user_memory(self, memory_service):
        """Test saving user memory to PostgreSQL"""
        from datetime import datetime

        from services.memory_service_postgres import UserMemory

        user_id = "test_user_integration_1"

        # Create UserMemory object
        memory = UserMemory(
            user_id=user_id,
            profile_facts=["Test user likes integration testing"],
            summary="",
            counters={"conversations": 0, "searches": 0, "tasks": 0},
            updated_at=datetime.now(),
        )

        # Save memory
        result = await memory_service.save_memory(memory)

        assert result is True

    @pytest.mark.asyncio
    async def test_retrieve_user_memory(self, memory_service):
        """Test retrieving user memory from PostgreSQL"""
        from datetime import datetime

        from services.memory_service_postgres import UserMemory

        user_id = "test_user_integration_2"

        # Create and save memory first
        memory = UserMemory(
            user_id=user_id,
            profile_facts=["Test user prefers PostgreSQL"],
            summary="",
            counters={"conversations": 0, "searches": 0, "tasks": 0},
            updated_at=datetime.now(),
        )
        await memory_service.save_memory(memory)

        # Retrieve memory
        retrieved_memory = await memory_service.get_memory(user_id)

        assert retrieved_memory is not None
        assert retrieved_memory.profile_facts is not None
        assert len(retrieved_memory.profile_facts) > 0

    @pytest.mark.asyncio
    async def test_update_user_summary(self, memory_service):
        """Test updating user conversation summary"""
        user_id = "test_user_integration_3"

        # Update summary
        result = await memory_service.update_summary(
            user_id=user_id, summary="User is testing integration with PostgreSQL"
        )

        assert result is True

        # Retrieve and verify
        memory = await memory_service.get_memory(user_id)
        assert memory is not None
        assert memory.summary == "User is testing integration with PostgreSQL"

    @pytest.mark.asyncio
    async def test_memory_deduplication(self, memory_service):
        """Test that duplicate memories are deduplicated"""
        user_id = "test_user_integration_4"
        fact_content = "User likes testing"

        # Add same fact twice using add_fact
        await memory_service.add_fact(user_id, fact_content)
        result = await memory_service.add_fact(
            user_id, fact_content
        )  # Should return False (duplicate)

        # Second add should fail (duplicate)
        assert result is False

        # Retrieve memory
        memory = await memory_service.get_memory(user_id)

        # Should only have one fact (deduplicated)
        facts = memory.profile_facts
        assert facts.count(fact_content) == 1
