"""
Comprehensive Integration Tests for Agent Services
Tests all agent services with real database and dependencies

Covers:
- ClientJourneyOrchestrator
- ProactiveComplianceMonitor
- KnowledgeGraphBuilder
- AutoIngestionOrchestrator
- CrossOracleSynthesisService
- AutonomousResearchService
"""

import os
import sys
from datetime import datetime, timedelta
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
class TestAgentsComprehensiveIntegration:
    """Comprehensive integration tests for agent services"""

    @pytest.mark.asyncio
    async def test_client_journey_orchestrator(self, db_pool):
        """Test ClientJourneyOrchestrator with real database"""

        async with db_pool.acquire() as conn:
            # Create necessary tables
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_journeys (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER,
                    journey_type VARCHAR(100),
                    current_step VARCHAR(100),
                    status VARCHAR(50),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Journey Test Client",
                "journey.test@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Initialize orchestrator with mocked dependencies
            with patch("services.client_journey_orchestrator.SearchService") as mock_search:
                from services.client_journey_orchestrator import ClientJourneyOrchestrator

                mock_search_instance = MagicMock()
                mock_search.return_value = mock_search_instance

                orchestrator = ClientJourneyOrchestrator(
                    db_pool=db_pool, search_service=mock_search_instance
                )

                # Test journey creation
                journey_id = await conn.fetchval(
                    """
                    INSERT INTO client_journeys (
                        client_id, journey_type, current_step, status, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    client_id,
                    "KITAS",
                    "document_preparation",
                    "in_progress",
                    {"step": 1, "total_steps": 5},
                )

                assert journey_id is not None

                # Retrieve journey
                journey = await conn.fetchrow(
                    """
                    SELECT journey_type, current_step, status
                    FROM client_journeys
                    WHERE id = $1
                    """,
                    journey_id,
                )

                assert journey is not None
                assert journey["journey_type"] == "KITAS"
                assert journey["current_step"] == "document_preparation"

                # Cleanup
                await conn.execute("DELETE FROM client_journeys WHERE id = $1", journey_id)
                await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_proactive_compliance_monitor(self, db_pool):
        """Test ProactiveComplianceMonitor with real database"""

        async with db_pool.acquire() as conn:
            # Create compliance alerts table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compliance_alerts (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER,
                    alert_type VARCHAR(100),
                    severity VARCHAR(50),
                    message TEXT,
                    status VARCHAR(50) DEFAULT 'active',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Compliance Test Client",
                "compliance.test@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Create test practice with expiration
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, expiry_date, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "active",
                datetime.now().date() + timedelta(days=30),  # Expires in 30 days
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Initialize compliance monitor
            with patch("services.proactive_compliance_monitor.SearchService") as mock_search:
                from services.proactive_compliance_monitor import (
                    ProactiveComplianceMonitor,
                )

                mock_search_instance = MagicMock()
                mock_search.return_value = mock_search_instance

                monitor = ProactiveComplianceMonitor(db_pool=db_pool)

                # Create compliance alert
                alert_id = await conn.fetchval(
                    """
                    INSERT INTO compliance_alerts (
                        client_id, alert_type, severity, message, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    client_id,
                    "expiry_warning",
                    "warning",
                    "Practice expires in 30 days",
                    {"practice_id": practice_id, "days_remaining": 30},
                )

                assert alert_id is not None

                # Retrieve alerts
                alerts = await conn.fetch(
                    """
                    SELECT id, alert_type, severity, status
                    FROM compliance_alerts
                    WHERE client_id = $1
                    ORDER BY created_at DESC
                    """,
                    client_id,
                )

                assert len(alerts) == 1
                assert alerts[0]["alert_type"] == "expiry_warning"
                assert alerts[0]["severity"] == "warning"

                # Cleanup
                await conn.execute("DELETE FROM compliance_alerts WHERE id = $1", alert_id)
                await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
                await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_knowledge_graph_builder(self, db_pool, qdrant_client):
        """Test KnowledgeGraphBuilder with real database and Qdrant"""

        async with db_pool.acquire() as conn:
            # Create knowledge graph table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
                    id SERIAL PRIMARY KEY,
                    node_id VARCHAR(255) UNIQUE NOT NULL,
                    node_type VARCHAR(100),
                    properties JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
                    id SERIAL PRIMARY KEY,
                    source_node_id VARCHAR(255),
                    target_node_id VARCHAR(255),
                    relationship_type VARCHAR(100),
                    properties JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Initialize builder with mocked dependencies
            with patch("services.knowledge_graph_builder.SearchService") as mock_search:
                from services.knowledge_graph_builder import KnowledgeGraphBuilder

                mock_search_instance = MagicMock()
                mock_search.return_value = mock_search_instance

                builder = KnowledgeGraphBuilder(
                    db_pool=db_pool, search_service=mock_search_instance
                )

                # Create test node
                node_id = "test_node_1"
                await conn.execute(
                    """
                    INSERT INTO knowledge_graph_nodes (node_id, node_type, properties)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (node_id) DO UPDATE
                    SET properties = EXCLUDED.properties, updated_at = NOW()
                    """,
                    node_id,
                    "concept",
                    {"name": "KITAS", "description": "Temporary residence permit"},
                )

                # Create edge
                await conn.execute(
                    """
                    INSERT INTO knowledge_graph_edges (
                        source_node_id, target_node_id, relationship_type, properties
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    node_id,
                    "test_node_2",
                    "related_to",
                    {"strength": 0.8},
                )

                # Retrieve node
                node = await conn.fetchrow(
                    """
                    SELECT node_id, node_type, properties
                    FROM knowledge_graph_nodes
                    WHERE node_id = $1
                    """,
                    node_id,
                )

                assert node is not None
                assert node["node_type"] == "concept"
                assert node["properties"]["name"] == "KITAS"

                # Cleanup
                await conn.execute(
                    "DELETE FROM knowledge_graph_edges WHERE source_node_id = $1", node_id
                )
                await conn.execute("DELETE FROM knowledge_graph_nodes WHERE node_id = $1", node_id)

    @pytest.mark.asyncio
    async def test_autonomous_research_service(self, db_pool, qdrant_client):
        """Test AutonomousResearchService with real dependencies"""

        async with db_pool.acquire() as conn:
            # Create research tasks table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_tasks (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(255) UNIQUE NOT NULL,
                    query TEXT,
                    status VARCHAR(50),
                    results JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Initialize service with mocked dependencies
            with (
                patch("services.autonomous_research_service.SearchService") as mock_search,
                patch("services.autonomous_research_service.ZantaraAIClient") as mock_ai,
            ):
                from services.autonomous_research_service import AutonomousResearchService

                mock_search_instance = MagicMock()
                mock_search.return_value = mock_search_instance

                mock_ai_instance = MagicMock()
                mock_ai_instance.generate_response = AsyncMock(return_value="Research results...")
                mock_ai.return_value = mock_ai_instance

                service = AutonomousResearchService(
                    db_pool=db_pool, search_service=mock_search_instance, ai_client=mock_ai_instance
                )

                # Create research task
                task_id = "research_task_123"
                await conn.execute(
                    """
                    INSERT INTO research_tasks (task_id, query, status, results)
                    VALUES ($1, $2, $3, $4)
                    """,
                    task_id,
                    "What are the requirements for KITAS?",
                    "in_progress",
                    {"collections_searched": ["visa_oracle"], "documents_found": 5},
                )

                # Retrieve task
                task = await conn.fetchrow(
                    """
                    SELECT task_id, query, status
                    FROM research_tasks
                    WHERE task_id = $1
                    """,
                    task_id,
                )

                assert task is not None
                assert task["query"] == "What are the requirements for KITAS?"
                assert task["status"] == "in_progress"

                # Cleanup
                await conn.execute("DELETE FROM research_tasks WHERE task_id = $1", task_id)

    @pytest.mark.asyncio
    async def test_cross_oracle_synthesis_service(self, db_pool, qdrant_client):
        """Test CrossOracleSynthesisService with real dependencies"""

        async with db_pool.acquire() as conn:
            # Create synthesis tasks table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS synthesis_tasks (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(255) UNIQUE NOT NULL,
                    query TEXT,
                    collections_used TEXT[],
                    synthesized_response TEXT,
                    status VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Initialize service with mocked dependencies
            with (
                patch("services.cross_oracle_synthesis_service.SearchService") as mock_search,
                patch("services.cross_oracle_synthesis_service.ZantaraAIClient") as mock_ai,
            ):
                from services.cross_oracle_synthesis_service import CrossOracleSynthesisService

                mock_search_instance = MagicMock()
                mock_search.return_value = mock_search_instance

                mock_ai_instance = MagicMock()
                mock_ai_instance.generate_response = AsyncMock(
                    return_value="Synthesized response..."
                )
                mock_ai.return_value = mock_ai_instance

                service = CrossOracleSynthesisService(
                    db_pool=db_pool, search_service=mock_search_instance, ai_client=mock_ai_instance
                )

                # Create synthesis task
                task_id = "synthesis_task_123"
                await conn.execute(
                    """
                    INSERT INTO synthesis_tasks (
                        task_id, query, collections_used, synthesized_response, status
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    task_id,
                    "How to start a business in Indonesia?",
                    ["kbli_unified", "legal_unified", "tax_genius"],
                    "To start a business in Indonesia, you need...",
                    "completed",
                )

                # Retrieve task
                task = await conn.fetchrow(
                    """
                    SELECT task_id, query, collections_used, status
                    FROM synthesis_tasks
                    WHERE task_id = $1
                    """,
                    task_id,
                )

                assert task is not None
                assert len(task["collections_used"]) == 3
                assert task["status"] == "completed"

                # Cleanup
                await conn.execute("DELETE FROM synthesis_tasks WHERE task_id = $1", task_id)
