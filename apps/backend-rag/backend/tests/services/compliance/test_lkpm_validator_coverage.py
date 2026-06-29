"""Focused coverage tests for deterministic LKPM validator branches."""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.models.lkpm import (
    EmploymentData,
    InvestmentRealization,
    LKPMClientConfig,
    LKPMDraft,
    ValidationSeverity,
)
from backend.services.compliance import lkpm_validator as validator_module
from backend.services.compliance.exceptions import LkpmValidationError
from backend.services.compliance.lkpm_validator import LKPMValidator


class _AcquireContext:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self.conn

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self.conn)


class _FakeConn:
    def __init__(
        self,
        *,
        fetch_results: list[list[dict[str, Any]]] | None = None,
        fetchrow_results: list[dict[str, Any] | None] | None = None,
        fetch_error: Exception | None = None,
        fetchrow_error: Exception | None = None,
    ) -> None:
        self._fetch_results = list(fetch_results or [])
        self._fetchrow_results = list(fetchrow_results or [])
        self.fetch_error = fetch_error
        self.fetchrow_error = fetchrow_error

    async def fetch(self, query: str, *args: object) -> list[dict[str, Any]]:
        _ = (query, args)
        if self.fetch_error is not None:
            raise self.fetch_error
        if self._fetch_results:
            return self._fetch_results.pop(0)
        return []

    async def fetchrow(self, query: str, *args: object) -> dict[str, Any] | None:
        _ = (query, args)
        if self.fetchrow_error is not None:
            raise self.fetchrow_error
        if self._fetchrow_results:
            return self._fetchrow_results.pop(0)
        return None


def _validator(
    *,
    fetch_results: list[list[dict[str, Any]]] | None = None,
    fetchrow_results: list[dict[str, Any] | None] | None = None,
    fetch_error: Exception | None = None,
    fetchrow_error: Exception | None = None,
) -> LKPMValidator:
    conn = _FakeConn(
        fetch_results=fetch_results,
        fetchrow_results=fetchrow_results,
        fetch_error=fetch_error,
        fetchrow_error=fetchrow_error,
    )
    return LKPMValidator(db_pool=_FakePool(conn))


def _report_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 1,
        "status": "draft",
        "client_id": 42,
        "realized_equipment_domestic": 0,
        "realized_equipment_import": 0,
        "realized_building_domestic": 0,
        "realized_building_import": 0,
        "realized_vehicle_domestic": 0,
        "realized_vehicle_import": 0,
        "realized_land": 0,
        "realized_working_capital": 0,
        "realized_other": 0,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_validate_aggregates_green_checks_for_clean_draft() -> None:
    validator = _validator(
        fetch_results=[
            [{"entity_id": "kbli:68111"}],
            [{"total": 25_000_000}],
        ],
        fetchrow_results=[{"kitas_count": 1}],
    )
    draft = LKPMDraft(
        client_id=42,
        quarter="Q2",
        year=2026,
        realized=InvestmentRealization(equipment_domestic=25_000_000),
        cumulative=InvestmentRealization(equipment_domestic=50_000_000),
        employment=EmploymentData(tki=4, tka=1),
    )
    config = LKPMClientConfig(
        client_id=42,
        company_name="Synthetic PT",
        kbli_codes=["68111"],
        planned=InvestmentRealization(equipment_domestic=100_000_000),
    )

    result = await validator.validate(draft, config)

    assert result.is_valid is True
    assert result.red_count == 0
    assert result.yellow_count == 0
    assert result.green_count == 3


@pytest.mark.asyncio
async def test_validate_kbli_match_requires_registered_codes() -> None:
    alerts = await _validator().validate_kbli_match(client_id=42, registered_kbli=[])

    assert len(alerts) == 1
    assert alerts[0].field == "kbli_codes"
    assert alerts[0].severity == ValidationSeverity.RED


@pytest.mark.asyncio
async def test_validate_kbli_match_marks_found_and_missing_codes() -> None:
    validator = _validator(fetch_results=[[{"entity_id": "kbli:68111"}]])

    alerts = await validator.validate_kbli_match(
        client_id=42,
        registered_kbli=["68111", "47911"],
    )

    by_field = {alert.field: alert for alert in alerts}
    assert by_field["kbli_68111"].severity == ValidationSeverity.GREEN
    assert by_field["kbli_47911"].severity == ValidationSeverity.YELLOW


@pytest.mark.asyncio
async def test_validate_kbli_match_degrades_to_manual_verification_on_db_error() -> None:
    validator = _validator(fetch_error=RuntimeError("db unavailable"))

    alerts = await validator.validate_kbli_match(client_id=42, registered_kbli=["68111"])

    assert len(alerts) == 1
    assert alerts[0].severity == ValidationSeverity.YELLOW
    assert "verify manually" in (alerts[0].details or "").lower()


@pytest.mark.asyncio
async def test_validate_wna_count_covers_match_mismatch_and_db_failure() -> None:
    matching = await _validator(fetchrow_results=[{"kitas_count": 2}]).validate_wna_count(
        reported_tka=2,
        client_id=42,
    )
    mismatch = await _validator(fetchrow_results=[{"kitas_count": 3}]).validate_wna_count(
        reported_tka=2,
        client_id=42,
    )
    failed = await _validator(fetchrow_error=RuntimeError("db unavailable")).validate_wna_count(
        reported_tka=2,
        client_id=42,
    )

    assert matching[0].severity == ValidationSeverity.GREEN
    assert mismatch[0].severity == ValidationSeverity.YELLOW
    assert "mismatch" in mismatch[0].message.lower()
    assert failed[0].severity == ValidationSeverity.YELLOW
    assert "could not verify" in failed[0].message.lower()


@pytest.mark.asyncio
async def test_detect_zero_realization_returns_red_yellow_or_empty() -> None:
    red = await _validator(
        fetch_results=[[{"total": 0}, {"total": 0}, {"total": 0}, {"total": 0}]],
    ).detect_zero_realization(client_id=42)
    yellow = await _validator(
        fetch_results=[[{"total": 0}, {"total": 0}, {"total": 10_000_000}]],
    ).detect_zero_realization(client_id=42)
    empty = await _validator(
        fetch_results=[[{"total": 10_000_000}, {"total": 0}]],
    ).detect_zero_realization(client_id=42)
    failed = await _validator(fetch_error=RuntimeError("db unavailable")).detect_zero_realization(
        client_id=42,
    )

    assert red[0].severity == ValidationSeverity.RED
    assert yellow[0].severity == ValidationSeverity.YELLOW
    assert empty == []
    assert failed == []


@pytest.mark.asyncio
async def test_check_completeness_async_rejects_malformed_periods() -> None:
    validator = _validator()

    with pytest.raises(LkpmValidationError, match="Period must be"):
        await validator.check_completeness_async(_FakeConn(), client_id=42, period="2026 Q2")

    with pytest.raises(LkpmValidationError, match="not an integer"):
        await validator.check_completeness_async(_FakeConn(), client_id=42, period="Q2 twenty")


@pytest.mark.asyncio
async def test_check_completeness_async_raises_when_report_row_is_missing() -> None:
    validator = _validator()

    with pytest.raises(LkpmValidationError, match="No lkpm_reports row found"):
        await validator.check_completeness_async(_FakeConn(fetchrow_results=[None]), 42, "Q2 2026")


@pytest.mark.asyncio
async def test_check_completeness_async_reports_missing_fields_and_status_warnings() -> None:
    validator = _validator()
    conn = _FakeConn(
        fetchrow_results=[
            _report_row(status="submitted"),
            _report_row(status="archived", realized_land=None),
        ],
    )

    submitted = await validator.check_completeness_async(conn, 42, "Q2 2026")
    archived = await validator.check_completeness_async(conn, 42, "Q2 2026")

    assert submitted == {
        "is_complete": True,
        "missing_fields": [],
        "warnings": ["Report already submitted to OSS"],
    }
    assert archived["is_complete"] is False
    assert archived["missing_fields"] == ["realized_land"]
    assert archived["warnings"] == ["Report is archived"]


@pytest.mark.asyncio
async def test_check_completeness_async_accepts_pool_like_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PatchedPool(_FakePool):
        pass

    monkeypatch.setattr(validator_module.asyncpg, "Pool", _PatchedPool)
    pool = _PatchedPool(_FakeConn(fetchrow_results=[_report_row()]))
    validator = LKPMValidator(db_pool=pool)

    result = await validator.check_completeness_async(pool, 42, "Q2 2026")

    assert result == {
        "is_complete": True,
        "missing_fields": [],
        "warnings": [],
    }
