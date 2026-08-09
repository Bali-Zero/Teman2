"""Security contract tests for the shadow identity token issuer."""

from __future__ import annotations

import uuid

from jose import jwt

from backend.app.core.config import settings
from backend.app.modules.identity.models import User
from backend.app.modules.identity.service import IdentityService


def test_identity_access_token_matches_primary_session_contract() -> None:
    user = User(
        id="synthetic-user-id",
        name="Synthetic User",
        email="synthetic.user@example.test",
        pin_hash="synthetic-hash",
        role="client",
    )

    token = IdentityService().create_access_token(user, "synthetic-session-id")
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == "synthetic-user-id"
    assert payload["type"] == "access"
    assert payload["sessionId"] == "synthetic-session-id"
    uuid.UUID(payload["jti"])
    expected_lifetime = settings.jwt_access_token_expire_hours * 3600
    assert expected_lifetime - 2 <= payload["exp"] - payload["iat"] <= expected_lifetime + 1
