"""Tests for HR leave RBAC helper — supervisor delegation + self-approval ban."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.app.routers.hr import _require_can_review_leave


def _mock_service_returning_request(requester_email: str) -> Any:
    service = AsyncMock()
    service.get_leave_request = AsyncMock(return_value={
        "id": 1,
        "requester_email": requester_email,
        "requester_name": "Test Employee",
        "status": "pending",
    })
    return service


class TestRequireCanReviewLeave:
    # ─── HR admins (universal access) ────────────────────────────────
    @pytest.mark.asyncio
    async def test_zero_approves_anyone(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "zero@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    @pytest.mark.asyncio
    async def test_asya_approves_anyone(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "asya@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    @pytest.mark.asyncio
    async def test_ruslana_approves_dea(self) -> None:
        service = _mock_service_returning_request("dea@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "ruslana@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    # ─── Supervisor delegation ───────────────────────────────────────
    @pytest.mark.asyncio
    async def test_veronika_approves_kadek(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "tax@balizero.com", "role": "member"},
            1,
        )
        assert req["id"] == 1

    @pytest.mark.asyncio
    async def test_veronika_cannot_approve_dea(self) -> None:
        service = _mock_service_returning_request("dea@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "tax@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_kadek_cannot_approve_angel(self) -> None:
        service = _mock_service_returning_request("angel.tax@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "kadek.tax@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    # ─── Self-approval forbidden (even for HR admins) ────────────────
    @pytest.mark.asyncio
    async def test_asya_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("asya@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "asya@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_zero_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("zero@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "zero@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_ruslana_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("ruslana@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "ruslana@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_veronika_cannot_self_approve(self) -> None:
        service = _mock_service_returning_request("tax@balizero.com")
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "tax@balizero.com", "role": "member"},
                1,
            )
        assert exc.value.status_code == 403

    # ─── Not found ───────────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_not_found_returns_404(self) -> None:
        service = AsyncMock()
        service.get_leave_request = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await _require_can_review_leave(
                service,
                {"email": "zero@balizero.com"},
                999,
            )
        assert exc.value.status_code == 404

    # ─── Email normalization ─────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_user_email_case_insensitive(self) -> None:
        service = _mock_service_returning_request("kadek.tax@balizero.com")
        req = await _require_can_review_leave(
            service,
            {"email": "  TAX@BALIZERO.COM  ", "role": "member"},
            1,
        )
        assert req["id"] == 1
