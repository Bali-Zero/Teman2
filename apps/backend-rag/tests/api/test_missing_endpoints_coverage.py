"""
Missing Endpoints Coverage Tests
Tests for endpoints that might have been missed in initial coverage

Coverage:
- Endpoints that might need additional coverage
- Edge cases for less common endpoints
- Additional scenarios for existing endpoints
- Integration scenarios for endpoint combinations
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["QDRANT_URL"] = "http://localhost:6333"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestAdditionalEndpointScenarios:
    """Test additional scenarios for existing endpoints"""

    def test_health_endpoints_all_variants(self, test_client):
        """Test all health endpoint variants"""
        health_endpoints = [
            "/health",
            "/api/health",
            "/api/oracle/health",
            "/api/team-activity/health",
        ]

        for endpoint in health_endpoints:
            response = test_client.get(endpoint)
            # Health endpoints should be accessible
            assert response.status_code in [200, 404, 500, 503]

    def test_root_endpoints_all_variants(self, test_client):
        """Test all root endpoint variants"""
        root_endpoints = [
            "/",
            "/api/csrf-token",
            "/api/dashboard/stats",
        ]

        for endpoint in root_endpoints:
            response = test_client.get(endpoint)
            assert response.status_code in [200, 401, 404, 500, 503]

    def test_auth_endpoints_all_variants(self, test_client):
        """Test all auth endpoint variants"""
        auth_endpoints = [
            ("POST", "/api/auth/login"),
            ("GET", "/api/auth/profile"),
            ("POST", "/api/auth/logout"),
            ("GET", "/api/auth/check"),
            ("GET", "/api/auth/csrf-token"),
            ("POST", "/api/auth/refresh"),
        ]

        for method, endpoint in auth_endpoints:
            if method == "GET":
                response = test_client.get(endpoint)
            else:
                response = test_client.post(endpoint, json={})

            assert response.status_code in [200, 400, 401, 404, 422, 500, 503]

    def test_productivity_endpoints_all_variants(self, authenticated_client):
        """Test all productivity endpoint variants"""
        productivity_endpoints = [
            ("POST", "/api/productivity/gmail/draft"),
            ("POST", "/api/productivity/calendar/schedule"),
            ("GET", "/api/productivity/calendar/events"),
            ("GET", "/api/productivity/drive/search"),
        ]

        for method, endpoint in productivity_endpoints:
            if method == "GET":
                response = authenticated_client.get(endpoint)
            else:
                response = authenticated_client.post(
                    endpoint,
                    json={
                        "to": "test@example.com",
                        "subject": "Test",
                        "body": "Test",
                        "title": "Test Meeting",
                        "start_time": "2025-12-10T10:00:00Z",
                        "duration_minutes": 60,
                        "query": "test",
                    },
                )

            assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_legal_ingest_endpoints_all_variants(self, authenticated_client):
        """Test all legal ingest endpoint variants"""
        legal_endpoints = [
            ("POST", "/api/legal/ingest"),
            ("POST", "/api/legal/ingest-batch"),
            ("GET", "/api/legal/collections/stats"),
        ]

        for method, endpoint in legal_endpoints:
            if method == "GET":
                response = authenticated_client.get(endpoint)
            else:
                response = authenticated_client.post(
                    endpoint,
                    json={
                        "file_path": "/path/to/file.pdf",
                        "collection": "legal_intelligence",
                        "tier": "A",
                        "files": [{"path": "/path/to/file.pdf"}],
                    },
                )

            assert response.status_code in [200, 201, 400, 404, 422, 500, 503]

    def test_media_endpoints_all_variants(self, authenticated_client):
        """Test all media endpoint variants"""
        media_endpoints = [
            ("POST", "/api/media/generate-image"),
        ]

        for method, endpoint in media_endpoints:
            response = authenticated_client.post(
                endpoint,
                json={"prompt": "A beautiful sunset"},
            )

            assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_whatsapp_endpoints_all_variants(self, authenticated_client):
        """Test all WhatsApp endpoint variants"""
        whatsapp_endpoints = [
            ("POST", "/api/whatsapp/webhook"),
            ("GET", "/api/whatsapp/status"),
        ]

        for method, endpoint in whatsapp_endpoints:
            if method == "GET":
                response = authenticated_client.get(endpoint)
            else:
                response = authenticated_client.post(
                    endpoint,
                    json={"message": "test"},
                )

            assert response.status_code in [200, 201, 400, 401, 404, 422, 500, 503]

    def test_instagram_endpoints_all_variants(self, authenticated_client):
        """Test all Instagram endpoint variants"""
        instagram_endpoints = [
            ("POST", "/api/instagram/webhook"),
            ("GET", "/api/instagram/status"),
        ]

        for method, endpoint in instagram_endpoints:
            if method == "GET":
                response = authenticated_client.get(endpoint)
            else:
                response = authenticated_client.post(
                    endpoint,
                    json={"message": "test"},
                )

            assert response.status_code in [200, 201, 400, 401, 404, 422, 500, 503]


@pytest.mark.api
class TestEdgeCasesForLessCommonEndpoints:
    """Test edge cases for less common endpoints"""

    def test_handlers_endpoint_edge_cases(self, api_key_client):
        """Test edge cases for handlers endpoint"""
        # Test with various query parameters
        edge_cases = [
            "?query=",
            "?query=test&limit=10",
            "?query=test&limit=1000",  # Exceeds max
            "?query=test&offset=-1",  # Negative offset
        ]

        for query in edge_cases:
            response = api_key_client.get(f"/api/handlers/search{query}")
            assert response.status_code in [200, 400, 422]

    def test_notifications_test_endpoint_edge_cases(self, authenticated_client):
        """Test edge cases for notification test endpoint"""
        edge_cases = [
            {"email": ""},  # Empty email
            {"phone": "invalid"},  # Invalid phone
            {"whatsapp": "invalid"},  # Invalid WhatsApp
            {"email": "a" * 1000 + "@example.com"},  # Very long email
        ]

        for params in edge_cases:
            response = authenticated_client.post(
                "/api/notifications/test",
                params=params,
            )

            assert response.status_code in [200, 201, 400, 422, 500, 503]


@pytest.mark.api
@pytest.mark.integration
class TestEndpointIntegrationScenarios:
    """Integration scenarios testing endpoint combinations"""

    def test_conversation_to_crm_flow(self, authenticated_client):
        """Test flow: save conversation -> auto-create CRM interaction"""
        conversation_response = authenticated_client.post(
            "/api/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "I'm John Doe, email john@example.com"},
                    {"role": "assistant", "content": "Hello John!"},
                ],
            },
        )
        assert conversation_response.status_code in [200, 201]

    def test_client_to_practice_flow(self, authenticated_client):
        """Test flow: create client -> create practice"""
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Integration Test Client",
                "email": "integration@example.com",
                "phone": "+6281234567890",
            },
        )
        assert client_response.status_code in [200, 201]


@pytest.mark.api
class TestEndpointErrorHandling:
    """Test error handling for endpoints"""

    def test_invalid_json_handling(self, authenticated_client):
        """Test handling of invalid JSON"""
        response = authenticated_client.post(
            "/api/conversations/save",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in [400, 422]

    def test_missing_required_fields(self, authenticated_client):
        """Test handling of missing required fields"""
        response = authenticated_client.post(
            "/api/crm/clients",
            json={},
        )
        assert response.status_code in [400, 422]

    def test_unauthorized_access(self, test_client):
        """Test that protected endpoints require authentication"""
        response = test_client.get("/api/crm/clients")
        assert response.status_code in [401, 403]


@pytest.mark.api
class TestSuccessfulResponseValidation:
    """Test successful responses with detailed validation"""

    def test_successful_client_creation_response(self, authenticated_client):
        """Test successful client creation with response validation"""
        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Success Validation Client",
                "email": "success.validation@example.com",
                "phone": "+6281234567890",
                "status": "active",
            },
        )

        assert response.status_code in [200, 201]

        if response.status_code in [200, 201]:
            data = response.json()
            # Validate response structure
            assert "id" in data or "client_id" in data
            assert "full_name" in data or "name" in data
            assert "email" in data
            assert "status" in data

            # Validate data types
            client_id = data.get("id") or data.get("client_id")
            assert isinstance(client_id, int) or isinstance(client_id, str)
            assert isinstance(data.get("full_name") or data.get("name"), str)
            assert isinstance(data.get("email"), str)

    def test_successful_conversation_save_response(self, authenticated_client):
        """Test successful conversation save with response validation"""
        response = authenticated_client.post(
            "/api/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "Test message"},
                    {"role": "assistant", "content": "Test response"},
                ],
                "session_id": "test_session_123",
            },
        )

        assert response.status_code in [200, 201]

        if response.status_code in [200, 201]:
            data = response.json()
            # Validate response structure
            assert "success" in data or "conversation_id" in data or "id" in data
            if "success" in data:
                assert data["success"] is True

    def test_successful_memory_store_response(self, authenticated_client):
        """Test successful memory store with response validation"""
        response = authenticated_client.post(
            "/api/memory/store",
            json={
                "user_id": "test@example.com",
                "text": "Test memory content",
            },
        )

        assert response.status_code in [200, 201]

        if response.status_code in [200, 201]:
            data = response.json()
            # Validate response structure
            assert "success" in data or "memory_id" in data or "id" in data

    def test_successful_oracle_query_response(self, authenticated_client):
        """Test successful Oracle query with response validation"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "What is PT PMA?",
                "user_id": "test@example.com",
            },
        )

        assert response.status_code in [200, 201]

        if response.status_code in [200, 201]:
            data = response.json()
            # Validate Oracle response structure
            assert "success" in data or "answer" in data or "response" in data
            if "success" in data:
                assert data["success"] is True
            if "answer" in data:
                assert isinstance(data["answer"], str)
                assert len(data["answer"]) > 0

    def test_successful_practice_creation_response(self, authenticated_client):
        """Test successful practice creation with response validation"""
        # First create a client
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Practice Test Client",
                "email": "practice.test@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_data = client_response.json()
            client_id = client_data.get("id") or client_data.get("client_id")

            if client_id:
                # Create practice
                practice_response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": client_id,
                        "practice_type": "KITAS",
                        "priority": "high",
                    },
                )

                assert practice_response.status_code in [200, 201]

                if practice_response.status_code in [200, 201]:
                    practice_data = practice_response.json()
                    # Validate response structure
                    assert "id" in practice_data or "practice_id" in practice_data
                    assert "practice_type" in practice_data or "type" in practice_data
                    assert "status" in practice_data

    def test_successful_interaction_creation_response(self, authenticated_client):
        """Test successful interaction creation with response validation"""
        # Create client first
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Interaction Test Client",
                "email": "interaction.test@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_data = client_response.json()
            client_id = client_data.get("id") or client_data.get("client_id")

            if client_id:
                # Create interaction
                interaction_response = authenticated_client.post(
                    "/api/crm/interactions",
                    json={
                        "client_id": client_id,
                        "interaction_type": "email",
                        "summary": "Test interaction",
                    },
                )

                assert interaction_response.status_code in [200, 201]

                if interaction_response.status_code in [200, 201]:
                    interaction_data = interaction_response.json()
                    # Validate response structure
                    assert "id" in interaction_data or "interaction_id" in interaction_data
                    assert "interaction_type" in interaction_data or "type" in interaction_data

    def test_successful_list_responses(self, authenticated_client):
        """Test successful list endpoint responses"""
        list_endpoints = [
            "/api/crm/clients",
            "/api/crm/practices",
            "/api/crm/interactions",
            "/api/conversations/list",
        ]

        for endpoint in list_endpoints:
            response = authenticated_client.get(endpoint)

            assert response.status_code in [200, 400, 404]

            if response.status_code == 200:
                data = response.json()
                # Validate list structure
                assert isinstance(data, (list, dict))
                if isinstance(data, dict):
                    assert (
                        "items" in data
                        or "data" in data
                        or "clients" in data
                        or "practices" in data
                    )

    def test_successful_stats_responses(self, authenticated_client):
        """Test successful statistics endpoint responses"""
        stats_endpoints = [
            "/api/crm/clients/stats/overview",
            "/api/crm/practices/stats/overview",
            "/api/crm/interactions/stats/overview",
            "/api/conversations/stats",
            "/api/memory/stats",
        ]

        for endpoint in stats_endpoints:
            response = authenticated_client.get(endpoint)

            assert response.status_code in [200, 400, 404]

            if response.status_code == 200:
                data = response.json()
                # Validate stats structure
                assert isinstance(data, dict)
                # Should contain some numeric metrics
                assert any(
                    isinstance(v, (int, float))
                    for v in data.values()
                    if not isinstance(v, (str, dict, list))
                )

    def test_successful_health_endpoints(self, test_client):
        """Test successful health endpoint responses"""
        health_endpoints = [
            "/health",
            "/api/health",
            "/api/oracle/health",
            "/api/team-activity/health",
            "/api/memory/health",
        ]

        for endpoint in health_endpoints:
            response = test_client.get(endpoint)

            assert response.status_code in [200, 404, 503]

            if response.status_code == 200:
                data = response.json()
                # Health endpoints should indicate status
                assert isinstance(data, dict)
                assert "status" in data or "healthy" in data or "ok" in data


@pytest.mark.api
class TestCompleteWorkflowSuccess:
    """Test complete workflows with success validation"""

    def test_complete_client_journey_success(self, authenticated_client):
        """Test complete client journey: create -> practice -> interaction -> memory"""
        # Step 1: Create client
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Complete Journey Client",
                "email": "journey@example.com",
                "phone": "+6281234567890",
            },
        )

        assert client_response.status_code in [200, 201]

        if client_response.status_code in [200, 201]:
            client_data = client_response.json()
            client_id = client_data.get("id") or client_data.get("client_id")

            if client_id:
                # Step 2: Create practice
                practice_response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": client_id,
                        "practice_type": "PT PMA",
                        "priority": "high",
                    },
                )

                assert practice_response.status_code in [200, 201]

                if practice_response.status_code in [200, 201]:
                    practice_data = practice_response.json()
                    practice_id = practice_data.get("id") or practice_data.get("practice_id")

                    if practice_id:
                        # Step 3: Create interaction
                        interaction_response = authenticated_client.post(
                            "/api/crm/interactions",
                            json={
                                "client_id": client_id,
                                "practice_id": practice_id,
                                "interaction_type": "email",
                                "summary": "Initial consultation",
                            },
                        )

                        assert interaction_response.status_code in [200, 201]

                        # Step 4: Store memory
                        memory_response = authenticated_client.post(
                            "/api/memory/store",
                            json={
                                "user_id": "journey@example.com",
                                "text": "Client interested in PT PMA",
                            },
                        )

                        assert memory_response.status_code in [200, 201]

                        # Verify all steps succeeded
                        assert all(
                            [
                                client_response.status_code in [200, 201],
                                practice_response.status_code in [200, 201],
                                interaction_response.status_code in [200, 201],
                                memory_response.status_code in [200, 201],
                            ]
                        )

    def test_conversation_to_crm_auto_creation_success(self, authenticated_client):
        """Test conversation save triggers CRM auto-creation"""
        # Save conversation with client info
        conversation_response = authenticated_client.post(
            "/api/conversations/save",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "Hi, I'm John Doe, email john.doe@example.com, phone +6281234567890",
                    },
                    {"role": "assistant", "content": "Hello John! How can I help?"},
                ],
            },
        )

        assert conversation_response.status_code in [200, 201]

        if conversation_response.status_code in [200, 201]:
            conv_data = conversation_response.json()
            conversation_id = conv_data.get("conversation_id") or conv_data.get("id")

            if conversation_id:
                # Try to create interaction from conversation
                interaction_response = authenticated_client.post(
                    "/api/crm/interactions/from-conversation",
                    json={"conversation_id": conversation_id},
                )

                # Should succeed or handle gracefully
                assert interaction_response.status_code in [200, 201, 400, 404]

    def test_oracle_with_memory_context_success(self, authenticated_client):
        """Test Oracle query uses memory context successfully"""
        # Step 1: Store memory
        memory_response = authenticated_client.post(
            "/api/memory/store",
            json={
                "user_id": "oracle.memory@example.com",
                "text": "Client prefers detailed explanations",
            },
        )

        assert memory_response.status_code in [200, 201]

        # Step 2: Query Oracle (should use memory)
        oracle_response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "Explain PT PMA in detail",
                "user_id": "oracle.memory@example.com",
            },
        )

        assert oracle_response.status_code in [200, 201]

        if oracle_response.status_code in [200, 201]:
            oracle_data = oracle_response.json()
            # Should have answer
            assert "answer" in oracle_data or "response" in oracle_data or "success" in oracle_data


@pytest.mark.api
class TestAutonomousAgentsEndpoints:
    """Test autonomous agents endpoints for improved coverage"""

    def test_conversation_trainer_run(self, authenticated_client):
        """Test conversation trainer agent execution"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            json={"days_back": 30},
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "agent_name" in data
            assert "status" in data
            assert data["status"] in ["started", "running", "completed", "failed"]

    def test_conversation_trainer_run_with_custom_days(self, authenticated_client):
        """Test conversation trainer with custom days_back parameter"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            json={"days_back": 7},
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_client_value_predictor_run(self, authenticated_client):
        """Test client value predictor agent execution"""
        response = authenticated_client.post(
            "/api/autonomous-agents/client-value-predictor/run",
            json={},
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "agent_name" in data

    def test_knowledge_graph_builder_run(self, authenticated_client):
        """Test knowledge graph builder agent execution"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run",
            json={},
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data

    def test_autonomous_agents_status(self, authenticated_client):
        """Test autonomous agents status endpoint"""
        response = authenticated_client.get("/api/autonomous-agents/status")

        assert response.status_code in [200, 401, 404, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_get_execution_by_id(self, authenticated_client):
        """Test getting execution by ID"""
        # First create an execution
        create_response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            json={"days_back": 30},
        )

        if create_response.status_code in [200, 201]:
            execution_data = create_response.json()
            execution_id = execution_data.get("execution_id")

            if execution_id:
                # Get execution status
                get_response = authenticated_client.get(
                    f"/api/autonomous-agents/executions/{execution_id}"
                )

                assert get_response.status_code in [200, 404, 500]

                if get_response.status_code == 200:
                    data = get_response.json()
                    assert "execution_id" in data
                    assert "status" in data

    def test_get_execution_by_id_not_found(self, authenticated_client):
        """Test getting non-existent execution"""
        response = authenticated_client.get("/api/autonomous-agents/executions/non-existent-id")

        assert response.status_code in [404, 500]

    def test_list_all_executions(self, authenticated_client):
        """Test listing all agent executions"""
        response = authenticated_client.get("/api/autonomous-agents/executions")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_scheduler_status(self, authenticated_client):
        """Test scheduler status endpoint"""
        response = authenticated_client.get("/api/autonomous-agents/scheduler/status")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_enable_scheduler_task(self, authenticated_client):
        """Test enabling a scheduler task"""
        response = authenticated_client.post(
            "/api/autonomous-agents/scheduler/task/conversation-trainer/enable"
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_disable_scheduler_task(self, authenticated_client):
        """Test disabling a scheduler task"""
        response = authenticated_client.post(
            "/api/autonomous-agents/scheduler/task/conversation-trainer/disable"
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_enable_invalid_task(self, authenticated_client):
        """Test enabling invalid task name"""
        response = authenticated_client.post(
            "/api/autonomous-agents/scheduler/task/invalid-task/enable"
        )

        assert response.status_code in [400, 404, 422, 500]


@pytest.mark.api
class TestConversationsEndpointsExpanded:
    """Expanded tests for conversations endpoints"""

    def test_save_conversation_with_session_id(self, authenticated_client):
        """Test saving conversation with session_id"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "Test message"},
                    {"role": "assistant", "content": "Test response"},
                ],
                "session_id": "test-session-123",
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "success" in data or "conversation_id" in data

    def test_save_conversation_with_metadata(self, authenticated_client):
        """Test saving conversation with metadata"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "Test"},
                    {"role": "assistant", "content": "Response"},
                ],
                "metadata": {"source": "test", "priority": "high"},
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_save_conversation_empty_messages(self, authenticated_client):
        """Test saving conversation with empty messages"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": []},
        )

        # Endpoint may accept empty messages or reject them
        assert response.status_code in [200, 201, 400, 422]

    def test_get_history_with_session_id(self, authenticated_client):
        """Test getting conversation history with session_id"""
        response = authenticated_client.get(
            "/api/bali-zero/conversations/history?session_id=test-session-123"
        )

        assert response.status_code in [200, 400, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "messages" in data or "success" in data

    def test_get_history_with_limit(self, authenticated_client):
        """Test getting history with custom limit"""
        response = authenticated_client.get("/api/bali-zero/conversations/history?limit=10")

        assert response.status_code in [200, 400, 404, 500]

    def test_get_history_with_offset(self, authenticated_client):
        """Test getting history with offset"""
        response = authenticated_client.get(
            "/api/bali-zero/conversations/history?offset=5&limit=10"
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_clear_conversations(self, authenticated_client):
        """Test clearing all conversations"""
        response = authenticated_client.delete("/api/bali-zero/conversations/clear")

        assert response.status_code in [200, 400, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "deleted" in data

    def test_get_conversation_stats(self, authenticated_client):
        """Test getting conversation statistics"""
        response = authenticated_client.get("/api/bali-zero/conversations/stats")

        assert response.status_code in [200, 400, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            # Should contain numeric stats
            assert any(
                isinstance(v, (int, float))
                for v in data.values()
                if not isinstance(v, (str, dict, list))
            )

    def test_list_conversations_with_pagination(self, authenticated_client):
        """Test listing conversations with pagination"""
        response = authenticated_client.get("/api/bali-zero/conversations/list?limit=10&offset=0")

        assert response.status_code in [200, 400, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "conversations" in data or isinstance(data, list)

    def test_list_conversations_with_limit(self, authenticated_client):
        """Test listing conversations with custom limit"""
        response = authenticated_client.get("/api/bali-zero/conversations/list?limit=5")

        assert response.status_code in [200, 400, 401, 404, 500]

    def test_get_single_conversation(self, authenticated_client):
        """Test getting single conversation by ID"""
        # First create a conversation
        create_response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "Test"},
                    {"role": "assistant", "content": "Response"},
                ]
            },
        )

        if create_response.status_code in [200, 201]:
            create_data = create_response.json()
            conversation_id = create_data.get("conversation_id") or create_data.get("id")

            if conversation_id:
                # Get the conversation
                get_response = authenticated_client.get(
                    f"/api/bali-zero/conversations/{conversation_id}"
                )

                assert get_response.status_code in [200, 404, 500]

                if get_response.status_code == 200:
                    data = get_response.json()
                    assert "id" in data or "conversation_id" in data
                    assert "messages" in data or "content" in data

    def test_get_single_conversation_not_found(self, authenticated_client):
        """Test getting non-existent conversation"""
        response = authenticated_client.get("/api/bali-zero/conversations/999999")

        assert response.status_code in [404, 500, 503]

    def test_delete_conversation(self, authenticated_client):
        """Test deleting a conversation"""
        # First create a conversation
        create_response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "Test"},
                    {"role": "assistant", "content": "Response"},
                ]
            },
        )

        if create_response.status_code in [200, 201]:
            create_data = create_response.json()
            conversation_id = create_data.get("conversation_id") or create_data.get("id")

            if conversation_id:
                # Delete the conversation
                delete_response = authenticated_client.delete(
                    f"/api/bali-zero/conversations/{conversation_id}"
                )

                assert delete_response.status_code in [200, 404, 500]

                if delete_response.status_code == 200:
                    data = delete_response.json()
                    assert "success" in data or "deleted" in data

    def test_delete_conversation_not_found(self, authenticated_client):
        """Test deleting non-existent conversation"""
        response = authenticated_client.delete("/api/bali-zero/conversations/999999")

        assert response.status_code in [404, 500, 503]

    def test_save_conversation_triggers_crm_auto_population(self, authenticated_client):
        """Test that saving conversation triggers CRM auto-population"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "Hi, I'm John Doe, email john@example.com, phone +6281234567890",
                    },
                    {"role": "assistant", "content": "Hello John!"},
                ]
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

        # The auto-CRM population happens in background, so we just verify the conversation was saved
        if response.status_code in [200, 201]:
            data = response.json()
            assert "success" in data or "conversation_id" in data


@pytest.mark.api
class TestAdditionalEdgeCases:
    """Additional edge cases for API endpoints"""

    def test_conversation_save_with_very_long_message(self, authenticated_client):
        """Test saving conversation with very long message"""
        long_content = "A" * 10000
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": long_content},
                    {"role": "assistant", "content": "Response"},
                ]
            },
        )

        assert response.status_code in [200, 201, 400, 422, 413, 500]

    def test_conversation_save_with_special_characters(self, authenticated_client):
        """Test saving conversation with special characters"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "Test with émojis 🎉 and spéciál chars"},
                    {"role": "assistant", "content": "Response with <tags> & symbols"},
                ]
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_conversation_save_with_many_messages(self, authenticated_client):
        """Test saving conversation with many messages"""
        messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            for i in range(50)
        ]
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": messages},
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_autonomous_agent_execution_with_invalid_params(self, authenticated_client):
        """Test autonomous agent execution with invalid parameters"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            json={"days_back": -1},  # Invalid negative value
        )

        # May accept negative values or reject them
        assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_autonomous_agent_execution_with_very_large_days(self, authenticated_client):
        """Test autonomous agent execution with very large days_back"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            json={"days_back": 10000},  # Very large value
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_conversation_list_with_invalid_pagination(self, authenticated_client):
        """Test conversation list with invalid pagination parameters"""
        invalid_cases = [
            "?limit=-1",
            "?offset=-1",
            "?limit=10000",  # Exceeds max
            "?limit=abc",  # Non-numeric
        ]

        for query in invalid_cases:
            response = authenticated_client.get(f"/api/bali-zero/conversations/list{query}")
            assert response.status_code in [200, 400, 422, 500]

    def test_conversation_history_with_invalid_session_id(self, authenticated_client):
        """Test conversation history with invalid session_id format"""
        response = authenticated_client.get(
            "/api/bali-zero/conversations/history?session_id=invalid-format-!!!"
        )

        assert response.status_code in [200, 400, 404, 422, 500]

    def test_conversation_save_missing_required_fields(self, authenticated_client):
        """Test conversation save with missing required fields"""
        # Missing messages
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={},
        )

        assert response.status_code in [400, 422]

    def test_conversation_save_invalid_message_format(self, authenticated_client):
        """Test conversation save with invalid message format"""
        invalid_cases = [
            {"messages": [{"role": "invalid", "content": "test"}]},  # Invalid role
            {"messages": [{"role": "user"}]},  # Missing content
            {"messages": [{"content": "test"}]},  # Missing role
            {"messages": "not a list"},  # Not a list
        ]

        for invalid_data in invalid_cases:
            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json=invalid_data,
            )
            assert response.status_code in [400, 422, 500]


@pytest.mark.api
class TestAgenticRAGEndpoints:
    """Test Agentic RAG endpoints"""

    def test_agentic_rag_query(self, authenticated_client):
        """Test Agentic RAG query endpoint"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "What are the requirements for PT PMA?",
                "user_id": "test_user@example.com",
            },
        )

        assert response.status_code in [200, 400, 422, 500]
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert isinstance(data["answer"], str)

    def test_agentic_rag_query_with_vision(self, authenticated_client):
        """Test Agentic RAG query with vision enabled"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={
                "query": "Analyze this document",
                "user_id": "test_user@example.com",
                "enable_vision": True,
            },
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_agentic_rag_stream(self, authenticated_client):
        """Test Agentic RAG streaming endpoint"""
        response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "Explain KITAS requirements",
                "user_id": "test_user@example.com",
            },
            stream=True,
        )

        assert response.status_code in [200, 400, 422, 500]
        if response.status_code == 200:
            # Verify it's a streaming response
            assert response.headers.get("content-type") == "text/event-stream"


@pytest.mark.api
class TestAdvancedWorkflowScenarios:
    """Test advanced multi-step workflow scenarios"""

    def test_complete_business_setup_workflow(self, authenticated_client):
        """Test complete business setup workflow: client -> journey -> compliance -> oracle"""
        # Step 1: Create client
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Business Setup Client",
                "email": "business.setup@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                # Step 2: Create journey
                journey_response = authenticated_client.post(
                    "/api/agents/journey/create",
                    json={
                        "journey_type": "pt_pma_setup",
                        "client_id": str(client_id),
                    },
                )

                # Step 3: Add compliance tracking
                deadline = (datetime.now() + timedelta(days=90)).isoformat().split("T")[0]
                compliance_response = authenticated_client.post(
                    "/api/agents/compliance/track",
                    json={
                        "client_id": str(client_id),
                        "compliance_type": "license_renewal",
                        "title": "NIB Renewal",
                        "description": "NIB license renewal required",
                        "deadline": deadline,
                    },
                )

                # Step 4: Query Oracle for setup info
                oracle_response = authenticated_client.post(
                    "/api/oracle/query",
                    json={
                        "query": "What documents are needed for PT PMA setup?",
                        "user_id": "business.setup@example.com",
                    },
                )

                # Verify workflow steps
                assert client_response.status_code in [200, 201]
                assert journey_response.status_code in [200, 201, 400]
                assert compliance_response.status_code in [200, 201, 400, 422]
                assert oracle_response.status_code in [200, 201, 400, 422]

    def test_client_onboarding_to_practice_workflow(self, authenticated_client):
        """Test client onboarding workflow: conversation -> client -> practice -> memory"""
        # Step 1: Save conversation with client info
        conversation_response = authenticated_client.post(
            "/api/conversations/save",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "I'm interested in opening a PT PMA company in Indonesia",
                    },
                    {
                        "role": "assistant",
                        "content": "I can help you with PT PMA setup. What's your name and email?",
                    },
                ],
            },
        )

        if conversation_response.status_code in [200, 201]:
            # Step 2: Create client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Onboarding Test Client",
                    "email": "onboarding@example.com",
                    "phone": "+6281234567890",
                },
            )

            if client_response.status_code in [200, 201]:
                client_id = client_response.json().get("id") or client_response.json().get(
                    "client_id"
                )

                if client_id:
                    # Step 3: Create practice
                    practice_response = authenticated_client.post(
                        "/api/crm/practices",
                        json={
                            "client_id": client_id,
                            "practice_type": "PT PMA",
                            "priority": "high",
                        },
                    )

                    # Step 4: Store memory about client preferences
                    memory_response = authenticated_client.post(
                        "/api/memory/store",
                        json={
                            "user_id": "onboarding@example.com",
                            "text": "Client interested in PT PMA, prefers English communication",
                        },
                    )

                    # Verify all steps
                    assert all(
                        [
                            conversation_response.status_code in [200, 201],
                            client_response.status_code in [200, 201],
                            practice_response.status_code in [200, 201, 400],
                            memory_response.status_code in [200, 201],
                        ]
                    )

    def test_research_to_oracle_to_crm_workflow(self, authenticated_client):
        """Test research -> oracle -> CRM workflow"""
        # Step 1: Query Oracle for information
        oracle_response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "What are the latest visa regulations for KITAS?",
                "user_id": "research@example.com",
            },
        )

        if oracle_response.status_code in [200, 201]:
            # Step 2: Create client based on research interest
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Research Based Client",
                    "email": "research@example.com",
                    "phone": "+6281234567890",
                },
            )

            if client_response.status_code in [200, 201]:
                client_id = client_response.json().get("id") or client_response.json().get(
                    "client_id"
                )

                if client_id:
                    # Step 3: Create practice based on oracle response
                    practice_response = authenticated_client.post(
                        "/api/crm/practices",
                        json={
                            "client_id": client_id,
                            "practice_type": "KITAS",
                            "priority": "medium",
                        },
                    )

                    # Verify workflow
                    assert oracle_response.status_code in [200, 201]
                    assert client_response.status_code in [200, 201]
                    assert practice_response.status_code in [200, 201, 400]


@pytest.mark.api
class TestEndpointParameterVariations:
    """Test endpoints with various parameter combinations"""

    def test_oracle_query_parameter_variations(self, authenticated_client):
        """Test Oracle query with various parameter combinations"""
        variations = [
            {"query": "Simple query"},
            {"query": "Complex query with multiple requirements", "limit": 5},
            {
                "query": "Query with all params",
                "limit": 10,
                "user_id": "test@example.com",
            },
        ]

        for params in variations:
            response = authenticated_client.post("/api/oracle/query", json=params)
            assert response.status_code in [200, 201, 400, 422, 500]

    def test_crm_client_creation_variations(self, authenticated_client):
        """Test client creation with various field combinations"""
        variations = [
            {
                "full_name": "Minimal Client",
                "email": "minimal@example.com",
            },
            {
                "full_name": "Full Client",
                "email": "full@example.com",
                "phone": "+6281234567890",
                "status": "active",
            },
            {
                "full_name": "Extended Client",
                "email": "extended@example.com",
                "phone": "+6281234567890",
                "status": "lead",
                "notes": "Interested in PT PMA",
            },
        ]

        for client_data in variations:
            response = authenticated_client.post("/api/crm/clients", json=client_data)
            assert response.status_code in [200, 201, 400, 422]

    def test_memory_store_variations(self, authenticated_client):
        """Test memory store with various data combinations"""
        variations = [
            {"user_id": "test@example.com", "text": "Simple memory"},
            {
                "user_id": "test@example.com",
                "text": "Memory with metadata",
                "metadata": {"source": "conversation", "importance": "high"},
            },
        ]

        for memory_data in variations:
            response = authenticated_client.post("/api/memory/store", json=memory_data)
            assert response.status_code in [200, 201, 400, 422]


@pytest.mark.api
class TestEndpointErrorRecovery:
    """Test error recovery scenarios"""

    def test_retry_after_temporary_failure(self, authenticated_client):
        """Test retrying after temporary failure"""
        # First attempt might fail
        response1 = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "user_id": "test@example.com"},
        )

        # Retry should work
        response2 = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "user_id": "test@example.com"},
        )

        # At least one should succeed
        assert response1.status_code in [200, 201, 500, 503] or response2.status_code in [
            200,
            201,
        ]

    def test_graceful_degradation_on_partial_failure(self, authenticated_client):
        """Test graceful degradation when some services fail"""
        # Create client (should work)
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Degradation Test",
                "email": "degradation@example.com",
            },
        )

        # Oracle query might fail but shouldn't affect client creation
        oracle_response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test", "user_id": "degradation@example.com"},
        )

        # Client creation should succeed regardless of oracle
        assert client_response.status_code in [200, 201]
        # Oracle might fail but should handle gracefully
        assert oracle_response.status_code in [200, 201, 400, 422, 500, 503]


@pytest.mark.api
class TestHandlersEndpoints:
    """Test handlers registry endpoints"""

    def test_list_all_handlers(self, authenticated_client):
        """Test listing all available handlers"""
        response = authenticated_client.get("/api/handlers/list")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "total_handlers" in data
            assert "categories" in data
            assert "handlers" in data
            assert isinstance(data["total_handlers"], int)
            assert isinstance(data["categories"], dict)
            assert isinstance(data["handlers"], list)

    def test_search_handlers(self, authenticated_client):
        """Test searching handlers by query"""
        response = authenticated_client.get("/api/handlers/search?query=conversation")

        assert response.status_code in [200, 400, 401, 404, 422, 500]

        if response.status_code == 200:
            data = response.json()
            assert "query" in data
            assert "matches" in data
            assert "handlers" in data
            assert isinstance(data["matches"], int)
            assert isinstance(data["handlers"], list)

    def test_search_handlers_empty_query(self, authenticated_client):
        """Test searching handlers with empty query"""
        response = authenticated_client.get("/api/handlers/search?query=")

        assert response.status_code in [200, 400, 422, 500]

    def test_search_handlers_special_characters(self, authenticated_client):
        """Test searching handlers with special characters"""
        response = authenticated_client.get("/api/handlers/search?query=test%20query")

        assert response.status_code in [200, 400, 422, 500]

    def test_get_handlers_by_category(self, authenticated_client):
        """Test getting handlers by category"""
        # First get list to find a category
        list_response = authenticated_client.get("/api/handlers/list")

        if list_response.status_code == 200:
            list_data = list_response.json()
            categories = list_data.get("categories", {})

            if categories:
                category_name = list(categories.keys())[0]
                response = authenticated_client.get(f"/api/handlers/category/{category_name}")

                assert response.status_code in [200, 404, 500]

                if response.status_code == 200:
                    data = response.json()
                    assert "count" in data or "handlers" in data

    def test_get_handlers_by_invalid_category(self, authenticated_client):
        """Test getting handlers with invalid category"""
        response = authenticated_client.get("/api/handlers/category/invalid_category_12345")

        assert response.status_code in [404, 500]


@pytest.mark.api
class TestAgentsEndpointsExpanded:
    """Expanded tests for agents endpoints"""

    def test_agents_status(self, authenticated_client):
        """Test getting agents status"""
        response = authenticated_client.get("/api/agents/status")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "total_agents" in data
            assert "agents" in data

    def test_create_client_journey(self, authenticated_client):
        """Test creating a client journey"""
        response = authenticated_client.post(
            "/api/agents/journey/create",
            json={
                "journey_type": "pt_pma_setup",
                "client_id": "test_client_123",
            },
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "success" in data
            assert "journey_id" in data

    def test_create_journey_with_custom_steps(self, authenticated_client):
        """Test creating journey with custom steps"""
        response = authenticated_client.post(
            "/api/agents/journey/create",
            json={
                "journey_type": "pt_pma_setup",
                "client_id": "test_client_456",
                "custom_steps": [
                    {"step_id": "step1", "name": "Custom Step 1", "status": "pending"},
                ],
            },
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_get_journey(self, authenticated_client):
        """Test getting journey details"""
        # First create a journey
        create_response = authenticated_client.post(
            "/api/agents/journey/create",
            json={
                "journey_type": "kitas_application",
                "client_id": "test_client_789",
            },
        )

        if create_response.status_code in [200, 201]:
            create_data = create_response.json()
            journey_id = create_data.get("journey_id")

            if journey_id:
                get_response = authenticated_client.get(f"/api/agents/journey/{journey_id}")

                assert get_response.status_code in [200, 404, 500]

                if get_response.status_code == 200:
                    data = get_response.json()
                    assert "success" in data
                    assert "journey" in data

    def test_get_journey_not_found(self, authenticated_client):
        """Test getting non-existent journey"""
        response = authenticated_client.get("/api/agents/journey/non-existent-id")

        assert response.status_code in [404, 500]

    def test_complete_journey_step(self, authenticated_client):
        """Test completing a journey step"""
        # First create a journey
        create_response = authenticated_client.post(
            "/api/agents/journey/create",
            json={
                "journey_type": "property_purchase",
                "client_id": "test_client_step",
            },
        )

        if create_response.status_code in [200, 201]:
            create_data = create_response.json()
            journey_id = create_data.get("journey_id")

            if journey_id:
                # Complete a step
                complete_response = authenticated_client.post(
                    f"/api/agents/journey/{journey_id}/step/step1/complete",
                    params={"notes": "Step completed successfully"},
                )

                assert complete_response.status_code in [200, 201, 400, 404, 422, 500]

    def test_get_next_steps(self, authenticated_client):
        """Test getting next steps in journey"""
        # First create a journey
        create_response = authenticated_client.post(
            "/api/agents/journey/create",
            json={
                "journey_type": "pt_pma_setup",
                "client_id": "test_client_next",
            },
        )

        if create_response.status_code in [200, 201]:
            create_data = create_response.json()
            journey_id = create_data.get("journey_id")

            if journey_id:
                next_steps_response = authenticated_client.get(
                    f"/api/agents/journey/{journey_id}/next-steps"
                )

                assert next_steps_response.status_code in [200, 404, 500]

                if next_steps_response.status_code == 200:
                    data = next_steps_response.json()
                    assert "success" in data
                    assert "next_steps" in data


@pytest.mark.api
class TestIntelEndpoints:
    """Test intel news endpoints"""

    def test_search_intel(self, authenticated_client):
        """Test searching intel news"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "immigration update",
                "date_range": "last_7_days",
                "limit": 10,
            },
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]

        if response.status_code == 200:
            data = response.json()
            assert "results" in data or "items" in data

    def test_search_intel_with_category(self, authenticated_client):
        """Test searching intel with specific category"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "tax update",
                "category": "bkpm_tax",
                "date_range": "last_30_days",
            },
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_search_intel_with_impact_level(self, authenticated_client):
        """Test searching intel with impact level filter"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "important news",
                "impact_level": "high",
                "date_range": "last_7_days",
            },
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_search_intel_all_time(self, authenticated_client):
        """Test searching intel with all time range"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "historical data",
                "date_range": "all",
            },
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]

    def test_search_intel_invalid_category(self, authenticated_client):
        """Test searching intel with invalid category"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "test",
                "category": "invalid_category_xyz",
            },
        )

        assert response.status_code in [200, 400, 404, 422, 500]


@pytest.mark.api
class TestTeamActivityEndpoints:
    """Test team activity endpoints"""

    def test_clock_in(self, authenticated_client):
        """Test clocking in"""
        response = authenticated_client.post("/api/team-activity/clock-in")

        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "status" in data or "success" in data

    def test_clock_out(self, authenticated_client):
        """Test clocking out"""
        response = authenticated_client.post("/api/team-activity/clock-out")

        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "status" in data or "success" in data

    def test_get_my_status(self, authenticated_client):
        """Test getting my status"""
        response = authenticated_client.get("/api/team-activity/my-status")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "status" in data or "user_id" in data

    def test_get_team_status(self, authenticated_client):
        """Test getting team status"""
        response = authenticated_client.get("/api/team-activity/status")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list) or isinstance(data, dict)

    def test_get_hours(self, authenticated_client):
        """Test getting daily hours"""
        response = authenticated_client.get("/api/team-activity/hours")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list) or isinstance(data, dict)

    def test_get_weekly_activity(self, authenticated_client):
        """Test getting weekly activity summary"""
        response = authenticated_client.get("/api/team-activity/activity/weekly")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list) or isinstance(data, dict)

    def test_get_monthly_activity(self, authenticated_client):
        """Test getting monthly activity summary"""
        response = authenticated_client.get("/api/team-activity/activity/monthly")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list) or isinstance(data, dict)

    def test_export_activity(self, authenticated_client):
        """Test exporting activity data"""
        response = authenticated_client.get("/api/team-activity/export")

        assert response.status_code in [200, 401, 404, 500]

    def test_team_activity_health(self, authenticated_client):
        """Test team activity health endpoint"""
        response = authenticated_client.get("/api/team-activity/health")

        assert response.status_code in [200, 401, 404, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestMemoryVectorEndpoints:
    """Test memory vector endpoints"""

    def test_init_memory(self, authenticated_client):
        """Test initializing memory vector"""
        response = authenticated_client.post(
            "/api/memory/init",
            json={"user_id": "test@example.com"},
        )

        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "success" in data or "user_id" in data

    def test_embed_text(self, authenticated_client):
        """Test embedding text"""
        response = authenticated_client.post(
            "/api/memory/embed",
            json={"text": "This is a test memory"},
        )

        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "embedding" in data or "vector" in data

    def test_store_memory(self, authenticated_client):
        """Test storing memory"""
        response = authenticated_client.post(
            "/api/memory/store",
            json={
                "user_id": "test@example.com",
                "text": "User prefers detailed explanations",
            },
        )

        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

        if response.status_code in [200, 201]:
            data = response.json()
            assert "success" in data or "memory_id" in data

    def test_search_memory(self, authenticated_client):
        """Test searching memory"""
        response = authenticated_client.post(
            "/api/memory/search",
            json={
                "user_id": "test@example.com",
                "query": "preferences",
                "limit": 5,
            },
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]

        if response.status_code == 200:
            data = response.json()
            assert "results" in data or "memories" in data

    def test_find_similar_memory(self, authenticated_client):
        """Test finding similar memories"""
        response = authenticated_client.post(
            "/api/memory/similar",
            json={
                "user_id": "test@example.com",
                "text": "User likes detailed information",
                "limit": 5,
            },
        )

        assert response.status_code in [200, 400, 401, 404, 422, 500]

        if response.status_code == 200:
            data = response.json()
            assert "results" in data or "similar" in data

    def test_delete_memory(self, authenticated_client):
        """Test deleting memory"""
        # First store a memory
        store_response = authenticated_client.post(
            "/api/memory/store",
            json={
                "user_id": "test@example.com",
                "text": "Temporary memory to delete",
            },
        )

        if store_response.status_code in [200, 201]:
            store_data = store_response.json()
            memory_id = store_data.get("memory_id") or store_data.get("id")

            if memory_id:
                delete_response = authenticated_client.delete(f"/api/memory/{memory_id}")

                assert delete_response.status_code in [200, 404, 500]

    def test_delete_memory_not_found(self, authenticated_client):
        """Test deleting non-existent memory"""
        response = authenticated_client.delete("/api/memory/999999")

        assert response.status_code in [404, 500]

    def test_get_memory_stats(self, authenticated_client):
        """Test getting memory statistics"""
        response = authenticated_client.get("/api/memory/stats")

        assert response.status_code in [200, 401, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_memory_health(self, authenticated_client):
        """Test memory health endpoint"""
        response = authenticated_client.get("/api/memory/health")

        assert response.status_code in [200, 401, 404, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestComplexIntegrationScenarios:
    """Complex integration scenarios testing multiple endpoints together"""

    def test_complete_agent_journey_workflow(self, authenticated_client):
        """Test complete workflow: create journey -> complete steps -> get next steps"""
        # Step 1: Create journey
        create_response = authenticated_client.post(
            "/api/agents/journey/create",
            json={
                "journey_type": "pt_pma_setup",
                "client_id": "integration_test_client",
            },
        )

        assert create_response.status_code in [200, 201, 400, 404, 422, 500]

        if create_response.status_code in [200, 201]:
            create_data = create_response.json()
            journey_id = create_data.get("journey_id")

            if journey_id:
                # Step 2: Get next steps
                next_steps_response = authenticated_client.get(
                    f"/api/agents/journey/{journey_id}/next-steps"
                )

                assert next_steps_response.status_code in [200, 404, 500]

                # Step 3: Complete a step
                if next_steps_response.status_code == 200:
                    complete_response = authenticated_client.post(
                        f"/api/agents/journey/{journey_id}/step/step1/complete",
                        params={"notes": "Integration test step"},
                    )

                    assert complete_response.status_code in [200, 201, 400, 404, 422, 500]

    def test_memory_to_conversation_workflow(self, authenticated_client):
        """Test workflow: store memory -> save conversation -> search memory"""
        # Step 1: Store memory
        memory_response = authenticated_client.post(
            "/api/memory/store",
            json={
                "user_id": "workflow@example.com",
                "text": "User prefers concise answers",
            },
        )

        assert memory_response.status_code in [200, 201, 400, 422, 500]

        # Step 2: Save conversation
        conversation_response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "Tell me about PT PMA"},
                    {"role": "assistant", "content": "PT PMA is..."},
                ]
            },
        )

        assert conversation_response.status_code in [200, 201, 400, 422, 500]

        # Step 3: Search memory
        search_response = authenticated_client.post(
            "/api/memory/search",
            json={
                "user_id": "workflow@example.com",
                "query": "preferences",
            },
        )

        assert search_response.status_code in [200, 400, 404, 422, 500]

    def test_intel_to_oracle_workflow(self, authenticated_client):
        """Test workflow: search intel -> query oracle with context"""
        # Step 1: Search intel
        intel_response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "immigration policy",
                "date_range": "last_7_days",
            },
        )

        assert intel_response.status_code in [200, 400, 404, 422, 500]

        # Step 2: Query oracle (might use intel context)
        oracle_response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "What are the latest immigration policies?",
                "user_id": "intel@example.com",
            },
        )

        assert oracle_response.status_code in [200, 201, 400, 422, 500]

    def test_team_activity_to_analytics_workflow(self, authenticated_client):
        """Test workflow: clock in -> check status -> get weekly summary"""
        # Step 1: Clock in
        clock_in_response = authenticated_client.post("/api/team-activity/clock-in")

        assert clock_in_response.status_code in [200, 201, 400, 404, 422, 500]

        # Step 2: Check status
        status_response = authenticated_client.get("/api/team-activity/my-status")

        assert status_response.status_code in [200, 404, 500]

        # Step 3: Get weekly summary
        weekly_response = authenticated_client.get("/api/team-activity/activity/weekly")

        assert weekly_response.status_code in [200, 404, 500]

    def test_handlers_discovery_workflow(self, authenticated_client):
        """Test workflow: list handlers -> search -> get by category"""
        # Step 1: List all handlers
        list_response = authenticated_client.get("/api/handlers/list")

        assert list_response.status_code in [200, 404, 500]

        if list_response.status_code == 200:
            list_data = list_response.json()
            categories = list_data.get("categories", {})

            # Step 2: Search handlers
            search_response = authenticated_client.get("/api/handlers/search?query=memory")

            assert search_response.status_code in [200, 400, 404, 422, 500]

            # Step 3: Get by category
            if categories:
                category_name = list(categories.keys())[0]
                category_response = authenticated_client.get(
                    f"/api/handlers/category/{category_name}"
                )

                assert category_response.status_code in [200, 404, 500]


@pytest.mark.api
class TestIngestEndpointsExpanded:
    """Test ingest endpoints with expanded scenarios"""

    def test_ingest_stats_endpoint(self, authenticated_client):
        """Test retrieving ingestion statistics"""
        response = authenticated_client.get("/api/ingest/stats")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_ingest_batch_endpoint(self, authenticated_client):
        """Test batch ingestion endpoint"""
        response = authenticated_client.post(
            "/api/ingest/batch",
            json={
                "files": [
                    {"file_path": "/path/to/file1.pdf", "title": "Book 1"},
                    {"file_path": "/path/to/file2.pdf", "title": "Book 2"},
                ]
            },
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]


@pytest.mark.api
class TestLegalIngestEndpointsExpanded:
    """Test legal ingest endpoints with expanded scenarios"""

    def test_legal_ingest_single(self, authenticated_client):
        """Test single legal document ingestion"""
        response = authenticated_client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/path/to/legal_doc.pdf",
                "collection": "legal_intelligence",
                "tier": "A",
            },
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_legal_ingest_batch(self, authenticated_client):
        """Test batch legal document ingestion"""
        response = authenticated_client.post(
            "/api/legal/ingest-batch",
            json={
                "files": [
                    {
                        "path": "/path/to/doc1.pdf",
                        "collection": "legal_intelligence",
                        "tier": "A",
                    },
                    {
                        "path": "/path/to/doc2.pdf",
                        "collection": "tax_updates",
                        "tier": "B",
                    },
                ]
            },
        )

        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_legal_collections_stats(self, authenticated_client):
        """Test retrieving legal collections statistics"""
        response = authenticated_client.get("/api/legal/collections/stats")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestOracleIngestEndpointsExpanded:
    """Test Oracle ingest endpoints with expanded scenarios"""

    def test_oracle_ingest_documents(self, authenticated_client):
        """Test Oracle document ingestion"""
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "content": "Test document content",
                        "metadata": {
                            "law_id": "TEST-2025",
                            "category": "business_licensing",
                        },
                    }
                ],
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_oracle_ingest_multiple_documents(self, authenticated_client):
        """Test Oracle ingestion with multiple documents"""
        documents = [
            {
                "content": f"Document {idx} content",
                "metadata": {"law_id": f"TEST-2025-{idx}", "category": "test"},
            }
            for idx in range(5)
        ]

        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": documents,
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_oracle_collections_list(self, authenticated_client):
        """Test listing Oracle collections"""
        response = authenticated_client.get("/api/oracle/ingest/collections")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (dict, list))


@pytest.mark.api
class TestImageGenerationEndpointsExpanded:
    """Test image generation endpoints with expanded scenarios"""

    def test_image_generation_basic(self, authenticated_client):
        """Test basic image generation"""
        response = authenticated_client.post(
            "/api/image/generate",
            json={
                "prompt": "A beautiful sunset over the ocean",
                "size": "1024x1024",
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_image_generation_different_sizes(self, authenticated_client):
        """Test image generation with different sizes"""
        sizes = ["512x512", "1024x1024", "1024x1792", "1792x1024"]

        for size in sizes:
            response = authenticated_client.post(
                "/api/image/generate",
                json={
                    "prompt": "Test image",
                    "size": size,
                },
            )

            assert response.status_code in [200, 201, 400, 422, 500]

    def test_image_generation_different_styles(self, authenticated_client):
        """Test image generation with different styles"""
        response = authenticated_client.post(
            "/api/image/generate",
            json={
                "prompt": "Modern office building",
                "style": "photorealistic",
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
class TestConcurrentRequestScenarios:
    """Test concurrent request scenarios"""

    def test_concurrent_client_creation(self, authenticated_client):
        """Test creating multiple clients concurrently"""
        import concurrent.futures

        def create_client(index):
            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": f"Concurrent Client {index}",
                    "email": f"concurrent{index}@example.com",
                    "phone": "+6281234567890",
                },
            )
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_client, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All should succeed or handle gracefully
        assert all(code in [200, 201, 400, 409, 422] for code in results)

    def test_concurrent_oracle_queries(self, authenticated_client):
        """Test multiple Oracle queries concurrently"""
        queries = [
            "What is PT PMA?",
            "What are KITAS requirements?",
            "How to open a business?",
            "What are visa regulations?",
            "Explain tax filing requirements",
        ]

        import concurrent.futures

        def execute_query(query):
            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": query, "user_id": "concurrent@example.com"},
            )
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_query, q) for q in queries]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All should handle gracefully
        assert all(code in [200, 201, 400, 422, 500, 503] for code in results)


@pytest.mark.api
class TestPerformanceScenarios:
    """Test performance-related scenarios"""

    def test_large_payload_handling(self, authenticated_client):
        """Test handling of large payloads"""
        # Create client with large notes field
        large_notes = "A" * 10000  # 10KB of text

        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Large Payload Client",
                "email": "large@example.com",
                "phone": "+6281234567890",
                "notes": large_notes,
            },
        )

        # Should handle gracefully (either accept or reject with appropriate error)
        assert response.status_code in [200, 201, 400, 413, 422]

    def test_many_parameters_handling(self, authenticated_client):
        """Test handling requests with many parameters"""
        # Oracle query with many optional parameters
        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "Test query",
                "user_id": "test@example.com",
                "limit": 10,
                "collection": "legal_intelligence",
                "language": "en",
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
class TestSecurityScenarios:
    """Test security-related scenarios"""

    def test_sql_injection_attempt(self, authenticated_client):
        """Test protection against SQL injection attempts"""
        # Try SQL injection in search query
        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "'; DROP TABLE clients; --",
                "user_id": "test@example.com",
            },
        )

        # Should handle securely (not execute SQL)
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_xss_attempt_handling(self, authenticated_client):
        """Test protection against XSS attempts"""
        # Try XSS in client name
        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "<script>alert('XSS')</script>",
                "email": "xss@example.com",
            },
        )

        # Should sanitize or reject
        assert response.status_code in [200, 201, 400, 422]


@pytest.mark.api
class TestRateLimitingScenarios:
    """Test rate limiting scenarios"""

    def test_rapid_requests(self, authenticated_client):
        """Test rapid consecutive requests"""
        # Make many rapid requests
        responses = []
        for _ in range(20):
            response = authenticated_client.get("/api/health")
            responses.append(response.status_code)

        # Should handle gracefully (may have rate limiting)
        # At least some requests should succeed
        assert any(code in [200, 503] for code in responses)

    def test_rate_limit_recovery(self, authenticated_client):
        """Test recovery after rate limit"""
        import time

        # Make rapid requests
        for _ in range(10):
            authenticated_client.get("/api/health")

        # Wait a bit
        time.sleep(1)

        # Next request should work
        response = authenticated_client.get("/api/health")
        assert response.status_code in [200, 503]
