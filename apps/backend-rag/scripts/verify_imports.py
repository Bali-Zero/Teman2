#!/usr/bin/env python3
"""
Import Verification Script

Verifies that all critical modules can be imported without errors.
This script can be run before deployment to catch ImportError issues early.

Usage:
    python scripts/verify_imports.py

Exit codes:
    0: All imports successful
    1: One or more imports failed
"""

import os
import sys
from pathlib import Path

# Set minimal environment variables for import verification
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def verify_import(module_name: str, import_statement: str) -> tuple[bool, str]:
    """
    Verify that a module can be imported.

    Args:
        module_name: Human-readable name of the module
        import_statement: Python import statement to execute

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        exec(import_statement)
        return True, ""
    except ImportError as e:
        return False, f"ImportError: {e}"
    except Exception as e:
        return False, f"Unexpected error: {type(e).__name__}: {e}"


def main() -> int:
    """Main verification function"""
    print("🔍 Verifying critical module imports...")
    print("=" * 70)

    # Critical imports that must work for application startup
    critical_imports = [
        ("app.main_cloud", "import app.main_cloud"),
        ("app.setup.app_factory", "from app.setup.app_factory import create_app"),
        (
            "app.setup.service_initializer",
            "from app.setup.service_initializer import initialize_services",
        ),
        ("services.rag.agentic", "from services.rag.agentic import create_agentic_rag"),
        (
            "services.rag.agentic.reasoning",
            "from services.rag.agentic.reasoning import detect_team_query",
        ),
        (
            "services.rag.agentic.session_fact_extractor",
            "from services.rag.agentic.session_fact_extractor import SessionFactExtractor",
        ),
        ("app.routers.agentic_rag", "from app.routers import agentic_rag"),
        ("app.routers.crm_practices", "from app.routers import crm_practices"),
        ("middleware.hybrid_auth", "from middleware.hybrid_auth import HybridAuthMiddleware"),
        ("app.dependencies", "from app.dependencies import get_database_pool"),
        ("core.embeddings", "from core.embeddings import create_embeddings_generator"),
        ("core.qdrant_db", "import core.qdrant_db"),
    ]

    failed_imports = []
    passed_count = 0

    for module_name, import_stmt in critical_imports:
        success, error = verify_import(module_name, import_stmt)
        if success:
            print(f"✅ {module_name}")
            passed_count += 1
        else:
            print(f"❌ {module_name}: {error}")
            failed_imports.append((module_name, error))

    print("=" * 70)
    print(f"Results: {passed_count}/{len(critical_imports)} imports successful")

    if failed_imports:
        print("\n❌ FAILED IMPORTS:")
        for module_name, error in failed_imports:
            print(f"  - {module_name}: {error}")
        print("\n⚠️  Fix these import errors before deploying!")
        return 1
    else:
        print("\n✅ All critical imports verified successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
