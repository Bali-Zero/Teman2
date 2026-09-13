"""Tests for backend.services.portal.challenge_leaderboard — pure scoring only.

No DB, no FastAPI: `compute_awards` and `merge_roster_and_activity` are plain
Python over dataclasses, exercised directly. SQL-string builders are checked
only for interpolation, not against a live database (that's done once by hand
against prod read-only per the PR evidence pack, not on every CI run).
"""

from datetime import datetime, timezone

from backend.services.portal.challenge_leaderboard import (
    TAX_FALLBACK_BONUS_IDR,
    TAX_FALLBACK_THRESHOLD,
    TAX_PODIUM_BONUS_IDR,
    WINDOW_END,
    WINDOW_START,
    MemberActivations,
    build_aggregates_sql,
    build_recent_activations_sql,
    build_team_total_activations_sql,
    compute_awards,
    compute_status,
    member_key_from_email,
    merge_roster_and_activity,
)


def _member(email: str, activations: int, *, is_tax: bool = False, last=None) -> MemberActivations:
    return MemberActivations(
        email=email,
        member=member_key_from_email(email),
        display_name=email.split("@")[0].title(),
        department="tax" if is_tax else "setup",
        is_tax=is_tax,
        activations=activations,
        invited=activations,
        last_activation_at=last or (datetime(2026, 9, 20, tzinfo=timezone.utc) if activations else None),
    )


class TestComputeAwardsExample:
    def test_17_then_16_matches_spec_example(self):
        """#1 has 17 -> tier2 (1.5M); #2 has 16 -> tier3 (700k); tier1 unawarded."""
        members = [_member("a@balizero.com", 17), _member("b@balizero.com", 16)]
        awarded = compute_awards(members)
        by_email = {e.email: e for e in awarded}

        assert by_email["a@balizero.com"].award_tier == 2
        assert by_email["a@balizero.com"].prize_idr == 1_500_000
        assert by_email["b@balizero.com"].award_tier == 3
        assert by_email["b@balizero.com"].prize_idr == 700_000

    def test_top_scorer_gets_tier1_when_threshold_met(self):
        members = [_member("a@balizero.com", 25), _member("b@balizero.com", 17)]
        awarded = compute_awards(members)
        by_email = {e.email: e for e in awarded}
        assert by_email["a@balizero.com"].award_tier == 1
        assert by_email["a@balizero.com"].prize_idr == 3_000_000
        # 17 still qualifies for tier2 (15) since tier1 is now taken by a, not b
        assert by_email["b@balizero.com"].award_tier == 2


class TestRankingAndTieBreak:
    def test_ties_share_rank_earlier_activation_wins_award_order(self):
        early = datetime(2026, 9, 15, tzinfo=timezone.utc)
        late = datetime(2026, 9, 25, tzinfo=timezone.utc)
        members = [
            _member("late@balizero.com", 20, last=late),
            _member("early@balizero.com", 20, last=early),
        ]
        awarded = compute_awards(members)
        by_email = {e.email: e for e in awarded}
        # Both hit the same activations count -> same dense rank.
        assert by_email["late@balizero.com"].rank == by_email["early@balizero.com"].rank == 1
        # But the earlier finisher is processed first for award assignment,
        # taking tier1; tier2 remains for the later one (25 also >= 20,
        # but tier1 is already gone).
        assert by_email["early@balizero.com"].award_tier == 1
        assert by_email["late@balizero.com"].award_tier == 2

    def test_zero_activation_members_share_bottom_rank(self):
        members = [
            _member("winner@balizero.com", 5),
            _member("zero1@balizero.com", 0),
            _member("zero2@balizero.com", 0),
        ]
        awarded = compute_awards(members)
        by_email = {e.email: e for e in awarded}
        assert by_email["zero1@balizero.com"].rank == by_email["zero2@balizero.com"].rank
        assert by_email["winner@balizero.com"].rank < by_email["zero1@balizero.com"].rank

    def test_zero_activation_members_never_awarded(self):
        members = [_member("zero@balizero.com", 0)]
        awarded = compute_awards(members)
        assert awarded[0].award_tier is None
        assert awarded[0].prize_idr == 0
        assert awarded[0].total_prize_idr == 0


class TestNextTierThreshold:
    def test_below_first_tier(self):
        awarded = compute_awards([_member("m@balizero.com", 4)])
        assert awarded[0].next_tier_threshold == 10
        assert awarded[0].to_next_tier == 6

    def test_at_or_above_top_tier_has_no_next(self):
        awarded = compute_awards([_member("m@balizero.com", 25)])
        assert awarded[0].next_tier_threshold is None
        assert awarded[0].to_next_tier is None

    def test_exactly_on_a_threshold_has_no_gap_to_that_tier(self):
        awarded = compute_awards([_member("m@balizero.com", 15)])
        # 15 meets tier2 already; next threshold above 15 is 20 (tier1).
        assert awarded[0].next_tier_threshold == 20
        assert awarded[0].to_next_tier == 5


class TestTaxBonus:
    def test_tax_member_on_podium_gets_podium_bonus(self):
        members = [_member("tax1@balizero.com", 20, is_tax=True)]
        awarded = compute_awards(members)
        e = awarded[0]
        assert e.award_tier == 1
        assert e.tax_bonus_idr == TAX_PODIUM_BONUS_IDR
        assert e.total_prize_idr == e.prize_idr + TAX_PODIUM_BONUS_IDR

    def test_multiple_tax_members_on_podium_each_get_bonus(self):
        members = [
            _member("tax1@balizero.com", 20, is_tax=True),
            _member("tax2@balizero.com", 15, is_tax=True),
            _member("tax3@balizero.com", 10, is_tax=True),
        ]
        awarded = compute_awards(members)
        assert all(e.tax_bonus_idr == TAX_PODIUM_BONUS_IDR for e in awarded)
        for e in awarded:
            assert e.total_prize_idr == e.prize_idr + TAX_PODIUM_BONUS_IDR

    def _three_nontax_podium(self) -> list[MemberActivations]:
        """tier1/2/3 all claimed by non-tax members, so any tax member at
        exactly the fallback threshold (== tier3's own threshold) still
        misses the podium — it ranks below the 11-activation tier3 holder."""
        return [
            _member("nontax1@balizero.com", 22, is_tax=False),  # tier1 (>=20)
            _member("nontax2@balizero.com", 17, is_tax=False),  # tier2 (>=15)
            _member("nontax3@balizero.com", 11, is_tax=False),  # tier3 (>=10)
        ]

    def test_no_tax_on_podium_falls_back_to_best_tax_at_or_above_10(self):
        members = [*self._three_nontax_podium(), _member("tax_ok@balizero.com", 10, is_tax=True)]
        awarded = compute_awards(members)
        by_email = {e.email: e for e in awarded}
        assert by_email["tax_ok@balizero.com"].award_tier is None
        assert by_email["tax_ok@balizero.com"].tax_bonus_idr == TAX_FALLBACK_BONUS_IDR
        assert (
            by_email["tax_ok@balizero.com"].total_prize_idr
            == by_email["tax_ok@balizero.com"].prize_idr + TAX_FALLBACK_BONUS_IDR
        )
        assert by_email["nontax3@balizero.com"].tax_bonus_idr == 0

    def test_fallback_requires_threshold_9_fails_10_passes(self):
        below = compute_awards(
            [
                *self._three_nontax_podium(),
                _member("tax_9@balizero.com", TAX_FALLBACK_THRESHOLD - 1, is_tax=True),
            ]
        )
        assert all(e.tax_bonus_idr == 0 for e in below)

        at_threshold = compute_awards(
            [
                *self._three_nontax_podium(),
                _member("tax_10@balizero.com", TAX_FALLBACK_THRESHOLD, is_tax=True),
            ]
        )
        by_email = {e.email: e for e in at_threshold}
        assert by_email["tax_10@balizero.com"].award_tier is None
        assert by_email["tax_10@balizero.com"].tax_bonus_idr == TAX_FALLBACK_BONUS_IDR

    def test_fallback_picks_best_ranked_tax_member_only(self):
        early = datetime(2026, 9, 15, tzinfo=timezone.utc)
        late = datetime(2026, 9, 25, tzinfo=timezone.utc)
        members = [
            *self._three_nontax_podium(),
            _member("tax_high@balizero.com", 10, is_tax=True, last=early),
            _member("tax_low@balizero.com", 10, is_tax=True, last=late),
        ]
        awarded = compute_awards(members)
        by_email = {e.email: e for e in awarded}
        assert by_email["tax_high@balizero.com"].award_tier is None
        assert by_email["tax_high@balizero.com"].tax_bonus_idr == TAX_FALLBACK_BONUS_IDR
        assert by_email["tax_low@balizero.com"].tax_bonus_idr == 0

    def test_no_tax_member_qualifies_no_fallback_awarded(self):
        members = [
            _member("nontax@balizero.com", 20, is_tax=False),
            _member("tax_low@balizero.com", 3, is_tax=True),
        ]
        awarded = compute_awards(members)
        assert all(e.tax_bonus_idr == 0 for e in awarded)


class TestMergeRosterAndActivity:
    def test_roster_member_with_zero_activity_is_included(self):
        roster = [
            {"email": "a@balizero.com", "display_name": "A", "department": "setup", "role": "member"}
        ]
        merged = merge_roster_and_activity(roster, [])
        assert len(merged) == 1
        assert merged[0].activations == 0

    def test_credited_creator_not_in_roster_is_still_included(self):
        merged = merge_roster_and_activity(
            [],
            [{"creator_email": "ghost@balizero.com", "activations": 3, "invited": 4, "last_activation_at": None}],
        )
        assert len(merged) == 1
        assert merged[0].display_name == "ghost"
        assert merged[0].is_tax is False

    def test_service_and_test_accounts_excluded_from_zero_activity_roster(self):
        roster = [
            {"email": "healthcheck@balizero.com", "display_name": "Probe", "department": None, "role": "monitoring"},
            {"email": "test@balizero.com", "display_name": "Test User", "department": "Engineering", "role": "member"},
            {"email": "real@balizero.com", "display_name": "Real", "department": "setup", "role": "member"},
        ]
        merged = merge_roster_and_activity(roster, [])
        emails = {m.email for m in merged}
        assert emails == {"real@balizero.com"}

    def test_department_case_insensitive_tax_flag(self):
        roster = [{"email": "a@balizero.com", "display_name": "A", "department": "Tax", "role": "member"}]
        merged = merge_roster_and_activity(roster, [])
        assert merged[0].is_tax is True


class TestComputeStatus:
    def test_before_window(self):
        assert compute_status(WINDOW_START.replace(year=2026, month=9, day=1)) == "upcoming"

    def test_inside_window(self):
        assert compute_status(WINDOW_START) == "live"

    def test_at_or_after_window_end(self):
        assert compute_status(WINDOW_END) == "closed"


class TestSqlBuilders:
    def test_aggregates_sql_interpolates_window_bounds(self):
        sql = build_aggregates_sql()
        assert "2026-09-14" in sql
        assert "2026-09-30" in sql
        assert "{start_ts}" not in sql and "{end_ts}" not in sql

    def test_recent_activations_sql_interpolates_window_bounds(self):
        sql = build_recent_activations_sql()
        assert "2026-09-14" in sql
        assert "2026-09-30" in sql

    def test_team_total_sql_counts_distinct_client_id_not_a_per_creator_sum(self):
        sql = build_team_total_activations_sql()
        assert "2026-09-14" in sql
        assert "2026-09-30" in sql
        assert "COUNT(DISTINCT client_id)" in sql
        assert "FROM window_activations" in sql
        # Must NOT group by creator — a per-creator GROUP BY here would just
        # reproduce build_aggregates_sql()'s per-creator counts, which is
        # exactly the double-counting shape this query exists to avoid.
        assert "GROUP BY" not in sql
