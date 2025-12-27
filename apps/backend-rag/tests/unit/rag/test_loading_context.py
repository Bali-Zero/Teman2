import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.asyncio
async def test_user_context_loaded_before_greeting(monkeypatch):
    """Ensure process_query loads user_context before bypass checks (greetings)."""
    from services.rag.agentic.orchestrator import AgenticRAGOrchestrator
    import services.rag.agentic.orchestrator as orchestrator_module

    tool = MagicMock()
    tool.name = "vector_search"
    tool.to_gemini_function_declaration = MagicMock(return_value={"name": "vector_search"})

    called = {"ctx": False}

    async def fake_get_user_context(db_pool, user_id, memory_orchestrator, query=None, session_id=None, **_kwargs):
        called["ctx"] = True
        return {"profile": {"name": "Test"}, "facts": ["Budget: 50k USD"], "history": []}

    monkeypatch.setattr(orchestrator_module, "get_user_context", fake_get_user_context)

    with patch("services.rag.agentic.orchestrator.LLMGateway") as mock_gateway_class:
        mock_gateway_class.return_value = MagicMock()
        orch = AgenticRAGOrchestrator(tools=[tool], db_pool=None, retriever=MagicMock())
        orch._get_memory_orchestrator = AsyncMock(return_value=None)

        def fake_check_greetings(q, context=None):
            assert called["ctx"] is True
            assert context and context.get("facts")
            return "Ciao! Come posso aiutarti oggi?"

        orch.prompt_builder.check_greetings = MagicMock(side_effect=fake_check_greetings)

        result = await orch.process_query(query="Ciao", user_id="test@example.com")
        assert result.answer.startswith("Ciao")

