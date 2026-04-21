"""Tests for the shared internal email client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.services.internal_email import send_internal_email


def _make_mock_client() -> tuple:
    """Mock the persistent httpx client returned by get_email_client().

    2026-04-21: refactored from per-call httpx.AsyncClient() to a shared
    persistent client (Golden Rule #10). The mock now represents the
    bare client object, not a context-manager factory.
    """
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client, mock_response


class TestSendInternalEmail:
    @pytest.mark.asyncio
    async def test_happy_path_with_cc(self) -> None:
        mock_client, _ = _make_mock_client()

        with patch(
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            await send_internal_email(
                to="kadek.tax@balizero.com",
                subject="Hello",
                body="<p>body</p>",
                cc=["zero@balizero.com", "asya@balizero.com"],
                log_context="test req=1",
            )

        assert mock_client.post.call_count == 1
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["to"] == "kadek.tax@balizero.com"
        assert payload["cc"] == "zero@balizero.com, asya@balizero.com"
        assert payload["subject"] == "Hello"
        assert payload["body"] == "<p>body</p>"

    @pytest.mark.asyncio
    async def test_omits_cc_when_none(self) -> None:
        mock_client, _ = _make_mock_client()

        with patch(
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            await send_internal_email(
                to="solo@balizero.com",
                subject="No CC",
                body="<p>body</p>",
                cc=None,
            )

        payload = mock_client.post.call_args.kwargs["json"]
        assert "cc" not in payload

    @pytest.mark.asyncio
    async def test_omits_cc_when_empty_list(self) -> None:
        mock_client, _ = _make_mock_client()

        with patch(
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            await send_internal_email(
                to="solo@balizero.com",
                subject="Empty CC",
                body="<p>body</p>",
                cc=[],
            )

        payload = mock_client.post.call_args.kwargs["json"]
        assert "cc" not in payload

    @pytest.mark.asyncio
    async def test_payload_validates_against_send_email_request_schema(
        self,
    ) -> None:
        """Regression: payload must match the receiving Pydantic model
        (commits 08c4df17c, 3dffb6e6e). The contract this module exists
        to enforce."""
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
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            await send_internal_email(
                to="kadek.tax@balizero.com",
                subject="Schema test",
                body="<p>body</p>",
                cc=["zero@balizero.com", "asya@balizero.com"],
            )

        # Will raise pydantic.ValidationError if schema drifts
        SendEmailRequest(**captured["payload"])

    @pytest.mark.asyncio
    async def test_http_error_is_swallowed(self) -> None:
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
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            # Must not raise
            await send_internal_email(
                to="x@balizero.com",
                subject="x",
                body="<p>x</p>",
            )

    @pytest.mark.asyncio
    async def test_network_error_is_swallowed(self) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused"),
        )

        with patch(
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            # Must not raise
            await send_internal_email(
                to="x@balizero.com",
                subject="x",
                body="<p>x</p>",
            )

    @pytest.mark.asyncio
    async def test_raise_on_failure_propagates_http_error(self) -> None:
        """Used by callers with fallback transport (e.g. Zoho)."""
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
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await send_internal_email(
                    to="x@balizero.com",
                    subject="x",
                    body="<p>x</p>",
                    raise_on_failure=True,
                )

    @pytest.mark.asyncio
    async def test_raise_on_failure_propagates_network_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused"),
        )

        with patch(
            "backend.app.services.internal_email.get_email_client",
            new=AsyncMock(return_value=mock_client),
        ):
            with pytest.raises(httpx.ConnectError):
                await send_internal_email(
                    to="x@balizero.com",
                    subject="x",
                    body="<p>x</p>",
                    raise_on_failure=True,
                )
