"""Tests for the GARUDA VOA public request funnel router (Slice A).

Mirrors the calling convention of
`backend/tests/services/visa_check/test_router_jwt.py`: endpoint functions
are called directly with a monkeypatched repository and `db_pool=None`,
no live DB or TestClient needed.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pydantic
import pytest

_TODAY = date(2026, 7, 27)


def _monkeypatch_save(monkeypatch, router_mod) -> None:
    """Fake `save_voa_check` that echoes its kwargs back as a VoaCheckResult
    — exercises the router's own price/verdict wiring, not the DB."""

    async def _fake_save(self, **kwargs):
        from backend.services.garuda_flow.repository import VoaCheckResult

        return VoaCheckResult(
            hash="voa1234567890ab",
            case_type=kwargs["case_type"],
            nationality=kwargs["nationality"],
            entry_date=kwargs["entry_date"],
            passport_expiry_date=kwargs["passport_expiry_date"],
            voa_expiry_date=kwargs["voa_expiry_date"],
            extension_already_used=kwargs["extension_already_used"],
            purpose=kwargs["purpose"],
            travellers=kwargs["travellers"],
            self_pay=kwargs["self_pay"],
            decision=kwargs["decision"],
            decline_reasons=kwargs["decline_reasons"],
            decline_codes=kwargs["decline_codes"],
            expiry_date=kwargs["expiry_date"],
            last_legal_day=kwargs["last_legal_day"],
            expiry_is_estimated=kwargs["expiry_is_estimated"],
            published_filing_deadline=kwargs["published_filing_deadline"],
            submit_by_date=kwargs["submit_by_date"],
            price_idr=kwargs["price_idr"],
            price_source=kwargs["price_source"],
            view_count=0,
            share_count=0,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(router_mod.GarudaVoaRepository, "save_voa_check", _fake_save)


class TestVoaResponseNeverCarriesInternalCheckpoints:
    """Structural check (spec §6 charter): the response schema itself must
    have no field capable of leaking a D-14/D-10/D-3/D-1 internal
    checkpoint — this must hold independent of any particular request."""

    def test_response_schema_has_no_internal_checkpoint_fields(self) -> None:
        from backend.app.routers.garuda_voa import VoaResponse

        fields = VoaResponse.model_fields
        forbidden = (
            "checkpoints",
            "internal_checkpoints",
            "client_facing_checkpoints",
            "extension_window_opens",
            "pilot_threshold",
            "internal_escalation",
            "final_check",
        )
        for name in forbidden:
            assert name not in fields, f"VoaResponse must not expose {name!r}"

    def test_response_schema_exposes_only_the_published_deadline(self) -> None:
        from backend.app.routers.garuda_voa import VoaResponse

        assert "published_filing_deadline" in VoaResponse.model_fields

    def test_response_schema_can_never_carry_the_disputed_window_opens_date(
        self,
    ) -> None:
        """Regression pin: `filing_window_opens_date` was briefly exposed
        client-facing under a defect-fix that mis-cited the source as
        stating a single reading. The source states the earliest-filing
        rule two incompatible ways on the same page (14 days before expiry
        vs. 14 days after arrival) — different dates on a 30-day B1 — so it
        must never be published as an official rule. This must hold
        structurally, independent of any particular request/response."""
        from backend.app.routers.garuda_voa import VoaResponse

        forbidden = (
            "filing_window_opens_date",
            "extension_window_opens_date",
            "filing_window_opens",
        )
        fields = VoaResponse.model_fields
        for name in forbidden:
            assert name not in fields, f"VoaResponse must not expose {name!r}"


class TestVoaResponseCarriesCodesNotProse:
    """Fix 2026-07-27 (cross-family review): the raw English audit prose
    (`decline_reasons`) must never reach the wire — only the neutral
    `reason_codes`. Structural check, same style as the checkpoint pins
    above; the content-level guard (real DECLINE payloads, every branch)
    lives in `test_garuda_voa_no_internal_leak.py`."""

    def test_response_schema_has_no_raw_reasons_field(self) -> None:
        from backend.app.routers.garuda_voa import VoaResponse

        assert "reasons" not in VoaResponse.model_fields

    def test_response_schema_exposes_reason_codes(self) -> None:
        from backend.app.routers.garuda_voa import VoaResponse

        assert "reason_codes" in VoaResponse.model_fields


class TestVoaRequestValidation:
    def test_extension_without_voa_expiry_date_is_rejected(self) -> None:
        from backend.app.routers.garuda_voa import CaseType, Purpose, VoaRequest

        with pytest.raises(pydantic.ValidationError):
            VoaRequest(
                case_type=CaseType.EXTENSION,
                nationality="USA",
                entry_date=_TODAY - timedelta(days=20),
                passport_expiry_date=_TODAY + timedelta(days=400),
                purpose=Purpose.TOURISM,
                travellers=1,
                self_pay=True,
            )

    def test_extension_with_voa_expiry_date_is_accepted(self) -> None:
        from backend.app.routers.garuda_voa import CaseType, Purpose, VoaRequest

        req = VoaRequest(
            case_type=CaseType.EXTENSION,
            nationality="usa",
            entry_date=_TODAY - timedelta(days=20),
            passport_expiry_date=_TODAY + timedelta(days=400),
            voa_expiry_date=_TODAY + timedelta(days=18),
            purpose=Purpose.TOURISM,
            travellers=1,
            self_pay=True,
        )
        assert req.nationality == "USA"  # normalised uppercase

    def test_travellers_out_of_bounds_is_rejected(self) -> None:
        from backend.app.routers.garuda_voa import CaseType, Purpose, VoaRequest

        with pytest.raises(pydantic.ValidationError):
            VoaRequest(
                case_type=CaseType.ISSUANCE,
                nationality="USA",
                entry_date=_TODAY + timedelta(days=5),
                passport_expiry_date=_TODAY + timedelta(days=400),
                purpose=Purpose.TOURISM,
                travellers=0,
                self_pay=True,
            )


@pytest.mark.asyncio
async def test_submit_voa_accept_issuance_returns_client_safe_response(monkeypatch):
    from backend.app.routers import garuda_voa as router_mod

    _monkeypatch_save(monkeypatch, router_mod)

    payload = router_mod.VoaRequest(
        case_type=router_mod.CaseType.ISSUANCE,
        nationality="usa",
        entry_date=date.today() + timedelta(days=5),
        passport_expiry_date=date.today() + timedelta(days=400),
        purpose=router_mod.Purpose.TOURISM,
        travellers=1,
        self_pay=True,
    )
    response = await router_mod.submit_voa(payload, db_pool=None)

    assert response.decision == "ACCEPT"
    assert response.reason_codes == []
    assert response.result_url == "/visa/voa/voa1234567890ab"
    # Price is server-side from PricingTool, never a hardcoded literal here.
    assert response.price_idr == 790_000
    assert response.price_source
    assert response.published_filing_deadline < response.expiry_date
    # Bali Zero's own submit-by commitment (owner ruling 2026-07-27) — must
    # be computed and returned on an accepted issuance, strictly before the
    # entry date itself.
    assert response.submit_by_date is not None
    assert response.submit_by_date < response.entry_date


@pytest.mark.asyncio
async def test_submit_voa_prices_extension_differently_from_issuance(monkeypatch):
    from backend.app.routers import garuda_voa as router_mod

    _monkeypatch_save(monkeypatch, router_mod)

    payload = router_mod.VoaRequest(
        case_type=router_mod.CaseType.EXTENSION,
        nationality="USA",
        entry_date=date.today() - timedelta(days=20),
        passport_expiry_date=date.today() + timedelta(days=400),
        voa_expiry_date=date.today() + timedelta(days=18),
        purpose=router_mod.Purpose.TOURISM,
        travellers=1,
        self_pay=True,
    )
    response = await router_mod.submit_voa(payload, db_pool=None)

    assert response.decision == "ACCEPT"
    assert response.price_idr == 850_000  # NOT the 790_000 issuance price


@pytest.mark.asyncio
async def test_submit_voa_declines_on_short_passport_validity(monkeypatch):
    from backend.app.routers import garuda_voa as router_mod

    _monkeypatch_save(monkeypatch, router_mod)

    entry = date.today() + timedelta(days=5)
    payload = router_mod.VoaRequest(
        case_type=router_mod.CaseType.ISSUANCE,
        nationality="DEU",
        entry_date=entry,
        passport_expiry_date=entry + timedelta(days=30),  # well short of 6mo
        purpose=router_mod.Purpose.TOURISM,
        travellers=1,
        self_pay=True,
    )
    response = await router_mod.submit_voa(payload, db_pool=None)

    assert response.decision == "DECLINE"
    assert "PASSPORT_VALIDITY" in response.reason_codes
    # A decline must never leave the visitor with a bare no (SOP amendment).
    assert response.reason_codes


@pytest.mark.asyncio
async def test_submit_voa_second_extension_declines_even_with_full_runway(monkeypatch):
    from backend.app.routers import garuda_voa as router_mod

    _monkeypatch_save(monkeypatch, router_mod)

    payload = router_mod.VoaRequest(
        case_type=router_mod.CaseType.EXTENSION,
        nationality="USA",
        entry_date=date.today() - timedelta(days=20),
        passport_expiry_date=date.today() + timedelta(days=400),
        voa_expiry_date=date.today() + timedelta(days=25),  # plenty of runway
        extension_already_used=True,
        purpose=router_mod.Purpose.TOURISM,
        travellers=1,
        self_pay=True,
    )
    response = await router_mod.submit_voa(payload, db_pool=None)

    assert response.decision == "DECLINE"
    assert "EXTENSION_ALREADY_USED" in response.reason_codes


def _fixed_today(monkeypatch, router_mod, pinned: date) -> None:
    """Monkeypatch `router_mod.date` to a `date` subclass whose `.today()`
    returns ``pinned`` — so `submit_voa`'s internal `date.today()` call
    (and `VoaRequest`'s own `entry_date` bounds validator, same module
    namespace, same late-bound global lookup) resolve to a pinned date
    instead of the real wall clock, without touching any other `date`
    behaviour or any literal `date(...)` value passed into the payload."""

    class _Frozen(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            return pinned

    monkeypatch.setattr(router_mod, "date", _Frozen)


@pytest.mark.asyncio
async def test_submit_voa_issuance_accepts_at_the_aug_18_departure_cutoff(monkeypatch):
    """Owner ruling (2026-07-27) pinned end-to-end through the router: 17
    Aug 2026 is Independence Day (a Monday), so the last open day before a
    Tue 18 Aug arrival is Fri 14 Aug — submitting ON that cutoff accepts."""
    from backend.app.routers import garuda_voa as router_mod

    _monkeypatch_save(monkeypatch, router_mod)
    _fixed_today(monkeypatch, router_mod, date(2026, 8, 14))

    payload = router_mod.VoaRequest(
        case_type=router_mod.CaseType.ISSUANCE,
        nationality="USA",
        entry_date=date(2026, 8, 18),
        passport_expiry_date=date(2026, 8, 18) + timedelta(days=400),
        purpose=router_mod.Purpose.TOURISM,
        travellers=1,
        self_pay=True,
    )
    response = await router_mod.submit_voa(payload, db_pool=None)

    assert response.decision == "ACCEPT"
    assert response.submit_by_date == date(2026, 8, 14)


@pytest.mark.asyncio
async def test_submit_voa_issuance_declines_one_day_past_the_aug_18_cutoff(monkeypatch):
    from backend.app.routers import garuda_voa as router_mod

    _monkeypatch_save(monkeypatch, router_mod)
    _fixed_today(monkeypatch, router_mod, date(2026, 8, 15))  # one day too late

    payload = router_mod.VoaRequest(
        case_type=router_mod.CaseType.ISSUANCE,
        nationality="USA",
        entry_date=date(2026, 8, 18),
        passport_expiry_date=date(2026, 8, 18) + timedelta(days=400),
        purpose=router_mod.Purpose.TOURISM,
        travellers=1,
        self_pay=True,
    )
    response = await router_mod.submit_voa(payload, db_pool=None)

    assert response.decision == "DECLINE"
    assert "ARRIVAL_TOO_SOON" in response.reason_codes
    # Routing, never a bare no — and it must NEVER read as "you are not
    # eligible": the response still carries the (already-passed) cutoff.
    assert response.submit_by_date == date(2026, 8, 14)


@pytest.mark.asyncio
async def test_submit_voa_issuance_past_coverage_end_fails_closed(monkeypatch):
    """A 2027 arrival: the 2027 SKB does not exist yet, so the cutoff
    cannot be computed without guessing. Must decline distinctly from
    "too soon" and must never leak a guessed date."""
    from backend.app.routers import garuda_voa as router_mod
    from backend.services.garuda_flow.operating_calendar import COVERAGE_END

    _monkeypatch_save(monkeypatch, router_mod)
    _fixed_today(monkeypatch, router_mod, date(2026, 6, 1))

    entry = COVERAGE_END + timedelta(days=5)
    payload = router_mod.VoaRequest(
        case_type=router_mod.CaseType.ISSUANCE,
        nationality="USA",
        entry_date=entry,
        passport_expiry_date=entry + timedelta(days=400),
        purpose=router_mod.Purpose.TOURISM,
        travellers=1,
        self_pay=True,
    )
    response = await router_mod.submit_voa(payload, db_pool=None)

    assert response.decision == "DECLINE"
    assert "ARRIVAL_DATE_UNCONFIRMED" in response.reason_codes
    assert "ARRIVAL_TOO_SOON" not in response.reason_codes
    assert response.submit_by_date is None


@pytest.mark.asyncio
async def test_get_voa_reads_back_the_stored_verdict(monkeypatch):
    from unittest.mock import AsyncMock

    from backend.app.routers import garuda_voa as router_mod
    from backend.services.garuda_flow.eligibility import Decision
    from backend.services.garuda_flow.intake import CaseType, Purpose
    from backend.services.garuda_flow.repository import VoaCheckResult

    async def _fake_load(self, hash_: str):
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

    monkeypatch.setattr(router_mod.GarudaVoaRepository, "get_voa_check", _fake_load)
    monkeypatch.setattr(router_mod.GarudaVoaRepository, "bump_view_count", AsyncMock())

    response = await router_mod.get_voa(hash="voa1234567890ab", db_pool=None)

    assert response.hash == "voa1234567890ab"
    assert response.decision == "ACCEPT"
    assert response.published_filing_deadline == date(2026, 8, 24)
    assert response.submit_by_date == date(2026, 7, 31)
    assert response.price_idr == 790_000


@pytest.mark.asyncio
async def test_get_voa_missing_hash_returns_404(monkeypatch):
    from fastapi import HTTPException

    from backend.app.routers import garuda_voa as router_mod

    async def _fake_load(self, hash_: str):
        return None

    monkeypatch.setattr(router_mod.GarudaVoaRepository, "get_voa_check", _fake_load)

    with pytest.raises(HTTPException) as exc_info:
        await router_mod.get_voa(hash="doesnotexist00", db_pool=None)
    assert exc_info.value.status_code == 404
