from __future__ import annotations

from typing import Any

import pytest

from backend.services.rag.agentic import pipeline as module
from backend.services.rag.agentic.pipeline import (
    CitationStage,
    FormatStage,
    PipelineStage,
    ResponsePipeline,
    VerificationStage,
    create_default_pipeline,
)


class _AppendStage(PipelineStage):
    def __init__(self, marker: str) -> None:
        self.marker = marker

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        data.setdefault("markers", []).append(self.marker)
        return data


class _FailingStage(PipelineStage):
    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("stage failed")


def test_create_default_pipeline_preserves_expected_stage_order() -> None:
    pipeline = create_default_pipeline()

    assert [stage.name for stage in pipeline.stages] == [
        "VerificationStage",
        "PostProcessingStage",
        "CitationStage",
        "FormatStage",
    ]


@pytest.mark.asyncio
async def test_response_pipeline_continues_when_a_stage_fails() -> None:
    pipeline = ResponsePipeline([_AppendStage("before"), _FailingStage(), _AppendStage("after")])

    result = await pipeline.process({"response": "ok"})

    assert result["markers"] == ["before", "after"]
    assert result["stages_completed"] == [
        "_AppendStage",
        "_FailingStage (failed)",
        "_AppendStage",
    ]


@pytest.mark.asyncio
async def test_response_pipeline_rejects_none_input() -> None:
    pipeline = ResponsePipeline([])

    with pytest.raises(ValueError, match="cannot be None"):
        await pipeline.process(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_verification_stage_skips_short_or_contextless_responses() -> None:
    stage = VerificationStage(min_response_length=20)

    result = await stage.process({"response": "short", "query": "KITAS", "context_chunks": []})

    assert result["verification_score"] == 1.0
    assert result["verification_status"] == "skipped"


@pytest.mark.asyncio
async def test_post_processing_stage_uses_shared_response_cleaner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "post_process_response", lambda response, query: "cleaned")
    pipeline = create_default_pipeline()

    result = await pipeline.process(
        {
            "response": "raw answer",
            "query": "How do I renew KITAS?",
            "context_chunks": [],
            "sources": [],
        },
    )

    assert result["response"] == "cleaned"
    assert result["pipeline_version"] == "1.0"
    assert result["stages_completed"][-2:] == ["CitationStage", "FormatStage"]


def test_citation_stage_deduplicates_filters_and_sorts_sources() -> None:
    stage = CitationStage(max_citations=2)
    sources = [
        {"title": "Low", "url": "https://a.test", "score": 0.1},
        {"title": "", "url": "https://skip.test", "score": 1.0},
        {"title": "High", "source_url": "https://b.test", "score": 0.9},
        {"title": "Low", "url": "https://a.test", "score": 0.8},
        "not a source",
    ]

    citations = stage._normalize_citations(sources)

    assert citations == [
        {
            "title": "High",
            "url": "https://b.test",
            "collection": "",
            "score": 0.9,
            "snippet": "",
            "metadata": {},
        },
        {
            "title": "Low",
            "url": "https://a.test",
            "collection": "",
            "score": 0.1,
            "snippet": "",
            "metadata": {},
        },
    ]


@pytest.mark.asyncio
async def test_format_stage_strips_response_and_adds_defaults() -> None:
    result = await FormatStage().process({"response": "  Done  "})

    assert result["response"] == "Done"
    assert result["citations"] == []
    assert result["pipeline_version"] == "1.0"
    assert result["stages_completed"] == ["FormatStage"]
