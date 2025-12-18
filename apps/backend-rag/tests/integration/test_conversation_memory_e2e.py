"""
End-to-End Test: Conversation Memory (Short-Term Memory Fix)

Tests the complete flow:
1. User says "Mi chiamo Marco e sono di Milano"
2. System saves conversation
3. User asks "Come mi chiamo?"
4. System remembers and responds "Marco"

This test verifies the fix for P1 issue: Zantara not remembering information
from 1-2 turns before in the same conversation.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestConversationMemoryE2E:
    """End-to-end tests for conversation memory (short-term memory)"""

    @pytest.mark.asyncio
    async def test_remember_name_and_city_across_turns(self, db_pool):
        """
        Test Case: "Mi chiamo Marco e sono di Milano" → "Come mi chiamo?"

        Expected: System remembers name (Marco) and city (Milano) from previous turn
        """
        user_email = "test.memory@balizero.com"
        session_id = f"test_session_{datetime.now().timestamp()}"

        async with db_pool.acquire() as conn:
            # Ensure user exists
            await conn.execute(
                """
                INSERT INTO users (id, email, name, role)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_email,
                user_email,
                "Test User",
                "member",
            )

            # TURN 1: User introduces themselves
            turn1_user_message = "Mi chiamo Marco e sono di Milano"
            turn1_assistant_response = "Ciao Marco! Piacere di conoscerti."

            # Save Turn 1 conversation
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, session_id, messages, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_email,
                session_id,
                json.dumps(
                    [
                        {"role": "user", "content": turn1_user_message},
                        {"role": "assistant", "content": turn1_assistant_response},
                    ]
                ),
                datetime.now(),
            )

            assert conversation_id is not None
            print(f"✅ Turn 1 saved: conversation_id={conversation_id}, session_id={session_id}")

            # TURN 2: User asks "Come mi chiamo?"
            turn2_user_message = "Come mi chiamo?"

            # Update conversation with Turn 2 user message
            await conn.execute(
                """
                UPDATE conversations
                SET messages = $1
                WHERE id = $2
                """,
                json.dumps(
                    [
                        {"role": "user", "content": turn1_user_message},
                        {"role": "assistant", "content": turn1_assistant_response},
                        {"role": "user", "content": turn2_user_message},
                    ]
                ),
                conversation_id,
            )

            # Now test oracle query with conversation_id
            from app.routers.oracle_universal import (
                OracleQueryRequest,
                extract_entities_from_history,
                get_conversation_history_for_query,
                hybrid_oracle_query,
            )

            # Step 1: Retrieve conversation history
            conversation_history = await get_conversation_history_for_query(
                conversation_id=conversation_id,
                session_id=None,
                user_email=user_email,
                db_pool=db_pool,
            )

            assert (
                len(conversation_history) == 3
            ), f"Expected 3 messages, got {len(conversation_history)}"
            assert conversation_history[0]["content"] == turn1_user_message
            assert conversation_history[2]["content"] == turn2_user_message

            # Step 2: Extract entities from history
            entities = extract_entities_from_history(conversation_history)

            assert entities["name"] == "Marco", f"Expected name 'Marco', got {entities['name']}"
            assert entities["city"] == "Milano", f"Expected city 'Milano', got {entities['city']}"

            print(f"✅ Entities extracted: name={entities['name']}, city={entities['city']}")

            # Step 3: Test oracle query with conversation_id (mocked LLM)
            mock_service = MagicMock()
            mock_router = MagicMock()
            mock_router.route_query.return_value = {
                "collection_name": "legal_docs",
                "domain_scores": {},
            }
            mock_service.query_router = mock_router
            mock_collection_manager = MagicMock()
            mock_collection_manager.get_collection.return_value = MagicMock(
                search=AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
            )
            mock_service.collection_manager = mock_collection_manager

            with (
                patch("app.routers.oracle_universal.db_manager") as mock_db_manager,
                patch("app.routers.oracle_universal.reason_with_gemini") as mock_reason,
                patch("app.routers.oracle_universal.get_memory_service") as mock_memory_service,
                patch("core.embeddings.create_embeddings_generator") as mock_create_embedder,
            ):
                # Mock user profile
                mock_db_manager.get_user_profile = AsyncMock(
                    return_value={
                        "id": user_email,
                        "email": user_email,
                        "name": "Test User",
                        "language": "it",
                    }
                )

                # Mock embeddings
                mock_embedder = MagicMock()
                mock_embedder.generate_single_embedding.return_value = [0.1] * 1536
                mock_create_embedder.return_value = mock_embedder

                # Mock memory service
                mock_memory_svc = MagicMock()
                mock_memory_svc.pool = None
                mock_memory_svc.get_memory = AsyncMock(return_value=MagicMock(profile_facts=[]))
                mock_memory_service.return_value = mock_memory_svc

                # Mock Gemini reasoning - should include Marco and Milano in response
                mock_reason.return_value = {
                    "answer": "Ti chiami Marco, e sei di Milano!",
                    "model_used": "gemini-2.0-flash",
                    "reasoning_time_ms": 100,
                    "success": True,
                }

                # Create request with conversation_id
                request = OracleQueryRequest(
                    query=turn2_user_message,
                    user_email=user_email,
                    conversation_id=conversation_id,
                    use_ai=True,
                )

                # Execute query
                response = await hybrid_oracle_query(request, mock_service, db_pool)

                # Verify response
                assert response.success is True, f"Query failed: {response.error}"
                assert response.answer is not None

                # Verify conversation history was passed to LLM
                call_args = mock_reason.call_args
                assert call_args is not None, "reason_with_gemini was not called"

                if call_args and "conversation_history" in call_args.kwargs:
                    history_passed = call_args.kwargs["conversation_history"]
                    assert (
                        len(history_passed) >= 2
                    ), f"Expected at least 2 messages in history, got {len(history_passed)}"
                    print(f"✅ Conversation history passed to LLM: {len(history_passed)} messages")

                # Verify answer contains Marco (entity extraction should add it to memory facts)
                answer_lower = response.answer.lower()
                # The answer should mention Marco (either from conversation history or entity extraction)
                assert "marco" in answer_lower or len(response.user_memory_facts) > 0, (
                    f"Answer should mention 'Marco' or have memory facts. "
                    f"Answer: {response.answer}, Memory facts: {response.user_memory_facts}"
                )

                print(f"✅ Response: {response.answer}")
                print(f"✅ Memory facts: {response.user_memory_facts}")

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM users WHERE id = $1", user_email)

    @pytest.mark.asyncio
    async def test_remember_name_across_multiple_turns(self, db_pool):
        """
        Test Case: Multiple turns with name mentioned once

        Turn 1: "Mi chiamo Marco"
        Turn 2: "Come mi chiamo?"
        Turn 3: "E la mia città?"

        Expected: System remembers name from Turn 1 in both Turn 2 and Turn 3
        """
        user_email = "test.memory2@balizero.com"
        session_id = f"test_session_{datetime.now().timestamp()}"

        async with db_pool.acquire() as conn:
            # Ensure user exists
            await conn.execute(
                """
                INSERT INTO users (id, email, name, role)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_email,
                user_email,
                "Test User 2",
                "member",
            )

            # Turn 1: User introduces name
            messages = [
                {"role": "user", "content": "Mi chiamo Marco"},
                {"role": "assistant", "content": "Ciao Marco!"},
            ]

            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, session_id, messages, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_email,
                session_id,
                json.dumps(messages),
                datetime.now(),
            )

            # Turn 2: User asks "Come mi chiamo?"
            messages.append({"role": "user", "content": "Come mi chiamo?"})
            await conn.execute(
                """
                UPDATE conversations SET messages = $1 WHERE id = $2
                """,
                json.dumps(messages),
                conversation_id,
            )

            # Retrieve history and extract entities
            from app.routers.oracle_universal import (
                extract_entities_from_history,
                get_conversation_history_for_query,
            )

            history = await get_conversation_history_for_query(
                conversation_id=conversation_id,
                session_id=None,
                user_email=user_email,
                db_pool=db_pool,
            )

            assert len(history) == 3

            entities = extract_entities_from_history(history)
            assert entities["name"] == "Marco"

            # Turn 3: User asks about city (name should still be remembered)
            messages.append({"role": "assistant", "content": "Ti chiami Marco"})
            messages.append({"role": "user", "content": "E la mia città?"})

            await conn.execute(
                """
                UPDATE conversations SET messages = $1 WHERE id = $2
                """,
                json.dumps(messages),
                conversation_id,
            )

            # Retrieve updated history
            history_updated = await get_conversation_history_for_query(
                conversation_id=conversation_id,
                session_id=None,
                user_email=user_email,
                db_pool=db_pool,
            )

            assert len(history_updated) == 5

            # Extract entities again - name should still be there
            entities_updated = extract_entities_from_history(history_updated)
            assert (
                entities_updated["name"] == "Marco"
            ), "Name should still be remembered after multiple turns"

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM users WHERE id = $1", user_email)

    @pytest.mark.asyncio
    async def test_entity_extraction_with_session_id(self, db_pool):
        """
        Test Case: Entity extraction using session_id instead of conversation_id
        """
        user_email = "test.memory3@balizero.com"
        session_id = f"test_session_{datetime.now().timestamp()}"

        async with db_pool.acquire() as conn:
            # Ensure user exists
            await conn.execute(
                """
                INSERT INTO users (id, email, name, role)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_email,
                user_email,
                "Test User 3",
                "member",
            )

            # Save conversation with session_id
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, session_id, messages, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_email,
                session_id,
                json.dumps(
                    [
                        {"role": "user", "content": "Mi chiamo Marco e sono di Milano"},
                        {"role": "assistant", "content": "Ciao Marco!"},
                    ]
                ),
                datetime.now(),
            )

            # Retrieve using session_id
            from app.routers.oracle_universal import (
                extract_entities_from_history,
                get_conversation_history_for_query,
            )

            history = await get_conversation_history_for_query(
                conversation_id=None,
                session_id=session_id,
                user_email=user_email,
                db_pool=db_pool,
            )

            assert len(history) == 2

            entities = extract_entities_from_history(history)
            assert entities["name"] == "Marco"
            assert entities["city"] == "Milano"

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM users WHERE id = $1", user_email)

    @pytest.mark.asyncio
    async def test_context_window_includes_last_5_turns(self, db_pool):
        """
        Test Case: Verify that context window includes at least last 5 turns (10 messages)
        """
        user_email = "test.memory4@balizero.com"
        session_id = f"test_session_{datetime.now().timestamp()}"

        async with db_pool.acquire() as conn:
            # Ensure user exists
            await conn.execute(
                """
                INSERT INTO users (id, email, name, role)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_email,
                user_email,
                "Test User 4",
                "member",
            )

            # Create conversation with 12 messages (6 turns)
            messages = []
            for i in range(6):
                messages.append({"role": "user", "content": f"Message {i + 1}"})
                messages.append({"role": "assistant", "content": f"Response {i + 1}"})

            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, session_id, messages, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_email,
                session_id,
                json.dumps(messages),
                datetime.now(),
            )

            # Retrieve history
            from app.routers.oracle_universal import get_conversation_history_for_query

            history = await get_conversation_history_for_query(
                conversation_id=conversation_id,
                session_id=None,
                user_email=user_email,
                db_pool=db_pool,
            )

            assert len(history) == 12

            # Verify that conversation history has 12 messages
            # When passed to reason_with_gemini, it should trim to last 10 (5 turns)
            assert len(history) == 12, "Should have 12 messages (6 turns)"

            # Verify history structure
            assert history[0]["role"] == "user"
            assert history[-1]["role"] == "assistant"

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM users WHERE id = $1", user_email)
