"""Guilt AND innocence for `OutboxAlarm`.

The innocence half is the point of the module: an alarm that fires on every
evaluation for a standing condition is how a real signal gets muted, which is
the same disease it exists to cure. So "does not fire again" is tested at least
as hard as "fires".
"""

from __future__ import annotations

import pytest

from backend.services.garuda_orders.outbox_alarm import REALERT_SECONDS, OutboxAlarm


def test_clean_stays_silent():
    alarm = OutboxAlarm()
    assert alarm.decide(exhausted=0, unroutable_types=frozenset(), now=0.0) is None
    assert alarm.decide(exhausted=0, unroutable_types=frozenset(), now=99999.0) is None


def test_an_exhausted_job_pages_once_and_says_nothing_else_will_notice():
    alarm = OutboxAlarm()
    msg = alarm.decide(exhausted=1, unroutable_types=frozenset(), now=0.0)
    assert msg is not None
    assert "1 job exhausted" in msg
    assert "never be claimed again" in msg


def test_the_same_condition_does_not_page_again_within_the_hour():
    alarm = OutboxAlarm()
    assert alarm.decide(exhausted=2, unroutable_types=frozenset(), now=0.0) is not None
    for t in (1.0, 60.0, REALERT_SECONDS - 1):
        assert alarm.decide(exhausted=2, unroutable_types=frozenset(), now=t) is None, (
            f"re-paged at t={t} for an unchanged condition — this is how a real "
            f"signal gets muted"
        )


def test_a_standing_condition_is_re_reported_after_the_window():
    alarm = OutboxAlarm()
    alarm.decide(exhausted=2, unroutable_types=frozenset(), now=0.0)
    again = alarm.decide(exhausted=2, unroutable_types=frozenset(), now=REALERT_SECONDS)
    assert again is not None, "a broken row stays broken; one page that scrolls away is none"
    assert "STILL" in again


def test_a_changed_condition_pages_immediately_even_inside_the_window():
    alarm = OutboxAlarm()
    alarm.decide(exhausted=2, unroutable_types=frozenset(), now=0.0)
    assert alarm.decide(exhausted=3, unroutable_types=frozenset(), now=1.0) is not None
    assert (
        alarm.decide(exhausted=3, unroutable_types=frozenset({"x"}), now=2.0) is not None
    )


def test_recovery_is_announced_exactly_once():
    alarm = OutboxAlarm()
    alarm.decide(exhausted=1, unroutable_types=frozenset(), now=0.0)
    recovered = alarm.decide(exhausted=0, unroutable_types=frozenset(), now=10.0)
    assert recovered is not None and "recovered" in recovered, (
        "without a recovery line a reader cannot tell 'resolved' from 'the alarm died'"
    )
    assert alarm.decide(exhausted=0, unroutable_types=frozenset(), now=20.0) is None


def test_unrouted_types_are_named_and_rendered_stably():
    alarm = OutboxAlarm()
    msg = alarm.decide(
        exhausted=0, unroutable_types=frozenset({"b_type", "a_type"}), now=0.0
    )
    assert msg is not None
    assert "a_type, b_type" in msg, "unsorted output defeats every downstream dedup"


def test_set_order_never_changes_the_message():
    """Two frozensets with the same members must produce identical text."""

    a, b = OutboxAlarm(), OutboxAlarm()
    m1 = a.decide(exhausted=0, unroutable_types=frozenset({"x", "y"}), now=0.0)
    m2 = b.decide(exhausted=0, unroutable_types=frozenset({"y", "x"}), now=0.0)
    assert m1 == m2


@pytest.mark.parametrize("bad", [-5, 0])
def test_a_non_positive_exhausted_count_is_not_a_condition(bad):
    alarm = OutboxAlarm()
    assert alarm.decide(exhausted=bad, unroutable_types=frozenset(), now=0.0) is None


def test_none_for_unroutable_types_is_treated_as_empty():
    """The caller passes `stats.unroutable_types`; a future refactor that lets it
    be None must not make the alarm raise inside a drain loop."""

    alarm = OutboxAlarm()
    assert alarm.decide(exhausted=0, unroutable_types=None, now=0.0) is None  # type: ignore[arg-type]


def test_the_page_names_only_counts_and_job_types():
    """`_send_outbox_alarm`'s docstring claims the page carries no applicant
    data. This is the test that claim points at — a docstring asserting a
    property nothing checks is the exact defect this lane has been correcting
    all day.

    The alarm is only ever handed two things: an integer and a set of
    `job_type` strings. So the property to pin is that NOTHING ELSE can reach
    the text: feed it a job type carrying applicant-shaped data and confirm the
    message contains that string and nothing more — i.e. the alarm never
    enriches, never looks anything up, and has no path to an order row.
    """

    alarm = OutboxAlarm()
    poisoned = "job_type_with_traveller@example.invalid_inside"
    msg = alarm.decide(exhausted=3, unroutable_types=frozenset({poisoned}), now=0.0)
    assert msg is not None
    # The one string it was given comes back; that is the whole surface.
    assert poisoned in msg
    # And the rest of the message is built from the count and fixed prose only.
    without_given = msg.replace(poisoned, "")
    for applicant_shaped in ("@", "+62", "passport", "order_id", "ord_"):
        assert applicant_shaped not in without_given, (
            f"the alarm text contains {applicant_shaped!r} from somewhere other than "
            f"its arguments — it has grown a lookup it must not have"
        )
