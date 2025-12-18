import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env vars from apps/backend-rag/.env
load_dotenv(Path(__file__).parent.parent / "apps" / "backend-rag" / ".env")

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "apps" / "backend-rag" / "backend"))

from unittest.mock import MagicMock, AsyncMock  # noqa: E402
import sys  # noqa: E402

# Mock services BEFORE importing IntelligentRouter
sys.modules["services.golden_router_service"] = MagicMock()
sys.modules["services.memory_service_postgres"] = MagicMock()

# Mock the classes inside the modules
mock_router_service = MagicMock()
mock_router_service.GoldenRouterService = MagicMock()
mock_router_instance = AsyncMock()
mock_router_instance.initialize = AsyncMock()
mock_router_instance.route = AsyncMock(return_value=None)  # Default to no route
mock_router_service.GoldenRouterService.return_value = mock_router_instance
sys.modules["services.golden_router_service"] = mock_router_service

mock_memory_service = MagicMock()
mock_memory_service.MemoryServicePostgres = MagicMock()
mock_memory_instance = AsyncMock()
mock_memory_instance.get_relevant_facts = AsyncMock(return_value=["User is testing."])
mock_memory_instance.get_recent_history = AsyncMock(return_value=[])
mock_memory_service.MemoryServicePostgres.return_value = mock_memory_instance
sys.modules["services.memory_service_postgres"] = mock_memory_service

from services.intelligent_router import IntelligentRouter  # noqa: E402
from app.core.config import settings  # noqa: E402


async def verify_integration():
    print("🚀 Verifying Agentic RAG Integration (with Mocks)...")

    # Initialize Router
    router = IntelligentRouter()
    await router.initialize()

    # Mock the orchestrator's internal components that might still need it
    router.orchestrator.mt_retriever = AsyncMock()
    router.orchestrator.mt_retriever.retrieve_with_graph_expansion = AsyncMock(
        return_value={
            "combined_context": "This is a mock context about PT PMA in Bali.",
            "primary_results": {
                "chunks": [
                    {
                        "title": "Mock Law",
                        "source_file": "law.pdf",
                        "collection": "legal",
                    }
                ]
            },
            "related_results": {},
        }
    )

    query = "Apa syarat mendirikan PT PMA di Bali?"
    user_id = "test_user"

    print(f"\n📝 Query: {query}")
    print("🌊 Streaming response...")

    chunks_received = 0
    metadata_received = False
    sources_received = False

    try:
        async for chunk in router.stream_chat(query, user_id):
            chunks_received += 1

            if chunk["type"] == "metadata":
                metadata_received = True
                print(f"\n[METADATA] {chunk['data']}")
            elif chunk["type"] == "token":
                print(chunk["data"], end="", flush=True)
            elif chunk["type"] == "sources":
                sources_received = True
                print(f"\n\n[SOURCES] {len(chunk['data'])} sources found")
                for s in chunk["data"]:
                    print(f"- {s['title']} ({s['collection']})")
            elif chunk["type"] == "done":
                print("\n\n[DONE]")

    except Exception as e:
        print(f"\n❌ Error during streaming: {e}")
        import traceback

        traceback.print_exc()
        return

    print("\n\n✅ Verification Results:")
    print(f"- Chunks received: {chunks_received}")
    print(f"- Metadata received: {metadata_received}")
    print(f"- Sources received: {sources_received}")

    if chunks_received > 0 and metadata_received:
        print(
            "🎉 Integration SUCCESS! IntelligentRouter is correctly using AgenticRAGOrchestrator."
        )
    else:
        print("⚠️ Integration verification FAILED.")


if __name__ == "__main__":
    if not settings.google_api_key:
        print("❌ GOOGLE_API_KEY not set")
    else:
        asyncio.run(verify_integration())
