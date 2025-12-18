"""
Debug Tests: Conversation Memory - Isolate Problem

These tests have extensive logging to debug:
1. What gets extracted from conversation history
2. What gets passed to reason_with_gemini
3. What gets saved to database
4. Where information might be lost

Run with: pytest -v -s --log-cli-level=DEBUG
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Setup logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestConversationMemoryDebug:
    """Debug tests with extensive logging"""

    @pytest.mark.asyncio
    async def test_debug_conversation_save_and_retrieve(self, db_pool):
        """
        DEBUG TEST 1: Verify conversation is saved correctly
        """
        logger.info("=" * 80)
        logger.info("DEBUG TEST 1: Conversation Save and Retrieve")
        logger.info("=" * 80)

        user_email = "debug.test@balizero.com"
        session_id = f"debug_session_{datetime.now().timestamp()}"

        async with db_pool.acquire() as conn:
            # Ensure user exists (use team_members table)
            await conn.execute(
                """
                INSERT INTO team_members (id, email, full_name, role)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_email,
                user_email,
                "Debug Test User",
                "member",
            )
            logger.info(f"✅ User created: {user_email}")

            # TURN 1: Save conversation
            turn1_messages = [
                {"role": "user", "content": "Mi chiamo Marco e sono di Milano"},
                {"role": "assistant", "content": "Ciao Marco! Piacere di conoscerti."},
            ]

            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, session_id, messages, created_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_email,
                session_id,
                json.dumps(turn1_messages),
                datetime.now(),
            )

            logger.info(f"✅ Conversation saved: id={conversation_id}, session_id={session_id}")
            logger.info(f"📝 Messages saved: {json.dumps(turn1_messages, indent=2)}")

            # Verify retrieval
            row = await conn.fetchrow(
                """
                SELECT id, user_id, session_id, messages, created_at
                FROM conversations
                WHERE id = $1
                """,
                conversation_id,
            )

            assert row is not None, "Conversation not found in database"
            logger.info("✅ Conversation retrieved from DB:")
            logger.info(f"   - ID: {row['id']}")
            logger.info(f"   - User ID: {row['user_id']}")
            logger.info(f"   - Session ID: {row['session_id']}")
            logger.info(f"   - Messages: {row['messages']}")
            logger.info(f"   - Created: {row['created_at']}")

            # Verify messages structure
            messages_retrieved = row["messages"]
            if isinstance(messages_retrieved, str):
                messages_retrieved = json.loads(messages_retrieved)

            assert (
                len(messages_retrieved) == 2
            ), f"Expected 2 messages, got {len(messages_retrieved)}"
            assert messages_retrieved[0]["role"] == "user"
            assert "Marco" in messages_retrieved[0]["content"]
            assert "Milano" in messages_retrieved[0]["content"]

            logger.info(f"✅ Messages structure verified: {len(messages_retrieved)} messages")

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM team_members WHERE id = $1", user_email)
            logger.info("✅ Cleanup completed")

    @pytest.mark.asyncio
    async def test_debug_entity_extraction(self, db_pool):
        """
        DEBUG TEST 2: Verify entity extraction works correctly
        """
        logger.info("=" * 80)
        logger.info("DEBUG TEST 2: Entity Extraction")
        logger.info("=" * 80)

        import sys

        backend_path = Path(__file__).parent.parent.parent / "backend"
        if str(backend_path) not in sys.path:
            sys.path.insert(0, str(backend_path))
        from app.routers.oracle_universal import extract_entities_from_history

        # Test case 1: Name and city
        conversation_history = [
            {"role": "user", "content": "Mi chiamo Marco e sono di Milano"},
            {"role": "assistant", "content": "Ciao Marco!"},
        ]

        logger.info(f"📝 Input conversation history: {json.dumps(conversation_history, indent=2)}")

        entities = extract_entities_from_history(conversation_history)

        logger.info("🔍 Extracted entities:")
        logger.info(f"   - Name: {entities['name']}")
        logger.info(f"   - City: {entities['city']}")
        logger.info(f"   - Budget: {entities['budget']}")
        logger.info(f"   - Preferences: {entities['preferences']}")

        assert entities["name"] == "Marco", f"Expected name 'Marco', got '{entities['name']}'"
        assert entities["city"] == "Milano", f"Expected city 'Milano', got '{entities['city']}'"

        logger.info("✅ Entity extraction verified")

        # Test case 2: Multiple user messages
        conversation_history_multi = [
            {"role": "user", "content": "Mi chiamo Marco"},
            {"role": "assistant", "content": "Ciao Marco!"},
            {"role": "user", "content": "Sono di Milano"},
            {"role": "assistant", "content": "Ottimo!"},
        ]

        logger.info(f"📝 Multi-turn conversation: {len(conversation_history_multi)} messages")
        entities_multi = extract_entities_from_history(conversation_history_multi)

        logger.info("🔍 Extracted entities (multi-turn):")
        logger.info(f"   - Name: {entities_multi['name']}")
        logger.info(f"   - City: {entities_multi['city']}")

        assert entities_multi["name"] == "Marco"
        assert entities_multi["city"] == "Milano"

        logger.info("✅ Multi-turn entity extraction verified")

    @pytest.mark.asyncio
    async def test_debug_conversation_history_retrieval(self, db_pool):
        """
        DEBUG TEST 3: Verify conversation history retrieval
        """
        logger.info("=" * 80)
        logger.info("DEBUG TEST 3: Conversation History Retrieval")
        logger.info("=" * 80)

        user_email = "debug.history@balizero.com"
        session_id = f"debug_history_{datetime.now().timestamp()}"

        async with db_pool.acquire() as conn:
            # Ensure user exists (use team_members table)
            await conn.execute(
                """
                INSERT INTO team_members (id, email, full_name, role)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_email,
                user_email,
                "Debug History User",
                "member",
            )

            # Save conversation with multiple turns
            messages = [
                {"role": "user", "content": "Mi chiamo Marco e sono di Milano"},
                {"role": "assistant", "content": "Ciao Marco!"},
                {"role": "user", "content": "Come mi chiamo?"},
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

            logger.info(f"✅ Conversation saved: id={conversation_id}")

            # Test retrieval by conversation_id
            from app.routers.oracle_universal import get_conversation_history_for_query

            history_by_id = await get_conversation_history_for_query(
                conversation_id=conversation_id,
                session_id=None,
                user_email=user_email,
                db_pool=db_pool,
            )

            logger.info("📚 History retrieved by conversation_id:")
            logger.info(f"   - Count: {len(history_by_id)} messages")
            for i, msg in enumerate(history_by_id):
                logger.info(f"   - Message {i + 1}: {msg['role']} - {msg['content'][:50]}...")

            assert len(history_by_id) == 3, f"Expected 3 messages, got {len(history_by_id)}"

            # Test retrieval by session_id
            history_by_session = await get_conversation_history_for_query(
                conversation_id=None,
                session_id=session_id,
                user_email=user_email,
                db_pool=db_pool,
            )

            logger.info("📚 History retrieved by session_id:")
            logger.info(f"   - Count: {len(history_by_session)} messages")
            for i, msg in enumerate(history_by_session):
                logger.info(f"   - Message {i + 1}: {msg['role']} - {msg['content'][:50]}...")

            assert (
                len(history_by_session) == 3
            ), f"Expected 3 messages, got {len(history_by_session)}"

            # Verify content
            assert history_by_id[0]["content"] == "Mi chiamo Marco e sono di Milano"
            assert history_by_id[2]["content"] == "Come mi chiamo?"

            logger.info("✅ Conversation history retrieval verified")

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM team_members WHERE id = $1", user_email)

    @pytest.mark.asyncio
    async def test_debug_hybrid_oracle_query_flow(self, db_pool):
        """
        DEBUG TEST 4: Full flow through hybrid_oracle_query
        """
        logger.info("=" * 80)
        logger.info("DEBUG TEST 4: Hybrid Oracle Query Flow")
        logger.info("=" * 80)

        user_email = "debug.oracle@balizero.com"
        session_id = f"debug_oracle_{datetime.now().timestamp()}"

        async with db_pool.acquire() as conn:
            # Ensure user exists (use team_members table)
            await conn.execute(
                """
                INSERT INTO team_members (id, email, full_name, role)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_email,
                user_email,
                "Debug Oracle User",
                "member",
            )

            # Save Turn 1 conversation
            turn1_messages = [
                {"role": "user", "content": "Mi chiamo Marco e sono di Milano"},
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
                json.dumps(turn1_messages),
                datetime.now(),
            )

            logger.info(f"✅ Turn 1 saved: conversation_id={conversation_id}")

            # Update with Turn 2
            turn2_messages = turn1_messages + [{"role": "user", "content": "Come mi chiamo?"}]
            await conn.execute(
                """
                UPDATE conversations SET messages = $1 WHERE id = $2
                """,
                json.dumps(turn2_messages),
                conversation_id,
            )

            logger.info(f"✅ Turn 2 added: {len(turn2_messages)} total messages")

            # Now test hybrid_oracle_query
            from app.routers.oracle_universal import OracleQueryRequest, hybrid_oracle_query

            # Setup mocks
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

            # Track what gets passed to reason_with_gemini
            captured_conversation_history = None
            captured_user_memory_facts = None

            def capture_reason_args(*args, **kwargs):
                nonlocal captured_conversation_history, captured_user_memory_facts
                captured_conversation_history = kwargs.get("conversation_history")
                captured_user_memory_facts = kwargs.get("user_memory_facts", [])
                logger.info("=" * 80)
                logger.info("🔍 CAPTURED: reason_with_gemini call arguments")
                logger.info("=" * 80)
                logger.info(f"📚 conversation_history: {captured_conversation_history}")
                logger.info(f"💾 user_memory_facts: {captured_user_memory_facts}")
                if captured_conversation_history:
                    logger.info(f"   - Count: {len(captured_conversation_history)} messages")
                    for i, msg in enumerate(captured_conversation_history):
                        logger.info(
                            f"   - Message {i + 1}: {msg.get('role')} - {msg.get('content', '')[:100]}..."
                        )
                logger.info("=" * 80)
                return {
                    "answer": "Ti chiami Marco, e sei di Milano!",
                    "model_used": "gemini-2.0-flash",
                    "reasoning_time_ms": 100,
                    "success": True,
                }

            with (
                patch("app.routers.oracle_universal.db_manager") as mock_db_manager,
                patch(
                    "app.routers.oracle_universal.reason_with_gemini",
                    side_effect=capture_reason_args,
                ) as mock_reason,
                patch("app.routers.oracle_universal.get_memory_service") as mock_memory_service,
                patch("core.embeddings.create_embeddings_generator") as mock_create_embedder,
            ):
                # Mock user profile
                mock_db_manager.get_user_profile = AsyncMock(
                    return_value={
                        "id": user_email,
                        "email": user_email,
                        "name": "Debug Oracle User",
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

                # Create request
                request = OracleQueryRequest(
                    query="Come mi chiamo?",
                    user_email=user_email,
                    conversation_id=conversation_id,
                    use_ai=True,
                )

                logger.info(
                    f"📤 Request: query='{request.query}', conversation_id={request.conversation_id}"
                )

                # Execute query
                response = await hybrid_oracle_query(request, mock_service, db_pool)

                logger.info("=" * 80)
                logger.info("📥 RESPONSE from hybrid_oracle_query")
                logger.info("=" * 80)
                logger.info(f"✅ Success: {response.success}")
                logger.info(f"💬 Answer: {response.answer}")
                logger.info(f"💾 User Memory Facts: {response.user_memory_facts}")
                logger.info(f"📊 Document Count: {response.document_count}")
                logger.info("=" * 80)

                # Verify conversation history was passed
                assert (
                    captured_conversation_history is not None
                ), "conversation_history was NOT passed to reason_with_gemini!"
                assert (
                    len(captured_conversation_history) >= 2
                ), f"Expected at least 2 messages, got {len(captured_conversation_history)}"

                # Verify entities were extracted and added to memory facts
                memory_facts_str = (
                    " ".join(captured_user_memory_facts) if captured_user_memory_facts else ""
                )
                logger.info("🔍 Checking memory facts for extracted entities...")
                logger.info(f"   - Memory facts string: {memory_facts_str}")

                # Entity extraction should add facts about Marco and Milano
                has_marco = "marco" in memory_facts_str.lower() or any(
                    "marco" in str(fact).lower() for fact in captured_user_memory_facts
                )
                has_milano = "milano" in memory_facts_str.lower() or any(
                    "milano" in str(fact).lower() for fact in captured_user_memory_facts
                )

                logger.info(f"   - Has 'Marco' in memory facts: {has_marco}")
                logger.info(f"   - Has 'Milano' in memory facts: {has_milano}")

                if not has_marco:
                    logger.warning("⚠️ WARNING: 'Marco' not found in memory facts!")
                if not has_milano:
                    logger.warning("⚠️ WARNING: 'Milano' not found in memory facts!")

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM team_members WHERE id = $1", user_email)

    @pytest.mark.asyncio
    async def test_debug_reason_with_gemini_context(self, db_pool):
        """
        DEBUG TEST 5: Verify what context is passed to reason_with_gemini
        """
        logger.info("=" * 80)
        logger.info("DEBUG TEST 5: reason_with_gemini Context")
        logger.info("=" * 80)

        conversation_history = [
            {"role": "user", "content": "Mi chiamo Marco e sono di Milano"},
            {"role": "assistant", "content": "Ciao Marco!"},
            {"role": "user", "content": "Come mi chiamo?"},
        ]

        from app.routers.oracle_universal import reason_with_gemini
        from backend.prompts.zantara_prompt_builder import PromptContext

        context = PromptContext(
            query="Come mi chiamo?",
            language="it",
            mode="default",
            emotional_state="neutral",
            user_name="Test",
            user_role="member",
        )

        user_memory_facts = [
            "User name: Marco",
            "User city: Milano",
        ]

        # Capture the actual prompt sent to Gemini
        captured_prompt = None

        def capture_gemini_call(*args, **kwargs):
            nonlocal captured_prompt
            # The prompt is in the user_message parameter
            if "user_message" in kwargs:
                captured_prompt = kwargs["user_message"]
            elif len(args) > 0:
                captured_prompt = str(args[0])
            logger.info("=" * 80)
            logger.info("🔍 CAPTURED: Prompt sent to Gemini")
            logger.info("=" * 80)
            if captured_prompt:
                # Show first 500 chars
                logger.info(f"📝 Prompt preview (first 500 chars):\n{captured_prompt[:500]}...")
                # Check if conversation history is in prompt
                if (
                    "CONVERSATION HISTORY" in captured_prompt
                    or "conversation" in captured_prompt.lower()
                ):
                    logger.info("✅ Conversation history found in prompt")
                else:
                    logger.warning("⚠️ WARNING: Conversation history NOT found in prompt!")
                # Check if Marco is in prompt
                if "marco" in captured_prompt.lower():
                    logger.info("✅ 'Marco' found in prompt")
                else:
                    logger.warning("⚠️ WARNING: 'Marco' NOT found in prompt!")
                # Check if Milano is in prompt
                if "milano" in captured_prompt.lower():
                    logger.info("✅ 'Milano' found in prompt")
                else:
                    logger.warning("⚠️ WARNING: 'Milano' NOT found in prompt!")
            logger.info("=" * 80)
            return {
                "answer": "Ti chiami Marco, e sei di Milano!",
                "model_used": "gemini-2.0-flash",
                "reasoning_time_ms": 100,
                "success": True,
            }

        with patch("app.routers.oracle_universal.google_services") as mock_google:
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Ti chiami Marco, e sei di Milano!"
            mock_model.generate_content = MagicMock(
                return_value=mock_response, side_effect=capture_gemini_call
            )
            mock_google.get_gemini_model.return_value = mock_model

            result = await reason_with_gemini(
                documents=[],
                query="Come mi chiamo?",
                context=context,
                use_full_docs=False,
                user_memory_facts=user_memory_facts,
                conversation_history=conversation_history,
            )

            logger.info(f"✅ reason_with_gemini result: {result['success']}")
            logger.info(f"💬 Answer: {result['answer']}")

            assert result["success"] is True
            assert captured_prompt is not None, "Prompt was not captured!"
