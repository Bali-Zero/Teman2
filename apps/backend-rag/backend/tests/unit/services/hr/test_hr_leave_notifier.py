"""Tests for HR leave notifier — Brevo HTTP, fire-and-forget semantics."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.services.hr.hr_leave_notifier import (
    notify_leave_request_pending,
)


@pytest.fixture
def sample_call_args() -> dict:
    return {
        "request_id": 42,
        "requester_email": "kadek.tax@balizero.com",
        "requester_name": "Kadek",
        "leave_type_name": "Annual Leave",
        "start_date": date(2026, 12, 15),
        "end_date": date(2026, 12, 19),
        "total_days": 5,
        "reason": "Family visit",
    }


class TestNotifyLeaveRequestPending:
    @pytest.mark.asyncio
    async def test_happy_path_posts_with_correct_recipients(
        self, sample_call_args: dict,
    ) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        assert mock_client.post.call_count == 1
        call_kwargs = mock_client.post.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["to"] == "tax@balizero.com"
        assert payload["cc"] == "zero@balizero.com, asya@balizero.com"
        assert "Kadek" in payload["subject"]
        assert "5 days" in payload["subject"]
        assert "Annual Leave" in payload["body"]
        assert "2026-12-15 → 2026-12-19" in payload["body"]
        assert "Family visit" in payload["body"]

    @pytest.mark.asyncio
    async def test_single_day_range_uses_singular_day(
        self, sample_call_args: dict,
    ) -> None:
        sample_call_args["total_days"] = 1
        sample_call_args["start_date"] = date(2026, 12, 15)
        sample_call_args["end_date"] = date(2026, 12, 15)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        payload = mock_client.post.call_args.kwargs["json"]
        assert "1 day" in payload["subject"]
        assert "1 days" not in payload["subject"]
        # Single date means no arrow
        assert "2026-12-15" in payload["body"]
        assert "→" not in payload["body"]

    @pytest.mark.asyncio
    async def test_reason_none_omits_reason_block(
        self, sample_call_args: dict,
    ) -> None:
        sample_call_args["reason"] = None

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        payload = mock_client.post.call_args.kwargs["json"]
        assert "Reason:" not in payload["body"]

    @pytest.mark.asyncio
    async def test_http_error_is_swallowed(self, sample_call_args: dict) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
        )
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # Must not raise
            await notify_leave_request_pending(**sample_call_args)

    @pytest.mark.asyncio
    async def test_network_error_is_swallowed(
        self, sample_call_args: dict,
    ) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused"),
        )

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # Must not raise
            await notify_leave_request_pending(**sample_call_args)

    @pytest.mark.asyncio
    async def test_payload_validates_against_send_email_request_schema(
        self, sample_call_args: dict,
    ) -> None:
        """Regression: cc must be comma-separated str, not list (commit 08c4df17c)."""
        from backend.app.modules.notifications.router import SendEmailRequest

        captured: dict = {}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        async def fake_post(url: str, **kwargs: object) -> MagicMock:
            captured["payload"] = kwargs["json"]
            return mock_response

        mock_client.post = AsyncMock(side_effect=fake_post)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        # Will raise pydantic.ValidationError if schema drifts
        SendEmailRequest(**captured["payload"])

    @pytest.mark.asyncio
    async def test_html_injection_in_reason_is_escaped(
        self, sample_call_args: dict,
    ) -> None:
        """Regression: free-text reason must not break HTML structure."""
        sample_call_args["reason"] = "</p><script>alert(1)</script>"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "backend.app.services.hr.hr_leave_notifier.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await notify_leave_request_pending(**sample_call_args)

        body = mock_client.post.call_args.kwargs["json"]["body"]
        assert "<script>" not in body
        assert "&lt;script&gt;" in body
