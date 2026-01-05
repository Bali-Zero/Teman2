"""
Unit tests for Telegram Router
Tests Telegram bot webhook and management endpoints
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

# Add backend to path
backend_path = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_telegram_bot():
    """Mock telegram_bot service"""
    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    bot.send_message = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.set_webhook = AsyncMock(return_value={"ok": True, "result": True, "description": "Webhook was set"})
    bot.delete_webhook = AsyncMock(return_value={"ok": True, "result": True, "description": "Webhook was deleted"})
    bot.get_webhook_info = AsyncMock(return_value={"ok": True, "result": {"url": "https://example.com/webhook"}})
    bot.get_me = AsyncMock(return_value={"ok": True, "result": {"id": 123, "username": "test_bot", "first_name": "Test Bot"}})
    return bot


@pytest.fixture
def mock_orchestrator():
    """Mock AgenticRAGOrchestrator"""
    orchestrator = MagicMock()
    orchestrator.process_query = AsyncMock(
        return_value=MagicMock(answer="Test response from RAG")
    )
    return orchestrator


@pytest.fixture
def mock_request():
    """Mock FastAPI Request"""
    request = MagicMock(spec=Request)
    request.app.state = MagicMock()
    request.app.state.db_pool = None
    request.app.state.search_service = None
    return request


@pytest.fixture
def cleanup_pending_articles():
    """Cleanup pending articles directory after tests"""
    pending_path = Path("/tmp/pending_articles")
    if pending_path.exists():
        for file in pending_path.glob("*.json"):
            file.unlink()
    yield
    if pending_path.exists():
        for file in pending_path.glob("*.json"):
            file.unlink()


# ============================================================================
# Tests for helper functions
# ============================================================================


def test_get_article_status_new(cleanup_pending_articles):
    """Test get_article_status for new article"""
    from app.routers.telegram import get_article_status
    
    article_id = "test_article_123"
    status = get_article_status(article_id)
    
    assert status["article_id"] == article_id
    assert status["status"] == "voting"
    assert status["votes"]["approve"] == []
    assert status["votes"]["reject"] == []
    assert status["feedback"] == []
    assert "created_at" in status


def test_get_article_status_existing(cleanup_pending_articles):
    """Test get_article_status for existing article"""
    from app.routers.telegram import get_article_status, save_article_status
    
    article_id = "test_article_456"
    data = {
        "article_id": article_id,
        "status": "approved",
        "votes": {"approve": [{"user_id": 1, "user_name": "User1"}], "reject": []},
        "feedback": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    save_article_status(article_id, data)
    
    status = get_article_status(article_id)
    assert status["status"] == "approved"
    assert len(status["votes"]["approve"]) == 1


def test_add_vote_new_vote(cleanup_pending_articles):
    """Test add_vote with new vote"""
    from app.routers.telegram import add_vote
    
    article_id = "test_vote_1"
    user = {"id": 1, "first_name": "TestUser"}
    
    data, result = add_vote(article_id, "approve", user)
    
    assert result == "vote_recorded"
    assert len(data["votes"]["approve"]) == 1
    assert data["votes"]["approve"][0]["user_id"] == 1


def test_add_vote_already_voted(cleanup_pending_articles):
    """Test add_vote when user already voted"""
    from app.routers.telegram import add_vote
    
    article_id = "test_vote_2"
    user = {"id": 1, "first_name": "TestUser"}
    
    add_vote(article_id, "approve", user)
    data, result = add_vote(article_id, "reject", user)
    
    assert result == "already_voted"


def test_add_vote_approved(cleanup_pending_articles):
    """Test add_vote reaching approval threshold"""
    from app.routers.telegram import add_vote
    
    article_id = "test_vote_3"
    user1 = {"id": 1, "first_name": "User1"}
    user2 = {"id": 2, "first_name": "User2"}
    
    add_vote(article_id, "approve", user1)
    data, result = add_vote(article_id, "approve", user2)
    
    assert result == "approved"
    assert data["status"] == "approved"
    assert len(data["votes"]["approve"]) == 2


def test_add_vote_rejected(cleanup_pending_articles):
    """Test add_vote reaching rejection threshold"""
    from app.routers.telegram import add_vote
    
    article_id = "test_vote_4"
    user1 = {"id": 1, "first_name": "User1"}
    user2 = {"id": 2, "first_name": "User2"}
    
    add_vote(article_id, "reject", user1)
    data, result = add_vote(article_id, "reject", user2)
    
    assert result == "rejected"
    assert data["status"] == "rejected"
    assert len(data["votes"]["reject"]) == 2


def test_add_vote_voting_closed(cleanup_pending_articles):
    """Test add_vote when voting is closed"""
    from app.routers.telegram import add_vote, save_article_status
    
    article_id = "test_vote_5"
    data = {
        "article_id": article_id,
        "status": "approved",
        "votes": {"approve": [], "reject": []},
        "feedback": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    save_article_status(article_id, data)
    
    user = {"id": 1, "first_name": "TestUser"}
    data, result = add_vote(article_id, "approve", user)
    
    assert result == "voting_closed"


def test_format_vote_tally(cleanup_pending_articles):
    """Test format_vote_tally"""
    from app.routers.telegram import format_vote_tally, add_vote
    
    article_id = "test_tally_1"
    user1 = {"id": 1, "first_name": "User1"}
    add_vote(article_id, "approve", user1)
    
    from app.routers.telegram import get_article_status
    data = get_article_status(article_id)
    
    tally = format_vote_tally(data, "Original article text")
    
    assert "VOTAZIONE IN CORSO" in tally
    assert "Original article text" in tally
    assert "User1 ✅" in tally
    assert "1/2" in tally or "2/2" in tally


# ============================================================================
# Tests for get_orchestrator
# ============================================================================


@pytest.mark.asyncio
async def test_get_orchestrator(mock_request):
    """Test get_orchestrator creates orchestrator"""
    from app.routers.telegram import get_orchestrator
    
    with patch("app.routers.telegram.create_agentic_rag") as mock_create:
        mock_orch = MagicMock()
        mock_create.return_value = mock_orch
        
        result = await get_orchestrator(mock_request)
        
        assert result == mock_orch
        mock_create.assert_called_once()


# ============================================================================
# Tests for telegram_webhook endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_telegram_webhook_invalid_secret():
    """Test webhook with invalid secret token"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = "expected_secret"
        
        response = client.post(
            "/api/telegram/webhook",
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
        )
        
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_valid_secret_no_token():
    """Test webhook with valid secret but no token in header"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = "expected_secret"
        
        response = client.post(
            "/api/telegram/webhook",
            json={"update_id": 1},
        )
        
        # Should fail because secret is required but not provided
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_invalid_format():
    """Test webhook with invalid update format"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
        
        response = client.post(
            "/api/telegram/webhook",
            json={"invalid": "data"},
        )
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_telegram_webhook_start_command(mock_telegram_bot):
    """Test webhook with /start command"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
    with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
        response = client.post(
            "/api/telegram/webhook",
            json={
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "chat": {"id": 123},
                    "from": {"id": 1, "first_name": "User"},
                    "text": "/start",
                },
            },
        )
        
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args
        assert "Zantara" in call_args[1]["text"]


@pytest.mark.asyncio
async def test_telegram_webhook_help_command(mock_telegram_bot):
    """Test webhook with /help command"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
    with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
        response = client.post(
            "/api/telegram/webhook",
            json={
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "chat": {"id": 123},
                    "from": {"id": 1, "first_name": "User"},
                    "text": "/help",
                },
            },
        )
        
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args
        assert "How can I help you" in call_args[1]["text"]


@pytest.mark.asyncio
async def test_telegram_webhook_normal_message(mock_telegram_bot, mock_orchestrator, mock_request):
    """Test webhook with normal message"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = None
    app.state.search_service = None
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
    with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
        with patch("app.routers.telegram.get_orchestrator") as mock_get_orch:
            mock_get_orch.return_value = mock_orchestrator
            
            response = client.post(
                "/api/telegram/webhook",
                json={
                    "update_id": 1,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 123},
                        "from": {"id": 1, "first_name": "User"},
                        "text": "Hello, how are you?",
                    },
                },
            )
            
            assert response.status_code == 200
            assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_telegram_webhook_callback_approve(mock_telegram_bot, cleanup_pending_articles):
    """Test webhook with approve callback"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
    with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
        response = client.post(
            "/api/telegram/webhook",
            json={
                "update_id": 1,
                "callback_query": {
                    "id": "callback_123",
                    "from": {"id": 1, "first_name": "User1"},
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 123},
                        "text": "Test article",
                    },
                    "data": "approve:article_123",
                },
            },
        )
        
        assert response.status_code == 200
        assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_telegram_webhook_callback_invalid_action(mock_telegram_bot):
    """Test webhook with invalid callback action"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("app.routers.telegram.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
    with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
        response = client.post(
            "/api/telegram/webhook",
            json={
                "update_id": 1,
                "callback_query": {
                    "id": "callback_123",
                    "from": {"id": 1, "first_name": "User1"},
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 123},
                        "text": "Test article",
                    },
                    "data": "invalid_action",
                },
            },
        )
        
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_telegram_bot.answer_callback_query.assert_called_once()


# ============================================================================
# Tests for setup_webhook endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_setup_webhook_success(mock_telegram_bot):
    """Test setup_webhook success"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch.object(config.settings, "telegram_webhook_secret", "secret"):
            with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
                client = TestClient(app)
                response = client.post(
                    "/api/telegram/setup-webhook",
                    json={"webhook_url": "https://example.com/webhook"},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["webhook_url"] == "https://example.com/webhook"
                mock_telegram_bot.set_webhook.assert_called_once()


@pytest.mark.asyncio
async def test_setup_webhook_default_url(mock_telegram_bot):
    """Test setup_webhook with default URL"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch.object(config.settings, "telegram_webhook_secret", "secret"):
            with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
                client = TestClient(app)
                response = client.post(
                    "/api/telegram/setup-webhook",
                    json={},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "nuzantara-rag.fly.dev" in data["webhook_url"]


@pytest.mark.asyncio
async def test_setup_webhook_no_token():
    """Test setup_webhook without bot token"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", None):
        client = TestClient(app)
        response = client.post(
            "/api/telegram/setup-webhook",
            json={},
        )
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_setup_webhook_error(mock_telegram_bot):
    """Test setup_webhook with error"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch.object(config.settings, "telegram_webhook_secret", "secret"):
            with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
                mock_telegram_bot.set_webhook.side_effect = Exception("API Error")
                client = TestClient(app)
                response = client.post(
                    "/api/telegram/setup-webhook",
                    json={"webhook_url": "https://example.com/webhook"},
                )
                
                assert response.status_code == 500


# ============================================================================
# Tests for delete_webhook endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_delete_webhook_success(mock_telegram_bot):
    """Test delete_webhook success"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
            client = TestClient(app)
            response = client.delete("/api/telegram/webhook")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            mock_telegram_bot.delete_webhook.assert_called_once()


@pytest.mark.asyncio
async def test_delete_webhook_no_token():
    """Test delete_webhook without bot token"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", None):
        client = TestClient(app)
        response = client.delete("/api/telegram/webhook")
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_webhook_error(mock_telegram_bot):
    """Test delete_webhook with error"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
            mock_telegram_bot.delete_webhook.side_effect = Exception("API Error")
            client = TestClient(app)
            response = client.delete("/api/telegram/webhook")
            
            assert response.status_code == 500


# ============================================================================
# Tests for get_webhook_info endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_webhook_info_success(mock_telegram_bot):
    """Test get_webhook_info success"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
            client = TestClient(app)
            response = client.get("/api/telegram/webhook-info")
            
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            mock_telegram_bot.get_webhook_info.assert_called_once()


@pytest.mark.asyncio
async def test_get_webhook_info_no_token():
    """Test get_webhook_info without bot token"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", None):
        client = TestClient(app)
        response = client.get("/api/telegram/webhook-info")
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_webhook_info_error(mock_telegram_bot):
    """Test get_webhook_info with error"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
            mock_telegram_bot.get_webhook_info.side_effect = Exception("API Error")
            client = TestClient(app)
            response = client.get("/api/telegram/webhook-info")
            
            assert response.status_code == 500


# ============================================================================
# Tests for get_bot_info endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_bot_info_success(mock_telegram_bot):
    """Test get_bot_info success"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
            client = TestClient(app)
            response = client.get("/api/telegram/bot-info")
            
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            mock_telegram_bot.get_me.assert_called_once()


@pytest.mark.asyncio
async def test_get_bot_info_no_token():
    """Test get_bot_info without bot token"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", None):
        client = TestClient(app)
        response = client.get("/api/telegram/bot-info")
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_bot_info_error(mock_telegram_bot):
    """Test get_bot_info with error"""
    from app.routers.telegram import router
    from fastapi import FastAPI
    from app.core import config
    
    app = FastAPI()
    app.include_router(router)
    
    with patch.object(config.settings, "telegram_bot_token", "test_token"):
        with patch("app.routers.telegram.telegram_bot", mock_telegram_bot):
            mock_telegram_bot.get_me.side_effect = Exception("API Error")
            client = TestClient(app)
            response = client.get("/api/telegram/bot-info")
            
            assert response.status_code == 500

