"""Unit tests for the Visa Match decision tree.

Covers every branch, the ranked-result shape, and backwards-compat
property accessors used by the router.
"""

from __future__ import annotations

from backend.services.visa_check.catalogue import VISA_META, VisaType
from backend.services.visa_check.match_tree import (
    BudgetBand,
    MatchResult,
    Purpose,
    RankedVisa,
    recommend_visa,
)


def _call(
    *,
    purpose: Purpose,
    duration_months: int = 6,
    budget_band: BudgetBand = BudgetBand.MID_50_500M,
    nationality: str = "USA",
) -> MatchResult:
    return recommend_visa(
        nationality=nationality,
        purpose=purpose,
        duration_months=duration_months,
        budget_band=budget_band,
    )


class TestRankedShape:
    def test_ranking_is_list_of_rankedvisa(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        assert isinstance(r.ranking, list)
        for item in r.ranking:
            assert isinstance(item, RankedVisa)

    def test_ranking_sorted_by_score_desc(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.MID_50_500M)
        scores = [rv.score for rv in r.ranking]
        assert scores == sorted(scores, reverse=True)

    def test_every_ranked_visa_is_in_visa_meta(self):
        for purpose in Purpose:
            if purpose == Purpose.OTHER:
                continue
            for band in BudgetBand:
                r = _call(purpose=purpose, duration_months=6, budget_band=band)
                for rv in r.ranking:
                    assert rv.visa in VISA_META, f"{rv.visa} not in VISA_META"

    def test_scores_in_unit_range(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.OVER_500M)
        for rv in r.ranking:
            assert 0.0 <= rv.score <= 1.0


class TestBackwardsCompatProperties:
    def test_recommended_visa_is_ranking_zero(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        if r.ranking:
            assert r.recommended_visa == r.ranking[0].visa
        else:
            assert r.recommended_visa is None

    def test_alternatives_is_ranking_tail(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.OVER_500M)
        expected = [rv.visa for rv in r.ranking[1:]]
        assert r.alternatives == expected

    def test_reason_is_ranking_zero_reason(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        if r.ranking:
            assert r.reason == r.ranking[0].reason


class TestOther:
    def test_other_always_refers(self):
        r = _call(purpose=Purpose.OTHER)
        assert r.recommended_visa is None
        assert r.referral_mode is True
        assert r.ranking == []
        assert "WhatsApp" in r.reason


class TestLongTourism:
    def test_short_trip_is_C1(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=1)
        assert r.recommended_visa is VisaType.C1
        assert r.referral_mode is False

    def test_medium_trip_stays_within_tourism_set(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=5)
        # Must pick a C-series or referral — never B211A (it's gone).
        allowed = {VisaType.C1, VisaType.C2, VisaType.C6, None}
        assert r.recommended_visa in allowed

    def test_too_long_tourism_refers(self):
        r = _call(purpose=Purpose.LONG_TOURISM, duration_months=10)
        assert r.recommended_visa is None
        assert r.referral_mode is True


class TestWorkRemote:
    def test_under_budget_still_produces_ranking(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.UNDER_50M)
        # Under-budget users get C1/C2 short-term options, not a referral.
        assert r.referral_mode is False
        assert r.recommended_visa in {VisaType.C1, VisaType.C2, VisaType.E23_FREELANCE}

    def test_mid_budget_is_E33G(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.MID_50_500M)
        assert r.recommended_visa is VisaType.E33G

    def test_high_budget_is_E33G(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.OVER_500M)
        assert r.recommended_visa is VisaType.E33G

    def test_e23_freelance_appears_with_fit_tag(self):
        r = _call(purpose=Purpose.WORK_REMOTE, budget_band=BudgetBand.MID_50_500M)
        freelance = next((rv for rv in r.ranking if rv.visa == VisaType.E23_FREELANCE), None)
        if freelance is not None:
            assert "invoices_indonesian_clients" in freelance.fit_tags


class TestInvestor:
    def test_high_budget_is_E28A(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.OVER_500M)
        assert r.recommended_visa is VisaType.E28A

    def test_mid_budget_ranking_includes_e33g_and_e28a(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.MID_50_500M)
        visas = {rv.visa for rv in r.ranking}
        assert VisaType.E33G in visas
        assert VisaType.D12 in visas or VisaType.E28A in visas

    def test_under_budget_refers(self):
        r = _call(purpose=Purpose.INVESTOR, budget_band=BudgetBand.UNDER_50M)
        assert r.recommended_visa is None
        assert r.referral_mode is True


class TestSimpleBranches:
    def test_work_employee_is_E23(self):
        r = _call(purpose=Purpose.WORK_EMPLOYEE, duration_months=12)
        assert r.recommended_visa is VisaType.E23

    def test_work_employee_short_can_suggest_c18(self):
        r = _call(purpose=Purpose.WORK_EMPLOYEE, duration_months=3)
        assert r.recommended_visa in {VisaType.E23, VisaType.C18, VisaType.C22A}

    def test_family_is_E31(self):
        assert _call(purpose=Purpose.FAMILY).recommended_visa is VisaType.E31

    def test_retirement_standard_is_E33F(self):
        r = _call(purpose=Purpose.RETIREMENT, budget_band=BudgetBand.MID_50_500M)
        assert r.recommended_visa is VisaType.E33F

    def test_retirement_high_budget_surfaces_E33E(self):
        r = _call(purpose=Purpose.RETIREMENT, budget_band=BudgetBand.OVER_500M)
        visas = {rv.visa for rv in r.ranking}
        assert VisaType.E33E in visas

    def test_student_is_E30A(self):
        assert _call(purpose=Purpose.STUDENT).recommended_visa is VisaType.E30A


class TestPreArrivalSteps:
    def test_all_branches_with_recommendation_return_steps(self):
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


class TestCoverageSweep:
    """Every purpose × budget combination must produce either a ranking or a referral."""

    def test_all_combinations_terminate(self):
        for purpose in Purpose:
            for band in BudgetBand:
                for months in (1, 6, 12, 24):
                    r = _call(purpose=purpose, duration_months=months, budget_band=band)
                    assert r.ranking or r.referral_mode, (
                        f"purpose={purpose} months={months} band={band} produced empty+no-referral"
                    )
