"""
Import-Time Tests

These tests verify that all critical modules can be imported without errors.
This prevents ImportError crashes during application startup (e.g., on Fly.io).

Run these tests before deploying to catch missing imports early:
    pytest tests/test_import_time.py -v
"""

import os
import sys
from pathlib import Path

import pytest

# Set minimal environment variables for import-time tests
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestImportTime:
    """Test that critical modules can be imported without errors"""

    def test_import_main_cloud(self):
        """Test that main_cloud module imports successfully"""
        try:
            import app.main_cloud  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import app.main_cloud: {e}")

    def test_import_app_factory(self):
        """Test that app_factory module imports successfully"""
        try:
            from app.setup.app_factory import create_app  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import app.setup.app_factory: {e}")

    def test_import_service_initializer(self):
        """Test that service_initializer module imports successfully"""
        try:
            from app.setup.service_initializer import initialize_services  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import app.setup.service_initializer: {e}")

    def test_import_agentic_rag(self):
        """Test that agentic RAG modules import successfully"""
        try:
            from services.rag.agentic import create_agentic_rag  # noqa: F401
            from services.rag.agentic.reasoning import detect_team_query  # noqa: F401
            from services.rag.agentic.session_fact_extractor import (
                SessionFactExtractor,  # noqa: F401
            )
        except ImportError as e:
            pytest.fail(f"Failed to import agentic RAG modules: {e}")

    def test_import_routers(self):
        """Test that critical routers import successfully"""
        try:
            from app.routers import (
                agentic_rag,  # noqa: F401
                auth,  # noqa: F401
                crm_interactions,  # noqa: F401
                crm_practices,  # noqa: F401
            )
        except ImportError as e:
            pytest.fail(f"Failed to import routers: {e}")

    def test_import_middleware(self):
        """Test that middleware modules import successfully"""
        try:
            from middleware.error_monitoring import ErrorMonitoringMiddleware  # noqa: F401
            from middleware.hybrid_auth import HybridAuthMiddleware  # noqa: F401
            from middleware.request_tracing import RequestTracingMiddleware  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import middleware: {e}")

    def test_import_dependencies(self):
        """Test that dependencies module imports successfully"""
        try:
            from app.dependencies import (
                get_ai_client,  # noqa: F401
                get_database_pool,  # noqa: F401
                get_search_service,  # noqa: F401
            )
        except ImportError as e:
            pytest.fail(f"Failed to import dependencies: {e}")

    def test_import_core_modules(self):
        """Test that core modules import successfully"""
        try:
            import core.qdrant_db  # noqa: F401
            from core.cache import get_cache_service  # noqa: F401
            from core.embeddings import create_embeddings_generator  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import core modules: {e}")


class TestImportTimeCriticalPaths:
    """Test critical import paths that must work for application startup"""

    def test_import_path_main_cloud_to_routers(self):
        """
        Test the import chain: main_cloud -> app_factory -> router_registration -> routers

        This simulates the actual import path during application startup.
        """
        try:
            # This should trigger the full import chain
            import app.main_cloud  # noqa: F401

            # Verify routers are accessible
            from app.setup.router_registration import include_routers  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import critical path: {e}")

    def test_import_path_service_initializer_to_agentic(self):
        """
        Test the import chain: service_initializer -> intelligent_router -> agentic_rag

        This simulates the import path that was failing before (detect_team_query missing).
        """
        try:
            from app.setup.service_initializer import initialize_services  # noqa: F401
            from services.rag.agentic import create_agentic_rag  # noqa: F401
            from services.rag.agentic.reasoning import detect_team_query  # noqa: F401
            from services.rag.agentic.session_fact_extractor import (
                SessionFactExtractor,  # noqa: F401
            )
            from services.routing.intelligent_router import IntelligentRouter  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import service initializer path: {e}")
