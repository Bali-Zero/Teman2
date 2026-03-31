"""Tests for legal_config and LegalFullIngestionWorker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest_plugins = ("anyio",)

from backend.core.legal_config import (
    VALID_TIPO,
    resolve_nb_notebook_id,
    resolve_nb_target,
)


def test_resolve_nb_target_auto_map():
    assert resolve_nb_target("PP", None) == "NB-3"
    assert resolve_nb_target("PMK", None) == "NB-4"
    assert resolve_nb_target("SE", None) == "NB-4"


def test_resolve_nb_target_override():
    assert resolve_nb_target("PP", "NB-5") == "NB-5"


def test_resolve_nb_target_invalid_override_falls_back():
    # Invalid override -> use auto-map
    assert resolve_nb_target("PP", "NB-99") == "NB-3"


def test_resolve_nb_notebook_id():
    nb_id = resolve_nb_notebook_id("NB-3")
    assert nb_id == "933509f9-1561-403d-bd44-4a7a67a36df2"


def test_resolve_nb_notebook_id_unknown():
    assert resolve_nb_notebook_id("NB-99") is None


def test_valid_tipo_contains_expected():
    assert "PP" in VALID_TIPO
    assert "PMK" in VALID_TIPO
    assert "INVALID" not in VALID_TIPO


@pytest.mark.anyio
async def test_update_job_builds_correct_sql():
    """_update_job generates valid parameterized SQL."""
    conn = AsyncMock()
    from backend.services.ingestion.legal_full_ingestion_worker import _update_job
    await _update_job(conn, "test-uuid", status="qdrant_done", qdrant_chunks=42)
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert "status" in call_args[0]
    assert "qdrant_done" in call_args
    assert 42 in call_args


@pytest.mark.anyio
async def test_process_one_job_empty_queue():
    """Worker does nothing when queue is empty (_claim_job returns None)."""
    from contextlib import asynccontextmanager

    import backend.services.ingestion.legal_full_ingestion_worker as worker_mod
    from backend.services.ingestion.legal_full_ingestion_worker import _process_one_job

    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=False)))

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    db_pool = MagicMock()
    db_pool.acquire = fake_acquire

    with patch.object(worker_mod, "_claim_job", new=AsyncMock(return_value=None)):
        await _process_one_job(db_pool, MagicMock())
        # No exception raised — queue empty is handled gracefully
