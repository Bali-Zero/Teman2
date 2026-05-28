from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.routers import guardian


@pytest.fixture(autouse=True)
def admin_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        guardian,
        "settings",
        SimpleNamespace(admin_emails_set={"admin@example.com"}, admin_api_key="admin-secret"),
    )


def test_require_admin_accepts_admin_email() -> None:
    guardian._require_admin({"email": "admin@example.com", "role": "user"})


def test_require_admin_accepts_admin_role() -> None:
    guardian._require_admin({"email": "admin@internal", "role": "admin"})


def test_require_admin_rejects_non_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        guardian._require_admin({"email": "operator@example.com", "role": "user"})

    assert exc.value.status_code == 403


def test_get_admin_user_accepts_admin_api_key() -> None:
    request = SimpleNamespace(headers={"X-Debug-Key": "admin-secret"})

    user = guardian._get_admin_user(request, None)

    assert user["role"] == "admin"
    assert user["user_id"] == "admin-api-key"
