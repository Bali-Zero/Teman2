"""
API/E2E Test Configuration

Sets up FastAPI TestClient for testing full request/response cycles.
These tests verify endpoints, middleware, and error handling.
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Set required environment variables BEFORE any imports
# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_whatsapp_verify_token"
os.environ["INSTAGRAM_VERIFY_TOKEN"] = "test_instagram_verify_token"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def create_mock_db_pool():
    """Create a properly configured mock database pool."""
    from unittest.mock import AsyncMock, MagicMock

    mock_conn = AsyncMock()
    mock_pool = MagicMock()

    mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value="DELETE 0")
    mock_conn.fetchval = AsyncMock(return_value=1)

    # Mock pool.acquire() as async context manager
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock pool methods for health check
    mock_pool.get_min_size = MagicMock(return_value=2)
    mock_pool.get_max_size = MagicMock(return_value=10)
    mock_pool.get_size = MagicMock(return_value=5)
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn


@pytest.fixture(scope="session")
def test_app():
    """
    Create FastAPI app with mocked state - shared across session.
    """
    import types
    from unittest.mock import MagicMock, patch

    # Mock modules that might not exist or cause import errors
    # Create services package structure properly - alias to backend.services
    if "services" not in sys.modules:
        # Import backend.services first to ensure it exists
        import backend.services

        # Make services an alias to backend.services
        sys.modules["services"] = backend.services

    # Mock services submodules that might be imported
    # List of services that might be imported during app initialization
    # Only mock modules that don't exist or cause import errors
    # List of all services modules that might be imported
    # We mock them to prevent import errors during test initialization
    service_modules_to_mock = [
        "personality_service",  # May not exist
        "query_router",
        "rag",
        "rag.agentic",
        "rag.vision_rag",
        "ingestion_service",
        "auto_ingestion_orchestrator",
        "client_journey_orchestrator",
        "alert_service",
        "auto_crm_service",
        "autonomous_research_service",
        "collaborator_service",
        "collective_memory_workflow",
        "cross_oracle_synthesis_service",
        "cultural_rag_service",
        "health_monitor",
        "intelligent_router",
        "memory_service_postgres",
        "proactive_compliance_monitor",
        "search_service",
        "tool_executor",
        "zantara_tools",
        "autonomous_scheduler",
        "knowledge_graph_builder",
        "legal_ingestion_service",
        "image_generation_service",
        "notification_hub",
        "smart_oracle",
        "oracle_config",
        "oracle_database",
        "oracle_google_services",
        "communication_utils",
        "memory_fallback",
    ]

    # Helper function to create mock service module
    def create_service_mock(service_name: str):
        """Create a mock service module with common attributes"""
        service_mock = types.ModuleType(service_name.split(".")[-1])

        # Add common classes/functions based on service name
        # These match the imports in main_cloud.py
        if service_name == "query_router":
            service_mock.QueryRouter = MagicMock
        elif service_name == "rag.agentic":
            service_mock.AgenticRAGOrchestrator = MagicMock
            service_mock.create_agentic_rag = MagicMock
        elif service_name == "rag.vision_rag":
            service_mock.VisionRAGService = MagicMock
        elif service_name == "autonomous_scheduler":
            service_mock.create_and_start_scheduler = MagicMock(return_value=MagicMock())
            service_mock.AutonomousScheduler = MagicMock
        elif service_name == "ingestion_service":
            service_mock.IngestionService = MagicMock
        elif service_name == "auto_ingestion_orchestrator":
            service_mock.AutoIngestionOrchestrator = MagicMock
        elif service_name == "client_journey_orchestrator":
            service_mock.ClientJourneyOrchestrator = MagicMock
        elif service_name == "alert_service":
            service_mock.AlertService = MagicMock
        elif service_name == "auto_crm_service":
            service_mock.get_auto_crm_service = MagicMock
        elif service_name == "autonomous_research_service":
            service_mock.AutonomousResearchService = MagicMock
        elif service_name == "collaborator_service":
            service_mock.CollaboratorService = MagicMock
        elif service_name == "collective_memory_workflow":
            service_mock.create_collective_memory_workflow = MagicMock
        elif service_name == "cross_oracle_synthesis_service":
            service_mock.CrossOracleSynthesisService = MagicMock
        elif service_name == "cultural_rag_service":
            service_mock.CulturalRAGService = MagicMock
        elif service_name == "health_monitor":
            service_mock.HealthMonitor = MagicMock
        elif service_name == "intelligent_router":
            service_mock.IntelligentRouter = MagicMock
        elif service_name == "memory_service_postgres":
            service_mock.MemoryServicePostgres = MagicMock
        elif service_name == "personality_service":
            service_mock.PersonalityService = MagicMock
        elif service_name == "proactive_compliance_monitor":
            service_mock.ProactiveComplianceMonitor = MagicMock
            service_mock.AlertSeverity = MagicMock  # Enum or class
        elif service_name == "search_service":
            service_mock.SearchService = MagicMock
        elif service_name == "autonomous_scheduler":
            service_mock.create_and_start_scheduler = MagicMock(return_value=MagicMock())
            service_mock.AutonomousScheduler = MagicMock
        elif service_name == "tool_executor":
            service_mock.ToolExecutor = MagicMock
        elif service_name == "zantara_tools":
            service_mock.ZantaraTools = MagicMock
        elif service_name == "knowledge_graph_builder":
            service_mock.KnowledgeGraphBuilder = MagicMock
        elif service_name == "legal_ingestion_service":
            service_mock.LegalIngestionService = MagicMock
        elif service_name == "image_generation_service":
            service_mock.ImageGenerationService = MagicMock
        elif service_name == "smart_oracle":
            service_mock.smart_oracle = MagicMock  # Function
        elif service_name == "notification_hub":
            service_mock.NotificationHub = MagicMock
            service_mock.NOTIFICATION_TEMPLATES = {}  # Dict of templates
            service_mock.Notification = MagicMock  # Pydantic model or class
            service_mock.NotificationChannel = MagicMock  # Enum
            service_mock.NotificationPriority = MagicMock  # Enum
            service_mock.NotificationStatus = MagicMock  # Enum
            service_mock.create_notification_from_template = MagicMock  # Function
            service_mock.notification_hub = MagicMock()  # Instance variable (singleton)
        elif service_name == "communication_utils":
            service_mock.detect_language = MagicMock(return_value="it")
            service_mock.get_language_instruction = MagicMock(return_value="Rispondi in italiano")
        elif service_name == "memory_fallback":
            service_mock.InMemoryConversationCache = MagicMock
            service_mock.get_memory_cache = MagicMock(return_value=MagicMock())

        return service_mock

    for service_name in service_modules_to_mock:
        service_module_name = f"services.{service_name}"
        if service_module_name not in sys.modules:
            service_mock = create_service_mock(service_name)
            sys.modules[service_module_name] = service_mock

            # Set parent attribute if nested
            if "." in service_name:
                parent_name = service_name.split(".")[0]
                child_name = service_name.split(".")[1]
                if f"services.{parent_name}" not in sys.modules:
                    parent_mock = types.ModuleType(parent_name)
                    parent_mock.__path__ = []
                    sys.modules[f"services.{parent_name}"] = parent_mock
                    setattr(sys.modules["services"], parent_name, parent_mock)
                setattr(sys.modules[f"services.{parent_name}"], child_name, service_mock)
            else:
                setattr(sys.modules["services"], service_name, service_mock)

        # Special handling for oracle_config - it's imported as a variable
        if "services.oracle_config" in sys.modules:
            oracle_config_module = sys.modules["services.oracle_config"]
            if not hasattr(oracle_config_module, "oracle_config"):
                config_instance = MagicMock()
                config_instance.google_api_key = "test_key"
                config_instance.database_url = "postgresql://test:test@localhost/test"
                oracle_config_module.oracle_config = config_instance

        # Special handling for oracle_database
        if "services.oracle_database" not in sys.modules:
            oracle_db_mock = types.ModuleType("oracle_database")
            oracle_db_mock.OracleDatabase = MagicMock
            oracle_db_mock.db_manager = MagicMock()  # Instance variable
            sys.modules["services.oracle_database"] = oracle_db_mock
            sys.modules["services"].oracle_database = oracle_db_mock

        # Special handling for oracle_google_services
        if "services.oracle_google_services" not in sys.modules:
            oracle_google_mock = types.ModuleType("oracle_google_services")
            oracle_google_mock.google_services = MagicMock()  # Instance variable
            sys.modules["services.oracle_google_services"] = oracle_google_mock
            sys.modules["services"].oracle_google_services = oracle_google_mock

    # Mock GeminiAdapter before importing app to prevent initialization errors
    with patch("llm.adapters.gemini.GeminiAdapter") as mock_adapter_class:
        mock_adapter_instance = MagicMock()
        mock_adapter_class.return_value = mock_adapter_instance

        from app.main_cloud import app

    # Clear startup/shutdown handlers to prevent heavy initialization
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    # Add lightweight handlers
    @app.on_event("startup")
    async def startup():
        pass

    @app.on_event("shutdown")
    async def shutdown():
        pass

    # Create mock services
    mock_pool, _ = create_mock_db_pool()

    # Mock app.state services to prevent 503
    app.state.search_service = MagicMock()
    app.state.search_service.embedder = MagicMock()
    app.state.search_service.embedder.provider = "openai"
    app.state.search_service.embedder.model = "text-embedding-3-small"
    app.state.search_service.embedder.dimensions = 1536

    app.state.ai_client = MagicMock()
    app.state.memory_service = MagicMock()
    app.state.db_pool = mock_pool
    app.state.intelligent_router = MagicMock()
    app.state.health_monitor = MagicMock()
    app.state.health_monitor._running = True
    app.state.compliance_monitor = MagicMock()
    app.state.ws_listener = MagicMock()
    app.state.proactive_compliance_monitor = MagicMock()

    # Mock image generation service
    from unittest.mock import AsyncMock

    app.state.image_generation_service = MagicMock()
    app.state.image_generation_service.generate_image = AsyncMock(
        return_value={"images": [{"url": "https://example.com/image.png"}]}
    )

    app.state.services_initialized = True

    yield app

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def test_client(test_app):
    """
    Create FastAPI TestClient for API tests.

    This fixture creates a test client with mocked services to avoid
    requiring real database connections for API tests.

    Yields:
        TestClient: FastAPI test client
    """
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture(scope="function")
def authenticated_client(test_client):
    """
    Create authenticated test client with valid JWT token.

    Yields:
        TestClient: Test client with Authorization header set
    """
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    # Generate test JWT token
    payload = {
        "sub": "test@example.com",
        "email": "test@example.com",
        "role": "member",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }

    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    token = jwt.encode(payload, secret, algorithm="HS256")

    # Set default headers
    test_client.headers.update({"Authorization": f"Bearer {token}"})

    yield test_client

    # Clean up headers
    test_client.headers.pop("Authorization", None)


@pytest.fixture(scope="function")
def api_key_client(test_client):
    """
    Create test client with API key authentication.

    Yields:
        TestClient: Test client with X-API-Key header set
    """
    # Use first test API key from environment
    api_keys = os.getenv("API_KEYS", "test_api_key_1,test_api_key_2")
    api_key = api_keys.split(",")[0]

    test_client.headers.update({"X-API-Key": api_key})

    yield test_client

    # Clean up headers
    test_client.headers.pop("X-API-Key", None)


@pytest.fixture(scope="function")
def mock_search_service():
    """
    Create mock SearchService for API tests.

    Yields:
        MagicMock: Mocked SearchService
    """
    from unittest.mock import MagicMock

    mock_service = MagicMock()
    mock_service.search = MagicMock(
        return_value={"results": [], "collection_used": "test_collection", "query": "test query"}
    )

    return mock_service


@pytest.fixture(scope="function")
def mock_ai_client():
    """
    Create mock AI client for API tests.

    Yields:
        MagicMock: Mocked AI client
    """
    from unittest.mock import AsyncMock, MagicMock

    mock_client = MagicMock()
    mock_client.generate_response = AsyncMock(return_value="Test AI response")
    mock_client.stream = AsyncMock()

    return mock_client
