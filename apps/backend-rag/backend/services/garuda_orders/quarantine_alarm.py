"""Decides WHEN a refused payment callback deserves a page — and when it does not.

A quarantined `garuda_payment_inbox` row is an authentic, signature-valid
provider callback we DELIBERATELY REFUSED TO ACT ON: it could not be tied to
exactly one order, or it claimed a PAID event for the wrong amount. The router
answers 204 either way, so the provider records a successful delivery and stops
retrying. Money moved and we did not move to match it. That is a page.

WHY A CLASS AND NOT AN `if` IN THE LOOP — the same reasoning as
`outbox_alarm.OutboxAlarm`, which this deliberately mirrors: an alarm that
fires on every evaluation of a standing condition is how a real signal gets
muted, which is the disease this module exists to cure, one level up. So the
decision has state, it is kept OUT of the scheduler where it would need a
database and an event loop to test, and everything here is a pure function of
(snapshot, clock) with the caller owning the sending.

SIBLING, NOT SUBCLASS, AND NOT A REFACTOR OF `OutboxAlarm`. The discipline is
identical and is reused deliberately — including the `decide`/`confirm_sent`
split, which is the load-bearing half — but the condition, the vocabulary and
every line of the message differ. Extracting a shared base would mean editing
the outbox's live money-page in a PR about the inbox, which is a second
concern and a real risk for no gain at this size. `REALERT_SECONDS` IS
imported rather than re-declared, so the two cadences cannot silently drift
apart; splitting them later is a deliberate act, not an accident.

TIME IS AN ARGUMENT, NEVER READ HERE. `now` is a monotonic seconds float. A
module that calls `time.monotonic()` internally can only be tested by
sleeping, and a test that sleeps gets shortened until it proves nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.services.garuda_orders.outbox_alarm import (
    REALERT_SECONDS,
    _code_span,
    _escape_markdown,
)
from backend.services.garuda_orders.payment_inbox_watch import QuarantineSnapshot

#: Rows named individually in the page. The snapshot's sample is already
#: bounded; this is the second bound, so a burst cannot produce a Telegram
#: message too long to send.
_MAX_LISTED = 5

#: THE TRANSPORT PARSES THIS TEXT AS MARKDOWN, AND EVERY REASON WE EMIT WOULD
#: HAVE BROKEN IT (cross-family seat, codex-gpt-5.6-sol, 2026-08-29).
#: `send_telegram_message` hardcodes `parse_mode="Markdown"`, whose V1 grammar
#: reserves ``_ * ` [``. All four `quarantine_reason` values contain an
#: underscore, and `order_id` is `^[A-Za-z0-9_-]{16,128}$` so it usually does
#: too. An unmatched underscore makes Telegram answer 400 "can't parse
#: entities" — and that function treats 4xx as NON-retryable, so the page is
#: dropped, permanently, for a formatting reason having nothing to do with
#: whether Telegram is reachable. An alarm whose every message fails to parse
#: is the exact disease this module exists to cure, one layer further out.
#:
#: `_escape_markdown` / `_code_span` were DEFINED here until 2026-08-29 and now
#: come from `outbox_alarm`, unchanged. The move is the point: the sibling
#: alarm shipped with this same defect UNCURED while a working escaper sat two
#: modules away, so the copies are collapsed into the one module both alarms
#: already depend on — the same reasoning that made `REALERT_SECONDS` shared
#: rather than re-declared, "so the two cadences cannot silently drift".


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


@dataclass
class QuarantineAlarm:
    """Turns repeated observations into at most one page per hour per condition.

    `decide` returns the text to send, or None. It NEVER sends, NEVER logs and
    NEVER raises on ordinary input — the caller is inside a drain loop that must
    not die because an alarm had an opinion.
    """

    #: Signature of the last condition SUCCESSFULLY DELIVERED, or None when the
    #: last delivered message was a quiet notice.
    _last_signature: tuple[int, frozenset[str]] | None = None
    _last_sent_at: float = field(default=0.0)
    #: What `decide` last returned and is waiting on `confirm_sent` for. Held
    #: separately BECAUSE A PAGE THAT WAS NEVER DELIVERED MUST NOT COUNT AS
    #: REPORTED — see `confirm_sent`.
    _pending: tuple[tuple[int, frozenset[str]] | None, float] | None = None

    def decide(self, snapshot: QuarantineSnapshot, *, now: float) -> str | None:
        """The page to send, or None.

        Fires while the window holds any refused callback. Re-fires only when
        the CONDITION CHANGED (a different count, or a different set of
        reasons) or when `REALERT_SECONDS` has passed.
        """

        recent = max(0, int(snapshot.recent))
        reasons = frozenset(snapshot.reasons or ())

        if recent == 0:
            if self._last_signature is None:
                return None
            self._pending = (None, now)
            return self._compose_quiet(snapshot.lifetime)

        signature = (recent, reasons)
        changed = signature != self._last_signature
        stale = (now - self._last_sent_at) >= REALERT_SECONDS
        if not changed and not stale:
            return None

        self._pending = (signature, now)
        # The NORMALISED values are passed on, never re-read from `snapshot`
        # inside `_compose`: a `None` reason set or a negative count that
        # `decide` already tolerated would otherwise raise one frame lower,
        # inside a drain loop, which is exactly what this class promises never
        # to do (`test_none_for_reasons_is_treated_as_empty` found this).
        return self._compose(snapshot, recent=recent, reasons=reasons, repeat=not changed)

    def confirm_sent(self, now: float) -> None:
        """Commit the last `decide` result — call ONLY after the page landed.

        Committing at decision time instead would let a page the transport
        FAILED to deliver consume the hour-long suppression window: the alarm
        goes quiet for an hour precisely because it just failed to reach
        anyone. With the commit split out, an undelivered page leaves the state
        untouched and `decide` re-fires on the next check instead.
        """

        if self._pending is None:
            return
        signature, _decided_at = self._pending
        self._last_signature = signature
        # `now`, not the decision time: the suppression window starts when the
        # human could actually have seen it.
        self._last_sent_at = now
        self._pending = None

    @staticmethod
    def _compose_quiet(lifetime: int) -> str:
        # NOT the word "recovered". Nothing here clears itself — a row leaves
        # the window by ageing out, not by being handled, and there is no
        # acknowledgement column that could tell the difference. Saying
        # "recovered" would be false in the common case.
        return (
            "GARUDA payment quarantine: nothing new in the window. "
            f"{_plural(lifetime, 'refused callback')} still on record — "
            "these do not clear themselves."
        )

    @staticmethod
    def _compose(
        snapshot: QuarantineSnapshot,
        *,
        recent: int,
        reasons: frozenset[str],
        repeat: bool,
    ) -> str:
        head = (
            "GARUDA payment quarantine STILL needs a human."
            if repeat
            else "GARUDA payment quarantine needs a human."
        )
        lines = [
            head,
            f"{_plural(recent, 'authentic provider callback')} refused and "
            "NOT acted on: signature valid, but unreconcilable to exactly one order "
            "or claiming the wrong amount. The provider got a 204 and will not retry.",
        ]
        if reasons:
            # Sorted so the same condition always renders identically — an alarm
            # whose text wobbles between identical states defeats every
            # downstream dedup, including a human's.
            lines.append(
                "Reason(s): " + ", ".join(_escape_markdown(r) for r in sorted(reasons))
            )
        listed = snapshot.sample[:_MAX_LISTED]
        for event in listed:
            # NO SQUARE BRACKETS around the order any more: `[` is reserved by
            # Markdown V1 too, so the old `[{order}]` form broke the parse on
            # every single page even after the ids themselves were made safe.
            # NOT "no matching order": NULL here does not mean the callback was
            # unmatchable. `garuda_payment_inbox.order_id` is never written —
            # not by the INSERT, not by `_quarantine` — so it is NULL even for
            # amount_mismatch and unexpected_state, where the repository HAD
            # already found the order (codex-gpt-5.6-sol, cross-family council).
            # Saying "no matching order" would state something false in an
            # alert, which is the defect this PR was opened to cure. Until the
            # writer records it (ledgered, REQUIRED), the page says only what
            # is true: this row does not carry one.
            order = (
                _code_span(event.order_id)
                if event.order_id
                else "no order id on the inbox row"
            )
            lines.append(
                f"  {_code_span(event.provider_event_id)} order {order} "
                f"— {_escape_markdown(event.reason)}"
            )
        if recent > len(listed):
            lines.append(f"  ... and {recent - len(listed)} more")
        if snapshot.lifetime > recent:
            lines.append(f"{snapshot.lifetime} refused in total, all time.")
        return "\n".join(lines)


__all__ = ["REALERT_SECONDS", "QuarantineAlarm"]
