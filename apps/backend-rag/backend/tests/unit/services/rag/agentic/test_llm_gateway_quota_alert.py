"""
Unit tests for the Gemini quota-exhaustion operator alert (spec item O1).

Context (2026-07-22 real incident): the Gemini prepay balance hit zero, so
BOTH the primary AND fallback tiers returned 429/RESOURCE_EXHAUSTED. The
agentic LLM could not drive tool retrieval, the WhatsApp bot silently
abstained on every question for hours, and nobody was paged — the failure
was found by accident. The architecture is deliberately fail-closed on
Gemini (no external LLM fallback), so the operator alert IS the mitigation.

These tests cover ``LLMGateway._call_model``'s two raw google-genai SDK call
sites (``client._client.aio.models.generate_content`` — chat-history branch
and no-history/"fallback" branch) and assert:

- GUILT: a real ``google.genai.errors.ClientError`` shaped like Gemini's
  429/RESOURCE_EXHAUSTED response triggers exactly one alert, on both call
  sites, and the original exception still propagates unchanged.
- INNOCENCE: a generic error (ValueError, a 503 ServerError, a timeout)
  triggers NO alert. A second quota error for the same subtype fired
  immediately after the first (inside the AlertService cooldown window)
  triggers NO second Telegram send. Alert-sending failures never break the
  original exception's propagation.
- The exception class is matched via the SDK's structured ``code``/``status``
  attributes (not a bare substring on one sentence — cicatrix scar family #3,
  guard-over-match), and the message text is used only to distinguish the
  balance-depleted vs rate-limited subtype for the alert text.
- No PII (user query text, phone number, client data) ever reaches the
  alert metadata.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core.exceptions import ResourceExhausted
from google.genai.errors import ClientError, ServerError

from backend.services.monitoring.alert_service import AlertLevel
from backend.services.rag.agentic.llm_gateway import LLMGateway


def _make_fake_response(prompt_tokens: int = 42, completion_tokens: int = 7) -> SimpleNamespace:
    """Build a fake google-genai response with usage_metadata + text."""
    return SimpleNamespace(
        text="Hello from Gemini",
        candidates=[],
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_tokens,
            candidates_token_count=completion_tokens,
        ),
    )


def _make_client_error(
    message: str = "Resource has been exhausted (e.g. check quota).",
    status: str = "RESOURCE_EXHAUSTED",
    code: int = 429,
) -> ClientError:
    """Build a real google.genai.errors.ClientError shaped like the SDK's
    actual 429/RESOURCE_EXHAUSTED response body (verified live against the
    installed google-genai==2.7.0: ClientError(code, response_json).status/
    .message/.code are populated from response_json["error"])."""
    return ClientError(code, {"error": {"status": status, "message": message, "code": code}})


def _make_server_error(message: str = "model overloaded", status: str = "UNAVAILABLE") -> ServerError:
    return ServerError(503, {"error": {"status": status, "message": message, "code": 503}})


@pytest.fixture
def gateway_with_raw_client():
    """LLMGateway whose genai client exposes the raw SDK call path used by
    _call_model (client._client.aio.models.generate_content)."""
    with patch("backend.services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client._client.aio.models.generate_content = AsyncMock(
            return_value=_make_fake_response(),
        )
        mock_get.return_value = mock_client
        gw = LLMGateway()
        gw._available = True
        yield gw, mock_client


@pytest.fixture
def mock_alert_service():
    """Patch the alert service at its source module (llm_gateway imports it
    lazily inside the alert helper, same pattern as the cost-recorder import
    in _call_model — see test_llm_gateway_cost_recorder.py)."""
    with patch("backend.services.monitoring.alert_service.get_alert_service") as mock_get_alert:
        mock_service = MagicMock()
        mock_service.send_alert = AsyncMock()
        mock_get_alert.return_value = mock_service
        yield mock_service


# ============================================================================
# GUILT — real 429/RESOURCE_EXHAUSTED fires exactly one alert
# ============================================================================


class TestQuotaExhaustionAlertsGuilt:
    @pytest.mark.asyncio
    async def test_no_history_branch_triggers_one_alert_and_reraises(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        """chat=None takes the 'Fallback: Build content directly' raw call
        site (~line 846) — must alert exactly once and re-raise the SAME
        exception instance unchanged."""
        gateway, mock_client = gateway_with_raw_client
        err = _make_client_error()
        mock_client._client.aio.models.generate_content = AsyncMock(side_effect=err)

        with pytest.raises(ClientError) as exc_info:
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        assert exc_info.value is err  # unchanged propagation, not re-wrapped
        mock_alert_service.send_alert.assert_awaited_once()
        kwargs = mock_alert_service.send_alert.call_args.kwargs
        assert kwargs["level"] == AlertLevel.CRITICAL
        assert kwargs["metadata"]["model"] == "gemini-3-flash"
        assert kwargs["metadata"]["error_code"] == 429
        assert kwargs["metadata"]["error_status"] == "RESOURCE_EXHAUSTED"

    @pytest.mark.asyncio
    async def test_chat_history_branch_triggers_one_alert_and_reraises(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        """chat with a .history attribute takes the chat-session raw call
        site (~line 737) — must also alert exactly once."""
        gateway, mock_client = gateway_with_raw_client
        err = _make_client_error()
        mock_client._client.aio.models.generate_content = AsyncMock(side_effect=err)
        chat = SimpleNamespace(history=[])

        with pytest.raises(ClientError) as exc_info:
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=chat, message="hi", images=None,
            )

        assert exc_info.value is err
        mock_alert_service.send_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_legacy_api_core_resource_exhausted_also_alerts(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        """Defense-in-depth: google.api_core.exceptions.ResourceExhausted
        (the class this file already imports/catches elsewhere in the
        fallback cascade) must ALSO be recognised as quota-exhaustion, not
        just the new SDK's google.genai.errors.ClientError."""
        gateway, mock_client = gateway_with_raw_client
        err = ResourceExhausted("429 Resource has been exhausted")
        mock_client._client.aio.models.generate_content = AsyncMock(side_effect=err)

        with pytest.raises(ResourceExhausted):
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        mock_alert_service.send_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_balance_depleted_message_sets_that_subtype(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        """The 2026-07-22 real incident's exact phrasing must classify as
        balance depletion, not a transient per-minute rate limit."""
        gateway, mock_client = gateway_with_raw_client
        err = _make_client_error(message="prepayment credits are depleted")
        mock_client._client.aio.models.generate_content = AsyncMock(side_effect=err)

        with pytest.raises(ClientError):
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        kwargs = mock_alert_service.send_alert.call_args.kwargs
        assert kwargs["metadata"]["subtype"] == "balance_depleted"
        assert "depleted" in kwargs["message"].lower() or "balance" in kwargs["message"].lower()

    @pytest.mark.asyncio
    async def test_rate_limit_message_sets_that_subtype(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        gateway, mock_client = gateway_with_raw_client
        err = _make_client_error(
            message="Quota exceeded for quota metric 'Generate content requests per minute'",
        )
        mock_client._client.aio.models.generate_content = AsyncMock(side_effect=err)

        with pytest.raises(ClientError):
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        kwargs = mock_alert_service.send_alert.call_args.kwargs
        assert kwargs["metadata"]["subtype"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_alert_metadata_carries_no_pii(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        """Hard legal boundary (UU PDP): the alert must never carry the
        user's query text, phone number, or any client data — only model
        name, error class, and counts."""
        gateway, mock_client = gateway_with_raw_client
        err = _make_client_error()
        mock_client._client.aio.models.generate_content = AsyncMock(side_effect=err)

        with pytest.raises(ClientError):
            await gateway._call_model(
                "gemini-3-flash",
                with_tools=False,
                chat=None,
                message="+62 812-3456-7890 my passport number is A1234567",
                images=None,
            )

        kwargs = mock_alert_service.send_alert.call_args.kwargs
        serialized = str(kwargs["metadata"]) + kwargs["message"] + kwargs["title"]
        assert "+62 812-3456-7890" not in serialized
        assert "A1234567" not in serialized
        assert set(kwargs["metadata"].keys()) == {
            "model", "error_class", "error_code", "error_status", "subtype",
        }


# ============================================================================
# INNOCENCE — non-quota errors never alert; alerting never breaks the path
# ============================================================================


class TestQuotaExhaustionAlertsInnocence:
    @pytest.mark.asyncio
    async def test_generic_value_error_triggers_no_alert(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        gateway, mock_client = gateway_with_raw_client
        mock_client._client.aio.models.generate_content = AsyncMock(
            side_effect=ValueError("something unrelated broke"),
        )

        with pytest.raises(ValueError):
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        mock_alert_service.send_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_server_error_503_triggers_no_alert(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        """A 5xx ServerError (model overloaded) is a DIFFERENT failure class
        from 429 quota exhaustion — must not be swept in by an over-broad
        guard (cicatrix scar family #3)."""
        gateway, mock_client = gateway_with_raw_client
        mock_client._client.aio.models.generate_content = AsyncMock(
            side_effect=_make_server_error(),
        )

        with pytest.raises(ServerError):
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        mock_alert_service.send_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_timeout_triggers_no_alert(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        gateway, mock_client = gateway_with_raw_client
        mock_client._client.aio.models.generate_content = AsyncMock(
            side_effect=TimeoutError("deadline exceeded"),
        )

        with pytest.raises(TimeoutError):
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        mock_alert_service.send_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_alert_send_failure_does_not_break_original_exception(
        self, gateway_with_raw_client, mock_alert_service,
    ):
        """Best-effort contract: if send_alert itself raises, the ORIGINAL
        429 must still propagate unchanged — never swallowed, never
        replaced by the alerting error."""
        gateway, mock_client = gateway_with_raw_client
        err = _make_client_error()
        mock_client._client.aio.models.generate_content = AsyncMock(side_effect=err)
        mock_alert_service.send_alert.side_effect = RuntimeError("telegram is down")

        with pytest.raises(ClientError) as exc_info:
            await gateway._call_model(
                "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
            )

        assert exc_info.value is err

    @pytest.mark.asyncio
    async def test_second_quota_alert_within_cooldown_is_suppressed(
        self, gateway_with_raw_client,
    ):
        """End-to-end dedup: reuses the REAL AlertService (not a mock) so its
        existing escalating-cooldown/dedup logic actually runs. Simulates the
        2026-07-22 shape — primary tier AND fallback tier both hit quota in
        the same request window — and asserts only ONE Telegram send fires.

        Limitation stated per mandate requirement #3: AlertService's cooldown
        state (`_last_alert_time`/`_alert_repeat`) is an in-memory dict on the
        process-local singleton. Fly runs this app with `--workers 1`, so a
        single machine dedups correctly; if Fly ever scales to N concurrent
        machines, each machine's own singleton could independently alert once
        within the same cooldown window (up to N alerts, not N*requests).
        """
        gateway, mock_client = gateway_with_raw_client
        mock_client._client.aio.models.generate_content = AsyncMock(
            side_effect=_make_client_error(),
        )

        from backend.services.monitoring.alert_service import AlertService

        real_service = AlertService()
        real_service.enable_telegram = True
        real_service.telegram_bot_token = "fake-token-for-test"
        real_service.telegram_admin_chat_id = "12345"

        with patch(
            "backend.services.monitoring.alert_service.get_alert_service",
            return_value=real_service,
        ), patch.object(
            real_service, "_send_telegram_alert", new_callable=AsyncMock,
        ) as mock_send_telegram:
            for _ in range(2):  # primary tier fails, then fallback tier fails
                with pytest.raises(ClientError):
                    await gateway._call_model(
                        "gemini-3-flash", with_tools=False, chat=None, message="hi", images=None,
                    )

        mock_send_telegram.assert_awaited_once()
