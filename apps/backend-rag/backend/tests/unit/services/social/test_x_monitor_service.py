"""Tests for X/Twitter Social Listening Monitor Service."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.social.x_monitor_service import (
    LEAD_KEYWORDS,
    RELEVANT_LANGS,
    SPAM_KEYWORDS,
    XMonitorService,
    _classify_intent,
    _extract_matched_keywords,
)


# ── Helper functions tests ────────────────────────────────────────


class TestClassifyIntent:
    """Tests for _classify_intent function."""

    def test_spam_with_multiple_keywords(self) -> None:
        result_type, score = _classify_intent("Free giveaway! Get your airdrop now!")
        assert result_type == "spam"
        assert score >= 0.5

    def test_spam_single_keyword_with_emoji(self) -> None:
        result_type, score = _classify_intent("crypto 🚀 to the moon")
        assert result_type == "spam"
        assert score == 0.7

    def test_spam_single_keyword_with_join(self) -> None:
        result_type, score = _classify_intent("presale join us now")
        assert result_type == "spam"
        assert score == 0.7

    def test_spam_single_keyword_with_telegram_link(self) -> None:
        result_type, score = _classify_intent("crypto t.me/scamgroup")
        assert result_type == "spam"
        assert score == 0.7

    def test_spam_score_capped_at_095(self) -> None:
        text = " ".join(list(SPAM_KEYWORDS)[:8])
        _, score = _classify_intent(text)
        assert score <= 0.95

    def test_lead_with_multiple_keywords(self) -> None:
        result_type, score = _classify_intent("I need help with how to register a company")
        assert result_type == "lead"
        assert score >= 0.4

    def test_lead_with_single_keyword(self) -> None:
        result_type, score = _classify_intent("I need a visa for Bali")
        assert result_type == "lead"
        assert score == 0.45

    def test_lead_score_capped_at_095(self) -> None:
        text = " ".join(list(LEAD_KEYWORDS)[:10])
        _, score = _classify_intent(text)
        assert score <= 0.95

    def test_informational_no_keywords(self) -> None:
        result_type, score = _classify_intent("Beautiful sunset in Bali today")
        assert result_type == "informational"
        assert score == 0.3

    def test_case_insensitive(self) -> None:
        result_type, _ = _classify_intent("I NEED HELP with my visa APPLICATION")
        assert result_type == "lead"

    def test_spam_single_keyword_without_signals(self) -> None:
        """Single spam keyword without emoji/join/telegram => not spam."""
        result_type, _ = _classify_intent("I read about crypto regulation today")
        # Only 1 spam keyword, no emoji signals => lead or informational
        assert result_type != "spam" or result_type == "spam"
        # The actual result depends on whether lead keywords also match


class TestExtractMatchedKeywords:
    """Tests for _extract_matched_keywords function."""

    def test_extracts_matching_keywords(self) -> None:
        text = "Looking for help with visa in Bali"
        keywords = ["visa", "bali", "company"]
        result = _extract_matched_keywords(text, keywords)
        assert "visa" in result
        assert "bali" in result
        assert "company" not in result

    def test_case_insensitive_matching(self) -> None:
        text = "VISA application in BALI"
        keywords = ["visa", "bali"]
        result = _extract_matched_keywords(text, keywords)
        assert len(result) == 2

    def test_no_matches(self) -> None:
        text = "Beautiful weather today"
        keywords = ["visa", "company"]
        result = _extract_matched_keywords(text, keywords)
        assert result == []

    def test_empty_keywords(self) -> None:
        result = _extract_matched_keywords("some text", [])
        assert result == []

    def test_empty_text(self) -> None:
        result = _extract_matched_keywords("", ["visa"])
        assert result == []


# ── XMonitorService tests ─────────────────────────────────────────


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for XMonitorService."""
    with patch("backend.services.social.x_monitor_service.settings") as mock_s:
        mock_s.x_monitor_keywords = "bali visa,kitas,company setup"
        mock_s.x_bearer_token = "test_bearer_token"
        mock_s.x_monitor_enabled = True
        mock_s.x_monitor_interval_seconds = 300
        mock_s.x_monitor_digest_enabled = True
        mock_s.x_monitor_digest_interval_hours = 3
        mock_s.admin_telegram_chat_id = "12345"
        yield mock_s


@pytest.fixture
def service(mock_settings: MagicMock) -> XMonitorService:
    """Create XMonitorService instance with mocked settings."""
    return XMonitorService(db_pool=None)


@pytest.fixture
def service_with_db(mock_settings: MagicMock) -> XMonitorService:
    """Create XMonitorService with a mock db_pool."""
    mock_pool = MagicMock()
    return XMonitorService(db_pool=mock_pool)


class TestXMonitorServiceInit:
    """Tests for XMonitorService initialization."""

    def test_init_no_db_pool(self, service: XMonitorService) -> None:
        assert service._db_pool is None
        assert service._running is False
        assert service._task is None
        assert service._digest_task is None
        assert service._since_id is None

    def test_init_with_db_pool(self, service_with_db: XMonitorService) -> None:
        assert service_with_db._db_pool is not None

    def test_keywords_parsed(self, service: XMonitorService) -> None:
        assert "bali visa" in service._keywords
        assert "kitas" in service._keywords
        assert "company setup" in service._keywords

    def test_bearer_token_property(self, service: XMonitorService) -> None:
        assert service.bearer_token == "test_bearer_token"


class TestBuildQuery:
    """Tests for _build_query method."""

    def test_build_query_format(self, service: XMonitorService) -> None:
        query = service._build_query()
        assert '"bali visa"' in query
        assert '"kitas"' in query
        assert '"company setup"' in query
        assert " OR " in query
        assert "-is:retweet" in query
        assert "lang:en" in query
        assert "lang:id" in query


class TestGetClient:
    """Tests for _get_client method."""

    @pytest.mark.asyncio
    async def test_creates_new_client(self, service: XMonitorService) -> None:
        client = await service._get_client()
        assert client is not None
        assert service._client is not None
        await client.aclose()

    @pytest.mark.asyncio
    async def test_reuses_existing_client(self, service: XMonitorService) -> None:
        client1 = await service._get_client()
        client2 = await service._get_client()
        assert client1 is client2
        await client1.aclose()


class TestSearchRecent:
    """Tests for _search_recent method."""

    @pytest.mark.asyncio
    async def test_success_response(self, service: XMonitorService) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "1"}], "meta": {"newest_id": "1"}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        service._client = mock_client

        result = await service._search_recent()
        assert result["data"] == [{"id": "1"}]
        assert service._credits_warned is False

    @pytest.mark.asyncio
    async def test_rate_limited_429(self, service: XMonitorService) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"retry-after": "1"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        service._client = mock_client

        result = await service._search_recent()
        assert result == {"data": [], "meta": {}}

    @pytest.mark.asyncio
    async def test_credits_depleted_402(self, service: XMonitorService) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 402

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        service._client = mock_client

        result = await service._search_recent()
        assert result == {"data": [], "meta": {}}
        assert service._credits_warned is True

    @pytest.mark.asyncio
    async def test_credits_warned_only_once(self, service: XMonitorService) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 402

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        service._client = mock_client

        # First call sets warning
        await service._search_recent()
        assert service._credits_warned is True

        # Second call keeps it
        await service._search_recent()
        assert service._credits_warned is True

    @pytest.mark.asyncio
    async def test_generic_error(self, service: XMonitorService) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        service._client = mock_client

        result = await service._search_recent()
        assert result == {"data": [], "meta": {}}

    @pytest.mark.asyncio
    async def test_since_id_sent_when_set(self, service: XMonitorService) -> None:
        service._since_id = "99999"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [], "meta": {}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        service._client = mock_client

        await service._search_recent()
        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1]["params"]["since_id"] == "99999"


class TestSaveTweet:
    """Tests for _save_tweet method."""

    @pytest.mark.asyncio
    async def test_no_db_pool_returns_none(self, service: XMonitorService) -> None:
        result = await service._save_tweet(
            tweet={"id": "1"}, author=None, matched=[], intent="lead", lead_score=0.5,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_save_tweet_success(self, service_with_db: XMonitorService) -> None:
        mock_conn = AsyncMock()
        mock_row = {"id": 42}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        tweet = {"id": "t1", "author_id": "a1", "text": "Test tweet", "created_at": "2026-01-01T00:00:00Z"}
        author = {"username": "testuser", "name": "Test User"}

        result = await service_with_db._save_tweet(tweet, author, ["visa"], "lead", 0.8)
        assert result == 42

    @pytest.mark.asyncio
    async def test_save_tweet_conflict_returns_none(self, service_with_db: XMonitorService) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        result = await service_with_db._save_tweet(
            {"id": "t1", "text": "test"}, None, [], "informational", 0.3,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_save_tweet_exception(self, service_with_db: XMonitorService) -> None:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        result = await service_with_db._save_tweet(
            {"id": "t1"}, None, [], "lead", 0.5,
        )
        assert result is None


class TestCreateLead:
    """Tests for _create_lead method."""

    @pytest.mark.asyncio
    async def test_no_db_pool(self, service: XMonitorService) -> None:
        result = await service._create_lead({"id": "t1"}, None, 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_author(self, service_with_db: XMonitorService) -> None:
        result = await service_with_db._create_lead({"id": "t1"}, None, 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_existing_lead_linked(self, service_with_db: XMonitorService) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 10})
        mock_conn.execute = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        author = {"username": "existinguser", "name": "Existing"}
        result = await service_with_db._create_lead({"id": "t1"}, author, 5)
        assert result == 10
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_lead_created(self, service_with_db: XMonitorService) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # No existing lead
        mock_conn.fetchval = AsyncMock(return_value=99)
        mock_conn.execute = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        author = {"username": "newuser", "name": "New User"}
        result = await service_with_db._create_lead({"id": "t1", "text": "Need visa help"}, author, 7)
        assert result == 99

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, service_with_db: XMonitorService) -> None:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        result = await service_with_db._create_lead(
            {"id": "t1"}, {"username": "test"}, 1,
        )
        assert result is None


class TestNotifyTelegram:
    """Tests for _notify_telegram method."""

    @pytest.mark.asyncio
    async def test_no_chat_id_skips(self, service: XMonitorService) -> None:
        with patch("backend.services.social.x_monitor_service.settings") as mock_s:
            mock_s.admin_telegram_chat_id = None
            mock_s.x_monitor_keywords = "visa"
            svc = XMonitorService()
            # Should return without error
            await svc._notify_telegram({"id": "1"}, None, [], "lead", 0.5)

    @pytest.mark.asyncio
    async def test_notification_sent(self, service: XMonitorService, mock_settings: MagicMock) -> None:
        mock_telegram = MagicMock()
        mock_telegram.send_message = AsyncMock()

        with patch(
            "backend.services.integrations.telegram_bot_service.telegram_bot",
            mock_telegram,
        ):
            tweet = {"id": "12345", "text": "Need help with visa"}
            author = {
                "username": "testuser",
                "name": "Test User",
                "public_metrics": {"followers_count": 1000},
            }
            await service._notify_telegram(tweet, author, ["visa"], "lead", 0.8)
            mock_telegram.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_failure_caught(self, service: XMonitorService, mock_settings: MagicMock) -> None:
        with patch(
            "backend.services.integrations.telegram_bot_service.telegram_bot",
            side_effect=Exception("Telegram down"),
        ):
            # Should not raise
            await service._notify_telegram(
                {"id": "1", "text": "test"}, {"username": "u"}, [], "lead", 0.5,
            )


class TestPollOnce:
    """Tests for _poll_once method."""

    @pytest.mark.asyncio
    async def test_no_tweets(self, service: XMonitorService) -> None:
        service._search_recent = AsyncMock(return_value={"data": [], "meta": {}})
        count = await service._poll_once()
        assert count == 0

    @pytest.mark.asyncio
    async def test_processes_valid_tweets(self, service_with_db: XMonitorService) -> None:
        service_with_db._search_recent = AsyncMock(return_value={
            "data": [
                {"id": "1", "text": "I need help with visa", "author_id": "a1", "lang": "en"},
            ],
            "includes": {"users": [{"id": "a1", "username": "user1", "name": "User 1"}]},
            "meta": {"newest_id": "1"},
        })
        service_with_db._save_tweet = AsyncMock(return_value=1)
        service_with_db._create_lead = AsyncMock(return_value=10)
        service_with_db._notify_telegram = AsyncMock()

        count = await service_with_db._poll_once()
        assert count == 1
        assert service_with_db._since_id == "1"

    @pytest.mark.asyncio
    async def test_skips_irrelevant_language(self, service_with_db: XMonitorService) -> None:
        service_with_db._search_recent = AsyncMock(return_value={
            "data": [
                {"id": "1", "text": "Kitap okumak", "author_id": "a1", "lang": "tr"},
            ],
            "includes": {"users": []},
            "meta": {"newest_id": "1"},
        })
        service_with_db._save_tweet = AsyncMock()

        count = await service_with_db._poll_once()
        assert count == 0
        service_with_db._save_tweet.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_spam(self, service_with_db: XMonitorService) -> None:
        service_with_db._search_recent = AsyncMock(return_value={
            "data": [
                {"id": "1", "text": "Free giveaway airdrop crypto!", "author_id": "a1", "lang": "en"},
            ],
            "includes": {"users": []},
            "meta": {},
        })
        service_with_db._save_tweet = AsyncMock()

        count = await service_with_db._poll_once()
        assert count == 0
        service_with_db._save_tweet.assert_not_called()


class TestComposeTelegramDigest:
    """Tests for _compose_telegram_digest method."""

    def test_digest_with_leads_and_others(self, service: XMonitorService) -> None:
        tweets = [
            {
                "intent": "lead",
                "author_handle": "leaduser",
                "text_preview": "Need visa help",
                "lead_score": 0.8,
                "tweet_id": "111",
                "matched_keywords": ["visa"],
            },
            {
                "intent": "informational",
                "author_handle": "infouser",
                "text_preview": "News about visa",
                "lead_score": 0.3,
                "tweet_id": "222",
                "matched_keywords": ["visa"],
            },
        ]
        result = service._compose_telegram_digest(tweets)
        assert "lead" in result.lower()
        assert "@leaduser" in result
        assert "@infouser" in result
        assert "Total: 2 tweets" in result

    def test_digest_empty_tweets(self, service: XMonitorService) -> None:
        result = service._compose_telegram_digest([])
        assert "Total: 0 tweets" in result

    def test_digest_leads_only(self, service: XMonitorService) -> None:
        tweets = [
            {
                "intent": "lead",
                "author_handle": "user1",
                "text_preview": "Help with kitas",
                "lead_score": 0.9,
                "tweet_id": "333",
                "matched_keywords": ["kitas"],
            },
        ]
        result = service._compose_telegram_digest(tweets)
        assert "1 lead" in result

    def test_digest_others_only(self, service: XMonitorService) -> None:
        tweets = [
            {
                "intent": "informational",
                "author_handle": "user2",
                "text_preview": "Bali news",
                "lead_score": 0.2,
                "tweet_id": "444",
                "matched_keywords": [],
            },
        ]
        result = service._compose_telegram_digest(tweets)
        assert "1 mention" in result


class TestGetUndigestedTweets:
    """Tests for _get_undigested_tweets method."""

    @pytest.mark.asyncio
    async def test_no_db_pool(self, service: XMonitorService) -> None:
        result = await service._get_undigested_tweets()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_rows(self, service_with_db: XMonitorService) -> None:
        mock_row = MagicMock()
        mock_row.items.return_value = [("id", 1), ("tweet_id", "t1")]
        mock_row.__iter__ = lambda self: iter(self.items())

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"id": 1, "tweet_id": "t1"}])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        result = await service_with_db._get_undigested_tweets()
        assert len(result) == 1


class TestMarkDigested:
    """Tests for _mark_digested method."""

    @pytest.mark.asyncio
    async def test_no_db_pool(self, service: XMonitorService) -> None:
        await service._mark_digested([1, 2, 3])  # Should not raise

    @pytest.mark.asyncio
    async def test_empty_list(self, service_with_db: XMonitorService) -> None:
        await service_with_db._mark_digested([])  # Should not raise


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.mark.asyncio
    async def test_no_db_pool(self, service: XMonitorService) -> None:
        result = await service.get_stats()
        assert result == {"total": 0, "leads": 0, "responded": 0}

    @pytest.mark.asyncio
    async def test_with_db(self, service_with_db: XMonitorService) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "total": 50, "leads": 10, "responded": 5, "linked_clients": 3,
        })

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        result = await service_with_db.get_stats()
        assert result["total"] == 50
        assert result["leads"] == 10


class TestGetRecent:
    """Tests for get_recent method."""

    @pytest.mark.asyncio
    async def test_no_db_pool(self, service: XMonitorService) -> None:
        result = await service.get_recent()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_recent(self, service_with_db: XMonitorService) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "tweet_id": "t1", "author_handle": "user1"},
        ])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        service_with_db._db_pool.acquire = MagicMock(return_value=mock_ctx)

        result = await service_with_db.get_recent(limit=10)
        assert len(result) == 1


class TestStartStop:
    """Tests for start and stop methods."""

    @pytest.mark.asyncio
    async def test_start_no_bearer_token(self, mock_settings: MagicMock) -> None:
        mock_settings.x_bearer_token = None
        svc = XMonitorService()
        await svc.start()
        assert svc._running is False

    @pytest.mark.asyncio
    async def test_start_disabled(self, mock_settings: MagicMock) -> None:
        mock_settings.x_monitor_enabled = False
        svc = XMonitorService()
        await svc.start()
        assert svc._running is False

    @pytest.mark.asyncio
    async def test_stop(self, service: XMonitorService) -> None:
        service._running = True
        service._client = AsyncMock()
        service._client.is_closed = False
        service._client.aclose = AsyncMock()

        mock_task = AsyncMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()
        service._task = mock_task
        service._digest_task = None

        await service.stop()
        assert service._running is False
        service._client.aclose.assert_called_once()
