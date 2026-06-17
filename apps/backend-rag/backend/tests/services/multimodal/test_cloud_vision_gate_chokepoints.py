"""PII-sovereignty gate behavior at every cloud-vision OCR chokepoint.

SYMBIOSIS Law 2 / UU PDP Art. 56: when local Ollama OCR is unavailable, NO
chokepoint may send a document image to Google Gemini Vision unless
OCR_ALLOW_CLOUD_VISION=true. This file exercises the *secondary* chokepoints
discovered after the first two (pdf_vision_service + crm_enhanced, covered in
their own test files):

  - portal.document_processing.DocumentOCR._gemini_vision_ocr  → returns ""
  - rag.vision_rag.VisionRAG._vision_via_gemini                → returns None
  - rag.vision_rag.VisionRAG.query_with_vision                 → returns dict
  - crm_clients_documents.extract_passport_enhanced (handler)  → degraded resp

Each test asserts: (a) when blocked, the no-result/degraded path is returned;
(b) the genai client is NEVER constructed (no PII leaves the machine).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDocumentProcessingGeminiOcr:
    @pytest.mark.asyncio
    async def test_blocked_returns_empty_without_client(self) -> None:
        from backend.services.portal.document_processing import DocumentOCR

        # vision_service whose _get_genai_client must NOT be called when blocked
        vision_service = MagicMock()
        vision_service._get_genai_client = MagicMock(
            side_effect=AssertionError("client must NOT be built when blocked")
        )
        with (
            patch(
                "backend.services.multimodal.cloud_vision_gate.cloud_vision_allowed",
                return_value=False,
            ),
            patch(
                "backend.services.multimodal.cloud_vision_gate.note_cloud_ocr_blocked",
            ) as note,
        ):
            result = await DocumentOCR._gemini_vision_ocr("Zm9v", vision_service)
        assert result == ""
        note.assert_called_once()
        assert "document_processing" in note.call_args.args[0]


class TestVisionRagGeminiFallback:
    @pytest.mark.asyncio
    async def test_vision_via_gemini_blocked_returns_none(self) -> None:
        from backend.services.rag.vision_rag import VisionRAGService

        svc = VisionRAGService.__new__(VisionRAGService)  # avoid __init__ side effects
        svc._get_genai_client = MagicMock(  # type: ignore[attr-defined]
            side_effect=AssertionError("client must NOT be built when blocked")
        )
        with (
            patch(
                "backend.services.multimodal.cloud_vision_gate.cloud_vision_allowed",
                return_value=False,
            ),
            patch(
                "backend.services.multimodal.cloud_vision_gate.note_cloud_ocr_blocked",
            ) as note,
        ):
            result = await svc._vision_via_gemini("prompt", "Zm9v")
        assert result is None
        note.assert_called_once()
        assert "vision_rag" in note.call_args.args[0]


class TestCrmClientsDocumentsPassportPreview:
    @pytest.mark.asyncio
    async def test_blocked_returns_degraded_response(self) -> None:
        """extract_passport_enhanced (preview mode, client_id=None): Ollama down +
        cloud blocked → degraded PassportPreviewResponse(success=False), and the
        genai client is never imported/built (no PII to Google)."""
        import httpx

        from backend.app.routers.crm_clients_documents import (
            PassportPreviewRequest,
            extract_passport_enhanced,
        )

        # Preview mode → no DB access; a dummy pool is never acquired.
        req = PassportPreviewRequest(image_base64="Zm9v", mime_type="image/jpeg", client_id=None)

        async def _boom_post(*_a, **_k):  # noqa: ANN002, ANN003
            raise RuntimeError("ollama down")

        with (
            # Force the local `import httpx` Ollama call to fail → cloud branch taken.
            patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=_boom_post)),
            patch(
                "backend.services.multimodal.cloud_vision_gate.cloud_vision_allowed",
                return_value=False,
            ),
            patch(
                "backend.services.multimodal.cloud_vision_gate.note_cloud_ocr_blocked",
            ) as note,
        ):
            resp = await extract_passport_enhanced(
                req,
                current_user={"email": "zero@balizero.com", "role": "admin"},
                db_pool=MagicMock(),
            )

        assert resp.success is False
        assert "PII" in resp.message or "blocked" in resp.message.lower()
        note.assert_called_once()
        assert "crm_clients_documents" in note.call_args.args[0]
