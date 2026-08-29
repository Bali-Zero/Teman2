"""Guilt AND innocence for `QuarantineAlarm`.

Guilt is the reason the module exists: a refused payment callback MUST reach a
human. Innocence is what keeps it alive: an alarm that fires on every
evaluation of a standing condition is how a real signal gets muted, which is
the same disease it exists to cure. Both halves are tested, and every assertion
here is one that would go RED if the guarantee it names were removed.
"""

from __future__ import annotations

import pytest

from backend.services.garuda_orders.payment_inbox_watch import (
    QuarantinedEvent,
    QuarantineSnapshot,
)
from backend.services.garuda_orders.quarantine_alarm import REALERT_SECONDS, QuarantineAlarm


def _snapshot(
    *,
    recent: int = 0,
    lifetime: int | None = None,
    reasons: frozenset[str] = frozenset(),
    sample: tuple[QuarantinedEvent, ...] = (),
) -> QuarantineSnapshot:
    return QuarantineSnapshot(
        recent=recent,
        lifetime=recent if lifetime is None else lifetime,
        reasons=reasons,
        sample=sample,
    )


def _one(reason: str = "amount_mismatch") -> QuarantineSnapshot:
    return _snapshot(
        recent=1,
        reasons=frozenset({reason}),
        sample=(
            QuarantinedEvent(
                provider_event_id="evt_test_0001", order_id="ord_test_0001", reason=reason
            ),
        ),
    )


# --------------------------------------------------------------------------
# GUILT — the thing must page
# --------------------------------------------------------------------------


def test_a_refused_callback_pages():
    """RED IF: the alarm ever decides a quarantined row is not worth a page.

    This is the whole mandate. Five writers, zero readers was the measured
    state; if this returns None the cure is undone.
    """

    assert QuarantineAlarm().decide(_one(), now=0.0) is not None


def test_the_page_says_the_callback_was_AUTHENTIC_and_we_refused_it():
    """RED IF: the text degrades into "an error occurred".

    The single most important thing a reader must understand at 3am is that
    this was not a failed request — it was a valid one we declined, so the
    provider believes it delivered and will not retry.
    """

    msg = QuarantineAlarm().decide(_one(), now=0.0)
    assert msg is not None
    assert "authentic" in msg
    assert "will not retry" in msg
    assert "needs a human" in msg


def test_the_page_carries_the_ids_and_the_cause_needed_to_act():
    """RED IF: the message stops naming the event id, the order or the reason —
    i.e. becomes a count with no way to act on it, which is the half-cure this
    subsystem keeps producing."""

    msg = QuarantineAlarm().decide(_one("amount_mismatch"), now=0.0)
    assert msg is not None
    assert "evt_test_0001" in msg
    assert "ord_test_0001" in msg
    assert "amount_mismatch" in msg


def test_an_unmatched_event_says_so_rather_than_printing_none():
    """RED IF: a row with no order renders the literal `None`."""

    snapshot = _snapshot(
        recent=1,
        reasons=frozenset({"unmatched_session"}),
        sample=(
            QuarantinedEvent(
                provider_event_id="evt_x", order_id=None, reason="unmatched_session"
            ),
        ),
    )
    msg = QuarantineAlarm().decide(snapshot, now=0.0)
    assert msg is not None
    assert "no matching order" in msg
    assert "None" not in msg


def test_the_lifetime_total_travels_when_it_exceeds_the_window():
    """RED IF: history disappears, letting "1 in the window" read as "1 ever"."""

    msg = QuarantineAlarm().decide(_snapshot(recent=1, lifetime=9), now=0.0)
    assert msg is not None
    assert "9 refused in total" in msg


def test_a_burst_is_bounded_and_admits_what_it_omitted():
    """RED IF: a burst either floods Telegram or silently truncates."""

    sample = tuple(
        QuarantinedEvent(provider_event_id=f"evt_{i}", order_id=None, reason="unmatched_session")
        for i in range(5)
    )
    msg = QuarantineAlarm().decide(
        _snapshot(recent=40, reasons=frozenset({"unmatched_session"}), sample=sample), now=0.0
    )
    assert msg is not None
    assert "and 35 more" in msg


# --------------------------------------------------------------------------
# INNOCENCE — the thing must shut up
# --------------------------------------------------------------------------


def test_clean_stays_silent():
    """RED IF: the alarm pages when there is nothing to page about."""

    alarm = QuarantineAlarm()
    assert alarm.decide(_snapshot(), now=0.0) is None
    assert alarm.decide(_snapshot(), now=99999.0) is None


def test_a_clean_window_with_history_still_stays_silent_if_it_never_paged():
    """RED IF: a startup with old rows in the table pages about them forever.

    `lifetime` is deliberately NOT a condition — only the window is.
    """

    assert QuarantineAlarm().decide(_snapshot(recent=0, lifetime=12), now=0.0) is None


def test_the_same_condition_does_not_page_again_within_the_hour():
    """RED IF: the suppression window stops working — this is the failure that
    makes a human mute the channel, after which the alarm is decoration."""

    alarm = QuarantineAlarm()
    assert alarm.decide(_one(), now=0.0) is not None
    alarm.confirm_sent(0.0)
    for t in (1.0, 60.0, REALERT_SECONDS - 1):
        assert alarm.decide(_one(), now=t) is None, (
            f"re-paged at t={t} for an unchanged condition — this is how a real "
            f"signal gets muted"
        )


def test_a_standing_condition_is_re_reported_after_the_window():
    """RED IF: one page that scrolls away becomes the only page. The row stays
    refused until a human acts on it."""

    alarm = QuarantineAlarm()
    alarm.decide(_one(), now=0.0)
    alarm.confirm_sent(0.0)
    again = alarm.decide(_one(), now=REALERT_SECONDS)
    assert again is not None
    assert "STILL" in again


def test_a_changed_count_pages_immediately_even_inside_the_window():
    """RED IF: a SECOND refused payment during the suppression hour is swallowed
    because the first one is still standing."""

    alarm = QuarantineAlarm()
    alarm.decide(_one(), now=0.0)
    alarm.confirm_sent(0.0)
    assert alarm.decide(_snapshot(recent=2, reasons=frozenset({"amount_mismatch"})), now=1.0)


def test_a_new_reason_pages_immediately_even_at_the_same_count():
    """RED IF: the signature keys on the count alone. One `unmatched_session`
    replaced by one `amount_mismatch` is a different incident."""

    alarm = QuarantineAlarm()
    alarm.decide(_one("unmatched_session"), now=0.0)
    alarm.confirm_sent(0.0)
    assert alarm.decide(_one("amount_mismatch"), now=1.0) is not None


def test_a_page_that_was_never_delivered_does_not_silence_the_next_hour():
    """RED IF: the state is committed inside `decide` again.

    Committing at decision time means a page the transport FAILED to deliver
    still burns the hour — the alarm goes quiet precisely because it just
    failed to reach anyone.
    """

    alarm = QuarantineAlarm()
    assert alarm.decide(_one(), now=0.0) is not None
    # No confirm_sent: delivery failed.
    assert alarm.decide(_one(), now=1.0) is not None, (
        "an undelivered page consumed the suppression window"
    )


# --------------------------------------------------------------------------
# HONESTY of the quiet notice
# --------------------------------------------------------------------------


def test_the_quiet_notice_never_claims_recovery():
    """RED IF: the word "recovered" comes back.

    Nothing here recovers on its own. A row leaves the window by ageing out,
    not by being handled, and there is no acknowledgement column that could
    tell the difference — so "recovered" would be false in the common case.
    """

    alarm = QuarantineAlarm()
    alarm.decide(_one(), now=0.0)
    alarm.confirm_sent(0.0)
    quiet = alarm.decide(_snapshot(recent=0, lifetime=1), now=10.0)
    assert quiet is not None
    assert "recovered" not in quiet.lower()
    assert "do not clear themselves" in quiet
    assert "1 refused callback" in quiet


def test_the_quiet_notice_is_announced_exactly_once():
    """RED IF: the quiet notice itself becomes a standing page."""

    alarm = QuarantineAlarm()
    alarm.decide(_one(), now=0.0)
    alarm.confirm_sent(0.0)
    assert alarm.decide(_snapshot(recent=0, lifetime=1), now=10.0) is not None
    alarm.confirm_sent(10.0)
    assert alarm.decide(_snapshot(recent=0, lifetime=1), now=20.0) is None


# --------------------------------------------------------------------------
# determinism + robustness inside a drain loop
# --------------------------------------------------------------------------


def test_reasons_render_sorted():
    """RED IF: set iteration order reaches the text. Wobbling text defeats every
    downstream dedup, including a human's."""

    msg = QuarantineAlarm().decide(
        _snapshot(recent=2, reasons=frozenset({"unmatched_session", "amount_mismatch"})),
        now=0.0,
    )
    assert msg is not None
    assert "amount_mismatch, unmatched_session" in msg


def test_set_order_never_changes_the_message():
    a, b = QuarantineAlarm(), QuarantineAlarm()
    m1 = a.decide(_snapshot(recent=2, reasons=frozenset({"x", "y"})), now=0.0)
    m2 = b.decide(_snapshot(recent=2, reasons=frozenset({"y", "x"})), now=0.0)
    assert m1 == m2


@pytest.mark.parametrize("bad", [-5, 0])
def test_a_non_positive_count_is_not_a_condition(bad):
    assert QuarantineAlarm().decide(_snapshot(recent=bad), now=0.0) is None


def test_none_for_reasons_is_treated_as_empty():
    """RED IF: the alarm raises inside the drain loop on a degenerate snapshot."""

    snapshot = QuarantineSnapshot(recent=1, lifetime=1, reasons=None, sample=())  # type: ignore[arg-type]
    assert QuarantineAlarm().decide(snapshot, now=0.0) is not None


# --------------------------------------------------------------------------
# PII
# --------------------------------------------------------------------------


def test_the_quarantine_page_carries_no_pii():
    """The claim `_send_quarantine_alarm`'s docstring makes, pinned.

    The alarm is only ever handed counts, the closed reason vocabulary, and
    provider/order ids. So the property to check is that NOTHING ELSE can reach
    the text: feed it applicant-shaped poison through the only string-carrying
    fields it has and confirm the message contains what it was given and
    nothing more — i.e. it never enriches and has no path to an order row.
    """

    poisoned_event = "evt_traveller@example.invalid"
    poisoned_order = "ord_+6281234567890"
    snapshot = _snapshot(
        recent=1,
        reasons=frozenset({"amount_mismatch"}),
        sample=(
            QuarantinedEvent(
                provider_event_id=poisoned_event,
                order_id=poisoned_order,
                reason="amount_mismatch",
            ),
        ),
    )
    msg = QuarantineAlarm().decide(snapshot, now=0.0)
    assert msg is not None
    assert poisoned_event in msg and poisoned_order in msg
    residue = msg.replace(poisoned_event, "").replace(poisoned_order, "")
    for applicant_shaped in ("@", "+62", "passport", "email", "phone"):
        assert applicant_shaped not in residue.lower(), (
            f"the page contains {applicant_shaped!r} from somewhere other than its "
            f"arguments — it has grown a lookup it must not have"
        )
