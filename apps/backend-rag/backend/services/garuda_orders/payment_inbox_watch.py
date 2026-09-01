"""THE READER `garuda_payment_inbox` never had.

WHAT A QUARANTINED ROW IS. An authentic, signature-valid provider callback
that we DELIBERATELY REFUSED TO ACT ON — it could not be tied to exactly one
order, or it claimed a PAID event for the wrong amount. The provider moved
money and we declined to move our state to match. That is a page, not a
metric.

THE GAP THIS CLOSES. Measured 2026-08-29 on `origin/main` @ 22dabc1166:
`quarantined` was SET at five sites in `repository.py` and read at NONE.
`git grep -n "FROM garuda_payment_inbox"` returned exactly one line in the
whole tree and it was a test. Five writers, one reader, and the reader was a
test. Superscar #2 — built is not armed — and the THIRD instance of it in
this one subsystem: the 2026-08-28 cure armed `count_undrained` and
`reconcile_expired_checkouts` in the same tick and left this one behind. The
generalisation, which is the reusable part: curing one instance of "nobody
reads this" does not cure its siblings. When you find a write-only state,
enumerate every other state the same subsystem persists and check each one
in the same turn.

WHY THE COUNT IS WINDOWED. Without a window the population only ever grows,
so the alarm would page hourly forever after the first quarantine until a
human deleted rows — which no tooling lets them do. An alarm that cannot
stop is an alarm that gets muted, which is this module's own disease one
level up. So the PAGE is driven by a rolling window while the LIFETIME total
travels with it, and the quiet notice says "none in the window, N still on
record" rather than the word "recovered" — nothing here recovers on its own,
and a message claiming otherwise would be false.

THE HONEST LIMITATION, stated because a reader will otherwise assume
otherwise: there is no acknowledgement column, so this cannot distinguish
"a human has dealt with it" from "it scrolled out of the window". The window
is a proxy for un-acknowledged, not a synonym. Measured consequence, not an
estimate: a quarantine that lands and is never handled produces 26 hourly
pages and then PERMANENT SILENCE, while the row stays unhandled forever.

Ledgered in `.claude/skills/modus/PENDING-ARMS.md` — search that file for
`REQUIRED FOLLOW-UP: the lifetime digest`. That sentence used to read
"Ledgered in PENDING-ARMS" with no row behind it, which is worse than saying
nothing: a false claim of ledgering, in a module whose entire subject is
state nobody reads, is the disease signing its own alibi. The row exists now;
if you cannot find it, the claim has rotted again and the row is what must be
restored, not this sentence deleted.

NO PII. The projection is `provider_event_id`, `order_id`, the closed
`quarantine_reason` vocabulary and a count — never an applicant name, email,
phone or passport. Those columns are not in this table at all
(`garuda_orders` holds them), and this module never joins to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import asyncpg

#: The page's rolling window. 24 hours: long enough that a quarantine landing
#: overnight is still reported when someone reads Telegram in the morning,
#: short enough that a standing condition cannot page forever.
DEFAULT_WINDOW = timedelta(hours=24)

#: How many rows travel in the page. Enough to act on, few enough that a
#: burst does not produce a message nobody reads.
DEFAULT_SAMPLE_LIMIT = 5

#: Rendered in place of a NULL `quarantine_reason` — rows quarantined before
#: migration 298. Deliberately NOT one of the four real reasons: inventing a
#: cause for a row that never recorded one would be a fabrication.
UNRECORDED = "unrecorded"


@dataclass(frozen=True, slots=True)
class QuarantinedEvent:
    """One refused callback, in the shape the page needs to be actionable."""

    provider_event_id: str
    order_id: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class QuarantineSnapshot:
    #: Quarantined inside the window — what the alarm fires on.
    recent: int
    #: Quarantined ever. Travels with every message so that "none in the
    #: window" can never be mistaken for "none at all".
    lifetime: int
    #: Reasons present in the window, for the alarm's change-detection
    #: signature and for the message body.
    reasons: frozenset[str]
    #: Up to `sample_limit` of the most recent, newest first.
    sample: tuple[QuarantinedEvent, ...]

    @property
    def clean(self) -> bool:
        return self.recent == 0


async def count_quarantined(
    conn: asyncpg.Connection,
    *,
    window: timedelta = DEFAULT_WINDOW,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
    now: datetime | None = None,
) -> QuarantineSnapshot:
    """Read-only. Mutates nothing, and must stay that way.

    `now` is an argument so the window is testable without sleeping — a test
    that sleeps gets shortened until it proves nothing (`outbox_alarm.py`'s
    own rule, and it applies to the query side too).
    """

    if sample_limit < 1:
        raise ValueError("sample_limit must be >= 1")
    if window <= timedelta(0):
        raise ValueError("window must be positive")

    cutoff = (now or datetime.now(UTC)) - window

    totals = await conn.fetchrow(
        """
        SELECT
            count(*) FILTER (WHERE processed_at >= $1) AS recent,
            count(*) AS lifetime
          FROM garuda_payment_inbox
         WHERE outcome = 'quarantined'
        """,
        cutoff,
    )

    rows = await conn.fetch(
        """
        SELECT provider_event_id, order_id, quarantine_reason
          FROM garuda_payment_inbox
         WHERE outcome = 'quarantined'
           AND processed_at >= $1
         ORDER BY processed_at DESC
         LIMIT $2
        """,
        cutoff,
        sample_limit,
    )

    # The reason set is read from the WINDOW, not from the sample: a burst of
    # twenty `unmatched_session` rows plus one `amount_mismatch` must not lose
    # the mismatch just because it fell past `sample_limit`. That is the same
    # "reading only the latest pass loses a type" trap the outbox scheduler
    # documents for `unroutable_types`.
    reason_rows = await conn.fetch(
        """
        SELECT DISTINCT coalesce(quarantine_reason, $2) AS reason
          FROM garuda_payment_inbox
         WHERE outcome = 'quarantined'
           AND processed_at >= $1
        """,
        cutoff,
        UNRECORDED,
    )

    return QuarantineSnapshot(
        recent=int(totals["recent"]) if totals else 0,
        lifetime=int(totals["lifetime"]) if totals else 0,
        reasons=frozenset(r["reason"] for r in reason_rows),
        sample=tuple(
            QuarantinedEvent(
                provider_event_id=r["provider_event_id"],
                order_id=r["order_id"],
                reason=r["quarantine_reason"] or UNRECORDED,
            )
            for r in rows
        ),
    )


__all__ = [
    "DEFAULT_SAMPLE_LIMIT",
    "DEFAULT_WINDOW",
    "UNRECORDED",
    "QuarantineSnapshot",
    "QuarantinedEvent",
    "count_quarantined",
]
