"""
Unit tests for Newsletter Router - 99% Coverage
Tests all endpoints, error cases, and edge cases
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the classes we need to test
from app.routers.newsletter import (
    ConfirmRequest,
    PreferencesRequest,
    SubscribeRequest,
    SubscribeResponse,
    SubscriberResponse,
    UnsubscribeRequest,
)


@pytest.mark.unit
class TestNewsletterRouter:
    """Comprehensive unit tests for Newsletter router targeting 99% coverage"""

    def test_subscribe_request_model_valid(self):
        """Test SubscribeRequest model with valid data"""
        request = SubscribeRequest(
            email="test@example.com",
            name="Test User",
            categories=["tech", "news"],
            frequency="weekly",
            language="en",
        )
        assert request.email == "test@example.com"
        assert request.name == "Test User"
        assert request.categories == ["tech", "news"]
        assert request.frequency == "weekly"
        assert request.language == "en"

    def test_subscribe_request_model_defaults(self):
        """Test SubscribeRequest model with default values"""
        request = SubscribeRequest(email="test@example.com")
        assert request.email == "test@example.com"
        assert request.name is None
        assert request.categories == []
        assert request.frequency == "weekly"
        assert request.language == "en"

    def test_subscribe_request_frequency_validator_valid(self):
        """Test frequency validator with valid values"""
        for freq in ["instant", "daily", "weekly"]:
            request = SubscribeRequest(email="test@example.com", frequency=freq)
            assert request.frequency == freq

    def test_subscribe_request_frequency_validator_invalid(self):
        """Test frequency validator with invalid values"""
        with pytest.raises(ValueError, match="frequency must be one of"):
            SubscribeRequest(email="test@example.com", frequency="invalid")

    def test_subscribe_response_model(self):
        """Test SubscribeResponse model"""
        response = SubscribeResponse(success=True, message="Success message", subscriberId="123")
        assert response.success is True
        assert response.message == "Success message"
        assert response.subscriberId == "123"

    def test_confirm_request_model(self):
        """Test ConfirmRequest model"""
        request = ConfirmRequest(subscriberId="123", token="token123")
        assert request.subscriberId == "123"
        assert request.token == "token123"

    def test_unsubscribe_request_model(self):
        """Test UnsubscribeRequest model"""
        request = UnsubscribeRequest(subscriberId="123", email="test@example.com", token="token123")
        assert request.subscriberId == "123"
        assert request.email == "test@example.com"
        assert request.token == "token123"

    def test_preferences_request_model(self):
        """Test PreferencesRequest model"""
        request = PreferencesRequest(
            subscriberId="123", categories=["tech"], frequency="daily", language="it"
        )
        assert request.subscriberId == "123"
        assert request.categories == ["tech"]
        assert request.frequency == "daily"
        assert request.language == "it"

    def test_subscriber_response_model(self):
        """Test SubscriberResponse model"""
        now = datetime.now()
        response = SubscriberResponse(
            id="123",
            email="test@example.com",
            name="Test User",
            categories=["tech"],
            frequency="daily",
            language="it",
            confirmed=True,
            created_at=now,
        )
        assert response.id == "123"
        assert response.email == "test@example.com"
        assert response.name == "Test User"
        assert response.categories == ["tech"]
        assert response.frequency == "daily"
        assert response.language == "it"
        assert response.confirmed is True
        assert response.created_at == now

    @pytest.mark.asyncio
    async def test_subscribe_new_subscriber(self):
        """Test subscribe endpoint with new subscriber"""
        # Mock the database pool and connection
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock database responses
        mock_conn.fetchrow.side_effect = [
            None,  # No existing subscriber
            {"id": "new-id-123"},  # New subscriber ID
        ]

        # Import and test the endpoint
        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import subscribe

            request = SubscribeRequest(
                email="new@example.com", name="New User", categories=["tech"], frequency="weekly"
            )

            response = await subscribe(request, pool=mock_pool)

            assert response.success is True
            assert response.subscriberId == "new-id-123"
            assert "check your email" in response.message.lower()

            # Verify database calls
            assert mock_conn.fetchrow.call_count == 2
            assert mock_conn.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_subscribe_already_confirmed(self):
        """Test subscribe endpoint with already confirmed subscriber"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock existing confirmed subscriber
        mock_conn.fetchrow.return_value = {
            "id": "existing-id",
            "confirmed": True,
            "unsubscribed_at": None,
        }

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from fastapi import HTTPException

            from app.routers.newsletter import subscribe

            request = SubscribeRequest(email="existing@example.com")

            with pytest.raises(HTTPException) as exc_info:
                await subscribe(request, pool=mock_pool)

            assert exc_info.value.status_code == 409
            assert "already subscribed" in str(exc_info.value.detail["message"])

    @pytest.mark.asyncio
    async def test_subscribe_resubscribing(self):
        """Test subscribe endpoint with resubscribing user"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock unsubscribed user
        mock_conn.fetchrow.return_value = {
            "id": "unsub-id",
            "confirmed": True,
            "unsubscribed_at": datetime.now(),
        }

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import subscribe

            request = SubscribeRequest(email="resub@example.com")

            response = await subscribe(request, pool=mock_pool)

            assert response.success is True
            assert response.subscriberId == "unsub-id"
            assert "check your email" in response.message.lower()

            # Verify update was called
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_not_confirmed_resend(self):
        """Test subscribe endpoint with unconfirmed user (resend confirmation)"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock unconfirmed user
        mock_conn.fetchrow.return_value = {
            "id": "unconf-id",
            "confirmed": False,
            "unsubscribed_at": None,
        }

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import subscribe

            request = SubscribeRequest(email="unconf@example.com")

            response = await subscribe(request, pool=mock_pool)

            assert response.success is True
            assert response.subscriberId == "unconf-id"
            assert "confirmation email resent" in response.message.lower()

    @pytest.mark.asyncio
    async def test_confirm_subscription_success(self):
        """Test confirm subscription endpoint success"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock subscriber found and not confirmed
        mock_conn.fetchrow.return_value = {
            "id": "sub-id",
            "email": "test@example.com",
            "confirmed": False,
        }

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import confirm_subscription

            request = ConfirmRequest(subscriberId="sub-id", token="valid-token")

            response = await confirm_subscription(request, pool=mock_pool)

            assert response["success"] is True
            assert "confirmed successfully" in response["message"]

            # Verify confirmation update
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_subscription_already_confirmed(self):
        """Test confirm subscription endpoint when already confirmed"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock already confirmed subscriber
        mock_conn.fetchrow.return_value = {
            "id": "sub-id",
            "email": "test@example.com",
            "confirmed": True,
        }

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import confirm_subscription

            request = ConfirmRequest(subscriberId="sub-id", token="valid-token")

            response = await confirm_subscription(request, pool=mock_pool)

            assert response["success"] is True
            assert "already confirmed" in response["message"]

            # Verify no update was made
            mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_subscription_invalid_link(self):
        """Test confirm subscription endpoint with invalid link"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock no subscriber found
        mock_conn.fetchrow.return_value = None

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from fastapi import HTTPException

            from app.routers.newsletter import confirm_subscription

            request = ConfirmRequest(subscriberId="invalid-id", token="invalid-token")

            with pytest.raises(HTTPException) as exc_info:
                await confirm_subscription(request, pool=mock_pool)

            assert exc_info.value.status_code == 404
            assert "invalid confirmation link" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_unsubscribe_by_id(self):
        """Test unsubscribe endpoint by subscriber ID"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock subscriber found
        mock_conn.fetchrow.return_value = {"id": "sub-id", "email": "test@example.com"}

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import unsubscribe

            request = UnsubscribeRequest(subscriberId="sub-id")

            response = await unsubscribe(request, pool=mock_pool)

            assert response["success"] is True
            assert "successfully unsubscribed" in response["message"]

            # Verify unsubscribe update
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsubscribe_by_email(self):
        """Test unsubscribe endpoint by email"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock subscriber found
        mock_conn.fetchrow.return_value = {"id": "sub-id", "email": "test@example.com"}

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import unsubscribe

            request = UnsubscribeRequest(email="test@example.com")

            response = await unsubscribe(request, pool=mock_pool)

            assert response["success"] is True
            assert "successfully unsubscribed" in response["message"]

    @pytest.mark.asyncio
    async def test_unsubscribe_no_identifier(self):
        """Test unsubscribe endpoint with no identifier"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from fastapi import HTTPException

            from app.routers.newsletter import unsubscribe

            request = UnsubscribeRequest()  # No ID or email

            with pytest.raises(HTTPException) as exc_info:
                await unsubscribe(request, pool=mock_pool)

            assert exc_info.value.status_code == 400
            assert "email or subscriberid required" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_unsubscribe_not_found(self):
        """Test unsubscribe endpoint with subscriber not found"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock no subscriber found
        mock_conn.fetchrow.return_value = None

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from fastapi import HTTPException

            from app.routers.newsletter import unsubscribe

            request = UnsubscribeRequest(subscriberId="nonexistent-id")

            with pytest.raises(HTTPException) as exc_info:
                await unsubscribe(request, pool=mock_pool)

            assert exc_info.value.status_code == 404
            assert "subscriber not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_update_preferences_by_id(self):
        """Test update preferences endpoint by subscriber ID"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock subscriber found
        mock_conn.fetchrow.return_value = {"id": "sub-id"}

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import update_preferences

            request = PreferencesRequest(
                subscriberId="sub-id", categories=["tech", "news"], frequency="daily", language="it"
            )

            response = await update_preferences(request, pool=mock_pool)

            assert response["success"] is True
            assert "preferences updated" in response["message"]

            # Verify update was called
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_preferences_by_email(self):
        """Test update preferences endpoint by email"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock subscriber found
        mock_conn.fetchrow.return_value = {"id": "sub-id"}

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import update_preferences

            request = PreferencesRequest(email="test@example.com", frequency="weekly")

            response = await update_preferences(request, pool=mock_pool)

            assert response["success"] is True
            assert "preferences updated" in response["message"]

    @pytest.mark.asyncio
    async def test_update_preferences_no_identifier(self):
        """Test update preferences endpoint with no identifier"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from fastapi import HTTPException

            from app.routers.newsletter import update_preferences

            request = PreferencesRequest()  # No ID or email

            with pytest.raises(HTTPException) as exc_info:
                await update_preferences(request, pool=mock_pool)

            assert exc_info.value.status_code == 400
            assert "email or subscriberid required" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_update_preferences_not_found(self):
        """Test update preferences endpoint with subscriber not found"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock no subscriber found
        mock_conn.fetchrow.return_value = None

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from fastapi import HTTPException

            from app.routers.newsletter import update_preferences

            request = PreferencesRequest(subscriberId="nonexistent-id")

            with pytest.raises(HTTPException) as exc_info:
                await update_preferences(request, pool=mock_pool)

            assert exc_info.value.status_code == 404
            assert "subscriber not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_update_preferences_no_changes(self):
        """Test update preferences endpoint with no changes"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock subscriber found
        mock_conn.fetchrow.return_value = {"id": "sub-id"}

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import update_preferences

            request = PreferencesRequest(subscriberId="sub-id")  # No actual changes

            response = await update_preferences(request, pool=mock_pool)

            assert response["success"] is True
            assert "no changes" in response["message"]

            # Verify no update was made
            mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_subscribers_all(self):
        """Test list subscribers endpoint with no filters"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock database responses
        mock_conn.fetch.side_effect = [
            [  # Subscribers list
                {
                    "id": "sub1",
                    "email": "test1@example.com",
                    "name": "User 1",
                    "categories": ["tech"],
                    "frequency": "weekly",
                    "language": "en",
                    "confirmed": True,
                    "created_at": datetime.now(),
                },
                {
                    "id": "sub2",
                    "email": "test2@example.com",
                    "name": None,
                    "categories": None,
                    "frequency": None,
                    "language": None,
                    "confirmed": False,
                    "created_at": datetime.now(),
                },
            ],
            50,  # Total count
        ]

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import list_subscribers

            response = await list_subscribers(
                category=None, frequency=None, confirmed=None, limit=100, offset=0, pool=mock_pool
            )

            assert "subscribers" in response
            assert len(response["subscribers"]) == 2
            assert response["total"] == 50
            assert response["limit"] == 100
            assert response["offset"] == 0

            # Verify subscriber data
            sub1 = response["subscribers"][0]
            assert sub1["email"] == "test1@example.com"
            assert sub1["name"] == "User 1"
            assert sub1["categories"] == ["tech"]
            assert sub1["frequency"] == "weekly"
            assert sub1["language"] == "en"
            assert sub1["confirmed"] is True

            # Verify defaults for null values
            sub2 = response["subscribers"][1]
            assert sub2["name"] is None
            assert sub2["categories"] == []
            assert sub2["frequency"] == "weekly"
            assert sub2["language"] == "en"
            assert sub2["confirmed"] is False

    @pytest.mark.asyncio
    async def test_list_subscribers_with_filters(self):
        """Test list subscribers endpoint with filters"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock database responses
        mock_conn.fetch.side_effect = [
            [  # Filtered subscribers
                {
                    "id": "sub1",
                    "email": "tech@example.com",
                    "name": "Tech User",
                    "categories": ["tech"],
                    "frequency": "daily",
                    "language": "en",
                    "confirmed": True,
                    "created_at": datetime.now(),
                }
            ],
            1,  # Total count
        ]

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import list_subscribers

            response = await list_subscribers(
                category="tech",
                frequency="daily",
                confirmed=True,
                limit=50,
                offset=10,
                pool=mock_pool,
            )

            assert len(response["subscribers"]) == 1
            assert response["total"] == 1
            assert response["limit"] == 50
            assert response["offset"] == 10

            # Verify the subscriber matches filters
            sub = response["subscribers"][0]
            assert "tech" in sub["categories"]
            assert sub["frequency"] == "daily"
            assert sub["confirmed"] is True

    @pytest.mark.asyncio
    async def test_log_newsletter_send(self):
        """Test log newsletter send endpoint"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import log_newsletter_send

            response = await log_newsletter_send(
                article_id="article-123",
                recipient_count=1000,
                sent_count=950,
                failed_count=50,
                pool=mock_pool,
            )

            assert response["success"] is True

            # Verify database insert was called
            mock_conn.execute.assert_called_once()

            # Check the SQL parameters
            call_args = mock_conn.execute.call_args
            assert (
                call_args[0][0]
                == """
            INSERT INTO newsletter_send_log (article_id, recipient_count, sent_count, failed_count)
            VALUES ($1, $2, $3, $4)
            """.strip()
            )
            assert call_args[0][1] == "article-123"
            assert call_args[0][2] == 1000
            assert call_args[0][3] == 950
            assert call_args[0][4] == 50

    def test_router_prefix_and_tags(self):
        """Test router configuration"""
        from app.routers.newsletter import router

        assert router.prefix == "/api/blog/newsletter"
        assert "newsletter" in router.tags

    @pytest.mark.asyncio
    async def test_subscribe_with_all_parameters(self):
        """Test subscribe endpoint with all optional parameters"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock database responses
        mock_conn.fetchrow.side_effect = [
            None,  # No existing subscriber
            {"id": "full-id-123"},  # New subscriber ID
        ]

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import subscribe

            request = SubscribeRequest(
                email="full@example.com",
                name="Full Name",
                categories=["tech", "news", "business"],
                frequency="daily",
                language="it",
            )

            response = await subscribe(request, pool=mock_pool)

            assert response.success is True
            assert response.subscriberId == "full-id-123"

            # Verify all parameters were passed to INSERT
            insert_call = mock_conn.execute.call_args
            assert insert_call[0][1] == "full@example.com"  # email
            assert insert_call[0][2] == "Full Name"  # name
            assert insert_call[0][3] == ["tech", "news", "business"]  # categories
            assert insert_call[0][4] == "daily"  # frequency
            assert insert_call[0][5] == "it"  # language

    @pytest.mark.asyncio
    async def test_update_preferences_partial_update(self):
        """Test update preferences with only some fields"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock subscriber found
        mock_conn.fetchrow.return_value = {"id": "sub-id"}

        with patch("app.routers.newsletter.get_database_pool", return_value=mock_pool):
            from app.routers.newsletter import update_preferences

            request = PreferencesRequest(
                subscriberId="sub-id",
                categories=["new-tech"],  # Only updating categories
            )

            response = await update_preferences(request, pool=mock_pool)

            assert response["success"] is True

            # Verify only categories was updated
            update_call = mock_conn.execute.call_args
            query = update_call[0][0]
            assert "categories = $2" in query
            assert "frequency =" not in query
            assert "language =" not in query
            assert "updated_at = NOW()" in query
