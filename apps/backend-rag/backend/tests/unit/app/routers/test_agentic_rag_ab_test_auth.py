"""Guilt/innocence for the two agentic_rag.py A/B-test endpoints.

2026-08-19 audit (Defect 2): `control_ab_test_experiment` and
`get_user_exposure` tested `role == "client"` instead of routing through
service_accounts.is_human_team_member. A service account (e.g. the
"monitoring" login-healthcheck probe) is not a client, but it is also not a
colleague — it must not be able to flip an A/B experiment live, nor read
another user's exposure history.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.routers.agentic_rag import (
    ABTestControlRequest,
    control_ab_test_experiment,
    get_user_exposure,
)


class _FakeAbManager:
    def __init__(self) -> None:
        self.enabled: list[str] = []
        self.disabled: list[str] = []

    def enable_experiment(self, experiment: str) -> bool:
        self.enabled.append(experiment)
        return True

    def disable_experiment(self, experiment: str) -> bool:
        self.disabled.append(experiment)
        return True


class _FakeTracker:
    async def get_user_exposure(self, user_id: str) -> dict[str, object]:
        return {"user_id": user_id, "experiments": []}


@pytest.fixture(autouse=True)
def _fake_ab_infra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.routers.agentic_rag.get_ab_test_manager",
        lambda: _FakeAbManager(),
    )
    monkeypatch.setattr(
        "backend.app.routers.agentic_rag.get_metrics_tracker",
        lambda: _FakeTracker(),
    )


@pytest.mark.asyncio
async def test_control_ab_test_rejects_monitoring_service_account() -> None:
    """Guilt: the probe must not be able to flip a live A/B experiment."""
    with pytest.raises(HTTPException) as exc:
        await control_ab_test_experiment(
            experiment="visa_prompt_v2",
            request=ABTestControlRequest(enabled=True),
            current_user={"email": "probe@balizero.com", "role": "monitoring"},
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_control_ab_test_allows_a_realistic_free_text_role() -> None:
    """Innocence: a real, free-text team-role title must still pass."""
    response = await control_ab_test_experiment(
        experiment="visa_prompt_v2",
        request=ABTestControlRequest(enabled=True),
        current_user={"email": "damar@balizero.com", "role": "Specialist Advisor"},
    )
    assert response["status"] == "updated"


@pytest.mark.asyncio
async def test_get_user_exposure_rejects_monitoring_reading_someone_elses_history() -> None:
    """Guilt: the probe reading another user's exposure history is denied."""
    with pytest.raises(HTTPException) as exc:
        await get_user_exposure(
            user_id="someone-else@balizero.com",
            current_user={"email": "probe@balizero.com", "role": "monitoring"},
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_user_exposure_allows_viewing_own_history_regardless_of_role() -> None:
    """Innocence (existing behavior preserved): anyone may view their own
    exposure history, service account or not — the guard only fires when the
    caller is non-human AND asking about someone else."""
    response = await get_user_exposure(
        user_id="probe@balizero.com",
        current_user={"email": "probe@balizero.com", "role": "monitoring"},
    )
    assert response["user_id"] == "probe@balizero.com"


@pytest.mark.asyncio
async def test_get_user_exposure_allows_a_realistic_free_text_role() -> None:
    """Innocence: a real, free-text team-role title viewing another user's
    history must still pass."""
    response = await get_user_exposure(
        user_id="client@example.com",
        current_user={"email": "surya@balizero.com", "role": "Tax Care"},
    )
    assert response["user_id"] == "client@example.com"
