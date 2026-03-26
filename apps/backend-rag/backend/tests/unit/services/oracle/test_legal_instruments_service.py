"""Tests for LegalInstrumentsService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.oracle.legal_instruments_service import LegalInstrumentsService


@pytest.fixture
def mock_pool() -> MagicMock:
    pool = MagicMock()
    pool.acquire = MagicMock()
    return pool


@pytest.fixture
def service(mock_pool: MagicMock) -> LegalInstrumentsService:
    return LegalInstrumentsService(db_pool=mock_pool)


@pytest.mark.asyncio
async def test_get_active_instruments_for_domain(
    service: LegalInstrumentsService, mock_pool: MagicMock
) -> None:
    mock_rows = [
        {
            "instrument_id": "UU-6-2011",
            "status": "active",
            "tier": 0,
            "domain": "immigration",
            "title": "UU Keimigrasian",
        },
        {
            "instrument_id": "Permenkumham-22-2023",
            "status": "partially_superseded",
            "tier": 1,
            "domain": "immigration",
            "title": "Permenkumham Visa",
        },
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    results = await service.get_active_instruments_for_domain("immigration")

    assert len(results) == 2
    assert results[0]["instrument_id"] == "UU-6-2011"
    mock_conn.fetch.assert_called_once()
    call_args = str(mock_conn.fetch.call_args)
    assert "immigration" in call_args


@pytest.mark.asyncio
async def test_mark_uploaded_to_nb(service: LegalInstrumentsService, mock_pool: MagicMock) -> None:
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    await service.mark_uploaded_to_nb("UU-6-2011")

    mock_conn.execute.assert_called_once()
    call_sql = mock_conn.execute.call_args[0][0]
    assert "nb_uploaded" in call_sql
    assert "UU-6-2011" in str(mock_conn.execute.call_args)


@pytest.mark.asyncio
async def test_get_conflict_notes_for_domain(
    service: LegalInstrumentsService, mock_pool: MagicMock
) -> None:
    mock_rows = [
        {
            "instrument_id": "Permenkumham-22-2023",
            "conflict_note": "Superseded by Permen Imipas 3/2025",
            "revoked_by": "Permen-Imipas-3-2025",
            "status": "partially_superseded",
        }
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    notes = await service.get_conflict_notes_for_domain("immigration")

    assert len(notes) == 1
    assert notes[0]["conflict_note"] == "Superseded by Permen Imipas 3/2025"


@pytest.mark.asyncio
async def test_get_not_yet_uploaded(service: LegalInstrumentsService, mock_pool: MagicMock) -> None:
    mock_rows = [
        {
            "instrument_id": "UU-6-2011",
            "instrument_type": "UU",
            "title": "UU Keimigrasian",
            "source_file": None,
            "source_url": "https://...",
        }
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    results = await service.get_not_yet_uploaded("immigration")

    assert len(results) == 1
    assert results[0]["instrument_id"] == "UU-6-2011"
