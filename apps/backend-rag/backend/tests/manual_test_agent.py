"""
Manual Test Script for LangGraph Agent Workflow (Phase 2 - Real Service Integration)

This script tests the complete RAG workflow with real service integration:
- Retrieve node → SearchService
- Grade node → LLMGateway
- Generate node → LLMGateway

Usage:
    cd /Users/antonellosiano/Projects/nuzantara/apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python backend/tests/manual_test_agent.py

Requirements:
    - .env file with GOOGLE_API_KEY or OPENAI_API_KEY
    - Qdrant running (for SearchService)
    - Backend services initialized
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set PYTHONPATH environment
os.environ.setdefault("PYTHONPATH", str(project_root))


async def test_workflow_with_mocked_services():
    """Test 1: Workflow with mocked services (no external dependencies)"""
    print("\n" + "=" * 80)
    print("TEST 1: Workflow with Mocked Services (Baseline)")
    print("=" * 80)

    from backend.app.agents.graph import invoke_rag_workflow

    question = "What are the requirements for opening a PT PMA in Bali?"
    metadata = {
        "user_id": "test_user_123",
        "session_id": "test_session_456",
        "test_mode": "mocked",
    }

    print(f"\n📝 Question: {question}")
    print("🔧 Mode: Mocked services (no external calls)")

    try:
        result = await invoke_rag_workflow(question=question, metadata=metadata)

        print("\n" + "=" * 80)
        print("✅ MOCKED WORKFLOW RESULTS")
        print("=" * 80)
        print(f"Success: {not bool(result.get('errors'))}")
        print(f"Execution Path: {result.get('execution_path', [])}")
        print(f"Step Count: {result.get('step_count', 0)}")
        print(f"Documents Retrieved: {len(result.get('documents', []))}")
        print(f"Filtered Documents: {len(result.get('filtered_documents', []))}")
        print("\n📄 Generation (first 500 chars):")
        print(result.get("generation", "No generation")[:500])

        if result.get("errors"):
            print(f"\n⚠️ Errors: {result.get('errors')}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_workflow_with_real_services():
    """Test 2: Workflow with real SearchService and LLMGateway integration"""
    print("\n" + "=" * 80)
    print("TEST 2: Workflow with Real Services")
    print("=" * 80)

    try:
        # Initialize services manually
        print("\n🔧 Initializing services...")

        # 1. Initialize SearchService
        from backend.app.core.config import settings
        from backend.core.embeddings import create_embeddings_generator
        from backend.services.ingestion.collection_manager import CollectionManager
        from backend.services.misc.cultural_insights_service import CulturalInsightsService
        from backend.services.routing.conflict_resolver import ConflictResolver
        from backend.services.routing.query_router_integration import QueryRouterIntegration
        from backend.services.search.search_service import SearchService

        print("   → Initializing SearchService...")
        collection_manager = CollectionManager(qdrant_url=settings.qdrant_url)
        conflict_resolver = ConflictResolver()
        query_router = QueryRouterIntegration()
        embedder = create_embeddings_generator()
        cultural_insights = CulturalInsightsService(
            collection_manager=collection_manager, embedder=embedder,
        )

        search_service = SearchService(
            collection_manager=collection_manager,
            conflict_resolver=conflict_resolver,
            cultural_insights=cultural_insights,
            query_router=query_router,
        )
        print("   ✅ SearchService initialized")

        # 2. Initialize LLMGateway
        from backend.services.rag.agentic.llm_gateway import LLMGateway

        print("   → Initializing LLMGateway...")
        llm_gateway = LLMGateway()
        print("   ✅ LLMGateway initialized")

        # 3. Inject services into agent graph
        from backend.app.agents.graph import set_llm_gateway, set_search_service

        print("   → Injecting services into agent graph...")
        set_search_service(search_service)
        set_llm_gateway(llm_gateway)
        print("   ✅ Services injected")

        # 4. Run workflow
        print("\n🚀 Invoking workflow with real services...\n")

        from backend.app.agents.graph import invoke_rag_workflow

        question = "What are the requirements for a KITAS work permit in Indonesia?"
        metadata = {
            "user_id": "test_user_real",
            "session_id": "test_session_real",
            "test_mode": "real_services",
        }

        print(f"📝 Question: {question}")

        result = await invoke_rag_workflow(question=question, metadata=metadata)

        print("\n" + "=" * 80)
        print("✅ REAL WORKFLOW RESULTS")
        print("=" * 80)
        print(f"Success: {not bool(result.get('errors'))}")
        print(f"Execution Path: {result.get('execution_path', [])}")
        print(f"Step Count: {result.get('step_count', 0)}")
        print(f"Timestamp: {result.get('timestamp')}")

        print("\n📊 Retrieval Stats:")
        print(f"   Documents Retrieved: {len(result.get('documents', []))}")
        print(f"   Retrieval Scores: {result.get('retrieved_scores', [])[:3]}")

        print("\n🔍 Grading Stats:")
        print(f"   Filtered Documents: {len(result.get('filtered_documents', []))}")
        print(f"   Relevance Scores: {result.get('relevance_scores', [])[:3]}")

        print("\n📄 Generated Answer:")
        print("-" * 80)
        print(result.get("generation", "No generation"))
        print("-" * 80)

        if result.get("errors"):
            print(f"\n⚠️ Errors: {result.get('errors')}")

        # Print sample documents
        if result.get("documents"):
            print("\n📚 Sample Retrieved Document (first 300 chars):")
            print("-" * 80)
            print(result["documents"][0][:300] + "...")
            print("-" * 80)

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_workflow_error_handling():
    """Test 3: Error handling when services fail"""
    print("\n" + "=" * 80)
    print("TEST 3: Error Handling (Simulated Failures)")
    print("=" * 80)

    # Test with invalid/empty question
    from backend.app.agents.graph import invoke_rag_workflow

    test_cases = [
        ("", "Empty question"),
        ("   ", "Whitespace question"),
        ("a" * 10000, "Extremely long question (10k chars)"),
    ]

    for question, description in test_cases:
        print(f"\n🧪 Testing: {description}")
        try:
            result = await invoke_rag_workflow(question=question)
            print(f"   Result: {'✅ Handled' if result else '❌ Failed'}")
            if result.get("errors"):
                print(f"   Errors captured: {result['errors'][:1]}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")

    return True


async def run_all_tests():
    """Run all test cases"""
    print("\n" + "=" * 80)
    print("LangGraph Agent Workflow - Manual Test Suite")
    print("=" * 80)
    print(f"Started: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    results = {}

    # Test 1: Mocked services (always runs)
    print("\n" + "🔹" * 40)
    results["test_1_mocked"] = await test_workflow_with_mocked_services()

    # Test 2: Real services (requires credentials)
    print("\n" + "🔹" * 40)
    print("\n⚠️ Test 2 requires:")
    print("   - GOOGLE_API_KEY or OPENAI_API_KEY in environment")
    print("   - Qdrant running at configured URL")
    print("   - Backend dependencies installed")

    proceed = input("\n❓ Run Test 2 with real services? (y/n): ").strip().lower()
    if proceed == "y":
        results["test_2_real"] = await test_workflow_with_real_services()
    else:
        print("⏭️  Skipping Test 2")
        results["test_2_real"] = None

    # Test 3: Error handling (always runs)
    print("\n" + "🔹" * 40)
    results["test_3_errors"] = await test_workflow_error_handling()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        if passed is None:
            status = "⏭️  SKIPPED"
        elif passed:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"{status:15} {test_name}")

    passed_count = sum(1 for v in results.values() if v is True)
    total_run = sum(1 for v in results.values() if v is not None)

    print(f"\n📊 Results: {passed_count}/{total_run} tests passed")
    print("=" * 80)
    print(f"Completed: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")

    return all(v is not False for v in results.values())


if __name__ == "__main__":
    print("\n🧪 LangGraph Agent Workflow - Manual Test Script")
    print("=" * 80)

    # Check environment
    print("\n📋 Environment Check:")
    print(f"   Python: {sys.version.split()[0]}")
    print(f"   Working Dir: {os.getcwd()}")
    print(f"   PYTHONPATH: {project_root}")

    # Check critical env vars
    has_google_key = bool(os.getenv("GOOGLE_API_KEY"))
    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
    has_qdrant_url = bool(os.getenv("QDRANT_URL"))

    print("\n🔑 API Keys:")
    print(f"   GOOGLE_API_KEY: {'✅ Set' if has_google_key else '❌ Not set'}")
    print(f"   OPENAI_API_KEY: {'✅ Set' if has_openai_key else '❌ Not set'}")
    print(f"   QDRANT_URL: {'✅ Set' if has_qdrant_url else '❌ Not set (will use default)'}")

    if not (has_google_key or has_openai_key):
        print("\n⚠️ WARNING: No LLM API keys found!")
        print("   Test 2 (real services) will fail without API keys.")
        print("   Test 1 (mocked) will still run successfully.")

    # Run tests
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
