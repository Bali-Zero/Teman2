from __future__ import annotations

import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from backend.services.multimodal import cloud_vision_gate
from backend.services.rag.vision_rag import MultiModalDocument, VisionRAGService, VisualElement


def _png_bytes(width: int = 12, height: int = 8) -> bytes:
    image = Image.new("RGB", (width, height), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_analyze_visual_element_prefers_ollama_and_builds_visual_element() -> None:
    service = VisionRAGService()
    service._vision_via_ollama = AsyncMock(
        return_value="""```json
        {
          "type": "TABLE",
          "extracted_text": "Name Amount",
          "description": "A fee table",
          "table_markdown": "| Name | Amount |"
        }
        ```""",
    )
    service._vision_via_gemini = AsyncMock(return_value=None)

    element = await service._analyze_visual_element(_png_bytes(), page_num=3, element_id="img-1")

    assert element is not None
    assert element.element_type == "table"
    assert element.page_number == 3
    assert element.bounding_box == (0, 0, 12, 8)
    assert element.image_data == _png_bytes()
    assert element.extracted_text == "Name Amount\n| Name | Amount |"
    assert element.description == "A fee table"
    service._vision_via_ollama.assert_awaited_once()
    service._vision_via_gemini.assert_not_awaited()


@pytest.mark.asyncio
async def test_analyze_visual_element_falls_back_to_gemini_when_ollama_empty() -> None:
    service = VisionRAGService()
    service._vision_via_ollama = AsyncMock(return_value=None)
    service._vision_via_gemini = AsyncMock(
        return_value='{"type": "PHOTO", "extracted_text": "", "description": "Passport scan"}',
    )

    element = await service._analyze_visual_element(_png_bytes(), page_num=1, element_id="img-2")

    assert element is not None
    assert element.element_type == "photo"
    assert element.description == "Passport scan"
    service._vision_via_gemini.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_visual_element_returns_none_for_invalid_provider_json() -> None:
    service = VisionRAGService()
    service._vision_via_ollama = AsyncMock(return_value="not-json")
    service._vision_via_gemini = AsyncMock(return_value=None)

    assert await service._analyze_visual_element(_png_bytes(), 1, "img-3") is None


@pytest.mark.asyncio
async def test_query_with_vision_returns_blocked_response_when_cloud_gate_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = []
    monkeypatch.setattr(cloud_vision_gate, "cloud_vision_allowed", lambda: False)
    monkeypatch.setattr(cloud_vision_gate, "note_cloud_ocr_blocked", blocked.append)

    service = VisionRAGService()
    document = MultiModalDocument(
        doc_id="doc-1",
        text_content="KITAS fee schedule",
        visual_elements=[
            VisualElement(
                element_type="table",
                page_number=1,
                bounding_box=(0, 0, 1, 1),
                image_data=_png_bytes(1, 1),
                extracted_text="KITAS fee",
                description="A table about KITAS fees",
            ),
        ],
        metadata={},
    )

    result = await service.query_with_vision("KITAS fee", [document])

    assert result == {
        "answer": "Vision service unavailable (cloud fallback blocked for PII sovereignty)",
        "visuals_used": [],
        "text_context_length": 0,
    }
    assert blocked == ["rag.vision_rag.VisionRAG.query_with_vision"]


def test_is_relevant_matches_query_terms_against_description_and_text() -> None:
    service = VisionRAGService()
    element = VisualElement(
        element_type="table",
        page_number=1,
        bounding_box=(0, 0, 1, 1),
        image_data=b"",
        extracted_text="KITAS investor renewal",
        description="Immigration fee table",
    )

    assert service._is_relevant("KITAS renewal", element) is True
    assert service._is_relevant("restaurant alcohol license", element) is False
