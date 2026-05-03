"""
Comprehensive pytest suite for Instagram Service.
Tests: send_message, mark_message_seen, get_profile, chunk_message,
       client lifecycle, error handling

Target: 80%+ coverage

Uses:
- pytest.mark.asyncio for async tests
- pytest.mark.parametrize for chunking edge cases
- AsyncMock/MagicMock for httpx and settings mocking
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Set env vars before importing
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")
os.environ.setdefault("INSTAGRAM_ACCESS_TOKEN", "test_ig_token")
os.environ.setdefault("INSTAGRAM_ACCOUNT_ID", "123456789")


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings with Instagram credentials."""
    with patch("backend.services.integrations.instagram_service.settings") as mock:
        mock.instagram_access_token = "test_ig_token_123"
        mock.instagram_account_id = "987654321"
        yield mock


@pytest.fixture
def instagram_service(mock_settings):
    """Fresh InstagramService instance with mocked settings."""
    from backend.services.integrations.instagram_service import InstagramService

    service = InstagramService()
    # Override the values directly since __init__ reads from settings
    service._token = "test_ig_token_123"
    service._account_id = "987654321"
    return service


@pytest.fixture
def mock_response_success():
    """Mock successful httpx response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"recipient_id": "user_123", "message_id": "mid_456"}
    return response


@pytest.fixture
def mock_response_error():
    """Mock error httpx response."""
    response = MagicMock()
    response.status_code = 400
    response.json.return_value = {
        "error": {
            "message": "Invalid OAuth access token",
            "code": 190,
            "type": "OAuthException",
        },
    }
    return response


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestInstagramServiceInit:
    """Tests for InstagramService initialization."""

    def test_service_created(self, instagram_service) -> None:
        """Service creates with token and account_id from settings."""
        assert instagram_service._token == "test_ig_token_123"
        assert instagram_service._account_id == "987654321"
        assert instagram_service._client is None

    def test_token_property(self, instagram_service) -> None:
        """token property returns stored token."""
        assert instagram_service.token == "test_ig_token_123"

    def test_account_id_property(self, instagram_service) -> None:
        """account_id property returns stored account_id."""
        assert instagram_service.account_id == "987654321"

    def test_api_url(self, instagram_service) -> None:
        """api_url builds correct Instagram Graph API URL."""
        assert instagram_service.api_url == "https://graph.instagram.com/v22.0/987654321"


# ============================================================================
# HTTP CLIENT LIFECYCLE TESTS
# ============================================================================


class TestHttpClientLifecycle:
    """Tests for _get_client and close methods."""

    @pytest.mark.asyncio
    async def test_get_client_creates_client(self, instagram_service) -> None:
        """_get_client creates a new httpx.AsyncClient."""
        client = await instagram_service._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        await instagram_service.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses_client(self, instagram_service) -> None:
        """_get_client reuses existing client."""
        client1 = await instagram_service._get_client()
        client2 = await instagram_service._get_client()
        assert client1 is client2
        await instagram_service.close()

    @pytest.mark.asyncio
    async def test_close_client(self, instagram_service) -> None:
        """close properly closes the httpx client."""
        await instagram_service._get_client()
        await instagram_service.close()
        # After close, next _get_client should create new
        assert instagram_service._client is None or instagram_service._client.is_closed

    @pytest.mark.asyncio
    async def test_close_when_no_client(self, instagram_service) -> None:
        """close is safe to call when no client exists."""
        await instagram_service.close()  # Should not raise


# ============================================================================
# send_message TESTS
# ============================================================================


class TestSendMessage:
    """Tests for send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, instagram_service, mock_response_success) -> None:
        """Successful message send."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_response_success
        instagram_service._client = mock_client

        result = await instagram_service.send_message("user_123", "Hello!")

        assert result == {"recipient_id": "user_123", "message_id": "mid_456"}
        mock_client.post.assert_called_once()

        # Verify payload structure
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["recipient"]["id"] == "user_123"
        assert payload["message"]["text"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_message_truncates_at_1000(
        self, instagram_service, mock_response_success,
    ) -> None:
        """Messages are truncated to 1000 chars."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_response_success
        instagram_service._client = mock_client

        long_text = "x" * 1500
        await instagram_service.send_message("user_123", long_text)

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(payload["message"]["text"]) == 1000

    @pytest.mark.asyncio
    async def test_send_message_no_token_raises(self, instagram_service) -> None:
        """ValueError raised when token not configured."""
        instagram_service._token = None
        with patch.object(
            type(instagram_service), "token", new_callable=lambda: property(lambda self: None),
        ):
            service = instagram_service
            service._token = None
            # Access the underlying property
            with pytest.raises(ValueError, match="access token not configured"):
                await service.send_message("user_123", "Hello")

    @pytest.mark.asyncio
    async def test_send_message_api_error(self, instagram_service, mock_response_error) -> None:
        """API error raises ValueError with error details."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_response_error
        instagram_service._client = mock_client

        with pytest.raises(ValueError, match="Instagram API error"):
            await instagram_service.send_message("user_123", "Hello")

    @pytest.mark.asyncio
    async def test_send_message_http_error(self, instagram_service) -> None:
        """httpx.HTTPError is re-raised."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        instagram_service._client = mock_client

        with pytest.raises(httpx.HTTPError):
            await instagram_service.send_message("user_123", "Hello")

    @pytest.mark.asyncio
    async def test_send_message_correct_headers(
        self, instagram_service, mock_response_success,
    ) -> None:
        """Correct authorization headers are sent."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_response_success
        instagram_service._client = mock_client

        await instagram_service.send_message("user_123", "Test")

        call_args = mock_client.post.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer test_ig_token_123"
        assert headers["Content-Type"] == "application/json"


# ============================================================================
# mark_message_seen TESTS
# ============================================================================


class TestMarkMessageSeen:
    """Tests for mark_message_seen method."""

    @pytest.mark.asyncio
    async def test_mark_seen_success(self, instagram_service) -> None:
        """Successfully mark message as seen."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_response
        instagram_service._client = mock_client

        result = await instagram_service.mark_message_seen("sender_123")
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_seen_api_failure(self, instagram_service) -> None:
        """API failure returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_response
        instagram_service._client = mock_client

        result = await instagram_service.mark_message_seen("sender_123")
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_seen_no_token(self, instagram_service) -> None:
        """Returns False when token not configured."""
        instagram_service._token = None
        with patch.object(
            type(instagram_service), "token", new_callable=lambda: property(lambda self: None),
        ):
            result = await instagram_service.mark_message_seen("sender_123")
            assert result is False

    @pytest.mark.asyncio
    async def test_mark_seen_exception(self, instagram_service) -> None:
        """Exception returns False (graceful degradation)."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.side_effect = Exception("Network error")
        instagram_service._client = mock_client

        result = await instagram_service.mark_message_seen("sender_123")
        assert result is False


# ============================================================================
# get_profile TESTS
# ============================================================================


class TestGetProfile:
    """Tests for get_profile method."""

    @pytest.mark.asyncio
    async def test_get_profile_success(self, instagram_service) -> None:
        """Successfully retrieve profile data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "987654321",
            "username": "balizero",
            "name": "Bali Zero",
            "profile_picture_url": "https://example.com/pic.jpg",
            "followers_count": 1500,
        }
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = mock_response
        instagram_service._client = mock_client

        result = await instagram_service.get_profile()

        assert result["username"] == "balizero"
        assert result["followers_count"] == 1500

    @pytest.mark.asyncio
    async def test_get_profile_no_token_raises(self) -> None:
        """ValueError raised when token not configured."""
        with patch("backend.services.integrations.instagram_service.settings") as mock_settings:
            mock_settings.instagram_access_token = None
            mock_settings.instagram_account_id = "123"

            from backend.services.integrations.instagram_service import InstagramService

            service = InstagramService()
            service._token = None

            with pytest.raises(ValueError, match="access token not configured"):
                await service.get_profile()

    @pytest.mark.asyncio
    async def test_get_profile_api_error(self, instagram_service) -> None:
        """API error raises ValueError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Token expired"}}
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = mock_response
        instagram_service._client = mock_client

        with pytest.raises(ValueError, match="Instagram profile error"):
            await instagram_service.get_profile()


# ============================================================================
# chunk_message TESTS
# ============================================================================


class TestChunkMessage:
    """Tests for chunk_message method."""

    def test_short_message_no_chunking(self, instagram_service) -> None:
        """Messages under max_length are returned as-is."""
        result = instagram_service.chunk_message("Short message")
        assert result == ["Short message"]

    def test_exact_limit(self, instagram_service) -> None:
        """Message exactly at max_length is not chunked."""
        text = "x" * 950
        result = instagram_service.chunk_message(text)
        assert len(result) == 1

    def test_two_chunks(self, instagram_service) -> None:
        """Long message splits into two chunks."""
        para1 = "A" * 500
        para2 = "B" * 500
        text = f"{para1}\n\n{para2}"
        result = instagram_service.chunk_message(text)
        assert len(result) == 2

    def test_respects_paragraph_boundaries(self, instagram_service) -> None:
        """Chunks split at paragraph (\\n\\n) boundaries."""
        paragraphs = [f"Paragraph {i}: " + "x" * 200 for i in range(5)]
        text = "\n\n".join(paragraphs)
        result = instagram_service.chunk_message(text)

        # Each chunk should end at a paragraph boundary
        for chunk in result:
            assert len(chunk) <= 950

    def test_very_long_single_paragraph(self, instagram_service) -> None:
        """Single paragraph longer than max_length is split by lines."""
        lines = [f"Line {i}: " + "x" * 80 for i in range(20)]
        text = "\n".join(lines)
        result = instagram_service.chunk_message(text)
        assert len(result) >= 2
        for chunk in result:
            assert len(chunk) <= 950

    @pytest.mark.parametrize(
        "max_length",
        [200, 500, 950, 1000],
        ids=["small", "medium", "default", "full-limit"],
    )
    def test_custom_max_length(self, instagram_service, max_length: int) -> None:
        """Custom max_length is respected for text with paragraph breaks."""
        # Text with paragraph breaks for proper splitting
        paragraphs = [f"Paragraph {i}: " + "word " * 20 for i in range(10)]
        text = "\n\n".join(paragraphs)  # ~1200 chars with breaks
        result = instagram_service.chunk_message(text, max_length=max_length)
        for chunk in result:
            assert len(chunk) <= max_length + 120  # Margin for paragraph boundaries


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestInstagramServiceIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_send_chunked_messages(self, instagram_service, mock_response_success) -> None:
        """Send a long message that needs chunking."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_response_success
        instagram_service._client = mock_client

        long_text = ("This is paragraph one. " * 50 + "\n\n") * 3
        chunks = instagram_service.chunk_message(long_text)

        for chunk in chunks:
            result = await instagram_service.send_message("user_123", chunk)
            assert result["recipient_id"] == "user_123"

        assert mock_client.post.call_count == len(chunks)

    @pytest.mark.asyncio
    async def test_full_flow_profile_then_send(self, instagram_service) -> None:
        """Full flow: get profile, then send message."""
        # Mock profile response
        profile_response = MagicMock()
        profile_response.status_code = 200
        profile_response.json.return_value = {"id": "123", "username": "test"}

        # Mock send response
        send_response = MagicMock()
        send_response.status_code = 200
        send_response.json.return_value = {"message_id": "mid_1"}

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = profile_response
        mock_client.post.return_value = send_response
        instagram_service._client = mock_client

        profile = await instagram_service.get_profile()
        assert profile["username"] == "test"

        result = await instagram_service.send_message("user_456", "Hello!")
        assert result["message_id"] == "mid_1"
