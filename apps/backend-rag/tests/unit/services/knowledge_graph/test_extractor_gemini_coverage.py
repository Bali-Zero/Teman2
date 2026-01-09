import importlib.util
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
module_path = backend_path / "services" / "knowledge_graph" / "extractor_gemini.py"
module_name = "services.knowledge_graph.extractor_gemini"


def _build_module(monkeypatch, client_factory):
    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = [str(backend_path / "services")]
    kg_pkg = types.ModuleType("services.knowledge_graph")
    kg_pkg.__path__ = [str(backend_path / "services" / "knowledge_graph")]
    monkeypatch.setitem(sys.modules, "services", services_pkg)
    monkeypatch.setitem(sys.modules, "services.knowledge_graph", kg_pkg)

    @dataclass
    class _ExtractedEntity:
        id: str
        type: object
        name: str
        mention: str
        attributes: dict = field(default_factory=dict)
        confidence: float = 0.8

    @dataclass
    class _ExtractedRelation:
        source_id: str
        target_id: str
        type: object
        evidence: str
        confidence: float = 0.7
        attributes: dict = field(default_factory=dict)

    @dataclass
    class _ExtractionResult:
        chunk_id: str
        entities: list = field(default_factory=list)
        relations: list = field(default_factory=list)
        raw_text: str = ""
        metadata: dict = field(default_factory=dict)

    extractor_stub = types.SimpleNamespace(ExtractedEntity=_ExtractedEntity,
        ExtractedRelation=_ExtractedRelation,
        ExtractionResult=_ExtractionResult,
        redis_url='redis://localhost:6379'
    )
    monkeypatch.setitem(sys.modules, "services.knowledge_graph.extractor", extractor_stub)

    ontology_name = "services.knowledge_graph.ontology"
    if ontology_name not in sys.modules:
        ontology_path = backend_path / "services" / "knowledge_graph" / "ontology.py"
        ontology_spec = importlib.util.spec_from_file_location(ontology_name, ontology_path)
        ontology_module = importlib.util.module_from_spec(ontology_spec)
        sys.modules[ontology_name] = ontology_module
        assert ontology_spec and ontology_spec.loader
        ontology_spec.loader.exec_module(ontology_module)

    google_genai = types.SimpleNamespace(Client=client_factory, redis_url='redis://localhost:6379')
    google_module = types.SimpleNamespace(genai=google_genai, redis_url='redis://localhost:6379')
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", google_genai)

    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _client_factory(response_text=None, error=None, call_counter=None):
    def _generate_content(*, model, contents, config):
        if call_counter is not None:
            call_counter["count"] += 1
        if error:
            raise error
        return types.SimpleNamespace(text=response_text, redis_url='redis://localhost:6379')

    class _Client:
        def __init__(self, api_key):
            self.api_key = api_key
            self.models = types.SimpleNamespace(generate_content=_generate_content, redis_url='redis://localhost:6379')

    return _Client


def test_init_requires_api_key(monkeypatch):
    module = _build_module(monkeypatch, _client_factory(response_text="{}"))
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_IMAGEN_API_KEY", raising=False)

    with pytest.raises(ValueError):
        module.GeminiKGExtractor()


def test_schema_prompt_includes_types(monkeypatch):
    module = _build_module(monkeypatch, _client_factory(response_text="{}"))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    extractor = module.GeminiKGExtractor()

    assert "ENTITY TYPES" in extractor.schema_prompt
    assert "RELATION TYPES" in extractor.schema_prompt
    assert "undang_undang" in extractor.schema_prompt


@pytest.mark.asyncio
async def test_extract_short_text_skips_generation(monkeypatch):
    call_counter = {"count": 0}
    module = _build_module(
        monkeypatch, _client_factory(response_text="{}", call_counter=call_counter)
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    extractor = module.GeminiKGExtractor()
    result = await extractor.extract("short", chunk_id="c1")

    assert result.chunk_id == "c1"
    assert result.raw_text == "short"
    assert result.entities == []
    assert result.relations == []
    assert call_counter["count"] == 0


@pytest.mark.asyncio
async def test_extract_parses_json_response(monkeypatch):
    response_text = json.dumps(
        {
            "entities": [
                {
                    "id": "e1",
                    "type": "undang_undang",
                    "name": "UU No. 6 Tahun 2023",
                    "mention": "UU No 6/2023",
                    "attributes": {"number": 6, "year": 2023},
                    "confidence": 0.91,
                }
            ],
            "relations": [
                {
                    "source_id": "e1",
                    "target_id": "e2",
                    "type": "REQUIRES",
                    "evidence": "wajib memiliki",
                    "confidence": 0.88,
                }
            ],
        }
    )
    module = _build_module(monkeypatch, _client_factory(response_text=response_text))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    extractor = module.GeminiKGExtractor()
    result = await extractor.extract("Legal text content here", chunk_id="c2")

    assert result.chunk_id == "c2"
    assert len(result.entities) == 1
    assert result.entities[0].type.value == "undang_undang"
    assert len(result.relations) == 1
    assert result.relations[0].type.value == "REQUIRES"


@pytest.mark.asyncio
async def test_extract_wrapped_json_skips_unknown_types(monkeypatch):
    response_text = """
    Some preface text
    {
      "entities": [
        {"type": "undang", "name": "UU", "mention": "UU", "confidence": 0.9},
        {"type": "unknown_type", "name": "X"}
      ],
      "relations": [
        {"source_id": "e1", "target_id": "e2", "type": "REQUIRES"},
        "not-a-dict"
      ]
    }
    trailing text
    """
    module = _build_module(monkeypatch, _client_factory(response_text=response_text))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    extractor = module.GeminiKGExtractor()
    result = await extractor.extract("Legal text content here", chunk_id="c3")

    assert len(result.entities) == 1
    assert result.entities[0].type.value == "undang_undang"
    assert len(result.relations) == 1
    assert result.relations[0].type.value == "REQUIRES"


@pytest.mark.asyncio
async def test_extract_no_json_or_errors(monkeypatch):
    module = _build_module(monkeypatch, _client_factory(response_text="no json here"))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    extractor = module.GeminiKGExtractor()
    result = await extractor.extract("Legal text content here", chunk_id="c4")

    assert result.chunk_id == "c4"
    assert result.entities == []
    assert result.relations == []

    module_error = _build_module(monkeypatch, _client_factory(error=RuntimeError("boom")))
    extractor_error = module_error.GeminiKGExtractor(api_key="test-key")
    result_error = await extractor_error.extract("Legal text content here", chunk_id="c5")

    assert result_error.chunk_id == "c5"
    assert result_error.entities == []
    assert result_error.relations == []
