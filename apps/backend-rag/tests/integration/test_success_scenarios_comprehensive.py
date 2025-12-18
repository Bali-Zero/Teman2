"""
Comprehensive Success Scenario Tests
Tests successful operations with detailed response validation

Covers:
- Successful CRUD operations with full response validation
- Successful workflows with data verification
- Success metrics and performance validation
- Complete response structure validation
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCRMSuccessScenarios:
    """Test successful CRM operations with detailed validation"""

    @pytest.mark.asyncio
    async def test_client_creation_success(self, db_pool):
        """Test successful client creation with full validation"""
        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, client_type, priority,
                    created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                "Success Test Client",
                "success.client@example.com",
                "+6281234567890",
                "active",
                "individual",
                "high",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            assert client_id is not None
            assert isinstance(client_id, int)
            assert client_id > 0

            # Verify all fields
            client = await conn.fetchrow(
                """
                SELECT
                    id, full_name, email, phone, status, client_type, priority,
                    created_by, created_at, updated_at
                FROM clients
                WHERE id = $1
                """,
                client_id,
            )

            assert client is not None
            assert client["id"] == client_id
            assert client["full_name"] == "Success Test Client"
            assert client["email"] == "success.client@example.com"
            assert client["phone"] == "+6281234567890"
            assert client["status"] == "active"
            assert client["client_type"] == "individual"
            assert client["priority"] == "high"
            assert client["created_by"] == "team@example.com"
            assert client["created_at"] is not None
            assert client["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_practice_creation_success(self, db_pool):
        """Test successful practice creation with relationships"""
        async with db_pool.acquire() as conn:
            # Create client first
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Practice Client",
                "practice.client@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practice
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, priority, description,
                    created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "in_progress",
                "high",
                "E28A Investor KITAS application",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            assert practice_id is not None

            # Verify practice with client relationship
            practice = await conn.fetchrow(
                """
                SELECT
                    p.id, p.practice_type, p.status, p.priority, p.description,
                    c.id as client_id, c.full_name as client_name
                FROM practices p
                JOIN clients c ON p.client_id = c.id
                WHERE p.id = $1
                """,
                practice_id,
            )

            assert practice is not None
            assert practice["id"] == practice_id
            assert practice["client_id"] == client_id
            assert practice["practice_type"] == "KITAS"
            assert practice["status"] == "in_progress"
            assert practice["priority"] == "high"
            assert practice["description"] == "E28A Investor KITAS application"
            assert practice["client_name"] == "Practice Client"

    @pytest.mark.asyncio
    async def test_interaction_creation_success(self, db_pool):
        """Test successful interaction creation with full details"""
        async with db_pool.acquire() as conn:
            # Create client and practice
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Interaction Client",
                "interaction@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                "PT PMA",
                "in_progress",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create interaction
            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    client_id, practice_id, interaction_type, summary, notes,
                    created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                practice_id,
                "email",
                "Initial consultation completed",
                "Client interested in PT PMA setup for e-commerce business",
                "team@example.com",
                datetime.now(),
            )

            assert interaction_id is not None

            # Verify interaction with relationships
            interaction = await conn.fetchrow(
                """
                SELECT
                    i.id, i.interaction_type, i.summary, i.notes,
                    c.full_name as client_name,
                    p.practice_type
                FROM interactions i
                JOIN clients c ON i.client_id = c.id
                LEFT JOIN practices p ON i.practice_id = p.id
                WHERE i.id = $1
                """,
                interaction_id,
            )

            assert interaction is not None
            assert interaction["id"] == interaction_id
            assert interaction["interaction_type"] == "email"
            assert interaction["summary"] == "Initial consultation completed"
            assert (
                interaction["notes"] == "Client interested in PT PMA setup for e-commerce business"
            )
            assert interaction["client_name"] == "Interaction Client"
            assert interaction["practice_type"] == "PT PMA"


@pytest.mark.integration
class TestConversationSuccessScenarios:
    """Test successful conversation operations"""

    @pytest.mark.asyncio
    async def test_conversation_save_success(self, db_pool):
        """Test successful conversation save with message validation"""
        async with db_pool.acquire() as conn:
            user_email = "conversation.success@example.com"
            messages = [
                {"role": "user", "content": "What is PT PMA?"},
                {"role": "assistant", "content": "PT PMA is a foreign investment company..."},
                {"role": "user", "content": "What are the capital requirements?"},
                {"role": "assistant", "content": "Minimum capital is IDR 10 billion..."},
            ]

            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (
                    user_id, messages, session_id, rating, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                user_email,
                json.dumps(messages),  # Serialize to JSON string
                "test_session_123",
                5,
                datetime.now(),
                datetime.now(),
            )

            assert conversation_id is not None

            # Verify conversation
            conversation = await conn.fetchrow(
                """
                SELECT
                    id, user_id, messages, session_id, rating, created_at, updated_at
                FROM conversations
                WHERE id = $1
                """,
                conversation_id,
            )

            assert conversation is not None
            assert conversation["id"] == conversation_id
            assert conversation["user_id"] == user_email
            # Parse JSON string back to list
            parsed_messages = (
                json.loads(conversation["messages"])
                if isinstance(conversation["messages"], str)
                else conversation["messages"]
            )
            assert len(parsed_messages) == 4
            assert parsed_messages[0]["role"] == "user"
            assert parsed_messages[0]["content"] == "What is PT PMA?"
            assert conversation["session_id"] == "test_session_123"
            assert conversation["rating"] == 5
            assert conversation["created_at"] is not None

    @pytest.mark.asyncio
    async def test_conversation_history_retrieval_success(self, db_pool):
        """Test successful conversation history retrieval"""
        async with db_pool.acquire() as conn:
            user_email = "history@example.com"

            # Create multiple conversations
            conversation_ids = []
            for i in range(3):
                conv_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (
                        user_id, messages, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    user_email,
                    json.dumps(
                        [
                            {"role": "user", "content": f"Question {i}"},
                            {"role": "assistant", "content": f"Answer {i}"},
                        ]
                    ),  # Serialize to JSON string
                    datetime.now() - timedelta(days=i),
                    datetime.now() - timedelta(days=i),
                )
                conversation_ids.append(conv_id)

            # Retrieve history
            history = await conn.fetch(
                """
                SELECT id, user_id, messages, created_at
                FROM conversations
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_email,
            )

            assert len(history) == 3
            assert all(h["user_id"] == user_email for h in history)
            # Verify chronological order (newest first)
            for i in range(len(history) - 1):
                assert history[i]["created_at"] >= history[i + 1]["created_at"]


@pytest.mark.integration
class TestMemorySuccessScenarios:
    """Test successful memory operations"""

    @pytest.mark.asyncio
    async def test_memory_storage_success(self, db_pool):
        """Test successful memory storage with validation"""
        async with db_pool.acquire() as conn:
            user_email = "memory.success@example.com"

            # Store memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO memory_facts (
                    user_id, content, fact_type, confidence, source, metadata, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                user_email,
                "Client prefers email communication over phone calls",
                "preference",
                0.95,
                "conversation",
                json.dumps(
                    {"context": "communication", "verified": True}
                ),  # Serialize to JSON string
                datetime.now(),
            )

            assert memory_id is not None

            # Verify memory
            memory = await conn.fetchrow(
                """
                SELECT
                    id, user_id, content, fact_type, confidence, source, metadata, created_at
                FROM memory_facts
                WHERE id = $1
                """,
                memory_id,
            )

            assert memory is not None
            assert memory["id"] == memory_id
            assert memory["user_id"] == user_email
            assert memory["content"] == "Client prefers email communication over phone calls"
            assert memory["fact_type"] == "preference"
            assert memory["confidence"] == 0.95
            assert memory["source"] == "conversation"
            # Parse JSON string back to dict
            metadata = (
                json.loads(memory["metadata"])
                if isinstance(memory["metadata"], str)
                else memory["metadata"]
            )
            assert metadata == {"context": "communication", "verified": True}
            assert memory["created_at"] is not None

    @pytest.mark.asyncio
    async def test_memory_search_success(self, db_pool):
        """Test successful memory search with results validation"""
        async with db_pool.acquire() as conn:
            user_email = "search@example.com"

            # Store multiple memories
            memories = [
                ("Client prefers email", "preference", 0.9),
                ("Client budget: IDR 2.5B", "fact", 0.85),
                ("Client interested in PT PMA", "interest", 0.95),
            ]

            for content, fact_type, confidence in memories:
                await conn.execute(
                    """
                    INSERT INTO memory_facts (
                        user_id, content, fact_type, confidence, source, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    user_email,
                    content,
                    fact_type,
                    confidence,
                    "conversation",
                    datetime.now(),
                )

            # Search memories
            results = await conn.fetch(
                """
                SELECT id, content, fact_type, confidence
                FROM memory_facts
                WHERE user_id = $1
                AND (content ILIKE $2 OR fact_type = $3)
                ORDER BY confidence DESC
                """,
                user_email,
                "%PT PMA%",
                "preference",
            )

            assert len(results) >= 2
            # Verify results are ordered by confidence
            for i in range(len(results) - 1):
                assert results[i]["confidence"] >= results[i + 1]["confidence"]


@pytest.mark.integration
class TestOracleSuccessScenarios:
    """Test successful Oracle query operations"""

    @pytest.mark.asyncio
    async def test_oracle_query_success(self, db_pool):
        """Test successful Oracle query with response validation"""
        async with db_pool.acquire() as conn:
            user_email = "oracle.success@example.com"

            # Create query record
            query_id = await conn.fetchval(
                """
                INSERT INTO oracle_queries (
                    user_id, query, response, collection_used, execution_time_ms,
                    document_count, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                user_email,
                "What is PT PMA?",
                "PT PMA (Penanaman Modal Asing) is a foreign investment company...",
                "legal_intelligence",
                1250.5,
                5,
                datetime.now(),
            )

            assert query_id is not None

            # Verify query
            query = await conn.fetchrow(
                """
                SELECT
                    id, user_id, query, response, collection_used,
                    execution_time_ms, document_count, created_at
                FROM oracle_queries
                WHERE id = $1
                """,
                query_id,
            )

            assert query is not None
            assert query["id"] == query_id
            assert query["user_id"] == user_email
            assert query["query"] == "What is PT PMA?"
            assert "PT PMA" in query["response"]
            assert query["collection_used"] == "legal_intelligence"
            assert query["execution_time_ms"] == 1250.5
            assert query["document_count"] == 5
            assert query["created_at"] is not None

    @pytest.mark.asyncio
    async def test_oracle_feedback_success(self, db_pool):
        """Test successful Oracle feedback submission"""
        async with db_pool.acquire() as conn:
            user_email = "feedback.success@example.com"

            # Create query
            query_id = await conn.fetchval(
                """
                INSERT INTO oracle_queries (
                    user_id, query, response, created_at
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_email,
                "Test query",
                "Test response",
                datetime.now(),
            )

            # Submit feedback
            feedback_id = await conn.fetchval(
                """
                INSERT INTO oracle_feedback (
                    query_id, user_id, rating, feedback_text, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                query_id,
                user_email,
                5,
                "Very helpful and accurate response",
                datetime.now(),
            )

            assert feedback_id is not None

            # Verify feedback
            feedback = await conn.fetchrow(
                """
                SELECT
                    f.id, f.query_id, f.user_id, f.rating, f.feedback_text,
                    q.query
                FROM oracle_feedback f
                JOIN oracle_queries q ON f.query_id = q.id
                WHERE f.id = $1
                """,
                feedback_id,
            )

            assert feedback is not None
            assert feedback["id"] == feedback_id
            assert feedback["query_id"] == query_id
            assert feedback["rating"] == 5
            assert feedback["feedback_text"] == "Very helpful and accurate response"
            assert feedback["query"] == "Test query"


@pytest.mark.integration
class TestTeamActivitySuccessScenarios:
    """Test successful team activity operations"""

    @pytest.mark.asyncio
    async def test_clock_in_out_success(self, db_pool):
        """Test successful clock in/out with time calculation"""
        async with db_pool.acquire() as conn:
            user_email = "team.success@example.com"
            # Use UTC time to avoid timezone issues
            from datetime import timezone

            base_time = datetime.now(timezone.utc).replace(microsecond=0)

            # Clock in
            clock_in_id = await conn.fetchval(
                """
                INSERT INTO team_activity (
                    user_id, activity_type, timestamp, notes, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_email,
                "clock_in",
                base_time,
                "Starting work day",
                datetime.now(),
            )

            assert clock_in_id is not None

            # Clock out (8 hours later)
            clock_out_time = base_time + timedelta(hours=8, minutes=30)
            clock_out_id = await conn.fetchval(
                """
                INSERT INTO team_activity (
                    user_id, activity_type, timestamp, notes, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_email,
                "clock_out",
                clock_out_time,
                "Ending work day",
                datetime.now(),
            )

            assert clock_out_id is not None

            # Calculate hours worked
            hours_data = await conn.fetchrow(
                """
                SELECT
                    MIN(CASE WHEN activity_type = 'clock_in' THEN timestamp END) as clock_in_time,
                    MAX(CASE WHEN activity_type = 'clock_out' THEN timestamp END) as clock_out_time,
                    EXTRACT(EPOCH FROM (
                        MAX(CASE WHEN activity_type = 'clock_out' THEN timestamp END) -
                        MIN(CASE WHEN activity_type = 'clock_in' THEN timestamp END)
                    )) / 3600 as hours_worked
                FROM team_activity
                WHERE user_id = $1
                AND DATE(timestamp) = CURRENT_DATE
                """,
                user_email,
            )

            assert hours_data is not None
            # Compare times (handle timezone - database returns UTC)
            clock_in = hours_data["clock_in_time"]
            clock_out = hours_data["clock_out_time"]
            # Both should be in UTC, so compare directly
            assert (
                clock_in.replace(tzinfo=None) == base_time.replace(tzinfo=None)
                or clock_in == base_time
            )
            assert (
                clock_out.replace(tzinfo=None) == clock_out_time.replace(tzinfo=None)
                or clock_out == clock_out_time
            )
            # Convert Decimal to float for comparison
            hours_worked = (
                float(hours_data["hours_worked"])
                if hasattr(hours_data["hours_worked"], "__float__")
                else hours_data["hours_worked"]
            )
            assert abs(hours_worked - 8.5) < 0.1  # Allow small rounding


@pytest.mark.integration
class TestComplexWorkflowSuccess:
    """Test complex multi-step workflows with success validation"""

    @pytest.mark.asyncio
    async def test_complete_client_onboarding_workflow(self, db_pool):
        """Test complete client onboarding workflow"""
        async with db_pool.acquire() as conn:
            user_email = "onboarding@example.com"

            # Step 1: Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "Onboarding Client",
                "onboarding@example.com",
                "+6281234567890",
                "active",
                user_email,
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Create practice
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, priority, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "PT PMA",
                "in_progress",
                "high",
                user_email,
                datetime.now(),
                datetime.now(),
            )

            # Step 3: Create multiple interactions
            interaction_ids = []
            for i, interaction_type in enumerate(["email", "call", "meeting"]):
                interaction_id = await conn.fetchval(
                    """
                    INSERT INTO interactions (
                        client_id, practice_id, interaction_type, summary, created_by, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    client_id,
                    practice_id,
                    interaction_type,
                    f"{interaction_type.capitalize()} interaction {i + 1}",
                    user_email,
                    datetime.now() + timedelta(days=i),
                )
                interaction_ids.append(interaction_id)

            # Step 4: Store shared memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, tags, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "preference",
                "Client prefers email communication",
                json.dumps(["communication", "preference"]),  # Serialize to JSON string
                user_email,
                datetime.now(),
                datetime.now(),
            )

            # Step 5: Verify complete workflow
            workflow_summary = await conn.fetchrow(
                """
                SELECT
                    c.id as client_id,
                    c.full_name,
                    COUNT(DISTINCT p.id) as practice_count,
                    COUNT(DISTINCT i.id) as interaction_count,
                    COUNT(DISTINCT sm.id) as memory_count
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                LEFT JOIN shared_memory sm ON c.id = sm.client_id
                WHERE c.id = $1
                GROUP BY c.id, c.full_name
                """,
                client_id,
            )

            assert workflow_summary is not None
            assert workflow_summary["client_id"] == client_id
            assert workflow_summary["full_name"] == "Onboarding Client"
            assert workflow_summary["practice_count"] == 1
            assert workflow_summary["interaction_count"] == 3
            assert workflow_summary["memory_count"] == 1

    @pytest.mark.asyncio
    async def test_practice_completion_workflow(self, db_pool):
        """Test practice completion workflow with status transitions"""
        async with db_pool.acquire() as conn:
            # Create client and practice
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Completion Client",
                "completion@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "in_progress",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Simulate status progression
            statuses = ["in_progress", "pending_review", "completed"]
            for status in statuses:
                await conn.execute(
                    """
                    UPDATE practices
                    SET status = $1, updated_at = $2
                    WHERE id = $3
                    """,
                    status,
                    datetime.now(),
                    practice_id,
                )

                # Verify status update
                current_status = await conn.fetchval(
                    "SELECT status FROM practices WHERE id = $1", practice_id
                )
                assert current_status == status

            # Final verification
            final_practice = await conn.fetchrow(
                """
                SELECT
                    p.id, p.status, p.updated_at,
                    c.full_name
                FROM practices p
                JOIN clients c ON p.client_id = c.id
                WHERE p.id = $1
                """,
                practice_id,
            )

            assert final_practice is not None
            assert final_practice["status"] == "completed"
            assert final_practice["updated_at"] is not None
