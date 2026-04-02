"""Tests for OCR dispatcher service — routes documents to correct OCR handler."""

from unittest.mock import AsyncMock, patch

import pytest


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


@pytest.mark.asyncio
async def test_dispatch_no_match():
    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    result = await dispatch_ocr_by_folder(
        db_pool=AsyncMock(), client_id=1, file_id="f1",
        folder_name="99_Misc", filename="random_letter.pdf",
    )
    assert result["dispatched"] is False
