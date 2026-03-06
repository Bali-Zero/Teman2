"""
Intelligence Center - Telegram Approval Teams Configuration

Defines who receives Telegram notifications for approval voting.
"""

from typing import TypedDict


class ApproverConfig(TypedDict):
    """Single approver configuration."""

    name: str
    chat_id: int
    email: str


class IntelTeamConfig(TypedDict):
    """Team configuration for intel approval."""

    type: str  # "news" or "visa"
    required_votes: int
    approvers: list[ApproverConfig]


# News Room Team - Solo owner approval
NEWS_TEAM: IntelTeamConfig = {
    "type": "news",
    "required_votes": 1,
    "approvers": [
        {"name": "Zero", "chat_id": 8032150393, "email": "zero@balizero.com"},
    ],
}

# Visa Oracle Team - Solo owner approval
VISA_TEAM: IntelTeamConfig = {
    "type": "visa",
    "required_votes": 1,
    "approvers": [
        {"name": "Zero", "chat_id": 8032150393, "email": "zero@balizero.com"},
    ],
}

# Lookup by type
INTEL_TEAMS = {"news": NEWS_TEAM, "visa": VISA_TEAM}


def get_team_config(intel_type: str) -> IntelTeamConfig | None:
    """Get team configuration for intel type."""
    return INTEL_TEAMS.get(intel_type)


def get_chat_ids(intel_type: str) -> list[int]:
    """Get list of chat IDs to notify for this intel type."""
    config = get_team_config(intel_type)
    if not config:
        return []
    return [approver["chat_id"] for approver in config["approvers"]]


def get_required_votes(intel_type: str) -> int:
    """Get required votes for approval."""
    config = get_team_config(intel_type)
    return config["required_votes"] if config else 2
