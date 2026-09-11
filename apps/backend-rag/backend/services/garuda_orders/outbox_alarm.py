"""Decides WHEN the outbox's failure states deserve a page — and when they do not.

THE GAP THIS CLOSES. `outbox_consumer.count_undrained` was written as "the
numbers a probe needs to go red", and `drain_once` reports `unroutable` per
pass. Measured 2026-08-28 on `origin/main`: `count_undrained` had **zero
non-test callers** — its only two non-test mentions in the whole tree were
COMMENTS promising a failure would "be visible in `count_undrained`". A comment
is not a caller. Superscar #2, one stage earlier than W120: there the sentinel
read a key the reporter never emitted; here the reporter was never asked.

WHY THAT MATTERED MORE THAN IT LOOKS. `DEFAULT_MAX_ATTEMPTS` is 5 and the
scheduler sleeps `0.1 if stats.dispatched else interval`. `exclude_ids` prevents
re-claiming a row inside ONE pass, not across passes — so while any other job in
the queue dispatches, a failing row is re-claimed every 100ms and burns all five
attempts in about half a second. A brief provider outage (a Telegram 5xx, an
expired token, a DNS blip) is therefore enough to exhaust a money-anomaly page
permanently, and nothing anywhere said so.

WHY THIS IS A CLASS AND NOT AN `if` IN THE LOOP. An alarm that fires on every
evaluation for a standing condition is how a real signal gets muted — the same
failure this module exists to prevent, one level up. So the decision has state
(what was last reported, and when), and it is kept OUT of the scheduler where it
would be untestable without a database, an event loop and a Telegram double.
Everything here is a pure function of (counts, clock); the caller owns the
sending.

TIME IS AN ARGUMENT, NEVER READ HERE. Every method takes `now` (a monotonic
seconds float). A module that calls `time.monotonic()` internally can only be
tested by sleeping, and a test that sleeps gets shortened until it proves
nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: A standing condition is re-reported at most this often. An hour is chosen
#: over "once, ever" deliberately: the row stays broken until a human acts, and
#: a single page that scrolls away is indistinguishable from no page at all.
REALERT_SECONDS = 3600.0

#: Telegram Markdown V1 (`parse_mode='Markdown'`, set by
#: `telegram_notifier.send_telegram_message`) reserves `_ * ` [`. An UNMATCHED
#: reserve character makes Telegram answer 400 "can't parse entities", and 4xx
#: is NON-retryable there — so a page the parser rejects is dropped for good.
#:
#: WHY THAT WAS A LIVE DEFECT AND NOT A TYPOGRAPHY NICETY. Until 2026-08-29
#: `_compose` interpolated job-type names raw, and the two real ones —
#: `practice_release` and `portal_invite` — carry exactly ONE underscore each.
#: So delivery depended on UNDERSCORE PARITY: one failing job type is an
#: unmatched `_` and the page dies; two of them pair up, parse, and arrive.
#: That is worse than always-broken. An alarm that never arrives gets noticed
#: eventually; an alarm that arrives most of the time teaches everyone the
#: channel works, and the silence on the odd-parity cases then reads as
#: "nothing went wrong".
#:
#: WHY THESE LIVE HERE. Same char set as `telegram_notifier._MARKDOWN_ESCAPE_RE`
#: and `outbox_handlers._MARKDOWN_ESCAPE_RE`, and NOT imported from either: both
#: of those modules pull in asyncpg, httpx and the portal/CRM services, and this
#: module is deliberately dependency-free so the decision stays testable without
#: a database, an event loop or a Telegram double (see the module docstring).
#: This is the package's alarm root — `quarantine_alarm` already imports
#: `REALERT_SECONDS` from here "so the two cadences cannot silently drift", and
#: the escaper is now shared the same way, for the same reason.
_MARKDOWN_ESCAPE_RE = re.compile(r"([_*`\[])")


def _escape_markdown(text: str) -> str:
    return _MARKDOWN_ESCAPE_RE.sub(r"\\\1", text)


def _code_span(value: str) -> str:
    """Wrap an identifier so Markdown V1 does not re-parse inside it.

    A BACKTICK IN THE VALUE WOULD END THE SPAN EARLY — the trap
    `outbox_handlers` records from Kimi K3 on 2026-08-28. Telegram would
    re-parse the tail and answer 400, and the page would never go out, so the
    malformed identifier is precisely what would make itself unseeable.
    Stripped to a visible marker rather than escaped: inside a code span a
    backslash is literal, so escaping would print the backslash AND still
    break the span.
    """

    return "`" + value.replace("`", "<backtick>") + "`"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


@dataclass
class OutboxAlarm:
    """Turns repeated observations into at most one page per hour per condition.

    `decide` returns the text to send, or None. It NEVER sends, NEVER logs and
    NEVER raises on ordinary input — the caller is inside a drain loop that must
    not die because an alarm had an opinion.
    """

    #: Signature of the last condition SUCCESSFULLY DELIVERED, or None when the
    #: last delivered message was a recovery notice.
    _last_signature: tuple[int, frozenset[str]] | None = None
    _last_sent_at: float = field(default=0.0)
    #: What `decide` last returned and is waiting on `confirm_sent` for. Held
    #: separately BECAUSE A PAGE THAT WAS NEVER DELIVERED MUST NOT COUNT AS
    #: REPORTED — see `confirm_sent`.
    _pending: tuple[tuple[int, frozenset[str]] | None, float] | None = None

    def decide(
        self,
        *,
        exhausted: int,
        unroutable_types: frozenset[str],
        now: float,
    ) -> str | None:
        """The page to send, or None.

        Fires when either failure state is present. Re-fires only when the
        CONDITION CHANGED (a different count, or a different set of unrouted
        types) or when `REALERT_SECONDS` has passed. Returns a one-line recovery
        notice the first time it sees clean after having fired — without it, a
        reader cannot tell "resolved" from "the alarm died", which is the same
        ambiguity that makes a silent probe useless.
        """

        exhausted = max(0, int(exhausted))
        types = frozenset(unroutable_types or ())

        if exhausted == 0 and not types:
            if self._last_signature is None:
                return None
            self._pending = (None, now)
            return "GARUDA outbox recovered: no exhausted jobs, no unrouted job types."

        signature = (exhausted, types)
        changed = signature != self._last_signature
        stale = (now - self._last_sent_at) >= REALERT_SECONDS
        if not changed and not stale:
            return None

        self._pending = (signature, now)
        return self._compose(exhausted, types, repeat=not changed)

    def confirm_sent(self, now: float) -> None:
        """Commit the last `decide` result — call ONLY after the page landed.

        WHY THIS IS NOT DONE INSIDE `decide`. The first version committed
        `_last_signature`/`_last_sent_at` at decision time, so a page that the
        transport then FAILED to deliver still consumed the hour-long
        suppression window: the alarm went quiet for an hour precisely because
        it had just failed to reach anyone. That is the exact disease this
        module exists to cure, reintroduced one level down.

        With the commit split out, an undelivered page leaves the state
        untouched, `decide` sees the same unchanged-and-unreported condition on
        the next check, and it re-fires five minutes later instead of sixty.
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
    def _compose(exhausted: int, types: frozenset[str], *, repeat: bool) -> str:
        lines = ["GARUDA outbox needs a human." if not repeat else "GARUDA outbox STILL needs a human."]
        if exhausted:
            lines.append(
                f"{_plural(exhausted, 'job')} exhausted every retry and will never be "
                f"claimed again. Nothing else will notice them."
            )
        if types:
            # Sorted so the same condition always renders identically — an
            # alarm whose text wobbles between identical states defeats every
            # downstream dedup, including a human's.
            # Code spans, not escapes: a job type is an IDENTIFIER, and
            # `outbox_handlers` already treats ids this way — Markdown V1 does
            # not re-parse inside a span, so the name arrives verbatim instead
            # of carrying backslashes an operator would have to read past.
            lines.append(
                "Unrouted job type(s), enqueued with no handler: "
                + ", ".join(_code_span(t) for t in sorted(types))
            )
        return "\n".join(lines)
