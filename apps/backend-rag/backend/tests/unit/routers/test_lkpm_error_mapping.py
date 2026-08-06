"""Client-safe error mapping for the portal LKPM submission route."""

import inspect
import logging
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.app.models.lkpm import LKPMClientSubmission
from backend.app.routers import lkpm as lkpm_router


def test_lkpm_router_never_serializes_raw_exception_detail() -> None:
    """Keep raw exception strings behind the client boundary across the router."""
    source = inspect.getsource(lkpm_router)

    assert "detail=str(" not in source


@pytest.mark.asyncio
async def test_submit_data_redacts_internal_failure_and_correlates_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An arbitrary service exception must never cross the client boundary."""
    marker = "SYNTHETIC_INTERNAL_DB_MARKER"
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(return_value=42),
        submit_form_data_for_client=AsyncMock(
            side_effect=RuntimeError(marker),
        ),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)
    submission = LKPMClientSubmission(client_id=0, quarter="Q1", year=2026)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await lkpm_router.submit_data(
                submission=submission,
                current_user={
                    "role": "client",
                    "user_id": "synthetic-user",
                    "email": "synthetic@example.invalid",
                },
                db_pool=object(),
            )

    assert exc_info.value.status_code == 500
    detail = str(exc_info.value.detail)
    match = re.fullmatch(
        r"LKPM submission temporarily unavailable\. Reference: ([0-9a-f]{32})",
        detail,
    )
    assert match is not None
    assert marker not in detail
    assert marker not in caplog.text
    assert f"error_ref={match.group(1)}" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
