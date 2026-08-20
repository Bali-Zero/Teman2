"""Tests for the owner-only GARUDA VOA historical archive."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pydantic
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def _stored_result(hash_: str = "voa1234567890ab"):
    from backend.services.garuda_flow.eligibility import Decision
    from backend.services.garuda_flow.intake import CaseType, Purpose
    from backend.services.garuda_flow.repository import VoaCheckResult

    return VoaCheckResult(
        hash=hash_,
        case_type=CaseType.ISSUANCE,
        nationality="USA",
        entry_date=date(2026, 8, 1),
        passport_expiry_date=date(2027, 8, 1),
        voa_expiry_date=None,
        extension_already_used=False,
        purpose=Purpose.TOURISM,
        travellers=1,
        self_pay=True,
        decision=Decision.ACCEPT,
        decline_reasons=[],
        decline_codes=[],
        expiry_date=date(2026, 8, 31),
        last_legal_day=date(2026, 8, 31),
        expiry_is_estimated=True,
        published_filing_deadline=date(2026, 8, 24),
        submit_by_date=date(2026, 7, 31),
        price_idr=790_000,
        price_source="B1 Visa on Arrival (VOA)",
        view_count=3,
        share_count=0,
        created_at=datetime.now(timezone.utc),
    )


class TestVoaResponseBoundary:
    def test_response_has_only_archive_safe_fields(self) -> None:
        from backend.app.routers.garuda_voa import VoaResponse

        fields = VoaResponse.model_fields
        for forbidden in (
            "checkpoints",
            "internal_checkpoints",
            "client_facing_checkpoints",
            "filing_window_opens_date",
            "extension_window_opens_date",
            "pilot_threshold",
            "internal_escalation",
            "final_check",
            "reasons",
            "result_url",
        ):
            assert forbidden not in fields
        assert "published_filing_deadline" in fields
        assert "reason_codes" in fields

    def test_response_model_rejects_unknown_fields(self) -> None:
        from backend.app.routers.garuda_voa import VoaResponse, _build_response

        payload = _build_response(_stored_result()).model_dump()
        payload["result_url"] = "/visa/voa/retired"
        with pytest.raises(pydantic.ValidationError):
            VoaResponse.model_validate(payload)


@pytest.mark.asyncio
async def test_get_voa_reads_back_the_stored_verdict(monkeypatch) -> None:
    from backend.app.routers import garuda_voa as router_mod

    repository = type("RepositorySpy", (), {})()
    repository.get_voa_check = AsyncMock(side_effect=lambda hash_: _stored_result(hash_))
    repository.save_voa_check = AsyncMock()
    monkeypatch.setattr(router_mod, "GarudaVoaRepository", lambda _pool: repository)

    response = await router_mod.get_voa(hash="voa1234567890ab", db_pool=None)

    assert response.hash == "voa1234567890ab"
    assert response.decision == "ACCEPT"
    assert response.published_filing_deadline == date(2026, 8, 24)
    assert response.submit_by_date == date(2026, 7, 31)
    assert response.price_idr == 790_000
    assert "result_url" not in response.model_dump()
    repository.get_voa_check.assert_awaited_once_with("voa1234567890ab")
    repository.save_voa_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_voa_missing_hash_returns_404(monkeypatch) -> None:
    from backend.app.routers import garuda_voa as router_mod

    async def _fake_load(self, hash_: str):
        return None

    monkeypatch.setattr(router_mod.GarudaVoaRepository, "get_voa_check", _fake_load)

    with pytest.raises(HTTPException) as exc_info:
        await router_mod.get_voa(hash="doesnotexist00", db_pool=None)
    assert exc_info.value.status_code == 404


def _auth_test_app(user_dependency) -> FastAPI:
    from backend.app.dependencies import get_database_pool
    from backend.app.deps.auth import get_current_user
    from backend.app.routers import garuda_voa as router_mod

    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_database_pool] = lambda: None
    app.dependency_overrides[get_current_user] = user_dependency
    return app


def test_archive_route_table_has_get_and_no_post() -> None:
    from backend.app.routers import garuda_voa as router_mod

    methods_by_path = {
        route.path: set(route.methods or set())
        for route in router_mod.router.routes
        if hasattr(route, "methods")
    }
    assert methods_by_path["/api/visa/voa/{hash}"] == {"GET"}
    assert "/api/visa/voa" not in methods_by_path
    assert all("POST" not in methods for methods in methods_by_path.values())


@pytest.mark.parametrize("path", ["/api/visa/voa", "/api/visa/voa/voa1234567890ab"])
def test_garuda_voa_paths_are_absent_from_public_registry(path: str) -> None:
    from backend.app.auth.public_endpoints import find_entry

    assert find_entry(path) is None


def test_owner_archive_is_hidden_from_public_openapi() -> None:
    app = _auth_test_app(lambda: {"email": "owner@example.test", "role": "admin"})

    paths = app.openapi()["paths"]
    assert "/api/visa/voa" not in paths
    assert "/api/visa/voa/{hash}" not in paths


def test_post_archive_creator_is_removed_even_for_owner() -> None:
    async def _owner() -> dict[str, str]:
        return {"email": "owner@example.test", "role": "admin"}

    response = TestClient(_auth_test_app(_owner)).post(
        "/api/visa/voa",
        json={"case_type": "extension"},
    )
    assert response.status_code == 404


def test_anonymous_cannot_read_owner_archive() -> None:
    async def _anonymous() -> dict[str, object]:
        raise HTTPException(status_code=401, detail="Authentication required")

    response = TestClient(_auth_test_app(_anonymous)).get("/api/visa/voa/voa1234567890ab")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "user",
    [
        {"email": "staff@balizero.com", "role": "staff"},
        {"email": "client@example.test", "role": "client"},
    ],
)
def test_non_owner_cannot_read_owner_archive(user: dict[str, str]) -> None:
    async def _current_user() -> dict[str, str]:
        return user

    response = TestClient(_auth_test_app(_current_user)).get("/api/visa/voa/voa1234567890ab")
    assert response.status_code == 403
    assert response.json() == {"detail": "Owner access required"}


def test_owner_can_read_historical_archive(monkeypatch) -> None:
    from backend.app.routers import garuda_voa as router_mod

    async def _get(self, hash_: str):
        return _stored_result(hash_)

    monkeypatch.setattr(router_mod.GarudaVoaRepository, "get_voa_check", _get)

    async def _owner() -> dict[str, str]:
        return {"email": "zero@balizero.com", "role": "admin"}

    response = TestClient(_auth_test_app(_owner)).get("/api/visa/voa/voa1234567890ab")
    assert response.status_code == 200
    assert response.json()["hash"] == "voa1234567890ab"
    assert "result_url" not in response.json()


def test_owner_archive_deduplicates_historical_decline_codes(monkeypatch) -> None:
    from backend.app.routers import garuda_voa as router_mod
    from backend.services.garuda_flow.eligibility import Decision

    saved = replace(
        _stored_result(),
        decision=Decision.DECLINE,
        decline_codes=[
            "PURPOSE_NOT_ELIGIBLE",
            "GROUP_CASE",
            "GROUP_CASE",
            "PURPOSE_NOT_ELIGIBLE",
        ],
    )

    async def _get(self, hash_: str):
        return saved

    monkeypatch.setattr(router_mod.GarudaVoaRepository, "get_voa_check", _get)

    async def _owner() -> dict[str, str]:
        return {"email": "zero@balizero.com", "role": "admin"}

    response = TestClient(_auth_test_app(_owner)).get("/api/visa/voa/voa1234567890ab")

    assert response.status_code == 200
    assert response.json()["reason_codes"] == ["PURPOSE_NOT_ELIGIBLE", "GROUP_CASE"]


def test_owner_archive_unknown_decline_code_fails_closed_without_leak(
    monkeypatch,
    caplog,
) -> None:
    from backend.app.routers import garuda_voa as router_mod
    from backend.services.garuda_flow.eligibility import Decision

    unknown_code = "UNKNOWN_ARCHIVE_CODE_DO_NOT_LEAK"
    saved = replace(
        _stored_result(),
        decision=Decision.DECLINE,
        decline_codes=[unknown_code],
    )

    async def _get(self, hash_: str):
        return saved

    monkeypatch.setattr(router_mod.GarudaVoaRepository, "get_voa_check", _get)

    async def _owner() -> dict[str, str]:
        return {"email": "zero@balizero.com", "role": "admin"}

    response = TestClient(_auth_test_app(_owner)).get("/api/visa/voa/voa1234567890ab")

    assert response.status_code == 500
    assert response.json() == {"detail": "Could not load VOA check"}
    assert unknown_code not in response.text
    assert unknown_code not in caplog.text
