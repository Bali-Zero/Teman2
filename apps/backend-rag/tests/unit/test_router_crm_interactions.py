"""
Unit tests for CRM Interactions Router
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.crm_interactions import (
    InteractionCreate,
    InteractionResponse,
    create_interaction,
    get_interaction,
    list_interactions,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg connection pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_request():
    """Mock FastAPI request object"""
    request = MagicMock()
    request.state = MagicMock()
    return request


@pytest.fixture
def sample_interaction_data():
    """Sample interaction data"""
    return {
        "id": 1,
        "client_id": 1,
        "practice_id": None,
        "interaction_type": "chat",
        "channel": "web_chat",
        "subject": "Test interaction",
        "summary": "Test summary",
        "team_member": "team@example.com",
        "direction": "inbound",
        "sentiment": "positive",
        "interaction_date": datetime.now(),
        "created_at": datetime.now(),
    }


# ============================================================================
# Tests for create_interaction
# ============================================================================


@pytest.mark.asyncio
async def test_create_interaction_success(mock_asyncpg_pool, mock_request, sample_interaction_data):
    """Test successful interaction creation"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_interaction_data)
    conn.execute = AsyncMock()

    interaction_data = InteractionCreate(
        client_id=1,
        interaction_type="chat",
        channel="web_chat",
        team_member="team@example.com",
        summary="Test summary",
    )

    result = await create_interaction(interaction_data, request=mock_request, db_pool=pool)

    assert isinstance(result, InteractionResponse)
    assert result.interaction_type == "chat"
    assert result.team_member == "team@example.com"


@pytest.mark.asyncio
async def test_create_interaction_database_error(mock_asyncpg_pool, mock_request):
    """Test interaction creation with database error"""
    from fastapi import HTTPException

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    interaction_data = InteractionCreate(interaction_type="chat", team_member="team@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await create_interaction(interaction_data, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_interactions
# ============================================================================


@pytest.mark.asyncio
async def test_get_interactions_success(mock_asyncpg_pool, mock_request, sample_interaction_data):
    """Test successful interactions retrieval"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_interaction_data])

    result = await list_interactions(limit=10, offset=0, request=mock_request, db_pool=pool)

    assert isinstance(result, list)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_interactions_with_filters(
    mock_asyncpg_pool, mock_request, sample_interaction_data
):
    """Test interactions retrieval with filters"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_interaction_data])

    result = await list_interactions(
        limit=10,
        offset=0,
        client_id=1,
        interaction_type="chat",
        team_member="team@example.com",
        request=mock_request,
        db_pool=pool,
    )

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_interactions_empty(mock_asyncpg_pool, mock_request):
    """Test interactions retrieval with no results"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await list_interactions(request=mock_request, db_pool=pool)

    assert isinstance(result, list)
    assert len(result) == 0


# ============================================================================
# Tests for get_interaction
# ============================================================================


@pytest.mark.asyncio
async def test_get_interaction_success(mock_asyncpg_pool, mock_request, sample_interaction_data):
    """Test successful interaction retrieval by ID"""
    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=sample_interaction_data)

    result = await get_interaction(interaction_id=1, request=mock_request, db_pool=pool)

    # Result can be dict or InteractionResponse depending on implementation
    if isinstance(result, dict):
        assert result["id"] == 1
        assert result["interaction_type"] == "chat"
    else:
        assert isinstance(result, InteractionResponse)
        assert result.id == 1
        assert result.interaction_type == "chat"


@pytest.mark.asyncio
async def test_get_interaction_not_found(mock_asyncpg_pool, mock_request):
    """Test interaction retrieval with non-existent ID"""
    from fastapi import HTTPException

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_interaction(interaction_id=999, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 404


# ============================================================================
# Tests for get_client_timeline
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_timeline_success(mock_asyncpg_pool, mock_request):
    """Test successful client timeline retrieval"""
    from app.routers.crm_interactions import get_client_timeline

    pool, conn = mock_asyncpg_pool
    timeline_data = [
        {
            "id": 1,
            "client_id": 1,
            "interaction_type": "chat",
            "interaction_date": datetime.now(),
            "practice_id": 1,
            "practice_type_name": "KITAS",
            "practice_type_code": "kitas",
        }
    ]
    conn.fetch = AsyncMock(return_value=timeline_data)

    result = await get_client_timeline(client_id=1, limit=50, request=mock_request, db_pool=pool)

    assert result["client_id"] == 1
    assert result["total_interactions"] == 1
    assert len(result["timeline"]) == 1


@pytest.mark.asyncio
async def test_get_client_timeline_empty(mock_asyncpg_pool, mock_request):
    """Test client timeline with no interactions"""
    from app.routers.crm_interactions import get_client_timeline

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await get_client_timeline(client_id=999, limit=50, request=mock_request, db_pool=pool)

    assert result["client_id"] == 999
    assert result["total_interactions"] == 0
    assert len(result["timeline"]) == 0


@pytest.mark.asyncio
async def test_get_client_timeline_error(mock_asyncpg_pool, mock_request):
    """Test client timeline with database error"""
    from fastapi import HTTPException

    from app.routers.crm_interactions import get_client_timeline

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_client_timeline(client_id=1, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_practice_history
# ============================================================================


@pytest.mark.asyncio
async def test_get_practice_history_success(mock_asyncpg_pool, mock_request):
    """Test successful practice history retrieval"""
    from app.routers.crm_interactions import get_practice_history

    pool, conn = mock_asyncpg_pool
    history_data = [
        {
            "id": 1,
            "practice_id": 1,
            "interaction_type": "email",
            "interaction_date": datetime.now(),
        }
    ]
    conn.fetch = AsyncMock(return_value=history_data)

    result = await get_practice_history(practice_id=1, request=mock_request, db_pool=pool)

    assert result["practice_id"] == 1
    assert result["total_interactions"] == 1
    assert len(result["history"]) == 1


@pytest.mark.asyncio
async def test_get_practice_history_empty(mock_asyncpg_pool, mock_request):
    """Test practice history with no interactions"""
    from app.routers.crm_interactions import get_practice_history

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[])

    result = await get_practice_history(practice_id=999, request=mock_request, db_pool=pool)

    assert result["practice_id"] == 999
    assert result["total_interactions"] == 0


@pytest.mark.asyncio
async def test_get_practice_history_error(mock_asyncpg_pool, mock_request):
    """Test practice history with database error"""
    from fastapi import HTTPException

    from app.routers.crm_interactions import get_practice_history

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_practice_history(practice_id=1, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for get_interactions_stats
# ============================================================================


@pytest.mark.asyncio
async def test_get_interactions_stats_success(mock_asyncpg_pool, mock_request):
    """Test successful interaction stats retrieval"""
    from app.routers.crm_interactions import get_interactions_stats

    pool, conn = mock_asyncpg_pool

    # Mock stats data
    by_type = [
        {"interaction_type": "chat", "count": 10},
        {"interaction_type": "email", "count": 5},
    ]
    by_sentiment = [
        {"sentiment": "positive", "count": 8},
        {"sentiment": "neutral", "count": 7},
    ]
    by_team_member = [
        {"team_member": "anton@balizero.com", "count": 12},
        {"team_member": "amanda@balizero.com", "count": 3},
    ]
    recent_count = {"count": 8}

    # Configure conn to return different values for different queries
    conn.fetch = AsyncMock(side_effect=[by_type, by_sentiment, by_team_member])
    conn.fetchrow = AsyncMock(return_value=recent_count)

    # Use __wrapped__ to bypass cache decorator
    result = await get_interactions_stats.__wrapped__(
        team_member=None, request=mock_request, db_pool=pool
    )

    assert result["total_interactions"] == 15
    assert result["last_7_days"] == 8
    assert "by_type" in result
    assert "by_sentiment" in result
    assert len(result["by_team_member"]) == 2


@pytest.mark.asyncio
async def test_get_interactions_stats_with_team_member_filter(mock_asyncpg_pool, mock_request):
    """Test interaction stats filtered by team member"""
    from app.routers.crm_interactions import get_interactions_stats

    pool, conn = mock_asyncpg_pool

    by_type = [{"interaction_type": "chat", "count": 5}]
    by_sentiment = [{"sentiment": "positive", "count": 4}]
    recent_count = {"count": 3}

    conn.fetch = AsyncMock(side_effect=[by_type, by_sentiment])
    conn.fetchrow = AsyncMock(return_value=recent_count)

    # Use __wrapped__ to bypass cache decorator
    result = await get_interactions_stats.__wrapped__(
        team_member="anton@balizero.com", request=mock_request, db_pool=pool
    )

    assert result["total_interactions"] == 5
    assert result["by_team_member"] == []


@pytest.mark.asyncio
async def test_get_interactions_stats_error(mock_asyncpg_pool, mock_request):
    """Test interaction stats with database error"""
    from fastapi import HTTPException

    from app.routers.crm_interactions import get_interactions_stats

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    # Use __wrapped__ to bypass cache decorator
    with pytest.raises(HTTPException) as exc_info:
        await get_interactions_stats.__wrapped__(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for create_interaction_from_conversation
# ============================================================================


@pytest.mark.asyncio
async def test_create_interaction_from_conversation_existing_client(
    mock_asyncpg_pool, mock_request
):
    """Test creating interaction from conversation with existing client"""
    from app.routers.crm_interactions import create_interaction_from_conversation

    pool, conn = mock_asyncpg_pool

    # Mock existing client
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": 1},  # Existing client
            {  # Conversation data
                "messages": [
                    {"role": "user", "content": "Hello, I need help with KITAS"},
                    {"role": "assistant", "content": "Sure, I can help!"},
                ]
            },
            {"id": 1, "client_id": 1},  # New interaction
        ]
    )

    result = await create_interaction_from_conversation(
        conversation_id=1,
        client_email="test@example.com",
        team_member="anton@balizero.com",
        request=mock_request,
        db_pool=pool,
    )

    assert result["success"] is True
    assert result["client_id"] == 1
    assert result["interaction_id"] == 1


@pytest.mark.asyncio
async def test_create_interaction_from_conversation_new_client(mock_asyncpg_pool, mock_request):
    """Test creating interaction from conversation with new client"""
    from app.routers.crm_interactions import create_interaction_from_conversation

    pool, conn = mock_asyncpg_pool

    # Mock no existing client (creates new one)
    conn.fetchrow = AsyncMock(
        side_effect=[
            None,  # No existing client
            {"id": 2},  # New client created
            {  # Conversation data
                "messages": [{"role": "user", "content": "Hello"}]
            },
            {"id": 1, "client_id": 2},  # New interaction
        ]
    )

    result = await create_interaction_from_conversation(
        conversation_id=1,
        client_email="newclient@example.com",
        team_member="anton@balizero.com",
        request=mock_request,
        db_pool=pool,
    )

    assert result["success"] is True
    assert result["client_id"] == 2


@pytest.mark.asyncio
async def test_create_interaction_from_conversation_with_summary(mock_asyncpg_pool, mock_request):
    """Test creating interaction from conversation with provided summary"""
    from app.routers.crm_interactions import create_interaction_from_conversation

    pool, conn = mock_asyncpg_pool

    conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": 1},  # Existing client
            {"messages": []},  # Empty conversation
            {"id": 1, "client_id": 1},  # New interaction
        ]
    )

    result = await create_interaction_from_conversation(
        conversation_id=1,
        client_email="test@example.com",
        team_member="anton@balizero.com",
        summary="Custom summary",
        request=mock_request,
        db_pool=pool,
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_create_interaction_from_conversation_error(mock_asyncpg_pool, mock_request):
    """Test creating interaction from conversation with error"""
    from fastapi import HTTPException

    from app.routers.crm_interactions import create_interaction_from_conversation

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await create_interaction_from_conversation(
            conversation_id=1,
            client_email="test@example.com",
            team_member="anton@balizero.com",
            request=mock_request,
            db_pool=pool,
        )

    assert exc_info.value.status_code == 500


# ============================================================================
# Tests for sync_gmail_interactions
# ============================================================================


@pytest.mark.skip(reason="sync_gmail_interactions endpoint removed - MCP integration pending")
@pytest.mark.asyncio
async def test_sync_gmail_interactions_success(mock_asyncpg_pool, mock_request):
    """Test successful Gmail sync - SKIPPED: endpoint removed"""
    pass  # Endpoint removed - MCP integration pending

    pool, conn = mock_asyncpg_pool

    # Mock Gmail service
    mock_gmail = MagicMock()
    mock_gmail.list_messages.return_value = [{"id": "msg1"}, {"id": "msg2"}]
    mock_gmail.get_message_details.return_value = {
        "id": "msg1",
        "subject": "Test email",
        "from": "client@example.com",
    }

    # Mock AutoCRM service
    mock_auto_crm = MagicMock()
    mock_auto_crm.process_email_interaction = AsyncMock(
        return_value={"success": True, "interaction_id": 1}
    )

    with patch("services.gmail_service.get_gmail_service", return_value=mock_gmail):
        with patch("services.auto_crm_service.get_auto_crm_service", return_value=mock_auto_crm):
            result = await sync_gmail_interactions(
                limit=5, team_member="system", request=mock_request, db_pool=pool
            )

            assert result["success"] is True
            assert result["processed_count"] >= 0


@pytest.mark.skip(reason="sync_gmail_interactions endpoint removed - MCP integration pending")
@pytest.mark.skip(reason="sync_gmail_interactions endpoint removed - MCP integration pending")
@pytest.mark.asyncio
async def test_sync_gmail_interactions_no_messages(mock_asyncpg_pool, mock_request):
    """Test Gmail sync with no messages"""
    from app.routers.crm_interactions import sync_gmail_interactions

    pool, conn = mock_asyncpg_pool

    mock_gmail = MagicMock()
    mock_gmail.list_messages.return_value = []

    mock_auto_crm = MagicMock()

    with patch("services.gmail_service.get_gmail_service", return_value=mock_gmail):
        with patch("services.auto_crm_service.get_auto_crm_service", return_value=mock_auto_crm):
            result = await sync_gmail_interactions(limit=5, request=mock_request, db_pool=pool)

            assert result["success"] is True
            assert result["processed_count"] == 0


@pytest.mark.skip(reason="sync_gmail_interactions endpoint removed - MCP integration pending")
@pytest.mark.asyncio
async def test_sync_gmail_interactions_error(mock_asyncpg_pool, mock_request):
    """Test Gmail sync with error"""
    from fastapi import HTTPException

    from app.routers.crm_interactions import sync_gmail_interactions

    pool, conn = mock_asyncpg_pool

    with patch(
        "services.gmail_service.get_gmail_service", side_effect=Exception("Gmail API error")
    ):
        with pytest.raises(HTTPException) as exc_info:
            await sync_gmail_interactions(request=mock_request, db_pool=pool)

        assert exc_info.value.status_code == 500


# ============================================================================
# Tests for additional list_interactions filters
# ============================================================================


@pytest.mark.asyncio
async def test_list_interactions_with_practice_id_filter(
    mock_asyncpg_pool, mock_request, sample_interaction_data
):
    """Test interactions retrieval with practice_id filter"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_interaction_data])

    result = await list_interactions(practice_id=1, limit=10, request=mock_request, db_pool=pool)

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_interactions_with_sentiment_filter(
    mock_asyncpg_pool, mock_request, sample_interaction_data
):
    """Test interactions retrieval with sentiment filter"""
    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(return_value=[sample_interaction_data])

    result = await list_interactions(
        sentiment="positive", limit=10, request=mock_request, db_pool=pool
    )

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_interactions_database_error(mock_asyncpg_pool, mock_request):
    """Test interactions retrieval with database error"""
    from fastapi import HTTPException

    pool, conn = mock_asyncpg_pool
    conn.fetch = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await list_interactions(request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_interaction_database_error(mock_asyncpg_pool, mock_request):
    """Test interaction retrieval with database error"""
    from fastapi import HTTPException

    pool, conn = mock_asyncpg_pool
    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_interaction(interaction_id=1, request=mock_request, db_pool=pool)

    assert exc_info.value.status_code == 500
