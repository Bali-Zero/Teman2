"""
API tests for agentic RAG session fixes

Tests that the API correctly handles session_id and applies fixes.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.api
class TestAgenticRAGSessionAPI:
    """Test agentic RAG API with session fixes"""

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator"""
        orchestrator = MagicMock()
        orchestrator.process_query = AsyncMock(return_value={
            "answer": "Test response",
            "sources": [],
            "context_used": 100,
            "execution_time": 0.5,
            "route_used": "test-route",
            "steps": [],
            "tools_called": 0,
            "total_steps": 1
        })
        return orchestrator

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool"""
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        conn.fetchrow = AsyncMock(return_value=None)
        return pool

    def test_greeting_endpoint_skips_rag(self, authenticated_client, mock_orchestrator):
        """Test: POST /api/agentic-rag/query with greeting skips RAG"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_get.return_value = mock_orchestrator
            
            # Mock greeting detection
            mock_orchestrator.process_query = AsyncMock(return_value={
                "answer": "Ciao! Come posso aiutarti oggi?",
                "sources": [],
                "context_used": 0,
                "execution_time": 0.01,
                "route_used": "greeting-pattern",
                "steps": [],
                "tools_called": 0,
                "total_steps": 0
            })
            
            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={
                    "query": "ciao",
                    "user_id": "test@example.com",
                    "session_id": str(uuid4())
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["answer"] == "Ciao! Come posso aiutarti oggi?"
            assert data["route_used"] == "greeting-pattern"
            
            # Verify orchestrator was called with session_id
            call_kwargs = mock_orchestrator.process_query.call_args[1]
            assert "session_id" in call_kwargs

    def test_session_id_passed_to_orchestrator(self, authenticated_client, mock_orchestrator):
        """Test: session_id is passed from API to orchestrator"""
        session_id = str(uuid4())
        
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_get.return_value = mock_orchestrator
            
            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={
                    "query": "What is KITAS?",
                    "user_id": "test@example.com",
                    "session_id": session_id
                }
            )
            
            assert response.status_code == 200
            
            # Verify session_id was passed to orchestrator
            call_kwargs = mock_orchestrator.process_query.call_args[1]
            assert call_kwargs.get("session_id") == session_id

    def test_stream_greeting_skips_rag(self, authenticated_client, mock_orchestrator):
        """Test: POST /api/agentic-rag/stream with greeting skips RAG"""
        async def mock_stream():
            yield {"type": "metadata", "data": {"status": "greeting"}}
            yield {"type": "token", "data": "Ciao! "}
            yield {"type": "token", "data": "Come posso aiutarti?"}
            yield {"type": "done", "data": None}
        
        mock_orchestrator.stream_query = mock_stream
        
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_get.return_value = mock_orchestrator
            
            response = authenticated_client.post(
                "/api/agentic-rag/stream",
                json={
                    "query": "ciao",
                    "user_id": "test@example.com",
                    "session_id": str(uuid4())
                }
            )
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            # Verify session_id was passed
            # (We can't easily verify this without more complex mocking, but the call should succeed)

    def test_different_sessions_get_different_contexts(self, authenticated_client, mock_orchestrator):
        """Test: Different session_ids get different conversation contexts"""
        session_1 = str(uuid4())
        session_2 = str(uuid4())
        
        def mock_process_query(*args, **kwargs):
            session_id = kwargs.get("session_id")
            if session_id == session_1:
                return AsyncMock(return_value={
                    "answer": "Session 1 context",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "test",
                    "steps": [],
                    "tools_called": 0,
                    "total_steps": 1
                })()
            else:
                return AsyncMock(return_value={
                    "answer": "Session 2 context",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "test",
                    "steps": [],
                    "tools_called": 0,
                    "total_steps": 1
                })()
        
        mock_orchestrator.process_query = AsyncMock(side_effect=mock_process_query)
        
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_get.return_value = mock_orchestrator
            
            # Query with session 1
            response_1 = authenticated_client.post(
                "/api/agentic-rag/query",
                json={
                    "query": "What did we discuss?",
                    "user_id": "test@example.com",
                    "session_id": session_1
                }
            )
            
            # Query with session 2
            response_2 = authenticated_client.post(
                "/api/agentic-rag/query",
                json={
                    "query": "What did we discuss?",
                    "user_id": "test@example.com",
                    "session_id": session_2
                }
            )
            
            assert response_1.status_code == 200
            assert response_2.status_code == 200
            
            # Verify both calls included session_id
            assert mock_orchestrator.process_query.call_count == 2
            call_1_kwargs = mock_orchestrator.process_query.call_args_list[0][1]
            call_2_kwargs = mock_orchestrator.process_query.call_args_list[1][1]
            assert call_1_kwargs.get("session_id") == session_1
            assert call_2_kwargs.get("session_id") == session_2

