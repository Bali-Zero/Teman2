"""
Router tests for the CRM Partners module.

Strategy: mock at the PartnersService / CommissionEngine level so we test
HTTP routing, RBAC guards, request validation, and response shaping without
requiring a live database.

Fixture layout:
  - mock_db_pool: from root conftest — pool + conn AsyncMocks
  - fake_admin / fake_team / fake_partner: user dicts
  - app(role): parameterisable FastAPI app with dependency overrides
  - client_for(role): TestClient helper
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.partners as partners_module
from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.crm.partners.models import Partner

# ── Helpers ──────────────────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
_PARTNER_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_USER_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
_TEAM_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
_REFERRAL_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000001")
_COMMISSION_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
_PROCESS_ID = uuid.UUID("ffffffff-0000-0000-0000-000000000001")


def _make_partner(**overrides: Any) -> Partner:
    """Return a Partner dataclass instance for router tests."""
    defaults: dict[str, Any] = dict(
        id=_PARTNER_ID,
        full_name="Test Partner",
        email="partner@test.invalid",
        entity_type="individual",
        tax_withholding_category="tbd",
        default_commission_type="percentage",
        default_commission_value=Decimal("10.0"),
        onboarding_status="pending_approval",
        payment_currency="IDR",
        preferred_language="id",
        created_at=_NOW,
        updated_at=_NOW,
        assigned_to=_USER_ID,
    )
    defaults.update(overrides)
    return Partner(**defaults)


def _partner_dict(**overrides: Any) -> dict[str, Any]:
    """Return a plain dict representation for JSON responses."""
    d = {
        "id": str(_PARTNER_ID),
        "full_name": "Test Partner",
        "email": "partner@test.invalid",
        "entity_type": "individual",
        "tax_withholding_category": "tbd",
        "default_commission_type": "percentage",
        "default_commission_value": "10.0",
        "onboarding_status": "pending_approval",
        "payment_currency": "IDR",
        "preferred_language": "id",
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
        "assigned_to": str(_USER_ID),
        "work_role": None,
        "company_name": None,
    }
    d.update(overrides)
    return d


# ── User fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def fake_admin() -> dict[str, Any]:
    # CRIT-3: finance.mark_paid is now load-bearing — admin role alone is
    # insufficient. Admin users that perform finance actions must hold the perm.
    return {"user_id": str(_USER_ID), "email": "admin@balizero.com", "role": "admin", "permissions": ["finance.mark_paid"]}


@pytest.fixture
def fake_team() -> dict[str, Any]:
    return {"user_id": str(_TEAM_ID), "email": "team@balizero.com", "role": "team", "permissions": []}


@pytest.fixture
def fake_partner_user() -> dict[str, Any]:
    return {"user_id": str(_USER_ID), "email": "partner@balizero.com", "role": "partner", "permissions": []}


# ── App factories ────────────────────────────────────────────────────────────

def _make_app(user: dict[str, Any], pool: MagicMock) -> FastAPI:
    application = FastAPI()
    application.include_router(partners_module.router)
    application.dependency_overrides[get_current_user] = lambda: user
    application.dependency_overrides[get_database_pool] = lambda: pool
    return application


@pytest.fixture
def admin_app(fake_admin, mock_db_pool) -> tuple[FastAPI, TestClient, MagicMock, AsyncMock]:
    pool, conn = mock_db_pool
    app = _make_app(fake_admin, pool)
    return app, TestClient(app, raise_server_exceptions=False), pool, conn


@pytest.fixture
def team_app(fake_team, mock_db_pool) -> tuple[FastAPI, TestClient, MagicMock, AsyncMock]:
    pool, conn = mock_db_pool
    app = _make_app(fake_team, pool)
    return app, TestClient(app, raise_server_exceptions=False), pool, conn


@pytest.fixture
def partner_app(fake_partner_user, mock_db_pool) -> tuple[FastAPI, TestClient, MagicMock, AsyncMock]:
    pool, conn = mock_db_pool
    app = _make_app(fake_partner_user, pool)
    return app, TestClient(app, raise_server_exceptions=False), pool, conn


# ── 1. create_partner — team auto-assigns self ───────────────────────────────

class TestCreatePartner:
    @pytest.mark.unit
    def test_router_has_correct_prefix_and_routes(self) -> None:
        assert partners_module.router.prefix == "/api/partners"
        paths = {route.path for route in partners_module.router.routes}
        assert "/api/partners" in paths
        assert "/api/partners/{partner_id}" in paths

    @pytest.mark.unit
    def test_partner_create_model_validation(self) -> None:
        payload = partners_module.PartnerCreate.model_validate({
            "full_name": "Hotel Kama",
            "email": "h@k.io",
            "entity_type": "corporate_pt",
        })
        assert payload.full_name == "Hotel Kama"
        assert payload.default_commission_type == "percentage"
        assert payload.default_commission_value == Decimal("10.0")

    @pytest.mark.integration
    def test_create_partner_team_auto_assigns_self(self, team_app, fake_team) -> None:
        app, client, pool, conn = team_app
        partner = _make_partner(assigned_to=uuid.UUID(fake_team["user_id"]))
        with (
            patch("backend.app.routers.partners.PartnersService") as MockSvc,
        ):
            svc_instance = MockSvc.return_value
            svc_instance.create_partner = AsyncMock(return_value=_PARTNER_ID)
            svc_instance.repo = MagicMock()
            svc_instance.repo.get_partner = AsyncMock(return_value=partner)

            resp = client.post(
                "/api/partners",
                json={"full_name": "Hotel Kama", "email": "h@k.io", "entity_type": "corporate_pt"},
            )
        assert resp.status_code == 201
        # Verify create_partner was called with the team user's ID as assigned_to
        call_kwargs = svc_instance.create_partner.await_args.kwargs
        assert str(call_kwargs.get("assigned_to")) == fake_team["user_id"]

    @pytest.mark.integration
    def test_create_partner_missing_required_fields_422(self, admin_app) -> None:
        _, client, _, _ = admin_app
        resp = client.post("/api/partners", json={"full_name": "No Email"})
        assert resp.status_code == 422

    @pytest.mark.integration
    def test_create_partner_conflict_409(self, admin_app) -> None:
        _, client, pool, conn = admin_app
        from backend.services.crm.partners.service import ConflictError
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.create_partner = AsyncMock(
                side_effect=ConflictError("email already in use: 'dupe@k.io'")
            )
            resp = client.post(
                "/api/partners",
                json={"full_name": "A", "email": "dupe@k.io", "entity_type": "individual"},
            )
        assert resp.status_code == 409

    @pytest.mark.integration
    def test_create_partner_collision_with_internal_email_409(self, admin_app) -> None:
        _, client, pool, conn = admin_app
        from backend.services.crm.partners.service import ConflictError
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.create_partner = AsyncMock(
                side_effect=ConflictError("email is already a team/admin user: 'admin@balizero.com'")
            )
            resp = client.post(
                "/api/partners",
                json={"full_name": "A", "email": "admin@balizero.com", "entity_type": "individual"},
            )
        assert resp.status_code == 409


# ── 2. list_partners ─────────────────────────────────────────────────────────

class TestListPartners:
    @pytest.mark.integration
    def test_list_partners_admin_returns_all(self, admin_app) -> None:
        _, client, _, _ = admin_app
        partner = _make_partner()
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.list_partners = AsyncMock(return_value=[partner])
            resp = client.get("/api/partners")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 1

    @pytest.mark.integration
    def test_list_partners_team_scopes_to_self(self, team_app, fake_team) -> None:
        _, client, _, _ = team_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.list_partners = AsyncMock(return_value=[])
            resp = client.get("/api/partners")
        assert resp.status_code == 200
        # Verify actor_role was passed as team
        call_kwargs = svc_instance.list_partners.await_args.kwargs
        assert call_kwargs["actor_role"] == "team"
        assert str(call_kwargs["actor_user"]) == fake_team["user_id"]


# ── 2b. CATA-2: role gate + DTO stripping ────────────────────────────────────

class TestListPartnersCata2:
    """CATA-2: Router-level role gate and list DTO PII stripping."""

    @pytest.mark.unit
    def test_require_team_or_admin_blocks_partner_role(self) -> None:
        from fastapi import HTTPException
        user = {"role": "partner", "permissions": []}
        with pytest.raises(HTTPException) as exc_info:
            partners_module._require_team_or_admin(user)
        assert exc_info.value.status_code == 403
        assert "team or admin" in exc_info.value.detail.lower()

    @pytest.mark.unit
    def test_require_team_or_admin_blocks_unknown_role(self) -> None:
        from fastapi import HTTPException
        user = {"role": "finance", "permissions": []}
        with pytest.raises(HTTPException) as exc_info:
            partners_module._require_team_or_admin(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.unit
    def test_require_team_or_admin_allows_team(self) -> None:
        user = {"role": "team", "permissions": []}
        partners_module._require_team_or_admin(user)  # must not raise

    @pytest.mark.unit
    def test_require_team_or_admin_allows_admin(self) -> None:
        user = {"role": "admin", "permissions": ["finance.mark_paid"]}
        partners_module._require_team_or_admin(user)  # must not raise

    @pytest.mark.integration
    def test_list_partners_forbidden_for_partner_role(self, partner_app) -> None:
        _, client, _, _ = partner_app
        resp = client.get("/api/partners")
        assert resp.status_code == 403
        assert "team or admin" in resp.json()["detail"].lower()

    @pytest.mark.integration
    def test_create_partner_forbidden_for_partner_role(self, partner_app) -> None:
        _, client, _, _ = partner_app
        resp = client.post(
            "/api/partners",
            json={"full_name": "Hotel Kama", "email": "h@k.io", "entity_type": "individual"},
        )
        assert resp.status_code == 403

    @pytest.mark.unit
    def test_partner_to_list_dict_strips_sensitive_fields(self) -> None:
        """_partner_to_list_dict must exclude all _SENSITIVE_PARTNER_FIELDS."""
        partner = _make_partner(
            npwp="01.234.567.8-901.000",
            nik="3171010101010001",
            fiscal_address="Jl. Raya Kuta 1",
            bank_name="BCA",
            bank_account_holder="Test Partner",
            bank_account_number="1234567890",
            ewallet_type="GoPay",
            ewallet_number="08123456789",
            iban="ID00BANK0000000000",
            payment_notes="wired monthly",
            payment_currency="IDR",
        )
        result = partners_module._partner_to_list_dict(partner)
        for field in partners_module._SENSITIVE_PARTNER_FIELDS:
            assert field not in result, f"Sensitive field {field!r} leaked in list view"

    @pytest.mark.unit
    def test_partner_to_list_dict_retains_non_sensitive_fields(self) -> None:
        """Non-sensitive fields (name, email, status) must still appear in list view."""
        partner = _make_partner()
        result = partners_module._partner_to_list_dict(partner)
        assert "full_name" in result
        assert "email" in result
        assert "onboarding_status" in result
        assert "entity_type" in result
        assert "id" in result

    @pytest.mark.integration
    def test_list_partners_admin_response_strips_banking_fields(self, admin_app) -> None:
        """Even admin callers must not receive banking PII in the list endpoint."""
        _, client, _, _ = admin_app
        partner = _make_partner(
            npwp="01.234.567.8-901.000",
            bank_account_number="1234567890",
            iban="ID00BANK0000000000",
        )
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.list_partners = AsyncMock(return_value=[partner])
            resp = client.get("/api/partners")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        row = data[0]
        assert "npwp" not in row, "NPWP leaked in list view"
        assert "bank_account_number" not in row, "Bank account leaked"
        assert "iban" not in row, "IBAN leaked"

    @pytest.mark.integration
    def test_get_partner_detail_returns_full_record(self, admin_app) -> None:
        """GET /api/partners/{id} (detail, with access control) must return full fields."""
        _, client, _, _ = admin_app
        partner = _make_partner(
            npwp="01.234.567.8-901.000",
            bank_account_number="1234567890",
        )
        with patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify:
            async def _verify(*a, **kw):
                return partner
            mock_verify.side_effect = _verify
            resp = client.get(f"/api/partners/{_PARTNER_ID}")
        assert resp.status_code == 200
        data = resp.json()
        # Detail endpoint uses _partner_to_dict (full record)
        assert data.get("npwp") == "01.234.567.8-901.000"
        assert data.get("bank_account_number") == "1234567890"


# ── 3. get_partner ────────────────────────────────────────────────────────────

class TestGetPartner:
    @pytest.mark.integration
    def test_get_partner_admin_sees_any(self, admin_app) -> None:
        _, client, _, _ = admin_app
        partner = _make_partner()
        with patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify:
            async def _verify(*args, **kwargs):
                return partner
            mock_verify.side_effect = _verify
            resp = client.get(f"/api/partners/{_PARTNER_ID}")
        assert resp.status_code == 200

    @pytest.mark.integration
    def test_get_partner_not_found_returns_404(self, admin_app) -> None:
        from fastapi import HTTPException
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify:
            async def _raise(*args, **kwargs):
                raise HTTPException(status_code=404, detail="partner not found")
            mock_verify.side_effect = _raise
            resp = client.get(f"/api/partners/{_PARTNER_ID}")
        assert resp.status_code == 404


# ── 4. update_partner ─────────────────────────────────────────────────────────

class TestUpdatePartner:
    @pytest.mark.integration
    def test_patch_partner_team_can_update_own(self, team_app) -> None:
        _, client, _, _ = team_app
        partner = _make_partner(full_name="Updated Name")
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.update_partner = AsyncMock()
            svc_instance.repo = MagicMock()
            svc_instance.repo.get_partner = AsyncMock(return_value=partner)
            resp = client.patch(
                f"/api/partners/{_PARTNER_ID}",
                json={"full_name": "Updated Name"},
            )
        assert resp.status_code == 200
        svc_instance.update_partner.assert_awaited_once()

    @pytest.mark.integration
    def test_patch_partner_team_forbidden_on_other(self, team_app) -> None:
        from fastapi import HTTPException
        _, client, _, _ = team_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.update_partner = AsyncMock(
                side_effect=HTTPException(status_code=403, detail="forbidden")
            )
            resp = client.patch(
                f"/api/partners/{_PARTNER_ID}",
                json={"full_name": "Hacker"},
            )
        assert resp.status_code == 403


# ── 5. activate / deactivate ──────────────────────────────────────────────────

class TestActivateDeactivate:
    @pytest.mark.integration
    def test_activate_requires_admin_team_gets_403(self, team_app) -> None:
        # Router-level _require_admin fires before any service call
        _, client, _, _ = team_app
        resp = client.post(f"/api/partners/{_PARTNER_ID}/activate")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_activate_admin_succeeds_204(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc, \
             patch("backend.services.crm.partners.emails.send_welcome", new=AsyncMock()):
            svc_instance = MockSvc.return_value
            svc_instance.activate_partner = AsyncMock()
            resp = client.post(f"/api/partners/{_PARTNER_ID}/activate")
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_deactivate_admin_succeeds_204(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.deactivate_partner = AsyncMock()
            resp = client.post(f"/api/partners/{_PARTNER_ID}/deactivate")
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_deactivate_requires_admin_team_gets_403(self, team_app) -> None:
        # Router-level _require_admin fires before any service call
        _, client, _, _ = team_app
        resp = client.post(f"/api/partners/{_PARTNER_ID}/deactivate")
        assert resp.status_code == 403


# ── 6. reassign / bulk-reassign ───────────────────────────────────────────────

class TestReassign:
    @pytest.mark.integration
    def test_reassign_admin_succeeds_204(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.reassign_partner = AsyncMock()
            resp = client.post(
                f"/api/partners/{_PARTNER_ID}/reassign",
                json={"new_user_id": str(_TEAM_ID), "reason": "reorganisation"},
            )
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_reassign_requires_reason_400_on_empty(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.reassign_partner = AsyncMock(
                side_effect=ValueError("reason is required for reassignment")
            )
            resp = client.post(
                f"/api/partners/{_PARTNER_ID}/reassign",
                json={"new_user_id": str(_TEAM_ID), "reason": ""},
            )
        assert resp.status_code == 400

    @pytest.mark.integration
    def test_reassign_requires_admin_team_forbidden(self, team_app) -> None:
        # Router-level _require_admin fires before any service call
        _, client, _, _ = team_app
        resp = client.post(
            f"/api/partners/{_PARTNER_ID}/reassign",
            json={"new_user_id": str(_TEAM_ID), "reason": "test"},
        )
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_bulk_reassign_admin_only_success(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.reassign_partner = AsyncMock()
            resp = client.post(
                "/api/partners/bulk-reassign",
                json={
                    "partner_ids": [str(_PARTNER_ID)],
                    "new_user_id": str(_TEAM_ID),
                    "reason": "bulk test",
                },
            )
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_bulk_reassign_team_forbidden(self, team_app) -> None:
        # Router-level _require_admin fires before any service call
        _, client, _, _ = team_app
        resp = client.post(
            "/api/partners/bulk-reassign",
            json={
                "partner_ids": [str(_PARTNER_ID)],
                "new_user_id": str(_TEAM_ID),
                "reason": "test",
            },
        )
        assert resp.status_code == 403


# ── 7. referrals ──────────────────────────────────────────────────────────────

class TestReferrals:
    def _make_referral(self) -> MagicMock:
        r = MagicMock()
        r.id = _REFERRAL_ID
        r.partner_id = _PARTNER_ID
        r.practice_id = _PROCESS_ID
        r.share_percent = Decimal("100.00")
        r.referred_at = _NOW
        r.referred_by_user_id = _USER_ID
        r.notes = None
        return r

    @pytest.mark.integration
    def test_list_referrals_scoped_by_role(self, admin_app) -> None:
        _, client, _, _ = admin_app
        ref = self._make_referral()
        with (
            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
            patch("backend.app.routers.partners.PartnersService") as MockSvc,
        ):
            async def _verify(*a, **kw):
                return _make_partner()
            mock_verify.side_effect = _verify
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.list_referrals_for_partner = AsyncMock(return_value=[ref])
            resp = client.get(f"/api/partners/{_PARTNER_ID}/referrals")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.integration
    def test_create_referral_success_201(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with (
            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
            patch("backend.app.routers.partners.PartnersService") as MockSvc,
        ):
            async def _verify(*a, **kw):
                return _make_partner()
            mock_verify.side_effect = _verify
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.insert_referral = AsyncMock(return_value=_REFERRAL_ID)
            resp = client.post(
                f"/api/partners/{_PARTNER_ID}/referrals",
                json={"practice_id": str(_PROCESS_ID)},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == str(_REFERRAL_ID)

    @pytest.mark.integration
    def test_create_referral_process_conflict_409(self, admin_app) -> None:
        import asyncpg
        _, client, _, _ = admin_app
        # asyncpg.UniqueViolationError has a non-standard constructor — use a
        # plain Exception with "unique" in the message to trigger the fallback.
        with (
            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
            patch("backend.app.routers.partners.PartnersService") as MockSvc,
        ):
            async def _verify(*a, **kw):
                return _make_partner()
            mock_verify.side_effect = _verify
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.insert_referral = AsyncMock(
                side_effect=Exception("unique constraint violation on partner_referrals_practice_unique_v1")
            )
            resp = client.post(
                f"/api/partners/{_PARTNER_ID}/referrals",
                json={"practice_id": str(_PROCESS_ID)},
            )
        assert resp.status_code == 409

    @pytest.mark.integration
    def test_swap_referral_admin_only(self, admin_app) -> None:
        _, client, _, _ = admin_app
        new_partner_id = uuid.uuid4()
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.update_referral_partner = AsyncMock()
            resp = client.patch(
                f"/api/partners/referrals/{_REFERRAL_ID}",
                json={"new_partner_id": str(new_partner_id)},
            )
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_swap_referral_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        new_partner_id = uuid.uuid4()
        resp = client.patch(
            f"/api/partners/referrals/{_REFERRAL_ID}",
            json={"new_partner_id": str(new_partner_id)},
        )
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_delete_referral_admin_success(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.delete_referral = AsyncMock()
            resp = client.delete(f"/api/partners/referrals/{_REFERRAL_ID}")
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_delete_referral_blocked_when_commissions_exist_409(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.delete_referral = AsyncMock(
                side_effect=RuntimeError("Cannot delete referral with commissions recorded")
            )
            resp = client.delete(f"/api/partners/referrals/{_REFERRAL_ID}")
        assert resp.status_code == 409

    @pytest.mark.integration
    def test_delete_referral_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.delete(f"/api/partners/referrals/{_REFERRAL_ID}")
        assert resp.status_code == 403


# ── 8. commissions ────────────────────────────────────────────────────────────

class TestCommissions:
    @pytest.mark.integration
    def test_list_commissions_scoped(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with (
            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
            patch("backend.app.routers.partners.PartnersService") as MockSvc,
        ):
            async def _verify(*a, **kw):
                return _make_partner()
            mock_verify.side_effect = _verify
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.list_commissions_for_partner = AsyncMock(return_value=[])
            resp = client.get(f"/api/partners/{_PARTNER_ID}/commissions")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.integration
    def test_approve_commission_admin_and_finance(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine:
            engine_instance = MockEngine.return_value
            engine_instance.approve = AsyncMock()
            resp = client.post(f"/api/partners/commissions/{_COMMISSION_ID}/approve")
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_approve_commission_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.post(f"/api/partners/commissions/{_COMMISSION_ID}/approve")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_mark_paid_admin_succeeds_204(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine, \
             patch("backend.services.crm.partners.emails.send_commission_earned", new=AsyncMock()):
            engine_instance = MockEngine.return_value
            engine_instance.mark_paid = AsyncMock()
            resp = client.post(
                f"/api/partners/commissions/{_COMMISSION_ID}/mark-paid",
                json={"paid_via": "BCA", "payment_reference": "TX123"},
            )
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_mark_paid_requires_finance_perm_non_admin_403(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.post(
            f"/api/partners/commissions/{_COMMISSION_ID}/mark-paid",
            json={"paid_via": "BCA", "payment_reference": "TX123"},
        )
        # team role hits _require_admin first → 403
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_clawback_admin_returns_new_commission_id(self, admin_app) -> None:
        new_cid = uuid.uuid4()
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine:
            engine_instance = MockEngine.return_value
            engine_instance.clawback = AsyncMock(return_value=new_cid)
            resp = client.post(
                f"/api/partners/commissions/{_COMMISSION_ID}/clawback",
                json={"reason": "client cancelled"},
            )
        assert resp.status_code == 201
        assert resp.json()["id"] == str(new_cid)

    @pytest.mark.integration
    def test_clawback_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.post(
            f"/api/partners/commissions/{_COMMISSION_ID}/clawback",
            json={"reason": "test"},
        )
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_waive_admin_succeeds_204(self, admin_app) -> None:
        _, client, _, _ = admin_app
        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine:
            engine_instance = MockEngine.return_value
            engine_instance.waive_clawback = AsyncMock()
            resp = client.post(
                f"/api/partners/commissions/{_COMMISSION_ID}/waive",
                json={"reason": "goodwill"},
            )
        assert resp.status_code == 204

    @pytest.mark.integration
    def test_waive_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.post(
            f"/api/partners/commissions/{_COMMISSION_ID}/waive",
            json={"reason": "test"},
        )
        assert resp.status_code == 403


# ── 9. /me endpoints ──────────────────────────────────────────────────────────

class TestMeEndpoints:
    @pytest.mark.integration
    def test_me_team_role_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.get("/api/partners/me")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_me_partner_returns_own_profile(self, partner_app) -> None:
        _, client, pool, conn = partner_app
        partner = _make_partner()
        # asyncpg Record-like dict for "SELECT partner_id FROM users ..."
        conn.fetchrow = AsyncMock(return_value={"partner_id": _PARTNER_ID})
        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.repo = MagicMock()
            svc_instance.repo.get_partner = AsyncMock(return_value=partner)
            resp = client.get("/api/partners/me")
        assert resp.status_code == 200

    @pytest.mark.integration
    def test_me_no_partner_id_linked_403(self, partner_app) -> None:
        _, client, pool, conn = partner_app
        conn.fetchrow = AsyncMock(return_value={"partner_id": None})
        resp = client.get("/api/partners/me")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_me_referrals_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.get("/api/partners/me/referrals")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_me_referrals_sterilizes_client_name(self, partner_app) -> None:
        """Happy-path: single JOIN returns rows, client_display is sterilized."""
        _, client, pool, conn = partner_app
        # First fetchrow: partner_id lookup
        conn.fetchrow = AsyncMock(return_value={"partner_id": _PARTNER_ID})
        # fetch: single-JOIN referrals result
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(side_effect=lambda k: {
            "id": _REFERRAL_ID,
            "practice_id": _PROCESS_ID,
            "referred_at": _NOW,
            "process_status": "in_progress",
            "service_type": "pt_pma",
            "client_name": "Mario Rossi",
        }[k])
        conn.fetch = AsyncMock(return_value=[mock_row])
        resp = client.get("/api/partners/me/referrals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["client_display"] == "Mario R."
        # Verify no sensitive fields leaked
        row = data[0]
        for sensitive in ("passport", "phone", "email", "npwp", "nik"):
            assert sensitive not in row

    @pytest.mark.integration
    def test_me_commissions_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.get("/api/partners/me/commissions")
        assert resp.status_code == 403


# ── 10. finance export ────────────────────────────────────────────────────────

class TestFinanceExport:
    @pytest.mark.integration
    def test_finance_export_admin_only_returns_csv(self, admin_app) -> None:
        _, client, pool, conn = admin_app
        # conn.fetch should return list of records
        mock_row = MagicMock()
        mock_row.keys = MagicMock(return_value=[
            "id", "full_name", "npwp", "entity_type", "entry_type",
            "gross_amount_idr", "withholding_category", "withholding_amount_idr",
            "net_amount_idr", "status", "paid_at", "paid_via", "payment_reference",
        ])
        mock_row.__getitem__ = MagicMock(side_effect=lambda k: {
            "id": str(_COMMISSION_ID),
            "full_name": "Test Partner",
            "npwp": None,
            "entity_type": "individual",
            "entry_type": "accrual",
            "gross_amount_idr": Decimal("1000000"),
            "withholding_category": "tbd",
            "withholding_amount_idr": Decimal("0"),
            "net_amount_idr": Decimal("1000000"),
            "status": "approved",
            "paid_at": None,
            "paid_via": None,
            "payment_reference": None,
        }[k])
        conn.fetch = AsyncMock(return_value=[mock_row])
        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "commission_id" in resp.text  # CSV header

    @pytest.mark.integration
    def test_finance_export_csv_has_expected_headers(self, admin_app) -> None:
        _, client, pool, conn = admin_app
        conn.fetch = AsyncMock(return_value=[])
        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
        assert resp.status_code == 200
        first_line = resp.text.splitlines()[0]
        assert "commission_id" in first_line
        assert "partner" in first_line
        assert "net_idr" in first_line

    @pytest.mark.integration
    def test_finance_export_team_forbidden(self, team_app) -> None:
        _, client, _, _ = team_app
        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
        assert resp.status_code == 403

    @pytest.mark.integration
    def test_finance_export_content_disposition(self, admin_app) -> None:
        _, client, pool, conn = admin_app
        conn.fetch = AsyncMock(return_value=[])
        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
        assert resp.status_code == 200
        assert "attachment" in resp.headers["content-disposition"]
        assert "partners-2026-01-01-to-2026-04-30.csv" in resp.headers["content-disposition"]

    @pytest.mark.integration
    def test_finance_export_bad_date_400(self, admin_app) -> None:
        _, client, pool, conn = admin_app
        resp = client.get("/api/partners/finance/export?from=yesterday&to=tomorrow")
        assert resp.status_code == 400
        assert "invalid date format" in resp.json()["detail"]


# ── 11. sterilize helpers ─────────────────────────────────────────────────────

class TestSterilizeServiceTypeForPartner:
    """Unit tests for _sterilize_service_type_for_partner (CRIT-6)."""

    @pytest.mark.unit
    def test_kitas_e33g(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("KITAS E33G") == "Visa / KITAS service"

    @pytest.mark.unit
    def test_visa_keyword(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("B211 Visa Extension") == "Visa / KITAS service"

    @pytest.mark.unit
    def test_kitap_service(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("KITAP application") == "KITAP service"

    @pytest.mark.unit
    def test_pt_pma_setup(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("PT PMA setup") == "Company setup"

    @pytest.mark.unit
    def test_tax_pph21(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("Tax PPh21 filing") == "Tax service"

    @pytest.mark.unit
    def test_property_sertifikat(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("Property sertifikat") == "Property service"

    @pytest.mark.unit
    def test_none_returns_generic(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st(None) == "Service"

    @pytest.mark.unit
    def test_empty_string_returns_generic(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("") == "Service"

    @pytest.mark.unit
    def test_unknown_type_returns_other(self) -> None:
        from backend.app.routers.partners import _sterilize_service_type_for_partner as st
        assert st("something completely new v99") == "Other service"


class TestSterilizeClientName:
    @pytest.mark.unit
    def test_sterilize_two_part_name(self) -> None:
        assert partners_module._sterilize_client_for_partner("Mario Rossi") == "Mario R."

    @pytest.mark.unit
    def test_sterilize_single_name(self) -> None:
        assert partners_module._sterilize_client_for_partner("Siti") == "Siti"

    @pytest.mark.unit
    def test_sterilize_three_part_name(self) -> None:
        result = partners_module._sterilize_client_for_partner("Maria Angela Gomez")
        assert result == "Maria G."

    @pytest.mark.unit
    def test_sterilize_empty_string(self) -> None:
        assert partners_module._sterilize_client_for_partner("") == ""


# ── 12. audit log endpoint ───────────────────────────────────────────────────

class TestAuditLog:
    @pytest.mark.integration
    def test_list_audit_log_admin_sees_entries(self, admin_app) -> None:
        _, client, _, _ = admin_app
        entry1 = MagicMock()
        entry1.id = uuid.uuid4()
        entry1.partner_id = _PARTNER_ID
        entry1.action = "activated"
        entry1.at = _NOW
        entry1.actor_user_id = _USER_ID
        entry1.before_json = None
        entry1.after_json = None
        entry1.reason = None
        entry2 = MagicMock()
        entry2.id = uuid.uuid4()
        entry2.partner_id = _PARTNER_ID
        entry2.action = "reassigned"
        entry2.at = _NOW
        entry2.actor_user_id = _USER_ID
        entry2.before_json = None
        entry2.after_json = None
        entry2.reason = "reorganisation"
        with (
            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
            patch("backend.app.routers.partners.PartnersService") as MockSvc,
        ):
            async def _verify(*a, **kw):
                return _make_partner()
            mock_verify.side_effect = _verify
            svc_instance = MockSvc.return_value
            svc_instance.list_audit = AsyncMock(return_value=[entry1, entry2])
            resp = client.get(f"/api/partners/{_PARTNER_ID}/audit-log")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.integration
    def test_list_audit_log_team_forbidden_for_other_partner(self, team_app) -> None:
        from fastapi import HTTPException
        _, client, _, _ = team_app
        with (
            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
            patch("backend.app.routers.partners.PartnersService"),
        ):
            async def _raise(*a, **kw):
                raise HTTPException(status_code=403, detail="forbidden")
            mock_verify.side_effect = _raise
            resp = client.get(f"/api/partners/{_PARTNER_ID}/audit-log")
        assert resp.status_code == 403


# ── 13. require_finance helper ────────────────────────────────────────────────

class TestRequireFinance:
    @pytest.mark.unit
    def test_admin_with_finance_perm_passes(self) -> None:
        # CRIT-3: admin role alone no longer bypasses — must hold the explicit perm.
        user = {"role": "admin", "permissions": ["finance.mark_paid"]}
        partners_module._require_finance(user)  # must not raise

    @pytest.mark.unit
    def test_admin_without_finance_perm_raises_403(self) -> None:
        # CRIT-3: admin without the perm must be rejected (this was the broken fallback).
        from fastapi import HTTPException
        user = {"role": "admin", "permissions": []}
        with pytest.raises(HTTPException) as exc_info:
            partners_module._require_finance(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.unit
    def test_non_admin_with_finance_perm_passes(self) -> None:
        user = {"role": "team", "permissions": ["finance.mark_paid"]}
        partners_module._require_finance(user)  # must not raise

    @pytest.mark.unit
    def test_non_admin_without_finance_perm_raises_403(self) -> None:
        from fastapi import HTTPException
        user = {"role": "team", "permissions": []}
        with pytest.raises(HTTPException) as exc_info:
            partners_module._require_finance(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.unit
    def test_finance_perm_passes_regardless_of_role(self) -> None:
        # Anyone with the perm — regardless of role — should pass.
        for role in ("admin", "team", "finance", "accountant"):
            user = {"role": role, "permissions": ["finance.mark_paid"]}
            partners_module._require_finance(user)  # must not raise

    @pytest.mark.unit
    def test_perm_check_tolerates_missing_permissions_key(self) -> None:
        # Defensive: JWT without 'permissions' key at all → reject.
        from fastapi import HTTPException
        user = {"role": "admin"}
        with pytest.raises(HTTPException) as exc_info:
            partners_module._require_finance(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.unit
    def test_perm_check_tolerates_none_permissions(self) -> None:
        # Defensive: JWT with permissions=None → reject (not crash).
        from fastapi import HTTPException
        user = {"role": "admin", "permissions": None}
        with pytest.raises(HTTPException) as exc_info:
            partners_module._require_finance(user)
        assert exc_info.value.status_code == 403
