"""Unit tests for the Visa Match decision tree.

Covers every branch + the 'catch-all referral' behaviour.
"""

from __future__ import annotations

from backend.services.visa_check.catalogue import VisaType
from backend.services.visa_check.match_tree import (
    BudgetBand,
    Purpose,
    recommend_visa,
)


def _call(
    *,
    purpose: Purpose,
    duration_months: int = 6,
    budget_band: BudgetBand = BudgetBand.MID_50_500M,
    nationality: str = "USA",
):
    return recommend_visa(
        nationality=nationality,
        purpose=purpose,
        duration_months=duration_months,
        budget_band=budget_band,
    )


class TestOther:
    def test_other_always_refers(self):
        r = _call(purpose=Purpose.OTHER)
        assert r.recommended_visa is None
        assert r.referral_mode is True
        assert "WhatsApp" in r.reason


class TestLongTourism:
    def test_short_trip_is_C1(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        assert r.recommended_visa is VisaType.C1
        assert VisaType.B211A in r.alternatives
        assert r.referral_mode is False

    def test_medium_trip_is_B211A(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=5)
        assert r.recommended_visa is VisaType.B211A

    def test_too_long_tourism_refers(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=10)
        assert r.recommended_visa is None
        assert r.referral_mode is True


class TestWorkRemote:
    def test_under_budget_falls_back_to_B211A(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.UNDER_50M)
        assert r.recommended_visa is VisaType.B211A
        assert VisaType.E33G in r.alternatives

    def test_mid_budget_is_E33G(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.MID_50_500M)
        assert r.recommended_visa is VisaType.E33G

    def test_high_budget_is_E33G(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.OVER_500M)
        assert r.recommended_visa is VisaType.E33G


class TestInvestor:
    def test_high_budget_is_E28A(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.OVER_500M)
        assert r.recommended_visa is VisaType.E28A

    def test_mid_budget_is_E33G(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.MID_50_500M)
        assert r.recommended_visa is VisaType.E33G
        assert VisaType.E28A in r.alternatives

    def test_under_budget_refers(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.UNDER_50M)
        assert r.recommended_visa is None
        assert r.referral_mode is True


class TestSimpleBranches:
    def test_work_employee_is_E23(self):
        assert _call(purpose=Purpose.WORK_EMPLOYEE).recommended_visa is VisaType.E23

    def test_family_is_E31(self):
        assert _call(purpose=Purpose.FAMILY).recommended_visa is VisaType.E31

    def test_retirement_is_E33F(self):
        assert _call(purpose=Purpose.RETIREMENT).recommended_visa is VisaType.E33F

    def test_student_is_E30A(self):
        assert _call(purpose=Purpose.STUDENT).recommended_visa is VisaType.E30A


class TestPreArrivalSteps:
    def test_all_rules_with_recommendation_return_steps(self):
        scenarios = [
            (Purpose.LONG_TOURISM, 1, BudgetBand.MID_50_500M),
            (Purpose.WORK_REMOTE, 12, BudgetBand.OVER_500M),
            (Purpose.INVESTOR, 24, BudgetBand.OVER_500M),
            (Purpose.WORK_EMPLOYEE, 12, BudgetBand.MID_50_500M),
            (Purpose.FAMILY, 12, BudgetBand.UNDER_50M),
            (Purpose.RETIREMENT, 12, BudgetBand.MID_50_500M),
            (Purpose.STUDENT, 12, BudgetBand.UNDER_50M),
        ]
        for purpose, months, band in scenarios:
            r = _call(purpose=purpose, duration_months=months, budget_band=band)
            if r.recommended_visa is not None:
                assert len(r.pre_arrival_steps) >= 3, (
                    f"{purpose} with {band.value} should produce pre-arrival steps"
                )
