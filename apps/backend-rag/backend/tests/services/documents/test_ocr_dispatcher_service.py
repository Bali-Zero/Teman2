"""Tests for OCR dispatcher service — routes documents to correct OCR handler.

Two-tier dispatch coverage:
  - Tier 1: filename / folder keyword match (fast path, no API call)
  - Tier 2: Gemini Vision content classifier fallback (when filename
            doesn't match — verifies classifier triggers, confidence
            threshold, handler re-routing, and graceful failure modes)
"""

from unittest.mock import AsyncMock, patch

import pytest

# ─── Tier 1: filename / folder keyword match ──────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_passport():
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
        return_value={"success": True},
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="00_Profile", filename="passport_scan.pdf",
        )
        assert result["dispatched"] is True
        assert result["handler"] == "passport"
        assert result["tier"] == "filename"


@pytest.mark.asyncio
async def test_dispatch_visa():
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_ocr_visa",
        new_callable=AsyncMock,
        return_value={"success": True},
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="01_Immigration", filename="kitas_extension.pdf",
        )
        assert result["dispatched"] is True
        assert result["handler"] == "visa"
        assert result["tier"] == "filename"


@pytest.mark.asyncio
async def test_dispatch_nib():
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_ocr_nib",
        new_callable=AsyncMock,
        return_value={"success": True},
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="02_Company", filename="NIB_document.pdf",
        )
        assert result["dispatched"] is True
        assert result["handler"] == "nib"
        assert result["tier"] == "filename"


@pytest.mark.asyncio
async def test_dispatch_npwp():
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_ocr_npwp",
        new_callable=AsyncMock,
        return_value={"success": True},
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="03_Tax", filename="npwp_card.pdf",
        )
        assert result["dispatched"] is True
        assert result["handler"] == "npwp"
        assert result["tier"] == "filename"


# ─── Tier 2: content classifier fallback ──────────────────────────────────


@pytest.mark.asyncio
async def test_content_classifier_high_confidence_passport():
    """Filename gives no signal; classifier identifies passport with high
    confidence → dispatcher must run the passport OCR handler."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    classifier_result = {
        "document_type": "passport",
        "confidence": 0.92,
        "language": "en",
        "reasoning": "MRZ + 'PASSPORT' header detected",
    }

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value=classifier_result,
    ), patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
        return_value={"success": True, "extracted": {"passport_number": "AB123456"}},
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="99_Misc", filename="IMG_2847.pdf",
        )
        assert result["dispatched"] is True
        assert result["handler"] == "passport"
        assert result["tier"] == "content"
        assert result["classifier"]["document_type"] == "passport"


@pytest.mark.asyncio
async def test_content_classifier_low_confidence_skipped():
    """Classifier returns a known type but confidence below threshold →
    dispatcher must NOT trigger any handler (avoid bad-data writes)."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    classifier_result = {
        "document_type": "passport",
        "confidence": 0.55,  # below 0.70 threshold
        "language": "en",
        "reasoning": "low quality scan, partial visibility",
    }

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value=classifier_result,
    ), patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
    ) as mock_passport:
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="99_Misc", filename="blurry_scan.pdf",
        )
        assert result["dispatched"] is False
        assert result["tier"] == "content"
        assert result["classifier"]["confidence"] == 0.55
        # Most important: handler must NOT have been called
        mock_passport.assert_not_called()


@pytest.mark.asyncio
async def test_content_classifier_unknown_type():
    """Classifier returns 'unknown' → no handler triggered, returns False."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    classifier_result = {
        "document_type": "unknown",
        "confidence": 0.20,
        "language": "unknown",
        "reasoning": "unable to classify",
    }

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value=classifier_result,
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="99_Misc", filename="random_doc.pdf",
        )
        assert result["dispatched"] is False
        assert result["tier"] == "content"


@pytest.mark.asyncio
async def test_content_classifier_recognized_but_no_handler():
    """Classifier identifies akta with high confidence, but akta handler is
    not yet implemented (Phase 2). Must return dispatched=False but record
    the classification for audit/cataloging."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    classifier_result = {
        "document_type": "akta",
        "confidence": 0.88,
        "language": "id",
        "reasoning": "Akta Pendirian header + notarial seal visible",
    }

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value=classifier_result,
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="02_Company", filename="document_001.pdf",
        )
        assert result["dispatched"] is False
        assert result["tier"] == "content"
        assert result["classifier"]["document_type"] == "akta"
        assert result["classifier"]["confidence"] == 0.88


@pytest.mark.asyncio
async def test_content_classifier_error_graceful():
    """Classifier itself raises an error (Drive download fail, Vision API
    timeout, etc.) → dispatcher must return False without crashing."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value={"error": "Drive 503 timeout"},
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="99_Misc", filename="anything.pdf",
        )
        assert result["dispatched"] is False
        assert result["tier"] == "content"
        assert "error" in result["classifier"]


@pytest.mark.asyncio
async def test_content_classifier_handler_failure_recorded():
    """Classifier matches passport, handler runs but raises → dispatcher
    must return False with handler_error captured for observability."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    classifier_result = {
        "document_type": "passport",
        "confidence": 0.95,
        "language": "en",
        "reasoning": "passport detected",
    }

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value=classifier_result,
    ), patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
        side_effect=RuntimeError("OCR pipeline crashed"),
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="99_Misc", filename="IMG.pdf",
        )
        assert result["dispatched"] is False
        assert result["tier"] == "content"
        assert "handler_error" in result
        assert "OCR pipeline crashed" in result["handler_error"]


@pytest.mark.asyncio
async def test_dispatch_filename_priority_over_content():
    """If filename matches Tier 1, content classifier must NOT be called
    (cost optimization — Tier 1 is free, Tier 2 costs a Vision API call)."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
    ) as mock_classifier, patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
        return_value={"success": True},
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="00_Profile", filename="passport.pdf",
        )
        assert result["tier"] == "filename"
        # Critical: classifier (expensive) must NOT have been called
        mock_classifier.assert_not_called()


# ─── Original no-match test, updated for Tier 2 ──────────────────────────


@pytest.mark.asyncio
async def test_dispatch_no_match_falls_through_to_classifier():
    """File with no Tier 1 match falls through to Tier 2. Verify the
    classifier is invoked. (Old test ran with no mocks and would now
    perform real Drive + Vision calls — replaced with mocked classifier
    that returns 'unknown' so the dispatcher returns False as before.)"""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value={
            "document_type": "unknown",
            "confidence": 0.30,
            "language": "unknown",
            "reasoning": "no clear signal",
        },
    ) as mock_classifier:
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="99_Misc", filename="random_letter.pdf",
        )
        assert result["dispatched"] is False
        # Tier 2 must have been reached (filename had no match)
        mock_classifier.assert_called_once_with("f1")


# ─── PR-A3: KG hook (feature-flag) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_kg_hook_off_by_default():
    """With CRM_KG_ENABLED unset, dispatcher must NOT call kg_link_document.
    Critical for backward compat: deployed before flag is flipped."""
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
        return_value={"success": True, "extracted": {"passport_number": "AB123"}},
    ), patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
    ) as mock_kg:
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="00_Profile", filename="passport.pdf",
        )
        assert result["dispatched"] is True
        # KG link NOT called because flag is off
        mock_kg.assert_not_called()


@pytest.mark.asyncio
async def test_kg_hook_fires_when_flag_on(monkeypatch):
    """With CRM_KG_ENABLED=true, dispatcher must call kg_link_document
    after successful OCR with the extracted fields."""
    monkeypatch.setenv("CRM_KG_ENABLED", "true")
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    extracted = {"passport_number": "AB123", "nationality": "RUS"}
    ocr_result = {"success": True, "extracted": extracted}

    with patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
        return_value=ocr_result,
    ), patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
        return_value={"ok": True, "nodes": 3, "edges": 2},
    ) as mock_kg:
        await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=42, file_id="drive_x",
            folder_name="00_Profile", filename="passport.pdf",
        )

        mock_kg.assert_called_once()
        call_kwargs = mock_kg.call_args.kwargs
        assert call_kwargs["file_id"] == "drive_x"
        assert call_kwargs["client_id"] == 42
        assert call_kwargs["document_type"] == "passport"
        assert call_kwargs["extracted_fields"] == extracted
        assert call_kwargs["filename"] == "passport.pdf"


@pytest.mark.asyncio
async def test_kg_hook_swallows_exceptions(monkeypatch):
    """KG-link failure must NOT break the dispatcher return path. The
    OCR caller still gets dispatched=True with the OCR result intact."""
    monkeypatch.setenv("CRM_KG_ENABLED", "1")
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    with patch(
        "backend.app.routers.crm_enhanced._auto_ocr_passport",
        new_callable=AsyncMock,
        return_value={"success": True, "extracted": {"passport_number": "AB"}},
    ), patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
        side_effect=RuntimeError("DB pool exhausted"),
    ):
        result = await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=1, file_id="f1",
            folder_name="00_Profile", filename="passport.pdf",
        )
        # Despite KG crash, dispatcher returns success
        assert result["dispatched"] is True
        assert result["handler"] == "passport"


@pytest.mark.asyncio
async def test_kg_hook_after_content_tier_dispatch(monkeypatch):
    """Tier-2 content-classifier dispatch must also fire the KG hook."""
    monkeypatch.setenv("CRM_KG_ENABLED", "true")
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    classifier_result = {
        "document_type": "npwp",
        "confidence": 0.93,
        "language": "id",
        "reasoning": "NPWP card detected",
    }
    ocr_result = {"success": True, "extracted": {"npwp": "01.234.567.8-901.000"}}

    with patch(
        "backend.app.routers.crm_enhanced._auto_classify_content",
        new_callable=AsyncMock,
        return_value=classifier_result,
    ), patch(
        "backend.app.routers.crm_enhanced._auto_ocr_npwp",
        new_callable=AsyncMock,
        return_value=ocr_result,
    ), patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
        return_value={"ok": True, "nodes": 3, "edges": 2},
    ) as mock_kg:
        await dispatch_ocr_by_folder(
            db_pool=AsyncMock(), client_id=42, file_id="drive_x",
            folder_name="99_Misc", filename="IMG_5555.pdf",
        )

        mock_kg.assert_called_once()
        assert mock_kg.call_args.kwargs["document_type"] == "npwp"
        assert mock_kg.call_args.kwargs["extracted_fields"]["npwp"] == "01.234.567.8-901.000"


@pytest.mark.asyncio
async def test_kg_flag_recognizes_truthy_values(monkeypatch):
    """Flag accepts true/1/yes/on (case-insensitive)."""
    from backend.services.documents.ocr_dispatcher_service import _kg_enabled

    for val in ("true", "TRUE", "True", "1", "yes", "YES", "on", "On"):
        monkeypatch.setenv("CRM_KG_ENABLED", val)
        assert _kg_enabled() is True, f"failed for {val!r}"

    for val in ("false", "0", "no", "off", "", "anything", "TRUEISH"):
        monkeypatch.setenv("CRM_KG_ENABLED", val)
        assert _kg_enabled() is False, f"failed for {val!r}"

    monkeypatch.delenv("CRM_KG_ENABLED", raising=False)
    assert _kg_enabled() is False
