"""Tests that submit_match emits a session_jwt usable for chat auth."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

from backend.app.core.config import settings


@pytest.fixture
def response_builder():
    """Import lazily — the endpoint imports settings at module load."""
    from backend.app.routers.visa_check import MatchResponse
    return MatchResponse


def _decode(token: str) -> dict:
    return jwt.decode(
        token, settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"verify_exp": False},
    )


def test_match_response_schema_exposes_session_jwt(response_builder):
    # Smoke: MatchResponse must declare the `session_jwt` field.
    fields = response_builder.model_fields
    assert "session_jwt" in fields, "MatchResponse missing session_jwt field"


@pytest.mark.asyncio
async def test_submit_match_returns_valid_jwt_with_check_hash_claim(monkeypatch):
    from backend.app.routers import visa_check as router_mod

    # Build a fake result so we only exercise the router's JWT path.
    class _FakeResult:
        recommended_visa = None  # simplest path: referral_mode=true
        reason = "Let's WhatsApp"
        pre_arrival_steps: list[str] = []
        alternatives: list = []
        referral_mode = True

    async def _fake_save_match(self, **kwargs):
        from backend.services.visa_check.repository import VisaMatchResult
        return VisaMatchResult(
            hash="abc1234567890000",
            nationality=kwargs["nationality"],
            purpose=kwargs["purpose"],
            duration_months=kwargs["duration_months"],
            budget_band=kwargs["budget_band"],
            recommended_visa=None,
            recommendation_reason=kwargs["recommendation_reason"],
            pre_arrival_steps=[],
            alternatives=[],
            expected_arrival_date=None,
            estimated_cost_idr=None,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        router_mod, "recommend_visa",
        lambda **_: _FakeResult(),
    )
    monkeypatch.setattr(
        router_mod.VisaCheckRepository, "save_match", _fake_save_match,
    )

    payload = router_mod.MatchRequest(
        nationality="USA", purpose=router_mod.Purpose.OTHER,
        duration_months=12, budget_band=router_mod.BudgetBand.MID_50_500M,
    )
    response = await router_mod.submit_match(payload, db_pool=None)
    assert response.session_jwt
    claims = _decode(response.session_jwt)
    assert claims["sub"] == "abc1234567890000"
    assert claims["type"] == "visa_funnel"
    assert "iat" in claims
    assert "exp" in claims
    assert claims["exp"] - claims["iat"] == 3600  # 1 hour TTL


@pytest.mark.asyncio
async def test_get_match_does_not_regenerate_jwt(monkeypatch):
    """GET /api/visa/match/{hash} should NOT issue a JWT — it is a read
    endpoint used to re-render the result page from a shareable URL.
    Chat auth must be obtained fresh from submit_match."""
    from backend.app.routers import visa_check as router_mod

    async def _fake_load(self, hash_: str) -> object:
        from backend.services.visa_check.repository import VisaMatchResult
        return VisaMatchResult(
            hash="xyz1234567890000", nationality="USA", purpose="work_remote",
            duration_months=12, budget_band="50m_500m",
            recommended_visa=None, recommendation_reason="...",
            pre_arrival_steps=[], alternatives=[],
            expected_arrival_date=None, estimated_cost_idr=None,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(router_mod.VisaCheckRepository, "load_match", _fake_load)
    monkeypatch.setattr(router_mod.VisaCheckRepository, "bump_view_count", AsyncMock())

    response = await router_mod.get_match(hash="xyz1234567890000", db_pool=None)
    # session_jwt is optional on GET; we assert it's absent or null-ish.
    assert getattr(response, "session_jwt", None) in (None, "")
