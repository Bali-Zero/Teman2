import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("apps/backend-rag/backend"))

# Mock settings
with patch("app.core.config.settings") as mock_settings:
    mock_settings.google_api_key = "test_key"
    mock_settings.gemini_model_smart = "gemini-pro"
    
    from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator
    from services.memory_service_postgres import UserMemory

async def verify_agentic_brain():
    print("🧠 Verifying Agentic Brain Upgrade...")

    # 1. Mock Services
    mock_memory_service = MagicMock()
    mock_memory_service.get_memory = AsyncMock(return_value=UserMemory(
        user_id="test_user",
        profile_facts=["Is a software engineer", "Lives in Bali"],
        summary="User is interested in visa regulations.",
        counters={"conversations": 10},
        updated_at=None
    ))
    mock_memory_service.get_recent_history = AsyncMock(return_value=[
        {"role": "user", "content": "Hi there"},
        {"role": "assistant", "content": "Hello! How can I help?"}
    ])

    mock_search_service = MagicMock()
    mock_search_service.search = AsyncMock(return_value={
        "results": [
            {
                "text": "Kitas pricing is 10M IDR.",
                "metadata": {"title": "Pricing Doc"},
                "score": 0.9
            }
        ]
    })

    # 2. Initialize Orchestrator with Mocks
    orchestrator = AgenticRAGOrchestrator(
        memory_service=mock_memory_service,
        search_service=mock_search_service
    )
    
    # Mock Gemini Model
    orchestrator.model = MagicMock()
    orchestrator.model.generate_content_async = AsyncMock(return_value=MagicMock(text="Based on the pricing doc, Kitas is 10M IDR."))

    # 3. Process Query
    query = "How much is Kitas?"
    print(f"❓ Query: {query}")
    
    result = await orchestrator.process_query(query, user_id="test_user")

    # 4. Verify Interactions
    print("\n🔍 Verification Results:")
    
    # Check Memory Access
    mock_memory_service.get_memory.assert_called_with("test_user")
    print("✅ Memory Service accessed (User Profile)")
    
    mock_memory_service.get_recent_history.assert_called_with("test_user", limit=5)
    print("✅ Memory Service accessed (History)")
    
    # Check Search Access
    mock_search_service.search.assert_called()
    print("✅ Search Service accessed (RAG)")
    
    # Check Response Structure
    assert "answer" in result
    assert "sources" in result
    assert len(result["sources"]) == 1
    assert result["sources"][0]["title"] == "Pricing Doc"
    print("✅ Response contains answer and sources")
    
    print(f"\n🤖 AI Answer: {result['answer']}")
    print("\n🎉 Agentic Brain Upgrade Verified Successfully!")

if __name__ == "__main__":
    asyncio.run(verify_agentic_brain())
