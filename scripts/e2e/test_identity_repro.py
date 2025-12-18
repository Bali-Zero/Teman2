import asyncio
import sys
from pathlib import Path

# Add apps/backend-rag to path so "backend" package is found
backend_rag_dir = Path("/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag")
sys.path.insert(0, str(backend_rag_dir))

# Also add backend dir for direct imports if needed (though backend.x is preferred)
backend_dir = backend_rag_dir / "backend"
sys.path.insert(0, str(backend_dir))

from services.rag.agentic import AgenticRAGOrchestrator
# from app.services.search_service import SearchService # Not needed for mock

async def test_identity():
    print("--- Testing Identity Awareness ---")
    
    # Mock retriever (we don't need actual search for this test)
    class MockRetriever:
        async def search(self, *args, **kwargs):
            return {"results": []}
        async def search_with_reranking(self, *args, **kwargs):
            return {"results": []}

    # Mock DB Pool
    class MockPool:
        def acquire(self):
            return self
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def fetchrow(self, query, *args):
            if "team_members" in query:
                # Mock user profile
                return {
                    "id": "zero",
                    "name": "Zero",
                    "role": "Founder",
                    "department": "Management",
                    "team": "Core",
                    "preferred_language": "en",
                    "notes": "The creator.",
                    "emotional_preferences": {}
                }
            if "conversations" in query:
                # Mock history
                return {"messages": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello Zero!"}]}
            return None
        async def fetch(self, query, *args):
            if "memory_facts" in query:
                return [{"content": "Zero likes coffee."}]
            return []

    mock_db_pool = MockPool()

    orchestrator = AgenticRAGOrchestrator(tools=[], db_pool=mock_db_pool)
    
    # Test with a known user ID (e.g., Zero)
    user_id = "zero" 
    query = "Who am I? Do you know my role?"
    
    print(f"Query: {query}")
    print(f"User ID: {user_id}")
    
    # We expect the prompt to be built with user context
    # Since we can't easily inspect the private method output without calling it,
    # we'll call process_query and see if it runs without error.
    # Ideally we'd inspect the logs or response if the model uses the context.
    
    # For this test, let's just inspect the built prompt directly to verify logic
    context = await orchestrator._get_user_context(user_id)
    print("\n[TEST] Retrieved Context:", context)
    
    prompt = orchestrator._build_system_prompt(user_id, context)
    print("\n[TEST] Built System Prompt Snippet:")
    print(prompt.split("### USER CONTEXT")[1].split("### AGENTIC")[0])

if __name__ == "__main__":
    asyncio.run(test_identity())
