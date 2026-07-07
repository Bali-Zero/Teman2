from __future__ import annotations

from typing import Any

import pytest

from backend.services.knowledge_graph import extractor_gemini as gemini_module
from backend.services.knowledge_graph.extractor_gemini import GeminiKGExtractor
from backend.services.knowledge_graph.ontology import EntityType, RelationType


class FakeGenAIClient:
    def __init__(self, response_text: str | None = None, *, fail: bool = False) -> None:
        self.response_text = response_text or "{}"
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> dict[str, str]:
        if self.fail:
            raise RuntimeError("genai unavailable")
        self.calls.append(kwargs)
        return {"text": self.response_text}


def make_extractor(monkeypatch: pytest.MonkeyPatch, client: FakeGenAIClient) -> GeminiKGExtractor:
    monkeypatch.setattr(gemini_module, "get_genai_client", lambda: client)
    return GeminiKGExtractor(model="gemini-test", max_tokens=512, temperature=0.0)


def test_build_schema_prompt_includes_entities_relations_and_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extractor = make_extractor(monkeypatch, FakeGenAIClient())

    assert "## ENTITY TYPES" in extractor.schema_prompt
    assert "undang_undang" in extractor.schema_prompt
    assert "## RELATION TYPES" in extractor.schema_prompt
    assert "REQUIRES" in extractor.schema_prompt
    assert "triggers:" in extractor.schema_prompt


def test_build_extraction_prompt_embeds_text_and_output_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extractor = make_extractor(monkeypatch, FakeGenAIClient())

    prompt = extractor._build_extraction_prompt("Pasal 10 UU No. 6 Tahun 2023")

    assert "Pasal 10 UU No. 6 Tahun 2023" in prompt
    assert "Return a JSON object with this exact structure" in prompt
    assert '"entities"' in prompt
    assert '"relations"' in prompt


@pytest.mark.asyncio
async def test_extract_parses_direct_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeGenAIClient(
        """
        {
          "entities": [
            {
              "id": "e1",
              "type": "undang_undang",
              "name": "UU No. 6 Tahun 2023",
              "mention": "UU No 6/2023",
              "attributes": {"number": 6, "year": 2023},
              "confidence": 0.95
            }
          ],
          "relations": [
            {
              "source_id": "e2",
              "target_id": "e1",
              "type": "PART_OF",
              "evidence": "Pasal 10 UU No. 6 Tahun 2023",
              "confidence": 0.9
            }
          ]
        }
        """,
    )
    extractor = make_extractor(monkeypatch, client)

    result = await extractor.extract("Pasal 10 UU No. 6 Tahun 2023 mengatur izin.", "chunk-1")

    assert result.chunk_id == "chunk-1"
    assert result.raw_text.startswith("Pasal 10")
    assert len(result.entities) == 1
    assert result.entities[0].type == EntityType.UNDANG_UNDANG
    assert result.entities[0].attributes == {"number": 6, "year": 2023}
    assert len(result.relations) == 1
    assert result.relations[0].type == RelationType.PART_OF
    assert client.calls[0]["model"] == "gemini-test"
    assert client.calls[0]["endpoint"] == "kg_extractor"


@pytest.mark.asyncio
async def test_extract_recovers_json_embedded_in_model_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeGenAIClient(
        'Here is the JSON:\n{"entities": [{"type": "kitas_visa", "name": "KITAS", '
        '"mention": "KITAS"}], "relations": []}\nDone.',
    )
    extractor = make_extractor(monkeypatch, client)

    result = await extractor.extract("KITAS investor requires sponsor document.", "chunk-2")

    assert len(result.entities) == 1
    assert result.entities[0].type == EntityType.KITAS
    assert result.entities[0].id == "e1"


@pytest.mark.asyncio
async def test_extract_returns_empty_result_for_short_text(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeGenAIClient()
    extractor = make_extractor(monkeypatch, client)

    result = await extractor.extract("short", "chunk-short")

    assert result.chunk_id == "chunk-short"
    assert result.raw_text == "short"
    assert result.entities == []
    assert result.relations == []
    assert client.calls == []


@pytest.mark.asyncio
async def test_extract_returns_empty_result_when_client_or_json_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing_extractor = make_extractor(monkeypatch, FakeGenAIClient(fail=True))
    failing_result = await failing_extractor.extract("Valid legal text with enough length.", "c1")
    assert failing_result.entities == []

    invalid_extractor = make_extractor(monkeypatch, FakeGenAIClient("no json here"))
    invalid_result = await invalid_extractor.extract("Valid legal text with enough length.", "c2")
    assert invalid_result.entities == []


def test_parse_helpers_skip_unknown_types_and_bad_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    extractor = make_extractor(monkeypatch, FakeGenAIClient())

    entities = extractor._parse_entities(
        [
            {"id": "e1", "type": "nib", "name": "NIB", "mention": "NIB"},
            {"id": "bad", "type": "unknown", "name": "Unknown"},
            {"id": "bad-confidence", "type": "kitas", "confidence": "not-float"},
        ],
    )
    relations = extractor._parse_relations(
        [
            {"source_id": "e1", "target_id": "e2", "type": "REQUIRES", "evidence": "needs"},
            {"source_id": "bad", "target_id": "e2", "type": "UNKNOWN", "evidence": "bad"},
            {"source_id": "bad", "target_id": "e2", "type": "PART_OF", "confidence": "bad"},
        ],
    )

    assert [entity.id for entity in entities] == ["e1"]
    assert entities[0].type == EntityType.NIB
    assert [relation.type for relation in relations] == [RelationType.REQUIRES]
