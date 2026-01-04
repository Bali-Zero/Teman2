import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


class DummySuggestion:
    def __init__(self, suggestion_id="id1"):
        self.suggestion_id = suggestion_id
        self.suggestion_type = SimpleNamespace(value="type")
        self.priority = SimpleNamespace(value="high")
        self.title = "Title"
        self.description = "Desc"
        self.action_label = "Act"
        self.action_payload = {"k": "v"}
        self.icon = "icon"


class DummyContextSuggestionService:
    def __init__(self, suggestions=None, error=None):
        self._suggestions = suggestions or []
        self._error = error
        self.calls = []

    async def get_suggestions(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._suggestions


class DummyOrchestrator:
    def __init__(self, result=None, stream_chunks=None, error=None):
        self._result = result
        self._stream_chunks = stream_chunks or []
        self._error = error
        self.init_calls = 0

    async def initialize(self):
        self.init_calls += 1

    async def process_query(self, **_kwargs):
        if self._error:
            raise self._error
        return self._result

    async def stream_query(self, **_kwargs):
        if self._error:
            raise self._error
        for chunk in self._stream_chunks:
            yield chunk


services_pkg = types.ModuleType("services")
services_pkg.__path__ = []
misc_pkg = types.ModuleType("services.misc")
misc_pkg.__path__ = []
rag_pkg = types.ModuleType("services.rag")
rag_pkg.__path__ = []

clarification_module = types.ModuleType("services.misc.clarification_service")


class ClarificationService:
    def __init__(self, search_service=None):
        self.search_service = search_service


clarification_module.ClarificationService = ClarificationService

context_module = types.ModuleType("services.misc.context_suggestion_service")


def get_context_suggestion_service(db_pool=None):
    return DummyContextSuggestionService()


context_module.get_context_suggestion_service = get_context_suggestion_service

agentic_module = types.ModuleType("services.rag.agentic")


def create_agentic_rag(**_kwargs):
    return DummyOrchestrator()


agentic_module.create_agentic_rag = create_agentic_rag

sys.modules.update(
    {
        "services": services_pkg,
        "services.misc": misc_pkg,
        "services.rag": rag_pkg,
        "services.misc.clarification_service": clarification_module,
        "services.misc.context_suggestion_service": context_module,
        "services.rag.agentic": agentic_module,
    }
)

module_path = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "services"
    / "routing"
    / "intelligent_router.py"
)
spec = importlib.util.spec_from_file_location("services.routing.intelligent_router", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
IntelligentRouter = module.IntelligentRouter


@pytest.mark.asyncio
async def test_initialize_calls_orchestrator():
    orchestrator = DummyOrchestrator()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        router = IntelligentRouter()
        await router.initialize()
    assert orchestrator.init_calls == 1


@pytest.mark.asyncio
async def test_route_chat_with_dict_and_suggestions():
    result = {"answer": "ok", "sources": ["s1"], "routing_stats": {"latency": 1}}
    orchestrator = DummyOrchestrator(result=result)
    suggestions = [DummySuggestion()]
    suggestion_service = DummyContextSuggestionService(suggestions=suggestions)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        mp.setattr(
            module, "get_context_suggestion_service", lambda db_pool=None: suggestion_service
        )
        router = IntelligentRouter()
        response = await router.route_chat("hi", "user", conversation_history=[])

    assert response["response"] == "ok"
    assert response["sources"] == ["s1"]
    assert response["routing_stats"] == {"latency": 1}
    assert response["suggestions"][0]["id"] == "id1"


@pytest.mark.asyncio
async def test_route_chat_core_result_no_suggestions():
    result = SimpleNamespace(answer="ok", sources=[], routing_stats=None)
    orchestrator = DummyOrchestrator(result=result)
    suggestion_service = DummyContextSuggestionService()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        mp.setattr(
            module, "get_context_suggestion_service", lambda db_pool=None: suggestion_service
        )
        router = IntelligentRouter()
        response = await router.route_chat(
            "hi", "user", conversation_history=[], include_suggestions=False
        )

    assert response["response"] == "ok"
    assert "suggestions" not in response
    assert suggestion_service.calls == []


@pytest.mark.asyncio
async def test_route_chat_suggestions_error_is_ignored():
    result = {"answer": "ok", "sources": []}
    orchestrator = DummyOrchestrator(result=result)
    suggestion_service = DummyContextSuggestionService(error=RuntimeError("boom"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        mp.setattr(
            module, "get_context_suggestion_service", lambda db_pool=None: suggestion_service
        )
        router = IntelligentRouter()
        response = await router.route_chat("hi", "user", conversation_history=[])

    assert response["response"] == "ok"


@pytest.mark.asyncio
async def test_route_chat_raises_on_error():
    orchestrator = DummyOrchestrator(error=RuntimeError("fail"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        router = IntelligentRouter()
        with pytest.raises(Exception) as exc:
            await router.route_chat("hi", "user", conversation_history=[])
    assert "Routing failed" in str(exc.value)


@pytest.mark.asyncio
async def test_stream_chat_yields_chunks():
    orchestrator = DummyOrchestrator(stream_chunks=["a", "b", "c"])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        router = IntelligentRouter()
        chunks = []
        async for chunk in router.stream_chat("hi", "user"):
            chunks.append(chunk)
    assert chunks == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_stream_chat_raises_on_error():
    orchestrator = DummyOrchestrator(error=RuntimeError("fail"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        router = IntelligentRouter()
        with pytest.raises(Exception) as exc:
            async for _ in router.stream_chat("hi", "user"):
                pass
    assert "Streaming failed" in str(exc.value)


def test_get_stats():
    router = IntelligentRouter()
    stats = router.get_stats()
    assert stats["router"] == "agentic_rag_wrapper"


@pytest.mark.asyncio
async def test_route_chat_with_object_no_attributes():
    """Test route_chat when result is object without attributes (covers line 109: return default)"""
    # Create an object that is not a dict and doesn't have the attributes
    result = object()  # Plain object with no attributes
    orchestrator = DummyOrchestrator(result=result)
    suggestion_service = DummyContextSuggestionService()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "create_agentic_rag", lambda **_kw: orchestrator)
        mp.setattr(
            module, "get_context_suggestion_service", lambda db_pool=None: suggestion_service
        )
        router = IntelligentRouter()
        response = await router.route_chat("hi", "user", conversation_history=[])

    # get_val should return default values when object has no attributes
    assert response["response"] == ""  # default from get_val(result, "answer", "")
    assert response["sources"] == []  # default from get_val(result, "sources", [])
    # routing_stats is only included if it's not None
    if "routing_stats" in response:
        assert response["routing_stats"] is None
