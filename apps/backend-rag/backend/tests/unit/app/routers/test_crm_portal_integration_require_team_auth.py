"""Guilt/innocence for crm_portal_integration.py::require_team_auth.

2026-08-19 audit (Defect 2): this dependency tested `role == "client"`
instead of routing through service_accounts.is_human_team_member. It gates 8
LIVE endpoints, including sending messages to real clients — a service
account (e.g. the "monitoring" login-healthcheck probe, which authenticates
continuously) is not a client, but it is also not a colleague.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.routers.crm_portal_integration import require_team_auth


def test_require_team_auth_rejects_client() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_team_auth(current_user={"email": "client@example.com", "role": "client"})
    assert exc_info.value.status_code == 403


def test_require_team_auth_rejects_monitoring_service_account() -> None:
    """Guilt: the probe must not be able to send messages to real clients."""
    with pytest.raises(HTTPException) as exc_info:
        require_team_auth(current_user={"email": "probe@balizero.com", "role": "monitoring"})
    assert exc_info.value.status_code == 403


def test_require_team_auth_allows_a_realistic_free_text_role() -> None:
    """Innocence: a real, free-text team-role title must still pass."""
    user = {"email": "board@balizero.com", "role": "Board Member"}
    result = require_team_auth(current_user=user)
    assert result == user
