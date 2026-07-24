"""Unit tests for the E33 Second Home case lifecycle model.

Fixed-clock pattern (same style as tests/services/visa_check/test_clock.py):
all deadline/alert computations take an explicit ``today``/``at`` so tests
are deterministic.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.compliance.alerts_engine import _DOCTYPE_TO_CATEGORY, AlertsEngine
from backend.services.compliance.renewal_rules import match_rule
from backend.services.compliance.templates_i18n import (
    TEMPLATE_REGISTRY,
    render_template,
)
from backend.services.crm.e33_case_repository import (
    E33CaseRepository,
    case_to_row,
    row_to_case,
)
from backend.services.crm.e33_lifecycle import (
    DEFAULT_DEPENDENT_CODES,
    DOCTYPE_GUARANTEE,
    DOCTYPE_MAINTENANCE,
    RULE_ID_ANNUAL_MAINTENANCE,
    RULE_ID_GUARANTEE_PROOF,
    CustodyViolationError,
    DependentLink,
    E33Case,
    E33InvalidTransitionError,
    E33Stage,
    EvidenceKind,
    EvidenceRef,
    GuaranteeBasis,
    UnknownDependentCodeError,
    compute_guarantee_deadline,
    guarantee_alert_schedule,
    next_itas_anniversary,
    severity_for_days_until,
    validate_dependent_code,
    validate_transition,
)

AT = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _case(**kwargs) -> E33Case:
    defaults = {
        "case_id": "e33case_test1",
        "client_id": 42,
        "basis": GuaranteeBasis.DEPOSIT,
        "owner": "surya@balizero.com",
    }
    defaults.update(kwargs)
    return E33Case(**defaults)


def _walk_to_annual_maintenance(case: E33Case) -> E33Case:
    """Drive a case through the full happy path."""
    case.advance(E33Stage.BANK_PRECHECK, at=AT)
    case.advance(E33Stage.APPLICATION, at=AT)
    case.advance(E33Stage.PAYMENT, at=AT)
    case.advance(E33Stage.VISA_ISSUED, at=AT)
    case.advance(E33Stage.ENTRY, at=AT, occurred_on=date(2026, 8, 10))
    case.advance(E33Stage.ITAS_ACTIVE, at=AT, occurred_on=date(2026, 8, 15))
    case.advance(E33Stage.GUARANTEE_PROOF_DUE, at=AT)
    case.advance(E33Stage.ANNUAL_MAINTENANCE, at=AT)
    return case


def _filed_guarantee_evidence() -> list[EvidenceRef]:
    return [
        EvidenceRef(
            evidence_id="ev_bank_1",
            kind=EvidenceKind.BANK_CONFIRMATION,
            document_ref="drive:file123",
            issued_date=date(2026, 8, 20),
        ),
        EvidenceRef(
            evidence_id="ev_filing_1",
            kind=EvidenceKind.IMMIGRATION_FILING,
            document_ref="crm:doc456",
            filed_date=date(2026, 9, 1),
            confirmed_by="surya@balizero.com",
        ),
    ]


# ── State machine ──────────────────────────────────────────────────────────────


class TestTransitions:
    def test_full_happy_path(self):
        case = _walk_to_annual_maintenance(_case())
        assert case.stage == E33Stage.ANNUAL_MAINTENANCE
        assert len(case.history) == 8
        assert case.history[0].from_stage is None or case.history[0].from_stage == E33Stage.FIT_MEMO

    def test_invalid_jump_raises(self):
        case = _case()
        with pytest.raises(E33InvalidTransitionError):
            case.advance(E33Stage.APPLICATION, at=AT)  # skips bank_precheck

    def test_same_stage_is_noop(self):
        assert validate_transition(E33Stage.FIT_MEMO, E33Stage.FIT_MEMO) is True

    def test_back_edge_one_step(self):
        case = _case()
        case.advance(E33Stage.BANK_PRECHECK, at=AT)
        case.advance(E33Stage.FIT_MEMO, at=AT)  # allowed correction
        assert case.stage == E33Stage.FIT_MEMO

    def test_epo_is_terminal(self):
        case = _case(stage=E33Stage.ITAS_ACTIVE)
        case.advance(E33Stage.EPO, at=AT)
        with pytest.raises(E33InvalidTransitionError):
            case.advance(E33Stage.RENEWAL, at=AT)

    def test_status_change_is_terminal(self):
        case = _case(stage=E33Stage.GUARANTEE_PROOF_DUE)
        case.advance(E33Stage.STATUS_CHANGE, at=AT)
        with pytest.raises(E33InvalidTransitionError):
            case.advance(E33Stage.ANNUAL_MAINTENANCE, at=AT)

    def test_renewal_reenters_itas_active(self):
        case = _walk_to_annual_maintenance(_case())
        case.advance(E33Stage.RENEWAL, at=AT)
        case.advance(E33Stage.ITAS_ACTIVE, at=AT, occurred_on=date(2031, 8, 20))
        assert case.stage == E33Stage.ITAS_ACTIVE
        assert case.itas_date == date(2031, 8, 20)

    def test_itap_eval_gated_by_default(self):
        case = _walk_to_annual_maintenance(_case())
        with pytest.raises(E33InvalidTransitionError, match="gated"):
            case.advance(E33Stage.ITAP_EVAL, at=AT)

    def test_itap_eval_allowed_when_enabled(self):
        case = _walk_to_annual_maintenance(_case())
        case.advance(E33Stage.ITAP_EVAL, at=AT, itap_eval_enabled=True)
        assert case.stage == E33Stage.ITAP_EVAL

    def test_entry_and_itas_dates_recorded(self):
        case = _case(stage=E33Stage.VISA_ISSUED)
        case.advance(E33Stage.ENTRY, at=AT, occurred_on=date(2026, 8, 10))
        case.advance(E33Stage.ITAS_ACTIVE, at=AT, occurred_on=date(2026, 8, 15))
        assert case.entry_date == date(2026, 8, 10)
        assert case.itas_date == date(2026, 8, 15)
        assert case.guarantee_anchor == date(2026, 8, 15)


# ── Day-90 guarantee gate ──────────────────────────────────────────────────────


class TestGuaranteeGate:
    def test_deadline_is_anchor_plus_90(self):
        assert compute_guarantee_deadline(date(2026, 8, 15)) == date(2026, 11, 13)

    def test_anchor_prefers_itas_over_entry(self):
        case = _case(
            stage=E33Stage.ITAS_ACTIVE,
            entry_date=date(2026, 8, 10),
            itas_date=date(2026, 8, 15),
        )
        assert case.guarantee_anchor == date(2026, 8, 15)
        entry_only = _case(stage=E33Stage.ENTRY, entry_date=date(2026, 8, 10))
        assert entry_only.guarantee_anchor == date(2026, 8, 10)

    def test_alert_schedule_day_30_60_75(self):
        schedule = guarantee_alert_schedule(date(2026, 8, 15))
        assert [(m.day_after_anchor, m.days_until_deadline) for m in schedule] == [
            (30, 60),
            (60, 30),
            (75, 15),
        ]
        assert schedule[0].at == date(2026, 9, 14)
        assert schedule[2].at == date(2026, 10, 29)

    def test_severity_boundaries(self):
        assert severity_for_days_until(61) == "info"
        assert severity_for_days_until(60) == "warning"
        assert severity_for_days_until(31) == "warning"
        assert severity_for_days_until(30) == "urgent"
        assert severity_for_days_until(8) == "urgent"
        assert severity_for_days_until(7) == "critical"
        assert severity_for_days_until(-1) == "critical"

    def _active_case(self) -> E33Case:
        return _case(
            stage=E33Stage.ITAS_ACTIVE,
            entry_date=date(2026, 8, 10),
            itas_date=date(2026, 8, 15),
        )

    def test_no_forecast_before_day_30(self):
        case = self._active_case()
        # Day 29 after anchor — first milestone not reached yet.
        assert case.build_case_forecasts(today=date(2026, 9, 13)) == []

    def test_forecast_at_day_30(self):
        case = self._active_case()
        forecasts = case.build_case_forecasts(today=date(2026, 9, 14))
        assert len(forecasts) == 1
        fc = forecasts[0]
        assert fc.matched_rule_id == RULE_ID_GUARANTEE_PROOF
        assert fc.document_type == DOCTYPE_GUARANTEE
        assert fc.days_until_expiry == 60
        assert fc.urgency_level == "warning"
        assert fc.expiry_date == date(2026, 11, 13)
        assert fc.client_id == 42

    def test_forecast_escalates_day_60_and_75(self):
        case = self._active_case()
        fc60 = case.build_case_forecasts(today=date(2026, 10, 14))[0]
        assert fc60.days_until_expiry == 30
        assert fc60.urgency_level == "urgent"
        fc75 = case.build_case_forecasts(today=date(2026, 10, 29))[0]
        assert fc75.days_until_expiry == 15
        assert fc75.urgency_level == "urgent"

    def test_overdue_forecast_is_critical(self):
        case = self._active_case()
        fc = case.build_case_forecasts(today=date(2026, 11, 20))[0]
        assert fc.days_until_expiry < 0
        assert fc.urgency_level == "critical"

    def test_no_forecast_once_proof_filed(self):
        case = self._active_case()
        for ev in _filed_guarantee_evidence():
            case.add_evidence(ev)
        assert case.build_case_forecasts(today=date(2026, 10, 14)) == []

    def test_no_forecast_for_terminal_stage(self):
        case = _case(
            stage=E33Stage.EPO,
            entry_date=date(2026, 8, 10),
            itas_date=date(2026, 8, 15),
        )
        assert case.build_case_forecasts(today=date(2026, 10, 14)) == []

    def test_property_basis_required_docs(self):
        case = _case(
            basis=GuaranteeBasis.PROPERTY,
            stage=E33Stage.ITAS_ACTIVE,
            itas_date=date(2026, 8, 15),
        )
        fc = case.build_case_forecasts(today=date(2026, 9, 14))[0]
        assert "property_title_proof" in fc.required_docs


# ── Annual maintenance ─────────────────────────────────────────────────────────


class TestAnnualMaintenance:
    def test_next_anniversary_same_day(self):
        assert next_itas_anniversary(date(2026, 8, 15), today=date(2027, 8, 15)) == date(
            2027, 8, 15
        )

    def test_next_anniversary_rolls_to_next_year(self):
        assert next_itas_anniversary(date(2026, 8, 15), today=date(2027, 9, 1)) == date(2028, 8, 15)

    def test_next_anniversary_feb29_safe(self):
        assert next_itas_anniversary(date(2028, 2, 29), today=date(2029, 1, 1)) == date(2029, 2, 28)

    def _maintained_case(self) -> E33Case:
        # Gate cleared = proof filed (the transition precondition in practice).
        case = _walk_to_annual_maintenance(_case())
        for ev in _filed_guarantee_evidence():
            case.add_evidence(ev)
        case.itas_date = date(2026, 8, 15)
        return case

    def test_maintenance_forecast_inside_window(self):
        case = self._maintained_case()
        forecasts = case.build_case_forecasts(today=date(2027, 7, 15))
        assert len(forecasts) == 1
        fc = forecasts[0]
        assert fc.matched_rule_id == RULE_ID_ANNUAL_MAINTENANCE
        assert fc.document_type == DOCTYPE_MAINTENANCE
        assert fc.days_until_expiry == 31
        assert fc.urgency_level == "warning"

    def test_maintenance_no_forecast_outside_window(self):
        case = self._maintained_case()
        assert case.build_case_forecasts(today=date(2027, 5, 1)) == []

    def test_maintenance_not_emitted_before_gate_cleared(self):
        case = _case(stage=E33Stage.GUARANTEE_PROOF_DUE, itas_date=date(2026, 8, 15))
        forecasts = case.build_case_forecasts(today=date(2027, 7, 15))
        assert all(fc.matched_rule_id != RULE_ID_ANNUAL_MAINTENANCE for fc in forecasts)


# ── No-custody + PII guardrails ────────────────────────────────────────────────


class TestNoCustody:
    @pytest.mark.parametrize(
        "bad_key",
        ["balance", "account_number", "Amount", "nomor_rekening", "saldo", "iban"],
    )
    def test_custody_keys_rejected(self, bad_key: str):
        with pytest.raises(CustodyViolationError):
            EvidenceRef(
                evidence_id="ev_x",
                kind=EvidenceKind.BANK_CONFIRMATION,
                document_ref="drive:file1",
                metadata={bad_key: "anything"},
            )

    @pytest.mark.parametrize(
        "bad_key",
        ["account_balance", "deposit_amount", "bank_account", "total_saldo", "swift_code"],
    )
    def test_compound_custody_keys_rejected(self, bad_key: str):
        """Gemini F3-review blocker: exact-match normalization let compound
        keys bypass the no-custody SOP; substring matching must catch them."""
        with pytest.raises(CustodyViolationError):
            EvidenceRef(
                evidence_id="ev_x",
                kind=EvidenceKind.BANK_CONFIRMATION,
                document_ref="drive:file1",
                metadata={bad_key: "anything"},
            )

    def test_reference_metadata_accepted(self):
        ev = EvidenceRef(
            evidence_id="ev_ok",
            kind=EvidenceKind.BANK_CONFIRMATION,
            document_ref="drive:file1",
            metadata={"bank_name": "Bank Mandiri", "letter_date": "2026-08-20"},
        )
        assert ev.metadata["bank_name"] == "Bank Mandiri"

    def test_evidence_complete_requires_basis_and_filing(self):
        case = _case(stage=E33Stage.ITAS_ACTIVE, itas_date=date(2026, 8, 15))
        case.add_evidence(_filed_guarantee_evidence()[0])  # bank confirmation only
        assert case.guarantee_basis_evidence_complete is True
        assert case.guarantee_evidence_complete is False
        case.add_evidence(_filed_guarantee_evidence()[1])  # filing
        assert case.guarantee_evidence_complete is True

    def test_property_basis_needs_title_not_bank_letter(self):
        case = _case(basis=GuaranteeBasis.PROPERTY)
        case.add_evidence(_filed_guarantee_evidence()[0])
        assert case.guarantee_basis_evidence_complete is False
        case.add_evidence(
            EvidenceRef(
                evidence_id="ev_title",
                kind=EvidenceKind.PROPERTY_TITLE,
                document_ref="drive:file999",
                issued_date=date(2026, 8, 20),
            )
        )
        assert case.guarantee_basis_evidence_complete is True


# ── StayGuard hook ─────────────────────────────────────────────────────────────


class TestStayGuard:
    def test_not_eligible_before_itas(self):
        assert _case().stayguard_eligible is False

    def test_not_eligible_without_complete_evidence(self):
        case = _case(stage=E33Stage.ITAS_ACTIVE, itas_date=date(2026, 8, 15))
        assert case.stayguard_eligible is False

    def test_eligible_with_evidence_complete(self):
        case = _case(stage=E33Stage.ITAS_ACTIVE, itas_date=date(2026, 8, 15))
        for ev in _filed_guarantee_evidence():
            case.add_evidence(ev)
        assert case.stayguard_eligible is True

    def test_not_eligible_when_terminal(self):
        case = _case(stage=E33Stage.EPO, itas_date=date(2026, 8, 15))
        for ev in _filed_guarantee_evidence():
            case.add_evidence(ev)
        assert case.stayguard_eligible is False


# ── Dependents (configurable codes) ────────────────────────────────────────────


class TestDependents:
    def test_default_codes_accepted(self):
        for code in DEFAULT_DEPENDENT_CODES:
            assert validate_dependent_code(code) == code

    def test_unknown_code_rejected(self):
        with pytest.raises(UnknownDependentCodeError):
            validate_dependent_code("E31Z")

    def test_codes_configurable(self):
        assert validate_dependent_code("E31Z", allowed=("E31Z",)) == "E31Z"

    def test_dependent_link_on_case(self):
        case = _case()
        link = DependentLink(code="E31B", client_id=77, relationship="spouse")
        case.dependents.append(link)
        assert case.dependents[0].code == "E31B"


# ── Alerts-engine wiring ───────────────────────────────────────────────────────


class TestAlertsWiring:
    def test_doctypes_map_to_registered_category(self):
        for doctype in (DOCTYPE_GUARANTEE, DOCTYPE_MAINTENANCE):
            category = _DOCTYPE_TO_CATEGORY[doctype]
            assert category in TEMPLATE_REGISTRY

    def test_guarantee_template_renders_with_forecast_kwargs(self):
        body = render_template(
            "guarantee_proof", "body", "en", days_until=60, doc_type="e33_guarantee"
        )
        assert "60 days" in body

    def test_forecast_shapes_compatible_with_engine(self):
        case = _case(stage=E33Stage.ITAS_ACTIVE, itas_date=date(2026, 8, 15))
        fc = case.build_case_forecasts(today=date(2026, 9, 14))[0]
        # AlertsEngine reads these verbatim.
        assert fc.urgency_level in {"info", "warning", "urgent", "critical"}
        assert fc.matched_rule_id  # becomes compliance_item_ref (dedup key)
        assert fc.renewal_pricing_key is None  # no pricing — evidence deadline

    def test_renewal_rule_matches_e33(self):
        rule = match_rule("kitas", "E33 Second Home")
        assert rule.rule_id == "e33_second_home_renewal"

    def test_renewal_rule_does_not_steal_e33g(self):
        # E33G remote worker has its own rule earlier in priority order.
        rule = match_rule("kitas", "E33G Remote Worker")
        assert rule.rule_id == "kitas_remote_worker_extend"


# ── Repository (de)serialization round-trip ────────────────────────────────────


class TestRepositorySerialization:
    def test_case_row_round_trip(self):
        case = _walk_to_annual_maintenance(_case(practice_id=123))
        for ev in _filed_guarantee_evidence():
            case.add_evidence(ev)
        case.dependents.append(DependentLink(code="E31B", client_id=77, relationship="spouse"))

        row = case_to_row(case)
        assert row["guarantee_proof_deadline"] == date(2026, 11, 13)
        assert row["stayguard_eligible"] is True
        assert row["stage"] == "annual_maintenance"

        restored = row_to_case(row)
        assert restored.case_id == case.case_id
        assert restored.stage == case.stage
        assert restored.basis == case.basis
        assert restored.entry_date == case.entry_date
        assert restored.itas_date == case.itas_date
        assert len(restored.history) == len(case.history)
        assert len(restored.evidence) == 2
        assert restored.evidence[0].kind == EvidenceKind.BANK_CONFIRMATION
        assert restored.dependents[0].code == "E31B"
        assert restored.stayguard_eligible is True


# ── No-custody boundary pinning (documented scope decision) ──────────────────


class TestNoCustodyBoundary:
    def test_document_ref_is_not_content_scanned(self):
        """Pin the documented boundary: the guard validates metadata KEYS only.

        document_ref is free-text and NOT scanned — keeping custody data out
        of free-text fields is a CRM/UI-layer responsibility (see module
        docstring). This test exists so the boundary is read as a decision,
        not mistaken for a gap.
        """
        ev = EvidenceRef(
            evidence_id="ev_boundary",
            kind=EvidenceKind.BANK_CONFIRMATION,
            document_ref="free text mentioning account_number and balance",
        )
        assert "account_number" in ev.document_ref  # accepted by design


# ── AlertsEngine integration (stubbed persistence, no DB) ────────────────────


class _StubAlertRepo:
    """In-memory AlertRepository stand-in (find/insert/promote only)."""

    def __init__(self) -> None:
        self.rows: dict[str, object] = {}

    async def find_active_by_dedup_key(self, dedup_key: str):
        return self.rows.get(dedup_key)

    async def insert(self, row):
        self.rows[row.dedup_key] = row
        return row

    async def promote(self, alert_id: str, *, new_severity: str, new_days_until: int):
        row = next(r for r in self.rows.values() if r.alert_id == alert_id)
        row.severity = new_severity
        row.days_until = new_days_until
        return row


def _engine_with_stub_repo() -> tuple[AlertsEngine, _StubAlertRepo, AsyncMock]:
    pricing = MagicMock()
    pricing.get_price = MagicMock(return_value=None)
    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=True)
    engine = AlertsEngine(MagicMock(), pricing=pricing, dispatcher=dispatcher)
    stub = _StubAlertRepo()
    engine._repo = stub
    return engine, stub, dispatcher


class TestAlertsEngineIntegration:
    @pytest.mark.asyncio
    async def test_case_forecast_produces_guarantee_proof_alert(self):
        case = _case(stage=E33Stage.ITAS_ACTIVE, itas_date=date(2026, 8, 15))
        forecasts = case.build_case_forecasts(today=date(2026, 9, 14))  # Day 30
        engine, _stub, dispatcher = _engine_with_stub_repo()

        alerts = await engine.generate_alerts(forecasts)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.category == "guarantee_proof"
        assert alert.severity == "warning"  # 60 days until deadline
        assert alert.compliance_item_ref == RULE_ID_GUARANTEE_PROOF
        assert "60 days" in alert.message_en
        dispatcher.dispatch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedup_and_severity_promotion_across_milestones(self):
        case = _case(stage=E33Stage.ITAS_ACTIVE, itas_date=date(2026, 8, 15))
        engine, _stub, dispatcher = _engine_with_stub_repo()

        day30 = await engine.generate_alerts(case.build_case_forecasts(today=date(2026, 9, 14)))
        dispatcher.reset_mock()

        # Same milestone again → dedup: existing alert, no re-dispatch.
        again = await engine.generate_alerts(case.build_case_forecasts(today=date(2026, 9, 14)))
        assert again[0].alert_id == day30[0].alert_id
        dispatcher.dispatch.assert_not_awaited()

        # Day 60 (30 left, urgent) → severity promotion on the same dedup key.
        promoted = await engine.generate_alerts(case.build_case_forecasts(today=date(2026, 10, 14)))
        assert promoted[0].alert_id == day30[0].alert_id
        assert promoted[0].severity == "urgent"
        dispatcher.dispatch.assert_awaited_once()


# ── Repository through with_connection (stubbed connection, no DB) ────────────


class TestRepositoryWithConnection:
    @pytest.mark.asyncio
    async def test_insert_binds_case_columns(self):
        conn = AsyncMock()
        repo = E33CaseRepository.with_connection(conn)
        case = _walk_to_annual_maintenance(_case())

        await repo.insert(case)

        conn.execute.assert_awaited_once()
        bind_args = conn.execute.await_args.args
        assert bind_args[1] == case.case_id  # first bind param after the SQL
        assert bind_args[2] == case.client_id
        assert bind_args[4] == case.basis.value

    @pytest.mark.asyncio
    async def test_load_round_trip_via_stubbed_connection(self):
        conn = AsyncMock()
        repo = E33CaseRepository.with_connection(conn)
        case = _walk_to_annual_maintenance(_case())
        for ev in _filed_guarantee_evidence():
            case.add_evidence(ev)
        conn.fetchrow = AsyncMock(return_value=case_to_row(case))

        loaded = await repo.load(case.case_id)

        assert loaded is not None
        assert loaded.case_id == case.case_id
        assert loaded.stage == case.stage
        assert loaded.guarantee_deadline == case.guarantee_deadline
        assert loaded.stayguard_eligible is True
        assert len(loaded.evidence) == 2
