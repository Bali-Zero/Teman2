"""Tests for backend.services.portal.challenge_round2 — Round 2 "Lascia o
raddoppia" scoring engine (October window). Pure-function tests only, no DB —
mirrors the style of the R1 tests for `challenge_leaderboard`.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.portal import challenge_round2 as r2
from backend.services.portal.challenge_leaderboard import WITA, AwardedEntry
from backend.services.portal.challenge_round2 import WORKDAY_HOURS

# ── working_hours_between / working_deadline ────────────────────────────────


class TestWorkingHoursBetween:
    def test_friday_evening_to_monday_morning_is_the_guides_example(self):
        start = datetime(2026, 10, 2, 17, 0, tzinfo=WITA)  # Friday
        end = datetime(2026, 10, 5, 10, 30, tzinfo=WITA)  # Monday
        assert r2.working_hours_between(start, end) == pytest.approx(3.0)

    def test_weekend_only_span_is_zero(self):
        start = datetime(2026, 10, 3, 12, 0, tzinfo=WITA)  # Saturday
        end = datetime(2026, 10, 4, 12, 0, tzinfo=WITA)  # Sunday
        assert r2.working_hours_between(start, end) == 0.0

    def test_inside_a_single_working_day(self):
        start = datetime(2026, 10, 1, 9, 0, tzinfo=WITA)  # Thursday
        end = datetime(2026, 10, 1, 11, 0, tzinfo=WITA)
        assert r2.working_hours_between(start, end) == pytest.approx(2.0)

    def test_across_two_working_days_full_first_day(self):
        # Thursday 09:00 -> Friday 09:00 = one full working day (9.5h)
        start = datetime(2026, 10, 1, 9, 0, tzinfo=WITA)
        end = datetime(2026, 10, 2, 9, 0, tzinfo=WITA)
        assert r2.working_hours_between(start, end) == pytest.approx(9.5)

    def test_end_before_start_is_zero(self):
        start = datetime(2026, 10, 2, 17, 0, tzinfo=WITA)
        end = datetime(2026, 10, 1, 9, 0, tzinfo=WITA)
        assert r2.working_hours_between(start, end) == 0.0

    def test_naive_inputs_are_treated_as_utc(self):
        # 2026-10-01 09:00 UTC == 2026-10-01 17:00 WITA (UTC+8)
        start_naive = datetime(2026, 10, 1, 9, 0)
        end_naive = datetime(2026, 10, 1, 10, 30)
        start_aware = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
        end_aware = datetime(2026, 10, 1, 10, 30, tzinfo=timezone.utc)
        assert r2.working_hours_between(start_naive, end_naive) == pytest.approx(
            r2.working_hours_between(start_aware, end_aware)
        )
        # 17:00-18:30 WITA is within business hours -> 1.5h
        assert r2.working_hours_between(start_naive, end_naive) == pytest.approx(1.5)


class TestWorkingDeadline:
    def test_is_the_inverse_of_the_guides_example(self):
        start = datetime(2026, 10, 2, 17, 0, tzinfo=WITA)  # Friday
        deadline = r2.working_deadline(start, 3.0)
        assert deadline == datetime(2026, 10, 5, 10, 30, tzinfo=WITA)  # Monday

    def test_one_working_day_lands_on_the_same_clock_time_next_business_day(self):
        start = datetime(2026, 10, 1, 12, 0, tzinfo=WITA)  # Thursday midday
        deadline = r2.working_deadline(start, WORKDAY_HOURS)
        assert deadline == datetime(2026, 10, 2, 12, 0, tzinfo=WITA)  # Friday, same time

    def test_exactly_one_working_day_from_the_opening_bell_lands_at_closing(self):
        # Starting AT the 09:00 opening bell, 9.5h (one full working day) is
        # consumed entirely within that same day, landing exactly at 18:30 —
        # the boundary case of the rule above.
        start = datetime(2026, 10, 1, 9, 0, tzinfo=WITA)  # Thursday
        deadline = r2.working_deadline(start, WORKDAY_HOURS)
        assert deadline == datetime(2026, 10, 1, 18, 30, tzinfo=WITA)


# ── active_round / compute_round_status ─────────────────────────────────────


class TestActiveRound:
    def test_before_round2_start_is_round_1(self):
        now = r2.ROUND2_START - timedelta(seconds=1)
        assert r2.active_round(now) == 1

    def test_at_or_after_round2_start_is_round_2(self):
        assert r2.active_round(r2.ROUND2_START) == 2
        assert r2.active_round(r2.ROUND2_START + timedelta(days=1)) == 2

    def test_freezes_consistently_on_both_sides_of_the_boundary(self):
        just_before = r2.ROUND2_START - timedelta(microseconds=1)
        just_after = r2.ROUND2_START
        assert r2.active_round(just_before) == 1
        assert r2.active_round(just_after) == 2


class TestComputeRoundStatus:
    def test_round1_closed_after_round1_window(self):
        from backend.services.portal.challenge_leaderboard import WINDOW_END

        assert r2.compute_round_status(WINDOW_END, 1) == "closed"

    def test_round2_live_inside_its_window(self):
        now = r2.ROUND2_START + timedelta(days=1)
        assert r2.compute_round_status(now, 2) == "live"

    def test_round2_closed_after_its_window(self):
        assert r2.compute_round_status(r2.ROUND2_END, 2) == "closed"


# ── roster fixtures ──────────────────────────────────────────────────────────


def _roster_row(email: str, display_name: str, department: str = "setup") -> dict:
    return {
        "email": email,
        "display_name": display_name,
        "department": department,
        "role": "member",
        "active": True,
        "avatar": None,
    }


ROSTER_ROWS = [
    _roster_row("surya@balizero.com", "Surya"),
    _roster_row("ari.firda@balizero.com", "Ari Firda"),
    _roster_row("krisna@balizero.com", "Krisna"),
    _roster_row("adit@balizero.com", "Adit"),
    _roster_row("asya@balizero.com", "Asya Nadia", department="accounting"),
]


def _r1_entry(email: str, activations: int) -> AwardedEntry:
    from backend.services.portal.challenge_leaderboard import member_key_from_email

    return AwardedEntry(
        email=email,
        member=member_key_from_email(email),
        display_name=email.split("@")[0],
        department=None,
        is_tax=False,
        rank=1,
        activations=activations,
        invited=activations,
        last_activation_at=None,
        award_tier=None,
        prize_idr=0,
        tax_bonus_idr=0,
        total_prize_idr=0,
        next_tier_threshold=None,
        to_next_tier=None,
    )


NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def _score(
    roster_rows=None,
    r1_awarded=None,
    registration_rows=None,
    first_document_rows=None,
    request_rows=None,
    review_rows=None,
    asya_request_rows=None,
    asya_client_event_rows=None,
    now=NOW,
):
    return r2.score_round2(
        roster_rows if roster_rows is not None else ROSTER_ROWS,
        r1_awarded if r1_awarded is not None else [],
        registration_rows if registration_rows is not None else [],
        first_document_rows if first_document_rows is not None else [],
        request_rows if request_rows is not None else [],
        review_rows if review_rows is not None else [],
        asya_request_rows if asya_request_rows is not None else [],
        asya_client_event_rows if asya_client_event_rows is not None else [],
        now,
    )


# ── carry rule ───────────────────────────────────────────────────────────────


class TestCarryRule:
    def test_september_prize_winners_start_at_zero(self):
        r1_awarded = [
            _r1_entry("surya@balizero.com", 25),
            _r1_entry("ari.firda@balizero.com", 22),
            _r1_entry("krisna@balizero.com", 18),
            _r1_entry("adit@balizero.com", 23),
        ]
        snapshot = _score(r1_awarded=r1_awarded)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["surya"].carry_points == 0
        assert by_member["surya"].september_choice == "prize"
        assert by_member["ari.firda"].carry_points == 0
        assert by_member["ari.firda"].september_choice == "prize"
        assert by_member["krisna"].carry_points == 0
        assert by_member["krisna"].september_choice == "prize"

    def test_non_winners_carry_their_september_activations(self):
        r1_awarded = [_r1_entry("adit@balizero.com", 23)]
        snapshot = _score(r1_awarded=r1_awarded)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].carry_points == 23
        assert by_member["adit"].points == 23
        assert by_member["adit"].september_choice == "carry"


# ── registrations ────────────────────────────────────────────────────────────


class TestRegistrations:
    def test_registration_adds_one_point_per_activation(self):
        registration_rows = [
            {
                "creator_email": "adit@balizero.com",
                "activations": 4,
                "invited": 5,
                "last_activation_at": NOW - timedelta(days=1),
            }
        ]
        snapshot = _score(registration_rows=registration_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].registrations == 4
        assert by_member["adit"].activations == 4
        assert by_member["adit"].points == 4


# ── first-document bonus ────────────────────────────────────────────────────


class TestFirstDocumentBonus:
    def test_credited_once_per_practice_to_the_practice_assignee(self):
        first_document_rows = [
            {
                "practice_id": 1,
                "client_id": 501,
                "first_doc_at": NOW - timedelta(days=1),
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            },
            {
                "practice_id": 2,
                "client_id": 502,
                "first_doc_at": NOW - timedelta(hours=2),
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            },
        ]
        snapshot = _score(first_document_rows=first_document_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].document_bonuses == 2
        assert by_member["adit"].points == 6

    def test_falls_back_to_client_assignee_when_practice_has_none(self):
        first_document_rows = [
            {
                "practice_id": 3,
                "client_id": 503,
                "first_doc_at": NOW,
                "practice_assignee": None,
                "client_assignee": "adit@balizero.com",
            }
        ]
        snapshot = _score(first_document_rows=first_document_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].document_bonuses == 1

    def test_unattributed_when_nobody_is_a_staff_assignee(self):
        first_document_rows = [
            {
                "practice_id": 4,
                "client_id": 504,
                "first_doc_at": NOW,
                "practice_assignee": None,
                "client_assignee": None,
            }
        ]
        snapshot = _score(first_document_rows=first_document_rows)
        assert sum(e.document_bonuses for e in snapshot.entries) == 0

    def test_the_sql_layer_is_responsible_for_excluding_predating_docs(self):
        """`build_first_documents_sql` only ever returns a row whose
        `first_doc_at` already fell inside the R2 window (see its WHERE
        clause) — a practice whose real first document predates the window
        never appears in `first_document_rows` at all, so the pure scorer
        has nothing extra to filter here. This test documents that contract:
        every row handed to the scorer counts, unconditionally."""
        first_document_rows = [
            {
                "practice_id": 5,
                "client_id": 505,
                "first_doc_at": r2.ROUND2_START,
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            }
        ]
        snapshot = _score(first_document_rows=first_document_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].document_bonuses == 1


# ── unanswered requests (-2) ─────────────────────────────────────────────────


class TestUnansweredRequestPenalty:
    def test_penalised_when_reply_takes_more_than_three_working_hours(self):
        created = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)  # Thursday 09:00 WITA
        reply = created + timedelta(hours=5)  # Thursday 14:00 WITA — 5 working hours, > 3
        request_rows = [
            {
                "client_id": 601,
                "practice_id": None,
                "created_at": created,
                "reply_at": reply,
                "client_assignee": "adit@balizero.com",
                "practice_assignee": None,
            }
        ]
        snapshot = _score(request_rows=request_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unanswered_requests == 1
        assert by_member["adit"].points == -2
        assert by_member["adit"].penalty_points == 2

    def test_never_penalised_when_replied_within_three_working_hours(self):
        created = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)  # Thursday 09:00 WITA
        reply = created + timedelta(hours=2)  # 2 working hours later
        request_rows = [
            {
                "client_id": 602,
                "practice_id": None,
                "created_at": created,
                "reply_at": reply,
                "client_assignee": "adit@balizero.com",
                "practice_assignee": None,
            }
        ]
        snapshot = _score(request_rows=request_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unanswered_requests == 0
        assert by_member["adit"].points == 0

    def test_still_open_request_measured_against_now(self):
        created = NOW - timedelta(hours=10)
        request_rows = [
            {
                "client_id": 603,
                "practice_id": None,
                "created_at": created,
                "reply_at": None,
                "client_assignee": "adit@balizero.com",
                "practice_assignee": None,
            }
        ]
        snapshot = _score(request_rows=request_rows, now=NOW)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unanswered_requests == 1


# ── unreviewed documents (-1) ────────────────────────────────────────────────


class TestUnreviewedDocumentPenalty:
    def test_penalised_when_review_takes_more_than_one_working_day(self):
        uploaded = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)  # Thursday 09:00 WITA
        reviewed = uploaded + timedelta(days=3)  # long past 9.5 working hours
        review_rows = [
            {
                "id": 701,
                "practice_id": 10,
                "client_id": 701,
                "uploaded_at": uploaded,
                "review_at": reviewed,
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            }
        ]
        snapshot = _score(review_rows=review_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unreviewed_documents == 1
        assert by_member["adit"].points == -1

    def test_never_penalised_when_reviewed_same_day(self):
        uploaded = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)  # Thursday 09:00 WITA
        reviewed = uploaded + timedelta(hours=4)
        review_rows = [
            {
                "id": 702,
                "practice_id": 11,
                "client_id": 702,
                "uploaded_at": uploaded,
                "review_at": reviewed,
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            }
        ]
        snapshot = _score(review_rows=review_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unreviewed_documents == 0

    def test_none_review_at_means_still_unreviewed_measured_against_now(self):
        uploaded = NOW - timedelta(days=5)
        review_rows = [
            {
                "id": 703,
                "practice_id": 12,
                "client_id": 703,
                "uploaded_at": uploaded,
                "review_at": None,
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            }
        ]
        snapshot = _score(review_rows=review_rows, now=NOW)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unreviewed_documents == 1


class TestSameIncidentDedupe:
    def test_drops_the_document_penalty_when_a_bigger_request_penalty_covers_it(self):
        uploaded = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)  # Thursday 09:00 WITA
        reviewed = uploaded + timedelta(days=3)
        # A client request created 1 hour after the doc upload — inside the
        # doc's [uploaded_at, uploaded_at + 1 working day] window.
        request_created = uploaded + timedelta(hours=1)
        request_reply = request_created + timedelta(hours=6)
        review_rows = [
            {
                "id": 801,
                "practice_id": 20,
                "client_id": 900,
                "uploaded_at": uploaded,
                "review_at": reviewed,
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            }
        ]
        request_rows = [
            {
                "client_id": 900,
                "practice_id": None,
                "created_at": request_created,
                "reply_at": request_reply,
                "client_assignee": "adit@balizero.com",
                "practice_assignee": None,
            }
        ]
        snapshot = _score(request_rows=request_rows, review_rows=review_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unanswered_requests == 1
        assert by_member["adit"].unreviewed_documents == 0
        assert by_member["adit"].points == -2

    def test_keeps_the_document_penalty_when_the_request_is_a_different_client(self):
        uploaded = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)
        reviewed = uploaded + timedelta(days=3)
        request_created = uploaded + timedelta(hours=1)
        request_reply = request_created + timedelta(hours=6)
        review_rows = [
            {
                "id": 802,
                "practice_id": 21,
                "client_id": 901,
                "uploaded_at": uploaded,
                "review_at": reviewed,
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            }
        ]
        request_rows = [
            {
                "client_id": 902,  # different client -> not the same incident
                "practice_id": None,
                "created_at": request_created,
                "reply_at": request_reply,
                "client_assignee": "adit@balizero.com",
                "practice_assignee": None,
            }
        ]
        snapshot = _score(request_rows=request_rows, review_rows=review_rows)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].unreviewed_documents == 1
        assert by_member["adit"].unanswered_requests == 1


# ── ranking, dense rank and rank prizes ──────────────────────────────────────


class TestRankingAndPrizes:
    def test_dense_rank_and_prizes_over_distinct_points(self):
        r1_awarded = [
            _r1_entry("adit@balizero.com", 23),
            _r1_entry("surya@balizero.com", 23),  # ties adit but is a Sept. winner -> carry 0
            _r1_entry("krisna@balizero.com", 5),
        ]
        snapshot = _score(r1_awarded=r1_awarded)
        by_member = {e.member: e for e in snapshot.entries}
        assert by_member["adit"].rank == 1
        assert by_member["adit"].prize_idr == r2.RANK_PRIZES_IDR[1]
        assert by_member["ari.firda"].points == 0
        assert by_member["krisna"].points == 0
        # ari.firda and krisna tie at 0 points -> share a rank and its prize
        assert by_member["ari.firda"].rank == by_member["krisna"].rank
        assert by_member["ari.firda"].prize_idr == by_member["krisna"].prize_idr

    def test_zero_prize_beyond_the_fifth_rank_row(self):
        roster_rows = [_roster_row(f"m{i}@balizero.com", f"M{i}") for i in range(7)]
        registration_rows = [
            {
                "creator_email": f"m{i}@balizero.com",
                "activations": 7 - i,
                "invited": 7 - i,
                "last_activation_at": NOW,
            }
            for i in range(7)
        ]
        snapshot = _score(roster_rows=roster_rows, registration_rows=registration_rows)
        by_rank = {e.rank: e for e in snapshot.entries}
        assert by_rank[6].prize_idr == 0
        assert by_rank[5].prize_idr == r2.RANK_PRIZES_IDR[5]

    def test_a_zero_point_tie_at_rank_five_earns_no_prize(self):
        """A rank prize requires points > 0 — landing on a prize-bearing
        rank by tying everyone else at zero is not "winning" it."""
        roster_rows = [_roster_row(f"m{i}@balizero.com", f"M{i}") for i in range(6)]
        # m0-m3 get distinct positive points (ranks 1-4); m4/m5 register
        # nothing and tie at 0 points, landing together on rank 5.
        registration_rows = [
            {
                "creator_email": f"m{i}@balizero.com",
                "activations": 4 - i,
                "invited": 4 - i,
                "last_activation_at": NOW,
            }
            for i in range(4)
        ]
        snapshot = _score(roster_rows=roster_rows, registration_rows=registration_rows)
        rank_five = [e for e in snapshot.entries if e.rank == 5]
        assert len(rank_five) == 2
        assert all(e.points == 0 for e in rank_five)
        assert all(e.prize_idr == 0 for e in rank_five)
        assert all(e.total_prize_idr == 0 for e in rank_five)

    def test_a_one_point_member_at_rank_five_still_earns_the_prize(self):
        roster_rows = [_roster_row(f"m{i}@balizero.com", f"M{i}") for i in range(5)]
        registration_rows = [
            {
                "creator_email": f"m{i}@balizero.com",
                "activations": 5 - i,
                "invited": 5 - i,
                "last_activation_at": NOW,
            }
            for i in range(5)
        ]
        snapshot = _score(roster_rows=roster_rows, registration_rows=registration_rows)
        by_rank = {e.rank: e for e in snapshot.entries}
        assert by_rank[5].points == 1
        assert by_rank[5].prize_idr == r2.RANK_PRIZES_IDR[5]
        assert by_rank[5].total_prize_idr == r2.RANK_PRIZES_IDR[5]


# ── Asya mission ─────────────────────────────────────────────────────────────


class TestAsyaMission:
    def test_asya_is_excluded_from_general_entries(self):
        snapshot = _score()
        assert "asya" not in {e.member for e in snapshot.entries}

    def test_asya_registrations_do_not_count_toward_her_mission(self):
        registration_rows = [
            {
                "creator_email": "asya@balizero.com",
                "activations": 10,
                "invited": 10,
                "last_activation_at": NOW,
            }
        ]
        snapshot = _score(registration_rows=registration_rows)
        assert snapshot.asya_mission.points == 0

    def test_mission_bonus_when_a_client_she_messaged_acts_within_thirty_days(self):
        asya_request_rows = [{"client_id": 950, "created_at": NOW - timedelta(days=10)}]
        asya_client_event_rows = [
            {"client_id": 950, "practice_id": None, "created_at": NOW - timedelta(days=1)}
        ]
        snapshot = _score(
            asya_request_rows=asya_request_rows, asya_client_event_rows=asya_client_event_rows
        )
        assert snapshot.asya_mission.mission_bonuses == 1
        assert snapshot.asya_mission.points == 3

    def test_no_bonus_when_her_message_is_more_than_thirty_days_before_the_event(self):
        asya_request_rows = [{"client_id": 951, "created_at": NOW - timedelta(days=45)}]
        asya_client_event_rows = [
            {"client_id": 951, "practice_id": None, "created_at": NOW - timedelta(days=1)}
        ]
        snapshot = _score(
            asya_request_rows=asya_request_rows, asya_client_event_rows=asya_client_event_rows
        )
        assert snapshot.asya_mission.mission_bonuses == 0

    def test_no_bonus_when_her_message_comes_after_the_event(self):
        asya_request_rows = [{"client_id": 952, "created_at": NOW}]
        asya_client_event_rows = [
            {"client_id": 952, "practice_id": None, "created_at": NOW - timedelta(days=1)}
        ]
        snapshot = _score(
            asya_request_rows=asya_request_rows, asya_client_event_rows=asya_client_event_rows
        )
        assert snapshot.asya_mission.mission_bonuses == 0

    def test_at_most_one_bonus_per_client_practice_key(self):
        asya_request_rows = [{"client_id": 953, "created_at": NOW - timedelta(days=5)}]
        asya_client_event_rows = [
            {"client_id": 953, "practice_id": None, "created_at": NOW - timedelta(days=2)},
            {"client_id": 953, "practice_id": None, "created_at": NOW - timedelta(days=1)},
        ]
        snapshot = _score(
            asya_request_rows=asya_request_rows, asya_client_event_rows=asya_client_event_rows
        )
        assert snapshot.asya_mission.mission_bonuses == 1

    def test_reached_flag_at_sixty_points(self):
        asya_request_rows = [
            {"client_id": 1000 + i, "created_at": NOW - timedelta(days=1)} for i in range(20)
        ]
        asya_client_event_rows = [
            {"client_id": 1000 + i, "practice_id": None, "created_at": NOW} for i in range(20)
        ]
        snapshot = _score(
            asya_request_rows=asya_request_rows, asya_client_event_rows=asya_client_event_rows
        )
        assert snapshot.asya_mission.mission_bonuses == 20
        assert snapshot.asya_mission.points == 60
        assert snapshot.asya_mission.reached is True

    def test_asyas_own_penalties_reduce_her_mission_not_the_general_pool(self):
        created = datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc)  # Thursday 09:00 WITA
        reply = created + timedelta(hours=5)  # Thursday 14:00 WITA — 5 working hours, > 3
        request_rows = [
            {
                "client_id": 960,
                "practice_id": None,
                "created_at": created,
                "reply_at": reply,
                "client_assignee": "asya@balizero.com",
                "practice_assignee": None,
            }
        ]
        snapshot = _score(request_rows=request_rows)
        assert snapshot.asya_mission.unanswered_requests == 1
        assert snapshot.asya_mission.penalty_points == 2
        assert snapshot.asya_mission.points == -2
        assert all(e.unanswered_requests == 0 for e in snapshot.entries)


# ── no client PII in the scorer's public shapes ─────────────────────────────


class TestNoClientIdentifiers:
    def test_round2_entry_has_no_client_bearing_field(self):
        names = {f.name for f in fields(r2.Round2Entry)}
        assert not any("client" in n for n in names)

    def test_scoring_event_has_no_client_bearing_field(self):
        names = {f.name for f in fields(r2.ScoringEvent)}
        assert not any("client" in n for n in names)

    def test_asya_mission_has_no_client_bearing_field(self):
        names = {f.name for f in fields(r2.AsyaMission)}
        assert not any("client" in n for n in names)

    def test_recent_events_carry_no_client_data(self):
        first_document_rows = [
            {
                "practice_id": 30,
                "client_id": 777,
                "first_doc_at": NOW,
                "practice_assignee": "adit@balizero.com",
                "client_assignee": None,
            }
        ]
        snapshot = _score(first_document_rows=first_document_rows)
        for event in snapshot.recent_events:
            assert "777" not in repr(event)
