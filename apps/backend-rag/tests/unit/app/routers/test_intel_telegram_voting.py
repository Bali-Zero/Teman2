"""
Unit tests for Intelligence Center Telegram voting system.

Tests the 2/3 majority voting mechanism for intel item approval.

Coverage:
- First vote recording
- Majority approval (2/3)
- Majority rejection (2/3)
- Duplicate vote prevention
- Voting closed handling
- Vote tally updates
"""

import json
from datetime import datetime
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_pending_dir(tmp_path):
    """Create temporary pending_intel directory"""
    pending_dir = tmp_path / "pending_intel"
    pending_dir.mkdir()
    return pending_dir


@pytest.fixture
def mock_staging_dir(tmp_path):
    """Create temporary staging directory with test file"""
    staging_dir = tmp_path / "staging" / "visa"
    staging_dir.mkdir(parents=True)

    # Create test staging file
    test_item = {
        "item_id": "visa_20260105_abc123",
        "title": "E33E Retirement Visa Update",
        "content": "The E33E visa requirements have changed...",
        "source_url": "https://imigrasi.go.id/e33e",
        "intel_type": "visa",
        "tier": "T1",
    }

    staging_file = staging_dir / "visa_20260105_abc123.json"
    staging_file.write_text(json.dumps(test_item, indent=2))

    return staging_dir


@pytest.fixture
def mock_team_config():
    """Mock team configuration"""
    return {
        "type": "visa",
        "required_votes": 2,
        "approvers": [
            {"name": "Zero", "chat_id": 8290313965, "email": "zero@balizero.com"},
            {"name": "Dea", "chat_id": 6217157548, "email": "dea@balizero.com"},
            {"name": "Damar", "chat_id": 1813875994, "email": "damar@balizero.com"},
        ],
    }


# --- VOTE RECORDING TESTS ---


def test_vote_approve_first_vote(mock_pending_dir, mock_team_config):
    """Test first APPROVE vote is recorded correctly"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test1"
    intel_type = "visa"
    user = {"id": 8290313965, "first_name": "Zero"}

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Create initial voting status
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {"approve": [], "reject": []},
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Cast first vote
        data, result = add_intel_vote(item_id, intel_type, "approve", user)

        assert result == "vote_recorded"
        assert len(data["votes"]["approve"]) == 1
        assert data["votes"]["approve"][0]["user_id"] == 8290313965
        assert data["votes"]["approve"][0]["user_name"] == "Zero"
        assert data["status"] == "voting"  # Still voting


def test_vote_approve_majority_reached(mock_pending_dir, mock_team_config):
    """Test APPROVE majority (2/3) triggers approval"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test2"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Create voting status with 1 approve vote already
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {
                "approve": [
                    {"user_id": 8290313965, "user_name": "Zero", "voted_at": "2026-01-05T10:00:00"}
                ],
                "reject": [],
            },
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Second vote (Dea) → should trigger approval
        user = {"id": 6217157548, "first_name": "Dea"}
        data, result = add_intel_vote(item_id, intel_type, "approve", user)

        assert result == "approved"
        assert len(data["votes"]["approve"]) == 2
        assert data["status"] == "approved"  # Status changed


def test_vote_reject_majority_reached(mock_pending_dir, mock_team_config):
    """Test REJECT majority (2/3) triggers rejection"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test3"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Create voting status with 1 reject vote already
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {
                "approve": [],
                "reject": [
                    {"user_id": 8290313965, "user_name": "Zero", "voted_at": "2026-01-05T10:00:00"}
                ],
            },
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Second reject vote (Damar) → should trigger rejection
        user = {"id": 1813875994, "first_name": "Damar"}
        data, result = add_intel_vote(item_id, intel_type, "reject", user)

        assert result == "rejected"
        assert len(data["votes"]["reject"]) == 2
        assert data["status"] == "rejected"


# --- DUPLICATE VOTE PREVENTION ---


def test_vote_duplicate_vote_rejected(mock_pending_dir, mock_team_config):
    """Test user cannot vote twice"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test4"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Create voting status with Zero already voted APPROVE
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {
                "approve": [
                    {"user_id": 8290313965, "user_name": "Zero", "voted_at": "2026-01-05T10:00:00"}
                ],
                "reject": [],
            },
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Zero tries to vote again (REJECT this time)
        user = {"id": 8290313965, "first_name": "Zero"}
        data, result = add_intel_vote(item_id, intel_type, "reject", user)

        assert result == "already_voted"
        assert len(data["votes"]["approve"]) == 1  # No change
        assert len(data["votes"]["reject"]) == 0  # Not added


def test_vote_duplicate_across_types(mock_pending_dir, mock_team_config):
    """Test user who voted APPROVE cannot vote REJECT"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test5"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Dea voted APPROVE
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {
                "approve": [
                    {"user_id": 6217157548, "user_name": "Dea", "voted_at": "2026-01-05T10:00:00"}
                ],
                "reject": [],
            },
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Dea tries to change mind and vote REJECT
        user = {"id": 6217157548, "first_name": "Dea"}
        data, result = add_intel_vote(item_id, intel_type, "reject", user)

        assert result == "already_voted"


# --- VOTING CLOSED HANDLING ---


def test_vote_closed_voting_approved(mock_pending_dir, mock_team_config):
    """Test cannot vote on already approved item"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test6"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Create voting status already APPROVED
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "approved",  # Voting closed
            "votes": {
                "approve": [
                    {"user_id": 8290313965, "user_name": "Zero"},
                    {"user_id": 6217157548, "user_name": "Dea"},
                ],
                "reject": [],
            },
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Damar tries to vote REJECT after closing
        user = {"id": 1813875994, "first_name": "Damar"}
        data, result = add_intel_vote(item_id, intel_type, "reject", user)

        assert result == "voting_closed"
        assert len(data["votes"]["reject"]) == 0  # Vote not recorded


def test_vote_closed_voting_rejected(mock_pending_dir, mock_team_config):
    """Test cannot vote on already rejected item"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test7"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Create voting status already REJECTED
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "rejected",  # Voting closed
            "votes": {
                "approve": [],
                "reject": [
                    {"user_id": 8290313965, "user_name": "Zero"},
                    {"user_id": 1813875994, "user_name": "Damar"},
                ],
            },
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Dea tries to vote APPROVE after closing
        user = {"id": 6217157548, "first_name": "Dea"}
        data, result = add_intel_vote(item_id, intel_type, "approve", user)

        assert result == "voting_closed"


# --- VOTE TALLY UPDATES ---


def test_vote_tally_mixed_votes(mock_pending_dir, mock_team_config):
    """Test tally with mixed approve/reject votes"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test8"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Zero voted APPROVE, Dea voted REJECT
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {
                "approve": [
                    {"user_id": 8290313965, "user_name": "Zero", "voted_at": "2026-01-05T10:00:00"}
                ],
                "reject": [
                    {"user_id": 6217157548, "user_name": "Dea", "voted_at": "2026-01-05T10:05:00"}
                ],
            },
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Damar votes APPROVE → should reach 2/3 approval
        user = {"id": 1813875994, "first_name": "Damar"}
        data, result = add_intel_vote(item_id, intel_type, "approve", user)

        assert result == "approved"
        assert len(data["votes"]["approve"]) == 2  # Zero + Damar
        assert len(data["votes"]["reject"]) == 1  # Dea


def test_format_vote_tally_display(mock_team_config):
    """Test vote tally formatting for display"""
    from app.routers.telegram import format_intel_vote_tally

    intel_data = {
        "votes": {
            "approve": [
                {"user_name": "Zero"},
                {"user_name": "Damar"},
            ],
            "reject": [
                {"user_name": "Dea"},
            ],
        }
    }

    original_text = "🛂 New Visa Update\n\nE33E Requirements Changed"

    with patch("app.routers.telegram.get_required_votes", return_value=2):
        tally = format_intel_vote_tally(intel_data, "visa", original_text)

        # Verify tally contains key elements
        assert "📊 VOTAZIONE IN CORSO" in tally
        assert "Voti: ✅ 2/2 | ❌ 1/2" in tally
        assert "Zero ✅" in tally
        assert "Damar ✅" in tally
        assert "Dea ❌" in tally
        assert "Servono 2 voti per decidere" in tally


# --- EDGE CASES ---


def test_vote_new_file_creation(mock_pending_dir, mock_team_config):
    """Test get_intel_status creates default status if file doesn't exist (defensive)"""
    from app.routers.telegram import get_intel_status

    item_id = "visa_20260105_new"

    with patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir):
        # No file exists yet - get_intel_status should return default status
        # (In production, file is created by send_intel_approval_notification)

        # This test verifies defensive programming
        status = get_intel_status(item_id)

        assert status["item_id"] == item_id
        assert status["status"] == "voting"
        assert status["votes"] == {"approve": [], "reject": []}
        assert "created_at" in status


def test_vote_concurrent_votes_same_type(mock_pending_dir, mock_team_config):
    """Test two users vote APPROVE at nearly same time"""
    from app.routers.telegram import add_intel_vote

    item_id = "visa_20260105_test9"
    intel_type = "visa"

    with (
        patch("app.routers.telegram.PENDING_INTEL_PATH", mock_pending_dir),
        patch("app.routers.telegram.get_team_config", return_value=mock_team_config),
        patch("app.routers.telegram.get_required_votes", return_value=2),
    ):
        # Initial empty state
        voting_status = {
            "item_id": item_id,
            "intel_type": intel_type,
            "status": "voting",
            "votes": {"approve": [], "reject": []},
            "created_at": datetime.now().isoformat(),
        }
        status_file = mock_pending_dir / f"{item_id}.json"
        status_file.write_text(json.dumps(voting_status))

        # Zero votes APPROVE
        user1 = {"id": 8290313965, "first_name": "Zero"}
        data1, result1 = add_intel_vote(item_id, intel_type, "approve", user1)

        assert result1 == "vote_recorded"

        # Dea votes APPROVE (reads updated file)
        user2 = {"id": 6217157548, "first_name": "Dea"}
        data2, result2 = add_intel_vote(item_id, intel_type, "approve", user2)

        assert result2 == "approved"  # Majority reached
        assert len(data2["votes"]["approve"]) == 2
